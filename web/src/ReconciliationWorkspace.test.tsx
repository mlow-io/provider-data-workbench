import {
  fireEvent,
  act,
  render,
  screen,
  waitFor,
  within,
} from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { afterEach, expect, test, vi } from "vitest";
import { ReconciliationWorkspace } from "./ReconciliationWorkspace";

afterEach(() => {
  vi.unstubAllGlobals();
  history.replaceState(null, "", "/");
});
const receipts = ["Clinic", "Payer", "Reference"].map((label, index) => ({
  id: `receipt-${index}`,
  label,
  source: label.toLowerCase(),
  profile: "flat",
  attempt_id: `attempt-${index}`,
  state: "previewed",
  designation: "synthetic",
}));
const evidence = {
  original_fields: {
    provider_name: "Alex Example",
    npi: "0000000001",
    address: {
      line1: "10 Example Street",
      suite: "04",
      path: "native_addresses[0]",
    },
  },
  comparison: {
    provider_name: "alex example",
    npi: "0000000001",
    address: {
      line1: "10 example st",
      suite: "04",
      path: "native_addresses[0]",
    },
  },
  field_findings: {},
  comparison_provenance: {},
  locator: { row: 1 },
  address_path: "native_addresses[0]",
};
const savedRun = {
  id: "run-one",
  rule_version: "provider-comparison-v1",
  actor: "Reviewer",
  reason: "Explicit source comparison",
  created_at: "2026-10-30",
  inputs_fresh: true,
  metrics: {
    input_records: 3,
    address_references: 3,
    candidate_count: 3,
    elapsed_seconds: 0.001,
    counts: { clinician: 2, location: 1 },
  },
};
const candidate = {
  id: "candidate-one",
  kind: "clinician",
  left: "left-reference",
  right: "right-reference",
  rank: 140,
  eligible: true,
  rule_version: "provider-comparison-v1",
  agreements: ["npi_equal"],
  contradictions: ["phone_conflict"],
  missing: ["native_id_missing"],
  left_record: evidence,
  right_record: evidence,
};
function setup(
  options: {
    history?: boolean;
    stale?: boolean;
    fail?: string;
    changed?: boolean;
    next?: boolean;
    flatCounts?: boolean;
    triage?: boolean;
    sameSource?: boolean;
    candidateResponse?: (path: string) => Promise<unknown>;
  } = {},
) {
  const calls: { url: string; body?: Record<string, unknown> }[] = [];
  vi.stubGlobal(
    "fetch",
    vi.fn(async (path: string, init?: RequestInit) => {
      const body = init?.body ? JSON.parse(String(init.body)) : undefined;
      calls.push({ url: path, body });
      if (options.fail && path.includes(options.fail))
        return new Response(
          JSON.stringify({
            detail:
              "Selected interpretation is no longer current; inspect the delivery again",
          }),
          { status: 409 },
        );
      if (path.includes("/candidates?") && options.candidateResponse) {
        return new Response(JSON.stringify(await options.candidateResponse(path)));
      }
      const value =
        path === "/api/intakes"
          ? {
              items: receipts.map((receipt, index) => ({
                ...receipt,
                ...(options.changed && index === 0 ? {attempt_id: "new-attempt"} : {}),
                ...(options.sameSource ? {source: "same-source"} : {}),
              })),
            }
          : path.includes("comparison-profile?")
            ? {
                total: 21,
                rule_version: "provider-comparison-v1",
                quality_counts: options.flatCounts
                  ? { "address.suite:null": 1 }
                  : { "address.suite": { null: 1 } },
                items: [evidence],
                next_offset: 20,
              }
            : path.includes("/candidates?")
              ? {
                  items: [candidate],
                  total: options.next ? 21 : 1,
                  next_offset:
                    options.next && path.includes("offset=0") ? 20 : null,
                  inputs_fresh: !options.stale,
                  ...(options.triage ? { reason_counts: { npi_missing: 24, npi_conflict: 7 }, unfiltered_total: 40 } : {}),
                }
              : path === "/api/reconciliation/runs" && body
                ? savedRun
                : path.startsWith("/api/reconciliation/runs?")
                  ? {
                      items:
                        options.history || calls.some((call) => call.body)
                          ? [savedRun]
                          : [],
                      total: options.history ? 1 : 0,
                      next_offset: null,
                    }
                  : { ...savedRun, inputs_fresh: !options.stale };
      return new Response(JSON.stringify(value));
    }),
  );
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  });
  render(
    <QueryClientProvider client={client}>
      <ReconciliationWorkspace />
    </QueryClientProvider>,
  );
  return calls;
}
async function selectSources() {
  fireEvent.click(await screen.findByRole("checkbox", { name: /Clinic/ }));
  fireEvent.click(screen.getByRole("checkbox", { name: /Payer/ }));
}

test("pins source attempts with unknown type by default and creates an explained run only after reviewer/reason", async () => {
  const calls = setup();
  expect(
    screen.getByRole("button", { name: "Create candidate run" }),
  ).toBeDisabled();
  await selectSources();
  await screen.findByText(/21 address references/);
  expect(calls.some((call) => call.body)).toBe(false);
  fireEvent.change(screen.getByLabelText("Entity type for Clinic"), {
    target: { value: "clinician" },
  });
  fireEvent.change(screen.getByLabelText("Run reviewer"), {
    target: { value: "Reviewer" },
  });
  fireEvent.change(screen.getByLabelText("Run reason"), {
    target: { value: "Explicit source comparison" },
  });
  fireEvent.click(screen.getByRole("button", { name: "Create candidate run" }));
  await screen.findByText(/1 clinician candidates in this filter/);
  expect(calls.find((call) => call.body)?.body).toEqual({
    inputs: [
      {
        receipt_id: "receipt-0",
        attempt_id: "attempt-0",
        entity_kind: "clinician",
      },
      {
        receipt_id: "receipt-1",
        attempt_id: "attempt-1",
        entity_kind: "unknown",
      },
    ],
    actor: "Reviewer",
    reason: "Explicit source comparison",
  });
  fireEvent.click(screen.getByText("Alex Example ↔ Alex Example"));
  expect(screen.getByRole("heading", { name: "Agreements" })).toBeVisible();
  expect(screen.getByText("npi equal")).toBeVisible();
  expect(screen.getByText("phone conflict")).toBeVisible();
  expect(screen.getByText("native id missing")).toBeVisible();
  expect(
    screen.queryByRole("button", { name: /Approve|Link identity/ }),
  ).not.toBeInTheDocument();
});

test("source comparison shows literal originals, native address paths and both profile count shapes", async () => {
  setup({ flatCounts: true });
  await selectSources();
  await screen.findByText(/21 address references/);
  expect(screen.getByText(/address.suite: null/)).toBeVisible();
  fireEvent.click(screen.getByText(/Inspect source record 1/));
  const region = screen.getByRole("region", {
    name: "Source record source and comparison values",
  });
  expect(within(region).getByText('"10 Example Street"')).toBeVisible();
  expect(within(region).getByText('"10 example st"')).toBeVisible();
  expect(within(region).getAllByText('"04"')).toHaveLength(2);
  expect(screen.getByText(/Address path native_addresses\[0\]/)).toBeVisible();
  expect(within(region).getAllByText("[absent]").length).toBeGreaterThan(0);
});

test("history restores readable stale candidates and filters/paginates with exact server parameters", async () => {
  const calls = setup({ history: true, stale: true, next: true });
  await screen.findByText(/This run is stale/);
  const filters = screen.getByLabelText("Candidate type");
  fireEvent.change(filters, { target: { value: "location" } });
  fireEvent.change(screen.getByLabelText("Review eligibility"), {
    target: { value: "false" },
  });
  await waitFor(() =>
    expect(
      calls.some((call) =>
        call.url.includes("kind=location&eligible=false&offset=0"),
      ),
    ).toBe(true),
  );
  const pager = await screen.findByLabelText("Candidate pages");
  fireEvent.click(within(pager).getByRole("button", { name: "Next" }));
  await waitFor(() =>
    expect(
      calls.some((call) =>
        call.url.includes("kind=location&eligible=false&offset=20"),
      ),
    ).toBe(true),
  );
  expect(screen.getByText(/Mailing addresses are excluded/)).toBeVisible();
});

test("profile conflict is displayed without creating a run", async () => {
  const calls = setup({ fail: "comparison-profile" });
  await selectSources();
  expect(await screen.findByRole("alert")).toHaveTextContent(
    "Selected interpretation is no longer current",
  );
  expect(calls.some((call) => call.body)).toBe(false);
});

test("empty sources and request failure are actionable", async () => {
  vi.stubGlobal(
    "fetch",
    vi.fn(
      async () =>
        new Response(
          JSON.stringify({ items: [], total: 0, next_offset: null }),
        ),
    ),
  );
  render(
    <QueryClientProvider client={new QueryClient()}>
      <ReconciliationWorkspace />
    </QueryClientProvider>,
  );
  expect(await screen.findByText(/No parsed deliveries yet/)).toBeVisible();
});

test("multiple deliveries from one source still explain how to add another source", async () => {
  const calls = setup({sameSource:true});
  expect(await screen.findByText(/Comparison needs at least two retained interpretations from different sources/)).toBeVisible();
  expect(screen.getByRole('link', {name:'Open Intake'})).toHaveAttribute('href', '?view=intake');
  expect(calls.some(call => call.body)).toBe(false);
});

test("returning from intake refreshes a still-fresh cached source list", async () => {
  history.replaceState(null, "", "/?view=reconciliation");
  let inputs = [receipts[0]];
  let sourceReads = 0;
  vi.stubGlobal('fetch', vi.fn(async (path:string) => {
    if (path === '/api/intakes') { sourceReads += 1; return new Response(JSON.stringify({items:inputs})); }
    return new Response(JSON.stringify({items:[],total:0,next_offset:null}));
  }));
  const client = new QueryClient({defaultOptions:{queries:{retry:false,staleTime:15_000}}});
  const renderWorkspace = () => render(<QueryClientProvider client={client}><ReconciliationWorkspace /></QueryClientProvider>);
  const first = renderWorkspace();
  expect(await screen.findByRole('checkbox', {name:/Clinic/})).toBeVisible();
  first.unmount();
  inputs = [receipts[0], receipts[1]];
  renderWorkspace();
  expect(await screen.findByRole('checkbox', {name:/Payer/}, {timeout:10000})).toBeVisible();
  expect(sourceReads).toBeGreaterThanOrEqual(2);
});

test("a failed source refresh blocks creating a run from stale cached choices", async () => {
  const options: {fail?:string} = {};
  const calls = setup(options);
  await selectSources();
  fireEvent.change(screen.getByLabelText('Run reviewer'), {target:{value:'Reviewer'}});
  fireEvent.change(screen.getByLabelText('Run reason'), {target:{value:'Compare sources'}});
  expect(screen.getByRole('button', {name:'Create candidate run'})).toBeEnabled();
  options.fail = '/api/intakes';
  fireEvent.click(screen.getByRole('button', {name:'Refresh sources and run status'}));
  expect(await screen.findByRole('alert')).toHaveTextContent('Selected interpretation is no longer current');
  expect(screen.getByRole('button', {name:'Create candidate run'})).toBeDisabled();
  expect(calls.some(call => call.body)).toBe(false);
});

test("refresh detects a replaced selected attempt and requires explicit selection of the latest interpretation", async () => {
  const options = { changed: false };
  const calls = setup(options);
  await selectSources();
  await screen.findByText(/21 address references/);
  options.changed = true;
  fireEvent.click(
    screen.getByRole("button", { name: "Refresh sources and run status" }),
  );
  expect(
    await screen.findByText(/A selected source has a newer interpretation/),
  ).toBeVisible();
  expect(
    screen.getByRole("button", { name: "Create candidate run" }),
  ).toBeDisabled();
  fireEvent.click(
    screen.getByRole("button", { name: "Use latest interpretation" }),
  );
  await waitFor(() =>
    expect(
      calls.some((call) => call.url.includes("expected_attempt=new-attempt")),
    ).toBe(true),
  );
  expect(
    screen.queryByText(/A selected source has a newer interpretation/),
  ).not.toBeInTheDocument();
});


test("reason counts describe the full subset, filtering is bookmarked, and changing type clears its reason", async () => {
  const calls = setup({ history: true, triage: true });
  const reason = await screen.findByRole("combobox", { name: "Evidence reason" });
  await screen.findByRole("option", { name: "NPI missing · 24 pairs" });
  fireEvent.change(reason, { target: { value: "npi_missing" } });
  await waitFor(() => expect(calls.some(call => call.url.includes("reason=npi_missing") && call.url.includes("offset=0"))).toBe(true));
  expect(new URLSearchParams(window.location.search).get("evidence_reason")).toBe("npi_missing");
  expect(await screen.findByRole("status", { name: "Evidence reason summary" })).toHaveTextContent("of 40 pairs");
  expect(screen.getByText(/counts are not additive/)).toBeInTheDocument();
  fireEvent.change(screen.getByRole("combobox", { name: "Candidate type" }), { target: { value: "location" } });
  await waitFor(() => expect(screen.getByRole("combobox", { name: "Evidence reason" })).toHaveValue(""));
  expect(new URLSearchParams(window.location.search).get("candidate_kind")).toBe("location");
  expect(calls.some(call => call.body)).toBe(false);
});

test("evidence triage bookmark resumes the same run and filters with reads only", async () => {
  window.history.replaceState(null, "", "/?view=reconciliation&run=run-one&candidate_kind=clinician&eligibility=false&evidence_reason=npi_conflict");
  const calls = setup({ history: true, triage: true });
  await waitFor(() => expect(screen.getByRole("combobox", { name: "Evidence reason" })).toHaveValue("npi_conflict"));
  await waitFor(() => expect(calls.some(call => call.url.includes("eligible=false") && call.url.includes("reason=npi_conflict"))).toBe(true));
  expect(screen.getByRole("combobox", { name: "Review eligibility" })).toHaveValue("false");
  expect(screen.getByLabelText("Saved candidate run")).toHaveValue("run-one");
  expect(calls.some(call => call.body)).toBe(false);
});


test("applies a search across the queue and scopes the download to applied criteria", async () => {
  window.history.replaceState(null, "", "/?view=reconciliation&run=run-one&context=preserve");
  const calls = setup({ history: true, triage: true });
  const input = await screen.findByRole("textbox", { name: "Find a provider or identifier" }, { timeout: 10000 });
  fireEvent.change(input, { target: { value: "  Alex  " } });
  fireEvent.click(screen.getByRole("button", { name: "Search candidates" }));
  await waitFor(() => expect(calls.some(call => call.url.includes("search=Alex"))).toBe(true));
  expect(screen.getByText("Applied search: Alex")).toBeInTheDocument();
  expect(screen.getByRole("link", { name: "Download filtered candidate evidence (JSON)" })).toHaveAttribute("href", expect.stringContaining("search=Alex"));
  expect(new URLSearchParams(window.location.search).get("candidate_search")).toBe("Alex");
  expect(new URLSearchParams(window.location.search).get("context")).toBe("preserve");
  fireEvent.change(input, { target: { value: "Unapplied" } });
  expect(new URLSearchParams(window.location.search).get("candidate_search")).toBe("Alex");
  expect(screen.getByRole("link", { name: "Download filtered candidate evidence (JSON)" })).toHaveAttribute("href", expect.stringContaining("search=Alex"));
  fireEvent.click(screen.getByRole("button", { name: "Clear search" }));
  await waitFor(() => expect(screen.queryByText("Applied search: Alex")).not.toBeInTheDocument());
  expect(new URLSearchParams(window.location.search).has("candidate_search")).toBe(false);
  expect(new URLSearchParams(window.location.search).get("context")).toBe("preserve");
});

test("bookmarked search and navigation restore the applied scope without writes", async () => {
  const first = "/?view=reconciliation&run=run-one&candidate_kind=clinician&eligibility=false&evidence_reason=npi_conflict&candidate_search=Alex&context=preserve";
  history.replaceState(null, "", first);
  const calls = setup({ history: true, triage: true });
  const input = await screen.findByRole("textbox", { name: "Find a provider or identifier" }, { timeout: 10000 });
  expect(input).toHaveValue("Alex");
  await waitFor(() => expect(calls.some(call => call.url.includes("search=Alex") && call.url.includes("reason=npi_conflict"))).toBe(true));
  fireEvent.change(input, { target: { value: "Taylor" } });
  expect(screen.getByRole("link", { name: "Download filtered candidate evidence (JSON)" })).toHaveAttribute("href", expect.stringContaining("search=Alex"));
  fireEvent.click(screen.getByRole("button", { name: "Search candidates" }));
  await waitFor(() => expect(new URLSearchParams(location.search).get("candidate_search")).toBe("Taylor"));
  await act(async () => {
    history.replaceState(null, "", first);
    window.dispatchEvent(new PopStateEvent("popstate"));
  });
  expect(input).toHaveValue("Alex");
  expect(screen.getByRole("combobox", { name: "Evidence reason" })).toHaveValue("npi_conflict");
  expect(screen.getByRole("combobox", { name: "Review eligibility" })).toHaveValue("false");
  expect(screen.getByRole("link", { name: "Download filtered candidate evidence (JSON)" })).toHaveAttribute("href", expect.stringContaining("search=Alex"));
  expect(new URLSearchParams(location.search).get("context")).toBe("preserve");
  expect(calls.some(call => call.body)).toBe(false);
});

test("same-name candidate summaries distinguish source locations and row evidence", async () => {
  history.replaceState(null, "", "/?view=reconciliation&run=run-one");
  const clinic = (site: string, row: number) => ({...evidence, source:'synthetic-clinic',
    locator:`Clinic roster!${row}`, original_fields:{...evidence.original_fields, source_location_id:site}});
  const references = ['NORTH', 'SOUTH'].map((site, index) => ({...candidate, id:`case-${site}`,
    left_record:clinic(site, index + 3), right_record:{...evidence, source:'synthetic-reference'}}));
  const calls = setup({history:true, candidateResponse:async () => ({items:references, total:2, next_offset:null, inputs_fresh:true})});
  const summaries = await screen.findAllByText(/Source location: (NORTH|SOUTH)/, {selector:'summary small'});
  expect(summaries).toHaveLength(2);
  expect(summaries[0]).toHaveTextContent('synthetic-clinic · Source location: NORTH · Row: Clinic roster!3');
  expect(summaries[1]).toHaveTextContent('synthetic-clinic · Source location: SOUTH · Row: Clinic roster!4');
  expect(summaries[0]).toHaveTextContent('synthetic-reference · No source location label');
  expect(summaries[0]).not.toHaveTextContent('Source address: 10 Example Street');
  expect(calls.some(call => call.body)).toBe(false);
});

test("location candidate summaries can show their specific source address and path", async () => {
  history.replaceState(null, "", "/?view=reconciliation&run=run-one&candidate_kind=location");
  setup({history:true, candidateResponse:async () => ({
    items:[{...candidate, kind:'location', left_record:{...evidence, source:'synthetic-reference'}}],
    total:1, next_offset:null, inputs_fresh:true,
  })});
  expect(await screen.findByText(/Source address: 10 Example Street/, {selector:'summary small'})).toHaveTextContent('Address path: native_addresses[0]');
});

test("an old candidate response cannot replace results for the current search", async () => {
  history.replaceState(null, "", "/?view=reconciliation&run=run-one&candidate_search=old");
  let resolveOld!: (value: unknown) => void;
  const old = new Promise<unknown>(resolve => { resolveOld = resolve; });
  const page = (name: string) => ({ items: [{ ...candidate, left_record: { ...evidence, original_fields: { ...evidence.original_fields, provider_name: name } } }], total: 1, next_offset: null, inputs_fresh: true });
  const calls = setup({ history: true, candidateResponse: path => path.includes("search=old") ? old : Promise.resolve(page("Current search result")) });
  await waitFor(() => expect(calls.some(call => call.url.includes("search=old"))).toBe(true), { timeout: 10000 });
  const input = screen.getByRole("textbox", { name: "Find a provider or identifier" });
  fireEvent.change(input, { target: { value: "new" } });
  fireEvent.click(screen.getByRole("button", { name: "Search candidates" }));
  expect(await screen.findByText(/Current search result/, { selector: "summary span" }, { timeout: 10000 })).toBeInTheDocument();
  await act(async () => { resolveOld(page("Stale search result")); await old; });
  expect(screen.getByText(/Current search result/, { selector: "summary span" })).toBeInTheDocument();
  expect(screen.queryByText(/Stale search result/, { selector: "summary span" })).not.toBeInTheDocument();
  expect(calls.some(call => call.body)).toBe(false);
});
