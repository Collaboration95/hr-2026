import assert from 'node:assert/strict';
import { harness, demo, noOverflow, selectedCells } from '../tests/frozen-qa.mjs';
const {page,check,go,shot,errors,finish} = await harness('experience-overview');
try {
  for (const width of [1440,390]) await check(`${width}px region markers clear controls and keyboard opens native evidence`,async()=>{
    await page.setViewportSize({width,height:1000}); await go('#/map');
    await page.locator('.pl-map[data-raster=ready]').waitFor();
    const measured = await page.evaluate(() => {
      // Region context now lives in the inspector. Map controls/coordinates are
      // the fixed obstructions that clickable plot markers must remain clear of.
      const controls = [...document.querySelectorAll('.pl-map__controls,.pl-map__coords')].map(e=>e.getBoundingClientRect());
      const markers = [...document.querySelectorAll('.pl-map__plot')].map(e=>{
        const r=e.querySelector('.pl-map__hit').getBoundingClientRect();
        return { name:e.getAttribute('aria-label'), overlapsControls:controls.some(b=>r.left<b.right && r.right>b.left && r.top<b.bottom && r.bottom>b.top) };
      });
      return {markers,viewport:innerWidth};
    });
    assert.equal(measured.markers.length,demo.plots.length);
    assert.deepEqual(measured.markers.filter(m=>m.overlapsControls),[]);
    await noOverflow(page); await shot(String(width));
    await page.getByRole('button',{name:'Select P-0003 on map',exact:true}).focus(); await page.keyboard.press('Enter');
    assert.equal(await page.locator('#plot-review-heading').innerText(),'P-0003');
    await selectedCells(page,demo.plots.find(p=>p.plot_id==='P-0003'),2025);
    assert.equal(await page.locator('.pl-scrub').getAttribute('data-mode'),'plot');
    assert.equal(await page.getByRole('group',{name:'Map layer',exact:true}).getByRole('button',{name:'Loss',exact:true}).isEnabled(),true);
    await noOverflow(page); return measured;
  });
  await check('experience overview has no page errors',async()=>assert.deepEqual(errors,[]));
} finally {await finish();}
