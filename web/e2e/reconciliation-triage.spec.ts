import { expect, test } from '@playwright/test';
import { readFile } from 'node:fs/promises';

test('evidence reason triage separates missing and conflicting identifiers and resumes without decisions', async ({ page }, info) => {
  const namespace = `synthetic-triage-${info.project.name}`;
  const cases = [
    { name: 'Synthetic Ready Clinician', clinicNpi: '1111111111', payerNpi: '1111111111' },
    { name: 'Synthetic Missing NPI', clinicNpi: '2222222222', payerNpi: null },
    { name: 'Synthetic Conflicting NPI', clinicNpi: '3333333333', payerNpi: '4444444444' },
  ];
  const receipts = [];
  for (const source of ['clinic', 'payer']) {
    const rows = cases.map((item, index) => ({
      record_id: `${source}-${index}`, entity_type: 'clinician',
      provider_name: item.name, npi: source === 'clinic' ? item.clinicNpi : item.payerNpi,
      address: `${10 + index} Synthetic Street`, suite: '100', city: 'Example',
      state: 'MA', zip: '02108', phone: '2125550100',
    }));
    const label = `${namespace}-${source}.json`;
    const response = await page.request.post(`/api/intakes/files?${new URLSearchParams({ filename: label, source: `${namespace}-${source}`, designation: 'synthetic', profile: 'flat' })}`, { data: JSON.stringify(rows), headers: { 'Content-Type': 'application/octet-stream' } });
    expect(response.ok(), await response.text()).toBe(true);
    receipts.push({ ...await response.json(), label });
  }
  const workBefore = await (await page.request.get('/api/work')).json();
  await page.goto('/?view=reconciliation');
  for (const receipt of receipts) await page.getByRole('checkbox', { name: new RegExp(receipt.label.replaceAll('.', '\\.')) }).check();
  await page.getByLabel('Run reviewer', { exact: true }).fill('Synthetic triage reviewer');
  await page.getByLabel('Run reason', { exact: true }).fill('Review supplied identifier gaps separately from conflicts');
  const created = page.waitForResponse(response => response.url().endsWith('/api/reconciliation/runs') && response.request().method() === 'POST');
  await page.getByRole('button', { name: 'Create candidate run', exact: true }).click();
  const saved = await (await created).json();
  const laterWrites: string[] = [];
  page.on('request', request => { if (!['GET', 'HEAD'].includes(request.method())) laterWrites.push(`${request.method()} ${request.url()}`); });
  await expect(page.getByText('3 clinician candidates in this filter · Ranking expresses rule priority only.', { exact: true })).toBeVisible();
  await page.getByLabel('Review eligibility', { exact: true }).selectOption('false');
  await expect(page.getByRole('option', { name: 'NPI missing · 1 pair', exact: true })).toBeAttached();
  await expect(page.getByRole('option', { name: 'NPI conflict · 1 pair', exact: true })).toBeAttached();
  await page.getByLabel('Evidence reason', { exact: true }).selectOption('npi_missing');
  await expect(page.getByRole('status', { name: 'Evidence reason summary' })).toContainText('Showing 1 of 2 pairs');
  await expect(page.locator('.rc-candidates > details')).toHaveCount(1);
  await expect(page.locator('.rc-candidates')).toContainText('Synthetic Missing NPI');
  await expect(page.locator('.rc-candidates')).not.toContainText('Synthetic Conflicting NPI');
  const bookmark = page.url();
  await page.reload();
  await expect(page.getByLabel('Saved candidate run', { exact: true })).toHaveValue(saved.id);
  await expect(page.getByLabel('Review eligibility', { exact: true })).toHaveValue('false');
  await expect(page.getByLabel('Evidence reason', { exact: true })).toHaveValue('npi_missing');
  await expect(page.locator('.rc-candidates > details')).toHaveCount(1);
  expect(page.url()).toBe(bookmark);
  await page.locator('div.rc-filters').screenshot({ path: info.outputPath('evidence-reason-filters.png') });
  const pageResponse = await (await page.request.get(`/api/reconciliation/runs/${saved.id}/candidates?kind=clinician&eligible=false&reason=npi_missing&limit=1`)).json();
  expect(pageResponse.unfiltered_total).toBe(2);
  expect(pageResponse.reason_counts.npi_conflict).toBe(1);
  expect(pageResponse.reason_counts.npi_missing).toBe(1);
  expect(pageResponse.items[0].eligible).toBe(false);
  await page.getByRole('button', { name: 'Clear evidence reason', exact: true }).click();
  await expect(page.locator('.rc-candidates > details')).toHaveCount(2);
  await expect(page.getByRole('combobox', { name: 'Evidence reason' })).toHaveValue('');
  await page.goBack();
  await expect(page.getByRole('combobox', { name: 'Evidence reason' })).toHaveValue('npi_missing');
  await expect(page.locator('.rc-candidates > details')).toHaveCount(1);
  await page.getByRole('button', { name: 'Clear evidence reason' }).click();
  await page.getByLabel('Find a provider or identifier').fill('conflicting');
  await page.getByRole('button', { name: 'Search candidates' }).click();
  await expect(page.getByRole('status').filter({ hasText: 'Applied search: conflicting' })).toBeVisible();
  await page.locator('form').filter({ has: page.getByLabel('Find a provider or identifier') }).screenshot({ path: info.outputPath('candidate-search.png') });
  await expect(page.locator('.rc-candidates > details')).toHaveCount(1);
  await expect(page.locator('.rc-candidates')).toContainText('Synthetic Conflicting NPI');
  expect(new URL(page.url()).searchParams.get('candidate_search')).toBe('conflicting');
  const searchBookmark = page.url();
  await page.reload();
  await expect(page.getByLabel('Saved candidate run', { exact: true })).toHaveValue(saved.id);
  await expect(page.getByLabel('Review eligibility', { exact: true })).toHaveValue('false');
  await expect(page.getByLabel('Find a provider or identifier')).toHaveValue('conflicting');
  await expect(page.locator('.rc-candidates > details')).toHaveCount(1);
  expect(page.url()).toBe(searchBookmark);
  await page.goBack();
  await expect(page.getByLabel('Find a provider or identifier')).toHaveValue('');
  await expect(page.locator('.rc-candidates > details')).toHaveCount(2);
  await page.goForward();
  await expect(page.getByLabel('Find a provider or identifier')).toHaveValue('conflicting');
  await expect(page.locator('.rc-candidates > details')).toHaveCount(1);
  const downloadPromise = page.waitForEvent('download');
  await page.getByRole('link', { name: 'Download filtered candidate evidence (JSON)' }).click();
  const download = await downloadPromise;
  const downloaded = JSON.parse(await readFile((await download.path())!, 'utf8'));
  expect(downloaded.scope).toEqual({ kind: 'clinician', eligible: false, reason: null, search: 'conflicting' });
  expect(downloaded.total).toBe(1);
  expect(downloaded.candidates).toHaveLength(1);
  expect(downloaded.records).toHaveLength(2);
  await page.getByRole('button', { name: 'Clear search' }).click();
  await expect(page.locator('.rc-candidates > details')).toHaveCount(2);
  expect(new URL(page.url()).searchParams.has('candidate_search')).toBe(false);
  await page.goBack();
  await expect(page.getByLabel('Find a provider or identifier')).toHaveValue('conflicting');
  await expect(page.locator('.rc-candidates > details')).toHaveCount(1);
  expect(await (await page.request.get('/api/work')).json()).toEqual(workBefore);
  expect(laterWrites).toEqual([]);
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
  await test.info().attach('triage-page.json', { body: JSON.stringify(pageResponse, null, 2), contentType: 'application/json' });
});
