"""One row interpretation path for recipe previews and durable intake attempts."""
from __future__ import annotations

import re

from .normalize import normalize_phone

REQUIRED = ['npi', 'provider_name', 'address', 'city', 'state', 'zip', 'phone']


def interpret(rows, mapping, native=False, recipe=None):
    for row in rows:
        original = row['original']
        row.setdefault('problems', [])
        if recipe is not None:
            from .normalization_recipes import transform_row
            result = transform_row(original, recipe)
            normalized = result['normalized']
            row['normalization'] = result['provenance']
            row['problems'].extend(result['problems'])
        else:
            normalized = row.get('normalized', {}) if native else {
                key: str(original.get(column) or '').strip() for key, column in mapping.items()}
            normalized = {key: ('' if value is None else value) for key, value in normalized.items()}
        row['normalized'] = normalized
        if not native or recipe is not None:
            row['native_id'] = normalized.get('record_id') or None
        for field in REQUIRED:
            value = normalized.get(field)
            if value is None or not str(value).strip():
                row['problems'].append(f'Missing {field}')
        npi = str(normalized.get('npi') or '')
        if npi and not re.fullmatch(r'\d{10}', npi):
            row['problems'].append('NPI must contain ten digits')
        postal = str(normalized.get('zip') or '')
        if postal and not re.fullmatch(r'\d{5}(?:-?\d{4})?', postal):
            row['problems'].append('ZIP must contain five digits or ZIP+4')
        phone = str(normalized.get('phone') or '')
        if phone and len(normalize_phone(phone)) != 10:
            row['problems'].append('Phone must contain ten digits')
        # Recipes own explicit transformations; the legacy interpretation remains
        # unchanged for existing attempts. Validation never repairs a recipe value.
        if recipe is None:
            normalized['phone'] = normalize_phone(phone)
            normalized['zip'] = str(normalized.get('zip', ''))
            normalized['state'] = str(normalized.get('state', '')).upper()
        row['problems'] = list(dict.fromkeys(row['problems']))
    return rows
