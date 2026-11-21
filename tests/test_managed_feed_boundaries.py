"""Independent managed-feed approval, evidence and inbox boundary tests."""
from __future__ import annotations

import hashlib
import json
import sqlite3
from pathlib import Path

import pytest

from provider_directory_truth_layer.intake_store import Conflict, IntakeStore
from provider_directory_truth_layer.managed_feed import ManagedFeed
from provider_directory_truth_layer.onboarding_service import OnboardingService


FIXTURES = Path(__file__).parent / 'fixtures' / 'managed_feed'
FIELDS = ['record_id', 'npi', 'provider_name', 'address', 'city', 'state', 'zip', 'phone', 'location_id']
SOURCE = 'synthetic-managed-clinic'
SCOPE = {'clinic': 'synthetic-managed-clinic', 'dataset': 'weekly-full-roster'}
ACTOR = {'actor': 'Synthetic coordinator', 'reason': 'Reviewed synthetic fixture evidence'}
AT = '2026-11-30T12:00:00+00:00'


@pytest.fixture
def feed_setup(tmp_path):
    store = IntakeStore(tmp_path / 'directory.sqlite3', tmp_path / 'retained')
    onboarding = OnboardingService(store)
    receipt = store.receive((FIXTURES / 'baseline.csv').read_bytes(), 'recipe-seed.csv',
                            source=SOURCE, metadata={'scope': SCOPE})
    definition = {'version': 1, 'mapping': {field: field for field in FIELDS},
                  'required': FIELDS, 'transforms': {'phone': ['phone_us'], 'zip': ['zip_us'], 'state': ['state_us']}}
    proposal = onboarding.propose(receipt['id'], {
        **ACTOR, 'name': 'Synthetic weekly clinic', 'expected_attempt': receipt['attempt_id'], 'definition': definition})
    recipe = onboarding.approve(receipt['id'], proposal['id'], {**ACTOR, 'expected_attempt': receipt['attempt_id']})
    inbox = tmp_path / 'inbox'
    inbox.mkdir()
    service = ManagedFeed(store)
    feed = service.register({**ACTOR, 'name': 'Synthetic weekly clinic', 'source': SOURCE,
                             'scope': SCOPE, 'owner': 'Synthetic coordinator', 'inbox': str(inbox),
                             'start_date': '2026-10-26'})
    draft = service.propose_contract(feed['id'], {**ACTOR, 'definition': {
        'recipe_revision_id': recipe['id'], 'required_headers': FIELDS}})
    contract = service.approve_contract(feed['id'], draft['id'], ACTOR)
    service.configure(feed['id'], {**ACTOR, 'expected_revision': feed['revision'],
                                   'config': {'enabled': True, 'contract_id': contract['id']}})
    return store, service, feed['id'], inbox


def deliver(setup, filename='baseline.csv', delivery_id='synthetic-delivery-1', period='2026-10-26'):
    _, _, _, inbox = setup
    payload = (FIXTURES / filename).read_bytes()
    csv_name = delivery_id + '.csv'
    (inbox / csv_name).write_bytes(payload)
    manifest = {'delivery_id': delivery_id, 'period': period, 'as_of': period, 'snapshot': 'full',
                'filename': csv_name, 'sha256': hashlib.sha256(payload).hexdigest()}
    (inbox / (delivery_id + '.manifest.json')).write_text(json.dumps(manifest))
    return manifest


def candidate(setup, **kwargs):
    deliver(setup, **kwargs)
    _, service, feed_id, _ = setup
    result = service.run_once(feed_id, AT)
    assert 'error' not in result, result
    return service.version(result['version_id'])


def decision_payload(version, current=None, key='synthetic-decision-1'):
    return {**ACTOR, 'decision': 'approved', 'expected_report': version['report_hash'],
            'expected_current': current, 'idempotency_key': key}


@pytest.mark.parametrize(('filename', 'code', 'raw'), [
    ('header_drift.csv', 'headers_missing', 3), ('empty.csv', 'empty', 0),
])
def test_hard_contract_failures_are_visible_candidates_and_cannot_be_waived(feed_setup, filename, code, raw):
    store, service, feed_id, _ = feed_setup
    version = candidate(feed_setup, filename=filename)
    assert version['state'] == 'candidate'
    assert version['report']['counts']['raw'] == raw
    assert any(finding['code'] == code and finding['severity'] == 'hard' for finding in version['report']['findings'])
    with pytest.raises(ValueError, match='Only soft'):
        service.review(version['id'], {**ACTOR, 'expected_report': version['report_hash'],
                                       'code': code, 'disposition': 'acknowledged'})
    with pytest.raises(ValueError, match='Hard quality'):
        service.decide(version['id'], decision_payload(version))
    with pytest.raises(KeyError, match='No approved'):
        service.current(feed_id)
    with store.db() as conn:
        assert conn.execute('SELECT count(*) FROM feed_decision').fetchone()[0] == 0
        assert conn.execute('SELECT count(*) FROM observation').fetchone()[0] == 0


def test_rediscovery_preserves_one_delivery_job_receipt_and_candidate(feed_setup):
    store, service, feed_id, _ = feed_setup
    version = candidate(feed_setup)
    for _ in range(3):
        service.discover(feed_id, AT)
        assert service.run_once(feed_id, AT)['processed'] is None
    with store.db() as conn:
        assert conn.execute('SELECT count(*) FROM feed_delivery').fetchone()[0] == 1
        assert conn.execute('SELECT count(*) FROM feed_job').fetchone()[0] == 1
        assert conn.execute('SELECT count(*) FROM feed_version').fetchone()[0] == 1
        assert conn.execute('SELECT count(*) FROM receipt WHERE id=?', (version['manifest']['receipt_id'],)).fetchone()[0] == 1


@pytest.mark.parametrize('violation', ['path', 'symlink', 'hash', 'conflict'])
def test_bad_inbox_input_records_issue_without_losing_retained_evidence(feed_setup, violation, tmp_path):
    store, service, feed_id, inbox = feed_setup
    original = deliver(feed_setup)
    service.discover(feed_id, AT)
    retained = store.artifacts / original['sha256']
    before = retained.read_bytes()
    bad = {**original, 'delivery_id': 'synthetic-bad-input'}
    if violation == 'path':
        bad['filename'] = '../outside.csv'
        (inbox.parent / 'outside.csv').write_bytes(before)
    elif violation == 'symlink':
        outside = tmp_path / 'outside.csv'
        outside.write_bytes(before)
        (inbox / 'linked.csv').symlink_to(outside)
        bad['filename'] = 'linked.csv'
    elif violation == 'hash':
        bad['sha256'] = '0' * 64
    else:
        bad['delivery_id'] = original['delivery_id']
        bad['filename'] = 'changed.csv'
        changed = (FIXTURES / 'clean_update.csv').read_bytes()
        (inbox / 'changed.csv').write_bytes(changed)
        bad['sha256'] = hashlib.sha256(changed).hexdigest()
    (inbox / 'bad.manifest.json').write_text(json.dumps(bad))
    service.discover(feed_id, AT)
    detail = service.detail(feed_id)
    assert detail['issues']
    messages = ' '.join(issue['message'] for issue in detail['issues']).lower()
    assert ('regular csv' if violation in {'path', 'symlink'} else 'hash mismatch' if violation == 'hash' else 'conflicting content') in messages
    assert len(detail['jobs']) == 1
    assert retained.read_bytes() == before


def test_manifest_json_array_is_visible_issue_and_does_not_stop_discovery(feed_setup):
    _, service, feed_id, inbox = feed_setup
    # The array contains an allowed field name to exercise object-type validation,
    # rather than failing accidentally on an unknown-field check.
    (inbox / 'bad-array.manifest.json').write_text(json.dumps(['delivery_id']))
    deliver(feed_setup)
    service.discover(feed_id, AT)
    detail = service.detail(feed_id)
    assert len(detail['jobs']) == 1
    assert any(issue['source_ref'] == 'bad-array.manifest.json' for issue in detail['issues'])


def test_manual_intake_acceptance_cannot_bypass_dataset_version_approval(feed_setup):
    store, service, feed_id, _ = feed_setup
    version = candidate(feed_setup)
    with pytest.raises(ValueError, match='dataset-version approval'):
        store.commit(version['manifest']['receipt_id'], {**ACTOR, 'policy': 'valid_rows',
                                                        'expected_attempt': version['manifest']['attempt_id']})
    with pytest.raises(ValueError, match='explicitly approved'):
        service.export(version['id'])
    assert service.detail(feed_id)['current_version'] is None
    assert store.detail(version['manifest']['receipt_id'])['observations'] == []


def test_remapping_managed_receipt_cannot_remove_approval_boundary(feed_setup):
    store, service, feed_id, _ = feed_setup
    version = candidate(feed_setup)
    receipt_id = version['manifest']['receipt_id']
    # Public interpretation operations must not turn a managed delivery into an
    # unmanaged interpretation whose ordinary acceptance skips dataset approval.
    try:
        remapped = store.mapping(receipt_id, {'mapping': {field: field for field in FIELDS}})
    except (ValueError, Conflict):
        pass
    else:
        with pytest.raises((ValueError, Conflict), match='[Mm]anaged|approval'):
            store.commit(receipt_id, {**ACTOR, 'policy': 'valid_rows', 'expected_attempt': remapped['attempt_id']})
    assert service.detail(feed_id)['current_version'] is None
    assert store.detail(receipt_id)['observations'] == []


def test_stale_baseline_requires_new_job_before_promotion(feed_setup):
    _, service, feed_id, _ = feed_setup
    first = candidate(feed_setup)
    later = candidate(feed_setup, filename='clean_update.csv', delivery_id='synthetic-update', period='2026-11-02')
    service.decide(first['id'], decision_payload(first))
    with pytest.raises(Conflict, match='Baseline'):
        service.decide(later['id'], decision_payload(later, first['id'], 'synthetic-stale'))
    service.job_action(later['job_id'], 'reprocess', ACTOR)
    result = service.run_once(feed_id, AT)
    assert 'error' not in result, result
    refreshed = service.version(result['version_id'])
    assert refreshed['id'] != later['id']
    assert refreshed['manifest']['baseline_version'] == first['id']
    assert refreshed['report']['comparison']['changed'] == 1
    service.decide(refreshed['id'], decision_payload(refreshed, first['id'], 'synthetic-refreshed'))
    assert service.current(feed_id)['version_id'] == refreshed['id']


def test_stale_config_requires_reprocessing_and_old_inputs_remain_pinned(feed_setup):
    _, service, feed_id, _ = feed_setup
    version = candidate(feed_setup)
    feed = service.detail(feed_id)
    service.configure(feed_id, {**ACTOR, 'expected_revision': feed['revision'], 'config': {'owner': 'Second synthetic coordinator'}})
    with pytest.raises(Conflict, match='configuration changed'):
        service.decide(version['id'], decision_payload(version))
    service.job_action(version['job_id'], 'reprocess', ACTOR)
    result = service.run_once(feed_id, AT)
    assert 'error' not in result, result
    refreshed = service.version(result['version_id'])
    assert refreshed['id'] != version['id']
    assert service.version(version['id'])['report_hash'] == version['report_hash']
    service.decide(refreshed['id'], decision_payload(refreshed, key='synthetic-new-owner'))


def test_approved_export_is_immutable_across_later_promotion_and_restart(feed_setup):
    store, service, feed_id, _ = feed_setup
    first = candidate(feed_setup)
    service.decide(first['id'], decision_payload(first))
    original_export = service.export(first['id'])
    original_hash = hashlib.sha256(json.dumps(original_export, sort_keys=True).encode()).hexdigest()
    later = candidate(feed_setup, filename='clean_update.csv', delivery_id='synthetic-update', period='2026-11-02')
    assert service.current(feed_id)['version_id'] == first['id']
    with pytest.raises(ValueError):
        service.export(later['id'])
    service.decide(later['id'], decision_payload(later, first['id'], 'synthetic-promote-later'))
    reopened = ManagedFeed(IntakeStore(store.path, store.root))
    assert reopened.current(feed_id)['version_id'] == later['id']
    assert hashlib.sha256(json.dumps(reopened.export(first['id']), sort_keys=True).encode()).hexdigest() == original_hash
    assert len(original_export['records']) == 3
    assert original_export['records'][0]['normalized']['zip'] == '02108'
    with store.db() as conn:
        with pytest.raises(sqlite3.IntegrityError, match='Immutable'):
            conn.execute('UPDATE feed_version SET report=? WHERE id=?', ('{}', first['id']))


def test_older_period_cannot_replace_newer_approved_version(feed_setup):
    _, service, feed_id, _ = feed_setup
    newer = candidate(feed_setup, delivery_id='synthetic-newer', period='2026-11-02')
    service.decide(newer['id'], decision_payload(newer))
    older = candidate(feed_setup, filename='clean_update.csv', delivery_id='synthetic-older', period='2026-10-26')
    with pytest.raises(ValueError, match='Out-of-order'):
        service.decide(older['id'], decision_payload(older, newer['id'], 'synthetic-older-promotion'))
    assert service.current(feed_id)['version_id'] == newer['id']
    assert service.version(older['id'])['state'] == 'candidate'


@pytest.mark.parametrize('missing', ['actor', 'reason'])
def test_review_and_approval_require_attributed_reasons(feed_setup, missing):
    _, service, feed_id, _ = feed_setup
    version = candidate(feed_setup, filename='invalid_phone.csv')
    review_payload = {**ACTOR, 'expected_report': version['report_hash'], 'code': 'quarantine', 'disposition': 'acknowledged'}
    review_payload.pop(missing)
    with pytest.raises(ValueError, match=missing):
        service.review(version['id'], review_payload)
    approve_payload = decision_payload(version)
    approve_payload.pop(missing)
    with pytest.raises(ValueError, match=missing):
        service.decide(version['id'], approve_payload)
    assert service.detail(feed_id)['current_version'] is None


def test_schema10_upgrade_preserves_populated_originals_and_human_history(tmp_path):
    store = IntakeStore(tmp_path / 'directory.sqlite3', tmp_path / 'retained')
    payload = (FIXTURES / 'baseline.csv').read_bytes()
    receipt = store.receive(payload, 'original.csv', source='synthetic-legacy-clinic', metadata={'scope': 'preservation'})
    mapped = store.mapping(receipt['id'], {'mapping': {field: field for field in FIELDS}})
    accepted = store.commit(receipt['id'], {**ACTOR, 'policy': 'valid_rows', 'expected_attempt': mapped['attempt_id']})
    case_id = accepted['linked_cases'][0]['id']
    case = store.event(case_id, {**ACTOR, 'action': 'assign', 'owner': 'Synthetic legacy owner', 'expected_version': 0})
    # Migration 11 is additive only: remove its empty objects to obtain populated v10.
    with store.db() as conn:
        from schema_helpers import remove_assistant_schema
        remove_assistant_schema(conn)
        conn.execute('DROP TABLE fhir_acquisition_event')
        conn.execute('DROP TABLE fhir_acquisition')
        conn.execute('DELETE FROM schema_migration WHERE version=12')
        tables = [row[0] for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name LIKE 'feed%'")]
        for name in reversed(tables):
            conn.execute(f'DROP TABLE {name}')
        conn.execute('DELETE FROM schema_migration WHERE version=11')
        conn.execute('PRAGMA user_version=10')
    reopened = IntakeStore(store.path, store.root)
    assert reopened.case(case_id) == case
    assert reopened.artifacts.joinpath(accepted['artifact_sha']).read_bytes() == payload
    backup = store.path.with_name(store.path.name + '.pre-intake-v11.bak')
    assert backup.exists()
    with sqlite3.connect(backup) as old:
        assert old.execute('PRAGMA user_version').fetchone()[0] == 10
        assert old.execute('SELECT count(*) FROM observation').fetchone()[0] == 3
        assert old.execute('SELECT count(*) FROM work_event').fetchone()[0] >= 1
    with reopened.db() as conn:
        assert conn.execute('PRAGMA integrity_check').fetchone()[0] == 'ok'
        assert conn.execute('PRAGMA foreign_key_check').fetchall() == []
