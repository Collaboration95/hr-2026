import { qaOrigin, qaEvidence } from '../scripts/qa-config.mjs';
import assert from 'node:assert/strict';
import { readFile, writeFile, mkdir } from 'node:fs/promises';
import { resolve } from 'node:path';
import { pathToFileURL } from 'node:url';

// Frozen review regression adapted to the map-first redesign. Notes and the six
// synthetic support fixtures retain their original semantics; artifacts stay untouched.
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
  await page.locator('.plot-row').filter({ has: page.getByText(id, { exact: true }) }).click();
  await page.waitForFunction(id => document.querySelector('#plot-review-heading')?.textContent.startsWith(id), id);
  await openNote();
}
const shot = name => page.screenshot({ path: resolve(out, `w3-c3-${name}.png`), fullPage: false });
async function openNote() { const disclosure = page.locator('details').filter({ has: page.locator('summary').filter({ hasText: /^Analyst note/ }) }); if (!(await disclosure.evaluate(e => e.open))) await disclosure.locator('summary').click(); }
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
  await page.goto(`${origin}/#/map/P-0005/2025`); await page.locator('.pl-review__actions').getByRole('button', { name: 'Proof', exact: true }).waitFor();
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
    assert.deepEqual(await page.locator('#proof-selected-year td').allTextContents(), ['11', '11', 'same']);
    await shot('proof-arrival');
    await page.getByRole('button', { name: 'Back to map', exact: true }).click();
    await page.waitForFunction(() => document.activeElement.id === 'annual-proof-trigger');
    const returned = await focusBox('annual-proof-trigger');
    assert.ok(returned.top >= 0 && returned.bottom <= returned.viewport, JSON.stringify(returned));
    assert.match(await page.locator('#plot-review-heading').innerText(), /P-0005/);
    assert.match(await page.locator('.pl-scrub__cols [aria-pressed=true]').getAttribute('aria-label'), /Year 2025/);
    await shot('proof-return'); return { arrival, returned, tableReopened: await page.locator('.cell-table').evaluate(e => e.open) };
  });
  const draftText = 'W3 regression draft — local test only; request the supplier evidence reference.';
  await check('integrated note drafts survive plot and proof switches', async () => {
    await openNote(); assert.equal(await note().inputValue(), ''); await note().fill(draftText);
    await select('P-0003'); assert.equal(await note().inputValue(), '');
    assert.match(await page.locator('.pl-notes').innerText(), /Unsaved drafts retained for P-0005/);
    await select('P-0005'); assert.equal(await note().inputValue(), draftText);
    await page.locator('.pl-review__actions').getByRole('button', { name: 'Proof', exact: true }).click();
    await page.getByRole('button', { name: 'Back to map', exact: true }).click();
    await openNote(); assert.equal(await note().inputValue(), draftText);
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
    await isolated.route('**/*', r => new URL(r.request().url()).origin === origin ? r.continue() : r.abort());
    try {
      await isolated.addInitScript(() => { const original = Storage.prototype.getItem; Storage.prototype.getItem = function(key) { if (key.startsWith('plotline:analyst-note:')) throw new DOMException('W3 local read test', 'SecurityError'); return original.call(this, key); }; });
      const probe = await isolated.newPage(); probe.on('pageerror', e => errors.push(e.message)); await probe.goto(`${origin}/#/map/P-0003/2025`); await probe.locator('details > summary').filter({ hasText: /^Analyst note/ }).click(); await probe.getByRole('textbox', { name: 'Question or observation' }).waitFor();
      assert.match(await probe.locator('.pl-notes [role=alert]').innerText(), /saved note could not be read/);
      assert.equal(await probe.getByRole('textbox', { name: 'Question or observation' }).inputValue(), '');
      assert.match(await probe.locator('.pl-review__head').innerText(), /P-0003/);
    } finally { await isolated.close(); }
  });
  await check('region raster layer controls, cohort extents and plot table scope', async () => {
    await page.getByRole('button', { name: 'Region', exact: true }).click();
    await page.locator('.pl-scrub[data-mode=region]').waitFor();
    await page.locator('.pl-map[data-raster=ready]').waitFor();
    assert.equal(await page.getByRole('button', { name: /Select P-\d+ on map/ }).count(), demo.plots.length);
    assert.equal(await page.locator('.pl-scrub').getAttribute('data-mode'), 'region');
    assert.equal(await page.locator('.cell-table').count(), 0);
    for (const label of ['Loss', 'Canopy 2000', 'Land mask']) {
      const button = page.getByRole('group', { name: 'Map layer', exact: true }).getByRole('button', { name: label, exact: true });
      assert.equal(await button.isEnabled(), true); await button.click(); assert.equal(await button.getAttribute('aria-pressed'), 'true');
    }
    const manifest = await page.evaluate(async () => (await fetch('/region/manifest.json')).json());
    const coords = demo.plots.flatMap(p => p.geometry.coordinates.flat());
    const [w,s,e,n] = manifest.hansen.bounds_west_south_east_north;
    assert.ok(coords.every(([x,y]) => x >= w && x <= e && y >= s && y <= n));
    const raster = await page.locator('.pl-map__canvas').evaluate(e => ({ width: e.width, height: e.height }));
    assert.ok(raster.width > 0 && raster.height > 0);
    await shot('overview');
    await select('P-0005');
    assert.match(await page.locator('.cell-table summary').innerText(), /P-0005 · 262 selected/);
    await page.waitForFunction(n => document.querySelectorAll('.native-cell').length === n, p5.evidence.features.length);
    assert.equal(await page.locator('.native-cell').count(), p5.evidence.features.length);
    return { bounds: manifest.hansen.bounds_west_south_east_north, raster, plotScopedTable: 'P-0005 · 262 selected' };
  });
  await page.locator('.pl-review__actions').getByRole('button', { name: 'Proof', exact: true }).click();
  await page.locator('#proof-heading').waitFor();
  await page.locator('.proof-lab > summary').click();
  await check('six actual synthetic cases × two periods stay outside real cohort', async () => {
    await page.locator('.edge-cases button').first().waitFor();
    const served = await page.evaluate(async () => (await fetch('/data/synthetic-v1.json')).json()); assert.deepEqual(served, synthetic);
    assert.equal(await page.locator('.edge-cases button').count(), 6);
    assert.match(await page.locator('.edge-banner').innerText(), /not supplier data and not part of the real fidelity results/);
    const observations = [];
    for (let index = 0; index < synthetic.cases.length; index++) {
      const fixture = synthetic.cases[index]; await page.locator('.edge-cases button').nth(index).click();
      for (const [period, expected] of Object.entries(fixture.result.periods)) {
        await page.locator('.edge-period').getByRole('button', { name: period.replace('-', '–'), exact: true }).click();
        const signal = expected.mapped_loss_present === true ? 'Observed' : expected.mapped_loss_present === false ? 'Not observed under this query' : 'Unknown';
        assert.equal((await page.locator('.edge-signal strong').textContent()).trim(), signal);
        const count = expected.observed_loss_cell_count === null ? 'Analytical count unavailable' : `${expected.observed_loss_cell_count} observed loss cells`;
        assert.match(await page.locator('.edge-signal small').textContent(), new RegExp(count));
        const raw = JSON.parse(await page.locator('.edge-lab details pre').textContent());
        assert.equal(raw.synthetic, true); assert.equal(raw.case_id, fixture.case_id); assert.deepEqual(raw.result, fixture.result);
        observations.push({ case: fixture.case_id, period, signal, count });
      }
    }
    assert.equal(await page.locator('.proof-hero .pl-stat__value').first().innerText(), `${demo.summary.exact_match_count}/${demo.summary.plot_count}`); assert.equal(await page.locator('.proof-plots button').count(), demo.plots.length);
    await page.locator('.edge-result').scrollIntoViewIfNeeded(); await shot('edge-missing-band'); return observations;
  });
  await page.getByRole('button', { name: 'Back to map', exact: true }).click();
  await page.setViewportSize({ width: 390, height: 844 });
  await check('mobile timeline scrolls at readable size and retains selected year', async () => {
    await page.getByRole('button', { name: 'Year 2001, 0 observed loss cells', exact: true }).click();
    await page.getByRole('button', { name: 'Year 2025, 11 observed loss cells', exact: true }).click();
    await page.waitForFunction(() => { const bar = document.querySelector('.pl-scrub__chart'), active = bar.querySelector('[aria-pressed=true]'), r = active.getBoundingClientRect(), b = bar.getBoundingClientRect(); return r.left >= b.left - 1 && r.right <= b.right + 1; });
    const state = await page.locator('.pl-scrub__chart').evaluate(bar => { const active = bar.querySelector('[aria-pressed=true]'), r = active.getBoundingClientRect(), b = bar.getBoundingClientRect(); return { selected: active.getAttribute('aria-label'), scrollWidth: bar.scrollWidth, clientWidth: bar.clientWidth, scrollLeft: bar.scrollLeft, font: parseFloat(getComputedStyle(active.querySelector('.pl-scrub__yr')).fontSize), selectedLeft: r.left, selectedRight: r.right, barLeft: b.left, barRight: b.right }; });
    await page.locator('.pl-scrub').scrollIntoViewIfNeeded(); await shot('mobile-timeline');
    assert.ok(state.scrollWidth > state.clientWidth); assert.ok(state.font >= 12, JSON.stringify(state));
    assert.ok(state.selectedLeft >= state.barLeft - 1 && state.selectedRight <= state.barRight + 1, JSON.stringify(state));
    return state;
  });
  await check('mobile count proof focus and back restore visible count', async () => {
    await page.locator('.cell-table > summary').click();
    await page.locator('#annual-proof-trigger').focus(); await page.keyboard.press('Enter');
    await page.waitForFunction(() => document.activeElement.id === 'proof-selected-year'); const arrival = await focusBox('proof-selected-year');
    assert.ok(arrival.top >= 0 && arrival.bottom <= arrival.viewport, JSON.stringify(arrival)); await shot('mobile-proof-arrival');
    await page.getByRole('button', { name: 'Back to map', exact: true }).click();
    await page.waitForFunction(() => document.activeElement.id === 'annual-proof-trigger'); const returned = await focusBox('annual-proof-trigger');
    assert.ok(returned.top >= 0 && returned.bottom <= returned.viewport, JSON.stringify(returned)); return { arrival, returned };
  });
  await check('integrated notes fit mobile viewport', async () => {
    await openNote();
    await page.locator('.pl-notes').scrollIntoViewIfNeeded();
    const box = await page.locator('.pl-notes').evaluate(e => ({ width: e.clientWidth, scrollWidth: e.scrollWidth, documentWidth: document.documentElement.scrollWidth, viewport: innerWidth }));
    assert.ok(box.scrollWidth <= box.width + 1); assert.ok(box.documentWidth <= box.viewport + 1); await shot('mobile-notes'); return box;
  });
  await check('cycle3 application has no page errors', async () => { assert.deepEqual(errors, []); });
} finally {
  await browser.close();
  const report = { timestamp: new Date().toISOString(), scope: 'Frozen map-first review, notes, synthetic support and keyboard/mobile focus; not malformed-fixture acceptance', artifact: demo.content_sha256, checks, errors };
  await writeFile(resolve(out, 'w3-cycle3-results.json'), JSON.stringify(report, null, 2));
  const failed = checks.filter(c => c.status === 'FAIL').length;
  console.log(JSON.stringify({ passed: checks.length - failed, failed })); process.exitCode = failed ? 1 : 0;
}
