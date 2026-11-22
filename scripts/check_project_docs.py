"""Check local Markdown files, heading anchors, and canonical documentation entrypoints."""
from pathlib import Path
import re
import sys
from urllib.parse import unquote

ROOT = Path(__file__).resolve().parents[1]
ENTRYPOINTS = (
    'README.md',
    'docs/ARCHITECTURE.md',
    'docs/DATA_MODEL.md',
    'docs/FHIR_AND_STANDARDS.md',
    'docs/API_REFERENCE.md',
    'docs/DEMO_WALKTHROUGH.md',
)


def prose_lines(text):
    """Yield non-fenced lines; support backtick and tilde fences."""
    fence = None
    for line in text.splitlines():
        marker = re.match(r'^ {0,3}(`{3,}|~{3,})(.*)$', line)
        if marker:
            run, rest = marker.groups()
            if fence is None:
                fence = run
                continue
            if run[0] == fence[0] and len(run) >= len(fence) and not rest.strip():
                fence = None
                continue
        if fence is None:
            yield line


def anchors(text):
    result = set()
    generated = set()
    for line in prose_lines(text):
        result.update(re.findall(r'<[^>]+\b(?:id|name)=[\"\']([^\"\']+)[\"\']', line))
        heading = re.match(r'^ {0,3}#{1,6}\s+(.+?)(?:\s+#+)?\s*$', line)
        if not heading:
            continue
        label = re.sub(r'\[([^\]]+)\]\([^)]+\)', r'\1', heading[1])
        label = re.sub(r'<[^>]*>', '', label)
        slug = re.sub(r'[^\w\- ]', '', label.lower()).replace(' ', '-')
        candidate, suffix = slug, 0
        while candidate in generated:
            suffix += 1
            candidate = f'{slug}-{suffix}'
        generated.add(candidate)
        result.add(candidate)
    return result


def check(root=ROOT):
    errors = []
    for name in ENTRYPOINTS:
        if not (root / name).is_file():
            errors.append(f'Missing canonical entrypoint: {name}')
    documents = sorted((root / 'docs').rglob('*.md')) + sorted(root.glob('*.md'))
    anchor_cache = {}
    for document in documents:
        prose = '\n'.join(prose_lines(document.read_text()))
        for target in re.findall(r'\]\(([^)]+)\)', prose):
            target = target.removeprefix('<').removesuffix('>')
            if re.match(r'^[a-zA-Z][a-zA-Z0-9+.-]*:', target):
                continue
            path, _, fragment = target.partition('#')
            destination = (document.parent / unquote(path)).resolve() if path else document.resolve()
            if not destination.exists():
                errors.append(f'{document.relative_to(root)}: missing {target}')
            elif fragment and destination.suffix.lower() == '.md':
                if destination not in anchor_cache:
                    anchor_cache[destination] = anchors(destination.read_text())
                if unquote(fragment) not in anchor_cache[destination]:
                    errors.append(f'{document.relative_to(root)}: missing heading {target}')
    return documents, errors


if __name__ == '__main__':
    documents, errors = check()
    for error in errors:
        print(error, file=sys.stderr)
    print(f'Checked {len(documents)} Markdown documents; {len(errors)} local link or entrypoint errors')
    raise SystemExit(bool(errors))
