import { act, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { afterEach, expect, test, vi } from "vitest";
import { ManagedFeeds } from "./ManagedFeeds";
import { navigateWorkspace } from "./workspaceNavigation";

afterEach(() => vi.unstubAllGlobals());
const recipe = { id: "recipe-1", name: "Reviewed synthetic clinic", source: "synthetic-clinic", scope: "weekly-clinic", definition: { mapping: { npi: "npi", phone: "phone", location_id: "location_id" } } };
const contract = { id: "contract-1", state: "approved", definition: { recipe_revision_id: "recipe-1", required_headers: ["npi", "phone", "location_id"], row_change_fraction: 0.2 } };
const feed = { id: "feed-1", name: "Synthetic clinic weekly", source: recipe.source, scope: recipe.scope, revision: 2, config: { inbox: "/synthetic/inbox", owner: "Clinic coordinator", enabled: true, contract_id: "contract-1" }, contracts: [contract], jobs: [{ id: "job-1", kind: "source_delivery", state: "succeeded", execution_count: 1 }, { id: "job-derived", kind: "derived_field_candidate", state: "succeeded", execution_count: 0 }], versions: [{ id: "candidate-2", state: "candidate", period: "2026-11-02", delivery_id: "delivery-2", created_at: "2026-11-02T09:00:00Z" }], windows: [] };
function api(options: { hard?: boolean; stale?: boolean; corrections?: boolean; derived?: boolean } = {}) {
  const calls: { url: string; body?: Record<string, unknown> }[] = [];
  let acknowledged = false;
  let approved = false;
  let reportHash = "report-2";
  let conflict = options.stale ?? false;
  vi.stubGlobal("fetch", vi.fn(async (input: string, init?: RequestInit) => {
    const url = String(input);
    const body = init?.body ? JSON.parse(String(init.body)) : undefined;
    calls.push({ url, body });
    if (url.endsWith("/decide") && conflict) {
      conflict = false; reportHash = "report-3";
      return new Response(JSON.stringify({ detail: "Approved baseline changed; reload before approval" }), { status: 409 });
    }
    if (url.endsWith("/exceptions")) acknowledged = body.disposition === "acknowledged";
    if (url.endsWith("/decide")) approved = true;
    const version = { id: "candidate-2", kind: options.derived ? "derived_field_candidate" : "source_delivery", report_notice: options.derived ? "Inherited report" : undefined, state: approved ? "approved" : "candidate", report_hash: reportHash, current_version: "approved-1", report: { counts: { raw: 3, valid: 2, quarantined: 1, unique: 3 }, effective_corrections: options.corrections ? { baseline_version: "corrected-base", fields: ["phone", "phone_extension"], notice: "Incoming data may differ from reviewed corrections.", total: 73, counts: {changed: 2, unchanged: 70, missing: 1, blocked_invalid: 0, unresolved: 0}, entry_count: 73, entries: [{key: ["001", "NORTH"], status: "changed", old: {phone: "6175550199", phone_extension: "0042"}, new: {phone: "6175550101", phone_extension: null}, previous_locator: "row:2", current_locator: "row:3", decision_id: "decision-1"}] } : null, comparison: { baseline_version: "approved-1", missing: 1 }, findings: options.hard ? [{ code: "headers", severity: "hard", message: "Required phone header is missing" }] : [{ code: "quarantine", severity: "hold", message: "One source row is quarantined" }] }, review: acknowledged ? [{ code: "quarantine", disposition: "acknowledged", actor: "Reviewer", reason: "Reviewed invalid row" }] : [], rows: [{ original: { zip: "02108" } }], delivery: { id: "delivery-2" }, manifest: { receipt_id: "receipt-1", attempt_id: "attempt-1", source_delivery: { period: "2026-11-02" }, designation: "synthetic", notice: "Synthetic source assertions, not independently verified provider truth." } };
    if (url.includes('/correction-comparison?')) {
      const params = new URL(url, 'http://localhost').searchParams;
      const entry = version.report.effective_corrections!.entries[0];
      const selected = params.get('status');
      return new Response(JSON.stringify({entries: selected === 'missing' ? [] : [entry], total: selected === 'missing' ? 0 : 73, next_offset: selected === 'all' ? 20 : null}));
    }
    const value = url === "/api/feeds" ? (body ? feed : { items: [feed] })
      : url === "/api/feeds/recipes" ? { items: [recipe] }
      : url === "/api/feeds/feed-1/current" ? { version_id: approved ? "candidate-2" : "approved-1", stale: true, notice: "A newer delivery is awaiting review" }
      : url === "/api/feeds/feed-1" ? feed
      : url === "/api/feed-versions/candidate-2" ? version
      : { id: "saved" };
    return new Response(JSON.stringify(value));
  }));
  return calls;
}
async function openCandidate() {
  fireEvent.click(await screen.findByRole("button", { name: /Synthetic clinic weekly/ }));
  fireEvent.change(await screen.findByLabelText("Reviewer"), { target: { value: "Reviewer" } });
  fireEvent.change(screen.getByLabelText("Decision reason"), { target: { value: "Reviewed invalid row" } });
  fireEvent.click(await screen.findByRole("button", { name: /candidate · 2026-11-02/ }));
  await screen.findByRole("heading", { name: "Dataset review · candidate" });
}

test("registry failure is not reported as an empty registry and can be retried", async () => {
  let unavailable = true;
  vi.stubGlobal("fetch", vi.fn(async (input: string) => {
    if (String(input) === '/api/feeds' && unavailable) {
      return new Response(JSON.stringify({detail:'Source registry unavailable'}), {status:503});
    }
    return new Response(JSON.stringify({items:[]}));
  }));
  render(<ManagedFeeds />);
  expect(await screen.findByRole('alert')).toHaveTextContent('Source registry unavailable');
  expect(screen.queryByText(/No managed feeds yet/)).not.toBeInTheDocument();
  unavailable = false;
  fireEvent.click(screen.getByRole('button', {name:'Reload evidence'}));
  await waitFor(() => expect(screen.queryByRole('alert')).not.toBeInTheDocument());
  expect(await screen.findByText(/No managed feeds yet/)).toBeVisible();
});

test("held candidate leaves prior approved version available and requires separate risk acknowledgement and dataset approval", async () => {
  const calls = api();
  render(<ManagedFeeds />);
  await openCandidate();
  expect(screen.getByRole("link", { name: "Download current approved JSON" })).toHaveAttribute("href", "/api/feed-versions/approved-1/export");
  expect(screen.getByRole("link", { name: "Download complete quality report JSON" })).toHaveAttribute("href", "/api/feed-versions/candidate-2/quality-report");
  expect(screen.getByText(/It is review evidence, not an approved dataset export/)).toBeVisible();
  expect(screen.getByRole("button", { name: "Approve dataset version" })).toBeDisabled();
  expect(calls.filter(call => call.body)).toHaveLength(0);
  expect(screen.getByText(/Period: 2026-11-02/)).toBeVisible();
  expect(screen.getByText("Evidence designation: synthetic")).toBeVisible();
  expect(screen.getByText("Synthetic source assertions, not independently verified provider truth.")).toBeVisible();
  fireEvent.click(screen.getByRole("button", { name: "Acknowledge quarantine" }));
  await waitFor(() => expect(screen.getByRole("button", { name: "Approve dataset version" })).toBeEnabled());
  expect(calls.some(call => call.url.endsWith("/decide"))).toBe(false);
  fireEvent.click(screen.getByRole("button", { name: "Approve dataset version" }));
  await screen.findByRole("heading", { name: "Dataset review · approved" });
  const decision = calls.find(call => call.url.endsWith("/decide"))!;
  expect(decision.body).toMatchObject({ decision: "approved", expected_report: "report-2", expected_current: "approved-1", actor: "Reviewer", reason: "Reviewed invalid row" });
  expect(decision.body?.idempotency_key).toEqual(expect.any(String));
  expect(screen.getByRole("link", { name: "Download this approved version JSON" })).toHaveAttribute("href", "/api/feed-versions/candidate-2/export");
});

test("hard contract failure cannot be acknowledged or approved", async () => {
  api({ hard: true });
  render(<ManagedFeeds />);
  await openCandidate();
  expect(screen.getByText("Required phone header is missing")).toBeInTheDocument();
  expect(screen.queryByRole("button", { name: /Acknowledge/ })).not.toBeInTheDocument();
  expect(screen.getByRole("button", { name: "Approve dataset version" })).toBeDisabled();
  expect(screen.getByRole("button", { name: "Reject candidate" })).toBeEnabled();
});

test("stale approval reports a conflict and reload refreshes the pinned report before a new decision", async () => {
  const calls = api({ stale: true });
  render(<ManagedFeeds />);
  await openCandidate();
  fireEvent.click(screen.getByRole("button", { name: "Acknowledge quarantine" }));
  await waitFor(() => expect(screen.getByRole("button", { name: "Approve dataset version" })).toBeEnabled());
  fireEvent.click(screen.getByRole("button", { name: "Approve dataset version" }));
  expect(await screen.findByRole("alert")).toHaveTextContent("Approved baseline changed; reload before approval");
  expect(screen.getByRole("heading", { name: "Dataset review · candidate" })).toBeInTheDocument();
  fireEvent.click(screen.getByRole("button", { name: "Reload evidence" }));
  await waitFor(() => expect(screen.queryByRole("alert")).not.toBeInTheDocument());
  await waitFor(() => expect(screen.getByRole("button", { name: "Approve dataset version" })).toBeEnabled());
  fireEvent.click(screen.getByRole("button", { name: "Approve dataset version" }));
  await screen.findByRole("heading", { name: "Dataset review · approved" });
  expect(calls.filter(call => call.url.endsWith("/decide")).map(call => call.body?.expected_report)).toEqual(["report-2", "report-3"]);
});

test("registration is disabled without reviewer and reason and preserves the chosen recipe's source scope", async () => {
  const calls = api();
  render(<ManagedFeeds />);
  await screen.findByRole("button", { name: /Synthetic clinic weekly/ });
  fireEvent.click(screen.getByText("Register a clinic CSV feed"));
  const form = screen.getByRole("button", { name: "Register disabled feed" }).closest("form")!;
  expect(within(form).getByRole("button", { name: "Register disabled feed" })).toBeDisabled();
  fireEvent.change(screen.getByLabelText("Feed name"), { target: { value: "New clinic" } });
  fireEvent.change(screen.getByLabelText("Approved source recipe"), { target: { value: "recipe-1" } });
  fireEvent.change(screen.getByLabelText("Local inbox directory"), { target: { value: "/synthetic/new-inbox" } });
  fireEvent.change(screen.getByLabelText("Feed owner"), { target: { value: "Coordinator" } });
  fireEvent.change(await screen.findByLabelText("Reviewer"), { target: { value: "Reviewer" } });
  fireEvent.change(screen.getByLabelText("Decision reason"), { target: { value: "Register reviewed scope" } });
  fireEvent.submit(form);
  await waitFor(() => expect(calls.find(call => call.url === "/api/feeds" && call.body)?.body).toMatchObject({ name: "New clinic", source: "synthetic-clinic", scope: "weekly-clinic", inbox: "/synthetic/new-inbox", owner: "Coordinator", actor: "Reviewer", reason: "Register reviewed scope" }));
  await screen.findByText("Feed registered and disabled. Propose and approve its contract before enabling deliveries.");
  expect(calls.some(call => call.url.endsWith("/approve") || call.url.endsWith("/configure") || call.url.endsWith("/decide"))).toBe(false);
});


test("deep-linked delivery opens its detail and returning to the list restores focus", async () => {
  api();
  window.history.replaceState({}, "", "?view=feeds&feed=feed-1&version=candidate-2");
  const mounted = render(<ManagedFeeds />);
  const detail = await screen.findByRole("region", { name: "Dataset review · candidate" });
  await waitFor(() => expect(detail).toHaveFocus());
  expect(detail.closest(".mf-workbench")).toHaveAttribute("data-detail-open", "true");
  fireEvent.click(screen.getByRole("button", { name: /Back to deliveries/ }));
  const selection = screen.getByRole("complementary", { name: "Delivery selection" });
  await waitFor(() => expect(selection).toHaveFocus());
  expect(selection.closest(".mf-workbench")).toHaveAttribute("data-detail-open", "false");
  fireEvent.click(screen.getByRole("button", { name: /candidate · 2026-11-02/ }));
  await waitFor(() => expect(detail).toHaveFocus());
  fireEvent.click(screen.getByRole("button", { name: /Back to deliveries/ }));
  act(() => navigateWorkspace("feeds", { feed: "feed-1" }));
  act(() => navigateWorkspace("feeds", { feed: "feed-1", version: "candidate-2" }));
  const reopened = await screen.findByRole("region", { name: "Dataset review · candidate" });
  await waitFor(() => expect(reopened).toHaveFocus());
  expect(reopened.closest(".mf-workbench")).toHaveAttribute("data-detail-open", "true");
  mounted.unmount();
  act(() => window.history.replaceState({}, "", "/"));
});


test("returning to deliveries does not steal focus from the operator's next control", async () => {
  api();
  const frames: FrameRequestCallback[] = [];
  vi.stubGlobal("requestAnimationFrame", (callback: FrameRequestCallback) => { frames.push(callback); return frames.length; });
  window.history.replaceState({}, "", "?view=feeds&feed=feed-1&version=candidate-2");
  render(<ManagedFeeds />);
  const detail = await screen.findByRole("region", { name: "Dataset review · candidate" });
  await waitFor(() => expect(detail).toHaveFocus());
  const back = screen.getByRole("button", { name: /Back to deliveries/ });
  back.focus();
  fireEvent.click(back);
  const next = screen.getByRole("button", { name: /candidate · 2026-11-02/ });
  next.focus();
  act(() => { for (const frame of frames.splice(0)) frame(16); });
  expect(next).toHaveFocus();
  fireEvent.click(next);
  await waitFor(() => expect(detail).toHaveFocus());
});


test("derived candidate jobs are labeled and cannot be reprocessed", async () => {
  api();
  render(<ManagedFeeds />);
  fireEvent.click(await screen.findByRole("button", { name: /Synthetic clinic weekly/ }));
  fireEvent.click(await screen.findByText("Processing and delivery history"));
  fireEvent.click(screen.getByText(/Processing history and delivery windows/));
  const derived = screen.getByText("Reviewed phone candidate · succeeded").closest("li")!;
  expect(within(derived).queryByRole("button", { name: /Reprocess/ })).not.toBeInTheDocument();
  const source = screen.getByText("Source delivery · succeeded").closest("li")!;
  expect(within(source).getByRole("button", { name: /Reprocess/ })).toBeInTheDocument();
});


test("incoming source separately compares the corrected roster with complete counts and a bounded sample", async () => {
  api({ corrections: true });
  render(<ManagedFeeds />);
  await openCandidate();
  const panel = screen.getByRole("region", { name: "Effective corrected roster comparison" });
  expect(panel).toHaveTextContent("corrected-base");
  await waitFor(() => expect(panel).toHaveTextContent("Showing 1–1 of 73 matching entries"));
  expect(panel).toHaveTextContent("Corrected keys assessed73");
  expect(panel).toHaveTextContent("Changed2");
  expect(panel).toHaveTextContent("6175550199 · extension: 0042");
  expect(panel).toHaveTextContent("6175550101 · extension: Not supplied");
  expect(panel).toHaveTextContent("Missing or unresolved keys do not establish closure");
  fireEvent.change(within(panel).getByLabelText("Filter correction comparisons"), {target: {value: "missing"}});
  await waitFor(() => expect(panel).toHaveTextContent("Showing 0–0 of 0 matching entries"));
  expect(screen.getByText("Source-to-source comparison:")).toBeInTheDocument();
});


test("derived approved handoff identifies reconciliation as original source evidence", async () => {
  api({ derived: true });
  render(<ManagedFeeds />);
  await openCandidate();
  fireEvent.click(screen.getByRole("button", { name: "Acknowledge quarantine" }));
  await waitFor(() => expect(screen.getByRole("button", { name: "Approve dataset version" })).toBeEnabled());
  fireEvent.click(screen.getByRole("button", { name: "Approve dataset version" }));
  await screen.findByRole("heading", { name: "Dataset review · approved" });
  expect(screen.getByText(/Reconciliation uses the retained original source interpretation/)).toBeInTheDocument();
  expect(screen.getByRole("link", { name: "Inspect original source evidence" })).toBeInTheDocument();
  expect(screen.getByRole("link", { name: "Prepare reconciliation from original source evidence" })).toHaveAttribute("href", expect.stringContaining("receipt=receipt-1"));
  expect(screen.queryByRole("link", { name: "Prepare reconciliation from this approved version" })).not.toBeInTheDocument();
});

test("attribution waits for selected evidence instead of accepting edits in a loading placeholder", async () => {
  api();
  const original = globalThis.fetch;
  let finish: (value: Response) => void = () => {};
  let requested = false;
  vi.stubGlobal("fetch", vi.fn(async (input: string, init?: RequestInit) => {
    if (String(input) === "/api/feed-versions/candidate-2") {
      requested = true;
      return new Promise<Response>(resolve => { finish = resolve; });
    }
    return original(input, init);
  }));
  window.history.replaceState({}, "", "/?view=feeds&feed=feed-1&version=candidate-2");
  render(<ManagedFeeds />);
  await waitFor(() => expect(requested).toBe(true));
  expect(screen.getByRole("heading", { name: "Loading selected evidence…" })).toBeVisible();
  expect(screen.queryByLabelText("Reviewer")).not.toBeInTheDocument();
  await act(async () => { finish(await original("/api/feed-versions/candidate-2")); });
  await screen.findByRole("heading", { name: "Dataset review · candidate" });
  fireEvent.change(await screen.findByLabelText("Reviewer"), { target: { value: "Reviewer" } });
  fireEvent.change(screen.getByLabelText("Decision reason"), { target: { value: "Reviewed ready evidence" } });
  expect(screen.getByRole("button", { name: "Acknowledge quarantine" })).toBeEnabled();
});
