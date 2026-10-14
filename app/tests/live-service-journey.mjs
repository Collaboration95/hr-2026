import { qaOrigin, qaEvidence } from '../scripts/qa-config.mjs';
import assert from 'node:assert/strict';
import { readFile, writeFile, mkdir } from 'node:fs/promises';
import { createHash } from 'node:crypto';
import { resolve } from 'node:path';
import { fileURLToPath } from 'node:url';

// C5-C: actual HTTP success bodies only. Fault injection affects this browser's transport only.
const appRoot = fileURLToPath(new URL('../', import.meta.url)), repoRoot = resolve(appRoot, '..');
process.env.PLAYWRIGHT_BROWSERS_PATH ||= resolve(appRoot, '.cache/playwright');
const { chromium } = await import('playwright');
const origin = qaOrigin;
const url = new URL(origin); assert.ok(url.protocol === 'http:' && ['localhost', '127.0.0.1'].includes(url.hostname));
const out = qaEvidence; await mkdir(out, { recursive: true });
const frozen = JSON.parse(await readFile(resolve(repoRoot, 'artifacts/demo-v1.json'), 'utf8'));
const p3 = frozen.plots.find(p => p.plot_id === 'P-0003');
const hash = text => createHash('sha256').update(text, 'utf8').digest('hex');
const browser = await chromium.launch({ headless: true });
const context = await browser.newContext({ viewport: { width: 1440, height: 1000 }, acceptDownloads: true });
await context.route('**/*', r => new URL(r.request().url()).origin === url.origin ? r.continue() : r.abort());
const page = await context.newPage(); page.setDefaultTimeout(7000);
const checks = [], errors = [], requests = []; let blocked = null, health = null;
page.on('pageerror', e => errors.push(e.message));
page.on('request', r => { if (r.url().endsWith('/v1/query')) requests.push(r.postData()); });
async function check(name, action) {
  try { const detail = await action(); checks.push({ name, status: 'PASS', detail }); console.log(`PASS ${name}`); return detail; }
  catch (e) { checks.push({ name, status: 'FAIL', error: e.message }); console.log(`FAIL ${name}: ${e.message}`); return undefined; }
}
const shot = name => page.screenshot({ path: resolve(out, `w3-live-service-${name}.png`), fullPage: false });
const result = () => page.locator('.live-result-heading');
const status = () => page.locator('.live-status');
async function enterLab() { await page.getByRole('button', { name: 'Live query', exact: true }).click(); await page.getByRole('heading', { name: 'Ask the layers a new question', exact: true }).waitFor(); await page.waitForFunction(() => { const c = document.querySelector('.live-connection'); return c && c.dataset.state !== 'connecting'; }); }
async function bounds(values) {
  await page.getByRole('radio', { name: 'Temporary rectangle', exact: true }).check();
  for (const [i, label] of ['West longitude', 'South latitude', 'East longitude', 'North latitude'].entries()) await page.getByRole('spinbutton', { name: label, exact: true }).fill(String(values[i]));
}
function validateBytes(answer, body) {
  assert.equal(answer.request_body_sha256, hash(body));
  assert.equal(answer.snapshot_id, health.snapshot_id);
  assert.deepEqual(answer.geometry, JSON.parse(body).geometry);
  assert.equal(answer.receipt.sha256, hash(answer.receipt.canonical_json));
  assert.deepEqual(JSON.parse(answer.receipt.canonical_json), answer.receipt.payload);
  for (const name of ['source_result', 'compact_result', 'evidence']) {
    assert.equal(typeof answer[`${name}_canonical_json`], 'string', `Actual HTTP body missing ${name}_canonical_json`);
    assert.deepEqual(JSON.parse(answer[`${name}_canonical_json`]), answer[name]);
    assert.equal(hash(answer[`${name}_canonical_json`]), answer.receipt.payload[`${name}_sha256`]);
  }
  assert.deepEqual(answer.source_result, answer.compact_result); assert.equal(answer.comparison.equal, true);
  assert.equal(answer.evidence.complete, true); assert.equal(answer.evidence.cells.features.length, answer.source_result.selected_cell_count);
  assert.equal(answer.evidence.returned_cell_count, answer.source_result.selected_cell_count);
  assert.equal(answer.runtime.benchmark, false);
}
async function run({ expectSuccess = true } = {}) {
  const waiting = page.waitForResponse(r => r.url().endsWith('/v1/query') && r.request().method() === 'POST');
  await page.getByRole('button', { name: 'Run region', exact: true }).click();
  const response = await waiting, text = await response.text(), answer = JSON.parse(text), body = response.request().postData();
  await page.waitForFunction(() => { const phase = document.querySelector('.live-status')?.dataset.phase; return phase && phase !== 'running' && phase !== 'connecting'; });
  if (expectSuccess) {
    assert.equal(response.status(), 200, text); validateBytes(answer, body);
    assert.equal(await result().count(), 1, `Actual response rejected by UI: ${await status().innerText()}`);
  } else assert.equal(await result().count(), 0);
  return { answer, body, status: response.status(), rawResponseSha256: hash(text) };
}
async function completeEvidence(answer) {
  assert.deepEqual(await page.locator('.live-measures thead th').allTextContents(), ['Measure', 'Original', 'Compact', 'Match']);
  for (const [key, label] of [['selected_cell_count', 'Selected cells'], ['valid_land_cell_count', 'Valid land cells'], ['unknown_cell_count', 'Unknown cells'], ['out_of_coverage_cell_count', 'Outside coverage']]) {
    const row = page.locator('.live-measures tbody tr').filter({ has: page.getByRole('rowheader', { name: label, exact: true }) });
    assert.deepEqual(await row.locator('td').allTextContents(), [String(answer.source_result[key]), String(answer.compact_result[key]), 'Equal']);
  }
  const disclosure = page.locator('.live-answer details').filter({ has: page.getByText(new RegExp(`^All ${answer.evidence.returned_cell_count} selected native cells$`)) });
  await disclosure.locator('summary').click();
  assert.equal(await disclosure.locator('tbody tr').count(), answer.evidence.returned_cell_count);
  assert.equal(await page.locator('.live-native svg > path').count(), answer.evidence.returned_cell_count + 1);
  assert.ok((await page.locator('.live-native svg').getAttribute('aria-label')).includes(`all ${answer.evidence.returned_cell_count} selected`));
}
async function holdNextQuery() {
  let release, capturedResolve, deliveredResolve;
  const gate = new Promise(r => release = r), captured = new Promise(r => capturedResolve = r), delivered = new Promise(r => deliveredResolve = r);
  const handler = async route => {
    // The body is the service's unmodified HTTP response; only delivery time changes.
    try {
      const response = await route.fetch(), body = await response.body();
      capturedResolve({ answer: JSON.parse(body.toString('utf8')), requestBody: route.request().postData() });
      await gate;
      try { await route.fulfill({ response, body }); deliveredResolve({ delivered: true }); }
      catch (e) { deliveredResolve({ delivered: false, reason: e.message }); }
    } catch (e) { capturedResolve({ error: e.message }); deliveredResolve({ delivered: false, reason: e.message }); }
  };
  await page.route('**/v1/query', handler, { times: 1 }); return { captured, release, delivered };
}
try {
  await page.goto(`${origin}/#/map/P-0003/2023`); await page.getByRole('button', { name: 'Live query', exact: true }).waitFor();
  await check('service unavailable remains explicit at desktop and390px; frozen review works', async () => {
    // Fault envelope only. Never stop a shared server or invent a successful response.
    await page.route('**/v1/health', r => r.fulfill({ status: 500, contentType: 'text/plain', body: '' }));
    for (const width of [1440, 390]) {
      await page.setViewportSize({ width, height: width === 390 ? 844 : 1000 });
      await enterLab(); assert.match(await page.locator('.live-connection').innerText(), /Service unavailable/);
      assert.equal(await page.getByRole('button', { name: 'Run region', exact: true }).isDisabled(), true);
      assert.match(await status().innerText(), /service|proxy|HTTP 500/i); assert.equal(await result().count(), 0);
      assert.ok(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth + 1)); await shot(`unavailable-${width}`);
      await page.getByRole('button', { name: 'Map', exact: true }).click(); assert.match(await page.locator('#plot-review-heading').innerText(), /P-0003/);
      await page.getByRole('button', { name: 'Receipt', exact: true }).click(); await page.getByRole('button', { name: 'Download receipt JSON', exact: true }).waitFor(); await page.keyboard.press('Escape');
    }
    await page.unroute('**/v1/health'); return { fault: 'Browser-local proxy500', sharedServerStopped: false, viewports: [1440, 390] };
  });
  await page.setViewportSize({ width: 1440, height: 1000 }); await enterLab();
  let healthResponse;
  try {
    healthResponse = await context.request.get(`${origin}/v1/health`, { timeout: 7000 });
    if (healthResponse.status() !== 200) blocked = `Actual service health HTTP ${healthResponse.status()}; positive integrated checks not run.`;
    else health = await healthResponse.json();
  } catch (error) { blocked = `Actual service health unavailable: ${error.message}; positive integrated checks not run.`; }
  if (blocked) { checks.push({ name: 'actual live service health required', status: 'BLOCKED', detail: blocked }); console.log(`BLOCKED ${blocked}`); }
  else {
    await check('actual service retry accepts immutable snapshot bytes', async () => {
      await page.getByRole('button', { name: 'Check connection', exact: true }).click(); await page.waitForFunction(() => document.querySelector('.live-connection')?.textContent.trim() === 'Local snapshot ready');
      assert.equal(health.snapshot_id, hash(health.snapshot_canonical_json)); assert.deepEqual(JSON.parse(health.snapshot_canonical_json), health.snapshot);
      return { snapshot_id: health.snapshot_id, lifetime: health.lifetime, limits: health.limits };
    });
    const exact = await check('actual unaugmented P-0003 response accepted with complete cells and receiptbytes', async () => {
      await page.getByLabel('Exact supplied polygon', { exact: true }).check(); await page.getByRole('combobox', { name: 'Reference plot', exact: true }).selectOption('P-0003');
      const query = await run(); assert.deepEqual(query.answer.source_result, p3.source_result); assert.deepEqual(query.answer.compact_result, p3.compact_result); assert.deepEqual(query.answer.geometry, p3.geometry);
      assert.deepEqual(query.answer.evidence.cells.features, p3.evidence.features); await completeEvidence(query.answer);
      const waiting = page.waitForEvent('download'); await page.getByRole('button', { name: 'Download live receipt', exact: true }).click(); const d = await waiting;
      const path = resolve(out, 'w3-live-service-exact-receipt.json'); await d.saveAs(path); const payload = JSON.parse(await readFile(path, 'utf8'));
      assert.deepEqual(payload.response, query.answer); assert.deepEqual(payload.snapshot, health); validateBytes(payload.response, query.body);
      await shot('exact-p0003');
      return { requestId: query.answer.request_id, selectedCells: query.answer.source_result.selected_cell_count, rawResponseSha256: query.rawResponseSha256, receiptSha256: query.answer.receipt.sha256, canonicalFieldsAddedByHarness: false };
    });
    if (!exact) blocked = 'Actual service positive acceptance failed; remaining dependent checks not claimed.';
    else {
      const points = p3.geometry.coordinates.flat(), plotBounds = [Math.min(...points.map(p => p[0])), Math.min(...points.map(p => p[1])), Math.max(...points.map(p => p[0])), Math.max(...points.map(p => p[1]))];
      await check('rectangle edits invalidate prior result and compute a different actualregion', async () => {
        await bounds(plotBounds); assert.equal(await result().count(), 0);
        await page.getByRole('spinbutton', { name: 'West longitude', exact: true }).fill('98');
        await page.getByRole('button', { name: 'Use P-0003 bounds', exact: true }).click();
        for (const [i, label] of ['West longitude', 'South latitude', 'East longitude', 'North latitude'].entries()) assert.equal(Number(await page.getByRole('spinbutton', { name: label, exact: true }).inputValue()), plotBounds[i]);
        const q = await run(); assert.notDeepEqual(q.answer.geometry, p3.geometry);
        assert.notEqual(q.answer.source_result.selected_cell_count, p3.source_result.selected_cell_count); await completeEvidence(q.answer); await shot('rectangle');
        return { exactSelected: p3.source_result.selected_cell_count, rectangleSelected: q.answer.source_result.selected_cell_count, rawResponseSha256: q.rawResponseSha256 };
      });
      await check('blank and reversed bounds reject locally; oversized region rejects withoutsampling', async () => {
        const before = requests.length; await page.getByRole('spinbutton', { name: 'West longitude', exact: true }).fill(''); await page.getByRole('button', { name: 'Run region', exact: true }).click(); assert.match(await status().innerText(), /all four|Empty fields/);
        await bounds([plotBounds[2], plotBounds[1], plotBounds[0], plotBounds[3]]); await page.getByRole('button', { name: 'Run region', exact: true }).click(); assert.match(await status().innerText(), /west < east/); assert.equal(requests.length, before);
        await bounds([98.77, 8.43, 99.09, 8.59]); const q = await run({ expectSuccess: false }); assert.equal(q.status, 422); assert.equal(q.answer.error.code, 'QUERY_TOO_LARGE'); assert.equal(await result().count(), 0); await shot('oversize'); return { invalidRequestsSent: 0, oversizedStatus: q.status, code: q.answer.error.code };
      });
      const [step, , west, , , north] = health.snapshot.grid.transform;
      for (const [name, b, expected] of [
        ['tiny-no-centers', [west + 0.00001, north - 0.00002, west + 0.00002, north - 0.00001], 'none'],
        ['outside', [west - 0.002, north + 0.001, west - 0.0015, north + 0.0015], 'none'],
        ['partial', [west - step, north - 2 * step, west + step, north], 'partial'],
      ]) await check(`actual ${name} region preserves unknown and complete evidence`, async () => {
        await bounds(b); const q = await run(), r = q.answer.source_result; assert.equal(r.support, expected);
        if (name === 'tiny-no-centers') assert.equal(r.selected_cell_count, 0);
        if (name === 'outside') assert.equal(r.out_of_coverage_cell_count, r.selected_cell_count);
        if (name === 'partial') assert.ok(r.out_of_coverage_cell_count > 0 && r.in_coverage_cell_count > 0);
        for (const [period, value] of Object.entries(r.periods)) {
          const card = page.locator('.live-period').filter({ has: page.getByText(period, { exact: true }) });
          assert.equal(await card.getAttribute('data-state'), value.mapped_loss_present === null ? 'unknown' : value.mapped_loss_present ? 'loss' : 'zero');
          if (!value.observed_loss_cell_count) assert.equal(value.mapped_loss_present, null);
          assert.ok((await page.locator('.live-periods').innerText()).includes(value.observed_loss_cell_count === null ? 'Unavailable' : `${value.observed_loss_cell_count} mapped loss cells`));
        }
        await completeEvidence(q.answer); await shot(name); return { selected: r.selected_cell_count, outside: r.out_of_coverage_cell_count, support: r.support, periods: r.periods, rawResponseSha256: q.rawResponseSha256 };
      });
      await check('active edit discards late actualresponse even when transport ignoresabort', async () => {
        // Deliberately ignore transport abort in this disposable realm. Actual bytes/IDs stay unchanged.
        await page.evaluate(() => { window.__w3Fetch = window.fetch; window.fetch = (input, init) => String(input).includes('/v1/query') ? window.__w3Fetch(input, { ...init, signal: undefined }) : window.__w3Fetch(input, init); });
        await bounds(plotBounds); const delayed = await holdNextQuery();
        try {
          await page.getByRole('button', { name: 'Run region', exact: true }).click(); const older = await delayed.captured; assert.ok(!older.error, older.error); validateBytes(older.answer, older.requestBody);
          await bounds([west + 0.00001, north - 0.00002, west + 0.00002, north - 0.00001]); assert.equal(await result().count(), 0);
          const newer = await run(); assert.equal(newer.answer.source_result.selected_cell_count, 0);
          delayed.release(); const delivery = await delayed.delivered;
          await page.waitForFunction(() => { const phase = document.querySelector('.live-status')?.dataset.phase; return phase && phase !== 'running' && phase !== 'connecting'; });
          assert.equal(await page.getByRole('row', { name: /^Selected cells / }).getByRole('cell').first().textContent(), '0');
          const waiting = page.waitForEvent('download'); await page.getByRole('button', { name: 'Download live receipt', exact: true }).click(); const d = await waiting;
          const dest = resolve(out, 'w3-live-service-race-receipt.json'); await d.saveAs(dest); const shown = JSON.parse(await readFile(dest, 'utf8'));
          assert.equal(shown.response.request_id, newer.answer.request_id); assert.notEqual(shown.response.request_id, older.answer.request_id);
          return { older: older.answer.request_id, newer: newer.answer.request_id, delivery, oldResultVisible: false };
        } finally { delayed.release(); await page.evaluate(() => { window.fetch = window.__w3Fetch; delete window.__w3Fetch; }); }
      });
      await check('Cancel query clears pendinganswer and staysclear afterlatebody', async () => {
        await bounds(plotBounds); const delayed = await holdNextQuery();
        try {
          await page.getByRole('button', { name: 'Run region', exact: true }).click(); const captured = await delayed.captured; assert.ok(!captured.error, captured.error);
          await page.getByRole('button', { name: 'Cancel query', exact: true }).click(); assert.match(await status().innerText(), /cancelled/); assert.equal(await result().count(), 0);
          delayed.release(); const delivery = await delayed.delivered; assert.equal(await result().count(), 0); assert.equal(await page.getByRole('button', { name: 'Run region', exact: true }).isEnabled(), true); return { delivery, pendingAnswerVisible: false };
        } finally { delayed.release(); }
      });
      await check('queryservicefailure invalidates ready thenrealretryrecovers', async () => {
        await page.route('**/v1/query', r => r.fulfill({ status: 500, contentType: 'text/plain', body: '' }), { times: 1 });
        await page.getByRole('button', { name: 'Run region', exact: true }).click(); await page.waitForFunction(() => document.querySelector('.live-connection')?.textContent.trim() === 'Service unavailable');
        assert.equal(await result().count(), 0); assert.equal(await page.getByRole('button', { name: 'Run region', exact: true }).isDisabled(), true);
        await page.getByRole('button', { name: 'Check connection', exact: true }).click(); await page.waitForFunction(() => document.querySelector('.live-connection')?.textContent.trim() === 'Local snapshot ready');
        const q = await run(); return { recoveredRequest: q.answer.request_id, fault: 'own browser HTTP500 only' };
      });
      await check('snapshot mismatch requires reconnect and never retains a prior answer', async () => {
        // Test-only error envelope, not a successful query body or a changed shared service.
        await page.route('**/v1/query', r => r.fulfill({ status: 409, contentType: 'application/json', body: JSON.stringify({ schema_version: 'plotline.live-error.v1', request_id: null, error: { code: 'SNAPSHOT_MISMATCH', message: 'Test-only transport fault: snapshot changed; reconnect.' } }) }), { times: 1 });
        const q = await run({ expectSuccess: false });
        assert.equal(q.status, 409);
        assert.equal(await page.locator('.live-connection').innerText(), 'Snapshot changed');
        assert.equal(await status().getAttribute('data-phase'), 'snapshot');
        assert.equal(await page.getByRole('button', { name: 'Run region', exact: true }).isDisabled(), true);
        await page.getByRole('button', { name: 'Check connection', exact: true }).click();
        await page.waitForFunction(() => document.querySelector('.live-connection')?.dataset.state === 'ready');
        const recovered = await run();
        return { fault: 'browser-local HTTP 409 SNAPSHOT_MISMATCH', recoveredRequest: recovered.answer.request_id, snapshot_id: health.snapshot_id };
      });
      await check('390px keyboardcomplete actualquery and nativeevidence receipt', async () => {
        await page.setViewportSize({ width: 390, height: 844 });
        await page.getByRole('radio', { name: 'Exact supplied polygon', exact: true }).focus(); await page.keyboard.press('Space');
        await page.getByRole('combobox', { name: 'Reference plot', exact: true }).selectOption('P-0003');
        const waiting = page.waitForResponse(r => r.url().endsWith('/v1/query') && r.request().method() === 'POST');
        await page.getByRole('button', { name: 'Run region', exact: true }).focus(); await page.keyboard.press('Enter');
        const response = await waiting; const q = await response.json(); validateBytes(q, response.request().postData());
        await result().waitFor(); assert.equal(await page.locator('.live-result-heading h3').evaluate(e => document.activeElement === e), true);
        const focusBounds = await page.locator('.live-result-heading h3').evaluate(e => ({ top: e.getBoundingClientRect().top, bottom: e.getBoundingClientRect().bottom, stickyBottom: document.querySelector('.pl-topbar').getBoundingClientRect().bottom, viewportHeight: innerHeight }));
        assert.ok(focusBounds.top >= focusBounds.stickyBottom && focusBounds.bottom <= focusBounds.viewportHeight, JSON.stringify(focusBounds));
        await completeEvidence(q); assert.ok(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth + 1));
        await page.locator('.live-result-heading').scrollIntoViewIfNeeded(); await shot('mobile-result');
        return { viewport: 390, selected: q.source_result.selected_cell_count, keyboardFocusedResult: true, focusBounds };
      });
      await check('frozen source export unchanged after temporaryqueries', async () => {
        assert.deepEqual(await page.evaluate(async () => (await fetch('/data/demo-v1.json')).json()), frozen);
        await page.getByRole('button', { name: 'Map', exact: true }).click(); assert.match(await page.locator('#plot-review-heading').innerText(), /P-0003/); return { frozenArtifact: frozen.content_sha256 };
      });
    }
  }
  await check('C5 browser has no application pageerrors', async () => assert.deepEqual(errors, []));
} finally {
  await browser.close();
  const uiReplacements = [
    { old: 'Query lab button', new: 'Live query button + Ask the layers a new question heading', why: 'Enter and confirm the redesigned live view.' },
    { old: 'Review desk + .plot-header', new: 'Map + #plot-review-heading on #/map/P-0003/2023', why: 'Landing is now an unselected region; offline review must still show the bound plot and receipt.' },
    { old: 'Computing original status text readiness', new: '.live-status[data-phase] readiness', why: 'Wait for the real lifecycle transition independently of renamed copy.' },
    { old: 'first answer tbody row', new: 'Selected cells row with Original, Compact and Match headers', why: 'Bind race and count assertions to the redesigned comparison table.' },
    { old: '.topbar focus boundary', new: '.pl-topbar focus boundary', why: 'Keep the mobile keyboard result visible below the redesigned sticky header.' },
  ];
  const report = { ui_replacements: uiReplacements, timestamp: new Date().toISOString(), origin, blocked, snapshot_id: health?.snapshot_id, frozenArtifact: frozen.content_sha256, queryRequests: requests.length, checks, errors, noResponseAugmentation: true };
  await writeFile(resolve(out, 'w3-live-service-results.json'), JSON.stringify(report, null, 2));
  const failed = checks.filter(c => c.status === 'FAIL').length; console.log(JSON.stringify({ passed: checks.filter(c => c.status === 'PASS').length, failed, blocked, output: out })); process.exitCode = failed ? 1 : blocked ? 2 : 0;
}
