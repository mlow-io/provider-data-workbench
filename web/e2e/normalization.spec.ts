import { expect, test } from "@playwright/test";

test("profiles a synthetic clinic file, reviews explicit normalization and separately accepts its dataset", async ({
  page,
}, info) => {
  const csv =
    'npi,provider_name,address,city,state,zip,Office tel,location_id,source_updated_at\n0000000001,Alex Synthetic,10 Example St,Boston,ma,02108-0042,"+1 (212) 555-0101 ext 007",NORTH,03/04/2026\n0000000002,Robin Synthetic,20 Example St,Boston,ma,02108,ambiguous phone,SOUTH,03/04/2026\n';
  await page.goto("/?view=intake");
  await page
    .getByLabel("Source namespace", { exact: true })
    .fill(`normalization-${info.project.name}`);
  await page
    .getByLabel("Source file", { exact: true })
    .setInputFiles({
      name: "synthetic-normalization.csv",
      mimeType: "text/csv",
      buffer: Buffer.from(csv),
    });
  await page.getByRole("button", { name: "Upload and preview" }).click();
  await expect(
    page.getByRole("heading", { name: "synthetic-normalization.csv" }),
  ).toBeVisible();
  const marker = await page
    .locator("#intake-receipt-detail > .iw-eyebrow")
    .textContent();
  const receiptId = marker!.replace("Delivery ", "").trim();
  expect(
    (await page.request.get(`/api/intakes/${receiptId}/dataset`)).ok(),
  ).toBe(false);
  await page.getByRole("button", { name: "Profile and normalize" }).click();
  const panel = page.getByRole("region", { name: "Profile and normalization" });
  await expect(panel.getByText(/2 source rows · 9 columns/)).toBeVisible();
  await panel
    .getByRole("button", { name: "Use suggested normalization columns" })
    .click();
  await panel
    .getByLabel("phone format", { exact: true })
    .selectOption("phone_us");
  await panel
    .getByLabel("state format", { exact: true })
    .selectOption("state_us");
  await panel.getByLabel("zip format", { exact: true }).selectOption("zip_us");
  await panel
    .getByText("Additional identifiers, extension and source date", {
      exact: true,
    })
    .click();
  await panel
    .getByLabel("Normalize source updated at source", { exact: true })
    .selectOption("source_updated_at");
  await panel
    .getByLabel("source updated at format", { exact: true })
    .selectOption("%d/%m/%Y");
  await panel.getByRole("button", { name: "Preview normalization" }).click();
  await expect(
    panel.getByText("1 valid · 1 quarantined · 2 total", { exact: true }),
  ).toBeVisible();
  await panel.getByText("Sample row 1 · Valid", { exact: true }).click();
  await expect(
    panel
      .locator("pre")
      .filter({ hasText: '"phone_extension": "007"' })
      .first(),
  ).toBeVisible();
  await expect(
    panel
      .locator("pre")
      .filter({ hasText: '"source_updated_at": "2026-04-03"' })
      .first(),
  ).toBeVisible();
  await panel
    .getByLabel("Recipe name", { exact: true })
    .fill("Synthetic clinic phone/date rules");
  await panel
    .getByLabel("Recipe reviewer", { exact: true })
    .fill("Synthetic reviewer");
  await panel
    .getByLabel("Recipe decision reason", { exact: true })
    .fill("Review original phone extensions and declared day/month dates");
  await panel.getByRole("button", { name: "Save proposed recipe" }).click();
  await expect(
    panel.getByText(
      "Proposed revision saved. Review it, then explicitly approve.",
    ),
  ).toBeVisible();
  await panel
    .getByRole("button", { name: "Approve recipe", exact: true })
    .click();
  await expect(
    panel.getByText(
      "Approved recipe saved. Apply it to create a new interpretation.",
    ),
  ).toBeVisible();
  await panel
    .getByRole("button", { name: "Apply approved recipe", exact: true })
    .click();
  await expect(
    panel.getByRole("button", { name: "Profile and normalize" }),
  ).toHaveAttribute("aria-expanded", "false");
  await expect(
    page.getByRole("button", { name: "Accept valid rows", exact: true }),
  ).toBeDisabled();
  await page
    .getByLabel("Reviewer", { exact: true })
    .first()
    .fill("Synthetic reviewer");
  await page
    .getByLabel("Acceptance / rejection reason", { exact: true })
    .fill(
      "Accept the single valid location; retain malformed phone in quarantine",
    );
  await page
    .getByRole("button", { name: "Accept valid rows", exact: true })
    .click();
  await expect(
    panel.getByRole("link", { name: "Download validated dataset JSON" }),
  ).toBeVisible();
  const response = await page.request.get(`/api/intakes/${receiptId}/dataset`);
  expect(response.ok()).toBe(true);
  const dataset = await response.json();
  expect(dataset.records).toHaveLength(1);
  expect(dataset.records[0].normalized).toMatchObject({
    npi: "0000000001",
    phone: "2125550101",
    phone_extension: "007",
    zip: "02108-0042",
    source_updated_at: "2026-04-03",
  });
  expect(dataset.records[0].original["Office tel"]).toBe(
    "+1 (212) 555-0101 ext 007",
  );
  expect(dataset.quarantine).toHaveLength(1);
  await page.getByRole("button", { name: "Profile and normalize" }).click();
  await expect(panel.getByLabel("Compatible approved recipe")).toBeVisible();
  await expect(panel.getByLabel("phone format", { exact: true })).toHaveValue(
    "phone_us",
  );
  await panel
    .getByText("Additional identifiers, extension and source date", {
      exact: true,
    })
    .click();
  await expect(
    panel.getByLabel("source updated at format", { exact: true }),
  ).toHaveValue("%d/%m/%Y");
  await expect(
    panel.getByText(/Applied normalization recipe/).first(),
  ).toBeVisible();
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= innerWidth,
    ),
  ).toBe(true);
  await page.screenshot({
    path: info.outputPath("normalization-accepted.png"),
    fullPage: true,
  });
});
