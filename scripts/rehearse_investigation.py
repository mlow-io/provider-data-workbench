"""Create a retained synthetic investigation and handoff in a new owned root."""
import argparse
import csv
import io
import json
from pathlib import Path
from provider_directory_truth_layer.intake_store import IntakeStore
from provider_directory_truth_layer.work_export import snapshot, handoff_workbook
from provider_directory_truth_layer.operations_sql import run


def rehearse(root):
    root.mkdir(parents=True, exist_ok=False)
    store = IntakeStore(root / 'directory.sqlite3', root)
    buffer = io.StringIO()
    writer = csv.DictWriter(buffer, fieldnames=['record_id','npi','provider_name','address','city','state','zip','phone','location_id','reference_phone'])
    writer.writeheader()
    for office, phone, reference in [('NORTH','6175550100','6175550199'),('SOUTH','6175550200','6175550299')]:
        writer.writerow(dict(record_id=office,npi='1000000001',provider_name='Synthetic Clinician',address=f'{10 if office == "NORTH" else 20} Example St',city='Example',state='MA',zip='02108',phone=phone,location_id=office,reference_phone=reference))
    receipt = store.receive(buffer.getvalue().encode(), 'synthetic-investigation.csv', source='synthetic-investigation', designation='synthetic')
    accepted = store.commit(receipt['id'], dict(actor='Synthetic analyst',reason='Fixture reviewed',policy='valid_rows'))
    north = next(c for c in accepted['linked_cases'] if c['kind']=='correction' and c['location_id'].endswith(':NORTH'))
    south = next(c for c in accepted['linked_cases'] if c['kind']=='correction' and c['location_id'].endswith(':SOUTH'))
    south_before = store.case(south['id'])
    # A second bounded delivery changes NORTH and omits SOUTH; absence is not closure.
    lines = buffer.getvalue().splitlines()
    changed = ('\n'.join([lines[0], lines[1].replace('6175550100', '6175550101')]) + '\n').encode()
    later = store.receive(changed, 'synthetic-incomplete-delivery.csv', source='synthetic-investigation', designation='synthetic')
    store.commit(later['id'], dict(actor='Synthetic analyst',reason='Bounded NORTH-only evidence; SOUTH remains unresolved',policy='valid_rows'))
    if store.case(south['id']) != south_before: raise RuntimeError('Missing SOUTH changed its case')
    actions = [('assign',dict(owner='Synthetic analyst',follow_up='2026-11-04')),
               ('outreach',dict(contact_at='2026-11-03T09:00:00-05:00',method='phone',outcome='no_answer')),
               ('outreach',dict(contact_at='2026-11-03T10:00:00-05:00',method='phone',outcome='response_received',response_summary='Office supplied its NORTH phone',respondent_role='Office manager',reported_phone='6175550199')),
               ('triage',{}),('approve',dict(proposal='6175550199')),
               ('submit',dict(submission_reference='SIMULATED directory ticket')),
               ('verify',dict(observed='6175550100',verification_note='Synthetic downstream still lists old number'))]
    case=store.case(north['id'])
    for action, fields in actions:
        case=store.event(case['id'],dict(action=action,actor='Synthetic analyst',reason='Synthetic investigation rehearsal',expected_version=case['version'],**fields))
    if case['status']!='reopened' or store.case(south['id'])!=south_before:
        raise RuntimeError('Rehearsal scope or verification invariant failed')
    reopened=IntakeStore(store.path,root)
    if reopened.case(case['id'])!=case:raise RuntimeError('Restart changed investigation')
    packet=snapshot(store.path,case['id'])
    (root/'investigation.json').write_text(json.dumps(packet,indent=2)+'\n')
    (root/'investigation.xlsx').write_bytes(handoff_workbook(store.path,case['id']))
    (root/'phone-review.json').write_text(json.dumps(run(store.path,'phone-review',as_of='2026-11-05'),indent=2)+'\n')
    (root/'lineage.json').write_text(json.dumps(run(store.path,'lineage',case_id=case['id']),indent=2)+'\n')
    result=dict(synthetic=True,case_id=case['id'],status=case['status'],outreach_count=len(packet['investigations'][0]['outreach']),retained_observations=len(packet['evidence']),south_unchanged=True,restart_preserved=True,notice='No actual communication or payer update occurred.')
    (root/'rehearsal.json').write_text(json.dumps(result,indent=2)+'\n')
    return result


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root',type=Path,required=True,help='New retained root; existing roots are refused')
    args=parser.parse_args()
    print(json.dumps(rehearse(args.root),indent=2))
