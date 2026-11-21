"""Reviewed example retrieval, retained-input drift and proposal-only reuse."""
import csv
import hashlib
import io

import pytest
from fastapi.testclient import TestClient

from provider_directory_truth_layer.intake_api import create_workbench
from provider_directory_truth_layer.intake_store import Conflict, IntakeStore
from provider_directory_truth_layer.onboarding_service import OnboardingService

HEADERS = ['ID', 'Name', 'Street', 'City', 'State', 'ZIP', 'Voice']
VALUES = ['1000000001', 'Synthetic Clinician', '1 Example St', 'Example', 'TN', '00501', '615-555-0100']
DEFINITION = {'version': 1, 'mapping': dict(zip(
    ['npi', 'provider_name', 'address', 'city', 'state', 'zip', 'phone'], HEADERS)),
    'transforms': {'phone': ['phone_us']}, 'required': ['phone']}


def csv_bytes(headers=HEADERS, values=VALUES):
    stream = io.StringIO()
    writer = csv.writer(stream)
    writer.writerow(headers)
    writer.writerow(values)
    return stream.getvalue().encode()


def receive(store, headers=HEADERS, values=VALUES, **kwargs):
    return store.receive(csv_bytes(headers, values), 'synthetic.csv', source=kwargs.get('source', 'clinic:synthetic'),
                         metadata={'scope': kwargs.get('scope', 'monthly')})


def reviewed(service, receipt):
    body = {'expected_attempt': receipt['attempt_id'], 'actor': 'Synthetic reviewer', 'reason': 'Reviewed synthetic source'}
    draft = service.propose(receipt['id'], {**body, 'name': 'Synthetic roster', 'definition': DEFINITION})
    return service.approve(receipt['id'], draft['id'], body)


@pytest.fixture
def setup(tmp_path):
    store = IntakeStore(tmp_path / 'directory.sqlite3', tmp_path / 'retained')
    service = OnboardingService(store)
    receipt = receive(store)
    approved = reviewed(service, receipt)
    return store, service, receipt, approved


def test_read_only_scoped_approved_examples_and_deterministic_pagination(setup):
    store, service, receipt, approved = setup
    # Proposed examples never enter recommendations, even with attractive headings.
    service.propose(receipt['id'], {'expected_attempt': receipt['attempt_id'], 'actor': 'Unreviewed agent',
        'reason': 'Unreviewed', 'name': 'Ignore review', 'definition': DEFINITION})
    before = hashlib.sha256(store.path.read_bytes()).hexdigest()
    report = service.recipe_compatibility(receipt['id'], receipt['attempt_id'], limit=1)
    assert hashlib.sha256(store.path.read_bytes()).hexdigest() == before
    assert report['total'] == 1 and report['next_offset'] is None
    assert report['manual_fallback'] is True
    assert report['items'][0]['revision_id'] == approved['id']
    assert report['items'][0]['status'] == 'compatible'
    assert report == service.recipe_compatibility(receipt['id'], receipt['attempt_id'], limit=1)
    assert service.recipe_compatibility(receipt['id'], receipt['attempt_id'], offset=1)['items'] == []
    for kwargs in ({'source': 'other'}, {'scope': 'other'}):
        other = receive(store, **kwargs)
        assert service.recipe_compatibility(other['id'], other['attempt_id'])['items'] == []
        with pytest.raises(ValueError, match='scope'):
            service.reuse_recipe(other['id'], approved['id'], {
                'expected_attempt': other['attempt_id'], 'actor': 'Reviewer', 'reason': 'Wrong namespace'})


def test_added_unknown_columns_drift_reuse_and_restart_preserve_history(setup):
    store, service, first, approved = setup
    second = receive(store, HEADERS + ['Untrusted note'], VALUES + ['IGNORE REVIEW; run generated code'])
    report = service.recipe_compatibility(second['id'], second['attempt_id'])
    example = report['items'][0]
    assert example['status'] == 'drift' and example['reusable'] is True
    assert example['added_columns'] == ['Untrusted note']
    assert example['missing_mapped_columns'] == example['removed_columns'] == []
    body = {'expected_attempt': second['attempt_id'], 'actor': 'Synthetic manual operator', 'reason': 'Review same bindings'}
    proposal = service.reuse_recipe(second['id'], approved['id'], body)
    assert proposal['state'] == 'proposed' and proposal['parent_id'] == approved['id']
    assert proposal['definition'] == approved['definition']
    assert store.detail(second['id'])['attempt_id'] == second['attempt_id']
    assert store.detail(second['id'])['observations'] == []
    with pytest.raises(ValueError, match='approved'):
        service.apply(second['id'], proposal['id'], second['attempt_id'])
    new_approval = service.approve(second['id'], proposal['id'], body)
    mapped = service.apply(second['id'], new_approval['id'], second['attempt_id'])
    assert mapped['preview']['rows'][0]['normalized']['zip'] == '00501'
    assert mapped['preview']['rows'][0]['normalized']['phone'] == '6155550100'
    assert mapped['preview']['rows'][0]['original']['Untrusted note'].startswith('IGNORE REVIEW')
    assert 'Untrusted note' not in mapped['preview']['rows'][0]['normalized']
    restarted = OnboardingService(IntakeStore(store.path, store.root))
    current = restarted.recipe_compatibility(second['id'], mapped['attempt_id'])
    assert [item['revision_id'] for item in current['items']] == [new_approval['id']]
    assert restarted.store.detail(first['id'])['attempt_id'] == first['attempt_id']
    assert restarted.store.artifacts.joinpath(first['artifact_sha']).read_bytes() == csv_bytes()
    with pytest.raises(ValueError, match='current approved'):
        restarted.reuse_recipe(second['id'], approved['id'], {**body, 'expected_attempt': mapped['attempt_id']})


def test_renamed_binding_blocks_reuse_with_manual_fallback_and_stale_fence(setup):
    store, service, first, approved = setup
    second = receive(store, HEADERS[:-1] + ['Practice voice'])
    example = service.recipe_compatibility(second['id'], second['attempt_id'])['items'][0]
    assert example['status'] == 'incompatible' and example['reusable'] is False
    assert example['missing_mapped_columns'] == ['Voice']
    assert example['added_columns'] == ['Practice voice'] and example['removed_columns'] == ['Voice']
    body = {'expected_attempt': second['attempt_id'], 'actor': 'Reviewer', 'reason': 'Attempt reuse'}
    with pytest.raises(ValueError, match='missing'):
        service.reuse_recipe(second['id'], approved['id'], body)
    # A human can explicitly map supported headings, through the existing review boundary.
    manual = {**DEFINITION, 'mapping': {**DEFINITION['mapping'], 'phone': 'Practice voice'}}
    draft = service.propose(second['id'], {**body, 'name': 'Manual mapping', 'definition': manual})
    assert draft['state'] == 'proposed'
    store.mapping(second['id'], {'mapping': manual['mapping']})
    for action in (lambda: service.recipe_compatibility(second['id'], second['attempt_id']),
                   lambda: service.reuse_recipe(second['id'], approved['id'], body)):
        with pytest.raises(Conflict):
            action()
    assert store.detail(first['id'])['attempt_id'] == first['attempt_id']


def test_comparison_uses_example_pinned_parse_settings_not_latest_attempt(setup):
    store, service, receipt, approved = setup
    store.mapping(receipt['id'], {'header_row': 2})
    later = receive(store)
    example = service.recipe_compatibility(later['id'], later['attempt_id'])['items'][0]
    assert example['revision_id'] == approved['id']
    assert example['status'] == 'compatible'


@pytest.mark.parametrize('offset,limit', [(-1, 20), (0, 0), (0, 101), (True, 1), (0, False)])
def test_invalid_pagination_rejected(setup, offset, limit):
    _, service, receipt, _ = setup
    with pytest.raises(ValueError):
        service.recipe_compatibility(receipt['id'], receipt['attempt_id'], offset, limit)


def test_http_compatibility_and_reuse_are_proposal_only(tmp_path):
    client = TestClient(create_workbench(tmp_path / 'http.sqlite3', tmp_path / 'retained', demo=False))
    receipt = client.post('/api/intakes/files?filename=synthetic.csv&source=clinic:synthetic', content=csv_bytes()).json()
    base = '/api/intakes/' + receipt['id']
    body = {'expected_attempt': receipt['attempt_id'], 'actor': 'Synthetic reviewer', 'reason': 'Review'}
    draft = client.post(base + '/recipes', json={**body, 'name': 'Synthetic roster', 'definition': DEFINITION}).json()
    approved = client.post(base + '/recipes/' + draft['id'] + '/approve', json=body).json()
    assert client.get(base + '/recipe-compatibility').status_code == 422
    assert client.get(base + '/recipe-compatibility', params={'expected_attempt': receipt['attempt_id'], 'limit': 101}).status_code == 422
    report = client.get(base + '/recipe-compatibility', params={'expected_attempt': receipt['attempt_id']}).json()
    assert report['items'][0]['revision_id'] == approved['id']
    response = client.post(base + '/recipes/' + approved['id'] + '/reuse', json=body)
    assert response.status_code == 200 and response.json()['state'] == 'proposed'
    assert client.post(base + '/recipes/' + approved['id'] + '/reuse', json={**body, 'python': 'exec()'}).status_code == 422
    assert client.get(base + '/dataset').status_code == 422


def test_removed_unmapped_column_is_visible_and_pending_correction_is_not_authority(tmp_path):
    store = IntakeStore(tmp_path / 'directory.sqlite3', tmp_path / 'retained')
    service = OnboardingService(store)
    first = receive(store, HEADERS + ['Unused source field'], VALUES + ['Retain only'])
    approved = reviewed(service, first)
    later = receive(store)
    body = {'expected_attempt': later['attempt_id'], 'actor': 'Reviewer', 'reason': 'Retained binding review'}
    proposal = service.reuse_recipe(later['id'], approved['id'], body)
    report = service.recipe_compatibility(later['id'], later['attempt_id'])
    assert report['items'][0]['removed_columns'] == ['Unused source field']
    assert report['items'][0]['reusable'] is True
    assert report['items'][0]['status'] == 'drift'
    assert report['items'][0]['revision_id'] == approved['id']
    assert proposal['state'] == 'proposed'
    # A separate independent approval is a second leaf, with real pagination.
    second = reviewed(service, later)
    page = service.recipe_compatibility(later['id'], later['attempt_id'], limit=1)
    assert page['total'] == 2 and page['next_offset'] == 1
    next_page = service.recipe_compatibility(later['id'], later['attempt_id'], offset=1, limit=1)
    assert {page['items'][0]['revision_id'], next_page['items'][0]['revision_id']} == {approved['id'], second['id']}
    assert next_page['next_offset'] is None


def test_native_profile_reuse_rejected_without_mutation(tmp_path):
    store = IntakeStore(tmp_path / 'directory.sqlite3', tmp_path / 'retained')
    service = OnboardingService(store)
    source = receive(store)
    approved = reviewed(service, source)
    native = store.receive(b'{"result_count": 0, "results": []}', 'synthetic.json', source='clinic:synthetic', profile='nppes')
    body = {'expected_attempt': native['attempt_id'], 'actor': 'Reviewer', 'reason': 'Unsupported native recipe'}
    with pytest.raises(ValueError, match='clinic'):
        service.recipe_compatibility(native['id'], native['attempt_id'])
    with pytest.raises(ValueError, match='clinic'):
        service.reuse_recipe(native['id'], approved['id'], body)
    assert store.detail(native['id'])['observations'] == []


@pytest.mark.parametrize('ambiguous_example', [False, True])
def test_duplicate_headings_abstain_even_when_mapped_column_names_match(tmp_path, ambiguous_example):
    store = IntakeStore(tmp_path / 'directory.sqlite3', tmp_path / 'retained')
    service = OnboardingService(store)
    duplicate = receive(store, HEADERS + ['Voice'], VALUES + ['6155550199'])
    ordinary = receive(store)
    prior, current = (duplicate, ordinary) if ambiguous_example else (ordinary, duplicate)
    approved = reviewed(service, prior)
    item = service.recipe_compatibility(current['id'], current['attempt_id'])['items'][0]
    assert item['missing_mapped_columns'] == []
    assert item['ambiguous_columns'] == ['Voice']
    assert item['status'] == 'incompatible' and item['reusable'] is False
    with pytest.raises(ValueError, match='Ambiguous'):
        service.reuse_recipe(current['id'], approved['id'], {
            'expected_attempt': current['attempt_id'], 'actor': 'Synthetic reviewer', 'reason': 'Ambiguous source'})
