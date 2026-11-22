import { expect, test, type Page } from "@playwright/test";

function attachErrorListeners(page: Page) {
  const errors: string[] = [];
  page.on("pageerror", (err) => errors.push(`pageerror: ${err.message}`));
  page.on("console", (msg) => {
    if (msg.type() === "error") {
      errors.push(`console.error: ${msg.text()}`);
    }
  });
  return errors;
}

async function assertNoHorizontalOverflow(page: Page) {
  const overflow = await page.evaluate(() => {
    return document.documentElement.scrollWidth - window.innerWidth;
  });
  expect(overflow).toBeLessThanOrEqual(1);
}

async function openSidebarView(page: Page, label: string) {
  const sidebarLink = page.locator("a[data-sidebar='menu-button']", { hasText: label }).first();
  if (!(await sidebarLink.isVisible())) {
    await page.getByRole("button", { name: "Toggle navigation" }).click();
  }
  await expect(sidebarLink).toBeVisible();
  await sidebarLink.click();
}

test.describe("Live SQLite & Intake Engine Workbench", () => {
  test("loads all four views cleanly with zero console errors or horizontal overflow", async ({
    page,
  }) => {
    const errors = attachErrorListeners(page);

    await page.goto("/");
    await expect(page.getByText("Directory Clean Rate")).toBeVisible();
    await expect(page.getByText("Open Discrepancies")).toBeVisible();
    await expect(page.getByText("Held Deliveries")).toBeVisible();
    await expect(page.getByText("NSA 2-Day SLA At-Risk")).toBeVisible();
    await expect(page.getByText(/Dr\. Elena Morales, MD/i)).toBeVisible();
    await assertNoHorizontalOverflow(page);

    await page.getByRole("button", { name: /Inspect Dr\. Elena Morales/i }).click();
    const sheet = page.getByRole("dialog");
    await expect(sheet.getByText(/Current Directory \(phone\)/i)).toBeVisible();
    await expect(sheet.getByText("(615) 555-0101", { exact: true })).toBeVisible();
    await expect(sheet.getByText("(615) 555-0142", { exact: true })).toBeVisible();
    await page.keyboard.press("Escape");

    await openSidebarView(page, "Import & Adapt");
    await expect(
      page.getByRole("heading", { name: /Import & Schema Adaptation/i })
    ).toBeVisible();
    const catalogRes = await page.request.get("/api/schema-catalog/status");
    const catalogJson = (await catalogRes.json()) as { enabled?: boolean };
    await page.getByRole("button", { name: /Cumberland Monthly Roster/i }).click();
    if (catalogJson.enabled) {
      await expect(page.getByText("Deterministic · 0 LLM Calls")).toBeVisible();
    } else {
      await expect(page.getByText(/Host CSV Intake Preview/i)).toBeVisible();
    }
    await assertNoHorizontalOverflow(page);

    await openSidebarView(page, "Deliveries & Export");
    await expect(
      page.getByRole("heading", { name: /Recurring Deliveries & Approved Exports/i })
    ).toBeVisible();
    await expect(
      page.getByText(/Candidate Held Automatically — Active Approved Baseline Protected/i)
    ).toBeVisible();
    await page.getByRole("button", { name: /Nov 2, 2026 Delivery/i }).click();
    const exportBtn = page.getByRole("button", { name: /Export Approved Roster/i });
    await expect(exportBtn).toBeEnabled();
    await exportBtn.click();
    await expect(page.getByText("Export Approved Directory Snapshot")).toBeVisible();
    await expect(page.getByText(/Snapshot pin:/i)).toBeVisible();
    await page.keyboard.press("Escape");
    await assertNoHorizontalOverflow(page);

    await openSidebarView(page, "Provider Directory");
    await expect(
      page.getByRole("heading", { name: /Provider & Clinic Directory/i })
    ).toBeVisible();
    await expect(page.getByText("Directory Listings (15)")).toBeVisible();
    await expect(page.getByText("Luhn Valid").first()).toBeVisible();
    await expect(page.getByText("Directory Suppressed").first()).toBeVisible();
    await assertNoHorizontalOverflow(page);

    expect(errors).toEqual([]);
  });
});

test.describe("Static Demo Sandbox (?demo=1)", () => {
  test("supports full interactive triage, schema adaptation, hold acknowledgement, and reset", async ({
    page,
  }) => {
    const errors = attachErrorListeners(page);

    await page.goto("/?demo=1");
    if ((page.viewportSize()?.width ?? 0) >= 640) {
      await expect(page.getByText(/Interactive Demo · Synthetic TN/i)).toBeVisible();
    }
    await expect(page.getByRole("button", { name: /Reset Demo/i })).toBeVisible();

    await page.getByRole("button", { name: /Inspect Dr\. Elena Morales/i }).click();
    await page
      .getByLabel("Audit Rationale")
      .fill("Confirmed direct Midtown desk scheduling line during E2E test.");
    await page.getByRole("button", { name: /Record Decision/i }).click();
    await expect(page.getByRole("tab", { name: /Audit Timeline \(1\)/i })).toBeVisible();
    await page.keyboard.press("Escape");

    await openSidebarView(page, "Import & Adapt");
    await page.getByRole("button", { name: /Renamed Payer Delta \(Exclusion Trap\)/i }).click();
    await expect(page.getByText(/Exclusion Flag Semantics Detected:/i)).toBeVisible();
    await expect(page.getByText("1234567890")).toBeVisible();
    await expect(page.getByText("Invalid Checksum")).toBeVisible();
    await page.getByRole("button", { name: /Save Reviewed Variant/i }).click();
    await expect(page.getByText("Saved Schema Variants (2)")).toBeVisible();
    await page.getByRole("button", { name: /Accept Valid Rows to Staging/i }).click();
    await expect(page.getByRole("button", { name: /Accepted to Staging/i })).toBeDisabled();

    await openSidebarView(page, "Deliveries & Export");
    const ackButtons = page.getByRole("button", { name: /^Acknowledge Hold$/i });
    await expect(ackButtons).toHaveCount(3);
    for (let i = 0; i < 3; i += 1) {
      await page.getByRole("button", { name: /^Acknowledge Hold$/i }).first().click();
    }
    const promoteBtn = page.getByRole("button", { name: /Approve & Promote Version/i });
    await expect(promoteBtn).toBeEnabled();
    await promoteBtn.click();
    await expect(page.getByText("Live Consumer Baseline").first()).toBeVisible();

    await page.getByRole("button", { name: /Reset Demo/i }).click();
    await expect(
      page.getByText(/Candidate Held Automatically — Active Approved Baseline Protected/i)
    ).toBeVisible();
    await assertNoHorizontalOverflow(page);

    expect(errors).toEqual([]);
  });
});
