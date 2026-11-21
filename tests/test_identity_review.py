"""Reviewed crosswalk boundaries: explicit, typed, immutable and retry-safe."""
from concurrent.futures import ThreadPoolExecutor
import json
import sqlite3
import uuid

import pytest
from fastapi.testclient import TestClient

from provider_directory_truth_layer.identity_review import IdentityReview
from provider_directory_truth_layer.intake_api import create_workbench
from provider_directory_truth_layer.intake_store import Conflict, IntakeStore, VERSION
from provider_directory_truth_layer.reconciliation_store import ReconciliationStore


@pytest.fixture
def scenario(tmp_path):
    store = IntakeStore(tmp_path / 'directory.sqlite3', tmp_path / 'root')
    receipts = []
    for source in ('clinic', 'payer', 'reference'):
        row = {'record_id': '001', 'npi': '1000000001', 'provider_name': 'Synthetic Clinician',
               'address': '10 Example Street Suite 004', 'city': 'Boston', 'state': 'MA',
               'zip': '02108', 'phone': '2125550101', 'entity_type': 'clinician'}
        receipts.append(store.receive(json.dumps([row]).encode(), source+'.json', source=source))
    run = ReconciliationStore(store).create_run({'inputs': [
        {'receipt_id': r['id'], 'attempt_id': r['attempt_id']} for r in receipts],
        'actor': 'Synthetic reviewer', 'reason': 'Compare retained sources'})
    return store, receipts, run


def candidate(store, run, kind='clinician', index=0):
    return ReconciliationStore(store).candidates(run['id'], kind=kind)['items'][index]


def payload(review, run, selected, action='approve', **kwargs):
    context = review.inspect(run['id'], selected['id'])
    return {'run_id': run['id'], 'candidate_id': selected['id'], 'decision': action,
            'request_id': uuid.uuid4().hex, 'expected_snapshot': context['review_snapshot'],
            'expected_revisions': {ref: link['id'] if link else None for ref, link in context['current_links'].items()},
            'expected_decision': context['latest_decision']['id'] if context['latest_decision'] else None,
            'actor': 'Synthetic reviewer', 'reason': 'Explicit evidence review', **kwargs}


def test_approve_is_explicit_typed_retry_safe_and_does_not_accept_sources(scenario):
    store, receipts, run = scenario
    review = IdentityReview(store)
    person = candidate(store, run)
    request = payload(review, run, person, new_label='Reviewed clinician')
    saved = review.decide(request)
    assert len(saved['links']) == 2
    target = saved['decision']['target_id']
    assert review.decide(request) == saved
    identity = review.identity('clinician', target)
    assert len(identity['assertions']) == 2
    assert all(a['inputs_fresh'] for a in identity['assertions'])
    assert len({a['records'][0]['source'] for a in identity['assertions']}) == 2
    assert review.inspect(run['id'], candidate(store, run, 'location')['id'])['current_links'] == {
        ref: None for ref in (candidate(store, run, 'location')['left'], candidate(store, run, 'location')['right'])}
    assert all(store.detail(r['id'])['observations'] == [] for r in receipts)
    with store.db() as conn:
        assert conn.execute('SELECT count(*) FROM clinician_identity').fetchone()[0] == 1
        assert conn.execute('SELECT count(*) FROM work_event').fetchone()[0] == 0
        for table in ('reviewed_identity_link', 'identity_review_decision', 'clinician_identity'):
            with pytest.raises(sqlite3.IntegrityError, match='Immutable'):
                conn.execute(f'DELETE FROM {table}')
    with pytest.raises(Conflict, match='different'):
        review.decide({**request, 'reason': 'Changed retry'})
    reopened = IdentityReview(IntakeStore(store.path, store.root))
    assert reopened.decide(request) == saved
    assert reopened.identity('clinician', target) == identity


def test_reject_defer_and_superseding_links_keep_history_across_runs(scenario):
    store, receipts, run = scenario
    review = IdentityReview(store)
    selected = candidate(store, run)
    rejected = review.decide(payload(review, run, selected, 'reject'))
    assert rejected['links'] == []
    second = ReconciliationStore(store).create_run({'inputs': [{k: pin[k] for k in ('receipt_id', 'attempt_id', 'entity_kind')} for pin in run['inputs']], 'actor': 'Reviewer', 'reason': 'Repeat'})
    selected2 = candidate(store, second)
    context = review.inspect(second['id'], selected2['id'])
    assert context['latest_decision']['id'] == rejected['decision']['id']
    deferred = review.decide(payload(review, second, selected2, 'defer'))
    assert deferred['decision']['previous_id'] == rejected['decision']['id']
    approved = review.decide(payload(review, second, selected2, new_label='First target'))
    old_id = approved['decision']['target_id']
    before = review.identity('clinician', old_id)
    defer_again = review.decide(payload(review, second, selected2, 'defer'))
    assert defer_again['links'] == []
    assert review.identity('clinician', old_id) == before  # Pair deferral does not revoke a crosswalk.
    superseded = review.decide(payload(review, second, selected2, new_label='Corrected explicit target'))
    assert {link['previous_id'] for link in superseded['links']} == {link['id'] for link in approved['links']}
    assert review.identity('clinician', old_id)['assertions'] == []
    assert len(review.identity('clinician', old_id)['history']) == 2
    assert len(review.inspect(run['id'], selected['id'])['history']) == 5


def test_stale_review_and_wrong_kind_targets_are_rejected_without_orphans(scenario):
    store, receipts, run = scenario
    review = IdentityReview(store)
    selected = candidate(store, run)
    stale = payload(review, run, selected, new_label='Stale target')
    first = review.decide(payload(review, run, selected, new_label='Current target'))
    with pytest.raises(Conflict, match='stale'):
        review.decide(stale)
    office = candidate(store, run, 'location')
    with pytest.raises(ValueError, match='kind'):
        review.decide(payload(review, run, office, target_id=first['decision']['target_id']))
    with store.db() as conn:
        assert conn.execute('SELECT count(*) FROM clinician_identity').fetchone()[0] == 1
        assert conn.execute('SELECT count(*) FROM practice_location').fetchone()[0] == 0
    request = payload(review, run, selected, 'reject')
    store.mapping(receipts[0]['id'], {})
    with pytest.raises(Conflict, match='stale'):
        review.decide(request)
    # A previously committed identical retry succeeds even when current source inputs changed.
    original = first['decision']
    assert any(not assertion['inputs_fresh'] for assertion in review.identity('clinician', original['target_id'])['assertions'])


def test_shared_target_requires_explicit_approval_and_location_is_independent(scenario):
    store, _, run = scenario
    review = IdentityReview(store)
    first = candidate(store, run, index=0)
    second = candidate(store, run, index=1)
    approved = review.decide(payload(review, run, first, new_label='Clinician'))
    target = approved['decision']['target_id']
    assert len(review.identity('clinician', target)['assertions']) == 2
    review.decide(payload(review, run, second, target_id=target))
    assert len(review.identity('clinician', target)['assertions']) == 3
    office = candidate(store, run, 'location')
    location = review.decide(payload(review, run, office, new_label='NORTH suite 004'))
    assert len(review.identity('location', location['decision']['target_id'])['assertions']) == 2
    assert len(review.identity('clinician', target)['assertions']) == 3


def test_concurrent_identical_approval_creates_one_decision(scenario):
    store, _, run = scenario
    review = IdentityReview(store)
    request = payload(review, run, candidate(store, run), new_label='Single target')
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(lambda _: review.decide(request), range(2)))
    assert results[0] == results[1]
    with store.db() as conn:
        assert conn.execute('SELECT count(*) FROM identity_review_decision').fetchone()[0] == 1
        assert conn.execute('SELECT count(*) FROM reviewed_identity_link').fetchone()[0] == 2


def test_upgrade_rollback_preserves_populated_comparison_run(scenario, monkeypatch):
    store, _, run = scenario
    from provider_directory_truth_layer import identity_review
    before = ReconciliationStore(store).export(run['id'])
    with store.db() as conn:
        from schema_helpers import remove_managed_schema
        remove_managed_schema(conn)
        conn.executescript('DROP TABLE follow_up_acknowledgement; DROP TABLE follow_up_association; DROP TABLE follow_up_confirmation; DROP TABLE change_proposal; DROP TABLE reconciled_field_decision; DROP TABLE reviewed_identity_link; DROP TABLE identity_review_decision; DROP TABLE clinician_identity; DELETE FROM schema_migration WHERE version>=7; PRAGMA user_version=6;')
    migration = identity_review.MIGRATION_7
    monkeypatch.setattr(identity_review, 'MIGRATION_7', migration+'\nINVALID SQL;')
    with pytest.raises(sqlite3.OperationalError):
        IntakeStore(store.path, store.root)
    with sqlite3.connect(store.path) as conn:
        assert conn.execute('PRAGMA user_version').fetchone()[0] == 6
        assert conn.execute('PRAGMA integrity_check').fetchone()[0] == 'ok'
    monkeypatch.setattr(identity_review, 'MIGRATION_7', migration)
    restored = IntakeStore(store.path, store.root)
    assert ReconciliationStore(restored).export(run['id']) == before
    with sqlite3.connect(store.path.with_name(store.path.name+'.pre-intake-v7.bak')) as conn:
        assert conn.execute('PRAGMA user_version').fetchone()[0] == 6
    with restored.db() as conn:
        assert conn.execute('PRAGMA user_version').fetchone()[0] == VERSION
        assert conn.execute('PRAGMA foreign_key_check').fetchall() == []


def test_review_api_validation_and_history(scenario):
    store, _, run = scenario
    review = IdentityReview(store)
    selected = candidate(store, run)
    client = TestClient(create_workbench(store.path, store.root))
    path = f"/api/reconciliation/runs/{run['id']}/candidates/{selected['id']}/review"
    assert client.get(path).json()['latest_decision'] is None
    request = payload(review, run, selected, new_label='API target')
    result = client.post('/api/reconciliation/links', json=request)
    assert result.status_code == 200
    target = result.json()['decision']['target_id']
    assert client.get(f'/api/reconciliation/identities/clinician/{target}').status_code == 200
    assert client.get(path).json()['latest_decision']['decision'] == 'approve'
    assert client.post('/api/reconciliation/links', json={**request, 'decision': 'merge'}).status_code == 422
    assert client.get('/api/reconciliation/identities/organization/unknown').status_code == 422
    assert client.get('/api/reconciliation/identities/clinician/unknown').status_code == 404
    assert client.get(path.replace(selected['id'], 'missing')).status_code == 404


def test_review_pages_and_typed_target_search_do_not_hide_saved_history(scenario):
    store, _, run = scenario
    review = IdentityReview(store)
    selected = candidate(store, run)
    approved = review.decide(payload(review, run, selected, new_label='Literal % clinician'))
    review.decide(payload(review, run, selected, 'defer'))
    context = review.inspect(run['id'], selected['id'], limit=1)
    assert len(context['history']) == 1 and context['history_total'] == 2
    assert context['history_next_offset'] == 1
    assert review.inspect(run['id'], selected['id'], offset=1, limit=1)['history'][0]['decision'] == 'approve'
    target = approved['decision']['target_id']
    assert review.targets('clinician', '%')['items'][0]['id'] == target
    assert review.targets('location')['items'] == []
    assert review.targets('clinician', target)['total'] == 1
    page = review.identity('clinician', target, limit=1)
    assert len(page['assertions']) == 1 and page['total'] == 2 and page['next_offset'] == 1
    assert review.identity('clinician', target, offset=1, limit=1)['assertions'][0] != page['assertions'][0]
    with pytest.raises(ValueError):
        review.inspect(run['id'], selected['id'], limit=0)


def test_changed_rule_or_baseline_requires_new_review_and_bad_types_are_rejected(scenario, monkeypatch):
    store, receipts, run = scenario
    review = IdentityReview(store)
    selected = candidate(store, run)
    request = payload(review, run, selected, new_label='Review target')
    approved = review.decide(request)
    # A later accepted delivery in the same source scope invalidates further decisions.
    data = [{'record_id': '002', 'npi': '1000000001', 'provider_name': 'Synthetic Clinician',
             'address': '10 Example St', 'city': 'Boston', 'state': 'MA', 'zip': '02108', 'phone': '2125550199'}]
    later = store.receive(json.dumps(data).encode(), 'changed.json', source='clinic')
    store.commit(later['id'], {'actor': 'Reviewer', 'reason': 'New source baseline', 'policy': 'valid_rows'})
    assert not review.inspect(run['id'], selected['id'])['inputs_fresh']
    assert review.decide(request) == approved
    with pytest.raises(Conflict):
        review.decide({**request, 'request_id': uuid.uuid4().hex})
    from provider_directory_truth_layer import identity_review
    monkeypatch.setattr(identity_review, 'RULE_VERSION', 'future-rule')
    assert not review.inspect(run['id'], selected['id'])['inputs_fresh']
    for field in ('actor', 'reason', 'request_id'):
        with pytest.raises(ValueError, match='string'):
            review.decide({**request, field: ['not', 'a', 'string']})


@pytest.mark.parametrize('kind,source_kind', [('clinician', 'organization'), ('clinician', 'unknown'), ('location', 'unknown')])
def test_typed_approval_cannot_convert_organizations_unknown_people_or_unknown_addresses(tmp_path, kind, source_kind):
    store = IntakeStore(tmp_path / 'typed.sqlite3', tmp_path / 'root')
    receipts = []
    for index in range(2):
        row = {'record_id': '001', 'npi': '1000000001', 'provider_name': 'Synthetic Entity',
               'entity_type': source_kind if kind == 'clinician' and index else 'clinician',
               'address': '10 Example St', 'city': 'Boston', 'state': 'MA', 'zip': '02108', 'phone': '2125550101'}
        if kind == 'location':
            row['native_addresses'] = [{'line1': row['address'], 'city': row['city'], 'state': row['state'],
                                        'zip': row['zip'], 'kind': source_kind if index else 'practice'}]
        receipts.append(store.receive(json.dumps([row]).encode(), f'source{index}.json', source=f'source{index}'))
    run = ReconciliationStore(store).create_run({'inputs': [{'receipt_id': r['id'], 'attempt_id': r['attempt_id']} for r in receipts],
                                                'actor': 'Reviewer', 'reason': 'Typed evidence'})
    selected = candidate(store, run, kind)
    review = IdentityReview(store)
    context = review.inspect(run['id'], selected['id'])
    assert not context['approval_allowed'] and context['approval_blockers']
    with pytest.raises(ValueError, match='requires explicit'):
        review.decide(payload(review, run, selected, new_label='Invalid implicit conversion'))
    # Rejection remains available without creating an incorrectly typed identity.
    assert review.decide(payload(review, run, selected, 'reject'))['links'] == []
    with store.db() as conn:
        assert conn.execute('SELECT count(*) FROM clinician_identity').fetchone()[0] == 0
        assert conn.execute('SELECT count(*) FROM practice_location').fetchone()[0] == 0
        assert conn.execute('SELECT count(*) FROM reviewed_identity_link').fetchone()[0] == 0


def test_rejected_selected_attempt_invalidates_review_without_rewriting_history(scenario):
    store, receipts, run = scenario
    review = IdentityReview(store)
    selected = candidate(store, run)
    request = payload(review, run, selected, new_label='Should not be created')
    receipt = receipts[0]
    store.commit(receipt['id'], {'actor': 'Reviewer', 'reason': 'Reject delivery',
                                 'policy': 'reject', 'expected_attempt': receipt['attempt_id']})
    assert not review.inspect(run['id'], selected['id'])['inputs_fresh']
    with pytest.raises(Conflict, match='stale'):
        review.decide(request)
    with store.db() as conn:
        assert conn.execute('SELECT count(*) FROM clinician_identity').fetchone()[0] == 0


def test_same_type_conflicting_identifiers_remain_explicitly_reviewable(scenario):
    store, receipts, run = scenario
    detail = store.detail(receipts[0]['id'])
    original = detail['preview']['rows'][0]['original']
    conflicting = store.receive(json.dumps([{**original, 'npi': '1000000002'}]).encode(), 'conflicting.json', source='conflicting')
    comparison = ReconciliationStore(store).create_run({'inputs': [
        {'receipt_id': receipts[0]['id'], 'attempt_id': receipts[0]['attempt_id']},
        {'receipt_id': conflicting['id'], 'attempt_id': conflicting['attempt_id']}],
        'actor': 'Reviewer', 'reason': 'Review conflicting identifiers'})
    selected = candidate(store, comparison)
    assert not selected['eligible'] and 'npi_conflict' in selected['contradictions']
    review = IdentityReview(store)
    assert review.inspect(comparison['id'], selected['id'])['approval_allowed']
    saved = review.decide(payload(review, comparison, selected, new_label='Explicit reviewed identity'))
    assert len(saved['links']) == 2
    assert store.detail(conflicting['id'])['preview']['rows'][0]['original']['npi'] == '1000000002'
