import { expect, test } from '@playwright/test';
import { spawn, execFileSync, type ChildProcess } from 'node:child_process';
import { mkdtemp, readFile } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

async function stopOwned(child:ChildProcess|undefined,group=false) {
  if(!child?.pid)return;
  const stop=(signal:NodeJS.Signals)=>{try{if(group)process.kill(-child.pid!,signal);else child.kill(signal);}catch(error){if((error as NodeJS.ErrnoException).code!=='ESRCH')throw error;}};
  stop('SIGTERM');
  if(child.exitCode!==null || child.signalCode!==null)return;
  await new Promise<void>(resolve=>{
    const timer=setTimeout(()=>stop('SIGKILL'),5000);
    child.once('exit',()=>{clearTimeout(timer);resolve();});
  });
}

test('combined retained workflow exposes held data, native findings, scoped NORTH handoff and independent contact consumer', async ({page}, info)=>{
  test.setTimeout(90_000);
  const parent=await mkdtemp(path.join(tmpdir(),'pdtl-operations-browser-'));
  const child=spawn('python3',['-u','scripts/browser_operations_api.py','--root',path.join(parent,'journey')],{
    cwd:path.resolve('..'),env:{...process.env,PYTHONPATH:'src'},stdio:['ignore','pipe','pipe'],
  });
  let output='';let errors='';
  let frontend:ChildProcess|undefined;
  child.stderr!.on('data',data=>{errors=(errors+data.toString()).slice(-8000);});
  try {
    const base=await new Promise<string>((resolve,reject)=>{
      const timer=setTimeout(()=>reject(new Error('Owned operations server startup timed out: '+errors)),30_000);
      child.once('error',error=>{clearTimeout(timer);reject(error);});
      child.once('exit',code=>{clearTimeout(timer);reject(new Error(`Owned operations server exited ${code}: ${errors}`));});
      child.stdout!.on('data',data=>{
        output+=data.toString();const match=output.match(/PDTL_OPERATIONS_URL=(http:\/\/127\.0\.0\.1:\d+)/);
        if(match){clearTimeout(timer);resolve(match[1]);}
      });
    });
    const result=await page.request.get(`${base}/__test/operations`);expect(result.ok(),await result.text()).toBe(true);
    const report=await result.json();
    // Use a real owned Vite proxy: Chromium's download-attribute requests can
    // bypass page-level request routing. Every UI request/download belongs to
    // the same prepared backend, as it does in the normal demo launcher.
    // Exercise CI's colored console even when the parent disables color. The
    // ready protocol reports the actual listener, independent of banner format.
    const frontendEnvironment:NodeJS.ProcessEnv={...process.env,PDTL_API:base,FORCE_COLOR:'1'};
    delete frontendEnvironment.NO_COLOR;
    frontend=spawn(process.execPath,[fileURLToPath(new URL('./support/operations-frontend.mjs',import.meta.url))],{
      cwd:path.resolve('.'),env:frontendEnvironment,detached:true,stdio:['ignore','pipe','pipe'],
    });
    let viteOutput='';let viteErrors='';frontend.stderr!.on('data',data=>{viteErrors=(viteErrors+data.toString()).slice(-4000);});
    const frontendBase=await new Promise<string>((resolve,reject)=>{
      const timer=setTimeout(()=>reject(new Error('Owned frontend startup timed out: '+viteErrors+'\n'+viteOutput)),15_000);
      frontend!.once('error',error=>{clearTimeout(timer);reject(error);});
      frontend!.once('exit',code=>{clearTimeout(timer);reject(new Error(`Owned frontend exited ${code}: ${viteErrors}`));});
      frontend!.stdout!.on('data',data=>{
        viteOutput+=data.toString();const match=viteOutput.match(/PDTL_OPERATIONS_FRONTEND_URL=(http:\/\/127\.0\.0\.1:\d+)/);
        if(match){clearTimeout(timer);resolve(match[1]);}
      });
    });
    await page.goto(`${frontendBase}/?view=feeds&feed=${report.feed_id}&version=${report.held_version_id}`);
    await expect(page.locator('.mf-current code')).toHaveText(report.approved_version_id);
    await expect(page.getByRole('heading',{name:'Dataset review · candidate',exact:true})).toBeVisible();
    await expect(page.getByText('missing_keys',{exact:true})).toBeVisible();
    const pending=page.waitForEvent('download');await page.getByRole('link',{name:'Download current approved JSON',exact:true}).click();
    const approvedPath=info.outputPath('approved.json');await (await pending).saveAs(approvedPath);
    const consumer=JSON.parse(execFileSync('python3',['-m','provider_directory_truth_layer.cli','consume-approved',approvedPath,
      '--expected-version',report.approved_version_id,'--expected-feed',report.feed_id],{cwd:path.resolve('..'),encoding:'utf8'}));
    expect(consumer.contacts.map((row:any)=>[row.location_id,row.phone,row.phone_extension,row.zip])).toEqual([
      ['NORTH','6175550100','007','02108'],['SOUTH','6175550200','008','02108']]);
    await page.goto(`${frontendBase}/?view=intake&receipt=${report.acquired_receipt_id}`);
    const native=page.getByRole('region',{name:'Native FHIR evidence',exact:true});
    await expect(native.getByText(/1 invalid resources/)).toBeVisible();
    await expect(native.getByRole('link',{name:'Download assembled searchset',exact:true})).toBeVisible();
    await expect(native.getByText(/Compatibility is unverified/)).toBeVisible();
    await page.goto(`${frontendBase}/?view=intake&receipt=${report.workbook_receipt_id}`);
    await page.getByRole('button',{name:'Profile and normalize',exact:true}).click();
    const assistant=page.getByRole('region',{name:'Optional mapping assistance',exact:true});
    await assistant.getByRole('button',{name:'Optional mapping assistance',exact:true}).click();
    await expect(assistant.getByText(/Mapping assistance unavailable/)).toBeVisible();
    await expect(assistant.getByRole('button',{name:'Queue model mapping',exact:true})).toBeDisabled();
    await page.goto(`${frontendBase}/?view=reconciliation`);
    await page.getByRole('button',{name:'Open reconciled field evidence',exact:true}).click();
    const fields=page.getByRole('region',{name:'Reconciled field evidence',exact:true});
    await fields.getByLabel('Find reviewed clinician',{exact:true}).fill(report.dossier.clinician_id);
    await fields.getByLabel('Reviewed clinician',{exact:true}).selectOption(report.dossier.clinician_id);
    await fields.getByLabel('Include a reviewed practice location',{exact:true}).check();
    await fields.getByLabel('Find reviewed practice location',{exact:true}).fill(report.dossier.reviewed_location_id);
    await fields.getByLabel('Reviewed practice location',{exact:true}).selectOption(report.dossier.reviewed_location_id);
    await expect(fields.getByText('Selected source assertion',{exact:true})).toBeVisible();
    const fieldDownload=page.waitForEvent('download');await fields.getByRole('button',{name:'Download reconciled JSON',exact:true}).click();
    const fieldPath=info.outputPath('north-fields.json');await (await fieldDownload).saveAs(fieldPath);
    const fieldPacket=JSON.parse(await readFile(fieldPath,'utf8'));
    expect(fieldPacket.fields.find((field:any)=>field.field==='phone').preferred_value).toEqual({number:'6175550199',extension:null});
    expect(fieldPacket.source_context.filter((context:any)=>context.receipt.id===report.acquired_receipt_id).map((context:any)=>context.row.locator)).not.toContain('$.entry[4].resource');
    expect(fieldPacket.fields.some((field:any)=>field.options.some((option:any)=>option.supporting_refs?.some((ref:any)=>ref.source_pages?.length)))).toBe(true);
    await page.goto(`${frontendBase}/?view=work&case=${report.north_case_id}`);
    await expect(page.getByText(/NORTH · reopened/)).toBeVisible();
    await expect(page.getByText(/Office reported its NORTH voice number/).first()).toBeVisible();
    const workDownload=page.waitForEvent('download');await page.getByRole('link',{name:'Download case JSON',exact:true}).click();
    const workPath=info.outputPath('north-investigation.json');await (await workDownload).saveAs(workPath);
    const work=JSON.parse(await readFile(workPath,'utf8'));
    expect(work.cases.map((item:any)=>item.id)).toEqual([report.north_case_id]);
    expect(work.investigations[0].outreach).toHaveLength(2);
    expect(work.evidence.every((row:any)=>row.normalized.location_id==='NORTH')).toBe(true);
    expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth)).toBe(true);
    await page.screenshot({path:info.outputPath('operations-north-handoff.png'),fullPage:true});
    await page.reload();await expect(page.getByText(/NORTH · reopened/)).toBeVisible();
    const current=await (await page.request.get(`${base}/api/feeds/${report.feed_id}/current`)).json();
    expect(current.version_id).toBe(report.approved_version_id);
  } finally {
    await stopOwned(frontend,true);
    await stopOwned(child);
  }
});
