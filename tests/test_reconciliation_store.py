"""Pinned retained comparisons, native address scope and immutable run recovery."""
import hashlib
import json
import sqlite3

import pytest
from fastapi.testclient import TestClient

from provider_directory_truth_layer.intake_api import create_workbench
from provider_directory_truth_layer.intake_store import Conflict, IntakeStore, VERSION
from provider_directory_truth_layer.reconciliation_store import ReconciliationStore


def row(**extra):
    return {'record_id': '001', 'npi': '1000000001', 'provider_name': 'Alex Synthetic',
        'address': '10 Example Street STE 100', 'address_line2': None, 'city': 'Boston',
        'state': 'MA', 'zip': '02108', 'phone': '212-555-0101 ext 007',
        'location_id': 'NORTH', 'entity_type': 'clinician', **extra}


@pytest.fixture
def store(tmp_path):
    return IntakeStore(tmp_path / 'db.sqlite3', tmp_path / 'runtime')


def receive(store, source, rows=None, scope='clinic-roster'):
    return store.receive(json.dumps(rows or [row()]).encode(), 'synthetic.json', source=source,
                         metadata={'scope': scope})


def selection(receipt):
    return {'receipt_id': receipt['id'], 'attempt_id': receipt['attempt_id'], 'entity_kind': 'clinician'}


def create(service, *receipts):
    return service.create_run({'inputs': list(map(selection, receipts)), 'actor': 'Synthetic Reviewer', 'reason': 'Compare selected sources'})


def test_source_quality_matches_durable_evidence_and_does_not_accept_quarantine(store):
    receipt = receive(store, 'clinic')
    source = store.detail(receipt['id'])
    durable = source['preview']['rows'][0]['comparison_values'][0]
    assert durable['comparison']['address']['suite'] == '100'
    assert durable['comparison']['phone_extension'] == '007'
    assert source['state'] == 'preview_ready'
    assert source['preview']['quarantined_count'] == 1  # Legacy phone validation doesn't infer extensions.
    before = hashlib.sha256(store.path.read_bytes()).hexdigest()
    quality = ReconciliationStore(store).preview_input(receipt['id'], receipt['attempt_id'])
    assert quality['total'] == 1
    assert quality['items'][0]['comparison']['phone_extension'] == '007'
    assert quality['items'][0]['source_problems']
    assert store.detail(receipt['id'])['observations'] == []
    assert hashlib.sha256(store.path.read_bytes()).hexdigest() == before


def test_typed_candidates_pin_originals_reproduce_and_survive_restart(store):
    a = receive(store, 'clinic')
    b = receive(store, 'payer', [row(phone='2125550199')])
    c = receive(store, 'reference', [row(address='10 EXAMPLE ST', native_addresses=[
        {'line1': '90 Mailing Road', 'suite': '100', 'city': 'Boston', 'state': 'MA', 'zip': '02108', 'kind': 'mailing'},
        {'line1': '10 Example Street', 'suite': '100', 'city': 'Boston', 'state': 'MA', 'zip': '02108', 'kind': 'practice'}])])
    service = ReconciliationStore(store)
    run = create(service, a, b, c)
    assert run['inputs_fresh']
    assert run['metrics']['input_records'] == 3
    assert run['metrics']['address_references'] == 4
    all_candidates = service.candidates(run['id'], limit=100)
    assert {item['kind'] for item in all_candidates['items']} == {'clinician', 'location'}
    for candidate in service.candidates(run['id'], kind='location')['items']:
        assert candidate['left_record']['address']['kind'] == candidate['right_record']['address']['kind'] == 'practice'
    again = create(service, a, b, c)
    assert [row['id'] for row in service.candidates(again['id'])['items']] == [row['id'] for row in all_candidates['items']]
    restarted = ReconciliationStore(IntakeStore(store.path, store.root))
    assert restarted.candidates(run['id'], limit=100) == all_candidates
    with store.db() as conn:
        assert conn.execute('SELECT count(*) FROM observation').fetchone()[0] == 0
        assert conn.execute('SELECT count(*) FROM work_event').fetchone()[0] == 0
        with pytest.raises(sqlite3.IntegrityError, match='Immutable'):
            conn.execute('DELETE FROM comparison_run WHERE id=?', (run['id'],))


def test_stale_interpretation_and_new_accepted_baseline_are_visible(store):
    a = receive(store, 'clinic', [row(phone='2125550101')])
    b = receive(store, 'payer', [row(phone='2125550199')])
    service = ReconciliationStore(store)
    run = create(service, a, b)
    other_scope = receive(store, 'clinic', [row(phone='2125550123')], scope='unrelated')
    store.commit(other_scope['id'], {'actor': 'Reviewer', 'reason': 'Unrelated scope', 'policy': 'valid_rows'})
    assert service.run(run['id'])['inputs_fresh']
    incoming = receive(store, 'clinic', [row(phone='2125550123')])
    store.commit(incoming['id'], {'actor': 'Reviewer', 'reason': 'New accepted source', 'policy': 'valid_rows'})
    assert not service.run(run['id'])['inputs_fresh']
    newer = create(service, a, b)
    assert newer['inputs_fresh']  # Explicit old evidence can be selected, with current baseline pinned.
    store.mapping(a['id'], {})
    assert not service.run(newer['id'])['inputs_fresh']
    with pytest.raises(Conflict, match='current'):
        create(service, a, b)


def test_input_type_declarations_scope_and_candidate_limits(store, monkeypatch):
    a = receive(store, 'clinic')
    b = receive(store, 'payer')
    service = ReconciliationStore(store)
    with pytest.raises(ValueError, match='each receipt'):
        create(service, a, a)
    same_source = receive(store, 'clinic', [row(record_id='002')])
    with pytest.raises(ValueError, match='namespaces'):
        create(service, a, same_source)
    with pytest.raises(ValueError, match='conflicts'):
        service.create_run({'inputs': [{**selection(a), 'entity_kind': 'organization'}, selection(b)], 'actor': 'R', 'reason': 'Conflict'})
    monkeypatch.setattr('provider_directory_truth_layer.reconciliation_store.MAX_CANDIDATES', 0)
    with pytest.raises(ValueError, match='cap exceeded'):
        create(service, a, b)
    assert service.runs()['total'] == 0


def test_http_run_history_paging_unknown_and_freshness(tmp_path):
    client = TestClient(create_workbench(tmp_path / 'db.sqlite3', tmp_path / 'runtime', demo=False))
    def upload(source):
        response = client.post('/api/intakes/files', params={'filename': 'synthetic.json', 'source': source}, content=json.dumps([row()]))
        assert response.status_code == 200
        return response.json()
    a, b = upload('clinic'), upload('payer')
    assert client.get(f"/api/intakes/{a['id']}/comparison-profile", params={'expected_attempt': a['attempt_id']}).json()['total'] == 1
    response = client.post('/api/reconciliation/runs', json={'inputs': [selection(a), selection(b)], 'actor': 'Reviewer', 'reason': 'Compare'})
    assert response.status_code == 200
    run = response.json()
    first = client.get(f"/api/reconciliation/runs/{run['id']}/candidates?limit=1").json()
    assert first['total'] == 2 and first['next_offset'] == 1
    assert client.get(f"/api/reconciliation/runs/{run['id']}/candidates?kind=bad").status_code == 422
    assert client.get('/api/reconciliation/runs/unknown').status_code == 404
    assert client.get('/api/reconciliation/runs?limit=0').status_code == 422
    assert client.get('/api/reconciliation/runs').json()['total'] == 1
    assert client.get('/api/work').json()['items'] == []


def test_schema_five_upgrade_and_injected_failure_preserve_recipe_history(store, monkeypatch):
    from provider_directory_truth_layer import reconciliation_store
    from provider_directory_truth_layer.onboarding_service import OnboardingService
    receipt = receive(store, 'clinic')
    onboarding = OnboardingService(store)
    fields = ['npi', 'provider_name', 'address', 'city', 'state', 'zip', 'phone']
    proposal = onboarding.propose(receipt['id'], {
        'definition': {'version': 1, 'mapping': {field: field for field in fields},
                       'transforms': {'phone': ['phone_us']}, 'required': fields},
        'expected_attempt': receipt['attempt_id'], 'name': 'Retained recipe',
        'actor': 'Synthetic proposer', 'reason': 'Migration preservation fixture'})
    onboarding.approve(receipt['id'], proposal['id'], {
        'expected_attempt': receipt['attempt_id'], 'actor': 'Synthetic reviewer',
        'reason': 'Explicitly reviewed fixture'})
    recipes_before = onboarding.recipes(receipt['id'])
    before = store.detail(receipt['id'])
    with store.db() as conn:
        from schema_helpers import remove_managed_schema
        remove_managed_schema(conn)
        conn.executescript('DROP TABLE follow_up_acknowledgement; DROP TABLE follow_up_association; DROP TABLE follow_up_confirmation; DROP TABLE change_proposal; DROP TABLE reconciled_field_decision; DROP TABLE reviewed_identity_link; DROP TABLE identity_review_decision; DROP TABLE clinician_identity; DROP TABLE observation_comparison; DROP TABLE comparison_candidate; DROP TABLE comparison_run; DELETE FROM schema_migration WHERE version>=6; PRAGMA user_version=5;')
    migration = reconciliation_store.MIGRATION_6
    monkeypatch.setattr(reconciliation_store, 'MIGRATION_6', migration + '\nINVALID SQL;')
    with pytest.raises(sqlite3.OperationalError):
        IntakeStore(store.path, store.root)
    with sqlite3.connect(store.path) as conn:
        assert conn.execute('PRAGMA user_version').fetchone()[0] == 5
        assert conn.execute('PRAGMA integrity_check').fetchone()[0] == 'ok'
    monkeypatch.setattr(reconciliation_store, 'MIGRATION_6', migration)
    restored = IntakeStore(store.path, store.root)
    assert restored.detail(receipt['id']) == before
    assert OnboardingService(restored).recipes(receipt['id']) == recipes_before
    with restored.db() as conn:
        assert conn.execute('PRAGMA user_version').fetchone()[0] == VERSION
        assert conn.execute('PRAGMA foreign_key_check').fetchall() == []
    with sqlite3.connect(store.path.with_name(store.path.name + '.pre-intake-v6.bak')) as backup:
        assert backup.execute('PRAGMA user_version').fetchone()[0] == 5


def test_run_rejects_interpretation_changed_before_first_snapshot(store, monkeypatch):
    a, b = receive(store, 'clinic'), receive(store, 'payer')
    service = ReconciliationStore(store)
    original = service._input
    changed = False
    def change_after_read(selected):
        nonlocal changed
        result = original(selected)
        if not changed:
            changed = True
            store.mapping(a['id'], {})
        return result
    monkeypatch.setattr(service, '_input', change_after_read)
    with pytest.raises(Conflict, match='changed'):
        create(service, a, b)
    assert service.runs()['total'] == 0


def test_flat_json_null_and_mapped_tabular_suite_are_retained(store):
    receipt = receive(store, 'nulls', [row(npi=None, phone=None, provider_name='')])
    record = ReconciliationStore(store).preview_input(receipt['id'], receipt['attempt_id'])['items'][0]
    assert record['original_fields']['npi'] is None
    assert record['comparison']['npi'] is None
    assert record['original_fields']['provider_name'] == ''
    assert 'null' in record['field_findings']['npi']
    payload = b'record_id,npi,provider_name,address,address_line2,suite,city,state,zip,phone,location_id\n001,1000000001,Synthetic,10 Example St,,04,Boston,MA,02108,2125550101,NORTH\n'
    receipt = store.receive(payload, 'suite.csv', source='suite')
    assert receipt['preview']['mapping']['suite'] == 'suite'
    assert receipt['preview']['rows'][0]['comparison_values'][0]['comparison']['address']['suite'] == '04'
    accepted = store.commit(receipt['id'], {'actor': 'Reviewer', 'reason': 'Explicit suite', 'policy': 'valid_rows'})
    assert accepted['observations'][0]['comparison_values']['records'][0]['original_fields']['address']['suite'] == '04'


def test_native_nppes_phone_is_scoped_to_each_actual_address(store):
    payload = {'result_count': 1, 'results': [{'number': 1000000001, 'enumeration_type': 'NPI-1',
        'basic': {'first_name': 'Alex', 'last_name': 'Synthetic'},
        'addresses': [{'address_1': '10 Example St', 'address_2': 'STE 04', 'city': 'Boston', 'state': 'MA',
                       'postal_code': '02108', 'telephone_number': '2125550101', 'address_purpose': 'LOCATION'},
                      {'address_1': '20 Example St', 'address_2': 'STE 40', 'city': 'Boston', 'state': 'MA',
                       'postal_code': '02108', 'telephone_number': '2125550102', 'address_purpose': 'LOCATION'}]}]}
    receipt = store.receive(json.dumps(payload).encode(), 'nppes.json', source='reference', profile='nppes')
    quality = ReconciliationStore(store).preview_input(receipt['id'], receipt['attempt_id'])
    assert [item['comparison']['phone'] for item in quality['items']] == ['2125550101', '2125550102']
    assert [item['comparison']['address']['suite'] for item in quality['items']] == ['04', '40']
    assert [item['address_path'] for item in quality['items']] == ['addresses[0]', 'addresses[1]']


def test_native_unscoped_root_phone_not_copied_to_two_practice_offices(store):
    offices = [{'line1': f'{number} Example St', 'suite': '04', 'city': 'Boston', 'state': 'MA',
                'zip': '02108', 'kind': 'practice'} for number in (10, 20)]
    receipt = receive(store, 'clinic', [row(native_addresses=offices)])
    records = ReconciliationStore(store).preview_input(receipt['id'], receipt['attempt_id'])['items']
    assert [item['comparison']['phone'] for item in records] == [None, None]


def test_malformed_suite_arrays_cannot_be_eligible_locations(store):
    offices = [{'line1': '10 Example St', 'suite': ['04'], 'city': 'Boston', 'state': 'MA', 'zip': '02108', 'kind': 'practice'}]
    a = receive(store, 'clinic', [row(native_addresses=offices)])
    b = receive(store, 'payer', [row(native_addresses=offices)])
    service = ReconciliationStore(store)
    run = create(service, a, b)
    candidates = service.candidates(run['id'], kind='location')['items']
    assert candidates and not any(candidate['eligible'] for candidate in candidates)
    assert candidates[0]['left_record']['original_fields']['address']['suite'] == ['04']


def test_interactive_sampling_bounds_malformed_containers_but_export_retains_them(store):
    malformed = ['x' * 1000 for _ in range(1000)]
    a = receive(store, 'clinic', [row(provider_name=malformed)])
    b = receive(store, 'payer', [row()])
    service = ReconciliationStore(store)
    quality = service.preview_input(a['id'], a['attempt_id'])
    assert quality['sample_truncated'] and len(json.dumps(quality)) < 100_000
    assert isinstance(quality['items'][0]['ref'], str)
    run = create(service, a, b)
    page = service.candidates(run['id'])
    assert len(json.dumps(page)) < 150_000
    before = hashlib.sha256(store.path.read_bytes()).hexdigest()
    exported = service.export(run['id'])
    record = next(record for record in exported['records'] if record['receipt_id'] == a['id'])
    assert record['original_fields']['provider_name'] == malformed
    assert hashlib.sha256(store.path.read_bytes()).hexdigest() == before


@pytest.mark.parametrize('masked', [None, 'unknown', {}, 'clinician'])
@pytest.mark.parametrize('profile', ['flat','nppes'])
def test_entity_discriminator_aliases_cannot_mask_known_organization(masked,profile):
    from provider_directory_truth_layer.comparison_inputs import entity_kind
    original={'entity_type':masked,'enumeration_type':'NPI-2'}
    expected='unknown' if masked=='clinician' else 'organization'
    assert entity_kind(original,profile)==expected
    with pytest.raises(ValueError,match='conflict'):
        entity_kind(original,profile,'clinician')


def test_contradictory_source_types_remain_unknown_and_cannot_be_declared_away(store):
    a=receive(store,'contradictory',[row(entity_type='clinician',enumeration_type='NPI-2')])
    b=receive(store,'known')
    quality=ReconciliationStore(store).preview_input(a['id'],a['attempt_id'])
    record=quality['items'][0]
    assert record['comparison']['entity_kind']=='unknown' and record['entity_kind_conflict']
    assert record['entity_kind_evidence']=={'entity_type':'clinician','enumeration_type':'NPI-2'}
    with pytest.raises(ValueError,match='conflict'):
        create(ReconciliationStore(store),a,b)
