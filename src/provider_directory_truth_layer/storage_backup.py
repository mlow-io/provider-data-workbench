"""Back up and restore a quiescent local workbench to a new, disjoint directory.

Stop all workbench services and workers before backup. The checks below detect
some concurrent changes; they cannot establish that the source is quiescent.
Neither command modifies, deletes, or replaces its source or an existing target.
"""

from __future__ import annotations

import argparse
from contextlib import closing
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import shutil
import sqlite3

from .intake_store import VERSION

FORMAT = 'pdtl-quiescent-backup-v1'


def _hash_file(path: Path) -> tuple[str, int]:
    digest = hashlib.sha256()
    size = 0
    with path.open('rb') as stream:
        while chunk := stream.read(1024 * 1024):
            size += len(chunk)
            digest.update(chunk)
    return digest.hexdigest(), size


def _regular_file(path: Path) -> None:
    if path.is_symlink() or not path.is_file():
        raise ValueError(f'Expected a regular file, not a symlink: {path}')


def _artifact_files(root: Path) -> dict[str, dict]:
    directory = root / 'artifacts'
    if directory.is_symlink() or not directory.is_dir():
        raise ValueError('The artifact directory must exist and must not be a symlink')
    files = {}
    for path in sorted(directory.iterdir()):
        _regular_file(path)
        sha, size = _hash_file(path)
        files[path.name] = {'sha256': sha, 'size': size}
    return files


def _no_wal(database: Path) -> None:
    for suffix, label in (('-wal', 'WAL'), ('-journal', 'rollback journal')):
        sidecar = database.with_name(database.name + suffix)
        if sidecar.is_symlink() or (sidecar.exists() and (not sidecar.is_file() or sidecar.stat().st_size)):
            raise ValueError(f'Close all services and resolve the source database before backup; a {label} is present')


def _inspect_database(database: Path, artifacts: dict[str, dict], expected_version: int = VERSION) -> int:
    _regular_file(database)
    with closing(sqlite3.connect(database.resolve().as_uri() + '?mode=ro&immutable=1', uri=True)) as conn:
        version = conn.execute('PRAGMA user_version').fetchone()[0]
        if version != expected_version:
            raise ValueError(f'Expected schema {expected_version}; found {version}')
        if conn.execute('PRAGMA integrity_check').fetchone()[0] != 'ok':
            raise ValueError('Database integrity check failed')
        if conn.execute('PRAGMA foreign_key_check').fetchone() is not None:
            raise ValueError('Database foreign-key check failed')
        registered = conn.execute('SELECT sha, size, storage_key FROM artifact').fetchall()
    for sha, size, key in registered:
        if not isinstance(key, str) or key in {'.', '..'} or Path(key).name != key:
            raise ValueError('Database contains an invalid artifact storage key')
        if artifacts.get(key) != {'sha256': sha, 'size': size}:
            raise ValueError(f'Registered artifact missing or does not match its digest/size: {key}')
    return len(registered)


def _destination(source: Path, destination: Path, database: Path | None = None) -> Path:
    if destination.exists() or destination.is_symlink():
        raise ValueError('Destination must be a new directory; existing paths are never overwritten')
    if not destination.parent.is_dir():
        raise ValueError('Destination parent must already exist')
    dest = destination.parent.resolve(strict=True) / destination.name
    if source == dest or source in dest.parents or dest in source.parents:
        raise ValueError('Source and destination must be disjoint')
    if database is not None and (database == dest or dest in database.parents):
        raise ValueError('Destination must not contain the source database')
    return dest


def _copy_artifacts(source: Path, destination: Path, artifacts: dict[str, dict]) -> None:
    destination.mkdir(mode=0o700)
    for name in artifacts:
        source_file = source / name
        _regular_file(source_file)
        shutil.copyfile(source_file, destination / name)


def backup(source_root: Path, destination: Path, database: Path | None = None) -> dict:
    """Create a verified backup; callers must stop all source writers first."""
    source_root, destination = Path(source_root), Path(destination)
    if source_root.is_symlink() or not source_root.is_dir():
        raise ValueError('Source root must be an existing directory, not a symlink')
    source_root = source_root.resolve(strict=True)
    database = Path(database) if database is not None else source_root / 'directory.sqlite3'
    _regular_file(database)
    database = database.resolve(strict=True)
    dest = _destination(source_root, destination, database)
    _no_wal(database)
    source_db_hash = _hash_file(database)
    before = _artifact_files(source_root)
    _inspect_database(database, before)
    dest.mkdir(mode=0o700)
    # An incomplete destination remains visible on failure and cannot be restored.
    with closing(sqlite3.connect(database.as_uri() + '?mode=ro&immutable=1', uri=True)) as source, \
            closing(sqlite3.connect(dest / 'directory.sqlite3')) as target:
        source.backup(target)
    _copy_artifacts(source_root / 'artifacts', dest / 'artifacts', before)
    _no_wal(database)
    if _hash_file(database) != source_db_hash or _artifact_files(source_root) != before:
        raise ValueError('Source changed during backup; keep the incomplete destination for inspection')
    copied = _artifact_files(dest)
    if copied != before:
        raise ValueError('Copied artifacts do not match source; backup is incomplete')
    registered_count = _inspect_database(dest / 'directory.sqlite3', copied)
    manifest = {'format': FORMAT, 'created_at': datetime.now(timezone.utc).isoformat(),
                'schema_version': VERSION, 'database_sha256': _hash_file(dest / 'directory.sqlite3')[0],
                'artifacts': copied, 'registered_artifacts': registered_count}
    (dest / 'manifest.json').write_text(json.dumps(manifest, indent=2, sort_keys=True) + '\n')
    return manifest


def _verify_backup(root: Path) -> dict:
    manifest_path = root / 'manifest.json'
    _regular_file(manifest_path)
    manifest = json.loads(manifest_path.read_text())
    if not isinstance(manifest, dict) or manifest.get('format') != FORMAT or type(manifest.get('schema_version')) is not int or manifest.get('schema_version') not in {11, 12, VERSION}:
        raise ValueError('Unsupported or incomplete backup manifest')
    database = root / 'directory.sqlite3'
    _regular_file(database)
    _no_wal(database)
    if _hash_file(database)[0] != manifest.get('database_sha256'):
        raise ValueError('Backup database digest mismatch')
    artifacts = _artifact_files(root)
    if artifacts != manifest.get('artifacts'):
        raise ValueError('Backup artifact inventory or digest mismatch')
    if _inspect_database(database, artifacts, manifest['schema_version']) != manifest.get('registered_artifacts'):
        raise ValueError('Backup registered artifact count mismatch')
    return manifest


def verify(backup_root: Path) -> dict:
    """Check a stopped backup without creating a restore or modifying its files."""
    backup_root = Path(backup_root)
    if backup_root.is_symlink() or not backup_root.is_dir():
        raise ValueError('Backup root must be an existing directory, not a symlink')
    return _verify_backup(backup_root.resolve(strict=True))


def restore(backup_root: Path, destination: Path) -> dict:
    """Verify a backup, then restore into a new, disjoint runtime root."""
    backup_root, destination = Path(backup_root), Path(destination)
    if backup_root.is_symlink() or not backup_root.is_dir():
        raise ValueError('Backup root must be an existing directory, not a symlink')
    backup_root = backup_root.resolve(strict=True)
    dest = _destination(backup_root, destination)
    manifest = _verify_backup(backup_root)
    dest.mkdir(mode=0o700)
    shutil.copyfile(backup_root / 'directory.sqlite3', dest / 'directory.sqlite3')
    _copy_artifacts(backup_root / 'artifacts', dest / 'artifacts', manifest['artifacts'])
    shutil.copyfile(backup_root / 'manifest.json', dest / 'manifest.json')
    if _verify_backup(dest) != manifest:
        raise ValueError('Restored copy did not match backup')
    return manifest


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest='command', required=True)
    create = commands.add_parser('backup', help='Back up stopped workbench storage to a new directory')
    create.add_argument('--source-root', required=True, type=Path)
    create.add_argument('--database', type=Path, help='Source database, if different from <source-root>/directory.sqlite3')
    create.add_argument('--destination', required=True, type=Path)
    recover = commands.add_parser('restore', help='Verify a backup and restore it to a new directory')
    recover.add_argument('--backup-root', required=True, type=Path)
    recover.add_argument('--destination', required=True, type=Path)
    check = commands.add_parser('verify', help='Verify a stopped backup without restoring it')
    check.add_argument('--backup-root', required=True, type=Path)
    args = parser.parse_args(argv)
    try:
        if args.command == 'backup':
            manifest = backup(args.source_root, args.destination, args.database)
        elif args.command == 'restore':
            manifest = restore(args.backup_root, args.destination)
        else:
            manifest = verify(args.backup_root)
    except (OSError, ValueError, sqlite3.Error) as error:
        parser.error(str(error))
    print(json.dumps({'result': args.command,
                      **({'backup_root': str(args.backup_root)} if args.command == 'verify'
                         else {'destination': str(args.destination)}),
                      'registered_artifacts': manifest['registered_artifacts'],
                      'artifact_files': len(manifest['artifacts']), 'schema_version': manifest['schema_version'],
                      'notice': ('Integrity checks passed; checksums do not authenticate the backup.' if args.command == 'verify'
                                 else 'Local data copied; stop all workbench services before using restored storage.')}, indent=2))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
