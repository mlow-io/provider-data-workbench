"""Idempotent Middle Tennessee synthetic showcase dataset for the operator workbench."""
from __future__ import annotations

import csv
import hashlib
import io
import json
from pathlib import Path
from typing import Any

from .intake_store import IntakeStore
from .managed_feed import ManagedFeed
from .onboarding_service import OnboardingService

SOURCE = "cumberland-clinic"
FEED_SCOPE = "weekly-tn-roster"

TN_CLINICS: list[dict[str, str]] = [
    {
        "code": "NASH-MAIN",
        "name": "Nashville Midtown Clinic",
        "address": "2100 West End Ave, Suite 400",
        "city": "Nashville",
        "state": "TN",
        "zip": "37203",
    },
    {
        "code": "FRNK-WEST",
        "name": "Franklin Cool Springs Clinic",
        "address": "1550 Mallory Ln, Suite 210",
        "city": "Franklin",
        "state": "TN",
        "zip": "37067",
    },
    {
        "code": "BRNT-PARK",
        "name": "Brentwood Maryland Farms",
        "address": "5120 Maryland Way, Suite 120",
        "city": "Brentwood",
        "state": "TN",
        "zip": "37027",
    },
    {
        "code": "MURF-EAST",
        "name": "Murfreesboro Medical Plaza",
        "address": "1725 Medical Center Pkwy, Suite 300",
        "city": "Murfreesboro",
        "state": "TN",
        "zip": "37129",
    },
    {
        "code": "HEND-LAKE",
        "name": "Hendersonville Indian Lake",
        "address": "300 Indian Lake Blvd, Suite 150",
        "city": "Hendersonville",
        "state": "TN",
        "zip": "37075",
    },
]

_CLINIC_BY_CODE = {c["code"]: c for c in TN_CLINICS}

# All NPIs pass CMS ISO 7812 Luhn check-digit validation and are strictly synthetic.
TN_LISTINGS: list[dict[str, str]] = [
    {
        "record_id": "CVMG-01",
        "npi": "1990001012",
        "provider_name": "Dr. Elena Morales, MD",
        "specialty": "207Q00000X · Family Medicine",
        "location_id": "NASH-MAIN",
        "phone": "6155550101",
        "reference_phone": "6155550142",
        "network_label": "Volunteer Commercial PPO; MidSouth Medicare Advantage",
        "Dir_Exclude_Flag": "N",
    },
    {
        "record_id": "CVMG-02",
        "npi": "1990001020",
        "provider_name": "Dr. Marcus Vance, DO",
        "specialty": "207R00000X · Internal Medicine",
        "location_id": "FRNK-WEST",
        "phone": "6155550102",
        "reference_phone": "6155550188",
        "network_label": "Volunteer Commercial PPO",
        "Dir_Exclude_Flag": "N",
    },
    {
        "record_id": "CVMG-03",
        "npi": "1990001038",
        "provider_name": "Dr. Samuel Okafor, MD",
        "specialty": "207RC0000X · Cardiovascular Disease",
        "location_id": "BRNT-PARK",
        "phone": "6155550103",
        "reference_phone": "6155550139",
        "network_label": "Volunteer Commercial PPO; MidSouth Medicare Advantage",
        "Dir_Exclude_Flag": "N",
    },
    {
        "record_id": "CVMG-04",
        "npi": "1990001046",
        "provider_name": "Dr. Hannah Brooks, MD",
        "specialty": "208000000X · Pediatrics",
        "location_id": "MURF-EAST",
        "phone": "6155550104",
        "reference_phone": "6155550144",
        "network_label": "Volunteer Commercial PPO",
        "Dir_Exclude_Flag": "N",
    },
    {
        "record_id": "CVMG-05",
        "npi": "1990001053",
        "provider_name": "Dr. David Chen, MD",
        "specialty": "207X00000X · Orthopedic Surgery",
        "location_id": "HEND-LAKE",
        "phone": "6155550105",
        "reference_phone": "",
        "network_label": "MidSouth Medicare Advantage",
        "Dir_Exclude_Flag": "N",
    },
    {
        "record_id": "CVMG-06",
        "npi": "1990001061",
        "provider_name": "Dr. Rachel Alvarez, MD",
        "specialty": "207V00000X · Obstetrics & Gynecology",
        "location_id": "NASH-MAIN",
        "phone": "6155550106",
        "reference_phone": "",
        "network_label": "Volunteer Commercial PPO",
        "Dir_Exclude_Flag": "Y",
    },
    {
        "record_id": "CVMG-07",
        "npi": "1990001038",
        "provider_name": "Dr. Samuel Okafor, MD",
        "specialty": "207RC0000X · Cardiovascular Disease",
        "location_id": "NASH-MAIN",
        "phone": "6155550101",
        "reference_phone": "6155550101",
        "network_label": "Volunteer Commercial PPO; MidSouth Medicare Advantage",
        "Dir_Exclude_Flag": "N",
    },
    {
        "record_id": "CVMG-08",
        "npi": "1990001079",
        "provider_name": "Dr. Priya Nair, MD",
        "specialty": "207R00000X · Internal Medicine",
        "location_id": "FRNK-WEST",
        "phone": "6155550107",
        "reference_phone": "6155550107",
        "network_label": "Volunteer Commercial PPO",
        "Dir_Exclude_Flag": "N",
    },
    {
        "record_id": "CVMG-09",
        "npi": "1990001079",
        "provider_name": "Dr. Priya Nair, MD",
        "specialty": "207R00000X · Internal Medicine",
        "location_id": "BRNT-PARK",
        "phone": "6155550103",
        "reference_phone": "6155550103",
        "network_label": "Volunteer Commercial PPO",
        "Dir_Exclude_Flag": "N",
    },
    {
        "record_id": "CVMG-10",
        "npi": "1990001087",
        "provider_name": "Dr. Caleb Wright, MD",
        "specialty": "207Q00000X · Family Medicine",
        "location_id": "MURF-EAST",
        "phone": "6155550108",
        "reference_phone": "6155550108",
        "network_label": "MidSouth Medicare Advantage",
        "Dir_Exclude_Flag": "N",
    },
    {
        "record_id": "CVMG-11",
        "npi": "1990001095",
        "provider_name": "Naomi Foster, APRN",
        "specialty": "363LF0000X · Family Nurse Practitioner",
        "location_id": "HEND-LAKE",
        "phone": "6155550109",
        "reference_phone": "6155550109",
        "network_label": "Volunteer Commercial PPO; MidSouth Medicare Advantage",
        "Dir_Exclude_Flag": "N",
    },
    {
        "record_id": "CVMG-12",
        "npi": "1990001103",
        "provider_name": "Dr. Jordan Patel, MD",
        "specialty": "207RC0000X · Cardiovascular Disease",
        "location_id": "NASH-MAIN",
        "phone": "6155550110",
        "reference_phone": "6155550110",
        "network_label": "MidSouth Medicare Advantage",
        "Dir_Exclude_Flag": "N",
    },
    {
        "record_id": "CVMG-13",
        "npi": "1990001111",
        "provider_name": "Tessa Gallagher, PA-C",
        "specialty": "363A00000X · Physician Assistant",
        "location_id": "MURF-EAST",
        "phone": "6155550111",
        "reference_phone": "6155550111",
        "network_label": "Volunteer Commercial PPO",
        "Dir_Exclude_Flag": "N",
    },
    {
        "record_id": "CVMG-14",
        "npi": "1990001111",
        "provider_name": "Tessa Gallagher, PA-C",
        "specialty": "363A00000X · Physician Assistant",
        "location_id": "FRNK-WEST",
        "phone": "6155550114",
        "reference_phone": "6155550114",
        "network_label": "Volunteer Commercial PPO",
        "Dir_Exclude_Flag": "N",
    },
    {
        "record_id": "CVMG-15",
        "npi": "1990001129",
        "provider_name": "Dr. Owen Reynolds, MD",
        "specialty": "207X00000X · Orthopedic Surgery",
        "location_id": "BRNT-PARK",
        "phone": "6155550112",
        "reference_phone": "6155550112",
        "network_label": "Volunteer Commercial PPO; MidSouth Medicare Advantage",
        "Dir_Exclude_Flag": "N",
    },
]

ROSTER_HEADERS = [
    "record_id",
    "npi",
    "provider_name",
    "specialty",
    "location_id",
    "location_name",
    "address",
    "city",
    "state",
    "zip",
    "phone",
    "reference_phone",
    "network_label",
    "Dir_Exclude_Flag",
    "source_updated_at",
]


def _csv_bytes(rows: list[dict[str, str]]) -> bytes:
    buf = io.StringIO(newline="")
    writer = csv.DictWriter(buf, fieldnames=ROSTER_HEADERS)
    writer.writeheader()
    writer.writerows(rows)
    return buf.getvalue().encode("utf-8")


def _build_rows(as_of: str, *, include_franklin: bool = True, update_morales: bool = False, include_bad: bool = False) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for item in TN_LISTINGS:
        if not include_franklin and item["location_id"] == "FRNK-WEST":
            continue
        clinic = _CLINIC_BY_CODE[item["location_id"]]
        phone = "6155550142" if (update_morales and item["record_id"] == "CVMG-01") else item["phone"]
        rows.append(
            {
                "record_id": item["record_id"],
                "npi": item["npi"],
                "provider_name": item["provider_name"],
                "specialty": item["specialty"],
                "location_id": item["location_id"],
                "location_name": clinic["name"],
                "address": clinic["address"],
                "city": clinic["city"],
                "state": clinic["state"],
                "zip": clinic["zip"],
                "phone": phone,
                "reference_phone": item["reference_phone"],
                "network_label": item["network_label"],
                "Dir_Exclude_Flag": item["Dir_Exclude_Flag"],
                "source_updated_at": as_of,
            }
        )
    if include_bad:
        rows.append(
            {
                "record_id": "CVMG-ERR-99",
                "npi": "199000199",
                "provider_name": "Dr. Malformed Roster Entry",
                "specialty": "207Q00000X · Family Medicine",
                "location_id": "NASH-MAIN",
                "location_name": "Nashville Midtown Clinic",
                "address": "2100 West End Ave, Suite 400",
                "city": "Nashville",
                "state": "TN",
                "zip": "37203",
                "phone": "615-55",
                "reference_phone": "",
                "network_label": "Volunteer Commercial PPO",
                "Dir_Exclude_Flag": "N",
                "source_updated_at": as_of,
            }
        )
    return rows


def seed_tennessee_demo(store: IntakeStore, schema_catalog: Any = None) -> dict[str, Any]:
    """Seed an idempotent, synthetic Middle Tennessee Cumberland Valley Medical Group showcase."""
    existing_orgs = store.catalog().get("organizations", [])
    if any(org.get("label") == "Cumberland Valley Medical Group" for org in existing_orgs):
        return {"seeded": False, "reason": "already_present"}

    actor_meta = {"actor": "TN Demo Seed", "reason": "Initialize synthetic Middle Tennessee showcase"}
    group_org = store.create_catalog(
        "organizations",
        {
            "label": "Cumberland Valley Medical Group",
            "kind": "group",
            "identifiers": [{"namespace": "tn_group", "value": "CVMG-TN"}],
            **actor_meta,
        },
    )
    payer_org = store.create_catalog(
        "organizations",
        {
            "label": "Volunteer Health Plan",
            "kind": "payer",
            "identifiers": [{"namespace": "payer", "value": "VOLUNTEER"}],
            **actor_meta,
        },
    )
    store.create_catalog(
        "networks",
        {
            "label": "Volunteer Commercial PPO",
            "payer_organization_id": payer_org["id"],
            "identifiers": [{"namespace": "network", "value": "VOL-PPO"}],
            **actor_meta,
        },
    )
    store.create_catalog(
        "networks",
        {
            "label": "MidSouth Medicare Advantage",
            "payer_organization_id": payer_org["id"],
            "identifiers": [{"namespace": "network", "value": "MS-MA"}],
            **actor_meta,
        },
    )
    location_ids: dict[str, str] = {}
    for clinic in TN_CLINICS:
        location_ids[clinic["zip"]] = store.create_catalog(
            "locations",
            {"label": clinic["name"], "organization_id": group_org["id"], **actor_meta},
        )["id"]

    baseline_csv = _csv_bytes(_build_rows("2026-11-02"))
    candidate_csv = _csv_bytes(_build_rows("2026-11-16", include_franklin=False, update_morales=True, include_bad=True))

    # 1. Seed approved normalization recipe in host OnboardingService
    seed_receipt = store.receive(
        baseline_csv,
        "cumberland-roster-2026-11-02.csv",
        source=SOURCE,
        designation="synthetic",
        metadata={"scope": FEED_SCOPE},
    )
    recipe_mapping = {
        k: k
        for k in (
            "record_id",
            "npi",
            "provider_name",
            "specialty",
            "location_id",
            "address",
            "city",
            "state",
            "zip",
            "phone",
            "reference_phone",
            "source_updated_at",
        )
    }
    onboarding = OnboardingService(store)
    proposed_recipe = onboarding.propose(
        seed_receipt["id"],
        {
            "name": "Cumberland EHR Monthly Roster",
            "expected_attempt": seed_receipt["attempt_id"],
            "definition": {
                "version": 1,
                "mapping": recipe_mapping,
                "required": ["record_id", "npi", "provider_name", "address", "city", "state", "zip", "phone", "location_id"],
                "transforms": {"phone": ["phone_us"], "reference_phone": ["phone_us"]},
            },
            "actor": "Operations Lead",
            "reason": "Reviewed Cumberland EHR clinic roster column contract",
        },
    )
    approved_recipe = onboarding.approve(
        seed_receipt["id"],
        proposed_recipe["id"],
        {
            "expected_attempt": seed_receipt["attempt_id"],
            "actor": "Operations Lead",
            "reason": "Approved baseline EHR roster recipe",
        },
    )

    # 2. Seed managed recurring feed: v1 Approved Baseline + v2 Held Partial Candidate
    inbox = store.root / "tennessee-feed-inbox"
    inbox.mkdir(parents=True, exist_ok=True)
    feeds = ManagedFeed(store)
    feed = feeds.register(
        {
            "name": "Cumberland Valley Monthly Roster",
            "source": SOURCE,
            "scope": FEED_SCOPE,
            "owner": "M. Brooks (TN Ops)",
            "inbox": str(inbox),
            "start_date": "2026-11-02",
            "actor": "Operations Lead",
            "reason": "Track monthly Cumberland clinic deliveries with quality holds",
        }
    )
    contract = feeds.propose_contract(
        feed["id"],
        {
            "definition": {
                "recipe_revision_id": approved_recipe["id"],
                "required_headers": ROSTER_HEADERS,
                "encoding": "utf-8-sig",
                "delimiter": ",",
                "row_change_fraction": 0.15,
            },
            "actor": "Operations Lead",
            "reason": "Pin required Cumberland roster headers and 15% drift gate",
        },
    )
    approved_contract = feeds.approve_contract(
        feed["id"],
        contract["id"],
        {"actor": "Operations Lead", "reason": "Approve Cumberland recurring contract"},
    )
    feeds.configure(
        feed["id"],
        {
            "expected_revision": feed["revision"],
            "config": {"enabled": True, "contract_id": approved_contract["id"]},
            "actor": "Operations Lead",
            "reason": "Enable Cumberland managed delivery intake",
        },
    )

    def _drop(filename: str, payload: bytes, delivery_id: str, period: str) -> None:
        (inbox / filename).write_bytes(payload)
        manifest = {
            "delivery_id": delivery_id,
            "period": period,
            "as_of": period,
            "snapshot": "full",
            "filename": filename,
            "sha256": hashlib.sha256(payload).hexdigest(),
        }
        (inbox / f"{delivery_id}.manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")

    _drop("cumberland-2026-11-02.csv", baseline_csv, "cumberland-2026-11-02", "2026-11-02")
    v1_run = feeds.run_once(feed["id"], at="2026-11-02T14:00:00+00:00")
    v1_id = v1_run["version_id"]
    v1_detail = feeds.version(v1_id)
    feeds.decide(
        v1_id,
        {
            "decision": "approved",
            "actor": "Operations Lead",
            "reason": "All 15 baseline Cumberland listings verified across 5 Middle TN clinics",
            "idempotency_key": f"seed-approve-{v1_id}",
            "expected_report": v1_detail["report_hash"],
            "expected_current": None,
        },
    )

    _drop("cumberland-2026-11-16.csv", candidate_csv, "cumberland-2026-11-16", "2026-11-16")
    v2_run = feeds.run_once(feed["id"], at="2026-11-16T14:00:00+00:00")
    v2_id = v2_run["version_id"]

    # 3. Shape realistic work queue states from committed v1 observations
    work_items = store.work()["items"]
    with store.db() as conn:
        ev_by_id = {
            r["id"]: json.loads(r["evidence"])
            for r in conn.execute("SELECT id, evidence FROM work_case")
        }

    for item in work_items:
        record_id = (ev_by_id.get(item["id"], {}).get("normalized") or {}).get("record_id")
        cid = item["id"]
        ver = item["version"]
        if record_id == "CVMG-01":
            # Keep urgent high-risk phone discrepancy in `new` for immediate operator triage
            continue
        if record_id == "CVMG-02":
            c = store.event(cid, {"action": "assign", "actor": "M. Brooks", "reason": "Assign Cool Springs clinic outreach", "owner": "M. Brooks", "follow_up": "2026-11-24", "expected_version": ver})
            c = store.event(cid, {"action": "outreach", "actor": "M. Brooks", "reason": "Called Franklin front desk; line went to voicemail", "contact_at": "2026-11-18T15:30:00+00:00", "method": "phone", "outcome": "no_answer", "contact_target": "Franklin Cool Springs Desk", "expected_version": c["version"]})
            store.event(cid, {"action": "triage", "actor": "M. Brooks", "reason": "Confirmed phone mismatch against EHR listing; awaiting callback", "expected_version": c["version"]})
        elif record_id == "CVMG-03":
            c = store.event(cid, {"action": "assign", "actor": "M. Brooks", "reason": "Assign Brentwood cardiology verification", "owner": "M. Brooks", "expected_version": ver})
            c = store.event(cid, {"action": "outreach", "actor": "M. Brooks", "reason": "Practice manager confirmed updated scheduling line", "contact_at": "2026-11-10T16:15:00+00:00", "method": "phone", "outcome": "response_received", "contact_target": "Brentwood Practice Manager", "respondent_role": "Office Manager", "response_summary": "Confirmed (615) 555-0139 is the live cardiology scheduling line", "reported_phone": "6155550139", "expected_version": c["version"]})
            c = store.event(cid, {"action": "triage", "actor": "M. Brooks", "reason": "Evidence complete from office manager", "expected_version": c["version"]})
            c = store.event(cid, {"action": "approve", "actor": "Operations Lead", "reason": "Approve verified Brentwood phone correction", "proposal": "6155550139", "expected_version": c["version"]})
            c = store.event(cid, {"action": "submit", "actor": "Operations Lead", "reason": "Submitted to Volunteer PPO roster portal", "submission_reference": "VOL-2026-1111-BRNT", "expected_version": c["version"]})
            store.event(cid, {"action": "verify", "actor": "Operations Lead", "reason": "Observed updated phone in payer directory extract", "observed": "6155550139", "verification_note": "Verified on 2026-11-14 payer directory pull", "expected_version": c["version"]})
        elif record_id == "CVMG-04":
            c = store.event(cid, {"action": "assign", "actor": "M. Brooks", "reason": "Assign Murfreesboro pediatrics correction", "owner": "M. Brooks", "expected_version": ver})
            c = store.event(cid, {"action": "triage", "actor": "M. Brooks", "reason": "Validated direct line against clinic voicemail", "expected_version": c["version"]})
            c = store.event(cid, {"action": "approve", "actor": "Operations Lead", "reason": "Approve Murfreesboro phone update", "proposal": "6155550144", "expected_version": c["version"]})
            store.event(cid, {"action": "submit", "actor": "Operations Lead", "reason": "Submitted under NSA 2-day SLA window", "submission_reference": "VOL-2026-1119-MURF", "expected_version": c["version"]})
        elif record_id == "CVMG-05":
            store.event(cid, {"action": "needs_information", "actor": "M. Brooks", "reason": "NPPES shows Suite 155 while clinic EHR lists Suite 150; requested lease confirmation", "expected_version": ver})
        elif record_id == "CVMG-06":
            # Keep open in `new` so Dir_Exclude_Flag suppression review is visible
            continue
        elif item["kind"] == "qa" and item["status"] == "new":
            store.event(cid, {"action": "resolve", "actor": "Baseline QA", "reason": "Clean baseline clinician-location verified against NPPES", "expected_version": ver})

    # 4. Seed one reviewed schema variant in provider-network-intake CatalogStore
    if schema_catalog is not None:
        from provider_network_intake import Engine, SourceContext, Variant

        engine = Engine()
        ctx = SourceContext(source=SOURCE, delivery_id="cumberland-2026-11-02", payer="volunteer-ppo", source_version="2026-q4")
        insp = engine.inspect(baseline_csv, context=ctx)
        if engine.recognize(insp, catalog=schema_catalog.snapshot(SOURCE)).status == "unknown":
            schema_catalog.observe(insp)
            note_key = "cumberland-ehr-guide-2026q4"
            note_text = "Cumberland EHR export guide 2026-q4: Dir_Exclude_Flag=Y suppresses public directory visibility without ending network participation."
            variant = Variant.from_dict(
                {
                    "version": 1,
                    "source": SOURCE,
                    "payer": "volunteer-ppo",
                    "source_version": "2026-q4",
                    "contract": "payer-network-roster/1",
                    "grain": "practitioner_office",
                    "headers": ROSTER_HEADERS,
                    "mapping": {
                        "record_id": "record_id",
                        "practitioner_npi": "npi",
                        "provider_name": "provider_name",
                        "specialty": "specialty",
                        "location_id": "location_id",
                        "address": "address",
                        "city": "city",
                        "state": "state",
                        "zip": "zip",
                        "phone": "phone",
                        "directory_visible": "Dir_Exclude_Flag",
                        "source_updated_at": "source_updated_at",
                    },
                    "transforms": {
                        "phone": ["phone_us"],
                        "zip": ["zip_us"],
                        "state": ["state_us"],
                        "directory_visible": [{"op": "value_map", "values": {"Y": False, "N": True}}],
                        "source_updated_at": [{"op": "date", "format": "%Y-%m-%d"}],
                    },
                    "ignored_fields": ["location_name", "reference_phone", "network_label"],
                    "evidence_refs": [note_key],
                    "source_notes": {note_key: note_text},
                }
            )
            snapshot = schema_catalog.snapshot()
            prop = schema_catalog.propose(
                insp,
                variant,
                origin="manual",
                request_id="seed-cumberland-ehr-variant",
                expected_revision=snapshot.revision,
            )
            schema_catalog.review(
                prop["id"],
                actor="Operations Lead",
                reason="Confirmed Cumberland EHR inverted directory-exclusion flag semantics",
                expected_revision=snapshot.revision,
            )

    phone_review = _seed_phone_review(store, v1_detail["manifest"], location_ids)

    return {
        "seeded": True,
        "feed_id": feed["id"],
        "approved_version": v1_id,
        "held_version": v2_id,
        "phone_review": phone_review,
    }


# Payer directory assertions for the two offices Dr. Okafor shares with the clinic roster.
PAYER_DIRECTORY_SOURCE = "volunteer-directory"
PAYER_DIRECTORY_RECORDS: list[dict[str, str]] = [
    {"record_id": "VHP-BRNT-PARK", "location_id": "BRNT-PARK", "phone": "6155550139"},
    {"record_id": "VHP-NASH-MAIN", "location_id": "NASH-MAIN", "phone": "6155550101"},
]
OKAFOR_NPI = "1990001038"
OKAFOR_NAME = "Dr. Samuel Okafor, MD"


def _seed_phone_review(store: IntakeStore, roster_manifest: dict[str, Any], location_ids: dict[str, str]) -> dict[str, Any]:
    """Prepare reviewed identity links so an operator can choose an office phone.

    The seed approves clinician and office links only. The phone choice itself,
    candidate creation and dataset approval stay operator actions in the UI.
    """
    import uuid

    from .identity_review import IdentityReview
    from .reconciliation_store import ReconciliationStore

    records = []
    for item in PAYER_DIRECTORY_RECORDS:
        clinic = _CLINIC_BY_CODE[item["location_id"]]
        records.append(
            {
                "record_id": item["record_id"],
                "npi": OKAFOR_NPI,
                "provider_name": OKAFOR_NAME,
                "entity_type": "clinician",
                "address": clinic["address"],
                "city": clinic["city"],
                "state": clinic["state"],
                "zip": clinic["zip"],
                "phone": item["phone"],
                "location_id": item["location_id"],
            }
        )
    reference = store.receive(
        json.dumps(records, indent=2).encode(),
        "volunteer-directory-extract-2026-11-14.json",
        source=PAYER_DIRECTORY_SOURCE,
        designation="synthetic",
    )
    comparison = ReconciliationStore(store)
    run = comparison.create_run(
        {
            "inputs": [
                {"receipt_id": roster_manifest["receipt_id"], "attempt_id": roster_manifest["attempt_id"], "entity_kind": "clinician"},
                {"receipt_id": reference["id"], "attempt_id": reference["attempt_id"], "entity_kind": "clinician"},
            ],
            "actor": "Operations Lead",
            "reason": "Compare approved clinic roster with Volunteer payer directory extract",
        }
    )
    review = IdentityReview(store)

    def approve(candidate: dict[str, Any], reason: str, **target: str) -> str:
        context = review.inspect(run["id"], candidate["id"])
        decision = review.decide(
            {
                "run_id": run["id"],
                "candidate_id": candidate["id"],
                "decision": "approve",
                "request_id": uuid.uuid4().hex,
                "expected_snapshot": context["review_snapshot"],
                "expected_revisions": {ref: link["id"] if link else None for ref, link in context["current_links"].items()},
                "expected_decision": context["latest_decision"]["id"] if context["latest_decision"] else None,
                "actor": "Operations Lead",
                "reason": reason,
                **target,
            }
        )
        return decision["decision"]["target_id"]

    def same_office(candidate: dict[str, Any]) -> bool:
        left, right = candidate["left_record"]["comparison"], candidate["right_record"]["comparison"]
        return left["npi"] == right["npi"] == OKAFOR_NPI and left["address"]["line1"] == right["address"]["line1"]

    # Link only same-office pairs; a shared NPI alone never selects an office.
    clinician_id = None
    for candidate in comparison.candidates(run["id"], kind="clinician", eligible=True, limit=100)["items"]:
        if same_office(candidate):
            target = {"target_id": clinician_id} if clinician_id else {"new_label": OKAFOR_NAME}
            clinician_id = approve(candidate, "Same NPI, name and office address in both sources", **target)
    # Office links target the existing catalog locations rather than new duplicates.
    linked: list[str] = []
    for candidate in comparison.candidates(run["id"], kind="location", eligible=True, limit=100)["items"]:
        if same_office(candidate):
            target_id = location_ids[candidate["left_record"]["comparison"]["address"]["zip_base"]]
            linked.append(approve(candidate, "Same street address and suite in both sources", target_id=target_id))
    return {"run_id": run["id"], "clinician_id": clinician_id, "location_ids": sorted(set(linked)), "reference_receipt": reference["id"]}
