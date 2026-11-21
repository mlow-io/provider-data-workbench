import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { afterEach, expect, test, vi } from 'vitest';
import { MappingAssistantPanel } from './MappingAssistantPanel';

const summary={id:'run-1',state:'queued',revision:0,attempt_id:'attempt-1',proposal_id:null,created_at:'2026-11-14'};
const queued={...summary,request_sha:'request-hash',response_sha:null,result:{}};
const succeeded={...queued,state:'succeeded',revision:3,proposal_id:'proposal-1',response_sha:'response-hash',result:{explanation:'Review voice phone separately',unresolved:[{field:'source_updated_at',reason:'Date meaning is ambiguous'}]}};
const registry={configuration:{available:true,experimental:true,reason:null,model:'controlled-model',limits:{rows:3,columns:40,cell_bytes:160,reserve_usd:.08,lifetime_usd:1}},source_processing_allowed:true,reserved_usd:0,items:[]};
afterEach(()=>vi.unstubAllGlobals());
function fill() {
  fireEvent.change(screen.getByLabelText('Assistance operator'),{target:{value:'Synthetic operator'}});
  fireEvent.change(screen.getByLabelText('Assistance reason'),{target:{value:'Review input sample'}});
  fireEvent.click(screen.getByLabelText('Allow this source sample to be sent to OpenAI for this run'));
}
async function open() {
  fireEvent.click(screen.getByRole('button',{name:'Optional mapping assistance'}));
  await screen.findByText('controlled-model',{exact:true});
}

test('collapsed panel makes no requests; unavailable assistance preserves manual fallback',async()=>{
  const fetch=vi.fn(async()=>new Response(JSON.stringify({...registry,configuration:{...registry.configuration,available:false,reason:'No configured key'}})));
  vi.stubGlobal('fetch',fetch);
  render(<MappingAssistantPanel receiptId="receipt-1" attemptId="attempt-1" onProposalReady={async()=>{}} />);
  expect(fetch).not.toHaveBeenCalled();await open();fill();
  expect(screen.getByText(/Continue with deterministic suggestions or manual mapping/)).toBeVisible();
  expect(screen.getByRole('button',{name:'Queue model mapping'})).toBeDisabled();
  expect(fetch).toHaveBeenCalledTimes(1);
});

test('lost creation response reuses intent, proposal enters normal review and local budget refreshes',async()=>{
  const created:Record<string,unknown>[]=[];const onReady=vi.fn(async()=>{});let completed=false;
  vi.stubGlobal('fetch',vi.fn(async(url:string,init?:RequestInit)=>{
    if(!init)return new Response(JSON.stringify({...registry,reserved_usd:completed ? .08 : 0,items:completed?[succeeded]:[]}));
    if(url.endsWith('/run-once')){completed=true;return new Response(JSON.stringify(succeeded));}
    created.push(JSON.parse(String(init.body)));
    if(created.length===1)throw new Error('Lost creation response');
    return new Response(JSON.stringify(queued));
  }));
  render(<MappingAssistantPanel receiptId="receipt-1" attemptId="attempt-1" onProposalReady={onReady} />);
  await open();fill();fireEvent.click(screen.getByRole('button',{name:'Queue model mapping'}));
  await screen.findByRole('alert');
  fireEvent.click(screen.getByRole('button',{name:'Queue model mapping'}));
  await screen.findByRole('article',{name:'Selected mapping assistance run'});
  expect(created[0]).toEqual(created[1]);
  expect(created[0]).toMatchObject({external_processing:true,expected_attempt:'attempt-1'});
  expect(screen.getByRole('link',{name:'Inspect exact model request'})).toHaveAttribute('href','/api/intakes/receipt-1/assistant-runs/run-1/artifacts/request');
  fireEvent.click(screen.getByRole('button',{name:'Run queued model mapping'}));
  await screen.findByText('succeeded',{exact:true});
  await waitFor(()=>expect(onReady).toHaveBeenCalledTimes(1));
  await screen.findByText(/Local reserved allowance: \$0.08/);
  expect(screen.getByText(/Date meaning is ambiguous/)).toBeVisible();
  expect(screen.queryByRole('button',{name:'Approve recipe'})).not.toBeInTheDocument();
});

test('refresh and cancellation work during a pending model call without a second invocation',async()=>{
  let finish:(value:Response)=>void=()=>{};let running=false;let cancelled=false;let calls=0;
  const onReady=vi.fn(async()=>{});
  const live=()=>({...queued,state:cancelled?'cancelled':running?'running':'queued',revision:cancelled?2:running?1:0});
  vi.stubGlobal('fetch',vi.fn(async(url:string,init?:RequestInit)=>{
    if(url.endsWith('/run-once')){calls++;running=true;return new Promise<Response>(resolve=>{finish=resolve;});}
    if(url.endsWith('/cancel')){expect(JSON.parse(String(init?.body)).expected_revision).toBe(1);cancelled=true;return new Response(JSON.stringify(live()));}
    if(init)return new Response(JSON.stringify(queued));
    return new Response(JSON.stringify(url.endsWith('run-1')?live():registry));
  }));
  render(<MappingAssistantPanel receiptId="receipt-1" attemptId="attempt-1" onProposalReady={onReady} />);
  await open();fill();fireEvent.click(screen.getByRole('button',{name:'Queue model mapping'}));
  await screen.findByText('queued',{exact:true});
  fireEvent.click(screen.getByRole('button',{name:'Run queued model mapping'}));
  await screen.findByText(/Model request in progress/);
  fireEvent.click(screen.getByRole('button',{name:'Refresh assistance'}));
  await screen.findByText('running',{exact:true});
  await waitFor(()=>expect(screen.getByRole('button',{name:'Cancel mapping run'})).toBeEnabled());
  fireEvent.click(screen.getByRole('button',{name:'Cancel mapping run'}));
  await screen.findByText('cancelled',{exact:true});
  finish(new Response(JSON.stringify(live())));
  await waitFor(()=>expect(screen.queryByText(/Model request in progress/)).not.toBeInTheDocument());
  expect(calls).toBe(1);expect(onReady).not.toHaveBeenCalled();
  expect(screen.getByLabelText('Assistance reason')).toHaveValue('Review input sample');
});

test('a failed partial response is labeled a retained prefix rather than a complete original',async()=>{
  const failed={...queued,state:'failed',revision:2,response_sha:'partial-response',result:{error:'Incomplete provider response',response_truncated:true}};
  vi.stubGlobal('fetch',vi.fn(async(url:string)=>new Response(JSON.stringify(url.endsWith('run-1')?failed:{...registry,items:[failed]}))));
  render(<MappingAssistantPanel receiptId="receipt-1" attemptId="attempt-1" onProposalReady={async()=>{}} />);
  await open();fireEvent.change(screen.getByLabelText('Retained assistance run'),{target:{value:'run-1'}});
  await screen.findByText('failed',{exact:true});
  expect(screen.getByRole('link',{name:'Retained response prefix'})).toBeVisible();
  expect(screen.queryByRole('link',{name:'Original model response'})).not.toBeInTheDocument();
});

test('approved mapping examples require separate opt-in and remain part of creation intent',async()=>{
  const bodies:Record<string,unknown>[]=[];
  vi.stubGlobal('fetch',vi.fn(async(_url:string,init?:RequestInit)=>{
    if(init){bodies.push(JSON.parse(String(init.body)));return new Response(JSON.stringify(queued));}
    return new Response(JSON.stringify(registry));
  }));
  render(<MappingAssistantPanel receiptId="receipt-1" attemptId="attempt-1" onProposalReady={async()=>{}} />);
  await open();fill();
  const examples=screen.getByLabelText('Include reviewed mapping definitions from this source and scope as model examples');
  expect(examples).not.toBeChecked();
  fireEvent.click(screen.getByRole('button',{name:'Queue model mapping'}));
  await screen.findByText('queued',{exact:true});
  expect(bodies[0]).not.toHaveProperty('include_approved_examples');
  fireEvent.click(examples);
  fireEvent.click(screen.getByRole('button',{name:'Queue model mapping'}));
  await waitFor(()=>expect(bodies).toHaveLength(2));
  expect(bodies[1]).toMatchObject({include_approved_examples:true,external_processing:true});
  expect(bodies[1].request_id).not.toBe(bodies[0].request_id);
});
