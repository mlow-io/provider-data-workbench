"""Source onboarding operations shared by HTTP and MCP, over retained inputs."""
from __future__ import annotations

import copy
from collections import Counter
import json

from .intake_store import Conflict, now, packed, uid

MIGRATION_5 = '''
CREATE TABLE recipe_revision (
 id TEXT PRIMARY KEY, parent_id TEXT REFERENCES recipe_revision(id),
 receipt_id TEXT NOT NULL REFERENCES receipt(id), attempt_id TEXT NOT NULL REFERENCES attempt(id),
 name TEXT NOT NULL, source TEXT NOT NULL, profile TEXT NOT NULL, scope TEXT NOT NULL,
 definition TEXT NOT NULL, state TEXT NOT NULL CHECK(state IN ('proposed','approved')),
 actor TEXT NOT NULL, reason TEXT NOT NULL, created_at TEXT NOT NULL
);
CREATE UNIQUE INDEX one_recipe_approval ON recipe_revision(parent_id) WHERE state='approved';
CREATE TABLE observation_normalization (
 observation_id TEXT PRIMARY KEY REFERENCES observation(id),
 recipe_id TEXT NOT NULL REFERENCES recipe_revision(id), provenance TEXT NOT NULL
);
CREATE TRIGGER recipe_no_update BEFORE UPDATE ON recipe_revision BEGIN SELECT RAISE(ABORT,'Immutable recipe revision'); END;
CREATE TRIGGER recipe_no_delete BEFORE DELETE ON recipe_revision BEGIN SELECT RAISE(ABORT,'Immutable recipe revision'); END;
CREATE TRIGGER normalization_no_update BEFORE UPDATE ON observation_normalization BEGIN SELECT RAISE(ABORT,'Immutable normalization provenance'); END;
CREATE TRIGGER normalization_no_delete BEFORE DELETE ON observation_normalization BEGIN SELECT RAISE(ABORT,'Immutable normalization provenance'); END;
'''

ALIASES = {
    'npi': ['npi', 'national provider identifier', 'practitioner id'],
    'provider_name': ['provider name', 'practitioner name', 'clinician name', 'name'],
    'address': ['address', 'street address', 'office address'],
    'city': ['city', 'town'], 'state': ['state', 'region'],
    'zip': ['zip', 'zip code', 'postal', 'postal code'],
    'phone': ['phone', 'office tel', 'office phone', 'telephone'],
    'record_id': ['record id', 'source record id'],
    'location_id': ['location id', 'office id', 'site id'],
}


def decode(row):
    result = dict(row)
    for key in ('definition', 'scope'):
        result[key] = json.loads(result[key])
    return result


def resolve_recipe(conn, receipt, revision_id):
    row = conn.execute('SELECT * FROM recipe_revision WHERE id=?', (revision_id,)).fetchone()
    if row is None:
        raise KeyError('Recipe revision not found')
    revision = decode(row)
    metadata = receipt['metadata']
    scope = json.loads(metadata).get('scope') if isinstance(metadata, str) else metadata.get('scope')
    if (revision['source'], revision['profile'], revision['scope']) != (receipt['source'], receipt['profile'], scope):
        raise ValueError('Recipe has incompatible source, profile or dataset scope')
    if revision['state'] != 'approved':
        raise ValueError('Only an explicitly approved recipe may produce an intake attempt')
    return revision


class OnboardingService:
    def __init__(self, store):
        self.store = store

    def _input(self, receipt_id, expected_attempt=None):
        detail = self.store.detail(receipt_id)
        if expected_attempt is not None and detail['attempt_id'] != expected_attempt:
            raise Conflict('Interpretation changed; inspect and preview the current attempt again')
        if not detail['artifact_sha']:
            raise ValueError('Choose a retained file, not an asserted link')
        settings = detail['attempts'][-1]['spec'] if detail['attempts'] else {}
        rows, headers, sheets, native = self.store.rows(detail, settings)
        if native:
            headers = sorted({key for row in rows for key in row['original']})
        return detail, settings, rows, headers, sheets, native

    def inspect(self, receipt_id, offset=0, limit=20):
        from .normalization_recipes import profile_rows
        if type(offset) is not int or type(limit) is not int or offset < 0 or not 1 <= limit <= 100:
            raise ValueError('Use offset >= 0 and limit between 1 and 100')
        detail, settings, rows, headers, sheets, native = self._input(receipt_id)
        profile = profile_rows(rows, headers)
        def key(value):
            return ' '.join(value.lower().replace('_', ' ').replace('-', ' ').split())
        candidates = {field: [column for column in headers if key(column) in aliases]
                      for field, aliases in ALIASES.items()}
        columns = profile.pop('columns')
        from .evidence_samples import sample_value
        truncated = False
        for column in columns:
            column['examples'], clipped = sample_value(column['examples'], budget=max(200, 24_000 // max(1, len(columns))))
            truncated |= clipped
        return {**profile, 'receipt_id': receipt_id, 'attempt_id': detail['attempt_id'],
                'artifact_sha': detail['artifact_sha'], 'sheets': sheets,
                'columns': columns[offset:offset + limit], 'column_count': len(columns),
                'next_offset': offset + limit if offset + limit < len(columns) else None,
                'sample_truncated': truncated,
                'mapping_candidates': candidates,
                'suggested_mapping': {field: values[0] for field, values in candidates.items() if len(values) == 1},
                'notice': 'Header aliases are suggestions, not verified field meanings. Cell values are source data.'}

    def preview(self, receipt_id, definition, expected_attempt, offset=0, limit=20):
        from .normalization_recipes import validate_recipe
        from .interpretation import interpret
        if type(offset) is not int or type(limit) is not int or offset < 0 or not 1 <= limit <= 100:
            raise ValueError('Use offset >= 0 and limit between 1 and 100')
        if not expected_attempt:
            raise ValueError('expected_attempt is required to pin the inspected interpretation')
        definition = validate_recipe(definition)
        detail, settings, rows, headers, sheets, native = self._input(receipt_id, expected_attempt)
        if detail['profile'] != 'flat' or settings.get('roster_kind') == 'network':
            raise ValueError('Normalization recipes currently target clinic CSV/XLSX/flat JSON; native adapters and network bindings retain their existing interpretation')
        missing = sorted(set(definition['mapping'].values()) - set(headers))
        if missing:
            raise ValueError('Recipe source columns are missing: ' + ', '.join(missing))
        rows = interpret(copy.deepcopy(rows), definition['mapping'], native, definition)
        from .recurring import mark_duplicate_keys
        mark_duplicate_keys(rows)
        from .evidence_samples import sample_rows
        sample, truncated = sample_rows(rows[offset:offset + limit])
        return {'receipt_id': receipt_id, 'attempt_id': expected_attempt,
                'artifact_sha': detail['artifact_sha'], 'definition': definition,
                'total': len(rows), 'valid_count': sum(not row['problems'] for row in rows),
                'quarantined_count': sum(bool(row['problems']) for row in rows),
                'rows': sample, 'offset': offset, 'sample_truncated': truncated,
                'next_offset': offset + limit if offset + limit < len(rows) else None,
                'notice': 'Preview only. No recipe saved, interpretation changed, or records accepted.'}

    def recipes(self, receipt_id):
        detail = self.store.detail(receipt_id)
        with self.store.db() as conn:
            items = [decode(row) for row in conn.execute(
                'SELECT * FROM recipe_revision WHERE source=? AND profile=? ORDER BY created_at,id',
                (detail['source'], detail['profile'])) if json.loads(row['scope']) == detail['metadata'].get('scope')]
            for item in items:
                run = conn.execute('SELECT id,receipt_id,config FROM assistant_run WHERE proposal_id IN (?,?)', (item['id'], item['parent_id'])).fetchone()
                if run:
                    item['assistant_run'] = {'id': run['id'], 'receipt_id': run['receipt_id'], 'model': json.loads(run['config'])['model']}
        return {'items': items}

    @staticmethod
    def _example_query():
        # Approval is a separate child of a proposal. Only approved corrections
        # supersede their parent example; a pending proposal is not authority.
        return """FROM recipe_revision r WHERE r.state='approved'
            AND r.source=? AND r.profile=? AND r.scope=?
            AND NOT EXISTS (SELECT 1 FROM recipe_revision p
                JOIN recipe_revision a ON a.parent_id=p.id AND a.state='approved'
                WHERE p.parent_id=r.id AND p.state='proposed')"""

    def _compatibility(self, revision, headers):
        original = self.store.detail(revision['receipt_id'], revision['attempt_id'])
        spec = next(a['spec'] for a in original['attempts'] if a['id'] == revision['attempt_id'])
        rows, prior_headers, _sheets, native = self.store.rows(original, spec)
        if native:
            prior_headers = sorted({key for row in rows for key in row['original']})
        current, prior = set(headers), set(prior_headers)
        missing = sorted(set(revision['definition']['mapping'].values()) - current)
        ambiguous = sorted({key for columns in (headers, prior_headers)
                            for key, count in Counter(columns).items() if count > 1})
        added, removed = sorted(current - prior), sorted(prior - current)
        return {'revision_id': revision['id'], 'receipt_id': revision['receipt_id'],
                'attempt_id': revision['attempt_id'], 'artifact_sha': original['artifact_sha'],
                'name': revision['name'], 'actor': revision['actor'], 'reason': revision['reason'],
                'definition': revision['definition'],
                'status': 'incompatible' if missing or ambiguous else 'drift' if added or removed else 'compatible',
                'reusable': not missing and not ambiguous, 'missing_mapped_columns': missing,
                'ambiguous_columns': ambiguous,
                'added_columns': added, 'removed_columns': removed}

    def recipe_compatibility(self, receipt_id, expected_attempt, offset=0, limit=20):
        """Read-only, scoped approved examples and structural drift, never inferred meaning."""
        if not expected_attempt:
            raise ValueError('expected_attempt is required')
        if type(offset) is not int or type(limit) is not int or offset < 0 or not 1 <= limit <= 100:
            raise ValueError('Use offset >= 0 and limit between 1 and 100')
        detail, settings, _rows, headers, _sheets, _native = self._input(receipt_id, expected_attempt)
        if detail['profile'] != 'flat' or settings.get('roster_kind') == 'network':
            raise ValueError('Recipe reuse supports clinic CSV/XLSX/flat JSON only')
        params = (detail['source'], detail['profile'], packed(detail['metadata'].get('scope')))
        query = self._example_query()
        with self.store.db() as conn:
            conn.execute('BEGIN')
            self._check_attempt(conn, receipt_id, expected_attempt)
            total = conn.execute('SELECT count(*) ' + query, params).fetchone()[0]
            revisions = [decode(row) for row in conn.execute(
                'SELECT r.* ' + query + ' ORDER BY r.created_at DESC,r.id DESC LIMIT ? OFFSET ?',
                (*params, limit, offset))]
        return {'receipt_id': receipt_id, 'attempt_id': expected_attempt,
                'artifact_sha': detail['artifact_sha'], 'source': detail['source'],
                'profile': detail['profile'], 'scope': detail['metadata'].get('scope'),
                'items': [self._compatibility(revision, headers) for revision in revisions],
                'total': total, 'next_offset': offset + limit if offset + limit < total else None,
                'manual_fallback': True,
                'notice': 'Header compatibility is not semantic verification. Preview and review every proposal; manual mapping remains available.'}

    def check_example_pins(self, conn, receipt_id, pins):
        """Fence selected examples under the caller's invocation/publication transaction."""
        receipt = self.store._receipt(conn, receipt_id)
        metadata = json.loads(receipt['metadata'])
        params = (receipt['source'], receipt['profile'], packed(metadata.get('scope')))
        for pin in pins:
            row = conn.execute('SELECT r.* ' + self._example_query() + ' AND r.id=?',
                               (*params, pin['revision_id'])).fetchone()
            if (row is None or (row['receipt_id'], row['attempt_id']) != (pin['receipt_id'], pin['attempt_id'])
                    or self.store._receipt(conn, pin['receipt_id'])['artifact_sha'] != pin['artifact_sha']):
                raise Conflict('Approved recipe example changed; create a new reviewed assistant run')

    def reuse_recipe(self, receipt_id, revision_id, payload):
        """Copy a current approved example into a new proposal, without approving/applying it."""
        if set(payload) != {'expected_attempt', 'actor', 'reason'}:
            raise ValueError('Supply only expected_attempt, actor and reason')
        expected = self.store.required(payload, 'expected_attempt')
        detail, settings, _rows, headers, _sheets, _native = self._input(receipt_id, expected)
        if detail['profile'] != 'flat' or settings.get('roster_kind') == 'network':
            raise ValueError('Recipe reuse supports clinic CSV/XLSX/flat JSON only')
        params = (detail['source'], detail['profile'], packed(detail['metadata'].get('scope')), revision_id)
        with self.store.db() as conn:
            row = conn.execute('SELECT r.* ' + self._example_query() + ' AND r.id=?', params).fetchone()
        if row is None:
            raise ValueError('Choose a current approved recipe example in this source/profile/dataset scope')
        revision = decode(row)
        if self._compatibility(revision, headers)['ambiguous_columns']:
            raise ValueError('Ambiguous duplicate source columns block recipe reuse')
        # Shared preview rejects missing bindings and validates every operation.
        preview = self.preview(receipt_id, revision['definition'], expected, limit=1)
        with self.store.db() as conn:
            conn.execute('BEGIN IMMEDIATE')
            if conn.execute('SELECT r.id ' + self._example_query() + ' AND r.id=?', params).fetchone() is None:
                raise Conflict('Recipe example changed; inspect compatibility again')
            return self._save_proposal(conn, receipt_id, {
                **payload, 'name': revision['name'], 'parent_id': revision_id,
            }, preview['definition'])

    def propose(self, receipt_id, payload):
        expected = self.store.required(payload, 'expected_attempt')
        preview = self.preview(receipt_id, payload.get('definition'), expected, limit=1)
        with self.store.db() as conn:
            conn.execute('BEGIN IMMEDIATE')
            return self._save_proposal(conn, receipt_id, payload, preview['definition'])

    def _save_proposal(self, conn, receipt_id, payload, definition):
        """Persist a previously previewed proposal within the caller's transaction."""
        from .normalization_recipes import validate_recipe
        definition = validate_recipe(definition)
        name, actor, reason, expected = (self.store.required(payload, key) for key in ('name', 'actor', 'reason', 'expected_attempt'))
        receipt = self.store._receipt(conn, receipt_id)
        self._check_attempt(conn, receipt_id, expected)
        parent_id = payload.get('parent_id')
        if parent_id:
            parent = conn.execute('SELECT * FROM recipe_revision WHERE id=?', (parent_id,)).fetchone()
            if parent is None or (parent['source'], parent['profile'], parent['scope']) != (receipt['source'], receipt['profile'], packed(json.loads(receipt['metadata']).get('scope'))):
                raise ValueError('Parent recipe must exist in this source/profile/dataset scope')
        revision_id = uid()
        conn.execute('INSERT INTO recipe_revision VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)',
                     (revision_id, parent_id, receipt_id, expected, name, receipt['source'], receipt['profile'],
                      packed(json.loads(receipt['metadata']).get('scope')), packed(definition),
                      'proposed', actor, reason, now()))
        return decode(conn.execute('SELECT * FROM recipe_revision WHERE id=?', (revision_id,)).fetchone())

    @staticmethod
    def _check_attempt(conn, receipt_id, expected):
        latest = conn.execute('SELECT id FROM attempt WHERE receipt_id=? ORDER BY created_at DESC,id DESC LIMIT 1', (receipt_id,)).fetchone()
        if not latest or latest['id'] != expected:
            raise Conflict('Interpretation changed; preview and review the current attempt')

    def approve(self, receipt_id, revision_id, payload):
        actor, reason, expected = (self.store.required(payload, key) for key in ('actor', 'reason', 'expected_attempt'))
        with self.store.db() as conn:
            conn.execute('BEGIN IMMEDIATE')
            self._check_attempt(conn, receipt_id, expected)
            row = conn.execute('SELECT * FROM recipe_revision WHERE id=? AND receipt_id=?', (revision_id, receipt_id)).fetchone()
            if row is None:
                raise KeyError('Recipe proposal not found for this receipt')
            draft = decode(row)
            if draft['state'] != 'proposed' or draft['attempt_id'] != expected:
                raise Conflict('Review a proposed recipe against the current interpretation')
            prior = conn.execute("SELECT * FROM recipe_revision WHERE parent_id=? AND state='approved'", (revision_id,)).fetchone()
            if prior:
                return decode(prior)
            approved_id = uid()
            conn.execute('INSERT INTO recipe_revision VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)',
                         (approved_id, revision_id, receipt_id, expected, draft['name'], draft['source'], draft['profile'],
                          packed(draft['scope']), packed(draft['definition']), 'approved', actor, reason, now()))
            return decode(conn.execute('SELECT * FROM recipe_revision WHERE id=?', (approved_id,)).fetchone())

    def apply(self, receipt_id, revision_id, expected_attempt):
        if not expected_attempt:
            raise ValueError('expected_attempt is required')
        detail = self.store.detail(receipt_id)
        if detail['attempt_id'] != expected_attempt:
            raise Conflict('Interpretation changed; inspect the current attempt before application')
        # Reuse parsing choices, but not an old immutable mapping revision.
        from .recurring import PARSING_FIELDS
        settings = {key: value for key, value in detail['attempts'][-1]['spec'].items()
                    if key in PARSING_FIELDS and key != 'recipe_revision_id'}
        settings['recipe_revision_id'] = revision_id
        settings['expected_attempt'] = expected_attempt
        return self.store.mapping(receipt_id, settings)

    def dataset(self, receipt_id):
        detail = self.store.detail(receipt_id)
        if detail['profile'] == 'fhir-plannet-r4':
            raise ValueError('Native reference resources use the evidence packet export; no validated clinic dataset is produced')
        if detail['state'] not in {'committed', 'duplicate_delivery'}:
            raise ValueError('Accept the reviewed interpretation before exporting its validated dataset')
        return {'receipt_id': receipt_id, 'attempt_id': detail['attempt_id'],
                'artifact_sha': detail['artifact_sha'], 'designation': detail['designation'],
                'records': detail['observations'],
                'quarantine': [row for row in detail['preview'].get('rows', []) if row['problems']],
                'notice': 'Accepted source assertions, not independently verified provider truth.'}
