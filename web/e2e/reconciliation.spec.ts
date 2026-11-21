import { expect, test, type Page } from "@playwright/test";

async function upload(
  page: Page,
  source: string,
  label: string,
  phone: string,
  native = false,
) {
  const practice = {
    line1: "10 Example Street",
    suite: "04",
    city: "Boston",
    state: "MA",
    zip: "02108",
    kind: "practice",
    path: "source-office-NORTH",
  };
  const row = {
    record_id: "001",
    npi: "1000000001",
    provider_name: "Alex Reconciliation Synthetic",
    entity_type: "clinician",
    address: "10 Example Street STE 04",
    city: "Boston",
    state: "MA",
    zip: "02108",
    phone,
    location_id: "NORTH",
    native_addresses: native
      ? [
          {
            ...practice,
            line1: "90 Postal Road",
            suite: null,
            kind: "mailing",
            path: "source-mailing",
          },
          { ...practice, suite: null, line2: "STE 04" },
          { ...practice, suite: "40", path: "source-office-OTHER" },
        ]
      : [practice],
  };
  const response = await page.request.post(
    `/api/intakes/files?${new URLSearchParams({ filename: label, source, designation: "synthetic", profile: "flat" })}`,
    {
      data: Buffer.from(JSON.stringify([row])),
      headers: { "Content-Type": "application/octet-stream" },
    },
  );
  expect(response.ok(), await response.text()).toBe(true);
  return response.json();
}

test("three retained sources show quality, reproducible typed candidates, persisted history and stale baselines", async ({
  page,
}, info) => {
  const prefix = `reconciliation-${info.project.name}`;
  const labels = ["clinic", "payer", "reference"].map(
    (source) => `${prefix}-${source}.json`,
  );
  const receipts = [];
  for (const [index, source] of ["clinic", "payer", "reference"].entries()) {
    receipts.push(
      await upload(
        page,
        `${prefix}-${source}`,
        labels[index],
        index === 1 ? "2125550199" : "2125550101",
        index === 2,
      ),
    );
  }
  await page.goto("/?view=intake");
  await page.getByRole("link", { name: "Reconcile", exact: true }).click();
  await expect(page).toHaveURL(/view=reconciliation/);
  await expect(
    page.getByRole("button", { name: "Create candidate run" }),
  ).toBeDisabled();
  for (const label of labels) {
    await page
      .getByRole("checkbox", { name: new RegExp("^" + label.replaceAll(".", "\\.")) })
      .check();
    await page
      .getByLabel(`Entity type for ${label}`, { exact: true })
      .selectOption("clinician");
  }
  await page
    .getByRole("button", { name: `Inspect quality: ${labels[2]}`, exact: true })
    .click();
  await expect(page.getByText(/3 address references · Rule/)).toBeVisible();
  await expect(page.getByText(/mailing excluded/)).toBeVisible();
  await page
    .getByText(/Inspect source record 2 · Alex Reconciliation Synthetic/)
    .click();
  await expect(
    page.getByText(/Address path native_addresses\[1\]/),
  ).toBeVisible();
  const quality = page.getByRole("region", {
    name: "Source record source and comparison values",
  });
  await expect(quality.getByText('"STE 04"', { exact: true })).toBeVisible();
  await expect(quality.getByText('"04"', { exact: true })).toBeVisible();
  await page
    .getByLabel("Run reviewer", { exact: true })
    .fill("Synthetic Reviewer");
  await page
    .getByLabel("Run reason", { exact: true })
    .fill("Compare explicitly selected three-source evidence");
  const firstRunResponse = page.waitForResponse(
    (response) =>
      response.url().endsWith("/api/reconciliation/runs") &&
      response.request().method() === "POST",
  );
  await page
    .getByRole("button", { name: "Create candidate run", exact: true })
    .click();
  const firstRun = await (await firstRunResponse).json();
  await expect(
    page.getByText(/3 clinician candidates in this filter/),
  ).toBeVisible();
  await page.locator(".rc-candidate > summary").first().click();
  await expect(
    page.getByRole("heading", { name: "Agreements", exact: true }),
  ).toBeVisible();
  await expect(
    page.getByText("npi equal", { exact: true }).first(),
  ).toBeVisible();
  await expect(
    page.getByRole("button", { name: /Approve link|Link identity/ }),
  ).toHaveCount(0);
  await page
    .getByLabel("Candidate type", { exact: true })
    .selectOption("location");
  await expect(page.getByText(/Mailing addresses are excluded/)).toBeVisible();
  await page
    .getByLabel("Review eligibility", { exact: true })
    .selectOption("false");
  await expect(
    page.getByText(/2 location candidates in this filter/),
  ).toBeVisible();
  await page.locator(".rc-candidate > summary").first().click();
  await expect(page.locator(".rc-candidate[open]").getByText("suite conflict", { exact: true })).toBeVisible();
  await page.screenshot({
    path: info.outputPath("reconciliation-candidate-evidence.png"),
    fullPage: true,
  });

  const againResponse = page.waitForResponse(
    (response) =>
      response.url().endsWith("/api/reconciliation/runs") &&
      response.request().method() === "POST",
  );
  await page
    .getByRole("button", { name: "Create candidate run", exact: true })
    .click();
  const again = await (await againResponse).json();
  expect(again.id).not.toBe(firstRun.id);
  const firstCandidates = await (
    await page.request.get(
      `/api/reconciliation/runs/${firstRun.id}/candidates?limit=100`,
    )
  ).json();
  const againCandidates = await (
    await page.request.get(
      `/api/reconciliation/runs/${again.id}/candidates?limit=100`,
    )
  ).json();
  expect(
    againCandidates.items.map((candidate: { id: string }) => candidate.id),
  ).toEqual(
    firstCandidates.items.map((candidate: { id: string }) => candidate.id),
  );
  const locationCandidates = againCandidates.items.filter(
    (candidate: { kind: string }) => candidate.kind === "location",
  );
  expect(locationCandidates).toHaveLength(5);
  for (const candidate of locationCandidates) {
    expect(candidate.left_record.original_fields.address.kind).toBe("practice");
    expect(candidate.right_record.original_fields.address.kind).toBe(
      "practice",
    );
  }
  await page.reload();
  await expect(page.getByLabel("Candidate type", { exact: true })).toHaveValue("location");
  await expect(page.getByLabel("Review eligibility", { exact: true })).toHaveValue("false");
  await expect(
    page.getByLabel("Saved candidate run", { exact: true }),
  ).toHaveValue(again.id);
  await expect(
    page.getByText(/2 location candidates in this filter/),
  ).toBeVisible();
  await page
    .getByLabel("Saved candidate run", { exact: true })
    .selectOption(firstRun.id);
  await expect(
    page.getByLabel("Saved candidate run", { exact: true }),
  ).toHaveValue(firstRun.id);

  const latest = await upload(
    page,
    `${prefix}-clinic`,
    `${prefix}-clinic-later.json`,
    "2125550123",
  );
  const accepted = await page.request.post(`/api/intakes/${latest.id}/commit`, {
    data: {
      policy: "valid_rows",
      actor: "Synthetic Reviewer",
      reason: "Explicit later accepted source baseline",
      expected_attempt: latest.attempt_id,
    },
  });
  expect(accepted.ok(), await accepted.text()).toBe(true);
  await page
    .getByRole("button", {
      name: "Refresh sources and run status",
      exact: true,
    })
    .click();
  await expect(
    page.getByRole("alert").filter({ hasText: "This run is stale" }),
  ).toBeVisible();
  await expect(
    page.getByText(/2 location candidates in this filter/),
  ).toBeVisible();
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= window.innerWidth + 1,
    ),
  ).toBe(true);
  await page.screenshot({
    path: info.outputPath("reconciliation-stale-run.png"),
    fullPage: true,
  });
});
