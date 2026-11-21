import { useState } from "react";
import {
  fireEvent,
  render,
  screen,
  waitFor,
  within,
} from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { afterEach, expect, test, vi } from "vitest";
import { ChangeImpact } from "./ChangeImpact";

afterEach(() => vi.unstubAllGlobals());
const inputs = [
  {
    id: "payer-receipt",
    attempt_id: "payer-attempt",
    label: "payer.json",
    source: "payer",
    profile: "flat",
    state: "preview_ready",
    designation: "synthetic",
  },
  {
    id: "unlinked-receipt",
    attempt_id: "unlinked-attempt",
    label: "unlinked.json",
    source: "unlinked",
    profile: "flat",
    state: "preview_ready",
    designation: "synthetic",
  },
];
const proposal = {
  id: "proposal-one",
  field: "phone",
  proposed_value: { number: "2125550111", extension: "004" },
  proposed_original: { number: "212-555-0111", extension: "004" },
  prior_evidence: { field_decision: "prior-phone" },
  inputs: [
    {
      receipt_id: "payer-receipt",
      attempt_id: "payer-attempt",
      entity_kind: "unknown",
    },
  ],
  actor: "Reviewer",
  reason: "Reviewed NORTH phone proposal",
  created_at: "2026-10-30",
};
function impact(stale = false, offset = 0, moreWork = false) {
  return {
    proposal_id: "proposal-one",
    snapshot: "impact-snapshot",
    inputs_fresh: !stale,
    stale_reasons: stale ? ["Reviewed location link changed"] : [],
    counts: {
      affected: 1,
      unaffected_within_assessed_scope: 1,
      not_assessed: 1,
    },
    work_counts: {
      affected: 0,
      unaffected_within_assessed_scope: 0,
      not_assessed: 0,
    },
    targets: offset
      ? []
      : [
          {
            ref: "north-ref",
            source: "payer",
            network_id: "NET-CEDAR",
            network_label: "CEDAR",
            classification: "affected",
            reason: "Reviewed NORTH clinician/location dependency",
            value: { number: "2125550101", extension: null },
            comparison_value: { number: "2125550101", extension: null },
            receipt_id: "payer-receipt",
            attempt_id: "payer-attempt",
            locator: "$[0]",
            address_path: "native_addresses[0]",
          },
          {
            ref: "south-ref",
            source: "payer",
            network_id: "NET-PINE",
            network_label: "PINE",
            classification: "unaffected_within_assessed_scope",
            reason: "SOUTH location is independent",
            value: { number: "2125550102", extension: null },
            comparison_value: { number: "2125550102", extension: null },
            receipt_id: "payer-receipt",
            attempt_id: "payer-attempt",
            locator: "$[1]",
            address_path: "native_addresses[0]",
          },
          {
            ref: "unlinked-ref",
            source: "unlinked",
            classification: "not_assessed",
            reason: "No reviewed clinician/location links",
            value: null,
            comparison_value: null,
            receipt_id: "unlinked-receipt",
            attempt_id: "unlinked-attempt",
            locator: "$[0]",
            address_path: "",
          },
        ],
    total: 3,
    next_offset: null,
    existing_work: [],
    work_total: moreWork ? 21 : 0,
    work_next_offset: moreWork && offset === 0 ? 20 : null,
    scope_notice:
      "Coverage is bounded to explicitly selected source inputs; unknown dependencies remain not assessed.",
  };
}
function setup(
  options: {
    unreviewed?: boolean;
    conflict?: boolean;
    uncertain?: boolean;
    previewStale?: boolean;
    moreWork?: boolean;
    changedSource?: boolean;
  } = {},
) {
  const calls: { path: string; body?: Record<string, unknown> }[] = [];
  let posts = 0;
  let updateSnapshot = (_value: string) => {};
  const refresh = vi.fn(async () => {
    updateSnapshot("r4-refreshed");
  });
  const pending = vi.fn();
  vi.stubGlobal(
    "fetch",
    vi.fn(async (path: string, init?: RequestInit) => {
      const body = init?.body ? JSON.parse(String(init.body)) : undefined;
      calls.push({ path, body });
      if (path.startsWith("/api/intakes?"))
        return new Response(
          JSON.stringify({
            items: inputs.map((item) =>
              options.changedSource && item.id === "payer-receipt"
                ? { ...item, attempt_id: "new-payer-attempt" }
                : item,
            ),
            total: 2,
            next_offset: null,
          }),
        );
      if (path === "/api/reconciliation/impact-preview")
        return new Response(
          JSON.stringify(
            impact(
              options.previewStale,
              Number(body?.work_offset ?? 0),
              options.moreWork,
            ),
          ),
        );
      if (body) {
        posts++;
        if (options.conflict && posts === 1)
          return new Response(
            JSON.stringify({ detail: "Field snapshot changed; refresh" }),
            { status: 409 },
          );
        if (options.uncertain && posts === 1)
          throw new TypeError("Connection interrupted");
        return new Response(
          JSON.stringify({
            ...proposal,
            field: body.field,
            proposed_value: body.proposed_value,
          }),
        );
      }
      if (path.startsWith("/api/reconciliation/change-proposals?"))
        return new Response(
          JSON.stringify({ items: [proposal], total: 1, next_offset: null }),
        );
      return new Response(JSON.stringify(proposal));
    }),
  );
  function Harness() {
    const [snapshot, setSnapshot] = useState("r4-snapshot");
    updateSnapshot = setSnapshot;
    return (
      <ChangeImpact
        clinicianId="clinician-one"
        locationId="north-one"
        snapshot={snapshot}
        inputsFresh
        fields={[
          {
            field: "phone",
            decision: options.unreviewed
              ? null
              : {
                  id: "prior-phone",
                  decision: "select",
                  value: { number: "2125550101", extension: null },
                },
          },
          {
            field: "address",
            decision: {
              id: "prior-address",
              decision: "conflict",
              value: null,
            },
          },
        ]}
        otherBusy={false}
        onPendingChange={pending}
        onRefresh={refresh}
      />
    );
  }
  render(
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
      <Harness />
    </QueryClientProvider>,
  );
  return { calls, refresh, pending };
}
async function open() {
  fireEvent.click(
    screen.getByRole("button", { name: "Open change impact preview" }),
  );
  await screen.findByLabelText("Assess delivery payer.json");
}
function fill() {
  fireEvent.change(screen.getByLabelText("Proposed field"), {
    target: { value: "phone" },
  });
  fireEvent.change(screen.getByLabelText("Proposed phone number"), {
    target: { value: "2125550111" },
  });
  fireEvent.change(screen.getByLabelText("Proposed phone extension"), {
    target: { value: "004" },
  });
  fireEvent.click(screen.getByLabelText("Assess delivery payer.json"));
  fireEvent.change(screen.getByLabelText("Proposal actor"), {
    target: { value: "Reviewer" },
  });
  fireEvent.change(screen.getByLabelText("Proposal reason"), {
    target: { value: "Reviewed NORTH phone proposal" },
  });
  fireEvent.click(
    screen.getByLabelText("I reviewed the prior field and assessment inputs"),
  );
}

test("impact opens lazily and creates nothing without explicit field/input review", async () => {
  const { calls } = setup();
  expect(calls).toHaveLength(0);
  await open();
  expect(
    screen.getByRole("button", { name: "Save change proposal" }),
  ).toBeDisabled();
  expect(screen.getByLabelText("Saved change proposal")).toHaveValue("");
  expect(calls.some((call) => call.body)).toBe(false);
  expect(
    screen.queryByRole("button", { name: /Create cases|Confirm follow/ }),
  ).not.toBeInTheDocument();
});

test("typed phone proposal pins exact R4 snapshot and retained inputs without automatically previewing", async () => {
  const { calls, pending } = setup();
  await open();
  fill();
  fireEvent.click(screen.getByRole("button", { name: "Save change proposal" }));
  await screen.findByText(
    "Change proposal saved. Run the read-only impact preview separately.",
  );
  expect(calls.find((call) => call.body)?.body).toEqual({
    clinician_id: "clinician-one",
    location_id: "north-one",
    field: "phone",
    proposed_value: { number: "2125550111", extension: "004" },
    inputs: [
      {
        receipt_id: "payer-receipt",
        attempt_id: "payer-attempt",
        entity_kind: "unknown",
      },
    ],
    expected_snapshot: "r4-snapshot",
    request_id: expect.any(String),
    actor: "Reviewer",
    reason: "Reviewed NORTH phone proposal",
  });
  expect(
    calls.some((call) => call.path === "/api/reconciliation/impact-preview"),
  ).toBe(false);
  expect(pending).toHaveBeenCalledWith(true);
  expect(pending).toHaveBeenLastCalledWith(false);
});

test("proposal requires a current explicit field decision", async () => {
  setup({ unreviewed: true });
  await open();
  fill();
  expect(
    screen.getByText(
      /Record a current source selection or retained-conflict decision/,
    ),
  ).toBeVisible();
  expect(
    screen.getByRole("button", { name: "Save change proposal" }),
  ).toBeDisabled();
});

test("typed coherent address keeps suite and blank optional lines explicit", async () => {
  const { calls } = setup();
  await open();
  fill();
  fireEvent.change(screen.getByLabelText("Proposed field"), {
    target: { value: "address" },
  });
  for (const [name, value] of Object.entries({
    line1: "10 Example Street",
    suite: "04",
    city: "Boston",
    state: "MA",
    zip: "02108",
  }))
    fireEvent.change(screen.getByLabelText(`Proposed address ${name}`), {
      target: { value },
    });
  fireEvent.click(
    screen.getByLabelText("I reviewed the prior field and assessment inputs"),
  );
  fireEvent.click(screen.getByRole("button", { name: "Save change proposal" }));
  await screen.findByText(/Change proposal saved/);
  expect(calls.find((call) => call.body)?.body?.proposed_value).toEqual({
    line1: "10 Example Street",
    line2: null,
    suite: "04",
    city: "Boston",
    state: "MA",
    zip: "02108",
  });
});

test("read-only preview keeps NORTH, SOUTH and unlinked coverage distinct and exposes network attribution", async () => {
  const { calls } = setup();
  await open();
  fireEvent.change(screen.getByLabelText("Saved change proposal"), {
    target: { value: "proposal-one" },
  });
  await screen.findByRole("button", { name: "Run read-only impact preview" });
  expect(
    calls.some((call) => call.path === "/api/reconciliation/impact-preview"),
  ).toBe(false);
  fireEvent.click(
    screen.getByRole("button", { name: "Run read-only impact preview" }),
  );
  await screen.findByRole("region", { name: "Impact assessment results" });
  expect(screen.getByText("SOUTH location is independent")).toBeVisible();
  expect(
    screen.getByText("No reviewed clinician/location links"),
  ).toBeVisible();
  expect(screen.getByText("Network CEDAR · NET-CEDAR")).toBeVisible();
  expect(
    screen.getByRole("region", { name: "Listing coverage" }),
  ).toHaveTextContent("1 affected");
  expect(calls.filter((call) => call.body).map((call) => call.path)).toEqual([
    "/api/reconciliation/impact-preview",
  ]);
});

test("uncertain proposal retries identical payload and keeps form edits locked", async () => {
  const { calls } = setup({ uncertain: true });
  await open();
  fill();
  fireEvent.click(screen.getByRole("button", { name: "Save change proposal" }));
  await screen.findByText(/proposal result is unconfirmed/);
  expect(screen.getByLabelText("Proposal actor")).toBeDisabled();
  fireEvent.click(
    screen.getByRole("button", { name: "Retry same change proposal" }),
  );
  await screen.findByText(/Change proposal saved/);
  const payloads = calls.filter((call) => call.body).map((call) => call.body);
  expect(payloads[1]).toEqual(payloads[0]);
});

test("409 retains proposal text but requires renewed snapshot/evidence before save", async () => {
  const { calls, refresh } = setup({ conflict: true });
  await open();
  fill();
  fireEvent.click(screen.getByRole("button", { name: "Save change proposal" }));
  await screen.findByText(/field snapshot or assessment inputs changed/);
  expect(screen.getByLabelText("Proposed phone number")).toHaveValue(
    "2125550111",
  );
  expect(
    screen.getByRole("button", { name: "Save change proposal" }),
  ).toBeDisabled();
  fireEvent.click(
    screen.getByRole("button", { name: "Refresh proposal evidence" }),
  );
  await waitFor(() => expect(refresh).toHaveBeenCalledOnce());
  fireEvent.click(
    screen.getByLabelText("I reviewed the prior field and assessment inputs"),
  );
  fireEvent.click(screen.getByRole("button", { name: "Save change proposal" }));
  await screen.findByText(/Change proposal saved/);
  const payloads = calls.filter((call) => call.body).map((call) => call.body!);
  expect(payloads[1].expected_snapshot).toBe("r4-refreshed");
  expect(payloads[1].request_id).not.toBe(payloads[0].request_id);
});

test("stale previews retain evidence and work-only overflow still paginates read-only", async () => {
  const { calls } = setup({ previewStale: true, moreWork: true });
  await open();
  fireEvent.change(screen.getByLabelText("Saved change proposal"), {
    target: { value: "proposal-one" },
  });
  fireEvent.click(
    await screen.findByRole("button", { name: "Run read-only impact preview" }),
  );
  await screen.findByText("This proposal preview is stale.");
  expect(screen.getByText("Reviewed location link changed")).toBeVisible();
  const pages = screen.getByRole("group", {
    name: "Impact existing work pages",
  });
  fireEvent.click(within(pages).getByRole("button", { name: "Next" }));
  await waitFor(() =>
    expect(
      calls.some(
        (call) =>
          call.path === "/api/reconciliation/impact-preview" &&
          call.body?.work_offset === 20,
      ),
    ).toBe(true),
  );
});
