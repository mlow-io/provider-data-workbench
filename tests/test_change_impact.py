"""Read-only scoped impact, immutable proposal revisions and stale dependency checks."""
from concurrent.futures import ThreadPoolExecutor
import hashlib
import importlib.util
import json
from pathlib import Path
import sqlite3
import uuid

import pytest
from fastapi.testclient import TestClient

from provider_directory_truth_layer.change_impact import ChangeImpact, normalized_value
from provider_directory_truth_layer.field_reconciliation import FieldReconciliation
from provider_directory_truth_layer.identity_review import IdentityReview
from provider_directory_truth_layer.intake_api import create_workbench
from provider_directory_truth_layer.intake_store import Conflict, IntakeStore, VERSION
from provider_directory_truth_layer.reconciliation_store import ReconciliationStore

ROOT=Path(__file__).resolve().parents[1]
SPEC=importlib.util.spec_from_file_location('impact_fixture_setup',ROOT/'scripts/evaluate_change_impact.py')
evaluation=importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(evaluation)


@pytest.fixture
def prepared(tmp_path):
    fixture=json.loads((ROOT/'tests/fixtures/onboarding/reconciliation_challenge.json').read_text())
    result=evaluation.prepare_reviewed_case(tmp_path/'case',fixture)
    result['fixture']=fixture
    return result


def payload(p,**extra):
    view=FieldReconciliation(p['store']).inspect(p['person'],p['office'])
    receipt=p['receipts']['payer']
    return {'clinician_id':p['person'],'location_id':p['office'],'field':'phone',
        'proposed_value':{'number':'2125550111','extension':None},
        'inputs':[{'receipt_id':receipt['id'],'attempt_id':receipt['attempt_id']}],
        'network_ids':list(p['networks'].values()),'expected_snapshot':view['snapshot'],
        'request_id':uuid.uuid4().hex,'actor':'Synthetic reviewer','reason':'Explicit target proposal',**extra}


def approve(review,run,candidate,target):
    context=review.inspect(run['id'],candidate['id'])
    return review.decide({'run_id':run['id'],'candidate_id':candidate['id'],'decision':'approve',
        'request_id':uuid.uuid4().hex,'expected_snapshot':context['review_snapshot'],
        'expected_revisions':{ref:link['id'] if link else None for ref,link in context['current_links'].items()},
        'expected_decision':context['latest_decision']['id'] if context['latest_decision'] else None,
        'target_id':target,'actor':'Reviewer','reason':'Explicit typed link'})


def test_independent_labels_preview_is_read_only_and_never_claims_unlinked_coverage(prepared):
    p=prepared;store=p['store'];service=ChangeImpact(store)
    proposal=service.create(payload(p))
    before=hashlib.sha256(store.path.read_bytes()).hexdigest()
    first=service.preview(proposal['id'],limit=100)
    second=service.preview(proposal['id'],limit=100)
    assert first==second and first['inputs_fresh']
    assert first['counts']=={'affected':2,'unaffected_within_assessed_scope':2,'not_assessed':5}
    assert {t['evaluation_ref'] for t in first['targets'] if t['classification']=='affected'}=={'payer:P1','payer:P4'}
    assert {t['network_id'] for t in first['targets'] if t['classification']=='affected'}==set(p['networks'].values())
    assert 'payer:P2' in {t['evaluation_ref'] for t in first['targets'] if t['classification']=='unaffected_within_assessed_scope'}
    assert hashlib.sha256(store.path.read_bytes()).hexdigest()==before
    with store.db() as conn:
        assert conn.execute('SELECT count(*) FROM observation').fetchone()[0]==0
        assert conn.execute('SELECT count(*) FROM work_case').fetchone()[0]==0
        with pytest.raises(sqlite3.IntegrityError,match='Immutable'):
            conn.execute('DELETE FROM change_proposal')


def test_proposal_revisions_exact_retry_restart_and_concurrency(prepared):
    p=prepared;store=p['store'];service=ChangeImpact(store)
    request=payload(p)
    with ThreadPoolExecutor(max_workers=2) as pool:
        saved=list(pool.map(lambda _:service.create(request),range(2)))
    assert saved[0]==saved[1]
    first=saved[0]
    revision=service.create(payload(p,previous_id=first['id'],proposed_value={'number':'2125550122','extension':'004'}))
    assert revision['root_id']==first['id'] and revision['previous_id']==first['id']
    old=service.preview(first['id'])
    assert not old['inputs_fresh'] and any('newer revision' in reason for reason in old['stale_reasons'])
    with pytest.raises(Conflict,match='superseded'):
        service.create(payload(p,previous_id=first['id']))
    with pytest.raises(Conflict,match='different'):
        service.create({**request,'reason':'Different retry'})
    reopened=ChangeImpact(IntakeStore(store.path,store.root))
    assert reopened.create(request)==first
    assert reopened.preview(revision['id'])==service.preview(revision['id'])
    assert service.list(p['person'],p['office'],limit=1)['next_offset']==1
    assert service.list(p['person'],p['office'],offset=1,limit=1)['items'][0]['id']==first['id']


def test_revised_link_changes_snapshot_and_marks_original_review_stale(prepared):
    p=prepared;service=ChangeImpact(p['store'])
    proposal=service.create(payload(p));before=service.preview(proposal['id'],limit=100)
    comparison=ReconciliationStore(p['store']);run=comparison.run(comparison.runs()['items'][0]['id'])
    index={r['ref']:r for r in p['records']}
    selected=next(c for c in comparison.export(run['id'])['candidates'] if c['kind']=='location' and
                  {index[c['left']]['evaluation_ref'],index[c['right']]['evaluation_ref']}=={'clinic:C1','payer:P1'})
    approve(IdentityReview(p['store']),run,selected,p['office'])
    after=service.preview(proposal['id'],limit=100)
    assert before['snapshot']!=after['snapshot'] and not after['inputs_fresh']
    assert any('field/source/link' in reason for reason in after['stale_reasons'])


def test_rejected_and_reinterpreted_input_is_stale_but_saved_retry_remains_valid(prepared):
    p=prepared;store=p['store'];service=ChangeImpact(store)
    request=payload(p);proposal=service.create(request)
    payer=p['receipts']['payer']
    store.commit(payer['id'],{'expected_attempt':payer['attempt_id'],'policy':'reject','actor':'Reviewer','reason':'Rejected assessed delivery'})
    preview=service.preview(proposal['id'],limit=100)
    assert not preview['inputs_fresh']
    assert preview['counts']['not_assessed']==9 and preview['counts']['affected']==0
    assert service.create(request)==proposal
    with pytest.raises((Conflict,ValueError)):
        service.create(payload(p))


def test_network_filter_is_explicit_and_cannot_claim_excluded_network_unaffected(prepared):
    p=prepared;service=ChangeImpact(p['store'])
    cedar=p['networks']['NET-CEDAR']
    proposal=service.create(payload(p,network_ids=[cedar]))
    preview=service.preview(proposal['id'],limit=100)
    pine=[t for t in preview['targets'] if t['network_id']!=cedar]
    assert pine and all(t['classification']=='not_assessed' for t in pine)
    assert {t['evaluation_ref'] for t in preview['targets'] if t['classification']=='affected'}=={'payer:P1'}
    assert all('network scope' in t['reason'] for t in pine)


def test_normalization_is_typed_and_explicit():
    assert normalized_value('phone',{'number':'+1 (212) 555-0111 ext 004'})=={'number':'2125550111','extension':'004'}
    assert normalized_value('address',{'line1':'10 Example Street STE 004','city':'Boston','state':'MA','zip':'02108-0042'})=={
        'line1':'10 example st','line2':None,'suite':'004','city':'boston','state':'ma','zip':'02108-0042'}
    for field,value in [('phone',{'number':'2125550111 ext 004','extension':'005'}),('phone',{'number':True}),
                        ('address',{'line1':'10 St','city':'Boston','state':'MA','zip':['02108']}),('npi','NA'),
                        ('phone',{'number':'2125550111','execute':'bad'}),('provider_name',''),('phone',{'number':'  '})]:
        with pytest.raises(ValueError):normalized_value(field,value)


@pytest.mark.parametrize('duplicate',[False,True])
def test_existing_phone_work_is_reported_without_resetting_owner_or_history(prepared,duplicate):
    p=prepared;store=p['store'];service=ChangeImpact(store)
    row={'record_id':'CASE-1','npi':'0000000001','provider_name':'Alex Example','entity_type':'clinician',
         'address':'10 Example St STE 100','suite':'100','city':'Exampleton','state':'MA','zip':'02108',
         'phone':'2125550101','reference_phone':'2125550199','location_id':'NORTH'}
    receipt=store.receive(json.dumps([row]).encode(),'existing-work.json',source='case-source')
    accepted=store.commit(receipt['id'],{'policy':'valid_rows','actor':'Reviewer','reason':'Accepted explicit case fixture'})
    case=next(c for c in accepted['linked_cases'] if c['field_name']=='phone')
    evidence_attempt=receipt['attempt_id']
    if duplicate:
        receipt=store.receive(json.dumps([row]).encode(),'repeat-work.json',source='case-source')
        repeated=store.commit(receipt['id'],{'policy':'valid_rows','actor':'Reviewer','reason':'Accept exact repeat'})
        assert repeated['state']=='duplicate_delivery'

    comparison=ReconciliationStore(store)
    clinic=p['receipts']['clinic']
    run=comparison.create_run({'inputs':[{'receipt_id':clinic['id'],'attempt_id':clinic['attempt_id']},
            {'receipt_id':receipt['id'],'attempt_id':receipt['attempt_id']}],'actor':'Reviewer','reason':'Explicit case-source review'})
    review=IdentityReview(store)
    candidates=comparison.candidates(run['id'],kind='clinician',limit=100)['items']
    selected=next(c for c in candidates if c['left_record']['comparison']['npi']=='0000000001' and c['right_record']['comparison']['npi']=='0000000001')
    approve(review,run,selected,p['person'])
    selected=next(c for c in comparison.candidates(run['id'],kind='location',limit=100)['items'] if c['left_record']['comparison']['address']['suite']=='100' and c['right_record']['comparison']['address']['suite']=='100')
    approve(review,run,selected,p['office'])
    fields=FieldReconciliation(store);view=fields.inspect(p['person'],p['office'])
    phone=view['fields'][0]
    fields.decide({'clinician_id':p['person'],'location_id':p['office'],'field':'phone','decision':'conflict',
        'expected_snapshot':view['snapshot'],'expected_decision':phone['decision']['id'],
        'request_id':uuid.uuid4().hex,'actor':'Reviewer','reason':'Re-review after explicit link changes'})
    proposal=service.create(payload(p,inputs=[{'receipt_id':receipt['id'],'attempt_id':receipt['attempt_id']}],network_ids=[]))
    first=service.preview(proposal['id'])
    assert first['work_counts']['affected']==1 and first['existing_work'][0]['id']==case['id']
    assert first['targets'][0]['evidence_attempt_id']==evidence_attempt
    assert first['targets'][0]['attempt_id']==receipt['attempt_id']
    store.event(case['id'],{'action':'assign','owner':'Existing owner','expected_version':case['version'],
                           'actor':'Reviewer','reason':'Explicit human ownership'})
    before=hashlib.sha256(store.path.read_bytes()).hexdigest()
    second=service.preview(proposal['id'])
    assert second['snapshot']!=first['snapshot']
    assert second['existing_work'][0]['owner']=='Existing owner'
    assert second['existing_work'][0]['version']==case['version']+1
    assert hashlib.sha256(store.path.read_bytes()).hexdigest()==before


def test_api_pages_errors_and_preview_do_not_create_work(prepared):
    p=prepared;client=TestClient(create_workbench(p['store'].path,p['store'].root))
    proposal=client.post('/api/reconciliation/change-proposals',json=payload(p))
    assert proposal.status_code==200
    proposal_id=proposal.json()['id']
    detail=client.get('/api/reconciliation/change-proposals/'+proposal_id)
    assert detail.json()['id']==proposal_id
    assert client.get('/api/reconciliation/change-proposals',params={'clinician_id':p['person'],'location_id':p['office']}).json()['total']==1
    page=client.post('/api/reconciliation/impact-preview',json={'proposal_id':proposal_id,'limit':1}).json()
    next_page=client.post('/api/reconciliation/impact-preview',json={'proposal_id':proposal_id,'limit':1,'offset':1}).json()
    assert page['total']==9 and page['next_offset']==1 and len(page['targets'])==1
    assert page['targets'][0]['ref']!=next_page['targets'][0]['ref'] and page['snapshot']==next_page['snapshot']
    assert client.post('/api/reconciliation/impact-preview',json={'proposal_id':proposal_id,'limit':0}).status_code==422
    assert client.post('/api/reconciliation/impact-preview',json={'proposal_id':'missing'}).status_code==404
    assert client.post('/api/reconciliation/change-proposals',json={**payload(p),'execute':'bad'}).status_code==422
    with p['store'].db() as conn:assert conn.execute('SELECT count(*) FROM work_case').fetchone()[0]==0


def test_populated_schema8_upgrade_failure_backup_and_reopen(prepared,monkeypatch):
    p=prepared;store=p['store']
    from provider_directory_truth_layer import change_impact
    before=FieldReconciliation(store).inspect(p['person'],p['office'])
    with store.db() as conn:
        from schema_helpers import remove_managed_schema
        remove_managed_schema(conn)
        conn.executescript('DROP TABLE follow_up_acknowledgement; DROP TABLE follow_up_association; DROP TABLE follow_up_confirmation; DROP TABLE change_proposal; DELETE FROM schema_migration WHERE version>=9; PRAGMA user_version=8;')
    migration=change_impact.MIGRATION_9
    monkeypatch.setattr(change_impact,'MIGRATION_9',migration+'\nINVALID SQL;')
    with pytest.raises(sqlite3.OperationalError):IntakeStore(store.path,store.root)
    with sqlite3.connect(store.path) as conn:
        assert conn.execute('PRAGMA user_version').fetchone()[0]==8
        assert conn.execute('PRAGMA integrity_check').fetchone()[0]=='ok'
    monkeypatch.setattr(change_impact,'MIGRATION_9',migration)
    restored=IntakeStore(store.path,store.root)
    assert FieldReconciliation(restored).inspect(p['person'],p['office'])==before
    with sqlite3.connect(store.path.with_name(store.path.name+'.pre-intake-v9.bak')) as conn:
        assert conn.execute('PRAGMA user_version').fetchone()[0]==8
    with restored.db() as conn:
        assert conn.execute('PRAGMA user_version').fetchone()[0]==VERSION
        assert not conn.execute('PRAGMA foreign_key_check').fetchall()


def test_clinician_field_has_one_target_per_row_not_per_native_address(prepared):
    p=prepared;store=p['store'];fields=FieldReconciliation(store)
    view=fields.inspect(p['person'])
    field=next(f for f in view['fields'] if f['field']=='provider_name')
    fields.decide({'clinician_id':p['person'],'location_id':None,'field':'provider_name','decision':'conflict',
        'expected_snapshot':view['snapshot'],'expected_decision':field['decision']['id'] if field['decision'] else None,
        'request_id':uuid.uuid4().hex,'actor':'Reviewer','reason':'Explicit name conflict'})
    view=fields.inspect(p['person'])
    source=p['receipts']['public_reference']
    service=ChangeImpact(store)
    proposal=service.create(payload(p,location_id=None,field='provider_name',proposed_value='Updated Alex',network_ids=[],
        inputs=[{'receipt_id':source['id'],'attempt_id':source['attempt_id']}],expected_snapshot=view['snapshot']))
    preview=service.preview(proposal['id'],limit=100)
    assert preview['total']==6
    affected=[t for t in preview['targets'] if t['classification']=='affected']
    assert len(affected)==1 and affected[0]['evaluation_ref']=='public_reference:R1'
    assert affected[0]['kind']=='clinician' and affected[0]['ref']==affected[0]['clinician_ref']
    assert affected[0]['address_path']=='' and len(affected[0]['address_evidence_refs'])==3


def test_optional_inbox_paging_keeps_legacy_shape_and_exact_retained_pages(prepared):
    store=prepared['store'];client=TestClient(create_workbench(store.path,store.root))
    assert set(client.get('/api/intakes').json())=={'items'}
    first=client.get('/api/intakes?limit=1').json()
    second=client.get('/api/intakes?limit=1&offset=1').json()
    assert first['total']==3 and first['next_offset']==1
    assert first['items'][0]['id']!=second['items'][0]['id']
    assert client.get('/api/intakes?limit=0').status_code==422


def test_later_accepted_same_scope_delivery_invalidates_proposal(prepared):
    p=prepared;store=p['store'];service=ChangeImpact(store)
    proposal=service.create(payload(p))
    receipt=p['receipts']['payer'];old=store.detail(receipt['id'])
    original=(store.artifacts/old['artifact_sha']).read_bytes()
    changed=original.replace(b'2125550199',b'2125550112',1)
    assert changed!=original
    newer=store.receive(changed,'later-payer.csv',source='payer',metadata=old['metadata'])
    spec=old['attempts'][-1]['spec']
    newer=store.mapping(newer['id'],{key:spec[key] for key in ('mapping','roster_kind','bindings')})
    accepted=store.commit(newer['id'],{'expected_attempt':newer['attempt_id'],'policy':'valid_rows','actor':'Reviewer','reason':'Later accepted source delivery'})
    assert accepted['state']=='committed'
    preview=service.preview(proposal['id'],limit=100)
    assert not preview['inputs_fresh']
    assert any('accepted baseline' in reason for reason in preview['stale_reasons'])
    assert preview['counts']['affected']==0 and preview['counts']['not_assessed']==9


def test_unknown_inputs_and_unsupported_proposal_scope_do_not_persist(prepared):
    p=prepared;service=ChangeImpact(p['store'])
    for changes in ({'network_ids':['missing']},{'inputs':[]},{'inputs':[{'receipt_id':'missing','attempt_id':'missing'}]},
                    {'field':'participation'},{'proposed_value':{'number':'','extension':None}}):
        with pytest.raises((ValueError,KeyError)):
            service.create(payload(p,**changes))
    with p['store'].db() as conn:
        assert conn.execute('SELECT count(*) FROM change_proposal').fetchone()[0]==0


def test_known_target_already_equal_after_rules_is_unaffected(prepared):
    p=prepared;service=ChangeImpact(p['store'])
    proposal=service.create(payload(p,proposed_value={'number':'+1 (212) 555-0199','extension':None}))
    preview=service.preview(proposal['id'],limit=100)
    assert proposal['proposed_value']=={'number':'2125550199','extension':None}
    assert {t['evaluation_ref'] for t in preview['targets'] if t['classification']=='affected'}=={'payer:P4'}
    target=next(t for t in preview['targets'] if t['evaluation_ref']=='payer:P1')
    assert target['classification']=='unaffected_within_assessed_scope'
    assert 'already equals' in target['reason']
