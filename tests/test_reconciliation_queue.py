"""Independent saved-queue search and scoped handoff regressions."""

import json

import pytest
from fastapi.testclient import TestClient

from provider_directory_truth_layer.intake_api import create_workbench
from provider_directory_truth_layer.intake_store import IntakeStore
from provider_directory_truth_layer.reconciliation_store import ReconciliationStore


@pytest.fixture
def saved_queue(tmp_path):
    store = IntakeStore(tmp_path / 'queue.sqlite3', tmp_path / 'artifacts')
    # Independent expected pairs: one per unique name/NPI and address. There
    # are more pairs than a normal page, and the needle group has one ready,
    # one missing-identifier and one conflicting-identifier candidate.
    names = [f'Routine Synthetic {index:02}' for index in range(24)] + [
        'Needle Ready', 'Needle Missing', 'Needle Conflict',
        'Straße Synthetic', 'Percent % Synthetic', 'Underscore Synthetic',
    ]
    receipts = []
    for source in ('clinic', 'payer'):
        rows = []
        for index, name in enumerate(names):
            npi = f'{1000000000 + index:010d}'
            if source == 'payer' and name == 'Needle Missing':
                npi = None
            elif source == 'payer' and name == 'Needle Conflict':
                npi = '1999999999'
            native_id = f'{source}-row-{index:02}'
            if source == 'payer' and name == 'Underscore Synthetic':
                native_id = 'PAYER_SPECIAL'
            rows.append({
                'record_id': native_id, 'provider_name': name, 'npi': npi,
                'address': f'{index + 1} Fiction Street STE 100',
                'city': 'Exampleton', 'state': 'MA', 'zip': '02108',
                'phone': '2125550101', 'entity_type': 'clinician',
                'location_id': f'loc-{index}',
            })
        receipts.append(store.receive(json.dumps(rows, ensure_ascii=False).encode(),
            f'{source}-synthetic.json', source=source,
            metadata={'scope': 'synthetic-queue'}))
    service = ReconciliationStore(store)
    run = service.create_run({
        'inputs': [{'receipt_id': receipt['id'], 'attempt_id': receipt['attempt_id'],
                    'entity_kind': 'clinician'} for receipt in receipts],
        'actor': 'Synthetic Reviewer', 'reason': 'Independent queue fixture',
    })
    return store, service, run


def test_search_scopes_complete_reason_facets_and_pagination(saved_queue):
    _, service, run = saved_queue
    # Searching applies to the complete run, not just currently visible rows.
    first = service.candidates(run['id'], kind='clinician', search=' routine ', limit=7)
    assert first['total'] == first['unfiltered_total'] == 24
    assert first['next_offset'] == 7
    assert first['reason_counts']['npi_equal'] == 24
    last = service.candidates(run['id'], kind='clinician', search='ROUTINE', offset=21, limit=7)
    assert last['total'] == 24 and len(last['items']) == 3 and last['next_offset'] is None
    assert first['reason_counts'] == last['reason_counts']
    assert not {row['id'] for row in first['items']} & {row['id'] for row in last['items']}

    all_needle = service.candidates(run['id'], kind='clinician', search='NEEDLE')
    assert all_needle['total'] == all_needle['unfiltered_total'] == 3
    assert all_needle['reason_counts']['npi_missing'] == 1
    assert all_needle['reason_counts']['npi_conflict'] == 1
    missing = service.candidates(run['id'], kind='clinician', eligible=False,
                                 search='needle', reason='npi_missing')
    assert missing['total'] == 1 and missing['unfiltered_total'] == 2
    assert missing['reason_counts']['npi_missing'] == missing['reason_counts']['npi_conflict'] == 1
    assert missing['items'][0]['eligible'] is False


def test_search_matches_either_side_names_identifiers_and_literal_unicode(saved_queue):
    _, service, run = saved_queue
    name = service.candidates(run['id'], kind='clinician', search='STRASSE')
    assert name['total'] == 1
    assert 'straße' in name['items'][0]['left_record']['comparison']['provider_name'] or \
           'strasse' in name['items'][0]['left_record']['comparison']['provider_name']
    by_payer = service.candidates(run['id'], kind='clinician', search='payer-row-24')
    assert by_payer['total'] == 1
    assert {by_payer['items'][0][side + '_record']['original_fields']['provider_name']
            for side in ('left', 'right')} == {'Needle Ready'}
    by_npi = service.candidates(run['id'], kind='clinician', search='1999999999')
    assert by_npi['total'] == 1 and 'npi_conflict' in by_npi['items'][0]['contradictions']
    assert service.candidates(run['id'], kind='clinician', search='%')['total'] == 1
    assert service.candidates(run['id'], kind='clinician', search='_')['total'] == 1
    assert service.candidates(run['id'], kind='clinician', search="' OR 1=1 --")['total'] == 0
    assert service.candidates(run['id'], kind='location', search='needle')['total'] == 3


@pytest.mark.parametrize('bad', ['', '  ', 'x' * 101, True, [], {}])
def test_invalid_search_is_rejected_by_both_reads(saved_queue, bad):
    _, service, run = saved_queue
    with pytest.raises(ValueError, match='(?i)search'):
        service.candidates(run['id'], search=bad)
    with pytest.raises(ValueError, match='(?i)search'):
        service.export_candidates(run['id'], search=bad)


def test_filtered_export_is_complete_scoped_and_keeps_source_evidence(saved_queue):
    _, service, run = saved_queue
    full_page = service.candidates(run['id'], kind='clinician', search='routine', limit=100)
    exported = service.export_candidates(run['id'], kind='clinician', search='routine')
    assert exported['run']['id'] == run['id']
    assert exported['scope'] == {'kind': 'clinician', 'eligible': None,
                                  'reason': None, 'search': 'routine'}
    assert exported['total'] == len(exported['candidates']) == 24
    assert [row['id'] for row in exported['candidates']] == [row['id'] for row in full_page['items']]
    assert len(exported['records']) == 48
    included = {record['clinician_ref'] for record in exported['records']}
    assert all({row['left'], row['right']} <= included for row in exported['candidates'])
    assert all(record['artifact_sha'] and record['attempt_id'] and record['locator']
               and record['original_fields'] for record in exported['records'])
    assert all('Needle' not in record['original_fields']['provider_name']
               for record in exported['records'])

    missing = service.export_candidates(run['id'], kind='clinician', eligible=False,
                                        reason='npi_missing', search='needle')
    assert missing['total'] == len(missing['candidates']) == 1
    assert len(missing['records']) == 2
    assert missing['scope'] == {'kind': 'clinician', 'eligible': False,
                                'reason': 'npi_missing', 'search': 'needle'}
    none = service.export_candidates(run['id'], search='no such provider')
    assert none['total'] == 0 and none['candidates'] == none['records'] == []


def test_api_search_and_export_match_service_and_preserve_database(saved_queue):
    store, service, run = saved_queue
    client = TestClient(create_workbench(store.path, store.root, demo=False))
    base = f"/api/reconciliation/runs/{run['id']}/candidates"
    params = {'kind': 'clinician', 'eligible': 'false', 'reason': 'npi_missing', 'search': 'needle'}
    before = service.export(run['id'])
    tables = ['receipt', 'attempt', 'comparison_run', 'comparison_candidate',
              'reviewed_identity_link', 'identity_review_decision', 'work_case', 'work_event']
    def snapshot():
        with store.db() as conn:
            return {table: [tuple(row) for row in conn.execute(f'SELECT * FROM {table} ORDER BY rowid')]
                    for table in tables}
    rows_before = snapshot()
    response = client.get(base, params=params)
    assert response.status_code == 200
    assert response.json() == service.candidates(run['id'], kind='clinician', eligible=False,
                                                  reason='npi_missing', search='needle')
    response = client.get(base + '/export', params=params)
    assert response.status_code == 200
    assert 'attachment' in response.headers['content-disposition']
    assert response.json() == service.export_candidates(run['id'], kind='clinician', eligible=False,
                                                          reason='npi_missing', search='needle')
    assert client.get(base, params={'search': ' '}).status_code == 422
    assert client.get(base + '/export', params={'search': 'x' * 101}).status_code == 422
    assert client.get('/api/reconciliation/runs/missing/candidates/export').status_code == 404
    assert snapshot() == rows_before and service.export(run['id']) == before
    reopened = ReconciliationStore(IntakeStore(store.path, store.root))
    assert reopened.export_candidates(run['id'], kind='clinician', search='routine')['total'] == 24
    assert reopened.export(run['id']) == before


def test_handoff_preserves_multi_address_grain_for_each_candidate_type(tmp_path):
    store = IntakeStore(tmp_path / 'multi.sqlite3', tmp_path / 'multi-artifacts')
    office_a = {'line1': '10 Synthetic Street', 'suite': '1', 'city': 'Exampleton',
                'state': 'MA', 'zip': '02108', 'kind': 'practice'}
    office_b = {'line1': '20 Synthetic Street', 'suite': '2', 'city': 'Exampleton',
                'state': 'MA', 'zip': '02108', 'kind': 'practice'}
    receipts = []
    for source, offices in [('clinic', [office_a, office_b]), ('payer', [office_a])]:
        row = {'record_id': source + '-id', 'provider_name': 'Multi Office Synthetic',
               'npi': '1234567890', 'entity_type': 'clinician', 'native_addresses': offices}
        receipts.append(store.receive(json.dumps([row]).encode(), source + '.json',
                                      source=source, metadata={'scope': 'multi-office'}))
    service = ReconciliationStore(store)
    run = service.create_run({'inputs': [{'receipt_id': item['id'], 'attempt_id': item['attempt_id'],
                                          'entity_kind': 'clinician'} for item in receipts],
                              'actor': 'Synthetic Reviewer', 'reason': 'Address grain'})
    clinician = service.export_candidates(run['id'], kind='clinician', search='multi office')
    location = service.export_candidates(run['id'], kind='location', search='multi office')
    assert clinician['total'] == location['total'] == 1
    assert len(clinician['records']) == 3
    assert len(location['records']) == 2
    assert {record['address_path'] for record in clinician['records']} == {
        'native_addresses[0]', 'native_addresses[1]'}
    assert {record['address_path'] for record in location['records']} == {'native_addresses[0]'}
    assert {row[side] for row in location['candidates'] for side in ('left', 'right')} == {
        record['ref'] for record in location['records']}
