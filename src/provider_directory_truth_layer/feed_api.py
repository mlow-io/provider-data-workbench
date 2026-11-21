"""Managed-feed HTTP adapter; application state transitions live in ManagedFeed."""
from fastapi.responses import JSONResponse
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

    @app.post('/api/feed-versions/{version_id}/exceptions')
    def review(version_id: str, payload: dict):
        return feeds.review(version_id, payload)

    @app.post('/api/feed-versions/{version_id}/decide')
    def decide(version_id: str, payload: dict):
        return feeds.decide(version_id, payload)

    @app.get('/api/feed-versions/{version_id}/export')
    def export(version_id: str):
        return JSONResponse(feeds.export(version_id), headers={'Content-Disposition': f'attachment; filename=approved-dataset-{version_id}.json'})

    @app.post('/api/feed-jobs/{job_id}/{action}')
    def job_action(job_id: str, action: str, payload: dict):
        return feeds.job_action(job_id, action, payload)
