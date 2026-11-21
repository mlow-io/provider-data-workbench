"""Evidence-reason review filters read immutable candidates without changing matching."""

import hashlib
import json

import pytest
from fastapi.testclient import TestClient

from provider_directory_truth_layer.comparison import RULE_VERSION
from provider_directory_truth_layer.intake_api import create_workbench
from provider_directory_truth_layer.intake_store import IntakeStore
from provider_directory_truth_layer.reconciliation_store import ReconciliationStore


def row(label, npi, street):
    return {
        'record_id': label, 'npi': npi, 'provider_name': label + ' Synthetic',
        'address': f'{street} Fiction Street STE 100', 'city': 'Exampleton',
        'state': 'MA', 'zip': '02108', 'phone': '2125550101',
        'location_id': label.upper(), 'entity_type': 'clinician',
    }


@pytest.fixture
def review_run(tmp_path):
    store = IntakeStore(tmp_path / 'directory.sqlite3', tmp_path / 'runtime')
    # Truth is authored here: one missing identifier, one contradiction, one
    # complete pair. Distinct names/offices prevent unintended cross pairs.
    clinic = [row('Alex', '1000000001', 10), row('Blair', '1000000002', 20),
              row('Casey', '1000000003', 30)]
    payer = [row('Alex', None, 10), row('Blair', '1000000099', 20),
             row('Casey', '1000000003', 30)]
    receipts = [store.receive(json.dumps(rows).encode(), 'synthetic.json',
                              source=source, metadata={'scope': 'triage-fixture'})
                for source, rows in [('clinic', clinic), ('payer', payer)]]
    service = ReconciliationStore(store)
    run = service.create_run({
        'inputs': [{'receipt_id': receipt['id'], 'attempt_id': receipt['attempt_id'],
                    'entity_kind': 'clinician'} for receipt in receipts],
        'actor': 'Synthetic Reviewer', 'reason': 'Independent evidence-gap fixture',
    })
    return store, service, run


def names(page):
    return {candidate['left_record']['original_fields']['provider_name']
            for candidate in page['items']}


def test_reason_filters_separate_missing_conflicting_and_ready_pairs(review_run):
    _, service, run = review_run
    missing = service.candidates(run['id'], kind='clinician', reason='npi_missing')
    conflict = service.candidates(run['id'], kind='clinician', reason='npi_conflict')
    ready = service.candidates(run['id'], kind='clinician', eligible=True)
    assert names(missing) == {'Alex Synthetic'}
    assert names(conflict) == {'Blair Synthetic'}
    assert names(ready) == {'Casey Synthetic'}
    assert missing['total'] == conflict['total'] == ready['total'] == 1
    assert missing['unfiltered_total'] == conflict['unfiltered_total'] == 3
    assert ready['unfiltered_total'] == 1
    assert not missing['items'][0]['eligible']
    assert not conflict['items'][0]['eligible']
    assert run['rule_version'] == RULE_VERSION
    assert service.candidates(run['id'], kind='clinician')['reason_counts'] == {
        'entity_kind_clinician': 3, 'provider_name_equal': 3,
        'npi_equal': 1, 'npi_conflict': 1, 'npi_missing': 1,
    }


def test_reason_counts_cover_all_candidates_before_paging_and_reason_filter(review_run):
    _, service, run = review_run
    # Existing positional offset/limit callers remain supported.
    first = service.candidates(run['id'], 'clinician', None, 0, 1,
                               reason='provider_name_equal')
    second = service.candidates(run['id'], 'clinician', None, 1, 1,
                                reason='provider_name_equal')
    third = service.candidates(run['id'], 'clinician', None, 2, 1,
                               reason='provider_name_equal')
    assert [page['next_offset'] for page in [first, second, third]] == [1, 2, None]
    assert [page['total'] for page in [first, second, third]] == [3, 3, 3]
    assert len({page['items'][0]['id'] for page in [first, second, third]}) == 3
    assert first['reason_counts'] == second['reason_counts'] == third['reason_counts']
    assert first['reason_counts']['provider_name_equal'] == 3
    assert first['reason_counts']['npi_missing'] == 1
    missing = service.candidates(run['id'], kind='clinician', reason='npi_missing', limit=1)
    assert missing['reason_counts'] == first['reason_counts']
    assert missing['total'] == 1 and missing['unfiltered_total'] == 3
    beyond = service.candidates(run['id'], kind='clinician', reason='npi_missing', offset=1)
    assert beyond['items'] == [] and beyond['next_offset'] is None
    assert beyond['total'] == 1 and beyond['unfiltered_total'] == 3


def test_kind_and_eligibility_scope_the_counts_before_reason_filter(review_run):
    _, service, run = review_run
    unresolved = service.candidates(run['id'], kind='clinician', eligible=False)
    assert unresolved['total'] == unresolved['unfiltered_total'] == 2
    assert unresolved['reason_counts'] == {
        'entity_kind_clinician': 2, 'provider_name_equal': 2,
        'npi_conflict': 1, 'npi_missing': 1,
    }
    locations = service.candidates(run['id'], kind='location', reason='suite_equal')
    assert locations['total'] == locations['unfiltered_total'] == 3
    assert locations['reason_counts']['suite_equal'] == 3
    assert 'npi_missing' not in locations['reason_counts']
    no_locations = service.candidates(run['id'], kind='location', eligible=False)
    assert no_locations['total'] == no_locations['unfiltered_total'] == 0
    assert no_locations['reason_counts'] == {}


def test_a_reason_present_in_multiple_arrays_does_not_duplicate_a_pair(review_run):
    store, service, run = review_run
    # A fixture-owned historical payload repeats one code. This is not a new
    # matcher rule and does not modify an existing immutable candidate.
    exported = service.export(run['id'])
    original = next(candidate for candidate in exported['candidates']
                    if candidate['kind'] == 'clinician')
    payload = {**original, 'id': 'fixture-overlap',
               'agreements': ['repeated_code', 'repeated_code'],
               'contradictions': ['repeated_code'], 'missing': ['repeated_code']}
    with store.db() as conn:
        conn.execute('''INSERT INTO comparison_run
            SELECT ?,inputs,rule_version,records,baseline_snapshot,metrics,actor,reason,created_at
            FROM comparison_run WHERE id=?''', ('fixture-overlap-run', run['id']))
        conn.execute('INSERT INTO comparison_candidate VALUES (?,?,?,?,?,?)',
                     (payload['id'], 'fixture-overlap-run', 'clinician',
                      payload['rank'], int(payload['eligible']), json.dumps(payload)))
    page = service.candidates('fixture-overlap-run', reason='repeated_code')
    assert page['reason_counts'] == {'repeated_code': 1}
    assert page['total'] == page['unfiltered_total'] == len(page['items']) == 1
    assert page['next_offset'] is None


@pytest.mark.parametrize('reason', ['', 'NPI_missing', 'npi missing', 'npi_missing\n',
                                    "npi_missing' OR 1=1 --", 'x' * 81, True, {}])
def test_malformed_reason_codes_are_rejected_by_service(review_run, reason):
    _, service, run = review_run
    with pytest.raises(ValueError, match='reason'):
        service.candidates(run['id'], reason=reason)


def test_unknown_valid_reason_returns_empty_without_losing_available_counts(review_run):
    _, service, run = review_run
    page = service.candidates(run['id'], kind='clinician', reason='not_in_this_run')
    assert page['items'] == [] and page['total'] == 0 and page['next_offset'] is None
    assert page['unfiltered_total'] == 3
    assert page['reason_counts']['npi_missing'] == 1
    assert service.candidates(run['id'], reason='x' * 80)['total'] == 0
    with pytest.raises(KeyError):
        service.candidates('unknown-run', reason='npi_missing')


def test_http_filter_validates_and_pages_the_same_saved_candidates(review_run):
    store, service, run = review_run
    client = TestClient(create_workbench(store.path, store.root, demo=False))
    url = f"/api/reconciliation/runs/{run['id']}/candidates"
    params = {'kind': 'clinician', 'eligible': 'false', 'reason': 'npi_missing', 'limit': 1}
    response = client.get(url, params=params)
    assert response.status_code == 200
    page = response.json()
    assert page == service.candidates(run['id'], 'clinician', False, 0, 1, reason='npi_missing')
    assert page['total'] == 1 and page['unfiltered_total'] == 2
    assert page['reason_counts']['npi_conflict'] == 1
    assert client.get(url, params={'reason': "' OR 1=1 --"}).status_code == 422
    assert client.get(url, params={'reason': ''}).status_code == 422
    assert client.get('/api/reconciliation/runs/missing/candidates',
                      params={'reason': 'npi_missing'}).status_code == 404


def test_triage_reads_preserve_database_wal_artifacts_and_reopen(review_run):
    store, service, run = review_run
    client = TestClient(create_workbench(store.path, store.root, demo=False))
    expected_export = service.export(run['id'])
    expected_page = service.candidates(run['id'], kind='clinician', reason='npi_missing')
    tables = ['receipt', 'attempt', 'observation', 'comparison_run',
              'comparison_candidate', 'work_case', 'work_event', 'reviewed_identity_link']

    def snapshot():
        with store.db() as conn:
            return {table: [tuple(row) for row in conn.execute(f'SELECT * FROM {table} ORDER BY rowid')]
                    for table in tables}

    def hashes(paths):
        return {str(path): hashlib.sha256(path.read_bytes()).hexdigest() for path in paths}

    before_rows = snapshot()
    with store.db() as reader:
        reader.execute('BEGIN')
        reader.execute('SELECT count(*) FROM receipt').fetchone()
        paths = [store.path, store.path.with_name(store.path.name + '-wal'),
                 *store.artifacts.iterdir()]
        paths = [path for path in paths if path.is_file()]
        before_bytes = hashes(paths)
        for reason in ['npi_missing', 'npi_conflict', 'provider_name_equal', 'not_in_this_run']:
            service.candidates(run['id'], kind='clinician', reason=reason, limit=1)
            response = client.get(f"/api/reconciliation/runs/{run['id']}/candidates",
                                  params={'kind': 'clinician', 'reason': reason, 'limit': 1})
            assert response.status_code == 200
        assert hashes(paths) == before_bytes
    assert snapshot() == before_rows
    restarted = ReconciliationStore(IntakeStore(store.path, store.root))
    assert restarted.candidates(run['id'], kind='clinician', reason='npi_missing') == expected_page
    assert restarted.export(run['id']) == expected_export
    assert snapshot() == before_rows
    assert not before_rows['observation'] and not before_rows['work_case']
    assert not before_rows['work_event'] and not before_rows['reviewed_identity_link']
