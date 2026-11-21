"""Structured, locally asserted contact evidence; recording sends no communication."""
from datetime import datetime

from .normalize import normalize_phone

METHODS = {"phone", "email", "portal", "other"}
OUTCOMES = {"no_answer", "message_left", "response_received", "unable_to_contact"}


def validate_outreach(payload):
    def text(key, required=False):
        value = payload.get(key, "")
        if not isinstance(value, str) or (required and not value.strip()):
            raise ValueError(f"{key} must be nonblank text" if required else f"{key} must be text")
        return value.strip()
    for key in ("owner", "follow_up", "proposal", "observed", "submission_reference", "verification_note"):
        if key in payload:
            raise ValueError("Outreach cannot change assignment, scheduling or correction fields")
    contact_at = text("contact_at", True)
    try:
        parsed = datetime.fromisoformat(contact_at.replace("Z", "+00:00"))
        if "T" not in contact_at or parsed.tzinfo is None or parsed.utcoffset() is None:
            raise ValueError
    except ValueError as error:
        raise ValueError("contact_at must be an ISO timestamp with timezone") from error
    method, outcome = text("method", True), text("outcome", True)
    if method not in METHODS or outcome not in OUTCOMES:
        raise ValueError("Unsupported outreach method or outcome")
    result = {"contact_at": contact_at, "method": method, "outcome": outcome}
    for key in ("contact_target", "respondent_role", "response_summary", "reported_phone"):
        value = text(key, key == "response_summary" and outcome == "response_received")
        if value:
            result[key] = value
    phone = result.get("reported_phone")
    if phone and (outcome != "response_received" or len(normalize_phone(phone)) != 10):
        raise ValueError("reported_phone requires a response_received outcome and ten digits")
    return {key: payload[key] for key in ("actor", "reason", "action", "expected_version")} | result
