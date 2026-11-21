"""Reviewed field preferences over explicitly linked, separately retained assertions."""
from __future__ import annotations

import io
import json
import re

from .comparison import RULE_VERSION
from .intake_store import Conflict, digest, now, packed, uid
from .reconciliation_store import ReconciliationStore, page_parameters, sample_record

MIGRATION_8 = '''
CREATE TABLE reconciled_field_decision (
 seq INTEGER PRIMARY KEY AUTOINCREMENT, id TEXT NOT NULL UNIQUE,
 request_id TEXT NOT NULL UNIQUE, request_hash TEXT NOT NULL,
 clinician_id TEXT NOT NULL REFERENCES clinician_identity(id),
 location_id TEXT REFERENCES practice_location(id), field TEXT NOT NULL,
 decision TEXT NOT NULL CHECK(decision IN ('select','conflict')),
 selected_ref TEXT, value TEXT NOT NULL, snapshot TEXT NOT NULL,
 review_snapshot TEXT NOT NULL, evidence TEXT NOT NULL,
 previous_id TEXT REFERENCES reconciled_field_decision(id),
 actor TEXT NOT NULL, reason TEXT NOT NULL, created_at TEXT NOT NULL,
 CHECK((location_id IS NULL AND field IN ('provider_name','npi'))
 OR (location_id IS NOT NULL AND field IN ('phone','address'))),
 CHECK((decision='select' AND selected_ref IS NOT NULL) OR (decision='conflict' AND selected_ref IS NULL)));
CREATE INDEX reconciled_field_scope ON reconciled_field_decision(clinician_id,location_id,field,seq DESC);
'''
for _action in ('UPDATE','DELETE'):
    MIGRATION_8 += f"CREATE TRIGGER reconciled_field_no_{_action.lower()} BEFORE {_action} ON reconciled_field_decision BEGIN SELECT RAISE(ABORT,'Immutable reconciled field decisions'); END;\n"


def decode(row):
    if row is None:
        return None
    item = dict(row)
    for key in ('value','evidence'):
        item[key] = json.loads(item[key])
    return item


def field_option(field, record, links):
    original, comparison = record['original_fields'], record['comparison']
    if field == 'phone':
        value = {'number': original.get('phone'), 'extension': original.get('phone_extension')}
        compared = {'number': comparison.get('phone'), 'extension': comparison.get('phone_extension')}
        relevant = ('phone','phone_extension')
    elif field == 'address':
        keys = ('line1','line2','suite','city','state','zip')
        value = {key: original.get('address', {}).get(key) for key in keys}
        compared = {key: comparison['address'].get(key) for key in keys}
        relevant = ('address', *('address.'+key for key in keys))
    else:
        value, compared, relevant = original.get(field), comparison.get(field), (field,)
    findings = {key: codes for key,codes in record['field_findings'].items() if key in relevant}
    invalid = any(code.startswith('invalid_') or code in {'extension_conflict','suite_assertion_conflict'}
                  for codes in findings.values() for code in codes)
    return {'ref': record['clinician_ref'] if field in {'provider_name','npi'} else record['ref'],
            'source': record['source'], 'value': value, 'comparison_value': compared,
            'selectable': not invalid, 'findings': findings, 'link_ids': links,
            'receipt_id': record['receipt_id'], 'attempt_id': record['attempt_id'],
            'locator': record['locator'], 'address_path': record['address_path'],
            'artifact_sha': record['artifact_sha'], 'network_id': record.get('network_id'),
            'source_field_values': record.get('source_field_values'),
            'provenance': record.get('comparison_provenance', {}),
            **({key:record[key] for key in ('supporting_refs','source_network_reference','native_validation') if key in record})}


class FieldReconciliation:
    def __init__(self, store):
        self.store = store
        self.comparison = ReconciliationStore(store)

    def _view(self, conn, clinician_id, location_id=None):
        clinician = conn.execute('SELECT * FROM clinician_identity WHERE id=?', (clinician_id,)).fetchone()
        if clinician is None:
            raise KeyError('Reviewed clinician not found')
        location = None
        if location_id is not None:
            location = conn.execute('SELECT * FROM practice_location WHERE id=?', (location_id,)).fetchone()
            if location is None:
                raise KeyError('Practice location not found')
        links = [dict(row) for row in conn.execute('''SELECT l.* FROM reviewed_identity_link l
            WHERE NOT EXISTS(SELECT 1 FROM reviewed_identity_link n WHERE n.kind=l.kind AND n.ref=l.ref AND n.seq>l.seq)
            AND ((l.kind='clinician' AND l.clinician_id=?) OR (l.kind='location' AND l.practice_location_id=?))
            ORDER BY l.kind,l.ref''', (clinician_id, location_id))]
        clinician_links = {link['ref']:link for link in links if link['kind']=='clinician'}
        runs = {}
        def run(run_id):
            if run_id not in runs:
                row = conn.execute('SELECT * FROM comparison_run WHERE id=?', (run_id,)).fetchone()
                runs[run_id] = {**dict(row), 'records': json.loads(row['records'])}
            return runs[run_id]
        records, record_links, relevant_links = {}, {}, {}
        type_conflicts=set()
        if location_id is None:
            for ref,link in clinician_links.items():
                for record in run(link['run_id'])['records']:
                    if record['clinician_ref']==ref:
                        records[record['ref']] = record
                        record_links[record['ref']] = [link['id']]
                relevant_links[link['id']] = link
        else:
            for link in links:
                if link['kind']!='location':
                    continue
                record = next((r for r in run(link['run_id'])['records'] if r['ref']==link['ref']), None)
                if record is None or record['clinician_ref'] not in clinician_links:
                    continue
                person_link = clinician_links[record['clinician_ref']]
                if record['comparison']['entity_kind']=='organization':
                    type_conflicts.add(record['ref'])
                record={**record,'clinician_type_support':{'link_id':person_link['id'],
                        'run_id':person_link['run_id'],'entity_kind':'clinician'}}
                records[record['ref']] = record
                record_links[record['ref']] = [person_link['id'],link['id']]
                relevant_links[person_link['id']] = person_link
                relevant_links[link['id']] = link
        snapshots, fresh = {}, bool(records) and not type_conflicts
        for link in relevant_links.values():
            selected = run(link['run_id'])
            current = self.comparison._snapshot(conn, json.loads(selected['inputs']))
            snapshots[selected['id']] = current
            fresh = fresh and current==json.loads(selected['baseline_snapshot']) and selected['rule_version']==RULE_VERSION
        scope = {'clinician_id':clinician_id,'location_id':location_id}
        evidence_snapshot = digest([scope, RULE_VERSION, sorted(relevant_links), snapshots])
        fields = []
        for field in (('provider_name','npi') if location_id is None else ('phone','address')):
            options = {}
            for ref,record in sorted(records.items()):
                option = field_option(field,record,record_links[ref])
                if ref in type_conflicts:
                    option['selectable']=False
                    option['findings']['identity_type']=['conflicting_reviewed_entity_declarations']
                if option['network_id']:
                    network=conn.execute('SELECT label FROM network WHERE id=?',(option['network_id'],)).fetchone()
                    option['network_label']=network['label'] if network else None
                options.setdefault(option['ref'], option)
            history = [decode(row) for row in conn.execute('''SELECT * FROM reconciled_field_decision
                WHERE clinician_id=? AND location_id IS ? AND field=? ORDER BY seq DESC''', (clinician_id,location_id,field))]
            for decision in history:
                decision['stale'] = decision['snapshot']!=evidence_snapshot or not fresh
            latest = history[0] if history else None
            status = 'unreviewed' if latest is None else 'stale' if latest['stale'] else 'selected' if latest['decision']=='select' else 'conflict'
            fields.append({'field':field,'options':list(options.values()),'option_count':len(options),
                           'decision':latest,'history':history,'status':status,
                           'preferred_value':latest['value'] if status=='selected' else None})
        snapshot = digest([evidence_snapshot, [(field['field'],field['decision']['id'] if field['decision'] else None) for field in fields]])
        return {'scope':scope,'clinician':dict(clinician),'location':dict(location) if location else None,
                'snapshot':snapshot,'evidence_snapshot':evidence_snapshot,'inputs_fresh':bool(fresh),
                'fields':fields,'records':list(records.values()),'source_count':len({r['source'] for r in records.values()}),
                'links':list(relevant_links.values()),'run_snapshots':snapshots,
                'scope_problems':['Conflicting reviewed entity declarations: a location assertion describes an organization while its clinician link asserts a person. Re-review the typed links before selecting values.'] if type_conflicts else [],
                'notice':'Local reviewed preferences, not verified provider facts. Source assertions are unchanged; address components and phone extensions remain coherent.'}

    def inspect(self, clinician_id, location_id=None, offset=0, limit=20, history_offset=0):
        page_parameters(offset,limit)
        page_parameters(history_offset,limit)
        with self.store.db() as conn:
            conn.execute('BEGIN')
            result=self._view(conn,clinician_id,location_id)
        result['total']=len(result['records'])
        result['next_offset']=offset+limit if offset+limit<result['total'] else None
        samples=[sample_record(record,limit) for record in result['records'][offset:offset+limit]]
        result['records']=[item[0] for item in samples]
        result['sample_truncated']=any(item[1] for item in samples)
        from .evidence_samples import sample_value
        for field in result['fields']:
            options=[]
            for option in field['options'][offset:offset+limit]:
                item=dict(option)
                for key in ('value','comparison_value','source_field_values','provenance','findings'):
                    item[key],clipped=sample_value(option[key],budget=max(400,80_000//limit//5))
                    result['sample_truncated'] |= clipped
                if len(item['source'])>512:
                    item['source']=item['source'][:512]+' [sample truncated]'
                    result['sample_truncated']=True
                options.append(item)
            field['options']=options
            field['history_total']=len(field['history'])
            field['history_next_offset']=history_offset+limit if history_offset+limit<field['history_total'] else None
            decisions=[sample_record(item,limit) for item in field['history'][history_offset:history_offset+limit]]
            field['history']=[item[0] for item in decisions]
            result['sample_truncated'] |= any(item[1] for item in decisions)
            if field['decision'] is not None:
                field['decision'],clipped=sample_record(field['decision'],1)
                result['sample_truncated'] |= clipped
            field['preferred_value'],clipped=sample_value(field['preferred_value'],budget=20_000)
            result['sample_truncated'] |= clipped
        result.pop('links')
        result.pop('run_snapshots')
        return result

    def decide(self,payload):
        allowed={'clinician_id','location_id','field','decision','selected_ref','expected_snapshot','expected_decision','request_id','actor','reason'}
        if not isinstance(payload,dict) or set(payload)-allowed:
            raise ValueError('Unknown field decision inputs')
        for key in ('clinician_id','field','decision','expected_snapshot','request_id','actor','reason'):
            if not isinstance(payload.get(key),str) or not payload[key].strip() or len(payload[key])>4096:
                raise ValueError(key+' must be a nonblank string of at most 4096 characters')
        if payload.get('location_id') is not None and not isinstance(payload['location_id'],str):
            raise ValueError('Location ID must be a string or null')
        if 'expected_decision' not in payload or (payload['expected_decision'] is not None and not isinstance(payload['expected_decision'],str)):
            raise ValueError('Supply the prior decision ID or explicit null')
        action=payload['decision']
        if action not in {'select','conflict'}:
            raise ValueError('Choose select or conflict')
        if action=='select' and (not isinstance(payload.get('selected_ref'),str) or not payload['selected_ref']):
            raise ValueError('Select an exact source reference')
        if action=='conflict' and payload.get('selected_ref') is not None:
            raise ValueError('An unresolved conflict cannot select a source')
        request_hash=digest(payload)
        with self.store.db() as conn:
            conn.execute('BEGIN IMMEDIATE')
            saved=conn.execute('SELECT * FROM reconciled_field_decision WHERE request_id=?',(payload['request_id'],)).fetchone()
            if saved:
                if saved['request_hash']!=request_hash:
                    raise Conflict('Request ID already used with different field decision content')
                return decode(saved)
            view=self._view(conn,payload['clinician_id'],payload.get('location_id'))
            if not view['inputs_fresh'] or view['snapshot']!=payload['expected_snapshot']:
                raise Conflict('Source/link/field snapshot changed; inspect and review again')
            field=next((field for field in view['fields'] if field['field']==payload['field']),None)
            if field is None:
                raise ValueError('Field does not belong to this clinician/location scope')
            previous=field['decision']['id'] if field['decision'] else None
            if payload['expected_decision']!=previous:
                raise Conflict('Field decision changed; review again')
            option=None
            if action=='select':
                option=next((option for option in field['options'] if option['ref']==payload['selected_ref']),None)
                if option is None or not option['selectable']:
                    raise ValueError('Select a valid source assertion in this exact reviewed scope')
            decision_id=uid()
            conn.execute('''INSERT INTO reconciled_field_decision
                (id,request_id,request_hash,clinician_id,location_id,field,decision,selected_ref,value,snapshot,review_snapshot,evidence,previous_id,actor,reason,created_at)
                VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)''',
                (decision_id,payload['request_id'],request_hash,payload['clinician_id'],payload.get('location_id'),payload['field'],action,
                 payload.get('selected_ref'),packed(option['value'] if option else None),view['evidence_snapshot'],view['snapshot'],
                 packed(option if option else {'options':field['options'],'explicit_unresolved_conflict':True}),previous,payload['actor'],payload['reason'],now()))
            return decode(conn.execute('SELECT * FROM reconciled_field_decision WHERE id=?',(decision_id,)).fetchone())

    def export(self,clinician_id,location_id,expected_snapshot):
        with self.store.db() as conn:
            conn.execute('BEGIN')
            result=self._view(conn,clinician_id,location_id)
            if expected_snapshot!=result['snapshot']:
                raise Conflict('Export snapshot changed; refresh the reconciled view')
            result['source_context']=[]
            contexts={}
            from .fhir_store import context_refs
            for record in result['records']:
                for key in context_refs(record):
                    contexts.setdefault(key, {'receipt_id':record['receipt_id'], 'roles':set()})['roles'].add('current_assertion')
            for field in result['fields']:
                for decision in field['history']:
                    evidence=decision['evidence']
                    options=evidence.get('options', []) if decision['decision']=='conflict' else [evidence]
                    for option in options:
                        for key in context_refs(option):
                            contexts.setdefault(key, {'receipt_id':option['receipt_id'], 'roles':set()})['roles'].add('historical_field_decision')
            for key,context in sorted(contexts.items()):
                attempt=conn.execute('SELECT spec,preview FROM attempt WHERE id=?',(key[0],)).fetchone()
                row=next(row for row in json.loads(attempt['preview'])['rows'] if row['locator']==key[1])
                receipt=dict(conn.execute('SELECT * FROM receipt WHERE id=?',(context['receipt_id'],)).fetchone())
                receipt['metadata']=json.loads(receipt['metadata'])
                result['source_context'].append({'receipt':receipt,'attempt_id':key[0],'spec':json.loads(attempt['spec']),
                                                 'row':row,'roles':sorted(context['roles'])})
            result['link_history']=[]
            for link in result['links']:
                result['link_history'].extend(dict(row) for row in conn.execute('SELECT * FROM reviewed_identity_link WHERE kind=? AND ref=? ORDER BY seq',(link['kind'],link['ref'])))
            decision_ids={link['decision_id'] for link in result['link_history']}
            result['identity_decisions']=[dict(conn.execute('SELECT * FROM identity_review_decision WHERE id=?',(decision_id,)).fetchone()) for decision_id in sorted(decision_ids)]
            result['format_version']=1
            result['source_context_notice']='Exact retained rows may include other native addresses as shared original context; only records/options define the selected clinician/location scope.'
        return result


def workbook(data):
    """Lossless chunked JSON plus a small readable decision index; all text cells."""
    from openpyxl import Workbook
    def display(value):
        text=json.dumps(value,ensure_ascii=True,sort_keys=True,allow_nan=False) if not isinstance(value,str) else value or '""'
        text=re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f\ud800-\udfff\ufffe\uffff]',lambda match:f'\\u{ord(match[0]):04x}',text)
        return text[:14000]+' [display truncated; see Payload]' if len(text)>14000 else text
    book=Workbook()
    notes=book.active
    notes.title='Read me'
    notes.append(['Boundary','Reviewed local preferences; source assertions and verification remain separate.'])
    notes.append(['Reconstruct','Join Payload json_chunk in numeric part order and parse JSON; it is the complete authoritative export.'])
    notes.append(['Scope',packed(data['scope'])])
    decisions=book.create_sheet('Field decisions')
    decisions.append(['field','status','preferred_value','decision_id','selected_ref','source','actor','reason','created_at','stale'])
    for field in data['fields']:
        decision=field['decision'] or {}
        decisions.append([display(value) for value in [field['field'],field['status'],field['preferred_value'],decision.get('id'),decision.get('selected_ref'),
                          decision.get('evidence',{}).get('source'),decision.get('actor'),decision.get('reason'),
                          decision.get('created_at'),decision.get('stale')]])
    assertions=book.create_sheet('Source assertions')
    assertions.append(['field','retained_ref','source','network_id','network_label','source_value','comparison_value',
                       'selectable','findings','receipt_id','attempt_id','locator','address_path','reviewed_link_revisions'])
    for field in data['fields']:
        for option in field['options']:
            assertions.append([display(value) for value in [field['field'],option['ref'],option['source'],option.get('network_id'),option.get('network_label'),
                               option['value'],option['comparison_value'],option['selectable'],option['findings'],
                               option['receipt_id'],option['attempt_id'],option['locator'],option['address_path'],option['link_ids']]])
    payload=book.create_sheet('Payload')
    payload.append(['part','json_chunk'])
    encoded=json.dumps(data,ensure_ascii=True,sort_keys=True,allow_nan=False)
    for index,start in enumerate(range(0,len(encoded),30000),1):
        if index>=1_048_576:
            raise ValueError('Export exceeds spreadsheet row capacity')
        payload.append([str(index),encoded[start:start+30000]])
    for sheet in book:
        sheet.freeze_panes='A2'
        for row in sheet:
            for cell in row:
                if cell.value is not None:
                    cell.data_type='s'
                    cell.number_format='@'
    output=io.BytesIO()
    book.save(output)
    book.close()
    return output.getvalue()
