import { act, cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { afterEach, expect, test, vi } from "vitest";
import { ManagedFeeds } from "./ManagedFeeds";
import { ReconciliationWorkspace } from "./ReconciliationWorkspace";
import { navigateWorkspace, workspaceHref } from "./workspaceNavigation";

const clients: QueryClient[] = [];
afterEach(() => {
  cleanup();
  clients.splice(0).forEach(client => client.clear());
  vi.unstubAllGlobals();
  window.history.replaceState(null, "", "/");
});

function response(value: unknown, status = 200) {
  return new Response(JSON.stringify(value), { status });
}

function version(id = "approved-1", feedId = "feed-1", state = "approved") {
  return {
    id, feed_id: feedId, state, report_hash: `report-${id}`,
    report: { counts: { raw: 2, valid: 2, quarantined: 0 }, comparison: {}, findings: [] },
    review: [], rows: [], current_version: "approved-1", delivery: { id: `delivery-${id}` },
    manifest: { feed_id: feedId, receipt_id: `receipt-${id}`, attempt_id: `attempt-${id}` },
  };
}

function feed(id = "feed-1", versions = [version(), version("candidate-2", id, "candidate")]) {
  return {
    id, name: `Synthetic ${id}`, source: `synthetic-${id}`, scope: "weekly",
    revision: 1, config: { inbox: "/synthetic/inbox", owner: "Synthetic operator", enabled: true, contract_id: null },
    contracts: [], jobs: [], windows: [],
    versions: versions.map(item => ({ id: item.id, state: item.state, delivery_id: `delivery-${item.id}`, period: "2026-10-26", created_at: "2026-10-26" })),
  };
}

type Call = { url: string; method: string };
function mockFeeds(options: {
  feeds?: ReturnType<typeof feed>[];
  versions?: ReturnType<typeof version>[];
  delayed?: { id: string; result: Promise<Response> };
  delayedPost?: { url: string; result: Promise<Response> };
  recipes?: { id: string; name: string; source: string; scope: string; definition: { mapping: Record<string, string> } }[];
} = {}) {
  const feeds = options.feeds ?? [feed()];
  const versions = options.versions ?? [version(), version("candidate-2", "feed-1", "candidate")];
  const calls: Call[] = [];
  vi.stubGlobal("fetch", vi.fn(async (input: string, init?: RequestInit) => {
    const url = String(input);
    calls.push({ url, method: init?.method ?? "GET" });
    if (options.delayedPost && init?.method === "POST" && url === options.delayedPost.url) return options.delayedPost.result;
    if (url === "/api/feeds") return response({ items: feeds });
    if (url === "/api/feeds/recipes") return response({ items: options.recipes ?? [] });
    const selectedFeed = feeds.find(item => url === `/api/feeds/${item.id}`);
    if (selectedFeed) return response(selectedFeed);
    const currentFeed = feeds.find(item => url === `/api/feeds/${item.id}/current`);
    if (currentFeed) return response({ version_id: currentFeed.versions[0].id, stale: true, notice: "A later delivery awaits review" });
    if (options.delayed && url === `/api/feed-versions/${options.delayed.id}`) return options.delayed.result;
    const selectedVersion = versions.find(item => url === `/api/feed-versions/${item.id}`);
    if (selectedVersion) return response(selectedVersion);
    return response({ detail: "Unknown retained selection" }, 404);
  }));
  return calls;
}

test("feed/version bookmark resumes the exact approved version while a newer candidate remains separate", async () => {
  window.history.replaceState(null, "", workspaceHref("feeds", { feed: "feed-1", version: "approved-1" }));
  const calls = mockFeeds();
  render(<ManagedFeeds />);
  await screen.findByRole("heading", { name: "Dataset review · approved" });
  expect(screen.getByRole("button", { name: /approved · 2026-10-26/ })).toHaveAttribute("aria-pressed", "true");
  expect(screen.getByRole("button", { name: /candidate · 2026-10-26/ })).toHaveAttribute("aria-pressed", "false");
  expect(screen.getByRole("link", { name: "Inspect this version's retained evidence" })).toHaveAttribute(
    "href", workspaceHref("intake", { receipt: "receipt-approved-1", attempt: "attempt-approved-1" }),
  );
  expect(screen.getByRole("link", { name: "Prepare reconciliation from this approved version" })).toHaveAttribute(
    "href", workspaceHref("reconciliation", { feed: "feed-1", version: "approved-1", receipt: "receipt-approved-1", attempt: "attempt-approved-1" }),
  );
  expect(calls.some(call => call.url === "/api/feed-versions/candidate-2")).toBe(false);
  expect(calls.every(call => call.method === "GET")).toBe(true);
});

test("candidate bookmark permits evidence inspection without offering approved reconciliation", async () => {
  window.history.replaceState(null, "", workspaceHref("feeds", { feed: "feed-1", version: "candidate-2" }));
  const calls = mockFeeds();
  render(<ManagedFeeds />);
  await screen.findByRole("heading", { name: "Dataset review · candidate" });
  expect(screen.queryByRole("link", { name: "Prepare reconciliation from this approved version" })).not.toBeInTheDocument();
  expect(screen.getByRole("link", { name: "Inspect this version's retained evidence" })).toHaveAttribute(
    "href", workspaceHref("intake", { receipt: "receipt-candidate-2", attempt: "attempt-candidate-2" }),
  );
  expect(screen.getByRole("link", { name: "Download current approved JSON" })).toHaveAttribute("href", "/api/feed-versions/approved-1/export");
  expect(calls.every(call => call.method === "GET")).toBe(true);
});

test("version from another feed is rejected without opening an unrelated current version", async () => {
  window.history.replaceState(null, "", workspaceHref("feeds", { feed: "feed-1", version: "foreign-version" }));
  const calls = mockFeeds();
  render(<ManagedFeeds />);
  expect(await screen.findByRole("alert")).toHaveTextContent("This version does not belong to the selected feed");
  expect(screen.queryByRole("heading", { name: /Dataset review/ })).not.toBeInTheDocument();
  expect(calls.some(call => call.url.startsWith("/api/feed-versions/"))).toBe(false);
});

test("version details cannot claim a different feed even when the feed summary listed the ID", async () => {
  window.history.replaceState(null, "", workspaceHref("feeds", { feed: "feed-1", version: "approved-1" }));
  mockFeeds({ versions: [version("approved-1", "another-feed")] });
  render(<ManagedFeeds />);
  expect(await screen.findByRole("alert")).toHaveTextContent("Dataset version has incompatible feed context");
  expect(screen.queryByRole("link", { name: "Prepare reconciliation from this approved version" })).not.toBeInTheDocument();
});

test("a delayed prior version response cannot overwrite the newly selected feed/version", async () => {
  let finishOld!: (result: Response) => void;
  const delayed = new Promise<Response>(resolve => { finishOld = resolve; });
  const nextVersion = version("next-candidate", "feed-2", "candidate");
  window.history.replaceState(null, "", workspaceHref("feeds", { feed: "feed-1", version: "approved-1" }));
  const calls = mockFeeds({ feeds: [feed(), feed("feed-2", [nextVersion])], versions: [nextVersion], delayed: { id: "approved-1", result: delayed } });
  render(<ManagedFeeds />);
  await waitFor(() => expect(calls.some(call => call.url === "/api/feed-versions/approved-1")).toBe(true));
  act(() => navigateWorkspace("feeds", { feed: "feed-2", version: "next-candidate" }));
  await screen.findByRole("heading", { name: "Dataset review · candidate" });
  await act(async () => { finishOld(response(version())); await delayed; });
  expect(screen.getByRole("heading", { name: "Synthetic feed-2" })).toBeInTheDocument();
  expect(screen.getByRole("heading", { name: "Dataset review · candidate" })).toBeInTheDocument();
  expect(screen.queryByRole("heading", { name: "Dataset review · approved" })).not.toBeInTheDocument();
  expect(screen.getByRole("link", { name: "Inspect this version's retained evidence" })).toHaveAttribute(
    "href", workspaceHref("intake", { receipt: "receipt-next-candidate", attempt: "attempt-next-candidate" }),
  );
});

test("a completed action for a prior feed cannot replace the newly selected feed or its notice", async () => {
  let finishAction!: (result: Response) => void;
  const delayedAction = new Promise<Response>(resolve => { finishAction = resolve; });
  const nextVersion = version("next-approved", "feed-2");
  window.history.replaceState(null, "", workspaceHref("feeds", { feed: "feed-1" }));
  const calls = mockFeeds({
    feeds: [feed(), feed("feed-2", [nextVersion])],
    versions: [version(), nextVersion],
    delayedPost: { url: "/api/feeds/feed-1/configure", result: delayedAction },
  });
  render(<ManagedFeeds />);
  await screen.findByRole("heading", { name: "Synthetic feed-1" });
  fireEvent.change(screen.getByLabelText("Reviewer"), { target: { value: "Synthetic reviewer" } });
  fireEvent.change(screen.getByLabelText("Decision reason"), { target: { value: "Pause this feed only" } });
  fireEvent.click(screen.getByRole("button", { name: "Disable new deliveries" }));
  await waitFor(() => expect(calls.some(call => call.url === "/api/feeds/feed-1/configure" && call.method === "POST")).toBe(true));
  act(() => navigateWorkspace("feeds", { feed: "feed-2", version: "next-approved" }));
  await screen.findByRole("heading", { name: "Synthetic feed-2" });
  await screen.findByRole("heading", { name: "Dataset review · approved" });
  await act(async () => { finishAction(response({ ...feed(), config: { ...feed().config, enabled: false } })); await delayedAction; });
  expect(new URLSearchParams(window.location.search).get("feed")).toBe("feed-2");
  expect(new URLSearchParams(window.location.search).get("version")).toBe("next-approved");
  expect(screen.getByRole("heading", { name: "Synthetic feed-2" })).toBeInTheDocument();
  expect(screen.queryByRole("heading", { name: "Synthetic feed-1" })).not.toBeInTheDocument();
  expect(screen.queryByText("Feed disabled for new deliveries. Retained jobs and evidence remain available.")).not.toBeInTheDocument();
  expect(screen.getByRole("link", { name: "Inspect this version's retained evidence" })).toHaveAttribute(
    "href", workspaceHref("intake", { receipt: "receipt-next-approved", attempt: "attempt-next-approved" }),
  );
  expect(calls.filter(call => call.url === "/api/feeds/feed-1")).toHaveLength(1);
});

test("late feed registration after unmount cannot redirect an operator in the Work queue", async () => {
  let finishRegistration!: (result: Response) => void;
  const pendingRegistration = new Promise<Response>(resolve => { finishRegistration = resolve; });
  window.history.replaceState(null, "", workspaceHref("feeds"));
  const calls = mockFeeds({
    recipes: [{ id: "recipe-1", name: "Synthetic approved recipe", source: "synthetic-clinic", scope: "weekly", definition: { mapping: { phone: "phone" } } }],
    delayedPost: { url: "/api/feeds", result: pendingRegistration },
  });
  const mounted = render(<ManagedFeeds />);
  await screen.findByRole("button", { name: /Synthetic feed-1/ });
  fireEvent.click(screen.getByText("Register a clinic CSV feed"));
  fireEvent.change(screen.getByLabelText("Feed name"), { target: { value: "New synthetic feed" } });
  fireEvent.change(screen.getByLabelText("Approved source recipe"), { target: { value: "recipe-1" } });
  fireEvent.change(screen.getByLabelText("Local inbox directory"), { target: { value: "/synthetic/registration-inbox" } });
  fireEvent.change(screen.getByLabelText("Feed owner"), { target: { value: "Synthetic coordinator" } });
  fireEvent.change(screen.getByLabelText("Reviewer"), { target: { value: "Synthetic reviewer" } });
  fireEvent.change(screen.getByLabelText("Decision reason"), { target: { value: "Register reviewed source" } });
  fireEvent.submit(screen.getByRole("button", { name: "Register disabled feed" }).closest("form")!);
  await waitFor(() => expect(calls.some(call => call.url === "/api/feeds" && call.method === "POST")).toBe(true));
  act(() => { mounted.unmount(); navigateWorkspace("work", { case: "retained-case" }); });
  await act(async () => { finishRegistration(response(feed("newly-registered"))); await pendingRegistration; });
  expect(window.location.search).toBe(workspaceHref("work", { case: "retained-case" }));
  expect(calls.some(call => call.url === "/api/feeds/newly-registered")).toBe(false);
});

const seed = { feed: "feed-1", version: "approved-1", receipt: "receipt-approved-1", attempt: "attempt-approved-1" };
const clinic = { id: seed.receipt, label: "Synthetic clinic delivery", source: "synthetic-clinic", profile: "flat", state: "committed", designation: "synthetic", attempt_id: seed.attempt };
const payer = { id: "payer-receipt", label: "Synthetic payer delivery", source: "synthetic-payer", profile: "flat", state: "committed", designation: "synthetic", attempt_id: "payer-attempt" };

function mockReconciliation(options: { state?: string; pinnedMissing?: boolean; newerAttempt?: boolean; unrelatedRun?: boolean } = {}) {
  const calls: Call[] = [];
  vi.stubGlobal("fetch", vi.fn(async (input: string, init?: RequestInit) => {
    const url = String(input);
    calls.push({ url, method: init?.method ?? "GET" });
    if (url === "/api/feed-versions/approved-1") return response(version("approved-1", "feed-1", options.state ?? "approved"));
    if (url === "/api/intakes") return response({ items: [options.newerAttempt ? { ...clinic, attempt_id: "newer-unapproved-attempt", state: "preview_ready" } : clinic, payer] });
    if (url.startsWith("/api/reconciliation/runs?")) return response({ items: [], total: 0, next_offset: null });
    if (options.unrelatedRun && url === "/api/reconciliation/runs/unrelated") {
      return response({ id: "unrelated", inputs: [{ receipt_id: payer.id, attempt_id: payer.attempt_id, entity_kind: "unknown" }],
        rule_version: "synthetic-rule", actor: "Synthetic reviewer", reason: "An unrelated comparison", created_at: "2026-10-26",
        inputs_fresh: true, metrics: { input_records: 1, address_references: 1, candidate_count: 1, elapsed_seconds: 0.001, counts: { clinician: 1, location: 0 } } });
    }
    if (options.unrelatedRun && url.startsWith("/api/reconciliation/runs/unrelated/candidates?")) {
      return response({ items: [], total: 0, next_offset: null, inputs_fresh: true });
    }
    if (url.includes("/comparison-profile?")) return response({ total: 0, rule_version: "synthetic-rule", quality_counts: {}, items: [], next_offset: null });
    if (url === `/api/intakes/${seed.receipt}?attempt_id=${seed.attempt}`) {
      return options.pinnedMissing ? response({ detail: "Interpretation attempt does not belong to this receipt" }, 404) : response({ ...clinic, latest_attempt_id: options.newerAttempt ? "newer-unapproved-attempt" : seed.attempt, is_current_attempt: !options.newerAttempt, attempts: [], observations: [] });
    }
    return response({ detail: "Unknown retained selection" }, 404);
  }));
  const client = new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } });
  clients.push(client);
  render(<QueryClientProvider client={client}><ReconciliationWorkspace /></QueryClientProvider>);
  return calls;
}

test("approved reconciliation link validates exact evidence before preselecting and creates no run on mount", async () => {
  window.history.replaceState(null, "", workspaceHref("reconciliation", seed));
  const calls = mockReconciliation();
  const context = await screen.findByRole("complementary", { name: "Approved delivery context" });
  expect(await within(context).findByText(/approved clinic interpretation stays pinned/)).toBeInTheDocument();
  await waitFor(() => expect(screen.getByRole("checkbox", { name: /Synthetic clinic delivery/ })).toBeChecked());
  expect(screen.getByRole("checkbox", { name: /Synthetic payer delivery/ })).not.toBeChecked();
  expect(screen.getByRole("button", { name: "Create candidate run" })).toBeDisabled();
  expect(calls.some(call => call.url === `/api/intakes/${seed.receipt}?attempt_id=${seed.attempt}`)).toBe(true);
  expect(calls.every(call => call.method === "GET")).toBe(true);
});

test("an approved seed remains pinned when its receipt has a newer unapproved interpretation", async () => {
  window.history.replaceState(null, "", workspaceHref("reconciliation", seed));
  const calls = mockReconciliation({ newerAttempt: true });
  await waitFor(() => expect(screen.getByRole("checkbox", { name: /Synthetic clinic delivery/ })).toBeChecked());
  const quality = screen.getByRole("heading", { name: "2. Inspect comparison quality" }).closest("section")!;
  expect(within(quality).getByText(seed.attempt)).toBeInTheDocument();
  expect(screen.queryByRole("button", { name: "Use latest interpretation" })).not.toBeInTheDocument();
  fireEvent.click(screen.getByRole("checkbox", { name: /Synthetic payer delivery/ }));
  fireEvent.change(screen.getByLabelText("Run reviewer"), { target: { value: "Synthetic reviewer" } });
  fireEvent.change(screen.getByLabelText("Run reason"), { target: { value: "Review exact approved evidence" } });
  expect(screen.getByRole("button", { name: "Create candidate run" })).toBeDisabled();
  expect(within(quality).getByText(seed.attempt)).toBeInTheDocument();
  expect(calls.some(call => call.url.includes(`expected_attempt=${seed.attempt}`))).toBe(true);
  expect(calls.some(call => call.url.includes("expected_attempt=newer-unapproved-attempt"))).toBe(false);
  expect(calls.every(call => call.method === "GET")).toBe(true);
});

test("an unrelated saved run cannot be opened under an approved delivery context", async () => {
  window.history.replaceState(null, "", workspaceHref("reconciliation", { ...seed, run: "unrelated" }));
  const calls = mockReconciliation({ unrelatedRun: true });
  expect(await screen.findByRole("alert")).toHaveTextContent(/approved.*(delivery|interpretation)|incompatible/i);
  expect(calls.some(call => call.url === "/api/reconciliation/runs/unrelated")).toBe(true);
  expect(calls.some(call => call.url.startsWith("/api/reconciliation/runs/unrelated/candidates?"))).toBe(false);
  expect(screen.queryByText("An unrelated comparison")).not.toBeInTheDocument();
  expect(calls.every(call => call.method === "GET")).toBe(true);
});

test.each(["feed", "receipt", "attempt"] as const)("forged reconciliation %s selection cannot seed an approved interpretation", async key => {
  window.history.replaceState(null, "", workspaceHref("reconciliation", { ...seed, [key]: "forged" }));
  const calls = mockReconciliation();
  expect(await screen.findByRole("alert")).toHaveTextContent("does not identify an approved version and its exact source interpretation");
  expect(screen.getByRole("checkbox", { name: /Synthetic clinic delivery/ })).not.toBeChecked();
  expect(calls.some(call => call.url.includes("?attempt_id="))).toBe(false);
  expect(calls.every(call => call.method === "GET")).toBe(true);
});

test("an unapproved dataset cannot seed reconciliation even with matching receipt and attempt IDs", async () => {
  window.history.replaceState(null, "", workspaceHref("reconciliation", seed));
  const calls = mockReconciliation({ state: "candidate" });
  expect(await screen.findByRole("alert")).toHaveTextContent("does not identify an approved version");
  expect(screen.getByRole("checkbox", { name: /Synthetic clinic delivery/ })).not.toBeChecked();
  expect(calls.some(call => call.url.includes("?attempt_id="))).toBe(false);
});

test("a missing pinned interpretation reports its error instead of selecting the receipt's latest evidence", async () => {
  window.history.replaceState(null, "", workspaceHref("reconciliation", seed));
  const calls = mockReconciliation({ pinnedMissing: true });
  expect(await screen.findByRole("alert")).toHaveTextContent("Interpretation attempt does not belong to this receipt");
  expect(screen.getByRole("checkbox", { name: /Synthetic clinic delivery/ })).not.toBeChecked();
  expect(calls.every(call => call.method === "GET")).toBe(true);
});

test("navigating from a valid approved seed to a forged seed clears the previous source selection", async () => {
  window.history.replaceState(null, "", workspaceHref("reconciliation", seed));
  const calls = mockReconciliation();
  await waitFor(() => expect(screen.getByRole("checkbox", { name: /Synthetic clinic delivery/ })).toBeChecked());
  act(() => navigateWorkspace("reconciliation", { ...seed, attempt: "forged" }));
  expect(await screen.findByRole("alert")).toHaveTextContent("does not identify an approved version");
  expect(screen.getByRole("checkbox", { name: /Synthetic clinic delivery/ })).not.toBeChecked();
  expect(calls.every(call => call.method === "GET")).toBe(true);
});
