"""Installed-package journey; called with isolated Python by check_distribution."""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import sqlite3
import subprocess
import sys


def require(condition, message):
    if not condition:
        raise RuntimeError(message)


def main():
    root = Path(sys.argv[1]).resolve()
    root.mkdir(mode=0o700)
    os.chdir(root)
    os.environ['PDTL_ROOT'] = str(root/'default-storage')
    import provider_directory_truth_layer as package
    from provider_directory_truth_layer.operations_rehearsal import xlsx_payload
    from provider_directory_truth_layer.operations_sql import run as sql
    from provider_directory_truth_layer.intake_store import IntakeStore
    from provider_directory_truth_layer.managed_feed import ManagedFeed

    installed = Path(package.__file__).resolve()
    require(installed.is_relative_to(Path(sys.prefix).resolve()) and 'site-packages' in installed.parts,
            'Import did not come from the isolated installed distribution')
    executable = Path(sys.executable).with_name('provider-truth-layer' + ('.exe' if os.name == 'nt' else ''))

    def command(*arguments, expected=0):
        result = subprocess.run([str(executable), *map(str, arguments)], capture_output=True, text=True, timeout=120)
        print(result.stdout, end=''); print(result.stderr, end='', file=sys.stderr)
        require(result.returncode == expected, f'Unexpected exit {result.returncode}: {arguments[0]}')
        return result

    command('run', '--as-of', '2026-06-01', '--output-dir', root/'qa', '--sqlite', root/'qa.sqlite3')
    import csv
    with (root/'qa/quality_summary.csv').open() as stream:
        summary = {row['metric']: float(row['value']) for row in csv.DictReader(stream)}
    require(summary['total_records'] == 12 and summary['total_issues'] > 0, 'Installed default QA output changed')
    command('rehearse-operations', '--root', root/'operations')
    journey = json.loads((root/'operations/operations-rehearsal.json').read_bytes())
    exports = root/'operations/exports'
    original = (exports/'approved.json').read_bytes()
    command('consume-approved', exports/'approved.json', '--expected-version', journey['approved_version_id'],
            '--expected-feed', journey['feed_id'], '--report', root/'consumer.json')
    contacts = json.loads((root/'consumer.json').read_bytes())['contacts']
    require([(item['location_id'], item['zip'], item['phone'], item['phone_extension']) for item in contacts] ==
            [('NORTH','02108','6175550100','007'), ('SOUTH','02108','6175550200','008')], 'Installed contacts lost office/ZIP/extension scope')
    require(xlsx_payload((exports/'north-fields.xlsx').read_bytes()) == json.loads((exports/'north-fields.json').read_bytes()),
            'Installed JSON/XLSX selected evidence differs')
    command('rehearse-operations', '--root', root/'operations', expected=2)
    require((exports/'approved.json').read_bytes() == original, 'Repeat-root refusal changed the approved export')
    command('evaluate-mapping', '--root', root/'mapping')
    evaluation = json.loads((root/'mapping/evaluation.json').read_bytes())
    require(evaluation['case_count'] == 8 and evaluation['invocations_attempted'] == evaluation['completed_model_cases'] == 0,
            'Default frozen evaluation used a model or changed its corpus')
    require(evaluation['baseline']['binding_expectations'] == 74 and evaluation['baseline']['correct_bindings_or_abstentions'] == 63,
            'Installed mapping baseline differs')
    store = IntakeStore.open_existing(root/'operations/storage/directory.sqlite3', root/'operations/storage')
    feeds = ManagedFeed(store)
    require(feeds.current(journey['feed_id'])['version_id'] == journey['approved_version_id'], 'Reopen changed approved version')
    with sqlite3.connect(store.path) as connection:
        before = list(connection.iterdump())
    rows = sql(store.path, 'latest-event')
    require(any(row['case_id'] == journey['north_case_id'] for row in rows), 'Installed SQL did not find the retained case')
    for question in ('follow-up', 'phone-review'):
        sql(store.path, question, as_of='2026-11-14')
    require(sql(store.path, 'lineage', case_id=journey['north_case_id']), 'Installed SQL lineage is empty')
    with sqlite3.connect(store.path) as connection:
        require(list(connection.iterdump()) == before, 'Read-only installed SQL changed state')
    report = {'installed_module': str(installed), 'interpreter': sys.executable, 'default_qa_records': 12,
              'consumer_contacts': contacts, 'approved_sha256': hashlib.sha256(original).hexdigest(),
              'baseline': evaluation['baseline'], 'model_invocations': evaluation['invocations_attempted'],
              'sql_latest_events': len(rows), 'sql_state_unchanged': True, 'repeat_root_preserved': True,
              'json_xlsx_equal': True, 'reopened_approved_version': journey['approved_version_id'],
              'operations': {key: journey[key] for key in ('north_status','south_unchanged','consumer_preserved_after_hold',
                  'restart_preserved','restore_preserved','backed_up_registered_artifacts')}}
    (root/'result.json').write_text(json.dumps(report, indent=2)+'\n')


if __name__ == '__main__':
    main()
