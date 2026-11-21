import { navigateViaSidebar } from './support/navigation';
import { test, expect } from '@playwright/test';
import { mkdtempSync, readFileSync, writeFileSync } from 'node:fs';
import { join, resolve } from 'node:path';
import { tmpdir } from 'node:os';
import { createHash } from 'node:crypto';

test('managed recurring feed requires separate contract and dataset review, preserves pinned consumer JSON', async ({ page }, testInfo) => {
  const inbox = mkdtempSync(join(tmpdir(), 'pdtl-feed-e2e-'));
  const source = `synthetic-managed-${testInfo.project.name}-${Date.now()}`;
  const fields = ['record_id','npi','provider_name','address','city','state','zip','phone','location_id'];
  const baseline = readFileSync(resolve('../tests/fixtures/managed_feed/baseline.csv'));
  const actor = {actor: 'Synthetic browser coordinator', reason: 'Reviewed synthetic recurring delivery'};
  async function post(url: string, data: unknown) {
    const response = await page.request.post(url, {data});
    expect(response.ok(), await response.text()).toBe(true);
    return response.json();
  }
  const receiptResponse = await page.request.post(`/api/intakes/files?${new URLSearchParams({filename:'recipe.csv', source, dataset_scope:'weekly'})}`, {data:baseline, headers:{'Content-Type':'application/octet-stream'}});
  expect(receiptResponse.ok(), await receiptResponse.text()).toBe(true);
  const receipt = await receiptResponse.json();
  const proposal = await post(`/api/intakes/${receipt.id}/recipes`, {...actor, name:'Synthetic managed browser recipe',expected_attempt:receipt.attempt_id,definition:{version:1,mapping:Object.fromEntries(fields.map(field=>[field,field])),required:fields,transforms:{phone:['phone_us']}}});
  const recipe = await post(`/api/intakes/${receipt.id}/recipes/${proposal.id}/approve`, {...actor,expected_attempt:receipt.attempt_id});
  function deliver(fixture: string, id: string, period: string) {
    const data = readFileSync(resolve(`../tests/fixtures/managed_feed/${fixture}`));
    writeFileSync(join(inbox,`${id}.csv`), data);
    writeFileSync(join(inbox,`${id}.manifest.json`),JSON.stringify({delivery_id:id,period,as_of:period,snapshot:'full',filename:`${id}.csv`,sha256:createHash('sha256').update(data).digest('hex')}));
  }
  await page.goto('/?view=feeds');
  await expect(page.getByRole('heading',{name:'Review deliveries'})).toBeVisible();
  await page.getByLabel('Reviewer',{exact:true}).fill(actor.actor);
  await page.getByLabel('Decision reason',{exact:true}).fill(actor.reason);
  await page.getByText('Register a clinic CSV feed',{exact:true}).click();
  await page.getByLabel('Feed name',{exact:true}).fill(`Synthetic weekly ${testInfo.project.name}`);
  await page.getByRole('combobox',{name:'Approved source recipe',exact:true}).selectOption(recipe.id);
  await page.getByLabel('Local inbox directory',{exact:true}).fill(inbox);
  await page.getByLabel('Feed owner',{exact:true}).fill('Synthetic owner');
  await page.getByLabel('First expected period',{exact:true}).fill('2026-10-05');
  await page.getByRole('button',{name:'Register disabled feed'}).click();
  await expect(page.getByText('No contract revision yet.',{exact:true})).toBeVisible();
  await page.getByRole('combobox',{name:'Recipe for new contract',exact:true}).selectOption(recipe.id);
  await page.getByRole('button',{name:'Propose contract',exact:true}).click();
  await page.getByRole('button',{name:'Approve contract',exact:true}).click();
  await page.getByRole('button',{name:'Enable with this contract',exact:true}).click();
  deliver('baseline.csv','baseline','2026-10-05');
  if (!await page.getByRole('button', { name: 'Check deliveries and process one job' }).isVisible()) await page.getByText('Processing and delivery history', { exact: true }).click();
  await page.getByRole('button',{name:'Check deliveries and process one job'}).click();
  await expect(page.getByText('Delivery check completed. Review the processing history and candidate results.',{exact:true})).toBeVisible();
  const registry = await (await page.request.get('/api/feeds')).json();
  const feed = registry.items.find((item: {source:string})=>item.source===source);
  expect(feed.versions).toHaveLength(1);
  const firstId = feed.versions[0].id;
  if (await page.getByRole('button', {name:'← Back to deliveries',exact:true}).isVisible()) await page.getByRole('button', {name:'← Back to deliveries',exact:true}).click();
  await page.locator(`button[data-version-id="${firstId}"]`).click();
  await expect(page.getByRole('heading',{name:'Dataset review · candidate'})).toBeVisible();
  expect((await page.request.get(`/api/feed-versions/${firstId}/export`)).status()).toBe(422);
  await page.getByRole('button',{name:'Approve dataset version',exact:true}).click();
  await expect(page.getByRole('heading',{name:'Dataset review · approved'})).toBeVisible();
  const firstResponse = await page.request.get(`/api/feed-versions/${firstId}/export`);
  const original = await firstResponse.text();
  const first = JSON.parse(original);
  expect(first.records).toHaveLength(3);
  expect(first.records[0].normalized.zip).toBe('02108');
  await testInfo.attach('first-approved-dataset.json',{body:original,contentType:'application/json'});
  deliver('row_drop.csv','changed','2026-10-12');
  if (!await page.getByRole('button', { name: 'Check deliveries and process one job' }).isVisible()) await page.getByText('Processing and delivery history', { exact: true }).click();
  await page.getByRole('button',{name:'Check deliveries and process one job'}).click();
  await expect(page.getByText('Delivery check completed. Review the processing history and candidate results.',{exact:true})).toBeVisible();
  const nextFeed = await (await page.request.get(`/api/feeds/${feed.id}`)).json();
  const secondId = nextFeed.versions.at(-1).id;
  if (await page.getByRole('button', {name:'← Back to deliveries',exact:true}).isVisible()) await page.getByRole('button', {name:'← Back to deliveries',exact:true}).click();
  await page.locator(`button[data-version-id="${secondId}"]`).click();
  await expect(page.getByRole('button',{name:'Approve dataset version',exact:true})).toBeDisabled();
  expect((await (await page.request.get(`/api/feeds/${feed.id}/current`)).json()).version_id).toBe(firstId);
  await page.screenshot({path:testInfo.outputPath('held-candidate.png'),fullPage:true});
  await page.getByRole('button',{name:'Acknowledge missing_keys',exact:true}).click();
  await page.getByRole('button',{name:'Acknowledge row_count_drift',exact:true}).click();
  await page.getByRole('button',{name:'Approve dataset version',exact:true}).click();
  await expect(page.getByRole('heading',{name:'Dataset review · approved'})).toBeVisible();
  const downloadPromise=page.waitForEvent('download');
  await page.getByRole('link',{name:'Download this approved version JSON'}).click();
  const download=await downloadPromise;
  const file=await download.path();
  const exported=JSON.parse(readFileSync(file!,'utf8'));
  expect(exported.records).toHaveLength(1);
  expect(exported.exception_review).toHaveLength(2);
  expect(await (await page.request.get(`/api/feed-versions/${firstId}/export`)).text()).toBe(original);
  await page.screenshot({path:testInfo.outputPath('approved-feed.png'),fullPage:true});
  expect(await page.evaluate(()=>document.documentElement.scrollWidth<=window.innerWidth)).toBe(true);
});

test('quarantined rows require review and hard header failures remain blocked in the real interface', async ({page}, testInfo) => {
  const inbox=mkdtempSync(join(tmpdir(),'pdtl-feed-quality-'));
  const source=`synthetic-quality-${testInfo.project.name}-${Date.now()}`;
  const fields=['record_id','npi','provider_name','address','city','state','zip','phone','location_id'];
  const actor={actor:'Synthetic quality coordinator',reason:'Inspect excluded rows and retain limitations'};
  async function post(url:string,data:unknown) { const r=await page.request.post(url,{data});expect(r.ok(),await r.text()).toBe(true);return r.json(); }
  const raw=readFileSync(resolve('../tests/fixtures/managed_feed/baseline.csv'));
  const r=await page.request.post(`/api/intakes/files?${new URLSearchParams({filename:'recipe.csv',source,dataset_scope:'quality'})}`,{data:raw});
  const receipt=await r.json();
  const proposal=await post(`/api/intakes/${receipt.id}/recipes`,{...actor,name:'Synthetic quality recipe',expected_attempt:receipt.attempt_id,definition:{version:1,mapping:Object.fromEntries(fields.map(f=>[f,f])),required:fields,transforms:{phone:['phone_us']}}});
  const recipe=await post(`/api/intakes/${receipt.id}/recipes/${proposal.id}/approve`,{...actor,expected_attempt:receipt.attempt_id});
  let feed=await post('/api/feeds',{...actor,name:`Synthetic quality ${testInfo.project.name}`,source,scope:'quality',inbox,owner:'Synthetic owner',start_date:'2026-10-05'});
  const contract=await post(`/api/feeds/${feed.id}/contracts`,{...actor,definition:{recipe_revision_id:recipe.id,required_headers:fields}});
  const approved=await post(`/api/feeds/${feed.id}/contracts/${contract.id}/approve`,actor);
  feed=await post(`/api/feeds/${feed.id}/configure`,{...actor,expected_revision:feed.revision,config:{contract_id:approved.id,enabled:true}});
  function deliver(fixture:string,id:string,period:string) {const data=readFileSync(resolve(`../tests/fixtures/managed_feed/${fixture}`));writeFileSync(join(inbox,id+'.csv'),data);writeFileSync(join(inbox,id+'.manifest.json'),JSON.stringify({delivery_id:id,period,as_of:period,snapshot:'full',filename:id+'.csv',sha256:createHash('sha256').update(data).digest('hex')}));}
  deliver('invalid_phone.csv','quarantined','2026-10-05');
  feed=await post(`/api/feeds/${feed.id}/tick`,{});
  const first=feed.versions[0].id;
  await page.goto('/?view=feeds');
  await page.getByRole('button',{name:new RegExp(`Synthetic quality ${testInfo.project.name}`)}).click();
  if (await page.getByRole('button', {name:'← Back to deliveries',exact:true}).isVisible()) await page.getByRole('button', {name:'← Back to deliveries',exact:true}).click();
  await page.locator(`button[data-version-id="${first}"]`).click();
  await page.getByLabel('Reviewer',{exact:true}).fill(actor.actor);
  await page.getByLabel('Decision reason',{exact:true}).fill(actor.reason);
  await expect(page.getByRole('button',{name:'Approve dataset version',exact:true})).toBeDisabled();
  await page.getByRole('button',{name:'Acknowledge quarantine',exact:true}).click();
  await page.getByRole('button',{name:'Approve dataset version',exact:true}).click();
  await expect(page.getByRole('heading',{name:'Dataset review · approved'})).toBeVisible();
  const exported=await (await page.request.get(`/api/feed-versions/${first}/export`)).json();
  expect(exported.records).toHaveLength(2);expect(exported.quarantine).toHaveLength(1);
  deliver('header_drift.csv','drift','2026-10-12');
  if (!await page.getByRole('button', { name: 'Check deliveries and process one job' }).isVisible()) await page.getByText('Processing and delivery history', { exact: true }).click();
  await page.getByRole('button',{name:'Check deliveries and process one job'}).click();
  await expect(page.getByText('Delivery check completed. Review the processing history and candidate results.',{exact:true})).toBeVisible();
  feed=await (await page.request.get(`/api/feeds/${feed.id}`)).json();
  const second=feed.versions.at(-1).id;
  if (await page.getByRole('button', {name:'← Back to deliveries',exact:true}).isVisible()) await page.getByRole('button', {name:'← Back to deliveries',exact:true}).click();
  await page.locator(`button[data-version-id="${second}"]`).click();
  await expect(page.getByText('Missing required headers: phone',{exact:true})).toBeVisible();
  await expect(page.getByRole('button',{name:'Approve dataset version',exact:true})).toBeDisabled();
  await expect(page.getByRole('button',{name:/Acknowledge headers_missing/})).toHaveCount(0);
  await page.screenshot({path:testInfo.outputPath('hard-header-block.png'),fullPage:true});
  await page.getByRole('button',{name:'Reject candidate',exact:true}).click();
  await expect(page.getByRole('heading',{name:'Dataset review · rejected'})).toBeVisible();
  expect((await (await page.request.get(`/api/feeds/${feed.id}/current`)).json()).version_id).toBe(first);
  expect(await page.evaluate(()=>document.documentElement.scrollWidth<=window.innerWidth)).toBe(true);
});


test('default entry opens the work queue and an invalid version never selects another dataset', async ({ page }) => {
  await page.goto('/');
  await expect(page.getByRole('heading', { name: 'Provider work queue' })).toBeVisible();
  await page.goto('/?view=feeds&version=unknown-retained-version');
  await expect(page.getByRole('alert')).toContainText('A dataset version needs its feed context');
  await expect(page.getByRole('heading', { name: /Dataset review/ })).toHaveCount(0);
  await navigateViaSidebar(page, 'Legacy QA');
  await expect(page.getByText('Batch exception review')).toBeVisible();
  await page.goBack();
  await expect(page.getByRole('alert')).toContainText('A dataset version needs its feed context');
  await page.goForward();
  await expect(page.getByText('Batch exception review')).toBeVisible();
});

test('unavailable registry does not look empty and recovers on reload', async ({ page }) => {
  let unavailable = true;
  await page.route(/\/api\/feeds(?:\/recipes)?$/, async route => {
    if (route.request().url().endsWith('/api/feeds') && unavailable) {
      await route.fulfill({status:503, contentType:'application/json', body:JSON.stringify({detail:'Source registry unavailable'})});
      return;
    }
    await route.fulfill({status:200, contentType:'application/json', body:JSON.stringify({items:[]})});
  });
  await page.goto('/?view=feeds');
  await expect(page.getByRole('alert')).toContainText('Source registry unavailable');
  await expect(page.getByText('Registry information is unavailable.', {exact:false})).toBeVisible();
  await expect(page.getByText('No managed feeds yet.', {exact:false})).toHaveCount(0);
  unavailable = false;
  await page.getByRole('button', {name:'Reload evidence'}).click();
  await expect(page.getByRole('alert')).toHaveCount(0);
  await expect(page.getByText('No managed feeds yet.', {exact:false})).toBeVisible();
});
