import { expect, test } from "@playwright/test";
import { readFile } from "node:fs/promises";
import { execFileSync } from "node:child_process";

test("confirmed plan creates one QA review, reuses owned work, and records separate acknowledgement with complete exports", async ({
  page,
}, info) => {
  const prefix = `follow-up-${info.project.name}`;
  async function catalog(path: string, payload: Record<string, unknown>) {
    const response = await page.request.post(`/api/catalog/${path}`, {
      data: {
        ...payload,
        actor: "Synthetic Reviewer",
        reason: "Explicit synthetic network follow-up scope",
      },
    });
    expect(response.ok(), await response.text()).toBe(true);
    return response.json();
  }
  const payerOrganization = await catalog("organizations", {
    label: `${prefix} payer`,
    kind: "payer",
  });
  const clinicOrganization = await catalog("organizations", {
    label: `${prefix} clinic`,
    kind: "clinic",
  });
  const network = await catalog("networks", {
    label: `CEDAR ${prefix}`,
    payer_organization_id: payerOrganization.id,
  });
  const north = await catalog("locations", {
    label: `NORTH ${prefix}`,
    organization_id: clinicOrganization.id,
  });
  const bindings: Record<string, Record<string, string>> = {
    network: {},
    location: {},
    organization: {},
  };
  for (const [kind, code, target_id] of [
    ["network", "CEDAR", network.id],
    ["location", "NORTH", north.id],
    ["organization", "CLINIC", clinicOrganization.id],
  ]) {
    const binding = await catalog("bindings", {
      source: `${prefix}-new`,
      kind,
      source_key: code,
      target_id,
    });
    bindings[kind][code] = binding.id;
  }
  const receipts: Record<string, { id: string; attempt_id: string }> = {};
  for (const source of ["clinic", "owned", "new"]) {
    const row = {
      record_id: `${source}-001`,
      npi: "1000000001",
      provider_name: "Alex Followup Synthetic",
      entity_type: "clinician",
      address: "10 Example Street STE 04",
      city: "Boston",
      state: "MA",
      zip: "02108",
      phone: source === "clinic" ? "2125550101" : "2125550199",
      phone_extension: null,
      location_id: "NORTH",
      ...(source === "owned" ? { reference_phone: "2125550111" } : {}),
      ...(source === "new"
        ? {
            network_code: "CEDAR",
            organization_code: "CLINIC",
            participation_status: "listed",
          }
        : {}),
    };
    const headers = Object.keys(row);
    const csv = `${headers.join(",")}\n${headers.map((key) => '"' + String((row as Record<string, unknown>)[key] ?? "").replaceAll('"', '""') + '"').join(",")}\n`;
    const uploaded = await page.request.post(
      `/api/intakes/files?${new URLSearchParams({ filename: `${prefix}-${source}.${source === "new" ? "csv" : "json"}`, source: `${prefix}-${source}`, designation: "synthetic", profile: "flat" })}`,
      {
        data: Buffer.from(source === "new" ? csv : JSON.stringify([row])),
        headers: { "Content-Type": "application/octet-stream" },
      },
    );
    expect(uploaded.ok(), await uploaded.text()).toBe(true);
    receipts[source] = await uploaded.json();
  }
  const networkMapping = await page.request.post(
    `/api/intakes/${receipts.new.id}/mapping`,
    {
      data: {
        roster_kind: "network",
        bindings,
        mapping: Object.fromEntries(
          [
            "record_id",
            "npi",
            "provider_name",
            "address",
            "city",
            "state",
            "zip",
            "phone",
            "location_id",
            "network_code",
            "organization_code",
            "participation_status",
          ].map((field) => [field, field]),
        ),
      },
    },
  );
  expect(networkMapping.ok(), await networkMapping.text()).toBe(true);
  receipts.new = await networkMapping.json();
  const accepted = await page.request.post(
    `/api/intakes/${receipts.owned.id}/commit`,
    {
      data: {
        policy: "valid_rows",
        actor: "Synthetic Reviewer",
        reason: "Create an existing owned source correction fixture",
        expected_attempt: receipts.owned.attempt_id,
      },
    },
  );
  expect(accepted.ok(), await accepted.text()).toBe(true);
  const existingWork = await (await page.request.get("/api/work")).json();
  const old = existingWork.items.find(
    (item: { source: string; field_name: string }) =>
      item.source === `${prefix}-owned` && item.field_name === "phone",
  );
  expect(old).toBeTruthy();
  let oldVersion = old.version;
  for (const event of [
    { action: "assign", owner: "Baseline steward" },
    { action: "triage" },
    { action: "approve", proposal: "2125550123" },
    { action: "submit", submission_reference: "SYNTHETIC-EXISTING" },
  ]) {
    const changed = await page.request.post(`/api/work/${old.id}/events`, {
      data: {
        ...event,
        actor: "Synthetic Reviewer",
        reason: "Preserve this pre-existing work state through follow-up",
        expected_version: oldVersion,
      },
    });
    expect(changed.ok(), await changed.text()).toBe(true);
    oldVersion = (await changed.json()).version;
  }
  const originalWorkState = (value: Record<string, unknown>) => {
    const { follow_up_scopes: _scope, ...original } = value;
    return original;
  };
  const oldCaseBefore = await (
    await page.request.get(`/api/work/${old.id}`)
  ).json();
  expect(oldCaseBefore.status).toBe("pending_verification");
  expect(oldCaseBefore.proposal).toBe("2125550123");
  const runResponse = await page.request.post("/api/reconciliation/runs", {
    data: {
      inputs: Object.values(receipts).map((receipt) => ({
        receipt_id: receipt.id,
        attempt_id: receipt.attempt_id,
        entity_kind: "clinician",
      })),
      actor: "Synthetic Reviewer",
      reason: "Three-source explicit follow-up crosswalk fixture",
    },
  });
  expect(runResponse.ok(), await runResponse.text()).toBe(true);
  const run = await runResponse.json();
  const candidates = await (
    await page.request.get(
      `/api/reconciliation/runs/${run.id}/candidates?limit=100`,
    )
  ).json();
  const targets: Record<string, string> = { location: north.id };
  for (const kind of ["clinician", "location"]) {
    for (const candidate of candidates.items.filter(
      (candidate: { kind: string }) => candidate.kind === kind,
    )) {
      const current = await (
        await page.request.get(
          `/api/reconciliation/runs/${run.id}/candidates/${candidate.id}/review`,
        )
      ).json();
      const approved = await page.request.post("/api/reconciliation/links", {
        data: {
          run_id: run.id,
          candidate_id: candidate.id,
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
          reason: `Explicit ${kind} source link`,
          ...(targets[kind]
            ? { target_id: targets[kind] }
            : { new_label: `${prefix} ${kind}` }),
        },
      });
      expect(approved.ok(), await approved.text()).toBe(true);
      targets[kind] = (await approved.json()).decision.target_id;
    }
  }
  let view = await (
    await page.request.get(
      `/api/reconciliation/fields/${targets.clinician}?location_id=${targets.location}`,
    )
  ).json();
  const fieldDecision = await page.request.post(
    "/api/reconciliation/field-decisions",
    {
      data: {
        clinician_id: targets.clinician,
        location_id: targets.location,
        field: "phone",
        decision: "conflict",
        expected_snapshot: view.snapshot,
        expected_decision: null,
        request_id: crypto.randomUUID(),
        actor: "Synthetic Reviewer",
        reason: "Retain original phone conflict",
      },
    },
  );
  expect(fieldDecision.ok(), await fieldDecision.text()).toBe(true);
  view = await (
    await page.request.get(
      `/api/reconciliation/fields/${targets.clinician}?location_id=${targets.location}`,
    )
  ).json();
  const proposed = await page.request.post(
    "/api/reconciliation/change-proposals",
    {
      data: {
        clinician_id: targets.clinician,
        location_id: targets.location,
        field: "phone",
        proposed_value: { number: "2125550111", extension: null },
        inputs: ["owned", "new"].map((source) => ({
          receipt_id: receipts[source].id,
          attempt_id: receipts[source].attempt_id,
          entity_kind: "clinician",
        })),
        expected_snapshot: view.snapshot,
        request_id: crypto.randomUUID(),
        actor: "Synthetic Reviewer",
        reason: "Bounded follow-up for two known source listings",
      },
    },
  );
  expect(proposed.ok(), await proposed.text()).toBe(true);
  const proposal = await proposed.json();
  const workBefore = await (await page.request.get("/api/work")).json();
  async function openSavedScope() {
    if (new URL(page.url()).searchParams.get("followup")) {
      const saved = page.getByRole("region", { name: "Bounded follow-up plan", exact: true });
      await expect(saved.getByText("Saved follow-up receipt", { exact: true })).toBeVisible();
      return saved;
    }
    const openFields = page.getByRole("button", { name: "Open reconciled field evidence", exact: true });
    if (await openFields.count()) await openFields.click();
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
      .fill(targets.location);
    await fields
      .getByLabel("Reviewed practice location", { exact: true })
      .selectOption(targets.location);
    await fields
      .getByRole("button", { name: "Open change impact preview", exact: true })
      .click();
    const impact = page.getByRole("region", {
      name: "Provider-change impact preview",
      exact: true,
    });
    await impact
      .getByLabel("Saved change proposal", { exact: true })
      .selectOption(proposal.id);
    await impact
      .getByRole("button", {
        name: "Run read-only impact preview",
        exact: true,
      })
      .click();
    await impact
      .getByRole("button", { name: "Review follow-up plan", exact: true })
      .click();
    return impact.getByRole("region", {
      name: "Bounded follow-up plan",
      exact: true,
    });
  }
  await page.goto("/?view=reconciliation");
  let panel = await openSavedScope();
  await panel
    .getByRole("button", { name: "Preview follow-up actions", exact: true })
    .click();
  await expect(
    panel.getByText("2 deduplicated follow-up targets · 0 blocked", {
      exact: true,
    }),
  ).toBeVisible();
  await expect(
    panel.getByText(
      /Current owner Baseline steward · Work state pending verification/,
    ),
  ).toBeVisible();
  await panel.screenshot({
    path: info.outputPath("follow-up-create-and-reuse-preview.png"),
  });
  expect(await (await page.request.get("/api/work")).json()).toEqual(
    workBefore,
  );
  await panel
    .getByLabel("Follow-up actor", { exact: true })
    .fill("Synthetic Reviewer");
  await panel
    .getByLabel("Follow-up reason", { exact: true })
    .fill(
      "Confirm bounded QA review while preserving existing owned correction",
    );
  await panel
    .getByLabel("I confirm this bounded review-case plan", { exact: true })
    .check();
  const confirmedResponse = page.waitForResponse(
    (response) =>
      response.url().endsWith("/api/reconciliation/follow-up") &&
      response.request().method() === "POST",
  );
  await panel
    .getByRole("button", { name: "Confirm follow-up plan", exact: true })
    .click();
  const confirmedRaw = await confirmedResponse;
  expect(confirmedRaw.ok(), await confirmedRaw.text()).toBe(true);
  const confirmed = await confirmedRaw.json();
  const posted = confirmedRaw.request().postDataJSON();
  await expect(
    panel.getByText("Saved follow-up receipt", { exact: true }),
  ).toBeVisible();
  const receipt = await (
    await page.request.get(`/api/reconciliation/follow-up/${confirmed.id}`)
  ).json();
  expect(receipt.targets).toHaveLength(2);
  expect(
    receipt.targets.map((target: { action: string }) => target.action).sort(),
  ).toEqual(["create", "reuse"]);
  const reused = receipt.targets.find(
    (target: { action: string }) => target.action === "reuse",
  );
  const created = receipt.targets.find(
    (target: { action: string }) => target.action === "create",
  );
  expect(reused.case.id).toBe(old.id);
  expect(created.case.kind).toBe("qa");
  expect(created.case.status).toBe("new");
  expect(created.case.owner).toBeNull();
  const newCaseDetail = await (
    await page.request.get(`/api/work/${created.case.id}`)
  ).json();
  expect(newCaseDetail.scope).toBeNull();
  expect(newCaseDetail.follow_up_scopes).toEqual(
    expect.arrayContaining([
      expect.objectContaining({
        kind: "follow_up",
        network_id: network.id,
        practice_location_id: north.id,
        clinician_id: targets.clinician,
        confirmation_id: confirmed.id,
      }),
    ]),
  );
  const networkWork = await (
    await page.request.get(
      `/api/work?network_id=${network.id}&location_id=${north.id}`,
    )
  ).json();
  expect(networkWork.items.map((item: { id: string }) => item.id)).toContain(
    created.case.id,
  );

  expect(
    originalWorkState(
      await (await page.request.get(`/api/work/${old.id}`)).json(),
    ),
  ).toEqual(originalWorkState(oldCaseBefore));
  const workAfter = await (await page.request.get("/api/work")).json();
  expect(workAfter.items).toHaveLength(workBefore.items.length + 1);
  const repeated = await page.request.post("/api/reconciliation/follow-up", {
    data: { ...posted, request_id: crypto.randomUUID() },
  });
  expect(repeated.ok(), await repeated.text()).toBe(true);
  expect((await repeated.json()).id).toBe(confirmed.id);
  expect(await (await page.request.get("/api/work")).json()).toEqual(workAfter);
  const reusedSection = panel.getByRole("region", {
    name: `Saved follow-up target ${reused.target_key}`,
    exact: true,
  });
  await reusedSection
    .getByLabel("Acknowledgement actor", { exact: true })
    .fill("Synthetic Receiver");
  await reusedSection
    .getByLabel("Acknowledgement reason", { exact: true })
    .fill("Received this follow-up for review; correction remains unverified");
  const ackResponse = page.waitForResponse(
    (response) =>
      response
        .url()
        .endsWith(
          `/api/reconciliation/follow-up/${confirmed.id}/acknowledge`,
        ) && response.request().method() === "POST",
  );
  await reusedSection
    .getByRole("button", { name: "Record acknowledgement", exact: true })
    .click();
  const ackRaw = await ackResponse;
  expect(ackRaw.ok(), await ackRaw.text()).toBe(true);
  await expect(
    reusedSection.getByText(
      "Receipt acknowledgement saved. Verification and case state were not changed.",
      { exact: true },
    ),
  ).toBeVisible();
  expect(
    originalWorkState(
      await (await page.request.get(`/api/work/${old.id}`)).json(),
    ),
  ).toEqual(originalWorkState(oldCaseBefore));
  await reusedSection
    .getByText("Acknowledgement history · 1", { exact: true })
    .click();
  await expect(
    reusedSection.getByText("1 recorded acknowledgements", { exact: true }),
  ).toBeVisible();
  await panel.screenshot({
    path: info.outputPath("follow-up-saved-receipt-acknowledgement.png"),
  });
  const jsonPromise = page.waitForEvent("download");
  await panel
    .getByRole("button", { name: "Download follow-up JSON", exact: true })
    .click();
  const jsonPath = info.outputPath("follow-up-plan.json");
  await (await jsonPromise).saveAs(jsonPath);
  const exported = JSON.parse(await readFile(jsonPath, "utf8"));
  expect(exported.associations).toHaveLength(2);
  expect(exported.acknowledgements).toHaveLength(1);
  expect(
    exported.cases.find((item: { id: string }) => item.id === old.id).proposal,
  ).toBe("2125550123");
  const xlsxPromise = page.waitForEvent("download");
  await panel
    .getByRole("button", { name: "Download follow-up XLSX", exact: true })
    .click();
  const xlsxPath = info.outputPath("follow-up-plan.xlsx");
  await (await xlsxPromise).saveAs(xlsxPath);
  const inspected = JSON.parse(
    execFileSync(
      "python3",
      [
        "-c",
        `import json,sys\nfrom openpyxl import load_workbook\nw=load_workbook(sys.argv[1],read_only=True,data_only=False)\nrows=list(w['Payload'].values)[1:]\npayload=json.loads(''.join(row[1] for row in sorted(rows,key=lambda row:int(row[0]))))\nprint(json.dumps({'payload':payload,'sheets':w.sheetnames,'formulas':sum(cell.data_type=='f' for sheet in w for row in sheet for cell in row)}))\nw.close()`,
        xlsxPath,
      ],
      { encoding: "utf8", maxBuffer: 10 * 1024 * 1024 },
    ),
  );
  expect(inspected.payload).toEqual(exported);
  expect(inspected.formulas).toBe(0);
  expect(inspected.sheets).toContain("Acknowledgements");
  await page.reload();
  panel = await openSavedScope();
  await expect(
    panel.getByText("Saved follow-up receipt", { exact: true }),
  ).toBeVisible();
  await expect(
    panel.getByText(/already exists for this immutable proposal/),
  ).toBeVisible();
  await expect(
    panel.getByRole("button", { name: "Confirm follow-up plan", exact: true }),
  ).toHaveCount(0);
  expect(await (await page.request.get("/api/work")).json()).toEqual(workAfter);
  await page.goto(
    `/?view=work&case=${created.case.id}&network_id=${network.id}&location_id=${north.id}`,
  );
  await expect(
    page.getByRole("region", { name: "Follow-up review scope", exact: true }),
  ).toBeVisible();
  await expect(
    page.getByRole("region", {
      name: "Network participation scope",
      exact: true,
    }),
  ).toHaveCount(0);
  await expect(
    page.getByRole("combobox", { name: "Network filter", exact: true }),
  ).toHaveValue(network.id);
  await expect(
    page.getByRole("combobox", {
      name: "Practice location filter",
      exact: true,
    }),
  ).toHaveValue(north.id);
  await page
    .getByRole("region", { name: "Follow-up review scope", exact: true })
    .screenshot({ path: info.outputPath("follow-up-work-queue-scope.png") });
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= window.innerWidth + 1,
    ),
  ).toBe(true);
});
