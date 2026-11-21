"""Field review preserves source evidence, exact location scope and immutable decisions."""
from concurrent.futures import ThreadPoolExecutor
import hashlib
import csv
import io
import json
import sqlite3
import uuid

import pytest
from fastapi.testclient import TestClient
from openpyxl import load_workbook

from provider_directory_truth_layer.field_reconciliation import FieldReconciliation, workbook
from provider_directory_truth_layer.identity_review import IdentityReview
from provider_directory_truth_layer.intake_api import create_workbench
from provider_directory_truth_layer.intake_store import Conflict, IntakeStore, VERSION
from provider_directory_truth_layer.reconciliation_store import ReconciliationStore


def approve(review, run, candidate, **target):
    context=review.inspect(run['id'],candidate['id'])
    return review.decide({'run_id':run['id'],'candidate_id':candidate['id'],'decision':'approve',
        'request_id':uuid.uuid4().hex,'expected_snapshot':context['review_snapshot'],
        'expected_revisions':{ref:link['id'] if link else None for ref,link in context['current_links'].items()},
        'expected_decision':context['latest_decision']['id'] if context['latest_decision'] else None,
        'actor':'Synthetic reviewer','reason':'Explicit retained identity review',**target})


@pytest.fixture
def scenario(tmp_path):
    store=IntakeStore(tmp_path/'directory.sqlite3',tmp_path/'root')
    receipts=[]
    for index,source in enumerate(('clinic','payer:CEDAR','reference')):
        row={'record_id':'001','npi':'1000000001','provider_name': ['Alex Synthetic','=1+1','Alex Synthetic'][index],
             'entity_type':'clinician','address':'10 Example St','city':'Boston','state':'MA','zip':'02108','phone':'2125550101',
             'native_addresses':[
                 {'line1':'10 Example St','suite':'004','city':'Boston','state':'MA','zip':'02108','kind':'practice',
                  'phone':['2125550101','2125550199',None][index],'phone_extension':'007'},
                 {'line1':'90 South Road','suite':'200','city':'Boston','state':'MA','zip':'02109','kind':'practice','phone':'6175550101'}]}
        receipts.append(store.receive(json.dumps([row]).encode(),source.replace(':','-')+'.json',source=source))
    comparison=ReconciliationStore(store)
    run=comparison.create_run({'inputs':[{'receipt_id':r['id'],'attempt_id':r['attempt_id']} for r in receipts],
                               'actor':'Reviewer','reason':'Three-source two-office fixture'})
    review=IdentityReview(store)
    people=comparison.candidates(run['id'],kind='clinician',limit=100)['items']
    first=approve(review,run,people[0],new_label='Reviewed Alex')
    clinician=first['decision']['target_id']
    for candidate in people[1:]:
        approve(review,run,candidate,target_id=clinician)
    locations={}
    for candidate in comparison.candidates(run['id'],kind='location',eligible=True,limit=100)['items']:
        suite=candidate['left_record']['comparison']['address']['suite']
        if suite in locations:
            approve(review,run,candidate,target_id=locations[suite])
        else:
            locations[suite]=approve(review,run,candidate,new_label='NORTH' if suite=='004' else 'SOUTH')['decision']['target_id']
    return store,receipts,run,clinician,locations


def request(service,clinician,location,field='phone',action='select',selected_ref=None,**extra):
    view=service.inspect(clinician,location)
    selected=next(f for f in view['fields'] if f['field']==field)
    if action=='select' and selected_ref is None:
        selected_ref=selected['options'][0]['ref']
    return {'clinician_id':clinician,'location_id':location,'field':field,'decision':action,
            'selected_ref':selected_ref,'expected_snapshot':view['snapshot'],
            'expected_decision':selected['decision']['id'] if selected['decision'] else None,
            'request_id':uuid.uuid4().hex,'actor':'Synthetic reviewer','reason':'Reviewed conflicting source assertions',**extra}


def test_three_sources_and_two_offices_remain_separate_without_automatic_precedence(scenario):
    store,receipts,run,person,locations=scenario
    service=FieldReconciliation(store)
    name=service.inspect(person)
    assert {f['field'] for f in name['fields']}=={'provider_name','npi'}
    assert name['source_count']==3 and all(f['status']=='unreviewed' for f in name['fields'])
    north=service.inspect(person,locations['004'])
    south=service.inspect(person,locations['200'])
    assert north['source_count']==south['source_count']==3
    phones=next(f for f in north['fields'] if f['field']=='phone')
    assert {o['value']['number'] for o in phones['options']}=={'2125550101','2125550199',None}
    assert all(o['value']['extension']=='007' for o in phones['options'])
    assert {f['field'] for f in north['fields']}=={'phone','address'}
    assert all(record['comparison']['address']['suite']=='004' for record in north['records'])
    assert all(record['comparison']['address']['suite']=='200' for record in south['records'])
    with pytest.raises(ValueError,match='scope'):
        service.decide({**request(service,person,locations['004']), 'selected_ref':south['fields'][0]['options'][0]['ref']})
    with pytest.raises(ValueError,match='scope'):
        service.decide({**request(service,person,locations['004']), 'field':'provider_name'})
    assert all(store.detail(r['id'])['observations']==[] for r in receipts)


def test_selected_and_conflict_decisions_are_immutable_retry_safe_and_independent_fields(scenario):
    store,_,_,person,locations=scenario
    service=FieldReconciliation(store);north=locations['004']
    payload=request(service,person,north)
    saved=service.decide(payload)
    assert service.decide(payload)==saved
    first=service.inspect(person,north)
    assert first['fields'][0]['status']=='selected' and not first['fields'][0]['decision']['stale']
    service.decide(request(service,person,north,field='address',action='conflict'))
    second=service.inspect(person,north)
    assert second['fields'][0]['status']=='selected'  # Other field decisions do not stale the selected phone.
    assert second['fields'][1]['status']=='conflict'
    overwritten=service.decide(request(service,person,north,action='conflict'))
    assert overwritten['previous_id']==saved['id']
    assert service.inspect(person,north)['fields'][0]['preferred_value'] is None
    with pytest.raises(Conflict,match='different'):
        service.decide({**payload,'reason':'Changed retry'})
    with store.db() as conn:
        with pytest.raises(sqlite3.IntegrityError,match='Immutable'):
            conn.execute('DELETE FROM reconciled_field_decision')
        assert conn.execute('SELECT count(*) FROM observation').fetchone()[0]==0
        assert conn.execute('SELECT count(*) FROM work_event').fetchone()[0]==0
    reopened=FieldReconciliation(IntakeStore(store.path,store.root))
    assert reopened.decide(payload)==saved
    assert reopened.inspect(person,north)==service.inspect(person,north)


def test_link_revision_stales_preference_and_pending_review_without_touching_other_office(scenario):
    store,_,run,person,locations=scenario
    service=FieldReconciliation(store);north=locations['004'];south=locations['200']
    saved=service.decide(request(service,person,north))
    stale_request=request(service,person,north,field='address',action='conflict')
    before_south=service.inspect(person,south)
    candidate=next(c for c in ReconciliationStore(store).candidates(run['id'],kind='location',limit=100)['items']
                   if c['left_record']['comparison']['address']['suite']=='004')
    approve(IdentityReview(store),run,candidate,target_id=north)
    fresh=service.inspect(person,north)
    assert fresh['fields'][0]['status']=='stale' and fresh['fields'][0]['decision']['id']==saved['id']
    assert fresh['fields'][0]['preferred_value'] is None
    assert service.inspect(person,south)==before_south
    with pytest.raises(Conflict):service.decide(stale_request)


def test_source_rejection_and_competing_field_decision_invalidate_writes_but_not_exact_retries(scenario):
    store,receipts,_,person,locations=scenario
    service=FieldReconciliation(store);north=locations['004']
    original=request(service,person,north)
    saved=service.decide(original)
    old=request(service,person,north,field='address',action='conflict')
    service.decide(request(service,person,north,action='conflict'))
    with pytest.raises(Conflict):service.decide(old)
    store.commit(receipts[0]['id'],{'expected_attempt':receipts[0]['attempt_id'],'policy':'reject','actor':'Reviewer','reason':'Rejected source'})
    assert not service.inspect(person,north)['inputs_fresh']
    assert service.decide(original)==saved
    with pytest.raises(Conflict):service.decide(request(service,person,north,action='conflict'))


def test_exports_are_complete_snapshot_pinned_literal_and_nonmutating(scenario):
    store,_,_,person,locations=scenario
    service=FieldReconciliation(store)
    service.decide(request(service,person,None,field='provider_name'))
    view=service.inspect(person)
    before=hashlib.sha256(store.path.read_bytes()).hexdigest()
    exported=service.export(person,None,view['snapshot'])
    assert len(exported['source_context'])==3 and exported['source_count']==3
    assert all('original' in context['row'] for context in exported['source_context'])
    assert len(exported['fields'][0]['options'])==3
    book=load_workbook(io.BytesIO(workbook(exported)),data_only=False)
    assert not any(cell.data_type=='f' for sheet in book for row in sheet for cell in row)
    encoded=''.join(row[1] for row in book['Payload'].iter_rows(min_row=2,values_only=True))
    assert json.loads(encoded)==exported
    assert '=1+1' in encoded and '007' in encoded
    assert hashlib.sha256(store.path.read_bytes()).hexdigest()==before
    service.decide(request(service,person,None,field='npi',action='conflict'))
    with pytest.raises(Conflict,match='Export'):service.export(person,None,view['snapshot'])


def test_concurrent_identical_field_request_creates_one_decision(scenario):
    store,_,_,person,locations=scenario
    service=FieldReconciliation(store);payload=request(service,person,locations['004'])
    with ThreadPoolExecutor(max_workers=2) as pool:
        saved=list(pool.map(lambda _:service.decide(payload),range(2)))
    assert saved[0]==saved[1]
    with store.db() as conn:
        assert conn.execute('SELECT count(*) FROM reconciled_field_decision').fetchone()[0]==1


def test_migration_failure_reopen_backup_preserves_populated_reviewed_links(scenario,monkeypatch):
    store,_,_,person,locations=scenario
    from provider_directory_truth_layer import field_reconciliation
    before=IdentityReview(store).identity('clinician',person)
    with store.db() as conn:
        from schema_helpers import remove_managed_schema
        remove_managed_schema(conn)
        conn.executescript('DROP TABLE follow_up_acknowledgement; DROP TABLE follow_up_association; DROP TABLE follow_up_confirmation; DROP TABLE change_proposal; DROP TABLE reconciled_field_decision; DELETE FROM schema_migration WHERE version>=8; PRAGMA user_version=7;')
    migration=field_reconciliation.MIGRATION_8
    monkeypatch.setattr(field_reconciliation,'MIGRATION_8',migration+'\nINVALID SQL;')
    with pytest.raises(sqlite3.OperationalError):IntakeStore(store.path,store.root)
    with sqlite3.connect(store.path) as conn:
        assert conn.execute('PRAGMA user_version').fetchone()[0]==7
    monkeypatch.setattr(field_reconciliation,'MIGRATION_8',migration)
    restored=IntakeStore(store.path,store.root)
    assert IdentityReview(restored).identity('clinician',person)==before
    with sqlite3.connect(store.path.with_name(store.path.name+'.pre-intake-v8.bak')) as conn:
        assert conn.execute('PRAGMA user_version').fetchone()[0]==7
    with restored.db() as conn:
        assert conn.execute('PRAGMA user_version').fetchone()[0]==VERSION
        assert conn.execute('PRAGMA integrity_check').fetchone()[0]=='ok'
        assert not conn.execute('PRAGMA foreign_key_check').fetchall()


def test_api_scope_errors_snapshot_downloads_and_unknown_fields(scenario):
    store,_,_,person,locations=scenario
    service=FieldReconciliation(store);client=TestClient(create_workbench(store.path,store.root))
    view=client.get(f'/api/reconciliation/fields/{person}',params={'location_id':locations['004'],'limit':1}).json()
    assert view['total']==3 and len(view['records'])==1 and view['next_offset']==1
    payload=request(service,person,locations['004'])
    assert client.post('/api/reconciliation/field-decisions',json=payload).status_code==200
    snapshot=service.inspect(person,locations['004'])['snapshot']
    path=f'/api/reconciliation/identities/clinician/{person}/export'
    for format in ('json','xlsx'):
        response=client.get(path,params={'location_id':locations['004'],'expected_snapshot':snapshot,'format':format})
        assert response.status_code==200 and 'attachment' in response.headers['content-disposition']
    assert client.get(path,params={'expected_snapshot':'stale'}).status_code==409
    assert client.get('/api/reconciliation/fields/missing').status_code==404
    assert client.post('/api/reconciliation/field-decisions',json={**payload,'executable':'bad'}).status_code==422
    assert client.get(f'/api/reconciliation/fields/{person}?limit=0').status_code==422


def test_history_export_keeps_removed_selected_source_without_leaking_current_other_office(scenario):
    store,_,run,person,locations=scenario
    service=FieldReconciliation(store);north=locations['004'];south=locations['200']
    selected=service.inspect(person,north)['fields'][0]['options'][0]
    service.decide(request(service,person,north,selected_ref=selected['ref']))
    candidate=next(c for c in ReconciliationStore(store).candidates(run['id'],kind='location',limit=100)['items']
                   if selected['ref'] in (c['left'],c['right']))
    approve(IdentityReview(store),run,candidate,new_label='Separate corrected office')
    view=service.inspect(person,north)
    assert view['fields'][0]['status']=='stale'
    assert selected['ref'] not in {r['ref'] for r in view['records']}
    data=service.export(person,north,view['snapshot'])
    assert all(r['comparison']['address']['suite']=='004' for r in data['records'])
    assert any(context['attempt_id']==selected['attempt_id'] and 'historical_field_decision' in context['roles'] for context in data['source_context'])
    # Original multi-office row remains shared source context; scoped records never add SOUTH.
    assert all(field['preferred_value'] is None for field in data['fields'])


def test_missing_blank_invalid_and_long_values_keep_types_and_complete_export(scenario):
    store,receipts,_,person,locations=scenario
    service=FieldReconciliation(store)
    # Long reviewer text and control characters must survive chunked workbook JSON.
    payload=request(service,person,None,field='provider_name',actor='=local actor',reason='Reviewed\x00 evidence '+('X'*3000))
    service.decide(payload)
    view=service.inspect(person)
    data=service.export(person,None,view['snapshot'])
    book=load_workbook(io.BytesIO(workbook(data)),data_only=False)
    assert json.loads(''.join(row[1] for row in book['Payload'].iter_rows(min_row=2,values_only=True)))==data
    assert data['fields'][0]['decision']['actor']=='=local actor'
    assert '\x00' in data['fields'][0]['decision']['reason']
    assert view['sample_truncated']
    # Every raw source value remains distinct from its standardized comparison.
    north=service.inspect(person,locations['004'])
    phone=north['fields'][0]
    null=next(option for option in phone['options'] if option['value']['number'] is None)
    assert null['comparison_value']['number'] is None
    assert 'null' in null['findings']['phone']
    original=store.detail(receipts[0]['id'])['preview']['rows'][0]['original']
    original['native_addresses'][0]['phone']=''
    blank=store.receive(json.dumps([original]).encode(),'blank-phone.json',source='blank-phone')
    comparison=ReconciliationStore(store)
    run=comparison.create_run({'inputs':[
        {'receipt_id':receipts[0]['id'],'attempt_id':receipts[0]['attempt_id']},
        {'receipt_id':blank['id'],'attempt_id':blank['attempt_id']}], 'actor':'Reviewer','reason':'Retain blank versus null'})
    review=IdentityReview(store)
    approve(review,run,comparison.candidates(run['id'],kind='clinician')['items'][0],target_id=person)
    office=next(c for c in comparison.candidates(run['id'],kind='location')['items'] if c['left_record']['comparison']['address']['suite']=='004')
    approve(review,run,office,target_id=locations['004'])
    options=service.inspect(person,locations['004'])['fields'][0]['options']
    blank_option=next(option for option in options if option['source']=='blank-phone')
    assert blank_option['value']['number']=='' and 'blank' in blank_option['findings']['phone']
    selected_blank=service.decide(request(service,person,locations['004'],selected_ref=blank_option['ref']))
    assert selected_blank['value']['number']==''
    selected_null=service.decide(request(service,person,locations['004'],selected_ref=null['ref']))
    assert selected_null['value']['number'] is None
    with pytest.raises(ValueError):service.decide({**request(service,person,None,field='npi'),'actor':[]})


def test_unlinked_source_and_unchosen_location_do_not_enter_field_scope(scenario):
    store,receipts,run,person,locations=scenario
    service=FieldReconciliation(store)
    before=service.inspect(person,locations['004'])
    original=store.detail(receipts[0]['id'])['preview']['rows'][0]['original']
    extra=store.receive(json.dumps([{**original,'phone':'9995550101'}]).encode(),'PINE.json',source='payer:PINE')
    after=service.inspect(person,locations['004'])
    assert after==before
    assert not any(option['source']=='payer:PINE' for field in after['fields'] for option in field['options'])
    # An unrelated newly created location is not an inferred association for this clinician.
    from provider_directory_truth_layer.network_store import create_catalog
    unrelated=create_catalog(store,'locations',{'label':'Unlinked office','actor':'Reviewer','reason':'Separate office'})
    empty=service.inspect(person,unrelated['id'])
    assert empty['total']==0 and not empty['inputs_fresh']
    with pytest.raises(Conflict):service.decide(request(service,person,unrelated['id'],action='conflict'))


def test_api_history_cursor_advances_and_malformed_phone_cannot_be_preferred(scenario):
    store,receipts,_,person,locations=scenario
    service=FieldReconciliation(store);north=locations['004']
    first=service.decide(request(service,person,north,action='conflict'))
    second=service.decide(request(service,person,north,action='conflict'))
    client=TestClient(create_workbench(store.path,store.root))
    path=f'/api/reconciliation/fields/{person}'
    page=client.get(path,params={'location_id':north,'limit':1}).json()
    assert page['fields'][0]['history_next_offset']==1
    older=client.get(path,params={'location_id':north,'limit':1,'history_offset':1}).json()
    assert page['fields'][0]['history'][0]['id']==second['id']
    assert older['fields'][0]['history'][0]['id']==first['id']
    assert older['fields'][0]['decision']['id']==second['id']
    original=store.detail(receipts[0]['id'])['preview']['rows'][0]['original']
    original['native_addresses'][0]['phone']=['malformed '+('X'*1000)]*200
    bad=store.receive(json.dumps([original]).encode(),'malformed-phone.json',source='bad-phone')
    comparison=ReconciliationStore(store)
    run=comparison.create_run({'inputs':[
        {'receipt_id':receipts[0]['id'],'attempt_id':receipts[0]['attempt_id']},
        {'receipt_id':bad['id'],'attempt_id':bad['attempt_id']}], 'actor':'Reviewer','reason':'Malformed value preservation'})
    review=IdentityReview(store)
    approve(review,run,comparison.candidates(run['id'],kind='clinician')['items'][0],target_id=person)
    office=next(c for c in comparison.candidates(run['id'],kind='location')['items'] if c['left_record']['comparison']['address']['suite']=='004')
    approve(review,run,office,target_id=north)
    view=service.inspect(person,north)
    invalid=next(option for option in view['fields'][0]['options'] if option['source']=='bad-phone')
    assert not invalid['selectable'] and view['sample_truncated']
    assert isinstance(invalid['ref'],str) and len(invalid['ref'])==64
    assert len(json.dumps(view))<300_000
    with pytest.raises(ValueError,match='valid source'):
        service.decide(request(service,person,north,selected_ref=invalid['ref']))
    data=service.export(person,north,view['snapshot'])
    complete=next(option for option in data['fields'][0]['options'] if option['source']=='bad-phone')
    assert complete['value']['number']==original['native_addresses'][0]['phone']


def test_conflicting_run_type_declarations_do_not_create_fresh_clinician_location_fields(tmp_path):
    store=IntakeStore(tmp_path/'types.sqlite3',tmp_path/'root')
    receipts=[]
    for source in ('clinic','payer'):
        row={'record_id':'001','npi':'1000000001','provider_name':'Synthetic unspecified entity',
             'address':'10 Example St','city':'Boston','state':'MA','zip':'02108','phone':'2125550101'}
        receipts.append(store.receive(json.dumps([row]).encode(),source+'.json',source=source))
    comparison=ReconciliationStore(store);review=IdentityReview(store)
    def run(kind):
        return comparison.create_run({'inputs':[{'receipt_id':r['id'],'attempt_id':r['attempt_id'],'entity_kind':kind} for r in receipts],
                                      'actor':'Reviewer','reason':'Explicit source type declaration'})
    person_run=run('clinician')
    person=approve(review,person_run,comparison.candidates(person_run['id'],kind='clinician')['items'][0],new_label='Clinician')['decision']['target_id']
    org_run=run('organization')
    location=approve(review,org_run,comparison.candidates(org_run['id'],kind='location')['items'][0],new_label='Office')['decision']['target_id']
    service=FieldReconciliation(store)
    view=service.inspect(person,location)
    assert not view['inputs_fresh'] and view['scope_problems']
    assert all(not option['selectable'] for field in view['fields'] for option in field['options'])
    assert all(record['comparison']['entity_kind']=='organization' for record in view['records'])
    with pytest.raises(Conflict):service.decide(request(service,person,location))
    # Compatible unknown purpose on another run does not negate explicit person support.
    unknown_run=run('unknown')
    approve(review,unknown_run,comparison.candidates(unknown_run['id'],kind='location')['items'][0],target_id=location)
    assert service.inspect(person,location)['inputs_fresh']


def test_same_namespace_cedar_and_pine_assertions_keep_distinct_network_provenance(scenario):
    store,receipts,_,person,locations=scenario
    source='payer:two-networks'
    targets={}
    for code in ('CEDAR','PINE'):
        target=store.create_catalog('networks',{'label':code,'actor':'Reviewer','reason':'Separate network'})
        binding=store.bind_source({'source':source,'kind':'network','source_key':code,'target_id':target['id'],
                                   'actor':'Reviewer','reason':'Explicit network code'})
        targets[code]=(target,binding)
    site=store.bind_source({'source':source,'kind':'location','source_key':'NORTH','target_id':locations['004'],
                            'actor':'Reviewer','reason':'Explicit site code'})
    rows=[{'record_id':'LIST-'+code,'npi':'1000000001','provider_name':'Alex Synthetic','entity_type':'clinician',
           'address':'10 Example St STE 004','city':'Boston','state':'MA','zip':'02108',
           'phone':'2125550101' if code=='CEDAR' else '2125550199','location_id':'NORTH','network_code':code,
           'participation_status':'listed'} for code in targets]
    stream=io.StringIO()
    writer=csv.DictWriter(stream,fieldnames=list(rows[0]))
    writer.writeheader()
    writer.writerows(rows)
    receipt=store.receive(stream.getvalue().encode(),'two-networks.csv',source=source)
    fields=['record_id','npi','provider_name','address','city','state','zip','phone','location_id','network_code','participation_status']
    receipt=store.mapping(receipt['id'],{'mapping':{field:field for field in fields},'roster_kind':'network',
                         'bindings':{'network':{code:binding['id'] for code,(_,binding) in targets.items()},
                                     'location':{'NORTH':site['id']},'organization':{}}})
    comparison=ReconciliationStore(store)
    run=comparison.create_run({'inputs':[
        {'receipt_id':receipts[0]['id'],'attempt_id':receipts[0]['attempt_id']},
        {'receipt_id':receipt['id'],'attempt_id':receipt['attempt_id']}], 'actor':'Reviewer','reason':'Keep networks separately attributed'})
    review=IdentityReview(store)
    for candidate in comparison.candidates(run['id'],kind='clinician',limit=100)['items']:
        approve(review,run,candidate,target_id=person)
    for candidate in comparison.candidates(run['id'],kind='location',eligible=True,limit=100)['items']:
        approve(review,run,candidate,target_id=locations['004'])
    service=FieldReconciliation(store);view=service.inspect(person,locations['004'])
    network_options=[o for o in view['fields'][0]['options'] if o['source']==source]
    assert len(network_options)==2
    assert {o['network_id'] for o in network_options}=={target['id'] for target,_ in targets.values()}
    assert {o['network_label'] for o in network_options}=={'CEDAR','PINE'}
    selected=next(o for o in network_options if o['network_label']=='PINE')
    saved=service.decide(request(service,person,locations['004'],selected_ref=selected['ref']))
    assert saved['evidence']['network_id']==targets['PINE'][0]['id']
    assert saved['value']['number']=='2125550199'
    cedar=next(o for o in network_options if o['network_label']=='CEDAR')
    assert cedar['ref']!=selected['ref'] and cedar['value']['number']=='2125550101'
