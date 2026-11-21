import { expect, test } from "@playwright/test";

test("explicit typed links, pair deferral and conflict refresh preserve reviewed history", async ({
  page,
}, info) => {
  const prefix = `identity-review-${info.project.name}`;
  const inputs = [];
  for (const source of ["clinic", "payer"]) {
    const response = await page.request.post(
      `/api/intakes/files?${new URLSearchParams({ filename: `${prefix}-${source}.json`, source: `${prefix}-${source}`, designation: "synthetic", profile: "flat" })}`,
      {
        data: Buffer.from(
          JSON.stringify([
            {
              record_id: "001",
              npi: "1000000001",
              provider_name: "Alex Identity Synthetic",
              entity_type: "clinician",
              address: "10 Example Street STE 04",
              city: "Boston",
              state: "MA",
              zip: "02108",
              phone: "2125550101",
              location_id: "NORTH",
            },
          ]),
        ),
        headers: { "Content-Type": "application/octet-stream" },
      },
    );
    expect(response.ok(), await response.text()).toBe(true);
    const receipt = await response.json();
    inputs.push({
      receipt_id: receipt.id,
      attempt_id: receipt.attempt_id,
      entity_kind: "clinician",
    });
  }
  const created = await page.request.post("/api/reconciliation/runs", {
    data: {
      inputs,
      actor: "Synthetic Reviewer",
      reason: "Review two explicit synthetic source assertions",
    },
  });
  expect(created.ok(), await created.text()).toBe(true);
  const run = await created.json();
  const candidates = await (
    await page.request.get(
      `/api/reconciliation/runs/${run.id}/candidates?limit=100`,
    )
  ).json();
  const clinician = candidates.items.find(
    (candidate: { kind: string }) => candidate.kind === "clinician",
  );
  const location = candidates.items.find(
    (candidate: { kind: string }) => candidate.kind === "location",
  );
  await page.goto("/?view=reconciliation");
  await expect(
    page.getByLabel("Saved candidate run", { exact: true }),
  ).toHaveValue(run.id);
  await page.locator(".rc-candidate > summary").first().click();
  await page
    .getByRole("button", { name: "Review clinician link", exact: true })
    .click();
  let review = page.getByRole("region", {
    name: "clinician link review",
    exact: true,
  });
  await expect(review.getByText("No reviewed clinician link.")).toHaveCount(2);
  await review
    .getByLabel("Link decision", { exact: true })
    .selectOption("approve");
  await review
    .getByLabel("Target selection", { exact: true })
    .selectOption("new");
  await review
    .getByLabel("New clinician label", { exact: true })
    .fill(`${prefix} Alex reviewed`);
  await review
    .getByLabel("Review actor", { exact: true })
    .fill("Synthetic Reviewer");
  await review
    .getByLabel("Review reason", { exact: true })
    .fill("Inspected retained NPI, names and independent location evidence");
  await review
    .getByRole("checkbox", { name: /I reviewed both source assertions/ })
    .check();
  const approvedResponse = page.waitForResponse(
    (response) =>
      response.url().endsWith("/api/reconciliation/links") &&
      response.request().method() === "POST",
  );
  await review
    .getByRole("button", { name: "Save link decision", exact: true })
    .click();
  const approved = await (await approvedResponse).json();
  await expect(
    review.getByText("Approved clinician link saved for both references.", {
      exact: true,
    }),
  ).toBeVisible();
  await expect(review.getByText(/Linked to/)).toHaveCount(2);
  expect(approved.links).toHaveLength(2);
  expect(
    new Set(approved.links.map((link: { target_id: string }) => link.target_id))
      .size,
  ).toBe(1);
  const unchangedLocation = await (
    await page.request.get(
      `/api/reconciliation/runs/${run.id}/candidates/${location.id}/review`,
    )
  ).json();
  expect(Object.values(unchangedLocation.current_links)).toEqual([null, null]);

  await review
    .getByLabel("Link decision", { exact: true })
    .selectOption("defer");
  await review
    .getByLabel("Review reason", { exact: true })
    .fill("Defer this pair without removing approved links");
  await review
    .getByRole("checkbox", { name: /I reviewed both source assertions/ })
    .check();
  await review
    .getByRole("button", { name: "Save link decision", exact: true })
    .click();
  await expect(
    review.getByText(
      "Deferral saved for this pair. Existing links were preserved.",
      { exact: true },
    ),
  ).toBeVisible();
  await expect(review.getByText(/Linked to/)).toHaveCount(2);
  await page.reload();
  await expect(
    page.getByLabel("Saved candidate run", { exact: true }),
  ).toHaveValue(run.id);
  await page.locator(".rc-candidate > summary").first().click();
  await page
    .getByRole("button", { name: "Review clinician link", exact: true })
    .click();
  review = page.getByRole("region", {
    name: "clinician link review",
    exact: true,
  });
  await expect(
    review.getByText("2 decisions recorded for this pair.", { exact: true }),
  ).toBeVisible();
  await expect(review.getByText(/Linked to/)).toHaveCount(2);
  await review.screenshot({
    path: info.outputPath("identity-reviewed-links-history.png"),
  });

  // An independent reviewer records a real intervening decision after this form
  // loaded; the UI must handle the server's actual optimistic-concurrency 409.
  await review
    .getByLabel("Link decision", { exact: true })
    .selectOption("reject");
  await review
    .getByLabel("Review actor", { exact: true })
    .fill("Synthetic Reviewer");
  await review
    .getByLabel("Review reason", { exact: true })
    .fill("Draft retained across an intervening review decision");
  await review
    .getByRole("checkbox", { name: /I reviewed both source assertions/ })
    .check();
  const current = await (
    await page.request.get(
      `/api/reconciliation/runs/${run.id}/candidates/${clinician.id}/review`,
    )
  ).json();
  const intervening = await page.request.post("/api/reconciliation/links", {
    data: {
      run_id: run.id,
      candidate_id: clinician.id,
      decision: "defer",
      request_id: crypto.randomUUID(),
      expected_snapshot: current.review_snapshot,
      expected_revisions: Object.fromEntries(
        Object.entries(current.current_links).map(([ref, link]) => [
          ref,
          (link as { id: string } | null)?.id ?? null,
        ]),
      ),
      expected_decision: current.latest_decision.id,
      actor: "Other synthetic reviewer",
      reason: "Explicit competing pair decision",
    },
  });
  expect(intervening.ok(), await intervening.text()).toBe(true);
  const conflictResponse = page.waitForResponse(
    (response) =>
      response.url().endsWith("/api/reconciliation/links") &&
      response.request().method() === "POST",
  );
  await review
    .getByRole("button", { name: "Save link decision", exact: true })
    .click();
  expect((await conflictResponse).status()).toBe(409);
  await expect(review.getByText(/Review state changed/)).toBeVisible();
  await expect(review.getByLabel("Review reason", { exact: true })).toHaveValue(
    "Draft retained across an intervening review decision",
  );
  await expect(
    review.getByRole("button", { name: "Save link decision", exact: true }),
  ).toBeDisabled();
  await review.screenshot({
    path: info.outputPath("identity-stale-conflict.png"),
  });
  await review
    .getByRole("button", { name: "Refresh review snapshot", exact: true })
    .click();
  await expect(
    review.getByText("3 decisions recorded for this pair.", { exact: true }),
  ).toBeVisible();
  await review
    .getByRole("checkbox", { name: /I reviewed both source assertions/ })
    .check();
  await review
    .getByRole("button", { name: "Save link decision", exact: true })
    .click();
  await expect(
    review.getByText(
      "Rejection saved for this pair. Existing links were preserved.",
      { exact: true },
    ),
  ).toBeVisible();
  const final = await (
    await page.request.get(
      `/api/reconciliation/runs/${run.id}/candidates/${clinician.id}/review`,
    )
  ).json();
  expect(final.history_total).toBe(4);
  expect(
    Object.values(final.current_links)
      .map((link) => (link as { id: string }).id)
      .sort(),
  ).toEqual(approved.links.map((link: { id: string }) => link.id).sort());
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= window.innerWidth + 1,
    ),
  ).toBe(true);
});
