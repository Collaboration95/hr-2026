import type { Demo, Geometry } from './types';

type Obj = Record<string, unknown>;
export type JrcCell = { row: number; col: number; value: 0 | 1 | null; valid: boolean };
export type JrcResult = {
  selected_cell_count: number;
  in_coverage_cell_count: number;
  out_of_coverage_cell_count: number;
  valid_cell_count: number;
  unknown_cell_count: number;
  class_counts: { '0': number; '1': number } | null;
  mapped_forest_present: boolean | null;
  support: 'complete' | 'partial' | 'none' | 'unavailable';
  unknown_reasons: string[];
  [key: string]: unknown;
};
export type JrcGrid = {
  shape: [number, number];
  transform: [number, number, number, number, number, number];
  crs: 'EPSG:4326';
  query_grid: string;
};
export type JrcPlot = {
  plot_id: string;
  geometry: Geometry;
  geometry_sha256: string;
  source_result: JrcResult;
  compact_result: JrcResult;
  comparison: { equal: boolean; independent_oracle_equal: boolean; mismatch_fields: string[] };
  receipt: Obj & { geometry_sha256: string; receipt_sha256: string };
  evidence: { index_origin: string; cells: JrcCell[] };
};
export type JrcArtifact = {
  schema_version: 'plotline.jrc-baseline.v1';
  query_version: 'jrc2020-centers.v1';
  dataset: Obj & JrcGrid & {
    product: 'JRC Global Forest Cover Map 2020'; version: 'v4'; reference_year: 2020;
    classes: { '0': 'Non-forest'; '1': 'Forest' }; zero_is_valid_class: true;
    citation: string; limitations: string[]; xml_observations: Obj;
  };
  native_grid: JrcGrid;
  store: Obj;
  full_chip: Obj;
  plots: JrcPlot[];
  summary: Obj;
  benchmark: Obj | null;
  limitations: string[];
  content_sha256: string;
};

// Bounded to this acquired chip. A new source/grid requires a new reviewed contract.
const shape = [1809, 3695];
const transform = [1 / 12000, 0, 98.77241666666667, 0, -1 / 12000, 8.581916666666666];
const queryGrid = 'acquired JRC chip affine lattice; zero-based chip row/col; original centers before any window read';
const indexOrigin = 'zero-based JRC chip row/col';
const product = 'JRC Global Forest Cover Map 2020';
// Declared acquisition identities for this bounded companion. Comparing these
// strings prevents source substitution; it does not verify files or authenticity.
const sourceIdentity = {
  source_sha256: 'fbae885505a5ee7a481775401f27c23b1b8ef1e5451b69156a70c04aa42f38d7',
  chip_sha256: '3019c19bca064ac8f31747da856f40ce04146da6759c2f36dc30d0ff2e07e7c5',
  provenance_sha256: 'c99d7780af8778be4c1ad7123c31fbee3b09401d3ff4d48e2eeece15ea434f7b',
  qml_sha256: 'd089a9d21a10537a13c77f206fd8ac844d364800b48580361893179d902080b0',
  xml_sha256: 'cdccfb393e306cf6775a2041263c09885a275a67b8098acde6536f06358a66b9',
};
const reasonsAllowed = ['no_selected_cells', 'out_of_coverage', 'band_mask_invalid', 'no_valid_cells', 'missing_band'];
const own = (o: Obj, k: string) => Object.hasOwn(o, k);
function need(condition: unknown, path: string, detail: string): asserts condition {
  if (!condition) throw new Error(`Invalid JRC companion at ${path}: ${detail}.`);
}
function object(v: unknown, path: string): Obj {
  need(v !== null && typeof v === 'object' && !Array.isArray(v), path, 'expected a JSON object');
  need(Object.getPrototypeOf(v) === Object.prototype || Object.getPrototypeOf(v) === null, path, 'expected a plain JSON object');
  return v as Obj;
}
function array(v: unknown, path: string): unknown[] { need(Array.isArray(v), path, 'expected an array'); return v; }
function text(v: unknown, path: string): string { need(typeof v === 'string' && v.trim().length > 0, path, 'expected nonempty text'); return v; }
function integer(v: unknown, path: string, min = 0): number {
  need(typeof v === 'number' && Number.isSafeInteger(v) && v >= min, path, `expected a safe integer >= ${min}`); return v;
}
function strings(v: unknown, path: string): string[] { return array(v, path).map((x, i) => text(x, `${path}[${i}]`)); }
function digest(v: unknown, path: string) { need(typeof v === 'string' && /^[a-f0-9]{64}$/.test(v), path, 'expected a lowercase SHA-256 declaration'); }
function keys(o: Obj, expected: string[], path: string) {
  need(Object.keys(o).length === expected.length && expected.every(k => own(o, k)), path, `expected keys ${expected.join(', ')}`);
}

/** JSON structure equality includes extensions and ignores object key order.
 * It checks internal claims only; no digest authenticates source pixels here. */
export function jrcStructuralEqual(a: unknown, b: unknown, depth = 0): boolean {
  if (depth > 64) return false;
  if (a === b) return true;
  if (Array.isArray(a) && Array.isArray(b)) {
    if (a.length !== b.length) return false;
    for (let i = 0; i < a.length; i++) if (!Object.hasOwn(a, i) || !Object.hasOwn(b, i) || !jrcStructuralEqual(a[i], b[i], depth + 1)) return false;
    return true;
  }
  if (a && b && typeof a === 'object' && typeof b === 'object' && !Array.isArray(a) && !Array.isArray(b)) {
    const left = a as Obj, right = b as Obj, names = Object.keys(left);
    return names.length === Object.keys(right).length && names.every(k => own(right, k) && jrcStructuralEqual(left[k], right[k], depth + 1));
  }
  return false;
}
// Bound untrusted extension trees before comparing/rendering them.
function jsonTree(v: unknown, path: string, depth = 0, budget = { left: 300_000 }): void {
  need(depth <= 64 && --budget.left >= 0, path, 'JSON tree exceeds supported bounds');
  if (v === null || typeof v === 'string' || typeof v === 'boolean') return;
  if (typeof v === 'number') { need(Number.isFinite(v), path, 'expected finite JSON number'); return; }
  if (Array.isArray(v)) {
    need(v.length <= budget.left, path, 'array exceeds supported bounds');
    for (const [i, x] of v.entries()) jsonTree(x, `${path}[${i}]`, depth + 1, budget);
    return;
  }
  const o = object(v, path);
  Object.entries(o).forEach(([k, x]) => jsonTree(x, `${path}.${k}`, depth + 1, budget));
}
export function jrcInCoverage(cell: JrcCell, grid: JrcGrid): boolean {
  return cell.row >= 0 && cell.col >= 0 && cell.row < grid.shape[0] && cell.col < grid.shape[1];
}
/** Original affine coordinates, including cells beyond chip coverage. */
export function jrcCellPoint(grid: JrcGrid, col: number, row: number): [number, number] {
  const [a, b, c, d, e, f] = grid.transform;
  return [a * col + b * row + c, d * col + e * row + f];
}
export function jrcComparisonAgrees(plot: JrcPlot): boolean {
  return plot.comparison?.equal === true && plot.comparison?.independent_oracle_equal === true
    && Array.isArray(plot.comparison.mismatch_fields) && plot.comparison.mismatch_fields.length === 0
    && !!plot.source_result && !!plot.compact_result && jrcStructuralEqual(plot.source_result, plot.compact_result);
}

function result(v: unknown, path: string): JrcResult {
  const r = object(v, path);
  const selected = integer(r.selected_cell_count, `${path}.selected_cell_count`);
  need(selected <= 100_000, path, 'selected-cell work limit exceeded');
  const inside = integer(r.in_coverage_cell_count, `${path}.in_coverage_cell_count`);
  const outside = integer(r.out_of_coverage_cell_count, `${path}.out_of_coverage_cell_count`);
  const valid = integer(r.valid_cell_count, `${path}.valid_cell_count`);
  const unknown = integer(r.unknown_cell_count, `${path}.unknown_cell_count`);
  need(inside + outside === selected && valid <= inside && valid + unknown === selected, path, 'coverage/valid/unknown accounting must balance');
  const reasons = strings(r.unknown_reasons, `${path}.unknown_reasons`);
  need(new Set(reasons).size === reasons.length && reasons.every(x => reasonsAllowed.includes(x)), path, 'unknown reasons must be unique contract reasons');
  const missing = reasons.includes('missing_band');
  need((selected === 0) === reasons.includes('no_selected_cells'), path, 'no_selected_cells must match support');
  need((outside > 0) === reasons.includes('out_of_coverage'), path, 'out_of_coverage must match support');
  need((selected > 0 && valid === 0) === reasons.includes('no_valid_cells'), path, 'no_valid_cells must match support');
  need((inside > valid) === reasons.includes('band_mask_invalid'), path, 'band_mask_invalid must match covered unknown cells');
  if (missing) need(valid === 0 && unknown === selected, path, 'missing band globally suppresses analytics');
  const support = missing ? 'unavailable' : valid === 0 ? 'none' : unknown > 0 ? 'partial' : 'complete';
  need(r.support === support, `${path}.support`, `expected ${support}`);
  let forest = 0;
  if (valid === 0) need(r.class_counts === null, `${path}.class_counts`, 'no analytical support requires explicit null');
  else {
    const counts = object(r.class_counts, `${path}.class_counts`); keys(counts, ['0', '1'], `${path}.class_counts`);
    const nonforest = integer(counts['0'], `${path}.class_counts.0`); forest = integer(counts['1'], `${path}.class_counts.1`);
    need(nonforest + forest === valid, path, 'class counts must sum to valid cells');
  }
  const flag = valid === 0 ? null : forest > 0 ? true : unknown === 0 ? false : null;
  need(r.mapped_forest_present === flag, `${path}.mapped_forest_present`, 'positive needs a witness; absence needs complete known support; otherwise explicit null');
  return r as JrcResult;
}

function fileList(v: unknown, path: string): Obj[] {
  const files = array(v, path); need(files.length > 0, path, 'expected declared files');
  const paths = new Set<string>();
  return files.map((f, i) => {
    const p = `${path}[${i}]`, o = object(f, p), name = text(o.path, `${p}.path`);
    need(!paths.has(name), p, 'duplicate file identity'); paths.add(name);
    digest(o.sha256, `${p}.sha256`); integer(o.bytes, `${p}.bytes`); return o;
  });
}

/** UI consistency/association gate, not engine acceptance or source verification.
 * Returns the frozen input unchanged. Main must already pass validateDemo. */
export function validateJrc(value: unknown, main: Demo): JrcArtifact {
  jsonTree(value, 'artifact');
  const a = object(value, 'artifact');
  need(a.schema_version === 'plotline.jrc-baseline.v1', 'schema_version', 'expected plotline.jrc-baseline.v1');
  need(a.query_version === 'jrc2020-centers.v1', 'query_version', 'expected jrc2020-centers.v1');
  need(main.schema_version === 'plotline.demo.v1' && main.query_version === 'hansen-centers.v1', 'main', 'requires the accepted Hansen envelope');
  const dataset = object(a.dataset, 'dataset'), grid = object(a.native_grid, 'native_grid');
  need(dataset.product === product && dataset.version === 'v4' && dataset.reference_year === 2020, 'dataset', 'expected JRC product, v4 and reference 2020');
  need(jrcStructuralEqual(dataset.classes, { '0': 'Non-forest', '1': 'Forest' }) && dataset.zero_is_valid_class === true && dataset.nodata === null, 'dataset.classes', '0 and 1 are known classes independent of style alpha');
  for (const [key, expected] of Object.entries({ shape, transform, crs: 'EPSG:4326', query_grid: queryGrid })) {
    need(jrcStructuralEqual(grid[key], expected) && jrcStructuralEqual(dataset[key], expected), `native_grid.${key}`, 'must match the separate acquired JRC chip');
  }
  const styles = object(dataset.class_styles, 'dataset.class_styles');
  for (const k of ['0', '1']) need(object(styles[k], `dataset.class_styles.${k}`).label === (k === '0' ? 'Non-forest' : 'Forest'), 'dataset.class_styles', 'labels must match raw classes');
  text(dataset.citation, 'dataset.citation'); strings(dataset.limitations, 'dataset.limitations'); strings(a.limitations, 'limitations');
  object(dataset.xml_observations, 'dataset.xml_observations');
  for (const key of ['chip_sha256', 'provenance_sha256', 'qml_sha256', 'xml_sha256']) digest(dataset[key], `dataset.${key}`);
  const source = object(dataset.source, 'dataset.source'); digest(source.sha256, 'dataset.source.sha256');
  need(source.sha256 === sourceIdentity.source_sha256, 'dataset.source.sha256', 'must match the declared acquired source identity');
  for (const key of ['chip_sha256', 'provenance_sha256', 'qml_sha256', 'xml_sha256'] as const) {
    need(dataset[key] === sourceIdentity[key], `dataset.${key}`, 'must match the declared acquisition identity');
  }
  text(source.path, 'dataset.source.path'); text(source.url, 'dataset.source.url'); integer(source.bytes, 'dataset.source.bytes');
  const inputs = fileList(dataset.required_inputs, 'dataset.required_inputs');
  need(inputs.length === 4 && ['chip_sha256', 'provenance_sha256', 'qml_sha256', 'xml_sha256'].every(k => inputs.filter(f => f.sha256 === dataset[k]).length === 1), 'dataset.required_inputs', 'chip/provenance/QML/XML identities must agree');
  const labels = object(dataset.class_label_source, 'dataset.class_label_source');
  need(labels.sha256 === dataset.qml_sha256 && inputs.some(f => f.path === labels.path && f.sha256 === labels.sha256 && f.bytes === labels.bytes), 'dataset.class_label_source', 'QML source identity must agree');
  const store = object(a.store, 'store'), files = fileList(store.files, 'store.files');
  text(store.candidate, 'store.candidate'); text(store.path, 'store.path');
  const payload = integer(store.payload_bytes, 'store.payload_bytes'), metadata = integer(store.metadata_index_bytes, 'store.metadata_index_bytes');
  need(integer(store.total_bytes, 'store.total_bytes') === payload + metadata && files.reduce((n, f) => n + (f.bytes as number), 0) === store.total_bytes, 'store.total_bytes', 'declared bytes must balance');
  const full = object(a.full_chip, 'full_chip');
  need(full.pixel_count === shape[0] * shape[1], 'full_chip.pixel_count', 'must match the JRC grid');
  for (const key of ['raw_values_equal', 'mask_equal', 'metadata_equal']) need(typeof full[key] === 'boolean', `full_chip.${key}`, 'expected a declared boolean');
  for (const key of ['raw_sha256', 'mask_sha256']) digest(full[key], `full_chip.${key}`);
  digest(a.content_sha256, 'content_sha256');
  const benchmark = a.benchmark === null ? null : object(a.benchmark, 'benchmark');
  let run: unknown = null;
  if (benchmark) {
    need(benchmark.schema_version === 'plotline.jrc-benchmark.v1', 'benchmark.schema_version', 'expected separate JRC benchmark');
    run = object(benchmark.archive, 'benchmark.archive').run_id; text(run, 'benchmark.archive.run_id');
  }
  need(main.plots.length === 17 && new Set(main.plots.map(p => p.plot_id)).size === 17, 'main.plots', 'expected 17 unique accepted plots');
  const plots = array(a.plots, 'plots'), seen = new Set<string>();
  need(plots.length === 17, 'plots', 'expected 17 matching plots');
  let datasetHash: unknown;
  for (const [i, v] of plots.entries()) {
    const path = `plots[${i}]`, p = object(v, path), id = text(p.plot_id, `${path}.plot_id`);
    need(!seen.has(id), path, 'duplicate plot ID'); seen.add(id);
    const accepted = main.plots.find(p => p.plot_id === id);
    need(accepted && jrcStructuralEqual(p.geometry, accepted.geometry), `${path}.geometry`, 'must exactly match the accepted plot geometry');
    const mainReceipt = object(accepted.receipt, `${path}.main.receipt`);
    digest(mainReceipt.geometry_sha256, `${path}.main.geometry_sha256`);
    need(p.geometry_sha256 === mainReceipt.geometry_sha256, `${path}.geometry_sha256`, 'must match the accepted geometry digest');
    const src = result(p.source_result, `${path}.source_result`), compact = result(p.compact_result, `${path}.compact_result`);
    const c = object(p.comparison, `${path}.comparison`), actual = jrcStructuralEqual(src, compact);
    need(typeof c.equal === 'boolean' && c.equal === actual, `${path}.comparison.equal`, 'declared equality contradicts full result structure');
    need(typeof c.independent_oracle_equal === 'boolean', `${path}.comparison.independent_oracle_equal`, 'expected declared oracle boolean');
    const mismatches = strings(c.mismatch_fields, `${path}.comparison.mismatch_fields`);
    const differingKeys = [...new Set([...Object.keys(src), ...Object.keys(compact)])].filter(k => !own(src, k) || !own(compact, k) || !jrcStructuralEqual(src[k], compact[k])).sort();
    need(jrcStructuralEqual([...mismatches].sort(), differingKeys), `${path}.comparison.mismatch_fields`, 'must list actual differing result fields');
    const evidence = object(p.evidence, `${path}.evidence`);
    need(evidence.index_origin === indexOrigin, `${path}.evidence.index_origin`, 'expected JRC chip indices');
    const cells = array(evidence.cells, `${path}.evidence.cells`);
    need(cells.length === src.selected_cell_count, `${path}.evidence.cells`, 'must contain every selected center');
    const cellIds = new Set<string>(); let covered = 0, valid = 0; const counts = { '0': 0, '1': 0 };
    for (const [j, v] of cells.entries()) {
      const cp = `${path}.evidence.cells[${j}]`, cell = object(v, cp);
      const row = integer(cell.row, `${cp}.row`, Number.MIN_SAFE_INTEGER), col = integer(cell.col, `${cp}.col`, Number.MIN_SAFE_INTEGER);
      const key = `${row}:${col}`; need(!cellIds.has(key), cp, 'duplicate native cell'); cellIds.add(key);
      need(typeof cell.valid === 'boolean' && (cell.value === 0 || cell.value === 1 || cell.value === null), cp, 'expected explicit validity and raw 0/1/null');
      const inside = row >= 0 && col >= 0 && row < shape[0] && col < shape[1];
      if (!inside) need(cell.value === null && cell.valid === false, cp, 'outside cells require null and invalid');
      else { covered++; need(cell.value === 0 || cell.value === 1, cp, 'covered raw values must preserve 0/1 even under invalid masks'); }
      if (cell.valid) { need(inside && cell.value !== null, cp, 'valid cells require covered raw class'); valid++; counts[String(cell.value) as '0' | '1']++; }
    }
    const missing = src.unknown_reasons.includes('missing_band');
    need(covered === src.in_coverage_cell_count && src.valid_cell_count === (missing ? 0 : valid)
      && src.unknown_cell_count === (missing ? cells.length : cells.length - valid), `${path}.evidence`, 'native evidence must match source support');
    need(jrcStructuralEqual(src.class_counts, missing || valid === 0 ? null : counts), `${path}.evidence`, 'valid native class counts must match analytics');
    const receipt = object(p.receipt, `${path}.receipt`);
    for (const key of ['receipt_sha256', 'geometry_sha256', 'dataset_sha256', 'source_result_sha256', 'compact_result_sha256', 'evidence_sha256']) digest(receipt[key], `${path}.receipt.${key}`);
    if (i === 0) datasetHash = receipt.dataset_sha256;
    need(receipt.dataset_sha256 === datasetHash, `${path}.receipt.dataset_sha256`, 'all receipts must declare the same source identity');
    need(receipt.query_version === a.query_version && receipt.query_grid === queryGrid && receipt.product === product && receipt.version === 'v4' && receipt.reference_year === 2020, `${path}.receipt`, 'source/query/version/reference identity must match');
    need(receipt.geometry_sha256 === p.geometry_sha256 && jrcStructuralEqual(receipt.store, store) && jrcStructuralEqual(receipt.full_chip, full) && receipt.benchmark_run === run, `${path}.receipt`, 'geometry/store/full-chip/run bindings must match');
    need((receipt.source_result_sha256 === receipt.compact_result_sha256) === actual, `${path}.receipt`, 'declared result digests contradict actual equality');
  }
  const summary = object(a.summary, 'summary'), typed = plots as JrcPlot[];
  const expected = {
    plot_count: 17, exact_match_count: typed.filter(p => p.comparison.equal).length,
    independent_match_count: typed.filter(p => p.comparison.independent_oracle_equal).length,
    selected_cell_count_sum: typed.reduce((n, p) => n + p.source_result.selected_cell_count, 0),
    class_counts_sum: { '0': typed.reduce((n, p) => n + (p.source_result.class_counts?.['0'] ?? 0), 0), '1': typed.reduce((n, p) => n + (p.source_result.class_counts?.['1'] ?? 0), 0) },
    mapped_forest_plot_counts: { true: typed.filter(p => p.source_result.mapped_forest_present === true).length, false: typed.filter(p => p.source_result.mapped_forest_present === false).length, unknown: typed.filter(p => p.source_result.mapped_forest_present === null).length },
  };
  for (const [k, v] of Object.entries(expected)) need(jrcStructuralEqual(summary[k], v), `summary.${k}`, 'must match the plot results');
  text(summary.count_note, 'summary.count_note');
  return value as JrcArtifact;
}

/** Optional same-origin loader. Lead owns mounting and engine-acceptance gating. */
export async function loadJrc(main: Demo, signal?: AbortSignal): Promise<JrcArtifact> {
  signal?.throwIfAborted();
  let response: Response;
  try { response = await fetch('/data/jrc-baseline-v1.json', { cache: 'no-store', signal }); }
  catch (error) { if (signal?.aborted) throw signal.reason; throw new Error('JRC baseline unavailable. Check the local server and accepted companion asset.', { cause: error }); }
  signal?.throwIfAborted();
  if (!response.ok) throw new Error(`JRC baseline unavailable (HTTP ${response.status}). The optional accepted companion asset is required.`);
  let body: string;
  try { body = await response.text(); }
  catch (error) { if (signal?.aborted) throw signal.reason; throw new Error('Could not read the JRC companion response.', { cause: error }); }
  signal?.throwIfAborted();
  if (!body.trim()) throw new Error('JRC companion response is empty.');
  let value: unknown;
  try { value = JSON.parse(body); } catch { throw new Error('JRC companion response is not valid JSON. Check the accepted asset; an HTML fallback is unavailable data.'); }
  return validateJrc(value, main);
}
