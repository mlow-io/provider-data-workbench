"""Verify Middle Tennessee synthetic showcase seeding, workbench endpoints, and schema catalog mount."""
from __future__ import annotations

from fastapi.testclient import TestClient

from provider_directory_truth_layer.demo_tennessee import seed_tennessee_demo
from provider_directory_truth_layer.intake_api import create_workbench
from provider_directory_truth_layer.intake_store import IntakeStore


def test_tennessee_seed_populates_overview_directory_and_schema_catalog(tmp_path):
    db_path = tmp_path / "directory.sqlite3"
    store = IntakeStore(db_path, tmp_path)
    app = create_workbench(db_path, tmp_path, demo=True)
    catalog_store = getattr(app.state, "source_catalog_store", None)

    first = seed_tennessee_demo(store, catalog_store)
    assert first["seeded"] is True
    second = seed_tennessee_demo(store, catalog_store)
    assert second == {"seeded": False, "reason": "already_present"}

    client = TestClient(app)
    overview = client.get("/api/workbench/overview").json()
    assert overview["total_providers"] == 12
    assert overview["total_locations"] == 5
    assert overview["total_directory_listings"] == 15
    assert overview["open_discrepancies"] == 5
    assert overview["held_deliveries"] == 1
    assert overview["approved_feeds"] == 1
    assert overview["quarantined_rows"] == 1
    assert overview["mode"] == "live"

    directory = client.get("/api/workbench/directory").json()["items"]
    assert len(directory) == 15
    assert all(item["npi_luhn_valid"] is True for item in directory)
    morales = next(item for item in directory if item["npi"] == "1990001012")
    assert morales["location_code"] == "NASH-MAIN"
    assert morales["open_issues"] == 1
    assert morales["primary_case_id"] is not None
    alvarez = next(item for item in directory if item["npi"] == "1990001061")
    assert alvarez["directory_visible"] is False

    filtered = client.get("/api/workbench/directory", params={"location": "FRNK-WEST"}).json()["items"]
    assert len(filtered) == 3

    status = client.get("/api/schema-catalog/status").json()
    if catalog_store is not None:
        assert status["enabled"] is True
        assert status["catalog_revision"] >= 1
        assert len(status["variants"]) == 1
        assert status["variants"][0]["source"] == "cumberland-clinic"
        assert overview["schema_variants_count"] == 1

    feeds = client.get("/api/feeds").json()["items"]
    assert len(feeds) == 1
    assert len(feeds[0]["versions"]) == 2
    states = {v["state"] for v in feeds[0]["versions"]}
    assert states == {"approved", "candidate"}

    work_items = client.get("/api/workbench/work").json()["items"]
    assert len(work_items) == 15
    morales_case = next(
        item for item in work_items if item.get("npi") == "1990001012" and item["field_name"] == "phone"
    )
    assert morales_case["listing_value"] == "6155550101"
    assert morales_case["reference_value"] == "6155550142"
    assert morales_case["clinic_name"] == "Nashville Midtown Clinic"


def test_tennessee_phone_review_flow_creates_separately_approved_correction(tmp_path):
    import uuid

    db_path = tmp_path / "directory.sqlite3"
    app = create_workbench(db_path, tmp_path, demo=True)
    seeded = seed_tennessee_demo(IntakeStore(db_path, tmp_path), getattr(app.state, "source_catalog_store", None))
    client = TestClient(app)

    def scopes():
        return {item["location_label"]: item for item in client.get("/api/workbench/phone-reviews").json()["items"]}

    # Seed links two offices for one clinician and leaves the phone choice to the operator.
    reviews = scopes()
    assert set(reviews) == {"Brentwood Maryland Farms", "Nashville Midtown Clinic"}
    brentwood, nashville = reviews["Brentwood Maryland Farms"], reviews["Nashville Midtown Clinic"]
    assert brentwood["status"] == "unreviewed" and brentwood["decision"] is None
    assert brentwood["sources_agree"] is False and nashville["sources_agree"] is True
    roster = next(o for o in brentwood["options"] if o["from_approved_roster"])
    payer = next(o for o in brentwood["options"] if not o["from_approved_roster"])
    assert (roster["number"], payer["number"]) == ("6155550103", "6155550139")
    assert brentwood["base_version"] == seeded["approved_version"]

    decision = client.post("/api/reconciliation/field-decisions", json={
        "clinician_id": brentwood["clinician_id"], "location_id": brentwood["location_id"], "field": "phone",
        "decision": "select", "selected_ref": payer["ref"], "expected_snapshot": brentwood["snapshot"],
        "expected_decision": None, "request_id": uuid.uuid4().hex, "actor": "M. Brooks", "reason": "Payer directory matches office",
    })
    assert decision.status_code == 200
    brentwood = scopes()["Brentwood Maryland Farms"]
    assert brentwood["correction"]["status"] == "eligible"
    assert brentwood["correction"]["new_value"] == {"number": "6155550139", "extension": None}
    assert scopes()["Nashville Midtown Clinic"]["correction"]["status"] == "not_selected"

    created = client.post(f"/api/feed-versions/{seeded['approved_version']}/field-materialization", json={
        "clinician_id": brentwood["clinician_id"], "location_id": brentwood["location_id"], "snapshot": brentwood["snapshot"],
        "decision_id": brentwood["decision"]["id"], "actor": "M. Brooks", "reason": "Correct Brentwood phone", "idempotency_key": "tn-1",
    })
    assert created.status_code == 200
    candidate = created.json()
    assert candidate["kind"] == "derived_field_candidate" and candidate["state"] == "candidate"
    assert scopes()["Brentwood Maryland Farms"]["candidates"][0]["state"] == "candidate"
    assert client.get("/api/workbench/overview").json()["held_deliveries"] == 1
    feed = client.get("/api/feeds").json()["items"][0]
    assert feed["current_version"] == seeded["approved_version"]

    approved = client.post(f"/api/feed-versions/{candidate['id']}/decide", json={
        "decision": "approved", "expected_report": candidate["report_hash"], "expected_current": feed["current_version"],
        "idempotency_key": "tn-approve", "actor": "Operations Lead", "reason": "Approve reviewed correction",
    })
    assert approved.status_code == 200
    brentwood = scopes()["Brentwood Maryland Farms"]
    assert brentwood["candidates"][0]["state"] == "approved"
    assert brentwood["correction"]["status"] == "no_change"
    rows = client.get(f"/api/feed-versions/{candidate['id']}/export").json()["records"]
    corrected = [r for r in rows if r.get("materialization")]
    assert len(corrected) == 1 and corrected[0]["normalized"]["phone"] == "6155550139"
    assert corrected[0]["original"]["phone"] == "6155550103"
    okafor_nashville = next(r for r in rows if r["normalized"]["record_id"] == "CVMG-07")
    assert okafor_nashville["normalized"]["phone"] == "6155550101" and "materialization" not in okafor_nashville
