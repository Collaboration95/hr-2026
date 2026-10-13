// C2-C bounded observation capture. Uses existing local Playwright; no installs.
import { chromium } from '/Users/speedpowermac/.npm/_npx/e41f203b7505f1fb/node_modules/playwright/index.mjs';
import { mkdir, writeFile, readFile } from 'node:fs/promises';
import { createHash } from 'node:crypto';
import { resolve } from 'node:path';
const dir = resolve('docs/lab/experience-design-evidence');
await mkdir(dir, {recursive:true});
const hashes = async () => Object.fromEntries(await Promise.all(['app/src/App.tsx','app/src/Benchmark.tsx','app/src/CellTable.tsx','app/src/app.css'].map(async p=>[p,createHash('sha256').update(await readFile(p)).digest('hex')])));
const report={started:new Date().toISOString(),startHashes:await hashes(),viewports:[],errors:[]};
const browser=await chromium.launch({headless:true});
try {
 for(const [name,width,height] of [['desktop',1440,1000],['tablet',834,1112],['mobile',390,844]]) {
  const context=await browser.newContext({viewport:{width,height},reducedMotion:'reduce'});
  await context.route('**/*',r=>new URL(r.request().url()).origin==='http://127.0.0.1:5173'?r.continue():r.abort());
  const page=await context.newPage(); page.setDefaultTimeout(5000);
  page.on('pageerror',e=>report.errors.push({name,error:e.message}));
  const out={name,width,height}; report.viewports.push(out);
  const shot=async label=>{await page.screenshot({path:resolve(dir,`${name}-${label}.png`),fullPage:true});};
  const geometry=async selectors=>page.evaluate(selectors=>Object.fromEntries(selectors.map(s=>{const e=document.querySelector(s);if(!e)return[s,null];const r=e.getBoundingClientRect();const cs=getComputedStyle(e);return[s,{text:e.innerText?.slice(0,2400),x:r.x,y:r.y,width:r.width,height:r.height,fontSize:cs.fontSize,lineHeight:cs.lineHeight}]})),selectors);
  const focus=()=>page.evaluate(()=>({tag:document.activeElement.tagName,name:(document.activeElement.getAttribute('aria-label')||document.activeElement.textContent||'').slice(0,180),visible:document.activeElement.matches(':focus-visible'),scrollY,rect:document.activeElement.getBoundingClientRect().toJSON()}));
  await page.goto('http://127.0.0.1:5173'); await page.getByRole('button',{name:'Show proof',exact:true}).waitFor();
  out.artifact=await page.evaluate(async()=>{const d=await(await fetch('/data/demo-v1.json')).json();return {content_sha256:d.content_sha256,query_version:d.query_version,benchmark_experiment:d.benchmark?.experiment_id,overall_storage_choice:d.benchmark?.overall_storage_choice,baseline_storage:d.benchmark?.baseline?.storage,winner:d.benchmark?.winner,plots:d.plots.filter(p=>['P-0003','P-0005'].includes(p.plot_id)).map(p=>({plot_id:p.plot_id,selected:p.source_result.selected_cell_count,support:p.source_result.support,periods:p.source_result.periods,year2025:p.source_result.yearly_loss_counts['2025'],comparison:p.comparison}))}});
  out.p3=await geometry(['.plot-header','.map-panel','.map-legend','.timeline','.declaration','.reference-note','.observation','.observation .fineprint','.time-context']);
  await shot('p3-review');
  await page.getByRole('button',{name:'All 17 plots',exact:true}).click();
  out.overview=await page.evaluate(()=>({title:document.querySelector('.map-title').innerText,footnote:document.querySelector('.map-footnote').innerText,table:document.querySelector('.cell-table summary').innerText,coordinates:[...document.querySelectorAll('.map-coordinate')].map(e=>e.textContent),markers:[...document.querySelectorAll('.plot-geometry')].map(e=>({name:e.getAttribute('aria-label'),text:e.textContent,title:e.querySelector('title')?.textContent})),legend:document.querySelector('.map-legend')?.innerText??null}));
  await shot('overview');
  await page.getByRole('button',{name:'Focus plot',exact:true}).click();
  await page.locator('.queue-row').filter({hasText:'P-0005'}).click();
  await page.getByRole('button',{name:'Year 2025, 11 observed loss cells',exact:true}).click();
  out.p5=await geometry(['.plot-header','.map-legend','.timeline','.declaration']);
  out.p5.visibleLossCells=await page.locator('.native-cell[fill="#df743f"]').count();
  await page.locator('.cell-table summary').click();
  await page.getByLabel('Only 2025 valid-land loss events (11)').check();
  out.p5.tableRows=await page.locator('.cell-table tbody tr').count();
  await page.locator('.cell-table tbody button').first().focus(); await page.keyboard.press('Enter');
  out.p5.inspectFocus=await focus();
  out.p5.inspector=await geometry(['.cell-inspector']);
  await shot('p5-cells');
  await page.getByRole('button',{name:'Inspect proof for 2025 observed loss cells',exact:true}).focus();
  out.beforeProof=await focus(); await page.keyboard.press('Enter');
  await page.locator('.proof-heading').waitFor();
  out.afterProof=await focus();out.proof=await geometry(['.plot-header','.proof-heading','.agreement','.comparison-table','.proof-actions','.benchmark']);
  await page.screenshot({path:resolve(dir,`${name}-proof-arrival-viewport.png`),fullPage:false});
  await page.keyboard.press('Tab');out.afterProofNextTab=await focus();
  await shot('p5-proof');
  await page.getByRole('button',{name:'Inspect provenance receipt',exact:true}).focus();await page.keyboard.press('Enter');
  out.receipt={text:await page.locator('dialog').innerText(),focus:await focus()};
  await shot('p5-receipt');await page.keyboard.press('Escape');out.receipt.returnFocus=await focus();
  out.benchmarkDefault=await geometry(['.benchmark-decision','.candidate-detail','.benchmark-method','.benchmark .json-details summary']);
  await page.locator('.storage-row').filter({hasText:'Original GeoTIFF'}).click();out.baseline=await geometry(['.candidate-detail']);
  out.storageRows=await page.locator('.storage-row').allInnerTexts();
  await page.locator('.storage-row').nth(1).click();out.candidate=await geometry(['.candidate-detail']);
  await page.getByText('Inspect measurement method, environment and experiment identity',{exact:true}).click();
  out.method=await page.locator('.benchmark details').first().innerText();
  await shot('benchmark-method');
  await context.close();
 }
}catch(e){report.errors.push({fatal:e.stack});process.exitCode=1}
finally {await browser.close();report.endHashes=await hashes();report.ended=new Date().toISOString();await writeFile(resolve(dir,'observations.json'),JSON.stringify(report,null,2));console.log(JSON.stringify({viewports:report.viewports.map(v=>v.name),errors:report.errors,sourceStable:JSON.stringify(report.startHashes)===JSON.stringify(report.endHashes)}))}
