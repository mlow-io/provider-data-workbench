"""Prepare synthetic managed-feed inputs and an approved recipe in a new owned root.

Does not register/enable a feed, approve its contract or accept any dataset.
"""
import argparse
import hashlib
import json
from pathlib import Path

from provider_directory_truth_layer.intake_store import IntakeStore
from provider_directory_truth_layer.onboarding_service import OnboardingService


def prepare(root):
    root = root.resolve()
    if root.exists():
        raise ValueError('Choose a new root; existing storage is preserved')
    root.mkdir(parents=True)
    inbox = root / 'inbox'
    inbox.mkdir()
    store = IntakeStore(root / 'directory.sqlite3', root)
    headers = ['record_id','npi','provider_name','address','city','state','zip','phone','location_id']
    original = ('record_id,npi,provider_name,address,city,state,zip,phone,location_id\n'
                'SYNTHETIC-001,1000000001,Synthetic Clinician,10 Example St,Example,MA,02108,6175550100,NORTH\n'
                'SYNTHETIC-001,1000000001,Synthetic Clinician,20 Example St,Example,MA,02108,6175550101,SOUTH\n'
                'SYNTHETIC-002,1000000002,Synthetic Second Clinician,30 Example St,Example,MA,02108,6175550102,EAST\n').encode()
    receipt = store.receive(original, 'synthetic-recipe.csv', source='synthetic-managed-clinic', metadata={'scope': 'weekly-full-roster'})
    service = OnboardingService(store)
    actor = {'actor': 'Explicit synthetic demo preparation', 'reason': 'Prepare deterministic approved normalization recipe only'}
    proposed = service.propose(receipt['id'], {'name': 'Synthetic weekly clinic', 'expected_attempt': receipt['attempt_id'], 'definition': {'version': 1, 'mapping': dict(zip(headers, headers)), 'required': headers, 'transforms': {'phone': ['phone_us']}}, **actor})
    recipe = service.approve(receipt['id'], proposed['id'], {'expected_attempt': receipt['attempt_id'], **actor})
    scenarios = {'baseline': (original, '2026-10-05'), 'changed': (original.replace(b'6175550100', b'6175550199'), '2026-10-12'), 'row-drop': (b'\n'.join(original.splitlines()[:2]) + b'\n', '2026-10-19'), 'header-drift': (original.replace(b',phone,', b',Published phone,'), '2026-10-26')}
    # Stage the baseline only; later deliveries are explicitly copied by the operator.
    staged = root / 'later-deliveries'
    staged.mkdir()
    for label, (data, period) in scenarios.items():
        destination = inbox if label == 'baseline' else staged
        (destination / (label + '.csv')).write_bytes(data)
        manifest = {'delivery_id': 'synthetic-' + label, 'period': period, 'as_of': period, 'snapshot': 'full', 'filename': label + '.csv', 'sha256': hashlib.sha256(data).hexdigest()}
        (destination / (label + '.manifest.json')).write_text(json.dumps(manifest, indent=2) + '\n')
    result = {'root': str(root), 'inbox': str(inbox), 'recipe_id': recipe['id'], 'start_date': '2026-10-05', 'notice': 'Synthetic demo only; no feed/contract/dataset acceptance has occurred.'}
    (root / 'managed-demo.json').write_text(json.dumps(result, indent=2) + '\n')
    return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', required=True, type=Path)
    args = parser.parse_args()
    print(json.dumps(prepare(args.root), indent=2))
