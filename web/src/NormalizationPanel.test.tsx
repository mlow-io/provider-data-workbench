import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, expect, test, vi } from "vitest";
import { NormalizationPanel } from "./NormalizationPanel";

afterEach(() => vi.unstubAllGlobals());
const definition = {
  version: 1,
  mapping: { phone: "Office tel" },
  transforms: { phone: [{ op: "phone_us" }] },
  required: ["phone"],
};
const profile = {
  row_count: 1,
  columns: [
    {
      name: "Office tel",
      nonempty: 1,
      missing: 0,
      distinct_count: 1,
      examples: ["(212) 555-0101 x007"],
      null_count: 0,
      blank_count: 0,
      absent_count: 0,
    },
  ],
  suggested_mapping: { phone: "Office tel" },
  mapping_candidates: { phone: ["Office tel"] },
  next_offset: null,
};
const preview = {
  total: 1,
  valid_count: 1,
  quarantined_count: 0,
  next_offset: null,
  rows: [
    {
      original: { "Office tel": "(212) 555-0101 x007" },
      normalized: { phone: "2125550101", phone_extension: "007" },
      normalization: { phone: { original: "(212) 555-0101 x007" } },
      locator: { row: 2 },
      problems: [],
    },
  ],
};
function mockApi(items: unknown[] = []) {
  const calls: { url: string; body: Record<string, unknown> | undefined }[] =
    [];
  vi.stubGlobal(
    "fetch",
    vi.fn(async (url: string, init?: RequestInit) => {
      const body = init?.body ? JSON.parse(String(init.body)) : undefined;
      calls.push({ url, body });
      const value = url.includes("/profile?")
        ? profile
        : url.endsWith("/normalization/preview")
          ? preview
          : url.endsWith("/approve")
            ? {
                id: "approved-1",
                state: "approved",
                name: "Office phones",
                definition,
              }
            : url.endsWith("/apply")
              ? { id: "receipt", attempt_id: "next" }
              : init?.method === "POST"
                ? {
                    id: "proposal-1",
                    state: "proposed",
                    name: "Office phones",
                    definition,
                  }
                : { items };
      return new Response(JSON.stringify(value));
    }),
  );
  return calls;
}
const props = {
  receiptId: "receipt",
  attemptId: "attempt",
  onChanged: async () => {},
};
async function open() {
  fireEvent.click(
    screen.getByRole("button", { name: "Profile and normalize" }),
  );
  await screen.findByText(
    "1 source rows · 1 columns. Counts cover all rows; examples are bounded and retain nulls and blanks.",
  );
}
async function makePreview() {
  fireEvent.click(
    screen.getByRole("button", { name: "Use suggested normalization columns" }),
  );
  fireEvent.change(screen.getByLabelText("phone format"), {
    target: { value: "phone_us" },
  });
  fireEvent.click(
    screen.getByRole("button", { name: "Preview normalization" }),
  );
  await screen.findByText("1 valid · 0 quarantined · 1 total");
}

test("lazy profile has no side effects until opened; preview, proposal, approval and application are separate", async () => {
  const calls = mockApi();
  const changed = vi.fn(async () => {});
  render(<NormalizationPanel {...props} onChanged={changed} />);
  expect(calls).toHaveLength(0);
  await open();
  await makePreview();
  expect(
    screen.getByRole("button", { name: "Save proposed recipe" }),
  ).toBeDisabled();
  fireEvent.change(screen.getByLabelText("Recipe name"), {
    target: { value: "Office phones" },
  });
  fireEvent.change(screen.getByLabelText("Recipe reviewer"), {
    target: { value: "Reviewer" },
  });
  fireEvent.change(screen.getByLabelText("Recipe decision reason"), {
    target: { value: "Explicit source format" },
  });
  fireEvent.click(screen.getByRole("button", { name: "Save proposed recipe" }));
  await screen.findByText(
    "Proposed revision saved. Review it, then explicitly approve.",
  );
  expect(calls.filter((c) => c.url.endsWith("/approve"))).toHaveLength(0);
  fireEvent.click(screen.getByRole("button", { name: "Approve recipe" }));
  await screen.findByText(
    "Approved recipe saved. Apply it to create a new interpretation.",
  );
  expect(calls.filter((c) => c.url.endsWith("/apply"))).toHaveLength(0);
  fireEvent.click(
    screen.getByRole("button", { name: "Apply approved recipe" }),
  );
  await waitFor(() => expect(changed).toHaveBeenCalledOnce());
  expect(
    calls
      .filter((c) => c.body)
      .every((c) => c.body?.expected_attempt === "attempt"),
  ).toBe(true);
  expect(
    calls.find((c) => c.url.endsWith("/normalization/preview"))?.body
      ?.definition,
  ).toMatchObject({ transforms: { phone: [{ op: "phone_us" }] } });
  expect(calls.some((c) => c.url.endsWith("/commit"))).toBe(false);
});

test("editing a rule discards old preview and blocks saving until previewed again", async () => {
  mockApi();
  render(<NormalizationPanel {...props} />);
  await open();
  await makePreview();
  fireEvent.change(screen.getByLabelText("phone case"), {
    target: { value: "uppercase" },
  });
  expect(
    screen.queryByText("1 valid · 0 quarantined · 1 total"),
  ).not.toBeInTheDocument();
  expect(
    screen.getByRole("button", { name: "Save proposed recipe" }),
  ).toBeDisabled();
});

test("attempt changes clear local drafts and late responses cannot hydrate the new attempt", async () => {
  let resolvePreview: (value: Response) => void = () => {};
  const calls = mockApi();
  const original = globalThis.fetch;
  vi.stubGlobal(
    "fetch",
    vi.fn((url: string, init?: RequestInit) =>
      url.endsWith("/normalization/preview")
        ? new Promise<Response>((resolve) => {
            resolvePreview = resolve;
          })
        : original(url, init),
    ),
  );
  const view = render(<NormalizationPanel {...props} />);
  await open();
  fireEvent.click(
    screen.getByRole("button", { name: "Use suggested normalization columns" }),
  );
  fireEvent.change(screen.getByLabelText("Recipe name"), {
    target: { value: "Old draft" },
  });
  fireEvent.click(
    screen.getByRole("button", { name: "Preview normalization" }),
  );
  view.rerender(<NormalizationPanel {...props} attemptId="attempt-2" />);
  resolvePreview(new Response(JSON.stringify(preview)));
  expect(screen.queryByLabelText("Recipe name")).not.toBeInTheDocument();
  await open();
  expect(screen.getByLabelText("Recipe name")).toHaveValue("");
  expect(
    screen.queryByText("1 valid · 0 quarantined · 1 total"),
  ).not.toBeInTheDocument();
  expect(calls.filter((c) => c.url.includes("/profile?"))).toHaveLength(2);
});

test("approved compatible recipe requires a fresh preview before reuse; accepted dataset stays discoverable", async () => {
  const calls = mockApi([
    {
      id: "prior-approved",
      name: "Prior phones",
      state: "approved",
      definition,
    },
  ]);
  render(<NormalizationPanel {...props} accepted />);
  expect(
    screen.getByRole("link", { name: "Download validated dataset JSON" }),
  ).toHaveAttribute("href", "/api/intakes/receipt/dataset");
  await open();
  fireEvent.change(screen.getByLabelText("Compatible approved recipe"), {
    target: { value: "prior-approved" },
  });
  expect(
    screen.getByRole("button", { name: "Apply selected approved recipe" }),
  ).toBeDisabled();
  fireEvent.click(
    screen.getByRole("button", { name: "Preview normalization" }),
  );
  await screen.findByText("1 valid · 0 quarantined · 1 total");
  fireEvent.click(
    screen.getByRole("button", { name: "Apply selected approved recipe" }),
  );
  await waitFor(() =>
    expect(calls.some((c) => c.url.endsWith("/prior-approved/apply"))).toBe(
      true,
    ),
  );
});

test("unsupported inputs explain their scope without loading; server errors remain visible", async () => {
  const calls = mockApi();
  const view = render(<NormalizationPanel {...props} supported={false} />);
  fireEvent.click(
    screen.getByRole("button", { name: "Profile and normalize" }),
  );
  expect(
    screen.getByText(/Native reference adapters and network rosters/),
  ).toBeInTheDocument();
  expect(calls).toHaveLength(0);
  view.unmount();
  vi.stubGlobal(
    "fetch",
    vi.fn(
      async () =>
        new Response(
          JSON.stringify({
            detail: "Interpretation changed; inspect current attempt",
          }),
          { status: 409 },
        ),
    ),
  );
  render(<NormalizationPanel {...props} />);
  fireEvent.click(
    screen.getByRole("button", { name: "Profile and normalize" }),
  );
  expect(await screen.findByRole("alert")).toHaveTextContent(
    "Interpretation changed",
  );
});

test("a persisted MCP proposal loads stored evidence and requires fresh preview and a new approval decision", async () => {
  const calls = mockApi([
    {
      id: "mcp-draft",
      name: "MCP office rules",
      state: "proposed",
      definition,
      receipt_id: "receipt",
      attempt_id: "attempt",
      actor: "MCP drafter",
      reason: "Source sample checked by agent",
    },
  ]);
  render(<NormalizationPanel {...props} />);
  await open();
  fireEvent.change(screen.getByLabelText("Retained recipe proposal"), {
    target: { value: "mcp-draft" },
  });
  expect(screen.getByLabelText("Normalize phone source")).toHaveValue(
    "Office tel",
  );
  expect(screen.getByLabelText("phone format")).toHaveValue("phone_us");
  expect(screen.getByLabelText("Saved recipe decision")).toHaveTextContent(
    "MCP drafter",
  );
  expect(screen.getByLabelText("Saved recipe decision")).toHaveTextContent(
    "Source sample checked by agent",
  );
  expect(screen.getByLabelText("Recipe reviewer")).toHaveValue("");
  expect(screen.getByLabelText("Recipe decision reason")).toHaveValue("");
  fireEvent.change(screen.getByLabelText("Recipe reviewer"), {
    target: { value: "Human reviewer" },
  });
  fireEvent.change(screen.getByLabelText("Recipe decision reason"), {
    target: { value: "Reviewed exact phone extension rule" },
  });
  expect(screen.getByRole("button", { name: "Approve recipe" })).toBeDisabled();
  fireEvent.click(
    screen.getByRole("button", { name: "Preview normalization" }),
  );
  await screen.findByText("1 valid · 0 quarantined · 1 total");
  fireEvent.click(screen.getByRole("button", { name: "Approve recipe" }));
  await waitFor(() =>
    expect(
      calls.find((c) => c.url.endsWith("/mcp-draft/approve"))?.body,
    ).toEqual({
      expected_attempt: "attempt",
      actor: "Human reviewer",
      reason: "Reviewed exact phone extension rule",
    }),
  );
  expect(
    calls.filter((c) => c.url.endsWith("/recipes") && c.body),
  ).toHaveLength(0);
});

test("stale proposals stay inspectable but cannot approve against a newer attempt", async () => {
  const calls = mockApi([
    {
      id: "stale-draft",
      name: "Older rules",
      state: "proposed",
      definition,
      receipt_id: "receipt",
      attempt_id: "old-attempt",
      actor: "Old reviewer",
      reason: "Old sample",
    },
  ]);
  render(<NormalizationPanel {...props} />);
  await open();
  fireEvent.change(screen.getByLabelText("Retained recipe proposal"), {
    target: { value: "stale-draft" },
  });
  expect(screen.getByLabelText("Saved recipe decision")).toHaveTextContent(
    "Old sample",
  );
  fireEvent.change(screen.getByLabelText("Recipe reviewer"), {
    target: { value: "Reviewer" },
  });
  fireEvent.change(screen.getByLabelText("Recipe decision reason"), {
    target: { value: "Current sample reviewed" },
  });
  fireEvent.click(
    screen.getByRole("button", { name: "Preview normalization" }),
  );
  await screen.findByText("1 valid · 0 quarantined · 1 total");
  expect(screen.getByRole("button", { name: "Approve recipe" })).toBeDisabled();
  expect(calls.some((c) => c.url.endsWith("/approve"))).toBe(false);
  fireEvent.click(
    screen.getByRole("button", {
      name: "Copy proposal rules into a new draft",
    }),
  );
  expect(
    screen.getByRole("button", { name: "Save proposed recipe" }),
  ).toBeDisabled();
  expect(
    screen.queryByText("1 valid · 0 quarantined · 1 total"),
  ).not.toBeInTheDocument();
});

test("a compatible proposal from another receipt requires a new proposal and an edited approved definition loses revision selection", async () => {
  const calls = mockApi([
    {
      id: "other-draft",
      name: "Shared source rules",
      state: "proposed",
      definition,
      receipt_id: "other-receipt",
      attempt_id: "other-attempt",
      actor: "Other drafter",
      reason: "Prior delivery",
    },
    {
      id: "prior-approved",
      name: "Prior approved",
      state: "approved",
      definition,
    },
  ]);
  render(<NormalizationPanel {...props} />);
  await open();
  fireEvent.change(screen.getByLabelText("Retained recipe proposal"), {
    target: { value: "other-draft" },
  });
  expect(screen.getByRole("button", { name: "Approve recipe" })).toBeDisabled();
  expect(screen.getByLabelText("Saved recipe decision")).toHaveTextContent(
    "Other drafter",
  );
  fireEvent.click(
    screen.getByRole("button", { name: "Preview normalization" }),
  );
  await screen.findByText("1 valid · 0 quarantined · 1 total");
  fireEvent.change(screen.getByLabelText("Recipe reviewer"), {
    target: { value: "Current reviewer" },
  });
  fireEvent.change(screen.getByLabelText("Recipe decision reason"), {
    target: { value: "Adapted source rules for this delivery" },
  });
  fireEvent.click(screen.getByRole("button", { name: "Save proposed recipe" }));
  await screen.findByText(
    "Proposed revision saved. Review it, then explicitly approve.",
  );
  expect(
    calls.some(
      (c) =>
        c.url.endsWith("/recipes") && c.body?.expected_attempt === "attempt",
    ),
  ).toBe(true);
  expect(calls.some((c) => c.url.endsWith("/other-draft/approve"))).toBe(false);
  fireEvent.change(screen.getByLabelText("Compatible approved recipe"), {
    target: { value: "prior-approved" },
  });
  fireEvent.click(
    screen.getByRole("button", { name: "Preview normalization" }),
  );
  await screen.findByText("1 valid · 0 quarantined · 1 total");
  fireEvent.change(screen.getByLabelText("phone case"), {
    target: { value: "uppercase" },
  });
  expect(screen.getByLabelText("Compatible approved recipe")).toHaveValue("");
  expect(
    screen.getByRole("button", { name: "Apply selected approved recipe" }),
  ).toBeDisabled();
});

test("reopening an applied recipe shows its authority and exact phone/date rules without creating a proposal", async () => {
  const appliedDefinition = {
    version: 1,
    mapping: { phone: "Office tel", source_updated_at: "Changed" },
    transforms: {
      phone: [{ op: "phone_us" }],
      source_updated_at: [{ op: "date", format: "%d/%m/%Y" }],
    },
    required: ["phone"],
  };
  const calls = mockApi([
    {
      id: "applied-approved",
      name: "Applied clinic rules",
      state: "approved",
      definition: appliedDefinition,
    },
  ]);
  const originalFetch = globalThis.fetch;
  vi.stubGlobal(
    "fetch",
    vi.fn((url: string, init?: RequestInit) =>
      url.includes("/profile?")
        ? Promise.resolve(
            new Response(
              JSON.stringify({
                ...profile,
                columns: [
                  ...profile.columns,
                  {
                    ...profile.columns[0],
                    name: "Changed",
                    examples: ["03/04/2026"],
                  },
                ],
              }),
            ),
          )
        : originalFetch(url, init),
    ),
  );
  render(<NormalizationPanel {...props} appliedRecipeId="applied-approved" />);
  expect(
    screen.getByLabelText("Applied normalization recipe"),
  ).toHaveTextContent("applied-approved");
  fireEvent.click(
    screen.getByRole("button", { name: "Profile and normalize" }),
  );
  await screen.findByText(
    "1 source rows · 2 columns. Counts cover all rows; examples are bounded and retain nulls and blanks.",
  );
  expect(
    screen.getByLabelText("Applied normalization recipe"),
  ).toHaveTextContent("Applied clinic rules / applied-approved");
  expect(screen.getByLabelText("phone format")).toHaveValue("phone_us");
  expect(screen.getByLabelText("source updated at format")).toHaveValue(
    "%d/%m/%Y",
  );
  expect(screen.getByLabelText("Recipe name")).toHaveValue("");
  expect(screen.getByLabelText("Compatible approved recipe")).toHaveValue("");
  expect(screen.getByRole("button", { name: "Approve recipe" })).toBeDisabled();
  expect(
    screen.getByRole("button", { name: "Apply approved recipe" }),
  ).toBeDisabled();
  fireEvent.change(screen.getByLabelText("phone format"), {
    target: { value: "" },
  });
  fireEvent.click(
    screen.getByRole("button", { name: "Profile and normalize" }),
  );
  fireEvent.click(
    screen.getByRole("button", { name: "Profile and normalize" }),
  );
  expect(screen.getByLabelText("phone format")).toHaveValue("");
  expect(calls.some((call) => call.body)).toBe(false);
});

test("profile compatibility explains drift and copying still requires a fresh preview", async () => {
  const calls = mockApi();
  const original = globalThis.fetch;
  vi.stubGlobal("fetch", vi.fn((url: string, init?: RequestInit) => {
    if (url.includes("/recipe-compatibility?")) return Promise.resolve(new Response(JSON.stringify({
      notice: "Structural compatibility only.", total: 2, next_offset: null,
      items: [
        { revision_id: "compatible", name: "Prior office phones", status: "compatible", reusable: true, missing_mapped_columns: [], added_columns: ["Updated"], removed_columns: [] },
        { revision_id: "drifted", name: "Old workbook", status: "drift", reusable: false, missing_mapped_columns: ["Old phone"], added_columns: [], removed_columns: ["Old phone"] },
      ],
    })));
    if (url.endsWith("/reuse")) return Promise.resolve(new Response(JSON.stringify({ id: "copied", name: "Prior office phones", state: "proposed", receipt_id: "receipt", attempt_id: "attempt", definition })));
    return original(url, init);
  }));
  render(<NormalizationPanel {...props} />);
  await open();
  fireEvent.click(screen.getByRole("button", { name: "Check reusable source profiles" }));
  await screen.findByText("Structural compatibility only.");
  expect(screen.getByText("Missing mapped columns: Old phone")).toBeInTheDocument();
  fireEvent.change(screen.getByLabelText("Recipe reviewer"), { target: { value: "Reviewer" } });
  fireEvent.change(screen.getByLabelText("Recipe decision reason"), { target: { value: "Reviewed repeated source" } });
  expect(screen.getByRole("button", { name: "Copy Old workbook as a proposal" })).toBeDisabled();
  fireEvent.click(screen.getByRole("button", { name: "Copy Prior office phones as a proposal" }));
  await screen.findByText(/Reviewed profile copied into a new proposal/);
  expect(screen.getByRole("button", { name: "Approve recipe" })).toBeDisabled();
  expect(screen.getByLabelText("Normalize phone source")).toHaveValue("Office tel");
  expect(calls.some(call => call.url.endsWith("/apply"))).toBe(false);
});
