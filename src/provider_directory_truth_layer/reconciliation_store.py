"""Immutable, scoped comparison runs over retained interpretation evidence."""
from __future__ import annotations

import json
import re
import time

from .comparison import RULE_VERSION, cleanse, generate_candidates
from .comparison_inputs import make_records
from .intake_store import Conflict, digest, now, packed, uid

MAX_RECORDS = 5000
MAX_CANDIDATES = 10000
MIGRATION_6 = '''
CREATE TABLE observation_comparison (
 observation_id TEXT PRIMARY KEY REFERENCES observation(id), rule_version TEXT NOT NULL,
 evidence TEXT NOT NULL);
CREATE TABLE comparison_run (
 id TEXT PRIMARY KEY, inputs TEXT NOT NULL, rule_version TEXT NOT NULL,
 records TEXT NOT NULL, baseline_snapshot TEXT NOT NULL, metrics TEXT NOT NULL,
 actor TEXT NOT NULL, reason TEXT NOT NULL, created_at TEXT NOT NULL);
CREATE TABLE comparison_candidate (
 id TEXT NOT NULL, run_id TEXT NOT NULL REFERENCES comparison_run(id),
 kind TEXT NOT NULL CHECK(kind IN ('clinician','location')), rank INTEGER NOT NULL,
 eligible INTEGER NOT NULL, payload TEXT NOT NULL, PRIMARY KEY(run_id,id));
CREATE INDEX candidate_page ON comparison_candidate(run_id,kind,rank DESC,id);
'''
for _table in ('observation_comparison', 'comparison_run', 'comparison_candidate'):
    for _action in ('UPDATE', 'DELETE'):
        MIGRATION_6 += f"CREATE TRIGGER {_table}_no_{_action.lower()} BEFORE {_action} ON {_table} BEGIN SELECT RAISE(ABORT,'Immutable {_table}'); END;\n"


def page_parameters(offset, limit):
    if type(offset) is not int or type(limit) is not int or offset < 0 or not 1 <= limit <= 100:
        raise ValueError('Use offset >= 0 and limit 1..100')


def sample_record(record, limit):
    from .evidence_samples import sample_value
    item, clipped = {}, False
    budget = max(400, 80_000 // max(1, limit) // 2)
    for key, value in record.items():
        if key not in {'field_findings', 'source_problems'} and isinstance(value, (dict, list)):
            item[key], truncated = sample_value(value, budget=budget)
            clipped |= truncated
        elif isinstance(value, str) and len(value) > 512:
            item[key] = value[:512] + ' [sample truncated]'
            clipped = True
        else:
            item[key] = value
    return item, clipped


class ReconciliationStore:
    def __init__(self, store):
        self.store = store

    def _input(self, selection):
        if not isinstance(selection, dict) or set(selection) - {'receipt_id', 'attempt_id', 'entity_kind'}:
            raise ValueError('Select receipt_id, attempt_id and optional entity_kind only')
        receipt_id, attempt_id = selection.get('receipt_id'), selection.get('attempt_id')
        if not isinstance(receipt_id, str) or not isinstance(attempt_id, str):
            raise ValueError('Select explicit receipt and interpretation IDs')
        detail = self.store.detail(receipt_id)
        if detail['attempt_id'] != attempt_id:
            raise Conflict('Selected interpretation is no longer current; inspect the delivery again')
        attempt = detail['attempts'][-1]
        if attempt['state'] in {'processing', 'failed', 'interrupted', 'rejected'}:
            raise ValueError('Choose a parsed interpretation; failed/interrupted/rejected input is not ready')
        rows = attempt['preview'].get('rows', [])
        if not rows:
            raise ValueError('Selected interpretation contains no source records')
        declared = selection.get('entity_kind', 'unknown')
        records = make_records(detail, attempt_id, rows, attempt['spec'], declared)
        from .recurring import comparison_scope
        pin = {'receipt_id': receipt_id, 'attempt_id': attempt_id, 'fingerprint': attempt['fingerprint'],
               'source': detail['source'], 'profile': detail['profile'], 'scope': detail['metadata'].get('scope'),
               'comparison_scope': comparison_scope(detail, attempt['spec']),
               'lookup_query': detail['metadata'].get('lookup_query'),
               'entity_kind': declared, 'designation': detail['designation']}
        return pin, records

    @staticmethod
    def _baseline(conn, pin):
        from .recurring import comparison_scope
        rows = conn.execute('''SELECT a.id,a.spec,r.metadata FROM attempt a JOIN receipt r ON r.id=a.receipt_id
            WHERE r.source=? AND r.profile=? AND a.state='committed'
            ORDER BY a.committed_at DESC,a.id DESC''', (pin['source'], pin['profile']))
        return next((row['id'] for row in rows
                     if comparison_scope(row, json.loads(row['spec'])) == pin['comparison_scope']
                     and json.loads(row['metadata']).get('lookup_query') == pin['lookup_query']), None)

    def _snapshot(self, conn, pins):
        result = []
        for pin in pins:
            latest = conn.execute('SELECT id,state FROM attempt WHERE receipt_id=? ORDER BY created_at DESC,id DESC LIMIT 1',
                                  (pin['receipt_id'],)).fetchone()
            result.append({'receipt_id': pin['receipt_id'], 'latest_attempt': latest['id'],
                           'latest_attempt_state': latest['state'], 'accepted_baseline': self._baseline(conn, pin)})
        return result

    def preview_input(self, receipt_id, expected_attempt, entity_kind='unknown', offset=0, limit=20):
        page_parameters(offset, limit)
        pin, records = self._input({'receipt_id': receipt_id, 'attempt_id': expected_attempt, 'entity_kind': entity_kind})
        evidence = [cleanse(record) for record in records]
        counts = {}
        for record in evidence:
            for field, findings in record['field_findings'].items():
                for finding in findings:
                    key = field + ':' + finding
                    counts[key] = counts.get(key, 0) + 1
        # Preserve metadata while bounding only original/comparison field evidence.
        samples = []
        truncated = False
        for record in evidence[offset:offset + limit]:
            item, clipped = sample_record(record, limit)
            truncated |= clipped
            samples.append(item)
        return {'input': pin, 'rule_version': RULE_VERSION, 'total': len(evidence),
                'quality_counts': counts, 'items': samples, 'sample_truncated': truncated,
                'next_offset': offset + limit if offset + limit < len(evidence) else None}

    def create_run(self, payload):
        inputs = payload.get('inputs')
        if not isinstance(inputs, list) or not 2 <= len(inputs) <= 6:
            raise ValueError('Select two to six explicit source interpretations')
        actor, reason = (self.store.required(payload, key) for key in ('actor', 'reason'))
        pins, records = [], []
        for selection in inputs:
            pin, items = self._input(selection)
            pins.append(pin)
            records.extend(items)
        if len({pin['receipt_id'] for pin in pins}) != len(pins):
            raise ValueError('Select each receipt only once')
        if len({pin['source'] for pin in pins}) < 2:
            raise ValueError('Cross-source comparison requires different source namespaces')
        if len(records) > MAX_RECORDS:
            raise ValueError(f'Comparison limit is {MAX_RECORDS} retained address references; narrow the selected inputs')
        with self.store.db() as conn:
            snapshot = self._snapshot(conn, pins)
            if any(item['latest_attempt'] != pin['attempt_id'] or item['latest_attempt_state'] in
                   {'processing', 'failed', 'interrupted', 'rejected'} for item, pin in zip(snapshot, pins)):
                raise Conflict('Selected interpretations changed while inputs were being read; inspect and rerun')
        start = time.perf_counter()
        candidates = generate_candidates(records, MAX_CANDIDATES)
        elapsed = time.perf_counter() - start
        evidence = [cleanse(record) for record in records]
        metrics = {'input_records': len({record['clinician_ref'] for record in records}),
                   'address_references': len(records), 'candidate_count': len(candidates),
                   'elapsed_seconds': elapsed, 'counts': {kind: sum(row['kind'] == kind for row in candidates)
                                                          for kind in ('clinician', 'location')},
                   'notice': 'Rule rankings organize review, not identity probabilities. No links were created.'}
        run_id = uid()
        with self.store.db() as conn:
            conn.execute('BEGIN IMMEDIATE')
            if self._snapshot(conn, pins) != snapshot:
                raise Conflict('Source interpretations or accepted baselines changed during matching; rerun')
            conn.execute('INSERT INTO comparison_run VALUES (?,?,?,?,?,?,?,?,?)',
                (run_id, packed(pins), RULE_VERSION, packed(evidence), packed(snapshot), packed(metrics), actor, reason, now()))
            conn.executemany('INSERT INTO comparison_candidate VALUES (?,?,?,?,?,?)',
                [(row['id'], run_id, row['kind'], row['rank'], int(row['eligible']), packed(row)) for row in candidates])
        return self.run(run_id)

    def run(self, run_id):
        with self.store.db() as conn:
            row = conn.execute('SELECT * FROM comparison_run WHERE id=?', (run_id,)).fetchone()
            if row is None:
                raise KeyError('Comparison run not found')
            result = dict(row)
            for key in ('inputs', 'baseline_snapshot', 'metrics'):
                result[key] = json.loads(result[key])
            result.pop('records')
            snapshot = self._snapshot(conn, result['inputs'])
            result['inputs_fresh'] = snapshot == result['baseline_snapshot']
            result['review_snapshot'] = digest([run_id, snapshot])
            result['notice'] = 'Candidates require explicit review; shared identifiers never merge records.'
        return result

    def runs(self, offset=0, limit=20):
        page_parameters(offset, limit)
        with self.store.db() as conn:
            rows = [dict(row) for row in conn.execute('SELECT id,rule_version,metrics,actor,reason,created_at FROM comparison_run ORDER BY created_at DESC,id DESC LIMIT ? OFFSET ?', (limit, offset))]
            total = conn.execute('SELECT count(*) FROM comparison_run').fetchone()[0]
        for row in rows:
            row['metrics'] = json.loads(row['metrics'])
        return {'items': rows, 'total': total, 'next_offset': offset + limit if offset + limit < total else None}

    @staticmethod
    def _candidate_selection(run_id, records, kind, eligible, reason, search):
        if (kind is not None and (not isinstance(kind, str) or kind not in {'clinician', 'location'})) or (eligible is not None and type(eligible) is not bool):
            raise ValueError('Choose clinician/location kind and a boolean eligible filter')
        if reason is not None and (not isinstance(reason, str) or re.fullmatch(r'[a-z][a-z0-9_]{0,79}', reason) is None):
            raise ValueError('Choose a lowercase evidence reason code of at most 80 characters')
        if search is not None:
            if not isinstance(search, str) or not search.strip() or len(search.strip()) > 100:
                raise ValueError('Search must contain 1 to 100 characters')
            search = search.strip()
        where, params = 'c.run_id=?', [run_id]
        if kind is not None:
            where += ' AND c.kind=?'
            params.append(kind)
        if eligible is not None:
            where += ' AND c.eligible=?'
            params.append(int(eligible))
        if search is not None:
            needle = search.casefold()
            matching_refs = set()
            for record in records:
                fields = record.get('comparison', {})
                if any(needle in value.casefold() for name in ('provider_name', 'npi', 'native_id')
                       if isinstance((value := fields.get(name)), str)):
                    matching_refs.update((record['ref'], record['clinician_ref']))
            # JSON array binding keeps wildcards literal and avoids SQLite's parameter limit.
            refs = json.dumps(sorted(matching_refs))
            where += """ AND (json_extract(c.payload,'$.left') IN (SELECT value FROM json_each(?))
                          OR json_extract(c.payload,'$.right') IN (SELECT value FROM json_each(?)))"""
            params.extend((refs, refs))
        return where, params, search

    @staticmethod
    def _reason_selection(where, params, reason):
        if reason is not None:
            where += """ AND (EXISTS (SELECT 1 FROM json_each(c.payload, '$.agreements') r WHERE r.value=?)
              OR EXISTS (SELECT 1 FROM json_each(c.payload, '$.contradictions') r WHERE r.value=?)
              OR EXISTS (SELECT 1 FROM json_each(c.payload, '$.missing') r WHERE r.value=?))"""
            params = [*params, reason, reason, reason]
        return where, params

    def candidates(self, run_id, kind=None, eligible=None, offset=0, limit=20, reason=None, search=None):
        page_parameters(offset, limit)
        run = self.run(run_id)
        with self.store.db() as conn:
            conn.execute('BEGIN')
            records = json.loads(conn.execute('SELECT records FROM comparison_run WHERE id=?', (run_id,)).fetchone()[0])
            where, params, _ = self._candidate_selection(run_id, records, kind, eligible, reason, search)
            index = {}
            for record in records:
                index[record['ref']] = record
                index.setdefault(record['clinician_ref'], record)
            # UNION deduplicates a code within/across reason arrays for one pair.
            # Facets describe the complete kind/eligibility subset, before paging
            # or applying the selected reason. Reason counts are not additive.
            reason_rows = conn.execute(f"""
                SELECT code, count(*) AS candidate_count FROM (
                  SELECT c.id, r.value AS code FROM comparison_candidate AS c,
                    json_each(c.payload, '$.agreements') AS r WHERE {where}
                  UNION
                  SELECT c.id, r.value AS code FROM comparison_candidate AS c,
                    json_each(c.payload, '$.contradictions') AS r WHERE {where}
                  UNION
                  SELECT c.id, r.value AS code FROM comparison_candidate AS c,
                    json_each(c.payload, '$.missing') AS r WHERE {where}
                ) GROUP BY code ORDER BY code
            """, params * 3).fetchall()
            reason_counts = {row['code']: row['candidate_count'] for row in reason_rows}
            unfiltered_total = conn.execute(f'SELECT count(*) FROM comparison_candidate AS c WHERE {where}', params).fetchone()[0]
            where, params = self._reason_selection(where, params, reason)
            rows = [json.loads(row[0]) for row in conn.execute(
                f"SELECT payload FROM comparison_candidate AS c WHERE {where} ORDER BY c.kind,c.rank DESC,json_extract(c.payload,'$.left'),json_extract(c.payload,'$.right') LIMIT ? OFFSET ?", (*params, limit, offset))]
            total = conn.execute(f'SELECT count(*) FROM comparison_candidate AS c WHERE {where}', params).fetchone()[0]
        for candidate in rows:
            for side in ('left', 'right'):
                record = index[candidate[side]]
                candidate[side + '_record'], clipped = sample_record(record, limit)
                candidate['sample_truncated'] = candidate.get('sample_truncated', False) or clipped
        return {'run_id': run_id, 'inputs_fresh': run['inputs_fresh'], 'review_snapshot': run['review_snapshot'],
                'items': rows, 'total': total, 'unfiltered_total': unfiltered_total, 'reason_counts': reason_counts,
                'next_offset': offset + limit if offset + limit < total else None}

    def export_candidates(self, run_id, kind=None, eligible=None, reason=None, search=None):
        """Complete filtered pair evidence, explicitly distinct from the full run export."""
        metadata = self.run(run_id)
        with self.store.db() as conn:
            conn.execute('BEGIN')
            records = json.loads(conn.execute('SELECT records FROM comparison_run WHERE id=?', (run_id,)).fetchone()[0])
            where, params, search = self._candidate_selection(run_id, records, kind, eligible, reason, search)
            where, params = self._reason_selection(where, params, reason)
            candidates = [json.loads(row[0]) for row in conn.execute(
                f"SELECT c.payload FROM comparison_candidate AS c WHERE {where} ORDER BY c.kind,c.rank DESC,json_extract(c.payload,'$.left'),json_extract(c.payload,'$.right')", params)]
        refs = {candidate[side] for candidate in candidates for side in ('left', 'right')}
        selected_records = [record for record in records if record['ref'] in refs or record['clinician_ref'] in refs]
        return {'run': metadata, 'scope': {'kind': kind, 'eligible': eligible, 'reason': reason, 'search': search},
                'total': len(candidates), 'candidates': candidates, 'records': selected_records,
                'notice': 'Filtered candidate evidence, not a complete run export; identity review history is separate. No provider facts verified.'}

    def export(self, run_id):
        """Complete immutable run evidence; interactive sampling never truncates it."""
        metadata = self.run(run_id)
        with self.store.db() as conn:
            conn.execute('BEGIN')
            records = json.loads(conn.execute('SELECT records FROM comparison_run WHERE id=?', (run_id,)).fetchone()[0])
            candidates = [json.loads(row[0]) for row in conn.execute(
                "SELECT payload FROM comparison_candidate WHERE run_id=? ORDER BY kind,rank DESC,json_extract(payload,'$.left'),json_extract(payload,'$.right')", (run_id,))]
        return {'run': metadata, 'records': records, 'candidates': candidates,
                'notice': 'Retained comparison evidence; identity review history is separate. No provider facts verified.'}
