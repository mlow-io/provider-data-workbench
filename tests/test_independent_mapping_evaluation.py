"""The replay reviewer must not approve field bindings outside its frozen key."""
import importlib.util
import json
from pathlib import Path
import shutil

import pytest


def test_unscored_supported_field_cannot_enter_synthetic_review(tmp_path, monkeypatch):
    script = Path(__file__).resolve().parents[1] / 'scripts/evaluation/independent/run.py'
    spec = importlib.util.spec_from_file_location('independent_mapping_evaluation', script)
    evaluation = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(evaluation)
    fixtures = tmp_path / 'challenge'
    fixtures.mkdir()
    for name in ('cases.json', 'expected.json', 'proposals.json'):
        shutil.copyfile(script.parent / name, fixtures / name)
    proposals = json.loads((fixtures / 'proposals.json').read_bytes())
    # This is a valid canonical application field and a distinct supplied column,
    # but the nine-field challenge never evaluated this extra assertion.
    proposals['proposals']['extra_roles']['mapping']['reference_phone'] = 'Fax'
    (fixtures / 'proposals.json').write_text(json.dumps(proposals))
    monkeypatch.setattr(evaluation, 'HERE', fixtures)
    root = tmp_path / 'replay'
    with pytest.raises(AssertionError, match='undeclared target fields'):
        evaluation.run(root)
    assert not root.exists()  # No receipt, proposal or approval was produced.
