import { expect, test } from "@playwright/test";

// All synthetic linking/field setup is explicit API fixture work. Proposal and
// impact preview are exercised through the real operator interface below.
test("NORTH phone preview excludes SOUTH, retains unlinked coverage and becomes stale after a link revision", async ({
  page,
}, info) => {
  const prefix = `impact-${info.project.name}`;
  const row = (id: string, office: string, phone: string) => ({
    record_id: id,
    npi: "1000000001",
    provider_name: "Alex Impact Synthetic",
    entity_type: "clinician",
    address:
      office === "NORTH"
        ? "10 Example Street STE 04"
        : "20 Sample Avenue STE 200",
    city: "Boston",
    state: "MA",
    zip: "02108",
    phone,
    phone_extension: null,
    location_id: office,
  });
  const receipts: Record<string, { id: string; attempt_id: string }> = {};
  for (const source of ["clinic", "payer", "unlinked"]) {
    const rows =
      source === "unlinked"
        ? [
            {
              ...row("U1", "NORTH", "2125550188"),
              npi: null,
              provider_name: "Unlinked Ambiguous Synthetic",
            },
          ]
        : [
            row(
              `${source}-N`,
              "NORTH",
              source === "payer" ? "2125550199" : "2125550101",
            ),
            row(`${source}-S`, "SOUTH", "2125550102"),
          ];
    const response = await page.request.post(
      `/api/intakes/files?${new URLSearchParams({ filename: `${prefix}-${source}.json`, source: `${prefix}-${source}`, designation: "synthetic", profile: "flat" })}`,
      {
        data: Buffer.from(JSON.stringify(rows)),
        headers: { "Content-Type": "application/octet-stream" },
      },
    );
    expect(response.ok(), await response.text()).toBe(true);
    receipts[source] = await response.json();
  }
  const runResponse = await page.request.post("/api/reconciliation/runs", {
    data: {
      inputs: Object.values(receipts).map((receipt) => ({
        receipt_id: receipt.id,
        attempt_id: receipt.attempt_id,
        entity_kind: "clinician",
      })),
      actor: "Synthetic Reviewer",
      reason: "Explicit NORTH/SOUTH/unlinked impact setup",
    },
  });
  expect(runResponse.ok(), await runResponse.text()).toBe(true);
  const run = await runResponse.json();
  const all = await (
    await page.request.get(
      `/api/reconciliation/runs/${run.id}/candidates?limit=100`,
    )
  ).json();
  const targets: Record<string, string> = {};
  let northCandidateId = "";
  async function approve(candidateId: string, key: string) {
    const current = await (
      await page.request.get(
        `/api/reconciliation/runs/${run.id}/candidates/${candidateId}/review`,
      )
    ).json();
    const response = await page.request.post("/api/reconciliation/links", {
      data: {
        run_id: run.id,
        candidate_id: candidateId,
        decision: "approve",
        request_id: crypto.randomUUID(),
        expected_snapshot: current.review_snapshot,
        expected_revisions: Object.fromEntries(
          Object.entries(current.current_links).map(([ref, link]) => [
            ref,
            (link as { id: string } | null)?.id ?? null,
          ]),
        ),
        expected_decision: current.latest_decision?.id ?? null,
        actor: "Synthetic Reviewer",
        reason: `Explicit ${key} crosswalk fixture`,
        ...(targets[key]
          ? { target_id: targets[key] }
          : { new_label: `${prefix} ${key}` }),
      },
    });
    expect(response.ok(), await response.text()).toBe(true);
    targets[key] = (await response.json()).decision.target_id;
  }
  for (const candidate of all.items) {
    if (
      candidate.left_record.source === `${prefix}-unlinked` ||
      candidate.right_record.source === `${prefix}-unlinked`
    )
      continue;
    if (candidate.kind === "clinician")
      await approve(candidate.id, "clinician");
  }
  for (const candidate of all.items) {
    if (
      candidate.kind !== "location" ||
      candidate.left_record.source === `${prefix}-unlinked` ||
      candidate.right_record.source === `${prefix}-unlinked`
    )
      continue;
    const office = candidate.left_record.comparison.address.line1.startsWith(
      "10 ",
    )
      ? "NORTH"
      : "SOUTH";
    await approve(candidate.id, office);
    if (office === "NORTH") northCandidateId = candidate.id;
  }
  const fieldView = await (
    await page.request.get(
      `/api/reconciliation/fields/${targets.clinician}?location_id=${targets.NORTH}`,
    )
  ).json();
  expect(fieldView.inputs_fresh).toBe(true);
  const reviewed = await page.request.post(
    "/api/reconciliation/field-decisions",
    {
      data: {
        clinician_id: targets.clinician,
        location_id: targets.NORTH,
        field: "phone",
        decision: "conflict",
        expected_snapshot: fieldView.snapshot,
        expected_decision: null,
        request_id: crypto.randomUUID(),
        actor: "Synthetic Reviewer",
        reason: "Retain the NORTH phone discrepancy before proposing a change",
      },
    },
  );
  expect(reviewed.ok(), await reviewed.text()).toBe(true);
  const beforeWork = await (await page.request.get("/api/work")).json();
  await page.goto("/?view=reconciliation");
  await page
    .getByRole("button", {
      name: "Open reconciled field evidence",
      exact: true,
    })
    .click();
  const fields = page.getByRole("region", {
    name: "Reconciled field evidence",
    exact: true,
  });
  await fields
    .getByLabel("Find reviewed clinician", { exact: true })
    .fill(targets.clinician);
  await fields
    .getByLabel("Reviewed clinician", { exact: true })
    .selectOption(targets.clinician);
  await fields
    .getByLabel("Include a reviewed practice location", { exact: true })
    .check();
  await fields
    .getByLabel("Find reviewed practice location", { exact: true })
    .fill(targets.NORTH);
  await fields
    .getByLabel("Reviewed practice location", { exact: true })
    .selectOption(targets.NORTH);
  await fields
    .getByRole("button", { name: "Open change impact preview", exact: true })
    .click();
  const panel = page.getByRole("region", {
    name: "Provider-change impact preview",
    exact: true,
  });
  await panel
    .getByLabel("Proposed field", { exact: true })
    .selectOption("phone");
  await panel
    .getByLabel("Proposed phone number", { exact: true })
    .fill("2125550111");
  await panel
    .getByLabel(`Assess delivery ${prefix}-payer.json`, { exact: true })
    .check();
  await panel
    .getByLabel(`Assess delivery ${prefix}-unlinked.json`, { exact: true })
    .check();
  await panel
    .getByLabel("Proposal actor", { exact: true })
    .fill("Synthetic Reviewer");
  await panel
    .getByLabel("Proposal reason", { exact: true })
    .fill("Propose NORTH phone change and assess named retained listings");
  await panel
    .getByLabel("I reviewed the prior field and assessment inputs", {
      exact: true,
    })
    .check();
  const savedResponse = page.waitForResponse(
    (response) =>
      response.url().endsWith("/api/reconciliation/change-proposals") &&
      response.request().method() === "POST",
  );
  await panel
    .getByRole("button", { name: "Save change proposal", exact: true })
    .click();
  const saved = await savedResponse;
  expect(saved.ok(), await saved.text()).toBe(true);
  const proposal = await saved.json();
  await expect(
    panel.getByText(
      "Change proposal saved. Run the read-only impact preview separately.",
      { exact: true },
    ),
  ).toBeVisible();
  const previewResponse = page.waitForResponse(
    (response) =>
      response.url().endsWith("/api/reconciliation/impact-preview") &&
      response.request().method() === "POST",
  );
  await panel
    .getByRole("button", { name: "Run read-only impact preview", exact: true })
    .click();
  const firstPreviewResponse = await previewResponse;
  expect(firstPreviewResponse.ok(), await firstPreviewResponse.text()).toBe(
    true,
  );
  const first = await firstPreviewResponse.json();
  expect(first.counts).toEqual({
    affected: 1,
    unaffected_within_assessed_scope: 1,
    not_assessed: 1,
  });
  expect(first.inputs_fresh).toBe(true);
  expect(
    first.targets.find(
      (target: { value: { number: string } }) =>
        target.value.number === "2125550102",
    ).classification,
  ).toBe("unaffected_within_assessed_scope");
  expect(
    first.targets.find(
      (target: { source: string }) => target.source === `${prefix}-unlinked`,
    ).classification,
  ).toBe("not_assessed");
  const results = panel.getByRole("region", {
    name: "Impact assessment results",
    exact: true,
  });
  await expect(
    results.getByText("Reviewed different practice location", { exact: true }),
  ).toBeVisible();
  await expect(
    results.getByText("No current reviewed clinician link", { exact: true }),
  ).toBeVisible();
  await expect(
    results.getByText(
      "No existing work records on this page. Preview creates none.",
      { exact: true },
    ),
  ).toBeVisible();
  await results.screenshot({
    path: info.outputPath("impact-NORTH-SOUTH-unlinked.png"),
  });
  const repeatResponse = page.waitForResponse(
    (response) =>
      response.url().endsWith("/api/reconciliation/impact-preview") &&
      response.request().method() === "POST",
  );
  await panel
    .getByRole("button", { name: "Run read-only impact preview", exact: true })
    .click();
  const repeat = await (await repeatResponse).json();
  expect(repeat.snapshot).toBe(first.snapshot);
  expect(await (await page.request.get("/api/work")).json()).toEqual(
    beforeWork,
  );
  await approve(northCandidateId, "NORTH");
  const staleResponse = page.waitForResponse(
    (response) =>
      response.url().endsWith("/api/reconciliation/impact-preview") &&
      response.request().method() === "POST",
  );
  await panel
    .getByRole("button", { name: "Run read-only impact preview", exact: true })
    .click();
  const stale = await (await staleResponse).json();
  expect(stale.inputs_fresh).toBe(false);
  expect(stale.stale_reasons).toContain(
    "Reviewed field/source/link evidence changed",
  );
  await expect(
    results.getByText("This proposal preview is stale.", { exact: true }),
  ).toBeVisible();
  await results.screenshot({
    path: info.outputPath("impact-stale-reviewed-link.png"),
  });
  expect(await (await page.request.get("/api/work")).json()).toEqual(
    beforeWork,
  );
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= window.innerWidth + 1,
    ),
  ).toBe(true);
  expect(proposal.id).toBeTruthy();
});
