"""Tests for promoted healthcare domain signals and enriched workbench read models."""
from __future__ import annotations

from provider_directory_truth_layer.domain_signals import (
    build_four_gate_evidence,
    classify_phone_conflict,
    classify_regulatory_regimes,
    is_hospital_based_taxonomy,
)


def test_hospital_based_and_regime_classification():
    assert is_hospital_based_taxonomy("207P00000X · Emergency Medicine") is True
    assert is_hospital_based_taxonomy("2085R0202X Diagnostic Radiology") is True
    assert is_hospital_based_taxonomy("207Q00000X Family Medicine") is False

    regimes = classify_regulatory_regimes(["Volunteer Commercial PPO", "MidSouth Medicare Advantage"])
    assert [r["regime"] for r in regimes] == ["commercial_nsa", "medicare_advantage"]
    medicaid = classify_regulatory_regimes(["TennCare Community Plan"])
    assert medicaid[0]["regime"] == "medicaid_mco"


def test_phone_conflict_classification():
    assert classify_phone_conflict("(615) 555-0101", "6155550101")["category"] == "exact_match"
    assert classify_phone_conflict("800-555-0199", "6155550142")["category"] == "toll_free_centralized_line"
    assert classify_phone_conflict("6155550101", "6155550142")["category"] == "same_npa_nxx_clinic_pbx"
    assert classify_phone_conflict("6153220101", "6158850142")["category"] == "same_area_code_different_exchange"
    assert classify_phone_conflict("6155550101", "2705550142")["category"] == "different_area_code_or_state"


def test_four_gate_evidence_never_promotes_self_reported_licensure():
    unverified_match = build_four_gate_evidence(
        npi="1990001012",
        npi_luhn_valid=True,
        practice_state="TN",
        license_state="TN",
        psv_status=None,
    )
    assert unverified_match["gate1_identity"]["status"] == "active_npi"
    assert unverified_match["gate2_licensure"]["status"] == "self_reported_state_match_unverified_psv"
    assert unverified_match["gate2_licensure"]["psv_required"] is True

    out_of_state = build_four_gate_evidence(
        npi="1990001012",
        npi_luhn_valid=True,
        practice_state="TN",
        license_state="KY",
        psv_status=None,
    )
    assert out_of_state["gate2_licensure"]["status"] == "out_of_state_license_only_unverified_psv"
    assert out_of_state["gate2_licensure"]["psv_required"] is True

    verified = build_four_gate_evidence(
        npi="1990001012",
        npi_luhn_valid=True,
        practice_state="TN",
        license_state="TN",
        psv_status="psv_verified_active",
        pecos_status="pecos_ffs_enrolled",
    )
    assert verified["gate2_licensure"]["status"] == "primary_source_verified"
    assert verified["gate2_licensure"]["psv_required"] is False
    assert verified["gate3_enrollment"]["status"] == "pecos_ffs_enrolled"


def test_seeded_workbench_routes_expose_domain_signals(tmp_path):
    from fastapi.testclient import TestClient
    from provider_directory_truth_layer.demo_tennessee import seed_tennessee_demo
    from provider_directory_truth_layer.intake_api import create_workbench
    from provider_directory_truth_layer.intake_store import IntakeStore

    db_path = tmp_path / "workbench.sqlite3"
    store = IntakeStore(db_path, tmp_path)
    seed_tennessee_demo(store)

    client = TestClient(create_workbench(db_path, tmp_path))

    dir_resp = client.get("/api/workbench/directory")
    assert dir_resp.status_code == 200
    dir_items = dir_resp.json()["items"]
    assert len(dir_items) >= 15
    first_dir = dir_items[0]
    assert first_dir["regulatory_regimes"]
    assert first_dir["four_gate_evidence"]["gate2_licensure"]["psv_required"] is True
    assert first_dir["licensure_psv_status"] == "self_reported_state_match_unverified_psv"

    work_resp = client.get("/api/workbench/work")
    assert work_resp.status_code == 200
    work_items = work_resp.json()["items"]
    phone_cases = [c for c in work_items if c.get("field_name") == "phone"]
    assert phone_cases
    assert phone_cases[0]["phone_conflict"]["category"] == "same_npa_nxx_clinic_pbx"
    assert phone_cases[0]["four_gate_evidence"]["gate2_licensure"]["psv_required"] is True

    case_id = phone_cases[0]["id"]
    detail_resp = client.get(f"/api/work/{case_id}")
    assert detail_resp.status_code == 200
    detail = detail_resp.json()
    assert detail["phone_conflict"]["category"] == "same_npa_nxx_clinic_pbx"
    assert detail["regulatory_regime"]["regime"]

    phone_resp = client.get("/api/workbench/phone-reviews")
    assert phone_resp.status_code == 200
    disagreements = [s for s in phone_resp.json()["items"] if not s["sources_agree"]]
    assert any(s.get("phone_conflict") for s in disagreements)
