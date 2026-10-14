import { qaOrigin, qaEvidence } from '../scripts/qa-config.mjs';
import assert from 'node:assert/strict';
import { readFile, mkdir, writeFile } from 'node:fs/promises';
import { resolve } from 'node:path';
import { pathToFileURL } from 'node:url';

// Requires an already installed Playwright. Never installs packages or browsers.
// From repo root: PLAYWRIGHT_MODULE=/absolute/path/to/playwright/index.mjs node app/tests/live-journey.mjs
const modulePath = process.env.PLAYWRIGHT_MODULE;
const { chromium } = await import(modulePath ? pathToFileURL(resolve(modulePath)).href : 'playwright');
const baseURL = qaOrigin;
const endpoint = new URL(baseURL);
assert.ok(endpoint.protocol === 'http:' && ['127.0.0.1', 'localhost', '[::1]'].includes(endpoint.hostname), 'QA only targets loopback');
const evidence = qaEvidence;
await mkdir(evidence, { recursive: true });
const canonical = JSON.parse(await readFile('artifacts/demo-v1.json', 'utf8'));
const p5 = canonical.plots.find(p => p.plot_id === 'P-0005');
assert.ok(p5, 'actual journey plot must exist');
const browser = await chromium.launch({ headless: true, downloadsPath: evidence });
const context = await browser.newContext({ viewport: { width: 1440, height: 1000 }, acceptDownloads: true });
const page = await context.newPage();
page.setDefaultTimeout(5000);
const errors = [];
const checks = [];
page.on('pageerror', e => errors.push(e.message));
page.on('console', m => { if (m.type() === 'error') errors.push(m.text()); });
await context.route('**/*', route => {
  const url = new URL(route.request().url());
  return url.origin === endpoint.origin ? route.continue() : route.abort();
});
async function check(name, fn) {
  try { const detail = await fn(); checks.push({ name, status: 'PASS', detail }); console.log(`PASS ${name}`); }
  catch (e) { checks.push({ name, status: 'FAIL', error: e.message }); console.log(`FAIL ${name}: ${e.message}`); }
}
const shot = name => page.screenshot({ path: resolve(evidence, name), fullPage: true });
const active = () => page.evaluate(() => ({ tag: document.activeElement.tagName, name: document.activeElement.getAttribute('aria-label') || document.activeElement.textContent, focusVisible: document.activeElement.matches(':focus-visible'), outline: getComputedStyle(document.activeElement).outline }));
const row = name => page.getByRole('row').filter({ has: page.getByRole('rowheader', { name, exact: true }) });
async function noOverflow() {
  const dimensions = await page.evaluate(() => ({ viewport: innerWidth, document: document.documentElement.scrollWidth, offenders: [...document.querySelectorAll('body *')].filter(e => { const r = e.getBoundingClientRect(); return r.width > 0 && r.right > innerWidth + 1 && getComputedStyle(e).position !== 'absolute'; }).slice(0, 12).map(e => ({ tag: e.tagName, class: e.className, right: e.getBoundingClientRect().right })) }));
  assert.ok(dimensions.document <= dimensions.viewport + 1, JSON.stringify(dimensions));
  return dimensions;
}
try {
  await page.goto(baseURL);
  await page.getByRole('button', { name: 'Show proof', exact: true }).waitFor();
  await check('served artifact equals canonical', async () => {
    const served = await page.evaluate(async () => (await fetch('/data/demo-v1.json')).json());
    assert.deepEqual(served, canonical);
    return { plots: served.plots.length, content_sha256: served.content_sha256 };
  });
  await check('keyboard queue and annual evidence', async () => {
    await page.keyboard.press('j');
    assert.match(await page.locator('.plot-header h2').innerText(), /P-0005/);
    const count2024 = p5.source_result.yearly_loss_counts['2024'];
    await page.getByRole('button', { name: `Year 2024, ${count2024} observed loss cells`, exact: true }).click();
    assert.equal(await page.locator('.native-cell').count(), p5.evidence.features.length);
    assert.equal(await page.locator('.native-cell[fill="#df743f"]').count(), count2024);
    await page.keyboard.press('Tab'); await page.keyboard.press('Enter');
    const count2025 = p5.source_result.yearly_loss_counts['2025'];
    assert.equal(await page.locator('.native-cell[fill="#df743f"]').count(), count2025);
    assert.match(await page.locator('.map-legend').innerText(), new RegExp(`2025 mapped loss · ${count2025} cells`));
    const focus = await active(); assert.ok(focus.focusVisible); assert.match(focus.outline, /solid/);
    await shot('w3-desktop-year-2025.png');
    return { plot: p5.plot_id, selected: p5.source_result.selected_cell_count, count2024, count2025, focus };
  });
  await page.getByRole('button', { name: 'Show proof', exact: true }).click();
  await check('proof table and cohort agree with JSON', async () => {
    for (const [label, value] of [['Selected native cells', p5.source_result.selected_cell_count], ['2024-2025 loss cells', p5.source_result.periods['2024-2025'].observed_loss_cell_count]]) {
      assert.deepEqual(await row(label).locator('td').allTextContents(), [String(value), String(value)]);
    }
    assert.match(await page.locator('.proof-secondary').innerText(), /17 \/ 17 plots with measured matching outputs/);
    await page.getByText('Inspect benchmark and method', { exact: true }).click();
    const shown = JSON.parse(await page.locator('details').filter({ has: page.getByText('Inspect benchmark and method', { exact: true }) }).locator('pre').textContent());
    assert.deepEqual(shown, canonical.benchmark);
    await page.getByText('Inspect benchmark and method', { exact: true }).click();
    await shot('w3-desktop-proof.png');
    return { overall_storage_choice: shown.overall_storage_choice, source_bytes: shown.baseline.storage.total_bytes, best_candidate_bytes: shown.winner.total_bytes };
  });
  await check('benchmark storage choice, units and timing match JSON', async () => {
    const benchmark = canonical.benchmark;
    const choices = [benchmark.baseline, ...benchmark.candidates];
    const chosenIndex = choices.findIndex(c => c.candidate === benchmark.overall_storage_choice);
    assert.ok(chosenIndex >= 0, 'embedded storage choice must identify a measured representation');
    const chosenRow = page.locator('.storage-row').nth(chosenIndex);
    assert.match(await chosenRow.innerText(), /storage choice/);
    await chosenRow.click();
    assert.equal(await page.locator('.candidate-id').innerText(), benchmark.overall_storage_choice);
    const decision = await page.locator('.benchmark-decision').innerText();
    if (benchmark.overall_storage_choice === 'source_geotiff') assert.match(decision, /Compressed originals remain the storage choice/);
    else assert.ok(decision.includes(await chosenRow.locator('strong').innerText()));
    const format = (number, digits) => number.toLocaleString('en-US', { minimumFractionDigits: digits, maximumFractionDigits: digits });
    const original = page.locator('.storage-row').filter({ hasText: 'Original GeoTIFF' });
    await original.click();
    assert.equal(await page.locator('.candidate-size strong').innerText(), `${format(benchmark.baseline.storage.total_bytes / 1024, 1)} KiB`);
    await page.getByRole('button', { name: 'Loaded query', exact: true }).click();
    assert.equal(await page.locator('.timing-number strong').innerText(), `${format(benchmark.baseline.queries.hot.wall_ms.median, 2)} ms`);
    assert.match(await page.locator('.timing-number').innerText(), /17-plot batch/);
    await page.getByRole('button', { name: 'Fresh-process load + query', exact: true }).click();
    assert.equal(await page.locator('.timing-number strong').innerText(), `${format(benchmark.baseline.queries.process_cold.wall_ms.median, 2)} ms`);
    assert.match(await page.locator('.candidate-detail').innerText(), /not disk-cold/);
    await shot('w3-benchmark-source.png');
    return { sourceTotalBytes: benchmark.baseline.storage.total_bytes, sourceHotMs: benchmark.baseline.queries.hot.wall_ms.median, sourceFreshProcessMs: benchmark.baseline.queries.process_cold.wall_ms.median };
  });
  await page.getByRole('button', { name: 'Inspect provenance receipt', exact: true }).click();
  await check('receipt content and downloaded JSON agree with canonical', async () => {
    await page.getByText('Hashes, grid and source provenance', { exact: true }).click();
    const receipt = JSON.parse(await page.locator('dialog details').filter({ has: page.getByText('Hashes, grid and source provenance', { exact: true }) }).locator('pre').textContent());
    assert.deepEqual(receipt, p5.receipt);
    await shot('w3-receipt-expanded.png');
    const downloading = page.waitForEvent('download');
    await page.getByRole('button', { name: 'Download receipt JSON', exact: true }).click();
    const downloaded = await downloading;
    assert.equal(downloaded.suggestedFilename(), 'P-0005-receipt.json');
    const dest = resolve(evidence, 'w3-P-0005-receipt.json'); await downloaded.saveAs(dest);
    const payload = JSON.parse(await readFile(dest, 'utf8'));
    assert.deepEqual(payload.receipt, p5.receipt); assert.deepEqual(payload.supplier, p5.supplier); assert.deepEqual(payload.comparison, p5.comparison);
    return { filename: downloaded.suggestedFilename(), receipt_sha256: receipt.receipt_sha256 };
  });
  await check('receipt dialog accessible name', async () => {
    const name = await page.locator('dialog').evaluate(e => e.getAttribute('aria-label') || (e.getAttribute('aria-labelledby') || '').split(/\s+/).map(id => document.getElementById(id)?.textContent || '').join(' ').trim());
    assert.ok(name, 'dialog has no aria-label or aria-labelledby accessible name'); return name;
  });
  await check('dialog traps keyboard and restores opener', async () => {
    await page.getByRole('button', { name: 'Close dialog', exact: true }).focus();
    await page.keyboard.press('Shift+Tab');
    assert.ok(await page.locator('dialog').evaluate(e => e.contains(document.activeElement)));
    await page.keyboard.press('Escape');
    assert.equal(await page.locator('dialog').evaluate(e => e.open), false);
    assert.equal((await active()).name, 'Inspect provenance receipt');
  });
  if (await page.locator('dialog').evaluate(e => e.open)) await page.keyboard.press('Escape');
  await check('empty search retains clearly labelled selection and recovers', async () => {
    await page.keyboard.press('/'); assert.equal((await active()).name, 'Search plots');
    await page.getByRole('textbox', { name: 'Search plots' }).fill('W3-no-matching-plot-unique');
    await page.getByText('No matching plots', { exact: true }).waitFor();
    assert.equal(await page.locator('.queue-row').count(), 0);
    assert.match(await page.locator('.selection-notice').innerText(), /P-0005 remains open/);
    await shot('w3-empty-search.png');
    await page.getByRole('button', { name: 'Clear filters', exact: true }).click();
    assert.equal(await page.locator('.queue-row').count(), 17);
    assert.equal(await page.getByRole('textbox', { name: 'Search plots' }).inputValue(), '');
  });
  await check('command Find a plot focuses search after close', async () => {
    await page.getByRole('button', { name: 'Open commands', exact: true }).click();
    await page.getByRole('button', { name: /Find a plot/ }).click();
    await page.waitForFunction(() => !document.querySelector('dialog').open);
    assert.equal((await active()).name, 'Search plots');
  });
  await page.getByRole('button', { name: 'Review desk', exact: true }).click();
  await check('all-plot map keyboard selection', async () => {
    await page.getByRole('button', { name: 'All 17 plots', exact: true }).click();
    assert.equal(await page.getByRole('button', { name: /Select P-\d+ on map/ }).count(), 17);
    await page.getByRole('button', { name: 'Select P-0001 on map', exact: true }).focus(); await page.keyboard.press('Enter');
    assert.match(await page.locator('.plot-header h2').innerText(), /P-0001/);
    return { selected: 'P-0001' };
  });
  await check('cell inspector has keyboard-accessible entry', async () => {
    await page.locator('.native-cell').first().waitFor();
    const p1 = canonical.plots.find(p => p.plot_id === 'P-0001');
    const cell = p1.evidence.features[0].properties;
    await page.locator('.cell-table > summary').focus(); await page.keyboard.press('Enter');
    assert.equal(await page.locator('.cell-table tbody tr').count(), p1.evidence.features.length);
    const control = page.getByRole('button', { name: `Inspect cell ${cell.row}:${cell.col}`, exact: true });
    await control.focus(); await page.keyboard.press('Enter');
    assert.match(await page.locator('.cell-inspector').innerText(), new RegExp(`Native cell ${cell.row}:${cell.col}`));
    await page.getByRole('button', { name: 'Close cell details', exact: true }).click();
    await page.locator('.cell-table > summary').click();
    return { rows: p1.evidence.features.length, keyboardInspected: `${cell.row}:${cell.col}` };
  });
  await check('17 plots expose all 25 annual counts from JSON', async () => {
    for (const plot of canonical.plots) {
      await page.locator('.queue-row').filter({ has: page.getByText(plot.plot_id, { exact: true }) }).click();
      await page.waitForFunction(id => document.querySelector('.map-title strong')?.textContent === id, plot.plot_id);
      const labels = await page.locator('.year-bars button').evaluateAll(nodes => nodes.map(n => n.getAttribute('aria-label')));
      assert.deepEqual(labels, Object.entries(plot.source_result.yearly_loss_counts).map(([year, count]) => `Year ${year}, ${count} observed loss cells`));
      assert.equal(await page.locator('.native-cell').count(), plot.evidence.features.length);
    }
    await page.locator('.queue-row').filter({ has: page.getByText('P-0001', { exact: true }) }).click();
    return { plots: canonical.plots.length, annualCounts: canonical.plots.length * 25 };
  });
  await page.setViewportSize({ width: 390, height: 844 });
  await check('390px review has no document overflow', async () => { await shot('w3-mobile-review.png'); return noOverflow(); });
  await check('390px map boundary and legend fit inside panel', async () => {
    const boxes = await page.evaluate(() => Object.fromEntries(['.map-panel', '.map-canvas', '.spatial-map', '.plot-geometry', '.map-legend'].map(selector => { const r = document.querySelector(selector).getBoundingClientRect(); return [selector, { left: r.left, right: r.right, width: r.width }]; })));
    const panel = boxes['.map-panel'];
    for (const [selector, box] of Object.entries(boxes)) assert.ok(box.left >= panel.left - 1 && box.right <= panel.right + 1, `${selector} is clipped: ${JSON.stringify(boxes)}`);
    return boxes;
  });
  await check('390px empty search and recovery', async () => {
    await page.getByRole('textbox', { name: 'Search plots' }).fill('W3-mobile-empty');
    await page.getByText('No matching plots', { exact: true }).waitFor();
    await shot('w3-mobile-empty.png'); await noOverflow();
    await page.getByRole('button', { name: 'Clear filters', exact: true }).click();
    assert.equal(await page.locator('.queue-row').count(), 17);
  });
  await page.getByRole('button', { name: 'Show proof', exact: true }).click();
  await check('390px proof controls and layout', async () => { await shot('w3-mobile-proof.png'); await page.getByRole('button', { name: 'Inspect provenance receipt', exact: true }).click(); await page.getByRole('button', { name: 'Download receipt JSON', exact: true }).waitFor(); await shot('w3-mobile-receipt.png'); const dimensions = await noOverflow(); await page.keyboard.press('Escape'); return dimensions; });
  await page.emulateMedia({ reducedMotion: 'reduce' });
  await check('reduced motion media and computed style', async () => {
    const state = await page.evaluate(() => ({ matches: matchMedia('(prefers-reduced-motion: reduce)').matches, transition: getComputedStyle(document.querySelector('button')).transitionDuration, animation: getComputedStyle(document.querySelector('button')).animationDuration, scroll: getComputedStyle(document.documentElement).scrollBehavior }));
    assert.ok(state.matches); assert.equal(state.scroll, 'auto'); assert.ok(parseFloat(state.transition) <= 0.00001); assert.ok(parseFloat(state.animation) <= 0.00001); return state;
  });
  await check('no browser application errors', async () => { assert.deepEqual(errors, []); });
} finally {
  await browser.close();
  const report = { timestamp: new Date().toISOString(), tool: 'existing Playwright 1.63.0 + cached Chromium', endpoint: baseURL, canonicalContentSha256: canonical.content_sha256, checks, errors };
  await writeFile(resolve(evidence, 'w3-live-results.json'), JSON.stringify(report, null, 2));
  console.log(JSON.stringify({ passed: checks.filter(c => c.status === 'PASS').length, failed: checks.filter(c => c.status === 'FAIL').length }));
  process.exitCode = checks.some(c => c.status === 'FAIL') ? 1 : 0;
}
