"""Create immutable roster candidates from explicitly reviewed office phones."""
from __future__ import annotations

import hashlib
import json
import re

from .field_reconciliation import FieldReconciliation
from .intake_store import Conflict, digest, now, packed, uid
from .managed_feed import decode, required
from .reconciliation_store import page_parameters


class FieldMaterialization:
    def __init__(self, store):
        self.store = store
        self.fields = FieldReconciliation(store)

    def _selection(self, conn, base, clinician_id, location_id, snapshot, decision_id, *, view=None):
        if view is None:
            view = self.fields._view(conn, clinician_id, location_id)
        if not view['inputs_fresh'] or view['snapshot'] != snapshot:
            raise Conflict('Reviewed source, link or field snapshot changed; inspect again')
        field = next(f for f in view['fields'] if f['field'] == 'phone')
        decision = field['decision']
        if field['status'] != 'selected' or not decision or decision['id'] != decision_id:
            raise Conflict('A current selected phone decision is required')
        option = next((o for o in field['options'] if o['ref'] == decision['selected_ref'] and o['selectable']), None)
        if not option:
            raise Conflict('Selected source assertion is no longer eligible')
        value = option['comparison_value']
        if not isinstance(value.get('number'), str) or not re.fullmatch(r'[0-9]{10}', value['number']):
            raise ValueError('Selected phone must have ten normalized digits')
        extension = value.get('extension')
        if extension is not None and (not isinstance(extension, str) or not re.fullmatch(r'[0-9]+', extension)):
            raise ValueError('Selected phone extension must contain only digits')
        sha = option['artifact_sha']
        try:
            actual_sha = hashlib.sha256((self.store.artifacts / sha).read_bytes()).hexdigest()
        except OSError as exc:
            raise Conflict('Selected source artifact is unavailable') from exc
        if actual_sha != sha:
            raise Conflict('Selected source artifact digest mismatch')
        # Match through the exact linked base interpretation and locator, never NPI.
        manifest = base['manifest']
        attempt = conn.execute('SELECT preview FROM attempt WHERE id=?', (manifest['attempt_id'],)).fetchone()
        canonical_attempt = json.loads(attempt['preview']).get('reuses_attempt', manifest['attempt_id'])
        linked = {r['locator'] for r in view['records'] if r['attempt_id'] in {manifest['attempt_id'], canonical_attempt} and r['receipt_id'] == manifest['receipt_id']}
        matches = [r for r in base['rows'] if not r['problems'] and r['locator'] in linked]
        if len(matches) != 1:
            raise ValueError('Reviewed identity must link exactly one eligible row in this dataset version')
        row = matches[0]
        old = {'number': row['normalized'].get('phone'), 'extension': row['normalized'].get('phone_extension')}
        new = {'number': value['number'], 'extension': value.get('extension')}
        if old == new:
            raise ValueError('Selected phone does not change this row')
        return {'clinician_id': clinician_id, 'location_id': location_id, 'field': 'phone',
                'snapshot': snapshot, 'evidence_snapshot': view['evidence_snapshot'],
                'link_ids': sorted(link['id'] for link in view['links']), 'decision_id': decision_id,
                'decision_reason': decision['reason'],
                'selected_ref': decision['selected_ref'], 'selected_evidence': option,
                'row_locator': row['locator'], 'old_value': old, 'new_value': new}

    def choices(self, version_id, offset=0, limit=20):
        page_parameters(offset, limit)
        with self.store.db() as conn:
            conn.execute('BEGIN')
            raw = conn.execute('SELECT * FROM feed_version WHERE id=?', (version_id,)).fetchone()
            if raw is None:
                raise KeyError('Dataset version not found')
            base = decode(raw)
            feed = conn.execute('SELECT current_version FROM feed WHERE id=?', (base['feed_id'],)).fetchone()
            if feed['current_version'] != version_id:
                raise Conflict('Choose the current approved dataset version')
            choices = []
            # Page the latest selected scopes in SQL before reconstructing their evidence.
            scope_query = """FROM reconciled_field_decision d WHERE d.field='phone'
                AND d.location_id IS NOT NULL AND d.decision='select'
                AND NOT EXISTS (SELECT 1 FROM reconciled_field_decision n
                    WHERE n.clinician_id=d.clinician_id AND n.location_id=d.location_id
                    AND n.field=d.field AND n.seq>d.seq)"""
            total = conn.execute('SELECT count(*) ' + scope_query).fetchone()[0]
            scopes = conn.execute('SELECT d.clinician_id,d.location_id ' + scope_query +
                                  ' ORDER BY d.seq LIMIT ? OFFSET ?', (limit, offset)).fetchall()
            for scope in scopes:
                view = self.fields._view(conn, scope['clinician_id'], scope['location_id'])
                field = next(f for f in view['fields'] if f['field'] == 'phone')
                if field['status'] != 'selected':
                    continue
                try:
                    item = self._selection(conn, base, scope['clinician_id'], scope['location_id'], view['snapshot'], field['decision']['id'], view=view)
                except (ValueError, KeyError, Conflict):
                    continue
                item.update(clinician_label=view['clinician']['label'], location_label=view['location']['label'])
                choices.append(item)
            return {'base_version': version_id, 'choices': choices, 'total': total,
                    'next_offset': offset + limit if offset + limit < total else None}

    def assess(self, conn, version_id, clinician_id, location_id, view):
        """Explain whether one reviewed scope can become a candidate of this version."""
        field = next(f for f in view['fields'] if f['field'] == 'phone')
        if field['status'] != 'selected' or not field['decision']:
            return {'status': 'not_selected'}
        base = decode(conn.execute('SELECT * FROM feed_version WHERE id=?', (version_id,)).fetchone())
        try:
            selection = self._selection(conn, base, clinician_id, location_id, view['snapshot'], field['decision']['id'], view=view)
        except ValueError as exc:
            status = 'no_change' if 'does not change' in str(exc) else 'ineligible'
            return {'status': status, 'reason': str(exc)}
        except Conflict as exc:
            return {'status': 'ineligible', 'reason': str(exc)}
        return {'status': 'eligible', 'row_locator': selection['row_locator'],
                'old_value': selection['old_value'], 'new_value': selection['new_value']}

    def create(self, version_id, payload):
        keys = {'clinician_id', 'location_id', 'snapshot', 'decision_id', 'actor', 'reason', 'idempotency_key'}
        if not isinstance(payload, dict) or set(payload) != keys:
            raise ValueError('Supply the exact reviewed scope, snapshot, decision, attribution and request key')
        for key in keys:
            required(payload, key)
        request_hash = digest([version_id, payload])
        marker = 'field-materialization:' + digest(payload['idempotency_key'])
        with self.store.db() as conn:
            conn.execute('BEGIN IMMEDIATE')
            prior = conn.execute('SELECT v.* FROM feed_version v JOIN feed_job j ON j.id=v.job_id JOIN feed_delivery d ON d.id=j.delivery_id WHERE d.source_id=?', (marker,)).fetchone()
            if prior:
                version = decode(prior)
                if version['manifest']['materialization']['request_hash'] != request_hash:
                    raise Conflict('Request key already used with different inputs')
                return version['id']
            raw = conn.execute('SELECT * FROM feed_version WHERE id=?', (version_id,)).fetchone()
            if raw is None:
                raise KeyError('Dataset version not found')
            base = decode(raw)
            feed = conn.execute('SELECT * FROM feed WHERE id=?', (base['feed_id'],)).fetchone()
            approval = conn.execute("SELECT 1 FROM feed_decision WHERE version_id=? AND decision='approved'", (version_id,)).fetchone()
            if not approval or feed['current_version'] != version_id:
                raise Conflict('Base must be the current approved version')
            selection = self._selection(conn, base, payload['clinician_id'], payload['location_id'], payload['snapshot'], payload['decision_id'])
            existing = conn.execute('''SELECT 1 FROM feed_version v JOIN feed_job j ON j.id=v.job_id
                WHERE j.baseline_version=? AND json_extract(v.manifest,'$.materialization.clinician_id')=?
                  AND json_extract(v.manifest,'$.materialization.location_id')=?
                  AND json_extract(v.manifest,'$.materialization.decision_id')=? LIMIT 1''',
                (version_id, payload['clinician_id'], payload['location_id'], payload['decision_id'])).fetchone()
            if existing:
                raise Conflict('This reviewed decision already has a candidate for this base; reuse its original request key')
            source_job = conn.execute('SELECT * FROM feed_job WHERE id=?', (base['job_id'],)).fetchone()
            if json.loads(feed['config'])['contract_id'] != source_job['contract_id'] or feed['revision'] != source_job['config_revision']:
                raise Conflict('Feed configuration changed; reprocess before materialization')
            if hashlib.sha256((self.store.artifacts / base['manifest']['artifact_sha']).read_bytes()).hexdigest() != base['manifest']['artifact_sha']:
                raise ValueError('Retained artifact digest mismatch')
            row = next(r for r in base['rows'] if r['locator'] == selection['row_locator'])
            row['normalized']['phone'] = selection['new_value']['number']
            row['normalized']['phone_extension'] = selection['new_value']['extension']
            lineage = {'base_version': version_id, **selection, 'actor': payload['actor'], 'reason': payload['reason'], 'request_hash': request_hash}
            row['materialization'] = lineage
            manifest = {**base['manifest'], 'baseline_version': version_id, 'materialization': lineage,
                        'records_sha256': digest([r for r in base['rows'] if not r['problems']])}
            report = base['report']
            delivery_id, job_id, candidate_id = uid(), uid(), uid()
            delivery = {**manifest['source_delivery'], 'kind': 'derived_field_candidate', 'base_version': version_id}
            conn.execute('INSERT INTO feed_delivery VALUES (?,?,?,?,?,?)', (delivery_id, base['feed_id'], marker, packed(delivery), manifest['artifact_sha'], now()))
            conn.execute('''INSERT INTO feed_job(id,feed_id,delivery_id,contract_id,config_revision,baseline_version,baseline_attempt_id,receipt_id,attempt_id,state,created_at)
                            VALUES (?,?,?,?,?,?,?,?,?,'succeeded',?)''', (job_id, base['feed_id'], delivery_id, source_job['contract_id'], feed['revision'], version_id, manifest['attempt_id'], manifest['receipt_id'], manifest['attempt_id'], now()))
            conn.execute('INSERT INTO feed_version VALUES (?,?,?,?,?,?,?,?)', (candidate_id, base['feed_id'], job_id, packed(manifest), packed(report), digest(report), packed(base['rows']), now()))
            for review in conn.execute('SELECT * FROM feed_exception WHERE version_id=? ORDER BY id', (version_id,)).fetchall():
                conn.execute('INSERT INTO feed_exception(version_id,code,disposition,actor,reason,created_at) VALUES (?,?,?,?,?,?)', (candidate_id, review['code'], review['disposition'], review['actor'], review['reason'], review['created_at']))
        return candidate_id

    def validate_approval(self, conn, version):
        lineage = version['manifest']['materialization']
        base = decode(conn.execute('SELECT * FROM feed_version WHERE id=?', (lineage['base_version'],)).fetchone())
        actual = self._selection(conn, base, lineage['clinician_id'], lineage['location_id'], lineage['snapshot'], lineage['decision_id'])
        for key, value in actual.items():
            if lineage.get(key) != value:
                raise Conflict('Pinned field materialization evidence changed; create a new candidate')
