"""Bound interactive source evidence; complete originals stay in retained storage."""
from __future__ import annotations


def sample_value(value, max_text=512, budget=24_000):
    """Return JSON-safe previews with explicit truncation rather than silent loss."""
    remaining = [budget]
    truncated = [False]

    def visit(item, depth=0):
        remaining[0] -= 8
        if remaining[0] <= 0 or depth > 8:
            truncated[0] = True
            return {'sample_truncated': True}
        if isinstance(item, str):
            size = min(max_text, max(0, remaining[0]))
            remaining[0] -= min(len(item), size)
            if len(item) > size:
                truncated[0] = True
                return {'text_preview': item[:size], 'character_count': len(item), 'sample_truncated': True}
            return item
        if isinstance(item, list):
            if len(item) > 100:
                truncated[0] = True
            return [visit(child, depth + 1) for child in item[:100]]
        if isinstance(item, dict):
            if len(item) > 64:
                truncated[0] = True
            return {key[:256]: visit(child, depth + 1) for key, child in list(item.items())[:64]}
        return item

    result = visit(value)
    return result, truncated[0]


def sample_rows(rows):
    """Preserve row metadata/issue types while bounding only source evidence."""
    result, truncated = [], False
    budget = max(200, 24_000 // max(1, len(rows)) // 3)
    for row in rows:
        item = dict(row)
        for field in ('original', 'normalized', 'normalization'):
            if field in row:
                item[field], clipped = sample_value(row[field], budget=budget)
                truncated |= clipped
        result.append(item)
    return result, truncated
