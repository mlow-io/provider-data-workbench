"""Approved feed review handoff: immutable directory and explicitly live work context."""
from __future__ import annotations

import io
import json
import re
import sqlite3
from contextlib import closing
from pathlib import Path

from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill
from openpyxl.utils import get_column_letter

from .intake_store import Conflict, digest, now, packed
from .managed_feed import decode

DIRECTORY_COLUMNS = ['directory_row_id', 'source_record_key', 'office_key', 'version_id', 'record_id', 'npi', 'provider_name', 'location_id', 'address', 'address_line2', 'suite', 'city', 'state', 'zip', 'phone', 'specialty', 'status', 'source_updated_at', 'source_ref']
ISSUE_COLUMNS = ['issue_id', 'directory_row_id', 'source_record_key', 'office_key', 'version_id', 'kind', 'status', 'field', 'issue', 'listed_value', 'proposed_value', 'observed_value', 'case_version', 'source_ref']
SOURCE_COLUMNS = ['source_ref', 'version_id', 'source', 'designation', 'receipt_id', 'attempt_id', 'artifact_sha256', 'row_locator', 'recipe_revision_id', 'contract_id', 'source_as_of', 'received_at']


def snapshot(path: Path, version_id: str, location_id: str | None = None, expected_snapshot: str | None = None) -> dict:
    """Materialize all reads in one read-only SQLite snapshot; never initialize storage."""
    with closing(sqlite3.connect(path.resolve().as_uri() + '?mode=ro', uri=True)) as conn:
        conn.row_factory = sqlite3.Row
        conn.execute('PRAGMA query_only=ON')
        conn.execute('BEGIN')
        raw = conn.execute('SELECT * FROM feed_version WHERE id=?', (version_id,)).fetchone()
        if raw is None:
            raise KeyError('Dataset version not found')
        version = decode(raw)
        approval = conn.execute('SELECT * FROM feed_decision WHERE version_id=?', (version_id,)).fetchone()
        if approval is None or approval['decision'] != 'approved':
            raise ValueError('Only explicitly approved dataset versions are consumable')
        manifest = version['manifest']
        receipt = dict(conn.execute('SELECT * FROM receipt WHERE id=?', (manifest['receipt_id'],)).fetchone())
        attempt = conn.execute('SELECT * FROM attempt WHERE id=?', (manifest['attempt_id'],)).fetchone()
        # Identical later deliveries reuse canonical observations without losing the
        # selected delivery's receipt/artifact/locator in the Directory sheet.
        attempt_id = json.loads(attempt['preview']).get('reuses_attempt', attempt['id'])
        observations = {r['locator']: dict(r) for r in conn.execute('SELECT * FROM observation WHERE attempt_id=? ORDER BY id', (attempt_id,))}
        rows = [row for row in version['rows'] if location_id is None or row['normalized'].get('location_id') == location_id]
        if location_id is not None and not rows:
            raise KeyError('Office not present in selected dataset version')
        directory, issues, sources = [], [], []
        seen_cases = set()
        excluded_case_ids = set()
        selected_scope = packed(json.loads(receipt['metadata']).get('scope'))
        source_refs = set()
        for row in sorted(rows, key=lambda row: row['locator']):
            norm = row['normalized']
            record = norm.get('record_id') or row.get('native_id')
            office = norm.get('location_id')
            source_record_key = 'source-record:' + digest([version['feed_id'], record]) if record else None
            office_key = 'feed-office:' + digest([version['feed_id'], office]) if office else None
            row_id = 'directory:' + digest([version['feed_id'], record, office]) if not row['problems'] else None
            source_ref = 'source:' + digest([version_id, receipt['id'], row['locator']])
            source_refs.add(source_ref)
            sources.append(dict(zip(SOURCE_COLUMNS, [source_ref, version_id, receipt['source'], receipt['designation'], receipt['id'], manifest['attempt_id'], receipt['artifact_sha'], row['locator'], manifest['recipe_revision_id'], manifest['contract_id'], manifest['source_delivery']['as_of'], receipt['received_at']])))
            common = {'directory_row_id': row_id, 'source_record_key': source_record_key, 'office_key': office_key, 'version_id': version_id, 'source_ref': source_ref}
            if row['problems']:
                issues.append({**common, 'issue_id': 'quarantine:' + digest([version_id, row['locator']]), 'kind': 'quarantine', 'status': 'excluded', 'issue': json.dumps(row['problems'], ensure_ascii=True)})
                continue
            directory.append({**common, **{key: norm.get(key) for key in DIRECTORY_COLUMNS if key not in common}})
            observation = observations.get(row['locator'])
            if observation is None:
                raise ValueError('Approved row has no retained observation locator')
            for case in conn.execute("SELECT c.* FROM work_case c JOIN work_evidence w ON w.case_id=c.id WHERE w.observation_id=? AND c.status NOT IN ('resolved','verified') ORDER BY c.id", (observation['id'],)):
                if case['id'] in seen_cases:
                    continue
                evidence = json.loads(case['evidence'])
                case_receipt = dict(conn.execute('SELECT * FROM receipt WHERE id=?', (evidence['receipt_id'],)).fetchone())
                if packed(json.loads(case_receipt['metadata']).get('scope')) != selected_scope:
                    excluded_case_ids.add(case['id'])
                    continue
                seen_cases.add(case['id'])
                case_observation = conn.execute('SELECT attempt_id FROM observation WHERE id=?', (evidence['observation_id'],)).fetchone()
                case_ref = 'source:' + digest([version_id, case_receipt['id'], evidence['locator']])
                if case_ref not in source_refs:
                    source_refs.add(case_ref)
                    sources.append(dict(zip(SOURCE_COLUMNS, [case_ref, version_id, case_receipt['source'], case_receipt['designation'], case_receipt['id'], case_observation['attempt_id'], case_receipt['artifact_sha'], evidence['locator'], None, None, json.loads(case_receipt['metadata']).get('as_of'), case_receipt['received_at']])))
                issues.append({**common, 'source_ref': case_ref, 'issue_id': case['id'], 'kind': case['kind'], 'status': case['status'], 'field': case['field_name'], 'issue': case['issue'], 'listed_value': evidence.get('listing_value'), 'proposed_value': case['proposal'], 'observed_value': case['observed'], 'case_version': case['version']})
        # Findings apply to the entire version, even for an office selection. They
        # carry blank row keys so consumers cannot mistake them for office facts.
        reviews = {r['code']: dict(r) for r in conn.execute('SELECT * FROM feed_exception WHERE version_id=? ORDER BY id', (version_id,))}
        for finding in version['report']['findings']:
            if finding['severity'] in {'hold', 'hard'}:
                review = reviews.get(finding['code'])
                issues.append({'issue_id': 'quality:' + digest([version_id, finding['code']]), 'version_id': version_id, 'kind': 'dataset_quality', 'status': review['disposition'] if review else 'unreviewed', 'issue': finding['message']})
        result = {'format_version': 1, 'version_id': version_id, 'scope': {'feed_id': version['feed_id'], 'location_id': location_id, 'kind': 'approved_feed_office' if location_id is not None else 'approved_feed'}, 'manifest': manifest, 'approval': dict(approval), 'report_hash': version['report_hash'], 'directory': directory, 'unresolved_issues': sorted(issues, key=lambda issue: issue['issue_id']), 'sources': sources, 'counts': {'directory': len(directory), 'unresolved_issues': len(issues), 'sources': len(sources), 'quarantined_rows': sum(bool(row['problems']) for row in rows), 'excluded_cross_scope_cases': len(excluded_case_ids)}}
        result['scope_notice'] = 'Work cases whose initial evidence belongs to a different dataset scope are excluded. Historical source-native work keys may retain links across scopes; this export does not rewrite those cases. Inspect excluded_cross_scope_cases before treating unresolved counts as complete.'
        result['snapshot_id'] = digest(result)
        if expected_snapshot is not None and expected_snapshot != result['snapshot_id']:
            raise Conflict('Export context changed; preview the selected approved version again')
        result['snapshot_at'] = now()
        conn.rollback()
        return result


def workbook(data: dict) -> bytes:
    """Render only materialized data; literal strings prevent formula execution."""
    book = Workbook()
    book.remove(book.active)

    def sheet(name, columns, rows):
        tab = book.create_sheet(name)
        for values in [columns, *[[row.get(key) for key in columns] for row in rows]]:
            serialized = []
            for value in values:
                if value is not None:
                    value = str(value)
                    value = re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f\ufffe\uffff]', lambda match: f'\\u{ord(match[0]):04x}', value)
                    if len(value.encode('utf-16-le')) // 2 > 32767:
                        raise ValueError('Workbook cell exceeds Excel capacity; use the JSON evidence export')
                    value = '""' if value == '' else value
                serialized.append(value)
            tab.append(serialized)
            for cell in tab[tab.max_row]:
                if cell.value is not None:
                    cell.data_type = 's'
                    cell.number_format = '@'
        tab.freeze_panes = 'A2'
        tab.auto_filter.ref = tab.dimensions
        for cell in tab[1]:
            cell.font = Font(bold=True, color='FFFFFF')
            cell.fill = PatternFill('solid', fgColor='204D58')
        for index, key in enumerate(columns, 1):
            tab.column_dimensions[get_column_letter(index)].width = min(48, max(18, len(key) + 3))

    sheet('Directory', DIRECTORY_COLUMNS, data['directory'])
    sheet('Unresolved issues', ISSUE_COLUMNS, data['unresolved_issues'])
    details = [
        ('format_version', data['format_version']), ('version_id', data['version_id']), ('snapshot_id', data['snapshot_id']), ('snapshot_at_utc', data['snapshot_at']),
        ('scope', json.dumps(data['scope'], sort_keys=True)), ('counts', json.dumps(data['counts'], sort_keys=True)),
        ('approval', json.dumps(data['approval'], sort_keys=True)), ('manifest', json.dumps(data['manifest'], sort_keys=True)),
        ('report_hash', data['report_hash']), ('scope_notice', data['scope_notice']),
        ('semantics', 'Directory contains only the selected explicitly approved source version. Pending work proposals never replace its values. Local approval is not external verification.'),
        ('issue_scope', 'Open work linked to retained selected-version observations with the same initial evidence dataset scope; excludes resolved/verified and separately reports excluded cross-scope case count. Quarantines are excluded from Directory. Dataset quality findings apply to the whole version, including office selections. Later unapproved deliveries are not included.'),
        ('identifiers', 'Feed-scoped source-record/office keys are not canonical clinician or office identity links. A native record ID may identify a provider-office row; no clinician key is inferred. directory_row_id is stable across feed versions for the native record/office pair. source_ref resolves below to retained receipt, artifact SHA256 and original row locator.'),
        ('values', 'All populated cells are literal text. Blank = null/absent; two quotes = empty string. XML controls are escaped in display; JSON preserves exact values. No formulas, hyperlinks or external links.'),
        ('consistency', 'All database reads share one read-only transaction. Directory is immutable; open work status is as of snapshot. Preview snapshot_id detects changed work context before download.'),
    ]
    # One sheet includes metadata rows and the source-reference table, each marked
    # by entry_type rather than incompatible header blocks.
    columns = ['entry_type', 'detail_key', 'detail_value', *SOURCE_COLUMNS]
    sheet('Sources and export details', columns, [{'entry_type': 'detail', 'detail_key': key, 'detail_value': value} for key, value in details] + [{'entry_type': 'source', **source} for source in data['sources']])
    output = io.BytesIO()
    book.save(output)
    book.close()
    return output.getvalue()
