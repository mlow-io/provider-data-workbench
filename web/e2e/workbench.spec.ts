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
  test("loads all five views cleanly with zero console errors or horizontal overflow", async ({
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

    await openSidebarView(page, "Phone Corrections");
    await expect(page.getByRole("heading", { name: /Reviewed Phone Corrections/i })).toBeVisible();
    await expect(page.getByText("Reviewed office scopes")).toBeVisible();
    await expect(page.getByRole("button", { name: /Brentwood Maryland Farms/i })).toBeVisible();
    await assertNoHorizontalOverflow(page);

    await openSidebarView(page, "Deliveries & Export");
    await expect(
      page.getByRole("heading", { name: /Recurring Deliveries & Approved Exports/i })
    ).toBeVisible();
    await page.getByRole("button", { name: /Nov 16, 2026 Delivery/i }).click();
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

test.describe("Live reviewed phone correction", () => {
  // Commits a correction to the invocation's shared database, so it runs once.
  test("decides a phone, creates a candidate and approves it separately", async ({ page }, testInfo) => {
    test.skip(testInfo.project.name !== "wide", "Mutates shared live state; covered once");
    const errors = attachErrorListeners(page);

    await page.goto("/?view=corrections");
    await page.getByRole("button", { name: /Brentwood Maryland Farms/i }).click();
    await expect(page.getByText("Sources disagree").first()).toBeVisible();
    await page.getByRole("radio", { name: /\(615\) 555-0139/ }).check();
    await page.getByLabel("Decision reason").fill("Payer directory matches the office manager's confirmation");
    await page.getByRole("button", { name: /Record phone decision/i }).click();

    await expect(page.getByText("Candidate value")).toBeVisible();
    await page.getByRole("button", { name: /Create roster candidate/i }).click();
    await page.getByRole("button", { name: /Review and approve/i }).click();

    await expect(page.getByText("Correction lineage")).toBeVisible();
    await expect(page.getByText(/Candidate Awaiting Approval/i)).toBeVisible();
    const feedsBefore = await (await page.request.get("/api/feeds")).json();
    const baseline = feedsBefore.items[0].current_version as string;
    await page.getByRole("button", { name: /Approve & Promote Version/i }).click();
    await expect(page.getByText("Live Consumer Baseline").first()).toBeVisible();
    await expect(page.getByText("Corrected", { exact: true })).toBeVisible();
    await assertNoHorizontalOverflow(page);

    const feed = (await (await page.request.get("/api/feeds")).json()).items[0];
    expect(feed.current_version).not.toBe(baseline);
    const exported = await (await page.request.get(`/api/feed-versions/${feed.current_version}/export`)).json();
    const corrected = exported.records.filter((r: { materialization?: unknown }) => r.materialization);
    expect(corrected).toHaveLength(1);
    expect(corrected[0].normalized.phone).toBe("6155550139");
    expect(corrected[0].original.phone).toBe("6155550103");

    await page.goto("/?view=corrections");
    await page.getByRole("button", { name: /Brentwood Maryland Farms/i }).click();
    await expect(page.getByText("Correction approved").first()).toBeVisible();
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
