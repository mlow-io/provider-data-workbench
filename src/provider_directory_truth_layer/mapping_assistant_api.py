"""Receipt-scoped optional model runs; proposal authority only."""
from fastapi.responses import FileResponse

from .mapping_assistant import MappingAssistant


def mount(app, store):
    service = MappingAssistant(store)

    @app.get('/api/intakes/{receipt_id}/assistant-runs')
    def list_runs(receipt_id: str):
        return service.list(receipt_id)

    @app.post('/api/intakes/{receipt_id}/assistant-runs')
    def create_run(receipt_id: str, payload: dict):
        return service.create(receipt_id, payload)

    @app.get('/api/intakes/{receipt_id}/assistant-runs/{run_id}')
    def detail(receipt_id: str, run_id: str):
        return service.detail(receipt_id, run_id)

    @app.post('/api/intakes/{receipt_id}/assistant-runs/{run_id}/run-once')
    def run_once(receipt_id: str, run_id: str):
        return service.run_once(receipt_id, run_id)

    @app.post('/api/intakes/{receipt_id}/assistant-runs/{run_id}/cancel')
    def cancel(receipt_id: str, run_id: str, payload: dict):
        return service.cancel(receipt_id, run_id, payload)

    @app.get('/api/intakes/{receipt_id}/assistant-runs/{run_id}/artifacts/{kind}')
    def artifact(receipt_id: str, run_id: str, kind: str):
        if kind not in {'request', 'response'}:
            raise KeyError('Choose request or response artifact')
        packet = service.detail(receipt_id, run_id)
        sha = packet[kind + '_sha']
        if not sha:
            raise KeyError('No retained artifact for this stage')
        service._read(sha)
        return FileResponse(store.artifacts / sha, filename=f'mapping-{kind}.json', media_type='application/json')
