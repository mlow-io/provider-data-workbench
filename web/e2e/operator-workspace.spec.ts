import { test, expect } from '@playwright/test';

test('operator entry has a keyboard path, useful empty state and only delivered destinations', async ({page}, info) => {
  await page.route('**/api/work', route => route.fulfill({json:{items:[]}}));
  await page.goto('/');
  await expect(page.getByRole('heading', {name:'Provider work queue'})).toBeVisible();
  const narrow = info.project.name === 'mobile';
  if (narrow) await page.getByRole('button', {name:'Toggle navigation',exact:true}).click();
  const nav = page.getByRole('navigation', {name:'Workbench navigation'});
  await expect(nav.getByRole('link', {name:'Work queue',exact:true})).toHaveAttribute('aria-current','page');
  await expect(nav.getByRole('link', {name:'Exchanges',exact:true})).toHaveCount(0);
  await expect(nav.getByRole('link', {name:'Operations',exact:true})).toHaveCount(0);
  if (narrow) await page.keyboard.press('Escape');
  await page.reload();
  await expect(page.getByRole('heading', {name:'Provider work queue'})).toBeVisible();
  await page.keyboard.press('Tab');
  await expect(page.getByRole('link', {name:'Skip to workspace'})).toBeFocused();
  await page.keyboard.press('Enter');
  await expect(page.locator('#workspace-content')).toBeFocused();
  const focus = await page.getByLabel('Search work').evaluate(element => {
    (element as HTMLElement).focus();
    const style = getComputedStyle(element);
    return {width:style.outlineWidth,style:style.outlineStyle};
  });
  expect(focus.style).toBe('solid');
  expect(parseFloat(focus.width)).toBeGreaterThanOrEqual(3);
  expect(await page.evaluate(()=>document.documentElement.scrollWidth <= innerWidth)).toBe(true);
  await page.screenshot({path:info.outputPath('operator-work-queue.png'),fullPage:true});
  await page.getByRole('link', {name:'Receive a provider file',exact:true}).click();
  await expect(page.getByRole('heading', {name:'Receive provider data'})).toBeVisible();
  if (narrow) await page.getByRole('button', {name:'Toggle navigation',exact:true}).click();
  await expect(nav.getByRole('link', {name:'Receive data',exact:true})).toHaveAttribute('aria-current','page');
  if (narrow) await page.keyboard.press('Escape');
  await page.waitForLoadState('networkidle');
  await page.screenshot({path:info.outputPath('operator-receive-data.png'),fullPage:true});
  if (narrow) await page.getByRole('button', {name:'Toggle navigation',exact:true}).click();
  await nav.getByRole('link', {name:'Deliveries',exact:true}).click();
  await expect(page.getByRole('heading', {name:'Review deliveries'})).toBeVisible();
  await page.waitForLoadState('networkidle');
  expect(await page.evaluate(()=>document.documentElement.scrollWidth <= innerWidth)).toBe(true);
  await page.screenshot({path:info.outputPath('operator-deliveries.png'),fullPage:true});
  if (narrow) await page.getByRole('button', {name:'Toggle navigation',exact:true}).click();
  for (const link of await nav.getByRole('link').all()) {
    expect((await link.boundingBox())!.height).toBeGreaterThanOrEqual(44);
  }
  if (narrow) await page.keyboard.press('Escape');
  await page.goBack();
  await expect(page.getByRole('heading', {name:'Receive provider data'})).toBeVisible();
});
