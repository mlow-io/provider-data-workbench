"""Independent normalization cases: preservation matters as much as formatting."""
from copy import deepcopy
import json
from pathlib import Path

import pytest

from provider_directory_truth_layer.normalization_recipes import profile_rows, transform_row, validate_recipe

FIXTURES = Path(__file__).parent / 'fixtures' / 'onboarding'


def recipe(field='phone', column='raw', operations=None):
    return {'version': 1, 'mapping': {field: column},
            'transforms': {field: operations or ['phone_us']}, 'required': []}


def test_heldout_hand_authored_cases_preserve_originals():
    fixture = json.loads((FIXTURES / 'heldout_normalization.json').read_text())
    for example in fixture['examples']:
        original = deepcopy(example['original'])
        result = transform_row(original, fixture['recipe'])
        assert result['normalized'] == example['expected']
        assert len(result['problems']) == example['problem_count']
        assert original == example['original']
        for field, column in fixture['recipe']['mapping'].items():
            assert result['provenance'][field]['original'] == original[column]


@pytest.mark.parametrize(('raw', 'phone', 'extension'), [
    ('2125550193', '2125550193', None),
    ('(212) 555-0193 x004', '2125550193', '004'),
    ('+1 212.555.0193 #9', '2125550193', '9'),
    ('212-555-0193 ext 18', '2125550193', '18'),
])
def test_explicit_us_phone_and_extension(raw, phone, extension):
    result = transform_row({'raw': raw}, recipe())
    assert not result['problems']
    assert result['normalized']['phone'] == phone
    assert result['normalized'].get('phone_extension') == extension
    assert result['provenance']['phone']['steps'][0]['before'] == raw


@pytest.mark.parametrize('raw', ['12125550193', '+44 2125550193', '2125550193/42',
                                     '(2125550193', 'NA', '212--555-0193', '2125550193 ext'])
def test_ambiguous_or_malformed_phone_is_preserved_with_structured_finding(raw):
    result = transform_row({'raw': raw}, recipe())
    assert result['normalized']['phone'] == raw
    assert result['problems']
    assert result['provenance']['phone']['steps'][0]['findings'][0]['code'] == 'invalid_transform'


def test_explicit_date_format_resolves_ambiguity_and_rejects_invalid_calendar():
    us = recipe('source_updated_at', operations=[{'op': 'date', 'format': '%m/%d/%Y'}])
    eu = recipe('source_updated_at', operations=[{'op': 'date', 'format': '%d/%m/%Y'}])
    assert transform_row({'raw': '03/04/2026'}, us)['normalized']['source_updated_at'] == '2026-03-04'
    assert transform_row({'raw': '03/04/2026'}, eu)['normalized']['source_updated_at'] == '2026-04-03'
    result = transform_row({'raw': '02/30/2026'}, us)
    assert result['normalized']['source_updated_at'] == '02/30/2026'
    assert result['problems']


def test_blank_null_literal_na_and_leading_zeros_are_distinct():
    definition = {'version': 1, 'mapping': {'npi': 'id', 'zip': 'zip'},
                  'transforms': {'zip': ['zip_us']}, 'required': ['npi']}
    assert transform_row({'id': 'NA', 'zip': '00501'}, definition)['normalized'] == {'npi': 'NA', 'zip': '00501'}
    assert not transform_row({'id': 'NA', 'zip': '00501'}, definition)['problems']
    for raw in (None, '', ' '):
        result = transform_row({'id': raw, 'zip': raw}, definition)
        assert result['provenance']['npi']['original'] == raw
        assert len(result['problems']) == 1


def test_deterministic_recipe_and_repeat_no_mutation():
    definition = recipe('provider_name', operations=['trim', 'collapse_spaces', 'uppercase'])
    canonical = validate_recipe(definition)
    assert validate_recipe(canonical) == canonical
    original = {'raw': '  Alex   Example  ', 'unknown': '=IMPORT("evil")'}
    before = deepcopy((original, definition))
    assert transform_row(original, definition) == transform_row(original, canonical)
    assert transform_row(original, definition)['normalized']['provider_name'] == 'ALEX EXAMPLE'
    assert (original, definition) == before


@pytest.mark.parametrize('definition', [
    {'version': True, 'mapping': {}},
    {'version': 2, 'mapping': {}},
    {'version': 1, 'mapping': {}, 'python': 'print(1)'},
    {'version': 1, 'mapping': {'unknown': 'raw'}},
    {'version': 1, 'mapping': {'phone': 'raw', 'npi': 'raw'}},
    {'version': 1, 'mapping': {'phone': 'raw'}, 'transforms': {'zip': ['trim']}},
    recipe(operations=['__import__("os").system("echo bad")']),
    recipe(operations=[{'op': 'trim', 'sql': 'DROP TABLE intake'}]),
    recipe(operations=[{'op': 'date', 'format': '%x'}]),
    recipe(operations=['trim'] * 33),
    recipe('npi', operations=['phone_us']),
    {'version': 1, 'mapping': {}, 'required': ['sql']},
    {'version': 1, 'mapping': {}, 'required': ['npi', 'npi']},
])
def test_strict_recipe_rejects_unknown_or_unbounded_instructions(definition):
    with pytest.raises(ValueError):
        validate_recipe(definition)


def test_profile_counts_all_rows_with_bounded_distinct_examples_and_unknown_headers():
    values = [None, '', ' ', 'NA', '00501', '00501', '=DROP TABLE X']
    rows = [{'original': {'raw': value, 'unknown': 'literal'}, 'locator': {'row': i}}
            for i, value in enumerate(values)]
    rows.append({'original': {}, 'locator': {'row': 99}})
    result = profile_rows(rows, ['raw', 'unknown'], limit=3)
    col = result['columns'][0]
    assert result['row_count'] == 8
    assert col == {'name': 'raw', 'nonempty': 4, 'missing': 4, 'distinct_count': 6,
                   'examples': [None, '', ' '], 'null_count': 1, 'blank_count': 2, 'absent_count': 1}
    assert result['columns'][1]['examples'] == ['literal']
    assert profile_rows(rows, ['raw'], 0)['columns'][0]['examples'] == []
    with pytest.raises(ValueError):
        profile_rows(rows, ['raw'] * 65)
    with pytest.raises(ValueError):
        profile_rows(rows, ['raw'], 100)


def test_missing_column_is_different_from_supplied_null():
    missing = transform_row({}, recipe())
    null = transform_row({'raw': None}, recipe())
    assert missing['problems'] == ['phone: mapped source column is absent']
    assert not null['problems']


def test_extension_conflict_preserves_both_assertions():
    definition = recipe()
    definition['mapping']['phone_extension'] = 'ext'
    result = transform_row({'raw': '2125550193 x007', 'ext': '8'}, definition)
    assert result['normalized']['phone_extension'] == '8'
    assert result['provenance']['phone']['original'] == '2125550193 x007'
    assert result['provenance']['phone_extension']['original'] == '8'
    assert result['problems']


def test_challenge_fixture_has_independently_labeled_location_and_identity_conflicts():
    fixture = json.loads((FIXTURES / 'reconciliation_challenge.json').read_text())
    keys = {f'{source}:{row["key"]}' for source, rows in fixture['sources'].items() for row in rows}
    assert len(fixture['sources']) == 3
    for group in ('expected_links', 'expected_conflicts', 'expected_nonlinks'):
        assert all(set(item['records']) <= keys for item in fixture[group])
    assert {item['field'] for item in fixture['expected_conflicts']} == {'npi', 'phone'}


@pytest.mark.parametrize('supplied', [None, '', ' '])
def test_derived_extension_does_not_erase_explicit_blank_original(supplied):
    definition = recipe()
    definition['mapping']['phone_extension'] = 'ext'
    result = transform_row({'raw': '2125550193 x007', 'ext': supplied}, definition)
    assert result['normalized']['phone_extension'] == '007'
    assert result['provenance']['phone_extension']['original'] == supplied
    assert result['provenance']['phone_extension']['steps'][-1]['source_column'] == 'raw'


def test_failure_retains_pre_operation_value_and_next_operation_has_lineage():
    definition = recipe('state', operations=['trim', 'state_us', 'lowercase'])
    result = transform_row({'raw': '  UNKNOWN  '}, definition)
    steps = result['provenance']['state']['steps']
    assert steps[1]['before'] == steps[1]['after'] == 'UNKNOWN'
    assert steps[1]['findings']
    assert steps[2]['after'] == 'unknown'
    assert result['normalized']['state'] == 'unknown'


def test_profile_does_not_conflate_typed_values_or_evaluate_cell_text():
    literal = '=IMPORT("https://invalid.example/steal")'
    values = [0, False, '0', literal, literal]
    rows = [{'original': {'cell': value}, 'locator': {'row': index}}
            for index, value in enumerate(values)]
    column = profile_rows(rows, ['cell'], 5)['columns'][0]
    assert column['distinct_count'] == 4
    assert column['examples'] == [0, False, '0', literal]
    assert column['nonempty'] == 5


def test_listed_and_reference_phone_extensions_have_separate_values_and_lineage():
    definition = {'version': 1, 'mapping': {'phone': 'Listed', 'reference_phone': 'Requested'},
                  'transforms': {'phone': ['phone_us'], 'reference_phone': ['phone_us']}, 'required': []}
    original = {'Listed': '(212) 555-0100 x001', 'Requested': '+1 (212) 555-0100 ext 009'}
    result = transform_row(original, definition)
    assert result['normalized'] == {'phone': '2125550100', 'phone_extension': '001',
                                    'reference_phone': '2125550100', 'reference_phone_extension': '009'}
    assert not result['problems']
    for field, column in [('phone_extension', 'Listed'), ('reference_phone_extension', 'Requested')]:
        assert result['provenance'][field]['source_column'] == column
        assert result['provenance'][field]['original'] == original[column]
        assert result['provenance'][field]['derived_from'] == field.removesuffix('_extension')


def test_reference_extension_never_becomes_listed_extension():
    result = transform_row({'raw': '2125550100 #007'}, recipe('reference_phone'))
    assert result['normalized'] == {'reference_phone': '2125550100', 'reference_phone_extension': '007'}
    assert 'phone_extension' not in result['provenance']
    assert not result['problems']


def test_reference_extension_conflict_is_scoped_and_preserves_both_source_assertions():
    definition = {'version': 1, 'mapping': {'phone': 'Listed', 'phone_extension': 'Listed ext',
                                           'reference_phone': 'Requested', 'reference_phone_extension': 'Requested ext'},
                  'transforms': {'phone': ['phone_us'], 'reference_phone': ['phone_us']}, 'required': []}
    original = {'Listed': '2125550100 x001', 'Listed ext': '001',
                'Requested': '2125550100 x009', 'Requested ext': '008'}
    result = transform_row(original, definition)
    assert result['normalized']['phone_extension'] == '001'
    assert result['normalized']['reference_phone_extension'] == '008'
    assert len(result['problems']) == 1
    assert result['problems'][0].startswith('reference_phone:')
    finding = result['provenance']['reference_phone']['findings'][0]
    assert finding['extension_field'] == 'reference_phone_extension'
    assert finding['derived_extension'] == '009' and finding['supplied_extension'] == '008'
    assert result['provenance']['reference_phone_extension']['original'] == '008'


@pytest.mark.parametrize('supplied', [None, '', ' '])
def test_reference_extension_derivation_preserves_explicit_empty_source(supplied):
    definition = recipe('reference_phone')
    definition['mapping']['reference_phone_extension'] = 'ext'
    result = transform_row({'raw': '2125550100 x009', 'ext': supplied}, definition)
    assert result['normalized']['reference_phone_extension'] == '009'
    assert result['provenance']['reference_phone_extension']['original'] == supplied
    assert result['provenance']['reference_phone_extension']['derived_from'] == 'reference_phone'


def test_explicit_suite_and_second_line_mapping_preserves_originals_and_leading_zeros():
    definition = {
        'version': 1,
        'mapping': {'suite': 'Office unit', 'address_line2': 'Address continuation'},
        'transforms': {'suite': ['trim'], 'address_line2': ['collapse_spaces']},
        'required': [],
    }
    original = {'Office unit': ' 04 ', 'Address continuation': ' West   Building '}
    before = deepcopy(original)
    result = transform_row(original, definition)
    assert result['normalized'] == {'suite': '04', 'address_line2': 'West Building'}
    assert result['provenance']['suite']['original'] == ' 04 '
    assert result['provenance']['address_line2']['original'] == ' West   Building '
    assert result['problems'] == []
    assert original == before


@pytest.mark.parametrize('value', [None, '', 'NA', '04'])
def test_optional_address_component_literal_fidelity(value):
    definition = {'version': 1, 'mapping': {'suite': 'unit', 'address_line2': 'line2'},
                  'transforms': {}, 'required': []}
    result = transform_row({'unit': value, 'line2': value}, definition)
    assert result['normalized'] == {'suite': value, 'address_line2': value}
    assert result['provenance']['suite']['original'] == value
    assert result['provenance']['address_line2']['original'] == value
    assert not result['problems']


@pytest.mark.parametrize(('field', 'value'), [
    ('provider_name', ['Alex']), ('provider_name', {'name': 'Alex'}),
    ('provider_name', 123), ('provider_name', True),
    ('address', ['10 Example St']), ('address_line2', {'building': 'West'}),
    ('suite', ['04']), ('suite', 4), ('city', 0), ('state', False),
    ('zip', 2108), ('phone', 2125550101), ('phone_extension', 7),
    ('npi', True), ('npi', False), ('npi', 1000000001.0), ('npi', []),
    ('record_id', {}), ('location_id', True), ('listing_id', 42.0),
])
def test_recipe_invalid_types_are_quarantined_without_fabricated_text(field, value):
    definition = {'version': 1, 'mapping': {field: 'raw'},
                  'transforms': {field: ['trim']}, 'required': []}
    original = {'raw': deepcopy(value)}
    before = deepcopy(original)
    result = transform_row(original, definition)
    assert result['normalized'][field] is None
    assert result['provenance'][field]['original'] == value
    assert result['provenance'][field]['findings'][0]['code'] == 'invalid_type'
    assert result['provenance'][field]['steps'][0]['before'] is None
    assert result['provenance'][field]['steps'][0]['after'] is None
    assert result['problems']
    assert original == before


@pytest.mark.parametrize('field', ['npi', 'record_id', 'location_id', 'listing_id'])
def test_recipe_integer_identifiers_are_explicitly_supported(field):
    definition = {'version': 1, 'mapping': {field: 'raw'}, 'transforms': {}, 'required': []}
    result = transform_row({'raw': 1000000001}, definition)
    assert result['normalized'][field] == '1000000001'
    assert result['provenance'][field]['original'] == 1000000001
    assert not result['problems']


def test_recipe_phone_suffix_does_not_replace_invalid_supplied_extension_type():
    definition = recipe()
    definition['mapping']['phone_extension'] = 'ext'
    result = transform_row({'raw': '2125550193 x007', 'ext': ['007']}, definition)
    assert result['normalized']['phone_extension'] is None
    assert result['provenance']['phone_extension']['original'] == ['007']
    assert result['provenance']['phone_extension']['findings'][0]['code'] == 'invalid_type'
    assert result['provenance']['phone']['derived_extension'] == '007'
    assert result['problems']


@pytest.mark.parametrize(('field', 'value', 'kind'), [
    ('provider_name', ['Alex Example'], 'clinician'),
    ('npi', True, 'clinician'),
    ('suite', ['04'], 'location'),
])
def test_explicit_recipe_cannot_turn_malformed_fields_into_eligible_identity(field, value, kind):
    from provider_directory_truth_layer.comparison import generate_candidates
    original = {'provider_name': 'Alex Example', 'npi': '1000000001', 'suite': '04'}
    original[field] = value
    definition = {'version': 1, 'mapping': {name: name for name in original},
                  'transforms': {}, 'required': []}
    result = transform_row(original, definition)
    records = []
    for source in ('clinic', 'payer'):
        records.append({'ref': source, 'clinician_ref': source, 'source': source,
                        'native_id': source, 'entity_kind': 'clinician',
                        'provider_name': result['normalized']['provider_name'],
                        'npi': result['normalized']['npi'], 'phone': '2125550193',
                        'address': {'line1': '10 Example St', 'suite': result['normalized']['suite'],
                                    'city': 'Boston', 'state': 'MA', 'zip': '02108',
                                    'kind': 'practice', 'path': ''}})
    assert result['problems']
    assert all(not candidate['eligible'] for candidate in generate_candidates(records)
               if candidate['kind'] == kind)
