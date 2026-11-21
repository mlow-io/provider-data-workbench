"""Qualify reviewed corrections at 100 and 1,000 synthetic rows.

Run from the repository root with PYTHONPATH=src and --root pointing to a new,
invocation-owned directory. Measurements are single service diagnostics with
fixture/identity setup excluded, not browser responsiveness or capacity tests.
"""
import argparse
import io
import json
from pathlib import Path
from time import perf_counter
from uuid import uuid4

from openpyxl import load_workbook

from serve import seed
from provider_directory_truth_layer.field_materialization import FieldMaterialization
from provider_directory_truth_layer.field_reconciliation import FieldReconciliation
from provider_directory_truth_layer.identity_review import IdentityReview
from provider_directory_truth_layer.intake_store import IntakeStore, packed
from provider_directory_truth_layer.managed_feed import ManagedFeed
from provider_directory_truth_layer.reconciliation_store import ReconciliationStore
from provider_directory_truth_layer.review_workbook import preview, snapshot, workbook

ATTR = {'actor': 'Synthetic qualification operator', 'reason': 'Review synthetic correction'}
NEW_PHONE = '6155559999'
EXTENSION = '0042'


def timed(function):
    start = perf_counter()
    result = function()
    return result, round((perf_counter() - start) * 1000, 2)


def require(condition, description):
    if not condition:
        raise AssertionError(description)


def approve_link(review, run_id, candidate, **target):
    view = review.inspect(run_id, candidate['id'])
    payload = {'run_id': run_id, 'candidate_id': candidate['id'], 'decision': 'approve',
               'request_id': uuid4().hex, 'expected_snapshot': view['review_snapshot'],
               'expected_revisions': {ref: link['id'] if link else None for ref, link in view['current_links'].items()},
               'expected_decision': view['latest_decision']['id'] if view['latest_decision'] else None,
               **ATTR, **target}
    return review.decide(payload)['decision']['target_id']


def review_first_office(store, fixture):
    feeds = ManagedFeed(store)
    base = feeds.version(fixture['version_id'], full=True)
    first, south = base['rows'][:2]
    original = first['normalized']
    reference = {key: original.get(key) for key in ('record_id', 'npi', 'provider_name', 'address', 'city', 'state', 'zip', 'location_id')}
    reference.update(phone=NEW_PHONE, phone_extension=EXTENSION, entity_type='clinician')
    receipt = store.receive(json.dumps([reference]).encode(), 'reference.json', source='synthetic-reference')
    comparison = ReconciliationStore(store)
    run = comparison.create_run({'inputs': [
        {'receipt_id': base['manifest']['receipt_id'], 'attempt_id': base['manifest']['attempt_id'], 'entity_kind': 'clinician'},
        {'receipt_id': receipt['id'], 'attempt_id': receipt['attempt_id'], 'entity_kind': 'clinician'}], **ATTR})
    review = IdentityReview(store)
    def first_match(kind):
        # The intended phone conflict makes the location pair ineligible for
        # automatic suggestions; explicit identity review can still link it.
        candidates = comparison.candidates(run['id'], kind=kind, limit=100)['items']
        return next(candidate for candidate in candidates if any(
            candidate[side + '_record']['receipt_id'] == base['manifest']['receipt_id']
            and candidate[side + '_record']['locator'] == first['locator'] for side in ('left', 'right')))
    clinician = approve_link(review, run['id'], first_match('clinician'), new_label='Synthetic clinician')
    location = approve_link(review, run['id'], first_match('location'), new_label='Synthetic first office')
    fields = FieldReconciliation(store)
    view = fields.inspect(clinician, location)
    phone = next(field for field in view['fields'] if field['field'] == 'phone')
    option = next(option for option in phone['options'] if option['source'] == 'synthetic-reference')
    decision = fields.decide({'clinician_id': clinician, 'location_id': location, 'field': 'phone',
        'decision': 'select', 'selected_ref': option['ref'], 'expected_snapshot': view['snapshot'],
        'expected_decision': None, 'request_id': uuid4().hex, **ATTR})
    view = fields.inspect(clinician, location)
    payload = {'clinician_id': clinician, 'location_id': location, 'snapshot': view['snapshot'],
               'decision_id': decision['id'], 'idempotency_key': uuid4().hex, **ATTR}
    return payload, first, south


def rows_from_sheet(sheet):
    iterator = sheet.iter_rows(values_only=True)
    columns = next(iterator)
    return [dict(zip(columns, row)) for row in iterator]


def qualify(store, fixture):
    count, feed_id, base_id = fixture['count'], fixture['feed_id'], fixture['version_id']
    feeds = ManagedFeed(store)
    payload, first, south = review_first_office(store, fixture)
    base_export = packed(feeds.export(base_id))
    before = snapshot(store.path, base_id)
    service = FieldMaterialization(store)
    choices, choices_ms = timed(lambda: service.choices(base_id))
    require(any(choice['decision_id'] == payload['decision_id'] for choice in choices['choices']), 'Reviewed selection missing from discovery')
    candidate, create_ms = timed(lambda: service.create(base_id, payload))
    require(feeds.current(feed_id)['version_id'] == base_id, 'Candidate unexpectedly changed the current pointer')
    version = feeds.version(candidate)
    approval = {'decision': 'approved', 'expected_report': version['report_hash'], 'expected_current': base_id,
                'idempotency_key': uuid4().hex, **ATTR}
    _, approve_ms = timed(lambda: feeds.decide(candidate, approval))
    require(feeds.current(feed_id)['version_id'] == candidate, 'Separate approval did not change the current pointer')
    sample, preview_ms = timed(lambda: preview(store.path, candidate, limit=5))
    def render():
        data = snapshot(store.path, candidate, expected_snapshot=sample['snapshot_id'])
        return data, workbook(data)
    (data, content), xlsx_ms = timed(render)
    require(data['counts']['directory'] == count and len(data['directory']) == count, 'Full JSON directory count differs')
    require(sample['counts'] == data['counts'] and len(sample['directory']) == min(5, count), 'Preview count or sample mismatch')
    require(data['counts']['corrections'] == 1, 'Expected one correction')
    by_office = {row['location_id']: row for row in data['directory']}
    north, south_row = by_office[first['normalized']['location_id']], by_office[south['normalized']['location_id']]
    require((north['phone'], north['phone_extension']) == (NEW_PHONE, EXTENSION), 'Corrected phone/extension mismatch')
    require((south_row['phone'], south_row['phone_extension']) == (south['normalized']['phone'], south['normalized'].get('phone_extension')), 'Other office changed')
    correction = data['corrections'][0]
    require(correction['decision_id'] == payload['decision_id'] and correction['base_version'] == base_id and correction['link_ids'], 'Decision/base/link lineage mismatch')
    source = next(row for row in data['sources'] if row['source_ref'] == correction['selected_source_ref'])
    require(source['source'] == 'synthetic-reference' and source['receipt_id'] != data['manifest']['receipt_id'], 'Selected source lineage mismatch')
    book = load_workbook(io.BytesIO(content), read_only=True, data_only=False)
    try:
        directory = rows_from_sheet(book['Directory'])
        ledger = rows_from_sheet(book['Reviewed corrections'])
        source_rows = rows_from_sheet(book['Sources and export details'])
        require(len(directory) == count and len(ledger) == 1, 'Full workbook population mismatch')
        actual = {row['location_id']: row for row in directory}
        require((actual[north['location_id']]['phone'], actual[north['location_id']]['phone_extension']) == (NEW_PHONE, EXTENSION), 'Workbook phone/extension mismatch')
        require((actual[south_row['location_id']]['phone'], actual[south_row['location_id']]['phone_extension']) ==
                (south_row['phone'], south_row['phone_extension']), 'Workbook other office changed')
        require(ledger[0]['decision_id'] == payload['decision_id'] and ledger[0]['selected_source_ref'] == source['source_ref'], 'Workbook correction lineage mismatch')
        require(any(row['source_ref'] == ledger[0]['selected_source_ref'] and row['source'] == 'synthetic-reference'
                    for row in source_rows), 'Workbook selected source missing')
    finally:
        book.close()
    reopened = IntakeStore(store.path, store.root)
    require(FieldMaterialization(reopened).create(base_id, payload) == candidate, 'Candidate retry after restart differs')
    require(ManagedFeed(reopened).decide(candidate, approval)['id'] == candidate, 'Approval retry after restart differs')
    require(packed(ManagedFeed(reopened).export(base_id)) == base_export, 'Prior approved export changed')
    require(snapshot(store.path, base_id)['snapshot_id'] == before['snapshot_id'], 'Prior review snapshot changed')
    return {'population': count, 'directory_rows': len(directory), 'corrections': len(ledger),
            'preview_returned': len(sample['directory']), 'workbook_bytes': len(content),
            'checks': {'separate_approval': True, 'other_office_unchanged': True, 'source_and_decision_lineage': True,
                       'leading_zero_extension': True, 'restart_retries': True, 'prior_export_stable': True},
            'service_wall_ms': {'choices': choices_ms, 'create': create_ms, 'approve': approve_ms,
                                'preview': preview_ms, 'full_snapshot_and_xlsx': xlsx_ms}}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, required=True, help='New invocation-owned directory')
    args = parser.parse_args()
    store, fixtures = seed(args.root)
    results = {'method': 'One synthetic service operation per population; setup excluded. Not browser responsiveness or capacity.',
               'results': []}
    for fixture in fixtures:
        results['results'].append(qualify(store, fixture))
        (args.root / 'correction-results.json').write_text(json.dumps(results, indent=2) + '\n')
        print(json.dumps(results['results'][-1]), flush=True)


if __name__ == '__main__':
    main()
