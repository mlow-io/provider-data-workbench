"""Invocation-owned HTTP fixture for the headless browser launcher only."""
import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from provider_directory_truth_layer.fhir_acquisition import Source


def start():
    fixture = json.loads((Path(__file__).resolve().parents[1] / 'tests/fixtures/intake/fhir-plannet/north-south.json').read_bytes())
    fixture['entry'] = [entry for entry in fixture['entry'] if entry['resource']['id'] != 'unresolved-role']

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            if self.path.startswith('/PractitionerRole/'):
                self.send_response(429)
                self.send_header('Retry-After', '3')
                self.end_headers()
                self.wfile.write(b'Synthetic source throttle; no public request was made')
                return
            if self.path == '/Location/?_count=1':
                body = {**fixture, 'entry': fixture['entry'][:3], 'link': [{'relation': 'next', 'url': '/?_getpages=browser'}]}
            elif self.path in {'/Location/?_count=1&_id=north', '/Location/?_count=1&_id=ignored-filter'}:
                entry = json.loads(json.dumps(next(e for e in fixture['entry'] if e['resource']['resourceType']=='Location' and e['resource']['id']=='north')))
                entry['resource'].pop('managingOrganization',None)
                entry['resource'].pop('partOf',None)
                body = {'resourceType':'Bundle','type':'searchset','total':1,'entry':[entry]}
            elif self.path == '/?_getpages=browser':
                body = {**fixture, 'entry': fixture['entry'][3:]}
            else:
                self.send_error(404)
                return
            self.send_response(200)
            self.send_header('Content-Type', 'application/fhir+json')
            self.end_headers()
            self.wfile.write(json.dumps(body).encode())

        def log_message(self, *args):
            pass

    server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
    base = f'http://127.0.0.1:{server.server_port}/'
    for entry in fixture['entry']:
        resource = entry['resource']
        entry['fullUrl'] = base + resource['resourceType'] + '/' + resource['id']
    threading.Thread(target=server.serve_forever, daemon=True).start()
    return Source(key='synthetic-browser', base=base, plan_net_version='Synthetic browser fixture', interval_seconds=0, test_http=True)
