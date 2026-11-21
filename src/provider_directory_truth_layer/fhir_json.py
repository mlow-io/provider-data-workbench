"""Shared strict, bounded decoding of retained FHIR JSON bytes."""
from __future__ import annotations

import json
import math

MAX_BYTES = 10 * 1024 * 1024


def _unique_object(pairs):
    value = {}
    for key, item in pairs:
        if key in value:
            raise ValueError(f'Duplicate JSON property: {key}')
        value[key] = item
    return value


def _reject_constant(value):
    raise ValueError(f'Non-JSON numeric constant: {value}')


def walk(value, path):
    stack = [(path, value, 0)]
    visited = 0
    while stack:
        at, node, depth = stack.pop()
        visited += 1
        if depth > 64 or visited > 100_000:
            raise ValueError('FHIR structure exceeds depth/node limits')
        yield at, node
        children = node.items() if isinstance(node, dict) else enumerate(node) if isinstance(node, list) else []
        for key, child in reversed(list(children)):
            child_path = f'{at}.{key}' if isinstance(node, dict) else f'{at}[{key}]'
            stack.append((child_path, child, depth + 1))


def load_fhir_json(payload: bytes, *, max_bytes=MAX_BYTES):
    """Decode before inspecting identities; never collapse ambiguous source keys."""
    if not payload or len(payload) > max_bytes:
        raise ValueError('FHIR artifact must contain 1 byte to 10 MiB')
    try:
        value = json.loads(payload.decode('utf-8-sig'), object_pairs_hook=_unique_object,
                           parse_constant=_reject_constant)
    except (UnicodeError, ValueError, RecursionError) as exc:
        raise ValueError(f'Invalid UTF-8 FHIR JSON: {exc}') from exc
    for _, node in walk(value, '$'):
        if isinstance(node, float) and not math.isfinite(node):
            raise ValueError('FHIR JSON numbers must be finite')
    return value
