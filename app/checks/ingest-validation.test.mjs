// Node 26 strips the type-only import in data.ts. No build or new dependency.
import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { performance } from 'node:perf_hooks';
import { validateDemo, loadDemo } from '../src/data.ts';

// Freeze each file once: the engine can regenerate canonical output concurrently.
const demo = JSON.parse(readFileSync(new URL('../../artifacts/demo-v1.json', import.meta.url), 'utf8'));
const synthetic = JSON.parse(readFileSync(new URL('../../artifacts/synthetic-v1.json', import.meta.url), 'utf8'));
const clone = () => structuredClone(demo);
const first = d => d.plots[0];
const p3 = d => d.plots.find(p => p.plot_id === 'P-0003');
const mutate = fn => {
  const d = clone(); fn(d);
  // Explicitly omitting metrics also omits the retained-benchmark claim.
  if (d.benchmark === null && d.benchmark_status?.state === 'bound_retained') d.benchmark_status.state = 'not_included';
  return d;
};
const reject = (name, fn, match = /Invalid demo artifact/) => test(name, () => assert.throws(() => validateDemo(mutate(fn)), match));
function fixtureResult(result, evidence = null) {
  return mutate(d => {
    const p = first(d);
    p.source_result = structuredClone(result);
    p.compact_result = structuredClone(result);
    p.comparison = { equal: true, differing_fields: [], source_result_sha256: null, compact_result_sha256: null };
    p.receipt = null; p.evidence = evidence;
    d.summary = null; d.benchmark = null;
  });
}
function fallback() {
  return mutate(d => {
    d.dataset = { status: 'declarations_only', sources: d.plots[0].receipt.supplier_sources };
    d.periods = ['2021-2023', '2024-2025'];
    d.summary = null; d.benchmark = null;
    for (const p of d.plots) for (const k of ['source_result', 'compact_result', 'comparison', 'receipt', 'evidence']) p[k] = null;
    delete d.benchmark_status;
  });
}
function reverseKeys(value) {
  if (Array.isArray(value)) return value.map(reverseKeys);
  if (value && typeof value === 'object') return Object.fromEntries(Object.entries(value).reverse().map(([k, v]) => [k, reverseKeys(v)]));
  return value;
}

test('canonical frozen export passes without mutation or manufactured proof', () => {
  const before = structuredClone(demo);
  assert.strictEqual(validateDemo(demo), demo);
  assert.deepStrictEqual(demo, before);
  assert.equal(demo.plots.length, 17);
});
test('object key order does not decide query equality', () => {
  const d = mutate(d => { for (const p of d.plots) p.compact_result = reverseKeys(p.compact_result); });
  assert.strictEqual(validateDemo(d), d);
});
test('explicit declaration-only fallback stays entirely uncomputed', () => {
  const d = fallback(); assert.strictEqual(validateDemo(d), d);
  assert.equal(d.plots[0].source_result, null); assert.equal(d.summary, null);
});
test('valid source-only pending codec handoff is accepted', () => {
  const d = mutate(d => {
    d.summary.exact_match_count = null; d.summary.comparison_status = 'pending_codec'; d.benchmark = null;
    for (const p of d.plots) {
      p.compact_result = null; p.comparison.equal = null;
      p.comparison.status = 'pending_codec'; p.comparison.compact_result_sha256 = null;
    }
  });
  assert.strictEqual(validateDemo(d), d);
});
test('nullable source/compact/comparison awaiting computation remain nullable', () => {
  const d = mutate(d => {
    first(d).source_result = null; first(d).compact_result = null; first(d).comparison = null;
    first(d).receipt = null; first(d).evidence = null; d.summary = null; d.benchmark = null;
  });
  assert.strictEqual(validateDemo(d), d);
});
test('uncomputed comparison with two available outputs makes no equality claim', () => {
  const d = mutate(d => { first(d).comparison = null; d.summary.exact_match_count = null; d.summary.comparison_status = 'pending_comparison'; });
  assert.strictEqual(validateDemo(d), d);
});

for (const c of synthetic.cases) test(`accept engine synthetic support semantics: ${c.case_id}`, () => {
  // Synthetic result is tested in memory, never written or merged into real data.
  const d = fixtureResult(c.result);
  assert.strictEqual(validateDemo(d), d);
  assert.deepStrictEqual(first(d).source_result, c.result);
});
test('missing datamask retains zero diagnostics and unavailable analytical outputs', () => {
  const r = structuredClone(synthetic.cases.find(c => c.case_id === 'missing_loss_band').result);
  r.datamask_counts = { 0: 0, 1: 0, 2: 0 };
  r.unknown_reasons = ['band_mask_invalid', 'no_valid_land', 'missing_band:datamask'];
  validateDemo(fixtureResult(r));
});
test('missing bands with no selected centers do not invent in-chip invalid counts', () => {
  const r = structuredClone(synthetic.cases.find(c => c.case_id === 'tiny_no_centers').result);
  r.support = 'unavailable'; r.unknown_reasons.push('missing_band:lossyear');
  validateDemo(fixtureResult(r));
});
test('stored raw valid cells remain inspectable when a missing band globally disables queries', () => {
  const c = synthetic.cases.find(c => c.case_id === 'missing_loss_band');
  const d = fixtureResult(c.result, structuredClone(c.evidence));
  // This case uses the engine's fictitious 4x4 grid, not the Hansen grid.
  d.dataset = { ...d.dataset, ...synthetic.dataset };
  for (const p of d.plots.slice(1)) { p.receipt = null; p.evidence = null; }
  validateDemo(d);
});
test('valid null outside-cell raw values survive without coercion to zero', () => {
  const r = { selected_cell_count: 1, in_coverage_cell_count: 0, out_of_coverage_cell_count: 1,
    valid_land_cell_count: 0, unknown_cell_count: 1, datamask_counts: {0:0,1:0,2:0},
    canopy_histogram: null, lossyear_histogram: null, yearly_loss_counts: null,
    periods: {'2021-2023': {mapped_loss_present:null,observed_loss_cell_count:null}, '2024-2025': {mapped_loss_present:null,observed_loss_cell_count:null}},
    support: 'none', unknown_reasons: ['out_of_coverage', 'no_valid_land'] };
  const cell = structuredClone(first(demo).evidence.features[0]);
  cell.properties = {...cell.properties, row:-1,col:-1,in_coverage:false, treecover2000:null,lossyear:null,datamask:null,band_validity:[false,false,false],valid_land:false};
  const d = fixtureResult(r, { type:'FeatureCollection', features:[cell] });
  validateDemo(d);
  assert.equal(first(d).evidence.features[0].properties.lossyear, null);
});

reject('reject the exact validator false-equality mutation', d => {
  const p = p3(d);
  p.compact_result.yearly_loss_counts['2023'] = 1;
  p.compact_result.lossyear_histogram[0] -= 1;
  p.compact_result.lossyear_histogram[23] += 1;
  p.compact_result.periods['2021-2023'] = { mapped_loss_present:true, observed_loss_cell_count:1 };
}, /comparison.equal: declared equality contradicts/);
reject('deep equality checks canopy fields outside the visible period table', d => {
  const p = first(d), h = p.compact_result.canopy_histogram;
  const from = h.findIndex(v => v > 0), to = (from + 1) % h.length;
  h[from]--; h[to]++;
}, /comparison.equal/);
reject('deep equality includes unknown extension fields with type differences', d => {
  first(d).source_result.extension = { observed: 1 };
  first(d).compact_result.extension = { observed: true };
}, /comparison.equal/);
test('a truthful computed mismatch is accepted and does not count as a match', () => {
  const d = mutate(d => {
    const p = first(d), h = p.compact_result.canopy_histogram;
    const from = h.findIndex(v => v > 0), to = (from + 1) % h.length;
    h[from]--; h[to]++;
    p.comparison.equal = false;
    p.comparison.differing_fields = [`canopy_histogram[${from}]`, `canopy_histogram[${to}]`];
    p.comparison.compact_result_sha256 = '1'.repeat(64);
    d.summary.exact_match_count--;
  });
  validateDemo(d); assert.equal(first(d).comparison.equal, false);
});
reject('false equality cannot be claimed for actually identical outputs', d => { first(d).comparison.equal = false; });
reject('different output fields cannot be hidden behind an incomplete differing_fields list', d => {
  const p = first(d); p.compact_result.extension = 1; p.comparison.equal = false;
  p.comparison.compact_result_sha256 = '1'.repeat(64);
});
reject('null outputs are not two equal computed results', d => {
  const p = first(d); p.source_result = null; p.compact_result = null;
  p.comparison.source_result_sha256 = null; p.comparison.compact_result_sha256 = null;
}, /equality requires both/);
for (const v of ['true', 1, 0, '', {}, []]) reject(`reject malformed comparison equal ${JSON.stringify(v)}`, d => { first(d).comparison.equal = v; });
for (const v of ['false', 'true', 0, 1, '', {}, [], undefined]) reject(`reject malformed mapped signal ${JSON.stringify(v)}`, d => { first(d).source_result.periods['2021-2023'].mapped_loss_present = v; }, /mapped_loss_present/);
test('partial observed absence cannot turn false/green', () => {
  const c = synthetic.cases.find(c => c.case_id === 'partial_absence_unknown');
  const d = fixtureResult(c.result); first(d).source_result.periods['2021-2023'].mapped_loss_present = false;
  assert.throws(() => validateDemo(d), /mapped_loss_present/);
});
test('partial observed positive cannot be hidden as null', () => {
  const c = synthetic.cases.find(c => c.case_id === 'partial_positive_known');
  const d = fixtureResult(c.result); first(d).source_result.periods['2024-2025'].mapped_loss_present = null;
  assert.throws(() => validateDemo(d), /mapped_loss_present/);
});
test('valid missing-band mask diagnostics must not be interpreted as analytical support', () => {
  const c = synthetic.cases.find(c => c.case_id === 'missing_loss_band');
  const d = fixtureResult(c.result); first(d).source_result.periods['2021-2023'] = {mapped_loss_present:false, observed_loss_cell_count:0};
  assert.throws(() => validateDemo(d), /observed_loss_cell_count/);
});
for (const v of [-1, 0.5, '1', NaN, Infinity, Number.MAX_SAFE_INTEGER + 1]) reject(`reject invalid integer counts ${String(v)}`, d => { first(d).source_result.selected_cell_count = v; }, /selected_cell_count/);
reject('histogram bins must be integers, not merely nonnegative floats', d => { first(d).source_result.canopy_histogram[0] = 0.5; }, /canopy_histogram/);
reject('histogram support must sum to valid land', d => { first(d).source_result.lossyear_histogram[0]++; }, /integer bins summing/);
reject('histogram has fixed native value-domain length', d => { first(d).source_result.canopy_histogram.pop(); });
reject('yearly counts must agree with histogram', d => { first(d).source_result.yearly_loss_counts['2023']++; }, /year 2023/);
reject('coverage counts must balance', d => { first(d).source_result.out_of_coverage_cell_count++; }, /coverage counts/);
reject('unknown counts cannot be larger than selected support', d => { first(d).source_result.unknown_cell_count = 100000; });
reject('diagnostic mask counts cannot exceed coverage', d => { first(d).source_result.datamask_counts['2'] = 100000; });
reject('available land cannot suppress histograms with null', d => { first(d).source_result.canopy_histogram = null; });
reject('17 unique joined IDs are required', d => { d.plots.pop(); }, /17 joined/);
reject('duplicate IDs are rejected', d => { d.plots[1].plot_id = first(d).plot_id; }, /duplicate plot ID/);
reject('supplier IDs match exactly without trimming', d => { first(d).supplier.a3_plot_id += ' '; }, /match plot ID exactly/);
reject('geometry properties preserve exact joined ID', d => { first(d).geometry_properties.ProductionPlace = 'WRONG'; });
reject('supplier fields must preserve strings', d => { first(d).supplier.a7_size_of_plot_ha = 5; }, /expected a string/);
for (const v of [NaN, Infinity, -Infinity, '99', null]) reject(`reject nonfinite or malformed geometry ${String(v)}`, d => { first(d).geometry.coordinates[0][1][0] = v; }, /finite number/);
reject('open ring is rejected', d => { first(d).geometry.coordinates[0].pop(); }, /explicitly closed/);
reject('short ring is rejected', d => { first(d).geometry.coordinates[0] = [[0,0],[1,1],[0,0]]; }, /at least four/);
reject('unsupported geometry type is explicit', d => { first(d).geometry.type = 'MultiPolygon'; }, /expected Polygon/);
reject('native evidence geometry must also be finite', d => { first(d).evidence.features[0].geometry.coordinates[0][1][1] = Infinity; });
reject('duplicate native evidence cells are rejected', d => { first(d).evidence.features[1] = structuredClone(first(d).evidence.features[0]); }, /must be unique/);
reject('null raw values require explicit unavailable band support', d => { first(d).evidence.features[0].properties.lossyear = null; }, /null raw cell values/);
reject('invalid bands cannot advertise valid land', d => { first(d).evidence.features[0].properties.band_validity[0] = false; }, /valid_land/);
reject('internally valid source counts cannot contradict evidence validity', d => {
  const cell = first(d).evidence.features[0];
  cell.properties.band_validity[0] = false; cell.properties.valid_land = false;
}, /evidence land and unknown support/);
reject('diagnostic mask support cannot contradict native evidence', d => {
  const cell = first(d).evidence.features[0];
  cell.properties.datamask = 2; cell.properties.valid_land = false;
}, /evidence diagnostic datamask/);
reject('receipt contract cannot contradict executed query contract', d => { first(d).receipt.query_version = 'wrong-query.v99'; });
reject('receipt period definitions must match', d => { first(d).receipt.observed_periods['2021-2023'] = [2099,2099]; });
reject('receipt grid must match dataset', d => { first(d).receipt.grid.shape[0]++; });
reject('summary count cannot contradict source count', d => { d.summary.selected_cell_count_sum = 1; });
reject('summary cannot manufacture full-cohort agreement', d => { d.summary.exact_match_count = 16; });
reject('summary tri-state totals must reflect observations', d => { d.summary.mapped_loss_plot_counts['2021-2023'].unknown++; });
reject('SHA values require digest syntax without claiming verification', d => { d.content_sha256 = 'verified'; });
reject('benchmark inclusion status must agree with presence', d => { d.benchmark_status = {state:'not_included'}; });
test('self digests are declared, not treated as authentication', () => {
  const d = mutate(d => { d.content_sha256 = '0'.repeat(64); first(d).receipt.receipt_sha256 = '0'.repeat(64); });
  validateDemo(d);
});
test('declarations_only cannot retain computed proof', () => {
  const d = fallback(); first(d).source_result = demo.plots[0].source_result;
  assert.throws(() => validateDemo(d), /declarations_only cannot include/);
});

test('loadDemo fetches only one no-store response and validates the frozen text body', async () => {
  const original = globalThis.fetch, controller = new AbortController();
  let requests = 0, reads = 0;
  globalThis.fetch = async (url, options) => {
    requests++; assert.equal(url, '/data/demo-v1.json'); assert.equal(options.cache, 'no-store'); assert.strictEqual(options.signal, controller.signal);
    return { ok:true, status:200, text:async () => { reads++; return JSON.stringify(demo); }, json:() => { throw Error('must not parse a second body'); } };
  };
  try { const d = await loadDemo(controller.signal); assert.equal(d.plots.length, 17); assert.equal(requests, 1); assert.equal(reads, 1); }
  finally { globalThis.fetch = original; }
});
for (const [name, response, match] of [
  ['HTTP error', { ok:false, status:404 }, /HTTP 404/],
  ['empty body', { ok:true, text:async () => ' \n' }, /response is empty/],
  ['HTML fallback body', { ok:true, text:async () => '<!doctype html>' }, /not valid JSON/],
  ['invalid JSON', { ok:true, text:async () => '{' }, /not valid JSON/],
  ['wrong schema', { ok:true, text:async () => '{"schema_version":"wrong"}' }, /schema_version/],
  ['unreadable body', { ok:true, text:async () => { throw Error('stream failed'); } }, /Could not read/],
]) test(`loadDemo reports ${name}`, async () => {
  const original = globalThis.fetch; globalThis.fetch = async () => response;
  try { await assert.rejects(loadDemo(), match); } finally { globalThis.fetch = original; }
});
test('loadDemo validates equality before returning incoming data', async () => {
  const invalid = mutate(d => { first(d).compact_result.extension = true; });
  const original = globalThis.fetch; globalThis.fetch = async () => new Response(JSON.stringify(invalid));
  try { await assert.rejects(loadDemo(), /comparison.equal/); } finally { globalThis.fetch = original; }
});
test('loadDemo reports network failure as an actionable local error', async () => {
  const original = globalThis.fetch; globalThis.fetch = async () => { throw new TypeError('network'); };
  try { await assert.rejects(loadDemo(), /Check the local server/); } finally { globalThis.fetch = original; }
});
test('loadDemo preserves abort cancellation rather than reporting artifact failure', async () => {
  const original = globalThis.fetch, controller = new AbortController();
  controller.abort(); globalThis.fetch = async () => { throw controller.signal.reason; };
  try { await assert.rejects(loadDemo(controller.signal), e => e === controller.signal.reason); } finally { globalThis.fetch = original; }
});
test('loadDemo preserves cancellation during body read', async () => {
  const original = globalThis.fetch, controller = new AbortController();
  globalThis.fetch = async () => ({ok:true, text:async () => { controller.abort(); throw controller.signal.reason; }});
  try { await assert.rejects(loadDemo(controller.signal), e => e === controller.signal.reason); } finally { globalThis.fetch = original; }
});
test('bounded validation timing on the frozen real cohort (diagnostic only)', t => {
  const start = performance.now();
  for (let i = 0; i < 25; i++) validateDemo(demo);
  t.diagnostic(`17 plots / ${demo.plots.reduce((n,p) => n + p.evidence.features.length,0)} cells: mean ${((performance.now()-start)/25).toFixed(2)} ms (25 validations, not a geospatial query benchmark)`);
});
