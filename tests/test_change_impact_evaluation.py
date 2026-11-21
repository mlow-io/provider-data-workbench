"""Independent impact arithmetic and real reviewed-link fixture rehearsals."""
from copy import deepcopy
import importlib.util
import json
from pathlib import Path
import subprocess
import sys

import pytest

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("evaluate_change_impact", ROOT / "scripts/evaluate_change_impact.py")
evaluation = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(evaluation)


def tiny_case():
    return {"assessed_records": ["a", "b", "c", "d"],
            "expected_targets": [{"record": "a"}, {"record": "b"}],
            "expected_unaffected": [{"record": "c"}],
            "expected_not_assessed": [{"record": "d"}],
            "expected_counts": {"affected": 2, "unaffected_within_assessed_scope": 1, "not_assessed": 1}}


def test_metric_math_only_uses_declared_scope_and_keeps_missing_evidence_visible():
    case = tiny_case()
    actual = {"a": "affected", "b": "not_assessed", "c": "affected", "outside": "affected"}
    before = deepcopy((case, actual))
    result = evaluation.score_impact(case, actual)
    assert result["target_precision_within_declared_scope"] == 0.5
    assert result["target_recall_within_declared_scope"] == 0.5
    assert result["true_positive_targets"] == ["a"]
    assert result["incorrect_targets"] == ["c"]
    assert result["missed_targets"] == ["b"]
    assert result["unassessed_coverage_within_declared_scope"] == 0.25
    assert result["missing_records"] == ["d"]
    assert result["outside_declared_scope"] == {"outside": "affected"}
    assert len(result["mismatches"]) == 3
    assert (case, actual) == before


def test_metric_labels_must_partition_declared_scope():
    case = tiny_case()
    case["expected_not_assessed"].append({"record": "a"})
    with pytest.raises(ValueError, match="Overlapping"):
        evaluation.score_impact(case, {})
    case = tiny_case()
    case["assessed_records"].append("unlabeled")
    with pytest.raises(ValueError, match="partition"):
        evaluation.score_impact(case, {})


@pytest.mark.parametrize("fixture_name,expected_counts", [
    ("challenge", {"affected": 2, "unaffected_within_assessed_scope": 2, "not_assessed": 5}),
    ("heldout", {"affected": 2, "unaffected_within_assessed_scope": 1, "not_assessed": 2}),
])
def test_frozen_case_over_explicit_reviews_matches_declared_scope_without_writes(tmp_path, fixture_name, expected_counts):
    path = ROOT / f"tests/fixtures/onboarding/reconciliation_{fixture_name}.json"
    original = path.read_bytes()
    root = tmp_path / fixture_name
    result = evaluation.evaluate_fixture(root, path)
    assert result["counts"] == expected_counts
    assert result["metrics"]["actual_counts_within_declared_scope"] == expected_counts
    assert result["metrics"]["target_precision_within_declared_scope"] == 1
    assert result["metrics"]["target_recall_within_declared_scope"] == 1
    assert result["metrics"]["mismatches"] == []
    assert result["metrics"]["outside_declared_scope"] == {}
    assert result["target_network_mismatches"] == []
    assert result["anchor_old_value_matches_label"]
    assert result["preview_database_unchanged"] and result["fixture_unchanged"]
    assert result["accepted_observations"] == result["work_events"] == 0
    assert result["inputs_fresh"]
    assert all(t["address_path"] == "" and t["network_id"] and t["network_label"] for t in result["target_evidence"])
    assert path.read_bytes() == original
    before = (root / "directory.sqlite3").read_bytes()
    with pytest.raises(FileExistsError):
        evaluation.evaluate_fixture(root, path)
    assert (root / "directory.sqlite3").read_bytes() == before


def test_cli_refuses_existing_output_before_creating_runtime(tmp_path):
    output = tmp_path / "evidence.json"
    output.write_text("preserve prior evidence\n")
    runtime = tmp_path / "new-runtime"
    result = subprocess.run([sys.executable, str(ROOT / "scripts/evaluate_change_impact.py"),
                             "--output", str(output), "--root", str(runtime)], capture_output=True, text=True)
    assert result.returncode != 0
    assert "FileExistsError" in result.stderr
    assert output.read_text() == "preserve prior evidence\n"
    assert not runtime.exists()
