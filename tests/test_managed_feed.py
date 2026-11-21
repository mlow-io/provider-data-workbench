"""Managed source-to-consumer behavior and durable job boundaries in owned roots."""
import hashlib
import json
import sqlite3
from pathlib import Path

import pytest

from provider_directory_truth_layer.intake_store import IntakeStore, Conflict, now, packed
from provider_directory_truth_layer.managed_feed import ManagedFeed
from provider_directory_truth_layer.onboarding_service import OnboardingService

FIXTURES = Path(__file__).parent / 'fixtures' / 'managed_feed'
ATTR = {'actor': 'Synthetic coordinator', 'reason': 'Reviewed synthetic source evidence'}
FIELDS = ['record_id', 'npi', 'provider_name', 'address', 'city', 'state', 'zip', 'phone', 'location_id']


def setup_feed(tmp_path):
    root = tmp_path / 'retained'
    store = IntakeStore(root / 'directory.sqlite3', root)
    service = ManagedFeed(store)
    scope = 'weekly-full-roster'
    receipt = store.receive((FIXTURES / 'baseline.csv').read_bytes(), 'recipe-sample.csv', source='synthetic-managed-clinic', metadata={'scope': scope})
    onboarding = OnboardingService(store)
    proposal = onboarding.propose(receipt['id'], {'name': 'Synthetic clinic CSV', 'definition': {'version': 1, 'mapping': dict(zip(FIELDS, FIELDS)), 'required': FIELDS, 'transforms': {'phone': ['phone_us']}}, 'expected_attempt': receipt['attempt_id'], **ATTR})
    recipe = onboarding.approve(receipt['id'], proposal['id'], {'expected_attempt': receipt['attempt_id'], **ATTR})
    inbox = tmp_path / 'inbox'
    inbox.mkdir()
    feed = service.register({'name': 'Synthetic weekly clinic', 'source': 'synthetic-managed-clinic', 'scope': scope, 'owner': 'Synthetic coordinator', 'inbox': str(inbox), 'start_date': '2026-10-05', **ATTR})
    contract = service.propose_contract(feed['id'], {'definition': {'recipe_revision_id': recipe['id'], 'required_headers': FIELDS}, **ATTR})
    approved = service.approve_contract(feed['id'], contract['id'], ATTR)
    feed = service.configure(feed['id'], {'expected_revision': feed['revision'], 'config': {'contract_id': approved['id'], 'enabled': True}, **ATTR})
    return store, service, feed, inbox


def deliver(inbox, filename='baseline.csv', delivery_id='week-1', period='2026-10-05'):
    data = (FIXTURES / filename).read_bytes()
    target = inbox / (delivery_id + '.csv')
    target.write_bytes(data)
    manifest = {'delivery_id': delivery_id, 'period': period, 'as_of': period, 'snapshot': 'full', 'filename': target.name, 'sha256': hashlib.sha256(data).hexdigest()}
    (inbox / (delivery_id + '.manifest.json')).write_text(json.dumps(manifest))
    return manifest


def approve(service, version_id):
    version = service.version(version_id)
    payload = {'decision': 'approved', 'expected_report': version['report_hash'], 'expected_current': version['current_version'], 'idempotency_key': version_id, **ATTR}
    return service.decide(version_id, payload), payload


def test_real_recurring_source_to_approved_consumer(tmp_path):
    store, service, feed, inbox = setup_feed(tmp_path)
    deliver(inbox)
    result = service.run_once(feed['id'], '2026-10-06T10:00:00+00:00')
    assert 'error' not in result, result
    first = service.version(result['version_id'])
    assert first['report']['counts'] == {'raw': 3, 'valid': 3, 'quarantined': 0, 'unique': 3}
    assert first['state'] == 'candidate'
    with pytest.raises(KeyError):
        service.current(feed['id'])
    with pytest.raises(ValueError, match='approved'):
        service.export(first['id'])
    decided, payload = approve(service, first['id'])
    assert decided['state'] == 'approved'
    assert service.decide(first['id'], payload)['id'] == first['id']
    original = packed(service.export(first['id']))
    assert len(json.loads(original)['records']) == 3
    deliver(inbox, 'row_drop.csv', 'week-2', '2026-10-12')
    result = service.run_once(feed['id'], '2026-10-13T10:00:00+00:00')
    assert 'error' not in result, result
    second = service.version(result['version_id'])
    assert second['report']['comparison']['missing_from_this_delivery'] == 2
    assert service.current(feed['id'])['version_id'] == first['id']
    with pytest.raises(ValueError, match='hold'):
        approve(service, second['id'])
    for finding in second['report']['findings']:
        if finding['severity'] == 'hold':
            service.review(second['id'], {'expected_report': second['report_hash'], 'code': finding['code'], 'disposition': 'acknowledged', **ATTR})
    approve(service, second['id'])
    assert service.current(feed['id'])['version_id'] == second['id']
    assert packed(service.export(first['id'])) == original
    assert service.run_once(feed['id'], '2026-10-13T10:00:00+00:00') == {'processed': None}
    reopened = ManagedFeed(IntakeStore(store.path, store.root))
    assert packed(reopened.export(first['id'])) == original
    with store.db() as conn:
        assert conn.execute('PRAGMA integrity_check').fetchone()[0] == 'ok'
        assert not conn.execute('PRAGMA foreign_key_check').fetchall()
        assert conn.execute('SELECT COUNT(*) FROM feed_delivery').fetchone()[0] == 2
        assert conn.execute('SELECT COUNT(*) FROM feed_decision').fetchone()[0] == 2


@pytest.mark.parametrize('scenario', ['clean_update.csv', 'row_drop.csv', 'invalid_phone.csv', 'duplicate_key.csv', 'empty.csv', 'reordered_repeat.csv', 'header_drift.csv'])
def test_independent_frozen_quality_counts(tmp_path, scenario):
    _, service, feed, inbox = setup_feed(tmp_path)
    deliver(inbox)
    first = service.run_once(feed['id'], '2026-10-06T10:00:00+00:00')
    approve(service, first['version_id'])
    deliver(inbox, scenario, 'next', '2026-10-12')
    result = service.run_once(feed['id'], '2026-10-13T10:00:00+00:00')
    assert 'error' not in result, result
    report = service.version(result['version_id'])['report']
    expected = json.loads((FIXTURES / 'expected.json').read_text())['cases'][scenario]
    for field in ('raw', 'valid', 'quarantined'):
        assert report['counts'][field] == expected[field]
    if scenario != 'header_drift.csv':
        for field in ('new', 'changed', 'unchanged', 'blocked_invalid', 'unresolved'):
            assert report['comparison'][field] == expected[field]
        assert report['comparison']['missing_from_this_delivery'] == expected['missing']
    else:
        assert report['comparison'] is None


def test_claim_expiry_fencing_and_live_startup(tmp_path):
    store, service, feed, inbox = setup_feed(tmp_path)
    deliver(inbox)
    service.discover(feed['id'], '2026-10-06T10:00:00+00:00')
    job = service.claim(feed['id'])
    assert job and service.claim(feed['id']) is None
    with store.db() as conn:
        # Managed attempt is registered before parsing and must survive a second API startup.
        receipt_id = 'recovery-receipt'
        delivery = conn.execute('SELECT * FROM feed_delivery').fetchone()
        conn.execute('INSERT INTO receipt VALUES (?,?,?,?,?,?,?,?,?)', (receipt_id, 'recovery.csv', feed['source'], 'synthetic', now(), delivery['artifact_sha'], 'flat', None, packed({'scope': feed['scope']})))
        conn.execute('INSERT INTO attempt VALUES (?,?,?,?,?,?,?,?,?)', ('managed-live-attempt', receipt_id, '{}', 'f', 'processing', '{}', now(), None, None))
        conn.execute('UPDATE feed_job SET receipt_id=?,attempt_id=? WHERE id=?', (receipt_id, 'managed-live-attempt', job['id']))
    IntakeStore(store.path, store.root)
    with store.db() as conn:
        assert conn.execute("SELECT state FROM attempt WHERE id='managed-live-attempt'").fetchone()[0] == 'processing'
        conn.execute("UPDATE feed_job SET lease_until='2000-01-01T00:00:00+00:00' WHERE id=?", (job['id'],))
    successor = service.claim(feed['id'])
    assert successor['token'] > job['token']
    with store.db() as conn, pytest.raises(Conflict, match='expired'):
        service._owned(conn, job)
    service.job_action(job['id'], 'cancel', ATTR)
    with store.db() as conn, pytest.raises(Conflict):
        service._owned(conn, successor)


def test_restored_backup_recovers_abandoned_job_without_duplicate_delivery(tmp_path):
    from provider_directory_truth_layer.storage_backup import backup, restore
    store, service, feed, inbox = setup_feed(tmp_path)
    deliver(inbox)
    baseline = service.run_once(feed['id'], '2026-10-06T10:00:00+00:00')
    approve(service, baseline['version_id'])
    original_export = packed(service.export(baseline['version_id']))
    deliver(inbox, 'clean_update.csv', 'week-2', '2026-10-12')
    service.discover(feed['id'], '2026-10-13T10:00:00+00:00')
    abandoned = service.claim(feed['id'])
    assert abandoned is not None
    with store.db() as conn:
        conn.execute("UPDATE feed_job SET lease_until='2000-01-01T00:00:00+00:00' WHERE id=?", (abandoned['id'],))
    backup(store.root, tmp_path / 'archive')
    restore(tmp_path / 'archive', tmp_path / 'recovered')
    recovered_store = IntakeStore(tmp_path / 'recovered' / 'directory.sqlite3', tmp_path / 'recovered')
    recovered = ManagedFeed(recovered_store)
    # The feed still refers to the explicitly synthetic test inbox; no external inbox is used.
    assert packed(recovered.export(baseline['version_id'])) == original_export
    result = recovered.run_once(feed['id'], '2026-10-13T10:00:00+00:00')
    assert result['processed'] == abandoned['id'] and 'version_id' in result
    assert recovered.current(feed['id'])['version_id'] == baseline['version_id']
    assert recovered.run_once(feed['id'], '2026-10-13T10:00:00+00:00') == {'processed': None}
    with recovered_store.db() as conn:
        job = conn.execute('SELECT * FROM feed_job WHERE id=?', (abandoned['id'],)).fetchone()
        assert job['token'] > abandoned['token'] and job['state'] == 'succeeded'
        assert conn.execute('SELECT count(*) FROM feed_delivery').fetchone()[0] == 2
        assert conn.execute('SELECT count(*) FROM feed_version').fetchone()[0] == 2
        assert conn.execute('SELECT count(*) FROM feed_decision').fetchone()[0] == 1
    assert packed(service.export(baseline['version_id'])) == original_export
    with store.db() as conn:
        assert conn.execute('SELECT state FROM feed_job WHERE id=?', (abandoned['id'],)).fetchone()[0] == 'running'


def test_approval_is_one_atomic_transaction(tmp_path, monkeypatch):
    store, service, feed, inbox = setup_feed(tmp_path)
    deliver(inbox)
    result = service.run_once(feed['id'], '2026-10-06T10:00:00+00:00')
    original = store.commit_in_transaction
    def fault(conn, receipt_id, payload, **kwargs):
        original(conn, receipt_id, payload, **kwargs)
        raise RuntimeError('simulated crash before promotion')
    monkeypatch.setattr(store, 'commit_in_transaction', fault)
    with pytest.raises(RuntimeError):
        approve(service, result['version_id'])
    with store.db() as conn:
        assert conn.execute('SELECT COUNT(*) FROM observation').fetchone()[0] == 0
        assert conn.execute('SELECT COUNT(*) FROM feed_decision').fetchone()[0] == 0
        assert conn.execute('SELECT current_version FROM feed').fetchone()[0] is None
    monkeypatch.setattr(store, 'commit_in_transaction', original)
    approve(service, result['version_id'])
    assert service.version(result['version_id'])['state'] == 'approved'


def test_late_windows_retry_and_worker_mutex(tmp_path, monkeypatch):
    store, service, feed, inbox = setup_feed(tmp_path)
    service.discover(feed['id'], '2026-10-20T12:00:00+00:00')
    assert [w['status'] for w in service.detail(feed['id'])['windows']] == ['late', 'late', 'late']
    deliver(inbox)
    original = service._process
    monkeypatch.setattr(service, '_process', lambda job: (_ for _ in ()).throw(OSError('transient read failure')))
    service.run_once(feed['id'])
    job = service.detail(feed['id'])['jobs'][0]
    assert job['state'] == 'retry_wait' and job['next_retry']
    with store.db() as conn:
        conn.execute("UPDATE feed_job SET next_retry='2000-01-01T00:00:00+00:00' WHERE id=?", (job['id'],))
    monkeypatch.setattr(service, '_process', original)
    with service.worker_lock() as acquired:
        assert acquired
        assert ManagedFeed(store).run_once(feed['id']) == {'busy': True}
    assert 'version_id' in service.run_once(feed['id'])


def test_conflicting_delivery_after_candidate_blocks_approval(tmp_path):
    _, service, feed, inbox = setup_feed(tmp_path)
    deliver(inbox)
    first = service.run_once(feed['id'])
    deliver(inbox, 'clean_update.csv')
    service.discover(feed['id'])
    with pytest.raises(ValueError, match='Conflicting delivery ID'):
        approve(service, first['version_id'])
    deliver(inbox, 'clean_update.csv', 'corrected-week-1')
    corrected = service.run_once(feed['id'])
    assert approve(service, corrected['version_id'])[0]['state'] == 'approved'


@pytest.mark.parametrize('stage', ['receipt', 'normalization', 'publication', 'approval'])
def test_real_process_death_reuses_stages_and_atomic_approval(tmp_path, stage):
    import os
    import subprocess
    import sys
    store, service, feed, inbox = setup_feed(tmp_path)
    deliver(inbox)
    # A child exits without finally/context cleanup; SQLite/OS must recover it.
    code = '''
import os,sys
from pathlib import Path
from provider_directory_truth_layer.intake_store import IntakeStore
from provider_directory_truth_layer.managed_feed import ManagedFeed
root=Path(sys.argv[1]); feed_id=sys.argv[2]; stage=sys.argv[3]
store=IntakeStore.open_existing(root/'directory.sqlite3',root); service=ManagedFeed(store)
if stage in ('receipt','normalization'):
    original=store.mapping
    def die(*args,**kwargs):
        if stage=='normalization': original(*args,**kwargs)
        os._exit(17)
    store.mapping=die
elif stage=='publication':
    original=service._event
    def die(conn,job_id,kind,token,payload):
        original(conn,job_id,kind,token,payload)
        if kind=='succeeded': os._exit(17)
    service._event=die
result=service.run_once(feed_id)
if stage=='approval':
    original=store.commit_in_transaction
    def die(*args,**kwargs):
        original(*args,**kwargs)
        os._exit(17)
    store.commit_in_transaction=die
    version=service.version(result['version_id'])
    service.decide(version['id'],{'decision':'approved','expected_report':version['report_hash'],'expected_current':None,'idempotency_key':'crash-approval','actor':'Synthetic reviewer','reason':'Crash rehearsal'})
'''
    result = subprocess.run([sys.executable, '-c', code, str(store.root), feed['id'], stage], env={**os.environ, 'PYTHONPATH': str(Path('src').resolve())}, capture_output=True, text=True, timeout=20)
    assert result.returncode == 17, result.stderr
    with store.db() as conn:
        job = dict(conn.execute('SELECT * FROM feed_job').fetchone())
        assert conn.execute('SELECT COUNT(*) FROM observation').fetchone()[0] == 0
        assert conn.execute('SELECT COUNT(*) FROM feed_decision').fetchone()[0] == 0
        if stage != 'approval':
            conn.execute("UPDATE feed_job SET lease_until='2000-01-01T00:00:00+00:00' WHERE id=?", (job['id'],))
    reopened = ManagedFeed(IntakeStore(store.path, store.root))
    if stage == 'approval':
        version_id = reopened.detail(feed['id'])['versions'][0]['id']
    else:
        recovered = reopened.run_once(feed['id'])
        assert 'version_id' in recovered, recovered
        version_id = recovered['version_id']
    approve(reopened, version_id)
    with store.db() as conn:
        recovered_job = conn.execute('SELECT * FROM feed_job').fetchone()
        assert recovered_job['receipt_id'] == job['receipt_id']
        assert recovered_job['attempt_id'] == job['attempt_id']
        assert conn.execute('SELECT COUNT(*) FROM feed_delivery').fetchone()[0] == 1
        assert conn.execute('SELECT COUNT(*) FROM feed_version').fetchone()[0] == 1
        assert conn.execute('SELECT COUNT(*) FROM feed_decision').fetchone()[0] == 1
        assert conn.execute('SELECT COUNT(*) FROM observation').fetchone()[0] == 3
        assert not conn.execute('PRAGMA foreign_key_check').fetchall()


def test_identical_bytes_new_period_preserves_delivery_and_canonical_baseline(tmp_path):
    store, service, feed, inbox = setup_feed(tmp_path)
    deliver(inbox)
    first = service.run_once(feed['id'])
    approve(service, first['version_id'])
    deliver(inbox, delivery_id='repeat', period='2026-10-12')
    second = service.run_once(feed['id'])
    approve(service, second['version_id'])
    with store.db() as conn:
        assert conn.execute('SELECT COUNT(*) FROM observation').fetchone()[0] == 3
        assert conn.execute("SELECT COUNT(*) FROM attempt WHERE state='duplicate_delivery'").fetchone()[0] == 1
        assert conn.execute('SELECT COUNT(*) FROM feed_delivery').fetchone()[0] == 2
    deliver(inbox, 'clean_update.csv', 'after-repeat', '2026-10-19')
    third = service.run_once(feed['id'])
    report = service.version(third['version_id'])['report']
    assert report['comparison']['changed'] == 1
    assert report['comparison']['unchanged'] == 2
    approve(service, third['version_id'])


def test_schema11_failure_rolls_back_and_backup_is_reopenable(tmp_path, monkeypatch):
    from provider_directory_truth_layer import managed_feed
    from schema_helpers import remove_managed_schema
    store = IntakeStore(tmp_path/'directory.sqlite3', tmp_path/'retained')
    receipt = store.receive((FIXTURES/'baseline.csv').read_bytes(), 'original.csv')
    with store.db() as conn:
        remove_managed_schema(conn)
        conn.execute('PRAGMA user_version=10')
        before = {table: [tuple(r) for r in conn.execute('SELECT * FROM '+table)] for table in ('artifact','receipt','attempt')}
    monkeypatch.setattr(managed_feed, 'MIGRATION_11', 'CREATE TABLE partial_feed(id TEXT); INSERT INTO absent_table VALUES (1);')
    with pytest.raises(sqlite3.OperationalError, match='absent_table'):
        IntakeStore(store.path, store.root)
    with store.db() as conn:
        assert conn.execute('PRAGMA user_version').fetchone()[0] == 10
        assert not conn.execute("SELECT 1 FROM sqlite_master WHERE name='partial_feed'").fetchone()
        for table, rows in before.items():
            assert [tuple(r) for r in conn.execute('SELECT * FROM '+table)] == rows
    with sqlite3.connect(store.path.with_name(store.path.name+'.pre-intake-v11.bak')) as backup:
        assert backup.execute('PRAGMA integrity_check').fetchone()[0] == 'ok'
        assert backup.execute('SELECT id FROM receipt').fetchone()[0] == receipt['id']


def test_local_recipe_designation_is_preserved_in_managed_source_and_export(tmp_path):
    store, service, feed, inbox = setup_feed(tmp_path)
    # Build a separate reviewed local recipe/source without labeling its data synthetic.
    receipt = store.receive((FIXTURES/'baseline.csv').read_bytes(), 'local.csv', source='local-clinic', designation='local', metadata={'scope':'local-weekly'})
    onboarding=OnboardingService(store)
    definition={'version':1,'mapping':dict(zip(FIELDS,FIELDS)),'required':FIELDS,'transforms':{'phone':['phone_us']}}
    proposed=onboarding.propose(receipt['id'],{'name':'Local CSV recipe','definition':definition,'expected_attempt':receipt['attempt_id'],**ATTR})
    recipe=onboarding.approve(receipt['id'],proposed['id'],{'expected_attempt':receipt['attempt_id'],**ATTR})
    local=service.register({'name':'Local clinic','source':'local-clinic','scope':'local-weekly','inbox':str(inbox),'owner':'Local owner','start_date':'2026-10-05',**ATTR})
    contract=service.propose_contract(local['id'],{'definition':{'recipe_revision_id':recipe['id'],'required_headers':FIELDS},**ATTR})
    approved=service.approve_contract(local['id'],contract['id'],ATTR)
    service.configure(local['id'],{'expected_revision':local['revision'],'config':{'enabled':True,'contract_id':approved['id']},**ATTR})
    deliver(inbox)
    result=service.run_once(local['id'])
    version=service.version(result['version_id'])
    assert store.detail(version['manifest']['receipt_id'])['designation']=='local'
    approve(service,version['id'])
    assert service.export(version['id'])['manifest']['designation']=='local'
    assert service.export(version['id'])['manifest']['notice'].startswith('Local source assertions')


def test_repeated_worker_loss_exhausts_automatic_execution_budget(tmp_path):
    store, service, feed, inbox = setup_feed(tmp_path)
    deliver(inbox)
    service.discover(feed['id'])
    for _ in range(3):
        job=service.claim(feed['id'])
        assert job is not None
        with store.db() as conn:
            conn.execute("UPDATE feed_job SET lease_until='2000-01-01T00:00:00+00:00' WHERE id=?",(job['id'],))
    assert service.claim(feed['id']) is None
    assert service.detail(feed['id'])['jobs'][0]['state']=='failed'
    service.job_action(job['id'],'retry',ATTR)
    assert service.claim(feed['id'])['execution_count']==1


def test_contract_change_does_not_implicitly_replay_retained_deliveries(tmp_path):
    _, service, feed, inbox = setup_feed(tmp_path)
    deliver(inbox)
    first=service.run_once(feed['id'])
    approve(service,first['version_id'])
    feed=service.detail(feed['id'])
    definition={key:feed['contracts'][0]['definition'][key] for key in ('recipe_revision_id','required_headers','encoding','delimiter','row_change_fraction')}
    proposal=service.propose_contract(feed['id'],{'definition':definition,**ATTR})
    approved=service.approve_contract(feed['id'],proposal['id'],ATTR)
    service.configure(feed['id'],{'expected_revision':feed['revision'],'config':{'contract_id':approved['id']},**ATTR})
    assert service.run_once(feed['id'])=={'processed':None}
    assert len(service.detail(feed['id'])['jobs'])==1
    service.job_action(service.detail(feed['id'])['jobs'][0]['id'],'reprocess',ATTR)
    assert len(service.detail(feed['id'])['jobs'])==2
    assert 'version_id' in service.run_once(feed['id'])
