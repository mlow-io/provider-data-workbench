"""Native reference intake using the existing receipt/attempt ledger.

No clinic validation, case generation, network binding or dataset promotion is
performed here. All durable operations use the caller's configured store.
"""
from __future__ import annotations

import hashlib
import json

from .fhir_intake import PROFILE, VERSION, parse_bundle
from .intake_store import Conflict, digest, now, packed, uid


def interpret(store, receipt_id, settings):
    settings = dict(settings)
    expected = settings.pop('expected_attempt', None)
    if settings:
        raise ValueError('FHIR resources do not support clinic mappings or recipes')
    with store.db() as conn:
        receipt = store._receipt(conn, receipt_id)
        metadata = json.loads(receipt['metadata'])
        if metadata.get('managed_feed_id'):
            raise ValueError('FHIR reference evidence is not a managed clinic feed')
    spec = {'profile': PROFILE, 'adapter_version': VERSION, 'native_projection_version': VERSION}
    fingerprint = digest([receipt['source'], metadata.get('scope'), receipt['artifact_sha'], spec])
    attempt_id = uid()
    with store.db() as conn:
        conn.execute('BEGIN IMMEDIATE')
        if expected is not None:
            latest = conn.execute('SELECT id FROM attempt WHERE receipt_id=? ORDER BY created_at DESC,id DESC LIMIT 1', (receipt_id,)).fetchone()
            if latest is None or latest['id'] != expected:
                raise Conflict('Interpretation changed; inspect the current attempt')
        conn.execute('INSERT INTO attempt VALUES (?,?,?,?,?,?,?,?,?)',
                     (attempt_id, receipt_id, packed(spec), fingerprint, 'processing', '{}', now(), None, None))
    try:
        payload = (store.artifacts / receipt['artifact_sha']).read_bytes()
        if hashlib.sha256(payload).hexdigest() != receipt['artifact_sha']:
            raise ValueError('Retained artifact digest mismatch')
        native = parse_bundle(payload)
        preview = preview_from_native(native)
    except (ValueError, OSError) as exc:
        preview = {'state': 'failed', 'error': str(exc), 'rows': [], 'headers': [], 'sheets': [],
                   'mapping': {}, 'total': 0, 'valid_count': 0, 'quarantined_count': 0}
    with store.db() as conn:
        conn.execute('UPDATE attempt SET state=?,preview=? WHERE id=?', (preview['state'], packed(preview), attempt_id))
    return store.detail(receipt_id)


def accept(store, conn, receipt, payload):
    """Accept a native attempt under the caller's BEGIN IMMEDIATE transaction."""
    allowed = {'expected_attempt', 'policy', 'actor', 'reason', 'request_id'}
    if set(payload) - allowed:
        raise ValueError('Unsupported native acceptance fields')
    for key in ('actor', 'reason', 'request_id', 'expected_attempt'):
        if not isinstance(payload.get(key), str) or not payload[key].strip() or len(payload[key]) > 2000:
            raise ValueError(key + ' must be nonblank text within 2000 characters')
    if payload.get('policy') not in {'reference_resources', 'reject'}:
        raise ValueError('FHIR acceptance requires reference_resources or reject')
    if json.loads(receipt['metadata']).get('managed_feed_id'):
        raise ValueError('FHIR evidence cannot promote a managed clinic dataset')
    intent = digest(payload)
    # Request IDs are scoped to one receipt; retries survive subsequent reprocessing.
    prior = conn.execute('SELECT id,decision FROM attempt WHERE receipt_id=? AND decision IS NOT NULL', (receipt['id'],)).fetchall()
    for old in prior:
        decision = json.loads(old['decision'])
        if decision.get('request_id') == payload['request_id']:
            if decision.get('intent_hash') != intent:
                raise Conflict('Request ID already used with different acceptance content')
            return old['id']
    attempt = conn.execute('SELECT * FROM attempt WHERE receipt_id=? ORDER BY created_at DESC,id DESC LIMIT 1', (receipt['id'],)).fetchone()
    if attempt is None or attempt['id'] != payload['expected_attempt']:
        raise Conflict('Interpretation changed; review the current preview')
    if attempt['decision'] is not None:
        raise Conflict('Attempt already has a terminal decision')
    preview = json.loads(attempt['preview'])
    reject = payload['policy'] == 'reject'
    if not reject and (attempt['state'] != 'preview_ready' or not preview.get('valid_count')):
        raise ValueError('No eligible reference resources to accept')
    state = 'rejected' if reject else 'committed'
    previous = conn.execute("SELECT id FROM attempt WHERE fingerprint=? AND state='committed' LIMIT 1", (attempt['fingerprint'],)).fetchone()
    if not reject and previous:
        state = 'duplicate_delivery'
        preview['reuses_attempt'] = previous['id']
    elif not reject:
        for row in preview['rows']:
            if row['problems']:
                continue
            conn.execute('INSERT INTO observation VALUES (?,?,?,?,?,?,?,?,?,?,?)',
                         (uid(), attempt['id'], row['native_id'], row['locator'], packed(row['original']),
                          packed(row['normalized']), None, None, row.get('source_updated_at'), receipt['received_at'], None))
    decision = {**payload, 'intent_hash': intent}
    conn.execute('UPDATE attempt SET state=?,preview=?,decision=?,committed_at=? WHERE id=?',
                 (state, packed(preview), packed(decision), now(), attempt['id']))
    return attempt['id']


def comparison_records(receipt, attempt_id, rows):
    from .comparison_inputs import reference
    records = []
    metadata = receipt.get('metadata', {})
    metadata = json.loads(metadata) if isinstance(metadata, str) else metadata
    origins = metadata.get('resource_origins', {})
    for row in rows:
        for assertion in row['normalized'].get('native_assertions', []):
            address = assertion['address']
            lines = address.get('line', [])
            records.append({'ref': reference(attempt_id, assertion['locator'], assertion['address_path']),
                'clinician_ref': reference(attempt_id, assertion['clinician_locator']),
                'source': receipt['source'], 'receipt_id': receipt['id'], 'attempt_id': attempt_id,
                'locator': assertion['locator'], 'address_path': assertion['address_path'],
                'artifact_sha': receipt['artifact_sha'], 'native_id': row['native_id'],
                'provider_name': assertion['provider_name'], 'npi': assertion['npi'], 'phone': assertion['phone'],
                'phone_extension': None, 'entity_kind': 'clinician', 'entity_kind_evidence': {'resourceType': 'Practitioner'},
                'entity_kind_conflict': False, 'entity_kind_declaration': 'clinician',
                'address': {'line1': lines[0] if lines else None, 'line2': ' '.join(lines[1:]) or None,
                            'suite': None, 'city': address.get('city'), 'state': address.get('state'),
                            'zip': address.get('postalCode'), 'kind': 'practice', 'path': assertion['address_path']},
                'network_id': None, 'organization_id': None, 'source_location_id': None,
                'source_network_reference': assertion['source_network_reference'],
                'source_problems': list(row['problems']), 'source_field_values': {},
                'native_validation': {'profile': 'not_run', 'terminology': 'not_run'},
                'supporting_refs': [{**s, 'attempt_id': attempt_id, **({'source_pages': origins[s['locator']]} if s['locator'] in origins else {})} for s in assertion['supporting_refs']]})
    return records


def context_refs(record):
    """Exact retained rows needed to explain a comparison or field decision."""
    result = [(record['attempt_id'], record['locator'])]
    result.extend((ref['attempt_id'], ref['locator']) for ref in record.get('supporting_refs', []))
    return list(dict.fromkeys(result))


def preview_from_native(native):
    rows = []
    for resource in native['resources']:
        original = resource['original']
        meta = resource.get('meta', {})
        row = {'locator': resource['locator'], 'original': original,
               'native_id': f"{resource['resource_type']}/{resource['id']}" if isinstance(resource['id'], str) else None,
               'normalized': {'resource_type': resource['resource_type'], 'source_id': resource['id'],
                              'meta': meta, 'native_assertions': [a for a in native['assertions'] if a['locator'] == resource['locator']]},
               'source_updated_at': meta.get('lastUpdated'),
               'problems': [] if resource.get('eligible') else [p['message'] for p in resource['problems']] or ['Unsupported resource']}
        rows.append(row)
    preview = {'state': 'preview_ready', 'headers': [], 'sheets': [], 'mapping': {}, 'rows': rows,
               'native': native, 'total': len(rows), 'valid_count': sum(not r['problems'] for r in rows),
               'quarantined_count': sum(bool(r['problems']) for r in rows), 'comparison': {}}
    return preview
