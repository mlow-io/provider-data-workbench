"""Independent read-only contact consumer for a pinned managed-feed export."""
from __future__ import annotations

import hashlib
import json
import re

MAX_BYTES = 10 * 1024 * 1024
MAX_ROWS = 20_000
ROOT_KEYS = {'version_id', 'manifest', 'report', 'report_hash', 'approval', 'exception_review', 'records', 'quarantine'}
CONTACT_FIELDS = ('record_id', 'location_id', 'npi', 'provider_name', 'address', 'city', 'state', 'zip', 'phone')


def canonical(value):
    """Producer schema-1 canonical JSON, including its default separators."""
    return json.dumps(value, sort_keys=True, ensure_ascii=False, allow_nan=False).encode()


def sha(value):
    return hashlib.sha256(value).hexdigest()


def _pairs(items):
    result = {}
    for key, value in items:
        if key in result:
            raise ValueError('Duplicate JSON key in consumer input')
        result[key] = value
    return result


def _nonfinite(_value):
    raise ValueError('Nonfinite JSON number in consumer input')


def _text(value, name):
    if not isinstance(value, str) or not value.strip():
        raise ValueError(name + ' must be nonblank text')
    return value


def _digest(value, name):
    if not isinstance(value, str) or re.fullmatch(r'[0-9a-f]{64}', value) is None:
        raise ValueError(name + ' must be a lowercase SHA-256 digest')
    return value


def consume(raw: bytes, expected_version: str, *, expected_feed=None, expected_sha=None):
    """Validate supplied bytes; never resolve a current version or open storage."""
    _text(expected_version, 'Expected version')
    if not isinstance(raw, bytes) or not raw or len(raw) > MAX_BYTES:
        raise ValueError('Consumer input must contain 1 byte to 10 MiB')
    input_sha = sha(raw)
    if expected_sha is not None and _digest(expected_sha, 'Expected file digest') != input_sha:
        raise ValueError('Consumer file digest differs from the pinned handoff')
    try:
        data = json.loads(raw, object_pairs_hook=_pairs, parse_constant=_nonfinite)
    except (UnicodeError, RecursionError) as exc:
        raise ValueError('Consumer input is not bounded UTF-8 JSON') from exc
    pending = [(data, 0)]
    nodes = 0
    while pending:
        value, depth = pending.pop(); nodes += 1
        if nodes > 500_000 or depth > 64:
            raise ValueError('Consumer JSON depth/node budget exceeded')
        if isinstance(value, dict):
            pending.extend((child, depth + 1) for child in value.values())
        elif isinstance(value, list):
            pending.extend((child, depth + 1) for child in value)
    if not isinstance(data, dict) or set(data) != ROOT_KEYS:
        raise ValueError('Choose a pinned approved-export payload, not a candidate or version detail')
    if data['version_id'] != expected_version:
        raise ValueError('Consumer version differs from the explicit expected version')
    manifest, approval, report = data['manifest'], data['approval'], data['report']
    if not all(isinstance(item, dict) for item in (manifest, approval, report)):
        raise ValueError('Export manifest, approval and report must be objects')
    if any(type(manifest.get(key)) is not int or manifest[key] != 1 for key in ('output_schema_version', 'policy_version')):
        raise ValueError('Unsupported producer schema or quality policy version')
    feed = _text(manifest.get('feed_id'), 'Feed ID')
    if expected_feed is not None and _text(expected_feed, 'Expected feed') != feed:
        raise ValueError('Consumer feed differs from the explicit expected feed')
    if approval.get('decision') != 'approved' or approval.get('version_id') != expected_version:
        raise ValueError('Only an explicitly approved matching version is consumable')
    for key in ('actor', 'reason', 'created_at'):
        _text(approval.get(key), 'Approval ' + key)
    if manifest.get('designation') not in {'synthetic', 'public', 'local'}:
        raise ValueError('Unknown source designation')
    for key in ('contract_id', 'recipe_revision_id', 'receipt_id', 'attempt_id', 'delivery_id'):
        _text(manifest.get(key), 'Manifest ' + key)
    _digest(manifest.get('artifact_sha'), 'Source artifact digest')
    records, quarantine = data['records'], data['quarantine']
    if (not isinstance(records, list) or not records or not isinstance(quarantine, list)
            or len(records) + len(quarantine) > MAX_ROWS):
        raise ValueError('Consumer requires a nonempty bounded included/excluded row set')
    if _digest(manifest.get('records_sha256'), 'Records digest') != sha(canonical(records)):
        raise ValueError('Included records do not match their producer digest')
    if _digest(data['report_hash'], 'Report digest') != sha(canonical(report)):
        raise ValueError('Quality report does not match its producer digest')
    counts = report.get('counts')
    if (not isinstance(counts, dict) or any(type(counts.get(key)) is not int or counts[key] < 0 for key in ('raw', 'valid', 'quarantined', 'unique'))
            or counts['valid'] != len(records) or counts['quarantined'] != len(quarantine)
            or counts['raw'] != len(records) + len(quarantine) or counts['unique'] > counts['raw']):
        raise ValueError('Quality counts disagree with exported rows')
    findings, reviews = report.get('findings'), data['exception_review']
    if not isinstance(findings, list) or not isinstance(reviews, list):
        raise ValueError('Quality findings and reviews must be lists')
    dispositions = {}
    for review in reviews:
        if not isinstance(review, dict) or review.get('version_id') != expected_version or not isinstance(review.get('code'), str):
            raise ValueError('Exception review belongs to another version or is malformed')
        dispositions[review['code']] = review.get('disposition')
    for finding in findings:
        if not isinstance(finding, dict) or not isinstance(finding.get('code'), str) or finding.get('severity') not in {'hard', 'hold', 'warning'}:
            raise ValueError('Unknown quality finding')
        if finding['severity'] == 'hard':
            raise ValueError('Hard quality blocker cannot be consumed')
        if finding['severity'] == 'hold' and dispositions.get(finding.get('code')) != 'acknowledged':
            raise ValueError('Unacknowledged quality hold cannot be consumed')
    contacts, keys = [], set()
    for record in records:
        if not isinstance(record, dict) or record.get('problems') != [] or not isinstance(record.get('normalized'), dict):
            raise ValueError('Included contact is malformed or quarantined')
        normalized = record['normalized']
        contact = {field: _text(normalized.get(field), 'Contact ' + field) for field in CONTACT_FIELDS}
        if (not re.fullmatch(r'[0-9]{10}', contact['npi']) or not re.fullmatch(r'[0-9]{10}', contact['phone'])
                or not re.fullmatch(r'[0-9]{5}(?:-[0-9]{4})?', contact['zip'])
                or not re.fullmatch(r'[A-Z]{2}', contact['state'])):
            raise ValueError('Contact requires canonical NPI, phone, ZIP and state text; review the producer recipe')
        if 'phone_extension' in normalized:
            extension = normalized['phone_extension']
            if extension is not None and (not isinstance(extension, str) or extension.strip() and not re.fullmatch(r'[0-9]{1,10}', extension)):
                raise ValueError('Contact extension must retain null/blank or canonical digit text')
            contact['phone_extension'] = extension
        key = contact['record_id'], contact['location_id']
        if key in keys:
            raise ValueError('Duplicate source-native record/location key')
        keys.add(key); contacts.append(contact)
    return {'consumer_schema_version': 1, 'version_id': expected_version, 'feed_id': feed,
            'input_sha256': input_sha, 'records_sha256': manifest['records_sha256'], 'report_hash': data['report_hash'],
            'designation': manifest['designation'], 'approval': approval,
            'contacts': sorted(contacts, key=lambda row: (row['record_id'], row['location_id'])),
            'notice': 'Pinned approved source assertions. Approval/digests are not signatures or independent provider verification. Current version and freshness were not queried.'}
