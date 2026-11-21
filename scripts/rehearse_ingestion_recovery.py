"""Rehearse repeat/reinterpret/reopen on a NEW copy of a synthetic confirmed plan.

The source must be quiescent current-schema storage with a confirmed plan made
with default case choices. No source database, original artifact or prior case
is changed. This is a local preservation rehearsal, not a load benchmark.
"""
from __future__ import annotations

import argparse
from contextlib import closing
import hashlib
import io
import json
from pathlib import Path
import shutil
import sqlite3
import subprocess
import sys
import tempfile
import time

from openpyxl import load_workbook

from provider_directory_truth_layer.follow_up import FollowUp
from provider_directory_truth_layer.follow_up_export import workbook
from provider_directory_truth_layer.intake_store import IntakeStore, VERSION, digest


def require(condition, message):
    if not condition:
        raise RuntimeError(message)


def files(root):
    return {str(p.relative_to(root)): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in root.rglob('*') if p.is_file()}


def has_pending_wal(path):
    wal = path.with_name(path.name + '-wal')
    return wal.exists() and wal.stat().st_size > 0


def tables(path):
    require(not has_pending_wal(path), 'Close source connections/checkpoint storage before rehearsal')
    with closing(sqlite3.connect(path.as_uri() + '?mode=ro&immutable=1', uri=True)) as conn:
        names = [row[0] for row in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name")]
        return {name: conn.execute('SELECT * FROM "' + name + '" ORDER BY 1').fetchall() for name in names}


def launch(root):
    subprocess.run([sys.executable, 'scripts/demo.py', '--root', str(root), '--prepare-only'], check=True)


def rehearse(source, root):
    source, root = source.resolve(), root.resolve()
    require(source.is_dir() and not root.exists(), 'Use existing source storage and a NEW destination root')
    require(source not in root.parents and root not in source.parents, 'Source/destination roots must be disjoint')
    path = source / 'directory.sqlite3'
    require(not has_pending_wal(path), 'Close source connections/checkpoint storage before rehearsal')
    with closing(sqlite3.connect(path.as_uri() + '?mode=ro&immutable=1', uri=True)) as conn:
        conn.row_factory = sqlite3.Row
        require(conn.execute('PRAGMA user_version').fetchone()[0] == VERSION, 'Source must use current schema')
        require(not conn.execute("SELECT 1 FROM receipt WHERE designation!='synthetic'").fetchone(),
                'This rehearsal is limited to explicitly synthetic storage')
        confirmation = conn.execute('SELECT * FROM follow_up_confirmation ORDER BY created_at DESC,id DESC LIMIT 1').fetchone()
        require(confirmation is not None, 'Source needs a confirmed follow-up plan')
        confirmation = dict(confirmation)
    original_tables, original_files = tables(path), files(source)
    shutil.copytree(source, root)
    launch(root)
    require(tables(root / 'directory.sqlite3') == original_tables, 'Startup changed prior domain rows')
    preserved = {name: sha for name, sha in original_files.items()
                 if name != 'artifact-recovery.json' and not name.startswith('directory.sqlite3')}
    require(all(files(root).get(name) == sha for name, sha in preserved.items()), 'A retained file changed')
    evidence_root = Path(tempfile.mkdtemp(prefix='recovery-evidence-', dir=root))
    if 'artifact-recovery.json' in original_files:
        shutil.copy2(source / 'artifact-recovery.json', evidence_root / 'prior-artifact-recovery.json')

    store = IntakeStore(root / 'directory.sqlite3', root)
    service = FollowUp(store)
    confirmation_id = confirmation['id']
    receipt = service.get(confirmation_id, limit=100)
    proposal_id = confirmation['proposal_id']
    request = {'proposal_id': proposal_id, 'expected_snapshot': confirmation['impact_snapshot'],
               'expected_plan': confirmation['plan_snapshot'], 'case_choices': {},
               'request_id': confirmation['request_id'], 'actor': confirmation['actor'],
               'reason': confirmation['reason'], 'confirm': True}
    require(digest({k: v for k, v in request.items() if k != 'request_id'}) == confirmation['intent_hash'],
            'Use a confirmation made with default case choices')
    saved = service.confirm(request)
    case_tables = {name: rows for name, rows in tables(store.path).items()
                   if name in {'work_case', 'work_event', 'work_evidence', 'case_scope',
                               'follow_up_confirmation', 'follow_up_association', 'follow_up_acknowledgement'}}
    start = time.perf_counter()
    export = service.export(confirmation_id, receipt['snapshot'])
    encoded = workbook(export)
    export_seconds = time.perf_counter() - start
    book = load_workbook(io.BytesIO(encoded), data_only=False)
    require(json.loads(''.join(row[1] for row in book['Payload'].iter_rows(min_row=2, values_only=True))) == export,
            'Workbook payload differs from complete JSON')
    require(not any(cell.data_type == 'f' for sheet in book for row in sheet for cell in row), 'Workbook has a formula')
    (evidence_root / 'confirmed-plan.json').write_text(json.dumps(export, ensure_ascii=False, indent=2) + '\n')
    (evidence_root / 'confirmed-plan.xlsx').write_bytes(encoded)

    # Repeated bytes are a separate delivery, never automatically cross-linked.
    pin = export['proposal']['inputs'][0]
    selected = store.detail(pin['receipt_id'])
    repeated = store.receive((store.artifacts / selected['artifact_sha']).read_bytes(), selected['label'],
                             source=selected['source'], designation=selected['designation'],
                             profile=selected['profile'], metadata=selected['metadata'])
    require(repeated['id'] != selected['id'] and repeated['artifact_sha'] == selected['artifact_sha'],
            'Repeat did not retain separate delivery identity')
    require(tables(store.path)['reviewed_identity_link'] == original_tables['reviewed_identity_link'],
            'Later delivery created or changed a reviewed link')
    require(service.get(confirmation_id, limit=100) == receipt, 'Unaccepted separate delivery changed saved plan')

    # A new interpretation of a selected receipt must make the old plan stale.
    settings = dict(selected['attempts'][-1]['spec'])
    if settings.get('mapping_revision_id'):
        settings = {'mapping_revision_id': settings['mapping_revision_id']}
    settings['expected_attempt'] = selected['attempt_id']
    store.mapping(selected['id'], settings)
    stale = service.get(confirmation_id, limit=100)
    require(not stale['source_inputs_fresh'] and stale['source_stale_reasons'], 'Reinterpretation did not stale saved context')
    require(service.confirm(request) == saved, 'Identical historical confirmation retry changed after staleness')
    require(all(tables(store.path)[name] == rows for name, rows in case_tables.items()),
            'Repeat/reinterpretation changed existing work, associations or acknowledgements')
    before_restart = tables(store.path)
    launch(root)
    require(tables(store.path) == before_restart, 'Separate-process reopen changed durable rows')
    reopened = FollowUp(IntakeStore(store.path, root))
    require(reopened.get(confirmation_id, limit=100) == stale, 'Reopened receipt differs')
    require(reopened.confirm(request) == saved, 'Reopened retry differs')
    with store.db() as conn:
        require(conn.execute('PRAGMA integrity_check').fetchone()[0] == 'ok', 'Integrity failure')
        require(not conn.execute('PRAGMA foreign_key_check').fetchall(), 'Foreign key failure')
    require(tables(path) == original_tables and files(source) == original_files, 'Source storage changed')
    require(all(files(root).get(name) == sha for name, sha in preserved.items()), 'A copied prior artifact changed')
    result = {'synthetic': True, 'schema': VERSION, 'prior_tables_preserved_before_new_actions': len(original_tables),
              'prior_files_preserved_except_refreshed_recovery_report': True, 'source_storage_unchanged': True,
              'evidence_directory': evidence_root.name,
              'assessment_counts': receipt['counts'], 'confirmed_associations': receipt['total'],
              'separate_repeat_delivery_same_artifact': True, 'later_delivery_inherited_links': False,
              'new_interpretation_made_saved_context_stale': True, 'historical_confirmation_retry_preserved': True,
              'existing_work_and_follow_up_history_unchanged': True, 'separate_process_reopen_rows_exact': True,
              'json_xlsx_payload_equal': True, 'formulas': 0, 'integrity': 'ok', 'foreign_keys': 'clean',
              'json_bytes': (evidence_root / 'confirmed-plan.json').stat().st_size, 'xlsx_bytes': len(encoded),
              'export_seconds': export_seconds,
              'timing_scope': 'One complete plan JSON assembly plus XLSX serialization on this copied root; excludes validation, workbook reopening and service startup. Not a capacity benchmark.'}
    (evidence_root / 'recovery-receipt.json').write_text(json.dumps(result, indent=2) + '\n')
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source-root', type=Path, required=True)
    parser.add_argument('--root', type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(rehearse(args.source_root, args.root), indent=2))


if __name__ == '__main__':
    main()
