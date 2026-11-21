"""Proposal authority, bounded input, uncertain calls and transactional recovery."""
import copy
import hashlib
import json
import sqlite3
import subprocess
import sys
import threading
from concurrent.futures import ThreadPoolExecutor

import pytest
from fastapi.testclient import TestClient

from provider_directory_truth_layer import mapping_model
from provider_directory_truth_layer.intake_api import create_workbench
from provider_directory_truth_layer.intake_store import Conflict, IntakeStore, REQUIRED, VERSION, packed
from provider_directory_truth_layer.mapping_assistant import Configuration, MappingAssistant
from provider_directory_truth_layer.onboarding_service import OnboardingService

DATA = (b'record_id,npi,provider_name,address,city,state,zip,phone,location_id\n'
        b'SYN-001,1000000001,Synthetic Clinician,10 Example St,Example,MA,02108,6175550100,NORTH\n')
HEADERS = DATA.splitlines()[0].decode().split(',')
CONFIG = Configuration(enabled=True, api_key='synthetic-provider-key')


def proposal():
    return {'bindings': [{'field': name, 'column': name, 'operations': []} for name in HEADERS],
            'unresolved': [], 'explanation': 'Synthetic controlled mapping; review independently.'}


def response(value=None, **changes):
    result = {'id': 'synthetic-response', 'status': 'completed', 'model': mapping_model.MODEL,
              'output': [{'type': 'message', 'role': 'assistant', 'content': [{'type': 'output_text', 'text': packed(value or proposal())}]}],
              'usage': {'input_tokens': 100, 'output_tokens': 100, 'total_tokens': 200}}
    result.update(changes)
    return packed(result).encode()


def reply(body=None):
    return {'status': 200, 'body': body or response(), 'error': None, 'request_id': 'synthetic-request'}


@pytest.fixture
def setup(tmp_path):
    store = IntakeStore(tmp_path / 'test.db', tmp_path)
    receipt = store.receive(DATA, 'clinic.csv', source='synthetic-clinic', designation='synthetic')
    calls = []
    def transport(raw, key):
        calls.append((raw, key))
        return reply()
    return store, receipt, MappingAssistant(store, configuration=CONFIG, transport=transport), calls


def create(service, receipt, request_id='run-1', **changes):
    return service.create(receipt['id'], {'request_id': request_id, 'expected_attempt': receipt['attempt_id'],
                                         'actor': 'Synthetic analyst', 'reason': 'Inspect bounded mapping',
                                         'external_processing': True, **changes})


def counts(store):
    with store.db() as conn:
        return {table: conn.execute('SELECT count(*) FROM ' + table).fetchone()[0] for table in
                ('attempt', 'recipe_revision', 'observation', 'work_case', 'feed_version')}


def test_one_run_saves_only_a_proposal_with_exact_artifacts_and_separate_approval(setup):
    store, receipt, service, calls = setup
    before = counts(store)
    run = create(service, receipt)
    assert calls == [] and run['state'] == 'queued'
    result = service.run_once(receipt['id'], run['id'])
    assert result['state'] == 'succeeded', result
    assert len(calls) == 1
    assert calls[0][0] == (store.artifacts / result['request_sha']).read_bytes()
    assert (store.artifacts / result['response_sha']).read_bytes() == response()
    assert 'synthetic-provider-key' not in packed(result)
    assert json.loads(calls[0][0])['store'] is False
    assert json.loads(calls[0][0])['reasoning'] == {'effort': 'none'}
    assert counts(store) == {**before, 'recipe_revision': before['recipe_revision'] + 1}
    recipes = service.onboarding.recipes(receipt['id'])['items']
    assert recipes[0]['state'] == 'proposed' and recipes[0]['assistant_run']['id'] == run['id']
    assert service.run_once(receipt['id'], run['id']) == result and len(calls) == 1
    approved = service.onboarding.approve(receipt['id'], result['proposal_id'], {
        'expected_attempt': receipt['attempt_id'], 'actor': 'Separate reviewer', 'reason': 'Review expected fields'})
    mapped = service.onboarding.apply(receipt['id'], approved['id'], receipt['attempt_id'])
    store.commit(receipt['id'], {'expected_attempt': mapped['attempt_id'], 'actor': 'Acceptance reviewer', 'reason': 'Review rows', 'policy': 'valid_rows'})
    dataset = service.onboarding.dataset(receipt['id'])
    provenance = dataset['records'][0]['normalization']['assistant']
    assert provenance['run_id'] == run['id'] and provenance['response_sha'] == result['response_sha']
    assert dataset['records'][0]['original']['zip'] == '02108'


def test_creation_identity_permission_source_policy_and_unavailable_do_not_invoke(setup):
    store, receipt, service, calls = setup
    first = create(service, receipt)
    assert create(service, receipt)['id'] == first['id']
    with pytest.raises(Conflict): create(service, receipt, reason='Changed intent')
    with pytest.raises(ValueError): create(service, receipt, request_id='no-permission', external_processing=False)
    with pytest.raises(ValueError): create(service, receipt, request_id='endpoint', endpoint='https://another.example')
    local = store.receive(DATA, 'private.csv', source='private-source', designation='local')
    with pytest.raises(ValueError, match='permission'): create(service, local, request_id='private')
    allowed = MappingAssistant(store, configuration=Configuration(enabled=True, api_key='synthetic-provider-key', allowed_sources=('private-source',)), transport=service.transport)
    assert create(allowed, local, request_id='allowed')['state'] == 'queued'
    unavailable = MappingAssistant(store, configuration=Configuration(), transport=service.transport)
    run = create(unavailable, receipt, request_id='unavailable')
    assert run['state'] == unavailable.run_once(receipt['id'], run['id'])['state'] == 'unavailable'
    assert calls == [] and unavailable.list(receipt['id'])['configuration']['experimental']


def test_stale_before_call_and_after_response_publish_no_proposal(setup):
    store, receipt, service, calls = setup
    run = create(service, receipt)
    updated = store.mapping(receipt['id'], {'expected_attempt': receipt['attempt_id']})
    assert service.run_once(receipt['id'], run['id'])['state'] == 'failed'
    assert calls == []
    new = create(service, updated, request_id='after-response')
    def changes_during_call(*args):
        store.mapping(receipt['id'], {'expected_attempt': updated['attempt_id']})
        return reply()
    service.transport = changes_during_call
    assert service.run_once(receipt['id'], new['id'])['state'] == 'failed'
    assert counts(store)['recipe_revision'] == 0


def test_invalid_proposal_retains_available_accounting_and_policy_basis(setup):
    store, receipt, service, _ = setup
    service.transport = lambda *args: reply(response(output=[{'type': 'function_call'}]))
    run = create(service, receipt)
    result = service.run_once(receipt['id'], run['id'])
    assert result['state'] == 'failed' and result['proposal_id'] is None
    assert result['result']['usage'] == {'input_tokens': 100, 'output_tokens': 100, 'total_tokens': 200}
    assert 0 < result['result']['conservative_estimated_usd'] < .08
    assert result['context']['external_processing_policy']['basis'] == 'synthetic-designation'


def test_changed_rate_contract_and_corrupted_request_fail_before_provider_call(setup):
    store, receipt, service, calls = setup
    run = create(service, receipt)
    with store.db() as conn:
        altered = copy.deepcopy(run['config']); altered['rates']['input_per_million_usd'] = 123
        conn.execute('UPDATE assistant_run SET config=? WHERE id=?', (packed(altered), run['id']))
    result = service.run_once(receipt['id'], run['id'])
    assert result['state'] == 'failed' and result['reserved_microusd'] == 0 and calls == []
    next_run = create(service, receipt, request_id='corrupt-request')
    (store.artifacts / next_run['request_sha']).write_bytes(b'Corrupted owned fixture')
    result = service.run_once(receipt['id'], next_run['id'])
    assert result['state'] == 'failed' and 'digest mismatch' in result['result']['error']
    assert result['reserved_microusd'] == 0 and calls == []


def test_timeout_failure_is_visible_and_never_retried_or_exported_as_a_secret(setup):
    store, receipt, service, _ = setup
    calls = []
    def timeout(*args):
        calls.append(1)
        raise TimeoutError('synthetic-provider-key must not enter history')
    service.transport = timeout
    run = create(service, receipt)
    result = service.run_once(receipt['id'], run['id'])
    assert result['state'] == 'failed' and result['reserved_microusd'] == 80000
    assert 'synthetic-provider-key' not in packed(result)
    assert service.run_once(receipt['id'], run['id']) == result and calls == [1]


@pytest.mark.parametrize('kind', ['columns', 'request_bytes'])
def test_oversized_inputs_are_declined_before_queuing_or_invoking(setup, kind):
    store, _, service, calls = setup
    names = [f'Column-{i}-' + ('a' * 230 if kind == 'request_bytes' else '') for i in range(40 if kind == 'request_bytes' else 41)]
    receipt = store.receive(packed([{name: 'x' * 160 for name in names}] * 3).encode(), 'wide.json')
    with pytest.raises(ValueError): create(service, receipt)
    assert calls == [] and service.list(receipt['id'])['items'] == []


def test_inflight_cancel_retains_discarded_body_without_proposal(setup):
    store, receipt, service, _ = setup
    entered, release = threading.Event(), threading.Event()
    def blocked(*args):
        entered.set(); assert release.wait(5); return reply()
    service.transport = blocked
    run = create(service, receipt)
    with ThreadPoolExecutor() as pool:
        future = pool.submit(service.run_once, receipt['id'], run['id'])
        assert entered.wait(5)
        current = service.detail(receipt['id'], run['id'])
        with pytest.raises(Conflict): service.cancel(receipt['id'], run['id'], {'expected_revision': 0, 'actor': 'Reviewer', 'reason': 'Stale cancellation'})
        service.cancel(receipt['id'], run['id'], {'expected_revision': current['revision'], 'actor': 'Reviewer', 'reason': 'Cancel retained intent'})
        release.set(); result = future.result(timeout=5)
    assert result['state'] == 'cancelled'
    assert result['events'][-1]['kind'] == 'discarded_response' and result['events'][-1]['artifact_sha']
    assert counts(store)['recipe_revision'] == 0


@pytest.mark.parametrize('fault', ['invented_column', 'duplicate_field', 'duplicate_column', 'operation', 'required', 'tool', 'refusal', 'incomplete', 'usage', 'model', 'shape', 'duplicate_json', 'nonfinite'])
def test_invalid_or_adversarial_result_cannot_publish(setup, fault):
    store, receipt, service, _ = setup
    value = proposal(); envelope = json.loads(response())
    if fault == 'invented_column': value['bindings'][0]['column'] = 'Invented'
    elif fault == 'duplicate_field': value['bindings'].append(copy.deepcopy(value['bindings'][0]))
    elif fault == 'duplicate_column': value['bindings'][1]['column'] = value['bindings'][0]['column']
    elif fault == 'operation': value['bindings'][0]['operations'] = [{'op': 'exec', 'format': None}]
    elif fault == 'required': value['bindings'] = [b for b in value['bindings'] if b['field'] != 'phone']
    elif fault == 'tool': envelope['output'] = [{'type': 'function_call', 'name': 'approve_everything'}]
    elif fault == 'refusal': envelope['output'][0]['content'] = [{'type': 'refusal', 'refusal': 'No'}]
    elif fault == 'incomplete': envelope['status'] = 'incomplete'
    elif fault == 'usage': envelope['usage']['input_tokens'] = 20001
    elif fault == 'model': envelope['model'] = 'unconfigured-model'
    elif fault == 'shape': envelope['output'] = ['not a message']
    raw = response(value) if fault in {'invented_column', 'duplicate_field', 'duplicate_column', 'operation', 'required'} else packed(envelope).encode()
    if fault == 'duplicate_json': raw = b'{"status":"completed","status":"failed"}'
    if fault == 'nonfinite': raw = b'{"usage":NaN}'
    service.transport = lambda *args: reply(raw)
    result = service.run_once(receipt['id'], create(service, receipt)['id'])
    assert result['state'] == 'failed' and result['proposal_id'] is None
    assert counts(store)['recipe_revision'] == counts(store)['observation'] == 0


def test_sample_policy_clips_cells_preserves_presence_and_keeps_gold_out_of_request(setup):
    store, _, service, _ = setup
    data = [{'npi': '1000000001', 'Notes': 'é' * 200, 'phone': None}, {'npi': '1000000001', 'Notes': ''}]
    receipt = store.receive(packed(data).encode(), 'sample.json')
    raw, context = mapping_model.build_request(service.onboarding, receipt['id'], receipt['attempt_id'])
    request = json.loads(raw); sample = json.loads(request['input'][0]['content'])
    assert sample['rows'][0]['values']['Notes']['clipped']
    assert len(sample['rows'][0]['values']['Notes']['value'].encode()) == 160
    assert sample['rows'][0]['values']['phone'] == {'present': True, 'value': None, 'clipped': False}
    assert sample['rows'][1]['values']['phone'] == {'present': False, 'value': None, 'clipped': False}
    assert context['sample_rows'] == 2 and len(raw) <= mapping_model.LIMITS['request_bytes']
    assert 'expected_mapping' not in raw.decode() and 'gold_operations' not in raw.decode()


def test_budget_reservation_includes_failed_calls_and_reopen_does_not_retry_unknown_calls(setup):
    store, receipt, service, calls = setup
    service.transport = lambda *args: {'status': 429, 'body': b'Synthetic throttle', 'error': None, 'request_id': None}
    for i in range(12):
        result = service.run_once(receipt['id'], create(service, receipt, request_id=f'failed-{i}')['id'])
        assert result['state'] == 'failed' and result['reserved_microusd'] == 80000
    blocked = service.run_once(receipt['id'], create(service, receipt, request_id='exhausted')['id'])
    assert blocked['reserved_microusd'] == 0 and 'budget exhausted' in blocked['result']['error']
    assert service.list(receipt['id'])['reserved_usd'] == .96
    assert calls == []


def test_real_process_death_during_call_has_no_automatic_billable_retry(setup):
    store, receipt, service, calls = setup
    run = create(service, receipt)
    code = '''
import os,sys
from pathlib import Path
from provider_directory_truth_layer.intake_store import IntakeStore
from provider_directory_truth_layer.mapping_assistant import MappingAssistant,Configuration
store=IntakeStore.open_existing(Path(sys.argv[1]),Path(sys.argv[2]))
def crash(*args):os._exit(23)
MappingAssistant(store,configuration=Configuration(enabled=True,api_key='synthetic'),transport=crash).run_once(sys.argv[3],sys.argv[4])
'''
    completed = subprocess.run([sys.executable, '-c', code, str(store.path), str(store.root), receipt['id'], run['id']], timeout=10)
    assert completed.returncode == 23
    assert service.detail(receipt['id'], run['id'])['state'] == 'running'
    result = service.run_once(receipt['id'], run['id'])
    assert result['state'] == 'failed' and result['reserved_microusd'] == 80000 and calls == []
    assert 'unknown outcome' in result['result']['error']


def test_real_process_death_in_proposal_transaction_rolls_back_and_resumes_response(setup):
    store, receipt, service, calls = setup
    run = create(service, receipt)
    code = '''
import os,sys
from pathlib import Path
from provider_directory_truth_layer.intake_store import IntakeStore
from provider_directory_truth_layer.mapping_assistant import MappingAssistant,Configuration
from provider_directory_truth_layer.onboarding_service import OnboardingService
store=IntakeStore.open_existing(Path(sys.argv[1]),Path(sys.argv[2]))
original=OnboardingService._save_proposal
def crash(self,*args):
 original(self,*args)
 os._exit(24)
OnboardingService._save_proposal=crash
body=Path(sys.argv[5]).read_bytes()
MappingAssistant(store,configuration=Configuration(enabled=True,api_key='synthetic'),transport=lambda *args:dict(status=200,body=body,error=None,request_id='synthetic')).run_once(sys.argv[3],sys.argv[4])
'''
    raw_path = store.root / 'controlled-response.json'; raw_path.write_bytes(response())
    completed = subprocess.run([sys.executable, '-c', code, str(store.path), str(store.root), receipt['id'], run['id'], str(raw_path)], timeout=10)
    assert completed.returncode == 24 and counts(store)['recipe_revision'] == 0
    assert service.detail(receipt['id'], run['id'])['state'] == 'response_ready'
    assert service.run_once(receipt['id'], run['id'])['state'] == 'succeeded'
    assert counts(store)['recipe_revision'] == 1 and calls == []


def test_schema12_upgrade_and_api_packet_keep_source_and_run_ownership(setup, monkeypatch):
    from schema_helpers import remove_assistant_schema
    from provider_directory_truth_layer import mapping_assistant_api
    store, receipt, service, _ = setup
    with store.db() as conn:
        remove_assistant_schema(conn); conn.execute('PRAGMA user_version=12')
    reopened = IntakeStore(store.path, store.root)
    with sqlite3.connect(str(store.path) + '.pre-intake-v13.bak') as old:
        assert old.execute('PRAGMA user_version').fetchone()[0] == 12
    with reopened.db() as conn:
        assert conn.execute('PRAGMA user_version').fetchone()[0] == VERSION
    monkeypatch.setattr(mapping_assistant_api, 'MappingAssistant', lambda _store: service)
    client = TestClient(create_workbench(store.path, store.root))
    run = create(service, receipt)
    assert client.get(f"/api/intakes/{receipt['id']}/assistant-runs").status_code == 200
    assert client.get(f"/api/intakes/wrong/assistant-runs/{run['id']}").status_code == 404
    downloaded = client.get(f"/api/intakes/{receipt['id']}/assistant-runs/{run['id']}/artifacts/request")
    assert hashlib.sha256(downloaded.content).hexdigest() == run['request_sha']
    result = client.post(f"/api/intakes/{receipt['id']}/assistant-runs/{run['id']}/run-once").json()
    assert result['state'] == 'succeeded'
    packet = client.get(f"/api/intakes/{receipt['id']}/packet").json()
    assert packet['assistant_runs'][0]['proposal_id'] == result['proposal_id']
    assert 'synthetic-provider-key' not in packed(packet)
