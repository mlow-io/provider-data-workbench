"""Retain strict-reference failure beside a real synthetic approved consumer.

Run with a new absolute root; existing data is refused. Uses owned loopback HTTP.
"""
from datetime import datetime, timezone
import hashlib
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
import sys
import threading

from provider_directory_truth_layer.fhir_acquisition import Acquisition, Source
from provider_directory_truth_layer.intake_store import IntakeStore
from provider_directory_truth_layer.managed_feed import ManagedFeed
from provider_directory_truth_layer.operations_rehearsal import rehearse


def run(root):
    journey = rehearse(root)
    store = IntakeStore.open_existing(root/'storage/directory.sqlite3', root/'storage')
    feeds = ManagedFeed(store)
    approved = root/'exports/approved.json'
    original = approved.read_bytes()
    before = feeds.export(journey['approved_version_id'])
    tables = ('receipt','observation','feed_version','feed_decision','work_case','recipe_revision')
    with store.db() as conn:
        counts = {name: conn.execute('SELECT count(*) FROM '+name).fetchone()[0] for name in tables}
    raw = b'{"resourceType":"Organization","id":"wrong","id":"clinic","name":"Synthetic clinic"}'
    page = json.dumps({'resourceType':'Bundle','type':'searchset','entry':[{'resource':{
        'resourceType':'Location','id':'north','managingOrganization':{'reference':'Organization/clinic'}}}]}).encode()
    requests = []
    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            requests.append(self.path)
            body = page if self.path=='/Location/?_count=1' else raw
            self.send_response(200); self.send_header('Content-Type','application/fhir+json'); self.end_headers()
            self.wfile.write(body)
        def log_message(self,*args): pass
    server = ThreadingHTTPServer(('127.0.0.1',0),Handler)
    thread = threading.Thread(target=server.serve_forever,daemon=True); thread.start()
    source = Source(key='synthetic-strict-json',base=f'http://127.0.0.1:{server.server_port}/',
                    interval_seconds=0,test_http=True)
    try:
        service = Acquisition(store,source=source,clock=lambda:datetime(2026,11,15,tzinfo=timezone.utc))
        created = service.create({'request_id':'strict-json-reference','resource_type':'Location','count':1,
                                 'actor':'Synthetic reviewer','reason':'Inspect ambiguous original JSON'})
        for _ in range(4):
            result = service.run_once(created['id'])
            if result['state'] in {'complete','failed'}: break
        assert result['state']=='failed' and result['receipt_id'] is None
        assert 'Duplicate JSON property' in result['checkpoint']['error']
        body_sha = hashlib.sha256(raw).hexdigest()
        assert (store.artifacts/body_sha).read_bytes()==raw
        event = next(item for item in result['events'] if item['artifact_sha']==body_sha)
        assert event['payload']['status']==200
    finally:
        server.shutdown(); server.server_close(); thread.join()
    reopened = IntakeStore.open_existing(store.path,store.root)
    replay = Acquisition(reopened,source=source).run_once(created['id'])
    assert replay['state']=='failed' and len(requests)==2
    assert feeds.current(journey['feed_id'])['version_id']==journey['approved_version_id']
    assert ManagedFeed(reopened).export(journey['approved_version_id'])==before==json.loads(original)
    assert approved.read_bytes()==original
    with reopened.db() as conn:
        assert counts=={name:conn.execute('SELECT count(*) FROM '+name).fetchone()[0] for name in tables}
        assert conn.execute('PRAGMA integrity_check').fetchone()[0]=='ok'
        assert conn.execute('PRAGMA foreign_key_check').fetchone() is None
    result = {'designation':'synthetic','requests':len(requests),'failed_status':'failed','http_status':200,
              'raw_sha256':body_sha,'raw_verified':True,'no_receipt':True,'restart_preserved':True,
              'approved_sha256':hashlib.sha256(original).hexdigest(),'approved_bytes_preserved':True,
              'approved_version_preserved':True,'operational_table_counts_preserved':counts,
              'south_preserved_by_operations_rehearsal':journey['south_unchanged']}
    (root/'strict-json-qualification.json').write_text(json.dumps(result,indent=2)+'\n')
    return result


if __name__=='__main__':
    print(json.dumps(run(Path(sys.argv[1]).resolve()),indent=2))
