"""Managed-feed HTTP adapter; application state transitions live in ManagedFeed."""
from fastapi.responses import JSONResponse, Response
from .managed_feed import ManagedFeed


def mount(app, store):
    feeds = ManagedFeed(store)

    @app.get('/api/feeds')
    def list_feeds():
        return feeds.list()

    @app.get('/api/feeds/recipes')
    def approved_recipes():
        return feeds.recipes()

    @app.post('/api/feeds')
    def register(payload: dict):
        return feeds.register(payload)

    @app.get('/api/feeds/{feed_id}')
    def detail(feed_id: str):
        return feeds.detail(feed_id)

    @app.post('/api/feeds/{feed_id}/contracts')
    def propose(feed_id: str, payload: dict):
        return feeds.propose_contract(feed_id, payload)

    @app.post('/api/feeds/{feed_id}/contracts/{contract_id}/approve')
    def approve_contract(feed_id: str, contract_id: str, payload: dict):
        return feeds.approve_contract(feed_id, contract_id, payload)

    @app.post('/api/feeds/{feed_id}/configure')
    def configure(feed_id: str, payload: dict):
        return feeds.configure(feed_id, payload)

    @app.post('/api/feeds/{feed_id}/tick')
    def tick(feed_id: str):
        feeds.run_once(feed_id)
        return feeds.detail(feed_id)

    @app.get('/api/feeds/{feed_id}/current')
    def current(feed_id: str):
        return feeds.current(feed_id)

    @app.get('/api/feed-versions/{version_id}')
    def version(version_id: str):
        return feeds.version(version_id)

    @app.get('/api/feed-versions/{version_id}/field-materialization')
    def field_materialization_choices(version_id: str, offset: int = 0, limit: int = 20):
        from .field_materialization import FieldMaterialization
        return FieldMaterialization(store).choices(version_id, offset, limit)

    @app.post('/api/feed-versions/{version_id}/field-materialization')
    def create_field_materialization(version_id: str, payload: dict):
        from .field_materialization import FieldMaterialization
        return feeds.version(FieldMaterialization(store).create(version_id, payload))

    @app.post('/api/feed-versions/{version_id}/exceptions')
    def review(version_id: str, payload: dict):
        return feeds.review(version_id, payload)

    @app.post('/api/feed-versions/{version_id}/decide')
    def decide(version_id: str, payload: dict):
        return feeds.decide(version_id, payload)

    @app.get('/api/feed-versions/{version_id}/export')
    def export(version_id: str):
        return JSONResponse(feeds.export(version_id), headers={'Content-Disposition': f'attachment; filename=approved-dataset-{version_id}.json'})

    @app.get('/api/feed-versions/{version_id}/review-preview')
    def review_preview(version_id: str, location_id: str | None = None, expected_snapshot: str | None = None, limit: int = 5):
        from .review_workbook import preview
        return preview(store.path, version_id, location_id, expected_snapshot, limit)

    @app.get('/api/feed-versions/{version_id}/review-export')
    def review_export(version_id: str, format: str = 'json', location_id: str | None = None, expected_snapshot: str | None = None):
        from .review_workbook import snapshot, workbook
        if format not in {'json', 'xlsx'}:
            raise ValueError('Choose json or xlsx')
        if format == 'xlsx' and expected_snapshot is None:
            raise ValueError('Preview export and provide expected_snapshot before downloading')
        data = snapshot(store.path, version_id, location_id, expected_snapshot)
        if format == 'json':
            return data
        return Response(workbook(data), media_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet', headers={'Content-Disposition': f'attachment; filename=reviewed-directory-{version_id}.xlsx'})

    @app.post('/api/feed-jobs/{job_id}/{action}')
    def job_action(job_id: str, action: str, payload: dict):
        return feeds.job_action(job_id, action, payload)
