"""Real launcher recovery keeps owned work and immutable follow-up history."""
import importlib.util
from pathlib import Path

import pytest

from test_change_impact import prepared
from test_follow_up import acknowledgement, confirmation, proposal_and_plan
from provider_directory_truth_layer.follow_up import FollowUp
from provider_directory_truth_layer.intake_store import IntakeStore

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location('ingestion_recovery_rehearsal', ROOT / 'scripts/rehearse_ingestion_recovery.py')
recovery = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(recovery)


def test_real_launcher_copy_repeat_reinterpret_and_reopen_preserve_owned_work(prepared, tmp_path):
    store = prepared['store']
    service = FollowUp(store)
    proposal, plan = proposal_and_plan(prepared)
    saved = service.confirm(confirmation(proposal, plan))
    target = service.get(saved['id'])['targets'][0]
    store.event(target['case']['id'], {'action': 'assign', 'owner': 'Synthetic recovery owner',
                'expected_version': 0, 'actor': 'Synthetic operator', 'reason': 'Keep accountable ownership'})
    target = service.get(saved['id'])['targets'][0]
    service.acknowledge(saved['id'], acknowledgement(target))
    prior_export = b'{"prior_export":true}\n'
    (store.root / 'confirmed-plan.json').write_bytes(prior_export)
    copied = tmp_path / 'rehearsal'
    result = recovery.rehearse(store.root, copied)
    assert result['source_storage_unchanged'] and result['existing_work_and_follow_up_history_unchanged']
    assert result['separate_process_reopen_rows_exact'] and result['new_interpretation_made_saved_context_stale']
    assert result['json_xlsx_payload_equal'] and result['formulas'] == 0
    assert result['json_bytes'] > 0 and result['xlsx_bytes'] > 0
    assert result['confirmed_associations'] == 2
    assert (copied / 'confirmed-plan.json').read_bytes() == prior_export
    before = recovery.files(copied)
    with pytest.raises(RuntimeError, match='NEW destination'):
        recovery.rehearse(store.root, copied)
    assert recovery.files(copied) == before


def test_rehearsal_rejects_non_synthetic_source_before_copy(tmp_path):
    source = tmp_path / 'source'
    store = IntakeStore(source / 'directory.sqlite3', source)
    store.receive(b'[]', 'local.json', designation='local')
    destination = tmp_path / 'copy'
    before = recovery.files(source)
    with pytest.raises(RuntimeError, match='explicitly synthetic'):
        recovery.rehearse(source, destination)
    assert not destination.exists() and recovery.files(source) == before
