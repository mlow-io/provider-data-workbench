"""Independent producer/consumer contracts and immutable input handling."""
import copy
import hashlib
import json
import os
import subprocess
import sys

import pytest

from provider_directory_truth_layer.approved_consumer import MAX_BYTES, consume
from provider_directory_truth_layer.intake_store import digest, packed
from test_managed_feed import setup_feed, deliver, approve


@pytest.fixture
def exported(tmp_path):
    store, feeds, feed, inbox = setup_feed(tmp_path)
    deliver(inbox)
    version = feeds.run_once(feed['id'], '2026-10-06T10:00:00+00:00')['version_id']
    approve(feeds, version)
    return store, feeds, feed, feeds.export(version)


def check(packet, **pins):
    return consume(packed(packet).encode(), packet['version_id'], **pins)


def rehash(packet):
    packet['manifest']['records_sha256'] = digest(packet['records'])
    packet['report_hash'] = digest(packet['report'])


def test_real_approved_export_reads_three_native_keys_and_pinned_bytes_remain_stable(exported):
    store, feeds, feed, packet = exported
    raw = packed(packet).encode()
    before = hashlib.sha256(store.path.read_bytes()).hexdigest()
    result = consume(raw, packet['version_id'], expected_feed=feed['id'], expected_sha=hashlib.sha256(raw).hexdigest())
    assert len(result['contacts']) == 3
    assert {contact['zip'] for contact in result['contacts']} == {'02108', '02109', '02110'}
    assert len({(c['record_id'], c['location_id']) for c in result['contacts']}) == 3
    assert result['records_sha256'] == packet['manifest']['records_sha256']
    assert result['version_id'] == feeds.current(feed['id'])['version_id']
    assert hashlib.sha256(store.path.read_bytes()).hexdigest() == before
    assert packed(feeds.export(packet['version_id'])).encode() == raw


@pytest.mark.parametrize('kind', ['version', 'feed', 'file_digest', 'record_digest', 'report_digest', 'schema', 'boolean_schema', 'candidate', 'approval_version', 'counts', 'hard', 'hold', 'duplicate_key', 'numeric_zip', 'formatted_phone', 'extension'])
def test_unsuitable_or_inconsistent_handoffs_fail_without_repair(exported, kind):
    _, _, _, original = exported
    packet = copy.deepcopy(original)
    if kind == 'version':
        with pytest.raises(ValueError, match='version'): consume(packed(packet).encode(), 'different-version')
        return
    if kind == 'feed':
        with pytest.raises(ValueError, match='feed'): check(packet, expected_feed='different-feed')
        return
    if kind == 'file_digest':
        with pytest.raises(ValueError, match='digest'): check(packet, expected_sha='0' * 64)
        return
    if kind == 'record_digest': packet['records'][0]['normalized']['phone'] = '6175550199'
    elif kind == 'report_digest': packet['report']['counts']['valid'] = 999
    elif kind == 'schema': packet['manifest']['output_schema_version'] = 2
    elif kind == 'boolean_schema': packet['manifest']['output_schema_version'] = True
    elif kind == 'candidate': packet['approval']['decision'] = 'candidate'
    elif kind == 'approval_version': packet['approval']['version_id'] = 'another-version'
    elif kind == 'counts': packet['report']['counts']['raw'] += 1; rehash(packet)
    elif kind == 'hard': packet['report']['findings'].append({'code':'hard-test','severity':'hard'}); rehash(packet)
    elif kind == 'hold': packet['report']['findings'].append({'code':'hold-test','severity':'hold'}); rehash(packet)
    elif kind == 'duplicate_key': packet['records'][1]['normalized'] = copy.deepcopy(packet['records'][0]['normalized']); rehash(packet)
    elif kind == 'numeric_zip': packet['records'][0]['normalized']['zip'] = 2108; rehash(packet)
    elif kind == 'formatted_phone': packet['records'][0]['normalized']['phone'] = '(617) 555-0100'; rehash(packet)
    elif kind == 'extension': packet['records'][0]['normalized']['phone_extension'] = 'x007'; rehash(packet)
    before = copy.deepcopy(packet)
    with pytest.raises(ValueError): check(packet)
    assert packet == before


def test_acknowledged_hold_and_extension_absent_null_blank_value_are_preserved(exported):
    _, _, _, packet = exported
    packet['report']['findings'].append({'code':'bounded-review','severity':'hold'})
    packet['exception_review'] = [{'version_id':packet['version_id'],'code':'bounded-review','disposition':'acknowledged'}]
    rehash(packet)
    first = packet['records'][0]['normalized']
    first.pop('phone_extension', None)
    rehash(packet)
    key = first['record_id'], first['location_id']
    contact = lambda result: next(c for c in result['contacts'] if (c['record_id'], c['location_id']) == key)
    assert 'phone_extension' not in contact(check(packet))
    for extension in (None, '', ' ', '007'):
        first['phone_extension'] = extension; rehash(packet)
        assert contact(check(packet))['phone_extension'] == extension
    packet['exception_review'].append({'version_id':packet['version_id'],'code':'bounded-review','disposition':'deferred'})
    with pytest.raises(ValueError, match='hold'): check(packet)


def test_candidate_version_and_later_held_delivery_do_not_replace_prior_consumer(exported):
    _, feeds, feed, packet = exported
    original = check(packet)
    inbox = feeds.detail(feed['id'])['config']['inbox']
    from pathlib import Path
    deliver(Path(inbox), 'row_drop.csv', 'later-held', '2026-10-12')
    candidate = feeds.run_once(feed['id'], '2026-10-13T10:00:00+00:00')['version_id']
    with pytest.raises(ValueError): consume(packed(feeds.version(candidate)).encode(), candidate)
    with pytest.raises(ValueError, match='hold'): approve(feeds, candidate)
    assert check(feeds.export(feeds.current(feed['id'])['version_id'])) == original


@pytest.mark.parametrize('raw', [b'{"x":1,"x":2}', b'{"x":NaN}', b'[', b'x'*(MAX_BYTES+1), b'['*66+b'0'+b']'*66])
def test_bounded_strict_json(raw):
    with pytest.raises(ValueError): consume(raw, 'expected-version')


def test_cli_is_read_only_and_refuses_report_overwrite(exported, tmp_path):
    store, _, feed, packet = exported
    source = tmp_path / 'approved.json'; source.write_text(packed(packet))
    before = source.read_bytes()
    untouched = tmp_path / 'must-not-open-storage'
    env = {**os.environ, 'PDTL_ROOT': str(untouched), 'PDTL_DB': str(untouched / 'directory.sqlite3')}
    command = [sys.executable, '-m', 'provider_directory_truth_layer.cli', 'consume-approved', str(source), '--expected-version', packet['version_id'], '--expected-feed', feed['id']]
    result = subprocess.run(command, capture_output=True, text=True, env=env, timeout=15)
    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout)['version_id'] == packet['version_id']
    assert not untouched.exists()
    refused = subprocess.run([*command, '--report', str(source)], capture_output=True, text=True, env=env, timeout=15)
    assert refused.returncode == 2 and source.read_bytes() == before and not untouched.exists()
