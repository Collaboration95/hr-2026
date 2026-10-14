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
const row = name => page.locator('.proof-compare tbody tr').filter({ has: page.getByRole('rowheader', { name, exact: true }) });
async function noOverflow() {
  const dimensions = await page.evaluate(() => ({ viewport: innerWidth, document: document.documentElement.scrollWidth, offenders: [...document.querySelectorAll('body *')].filter(e => { const r = e.getBoundingClientRect(); return r.width > 0 && r.right > innerWidth + 1 && getComputedStyle(e).position !== 'absolute'; }).slice(0, 12).map(e => ({ tag: e.tagName, class: e.className, right: e.getBoundingClientRect().right })) }));
  assert.ok(dimensions.document <= dimensions.viewport + 1, JSON.stringify(dimensions));
  return dimensions;
}
try {
  await page.goto(`${baseURL}/#/map/P-0004/2025`);
  await page.locator('.pl-review__actions').getByRole('button', { name: 'Proof', exact: true }).waitFor();
  await check('served artifact equals canonical', async () => {
    const served = await page.evaluate(async () => (await fetch('/data/demo-v1.json')).json());
    assert.deepEqual(served, canonical);
    return { plots: served.plots.length, content_sha256: served.content_sha256 };
  });
  await check('keyboard queue and annual evidence', async () => {
    await page.keyboard.press('j');
    await page.waitForFunction(() => document.querySelector('#plot-review-heading')?.textContent === 'P-0005');
    assert.match(await page.locator('#plot-review-heading').innerText(), /P-0005/);
    const count2024 = p5.source_result.yearly_loss_counts['2024'];
    await page.getByRole('button', { name: `Year 2024, ${count2024} observed loss cells`, exact: true }).click();
    await page.waitForFunction(n => document.querySelectorAll('.native-cell').length === n, p5.evidence.features.length);
    assert.equal(await page.locator('.native-cell').count(), p5.evidence.features.length);
    assert.equal(await page.locator('.native-cell[data-event="true"]').count(), count2024);
    await page.getByRole('button', { name: `Year 2024, ${count2024} observed loss cells`, exact: true }).focus(); await page.keyboard.press('ArrowRight');
    await page.waitForFunction(() => document.querySelector('.pl-scrub__cols [aria-pressed=true]')?.dataset.year === '2025');
    const count2025 = p5.source_result.yearly_loss_counts['2025'];
    assert.equal(await page.locator('.native-cell[data-event="true"]').count(), count2025);
    const focus = await active(); assert.ok(focus.focusVisible); assert.match(focus.outline, /solid/);
    await page.getByRole('button', { name: 'Legend', exact: true }).click();
    assert.match(await page.locator('.pl-map__legend').innerText(), /Loss in 2025/);
    assert.equal(await page.locator('#annual-proof-trigger').getAttribute('aria-label'), `Inspect proof for 2025 observed loss cells`);
    assert.match(await page.locator('#annual-proof-trigger').innerText(), new RegExp(`^${count2025}\\s`));
    await shot('w3-desktop-year-2025.png');
    return { plot: p5.plot_id, selected: p5.source_result.selected_cell_count, count2024, count2025, focus };
  });
  await page.locator('.pl-review__actions').getByRole('button', { name: 'Proof', exact: true }).click();
  await page.locator('#proof-heading').waitFor();
  await check('proof table and cohort agree with JSON', async () => {
    for (const [label, value] of [['Selected native cells', p5.source_result.selected_cell_count], ['2024–2025 loss cells', p5.source_result.periods['2024-2025'].observed_loss_cell_count]]) {
      assert.deepEqual(await row(label).locator('td').allTextContents(), [String(value), String(value), 'same']);
    }
    const b = canonical.benchmark, retainedId = b.retained_selection?.overall_storage_choice ?? b.overall_storage_choice;
    const kept = b.candidates.find(c => c.candidate === retainedId), base = b.baseline;
    const fixed = (n,digits) => n.toLocaleString('en-US',{minimumFractionDigits:digits,maximumFractionDigits:digits});
    const percent = 100*(kept.storage.total_bytes/base.storage.total_bytes-1);
    const hotRatio = base.queries.hot.wall_ms.median/kept.queries.hot.wall_ms.median;
    assert.deepEqual(await page.locator('.proof-hero .pl-stat__value').allTextContents(),[
      `${canonical.summary.exact_match_count}/${canonical.summary.plot_count}`,
      kept.roundtrip.raw_bands_equal && kept.roundtrip.all_band_masks_equal ? '100%' : 'Differs',
      `${percent < 0 ? '−' : '+'}${fixed(Math.abs(percent),2)}%`,
      `${fixed(base.queries.process_cold.wall_ms.median/kept.queries.process_cold.wall_ms.median,2)}×`,
      hotRatio > 0.95 && hotRatio < 1.05 ? '≈1.0×' : `${fixed(hotRatio,2)}×`,
    ]);
    const summary = page.locator('details').filter({ has: page.locator('summary').getByText('Cohort summary (JSON)', { exact: true }) });
    await summary.locator('summary').click(); assert.deepEqual(JSON.parse(await summary.locator('pre').textContent()), canonical.summary);
    const outputs = page.locator('details').filter({ has: page.locator('summary').getByText('Full source and compact query outputs', { exact: true }) });
    await outputs.locator('summary').click(); assert.deepEqual(JSON.parse(await outputs.locator('pre').textContent()), { source: p5.source_result, compact: p5.compact_result });
    await shot('w3-desktop-proof.png');
    return { exactPlots: canonical.summary.exact_match_count };
  });
  await check('benchmark storage choice, units and timing match JSON', async () => {
    const benchmark = canonical.benchmark;
    const choices = [benchmark.baseline, ...benchmark.candidates];
    assert.equal(await page.locator('button.bench-row').count(), choices.length);
    const retained = benchmark.retained_selection?.overall_storage_choice ?? benchmark.overall_storage_choice;
    assert.equal(await page.locator('button.bench-row.is-retained code').innerText(), retained);
    const format = (n, digits) => n.toLocaleString('en-US', { minimumFractionDigits: digits, maximumFractionDigits: digits });
    for (let i = 0; i < choices.length; i++) {
      const c = choices[i], control = page.locator('button.bench-row').nth(i);
      assert.equal(await control.locator('code').innerText(), c.candidate);
      assert.equal(await control.locator('.bench-row__total small').innerText(), `${c.storage.total_bytes.toLocaleString('en-US')} B`);
      assert.ok((await control.locator('.bench-row__total').innerText()).startsWith(`${format(c.storage.total_bytes / 1024, 1)} KiB`));
      await control.click(); assert.equal(await control.getAttribute('aria-pressed'), 'true');
      const detail = page.locator('details').filter({ has: page.locator('summary').filter({ hasText: 'Full evidence for the selected candidate' }) });
      if (!(await detail.evaluate(e => e.open))) await detail.locator('summary').click();
      assert.deepEqual(JSON.parse(await detail.locator('pre').textContent()), c);
      for (const [title, key] of [['Hot query', 'hot'], ['Fresh-process load + query', 'process_cold']]) {
        const stats = c.queries[key].wall_ms;
        const timing = page.getByRole('region', { name: title, exact: true }).locator('.bench-timing-row').nth(i);
        assert.equal(await timing.locator('b').innerText(), `${format(stats.median, 2)} ms`);
        assert.equal(await timing.locator('.bench-dots__dot').count(), stats.samples.length);
        assert.match(await timing.locator('small').innerText(), new RegExp(`n=${stats.repetitions}`));
        assert.ok((await timing.locator('[role=img]').getAttribute('aria-label')).includes(`median ${format(stats.median, 2)} milliseconds`));
      }
    }
    const method = page.locator('details').filter({ has: page.locator('summary').getByText('Measurement method, environment and experiment identity', { exact: true }) });
    await method.locator('summary').click();
    assert.deepEqual(JSON.parse(await method.locator('pre').textContent()), { experiment_id: benchmark.experiment_id, method: benchmark.method, environment: benchmark.environment, settings: benchmark.identity.settings });
    await page.getByRole('button', { name: 'About fresh-process load + query timing', exact: true }).click();
    assert.match(await page.locator('.pl-info__panel').innerText(), /not disk-cold/);
    await page.getByRole('button', { name: 'About fresh-process load + query timing', exact: true }).click();
    await shot('w3-benchmark-source.png');
    return { candidates: choices.length, retained };
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
    assert.equal(await page.locator('dialog[open]').count(), 0);
    assert.equal((await active()).name, 'Inspect provenance receipt');
  });
  if (await page.locator('dialog[open]').count()) await page.keyboard.press('Escape');
  await page.getByRole('button', { name: 'Back to map', exact: true }).click();
  await check('empty search retains clearly labelled selection and recovers', async () => {
    await page.keyboard.press('/'); assert.equal((await active()).name, 'Search plots');
    await page.getByRole('textbox', { name: 'Search plots' }).fill('W3-no-matching-plot-unique');
    await page.getByText('No matching plots', { exact: true }).waitFor();
    assert.equal(await page.locator('.plot-row').count(), 0);
    assert.match(await page.locator('.pl-rail__notice').innerText(), /P-0005 is open but hidden by this filter/);
    await shot('w3-empty-search.png');
    await page.getByRole('button', { name: 'Clear filters', exact: true }).click();
    assert.equal(await page.locator('.plot-row').count(), 17);
    assert.equal(await page.getByRole('textbox', { name: 'Search plots' }).inputValue(), '');
  });
  await check('command Find a plot focuses search after close', async () => {
    await page.getByRole('button', { name: 'Open commands', exact: true }).click();
    await page.getByRole('button', { name: /Find a plot/ }).click();
    await page.waitForFunction(() => !document.querySelector('dialog[open]'));
    assert.equal((await active()).name, 'Search plots');
  });
  await page.locator('nav[aria-label="Workspace view"]').getByRole('button', { name: 'Map', exact: true }).click();
  await check('all-plot map keyboard selection', async () => {
    await page.getByRole('button', { name: 'Region', exact: true }).click();
    assert.equal(await page.getByRole('button', { name: /Select P-\d+ on map/ }).count(), 17);
    await page.getByRole('button', { name: 'Select P-0001 on map', exact: true }).focus(); await page.keyboard.press('Enter');
    assert.match(await page.locator('#plot-review-heading').innerText(), /P-0001/);
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
    assert.match(await page.locator('.pl-map__pinned').innerText(), new RegExp(`NATIVE CELL\\s+${cell.row}:${cell.col}`));
    await page.getByRole('button', { name: 'Close cell details', exact: true }).click();
    await page.locator('.cell-table > summary').click();
    return { rows: p1.evidence.features.length, keyboardInspected: `${cell.row}:${cell.col}` };
  });
  await check('17 plots expose all 25 annual counts from JSON', async () => {
    for (const plot of canonical.plots) {
      await page.locator('.plot-row').filter({ has: page.getByText(plot.plot_id, { exact: true }) }).click();
      await page.waitForFunction(id => document.querySelector('#plot-review-heading')?.textContent === id, plot.plot_id);
      const labels = await page.locator('.pl-scrub__cols button').evaluateAll(nodes => nodes.map(n => n.getAttribute('aria-label')));
      assert.deepEqual(labels, Object.entries(plot.source_result.yearly_loss_counts).map(([year, count]) => `Year ${year}, ${count} observed loss cells`));
      await page.waitForFunction(n => document.querySelectorAll('.native-cell').length === n, plot.evidence.features.length);
      assert.equal(await page.locator('.native-cell').count(), plot.evidence.features.length);
    }
    await page.locator('.plot-row').filter({ has: page.getByText('P-0001', { exact: true }) }).click();
    return { plots: canonical.plots.length, annualCounts: canonical.plots.length * 25 };
  });
  await page.setViewportSize({ width: 390, height: 844 });
  await check('390px review has no document overflow', async () => { await shot('w3-mobile-review.png'); return noOverflow(); });
  await check('390px map boundary and legend fit inside panel', async () => {
    await page.waitForFunction(() => { const b = document.querySelector('.pl-map__boundary')?.getBoundingClientRect(), p = document.querySelector('.pl-map')?.getBoundingClientRect(); return b && p && b.left >= p.left - 1 && b.right <= p.right + 1; });
    const boxes = await page.evaluate(() => Object.fromEntries(['.pl-map', '.pl-map__viewport', '.pl-map__svg', '.pl-map__boundary', '.pl-map__legend'].map(selector => { const r = document.querySelector(selector).getBoundingClientRect(); return [selector, { left: r.left, right: r.right, width: r.width }]; })));
    const panel = boxes['.pl-map'];
    for (const [selector, box] of Object.entries(boxes)) assert.ok(box.left >= panel.left - 1 && box.right <= panel.right + 1, `${selector} is clipped: ${JSON.stringify(boxes)}`);
    return boxes;
  });
  await check('390px empty search and recovery', async () => {
    await page.getByRole('textbox', { name: 'Search plots' }).fill('W3-mobile-empty');
    await page.getByText('No matching plots', { exact: true }).waitFor();
    await shot('w3-mobile-empty.png'); await noOverflow();
    await page.getByRole('button', { name: 'Clear filters', exact: true }).click();
    assert.equal(await page.locator('.plot-row').count(), 17);
  });
  await page.locator('.pl-review__actions').getByRole('button', { name: 'Proof', exact: true }).click();
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
