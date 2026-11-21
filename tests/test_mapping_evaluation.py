import json
from pathlib import Path

import pytest

from provider_directory_truth_layer.intake_store import REQUIRED
from provider_directory_truth_layer.mapping_evaluation import evaluate, frozen_corpus, score

CORPUS = Path(__file__).parent / 'fixtures/onboarding'


def gold_definition(case):
    return {'version': 1, 'mapping': {field: column for field, column in case['expected_mapping'].items() if column is not None},
            'transforms': case['gold_operations'], 'required': list(REQUIRED)}


def test_frozen_manifest_and_independent_gold_values_are_coherent():
    manifest, cases = frozen_corpus(CORPUS)
    assert manifest['case_count'] == len(cases) == 8
    for case in cases:
        result = score(case, gold_definition(case))
        assert not result['binding_errors'] and not result['cleaned_value_errors'], case['id']


def test_wrong_fax_and_ambiguous_date_are_measured_even_when_schema_valid():
    _, cases = frozen_corpus(CORPUS)
    fax_case = next(case for case in cases if case['id'] == 'voice-versus-fax')
    bad = gold_definition(fax_case); bad['mapping']['phone'] = 'Fax'
    assert score(fax_case, bad)['corrections_needed'] == 1
    assert score(fax_case, bad)['cleaned_value_errors'][0]['field'] == 'phone'
    date_case = next(case for case in cases if case['id'] == 'ambiguous-day-month')
    bad = gold_definition(date_case); bad['transforms'] = {'source_updated_at': [{'op': 'date', 'format': '%m/%d/%Y'}]}
    assert score(date_case, bad)['cleaned_value_errors']


def test_offline_baseline_does_not_read_configured_model_or_overwrite_root(tmp_path, monkeypatch):
    monkeypatch.setenv('PDTL_ASSISTANT_ENABLED', '1'); monkeypatch.setenv('OPENAI_API_KEY', 'synthetic-secret-never-used')
    from provider_directory_truth_layer import mapping_assistant
    monkeypatch.setattr(mapping_assistant.MappingAssistant, 'run_once', lambda *args: pytest.fail('Offline evaluation invoked a model'))
    root = tmp_path / 'baseline'
    result = evaluate(root, CORPUS)
    assert result['case_count'] == 8 and result['invocations_attempted'] == result['completed_model_cases'] == 0
    assert result['baseline']['corrections_needed'] > 0 and result['baseline']['cleaned_value_errors'] > 0
    assert result['state_counts'] == {'observation': 0, 'feed_version': 0, 'approved_recipes': 0}
    assert 'synthetic-secret-never-used' not in (root / 'evaluation.json').read_text()
    with pytest.raises(ValueError, match='new'): evaluate(root, CORPUS)


def test_requested_but_unavailable_model_keeps_all_case_outcomes_explicit(tmp_path, monkeypatch):
    monkeypatch.delenv('OPENAI_API_KEY', raising=False); monkeypatch.delenv('PDTL_ASSISTANT_ENABLED', raising=False)
    result = evaluate(tmp_path / 'unavailable', CORPUS, invoke_model=True)
    assert result['invocations_attempted'] == result['completed_model_cases'] == 0
    assert {case['model']['state'] for case in result['outcomes']} == {'unavailable'}
    assert result['quality_evaluation'] == 'actual model quality not evaluated'


def test_modified_corpus_fails_before_creating_runtime(tmp_path):
    for filename in ('mapping-assistant-v1.json', 'mapping-assistant-manifest-v1.json'):
        (tmp_path / filename).write_bytes((CORPUS / filename).read_bytes())
    path = tmp_path / 'mapping-assistant-v1.json'; value = json.loads(path.read_bytes()); value['cases'].pop(); path.write_text(json.dumps(value))
    with pytest.raises(ValueError, match='digest mismatch'): evaluate(tmp_path / 'refused', tmp_path)
    assert not (tmp_path / 'refused').exists()
