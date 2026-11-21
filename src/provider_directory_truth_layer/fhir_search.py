"""Conservative query-integrity checks, separate from resource/profile validity."""
from __future__ import annotations

COUNT_FIELDS = ('matched_entries', 'implicit_match_entries', 'included_entries', 'outcome_entries')


def search_entry_mode(entry, locator):
    if not isinstance(entry, dict):
        raise ValueError(f'Filtered query entry {locator} must be an object')
    metadata = entry.get('search', {})
    if not isinstance(metadata, dict):
        raise ValueError(f'Filtered query search metadata at {locator} must be an object')
    mode = metadata.get('mode', 'match')
    if not isinstance(mode, str) or mode not in {'match', 'include', 'outcome'}:
        raise ValueError(f'Filtered query search mode at {locator} is unknown')
    return mode, 'mode' not in metadata


def search_page_counts(data, resource_type, resource_id):
    """Check declared match meaning; do not certify included resource validity."""
    entries = data.get('entry', [])
    if not isinstance(entries, list):
        raise ValueError('Filtered query entries must be a list')
    counts = dict.fromkeys(COUNT_FIELDS, 0)
    for index, entry in enumerate(entries):
        locator = f'$.entry[{index}]'
        mode, implicit = search_entry_mode(entry, locator)
        resource = entry.get('resource')
        if not isinstance(resource, dict):
            raise ValueError(f'Filtered query resource at {locator} must be an object')
        if mode == 'match':
            if resource.get('resourceType') != resource_type or resource.get('id') != resource_id:
                raise ValueError(f'Filtered query match at {locator} differs from requested {resource_type}/{resource_id}')
            counts['matched_entries'] += 1
            counts['implicit_match_entries'] += int(implicit)
        elif mode == 'include':
            if resource.get('resourceType') == 'OperationOutcome':
                raise ValueError(f'Filtered query OperationOutcome at {locator} requires outcome mode')
            counts['included_entries'] += 1
        else:
            issues = resource.get('issue')
            if resource.get('resourceType') != 'OperationOutcome' or not isinstance(issues, list) or not issues:
                raise ValueError(f'Filtered query outcome at {locator} requires OperationOutcome issues')
            for issue in issues:
                severity = issue.get('severity') if isinstance(issue, dict) else None
                code = issue.get('code') if isinstance(issue, dict) else None
                if (not isinstance(severity, str) or severity not in {'fatal', 'error', 'warning', 'information'}
                        or not isinstance(code, str) or not code.strip()):
                    raise ValueError(f'Filtered query outcome at {locator} has malformed severity/code')
                if severity in {'fatal', 'error'}:
                    raise ValueError(f'Filtered query source returned an error/fatal outcome at {locator}')
            counts['outcome_entries'] += 1
    return counts
