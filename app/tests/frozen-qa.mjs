// Shared only by the frozen redesign/experience suites. No package/browser install.
import assert from 'node:assert/strict';
import { readFile, writeFile } from 'node:fs/promises';
import { resolve } from 'node:path';
import { fileURLToPath, pathToFileURL } from 'node:url';
import { qaOrigin, qaEvidence } from '../scripts/qa-config.mjs';
import { validateArtifact } from './contract-check.mjs';
export const repoRoot = fileURLToPath(new URL('../../', import.meta.url));
export const demo = JSON.parse(await readFile(resolve(repoRoot, 'artifacts/demo-v1.json'), 'utf8'));
const validation = validateArtifact(demo, { expectedPlots: 17 });
assert.deepEqual(validation.errors, [], 'canonical fixture must remain valid');
export const plots = [...demo.plots].sort((a,b) => a.plot_id.localeCompare(b.plot_id));
export const years = Array.from({ length: 25 }, (_,i) => 2001+i);
export const declared = p => p.supplier.c2_deforestation_spatial_analysis_result === 'b. Indication of deforestation';
export const mapped = p => p.source_result.periods['2021-2023'].mapped_loss_present;
export const fmt = n => n.toLocaleString('en-US');
export async function harness(suite) {
  process.env.PLAYWRIGHT_BROWSERS_PATH ||= resolve(repoRoot, 'app/.cache/playwright');
  const { chromium } = await import(process.env.PLAYWRIGHT_MODULE ? pathToFileURL(resolve(process.env.PLAYWRIGHT_MODULE)).href : 'playwright');
  const browser = await chromium.launch({ headless: true });
  const context = await browser.newContext({ viewport: { width: 1440, height: 1000 }, acceptDownloads: true });
  await context.route('**/*', r => new URL(r.request().url()).origin === qaOrigin ? r.continue() : r.abort());
  const page = await context.newPage(); page.setDefaultTimeout(5000);
  const errors = [], checks = [];
  page.on('pageerror', e => errors.push(e.message));
  const check = async (name, fn) => {
    try { const detail = await fn(); checks.push({ name, status:'PASS', detail }); console.log(`PASS ${name}`); }
    catch(e) { checks.push({ name, status:'FAIL', error: e.message }); console.log(`FAIL ${name}: ${e.message}`); }
  };
  const go = async hash => { await page.goto(`${qaOrigin}/${hash}`); await page.locator('nav[aria-label="Workspace view"]').waitFor(); };
  const shot = name => page.screenshot({ path: resolve(qaEvidence, `${suite}-${name}.png`), fullPage: true });
  const finish = async () => {
    await browser.close();
    await writeFile(resolve(qaEvidence, `${suite}-results.json`), JSON.stringify({ timestamp: new Date().toISOString(), origin: qaOrigin, artifact: demo.content_sha256, checks, errors }, null, 2));
    const failed = checks.filter(c => c.status === 'FAIL').length;
    console.log(JSON.stringify({ suite, passed: checks.length-failed, failed, output: qaEvidence }));
    process.exitCode = failed ? 1 : 0;
  };
  return { browser, context, page, errors, check, go, shot, finish, out: qaEvidence };
}
export async function noOverflow(page) {
  const sizes = await page.evaluate(() => ({ viewport: innerWidth, document: document.documentElement.scrollWidth }));
  assert.ok(sizes.document <= sizes.viewport + 1, JSON.stringify(sizes)); return sizes;
}
export async function selectedCells(page, plot, year) {
  await page.waitForFunction(n => document.querySelectorAll('.native-cell').length === n, plot.evidence.features.length);
  await page.waitForFunction(y => document.querySelector('.pl-scrub__cols [aria-pressed=true]')?.dataset.year === String(y), year);
  assert.equal(await page.locator('.native-cell').count(), plot.source_result.selected_cell_count);
  assert.equal(await page.locator('.native-cell[data-event="true"]').count(), plot.source_result.yearly_loss_counts[year]);
}
export async function matrix(page, selector) {
  const labels = await page.locator(selector).evaluate(table => {
    const text = el => { const clone = el.cloneNode(true); clone.querySelectorAll('.co-matrix__total').forEach(e=>e.remove()); return clone.textContent.trim(); };
    return { columns: [...table.querySelectorAll('thead th')].filter(th=>th.scope==='col').map(text).filter(t=>t!=='Supplier declaration'), rows: [...table.querySelectorAll('tbody th')].map(text) };
  });
  assert.deepEqual(labels, { columns: ['Mapped loss','No mapped loss','Unknown'], rows: ['Declared indication','Declared none'] });
  const actual = await page.locator(`${selector} tbody tr`).evaluateAll(rows => rows.map(row => [...row.querySelectorAll('td')].map(td => [...td.querySelectorAll('button')].map(b => b.textContent.trim()))));
  const expected = [true, false].map(d => [true, false, null].map(m => plots.filter(p => declared(p) === d && mapped(p) === m).map(p => p.plot_id)));
  assert.deepEqual(actual, expected); assert.equal(actual.flat(2).length, plots.length); return expected;
}
