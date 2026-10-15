// Record the pitch journey against real local data and service responses.
import assert from 'node:assert/strict';
import { readFile, rename, writeFile } from 'node:fs/promises';
import { resolve } from 'node:path';
import { fileURLToPath } from 'node:url';
import { qaOrigin, qaEvidence } from './qa-config.mjs';

process.env.PLAYWRIGHT_BROWSERS_PATH ||= fileURLToPath(new URL('../.cache/playwright', import.meta.url));
const { chromium } = await import('playwright');
const frozen = JSON.parse(await readFile(new URL('../../artifacts/demo-v1.json', import.meta.url), 'utf8'));
const p1 = frozen.plots.find(p => p.plot_id === 'P-0001');
const p5 = frozen.plots.find(p => p.plot_id === 'P-0005');
const browser = await chromium.launch({ headless: true });
const viewport = { width: 1440, height: 900 };
const context = await browser.newContext({ viewport, recordVideo: { dir: qaEvidence, size: viewport } });
await context.route('**/*', route =>
  new URL(route.request().url()).origin === qaOrigin ? route.continue() : route.abort(),
);
const page = await context.newPage();
page.setDefaultTimeout(15000);
const video = page.video();
const started = Date.now();
const chapters = [];
const errors = [];
let failure = null, blocked = null, liveRequest = null;
page.on('pageerror', error => errors.push(error.message));
const tab = name => page.getByRole('navigation', { name: 'Workspace view' }).getByRole('button', { name, exact: true });
function chapter(title, description) {
  const entry = { seconds: Math.round((Date.now() - started) / 100) / 10, title, description, route: new URL(page.url()).hash };
  chapters.push(entry);
  return entry;
}
async function hold(title, description) {
  const entry = chapter(title, description);
  // Reading time only. Every chapter checks readiness before starting this hold.
  await page.waitForTimeout(4000);
  entry.end_seconds = Math.round((Date.now() - started) / 100) / 10;
}
try {
  await page.goto(`${qaOrigin}/#/map`);
  await page.locator('.pl-map[data-raster="ready"]').waitFor();
  assert.equal(await page.locator('#plot-review-heading').count(), 0);
  await hold('Region overview', 'The actual Hansen display raster and all 17 supplied plot boundaries.');

  const playback = chapter('Play 2001–2025', 'Actual annual loss playback on the region raster, ending at 2025.');
  await page.getByRole('button', { name: 'Play years', exact: true }).click();
  await page.getByRole('button', { name: 'Pause years', exact: true }).waitFor();
  await page.waitForFunction(() => document.querySelector('.pl-scrub__year')?.textContent === '2025' && document.querySelector('.pl-scrub__play')?.getAttribute('aria-pressed') === 'false');
  await page.waitForTimeout(4000);
  playback.end_seconds = Math.round((Date.now() - started) / 100) / 10;

  await page.getByRole('button', { name: 'JRC 2020 forest', exact: true }).click();
  assert.equal(await page.getByRole('button', { name: 'JRC 2020 forest', exact: true }).getAttribute('aria-pressed'), 'true');
  await hold('Stack the forest baseline', 'JRC 2020 forest is a separate real raster overlay, with its own grid and definitions.');

  // Deep-link the year so this is the pitch's 2022 observation, not the current scrubber year.
  await page.goto(`${qaOrigin}/#/map/P-0001/2022`);
  await page.locator('#plot-review-heading').waitFor();
  assert.equal(await page.locator('#plot-review-heading').innerText(), 'P-0001');
  assert.equal(await page.locator('.native-cell').count(), p1.evidence.features.length);
  assert.equal(await page.locator('.native-cell.is-event').count(), p1.source_result.yearly_loss_counts['2022']);
  await page.getByRole('button', { name: 'Load JRC 2020 baseline', exact: true }).click();
  await page.locator('.jrc-summary[data-signal]').waitFor();
  await page.getByRole('region', { name: 'Declared and mapped accounts', exact: true }).scrollIntoViewIfNeeded();
  assert.match(await page.locator('#annual-proof-trigger').innerText(), /^38\b/);
  await hold('Two accounts · P-0001 / 2022', 'Supplier declaration and mapped observations stay separate: 38 loss cells in 2022, with a separately loaded JRC baseline.');

  await page.locator('.cell-table > summary').click();
  await page.getByRole('checkbox', { name: 'Only 2022 valid-land loss events (38)', exact: true }).check();
  assert.equal(await page.locator('.cell-table tbody tr').count(), p1.source_result.yearly_loss_counts['2022']);
  await page.locator('.cell-table').scrollIntoViewIfNeeded();
  await hold('Native cells behind the count', 'All 38 actual valid-land 2022 event rows remain inspectable; the map shows native footprints and centers.');

  await tab('Cohort').click();
  await page.locator('.co-matrix').waitFor();
  await page.locator('.co-barcode').waitFor();
  assert.equal(await page.locator('.co-barcode tbody tr').count(), frozen.plots.length);
  await page.getByRole('heading', { name: /Declared vs mapped/ }).scrollIntoViewIfNeeded();
  await hold('Cohort matrix and barcode', '17 supplied plots across 25 years: five declared indications, three mapped plots in 2021–23, zero overlap.');

  await page.getByRole('button', { name: 'Review P-0005, 2025: 11 observed loss cells', exact: true }).click();
  await page.waitForURL('**/#/map/P-0005/2025');
  assert.match(await page.locator('#annual-proof-trigger').innerText(), /^11\b/);
  assert.equal(await page.locator('.native-cell.is-event').count(), p5.source_result.yearly_loss_counts['2025']);
  await hold('Follow a count · P-0005 / 2025', 'Eleven selected 2025 loss cells lead directly to the bound original-versus-compact proof.');
  await page.locator('#annual-proof-trigger').click();
  await page.waitForURL('**/#/proof/P-0005/2025');
  await page.locator('#proof-heading').waitFor();
  await page.getByRole('list', { name: 'Headline results from the frozen export', exact: true }).scrollIntoViewIfNeeded();
  await hold('Same question, two representations', '17/17 identical plot outputs, 100% raw pixel and mask fidelity, honest storage and timing measurements.');

  await page.getByRole('region', { name: 'Complete stored bytes, losers included', exact: true }).scrollIntoViewIfNeeded();
  assert.match(await page.getByRole('region', { name: 'Complete stored bytes, losers included', exact: true }).innerText(), /532,444 B/);
  await hold('Storage chart · losers included', 'The measured standard GeoTIFF control beats the retained custom store by 0.48%; the losing candidates remain visible.');

  await page.getByRole('button', { name: 'Inspect provenance receipt', exact: true }).click();
  await page.getByRole('dialog', { name: 'P-0005 evidence receipt', exact: true }).waitFor();
  await page.getByRole('button', { name: 'Download receipt JSON', exact: true }).waitFor();
  await hold('Bound receipt', 'P-0005 source versions, native grid, query rule and hashes: a reproducibility record, not a certification.');
  await page.getByRole('button', { name: 'Close dialog', exact: true }).click();
  assert.equal(await page.getByRole('dialog').count(), 0);

  await tab('Live query').click();
  await page.getByRole('heading', { name: 'Ask the layers a new question', exact: true }).waitFor();
  await page.waitForFunction(() => { const c = document.querySelector('.live-connection'); return c && c.dataset.state !== 'connecting'; });
  if (await page.locator('.live-connection').getAttribute('data-state') !== 'ready') {
    blocked = `Actual live health unavailable: ${await page.locator('.live-status').innerText()}`;
    const error = new Error(blocked); error.name = 'BlockedLiveService'; throw error;
  }
  const responsePromise = page.waitForResponse(r => r.url().endsWith('/v1/query') && r.request().method() === 'POST');
  await page.getByRole('button', { name: 'Run region', exact: true }).click();
  const response = await responsePromise;
  assert.equal(response.status(), 200, await response.text());
  const answer = await response.json();
  assert.deepEqual(answer.source_result, answer.compact_result);
  assert.equal(answer.evidence.returned_cell_count, answer.source_result.selected_cell_count);
  await page.getByRole('heading', { name: 'Same answer. Inspect the evidence.', exact: true }).waitFor();
  assert.equal((await page.locator('.live-agree .pl-chip').innerText()).trim(), 'Original = compact');
  liveRequest = { request_id: answer.request_id, snapshot_id: answer.snapshot_id, receipt_sha256: answer.receipt.sha256, selected_cells: answer.source_result.selected_cell_count };
  await page.locator('.live-result-heading').scrollIntoViewIfNeeded();
  await hold('Live query · Original = compact', 'A new real read-only request for P-0005 reproduces both answers with all selected native cells and a bound receipt.');
  assert.deepEqual(errors, []);
} catch (error) {
  if (error.name !== 'BlockedLiveService') failure = error.stack;
  console.error(error.message);
  process.exitCode = blocked ? 2 : 1;
} finally {
  // A page error still fails the recording even if a service outage also occurred.
  if (errors.length) { failure ||= `Application page errors: ${JSON.stringify(errors)}`; process.exitCode = 1; }
  await context.close();
  await browser.close();
}
const destination = resolve(qaEvidence, 'plotline-demo.webm');
await rename(await video.path(), destination);
await writeFile(resolve(qaEvidence, 'plotline-demo.json'), JSON.stringify({
  recorded_at: new Date().toISOString(), origin: qaOrigin, viewport,
  recording: 'plotline-demo.webm', narration: false,
  note: 'Actual local browser walkthrough following docs/writeups/04-pitch.md. No successful service responses were injected.',
  ui_replacements: [
    { old: 'Review desk opening', new: '#/map region + Play years through 2025', why: 'Follow the pitch opening and show the actual multi-year raster.' },
    { old: 'Evidence index', new: 'Cohort matrix + loss barcode', why: 'Keep the 17-plot annual index and declared-vs-mapped comparison visible.' },
    { old: 'Show proof', new: '#annual-proof-trigger → #/proof/P-0005/2025', why: 'Keep the selected annual count connected to its bound proof.' },
    { old: 'Separate forest baseline via companion-panel', new: 'JRC 2020 forest overlay + P-0001 Mapped-column JRC summary', why: 'Show the real separate layer in the pitch order, with independent grid counts.' },
    { old: 'Encoding proof hold', new: 'Hero statistics + storage chart + Receipt dialog', why: 'Keep equality and honest measured tradeoffs, and expose the bound provenance.' },
    { old: 'Query lab / P-0003', new: 'Live query / P-0005 → Run region → Original = compact', why: 'Continue the same plot context with a real fresh request and complete evidence.' },
  ],
  chapters, live_request: liveRequest, errors, blocked, failure,
}, null, 2) + '\n');
console.log(`Demo recording: ${destination}`);
console.log(JSON.stringify({ chapters: chapters.map(({ seconds, title }) => ({ seconds, title })), blocked, failure, output: qaEvidence }));
