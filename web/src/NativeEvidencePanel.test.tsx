import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, expect, test, vi } from "vitest";
import { NativeEvidencePanel, type NativePreview } from "./NativeEvidencePanel";

const native: NativePreview = {
  format_version: 1, parser_version: "v1", validation: {structural:"assessed",profile:"not_run",terminology:"not_run"},
  coverage: {entry_count:3,supported_count:2,eligible_count:2,unsupported_count:1,invalid_count:0,unresolved_count:1,assertion_count:0,completeness:"unknown_saved_scope"},
  resources: [{locator:"$.entry[0].resource",resource_type:"Location",id:"NORTH",original:{resourceType:"Location",id:"NORTH"},eligible:true,problems:[]}],
  references:[{path:"$.entry[1].resource.practitioner.reference",raw_target:"Practitioner/missing",state:"unresolved",target:null}],
  assertions:[],findings:[{code:"unsupported_resource",locator:"$.entry[2].resource",message:"InsurancePlan retained",severity:"warning"}],
};
const receipt = {id:"receipt-1",label:"directory.json",profile:"fhir-plannet-r4",source:"synthetic",designation:"synthetic",state:"preview_ready",attempt_id:"attempt-1",artifact_sha:"hash",preview:{native,valid_count:2}};
afterEach(() => vi.unstubAllGlobals());
function fill() {
  fireEvent.change(screen.getByLabelText("Reference reviewer"), {target:{value:"Synthetic analyst"}});
  fireEvent.change(screen.getByLabelText("Reference review reason"), {target:{value:"Review saved evidence"}});
}

test("native review shows resource semantics, incomplete validation and source downloads", () => {
  render(<NativeEvidencePanel receipt={receipt} refresh={async () => {}} />);
  expect(screen.getByText(/3 entries · 2 supported/)).toBeVisible();
  expect(screen.getByText(/0 invalid resources/)).toBeVisible();
  expect(screen.getByText(/Location · NORTH/)).toBeVisible();
  expect(screen.getByText(/unresolved · Practitioner\/missing/)).toBeVisible();
  expect(screen.getByText(/Structural inspection is separate/)).toBeVisible();
  expect(screen.queryByText("Column mapping and parsing")).not.toBeInTheDocument();
  expect(screen.getByRole("link",{name:"Evidence packet JSON"})).toHaveAttribute("href","/api/intakes/receipt-1/packet");
  expect(screen.getByRole("button",{name:"Accept reference resources"})).toBeDisabled();
});

test("uncertain identical retry reuses request ID and preserves draft while changed intent creates a new ID", async () => {
  const calls: Record<string,unknown>[] = [];
  const refresh = vi.fn(async () => {});
  vi.stubGlobal("fetch",vi.fn(async (_url, init) => {
    calls.push(JSON.parse(init.body));
    if (calls.length===1) throw new Error("Connection lost");
    return new Response("{}");
  }));
  render(<NativeEvidencePanel receipt={receipt} refresh={refresh} />);
  fill();
  fireEvent.click(screen.getByRole("button",{name:"Accept reference resources"}));
  await screen.findByRole("alert");
  expect(screen.getByLabelText("Reference review reason")).toHaveValue("Review saved evidence");
  fireEvent.click(screen.getByRole("button",{name:"Accept reference resources"}));
  await waitFor(() => expect(refresh).toHaveBeenCalledTimes(1));
  expect(calls[0]).toEqual(calls[1]);
  expect(calls[0]).toMatchObject({policy:"reference_resources",expected_attempt:"attempt-1"});
  await waitFor(() => expect(screen.getByRole("button",{name:"Accept reference resources"})).toBeEnabled());
  fireEvent.change(screen.getByLabelText("Reference review reason"),{target:{value:"Changed intent"}});
  fireEvent.click(screen.getByRole("button",{name:"Reject reference intake"}));
  await waitFor(() => expect(calls).toHaveLength(3));
  expect(calls[2].request_id).not.toBe(calls[0].request_id);
  expect(calls[2].policy).toBe("reject");
});

test("read-only selected attempts have no mutation controls and show newer interpretation", () => {
  render(<NativeEvidencePanel receipt={{...receipt,is_current_attempt:false}} readOnly refresh={async () => {}} />);
  expect(screen.queryByRole("button",{name:"Accept reference resources"})).not.toBeInTheDocument();
  expect(screen.queryByRole("button",{name:"Reprocess saved FHIR evidence"})).not.toBeInTheDocument();
  expect(screen.getByRole("status")).toHaveTextContent("newer interpretation");
});

test("terminal decisions cannot be resubmitted; reprocessing sends only expected attempt", async () => {
  const fetch = vi.fn(async (_url: string, _init?: RequestInit) => new Response("{}")); vi.stubGlobal("fetch",fetch);
  const refresh=vi.fn(async () => {});
  render(<NativeEvidencePanel receipt={{...receipt,state:"committed"}} refresh={refresh} />);
  fill();
  expect(screen.getByRole("button",{name:"Accept reference resources"})).toBeDisabled();
  expect(screen.getByRole("button",{name:"Reject reference intake"})).toBeDisabled();
  fireEvent.click(screen.getByRole("button",{name:"Reprocess saved FHIR evidence"}));
  await waitFor(() => expect(refresh).toHaveBeenCalled());
  expect(JSON.parse(String(fetch.mock.calls[0][1]?.body))).toEqual({expected_attempt:"attempt-1"});
});

test("failed and empty interpretations stay inspectable and cannot be accepted", () => {
  render(<NativeEvidencePanel receipt={{...receipt,state:"failed",preview:{error:"Invalid FHIR envelope",valid_count:0}}} refresh={async () => {}} />);
  fill();
  expect(screen.getByRole("alert")).toHaveTextContent("Invalid FHIR envelope");
  expect(screen.getByRole("button",{name:"Accept reference resources"})).toBeDisabled();
  expect(screen.getByRole("button",{name:"Reject reference intake"})).toBeEnabled();
});

test("bounded sample placeholders and refresh errors remain readable", () => {
  const sampled = {...native,sample_truncated:true,resources:[{sample_truncated:true}],references:[{sample_truncated:true}],assertions:[{sample_truncated:true}],findings:[{sample_truncated:true}]} as unknown as NativePreview;
  render(<NativeEvidencePanel receipt={{...receipt,preview:{native:sampled,valid_count:2}}} loadError="Refresh failed" refresh={async () => {}} />);
  expect(screen.getByRole('status')).toHaveTextContent('Bounded sample shown');
  expect(screen.getByRole('alert')).toHaveTextContent('Refresh failed');
});

test("receipt workspace routes native evidence away from clinic mapping and normalization", async () => {
  const {IntakeWorkbench}=await import('./IntakeWorkbench');
  history.replaceState(null,'','/?view=intake&receipt=receipt-1');
  const calls:string[]=[];
  vi.stubGlobal('fetch',vi.fn(async (url:string)=>{
    calls.push(url);
    return new Response(JSON.stringify(url==='/api/intakes/receipt-1'?receipt:{items:[]}));
  }));
  render(<IntakeWorkbench page="intake" />);
  await screen.findByRole('region',{name:'Native FHIR evidence'});
  expect(screen.queryByText('Column mapping and parsing')).not.toBeInTheDocument();
  expect(screen.queryByRole('button',{name:'Profile and normalize'})).not.toBeInTheDocument();
  expect(calls.some(url=>url.includes('/recipes')||url.includes('/profile?'))).toBe(false);
});

test("assembled network evidence is never labeled an original response", () => {
  render(<NativeEvidencePanel receipt={{...receipt,metadata:{representation:'derived_assembled_searchset',acquisition_id:'capture-1',source_plan_net_version:'1.0.0 source assertion',parser_target:'1.2.0 subset'}}} refresh={async () => {}} />);
  expect(screen.queryByRole('link',{name:'Download original'})).not.toBeInTheDocument();
  expect(screen.getByRole('link',{name:'Download assembled searchset'})).toHaveAttribute('href','/api/intakes/receipt-1/artifact');
  expect(screen.getByRole('link',{name:'Acquisition history JSON'})).toHaveAttribute('href','/api/fhir-acquisitions/capture-1');
  expect(screen.getByText(/Compatibility is unverified/)).toBeVisible();
});

test('filtered query report separates matches, included context and source outcomes',()=>{
  render(<NativeEvidencePanel receipt={{...receipt,metadata:{representation:'derived_assembled_searchset',
    query:{resource_type:'Location',resource_id:'north'},query_validation:{version:1,matched_entries:1,
      implicit_match_entries:1,included_entries:2,outcome_entries:1}}}} refresh={async()=>{}} />);
  expect(screen.getByRole('region',{name:'Source query scope'})).toHaveTextContent('Source resource ID north');
  expect(screen.getByText('Checked matches: 1 · Included context: 2 · Source outcomes: 1')).toBeVisible();
  expect(screen.getByText(/Matching entries without a search mode: 1/)).toBeVisible();
  expect(screen.getByText(/Profile validation:/)).toHaveTextContent('not run');
});

test('older filtered receipt does not inherit a new match-validation claim',()=>{
  render(<NativeEvidencePanel receipt={{...receipt,metadata:{representation:'derived_assembled_searchset',
    query:{resource_type:'Location',resource_id:'north'}}}} refresh={async()=>{}} />);
  expect(screen.getByText(/Match validation was not recorded for this capture/)).toBeVisible();
  expect(screen.queryByText(/Checked matches:/)).not.toBeInTheDocument();
});

test('unsupported query report stays explicit rather than appearing verified',()=>{
  render(<NativeEvidencePanel receipt={{...receipt,metadata:{representation:'derived_assembled_searchset',
    query:{resource_type:'Location',resource_id:'north'},query_validation:{version:99}}}} refresh={async()=>{}} />);
  expect(screen.getByText(/Unsupported search-match report version/)).toBeVisible();
  expect(screen.queryByText(/Checked matches:/)).not.toBeInTheDocument();
});
