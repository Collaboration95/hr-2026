import { qaOrigin, qaEvidence } from '../scripts/qa-config.mjs';
import assert from 'node:assert/strict';
import { readFile, writeFile, mkdir } from 'node:fs/promises';
import { fileURLToPath } from 'node:url';
import { resolve } from 'node:path';

// Project-local browser only; this check never downloads dependencies/browsers.
const appRoot = fileURLToPath(new URL('../', import.meta.url));
const repoRoot = resolve(appRoot, '..');
process.env.PLAYWRIGHT_BROWSERS_PATH ||= resolve(appRoot, '.cache/playwright');
const { chromium } = await import('playwright');
const origin = qaOrigin;
const out = qaEvidence; await mkdir(out, { recursive: true });
const data = JSON.parse(await readFile(resolve(repoRoot, 'artifacts/demo-v1.json'), 'utf8'));
const plots = [...data.plots].sort((a, b) => a.plot_id.localeCompare(b.plot_id));
const selected = plots.find(p => p.plot_id === 'P-0001');
const checks = [], errors = [], observations = [];
const browser = await chromium.launch({ headless: true });
const context = await browser.newContext({ viewport: { width: 1440, height: 1000 }, acceptDownloads: true });
await context.route('**/*', r => new URL(r.request().url()).origin === origin ? r.continue() : r.abort());
const page = await context.newPage(); page.setDefaultTimeout(5000); page.on('pageerror', e => errors.push(e.message));
async function check(name, fn) {
  try { const detail = await fn(); checks.push({ name, status: 'PASS', detail }); console.log(`PASS ${name}`); }
  catch (e) { checks.push({ name, status: 'FAIL', error: e.message }); console.log(`FAIL ${name}: ${e.message}`); }
}
const shot = name => page.screenshot({ path: resolve(out, `w3-index-receipt-${name}.png`), fullPage: false });
function parseCsv(text) {
  const rows = []; let row = [], field = '', quoted = false;
  text = text.replace(/^\uFEFF/, '');
  for (let i = 0; i < text.length; i++) {
    const c = text[i];
    if (c === '"') { if (quoted && text[i + 1] === '"') { field += '"'; i++; } else quoted = !quoted; }
    else if (c === ',' && !quoted) { row.push(field); field = ''; }
    else if ((c === '\r' || c === '\n') && !quoted) { if (c === '\r' && text[i + 1] === '\n') i++; row.push(field); rows.push(row); field = ''; row = []; }
    else field += c;
  }
  assert.equal(quoted, false, 'CSV quote imbalance'); if (field || row.length) rows.push([...row, field]);
  return rows;
}
async function download(button, filename) {
  const waiting = page.waitForEvent('download'); await button.click(); const d = await waiting;
  const dest = resolve(out, filename); await d.saveAs(dest); return { suggested: d.suggestedFilename(), text: await readFile(dest, 'utf8') };
}
async function field(label) {
  return page.locator('.pl-receipt__field').filter({ has: page.locator('dt').filter({ hasText: new RegExp(`^${label.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')}$`) }) }).locator('dd').innerText();
}
async function validateDisplayed(start, end) {
  const rendered = await page.locator('.cohort-table tbody tr').evaluateAll(rows => rows.map(row => ({ id: row.querySelector('th button').textContent.trim(), declaration: row.querySelector('.cohort-declaration').textContent.trim(), values: [...row.querySelectorAll('td:not(.cohort-declaration)')].map(e => e.textContent.trim().match(/^(Unknown|[\d,]+)/)?.[1]) })));
  assert.equal(rendered.length, 17);
  let sum = 0, positives = 0;
  for (let index = 0; index < plots.length; index++) {
    const p = plots[index], values = Array.from({ length: end - start + 1 }, (_, i) => p.source_result.yearly_loss_counts[start + i]);
    assert.equal(rendered[index].id, p.plot_id); assert.equal(rendered[index].declaration, p.supplier.c2_deforestation_spatial_analysis_result);
    assert.deepEqual(rendered[index].values, values.map(v => v == null ? 'Unknown' : v.toLocaleString('en-US')));
    sum += values.reduce((a, b) => a + (b || 0), 0); if (values.some(v => v > 0)) positives++;
  }
  const totals = await page.locator('.cohort-overview dd').allTextContents();
  assert.equal(parseInt(totals[0]), positives); assert.equal(parseInt(totals[1].replaceAll(',', '')), sum);
  assert.ok((await page.locator('.cohort-context').innerText()).includes(data.dataset.product));
  assert.ok((await page.locator('.cohort-context').innerText()).includes(data.query_version));
  return { plots: rendered.length, displayedCells: 17 * (end - start + 1), start, end, positivePlots: positives, sum };
}
try {
  await page.goto(origin); await page.getByRole('button', { name: 'Evidence index', exact: true }).waitFor();
  await page.getByRole('button', { name: 'Evidence index', exact: true }).click();
  await check('integrated period tables preserve all17 counts and separate declarations', async () => {
    assert.deepEqual(await page.evaluate(async () => (await fetch('/data/demo-v1.json')).json()), data);
    const result = [await validateDisplayed(2024, 2025)];
    await page.getByRole('button', { name: 'All years · 2001–2025', exact: true }).click(); result.push(await validateDisplayed(2001, 2025));
    await page.getByRole('button', { name: '2021–2023', exact: true }).click(); result.push(await validateDisplayed(2021, 2023));
    return result;
  });
  await check('actual displayed CSV download has51rows and exact source context', async () => {
    const csv = await download(page.getByRole('button', { name: 'Export displayed counts · CSV', exact: true }), 'w3-index-displayed-2021-2023.csv');
    assert.equal(csv.suggested, 'plotline-source-counts-2021-2023.csv');
    const [header, ...rows] = parseCsv(csv.text); assert.equal(rows.length, 51);
    const records = rows.map(values => Object.fromEntries(header.map((key, i) => [key, values[i]])));
    for (const row of records) {
      const p = plots.find(p => p.plot_id === row.plot_id); assert.ok(p);
      assert.ok(Number(row.year) >= 2021 && Number(row.year) <= 2023);
      assert.equal(row.observed_loss_cell_count, String(p.source_result.yearly_loss_counts[row.year]));
      assert.equal(row.supplier_indication_declared, p.supplier.c2_deforestation_spatial_analysis_result);
      assert.equal(row.source_product, data.dataset.product); assert.equal(row.query_version, data.query_version); assert.equal(row.artifact_content_sha256, data.content_sha256);
      assert.equal(row.selected_support, p.source_result.support); assert.equal(row.count_state, 'observed');
      assert.equal(row.view_start_year, '2021'); assert.equal(row.view_end_year, '2023'); assert.match(row.count_basis, /not area or a legal verdict/);
    }
    assert.equal(new Set(records.map(r => `${r.plot_id}/${r.year}`)).size, 51);
    return { downloadedFilename: csv.suggested, rows: records.length, zeroRows: records.filter(r => r.observed_loss_cell_count === '0').length };
  });
  await check('positive earlierperiod count navigates exact plot/year with visible keyboard focus', async () => {
    const button = page.getByRole('button', { name: 'Review P-0001, 2022: 38 observed loss cells', exact: true });
    await button.focus(); await page.keyboard.press('Enter');
    await page.waitForFunction(() => document.activeElement.id === 'plot-review-heading');
    const state = await page.evaluate(() => ({ focus: document.activeElement.id, top: document.activeElement.getBoundingClientRect().top, headerBottom: document.querySelector('.topbar').getBoundingClientRect().bottom, year: document.querySelector('.year-bars [aria-pressed=true]').getAttribute('aria-label'), plot: document.querySelector('.plot-header h2').textContent }));
    assert.match(state.plot, /^P-0001/); assert.equal(state.year, 'Year 2022, 38 observed loss cells'); assert.ok(state.top >= state.headerBottom);
    assert.equal(await page.locator('.native-cell[fill="#df743f"]').count(), 38); await shot('index-arrival'); return state;
  });
  await check('return to index is reachable and focuses visible heading', async () => {
    await page.getByRole('button', { name: 'Evidence index', exact: true }).click();
    const state = await page.locator('.cohort-heading h2').evaluate(e => ({ focused: document.activeElement === e, top: e.getBoundingClientRect().top, headerBottom: document.querySelector('.topbar').getBoundingClientRect().bottom, period: document.querySelector('.cohort-controls [aria-pressed=true]').textContent }));
    assert.ok(state.focused); assert.ok(state.top >= state.headerBottom, JSON.stringify(state));
    observations.push({ returnPeriod: state.period, departurePeriod: '2021–2023', note: 'Period state remount behavior recorded, not an assumed component persistence promise.' });
    await page.getByRole('button', { name: '2021–2023', exact: true }).click();
    await page.getByRole('button', { name: 'Review P-0001, 2022: 38 observed loss cells', exact: true }).click(); return state;
  });
  await page.getByRole('button', { name: 'Receipt', exact: true }).click();
  await check('readable receipt disclosures open by keyboard and show actual plot/year', async () => {
    assert.equal(await field('Plot'), 'P-0001'); assert.equal(await field('Selected observation year'), '2022'); assert.equal(await field('2022 observed loss cells'), '38');
    assert.equal(await field('Source product / release'), data.dataset.product);
    const summaries = page.locator('.pl-receipt__disclosure > summary'); assert.equal(await summaries.count(), 6);
    const names = await summaries.allTextContents();
    for (let i = 0; i < names.length; i++) { await summaries.nth(i).focus(); await page.keyboard.press('Enter'); assert.equal(await summaries.nth(i).evaluate(e => e.parentElement.open), true); }
    assert.match(await page.locator('.pl-receipt').innerText(), /does not independently verify/);
    const rows = await page.locator('.pl-receipt tbody tr').evaluateAll(rows => rows.map(r => [...r.children].map(c => c.textContent.trim())));
    for (const row of rows) { const period = selected.source_result.periods[row[0]]; assert.ok(period); assert.equal(row[1], period.mapped_loss_present ? 'Mapped loss present' : 'No mapped loss'); assert.equal(row[2], String(period.observed_loss_cell_count)); }
    return names;
  });
  await check('full hashes rules grid engine claims and unavailable metadata retain meaning', async () => {
    const receipt = selected.receipt;
    for (const [label, expected] of [['Supplier row SHA-256', receipt.supplier_row_sha256], ['Geometry SHA-256', receipt.geometry_sha256], ['Source metadata SHA-256', receipt.source_metadata_sha256], ['Receipt SHA-256', receipt.receipt_sha256], ['Export content SHA-256', data.content_sha256], ['Experiment ID', data.benchmark.experiment_id], ['Measured run ID', data.benchmark.registry.run_id]]) assert.equal(await field(label), expected);
    assert.equal(await field('Rows × columns'), `${receipt.grid.shape[0].toLocaleString('en-US')} × ${receipt.grid.shape[1].toLocaleString('en-US')}`);
    assert.equal(await field('Cell-center / boundary rule'), receipt.boundary_rule); assert.equal(await field('Valid-land rule'), receipt.valid_land_rule);
    const text = await page.locator('.pl-receipt').innerText();
    const allFiles = [...receipt.supplier_sources, ...receipt.sources, ...receipt.compact_store.files];
    for (const f of allFiles) { assert.ok(text.includes(f.sha256)); assert.ok(text.includes(f.path)); }
    assert.equal(await field('Full-grid raw band values'), 'Equal — engine claim'); assert.equal(await field('Full-grid band validity masks'), 'Equal — engine claim');
    const nodata = await page.locator('.pl-receipt__field').filter({ has: page.locator('dt').getByText('Nodata metadata', { exact: true }) }).locator('dd').allTextContents();
    assert.deepEqual(nodata, receipt.sources.map(s => s.nodata === null ? 'Unavailable' : String(s.nodata)));
    assert.equal(await page.locator('.pl-receipt a').count(), 0);
    return { completeFileHashes: allFiles.length, nullNodata: nodata, claims: 'Engine-reported, not independently reverified' };
  });
  await check('raw disclosures and original receipt download coexist with readable basis', async () => {
    await page.getByText('Hashes, grid and source provenance', { exact: true }).click();
    const raw = JSON.parse(await page.locator('dialog .json-details').filter({ has: page.getByText('Hashes, grid and source provenance', { exact: true }) }).locator('pre').textContent()); assert.deepEqual(raw, selected.receipt);
    await page.getByText('Exact supplier CSV fields', { exact: true }).click();
    const supplier = JSON.parse(await page.locator('dialog .json-details').filter({ has: page.getByText('Exact supplier CSV fields', { exact: true }) }).locator('pre').textContent()); assert.deepEqual(supplier, selected.supplier);
    const downloaded = await download(page.getByRole('button', { name: 'Download receipt JSON', exact: true }), 'w3-index-receipt-P-0001.json');
    const payload = JSON.parse(downloaded.text); assert.deepEqual(payload.receipt, selected.receipt); assert.deepEqual(payload.supplier, selected.supplier); assert.deepEqual(payload.comparison, selected.comparison);
    return { filename: downloaded.suggested, selectedPlot: payload.plot_id };
  });
  for (const width of [390, 320]) {
    await page.setViewportSize({ width, height: 844 });
    await check(`${width}px integrated expanded receipt fits and Escape restores opener`, async () => {
      // ReceiptDetails remounts when a closed dialog is reopened. Expand on each viewport.
      const disclosures = page.locator('.pl-receipt__disclosure');
      for (let i = 0; i < await disclosures.count(); i++) {
        if (!(await disclosures.nth(i).evaluate(e => e.open))) await disclosures.nth(i).locator('summary').click();
      }
      assert.equal(await page.locator('.pl-receipt__disclosure[open]').count(), 6);
      const dimensions = await page.locator('dialog').evaluate(dialog => { const r = dialog.getBoundingClientRect(); return { viewport: innerWidth, left: r.left, right: r.right, clientWidth: dialog.clientWidth, scrollWidth: dialog.scrollWidth, overflowingFields: [...dialog.querySelectorAll('.pl-receipt dd,.pl-receipt code,.pl-receipt summary')].filter(e => e.getBoundingClientRect().right > r.right + 1).map(e => e.textContent.slice(0,90)) }; });
      assert.ok(dimensions.left >= 0 && dimensions.right <= width + 1); assert.ok(dimensions.scrollWidth <= dimensions.clientWidth + 1); assert.deepEqual(dimensions.overflowingFields, []);
      await page.locator('.pl-receipt__disclosure').nth(3).locator('.pl-receipt__files code').nth(1).evaluate(e => e.scrollIntoView({ block: 'center' })); await shot(`receipt-${width}`);
      await page.keyboard.press('Escape'); assert.equal(await page.locator('dialog').evaluate(e => e.open), false);
      const active = await page.evaluate(() => ({ text: document.activeElement.textContent, visible: document.activeElement.matches(':focus-visible') })); assert.equal(active.text, 'Receipt');
      await page.getByRole('button', { name: 'Receipt', exact: true }).click(); return { dimensions, returnedFocus: active };
    });
  }
  await page.keyboard.press('Escape');
  await page.setViewportSize({ width: 390, height: 844 });
  await check('mobile index period→positivecell→receipt preserves exact context below header', async () => {
    await page.getByRole('button', { name: 'Evidence index', exact: true }).click();
    await page.getByRole('button', { name: '2021–2023', exact: true }).click();
    await page.getByRole('button', { name: 'Review P-0001, 2022: 38 observed loss cells', exact: true }).click();
    const arrival = await page.evaluate(() => ({ focus: document.activeElement.id, y: document.activeElement.getBoundingClientRect().top, headerBottom: document.querySelector('.topbar').getBoundingClientRect().bottom }));
    assert.equal(arrival.focus, 'plot-review-heading'); assert.ok(arrival.y >= arrival.headerBottom); await shot('mobile-arrival');
    await page.getByRole('button', { name: 'Receipt', exact: true }).click(); assert.equal(await field('2022 observed loss cells'), '38'); await page.keyboard.press('Escape'); return arrival;
  });
  await check('focused integration has no page errors', async () => assert.deepEqual(errors, []));
} finally {
  await browser.close();
  await writeFile(resolve(out, 'w3-index-receipt-results.json'), JSON.stringify({ timestamp: new Date().toISOString(), artifact: data.content_sha256, checks, observations, errors }, null, 2));
  const failed = checks.filter(c => c.status === 'FAIL').length; console.log(JSON.stringify({ passed: checks.length - failed, failed })); process.exitCode = failed ? 1 : 0;
}
