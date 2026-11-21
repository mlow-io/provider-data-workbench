"""Verify independent fixture structure and truth, without running any matcher."""
import importlib.util
import hashlib
from itertools import combinations
import json
from pathlib import Path
import subprocess
import sys

import pytest

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("reconciliation_corpus", ROOT / "scripts/reconciliation_corpus.py")
corpus_module = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(corpus_module)


def test_deterministic_seed_and_declared_size():
    corpus = corpus_module.build_corpus()
    assert corpus == corpus_module.build_corpus()
    assert corpus != corpus_module.build_corpus(seed=43)
    assert len(corpus["records"]) == corpus["metadata"]["record_count"] == 1005
    assert {r["source"] for r in corpus["records"]} == {"clinic", "payer", "reference"}
    assert corpus["metadata"]["synthetic"] is True
    # Source-local row labels change with the seed, but truth counts do not.
    other = corpus_module.build_corpus(seed=43)
    assert len(corpus["expected_clinician_pairs"]) == len(other["expected_clinician_pairs"])
    assert len(corpus["expected_location_pairs"]) == len(other["expected_location_pairs"])


def test_frozen_manifest_matches_default_corpus():
    manifest = json.loads((ROOT / "tests/fixtures/onboarding/corpus_manifest.json").read_text())
    corpus = corpus_module.build_corpus(seed=manifest["seed"], entities=manifest["entities"])
    encoded = json.dumps(corpus, sort_keys=True, separators=(",", ":")).encode()
    assert hashlib.sha256(encoded).hexdigest() == manifest["canonical_json_sha256"]
    assert len(corpus["records"]) == manifest["record_count"]
    assert len(corpus["expected_clinician_pairs"]) == manifest["expected_clinician_pair_count"]
    assert len(corpus["expected_location_pairs"]) == manifest["expected_location_pair_count"]


@pytest.mark.parametrize("entities", [0, -1, 1.5, True])
def test_invalid_entity_count(entities):
    with pytest.raises(ValueError, match="positive integer"):
        corpus_module.build_corpus(entities=entities)


def test_truth_is_unique_cross_source_complete_and_references_retained_rows():
    corpus = corpus_module.build_corpus()
    records = corpus["records"]
    assert len({r["ref"] for r in records}) == len(records)
    for pair_key, truth_key, ref_key in [
        ("expected_clinician_pairs", "clinician_truth", "clinician_ref"),
        ("expected_location_pairs", "location_truth", "ref"),
    ]:
        sources = {r[ref_key]: r["source"] for r in records}
        truth = corpus["metadata"][truth_key]
        expected = {tuple(sorted((a, b))) for a, b in combinations(truth, 2)
                    if truth[a] == truth[b] and sources[a] != sources[b]}
        actual = [tuple(pair) for pair in corpus[pair_key]]
        assert actual == sorted(set(actual))
        assert set(actual) == expected
        assert all(a in sources and b in sources and a != b for a, b in actual)
    # Multi-address source rows contribute only once to clinician pair truth.
    assert len({r["clinician_ref"] for r in records}) < len(records)


def test_shared_office_does_not_imply_clinician_and_suites_remain_separate():
    corpus = corpus_module.build_corpus(entities=40)
    records = {r["ref"]: r for r in corpus["records"]}
    identities = corpus["metadata"]["clinician_truth"]
    assert any(identities.get(records[a]["clinician_ref"]) != identities.get(records[b]["clinician_ref"])
               for a, b in corpus["expected_location_pairs"]
               if records[a]["entity_kind"] == records[b]["entity_kind"] == "clinician")
    location_truth = corpus["metadata"]["location_truth"]
    clinic = [r for r in records.values() if r["source"] == "clinic"]
    assert any(a["address"]["line1"] == b["address"]["line1"] and
               a["address"]["suite"] != b["address"]["suite"] and
               location_truth[a["ref"]] != location_truth[b["ref"]]
               for a, b in combinations(clinic, 2))
    assert any(identities.get(records[a]["clinician_ref"]) == identities.get(records[b]["clinician_ref"])
               and location_truth[a] != location_truth[b]
               for a, b in combinations(records, 2)
               if a in location_truth and b in location_truth and
               records[a]["clinician_ref"] in identities and records[b]["clinician_ref"] in identities)


def test_missing_ids_are_retained_and_mailing_has_no_location_truth():
    corpus = corpus_module.build_corpus(entities=40)
    records = corpus["records"]
    absent = [r for r in records if r["native_id"] is None]
    assert absent and any(r["npi"] is None for r in absent)
    assert len({r["ref"] for r in absent}) == len(absent)
    assert all(r["native_id"] is None for r in absent)  # Ref labels never fill ID fields.
    mailing = [r for r in records if r["address"]["kind"] == "mailing"]
    assert mailing
    truth = corpus["metadata"]["location_truth"]
    assert all(r["ref"] not in truth for r in mailing)
    assert all(r["entity_kind"] == "clinician" for r in records
               if r["clinician_ref"] in corpus["metadata"]["clinician_truth"])
    assert any(r["entity_kind"] == "organization" for r in records)
    assert any(r["entity_kind"] == "unknown" for r in records)


@pytest.mark.parametrize("fixture_name", ["reconciliation_challenge", "reconciliation_heldout"])
def test_adapter_retains_all_addresses_native_ids_and_authored_selections(fixture_name):
    path = ROOT / "tests/fixtures/onboarding" / f"{fixture_name}.json"
    original = path.read_bytes()
    fixture = json.loads(original)
    corpus = corpus_module.load_labeled_fixture(path)
    rows = {row["record_id"]: row for rows in fixture["sources"].values() for row in rows}
    assert len(corpus["records"]) == sum(len(row["native_addresses"]) for row in rows.values())
    refs = {r["ref"]: r for r in corpus["records"]}
    assert len(refs) == len(corpus["records"])
    for record in refs.values():
        original_row = rows[record["clinician_ref"]]
        assert record["native_id"] == original_row.get("source_native_id")
        assert record["address"] in [
            {field: address.get(field) for field in record["address"]}
            for address in original_row["native_addresses"]
        ]
    for row_ref, row in rows.items():
        selected = row["selected_address"]
        expected = corpus_module.address_ref(row_ref, selected["path"]) if selected else None
        assert corpus["metadata"]["selected_address_refs"][row_ref] == expected
    for a, b in corpus["expected_location_pairs"]:
        assert refs[a]["address"]["kind"] == refs[b]["address"]["kind"] == "practice"
        assert refs[a]["source"] != refs[b]["source"]
    assert all(a in rows and b in rows for a, b in corpus["expected_clinician_pairs"])
    assert path.read_bytes() == original


def test_cli_creates_new_file_and_refuses_existing_output(tmp_path):
    output = tmp_path / "corpus.json"
    command = [sys.executable, str(ROOT / "scripts/reconciliation_corpus.py"),
               "--output", str(output), "--entities", "20", "--seed", "7"]
    first = subprocess.run(command, capture_output=True, text=True)
    assert first.returncode == 0, first.stderr
    expected = corpus_module.build_corpus(seed=7, entities=20)
    assert json.loads(output.read_text()) == expected
    original = output.read_bytes()
    second = subprocess.run(command, capture_output=True, text=True)
    assert second.returncode != 0
    assert output.read_bytes() == original
