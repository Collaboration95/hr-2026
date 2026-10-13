import { isDeepStrictEqual } from 'node:util';

const years = Array.from({ length: 25 }, (_, i) => String(i + 2001));
const periods = { '2021-2023': ['2021', '2022', '2023'], '2024-2025': ['2024', '2025'] };
const countKeys = ['selected_cell_count', 'in_coverage_cell_count', 'out_of_coverage_cell_count', 'valid_land_cell_count', 'unknown_cell_count'];
const integer = value => Number.isSafeInteger(value) && value >= 0;
const object = value => value !== null && typeof value === 'object' && !Array.isArray(value);

/** Read-only semantic checks of the published v1 contract. Does not query source rasters. */
export function validateArtifact(data, { expectedPlots } = {}) {
  const errors = [];
  const warnings = [];
  const check = (condition, path, message) => { if (!condition) errors.push(`${path}: ${message}`); };
  if (!object(data)) return { errors: ['artifact: expected an object'], warnings };
  check(data.schema_version === 'plotline.demo.v1', 'schema_version', 'expected plotline.demo.v1');
  check(data.query_version === 'hansen-centers.v1', 'query_version', 'expected hansen-centers.v1');
  check(object(data.dataset), 'dataset', 'source metadata must be present');
  check(data.periods !== undefined, 'periods', 'period definitions must be present');
  check(object(data.summary), 'summary', 'summary must be present');
  check(Array.isArray(data.limitations), 'limitations', 'limitations must be an array');
  if (data.benchmark === null) warnings.push('benchmark: unmeasured; UI must show unavailable, not a numeric claim');
  else check(object(data.benchmark), 'benchmark', 'must be an object or explicit null');
  if (!Array.isArray(data.plots)) return { errors: [...errors, 'plots: expected an array'], warnings };
  if (expectedPlots !== undefined) check(data.plots.length === expectedPlots, 'plots', `expected ${expectedPlots} records`);
  const ids = new Set();
  for (const [index, plot] of data.plots.entries()) {
    const path = `plots[${index}]`;
    if (!object(plot)) { check(false, path, 'expected an object'); continue; }
    check(typeof plot.plot_id === 'string' && plot.plot_id.length > 0, `${path}.plot_id`, 'expected nonempty exact ID');
    check(!ids.has(plot.plot_id), `${path}.plot_id`, 'duplicate plot ID');
    ids.add(plot.plot_id);
    check(object(plot.geometry) && ['Polygon', 'MultiPolygon'].includes(plot.geometry.type) && Array.isArray(plot.geometry.coordinates), `${path}.geometry`, 'expected GeoJSON polygon geometry');
    check(object(plot.supplier) && Object.values(plot.supplier).every(v => typeof v === 'string'), `${path}.supplier`, 'declarations must retain CSV strings');
    check(object(plot.receipt), `${path}.receipt`, 'receipt/provenance must be present');
    check(object(plot.evidence) && plot.evidence.type === 'FeatureCollection' && Array.isArray(plot.evidence.features), `${path}.evidence`, 'expected GeoJSON FeatureCollection');
    validateResult(plot.source_result, `${path}.source_result`);
    validateResult(plot.compact_result, `${path}.compact_result`);
    if (!object(plot.comparison)) { check(false, `${path}.comparison`, 'expected comparison object'); continue; }
    const same = isDeepStrictEqual(plot.source_result, plot.compact_result);
    check(typeof plot.comparison.equal === 'boolean' && plot.comparison.equal === same, `${path}.comparison.equal`, 'advertised equality must match actual query results');
    check(Array.isArray(plot.comparison.differing_fields), `${path}.comparison.differing_fields`, 'expected an array');
    if (same) check(plot.comparison.differing_fields?.length === 0, `${path}.comparison.differing_fields`, 'equal results cannot list differences');
    for (const key of ['source_result_sha256', 'compact_result_sha256']) check(/^[a-f0-9]{64}$/i.test(plot.comparison[key] ?? ''), `${path}.comparison.${key}`, 'expected SHA-256 digest');
    if (same) check(plot.comparison.source_result_sha256 === plot.comparison.compact_result_sha256, `${path}.comparison`, 'equal results should have equal contract digests');
  }
  return { errors, warnings };

  function validateResult(result, path) {
    if (!object(result)) { check(false, path, 'expected query result object'); return; }
    for (const key of countKeys) check(integer(result[key]), `${path}.${key}`, 'expected nonnegative safe integer');
    check(['complete', 'partial', 'none', 'unavailable'].includes(result.support), `${path}.support`, 'unexpected support state');
    check(Array.isArray(result.unknown_reasons) && result.unknown_reasons.every(v => typeof v === 'string'), `${path}.unknown_reasons`, 'expected string array');
    check(result.selected_cell_count === result.in_coverage_cell_count + result.out_of_coverage_cell_count, path, 'coverage counts must sum to selected centers');
    check(result.valid_land_cell_count <= result.in_coverage_cell_count, path, 'valid land cannot exceed covered centers');
    check(result.unknown_cell_count <= result.selected_cell_count, path, 'unknown cannot exceed selected centers');
    if (result.support === 'complete') {
      check(result.out_of_coverage_cell_count === 0 && result.unknown_cell_count === 0, `${path}.support`, 'complete support cannot have unknown or uncovered centers');
    }
    check(object(result.datamask_counts) && ['0', '1', '2'].every(k => integer(result.datamask_counts[k])), `${path}.datamask_counts`, 'expected nonnegative 0/1/2 counts');
    const suppressed = result.selected_cell_count === 0 || result.valid_land_cell_count === 0 || (Array.isArray(result.unknown_reasons) && result.unknown_reasons.some(v => typeof v === 'string' && v.startsWith('missing_band:')));
    for (const [key, length] of [['canopy_histogram', 101], ['lossyear_histogram', 26]]) {
      const histogram = result[key];
      check(histogram === null || (Array.isArray(histogram) && histogram.length === length && histogram.every(integer)), `${path}.${key}`, `expected null or ${length} integer bins`);
      if (suppressed) check(histogram === null, `${path}.${key}`, 'analytical outputs must be null without selected valid land or a required band');
      if (Array.isArray(histogram)) check(histogram.reduce((a, b) => a + b, 0) === result.valid_land_cell_count, `${path}.${key}`, 'histogram support must equal valid land count');
    }
    const annual = result.yearly_loss_counts;
    check(annual === null || (object(annual) && years.every(y => integer(annual[y]))), `${path}.yearly_loss_counts`, 'expected null or all 2001–2025 integer counts');
    if (suppressed) check(annual === null, `${path}.yearly_loss_counts`, 'analytical outputs must be null');
    if (object(annual) && Array.isArray(result.lossyear_histogram)) {
      for (const [i, year] of years.entries()) check(annual[year] === result.lossyear_histogram[i + 1], `${path}.yearly_loss_counts.${year}`, 'must match the loss-year histogram');
    }
    if (!object(result.periods)) { check(false, `${path}.periods`, 'expected period object'); return; }
    for (const [key, periodYears] of Object.entries(periods)) {
      const period = result.periods[key];
      const p = `${path}.periods.${key}`;
      if (!object(period)) { check(false, p, 'expected period result'); continue; }
      const signal = period.mapped_loss_present;
      const count = period.observed_loss_cell_count;
      check(signal === true || signal === false || signal === null, `${p}.mapped_loss_present`, 'expected true, false or null');
      check(count === null || integer(count), `${p}.observed_loss_cell_count`, 'expected integer or null');
      if (suppressed) check(signal === null && count === null, p, 'suppressed analytical period must stay unknown');
      if (object(annual)) check(count === periodYears.reduce((sum, y) => sum + annual[y], 0), `${p}.observed_loss_cell_count`, 'must sum actual yearly observed counts');
      if (integer(count) && count > 0) check(signal === true, p, 'witnessed loss must remain true even with partial support');
      if (signal === true) check(integer(count) && count > 0, p, 'true requires an observed positive');
      if (signal === false) check(count === 0 && result.support === 'complete' && result.valid_land_cell_count > 0 && !suppressed, p, 'false requires complete known support and valid land');
      if (!suppressed && count === 0) check(signal === (result.support === 'complete' ? false : null), p, 'absence under incomplete support must remain unknown');
    }
  }
}
