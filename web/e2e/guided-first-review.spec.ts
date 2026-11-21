import { expect, test } from '@playwright/test';
import { readFile } from 'node:fs/promises';

test('first synthetic clinic and reference can reach a resumable comparison and handoff', async ({page, request}, info) => {
  test.setTimeout(120_000);
  await page.goto('/');
  await expect(page.getByRole('heading', {name:'Provider work queue'})).toBeVisible();
  await page.getByRole('link', {name:'Receive data', exact:true}).click();
  await expect(page.getByRole('heading', {name:'Start with a clinic roster'})).toBeVisible();
  const clinicReceived = page.waitForResponse(response => response.url().endsWith('/api/demo/samples/clinic-workbook') && response.request().method() === 'POST');
  await page.getByRole('button', {name:'Load synthetic sample'}).click();
  const clinic = await (await clinicReceived).json();
  await expect(page.locator('#intake-receipt-detail > p.iw-eyebrow')).toContainText(clinic.id);
  if (clinic.state === 'needs_mapping') {
    await page.getByRole('button', {name:'Use suggested columns'}).click();
    await page.getByRole('button', {name:'Save mapping and reprocess'}).click();
  }
  await expect(page.getByText('2 valid · 1 quarantined · 3 total')).toBeVisible();
  await page.getByLabel('Reviewer', {exact:true}).first().fill('Synthetic reviewer');
  await page.getByLabel('Acceptance / rejection reason').fill('Reviewed the clinic source and quarantine');
  const accepted = page.waitForResponse(response => response.url().endsWith(`/api/intakes/${clinic.id}/commit`) && response.request().method() === 'POST');
  await page.getByRole('button', {name:'Accept valid rows'}).click();
  expect((await accepted).ok()).toBe(true);
  await expect(page.getByRole('heading', {name:'Linked cases'})).toBeVisible();

  const inbox = await (await request.get('/api/intakes')).json();
  const parsed = inbox.items.filter((item: {attempt_id?:string; state?:string}) =>
    item.attempt_id && !['processing', 'failed', 'interrupted', 'rejected'].includes(item.state ?? ''));
  await page.getByRole('link', {name:'Provider records', exact:true}).click();
  if (new Set(parsed.map((item: {source:string}) => item.source)).size < 2) {
    await expect(page.getByText(/Comparison needs at least two retained interpretations/)).toBeVisible();
    await page.getByRole('link', {name:'Open Intake', exact:true}).click();
  } else {
    await page.getByRole('link', {name:'Receive data', exact:true}).click();
  }
  await page.getByRole('combobox', {name:/^Synthetic sample/}).selectOption('nppes');
  const referenceReceived = page.waitForResponse(response => response.url().endsWith('/api/demo/samples/nppes') && response.request().method() === 'POST');
  await page.getByRole('button', {name:'Load synthetic sample'}).click();
  const reference = await (await referenceReceived).json();
  expect(reference.source).toBe('synthetic-nppes-reference');
  await expect(page.locator('#intake-receipt-detail > p.iw-eyebrow')).toContainText(reference.id);
  const before = await (await request.get('/api/work')).json();
  const identityWrites: string[] = [];
  page.on('request', req => { if (req.method() === 'POST' && req.url().endsWith('/api/reconciliation/links')) identityWrites.push(req.url()); });
  await page.getByRole('link', {name:'Provider records', exact:true}).click();
  for (const item of [clinic, reference]) {
    const card = page.locator(`[data-receipt-id="${item.id}"]`);
    await expect(card).toContainText(item.id);
    await card.getByRole('checkbox').check();
    await card.getByRole('combobox').selectOption('clinician');
  }
  await page.getByLabel('Run reviewer', {exact:true}).fill('Synthetic reviewer');
  await page.getByLabel('Run reason', {exact:true}).fill('Compare the clinic and reference examples');
  const created = page.waitForResponse(response => response.url().endsWith('/api/reconciliation/runs') && response.request().method() === 'POST');
  await page.getByRole('button', {name:'Create candidate run', exact:true}).click();
  const response = await created;
  expect(response.ok(), await response.text()).toBe(true);
  const run = await response.json();
  expect(run.metrics.candidate_count).toBeGreaterThan(0);
  await page.getByLabel('Find a provider or identifier').fill('1234567890');
  await page.getByRole('button', {name:'Search candidates'}).click();
  await expect(page.getByRole('status').filter({hasText:'Applied search: 1234567890'})).toBeVisible();
  const summaries = page.locator('.rc-candidates > details > summary');
  await expect(summaries.filter({hasText:'Source location: NORTH'})).toHaveCount(1);
  await expect(summaries.filter({hasText:'Source location: SOUTH'})).toHaveCount(1);
  await expect(page.locator('.rc-candidates')).not.toContainText('Source address:');
  await page.locator('.rc-candidates').screenshot({path:info.outputPath('candidate-context.png')});
  const download = page.waitForEvent('download');
  await page.getByRole('link', {name:'Download filtered candidate evidence (JSON)'}).click();
  const data = JSON.parse(await readFile((await (await download).path())!, 'utf8'));
  expect(data.scope.search).toBe('1234567890');
  expect(data.total).toBeGreaterThan(0);
  expect(data.candidates).toHaveLength(data.total);
  await page.reload();
  await expect(page.getByLabel('Saved candidate run')).toHaveValue(run.id);
  await expect(page.getByLabel('Find a provider or identifier')).toHaveValue('1234567890');
  expect(await (await request.get('/api/work')).json()).toEqual(before);
  expect((await (await request.get(`/api/intakes/${reference.id}`)).json()).observations_count).toBe(0);
  expect(identityWrites).toEqual([]);
});
