import { readFileSync } from 'node:fs';

// A frozen candidate is input for shape tests only, never an accepted UI asset.
export const candidate = JSON.parse(readFileSync(new URL('../../artifacts/jrc-baseline-v1.json', import.meta.url), 'utf8'));
export const main = JSON.parse(readFileSync(new URL('../../artifacts/demo-v1.json', import.meta.url), 'utf8'));
export const cloneCandidate = () => structuredClone(candidate);
const digest = '0'.repeat(64);
const cell = (row, col, value, valid = true) => ({ row, col, value, valid });
export const cases = {
  valid0: { cells: [cell(0, 0, 0)], counts: { '0': 1, '1': 0 }, selected: 1, inside: 1, valid: 1, unknown: 0, flag: false, support: 'complete', reasons: [] },
  positive1: { cells: [cell(0, 0, 1)], counts: { '0': 0, '1': 1 }, selected: 1, inside: 1, valid: 1, unknown: 0, flag: true, support: 'complete', reasons: [] },
  partialAbsence: { cells: [cell(0, 0, 0), cell(-1, 0, null, false)], counts: { '0': 1, '1': 0 }, selected: 2, inside: 1, valid: 1, unknown: 1, flag: null, support: 'partial', reasons: ['out_of_coverage'] },
  partialPositive: { cells: [cell(0, 0, 1), cell(-1, 0, null, false)], counts: { '0': 0, '1': 1 }, selected: 2, inside: 1, valid: 1, unknown: 1, flag: true, support: 'partial', reasons: ['out_of_coverage'] },
  noCenters: { cells: [], counts: null, selected: 0, inside: 0, valid: 0, unknown: 0, flag: null, support: 'none', reasons: ['no_selected_cells'] },
  invalidMask: { cells: [cell(0, 0, 0, false), cell(0, 1, 1, false)], counts: null, selected: 2, inside: 2, valid: 0, unknown: 2, flag: null, support: 'none', reasons: ['band_mask_invalid', 'no_valid_cells'] },
  missingBand: { cells: [cell(0, 0, 1)], counts: null, selected: 1, inside: 1, valid: 0, unknown: 1, flag: null, support: 'unavailable', reasons: ['band_mask_invalid', 'no_valid_cells', 'missing_band'] },
  missingNoCenters: { cells: [], counts: null, selected: 0, inside: 0, valid: 0, unknown: 0, flag: null, support: 'unavailable', reasons: ['no_selected_cells', 'missing_band'] },
  outside: { cells: [cell(-1, 0, null, false)], counts: null, selected: 1, inside: 0, valid: 0, unknown: 1, flag: null, support: 'none', reasons: ['out_of_coverage', 'no_valid_cells'] },
};
export function caseResult(name) {
  const c = cases[name];
  return { selected_cell_count: c.selected, in_coverage_cell_count: c.inside, out_of_coverage_cell_count: c.selected - c.inside,
    valid_cell_count: c.valid, unknown_cell_count: c.unknown, class_counts: structuredClone(c.counts), mapped_forest_present: c.flag,
    support: c.support, unknown_reasons: [...c.reasons] };
}
export function refreshSummary(d) {
  const ps = d.plots;
  d.summary = { plot_count: ps.length, exact_match_count: ps.filter(p => p.comparison.equal).length,
    independent_match_count: ps.filter(p => p.comparison.independent_oracle_equal).length,
    selected_cell_count_sum: ps.reduce((n, p) => n + p.source_result.selected_cell_count, 0),
    class_counts_sum: { '0': ps.reduce((n, p) => n + (p.source_result.class_counts?.['0'] ?? 0), 0), '1': ps.reduce((n, p) => n + (p.source_result.class_counts?.['1'] ?? 0), 0) },
    mapped_forest_plot_counts: { true: ps.filter(p => p.source_result.mapped_forest_present === true).length,
      false: ps.filter(p => p.source_result.mapped_forest_present === false).length, unknown: ps.filter(p => p.source_result.mapped_forest_present === null).length },
    count_note: 'Synthetic shape controls; sum over plots may repeat native cells.' };
}
export function shapeFixture(name) {
  const d = cloneCandidate(), p = d.plots[0];
  d.benchmark = null; d.plots.forEach(p => { p.receipt.benchmark_run = null; });
  p.source_result = caseResult(name); p.compact_result = structuredClone(p.source_result);
  p.evidence.cells = structuredClone(cases[name].cells);
  p.receipt.source_result_sha256 = digest; p.receipt.compact_result_sha256 = digest;
  // Fake hashes deliberately illustrate the UI gate's non-authentication scope.
  p.receipt.evidence_sha256 = digest; p.receipt.receipt_sha256 = digest;
  refreshSummary(d); return d;
}

// Standalone display fixtures: no real supplier/plot geometry, candidate findings,
// benchmark measurements or source receipts enter the isolated browser page.
export function panelFixture(name) {
  const grid = { shape: [1809, 3695], transform: [1 / 12000, 0, 98.77241666666667, 0, -1 / 12000, 8.581916666666666], crs: 'EPSG:4326', query_grid: 'Synthetic display on declared JRC lattice' };
  const r = caseResult(name === 'mismatch' || name === 'forgedEquality' || name === 'pagination' ? 'valid0' : name);
  const cells = name === 'pagination' ? Array.from({ length: 31 }, (_, col) => cell(0, col, 0)) : structuredClone(cases[name === 'mismatch' || name === 'forgedEquality' ? 'valid0' : name].cells);
  if (name === 'pagination') { r.selected_cell_count = r.in_coverage_cell_count = r.valid_cell_count = 31; r.class_counts['0'] = 31; }
  const p = { plot_id: 'SYNTHETIC-JRC', geometry: { type: 'Polygon', coordinates: [[[98.77241666666667, 8.581916666666666], [98.7726, 8.581916666666666], [98.7726, 8.5817], [98.77241666666667, 8.5817], [98.77241666666667, 8.581916666666666]]] }, geometry_sha256: digest,
    source_result: r, compact_result: structuredClone(r), comparison: { equal: true, independent_oracle_equal: true, mismatch_fields: [] },
    evidence: { index_origin: 'zero-based JRC chip row/col', cells }, receipt: { geometry_sha256: digest, receipt_sha256: digest, store: {}, full_chip: { raw_values_equal: true, mask_equal: true, metadata_equal: true } } };
  if (name === 'mismatch' || name === 'forgedEquality') {
    p.compact_result.class_counts = { '0': 0, '1': 1 }; p.compact_result.mapped_forest_present = true;
    if (name === 'mismatch') { p.comparison.equal = false; p.comparison.mismatch_fields = ['class_counts', 'mapped_forest_present']; }
  }
  return { schema_version: 'plotline.jrc-baseline.v1', query_version: 'jrc2020-centers.v1', native_grid: grid,
    dataset: { ...grid, product: 'JRC Global Forest Cover Map 2020', version: 'v4', reference_year: 2020, classes: { '0': 'Non-forest', '1': 'Forest' }, zero_is_valid_class: true,
      citation: 'SYNTHETIC DISPLAY FIXTURE — no source observation or acceptance claimed.', limitations: [], xml_observations: { note: 'Synthetic fixture; production preserves original XML observations.' } },
    store: {}, full_chip: p.receipt.full_chip, plots: [p], benchmark: null, summary: {}, limitations: ['Artificial display controls only.'], content_sha256: digest };
}
