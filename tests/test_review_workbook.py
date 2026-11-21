"""Inspect actual workbook values against synthetic managed-feed decisions."""
import io
import sqlite3

import pytest
from fastapi.testclient import TestClient
from openpyxl import load_workbook

from provider_directory_truth_layer.intake_api import create_workbench
from provider_directory_truth_layer.intake_store import Conflict
from provider_directory_truth_layer.review_workbook import snapshot, workbook
from test_managed_feed import approve, deliver, setup_feed


def sheet_rows(book, name):
    iterator = book[name].iter_rows(values_only=True)
    headers = next(iterator)
    return [dict(zip(headers, values)) for values in iterator]


def ready(tmp_path):
    store, service, feed, inbox = setup_feed(tmp_path)
    deliver(inbox)
    result = service.run_once(feed['id'])
    approve(service, result['version_id'])
    return store, service, feed, inbox, result['version_id']


def test_workbook_pins_approved_values_scope_identifiers_and_sources(tmp_path):
    store, service, feed, inbox, version = ready(tmp_path)
    north = snapshot(store.path, version, 'NORTH')
    assert north['counts'] == {'directory': 1, 'unresolved_issues': 1, 'sources': 1, 'quarantined_rows': 0, 'excluded_cross_scope_cases': 0}
    issue = north['unresolved_issues'][0]
    with store.db() as conn:
        conn.execute("UPDATE work_case SET proposal='6175550199',status='approved',version=version+1 WHERE id=?", (issue['issue_id'],))
    with pytest.raises(Conflict, match='changed'):
        snapshot(store.path, version, 'NORTH', north['snapshot_id'])
    fresh = snapshot(store.path, version, 'NORTH')
    deliver(inbox, 'clean_update.csv', 'next', '2026-10-12')
    next_version = service.run_once(feed['id'])['version_id']
    # Pending deliveries do not change the selected immutable approved roster.
    assert snapshot(store.path, version, 'NORTH')['snapshot_id'] == fresh['snapshot_id']
    with pytest.raises(ValueError, match='approved'):
        snapshot(store.path, next_version)
    book = load_workbook(io.BytesIO(workbook(fresh)), data_only=False)
    assert book.sheetnames == ['Directory', 'Unresolved issues', 'Sources and export details']
    directory = sheet_rows(book, 'Directory')
    unresolved = sheet_rows(book, 'Unresolved issues')
    assert directory[0]['phone'] == '6175550101'
    assert directory[0]['zip'] == '02108'
    assert unresolved[0]['proposed_value'] == '6175550199'
    assert unresolved[0]['directory_row_id'] == directory[0]['directory_row_id']
    assert unresolved[0]['office_key'] == directory[0]['office_key']
    sources = [r for r in sheet_rows(book, 'Sources and export details') if r['entry_type'] == 'source']
    assert {r['source_ref'] for r in sources} == {directory[0]['source_ref'], unresolved[0]['source_ref']}
    assert sources[0]['artifact_sha256'] == fresh['manifest']['artifact_sha']
    assert sources[0]['row_locator']
    with pytest.raises(KeyError, match='Office'):
        snapshot(store.path, version, 'NOT-HERE')
    with store.db() as conn:
        conn.execute("UPDATE work_case SET status='verified' WHERE id=?", (issue['issue_id'],))
    assert snapshot(store.path, version, 'NORTH')['unresolved_issues'] == []


def test_literal_text_and_overflow_are_not_silently_coerced(tmp_path):
    store, _, _, _, version = ready(tmp_path)
    data = snapshot(store.path, version)
    for row, value in zip(data['directory'], ['=HYPERLINK("https://invalid")', '+123', '@SUM(A1)']):
        row['provider_name'] = value
    data['directory'][0]['record_id'] = '000001'
    data['directory'][0]['address_line2'] = ''
    data['directory'][0]['suite'] = '\x00untrusted'
    book = load_workbook(io.BytesIO(workbook(data)), data_only=False)
    rows = sheet_rows(book, 'Directory')
    assert [row['provider_name'] for row in rows] == [row['provider_name'] for row in data['directory']]
    assert rows[0]['record_id'] == '000001'
    assert rows[0]['address_line2'] == '""'
    assert rows[0]['suite'] == '\\u0000untrusted'
    assert all(cell.data_type != 'f' and cell.hyperlink is None for sheet in book for row in sheet for cell in row)
    assert not book._external_links
    data['directory'][0]['provider_name'] = 'x' * 32768
    with pytest.raises(ValueError, match='capacity'):
        workbook(data)


def test_route_preview_download_conflicts_and_no_writes(tmp_path):
    store, _, _, _, version = ready(tmp_path)
    client = TestClient(create_workbench(store.path, store.root, demo=False))
    url = f'/api/feed-versions/{version}/review-export'
    with sqlite3.connect(store.path) as conn:
        before = list(conn.iterdump())
    response = client.get(url)
    assert response.status_code == 200
    data = response.json()
    assert client.get(url, params={'format': 'xlsx'}).status_code == 422
    assert client.get(url, params={'expected_snapshot': 'stale', 'format': 'xlsx'}).status_code == 409
    response = client.get(url, params={'expected_snapshot': data['snapshot_id'], 'format': 'xlsx'})
    assert response.status_code == 200
    book = load_workbook(io.BytesIO(response.content))
    assert len(sheet_rows(book, 'Directory')) == data['counts']['directory'] == 3
    assert len(sheet_rows(book, 'Unresolved issues')) == data['counts']['unresolved_issues']
    assert client.get(url, params={'format': 'csv'}).status_code == 422
    assert client.get('/api/feed-versions/absent/review-export').status_code == 404
    with sqlite3.connect(store.path) as conn:
        assert list(conn.iterdump()) == before


def test_repeat_delivery_reuses_observations_and_links_original_case_source(tmp_path):
    store, service, feed, inbox, first = ready(tmp_path)
    deliver(inbox, delivery_id='repeat', period='2026-10-12')
    second = service.run_once(feed['id'])['version_id']
    approve(service, second)
    data = snapshot(store.path, second)
    original = snapshot(store.path, first)
    assert len(data['directory']) == len(data['unresolved_issues']) == 3
    assert {r['directory_row_id'] for r in data['directory']} == {r['directory_row_id'] for r in original['directory']}
    assert {s['receipt_id'] for s in data['sources']} == {data['manifest']['receipt_id'], original['manifest']['receipt_id']}


def test_quarantined_rows_and_acknowledged_hold_remain_explicit(tmp_path):
    store, service, feed, inbox = setup_feed(tmp_path)
    deliver(inbox, 'invalid_phone.csv')
    version = service.run_once(feed['id'])['version_id']
    detail = service.version(version)
    for finding in detail['report']['findings']:
        if finding['severity'] == 'hold':
            service.review(version, {'code': finding['code'], 'disposition': 'acknowledged', 'expected_report': detail['report_hash'], 'actor': 'Synthetic reviewer', 'reason': 'Accept valid rows only'})
    approve(service, version)
    data = snapshot(store.path, version)
    book = load_workbook(io.BytesIO(workbook(data)))
    assert {r['location_id'] for r in sheet_rows(book, 'Directory')} == {'SOUTH', 'EAST'}
    issues = sheet_rows(book, 'Unresolved issues')
    quarantine = [r for r in issues if r['kind'] == 'quarantine']
    assert len(quarantine) == data['counts']['quarantined_rows'] == 1
    assert quarantine[0]['directory_row_id'] is None
    assert any(r['kind'] == 'dataset_quality' and r['status'] == 'acknowledged' for r in issues)
    assert data['counts']['sources'] == 3


def test_all_rows_export_beyond_preview_cap(tmp_path):
    import hashlib
    import json
    store, service, feed, inbox = setup_feed(tmp_path)
    headers = 'record_id,npi,provider_name,address,city,state,zip,phone,location_id\n'
    body = ''.join(f'SYNTHETIC-{i:04d},{1234567800+i},Synthetic Clinic {i},{i} Fiction Street,Example,MA,02108,6175550101,OFFICE-{i:04d}\n' for i in range(65))
    data = (headers + body).encode()
    (inbox/'large.csv').write_bytes(data)
    manifest = {'delivery_id': 'large', 'period': '2026-10-05', 'as_of': '2026-10-05', 'snapshot': 'full', 'filename': 'large.csv', 'sha256': hashlib.sha256(data).hexdigest()}
    (inbox/'large.manifest.json').write_text(json.dumps(manifest))
    version = service.run_once(feed['id'])['version_id']
    approve(service, version)
    assert len(service.version(version)['rows']) == 50
    selected = snapshot(store.path, version)
    assert selected['counts']['directory'] == 65
    book = load_workbook(io.BytesIO(workbook(selected)))
    assert len(sheet_rows(book, 'Directory')) == 65
    assert len(sheet_rows(book, 'Unresolved issues')) == 65
    assert {r['record_id'] for r in sheet_rows(book, 'Directory')} == {f'SYNTHETIC-{i:04d}' for i in range(65)}


def test_work_context_is_one_database_snapshot(tmp_path, monkeypatch):
    from provider_directory_truth_layer import review_workbook
    store, _, _, _, version = ready(tmp_path)
    original = review_workbook.decode
    def concurrent_update(row):
        decoded = original(row)
        # The export's first SELECT has already pinned its WAL reader. A writer
        # commits before work is read; this export must still see the old work.
        with store.db() as conn:
            conn.execute("UPDATE work_case SET status='verified',version=version+1")
        return decoded
    monkeypatch.setattr(review_workbook, 'decode', concurrent_update)
    data = snapshot(store.path, version)
    assert len(data['unresolved_issues']) == 3
    assert {issue['status'] for issue in data['unresolved_issues']} == {'new'}
    monkeypatch.setattr(review_workbook, 'decode', original)
    assert snapshot(store.path, version)['unresolved_issues'] == []


def test_record_grain_and_office_namespaces_do_not_invent_clinician_identity(tmp_path):
    import hashlib
    import json
    from provider_directory_truth_layer.onboarding_service import OnboardingService
    from test_managed_feed import ATTR, FIELDS

    store, service, first_feed, first_inbox = setup_feed(tmp_path)
    payload = (
        ','.join(FIELDS) + '\n'
        'OFFICE-ROW-A,1234567890,Synthetic Avery,10 Fiction Street,Example,MA,02108,6175550101,NORTH\n'
        'OFFICE-ROW-B,1234567890,Synthetic Avery,20 Fiction Street,Example,MA,02109,6175550102,SOUTH\n'
    ).encode()

    def publish(feed, inbox, delivery_id):
        filename = delivery_id + '.csv'
        (inbox / filename).write_bytes(payload)
        (inbox / (delivery_id + '.manifest.json')).write_text(json.dumps({
            'delivery_id': delivery_id, 'period': '2026-10-05', 'as_of': '2026-10-05',
            'snapshot': 'full', 'filename': filename, 'sha256': hashlib.sha256(payload).hexdigest(),
        }))
        version = service.run_once(feed['id'])['version_id']
        approve(service, version)
        return snapshot(store.path, version)

    first = publish(first_feed, first_inbox, 'organization-a')
    second_scope = {'organization': 'synthetic-organization-b', 'dataset': 'weekly-roster'}
    receipt = store.receive(payload, 'organization-b-sample.csv', source=first_feed['source'], metadata={'scope': second_scope})
    onboarding = OnboardingService(store)
    proposal = onboarding.propose(receipt['id'], {'name': 'Organization B reviewed recipe',
        'definition': {'version': 1, 'mapping': dict(zip(FIELDS, FIELDS)), 'required': FIELDS,
                       'transforms': {'phone': ['phone_us']}},
        'expected_attempt': receipt['attempt_id'], **ATTR})
    recipe = onboarding.approve(receipt['id'], proposal['id'], {'expected_attempt': receipt['attempt_id'], **ATTR})
    inbox = tmp_path / 'organization-b-inbox'
    inbox.mkdir()
    second_feed = service.register({'name': 'Synthetic organization B', 'source': first_feed['source'],
        'scope': second_scope, 'owner': 'Synthetic operator', 'inbox': str(inbox), 'start_date': '2026-10-05', **ATTR})
    contract = service.propose_contract(second_feed['id'], {'definition': {'recipe_revision_id': recipe['id'], 'required_headers': FIELDS}, **ATTR})
    approved_contract = service.approve_contract(second_feed['id'], contract['id'], ATTR)
    second_feed = service.configure(second_feed['id'], {'expected_revision': second_feed['revision'],
        'config': {'contract_id': approved_contract['id'], 'enabled': True}, **ATTR})
    second = publish(second_feed, inbox, 'organization-b')

    first_book = load_workbook(io.BytesIO(workbook(first)))
    second_book = load_workbook(io.BytesIO(workbook(second)))
    first_rows = sheet_rows(first_book, 'Directory')
    second_rows = sheet_rows(second_book, 'Directory')
    assert {row['npi'] for row in first_rows} == {'1234567890'}
    assert {row['record_id'] for row in first_rows} == {'OFFICE-ROW-A', 'OFFICE-ROW-B'}
    assert len({row['source_record_key'] for row in first_rows}) == 2
    assert all('clinician_key' not in row for row in first_rows)
    first_north = next(row for row in first_rows if row['location_id'] == 'NORTH')
    second_north = next(row for row in second_rows if row['location_id'] == 'NORTH')
    assert first_north['record_id'] == second_north['record_id']
    assert first_north['source_record_key'] != second_north['source_record_key']
    assert first_north['office_key'] != second_north['office_key']
    # Preserve the export guard for historical polluted links from before the
    # source-work scope fix. New cases are now isolated; reproduce only the old
    # extra links in this owned synthetic database, without changing case keys.
    north_case = next(issue for issue in first['unresolved_issues'] if issue['office_key'] == first_north['office_key'])
    assert len(first['unresolved_issues']) == len(second['unresolved_issues']) == 2
    assert {issue['issue_id'] for issue in first['unresolved_issues']}.isdisjoint({issue['issue_id'] for issue in second['unresolved_issues']})
    with store.db() as conn:
        for issue in first['unresolved_issues']:
            source_record = next(row['record_id'] for row in first['directory'] if row['directory_row_id'] == issue['directory_row_id'])
            observation = conn.execute('SELECT id FROM observation WHERE attempt_id=? AND native_id=?', (second['manifest']['attempt_id'], source_record)).fetchone()
            conn.execute('INSERT INTO work_evidence VALUES (?,?)', (issue['issue_id'], observation['id']))
        conn.execute("UPDATE work_case SET proposal='6175550199',version=version+1 WHERE id=?", (north_case['issue_id'],))
    first_current = snapshot(store.path, first['version_id'])
    second_current = snapshot(store.path, second['version_id'])
    assert any(issue['proposed_value'] == '6175550199' for issue in first_current['unresolved_issues'])
    assert len(second_current['unresolved_issues']) == 2
    assert all(issue['proposed_value'] != '6175550199' for issue in second_current['unresolved_issues'])
    assert second_current['counts']['excluded_cross_scope_cases'] == 2
    assert second_current['scope_notice']
    guarded_book = load_workbook(io.BytesIO(workbook(second_current)))
    details = {row['detail_key']: row['detail_value'] for row in sheet_rows(guarded_book, 'Sources and export details') if row['entry_type'] == 'detail'}
    assert json.loads(details['counts'])['excluded_cross_scope_cases'] == 2
    assert 'different dataset scope' in details['scope_notice']
    assert len(second_current['sources']) == 2  # no other organization's initial case evidence
    assert len(first_current['unresolved_issues']) == 2  # original work was preserved
    for book in (first_book, second_book):
        directory = {row['directory_row_id']: row for row in sheet_rows(book, 'Directory')}
        for issue in sheet_rows(book, 'Unresolved issues'):
            if issue['directory_row_id']:
                target = directory[issue['directory_row_id']]
                assert issue['office_key'] == target['office_key']
                assert issue['source_record_key'] == target['source_record_key']
