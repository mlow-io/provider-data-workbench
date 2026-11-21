"""The portable demo preserves retained evidence without accepting or linking it."""
import importlib.util
import json
from pathlib import Path

import pytest


def test_prepare_demo_owns_new_root_and_exports_complete_run(tmp_path, monkeypatch):
    scripts = Path(__file__).resolve().parents[1] / 'scripts'
    monkeypatch.syspath_prepend(str(scripts))
    spec = importlib.util.spec_from_file_location('prepare_reconciliation_demo', scripts / 'prepare_reconciliation_demo.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    from reconciliation_corpus import build_corpus
    from provider_directory_truth_layer.intake_store import IntakeStore
    from provider_directory_truth_layer.reconciliation_store import ReconciliationStore

    root = tmp_path / 'demo'
    manifest = module.prepare(root, build_corpus(seed=42, entities=10))
    store = IntakeStore(root / 'directory.sqlite3', root)
    service = ReconciliationStore(store)
    exported = json.loads((root / 'comparison-evidence.json').read_text())
    assert exported == service.export(manifest['run_id'])
    assert len(exported['records']) == manifest['metrics']['address_references']
    assert len(exported['candidates']) == manifest['metrics']['candidate_count']
    with store.db() as conn:
        assert conn.execute('SELECT count(*) FROM observation').fetchone()[0] == 0
        assert conn.execute('SELECT count(*) FROM work_event').fetchone()[0] == 0
    before = (root / 'comparison-evidence.json').read_bytes()
    with pytest.raises(FileExistsError):
        module.prepare(root, build_corpus(seed=42, entities=10))
    assert (root / 'comparison-evidence.json').read_bytes() == before
