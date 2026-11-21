"""Retained interpretation records and native address selectors for comparison.

References identify retained evidence, never inferred business identities.
"""
from __future__ import annotations

import hashlib
import json
from copy import deepcopy


def reference(attempt_id, locator, path=''):
    return hashlib.sha256(json.dumps([attempt_id, locator, path], ensure_ascii=False).encode()).hexdigest()


def entity_evidence(original, profile):
    aliases = {'person': 'clinician', 'individual': 'clinician', 'clinician': 'clinician',
               'organization': 'organization', 'npi-1': 'clinician', 'npi-2': 'organization', 'unknown': 'unknown'}
    evidence={key:deepcopy(original[key]) for key in ('entity_type','enumeration_type') if key in original}
    kinds={aliases.get(value.strip().casefold(),'unknown') for value in evidence.values() if isinstance(value,str)}-{'unknown'}
    if profile == 'cms':
        evidence['adapter_entity_kind']='clinician'
        kinds.add('clinician')  # The explicit clinician/enrollment/address dataset.
    return evidence,kinds


def entity_kind(original, profile, declared='unknown'):
    if not isinstance(declared, str) or declared not in {'unknown', 'clinician', 'organization'}:
        raise ValueError('Declare unknown, clinician or organization entity kind')
    _,kinds=entity_evidence(original,profile)
    if len(kinds)>1:
        if declared!='unknown':
            raise ValueError('Declared entity kind conflicts with contradictory retained source evidence')
        return 'unknown'
    known=next(iter(kinds),'unknown')
    if declared != 'unknown' and known != 'unknown' and declared != known:
        raise ValueError('Declared entity kind conflicts with retained source evidence')
    return known if known != 'unknown' else declared


def source_addresses(original, normalized, profile):
    if isinstance(original.get('native_addresses'), list):
        addresses = original['native_addresses']
        practices = [item for item in addresses if isinstance(item, dict) and item.get('kind') == 'practice']
        selected = original.get('selected_address')
        selected = selected if isinstance(selected, dict) else {}
        for index, item in enumerate(addresses):
            if not isinstance(item, dict):
                yield {'line1': None, 'line2': None, 'suite': None, 'city': None,
                       'state': None, 'zip': None, 'kind': 'unknown', 'path': f'native_addresses[{index}]',
                       'source_error': 'Native address is not an object; retained without inferred components',
                       'phone': None, 'phone_extension': None, 'use_record_phone': False}
                continue
            selected_path = selected.get('path')
            selected_path = selected_path if isinstance(selected_path, str) and selected_path else None
            path_matches = selected_path is not None and selected_path in (item.get('path'), f'native_addresses[{index}]')
            use_root_phone = (item.get('kind') == 'practice' and
                              (path_matches if selected_path is not None else len(practices) == 1))
            yield {'line1': item.get('line1'), 'line2': item.get('line2'), 'suite': item.get('suite'),
                   'city': item.get('city'), 'state': item.get('state'), 'zip': item.get('zip'),
                   'kind': item.get('kind', 'unknown'), 'path': f'native_addresses[{index}]',
                   'source_path': item.get('path'), 'phone': item.get('phone'),
                   'phone_extension': item.get('phone_extension'),
                   'use_record_phone': use_root_phone and 'phone' not in item}
        return
    if profile == 'nppes':
        for collection in ('addresses', 'practiceLocations'):
            for index, item in enumerate(original.get(collection) or []):
                purpose = str(item.get('address_purpose', '')).upper()
                kind = 'practice' if purpose == 'LOCATION' or collection == 'practiceLocations' else 'mailing' if purpose == 'MAILING' else 'unknown'
                yield {'line1': item.get('address_1'), 'line2': item.get('address_2'), 'suite': item.get('suite'),
                       'city': item.get('city'), 'state': item.get('state'), 'zip': item.get('postal_code'),
                       'kind': kind, 'path': f'{collection}[{index}]',
                       'phone': item.get('telephone_number'), 'phone_extension': item.get('phone_extension'),
                       'use_record_phone': False}
        return
    yield {'line1': normalized.get('address'), 'line2': normalized.get('address_line2'),
           'suite': normalized.get('suite'), 'city': normalized.get('city'),
           'state': normalized.get('state'), 'zip': normalized.get('zip'),
           'kind': 'practice' if normalized.get('address') else 'unknown', 'path': '', 'use_record_phone': True}


def make_records(receipt, attempt_id, rows, spec=None, declared='unknown'):
    spec = spec or {}
    if receipt['profile'] == 'fhir-plannet-r4':
        if declared not in {'unknown', 'clinician'}:
            raise ValueError('FHIR practitioner assertions cannot be declared organizations')
        from .fhir_store import comparison_records
        return comparison_records(receipt, attempt_id, rows)
    result = []
    for row in rows:
        original = row['original']
        normalized = deepcopy(row.get('normalized') or {})
        mapping = spec.get('mapping') or {}
        source_fields = {}
        for field in ('npi', 'provider_name', 'phone', 'phone_extension', 'address', 'address_line2', 'suite', 'city', 'state', 'zip'):
            column = mapping.get(field, field)
            if column in original:
                source_fields[field] = deepcopy(original[column])
                # Legacy projection turns JSON null into blank and strips text.
                # Read its explicitly mapped source value for comparative evidence.
                if not spec.get('recipe_revision_id') and receipt['profile'] == 'flat':
                    normalized[field] = deepcopy(original[column])
        if receipt['profile'] == 'nppes' and 'number' in original:
            normalized['npi'] = original['number']
            source_fields['npi'] = original['number']
        locator = row['locator']
        clinician_ref = reference(attempt_id, locator)
        phone = normalized.get('phone')
        # Legacy phone projection can strip extension syntax. Comparison reads the
        # exact explicitly mapped source cell rather than guessing a repair.
        if not spec.get('recipe_revision_id') and receipt['profile'] == 'flat':
            column = spec.get('mapping', {}).get('phone', 'phone')
            if column in original:
                phone = original[column]
        addresses = list(source_addresses(original, normalized, receipt['profile']))
        if not addresses:
            addresses = [{'line1': None, 'suite': None, 'city': None, 'state': None,
                          'zip': None, 'kind': 'unknown', 'path': '', 'use_record_phone': False}]
        for address in addresses:
            result.append({'ref': reference(attempt_id, locator, address['path']),
                'clinician_ref': clinician_ref, 'source': receipt['source'],
                'receipt_id': receipt['id'], 'attempt_id': attempt_id,
                'locator': locator, 'address_path': address['path'],
                'artifact_sha': receipt['artifact_sha'], 'native_id': row.get('native_id'),
                'provider_name': normalized.get('provider_name'), 'npi': normalized.get('npi'),
                'phone': phone if address.get('use_record_phone') else address.get('phone'),
                'phone_extension': normalized.get('phone_extension') if address.get('use_record_phone') else address.get('phone_extension'),
                'source_field_values': source_fields,
                'entity_kind': entity_kind(original, receipt['profile'], declared),
                'entity_kind_evidence': entity_evidence(original, receipt['profile'])[0],
                'entity_kind_conflict': len(entity_evidence(original, receipt['profile'])[1])>1,
                'entity_kind_declaration': declared, 'address': address,
                'network_id': (normalized.get('participation') or {}).get('network_id'),
                'organization_id': (normalized.get('participation') or {}).get('organization_id'),
                'source_location_id': normalized.get('location_id'),
                'source_problems': list(row.get('problems', [])),
                'evaluation_ref': original.get('evaluation_ref')})
    return result
