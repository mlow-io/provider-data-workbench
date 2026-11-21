"""Validate frozen, manually authored R0 labels; these are not matcher tests.

No reconciliation implementation is imported. Positive labels describe expected
review relationships in a future evaluation, not current application decisions.
"""
from itertools import combinations
import json
from pathlib import Path

import pytest

FIXTURES = Path(__file__).parent / 'fixtures' / 'onboarding'
NAMES = ['reconciliation_challenge.json', 'reconciliation_heldout.json']


def read_fixture(name):
    return json.loads((FIXTURES / name).read_text())


def index_records(fixture):
    return {record['record_id']: record
            for records in fixture['sources'].values() for record in records}


def selected_address(record, selection):
    matches = [address for address in record['native_addresses']
               if address['path'] == selection['address_path']
               and address['index'] == selection['address_index']]
    assert len(matches) == 1, f'Address selector must identify exactly one native address: {selection}'
    return matches[0]


def record_references(value):
    """Find explicit references, including scoped exclusions and native paths."""
    if isinstance(value, dict):
        for key, child in value.items():
            if key in {'record', 'anchor_record'}:
                yield child
            elif key in {'records', 'assessed_records'}:
                yield from child
            else:
                yield from record_references(child)
    elif isinstance(value, list):
        for child in value:
            yield from record_references(child)


@pytest.mark.parametrize('name', NAMES)
def test_manual_truth_has_unique_stable_records_and_complete_references(name):
    fixture = read_fixture(name)
    assert fixture['schema_version'] == 1
    assert 'synthetic' in fixture['designation'].lower()
    assert fixture['label_authoring']['is_matching_output'] is False
    assert fixture['label_authoring']['runtime_identity_ids'] is False
    assert set(fixture['sources']) == {'clinic', 'payer', 'public_reference'}
    records = index_records(fixture)
    assert len(records) == sum(map(len, fixture['sources'].values()))
    for source, rows in fixture['sources'].items():
        assert len({row['key'] for row in rows}) == len(rows)
        for row in rows:
            assert row['record_id'] == f'{source}:{row["key"]}'
            assert row['entity_type'] in {'clinician', 'organization'}
            assert row['source_native_id'] is None or isinstance(row['source_native_id'], str)
            assert row['npi'] is None or isinstance(row['npi'], str)
            addresses = row['native_addresses']
            assert len({a['path'] for a in addresses}) == len(addresses)
            assert len({a['index'] for a in addresses}) == len(addresses)
            for address in addresses:
                assert address['path'] == f'addresses[{address["index"]}]'
                assert address['kind'] in {'practice', 'mailing'}
                assert address['suite'] is None or isinstance(address['suite'], str)
            if row['selected_address'] is not None:
                selected_address(row, {'address_path': row['selected_address']['path'],
                                      'address_index': row['selected_address']['index']})
    assert set(record_references(fixture)) <= set(records)


@pytest.mark.parametrize('name', NAMES)
def test_positive_clinician_location_and_organization_labels_have_separate_grains(name):
    fixture = read_fixture(name)
    records = index_records(fixture)
    for collection, id_field in [('expected_clinician_links', 'clinician_id'),
                                 ('expected_organization_links', 'organization_id'),
                                 ('expected_location_links', 'location_id')]:
        groups = fixture[collection]
        assert len({group[id_field] for group in groups}) == len(groups)
        assert all(group['reason'] for group in groups)
    clinician_members = [ref for group in fixture['expected_clinician_links'] for ref in group['records']]
    assert len(set(clinician_members)) == len(clinician_members)
    assert all(records[ref]['entity_type'] == 'clinician' for ref in clinician_members)
    for group in fixture['expected_organization_links']:
        assert all(records[ref]['entity_type'] == 'organization' for ref in group['records'])
    location_members = []
    for group in fixture['expected_location_links']:
        assert len(group['members']) >= 2
        for member in group['members']:
            address = selected_address(records[member['record']], member)
            assert address['kind'] == 'practice', 'Mailing evidence cannot establish an operating location'
            location_members.append((member['record'], member['address_path'], member['address_index']))
    assert len(set(location_members)) == len(location_members), 'One exact native address cannot label two locations'


@pytest.mark.parametrize('name', NAMES)
def test_positive_negative_and_unresolved_clinician_truth_does_not_contradict_itself(name):
    fixture = read_fixture(name)
    positives = {frozenset(pair) for group in fixture['expected_clinician_links']
                 for pair in combinations(group['records'], 2)}
    negatives = {frozenset(pair) for label in fixture['expected_clinician_nonlinks']
                 for pair in combinations(label['records'], 2)}
    unresolved = {frozenset(pair) for label in fixture['expected_unresolved']
                  if label['scope'] in {'clinician', 'clinician_and_location'}
                  for pair in combinations(label['records'], 2)}
    assert positives and negatives and unresolved
    assert not positives & negatives
    assert not positives & unresolved
    assert not negatives & unresolved
    for collection in ('expected_unresolved', 'expected_clinician_nonlinks', 'expected_location_nonlinks'):
        assert all(len(label['records']) >= 2 and label['reason'] and label['case'] for label in fixture[collection])
    for label in fixture['expected_location_nonlinks']:
        if 'address_selection' in label:
            member = label['address_selection']
            assert member['record'] in label['records']
            assert selected_address(index_records(fixture)[member['record']], member)['kind'] == 'mailing'


@pytest.mark.parametrize('name', NAMES)
def test_phone_change_targets_partition_named_source_scope_without_claiming_unknown_coverage(name):
    fixture = read_fixture(name)
    records = index_records(fixture)
    impact = fixture['impact_case']
    networks = {network['network_id']: network['name'] for network in fixture['networks']}
    clinician = next(group for group in fixture['expected_clinician_links']
                     if group['clinician_id'] == impact['clinician_id'])
    location = next(group for group in fixture['expected_location_links']
                    if group['location_id'] == impact['location_id'])
    location_records = {member['record'] for member in location['members']}
    assert impact['anchor_record'] in clinician['records']
    assert impact['anchor_record'] in location_records
    assert impact['field'] == 'phone' and impact['old_value'] != impact['proposed_value']
    assert records[impact['anchor_record']]['phone'] == impact['old_value']
    partitions = [impact['expected_targets'], impact['expected_unaffected'], impact['expected_not_assessed']]
    memberships = [[item['record'] for item in partition] for partition in partitions]
    all_members = [ref for partition in memberships for ref in partition]
    assert len(all_members) == len(set(all_members))
    assert set(all_members) == set(impact['assessed_records'])
    assert impact['expected_counts'] == dict(zip(
        ['affected', 'unaffected_within_assessed_scope', 'not_assessed'], map(len, partitions)))
    assert set(impact['network_scope']) == {item['network_id'] for item in impact['expected_targets']}
    for target in impact['expected_targets']:
        assert target['record'] in clinician['records'] and target['record'] in location_records
        assert target['network_id'] == records[target['record']]['network_id']
        assert target['network_id'] in networks
        assert 'synthetic' in networks[target['network_id']].lower()
    for ref in all_members:
        assert ref.partition(':')[0] in impact['source_scope']
    assert impact['expected_not_assessed'], 'Unknown identity dependencies must remain visible'


def test_primary_challenge_covers_all_required_r0_cases_with_explicit_native_selections():
    fixture = read_fixture('reconciliation_challenge.json')
    records = index_records(fixture)
    cases = {item['case'] for key in ['expected_unresolved', 'expected_clinician_nonlinks', 'expected_location_nonlinks']
             for item in fixture[key]}
    assert {'same_npi_conflicting_identity', 'organization_vs_clinician',
            'shared_office_distinct_clinicians', 'distinct_suites', 'two_offices_per_clinician',
            'ambiguous_name_missing_identifiers', 'missing_identifier_and_suite', 'mailing_not_practice'} <= cases
    # Explicit fixture facts prevent a case tag alone from pretending to supply coverage.
    assert records['clinic:C1']['npi'] == records['public_reference:R4']['npi']
    assert records['clinic:C1']['name'] != records['public_reference:R4']['name']
    assert records['clinic:C1']['npi'] == records['payer:P6']['npi']
    assert records['payer:P6']['entity_type'] == 'organization'
    assert records['clinic:C4']['npi'] is records['clinic:C5']['npi'] is None
    assert records['clinic:C4']['source_native_id'] is records['clinic:C5']['source_native_id'] is None
    assert records['payer:P9']['source_native_id'] is records['payer:P9']['office'] is None
    assert records['clinic:C4']['name'] == records['clinic:C5']['name']
    assert records['clinic:C1']['native_addresses'] == records['clinic:C3']['native_addresses']
    assert records['clinic:C1']['native_addresses'][0]['suite'] == '100'
    assert records['clinic:C7']['native_addresses'][0]['suite'] == '200'
    assert records['public_reference:R1']['selected_address'] == {'path': 'addresses[1]', 'index': 1}
    assert [a['kind'] for a in records['public_reference:R1']['native_addresses']] == ['mailing', 'practice', 'practice']
    assert {target['record'] for target in fixture['impact_case']['expected_targets']} == {'payer:P1', 'payer:P4'}
    assert {target['network_id'] for target in fixture['impact_case']['expected_targets']} == {'NET-CEDAR', 'NET-PINE'}
    assert 'payer:P2' in {item['record'] for item in fixture['impact_case']['expected_unaffected']}
    assert 'payer:P8' in {item['record'] for item in fixture['impact_case']['expected_not_assessed']}


def test_heldout_is_separately_authored_and_preserves_suite_identifier_text():
    challenge = read_fixture('reconciliation_challenge.json')
    heldout = read_fixture('reconciliation_heldout.json')
    baseline_records, heldout_records = index_records(challenge), index_records(heldout)
    assert challenge['fixture_id'] != heldout['fixture_id']
    assert not set(baseline_records) & set(heldout_records)
    assert not {r['name'] for r in baseline_records.values()} & {r['name'] for r in heldout_records.values()}
    assert not {a['line1'] for r in baseline_records.values() for a in r['native_addresses']} & {
        a['line1'] for r in heldout_records.values() for a in r['native_addresses']}
    assert heldout_records['clinic:H-C1']['native_addresses'][0]['suite'] == '04'
    assert heldout_records['clinic:H-C3']['native_addresses'][0]['suite'] == '40'
    assert heldout_records['public_reference:H-R1']['selected_address'] == {'path': 'addresses[0]', 'index': 0}
