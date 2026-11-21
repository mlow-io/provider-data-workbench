"""Measure retained clinic CSV profiling/preview on an explicitly synthetic corpus."""
from __future__ import annotations

import argparse
import csv
import io
import json
from pathlib import Path
import resource
import sys
import time

from provider_directory_truth_layer.intake_store import IntakeStore
from provider_directory_truth_layer.onboarding_service import OnboardingService


def measure(root: Path, count: int):
    if not 1 <= count <= 20_000:
        raise ValueError('Choose 1..20,000 synthetic rows')
    root.mkdir(parents=True, exist_ok=False)
    fields = ['record_id', 'npi', 'provider_name', 'address', 'city', 'state', 'zip', 'phone', 'location_id']
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(fields)
    for index in range(count):
        writer.writerow([f'{index:05}', '1000000001', f'Synthetic Provider {index}',
            '10 Example St', 'Example', 'ma', '02108', '+1 (212) 555-0101 ext 007', 'NORTH'])
    store = IntakeStore(root / 'directory.sqlite3', root)
    receipt = store.receive(output.getvalue().encode(), 'synthetic-capacity.csv', source='synthetic-capacity')
    service = OnboardingService(store)
    definition = {'version': 1, 'mapping': {field: field for field in fields},
                  'transforms': {'phone': ['phone_us'], 'state': ['state_us']}, 'required': fields[:8]}
    start = time.perf_counter()
    profile = service.inspect(receipt['id'])
    profile_seconds = time.perf_counter() - start
    start = time.perf_counter()
    preview = service.preview(receipt['id'], definition, receipt['attempt_id'])
    preview_seconds = time.perf_counter() - start
    if profile['row_count'] != count or preview['valid_count'] != count:
        raise RuntimeError('Synthetic capacity corpus did not retain its expected valid count')
    rss_unit = 1024 * 1024 if sys.platform == 'darwin' else 1024
    result = {'synthetic_rows': count, 'profile_seconds': round(profile_seconds, 4),
              'preview_seconds': round(preview_seconds, 4), 'sample_rows': len(preview['rows']),
              'preview_json_bytes': len(json.dumps(preview).encode()),
              'peak_process_rss_mib': round(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / rss_unit, 2),
              'platform': sys.platform, 'python': sys.version.split()[0],
              'scope': 'Single synthetic clinic CSV profile/preview; not acceptance, XLSX or concurrent-user capacity'}
    (root / 'result.json').write_text(json.dumps(result, indent=2) + '\n')
    return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', required=True, type=Path, help='New invocation-owned output directory')
    parser.add_argument('--rows', default=1000, type=int)
    args = parser.parse_args()
    print(json.dumps(measure(args.root.resolve(), args.rows), indent=2))
