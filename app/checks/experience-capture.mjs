import assert from 'node:assert/strict';
import { harness, noOverflow, selectedCells, plots } from '../tests/frozen-qa.mjs';
const {page,check,go,errors,shot,finish}=await harness('experience-capture');
try {
  await page.emulateMedia({reducedMotion:'reduce'});
  await check('capture canonical plot3 and plot5, proof and mobile review',async()=>{
    await go('#/map/P-0003/2025'); await selectedCells(page,plots.find(p=>p.plot_id==='P-0003'),2025);await shot('review-p3-desktop');
    await go('#/map/P-0005/2025'); await selectedCells(page,plots.find(p=>p.plot_id==='P-0005'),2025);await shot('review-p5-desktop');
    await page.locator('.pl-review__actions').getByRole('button',{name:'Proof',exact:true}).click();await page.locator('#proof-heading').waitFor();await shot('proof-desktop');
    await page.getByRole('button',{name:'Back to map',exact:true}).click();await page.locator('#plot-review-heading').waitFor();
    await page.setViewportSize({width:390,height:844});await noOverflow(page);await shot('review-p5-mobile');
    return {screenshots:4,fixture:'Canonical P-0003/P-0005; UI captures do not reverify the engine'};
  });
  await check('capture has no page errors',async()=>assert.deepEqual(errors,[]));
} finally {await finish();}
