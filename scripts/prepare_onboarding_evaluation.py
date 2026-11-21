"""Prepare an explicitly synthetic MCP evaluation in a NEW invocation-owned root."""
from __future__ import annotations

import argparse
import csv
import io
import json
from pathlib import Path

from provider_directory_truth_layer.intake_store import IntakeStore
from provider_directory_truth_layer.onboarding_service import OnboardingService


def prepare(root: Path):
    root.mkdir(parents=True, exist_ok=False)
    headers = ['Source record', 'Practitioner ID', 'Clinician name', 'Office address', 'Town', 'Region', 'Postal', 'Office Tel', 'Office ID', 'Updated']
    good = ['001', '1000000001', '  Alex   Synthetic ', '10 Example St', 'Boston', 'ma', '02108', '+1 (212) 555-0101 ext 007', 'NORTH', '03/04/2026']
    rows = [good,
            ['002', '1000000002', *good[2:7], '', 'NORTH', '03/04/2026'],
            ['003', '', *good[2:7], '615-555-0100', 'NORTH', '03/04/2026'],
            ['004', '1000000004', *good[2:7], 'ambiguous phone', 'NORTH', '03/04/2026'],
            ['005', '1000000005', 'Robin Synthetic', '20 Example St', 'Boston', 'MA', '02108-0042', '615-555-0109', 'SOUTH', '03/04/2026']]
    stream = io.StringIO()
    writer = csv.writer(stream)
    writer.writerow(headers)
    writer.writerows(rows)
    store = IntakeStore(root / 'directory.sqlite3', root)
    receipt = store.receive(stream.getvalue().encode(), 'synthetic-evaluation.csv', source='synthetic-evaluation', metadata={'scope': 'frozen-five-rows'})
    fields = ['record_id', 'npi', 'provider_name', 'address', 'city', 'state', 'zip', 'phone', 'location_id', 'source_updated_at']
    definition = {'version': 1, 'mapping': dict(zip(fields, headers)), 'required': fields[:8],
                  'transforms': {'provider_name': ['trim', 'collapse_spaces'], 'state': ['state_us'],
                                 'zip': ['zip_us'], 'phone': ['phone_us'],
                                 'source_updated_at': [{'op': 'date', 'format': '%d/%m/%Y'}]}}
    proposal = OnboardingService(store).propose(receipt['id'], {
        'expected_attempt': receipt['attempt_id'], 'definition': definition,
        'name': 'Frozen synthetic evaluation rules', 'actor': 'Synthetic evaluation author',
        'reason': 'Explicit day/month date interpretation; no real provider facts'})
    manifest = {'synthetic': True, 'receipt_id': receipt['id'], 'attempt_id': receipt['attempt_id'],
                'proposal_id': proposal['id'], 'artifact_sha': receipt['artifact_sha'],
                'notice': 'Prepared fixture only; no model evaluation has been run.'}
    (root / 'evaluation-manifest.json').write_text(json.dumps(manifest, indent=2) + '\n')
    return manifest


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', required=True, type=Path, help='New dedicated evaluation directory; existing roots are rejected')
    args = parser.parse_args()
    print(json.dumps(prepare(args.root.resolve()), indent=2))
