import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from provider_directory_truth_layer.intake_api import create_workbench
from provider_directory_truth_layer.intake_store import IntakeStore, Conflict, VERSION
from provider_directory_truth_layer.reconciliation_store import ReconciliationStore

FIXTURES = Path(__file__).parent / 'fixtures/intake/fhir-plannet'
PAYLOAD = (FIXTURES / 'north-south.json').read_bytes()


def receive(store, payload=PAYLOAD, source='synthetic-fhir'):
    return store.receive(payload, 'directory.json', source=source, profile='fhir-plannet-r4')


def decision(receipt, **changes):
    return dict(expected_attempt=receipt['attempt_id'], policy='reference_resources',
                actor='Synthetic analyst', reason='Reviewed bounded reference evidence',
                request_id='accept-1', **changes)


@pytest.fixture
def store(tmp_path):
    return IntakeStore(tmp_path / 'test.sqlite3', tmp_path)


def test_native_acceptance_without_npi_creates_only_observations_and_survives_restart(store):
    receipt = receive(store)
    assert receipt['state'] == 'preview_ready'
    assert receipt['preview']['valid_count'] == 8
    assert receipt['preview']['native']['coverage']['assertion_count'] == 2
    accepted = store.commit(receipt['id'], decision(receipt))
    assert len(accepted['observations']) == 8
    locations = [o for o in accepted['observations'] if o['original']['resourceType'] == 'Location']
    assert len(locations) == 2
    assert all(o['provider_id'] is None and o['location_id'] is None for o in locations)
    assert accepted['linked_cases'] == []
    with store.db() as conn:
        for table in ('work_case', 'relationship', 'network', 'reviewed_identity_link', 'feed_version'):
            assert conn.execute(f'SELECT count(*) FROM {table}').fetchone()[0] == 0
        assert conn.execute('PRAGMA user_version').fetchone()[0] == VERSION
    reopened = IntakeStore(store.path, store.root)
    assert reopened.detail(receipt['id'])['observations'] == accepted['observations']


def test_identical_retry_changed_intent_and_terminal_conflicts(store):
    receipt = receive(store)
    request = decision(receipt)
    accepted = store.commit(receipt['id'], request)
    assert store.commit(receipt['id'], request) == accepted
    for changed in ({**request, 'reason': 'Different'}, {**request, 'request_id': 'different'}):
        with pytest.raises(Conflict):
            store.commit(receipt['id'], changed)
    newer = store.mapping(receipt['id'], {'expected_attempt': receipt['attempt_id']})
    # Identical uncertain retry returns its original selected attempt after reprocessing.
    assert store.commit(receipt['id'], request)['attempt_id'] == receipt['attempt_id']
    with pytest.raises(Conflict):
        store.commit(receipt['id'], {**request, 'request_id': 'stale'})
    assert newer['attempt_id'] != receipt['attempt_id']


def test_repeat_delivery_reuses_observations_but_keeps_receipt_and_decision(store):
    first = receive(store)
    accepted = store.commit(first['id'], decision(first))
    second = receive(store)
    repeat = store.commit(second['id'], decision(second))
    assert repeat['state'] == 'duplicate_delivery'
    assert repeat['duplicate_of'] == first['id']
    assert repeat['preview']['reuses_attempt'] == first['attempt_id']
    assert repeat['observations'] == accepted['observations']
    with store.db() as conn:
        assert conn.execute('SELECT count(*) FROM observation').fetchone()[0] == 8
        assert conn.execute('SELECT count(*) FROM attempt WHERE decision IS NOT NULL').fetchone()[0] == 2
    other = receive(store, source='other-source')
    assert store.commit(other['id'], decision(other))['state'] == 'committed'


@pytest.mark.parametrize('payload', [b'{}', b'{', b'{"resourceType":"Bundle","type":"searchset","entry":[]}'])
def test_invalid_and_empty_evidence_retained_but_not_accepted(store, payload):
    receipt = receive(store, payload)
    assert (store.artifacts / receipt['artifact_sha']).read_bytes() == payload
    with pytest.raises(ValueError):
        store.commit(receipt['id'], decision(receipt))
    rejected = store.commit(receipt['id'], {**decision(receipt), 'policy': 'reject'})
    assert rejected['state'] == 'rejected'
    assert rejected['observations'] == []


@pytest.mark.parametrize('change', [{'policy':'valid_rows'}, {'expected_attempt':None}, {'request_id':{}}, {'actor':[]}, {'extra':'bad'}])
def test_invalid_acceptance_cannot_change_observations(store, change):
    receipt = receive(store)
    with pytest.raises(ValueError):
        store.commit(receipt['id'], {**decision(receipt), **change})
    assert store.detail(receipt['id'])['observations'] == []


def test_clinic_mappings_cannot_reinterpret_native_resources(store):
    receipt = receive(store)
    with pytest.raises(ValueError):
        store.mapping(receipt['id'], {'mapping': {'npi':'id'}})
    assert store.detail(receipt['id'])['attempt_id'] == receipt['attempt_id']


def test_comparison_records_preserve_exact_support_and_office_values(store):
    receipt = receive(store)
    profile = ReconciliationStore(store).preview_input(receipt['id'], receipt['attempt_id'])
    assert profile['total'] == 2
    records = profile['items']
    assert {r['comparison']['phone'] for r in records} == {'6175550100','6175550200'}
    assert all(r['comparison']['address']['zip'] == '02108' for r in records)
    assert records[0]['clinician_ref'] == records[1]['clinician_ref']
    assert records[0]['ref'] != records[1]['ref']
    assert all(r['network_id'] is None and len(r['supporting_refs']) == 6 for r in records)


def test_http_upload_acceptance_artifact_packet_and_stale_conflict(tmp_path):
    client = TestClient(create_workbench(tmp_path/'http.db', tmp_path))
    response = client.post('/api/intakes/files?filename=directory.json&profile=fhir-plannet-r4&source=synthetic-fhir', content=PAYLOAD)
    assert response.status_code == 200, response.text
    receipt = response.json()
    rid = receipt['id']
    assert client.get(f'/api/intakes/{rid}/artifact').content == PAYLOAD
    response = client.post(f'/api/intakes/{rid}/commit', json=decision(receipt))
    assert response.status_code == 200, response.text
    packet = client.get(f'/api/intakes/{rid}/packet').json()
    assert packet['preview']['native']['coverage']['entry_count'] == 9
    assert len(packet['observations']) == 8
    assert packet['cases'] == []
    assert client.post(f'/api/intakes/{rid}/mapping', json={'expected_attempt':receipt['attempt_id']}).status_code == 200
    assert client.post(f'/api/intakes/{rid}/commit', json={**decision(receipt),'request_id':'new-stale'}).status_code == 409
    assert client.post('/api/intakes/files?filename=directory.json&profile=fhir-plannet-r4&completeness=full', content=PAYLOAD).status_code == 422


def test_native_field_decision_and_xlsx_keep_all_supporting_resources(store):
    import io
    import uuid
    from openpyxl import load_workbook
    from provider_directory_truth_layer.identity_review import IdentityReview
    from provider_directory_truth_layer.field_reconciliation import FieldReconciliation, workbook
    from provider_directory_truth_layer.change_impact import ChangeImpact

    value = json.loads(PAYLOAD)
    value['entry'][0]['resource']['identifier'].append({'system':'http://hl7.org/fhir/sid/us-npi','value':'1000000001'})
    native = receive(store, json.dumps(value).encode())
    store.commit(native['id'], decision(native))
    clinic = store.receive(json.dumps([{'record_id':'NORTH', 'npi':'1000000001', 'entity_type':'clinician',
        'provider_name':'Synthetic Example','address':'10 Example St','city':'Example','state':'MA',
        'zip':'02108','phone':'6175550199','location_id':'NORTH'}]).encode(), 'clinic.json', source='synthetic-clinic')
    comparison = ReconciliationStore(store)
    run = comparison.create_run({'inputs':[{'receipt_id':r['id'],'attempt_id':r['attempt_id']} for r in [native,clinic]],
                                 'actor':'Synthetic reviewer','reason':'Review source scope'})
    reviewer = IdentityReview(store)
    def approve(candidate, label):
        context = reviewer.inspect(run['id'], candidate['id'])
        return reviewer.decide({'run_id':run['id'],'candidate_id':candidate['id'],'decision':'approve',
            'request_id':uuid.uuid4().hex,'expected_snapshot':context['review_snapshot'],
            'expected_revisions':{ref:link['id'] if link else None for ref,link in context['current_links'].items()},
            'expected_decision':context['latest_decision']['id'] if context['latest_decision'] else None,
            'actor':'Synthetic reviewer','reason':'Explicit identity review','new_label':label})['decision']['target_id']
    person = approve(comparison.candidates(run['id'],kind='clinician',limit=100)['items'][0], 'Synthetic Example')
    candidate = next(c for c in comparison.candidates(run['id'],kind='location',limit=100)['items']
                     if c['left_record']['comparison']['address']['line1'] == c['right_record']['comparison']['address']['line1'])
    location = approve(candidate, 'NORTH')
    fields = FieldReconciliation(store)
    view = fields.inspect(person, location)
    phones = next(f for f in view['fields'] if f['field']=='phone')
    native_option = next(o for o in phones['options'] if o['source']=='synthetic-fhir')
    assert native_option['supporting_refs']
    fields.decide({'clinician_id':person,'location_id':location,'field':'phone','decision':'select',
        'selected_ref':native_option['ref'],'expected_snapshot':view['snapshot'],'expected_decision':None,
        'request_id':uuid.uuid4().hex,'actor':'Synthetic reviewer','reason':'Select retained NORTH evidence'})
    view = fields.inspect(person, location)
    exported = fields.export(person, location, view['snapshot'])
    native_rows = [c['row']['locator'] for c in exported['source_context'] if c['receipt']['id']==native['id']]
    assert set(native_rows) == {'$.entry[0].resource','$.entry[1].resource','$.entry[2].resource','$.entry[3].resource','$.entry[5].resource'}
    assert '$.entry[4].resource' not in native_rows  # SOUTH is shared artifact context, not selected NORTH evidence.
    assert any(o.get('supporting_refs') for f in exported['fields'] for o in f['options'])
    book = load_workbook(io.BytesIO(workbook(exported)), read_only=True)
    # Lossless payload chunks are authoritative; the JSON includes supporting locators.
    assert 'Payload' in book.sheetnames
    chunks = sorted(book['Payload'].iter_rows(min_row=2, values_only=True), key=lambda row:int(row[0]))
    assert json.loads(''.join(row[1] for row in chunks)) == exported
    book.close()
    impact = ChangeImpact(store)
    proposal = impact.create({'clinician_id':person,'location_id':location,'field':'phone',
        'proposed_value':{'number':'6175550188','extension':None},
        'inputs':[{'receipt_id':r['id'],'attempt_id':r['attempt_id']} for r in [native,clinic]],
        'network_ids':[], 'expected_snapshot':view['snapshot'], 'request_id':uuid.uuid4().hex,
        'actor':'Synthetic reviewer','reason':'Preview scoped change'})
    assessment = impact.preview(proposal['id'],limit=100)
    native_targets = [t for t in assessment['targets'] if t['source']=='synthetic-fhir']
    assert native_targets and all(t['supporting_refs'] for t in native_targets)
    old = view['snapshot']
    store.mapping(native['id'], {'expected_attempt':native['attempt_id']})
    with pytest.raises(Conflict):
        fields.export(person, location, old)


def test_bounded_native_http_samples_retain_full_counts_and_packet(tmp_path):
    value = json.loads(PAYLOAD)
    value['entry'] = [{'resource':{'resourceType':'Location','id':f'loc-{i}','name':'x'*5000,'status':'active'}} for i in range(80)]
    client = TestClient(create_workbench(tmp_path/'http.db', tmp_path))
    response = client.post('/api/intakes/files?filename=directory.json&profile=fhir-plannet-r4',content=json.dumps(value).encode())
    assert response.status_code == 200, response.text
    receipt = response.json()
    native = receipt['preview']['native']
    assert native['resources_count'] == 80 and len(native['resources']) == 50
    assert native['sample_truncated']
    packet = client.get(f"/api/intakes/{receipt['id']}/packet").json()
    assert len(packet['preview']['native']['resources']) == 80
    assert packet['preview']['rows'][0]['original']['name'] == 'x'*5000


def test_populated_clinic_approved_export_and_history_survive_native_acceptance(tmp_path):
    from test_managed_feed import setup_feed, deliver, approve
    from provider_directory_truth_layer.intake_store import packed
    store, service, feed, inbox = setup_feed(tmp_path)
    deliver(inbox)
    result = service.run_once(feed['id'], '2026-10-06T10:00:00+00:00')
    approve(service, result['version_id'])
    before = packed(service.export(result['version_id']))
    with store.db() as conn:
        history = [tuple(r) for r in conn.execute('SELECT * FROM work_event ORDER BY id')]
    native = receive(store)
    store.commit(native['id'], decision(native))
    assert packed(service.export(result['version_id'])) == before
    assert service.current(feed['id'])['version_id'] == result['version_id']
    with store.db() as conn:
        assert history == [tuple(r) for r in conn.execute('SELECT * FROM work_event ORDER BY id')]
        assert conn.execute('PRAGMA integrity_check').fetchone()[0] == 'ok'
        assert conn.execute('PRAGMA foreign_key_check').fetchall() == []


def test_native_acceptance_cannot_produce_labelled_validated_dataset(store):
    from provider_directory_truth_layer.onboarding_service import OnboardingService
    receipt = receive(store)
    store.commit(receipt['id'], decision(receipt))
    with pytest.raises(ValueError, match='evidence packet'):
        OnboardingService(store).dataset(receipt['id'])


def test_concurrent_identical_acceptance_has_one_observation_set(store):
    from concurrent.futures import ThreadPoolExecutor
    receipt = receive(store)
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(lambda _:store.commit(receipt['id'],decision(receipt)), range(2)))
    assert results[0] == results[1]
    with store.db() as conn:
        assert conn.execute('SELECT count(*) FROM observation').fetchone()[0] == 8


def test_mid_acceptance_failure_rolls_back_observations_and_decision(store):
    import sqlite3
    receipt = receive(store)
    with store.db() as conn:
        conn.execute("CREATE TRIGGER synthetic_abort BEFORE INSERT ON observation WHEN NEW.native_id='Location/north' BEGIN SELECT RAISE(ABORT,'synthetic failure'); END")
    with pytest.raises(sqlite3.IntegrityError, match='synthetic failure'):
        store.commit(receipt['id'], decision(receipt))
    with store.db() as conn:
        assert conn.execute('SELECT count(*) FROM observation').fetchone()[0] == 0
        assert conn.execute('SELECT decision FROM attempt WHERE id=?',(receipt['attempt_id'],)).fetchone()[0] is None
        conn.execute('DROP TRIGGER synthetic_abort')
    assert store.commit(receipt['id'], decision(receipt))['state'] == 'committed'
