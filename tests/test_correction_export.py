"""Independently inspect the reviewed correction in actual JSON and XLSX output."""
import io

import pytest
from fastapi.testclient import TestClient
from openpyxl import load_workbook

from provider_directory_truth_layer.field_materialization import FieldMaterialization
from provider_directory_truth_layer.intake_api import create_workbench
from provider_directory_truth_layer.review_workbook import snapshot, workbook, preview
from test_field_materialization import fixture
from test_managed_feed import approve
from test_review_workbook import sheet_rows


def test_correction_export_keeps_office_values_source_and_decision_lineage(tmp_path):
    store, feeds, feed, base, payload, _, _ = fixture(tmp_path)
    before = snapshot(store.path, base)
    candidate = FieldMaterialization(store).create(base, payload)
    assert snapshot(store.path, base)['snapshot_id'] == before['snapshot_id']
    with pytest.raises(ValueError, match='approved'):
        snapshot(store.path, candidate)
    approve(feeds, candidate)
    selected = snapshot(store.path, candidate)
    assert selected['format_version'] == 2
    assert selected['counts']['corrections'] == 1
    assert selected['counts']['directory'] == before['counts']['directory']
    directory = {row['location_id']: row for row in selected['directory']}
    assert directory['NORTH']['phone'] == '6175550199'
    assert directory['NORTH']['phone_extension'] == '0042'
    assert directory['SOUTH']['phone'] == '6175550102'
    assert directory['SOUTH']['correction_ref'] is None
    correction = selected['corrections'][0]
    assert correction['correction_ref'] == directory['NORTH']['correction_ref']
    assert correction['directory_row_id'] == directory['NORTH']['directory_row_id']
    assert correction['old_phone'] == '6175550101'
    assert correction['new_phone'] == '6175550199'
    assert correction['new_extension'] == '0042'
    assert correction['decision_id'] == payload['decision_id']
    assert correction['base_version'] == base
    assert correction['actor'] == payload['actor']
    assert correction['reason'] == payload['reason']
    assert correction['link_ids']
    source = next(row for row in selected['sources'] if row['source_ref'] == correction['selected_source_ref'])
    assert source['source'] == 'synthetic-reference'
    assert (store.artifacts / source['artifact_sha256']).exists()
    assert source['receipt_id'] != selected['manifest']['receipt_id']
    # Independent binary-reader checks, not just comparing a writer's input dict.
    book = load_workbook(io.BytesIO(workbook(selected)), data_only=False)
    assert 'Reviewed corrections' in book.sheetnames
    actual = {row['location_id']: row for row in sheet_rows(book, 'Directory')}
    assert actual['NORTH']['phone_extension'] == '0042'
    assert actual['NORTH']['zip'] == '02108'
    assert actual['NORTH']['phone'] == '6175550199'
    assert actual['SOUTH']['phone'] == '6175550102'
    ledger = sheet_rows(book, 'Reviewed corrections')
    assert len(ledger) == 1
    assert ledger[0]['decision_id'] == payload['decision_id']
    assert ledger[0]['selected_source_ref'] == source['source_ref']
    assert all(cell.data_type != 'f' and not cell.hyperlink for sheet in book for row in sheet for cell in row)
    book.close()
    sample = preview(store.path, candidate, limit=1)
    assert sample['counts'] == selected['counts']
    assert sample['snapshot_id'] == selected['snapshot_id']
    assert sample['preview']['returned']['corrections'] == 1
    client = TestClient(create_workbench(store.path, store.root, demo=False))
    url = f'/api/feed-versions/{candidate}/review-export'
    response = client.get(url, params={'expected_snapshot': sample['snapshot_id']})
    assert response.status_code == 200
    assert response.json()['corrections'][0]['decision_id'] == payload['decision_id']
    downloaded = client.get(url, params={'format': 'xlsx', 'expected_snapshot': sample['snapshot_id']})
    assert downloaded.status_code == 200
    downloaded_book = load_workbook(io.BytesIO(downloaded.content))
    assert sheet_rows(downloaded_book, 'Reviewed corrections')[0]['new_extension'] == '0042'
    downloaded_book.close()
    # Prior approved output and its source bytes remain readable after promotion.
    assert snapshot(store.path, base)['snapshot_id'] == before['snapshot_id']
    assert feeds.export(base)['records'][0]['original']
