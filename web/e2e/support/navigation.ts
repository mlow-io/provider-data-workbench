import { expect, type Page } from '@playwright/test';

/** Exercise the real responsive sidebar rather than clicking hidden links. */
export async function navigateViaSidebar(page: Page, label: string) {
  const navigation = page.getByRole('navigation', { name: 'Workbench navigation', exact: true });
  if (!await navigation.isVisible()) {
    await page.getByRole('button', { name: 'Toggle navigation', exact: true }).click();
  }
  await expect(navigation).toBeVisible();
  const narrow = await page.evaluate(() => matchMedia('(max-width: 1023px)').matches);
  await navigation.getByRole('link', { name: label, exact: true }).click();
  if (narrow) await expect(navigation).not.toBeVisible();
}
