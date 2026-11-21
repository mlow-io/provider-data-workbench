"""Pure, bounded saved-FHIR interpretation. Never performs I/O or approves data.

Structural support checks are deliberately distinct from full profile validation.
Every assertion points to retained resource fields rather than a fabricated row.
"""
from __future__ import annotations

import copy
import hashlib
import re
from collections import defaultdict
from urllib.parse import urlsplit

from .fhir_json import MAX_BYTES, load_fhir_json, walk as _walk

PROFILE = 'fhir-plannet-r4'
VERSION = 'fhir-plannet-r4-v2'
MAX_ENTRIES = 1000
NETWORK_PROFILE = 'http://hl7.org/fhir/us/davinci-pdex-plan-net/StructureDefinition/plannet-Network'
SUPPORTED_NETWORK_PROFILES = {NETWORK_PROFILE, NETWORK_PROFILE + '|1.2.0'}
NETWORK_REFERENCE = 'http://hl7.org/fhir/us/davinci-pdex-plan-net/StructureDefinition/network-reference'
SUPPORTED = {'Practitioner', 'Organization', 'Location', 'PractitionerRole'}


def parse_bundle(payload: bytes) -> dict:
    """Return resources, references, assertions, findings and bounded coverage.

    Invalid envelopes raise ValueError; entry failures remain visible findings.
    A resolved reference is a source relationship, never a reviewed identity link.
    """
    bundle = load_fhir_json(payload, max_bytes=MAX_BYTES)
    if not isinstance(bundle, dict) or bundle.get('resourceType') != 'Bundle' or bundle.get('type') != 'searchset':
        raise ValueError('FHIR intake requires a Bundle with type searchset')
    entries = bundle.get('entry', [])
    if not isinstance(entries, list):
        raise ValueError('Bundle.entry must be an array')
    if len(entries) > MAX_ENTRIES:
        raise ValueError('FHIR entry limit is 1,000; split the artifact')
    result = {'format_version': 1, 'parser_version': VERSION, 'resources': [], 'references': [],
              'assertions': [], 'findings': [],
              'validation': {'structural': 'assessed', 'profile': 'not_run', 'terminology': 'not_run'}}
    findings = result['findings']

    def finding(code, path, message, blocked=True):
        item = {'code': code, 'locator': path, 'message': message,
                'severity': 'error' if blocked else 'warning', 'blocks_projection': blocked}
        findings.append(item)
        return item

    def semantic_checks(value, path):
        """Check shapes used by our projections; retain all unsupported fields."""
        problems = []
        for at, node in _walk(value, path):
            if not isinstance(node, dict):
                continue
            if 'modifierExtension' in node or 'implicitRules' in node:
                problems.append(finding('unsupported_modifier', at,
                                        'Modifier extensions/implicit rules are not interpreted'))
            for key in ('extension', 'modifierExtension', 'telecom', 'coding', *(['identifier'] if at == path else [])):
                if key in node and (not isinstance(node[key], list) or
                                   any(not isinstance(v, dict) for v in node[key])):
                    problems.append(finding('invalid_shape', f'{at}.{key}', 'Expected an array of objects'))
            for key in ('system', 'value', 'use', 'family', 'text', 'city', 'state', 'postalCode', 'country'):
                if key == 'text' and node.get('resourceType') and isinstance(node.get(key), dict):
                    continue  # DomainResource.text is a Narrative, unlike HumanName/CodeableConcept.text.
                if key in node and not isinstance(node[key], str):
                    problems.append(finding('invalid_shape', f'{at}.{key}', 'Expected text'))
            extensions = node.get('extension', [])
            if isinstance(extensions, list):
                for index, extension in enumerate(extensions):
                    if isinstance(extension, dict) and extension.get('url') != NETWORK_REFERENCE:
                        finding('unsupported_extension', f'{at}.extension[{index}]',
                                'Extension is retained without interpretation', False)
            if 'reference' in node and not isinstance(node['reference'], str):
                problems.append(finding('invalid_reference', f'{at}.reference', 'Reference must be text'))
        return problems

    for index, entry in enumerate(entries):
        path = f'$.entry[{index}].resource'
        original = entry.get('resource') if isinstance(entry, dict) else None
        kind = original.get('resourceType') if isinstance(original, dict) else None
        resource = {'locator': path, 'fullUrl': entry.get('fullUrl') if isinstance(entry, dict) else None,
                    'resource_type': kind, 'id': original.get('id') if isinstance(original, dict) else None,
                    'original': copy.deepcopy(original), 'supported': isinstance(kind, str) and kind in SUPPORTED,
                    'problems': []}
        result['resources'].append(resource)
        if not isinstance(original, dict) or not isinstance(kind, str):
            resource['problems'].append(finding('malformed_entry', path, 'Entry requires an object resource with resourceType'))
            continue
        if not resource['supported']:
            code = 'operation_outcome' if kind == 'OperationOutcome' else 'unsupported_resource'
            resource['problems'].append(finding(code, path, f'{kind} is retained without provider interpretation', False))
            continue
        resource['problems'].extend(semantic_checks(original, path))
        for key, expected_type in [('meta', dict), ('address', dict if kind == 'Location' else list),
                                   ('name', list if kind == 'Practitioner' else str),
                                   ('location', list), ('practitioner', dict), ('organization', dict),
                                   ('managingOrganization', dict), ('active', bool), ('status', str)]:
            if key in original and not isinstance(original[key], expected_type):
                resource['problems'].append(finding('invalid_shape', path + '.' + key,
                                                    f'Unsupported {key} shape'))
        if kind == 'Practitioner' and isinstance(original.get('name'), list):
            for name in original['name']:
                if not isinstance(name, dict) or ('given' in name and
                    (not isinstance(name['given'], list) or any(not isinstance(g, str) for g in name['given']))):
                    resource['problems'].append(finding('invalid_shape', path + '.name', 'Invalid HumanName'))
        if kind == 'Location' and isinstance(original.get('address'), dict):
            address = original['address']
            if 'line' in address and (not isinstance(address['line'], list) or any(not isinstance(v, str) for v in address['line'])):
                resource['problems'].append(finding('invalid_shape', path + '.address.line', 'Address lines must be text array'))
        for field in ('fullUrl', 'id'):
            if resource[field] is not None and not isinstance(resource[field], str):
                resource['problems'].append(finding('invalid_shape', path, f'{field} must be text'))
        if kind == 'PractitionerRole' and isinstance(original.get('location'), list) and any(not isinstance(v, dict) for v in original['location']):
            resource['problems'].append(finding('invalid_shape', path + '.location', 'Location references must be objects'))
        meta = original.get('meta')
        if isinstance(meta, dict) and 'profile' in meta and (not isinstance(meta['profile'], list) or any(not isinstance(v, str) for v in meta['profile'])):
            resource['problems'].append(finding('invalid_shape', path + '.meta.profile', 'Profiles must be text array'))
        resource['meta'] = copy.deepcopy(meta) if isinstance(meta, dict) else {}
        resource['eligible'] = not resource['problems']

    # Exact fullUrl takes priority. Relative references are resolved in the origin
    # resource's declared REST base; absent/URN bases use only unambiguous type/id.
    full_index, identity_index = defaultdict(list), defaultdict(list)
    for resource in result['resources']:
        if isinstance(resource['fullUrl'], str):
            full_index[resource['fullUrl']].append(resource)
        if isinstance(resource['id'], str) and isinstance(resource['resource_type'], str):
            identity_index[f"{resource['resource_type']}/{resource['id']}"].append(resource)

    for matches in full_index.values():
        if len(matches) > 1:
            for resource in matches:
                resource['eligible'] = False
                resource['problems'].append(finding('duplicate_full_url', resource['locator'], 'Repeated fullUrl requires explicit version resolution'))

    references_by_path = {}
    for resource in result['resources']:
        original = resource['original']
        if not isinstance(original, dict):
            continue
        for path, node in _walk(original, resource['locator']):
            if not isinstance(node, dict) or not ('reference' in node or 'identifier' in node and re.search(r'\.(?:practitioner|organization|managingOrganization|valueReference|location\[\d+\])$', path)):
                continue
            raw = node.get('reference')
            matches = []
            state = 'unresolved'
            if isinstance(raw, str) and raw and not raw.startswith('#') and '/_history/' not in raw:
                matches = full_index.get(raw, [])
                if not matches and re.fullmatch(r'[A-Za-z]+/[A-Za-z0-9.\-]{1,64}', raw):
                    own = resource['fullUrl']
                    suffix = f"{resource['resource_type']}/{resource['id']}"
                    if isinstance(own, str) and urlsplit(own).scheme in {'http', 'https'} and own.endswith(suffix):
                        matches = full_index.get(own[:-len(suffix)] + raw, [])
                    else:
                        matches = identity_index.get(raw, [])
            if len(matches) == 1:
                state = 'resolved'
            elif len(matches) > 1:
                state = 'ambiguous'
            ref = {'origin': resource['locator'], 'path': path + '.reference', 'raw_target': raw,
                   'state': state, 'target': matches[0]['locator'] if state == 'resolved' else None}
            result['references'].append(ref)
            references_by_path[ref['path']] = ref
            if state != 'resolved':
                finding('reference_' + state, ref['path'], 'Reference has no unique supported within-Bundle target')

    by_locator = {r['locator']: r for r in result['resources']}
    def target(role, path, expected):
        ref = references_by_path.get(role['locator'] + '.' + path + '.reference')
        resolved = by_locator.get(ref['target']) if ref and ref['state'] == 'resolved' else None
        return resolved if resolved and resolved.get('eligible') and resolved['resource_type'] == expected else None

    bundle_blocked = 'modifierExtension' in bundle or 'implicitRules' in bundle
    if bundle_blocked:
        finding('unsupported_modifier', '$', 'Bundle rules/modifiers block all automatic projections')
    for role in result['resources']:
        if role['resource_type'] != 'PractitionerRole' or not role.get('eligible') or bundle_blocked:
            continue
        value = role['original']
        locations = value.get('location', [])
        if len(locations) != 1:
            finding('ambiguous_location_scope', role['locator'], 'Automatic projection requires exactly one role location')
            continue
        practitioner = target(role, 'practitioner', 'Practitioner')
        location = target(role, 'location[0]', 'Location')
        organization = target(role, 'organization', 'Organization') if 'organization' in value else None
        if not practitioner or not location or ('organization' in value and not organization):
            finding('unresolved_role_context', role['locator'], 'Required role context cannot be uniquely projected')
            continue
        extensions = value.get('extension', [])
        networks = [(i, e) for i, e in enumerate(extensions) if e.get('url') == NETWORK_REFERENCE]
        if len(networks) > 1:
            finding('unresolved_network_scope', role['locator'],
                    f'Plan-Net 1.2 subset requires at most one Network reference; received {len(networks)}. No office projection is made for this role')
            continue
        network = target(role, f'extension[{networks[0][0]}].valueReference', 'Organization') if len(networks) == 1 else None
        if networks and (not network or not SUPPORTED_NETWORK_PROFILES.intersection(network['meta'].get('profile', []))):
            finding('unresolved_network_scope', role['locator'], 'Network reference must resolve to an explicit Network profile')
            continue
        person = practitioner['original']
        names = person.get('name', [])
        name = names[0] if len(names) == 1 else {}
        name_value = name.get('text') or ' '.join([*name.get('given', []), name.get('family', '')]).strip() or None
        npi_values = [i.get('value') for i in person.get('identifier', []) if i.get('system') == 'http://hl7.org/fhir/sid/us-npi']
        phones = [(i, t) for i, t in enumerate(location['original'].get('telecom', [])) if t.get('system') == 'phone']
        phone = phones[0][1].get('value') if len(phones) == 1 and not phones[0][1].get('period') and phones[0][1].get('use') in {None, 'work'} else None
        supports = [{'locator': practitioner['locator'], 'path': 'name[0]', 'field': 'provider_name'},
                    {'locator': location['locator'], 'path': 'address', 'field': 'address'},
                    {'locator': role['locator'], 'path': 'location[0].reference', 'field': 'location_context'}]
        if npi_values:
            supports.append({'locator': practitioner['locator'], 'path': 'identifier', 'field': 'npi'})
        if phone:
            supports.append({'locator': location['locator'], 'path': f'telecom[{phones[0][0]}].value', 'field': 'phone'})
        elif phones:
            finding('ambiguous_phone', location['locator'] + '.telecom', 'Multiple or temporally scoped phone values remain unresolved', False)
        if organization:
            supports.append({'locator': organization['locator'], 'path': 'id', 'field': 'organization_context'})
        if network:
            supports.append({'locator': network['locator'], 'path': 'id', 'field': 'network_context'})
        result['assertions'].append({'locator': role['locator'], 'address_path': 'location[0]',
            'clinician_locator': practitioner['locator'], 'location_locator': location['locator'],
            'provider_name': name_value, 'npi': npi_values[0] if len(npi_values) == 1 else None,
            'address': copy.deepcopy(location['original'].get('address', {})), 'phone': phone,
            'network_id': None, 'source_network_reference': networks[0][1]['valueReference'].get('reference') if network else None,
            'supporting_refs': supports, 'rule_version': VERSION,
            'role_active': value.get('active'), 'role_period': copy.deepcopy(value.get('period')),
            'location_status': location['original'].get('status'), 'practitioner_active': person.get('active')})
    result['coverage'] = {'entry_count': len(entries),
        'supported_count': sum(r['supported'] for r in result['resources']),
        'eligible_count': sum(bool(r.get('eligible')) for r in result['resources']),
        'unsupported_count': sum(not r['supported'] and isinstance(r['original'], dict) for r in result['resources']),
        'invalid_count': sum(not r.get('eligible', False) and r['supported'] or not isinstance(r['original'], dict) for r in result['resources']),
        'unresolved_count': sum(r['state'] != 'resolved' for r in result['references']),
        'assertion_count': len(result['assertions']), 'completeness': 'unknown_saved_scope',
        'links': copy.deepcopy(bundle.get('link', []))}
    result['artifact_sha256'] = hashlib.sha256(payload).hexdigest()
    return result
