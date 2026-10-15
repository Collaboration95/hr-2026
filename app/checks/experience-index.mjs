import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import { harness, demo, plots, noOverflow, selectedCells } from '../tests/frozen-qa.mjs';
const qa = await harness('experience-index');
const { page, check, go, errors, shot, finish } = qa;
try {
  for (const width of [1440,390]) await check(`${width}px full cohort, default CSV and positive-cell keyboard navigation`, async () => {
    await page.setViewportSize({width,height:1000}); await go('#/cohort');
    assert.equal(await page.locator('.co-barcode tbody tr').count(), plots.length);
    const waiting = page.waitForEvent('download');
    await page.getByRole('button',{name:'Export displayed counts · CSV',exact:true}).click();
    const download = await waiting, csv = await readFile(await download.path(),'utf8');
    const expectedRows = plots.length * Object.keys(plots[0].source_result.yearly_loss_counts).length;
    assert.equal(csv.split('\r\n').filter(Boolean).length, expectedRows+1);
    assert.equal(download.suggestedFilename(),'plotline-source-counts-2001-2025.csv');
    assert.equal(await page.locator('.co-barcode tbody td.co-cell').count(),expectedRows);
    const positives = plots.reduce((n,p) => n + Object.values(p.source_result.yearly_loss_counts).filter(v => v > 0).length,0);
    assert.equal(await page.locator('.co-cell--hit button').count(),positives);
    await noOverflow(page); await shot(String(width));
    const button = page.getByRole('button',{name:'Review P-0005, 2025: 11 observed loss cells',exact:true});
    await button.focus(); await page.keyboard.press('Enter');
    await page.waitForFunction(() => document.activeElement.id === 'plot-review-heading');
    assert.equal(await page.locator('#plot-review-heading').innerText(),'P-0005');
    const focus = await page.evaluate(() => ({id:document.activeElement.id,top:document.activeElement.getBoundingClientRect().top,headerBottom:document.querySelector('.pl-topbar').getBoundingClientRect().bottom}));
    assert.ok(focus.top >= focus.headerBottom,JSON.stringify(focus));
    await selectedCells(page, demo.plots.find(p=>p.plot_id==='P-0005'),2025); await noOverflow(page);
    return {width,rows:plots.length,annualCells:expectedRows,csvRows:expectedRows,positiveButtons:positives,focus};
  });
  await check('experience index has no page errors',async()=>assert.deepEqual(errors,[]));
} finally { await finish(); }
