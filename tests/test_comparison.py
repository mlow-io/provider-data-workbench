"""Rule behavior plus evaluation against truth authored before implementation."""
from copy import deepcopy
from itertools import combinations
import json
from pathlib import Path
from time import perf_counter
import tracemalloc

import pytest

from provider_directory_truth_layer.comparison import RULE_VERSION, cleanse, generate_candidates


def record(ref='a', source='clinic', **changes):
    result = {'ref': ref, 'clinician_ref': ref, 'source': source,
              'entity_kind': 'clinician', 'native_id': ref,
              'provider_name': 'Alex Example', 'npi': '0000000001',
              'phone': '(212) 555-0101', 'phone_extension': None,
              'address': {'line1': '10 Example Street', 'suite': '100',
                          'city': 'Exampleton', 'state': 'MA', 'zip': '02108',
                          'kind': 'practice', 'path': 'addresses[0]'}}
    result.update(changes)
    return result


def test_cleanse_preserves_original_and_metadata_without_aliasing():
    original = record(provider_name='  STRAẞE\u00a0 Éxample ', npi='NA',
                      phone='+1 (212) 555-0101 ext. 004', phone_extension='005',
                      metadata={'literal': [None, '', 'NA']})
    original['address'].update(line1='10 Streetwise Street Suite 04', zip='02108-0004')
    before = deepcopy(original)
    result = cleanse(original)
    assert original == before
    assert result['original_fields'] == before
    assert result['comparison']['provider_name'] == 'strasse éxample'
    assert result['comparison']['address']['line1'] == '10 streetwise st'
    assert result['comparison']['address']['zip'] == '02108-0004'
    assert result['comparison']['address']['zip_base'] == '02108'
    assert result['comparison']['phone'] == '2125550101'
    assert result['comparison']['phone_extension'] == '005'
    assert result['comparison']['derived_phone_extension'] == '004'
    assert result['field_findings']['phone_extension'] == ['extension_conflict']
    assert result['field_findings']['npi'] == ['invalid_npi_shape']
    assert result['rule_version'] == RULE_VERSION
    result['metadata']['literal'].append('changed')
    result['original_fields']['address']['suite'] = 'changed'
    assert original == before


@pytest.mark.parametrize('value', [None, '', '  ', 'NA'])
def test_null_blank_literal_and_failed_phone_retained(value):
    result = cleanse(record(npi=value, phone=value))
    expected = value.strip().casefold() if value is not None else None
    assert result['comparison']['npi'] == expected
    assert result['comparison']['phone'] == expected
    assert result['original_fields']['phone'] == value
    if value == 'NA':
        assert 'invalid_phone_shape' in result['field_findings']['phone']


@pytest.mark.parametrize('phone', ['12125550101', '2125550101 ext unknown', '212/555/0101'])
def test_phone_failures_are_not_guessed(phone):
    result = cleanse(record(phone=phone))
    assert result['comparison']['phone'] == phone
    assert 'invalid_phone_shape' in result['field_findings']['phone']


def test_extension_derived_and_leading_zero_preserved():
    result = cleanse(record(phone='212-555-0101 x004'))
    assert result['comparison']['phone_extension'] == '004'
    assert result['original_fields']['phone_extension'] is None


def pair_candidates(a, b):
    return {item['kind']: item for item in generate_candidates([a, b])}


def test_shared_office_and_phone_do_not_establish_clinician_identity():
    candidates = pair_candidates(record(), record('b', 'payer', npi='0000000002', provider_name='Robin Fixture'))
    assert set(candidates) == {'location'}
    assert candidates['location']['eligible']


@pytest.mark.parametrize('changes,explanation', [
    ({'npi': '0000000002'}, 'npi_conflict'),
    ({'provider_name': 'Different Person'}, 'provider_name_conflict'),
    ({'entity_kind': 'organization'}, 'organization_not_clinician'),
    ({'npi': 'NA'}, 'invalid_npi_shape'),
])
def test_contradictory_identity_is_visible_and_ineligible(changes, explanation):
    a = record(npi='NA') if changes == {'npi': 'NA'} else record()
    candidate = pair_candidates(a, record('b', 'payer', **changes))['clinician']
    assert explanation in candidate['contradictions']
    assert not candidate['eligible']


def test_missing_identifier_and_unknown_type_do_not_agree():
    candidate = pair_candidates(record(npi=None, entity_kind='unknown'),
                                record('b', 'payer', npi=''))['clinician']
    assert 'npi_missing' in candidate['missing']
    assert 'entity_kind_missing' in candidate['missing']
    assert 'npi_equal' not in candidate['agreements']
    assert not candidate['eligible']


def test_distinct_and_missing_suites_are_explained():
    for suite, field, explanation in [('200', 'contradictions', 'suite_conflict'),
                                      (None, 'missing', 'suite_missing')]:
        b = record('b', 'payer')
        b['address']['suite'] = suite
        candidate = pair_candidates(record(), b)['location']
        assert explanation in candidate[field]
        assert not candidate['eligible']


def test_mailing_excluded_unknown_kind_not_eligible():
    b = record('b', 'payer')
    b['address']['kind'] = 'mailing'
    assert set(pair_candidates(record(), b)) == {'clinician'}
    b['address']['kind'] = 'unknown'
    candidate = pair_candidates(record(), b)['location']
    assert not candidate['eligible']
    assert 'practice_kind_missing' in candidate['missing']


def test_address_variants_dedup_only_clinician_and_reordering_is_stable():
    a, b = record(), record('b', 'payer')
    c = deepcopy(b)
    c['ref'] = 'b:second'
    c['address']['path'] = 'addresses[2]'
    c['address']['suite'] = '200'
    before = deepcopy([a, b, c])
    candidates = generate_candidates([a, b, c])
    assert candidates == generate_candidates([c, b, a])
    assert [a, b, c] == before
    assert len([item for item in candidates if item['kind'] == 'clinician']) == 1
    assert len([item for item in candidates if item['kind'] == 'location']) == 2
    assert all(item['left'] != item['right'] for item in candidates)
    c['npi'] = '0000000002'
    with pytest.raises(ValueError, match='Conflicting clinician'):
        generate_candidates([a, b, c])


def test_same_source_exclusion_duplicate_refs_and_complete_output_cap():
    assert generate_candidates([record(), record('b')], max_candidates=0) == []
    with pytest.raises(ValueError, match='cap exceeded'):
        generate_candidates([record(), record('b', 'payer')], max_candidates=1)
    assert len(generate_candidates([record(), record('b', 'payer')], max_candidates=2)) == 2
    with pytest.raises(ValueError, match='Duplicate'):
        generate_candidates([record(), record()])
    with pytest.raises(ValueError, match='nonnegative'):
        generate_candidates([], max_candidates=-1)


def fixture_records(fixture):
    rows = []
    for source, records in fixture['sources'].items():
        for original in records:
            for address in original['native_addresses']:
                rows.append({'ref': original['record_id'] + '/' + address['path'],
                             'clinician_ref': original['record_id'], 'source': source,
                             'native_id': original['source_native_id'],
                             'entity_kind': original['entity_type'],
                             'provider_name': original['name'], 'npi': original['npi'],
                             'phone': original['phone'], 'phone_extension': None,
                             'address': address})
    return rows


def evaluate_fixture(path):
    fixture = json.loads(path.read_text())
    rows = fixture_records(fixture)
    sources = {row['clinician_ref']: row['source'] for row in rows}
    truth = {'clinician': set(), 'location': set()}
    for group in fixture['expected_clinician_links']:
        truth['clinician'].update(tuple(sorted(pair)) for pair in combinations(group['records'], 2)
                                  if sources[pair[0]] != sources[pair[1]])
    for group in fixture['expected_location_links']:
        members = [(member['record'], member['address_path']) for member in group['members']]
        truth['location'].update(tuple(sorted((a + '/' + ap, b + '/' + bp)))
                                 for (a, ap), (b, bp) in combinations(members, 2)
                                 if sources[a] != sources[b])
    tracemalloc.start()
    start = perf_counter()
    candidates = generate_candidates(rows)
    elapsed = perf_counter() - start
    _, peak = tracemalloc.get_traced_memory()
    tracemalloc.stop()
    metrics = {'records': len(rows), 'candidates': len(candidates),
               'seconds': elapsed, 'peak_bytes': peak}
    for kind in truth:
        proposed = {(c['left'], c['right']) for c in candidates if c['kind'] == kind}
        eligible = {(c['left'], c['right']) for c in candidates if c['kind'] == kind and c['eligible']}
        metrics[kind] = {'truth': len(truth[kind]), 'proposed_true': len(proposed & truth[kind]),
                         'missed_true': sorted(truth[kind] - proposed),
                         'incorrect_eligible': sorted(eligible - truth[kind]),
                         'extra_review_candidates': len(proposed - truth[kind])}
    return metrics


@pytest.mark.parametrize('filename', ['reconciliation_challenge.json', 'reconciliation_heldout.json'])
def test_frozen_fixture_candidate_recall_and_measurements(filename):
    metrics = evaluate_fixture(Path(__file__).parent / 'fixtures' / 'onboarding' / filename)
    print(filename, json.dumps(metrics, sort_keys=True))
    for kind in ('clinician', 'location'):
        assert metrics[kind]['missed_true'] == []
    # Record incorrect eligible pairs rather than concealing them behind recall.
    assert metrics['location']['incorrect_eligible'] == []


def test_indexed_unrelated_records_emit_no_candidates():
    rows = []
    for index in range(2000):
        item = record(str(index), 'clinic' if index % 2 else 'payer',
                      npi=f'{index:010d}', provider_name=f'Person {index}')
        item['address']['line1'] = f'{index} Unique St'
        rows.append(item)
    assert generate_candidates(rows, max_candidates=0) == []


def test_ambiguous_names_distinguish_unidentified_records_from_two_offices():
    candidates = generate_candidates([record(), record('a:office2'), record('b', 'payer')])
    assert all('ambiguous_name' not in c['missing'] for c in candidates if c['kind'] == 'clinician')
    candidates = generate_candidates([record(npi=None), record('a:other', npi=None),
                                      record('b', 'payer', npi=None)])
    clinicians = [c for c in candidates if c['kind'] == 'clinician']
    assert len(clinicians) == 2
    assert all('ambiguous_name' in c['missing'] and not c['eligible'] for c in clinicians)


def test_zip_plus_four_retained_and_conflicting_extensions_explained():
    a, b = record(), record('b', 'payer')
    a['address']['zip'] = '02108-0001'
    b['address']['zip'] = '02108-0002'
    candidate = pair_candidates(a, b)['location']
    assert 'zip_base_equal' in candidate['agreements']
    assert 'zip_extension_conflict' in candidate['contradictions']
    assert not candidate['eligible']


def test_candidate_chains_do_not_propose_transitive_clinician_pairs():
    a = record(provider_name='First Person')
    b = record('b', 'payer', provider_name='Second Person')
    c = record('c', 'reference', provider_name='Second Person', npi='0000000002')
    pairs = {(c['left'], c['right']) for c in generate_candidates([a, b, c])
             if c['kind'] == 'clinician'}
    assert pairs == {('a', 'b'), ('b', 'c')}


@pytest.mark.parametrize('unit_line', ['STE 100', 'SUITE 100', 'UNIT 100', '#100', '# 100'])
def test_native_second_address_line_explicit_unit_matches_canonical(unit_line):
    native = record('native', 'public_reference')
    native['address'].update(line1='10 Example St', line2=unit_line, suite=None)
    before = deepcopy(native)
    canonical = record()
    candidate = pair_candidates(canonical, native)['location']
    assert candidate['eligible']
    assert 'suite_equal' in candidate['agreements']
    result = cleanse(native)
    assert result['comparison']['address']['line2'] == unit_line.casefold()
    assert result['comparison']['address']['suite'] == '100'
    assert result['original_fields'] == before
    assert native == before
    assert result['comparison_provenance']['address.suite'] == [{
        'rule': 'explicit_unit_suffix', 'source_field': 'address.line2',
        'original': unit_line, 'comparison_input': unit_line.casefold(), 'value': '100'}]


def test_inline_suite_is_removed_only_from_comparison_street_with_provenance():
    native = record('native', 'reference')
    native['address'].update(line1='10 Example Street, Suite 04', suite=None)
    canonical = record()
    canonical['address']['suite'] = '04'
    assert pair_candidates(canonical, native)['location']['eligible']
    cleaned = cleanse(native)
    assert cleaned['original_fields']['address']['line1'] == '10 Example Street, Suite 04'
    assert cleaned['comparison']['address']['line1'] == '10 example st'
    assert cleaned['comparison']['address']['suite'] == '04'
    assert cleaned['comparison_provenance']['address.line1'][0]['value'] == '10 example street'
    native['address']['line1'] = '10 Example Street, Suite 40'
    candidate = pair_candidates(canonical, native)['location']
    assert not candidate['eligible']
    assert 'suite_conflict' in candidate['contradictions']


def test_explicit_suite_conflicts_with_second_line_and_cannot_link_location():
    native = record('native', 'reference')
    native['address'].update(line2='STE 100', suite='200')
    canonical = record()
    canonical['address']['suite'] = '200'
    result = cleanse(native)
    assert result['comparison']['address']['suite'] == '200'
    assert result['comparison']['address']['line2'] == 'ste 100'
    assert 'suite_assertion_conflict' in result['field_findings']['address.suite']
    candidate = pair_candidates(canonical, native)['location']
    assert 'suite_equal' in candidate['agreements']
    assert 'suite_assertion_conflict' in candidate['contradictions']
    assert not candidate['eligible']


@pytest.mark.parametrize('line2', ['100', 'West Building', 'NA', 'West Building STE 100'])
def test_unknown_second_line_retained_and_vetoes_location(line2):
    native = record('native', 'reference')
    native['address']['line2'] = line2
    result = cleanse(native)
    assert result['comparison']['address']['line2'] == line2.casefold()
    assert result['original_fields']['address']['line2'] == line2
    assert 'line2_unknown' in result['field_findings']['address.line2']
    candidate = pair_candidates(record(), native)['location']
    assert 'line2_unknown' in candidate['missing']
    assert not candidate['eligible']


def test_inline_and_second_line_unit_disagreement_retains_both_assertions():
    native = record('native', 'reference')
    native['address'].update(line1='10 Example St #04', line2='UNIT 40', suite=None)
    cleaned = cleanse(native)
    assert cleaned['comparison']['address']['suite'] == '04'
    assert [step['value'] for step in cleaned['comparison_provenance']['address.suite']] == ['04', '40']
    assert 'suite_assertion_conflict' in cleaned['field_findings']['address.suite']


@pytest.mark.parametrize('label', ['Suite 04', 'STE 04', 'Unit 04', '#04'])
def test_explicit_suite_field_labels_normalize_without_losing_leading_zero(label):
    left, right = record(), record('right', 'payer')
    left['address']['suite'] = '04'
    right['address']['suite'] = label
    cleaned = cleanse(right)
    assert cleaned['comparison']['address']['suite'] == '04'
    assert cleaned['original_fields']['address']['suite'] == label
    assert cleaned['comparison_provenance']['address.suite'][0]['rule'] == 'explicit_suite_label'
    assert pair_candidates(left, right)['location']['eligible']


def test_suite_field_label_does_not_authorize_merging_different_units():
    left, right = record(), record('right', 'payer')
    left['address']['suite'] = '04'
    right['address']['suite'] = 'Suite 40'
    assert not pair_candidates(left, right)['location']['eligible']


@pytest.mark.parametrize(('field', 'value'), [
    ('provider_name', ['Alex Example']), ('provider_name', {'name': 'Alex Example'}),
    ('provider_name', 123), ('npi', True), ('npi', False), ('npi', 1000000001.0),
    ('npi', ['1000000001']), ('native_id', ['row-1']), ('entity_kind', ['clinician']),
])
def test_malformed_identity_fields_preserve_raw_without_identity_agreement(field, value):
    left, right = record(), record('right', 'payer')
    left[field] = deepcopy(value)
    right[field] = deepcopy(value)
    before = deepcopy([left, right])
    cleaned = cleanse(left)
    assert cleaned['original_fields'][field] == value
    assert cleaned['comparison'][field] is None
    assert 'invalid_type' in cleaned['field_findings'][field]
    clinicians = [item for item in generate_candidates([left, right]) if item['kind'] == 'clinician']
    assert all(not item['eligible'] for item in clinicians)
    assert all(field + '_invalid_type' in item['contradictions'] for item in clinicians)
    assert [left, right] == before


@pytest.mark.parametrize(('field', 'value'), [
    ('suite', ['04']), ('suite', {'unit': '04'}), ('suite', 4),
    ('line1', ['10 Example St']), ('line2', ['STE 100']),
    ('city', {'name': 'Boston'}), ('state', ['MA']), ('zip', 2108),
    ('zip', True), ('kind', ['practice']), ('path', ['addresses[0]']),
])
def test_malformed_address_components_cannot_establish_location(field, value):
    left, right = record(), record('right', 'payer')
    left['address'][field] = deepcopy(value)
    right['address'][field] = deepcopy(value)
    before = deepcopy([left, right])
    cleaned = cleanse(left)
    assert cleaned['original_fields']['address'][field] == value
    assert cleaned['comparison']['address'][field] is None
    assert 'invalid_type' in cleaned['field_findings']['address.' + field]
    locations = [item for item in generate_candidates([left, right]) if item['kind'] == 'location']
    assert all(not item['eligible'] for item in locations)
    assert all('address_' + field + '_invalid_type' in item['contradictions'] for item in locations)
    assert [left, right] == before


@pytest.mark.parametrize('value', [[], ['address'], '10 Example Street', False, 10])
def test_non_object_address_is_preserved_and_explained(value):
    left, right = record(address=value), record('right', 'payer', address=deepcopy(value))
    cleaned = cleanse(left)
    assert cleaned['original_fields']['address'] == value
    assert cleaned['field_findings']['address'] == ['invalid_type']
    assert cleaned['comparison']['address']['line1'] is None
    assert not any(item['kind'] == 'location' for item in generate_candidates([left, right]))


@pytest.mark.parametrize('value', [[], {}, True, False, 2125550101, 2125550101.0])
def test_malformed_phone_is_not_coerced_to_comparison_digits(value):
    cleaned = cleanse(record(phone=value))
    assert cleaned['comparison']['phone'] is None
    assert cleaned['original_fields']['phone'] == value
    assert cleaned['field_findings']['phone'] == ['invalid_type']


def test_malformed_explicit_unit_and_extension_do_not_hide_behind_valid_derivation():
    item = record('right', 'payer', phone='2125550101 x004', phone_extension=['004'])
    item['address'].update(suite=['04'], line2='STE 04')
    cleaned = cleanse(item)
    assert cleaned['comparison']['phone_extension'] is None
    assert cleaned['comparison']['derived_phone_extension'] == '004'
    assert cleaned['field_findings']['phone_extension'] == ['invalid_type']
    assert cleaned['comparison']['address']['suite'] is None
    assert 'invalid_type' in cleaned['field_findings']['address.suite']
    candidate = pair_candidates(record(), item)['location']
    assert not candidate['eligible']
    assert 'address_suite_invalid_type' in candidate['contradictions']


def test_integer_native_npi_identifier_is_supported_without_accepting_numeric_zip():
    left, right = record(npi=1000000001, native_id=42), record('right', 'payer', npi='1000000001')
    cleaned = cleanse(left)
    assert cleaned['original_fields']['npi'] == 1000000001
    assert cleaned['comparison']['npi'] == '1000000001'
    assert cleaned['comparison']['native_id'] == '42'
    assert pair_candidates(left, right)['clinician']['eligible']
    assert RULE_VERSION == 'provider-comparison-v4'


@pytest.mark.parametrize('value', [None, [], 'record', True, 42])
def test_record_body_requires_an_object(value):
    with pytest.raises(ValueError, match='record must be an object'):
        cleanse(value)
    with pytest.raises(ValueError, match='record must be an object'):
        generate_candidates([value])


@pytest.mark.parametrize('value', [None, {}, 'records', True])
def test_candidate_input_body_requires_a_list(value):
    with pytest.raises(ValueError, match='records must be a list'):
        generate_candidates(value)


@pytest.mark.parametrize('field', ['ref', 'clinician_ref', 'source'])
@pytest.mark.parametrize('value', [None, '', [], 42])
def test_candidate_reference_fields_require_nonblank_text(field, value):
    item = record()
    item[field] = value
    with pytest.raises(ValueError, match=field + ' must be nonblank text'):
        generate_candidates([item])
