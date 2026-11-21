"""One local managed CSV feed: immutable evidence, claimed jobs and explicit approval."""
from __future__ import annotations

import csv
import fcntl
import hashlib
import io
import json
import sqlite3
import stat
import threading
from contextlib import contextmanager
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

from .intake_store import Conflict, MAX_BYTES, digest, now, packed, uid

MIGRATION_11 = '''
CREATE TABLE feed (id TEXT PRIMARY KEY, name TEXT NOT NULL, source TEXT NOT NULL,
 scope TEXT NOT NULL, revision INTEGER NOT NULL, config TEXT NOT NULL, current_version TEXT,
 UNIQUE(source,scope));
CREATE TABLE feed_config (feed_id TEXT REFERENCES feed(id), revision INTEGER,
 config TEXT NOT NULL, actor TEXT NOT NULL, reason TEXT NOT NULL, created_at TEXT NOT NULL,
 PRIMARY KEY(feed_id,revision));
CREATE TABLE feed_contract (id TEXT PRIMARY KEY, feed_id TEXT REFERENCES feed(id),
 parent_id TEXT REFERENCES feed_contract(id), definition TEXT NOT NULL, state TEXT NOT NULL,
 actor TEXT NOT NULL, reason TEXT NOT NULL, created_at TEXT NOT NULL);
CREATE UNIQUE INDEX feed_contract_approval ON feed_contract(parent_id) WHERE state='approved';
CREATE TABLE feed_delivery (id TEXT PRIMARY KEY, feed_id TEXT REFERENCES feed(id),
 source_id TEXT NOT NULL, manifest TEXT NOT NULL, artifact_sha TEXT NOT NULL REFERENCES artifact(sha),
 created_at TEXT NOT NULL, UNIQUE(feed_id,source_id));
CREATE TABLE feed_job (id TEXT PRIMARY KEY, feed_id TEXT REFERENCES feed(id),
 delivery_id TEXT NOT NULL REFERENCES feed_delivery(id), contract_id TEXT NOT NULL REFERENCES feed_contract(id),
 config_revision INTEGER NOT NULL, baseline_version TEXT, baseline_attempt_id TEXT,
 receipt_id TEXT REFERENCES receipt(id), attempt_id TEXT, state TEXT NOT NULL,
 token INTEGER NOT NULL DEFAULT 0, lease_until TEXT, execution_count INTEGER NOT NULL DEFAULT 0,
 next_retry TEXT, error TEXT, created_at TEXT NOT NULL,
 UNIQUE(delivery_id,contract_id,baseline_version,config_revision));
CREATE UNIQUE INDEX feed_job_first_baseline ON feed_job(delivery_id,contract_id,config_revision) WHERE baseline_version IS NULL;
CREATE TABLE feed_job_event (id INTEGER PRIMARY KEY, job_id TEXT REFERENCES feed_job(id),
 kind TEXT NOT NULL, token INTEGER NOT NULL, payload TEXT NOT NULL, created_at TEXT NOT NULL);
CREATE TABLE feed_version (id TEXT PRIMARY KEY, feed_id TEXT REFERENCES feed(id),
 job_id TEXT NOT NULL UNIQUE REFERENCES feed_job(id), manifest TEXT NOT NULL, report TEXT NOT NULL,
 report_hash TEXT NOT NULL, rows TEXT NOT NULL, created_at TEXT NOT NULL);
CREATE TABLE feed_decision (version_id TEXT PRIMARY KEY REFERENCES feed_version(id),
 decision TEXT NOT NULL, actor TEXT NOT NULL, reason TEXT NOT NULL, request_hash TEXT NOT NULL,
 idempotency_key TEXT NOT NULL UNIQUE, created_at TEXT NOT NULL);
CREATE TABLE feed_exception (id INTEGER PRIMARY KEY, version_id TEXT REFERENCES feed_version(id),
 code TEXT NOT NULL, disposition TEXT NOT NULL, actor TEXT NOT NULL, reason TEXT NOT NULL,
 created_at TEXT NOT NULL);
CREATE TABLE feed_window (feed_id TEXT REFERENCES feed(id), period TEXT NOT NULL,
 status TEXT NOT NULL, PRIMARY KEY(feed_id,period));
CREATE TABLE feed_window_event (id INTEGER PRIMARY KEY, feed_id TEXT REFERENCES feed(id), period TEXT NOT NULL, status TEXT NOT NULL, observed_at TEXT NOT NULL);
CREATE TABLE feed_issue (id TEXT PRIMARY KEY, feed_id TEXT REFERENCES feed(id),
 source_ref TEXT NOT NULL, message TEXT NOT NULL, created_at TEXT NOT NULL,
 UNIQUE(feed_id,source_ref,message));
'''
for _table in ('feed_config', 'feed_contract', 'feed_delivery', 'feed_job_event', 'feed_version', 'feed_decision', 'feed_exception', 'feed_issue', 'feed_window_event'):
    for _operation in ('UPDATE', 'DELETE'):
        MIGRATION_11 += f"CREATE TRIGGER {_table}_no_{_operation.lower()} BEFORE {_operation} ON {_table} BEGIN SELECT RAISE(ABORT,'Immutable managed feed evidence'); END;\n"


def required(payload, field):
    value = payload.get(field)
    if not isinstance(value, str) or not value.strip() or len(value) > 4096:
        raise ValueError(f'{field} is required (at most 4096 characters)')
    return value.strip()


def instant(value=None):
    result = datetime.fromisoformat(value) if value else datetime.now(timezone.utc)
    if result.tzinfo is None:
        raise ValueError('Use a timezone-aware timestamp')
    return result.astimezone(timezone.utc)


def decode(row):
    result = dict(row)
    for key in ('config', 'definition', 'manifest', 'report', 'rows', 'payload'):
        if key in result:
            result[key] = json.loads(result[key])
    return result


class ManagedFeed:
    def __init__(self, store):
        self.store = store

    @staticmethod
    def _feed(conn, feed_id):
        row = conn.execute('SELECT * FROM feed WHERE id=?', (feed_id,)).fetchone()
        if row is None:
            raise KeyError('Feed not found')
        return decode(row)

    def recipes(self):
        with self.store.db() as conn:
            items = [decode(row) for row in conn.execute("SELECT * FROM recipe_revision WHERE state='approved' ORDER BY created_at,id")]
            for item in items:
                item['scope'] = json.loads(item['scope'])
            return {'items': items}

    def register(self, payload):
        name, source, owner, actor, reason = (required(payload, key) for key in ('name', 'source', 'owner', 'actor', 'reason'))
        scope = payload.get('scope')
        if not isinstance(scope, (str, dict)) or not scope:
            raise ValueError('Declare a nonempty source dataset scope')
        inbox = Path(required(payload, 'inbox')).expanduser()
        if not inbox.is_absolute() or inbox.is_symlink() or not inbox.is_dir():
            raise ValueError('Choose an existing absolute local inbox directory, not a symlink')
        start = payload.get('start_date', date.today().isoformat())
        date.fromisoformat(start)
        config = {'inbox': str(inbox.resolve()), 'owner': owner, 'enabled': False, 'contract_id': None,
                  'start_date': start, 'weekday': 0, 'hour_utc': 9, 'grace_hours': 24}
        feed_id = uid()
        with self.store.db() as conn:
            conn.execute('BEGIN IMMEDIATE')
            conn.execute('INSERT INTO feed VALUES (?,?,?,?,?,?,NULL)', (feed_id, name, source, packed(scope), 1, packed(config)))
            conn.execute('INSERT INTO feed_config VALUES (?,?,?,?,?,?)', (feed_id, 1, packed(config), actor, reason, now()))
        return self.detail(feed_id)

    def detail(self, feed_id):
        with self.store.db() as conn:
            feed = self._feed(conn, feed_id)
            feed['scope'] = json.loads(feed['scope'])
            for key, table in (('contracts', 'feed_contract'), ('jobs', 'feed_job'), ('windows', 'feed_window'), ('issues', 'feed_issue'), ('configuration_history', 'feed_config'), ('window_history', 'feed_window_event')):
                feed[key] = [decode(row) for row in conn.execute(f'SELECT * FROM {table} WHERE feed_id=? ORDER BY rowid', (feed_id,))]
            for job in feed['jobs']:
                delivery = conn.execute('SELECT manifest FROM feed_delivery WHERE id=?', (job['delivery_id'],)).fetchone()
                job['kind'] = json.loads(delivery['manifest']).get('kind', 'source_delivery')
            feed['versions'] = [dict(row) for row in conn.execute('''SELECT v.id,v.created_at,
                COALESCE(d.decision,'candidate') state,j.delivery_id,x.manifest
                FROM feed_version v JOIN feed_job j ON j.id=v.job_id JOIN feed_delivery x ON x.id=j.delivery_id
                LEFT JOIN feed_decision d ON d.version_id=v.id WHERE v.feed_id=? ORDER BY v.created_at,v.id''', (feed_id,))]
            for version in feed['versions']:
                delivery = json.loads(version.pop('manifest'))
                version['period'] = delivery['period']
                version['kind'] = delivery.get('kind', 'source_delivery')
        return feed

    def list(self):
        with self.store.db() as conn:
            ids = [row[0] for row in conn.execute('SELECT id FROM feed ORDER BY rowid')]
        return {'items': [self.detail(feed_id) for feed_id in ids]}

    def propose_contract(self, feed_id, payload):
        actor, reason = required(payload, 'actor'), required(payload, 'reason')
        definition = payload.get('definition')
        allowed = {'recipe_revision_id', 'required_headers', 'encoding', 'delimiter', 'row_change_fraction'}
        if not isinstance(definition, dict) or set(definition) - allowed:
            raise ValueError('Use the supported CSV contract fields')
        definition = {'encoding': 'utf-8-sig', 'delimiter': ',', 'row_change_fraction': .2, **definition}
        if definition['encoding'] not in {'utf-8-sig', 'utf-8', 'cp1252'} or definition['delimiter'] not in {',', ';', '\t', '|'}:
            raise ValueError('Unsupported CSV encoding/delimiter')
        threshold = definition['row_change_fraction']
        if type(threshold) not in {float, int} or not 0 <= threshold <= 1:
            raise ValueError('row_change_fraction must be between 0 and 1')
        headers = definition.get('required_headers')
        if not isinstance(headers, list) or not headers or len(headers) > 64 or any(not isinstance(h, str) or not h.strip() for h in headers) or len(set(headers)) != len(headers):
            raise ValueError('Declare unique required_headers')
        with self.store.db() as conn:
            feed = self._feed(conn, feed_id)
            recipe = conn.execute("SELECT * FROM recipe_revision WHERE id=? AND state='approved'", (definition.get('recipe_revision_id'),)).fetchone()
            if recipe is None or (recipe['source'], recipe['scope'], recipe['profile']) != (feed['source'], feed['scope'], 'flat'):
                raise ValueError('Choose an approved recipe in this source/profile/dataset scope')
            mapping = json.loads(recipe['definition'])['mapping']
            if not {'record_id', 'location_id'} <= set(mapping) or not set(mapping.values()) <= set(headers):
                raise ValueError('Contract headers must cover recipe and native record/location keys')
            designation = conn.execute('SELECT designation FROM receipt WHERE id=?', (recipe['receipt_id'],)).fetchone()[0]
            definition.update(designation=designation, output_schema_version=1, policy_version=1, snapshot='full', native_key=['record_id', 'location_id'], field_types='text', null_semantics='retain original blank/absent; quarantine missing required values')
            contract_id = uid()
            conn.execute('INSERT INTO feed_contract VALUES (?,?,NULL,?,?,?,?,?)', (contract_id, feed_id, packed(definition), 'proposed', actor, reason, now()))
        return {'id': contract_id, 'state': 'proposed', 'definition': definition}

    def approve_contract(self, feed_id, contract_id, payload):
        actor, reason = required(payload, 'actor'), required(payload, 'reason')
        with self.store.db() as conn:
            conn.execute('BEGIN IMMEDIATE')
            row = conn.execute("SELECT * FROM feed_contract WHERE id=? AND feed_id=? AND state='proposed'", (contract_id, feed_id)).fetchone()
            if row is None:
                raise ValueError('Select a proposed contract')
            prior = conn.execute('SELECT * FROM feed_contract WHERE parent_id=?', (contract_id,)).fetchone()
            if prior:
                return decode(prior)
            approved_id = uid()
            conn.execute('INSERT INTO feed_contract VALUES (?,?,?,?,?,?,?,?)', (approved_id, feed_id, contract_id, row['definition'], 'approved', actor, reason, now()))
        return {'id': approved_id, 'state': 'approved', 'definition': json.loads(row['definition'])}

    def configure(self, feed_id, payload):
        actor, reason = required(payload, 'actor'), required(payload, 'reason')
        changes = payload.get('config', {})
        if not isinstance(changes, dict) or set(changes) - {'enabled', 'contract_id', 'owner', 'inbox', 'start_date'}:
            raise ValueError('Unsupported feed configuration')
        with self.store.db() as conn:
            conn.execute('BEGIN IMMEDIATE')
            feed = self._feed(conn, feed_id)
            if payload.get('expected_revision') != feed['revision']:
                raise Conflict('Feed configuration changed; reload before saving')
            config = {**feed['config'], **changes}
            if type(config['enabled']) is not bool or not str(config['owner']).strip():
                raise ValueError('Use enabled boolean and an owner')
            inbox = Path(config['inbox'])
            if not inbox.is_absolute() or inbox.is_symlink() or not inbox.is_dir():
                raise ValueError('Choose an existing absolute inbox directory')
            config['inbox'] = str(inbox.resolve())
            date.fromisoformat(config['start_date'])
            if config['contract_id'] is not None:
                row = conn.execute("SELECT id FROM feed_contract WHERE id=? AND feed_id=? AND state='approved'", (config['contract_id'], feed_id)).fetchone()
                if row is None:
                    raise ValueError('Choose an approved feed contract')
            if config['enabled'] and not config['contract_id']:
                raise ValueError('Approve/select a contract before enabling')
            revision = feed['revision'] + 1
            conn.execute('INSERT INTO feed_config VALUES (?,?,?,?,?,?)', (feed_id, revision, packed(config), actor, reason, now()))
            conn.execute('UPDATE feed SET config=?,revision=? WHERE id=?', (packed(config), revision, feed_id))
        return self.detail(feed_id)

    def _issue(self, feed_id, source_ref, message):
        with self.store.db() as conn:
            conn.execute('INSERT OR IGNORE INTO feed_issue VALUES (?,?,?,?,?)', (uid(), feed_id, source_ref, message, now()))

    def discover(self, feed_id, at=None):
        timestamp = instant(at)
        feed = self.detail(feed_id)
        if not feed['config']['enabled']:
            return
        inbox = Path(feed['config']['inbox'])
        for path in sorted(inbox.glob('*.manifest.json')):
            try:
                if path.is_symlink() or not stat.S_ISREG(path.stat().st_mode) or path.stat().st_size > 65536:
                    raise ValueError('Manifest must be a regular file of at most 64 KiB')
                manifest = json.loads(path.read_text())
                if not isinstance(manifest, dict):
                    raise ValueError('Delivery manifest must be a JSON object')
                if set(manifest) - {'delivery_id', 'period', 'as_of', 'snapshot', 'filename', 'sha256', 'supersedes'}:
                    raise ValueError('Unknown delivery manifest fields')
                for field in ('delivery_id', 'period', 'as_of', 'filename', 'sha256'):
                    required(manifest, field)
                period = date.fromisoformat(manifest['period'])
                date.fromisoformat(manifest['as_of'])
                if period.weekday() != 0 or period.isoformat() < feed['config']['start_date'] or period > timestamp.date():
                    raise ValueError('Delivery period must be a due Monday on/after feed start')
                if manifest.get('snapshot') != 'full':
                    raise ValueError('Only declared full snapshots are supported')
                filename = manifest['filename']
                target = inbox / filename
                if Path(filename).name != filename or not filename.endswith('.csv') or target.is_symlink() or not target.is_file() or not stat.S_ISREG(target.stat().st_mode):
                    raise ValueError('Select a regular CSV directly inside the inbox')
                if target.stat().st_size > MAX_BYTES:
                    raise ValueError('Artifact limit is 10 MiB')
                data = target.read_bytes()
                sha = hashlib.sha256(data).hexdigest()
                if sha != manifest['sha256']:
                    raise ValueError('Delivery hash mismatch')
                self._retain_delivery(feed, manifest, data, sha)
            except (ValueError, OSError, TypeError, KeyError) as exc:
                self._issue(feed_id, ('delivery:' + manifest['delivery_id']) if isinstance(locals().get('manifest'), dict) and str(exc).startswith('Conflicting content') else path.name, str(exc))
        self._windows(feed_id, timestamp)

    def _retain_delivery(self, feed, manifest, data, sha):
        # retain() fsyncs content-addressed bytes. Register delivery and job together.
        self.store.retain(data)
        with self.store.db() as conn:
            conn.execute('BEGIN IMMEDIATE')
            current = self._feed(conn, feed['id'])
            if current['revision'] != feed['revision']:
                raise Conflict('Feed changed during discovery; retry')
            prior = conn.execute('SELECT * FROM feed_delivery WHERE feed_id=? AND source_id=?', (feed['id'], manifest['delivery_id'])).fetchone()
            if prior and (prior['artifact_sha'] != sha or json.loads(prior['manifest']) != manifest):
                raise ValueError('Conflicting content for existing delivery ID; use a new corrected delivery ID')
            delivery_id = prior['id'] if prior else uid()
            if not prior:
                conn.execute('INSERT OR IGNORE INTO artifact VALUES (?,?,?)', (sha, len(data), sha))
                conn.execute('INSERT INTO feed_delivery VALUES (?,?,?,?,?,?)', (delivery_id, feed['id'], manifest['delivery_id'], packed(manifest), sha, now()))
            baseline = current['current_version']
            # Rediscovery does not rerun an already successful candidate after promotion.
            existing = conn.execute('SELECT id FROM feed_job WHERE delivery_id=?', (delivery_id,)).fetchone()
            if existing:
                return
            baseline_attempt = None
            if baseline:
                baseline_attempt = json.loads(conn.execute('SELECT manifest FROM feed_version WHERE id=?', (baseline,)).fetchone()[0])['attempt_id']
                prior_attempt = conn.execute('SELECT state,preview FROM attempt WHERE id=?', (baseline_attempt,)).fetchone()
                if prior_attempt['state'] == 'duplicate_delivery':
                    baseline_attempt = json.loads(prior_attempt['preview'])['reuses_attempt']
            job_id = uid()
            conn.execute('''INSERT INTO feed_job (id,feed_id,delivery_id,contract_id,config_revision,baseline_version,baseline_attempt_id,state,created_at)
                VALUES (?,?,?,?,?,?,?,'queued',?)''', (job_id, feed['id'], delivery_id, feed['config']['contract_id'], feed['revision'], baseline, baseline_attempt, now()))
            self._event(conn, job_id, 'queued', 0, {'delivery_id': delivery_id})

    def _windows(self, feed_id, timestamp):
        with self.store.db() as conn:
            feed = self._feed(conn, feed_id)
            start = date.fromisoformat(feed['config']['start_date'])
            start += timedelta(days=(0 - start.weekday()) % 7)
            delivered = {json.loads(r[0])['period'] for r in conn.execute('SELECT manifest FROM feed_delivery WHERE feed_id=?', (feed_id,))}
            while start <= timestamp.date():
                due = datetime.combine(start, datetime.min.time(), tzinfo=timezone.utc) + timedelta(hours=9)
                if due <= timestamp:
                    status = 'received' if start.isoformat() in delivered else 'late' if timestamp > due + timedelta(hours=24) else 'awaiting'
                    prior = conn.execute('SELECT status FROM feed_window WHERE feed_id=? AND period=?', (feed_id, start.isoformat())).fetchone()
                    if not prior or prior['status'] != status:
                        conn.execute('INSERT INTO feed_window_event(feed_id,period,status,observed_at) VALUES (?,?,?,?)', (feed_id, start.isoformat(), status, timestamp.isoformat()))
                    conn.execute('INSERT INTO feed_window VALUES (?,?,?) ON CONFLICT(feed_id,period) DO UPDATE SET status=excluded.status', (feed_id, start.isoformat(), status))
                start += timedelta(days=7)

    @staticmethod
    def _event(conn, job_id, kind, token, payload):
        conn.execute('INSERT INTO feed_job_event(job_id,kind,token,payload,created_at) VALUES (?,?,?,?,?)', (job_id, kind, token, packed(payload), now()))

    @contextmanager
    def worker_lock(self):
        # One execution lane across HTTP ticks and CLI processes. Leases remain durable;
        # the OS lock prevents abandoned work overlapping a successor's intake stages.
        path = self.store.root / 'feed-worker.lock'
        with path.open('a') as lock:
            try:
                fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError:
                yield False
                return
            try:
                yield True
            finally:
                fcntl.flock(lock, fcntl.LOCK_UN)

    def claim(self, feed_id=None):
        with self.store.db() as conn:
            conn.execute('BEGIN IMMEDIATE')
            timestamp = now()
            row = conn.execute('''SELECT * FROM feed_job WHERE (? IS NULL OR feed_id=?) AND
                (state='queued' OR (state='retry_wait' AND next_retry<=?) OR (state='running' AND lease_until<?))
                ORDER BY created_at,id LIMIT 1''', (feed_id, feed_id, timestamp, timestamp)).fetchone()
            if row is None:
                return None
            job = dict(row)
            if job['execution_count'] >= 3:
                conn.execute("UPDATE feed_job SET state='failed',lease_until=NULL,error=? WHERE id=?", ('Automatic execution limit reached; review before manual retry', job['id']))
                self._event(conn, job['id'], 'failed', job['token'], {'error': 'Execution limit reached after interruption'})
                return None
            token = job['token'] + 1
            lease = (instant() + timedelta(seconds=30)).isoformat()
            conn.execute("UPDATE feed_job SET state='running',token=?,lease_until=?,execution_count=execution_count+1,error=NULL WHERE id=?", (token, lease, job['id']))
            self._event(conn, job['id'], 'claimed', token, {'previous_state': job['state']})
            return dict(conn.execute('SELECT * FROM feed_job WHERE id=?', (job['id'],)).fetchone())

    def _owned(self, conn, job):
        current = conn.execute('SELECT * FROM feed_job WHERE id=?', (job['id'],)).fetchone()
        if current['state'] != 'running' or current['token'] != job['token'] or current['lease_until'] < now():
            raise Conflict('Job claim expired or cancelled; result cannot publish')
        return current

    def _heartbeat(self, job, stop):
        while not stop.wait(5):
            with self.store.db() as conn:
                conn.execute("UPDATE feed_job SET lease_until=? WHERE id=? AND token=? AND state='running'", ((instant() + timedelta(seconds=30)).isoformat(), job['id'], job['token']))

    def run_once(self, feed_id=None, at=None):
        with self.worker_lock() as acquired:
            if not acquired:
                return {'busy': True}
            ids = [feed_id] if feed_id else [f['id'] for f in self.list()['items']]
            for selected in ids:
                self.discover(selected, at)
            job = self.claim(feed_id)
            if job is None:
                return {'processed': None}
            stop = threading.Event()
            heart = threading.Thread(target=self._heartbeat, args=(job, stop), daemon=True)
            heart.start()
            try:
                result = self._process(job)
                return {'processed': job['id'], 'version_id': result}
            except Exception as exc:
                with self.store.db() as conn:
                    conn.execute('BEGIN IMMEDIATE')
                    current = conn.execute('SELECT * FROM feed_job WHERE id=?', (job['id'],)).fetchone()
                    if current['state'] == 'running' and current['token'] == job['token']:
                        retry = isinstance(exc, (OSError, sqlite3.OperationalError)) and current['execution_count'] < 3
                        delay = 5 if current['execution_count'] == 1 else 30
                        conn.execute('UPDATE feed_job SET state=?,error=?,next_retry=?,lease_until=NULL WHERE id=?', ('retry_wait' if retry else 'failed', str(exc), (instant() + timedelta(seconds=delay)).isoformat() if retry else None, job['id']))
                        self._event(conn, job['id'], 'retry_wait' if retry else 'failed', job['token'], {'error': str(exc)})
                return {'processed': job['id'], 'error': str(exc)}
            finally:
                stop.set()
                heart.join(timeout=6)

    def _process(self, job):
        with self.store.db() as conn:
            self._owned(conn, job)
            feed = self._feed(conn, job['feed_id'])
            delivery = decode(conn.execute('SELECT * FROM feed_delivery WHERE id=?', (job['delivery_id'],)).fetchone())
            contract = decode(conn.execute('SELECT * FROM feed_contract WHERE id=?', (job['contract_id'],)).fetchone())
        payload = (self.store.artifacts / delivery['artifact_sha']).read_bytes()
        if hashlib.sha256(payload).hexdigest() != delivery['artifact_sha']:
            raise ValueError('Retained artifact digest mismatch')
        definition = contract['definition']
        headers = next(csv.reader(io.StringIO(payload.decode(definition['encoding'])), delimiter=definition['delimiter']), [])
        hard = []
        if len(set(headers)) != len(headers) or any(not h for h in headers):
            hard.append({'code': 'headers', 'severity': 'hard', 'message': 'Headers must be unique and nonblank'})
        missing = sorted(set(definition['required_headers']) - set(headers))
        if missing:
            hard.append({'code': 'headers_missing', 'severity': 'hard', 'message': 'Missing required headers: ' + ', '.join(missing)})
        with self.store.db() as conn:
            conn.execute('BEGIN IMMEDIATE')
            current = self._owned(conn, job)
            receipt_id = current['receipt_id'] or uid()
            attempt_id = current['attempt_id'] or uid()
            if not current['receipt_id']:
                metadata = {'scope': json.loads(feed['scope']), 'managed_feed_id': feed['id'], 'delivery_id': delivery['id'], 'completeness': 'full', 'as_of': delivery['manifest']['as_of']}
                conn.execute('INSERT INTO receipt VALUES (?,?,?,?,?,?,?,?,?)', (receipt_id, delivery['manifest']['filename'], feed['source'], definition['designation'], now(), delivery['artifact_sha'], 'flat', None, packed(metadata)))
                conn.execute('UPDATE feed_job SET receipt_id=?,attempt_id=? WHERE id=?', (receipt_id, attempt_id, job['id']))
        detail = None
        if not hard:
            # The immutable job attempt ID makes normalization restartable.
            with self.store.db() as conn:
                existing = conn.execute('SELECT state FROM attempt WHERE id=?', (attempt_id,)).fetchone()
            if existing is None or existing['state'] in {'processing', 'interrupted'}:
                detail = self.store.mapping(receipt_id, {'recipe_revision_id': definition['recipe_revision_id'], 'encoding': definition['encoding'], 'delimiter': definition['delimiter']}, managed={'feed_id': feed['id'], 'baseline_attempt_id': job['baseline_attempt_id']}, attempt_id=attempt_id)
            else:
                detail = self.store.detail(receipt_id)
            if detail['attempt_id'] != attempt_id:
                raise Conflict('Managed receipt interpretation changed outside its job')
        report, rows = self._quality(job, definition, headers, hard, detail)
        if hard:
            from .intake_store import MAX_ROWS
            raw_count = 0
            for _ in csv.reader(io.StringIO(payload.decode(definition['encoding'])), delimiter=definition['delimiter']):
                raw_count += 1
                if raw_count > MAX_ROWS + 1:
                    raise ValueError('Row limit is 20,000')
            report['counts']['raw'] = max(0, raw_count - 1)
        version_id = uid()
        manifest = {'feed_id': feed['id'], 'delivery_id': delivery['id'], 'source_delivery': delivery['manifest'],
                    'receipt_id': receipt_id, 'attempt_id': attempt_id if detail else None,
                    'artifact_sha': delivery['artifact_sha'], 'contract_id': job['contract_id'], 'recipe_revision_id': definition['recipe_revision_id'],
                    'baseline_version': job['baseline_version'], 'output_schema_version': 1, 'policy_version': 1,
                    'records_sha256': digest([row for row in rows if not row['problems']]),
                    'designation': definition['designation'], 'notice': definition['designation'].capitalize() + ' source assertions, not independently verified provider truth.'}
        with self.store.db() as conn:
            conn.execute('BEGIN IMMEDIATE')
            self._owned(conn, job)
            prior = conn.execute('SELECT id FROM feed_version WHERE job_id=?', (job['id'],)).fetchone()
            if prior:
                version_id = prior[0]
            else:
                conn.execute('INSERT INTO feed_version VALUES (?,?,?,?,?,?,?,?)', (version_id, feed['id'], job['id'], packed(manifest), packed(report), digest(report), packed(rows), now()))
            conn.execute("UPDATE feed_job SET state='succeeded',lease_until=NULL WHERE id=? AND token=?", (job['id'], job['token']))
            self._event(conn, job['id'], 'succeeded', job['token'], {'version_id': version_id})
        return version_id

    def _quality(self, job, definition, headers, hard, detail):
        findings = list(hard)
        rows = detail['preview']['rows'] if detail else []
        comparison = detail['preview'].get('comparison') if detail else None
        counts = {'raw': None, 'valid': None, 'quarantined': None, 'unique': None}
        if detail and comparison is None:
            findings.append({'code': 'interpretation', 'severity': 'hard', 'message': detail['preview'].get('error') or 'Interpretation failed'})
        if detail and comparison is not None:
            preview = detail['preview']
            counts = {'raw': preview['total'], 'valid': preview['valid_count'], 'quarantined': preview['quarantined_count'], 'unique': comparison.get('unique_identity_count', 0)}
            if detail['state'] != 'preview_ready':
                findings.append({'code': 'interpretation', 'severity': 'hard', 'message': preview.get('error') or 'Interpretation did not complete'})
            if not counts['raw']:
                findings.append({'code': 'empty', 'severity': 'hard', 'message': 'Empty full snapshot cannot be approved'})
            elif not counts['valid']:
                findings.append({'code': 'no_valid', 'severity': 'hard', 'message': 'No valid records can be included'})
            if counts['quarantined']:
                findings.append({'code': 'quarantine', 'severity': 'hold', 'message': 'Quarantined rows are excluded; review incomplete coverage'})
            if comparison.get('missing_from_this_delivery'):
                findings.append({'code': 'missing_keys', 'severity': 'hold', 'message': 'Prior approved keys are missing; absence is not termination'})
            if job['baseline_version']:
                with self.store.db() as conn:
                    previous = json.loads(conn.execute('SELECT report FROM feed_version WHERE id=?', (job['baseline_version'],)).fetchone()[0])['counts']['raw']
                change = abs(counts['raw'] - previous) / previous if previous else 1
                if change > definition['row_change_fraction']:
                    findings.append({'code': 'row_count_drift', 'severity': 'hold', 'message': f'Raw row count changed by {change:.1%}'})
        if not job['baseline_version']:
            findings.append({'code': 'first_version', 'severity': 'warning', 'message': 'No approved baseline: baseline-dependent checks not assessed'})
        extra = sorted(set(headers) - set(definition['required_headers']))
        if extra:
            findings.append({'code': 'added_columns', 'severity': 'warning', 'message': 'Unmapped additional columns retained: ' + ', '.join(extra)})
        recipe_id = definition['recipe_revision_id']
        with self.store.db() as conn:
            fields = json.loads(conn.execute('SELECT definition FROM recipe_revision WHERE id=?', (recipe_id,)).fetchone()[0])['mapping']
        missing_rates = {field: sum(row['original'].get(column) in (None, '') for row in rows) / len(rows) if rows else None for field, column in fields.items()}
        effective = None
        if detail and comparison is not None and job['baseline_version']:
            with self.store.db() as conn:
                baseline = decode(conn.execute('SELECT * FROM feed_version WHERE id=?', (job['baseline_version'],)).fetchone())
            corrected = [row for row in baseline['rows'] if row.get('materialization') and not row['problems']]
            if corrected:
                # The parser compares against immutable source observations. A
                # corrected roster is a separate approved baseline, so expose
                # both views instead of silently replacing source history.
                from .recurring import identity
                incoming = {}
                for row in rows:
                    key = identity(row)
                    if key is not None:
                        incoming.setdefault(key, []).append(row)
                entries = []
                for prior in corrected:
                    key = identity(prior)
                    matches = incoming.get(key, []) if key is not None else []
                    current = matches[0] if len(matches) == 1 else None
                    old = {field: prior['normalized'].get(field) for field in ('phone', 'phone_extension')}
                    new = ({field: current['normalized'].get(field) for field in old} if current else None)
                    status = ('unresolved' if key is None or len(matches) > 1 else
                              'missing' if not matches else 'blocked_invalid' if current['problems'] else
                              'unchanged' if old == new else 'changed')
                    entries.append({'key': key, 'status': status, 'old': old, 'new': new,
                                    'previous_locator': prior['locator'],
                                    'current_locator': current['locator'] if current else None,
                                    'decision_id': prior['materialization']['decision_id']})
                effective = {'baseline_version': job['baseline_version'], 'fields': ['phone', 'phone_extension'],
                             'notice': 'Previously corrected offices compared with this delivery; source comparison above remains against retained source observations.',
                             'counts': {status: sum(entry['status'] == status for entry in entries)
                                        for status in ('changed', 'unchanged', 'missing', 'blocked_invalid', 'unresolved')},
                             'total': len(entries), 'entries': entries}
                if any(entry['status'] != 'unchanged' for entry in entries):
                    findings.append({'code': 'effective_correction_drift', 'severity': 'hold',
                                     'message': 'Incoming source differs from, omits, or cannot be compared with a previously approved local correction; inspect the effective correction comparison.'})
        return {'counts': counts, 'comparison': comparison, 'effective_corrections': effective,
                'required_field_missing_rates': missing_rates, 'baseline_version': job['baseline_version'], 'policy_version': 1, 'findings': findings}, rows

    def version(self, version_id, *, full=False):
        with self.store.db() as conn:
            row = conn.execute('SELECT * FROM feed_version WHERE id=?', (version_id,)).fetchone()
            if row is None:
                raise KeyError('Dataset version not found')
            result = decode(row)
            feed = self._feed(conn, result['feed_id'])
            decision = conn.execute('SELECT * FROM feed_decision WHERE version_id=?', (version_id,)).fetchone()
            result['state'] = decision['decision'] if decision else 'candidate'
            result['decision'] = dict(decision) if decision else None
            result['current_version'] = feed['current_version']
            result['review'] = [dict(r) for r in conn.execute('SELECT * FROM feed_exception WHERE version_id=? ORDER BY id', (version_id,))]
            result['delivery'] = result['manifest']['source_delivery']
            result['kind'] = 'derived_field_candidate' if result['manifest'].get('materialization') else 'source_delivery'
            if result['kind'] == 'derived_field_candidate':
                result['report_notice'] = 'Quality report and acknowledgments are inherited from the approved base; comparison findings describe that base, not the correction.'
        result['row_count'] = len(result['rows'])
        if not full:
            result['rows'] = result['rows'][:50]
            comparison = result['report'].get('comparison')
            if comparison and 'entries' in comparison:
                comparison['entry_count'] = len(comparison['entries'])
                comparison['entries'] = comparison['entries'][:50]
            effective = result['report'].get('effective_corrections')
            if effective:
                effective['entry_count'] = len(effective['entries'])
                effective['entries'] = effective['entries'][:50]
        return result

    def quality_report(self, version_id):
        """Return complete quality evidence; dataset-consumption approval stays separate."""
        with self.store.db() as conn:
            row = conn.execute('''SELECT v.id, v.feed_id, v.report_hash, v.report, d.decision
                                  FROM feed_version v LEFT JOIN feed_decision d ON d.version_id=v.id
                                  WHERE v.id=?''', (version_id,)).fetchone()
            if row is None:
                raise KeyError('Dataset version not found')
            return {'version_id': row['id'], 'feed_id': row['feed_id'],
                    'state': row['decision'] or 'candidate', 'report_hash': row['report_hash'],
                    'report': json.loads(row['report']),
                    'notice': 'Review evidence only; not an approved dataset export'}

    def correction_comparison_page(self, version_id, expected_report, status='all', offset=0, limit=20):
        """Page persisted correction evidence without making a candidate consumable."""
        from .reconciliation_store import page_parameters
        page_parameters(offset, limit)
        if status not in {'all', 'changed', 'unchanged', 'missing', 'blocked_invalid', 'unresolved'}:
            raise ValueError('Choose a valid comparison status')
        if not expected_report:
            raise ValueError('Provide the inspected report hash')
        result = self.quality_report(version_id)
        if result['report_hash'] != expected_report:
            raise Conflict('Report changed; reload before inspecting comparisons')
        comparison = result['report'].get('effective_corrections')
        entries = comparison['entries'] if comparison else []
        selected = [entry for entry in entries if status == 'all' or entry['status'] == status]
        return {'version_id': version_id, 'report_hash': result['report_hash'], 'status': status,
                'total': len(selected), 'offset': offset, 'limit': limit,
                'next_offset': offset + limit if offset + limit < len(selected) else None,
                'entries': selected[offset:offset + limit]}

    def review(self, version_id, payload):
        actor, reason = required(payload, 'actor'), required(payload, 'reason')
        with self.store.db() as conn:
            conn.execute('BEGIN IMMEDIATE')
            version = conn.execute('SELECT * FROM feed_version WHERE id=?', (version_id,)).fetchone()
            if version is None:
                raise KeyError('Dataset version not found')
            if payload.get('expected_report') != version['report_hash']:
                raise Conflict('Report changed; reload before reviewing')
            if conn.execute('SELECT 1 FROM feed_decision WHERE version_id=?', (version_id,)).fetchone():
                raise Conflict('Dataset version already decided')
            code = payload.get('code')
            findings = json.loads(version['report'])['findings']
            finding = next((f for f in findings if f['code'] == code), None)
            if not finding or finding['severity'] != 'hold':
                raise ValueError('Only soft approval holds can be acknowledged or deferred')
            if payload.get('disposition') not in {'acknowledged', 'deferred'}:
                raise ValueError('Choose acknowledged or deferred')
            conn.execute('INSERT INTO feed_exception(version_id,code,disposition,actor,reason,created_at) VALUES (?,?,?,?,?,?)', (version_id, code, payload['disposition'], actor, reason, now()))
        return self.version(version_id)

    def decide(self, version_id, payload):
        actor, reason, key = (required(payload, field) for field in ('actor', 'reason', 'idempotency_key'))
        request_hash = digest([version_id, payload])
        decision = payload.get('decision')
        if decision not in {'approved', 'rejected'}:
            raise ValueError('Choose approved or rejected')
        with self.store.db() as conn:
            conn.execute('BEGIN IMMEDIATE')
            previous = conn.execute('SELECT * FROM feed_decision WHERE idempotency_key=? OR version_id=?', (key, version_id)).fetchone()
            if previous:
                if previous['request_hash'] != request_hash:
                    raise Conflict('Decision already recorded with different inputs')
                return self.version(version_id)
            row = conn.execute('SELECT * FROM feed_version WHERE id=?', (version_id,)).fetchone()
            if row is None:
                raise KeyError('Dataset version not found')
            version = decode(row)
            feed = self._feed(conn, version['feed_id'])
            if payload.get('expected_report') != version['report_hash'] or 'expected_current' not in payload or payload['expected_current'] != feed['current_version']:
                raise Conflict('Report or current approved version changed; reload/reprocess before approval')
            if decision == 'approved':
                job = conn.execute('SELECT * FROM feed_job WHERE id=?', (version['job_id'],)).fetchone()
                if job['baseline_version'] != feed['current_version'] or job['config_revision'] != feed['revision']:
                    raise Conflict('Baseline or feed configuration changed; reprocess before approval')
                if feed['config']['contract_id'] != job['contract_id']:
                    raise Conflict('Active contract changed; reprocess before approval')
                source_ref = 'delivery:' + version['manifest']['source_delivery']['delivery_id']
                if conn.execute('SELECT 1 FROM feed_issue WHERE feed_id=? AND source_ref=?', (feed['id'], source_ref)).fetchone():
                    raise ValueError('Conflicting delivery ID blocks approval; deliver corrected bytes under a new ID')
                findings = version['report']['findings']
                if any(f['severity'] == 'hard' for f in findings):
                    raise ValueError('Hard quality blockers require correction and reprocessing')
                dispositions = {r['code']: r['disposition'] for r in conn.execute('SELECT * FROM feed_exception WHERE version_id=? ORDER BY id', (version_id,))}
                if any(f['severity'] == 'hold' and dispositions.get(f['code']) != 'acknowledged' for f in findings):
                    raise ValueError('Review and acknowledge every soft quality hold before approval')
                if feed['current_version']:
                    current_manifest = json.loads(conn.execute('SELECT manifest FROM feed_version WHERE id=?', (feed['current_version'],)).fetchone()[0])
                    if version['manifest']['source_delivery']['period'] < current_manifest['source_delivery']['period'] or version['manifest']['source_delivery']['as_of'] < current_manifest['source_delivery']['as_of']:
                        raise ValueError('Out-of-order delivery cannot regress current approved data')
                sha = version['manifest']['artifact_sha']
                if hashlib.sha256((self.store.artifacts / sha).read_bytes()).hexdigest() != sha:
                    raise ValueError('Retained artifact digest mismatch')
                if version['manifest'].get('materialization'):
                    from .field_materialization import FieldMaterialization
                    FieldMaterialization(self.store).validate_approval(conn, version)
                else:
                    self.store.commit_in_transaction(conn, version['manifest']['receipt_id'], {'actor': actor, 'reason': reason, 'policy': 'valid_rows', 'expected_attempt': version['manifest']['attempt_id']}, managed=True)
                conn.execute('UPDATE feed SET current_version=? WHERE id=?', (version_id, feed['id']))
            conn.execute('INSERT INTO feed_decision VALUES (?,?,?,?,?,?,?)', (version_id, decision, actor, reason, request_hash, key, now()))
        return self.version(version_id)

    def current(self, feed_id):
        feed = self.detail(feed_id)
        if not feed['current_version']:
            raise KeyError('No approved dataset version is available')
        version = self.version(feed['current_version'])
        period = date.fromisoformat(version['delivery']['period'])
        deadline = datetime.combine(period + timedelta(days=7), datetime.min.time(), tzinfo=timezone.utc) + timedelta(hours=33)
        return {'version_id': version['id'], 'stale': instant() > deadline, 'notice': 'Approved source assertions; freshness does not establish verified provider truth.'}

    def export(self, version_id):
        version = self.version(version_id, full=True)
        if version['state'] != 'approved':
            raise ValueError('Only explicitly approved dataset versions are consumable')
        # Do not include mutable current pointer or later review history in pinned bytes.
        rows = version['rows']
        return {'version_id': version_id, 'manifest': version['manifest'], 'report': version['report'],
                'report_hash': version['report_hash'], 'approval': version['decision'], 'exception_review': version['review'],
                'records': [row for row in rows if not row['problems']], 'quarantine': [row for row in rows if row['problems']]}

    def job_action(self, job_id, action, payload):
        actor, reason = required(payload, 'actor'), required(payload, 'reason')
        with self.store.db() as conn:
            conn.execute('BEGIN IMMEDIATE')
            job = conn.execute('SELECT * FROM feed_job WHERE id=?', (job_id,)).fetchone()
            if job is None:
                raise KeyError('Job not found')
            if action == 'cancel':
                if job['state'] == 'succeeded':
                    raise Conflict('Completed job cannot be cancelled')
                conn.execute("UPDATE feed_job SET state='cancelled',token=token+1,lease_until=NULL WHERE id=?", (job_id,))
            elif action == 'reprocess':
                delivery = conn.execute('SELECT manifest FROM feed_delivery WHERE id=?', (job['delivery_id'],)).fetchone()
                if json.loads(delivery['manifest']).get('kind') == 'derived_field_candidate':
                    raise Conflict('Derived field candidates cannot be reprocessed; create a new candidate from the current reviewed scope')
                if job['state'] in {'queued', 'running', 'retry_wait'}:
                    raise Conflict('Wait for or cancel active processing before reprocessing')
                feed = self._feed(conn, job['feed_id'])
                if not feed['config']['contract_id']:
                    raise ValueError('Select an approved contract first')
                baseline = feed['current_version']
                baseline_attempt = None
                if baseline:
                    baseline_attempt = json.loads(conn.execute('SELECT manifest FROM feed_version WHERE id=?', (baseline,)).fetchone()[0])['attempt_id']
                    prior = conn.execute('SELECT state,preview FROM attempt WHERE id=?', (baseline_attempt,)).fetchone()
                    if prior['state'] == 'duplicate_delivery':
                        baseline_attempt = json.loads(prior['preview'])['reuses_attempt']
                previous = conn.execute('SELECT id FROM feed_job WHERE delivery_id=? AND contract_id=? AND baseline_version IS ? AND config_revision=?', (job['delivery_id'], feed['config']['contract_id'], baseline, feed['revision'])).fetchone()
                if previous:
                    raise Conflict('These pinned inputs already have a job; retry failures or change reviewed inputs')
                new_id = uid()
                conn.execute('''INSERT INTO feed_job(id,feed_id,delivery_id,contract_id,config_revision,baseline_version,baseline_attempt_id,state,created_at)
                    VALUES (?,?,?,?,?,?,?,'queued',?)''', (new_id, feed['id'], job['delivery_id'], feed['config']['contract_id'], feed['revision'], baseline, baseline_attempt, now()))
                self._event(conn, new_id, 'reprocess', 0, {'actor': actor, 'reason': reason, 'previous_job': job_id})
            elif action == 'retry':
                if job['state'] not in {'failed', 'cancelled'}:
                    raise Conflict('Only failed/cancelled jobs can be retried')
                conn.execute("UPDATE feed_job SET state='queued',execution_count=0,next_retry=NULL WHERE id=?", (job_id,))
            else:
                raise ValueError('Unknown job action')
            self._event(conn, job_id, action, job['token'], {'actor': actor, 'reason': reason})
        return self.detail(job['feed_id'])
