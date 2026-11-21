import { expect, test } from "@playwright/test";

test("work queue reports failures and labels stale results until retry", async ({ page }) => {
  let available = false;
  await page.route("**/api/work", route => {
    if (!available) return route.fulfill({ status: 503, json: { detail: "Work service unavailable" } });
    return route.fulfill({ json: { items: [{ id: "north", provider_name: "North clinician", kind: "qa", issue: "Phone review", status: "new" }] } });
  });
  await page.goto("/?view=work");
  await expect(page.getByRole("alert")).toContainText("Work service unavailable");
  await expect(page.getByText("No work matches these filters.")).toHaveCount(0);
  available = true;
  await page.getByRole("button", { name: "Retry / refresh" }).click();
  await expect(page.getByRole("button", { name: /North clinician/ })).toBeVisible();
  available = false;
  await page.getByRole("button", { name: "Refresh", exact: true }).click();
  await expect(page.getByRole("alert")).toContainText("Work service unavailable");
  await expect(page.getByText(/Showing previously loaded work; the latest refresh failed/)).toBeVisible();
  available = true;
  await page.getByRole("button", { name: "Retry / refresh" }).click();
  await expect(page.getByRole("alert")).toHaveCount(0);
  await expect(page.getByText(/Showing previously loaded work; the latest refresh failed/)).toHaveCount(0);
});

test("work queue filters track browser history", async ({ page }) => {
  await page.route("**/api/work", route => route.fulfill({ json: { items: [
    { id: "north", provider_name: "North clinician", kind: "qa", issue: "Phone review", status: "new" },
    { id: "south", provider_name: "South clinician", kind: "qa", issue: "Phone review", status: "new" },
  ] } }));
  await page.goto("/?view=work&search=North");
  await expect(page.getByRole("button", { name: /North clinician/ })).toBeVisible();
  await page.evaluate(() => { history.pushState(null, "", "?view=work&search=South&unassigned=1"); window.dispatchEvent(new PopStateEvent("popstate")); });
  await expect(page.getByLabel("Search work")).toHaveValue("South");
  await expect(page.getByRole("checkbox", { name: "Unassigned" })).toBeChecked();
  await expect(page.getByRole("button", { name: /South clinician/ })).toBeVisible();
  await page.goBack();
  await expect(page.getByLabel("Search work")).toHaveValue("North");
  await expect(page.getByRole("checkbox", { name: "Unassigned" })).not.toBeChecked();
  await expect(page.getByRole("button", { name: /North clinician/ })).toBeVisible();
  await expect(page.getByRole("button", { name: /South clinician/ })).toHaveCount(0);
});

test("reviews missing-field, stale-verification, and duplicate candidate cases", async ({ page }, testInfo) => {
  const missingCase = testInfo.project.name === "mobile"
    ? { provider: "Robert Lane MD", field: "specialty" }
    : { provider: "Jordan Ellis DO", field: "phone" };

  await page.goto("/?view=qa");
  await expect(page.getByRole("heading", { name: "Batch exception review" })).toBeVisible();
  await expect(page.getByText(/bounded review data/i)).toBeVisible();
  await page.screenshot({ path: testInfo.outputPath("queue-overview.png"), fullPage: true });

  await page.getByRole("button", { name: /missing required field/i }).click();
  await page.getByRole("row", { name: new RegExp(missingCase.provider) }).click();
  await expect(page.getByText(new RegExp(`${missingCase.field} is required`))).toBeVisible();
  await expect(page.getByRole("region", { name: "Normalized record comparison" })).toBeVisible();
  await page.screenshot({ path: testInfo.outputPath("missing-field-evidence.png"), fullPage: true });
  await page.getByLabel("Action").selectOption("assign");
  await page.getByLabel("Assignee").fill("Avery");
  const decisionReason = `Route missing ${missingCase.field} for source confirmation`;
  await page.getByLabel(/Reason/).fill(decisionReason);
  const saveEvent = page.getByRole("button", { name: "Save event" });
  await page.locator(".action-panel").scrollIntoViewIfNeeded();
  await saveEvent.click();
  await expect(page.locator("aside .status-assigned")).toBeVisible();
  await expect(page.locator("aside .history")).toContainText(decisionReason);
  await page.screenshot({ path: testInfo.outputPath("recorded-decision-history.png"), fullPage: true });

  await page.getByRole("button", { name: /stale verification/i }).click();
  await page.getByRole("row", { name: /Anita Shah NP/i }).click();
  await expect(page.locator("aside .rule-callout")).toContainText(/last verified/i);

  await page.getByRole("button", { name: /possible duplicate provider location/i }).click();
  await page.getByRole("row", { name: /Keisha Thompson MD/i }).click();
  await expect(page.getByText(/candidate only — no automatic merge/i)).toBeVisible();
  await expect(page.getByRole("region", { name: "Normalized record comparison" })).toBeVisible();
  await page.screenshot({ path: testInfo.outputPath("duplicate-comparison.png"), fullPage: true });
});
