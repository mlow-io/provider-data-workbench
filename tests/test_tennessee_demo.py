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
