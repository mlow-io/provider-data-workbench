"""Bounded, declarative intake normalization with inspectable per-field lineage.

Recipes contain data only. Failures retain the pre-operation value and never
invent replacements. The caller owns row locators, persistence and acceptance.
"""
from __future__ import annotations

from copy import deepcopy
from datetime import datetime
import json
import re

# Mirrors intake_store.FIELDS without importing the persistence layer.
FIELDS = frozenset({
    'record_id', 'npi', 'provider_name', 'address', 'city', 'state', 'zip',
    'phone', 'location_id', 'listing_id', 'reference_phone', 'specialty',
    'status', 'source_updated_at', 'phone_extension', 'reference_phone_extension',
    'suite', 'address_line2',
})
_SIMPLE_OPS = frozenset({'trim', 'collapse_spaces', 'uppercase', 'lowercase',
                        'phone_us', 'zip_us', 'state_us'})
_DATE_FORMATS = frozenset({'%m/%d/%Y', '%d/%m/%Y', '%Y-%m-%d'})
_STATES = frozenset(('AL AK AZ AR CA CO CT DE DC FL GA HI ID IL IN IA KS KY LA ME '
                     'MD MA MI MN MS MO MT NE NV NH NJ NM NY NC ND OH OK OR PA RI '
                     'SC SD TN TX UT VT VA WA WV WI WY AS GU MP PR VI').split())
_INTEGER_IDENTIFIERS = frozenset({'npi', 'record_id', 'location_id', 'listing_id'})
_SPECIAL_FIELDS = {'phone_us': {'phone', 'reference_phone'}, 'zip_us': {'zip'},
                   'state_us': {'state'}, 'date': {'source_updated_at'}}


def validate_recipe(definition: dict) -> dict:
    """Return an independent, deterministic recipe or raise ValueError."""
    if not isinstance(definition, dict):
        raise ValueError('Recipe must be an object')
    if set(definition) - {'version', 'mapping', 'transforms', 'required'}:
        raise ValueError('Unknown recipe keys')
    if type(definition.get('version')) is not int or definition['version'] != 1:
        raise ValueError('Recipe version must be 1')
    mapping = definition.get('mapping')
    transforms = definition.get('transforms', {})
    required = definition.get('required', [])
    if not isinstance(mapping, dict) or len(mapping) > 64:
        raise ValueError('Mapping must be an object with at most 64 columns')
    if any(field not in FIELDS for field in mapping):
        raise ValueError('Unknown canonical mapping field')
    if any(not isinstance(col, str) or not col.strip() or len(col) > 256 for col in mapping.values()):
        raise ValueError('Source columns must be nonblank text of at most 256 characters')
    if len(set(mapping.values())) != len(mapping):
        raise ValueError('A source column cannot bind to multiple fields')
    if not isinstance(transforms, dict) or set(transforms) - set(mapping):
        raise ValueError('Transforms must reference mapped fields')
    if (not isinstance(required, list) or any(not isinstance(f, str) or f not in FIELDS for f in required)
            or len(set(required)) != len(required)):
        raise ValueError('Required fields must be unique canonical field names')
    canonical = {}
    for field, operations in sorted(transforms.items()):
        if not isinstance(operations, list) or len(operations) > 32:
            raise ValueError('Each field permits at most 32 operations')
        canonical[field] = []
        for operation in operations:
            operation = {'op': operation} if isinstance(operation, str) else operation
            if not isinstance(operation, dict) or not isinstance(operation.get('op'), str):
                raise ValueError('Operation must be a supported name or object')
            name = operation['op']
            if name in _SIMPLE_OPS and set(operation) == {'op'}:
                result = {'op': name}
            elif (name == 'date' and set(operation) == {'op', 'format'}
                  and isinstance(operation['format'], str) and operation['format'] in _DATE_FORMATS):
                result = {'op': name, 'format': operation['format']}
            else:
                raise ValueError('Unsupported operation or operation arguments')
            if name in _SPECIAL_FIELDS and field not in _SPECIAL_FIELDS[name]:
                raise ValueError(f'{name} cannot transform {field}')
            canonical[field].append(result)
    return {'version': 1, 'mapping': dict(sorted(mapping.items())),
            'transforms': canonical, 'required': sorted(required)}


def _apply(value: str, operation: dict) -> tuple[str, str | None]:
    name = operation['op']
    if name == 'trim':
        return value.strip(), None
    if name == 'collapse_spaces':
        return ' '.join(value.split()), None
    if name == 'uppercase':
        return value.upper(), None
    if name == 'lowercase':
        return value.lower(), None
    # Optional empty cells remain empty, while literal NA is ordinary data.
    if not value.strip():
        return value, None
    if name == 'phone_us':
        match = re.fullmatch(r'\s*(\+1[ .-]?)?([0-9(). -]+?)(?:\s*(?:ext\.?|x|#)\s*([0-9]{1,10}))?\s*', value, re.I)
        if not match:
            raise ValueError('Expected a US phone with optional +1 and explicit extension')
        digits = re.sub(r'[^0-9]', '', match[2])
        # Restrict punctuation to a familiar 10-digit layout, not arbitrary symbols.
        if len(digits) != 10 or not re.fullmatch(r'(?:[0-9]{3}|\([0-9]{3}\))[ .-]?[0-9]{3}[ .-]?[0-9]{4}', match[2].strip()):
            raise ValueError('Expected ten US phone digits; bare country prefixes are ambiguous')
        return digits, match[3]
    if name == 'zip_us':
        candidate = value.strip()
        if not re.fullmatch(r'[0-9]{5}(?:-[0-9]{4})?', candidate):
            raise ValueError('Expected five-digit ZIP or ZIP+4')
        return candidate, None
    if name == 'state_us':
        candidate = value.strip().upper()
        if candidate not in _STATES:
            raise ValueError('Expected a US state or territory abbreviation')
        return candidate, None
    if name == 'date':
        pattern = r'[0-9]{4}-[0-9]{2}-[0-9]{2}' if operation['format'] == '%Y-%m-%d' else r'[0-9]{2}/[0-9]{2}/[0-9]{4}'
        if not re.fullmatch(pattern, value):
            raise ValueError('Date does not match explicit format')
        try:
            return datetime.strptime(value, operation['format']).date().isoformat(), None
        except ValueError:
            raise ValueError('Invalid calendar date for explicit format') from None
    raise ValueError('Unsupported operation')


def transform_row(original: dict, definition: dict) -> dict:
    """Interpret one original object without mutating it or its recipe."""
    recipe = validate_recipe(definition)
    if not isinstance(original, dict):
        raise ValueError('Original row must be an object')
    normalized, provenance, problems = {}, {}, []
    derived_extensions = []
    for field, column in recipe['mapping'].items():
        raw = deepcopy(original.get(column))
        findings, steps = [], []
        if raw is None or isinstance(raw, str):
            value = raw
        elif field in _INTEGER_IDENTIFIERS and type(raw) is int:
            value = str(raw)
        else:
            value = None
            message = ('Expected text or null, or an integer identifier' if field in _INTEGER_IDENTIFIERS
                       else 'Expected text or null')
            findings.append({'code': 'invalid_type', 'message': message})
            problems.append(f'{field}: {message}')
        if column not in original:
            findings.append({'code': 'missing_column', 'message': 'Mapped source column is absent'})
            problems.append(f'{field}: mapped source column is absent')
        for operation in recipe['transforms'].get(field, []):
            before = value
            step_findings = []
            if value is not None:
                try:
                    value, extension = _apply(value, operation)
                    if extension is not None:
                        derived_extensions.append((field, column, raw, extension))
                except ValueError as exc:
                    finding = {'code': 'invalid_transform', 'op': operation['op'], 'message': str(exc)}
                    step_findings.append(finding)
                    findings.append(finding)
                    problems.append(f"{field}: {operation['op']}: {exc}")
            steps.append({'op': deepcopy(operation), 'before': before, 'after': value,
                          'findings': step_findings})
        normalized[field] = value
        provenance[field] = {'source_column': column, 'original': raw, 'value': value,
                             'steps': steps, 'findings': findings}
    for field, column, raw, extension in derived_extensions:
        extension_field = 'reference_phone_extension' if field == 'reference_phone' else 'phone_extension'
        existing = normalized.get(extension_field)
        if any(finding['code'] == 'invalid_type' for finding in provenance.get(extension_field, {}).get('findings', [])):
            # A valid phone suffix cannot repair a malformed supplied value.
            provenance[field]['derived_extension'] = extension
            continue
        if existing is not None and existing.strip() and existing != extension:
            finding = {'code': 'extension_conflict', 'message': 'Derived extension conflicts with another supplied extension',
                       'extension_field': extension_field, 'derived_extension': extension, 'supplied_extension': existing}
            provenance[field]['findings'].append(finding)
            problems.append(f'{field}: derived extension conflicts with another supplied extension')
            continue
        if extension_field not in normalized or existing is None or not existing.strip():
            normalized[extension_field] = extension
            derivation = {'op': {'op': 'phone_us'}, 'before': raw, 'after': extension,
                          'source_column': column, 'findings': []}
            if extension_field in provenance:
                # Preserve even explicitly supplied blank/null originals.
                provenance[extension_field]['value'] = extension
                provenance[extension_field]['steps'].append(derivation)
                provenance[extension_field]['derived_from'] = field
            else:
                provenance[extension_field] = {
                    'source_column': column, 'original': raw, 'value': extension,
                    'steps': [derivation], 'findings': [], 'derived_from': field,
                }
    for field in recipe['required']:
        if normalized.get(field) is None or not normalized[field].strip():
            problems.append(f'{field}: required value is missing')
            if field in provenance:
                provenance[field]['findings'].append({'code': 'required', 'message': 'Required value is missing'})
    return {'normalized': normalized, 'provenance': provenance, 'problems': problems}


def profile_rows(rows: list[dict], headers: list[str], limit: int = 5) -> dict:
    """Count every original row and retain bounded first-seen distinct examples.

    Empty/whitespace strings and null/absent keys are missing; literal NA is not.
    Distinct counts and examples preserve type, null and blank differences.
    """
    if (not isinstance(headers, list) or len(headers) > 64
            or any(not isinstance(h, str) or not h.strip() or len(h) > 256 for h in headers)
            or len(set(headers)) != len(headers)):
        raise ValueError('Headers must contain at most 64 unique nonblank strings')
    if type(limit) is not int or not 0 <= limit <= 20:
        raise ValueError('Example limit must be between 0 and 20')
    columns = []
    for header in headers:
        distinct, examples = set(), []
        absent = null = blank = 0
        for row in rows:
            original = row['original']
            if header not in original:
                absent += 1
                continue
            value = original[header]
            null += value is None
            blank += isinstance(value, str) and not value.strip()
            key = (type(value).__name__, json.dumps(value, ensure_ascii=False, sort_keys=True, allow_nan=False))
            if key not in distinct:
                distinct.add(key)
                if len(examples) < limit:
                    examples.append(deepcopy(value))
        missing = absent + null + blank
        columns.append({'name': header, 'nonempty': len(rows) - missing,
                        'missing': missing, 'distinct_count': len(distinct), 'examples': examples,
                        'absent_count': absent, 'null_count': null, 'blank_count': blank})
    return {'row_count': len(rows), 'columns': columns}
