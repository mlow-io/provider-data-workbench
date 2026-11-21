"""Local acquisition operations; source URLs are never accepted in payloads."""
from fastapi.responses import FileResponse

from .fhir_acquisition import Acquisition


def mount(app, store):
    service = Acquisition(store)

    @app.get('/api/fhir-acquisitions')
    def list_acquisitions():
        return service.list()

    @app.post('/api/fhir-acquisitions')
    def create_acquisition(payload: dict):
        return service.create(payload)

    @app.get('/api/fhir-acquisitions/{acquisition_id}')
    def acquisition(acquisition_id: str):
        return service.detail(acquisition_id)

    @app.post('/api/fhir-acquisitions/{acquisition_id}/run-once')
    def run_once(acquisition_id: str):
        return service.run_once(acquisition_id)

    @app.post('/api/fhir-acquisitions/{acquisition_id}/cancel')
    def cancel(acquisition_id: str, payload: dict):
        return service.cancel(acquisition_id, payload)

    @app.get('/api/fhir-acquisitions/{acquisition_id}/events/{sequence}/artifact')
    def response_artifact(acquisition_id: str, sequence: int):
        service.detail(acquisition_id)
        with store.db() as conn:
            row=conn.execute('SELECT artifact_sha FROM fhir_acquisition_event WHERE acquisition_id=? AND seq=?', (acquisition_id,sequence)).fetchone()
            if row is None or row['artifact_sha'] is None:
                raise KeyError('Retained response body not found')
        return FileResponse(store.artifacts/row['artifact_sha'],filename=f'response-{sequence}.bin',media_type='application/octet-stream')
