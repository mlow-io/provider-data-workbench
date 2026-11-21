"""Explicit retained-interpretation reads never silently select newer evidence."""

import csv
import hashlib
import io
from pathlib import Path

from fastapi.testclient import TestClient
import pytest

from provider_directory_truth_layer.intake_api import create_workbench
from provider_directory_truth_layer.intake_store import IntakeStore


@pytest.fixture
def store(tmp_path):
    return IntakeStore(tmp_path / 'directory.sqlite3', tmp_path / 'runtime')


def payload():
    row = {'record_id': '001', 'npi': '1000000001', 'provider_name': 'Synthetic Clinic',
           'address': '10 Fiction St', 'city': 'Example', 'state': 'TN', 'zip': '01234',
           'phone': '5550100000', 'alternate_phone': '5550100009', 'location_id': 'A'}
    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=row)
    writer.writeheader()
    writer.writerow(row)
    return output.getvalue().encode()


def accept(store, receipt_id):
    return store.commit(receipt_id, {'actor': 'Synthetic operator', 'reason': 'Reviewed fixture',
                                     'policy': 'valid_rows'})


def revised(store):
    first = accept(store, store.receive(payload(), 'synthetic.csv')['id'])
    mapping = {**first['preview']['mapping'], 'phone': 'alternate_phone'}
    store.mapping(first['id'], {'mapping': mapping})
    return first, accept(store, first['id'])


def test_pinned_attempt_retains_its_preview_observations_and_case_links(store):
    first, latest = revised(store)
    pinned = store.detail(first['id'], attempt_id=first['attempt_id'])
    assert pinned['attempt_id'] == first['attempt_id']
    assert pinned['preview'] == first['preview']
    assert pinned['state'] == first['state']
    assert pinned['observations'] == first['observations']
    assert pinned['linked_cases'] == latest['linked_cases']
    assert pinned['observations'][0]['normalized']['phone'] == '5550100000'
    assert latest['observations'][0]['normalized']['phone'] == '5550100009'
    assert pinned['attempts'] == latest['attempts']
    assert pinned['latest_attempt_id'] == latest['attempt_id']
    assert pinned['is_current_attempt'] is False
    current = store.detail(first['id'], attempt_id=latest['attempt_id'])
    assert current['is_current_attempt'] is True
    legacy = store.detail(first['id'])
    assert legacy == latest
    assert 'latest_attempt_id' not in legacy
    assert 'is_current_attempt' not in legacy


def test_pinned_attempt_must_belong_to_receipt(store):
    first = store.receive(payload(), 'first.csv')
    other = store.receive(payload(), 'other.csv')
    for attempt_id in ('missing', '', other['attempt_id']):
        with pytest.raises(KeyError, match='does not belong'):
            store.detail(first['id'], attempt_id=attempt_id)


def test_unaccepted_historical_preview_does_not_borrow_later_observations(store):
    preview = store.receive(payload(), 'synthetic.csv')
    store.mapping(preview['id'], {'mapping': {**preview['preview']['mapping'], 'phone': 'alternate_phone'}})
    latest = accept(store, preview['id'])
    assert latest['observations']
    pinned = store.detail(preview['id'], attempt_id=preview['attempt_id'])
    assert pinned['state'] == 'preview_ready'
    assert pinned['preview'] == preview['preview']
    assert pinned['observations'] == []
    assert pinned['linked_cases'] == []
    assert pinned['is_current_attempt'] is False


def test_pinned_duplicate_retains_delivery_identity_and_reuses_original_evidence(store):
    first = accept(store, store.receive(payload(), 'first.csv')['id'])
    duplicate = accept(store, store.receive(payload(), 'repeat.csv')['id'])
    assert duplicate['state'] == 'duplicate_delivery'
    # A later interpretation must not replace the selected repeat's reused evidence.
    store.mapping(duplicate['id'], {'mapping': {**duplicate['preview']['mapping'], 'phone': 'alternate_phone'}})
    accept(store, duplicate['id'])
    pinned = store.detail(duplicate['id'], attempt_id=duplicate['attempt_id'])
    assert pinned['id'] == duplicate['id']
    assert pinned['attempt_id'] == duplicate['attempt_id']
    assert pinned['state'] == 'duplicate_delivery'
    assert pinned['observations'] == first['observations']
    assert {case['id'] for case in pinned['linked_cases']} == {case['id'] for case in first['linked_cases']}
    assert pinned['is_current_attempt'] is False


def test_http_pinned_reads_preserve_database_wal_artifacts_and_migration_state(tmp_path):
    db = tmp_path / 'directory.sqlite3'
    root = tmp_path / 'runtime'
    app = create_workbench(db, root)
    client = TestClient(app)
    store = IntakeStore(db, root)
    first, latest = revised(store)
    other = store.receive(payload(), 'other.csv')
    with store.db() as writer:
        # Keep the WAL open while the HTTP reader opens and closes its own connection.
        writer.execute('BEGIN')
        writer.execute('SELECT count(*) FROM receipt').fetchone()
        tracked = [db, *root.joinpath('artifacts').glob('*')]
        wal = Path(str(db) + '-wal')
        if wal.exists():
            tracked.append(wal)
        before = {path: hashlib.sha256(path.read_bytes()).hexdigest() for path in tracked}
        response = client.get(f"/api/intakes/{first['id']}", params={'attempt_id': first['attempt_id']})
        assert response.status_code == 200, response.text
        assert response.json()['attempt_id'] == first['attempt_id']
        assert response.json()['latest_attempt_id'] == latest['attempt_id']
        assert response.json()['observations'][0]['normalized']['phone'] == '5550100000'
        for attempt_id in ('missing', other['attempt_id']):
            assert client.get(f"/api/intakes/{first['id']}", params={'attempt_id': attempt_id}).status_code == 404
        assert client.get(f"/api/intakes/{first['id']}").json()['attempt_id'] == latest['attempt_id']
        assert {path: hashlib.sha256(path.read_bytes()).hexdigest() for path in tracked} == before
