"""Create a new, isolated synthetic workbench for the phone-review SQL walkthrough."""

import argparse
import json
from pathlib import Path

from provider_directory_truth_layer.intake_store import IntakeStore


def prepare(root: Path) -> dict:
    root = root.expanduser().absolute()
    # Atomic creation refuses existing directories and symlinks, including dangling ones.
    root.mkdir(parents=False, exist_ok=False)
    store = IntakeStore(root / 'directory.sqlite3', root)
    header = 'record_id,npi,provider_name,address,city,state,zip,phone,location_id,reference_phone\n'
    north = 'SYN-1,1000000001,Synthetic Clinician,10 Example St,Example,MA,02108,6175550100,NORTH,6175550199\n'
    south = 'SYN-1,1000000001,Synthetic Clinician,20 Example St,Example,MA,02108,6175550101,SOUTH,6175550198\n'
    for name, payload in [('baseline.csv', header + north + south),
                          ('later.csv', header + north.replace('6175550100', '6175550102') + south)]:
        receipt = store.receive(payload.encode(), name, source='synthetic-phone-demo',
                                designation='synthetic', metadata={'scope': 'synthetic-clinic'})
        store.commit(receipt['id'], {'actor': 'Synthetic reviewer', 'reason': 'Prepare synthetic SQL exercise',
                                     'policy': 'valid_rows'})
    cases = [case for case in store.work()['items'] if case['field_name'] == 'phone']
    by_location = {case['location_id'].rsplit(':', 1)[-1]: case for case in cases}
    for location, due in [('NORTH', '2026-01-31'), ('SOUTH', '2026-02-01')]:
        case = by_location[location]
        store.event(case['id'], {'actor': 'Synthetic reviewer', 'reason': 'Synthetic follow-up assignment',
                                 'action': 'assign', 'owner': 'Demo analyst', 'follow_up': due,
                                 'expected_version': case['version']})
    return {'database': str(store.path), 'as_of': '2026-02-01',
            'north_case_id': by_location['NORTH']['id'],
            'notice': 'Synthetic local exercise; no real providers or external updates.'}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', required=True, type=Path, help='New directory; its parent must already exist')
    args = parser.parse_args()
    print(json.dumps(prepare(args.root), indent=2))
