"""One retained synthetic source-to-consumer journey; no public/model requests."""
from __future__ import annotations

import copy
import csv
import io
import json
import os
import re
import subprocess
import sys
import threading
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from openpyxl import Workbook, load_workbook

from .approved_consumer import canonical, consume, sha
from .bundled_assets import assets
from .field_reconciliation import FieldReconciliation, workbook as field_workbook
from .fhir_acquisition import Acquisition, Source
from .fhir_intake import parse_bundle
from .identity_review import IdentityReview
from .intake_store import IntakeStore, packed
from .managed_feed import ManagedFeed
from .mapping_assistant import Configuration, MappingAssistant
from .onboarding_service import OnboardingService
from .reconciliation_store import ReconciliationStore
from .storage_backup import backup, restore, verify
from .work_export import handoff_workbook, snapshot

SOURCE = 'synthetic-operations-clinic'
SCOPE = 'weekly-full-roster'
ATTR = {'actor': 'Synthetic operations reviewer', 'reason': 'Explicit review of synthetic source evidence'}
HEADERS = ['Record Key', 'NPI', 'Clinician Name', 'Office Address', 'City', 'State', 'Postal',
           'Office Tel', 'Telephone', 'Office Key', 'Directory Phone', 'entity_type']
MAPPING = dict(zip(('record_id', 'npi', 'provider_name', 'address', 'city', 'state', 'zip', 'phone'), HEADERS[:8]))
MAPPING.update(location_id='Office Key', reference_phone='Directory Phone')
ROWS = [
    ['SYN-001', '1000000001', '  Synthetic   Clinician ', '10 Example St', 'Example', ' ma ', '02108', '+1 (617) 555-0100 ext 007', '6175550998', 'NORTH', '6175550199', 'clinician'],
    ['SYN-001', '1000000001', '  Synthetic   Clinician ', '20 Example St', 'Example', ' ma ', '02108', '+1 (617) 555-0200 ext 008', '6175550998', 'SOUTH', '6175550299', 'clinician'],
]
RECIPE = {'version': 1, 'mapping': MAPPING, 'required': list(MAPPING),
          'transforms': {'provider_name': ['trim', 'collapse_spaces'], 'phone': ['phone_us'],
                         'reference_phone': ['phone_us'], 'zip': ['zip_us'], 'state': ['state_us']}}


def require(condition, message):
    if not condition:
        raise RuntimeError(message)


def rejected(operation, label):
    try:
        operation()
    except ValueError as exc:
        return {'action': label, 'rejected': True, 'reason': str(exc)}
    raise RuntimeError(label + ' unexpectedly succeeded')


def write_json(path, value):
    with path.open('x', encoding='utf-8') as stream:
        stream.write(json.dumps(value, indent=2, ensure_ascii=False, allow_nan=False) + '\n')


def workbook_bytes():
    output = io.BytesIO(); book = Workbook(); sheet = book.active; sheet.title = 'Clinic'
    sheet.append(HEADERS)
    for row in [ROWS[0], ROWS[1], ROWS[0]]:
        values = list(row); values[6] = 2108; sheet.append(values)
        sheet.cell(sheet.max_row, 7).number_format = '00000'
    book.save(output); book.close()
    return output.getvalue()


def csv_bytes(rows):
    output = io.StringIO(); writer = csv.writer(output); writer.writerow(HEADERS); writer.writerows(rows)
    return output.getvalue().encode()


def deliver(inbox, name, rows, period):
    raw = csv_bytes(rows); filename = name + '.csv'; (inbox / filename).write_bytes(raw)
    manifest = {'delivery_id': name, 'period': period, 'as_of': period, 'snapshot': 'full', 'filename': filename, 'sha256': sha(raw)}
    write_json(inbox / (name + '.manifest.json'), manifest)
    return raw


def approve_version(feeds, version_id):
    version = feeds.version(version_id)
    return feeds.decide(version_id, {'decision': 'approved', 'expected_report': version['report_hash'],
        'expected_current': version['current_version'], 'idempotency_key': version_id, **ATTR})


def bundle():
    value = json.loads(assets().joinpath('operations/north-south.json').read_bytes())
    value['entry'][0]['resource']['identifier'].append({'system': 'http://hl7.org/fhir/sid/us-npi', 'value': '1000000001'})
    value['entry'][3]['resource']['telecom'][0]['value'] = '6175550199'
    value['entry'][4]['resource']['telecom'][0]['value'] = '6175550200'
    value['entry'].append({'resource': {'resourceType': 'Location', 'id': 'malformed-location', 'address': 7}})
    return value


@contextmanager
def controlled_source(saved):
    """Private loopback server owned by this invocation; no endpoint input."""
    seen = []; graph = copy.deepcopy(saved)
    graph['entry'] = [entry for entry in graph['entry'] if entry['resource']['id'] != 'unresolved-role']
    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            seen.append(self.path)
            code, headers, raw = 200, {'Content-Type': 'application/fhir+json'}, b'{'  # malformed route
            count = self.path.split('_count=')[-1] if self.path.startswith('/Location/?_count=') else None
            if count == '2':
                code, headers, raw = 429, {'Retry-After': '60'}, b'Synthetic rate limit'
            elif count in {'1', '3', '4'}:
                target = '/?_getpages=complete' if count == '1' else '/?_getpages=broken' if count == '3' else 'https://outside.example.invalid/Patient/'
                raw = packed({**graph, 'entry': graph['entry'][:3], 'link': [{'relation': 'next', 'url': target}]}).encode()
            elif self.path == '/?_getpages=complete':
                raw = packed({**graph, 'entry': graph['entry'][3:]}).encode()
            self.send_response(code)
            for key, value in headers.items(): self.send_header(key, value)
            self.end_headers(); self.wfile.write(raw)
        def log_message(self, *_args): pass
    server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
    source = Source(key='synthetic-operations-payer', base=f'http://127.0.0.1:{server.server_port}/',
                    plan_net_version='Synthetic Plan-Net subset; conformance unverified', interval_seconds=0, test_http=True)
    for entry in graph['entry']:
        resource = entry['resource']; entry['fullUrl'] = source.base + resource['resourceType'] + '/' + resource['id']
    thread = threading.Thread(target=server.serve_forever, daemon=True); thread.start()
    try: yield source, seen
    finally: server.shutdown(); server.server_close(); thread.join()


def capture(acquisition, request_id, count):
    run = acquisition.create({'request_id': request_id, 'resource_type': 'Location', 'count': count, **ATTR})
    for _ in range(10):
        run = acquisition.run_once(run['id'])
        if run['state'] in {'complete', 'failed', 'retry_wait', 'cancelled'}: return run
    raise RuntimeError('Controlled capture did not reach a bounded outcome')


def link(review, comparison, run_id, left_receipt, right_receipt, kind, label, target_id=None, office=None):
    candidates = comparison.candidates(run_id, kind=kind, limit=100)['items']
    choices = [candidate for candidate in candidates if
               {candidate['left_record']['receipt_id'], candidate['right_record']['receipt_id']} == {left_receipt['id'], right_receipt['id']}]
    if office:
        line = '10 example st' if office == 'NORTH' else '20 example st'
        choices = [candidate for candidate in choices if all(candidate[side]['comparison']['address']['line1'] == line for side in ('left_record', 'right_record'))]
    require(bool(choices), 'Expected exact typed source candidate is missing: ' + label)
    candidate = choices[0]; context = review.inspect(run_id, candidate['id'])
    payload = {'run_id': run_id, 'candidate_id': candidate['id'], 'decision': 'approve',
        'request_id': uuid.uuid4().hex, 'expected_snapshot': context['review_snapshot'],
        'expected_revisions': {ref: current['id'] if current else None for ref, current in context['current_links'].items()},
        'expected_decision': context['latest_decision']['id'] if context['latest_decision'] else None, **ATTR}
    payload.update({'target_id': target_id} if target_id else {'new_label': label})
    return review.decide(payload)['decision']['target_id']


def xlsx_payload(raw, sheet='Payload'):
    book = load_workbook(io.BytesIO(raw), read_only=True, data_only=False)
    try:
        chunks = sorted(book[sheet].iter_rows(min_row=2, values_only=True), key=lambda row: int(row[0]))
        return json.loads(''.join(row[1] for row in chunks))
    finally: book.close()


def stable_work(packet):
    packet = copy.deepcopy(packet); packet.pop('snapshot_at', None)
    return packet


def work_payloads(raw):
    book = load_workbook(io.BytesIO(raw), read_only=True, data_only=False)
    try:
        groups = {}
        for payload_id, part, chunk in book['Payloads'].iter_rows(min_row=2, values_only=True):
            groups.setdefault(payload_id, []).append((int(part), chunk))
        return {key: json.loads(''.join(chunk for _part, chunk in sorted(parts))) for key, parts in groups.items()}
    finally: book.close()


def verify_origins(store, packet, receipt_id):
    contexts = {item['row']['locator']: item['row']['original'] for item in packet['source_context'] if item['receipt']['id'] == receipt_id}
    checked = 0
    for field in packet['fields']:
        for option in field['options']:
            if option['receipt_id'] != receipt_id: continue
            for ref in option.get('supporting_refs', []):
                require(bool(ref.get('source_pages')), 'Acquired support reference has no original page')
                for origin in ref['source_pages']:
                    raw = (store.artifacts / origin['artifact_sha']).read_bytes()
                    require(sha(raw) == origin['artifact_sha'], 'Retained HTTP response digest differs')
                    original = json.loads(raw)
                    match = re.fullmatch(r'\$\.entry\[([0-9]+)\]\.resource', origin['locator'])
                    resource = original['entry'][int(match[1])]['resource'] if match else original if origin['locator'] == '$' else None
                    require(resource == contexts[ref['locator']], 'Assembled resource does not equal its original page resource')
                    checked += 1
    require(checked > 0, 'No acquired original-page references were checked')
    return checked


def rehearse(root: Path):
    if root.exists() or root.is_symlink(): raise ValueError('Choose a new operations root; existing storage is preserved')
    root = root.resolve()
    root.mkdir(parents=False)
    inputs, exports, inbox = (root / name for name in ('inputs', 'exports', 'inbox'))
    for folder in (inputs, exports, inbox): folder.mkdir()
    store = IntakeStore(root / 'storage/directory.sqlite3', root / 'storage')
    expected = json.loads(assets().joinpath('operations/expected.json').read_bytes())
    onboarding = OnboardingService(store)
    raw_workbook = workbook_bytes(); (inputs / 'clinic.xlsx').write_bytes(raw_workbook)
    original = store.receive(raw_workbook, 'clinic.xlsx', source=SOURCE, metadata={'scope': SCOPE})
    profile = onboarding.inspect(original['id'], limit=100)
    require('phone' not in profile['suggested_mapping'] and len(profile['mapping_candidates']['phone']) == 2, 'Ambiguous phone headers were silently resolved')
    bad_recipe = copy.deepcopy(RECIPE); bad_recipe['transforms']['phone'] = ['execute_code']
    invalid = rejected(lambda: onboarding.propose(original['id'], {'name': 'Rejected invalid rules', 'definition': bad_recipe, 'expected_attempt': original['attempt_id'], **ATTR}), 'unsupported recipe')
    proposal = onboarding.propose(original['id'], {'name': 'Reviewed synthetic clinic rules', 'definition': RECIPE, 'expected_attempt': original['attempt_id'], **ATTR})
    approved = onboarding.approve(original['id'], proposal['id'], {'expected_attempt': original['attempt_id'], **ATTR})
    cleaned = onboarding.apply(original['id'], approved['id'], original['attempt_id'])
    require((cleaned['preview']['valid_count'], cleaned['preview']['quarantined_count']) == (expected['workbook']['valid'], expected['workbook']['quarantined']), 'Workbook duplicate quarantine disagrees with authored expectations')
    workbook_receipt = store.commit(original['id'], {'expected_attempt': cleaned['attempt_id'], 'policy': 'valid_rows', **ATTR})
    disabled = MappingAssistant(store, configuration=Configuration())
    unavailable = disabled.create(original['id'], {'request_id': 'operations-no-model', 'expected_attempt': cleaned['attempt_id'], 'external_processing': True, **ATTR})
    require(unavailable['state'] == 'unavailable', 'No-model rehearsal attempted assistance')
    feeds = ManagedFeed(store)
    feed = feeds.register({'name': 'Synthetic clinic weekly roster', 'source': SOURCE, 'scope': SCOPE,
                          'owner': 'Synthetic coordinator', 'inbox': str(inbox), 'start_date': '2026-11-02', **ATTR})
    contract = feeds.propose_contract(feed['id'], {'definition': {'recipe_revision_id': approved['id'], 'required_headers': HEADERS, 'row_change_fraction': .2}, **ATTR})
    contract = feeds.approve_contract(feed['id'], contract['id'], ATTR)
    feed = feeds.configure(feed['id'], {'expected_revision': feed['revision'], 'config': {'enabled': True, 'contract_id': contract['id']}, **ATTR})
    deliver(inbox, 'baseline', ROWS, '2026-11-02')
    baseline = feeds.run_once(feed['id'], '2026-11-03T10:00:00+00:00')
    approved_version = approve_version(feeds, baseline['version_id'])
    version_id = approved_version['id']; clinic = store.detail(approved_version['manifest']['receipt_id'])
    export_bytes = canonical(feeds.export(version_id)); (exports / 'approved.json').write_bytes(export_bytes)
    consumed = consume(export_bytes, version_id, expected_feed=feed['id'], expected_sha=sha(export_bytes))
    require(len(consumed['contacts']) == expected['approved_rows'], 'Approved contact count differs')
    for contact in consumed['contacts']:
        require(all(contact[key] == value for key, value in expected['contacts'][contact['location_id']].items()), 'Consumer lost a phone, extension or leading-zero ZIP')
    guard = root / 'consumer-must-not-open-storage'
    command = [sys.executable, '-m', 'provider_directory_truth_layer.cli', 'consume-approved', str(exports / 'approved.json'),
        '--expected-version', version_id, '--expected-feed', feed['id'], '--sha256', sha(export_bytes), '--report', str(exports / 'consumer.json')]
    completed = subprocess.run(command, capture_output=True, text=True, timeout=30,
        env={**os.environ, 'PDTL_ROOT': str(guard), 'PDTL_DB': str(guard / 'directory.sqlite3')})
    require(completed.returncode == 0 and not guard.exists(), 'Independent consumer failed or opened application storage')
    require(json.loads((exports / 'consumer.json').read_bytes()) == consumed, 'Independent consumer process changed the projection')
    saved_bundle = bundle(); saved_bytes = packed(saved_bundle).encode(); (inputs / 'directory.json').write_bytes(saved_bytes)
    saved = store.receive(saved_bytes, 'directory.json', source='synthetic-operations-saved-payer', profile='fhir-plannet-r4')
    coverage = saved['preview']['native']['coverage']
    require(coverage['assertion_count'] == expected['fhir_office_assertions'] and coverage['invalid_count'] > 0 and coverage['unsupported_count'] > 0 and coverage['unresolved_count'] > 0, 'Saved native diagnostic coverage was lost')
    saved = store.commit(saved['id'], {'expected_attempt': saved['attempt_id'], 'policy': 'reference_resources', 'request_id': 'operations-saved-accept', **ATTR})
    with controlled_source(saved_bundle) as (source, seen):
        clock=[datetime.now(timezone.utc)]
        acquisition = Acquisition(store, source=source, clock=lambda:clock[0])
        fetched = capture(acquisition, 'operations-complete', 1)
        require(fetched['state'] == 'complete' and fetched['checkpoint']['pages'] == 2, 'Controlled two-page capture failed')
        native = store.detail(fetched['receipt_id'])
        replay = parse_bundle((store.artifacts / native['artifact_sha']).read_bytes())
        require(replay['assertions'] == native['preview']['native']['assertions'], 'Saved/network parser paths disagree for identical assembled bytes')
        native = store.commit(native['id'], {'expected_attempt': native['attempt_id'], 'policy': 'reference_resources', 'request_id': 'operations-capture-accept', **ATTR})
        rate=capture(acquisition,'rate-limit',2)
        before=len(seen); acquisition.run_once(rate['id'])
        require(len(seen)==before,'Future retry fetched before its persisted due time')
        # Advance only the owned fixture clock, never sleep or bypass production cooldown.
        clock[0]=datetime.fromisoformat(rate['next_retry'])
        faults = [rate]
        faults.extend(capture(acquisition, name, count) for name, count in [('later-page', 3), ('unsafe-next', 4), ('malformed', 5)])
        require([run['state'] for run in faults] == ['retry_wait', 'failed', 'failed', 'failed'], 'Controlled source failures were mislabeled healthy')
        require(faults[1]['partial'] and all(run['receipt_id'] is None for run in faults), 'Incomplete acquisition published a receipt')
        http_paths = list(seen)
    require(canonical(feeds.export(version_id)) == export_bytes, 'Reference capture changed approved consumer bytes')
    comparison = ReconciliationStore(store)
    selected = [clinic, saved, native, workbook_receipt]
    run = comparison.create_run({'inputs': [{'receipt_id': row['id'], 'attempt_id': row['attempt_id']} for row in selected], **ATTR})
    review = IdentityReview(store); person = None; locations = {}
    for other in (saved, native):
        person = link(review, comparison, run['id'], clinic, other, 'clinician', 'Synthetic Clinician', person)
    for office in ('NORTH', 'SOUTH'):
        for other in (saved, native):
            locations[office] = link(review, comparison, run['id'], clinic, other, 'location', office, locations.get(office), office)
    ambiguous = next((candidate for candidate in comparison.candidates(run['id'], kind='location', limit=100)['items']
                  if any(candidate[side]['receipt_id'] == workbook_receipt['id']
                         and candidate[side]['comparison']['address']['line1'] == '10 example st' for side in ('left_record', 'right_record'))), None)
    require(ambiguous is not None, 'No duplicate-key source candidate was retained for unresolved review')
    context = review.inspect(run['id'], ambiguous['id'])
    review.decide({'run_id': run['id'], 'candidate_id': ambiguous['id'], 'decision': 'defer',
        'request_id': uuid.uuid4().hex, 'expected_snapshot': context['review_snapshot'],
        'expected_revisions': {ref: current['id'] if current else None for ref, current in context['current_links'].items()},
        'expected_decision': context['latest_decision']['id'] if context['latest_decision'] else None,
        'actor': ATTR['actor'], 'reason': 'Duplicate NORTH source keys remain quarantined; leave this ambiguous row candidate unresolved'})
    fields = FieldReconciliation(store)
    south_fields = fields.inspect(person, locations['SOUTH'])
    north = fields.inspect(person, locations['NORTH'])
    phone = next(field for field in north['fields'] if field['field'] == 'phone')
    option = next(option for option in phone['options'] if option['source'] == native['source'])
    fields.decide({'clinician_id': person, 'location_id': locations['NORTH'], 'field': 'phone', 'decision': 'select',
        'selected_ref': option['ref'], 'expected_snapshot': north['snapshot'], 'expected_decision': None,
        'request_id': 'operations-north-phone', **ATTR})
    require(fields.inspect(person, locations['SOUTH']) == south_fields, 'NORTH field review changed SOUTH')
    north = fields.inspect(person, locations['NORTH'])
    field_packet = fields.export(person, locations['NORTH'], north['snapshot'])
    selected_phone = next(field for field in field_packet['fields'] if field['field'] == 'phone')['preferred_value']
    require(selected_phone == {'number': expected['north_selected_phone'], 'extension': expected['north_selected_extension']}, 'NORTH field selection invented an extension or chose another phone')
    for receipt in (saved, native):
        locators = {context['row']['locator'] for context in field_packet['source_context'] if context['receipt']['id'] == receipt['id']}
        require(locators == set(expected['north_resource_locators']), 'Selected field context mixed NORTH/SOUTH native rows')
    origin_checks = verify_origins(store, field_packet, native['id'])
    field_bytes = field_workbook(field_packet)
    require(xlsx_payload(field_bytes) == field_packet, 'Field workbook lost payload fidelity')
    write_json(exports / 'north-fields.json', field_packet); (exports / 'north-fields.xlsx').write_bytes(field_bytes)
    cases = clinic['linked_cases']; north_case = next(case for case in cases if case['kind'] == 'correction' and case['location_id'].endswith(':NORTH'))
    south_case = next(case for case in cases if case['kind'] == 'correction' and case['location_id'].endswith(':SOUTH'))
    south_before = store.case(south_case['id'])
    later_rows = copy.deepcopy(ROWS[:1]); later_rows[0][7] = '6175550188'
    deliver(inbox, 'incomplete', later_rows, '2026-11-09')
    later = feeds.run_once(feed['id'], '2026-11-10T10:00:00+00:00'); held = feeds.version(later['version_id'])
    require(held['report']['comparison']['missing_from_this_delivery'] == expected['held_missing_keys'], 'Missing SOUTH coverage was not recorded')
    held_rejection = rejected(lambda: approve_version(feeds, held['id']), 'held dataset promotion')
    candidate_rejection = rejected(lambda: consume(canonical(held), held['id']), 'candidate consumption')
    require(feeds.current(feed['id'])['version_id'] == version_id and canonical(feeds.export(version_id)) == export_bytes, 'Held delivery replaced current or pinned consumer data')
    require(store.case(south_case['id']) == south_before, 'SOUTH omission changed its case')
    actions = [('assign', {'owner': 'Synthetic investigator', 'follow_up': '2026-11-16'}),
        ('outreach', {'contact_at': '2026-11-03T09:00:00-05:00', 'method': 'phone', 'outcome': 'no_answer'}),
        ('outreach', {'contact_at': '2026-11-03T10:00:00-05:00', 'method': 'phone', 'outcome': 'response_received',
                      'response_summary': 'Office reported its NORTH voice number', 'respondent_role': 'Office manager', 'reported_phone': '6175550199'}),
        ('triage', {}), ('approve', {'proposal': '6175550199'}), ('submit', {'submission_reference': 'SIMULATED operations ticket'}),
        ('verify', {'observed': '6175550100', 'verification_note': 'Synthetic downstream observation still shows the old number'})]
    case = store.case(north_case['id'])
    for action, values in actions:
        case = store.event(case['id'], {'action': action, 'expected_version': case['version'], **ATTR, **values})
    require(case['status'] == expected['north_work_status'] and store.case(south_case['id']) == south_before, 'Investigation or SOUTH state differs from authored expectations')
    work_packet = snapshot(store.path, case['id'])
    require(len(work_packet['investigations'][0]['outreach']) == expected['north_outreach_events'], 'Distinct contacts were lost')
    work_bytes = handoff_workbook(store.path, case['id'])
    decoded = list(work_payloads(work_bytes).values())
    require(work_packet['cases'][0] in decoded and work_packet['investigations'][0] in decoded, 'Investigation workbook lost selected case/contact payloads')
    require(all(item['normalized'].get('location_id') == 'NORTH' for item in work_packet['evidence']), 'Investigation export labels SOUTH as NORTH evidence')
    write_json(exports / 'north-investigation.json', work_packet); (exports / 'north-investigation.xlsx').write_bytes(work_bytes)
    require(feeds.run_once(feed['id'], '2026-11-10T10:00:00+00:00') == {'processed': None}, 'Repeat delivery created another job')
    reopened = IntakeStore.open_existing(store.path, store.root)
    require(canonical(ManagedFeed(reopened).export(version_id)) == export_bytes, 'Restart changed approved bytes')
    require(stable_work(snapshot(reopened.path, case['id'])) == stable_work(work_packet), 'Restart changed selected investigation evidence')
    backup_manifest = backup(store.root, root / 'backup')
    verify(root / 'backup'); restore(root / 'backup', root / 'restored')
    recovered = IntakeStore.open_existing(root / 'restored/directory.sqlite3', root / 'restored')
    recovered_export = canonical(ManagedFeed(recovered).export(version_id))
    require(recovered_export == export_bytes and consume(recovered_export, version_id) == consumed, 'Restore changed pinned contacts')
    require(stable_work(snapshot(recovered.path, case['id'])) == stable_work(work_packet), 'Restore changed selected work evidence')
    require(FieldReconciliation(recovered).export(person, locations['NORTH'], north['snapshot']) == field_packet, 'Restore changed field provenance')
    with recovered.db() as conn:
        require(conn.execute('PRAGMA integrity_check').fetchone()[0] == 'ok' and conn.execute('PRAGMA foreign_key_check').fetchone() is None, 'Recovered database integrity failed')
        networks = conn.execute('SELECT count(*) FROM network').fetchone()[0]
        require(networks == expected['automatic_local_networks'], 'Source-declared network became a local binding')
        for row in conn.execute('SELECT sha FROM artifact'):
            require(sha((recovered.artifacts / row['sha']).read_bytes()) == row['sha'], 'Recovered artifact digest differs')
    index = {'format_version': 1, 'designation': 'synthetic', 'clinician_id': person, 'reviewed_location_id': locations['NORTH'],
             'identity_review_run_id': run['id'], 'source_case_location_id': case['location_id'],
             'case_id': case['id'], 'approved_version_id': version_id,
             'notice': 'NORTH field evidence and investigation are separate reviewed scopes. Complete shared receipts/Bundles can contain SOUTH; their complete payloads do not label SOUTH as selected NORTH evidence.',
             'files': {path.name: sha(path.read_bytes()) for path in sorted(exports.iterdir())}}
    write_json(exports / 'north-dossier.json', index)
    result = {'format_version': 1, 'synthetic': True, 'approved_version_id': version_id, 'held_version_id': held['id'],
        'feed_id': feed['id'], 'workbook_receipt_id': original['id'], 'clinic_receipt_id': clinic['id'],
        'saved_receipt_id': saved['id'], 'acquired_receipt_id': native['id'],
        'consumer': consumed, 'workbook_counts': expected['workbook'], 'rejections': [invalid, held_rejection, candidate_rejection],
        'saved_native_coverage': coverage, 'acquired_native_coverage': native['preview']['native']['coverage'],
        'acquisitions': [{'id': run['id'], 'state': run['state'], 'partial': run['partial'], 'receipt_id': run['receipt_id']} for run in [fetched, *faults]],
        'controlled_http_requests': http_paths, 'assistance': {'state': unavailable['state'], 'mode': 'explicitly disabled for no-model rehearsal', 'provider_calls': 0},
        'deferred_location_candidate_id': ambiguous['id'], 'verified_original_page_references': origin_checks,
        'north_case_id': case['id'], 'north_status': case['status'], 'north_outreach_events': len(work_packet['investigations'][0]['outreach']),
        'south_unchanged': True, 'consumer_preserved_after_hold': True, 'restart_preserved': True, 'restore_preserved': True,
        'backed_up_registered_artifacts': backup_manifest['registered_artifacts'], 'dossier': index,
        'limits': 'Synthetic controlled-source/no-model engineering rehearsal; public interoperability, complete conformance and human usefulness are unverified.'}
    write_json(root / 'operations-rehearsal.json', result)
    return result
