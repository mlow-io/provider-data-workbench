"""Read-only synthetic candidate evaluation; partial labels are never negatives."""
from __future__ import annotations

import argparse
from collections import defaultdict
import hashlib
from itertools import combinations
import json
from pathlib import Path
import platform
import sys
import time
import tracemalloc

from provider_directory_truth_layer.comparison import RULE_VERSION, generate_candidates

# Keep this runnable both as a direct script and through importlib in tests.
sys.path.insert(0, str(Path(__file__).resolve().parent))
from reconciliation_corpus import build_corpus, load_labeled_fixture


def _pair(left, right):
    return tuple(sorted((left, right)))


def _address_label_pairs(label, addresses):
    """An unspecified multi-address side is ambiguous, not an all-path label."""
    selection = label.get("address_selection") or {}
    resolved = []
    for row in label["records"]:
        refs = addresses.get(row, [])
        if selection.get("record") == row:
            refs = [r for r in refs if r["address"]["path"] == selection.get("address_path")]
        if len(refs) != 1:
            return set()
        resolved.append(refs[0]["ref"])
    return {_pair(a, b) for a, b in combinations(resolved, 2)}


def _authored_labels(corpus, kind):
    metadata = corpus["metadata"]
    addresses = defaultdict(list)
    for record in corpus["records"]:
        addresses[record["clinician_ref"]].append(record)
    nonlinks, unresolved = set(), set()
    for destination, labels in [
        (nonlinks, metadata.get(f"expected_{kind}_nonlinks", [])),
        (unresolved, metadata.get("expected_unresolved", [])),
    ]:
        for label in labels:
            scope = label.get("scope", "")
            if kind == "clinician" and scope in ("clinician", "clinician_and_location"):
                destination.update(_pair(a, b) for a, b in combinations(label["records"], 2))
            elif kind == "location" and scope in ("location", "operating_location", "clinician_and_location"):
                destination.update(_address_label_pairs(label, addresses))
    return nonlinks, unresolved


def _exhaustive(corpus, kind):
    metadata = corpus["metadata"]
    if not metadata.get("positive_label_scope", "").startswith("Exhaustive cross-source"):
        return False
    truth_key = "clinician_truth" if kind == "clinician" else "location_truth"
    truth = metadata.get(truth_key)
    if not isinstance(truth, dict):
        return False
    required = {r["clinician_ref"] for r in corpus["records"] if r["entity_kind"] == "clinician"} if kind == "clinician" else {
        r["ref"] for r in corpus["records"] if r["address"]["kind"] == "practice"}
    return set(truth) == required


def score_candidates(corpus: dict, candidates: list[dict]) -> dict:
    """Score pair retrieval and eligible subsets without changing inputs.

    Eligible means the rule permits human review; it is not a reviewed link.
    Partial authored fixtures have no overall precision denominator because
    candidates outside explicit labels remain unassessed.
    """
    results = {}
    for kind in ("clinician", "location"):
        positives = {_pair(*pair) for pair in corpus[f"expected_{kind}_pairs"]}
        nonlinks, unresolved = _authored_labels(corpus, kind)
        if positives & (nonlinks | unresolved) or nonlinks & unresolved:
            raise ValueError(f"Contradictory {kind} evaluation labels")
        exhaustive = _exhaustive(corpus, kind)
        typed = [candidate for candidate in candidates if candidate["kind"] == kind]
        proposed = {_pair(c["left"], c["right"]): c for c in typed}
        if len(proposed) != len(typed):
            raise ValueError("Duplicate typed candidate pair")
        classifications = {}
        for pair in proposed:
            classifications[pair] = ("positive" if pair in positives else
                                     "known_nonlink" if pair in nonlinks else
                                     "unresolved" if pair in unresolved else
                                     "incorrect" if exhaustive else "unassessed")
        subsets = {}
        for subset in ("all_candidates", "eligible_candidates"):
            selected = {pair for pair, c in proposed.items() if subset == "all_candidates" or c["eligible"]}
            true_pairs = selected & positives
            missed = positives - selected
            counts = {name: sum(classifications[pair] == name for pair in selected)
                      for name in ("positive", "known_nonlink", "unresolved", "unassessed", "incorrect")}
            subsets[subset] = {
                "candidate_count": len(selected), "expected_positive_count": len(positives),
                "proposed_true_links": len(true_pairs), "missed_true_links": len(missed),
                "positive_pair_recall": len(true_pairs) / len(positives) if positives else None,
                "candidate_precision": len(true_pairs) / len(selected) if exhaustive and selected else None,
                "known_nonlink_candidates": counts["known_nonlink"],
                "unresolved_candidates": counts["unresolved"],
                "unassessed_candidates": counts["unassessed"],
                "incorrect_proposals": counts["incorrect"] + counts["known_nonlink"],
                "missed_pairs": [list(pair) for pair in sorted(missed)],
                "nonpositive_pairs": [
                    {"pair": list(pair), "classification": classifications[pair],
                     "eligible": proposed[pair]["eligible"],
                     "agreements": proposed[pair].get("agreements", []),
                     "contradictions": proposed[pair].get("contradictions", []),
                     "missing": proposed[pair].get("missing", [])}
                    for pair in sorted(selected - positives)
                ],
            }
        results[kind] = {"truth_scope": "exhaustive_generated" if exhaustive else "partial_authored",
                         **subsets}
    return results


def evaluate(corpus: dict) -> dict:
    digest = hashlib.sha256(json.dumps(corpus, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    tracemalloc.start()
    start = time.perf_counter()
    try:
        candidates = generate_candidates(corpus["records"])
        elapsed = time.perf_counter() - start
        _, peak = tracemalloc.get_traced_memory()
    finally:
        tracemalloc.stop()
    return {"rule_version": RULE_VERSION, "corpus_sha256": digest,
            "record_count": len(corpus["records"]),
            "clinician_row_count": len({r["clinician_ref"] for r in corpus["records"]}),
            "candidate_count": len(candidates), "eligible_candidate_count": sum(c["eligible"] for c in candidates),
            "elapsed_seconds": elapsed, "tracemalloc_peak_bytes": peak,
            "timing_scope": "One generate_candidates invocation with tracemalloc enabled; excludes corpus creation and scoring. Python allocations, not process RSS.",
            "metrics": score_candidates(corpus, candidates)}


def run_evaluation() -> dict:
    root = Path(__file__).resolve().parents[1]
    fixtures = root / "tests/fixtures/onboarding"
    corpora = {
        "investigation": load_labeled_fixture(fixtures / "reconciliation_investigation.json"),
        "challenge": load_labeled_fixture(fixtures / "reconciliation_challenge.json"),
        "heldout": load_labeled_fixture(fixtures / "reconciliation_heldout.json"),
        "generated_seed42": build_corpus(seed=42),
        "generated_seed99": build_corpus(seed=99),
    }
    return {"synthetic": True, "python_version": platform.python_version(),
            "platform": platform.platform(), "machine": platform.machine(),
            "limitations": [
                "Synthetic results do not establish production accuracy or reviewed-link accuracy.",
                "Hand-authored fixtures are partially labeled; unlabeled pairs are unassessed and precision is null.",
                "Seed 99 permutes source-local retained references only; it is a determinism check, not an independent difficulty distribution or held-out clinical population.",
                "Eligible candidates require human review; eligibility is not identity certification.",
            ],
            "evaluations": {name: evaluate(corpus) for name, corpus in corpora.items()}}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", required=True, type=Path, help="New JSON file; existing outputs rejected before evaluation")
    args = parser.parse_args()
    # Exclusive open precedes work so existing evidence is never replaced.
    with args.output.open("x") as output:
        result = run_evaluation()
        json.dump(result, output, indent=2)
        output.write("\n")
    print(json.dumps({name: {key: result["evaluations"][name][key] for key in
                            ("record_count", "candidate_count", "eligible_candidate_count", "elapsed_seconds", "tracemalloc_peak_bytes")}
                      for name in result["evaluations"]}, indent=2))


if __name__ == "__main__":
    main()
