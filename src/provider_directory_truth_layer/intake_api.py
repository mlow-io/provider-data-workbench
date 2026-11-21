"""One HTTP application for intake and existing review routes."""
from __future__ import annotations

import csv
import io
import os
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, JSONResponse, Response
from starlette.concurrency import run_in_threadpool

from .intake_store import IntakeStore, Conflict, MAX_BYTES
from .storage import database_path, storage_root
from .review_api import create_app
from .remediation_api import create_remediation_app


def create_workbench(path: Path | None = None, root: Path | None = None, *, demo: bool | None = None) -> FastAPI:
    path = path or database_path()
    store = IntakeStore(path, root or storage_root())
    app = create_app(path)
    from .fhir_acquisition_api import mount as mount_acquisitions
    mount_acquisitions(app, store)
    from .mapping_assistant_api import mount as mount_assistance
    mount_assistance(app, store)
    from .feed_api import mount as mount_feeds
    mount_feeds(app, store)
    from .onboarding_service import OnboardingService
    onboarding = OnboardingService(store)
    from .reconciliation_store import ReconciliationStore
    reconciliation = ReconciliationStore(store)

    from .identity_review import IdentityReview
    identity_review = IdentityReview(store)

    from .field_reconciliation import FieldReconciliation, workbook as reconciled_workbook
    fields = FieldReconciliation(store)

    from .change_impact import ChangeImpact
    impact = ChangeImpact(store)

    from .follow_up import FollowUp
    from .follow_up_export import workbook as follow_up_workbook
    follow_up = FollowUp(store)

    @app.post('/api/reconciliation/follow-up-preview')
    def follow_up_preview(payload: dict):
        if set(payload) - {'proposal_id','case_choices','offset','limit'} or not isinstance(payload.get('proposal_id'),str):
            raise ValueError('Select proposal_id and optional case_choices/offset/limit')
        return follow_up.preview(payload['proposal_id'],payload.get('case_choices'),payload.get('offset',0),payload.get('limit',20))

    @app.post('/api/reconciliation/follow-up')
    def confirm_follow_up(payload: dict):
        return follow_up.confirm(payload)

    @app.get('/api/reconciliation/follow-up')
    def confirmed_follow_ups(proposal_id: str | None = None, offset: int = 0, limit: int = 20):
        return follow_up.list(proposal_id,offset,limit)

    @app.get('/api/reconciliation/follow-up/{confirmation_id}')
    def confirmed_follow_up(confirmation_id: str, offset: int = 0, limit: int = 20):
        return follow_up.get(confirmation_id,offset,limit)

    @app.post('/api/reconciliation/follow-up/{confirmation_id}/acknowledge')
    def acknowledge_follow_up(confirmation_id: str, payload: dict):
        return follow_up.acknowledge(confirmation_id,payload)

    @app.get('/api/reconciliation/follow-up/{confirmation_id}/acknowledgements')
    def follow_up_acknowledgements(confirmation_id: str, association_id: str | None = None, offset: int = 0, limit: int = 20):
        return follow_up.acknowledgements(confirmation_id,association_id,offset,limit)

    @app.get('/api/reconciliation/follow-up/{confirmation_id}/export')
    def export_follow_up(confirmation_id: str, expected_snapshot: str, format: str = 'json'):
        if format not in {'json','xlsx'}:raise ValueError('Choose json or xlsx')
        data=follow_up.export(confirmation_id,expected_snapshot)
        headers={'Content-Disposition':'attachment; filename=follow-up-plan.'+format}
        if format=='xlsx':return Response(follow_up_workbook(data),media_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',headers=headers)
        return JSONResponse(data,headers=headers)

    @app.post('/api/reconciliation/change-proposals')
    def create_change_proposal(payload: dict):
        return impact.create(payload)

    @app.get('/api/reconciliation/change-proposals')
    def list_change_proposals(clinician_id: str | None = None, location_id: str | None = None, offset: int = 0, limit: int = 20):
        return impact.list(clinician_id, location_id, offset, limit)

    @app.get('/api/reconciliation/change-proposals/{proposal_id}')
    def change_proposal(proposal_id: str):
        return impact.get(proposal_id)

    @app.post('/api/reconciliation/impact-preview')
    def impact_preview(payload: dict):
        if set(payload) - {'proposal_id', 'offset', 'limit', 'work_offset'} or not isinstance(payload.get('proposal_id'), str):
            raise ValueError('Select proposal_id and optional offset/limit/work_offset')
        return impact.preview(payload['proposal_id'], payload.get('offset', 0), payload.get('limit', 20), payload.get('work_offset', 0))

    @app.get('/api/reconciliation/fields/{clinician_id}')
    def reconciled_fields(clinician_id: str, location_id: str | None = None, offset: int = 0, limit: int = 20, history_offset: int = 0):
        return fields.inspect(clinician_id, location_id, offset, limit, history_offset)

    @app.post('/api/reconciliation/field-decisions')
    def decide_reconciled_field(payload: dict):
        return fields.decide(payload)

    @app.get('/api/reconciliation/identities/clinician/{clinician_id}/export')
    def export_reconciled_fields(clinician_id: str, expected_snapshot: str, location_id: str | None = None, format: str = 'json'):
        if format not in {'json', 'xlsx'}:
            raise ValueError('Choose json or xlsx')
        data = fields.export(clinician_id, location_id, expected_snapshot)
        headers = {'Content-Disposition': 'attachment; filename=reconciled-fields.' + format}
        if format == 'xlsx':
            return Response(reconciled_workbook(data), media_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet', headers=headers)
        return JSONResponse(data, headers=headers)

    @app.get('/api/reconciliation/runs/{run_id}/candidates/{candidate_id}/review')
    def inspect_identity_review(run_id: str, candidate_id: str, offset: int = 0, limit: int = 20):
        return identity_review.inspect(run_id, candidate_id, offset, limit)

    @app.get('/api/reconciliation/targets/{kind}')
    def identity_targets(kind: str, search: str = '', offset: int = 0, limit: int = 20):
        return identity_review.targets(kind, search, offset, limit)

    @app.post('/api/reconciliation/links')
    def decide_identity_review(payload: dict):
        return identity_review.decide(payload)

    @app.get('/api/reconciliation/identities/{kind}/{identity_id}')
    def reviewed_identity(kind: str, identity_id: str, offset: int = 0, limit: int = 20, history_offset: int = 0):
        return identity_review.identity(kind, identity_id, offset, limit, history_offset)

    @app.get('/api/intakes/{receipt_id}/comparison-profile')
    def comparison_profile(receipt_id: str, expected_attempt: str, entity_kind: str = 'unknown', offset: int = 0, limit: int = 20):
        return reconciliation.preview_input(receipt_id, expected_attempt, entity_kind, offset, limit)

    @app.get('/api/reconciliation/runs')
    def comparison_runs(offset: int = 0, limit: int = 20):
        return reconciliation.runs(offset, limit)

    @app.post('/api/reconciliation/runs')
    def create_comparison_run(payload: dict):
        return reconciliation.create_run(payload)

    @app.get('/api/reconciliation/runs/{run_id}')
    def comparison_run(run_id: str):
        return reconciliation.run(run_id)

    @app.get('/api/reconciliation/runs/{run_id}/candidates')
    def comparison_candidates(run_id: str, kind: str | None = None, eligible: bool | None = None, offset: int = 0, limit: int = 20, reason: str | None = None, search: str | None = None):
        return reconciliation.candidates(run_id, kind, eligible, offset, limit, reason=reason, search=search)

    @app.get('/api/reconciliation/runs/{run_id}/candidates/export')
    def comparison_candidates_export(run_id: str, kind: str | None = None, eligible: bool | None = None, reason: str | None = None, search: str | None = None):
        return JSONResponse(reconciliation.export_candidates(run_id, kind, eligible, reason, search), headers={
            'Content-Disposition': 'attachment; filename=comparison-filtered-candidates.json'})

    @app.get('/api/reconciliation/runs/{run_id}/export')
    def comparison_export(run_id: str):
        return JSONResponse(reconciliation.export(run_id), headers={
            'Content-Disposition': 'attachment; filename=comparison-evidence.json'})
    demo_enabled = os.environ.get('PDTL_DEMO') == '1' if demo is None else demo
    # Keep existing route compatibility in the same process and database.
    for route in create_remediation_app(path).routes:
        if getattr(route, 'path', '').startswith('/api/remediation'):
            app.router.routes.append(route)

    @app.exception_handler(ValueError)
    async def invalid(request, exc):
        return JSONResponse({'detail': str(exc)}, status_code=409 if isinstance(exc, Conflict) else 422)

    @app.exception_handler(KeyError)
    async def missing(request, exc):
        return JSONResponse({'detail': str(exc)}, status_code=404)

    @app.get('/api/intakes')
    def inbox(offset: int | None = None, limit: int | None = None):
        return store.inbox(offset,limit)

    @app.post('/api/intakes/files')
    async def upload(request: Request, filename: str, source: str = 'clinic', designation: str = 'synthetic', profile: str = 'flat', dataset_scope: str | None = None, completeness: str = 'unknown', as_of: str | None = None):
        if completeness not in {'unknown','bounded','full'}:
            raise ValueError('Choose unknown, bounded or full declared completeness')
        if as_of:
            from datetime import date
            if date.fromisoformat(as_of).isoformat() != as_of:
                raise ValueError('as_of must use YYYY-MM-DD')
        if profile == 'fhir-plannet-r4' and completeness == 'full':
            raise ValueError('Saved FHIR searchsets cannot declare full-directory completeness')
        metadata = {'scope': dataset_scope, 'completeness': completeness, 'as_of': as_of}
        payload = bytearray()
        async for chunk in request.stream():
            payload.extend(chunk)
            if len(payload) > MAX_BYTES:
                raise ValueError('Artifact limit is 10 MiB')
        # Bounded parsing runs off the event loop, so receipt/status reads remain responsive.
        return bounded(await run_in_threadpool(store.receive, bytes(payload), filename, source, designation, profile, metadata))

    def bounded(result):
        # Full evidence is downloadable; interactive responses have bounded samples.
        if result.get('preview'):
            result['preview']['rows'] = result['preview']['rows'][:50]
        for attempt in result.get('attempts', []):
            attempt['preview']['rows'] = attempt['preview'].get('rows', [])[:50]
        for preview in [result.get('preview'), *[attempt.get('preview') for attempt in result.get('attempts', [])]]:
            if preview and preview.get('comparison', {}).get('entries') is not None:
                comparison = preview['comparison']
                comparison['entry_count'] = max(comparison.get('entry_count', 0), len(comparison['entries']))
                comparison['entries'] = comparison['entries'][:50]
        if result.get('profile') == 'fhir-plannet-r4':
            from .evidence_samples import sample_value, sample_rows
            seen_native = set()
            for preview in [result.get('preview'), *[a.get('preview') for a in result.get('attempts', [])]]:
                if preview and 'native' in preview and id(preview['native']) not in seen_native:
                    native = preview['native']
                    seen_native.add(id(native))
                    preview['rows'], preview['sample_truncated'] = sample_rows(preview.get('rows', []))
                    for key in ('resources', 'references', 'assertions', 'findings'):
                        native[key + '_count'] = len(native.get(key, []))
                        native[key], clipped = sample_value(native.get(key, [])[:50])
                        native['sample_truncated'] = native.get('sample_truncated', False) or clipped or native[key + '_count'] > 50
        for field in ['observations', 'linked_cases']:
            result[field + '_count'] = len(result.get(field, []))
            result[field] = result.get(field, [])[:50]
        if result.get('profile') == 'fhir-plannet-r4':
            result['observations'], clipped = sample_rows(result['observations'])
            result['sample_truncated'] = result.get('sample_truncated', False) or clipped
        return result

    @app.get('/api/demo/samples')
    def samples():
        from .demo_samples import SAMPLES
        return {'items': SAMPLES if demo_enabled else []}

    @app.post('/api/demo/network-setup')
    def prepare_network_demo():
        if not demo_enabled:
            raise HTTPException(404,'Synthetic network setup is disabled; use the offline demo launcher')
        from .demo_network import prepare
        return prepare(store)

    @app.post('/api/demo/samples/{sample_id}')
    def load_sample(sample_id: str):
        from .demo_samples import SAMPLES, WORKBOOK_MAPPING, sample_payloads
        if not demo_enabled:
            raise HTTPException(404, 'Synthetic sample loading is disabled; use the offline demo launcher')
        sample = next((s for s in SAMPLES if s['id'] == sample_id), None)
        if sample is None:
            raise KeyError('Unknown synthetic sample')
        metadata = {'demo_sample': sample_id, 'notice': 'SYNTHETIC offline example; no real clinicians or payer updates'}
        if sample_id == 'clinic-workbook':
            metadata['suggested_mapping'] = WORKBOOK_MAPPING
        # Distinct sources are required for cross-source review. Clinic versions
        # retain their shared namespace so repeated deliveries keep their history.
        source={'nppes':'synthetic-nppes-reference', 'cms':'synthetic-cms-reference'}.get(sample_id, 'synthetic-demo')
        if sample_id.startswith('network-'):
            from .demo_network import SOURCE,SCOPE,prepared_settings
            source=SOURCE
            metadata.update(scope=SCOPE,completeness='bounded',expected_roster_kind='network',as_of='2026-10-01' if sample_id=='network-baseline' else '2026-10-15')
            suggested=prepared_settings(store)
            if suggested:
                metadata['suggested_network_settings']=suggested
            else:
                metadata['demo_notice']='Prepare the synthetic network catalog explicitly, then load this sample again to review its suggested scope.'
        result = store.receive(sample_payloads()[sample_id], sample['filename'], source, 'synthetic', sample['profile'], metadata)
        if sample_id == 'clinic-workbook' and result['state'] == 'failed':
            result = store.mapping(result['id'], {'header_row': 2, 'sheet': 'Clinic roster'})
        return bounded(result)

    @app.get('/api/intakes/{receipt_id}')
    def detail(receipt_id: str, attempt_id: str | None = None):
        return bounded(store.detail(receipt_id, attempt_id=attempt_id))

    @app.get('/api/intakes/{receipt_id}/saved-mappings')
    def saved_mappings(receipt_id: str):
        return store.saved_mappings(receipt_id)

    @app.get('/api/intakes/{receipt_id}/profile')
    def profile_input(receipt_id: str, offset: int = 0, limit: int = 20):
        return onboarding.inspect(receipt_id, offset, limit)

    @app.post('/api/intakes/{receipt_id}/normalization/preview')
    def preview_recipe(receipt_id: str, payload: dict):
        return onboarding.preview(receipt_id, payload.get('definition'), payload.get('expected_attempt'),
                                  payload.get('offset', 0), payload.get('limit', 20))

    @app.get('/api/intakes/{receipt_id}/recipes')
    def recipes(receipt_id: str):
        return onboarding.recipes(receipt_id)

    @app.post('/api/intakes/{receipt_id}/recipes')
    def propose_recipe(receipt_id: str, payload: dict):
        return onboarding.propose(receipt_id, payload)

    @app.post('/api/intakes/{receipt_id}/recipes/{revision_id}/approve')
    def approve_recipe(receipt_id: str, revision_id: str, payload: dict):
        return onboarding.approve(receipt_id, revision_id, payload)

    @app.post('/api/intakes/{receipt_id}/recipes/{revision_id}/apply')
    def apply_recipe(receipt_id: str, revision_id: str, payload: dict):
        return bounded(onboarding.apply(receipt_id, revision_id, payload.get('expected_attempt')))

    @app.get('/api/intakes/{receipt_id}/dataset')
    def dataset(receipt_id: str):
        return JSONResponse(onboarding.dataset(receipt_id), headers={
            'Content-Disposition': 'attachment; filename=validated-dataset.json'})

    @app.post('/api/intakes/{receipt_id}/saved-mappings')
    def save_mapping(receipt_id: str, payload: dict):
        return store.save_mapping(receipt_id, payload)

    @app.post('/api/intakes/{receipt_id}/mapping')
    def mapping(receipt_id: str, payload: dict):
        return bounded(store.mapping(receipt_id, payload))

    @app.post('/api/intakes/{receipt_id}/commit')
    def commit(receipt_id: str, payload: dict):
        if not payload.get('expected_attempt'):
            raise ValueError('expected_attempt is required; accept the interpretation you previewed')
        return bounded(store.commit(receipt_id, payload))

    @app.get('/api/intakes/{receipt_id}/artifact')
    def artifact(receipt_id: str):
        receipt = store.detail(receipt_id)
        if not receipt['artifact_sha']:
            raise ValueError('Reference-only receipt has no fetched artifact')
        return FileResponse(store.artifacts / receipt['artifact_sha'], filename=receipt['label'])

    @app.get('/api/intakes/{receipt_id}/quarantine')
    def quarantine(receipt_id: str):
        receipt = store.detail(receipt_id)
        stream = io.StringIO()
        writer = csv.writer(stream)
        writer.writerow(['locator','problems','original'])
        for row in (receipt['preview'] or {}).get('rows', []):
            if row['problems']:
                from .intake_store import packed
                writer.writerow([row['locator'], '; '.join(row['problems']), packed(row['original'])])
        return Response(stream.getvalue(), media_type='text/csv', headers={'Content-Disposition': 'attachment; filename=quarantine.csv'})

    @app.get('/api/intakes/{receipt_id}/packet')
    def packet(receipt_id: str):
        receipt = store.detail(receipt_id)
        receipt['cases'] = [store.case(c['id']) for c in receipt['linked_cases']]
        from .mapping_assistant import MappingAssistant
        assistant = MappingAssistant(store)
        with store.db() as conn:
            runs = conn.execute('SELECT id FROM assistant_run WHERE receipt_id=? ORDER BY created_at,id', (receipt_id,)).fetchall()
        if runs:
            receipt['assistant_runs'] = [assistant.detail(receipt_id, row['id']) for row in runs]
        return JSONResponse(receipt, headers={'Content-Disposition': 'attachment; filename=evidence-packet.json'})

    @app.post('/api/intakes/lookups')
    def lookup(payload: dict):
        from .intake_adapters import fetch_public, PublicFetchError
        source = payload.get('source')
        query = payload.get('query', {})
        if not payload.get('refresh', False):
            from datetime import datetime, timezone, timedelta
            with store.db() as conn:
                candidates = [dict(r) for r in conn.execute('select * from receipt where source=? and artifact_sha is not null order by received_at desc', (source,))]
            import json
            for candidate in candidates:
                metadata = json.loads(candidate['metadata'])
                if metadata.get('lookup_query') == query and not metadata.get('error') and datetime.fromisoformat(candidate['received_at']) > datetime.now(timezone.utc) - timedelta(minutes=15):
                    return store.receive((store.artifacts / candidate['artifact_sha']).read_bytes(), candidate['label'], source, 'public', candidate['profile'], {**metadata, 'cache_status':'retained_response', 'replayed_from':candidate['id']})
        try:
            fetched = fetch_public(source, payload.get('query', {}))
        except PublicFetchError as exc:
            if exc.payload:
                receipt = store.receive(exc.payload, exc.label + '.json', source, 'public', exc.profile, exc.metadata)
                with store.db() as conn:
                    conn.execute("update attempt set state='failed' where receipt_id=?", (receipt['id'],))
            else:
                receipt = store.link({'url': exc.metadata.get('request_url', 'https://data.cms.gov/'), 'title': exc.label, 'source': source, **exc.metadata})
            return JSONResponse({**store.detail(receipt['id']), 'state': 'failed', 'detail': str(exc)}, status_code=422)
        except ValueError as exc:
            receipt = store.link({'url': 'https://npiregistry.cms.hhs.gov/' if source == 'nppes' else 'https://data.cms.gov/', 'title': 'Failed ' + str(source) + ' lookup', 'source': str(source), 'observed_at': '', 'error': str(exc), 'query': payload.get('query', {})})
            return JSONResponse({**receipt, 'state': 'failed', 'detail': str(exc)}, status_code=422)
        return bounded(store.receive(fetched['payload'], fetched['label'] + '.json', source, 'public', fetched['profile'], {**fetched['metadata'], 'lookup_query':query}))

    @app.post('/api/intakes/links')
    def link(payload: dict):
        return store.link(payload)

    @app.get('/api/sources')
    def sources():
        items = []
        with store.db() as conn:
            for source in ['nppes','cms']:
                rows = [dict(r) for r in conn.execute('select * from receipt where source=? order by received_at desc', (source,))]
                import json
                success = next((r for r in rows if r['artifact_sha'] and not json.loads(r['metadata']).get('error')), None)
                failure = next((r for r in rows if json.loads(r['metadata']).get('error')), None)
                items.append({'source': source, 'adapter_version': '1', 'scope': 'Bounded public reference; not certified truth or complete directory', 'last_success': success['received_at'] if success else None, 'last_failure': json.loads(failure['metadata']) if failure else None, 'metadata': json.loads(success['metadata']) if success else {}})
        return {'items': items}

    @app.get('/api/catalog')
    def catalog():
        return store.catalog()

    @app.post('/api/catalog/bindings')
    def bind_source(payload: dict):
        return store.bind_source(payload)

    @app.post('/api/catalog/{kind}')
    def create_catalog(kind: str, payload: dict):
        return store.create_catalog(kind, payload)

    @app.get('/api/work')
    def work(network_id: str | None = None, organization_id: str | None = None, location_id: str | None = None):
        return store.work(network_id,organization_id,location_id)

    @app.get('/api/work-export.xlsx')
    def work_export(case_id: str | None = None, network_id: str | None = None):
        from .work_export import handoff_workbook
        return Response(handoff_workbook(store.path, case_id, network_id),
            media_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
            headers={'Content-Disposition': 'attachment; filename=durable-work-handoff.xlsx'})

    @app.get('/api/work-export.json')
    def work_export_json(case_id: str | None = None, network_id: str | None = None):
        from .work_export import snapshot
        return JSONResponse(snapshot(store.path,case_id,network_id),
            headers={'Content-Disposition':'attachment; filename=durable-work-handoff.json'})

    @app.get('/api/work/{case_id}')
    def case(case_id: str):
        return store.case(case_id)

    @app.post('/api/work/{case_id}/events')
    def event(case_id: str, payload: dict):
        return store.event(case_id, payload)

    @app.post('/api/relationships')
    def relationship(payload: dict):
        return store.relationship(payload)

    return app


def run():
    import argparse
    import uvicorn
    parser = argparse.ArgumentParser()
    parser.add_argument('--port', type=int, default=8000)
    args = parser.parse_args()
    uvicorn.run(create_workbench(), host='127.0.0.1', port=args.port)


if __name__ == '__main__':
    run()
