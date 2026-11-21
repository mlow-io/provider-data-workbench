"""Check exact packaged defaults against their authoritative contributor files.

Run with --write after intentionally changing a source asset, then review both.
The default is read-only and suitable for CI.
"""
from __future__ import annotations

import argparse
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DESTINATION = ROOT / 'src/provider_directory_truth_layer/assets'
SOURCES = {
    'qa/sample_provider_directory.csv': 'data/raw/sample_provider_directory.csv',
    'qa/qa_rules.yml': 'config/qa_rules.yml',
    'operations/north-south.json': 'tests/fixtures/intake/fhir-plannet/north-south.json',
    'operations/expected.json': 'tests/fixtures/operations/expected.json',
    'mapping/mapping-assistant-manifest-v1.json': 'tests/fixtures/onboarding/mapping-assistant-manifest-v1.json',
    'mapping/mapping-assistant-v1.json': 'tests/fixtures/onboarding/mapping-assistant-v1.json',
    **{f'sql/{name}.sql': f'sql/operations/{name}.sql' for name in (
        'follow_up', 'latest_event', 'lineage', 'lineage_review', 'phone_review', 'selected_delivery_diff')},
}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--write', action='store_true')
    args = parser.parse_args()
    mismatches = []
    for target, original in SOURCES.items():
        path = DESTINATION / target
        raw = (ROOT / original).read_bytes()
        if args.write:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(raw)
        if not path.is_file() or path.read_bytes() != raw:
            mismatches.append(target)
    unexpected = {str(p.relative_to(DESTINATION)) for p in DESTINATION.rglob('*') if p.is_file()} - SOURCES.keys()
    if mismatches or unexpected:
        parser.exit(1, f'Bundled asset drift: {sorted(mismatches)}; unexpected files: {sorted(unexpected)}. Review sources, then run --write.\n')
    print(f'Checked {len(SOURCES)} bundled assets against authoritative files')


if __name__ == '__main__':
    main()
