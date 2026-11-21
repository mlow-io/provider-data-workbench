"""Independent synthetic reconciliation truth; no matcher or application imports.

Truth is assigned to latent entities/offices before source values are rendered.
Evaluation references identify retained rows/addresses, never future identities.
"""
from __future__ import annotations

import argparse
from collections import defaultdict
from itertools import combinations
import json
from pathlib import Path
import random

SOURCES = ("clinic", "payer", "reference")
VERSION = "synthetic-reconciliation-corpus-v1"


def address_ref(clinician_ref: str, path: str) -> str:
    return f"{clinician_ref}@{path}"


def _pairs(groups: dict, sources: dict) -> list[list[str]]:
    """Expand authored truth groups, deduplicating rows with several addresses."""
    return [list(pair) for pair in sorted({
        tuple(sorted((left, right)))
        for members in groups.values()
        for left, right in combinations(sorted(set(members)), 2)
        if sources[left] != sources[right]
    })]


def build_corpus(seed: int = 42, entities: int = 300) -> dict:
    """Return comparison records and separate exhaustive latent positive labels.

    Every entity has three source rows. Every tenth entity has a second office
    (a separate clinic/payer row and another reference address); every twentieth
    reference row also retains mailing evidence. Default: 1,005 address records.
    Unknown and organization entities have location truth but no clinician truth.
    Supplied IDs/values deliberately contain omissions and contradictions; labels
    depend exclusively on the preassigned latent identities and physical offices.
    """
    if isinstance(entities, bool) or not isinstance(entities, int) or entities < 1:
        raise ValueError("entities must be a positive integer")
    rng = random.Random(seed)
    # Four people share each building: two in each suite. The second office is
    # separately numbered, so neither clinician identity nor street alone is truth.
    latent = [{"id": i, "kind": "organization" if i % 29 == 0 else
               "unknown" if i % 31 == 0 else "clinician",
               "offices": [(i // 4, (i % 4) // 2)] +
               ([(entities + i, 0)] if i % 10 == 0 else [])}
              for i in range(entities)]
    records, clinician_groups, location_groups = [], defaultdict(list), defaultdict(list)
    row_sources, address_sources, entity_truth, location_truth = {}, {}, {}, {}
    selected_refs = {}
    for source_index, source in enumerate(SOURCES):
        shuffled = list(range(entities))
        rng.shuffle(shuffled)
        for entity in latent:
            i, kind = entity["id"], entity["kind"]
            # Independent source-local row ordering prevents positional IDs from
            # acting as a cross-source business identifier.
            row_label = f"{source}:row-{shuffled[i]:05d}"
            native_id = None if (i + source_index) % 7 == 0 else f"SYN-{source}-{shuffled[i]:05d}"
            npi = None if i % 9 == 0 or (i + source_index) % 13 == 0 else f"{i + 1:010d}"
            if source == "payer" and i % 23 == 1:
                npi = f"{i:010d}"  # Contradiction copied from a distinct entity.
            name = f"Synthetic Person {i:04d}" if kind != "organization" else f"Synthetic Group {i:04d}"
            if i % 17 in (3, 4):
                name = f"Synthetic Ambiguous {i // 17:03d}"
            if source == "payer":
                name = name.upper()
            elif source == "reference":
                name = "  " + name.replace(" ", "  ") + "  "
            for office_index, (building, suite_index) in enumerate(entity["offices"]):
                row_ref = row_label if source == "reference" or office_index == 0 else row_label + "-office-2"
                path = f"addresses[{office_index + (1 if i % 20 == 0 else 0)}]" if source == "reference" else "addresses[0]"
                ref = address_ref(row_ref, path)
                office = f"office-{building:05d}-suite-{suite_index}"
                phone_digits = f"212555{100 + building % 100:04d}"
                phone = phone_digits if source == "clinic" else f"(212) 555-{phone_digits[-4:]}"
                if source == "payer" and i % 19 == 0:
                    phone = "2125550199"
                if source == "reference" and i % 11 == 0:
                    phone = None
                record = {
                    "ref": ref, "clinician_ref": row_ref, "source": source,
                    "entity_kind": kind, "native_id": native_id,
                    "provider_name": name, "npi": npi, "phone": phone,
                    "phone_extension": "007" if building % 8 == 0 else None,
                    "address": {"line1": f"{100 + building} Synthetic {'Street' if source == 'payer' else 'St'}",
                                "suite": f"{'Suite ' if source == 'payer' else ''}{100 + suite_index * 100}",
                                "city": "Syntheticville", "state": "ma" if source == "payer" else "MA",
                                "zip": "02108-0042" if source == "reference" else "02108",
                                "kind": "practice", "path": path},
                }
                records.append(record)
                row_sources[row_ref] = source
                address_sources[ref] = source
                if kind == "clinician":
                    clinician_groups[f"entity-{i:05d}"].append(row_ref)
                    entity_truth[row_ref] = f"entity-{i:05d}"
                location_groups[office].append(ref)
                location_truth[ref] = office
                selected_refs.setdefault(row_ref, ref)
            if source == "reference" and i % 20 == 0:
                mailing = {**record, "ref": address_ref(row_label, "addresses[0]"),
                           "clinician_ref": row_label,
                           "address": {"line1": f"PO Box {i + 1}", "suite": None,
                                       "city": "Syntheticville", "state": "MA", "zip": "02108",
                                       "kind": "mailing", "path": "addresses[0]"}}
                records.append(mailing)
                address_sources[mailing["ref"]] = source
    return {
        "records": records,
        "expected_clinician_pairs": _pairs(clinician_groups, row_sources),
        "expected_location_pairs": _pairs(location_groups, address_sources),
        "metadata": {"version": VERSION, "synthetic": True, "seed": seed,
                     "entities": entities, "record_count": len(records),
                     "sources": list(SOURCES), "truth_method": "Latent truth assigned before source rendering; no matching output used.",
                     "positive_label_scope": "Exhaustive cross-source clinician and practice-office truth within generated inputs.",
                     "clinician_truth": entity_truth, "location_truth": location_truth,
                     "selected_address_refs": selected_refs,
                     "limits": "Fictional, deliberately invalid synthetic identifiers; synthetic evaluation does not establish production accuracy."},
    }


def load_labeled_fixture(path: str | Path) -> dict:
    """Adapt authored R0 fixtures without inferring any labels from source values.

    Emit every native practice/mailing address and retain the explicitly selected
    path in metadata. Unlabeled fixture pairs are unassessed, not known negatives.
    """
    fixture = json.loads(Path(path).read_text())
    records, row_sources, address_sources, selected_refs = [], {}, {}, {}
    for source_name, rows in fixture["sources"].items():
        source = "reference" if source_name == "public_reference" else source_name
        for row in rows:
            row_ref = row["record_id"]
            row_sources[row_ref] = source
            selected = row.get("selected_address")
            addresses = row.get("native_addresses", [])
            if selected is not None and selected["path"] not in {a["path"] for a in addresses}:
                raise ValueError(f"Selected address is absent: {row_ref}")
            selected_refs[row_ref] = address_ref(row_ref, selected["path"]) if selected else None
            for address in addresses:
                ref = address_ref(row_ref, address["path"])
                address_sources[ref] = source
                records.append({
                    "ref": ref, "clinician_ref": row_ref, "source": source,
                    "entity_kind": row.get("entity_type", "unknown"),
                    "native_id": row.get("source_native_id"),
                    "provider_name": row.get("name"), "npi": row.get("npi"),
                    "phone": row.get("phone"), "phone_extension": row.get("phone_extension"),
                    "address": {field: address.get(field) for field in
                                ("line1", "suite", "city", "state", "zip", "kind", "path")},
                })
    clinicians = {group["clinician_id"]: group["records"] for group in fixture["expected_clinician_links"]}
    locations = {group["location_id"]: [address_ref(member["record"], member["address_path"])
                                       for member in group["members"]]
                 for group in fixture["expected_location_links"]}
    by_ref = {record["ref"]: record for record in records}
    if any(ref not in by_ref or by_ref[ref]["address"]["kind"] != "practice"
           for members in locations.values() for ref in members):
        raise ValueError("Location truth must reference a retained practice address")
    return {"records": records,
            "expected_clinician_pairs": _pairs(clinicians, row_sources),
            "expected_location_pairs": _pairs(locations, address_sources),
            "metadata": {"version": VERSION, "synthetic": True,
                         "fixture_id": fixture["fixture_id"], "record_count": len(records),
                         "selected_address_refs": selected_refs,
                         "positive_label_scope": "Authored links only; other pairs may be unresolved or unassessed.",
                         "expected_unresolved": fixture.get("expected_unresolved", []),
                         "expected_clinician_nonlinks": fixture.get("expected_clinician_nonlinks", []),
                         "expected_location_nonlinks": fixture.get("expected_location_nonlinks", [])}}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True, help="New output JSON path; existing files are rejected")
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--entities", type=int, default=300)
    parser.add_argument("--fixture", type=Path, help="Adapt an authored challenge/held-out fixture instead")
    args = parser.parse_args()
    corpus = load_labeled_fixture(args.fixture) if args.fixture else build_corpus(args.seed, args.entities)
    with args.output.open("x") as output:
        json.dump(corpus, output, indent=2)
        output.write("\n")
    print(json.dumps({"output": str(args.output), "records": len(corpus["records"]),
                      "clinician_pairs": len(corpus["expected_clinician_pairs"]),
                      "location_pairs": len(corpus["expected_location_pairs"])}))


if __name__ == "__main__":
    main()
