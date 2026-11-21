import hashlib,json,sys,threading
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
from pathlib import Path
from provider_directory_truth_layer.fhir_acquisition import Acquisition,Source
from provider_directory_truth_layer.intake_store import IntakeStore,packed
from test_managed_feed import setup_feed,deliver,approve
root=Path(sys.argv[1]).resolve();root.mkdir()
store,feeds,feed,inbox=setup_feed(root)
deliver(inbox);version=feeds.run_once(feed['id'],'2026-10-06T10:00:00+00:00')['version_id'];approve(feeds,version)
initial=packed(feeds.export(version)).encode();(root/'approved-before.json').write_bytes(initial)
with store.db() as conn:case_count=conn.execute('SELECT count(*) FROM work_case').fetchone()[0]
entries=[{'search':{'mode':'match'},'resource':{'resourceType':'Location','id':'north','status':'active','name':'Synthetic NORTH'}},
 {'search':{'mode':'include'},'resource':{'resourceType':'Location','id':'south','status':'active','name':'Synthetic SOUTH'}},
 {'search':{'mode':'include'},'resource':{'resourceType':'Organization','id':'clinic','name':'Synthetic clinic'}},
 {'search':{'mode':'outcome'},'resource':{'resourceType':'OperationOutcome','issue':[{'severity':'warning','code':'processing','diagnostics':'Synthetic retained warning'}]}}]
good={'resourceType':'Bundle','type':'searchset','entry':entries};bad={'resourceType':'Bundle','type':'searchset','entry':[entries[0]]}
seen=[]
class Handler(BaseHTTPRequestHandler):
 def do_GET(self):
  seen.append(self.path);body=good if self.path.endswith('_id=north') else bad
  self.send_response(200);self.send_header('Content-Type','application/fhir+json');self.end_headers();self.wfile.write(json.dumps(body).encode())
 def log_message(self,*args):pass
server=ThreadingHTTPServer(('127.0.0.1',0),Handler);thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
source=Source(key='synthetic-r1',base=f'http://127.0.0.1:{server.server_port}/',test_http=True,interval_seconds=0)
service=Acquisition(store,source=source)
attr={'actor':'Synthetic analyst','reason':'Retain exact source-query scope for R1 qualification','resource_type':'Location','count':1}
try:
 first=service.create({**attr,'request_id':'correct-filter','resource_id':'north'});service.run_once(first['id']);completed=service.run_once(first['id'])
 assert completed['state']=='complete'
 receipt=store.detail(completed['receipt_id']);assert receipt['observations']==[]
 expected={'version':1,'resource_type':'Location','resource_id':'north','matched_entries':1,'implicit_match_entries':0,'included_entries':2,'outcome_entries':1,'scope':'captured_search_pages'}
 assert receipt['metadata']['query_validation']==expected
 accepted=store.commit(receipt['id'],{'expected_attempt':receipt['attempt_id'],'policy':'reference_resources','request_id':'reference-review','actor':'Synthetic reviewer','reason':'Separate reference acceptance after inspecting source-query checks'})
 assert len(accepted['observations'])==3 and accepted['linked_cases']==[]
 (root/'reference-packet.json').write_text(json.dumps(accepted,indent=2)+'\n')
 wrong=service.run_once(service.create({**attr,'request_id':'ignored-filter','resource_id':'ignored-filter'})['id'])
 assert wrong['state']=='failed' and wrong['receipt_id'] is None
 response=next(e for e in wrong['events'] if e['kind']=='response');raw=(store.artifacts/response['artifact_sha']).read_bytes()
 assert response['payload']['status']==200 and hashlib.sha256(raw).hexdigest()==response['artifact_sha']
 (root/'failed-response.json').write_bytes(raw)
 reopened=IntakeStore.open_existing(store.path,store.root)
 assert reopened.detail(receipt['id'])['metadata']['query_validation']==expected
 with reopened.db() as conn:
  assert conn.execute('SELECT count(*) FROM work_case').fetchone()[0]==case_count
  assert conn.execute('PRAGMA integrity_check').fetchone()[0]=='ok' and not conn.execute('PRAGMA foreign_key_check').fetchall()
 after=packed(feeds.export(version)).encode();assert after==initial and feeds.current(feed['id'])['version_id']==version
 (root/'approved-after.json').write_bytes(after)
 report={'designation':'synthetic','transport':'owned real loopback HTTP','http_requests':seen,'query_validation':expected,'separate_reference_observations':3,'failed_http_status':response['payload']['status'],'failed_capture_state':wrong['state'],'failed_capture_receipt':wrong['receipt_id'],'failed_body_sha256':response['artifact_sha'],'approved_version_preserved':version,'approved_bytes_sha256':hashlib.sha256(initial).hexdigest(),'restart_query_report_preserved':True,'work_cases_unchanged':True,'integrity':'ok','foreign_key_errors':0}
 (root/'qualification.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report,indent=2))
finally:server.shutdown();server.server_close();thread.join()
