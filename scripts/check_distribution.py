"""Build and exercise wheel/sdist installs outside the checkout in new owned storage.

Requires the dev extra. Installs dependencies from the configured public package
index; the product rehearsal uses only synthetic data and owned loopback HTTP.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tarfile
import venv
import zipfile

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, required=True, help='New directory outside the checkout; parent must exist.')
    args = parser.parse_args()
    root = args.root.resolve()
    if args.root.exists() or args.root.is_symlink() or root.is_relative_to(ROOT):
        parser.error('Choose a new root outside the checkout; existing paths are preserved')
    root.mkdir(mode=0o700)
    environment = os.environ.copy()
    for key in ('PYTHONPATH', 'PYTHONHOME', 'VIRTUAL_ENV', 'OPENAI_API_KEY', 'PDTL_DB', 'PDTL_ROOT'):
        environment.pop(key, None)
    environment.update(PYTHONNOUSERSITE='1', PDTL_ASSISTANT_ENABLED='0', PIP_CONFIG_FILE=os.devnull,
                       PIP_DISABLE_PIP_VERSION_CHECK='1')
    commands = []

    def run(argv, name, *, cwd=root, timeout=600):
        commands.append({'argv': [str(value) for value in argv], 'cwd': str(cwd), 'log': name})
        with (root/name).open('x') as output:
            result = subprocess.run(argv, cwd=cwd, env=environment, stdout=output, stderr=subprocess.STDOUT, timeout=timeout)
        if result.returncode:
            raise RuntimeError(f'{name}: exit {result.returncode}; original evidence retained at {root}')

    try:
        run([sys.executable, '-I', str(ROOT/'scripts/sync_bundled_assets.py')], 'asset-check.txt')
        source = root/'source'
        source.mkdir()
        for name in ('pyproject.toml', 'README.md'):
            shutil.copyfile(ROOT/name, source/name)
        for license_file in ROOT.glob('LICENSE*'):
            if license_file.is_file():
                shutil.copyfile(license_file, source/license_file.name)
        shutil.copytree(ROOT/'src', source/'src', ignore=shutil.ignore_patterns('__pycache__', '*.egg-info', '.DS_Store'))
        source_hashes = {str(path.relative_to(source)): hashlib.sha256(path.read_bytes()).hexdigest()
                         for path in source.rglob('*') if path.is_file()}
        run([sys.executable, '-m', 'build', '--outdir', str(root/'dist'), '--wheel', '--sdist'], 'build.txt', cwd=source)
        distributions = sorted((root/'dist').iterdir())
        if len(distributions) != 2:
            raise RuntimeError('Expected exactly one wheel and one sdist')
        artifacts = []
        asset_root = ROOT/'src/provider_directory_truth_layer/assets'
        expected_assets = {str(path.relative_to(asset_root)): hashlib.sha256(path.read_bytes()).hexdigest()
                           for path in asset_root.rglob('*') if path.is_file()}
        for distribution in distributions:
            marker = 'provider_directory_truth_layer/assets/'
            if distribution.suffix == '.whl':
                with zipfile.ZipFile(distribution) as archive:
                    bundled = {name.split(marker, 1)[1]: hashlib.sha256(archive.read(name)).hexdigest()
                               for name in archive.namelist() if marker in name and not name.endswith('/')}
            else:
                with tarfile.open(distribution) as archive:
                    bundled = {member.name.split(marker, 1)[1]: hashlib.sha256(archive.extractfile(member).read()).hexdigest()
                               for member in archive.getmembers() if member.isfile() and marker in member.name}
            if bundled != expected_assets:
                raise RuntimeError(f'{distribution.name} assets differ from the checked authoritative copies')
            artifacts.append({'name': distribution.name, 'sha256': hashlib.sha256(distribution.read_bytes()).hexdigest(),
                              'bundled_assets': bundled})
            label = 'wheel' if distribution.suffix == '.whl' else 'sdist'
            install = root/label
            venv.EnvBuilder(with_pip=True).create(install)
            python = install/('Scripts/python.exe' if os.name == 'nt' else 'bin/python')
            # pip rebuilds the sdist in an isolated build environment before install.
            run([str(python), '-I', '-m', 'pip', 'install', '--no-input', str(distribution)], label+'-install.txt')
            run([str(python), '-I', str(ROOT/'scripts/distribution_probe.py'), str(root/(label+'-journey'))], label+'-probe.txt')
            run([str(python), '-I', '-m', 'pip', 'freeze'], label+'-dependencies.txt')
        report = {'source_files_sha256': source_hashes, 'artifacts': artifacts, 'commands': commands,
                  'probes': {label: json.loads((root/(label+'-journey/result.json')).read_bytes()) for label in ('wheel', 'sdist')},
                  'scope': 'Owned clean installations, synthetic product data, no actual model/source calls; React assets excluded'}
        (root/'result.json').write_text(json.dumps(report, indent=2)+'\n')
        print(f'Wheel and sdist installed journeys passed; retained evidence: {root}')
    finally:
        (root/'commands.json').write_text(json.dumps(commands, indent=2)+'\n')


if __name__ == '__main__':
    main()
