"""Durable optional mapping assistance, with proposal-only publication."""
from __future__ import annotations

import hashlib
import json
import os
import time
from dataclasses import dataclass, field

from . import mapping_model
from .intake_store import Conflict, digest, now, packed, uid
from .managed_feed import ManagedFeed
from .onboarding_service import OnboardingService

MIGRATION_13 = '''
CREATE TABLE assistant_run (
 id TEXT PRIMARY KEY, request_id TEXT NOT NULL UNIQUE, intent_hash TEXT NOT NULL,
 receipt_id TEXT NOT NULL REFERENCES receipt(id), attempt_id TEXT NOT NULL REFERENCES attempt(id),
 config TEXT NOT NULL, context TEXT NOT NULL, request_sha TEXT NOT NULL REFERENCES artifact(sha),
 response_sha TEXT REFERENCES artifact(sha), state TEXT NOT NULL, revision INTEGER NOT NULL,
 reserved_microusd INTEGER NOT NULL DEFAULT 0, result TEXT NOT NULL,
 proposal_id TEXT REFERENCES recipe_revision(id), created_at TEXT NOT NULL);
CREATE TABLE assistant_run_event (
 seq INTEGER PRIMARY KEY, run_id TEXT NOT NULL REFERENCES assistant_run(id),
 kind TEXT NOT NULL, payload TEXT NOT NULL, artifact_sha TEXT REFERENCES artifact(sha), created_at TEXT NOT NULL);
CREATE INDEX assistant_run_receipt ON assistant_run(receipt_id,created_at);
CREATE TRIGGER assistant_event_no_update BEFORE UPDATE ON assistant_run_event BEGIN SELECT RAISE(ABORT,'Immutable assistant event'); END;
CREATE TRIGGER assistant_event_no_delete BEFORE DELETE ON assistant_run_event BEGIN SELECT RAISE(ABORT,'Immutable assistant event'); END;
'''
TERMINAL = {'succeeded', 'failed', 'cancelled', 'unavailable'}
RESERVATION = 80_000
LIFETIME = 1_000_000


@dataclass(frozen=True)
class Configuration:
    enabled: bool = False
    api_key: str = field(default='', repr=False)
    allowed_sources: tuple[str, ...] = ()

    @classmethod
    def environment(cls):
        return cls(enabled=os.environ.get('PDTL_ASSISTANT_ENABLED') == '1',
                   api_key=os.environ.get('OPENAI_API_KEY', '').strip(),
                   allowed_sources=tuple(value.strip() for value in os.environ.get('PDTL_ASSISTANT_ALLOWED_SOURCES', '').split(',') if value.strip()))

    def public(self):
        return {'provider': 'OpenAI Responses API', 'model': mapping_model.MODEL,
                'available': bool(self.enabled and self.api_key), 'experimental': True,
                'reason': None if self.enabled and self.api_key else 'Optional model client is disabled or OPENAI_API_KEY is unavailable',
                'prompt_version': mapping_model.PROMPT_VERSION, 'schema_version': mapping_model.SCHEMA_VERSION,
                'limits': mapping_model.LIMITS, 'rates': mapping_model.RATES}


class MappingAssistant:
    def __init__(self, store, *, configuration=None, transport=mapping_model.invoke):
        self.store = store
        self.onboarding = OnboardingService(store)
        self.configuration = configuration or Configuration.environment()
        self.transport = transport

    @staticmethod
    def _event(conn, run_id, kind, payload, sha=None):
        conn.execute('INSERT INTO assistant_run_event(run_id,kind,payload,artifact_sha,created_at) VALUES (?,?,?,?,?)',
                     (run_id, kind, packed(payload), sha, now()))

    def detail(self, receipt_id, run_id):
        with self.store.db() as conn:
            conn.execute('BEGIN')
            row = conn.execute('SELECT * FROM assistant_run WHERE id=? AND receipt_id=?', (run_id, receipt_id)).fetchone()
            if row is None:
                raise KeyError('Assistant run not found for this receipt')
            result = dict(row)
            for key in ('config', 'context', 'result'):
                result[key] = json.loads(result[key])
            result['events'] = [{**dict(event), 'payload': json.loads(event['payload'])} for event in conn.execute(
                'SELECT * FROM assistant_run_event WHERE run_id=? ORDER BY seq', (run_id,))]
        return result

    def list(self, receipt_id):
        detail = self.store.detail(receipt_id)
        with self.store.db() as conn:
            items = [dict(row) for row in conn.execute(
                'SELECT id,state,revision,attempt_id,proposal_id,created_at FROM assistant_run WHERE receipt_id=? ORDER BY created_at DESC LIMIT 100', (receipt_id,))]
            reserved = conn.execute('SELECT coalesce(sum(reserved_microusd),0) FROM assistant_run').fetchone()[0]
        eligible = detail['designation'] == 'synthetic' or detail['source'] in self.configuration.allowed_sources
        return {'configuration': self.configuration.public(), 'source_processing_allowed': eligible,
                'reserved_usd': reserved / 1_000_000, 'items': items}

    def _eligible(self, detail):
        if detail['designation'] != 'synthetic' and detail['source'] not in self.configuration.allowed_sources:
            raise ValueError('This source namespace has no server-configured external-processing permission')

    def create(self, receipt_id, payload):
        if set(payload) != {'request_id', 'expected_attempt', 'actor', 'reason', 'external_processing'}:
            raise ValueError('Supply only request_id, expected_attempt, actor, reason and external_processing')
        for key in ('request_id', 'expected_attempt', 'actor', 'reason'):
            if not isinstance(payload[key], str) or not payload[key].strip() or len(payload[key]) > 2000:
                raise ValueError(key + ' requires nonblank bounded text')
        if payload['external_processing'] is not True:
            raise ValueError('Explicit external-processing permission is required for this run')
        intent_hash = digest([receipt_id, payload])
        with self.store.db() as conn:
            prior = conn.execute('SELECT id,intent_hash,receipt_id FROM assistant_run WHERE request_id=?', (payload['request_id'],)).fetchone()
        if prior:
            if prior['intent_hash'] != intent_hash:
                raise Conflict('Assistant request ID has different content')
            return self.detail(receipt_id, prior['id'])
        detail = self.store.detail(receipt_id)
        self._eligible(detail)
        raw, context = mapping_model.build_request(self.onboarding, receipt_id, payload['expected_attempt'])
        context['external_processing_policy'] = {
            'basis': 'synthetic-designation' if detail['designation'] == 'synthetic' else 'configured-source-namespace',
            'source': detail['source'], 'explicit_run_permission': True}
        sha = self.store.retain(raw)
        configuration = self.configuration.public()
        state = 'queued' if configuration['available'] else 'unavailable'
        result = {} if state == 'queued' else {'error': configuration['reason']}
        with self.store.db() as conn:
            conn.execute('BEGIN IMMEDIATE')
            prior = conn.execute('SELECT id,intent_hash FROM assistant_run WHERE request_id=?', (payload['request_id'],)).fetchone()
            if prior:
                if prior['intent_hash'] != intent_hash:
                    raise Conflict('Assistant request ID has different content')
                run_id = prior['id']
            else:
                self.onboarding._check_attempt(conn, receipt_id, payload['expected_attempt'])
                run_id = uid()
                conn.execute('''INSERT INTO assistant_run
                    (id,request_id,intent_hash,receipt_id,attempt_id,config,context,request_sha,state,revision,result,created_at)
                    VALUES (?,?,?,?,?,?,?,?,?,0,?,?)''',
                    (run_id, payload['request_id'], intent_hash, receipt_id, payload['expected_attempt'],
                     packed(configuration), packed(context), sha, state, packed(result), now()))
                self._event(conn, run_id, 'created', payload, sha)
        return self.detail(receipt_id, run_id)

    def cancel(self, receipt_id, run_id, payload):
        if (set(payload) != {'expected_revision', 'actor', 'reason'} or type(payload['expected_revision']) is not int
                or any(not isinstance(payload[k], str) or not payload[k].strip() or len(payload[k]) > 2000 for k in ('actor', 'reason'))):
            raise ValueError('Cancellation requires current revision, actor and reason')
        with self.store.db() as conn:
            conn.execute('BEGIN IMMEDIATE')
            row = conn.execute('SELECT * FROM assistant_run WHERE id=? AND receipt_id=?', (run_id, receipt_id)).fetchone()
            if row is None:
                raise KeyError('Assistant run not found')
            if row['state'] in TERMINAL or row['revision'] != payload['expected_revision']:
                raise Conflict('Assistant run changed or is terminal')
            conn.execute("UPDATE assistant_run SET state='cancelled',revision=revision+1 WHERE id=?", (run_id,))
            self._event(conn, run_id, 'cancelled', payload)
        return self.detail(receipt_id, run_id)

    def _fail(self, row, message, state='failed'):
        with self.store.db() as conn:
            conn.execute('BEGIN IMMEDIATE')
            changed = conn.execute('UPDATE assistant_run SET state=?,revision=revision+1,result=? WHERE id=? AND revision=?',
                                   (state, packed({**row['result'], 'error': message}), row['id'], row['revision'])).rowcount
            if changed:
                self._event(conn, row['id'], state, {'error': message})
        return self.detail(row['receipt_id'], row['id'])

    def _read(self, sha):
        try:
            raw = (self.store.artifacts / sha).read_bytes()
        except OSError:
            raise ValueError('Retained assistant artifact is unavailable') from None
        if hashlib.sha256(raw).hexdigest() != sha:
            raise ValueError('Assistant artifact digest mismatch')
        return raw

    def run_once(self, receipt_id, run_id):
        with ManagedFeed(self.store).worker_lock() as acquired:
            if not acquired:
                return {**self.detail(receipt_id, run_id), 'busy': True}
            row = self.detail(receipt_id, run_id)
            if row['state'] in TERMINAL:
                return row
            if row['state'] == 'running':
                return self._fail(row, 'Interrupted provider call has unknown outcome; no automatic retry. Create a new run only after review.')
            if row['state'] == 'queued':
                if not self.configuration.public()['available']:
                    return self._fail(row, 'Model client is now unavailable; no request sent', state='unavailable')
                try:
                    self._eligible(self.store.detail(receipt_id))
                    current_config = self.configuration.public()
                    if any(row['config'].get(key) != current_config[key] for key in ('provider', 'model', 'prompt_version', 'schema_version', 'limits', 'rates')):
                        raise ValueError('Assistant configuration changed; create a new reviewed run')
                    raw = self._read(row['request_sha'])
                    if len(raw) > mapping_model.LIMITS['request_bytes']:
                        raise ValueError('Retained request exceeds budget')
                    with self.store.db() as conn:
                        conn.execute('BEGIN IMMEDIATE')
                        self.onboarding._check_attempt(conn, receipt_id, row['attempt_id'])
                        reserved = conn.execute('SELECT coalesce(sum(reserved_microusd),0) FROM assistant_run').fetchone()[0]
                        if reserved + RESERVATION > LIFETIME:
                            raise ValueError('Local lifetime assistant budget exhausted; no request sent')
                        changed = conn.execute("UPDATE assistant_run SET state='running',reserved_microusd=?,revision=revision+1 WHERE id=? AND revision=?", (RESERVATION, run_id, row['revision'])).rowcount
                        if not changed:
                            return self.detail(receipt_id, run_id)
                        self._event(conn, run_id, 'invocation_started', {'reserved_usd': RESERVATION / 1_000_000})
                except (ValueError, Conflict, OSError) as exc:
                    return self._fail(row, str(exc))
                row = self.detail(receipt_id, run_id)
                started = time.monotonic()
                # The injected transport is test-only. Production invokes the one fixed HTTPS endpoint.
                try:
                    reply = self.transport(raw, self.configuration.api_key)
                except OSError:
                    reply = {'status': None, 'body': b'', 'error': 'Provider transport failed; outcome may be unknown', 'request_id': None}
                elapsed = time.monotonic() - started
                response_sha = self.store.retain(reply['body']) if reply['body'] else None
                error = reply.get('error')
                if reply.get('status') == 200 and not reply['body']:
                    error = 'Provider returned an empty response'
                if elapsed > mapping_model.LIMITS['active_seconds']:
                    error = 'Provider active-call deadline exceeded'
                if reply.get('status') != 200:
                    error = error or f"Provider HTTP {reply.get('status')}; no automatic retry"
                evidence = {'status': reply.get('status'), 'request_id': reply.get('request_id'),
                            'elapsed_seconds': elapsed, 'error': error, 'response_truncated': bool(reply.get('truncated'))}
                try:
                    parsed = mapping_model.strict_json(reply['body'])
                    evidence.update(mapping_model.summarize_usage(parsed.get('usage')))
                except (ValueError, TypeError, AttributeError, RecursionError):
                    pass  # Exact retained bytes remain available when accounting cannot be interpreted.
                with self.store.db() as conn:
                    conn.execute('BEGIN IMMEDIATE')
                    self._event(conn, run_id, 'response', evidence, response_sha)
                    changed = conn.execute("UPDATE assistant_run SET state=?,response_sha=?,result=?,revision=revision+1 WHERE id=? AND revision=?", ('failed' if error else 'response_ready', response_sha, packed(evidence), run_id, row['revision'])).rowcount
                    if not changed:
                        self._event(conn, run_id, 'discarded_response', {'reason': 'Concurrent cancellation fenced this response'}, response_sha)
                row = self.detail(receipt_id, run_id)
            if row['state'] != 'response_ready':
                return row
            try:
                result = mapping_model.parse_response(self._read(row['response_sha']), row['context'])
                self.onboarding.preview(receipt_id, result['definition'], row['attempt_id'], limit=1)
                with self.store.db() as conn:
                    conn.execute('BEGIN IMMEDIATE')
                    current = conn.execute('SELECT revision FROM assistant_run WHERE id=?', (run_id,)).fetchone()
                    if current['revision'] != row['revision']:
                        return self.detail(receipt_id, run_id)
                    proposal = self.onboarding._save_proposal(conn, receipt_id, {
                        'name': 'Model mapping proposal', 'actor': 'OpenAI model proposal: ' + mapping_model.MODEL,
                        'reason': f"Assistant run {run_id}; review required. " + result['explanation'],
                        'expected_attempt': row['attempt_id']}, result['definition'])
                    result['invocation'] = row['result']
                    conn.execute("UPDATE assistant_run SET state='succeeded',result=?,proposal_id=?,revision=revision+1 WHERE id=? AND revision=?", (packed(result), proposal['id'], run_id, row['revision']))
                    self._event(conn, run_id, 'proposal_saved', {'proposal_id': proposal['id'], 'approval': 'not_granted'})
            except (ValueError, Conflict, KeyError, TypeError, RecursionError, OSError) as exc:
                return self._fail(row, 'Proposal rejected: ' + str(exc))
            return self.detail(receipt_id, run_id)
