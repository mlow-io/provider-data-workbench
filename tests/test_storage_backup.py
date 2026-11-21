"""Backup/restore contracts use fresh synthetic roots and never modify their source."""

import hashlib
import json
from contextlib import closing
from pathlib import Path
import shutil
import sqlite3
import subprocess
import sys

import pytest

from provider_directory_truth_layer.intake_store import IntakeStore, VERSION
from provider_directory_truth_layer.operations_sql import run
from provider_directory_truth_layer import storage_backup


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


@pytest.fixture
def source(tmp_path):
    root = tmp_path / 'source'
    root.mkdir()
    store = IntakeStore(root / 'directory.sqlite3', root)
    data = (b'record_id,npi,provider_name,address,city,state,zip,phone,location_id,reference_phone\n'
            b'SYN-1,1000000001,Synthetic Clinician,10 Example St,Example,MA,02108,6175550100,NORTH,6175550199\n')
    receipt = store.receive(data, 'clinic.csv', source='synthetic-backup', designation='synthetic')
    accepted = store.commit(receipt['id'], {'actor': 'reviewer', 'reason': 'synthetic fixture', 'policy': 'valid_rows'})
    case_id = accepted['linked_cases'][0]['id']
    store.event(case_id, {'action': 'assign', 'actor': 'reviewer', 'reason': 'follow up',
                          'owner': 'analyst', 'follow_up': '2026-01-31', 'expected_version': 0})
    # Unregistered and staged files are preserved, not silently discarded.
    (store.artifacts / 'orphan').write_bytes(b'unregistered evidence')
    (store.artifacts / 'partial.staged').write_bytes(b'interrupted write')
    return root, case_id


def test_backup_restore_preserves_evidence_and_all_artifacts(source, tmp_path):
    root, case_id = source
    before_db = digest(root / 'directory.sqlite3')
    before_files = {p.name: digest(p) for p in (root / 'artifacts').iterdir()}
    original_report = run(root / 'directory.sqlite3', 'phone-review', as_of='2026-02-01')
    original_lineage = run(root / 'directory.sqlite3', 'lineage', case_id=case_id)
    archive, restored = tmp_path / 'archive', tmp_path / 'restored'
    manifest = storage_backup.backup(root, archive)
    assert manifest['registered_artifacts'] == 1
    assert len(manifest['artifacts']) == 3
    assert archive.stat().st_mode & 0o077 == 0
    assert (archive / 'artifacts').stat().st_mode & 0o077 == 0
    assert storage_backup.restore(archive, restored) == manifest
    assert restored.stat().st_mode & 0o077 == 0
    assert run(restored / 'directory.sqlite3', 'phone-review', as_of='2026-02-01') == original_report
    assert run(restored / 'directory.sqlite3', 'lineage', case_id=case_id) == original_lineage
    assert {p.name: digest(p) for p in (restored / 'artifacts').iterdir()} == before_files
    assert digest(root / 'directory.sqlite3') == before_db
    assert {p.name: digest(p) for p in (root / 'artifacts').iterdir()} == before_files
    reopened = IntakeStore(restored / 'directory.sqlite3', restored)
    assert reopened.case(case_id)['owner'] == 'analyst'
    recovery = json.loads((restored / 'artifact-recovery.json').read_text())
    assert recovery['staged'] == ['partial.staged'] and recovery['unregistered'] == ['orphan']


def test_missing_or_changed_registered_artifact_blocks_backup(source, tmp_path):
    root, _ = source
    with sqlite3.connect(root / 'directory.sqlite3') as conn:
        key = conn.execute('SELECT storage_key FROM artifact').fetchone()[0]
    artifact = root / 'artifacts' / key
    original = artifact.read_bytes()
    artifact.unlink()
    with pytest.raises(ValueError, match='missing or does not match'):
        storage_backup.backup(root, tmp_path / 'missing')
    assert not (tmp_path / 'missing').exists()
    artifact.write_bytes(original + b'changed')
    with pytest.raises(ValueError, match='missing or does not match'):
        storage_backup.backup(root, tmp_path / 'changed')
    assert not (tmp_path / 'changed').exists()


def test_changed_backup_is_rejected_before_restore(source, tmp_path):
    root, _ = source
    archive, restored = tmp_path / 'archive', tmp_path / 'restored'
    storage_backup.backup(root, archive)
    (archive / 'artifacts' / 'orphan').write_text('changed after backup')
    with pytest.raises(ValueError, match='inventory or digest mismatch'):
        storage_backup.restore(archive, restored)
    assert not restored.exists()
    assert (root / 'artifacts' / 'orphan').read_bytes() == b'unregistered evidence'


def test_verify_cli_is_read_only_and_detects_changed_artifact(source, tmp_path, capsys):
    root, _ = source
    archive = tmp_path / 'archive'
    storage_backup.backup(root, archive)
    before = {str(p.relative_to(archive)): digest(p) for p in archive.rglob('*') if p.is_file()}
    assert storage_backup.main(['verify', '--backup-root', str(archive)]) == 0
    result = json.loads(capsys.readouterr().out)
    assert result['result'] == 'verify'
    assert result['backup_root'] == str(archive)
    assert result['registered_artifacts'] == 1 and result['artifact_files'] == 3
    assert 'do not authenticate' in result['notice']
    assert {str(p.relative_to(archive)): digest(p) for p in archive.rglob('*') if p.is_file()} == before
    (archive / 'artifacts' / 'orphan').write_bytes(b'changed')
    with pytest.raises(SystemExit) as error:
        storage_backup.main(['verify', '--backup-root', str(archive)])
    assert error.value.code == 2
    assert 'inventory or digest mismatch' in capsys.readouterr().err
    assert not (tmp_path / 'restored').exists()


def test_verify_rejects_symlinked_root_and_unresolved_wal(source, tmp_path):
    root, _ = source
    archive = tmp_path / 'archive'
    storage_backup.backup(root, archive)
    linked = tmp_path / 'linked'
    linked.symlink_to(archive, target_is_directory=True)
    with pytest.raises(ValueError, match='not a symlink'):
        storage_backup.verify(linked)
    wal = archive / 'directory.sqlite3-wal'
    wal.write_bytes(b'unresolved synthetic wal')
    with pytest.raises(ValueError, match='WAL'):
        storage_backup.verify(archive)
    assert wal.read_bytes() == b'unresolved synthetic wal'


def test_database_integrity_is_checked_even_if_manifest_hash_is_rewritten(source, tmp_path):
    root, _ = source
    archive = tmp_path / 'archive'
    storage_backup.backup(root, archive)
    db = archive / 'directory.sqlite3'
    with db.open('r+b') as stream:
        stream.write(b'not a database!!')
    manifest_path = archive / 'manifest.json'
    manifest = json.loads(manifest_path.read_text())
    manifest['database_sha256'] = digest(db)
    manifest_path.write_text(json.dumps(manifest))
    with pytest.raises(sqlite3.DatabaseError):
        storage_backup.restore(archive, tmp_path / 'restored')
    assert not (tmp_path / 'restored').exists()


def test_broken_foreign_keys_block_backup_before_destination_creation(source, tmp_path):
    root, _ = source
    with closing(sqlite3.connect(root / 'directory.sqlite3')) as conn:
        conn.execute('PRAGMA foreign_keys=OFF')
        conn.execute("INSERT INTO work_evidence VALUES ('absent-case','absent-observation')")
        conn.commit()
    with pytest.raises(ValueError, match='foreign-key check failed'):
        storage_backup.backup(root, tmp_path / 'archive')
    assert not (tmp_path / 'archive').exists()


def test_existing_nested_and_symlink_destinations_are_never_overwritten(source, tmp_path):
    root, _ = source
    existing = tmp_path / 'existing'
    existing.mkdir()
    (existing / 'sentinel').write_text('keep')
    with pytest.raises(ValueError, match='new directory'):
        storage_backup.backup(root, existing)
    with pytest.raises(ValueError, match='disjoint'):
        storage_backup.backup(root, root / 'nested')
    dangling = tmp_path / 'dangling'
    dangling.symlink_to(tmp_path / 'absent')
    with pytest.raises(ValueError, match='new directory'):
        storage_backup.backup(root, dangling)
    assert (existing / 'sentinel').read_text() == 'keep'


def test_nonempty_wal_blocks_backup_without_checkpointing(source, tmp_path):
    root, _ = source
    db = root / 'directory.sqlite3'
    with sqlite3.connect(db) as writer:
        writer.execute('PRAGMA journal_mode=WAL')
        writer.execute("CREATE TABLE synthetic_live_writer (id INTEGER)")
        writer.commit()
        wal = Path(str(db) + '-wal')
        assert wal.stat().st_size > 0
        before = digest(wal)
        with pytest.raises(ValueError, match='WAL'):
            storage_backup.backup(root, tmp_path / 'archive')
        assert digest(wal) == before
        assert not (tmp_path / 'archive').exists()


def test_nonempty_rollback_journal_blocks_backup_without_touching_it(source, tmp_path):
    root, _ = source
    journal = root / 'directory.sqlite3-journal'
    journal.write_bytes(b'synthetic unresolved journal')
    with pytest.raises(ValueError, match='rollback journal'):
        storage_backup.backup(root, tmp_path / 'archive')
    assert journal.read_bytes() == b'synthetic unresolved journal'
    assert not (tmp_path / 'archive').exists()


def test_stopped_crash_wal_can_be_recovered_on_a_copy_before_backup(source, tmp_path):
    root, _ = source
    db = root / 'directory.sqlite3'
    code = """import os,sqlite3,sys
c=sqlite3.connect(sys.argv[1]); c.execute('PRAGMA journal_mode=WAL')
c.execute('CREATE TABLE synthetic_crash_receipt (id INTEGER)')
c.execute('INSERT INTO synthetic_crash_receipt VALUES (41)'); c.commit(); os._exit(0)
"""
    subprocess.run([sys.executable, '-c', code, str(db)], check=True, timeout=60)
    wal = Path(str(db) + '-wal')
    assert wal.stat().st_size > 0
    original_hashes = {p.name: digest(p) for p in (db, wal)}
    with pytest.raises(ValueError, match='WAL'):
        storage_backup.backup(root, tmp_path / 'archive')
    # The writer is stopped; replay and checkpoint only a separate owned copy.
    staged = tmp_path / 'staged'
    shutil.copytree(root, staged)
    with closing(sqlite3.connect(staged / 'directory.sqlite3')) as conn:
        assert conn.execute('SELECT id FROM synthetic_crash_receipt').fetchone()[0] == 41
        assert conn.execute('PRAGMA wal_checkpoint(TRUNCATE)').fetchone()[0] == 0
    archive = tmp_path / 'archive'
    storage_backup.backup(staged, archive)
    restored = tmp_path / 'restored'
    storage_backup.restore(archive, restored)
    with closing(sqlite3.connect(restored / 'directory.sqlite3')) as conn:
        assert conn.execute('SELECT id FROM synthetic_crash_receipt').fetchone()[0] == 41
    assert {p.name: digest(p) for p in (db, wal)} == original_hashes


def test_change_during_copy_leaves_unrestorable_target_and_source_untouched(source, tmp_path, monkeypatch):
    root, _ = source
    copy = storage_backup._copy_artifacts
    def concurrent_change(source_dir, destination_dir, artifacts):
        copy(source_dir, destination_dir, artifacts)
        (source_dir / 'new-orphan').write_bytes(b'concurrent test writer')
    monkeypatch.setattr(storage_backup, '_copy_artifacts', concurrent_change)
    archive = tmp_path / 'partial'
    with pytest.raises(ValueError, match='Source changed during backup'):
        storage_backup.backup(root, archive)
    assert archive.is_dir() and not (archive / 'manifest.json').exists()
    with pytest.raises(ValueError, match='regular file'):
        storage_backup.restore(archive, tmp_path / 'restored')
    assert (root / 'artifacts' / 'new-orphan').read_bytes() == b'concurrent test writer'


def test_external_database_and_symlinked_artifact_are_handled_safely(source, tmp_path):
    root, _ = source
    external = tmp_path / 'selected.sqlite3'
    (root / 'directory.sqlite3').rename(external)
    archive = tmp_path / 'archive'
    storage_backup.backup(root, archive, database=external)
    assert storage_backup.restore(archive, tmp_path / 'restored')['registered_artifacts'] == 1
    (root / 'artifacts' / 'link').symlink_to(root / 'artifacts' / 'orphan')
    with pytest.raises(ValueError, match='not a symlink'):
        storage_backup.backup(root, tmp_path / 'linked', database=external)


@pytest.mark.parametrize('legacy_version', [11, 12])
def test_prior_archive_can_be_verified_and_restored_before_additive_upgrade(source,tmp_path,legacy_version):
    root,_=source
    archive=tmp_path/f'schema{legacy_version}-archive'
    manifest=storage_backup.backup(root,archive)
    # Reconstruct the previous supported, stopped archive format in owned fixtures.
    with sqlite3.connect(archive/'directory.sqlite3') as db:
        from schema_helpers import remove_assistant_schema
        remove_assistant_schema(db)
        if legacy_version == 11:
            db.execute('DROP TABLE fhir_acquisition_event');db.execute('DROP TABLE fhir_acquisition')
            db.execute('DELETE FROM schema_migration WHERE version=12')
        db.execute(f'PRAGMA user_version={legacy_version}')
    db.close()  # sqlite's transaction context does not close/checkpoint the connection.
    manifest['schema_version']=legacy_version
    manifest['database_sha256']=digest(archive/'directory.sqlite3')
    (archive/'manifest.json').write_text(json.dumps(manifest))
    before={p.name:digest(p) for p in archive.iterdir() if p.is_file()}
    assert storage_backup.verify(archive)['schema_version']==legacy_version
    destination=tmp_path/f'restored-schema{legacy_version}'
    assert storage_backup.restore(archive,destination)['schema_version']==legacy_version
    assert {p.name:digest(p) for p in archive.iterdir() if p.is_file()}==before
    reopened=IntakeStore(destination/'directory.sqlite3',destination)
    with reopened.db() as db:
        assert db.execute('PRAGMA user_version').fetchone()[0]==VERSION
        assert db.execute('PRAGMA integrity_check').fetchone()[0]=='ok'
    assert (destination/'directory.sqlite3.pre-intake-v13.bak').exists()
