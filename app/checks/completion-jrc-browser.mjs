#!/usr/bin/env node
import assert from 'node:assert/strict';
import { createHash } from 'node:crypto';
import { mkdir, readFile, writeFile } from 'node:fs/promises';
import { resolve } from 'node:path';
import { qaOrigin, qaEvidence } from '../scripts/qa-config.mjs';

const root = resolve(import.meta.dirname, '../..');
const evidence = qaEvidence;
const origin = qaOrigin;
process.env.PLAYWRIGHT_BROWSERS_PATH ||= resolve(root, 'app/.cache/playwright');
const { chromium } = await import('playwright');
const [main, jrc, mainBytes, jrcBytes] = await Promise.all([
  readFile(resolve(root, 'artifacts/demo-v1.json'), 'utf8').then(JSON.parse),
  readFile(resolve(root, 'artifacts/jrc-baseline-v1.json'), 'utf8').then(JSON.parse),
  readFile(resolve(root, 'artifacts/demo-v1.json')),
  readFile(resolve(root, 'artifacts/jrc-baseline-v1.json')),
]);
const mainSha = createHash('sha256').update(mainBytes).digest('hex');
const jrcSha = createHash('sha256').update(jrcBytes).digest('hex');
assert.equal(jrcSha, '933b3d302b8ec961444a7f252f74deb87f3f186f1b7f8d5bcb5012cb55658f71');
assert.equal(jrc.summary.mapped_forest_plot_counts.unknown, 0, 'actual artifact should drive the unknown-state limit');
const uiReplacements = [
  { old: 'Default P-0003 review', new: '#/map/P-0003/2023', why: 'The landing page is now a region overview with no selected plot.' },
  { old: '.companion-panel/.companion-body', new: 'Mapped-column JrcSummary + .pl-jrc disclosure', why: 'Verify both the lazy summary and independent full source panel.' },
  { old: '.workspace-footer', new: '.pl-review__foot', why: 'Retain Hansen provenance and usable review during a separate JRC outage.' },
  { old: 'P-0001 button + Supplier plot review queue/.queue-row', new: 'button.plot-row + Supplier plots/.plot-row', why: 'Keep pointer and J/K selection bound to the correct JRC plot.' },
  { old: 'Reference 2020 · version v4 tag', new: 'Reference 2020 · separate native grid tag + v4 heading and exact receipt version', why: 'Keep reference year, version and distinct grid verified.' },
  { old: 'Raw class and analytical label in wide scrolling table', new: 'Compact raw 0/1 + Observation, More columns exposes class labels/masks/centers/corners', why: 'Preserve full native records while prioritizing readable columns.' },
  { old: '390px table must overflow horizontally', new: '390px priority table fits; expanded raw columns remain keyboard-scrollable inside the table', why: 'Verify the required mobile improvement without dropping raw evidence access.' },
  { old: 'Retry JRC companion in the full panel', new: 'Retry JRC baseline in .pl-jrc; summary still shows unavailable and Retry JRC companion', why: 'Prove separate-source retry restores actual data while Hansen proof stays usable.' },
];
const results = { ui_replacements: uiReplacements, started_at: new Date().toISOString(), origin, source: { hansen_content_sha256: main.content_sha256, hansen_file_sha256: mainSha, jrc_file_sha256: jrcSha, jrc_content_sha256: jrc.content_sha256 }, checks: [], findings: [], screenshots: [], downloaded_receipt: null };
const check = (name, evidenceValue) => results.checks.push({ name, pass: true, evidence: evidenceValue });
const capture = async (page, filename, label) => {
  const path = resolve(evidence, filename);
  await page.screenshot({ path, animations: 'disabled' });
  results.screenshots.push({ label, path: filename });
};
const browser = await chromium.launch({ headless: true });
const errors = [];
const consoleErrors = [];
const listenErrors = page => {
  page.on('pageerror', error => errors.push(error.message));
  page.on('console', message => { if (message.type() === 'error') consoleErrors.push(message.text()); });
};
async function assertNativePage(page, plot, index) {
  const selected = plot.evidence.cells.slice(index * 25, (index + 1) * 25);
  const status = page.locator('.jrc-pagination [role="status"]');
  await page.waitForFunction(({ index, pages }) => document.querySelector('.jrc-pagination [role="status"]')?.textContent === `Page ${index + 1} of ${pages}`, { index, pages: Math.ceil(plot.evidence.cells.length / 25) });
  assert.equal(await status.innerText(), `Page ${index + 1} of ${Math.ceil(plot.evidence.cells.length / 25)}`);
  const actual = await page.locator('.jrc-cells tbody tr').evaluateAll(rows => rows.map(row => [...row.children].slice(0, 5).map(cell => cell.textContent.trim())));
  const [a, b, c, d, e, f] = jrc.native_grid.transform;
  const expected = selected.map(cell => [
    `${cell.row} / ${cell.col}`,
    `${cell.value} — ${jrc.dataset.classes[String(cell.value)]}`,
    cell.valid ? cell.value === 1 ? 'Mapped forest' : 'Mapped non-forest' : 'Unknown — invalid mask',
    cell.valid ? 'Valid' : 'Invalid',
    `${(a * (cell.col + 0.5) + b * (cell.row + 0.5) + c).toFixed(9)}, ${(d * (cell.col + 0.5) + e * (cell.row + 0.5) + f).toFixed(9)}`,
  ]);
  assert.deepEqual(actual, expected, 'rendered page must retain every canonical native record and affine center');
}
try {
  const context = await browser.newContext({ viewport: { width: 1440, height: 1000 }, acceptDownloads: true });
  const page = await context.newPage();
  listenErrors(page);
  const servedData = [];
  page.on('response', response => {
    if (!new URL(response.url()).pathname.includes('/data/')) return;
    const entry = { url: response.url(), bytes: response.body().then(body => createHash('sha256').update(body).digest('hex')).catch(() => null) };
    servedData.push(entry);
  });
  await page.goto(`${origin}/#/map/P-0003/2023`, { waitUntil: 'networkidle' });
  await page.waitForFunction(() => performance.getEntriesByType('resource').some(entry => entry.name.includes('/data/demo-v1.json')));
  await page.locator('#plot-review-heading').waitFor();
  const mainServed = servedData.find(entry => new URL(entry.url).pathname.endsWith('/data/demo-v1.json'));
  assert.equal(await mainServed?.bytes, mainSha, 'served Hansen export must be byte-identical to canonical JSON');
  check('served Hansen JSON is byte-identical to canonical evidence', { sha256: mainSha, content_sha256: main.content_sha256 });
  assert.equal(await page.locator('.pl-jrc').count(), 1);
  assert.equal(servedData.some(entry => entry.url.endsWith('/data/jrc-baseline-v1.json')), false, 'JRC must remain lazy until requested');
  assert.equal(await page.getByRole('button', { name: 'Load JRC 2020 baseline', exact: true }).count(), 1);
  assert.match(await page.locator('.pl-review__foot').innerText(), /Hansen Global Forest Change 2025 v1\.13/);
  const jrcDisclosure = page.locator('.pl-jrc > summary');
  await page.getByRole('button', { name: 'Load JRC 2020 baseline', exact: true }).click();
  await page.locator('.jrc-summary[data-signal="false"]').waitFor();
  assert.match(await page.locator('.jrc-summary').innerText(), /0 forest-class cells of 793 JRC cells \(separate grid\)/);
  assert.match(await page.locator('.jrc-summary').innerText(), /original = compact/);
  assert.equal(await page.locator('.pl-jrc').getAttribute('open'), null);
  check('Mapped column loads the separate JRC summary on demand without opening the full disclosure', { plot: 'P-0003', forest: 0, selected: 793, separate_grid: true });
  await jrcDisclosure.click();
  await page.getByRole('heading', { name: '2020 baseline observation · JRC v4' }).waitFor();
  const jrcServed = servedData.find(entry => new URL(entry.url).pathname.endsWith('/data/jrc-baseline-v1.json'));
  assert.equal(await jrcServed?.bytes, jrcSha, 'served JRC companion must be byte-identical to the pinned accepted JSON');
  check('served JRC JSON is byte-identical to accepted pinned evidence', { sha256: jrcSha, content_sha256: jrc.content_sha256 });
  const p3 = jrc.plots.find(plot => plot.plot_id === 'P-0003');
  assert.equal((await page.locator('.jrc-signal').getAttribute('data-signal')), 'false');
  assert.match(await page.locator('.jrc-signal').innerText(), /No mapped forest-class cells/);
  assert.match(await page.locator('.jrc-counts').innerText(), /0 — Non-forest\s+793/);
  assert.match(await page.locator('.jrc-counts').innerText(), /1 — Forest\s+0/);
  assert.equal(p3.source_result.unknown_cell_count, 0);
  await page.locator('.jrc-proof > summary').click();
  assert.match(await page.locator('.jrc-proof').innerText(), /Actual result equality\s+Equal/);
  assert.match(await page.locator('.jrc-source-tag').innerText(), /Reference 2020 · separate native grid/);
  const p3Cell = page.locator('.jrc-cells tbody tr').first();
  assert.match(await p3Cell.innerText(), /\b0\b[\s\S]*Mapped non-forest/);
  await page.getByRole('button', { name: 'More columns', exact: true }).click();
  await assertNativePage(page, p3, 0);
  await page.locator('.jrc-table-scroll').focus();
  await page.keyboard.press('ArrowRight');
  await capture(page, 'completion-browser-jrc-desktop-p0003.png', 'desktop P-0003 JRC known class 0 with separate proof');
  check('desktop P-0003 known class 0 is shown as mapped non-forest, not unknown', { selected: p3.source_result.selected_cell_count, class_counts: p3.source_result.class_counts, unknown: p3.source_result.unknown_cell_count, signal: false });
  check('native cell display preserves raw class zero and analytical class label', { first_row: (await p3Cell.innerText()).replace(/\s+/g, ' ').trim() });

  // Every canonical selected cell remains reachable; pagination never substitutes sampling.
  const pages = Math.ceil(p3.evidence.cells.length / 25);
  assert.equal(await page.getByRole('button', { name: 'Previous cells', exact: true }).isDisabled(), true);
  for (let index = 1; index < pages; index++) {
    await page.getByRole('button', { name: 'Next cells', exact: true }).click();
    await assertNativePage(page, p3, index);
  }
  assert.equal(await page.getByRole('button', { name: 'Next cells', exact: true }).isDisabled(), true);
  await page.getByRole('button', { name: 'Previous cells', exact: true }).click();
  await assertNativePage(page, p3, pages - 2);
  check('all 793 canonical JRC cells are reachable through 32 correctly bound pages, including raw classes and masks', { cells: p3.evidence.cells.length, pages });

  const p1 = jrc.plots.find(plot => plot.plot_id === 'P-0001');
  await page.locator('button.plot-row').filter({ hasText: 'P-0001' }).click();
  await page.waitForFunction(() => document.querySelector('.jrc-eyebrow')?.textContent?.includes('P-0001'));
  assert.match(await page.locator('.jrc-eyebrow').innerText(), /Separate source · P-0001/i);
  assert.equal(await page.locator('.jrc-signal').getAttribute('data-signal'), 'true');
  assert.match(await page.locator('.jrc-counts').innerText(), /1 — Forest\s+554/);
  assert.match(await page.locator('.jrc-grid-warning').innerText(), /not area/);
  assert.match(await page.locator('.jrc-source-name').innerText(), /single reference layer/);
  await page.getByRole('button', { name: 'More columns', exact: true }).click();
  await assertNativePage(page, p1, 0);
  assert.match(await page.locator('.jrc-cells tbody tr').first().innerText(), /1 — Forest[\s\S]*Mapped forest/);
  await capture(page, 'completion-browser-jrc-desktop-p0001.png', 'desktop P-0001 JRC class 1 and independent Hansen context');
  const [download] = await Promise.all([
    page.waitForEvent('download'),
    page.getByRole('button', { name: 'Download separate JRC receipt' }).click(),
  ]);
  const receiptPath = resolve(evidence, 'completion-browser-jrc-receipt-P-0001.json');
  await download.saveAs(receiptPath);
  const downloaded = JSON.parse(await readFile(receiptPath, 'utf8'));
  assert.equal(download.suggestedFilename(), 'plotline-jrc-P-0001.json');
  assert.deepEqual(downloaded.plot, p1);
  assert.deepEqual(downloaded.dataset, jrc.dataset);
  assert.deepEqual(downloaded.native_grid, jrc.native_grid);
  assert.deepEqual(downloaded.limitations, jrc.limitations);
  assert.equal(downloaded.content_sha256, jrc.content_sha256);
  assert.equal(downloaded.dataset.version, 'v4');
  assert.equal(downloaded.plot.receipt.product, 'JRC Global Forest Cover Map 2020');
  results.downloaded_receipt = { path: 'completion-browser-jrc-receipt-P-0001.json', suggested_filename: download.suggestedFilename(), exact_plot_match: true, receipt_sha256: downloaded.plot.receipt.receipt_sha256 };
  check('class 1 P-0001 and separate JRC receipt download match canonical JSON exactly', { counts: p1.source_result.class_counts, selected: p1.source_result.selected_cell_count, receipt_sha256: p1.receipt.receipt_sha256 });
  await page.locator('#plot-review-heading').focus();
  await page.keyboard.press('j');
  await page.waitForFunction(() => document.querySelector('.jrc-eyebrow')?.textContent?.includes('P-0003'));
  const selectedAfterJ = await page.getByRole('complementary', { name: 'Supplier plots' }).locator('.plot-row[aria-pressed="true"]').innerText();
  assert.doesNotMatch(selectedAfterJ, /P-0001/);
  assert.match(await page.locator('.jrc-eyebrow').innerText(), /Separate source · P-/i);
  const currentId = selectedAfterJ.match(/P-\d{4}/)?.[0];
  assert.ok(currentId && currentId !== 'P-0001');
  await page.locator('button.plot-row').filter({ hasText: 'P-0001' }).click();
  await page.waitForFunction(() => document.querySelector('.jrc-eyebrow')?.textContent?.includes('P-0001'));
  assert.match(await page.locator('.jrc-eyebrow').innerText(), /P-0001/);
  check('integrated selection updates the bound JRC plot; J keyboard navigation moves away from P-0001 and returns correctly', { keyboard_next_plot: currentId, returned_plot: 'P-0001' });
  assert.deepEqual(errors, []);
  await context.close();

  const mobileContext = await browser.newContext({ viewport: { width: 390, height: 844 }, isMobile: true, hasTouch: true, acceptDownloads: true });
  const mobile = await mobileContext.newPage();
  listenErrors(mobile);
  await mobile.goto(`${origin}/#/map/P-0003/2023`, { waitUntil: 'networkidle' });
  await mobile.locator('.pl-jrc > summary').click();
  await mobile.getByRole('heading', { name: '2020 baseline observation · JRC v4' }).waitFor();
  assert.match(await mobile.locator('.jrc-eyebrow').innerText(), /P-0003/);
  await mobile.keyboard.press('j');
  await mobile.waitForFunction(() => !document.querySelector('.jrc-eyebrow')?.textContent?.includes('P-0003'));
  const mobileNext = (await mobile.locator('.jrc-eyebrow').innerText()).match(/P-\d{4}/)?.[0];
  assert.ok(mobileNext && mobileNext !== 'P-0003');
  await mobile.keyboard.press('k');
  await mobile.waitForFunction(() => document.querySelector('.jrc-eyebrow')?.textContent?.includes('P-0003'));
  await mobile.locator('.jrc-proof > summary').click();
  await mobile.locator('.jrc-table-scroll').focus();
  await mobile.keyboard.press('ArrowRight');
  const dims = await mobile.evaluate(() => ({ inner: innerWidth, document: document.documentElement.scrollWidth, body: document.body.scrollWidth, tableRegion: document.querySelector('.jrc-table-scroll').clientWidth, table: document.querySelector('.jrc-table-scroll table').scrollWidth }));
  assert.equal(dims.document, 390);
  assert.equal(dims.body, 390);
  assert.ok(dims.table <= dims.tableRegion + 1, `priority native table must need no forced horizontal scrolling: ${JSON.stringify(dims)}`);
  assert.equal(await mobile.getByRole('button', { name: 'More columns', exact: true }).getAttribute('aria-pressed'), 'false');
  const firstMobile = mobile.locator('.jrc-cells tbody tr').first();
  assert.equal((await firstMobile.locator('td').nth(0).innerText()).trim(), '0');
  assert.equal(await firstMobile.locator('.jrc-cell-state').innerText(), 'Mapped non-forest');
  assert.equal(await mobile.getByRole('columnheader', { name: 'Native center (°E, °N)', exact: true }).isVisible(), false);
  await mobile.getByRole('button', { name: 'More columns', exact: true }).click();
  assert.equal(await mobile.getByRole('button', { name: 'More columns', exact: true }).getAttribute('aria-pressed'), 'true');
  assert.equal((await firstMobile.locator('td').nth(0).innerText()).trim(), '0 — Non-forest');
  assert.equal(await mobile.getByRole('columnheader', { name: 'Stored mask', exact: true }).isVisible(), true);
  await assertNativePage(mobile, p3, 0);
  await firstMobile.getByText('Inspect corners', { exact: true }).click();
  const cell = p3.evidence.cells[0];
  const [a, b, c, d, e, f] = jrc.native_grid.transform;
  const expectedCorners = [[cell.col, cell.row], [cell.col + 1, cell.row], [cell.col + 1, cell.row + 1], [cell.col, cell.row + 1]].map(([x, y]) => `${(a * x + b * y + c).toFixed(9)}, ${(d * x + e * y + f).toFixed(9)}`);
  assert.deepEqual(await firstMobile.locator('.jrc-corners li').allTextContents(), expectedCorners);
  const expanded = await mobile.locator('.jrc-table-scroll').evaluate(e => ({ region: e.clientWidth, table: e.scrollWidth }));
  assert.equal(await mobile.locator('.jrc-table-scroll').getAttribute('tabindex'), '0');
  await mobile.locator('.jrc-table-scroll').focus();
  await mobile.keyboard.press('ArrowRight');
  if (expanded.table > expanded.region) await mobile.waitForFunction(() => document.querySelector('.jrc-table-scroll').scrollLeft > 0);
  assert.equal(await mobile.evaluate(() => document.documentElement.scrollWidth), 390);
  check('390px More columns exposes raw labels, masks, native centers and whole-cell corners with contained keyboard scrolling', { compact: dims, expanded, first_cell: p3.evidence.cells[0] });
  await mobile.getByRole('button', { name: 'More columns', exact: true }).click();
  assert.equal(await mobile.getByRole('columnheader', { name: 'Stored mask', exact: true }).isVisible(), false);
  await mobile.locator('.jrc-baseline').scrollIntoViewIfNeeded();
  await capture(mobile, 'completion-browser-jrc-mobile.png', '390px JRC integration, separate proof, keyboard navigation and contained native table');
  check('390px mobile J/K keyboard flow preserves selected plot binding and contained native table', { next_plot: mobileNext, returned_plot: 'P-0003', dimensions: dims });
  assert.deepEqual(errors, []);
  await mobileContext.close();

  const unavailableContext = await browser.newContext({ viewport: { width: 1280, height: 800 } });
  const unavailablePage = await unavailableContext.newPage();
  listenErrors(unavailablePage);
  await unavailablePage.route('**/data/jrc-baseline-v1.json', route => route.abort('failed'));
  await unavailablePage.goto(`${origin}/#/map/P-0003/2023`, { waitUntil: 'networkidle' });
  await unavailablePage.locator('.pl-jrc > summary').click();
  await unavailablePage.getByRole('button', { name: 'Retry JRC baseline' }).waitFor();
  const unavailableText = await unavailablePage.locator('.pl-jrc').innerText();
  assert.match(unavailableText, /JRC baseline unavailable/);
  assert.doesNotMatch(unavailableText, /0 — Non-forest\s+0/);
  assert.match(await unavailablePage.locator('.pl-review__foot').innerText(), /Hansen Global Forest Change/);
  check('failed JRC fetch stays unavailable without inventing zero and retains usable Hansen review', { actual_transport_outcome: 'aborted test request', jrc_unavailable: true, hansen_retained: true });
  assert.match(await unavailablePage.locator('.jrc-summary').innerText(), /JRC 2020 v4 unavailable/);
  assert.equal(await unavailablePage.locator('.jrc-counts').count(), 0);
  assert.equal(await unavailablePage.locator('#plot-review-heading').innerText(), 'P-0003');
  await unavailablePage.locator('#annual-proof-trigger').click();
  await unavailablePage.locator('#proof-heading').waitFor();
  assert.equal(await unavailablePage.getByRole('combobox', { name: 'Proof plot' }).inputValue(), 'P-0003');
  await unavailablePage.getByRole('button', { name: 'Back to map', exact: true }).click();
  await unavailablePage.locator('.pl-jrc > summary').click();
  await unavailablePage.unroute('**/data/jrc-baseline-v1.json');
  await unavailablePage.getByRole('button', { name: 'Retry JRC baseline', exact: true }).click();
  await unavailablePage.getByRole('heading', { name: '2020 baseline observation · JRC v4', exact: true }).waitFor();
  assert.equal(await unavailablePage.locator('.jrc-signal').getAttribute('data-signal'), 'false');
  assert.match(await unavailablePage.locator('.jrc-summary').innerText(), /0 forest-class cells of 793 JRC cells/);
  check('real JRC retry recovers the summary and separate baseline after usable Hansen proof navigation', { fault: 'test-only aborted JRC transport', retry: 'unmodified served artifact' });
  await unavailableContext.close();
  assert.deepEqual(errors, []);
  const expectedTransportConsole = 'Failed to load resource: net::ERR_FAILED';
  const unexpectedConsoleErrors = consoleErrors.filter(message => message !== expectedTransportConsole);
  assert.deepEqual(unexpectedConsoleErrors, []);
  results.checks.push({ name: 'no unexpected browser page or console errors', pass: true, evidence: { page_errors: errors, unexpected_console_errors: unexpectedConsoleErrors, expected_console_errors_from_aborted_JRC_request: consoleErrors.filter(message => message === expectedTransportConsole) } });
  results.finished_at = new Date().toISOString();
  await mkdir(evidence, { recursive: true });
  await writeFile(resolve(evidence, 'completion-browser-results.json'), `${JSON.stringify(results, null, 2)}\n`);
  console.log(JSON.stringify({ passed: results.checks.length, failed: 0, output: evidence }));
} catch (error) {
  results.checks.push({ name: 'JRC journey completion', pass: false, error: error.stack });
  results.finished_at = new Date().toISOString();
  await writeFile(resolve(evidence, 'completion-browser-results.json'), `${JSON.stringify(results, null, 2)}\n`);
  console.error(error);
  console.log(JSON.stringify({ passed: results.checks.filter(c => c.pass).length, failed: 1, output: evidence }));
  process.exitCode = 1;
} finally {
  await browser.close();
}
