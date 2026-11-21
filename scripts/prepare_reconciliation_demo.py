"""Prepare retained synthetic sources and an unreviewed comparison run in a NEW root."""
from __future__ import annotations

import argparse
from collections import defaultdict
import json
from pathlib import Path

from reconciliation_corpus import build_corpus, load_labeled_fixture
from provider_directory_truth_layer.intake_store import IntakeStore
from provider_directory_truth_layer.reconciliation_store import ReconciliationStore


def prepare(root: Path, corpus: dict):
    root.mkdir(parents=True, exist_ok=False)
    inputs = root / 'inputs'
    inputs.mkdir()
    store = IntakeStore(root / 'directory.sqlite3', root)
    grouped = defaultdict(list)
    for record in corpus['records']:
        grouped[(record['source'], record['clinician_ref'])].append(record)
    sources = defaultdict(list)
    for (source, retained_label), records in sorted(grouped.items()):
        selected_ref = corpus.get('metadata', {}).get('selected_address_refs', {}).get(retained_label)
        selected = next((record for record in records if record['ref'] == selected_ref), records[0])
        address = selected['address']
        addresses = [{**record['address'], 'phone': record.get('phone'),
                      'phone_extension': record.get('phone_extension')} for record in records]
        sources[source].append({'record_id': selected.get('native_id'), 'npi': selected.get('npi'),
            'provider_name': selected.get('provider_name'), 'entity_type': selected['entity_kind'],
            'address': address.get('line1'), 'suite': address.get('suite'), 'city': address.get('city'),
            'state': address.get('state'), 'zip': address.get('zip'), 'phone': selected.get('phone'),
            'phone_extension': selected.get('phone_extension'), 'native_addresses': addresses,
            'selected_address': {'path': address['path']},
            'evaluation_ref': retained_label,
            'notice': 'Synthetic fixture labels are not source-native identities or verified provider facts.'})
    selections = []
    for source, rows in sorted(sources.items()):
        path = inputs / f'synthetic-{source}.json'
        path.write_text(json.dumps(rows, ensure_ascii=False, indent=2) + '\n')
        receipt = store.receive(path.read_bytes(), path.name, source='synthetic-reconciliation-' + source,
                                metadata={'scope': 'frozen-comparison-demo', 'synthetic_evaluation': True})
        selections.append({'receipt_id': receipt['id'], 'attempt_id': receipt['attempt_id'], 'entity_kind': 'unknown'})
    service = ReconciliationStore(store)
    run = service.create_run({'inputs': selections, 'actor': 'Synthetic demonstration author',
                              'reason': 'Explicit retained source comparison; no records accepted or identities linked'})
    exported = service.export(run['id'])
    (root / 'comparison-evidence.json').write_text(json.dumps(exported, ensure_ascii=False, indent=2) + '\n')
    manifest = {'synthetic': True, 'run_id': run['id'], 'inputs': selections,
                'metrics': run['metrics'], 'rule_version': run['rule_version'],
                'notice': 'Prepared retained sources and candidates only. No observations accepted, links approved or external requests made.'}
    (root / 'reconciliation-manifest.json').write_text(json.dumps(manifest, indent=2) + '\n')
    return manifest


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, required=True, help='NEW owned directory; existing data is never replaced')
    parser.add_argument('--fixture', type=Path, help='Authored challenge/held-out fixture; defaults to approximately1k synthetic records')
    parser.add_argument('--entities', type=int, default=300)
    parser.add_argument('--seed', type=int, default=42)
    args = parser.parse_args()
    corpus = load_labeled_fixture(args.fixture) if args.fixture else build_corpus(args.seed, args.entities)
    print(json.dumps(prepare(args.root.resolve(), corpus), indent=2))
