"""Literal workbook cells and lossless authoritative selected-plan payload."""
from copy import deepcopy
import io
import json
from zipfile import ZipFile

from openpyxl import load_workbook
import pytest

from provider_directory_truth_layer import follow_up_export


def selected_plan():
    return {"format_version": 1, "snapshot": "001-snapshot",
            "confirmation": {"id": "confirmation", "proposal_id": "proposal", "impact_snapshot": "impact",
                "plan_snapshot": "plan", "assessment": {"counts": {"affected": 1, "not_assessed": 2},
                    "targets": [{"ref": "ref", "evaluation_ref": "payer:P1", "source": "payer",
                                 "classification": "affected", "reason": "Needs local review", "value": None}],
                    "existing_work": []}, "plan": {"actions": [{"action": "create"}]},
                "actor": "Reviewer", "reason": "Explicit confirmation", "created_at": "2026-10-30"},
            "proposal": {"id": "proposal", "proposed_original": "2125550111", "proposed_value": {"number": "2125550111", "extension": None},
                         "prior_evidence": {"npi": "0000000001"}, "records": []},
            "associations": [{"id": "association", "confirmation_id": "confirmation", "proposal_id": "proposal",
                "target_key": "target", "field": "phone", "case_id": "case", "refs": ["ref"],
                "evidence": {"source": "payer", "network_id": "network", "network_label": "CEDAR", "refs": ["ref"], "action": "create"},
                "case_version_at_confirmation": 1, "action": "create", "actor": "Reviewer", "reason": "Review required", "created_at": "2026-10-30"}],
            "cases": [{"id": "case", "kind": "qa", "field_name": "phone", "owner": None, "status": "new", "version": 1,
                "evidence": {"npi": "0000000001"}, "events": [{"id": "event", "action": "create", "actor": "Reviewer", "reason": "Confirmed plan",
                    "payload": {"flag": True}, "from_status": None, "to_status": "new", "occurred_at": "2026-10-30"}]}],
            "acknowledgements": [{"id": "ack", "association_id": "association", "request_id": "request", "previous_id": None,
                "case_version": 1, "actor": "Reviewer", "reason": "Received; not verified", "created_at": "2026-10-30"}],
            "source_context": [{"native_id": "00001", "npi": "0000000001", "nullable": None, "empty": "", "integer": 2**65, "truth": False}],
            "current_source_inputs_fresh": False, "source_stale_reasons": ["New source interpretation"]}


def decode_payload(book):
    chunks = sorted(book["Payload"].iter_rows(min_row=2, values_only=True), key=lambda row: int(row[0]))
    assert [int(row[0]) for row in chunks] == list(range(1, len(chunks) + 1))
    assert all(len(row[1]) <= 30000 and row[1].isascii() for row in chunks)
    return json.loads("".join(row[1] for row in chunks))


def test_selected_plan_roundtrips_complete_payload_and_renders_boundaries_without_mutation():
    data = selected_plan()
    before = deepcopy(data)
    output = follow_up_export.workbook(data)
    assert isinstance(output, bytes)
    assert data == before
    book = load_workbook(io.BytesIO(output), data_only=False)
    assert book.sheetnames == ["Read me", "Plan", "Work history", "Acknowledgements", "Assessment", "Payload"]
    assert decode_payload(book) == data
    assert book["Plan"].max_row == 2 and book["Work history"].max_row == 2
    assert book["Acknowledgements"].max_row == 2 and book["Assessment"].max_row == 2
    notes = " ".join(str(cell.value) for row in book["Read me"] for cell in row)
    assert "QA review cases" in notes
    assert "does not verify" in notes
    assert "source assertions remain unchanged" in notes
    assert "Assessment counts" in notes and "not_assessed" in notes
    assert "false" in notes
    book.close()


def test_formula_like_values_controls_unicode_and_oversized_fields_are_literal_and_lossless():
    data = selected_plan()
    data["associations"][0]["actor"] = '=HYPERLINK("https://example.invalid","click")'
    data["associations"][0]["reason"] = "+cmd|' /C calc'!A0"
    data["associations"][0]["id"] = -123
    data["associations"][0]["evidence"]["network_label"] = "@SUM(1,2)"
    data["cases"][0]["owner"] = "-2+3"
    data["cases"][0]["evidence"] = {"controls": "\x00\t\n\r\x85\ud800\ufffe🚀", "npi": "0000000001"}
    data["cases"][0]["events"][0]["reason"] = "🚀" * 20000
    data["acknowledgements"][0]["reason"] = "x" * 90001
    data["source_context"][0]["numeric_id"] = 9007199254740993
    output = follow_up_export.workbook(data)
    book = load_workbook(io.BytesIO(output), data_only=False)
    assert decode_payload(book) == data
    assert book["Payload"].max_row > 4
    for sheet in book:
        for row in sheet:
            for cell in row:
                if cell.value is not None:
                    assert isinstance(cell.value, str)
                    assert cell.data_type == "s" and cell.number_format == "@"
                    assert cell.hyperlink is None
    history = list(book["Work history"].iter_rows(min_row=2, values_only=True))[0]
    assert "\\u0000" in history[6] and "\\ud800" in history[6]
    assert "display truncated" in history[10]
    assert "#/cases/0/events/0/reason" in history[10]
    ack = list(book["Acknowledgements"].iter_rows(min_row=2, values_only=True))[0]
    assert "#/acknowledgements/0/reason" in ack[6]
    assert book["Plan"]["M2"].value.startswith("=HYPERLINK")
    book.close()
    with ZipFile(io.BytesIO(output)) as archive:
        assert not any("externalLink" in path for path in archive.namelist())
        for path in archive.namelist():
            if path.startswith("xl/worksheets/") and path.endswith(".xml"):
                assert b"<f>" not in archive.read(path)


def test_missing_event_history_and_empty_lists_keep_complete_typed_payload():
    data = selected_plan()
    data["cases"][0]["events"] = []
    data["cases"][0]["owner"] = ""
    data["associations"] = []
    data["acknowledgements"] = []
    data["confirmation"]["assessment"]["targets"] = []
    book = load_workbook(io.BytesIO(follow_up_export.workbook(data)))
    assert decode_payload(book) == data
    assert book["Plan"].max_row == book["Acknowledgements"].max_row == book["Assessment"].max_row == 1
    assert book["Work history"]["D2"].value == '""'
    assert book["Work history"]["H2"].value == "null"
    book.close()


@pytest.mark.parametrize("large_section", ["payload", "events", "associations", "acknowledgements", "targets"])
def test_every_sheet_is_guarded_before_excel_row_capacity(monkeypatch, large_section):
    data = selected_plan()
    monkeypatch.setattr(follow_up_export, "MAX_SHEET_ROWS", 11)
    if large_section == "payload":
        data["source_context"] = ["x" * 330001]
    elif large_section == "events":
        data["cases"][0]["events"] *= 11
    elif large_section == "targets":
        data["confirmation"]["assessment"]["targets"] *= 11
    else:
        data[large_section] *= 11
    with pytest.raises(ValueError, match="row capacity"):
        follow_up_export.workbook(data)


def test_non_json_numeric_values_are_rejected_without_partial_output():
    data = selected_plan()
    data["proposal"]["proposed_original"] = float("nan")
    with pytest.raises(ValueError):
        follow_up_export.workbook(data)
