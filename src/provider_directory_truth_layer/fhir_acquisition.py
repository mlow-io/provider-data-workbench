"""Durable bounded provider-directory acquisition; one HTTP response per pass."""
from __future__ import annotations

import copy
import hashlib
from http.client import IncompleteRead
import json
import re
import ssl
import time
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from urllib.error import HTTPError, URLError
from urllib.parse import parse_qsl, urlencode, urljoin, urlsplit, urlunsplit
from urllib.request import HTTPRedirectHandler, HTTPSHandler, Request, build_opener

import certifi

from .fhir_intake import PROFILE, VERSION, SUPPORTED, parse_bundle
from .fhir_json import load_fhir_json
from .fhir_search import COUNT_FIELDS, search_entry_mode, search_page_counts
from .intake_store import Conflict, digest, now, packed, uid
from .managed_feed import ManagedFeed

MIGRATION_12 = '''
CREATE TABLE fhir_acquisition (
 id TEXT PRIMARY KEY, request_id TEXT NOT NULL UNIQUE, intent_hash TEXT NOT NULL,
 config TEXT NOT NULL, revision INTEGER NOT NULL, state TEXT NOT NULL,
 checkpoint TEXT NOT NULL, next_retry TEXT, receipt_id TEXT REFERENCES receipt(id), created_at TEXT NOT NULL);
CREATE TABLE fhir_acquisition_event (
 seq INTEGER PRIMARY KEY, acquisition_id TEXT NOT NULL REFERENCES fhir_acquisition(id),
 kind TEXT NOT NULL, payload TEXT NOT NULL, artifact_sha TEXT REFERENCES artifact(sha), created_at TEXT NOT NULL);
CREATE INDEX fhir_acquisition_event_owner ON fhir_acquisition_event(acquisition_id,seq);
CREATE TRIGGER fhir_acquisition_event_no_update BEFORE UPDATE ON fhir_acquisition_event BEGIN SELECT RAISE(ABORT,'Immutable acquisition events'); END;
CREATE TRIGGER fhir_acquisition_event_no_delete BEFORE DELETE ON fhir_acquisition_event BEGIN SELECT RAISE(ABORT,'Immutable acquisition events'); END;
'''
LIMITS = dict(pages=3, references=12, requests=24, entries=200, response_bytes=2*1024*1024,
              total_bytes=10*1024*1024, socket_seconds=10, active_seconds=90, attempts=3)
HAP_ROUTED_AUTHORITIES = {'fhir-prov-dir-r4.api.hap.org', 'fhir-prov-dir-r4.api.hap.org:443',
                          'provider-directory-r4.api.hap.org:443'}


@dataclass(frozen=True)
class Source:
    key: str = 'hap'
    base: str = 'https://provider-directory-r4.api.hap.org/'
    plan_net_version: str = '1.0.0 (source documentation; not verified conformance)'
    interval_seconds: int = 30
    test_http: bool = False


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def fetch_response(url, limit, timeout):
    """Retain a capped body even for HTTP errors; never follow a redirect."""
    opener = build_opener(NoRedirect(), HTTPSHandler(context=ssl.create_default_context(cafile=certifi.where())))
    try:
        response = opener.open(Request(url, headers={'Accept':'application/fhir+json', 'User-Agent':'ProviderDirectoryWorkbench/2'}), timeout=timeout)
    except HTTPError as error:
        response = error
    except (URLError, OSError) as error:
        return {'status':None, 'headers':{}, 'body':b'', 'error':str(error), 'truncated':False}
    body = bytearray()
    started = time.monotonic()
    error = None
    with response:
        headers = {key.lower():value for key,value in response.headers.items()
                   if key.lower() in {'content-type','location','retry-after','etag','last-modified'}}
        try:
            while len(body) <= limit:
                if time.monotonic() - started > timeout:
                    raise TimeoutError('Response active-read deadline exceeded')
                chunk = response.read(min(65536, limit+1-len(body)))
                if not chunk:
                    break
                body.extend(chunk)
        except IncompleteRead as exc:
            body.extend(exc.partial[:max(0,limit+1-len(body))])
            error = 'Incomplete HTTP response body'
        except (OSError, TimeoutError) as exc:
            error = str(exc)
        return {'status':response.code, 'headers':headers, 'body':bytes(body[:limit]),
                'error':error, 'truncated':len(body)>limit}


class Acquisition:
    def __init__(self, store, *, source=Source(), clock=None, fetcher=fetch_response):
        self.store, self.source, self.fetcher = store, source, fetcher
        self.clock = clock or (lambda:datetime.now(timezone.utc))
        base = urlsplit(source.base)
        if source.test_http:
            if base.scheme != 'http' or base.hostname not in {'127.0.0.1','localhost','::1'}:
                raise ValueError('Test HTTP configuration requires loopback')
        elif base.scheme != 'https' or source.base != Source().base or source.key != 'hap':
            raise ValueError('Only the configured public HAP source is supported')

    def validate_url(self, value):
        if not isinstance(value,str) or len(value)>4096 or any(ord(c)<32 for c in value):
            raise ValueError('Invalid acquisition URL')
        url = urlsplit(value)
        base = urlsplit(self.source.base)
        if url.username or url.password or '#' in value or '%' in url.path or '\\' in value:
            raise ValueError('Acquisition destination is outside the configured source')
        if not self.source.test_http and url.scheme == 'https' and url.netloc in HAP_ROUTED_AUTHORITIES:
            # Route a declared source alias through the published gateway. Never
            # fetch the advertised alternate host or rewrite source resources.
            value = urlunsplit(('https', base.netloc, url.path or '/', url.query, ''))
            url = urlsplit(value)
        if url.scheme != base.scheme or url.netloc != base.netloc:
            raise ValueError('Acquisition destination is outside the configured source')
        relative = url.path.removeprefix(base.path).strip('/') if url.path.startswith(base.path) else ''
        parts = relative.split('/')
        resource = len(parts) in {1,2} and parts[0] in SUPPORTED and (len(parts)==1 or re.fullmatch(r'[A-Za-z0-9.\-]{1,64}',parts[1]))
        pairs = parse_qsl(url.query, keep_blank_values=True, max_num_fields=20)
        paging = relative == '' and any(key=='_getpages' for key,_ in pairs)
        if not resource and not paging:
            raise ValueError('Only provider resource or bounded paging paths are allowed')
        if any(k not in {'_count','_include','_getpages','_getpagesoffset','_bundletype','_pretty','_id'} or len(v)>2048 for k,v in pairs):
            raise ValueError('Unsupported acquisition query')
        for key, content in pairs:
            if key == '_include' and content not in {'PractitionerRole:'+name for name in ('practitioner','location','organization','network')}:
                raise ValueError('Unsupported include resource')
            if key == '_count' and (not content.isdecimal() or not 1 <= int(content) <= 20):
                raise ValueError('Paging count exceeds query budget')
            if key == '_getpagesoffset' and (not content.isdecimal() or int(content)>10000):
                raise ValueError('Paging offset exceeds query budget')
            if key == '_bundletype' and content != 'searchset':
                raise ValueError('Unsupported Bundle type')
            if key == '_pretty' and content not in {'true','false'}:
                raise ValueError('Unsupported formatting flag')
            if key == '_id' and not re.fullmatch(r'[A-Za-z0-9.\-]{1,64}',content):
                raise ValueError('Invalid source resource ID')
        if any(sum(key == candidate for candidate,_ in pairs)>1 for key,_ in pairs if key!='_include'):
            raise ValueError('Ambiguous repeated query parameter')
        return value

    def _node(self, value, kind):
        destination = self.validate_url(value)
        node = {'url': destination, 'kind': kind}
        if destination != value:
            node['source_url'] = value
        return node

    @staticmethod
    def _event(conn, acquisition_id, kind, payload, sha=None):
        conn.execute('INSERT INTO fhir_acquisition_event(acquisition_id,kind,payload,artifact_sha,created_at) VALUES (?,?,?,?,?)',
                     (acquisition_id,kind,packed(payload),sha,now()))

    def detail(self, acquisition_id):
        with self.store.db() as conn:
            conn.execute('BEGIN')
            row=conn.execute('SELECT * FROM fhir_acquisition WHERE id=?',(acquisition_id,)).fetchone()
            if row is None: raise KeyError('Acquisition not found')
            result=dict(row)
            result['config']=json.loads(result['config']); result['checkpoint']=json.loads(result['checkpoint'])
            result['events']=[{**dict(e),'payload':json.loads(e['payload'])} for e in conn.execute('SELECT * FROM fhir_acquisition_event WHERE acquisition_id=? ORDER BY seq',(acquisition_id,))]
        result['partial']=bool(result['checkpoint']['bodies']) and result['state']!='complete'
        return result

    def list(self):
        with self.store.db() as conn:
            conn.execute('BEGIN')
            due=self._source_due(conn)
            return {'source':{'key':self.source.key,'base':self.source.base,
                              'plan_net_version':self.source.plan_net_version,
                              'parser_target':'Plan-Net 1.2.0 subset', 'limits':LIMITS,
                              'interval_seconds':self.source.interval_seconds,
                              'next_request_at':due.isoformat() if due and due>self.clock() else None},
                    'items':[dict(r) for r in conn.execute('SELECT id,revision,state,next_retry,receipt_id,created_at FROM fhir_acquisition ORDER BY created_at DESC LIMIT 100')]}

    def _source_due(self,conn):
        row=conn.execute('''SELECT max(due) FROM (
            SELECT json_extract(e.payload,'$.source_wait_until') due
            FROM fhir_acquisition_event e JOIN fhir_acquisition a ON a.id=e.acquisition_id
            WHERE json_extract(a.config,'$.source_base')=?
            UNION ALL SELECT next_retry due FROM fhir_acquisition
            WHERE json_extract(config,'$.source_base')=?)''',(self.source.base,self.source.base)).fetchone()
        return datetime.fromisoformat(row[0]) if row[0] else None

    def create(self, payload):
        if set(payload)-{'request_id','actor','reason','resource_type','resource_id','count','source'}:
            raise ValueError('Unknown acquisition input fields')
        for key in ('request_id','actor','reason'):
            if not isinstance(payload.get(key),str) or not payload[key].strip() or len(payload[key])>2000:
                raise ValueError(key+' requires nonblank text')
        kind=payload.get('resource_type','PractitionerRole'); count=payload.get('count',10)
        if not isinstance(kind,str) or kind not in {'PractitionerRole','Location'} or type(count) is not int or not 1<=count<=20 or payload.get('source',self.source.key)!=self.source.key:
            raise ValueError('Select configured source, Location/PractitionerRole and count 1–20')
        if 'resource_id' in payload and (not isinstance(payload['resource_id'],str) or not re.fullmatch(r'[A-Za-z0-9.\-]{1,64}',payload['resource_id'])):
            raise ValueError('Source resource ID requires 1–64 letters, digits, hyphens or periods')
        config={**payload,'source':self.source.key,'resource_type':kind,'count':count,'source_base':self.source.base,
                'source_plan_net_version':self.source.plan_net_version,'parser_target':'Plan-Net 1.2.0 subset','limits':LIMITS}
        intent=digest(config)
        query=[('_count',str(count))]
        if 'resource_id' in payload: query.append(('_id',payload['resource_id']))
        if kind=='PractitionerRole': query.extend(('_include','PractitionerRole:'+t) for t in ('practitioner','location','organization','network'))
        start=self.validate_url(self.source.base+kind+'/?'+urlencode(query))
        checkpoint={'pending':[{'url':start,'kind':'page'}],'completed_urls':[],'bodies':[],'attempts':{},'requests':0,'pages':0,'references':0,'bytes':0,'active_seconds':0,'error':None}
        with self.store.db() as conn:
            conn.execute('BEGIN IMMEDIATE')
            prior=conn.execute('SELECT id,intent_hash FROM fhir_acquisition WHERE request_id=?',(payload['request_id'],)).fetchone()
            if prior:
                if prior['intent_hash']!=intent: raise Conflict('Acquisition request ID has different content')
                acquisition_id=prior['id']
            else:
                acquisition_id=uid()
                conn.execute('INSERT INTO fhir_acquisition VALUES (?,?,?,?,?,?,?,?,?,?)',
                             (acquisition_id,payload['request_id'],intent,packed(config),0,'queued',packed(checkpoint),None,None,now()))
                self._event(conn,acquisition_id,'created',config)
        return self.detail(acquisition_id)

    def cancel(self, acquisition_id, payload):
        if type(payload.get('expected_revision')) is not int or set(payload)-{'expected_revision','actor','reason'} or any(not isinstance(payload.get(k),str) or not payload[k].strip() for k in ('actor','reason')):
            raise ValueError('Cancellation requires expected revision, actor and reason')
        with self.store.db() as conn:
            conn.execute('BEGIN IMMEDIATE')
            row=conn.execute('SELECT * FROM fhir_acquisition WHERE id=?',(acquisition_id,)).fetchone()
            if row is None: raise KeyError('Acquisition not found')
            if row['revision']!=payload.get('expected_revision') or row['state'] in {'complete','cancelled','failed'}:
                raise Conflict('Acquisition changed or is terminal')
            conn.execute("UPDATE fhir_acquisition SET state='cancelled',revision=revision+1,next_retry=NULL WHERE id=?",(acquisition_id,))
            self._event(conn,acquisition_id,'cancelled',payload)
        return self.detail(acquisition_id)

    def _retained_response(self, body):
        raw=(self.store.artifacts/body['sha']).read_bytes()
        if hashlib.sha256(raw).hexdigest()!=body['sha']: raise ValueError('Retained response artifact digest mismatch')
        return load_fhir_json(raw)

    def _query_validation(self, config, checkpoint):
        if 'resource_id' not in config: return None
        counts=dict.fromkeys(COUNT_FIELDS,0); pages=0
        for body in checkpoint['bodies']:
            if body['kind']!='page': continue
            page=self._retained_response(body); pages+=1
            current=search_page_counts(page,config['resource_type'],config['resource_id'])
            for field in COUNT_FIELDS: counts[field]+=current[field]
        if not pages: raise ValueError('Filtered query has no retained search pages')
        if counts['included_entries'] and not counts['matched_entries']:
            raise ValueError('Filtered query has includes without a matching resource')
        return {'version':1,'resource_type':config['resource_type'],'resource_id':config['resource_id'],
                **counts,'scope':'captured_search_pages'}

    def _assemble(self, checkpoint, config=None):
        entries=[]; origins={}; identical={}
        for body in checkpoint['bodies']:
            data=self._retained_response(body)
            source_entries=data.get('entry',[]) if body['kind']=='page' else [{'fullUrl':body.get('source_url',body['url']),'resource':data}]
            for index,entry in enumerate(source_entries):
                key=digest([entry.get('fullUrl'),entry.get('resource')]) if isinstance(entry,dict) else digest(entry)
                if key not in identical:
                    identical[key]=len(entries); entries.append(entry)
                elif config and 'resource_id' in config and body['kind']=='page':
                    existing=entries[identical[key]]
                    if (search_entry_mode(existing,'assembled entry')[0]=='include'
                            and search_entry_mode(entry,'source entry')[0]=='match'):
                        entries[identical[key]]=entry
                locator=f"$.entry[{identical[key]}].resource"
                origin={'artifact_sha':body['sha'],'request_url':body['url'],
                        'locator':f'$.entry[{index}].resource' if body['kind']=='page' else '$',
                        'retrieved_at':body['retrieved_at']}
                origins.setdefault(locator,[]).append(origin)
        if len(entries)>LIMITS['entries']: raise ValueError('Acquisition entry budget exceeded')
        bundle={'resourceType':'Bundle','type':'searchset','entry':entries}
        return packed(bundle).encode(),origins

    def _publish(self, conn, row, checkpoint, query_validation):
        from .fhir_store import preview_from_native
        data,origins=self._assemble(checkpoint,row['config'])
        # retain() opens another writer; artifacts are finalized before this transaction.
        sha=checkpoint['derived_sha']
        native=parse_bundle(data)
        scope={k:row['config'][k] for k in ('source','source_base','resource_type','count')}
        if 'resource_id' in row['config']: scope['resource_id']=row['config']['resource_id']
        metadata={'acquisition_id':row['id'],'source_base':self.source.base,'scope':digest(scope),
                  'completeness':'bounded','representation':'derived_assembled_searchset',
                  'source_plan_net_version':self.source.plan_net_version,'parser_target':'Plan-Net 1.2.0 subset',
                  'resource_origins':origins,'response_artifacts':[b['sha'] for b in checkpoint['bodies']]}
        if 'resource_id' in row['config']:
            metadata['query']={k:row['config'][k] for k in ('resource_type','count','resource_id')}
            metadata['query_validation']=query_validation
        rid='acquisition-'+row['id']; aid='acquisition-attempt-'+row['id']
        spec={'profile':PROFILE,'adapter_version':VERSION,'native_projection_version':VERSION}
        conn.execute('INSERT INTO receipt VALUES (?,?,?,?,?,?,?,?,?)',(rid,'Assembled '+self.source.key+' directory.json',self.source.key,'synthetic' if self.source.test_http else 'public',now(),sha,PROFILE,None,packed(metadata)))
        preview=preview_from_native(native)
        conn.execute('INSERT INTO attempt VALUES (?,?,?,?,?,?,?,?,?)',(aid,rid,packed(spec),digest([self.source.key,metadata['scope'],sha,spec]),'preview_ready',packed(preview),now(),None,None))
        conn.execute("UPDATE fhir_acquisition SET state='complete',revision=revision+1,checkpoint=?,receipt_id=?,next_retry=NULL WHERE id=?",(packed(checkpoint),rid,row['id']))
        evidence={'receipt_id':rid,'attempt_id':aid,'derived_artifact_sha':sha}
        if query_validation is not None: evidence['query_validation']=query_validation
        self._event(conn,row['id'],'published',evidence)

    def run_once(self, acquisition_id):
        with ManagedFeed(self.store).worker_lock() as acquired:
            if not acquired: return {**self.detail(acquisition_id),'busy':True}
            return self._run(acquisition_id)

    def _run(self, acquisition_id):
        row=self.detail(acquisition_id); cp=copy.deepcopy(row['checkpoint'])
        if row['state'] in {'complete','cancelled','failed'}: return row
        if row['config']['source_base']!=self.source.base: raise ValueError('Stored source configuration differs from worker')
        if cp['pending'] and row['next_retry'] and datetime.fromisoformat(row['next_retry'])>self.clock(): return row
        node=cp['pending'][0] if cp['pending'] else None
        if node is None:
            try:
                query_validation=self._query_validation(row['config'],cp)
                data,_=self._assemble(cp,row['config']); cp['derived_sha']=self.store.retain(data)
            except (ValueError, OSError) as exc:
                return self._fail(row,cp,str(exc))
            with self.store.db() as conn:
                conn.execute('BEGIN IMMEDIATE')
                current=conn.execute('SELECT revision FROM fhir_acquisition WHERE id=?',(acquisition_id,)).fetchone()
                if current['revision']!=row['revision']: return self.detail(acquisition_id)
                self._publish(conn,row,cp,query_validation)
            return self.detail(acquisition_id)
        source_wait=False
        with self.store.db() as conn:
            conn.execute('BEGIN IMMEDIATE')
            due=self._source_due(conn)
            if due and due>self.clock():
                changed=conn.execute("UPDATE fhir_acquisition SET state='retry_wait',next_retry=?,revision=revision+1 WHERE id=? AND revision=?",(due.isoformat(),acquisition_id,row['revision'])).rowcount
                if changed:self._event(conn,acquisition_id,'source_wait',{'source_wait_until':due.isoformat(),'reason':'Configured source cooldown applies across acquisitions; no request sent'})
                source_wait=True
        if source_wait:return self.detail(acquisition_id)
        url=self.validate_url(node['url'])
        if cp['requests']>=LIMITS['requests'] or cp['active_seconds']>=LIMITS['active_seconds'] or cp['bytes']>=LIMITS['total_bytes'] or cp['attempts'].get(url,0)>=LIMITS['attempts']:
            return self._fail(row,cp,'Acquisition request/time/byte/retry budget exceeded')
        cp['requests']+=1; cp['attempts'][url]=cp['attempts'].get(url,0)+1
        request_due=self.clock()+timedelta(seconds=self.source.interval_seconds)
        with self.store.db() as conn:
            conn.execute('BEGIN IMMEDIATE')
            changed=conn.execute("UPDATE fhir_acquisition SET state='running',revision=revision+1,checkpoint=? WHERE id=? AND revision=?",(packed(cp),acquisition_id,row['revision'])).rowcount
            if not changed: return self.detail(acquisition_id)
            self._event(conn,acquisition_id,'request',{**node,'source_wait_until':request_due.isoformat()})
        token=row['revision']+1
        started=time.monotonic()
        response=self.fetcher(url,min(LIMITS['response_bytes'],LIMITS['total_bytes']-cp['bytes']),LIMITS['socket_seconds'])
        cp['active_seconds']+=time.monotonic()-started; cp['bytes']+=len(response['body'])
        sha=self.store.retain(response['body']) if response['body'] else None
        evidence={k:v for k,v in response.items() if k!='body'}; evidence.update(url=url,kind=node['kind'],bytes=len(response['body']))
        if 'source_url' in node: evidence['source_url']=node['source_url']
        state='queued'; retry=self.clock()+timedelta(seconds=self.source.interval_seconds); source_due=max(request_due,retry)
        try:
            status=response['status']
            transient=response.get('error') or status in {429,500,502,503,504}
            if transient:
                delay=response['headers'].get('retry-after','')
                try: seconds=max(0,float(delay))
                except ValueError:
                    try: seconds=max(0,(parsedate_to_datetime(delay)-self.clock()).total_seconds())
                    except (ValueError,TypeError): seconds=2**cp['attempts'][url]
                retry=self.clock()+timedelta(seconds=max(self.source.interval_seconds,seconds))
                source_due=max(source_due,retry)
            if response['truncated'] or cp['active_seconds']>LIMITS['active_seconds']: raise ValueError('Response byte/time budget exceeded')
            if transient:
                if cp['attempts'][url]>=LIMITS['attempts']: raise ValueError('Transient request exhausted retry budget')
                state='retry_wait'; cp['error']=response.get('error') or f'HTTP {status}'
            elif status in {301,302,303,307,308}:
                if not response['headers'].get('location'): raise ValueError('Redirect has no Location')
                cp['pending'][0].update(self._node(urljoin(url,response['headers']['location']),node['kind']))
            elif status!=200: raise ValueError(f'Unexpected source HTTP {status}')
            else:
                data=load_fhir_json(response['body'])
                if node['kind']=='page':
                    parse_bundle(response['body'])
                    if 'resource_id' in row['config']:
                        search_page_counts(data,row['config']['resource_type'],row['config']['resource_id'])
                    cp['pages']+=1
                    links=data.get('link',[])
                    if not isinstance(links,list) or any(not isinstance(link,dict) for link in links): raise ValueError('Invalid searchset links')
                    nexts=[link.get('url') for link in links if link.get('relation')=='next']
                    if len(nexts)>1: raise ValueError('Ambiguous next page')
                else:
                    if not isinstance(data,dict) or data.get('resourceType')!=urlsplit(url).path.strip('/').split('/')[-2] or data.get('id')!=urlsplit(url).path.strip('/').split('/')[-1]: raise ValueError('Reference response identity does not match request')
                    cp['references']+=1; nexts=[]
                retained={'sha':sha,'url':url,'kind':node['kind'],'retrieved_at':self.clock().isoformat()}
                if 'source_url' in node: retained['source_url']=node['source_url']
                cp['bodies'].append(retained)
                cp['completed_urls'].append(url); cp['pending'].pop(0); cp['error']=None
                if nexts:
                    next_node=self._node(urljoin(url,nexts[0]),'page'); destination=next_node['url']
                    if destination in cp['completed_urls']: raise ValueError('Pagination cycle')
                    if cp['pages']>=LIMITS['pages']: raise ValueError('Search page budget exceeded')
                    cp['pending'].insert(0,next_node)
                assembled,_=self._assemble(cp,row['config'])
                if not cp['pending']:
                    parsed=parse_bundle(assembled)
                    resources={r['locator']:r for r in parsed['resources']}
                    for ref in parsed['references']:
                        if ref['state']!='unresolved' or not isinstance(ref['raw_target'],str): continue
                        advertised=urljoin(self.source.base,ref['raw_target'])
                        resource=resources[ref['origin']]; own=resource['fullUrl']
                        suffix=f"{resource['resource_type']}/{resource['id']}"
                        if (re.fullmatch(r'[A-Za-z]+/[A-Za-z0-9.\-]{1,64}',ref['raw_target']) and isinstance(own,str)
                                and urlsplit(own).scheme in {'http','https'} and own.endswith(suffix)):
                            advertised=own[:-len(suffix)]+ref['raw_target']
                        try: reference_node=self._node(advertised,'reference')
                        except ValueError: continue
                        destination=reference_node['url']
                        if urlsplit(destination).query or len(urlsplit(destination).path.strip('/').split('/'))!=2: continue
                        if destination not in cp['completed_urls'] and all(n['url']!=destination for n in cp['pending']):
                            if cp['references']+len(cp['pending'])>=LIMITS['references']: raise ValueError('Reference request budget exceeded')
                            cp['pending'].append(reference_node)
        except (ValueError,TypeError,KeyError,OverflowError,RecursionError,OSError) as exc:
            state='failed'; cp['error']=str(exc); retry=None
        with self.store.db() as conn:
            conn.execute('BEGIN IMMEDIATE')
            evidence['source_wait_until']=source_due.isoformat()
            self._event(conn,acquisition_id,'response',evidence,sha)
            changed=conn.execute('UPDATE fhir_acquisition SET state=?,checkpoint=?,next_retry=?,revision=revision+1 WHERE id=? AND revision=?',
                                 (state,packed(cp),retry.isoformat() if retry else None,acquisition_id,token)).rowcount
            if not changed: self._event(conn,acquisition_id,'discarded_response',{'reason':'Concurrent revision/cancellation fenced result'},sha)
        return self.detail(acquisition_id)

    def _fail(self,row,cp,message):
        cp['error']=message
        with self.store.db() as conn:
            conn.execute('BEGIN IMMEDIATE')
            changed=conn.execute("UPDATE fhir_acquisition SET state='failed',checkpoint=?,revision=revision+1,next_retry=NULL WHERE id=? AND revision=?",(packed(cp),row['id'],row['revision'])).rowcount
            if changed:self._event(conn,row['id'],'failed',{'error':message})
        return self.detail(row['id'])
