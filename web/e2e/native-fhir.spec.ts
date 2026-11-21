import { expect, test } from "@playwright/test";
import { readFile } from "node:fs/promises";
import path from "node:path";
import { execFileSync } from "node:child_process";

async function fixture() {
  const value = JSON.parse(await readFile(path.resolve('../tests/fixtures/intake/fhir-plannet/north-south.json'), 'utf8'));
  value.entry[0].resource.identifier.push({system:'http://hl7.org/fhir/sid/us-npi',value:'1000000001'});
  return Buffer.from(JSON.stringify(value));
}

test('saved native evidence reaches explicit acceptance, selected NORTH field review and lossless exports', async ({page}, info) => {
  const prefix = `native-fhir-${info.project.name}`;
  await page.goto('/?view=intake');
  await page.getByLabel('Source namespace', {exact:true}).fill(prefix);
  await page.getByRole('combobox',{name:'Response profile',exact:true}).selectOption('fhir-plannet-r4');
  await page.getByLabel('Source file', {exact:true}).setInputFiles({name:prefix+'.json',mimeType:'application/json',buffer:await fixture()});
  const received = page.waitForResponse(response => response.url().includes('/api/intakes/files?') && response.request().method()==='POST');
  await page.getByRole('button',{name:'Upload and preview',exact:true}).click();
  const upload = await received; expect(upload.ok(),await upload.text()).toBe(true);
  const native = await upload.json();
  const panel = page.getByRole('region',{name:'Native FHIR evidence',exact:true});
  await expect(panel).toBeVisible();
  await expect(panel.getByText(/9 entries · 8 supported · 8 eligible/)).toBeVisible();
  await expect(panel.getByText(/unresolved · Practitioner\/not-present/)).toBeVisible();
  await expect(panel.getByText('unsupported_resource',{exact:true})).toBeVisible();
  await expect(panel.getByText(/Profile validation:/)).toContainText('not run');
  await expect(page.getByText('Column mapping and parsing',{exact:true})).toHaveCount(0);
  await expect(page.getByRole('button',{name:'Profile and normalize',exact:true})).toHaveCount(0);
  await panel.getByLabel('Reference reviewer',{exact:true}).fill('Synthetic analyst');
  await panel.getByLabel('Reference review reason',{exact:true}).fill('Review saved two-office directory evidence');
  await panel.getByRole('button',{name:'Accept reference resources',exact:true}).click();
  await expect(panel.getByRole('button',{name:'Accept reference resources',exact:true})).toBeDisabled();
  await expect(panel.getByText('committed',{exact:true})).toBeVisible();
  const download = page.waitForEvent('download');
  await panel.getByRole('link',{name:'Evidence packet JSON',exact:true}).click();
  const packetPath = info.outputPath('native-packet.json'); await (await download).saveAs(packetPath);
  const packet = JSON.parse(await readFile(packetPath,'utf8'));
  expect(packet.observations).toHaveLength(8);
  expect(packet.cases).toEqual([]);
  expect(packet.preview.native.coverage.assertion_count).toBe(2);
  expect(packet.observations.filter((o:any)=>o.original.resourceType==='Location').every((o:any)=>o.provider_id===null)).toBe(true);
  await page.reload();
  await expect(panel.getByText('committed',{exact:true})).toBeVisible();
  await panel.screenshot({path:info.outputPath('native-review.png')});
  expect(await page.evaluate(()=>document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);

  // Reviewed identity fixture uses the same service requests as IdentityReview.
  const clinicUpload = await page.request.post(`/api/intakes/files?filename=clinic.json&source=${prefix}-clinic`,{data:Buffer.from(JSON.stringify([{
    record_id:'NORTH', npi:'1000000001', entity_type:'clinician', provider_name:'Synthetic Example', address:'10 Example St', city:'Example', state:'MA', zip:'02108', phone:'6175550199', location_id:'NORTH',
  }]))});
  expect(clinicUpload.ok()).toBe(true); const clinic = await clinicUpload.json();
  const runResponse = await page.request.post('/api/reconciliation/runs',{data:{inputs:[native,clinic].map(r=>({receipt_id:r.id,attempt_id:r.attempt_id})),actor:'Synthetic reviewer',reason:'Compare retained NORTH evidence'}});
  expect(runResponse.ok(),await runResponse.text()).toBe(true); const run=await runResponse.json();
  const candidates=(await (await page.request.get(`/api/reconciliation/runs/${run.id}/candidates?limit=100`)).json()).items;
  const targets:Record<string,string>={};
  for (const kind of ['clinician','location']) {
    const candidate=candidates.find((c:any)=>c.kind===kind && (kind==='clinician'||c.left_record.comparison.address.line1===c.right_record.comparison.address.line1));
    const current=await (await page.request.get(`/api/reconciliation/runs/${run.id}/candidates/${candidate.id}/review`)).json();
    const response=await page.request.post('/api/reconciliation/links',{data:{run_id:run.id,candidate_id:candidate.id,decision:'approve',request_id:crypto.randomUUID(),expected_snapshot:current.review_snapshot,expected_revisions:Object.fromEntries(Object.entries(current.current_links).map(([ref,link])=>[ref,(link as any)?.id??null])),expected_decision:current.latest_decision?.id??null,actor:'Synthetic reviewer',reason:'Explicit native identity review',new_label:`${prefix} ${kind}`}});
    expect(response.ok(),await response.text()).toBe(true);targets[kind]=(await response.json()).decision.target_id;
  }
  await page.goto('/?view=reconciliation');
  await page.getByRole('button',{name:'Open reconciled field evidence',exact:true}).click();
  const fields=page.getByRole('region',{name:'Reconciled field evidence',exact:true});
  await fields.getByLabel('Find reviewed clinician',{exact:true}).fill(targets.clinician);
  await fields.getByLabel('Reviewed clinician',{exact:true}).selectOption(targets.clinician);
  await fields.getByLabel('Include a reviewed practice location',{exact:true}).check();
  await fields.getByLabel('Find reviewed practice location',{exact:true}).fill(targets.location);
  await fields.getByLabel('Reviewed practice location',{exact:true}).selectOption(targets.location);
  const phone=fields.getByRole('region',{name:'phone reconciliation',exact:true});
  await phone.getByLabel('Decision for phone',{exact:true}).selectOption('select');
  await phone.getByRole('radio',{name:new RegExp(`Choose phone from ${prefix} `)}).check();
  for (const provenance of await phone.getByText('Source provenance',{exact:true}).all()) await provenance.click();
  await expect(phone.getByText(/Contributing FHIR resources/)).toBeVisible();
  await phone.getByLabel('Actor for phone',{exact:true}).fill('Synthetic reviewer');
  await phone.getByLabel('Reason for phone',{exact:true}).fill('Reviewed NORTH phone source paths');
  await phone.getByLabel('I reviewed phone source evidence',{exact:true}).check();
  await phone.getByRole('button',{name:'Save phone decision',exact:true}).click();
  await expect(phone.getByText('Selected source assertion',{exact:true})).toBeVisible();
  const jsonDownload=page.waitForEvent('download');await fields.getByRole('button',{name:'Download reconciled JSON',exact:true}).click();
  const selectedPath=info.outputPath('native-north.json');await (await jsonDownload).saveAs(selectedPath);
  const selected=JSON.parse(await readFile(selectedPath,'utf8'));
  expect(selected.fields.find((f:any)=>f.field==='phone').preferred_value).toEqual({number:'617-555-0100',extension:null});
  const locators=selected.source_context.filter((c:any)=>c.receipt.id===native.id).map((c:any)=>c.row.locator);
  expect(locators).toContain('$.entry[3].resource');expect(locators).not.toContain('$.entry[4].resource');
  const xlsxDownload=page.waitForEvent('download');await fields.getByRole('button',{name:'Download reconciled XLSX',exact:true}).click();
  const workbookPath=info.outputPath('native-north.xlsx');await (await xlsxDownload).saveAs(workbookPath);
  const decoded=JSON.parse(execFileSync('python3',['-c','import sys,json;from openpyxl import load_workbook;b=load_workbook(sys.argv[1],read_only=True);print("".join(r[1] for r in sorted(b["Payload"].iter_rows(min_row=2,values_only=True),key=lambda r:int(r[0]))));b.close()',workbookPath],{encoding:'utf8'}));
  expect(decoded.scope).toEqual(selected.scope);expect(decoded.source_context).toEqual(selected.source_context);
});

test('native stale review and lost acceptance response recover without duplicate observations', async ({page}, info) => {
  const uploaded=await page.request.post(`/api/intakes/files?filename=retry.json&profile=fhir-plannet-r4&source=native-retry-${info.project.name}`,{data:await fixture()});
  const receipt=await uploaded.json();expect(uploaded.ok(),await uploaded.text()).toBe(true);
  await page.goto(`/?view=intake&receipt=${receipt.id}`);
  const panel=page.getByRole('region',{name:'Native FHIR evidence',exact:true});
  await panel.getByLabel('Reference reviewer',{exact:true}).fill('Synthetic retry reviewer');
  await panel.getByLabel('Reference review reason',{exact:true}).fill('Review retained source');
  const reprocessed=await page.request.post(`/api/intakes/${receipt.id}/mapping`,{data:{expected_attempt:receipt.attempt_id}});
  expect(reprocessed.ok()).toBe(true);
  await panel.getByRole('button',{name:'Accept reference resources',exact:true}).click();
  await expect(panel.getByRole('alert')).toContainText('Interpretation changed');
  await expect(panel.getByLabel('Reference review reason',{exact:true})).toHaveValue('Review retained source');
  await panel.getByRole('button',{name:'Refresh native evidence',exact:true}).click();
  await expect(panel.getByText((await reprocessed.json()).attempt_id,{exact:true})).toBeVisible();
  const requestIds:string[]=[];
  await page.route(`**/api/intakes/${receipt.id}/commit`,async route=>{
    requestIds.push(route.request().postDataJSON().request_id);
    if(requestIds.length===1){const response=await route.fetch();expect(response.ok()).toBe(true);await route.abort('failed');}
    else await route.continue();
  });
  await panel.getByRole('button',{name:'Accept reference resources',exact:true}).click();
  await expect(panel.getByRole('alert')).toContainText('reviewer and reason are preserved');
  await panel.getByRole('button',{name:'Accept reference resources',exact:true}).click();
  await expect(panel.getByText('committed',{exact:true})).toBeVisible();
  expect(requestIds).toHaveLength(2);expect(requestIds[0]).toBe(requestIds[1]);
  const packet=await (await page.request.get(`/api/intakes/${receipt.id}/packet`)).json();
  expect(packet.observations).toHaveLength(8);expect(packet.cases).toEqual([]);
  await panel.getByRole('button',{name:'Reprocess saved FHIR evidence',exact:true}).click();
  await expect(panel.getByText('preview ready',{exact:true})).toBeVisible();
  await panel.getByRole('button',{name:'Reject reference intake',exact:true}).click();
  await expect(panel.getByText('rejected',{exact:true})).toBeVisible();
  await page.reload();await expect(panel.getByText('rejected',{exact:true})).toBeVisible();
});
