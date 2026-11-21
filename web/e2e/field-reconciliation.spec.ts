import { expect, test } from "@playwright/test";
import { readFile } from "node:fs/promises";
import { execFileSync } from "node:child_process";

test("three approved sources retain conflicting phones, explicit preferences/conflicts and complete pinned exports", async ({
  page,
}, info) => {
  const prefix = `field-reconciliation-${info.project.name}`;
  const inputs = [];
  for (const source of ["clinic", "payer", "reference"]) {
    const row = {
      record_id: "001",
      npi: "1000000001",
      provider_name: "Alex Fields Synthetic",
      entity_type: "clinician",
      address: "10 Example Street STE 04",
      city: "Boston",
      state: "MA",
      zip: "02108",
      phone: source === "payer" ? "2125550199" : "2125550101",
      phone_extension: source === "reference" ? null : "004",
      location_id: "NORTH",
    };
    const uploaded = await page.request.post(
      `/api/intakes/files?${new URLSearchParams({ filename: `${prefix}-${source}.json`, source: `${prefix}-${source}`, designation: "synthetic", profile: "flat" })}`,
      {
        data: Buffer.from(JSON.stringify([row])),
        headers: { "Content-Type": "application/octet-stream" },
      },
    );
    expect(uploaded.ok(), await uploaded.text()).toBe(true);
    const receipt = await uploaded.json();
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
      reason: "Three-source field reconciliation setup",
    },
  });
  expect(created.ok(), await created.text()).toBe(true);
  const run = await created.json();
  const candidates = await (
    await page.request.get(
      `/api/reconciliation/runs/${run.id}/candidates?limit=100`,
    )
  ).json();
  const targets: Record<string, string> = {};
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
          reason: `Explicit ${kind} crosswalk for three-source field journey`,
          ...(targets[kind]
            ? { target_id: targets[kind] }
            : { new_label: `${prefix} ${kind}` }),
        },
      });
      expect(approved.ok(), await approved.text()).toBe(true);
      targets[kind] = (await approved.json()).decision.target_id;
    }
  }
  await page.goto("/?view=reconciliation");
  await page
    .getByRole("button", {
      name: "Open reconciled field evidence",
      exact: true,
    })
    .click();
  const panel = page.getByRole("region", {
    name: "Reconciled field evidence",
    exact: true,
  });
  await panel
    .getByLabel("Find reviewed clinician", { exact: true })
    .fill(targets.clinician);
  await panel
    .getByLabel("Reviewed clinician", { exact: true })
    .selectOption(targets.clinician);
  await expect(
    panel.getByRole("region", {
      name: "provider name reconciliation",
      exact: true,
    }),
  ).toBeVisible();
  await expect(
    panel.getByRole("region", { name: "phone reconciliation", exact: true }),
  ).toHaveCount(0);
  await panel
    .getByLabel("Include a reviewed practice location", { exact: true })
    .check();
  await panel
    .getByLabel("Find reviewed practice location", { exact: true })
    .fill(targets.location);
  await panel
    .getByLabel("Reviewed practice location", { exact: true })
    .selectOption(targets.location);
  const phone = panel.getByRole("region", {
    name: "phone reconciliation",
    exact: true,
  });
  await expect(
    phone.getByText(
      "No preferred value or retained-conflict decision has been recorded. No source is selected by default.",
      { exact: true },
    ),
  ).toBeVisible();
  await expect(phone.getByRole("radio")).toHaveCount(3);
  await expect(
    panel.getByText(/3 contributing sources · 3 approved source records/),
  ).toBeVisible();
  await phone
    .getByLabel("Decision for phone", { exact: true })
    .selectOption("select");
  await phone
    .getByRole("radio", {
      name: new RegExp(`Choose phone from ${prefix}-payer `),
    })
    .check();
  await phone
    .getByLabel("Actor for phone", { exact: true })
    .fill("Synthetic Reviewer");
  await phone
    .getByLabel("Reason for phone", { exact: true })
    .fill("Explicit payer phone preference while retaining every assertion");
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
  await expect(
    phone.getByText("Selected source assertion", { exact: true }),
  ).toBeVisible();
  const selectedDownloadPromise = page.waitForEvent("download");
  await panel
    .getByRole("button", { name: "Download reconciled JSON", exact: true })
    .click();
  const selectedDownload = await selectedDownloadPromise;
  const selectedPath = info.outputPath("reconciled-selected.json");
  await selectedDownload.saveAs(selectedPath);
  const selected = JSON.parse(await readFile(selectedPath, "utf8"));
  expect(
    selected.fields.find((field: { field: string }) => field.field === "phone")
      .preferred_value,
  ).toEqual({ number: "2125550199", extension: "004" });
  expect(selected.scope).toEqual({
    clinician_id: targets.clinician,
    location_id: targets.location,
  });
  await phone.screenshot({
    path: info.outputPath("reconciled-phone-selected.png"),
  });

  await phone
    .getByLabel("Decision for phone", { exact: true })
    .selectOption("conflict");
  await phone
    .getByLabel("Reason for phone", { exact: true })
    .fill(
      "Retain the phone discrepancy for further review; no preferred source",
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
  await expect(
    phone.getByText("Retained conflict", { exact: true }),
  ).toBeVisible();
  await phone.getByText(/phone decision history · 2 shown/).click();
  await phone.screenshot({
    path: info.outputPath("reconciled-phone-conflict-history.png"),
  });
  const jsonPromise = page.waitForEvent("download");
  await panel
    .getByRole("button", { name: "Download reconciled JSON", exact: true })
    .click();
  const jsonDownload = await jsonPromise;
  const jsonPath = info.outputPath("reconciled-conflict.json");
  await jsonDownload.saveAs(jsonPath);
  const data = JSON.parse(await readFile(jsonPath, "utf8"));
  expect(data.records).toHaveLength(3);
  const conflictPhone = data.fields.find(
    (field: { field: string }) => field.field === "phone",
  );
  expect(conflictPhone.status).toBe("conflict");
  expect(conflictPhone.preferred_value).toBeNull();
  expect(conflictPhone.history).toHaveLength(2);
  expect(conflictPhone.options).toHaveLength(3);
  expect(
    conflictPhone.options.some(
      (option: { value: { number: string; extension: string | null } }) =>
        option.value.number === "2125550101" && option.value.extension === null,
    ),
  ).toBe(true);
  const xlsxPromise = page.waitForEvent("download");
  await panel
    .getByRole("button", { name: "Download reconciled XLSX", exact: true })
    .click();
  const workbookDownload = await xlsxPromise;
  const workbookPath = info.outputPath("reconciled-conflict.xlsx");
  await workbookDownload.saveAs(workbookPath);
  const inspected = JSON.parse(
    execFileSync(
      "python3",
      [
        "-c",
        `import json,sys\nfrom openpyxl import load_workbook\nw=load_workbook(sys.argv[1],read_only=True,data_only=False)\nrows=list(w['Payload'].values)[1:]\npayload=json.loads(''.join(row[1] for row in sorted(rows,key=lambda row:int(row[0]))))\nprint(json.dumps({'payload':payload,'sheets':w.sheetnames,'assertion_rows':list(w['Source assertions'].values)[1:],'decision_rows':list(w['Field decisions'].values)[1:],'formulas':sum(cell.data_type=='f' for sheet in w for row in sheet for cell in row)}))\nw.close()`,
        workbookPath,
      ],
      { encoding: "utf8", maxBuffer: 10 * 1024 * 1024 },
    ),
  );
  expect(inspected.payload).toEqual(data);
  expect(inspected.sheets).toEqual(["Read me", "Field decisions", "Source assertions", "Payload"]);
  expect(inspected.assertion_rows).toHaveLength(6);
  expect(inspected.assertion_rows.some((row: string[]) => row[0] === "phone" && row[2].endsWith("payer") && JSON.parse(row[5]).number === "2125550199")).toBe(true);
  expect(inspected.decision_rows[0][1]).toBe("conflict");
  expect(inspected.decision_rows[0][2]).toBe("null");
  expect(inspected.formulas).toBe(0);
  // Fill a deliberately bounded synthetic history so the real UI must request
  // its next history page while keeping the latest field decision separate.
  for (let index = 0; index < 19; index++) {
    const context = await (
      await page.request.get(
        `/api/reconciliation/fields/${targets.clinician}?location_id=${targets.location}`,
      )
    ).json();
    const currentPhone = context.fields.find(
      (field: { field: string }) => field.field === "phone",
    );
    const decision = await page.request.post(
      "/api/reconciliation/field-decisions",
      {
        data: {
          clinician_id: targets.clinician,
          location_id: targets.location,
          field: "phone",
          decision: "conflict",
          expected_snapshot: context.snapshot,
          expected_decision: currentPhone.decision.id,
          request_id: crypto.randomUUID(),
          actor: "Synthetic pagination reviewer",
          reason: `Explicit retained pagination conflict ${index + 1}`,
        },
      },
    );
    expect(decision.ok(), await decision.text()).toBe(true);
  }
  await panel
    .getByRole("button", { name: "Refresh field evidence", exact: true })
    .click();
  await expect(
    phone.getByText("phone decision history · 20 shown of 21", { exact: true }),
  ).toBeVisible();
  const historyRequest = page.waitForResponse(
    (response) =>
      response
        .url()
        .includes(`/api/reconciliation/fields/${targets.clinician}?`) &&
      response.url().includes("history_offset=20"),
  );
  await phone
    .getByRole("group", { name: "phone decision history pages", exact: true })
    .getByRole("button", { name: "Next", exact: true })
    .click();
  const historyPage = await (await historyRequest).json();
  const pagedPhone = historyPage.fields.find(
    (field: { field: string }) => field.field === "phone",
  );
  expect(pagedPhone.history_total).toBe(21);
  expect(pagedPhone.history).toHaveLength(1);
  expect(pagedPhone.history[0].decision).toBe("select");
  expect(pagedPhone.decision.decision).toBe("conflict");
  await expect(
    phone.getByText("phone decision history · 1 shown of 21", { exact: true }),
  ).toBeVisible();
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= window.innerWidth + 1,
    ),
  ).toBe(true);
});
