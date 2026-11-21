"""Immutable typed proposals and read-only impact over explicitly retained scope."""
from __future__ import annotations

import json
import re

from .comparison import RULE_VERSION, cleanse
from .field_reconciliation import FieldReconciliation, field_option
from .intake_store import Conflict, digest, now, packed, uid
from .normalization_recipes import _apply
from .reconciliation_store import MAX_RECORDS, ReconciliationStore, page_parameters, sample_record

MIGRATION_9 = '''
CREATE TABLE change_proposal (
 seq INTEGER PRIMARY KEY AUTOINCREMENT, id TEXT NOT NULL UNIQUE,
 request_id TEXT NOT NULL UNIQUE, request_hash TEXT NOT NULL,
 clinician_id TEXT NOT NULL REFERENCES clinician_identity(id), location_id TEXT REFERENCES practice_location(id),
 field TEXT NOT NULL, proposed_original TEXT NOT NULL, proposed_value TEXT NOT NULL,
 prior_evidence TEXT NOT NULL, field_snapshot TEXT NOT NULL,
 inputs TEXT NOT NULL, records TEXT NOT NULL, baseline_snapshot TEXT NOT NULL,
 network_ids TEXT NOT NULL, rule_version TEXT NOT NULL,
 previous_id TEXT REFERENCES change_proposal(id), root_id TEXT NOT NULL,
 actor TEXT NOT NULL, reason TEXT NOT NULL, created_at TEXT NOT NULL,
 CHECK((location_id IS NULL AND field IN ('provider_name','npi'))
 OR (location_id IS NOT NULL AND field IN ('phone','address'))));
CREATE INDEX change_proposal_scope ON change_proposal(clinician_id,location_id,seq DESC);
'''
for action in ('UPDATE','DELETE'):
    MIGRATION_9 += f"CREATE TRIGGER change_proposal_no_{action.lower()} BEFORE {action} ON change_proposal BEGIN SELECT RAISE(ABORT,'Immutable change proposals'); END;\n"


def normalized_value(field, value):
    """A typed proposed target, not an instruction to mutate any source."""
    if field=='phone':
        if not isinstance(value,dict) or set(value)-{'number','extension'} or not isinstance(value.get('number'),str) or len(value['number'])>128:
            raise ValueError('Phone requires number and optional extension')
        number,derived=_apply(value['number'],{'op':'phone_us'})
        if not isinstance(number,str) or not re.fullmatch(r'[0-9]{10}',number):
            raise ValueError('Proposed phone requires a substantive ten-digit number')
        extension=value.get('extension')
        if extension is not None and (not isinstance(extension,str) or not re.fullmatch(r'[0-9]{1,10}',extension)):
            raise ValueError('Extension must be null or 1..10 digits')
        if derived and extension and derived!=extension:
            raise ValueError('Conflicting phone extensions')
        return {'number':number,'extension':extension if extension is not None else derived}
    if field=='address':
        keys={'line1','line2','suite','city','state','zip'}
        if not isinstance(value,dict) or set(value)-keys or any(value.get(k) is not None and (not isinstance(value[k],str) or len(value[k])>512) for k in keys):
            raise ValueError('Address requires one coherent source-shaped component object')
        if any(not isinstance(value.get(k),str) or not value[k].strip() for k in ('line1','city','state','zip')):
            raise ValueError('Supply line1, city, state and ZIP')
        address={k:value.get(k) for k in keys}
        address['state']=_apply(address['state'],{'op':'state_us'})[0]
        address['zip']=_apply(address['zip'],{'op':'zip_us'})[0]
        evidence=cleanse({'address':{**address,'kind':'practice'}})
        if any(code.startswith('invalid_') or code=='suite_assertion_conflict' for codes in evidence['field_findings'].values() for code in codes):
            raise ValueError('Address contains invalid or conflicting components')
        return {k:evidence['comparison']['address'][k] for k in sorted(keys)}
    if field not in {'provider_name','npi'} or not isinstance(value,str) or not value.strip() or len(value)>512:
        raise ValueError('Supply a supported nonblank clinician field')
    if field=='npi' and not re.fullmatch(r'[0-9]{10}',value):
        raise ValueError('NPI must be ten ASCII digits; shape does not certify identity')
    return cleanse({field:value})['comparison'][field]


def proposal_record(row, include_records=False):
    result=dict(row)
    for key in ('proposed_original','proposed_value','prior_evidence','inputs','records','baseline_snapshot','network_ids'):
        result[key]=json.loads(result[key])
    if not include_records:
        result['record_count']=len(result.pop('records'))
    return result


def public_proposal(row):
    """Keep current prior-decision metadata intact while bounding bulky evidence."""
    from .evidence_samples import sample_value
    result=proposal_record(row)
    prior=result['prior_evidence']
    field=prior['field']
    decision,clipped=sample_record(field['decision'],1) if field['decision'] else (None,False)
    preferred,truncated=sample_value(field['preferred_value'])
    sampled=[sample_record(option,20) for option in field['options'][:20]]
    options=[item[0] for item in sampled]
    cut=any(item[1] for item in sampled)
    result['prior_evidence']={'scope':prior['scope'],'evidence_snapshot':prior['evidence_snapshot'],
                             'field':{'field':field['field'],'status':field['status'],'decision':decision,
                                      'preferred_value':preferred,'options':options,'option_count':field['option_count']},
                             'link_count':len(prior['links'])}
    result['prior_evidence_sampled']=True
    result['sample_truncated']=clipped or truncated or cut or len(field['options'])>20
    return result


class ChangeImpact:
    def __init__(self, store):
        self.store=store
        self.fields=FieldReconciliation(store)
        self.comparison=ReconciliationStore(store)

    def create(self,payload):
        allowed={'clinician_id','location_id','field','proposed_value','inputs','network_ids','expected_snapshot','request_id','actor','reason','previous_id'}
        if not isinstance(payload,dict) or set(payload)-allowed:
            raise ValueError('Unknown change proposal fields')
        for key in ('clinician_id','field','expected_snapshot','request_id','actor','reason'):
            if not isinstance(payload.get(key),str) or not payload[key].strip() or len(payload[key])>4096:
                raise ValueError(key+' must be a nonblank string of at most 4096 characters')
        for key in ('location_id','previous_id'):
            if payload.get(key) is not None and (not isinstance(payload[key],str) or not payload[key]):
                raise ValueError(key+' must be an ID or null')
        networks=payload.get('network_ids',[])
        if not isinstance(networks,list) or len(networks)>100 or any(not isinstance(n,str) or not n for n in networks) or len(set(networks))!=len(networks):
            raise ValueError('Select at most100 distinct network IDs')
        inputs=payload.get('inputs')
        if not isinstance(inputs,list) or not 1<=len(inputs)<=6:
            raise ValueError('Select one to six retained source interpretations')
        value=normalized_value(payload['field'],payload.get('proposed_value'))
        request_hash=digest(payload)
        # An identical uncertain retry is served before resolving now-stale inputs.
        with self.store.db() as conn:
            saved=conn.execute('SELECT * FROM change_proposal WHERE request_id=?',(payload['request_id'],)).fetchone()
            if saved:
                if saved['request_hash']!=request_hash:raise Conflict('Request ID already used with different proposal content')
                return public_proposal(saved)
        pins,records=[],[]
        for selected in inputs:
            pin,rows=self.comparison._input(selected)
            pins.append(pin)
            records.extend(cleanse(row) for row in rows)
        if len({p['receipt_id'] for p in pins})!=len(pins) or len(records)>MAX_RECORDS:
            raise ValueError('Select each receipt once and at most5000 address references')
        with self.store.db() as conn:
            baseline=self.comparison._snapshot(conn,pins)
        with self.store.db() as conn:
            conn.execute('BEGIN IMMEDIATE')
            saved=conn.execute('SELECT * FROM change_proposal WHERE request_id=?',(payload['request_id'],)).fetchone()
            if saved:
                if saved['request_hash']!=request_hash:raise Conflict('Request ID already used with different proposal content')
                return public_proposal(saved)
            if self.comparison._snapshot(conn,pins)!=baseline or any(s['latest_attempt']!=p['attempt_id'] or s['latest_attempt_state'] in {'failed','rejected','processing','interrupted'} for s,p in zip(baseline,pins)):
                raise Conflict('Assessed source inputs changed; inspect them again')
            view=self.fields._view(conn,payload['clinician_id'],payload.get('location_id'))
            if not view['inputs_fresh'] or view['snapshot']!=payload['expected_snapshot']:
                raise Conflict('Reconciled field snapshot changed; refresh and review')
            field=next((f for f in view['fields'] if f['field']==payload['field']),None)
            if field is None or field['status'] not in {'selected','conflict'}:
                raise ValueError('First explicitly review this field as a selection or retained conflict')
            for network in networks:
                if conn.execute('SELECT id FROM network WHERE id=?',(network,)).fetchone() is None:
                    raise ValueError('Selected network not found')
            previous=None
            if payload.get('previous_id'):
                previous=conn.execute('SELECT * FROM change_proposal WHERE id=?',(payload['previous_id'],)).fetchone()
                if previous is None:raise KeyError('Previous proposal not found')
                if (previous['clinician_id'],previous['location_id'],previous['field'])!=(payload['clinician_id'],payload.get('location_id'),payload['field']):
                    raise ValueError('Revision must retain its clinician/location/field scope')
                if conn.execute('SELECT id FROM change_proposal WHERE previous_id=?',(previous['id'],)).fetchone():
                    raise Conflict('Proposal already superseded; review the latest revision')
            proposal_id=uid()
            prior={'field':field,'scope':view['scope'],'evidence_snapshot':view['evidence_snapshot'],'links':view['links']}
            conn.execute('''INSERT INTO change_proposal
                (id,request_id,request_hash,clinician_id,location_id,field,proposed_original,proposed_value,prior_evidence,
                 field_snapshot,inputs,records,baseline_snapshot,network_ids,rule_version,previous_id,root_id,actor,reason,created_at)
                VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)''',
                (proposal_id,payload['request_id'],request_hash,payload['clinician_id'],payload.get('location_id'),payload['field'],
                 packed(payload['proposed_value']),packed(value),packed(prior),view['snapshot'],packed(pins),packed(records),packed(baseline),
                 packed(sorted(networks)),RULE_VERSION,previous['id'] if previous else None,previous['root_id'] if previous else proposal_id,
                 payload['actor'],payload['reason'],now()))
            return public_proposal(conn.execute('SELECT * FROM change_proposal WHERE id=?',(proposal_id,)).fetchone())

    def get(self,proposal_id):
        with self.store.db() as conn:
            row=conn.execute('SELECT * FROM change_proposal WHERE id=?',(proposal_id,)).fetchone()
            if row is None:raise KeyError('Change proposal not found')
            result=public_proposal(row)
        return result

    def list(self,clinician_id=None,location_id=None,offset=0,limit=20):
        page_parameters(offset,limit)
        where,params='1=1',[]
        if clinician_id is not None:
            where+=' AND clinician_id=? AND location_id IS ?'
            params.extend([clinician_id,location_id])
        with self.store.db() as conn:
            conn.execute('BEGIN')
            total=conn.execute('SELECT count(*) FROM change_proposal WHERE '+where,params).fetchone()[0]
            columns='id,clinician_id,location_id,field,proposed_original,proposed_value,inputs,network_ids,previous_id,root_id,actor,reason,created_at'
            items=[dict(row) for row in conn.execute('SELECT '+columns+' FROM change_proposal WHERE '+where+' ORDER BY seq DESC LIMIT ? OFFSET ?',(*params,limit,offset))]
        # History never hydrates complete retained rows or prior assertion payloads.
        for item in items:
            for key in ('proposed_original','proposed_value','inputs','network_ids'):
                item[key]=json.loads(item[key])
        return {'items':items,'total':total,'next_offset':offset+limit if offset+limit<total else None}

    def _assess(self,conn,proposal_id):
        row=conn.execute('SELECT * FROM change_proposal WHERE id=?',(proposal_id,)).fetchone()
        if row is None:raise KeyError('Change proposal not found')
        proposal=proposal_record(row,True)
        current=self.comparison._snapshot(conn,proposal['inputs'])
        view=self.fields._view(conn,proposal['clinician_id'],proposal['location_id'])
        stale=[]
        if current!=proposal['baseline_snapshot']:stale.append('Selected source interpretation/state or accepted baseline changed')
        if not view['inputs_fresh'] or view['snapshot']!=proposal['field_snapshot']:stale.append('Reviewed field/source/link evidence changed')
        if proposal['rule_version']!=RULE_VERSION:stale.append('Comparison rules changed')
        child=conn.execute('SELECT id FROM change_proposal WHERE previous_id=?',(proposal_id,)).fetchone()
        if child:stale.append('Proposal has a newer revision')
        changed_inputs={pin['receipt_id'] for pin,old,new in zip(proposal['inputs'],proposal['baseline_snapshot'],current) if old!=new}
        links={}
        run_states={}
        evidence_lineages={}
        def evidence_attempt(attempt_id):
            if attempt_id not in evidence_lineages:
                lineage=[]
                current_id=attempt_id
                while True:
                    if current_id in {item[0] for item in lineage}:
                        raise ValueError('Invalid retained observation reuse cycle')
                    selected=conn.execute('SELECT state,preview FROM attempt WHERE id=?',(current_id,)).fetchone()
                    if selected is None:raise ValueError('Missing retained observation reuse evidence')
                    lineage.append((current_id,selected['state']))
                    reused=json.loads(selected['preview']).get('reuses_attempt')
                    if not reused:break
                    current_id=reused
                evidence_lineages[attempt_id]=lineage
            return evidence_lineages[attempt_id][-1][0]
        def latest(kind,ref):
            key=(kind,ref)
            if key not in links:
                found=conn.execute('SELECT * FROM reviewed_identity_link WHERE kind=? AND ref=? ORDER BY seq DESC LIMIT 1',(kind,ref)).fetchone()
                links[key]=dict(found) if found else None
            return links[key]
        def link_fresh(link):
            if not link:return False
            run_id=link['run_id']
            if run_id not in run_states:
                run=conn.execute('SELECT inputs,baseline_snapshot,rule_version FROM comparison_run WHERE id=?',(run_id,)).fetchone()
                snapshot=self.comparison._snapshot(conn,json.loads(run['inputs']))
                run_states[run_id]={'snapshot':snapshot,'fresh':snapshot==json.loads(run['baseline_snapshot']) and run['rule_version']==RULE_VERSION}
            return run_states[run_id]['fresh']
        assessed_records=proposal['records']
        if proposal['location_id'] is None:
            grouped={}
            for record in assessed_records:
                grouped.setdefault(record['clinician_ref'],[]).append(record)
            assessed_records=[{**records[0],'ref':ref,'address_path':'',
                               'address_evidence_refs':[r['ref'] for r in records],
                               'address_evidence_paths':[r['address_path'] for r in records]}
                              for ref,records in grouped.items()]
        targets=[]
        work={}
        from .follow_up import target_identity
        target_cache={}
        for record in sorted(assessed_records,key=lambda r:r['ref']):
            person=latest('clinician',record['clinician_ref'])
            location=latest('location',record['ref']) if proposal['location_id'] is not None else None
            option=field_option(proposal['field'],record,[])
            category,reason='not_assessed','No current reviewed clinician link'
            if record['receipt_id'] in changed_inputs:
                reason='Selected source input is stale'
            elif proposal['network_ids'] and record.get('network_id') not in proposal['network_ids']:
                reason='Outside selected or known network scope'
            elif not person:
                pass
            elif not link_fresh(person):
                reason='Reviewed clinician support is stale'
            elif record['comparison']['entity_kind']=='organization' or record.get('entity_kind_conflict'):
                reason='Incompatible or contradictory source entity type'
            elif person['clinician_id']!=proposal['clinician_id']:
                category,reason='unaffected_within_assessed_scope','Reviewed different clinician'
            elif proposal['location_id'] is not None and not location:
                reason='No current reviewed exact practice-location link'
            elif location and not link_fresh(location):
                reason='Reviewed location support is stale'
            elif location and location['practice_location_id']!=proposal['location_id']:
                category,reason='unaffected_within_assessed_scope','Reviewed different practice location'
            elif not option['selectable']:
                reason='Field contains invalid or internally conflicting source evidence'
            elif option['comparison_value']==proposal['proposed_value']:
                category,reason='unaffected_within_assessed_scope','Retained value already equals proposed value after explicit comparison rules'
            else:
                category,reason='affected','Reviewed target differs from proposed value and may need follow-up'
            network=None
            if record.get('network_id'):
                network=conn.execute('SELECT label FROM network WHERE id=?',(record['network_id'],)).fetchone()
            target={'ref':record['ref'],'clinician_ref':record['clinician_ref'],'source':record['source'],
                    'kind':'clinician' if proposal['location_id'] is None else 'location',
                    'address_evidence_refs':record.get('address_evidence_refs',[record['ref']]),
                    'address_evidence_paths':record.get('address_evidence_paths',[record['address_path']]),
                    'network_id':record.get('network_id'),'network_label':network['label'] if network else None,
                    'classification':category,'reason':reason,'value':option['value'],'comparison_value':option['comparison_value'],
                    'clinician_link':person,'location_link':location,'receipt_id':record['receipt_id'],
                    'attempt_id':record['attempt_id'],'locator':record['locator'],'address_path':record['address_path'],
                    'evidence_attempt_id':evidence_attempt(record['attempt_id']),
                    'evaluation_ref':record.get('evaluation_ref'),'artifact_sha':record['artifact_sha'],
                    **({key:record[key] for key in ('supporting_refs','source_network_reference','native_validation') if key in record})}
            targets.append(target)
            target_key,_=target_identity(conn,proposal,target,target_cache)
            target['target_key']=target_key
            for case in conn.execute('''SELECT DISTINCT c.*,s.practice_location_id AS scoped_location,s.network_id AS scoped_network
                ,EXISTS(SELECT 1 FROM follow_up_association f WHERE f.case_id=c.id AND f.target_key=?) AS follow_up_scoped
                FROM work_case c LEFT JOIN case_scope s ON s.case_id=c.id WHERE c.id IN
                (SELECT w.case_id FROM work_evidence w JOIN observation o ON o.id=w.observation_id WHERE o.attempt_id=? AND o.locator=?)
                OR c.id IN (SELECT case_id FROM follow_up_association WHERE target_key=?)''',
                (target_key,target['evidence_attempt_id'],record['locator'],target_key)):
                item=work.setdefault(case['id'],{'id':case['id'],'status':case['status'],'owner':case['owner'],'version':case['version'],
                     'field_name':case['field_name'],'refs':[],'evidence_attempt_ids':[],'assessments':[]})
                status,why=category,reason
                if record['address_path'] and not case['follow_up_scoped']:
                    status,why='not_assessed','Existing work lacks an exact native-address selector'
                elif case['scoped_location'] and location and case['scoped_location']!=location['practice_location_id']:
                    status,why='not_assessed','Existing work and reviewed location scopes disagree'
                elif case['scoped_network'] and case['scoped_network']!=record.get('network_id'):
                    status,why='not_assessed','Existing work and source network scopes disagree'
                elif case['field_name'] not in {proposal['field'],'record'}:
                    status,why='unaffected_within_assessed_scope','Existing work concerns a different field'
                item['refs'].append(record['ref'])
                if target['evidence_attempt_id'] not in item['evidence_attempt_ids']:
                    item['evidence_attempt_ids'].append(target['evidence_attempt_id'])
                item['assessments'].append((status,why))
        for item in work.values():
            statuses={a[0] for a in item['assessments']}
            if len(statuses)>1:
                item.update(classification='not_assessed',reason='Existing work spans differently assessed retained assertions')
            else:
                item.update(classification=item['assessments'][0][0],reason=item['assessments'][0][1])
            item.pop('assessments')
        names=('affected','unaffected_within_assessed_scope','not_assessed')
        work_items=sorted(work.values(),key=lambda item:item['id'])
        snapshot=digest([proposal_id,current,view['snapshot'],RULE_VERSION,child['id'] if child else None,
                         sorted((kind,ref,link['id'] if link else None) for (kind,ref),link in links.items()),run_states,evidence_lineages,work_items])
        return {'proposal_id':proposal_id,'snapshot':snapshot,'inputs_fresh':not stale,'stale_reasons':stale,
                'counts':{name:sum(t['classification']==name for t in targets) for name in names},
                'work_counts':{name:sum(t['classification']==name for t in work_items) for name in names},
                'targets':targets,'existing_work':work_items,'proposed_value':proposal['proposed_value'],
                'scope':{'clinician_id':proposal['clinician_id'],'location_id':proposal['location_id'],'field':proposal['field'],
                         'inputs':proposal['inputs'],'network_ids':proposal['network_ids']},
                'scope_notice':'Assessment is limited to explicitly selected retained inputs and reviewed links. Unlinked/ambiguous targets remain not assessed. No source, work, downloaded copy or external system was changed.'}

    def preview(self,proposal_id,offset=0,limit=20,work_offset=0):
        page_parameters(offset,limit)
        page_parameters(work_offset,limit)
        with self.store.db() as conn:
            conn.execute('BEGIN')
            result=self._assess(conn,proposal_id)
        result['total']=len(result['targets'])
        result['next_offset']=offset+limit if offset+limit<result['total'] else None
        result['work_total']=len(result['existing_work'])
        result['work_next_offset']=work_offset+limit if work_offset+limit<result['work_total'] else None
        samples=[sample_record(target,limit) for target in result['targets'][offset:offset+limit]]
        result['targets']=[item[0] for item in samples]
        result['sample_truncated']=any(item[1] for item in samples)
        samples=[sample_record(item,limit) for item in result['existing_work'][work_offset:work_offset+limit]]
        result['existing_work']=[item[0] for item in samples]
        result['sample_truncated'] |= any(item[1] for item in samples)
        return result
