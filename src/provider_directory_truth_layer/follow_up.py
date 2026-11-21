"""Explicit atomic confirmation, scoped work association and separate acknowledgement."""
from __future__ import annotations

import json

from .change_impact import ChangeImpact, proposal_record
from .intake_store import Conflict, digest, now, packed, uid
from .reconciliation_store import page_parameters, sample_record

MIGRATION_10='''
CREATE TABLE follow_up_confirmation (
 id TEXT PRIMARY KEY, proposal_id TEXT NOT NULL UNIQUE REFERENCES change_proposal(id),
 request_id TEXT NOT NULL UNIQUE, request_hash TEXT NOT NULL, intent_hash TEXT NOT NULL,
 impact_snapshot TEXT NOT NULL, plan_snapshot TEXT NOT NULL,
 assessment TEXT NOT NULL, plan TEXT NOT NULL, actor TEXT NOT NULL, reason TEXT NOT NULL, created_at TEXT NOT NULL);
CREATE TABLE follow_up_association (
 id TEXT PRIMARY KEY, confirmation_id TEXT NOT NULL REFERENCES follow_up_confirmation(id),
 proposal_id TEXT NOT NULL REFERENCES change_proposal(id), target_key TEXT NOT NULL,
 field TEXT NOT NULL, case_id TEXT NOT NULL REFERENCES work_case(id), refs TEXT NOT NULL,
 evidence TEXT NOT NULL, case_version_at_confirmation INTEGER NOT NULL,
 action TEXT NOT NULL CHECK(action IN ('create','reuse')), actor TEXT NOT NULL, reason TEXT NOT NULL, created_at TEXT NOT NULL,
 UNIQUE(proposal_id,target_key,field));
CREATE INDEX follow_up_target_work ON follow_up_association(target_key,case_id);
CREATE TABLE follow_up_acknowledgement (
 seq INTEGER PRIMARY KEY AUTOINCREMENT, id TEXT NOT NULL UNIQUE,
 association_id TEXT NOT NULL REFERENCES follow_up_association(id), request_id TEXT NOT NULL UNIQUE,
 request_hash TEXT NOT NULL, previous_id TEXT REFERENCES follow_up_acknowledgement(id),
 case_version INTEGER NOT NULL, actor TEXT NOT NULL, reason TEXT NOT NULL, created_at TEXT NOT NULL);
CREATE INDEX follow_up_ack_history ON follow_up_acknowledgement(association_id,seq DESC);
'''
for table in ('follow_up_confirmation','follow_up_association','follow_up_acknowledgement'):
    for action in ('UPDATE','DELETE'):
        MIGRATION_10+=f"CREATE TRIGGER {table}_no_{action.lower()} BEFORE {action} ON {table} BEGIN SELECT RAISE(ABORT,'Immutable {table}'); END;\n"


def target_identity(conn,proposal,target,cache=None):
    """A source-native target when explicit/unique; otherwise exact retained evidence."""
    cache={} if cache is None else cache
    attempt_id=target['attempt_id']
    if attempt_id not in cache:
        attempt=conn.execute('SELECT spec,preview FROM attempt WHERE id=?',(attempt_id,)).fetchone()
        spec=json.loads(attempt['spec']);rows=json.loads(attempt['preview'])['rows']
        column=spec.get('mapping',{}).get('record_id','record_id')
        native={}
        counts={}
        for row in rows:
            original=row['original']
            value=original.get(column) if spec.get('profile')=='flat' else original.get('number') if spec.get('profile')=='nppes' else None
            key=str(value).strip() if (isinstance(value,str) or type(value) is int) and str(value).strip() else None
            location_column=spec.get('mapping',{}).get('location_id','location_id')
            raw_location=original.get(location_column) if spec.get('profile')=='flat' else None
            source_location=str(raw_location).strip() if (isinstance(raw_location,str) or type(raw_location) is int) and str(raw_location).strip() else None
            part=row['normalized'].get('participation') or {}
            identity=(key,part.get('network_id'),source_location)
            native[row['locator']]={'key':key,'identity':identity,'source_location':source_location,'organization_id':part.get('organization_id')}
            if key is not None:counts[identity]=counts.get(identity,0)+1
        cache[attempt_id]={'native':native,'counts':counts,'rows':{r['locator']:r for r in rows}}
    info=cache[attempt_id]
    source_identity=info['native'][target['locator']]
    native=source_identity['key']
    if native is not None and info['counts'][source_identity['identity']]!=1:native=None
    pin=next(pin for pin in proposal['inputs'] if pin['receipt_id']==target['receipt_id'])
    scope={'clinician_id':proposal['clinician_id'],'location_id':proposal['location_id'],'field':proposal['field'],
           'source':target['source'],'profile':pin['profile'],'comparison_scope':pin['comparison_scope'],
           'lookup_query':pin.get('lookup_query'),'network_id':target.get('network_id'),
           'organization_id':source_identity['organization_id'],'source_location_key':source_identity['source_location'],
           'native_id':native,'retained_ref':target['ref'] if native is None else None}
    return digest(scope),scope


def case_scopes(conn,case_id):
    """Follow-up context stays distinct from source-asserted participation scope."""
    result={}
    for row in conn.execute('SELECT target_key,confirmation_id,evidence FROM follow_up_association WHERE case_id=? ORDER BY created_at,id',(case_id,)):
        evidence=json.loads(row['evidence']);scope=evidence['scope']
        def label(table,key):
            found=conn.execute(f'SELECT label FROM {table} WHERE id=?',(key,)).fetchone() if key else None
            return found['label'] if found else None
        result[row['target_key']]={'kind':'follow_up','target_key':row['target_key'],'confirmation_id':row['confirmation_id'],
            'source':scope['source'],'field':scope['field'],'clinician_id':scope['clinician_id'],
            'clinician_label':label('clinician_identity',scope['clinician_id']),
            'network_id':scope['network_id'],'network_label':label('network',scope['network_id']),
            'organization_id':scope.get('organization_id'),'organization_label':label('organization',scope.get('organization_id')),
            'practice_location_id':scope['location_id'],'location_label':label('practice_location',scope['location_id']),
            'native_id':scope['native_id'],'source_location_key':scope.get('source_location_key'),'retained_ref':scope['retained_ref']}
    return list(result.values())


def enrich_work_export(conn,cases,result):
    """Project follow-up associations without inventing participation observations."""
    result.update(follow_up_scopes=[],follow_up_associations=[],follow_up_acknowledgements=[],follow_up_confirmations=[])
    receipts=set();confirmations=set()
    for case in cases:
        scopes=[scope for scope in case_scopes(conn,case['id']) if not result.get('network_id') or scope['network_id']==result['network_id']]
        case['follow_up_scopes']=scopes
        result['follow_up_scopes'].extend({'case_id':case['id'],**scope} for scope in scopes)
        for row in conn.execute('SELECT * FROM follow_up_association WHERE case_id=? ORDER BY created_at,id',(case['id'],)):
            association=decode_association(row)
            if result.get('network_id') and association['evidence']['scope']['network_id']!=result['network_id']:continue
            result['follow_up_associations'].append(association);confirmations.add(association['confirmation_id'])
            receipts.update(target['receipt_id'] for target in association['evidence']['targets'])
            result['follow_up_acknowledgements'].extend(dict(ack) for ack in conn.execute('SELECT * FROM follow_up_acknowledgement WHERE association_id=? ORDER BY seq',(association['id'],)))
    for confirmation in sorted(confirmations):
        item=dict(conn.execute('''SELECT c.id,c.proposal_id,c.impact_snapshot,c.plan_snapshot,c.actor,c.reason,c.created_at,
            p.field,p.clinician_id,p.location_id,p.proposed_original,p.proposed_value FROM follow_up_confirmation c
            JOIN change_proposal p ON p.id=c.proposal_id WHERE c.id=?''',(confirmation,)).fetchone())
        for key in ('proposed_original','proposed_value'):item[key]=json.loads(item[key])
        result['follow_up_confirmations'].append(item)
    desired={'networks':set(),'locations':set(),'organizations':set()}
    for scope in result['follow_up_scopes']:
        for group,key in (('networks','network_id'),('locations','practice_location_id'),('organizations','organization_id')):
            if scope.get(key):desired[group].add(scope[key])
    for group,table in (('networks','network'),('locations','practice_location'),('organizations','organization')):
        present={item['id'] for item in result['catalog'][group]}
        for identifier in sorted(desired[group]-present):
            item=dict(conn.execute(f'SELECT * FROM {table} WHERE id=?',(identifier,)).fetchone())
            if group!='locations':item['identifiers']=json.loads(item['identifiers'])
            result['catalog'][group].append(item)
            if group=='networks' and item['payer_organization_id']:desired['organizations'].add(item['payer_organization_id'])
            if group=='locations' and item['organization_id']:desired['organizations'].add(item['organization_id'])
    return receipts


def case_summary(row):
    return {key:row[key] for key in ('id','kind','field_name','owner','status','version','proposal','observed')}


def public_target(target,limit):
    item,clipped=sample_record(target,limit)
    # IDs, references, case versions and choices are control metadata, not samples.
    item['refs']=target['refs']
    def case_display(case):
        value=dict(case)
        for key in ('owner','proposal','observed'):
            if isinstance(value.get(key),str) and len(value[key])>512:
                value[key]=value[key][:512]+' [sample truncated]'
        return value
    if 'available_cases' in target:
        item['available_cases']=[case_display(case) for case in target['available_cases']]
    if 'case' in target:item['case']=case_display(target['case'])
    if target.get('latest_ack') is not None:
        item['latest_ack'],cut=sample_record(target['latest_ack'],1)
        clipped |= cut
    retained=target.get('targets',[])
    samples=[sample_record(record,limit) for record in retained[:3]]
    item['targets']=[sample[0] for sample in samples]
    item['target_count']=len(retained)
    return item,clipped or len(retained)>3 or any(sample[1] for sample in samples)


def decode_association(row):
    result=dict(row)
    for key in ('refs','evidence'):result[key]=json.loads(result[key])
    return result


def required(payload,keys):
    for key in keys:
        if not isinstance(payload.get(key),str) or not payload[key].strip() or len(payload[key])>4096:
            raise ValueError(key+' must be a nonblank string of at most4096 characters')


class FollowUp:
    def __init__(self,store):
        self.store=store
        self.impact=ChangeImpact(store)

    def _plan(self,conn,proposal_id,choices):
        if not isinstance(choices,dict) or len(choices)>5000 or any(not isinstance(k,str) or not isinstance(v,str) for k,v in choices.items()):
            raise ValueError('Case choices must map exact target keys to case IDs or new')
        assessment=self.impact._assess(conn,proposal_id)
        proposal=proposal_record(conn.execute('SELECT * FROM change_proposal WHERE id=?',(proposal_id,)).fetchone(),True)
        groups={};cache={}
        for target in assessment['targets']:
            if target['classification']!='affected':continue
            key,scope=target_identity(conn,proposal,target,cache)
            group=groups.setdefault(key,{'target_key':key,'scope':scope,'refs':[],'targets':[],
                'source':target['source'],'network_id':target.get('network_id'),'network_label':target.get('network_label'),
                'field':proposal['field']})
            group['refs'].append(target['ref']);group['targets'].append(target)
        if set(choices)-set(groups):raise ValueError('Case choice does not belong to an affected target')
        actions=[]
        for key,group in sorted(groups.items()):
            case_ids={item['id'] for item in assessment['existing_work'] if item['classification']=='affected'
                      and item['field_name']==proposal['field'] and set(item['refs'])&set(group['refs'])}
            case_ids.update(row['case_id'] for row in conn.execute('SELECT DISTINCT case_id FROM follow_up_association WHERE target_key=?',(key,)))
            cases=[]
            for case_id in sorted(case_ids):
                row=conn.execute('SELECT * FROM work_case WHERE id=?',(case_id,)).fetchone()
                if row is not None and row['field_name']==proposal['field']:
                    cases.append({**case_summary(row),'eligible_for_reuse':row['status'] not in {'resolved','verified'}})
            eligible=[case for case in cases if case['eligible_for_reuse']]
            selected=choices.get(key)
            action,case,reason='create',None,'No open matching work; create a separate QA review without reopening closed cases'
            if selected=='new' and eligible:
                raise ValueError('Reuse an existing open matching case rather than creating duplicate follow-up')
            if selected and selected!='new':
                case=next((case for case in eligible if case['id']==selected),None)
                if case is None:raise ValueError('Select an eligible open case for this exact target')
                action,reason='reuse','Explicit selected work; preserve its owner, status, proposal and initial evidence'
            elif len(eligible)==1:
                case=eligible[0];action,reason='reuse','Existing matching work; preserve its owner, status, proposal and initial evidence'
            elif len(eligible)>1:
                action,reason='blocked','Several open cases match; explicitly select one before confirmation'
            actions.append({**group,'action':action,'case_id':case['id'] if case else None,
                            'case_version':case['version'] if case else None,'available_cases':cases,'reason':reason})
        plan_snapshot=digest([assessment['snapshot'],choices,actions])
        return {'proposal_id':proposal_id,'impact_snapshot':assessment['snapshot'],'plan_snapshot':plan_snapshot,
                'inputs_fresh':assessment['inputs_fresh'],'stale_reasons':assessment['stale_reasons'],
                'counts':assessment['counts'],'actions':actions,'blocked_count':sum(a['action']=='blocked' for a in actions),
                'notice':'Confirmation creates QA review work or associates existing work. Acknowledgement is separate from closure and verification.'},assessment,proposal

    def preview(self,proposal_id,case_choices=None,offset=0,limit=20):
        page_parameters(offset,limit)
        with self.store.db() as conn:
            conn.execute('BEGIN');plan,_,_=self._plan(conn,proposal_id,case_choices or {})
        plan['total']=len(plan['actions']);plan['next_offset']=offset+limit if offset+limit<plan['total'] else None
        samples=[public_target(action,limit) for action in plan['actions'][offset:offset+limit]]
        plan['actions']=[sample[0] for sample in samples];plan['sample_truncated']=any(sample[1] for sample in samples)
        return plan

    @staticmethod
    def _saved(conn,confirmation_id):
        row=conn.execute('SELECT * FROM follow_up_confirmation WHERE id=?',(confirmation_id,)).fetchone()
        result={key:row[key] for key in ('id','proposal_id','impact_snapshot','plan_snapshot','actor','reason','created_at')}
        result['counts']=json.loads(row['assessment'])['counts']
        result['association_count']=conn.execute('SELECT count(*) FROM follow_up_association WHERE confirmation_id=?',(confirmation_id,)).fetchone()[0]
        return result

    def _create_case(self,conn,proposal,action,confirmation_id,actor,reason):
        target=action['targets'][0]
        attempt=conn.execute('SELECT preview FROM attempt WHERE id=?',(target['attempt_id'],)).fetchone()
        row=next(row for row in json.loads(attempt['preview'])['rows'] if row['locator']==target['locator'])
        identity=conn.execute('SELECT label FROM clinician_identity WHERE id=?',(proposal['clinician_id'],)).fetchone()
        source_receipt=conn.execute('SELECT designation FROM receipt WHERE id=?',(target['receipt_id'],)).fetchone()
        evidence={'original':row['original'],'normalized':row['normalized'],'locator':target['locator'],
            'observation_id':None,'attempt_id':target['attempt_id'],
            'receipt_id':target['receipt_id'],'source':target['source'],'designation':source_receipt['designation'],
            **({key:target[key] for key in ('supporting_refs','source_network_reference','native_validation') if key in target}),
            'listing_value':target['value'],'reference_value':None,
            'follow_up':{'confirmation_id':confirmation_id,'proposal_id':proposal['id'],'target_key':action['target_key'],
                         'scope':action['scope'],'refs':action['refs'],'proposed_value':proposal['proposed_value'],
                         'notice':'Proposed review work only; no acceptance, source update or verification.'}}
        case_id=uid();timestamp=now()
        conn.execute('''INSERT INTO work_case
            (id,kind,identity_key,provider_name,location_id,field_name,issue,risk_level,risk_reason,status,
             owner,follow_up,version,evidence,proposal,observed,created_at,updated_at)
             VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)''',
            (case_id,'qa',digest(['follow_up',action['target_key'],confirmation_id]),identity['label'],proposal['location_id'],
             proposal['field'],'Review proposed '+proposal['field']+' for '+target['source'],'medium',
             'Explicitly confirmed known dependency; source assertion is not verified','new',None,None,0,packed(evidence),None,None,timestamp,timestamp))
        conn.execute('''INSERT INTO work_event (case_id,action,actor,reason,payload,from_status,to_status,occurred_at)
            VALUES (?,?,?,?,?,?,?,?)''',(case_id,'follow_up_created',actor,reason,packed(evidence['follow_up']),'new','new',timestamp))
        return case_id

    def confirm(self,payload):
        allowed={'proposal_id','expected_snapshot','expected_plan','case_choices','request_id','actor','reason','confirm'}
        if not isinstance(payload,dict) or set(payload)-allowed:raise ValueError('Unknown follow-up confirmation fields')
        required(payload,('proposal_id','expected_snapshot','expected_plan','request_id','actor','reason'))
        if payload.get('confirm') is not True:raise ValueError('Explicit confirm=true is required')
        choices=payload.get('case_choices',{})
        request_hash=digest(payload);intent_hash=digest({k:v for k,v in payload.items() if k!='request_id'})
        with self.store.db() as conn:
            conn.execute('BEGIN IMMEDIATE')
            old=conn.execute('SELECT * FROM follow_up_confirmation WHERE request_id=?',(payload['request_id'],)).fetchone()
            if old:
                if old['request_hash']!=request_hash:raise Conflict('Request ID already used with different confirmation content')
                return self._saved(conn,old['id'])
            old=conn.execute('SELECT * FROM follow_up_confirmation WHERE proposal_id=?',(payload['proposal_id'],)).fetchone()
            if old:
                if old['intent_hash']!=intent_hash:raise Conflict('Proposal already confirmed; inspect its saved plan or create a revised proposal')
                return self._saved(conn,old['id'])
            plan,assessment,proposal=self._plan(conn,payload['proposal_id'],choices)
            if not plan['inputs_fresh'] or plan['impact_snapshot']!=payload['expected_snapshot'] or plan['plan_snapshot']!=payload['expected_plan']:
                raise Conflict('Impact, source, reviewed links or work versions changed; inspect a fresh plan')
            if plan['blocked_count']:raise Conflict('Choose an existing case for each ambiguous target')
            confirmation_id=uid();timestamp=now()
            conn.execute('INSERT INTO follow_up_confirmation VALUES (?,?,?,?,?,?,?,?,?,?,?,?)',
                (confirmation_id,proposal['id'],payload['request_id'],request_hash,intent_hash,plan['impact_snapshot'],plan['plan_snapshot'],
                 packed(assessment),packed(plan),payload['actor'],payload['reason'],timestamp))
            for action in plan['actions']:
                case_id=action['case_id'] if action['action']=='reuse' else self._create_case(conn,proposal,action,confirmation_id,payload['actor'],payload['reason'])
                version=conn.execute('SELECT version FROM work_case WHERE id=?',(case_id,)).fetchone()[0]
                conn.execute('INSERT INTO follow_up_association VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)',
                    (uid(),confirmation_id,proposal['id'],action['target_key'],proposal['field'],case_id,packed(action['refs']),
                     packed(action),version,action['action'],payload['actor'],payload['reason'],timestamp))
            return self._saved(conn,confirmation_id)

    def list(self,proposal_id=None,offset=0,limit=20):
        page_parameters(offset,limit)
        with self.store.db() as conn:
            conn.execute('BEGIN')
            where,params=('proposal_id=?',[proposal_id]) if proposal_id is not None else ('1=1',[])
            total=conn.execute('SELECT count(*) FROM follow_up_confirmation WHERE '+where,params).fetchone()[0]
            items=[dict(row) for row in conn.execute('SELECT id,proposal_id,actor,reason,created_at FROM follow_up_confirmation WHERE '+where+' ORDER BY created_at DESC,id DESC LIMIT ? OFFSET ?',(*params,limit,offset))]
        return {'items':items,'total':total,'next_offset':offset+limit if offset+limit<total else None}

    def _receipt(self,conn,confirmation_id):
        row=conn.execute('SELECT * FROM follow_up_confirmation WHERE id=?',(confirmation_id,)).fetchone()
        if row is None:raise KeyError('Follow-up confirmation not found')
        current=self.impact._assess(conn,row['proposal_id'])
        associations=[decode_association(a) for a in conn.execute('SELECT * FROM follow_up_association WHERE confirmation_id=? ORDER BY target_key',(confirmation_id,))]
        targets=[]
        for association in associations:
            case=conn.execute('SELECT * FROM work_case WHERE id=?',(association['case_id'],)).fetchone()
            ack=conn.execute('SELECT * FROM follow_up_acknowledgement WHERE association_id=? ORDER BY seq DESC LIMIT 1',(association['id'],)).fetchone()
            target={**association['evidence'],'association_id':association['id'],'case':case_summary(case),
                    'case_version_at_confirmation':association['case_version_at_confirmation'],
                    'latest_ack':dict(ack) if ack else None,
                    'ack_count':conn.execute('SELECT count(*) FROM follow_up_acknowledgement WHERE association_id=?',(association['id'],)).fetchone()[0]}
            targets.append(target)
        snapshot=digest([confirmation_id,current['snapshot'],[(t['association_id'],t['case']['version'],t['latest_ack']['id'] if t['latest_ack'] else None) for t in targets]])
        return {**self._saved(conn,confirmation_id),'snapshot':snapshot,'scope':current['scope'],
                'source_inputs_fresh':current['inputs_fresh'],'source_stale_reasons':current['stale_reasons'],
                'targets':targets,'total':len(targets),
                'notice':'Saved confirmation is historical evidence. Current case state and acknowledgement do not certify source correctness.'}

    def get(self,confirmation_id,offset=0,limit=20):
        page_parameters(offset,limit)
        with self.store.db() as conn:
            conn.execute('BEGIN');result=self._receipt(conn,confirmation_id)
        samples=[public_target(target,limit) for target in result['targets'][offset:offset+limit]]
        result['targets']=[sample[0] for sample in samples];result['sample_truncated']=any(sample[1] for sample in samples)
        result['next_offset']=offset+limit if offset+limit<result['total'] else None
        return result

    def acknowledge(self,confirmation_id,payload):
        allowed={'association_id','expected_ack_id','expected_case_version','request_id','actor','reason'}
        if not isinstance(payload,dict) or set(payload)-allowed:raise ValueError('Unknown acknowledgement fields')
        required(payload,('association_id','request_id','actor','reason'))
        if 'expected_ack_id' not in payload or (payload['expected_ack_id'] is not None and not isinstance(payload['expected_ack_id'],str)) or type(payload.get('expected_case_version')) is not int:
            raise ValueError('Supply the current acknowledgement ID/null and exact case version')
        request_hash=digest([confirmation_id,payload])
        with self.store.db() as conn:
            conn.execute('BEGIN IMMEDIATE')
            old=conn.execute('SELECT * FROM follow_up_acknowledgement WHERE request_id=?',(payload['request_id'],)).fetchone()
            if old:
                if old['request_hash']!=request_hash:raise Conflict('Request ID already used with different acknowledgement content')
                return dict(old)
            association=conn.execute('SELECT * FROM follow_up_association WHERE id=? AND confirmation_id=?',(payload['association_id'],confirmation_id)).fetchone()
            if association is None:raise KeyError('Association not found in this confirmed plan')
            latest=conn.execute('SELECT id FROM follow_up_acknowledgement WHERE association_id=? ORDER BY seq DESC LIMIT 1',(association['id'],)).fetchone()
            version=conn.execute('SELECT version FROM work_case WHERE id=?',(association['case_id'],)).fetchone()[0]
            if version!=payload['expected_case_version'] or payload['expected_ack_id']!=(latest['id'] if latest else None):
                raise Conflict('Case or acknowledgement changed; inspect current plan state')
            ack_id=uid()
            conn.execute('''INSERT INTO follow_up_acknowledgement
                (id,association_id,request_id,request_hash,previous_id,case_version,actor,reason,created_at) VALUES (?,?,?,?,?,?,?,?,?)''',
                (ack_id,association['id'],payload['request_id'],request_hash,latest['id'] if latest else None,version,payload['actor'],payload['reason'],now()))
            return dict(conn.execute('SELECT * FROM follow_up_acknowledgement WHERE id=?',(ack_id,)).fetchone())

    def acknowledgements(self,confirmation_id,association_id=None,offset=0,limit=20):
        page_parameters(offset,limit)
        with self.store.db() as conn:
            conn.execute('BEGIN')
            if conn.execute('SELECT id FROM follow_up_confirmation WHERE id=?',(confirmation_id,)).fetchone() is None:raise KeyError('Confirmation not found')
            where,params='a.confirmation_id=?',[confirmation_id]
            if association_id is not None:
                if not conn.execute('SELECT id FROM follow_up_association WHERE id=? AND confirmation_id=?',(association_id,confirmation_id)).fetchone():raise KeyError('Association not found in this plan')
                where+=' AND a.id=?';params.append(association_id)
            query=' FROM follow_up_acknowledgement k JOIN follow_up_association a ON a.id=k.association_id WHERE '+where
            total=conn.execute('SELECT count(*)'+query,params).fetchone()[0]
            items=[dict(row) for row in conn.execute('SELECT k.*'+query+' ORDER BY k.seq DESC LIMIT ? OFFSET ?',(*params,limit,offset))]
        return {'items':items,'total':total,'next_offset':offset+limit if offset+limit<total else None}

    def export(self,confirmation_id,expected_snapshot):
        with self.store.db() as conn:
            conn.execute('BEGIN');receipt=self._receipt(conn,confirmation_id)
            if receipt['snapshot']!=expected_snapshot:raise Conflict('Plan/source/work/acknowledgement snapshot changed; refresh before export')
            confirmation=dict(conn.execute('SELECT * FROM follow_up_confirmation WHERE id=?',(confirmation_id,)).fetchone())
            confirmation['assessment']=json.loads(confirmation['assessment']);confirmation['plan']=json.loads(confirmation['plan'])
            proposal=proposal_record(conn.execute('SELECT * FROM change_proposal WHERE id=?',(confirmation['proposal_id'],)).fetchone(),True)
            associations=[decode_association(row) for row in conn.execute('SELECT * FROM follow_up_association WHERE confirmation_id=? ORDER BY target_key',(confirmation_id,))]
            cases=[]
            for case_id in sorted({a['case_id'] for a in associations}):
                case=dict(conn.execute('SELECT * FROM work_case WHERE id=?',(case_id,)).fetchone());case['evidence']=json.loads(case['evidence'])
                events=[dict(row) for row in conn.execute('SELECT * FROM work_event WHERE case_id=? ORDER BY id',(case_id,))]
                for event in events:event['payload']=json.loads(event['payload'])
                case['events']=events;cases.append(case)
            acknowledgements=[dict(row) for row in conn.execute('''SELECT k.* FROM follow_up_acknowledgement k JOIN follow_up_association a ON a.id=k.association_id
                WHERE a.confirmation_id=? ORDER BY k.seq''',(confirmation_id,))]
            contexts=[];selected_context={}
            def include_context(attempt_id,locator,receipt_id,role):
                selected_context.setdefault((attempt_id,locator),{'receipt_id':receipt_id,'roles':set()})['roles'].add(role)
            from .fhir_store import context_refs
            def include_record(record, role):
                for attempt_id, locator in context_refs(record):
                    include_context(attempt_id, locator, record['receipt_id'], role)
            for record in proposal['records']:
                include_record(record,'assessment_input')
            prior=proposal['prior_evidence']['field']
            for option in prior['options']:
                include_record(option,'prior_field_assertion')
            for decision in prior['history']:
                evidence=decision['evidence']
                for option in (evidence.get('options',[]) if decision['decision']=='conflict' else [evidence]):
                    include_record(option,'historical_field_decision')
            initial_receipts={}
            for case in cases:
                evidence=case['evidence'];receipt_id=evidence['receipt_id']
                source=dict(conn.execute('SELECT * FROM receipt WHERE id=?',(receipt_id,)).fetchone())
                source['metadata']=json.loads(source['metadata']);initial_receipts[receipt_id]=source
                origin=conn.execute('SELECT attempt_id,locator FROM observation WHERE id=?',(evidence.get('observation_id'),)).fetchone()
                if origin:include_context(origin['attempt_id'],origin['locator'],receipt_id,'initial_work_evidence')
                elif evidence.get('attempt_id'):include_context(evidence['attempt_id'],evidence['locator'],receipt_id,'initial_work_evidence')
            for key,context in sorted(selected_context.items()):
                attempt=conn.execute('SELECT spec,preview FROM attempt WHERE id=?',(key[0],)).fetchone()
                source_row=next(r for r in json.loads(attempt['preview'])['rows'] if r['locator']==key[1])
                source_receipt=dict(conn.execute('SELECT * FROM receipt WHERE id=?',(context['receipt_id'],)).fetchone());source_receipt['metadata']=json.loads(source_receipt['metadata'])
                contexts.append({'receipt':source_receipt,'attempt_id':key[0],'spec':json.loads(attempt['spec']),'row':source_row,'roles':sorted(context['roles'])})
        return {'format_version':1,'snapshot':receipt['snapshot'],'confirmation':confirmation,'proposal':proposal,
                'associations':associations,'cases':cases,'acknowledgements':acknowledgements,'source_context':contexts,
                'initial_work_receipt_context':[initial_receipts[key] for key in sorted(initial_receipts)],
                'current_source_inputs_fresh':receipt['source_inputs_fresh'],'source_stale_reasons':receipt['source_stale_reasons'],
                'notice':'Full selected plan and source context; original rows may contain unselected native addresses. Acknowledgement and QA disposition are not source verification or external updates.'}
