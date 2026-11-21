import {
  fireEvent,
  render,
  screen,
  waitFor,
  within,
} from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { afterEach, expect, test, vi } from "vitest";
import { FieldReconciliation } from "./FieldReconciliation";

afterEach(() => vi.unstubAllGlobals());
function field(name: string) {
  const values =
    name === "phone"
      ? [
          { number: "2125550101", extension: "004" },
          { number: "2125550199", extension: "004" },
          { number: "2125550101", extension: null },
        ]
      : name === "address"
        ? [
            {
              line1: "10 Example Street",
              line2: null,
              suite: "04",
              city: "Boston",
              state: "MA",
              zip: "02108",
            },
            {
              line1: "10 Example St",
              line2: "STE 04",
              suite: "04",
              city: "Boston",
              state: "MA",
              zip: "02108",
            },
            {
              line1: "10 Example Street",
              line2: null,
              suite: "04",
              city: "Boston",
              state: "MA",
              zip: "02108",
            },
          ]
        : ["Alex Example", "Alex EXAMPLE", "Alex Example"];
  return {
    field: name,
    option_count: 3,
    options: ["clinic", "payer", "reference"].map((source, index) => ({
      ref: `${source}-ref`,
      source,
      value: values[index],
      comparison_value: values[index],
      selectable: true,
      findings: [],
      link_ids: [`${source}-reviewed-link`],
    })),
    decision: null,
    history: [],
  };
}
function view(location: boolean, overrides = {}) {
  return {
    scope: {
      clinician_id: "clinician-one",
      location_id: location ? "location-one" : null,
    },
    clinician: { id: "clinician-one", label: "Alex reviewed" },
    location: location ? { id: "location-one", label: "North office" } : null,
    snapshot: "field-snapshot-one",
    inputs_fresh: true,
    source_count: 3,
    total: 3,
    next_offset: null,
    records: [
      {
        ref: "clinic-ref",
        source: "clinic",
        original_fields: { provider_name: "Alex Example" },
      },
    ],
    fields: location
      ? [field("phone"), field("address")]
      : [field("provider_name"), field("npi")],
    notice: "Approved assertions remain independent source evidence.",
    ...overrides,
  };
}
const priorDecision = {
  id: "previous-field-decision",
  decision: "select",
  selected_ref: "clinic-ref",
  value: { number: "2125550101", extension: "004" },
  snapshot: "old-field-snapshot",
  actor: "Earlier reviewer",
  reason: "Prior office selection",
  created_at: "2026-10-30",
  stale: true,
};
function setup(
  options: {
    conflict?: boolean;
    uncertain?: boolean;
    stale?: boolean;
    prior?: boolean;
    paged?: boolean;
    exportConflict?: boolean;
    scopeProblem?: boolean;
  } = {},
) {
  const calls: { path: string; body?: Record<string, unknown> }[] = [];
  let posts = 0;
  let newer = false;
  vi.stubGlobal(
    "fetch",
    vi.fn(async (path: string, init?: RequestInit) => {
      const body = init?.body ? JSON.parse(String(init.body)) : undefined;
      calls.push({ path, body });
      if (path.includes("/targets/"))
        return new Response(
          JSON.stringify({
            items: path.includes("/location?")
              ? [{ id: "location-one", label: "North office" }]
              : [{ id: "clinician-one", label: "Alex reviewed" }],
            total: 1,
            next_offset: null,
          }),
        );
      if (path.includes("/export?"))
        return new Response(
          JSON.stringify({
            detail: "Export snapshot changed; refresh field evidence",
          }),
          { status: 409 },
        );
      if (body) {
        posts++;
        if (options.conflict && posts === 1) {
          newer = true;
          return new Response(
            JSON.stringify({ detail: "Field snapshot changed; inspect again" }),
            { status: 409 },
          );
        }
        if (options.uncertain && posts === 1)
          throw new TypeError("Connection interrupted");
        return new Response(JSON.stringify({ id: "saved", ...body }));
      }
      const location = path.includes("location_id=location-one");
      const data = view(location, {
        inputs_fresh: !options.stale && !options.scopeProblem,
        ...(options.paged
          ? { total: 21, next_offset: path.includes("offset=20") ? null : 20 }
          : {}),
        ...(newer ? { snapshot: "field-snapshot-two" } : {}),
      });
      if (location && (options.prior || newer))
        data.fields[0] = {
          ...data.fields[0],
          decision: {
            ...priorDecision,
            id: newer ? "intervening-decision" : priorDecision.id,
          } as never,
          history: [priorDecision] as never,
        };
      if (options.scopeProblem) {
        Object.assign(data, {
          scope_problems: [
            "Conflicting clinician type declarations across linked source runs",
          ],
        });
        data.fields.forEach((field) =>
          field.options.forEach((option) =>
            Object.assign(option, {
              selectable: false,
              network_label: "CEDAR",
              network_id: "NET-CEDAR",
            }),
          ),
        );
      }
      return new Response(JSON.stringify(data));
    }),
  );
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  });
  render(
    <QueryClientProvider client={client}>
      <FieldReconciliation />
    </QueryClientProvider>,
  );
  return calls;
}
async function open(location = false) {
  fireEvent.click(
    screen.getByRole("button", { name: "Open reconciled field evidence" }),
  );
  await screen.findByText("1 reviewed clinician targets in this search.");
  fireEvent.change(screen.getByLabelText("Reviewed clinician"), {
    target: { value: "clinician-one" },
  });
  await screen.findByRole("region", { name: "provider name reconciliation" });
  if (location) {
    fireEvent.click(
      screen.getByLabelText("Include a reviewed practice location"),
    );
    await screen.findByText(
      "1 reviewed practice location targets in this search.",
    );
    fireEvent.change(screen.getByLabelText("Reviewed practice location"), {
      target: { value: "location-one" },
    });
    await screen.findByRole("region", { name: "phone reconciliation" });
  }
}
function fill(name: string, decision: string) {
  fireEvent.change(screen.getByLabelText(`Decision for ${name}`), {
    target: { value: decision },
  });
  fireEvent.change(screen.getByLabelText(`Actor for ${name}`), {
    target: { value: "Reviewer" },
  });
  fireEvent.change(screen.getByLabelText(`Reason for ${name}`), {
    target: { value: "Reviewed pinned source attribution" },
  });
  fireEvent.click(screen.getByLabelText(`I reviewed ${name} source evidence`));
}

test("field evidence is lazy and has explicit clinician/location scope with no preferred source default", async () => {
  const calls = setup();
  expect(calls).toHaveLength(0);
  await open();
  expect(
    screen.getByRole("region", { name: "provider name reconciliation" }),
  ).toBeVisible();
  expect(
    screen.queryByRole("region", { name: "phone reconciliation" }),
  ).not.toBeInTheDocument();
  expect(screen.getByLabelText("Decision for provider name")).toHaveValue("");
  expect(
    screen
      .getAllByRole("radio")
      .every((input) => !(input as HTMLInputElement).checked),
  ).toBe(true);
  expect(calls.some((call) => call.body)).toBe(false);
});

test("selecting a location phone pins its exact source reference and decision snapshot without assembling values", async () => {
  const calls = setup();
  await open(true);
  fill("phone", "select");
  expect(
    screen.getByRole("button", { name: "Save phone decision" }),
  ).toBeDisabled();
  fireEvent.click(
    screen.getByRole("radio", { name: "Choose phone from payer payer-ref" }),
  );
  fireEvent.click(screen.getByRole("button", { name: "Save phone decision" }));
  await screen.findByText(
    "Selected phone source assertion saved. Source observations were preserved.",
  );
  expect(calls.find((call) => call.body)?.body).toEqual({
    clinician_id: "clinician-one",
    location_id: "location-one",
    field: "phone",
    decision: "select",
    selected_ref: "payer-ref",
    expected_snapshot: "field-snapshot-one",
    expected_decision: null,
    request_id: expect.any(String),
    actor: "Reviewer",
    reason: "Reviewed pinned source attribution",
  });
  const address = screen.getByRole("region", {
    name: "address reconciliation",
  });
  expect(
    within(address).getByText(/individual components are never assembled/),
  ).toBeVisible();
});

test("a retained conflict omits preferred source and preserves visible stale decision history", async () => {
  const calls = setup({ prior: true });
  await open(true);
  expect(screen.getByText(/Stale decision/)).toBeVisible();
  fill("phone", "conflict");
  fireEvent.click(screen.getByRole("button", { name: "Save phone decision" }));
  await screen.findByText(
    "Explicit phone conflict saved. Source observations were preserved.",
  );
  const payload = calls.find((call) => call.body)?.body;
  expect(payload?.decision).toBe("conflict");
  expect(payload?.expected_decision).toBe("previous-field-decision");
  expect(payload).not.toHaveProperty("selected_ref");
});

test("409 retains the draft but requires refresh and reviewed evidence against new snapshot/prior decision", async () => {
  const calls = setup({ conflict: true });
  await open(true);
  fill("phone", "conflict");
  fireEvent.click(screen.getByRole("button", { name: "Save phone decision" }));
  await screen.findByText(/The field snapshot or prior decision changed/);
  expect(screen.getByLabelText("Reason for phone")).toHaveValue(
    "Reviewed pinned source attribution",
  );
  expect(
    screen.getByRole("button", { name: "Save phone decision" }),
  ).toBeDisabled();
  fireEvent.click(
    screen.getByRole("button", { name: "Refresh phone evidence" }),
  );
  await screen.findByText(/field-snapshot-two/);
  fireEvent.click(screen.getByLabelText("I reviewed phone source evidence"));
  fireEvent.click(screen.getByRole("button", { name: "Save phone decision" }));
  await screen.findByText(/Explicit phone conflict saved/);
  const payloads = calls.filter((call) => call.body).map((call) => call.body!);
  expect(payloads).toHaveLength(2);
  expect(payloads[1].expected_snapshot).toBe("field-snapshot-two");
  expect(payloads[1].expected_decision).toBe("intervening-decision");
  expect(payloads[1].request_id).not.toBe(payloads[0].request_id);
});

test("uncertain save locks scope and retries the identical field payload", async () => {
  const calls = setup({ uncertain: true });
  await open(true);
  fill("phone", "conflict");
  fireEvent.click(screen.getByRole("button", { name: "Save phone decision" }));
  await screen.findByText(/The result is unconfirmed/);
  expect(screen.getByLabelText("Reviewed clinician")).toBeDisabled();
  expect(screen.getByLabelText("Actor for phone")).toBeDisabled();
  fireEvent.click(
    screen.getByRole("button", { name: "Retry same phone decision" }),
  );
  await screen.findByText(/Explicit phone conflict saved/);
  const payloads = calls.filter((call) => call.body).map((call) => call.body);
  expect(payloads[1]).toEqual(payloads[0]);
});

test("stale approved dependencies remain exportable as pinned evidence but cannot authorize new decisions", async () => {
  const calls = setup({ stale: true });
  await open(true);
  fill("phone", "conflict");
  expect(
    screen.getByRole("button", { name: "Save phone decision" }),
  ).toBeDisabled();
  expect(
    screen.getByRole("button", { name: "Download reconciled JSON" }),
  ).toBeEnabled();
  expect(
    screen.getByRole("button", { name: "Download reconciled XLSX" }),
  ).toBeEnabled();
  expect(calls.some((call) => call.body)).toBe(false);
});

test("exports pin the complete selected scope and surface stale export errors", async () => {
  const calls = setup({ exportConflict: true });
  await open(true);
  fireEvent.click(
    screen.getByRole("button", { name: "Download reconciled JSON" }),
  );
  await screen.findByText("Export snapshot changed; refresh field evidence");
  expect(
    calls.some(
      (call) =>
        call.path ===
        "/api/reconciliation/identities/clinician/clinician-one/export?location_id=location-one&expected_snapshot=field-snapshot-one&format=json",
    ),
  ).toBe(true);
});

test("evidence pagination is explicit and resets a source choice on the next page", async () => {
  const calls = setup({ paged: true });
  await open(true);
  fill("phone", "select");
  fireEvent.click(
    screen.getByRole("radio", { name: "Choose phone from payer payer-ref" }),
  );
  fireEvent.click(
    within(
      screen.getByRole("group", { name: "Reconciled evidence pages" }),
    ).getByRole("button", { name: "Next" }),
  );
  await waitFor(() =>
    expect(
      calls.some((call) =>
        call.path.includes("location_id=location-one&offset=20&limit=20"),
      ),
    ).toBe(true),
  );
  expect(await screen.findByLabelText("Decision for phone")).toHaveValue("");
});

test("scope declaration problems stay explicit and payer network attribution stays visible", async () => {
  setup({ scopeProblem: true });
  await open(true);
  expect(
    screen.getByText(
      "Conflicting clinician type declarations across linked source runs",
    ),
  ).toBeVisible();
  expect(screen.getAllByText(/Network CEDAR/).length).toBeGreaterThan(0);
  expect(screen.getAllByText("NET-CEDAR").length).toBeGreaterThan(0);
  fill("phone", "select");
  expect(
    screen.getByRole("radio", { name: "Choose phone from payer payer-ref" }),
  ).toBeDisabled();
  expect(
    screen.getByRole("button", { name: "Save phone decision" }),
  ).toBeDisabled();
});

test("technical source provenance stays collapsed outside the exact accessible radio label", async () => {
  setup();
  await open(true);
  const phone = screen.getByRole("region", { name: "phone reconciliation" });
  const provenance = within(phone)
    .getAllByText("Source provenance")[0]
    .closest("details")!;
  expect(provenance).not.toHaveAttribute("open");
  expect(provenance.closest("label")).toBeNull();
  expect(within(provenance).getByText("clinic-ref")).not.toBeVisible();
  expect(
    within(phone).getByRole("radio", {
      name: "Choose phone from clinic clinic-ref",
    }),
  ).toBeInTheDocument();
  fireEvent.click(within(provenance).getByText("Source provenance"));
  expect(within(provenance).getByText("clinic-ref")).toBeVisible();
});
