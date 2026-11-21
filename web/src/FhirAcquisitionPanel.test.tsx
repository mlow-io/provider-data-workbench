import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { afterEach, expect, test, vi } from 'vitest';
import { FhirAcquisitionPanel } from './FhirAcquisitionPanel';

const source = {key:'hap',base:'https://configured.example/',plan_net_version:'1.0.0 source assertion',parser_target:'1.2.0 subset',interval_seconds:30,limits:{pages:3,references:12,requests:24}};
const capture = {id:'capture-1',state:'queued',revision:0,next_retry:null,receipt_id:null,created_at:'2026-11-14',partial:false,config:{resource_type:'Location',count:1,source_base:source.base},checkpoint:{pages:0,references:0,requests:0,bytes:0,error:null,pending:[{}]},events:[]};
afterEach(() => {vi.unstubAllGlobals();history.replaceState(null,'','/');});
function fill() {
  fireEvent.change(screen.getByLabelText('Capture operator'),{target:{value:'Synthetic operator'}});
  fireEvent.change(screen.getByLabelText('Capture reason'),{target:{value:'Review bounded source'}});
}
test('mount reads only; uncertain creation retry preserves one request ID and never runs a capture', async () => {
  history.replaceState(null,'','/?view=sources');
  const calls: {url:string;body?:Record<string,unknown>}[]=[];
  vi.stubGlobal('fetch',vi.fn(async (url:string,init?:RequestInit) => {
    const body=init?.body?JSON.parse(String(init.body)):undefined; calls.push({url,body});
    if(body) {if(calls.filter(call=>call.body).length===1) throw new Error('Lost response');return new Response(JSON.stringify(capture));}
    return new Response(JSON.stringify(url.endsWith('capture-1')?capture:{source,items:[]}));
  }));
  render(<FhirAcquisitionPanel />);
  await screen.findByText('hap',{exact:true});expect(calls).toEqual([{url:'/api/fhir-acquisitions',body:undefined}]);
  fill();fireEvent.click(screen.getByRole('button',{name:'Queue bounded capture'}));
  await screen.findByRole('alert');
  expect(screen.getByLabelText('Capture reason')).toHaveValue('Review bounded source');
  fireEvent.click(screen.getByRole('button',{name:'Queue bounded capture'}));
  await screen.findByRole('article',{name:'Selected FHIR capture'});
  const posted=calls.filter(call=>call.body);expect(posted).toHaveLength(2);
  expect(posted[0].body).toEqual(posted[1].body);
  expect(calls.some(call=>call.url.endsWith('run-once'))).toBe(false);
  expect(location.search).toContain('acquisition=capture-1');
});

test('persisted throttle disables requests; stale cancellation preserves draft and refresh is read-only', async () => {
  history.replaceState(null,'','/?view=sources&acquisition=capture-1');
  const waiting={...capture,state:'retry_wait',next_retry:'2099-01-01T00:00:00Z',revision:2,checkpoint:{...capture.checkpoint,requests:1,error:'HTTP 429'}};
  const posted:Record<string,unknown>[]=[];
  vi.stubGlobal('fetch',vi.fn(async (url:string,init?:RequestInit)=>{
    if(init?.body) {posted.push(JSON.parse(String(init.body)));return new Response(JSON.stringify({detail:'Acquisition changed'}),{status:409});}
    return new Response(JSON.stringify(url.endsWith('capture-1')?waiting:{source,items:[waiting]}));
  }));
  render(<FhirAcquisitionPanel />);
  await screen.findByText('retry wait',{exact:true});
  expect(screen.getByRole('button',{name:'Run one capture step'})).toBeDisabled();
  fill();fireEvent.click(screen.getByRole('button',{name:'Cancel capture'}));
  await screen.findByRole('alert');
  expect(posted).toEqual([{expected_revision:2,actor:'Synthetic operator',reason:'Review bounded source'}]);
  expect(screen.getByLabelText('Capture reason')).toHaveValue('Review bounded source');
  fireEvent.click(screen.getByRole('button',{name:'Refresh captures'}));
  await waitFor(()=>expect(screen.getByRole('button',{name:'Refresh captures'})).toBeEnabled());
  expect(posted).toHaveLength(1);
});

test('unavailable registry stays an error and can recover without offering a configured source', async () => {
  let unavailable=true;
  vi.stubGlobal('fetch',vi.fn(async ()=>unavailable?new Response(JSON.stringify({detail:'Storage unavailable'}),{status:503}):new Response(JSON.stringify({source,items:[]}))));
  render(<FhirAcquisitionPanel />);
  await screen.findByRole('alert');fill();
  expect(screen.getByRole('button',{name:'Queue bounded capture'})).toBeDisabled();
  expect(screen.queryByText('No captures recorded.',{exact:false})).not.toBeInTheDocument();
  unavailable=false;fireEvent.click(screen.getByRole('button',{name:'Refresh captures'}));
  await screen.findByText('hap',{exact:true});
  expect(screen.getByRole('button',{name:'Queue bounded capture'})).toBeEnabled();
});

test('source-wide cooldown blocks a queued capture even when its own retry time is empty',async()=>{
  history.replaceState(null,'','/?view=sources&acquisition=capture-1');
  vi.stubGlobal('fetch',vi.fn(async(url:string)=>new Response(JSON.stringify(url.endsWith('capture-1')?capture:{source:{...source,next_request_at:'2099-01-01T00:00:00Z'},items:[capture]}))));
  render(<FhirAcquisitionPanel />);
  await screen.findByText('queued',{exact:true});
  expect(screen.getByRole('button',{name:'Run one capture step'})).toBeDisabled();
  expect(screen.getByText(/It applies across captures, including cancelled ones/)).toBeVisible();
});

test('source-native ID validates before queueing and stays in the explicit capture scope',async()=>{
  const posted:Record<string,unknown>[]=[];
  const filtered={...capture,config:{...capture.config,resource_id:'north-1'}};
  vi.stubGlobal('fetch',vi.fn(async(url:string,init?:RequestInit)=>{
    if(init?.body){posted.push(JSON.parse(String(init.body)));return new Response(JSON.stringify(filtered));}
    return new Response(JSON.stringify(url.endsWith('capture-1')?filtered:{source,items:[]}));
  }));
  render(<FhirAcquisitionPanel />);
  await screen.findByText('hap',{exact:true});fill();
  fireEvent.change(screen.getByLabelText('Source-native resource ID (optional)'),{target:{value:'../Patient/x'}});
  expect(screen.getByRole('button',{name:'Queue bounded capture'})).toBeDisabled();
  expect(posted).toEqual([]);
  fireEvent.change(screen.getByLabelText('Source-native resource ID (optional)'),{target:{value:'north-1'}});
  fireEvent.click(screen.getByRole('button',{name:'Queue bounded capture'}));
  await screen.findByRole('article',{name:'Selected FHIR capture'});
  expect(posted).toHaveLength(1);expect(posted[0].resource_id).toBe('north-1');
  expect(screen.getByText('Source resource ID:',{exact:false})).toHaveTextContent('north-1');
  expect(posted[0]).not.toHaveProperty('url');
});
