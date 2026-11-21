import copy
import hashlib
import json
from pathlib import Path

import pytest

from provider_directory_truth_layer import fhir_intake as fhir

FIXTURES = Path(__file__).parent / 'fixtures/intake/fhir-plannet'


def bundle():
    return json.loads((FIXTURES / 'north-south.json').read_bytes())


def parse(value):
    return fhir.parse_bundle(json.dumps(value).encode())


def test_authored_office_expectations_and_complete_resource_lineage():
    payload = (FIXTURES / 'north-south.json').read_bytes()
    expected = json.loads((FIXTURES / 'expected.json').read_bytes())
    result = fhir.parse_bundle(payload)
    assert result['artifact_sha256'] == hashlib.sha256(payload).hexdigest()
    assert result['coverage']['entry_count'] == expected['resource_entries']
    assert result['coverage']['supported_count'] == expected['supported_resource_entries']
    assert result['coverage']['unsupported_count'] == expected['unsupported_resource_entries']
    assert result['coverage']['assertion_count'] == 2
    assert result['validation']['profile'] == result['validation']['terminology'] == 'not_run'
    for assertion, office in zip(result['assertions'], expected['office_assertions']):
        assert assertion['phone'] == office['phone_original']
        assert assertion['address']['postalCode'] == '02108'
        assert assertion['network_id'] is None
        assert assertion['npi'] is None
        assert assertion['clinician_locator'] == office['clinician_locator']
        assert assertion['locator'] == office['role_locator']
        phone = next(s for s in assertion['supporting_refs'] if s['field'] == 'phone')
        assert phone['locator'] + '.' + phone['path'] == office['phone_path']
    assert [r['path'] for r in result['references'] if r['state'] != 'resolved'] == expected['unresolved_reference_paths']
    for source, retained in zip(bundle()['entry'], result['resources']):
        assert source['resource'] == retained['original']


@pytest.mark.parametrize('payload', [b'', b'\xff', b'[]', b'{}', b'{broken',
    b'{"resourceType":"Bundle","type":"collection"}',
    b'{"resourceType":"Bundle","type":"searchset","entry":null}',
    b'{"resourceType":"Bundle","type":"searchset","entry":[],"entry":[]}',
    b'{"resourceType":"Bundle","type":"searchset","total":NaN}'])
def test_invalid_envelope_is_not_an_empty_success(payload):
    with pytest.raises(ValueError):
        fhir.parse_bundle(payload)


def test_empty_search_and_limits_are_distinct(monkeypatch):
    assert parse({'resourceType': 'Bundle', 'type': 'searchset'})['coverage']['entry_count'] == 0
    with pytest.raises(ValueError, match='1,000'):
        parse({'resourceType': 'Bundle', 'type': 'searchset', 'entry': [{}] * 1001})
    monkeypatch.setattr(fhir, 'MAX_BYTES', 2)
    with pytest.raises(ValueError, match='10 MiB'):
        fhir.parse_bundle(b'{} ')


def test_duplicate_target_does_not_pick_last_value_or_project_north():
    value = bundle()
    duplicate = copy.deepcopy(value['entry'][3])
    duplicate['resource']['telecom'][0]['value'] = '617-555-9999'
    value['entry'].append(duplicate)
    result = parse(value)
    assert any(r['state'] == 'ambiguous' for r in result['references'])
    assert [a['phone'] for a in result['assertions']] == ['617-555-0200']
    assert result['resources'][-1]['original']['telecom'][0]['value'] == '617-555-9999'


@pytest.mark.parametrize('reference', ['https://evil.invalid/Location/north', '#contained',
                                     'Location/north/_history/1', 'http://127.0.0.1/secret'])
def test_external_contained_and_versioned_references_are_never_fetched(reference):
    value = bundle()
    value['entry'][5]['resource']['location'][0]['reference'] = reference
    result = parse(value)
    assert [a['phone'] for a in result['assertions']] == ['617-555-0200']
    assert any(r['raw_target'] == reference and r['state'] == 'unresolved' for r in result['references'])


def test_relative_reference_cannot_cross_rest_base():
    value = bundle()
    value['entry'][3]['fullUrl'] = 'https://other.invalid/fhir/Location/north'
    assert [a['phone'] for a in parse(value)['assertions']] == ['617-555-0200']


def test_urn_full_urls_and_exact_absolute_references():
    value = bundle()
    value['entry'][3]['fullUrl'] = 'urn:uuid:synthetic-north'
    value['entry'][5]['resource']['location'][0]['reference'] = 'urn:uuid:synthetic-north'
    assert len(parse(value)['assertions']) == 2


def test_multi_location_role_and_no_practitioner_do_not_invent_scope():
    value = bundle()
    value['entry'][5]['resource']['location'].append({'reference': 'Location/south'})
    del value['entry'][6]['resource']['practitioner']
    assert parse(value)['assertions'] == []


@pytest.mark.parametrize('where', ['location', 'role', 'practitioner', 'bundle'])
def test_unknown_modifiers_block_affected_projection(where):
    value = bundle()
    target = value if where == 'bundle' else value['entry'][{'location': 3, 'role': 5, 'practitioner': 0}[where]]['resource']
    target['modifierExtension'] = [{'url': 'https://example.invalid/unknown', 'valueBoolean': True}]
    result = parse(value)
    assert len(result['assertions']) == (0 if where in {'bundle', 'practitioner'} else 1)
    assert any(f['code'] == 'unsupported_modifier' for f in result['findings'])


def test_unknown_extension_retained_and_diagnostic_entry_counted():
    value = bundle()
    value['entry'][3]['resource']['extension'] = [{'url': 'https://example.invalid/unknown', 'valueString': 'keep'}]
    value['entry'].extend([42, {'resource': {'resourceType': 'OperationOutcome', 'issue': []}}])
    result = parse(value)
    assert result['coverage']['entry_count'] == 11
    assert result['coverage']['invalid_count'] == 1
    assert result['resources'][3]['original']['extension'][0]['valueString'] == 'keep'
    assert any(f['code'] == 'operation_outcome' for f in result['findings'])


@pytest.mark.parametrize('telecom', [[{'system': 'phone', 'value': '617-555-0100'}, {'system': 'phone', 'value': '617-555-0199'}],
                                   [{'system': 'phone', 'value': '617-555-0100', 'period': {'end': '2020-01-01'}}]])
def test_multiple_or_temporally_scoped_contacts_remain_unresolved(telecom):
    value = bundle()
    value['entry'][3]['resource']['telecom'] = telecom
    result = parse(value)
    assert result['assertions'][0]['phone'] is None
    assert any(f['code'] == 'ambiguous_phone' for f in result['findings'])


@pytest.mark.parametrize('field,bad', [('telecom', 'wrong'), ('address', []), ('meta', []), ('identifier', [1])])
def test_malformed_resource_fields_block_projection_instead_of_crashing(field, bad):
    value = bundle()
    value['entry'][3]['resource'][field] = bad
    result = parse(value)
    assert [a['phone'] for a in result['assertions']] == ['617-555-0200']
    assert any(f['code'] == 'invalid_shape' for f in result['findings'])


def test_input_objects_are_not_modified():
    value = bundle()
    before = copy.deepcopy(value)
    parse(value)
    assert value == before


@pytest.mark.parametrize('index,field', [(0, 'name'), (0, 'identifier'), (2, 'meta'), (3, 'telecom'), (3, 'address'), (5, 'location'), (5, 'extension'), (5, 'practitioner')])
@pytest.mark.parametrize('bad', [None, 42, 'wrong', [None], {'value': []}])
def test_adversarial_shapes_do_not_escape_as_runtime_type_errors(index, field, bad):
    value = bundle()
    value['entry'][index]['resource'][field] = bad
    try:
        result = parse(value)
    except ValueError:
        return  # A bounded envelope/structure rejection is also explicit failure.
    assert result['coverage']['entry_count'] == 9


def test_nested_graph_is_rejected_before_unbounded_traversal():
    value = bundle()
    nested = {}
    value['entry'][0]['resource']['unknown'] = nested
    for _ in range(70):
        nested['child'] = {}
        nested = nested['child']
    with pytest.raises(ValueError, match='depth/node'):
        parse(value)


def test_contact_name_and_profile_scalar_types_cannot_crash_projection():
    for index, key, bad in [(0, 'name', [{'family': {}, 'given': ['Synthetic']}]),
                            (2, 'meta', {'profile': None}),
                            (3, 'telecom', [{'system': 'phone', 'value': []}])]:
        value = bundle()
        value['entry'][index]['resource'][key] = bad
        assert parse(value)['coverage']['invalid_count'] >= 1


def test_cli_inspects_without_database_and_refuses_report_overwrite(tmp_path, monkeypatch, capsys):
    from provider_directory_truth_layer.cli import main
    source = FIXTURES / 'north-south.json'
    report = tmp_path / 'inspection.json'
    monkeypatch.setenv('PDTL_ROOT', str(tmp_path / 'not-created'))
    monkeypatch.setattr('sys.argv', ['provider-truth-layer', 'inspect-fhir', str(source), '--report', str(report)])
    main()
    original = report.read_bytes()
    assert json.loads(original)['coverage']['assertion_count'] == 2
    assert not (tmp_path / 'not-created').exists()
    with pytest.raises(SystemExit) as exc:
        main()
    assert exc.value.code == 2
    assert report.read_bytes() == original
    assert 'inspection failed' in capsys.readouterr().err


def test_cli_invalid_envelope_does_not_create_report(tmp_path, monkeypatch):
    from provider_directory_truth_layer.cli import main
    source = tmp_path / 'invalid.json'
    source.write_text('{}')
    report = tmp_path / 'inspection.json'
    monkeypatch.setattr('sys.argv', ['provider-truth-layer', 'inspect-fhir', str(source), '--report', str(report)])
    with pytest.raises(SystemExit):
        main()
    assert not report.exists()


def test_nonfinite_numbers_and_identifier_only_reference_are_explicit():
    with pytest.raises(ValueError, match='finite'):
        fhir.parse_bundle(b'{"resourceType":"Bundle","type":"searchset","total":1e400}')
    value = bundle()
    value['entry'][5]['resource']['location'][0] = {'identifier': {'system': 'https://example.invalid', 'value': 'north'}}
    result = parse(value)
    assert any(r['path'] == '$.entry[5].resource.location[0].reference' and r['state'] == 'unresolved' for r in result['references'])
    assert len(result['assertions']) == 1


def test_unsupported_extension_has_visible_finding():
    value = bundle()
    value['entry'][3]['resource']['extension'] = [{'url': 'https://example.invalid/new-extension', 'valueString': 'raw'}]
    result = parse(value)
    assert any(f['code'] == 'unsupported_extension' and not f['blocks_projection'] for f in result['findings'])


def test_profile_location_narrative_is_not_misclassified_as_scalar_text():
    location = json.loads((FIXTURES / 'profile-location.json').read_bytes())
    result = parse({'resourceType':'Bundle','type':'searchset','entry':[{'resource':location}]})
    assert result['coverage']['eligible_count'] == 1
    assert result['resources'][0]['original']['text'] == location['text']
