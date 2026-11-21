"""Evaluation arithmetic and label scope, independent of matcher quality."""
from copy import deepcopy
import importlib.util
import json
from pathlib import Path
import subprocess
import sys

import pytest

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("evaluate_reconciliation", ROOT / "scripts/evaluate_reconciliation.py")
evaluation = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(evaluation)


def record(row, path="addresses[0]", kind="practice"):
    return {"ref": row + "@" + path, "clinician_ref": row,
            "source": row.split(":")[0], "entity_kind": "clinician",
            "address": {"path": path, "kind": kind}}


def candidate(a, b, eligible=False, kind="clinician"):
    return {"kind": kind, "left": a, "right": b, "eligible": eligible}


def tiny_corpus(exhaustive=False):
    rows = [record("clinic:a"), record("payer:b"), record("reference:c"), record("payer:d")]
    metadata = {"expected_clinician_nonlinks": [{"records": ["clinic:a", "payer:d"], "scope": "clinician"}],
                "expected_unresolved": [{"records": ["payer:b", "reference:c"], "scope": "clinician"}]}
    if exhaustive:
        metadata = {"positive_label_scope": "Exhaustive cross-source synthetic truth",
                    "clinician_truth": {r["clinician_ref"]: "same" if r["clinician_ref"] in
                                        ("clinic:a", "payer:b") else r["clinician_ref"] for r in rows},
                    "location_truth": {r["ref"]: r["ref"] for r in rows}}
    return {"records": rows, "expected_clinician_pairs": [["clinic:a", "payer:b"]],
            "expected_location_pairs": [], "metadata": metadata}


def test_partial_metrics_keep_known_nonlinks_unresolved_and_unassessed_separate():
    corpus = tiny_corpus()
    candidates = [candidate("clinic:a", "payer:b", True),
                  candidate("clinic:a", "payer:d", True),
                  candidate("payer:b", "reference:c"),
                  candidate("clinic:a", "reference:c", True)]
    originals = deepcopy((corpus, candidates))
    result = evaluation.score_candidates(corpus, candidates)["clinician"]
    all_metrics, eligible = result["all_candidates"], result["eligible_candidates"]
    assert result["truth_scope"] == "partial_authored"
    assert all_metrics["candidate_count"] == 4
    assert all_metrics["proposed_true_links"] == 1
    assert all_metrics["positive_pair_recall"] == 1
    assert all_metrics["missed_true_links"] == 0
    assert all_metrics["known_nonlink_candidates"] == 1
    assert all_metrics["unresolved_candidates"] == 1
    assert all_metrics["unassessed_candidates"] == 1
    assert all_metrics["incorrect_proposals"] == 1
    assert all_metrics["candidate_precision"] is None
    assert eligible["candidate_count"] == 3
    assert eligible["unresolved_candidates"] == 0
    assert eligible["unassessed_candidates"] == 1
    assert eligible["candidate_precision"] is None
    assert (corpus, candidates) == originals


def test_exhaustive_math_and_eligible_recall_are_distinct():
    result = evaluation.score_candidates(tiny_corpus(True), [
        candidate("clinic:a", "payer:b"),
        candidate("clinic:a", "reference:c", True),
    ])["clinician"]
    assert result["truth_scope"] == "exhaustive_generated"
    assert result["all_candidates"]["candidate_precision"] == 0.5
    assert result["all_candidates"]["positive_pair_recall"] == 1
    assert result["all_candidates"]["incorrect_proposals"] == 1
    assert result["eligible_candidates"]["candidate_precision"] == 0
    assert result["eligible_candidates"]["positive_pair_recall"] == 0
    assert result["eligible_candidates"]["missed_pairs"] == [["clinic:a", "payer:b"]]


def test_incomplete_latent_map_does_not_authorize_precision():
    corpus = tiny_corpus(True)
    del corpus["metadata"]["clinician_truth"]["payer:d"]
    result = evaluation.score_candidates(corpus, [candidate("clinic:a", "reference:c", True)])
    assert result["clinician"]["truth_scope"] == "partial_authored"
    assert result["clinician"]["all_candidates"]["candidate_precision"] is None
    assert result["clinician"]["all_candidates"]["unassessed_candidates"] == 1


def test_location_nonlink_honors_explicit_mailing_path_only():
    corpus = {"records": [record("clinic:a"), record("reference:b"),
                          record("reference:b", "addresses[1]", "mailing")],
              "expected_clinician_pairs": [], "expected_location_pairs": [],
              "metadata": {"expected_location_nonlinks": [
                  {"records": ["clinic:a", "reference:b"], "scope": "operating_location",
                   "address_selection": {"record": "reference:b", "address_path": "addresses[1]"}}]}}
    candidates = [candidate("clinic:a@addresses[0]", "reference:b@addresses[0]", True, "location"),
                  candidate("clinic:a@addresses[0]", "reference:b@addresses[1]", False, "location")]
    result = evaluation.score_candidates(corpus, candidates)["location"]["all_candidates"]
    assert result["known_nonlink_candidates"] == 1
    assert result["unassessed_candidates"] == 1
    assert result["nonpositive_pairs"][0]["classification"] == "unassessed"
    del corpus["metadata"]["expected_location_nonlinks"][0]["address_selection"]
    ambiguous = evaluation.score_candidates(corpus, candidates)["location"]["all_candidates"]
    assert ambiguous["known_nonlink_candidates"] == 0
    assert ambiguous["unassessed_candidates"] == 2


def test_conflicting_labels_and_duplicate_candidate_pairs_are_rejected():
    corpus = tiny_corpus()
    with pytest.raises(ValueError, match="Duplicate"):
        evaluation.score_candidates(corpus, [candidate("clinic:a", "payer:b"), candidate("payer:b", "clinic:a")])
    corpus["expected_clinician_pairs"].append(["clinic:a", "payer:d"])
    with pytest.raises(ValueError, match="Contradictory"):
        evaluation.score_candidates(corpus, [])


def test_cli_refuses_existing_output_without_mutation(tmp_path):
    output = tmp_path / "existing.json"
    output.write_text("preserved evidence\n")
    command = [sys.executable, str(ROOT / "scripts/evaluate_reconciliation.py"), "--output", str(output)]
    result = subprocess.run(command, capture_output=True, text=True)
    assert result.returncode != 0
    assert "FileExistsError" in result.stderr
    assert output.read_text() == "preserved evidence\n"


def test_evaluate_retains_inputs_and_reports_cost_and_digest():
    corpus = evaluation.build_corpus(entities=10)
    original = deepcopy(corpus)
    result = evaluation.evaluate(corpus)
    assert corpus == original
    assert result["record_count"] == len(corpus["records"])
    assert result["candidate_count"] >= result["eligible_candidate_count"]
    assert result["tracemalloc_peak_bytes"] > 0
    assert result["elapsed_seconds"] >= 0
    assert len(result["corpus_sha256"]) == 64
    assert result["rule_version"] == evaluation.RULE_VERSION
    assert result["metrics"]["clinician"]["truth_scope"] == "exhaustive_generated"
