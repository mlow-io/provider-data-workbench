"""Synthetic two-office materialization retains evidence and requires approval."""
import json
import uuid

import pytest

from provider_directory_truth_layer.field_materialization import FieldMaterialization
from provider_directory_truth_layer.field_reconciliation import FieldReconciliation
from provider_directory_truth_layer.identity_review import IdentityReview
from provider_directory_truth_layer.intake_store import Conflict, IntakeStore, packed
from provider_directory_truth_layer.managed_feed import ManagedFeed
from provider_directory_truth_layer.reconciliation_store import ReconciliationStore
from test_managed_feed import setup_feed, deliver, approve
from test_field_reconciliation import approve as approve_link


def fixture(tmp_path, selected_phone='6175550199', selected_extension='0042'):
    store, feeds, feed, inbox = setup_feed(tmp_path)
    deliver(inbox)
    base = feeds.run_once(feed['id'], '2026-10-06T10:00:00+00:00')['version_id']
    approve(feeds, base)
    manifest = feeds.version(base)['manifest']
    records = [dict(record_id='SYNTHETIC-001', npi='1234567890', provider_name='Synthetic Avery Clinic', address=address, city='Example', state='MA', zip=zip_code, phone=phone, phone_extension=selected_extension if office == 'NORTH' else None, location_id=office, entity_type='clinician') for address, zip_code, phone, office in [('10 Fiction Street','02108',selected_phone,'NORTH'),('20 Fiction Street','02109','6175550102','SOUTH')]]
    ref = store.receive(json.dumps(records).encode(), 'reference.json', source='synthetic-reference')
    comparison = ReconciliationStore(store)
    run = comparison.create_run({'inputs': [{'receipt_id': manifest['receipt_id'], 'attempt_id': manifest['attempt_id'], 'entity_kind': 'clinician'}, {'receipt_id': ref['id'], 'attempt_id': ref['attempt_id'], 'entity_kind': 'clinician'}], 'actor': 'Reviewer', 'reason': 'Compare synthetic offices'})
    review = IdentityReview(store)
    person = None
    for candidate in comparison.candidates(run['id'], kind='clinician', eligible=True, limit=100)['items']:
        if candidate['left_record']['comparison']['address']['line1'] != candidate['right_record']['comparison']['address']['line1']:
            continue
        person = approve_link(review, run, candidate, **({'target_id': person} if person else {'new_label': 'Avery'}))['decision']['target_id']
    locations = {}
    for candidate in comparison.candidates(run['id'], kind='location', limit=100)['items']:
        address = candidate['left_record']['comparison']['address']['line1']
        if address in ('10 fiction st', '20 fiction st'):
            label = 'NORTH' if address.startswith('10 ') else 'SOUTH'
            locations[label] = approve_link(review, run, candidate, new_label=label)['decision']['target_id']
    fields = FieldReconciliation(store)
    view = fields.inspect(person, locations['NORTH'])
    option = next(o for o in view['fields'][0]['options'] if o['source'] == 'synthetic-reference')
    decision = fields.decide({'clinician_id':person, 'location_id':locations['NORTH'], 'field':'phone', 'decision':'select', 'selected_ref':option['ref'], 'expected_snapshot':view['snapshot'], 'expected_decision':None, 'request_id':uuid.uuid4().hex, 'actor':'Reviewer', 'reason':'Reviewed phone'})
    view = fields.inspect(person, locations['NORTH'])
    payload = {'clinician_id':person, 'location_id':locations['NORTH'], 'snapshot':view['snapshot'], 'decision_id':decision['id'], 'actor':'Reviewer', 'reason':'Correct roster phone', 'idempotency_key':'test-request'}
    return store, feeds, feed, base, payload, fields, locations


def test_two_office_candidate_approval_and_restart(tmp_path):
    store, feeds, feed, base, payload, fields, locations = fixture(tmp_path)
    service = FieldMaterialization(store)
    choices = service.choices(base)['choices']
    assert len(choices) == 1 and choices[0]['location_label'] == 'NORTH'
    before = packed(feeds.export(base))
    candidate = service.create(base, payload)
    assert service.create(base, payload) == candidate
    with pytest.raises(Conflict, match='already has a candidate'):
        service.create(base, {**payload, 'idempotency_key': 'another-key'})
    with pytest.raises(Conflict, match='different'):
        service.create(base, {**payload, 'reason': 'Different'})
    assert feeds.current(feed['id'])['version_id'] == base
    with pytest.raises(ValueError, match='approved'):
        feeds.export(candidate)
    approved, approval = approve(feeds, candidate)
    assert approved['state'] == 'approved'
    rows = feeds.export(candidate)['records']
    north = next(r for r in rows if r['normalized']['location_id'] == 'NORTH')
    south = next(r for r in rows if r['normalized']['location_id'] == 'SOUTH')
    assert north['normalized']['phone'] == '6175550199'
    assert north['normalized']['phone_extension'] == '0042'
    assert north['original']['phone'] == '6175550101'
    assert north['materialization']['decision_id'] == payload['decision_id']
    assert south['normalized']['phone'] == '6175550102' and 'materialization' not in south
    assert packed(feeds.export(base)) == before
    with pytest.raises(Conflict, match='current approved'):
        service.create(base, {**payload, 'idempotency_key': 'stale-base'})
    with pytest.raises(ValueError, match='does not change'):
        service.create(candidate, {**payload, 'idempotency_key': 'no-op'})
    reopened = IntakeStore(store.path, store.root)
    assert FieldMaterialization(reopened).create(base, payload) == candidate
    assert ManagedFeed(reopened).decide(candidate, approval)['id'] == candidate
    assert packed(ManagedFeed(reopened).export(base)) == before


def test_stale_decision_and_wrong_scope_rejected(tmp_path):
    store, feeds, feed, base, payload, fields, locations = fixture(tmp_path)
    service = FieldMaterialization(store)
    with pytest.raises((ValueError, Conflict)):
        service.create(base, {**payload, 'location_id': locations['SOUTH']})
    candidate = service.create(base, payload)
    view = fields.inspect(payload['clinician_id'], locations['NORTH'])
    fields.decide({'clinician_id':payload['clinician_id'], 'location_id':locations['NORTH'], 'field':'phone', 'decision':'conflict', 'selected_ref':None, 'expected_snapshot':view['snapshot'], 'expected_decision':payload['decision_id'], 'request_id':uuid.uuid4().hex, 'actor':'Reviewer', 'reason':'Unresolved'})
    with pytest.raises(Conflict):
        approve(feeds, candidate)
    assert feeds.current(feed['id'])['version_id'] == base


def test_http_contract_and_derived_job_boundary(tmp_path):
    from fastapi.testclient import TestClient
    from provider_directory_truth_layer.intake_api import create_workbench

    store, feeds, feed, base, payload, _, _ = fixture(tmp_path)
    client = TestClient(create_workbench(store.path, store.root, demo=False))
    route = f'/api/feed-versions/{base}/field-materialization'
    page = client.get(route, params={'limit': 1}).json()
    assert page['total'] == 1 and page['next_offset'] is None
    assert page['choices'][0]['decision_reason'] == 'Reviewed phone'
    assert client.get(route, params={'limit': 0}).status_code == 422
    assert client.post(route, json={**payload, 'location_id': 'missing'}).status_code == 404
    response = client.post(route, json=payload)
    assert response.status_code == 200
    candidate = response.json()
    assert candidate['kind'] == 'derived_field_candidate'
    assert 'inherited' in candidate['report_notice']
    assert client.post(route, json=payload).json()['id'] == candidate['id']
    assert client.post(route, json={**payload, 'reason': 'changed'}).status_code == 409
    job = next(j for j in feeds.detail(feed['id'])['jobs'] if j['id'] == candidate['job_id'])
    assert job['kind'] == 'derived_field_candidate'
    response = client.post(f"/api/feed-jobs/{job['id']}/reprocess", json={'actor': 'Reviewer', 'reason': 'Try'})
    assert response.status_code == 409 and 'cannot be reprocessed' in response.json()['detail']
    assert feeds.current(feed['id'])['version_id'] == base


def test_selected_source_integrity_rechecked_at_approval(tmp_path):
    store, feeds, feed, base, payload, _, _ = fixture(tmp_path)
    service = FieldMaterialization(store)
    choice = service.choices(base)['choices'][0]
    path = store.artifacts / choice['selected_evidence']['artifact_sha']
    original = path.read_bytes()
    candidate = service.create(base, payload)
    path.write_bytes(b'changed')
    with pytest.raises(Conflict, match='artifact digest'):
        approve(feeds, candidate)
    assert feeds.current(feed['id'])['version_id'] == base
    path.write_bytes(original)
    assert approve(feeds, candidate)[0]['state'] == 'approved'


def test_selection_rejects_ambiguous_and_unlinked_base_rows(tmp_path):
    store, feeds, _, base, payload, _, _ = fixture(tmp_path)
    service = FieldMaterialization(store)
    original_view = service.fields._view
    with store.db() as conn:
        version = feeds.version(base, full=True)
        view = original_view(conn, payload['clinician_id'], payload['location_id'])
        linked = next(r for r in view['records'] if r['receipt_id'] == version['manifest']['receipt_id'])
        rows = version['rows']
        rows.append({**next(r for r in rows if r['locator'] == linked['locator'])})
        with pytest.raises(ValueError, match='exactly one'):
            service._selection(conn, version, payload['clinician_id'], payload['location_id'], payload['snapshot'], payload['decision_id'])
        version['rows'] = [r for r in rows if r['locator'] != linked['locator']]
        with pytest.raises(ValueError, match='exactly one'):
            service._selection(conn, version, payload['clinician_id'], payload['location_id'], payload['snapshot'], payload['decision_id'])


def test_approval_rejects_changed_current_base(tmp_path):
    store, feeds, feed, base, payload, _, _ = fixture(tmp_path)
    candidate = FieldMaterialization(store).create(base, payload)
    deliver(tmp_path / 'inbox', 'clean_update.csv', 'week-2', '2026-10-12')
    next_version = feeds.run_once(feed['id'], '2026-10-13T10:00:00+00:00')['version_id']
    current = feeds.version(next_version)
    for finding in current['report']['findings']:
        if finding['severity'] == 'hold':
            feeds.review(next_version, {'expected_report': current['report_hash'], 'code': finding['code'],
                         'disposition': 'acknowledged', 'actor': 'Reviewer', 'reason': 'Reviewed hold'})
    approve(feeds, next_version)
    with pytest.raises(Conflict, match='Baseline'):
        approve(feeds, candidate)
    assert feeds.current(feed['id'])['version_id'] == next_version


def test_approval_rejects_changed_identity_link(tmp_path):
    store, feeds, feed, base, payload, _, _ = fixture(tmp_path)
    service = FieldMaterialization(store)
    candidate = service.create(base, payload)
    with store.db() as conn:
        view = service.fields._view(conn, payload['clinician_id'], payload['location_id'])
        link = next(link for link in view['links'] if link['kind'] == 'location')
        run_id = link['run_id']
    comparison = ReconciliationStore(store)
    candidates = comparison.candidates(run_id, kind='location', limit=100)['items']
    matched = next(c for c in candidates if link['ref'] in (c['left_record']['ref'], c['right_record']['ref']))
    approve_link(IdentityReview(store), {'id': run_id}, matched, target_id=payload['location_id'])
    with pytest.raises(Conflict, match='snapshot changed'):
        approve(feeds, candidate)
    assert feeds.current(feed['id'])['version_id'] == base


def test_next_delivery_reports_source_and_effective_correction_separately(tmp_path):
    store, feeds, feed, base, payload, _, _ = fixture(tmp_path)
    candidate = FieldMaterialization(store).create(base, payload)
    approve(feeds, candidate)
    deliver(tmp_path / 'inbox', delivery_id='unchanged-source', period='2026-10-12')
    result = feeds.run_once(feed['id'], '2026-10-13T10:00:00+00:00')
    assert 'error' not in result, result
    report = feeds.version(result['version_id'], full=True)['report']
    source = next(entry for entry in report['comparison']['entries'] if entry['current_locator'] == 'row:2')
    assert source['status'] == 'unchanged'  # Compared with the retained source observation.
    effective = report['effective_corrections']
    assert effective['baseline_version'] == candidate
    assert effective['counts']['changed'] == 1
    entry = effective['entries'][0]
    assert entry['status'] == 'changed'
    assert entry['old'] == {'phone': '6175550199', 'phone_extension': '0042'}
    assert entry['new'] == {'phone': '6175550101', 'phone_extension': None}
    assert entry['decision_id'] == payload['decision_id']
    assert any(f['code'] == 'effective_correction_drift' and f['severity'] == 'hold' for f in report['findings'])
    assert feeds.current(feed['id'])['version_id'] == candidate
    with pytest.raises(ValueError, match='hold'):
        approve(feeds, result['version_id'])
    next_version = feeds.version(result['version_id'])
    feeds.review(next_version['id'], {'expected_report': next_version['report_hash'], 'code': 'effective_correction_drift',
        'disposition': 'acknowledged', 'actor': 'Reviewer', 'reason': 'Reviewed returning source value'})
    approve(feeds, next_version['id'])
    assert feeds.current(feed['id'])['version_id'] == next_version['id']


def test_next_delivery_matching_effective_phone_has_no_drift_hold(tmp_path):
    import hashlib
    store, feeds, feed, base, payload, _, _ = fixture(tmp_path, selected_extension=None)
    candidate = FieldMaterialization(store).create(base, payload)
    approve(feeds, candidate)
    inbox = tmp_path / 'inbox'
    original = (inbox / 'week-1.csv').read_bytes()
    updated = original.replace(b'6175550101', b'6175550199')
    assert updated != original
    (inbox / 'matching.csv').write_bytes(updated)
    (inbox / 'matching.manifest.json').write_text(json.dumps({'delivery_id': 'matching', 'period': '2026-10-12',
        'as_of': '2026-10-12', 'snapshot': 'full', 'filename': 'matching.csv', 'sha256': hashlib.sha256(updated).hexdigest()}))
    result = feeds.run_once(feed['id'], '2026-10-13T10:00:00+00:00')
    assert 'error' not in result, result
    report = feeds.version(result['version_id'])['report']
    assert report['effective_corrections']['counts']['unchanged'] == 1
    assert not any(f['code'] == 'effective_correction_drift' for f in report['findings'])


def test_next_invalid_corrected_office_is_blocked_and_held(tmp_path):
    store, feeds, feed, base, payload, _, _ = fixture(tmp_path)
    candidate = FieldMaterialization(store).create(base, payload)
    approve(feeds, candidate)
    deliver(tmp_path / 'inbox', 'invalid_phone.csv', 'invalid-next', '2026-10-12')
    result = feeds.run_once(feed['id'], '2026-10-13T10:00:00+00:00')
    assert 'error' not in result, result
    report = feeds.version(result['version_id'])['report']
    assert report['effective_corrections']['counts']['blocked_invalid'] == 1
    assert any(f['code'] == 'effective_correction_drift' and f['severity'] == 'hold' for f in report['findings'])
    assert feeds.current(feed['id'])['version_id'] == candidate
