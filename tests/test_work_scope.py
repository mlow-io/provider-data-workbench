"""Dataset scope is part of operational work identity, without rewriting history."""
import json

import pytest

from provider_directory_truth_layer.intake_store import IntakeStore, digest
from test_intake_store import csv_bytes, provider


def accept(store, scope, **changes):
    receipt = store.receive(csv_bytes([provider(**changes)]), 'synthetic.csv', source='synthetic-shared-source', metadata={'scope': scope})
    store.commit(receipt['id'], {'actor': 'Synthetic reviewer', 'reason': 'Reviewed source scope', 'policy': 'valid_rows', 'expected_attempt': receipt['attempt_id']})
    return receipt


def cases(store):
    with store.db() as conn:
        return [dict(row) for row in conn.execute('SELECT * FROM work_case ORDER BY created_at,id')]


def linked_receipts(store, case_id):
    with store.db() as conn:
        return {row[0] for row in conn.execute('SELECT a.receipt_id FROM work_evidence w JOIN observation o ON o.id=w.observation_id JOIN attempt a ON a.id=o.attempt_id WHERE w.case_id=?', (case_id,))}


def seed_legacy_identity(store, case):
    """Reproduce a pre-fix case key over an otherwise real accepted fixture."""
    evidence = json.loads(case['evidence'])
    normalized = evidence['normalized']
    stable = [evidence['source'], evidence['provider_id'], evidence['location_id'], normalized.get('listing_id') or normalized['record_id']]
    legacy = digest([stable, case['kind'], case['field_name']])
    with store.db() as conn:
        conn.execute('UPDATE work_case SET identity_key=? WHERE id=?', (legacy, case['id']))
    return legacy


@pytest.mark.parametrize('correction', [False, True])
def test_scope_separates_cases_and_same_scope_attaches_original(tmp_path, correction):
    store = IntakeStore(tmp_path/'directory.sqlite3', tmp_path/'retained')
    extra = {'reference_phone': '5550109999'} if correction else {}
    scope_a = {'organization': 'synthetic-A', 'dataset': 'weekly'}
    scope_b = {'organization': 'synthetic-B', 'dataset': 'weekly'}
    first = accept(store, scope_a, **extra)
    second = accept(store, scope_b, **extra)
    before = cases(store)
    assert len(before) == 2
    assert len({case['identity_key'] for case in before}) == 2
    first_case = next(case for case in before if json.loads(case['evidence'])['receipt_id'] == first['id'])
    other_case = next(case for case in before if case['id'] != first_case['id'])
    # Different insertion order is the same canonical JSON dataset scope.
    repeated = accept(store, {'dataset': 'weekly', 'organization': 'synthetic-A'}, phone='5550100001', **extra)
    assert len(cases(store)) == 2
    assert linked_receipts(store, first_case['id']) == {first['id'], repeated['id']}
    assert linked_receipts(store, other_case['id']) == {second['id']}


@pytest.mark.parametrize('scope', [None, {'organization': 'synthetic-A', 'dataset': 'weekly'}])
@pytest.mark.parametrize('issue_disappears', [False, True])
def test_matching_legacy_case_is_reused_without_identity_rewrite(tmp_path, scope, issue_disappears):
    store = IntakeStore(tmp_path/'directory.sqlite3', tmp_path/'retained')
    first = accept(store, scope, reference_phone='5550109999')
    original = cases(store)[0]
    legacy = seed_legacy_identity(store, original)
    if scope is None:
        assert original['identity_key'] == legacy
    # Both the attachment-only path and a continuing finding reuse this case.
    later = accept(store, scope, phone='5550109999' if issue_disappears else '5550100001', reference_phone='5550109999')
    retained = cases(store)
    assert len(retained) == 1
    assert retained[0]['identity_key'] == legacy
    assert retained[0]['id'] == original['id']
    assert retained[0]['evidence'] == original['evidence']
    assert linked_receipts(store, original['id']) == {first['id'], later['id']}


def test_foreign_legacy_case_does_not_capture_scoped_or_null_scope_work(tmp_path):
    store = IntakeStore(tmp_path/'directory.sqlite3', tmp_path/'retained')
    first = accept(store, {'organization': 'synthetic-A'}, reference_phone='5550109999')
    original = cases(store)[0]
    legacy = seed_legacy_identity(store, original)
    scoped = accept(store, {'organization': 'synthetic-B'}, reference_phone='5550109999')
    unscoped = accept(store, None, reference_phone='5550109999')
    unscoped_later = accept(store, None, phone='5550100001', reference_phone='5550109999')
    all_cases = cases(store)
    assert len(all_cases) == 3
    assert len({case['identity_key'] for case in all_cases}) == 3
    assert linked_receipts(store, original['id']) == {first['id']}
    assert next(case for case in all_cases if case['id'] == original['id'])['identity_key'] == legacy
    other = {json.loads(case['evidence'])['receipt_id']: case for case in all_cases if case['id'] != original['id']}
    assert linked_receipts(store, other[scoped['id']]['id']) == {scoped['id']}
    assert linked_receipts(store, other[unscoped['id']]['id']) == {unscoped['id'], unscoped_later['id']}
