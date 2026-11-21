import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { afterEach, expect, test, vi } from 'vitest';
import { IntakeWorkbench } from './IntakeWorkbench';

afterEach(() => {
  vi.unstubAllGlobals();
  history.replaceState(null, '', '/');
});

test('overdue filter uses calendar days and excludes closed and undated cases', async () => {
  const localDate = (offset: number) => {
    const date = new Date();
    date.setDate(date.getDate() + offset);
    return [date.getFullYear(), String(date.getMonth() + 1).padStart(2, '0'), String(date.getDate()).padStart(2, '0')].join('-');
  };
  const cases = [
    {id:'past', provider_name:'Past clinician', follow_up:localDate(-1), status:'new', owner:'  '},
    {id:'today', provider_name:'Today clinician', follow_up:localDate(0), status:'new'},
    {id:'future', provider_name:'Future clinician', follow_up:localDate(1), status:'new'},
    {id:'closed', provider_name:'Closed clinician', follow_up:localDate(-1), status:'resolved'},
    {id:'unknown', provider_name:'Unscheduled clinician', follow_up:null, status:'new'},
    {id:'invalid', provider_name:'Invalid clinician', follow_up:'2026-02-30', status:'new'},
  ].map(item => ({kind:'qa', issue:'Phone review', owner:null, ...item}));
  vi.stubGlobal('fetch', vi.fn(async () => new Response(JSON.stringify({items: cases}))));
  render(<IntakeWorkbench page='work' />);
  await screen.findByRole('button', {name:/Today clinician/});
  fireEvent.click(screen.getByRole('checkbox', {name:'Overdue follow-up'}));
  expect(screen.getByRole('button', {name:/Past clinician/})).toBeVisible();
  expect(screen.getByRole('button', {name:/Past clinician/})).toHaveTextContent('Unassigned');
  fireEvent.click(screen.getByRole('checkbox', {name:'Unassigned'}));
  expect(screen.getByRole('button', {name:/Past clinician/})).toBeVisible();
  for (const name of ['Today', 'Future', 'Closed', 'Unscheduled', 'Invalid']) {
    expect(screen.queryByRole('button', {name:new RegExp(`${name} clinician`)})).not.toBeInTheDocument();
  }
});

test('case return link preserves applied candidate search without copying work-only filters', () => {
  history.replaceState(null, '', '/?view=work&proposal=p1&run=r1&candidate_search=synthetic&search=work-only');
  vi.stubGlobal('fetch', vi.fn(async () => new Response(JSON.stringify({items: []}))));
  render(<IntakeWorkbench page='work' />);
  const link = screen.getByRole('link', {name:'Return to change assessment and follow-up receipt'});
  const query = new URL(link.getAttribute('href')!, window.location.href).searchParams;
  expect(query.get('run')).toBe('r1');
  expect(query.get('proposal')).toBe('p1');
  expect(query.get('candidate_search')).toBe('synthetic');
  expect(query.has('search')).toBe(false);
});

test('work filters follow navigation while the queue remains open', async () => {
  const cases = [
    {id:'north', provider_name:'North clinician', kind:'qa', issue:'Phone review', status:'new'},
    {id:'south', provider_name:'South clinician', kind:'qa', issue:'Phone review', status:'new'},
  ];
  history.replaceState(null, '', '/?view=work&search=North');
  vi.stubGlobal('fetch', vi.fn(async () => new Response(JSON.stringify({items: cases}))));
  render(<IntakeWorkbench page='work' />);
  expect(await screen.findByRole('button', {name:/North clinician/})).toBeVisible();
  expect(screen.queryByRole('button', {name:/South clinician/})).not.toBeInTheDocument();
  history.pushState(null, '', '/?view=work&search=South&unassigned=1');
  fireEvent.popState(window);
  expect(screen.getByLabelText('Search work')).toHaveValue('South');
  expect(screen.getByRole('checkbox', {name:'Unassigned'})).toBeChecked();
  expect(screen.getByRole('button', {name:/South clinician/})).toBeVisible();
  expect(screen.queryByRole('button', {name:/North clinician/})).not.toBeInTheDocument();
});

test('work queue distinguishes a failed load from an empty queue and can retry', async () => {
  const fetchWork = vi.fn()
    .mockResolvedValueOnce(new Response(JSON.stringify({detail:'Work service unavailable'}), {status:503}))
    .mockResolvedValueOnce(new Response(JSON.stringify({items:[]})));
  vi.stubGlobal('fetch', fetchWork);
  render(<IntakeWorkbench page='work' />);
  expect(await screen.findByRole('alert')).toHaveTextContent('Work service unavailable');
  expect(screen.queryByText('No work matches these filters.')).not.toBeInTheDocument();
  fireEvent.click(screen.getByRole('button', {name:'Retry / refresh'}));
  expect(await screen.findByText('No work matches these filters.')).toBeVisible();
  expect(screen.queryByRole('alert')).not.toBeInTheDocument();
});

test('a failed work queue refresh labels the retained results as stale', async () => {
  const item = {id:'north', provider_name:'North clinician', kind:'qa', issue:'Phone review', status:'new'};
  const fetchWork = vi.fn()
    .mockResolvedValueOnce(new Response(JSON.stringify({items:[item]})))
    .mockResolvedValueOnce(new Response(JSON.stringify({detail:'Work service unavailable'}), {status:503}));
  vi.stubGlobal('fetch', fetchWork);
  render(<IntakeWorkbench page='work' />);
  expect(await screen.findByRole('button', {name:/North clinician/})).toBeVisible();
  fireEvent.click(screen.getByRole('button', {name:'Refresh'}));
  expect(await screen.findByRole('alert')).toHaveTextContent('Work service unavailable');
  expect(screen.getByText('Showing previously loaded work; the latest refresh failed and these results may be out of date.')).toBeVisible();
  expect(screen.getByRole('button', {name:/North clinician/})).toBeVisible();
  expect(screen.queryByText('No work matches these filters.')).not.toBeInTheDocument();
});

test('switching case actions does not submit hidden assignment fields', async () => {
  const detail = {id:'case-1',kind:'correction',provider_name:'Synthetic clinician',location_id:'NORTH',status:'new',issue:'Phone review',version:0,owner:'Existing owner',evidence:{original:{},normalized:{}},history:[],later_evidence:[]};
  const events: unknown[] = [];
  vi.stubGlobal('fetch', vi.fn(async (url: string, init?: RequestInit) => {
    if (init?.method === 'POST') events.push(JSON.parse(String(init.body)));
    return new Response(JSON.stringify(url === '/api/work' ? {items:[detail]} : detail));
  }));
  render(<IntakeWorkbench page='work' />);
  fireEvent.click(await screen.findByRole('button', {name:/Synthetic clinician/}));
  await screen.findByRole('heading', {name:'Synthetic clinician'});
  fireEvent.change(screen.getByLabelText(/actor/i), {target:{value:'Analyst'}});
  fireEvent.change(screen.getByLabelText(/reason/i), {target:{value:'Investigate conflict'}});
  fireEvent.change(screen.getByPlaceholderText('Current: Existing owner'), {target:{value:'Old draft owner'}});
  fireEvent.change(screen.getByLabelText(/follow up/i, {selector:'input'}), {target:{value:'2026-12-01'}});
  fireEvent.change(screen.getByLabelText('Action'), {target:{value:'triage'}});
  fireEvent.click(screen.getByRole('button', {name:'Save review event'}));
  await waitFor(() => expect(events).toEqual([{actor:'Analyst',reason:'Investigate conflict',action:'triage',expected_version:0}]));
});

test('CMS lookup sends its supported NPI query without NPPES-only fields', async () => {
  const lookups: unknown[] = [];
  vi.stubGlobal('fetch', vi.fn(async (url: string, init?: RequestInit) => {
    if (url === '/api/intakes/lookups') {
      lookups.push(JSON.parse(String(init?.body)));
      return new Response(JSON.stringify({id:'synthetic-reference'}),{status:200});
    }
    return new Response(JSON.stringify(url === '/api/intakes' ? {items:[]} : {id:'synthetic-reference',label:'Synthetic CMS response',state:'preview_ready',metadata:{},attempts:[],observations:[],linked_cases:[]}),{status:200});
  }));
  render(<IntakeWorkbench page='intake' />);
  fireEvent.click(screen.getByText('Look up a public reference'));
  fireEvent.change(screen.getByRole('combobox',{name:/^Reference$/}),{target:{value:'cms'}});
  fireEvent.change(screen.getByLabelText('NPI (optional)'),{target:{value:'1234567890'}});
  fireEvent.click(screen.getByRole('button',{name:'Fetch reference'}));
  await waitFor(()=>expect(lookups).toEqual([{source:'cms',query:{npi:'1234567890',limit:10}}]));
  await screen.findByRole('heading',{name:'Synthetic CMS response'});
});

test('sample columns fill an editable form without accepting or saving until the reviewer acts', async () => {
  const calls: {url: string; body: Record<string, unknown>}[] = [];
  const mapping = {
    npi: 'Registry number', provider_name: 'Clinician', address: 'Street', city: 'Town',
    state: 'Region', zip: 'Postal', phone: 'Listed phone', record_id: 'Roster key',
    location_id: 'Site key', reference_phone: 'Requested phone',
  };
  const receipt = {
    id: 'sample-receipt', label: 'synthetic-clinic.xlsx', source: 'synthetic-demo', designation: 'synthetic',
    state: 'needs_mapping', attempt_id: 'attempt-1',
    metadata: {demo_sample: 'clinic-workbook', suggested_mapping: mapping},
    attempts: [{id: 'attempt-1', spec: {header_row: 2, sheet: 'Clinic roster'}}],
    preview: {headers: Object.values(mapping), mapping: {}, state: 'needs_mapping', rows: [], valid_count: 0},
    observations: [], linked_cases: [],
  };
  vi.stubGlobal('fetch', vi.fn(async (url: string, init?: RequestInit) => {
    if (init?.method === 'POST') calls.push({url, body: JSON.parse(String(init.body))});
    if (url === '/api/demo/samples') return new Response(JSON.stringify({items: [
      {id: 'clinic-workbook', label: 'Synthetic clinic workbook', description: 'Two locations and one malformed row.'},
    ]}));
    if (url === '/api/intakes') return new Response(JSON.stringify({items: []}));
    return new Response(JSON.stringify(receipt));
  }));
  render(<IntakeWorkbench page='intake' />);
  fireEvent.click(await screen.findByRole('button', {name: 'Load synthetic sample'}));
  await screen.findByRole('heading', {name: 'synthetic-clinic.xlsx'});
  await waitFor(() => expect(screen.getByLabelText('Header row')).toHaveValue(2));
  expect(screen.getByRole('button', {name: 'Accept valid rows'})).toBeDisabled();
  expect(screen.getByLabelText('npi *')).toHaveValue('');
  fireEvent.click(screen.getByRole('button', {name: 'Use suggested columns'}));
  expect(screen.getByLabelText('npi *')).toHaveValue('Registry number');
  expect(screen.getByLabelText('location id (optional)')).toHaveValue('Site key');
  expect(calls).toEqual([{url: '/api/demo/samples/clinic-workbook', body: {}}]);
  fireEvent.change(screen.getByLabelText('npi *'), {target: {value: 'Clinician'}});
  fireEvent.click(screen.getByRole('button', {name: 'Save mapping and reprocess'}));
  await waitFor(() => expect(calls).toHaveLength(2));
  expect(calls[1]).toMatchObject({url: '/api/intakes/sample-receipt/mapping', body: {
    header_row: 2, mapping: {...mapping, npi: 'Clinician'},
  }});
  expect(calls.some(call => call.url.endsWith('/commit'))).toBe(false);
  expect(screen.getByLabelText('Synthetic sample next step')).toHaveTextContent('no real clinicians');
});

test('ordinary uploads remain available when synthetic sample mode is disabled', async () => {
  vi.stubGlobal('fetch', vi.fn(async () => new Response(JSON.stringify({items: []}))));
  render(<IntakeWorkbench page='intake' />);
  await screen.findByText('No deliveries yet. Upload a file to begin.');
  expect(screen.queryByRole('button', {name: 'Load synthetic sample'})).not.toBeInTheDocument();
  expect(screen.getByLabelText('Source file')).toBeInTheDocument();
  expect(screen.getByRole('button', {name: 'Upload and preview'})).toBeDisabled();
});

test('XLSX links distinguish the full queue from the selected case regardless of filters', async () => {
  history.replaceState(null, '', '/?view=work&case=case-1&search=not-matching');
  vi.stubGlobal('fetch', vi.fn(async (url: string) => new Response(JSON.stringify(
    url === '/api/work' ? {items: []} : {
      id: 'case-1', provider_name: 'Synthetic clinician', kind: 'correction', status: 'new', version: 0,
      location_id: 'synthetic-demo:NORTH', evidence: {}, history: [], later_evidence: [],
    },
  ))));
  render(<IntakeWorkbench page='work' />);
  expect(screen.getByRole('link', {name: 'Download all work XLSX'})).toHaveAttribute('href', '/api/work-export.xlsx');
  expect(screen.getByText(/ignores the filters below/)).toBeInTheDocument();
  expect(await screen.findByRole('link', {name: 'Download case XLSX'})).toHaveAttribute('href', '/api/work-export.xlsx?case_id=case-1');
});

test('only a reviewed empty full network snapshot can accept absence evidence', async () => {
  const commits: Record<string,unknown>[] = [];
  const receipt = {
    id:'empty-network',label:'empty-network.csv',source:'synthetic-network',designation:'synthetic',state:'preview_ready',attempt_id:'attempt-empty',
    metadata:{completeness:'full'},attempts:[{id:'attempt-empty',spec:{roster_kind:'network',mapping:{},bindings:{network:{},location:{},organization:{}}}}],
    preview:{state:'preview_ready',total:0,valid_count:0,quarantined_count:0,rows:[],mapping:{},comparison:{baseline:{attempt_id:'prior',receipt_id:'prior-receipt',label:'prior.csv',committed_at:'2026-10-30'},missing_from_this_delivery:3,entries:[]}},
    observations:[],linked_cases:[],
  };
  vi.stubGlobal('fetch',vi.fn(async (url:string,init?:RequestInit) => {
    if (url === '/api/intakes') return new Response(JSON.stringify({items:[{id:receipt.id,label:receipt.label,source:receipt.source,state:receipt.state}]}));
    if (url === '/api/demo/samples') return new Response(JSON.stringify({items:[]}));
    if (url.endsWith('/saved-mappings')) return new Response(JSON.stringify({items:[]}));
    if (url.endsWith('/commit')) {commits.push(JSON.parse(String(init?.body)));return new Response(JSON.stringify({...receipt,state:'committed'}));}
    if (url === '/api/catalog') return new Response(JSON.stringify({organizations:[],networks:[],locations:[],bindings:[]}));
    return new Response(JSON.stringify(receipt));
  }));
  render(<IntakeWorkbench page="intake" />);
  fireEvent.click(await screen.findByRole('button',{name:/empty-network.csv/}));
  const accept = await screen.findByRole('button',{name:'Accept empty snapshot as absence evidence'});
  expect(accept).toBeDisabled();
  fireEvent.change(screen.getByLabelText('Reviewer',{exact:true}),{target:{value:'Synthetic Reviewer'}});
  fireEvent.change(screen.getByLabelText('Acceptance / rejection reason'),{target:{value:'Full scoped empty file reviewed'}});
  expect(accept).toBeEnabled();
  fireEvent.click(accept);
  await waitFor(() => expect(commits).toEqual([{policy:'valid_rows',actor:'Synthetic Reviewer',reason:'Full scoped empty file reviewed',expected_attempt:'attempt-empty'}]));
});

test('a follow-up-only case remains discoverable by network/location and has separate review scope', async () => {
  const followUp = {target_key:'follow-target',kind:'follow_up',source:'payer follow-up',field:'phone',clinician_id:'clinician-one',clinician_label:'Alex reviewed',network_id:'cedar-id',network_label:'CEDAR',organization_id:'org-one',organization_label:'Clinic',practice_location_id:'north-id',location_label:'NORTH',confirmation_id:'confirmation-one'};
  const detail = {id:'follow-case',kind:'qa',provider_name:'Alex follow-up',location_id:'north-id',network_id:null,practice_location_id:null,scope:null,follow_up_scopes:[followUp],status:'new',issue:'Review proposed phone',version:0,owner:null,evidence:{original:{phone:'2125550101'},normalized:{phone:'2125550101'}},history:[],later_evidence:[]};
  vi.stubGlobal('fetch',vi.fn(async(url:string)=>new Response(JSON.stringify(url==='/api/work'?{items:[detail]}:detail))));
  history.replaceState(null,'','/?view=work&network_id=cedar-id&location_id=north-id');
  render(<IntakeWorkbench page="work"/>);
  fireEvent.click(await screen.findByRole('button',{name:/Alex follow-up/}));
  expect(await screen.findByRole('region',{name:'Follow-up review scope'})).toBeVisible();
  expect(screen.queryByRole('region',{name:'Network participation scope'})).not.toBeInTheDocument();
  expect(screen.getByRole('combobox',{name:'Network filter'})).toHaveValue('cedar-id');
  expect(screen.getByRole('combobox',{name:'Practice location filter'})).toHaveValue('north-id');
  expect(screen.queryByText('No work matches these filters.')).not.toBeInTheDocument();
});
