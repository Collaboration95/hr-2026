import test from 'node:test';
import assert from 'node:assert/strict';
import { createHash } from 'node:crypto';
import { validateArtifact } from './contract-check.mjs';

// Synthetic contract fixtures only. These are not company data or measured observations.
function fixture({ support = 'complete', loss = 0, suppressed = false, missing = false } = {}) {
  const canopy = Array(101).fill(0); canopy[50] = 1;
  const histogram = Array(26).fill(0); histogram[loss ? 21 : 0] = 1;
  const annual = Object.fromEntries(Array.from({ length: 25 }, (_, i) => [String(i + 2001), loss && i === 20 ? 1 : 0]));
  const result = {
    selected_cell_count: support === 'partial' ? 2 : 1,
    in_coverage_cell_count: 1,
    out_of_coverage_cell_count: support === 'partial' ? 1 : 0,
    valid_land_cell_count: suppressed ? 0 : 1,
    unknown_cell_count: support === 'partial' ? 1 : 0,
    datamask_counts: { '0': 0, '1': suppressed ? 0 : 1, '2': suppressed ? 1 : 0 },
    canopy_histogram: suppressed || missing ? null : canopy,
    lossyear_histogram: suppressed || missing ? null : histogram,
    yearly_loss_counts: suppressed || missing ? null : annual,
    periods: {
      '2021-2023': { mapped_loss_present: suppressed || missing ? null : loss ? true : support === 'complete' ? false : null, observed_loss_cell_count: suppressed || missing ? null : loss },
      '2024-2025': { mapped_loss_present: suppressed || missing ? null : support === 'complete' ? false : null, observed_loss_cell_count: suppressed || missing ? null : 0 },
    },
    support,
    unknown_reasons: missing ? ['missing_band:lossyear'] : support === 'partial' ? ['out_of_coverage'] : suppressed ? ['no_valid_land'] : [],
  };
  const digest = createHash('sha256').update(JSON.stringify(result)).digest('hex');
  return {
    schema_version: 'plotline.demo.v1', query_version: 'hansen-centers.v1', dataset: { fixture: 'synthetic test only' },
    periods: ['2021-2023', '2024-2025'], summary: {}, benchmark: null, limitations: ['Synthetic test only'],
    plots: [{ plot_id: 'synthetic-1', geometry: { type: 'Polygon', coordinates: [[[0, 0], [1, 0], [1, 1], [0, 0]]] }, supplier: { declaration: 'synthetic' },
      source_result: result, compact_result: structuredClone(result),
      comparison: { equal: true, differing_fields: [], source_result_sha256: digest, compact_result_sha256: digest },
      receipt: { fixture: 'synthetic' }, evidence: { type: 'FeatureCollection', features: [] } }],
  };
}

test('accept complete known absence, partial unknown absence, and partial witnessed loss', () => {
  for (const options of [{}, { support: 'partial' }, { support: 'partial', loss: 1 }, { suppressed: true }, { missing: true }]) {
    assert.deepEqual(validateArtifact(fixture(options), { expectedPlots: 1 }).errors, []);
  }
});

test('reject incomplete-support absence incorrectly presented as false', () => {
  const data = fixture({ support: 'partial' });
  data.plots[0].source_result.periods['2021-2023'].mapped_loss_present = false;
  assert.ok(validateArtifact(data).errors.some(error => error.includes('false requires complete known support')));
});

test('reject witnessed positive incorrectly presented as unknown', () => {
  const data = fixture({ support: 'partial', loss: 1 });
  data.plots[0].source_result.periods['2021-2023'].mapped_loss_present = null;
  assert.ok(validateArtifact(data).errors.some(error => error.includes('witnessed loss must remain true')));
});

test('reject claimed equality when compact output differs', () => {
  const data = fixture();
  data.plots[0].compact_result.unknown_reasons = ['synthetic mismatch'];
  assert.ok(validateArtifact(data).errors.some(error => error.includes('advertised equality')));
});

test('reject missing-band analytical counts and accidental supplier type coercion', () => {
  const data = fixture({ missing: true });
  data.plots[0].source_result.periods['2021-2023'].observed_loss_cell_count = 0;
  data.plots[0].supplier.declaration = true;
  const errors = validateArtifact(data).errors;
  assert.ok(errors.some(error => error.includes('suppressed analytical period')));
  assert.ok(errors.some(error => error.includes('retain CSV strings')));
});

test('reject inconsistent counts, periods and duplicate identities', () => {
  const data = fixture({ loss: 1 });
  data.plots[0].source_result.selected_cell_count = 8;
  data.plots[0].source_result.periods['2021-2023'].observed_loss_cell_count = 2;
  data.plots.push(structuredClone(data.plots[0]));
  const errors = validateArtifact(data).errors;
  assert.ok(errors.some(error => error.includes('coverage counts must sum')));
  assert.ok(errors.some(error => error.includes('sum actual yearly')));
  assert.ok(errors.some(error => error.includes('duplicate plot ID')));
});

test('null benchmarks are explicitly warned without fabricating a number', () => {
  const result = validateArtifact(fixture());
  assert.equal(result.errors.length, 0);
  assert.ok(result.warnings.some(warning => warning.includes('unmeasured')));
});

test('malformed input returns diagnostics rather than throwing', () => {
  for (const value of [null, [], {}, { schema_version: 'wrong', plots: [null, {}] }]) {
    assert.ok(validateArtifact(value).errors.length > 0);
  }
  const data = fixture();
  data.plots[0].source_result.unknown_reasons = 'invalid';
  assert.ok(validateArtifact(data).errors.some(error => error.includes('expected string array')));
});
