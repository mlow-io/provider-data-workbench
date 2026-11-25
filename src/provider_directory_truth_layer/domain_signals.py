"""Operational domain signal evaluators for Provider Data Workbench.

Integrates patterns validated across public Tennessee provider & payer reconciliations:
- 4-Gate Provider Truth Card (Identity -> Licensure PSV -> Enrollment/LEIE -> Directory/Panel)
- Regulatory regime classification (Commercial NSA vs. CMS MA vs. Medicaid MCO vs. Delegated Dental/Vision)
- Hospital-based accepting-new-patients (`newpt`) visibility leak detection
- Phone conflict root-cause classification (`toll_free_centralized_line` vs. `same_npa_nxx_clinic_pbx` vs. different exchange)
"""
from __future__ import annotations

import re
from typing import Any

try:
    from provider_network_intake.domain_rules import (
        assess_licensure_state_consistency as _intake_licensure,
        classify_phone_conflict as _intake_phone_conflict,
        classify_regulatory_regime as _intake_regime,
        is_hospital_based_taxonomy as _intake_hospital_based,
    )
except ImportError:  # pragma: no cover - self-contained fallback when intake pkg isn't installed
    _intake_licensure = None  # type: ignore[assignment]
    _intake_phone_conflict = None  # type: ignore[assignment]
    _intake_regime = None  # type: ignore[assignment]
    _intake_hospital_based = None  # type: ignore[assignment]

HOSPITAL_BASED_PREFIXES = ("2085R", "207L", "207P", "207Z", "208M", "367500")
HOSPITAL_BASED_KEYWORDS = (
    "radiology",
    "anesthesiology",
    "emergency medicine",
    "pathology",
    "hospitalist",
    "crna",
    "nurse anesthetist",
)
TOLL_FREE_PREFIXES = {"800", "888", "877", "866", "855", "844", "833"}
ACCEPTING_TOKENS = {"newpt", "accepting", "open", "true", "yes", "y", "accepting_new_patients", "accepting new patients"}


def is_hospital_based_taxonomy(specialty: str | None) -> bool:
    if _intake_hospital_based is not None:
        return bool(_intake_hospital_based(specialty))
    if not specialty:
        return False
    token = specialty.strip().split()[0].upper()
    if any(token.startswith(p) for p in HOSPITAL_BASED_PREFIXES):
        return True
    low = specialty.lower()
    return any(k in low for k in HOSPITAL_BASED_KEYWORDS)


def is_accepting_panel(panel_status: str | None) -> bool:
    if not panel_status:
        return True  # Default directory-visible listing without explicit panel closed flag
    tok = " ".join(str(panel_status).strip().lower().split())
    if tok in {"closed", "existptonly", "existing_only", "false", "no", "n", "not_accepting"}:
        return False
    return tok in ACCEPTING_TOKENS or True


def classify_regulatory_regime(network_or_source: str | None) -> dict[str, str]:
    if _intake_regime is not None:
        return dict(_intake_regime(network_or_source))
    text = (network_or_source or "").strip().lower()
    if any(k in text for k in ("tenncare", "medicaid", "community plan", "chip")):
        return {
            "regime": "medicaid_mco",
            "label": "Medicaid / TennCare MCO",
            "sla_note": "Governed by state Medicaid MCO network-adequacy & CMS Medicaid managed-care directory standards (separate from commercial NSA rules).",
        }
    if any(k in text for k in ("medicare advantage", "midsouth", "d-snp", "c-snp", "dual complete", "ma ", "ma-", "-ma")):
        return {
            "regime": "medicare_advantage",
            "label": "CMS Medicare Advantage",
            "sla_note": "Subject to CMS Medicare Advantage directory accuracy oversight and REAL Health Providers Act verification cadence.",
        }
    if any(k in text for k in ("dental", "vision", "fedvip", "optometry", "spectera", "healthplex")):
        return {
            "regime": "delegated_dental_vision",
            "label": "Delegated Dental / Vision",
            "sla_note": "Often routed through delegated dental/vision vendor hubs; check for multi-site corporate hub fan-out.",
        }
    if any(k in text for k in ("commercial", "ppo", "epo", "hmo", "erisa", "volunteer", "choice", "options")):
        return {
            "regime": "commercial_nsa",
            "label": "Commercial / NSA ERISA",
            "sla_note": "Subject to No Surprises Act >=90-day verification cycle and 2-business-day update window.",
        }
    return {
        "regime": "unclassified_regime",
        "label": "Unclassified Payer Regime",
        "sla_note": "Do not apply commercial No Surprises Act deadlines indiscriminately before confirming line of business.",
    }


def classify_regulatory_regimes(networks: list[str], source: str | None = None) -> list[dict[str, str]]:
    candidates = [n for n in networks if n] or ([source] if source else [])
    seen: set[str] = set()
    regimes: list[dict[str, str]] = []
    for item in candidates:
        r = classify_regulatory_regime(item)
        if r["regime"] not in seen:
            seen.add(r["regime"])
            regimes.append(r)
    return regimes or [classify_regulatory_regime(source)]


def _digits10(value: str | None) -> str | None:
    if not value:
        return None
    raw = re.sub(r"\D", "", str(value).split("x")[0].split("X")[0])
    if len(raw) == 11 and raw.startswith("1"):
        raw = raw[1:]
    return raw if len(raw) == 10 else None


def classify_phone_conflict(phone_a: str | None, phone_b: str | None) -> dict[str, str]:
    if _intake_phone_conflict is not None:
        return dict(_intake_phone_conflict(phone_a, phone_b))
    pa = _digits10(phone_a)
    pb = _digits10(phone_b)
    if not pa or not pb:
        return {
            "category": "missing_phone",
            "label": "Missing Phone Comparison",
            "guidance": "One or both sources lack a valid 10-digit US telephone number.",
        }
    if pa == pb:
        return {
            "category": "exact_match",
            "label": "Exact Match",
            "guidance": "Normalized 10-digit numbers agree.",
        }
    if pa[:3] in TOLL_FREE_PREFIXES or pb[:3] in TOLL_FREE_PREFIXES:
        return {
            "category": "toll_free_centralized_line",
            "label": "Toll-Free Centralized Desk",
            "guidance": "One source lists an 800/8xx call center instead of a local clinic desk; verify patient scheduling preference before overwriting.",
        }
    if pa[:6] == pb[:6]:
        return {
            "category": "same_npa_nxx_clinic_pbx",
            "label": "Same Clinic Prefix (NPA-NXX)",
            "guidance": "First 6 digits match, indicating another DID/extension on the same clinic/hospital PBX rather than an unrelated address.",
        }
    if pa[:3] == pb[:3]:
        return {
            "category": "same_area_code_different_exchange",
            "label": "Same Area Code (Different Exchange)",
            "guidance": "Same metro area code with different exchange; confirm whether clinic moved or uses an off-site scheduling hub.",
        }
    return {
        "category": "different_area_code_or_state",
        "label": "Different Area Code / State",
        "guidance": "Different area code or out-of-state number; high priority for stale billing-office or corporate hub routing check.",
    }


def _assess_licensure(practice_state: str | None, license_state: str | None, psv_verified: bool = False) -> dict[str, Any]:
    if _intake_licensure is not None:
        raw = _intake_licensure(practice_state, license_state, psv_verified=psv_verified)
        return {
            "status": raw["status"],
            "label": raw["label"],
            "psv_required": raw["psv_required"] == "true",
            "note": raw["note"],
        }
    prac = (practice_state or "").strip().upper()
    lic = (license_state or "").strip().upper()
    if psv_verified:
        return {
            "status": "primary_source_verified",
            "label": "Primary-Source Verified (TN Board)",
            "psv_required": False,
            "note": "Confirmed directly against state licensing board primary-source verification record.",
        }
    if lic and prac and lic != prac:
        return {
            "status": "out_of_state_license_only_unverified_psv",
            "label": f"Out-of-State License ({lic} Only — PSV Required)",
            "psv_required": True,
            "note": f"Self-reported {lic} license does not match {prac} practice site; verify compact privilege (e.g., eNLC) or active {prac} license via primary source.",
        }
    if lic:
        return {
            "status": "self_reported_state_match_unverified_psv",
            "label": f"Self-Reported {lic} License (PSV Required)",
            "psv_required": True,
            "note": "Self-reported NPPES/roster license matches clinic state, but never replaces primary-source board verification.",
        }
    return {
        "status": "no_license_state_recorded_unverified_psv",
        "label": "No License Recorded (PSV Required)",
        "psv_required": True,
        "note": "No license state recorded in intake/NPPES; manual primary-source verification required.",
    }


def build_four_gate_evidence(
    *,
    npi: str | None,
    npi_luhn_valid: bool,
    practice_state: str | None = None,
    license_state: str | None = None,
    psv_status: str | None = None,
    pecos_status: str | None = None,
    leie_status: str | None = "clear",
    address_confirmed: bool = True,
    hospital_based_newpt_leak: bool = False,
    claims_activity_note: str | None = None,
) -> dict[str, Any]:
    """Assemble the 4-Gate Provider Truth Card while strictly separating unverified gates."""
    gate1 = (
        {
            "status": "active_npi",
            "label": "Valid Luhn NPI" if npi else "NPI Unlinked",
            "source": "CMS ISO 7812 / NPPES",
        }
        if (npi and npi_luhn_valid)
        else {
            "status": "invalid_checksum" if npi else "unlinked",
            "label": "Invalid NPI Checksum" if npi else "Unlinked Identity",
            "source": "CMS ISO 7812",
        }
    )

    psv_verified = bool(psv_status and str(psv_status).strip().lower() in {"active", "primary_source_verified", "psv_verified_active", "verified"})
    gate2 = _assess_licensure(practice_state, license_state, psv_verified=psv_verified)

    pecos_norm = (pecos_status or "unverified").strip().lower()
    if pecos_norm in {"pecos_ffs_enrolled", "enrolled", "ffs"}:
        g3_status, g3_label = "pecos_ffs_enrolled", "PECOS FFS Enrolled"
        g3_note = "Individual or reassigned Medicare Part B FFS enrollment confirmed."
    elif pecos_norm in {"order_referring_only", "order_only"}:
        g3_status, g3_label = "order_referring_only", "Order & Referring Only"
        g3_note = "Order/Referring eligible (DME/HHA/Hospice) without full PECOS Part B billing enrollment."
    elif pecos_norm in {"not_in_medicare_ffs", "medicaid_or_dental_only"}:
        g3_status, g3_label = "not_in_medicare_ffs", "Not in Medicare PECOS"
        g3_note = "Zero Medicare enrollment; verify whether Medicaid/pediatric/dental/OB-GYN scope explains absence."
    else:
        g3_status, g3_label = "unverified", "PECOS Unchecked (Manual Check)"
        g3_note = "Exclusion screen clear; Medicare PECOS enrollment requires reconciliation."

    gate3 = {
        "status": g3_status,
        "leie_clear": (leie_status or "clear").lower() == "clear",
        "label": g3_label,
        "note": g3_note,
    }

    g4_parts = []
    if not address_confirmed:
        g4_parts.append("Address unconfirmed in NPD/NPPES")
    if hospital_based_newpt_leak:
        g4_parts.append("Hospital-based specialty marked accepting new patients")
    if claims_activity_note:
        g4_parts.append(claims_activity_note)
    gate4 = {
        "address_confirmed": bool(address_confirmed),
        "hospital_based_newpt_leak": bool(hospital_based_newpt_leak),
        "label": "; ".join(g4_parts) if g4_parts else "Confirmed Location & Panel",
        "note": claims_activity_note or ("Flagged for outpatient scheduling confirmation." if hospital_based_newpt_leak else "Directory location aligned with source assertions."),
    }
    return {
        "gate1_identity": gate1,
        "gate2_licensure": gate2,
        "gate3_enrollment": gate3,
        "gate4_directory": gate4,
    }
