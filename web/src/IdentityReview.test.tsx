import {
  fireEvent,
  render,
  screen,
  waitFor,
  within,
} from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { afterEach, expect, test, vi } from "vitest";
import { IdentityReview } from "./IdentityReview";

afterEach(() => vi.unstubAllGlobals());
const revision = {
  id: "left-revision",
  kind: "clinician",
  ref: "left",
  target_id: "clinician-one",
  previous_id: null,
  decision_id: "earlier",
  actor: "Earlier reviewer",
  reason: "Existing source crosswalk",
  created_at: "2026-10-30T12:00:00Z",
};
const previousDecision = {
  id: "earlier",
  decision: "defer",
  actor: "Earlier reviewer",
  reason: "Waiting for evidence",
  created_at: "2026-10-30T12:00:00Z",
  target_id: null,
  run_id: "run",
  candidate_id: "candidate",
  pair_key: "pair",
};
function snapshot(overrides = {}) {
  return {
    candidate: {
      id: "candidate",
      kind: "clinician",
      left: "left",
      right: "right",
      eligible: false,
    },
    review_snapshot: "snapshot-one",
    inputs_fresh: true,
    current_links: { left: revision, right: null },
    latest_decision: previousDecision,
    history: [previousDecision],
    targets: {
      clinicians: [{ id: "clinician-one", label: "Alex reviewed" }],
      locations: [{ id: "location-one", label: "North office" }],
    },
    ...overrides,
  };
}
function setup(
  options: {
    kind?: "clinician" | "location";
    stale?: boolean;
    conflict?: boolean;
    uncertain?: boolean;
    unavailable?: boolean;
    paginated?: boolean;
    blocked?: boolean;
  } = {},
) {
  const calls: { path: string; body?: Record<string, unknown> }[] = [];
  let reads = 0;
  let posts = 0;
  vi.stubGlobal(
    "fetch",
    vi.fn(async (path: string, init?: RequestInit) => {
      const body = init?.body ? JSON.parse(String(init.body)) : undefined;
      calls.push({ path, body });
      if (!body) {
        if (path.includes("/targets/"))
          return new Response(
            JSON.stringify(
              options.paginated
                ? {
                    items: [
                      {
                        id: path.includes("offset=20")
                          ? "clinician-later"
                          : "clinician-first",
                        label: path.includes("offset=20")
                          ? "Later page target"
                          : "First page target",
                      },
                    ],
                    total: 21,
                    next_offset: path.includes("offset=20") ? null : 20,
                  }
                : {
                    items: path.includes("/location?")
                      ? [{ id: "location-one", label: "North office" }]
                      : [{ id: "clinician-one", label: "Alex reviewed" }],
                    total: 1,
                    next_offset: null,
                  },
            ),
          );
        reads++;
        if (options.unavailable)
          return new Response(
            JSON.stringify({ detail: "Review unavailable" }),
            { status: 503 },
          );
        return new Response(
          JSON.stringify(
            snapshot({
              candidate: {
                id: "candidate",
                kind: options.kind ?? "clinician",
                left: "left",
                right: "right",
                eligible: false,
              },
              inputs_fresh: !options.stale,
              ...(options.blocked
                ? {
                    approval_allowed: false,
                    approval_blockers: [
                      "Organization evidence cannot establish a clinician identity",
                    ],
                  }
                : {}),
              ...(options.paginated
                ? {
                    history_total: 21,
                    history_next_offset: path.includes("offset=20") ? null : 20,
                    history: [
                      {
                        ...previousDecision,
                        reason: path.includes("offset=20")
                          ? "Older retained decision"
                          : "Waiting for evidence",
                      },
                    ],
                  }
                : {}),
              ...(options.conflict && reads > 1
                ? {
                    review_snapshot: "snapshot-two",
                    current_links: {
                      left: { ...revision, id: "new-left-revision" },
                      right: null,
                    },
                    latest_decision: { ...previousDecision, id: "new-earlier" },
                  }
                : {}),
            }),
          ),
        );
      }
      posts++;
      if (options.conflict && posts === 1)
        return new Response(
          JSON.stringify({
            detail: "Reviewed links or pair decision changed; inspect again",
          }),
          { status: 409 },
        );
      if (options.uncertain && posts === 1)
        throw new TypeError("Connection interrupted");
      return new Response(
        JSON.stringify({
          decision: {
            ...previousDecision,
            id: "saved",
            decision: body.decision,
            actor: body.actor,
            reason: body.reason,
          },
          links: [],
        }),
      );
    }),
  );
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  });
  render(
    <QueryClientProvider client={client}>
      <IdentityReview
        runId="run"
        candidateId="candidate"
        kind={options.kind ?? "clinician"}
      />
    </QueryClientProvider>,
  );
  return calls;
}
async function open(kind = "clinician") {
  fireEvent.click(screen.getByRole("button", { name: `Review ${kind} link` }));
  await screen.findByText(/Source inputs current at this review snapshot/);
}
function fill(action: string) {
  fireEvent.change(screen.getByLabelText("Link decision"), {
    target: { value: action },
  });
  fireEvent.change(screen.getByLabelText("Review actor"), {
    target: { value: "Reviewer" },
  });
  fireEvent.change(screen.getByLabelText("Review reason"), {
    target: { value: "Reviewed both assertions and conflicts" },
  });
  fireEvent.click(
    screen.getByRole("checkbox", { name: /I reviewed both source assertions/ }),
  );
}

test("review is deliberately lazy and retains existing typed links and decision history", async () => {
  const calls = setup();
  expect(calls).toHaveLength(0);
  await open();
  expect(calls).toHaveLength(1);
  expect(calls[0].path).toBe(
    "/api/reconciliation/runs/run/candidates/candidate/review?offset=0&limit=20",
  );
  expect(screen.getByText("Alex reviewed")).toBeVisible();
  expect(screen.getByText("left-revision")).toBeVisible();
  expect(screen.getByText("No reviewed clinician link.")).toBeVisible();
  expect(
    screen.getByText("Earlier reviewer: Waiting for evidence"),
  ).toBeVisible();
  expect(
    screen.getByRole("button", { name: "Save link decision" }),
  ).toBeDisabled();
  expect(calls.some((call) => call.body)).toBe(false);
});

test("manual approval of a conflicting candidate pins both revisions and creates only the explicitly labeled clinician", async () => {
  const calls = setup();
  await open();
  fill("approve");
  expect(
    screen.getByRole("button", { name: "Save link decision" }),
  ).toBeDisabled();
  fireEvent.change(screen.getByLabelText("Target selection"), {
    target: { value: "new" },
  });
  fireEvent.change(screen.getByLabelText("New clinician label"), {
    target: { value: "Alex reviewed identity" },
  });
  expect(
    screen.getByRole("button", { name: "Save link decision" }),
  ).toBeEnabled();
  fireEvent.click(screen.getByRole("button", { name: "Save link decision" }));
  await screen.findByText("Approved clinician link saved for both references.");
  const payload = calls.find((call) => call.body)?.body;
  expect(payload).toEqual({
    run_id: "run",
    candidate_id: "candidate",
    decision: "approve",
    request_id: expect.any(String),
    expected_snapshot: "snapshot-one",
    expected_revisions: { left: "left-revision", right: null },
    expected_decision: "earlier",
    actor: "Reviewer",
    reason: "Reviewed both assertions and conflicts",
    new_label: "Alex reviewed identity",
  });
  expect(payload?.target_id).toBeUndefined();
});

test("location targets stay separate from clinician targets", async () => {
  const calls = setup({ kind: "location" });
  await open("practice location");
  fill("approve");
  const select = await screen.findByLabelText("Target practice location");
  await screen.findByText("1 matching practice location targets.");
  expect(
    within(select).getByRole("option", { name: "North office · location-one" }),
  ).toBeInTheDocument();
  expect(within(select).queryByText(/Alex reviewed/)).not.toBeInTheDocument();
  fireEvent.change(select, { target: { value: "location-one" } });
  fireEvent.click(screen.getByRole("button", { name: "Save link decision" }));
  await screen.findByText(
    "Approved practice location link saved for both references.",
  );
  expect(calls.find((call) => call.body)?.body?.target_id).toBe("location-one");
});

for (const action of ["reject", "defer"]) {
  test(`${action} records only the pair decision and omits targets even after an approval draft`, async () => {
    const calls = setup();
    await open();
    fill("approve");
    await screen.findByText("1 matching clinician targets.");
    fireEvent.change(screen.getByLabelText("Target clinician"), {
      target: { value: "clinician-one" },
    });
    fireEvent.change(screen.getByLabelText("Link decision"), {
      target: { value: action },
    });
    fireEvent.click(screen.getByRole("button", { name: "Save link decision" }));
    await screen.findByText(
      /saved for this pair. Existing links were preserved/,
    );
    const payload = calls.find((call) => call.body)?.body;
    expect(payload?.decision).toBe(action);
    expect(payload).not.toHaveProperty("target_id");
    expect(payload).not.toHaveProperty("new_label");
  });
}

test("a 409 requires explicit refreshed evidence and new snapshot/revision values before retry", async () => {
  const calls = setup({ conflict: true });
  await open();
  fill("defer");
  fireEvent.click(screen.getByRole("button", { name: "Save link decision" }));
  await screen.findByText(/Review state changed/);
  expect(
    screen.getByRole("button", { name: "Save link decision" }),
  ).toBeDisabled();
  expect(screen.getByLabelText("Review reason")).toHaveValue(
    "Reviewed both assertions and conflicts",
  );
  fireEvent.click(
    screen.getByRole("button", { name: "Refresh review snapshot" }),
  );
  await screen.findByText("snapshot-two");
  expect(
    screen.getByRole("button", { name: "Save link decision" }),
  ).toBeDisabled();
  fireEvent.click(
    screen.getByRole("checkbox", { name: /I reviewed both source assertions/ }),
  );
  fireEvent.click(screen.getByRole("button", { name: "Save link decision" }));
  await screen.findByText(/Deferral saved/);
  const payloads = calls.filter((call) => call.body).map((call) => call.body!);
  expect(payloads).toHaveLength(2);
  expect(payloads[1].expected_snapshot).toBe("snapshot-two");
  expect(payloads[1].expected_revisions).toEqual({
    left: "new-left-revision",
    right: null,
  });
  expect(payloads[1].expected_decision).toBe("new-earlier");
  expect(payloads[1].request_id).not.toBe(payloads[0].request_id);
});

test("uncertain network outcome locks edits and retries the identical request UUID and payload", async () => {
  const calls = setup({ uncertain: true });
  await open();
  fill("defer");
  fireEvent.click(screen.getByRole("button", { name: "Save link decision" }));
  await screen.findByText(/The outcome is unconfirmed/);
  expect(screen.getByLabelText("Review actor")).toBeDisabled();
  expect(
    screen.getByRole("button", { name: "Refresh review snapshot" }),
  ).toBeDisabled();
  fireEvent.click(
    screen.getByRole("button", { name: "Retry same review decision" }),
  );
  await screen.findByText(/Deferral saved/);
  const payloads = calls.filter((call) => call.body).map((call) => call.body);
  expect(payloads).toHaveLength(2);
  expect(payloads[1]).toEqual(payloads[0]);
});

test("stale inputs retain history and prevent all decisions", async () => {
  const calls = setup({ stale: true });
  fireEvent.click(
    screen.getByRole("button", { name: "Review clinician link" }),
  );
  await screen.findByText(/These source inputs are stale/);
  fill("defer");
  expect(
    screen.getByRole("button", { name: "Save link decision" }),
  ).toBeDisabled();
  expect(
    screen.getByText("Earlier reviewer: Waiting for evidence"),
  ).toBeVisible();
  expect(calls.some((call) => call.body)).toBe(false);
});

test("failed inspection offers refresh without presenting a write form", async () => {
  setup({ unavailable: true });
  fireEvent.click(
    screen.getByRole("button", { name: "Review clinician link" }),
  );
  expect(await screen.findByRole("alert")).toHaveTextContent(
    "Review unavailable",
  );
  expect(screen.queryByLabelText("Review actor")).not.toBeInTheDocument();
  expect(
    screen.getByRole("button", { name: "Refresh review snapshot" }),
  ).toBeEnabled();
});

test("target search and pagination reach later identities without reusing an invisible selected target", async () => {
  const calls = setup({ paginated: true });
  await open();
  fill("approve");
  await screen.findByText("21 matching clinician targets.");
  const pages = screen.getByRole("group", { name: "clinician target pages" });
  fireEvent.click(within(pages).getByRole("button", { name: "Next targets" }));
  const later = await screen.findByRole("option", {
    name: "Later page target · clinician-later",
  });
  expect(later).toBeInTheDocument();
  fireEvent.change(screen.getByLabelText("Target clinician"), {
    target: { value: "clinician-later" },
  });
  expect(
    screen.getByRole("button", { name: "Save link decision" }),
  ).toBeEnabled();
  fireEvent.change(screen.getByLabelText("Find clinician target"), {
    target: { value: "%_late" },
  });
  await waitFor(() =>
    expect(
      calls.some((call) =>
        call.path.includes("search=%25_late&offset=0&limit=20"),
      ),
    ).toBe(true),
  );
  expect(screen.getByLabelText("Target clinician")).toHaveValue("");
  expect(
    screen.getByRole("button", { name: "Save link decision" }),
  ).toBeDisabled();
});

test("bounded history pages retain total and require evidence review after refreshed context", async () => {
  const calls = setup({ paginated: true });
  await open();
  fill("defer");
  expect(
    screen.getByText("21 decisions recorded for this pair."),
  ).toBeVisible();
  fireEvent.click(screen.getByRole("button", { name: "Next history" }));
  await screen.findByText("Earlier reviewer: Older retained decision");
  expect(
    calls.some((call) => call.path.includes("/review?offset=20&limit=20")),
  ).toBe(true);
  expect(
    screen.getByRole("checkbox", { name: /I reviewed both source assertions/ }),
  ).not.toBeChecked();
  expect(
    screen.getByRole("button", { name: "Save link decision" }),
  ).toBeDisabled();
});

test("typed approval blockers prevent approval while explicit reject and defer stay available", async () => {
  const calls = setup({ blocked: true });
  await open();
  expect(
    screen.getByText(
      "Organization evidence cannot establish a clinician identity",
    ),
  ).toBeVisible();
  expect(
    screen.getByRole("option", {
      name: "Approve both references to one target",
    }),
  ).toBeDisabled();
  fill("defer");
  expect(
    screen.getByRole("button", { name: "Save link decision" }),
  ).toBeEnabled();
  fireEvent.click(screen.getByRole("button", { name: "Save link decision" }));
  await screen.findByText(/Deferral saved/);
  expect(calls.find((call) => call.body)?.body?.decision).toBe("defer");
});
