import { expect, test, type Page, type APIResponse } from "@playwright/test";
import { readFile, writeFile, mkdtemp } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { createHash } from "node:crypto";
import { execFileSync } from "node:child_process";

type Receipt = {
  id: string;
  attempt_id: string;
  state: string;
  observations: unknown[];
  preview: {
    rows: {
      original: Record<string, unknown>;
      normalized: Record<string, unknown>;
    }[];
    valid_count: number;
    quarantined_count: number;
  };
};
type Candidate = {
  id: string;
  kind: "clinician" | "location";
  left_record: {
    source: string;
    address_path: string;
    comparison: {
      npi: string | null;
      address: { line1: string; kind: string };
    };
  };
  right_record: {
    source: string;
    address_path: string;
    comparison: {
      npi: string | null;
      address: { line1: string; kind: string };
    };
  };
};
async function body(response: APIResponse) {
  expect(response.ok(), await response.text()).toBe(true);
  return response.json();
}
async function uploadUI(
  page: Page,
  source: string,
  filename: string,
  bytes: Buffer,
  profile: "flat" | "nppes" = "flat",
  datasetScope?: string,
): Promise<Receipt> {
  await page.getByLabel("Source namespace", { exact: true }).fill(source);
  if (datasetScope) {
    await page.getByText("Delivery scope and source date (optional)", { exact: true }).click();
    await page.getByLabel("Dataset scope", { exact: true }).fill(datasetScope);
  }
  await page
    .getByRole("combobox", { name: "Response profile", exact: true })
    .selectOption(profile);
  await page.getByLabel("Source file", { exact: true }).setInputFiles({
    name: filename,
    mimeType: profile === "nppes" ? "application/json" : "text/csv",
    buffer: bytes,
  });
  const response = page.waitForResponse(
    (response) =>
      response.url().includes("/api/intakes/files?") &&
      response.request().method() === "POST",
  );
  await page
    .getByRole("button", { name: "Upload and preview", exact: true })
    .click();
  const receipt = await body(await response);
  await expect(
    page.getByRole("heading", { name: filename, exact: true }),
  ).toBeVisible();
  return receipt;
}
async function downloadJSON(
  page: Page,
  button: ReturnType<Page["getByRole"]>,
  filename: string,
) {
  const pending = page.waitForEvent("download");
  await button.click();
  await (await pending).saveAs(filename);
  return JSON.parse(await readFile(filename, "utf8"));
}
async function downloadWorkbook(
  page: Page,
  button: ReturnType<Page["getByRole"]>,
  filename: string,
) {
  const pending = page.waitForEvent("download");
  await button.click();
  await (await pending).saveAs(filename);
  return JSON.parse(
    execFileSync(
      "python3",
      [
        "-c",
        `import json,sys\nfrom openpyxl import load_workbook\nw=load_workbook(sys.argv[1],read_only=True,data_only=False)\nrows=list(w['Payload'].values)[1:]\npayload=json.loads(''.join(row[1] for row in sorted(rows,key=lambda row:int(row[0]))))\nprint(json.dumps({'payload':payload,'sheets':w.sheetnames,'formulas':sum(cell.data_type=='f' for sheet in w for row in sheet for cell in row)}))\nw.close()`,
        filename,
      ],
      { encoding: "utf8", maxBuffer: 20 * 1024 * 1024 },
    ),
  );
}

// Catalog/source-code setup is fixture scaffolding only. Every recipe, source
// acceptance, reviewed crosswalk, field, proposal, confirmation and ack decision
// below uses real UI controls; no test route or pre-populated link is used.
test("one discoverable three-source journey from reviewed normalization through scoped acknowledged handoff", async ({
  page,
}, info) => {
  test.setTimeout(240_000);
  const prefix = `ri1-${info.project.name}`;
  const sources = {
    clinic: `${prefix}-clinic`,
    payer: `${prefix}-payer`,
    native: `${prefix}-nppes`,
  };
  const labels = {
    clinic: `${prefix}-clinic.csv`,
    payer: `${prefix}-payer.csv`,
    native: `${prefix}-nppes.json`,
  };
  const fixtures = new URL("./fixtures/ingestion-platform/", import.meta.url);
  const clinicBytes = await readFile(new URL("clinic.csv", fixtures));
  const payerBytes = await readFile(new URL("payer.csv", fixtures));
  const nativeBytes = await readFile(new URL("nppes.json", fixtures));
  await test.step("Start from the default operator entry", async () => {
    await page.goto('/');
    await expect(page.getByRole('heading', {name:'Review the delivery. Approve the version.'})).toBeVisible();
    await expect(page.getByRole('heading', {name:'Registered feeds'})).toBeVisible();
  });
  async function catalog(path: string, value: Record<string, unknown>) {
    return body(
      await page.request.post(`/api/catalog/${path}`, {
        data: {
          ...value,
          actor: "RI1 Synthetic Reviewer",
          reason: "Owned synthetic RI1 catalog/source-code scaffolding",
        },
      }),
    );
  }
  const payerOrganization = await catalog("organizations", {
    label: `${prefix} payer organization`,
    kind: "payer",
  });
  const clinicOrganization = await catalog("organizations", {
    label: `${prefix} clinic organization`,
    kind: "clinic",
  });
  const cedar = await catalog("networks", {
    label: `CEDAR ${prefix}`,
    payer_organization_id: payerOrganization.id,
  });
  const pine = await catalog("networks", {
    label: `PINE ${prefix}`,
    payer_organization_id: payerOrganization.id,
  });
  const north = await catalog("locations", {
    label: `NORTH ${prefix}`,
    organization_id: clinicOrganization.id,
  });
  const south = await catalog("locations", {
    label: `SOUTH ${prefix}`,
    organization_id: clinicOrganization.id,
  });
  for (const [kind, source_key, target_id] of [
    ["network", "CEDAR", cedar.id],
    ["network", "PINE", pine.id],
    ["location", "NORTH", north.id],
    ["location", "SOUTH", south.id],
    ["organization", "CLINIC", clinicOrganization.id],
  ])
    await catalog("bindings", {
      source: sources.payer,
      kind,
      source_key,
      target_id,
    });
  let clinic: Receipt, payer: Receipt, native: Receipt;
  let managedFeedId: string, managedVersionId: string;
  await test.step("Upload the clinic roster and review a real immutable normalization recipe", async () => {
    await page.goto("/?view=intake");
    clinic = await uploadUI(page, sources.clinic, labels.clinic, clinicBytes, "flat", "connected-operations");
    expect(clinic.observations).toHaveLength(0);
    await page
      .getByRole("button", { name: "Profile and normalize", exact: true })
      .click();
    const panel = page.getByRole("region", {
      name: "Profile and normalization",
      exact: true,
    });
    await panel
      .getByRole("button", {
        name: "Use suggested normalization columns",
        exact: true,
      })
      .click();
    for (const [field, operation] of [
      ["phone", "phone_us"],
      ["state", "state_us"],
      ["zip", "zip_us"],
    ])
      await panel
        .getByLabel(`${field} format`, { exact: true })
        .selectOption(operation);
    await panel
      .getByRole("button", { name: "Preview normalization", exact: true })
      .click();
    await expect(
      panel.getByText("2 valid · 0 quarantined · 2 total", { exact: true }),
    ).toBeVisible();
    await panel.getByText("Sample row 1 · Valid", { exact: true }).click();
    await expect(
      panel
        .locator("pre")
        .filter({ hasText: '"phone_extension": "004"' })
        .first(),
    ).toBeVisible();
    await panel
      .getByLabel("Recipe name", { exact: true })
      .fill(`${prefix} explicit clinic phones/state/ZIP`);
    await panel
      .getByLabel("Recipe reviewer", { exact: true })
      .fill("RI1 Synthetic Reviewer");
    await panel
      .getByLabel("Recipe decision reason", { exact: true })
      .fill(
        "Reviewed original US phone extension, state and leading-zero ZIP values",
      );
    await panel
      .getByRole("button", { name: "Save proposed recipe", exact: true })
      .click();
    await expect(
      panel.getByText(
        "Proposed revision saved. Review it, then explicitly approve.",
        { exact: true },
      ),
    ).toBeVisible();
    await panel
      .getByRole("button", { name: "Approve recipe", exact: true })
      .click();
    await expect(
      panel.getByText(
        "Approved recipe saved. Apply it to create a new interpretation.",
        { exact: true },
      ),
    ).toBeVisible();
    await panel
      .getByRole("button", { name: "Apply approved recipe", exact: true })
      .click();
    await expect(
      panel.getByRole("button", { name: "Profile and normalize", exact: true }),
    ).toHaveAttribute("aria-expanded", "false");
    clinic = await body(await page.request.get(`/api/intakes/${clinic.id}`));
    expect(clinic.observations).toHaveLength(0);
    expect(clinic.preview.valid_count).toBe(2);
    await page
      .getByLabel("Reviewer", { exact: true })
      .first()
      .fill("RI1 Synthetic Reviewer");
    await page
      .getByLabel("Acceptance / rejection reason", { exact: true })
      .fill(
        "Accept these two reviewed clinic interpretations; source values remain retained",
      );
    const accepted = page.waitForResponse(
      (response) =>
        response.url().endsWith(`/api/intakes/${clinic.id}/commit`) &&
        response.request().method() === "POST",
    );
    await page
      .getByRole("button", { name: "Accept valid rows", exact: true })
      .click();
    await body(await accepted);
    const dataset = await body(
      await page.request.get(`/api/intakes/${clinic.id}/dataset`),
    );
    expect(dataset.records).toHaveLength(2);
    expect(dataset.records[0].normalized).toMatchObject({
      phone: "2125550101",
      phone_extension: "004",
      zip: "02108-0042",
      state: "MA",
    });
    expect(dataset.records[0].original["Office tel"]).toBe(
      " +1 (212) 555-0101 ext 004 ",
    );
    clinic = await body(await page.request.get(`/api/intakes/${clinic.id}`));
    await page.screenshot({
      path: info.outputPath("ri1-normalization-accepted.png"),
      fullPage: true,
    });
  });
  await test.step("Continue a managed baseline through held delivery, approval and exact retained evidence", async () => {
    const attribution = { actor: "RI1 Synthetic Reviewer", reason: "Reviewed connected managed-feed journey" };
    const recipes = await body(await page.request.get("/api/feeds/recipes"));
    const recipe = recipes.items.find((item: { source: string }) => item.source === sources.clinic);
    expect(recipe).toBeTruthy();
    const inbox = await mkdtemp(join(tmpdir(), "pdtl-connected-feed-"));
    let feed = await body(await page.request.post("/api/feeds", { data: { ...attribution, name: `${prefix} connected clinic`, source: sources.clinic, scope: "connected-operations", owner: "Synthetic coordinator", inbox, start_date: "2026-10-05" } }));
    managedFeedId = feed.id;
    const contract = await body(await page.request.post(`/api/feeds/${feed.id}/contracts`, { data: { ...attribution, definition: { recipe_revision_id: recipe.id, required_headers: Object.values(recipe.definition.mapping) } } }));
    const approvedContract = await body(await page.request.post(`/api/feeds/${feed.id}/contracts/${contract.id}/approve`, { data: attribution }));
    feed = await body(await page.request.get(`/api/feeds/${feed.id}`));
    await body(await page.request.post(`/api/feeds/${feed.id}/configure`, { data: { ...attribution, expected_revision: feed.revision, config: { enabled: true, contract_id: approvedContract.id } } }));
    async function deliver(bytes: Buffer, id: string, period: string) {
      const filename = `${prefix}-managed-${id}.csv`;
      await writeFile(join(inbox, filename), bytes);
      await writeFile(join(inbox, `${id}.manifest.json`), JSON.stringify({ delivery_id: id, period, as_of: period, snapshot: "full", filename, sha256: createHash("sha256").update(bytes).digest("hex") }));
      return filename;
    }
    const lines = clinicBytes.toString("utf8").trimEnd().split("\n");
    const changedNorth = lines[1].replace("555-0101", "555-0103");
    expect(changedNorth).not.toBe(lines[1]);
    await deliver(clinicBytes, "baseline", "2026-10-05");
    await page.goto(`/?view=feeds&feed=${feed.id}`);
    await page.getByLabel("Reviewer", { exact: true }).fill(attribution.actor);
    await page.getByLabel("Decision reason", { exact: true }).fill(attribution.reason);
    await page.getByRole("button", { name: "Check deliveries and process one job" }).click();
    await expect(page.getByText("Delivery check completed. Review the job and candidate results below.", { exact: true })).toBeVisible();
    feed = await body(await page.request.get(`/api/feeds/${feed.id}`));
    const baselineId = feed.versions.at(-1).id;
    await page.getByRole("button").filter({ has: page.locator("code", { hasText: baselineId }) }).click();
    await page.getByRole("button", { name: "Approve dataset version", exact: true }).click();
    await expect(page.getByRole("heading", { name: "Dataset review · approved" })).toBeVisible();
    const baselineExport = await (await page.request.get(`/api/feed-versions/${baselineId}/export`)).text();
    // NORTH's changed phone arrives without SOUTH. A partial delivery is not a closure.
    await deliver(Buffer.from([lines[0], changedNorth].join("\n") + "\n"), "partial", "2026-10-12");
    await page.getByRole("button", { name: "Check deliveries and process one job" }).click();
    await expect(page.getByText("Delivery check completed. Review the job and candidate results below.", { exact: true })).toBeVisible();
    feed = await body(await page.request.get(`/api/feeds/${feed.id}`));
    const partialVersionId = feed.versions.at(-1).id;
    await page.getByRole("button").filter({ has: page.locator("code", { hasText: partialVersionId }) }).click();
    await expect(page.getByRole("button", { name: "Approve dataset version", exact: true })).toBeDisabled();
    expect((await body(await page.request.get(`/api/feeds/${feed.id}/current`))).version_id).toBe(baselineId);
    expect(await (await page.request.get(`/api/feed-versions/${baselineId}/export`)).text()).toBe(baselineExport);
    const partialVersion = await body(await page.request.get(`/api/feed-versions/${partialVersionId}`));
    expect(partialVersion.report.counts.raw).toBe(1);
    expect(partialVersion.report.comparison.missing_from_this_delivery).toBe(1);
    expect(partialVersion.report.findings.some((item: {code:string; severity:string}) => item.code === 'row_count_drift' && item.severity === 'hold')).toBe(true);
    await page.screenshot({ path: info.outputPath("connected-held-version.png"), fullPage: true });
    await page.getByRole("button", { name: "Reject candidate", exact: true }).click();
    await expect(page.getByRole("heading", { name: "Dataset review · rejected" })).toBeVisible();
    expect((await body(await page.request.get(`/api/feeds/${feed.id}/current`))).version_id).toBe(baselineId);
    // Corrected full delivery retains the changed NORTH phone and SOUTH source row.
    labels.clinic = await deliver(Buffer.from([lines[0], changedNorth, lines[2]].join("\n") + "\n"), "corrected", "2026-10-19");
    await page.getByRole("button", { name: "Check deliveries and process one job" }).click();
    await expect(page.getByText("Delivery check completed. Review the job and candidate results below.", { exact: true })).toBeVisible();
    feed = await body(await page.request.get(`/api/feeds/${feed.id}`));
    managedVersionId = feed.versions.at(-1).id;
    await page.getByRole("button").filter({ has: page.locator("code", { hasText: managedVersionId }) }).click();
    await page.getByRole("button", { name: "Approve dataset version", exact: true }).click();
    await expect(page.getByRole("heading", { name: "Dataset review · approved" })).toBeVisible();
    const version = await body(await page.request.get(`/api/feed-versions/${managedVersionId}`));
    clinic = await body(await page.request.get(`/api/intakes/${version.manifest.receipt_id}`));
    expect(clinic.attempt_id).toBe(version.manifest.attempt_id);
    expect(clinic.observations).toHaveLength(2);
    await page.getByRole("region", { name: "Dataset review · approved", exact: true }).screenshot({ path: info.outputPath("connected-approved-version.png") });
    await page.goto(`/?view=feeds&feed=${feed.id}&version=${baselineId}`);
    await expect(page.getByRole("heading", { name: "Dataset review · approved" })).toBeVisible();
    await page.getByRole("button").filter({ has: page.locator("code", { hasText: managedVersionId }) }).click();
    await expect(page.getByRole("heading", { name: "Dataset review · approved" })).toBeVisible();
    const bookmark = page.url();
    await page.goBack();
    await expect(page.getByRole("heading", { name: "Dataset review · approved" })).toBeVisible();
    expect(new URL(page.url()).searchParams.get("version")).toBe(baselineId);
    await page.goForward();
    await expect(page.getByRole("heading", { name: "Dataset review · approved" })).toBeVisible();
    expect(new URL(page.url()).searchParams.get("version")).toBe(managedVersionId);
    await page.reload();
    await expect(page.getByRole("heading", { name: "Dataset review · approved" })).toBeVisible();
    expect(page.url()).toBe(bookmark);
    await page.getByRole("link", { name: "Inspect this version's retained evidence", exact: true }).click();
    await expect(page.getByRole("region", { name: "Pinned delivery evidence" })).toBeVisible();
    expect(new URL(page.url()).searchParams.get("attempt")).toBe(clinic.attempt_id);
    await expect(page.getByRole("button", { name: "Accept valid rows", exact: true })).toHaveCount(0);
    expect(await (await page.request.get(`/api/feed-versions/${baselineId}/export`)).text()).toBe(baselineExport);
    await page.goto("/?view=intake");
  });
  await test.step("Review payer source-code bindings and retain a genuine multi-address NPPES-shaped response", async () => {
    payer = await uploadUI(page, sources.payer, labels.payer, payerBytes);
    const mapping = page.getByText("Column mapping and parsing", {
      exact: true,
    });
    if ((await mapping.locator("..").getAttribute("open")) === null)
      await mapping.click();
    const roster = page.getByRole("region", {
      name: "Roster configuration",
      exact: true,
    });
    await roster
      .getByRole("combobox", { name: "Roster kind", exact: true })
      .selectOption("network");
    for (const code of ["CEDAR", "PINE", "NORTH", "SOUTH", "CLINIC"])
      await roster
        .getByRole("checkbox", { name: new RegExp(`^${code} →`) })
        .check();
    const mapped = page.waitForResponse(
      (response) =>
        response.url().endsWith(`/api/intakes/${payer.id}/mapping`) &&
        response.request().method() === "POST",
    );
    await page
      .getByRole("button", { name: "Save mapping and reprocess", exact: true })
      .click();
    payer = await body(await mapped);
    expect(payer.preview.valid_count).toBe(3);
    expect(payer.preview.quarantined_count).toBe(1);
    expect(payer.observations).toHaveLength(0);
    native = await uploadUI(
      page,
      sources.native,
      labels.native,
      nativeBytes,
      "nppes",
    );
    expect(native.preview.rows[0].original).toMatchObject({
      number: 1000000001,
      enumeration_type: "NPI-1",
    });
    expect(native.preview.rows[0].original.addresses as unknown[]).toHaveLength(
      3,
    );
    expect(native.observations).toHaveLength(0);
  });
  let runId = "",
    clinicianId = "",
    proposalId = "",
    confirmationId = "";
  let allCandidates: Candidate[] = [];
  let workAfterConfirmation: unknown;
  async function approveUI(
    candidate: Candidate,
    targetId: string | undefined,
    newLabel: string | undefined,
    reason: string,
  ) {
    const card = page
      .locator(".rc-candidate")
      .filter({ hasText: candidate.id });
    if ((await card.getAttribute("open")) === null)
      await card.locator(":scope > summary").click();
    const label =
      candidate.kind === "clinician" ? "clinician" : "practice location";
    const lazy = card.getByRole("button", {
      name: `Review ${label} link`,
      exact: true,
    });
    if (await lazy.count()) await lazy.click();
    else
      await card
        .getByRole("button", { name: "Refresh review snapshot", exact: true })
        .click();
    const review = card.getByRole("region", {
      name: `${label} link review`,
      exact: true,
    });
    await review
      .getByLabel("Link decision", { exact: true })
      .selectOption("approve");
    if (targetId) {
      await review
        .getByLabel("Target selection", { exact: true })
        .selectOption("existing");
      await review
        .getByLabel(`Find ${label} target`, { exact: true })
        .fill(targetId);
      await review
        .getByLabel(`Target ${label}`, { exact: true })
        .selectOption(targetId);
    } else {
      await review
        .getByLabel("Target selection", { exact: true })
        .selectOption("new");
      await review
        .getByLabel(`New ${label} label`, { exact: true })
        .fill(newLabel!);
    }
    await review
      .getByLabel("Review actor", { exact: true })
      .fill("RI1 Synthetic Reviewer");
    await review.getByLabel("Review reason", { exact: true }).fill(reason);
    await review
      .getByRole("checkbox", { name: /I reviewed both source assertions/ })
      .check();
    await expect.poll(() => page.evaluate(() =>
      document.documentElement.scrollWidth <= window.innerWidth + 1,
    )).toBe(true);
    const saved = page.waitForResponse(
      (response) =>
        response.url().endsWith("/api/reconciliation/links") &&
        response.request().method() === "POST",
    );
    await review
      .getByRole("button", { name: "Save link decision", exact: true })
      .click();
    const result = await body(await saved);
    await expect(
      review.getByText(`Approved ${label} link saved for both references.`, {
        exact: true,
      }),
    ).toBeVisible();
    return result.decision.target_id as string;
  }
  await test.step("Inspect shared comparison evidence and explicitly review clinician and location links", async () => {
    await page.goto(`/?view=feeds&feed=${managedFeedId}&version=${managedVersionId}`);
    await page.getByRole("link", { name: "Prepare reconciliation from this approved version", exact: true }).click();
    await expect(page.getByRole("complementary", { name: "Approved delivery context" })).toBeVisible();
    for (const label of Object.values(labels)) {
      const sourceCheckbox = page.getByRole("checkbox", { name: new RegExp(label.replaceAll(".", "\\.")) });
      if (label === labels.clinic) await expect(sourceCheckbox).toBeChecked();
      else await sourceCheckbox.check();
      await page
        .getByLabel(`Entity type for ${label}`, { exact: true })
        .selectOption("clinician");
    }
    await page
      .getByRole("button", {
        name: `Inspect quality: ${labels.native}`,
        exact: true,
      })
      .click();
    await expect(page.getByText(/3 address references · Rule/)).toBeVisible();
    await expect(page.getByText(/mailing excluded/)).toBeVisible();
    await page
      .getByText(/Inspect source record 2 · Alex RI1 Synthetic/)
      .click();
    await expect(page.getByText(/Address path addresses\[1\]/)).toBeVisible();
    await page
      .getByLabel("Run reviewer", { exact: true })
      .fill("RI1 Synthetic Reviewer");
    await page
      .getByLabel("Run reason", { exact: true })
      .fill(
        "Explicit clinic/payer/native NPPES sources, retaining unlinked and mailing evidence",
      );
    const created = page.waitForResponse(
      (response) =>
        response.url().endsWith("/api/reconciliation/runs") &&
        response.request().method() === "POST",
    );
    await page
      .getByRole("button", { name: "Create candidate run", exact: true })
      .click();
    const run = await body(await created);
    runId = run.id;
    const pageData = await body(
      await page.request.get(
        `/api/reconciliation/runs/${runId}/candidates?limit=100`,
      ),
    );
    allCandidates = pageData.items;
    await writeFile(
      info.outputPath("ri1-run-and-candidates.json"),
      JSON.stringify({ run, candidates: pageData }, null, 2),
    );
    expect(run.metrics.candidate_count).toBe(21);
    // An operator can search, hand off the exact subset, and resume the same run.
    const workBeforeSearch = await body(await page.request.get('/api/work'));
    await page.getByLabel('Find a provider or identifier').fill('1000000001');
    await page.getByRole('button', { name: 'Search candidates', exact: true }).click();
    await expect(page.getByRole('status').filter({ hasText: 'Applied search: 1000000001' })).toBeVisible();
    const handoff = page.waitForEvent('download');
    await page.getByRole('link', { name: 'Download filtered candidate evidence (JSON)' }).click();
    const handoffJson = JSON.parse(await readFile((await (await handoff).path())!, 'utf8'));
    expect(handoffJson.scope.search).toBe('1000000001');
    expect(handoffJson.total).toBeGreaterThan(0);
    expect(handoffJson.candidates).toHaveLength(handoffJson.total);
    expect(handoffJson.records.length).toBeGreaterThan(0);
    await page.reload();
    await expect(page.getByLabel('Saved candidate run', { exact: true })).toHaveValue(runId);
    await expect(page.getByLabel('Find a provider or identifier')).toHaveValue('1000000001');
    await expect(page.getByRole('status').filter({ hasText: 'Applied search: 1000000001' })).toBeVisible();
    expect(await body(await page.request.get('/api/work'))).toEqual(workBeforeSearch);
    await page.getByRole('button', { name: 'Clear search', exact: true }).click();
    await expect(page.getByRole('status').filter({ hasText: 'Applied search: 1000000001' })).toHaveCount(0);
    for (const candidate of allCandidates.filter(
      (candidate) => candidate.kind === "location",
    ))
      for (const record of [candidate.left_record, candidate.right_record])
        expect(record.comparison.address.kind).toBe("practice");
    const personPairs = allCandidates.filter(
      (candidate) =>
        candidate.kind === "clinician" &&
        (candidate.left_record.source === sources.native ||
          candidate.right_record.source === sources.native),
    );
    expect(personPairs).toHaveLength(5);
    for (const candidate of personPairs)
      clinicianId = await approveUI(
        candidate,
        clinicianId || undefined,
        `${prefix} reviewed clinician`,
        "Reviewed exact clinician identity evidence; offices and network assertions remain separately scoped",
      );
    await page
      .getByLabel("Candidate type", { exact: true })
      .selectOption("location");
    const locationPairs = allCandidates.filter(
      (candidate) =>
        candidate.kind === "location" &&
        (candidate.left_record.source === sources.native ||
          candidate.right_record.source === sources.native) &&
        Boolean(candidate.left_record.comparison.npi) &&
        Boolean(candidate.right_record.comparison.npi),
    );
    expect(locationPairs).toHaveLength(5);
    for (const candidate of locationPairs) {
      const target = candidate.left_record.comparison.address.line1.startsWith(
        "10 ",
      )
        ? north.id
        : south.id;
      await approveUI(
        candidate,
        target,
        undefined,
        "Reviewed the exact practice path and suite; mailing evidence does not establish an operating office",
      );
    }
    const unresolved = allCandidates.find(
      (candidate) =>
        candidate.kind === "location" &&
        (!candidate.left_record.comparison.npi ||
          !candidate.right_record.comparison.npi),
    )!;
    expect(unresolved).toBeTruthy();
    const card = page
      .locator(".rc-candidate")
      .filter({ hasText: unresolved.id });
    await card.locator(":scope > summary").click();
    await card
      .getByRole("button", {
        name: "Review practice location link",
        exact: true,
      })
      .click();
    const review = card.getByRole("region", {
      name: "practice location link review",
      exact: true,
    });
    await review
      .getByLabel("Link decision", { exact: true })
      .selectOption("defer");
    await review
      .getByLabel("Review actor", { exact: true })
      .fill("RI1 Synthetic Reviewer");
    await review
      .getByLabel("Review reason", { exact: true })
      .fill(
        "Leave this source row unresolved for later review; no clinician crosswalk has been approved",
      );
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
  });
  async function openFieldScope() {
    const openFields = page.getByRole("button", { name: "Open reconciled field evidence", exact: true });
    if (await openFields.count()) await openFields.click();
    const panel = page.getByRole("region", {
      name: "Reconciled field evidence",
      exact: true,
    });
    await panel
      .getByLabel("Find reviewed clinician", { exact: true })
      .fill(clinicianId);
    await panel
      .getByLabel("Reviewed clinician", { exact: true })
      .selectOption(clinicianId);
    await panel
      .getByLabel("Include a reviewed practice location", { exact: true })
      .check();
    await panel
      .getByLabel("Find reviewed practice location", { exact: true })
      .fill(north.id);
    await panel
      .getByLabel("Reviewed practice location", { exact: true })
      .selectOption(north.id);
    return panel;
  }
  let fields: ReturnType<Page["getByRole"]>,
    impact: ReturnType<Page["getByRole"]>,
    followUp: ReturnType<Page["getByRole"]>;
  await test.step("Reconcile NORTH evidence explicitly and inspect the complete native/source-preserving field export", async () => {
    fields = await openFieldScope();
    await expect(
      fields.getByText(/3 contributing sources · 4 approved source records/),
    ).toBeVisible();
    const view = await body(
      await page.request.get(
        `/api/reconciliation/fields/${clinicianId}?location_id=${north.id}`,
      ),
    );
    expect(view.records).toHaveLength(4);
    expect(
      view.records.every(
        (record: {
          comparison: { address: { line1: string; kind: string } };
        }) =>
          record.comparison.address.line1.startsWith("10 ") &&
          record.comparison.address.kind === "practice",
      ),
    ).toBe(true);
    const phone = fields.getByRole("region", {
      name: "phone reconciliation",
      exact: true,
    });
    const clinicOption = view.fields
      .find((field: { field: string }) => field.field === "phone")
      .options.find(
        (option: { source: string }) => option.source === sources.clinic,
      );
    await phone
      .getByLabel("Decision for phone", { exact: true })
      .selectOption("select");
    await phone
      .getByRole("radio", {
        name: `Choose phone from ${sources.clinic} ${clinicOption.ref}`,
        exact: true,
      })
      .check();
    await phone
      .getByLabel("Actor for phone", { exact: true })
      .fill("RI1 Synthetic Reviewer");
    await phone
      .getByLabel("Reason for phone", { exact: true })
      .fill(
        "Explicit clinic phone preference with retained original extension syntax",
      );
    await phone
      .getByLabel("I reviewed phone source evidence", { exact: true })
      .check();
    await phone
      .getByRole("button", { name: "Save phone decision", exact: true })
      .click();
    await expect(
      phone.getByText(
        "Selected phone source assertion saved. Source observations were preserved.",
        { exact: true },
      ),
    ).toBeVisible();
    await phone
      .getByLabel("Decision for phone", { exact: true })
      .selectOption("conflict");
    await phone
      .getByLabel("Reason for phone", { exact: true })
      .fill(
        "Keep the clinic/payer NORTH phone discrepancy explicit until the proposed change is reviewed",
      );
    await phone
      .getByLabel("I reviewed phone source evidence", { exact: true })
      .check();
    await phone
      .getByRole("button", { name: "Save phone decision", exact: true })
      .click();
    await expect(
      phone.getByText(
        "Explicit phone conflict saved. Source observations were preserved.",
        { exact: true },
      ),
    ).toBeVisible();
    const address = fields.getByRole("region", {
      name: "address reconciliation",
      exact: true,
    });
    const option = view.fields
      .find((field: { field: string }) => field.field === "address")
      .options.find(
        (option: { source: string }) => option.source === sources.clinic,
      );
    await address
      .getByLabel("Decision for address", { exact: true })
      .selectOption("select");
    await address
      .getByRole("radio", {
        name: `Choose address from ${sources.clinic} ${option.ref}`,
        exact: true,
      })
      .check();
    await address
      .getByLabel("Actor for address", { exact: true })
      .fill("RI1 Synthetic Reviewer");
    await address
      .getByLabel("Reason for address", { exact: true })
      .fill(
        "Choose the coherent NORTH clinic address, preserving Suite 04 and ZIP+4",
      );
    await address
      .getByLabel("I reviewed address source evidence", { exact: true })
      .check();
    await address
      .getByRole("button", { name: "Save address decision", exact: true })
      .click();
    await expect(
      address.getByText(
        "Selected address source assertion saved. Source observations were preserved.",
        { exact: true },
      ),
    ).toBeVisible();
    const data = await downloadJSON(
      page,
      fields.getByRole("button", {
        name: "Download reconciled JSON",
        exact: true,
      }),
      info.outputPath("ri1-fields.json"),
    );
    expect(data.scope).toEqual({
      clinician_id: clinicianId,
      location_id: north.id,
    });
    expect(data.records).toHaveLength(4);
    expect(
      data.fields.find((field: { field: string }) => field.field === "phone")
        .status,
    ).toBe("conflict");
    expect(
      data.source_context.find(
        (item: { receipt: { profile: string } }) =>
          item.receipt.profile === "nppes",
      ).row.original.addresses,
    ).toHaveLength(3);
    const workbook = await downloadWorkbook(
      page,
      fields.getByRole("button", {
        name: "Download reconciled XLSX",
        exact: true,
      }),
      info.outputPath("ri1-fields.xlsx"),
    );
    expect(workbook.payload).toEqual(data);
    expect(workbook.formulas).toBe(0);
    await phone.screenshot({
      path: info.outputPath("ri1-NORTH-field-evidence.png"),
    });
  });
  await test.step("Propose a NORTH phone change and preview named payer networks with SOUTH/unlinked exclusions", async () => {
    await fields
      .getByRole("button", { name: "Open change impact preview", exact: true })
      .click();
    impact = page.getByRole("region", {
      name: "Provider-change impact preview",
      exact: true,
    });
    await impact
      .getByLabel("Proposed field", { exact: true })
      .selectOption("phone");
    await impact
      .getByLabel("Proposed phone number", { exact: true })
      .fill("2125550111");
    await impact
      .getByLabel("Proposed phone extension", { exact: true })
      .fill("004");
    await impact
      .getByLabel(`Assess delivery ${labels.payer}`, { exact: true })
      .check();
    await impact
      .getByLabel("Proposal actor", { exact: true })
      .fill("RI1 Synthetic Reviewer");
    await impact
      .getByLabel("Proposal reason", { exact: true })
      .fill(
        "Propose NORTH phone review for explicitly selected CEDAR/PINE listings; preserve SOUTH and unresolved evidence",
      );
    await impact
      .getByLabel("I reviewed the prior field and assessment inputs", {
        exact: true,
      })
      .check();
    const created = page.waitForResponse(
      (response) =>
        response.url().endsWith("/api/reconciliation/change-proposals") &&
        response.request().method() === "POST",
    );
    await impact
      .getByRole("button", { name: "Save change proposal", exact: true })
      .click();
    proposalId = (await body(await created)).id;
    const assessed = page.waitForResponse(
      (response) =>
        response.url().endsWith("/api/reconciliation/impact-preview") &&
        response.request().method() === "POST",
    );
    await impact
      .getByRole("button", {
        name: "Run read-only impact preview",
        exact: true,
      })
      .click();
    const assessment = await body(await assessed);
    expect(assessment.counts).toEqual({
      affected: 2,
      unaffected_within_assessed_scope: 1,
      not_assessed: 1,
    });
    expect(
      assessment.targets
        .filter(
          (target: { classification: string }) =>
            target.classification === "affected",
        )
        .map((target: { network_id: string }) => target.network_id)
        .sort(),
    ).toEqual([cedar.id, pine.id].sort());
    expect(
      assessment.targets.find(
        (target: { value: { number: string } }) =>
          target.value.number === "2125550102",
      ).classification,
    ).toBe("unaffected_within_assessed_scope");
    expect(
      assessment.targets.find(
        (target: { value: { number: string } }) =>
          target.value.number === "2125550188",
      ).classification,
    ).toBe("not_assessed");
    await writeFile(
      info.outputPath("ri1-impact.json"),
      JSON.stringify(assessment, null, 2),
    );
    await impact
      .getByRole("region", { name: "Impact assessment results", exact: true })
      .screenshot({ path: info.outputPath("ri1-impact-coverage.png") });
  });
  await test.step("Confirm two QA follow-ups explicitly, acknowledge one independently, and inspect the complete handoff", async () => {
    const workBefore = await body(await page.request.get("/api/work"));
    await impact
      .getByRole("button", { name: "Review follow-up plan", exact: true })
      .click();
    followUp = impact.getByRole("region", {
      name: "Bounded follow-up plan",
      exact: true,
    });
    await followUp
      .getByRole("button", { name: "Preview follow-up actions", exact: true })
      .click();
    await expect(
      followUp.getByText("2 deduplicated follow-up targets · 0 blocked", {
        exact: true,
      }),
    ).toBeVisible();
    await followUp
      .getByLabel("Follow-up actor", { exact: true })
      .fill("RI1 Synthetic Reviewer");
    await followUp
      .getByLabel("Follow-up reason", { exact: true })
      .fill("Confirm bounded review tasks for two known NORTH listings only");
    await followUp
      .getByLabel("I confirm this bounded review-case plan", { exact: true })
      .check();
    const confirmed = page.waitForResponse(
      (response) =>
        response.url().endsWith("/api/reconciliation/follow-up") &&
        response.request().method() === "POST",
    );
    await followUp
      .getByRole("button", { name: "Confirm follow-up plan", exact: true })
      .click();
    confirmationId = (await body(await confirmed)).id;
    await expect(
      followUp.getByText("Saved follow-up receipt", { exact: true }),
    ).toBeVisible();
    const receipt = await body(
      await page.request.get(`/api/reconciliation/follow-up/${confirmationId}`),
    );
    expect(receipt.targets).toHaveLength(2);
    expect(
      receipt.targets.every(
        (target: {
          action: string;
          case: { kind: string; status: string; owner: string | null };
        }) =>
          target.action === "create" &&
          target.case.kind === "qa" &&
          target.case.status === "new" &&
          target.case.owner === null,
      ),
    ).toBe(true);
    const chosen = receipt.targets.find(
      (target: { network_id: string }) => target.network_id === cedar.id,
    );
    const currentCase = await body(
      await page.request.get(`/api/work/${chosen.case.id}`),
    );
    expect(currentCase.scope).toBeNull();
    expect(currentCase.follow_up_scopes).toEqual(
      expect.arrayContaining([
        expect.objectContaining({
          kind: "follow_up",
          network_id: cedar.id,
          practice_location_id: north.id,
          confirmation_id: confirmationId,
        }),
      ]),
    );
    const target = followUp.getByRole("region", {
      name: `Saved follow-up target ${chosen.target_key}`,
      exact: true,
    });
    await target
      .getByLabel("Acknowledgement actor", { exact: true })
      .fill("RI1 Receiving Reviewer");
    await target
      .getByLabel("Acknowledgement reason", { exact: true })
      .fill(
        "Received the CEDAR follow-up for manual review; no correction has been verified",
      );
    await target
      .getByRole("button", { name: "Record acknowledgement", exact: true })
      .click();
    await expect(
      target.getByText(
        "Receipt acknowledgement saved. Verification and case state were not changed.",
        { exact: true },
      ),
    ).toBeVisible();
    expect(
      await body(await page.request.get(`/api/work/${chosen.case.id}`)),
    ).toEqual(currentCase);
    const packet = await downloadJSON(
      page,
      followUp.getByRole("button", {
        name: "Download follow-up JSON",
        exact: true,
      }),
      info.outputPath("ri1-follow-up.json"),
    );
    expect(packet.associations).toHaveLength(2);
    expect(packet.acknowledgements).toHaveLength(1);
    expect(
      packet.cases.every(
        (item: {
          kind: string;
          status: string;
          proposal: unknown;
          observed: unknown;
        }) =>
          item.kind === "qa" &&
          item.status === "new" &&
          item.proposal === null &&
          item.observed === null,
      ),
    ).toBe(true);
    const workbook = await downloadWorkbook(
      page,
      followUp.getByRole("button", {
        name: "Download follow-up XLSX",
        exact: true,
      }),
      info.outputPath("ri1-follow-up.xlsx"),
    );
    expect(workbook.payload).toEqual(packet);
    expect(workbook.formulas).toBe(0);
    await followUp.screenshot({
      path: info.outputPath("ri1-confirmed-acknowledged-handoff.png"),
    });
    await followUp.getByRole("link", { name: "Open work case", exact: true }).first().click();
    await expect(page.getByRole("complementary", { name: "Follow-up context" })).toBeVisible();
    await page.getByRole("link", { name: "Return to change assessment and follow-up receipt", exact: true }).click();
    impact = page.getByRole("region", { name: "Provider-change impact preview", exact: true });
    followUp = impact.getByRole("region", { name: "Bounded follow-up plan", exact: true });
    await expect(followUp.getByText("Saved follow-up receipt", { exact: true })).toBeVisible();

    const currentWork = await body(await page.request.get("/api/work"));
    expect(currentWork.items).toHaveLength(workBefore.items.length + 2);
    workAfterConfirmation = currentWork;
    const payerAfter = await body(
      await page.request.get(`/api/intakes/${payer.id}`),
    );
    const nativeAfter = await body(
      await page.request.get(`/api/intakes/${native.id}`),
    );
    expect(payerAfter.observations).toHaveLength(0);
    expect(nativeAfter.observations).toHaveLength(0);
  });
  await test.step("A real reviewed-link revision stales dependent previews; reload preserves the existing receipt without duplicate work", async () => {
    await page
      .getByLabel("Candidate type", { exact: true })
      .selectOption("location");
    const candidate = allCandidates.find(
      (candidate) =>
        candidate.kind === "location" &&
        (candidate.left_record.source === sources.native ||
          candidate.right_record.source === sources.native) &&
        Boolean(candidate.left_record.comparison.npi) &&
        Boolean(candidate.right_record.comparison.npi) &&
        candidate.left_record.comparison.address.line1.startsWith("10 "),
    )!;
    await approveUI(
      candidate,
      north.id,
      undefined,
      "Explicit repeated NORTH office review to demonstrate dependent snapshot staleness",
    );
    await followUp
      .getByRole("button", {
        name: "Refresh saved follow-up receipt",
        exact: true,
      })
      .click();
    await expect(
      followUp.getByText(
        "Source dependencies have changed since confirmation.",
        { exact: true },
      ),
    ).toBeVisible();
    await impact
      .getByRole("button", {
        name: "Run read-only impact preview",
        exact: true,
      })
      .click();
    await expect(
      impact.getByText("This proposal preview is stale.", { exact: true }),
    ).toBeVisible();
    await followUp.screenshot({
      path: info.outputPath("ri1-stale-historical-receipt.png"),
    });
    expect(await body(await page.request.get("/api/work"))).toEqual(
      workAfterConfirmation,
    );
    await page.reload();
    await expect(
      page.getByLabel("Saved candidate run", { exact: true }),
    ).toHaveValue(runId);
    fields = page.getByRole("region", { name: "Reconciled field evidence", exact: true });
    impact = page.getByRole("region", { name: "Provider-change impact preview", exact: true });
    await expect(impact.getByLabel("Saved change proposal", { exact: true })).toHaveValue(proposalId);
    // Saved follow-up restores through GETs; no new impact preview or confirmation is required.
    followUp = impact.getByRole("region", { name: "Bounded follow-up plan", exact: true });
    await expect(
      followUp.getByText("Saved follow-up receipt", { exact: true }),
    ).toBeVisible();
    await expect(
      followUp.getByRole("button", {
        name: "Confirm follow-up plan",
        exact: true,
      }),
    ).toHaveCount(0);
    await expect(
      followUp.getByText(/Latest acknowledgement: RI1 Receiving Reviewer/),
    ).toBeVisible();
    expect(
      (
        await body(
          await page.request.get(
            `/api/reconciliation/follow-up?proposal_id=${proposalId}`,
          ),
        )
      ).total,
    ).toBe(1);
    expect(await body(await page.request.get("/api/work"))).toEqual(
      workAfterConfirmation,
    );
    expect(
      await page.evaluate(
        () => document.documentElement.scrollWidth <= window.innerWidth + 1,
      ),
    ).toBe(true);
  });
});
