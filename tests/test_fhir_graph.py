"""Independent positive graph expectations and preserved interpretation versions."""
import copy
import hashlib
import json
from pathlib import Path

import pytest

from provider_directory_truth_layer.fhir_intake import NETWORK_PROFILE, parse_bundle
from provider_directory_truth_layer.intake_store import IntakeStore, packed
from provider_directory_truth_layer.reconciliation_store import ReconciliationStore

FIXTURES = Path(__file__).parent / 'fixtures/intake/fhir-plannet'
PAYLOAD = (FIXTURES / 'profile-graph.json').read_bytes()
EXPECTED = json.loads((FIXTURES / 'profile-graph-expected.json').read_bytes())


def request(receipt, request_id='review-graph'):
    return {'expected_attempt': receipt['attempt_id'], 'policy': 'reference_resources', 'request_id': request_id,
            'actor': 'Synthetic graph reviewer', 'reason': 'Explicit review of complete synthetic source relationships'}


def test_positive_graph_keeps_independent_values_network_scope_and_all_reference_paths():
    result = parse_bundle(PAYLOAD)
    assert len(result['assertions']) == 2, result['findings']
    assert result['parser_version'] == EXPECTED['parser_version']
    assert result['coverage']['eligible_count'] == EXPECTED['resource_count']
    assert result['coverage']['unresolved_count'] == result['coverage']['invalid_count'] == result['coverage']['unsupported_count'] == 0
    assert result['findings'] == []
    assert [r['resource_type'] + '/' + r['id'] for r in result['resources']] == EXPECTED['resource_order']
    assert len(result['references']) == 11 and all(r['state'] == 'resolved' for r in result['references'])
    for role, assertion in zip(EXPECTED['roles'], result['assertions']):
        assert assertion['locator'] == role['role_locator'] and assertion['location_locator'] == role['location_locator']
        assert assertion['provider_name'] == EXPECTED['provider_name'] and assertion['npi'] == EXPECTED['npi']
        assert assertion['phone'] == role['phone'] and assertion['address']['line'] == [role['address_line']]
        assert assertion['address']['postalCode'] == role['zip']
        assert assertion['network_id'] is EXPECTED['local_network_id']
        assert assertion['source_network_reference'] == EXPECTED['source_network_reference']
        assert {r['locator'] for r in assertion['supporting_refs']} == set(role['supporting_locators'])
    original = json.loads(PAYLOAD)
    assert original['entry'][3]['resource']['partOf']['reference'] == EXPECTED['network_parent']
    assert original['entry'][3]['resource']['meta']['versionId'] == 'fixture-1'
    assert all(e['resource']['telecom'][0]['value'] == EXPECTED['role_contact_phone'] for e in original['entry'] if e['resource']['resourceType'] == 'PractitionerRole')
    assert original['entry'][3]['resource']['meta']['profile'] == [NETWORK_PROFILE + '|1.2.0']


@pytest.mark.parametrize('canonical, supported', [(NETWORK_PROFILE, True), (NETWORK_PROFILE + '|1.2.0', True),
    (NETWORK_PROFILE + '|999.0.0', False), (NETWORK_PROFILE + '|1.2.0#other', False)])
def test_network_classification_requires_the_declared_supported_profile(canonical, supported):
    value = json.loads(PAYLOAD); value['entry'][3]['resource']['meta']['profile'] = [canonical]
    result = parse_bundle(packed(value).encode())
    assert len(result['assertions']) == (2 if supported else 0)
    assert all(a['network_id'] is None for a in result['assertions'])
    if not supported:
        assert any(f['code'] == 'unresolved_network_scope' for f in result['findings'])


def test_v1_attempt_and_observations_survive_explicit_v2_reinterpretation(tmp_path, monkeypatch):
    from provider_directory_truth_layer import fhir_intake, fhir_store
    value = json.loads(PAYLOAD); value['entry'][3]['resource']['meta']['profile'] = [NETWORK_PROFILE]
    raw = packed(value).encode()
    store = IntakeStore(tmp_path/'graph.sqlite3', tmp_path)
    # The bare Network representation had identical interpretation semantics in
    # v1. Model that known preceding version without rewriting stored attempts.
    with monkeypatch.context() as legacy:
        legacy.setattr(fhir_intake, 'VERSION', 'fhir-plannet-r4-v1')
        legacy.setattr(fhir_store, 'VERSION', 'fhir-plannet-r4-v1')
        receipt = store.receive(raw, 'old-graph.json', source='synthetic-old-graph', profile='fhir-plannet-r4')
        accepted = store.commit(receipt['id'], request(receipt))
    old_attempt = receipt['attempt_id']; old_observations = copy.deepcopy(accepted['observations'])
    reopened = IntakeStore.open_existing(store.path, store.root)
    old = reopened.detail(receipt['id'])
    assert old['attempt_id'] == old_attempt and old['preview']['native']['parser_version'] == 'fhir-plannet-r4-v1'
    assert old['observations'] == old_observations
    newer = reopened.mapping(receipt['id'], {'expected_attempt': old_attempt})
    assert newer['attempt_id'] != old_attempt
    assert newer['preview']['native']['parser_version'] == EXPECTED['parser_version']
    assert newer['observations'] == []
    assert reopened.detail(receipt['id'], attempt_id=old_attempt)['observations'] == old_observations
    reviewed = reopened.commit(receipt['id'], request(newer, 'review-v2'))
    assert len(reviewed['observations']) == 8
    assert (reopened.artifacts / receipt['artifact_sha']).read_bytes() == raw
    with reopened.db() as conn:
        assert conn.execute('SELECT count(*) FROM observation').fetchone()[0] == 16
        assert conn.execute('SELECT count(*) FROM attempt WHERE decision IS NOT NULL').fetchone()[0] == 2
        assert conn.execute('SELECT count(*) FROM network').fetchone()[0] == 0


def test_profile_graph_reaches_reviewed_north_export_without_changing_south(tmp_path):
    from provider_directory_truth_layer.identity_review import IdentityReview
    from provider_directory_truth_layer.field_reconciliation import FieldReconciliation, workbook
    from provider_directory_truth_layer.operations_rehearsal import link, xlsx_payload
    store = IntakeStore(tmp_path/'graph.sqlite3', tmp_path)
    native = store.receive(PAYLOAD, 'profile-graph.json', source='synthetic-profile-graph', profile='fhir-plannet-r4')
    accepted = store.commit(native['id'], request(native))
    assert len(accepted['observations']) == 8 and accepted['linked_cases'] == []
    clinic_rows = [{'record_id': role['id'], 'npi': EXPECTED['npi'], 'provider_name': EXPECTED['provider_name'],
        'entity_type': 'clinician', 'location_id': role['id'].removeprefix('role-').upper(),
        'address': role['address_line'], 'city': 'Example', 'state': 'MA', 'zip': role['zip'],
        'phone': '6175550199' if role['id'] == 'role-north' else '6175550200'} for role in EXPECTED['roles']]
    clinic = store.receive(packed(clinic_rows).encode(), 'clinic.json', source='synthetic-clinic')
    comparison = ReconciliationStore(store)
    run = comparison.create_run({'inputs': [{'receipt_id': r['id'], 'attempt_id': r['attempt_id']} for r in (native, clinic)],
        'actor': 'Synthetic reviewer', 'reason': 'Review exact source and office relationships'})
    reviewer = IdentityReview(store)
    person = link(reviewer, comparison, run['id'], native, clinic, 'clinician', 'Synthetic Example')
    north = link(reviewer, comparison, run['id'], native, clinic, 'location', 'NORTH', office='NORTH')
    south = link(reviewer, comparison, run['id'], native, clinic, 'location', 'SOUTH', office='SOUTH')
    fields = FieldReconciliation(store)
    before_south = fields.inspect(person, south)
    view = fields.inspect(person, north)
    phone = next(f for f in view['fields'] if f['field'] == 'phone')
    selected = next(o for o in phone['options'] if o['source'] == 'synthetic-profile-graph')
    assert selected['comparison_value'] == {'number': '6175550100', 'extension': None}
    fields.decide({'clinician_id': person, 'location_id': north, 'field': 'phone', 'decision': 'select',
        'selected_ref': selected['ref'], 'expected_snapshot': view['snapshot'], 'expected_decision': None,
        'request_id': 'north-source-phone', 'actor': 'Synthetic reviewer', 'reason': 'Select the retained NORTH source assertion'})
    view = fields.inspect(person, north)
    packet = fields.export(person, north, view['snapshot'])
    assert next(f for f in packet['fields'] if f['field'] == 'phone')['preferred_value'] == {'number': EXPECTED['roles'][0]['phone'], 'extension': None}
    assert fields.inspect(person, south)['fields'] == before_south['fields']
    locators = {c['row']['locator'] for c in packet['source_context'] if c['receipt']['id'] == native['id']}
    assert locators == set(EXPECTED['roles'][0]['supporting_locators'])
    assert xlsx_payload(workbook(packet)) == packet
    assert (store.artifacts / native['artifact_sha']).read_bytes() == PAYLOAD
    reopened = IntakeStore.open_existing(store.path, store.root)
    current = FieldReconciliation(reopened)
    assert current.export(person, north, current.inspect(person, north)['snapshot']) == packet
    with reopened.db() as conn:
        for table in ('network', 'work_case', 'feed_version'):
            assert conn.execute('SELECT count(*) FROM ' + table).fetchone()[0] == 0
        assert conn.execute('PRAGMA integrity_check').fetchone()[0] == 'ok'
        assert not conn.execute('PRAGMA foreign_key_check').fetchall()


def test_multiple_networks_block_only_that_role_with_an_explicit_cardinality_finding():
    raw = (FIXTURES / 'profile-graph-multiple-networks.json').read_bytes()
    result = parse_bundle(raw)
    assert [a['locator'] for a in result['assertions']] == [EXPECTED['roles'][1]['role_locator']]
    assert result['assertions'][0]['phone'] == EXPECTED['roles'][1]['phone']
    findings = [f for f in result['findings'] if f['code'] == 'unresolved_network_scope']
    assert len(findings) == 1 and findings[0]['locator'] == EXPECTED['roles'][0]['role_locator']
    assert 'at most one Network reference' in findings[0]['message'] and 'received 3' in findings[0]['message']
    assert result['coverage']['eligible_count'] == 10 and result['coverage']['unresolved_count'] == 0
    assert result['artifact_sha256'] == hashlib.sha256(raw).hexdigest()
