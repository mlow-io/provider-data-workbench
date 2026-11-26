"""Read models and optional schema-catalog integration for the operator workbench UI."""
from __future__ import annotations

import json
import re
from datetime import date, datetime, timezone
from typing import Any

from .domain_signals import (
    build_four_gate_evidence,
    classify_phone_conflict,
    classify_regulatory_regime,
    classify_regulatory_regimes,
    is_accepting_panel,
    is_hospital_based_taxonomy,
)
from .managed_feed import ManagedFeed
from .normalize import normalize_phone


def _reported_panel(normalized: dict[str, Any], original: dict[str, Any]) -> bool | None:
    for record in (normalized, original):
        for key in ("panel_status", "accepting_new_patients"):
            if record.get(key) is not None:
                return is_accepting_panel(str(record[key]))
    return None


def is_valid_npi(value: str | None) -> bool:
    """Validate 10-digit NPI using CMS ISO 7812 Luhn check digit (80840 prefix)."""
    if not isinstance(value, str) or not re.fullmatch(r"\d{10}", value):
        return False
    try:
        from provider_network_intake import is_valid_npi as intake_luhn

        return bool(intake_luhn(value))
    except ImportError:
        digits = [int(ch) for ch in f"80840{value[:-1]}"]
        total = 0
        for idx, digit in enumerate(reversed(digits)):
            if idx % 2 == 0:
                digit *= 2
                if digit > 9:
                    digit -= 9
            total += digit
        return ((10 - (total % 10)) % 10) == int(value[-1])


def _location_code(raw_location: str | None, norm: dict[str, Any]) -> str:
    if norm.get("location_id"):
        return str(norm["location_id"])
    if raw_location and ":" in raw_location:
        return raw_location.split(":", 1)[1]
    return raw_location or "UNASSIGNED"


def _open_cases_index(store) -> tuple[list[dict[str, Any]], dict[tuple[str, str], list[str]], dict[str, list[str]]]:
    work = store.work()
    cases = work.get("items", [])
    by_provider_loc: dict[tuple[str, str], list[str]] = {}
    by_npi: dict[str, list[str]] = {}
    with store.db() as conn:
        evidence_rows = {
            row["id"]: json.loads(row["evidence"])
            for row in conn.execute("SELECT id, evidence FROM work_case")
        }
    for case in cases:
        if case["status"] in {"verified", "resolved", "deferred"}:
            continue
        ev = evidence_rows.get(case["id"], {})
        norm = ev.get("normalized") or {}
        npi = str(norm.get("npi") or "")
        if not npi and str(ev.get("provider_id") or "").startswith("NPI:"):
            npi = str(ev["provider_id"]).split("NPI:", 1)[1]
        loc = _location_code(case.get("location_id"), norm)
        if npi:
            by_provider_loc.setdefault((npi, loc), []).append(case["id"])
            by_npi.setdefault(npi, []).append(case["id"])
    return cases, by_provider_loc, by_npi


def build_directory_records(
    store,
    *,
    search: str = "",
    location: str = "",
    network: str = "",
) -> list[dict[str, Any]]:
    """Aggregate deduplicated clinician-location records from committed observations and catalog metadata."""
    _, by_provider_loc, _ = _open_cases_index(store)
    catalog_data = store.catalog()
    loc_labels = {item["id"]: item["label"] for item in catalog_data.get("locations", [])}
    net_labels = {item["id"]: item["label"] for item in catalog_data.get("networks", [])}

    with store.db() as conn:
        obs_rows = conn.execute(
            """
            SELECT o.*, r.source, r.metadata AS receipt_metadata, r.received_at,
                   p.practice_location_id, p.network_id, p.listed_status, p.effective_date
            FROM observation o
            JOIN attempt a ON a.id = o.attempt_id
            JOIN receipt r ON r.id = a.receipt_id
            LEFT JOIN participation_observation p ON p.observation_id = o.id
            WHERE a.state = 'committed'
            ORDER BY o.retrieved_at ASC, o.rowid ASC
            """
        ).fetchall()

    records: dict[tuple[str, str], dict[str, Any]] = {}
    for row in obs_rows:
        norm = json.loads(row["normalized"])
        orig = json.loads(row["original"])
        npi = str(norm.get("npi") or "")
        if not npi and row["provider_id"] and str(row["provider_id"]).startswith("NPI:"):
            npi = str(row["provider_id"]).split("NPI:", 1)[1]
        if not npi:
            continue
        code = _location_code(row["location_id"], norm)
        key = (npi, code)
        existing = records.get(key)
        networks_set = set(existing["networks"]) if existing else set()
        if row["network_id"] and row["network_id"] in net_labels:
            networks_set.add(net_labels[row["network_id"]])
        for net_key in ("network_label", "network_name", "networks"):
            raw_net = norm.get(net_key) or orig.get(net_key)
            if isinstance(raw_net, str) and raw_net.strip():
                for part in raw_net.split(";"):
                    if part.strip():
                        networks_set.add(part.strip())
            elif isinstance(raw_net, list):
                networks_set.update(str(v).strip() for v in raw_net if str(v).strip())

        loc_name = (
            loc_labels.get(row["practice_location_id"])
            or norm.get("location_name")
            or orig.get("location_name")
            or orig.get("clinic_name")
            or code
        )
        raw_visible = norm.get("directory_visible")
        if raw_visible is None and row["listed_status"]:
            raw_visible = row["listed_status"] != "not_listed"
        if raw_visible is None:
            excl = str(orig.get("Dir_Exclude_Flag") or orig.get("exclude_flag") or "").strip().upper()
            raw_visible = False if excl == "Y" else True

        phone = normalize_phone(norm.get("phone") or orig.get("phone") or "")
        ext = norm.get("phone_extension") or orig.get("phone_extension") or None
        specialty = norm.get("specialty") or orig.get("specialty") or "General Practice"
        panel_accepting = _reported_panel(norm, orig)
        hb_leak = bool(
            is_hospital_based_taxonomy(str(specialty))
            and raw_visible
            and panel_accepting is True
        )
        state_val = str(norm.get("state") or orig.get("state") or "")
        lic_state = norm.get("license_state") or orig.get("license_state")
        psv_status = norm.get("psv_status") or orig.get("psv_status")
        pecos_status = (
            norm.get("pecos_status")
            or orig.get("pecos_status")
            or "unverified"
        )
        regimes = classify_regulatory_regimes(sorted(networks_set), row["source"])
        four_gate = build_four_gate_evidence(
            npi=npi,
            npi_luhn_valid=is_valid_npi(npi),
            practice_state=state_val,
            license_state=str(lic_state) if lic_state else None,
            psv_status=str(psv_status) if psv_status else None,
            pecos_status=str(pecos_status) if pecos_status else None,
            accepting_new_patients=panel_accepting,
            hospital_based_newpt_leak=hb_leak,
        )
        case_ids = by_provider_loc.get(key, [])
        records[key] = {
            "id": f"{npi}:{code}",
            "provider_name": str(norm.get("provider_name") or orig.get("provider_name") or f"NPI {npi}"),
            "npi": npi,
            "npi_luhn_valid": is_valid_npi(npi),
            "specialty": str(specialty),
            "location_code": code,
            "location_name": str(loc_name),
            "address": str(norm.get("address") or orig.get("address") or ""),
            "city": str(norm.get("city") or orig.get("city") or ""),
            "state": state_val,
            "zip": str(norm.get("zip") or orig.get("zip") or ""),
            "phone": phone,
            "phone_extension": str(ext) if ext else None,
            "networks": sorted(networks_set),
            "directory_visible": bool(raw_visible),
            "verified_at": row["human_verified_at"],
            "open_issues": len(case_ids),
            "primary_case_id": case_ids[0] if case_ids else None,
            "source": row["source"],
            "regulatory_regimes": regimes,
            "hospital_based_newpt_risk": hb_leak,
            "licensure_psv_status": four_gate["gate2_licensure"]["status"],
            "four_gate_evidence": four_gate,
        }

    items = sorted(records.values(), key=lambda r: (r["open_issues"] == 0, r["provider_name"], r["location_code"]))
    q = search.strip().lower()
    if q:
        items = [
            item
            for item in items
            if q in item["provider_name"].lower()
            or q in item["npi"].lower()
            or q in item["specialty"].lower()
            or q in item["location_code"].lower()
            or q in item["location_name"].lower()
            or q in item["city"].lower()
        ]
    if location.strip():
        items = [item for item in items if item["location_code"] == location.strip()]
    if network.strip():
        items = [item for item in items if network.strip() in item["networks"]]
    return items


def build_overview(store, schema_catalog=None) -> dict[str, Any]:
    """Build executive & operational KPI metrics across work queue, feeds, directory, and schema catalog."""
    cases, _, _ = _open_cases_index(store)
    directory = build_directory_records(store)
    today_iso = date.today().isoformat()

    open_cases = [c for c in cases if c["status"] not in {"verified", "resolved", "deferred"}]
    high_risk = [c for c in open_cases if c["risk_level"] == "high"]
    sla_at_risk = [
        c
        for c in open_cases
        if c["risk_level"] == "high" or (c.get("follow_up") and str(c["follow_up"]) < today_iso)
    ]

    feeds = ManagedFeed(store).list().get("items", [])
    approved_feeds = sum(1 for f in feeds if f.get("current_version"))
    # Reviewed-correction candidates await approval but are not held source deliveries.
    held_deliveries = sum(
        1
        for f in feeds
        for v in f.get("versions", [])
        if v.get("state") == "candidate" and v.get("kind") != "derived_field_candidate"
    )
    quarantined_rows = 0
    feed_service = ManagedFeed(store)
    for f in feeds:
        for v in f.get("versions", []):
            # A correction candidate repeats its base's quarantine counts; count each source once.
            held = v.get("state") == "candidate" and v.get("kind") != "derived_field_candidate"
            if held or v["id"] == f.get("current_version"):
                detail = feed_service.version(v["id"])
                quarantined_rows += int((detail.get("report", {}).get("counts") or {}).get("quarantined") or 0)

    total_records = len(directory)
    clean_records = sum(1 for r in directory if r["open_issues"] == 0)
    clean_rate_pct = round(100.0 * clean_records / total_records, 1) if total_records else 100.0
    unique_providers = len({r["npi"] for r in directory})
    unique_locations = len({r["location_code"] for r in directory})

    variants_count = 0
    if schema_catalog is not None:
        variants_count = len(schema_catalog.snapshot().variants)

    return {
        "total_providers": unique_providers,
        "total_locations": unique_locations,
        "total_directory_listings": total_records,
        "clean_rate_pct": clean_rate_pct,
        "listings_without_open_issues": clean_records,
        "open_discrepancies": len(open_cases),
        "high_risk_discrepancies": len(high_risk),
        "held_deliveries": held_deliveries,
        "approved_feeds": approved_feeds,
        "sla_at_risk": len(sla_at_risk),
        "quarantined_rows": quarantined_rows,
        "schema_variants_count": variants_count,
        "mode": "live",
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }


def schema_catalog_status(schema_catalog=None) -> dict[str, Any]:
    """Summarize active reviewed schema variants from provider-network-intake."""
    if schema_catalog is None:
        return {"enabled": False, "catalog_revision": 0, "variants": []}
    snapshot = schema_catalog.snapshot()
    variants = []
    for variant in snapshot.variants:
        body = variant.to_dict()
        variants.append(
            {
                "id": variant.id,
                "source": body["source"],
                "payer": body.get("payer"),
                "network": body.get("network"),
                "source_version": body.get("source_version"),
                "contract": body["contract"],
                "grain": body["grain"],
                "headers": body["headers"],
                "mapping": body["mapping"],
                "transforms": body["transforms"],
                "source_notes": body["source_notes"],
            }
        )
    return {
        "enabled": True,
        "catalog_revision": snapshot.revision,
        "variants": variants,
    }


def _case_domain_signals(
    item: dict[str, Any],
    ev: dict[str, Any],
    npi: str | None,
) -> dict[str, Any]:
    """Compute domain triage signals (regime, phone conflict, hospital newpt, 4-gate truth) for a case."""
    norm = ev.get("normalized") or {}
    orig = ev.get("original") or {}
    net_hint = (
        item.get("network_label")
        or item.get("network_id")
        or norm.get("network_label")
        or norm.get("network_name")
        or orig.get("network_label")
        or orig.get("network_name")
        or ev.get("source")
        or item.get("source")
    )
    regimes = classify_regulatory_regimes(
        [str(net_hint)] if net_hint else [],
        str(ev.get("source") or item.get("source") or ""),
    )
    regime = regimes[0] if regimes else classify_regulatory_regime(str(net_hint or ""))

    phone_conflict = (
        classify_phone_conflict(item.get("listing_value"), item.get("reference_value"))
        if item.get("field_name") == "phone"
        else None
    )

    specialty = str(norm.get("specialty") or orig.get("specialty") or "")
    raw_visible = norm.get("directory_visible")
    visible = True if raw_visible is None else bool(raw_visible)
    panel_accepting = _reported_panel(norm, orig)
    hb_risk = bool(
        is_hospital_based_taxonomy(specialty)
        and visible
        and panel_accepting is True
    )
    practice_state = str(norm.get("state") or orig.get("state") or "")
    license_state = norm.get("license_state") or orig.get("license_state")
    four_gate = build_four_gate_evidence(
        npi=npi,
        npi_luhn_valid=bool(npi and is_valid_npi(npi)),
        practice_state=practice_state,
        license_state=str(license_state) if license_state else None,
        psv_status=norm.get("psv_status") or orig.get("psv_status"),
        pecos_status=norm.get("pecos_status") or orig.get("pecos_status") or "unverified",
        accepting_new_patients=panel_accepting,
        hospital_based_newpt_leak=hb_risk,
    )
    return {
        "regulatory_regime": regime,
        "phone_conflict": phone_conflict,
        "hospital_based_newpt_risk": hb_risk,
        "four_gate_evidence": four_gate,
    }


def enrich_case_detail(case: dict[str, Any]) -> dict[str, Any]:
    """Attach operational domain signals to a single work-case detail payload."""
    ev = case.get("evidence") or {}
    norm = ev.get("normalized") or {}
    npi = str(norm.get("npi") or "")
    if not npi and str(ev.get("provider_id") or "").startswith("NPI:"):
        npi = str(ev["provider_id"]).split("NPI:", 1)[1]
    enriched = {
        **case,
        "npi": case.get("npi") or (npi or None),
        "listing_value": case.get("listing_value") if case.get("listing_value") is not None else ev.get("listing_value"),
        "reference_value": case.get("reference_value") if case.get("reference_value") is not None else ev.get("reference_value"),
    }
    return {
        **enriched,
        **_case_domain_signals(enriched, ev, npi or None),
    }


def build_work_queue(store) -> list[dict[str, Any]]:
    """Return work queue items enriched with formatted field diffs and clinic metadata."""
    items = store.work().get("items", [])
    with store.db() as conn:
        ev_rows = {
            row["id"]: json.loads(row["evidence"])
            for row in conn.execute("SELECT id, evidence FROM work_case")
        }
    loc_names = {
        "NASH-MAIN": "Nashville Midtown Clinic",
        "FRNK-WEST": "Franklin Cool Springs Clinic",
        "BRNT-PARK": "Brentwood Maryland Farms",
        "MURF-EAST": "Murfreesboro Medical Plaza",
        "HEND-LAKE": "Hendersonville Indian Lake",
    }
    enriched: list[dict[str, Any]] = []
    for item in items:
        ev = ev_rows.get(item["id"], {})
        norm = ev.get("normalized") or {}
        npi = str(norm.get("npi") or "")
        if not npi and str(ev.get("provider_id") or "").startswith("NPI:"):
            npi = str(ev["provider_id"]).split("NPI:", 1)[1]
        code = _location_code(item.get("location_id"), norm)
        clinic_name = item.get("location_label") or loc_names.get(code) or code
        row = {
            **item,
            "listing_value": ev.get("listing_value"),
            "reference_value": ev.get("reference_value"),
            "npi": npi or None,
            "location_code": code,
            "clinic_name": clinic_name,
        }
        row.update(_case_domain_signals(row, ev, npi or None))
        enriched.append(row)
    return enriched


PHONE_REVIEW_LIMIT = 50


def _phone_option(option: dict[str, Any], roster_receipts: set[str]) -> dict[str, Any]:
    value = option.get("comparison_value") or {}
    return {
        "ref": option["ref"],
        "source": option["source"],
        "number": value.get("number"),
        "extension": value.get("extension"),
        "locator": option["locator"],
        "selectable": bool(option["selectable"]),
        "findings": option.get("findings") or [],
        "from_approved_roster": option["receipt_id"] in roster_receipts,
    }


def build_phone_reviews(store) -> dict[str, Any]:
    """List reviewed clinician/office phone scopes with their correction state.

    Scopes come only from current reviewed clinician and office links; a scope
    needs both, so an NPI alone never places a phone at an office. Bounded to
    PHONE_REVIEW_LIMIT clinicians for the workbench view.
    """
    from .field_materialization import FieldMaterialization
    from .field_reconciliation import FieldReconciliation

    feeds = ManagedFeed(store)
    current = [f["current_version"] for f in feeds.list().get("items", []) if f.get("current_version")]
    fields, materialization = FieldReconciliation(store), FieldMaterialization(store)
    current_links = """FROM reviewed_identity_link l WHERE NOT EXISTS (
        SELECT 1 FROM reviewed_identity_link n WHERE n.kind=l.kind AND n.ref=l.ref AND n.seq>l.seq)"""
    items: list[dict[str, Any]] = []
    with store.db() as conn:
        conn.execute("BEGIN")
        clinicians = [r[0] for r in conn.execute(
            f"SELECT DISTINCT l.clinician_id {current_links} AND l.kind='clinician' ORDER BY l.clinician_id LIMIT ?",
            (PHONE_REVIEW_LIMIT,))]
        locations = [r[0] for r in conn.execute(
            f"SELECT DISTINCT l.practice_location_id {current_links} AND l.kind='location' ORDER BY l.practice_location_id")]
        bases = {}
        for version_id in current:
            manifest = json.loads(conn.execute("SELECT manifest FROM feed_version WHERE id=?", (version_id,)).fetchone()[0])
            bases[manifest["receipt_id"]] = version_id
        for clinician_id in clinicians:
            for location_id in locations:
                view = fields._view(conn, clinician_id, location_id)
                phone = next(f for f in view["fields"] if f["field"] == "phone")
                if not phone["options"]:
                    continue
                receipts = {o["receipt_id"] for o in phone["options"]}
                base = next((bases[r] for r in receipts if r in bases), None)
                options = [_phone_option(o, set(bases)) for o in phone["options"]]
                values = {(o["number"], o["extension"]) for o in options if o["selectable"]}
                decision = phone["decision"]
                lineage = conn.execute(
                    """SELECT v.id FROM feed_version v
                       WHERE json_extract(v.manifest,'$.materialization.clinician_id')=?
                         AND json_extract(v.manifest,'$.materialization.location_id')=?
                       ORDER BY v.created_at DESC""",
                    (clinician_id, location_id)).fetchall()
                candidates = []
                for row in lineage:
                    state = conn.execute(
                        "SELECT decision FROM feed_decision WHERE version_id=? ORDER BY created_at DESC LIMIT 1",
                        (row["id"],)).fetchone()
                    manifest = json.loads(conn.execute("SELECT manifest FROM feed_version WHERE id=?", (row["id"],)).fetchone()[0])
                    candidates.append({
                        "version_id": row["id"],
                        "state": state["decision"] if state else "candidate",
                        "decision_id": manifest["materialization"]["decision_id"],
                        "old_value": manifest["materialization"]["old_value"],
                        "new_value": manifest["materialization"]["new_value"],
                    })
                correction = {"status": "no_roster"} if base is None else materialization.assess(conn, base, clinician_id, location_id, view)
                selectable_numbers: list[str] = []
                for opt in options:
                    num = opt.get("number")
                    if opt.get("selectable") and num and num not in selectable_numbers:
                        selectable_numbers.append(str(num))
                phone_conflict = (
                    classify_phone_conflict(
                        selectable_numbers[0] if selectable_numbers else None,
                        selectable_numbers[1] if len(selectable_numbers) > 1 else (selectable_numbers[0] if selectable_numbers else None),
                    )
                    if len(values) > 1
                    else None
                )
                items.append({
                    "clinician_id": clinician_id,
                    "clinician_label": view["clinician"]["label"],
                    "location_id": location_id,
                    "location_label": view["location"]["label"],
                    "snapshot": view["snapshot"],
                    "inputs_fresh": view["inputs_fresh"],
                    "status": phone["status"],
                    "sources_agree": len(values) <= 1,
                    "phone_conflict": phone_conflict,
                    "options": options,
                    "decision": None if decision is None else {
                        "id": decision["id"],
                        "decision": decision["decision"],
                        "selected_ref": decision["selected_ref"],
                        "actor": decision["actor"],
                        "reason": decision["reason"],
                        "created_at": decision["created_at"],
                    },
                    "base_version": base,
                    "correction": correction,
                    "candidates": candidates,
                })
    return {"items": items, "limit": PHONE_REVIEW_LIMIT, "truncated": len(clinicians) == PHONE_REVIEW_LIMIT}


def mount_workbench_routes(app, store, schema_catalog=None) -> None:
    """Attach clean overview, directory, work-queue, and schema-catalog read endpoints."""

    @app.get("/api/schema-catalog/status")
    def get_schema_catalog_status():
        return schema_catalog_status(schema_catalog)

    @app.get("/api/workbench/overview")
    def get_workbench_overview():
        return build_overview(store, schema_catalog)

    @app.get("/api/workbench/directory")
    def get_workbench_directory(search: str = "", location: str = "", network: str = ""):
        return {"items": build_directory_records(store, search=search, location=location, network=network)}

    @app.get("/api/workbench/work")
    def get_workbench_work():
        return {"items": build_work_queue(store)}

    @app.get("/api/workbench/phone-reviews")
    def get_workbench_phone_reviews():
        return build_phone_reviews(store)
