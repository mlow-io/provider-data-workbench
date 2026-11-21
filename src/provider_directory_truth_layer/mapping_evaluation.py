"""Frozen mapping baseline and optional real-model trials in a new owned root."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

from .intake_store import IntakeStore, REQUIRED, packed
from .bundled_assets import assets
from .mapping_assistant import MappingAssistant
from .normalization_recipes import transform_row, validate_recipe
from .onboarding_service import OnboardingService


def frozen_corpus(directory):
    manifest = json.loads((directory / 'mapping-assistant-manifest-v1.json').read_bytes())
    if manifest.get('corpus_file') != 'mapping-assistant-v1.json':
        raise ValueError('Unknown mapping corpus file')
    raw = (directory / manifest['corpus_file']).read_bytes()
    if hashlib.sha256(raw).hexdigest() != manifest['sha256']:
        raise ValueError('Frozen mapping corpus digest mismatch')
    corpus = json.loads(raw)
    if manifest['case_count'] != len(corpus['cases']) or len({case['id'] for case in corpus['cases']}) != len(corpus['cases']):
        raise ValueError('Frozen case count or IDs disagree')
    return manifest, corpus['cases']


def score(case, definition):
    definition = validate_recipe(definition)
    expected = case['expected_mapping']
    observed = definition['mapping']
    binding_errors = [{'field': field, 'expected': expected.get(field), 'observed': observed.get(field)}
                      for field in sorted(set(expected) | set(observed)) if expected.get(field) != observed.get(field)]
    cleaned_errors = []
    values_checked = 0
    for index, (original, gold) in enumerate(zip(case['rows'], case['expected_cleaned'])):
        actual = transform_row(original, definition)['normalized']
        for field, expected_value in gold.items():
            values_checked += 1
            if actual.get(field) != expected_value:
                cleaned_errors.append({'row': index, 'field': field, 'expected': expected_value, 'observed': actual.get(field)})
    return {'binding_expectations': len(expected), 'correct_bindings_or_abstentions': sum(expected[field] == observed.get(field) for field in expected),
            'binding_errors': binding_errors, 'corrections_needed': len(binding_errors),
            'expected_abstentions': sum(value is None for value in expected.values()),
            'observed_required_abstentions': sorted(set(REQUIRED) - set(observed)),
            'cleaned_values_checked': values_checked, 'cleaned_value_errors': cleaned_errors}


def evaluate(root: Path, corpus_directory: Path | None = None, *, invoke_model=False):
    manifest, cases = frozen_corpus(corpus_directory if corpus_directory is not None else assets().joinpath('mapping'))
    if root.exists() or root.is_symlink():
        raise ValueError('Evaluation root must be new; existing data is never overwritten')
    root.mkdir(parents=False, mode=0o700)
    store = IntakeStore(root / 'directory.sqlite3', root)
    onboarding = OnboardingService(store)
    assistant = MappingAssistant(store)
    outcomes = []
    for case in cases:
        receipt = store.receive(packed(case['rows']).encode(), case['id'] + '.json',
                                source='synthetic-mapping-evaluation-' + case['id'], designation='synthetic',
                                metadata={'scope': 'mapping-assistant-v1'})
        profile = onboarding.inspect(receipt['id'], limit=100)
        baseline = {'version': 1, 'mapping': profile['suggested_mapping'], 'transforms': {}, 'required': list(REQUIRED)}
        outcome = {'case_id': case['id'], 'receipt_id': receipt['id'], 'attempt_id': receipt['attempt_id'],
                   'baseline_definition': baseline, 'baseline': score(case, baseline), 'model': {'state': 'not_requested'}}
        if invoke_model:
            run = assistant.create(receipt['id'], {'request_id': 'evaluation-' + case['id'],
                'expected_attempt': receipt['attempt_id'], 'actor': 'Synthetic evaluation runner',
                'reason': 'Frozen mapping-assistant-v1 held-out trial; proposal only', 'external_processing': True})
            run = assistant.run_once(receipt['id'], run['id'])
            outcome['model'] = {'state': run['state'], 'run_id': run['id'], 'proposal_id': run['proposal_id'],
                                'request_sha': run['request_sha'], 'response_sha': run['response_sha'], 'result': run['result']}
            if run['state'] == 'succeeded':
                outcome['model']['score'] = score(case, run['result']['definition'])
        outcomes.append(outcome)
    with store.db() as conn:
        counts = {table: conn.execute('SELECT count(*) FROM ' + table).fetchone()[0] for table in ('observation', 'feed_version')}
        counts['approved_recipes'] = conn.execute("SELECT count(*) FROM recipe_revision WHERE state='approved'").fetchone()[0]
        attempts = conn.execute("SELECT count(*) FROM assistant_run_event WHERE kind='invocation_started'").fetchone()[0]
    if any(counts.values()):
        raise ValueError('Evaluation changed acceptance or approval state')
    scores = [outcome['baseline'] for outcome in outcomes]
    completed = sum(outcome['model']['state'] == 'succeeded' for outcome in outcomes)
    report = {'format_version': 1, 'corpus_manifest': manifest, 'case_count': len(cases),
              'baseline': {'name': 'existing alias-only suggestions; no transforms',
                           'binding_expectations': sum(item['binding_expectations'] for item in scores),
                           'correct_bindings_or_abstentions': sum(item['correct_bindings_or_abstentions'] for item in scores),
                           'corrections_needed': sum(item['corrections_needed'] for item in scores),
                           'cleaned_values_checked': sum(item['cleaned_values_checked'] for item in scores),
                           'cleaned_value_errors': sum(len(item['cleaned_value_errors']) for item in scores)},
              'model_requested': invoke_model, 'invocations_attempted': attempts, 'completed_model_cases': completed,
              'configuration': assistant.configuration.public(), 'state_counts': counts, 'outcomes': outcomes,
              'quality_evaluation': 'model outcomes retained for review' if completed else 'actual model quality not evaluated',
              'notice': 'Synthetic engineering evaluation. Corrections are field disagreements, not measured human time. No automatic approval/acceptance. Feature remains experimental.'}
    with (root / 'evaluation.json').open('x', encoding='utf-8') as stream:
        json.dump(report, stream, indent=2, ensure_ascii=False, allow_nan=False)
        stream.write('\n')
    return report
