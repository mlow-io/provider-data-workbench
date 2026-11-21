"""Independent I1 fixture evaluation over explicitly reviewed retained evidence.

Expected outcomes come only from frozen impact_case labels, never engine output.
All preparation writes belong to a newly created evaluation root. No source is
accepted and no follow-up work is created.
"""
from __future__ import annotations

import argparse
from copy import deepcopy
import csv
import hashlib
import io
import json
from pathlib import Path
import tempfile
import uuid

from provider_directory_truth_layer.field_reconciliation import FieldReconciliation
from provider_directory_truth_layer.identity_review import IdentityReview
from provider_directory_truth_layer.intake_store import IntakeStore
from provider_directory_truth_layer.reconciliation_store import ReconciliationStore

REVIEW = {"actor": "Synthetic impact evaluator", "reason": "Explicitly enact independently authored fixture relationships"}
ROOT = Path(__file__).resolve().parents[1]


def score_impact(case, actual):
    """Score declared records only; report extra engine scope separately.

    actual maps original evaluation labels to affected/unaffected/not_assessed.
    Missing classifications remain missing rather than being counted unaffected.
    """
    expected = {}
    for field, status in (("expected_targets", "affected"),
                          ("expected_unaffected", "unaffected_within_assessed_scope"),
                          ("expected_not_assessed", "not_assessed")):
        for row in case[field]:
            if row["record"] in expected:
                raise ValueError("Overlapping impact labels")
            expected[row["record"]] = status
    declared = set(case["assessed_records"])
    if set(expected) != declared:
        raise ValueError("Impact labels must partition the declared assessed records")
    true_targets = {r for r, s in expected.items() if s == "affected"}
    proposed = {r for r, s in actual.items() if s == "affected" and r in declared}
    true_positive = true_targets & proposed
    counts = {status: sum(actual.get(r) == status for r in declared)
              for status in ("affected", "unaffected_within_assessed_scope", "not_assessed")}
    mismatches = [{"record": r, "expected": expected[r], "actual": actual.get(r)}
                  for r in sorted(declared) if expected[r] != actual.get(r)]
    return {"declared_record_count": len(declared), "expected_counts": case["expected_counts"],
            "actual_counts_within_declared_scope": counts,
            "target_precision_within_declared_scope": len(true_positive) / len(proposed) if proposed else None,
            "target_recall_within_declared_scope": len(true_positive) / len(true_targets) if true_targets else None,
            "true_positive_targets": sorted(true_positive),
            "incorrect_targets": sorted(proposed - true_targets),
            "missed_targets": sorted(true_targets - proposed), "mismatches": mismatches,
            "unassessed_coverage_within_declared_scope": counts["not_assessed"] / len(declared) if declared else None,
            "missing_records": sorted(declared - set(actual)),
            "outside_declared_scope": {r: actual[r] for r in sorted(set(actual) - declared)}}


def _catalog(store, fixture):
    payer = store.create_catalog("organizations", {"label": "Synthetic evaluation payer", "kind": "payer", **REVIEW})
    clinic = store.create_catalog("organizations", {"label": "Synthetic evaluation clinic", "kind": "clinic", **REVIEW})
    networks = {n["network_id"]: store.create_catalog("networks", {
        "label": n["name"], "payer_organization_id": payer["id"], **REVIEW})["id"] for n in fixture["networks"]}
    locations = {g["location_id"]: store.create_catalog("locations", {
        "label": g["label"], "organization_id": clinic["id"], **REVIEW})["id"]
                 for g in fixture["expected_location_links"]}
    bindings = {"network": {}, "location": {}, "organization": {}}
    for kind, targets in (("network", networks), ("location", locations), ("organization", {"SYNTHETIC-CLINIC": clinic["id"]})):
        for code, target in targets.items():
            bindings[kind][code] = store.bind_source({"source": "payer", "kind": kind,
                "source_key": code, "target_id": target, **REVIEW})["id"]
    return networks, locations, bindings


def _native_row(row):
    selected = row.get("selected_address")
    addresses = deepcopy(row["native_addresses"])
    primary = next((a for a in addresses if selected and a["path"] == selected["path"]), addresses[0])
    return {"record_id": row.get("source_native_id"), "evaluation_ref": row["record_id"],
            "entity_type": row["entity_type"], "npi": row["npi"], "provider_name": row["name"],
            "phone": row["phone"], "address": primary["line1"], "suite": primary.get("suite"),
            "city": primary["city"], "state": primary["state"], "zip": primary["zip"],
            "native_addresses": addresses, "selected_address": deepcopy(selected)}


def prepare_sources(store, fixture):
    """Import immutable inputs, retaining missing native IDs and explicit networks."""
    networks, locations, bindings = _catalog(store, fixture)
    receipts = {}
    for source, rows in fixture["sources"].items():
        if source != "payer":
            receipts[source] = store.receive(json.dumps([_native_row(row) for row in rows]).encode(),
                source + ".json", source=source, metadata={"scope": fixture["fixture_id"]})
            continue
        location_codes = {m["record"]: g["location_id"] for g in fixture["expected_location_links"]
                          for m in g["members"] if m["record"].startswith("payer:")}
        fields = ["record_id", "evaluation_ref", "entity_type", "npi", "provider_name", "phone",
                  "address", "suite", "city", "state", "zip", "location_id", "network_code", "organization_code"]
        output = io.StringIO()
        writer = csv.DictWriter(output, fieldnames=fields)
        writer.writeheader()
        for row in rows:
            native = _native_row(row)
            writer.writerow({**{k: native.get(k) for k in fields},
                             "location_id": location_codes.get(row["record_id"], ""),
                             "network_code": row["network_id"], "organization_code": "SYNTHETIC-CLINIC"})
        receipt = store.receive(output.getvalue().encode(), "payer.csv", source="payer", metadata={"scope": fixture["fixture_id"]})
        receipts[source] = store.mapping(receipt["id"], {"mapping": {field: field for field in fields if field not in {"evaluation_ref", "entity_type"}},
                                                       "roster_kind": "network", "bindings": bindings})
    return receipts, networks, locations


def _approve_group(review, run, candidates, members, target=None, label=None):
    linked = set()
    for candidate in candidates:
        refs = {candidate["left"], candidate["right"]}
        if not refs <= members or refs <= linked:
            continue
        context = review.inspect(run["id"], candidate["id"])
        saved = review.decide({"run_id": run["id"], "candidate_id": candidate["id"], "decision": "approve",
            "request_id": uuid.uuid4().hex, "expected_snapshot": context["review_snapshot"],
            "expected_revisions": {ref: link["id"] if link else None for ref, link in context["current_links"].items()},
            "expected_decision": context["latest_decision"]["id"] if context["latest_decision"] else None,
            **({"target_id": target} if target else {"new_label": label}), **REVIEW})
        target = saved["decision"]["target_id"]
        linked |= refs
    if linked != members:
        raise ValueError(f"Authored truth could not be explicitly linked through retained candidates: {sorted(members - linked)}")
    return target


def prepare_reviewed_case(root: Path, fixture: dict):
    root.mkdir(parents=True, exist_ok=False)
    store = IntakeStore(root / "directory.sqlite3", root)
    receipts, networks, locations = prepare_sources(store, fixture)
    comparison = ReconciliationStore(store)
    run = comparison.create_run({"inputs": [{"receipt_id": r["id"], "attempt_id": r["attempt_id"], "entity_kind": "unknown"}
                                           for r in receipts.values()], **REVIEW})
    exported = comparison.export(run["id"])
    records = exported["records"]
    row_refs = {r["evaluation_ref"]: r["clinician_ref"] for r in records}
    address_refs = {(r["evaluation_ref"], r["address"].get("source_path", r["address_path"])): r["ref"] for r in records}
    # Flat payer rows have exactly one address and a native empty address path.
    for row in fixture["sources"]["payer"]:
        address_refs[(row["record_id"], row["native_addresses"][0]["path"])] = address_refs[(row["record_id"], "")]
    review = IdentityReview(store)
    clinicians = {}
    for group in fixture["expected_clinician_links"]:
        clinicians[group["clinician_id"]] = _approve_group(review, run,
            [c for c in exported["candidates"] if c["kind"] == "clinician"],
            {row_refs[r] for r in group["records"]}, label=group["clinician_id"])
    for group in fixture["expected_location_links"]:
        _approve_group(review, run, [c for c in exported["candidates"] if c["kind"] == "location"],
            {address_refs[(m["record"], m["address_path"])] for m in group["members"]}, target=locations[group["location_id"]])
    case = fixture["impact_case"]
    person, office = clinicians[case["clinician_id"]], locations[case["location_id"]]
    fields = FieldReconciliation(store)
    view = fields.inspect(person, office)
    phone = next(f for f in view["fields"] if f["field"] == "phone")
    anchor_row = next(row for row in fixture["sources"]["clinic"] if row["record_id"] == case["anchor_record"])
    anchor = address_refs[(case["anchor_record"], anchor_row["selected_address"]["path"])]
    fields.decide({"clinician_id": person, "location_id": office, "field": "phone", "decision": "select",
        "selected_ref": anchor, "expected_snapshot": view["snapshot"],
        "expected_decision": phone["decision"]["id"] if phone["decision"] else None,
        "request_id": uuid.uuid4().hex, **REVIEW})
    return {"store": store, "receipts": receipts, "networks": networks, "locations": locations,
            "clinicians": clinicians, "records": records, "person": person, "office": office}


def evaluate_fixture(root: Path, fixture_path: Path):
    from provider_directory_truth_layer.change_impact import ChangeImpact
    original = fixture_path.read_bytes()
    fixture = json.loads(original)
    prepared = prepare_reviewed_case(root, fixture)
    store, case = prepared["store"], fixture["impact_case"]
    payer = prepared["receipts"]["payer"]
    service = ChangeImpact(store)
    view = FieldReconciliation(store).inspect(prepared["person"], prepared["office"])
    proposal = service.create({"clinician_id": prepared["person"], "location_id": prepared["office"],
        "field": case["field"], "proposed_value": {"number": case["proposed_value"], "extension": None},
        "inputs": [{"receipt_id": payer["id"], "attempt_id": payer["attempt_id"], "entity_kind": "unknown"}],
        "expected_snapshot": view["snapshot"], "network_ids": [prepared["networks"][n] for n in case["network_scope"]],
        "request_id": uuid.uuid4().hex, **REVIEW})
    before = hashlib.sha256(store.path.read_bytes()).hexdigest()
    preview = service.preview(proposal["id"], limit=100)
    after = hashlib.sha256(store.path.read_bytes()).hexdigest()
    actual, target_evidence = {}, []
    known_refs = {r["ref"]: r for r in prepared["records"]}
    network_labels = {value: label for label, value in prepared["networks"].items()}
    for target in preview["targets"]:
        retained = known_refs[target["ref"]]
        label = retained["evaluation_ref"]
        if label in actual:
            raise ValueError("Evaluation requires one exact retained payer address per labeled row")
        actual[label] = target["classification"]
        target_evidence.append({"record": label, "ref": target["ref"],
            "address_path": target["address_path"], "network_id": target["network_id"],
            "network_label": network_labels.get(target["network_id"]),
            "classification": target["classification"], "reason": target["reason"]})
    actual_networks = {t["record"]: t["network_label"] for t in target_evidence}
    network_mismatches = [{"record": t["record"], "expected": t["network_id"], "actual": actual_networks.get(t["record"])}
                          for t in case["expected_targets"] if actual_networks.get(t["record"]) != t["network_id"]]
    result = {"fixture_id": fixture["fixture_id"], "fixture_sha256": hashlib.sha256(original).hexdigest(),
              "counts": preview["counts"], "inputs_fresh": preview["inputs_fresh"],
              "proposal_id": proposal["id"], "metrics": score_impact(case, actual),
              "actual_classifications": actual, "target_evidence": target_evidence,
              "target_network_mismatches": network_mismatches,
              "anchor_old_value_matches_label": proposal["prior_evidence"]["field"]["preferred_value"] == {"number": case["old_value"], "extension": None},
              "preview_database_unchanged": before == after,
              "fixture_unchanged": original == fixture_path.read_bytes()}
    with store.db() as conn:
        result["accepted_observations"] = conn.execute("SELECT count(*) FROM observation").fetchone()[0]
        result["work_events"] = conn.execute("SELECT count(*) FROM work_event").fetchone()[0]
    return result


def run_evaluation(root: Path):
    root.mkdir(parents=True, exist_ok=False)
    return {"synthetic": True, "scope": "Frozen hand-authored payer impact_case dependency labels only.",
            "limitations": "Explicit approvals enact fixture assumptions. These results do not establish external directory coverage or production impact accuracy.",
            "evaluations": {name: evaluate_fixture(root / name, ROOT / f"tests/fixtures/onboarding/reconciliation_{name}.json")
                            for name in ("challenge", "heldout")}}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True, help="New JSON evidence file; never overwrites")
    parser.add_argument("--root", type=Path, help="New retained evaluation root; otherwise an owned temporary directory is used")
    args = parser.parse_args()
    with args.output.open("x") as output:
        if args.root:
            result = run_evaluation(args.root)
        else:
            with tempfile.TemporaryDirectory(prefix="pdtl-impact-evaluation-") as temporary:
                result = run_evaluation(Path(temporary) / "case")
        json.dump(result, output, indent=2)
        output.write("\n")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
