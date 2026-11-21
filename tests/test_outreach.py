"""Investigation contracts: scoped assertions, accountable decisions, and readable handoff."""
import io
import json
import hashlib
import pytest
from openpyxl import load_workbook
from fastapi.testclient import TestClient
from provider_directory_truth_layer.intake_store import IntakeStore, Conflict
from provider_directory_truth_layer.intake_api import create_workbench
from provider_directory_truth_layer.work_export import snapshot, handoff_workbook
from provider_directory_truth_layer.operations_sql import run


@pytest.fixture
def investigation(tmp_path):
    store = IntakeStore(tmp_path / 'directory.sqlite3', tmp_path)
    rows = b'record_id,npi,provider_name,address,city,state,zip,phone,location_id,reference_phone\nN,1000000001,Synthetic Clinician,10 Example St,Example,MA,02108,6175550100,NORTH,6175550199\nS,1000000001,Synthetic Clinician,20 Example St,Example,MA,02108,6175550200,SOUTH,6175550299\n'
    receipt = store.receive(rows, 'synthetic-investigation.csv', source='synthetic-investigation', designation='synthetic')
    accepted = store.commit(receipt['id'], {'actor':'Analyst', 'reason':'Synthetic data', 'policy':'valid_rows'})
    cases = [store.case(c['id']) for c in accepted['linked_cases'] if c['kind'] == 'correction']
    north = next(c for c in cases if c['location_id'].endswith(':NORTH'))
    south = next(c for c in cases if c['location_id'].endswith(':SOUTH'))
    return store, north, south


def contact(**changes):
    return dict(action='outreach', actor='Analyst', reason='Investigate conflicting phones', expected_version=0,
                contact_at='2026-11-03T09:00:00-05:00', method='phone', outcome='no_answer', **changes)


def test_complete_investigation_preserves_scope_and_exports(investigation):
    store, north, south = investigation
    before_south = store.case(south['id'])
    originals = {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in store.artifacts.iterdir()}
    c = store.event(north['id'], dict(action='assign', actor='Analyst', reason='Own investigation', expected_version=0, owner='Analyst', follow_up='2026-11-04'))
    initial = {k:c[k] for k in ['status','owner','follow_up','proposal','observed','evidence']}
    payload = contact(); payload['expected_version'] = c['version']
    c = store.event(c['id'], payload)
    assert {k:c[k] for k in initial} == initial
    payload.update(expected_version=c['version'], outcome='response_received', response_summary='Office supplied its NORTH number', reported_phone='617-555-0199', respondent_role='Office manager')
    c = store.event(c['id'], payload)
    for action, extra in [('triage', {}), ('approve', {'proposal':'6175550199'}), ('submit', {'submission_reference':'SIMULATED ticket'}), ('verify', {'observed':'6175550100','verification_note':'Synthetic downstream still has old number'})]:
        c = store.event(c['id'], dict(action=action, actor='Analyst', reason='Synthetic exercise', expected_version=c['version'], **extra))
    assert c['status'] == 'reopened'
    assert store.case(south['id']) == before_south
    reopened = IntakeStore(store.path, store.root)
    assert reopened.case(c['id']) == c
    data = snapshot(store.path, c['id'])
    summary = data['investigations'][0]
    assert summary['case_id'] == c['id'] and len(summary['outreach']) == 2
    assert summary['latest_submission']['payload']['submission_reference'] == 'SIMULATED ticket'
    assert summary['latest_verification']['to_status'] == 'reopened'
    assert {item['case_id'] for item in data['investigations']} == {c['id']}
    assert len(run(store.path, 'phone-review', as_of='2026-11-05')) == 2
    book = load_workbook(io.BytesIO(handoff_workbook(store.path, c['id'])))
    assert book['Investigation'].max_row == 2 and book['Outreach'].max_row == 3
    assert all(cell.data_type != 'f' for sheet in book for row in sheet for cell in row)
    assert originals == {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in store.artifacts.iterdir()}


@pytest.mark.parametrize('changes', [
    {'contact_at':'2026-11-03'}, {'contact_at':'2026-11-03T09:00:00'},
    {'method':'sms'}, {'outcome':'closed'}, {'reported_phone':'6175550199'},
    {'outcome':'response_received'}, {'owner':'Accidental owner'}, {'proposal':'6175550199'},
    {'outcome':'response_received','response_summary':'A response','reported_phone':'123'},
])
def test_invalid_contact_is_atomic(investigation, changes):
    store, north, _ = investigation
    p = contact();p.update(changes)
    with pytest.raises(ValueError):store.event(north['id'], p)
    assert store.case(north['id']) == north


def test_api_contact_conflict_and_no_automatic_verification(investigation):
    store, north, _ = investigation
    with TestClient(create_workbench(store.path, store.root)) as client:
        result = client.post(f"/api/work/{north['id']}/events", json=contact())
        assert result.status_code == 200
        assert result.json()['status'] == north['status']
        stale = client.post(f"/api/work/{north['id']}/events", json=contact())
        assert stale.status_code == 409
        assert len(store.case(north['id'])['history']) == 1


def test_retained_rehearsal_includes_incomplete_delivery_and_refuses_reuse(tmp_path):
    import subprocess
    import sys
    root = tmp_path / 'rehearsal'
    command = [sys.executable, 'scripts/rehearse_investigation.py', '--root', str(root)]
    result = subprocess.run(command, capture_output=True, text=True, check=True)
    receipt = json.loads(result.stdout)
    assert receipt['retained_observations'] == 2
    assert receipt['outreach_count'] == 2 and receipt['status'] == 'reopened'
    assert receipt['south_unchanged'] and receipt['restart_preserved']
    repeated = subprocess.run(command, capture_output=True, text=True)
    assert repeated.returncode != 0
    assert json.loads((root / 'rehearsal.json').read_text()) == receipt
