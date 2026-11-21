"""Reference bodies must have the same strict interpretation as saved/search JSON."""
import hashlib
import json

import pytest

from provider_directory_truth_layer import fhir_acquisition
from provider_directory_truth_layer.fhir_acquisition import Acquisition
from provider_directory_truth_layer.intake_store import IntakeStore
from test_fhir_acquisition import ATTR, finish, route_json, server, setup


@pytest.mark.parametrize('raw', [
    b'{"resourceType":"Organization","id":"wrong","id":"clinic","name":"Synthetic clinic"}',
    b'{"resourceType":"Location","resourceType":"Organization","id":"clinic"}',
    b'{"resourceType":"Organization","id":"clinic","extension":[{"url":"synthetic","valueString":"first","valueString":"second"}]}',
])
def test_duplicate_reference_keys_fail_before_publication_and_survive_restart(setup, raw):
    store, service, routes, seen, clock = setup
    route_json(routes,'/Location/?_count=1', {'resourceType':'Bundle','type':'searchset','entry':[
        {'resource':{'resourceType':'Location','id':'north','managingOrganization':{'reference':'Organization/clinic'}}}]})
    routes['/Organization/clinic'] = (200, {'Content-Type':'application/fhir+json'}, raw)
    created = service.create({**ATTR,'resource_type':'Location'})
    result = finish(service,created['id'])
    assert result['state'] == 'failed', result
    assert result['receipt_id'] is None
    assert 'Duplicate JSON property' in result['checkpoint']['error']
    assert result['checkpoint']['pages'] == 1 and result['checkpoint']['references'] == 0
    response = next(event for event in reversed(result['events']) if event['kind']=='response')
    assert response['payload']['status'] == 200 and response['artifact_sha'] == hashlib.sha256(raw).hexdigest()
    assert (store.artifacts/response['artifact_sha']).read_bytes() == raw
    reopened = IntakeStore.open_existing(store.path,store.root)
    again = Acquisition(reopened,source=service.source,clock=lambda:clock[0]).run_once(created['id'])
    assert again['state']=='failed' and again['receipt_id'] is None and len(seen)==2
    with reopened.db() as conn:
        assert conn.execute('SELECT count(*) FROM receipt').fetchone()[0] == 0
        assert conn.execute('SELECT count(*) FROM observation').fetchone()[0] == 0
        assert conn.execute('SELECT count(*) FROM feed_version').fetchone()[0] == 0


@pytest.mark.parametrize('value, message', [
    (b'NaN', 'Non-JSON numeric constant'),
    (b'Infinity', 'Non-JSON numeric constant'),
    (b'1e999', 'finite'),
    (b'['*66+b'0'+b']'*66, 'depth/node'),
    (b'['+b'0,'*100_000+b'0]', 'depth/node'),
])
def test_reference_json_limits_apply_before_identity_and_assembly(setup, value, message):
    store, service, routes, _, _ = setup
    route_json(routes,'/Location/?_count=1', {'resourceType':'Bundle','type':'searchset','entry':[
        {'resource':{'resourceType':'Location','id':'north','managingOrganization':{'reference':'Organization/clinic'}}}]})
    raw = b'{"resourceType":"Organization","id":"clinic","uninterpreted":'+value+b'}'
    routes['/Organization/clinic'] = (200, {}, raw)
    result = finish(service,service.create({**ATTR,'resource_type':'Location'})['id'])
    assert result['state']=='failed' and result['receipt_id'] is None
    assert result['checkpoint']['references']==0 and message in result['checkpoint']['error']
    assert any(event['artifact_sha']==hashlib.sha256(raw).hexdigest() for event in result['events'])


def test_legacy_queued_reference_rechecks_original_bytes_at_publication(setup, monkeypatch):
    store, service, routes, seen, _ = setup
    route_json(routes,'/Location/?_count=1', {'resourceType':'Bundle','type':'searchset','entry':[
        {'resource':{'resourceType':'Location','id':'north','managingOrganization':{'reference':'Organization/clinic'}}}]})
    raw=b'{"resourceType":"Organization","id":"wrong","id":"clinic"}'
    routes['/Organization/clinic']=(200,{},raw)
    # Reproduce the old decoder in acquisition only; the normalized assembled
    # Bundle remains valid, which is why publication must revisit raw bytes.
    monkeypatch.setattr(fhir_acquisition,'load_fhir_json',json.loads)
    created=service.create({**ATTR,'resource_type':'Location'})
    service.run_once(created['id'])
    queued=service.run_once(created['id'])
    assert queued['state']=='queued' and queued['checkpoint']['pending']==[]
    assert queued['checkpoint']['references']==1 and queued['receipt_id'] is None
    monkeypatch.undo()
    result=service.run_once(created['id'])
    assert result['state']=='failed' and 'Duplicate JSON property' in result['checkpoint']['error']
    assert result['receipt_id'] is None and len(seen)==2
    assert (store.artifacts/hashlib.sha256(raw).hexdigest()).read_bytes()==raw


def test_reference_utf8_bom_remains_accepted_with_exact_original_retained(setup):
    store,service,routes,_,_=setup
    route_json(routes,'/Location/?_count=1',{'resourceType':'Bundle','type':'searchset','entry':[
        {'resource':{'resourceType':'Location','id':'north','managingOrganization':{'reference':'Organization/clinic'}}}]})
    raw=b'\xef\xbb\xbf{"resourceType":"Organization","id":"clinic","name":"Synthetic clinic"}'
    routes['/Organization/clinic']=(200,{},raw)
    result=finish(service,service.create({**ATTR,'resource_type':'Location'})['id'])
    assert result['state']=='complete'
    detail=store.detail(result['receipt_id'])
    assert detail['preview']['native']['coverage']['entry_count']==2
    assert (store.artifacts/hashlib.sha256(raw).hexdigest()).read_bytes()==raw
