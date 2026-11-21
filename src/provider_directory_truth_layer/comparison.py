"""Pure, versioned comparison evidence and bounded cross-source candidates.

Rank expresses rule priority, never probability. Eligibility means suitable for
explicit review; these functions create no identities or reviewed links.
"""
from __future__ import annotations

from collections import defaultdict
from copy import deepcopy
from hashlib import sha256
from itertools import combinations
import json
import re
import unicodedata

from .normalization_recipes import _apply

RULE_VERSION = 'provider-comparison-v4'
# Whole tokens only. This intentionally does not attempt a postal-address parser.
_STREET_SUFFIXES = {
    'street': 'st', 'st.': 'st', 'avenue': 'ave', 'ave.': 'ave',
    'road': 'rd', 'rd.': 'rd', 'boulevard': 'blvd', 'blvd.': 'blvd',
    'drive': 'dr', 'dr.': 'dr', 'lane': 'ln', 'ln.': 'ln',
    'court': 'ct', 'ct.': 'ct', 'place': 'pl', 'pl.': 'pl',
}


def _text(value):
    if value is None:
        return None
    return ' '.join(unicodedata.normalize('NFC', value).casefold().split())


def _present(value):
    return value is not None and value != ''


# Narrow labeled suffix extraction; unlabeled second lines remain unresolved.
_UNIT_SUFFIX = re.compile(r'(?:^|[\s,]+)(?:(?:ste|suite|unit)\s+|#\s*)([\w/-]+)$')


def _address_units(address, raw_address, finding):
    """Extract only explicit unit labels, retaining source lines and derivations."""
    provenance = {}
    assertions = []
    if _present(address['suite']):
        supplied = address['suite']
        labeled = _UNIT_SUFFIX.fullmatch(supplied)
        if labeled:
            address['suite'] = labeled[1]
            finding('address.suite', 'explicit_suite_label_normalized')
            provenance.setdefault('address.suite', []).append({
                'rule': 'explicit_suite_label', 'source_field': 'address.suite',
                'original': raw_address.get('suite'), 'comparison_input': supplied, 'value': labeled[1]})
        assertions.append(address['suite'])
    for field in ('line1', 'line2'):
        value = address[field]
        match = _UNIT_SUFFIX.search(value) if _present(value) else None
        if match is None:
            if field == 'line2' and _present(value):
                finding('address.line2', 'line2_unknown')
            continue
        suite = match[1]
        prefix = value[:match.start()].strip(' ,')
        assertions.append(suite)
        finding('address.' + field, 'suite_suffix_extracted')
        provenance.setdefault('address.suite', []).append({
            'rule': 'explicit_unit_suffix', 'source_field': 'address.' + field,
            'original': raw_address.get(field), 'comparison_input': value, 'value': suite,
        })
        if field == 'line1':
            # The full source line remains in original_fields and provenance.
            address['line1'] = prefix
            provenance['address.line1'] = [{
                'rule': 'remove_explicit_unit_suffix', 'original': raw_address.get(field),
                'comparison_input': value, 'value': prefix,
            }]
        elif prefix:
            # E.g. "Building West STE 100" supplies a unit but has other text
            # whose location meaning these rules cannot safely interpret.
            finding('address.line2', 'line2_unknown')
    if assertions:
        if not _present(address['suite']):
            address['suite'] = assertions[0]
        if len(set(assertions)) > 1:
            finding('address.suite', 'suite_assertion_conflict')
    return provenance


def cleanse(record: dict) -> dict:
    """Return independent originals, comparison values and per-field findings.

    None, blank and literal NA stay distinct. Failed structural transformations
    retain their normalized literal value and cannot count as valid evidence.
    Invalid JSON field types remain in originals and become None in comparison;
    only string/integer identifiers are accepted, with booleans excluded.
    NPI validation checks ten ASCII digits only, not certification/checksums.
    """
    if not isinstance(record, dict):
        raise ValueError('Comparison record must be an object')
    result = deepcopy(record)
    original = deepcopy(record)
    findings = {}

    def finding(field, code):
        findings.setdefault(field, []).append(code)

    def text_field(field, value, identifier=False):
        # JSON booleans are Python ints; accept only exact int identifiers.
        if value is None or isinstance(value, str):
            return _text(value)
        if identifier and type(value) is int:
            return _text(str(value))
        finding(field, 'invalid_type')
        return None

    comparison = {field: text_field(field, record.get(field), identifier=field in {'npi', 'native_id'})
                  for field in ('provider_name', 'npi', 'native_id', 'phone', 'phone_extension')}
    for field, value in comparison.items():
        if not _present(value) and 'invalid_type' not in findings.get(field, []):
            finding(field, 'null' if value is None else 'blank')
    npi = comparison['npi']
    if _present(npi) and not re.fullmatch(r'[0-9]{10}', npi):
        finding('npi', 'invalid_npi_shape')
    if _present(comparison['phone']):
        try:
            phone, extension = _apply(comparison['phone'], {'op': 'phone_us'})
            comparison['phone'] = phone
            if extension is not None:
                supplied = comparison['phone_extension']
                if _present(supplied) and supplied != extension:
                    finding('phone_extension', 'extension_conflict')
                    comparison['derived_phone_extension'] = extension
                elif not _present(supplied):
                    if 'invalid_type' in findings.get('phone_extension', []):
                        comparison['derived_phone_extension'] = extension
                    else:
                        comparison['phone_extension'] = extension
                        # The original missing field remains inspectable above.
                        findings.pop('phone_extension', None)
        except ValueError:
            finding('phone', 'invalid_phone_shape')
    extension = comparison['phone_extension']
    if _present(extension) and not re.fullmatch(r'[0-9]{1,10}', extension):
        finding('phone_extension', 'invalid_extension_shape')
    raw_address = record.get('address')
    if raw_address is None:
        raw_address = {}
    elif not isinstance(raw_address, dict):
        finding('address', 'invalid_type')
        raw_address = {}
    address = {field: text_field('address.' + field, raw_address.get(field)) for field in (
        'line1', 'line2', 'suite', 'city', 'state', 'zip', 'kind', 'path', 'source_path')}
    provenance = _address_units(address, raw_address, finding)
    if 'invalid_type' in findings.get('address.suite', []):
        address['suite'] = None
    if _present(address['line1']):
        address['line1'] = ' '.join(_STREET_SUFFIXES.get(token, token)
                                    for token in address['line1'].split())
    for field in ('line1', 'suite', 'city', 'state', 'zip'):
        if not _present(address[field]) and 'invalid_type' not in findings.get('address.' + field, []):
            finding('address.' + field, 'null' if address[field] is None else 'blank')
    address['zip_base'] = None
    if _present(address['zip']):
        if re.fullmatch(r'[0-9]{5}(?:-[0-9]{4})?', address['zip']):
            address['zip_base'] = address['zip'][:5]
        else:
            finding('address.zip', 'invalid_zip_shape')
    if address['kind'] != 'practice':
        finding('address.kind', 'mailing_excluded' if address['kind'] == 'mailing'
                else 'unknown_address_kind')
    comparison['address'] = address
    comparison['entity_kind'] = text_field('entity_kind', record.get('entity_kind', 'unknown'))
    if comparison['entity_kind'] not in ('clinician', 'organization'):
        finding('entity_kind', 'unknown_entity_kind')
    result.update(original_fields=original, comparison=comparison,
                  field_findings=findings, comparison_provenance=provenance, rule_version=RULE_VERSION)
    return result


def _valid(record, field):
    value = record['comparison'][field]
    return _present(value) and not any(code.startswith('invalid_')
                                      for code in record['field_findings'].get(field, []))


def _candidate(kind, left, right, ambiguous):
    a, b = left['comparison'], right['comparison']
    agreements, contradictions, missing = [], [], []

    def compare(field, av, bv):
        if not _present(av) or not _present(bv):
            missing.append(field + '_missing')
        elif av == bv:
            agreements.append(field + '_equal')
        else:
            contradictions.append(field + '_conflict')

    relevant_fields = {'provider_name', 'npi', 'native_id', 'entity_kind'} if kind == 'clinician' else {
        'address', 'address.line1', 'address.line2', 'address.suite', 'address.city',
        'address.state', 'address.zip', 'address.kind', 'address.path'}
    for record in (left, right):
        for field in sorted(relevant_fields):
            if 'invalid_type' in record['field_findings'].get(field, []):
                contradictions.append(field.replace('.', '_') + '_invalid_type')

    if kind == 'clinician':
        for field in ('npi', 'provider_name'):
            compare(field, a[field], b[field])
        for record in (left, right):
            if not _valid(record, 'npi') and _present(record['comparison']['npi']):
                contradictions.append('invalid_npi_shape')
        if a['entity_kind'] == b['entity_kind'] == 'clinician':
            agreements.append('entity_kind_clinician')
        elif 'organization' in (a['entity_kind'], b['entity_kind']):
            contradictions.append('organization_not_clinician')
        else:
            missing.append('entity_kind_missing')
        if a['provider_name'] in ambiguous or b['provider_name'] in ambiguous:
            missing.append('ambiguous_name')
        # Native IDs belong to source namespaces, never cross-source evidence.
        if not _valid(left, 'native_id') or not _valid(right, 'native_id'):
            missing.append('native_id_missing')
        eligible = (not contradictions and 'npi_equal' in agreements
                    and 'provider_name_equal' in agreements
                    and 'entity_kind_clinician' in agreements)
        rank = (100 if 'npi_equal' in agreements else 0) + (40 if 'provider_name_equal' in agreements else 0)
    else:
        aa, ba = a['address'], b['address']
        for field in ('line1', 'suite', 'city', 'state', 'zip_base'):
            compare(field, aa[field], ba[field])
        if aa['zip'] != ba['zip']:
            if len(aa['zip'] or '') == len(ba['zip'] or '') == 10:
                contradictions.append('zip_extension_conflict')
            else:
                missing.append('zip_extension_missing')
        if aa['kind'] != 'practice' or ba['kind'] != 'practice':
            missing.append('practice_kind_missing')
        for record in (left, right):
            if 'suite_assertion_conflict' in record['field_findings'].get('address.suite', []):
                contradictions.append('suite_assertion_conflict')
            if 'line2_unknown' in record['field_findings'].get('address.line2', []):
                missing.append('line2_unknown')
        # Location phone discrepancies remain evidence, not identity vetoes.
        if _valid(left, 'phone') and _valid(right, 'phone'):
            compare('phone', a['phone'], b['phone'])
        else:
            missing.append('phone_missing_or_invalid')
        compare('phone_extension', a['phone_extension'], b['phone_extension'])
        for record in (left, right):
            for field in ('phone', 'phone_extension'):
                if 'invalid_type' in record['field_findings'].get(field, []):
                    missing.append(field + '_invalid_type')
        eligible = (not any(code.endswith('_invalid_type') or code.startswith(('suite_', 'zip_extension_'))
                            for code in contradictions)
                    and 'suite_equal' in agreements
                    and 'line2_unknown' not in missing
                    and aa['kind'] == ba['kind'] == 'practice')
        rank = 80 + (20 if 'suite_equal' in agreements else 0)
    ref_field = 'clinician_ref' if kind == 'clinician' else 'ref'
    refs = sorted((left[ref_field], right[ref_field]))
    identity = json.dumps([RULE_VERSION, kind, *refs], separators=(',', ':'))
    return {'id': sha256(identity.encode()).hexdigest(), 'kind': kind,
            'left': refs[0], 'right': refs[1], 'agreements': sorted(set(agreements)),
            'contradictions': sorted(set(contradictions)), 'missing': sorted(set(missing)),
            'rank': rank, 'eligible': eligible, 'rule_version': RULE_VERSION}


def generate_candidates(records: list[dict], max_candidates: int = 10000) -> list[dict]:
    """Index NPI/name and street/city/state/base-ZIP blocks, then explain pairs.

    Unrelated rows are never compared. Dense blocks still inherently contain
    quadratic output; exceeding the complete-output cap raises instead of
    returning an undisclosed partial list. Source namespace strings are opaque.
    """
    if type(max_candidates) is not int or max_candidates < 0:
        raise ValueError('max_candidates must be a nonnegative integer')
    if not isinstance(records, list):
        raise ValueError('Comparison records must be a list of objects')
    rows = [cleanse(record) for record in records]
    for record in rows:
        for field in ('ref', 'clinician_ref', 'source'):
            if not isinstance(record.get(field), str) or not record[field].strip():
                raise ValueError(f'Comparison {field} must be nonblank text')
    refs = set()
    clinicians = {}
    blocks = {'clinician': defaultdict(list), 'location': defaultdict(list)}
    names_by_source = defaultdict(set)
    for record in sorted(rows, key=lambda row: row['ref']):
        if record['ref'] in refs:
            raise ValueError('Duplicate retained address ref')
        refs.add(record['ref'])
        cref = record['clinician_ref']
        if cref in clinicians:
            previous = clinicians[cref]
            fields = ('provider_name', 'npi', 'entity_kind')
            if (previous['source'] != record['source'] or any(
                    previous['comparison'][field] != record['comparison'][field] for field in fields)):
                raise ValueError('Conflicting clinician evidence across address variants')
        else:
            clinicians[cref] = record
            for field in ('npi', 'provider_name'):
                value = record['comparison'][field]
                if _present(value):
                    blocks['clinician'][(field, value)].append(record)
            name = record['comparison']['provider_name']
            if _present(name):
                names_by_source[(record['source'], name)].add(
                    ('npi', record['comparison']['npi']) if _valid(record, 'npi')
                    else ('unidentified_record', cref))
        address = record['comparison']['address']
        key = tuple(address[field] for field in ('line1', 'city', 'state', 'zip_base'))
        if address['kind'] != 'mailing' and all(_present(value) for value in key):
            blocks['location'][key].append(record)
    ambiguous = {name for (_, name), members in names_by_source.items() if len(members) > 1}
    candidates = {}
    for kind, index in blocks.items():
        ref_field = 'clinician_ref' if kind == 'clinician' else 'ref'
        for block in index.values():
            # Group by namespace so large one-source blocks don't scan pairs.
            sources = defaultdict(list)
            for row in block:
                sources[row['source']].append(row)
            for source_left, source_right in combinations(sorted(sources), 2):
                for left in sources[source_left]:
                    for right in sources[source_right]:
                        pair = (kind, *sorted((left[ref_field], right[ref_field])))
                        if pair in candidates:
                            continue
                        if len(candidates) >= max_candidates:
                            raise ValueError('Candidate cap exceeded; select narrower inputs or raise max_candidates')
                        candidates[pair] = _candidate(kind, left, right, ambiguous)
    return sorted(candidates.values(), key=lambda candidate: (
        candidate['kind'], -candidate['rank'], candidate['left'], candidate['right']))
