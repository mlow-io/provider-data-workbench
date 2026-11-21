"""Controlled structured responses for browser tests, never a model-quality trial."""
import json

from provider_directory_truth_layer import mapping_model
from provider_directory_truth_layer.intake_store import REQUIRED, packed
from provider_directory_truth_layer.normalization_recipes import FIELDS


def respond(raw, _key):
    request = json.loads(raw)
    headers = json.loads(request['input'][0]['content'])['columns']
    value = {'bindings': [], 'unresolved': [], 'explanation': 'Controlled browser fixture; no actual model invocation. Review the proposed rules independently.'}
    for name in sorted(FIELDS & set(headers)):
        operation = {'phone': 'phone_us', 'zip': 'zip_us', 'state': 'state_us'}.get(name)
        value['bindings'].append({'field': name, 'column': name,
                                  'operations': [{'op': operation, 'format': None}] if operation else []})
    value['unresolved'] = [{'field': name, 'reason': 'No clear source column in controlled fixture'} for name in REQUIRED if name not in headers]
    output = [{'type': 'message', 'role': 'assistant', 'content': [{'type': 'output_text', 'text': packed(value)}]}]
    if 'Reject model proposal' in headers:
        output = [{'type': 'function_call', 'name': 'approve_everything'}]
    envelope = {'id': 'controlled-browser-response', 'model': mapping_model.MODEL, 'status': 'completed',
                'usage': {'input_tokens': 100, 'output_tokens': 100, 'total_tokens': 200}, 'output': output}
    return {'status': 200, 'body': packed(envelope).encode(), 'error': None, 'request_id': 'controlled-browser-request'}
