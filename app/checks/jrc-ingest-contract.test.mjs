import test from 'node:test';
import assert from 'node:assert/strict';
import { validateJrc, loadJrc, jrcComparisonAgrees, jrcCellPoint } from '../src/jrc-data.ts';
import { candidate, main, cloneCandidate, cases, shapeFixture, refreshSummary, panelFixture } from './jrc-ingest-fixtures.mjs';

test('preliminary actual candidate passes UI shape/association only, unchanged', () => {
  const before = structuredClone(candidate), mainBefore = structuredClone(main);
  assert.strictEqual(validateJrc(candidate, main), candidate);
  assert.deepEqual(candidate, before); assert.deepEqual(main, mainBefore);
  assert.equal(candidate.plots.length, 17);
});
for (const name of Object.keys(cases)) {
  test(`synthetic ${name}: explicit support and raw records pass`, () => {
    const d = shapeFixture(name); assert.strictEqual(validateJrc(d, main), d);
    assert.equal(d.plots[0].source_result.mapped_forest_present, cases[name].flag);
  });
  test(`paired forged ${name}: wrong nullable signal is rejected`, () => {
    const d = shapeFixture(name); d.plots[0].source_result.mapped_forest_present = cases[name].flag === null ? false : null;
    assert.throws(() => validateJrc(d, main), /mapped_forest_present/);
  });
}
const reject = (name, mutate, match = /Invalid JRC companion/) => test(name, () => {
  const d = cloneCandidate(); mutate(d); assert.throws(() => validateJrc(d, main), match);
});
reject('17 IDs cannot become 16', d => d.plots.pop(), /17 matching/);
reject('duplicate plot ID', d => { d.plots[1].plot_id = d.plots[0].plot_id; }, /duplicate/);
reject('unmatched plot ID', d => { d.plots[0].plot_id = 'invented'; }, /geometry/);
reject('geometry coordinate change despite old digest', d => { d.plots[0].geometry.coordinates[0][1][0] += 0.00001; }, /geometry/);
reject('geometry digest change despite unchanged shape', d => { d.plots[0].geometry_sha256 = '1'.repeat(64); }, /geometry_sha256/);
reject('source version mismatch', d => { d.dataset.version = 'v3'; }, /dataset/);
reject('source product mismatch', d => { d.dataset.product = 'Hansen'; }, /dataset/);
reject('reference year mismatch', d => { d.dataset.reference_year = 2025; }, /dataset/);
reject('schema mismatch', d => { d.schema_version = 'plotline.demo.v1'; }, /schema_version/);
reject('query mismatch', d => { d.query_version = 'hansen-centers.v1'; }, /query_version/);
reject('Hansen grid reused even in both grid declarations', d => { d.native_grid.shape = d.dataset.shape = main.dataset.shape; }, /native_grid.shape/);
reject('shifted window transform in both declarations', d => { d.native_grid.transform[2] += 0.001; d.dataset.transform = [...d.native_grid.transform]; }, /native_grid.transform/);
reject('class zero changed to nodata', d => { d.dataset.zero_is_valid_class = false; }, /dataset.classes/);
reject('class definitions swapped', d => { d.dataset.classes['0'] = 'Forest'; }, /dataset.classes/);
reject('source identity digest not valid syntax', d => { d.dataset.source.sha256 = 'verified'; }, /source.sha256/);
reject('chip identity differs from acquisition', d => { d.dataset.chip_sha256 = '1'.repeat(64); }, /chip_sha256/);
reject('source SHA substitution with valid digest syntax', d => { d.dataset.source.sha256 = '1'.repeat(64); }, /source.sha256/);
reject('coordinated QML identity substitution still fails acquisition pin', d => {
  const previous = d.dataset.qml_sha256; d.dataset.qml_sha256 = d.dataset.class_label_source.sha256 = '1'.repeat(64);
  d.dataset.required_inputs.find(f => f.sha256 === previous).sha256 = '1'.repeat(64);
}, /qml_sha256/);
reject('receipt source identity differs between plots', d => { d.plots[1].receipt.dataset_sha256 = '1'.repeat(64); }, /dataset_sha256/);
reject('receipt source product forged', d => { d.plots[0].receipt.product = 'Hansen'; }, /source\/query/);
reject('receipt store binding forged', d => { d.plots[0].receipt.store.total_bytes++; }, /bindings/);
reject('benchmark run binding forged', d => { d.plots[0].receipt.benchmark_run = 'other-run'; }, /bindings/);
reject('non-JRC benchmark schema', d => { d.benchmark.schema_version = 'hansen-benchmark'; }, /benchmark.schema_version/);
reject('proof flags cannot replace actual deep equality', d => { d.plots[0].compact_result.extension = { hidden: true }; }, /comparison.equal/);
reject('equal=false cannot contradict identical results', d => { d.plots[0].comparison.equal = false; }, /comparison.equal/);
reject('mismatch fields cannot be fabricated', d => { d.plots[0].comparison.mismatch_fields = ['support']; }, /mismatch_fields/);
reject('raw 0 coerced to null is rejected in coverage', d => { d.plots[2].evidence.cells[0].value = null; }, /covered raw/);
reject('evidence cannot have duplicate native indices', d => { d.plots[0].evidence.cells[1] = structuredClone(d.plots[0].evidence.cells[0]); }, /duplicate native/);
reject('unknown raw domain rejected', d => { d.plots[0].evidence.cells[0].value = 2; }, /raw 0\/1\/null/);
reject('string validity rejected', d => { d.plots[0].evidence.cells[0].valid = 'true'; }, /explicit validity/);
reject('invalid masks cannot silently remain analytical', d => { d.plots[0].evidence.cells[0].valid = false; }, /native evidence/);
reject('summary cannot manufacture counts', d => { d.summary.class_counts_sum['0']++; }, /summary/);
reject('unsafe count rejected', d => { d.plots[0].source_result.selected_cell_count = Number.MAX_SAFE_INTEGER + 1; }, /safe integer/);
reject('fractional count rejected', d => { d.plots[0].source_result.valid_cell_count = 1.1; }, /safe integer/);
reject('array holes are invalid JSON data', d => { delete d.native_grid.transform[0]; }, /native_grid.transform/);
for (const raw of [0, 1, 'false', undefined]) reject(`nullable signal never coerces ${String(raw)}`, d => { d.plots[0].source_result.mapped_forest_present = raw; });
test('outside records retain null/invalid; a forged outside raw zero fails', () => {
  const d = shapeFixture('outside'); validateJrc(d, main);
  d.plots[0].evidence.cells[0].value = 0; assert.throws(() => validateJrc(d, main), /outside cells/);
});
test('missing band with stored valid forest never restores analytic classes', () => {
  const d = shapeFixture('missingBand'); validateJrc(d, main);
  d.plots[0].source_result.class_counts = { '0': 0, '1': 1 }; assert.throws(() => validateJrc(d, main), /explicit null/);
});
test('truthful mismatch is retained, never marked agreement', () => {
  const d = shapeFixture('valid0'), p = d.plots[0];
  p.compact_result.extension = { observed: true }; p.comparison.equal = false; p.comparison.mismatch_fields = ['extension'];
  p.receipt.compact_result_sha256 = '1'.repeat(64); refreshSummary(d);
  validateJrc(d, main); assert.equal(jrcComparisonAgrees(p), false);
});
test('truthful oracle failure is retained as unconfirmed', () => {
  const d = cloneCandidate(); d.plots[0].comparison.independent_oracle_equal = false; refreshSummary(d);
  validateJrc(d, main); assert.equal(jrcComparisonAgrees(d.plots[0]), false);
});
test('comparison ignores result key order but includes nested extension values', () => {
  const d = cloneCandidate(), p = d.plots[0];
  p.compact_result = Object.fromEntries(Object.entries(p.compact_result).reverse()); validateJrc(d, main);
  p.source_result.extra = { n: 0 }; p.compact_result.extra = { n: null };
  assert.throws(() => validateJrc(d, main), /comparison.equal/);
});
test('native center and corners use the exact JRC affine', () => {
  const g = candidate.native_grid;
  assert.deepEqual(jrcCellPoint(g, 0, 0), [g.transform[2], g.transform[5]]);
  assert.deepEqual(jrcCellPoint(g, 205.5, 151.5), [g.transform[0] * 205.5 + g.transform[2], g.transform[4] * 151.5 + g.transform[5]]);
});
test('forged display equality is independently unconfirmed', () => {
  assert.equal(jrcComparisonAgrees(panelFixture('valid0').plots[0]), true);
  assert.equal(jrcComparisonAgrees(panelFixture('forgedEquality').plots[0]), false);
});

test('optional loader freezes one no-store same-origin body without changing Hansen', async () => {
  const original = globalThis.fetch, before = structuredClone(main), controller = new AbortController(); let requests = 0, reads = 0;
  globalThis.fetch = async (url, options) => {
    requests++; assert.equal(url, '/data/jrc-baseline-v1.json'); assert.equal(options.cache, 'no-store'); assert.strictEqual(options.signal, controller.signal);
    return { ok: true, text: async () => { reads++; return JSON.stringify(candidate); } };
  };
  try { await loadJrc(main, controller.signal); assert.equal(requests, 1); assert.equal(reads, 1); assert.deepEqual(main, before); }
  finally { globalThis.fetch = original; }
});
for (const [name, response, pattern] of [
  ['404', { ok: false, status: 404 }, /HTTP 404/], ['empty', { ok: true, text: async () => ' ' }, /empty/],
  ['HTML fallback', { ok: true, text: async () => '<html>' }, /not valid JSON/],
  ['malformed JSON', { ok: true, text: async () => '{' }, /not valid JSON/],
  ['wrong schema', { ok: true, text: async () => '{"schema_version":"wrong"}' }, /schema_version/],
  ['stream failure', { ok: true, text: async () => { throw new Error('stream'); } }, /Could not read/],
]) test(`optional loader ${name} throws and never supplies no-forest data`, async () => {
  const original = globalThis.fetch; globalThis.fetch = async () => response;
  try { await assert.rejects(loadJrc(main), pattern); } finally { globalThis.fetch = original; }
});
test('network unavailable is explicit', async () => {
  const original = globalThis.fetch; globalThis.fetch = async () => { throw new TypeError('offline'); };
  try { await assert.rejects(loadJrc(main), /Check the local server/); } finally { globalThis.fetch = original; }
});
for (const phase of ['before', 'fetch', 'read']) test(`cancellation survives ${phase}`, async () => {
  const original = globalThis.fetch, c = new AbortController();
  if (phase === 'before') c.abort();
  globalThis.fetch = async () => {
    if (phase === 'fetch') { c.abort(); throw c.signal.reason; }
    return { ok: true, text: async () => { c.abort(); throw c.signal.reason; } };
  };
  try { await assert.rejects(loadJrc(main, c.signal), e => e === c.signal.reason); } finally { globalThis.fetch = original; }
});
