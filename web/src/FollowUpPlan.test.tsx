import {
  act,
  fireEvent,
  render,
  screen,
  waitFor,
  within,
} from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { afterEach, expect, test, vi } from "vitest";
import { FollowUpPlan } from "./FollowUpPlan";

afterEach(() => vi.unstubAllGlobals());
const summary = {
  id: "confirmation-one",
  proposal_id: "proposal-one",
  actor: "Reviewer",
  reason: "Bounded review plan",
  created_at: "2026-10-30",
};
const owned = {
  id: "owned-case",
  owner: "Existing owner",
  status: "in_review",
  version: 3,
  kind: "correction",
  field_name: "phone",
  eligible_for_reuse: true,
  proposal: { number: "2125550199" },
  observed: null,
};
const ack = {
  id: "ack-one",
  actor: "Receiver",
  reason: "Received for manual review",
  created_at: "2026-10-30",
  case_version: 3,
};
function setup(
  options: {
    existing?: boolean;
    ambiguous?: boolean;
    stale?: boolean;
    uncertain?: boolean;
    conflict?: boolean;
    ackUncertain?: boolean;
    ackConflict?: boolean;
    invalidChoice?: boolean;
    delayConfirmation?: Promise<void>;
  } = {},
) {
  const calls: { path: string; body?: Record<string, unknown> }[] = [];
  const pending = vi.fn();
  let saved = Boolean(options.existing);
  let confirmationPosts = 0;
  let ackPosts = 0;
  let acknowledged = false;
  let changedPlan = false;
  let changedCase = false;
  vi.stubGlobal(
    "fetch",
    vi.fn(async (path: string, init?: RequestInit) => {
      const body = init?.body ? JSON.parse(String(init.body)) : undefined;
      calls.push({ path, body });
      if (path === "/api/reconciliation/follow-up-preview") {
        const chosen = (
          body?.case_choices as Record<string, string> | undefined
        )?.["target-owned"];
        if (options.invalidChoice && chosen)
          return new Response(
            JSON.stringify({
              detail: "Case choice no longer belongs to an affected target",
            }),
            { status: 422 },
          );
        const blocked = options.ambiguous && !chosen;
        return new Response(
          JSON.stringify({
            proposal_id: "proposal-one",
            impact_snapshot: changedPlan ? "impact-two" : "impact-one",
            plan_snapshot: changedPlan ? "plan-two" : "plan-one",
            inputs_fresh: !options.stale,
            stale_reasons: options.stale
              ? ["Reviewed source link changed"]
              : [],
            counts: {
              create: 1,
              reuse: blocked ? 0 : 1,
              blocked: blocked ? 1 : 0,
            },
            actions: [
              {
                target_key: "target-new",
                refs: ["new-ref"],
                source: "payer-new",
                network_id: "NET-PINE",
                network_label: "PINE",
                field: "phone",
                action: "create",
                case_id: null,
                case_version: null,
                available_cases: [],
                reason: "No open exact-field case",
              },
              {
                target_key: "target-owned",
                refs: ["owned-ref"],
                source: "payer-owned",
                network_id: "NET-CEDAR",
                network_label: "CEDAR",
                field: "phone",
                action: blocked ? "blocked" : "reuse",
                case_id: blocked ? null : (chosen ?? "owned-case"),
                case_version: 3,
                available_cases: options.ambiguous
                  ? [owned, { ...owned, id: "second-open" }]
                  : [owned],
                reason: blocked
                  ? "Multiple open cases require explicit choice"
                  : "Existing owner/status/proposal preserved",
              },
            ],
            total: 2,
            next_offset: null,
            blocked_count: blocked ? 1 : 0,
          }),
        );
      }
      if (path === "/api/reconciliation/follow-up" && body) {
        confirmationPosts++;
        if (options.conflict && confirmationPosts === 1) {
          changedPlan = true;
          return new Response(
            JSON.stringify({ detail: "Case plan changed; inspect again" }),
            { status: 409 },
          );
        }
        if (options.uncertain && confirmationPosts === 1)
          throw new TypeError("Connection interrupted");
        if (options.delayConfirmation) await options.delayConfirmation;
        saved = true;
        return new Response(JSON.stringify(summary));
      }
      if (path.endsWith("/acknowledge")) {
        ackPosts++;
        if (options.ackConflict && ackPosts === 1) {
          changedCase = true;
          return new Response(
            JSON.stringify({ detail: "Case version changed" }),
            { status: 409 },
          );
        }
        if (options.ackUncertain && ackPosts === 1)
          throw new TypeError("Connection interrupted");
        acknowledged = true;
        return new Response(
          JSON.stringify({ ...ack, case_version: changedCase ? 4 : 3 }),
        );
      }
      if (path.includes("/acknowledgements?"))
        return new Response(
          JSON.stringify({
            items: acknowledged ? [ack] : [],
            total: acknowledged ? 1 : 0,
            next_offset: null,
          }),
        );
      if (path.includes("/export?"))
        return new Response(
          JSON.stringify({ detail: "Saved receipt snapshot changed; refresh" }),
          { status: 409 },
        );
      if (path.startsWith("/api/reconciliation/follow-up?"))
        return new Response(
          JSON.stringify({
            items: saved ? [summary] : [],
            total: saved ? 1 : 0,
            next_offset: null,
          }),
        );
      return new Response(
        JSON.stringify({
          ...summary,
          snapshot: acknowledged ? "receipt-acked" : "receipt-one",
          scope: { clinician_id: "clinician-one", location_id: "north-one" },
          counts: { create: 1, reuse: 1 },
          source_inputs_fresh: !options.stale,
          source_stale_reasons: options.stale
            ? ["Source baseline changed"]
            : [],
          targets: [
            {
              association_id: "association-one",
              target_key: "target-owned",
              refs: ["owned-ref"],
              source: "payer-owned",
              network_id: "NET-CEDAR",
              network_label: "CEDAR",
              field: "phone",
              action: "reuse",
              case: { ...owned, version: changedCase ? 4 : 3 },
              latest_ack: acknowledged ? ack : null,
              ack_count: acknowledged ? 1 : 0,
            },
          ],
          total: 1,
          next_offset: null,
        }),
      );
    }),
  );
  const mounted = render(
    <QueryClientProvider
      client={
        new QueryClient({
          defaultOptions: {
            queries: { retry: false },
            mutations: { retry: false },
          },
        })
      }
    >
      <FollowUpPlan
        proposalId="proposal-one"
        otherBusy={false}
        onPendingChange={pending}
      />
    </QueryClientProvider>,
  );
  return { calls, pending, unmount: mounted.unmount };
}
async function open(preview = true) {
  fireEvent.click(
    screen.getByRole("button", { name: "Review follow-up plan" }),
  );
  if (preview) {
    fireEvent.click(
      await screen.findByRole("button", { name: "Preview follow-up actions" }),
    );
    await screen.findByText(/2 deduplicated follow-up targets/);
  }
}
function fill() {
  fireEvent.change(screen.getByLabelText("Follow-up actor"), {
    target: { value: "Reviewer" },
  });
  fireEvent.change(screen.getByLabelText("Follow-up reason"), {
    target: { value: "Bounded review plan" },
  });
  fireEvent.click(
    screen.getByLabelText("I confirm this bounded review-case plan"),
  );
}
async function openAck() {
  await screen.findByText("Saved follow-up receipt");
  fireEvent.change(screen.getByLabelText("Acknowledgement actor"), {
    target: { value: "Receiver" },
  });
  fireEvent.change(screen.getByLabelText("Acknowledgement reason"), {
    target: { value: "Received for manual review" },
  });
}

test("follow-up planning is lazy and readonly until an attributed explicit confirmation", async () => {
  const { calls } = setup();
  expect(calls).toHaveLength(0);
  await open();
  expect(
    screen.getByRole("button", { name: "Confirm follow-up plan" }),
  ).toBeDisabled();
  expect(calls.filter((call) => call.body).map((call) => call.path)).toEqual([
    "/api/reconciliation/follow-up-preview",
  ]);
  expect(
    screen.getAllByRole("option", { name: "Create a new QA review case" }),
  ).toHaveLength(2);
});

test("confirmation pins plan/impact snapshots and preserves assessed reuse defaults", async () => {
  const { calls, pending } = setup();
  await open();
  fill();
  fireEvent.click(
    screen.getByRole("button", { name: "Confirm follow-up plan" }),
  );
  await screen.findByText("Saved follow-up receipt");
  expect(
    calls.find(
      (call) => call.path === "/api/reconciliation/follow-up" && call.body,
    )?.body,
  ).toEqual({
    proposal_id: "proposal-one",
    expected_snapshot: "impact-one",
    expected_plan: "plan-one",
    case_choices: {},
    request_id: expect.any(String),
    actor: "Reviewer",
    reason: "Bounded review plan",
    confirm: true,
  });
  expect(screen.getByText("Existing owner")).toBeVisible();
  expect(screen.getByText(/in review · Version 3/)).toBeVisible();
  expect(pending).toHaveBeenCalledWith(true);
  expect(pending).toHaveBeenLastCalledWith(false);
});

test("ambiguous open cases block confirmation until explicit existing-case choice; new duplicate is unavailable", async () => {
  const { calls } = setup({ ambiguous: true });
  await open();
  fill();
  expect(
    screen.getByRole("button", { name: "Confirm follow-up plan" }),
  ).toBeDisabled();
  const selector = screen.getByLabelText("Case choice for target-owned");
  expect(
    within(selector).getByRole("option", {
      name: "Create a new QA review case",
    }),
  ).toBeDisabled();
  fireEvent.change(selector, { target: { value: "second-open" } });
  await screen.findByText(/2 deduplicated follow-up targets · 0 blocked/);
  fireEvent.click(
    screen.getByLabelText("I confirm this bounded review-case plan"),
  );
  fireEvent.click(
    screen.getByRole("button", { name: "Confirm follow-up plan" }),
  );
  await screen.findByText("Saved follow-up receipt");
  expect(
    calls.find(
      (call) => call.path === "/api/reconciliation/follow-up" && call.body,
    )?.body?.case_choices,
  ).toEqual({ "target-owned": "second-open" });
});

test("existing immutable confirmation loads its receipt and never offers another confirmation", async () => {
  const { calls } = setup({ existing: true });
  await open(false);
  await screen.findByText("Saved follow-up receipt");
  const caseLink = new URL(screen.getByRole("link", { name: "Open work case" }).getAttribute("href")!, window.location.origin);
  expect(caseLink.searchParams.get("view")).toBe("work");
  expect(caseLink.searchParams.get("case")).toBe("owned-case");
  expect(caseLink.searchParams.get("followup")).toBe(summary.id);
  expect(
    screen.getByText(/already exists for this immutable proposal/),
  ).toBeVisible();
  expect(
    screen.queryByRole("button", { name: "Confirm follow-up plan" }),
  ).not.toBeInTheDocument();
  expect(
    calls.some((call) => call.path === "/api/reconciliation/follow-up-preview"),
  ).toBe(false);
});

test("uncertain confirmation retry keeps UUID/payload identical and locks attribution", async () => {
  const { calls } = setup({ uncertain: true });
  await open();
  fill();
  fireEvent.click(
    screen.getByRole("button", { name: "Confirm follow-up plan" }),
  );
  await screen.findByText(/Confirmation outcome is unconfirmed/);
  expect(screen.getByLabelText("Follow-up actor")).toBeDisabled();
  fireEvent.click(
    screen.getByRole("button", { name: "Retry same follow-up confirmation" }),
  );
  await screen.findByText("Saved follow-up receipt");
  const bodies = calls
    .filter(
      (call) => call.path === "/api/reconciliation/follow-up" && call.body,
    )
    .map((call) => call.body);
  expect(bodies[1]).toEqual(bodies[0]);
});

test("409 requires renewed plan snapshots and explicit reconfirmation", async () => {
  const { calls } = setup({ conflict: true });
  await open();
  fill();
  fireEvent.click(
    screen.getByRole("button", { name: "Confirm follow-up plan" }),
  );
  await screen.findByText(/impact or work-case plan changed/);
  expect(
    screen.getByRole("button", { name: "Confirm follow-up plan" }),
  ).toBeDisabled();
  fireEvent.click(
    screen.getByRole("button", { name: "Preview follow-up actions" }),
  );
  await screen.findByText("plan-two");
  fireEvent.click(
    screen.getByLabelText("I confirm this bounded review-case plan"),
  );
  fireEvent.click(
    screen.getByRole("button", { name: "Confirm follow-up plan" }),
  );
  await screen.findByText("Saved follow-up receipt");
  const bodies = calls
    .filter(
      (call) => call.path === "/api/reconciliation/follow-up" && call.body,
    )
    .map((call) => call.body!);
  expect(bodies[1].expected_plan).toBe("plan-two");
  expect(bodies[1].expected_snapshot).toBe("impact-two");
  expect(bodies[1].request_id).not.toBe(bodies[0].request_id);
});

test("acknowledgement pins association, prior ack and current case version without work-state mutation", async () => {
  const { calls } = setup({ existing: true });
  await open(false);
  await openAck();
  fireEvent.click(
    screen.getByRole("button", { name: "Record acknowledgement" }),
  );
  await screen.findByText(
    "Receipt acknowledgement saved. Verification and case state were not changed.",
  );
  expect(
    calls.find((call) => call.path.endsWith("/acknowledge"))?.body,
  ).toEqual({
    association_id: "association-one",
    expected_ack_id: null,
    expected_case_version: 3,
    request_id: expect.any(String),
    actor: "Receiver",
    reason: "Received for manual review",
  });
  expect(calls.some((call) => call.path.includes("/events"))).toBe(false);
  expect(screen.getByText(/in review · Version 3/)).toBeVisible();
});

test("acknowledgement uncertainty retries exactly and conflict requires current case context", async () => {
  const { calls } = setup({ existing: true, ackUncertain: true });
  await open(false);
  await openAck();
  fireEvent.click(
    screen.getByRole("button", { name: "Record acknowledgement" }),
  );
  await screen.findByText(/Acknowledgement outcome is unconfirmed/);
  expect(screen.getByLabelText("Acknowledgement actor")).toBeDisabled();
  fireEvent.click(
    screen.getByRole("button", { name: "Retry same acknowledgement" }),
  );
  await screen.findByText(/Receipt acknowledgement saved/);
  const bodies = calls
    .filter((call) => call.path.endsWith("/acknowledge"))
    .map((call) => call.body);
  expect(bodies[1]).toEqual(bodies[0]);
});

test("saved receipt source staleness remains separate from acknowledgement and export state", async () => {
  const { calls } = setup({ existing: true, stale: true });
  await open(false);
  await screen.findByText(
    "Source dependencies have changed since confirmation.",
  );
  await openAck();
  expect(
    screen.getByRole("button", { name: "Record acknowledgement" }),
  ).toBeEnabled();
  fireEvent.click(
    screen.getByRole("button", { name: "Download follow-up JSON" }),
  );
  await screen.findByText("Saved receipt snapshot changed; refresh");
  expect(
    calls.some(
      (call) =>
        call.path ===
        "/api/reconciliation/follow-up/confirmation-one/export?expected_snapshot=receipt-one&format=json",
    ),
  ).toBe(true);
});

test("acknowledgement conflict requires receipt refresh and the new case version", async () => {
  const { calls } = setup({ existing: true, ackConflict: true });
  await open(false);
  await openAck();
  fireEvent.click(
    screen.getByRole("button", { name: "Record acknowledgement" }),
  );
  await screen.findByText(/Acknowledgement or case state changed/);
  expect(
    screen.getByRole("button", { name: "Record acknowledgement" }),
  ).toBeDisabled();
  fireEvent.click(
    screen.getByRole("button", { name: "Refresh acknowledgement context" }),
  );
  await screen.findByText(/in review · Version 4/);
  fireEvent.click(
    screen.getByRole("button", { name: "Record acknowledgement" }),
  );
  await screen.findByText(/Receipt acknowledgement saved/);
  const bodies = calls
    .filter((call) => call.path.endsWith("/acknowledge"))
    .map((call) => call.body!);
  expect(bodies[1].expected_case_version).toBe(4);
  expect(bodies[1].request_id).not.toBe(bodies[0].request_id);
});

test("a no-longer-valid case choice can be reset without trapping the read-only plan", async () => {
  const { calls } = setup({ ambiguous: true, invalidChoice: true });
  await open();
  fireEvent.change(screen.getByLabelText("Case choice for target-owned"), {
    target: { value: "second-open" },
  });
  await screen.findByText(
    "Case choice no longer belongs to an affected target",
  );
  fireEvent.click(
    screen.getByRole("button", { name: "Reset case choices and preview" }),
  );
  expect(
    await screen.findByLabelText("Case choice for target-owned"),
  ).toHaveValue("");
  expect(
    calls.some(
      (call) => call.path === "/api/reconciliation/follow-up" && call.body,
    ),
  ).toBe(false);
});


test("saved receipt cannot leak from a warmed cache into another proposal scope", async () => {
  window.history.replaceState(null, "", "/?view=reconciliation&followup=saved-receipt");
  const saved = { ...summary, id: "saved-receipt", proposal_id: "proposal-a", snapshot: "receipt-snapshot", scope: {}, counts: { create: 0, reuse: 0 }, source_inputs_fresh: true, source_stale_reasons: [], targets: [], total: 0, next_offset: null };
  const requests: string[] = [];
  vi.stubGlobal("fetch", vi.fn(async (url: string, init?: RequestInit) => {
    requests.push(init?.method ?? "GET");
    return new Response(JSON.stringify(url.includes("/saved-receipt?") ? saved : { items: [{ ...summary, id: saved.id }], total: 1, next_offset: null }));
  }));
  const client = new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } });
  const view = (proposalId: string) => <QueryClientProvider client={client}><FollowUpPlan proposalId={proposalId} otherBusy={false} onPendingChange={() => {}} /></QueryClientProvider>;
  const mounted = render(view("proposal-a"));
  await screen.findByText("Saved follow-up receipt", { exact: true });
  mounted.rerender(view("proposal-b"));
  await screen.findByText("This follow-up receipt belongs to another change proposal. Select a receipt for this proposal.");
  expect(screen.queryByText("Saved follow-up receipt", { exact: true })).not.toBeInTheDocument();
  expect(screen.queryByRole("button", { name: "Download follow-up JSON" })).not.toBeInTheDocument();
  expect(requests.every(method => method === "GET")).toBe(true);
  mounted.unmount(); client.clear();
});


test("a confirmation finishing after leaving the workspace cannot change the new URL", async () => {
  let complete!: () => void;
  const delay = new Promise<void>(resolve => { complete = resolve; });
  const { calls, unmount } = setup({ delayConfirmation: delay });
  await open(); fill();
  fireEvent.click(screen.getByRole("button", { name: "Confirm follow-up plan" }));
  await waitFor(() => expect(calls.some(call => call.path === "/api/reconciliation/follow-up" && call.body)).toBe(true));
  unmount();
  window.history.pushState(null, "", "/?view=work&case=another-case");
  await act(async () => { complete(); await delay; await new Promise(resolve => setTimeout(resolve, 0)); });
  expect(window.location.search).toBe("?view=work&case=another-case");
});
