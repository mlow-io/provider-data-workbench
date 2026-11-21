import copy
import json
import sqlite3
import threading
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from provider_directory_truth_layer.fhir_acquisition import Acquisition, Source, LIMITS
from provider_directory_truth_layer.intake_store import IntakeStore, Conflict, VERSION
from provider_directory_truth_layer.intake_api import create_workbench

FIXTURE=Path(__file__).parent/'fixtures/intake/fhir-plannet/north-south.json'
ATTR={'request_id':'fetch-1','actor':'Synthetic analyst','reason':'Inspect bounded provider evidence','count':1}


@pytest.fixture
def server():
    routes={}; seen=[]
    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            seen.append(self.path)
            status,headers,body=routes.get(self.path,(404,{},b'Unknown synthetic route'))
            self.send_response(status)
            for key,value in headers.items():self.send_header(key,value)
            self.end_headers(); self.wfile.write(body)
        def log_message(self,*args):pass
    instance=ThreadingHTTPServer(('127.0.0.1',0),Handler)
    thread=threading.Thread(target=instance.serve_forever,daemon=True);thread.start()
    base=f'http://127.0.0.1:{instance.server_port}/'
    yield base,routes,seen
    instance.shutdown();instance.server_close();thread.join()


@pytest.fixture
def setup(tmp_path,server):
    base,routes,seen=server
    store=IntakeStore(tmp_path/'directory.sqlite3',tmp_path)
    source=Source(key='synthetic',base=base,plan_net_version='synthetic subset',interval_seconds=0,test_http=True)
    clock=[datetime(2026,11,14,tzinfo=timezone.utc)]
    service=Acquisition(store,source=source,clock=lambda:clock[0])
    return store,service,routes,seen,clock


def route_json(routes,path,data,headers=None):
    routes[path]=(200,headers or {'Content-Type':'application/fhir+json'},json.dumps(data).encode())


def source_bundle(service):
    value=json.loads(FIXTURE.read_bytes())
    for entry in value['entry']:
        r=entry['resource'];entry['fullUrl']=service.source.base+r['resourceType']+'/'+r['id']
    # Remove the intentionally unresolved source role from complete-capture fixtures.
    value['entry']=[e for e in value['entry'] if e['resource']['id']!='unresolved-role']
    return value


def finish(service,id,limit=30):
    for _ in range(limit):
        result=service.run_once(id)
        if result.get('state') in {'complete','failed','cancelled','retry_wait'}:return result
    pytest.fail('Acquisition did not reach a terminal/delayed state within bounded passes')


def test_real_http_multipage_retention_assembly_and_acceptance_have_original_page_origins(setup):
    store,service,routes,seen,_=setup
    value=source_bundle(service)
    first={**value,'entry':value['entry'][:3],'link':[{'relation':'next','url':service.source.base+'?_getpages=synthetic&_count=1'}]}
    second={**value,'entry':value['entry'][3:]}
    route_json(routes,'/Location/?_count=1',first)
    route_json(routes,'/?_getpages=synthetic&_count=1',second)
    created=service.create({**ATTR,'resource_type':'Location'})
    result=finish(service,created['id'])
    assert result['state']=='complete',result
    assert len(seen)==2 and result['checkpoint']['pages']==2
    receipt=store.detail(result['receipt_id'])
    assert receipt['preview']['native']['coverage']['assertion_count']==2
    assert receipt['metadata']['representation']=='derived_assembled_searchset'
    assert receipt['observations']==[] and receipt['linked_cases']==[]
    from provider_directory_truth_layer.reconciliation_store import ReconciliationStore
    records=ReconciliationStore(store).preview_input(receipt['id'],receipt['attempt_id'])['items']
    assert all(ref.get('source_pages') for record in records for ref in record['supporting_refs'])
    from provider_directory_truth_layer.fhir_intake import parse_bundle
    assert receipt['preview']['native']['assertions']==parse_bundle(json.dumps(value).encode())['assertions']
    origin=receipt['metadata']['resource_origins']['$.entry[3].resource'][0]
    assert origin['locator']=='$.entry[0].resource'
    assert json.loads((store.artifacts/origin['artifact_sha']).read_bytes())==second
    request={'expected_attempt':receipt['attempt_id'],'policy':'reference_resources','request_id':'accept','actor':'Synthetic analyst','reason':'Review capture'}
    accepted=store.commit(receipt['id'],request)
    assert len(accepted['observations'])==7
    assert service.run_once(result['id'])['receipt_id']==result['receipt_id']
    assert len(seen)==2
    with store.db() as conn:
        assert conn.execute('SELECT count(*) FROM receipt WHERE id=?',(result['receipt_id'],)).fetchone()[0]==1
        assert conn.execute('PRAGMA integrity_check').fetchone()[0]=='ok'
        assert not conn.execute('PRAGMA foreign_key_check').fetchall()


def test_reference_reads_are_typed_and_never_follow_external_targets(setup):
    store,service,routes,seen,_=setup
    value=source_bundle(service)
    role=next(e for e in value['entry'] if e['resource']['id']=='role-north')
    route_json(routes,'/Location/?_count=1',{'resourceType':'Bundle','type':'searchset','entry':[role]})
    for entry in value['entry']:
        r=entry['resource']
        if r['resourceType'] in {'Practitioner','Location','Organization'}:
            route_json(routes,'/'+r['resourceType']+'/'+r['id'],r)
    result=finish(service,service.create({**ATTR,'resource_type':'Location'})['id'])
    assert result['state']=='complete',result
    assert result['checkpoint']['references']==4
    receipt=store.detail(result['receipt_id'])
    assert receipt['preview']['native']['coverage']['assertion_count']==1
    assert all(not path.startswith('/Patient') for path in seen)


def test_rate_limit_retains_raw_error_and_returns_without_sleep_until_due(setup):
    store,service,routes,seen,clock=setup
    routes['/Location/?_count=1']=(429,{'Retry-After':'120'},b'throttled synthetic body')
    created=service.create({**ATTR,'resource_type':'Location'})
    result=service.run_once(created['id'])
    assert result['state']=='retry_wait'
    assert result['next_retry']==(clock[0]+timedelta(seconds=120)).isoformat()
    event=result['events'][-1]
    assert (store.artifacts/event['artifact_sha']).read_bytes()==b'throttled synthetic body'
    assert service.run_once(created['id'])['revision']==result['revision']
    assert len(seen)==1
    route_json(routes,'/Location/?_count=1',{'resourceType':'Bundle','type':'searchset','entry':[]})
    clock[0]+=timedelta(seconds=120)
    assert finish(service,created['id'])['state']=='complete'


@pytest.mark.parametrize('target',['https://evil.invalid/Location/a','/Patient/a','/Location/a%2fPatient/b','/?_getpages=x&_include=Patient:general-practitioner','/?_getpages=x&_count=999'])
def test_unsafe_next_urls_fail_before_second_request(setup,target):
    store,service,routes,seen,_=setup
    route_json(routes,'/Location/?_count=1',{'resourceType':'Bundle','type':'searchset','entry':[],'link':[{'relation':'next','url':target}]})
    result=finish(service,service.create({**ATTR,'resource_type':'Location'})['id'])
    assert result['state']=='failed' and result['receipt_id'] is None
    assert len(seen)==1


def test_later_page_failure_is_partial_without_publishable_receipt(setup):
    store,service,routes,seen,_=setup
    value=source_bundle(service)
    route_json(routes,'/Location/?_count=1',{**value,'link':[{'relation':'next','url':'/?_getpages=two'}]})
    routes['/?_getpages=two']=(200,{},b'{not-json')
    result=finish(service,service.create({**ATTR,'resource_type':'Location'})['id'])
    assert result['state']=='failed' and result['partial']
    assert result['receipt_id'] is None and len(result['checkpoint']['bodies'])==1
    with store.db() as conn:assert conn.execute('SELECT count(*) FROM observation').fetchone()[0]==0


def test_same_request_recovers_identity_and_changed_request_conflicts(setup):
    _,service,_,_,_=setup
    created=service.create(ATTR)
    assert service.create(ATTR)['id']==created['id']
    with pytest.raises(Conflict):service.create({**ATTR,'count':2})
    with pytest.raises(ValueError):service.create({**ATTR,'url':'http://127.0.0.1/Patient'})


def test_restart_between_pages_and_before_publication_reuses_checkpoint(setup):
    store,service,routes,seen,_=setup
    value=source_bundle(service)
    route_json(routes,'/Location/?_count=1',value)
    created=service.create({**ATTR,'resource_type':'Location'})
    processed=service.run_once(created['id'])
    assert processed['state']=='queued' and not processed['checkpoint']['pending']
    reopened=IntakeStore.open_existing(store.path,store.root)
    new=Acquisition(reopened,source=service.source,clock=service.clock)
    result=finish(new,created['id'])
    assert result['state']=='complete' and len(seen)==1


def test_cancellation_fences_inflight_response_but_preserves_its_bytes(setup):
    store,service,_,_,_=setup
    entered=threading.Event(); release=threading.Event()
    def fetch(url,limit,timeout):
        entered.set(); assert release.wait(5)
        return {'status':200,'headers':{},'body':b'{"resourceType":"Bundle","type":"searchset"}','error':None,'truncated':False}
    worker=Acquisition(store,source=service.source,clock=service.clock,fetcher=fetch)
    created=worker.create({**ATTR,'resource_type':'Location'})
    with ThreadPoolExecutor(max_workers=1) as pool:
        future=pool.submit(worker.run_once,created['id'])
        assert entered.wait(5)
        current=worker.detail(created['id'])
        worker.cancel(created['id'],{'expected_revision':current['revision'],'actor':'Synthetic analyst','reason':'Cancel scope'})
        release.set(); result=future.result(timeout=5)
    assert result['state']=='cancelled' and result['receipt_id'] is None
    assert result['events'][-1]['kind']=='discarded_response'
    assert result['events'][-1]['artifact_sha']


def test_schema11_upgrade_preserves_artifacts_and_backs_up_stopped_database(tmp_path):
    store=IntakeStore(tmp_path/'test.db',tmp_path)
    receipt=store.receive(b'[]','empty.json')
    with store.db() as conn:
        from schema_helpers import remove_assistant_schema
        remove_assistant_schema(conn)
        conn.execute('DROP TABLE fhir_acquisition_event');conn.execute('DROP TABLE fhir_acquisition')
        conn.execute('DELETE FROM schema_migration WHERE version=12');conn.execute('PRAGMA user_version=11')
    reopened=IntakeStore(store.path,store.root)
    assert reopened.detail(receipt['id'])['artifact_sha']==receipt['artifact_sha']
    with sqlite3.connect(str(store.path)+'.pre-intake-v12.bak') as old:
        assert old.execute('PRAGMA user_version').fetchone()[0]==11
    with reopened.db() as conn:assert conn.execute('PRAGMA user_version').fetchone()[0]==VERSION


def test_same_source_redirect_is_retained_then_checked_before_next_pass(setup):
    store,service,routes,seen,_=setup
    routes['/Location/?_count=1']=(302,{'Location':'/Location?_count=1'},b'redirect-body')
    route_json(routes,'/Location?_count=1',{'resourceType':'Bundle','type':'searchset'})
    created=service.create({**ATTR,'resource_type':'Location'})
    first=service.run_once(created['id'])
    assert first['state']=='queued' and len(seen)==1
    assert first['events'][-1]['payload']['status']==302
    assert (store.artifacts/first['events'][-1]['artifact_sha']).read_bytes()==b'redirect-body'
    assert finish(service,created['id'])['state']=='complete'
    assert len(seen)==2


def test_transient_failures_are_bounded_and_raw_bytes_remain_inspectable(setup):
    _,service,routes,seen,clock=setup
    routes['/Location/?_count=1']=(503,{},b'source unavailable')
    created=service.create({**ATTR,'resource_type':'Location'})
    for _ in range(3):
        result=service.run_once(created['id'])
        clock[0]+=timedelta(seconds=10)
    assert result['state']=='failed' and result['receipt_id'] is None
    assert len(seen)==3
    assert len([e for e in result['events'] if e['kind']=='response' and e['artifact_sha']])==3
    assert service.run_once(created['id'])['state']=='failed'
    assert len(seen)==3


def test_page_cycle_and_response_caps_cannot_publish_partial_evidence(setup,monkeypatch):
    _,service,routes,_,_=setup
    route_json(routes,'/Location/?_count=1',{'resourceType':'Bundle','type':'searchset','link':[{'relation':'next','url':'/Location/?_count=1'}]})
    result=finish(service,service.create({**ATTR,'resource_type':'Location'})['id'])
    assert result['state']=='failed' and 'cycle' in result['checkpoint']['error']
    monkeypatch.setitem(LIMITS,'response_bytes',32)
    routes['/Location/?_count=1']=(200,{},b'x'*100)
    result=finish(service,service.create({**ATTR,'request_id':'oversize','resource_type':'Location'})['id'])
    assert result['state']=='failed'
    assert result['events'][-1]['payload']['truncated']
    assert result['events'][-1]['payload']['bytes']==32


def test_atomic_publication_retries_after_crash_without_duplicate_receipts(setup):
    store,service,routes,_,_=setup
    route_json(routes,'/Location/?_count=1',source_bundle(service))
    created=service.create({**ATTR,'resource_type':'Location'})
    service.run_once(created['id'])
    with store.db() as conn:
        conn.execute("CREATE TRIGGER synthetic_publish_failure BEFORE INSERT ON attempt BEGIN SELECT RAISE(ABORT,'publish crash'); END")
    with pytest.raises(sqlite3.IntegrityError,match='publish crash'):
        service.run_once(created['id'])
    with store.db() as conn:
        assert conn.execute('SELECT count(*) FROM receipt').fetchone()[0]==0
        conn.execute('DROP TRIGGER synthetic_publish_failure')
    reopened=Acquisition(IntakeStore.open_existing(store.path,store.root),source=service.source,clock=service.clock)
    result=finish(reopened,created['id'])
    assert result['state']=='complete'
    with store.db() as conn:assert conn.execute('SELECT count(*) FROM receipt').fetchone()[0]==1


def test_repeated_successful_query_retains_delivery_and_reuses_accepted_evidence(setup):
    store,service,routes,_,_=setup
    route_json(routes,'/Location/?_count=1',source_bundle(service))
    results=[]
    for request_id in ['one','two']:
        result=finish(service,service.create({**ATTR,'request_id':request_id,'resource_type':'Location'})['id'])
        receipt=store.detail(result['receipt_id'])
        accepted=store.commit(receipt['id'],{'expected_attempt':receipt['attempt_id'],'policy':'reference_resources','actor':'Synthetic analyst','reason':'Review capture','request_id':'accept'})
        results.append(accepted)
    assert results[0]['state']=='committed' and results[1]['state']=='duplicate_delivery'
    assert results[0]['observations']==results[1]['observations']


def test_api_surface_cannot_configure_arbitrary_source_and_downloads_exact_response(setup,monkeypatch):
    from provider_directory_truth_layer import fhir_acquisition_api
    store,service,routes,_,_=setup
    monkeypatch.setattr(fhir_acquisition_api,'Acquisition',lambda s:service)
    client=TestClient(create_workbench(store.path,store.root))
    registry=client.get('/api/fhir-acquisitions').json()
    assert registry['source']['base']==service.source.base
    assert registry['source']['limits']==LIMITS and registry['items']==[]
    route_json(routes,'/Location/?_count=1',{'resourceType':'Bundle','type':'searchset','entry':[]})
    response=client.post('/api/fhir-acquisitions',json={**ATTR,'source':'synthetic','resource_type':'Location'})
    assert response.status_code==200,response.text
    acquisition_id=response.json()['id']
    assert client.post('/api/fhir-acquisitions',json={**ATTR,'url':'http://127.0.0.1/Patient'}).status_code==422
    fetched=client.post(f'/api/fhir-acquisitions/{acquisition_id}/run-once').json()
    event=fetched['events'][-1]
    artifact=client.get(f"/api/fhir-acquisitions/{acquisition_id}/events/{event['seq']}/artifact")
    assert artifact.content==routes['/Location/?_count=1'][2]
    assert client.get(f"/api/fhir-acquisitions/missing/events/{event['seq']}/artifact").status_code==404
    completed=client.post(f'/api/fhir-acquisitions/{acquisition_id}/run-once').json()
    assert completed['state']=='complete'
    assert client.get('/api/fhir-acquisitions').json()['items'][0]['receipt_id']==completed['receipt_id']


def test_approved_clinic_dataset_does_not_change_during_acquisition(tmp_path,server):
    from test_managed_feed import setup_feed,deliver,approve
    from provider_directory_truth_layer.intake_store import packed
    base,routes,_=server
    store,feeds,feed,inbox=setup_feed(tmp_path)
    deliver(inbox)
    run=feeds.run_once(feed['id'],'2026-10-06T10:00:00+00:00');approve(feeds,run['version_id'])
    before=packed(feeds.export(run['version_id']))
    service=Acquisition(store,source=Source(key='synthetic',base=base,test_http=True,interval_seconds=0))
    route_json(routes,'/Location/?_count=1',source_bundle(service))
    assert finish(service,service.create({**ATTR,'resource_type':'Location'})['id'])['state']=='complete'
    assert packed(feeds.export(run['version_id']))==before
    assert feeds.current(feed['id'])['version_id']==run['version_id']


def test_real_process_death_during_fetch_releases_worker_lock_and_resumes_once(setup):
    import subprocess,sys
    store,service,routes,seen,_=setup
    route_json(routes,'/Location/?_count=1',source_bundle(service))
    created=service.create({**ATTR,'resource_type':'Location'})
    code='''
import os,sys
from datetime import datetime
from pathlib import Path
from provider_directory_truth_layer.intake_store import IntakeStore
from provider_directory_truth_layer.fhir_acquisition import Acquisition,Source,fetch_response
store=IntakeStore.open_existing(Path(sys.argv[1]),Path(sys.argv[2]))
def crash(url,limit,timeout):
    fetch_response(url,limit,timeout)
    os._exit(23)
Acquisition(store,source=Source(key='synthetic',base=sys.argv[3],test_http=True,interval_seconds=0),fetcher=crash,clock=lambda:datetime.fromisoformat(sys.argv[5])).run_once(sys.argv[4])
'''
    result=subprocess.run([sys.executable,'-c',code,str(store.path),str(store.root),service.source.base,created['id'],service.clock().isoformat()],timeout=15)
    assert result.returncode==23
    assert service.detail(created['id'])['state']=='running'
    result=finish(service,created['id'])
    assert result['state']=='complete' and len(seen)==2
    with store.db() as conn:assert conn.execute('SELECT count(*) FROM receipt').fetchone()[0]==1


def test_real_process_death_inside_publication_rolls_back_partial_receipt(setup):
    import subprocess,sys
    store,service,routes,seen,_=setup
    route_json(routes,'/Location/?_count=1',source_bundle(service))
    created=service.create({**ATTR,'resource_type':'Location'})
    service.run_once(created['id'])
    code='''
import os,sys
from pathlib import Path
from provider_directory_truth_layer.intake_store import IntakeStore
from provider_directory_truth_layer.fhir_acquisition import Acquisition,Source
from provider_directory_truth_layer import fhir_store
store=IntakeStore.open_existing(Path(sys.argv[1]),Path(sys.argv[2]))
fhir_store.preview_from_native=lambda native:os._exit(24)
Acquisition(store,source=Source(key='synthetic',base=sys.argv[3],test_http=True,interval_seconds=0)).run_once(sys.argv[4])
'''
    result=subprocess.run([sys.executable,'-c',code,str(store.path),str(store.root),service.source.base,created['id']],timeout=15)
    assert result.returncode==24
    with store.db() as conn:assert conn.execute('SELECT count(*) FROM receipt').fetchone()[0]==0
    assert finish(service,created['id'])['state']=='complete'
    assert len(seen)==1


@pytest.mark.parametrize('budget',['pages','requests','entries','references'])
def test_each_capture_budget_fails_explicitly_without_publication(setup,monkeypatch,budget):
    _,service,routes,_,_=setup
    value=source_bundle(service)
    if budget in {'pages','requests'}:
        value['link']=[{'relation':'next','url':'/?_getpages=another'}]
        monkeypatch.setitem(LIMITS,budget,1)
    elif budget=='entries':monkeypatch.setitem(LIMITS,'entries',1)
    else:
        value['entry']=[e for e in value['entry'] if e['resource']['id']=='role-north']
        monkeypatch.setitem(LIMITS,'references',0)
    route_json(routes,'/Location/?_count=1',value)
    result=finish(service,service.create({**ATTR,'resource_type':'Location'})['id'])
    assert result['state']=='failed' and result['receipt_id'] is None
    assert 'budget' in result['checkpoint']['error'].lower()


def test_active_time_overrun_retains_body_but_cannot_publish(setup,monkeypatch):
    from types import SimpleNamespace
    from provider_directory_truth_layer import fhir_acquisition
    store,service,_,_,_=setup
    ticks=iter([0,91])
    monkeypatch.setattr(fhir_acquisition,'time',SimpleNamespace(monotonic=lambda:next(ticks)))
    worker=Acquisition(store,source=service.source,clock=service.clock,fetcher=lambda *args:{'status':200,'headers':{},'body':b'{"resourceType":"Bundle","type":"searchset"}','error':None,'truncated':False})
    result=worker.run_once(worker.create({**ATTR,'resource_type':'Location'})['id'])
    assert result['state']=='failed' and result['receipt_id'] is None
    assert result['events'][-1]['artifact_sha']


def test_busy_worker_returns_current_state_without_overlapping_network_request(setup):
    store,service,_,_,_=setup
    from provider_directory_truth_layer.managed_feed import ManagedFeed
    created=service.create({**ATTR,'resource_type':'Location'})
    with ManagedFeed(store).worker_lock() as acquired:
        assert acquired
        result=service.run_once(created['id'])
        assert result['busy'] and result['state']=='queued'
        assert result['checkpoint']['requests']==0


def test_retry_after_applies_to_other_acquisitions_and_survives_cancellation(setup):
    store,service,routes,seen,clock=setup
    routes['/Location/?_count=1']=(429,{'Retry-After':'60'},b'Synthetic source-wide throttle')
    first=service.create({**ATTR,'resource_type':'Location'})
    waiting=service.run_once(first['id'])
    service.cancel(first['id'],{'expected_revision':waiting['revision'],'actor':'Synthetic analyst','reason':'Cancel intent while retaining source cooldown'})
    route_json(routes,'/Location/?_count=2',{'resourceType':'Bundle','type':'searchset','entry':[]})
    second=service.create({**ATTR,'request_id':'different-intent','resource_type':'Location','count':2})
    reopened=Acquisition(IntakeStore.open_existing(store.path,store.root),source=service.source,clock=service.clock)
    held=reopened.run_once(second['id'])
    assert len(seen)==1 and held['state']=='retry_wait' and held['checkpoint']['requests']==0
    clock[0]+=timedelta(seconds=60)
    assert reopened.run_once(second['id'])['checkpoint']['requests']==1
    assert len(seen)==2


def test_minimum_spacing_survives_completed_acquisition_and_does_not_delay_publication(setup):
    from dataclasses import replace
    store,service,routes,seen,clock=setup
    worker=Acquisition(store,source=replace(service.source,interval_seconds=30),clock=service.clock)
    route_json(routes,'/Location/?_count=1',{'resourceType':'Bundle','type':'searchset','entry':[]})
    first=worker.create({**ATTR,'resource_type':'Location'})
    worker.run_once(first['id'])
    assert worker.run_once(first['id'])['state']=='complete'  # Local publication is not a source request.
    second=worker.create({**ATTR,'request_id':'second','resource_type':'Location'})
    held=worker.run_once(second['id'])
    assert len(seen)==1 and held['checkpoint']['requests']==0 and held['state']=='retry_wait'
    clock[0]+=timedelta(seconds=30)
    assert worker.run_once(second['id'])['checkpoint']['requests']==1 and len(seen)==2


@pytest.mark.parametrize('terminal_reason',['exhausted','oversized'])
def test_source_retry_after_survives_terminal_failure(setup,terminal_reason):
    _,service,routes,seen,clock=setup
    body=b'x'*(LIMITS['response_bytes']+1) if terminal_reason=='oversized' else b'Synthetic throttle'
    routes['/Location/?_count=1']=(429,{'Retry-After':'60'},body)
    first=service.create({**ATTR,'resource_type':'Location'})
    for _ in range(3):
        result=service.run_once(first['id'])
        if result['state']=='failed':break
        clock[0]+=timedelta(seconds=60)
    assert result['state']=='failed'
    route_json(routes,'/Location/?_count=2',{'resourceType':'Bundle','type':'searchset','entry':[]})
    second=service.create({**ATTR,'request_id':'next-after-failure','resource_type':'Location','count':2})
    before=len(seen)
    held=service.run_once(second['id'])
    assert held['state']=='retry_wait' and len(seen)==before and held['checkpoint']['requests']==0
    clock[0]+=timedelta(seconds=60)
    assert service.run_once(second['id'])['checkpoint']['requests']==1 and len(seen)==before+1


@pytest.mark.parametrize('relative_reference',[False,True])
def test_hap_advertised_paging_and_reference_aliases_fetch_only_published_origin(setup,relative_reference):
    store,_,_,_,clock=setup
    alias='https://fhir-prov-dir-r4.api.hap.org:443'
    reference=alias+'/Organization/clinic'
    advertised=alias+'?_getpages=synthetic&_getpagesoffset=1&_count=1&_pretty=true&_bundletype=searchset'
    source=Source()
    seen=[]
    pages=[
        {'resourceType':'Bundle','type':'searchset','entry':[{'fullUrl':alias+'/Location/north','resource':{'resourceType':'Location','id':'north','status':'active','managingOrganization':{'reference':'Organization/clinic' if relative_reference else reference}}}], 'link':[{'relation':'next','url':advertised}]},
        {'resourceType':'Bundle','type':'searchset','entry':[]},
        {'resourceType':'Organization','id':'clinic','name':'Synthetic clinic'},
    ]
    def fetch(url,*_args):
        seen.append(url)
        return {'status':200,'headers':{},'body':json.dumps(pages[len(seen)-1]).encode(),'error':None,'truncated':False}
    service=Acquisition(store,source=source,clock=lambda:clock[0],fetcher=fetch)
    created=service.create({**ATTR,'resource_type':'Location'})
    result=service.run_once(created['id'])
    assert result['state']=='queued',result['checkpoint']['error']
    assert result['checkpoint']['pending'][0]['source_url']==advertised
    clock[0]+=timedelta(seconds=30)
    result=service.run_once(created['id'])
    assert result['checkpoint']['pending'][0]['source_url']==reference
    clock[0]+=timedelta(seconds=30)
    result=service.run_once(created['id'])
    assert result['state']=='queued'
    complete=service.run_once(created['id'])
    assert complete['state']=='complete'
    assert seen==[source.base+'Location/?_count=1',source.base+'?_getpages=synthetic&_getpagesoffset=1&_count=1&_pretty=true&_bundletype=searchset',source.base+'Organization/clinic']
    receipt=store.detail(complete['receipt_id'])
    native=receipt['preview']['native']
    assert native['coverage']['unresolved_count']==0
    assert native['references'][0]['raw_target']==('Organization/clinic' if relative_reference else reference)
    original_bodies=complete['checkpoint']['bodies']
    derived=json.loads((store.artifacts/receipt['artifact_sha']).read_bytes())
    assert derived['entry'][-1]['fullUrl']==reference
    assert derived['entry'][0]['resource']==pages[0]['entry'][0]['resource']
    assert original_bodies[-1]['url']==source.base+'Organization/clinic' and original_bodies[-1]['source_url']==reference
    assert receipt['metadata']['resource_origins']['$.entry[1].resource'][0]['request_url']==seen[-1]
    assert any(e['kind']=='request' and e['payload'].get('source_url')==advertised for e in complete['events'])
    assert any(e['kind']=='response' and e['payload'].get('source_url')==reference for e in complete['events'])
    assert receipt['observations']==[] and receipt['linked_cases']==[]


@pytest.mark.parametrize('authority',['fhir-prov-dir-r4.api.hap.org','fhir-prov-dir-r4.api.hap.org:443','provider-directory-r4.api.hap.org:443'])
def test_only_declared_hap_default_https_aliases_normalize_to_published_origin(setup,authority):
    store,*_=setup
    service=Acquisition(store)
    assert service.validate_url('https://'+authority+'/Location/north')==service.source.base+'Location/north'


@pytest.mark.parametrize('url',[
    'http://fhir-prov-dir-r4.api.hap.org/Location/north',
    'https://fhir-prov-dir-r4.api.hap.org:444/Location/north',
    'https://fhir-prov-dir-r4.api.hap.org.evil.example/Location/north',
    'https://user@fhir-prov-dir-r4.api.hap.org/Location/north',
    'https://fhir-prov-dir-r4.api.hap.org/Location/north#fragment',
    'https://fhir-prov-dir-r4.api.hap.org/Patient/north',
    'https://fhir-prov-dir-r4.api.hap.org/%4cocation/north',
    'https://fhir-prov-dir-r4.api.hap.org/?_getpages=x&_pretty=yes',
    'https://fhir-prov-dir-r4.api.hap.org/?_getpages=x&_pretty=true&_pretty=false',
])
def test_hap_aliases_do_not_expand_scheme_port_host_path_or_query_authority(setup,url):
    store,*_=setup
    with pytest.raises(ValueError):Acquisition(store).validate_url(url)


def test_injected_source_cannot_route_a_hap_alias(setup):
    _,service,*_=setup
    with pytest.raises(ValueError):service.validate_url('https://fhir-prov-dir-r4.api.hap.org/Location/north')


def test_relative_reference_in_a_foreign_declared_base_is_not_fetched_from_local_source(setup):
    _,service,routes,seen,_=setup
    value={'resourceType':'Bundle','type':'searchset','entry':[{'fullUrl':'https://foreign.example/Location/north','resource':{'resourceType':'Location','id':'north','managingOrganization':{'reference':'Organization/clinic'}}}]}
    route_json(routes,'/Location/?_count=1',value)
    first=service.run_once(service.create({**ATTR,'resource_type':'Location'})['id'])
    assert first['checkpoint']['pending']==[]
    complete=service.run_once(first['id'])
    assert complete['state']=='complete' and len(seen)==1
    assert service.store.detail(complete['receipt_id'])['preview']['native']['coverage']['unresolved_count']==1


def test_native_id_filter_is_pinned_in_query_scope_receipt_and_request_identity(setup):
    _,service,routes,seen,_=setup
    value={'resourceType':'Bundle','type':'searchset','entry':[{'resource':{'resourceType':'Location','id':'north','name':'Synthetic NORTH','status':'active'}}]}
    route_json(routes,'/Location/?_count=1&_id=north',value)
    filtered=service.create({**ATTR,'resource_type':'Location','resource_id':'north'})
    assert service.create({**ATTR,'resource_type':'Location','resource_id':'north'})['id']==filtered['id']
    with pytest.raises(Conflict):service.create({**ATTR,'resource_type':'Location','resource_id':'south'})
    complete=finish(service,filtered['id'])
    assert complete['state']=='complete'
    receipt=service.store.detail(complete['receipt_id'])
    assert complete['config']['resource_id']=='north'
    assert receipt['metadata']['query']=={'resource_type':'Location','count':1,'resource_id':'north'}
    assert seen==['/Location/?_count=1&_id=north']
    assert receipt['observations']==[]
    route_json(routes,'/Location/?_count=1',value)
    other=finish(service,service.create({**ATTR,'request_id':'unfiltered','resource_type':'Location'})['id'])
    assert other['state']=='complete'
    unfiltered=service.store.detail(other['receipt_id'])
    assert receipt['metadata']['scope']!=unfiltered['metadata']['scope']
    assert 'query' not in unfiltered['metadata']  # Prior unfiltered metadata stays compatible.


@pytest.mark.parametrize('resource_id',[None,'','north/one','x?_count=20','a'*65,True,{'id':'north'}])
def test_native_id_filter_rejects_invalid_payloads_without_requests(setup,resource_id):
    _,service,_,seen,_=setup
    with pytest.raises(ValueError):service.create({**ATTR,'resource_id':resource_id})
    assert seen==[] and service.list()['items']==[]


@pytest.mark.parametrize('query',['_id=north&_id=south','_id=north%2Fone','_id='+('a'*65)])
def test_source_links_cannot_expand_the_native_id_filter_grammar(setup,query):
    _,service,*_=setup
    with pytest.raises(ValueError):service.validate_url(service.source.base+'Location/?'+query)


def test_api_native_id_filter_is_validated_locally_before_any_fetch(setup,monkeypatch):
    from provider_directory_truth_layer import fhir_acquisition_api
    store,service,_,seen,_=setup
    monkeypatch.setattr(fhir_acquisition_api,'Acquisition',lambda _store:service)
    client=TestClient(create_workbench(store.path,store.root))
    response=client.post('/api/fhir-acquisitions',json={**ATTR,'resource_type':'Location','resource_id':'north'})
    assert response.status_code==200 and response.json()['config']['resource_id']=='north'
    assert seen==[]
    assert client.post('/api/fhir-acquisitions',json={**ATTR,'request_id':'invalid-filter','resource_id':'../Patient/x'}).status_code==422
