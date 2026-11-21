"""Real source onboarding, accepted lineage, scope isolation and recovery."""
import csv
import hashlib
import io
import json
import sqlite3

import pytest
from fastapi.testclient import TestClient
from openpyxl import Workbook

from provider_directory_truth_layer.intake_api import create_workbench
from provider_directory_truth_layer.intake_store import IntakeStore, Conflict, VERSION
from provider_directory_truth_layer.onboarding_service import OnboardingService


FIELDS = ['record_id', 'npi', 'provider_name', 'address', 'city', 'state', 'zip', 'phone', 'location_id']
HEADERS = ['Source record', 'Practitioner ID', 'Clinician name', 'Office address', 'Town', 'Region', 'Postal', 'Office Tel', 'Office ID']
GOOD = ['001', '1000000001', '  Synthetic   Clinician ', '10 Example St', 'Example', ' tn ', '02108', '+1 (615) 555-0100 ext 23', 'NORTH']


def payload(rows=None, filetype='csv'):
    rows = rows or [GOOD, ['002', '', *GOOD[2:]]]
    stream = io.BytesIO() if filetype == 'xlsx' else io.StringIO()
    if filetype == 'xlsx':
        workbook = Workbook()
        worksheet = workbook.active
        worksheet.append(HEADERS)
        for row in rows:
            worksheet.append(row)
        workbook.save(stream)
    elif filetype == 'json':
        return json.dumps([dict(zip(HEADERS, row)) for row in rows]).encode()
    else:
        writer = csv.writer(stream)
        writer.writerow(HEADERS)
        writer.writerows(rows)
    return stream.getvalue() if filetype == 'xlsx' else stream.getvalue().encode()


def definition():
    return {'version': 1, 'mapping': dict(zip(FIELDS, HEADERS)),
            'transforms': {'phone': ['phone_us'], 'state': ['state_us'], 'zip': ['zip_us'],
                           'provider_name': ['trim', 'collapse_spaces']}, 'required': FIELDS[:8]}


@pytest.fixture
def store(tmp_path):
    return IntakeStore(tmp_path / 'directory.sqlite3', tmp_path / 'retained')


def review(service, receipt):
    proposal = service.propose(receipt['id'], {'definition': definition(), 'expected_attempt': receipt['attempt_id'],
        'name': 'Synthetic provider roster', 'actor': 'Agent proposal', 'reason': 'Explicit source mapping'})
    approved = service.approve(receipt['id'], proposal['id'], {'expected_attempt': receipt['attempt_id'],
        'actor': 'Synthetic human reviewer', 'reason': 'Reviewed original and preview'})
    return proposal, approved


@pytest.mark.parametrize('filetype', ['csv', 'xlsx', 'json'])
def test_end_to_end_recipe_acceptance_originals_extension_and_restart(store, filetype):
    original = payload(filetype=filetype)
    receipt = store.receive(original, 'roster.' + filetype, source='clinic:synthetic', metadata={'scope': 'monthly'})
    service = OnboardingService(store)
    before = hashlib.sha256(store.path.read_bytes()).hexdigest()
    profile = service.inspect(receipt['id'])
    preview = service.preview(receipt['id'], definition(), receipt['attempt_id'])
    assert hashlib.sha256(store.path.read_bytes()).hexdigest() == before
    assert profile['row_count'] == preview['total'] == 2
    assert profile['suggested_mapping']['phone'] == 'Office Tel'
    assert preview['valid_count'] == preview['quarantined_count'] == 1
    assert preview['rows'][0]['normalized']['phone'] == '6155550100'
    assert preview['rows'][0]['normalized']['phone_extension'] == '23'
    proposed, approved = review(service, receipt)
    assert proposed['state'] == 'proposed' and approved['parent_id'] == proposed['id']
    with pytest.raises(ValueError, match='approved'):
        service.apply(receipt['id'], proposed['id'], receipt['attempt_id'])
    mapped = service.apply(receipt['id'], approved['id'], receipt['attempt_id'])
    assert mapped['state'] == 'preview_ready'
    assert mapped['preview']['valid_count'] == 1
    assert mapped['observations'] == []
    accepted = store.commit(receipt['id'], {'actor': 'Reviewer', 'reason': 'Accept reviewed rows only',
        'expected_attempt': mapped['attempt_id'], 'policy': 'valid_rows'})
    dataset = service.dataset(receipt['id'])
    assert len(dataset['records']) == len(dataset['quarantine']) == 1
    record = dataset['records'][0]
    assert record['normalized']['zip'] == '02108'
    assert record['normalization']['recipe_id'] == approved['id']
    assert record['normalization']['fields']['phone']['original'] == GOOD[7]
    assert store.artifacts.joinpath(accepted['artifact_sha']).read_bytes() == original
    restarted = OnboardingService(IntakeStore(store.path, store.root))
    assert restarted.dataset(receipt['id']) == dataset
    repeated = store.receive(original, 'roster.' + filetype, source='clinic:synthetic', metadata={'scope': 'monthly'})
    repeated = store.commit(repeated['id'], {'actor': 'Reviewer', 'reason': 'Repeated delivery', 'policy': 'valid_rows'})
    assert repeated['state'] == 'duplicate_delivery'
    assert service.dataset(repeated['id'])['records'] == dataset['records']


def test_stale_review_scope_and_immutable_approval(store):
    receipt = store.receive(payload(), 'roster.csv', source='a', metadata={'scope': 'one'})
    service = OnboardingService(store)
    proposal, approved = review(service, receipt)
    assert service.approve(receipt['id'], proposal['id'], {'expected_attempt': receipt['attempt_id'],
        'actor': 'Second reviewer', 'reason': 'Retry'})['id'] == approved['id']
    other = store.receive(payload(), 'roster.csv', source='a', metadata={'scope': 'two'})
    assert service.recipes(other['id'])['items'] == []
    with pytest.raises(ValueError, match='scope'):
        service.apply(other['id'], approved['id'], other['attempt_id'])
    store.mapping(receipt['id'], {'mapping': definition()['mapping']})
    with pytest.raises(Conflict):
        service.preview(receipt['id'], definition(), receipt['attempt_id'])
    with pytest.raises(Conflict):
        service.approve(receipt['id'], proposal['id'], {'actor': 'Reviewer', 'reason': 'Stale', 'expected_attempt': receipt['attempt_id']})
    with store.db() as conn, pytest.raises(sqlite3.IntegrityError, match='Immutable'):
        conn.execute('UPDATE recipe_revision SET state=? WHERE id=?', ('approved', proposal['id']))


def test_changed_delivery_recipe_reuse_header_drift_and_full_dataset(store):
    first = store.receive(payload([GOOD]), 'roster.csv', source='a')
    service = OnboardingService(store)
    _, approved = review(service, first)
    mapped = service.apply(first['id'], approved['id'], first['attempt_id'])
    store.commit(first['id'], {'actor': 'Reviewer', 'reason': 'Baseline', 'policy': 'valid_rows'})
    second = store.receive(payload([GOOD[:7] + ['615-555-0199'] + GOOD[8:]]), 'roster.csv', source='a')
    mapped = service.apply(second['id'], approved['id'], second['attempt_id'])
    assert mapped['preview']['comparison']['changed'] == 1
    store.commit(second['id'], {'actor': 'Reviewer', 'reason': 'Changed source', 'policy': 'valid_rows'})
    broken = store.receive(payload().replace(b'Office Tel', b'Published telephone'), 'roster.csv', source='a')
    mapped = service.apply(broken['id'], approved['id'], broken['attempt_id'])
    assert mapped['state'] == 'needs_mapping'
    assert 'do not exist' in mapped['preview']['error']
    with pytest.raises(ValueError, match='Accept'):
        service.dataset(broken['id'])
    assert service.dataset(first['id'])['records'][0]['normalized']['phone'] == '6155550100'


def test_http_validation_bounds_proposals_and_dataset(tmp_path):
    client = TestClient(create_workbench(tmp_path / 'db.sqlite3', tmp_path / 'retained', demo=False))
    receipt = client.post('/api/intakes/files?filename=roster.csv&source=synthetic', content=payload()).json()
    base = '/api/intakes/' + receipt['id']
    assert client.get(base + '/profile?limit=0').status_code == 422
    assert client.get(base + '/profile?limit=2').json()['next_offset'] == 2
    assert client.get(base + '/dataset').status_code == 422
    assert client.post(base + '/normalization/preview', json={'definition': definition()}).status_code == 422
    body = {'definition': definition(), 'expected_attempt': receipt['attempt_id']}
    preview = client.post(base + '/normalization/preview', json={**body, 'limit': 1}).json()
    assert len(preview['rows']) == 1 and preview['total'] == 2 and preview['next_offset'] == 1
    assert client.post(base + '/recipes', json=body).status_code == 422
    draft = client.post(base + '/recipes', json={**body, 'name': 'Reviewed', 'actor': 'Agent', 'reason': 'Proposal'}).json()
    approved = client.post(base + '/recipes/' + draft['id'] + '/approve', json={
        'expected_attempt': receipt['attempt_id'], 'actor': 'Human', 'reason': 'Reviewed'}).json()
    applied = client.post(base + '/recipes/' + approved['id'] + '/apply', json={'expected_attempt': receipt['attempt_id']}).json()
    assert client.post(base + '/commit', json={'actor': 'Human', 'reason': 'Reviewed',
        'policy': 'valid_rows', 'expected_attempt': applied['attempt_id']}).status_code == 200
    exported = client.get(base + '/dataset')
    assert 'attachment' in exported.headers['content-disposition']
    assert len(exported.json()['records']) == 1


def test_populated_v4_upgrade_retains_exact_evidence_and_backup(store):
    receipt = store.receive(payload([GOOD]), 'roster.csv')
    before = store.detail(receipt['id'])
    # Reconstruct a genuine v4 schema on this invocation-owned database only.
    with store.db() as conn:
        from schema_helpers import remove_managed_schema
        remove_managed_schema(conn)
        conn.executescript('DROP TABLE follow_up_acknowledgement; DROP TABLE follow_up_association; DROP TABLE follow_up_confirmation; DROP TABLE change_proposal; DROP TABLE reconciled_field_decision; DROP TABLE reviewed_identity_link; DROP TABLE identity_review_decision; DROP TABLE clinician_identity; DROP TABLE observation_comparison; DROP TABLE comparison_candidate; DROP TABLE comparison_run; DROP TABLE observation_normalization; DROP TABLE recipe_revision; DELETE FROM schema_migration WHERE version>4; PRAGMA user_version=4;')
    restored = IntakeStore(store.path, store.root)
    assert restored.detail(receipt['id']) == before
    backup = store.path.with_name(store.path.name + '.pre-intake-v5.bak')
    with sqlite3.connect(backup) as conn:
        assert conn.execute('PRAGMA user_version').fetchone()[0] == 4
        assert conn.execute('PRAGMA integrity_check').fetchone()[0] == 'ok'
    with restored.db() as conn:
        assert conn.execute('PRAGMA user_version').fetchone()[0] == VERSION
        assert conn.execute('PRAGMA foreign_key_check').fetchall() == []


def test_recipe_cannot_relax_application_required_values_or_hide_truncation(store):
    service = OnboardingService(store)
    blank = GOOD.copy()
    blank[2:6] = [' ', ' ', '\t', ' ']
    receipt = store.receive(payload([blank]), 'blank.csv')
    recipe = {**definition(), 'required': [], 'transforms': {}}
    preview = service.preview(receipt['id'], recipe, receipt['attempt_id'])
    assert preview['valid_count'] == 0
    assert 'Missing provider_name' in preview['rows'][0]['problems']
    huge = GOOD.copy()
    huge[2] = 'A' * 50_000
    receipt = store.receive(payload([huge]), 'huge.csv')
    profile = service.inspect(receipt['id'])
    assert profile['sample_truncated']
    assert all(isinstance(column['name'], str) for column in profile['columns'])
    preview = service.preview(receipt['id'], definition(), receipt['attempt_id'])
    assert preview['sample_truncated'] and preview['total'] == 1
    assert isinstance(preview['rows'][0]['problems'], list)
    assert len(json.dumps(preview)) < 40_000
    draft, approved = review(service, receipt)
    service.apply(receipt['id'], approved['id'], receipt['attempt_id'])
    store.commit(receipt['id'], {'actor': 'Reviewer', 'reason': 'Full retained evidence reviewed', 'policy': 'valid_rows'})
    assert service.dataset(receipt['id'])['records'][0]['normalized']['provider_name'] == 'A' * 50_000


def test_recipe_json_duplicate_policy_matches_pure_preview_and_applied_attempt(store):
    receipt = store.receive(payload([GOOD, GOOD], filetype='json'), 'duplicate.json')
    service = OnboardingService(store)
    preview = service.preview(receipt['id'], definition(), receipt['attempt_id'])
    assert preview['valid_count'] == 0 and preview['quarantined_count'] == 2
    _, approved = review(service, receipt)
    applied = service.apply(receipt['id'], approved['id'], receipt['attempt_id'])
    assert applied['preview']['valid_count'] == 0 and applied['preview']['quarantined_count'] == 2
    with pytest.raises(ValueError, match='No valid rows'):
        store.commit(receipt['id'], {'actor': 'Reviewer', 'reason': 'Check duplicate rejection', 'policy': 'valid_rows'})


def test_failed_recipe_migration_rolls_back_and_preserves_v4_receipt(store, monkeypatch):
    from provider_directory_truth_layer import onboarding_service
    receipt = store.receive(payload([GOOD]), 'retained.csv')
    with store.db() as conn:
        from schema_helpers import remove_managed_schema
        remove_managed_schema(conn)
        conn.executescript('DROP TABLE follow_up_acknowledgement; DROP TABLE follow_up_association; DROP TABLE follow_up_confirmation; DROP TABLE change_proposal; DROP TABLE reconciled_field_decision; DROP TABLE reviewed_identity_link; DROP TABLE identity_review_decision; DROP TABLE clinician_identity; DROP TABLE observation_comparison; DROP TABLE comparison_candidate; DROP TABLE comparison_run; DROP TABLE observation_normalization; DROP TABLE recipe_revision; DELETE FROM schema_migration WHERE version>4; PRAGMA user_version=4;')
    before = store.artifacts.joinpath(receipt['artifact_sha']).read_bytes()
    monkeypatch.setattr(onboarding_service, 'MIGRATION_5', onboarding_service.MIGRATION_5 + '\nTHIS IS INVALID SQL;')
    with pytest.raises(sqlite3.OperationalError):
        IntakeStore(store.path, store.root)
    with sqlite3.connect(store.path) as conn:
        assert conn.execute('PRAGMA user_version').fetchone()[0] == 4
        assert conn.execute("SELECT count(*) FROM sqlite_master WHERE name='recipe_revision'").fetchone()[0] == 0
        assert conn.execute('SELECT count(*) FROM receipt WHERE id=?', (receipt['id'],)).fetchone()[0] == 1
        assert conn.execute('PRAGMA integrity_check').fetchone()[0] == 'ok'
    assert store.artifacts.joinpath(receipt['artifact_sha']).read_bytes() == before
