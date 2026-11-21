"""The installed CLI defaults must work independently of checkout paths."""
from pathlib import Path
import sys

import pandas as pd

from provider_directory_truth_layer.cli import main


def test_default_qa_ignores_current_directory_fixture_names(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    # Local lookalikes must not silently replace the versioned synthetic defaults.
    (tmp_path / 'data/raw').mkdir(parents=True)
    (tmp_path / 'data/raw/sample_provider_directory.csv').write_text('broken local file')
    (tmp_path / 'config').mkdir()
    (tmp_path / 'config/qa_rules.yml').write_text('broken local rules')
    monkeypatch.setattr(sys, 'argv', ['provider-truth-layer', 'run', '--output-dir', str(tmp_path/'qa'),
        '--sqlite', str(tmp_path/'qa.sqlite3'), '--as-of', '2026-06-01'])
    main()
    report = pd.read_csv(tmp_path/'qa/quality_summary.csv')
    assert dict(zip(report.metric, report.value))['total_records'] == 12


def test_explicit_qa_input_and_rules_remain_overrides(tmp_path, monkeypatch):
    source = Path(__file__).parent.parent
    raw = (source/'data/raw/sample_provider_directory.csv').read_text().splitlines()
    chosen = tmp_path/'chosen.csv'; chosen.write_text('\n'.join(raw[:2])+'\n')
    config = tmp_path/'chosen.yml'; config.write_bytes((source/'config/qa_rules.yml').read_bytes())
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(sys, 'argv', ['provider-truth-layer','run','--input',str(chosen),'--config',str(config),
        '--output-dir',str(tmp_path/'qa'),'--sqlite',str(tmp_path/'qa.sqlite3'),'--as-of','2026-06-01'])
    main()
    report = pd.read_csv(tmp_path/'qa/quality_summary.csv')
    assert dict(zip(report.metric,report.value))['total_records'] == 1
