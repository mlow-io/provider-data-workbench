"""Reject private release inputs and personal commit metadata without printing values."""
from __future__ import annotations

import argparse
from pathlib import Path
import re
import subprocess


def check(root: Path, history: bool = False) -> list[str]:
    names = subprocess.check_output(['git', 'ls-files', '-z'], cwd=root).decode().split('\0')
    problems = []
    for name in filter(None, names):
        path = Path(name)
        if any(part in {'.handoff', '.runtime', 'private', 'chat-exports', 'publication-private', 'node_modules'} for part in path.parts):
            problems.append(f'{name}: private directory')
        if path.name.startswith('.env') and path.name != '.env.example':
            problems.append(f'{name}: environment file')
        if path.suffix in {'.sqlite', '.sqlite3', '.db', '.pem', '.p12', '.pfx'}:
            problems.append(f'{name}: private runtime or key file')
        file = root / path
        if file.is_symlink():
            problems.append(f'{name}: symlink requires explicit release review')
            continue
        try:
            text = file.read_text()
        except UnicodeError:
            continue
        if re.search('/' + r'Users/(?!<|example(?:/|$))[^/\s<>]+/', text):
            problems.append(f'{name}: personal home path')
        if re.search(r'[A-Za-z0-9._%+-]+@(?:gmail|icloud|hotmail|outlook)\.com', text, re.I):
            problems.append(f'{name}: personal email provider')
        if re.search(r'-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----', text):
            problems.append(f'{name}: private key material')
    if history:
        identities = subprocess.check_output(['git', 'log', '--all', '--format=%ae%n%ce'], cwd=root).decode().splitlines()
        for identity in set(identities):
            if identity and not identity.endswith('@users.noreply.github.com'):
                problems.append('git history: non-noreply author or committer email')
                break
    return problems


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument('--check-history', action='store_true')
    args = parser.parse_args()
    findings = check(args.root.resolve(), args.check_history)
    for finding in findings:
        print(finding)
    print(f'Release privacy checks: {len(findings)} findings')
    raise SystemExit(bool(findings))
