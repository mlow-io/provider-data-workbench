"""Documentation link and entrypoint verification must match CI expectations."""
import importlib.util
from pathlib import Path

spec = importlib.util.spec_from_file_location(
    'check_project_docs', Path(__file__).parents[1] / 'scripts/check_project_docs.py')
checker = importlib.util.module_from_spec(spec)
spec.loader.exec_module(checker)


def project(tmp_path):
    (tmp_path / 'docs').mkdir(parents=True, exist_ok=True)
    for name in checker.ENTRYPOINTS:
        target = tmp_path / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(f'# {name}\n')
    return tmp_path


def test_deleted_heading_is_an_error_even_when_destination_file_exists(tmp_path):
    root = project(tmp_path)
    (root / 'README.md').write_text('[old plan](docs/plan.md#retired-milestone)\n')
    (root / 'docs/plan.md').write_text('# Historical entrypoint\n')
    assert checker.check(root)[1] == ['README.md: missing heading docs/plan.md#retired-milestone']


def test_same_document_duplicate_and_encoded_heading_links(tmp_path):
    root = project(tmp_path)
    (root / 'README.md').write_text(
        '# Overview\n[local](#overview)\n[second](#review-1)\n'
        '[encoded](docs/plan%20notes.md#caf%C3%A9)\n## Review\n## Review\n')
    (root / 'docs/plan notes.md').write_text('# Café\n')
    assert checker.check(root)[1] == []


def test_code_examples_do_not_provide_headings_or_require_link_targets(tmp_path):
    root = project(tmp_path)
    (root / 'README.md').write_text(
        '[missing](#not-a-heading)\n```md\n# Not a heading\n'
        '[example](not-a-file.md)\n```\n'
        '~~~markdown\n[example](also-not-a-file.md)\n~~~\n')
    assert checker.check(root)[1] == ['README.md: missing heading #not-a-heading']


def test_explicit_anchor_formatted_heading_and_nonmarkdown_fragment(tmp_path):
    root = project(tmp_path)
    (root / 'docs/data.json').write_text('{}')
    (root / 'README.md').write_text(
        '<a id="stable-contract"></a>\n## **Field** `rules` ###\n'
        '[stable](#stable-contract)\n[rules](#field-rules)\n'
        '[json](docs/data.json#data)\n[web](https://example.invalid/#unknown)\n')
    assert checker.check(root)[1] == []


def test_missing_files_and_entrypoints_remain_errors(tmp_path):
    root = project(tmp_path)
    (root / 'docs/DEMO_WALKTHROUGH.md').unlink()
    (root / 'README.md').write_text('[missing](docs/absent.md)\n')
    assert checker.check(root)[1] == [
        'Missing canonical entrypoint: docs/DEMO_WALKTHROUGH.md', 'README.md: missing docs/absent.md']
