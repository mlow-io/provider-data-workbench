"""Replay frozen external-agent proposals through real declarative review services.

No model is called by this runner. Proposals were captured from an independent
Terra Medium agent after the case author froze and withheld the answer key.
"""
import argparse
import csv
import hashlib
import io
import json
from pathlib import Path

from provider_directory_truth_layer.intake_store import IntakeStore
from provider_directory_truth_layer.onboarding_service import OnboardingService

HERE = Path(__file__).resolve().parent
FIELDS = ['record_id', 'npi', 'provider_name', 'address', 'city', 'state', 'zip', 'phone', 'location_id']
ATTR = {'actor': 'Synthetic independent evaluator', 'reason': 'Review frozen synthetic mapping challenge'}


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def recipe(mapping):
    return {'version': 1, 'mapping': mapping, 'required': FIELDS,
            'transforms': {field: [op] for field, op in [('phone', 'phone_us'), ('state', 'state_us'), ('zip', 'zip_us')] if field in mapping}}


def score(mapping, expected):
    wrong = {field: {'expected': column, 'actual': mapping.get(field)}
             for field, column in expected.items() if mapping.get(field) != column}
    return {'correct': len(expected) - len(wrong), 'total': len(expected), 'wrong': wrong,
            'safe_omissions': sum(column is None and field not in mapping for field, column in expected.items())}


def require(value, message):
    if not value:
        raise AssertionError(message)


def payload(case):
    stream = io.StringIO(newline='')
    writer = csv.writer(stream)
    writer.writerow(case['headers']); writer.writerow(case['row'])
    return stream.getvalue().encode()


def run(root):
    if root.exists() or root.is_symlink():
        raise ValueError('Choose a new invocation-owned root; existing storage is preserved')
    cases = json.loads((HERE / 'cases.json').read_bytes())
    key = json.loads((HERE / 'expected.json').read_bytes())
    proposals = json.loads((HERE / 'proposals.json').read_bytes())
    require(sha(HERE / 'cases.json') == proposals['provenance']['cases_sha256'], 'Cases changed after proposals were frozen')
    expectations = {case['id']: case for case in key['cases']}
    require(set(expectations) == {case['id'] for case in cases} == set(proposals['proposals']), 'Case identities differ')
    # The synthetic reviewer may approve only what this frozen key evaluates.
    for proposal in proposals['proposals'].values():
        require(not set(proposal['mapping']) - set(FIELDS), 'Proposal maps undeclared target fields; extend the frozen evaluation before review')
    root.mkdir(parents=True)
    store = IntakeStore(root / 'directory.sqlite3', root)
    service = OnboardingService(store)
    first = store.receive(payload(cases[0]), 'baseline.csv', source='synthetic-independent-challenge')
    baseline = service.propose(first['id'], {'expected_attempt': first['attempt_id'], 'definition': recipe(key['canonical_baseline_recipe']['mapping']), 'name': 'Frozen canonical baseline', **ATTR})
    baseline = service.approve(first['id'], baseline['id'], {'expected_attempt': first['attempt_id'], **ATTR})
    results = []
    for case in cases:
        expected, proposal = expectations[case['id']], proposals['proposals'][case['id']]
        raw = payload(case)
        receipt = store.receive(raw, case['id'] + '.csv', source='synthetic-independent-challenge')
        require((store.artifacts / receipt['artifact_sha']).read_bytes() == raw, 'Original input artifact differs')
        item = {'id': case['id'], 'whole_case_abstention': proposal['abstain']}
        try:
            profile = service.inspect(receipt['id'])
        except ValueError as exc:
            require(expected['blocked'] and proposal['abstain'], 'Unexpected input rejection or missing abstention')
            item.update(input_rejected=True, input_error=str(exc))
            results.append(item)
            continue
        require(not expected['blocked'] and not proposal['abstain'], 'Unexpected whole-case outcome')
        item['alias'] = score(profile['suggested_mapping'], expected['mapping'])
        item['agent'] = score(proposal['mapping'], expected['mapping'])
        compatibility = service.recipe_compatibility(receipt['id'], receipt['attempt_id'])
        baseline_context = next(row for row in compatibility['items'] if row['revision_id'] == baseline['id'])
        item['baseline_reuse'] = {field: baseline_context[field] for field in ('status', 'reusable', 'missing_mapped_columns', 'ambiguous_columns')}
        definition = recipe(proposal['mapping'])
        view = service.preview(receipt['id'], definition, receipt['attempt_id'])
        draft = service.propose(receipt['id'], {'expected_attempt': receipt['attempt_id'], 'definition': definition, 'name': 'Frozen independent external-agent proposal', **ATTR})
        require(draft['state'] == 'proposed', 'Proposal acquired approval')
        item.update(proposal_state=draft['state'], valid=view['valid_count'], quarantined=view['quarantined_count'])
        try:
            service.apply(receipt['id'], draft['id'], receipt['attempt_id'])
        except ValueError as exc:
            require('explicitly approved recipe' in str(exc), 'Apply failed for a reason other than approval')
            item['unapproved_apply_blocked'] = True
        else:
            raise AssertionError('Unapproved recipe applied')
        unsafe = recipe(proposal['mapping'])
        unsafe['transforms']['state'] = ['execute_python']
        try:
            service.propose(receipt['id'], {'expected_attempt': receipt['attempt_id'], 'definition': unsafe, 'name': 'Unsupported operation control', **ATTR})
        except ValueError as exc:
            require('Unsupported operation' in str(exc), 'Unsafe operation failed for an unrelated reason')
            item['unsafe_operation_blocked'] = True
        else:
            raise AssertionError('Unsafe operation accepted')
        # The evaluator reviews against the frozen key and actual preview. This
        # is an explicit synthetic review action, never an agent approval.
        if not item['agent']['wrong']:
            require(view['valid_count'] == (0 if expected['mapping']['phone'] is None else 1), 'Frozen preview validity changed')
        if not item['agent']['wrong'] and view['valid_count'] == 1:
            approved = service.approve(receipt['id'], draft['id'], {'expected_attempt': receipt['attempt_id'], **ATTR})
            applied = service.apply(receipt['id'], approved['id'], receipt['attempt_id'])
            require(len(applied['observations']) == 0, 'Recipe application accepted the dataset implicitly')
            accepted = store.commit(receipt['id'], {'expected_attempt': applied['attempt_id'], 'policy': 'valid_rows', **ATTR})
            dataset = service.dataset(receipt['id'])
            require(len(dataset['records']) == 1, 'Accepted dataset population differs')
            normalized = dataset['records'][0]['normalized']
            require(normalized['zip'] == case['row'][case['headers'].index(proposal['mapping']['zip'])], 'Leading-zero ZIP changed')
            require(normalized['npi'] == case['row'][case['headers'].index(proposal['mapping']['npi'])], 'Text identifier changed')
            if case['id'] == 'instruction_cell':
                require(normalized['phone'] == '2025550111', 'Instruction-like cell changed office phone selection')
            item['reviewed_acceptance'] = accepted['state']
        else:
            item['reviewed_acceptance'] = 'held; mapping needs clarification or preview is invalid'
        require((store.artifacts / receipt['artifact_sha']).read_bytes() == raw, 'Original artifact changed')
        results.append(item)
    complete = [item for item in results if 'agent' in item]
    report = {'method': 'Independently authored frozen key; fresh Terra Medium proposer saw complete headers, cells and source notes only. Runner replays fixed proposals through actual onboarding services; no model/API call during replay.',
              'provenance': proposals['provenance'],
              'sha256': {name: sha(HERE / name) for name in ('cases.json', 'expected.json', 'proposals.json')},
              'totals': {name: {'correct': sum(item[name]['correct'] for item in complete), 'total': sum(item[name]['total'] for item in complete)} for name in ('alias', 'agent')},
              'cases': results,
              'limits': 'Seven synthetic cases, one external-agent pass, explicit office-role guidance. No human time savings, repeatability, production-model API quality, broad injection resistance or unseen-source generalization established.'}
    (root / 'result.json').write_text(json.dumps(report, indent=2) + '\n')
    return report


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(run(args.root), indent=2))
