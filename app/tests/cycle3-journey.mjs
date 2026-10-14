import { qaOrigin, qaEvidence } from '../scripts/qa-config.mjs';
import assert from 'node:assert/strict';
import { readFile, writeFile, mkdir } from 'node:fs/promises';
import { resolve } from 'node:path';
import { pathToFileURL } from 'node:url';

// Focused regression of the 02:32 integration. No artifact mutation or malicious fixtures.
const { chromium } = await import(process.env.PLAYWRIGHT_MODULE ? pathToFileURL(resolve(process.env.PLAYWRIGHT_MODULE)).href : 'playwright');
const origin = qaOrigin;
const out = qaEvidence; await mkdir(out, { recursive: true });
const demo = JSON.parse(await readFile('artifacts/demo-v1.json', 'utf8'));
const synthetic = JSON.parse(await readFile('artifacts/synthetic-v1.json', 'utf8'));
const p5 = demo.plots.find(p => p.plot_id === 'P-0005');
const browser = await chromium.launch({ headless: true, downloadsPath: out });
const context = await browser.newContext({ viewport: { width: 1440, height: 1000 }, acceptDownloads: true });
await context.route('**/*', r => new URL(r.request().url()).origin === origin ? r.continue() : r.abort());
const page = await context.newPage(); page.setDefaultTimeout(5000);
const checks = [], errors = [];
page.on('pageerror', e => errors.push(e.message));
async function check(name, fn) {
  try { const detail = await fn(); checks.push({ name, status: 'PASS', detail }); console.log(`PASS ${name}`); }
  catch (e) { checks.push({ name, status: 'FAIL', error: e.message }); console.log(`FAIL ${name}: ${e.message}`); }
}
async function select(id) {
  await page.locator('.queue-row').filter({ has: page.getByText(id, { exact: true }) }).click();
  await page.waitForFunction(id => document.querySelector('.plot-header h2')?.textContent.startsWith(id), id);
}
const shot = name => page.screenshot({ path: resolve(out, `w3-c3-${name}.png`), fullPage: false });
const note = () => page.getByRole('textbox', { name: 'Question or observation' });
const storageKey = `plotline:analyst-note:v1:${JSON.stringify([p5.receipt.supplier_row_sha256, 'P-0005'])}`;
async function downloadNote(filename) {
  const waiting = page.waitForEvent('download'); await page.getByRole('button', { name: 'Export note JSON', exact: true }).click();
  const d = await waiting; const path = resolve(out, filename); await d.saveAs(path);
  return JSON.parse(await readFile(path, 'utf8'));
}
async function focusBox(id) {
  return page.locator(`#${id}`).evaluate(el => { const r = el.getBoundingClientRect(); return { id: document.activeElement.id, top: r.top, bottom: r.bottom, viewport: innerHeight, text: el.textContent, scrollY }; });
}
try {
  await page.goto(origin); await page.getByRole('button', { name: 'Show proof', exact: true }).waitFor();
  await check('cycle3 accepted artifact matches canonical', async () => {
    assert.deepEqual(await page.evaluate(async () => (await fetch('/data/demo-v1.json')).json()), demo);
    return { content_sha256: demo.content_sha256, experiment_id: demo.benchmark.experiment_id, overall_storage_choice: demo.benchmark.overall_storage_choice };
  });
  await select('P-0005');
  await check('expanded cell table count → proof focus and scroll → return context', async () => {
    await page.getByRole('button', { name: 'Year 2025, 11 observed loss cells', exact: true }).click();
    await page.locator('.cell-table > summary').click();
    await page.getByRole('checkbox', { name: 'Only 2025 valid-land loss events (11)', exact: true }).check();
    assert.equal(await page.locator('.cell-table tbody tr').count(), 11);
    await page.locator('.cell-table tbody button').first().focus(); await page.keyboard.press('Enter');
    await page.locator('#annual-proof-trigger').focus(); await page.keyboard.press('Enter');
    await page.waitForFunction(() => document.activeElement.id === 'proof-selected-year');
    const arrival = await focusBox('proof-selected-year');
    assert.ok(arrival.top >= 0 && arrival.bottom <= arrival.viewport, JSON.stringify(arrival));
    assert.deepEqual(await page.locator('#proof-selected-year td').allTextContents(), ['11', '11']);
    await shot('proof-arrival');
    await page.getByRole('button', { name: 'Back to review', exact: true }).click();
    await page.waitForFunction(() => document.activeElement.id === 'annual-proof-trigger');
    const returned = await focusBox('annual-proof-trigger');
    assert.ok(returned.top >= 0 && returned.bottom <= returned.viewport, JSON.stringify(returned));
    assert.match(await page.locator('.plot-header h2').innerText(), /P-0005/);
    assert.match(await page.locator('.year-bars [aria-pressed=true]').getAttribute('aria-label'), /Year 2025/);
    await shot('proof-return'); return { arrival, returned, tableReopened: await page.locator('.cell-table').evaluate(e => e.open) };
  });
  const draftText = 'W3 regression draft — local test only; request the supplier evidence reference.';
  await check('integrated note drafts survive plot and proof switches', async () => {
    assert.equal(await note().inputValue(), ''); await note().fill(draftText);
    await select('P-0003'); assert.equal(await note().inputValue(), '');
    assert.match(await page.locator('.pl-notes').innerText(), /Unsaved drafts retained for P-0005/);
    await select('P-0005'); assert.equal(await note().inputValue(), draftText);
    await page.getByRole('button', { name: 'Show proof', exact: true }).click();
    await page.getByRole('button', { name: 'Back to review', exact: true }).click();
    assert.equal(await note().inputValue(), draftText);
    assert.equal(await page.evaluate(key => localStorage.getItem(key), storageKey), null);
  });
  await check('saved note survives reload under exact supplier-row context', async () => {
    await page.getByRole('button', { name: 'Save note', exact: true }).click();
    const saved = JSON.parse(await page.evaluate(key => localStorage.getItem(key), storageKey));
    assert.equal(saved.context_key, p5.receipt.supplier_row_sha256); assert.equal(saved.plot_id, 'P-0005'); assert.equal(saved.text, draftText);
    await page.reload(); await select('P-0005'); assert.equal(await note().inputValue(), draftText);
    const payload = await downloadNote('w3-c3-saved-note.json');
    assert.equal(payload.saved_locally, true); assert.equal(payload.saved_at, saved.saved_at); assert.equal(payload.context_key, saved.context_key);
    return { plot: saved.plot_id, context_key: saved.context_key, saved_locally: payload.saved_locally };
  });
  await check('unsaved note export is explicitly a draft and leaves evidence unchanged', async () => {
    await note().fill(`${draftText} Revised without saving.`);
    const payload = await downloadNote('w3-c3-draft-note.json');
    assert.equal(payload.saved_locally, false); assert.equal(payload.saved_at, null); assert.equal(payload.text, await note().inputValue());
    assert.equal(JSON.parse(await page.evaluate(key => localStorage.getItem(key), storageKey)).text, draftText);
    assert.deepEqual(await page.evaluate(async () => (await fetch('/data/demo-v1.json')).json()), demo);
    return { annotation_type: payload.annotation_type, saved_locally: payload.saved_locally };
  });
  await check('quota error keeps draft and previous saved note; retry recovers', async () => {
    await page.evaluate(() => { window.__w3SetItem = Storage.prototype.setItem; Storage.prototype.setItem = function(key, value) { if (key.startsWith('plotline:analyst-note:')) throw new DOMException('W3 local quota test', 'QuotaExceededError'); return window.__w3SetItem.call(this, key, value); }; });
    try {
      await page.getByRole('button', { name: 'Save note', exact: true }).click();
      assert.match(await page.locator('.pl-notes [role=alert]').innerText(), /Save failed/);
      assert.equal(JSON.parse(await page.evaluate(key => localStorage.getItem(key), storageKey)).text, draftText);
      assert.match(await note().inputValue(), /Revised without saving/); await shot('note-storage-error');
    } finally { await page.evaluate(() => { Storage.prototype.setItem = window.__w3SetItem; delete window.__w3SetItem; }); }
    await page.getByRole('button', { name: 'Save note', exact: true }).click();
    assert.equal(await page.locator('.pl-notes [role=alert]').count(), 0);
    assert.equal(JSON.parse(await page.evaluate(key => localStorage.getItem(key), storageKey)).text, await note().inputValue());
  });
  await check('supplier-context versions isolate actual notes component', async () => {
    // Separate temporary UI host; synthetic QA ID/context, never a fake cohort artifact.
    await page.evaluate(async () => {
      const React = (await import('/node_modules/.vite/deps/react.js')).default;
      const ReactDOM = (await import('/node_modules/.vite/deps/react-dom_client.js')).default;
      const Notes = (await import('/src/AnalystNotes.tsx')).default;
      const host = document.createElement('div'); host.id = 'w3-context-probe'; document.body.append(host);
      const root = ReactDOM.createRoot(host);
      window.__w3ContextMount = contextKey => root.render(React.createElement(Notes, { plotId: 'W3-TEST-CONTEXT', contextKey }));
      window.__w3ContextUnmount = () => { root.unmount(); host.remove(); };
      window.__w3ContextMount('version-A');
    });
    const field = page.locator('#w3-context-probe textarea'); await field.fill('Version A local QA draft');
    await page.evaluate(() => window.__w3ContextMount('version-B'));
    await page.waitForFunction(() => document.querySelector('#w3-context-probe textarea')?.value === '');
    await page.evaluate(() => window.__w3ContextMount('version-A'));
    await page.waitForFunction(() => document.querySelector('#w3-context-probe textarea')?.value === 'Version A local QA draft');
    await page.evaluate(() => { window.__w3ContextUnmount(); delete window.__w3ContextMount; delete window.__w3ContextUnmount; });
  });
  await check('storage read denial remains explicit without blocking evidence', async () => {
    const isolated = await browser.newContext();
    try {
      await isolated.addInitScript(() => { const original = Storage.prototype.getItem; Storage.prototype.getItem = function(key) { if (key.startsWith('plotline:analyst-note:')) throw new DOMException('W3 local read test', 'SecurityError'); return original.call(this, key); }; });
      const probe = await isolated.newPage(); await probe.goto(origin); await probe.getByRole('textbox', { name: 'Question or observation' }).waitFor();
      assert.match(await probe.locator('.pl-notes [role=alert]').innerText(), /saved note could not be read/);
      assert.equal(await probe.getByRole('textbox', { name: 'Question or observation' }).inputValue(), '');
      assert.match(await probe.locator('.plot-header').innerText(), /P-0003/);
    } finally { await isolated.close(); }
  });
  await check('overview layer controls, cohort extents and single-plot table scope', async () => {
    await page.getByRole('button', { name: 'All 17 plots', exact: true }).click();
    assert.equal(await page.locator('.map-toolbar .segmented button:disabled').count(), 3);
    assert.equal(await page.locator('.plot-geometry[role=button]').count(), 17);
    assert.equal(await page.locator('.overview-selected-label').textContent(), 'P-0005');
    assert.equal(await page.locator('.plot-geometry title').count(), 17);
    const coords = demo.plots.flatMap(p => p.geometry.coordinates.flat());
    const latitude = Math.max(...coords.map(p => p[1])).toFixed(5), longitude = Math.min(...coords.map(p => p[0])).toFixed(5);
    const labels = await page.locator('.spatial-map .map-coordinate').allTextContents();
    assert.ok(labels.includes(`${latitude}° N`)); assert.ok(labels.includes(`${longitude}° E · EPSG:4326`));
    assert.match(await page.locator('.cell-table summary').innerText(), /P-0005 · 262 selected/);
    await page.locator('.map-panel').scrollIntoViewIfNeeded(); await shot('overview');
    const overlap = await page.evaluate(() => {
      const title = document.querySelector('.map-title').getBoundingClientRect();
      return [...document.querySelectorAll('.plot-geometry')].filter(e => { const r = e.getBoundingClientRect(); return r.left < title.right && r.right > title.left && r.top < title.bottom && r.bottom > title.top; }).map(e => e.getAttribute('aria-label'));
    });
    // Preserve measured residual design issues separately from functional control checks.
    await writeFile(resolve(out, 'w3-c3-overview-title-overlap.json'), JSON.stringify({ overlap }, null, 2));
    await page.getByRole('button', { name: 'Focus plot', exact: true }).click();
    assert.equal(await page.locator('.map-toolbar .segmented button:disabled').count(), 0);
    return { latitude, longitude, plotScopedTable: 'P-0005 · 262 selected', markersOverlappingTitle: overlap };
  });
  await page.getByRole('button', { name: 'Show proof', exact: true }).click();
  await page.locator('.support-lab-disclosure > summary').click();
  await check('six actual synthetic cases × two periods stay outside real cohort', async () => {
    await page.locator('.lab-cases button').first().waitFor();
    const served = await page.evaluate(async () => (await fetch('/data/synthetic-v1.json')).json()); assert.deepEqual(served, synthetic);
    assert.equal(await page.locator('.lab-cases button').count(), 6);
    assert.match(await page.locator('.lab-disclaimer').innerText(), /not Hansen observations, supplier records, or part of the 17-plot evidence cohort/);
    const observations = [];
    for (let index = 0; index < synthetic.cases.length; index++) {
      const fixture = synthetic.cases[index]; await page.locator('.lab-cases button').nth(index).click();
      for (const [period, expected] of Object.entries(fixture.result.periods)) {
        await page.locator('.lab-period').getByRole('button', { name: period.replace('-', '–'), exact: true }).click();
        const signal = expected.mapped_loss_present === true ? 'Observed' : expected.mapped_loss_present === false ? 'Not observed under this query' : 'Unknown';
        assert.equal(await page.locator('.lab-signal strong').textContent(), signal);
        const count = expected.observed_loss_cell_count === null ? 'Analytical count unavailable' : `${expected.observed_loss_cell_count} observed loss cells`;
        assert.match(await page.locator('.lab-signal small').textContent(), new RegExp(count));
        const raw = JSON.parse(await page.locator('.edge-lab details pre').textContent());
        assert.equal(raw.synthetic, true); assert.equal(raw.case_id, fixture.case_id); assert.deepEqual(raw.result, fixture.result);
        observations.push({ case: fixture.case_id, period, signal, count });
      }
    }
    assert.match(await page.locator('.proof-secondary').innerText(), /17 \/ 17 plots/); assert.equal(await page.locator('.queue-row').count(), 17);
    await page.locator('.lab-result').scrollIntoViewIfNeeded(); await shot('edge-missing-band'); return observations;
  });
  await page.getByRole('button', { name: 'Back to review', exact: true }).click();
  await page.setViewportSize({ width: 390, height: 844 });
  await check('mobile timeline scrolls at readable size and retains selected year', async () => {
    await page.getByRole('button', { name: 'Year 2001, 0 observed loss cells', exact: true }).click();
    await page.getByRole('button', { name: 'Year 2025, 11 observed loss cells', exact: true }).click();
    const state = await page.locator('.year-bars').evaluate(bar => { const active = bar.querySelector('[aria-pressed=true]'), r = active.getBoundingClientRect(), b = bar.getBoundingClientRect(); return { selected: active.getAttribute('aria-label'), scrollWidth: bar.scrollWidth, clientWidth: bar.clientWidth, scrollLeft: bar.scrollLeft, font: parseFloat(getComputedStyle(active.querySelector('.year-label')).fontSize), selectedLeft: r.left, selectedRight: r.right, barLeft: b.left, barRight: b.right }; });
    await page.locator('.timeline').scrollIntoViewIfNeeded(); await shot('mobile-timeline');
    assert.ok(state.scrollWidth > state.clientWidth); assert.ok(state.font >= 12, JSON.stringify(state));
    assert.ok(state.selectedLeft >= state.barLeft - 1 && state.selectedRight <= state.barRight + 1, JSON.stringify(state));
    return state;
  });
  await check('mobile count proof focus and back restore visible count', async () => {
    await page.locator('.cell-table > summary').click();
    await page.locator('#annual-proof-trigger').focus(); await page.keyboard.press('Enter');
    await page.waitForFunction(() => document.activeElement.id === 'proof-selected-year'); const arrival = await focusBox('proof-selected-year');
    assert.ok(arrival.top >= 0 && arrival.bottom <= arrival.viewport, JSON.stringify(arrival)); await shot('mobile-proof-arrival');
    await page.getByRole('button', { name: 'Back to review', exact: true }).click();
    await page.waitForFunction(() => document.activeElement.id === 'annual-proof-trigger'); const returned = await focusBox('annual-proof-trigger');
    assert.ok(returned.top >= 0 && returned.bottom <= returned.viewport, JSON.stringify(returned)); return { arrival, returned };
  });
  await check('integrated notes fit mobile viewport', async () => {
    await page.getByRole('button', { name: 'Inspect declaration', exact: true }).click();
    await page.locator('.pl-notes').scrollIntoViewIfNeeded();
    const box = await page.locator('.pl-notes').evaluate(e => ({ width: e.clientWidth, scrollWidth: e.scrollWidth, documentWidth: document.documentElement.scrollWidth, viewport: innerWidth }));
    assert.ok(box.scrollWidth <= box.width + 1); assert.ok(box.documentWidth <= box.viewport + 1); await shot('mobile-notes'); return box;
  });
  await check('cycle3 application has no page errors', async () => { assert.deepEqual(errors, []); });
} finally {
  await browser.close();
  const report = { timestamp: new Date().toISOString(), scope: '02:32 cycle3 changed UI, not V5/V7 malformed fixtures', artifact: demo.content_sha256, checks, errors };
  await writeFile(resolve(out, 'w3-cycle3-results.json'), JSON.stringify(report, null, 2));
  const failed = checks.filter(c => c.status === 'FAIL').length;
  console.log(JSON.stringify({ passed: checks.length - failed, failed })); process.exitCode = failed ? 1 : 0;
}
