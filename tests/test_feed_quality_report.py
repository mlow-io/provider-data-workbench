"""Complete preapproval quality evidence stays separate from dataset exports."""
import csv
import hashlib
import io
import json

import pytest
from fastapi.testclient import TestClient

from provider_directory_truth_layer.intake_api import create_workbench
from provider_directory_truth_layer.intake_store import digest, packed, uid
from test_managed_feed import ATTR, FIELDS, approve, setup_feed


def write_delivery(inbox, name, period, changed=False):
    stream = io.StringIO(newline='')
    writer = csv.writer(stream)
    writer.writerow(FIELDS)
    for index in range(51):
        writer.writerow([f'ROW-{index:03}', '1234567890', 'Synthetic Clinician',
                         '10 Fiction Street', 'Example', 'MA', '02108',
                         '6175550199' if changed and index == 50 else '6175550101',
                         f'OFFICE-{index:03}'])
    data = stream.getvalue().encode()
    (inbox / f'{name}.csv').write_bytes(data)
    (inbox / f'{name}.manifest.json').write_text(json.dumps({
        'delivery_id': name, 'period': period, 'as_of': period, 'snapshot': 'full',
        'filename': f'{name}.csv', 'sha256': hashlib.sha256(data).hexdigest()}))


def seed_corrected_baseline(store, base_id):
    """Seed many corrected keys; other tests cover authentic correction creation."""
    with store.db() as conn:
        base = dict(conn.execute('SELECT * FROM feed_version WHERE id=?', (base_id,)).fetchone())
        job = dict(conn.execute('SELECT * FROM feed_job WHERE id=?', (base['job_id'],)).fetchone())
        delivery = dict(conn.execute('SELECT * FROM feed_delivery WHERE id=?', (job['delivery_id'],)).fetchone())
        delivery['id'], delivery['source_id'] = uid(), 'synthetic-many-corrections'
        job['id'], job['delivery_id'], job['baseline_version'] = uid(), delivery['id'], base_id
        rows = json.loads(base['rows'])
        for index, row in enumerate(rows):
            row['materialization'] = {'decision_id': f'synthetic-decision-{index:03}'}
        manifest = json.loads(base['manifest'])
        manifest['records_sha256'] = digest([row for row in rows if not row['problems']])
        base['id'], base['job_id'], base['manifest'], base['rows'] = uid(), job['id'], packed(manifest), packed(rows)
        for table, item in [('feed_delivery', delivery), ('feed_job', job), ('feed_version', base)]:
            columns = ','.join(item)
            conn.execute(f"INSERT INTO {table} ({columns}) VALUES ({','.join('?' for _ in item)})", tuple(item.values()))
        conn.execute('INSERT INTO feed_decision VALUES (?,?,?,?,?,?,?)',
                     (base['id'], 'approved', 'Synthetic reviewer', 'Seed corrected baseline',
                      'synthetic-request', 'synthetic-corrected-baseline', '2026-10-06T00:00:00Z'))
        conn.execute('UPDATE feed SET current_version=? WHERE id=?', (base['id'], base['feed_id']))
    return base['id']


def database_dump(store):
    with store.db() as conn:
        return list(conn.iterdump())


def test_complete_candidate_report_exposes_drift_beyond_bounded_sample_without_writes(tmp_path):
    store, feeds, feed, inbox = setup_feed(tmp_path)
    write_delivery(inbox, 'first', '2026-10-05')
    first = feeds.run_once(feed['id'], '2026-10-06T10:00:00+00:00')['version_id']
    approve(feeds, first)
    corrected = seed_corrected_baseline(store, first)
    write_delivery(inbox, 'next', '2026-10-12', changed=True)
    result = feeds.run_once(feed['id'], '2026-10-13T10:00:00+00:00')
    assert 'error' not in result, result
    candidate = result['version_id']
    client = TestClient(create_workbench(store.path, store.root, demo=False))
    before = database_dump(store)

    detail = client.get(f'/api/feed-versions/{candidate}').json()
    effective = detail['report']['effective_corrections']
    assert effective['total'] == 51 and effective['entry_count'] == 51
    assert len(effective['entries']) == 50
    assert {entry['status'] for entry in effective['entries']} == {'unchanged'}
    assert effective['counts']['changed'] == 1
    response = client.get(f'/api/feed-versions/{candidate}/quality-report')
    assert response.status_code == 200
    assert response.headers['content-disposition'] == f'attachment; filename=quality-review-{candidate}.json'
    report = response.json()
    assert set(report) == {'version_id', 'feed_id', 'state', 'report_hash', 'report', 'notice'}
    assert (report['version_id'], report['feed_id'], report['state'], report['report_hash']) == (candidate, feed['id'], 'candidate', detail['report_hash'])
    assert report['notice'] == 'Review evidence only; not an approved dataset export'
    entries = report['report']['effective_corrections']['entries']
    assert len(entries) == 51 and entries[50]['status'] == 'changed'
    assert entries[50]['old']['phone'] == '6175550101'
    assert entries[50]['new']['phone'] == '6175550199'
    assert client.get(f'/api/feed-versions/{candidate}/export').status_code == 422
    page_url = f'/api/feed-versions/{candidate}/correction-comparison'
    page = client.get(page_url, params={'expected_report': detail['report_hash'], 'status': 'changed', 'limit': 1})
    assert page.status_code == 200
    assert page.json()['total'] == 1 and page.json()['entries'][0]['new']['phone'] == '6175550199'
    assert page.json()['next_offset'] is None
    all_page = client.get(page_url, params={'expected_report': detail['report_hash'], 'offset': 50, 'limit': 1}).json()
    assert all_page['total'] == 51 and all_page['entries'][0]['status'] == 'changed'
    assert client.get(page_url, params={'expected_report': 'stale'}).status_code == 409
    assert client.get(page_url, params={'expected_report': detail['report_hash'], 'status': 'invalid'}).status_code == 422
    assert client.get(page_url, params={'expected_report': detail['report_hash'], 'limit': 101}).status_code == 422
    assert client.get('/api/feed-versions/missing/quality-report').status_code == 404
    assert client.get(f'/api/feed-versions/{corrected}/quality-report').json()['state'] == 'approved'
    assert database_dump(store) == before
    assert feeds.current(feed['id'])['version_id'] == corrected
    with pytest.raises(ValueError, match='hold'):
        approve(feeds, candidate)
    assert feeds.current(feed['id'])['version_id'] == corrected
    feeds.decide(candidate, {'decision': 'rejected', 'expected_report': detail['report_hash'],
                             'expected_current': corrected, 'idempotency_key': 'reject-candidate', **ATTR})
    assert client.get(f'/api/feed-versions/{candidate}/quality-report').json()['state'] == 'rejected'
