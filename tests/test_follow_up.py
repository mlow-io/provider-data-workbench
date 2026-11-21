"""Atomic explicit confirmation, typed work scope, preservation and acknowledgement."""
from concurrent.futures import ThreadPoolExecutor
import hashlib
import io
import json
import sqlite3
import uuid

import pytest
from fastapi.testclient import TestClient
from openpyxl import load_workbook

from test_change_impact import prepared, payload, approve
from provider_directory_truth_layer.change_impact import ChangeImpact
from provider_directory_truth_layer.follow_up import FollowUp
from provider_directory_truth_layer.follow_up_export import workbook
from provider_directory_truth_layer.intake_api import create_workbench
from provider_directory_truth_layer.intake_store import Conflict, IntakeStore, VERSION


def proposal_and_plan(p,**extra):
    proposal=ChangeImpact(p['store']).create(payload(p,**extra))
    service=FollowUp(p['store'])
    return proposal,service.preview(proposal['id'],limit=100)


def confirmation(proposal,plan,**extra):
    return {'proposal_id':proposal['id'],'expected_snapshot':plan['impact_snapshot'],'expected_plan':plan['plan_snapshot'],
            'case_choices':{},'request_id':uuid.uuid4().hex,'actor':'Synthetic operator',
            'reason':'Explicitly confirm bounded known follow-up','confirm':True,**extra}


def acknowledgement(target,**extra):
    return {'association_id':target['association_id'],'expected_ack_id':target['latest_ack']['id'] if target['latest_ack'] else None,
        'expected_case_version':target['case']['version'],'request_id':uuid.uuid4().hex,
        'actor':'Synthetic recipient','reason':'Received review task; no provider verification',**extra}


def test_explicit_confirmation_creates_only_affected_scoped_qa_and_exact_retries(prepared):
    p=prepared;store=p['store'];service=FollowUp(store)
    proposal,plan=proposal_and_plan(p)
    assert plan['total']==2 and plan['blocked_count']==0 and all(a['action']=='create' for a in plan['actions'])
    before=hashlib.sha256(store.path.read_bytes()).hexdigest()
    assert service.preview(proposal['id'],limit=100)==plan
    assert hashlib.sha256(store.path.read_bytes()).hexdigest()==before
    request=confirmation(proposal,plan)
    saved=service.confirm(request)
    assert saved['association_count']==2
    assert service.confirm(request)==saved
    assert service.confirm({**request,'request_id':uuid.uuid4().hex})==saved
    receipt=service.get(saved['id'],limit=100)
    assert receipt['source_inputs_fresh'] and receipt['total']==2
    assert {t['network_id'] for t in receipt['targets']}==set(p['networks'].values())
    assert all(t['case']['kind']=='qa' and t['case']['status']=='new' and t['case']['proposal'] is None for t in receipt['targets'])
    assert all(t['scope']['location_id']==p['office'] for t in receipt['targets'])
    with store.db() as conn:
        assert conn.execute('SELECT count(*) FROM work_case').fetchone()[0]==2
        assert conn.execute('SELECT count(*) FROM observation').fetchone()[0]==0
        for table in ('follow_up_confirmation','follow_up_association'):
            with pytest.raises(sqlite3.IntegrityError,match='Immutable'):
                conn.execute(f'DELETE FROM {table}')
    with pytest.raises(Conflict,match='different'):
        service.confirm({**request,'reason':'Changed retry'})
    with pytest.raises(Conflict,match='already confirmed'):
        service.confirm({**request,'request_id':uuid.uuid4().hex,'reason':'Changed intent'})
    reopened=FollowUp(IntakeStore(store.path,store.root))
    assert reopened.confirm(request)==saved
    assert reopened.get(saved['id'],limit=100)==receipt


def test_existing_owner_status_initial_evidence_and_events_are_preserved(prepared):
    p=prepared;store=p['store'];service=FollowUp(store)
    first,plan=proposal_and_plan(p);saved=service.confirm(confirmation(first,plan))
    receipt=service.get(saved['id'],limit=100)
    target=receipt['targets'][0];case_id=target['case']['id']
    store.event(case_id,{'action':'assign','owner':'Existing owner','expected_version':0,'actor':'Operator','reason':'Human ownership'})
    store.event(case_id,{'action':'triage','expected_version':1,'actor':'Operator','reason':'Human triage'})
    with store.db() as conn:
        before_cases=[tuple(row) for row in conn.execute('SELECT * FROM work_case ORDER BY id')]
        before_events=[tuple(row) for row in conn.execute('SELECT * FROM work_event ORDER BY id')]
    second,plan2=proposal_and_plan(p,proposed_value={'number':'2125550122','extension':None})
    assert all(a['action']=='reuse' for a in plan2['actions'])
    saved2=service.confirm(confirmation(second,plan2))
    with store.db() as conn:
        assert [tuple(row) for row in conn.execute('SELECT * FROM work_case ORDER BY id')]==before_cases
        assert [tuple(row) for row in conn.execute('SELECT * FROM work_event ORDER BY id')]==before_events
    current=service.get(saved2['id'],limit=100)
    reused=next(t for t in current['targets'] if t['case']['id']==case_id)
    assert reused['case']['owner']=='Existing owner' and reused['case']['status']=='triaged' and reused['case']['version']==2
    refreshed=ChangeImpact(store).preview(second['id'],limit=100)
    assert refreshed['work_counts']['affected']==2
    assert all(t['case']['id'] in {x['case']['id'] for x in receipt['targets']} for t in current['targets'])


def test_acknowledgement_does_not_close_verify_or_change_work_and_keeps_history(prepared):
    p=prepared;store=p['store'];service=FollowUp(store)
    proposal,plan=proposal_and_plan(p);saved=service.confirm(confirmation(proposal,plan))
    target=service.get(saved['id'])['targets'][0]
    case_id=target['case']['id']
    with store.db() as conn:
        before=tuple(conn.execute('SELECT * FROM work_case WHERE id=?',(case_id,)).fetchone())
        events=[tuple(row) for row in conn.execute('SELECT * FROM work_event WHERE case_id=? ORDER BY id',(case_id,))]
    request=acknowledgement(target)
    ack=service.acknowledge(saved['id'],request)
    assert service.acknowledge(saved['id'],request)==ack
    with store.db() as conn:
        assert tuple(conn.execute('SELECT * FROM work_case WHERE id=?',(case_id,)).fetchone())==before
        assert [tuple(row) for row in conn.execute('SELECT * FROM work_event WHERE case_id=? ORDER BY id',(case_id,))]==events
        with pytest.raises(sqlite3.IntegrityError,match='Immutable'):
            conn.execute('DELETE FROM follow_up_acknowledgement')
    stale={**request,'request_id':uuid.uuid4().hex}
    with pytest.raises(Conflict):service.acknowledge(saved['id'],stale)
    current=next(t for t in service.get(saved['id'])['targets'] if t['association_id']==target['association_id'])
    second=service.acknowledge(saved['id'],acknowledgement(current,reason='Additional receipt note'))
    assert second['previous_id']==ack['id']
    history=service.acknowledgements(saved['id'],target['association_id'],limit=1)
    assert history['total']==2 and history['next_offset']==1 and history['items'][0]['id']==second['id']
    store.event(case_id,{'action':'assign','owner':'New owner','expected_version':0,'actor':'Operator','reason':'Changed work context'})
    assert service.acknowledge(saved['id'],request)==ack
    with pytest.raises(Conflict):service.acknowledge(saved['id'],acknowledgement(current))


def test_stale_impact_or_work_snapshot_cannot_confirm(prepared):
    p=prepared;store=p['store'];service=FollowUp(store)
    first,plan=proposal_and_plan(p);saved=service.confirm(confirmation(first,plan))
    second,old_plan=proposal_and_plan(p,proposed_value={'number':'2125550133','extension':None})
    case=service.get(saved['id'])['targets'][0]['case']
    store.event(case['id'],{'action':'assign','owner':'Changed owner','expected_version':case['version'],
                           'actor':'Operator','reason':'Competing work edit'})
    with pytest.raises(Conflict,match='versions changed'):
        service.confirm(confirmation(second,old_plan))
    assert service.preview(second['id'])['plan_snapshot']!=old_plan['plan_snapshot']
    current=service.preview(second['id'])
    with pytest.raises(ValueError,match='Explicit'):
        service.confirm(confirmation(second,current,confirm=False))


def test_confirmation_rolls_back_cases_events_and_associations_on_mid_transaction_failure(prepared,monkeypatch):
    p=prepared;store=p['store'];service=FollowUp(store)
    proposal,plan=proposal_and_plan(p)
    original=service._create_case;calls=[]
    def fail_second(*args):
        calls.append(1)
        if len(calls)==2:raise RuntimeError('Injected second-target failure')
        return original(*args)
    monkeypatch.setattr(service,'_create_case',fail_second)
    with pytest.raises(RuntimeError,match='Injected'):
        service.confirm(confirmation(proposal,plan))
    with store.db() as conn:
        for table in ('follow_up_confirmation','follow_up_association','work_case','work_event'):
            assert conn.execute(f'SELECT count(*) FROM {table}').fetchone()[0]==0
        assert conn.execute('PRAGMA integrity_check').fetchone()[0]=='ok'
    monkeypatch.setattr(service,'_create_case',original)
    assert service.confirm(confirmation(proposal,plan))['association_count']==2


def test_concurrent_identical_confirmation_creates_one_plan(prepared):
    p=prepared;service=FollowUp(p['store']);proposal,plan=proposal_and_plan(p)
    request=confirmation(proposal,plan)
    with ThreadPoolExecutor(max_workers=2) as pool:
        results=list(pool.map(lambda _:service.confirm(request),range(2)))
    assert results[0]==results[1]
    with p['store'].db() as conn:
        assert conn.execute('SELECT count(*) FROM follow_up_confirmation').fetchone()[0]==1
        assert conn.execute('SELECT count(*) FROM work_case').fetchone()[0]==2


def test_closed_work_is_not_reopened_and_open_work_cannot_be_duplicated(prepared):
    p=prepared;store=p['store'];service=FollowUp(store)
    proposal,plan=proposal_and_plan(p);saved=service.confirm(confirmation(proposal,plan))
    case=service.get(saved['id'])['targets'][0]['case']
    store.event(case['id'],{'action':'resolve','expected_version':0,'actor':'Operator','reason':'QA disposition only'})
    second,plan2=proposal_and_plan(p,proposed_value={'number':'2125550144','extension':None})
    assert {a['action'] for a in plan2['actions']}=={'create','reuse'}
    open_action=next(a for a in plan2['actions'] if a['action']=='reuse')
    with pytest.raises(ValueError,match='duplicate'):
        service.preview(second['id'],case_choices={open_action['target_key']:'new'})
    saved2=service.confirm(confirmation(second,plan2))
    with store.db() as conn:
        assert conn.execute('SELECT status FROM work_case WHERE id=?',(case['id'],)).fetchone()[0]=='resolved'
        assert conn.execute('SELECT count(*) FROM work_case').fetchone()[0]==3
    assert service.get(saved2['id'])['total']==2


def test_exports_are_complete_literal_snapshot_pinned_and_read_only(prepared):
    p=prepared;store=p['store'];service=FollowUp(store)
    proposal,plan=proposal_and_plan(p);saved=service.confirm(confirmation(proposal,plan,actor='=Local operator',reason='Review\x00 '+('X'*2000)))
    receipt=service.get(saved['id'],limit=100)
    service.acknowledge(saved['id'],acknowledgement(receipt['targets'][0]))
    with pytest.raises(Conflict,match='snapshot changed'):service.export(saved['id'],receipt['snapshot'])
    receipt=service.get(saved['id'],limit=100)
    before=hashlib.sha256(store.path.read_bytes()).hexdigest()
    data=service.export(saved['id'],receipt['snapshot'])
    assert len(data['associations'])==2 and len(data['acknowledgements'])==1
    assert len(data['source_context'])==11 and data['confirmation']['assessment']['counts']['not_assessed']==5
    assert any('prior_field_assertion' in context['roles'] for context in data['source_context'])
    assert data['initial_work_receipt_context']
    book=load_workbook(io.BytesIO(workbook(data)),data_only=False)
    payload_data=json.loads(''.join(row[1] for row in book['Payload'].iter_rows(min_row=2,values_only=True)))
    assert payload_data==data
    assert not any(cell.data_type=='f' for sheet in book for row in sheet for cell in row)
    assert hashlib.sha256(store.path.read_bytes()).hexdigest()==before
    client=TestClient(create_workbench(store.path,store.root))
    path='/api/reconciliation/follow-up/'+saved['id']
    assert client.get(path+'?limit=1').json()['next_offset']==1
    for format in ('json','xlsx'):
        assert client.get(path+'/export',params={'expected_snapshot':receipt['snapshot'],'format':format}).status_code==200
    assert client.get('/api/reconciliation/follow-up',params={'proposal_id':proposal['id']}).json()['total']==1
    assert client.get(path+'/acknowledgements').json()['total']==1


def test_schema9_failure_backup_upgrade_preserves_proposals_and_fields(prepared,monkeypatch):
    p=prepared;store=p['store']
    from provider_directory_truth_layer import follow_up
    proposal,plan=proposal_and_plan(p)
    before=ChangeImpact(store).get(proposal['id'])
    with store.db() as conn:
        from schema_helpers import remove_managed_schema
        remove_managed_schema(conn)
        conn.executescript('DROP TABLE follow_up_acknowledgement; DROP TABLE follow_up_association; DROP TABLE follow_up_confirmation; DELETE FROM schema_migration WHERE version=10; PRAGMA user_version=9;')
    migration=follow_up.MIGRATION_10
    monkeypatch.setattr(follow_up,'MIGRATION_10',migration+'\nINVALID SQL;')
    with pytest.raises(sqlite3.OperationalError):IntakeStore(store.path,store.root)
    with sqlite3.connect(store.path) as conn:
        assert conn.execute('PRAGMA user_version').fetchone()[0]==9
        assert conn.execute('PRAGMA integrity_check').fetchone()[0]=='ok'
    monkeypatch.setattr(follow_up,'MIGRATION_10',migration)
    restored=IntakeStore(store.path,store.root)
    assert ChangeImpact(restored).get(proposal['id'])==before
    with sqlite3.connect(store.path.with_name(store.path.name+'.pre-intake-v10.bak')) as conn:
        assert conn.execute('PRAGMA user_version').fetchone()[0]==9
    with restored.db() as conn:
        assert conn.execute('PRAGMA user_version').fetchone()[0]==VERSION
        assert not conn.execute('PRAGMA foreign_key_check').fetchall()


def refresh_explicit_reviews(p,extra_receipts=()):
    """Enact the same frozen human labels on current/extra retained deliveries."""
    from test_change_impact import evaluation
    from provider_directory_truth_layer.reconciliation_store import ReconciliationStore
    from provider_directory_truth_layer.identity_review import IdentityReview
    from provider_directory_truth_layer.field_reconciliation import FieldReconciliation
    store=p['store'];comparison=ReconciliationStore(store)
    receipts=[*p['receipts'].values(),*extra_receipts]
    run=comparison.create_run({'inputs':[{'receipt_id':r['id'],'attempt_id':r['attempt_id']} for r in receipts],
                              'actor':'Fixture reviewer','reason':'Explicitly renew frozen source labels'})
    export=comparison.export(run['id']);records=export['records'];review=IdentityReview(store)
    for group in p['fixture']['expected_clinician_links']:
        members={r['clinician_ref'] for r in records if r['evaluation_ref'] in group['records']}
        evaluation._approve_group(review,run,[c for c in export['candidates'] if c['kind']=='clinician'],members,target=p['clinicians'][group['clinician_id']])
    for group in p['fixture']['expected_location_links']:
        members={r['ref'] for r in records for m in group['members'] if r['evaluation_ref']==m['record'] and
                 ((r['address'].get('source_path') or r['address_path'])==m['address_path'] or (r['source']=='payer' and r['address_path']==''))}
        evaluation._approve_group(review,run,[c for c in export['candidates'] if c['kind']=='location'],members,target=p['locations'][group['location_id']])
    fields=FieldReconciliation(store);view=fields.inspect(p['person'],p['office']);phone=view['fields'][0]
    fields.decide({'clinician_id':p['person'],'location_id':p['office'],'field':'phone','decision':'select',
        'selected_ref':phone['decision']['selected_ref'],'expected_snapshot':view['snapshot'],'expected_decision':phone['decision']['id'],
        'request_id':uuid.uuid4().hex,'actor':'Fixture reviewer','reason':'Renew field evidence after explicit source-link review'})


@pytest.mark.parametrize('missing_native',[False,True])
def test_repeat_deliveries_deduplicate_only_valid_unique_native_target_keys(prepared,tmp_path,missing_native):
    from copy import deepcopy
    from test_change_impact import evaluation
    p=prepared
    if missing_native:
        fixture=deepcopy(p['fixture'])
        for row in fixture['sources']['payer']:
            if row['record_id'] in {'payer:P1','payer:P4'}:row['source_native_id']=None
        p=evaluation.prepare_reviewed_case(tmp_path/'missing-keys',fixture);p['fixture']=fixture
    store=p['store'];original=p['receipts']['payer'];detail=store.detail(original['id']);spec=detail['attempts'][-1]['spec']
    repeated=store.receive((store.artifacts/detail['artifact_sha']).read_bytes(),'repeat.csv',source='payer',metadata=detail['metadata'])
    repeated=store.mapping(repeated['id'],{k:spec[k] for k in ('mapping','roster_kind','bindings')})
    refresh_explicit_reviews(p,[repeated])
    sources=[{'receipt_id':r['id'],'attempt_id':r['attempt_id']} for r in (original,repeated)]
    proposal,plan=proposal_and_plan(p,inputs=sources)
    assert plan['counts']['affected']==4
    assert plan['total']==(4 if missing_native else 2)
    if not missing_native:assert all(len(a['refs'])==2 for a in plan['actions'])
    else:assert all(a['scope']['native_id'] is None and a['scope']['retained_ref'] for a in plan['actions'])
    saved=FollowUp(store).confirm(confirmation(proposal,plan))
    assert saved['association_count']==plan['total']
    with store.db() as conn:assert conn.execute('SELECT count(*) FROM work_case').fetchone()[0]==plan['total']


def test_follow_up_queue_filters_case_context_and_network_handoffs_preserve_typed_scope(prepared):
    from provider_directory_truth_layer.work_export import snapshot,handoff_workbook
    p=prepared;store=p['store'];service=FollowUp(store)
    proposal,plan=proposal_and_plan(p);saved=service.confirm(confirmation(proposal,plan))
    all_cases=store.work(location_id=p['office'])['items']
    assert len(all_cases)==2
    for network in p['networks'].values():
        rows=store.work(network_id=network,location_id=p['office'])['items']
        assert len(rows)==1 and rows[0]['network_id']==network
        detail=store.case(rows[0]['id'])
        assert detail['scope'] is None  # No invented participation assertion.
        assert detail['follow_up_scopes'][0]['kind']=='follow_up'
        assert detail['follow_up_scopes'][0]['network_id']==network
        before=hashlib.sha256(store.path.read_bytes()).hexdigest()
        data=snapshot(store.path,network_id=network)
        assert {case['id'] for case in data['cases']}=={rows[0]['id']}
        assert {scope['network_id'] for scope in data['follow_up_scopes']}=={network}
        assert {scope['evidence']['scope']['network_id'] for scope in data['follow_up_associations']}=={network}
        assert data['participations']==[]
        assert data['follow_up_confirmations'][0]['proposed_value']=={'number':'2125550111','extension':None}
        book=load_workbook(io.BytesIO(handoff_workbook(store.path,network_id=network)),data_only=False)
        assert 'Follow-up scopes' in book.sheetnames and 'Follow-up confirmations' in book.sheetnames
        assert not any(cell.data_type=='f' for sheet in book for row in sheet for cell in row)
        assert hashlib.sha256(store.path.read_bytes()).hexdigest()==before


def test_ambiguous_legacy_cases_require_explicit_selection_without_duplicate_creation(prepared):
    from provider_directory_truth_layer.intake_store import packed,now
    p=prepared;store=p['store'];payer=p['receipts']['payer']
    accepted=store.commit(payer['id'],{'policy':'valid_rows','expected_attempt':payer['attempt_id'],'actor':'Fixture operator','reason':'Accept legacy work evidence'})
    refresh_explicit_reviews(p)
    observation=next(o for o in accepted['observations'] if o['native_id']=='P1')
    # Historical imported duplicate work is a boundary fixture, not created by confirmation.
    case_ids=[]
    with store.db() as conn:
        template=dict(conn.execute('SELECT * FROM work_case ORDER BY id LIMIT 1').fetchone())
        for owner in ('Legacy A','Legacy B'):
            cid=uuid.uuid4().hex;case_ids.append(cid)
            evidence={'original':observation['original'],'normalized':observation['normalized'],'receipt_id':payer['id'],
                      'observation_id':observation['id'],'source':'payer','designation':'synthetic','locator':observation['locator'],
                      'listing_value':'2125550199','reference_value':None}
            row={**template,'id':cid,'kind':'correction','identity_key':cid,'field_name':'phone','provider_name':'Alex Example',
                 'location_id':p['office'],'owner':owner,'status':'new','version':0,'evidence':packed(evidence),'proposal':None,'observed':None,
                 'created_at':now(),'updated_at':now()}
            conn.execute('INSERT INTO work_case ('+','.join(row)+') VALUES ('+','.join('?' for _ in row)+')',tuple(row.values()))
            conn.execute('INSERT INTO work_evidence VALUES (?,?)',(cid,observation['id']))
    proposal,plan=proposal_and_plan(p)
    assert plan['blocked_count']==1
    blocked=next(a for a in plan['actions'] if a['action']=='blocked')
    assert {case['id'] for case in blocked['available_cases']}==set(case_ids)
    service=FollowUp(store)
    with pytest.raises(Conflict,match='ambiguous'):service.confirm(confirmation(proposal,plan))
    choices={blocked['target_key']:case_ids[0]}
    selected=service.preview(proposal['id'],case_choices=choices,limit=100)
    assert selected['blocked_count']==0
    saved=service.confirm(confirmation(proposal,selected,case_choices=choices))
    receipt=service.get(saved['id'],limit=100)
    assert any(t['case']['id']==case_ids[0] and t['case']['owner']=='Legacy A' for t in receipt['targets'])
    assert store.case(case_ids[1])['owner']=='Legacy B'
