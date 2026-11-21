"""Build owned 100/1,000-row synthetic feeds and serve actual application APIs."""
import argparse
import csv
import hashlib
import io
import json
from pathlib import Path
import socket
import time

import uvicorn
from provider_directory_truth_layer.intake_store import IntakeStore
from provider_directory_truth_layer.managed_feed import ManagedFeed
from provider_directory_truth_layer.onboarding_service import OnboardingService
from provider_directory_truth_layer.intake_api import create_workbench

FIELDS = ['record_id', 'npi', 'provider_name', 'address', 'city', 'state', 'zip', 'phone', 'location_id']
ATTR = {'actor': 'Synthetic qualification operator', 'reason': 'Explicit synthetic performance fixture approval'}


def seed(root):
    if root.exists():
        raise ValueError('Qualification root must be new; existing storage is never reused')
    root.mkdir(parents=True)
    store = IntakeStore(root / 'directory.sqlite3', root)
    service = ManagedFeed(store)
    reports = []
    for count in (100, 1000):
        source = f'synthetic-qualification-{count}'
        text = io.StringIO()
        writer = csv.writer(text); writer.writerow(FIELDS)
        for i in range(count):
            writer.writerow([f'ROW-{i:05}', f'{1000000000+i//2}', f'Synthetic Provider {i//2:04} — Long Practice Group', f'{100+i//2} Example Street Suite {i%2+1}', 'Nashville', 'TN', '03701', f'615555{i%10000:04}', f'OFFICE-{i:05}'])
        payload = text.getvalue().encode()
        receipt = store.receive(payload, 'profile.csv', source=source, metadata={'scope': source})
        onboarding = OnboardingService(store)
        proposed = onboarding.propose(receipt['id'], {'name': source, 'definition': {'version': 1, 'mapping': dict(zip(FIELDS, FIELDS)), 'required': FIELDS, 'transforms': {'phone': ['phone_us']}}, 'expected_attempt': receipt['attempt_id'], **ATTR})
        recipe = onboarding.approve(receipt['id'], proposed['id'], {'expected_attempt': receipt['attempt_id'], **ATTR})
        inbox = root / f'inbox-{count}'; inbox.mkdir()
        feed = service.register({'name': f'Synthetic {count}-record roster', 'source': source, 'scope': source, 'owner': 'Synthetic operator', 'inbox': str(inbox), 'start_date': '2026-10-05', **ATTR})
        contract = service.propose_contract(feed['id'], {'definition': {'recipe_revision_id': recipe['id'], 'required_headers': FIELDS}, **ATTR})
        contract = service.approve_contract(feed['id'], contract['id'], ATTR)
        service.configure(feed['id'], {'expected_revision': feed['revision'], 'config': {'contract_id': contract['id'], 'enabled': True}, **ATTR})
        (inbox / 'roster.csv').write_bytes(payload)
        (inbox / 'roster.manifest.json').write_text(json.dumps({'delivery_id': f'qualification-{count}', 'period': '2026-10-05', 'as_of': '2026-10-05', 'snapshot': 'full', 'filename': 'roster.csv', 'sha256': hashlib.sha256(payload).hexdigest()}))
        result = service.run_once(feed['id'])
        version = service.version(result['version_id'])
        if version['report']['counts']['valid'] != count:
            raise ValueError(f'Fixture did not produce {count} valid rows: {version["report"]["counts"]}')
        service.decide(version['id'], {'decision': 'approved', 'expected_report': version['report_hash'], 'expected_current': version['current_version'], 'idempotency_key': f'approve-{count}', **ATTR})
        reports.append({'count': count, 'feed_id': feed['id'], 'version_id': version['id']})
    return store, reports


if __name__ == '__main__':
    parser = argparse.ArgumentParser(); parser.add_argument('--root', type=Path, required=True); parser.add_argument('--corrected', action='store_true'); args = parser.parse_args()
    store, fixtures = seed(args.root)
    if args.corrected:
        from corrections import qualify
        for fixture in fixtures:
            qualify(store, fixture)
            fixture['version_id'] = ManagedFeed(store).current(fixture['feed_id'])['version_id']
            fixture['corrected'] = True
    app = create_workbench(store.path, store.root, demo=False)
    @app.middleware('http')
    async def timing(request, call_next):
        start = time.perf_counter(); response = await call_next(request)
        response.headers['Server-Timing'] = f'app;dur={(time.perf_counter()-start)*1000:.2f}'
        return response
    @app.get('/__qualification')
    def report():
        return {'fixtures': fixtures}
    with socket.socket() as listener:
        listener.bind(('127.0.0.1', 0)); listener.listen(128)
        print(f'QUALIFICATION_API=http://127.0.0.1:{listener.getsockname()[1]}', flush=True)
        uvicorn.Server(uvicorn.Config(app, log_level='warning')).run(sockets=[listener])
