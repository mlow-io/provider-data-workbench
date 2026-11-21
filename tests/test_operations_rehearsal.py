"""Inspect combined owned artifacts and durable state independently of summary flags."""
import json
from pathlib import Path
import subprocess
import sys

import pytest

from provider_directory_truth_layer.approved_consumer import consume, sha
from provider_directory_truth_layer.identity_review import IdentityReview
from provider_directory_truth_layer.intake_store import IntakeStore
from provider_directory_truth_layer.managed_feed import ManagedFeed
from provider_directory_truth_layer.operations_rehearsal import rehearse, work_payloads, xlsx_payload


@pytest.fixture(scope='module')
def journey(tmp_path_factory):
    root = tmp_path_factory.mktemp('operations-parent') / 'journey'
    report = rehearse(root)
    return root, report


def test_pinned_consumer_and_unacknowledged_hold_survive_recovery(journey):
    root, report = journey
    raw = (root / 'exports/approved.json').read_bytes()
    contact = consume(raw, report['approved_version_id'], expected_feed=report['feed_id'])
    assert [(row['location_id'], row['phone'], row['phone_extension'], row['zip']) for row in contact['contacts']] == [
        ('NORTH', '6175550100', '007', '02108'), ('SOUTH', '6175550200', '008', '02108')]
    for folder in ('storage', 'restored'):
        store = IntakeStore.open_existing(root / folder / 'directory.sqlite3', root / folder)
        feeds = ManagedFeed(store)
        assert feeds.current(report['feed_id'])['version_id'] == report['approved_version_id']
        held = feeds.version(report['held_version_id'])
        assert held['state'] == 'candidate' and held['report']['comparison']['missing_from_this_delivery'] == 1
        assert {finding['code'] for finding in held['report']['findings'] if finding['severity'] == 'hold'} >= {'missing_keys', 'row_count_drift'}
        assert held['review'] == []
        assert json.loads(raw) == feeds.export(report['approved_version_id'])
        with store.db() as conn:
            assert conn.execute('SELECT count(*) FROM feed_decision').fetchone()[0] == 1
            assert conn.execute('SELECT count(*) FROM feed_delivery').fetchone()[0] == 2
            assert conn.execute('SELECT count(*) FROM network').fetchone()[0] == 0
            assert conn.execute('PRAGMA integrity_check').fetchone()[0] == 'ok'
            assert not conn.execute('PRAGMA foreign_key_check').fetchall()
    assert not (root / 'consumer-must-not-open-storage').exists()


def test_scoped_native_and_investigation_downloads_keep_pages_contacts_and_unknowns(journey):
    root, report = journey
    field = json.loads((root / 'exports/north-fields.json').read_bytes())
    phone = next(item for item in field['fields'] if item['field'] == 'phone')
    assert phone['preferred_value'] == {'number': '6175550199', 'extension': None}
    assert xlsx_payload((root / 'exports/north-fields.xlsx').read_bytes()) == field
    for receipt in (report['saved_receipt_id'], report['acquired_receipt_id']):
        locators = {context['row']['locator'] for context in field['source_context'] if context['receipt']['id'] == receipt}
        assert '$.entry[3].resource' in locators and '$.entry[5].resource' in locators
        assert '$.entry[4].resource' not in locators and '$.entry[6].resource' not in locators
    original = json.loads((root / 'inputs/directory.json').read_bytes())
    assert original['entry'][4]['resource']['id'] == 'south'  # Original shared context stays complete.
    store = IntakeStore.open_existing(root / 'storage/directory.sqlite3', root / 'storage')
    native = next(option for option in phone['options'] if option['receipt_id'] == report['acquired_receipt_id'])
    phone_ref = next(ref for ref in native['supporting_refs'] if ref['field'] == 'phone')
    origin = phone_ref['source_pages'][0]
    page = (store.artifacts / origin['artifact_sha']).read_bytes()
    assert sha(page) == origin['artifact_sha']
    assert any(entry['resource'].get('id') == 'north' and entry['resource']['telecom'][0]['value'] == '6175550199' for entry in json.loads(page)['entry'])
    work = json.loads((root / 'exports/north-investigation.json').read_bytes())
    assert len(work['cases']) == 1 and work['cases'][0]['id'] == report['north_case_id']
    assert work['investigations'][0]['status'] == 'reopened' and len(work['investigations'][0]['outreach']) == 2
    assert [item['payload']['outcome'] for item in work['investigations'][0]['outreach']] == ['no_answer', 'response_received']
    assert all(row['normalized']['location_id'] == 'NORTH' for row in work['evidence'])
    decoded = list(work_payloads((root / 'exports/north-investigation.xlsx').read_bytes()).values())
    assert work['cases'][0] in decoded and work['investigations'][0] in decoded
    for name, expected in report['dossier']['files'].items():
        assert sha((root / 'exports' / name).read_bytes()) == expected


def test_unresolved_candidate_and_failed_captures_are_retained_without_promotion(journey):
    root, report = journey
    store = IntakeStore.open_existing(root / 'storage/directory.sqlite3', root / 'storage')
    reviewed = IdentityReview(store).inspect(report['dossier']['identity_review_run_id'], report['deferred_location_candidate_id'])
    assert reviewed['latest_decision']['decision'] == 'defer' and reviewed['latest_decision']['target_id'] is None
    with store.db() as conn:
        rows = conn.execute('SELECT state,receipt_id,checkpoint FROM fhir_acquisition ORDER BY created_at').fetchall()
        assert [row['state'] for row in rows] == ['complete', 'retry_wait', 'failed', 'failed', 'failed']
        assert all(row['receipt_id'] is None for row in rows[1:])
        assert json.loads(rows[2]['checkpoint'])['pages'] == 1
        assert conn.execute("SELECT count(*) FROM assistant_run_event WHERE kind='invocation_started'").fetchone()[0] == 0
    assert len(report['controlled_http_requests']) == 7
    assert report['verified_original_page_references'] >= 5
    workbook = store.detail(report['workbook_receipt_id'])
    assert workbook['preview']['valid_count'] == 1 and workbook['preview']['quarantined_count'] == 2
    assert len(workbook['observations']) == 1 and workbook['observations'][0]['normalized']['location_id'] == 'SOUTH'


def test_cli_and_function_refuse_existing_roots_without_changing_artifacts(journey):
    root, _ = journey
    before = (root / 'operations-rehearsal.json').read_bytes()
    with pytest.raises(ValueError, match='existing storage'): rehearse(root)
    result = subprocess.run([sys.executable, '-m', 'provider_directory_truth_layer.cli', 'rehearse-operations', '--root', str(root)], capture_output=True, text=True, timeout=15)
    assert result.returncode == 2 and (root / 'operations-rehearsal.json').read_bytes() == before
