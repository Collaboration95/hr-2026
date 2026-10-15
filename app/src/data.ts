import type { Demo } from './types';

type Obj = Record<string, unknown>;
const bands = ['treecover2000', 'lossyear', 'datamask'] as const;
const periods = { '2021-2023': [2021, 2023], '2024-2025': [2024, 2025] } as const;
const years = Array.from({ length: 25 }, (_, i) => String(2001 + i));
const own = (o: Obj, k: string) => Object.hasOwn(o, k);

function requireValue(condition: unknown, path: string, message: string): asserts condition {
  if (!condition) throw new Error(`Invalid demo artifact at ${path}: ${message}.`);
}
function object(value: unknown, path: string): Obj {
  requireValue(value !== null && typeof value === 'object' && !Array.isArray(value), path, 'expected an object');
  const prototype = Object.getPrototypeOf(value);
  requireValue(prototype === Object.prototype || prototype === null, path, 'expected a JSON object');
  return value as Obj;
}
function array(value: unknown, path: string): unknown[] {
  requireValue(Array.isArray(value), path, 'expected an array');
  return value;
}
function text(value: unknown, path: string, nonempty = false): string {
  requireValue(typeof value === 'string' && (!nonempty || value.trim().length > 0), path, 'expected a string' + (nonempty ? ' with content' : ''));
  return value;
}
function strings(value: unknown, path: string): string[] {
  return array(value, path).map((v, i) => text(v, `${path}[${i}]`, true));
}
function integer(value: unknown, path: string, minimum = 0): number {
  requireValue(typeof value === 'number' && Number.isSafeInteger(value) && value >= minimum, path, `expected a safe integer >= ${minimum}`);
  return value;
}
function finite(value: unknown, path: string): number {
  requireValue(typeof value === 'number' && Number.isFinite(value), path, 'expected a finite number');
  return value;
}
function keys(o: Obj, expected: readonly string[], path: string) {
  requireValue(Object.keys(o).length === expected.length && expected.every(k => own(o, k)), path, `expected keys ${expected.join(', ')}`);
}
function digest(value: unknown, path: string, nullable = false) {
  requireValue((nullable && value === null) || (typeof value === 'string' && /^[a-f0-9]{64}$/.test(value)), path, `expected ${nullable ? 'null or ' : ''}a lowercase SHA-256 digest`);
}
function point(value: unknown, path: string) {
  const p = array(value, path);
  requireValue(p.length === 2, path, 'expected two coordinates');
  p.forEach((v, i) => finite(v, `${path}[${i}]`));
  return p;
}
function geometry(value: unknown, path: string) {
  const g = object(value, path);
  requireValue(g.type === 'Polygon', `${path}.type`, 'expected Polygon');
  const rings = array(g.coordinates, `${path}.coordinates`);
  requireValue(rings.length > 0, path, 'expected an exterior ring');
  let vertices = 0;
  rings.forEach((value, i) => {
    const p = `${path}.coordinates[${i}]`, ring = array(value, p);
    vertices += ring.length;
    requireValue(vertices <= 100_000, path, 'too many geometry vertices');
    requireValue(ring.length >= 4, p, 'rings need at least four positions');
    const positions = ring.map((v, j) => point(v, `${p}[${j}]`));
    const first = positions[0], last = positions[positions.length - 1];
    requireValue(first[0] === last[0] && first[1] === last[1], p, 'ring must be explicitly closed');
  });
}

// Compare structure, including extension fields, independently of object key order.
// Hashes supplied by the artifact are not used as evidence of equality.
function differences(a: unknown, b: unknown, path = '', depth = 0): string[] {
  requireValue(depth <= 64, path || 'query result', 'result nesting exceeds the supported depth');
  if (a === b) return [];
  if (Array.isArray(a) && Array.isArray(b)) {
    if (a.length !== b.length) return [path];
    return a.flatMap((v, i) => differences(v, b[i], `${path}[${i}]`, depth + 1));
  }
  if (a !== null && b !== null && typeof a === 'object' && typeof b === 'object' && !Array.isArray(a) && !Array.isArray(b)) {
    const left = object(a, path), right = object(b, path);
    return [...new Set([...Object.keys(left), ...Object.keys(right)])].sort().flatMap(k => {
      const child = path ? `${path}.${k}` : k;
      return !own(left, k) || !own(right, k) ? [child] : differences(left[k], right[k], child, depth + 1);
    });
  }
  return [path || '$'];
}
const equal = (a: unknown, b: unknown) => differences(a, b).length === 0;

function result(value: unknown, path: string): Obj | null {
  if (value === null) return null;
  const r = object(value, path);
  const n = integer(r.selected_cell_count, `${path}.selected_cell_count`);
  const inside = integer(r.in_coverage_cell_count, `${path}.in_coverage_cell_count`);
  const outside = integer(r.out_of_coverage_cell_count, `${path}.out_of_coverage_cell_count`);
  const land = integer(r.valid_land_cell_count, `${path}.valid_land_cell_count`);
  const unknown = integer(r.unknown_cell_count, `${path}.unknown_cell_count`);
  requireValue(n === inside + outside, path, 'coverage counts must sum to selected cells');
  requireValue(unknown >= outside && unknown <= n && land <= inside && land + unknown <= n, path, 'land and unknown counts must fit selected support');
  const reasons = strings(r.unknown_reasons, `${path}.unknown_reasons`);
  requireValue(new Set(reasons).size === reasons.length, `${path}.unknown_reasons`, 'reasons must not repeat');
  const missing = reasons.filter(v => v.startsWith('missing_band:')).map(v => v.slice('missing_band:'.length));
  requireValue(missing.every(v => (bands as readonly string[]).includes(v)), `${path}.unknown_reasons`, 'missing_band must name a required band');
  requireValue((n === 0) === reasons.includes('no_selected_cells'), path, 'no_selected_cells reason must match selected support');
  requireValue((outside > 0) === reasons.includes('out_of_coverage'), path, 'out_of_coverage reason must match uncovered cells');
  requireValue((n > 0 && land === 0) === reasons.includes('no_valid_land'), path, 'no_valid_land reason must match selected support');
  const mask = object(r.datamask_counts, `${path}.datamask_counts`);
  keys(mask, ['0', '1', '2'], `${path}.datamask_counts`);
  const maskCounts = ['0', '1', '2'].map(k => integer(mask[k], `${path}.datamask_counts.${k}`));
  const maskTotal = maskCounts.reduce((a, b) => a + b, 0);
  requireValue(maskTotal <= inside && land <= maskCounts[1], path, 'diagnostic datamask counts must fit covered cells and valid land');
  requireValue(unknown >= outside + maskCounts[0] && unknown >= outside + inside - maskTotal, path, 'unknown count must include nodata and invalid datamask support');
  requireValue((maskCounts[0] > 0) === reasons.includes('nodata'), path, 'nodata reason must match diagnostic counts');
  if (missing.includes('datamask')) requireValue(maskTotal === 0, path, 'missing datamask must retain zero diagnostic mask counts');
  if (missing.length) {
    requireValue(land === 0 && unknown === n, path, 'missing bands disable valid land and make all selected cells unknown');
    if (inside > 0) requireValue(reasons.includes('band_mask_invalid'), path, 'covered cells with missing bands require band_mask_invalid');
  }
  if (reasons.includes('band_mask_invalid')) requireValue(inside > 0 && unknown > outside, path, 'band_mask_invalid requires covered unknown cells');
  if (unknown > outside && maskCounts[0] === 0 && !missing.length) requireValue(reasons.includes('band_mask_invalid'), path, 'covered unknown cells require an invalid-band reason');
  const expectedSupport = missing.length ? 'unavailable' : n === 0 || land === 0 ? 'none' : unknown > 0 ? 'partial' : 'complete';
  requireValue(r.support === expectedSupport, `${path}.support`, `counts and reasons require ${expectedSupport} support`);
  const analytical = land > 0 && missing.length === 0;
  function histogram(key: string, length: number): number[] | null {
    const p = `${path}.${key}`;
    if (!analytical) { requireValue(r[key] === null, p, 'analytical output must be null without available valid land'); return null; }
    const h = array(r[key], p).map((v, i) => integer(v, `${p}[${i}]`));
    requireValue(h.length === length && h.reduce((a, b) => a + b, 0) === land, p, `expected ${length} integer bins summing to valid land`);
    return h;
  }
  histogram('canopy_histogram', 101);
  const loss = histogram('lossyear_histogram', 26);
  if (analytical) {
    const annual = object(r.yearly_loss_counts, `${path}.yearly_loss_counts`);
    keys(annual, years, `${path}.yearly_loss_counts`);
    years.forEach((y, i) => requireValue(integer(annual[y], `${path}.yearly_loss_counts.${y}`) === loss![i + 1], path, `year ${y} must match its histogram bin`));
  } else requireValue(r.yearly_loss_counts === null, `${path}.yearly_loss_counts`, 'analytical output must be null');
  const ps = object(r.periods, `${path}.periods`);
  keys(ps, Object.keys(periods), `${path}.periods`);
  for (const [key, [start, end]] of Object.entries(periods)) {
    const p = `${path}.periods.${key}`, period = object(ps[key], p);
    const count = analytical ? loss!.slice(start - 2000, end - 2000 + 1).reduce((a, b) => a + b, 0) : null;
    const signal = count === null ? null : count > 0 ? true : expectedSupport === 'complete' ? false : null;
    requireValue(period.observed_loss_cell_count === count, `${p}.observed_loss_cell_count`, 'must match observed histogram counts or explicit null');
    requireValue(period.mapped_loss_present === signal, `${p}.mapped_loss_present`, 'positive loss needs observed cells; absence needs complete valid support; otherwise use null');
  }
  return r;
}

function comparison(value: unknown, source: Obj | null, compact: Obj | null, path: string): Obj | null {
  if (value === null) return null;
  const c = object(value, path), fields = strings(c.differing_fields, `${path}.differing_fields`);
  requireValue(c.equal === null || typeof c.equal === 'boolean', `${path}.equal`, 'expected true, false or null');
  for (const [key, output] of [['source_result_sha256', source], ['compact_result_sha256', compact]] as const) {
    digest(c[key], `${path}.${key}`, true);
    if (output === null) requireValue(c[key] === null, `${path}.${key}`, 'uncomputed result cannot have a result digest');
  }
  if (own(c, 'status')) text(c.status, `${path}.status`, true);
  if (c.status === 'pending_codec') requireValue(compact === null, `${path}.status`, 'pending_codec requires an uncomputed compact result');
  if (c.equal === null) {
    requireValue(fields.length === 0 && c.status !== 'computed', path, 'pending comparison cannot claim differences or computed status');
  } else {
    requireValue(source !== null && compact !== null, path, 'equality requires both query results');
    const actual = differences(source, compact);
    requireValue(c.equal === (actual.length === 0), `${path}.equal`, 'declared equality contradicts the query result fields');
    requireValue(new Set(fields).size === fields.length && equal([...fields].sort(), [...actual].sort()), `${path}.differing_fields`, 'must list the actual structural differences');
    requireValue(c.status === undefined || c.status === 'computed', `${path}.status`, 'boolean equality requires computed status');
    if (c.source_result_sha256 !== null && c.compact_result_sha256 !== null) {
      requireValue((c.source_result_sha256 === c.compact_result_sha256) === c.equal, path, 'declared digests contradict the result equality');
    }
  }
  return c;
}

function evidence(value: unknown, source: Obj | null, dataset: Obj, path: string) {
  if (value === null) return;
  const e = object(value, path);
  requireValue(e.type === 'FeatureCollection', `${path}.type`, 'expected FeatureCollection');
  const features = array(e.features, `${path}.features`), ids = new Set<string>();
  let covered = 0, landCount = 0, unknownCount = 0;
  const maskCounts = [0, 0, 0];
  const missing = source ? (source.unknown_reasons as string[]).filter(v => v.startsWith('missing_band:')) : [];
  if (source) requireValue(features.length === source.selected_cell_count, path, 'selected native cell count must match the evidence collection');
  for (const [i, value] of features.entries()) {
    const p = `${path}.features[${i}]`, f = object(value, p);
    requireValue(f.type === 'Feature', `${p}.type`, 'expected Feature');
    geometry(f.geometry, `${p}.geometry`);
    const props = object(f.properties, `${p}.properties`);
    const row = integer(props.row, `${p}.properties.row`, Number.MIN_SAFE_INTEGER);
    const col = integer(props.col, `${p}.properties.col`, Number.MIN_SAFE_INTEGER);
    const shape = dataset.shape as number[];
    const inside = row >= 0 && col >= 0 && row < shape[0] && col < shape[1];
    requireValue(!ids.has(`${row}:${col}`), p, 'native cell row/column must be unique per plot');
    ids.add(`${row}:${col}`);
    if (own(props, 'center')) point(props.center, `${p}.properties.center`);
    if (own(props, 'in_coverage')) {
      requireValue(typeof props.in_coverage === 'boolean', p, 'in_coverage must be boolean');
      requireValue(props.in_coverage === inside, p, 'in_coverage must match the declared grid');
    }
    const validity = own(props, 'band_validity') ? array(props.band_validity, `${p}.properties.band_validity`) : null;
    if (validity) requireValue(validity.length === 3 && validity.every(v => typeof v === 'boolean'), p, 'band_validity must contain three booleans');
    bands.forEach((band, j) => {
      const raw = props[band];
      if (raw === null) requireValue(props.in_coverage === false || validity?.[j] === false, `${p}.properties.${band}`, 'null raw cell values require explicit unavailable support');
      else requireValue(integer(raw, `${p}.properties.${band}`) <= [100, 25, 2][j], p, `${band} exceeds its native domain`);
      if (!inside) requireValue(raw === null && validity?.[j] === false, p, 'outside cells require null values and invalid bands');
    });
    const validLand = inside && props.datamask === 1 && bands.every(b => props[b] !== null) && (!validity || validity.every(v => v === true));
    requireValue(props.valid_land === validLand, `${p}.properties.valid_land`, 'must reflect raw datamask and band validity');
    if (inside) {
      covered++;
      const maskKnown = props.datamask !== null && (!validity || validity[2] === true);
      if (maskKnown) maskCounts[props.datamask as number]++;
      if (validLand) landCount++;
      if (bands.some(b => props[b] === null) || validity?.some(v => v === false) || (maskKnown && props.datamask === 0)) unknownCount++;
    } else unknownCount++;
  }
  if (source) {
    requireValue(covered === source.in_coverage_cell_count, path, 'evidence coverage must match the source query');
    const expectedMasks = missing.includes('missing_band:datamask') ? [0, 0, 0] : maskCounts;
    requireValue(equal(source.datamask_counts, Object.fromEntries(expectedMasks.map((n, i) => [String(i), n]))), path, 'evidence diagnostic datamask counts must match the source query');
    // Missing bands globally disable analytics even when stored evidence is valid.
    requireValue(source.valid_land_cell_count === (missing.length ? 0 : landCount) && source.unknown_cell_count === (missing.length ? features.length : unknownCount), path, 'evidence land and unknown support must match the source query');
  }
}

function sources(value: unknown, path: string) {
  const list = array(value, path);
  requireValue(list.length > 0, path, 'expected source provenance');
  list.forEach((v, i) => {
    const p = `${path}[${i}]`, s = object(v, p);
    text(s.path, `${p}.path`, true);
    digest(s.sha256, `${p}.sha256`);
    if (own(s, 'bytes')) integer(s.bytes, `${p}.bytes`);
  });
}
function receipt(value: unknown, source: Obj | null, dataset: Obj, path: string) {
  if (value === null) return;
  const r = object(value, path);
  for (const key of ['receipt_sha256', 'geometry_sha256', 'supplier_row_sha256', 'source_metadata_sha256']) {
    if (own(r, key)) digest(r[key], `${path}.${key}`);
  }
  if (own(r, 'query_version')) requireValue(r.query_version === 'hansen-centers.v1', `${path}.query_version`, 'receipt must use the envelope query contract');
  if (own(r, 'product')) requireValue(r.product === dataset.product, `${path}.product`, 'receipt product must match dataset');
  if (own(r, 'grid')) requireValue(equal(r.grid, { shape: dataset.shape, crs: dataset.crs, transform: dataset.transform }), `${path}.grid`, 'receipt grid must match dataset');
  if (own(r, 'sources')) requireValue(equal(r.sources, dataset.sources), `${path}.sources`, 'receipt source list must match dataset');
  if (own(r, 'supplier_sources')) sources(r.supplier_sources, `${path}.supplier_sources`);
  if (own(r, 'observed_periods')) requireValue(equal(r.observed_periods, periods), `${path}.observed_periods`, 'receipt periods must match the query contract');
  if (own(r, 'unknown_reasons')) requireValue(source !== null && equal(r.unknown_reasons, source.unknown_reasons), `${path}.unknown_reasons`, 'receipt unknown reasons must match source query');
}

/** Check the frozen export's shape and internal semantics, not source authenticity.
 * Returns the same artifact without fabricating measurements or repairing claims.
 */
export function validateDemo(value: unknown): Demo {
  const d = object(value, 'artifact');
  requireValue(d.schema_version === 'plotline.demo.v1', 'schema_version', 'expected plotline.demo.v1');
  requireValue(d.query_version === 'hansen-centers.v1', 'query_version', 'expected hansen-centers.v1');
  const dataset = object(d.dataset, 'dataset'), declaredOnly = dataset.status === 'declarations_only';
  sources(dataset.sources, 'dataset.sources');
  if (declaredOnly) {
    // sync-data.py's existing fallback uses a period-key array and no mapped grid.
    requireValue(equal(d.periods, Object.keys(periods)) || equal(d.periods, Object.fromEntries(Object.entries(periods).map(([k, [start_year, end_year]]) => [k, { start_year, end_year }]))), 'periods', 'expected the two declared review periods');
  } else {
    text(dataset.product, 'dataset.product', true);
    requireValue(dataset.crs === 'EPSG:4326', 'dataset.crs', 'expected EPSG:4326');
    const shape = array(dataset.shape, 'dataset.shape');
    requireValue(shape.length === 2, 'dataset.shape', 'expected height and width');
    shape.forEach((n, i) => integer(n, `dataset.shape[${i}]`, 1));
    const transform = array(dataset.transform, 'dataset.transform');
    requireValue(transform.length === 6, 'dataset.transform', 'expected six finite transform values');
    transform.forEach((n, i) => finite(n, `dataset.transform[${i}]`));
    requireValue((transform[0] as number) > 0 && transform[1] === 0 && transform[3] === 0 && (transform[4] as number) < 0, 'dataset.transform', 'expected the contract north-up native grid');
    requireValue(equal(dataset.band_names, bands), 'dataset.band_names', 'expected the three required bands in contract order');
    const definitions = object(d.periods, 'periods');
    keys(definitions, Object.keys(periods), 'periods');
    for (const [k, [start_year, end_year]] of Object.entries(periods)) requireValue(equal(definitions[k], { start_year, end_year }), `periods.${k}`, 'period definition must match the query contract');
  }
  strings(d.limitations, 'limitations');
  const plots = array(d.plots, 'plots'), ids = new Set<string>();
  requireValue(plots.length === 17, 'plots', 'expected 17 joined sample plots');
  const validated = plots.map((value, i) => {
    const p = `plots[${i}]`, plot = object(value, p), id = text(plot.plot_id, `${p}.plot_id`, true);
    requireValue(!ids.has(id), `${p}.plot_id`, 'duplicate plot ID'); ids.add(id);
    geometry(plot.geometry, `${p}.geometry`);
    const supplier = object(plot.supplier, `${p}.supplier`);
    Object.entries(supplier).forEach(([k, v]) => text(v, `${p}.supplier.${k}`));
    requireValue(supplier.a3_plot_id === id, `${p}.supplier.a3_plot_id`, 'supplier ID must match plot ID exactly');
    if (own(plot, 'geometry_properties')) requireValue(object(plot.geometry_properties, `${p}.geometry_properties`).ProductionPlace === id, `${p}.geometry_properties.ProductionPlace`, 'geometry ID must match plot ID exactly');
    const source = result(plot.source_result, `${p}.source_result`), compact = result(plot.compact_result, `${p}.compact_result`);
    const compared = comparison(plot.comparison, source, compact, `${p}.comparison`);
    if (declaredOnly) requireValue(source === null && compact === null && compared === null && plot.receipt === null && plot.evidence === null, p, 'declarations_only cannot include mapped observations or encoding proof');
    receipt(plot.receipt, source, dataset, `${p}.receipt`);
    evidence(plot.evidence, source, dataset, `${p}.evidence`);
    return { plot, source, compact, compared };
  });
  if (d.summary !== null) {
    const s = object(d.summary, 'summary');
    requireValue(s.plot_count === 17, 'summary.plot_count', 'must equal the joined cohort size');
    const allSource = validated.every(p => p.source !== null);
    const selected = allSource ? validated.reduce((n, p) => n + (p.source!.selected_cell_count as number), 0) : null;
    if (selected !== null) integer(s.selected_cell_count_sum, 'summary.selected_cell_count_sum');
    requireValue(s.selected_cell_count_sum === selected, 'summary.selected_cell_count_sum', 'must match available source results; incomplete totals require null');
    const allCompared = validated.every(p => typeof p.compared?.equal === 'boolean');
    const matches = allCompared ? validated.filter(p => p.compared!.equal === true).length : null;
    requireValue(s.exact_match_count === matches, 'summary.exact_match_count', 'must match computed comparisons; pending cohort proof requires null');
    if (own(s, 'comparison_status')) requireValue((s.comparison_status === 'computed') === allCompared, 'summary.comparison_status', 'computed status requires every plot comparison');
    if (own(s, 'mapped_loss_plot_counts')) {
      const totals = object(s.mapped_loss_plot_counts, 'summary.mapped_loss_plot_counts');
      keys(totals, Object.keys(periods), 'summary.mapped_loss_plot_counts');
      for (const k of Object.keys(periods)) {
        const expected = { true: 0, false: 0, unknown: 0 };
        for (const p of validated) {
          const signal = p.source ? (p.source.periods as Record<string, Obj>)[k].mapped_loss_present : null;
          expected[signal === true ? 'true' : signal === false ? 'false' : 'unknown']++;
        }
        requireValue(equal(totals[k], expected), `summary.mapped_loss_plot_counts.${k}`, 'must count actual tri-state plot observations');
      }
    }
    if (own(s, 'supplier_indication_count')) requireValue(s.supplier_indication_count === validated.filter(p => (p.plot.supplier as Obj).c2_deforestation_spatial_analysis_result === 'b. Indication of deforestation').length, 'summary.supplier_indication_count', 'must count exact supplier declarations');
  }
  requireValue(d.benchmark === null || (typeof d.benchmark === 'object' && !Array.isArray(d.benchmark) && d.benchmark !== undefined), 'benchmark', 'expected a benchmark object or explicit null');
  if (own(d, 'benchmark_status')) {
    const status = object(d.benchmark_status, 'benchmark_status');
    requireValue(status.state === (d.benchmark === null ? 'not_included' : 'bound_retained'), 'benchmark_status.state', 'declared benchmark inclusion state must match its presence');
  }
  if (declaredOnly) requireValue(d.summary === null && d.benchmark === null, 'artifact', 'declaration fallback must not claim computed summaries or benchmarks');
  if (own(d, 'content_sha256')) digest(d.content_sha256, 'content_sha256');
  // Preserve runtime envelope fields not yet described in types.ts (periods,
  // benchmark_status, content_sha256); the experience lead owns type changes.
  return value as Demo;
}

/** Read and validate one frozen response. No retries, alternate data, or uploads. */
export async function loadDemo(signal?: AbortSignal): Promise<Demo> {
  let response: Response;
  try {
    response = await fetch('/data/demo-v1.json', { cache: 'no-store', signal });
  } catch (error) {
    if (signal?.aborted || (error instanceof Error && error.name === 'AbortError')) throw error;
    throw new Error('Could not fetch the local demo artifact. Check the local server and retry.');
  }
  if (!response.ok) throw new Error(`Demo artifact request failed (HTTP ${response.status}).`);
  let body: string;
  try { body = await response.text(); }
  catch (error) {
    if (signal?.aborted || (error instanceof Error && error.name === 'AbortError')) throw error;
    throw new Error('Could not read the demo artifact response. Retry loading.');
  }
  if (signal?.aborted) { signal.throwIfAborted(); }
  if (!body.trim()) throw new Error('Demo artifact response is empty.');
  let value: unknown;
  try { value = JSON.parse(body); }
  catch { throw new Error('Demo artifact response is not valid JSON.'); }
  return validateDemo(value);
}
