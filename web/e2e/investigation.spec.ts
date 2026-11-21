import {expect, test} from '@playwright/test';
import {readFile} from 'node:fs/promises';

test('synthetic office investigation retains outreach and verifies a separate downstream observation', async ({page}, info) => {
  test.setTimeout(150_000);
  const csv = 'record_id,npi,provider_name,address,city,state,zip,phone,location_id,reference_phone\nN,1000000001,Synthetic Investigator,10 Example St,Example,MA,02108,6175550100,NORTH,6175550199\nS,1000000001,Synthetic Investigator,20 Example St,Example,MA,02108,6175550200,SOUTH,6175550299\n';
  const receipt = await (await page.request.post(`/api/intakes/files?filename=synthetic-investigation.csv&source=investigation-${info.project.name}`, {data:csv})).json();
  const acceptedResponse = await page.request.post(`/api/intakes/${receipt.id}/commit`, {data:{actor:'Synthetic analyst',reason:'Fixture reviewed',policy:'valid_rows',expected_attempt:receipt.attempt_id}});
  expect(acceptedResponse.ok()).toBe(true);
  const accepted = await acceptedResponse.json();
  const north = accepted.linked_cases.find((c: any) => c.kind === 'correction' && c.location_id.endsWith(':NORTH'));
  const south = accepted.linked_cases.find((c: any) => c.kind === 'correction' && c.location_id.endsWith(':SOUTH'));
  const southBefore = await (await page.request.get(`/api/work/${south.id}`)).json();
  const laterCsv = csv.split('\n').slice(0,2).join('\n').replace('6175550100','6175550101') + '\n';
  const laterReceipt = await (await page.request.post(`/api/intakes/files?filename=synthetic-incomplete-delivery.csv&source=investigation-${info.project.name}`, {data:laterCsv})).json();
  const laterAccepted = await page.request.post(`/api/intakes/${laterReceipt.id}/commit`, {data:{actor:'Synthetic analyst',reason:'Bounded NORTH-only evidence; no SOUTH closure',policy:'valid_rows',expected_attempt:laterReceipt.attempt_id}});
  expect(laterAccepted.ok()).toBe(true);
  await page.goto(`/?view=work&case=${north.id}`);
  await expect(page.getByRole('heading',{name:'Synthetic Investigator'})).toBeVisible();
  const form = page.locator('.iw-decision');
  async function save(action: string, values: Record<string,string>) {
    await form.getByRole('combobox',{name:'Action',exact:true}).selectOption(action);
    await form.getByLabel('actor *',{exact:true}).fill('Synthetic analyst');
    await form.getByLabel('reason *',{exact:true}).fill('Synthetic office investigation');
    for (const [key,value] of Object.entries(values)) {
      const control = form.getByLabel(new RegExp(`^${key.replaceAll('_',' ')}(?: \\*)?$`));
      if (key === 'method' || key === 'outcome') await form.getByRole('combobox',{name:key,exact:true}).selectOption(value); else await control.fill(value);
    }
    const response = page.waitForResponse(r => r.url().endsWith(`/api/work/${north.id}/events`) && r.request().method()==='POST');
    await form.getByRole('button',{name:'Save review event'}).click();
    expect((await response).ok()).toBe(true);
    await expect(form.getByRole('button',{name:'Save review event'})).toBeEnabled();
  }
  await save('assign',{owner:'Synthetic analyst',follow_up:'2026-11-04'});
  await save('outreach',{contact_at:'2026-11-03T09:00:00-05:00',outcome:'no_answer',contact_target:'Synthetic NORTH office'});
  await save('outreach',{contact_at:'2026-11-03T10:00:00-05:00',outcome:'response_received',response_summary:'Office supplied NORTH number',reported_phone:'6175550199',respondent_role:'Office manager'});
  await expect(page.getByText(/Reported phone: 6175550199/)).toBeVisible();
  await save('triage',{});
  await save('approve',{proposal:'6175550199'});
  await save('submit',{submission_reference:'SIMULATED directory ticket'});
  await save('verify',{observed:'6175550199',verification_note:'Synthetic downstream listing inspected separately'});
  await page.reload();
  await expect(page.getByText('NORTH · verified',{exact:false})).toBeVisible();
  await expect(page.getByText(/Office supplied NORTH number/).first()).toBeVisible();
  const downloadEvent = page.waitForEvent('download');
  await page.getByRole('link',{name:'Download case JSON'}).click();
  const download = await downloadEvent;
  const path = info.outputPath('synthetic-investigation.json');await download.saveAs(path);
  const packet = JSON.parse(await readFile(path,'utf8'));
  expect(packet.investigations).toHaveLength(1);
  expect(packet.evidence).toHaveLength(2);
  expect(packet.investigations[0].outreach).toHaveLength(2);
  expect(packet.investigations[0].status).toBe('verified');
  expect(await (await page.request.get(`/api/work/${south.id}`)).json()).toEqual(southBefore);
  await page.screenshot({path:info.outputPath('synthetic-investigation.png'),fullPage:true});
});
