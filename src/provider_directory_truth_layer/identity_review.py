"""Explicit append-only identity crosswalks; never mutate source observations."""
from __future__ import annotations

import json

from .comparison import RULE_VERSION
from .intake_store import Conflict, digest, now, packed, uid

MIGRATION_7 = '''
CREATE TABLE clinician_identity (
 id TEXT PRIMARY KEY, label TEXT NOT NULL, identifiers TEXT NOT NULL,
 actor TEXT NOT NULL, reason TEXT NOT NULL, created_at TEXT NOT NULL);
CREATE TABLE identity_review_decision (
 seq INTEGER PRIMARY KEY AUTOINCREMENT, id TEXT NOT NULL UNIQUE,
 request_id TEXT NOT NULL UNIQUE, request_hash TEXT NOT NULL,
 run_id TEXT NOT NULL REFERENCES comparison_run(id), candidate_id TEXT NOT NULL,
 pair_key TEXT NOT NULL, kind TEXT NOT NULL CHECK(kind IN ('clinician','location')),
 decision TEXT NOT NULL CHECK(decision IN ('approve','reject','defer')),
 target_id TEXT, previous_id TEXT REFERENCES identity_review_decision(id),
 snapshot TEXT NOT NULL, actor TEXT NOT NULL, reason TEXT NOT NULL, created_at TEXT NOT NULL,
 FOREIGN KEY(run_id,candidate_id) REFERENCES comparison_candidate(run_id,id));
CREATE INDEX review_pair_history ON identity_review_decision(pair_key,seq DESC);
CREATE TABLE reviewed_identity_link (
 seq INTEGER PRIMARY KEY AUTOINCREMENT, id TEXT NOT NULL UNIQUE,
 kind TEXT NOT NULL CHECK(kind IN ('clinician','location')), ref TEXT NOT NULL,
 clinician_id TEXT REFERENCES clinician_identity(id),
 practice_location_id TEXT REFERENCES practice_location(id),
 previous_id TEXT REFERENCES reviewed_identity_link(id),
 decision_id TEXT NOT NULL REFERENCES identity_review_decision(id),
 run_id TEXT NOT NULL REFERENCES comparison_run(id),
 actor TEXT NOT NULL, reason TEXT NOT NULL, created_at TEXT NOT NULL,
 CHECK((kind='clinician' AND clinician_id IS NOT NULL AND practice_location_id IS NULL)
 OR (kind='location' AND clinician_id IS NULL AND practice_location_id IS NOT NULL)));
CREATE INDEX reviewed_link_current ON reviewed_identity_link(kind,ref,seq DESC);
'''
for _table in ('clinician_identity', 'identity_review_decision', 'reviewed_identity_link'):
    for _action in ('UPDATE', 'DELETE'):
        MIGRATION_7 += f"CREATE TRIGGER {_table}_no_{_action.lower()} BEFORE {_action} ON {_table} BEGIN SELECT RAISE(ABORT,'Immutable {_table}'); END;\n"


def link_record(row):
    if row is None:
        return None
    result = dict(row)
    result['target_id'] = result['clinician_id'] or result['practice_location_id']
    return result


class IdentityReview:
    def __init__(self, store):
        self.store = store
        from .reconciliation_store import ReconciliationStore
        self.comparison = ReconciliationStore(store)

    def _context(self, conn, run_id, candidate_id):
        row = conn.execute('SELECT * FROM comparison_run WHERE id=?', (run_id,)).fetchone()
        if row is None:
            raise KeyError('Comparison run not found')
        selected = conn.execute('SELECT payload FROM comparison_candidate WHERE run_id=? AND id=?',
                                (run_id, candidate_id)).fetchone()
        if selected is None:
            raise KeyError('Candidate not found in selected run')
        candidate = json.loads(selected[0])
        refs = sorted([candidate['left'], candidate['right']])
        records = json.loads(row['records'])
        blockers = []
        for ref in refs:
            evidence = [record for record in records if
                        (record['clinician_ref'] if candidate['kind'] == 'clinician' else record['ref']) == ref]
            if not evidence:
                blockers.append('Retained candidate reference has no source evidence')
            elif candidate['kind'] == 'clinician' and any(record['comparison']['entity_kind'] != 'clinician' for record in evidence):
                blockers.append('Clinician approval requires explicit clinician type for both sources; declare unknown types and create a new run')
            elif candidate['kind'] == 'location' and any(record['comparison']['address']['kind'] != 'practice' for record in evidence):
                blockers.append('Location approval requires explicit practice-address purpose for both sources; reinterpret unknown address purpose')
        pair_key = digest([candidate['kind'], refs])
        links = {ref: link_record(conn.execute('SELECT * FROM reviewed_identity_link WHERE kind=? AND ref=? ORDER BY seq DESC LIMIT 1',
                                              (candidate['kind'], ref)).fetchone()) for ref in refs}
        latest = conn.execute('SELECT * FROM identity_review_decision WHERE pair_key=? ORDER BY seq DESC LIMIT 1', (pair_key,)).fetchone()
        latest = dict(latest) if latest else None
        pins = json.loads(row['inputs'])
        current = self.comparison._snapshot(conn, pins)
        fresh = current == json.loads(row['baseline_snapshot']) and row['rule_version'] == RULE_VERSION
        revisions = {ref: link['id'] if link else None for ref, link in links.items()}
        snapshot = digest([run_id, candidate_id, current, RULE_VERSION, revisions, latest['id'] if latest else None])
        return {'candidate': candidate, 'pair_key': pair_key, 'current_links': links,
                'latest_decision': latest, 'review_snapshot': snapshot, 'inputs_fresh': fresh,
                'approval_allowed': not blockers, 'approval_blockers': sorted(set(blockers))}

    def inspect(self, run_id, candidate_id, offset=0, limit=20):
        from .reconciliation_store import page_parameters
        page_parameters(offset, limit)
        with self.store.db() as conn:
            conn.execute('BEGIN')
            context = self._context(conn, run_id, candidate_id)
            context['history'] = [dict(row) for row in conn.execute(
                'SELECT * FROM identity_review_decision WHERE pair_key=? ORDER BY seq DESC LIMIT ? OFFSET ?',
                (context['pair_key'], limit, offset))]
            total = conn.execute('SELECT count(*) FROM identity_review_decision WHERE pair_key=?', (context['pair_key'],)).fetchone()[0]
            context.update(history_total=total, history_next_offset=offset + limit if offset + limit < total else None)
            context['targets'] = {
                'clinicians': [dict(row) for row in conn.execute('SELECT id,label FROM clinician_identity ORDER BY label,id LIMIT 100')],
                'locations': [dict(row) for row in conn.execute('SELECT id,label FROM practice_location ORDER BY label,id LIMIT 100')]}
            context['target_counts'] = {'clinicians': conn.execute('SELECT count(*) FROM clinician_identity').fetchone()[0],
                                        'locations': conn.execute('SELECT count(*) FROM practice_location').fetchone()[0]}
        return context

    def targets(self, kind, search='', offset=0, limit=20):
        from .reconciliation_store import page_parameters
        page_parameters(offset, limit)
        if kind not in {'clinician', 'location'} or not isinstance(search, str) or len(search) > 512:
            raise ValueError('Choose clinician/location and a search of at most 512 characters')
        table = 'clinician_identity' if kind == 'clinician' else 'practice_location'
        # instr treats user percent/underscore characters literally, unlike LIKE.
        with self.store.db() as conn:
            conn.execute('BEGIN')
            total = conn.execute(f'SELECT count(*) FROM {table} WHERE instr(lower(label),lower(?))>0 OR id=?', (search, search)).fetchone()[0]
            items = [dict(row) for row in conn.execute(f'SELECT id,label FROM {table} WHERE instr(lower(label),lower(?))>0 OR id=? ORDER BY label,id LIMIT ? OFFSET ?',
                                                       (search, search, limit, offset))]
        return {'items': items, 'total': total, 'next_offset': offset + limit if offset + limit < total else None}

    @staticmethod
    def _saved(conn, decision):
        return {'decision': dict(decision), 'links': [link_record(row) for row in conn.execute(
            'SELECT * FROM reviewed_identity_link WHERE decision_id=? ORDER BY ref', (decision['id'],))]}

    def decide(self, payload):
        allowed = {'run_id', 'candidate_id', 'decision', 'request_id', 'expected_snapshot',
                   'expected_revisions', 'expected_decision', 'actor', 'reason', 'target_id', 'new_label'}
        if not isinstance(payload, dict) or set(payload) - allowed:
            raise ValueError('Unknown identity review fields')
        for key in ('run_id', 'candidate_id', 'decision', 'request_id', 'expected_snapshot', 'actor', 'reason'):
            if not isinstance(payload.get(key), str) or not payload[key].strip() or len(payload[key]) > 4096:
                raise ValueError(key + ' must be a nonblank string of at most 4096 characters')
        values = {key: self.store.required(payload, key) for key in
                  ('run_id', 'candidate_id', 'decision', 'request_id', 'expected_snapshot', 'actor', 'reason')}
        action = values['decision']
        if action not in {'approve', 'reject', 'defer'}:
            raise ValueError('Choose approve, reject or defer')
        if not isinstance(payload.get('expected_revisions'), dict) or 'expected_decision' not in payload:
            raise ValueError('Supply exact prior link revisions and prior decision')
        target, label = payload.get('target_id'), payload.get('new_label')
        if action == 'approve':
            if bool(target) == bool(label):
                raise ValueError('Select an existing target OR explicitly label a new identity')
            if target is not None and (not isinstance(target, str) or not target.strip()):
                raise ValueError('Target must be a nonblank identity ID')
            if label is not None and (not isinstance(label, str) or not label.strip() or len(label) > 512):
                raise ValueError('New identity label must be 1..512 characters')
        elif target is not None or label is not None:
            raise ValueError('Reject/defer only record a pair decision; omit identity targets')
        request_hash = digest(payload)
        with self.store.db() as conn:
            conn.execute('BEGIN IMMEDIATE')
            prior_request = conn.execute('SELECT * FROM identity_review_decision WHERE request_id=?', (values['request_id'],)).fetchone()
            if prior_request:
                if prior_request['request_hash'] != request_hash:
                    raise Conflict('Request ID already used with different review content')
                return self._saved(conn, prior_request)
            context = self._context(conn, values['run_id'], values['candidate_id'])
            if not context['inputs_fresh'] or context['review_snapshot'] != values['expected_snapshot']:
                raise Conflict('Review snapshot is stale; inspect the candidate again')
            current_revisions = {ref: link['id'] if link else None for ref, link in context['current_links'].items()}
            latest_id = context['latest_decision']['id'] if context['latest_decision'] else None
            if payload['expected_revisions'] != current_revisions or payload['expected_decision'] != latest_id:
                raise Conflict('Reviewed links or pair decision changed; inspect again')
            kind = context['candidate']['kind']
            if action == 'approve':
                if not context['approval_allowed']:
                    raise ValueError('; '.join(context['approval_blockers']))
                table = 'clinician_identity' if kind == 'clinician' else 'practice_location'
                if target:
                    if conn.execute(f'SELECT id FROM {table} WHERE id=?', (target,)).fetchone() is None:
                        raise ValueError('Selected target does not exist for this identity kind')
                else:
                    target = uid()
                    if kind == 'clinician':
                        conn.execute('INSERT INTO clinician_identity VALUES (?,?,?,?,?,?)',
                                     (target, label.strip(), '[]', values['actor'], values['reason'], now()))
                    else:
                        conn.execute('INSERT INTO practice_location VALUES (?,?,?,?,?,?)',
                                     (target, label.strip(), None, values['actor'], values['reason'], now()))
            decision_id = uid()
            conn.execute('''INSERT INTO identity_review_decision
                (id,request_id,request_hash,run_id,candidate_id,pair_key,kind,decision,target_id,previous_id,snapshot,actor,reason,created_at)
                VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)''',
                (decision_id, values['request_id'], request_hash, values['run_id'], values['candidate_id'],
                 context['pair_key'], kind, action, target, latest_id, values['expected_snapshot'], values['actor'], values['reason'], now()))
            if action == 'approve':
                for ref, previous in current_revisions.items():
                    conn.execute('''INSERT INTO reviewed_identity_link
                        (id,kind,ref,clinician_id,practice_location_id,previous_id,decision_id,run_id,actor,reason,created_at)
                        VALUES (?,?,?,?,?,?,?,?,?,?,?)''',
                        (uid(), kind, ref, target if kind == 'clinician' else None,
                         target if kind == 'location' else None, previous, decision_id, values['run_id'],
                         values['actor'], values['reason'], now()))
            return self._saved(conn, conn.execute('SELECT * FROM identity_review_decision WHERE id=?', (decision_id,)).fetchone())

    def identity(self, kind, identity_id, offset=0, limit=20, history_offset=0):
        from .reconciliation_store import page_parameters, sample_record
        page_parameters(offset, limit)
        page_parameters(history_offset, limit)
        if kind not in {'clinician', 'location'}:
            raise ValueError('Choose clinician or location')
        table = 'clinician_identity' if kind == 'clinician' else 'practice_location'
        column = 'clinician_id' if kind == 'clinician' else 'practice_location_id'
        with self.store.db() as conn:
            conn.execute('BEGIN')
            identity = conn.execute(f'SELECT * FROM {table} WHERE id=?', (identity_id,)).fetchone()
            if identity is None:
                raise KeyError('Reviewed identity not found')
            links = [link_record(row) for row in conn.execute(f'''SELECT l.* FROM reviewed_identity_link l
                WHERE l.{column}=? AND NOT EXISTS(SELECT 1 FROM reviewed_identity_link n
                  WHERE n.kind=l.kind AND n.ref=l.ref AND n.seq>l.seq) ORDER BY l.ref''', (identity_id,))]
            total = len(links)
            assertions = []
            for link in links[offset:offset + limit]:
                run = conn.execute('SELECT * FROM comparison_run WHERE id=?', (link['run_id'],)).fetchone()
                records = json.loads(run['records'])
                evidence = [r for r in records if (r['clinician_ref'] if kind == 'clinician' else r['ref']) == link['ref']]
                fresh = self.comparison._snapshot(conn, json.loads(run['inputs'])) == json.loads(run['baseline_snapshot']) and run['rule_version'] == RULE_VERSION
                samples = [sample_record(record, 50) for record in evidence[:50]]
                assertions.append({'link': link, 'records': [sample[0] for sample in samples],
                                   'record_count': len(evidence),
                                   'sample_truncated': len(evidence) > 50 or any(sample[1] for sample in samples),
                                   'inputs_fresh': fresh})
            history = [link_record(row) for row in conn.execute(
                f'SELECT * FROM reviewed_identity_link WHERE {column}=? ORDER BY seq LIMIT ? OFFSET ?', (identity_id, limit, history_offset))]
            history_total = conn.execute(f'SELECT count(*) FROM reviewed_identity_link WHERE {column}=?', (identity_id,)).fetchone()[0]
        return {'identity': dict(identity), 'kind': kind, 'assertions': assertions, 'history': history,
                'total': total, 'next_offset': offset + limit if offset + limit < total else None,
                'history_total': history_total, 'history_next_offset': history_offset + limit if history_offset + limit < history_total else None,
                'notice': 'Reviewed crosswalk only; source assertions remain separate and unverified.'}
