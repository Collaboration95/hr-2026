import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import { resolve } from 'node:path';
import { harness, demo, plots, repoRoot, noOverflow } from './frozen-qa.mjs';

// Decision-layer journeys: the "Keep the decision, not the data" Proof section and the map-panel block.
// Every expectation is read from artifacts/decision/summary-v1.json, never typed in by hand.
const summary = JSON.parse(await readFile(resolve(repoRoot, 'artifacts/decision/summary-v1.json'), 'utf8'));
const DEC = 'eudr-decision.v1', SCR = 'eudr-screen.v1';
const n = v => v.toLocaleString('en-US');
const plain = text => text.replace(/\s+/g, ' ').trim();
const { page, check, go, errors, shot, finish } = await harness('decision');
const section = page.locator('[data-section="decision-layer"]');
const ASSET = '**/data/decision-v1.json';
const serve = (body, status = 200, contentType = 'application/json') => page.route(ASSET, r => r.fulfill({ status, contentType, body }));
const restore = () => page.unroute(ASSET);
// A hash-only goto keeps the running app, and with it the summary it already loaded; leave the page first.
const fresh = async hash => { await page.goto('about:blank'); await go(hash); };
const panelFacts = async () => ({
  forest: plain(await page.locator('.pl-decision .pl-fact').nth(0).locator('dd').innerText()),
  deforestation: plain(await page.locator('.pl-decision .pl-fact').nth(1).locator('dd').innerText()),
  support: plain(await page.locator('.pl-decision .pl-fact').nth(2).locator('dd').innerText()),
});
// Independent reading of one plot's summary entry, as the panel should show it.
function expectedFacts(id) {
  const o = summary.plots[id].outputs[DEC];
  const forest = o.forest_2020.present === true ? { text: `${n(o.forest_2020.cell_counts.forest)} cells` }
    : o.forest_2020.present === false ? { text: 'none' } : { text: 'Unknown' };
  const d = o.deforestation_after_2020;
  const years = d.present === true ? Object.entries(d.yearly_cell_counts).filter(([, c]) => c > 0) : [];
  const deforestation = d.present === true
    ? { text: `${n(d.cell_count)} cells`, years }
    : d.present === false ? { text: 'none mapped' } : { text: 'Unknown' };
  return { forest, deforestation, support: o.support };
}

try {
  await check('Proof leads with the decision section, above the relabelled lossless audit tier', async () => {
    await go('#/proof/P-0001/2022');
    await section.waitFor();
    assert.equal(plain(await page.locator('#proof-heading').innerText()), 'Keep the decision, not the data.');
    const audit = page.locator('#proof-audit-title');
    assert.match(plain(await audit.innerText()), /^Lossless audit tier \(v1\)/);
    const [top, below] = [await section.boundingBox(), await audit.boundingBox()];
    assert.ok(top.y + top.height <= below.y, 'decision section sits above the audit tier');
    // The audit tier is unchanged: five headline stats, the selected-year row and the plot chips.
    assert.equal(await page.locator('.proof-hero .pl-stat__value').count(), 5);
    assert.equal(await page.locator('.proof-hero .pl-stat__value').first().innerText(), `${demo.summary.exact_match_count}/${demo.summary.plot_count}`);
    assert.equal(await page.locator('#proof-selected-year').count(), 1);
    assert.equal(await page.locator('.proof-plots button').count(), demo.plots.length);
    await shot('proof-desktop');
  });

  await check('hero stats: storage, identical answers and registered-plot speed read from the summary', async () => {
    const cells = section.locator('.dec-hero > li');
    assert.equal(await cells.count(), 3);
    const values = await cells.locator('.pl-stat__value').allInnerTexts();
    const vs = summary.storage.levels[DEC].vs_baselines.original_all_layers;
    assert.equal(values[0], `${vs.percent_smaller.toFixed(1)}%`);
    const f = summary.fidelity;
    assert.equal(values[1], `${n(f.cells_compared - f.cell_mismatches)}/${n(f.cells_compared)}`);
    const p5d = summary.speed.find(r => r.path === 'P5d'), p6d = summary.speed.find(r => r.path === 'P6d');
    const hot = p5d.speedup_vs_v1.hot;
    assert.equal(parseFloat(values[2]), hot >= 10 ? Math.round(hot) : Number(hot.toFixed(1)));
    assert.ok(values[2].endsWith('×'));
    const text = [plain(await cells.nth(0).innerText()), plain(await cells.nth(1).innerText()), plain(await cells.nth(2).innerText())];
    assert.match(text[0], new RegExp(`${vs.ratio.toFixed(0)}×`));
    assert.match(text[0], /KB decision store vs \d+ KB originals/);
    assert.match(text[1], new RegExp(`${n(f.plots_equal)}/${Object.keys(summary.plots).length} plots`));
    assert.match(text[1], new RegExp(`${n(f.fuzz_polygons_equal)}/${n(f.fuzz_polygons_compared)} fuzzed polygons`));
    assert.match(text[2], /registered plots only/);
    assert.match(text[2], new RegExp(`answer table: ${Math.round(p6d.speedup_vs_v1.hot)}×`));
    // Boundary notes stay one click away.
    await cells.nth(2).getByRole('button', { name: 'About the speed figure' }).click();
    assert.match(plain(await page.locator('.dec-hero .pl-info__panel').innerText()), /registered plots only/);
    await page.keyboard.press('Escape');
  });

  await check('ladder rows give bytes and percentage for L0, L1, L2 and the registered-plot table', async () => {
    const rows = section.locator('tr[data-rung]');
    assert.deepEqual(await rows.evaluateAll(es => es.map(e => e.dataset.rung)), ['l0', 'l1', 'l2', 'table']);
    const bytes = [summary.storage.baselines.retained_lossless_l0, summary.storage.levels[SCR].file_bytes, summary.storage.levels[DEC].file_bytes, summary.speed.find(r => r.path === 'P6d').bytes_read];
    const original = summary.storage.baselines.original_all_layers;
    for (const [i, b] of bytes.entries()) {
      const cells = await rows.nth(i).locator('td').allInnerTexts();
      assert.match(cells[3], new RegExp(`^${n(b)} B`));
      assert.match(cells[4], new RegExp(`^${(100 * (1 - b / original)).toFixed(1)}%`));
    }
    const l2 = plain(await rows.nth(2).innerText());
    assert.ok(l2.includes(summary.contracts[DEC]), 'L2 answers text is the contract text');
    for (const dropped of summary.dropped) assert.ok(l2.includes(dropped.replace(/^decision level only:\s*/i, '')), dropped);
    const l1 = plain(await rows.nth(1).innerText());
    assert.ok(!l1.includes('loss years on JRC 2020 non-forest land'), 'L1 keeps the decision-only attribute');
  });

  await check('layer analysis and speed tables list every row; registered-only rows are flagged', async () => {
    const layers = section.locator('.dec-layers tbody tr');
    assert.equal(await layers.count(), summary.layer_analysis.length);
    for (const [i, l] of summary.layer_analysis.entries()) {
      assert.equal(await layers.nth(i).locator('th').innerText(), l.plane);
      assert.match(await layers.nth(i).locator('td').nth(0).innerText(), new RegExp(`^${n(l.zstd19_bytes)}`));
      assert.equal(plain(await layers.nth(i).locator('.pl-chip').innerText()).toLowerCase(), l.verdict.toLowerCase());
      assert.equal(await layers.nth(i).locator('td').nth(1).locator('li').count(), l.needed_for.length);
    }
    const speed = section.locator('.dec-speed tbody tr');
    assert.deepEqual(await speed.evaluateAll(es => es.map(e => e.dataset.path)), summary.speed.map(r => r.path));
    assert.deepEqual(
      await speed.evaluateAll(es => es.filter(e => e.dataset.registered === 'true').map(e => e.dataset.path)),
      summary.speed.filter(r => r.registered_plots_only).map(r => r.path));
    for (const r of summary.speed.filter(x => x.registered_plots_only)) {
      assert.match(plain(await section.locator(`.dec-speed tr[data-path="${r.path}"] th`).innerText()), /registered plots only/);
    }
    for (const r of summary.speed) assert.match(await section.locator(`.dec-speed tr[data-path="${r.path}"] td`).nth(5).innerText(), new RegExp(`^${n(r.bytes_read)}$`));
  });

  await check('scale, standard control and limits stay visible and honest', async () => {
    const t = summary.tile_scale;
    const tile = plain(await section.locator('[data-card="tile"]').innerText());
    for (const bytes of [t.original_files_bytes, t.screen_bytes, t.decision_bytes]) assert.ok(tile.includes(`${(bytes / 1e6).toFixed(1)} MB`), tile);
    const control = plain(await section.locator('[data-card="control"]').innerText());
    for (const level of [DEC, SCR]) {
      const l = summary.storage.levels[level];
      assert.ok(control.includes(`${n(l.file_bytes)} B`) && control.includes(`${n(l.best_standard_control_bytes)} B`) && control.includes(l.best_standard_control), control);
    }
    assert.match(control, /not from the container/);
    assert.deepEqual(await section.locator('.dec-limits li').allInnerTexts(), summary.limitations);
  });

  await check('map panel shows the EUDR decision layer for every plot, matching the summary', async () => {
    await go('#/map/P-0001/2022');
    for (const plot of plots) {
      await page.evaluate(h => { location.hash = h; }, `#/map/${plot.plot_id}/2022`);
      await page.waitForFunction(id => document.querySelector('#plot-review-heading')?.textContent === id, plot.plot_id);
      await page.locator('.pl-decision[data-state=ready]').waitFor();
      const mapped = page.locator('.pl-account--mapped');
      assert.equal(await mapped.locator('.pl-decision').count(), 1, 'block lives in the Mapped account');
      assert.equal(await page.locator('.pl-account--declared .pl-decision').count(), 0);
      const want = expectedFacts(plot.plot_id), got = await panelFacts();
      assert.ok(got.forest.startsWith(want.forest.text), `${plot.plot_id} forest: ${got.forest}`);
      assert.ok(got.deforestation.startsWith(want.deforestation.text), `${plot.plot_id} deforestation: ${got.deforestation}`);
      for (const [year, count] of want.deforestation.years ?? []) assert.ok(got.deforestation.includes(`${year}`) && got.deforestation.includes(n(count)), got.deforestation);
      assert.equal(got.support, want.support);
      assert.doesNotMatch(await page.locator('.pl-decision').innerText(), /compliant|violation|illegal|deforested farm|non-compliant/i);
    }
    return { plots: plots.length };
  });

  await check('P-0001 reads as forest cells and a mapped loss year; a plot without either reads none', async () => {
    await go('#/map/P-0001/2022');
    await page.locator('.pl-decision[data-state=ready]').waitFor();
    const want = expectedFacts('P-0001'), got = await panelFacts();
    assert.match(got.forest, new RegExp(`^${want.forest.text}`));
    assert.match(got.deforestation, new RegExp(`^${want.deforestation.text} in ${want.deforestation.years[0][0]}`));
    assert.equal(await page.locator('.pl-decision .pl-fact__num.is-forest').count(), 1);
    assert.equal(await page.locator('.pl-decision .pl-fact__num.is-loss').count(), 1);
    await shot('map-P-0001');
    const none = plots.map(p => p.plot_id).find(id => summary.plots[id].outputs[DEC].forest_2020.present === false && summary.plots[id].outputs[DEC].deforestation_after_2020.present === false);
    await page.evaluate(h => { location.hash = h; }, `#/map/${none}/2022`);
    await page.waitForFunction(id => document.querySelector('#plot-review-heading')?.textContent === id, none);
    assert.deepEqual(await panelFacts(), { forest: `none 0 of ${n(summary.plots[none].outputs[DEC].valid_land_cell_count)} land cells`, deforestation: 'none mapped 0 cells, 2021–2025', support: 'complete' });
    assert.equal(await page.locator('.pl-decision .pl-unknown').count(), 0, 'a known zero is not drawn as unknown');
  });

  await check('tri-state: unanalysable and unknown-blocked answers render as Unknown, never as zero', async () => {
    const edited = structuredClone(summary);
    const [a, b] = ['P-0001', plots.find(p => p.plot_id !== 'P-0001').plot_id];
    const oa = edited.plots[a].outputs[DEC];
    oa.forest_2020 = { cell_counts: null, present: null };
    oa.deforestation_after_2020 = { yearly_cell_counts: null, cell_count: null, present: null };
    oa.valid_land_cell_count = 0; oa.support = 'none';
    const ob = edited.plots[b].outputs[DEC];
    ob.forest_2020 = { cell_counts: { forest: 0, nonforest: ob.valid_land_cell_count - 2, unknown: 2 }, present: null };
    ob.deforestation_after_2020.present = null; ob.support = 'partial';
    await serve(JSON.stringify(edited));
    try {
      await fresh(`#/map/${a}/2022`);
      await page.locator('.pl-decision[data-state=ready]').waitFor();
      assert.equal(await page.locator('.pl-decision .pl-unknown').count(), 3, 'forest, deforestation and support are unknown');
      let got = await panelFacts();
      assert.match(got.forest, /^Unknown/);
      assert.match(got.deforestation, /^Unknown/);
      assert.doesNotMatch(`${got.forest} ${got.deforestation}`, /\b0\b/);
      await page.evaluate(h => { location.hash = h; }, `#/map/${b}/2022`);
      await page.waitForFunction(id => document.querySelector('#plot-review-heading')?.textContent === id, b);
      got = await panelFacts();
      assert.match(got.forest, /^Unknown\s+no forest seen; \d+ cells unknown/);
      assert.match(got.deforestation, /^Unknown/);
      assert.match(got.support, /^partial/);
    } finally { await restore(); }
  });

  await check('a plot boundary that differs from the computed one hides the block instead of mismatching', async () => {
    const edited = structuredClone(summary);
    edited.plots['P-0001'].geometry_sha256 = '0'.repeat(64);
    await serve(JSON.stringify(edited));
    try {
      await fresh('#/map/P-0001/2022');
      await page.locator('.pl-decision[data-state=stale]').waitFor();
      assert.match(await page.locator('.pl-decision').innerText(), /not shown/);
      assert.equal(await page.locator('.pl-decision .pl-fact').count(), 0);
    } finally { await restore(); }
  });

  for (const [name, respond] of [
    ['missing file (404)', () => serve('Not found', 404, 'text/plain')],
    ['HTML fallback page', () => serve('<!doctype html><title>Plotline</title>', 200, 'text/html')],
    ['wrong schema', () => serve(JSON.stringify({ ...summary, schema: 'plotline.decision-summary.v0' }))],
    ['malformed plot output', () => { const e = structuredClone(summary); e.plots['P-0001'].outputs[DEC].forest_2020.present = false; return serve(JSON.stringify(e)); }],
  ]) {
    await check(`optional asset unavailable (${name}): the app falls back to the lossless proof and an unchanged map`, async () => {
      await respond();
      try {
        await fresh('#/proof/P-0001/2022');
        await page.locator('#proof-heading').waitFor();
        await page.waitForLoadState('networkidle');
        assert.equal(plain(await page.locator('#proof-heading').innerText()), 'Same question. Two representations.');
        assert.equal(await section.count(), 0);
        assert.equal(await page.locator('#proof-audit-title').count(), 0);
        assert.equal(await page.locator('.proof-hero .pl-stat__value').count(), 5);
        assert.equal(await page.locator('#proof-selected-year').count(), 1);
        await fresh('#/map/P-0001/2022');
        await page.locator('#plot-review-heading').waitFor();
        await page.waitForLoadState('networkidle');
        assert.equal(await page.locator('.pl-decision').count(), 0);
        assert.equal(await page.locator('.pl-accounts .pl-account--mapped .pl-fact').count(), 4, 'the Hansen facts are untouched');
      } finally { await restore(); }
    });
  }

  for (const route of ['#/proof/P-0001/2022', '#/map/P-0001/2022']) await check(`390px: no document overflow on ${route}`, async () => {
    await page.setViewportSize({ width: 390, height: 844 });
    await fresh(route);
    if (route.startsWith('#/proof')) await section.waitFor(); else await page.locator('.pl-decision[data-state=ready]').waitFor();
    await shot(`mobile-${route.slice(2).replaceAll('/', '-')}`);
    return noOverflow(page);
  });

  await check('decision journeys have no page errors', async () => assert.deepEqual(errors, []));
} finally { await finish(); }
