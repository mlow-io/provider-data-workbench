"""Filtered source meaning is checked before retained reference publication."""
import copy
import json

import pytest

from provider_directory_truth_layer.fhir_acquisition import Acquisition, Source
from provider_directory_truth_layer.intake_store import IntakeStore, packed
from test_fhir_acquisition import ATTR, finish, route_json, server, setup


FILTER = {**ATTR, 'resource_type': 'Location', 'resource_id': 'north'}
PATH = '/Location/?_count=1&_id=north'


def entry(kind='Location', native_id='north', mode='match'):
    result = {'resource': {'resourceType': kind, 'id': native_id}}
    if mode != 'omitted':
        result['search'] = {'mode': mode}
    return result


def search(entries, next_url=None):
    result = {'resourceType': 'Bundle', 'type': 'searchset', 'entry': entries}
    if next_url:
        result['link'] = [{'relation': 'next', 'url': next_url}]
    return result


def outcome(severity='warning'):
    return {'search': {'mode': 'outcome'}, 'resource': {'resourceType': 'OperationOutcome', 'issue': [{'severity': severity, 'code': 'processing'}]}}


@pytest.mark.parametrize('mode', ['match', 'omitted'])
@pytest.mark.parametrize('resource', [
    {'resourceType': 'Location', 'id': 'south'},
    {'resourceType': 'Location', 'id': 'North'},
    {'resourceType': 'Practitioner', 'id': 'north'},
    {'resourceType': 'Location'},
    None,
])
def test_http_success_with_wrong_or_missing_match_identity_cannot_publish(setup, mode, resource):
    store, service, routes, seen, _ = setup
    value = entry(mode=mode); value['resource'] = resource
    body = search([value]); route_json(routes, PATH, body)
    result = finish(service, service.create(FILTER)['id'])
    assert result['state'] == 'failed' and result['receipt_id'] is None
    assert 'query' in result['checkpoint']['error'].lower()
    assert seen == [PATH]
    response = next(event for event in result['events'] if event['kind'] == 'response')
    assert response['payload']['status'] == 200
    assert (store.artifacts / response['artifact_sha']).read_bytes() == routes[PATH][2]
    with store.db() as conn:
        assert conn.execute('SELECT count(*) FROM receipt').fetchone()[0] == 0
        assert conn.execute('SELECT count(*) FROM observation').fetchone()[0] == 0


@pytest.mark.parametrize('metadata', [None, 'match', {'mode': None}, {'mode': 'unknown'}, {'mode': []}])
def test_filtered_search_cannot_hide_identity_in_malformed_or_unknown_mode(setup, metadata):
    _, service, routes, _, _ = setup
    value = entry(); value['search'] = metadata
    route_json(routes, PATH, search([value]))
    result = finish(service, service.create(FILTER)['id'])
    assert result['state'] == 'failed' and result['receipt_id'] is None


def test_matches_includes_and_warning_outcomes_keep_distinct_counts_and_acceptance(setup):
    store, service, routes, _, _ = setup
    body = search([entry(), entry('Organization', 'clinic', 'include'), entry('Location', 'south', 'include'), outcome()])
    route_json(routes, PATH, body)
    result = finish(service, service.create(FILTER)['id'])
    assert result['state'] == 'complete'
    receipt = store.detail(result['receipt_id'])
    expected = {'version': 1, 'resource_type': 'Location', 'resource_id': 'north', 'matched_entries': 1,
                'implicit_match_entries': 0, 'included_entries': 2, 'outcome_entries': 1, 'scope': 'captured_search_pages'}
    assert receipt['metadata']['query_validation'] == expected
    assert next(event for event in result['events'] if event['kind'] == 'published')['payload']['query_validation'] == expected
    assert receipt['observations'] == [] and receipt['linked_cases'] == []
    assert json.loads((store.artifacts / receipt['artifact_sha']).read_bytes())['entry'] == body['entry']
    accepted = store.commit(receipt['id'], {'expected_attempt': receipt['attempt_id'], 'policy': 'reference_resources',
        'request_id': 'separate-review', 'actor': 'Synthetic reviewer', 'reason': 'Review matched and explicitly included native evidence'})
    assert len(accepted['observations']) == 3 and accepted['linked_cases'] == []


@pytest.mark.parametrize('mode', ['omitted', 'match'])
def test_exact_match_with_optional_mode_records_whether_it_was_implicit(setup, mode):
    store, service, routes, _, _ = setup
    route_json(routes, PATH, search([entry(mode=mode)]))
    result = finish(service, service.create(FILTER)['id'])
    assert result['state'] == 'complete'
    proof = store.detail(result['receipt_id'])['metadata']['query_validation']
    assert proof['matched_entries'] == 1 and proof['implicit_match_entries'] == (1 if mode == 'omitted' else 0)


def test_include_only_capture_is_rejected_locally_after_restart(setup):
    store, service, routes, seen, _ = setup
    route_json(routes, PATH, search([entry('Location', 'south', 'include')]))
    first = service.run_once(service.create(FILTER)['id'])
    assert first['state'] == 'queued' and first['checkpoint']['pending'] == []
    reopened = Acquisition(IntakeStore.open_existing(store.path, store.root), source=service.source, clock=service.clock)
    result = reopened.run_once(first['id'])
    assert result['state'] == 'failed' and result['partial'] and result['receipt_id'] is None
    assert 'include' in result['checkpoint']['error'].lower() and seen == [PATH]


@pytest.mark.parametrize('match_mode', ['match', 'omitted'])
def test_include_page_can_precede_matching_page_and_original_modes_survive(setup, match_mode):
    store, service, routes, seen, _ = setup
    include = entry('Location', 'north', 'include')
    include['fullUrl'] = service.source.base + 'Location/north'
    match = copy.deepcopy(include)
    if match_mode == 'omitted': match.pop('search')
    else: match['search']['mode'] = 'match'
    route_json(routes, PATH, search([include], '/?_getpages=matches'))
    route_json(routes, '/?_getpages=matches', search([match]))
    result = finish(service, service.create(FILTER)['id'])
    assert result['state'] == 'complete' and len(seen) == 2
    receipt = store.detail(result['receipt_id'])
    proof = receipt['metadata']['query_validation']
    assert proof['matched_entries'] == 1 and proof['included_entries'] == 1
    derived = json.loads((store.artifacts / receipt['artifact_sha']).read_bytes())
    assert len(derived['entry']) == 1 and derived['entry'][0].get('search', {}).get('mode', 'match') == 'match'
    assert proof['implicit_match_entries'] == (1 if match_mode == 'omitted' else 0)
    assert len(receipt['metadata']['resource_origins']['$.entry[0].resource']) == 2
    assert json.loads((store.artifacts / result['checkpoint']['bodies'][0]['sha']).read_bytes())['entry'][0]['search']['mode'] == 'include'


def test_later_page_ignoring_filter_retains_partial_evidence_without_receipt(setup):
    _, service, routes, seen, _ = setup
    route_json(routes, PATH, search([entry()], '/?_getpages=wrong'))
    route_json(routes, '/?_getpages=wrong', search([entry(native_id='south')]))
    result = finish(service, service.create(FILTER)['id'])
    assert result['state'] == 'failed' and result['partial'] and result['receipt_id'] is None
    assert result['checkpoint']['pages'] == 1 and len(seen) == 2
    assert len([e for e in result['events'] if e['kind'] == 'response' and e['artifact_sha']]) == 2


@pytest.mark.parametrize('entries', [[], [outcome('information')]])
def test_successful_empty_or_informational_search_is_not_termination_or_acceptance(setup, entries):
    store, service, routes, _, _ = setup
    route_json(routes, PATH, search(entries))
    result = finish(service, service.create(FILTER)['id'])
    assert result['state'] == 'complete'
    receipt = store.detail(result['receipt_id'])
    assert receipt['metadata']['query_validation']['matched_entries'] == 0
    assert receipt['metadata']['query_validation']['outcome_entries'] == len(entries)
    assert receipt['preview']['native']['coverage']['eligible_count'] == 0
    assert receipt['observations'] == [] and receipt['linked_cases'] == []


@pytest.mark.parametrize('bad_outcome', [
    outcome('error'), outcome('fatal'), outcome('unknown'),
    {'search': {'mode': 'outcome'}, 'resource': {'resourceType': 'OperationOutcome', 'issue': []}},
    {'search': {'mode': 'outcome'}, 'resource': {'resourceType': 'OperationOutcome'}},
    {'search': {'mode': 'outcome'}, 'resource': {'resourceType': 'OperationOutcome', 'issue': [{'severity': 'warning'}]}},
    entry(mode='outcome'),
    {'search': {'mode': 'include'}, 'resource': {'resourceType': 'OperationOutcome', 'issue': [{'severity': 'error', 'code': 'processing'}]}},
])
def test_source_errors_or_malformed_outcomes_cannot_hide_in_http_success(setup, bad_outcome):
    _, service, routes, _, _ = setup
    route_json(routes, PATH, search([entry(), bad_outcome]))
    result = finish(service, service.create(FILTER)['id'])
    assert result['state'] == 'failed' and result['receipt_id'] is None


def test_old_queued_page_is_rechecked_before_publication_without_another_fetch(setup):
    store, service, _, seen, _ = setup
    created = service.create(FILTER)
    # Model a pre-R1 queued checkpoint: an ignored-filter page was retained, but
    # no receipt, acceptance or new validation counters have been written.
    raw = packed(search([entry(native_id='south')])).encode()
    sha = store.retain(raw)
    checkpoint = copy.deepcopy(created['checkpoint'])
    checkpoint.update(pending=[], pages=1, requests=1, bytes=len(raw), bodies=[{'sha': sha,
        'url': service.source.base + 'Location/?_count=1&_id=north', 'kind': 'page', 'retrieved_at': service.clock().isoformat()}])
    with store.db() as conn:
        conn.execute('UPDATE fhir_acquisition SET checkpoint=?,revision=revision+1 WHERE id=?', (packed(checkpoint), created['id']))
    worker = Acquisition(IntakeStore.open_existing(store.path, store.root), source=service.source, clock=service.clock)
    result = worker.run_once(created['id'])
    assert result['state'] == 'failed' and result['receipt_id'] is None and seen == []
    assert result['checkpoint']['requests'] == 1


def test_unfiltered_search_keeps_prior_native_findings_without_new_query_claim(setup):
    store, service, routes, _, _ = setup
    route_json(routes, '/Location/?_count=1', search([entry('InsurancePlan', 'unsupported-plan', 'include')]))
    result = finish(service, service.create({**ATTR, 'resource_type': 'Location'})['id'])
    assert result['state'] == 'complete'
    receipt = store.detail(result['receipt_id'])
    assert 'query_validation' not in receipt['metadata']
    assert receipt['preview']['native']['coverage']['unsupported_count'] == 1


def test_wrong_filtered_match_cannot_change_approved_consumer(tmp_path, server):
    from test_managed_feed import setup_feed, deliver, approve
    base, routes, _ = server
    store, feeds, feed, inbox = setup_feed(tmp_path)
    deliver(inbox)
    version = feeds.run_once(feed['id'], '2026-10-06T10:00:00+00:00')['version_id']
    approve(feeds, version)
    before = packed(feeds.export(version))
    service = Acquisition(store, source=Source(key='synthetic', base=base, test_http=True, interval_seconds=0))
    route_json(routes, PATH, search([entry(native_id='south')]))
    result = finish(service, service.create(FILTER)['id'])
    assert result['state'] == 'failed' and result['receipt_id'] is None
    assert feeds.current(feed['id'])['version_id'] == version and packed(feeds.export(version)) == before
