"""Pure workbook rendering for one selected, explicitly confirmed follow-up plan."""
from __future__ import annotations

import io
import json
import re

from openpyxl import Workbook

MAX_SHEET_ROWS = 1_048_576
JSON_CHUNK_SIZE = 30_000
DISPLAY_LIMIT = 14_000  # Also below Excel's limit when every character is astral.
_CONTROLS = re.compile(r"[\x00-\x1f\x7f-\x9f\ud800-\udfff\ufffe\uffff]")


def _display(value, pointer):
    if isinstance(value, str):
        text = value if value else '""'
        text = _CONTROLS.sub(lambda match: f"\\u{ord(match[0]):04x}", text)
    else:
        text = json.dumps(value, ensure_ascii=True, sort_keys=True, allow_nan=False)
    if len(text) > DISPLAY_LIMIT:
        text = text[:DISPLAY_LIMIT] + f" [display truncated; complete value in Payload JSON {pointer}]"
    return text


def workbook(data: dict) -> bytes:
    """Return XLSX bytes without mutating data or accessing persistence.

    Readable sheets are indexes. The complete authoritative Payload includes all
    original values and types, including undisplayed fields and source context.
    Joining json_chunk in numeric part order and parsing JSON reconstructs data.
    """
    encoded = json.dumps(data, ensure_ascii=True, sort_keys=True, allow_nan=False)
    confirmation = data["confirmation"]
    associations = data["associations"]
    cases = data["cases"]
    acknowledgements = data["acknowledgements"]
    assessment = confirmation["assessment"]
    targets = assessment.get("targets", [])
    sizes = {"Payload": 1 + (len(encoded) + JSON_CHUNK_SIZE - 1) // JSON_CHUNK_SIZE,
             "Plan": 1 + len(associations),
             "Work history": 1 + sum(max(1, len(case.get("events", []))) for case in cases),
             "Acknowledgements": 1 + len(acknowledgements),
             "Assessment": 1 + len(targets), "Read me": 11}
    if any(rows > MAX_SHEET_ROWS for rows in sizes.values()):
        raise ValueError("Export exceeds spreadsheet row capacity")

    book = Workbook()
    notes = book.active
    notes.title = "Read me"
    notes.append(["Topic", "Meaning"])
    notes.append(["Boundary", "Explicitly confirmed local follow-up plan. Tasks are QA review cases; source assertions remain unchanged."])
    notes.append(["Acknowledgement", "An acknowledgement records receipt/action context. It does not verify a correction or an external directory change."])
    notes.append(["Scope", "This workbook contains the selected confirmed plan and its retained assessment, associations, cases and history."])
    notes.append(["Authoritative payload", "Join Payload json_chunk in numeric part order and parse JSON to reconstruct the complete export, including source_context and all original types."])
    notes.append(["Readable displays", 'Null displays as null; an empty string displays as "". Controls are escaped. Truncated displays identify the complete value by Payload JSON pointer.'])
    notes.append(["Confirmation", _display(confirmation.get("id"), "#/confirmation/id")])
    notes.append(["Snapshot", _display(data.get("snapshot"), "#/snapshot")])
    notes.append(["Current source inputs fresh", _display(data.get("current_source_inputs_fresh"), "#/current_source_inputs_fresh")])
    notes.append(["Source stale reasons", _display(data.get("source_stale_reasons"), "#/source_stale_reasons")])
    notes.append(["Assessment counts", _display(assessment.get("counts"), "#/confirmation/assessment/counts")])

    plan = book.create_sheet("Plan")
    plan.append(["association_id", "confirmation_id", "proposal_id", "target_key", "field", "case_id", "action",
                 "source", "network_id", "network_label", "refs", "case_version_at_confirmation", "actor", "reason", "created_at"])
    for index, association in enumerate(associations):
        evidence = association.get("evidence") or {}
        values = [(key, association.get(key)) for key in
                  ("id", "confirmation_id", "proposal_id", "target_key", "field", "case_id", "action")]
        values += [("evidence/" + key, evidence.get(key)) for key in ("source", "network_id", "network_label")]
        values += [(key, association.get(key)) for key in ("refs", "case_version_at_confirmation", "actor", "reason", "created_at")]
        plan.append([_display(value, f"#/associations/{index}/{key}") for key, value in values])

    history = book.create_sheet("Work history")
    history.append(["case_id", "kind", "field_name", "owner", "current_status", "current_version", "case_evidence",
                    "event_id", "action", "actor", "reason", "payload", "from_status", "to_status", "occurred_at"])
    for case_index, case in enumerate(cases):
        base = [_display(case.get(key), f"#/cases/{case_index}/{key}")
                for key in ("id", "kind", "field_name", "owner", "status", "version", "evidence")]
        events = case.get("events", [])
        if not events:
            history.append(base + ["null"] * 8)
        for event_index, event in enumerate(events):
            history.append(base + [_display(event.get(key), f"#/cases/{case_index}/events/{event_index}/{key}")
                                   for key in ("id", "action", "actor", "reason", "payload", "from_status", "to_status", "occurred_at")])

    ack_sheet = book.create_sheet("Acknowledgements")
    ack_keys = ("id", "association_id", "request_id", "previous_id", "case_version", "actor", "reason", "created_at")
    ack_sheet.append(list(ack_keys))
    for index, acknowledgement in enumerate(acknowledgements):
        ack_sheet.append([_display(acknowledgement.get(key), f"#/acknowledgements/{index}/{key}") for key in ack_keys])

    assessment_sheet = book.create_sheet("Assessment")
    target_keys = ("ref", "clinician_ref", "evaluation_ref", "source", "network_id", "network_label",
                   "classification", "reason", "value", "comparison_value", "receipt_id", "attempt_id", "locator", "address_path")
    assessment_sheet.append(list(target_keys))
    for index, target in enumerate(targets):
        assessment_sheet.append([_display(target.get(key), f"#/confirmation/assessment/targets/{index}/{key}") for key in target_keys])

    payload = book.create_sheet("Payload")
    payload.append(["part", "json_chunk"])
    for part, start in enumerate(range(0, len(encoded), JSON_CHUNK_SIZE), 1):
        payload.append([str(part), encoded[start:start + JSON_CHUNK_SIZE]])

    for sheet in book:
        sheet.freeze_panes = "A2"
        sheet.auto_filter.ref = sheet.dimensions
        for row in sheet:
            for cell in row:
                if cell.value is not None:
                    cell.data_type = "s"
                    cell.number_format = "@"
        sheet.column_dimensions["A"].width = 30
        sheet.column_dimensions["B"].width = 60
    output = io.BytesIO()
    try:
        book.save(output)
        return output.getvalue()
    finally:
        book.close()
