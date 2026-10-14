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
const results = { started_at: new Date().toISOString(), origin, source: { hansen_content_sha256: main.content_sha256, hansen_file_sha256: mainSha, jrc_file_sha256: jrcSha, jrc_content_sha256: jrc.content_sha256 }, checks: [], findings: [], screenshots: [], downloaded_receipt: null };
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
try {
  const context = await browser.newContext({ viewport: { width: 1440, height: 1000 }, acceptDownloads: true });
  const page = await context.newPage();
  listenErrors(page);
  const servedData = [];
  page.on('response', async response => {
    if (!new URL(response.url()).pathname.includes('/data/')) return;
    try { servedData.push({ url: response.url(), sha256: createHash('sha256').update(await response.body()).digest('hex') }); } catch {}
  });
  await page.goto(origin, { waitUntil: 'networkidle' });
  await page.waitForFunction(() => performance.getEntriesByType('resource').some(entry => entry.name.includes('/data/demo-v1.json')));
  await page.waitForTimeout(100);
  const mainServed = servedData.find(entry => new URL(entry.url).pathname.endsWith('/data/demo-v1.json'));
  assert.equal(mainServed?.sha256, mainSha, 'served Hansen export must be byte-identical to canonical JSON');
  check('served Hansen JSON is byte-identical to canonical evidence', { sha256: mainServed.sha256, content_sha256: main.content_sha256 });
  assert.equal(await page.locator('.companion-panel').count(), 1);
  assert.match(await page.locator('.workspace-footer').innerText(), /Hansen Global Forest Change 2025 v1\.13/);
  const jrcDisclosure = page.locator('.companion-panel > summary');
  await jrcDisclosure.click();
  await page.getByRole('heading', { name: '2020 baseline observation · JRC v4' }).waitFor();
  await page.waitForTimeout(100);
  const jrcServed = servedData.find(entry => new URL(entry.url).pathname.endsWith('/data/jrc-baseline-v1.json'));
  assert.equal(jrcServed?.sha256, jrcSha, 'served JRC companion must be byte-identical to the pinned accepted JSON');
  check('served JRC JSON is byte-identical to accepted pinned evidence', { sha256: jrcServed.sha256, content_sha256: jrc.content_sha256 });
  const p3 = jrc.plots.find(plot => plot.plot_id === 'P-0003');
  assert.equal((await page.locator('.jrc-signal').getAttribute('data-signal')), 'false');
  assert.match(await page.locator('.jrc-signal').innerText(), /No mapped forest-class cells/);
  assert.match(await page.locator('.jrc-counts').innerText(), /0 — Non-forest\s+793/);
  assert.match(await page.locator('.jrc-counts').innerText(), /1 — Forest\s+0/);
  assert.equal(p3.source_result.unknown_cell_count, 0);
  await page.locator('.jrc-proof > summary').click();
  assert.match(await page.locator('.jrc-proof').innerText(), /Actual result equality\s+Equal/);
  assert.match(await page.locator('.jrc-source-tag').innerText(), /Reference 2020 · version v4/);
  const p3Cell = page.locator('.jrc-cells tbody tr').first();
  assert.match(await p3Cell.innerText(), /\b0\b[\s\S]*Mapped non-forest/);
  await page.locator('.jrc-table-scroll').focus();
  await page.keyboard.press('ArrowRight');
  await capture(page, 'completion-browser-jrc-desktop-p0003.png', 'desktop P-0003 JRC known class 0 with separate proof');
  check('desktop P-0003 known class 0 is shown as mapped non-forest, not unknown', { selected: p3.source_result.selected_cell_count, class_counts: p3.source_result.class_counts, unknown: p3.source_result.unknown_cell_count, signal: false });
  check('native cell display preserves raw class zero and analytical class label', { first_row: (await p3Cell.innerText()).replace(/\s+/g, ' ').trim() });

  const p1 = jrc.plots.find(plot => plot.plot_id === 'P-0001');
  await page.getByRole('button', { name: /^P-0001 / }).click();
  await page.getByRole('heading', { name: '2020 baseline observation · JRC v4' }).waitFor();
  assert.match(await page.locator('.jrc-eyebrow').innerText(), /Separate source · P-0001/);
  assert.equal(await page.locator('.jrc-signal').getAttribute('data-signal'), 'true');
  assert.match(await page.locator('.jrc-counts').innerText(), /1 — Forest\s+554/);
  assert.match(await page.locator('.jrc-grid-warning').innerText(), /not area/);
  assert.match(await page.locator('.jrc-source-name').innerText(), /single reference layer/);
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
  assert.equal(downloaded.dataset.version, 'v4');
  assert.equal(downloaded.plot.receipt.product, 'JRC Global Forest Cover Map 2020');
  results.downloaded_receipt = { path: 'completion-browser-jrc-receipt-P-0001.json', suggested_filename: download.suggestedFilename(), exact_plot_match: true, receipt_sha256: downloaded.plot.receipt.receipt_sha256 };
  check('class 1 P-0001 and separate JRC receipt download match canonical JSON exactly', { counts: p1.source_result.class_counts, selected: p1.source_result.selected_cell_count, receipt_sha256: p1.receipt.receipt_sha256 });
  await page.keyboard.press('j');
  const selectedAfterJ = await page.getByRole('complementary', { name: 'Supplier plot review queue' }).locator('.queue-row[aria-pressed="true"]').innerText();
  assert.doesNotMatch(selectedAfterJ, /P-0001/);
  assert.match(await page.locator('.jrc-eyebrow').innerText(), /Separate source · P-/);
  const currentId = selectedAfterJ.match(/P-\d{4}/)?.[0];
  assert.ok(currentId && currentId !== 'P-0001');
  await page.getByRole('button', { name: /^P-0001 / }).click();
  assert.match(await page.locator('.jrc-eyebrow').innerText(), /P-0001/);
  check('integrated selection updates the bound JRC plot; J keyboard navigation moves away from P-0001 and returns correctly', { keyboard_next_plot: currentId, returned_plot: 'P-0001' });
  assert.deepEqual(errors, []);
  await context.close();

  const mobileContext = await browser.newContext({ viewport: { width: 390, height: 844 }, isMobile: true, hasTouch: true, acceptDownloads: true });
  const mobile = await mobileContext.newPage();
  listenErrors(mobile);
  await mobile.goto(origin, { waitUntil: 'networkidle' });
  await mobile.locator('.companion-panel > summary').click();
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
  assert.ok(dims.table > dims.tableRegion, 'native evidence table should scroll inside its own region');
  results.findings.push({ severity: 'non-blocking UX improvement', area: '390px native-cell table', observation: 'The 980px evidence table shows only about 30% of its columns in the 296px viewport. Raw class and mask are visible first; analytical observation, native center and corners require horizontal scrolling.', evidence: dims, suggestion: 'For the demo, keep the analytical observation column pinned or offer a compact mobile row view. The existing scroll instruction and keyboard arrow navigation make the current behavior discoverable and usable.' });
  await mobile.locator('.jrc-baseline').scrollIntoViewIfNeeded();
  await capture(mobile, 'completion-browser-jrc-mobile.png', '390px JRC integration, separate proof, keyboard navigation and contained native table');
  check('390px mobile J/K keyboard flow preserves selected plot binding and contained native table', { next_plot: mobileNext, returned_plot: 'P-0003', dimensions: dims });
  assert.deepEqual(errors, []);
  await mobileContext.close();

  const unavailableContext = await browser.newContext({ viewport: { width: 1280, height: 800 } });
  const unavailablePage = await unavailableContext.newPage();
  listenErrors(unavailablePage);
  await unavailablePage.route('**/data/jrc-baseline-v1.json', route => route.abort('failed'));
  await unavailablePage.goto(origin, { waitUntil: 'networkidle' });
  await unavailablePage.locator('.companion-panel > summary').click();
  await unavailablePage.getByRole('button', { name: 'Retry JRC companion' }).waitFor();
  const unavailableText = await unavailablePage.locator('.companion-body').innerText();
  assert.match(unavailableText, /JRC is unavailable/);
  assert.doesNotMatch(unavailableText, /0 — Non-forest\s+0/);
  assert.match(await unavailablePage.locator('.workspace-footer').innerText(), /Hansen Global Forest Change/);
  check('failed JRC fetch stays unavailable without inventing zero and retains usable Hansen review', { actual_transport_outcome: 'aborted test request', jrc_unavailable: true, hansen_retained: true });
  await unavailableContext.close();
  assert.deepEqual(errors, []);
  const expectedTransportConsole = 'Failed to load resource: net::ERR_FAILED';
  const unexpectedConsoleErrors = consoleErrors.filter(message => message !== expectedTransportConsole);
  assert.deepEqual(unexpectedConsoleErrors, []);
  results.checks.push({ name: 'no unexpected browser page or console errors', pass: true, evidence: { page_errors: errors, unexpected_console_errors: unexpectedConsoleErrors, expected_console_errors_from_aborted_JRC_request: consoleErrors.filter(message => message === expectedTransportConsole) } });
  results.finished_at = new Date().toISOString();
  await mkdir(evidence, { recursive: true });
  await writeFile(resolve(evidence, 'completion-browser-results.json'), `${JSON.stringify(results, null, 2)}\n`);
  console.log(JSON.stringify(results, null, 2));
} finally {
  await browser.close();
}
