/**
 * Optional decision-layer summary (`plotline.decision-summary.v1`, written by
 * engine/decision_export.py and copied to /data/decision-v1.json by sync-data).
 *
 * Everything the Proof view and the map panel show is read from this file; no
 * number is hard-coded. Validation is strict about the fields the UI uses and
 * about the internal tri-state/count consistency of each plot output. Anything
 * malformed rejects the whole file, which the caller treats as "unavailable":
 * the rest of the app never depends on it.
 *
 * This module must stay erasable TypeScript with type-only imports so the node
 * test runner can import it directly.
 */

export const DECISION_SCHEMA = "plotline.decision-summary.v1";
export const DECISION_URL = "/data/decision-v1.json";
export const SCREEN = "eudr-screen.v1";
export const DECISION = "eudr-decision.v1";

export type Contract = typeof SCREEN | typeof DECISION;
export type Tri = boolean | null;

export type Baselines = {
  original_all_layers: number;
  original_contract_inputs: number;
  retained_lossless_l0: number;
};
export type VsBaseline = { baseline_bytes: number; percent_smaller: number; ratio: number };
export type LevelStorage = {
  file_bytes: number;
  encoding: string;
  best_standard_control: string;
  best_standard_control_bytes: number;
  vs_baselines: Record<keyof Baselines, VsBaseline>;
};
export type SpeedRow = {
  path: string;
  label: string;
  registered_plots_only: boolean;
  hot_17_plots_ms: number;
  hot_per_plot_us: number;
  process_cold_ms: number;
  end_to_end_ms: number;
  peak_rss_mb: number;
  bytes_read: number;
  speedup_vs_v1: { hot: number; process_cold: number; end_to_end: number };
};
export type LayerRow = { plane: string; zstd19_bytes: number; needed_for: string[]; verdict: string };
export type ForestCounts = { forest: number; nonforest: number; unknown: number };
export type DecisionOutput = {
  contract: string;
  selected_cell_count: number;
  out_of_coverage_cell_count: number;
  valid_land_cell_count: number;
  water_cell_count: number;
  unknown_cell_count: number;
  support: "complete" | "partial" | "none";
  forest_2020: { cell_counts: ForestCounts | null; present: Tri };
  deforestation_after_2020: {
    yearly_cell_counts: Record<string, number> | null;
    cell_count: number | null;
    present: Tri;
  };
};
export type DecisionPlot = { geometry_sha256: string; outputs: Partial<Record<Contract, DecisionOutput>> };
export type TileScale = {
  tile: string;
  original_files_bytes: number;
  lossless_zstd19_yardstick_bytes: number;
  screen_bytes: number;
  decision_bytes: number;
};
export type Fidelity = {
  cells_compared: number;
  cell_mismatches: number | null;
  plots_equal: number;
  fuzz_polygons_compared: number;
  fuzz_polygons_equal: number;
  v1_hansen_counts_equal: boolean;
  theorem: string;
};
export type DecisionSummary = {
  schema: typeof DECISION_SCHEMA;
  question: string | null;
  contracts: Record<Contract, string>;
  dropped: string[];
  fidelity: Fidelity;
  storage: { baselines: Baselines; levels: Record<Contract, LevelStorage> };
  speed: SpeedRow[];
  tile_scale: TileScale;
  layer_analysis: LayerRow[];
  limitations: string[];
  evidence: Record<string, string>;
  plots: Record<string, DecisionPlot>;
};

type Obj = Record<string, unknown>;
const BASELINE_KEYS = ["original_all_layers", "original_contract_inputs", "retained_lossless_l0"] as const;
const own = (o: Obj, k: string) => Object.hasOwn(o, k);

function need(condition: unknown, path: string, detail: string): asserts condition {
  if (!condition) throw new Error(`Invalid decision summary at ${path}: ${detail}.`);
}
function obj(v: unknown, path: string): Obj {
  need(v !== null && typeof v === "object" && !Array.isArray(v), path, "expected a JSON object");
  const proto = Object.getPrototypeOf(v);
  need(proto === Object.prototype || proto === null, path, "expected a plain JSON object");
  return v as Obj;
}
function arr(v: unknown, path: string): unknown[] {
  need(Array.isArray(v), path, "expected an array");
  return v;
}
function str(v: unknown, path: string): string {
  need(typeof v === "string" && v.trim().length > 0, path, "expected nonempty text");
  return v;
}
function int(v: unknown, path: string, min = 0): number {
  need(typeof v === "number" && Number.isSafeInteger(v) && v >= min, path, `expected a safe integer >= ${min}`);
  return v;
}
function num(v: unknown, path: string, minExclusive = -1): number {
  need(typeof v === "number" && Number.isFinite(v) && v > minExclusive, path, `expected a finite number > ${minExclusive}`);
  return v;
}
function bool(v: unknown, path: string): boolean {
  need(typeof v === "boolean", path, "expected true or false");
  return v;
}
function tri(v: unknown, path: string): Tri {
  need(v === null || typeof v === "boolean", path, "expected true, false or null");
  return v;
}
function strings(v: unknown, path: string): string[] {
  return arr(v, path).map((x, i) => str(x, `${path}[${i}]`));
}
function sha(v: unknown, path: string): string {
  need(typeof v === "string" && /^[a-f0-9]{64}$/.test(v), path, "expected a lowercase SHA-256 hex digest");
  return v;
}
/** 100 * (1 - bytes / baseline), the same definition the engine uses for `percent_smaller`. */
export const percentSmaller = (bytes: number, baseline: number): number => 100 * (1 - bytes / baseline);

function level(v: unknown, path: string, baselines: Baselines): LevelStorage {
  const o = obj(v, path);
  const fileBytes = int(o.file_bytes, `${path}.file_bytes`, 1);
  const vsRaw = obj(o.vs_baselines, `${path}.vs_baselines`);
  const vs = {} as Record<keyof Baselines, VsBaseline>;
  for (const key of BASELINE_KEYS) {
    const e = obj(vsRaw[key], `${path}.vs_baselines.${key}`);
    const baseline = int(e.baseline_bytes, `${path}.vs_baselines.${key}.baseline_bytes`, 1);
    need(baseline === baselines[key], `${path}.vs_baselines.${key}`, "baseline bytes disagree with storage.baselines");
    const percent = num(e.percent_smaller, `${path}.vs_baselines.${key}.percent_smaller`, -1e9);
    const ratio = num(e.ratio, `${path}.vs_baselines.${key}.ratio`, 0);
    need(Math.abs(percent - percentSmaller(fileBytes, baseline)) < 0.01, `${path}.vs_baselines.${key}`, "percent_smaller disagrees with file_bytes");
    need(Math.abs(ratio - baseline / fileBytes) < 0.01 * Math.max(1, baseline / fileBytes), `${path}.vs_baselines.${key}`, "ratio disagrees with file_bytes");
    vs[key] = { baseline_bytes: baseline, percent_smaller: percent, ratio };
  }
  return {
    file_bytes: fileBytes,
    encoding: str(o.encoding, `${path}.encoding`),
    best_standard_control: str(o.best_standard_control, `${path}.best_standard_control`),
    best_standard_control_bytes: int(o.best_standard_control_bytes, `${path}.best_standard_control_bytes`, 1),
    vs_baselines: vs,
  };
}

function speedRow(v: unknown, path: string): SpeedRow {
  const o = obj(v, path);
  const s = obj(o.speedup_vs_v1, `${path}.speedup_vs_v1`);
  return {
    path: str(o.path, `${path}.path`),
    label: str(o.label, `${path}.label`),
    registered_plots_only: bool(o.registered_plots_only, `${path}.registered_plots_only`),
    hot_17_plots_ms: num(o.hot_17_plots_ms, `${path}.hot_17_plots_ms`, 0),
    hot_per_plot_us: num(o.hot_per_plot_us, `${path}.hot_per_plot_us`, 0),
    process_cold_ms: num(o.process_cold_ms, `${path}.process_cold_ms`, 0),
    end_to_end_ms: num(o.end_to_end_ms, `${path}.end_to_end_ms`, 0),
    peak_rss_mb: num(o.peak_rss_mb, `${path}.peak_rss_mb`, 0),
    bytes_read: int(o.bytes_read, `${path}.bytes_read`, 1),
    speedup_vs_v1: {
      hot: num(s.hot, `${path}.speedup_vs_v1.hot`, 0),
      process_cold: num(s.process_cold, `${path}.speedup_vs_v1.process_cold`, 0),
      end_to_end: num(s.end_to_end, `${path}.speedup_vs_v1.end_to_end`, 0),
    },
  };
}

function output(v: unknown, path: string, contract: Contract): DecisionOutput {
  const o = obj(v, path);
  need(o.contract === contract, `${path}.contract`, `expected ${contract}`);
  const land = int(o.valid_land_cell_count, `${path}.valid_land_cell_count`);
  need(o.support === "complete" || o.support === "partial" || o.support === "none", `${path}.support`, "expected complete, partial or none");

  const f = obj(o.forest_2020, `${path}.forest_2020`);
  const fPresent = tri(f.present, `${path}.forest_2020.present`);
  let forest: ForestCounts | null = null;
  if (f.cell_counts !== null) {
    const c = obj(f.cell_counts, `${path}.forest_2020.cell_counts`);
    forest = {
      forest: int(c.forest, `${path}.forest_2020.cell_counts.forest`),
      nonforest: int(c.nonforest, `${path}.forest_2020.cell_counts.nonforest`),
      unknown: int(c.unknown, `${path}.forest_2020.cell_counts.unknown`),
    };
    need(forest.forest + forest.nonforest + forest.unknown === land, `${path}.forest_2020.cell_counts`, "classes do not sum to valid_land_cell_count");
    need(fPresent !== true || forest.forest > 0, `${path}.forest_2020.present`, "present=true needs forest cells");
    need(fPresent !== false || (forest.forest === 0 && forest.unknown === 0), `${path}.forest_2020.present`, "present=false needs zero forest and zero unknown cells");
  } else {
    need(fPresent === null, `${path}.forest_2020.present`, "no counts means present must be null");
  }

  const d = obj(o.deforestation_after_2020, `${path}.deforestation_after_2020`);
  const dPresent = tri(d.present, `${path}.deforestation_after_2020.present`);
  let yearly: Record<string, number> | null = null;
  let total: number | null = null;
  if (d.yearly_cell_counts !== null || d.cell_count !== null) {
    const y = obj(d.yearly_cell_counts, `${path}.deforestation_after_2020.yearly_cell_counts`);
    yearly = {};
    let sum = 0;
    for (const [year, count] of Object.entries(y)) {
      need(/^\d{4}$/.test(year), `${path}.deforestation_after_2020.yearly_cell_counts`, "expected four-digit year keys");
      yearly[year] = int(count, `${path}.deforestation_after_2020.yearly_cell_counts.${year}`);
      sum += yearly[year];
    }
    total = int(d.cell_count, `${path}.deforestation_after_2020.cell_count`);
    need(sum === total, `${path}.deforestation_after_2020`, "yearly counts do not sum to cell_count");
    need(dPresent !== true || total > 0, `${path}.deforestation_after_2020.present`, "present=true needs cells");
    need(dPresent !== false || total === 0, `${path}.deforestation_after_2020.present`, "present=false needs zero cells");
  } else {
    need(dPresent === null, `${path}.deforestation_after_2020.present`, "no counts means present must be null");
  }

  return {
    contract,
    selected_cell_count: int(o.selected_cell_count, `${path}.selected_cell_count`),
    out_of_coverage_cell_count: int(o.out_of_coverage_cell_count, `${path}.out_of_coverage_cell_count`),
    valid_land_cell_count: land,
    water_cell_count: int(o.water_cell_count, `${path}.water_cell_count`),
    unknown_cell_count: int(o.unknown_cell_count, `${path}.unknown_cell_count`),
    support: o.support,
    forest_2020: { cell_counts: forest, present: fPresent },
    deforestation_after_2020: { yearly_cell_counts: yearly, cell_count: total, present: dPresent },
  };
}

/** Throws on anything the UI cannot render safely. Callers treat a throw as "unavailable". */
export function validateDecisionSummary(value: unknown): DecisionSummary {
  const root = obj(value, "$");
  need(root.schema === DECISION_SCHEMA, "$.schema", `expected ${DECISION_SCHEMA}`);

  const contractsRaw = obj(root.contracts, "$.contracts");
  const contracts = {
    [SCREEN]: str(contractsRaw[SCREEN], `$.contracts.${SCREEN}`),
    [DECISION]: str(contractsRaw[DECISION], `$.contracts.${DECISION}`),
  } as Record<Contract, string>;

  const f = obj(root.fidelity, "$.fidelity");
  const mismatches = f.cell_mismatches === null ? null : int(f.cell_mismatches, "$.fidelity.cell_mismatches");
  const fidelity: Fidelity = {
    cells_compared: int(f.cells_compared, "$.fidelity.cells_compared", 1),
    cell_mismatches: mismatches,
    plots_equal: int(f.plots_equal, "$.fidelity.plots_equal"),
    fuzz_polygons_compared: int(f.fuzz_polygons_compared, "$.fidelity.fuzz_polygons_compared"),
    fuzz_polygons_equal: int(f.fuzz_polygons_equal, "$.fidelity.fuzz_polygons_equal"),
    v1_hansen_counts_equal: bool(f.v1_hansen_counts_equal, "$.fidelity.v1_hansen_counts_equal"),
    theorem: str(f.theorem, "$.fidelity.theorem"),
  };
  need(mismatches === null || mismatches <= fidelity.cells_compared, "$.fidelity.cell_mismatches", "more mismatches than cells compared");
  need(fidelity.fuzz_polygons_equal <= fidelity.fuzz_polygons_compared, "$.fidelity.fuzz_polygons_equal", "more equal than compared");

  const st = obj(root.storage, "$.storage");
  const b = obj(st.baselines, "$.storage.baselines");
  const baselines: Baselines = {
    original_all_layers: int(b.original_all_layers, "$.storage.baselines.original_all_layers", 1),
    original_contract_inputs: int(b.original_contract_inputs, "$.storage.baselines.original_contract_inputs", 1),
    retained_lossless_l0: int(b.retained_lossless_l0, "$.storage.baselines.retained_lossless_l0", 1),
  };
  const lv = obj(st.levels, "$.storage.levels");
  const levels = {
    [SCREEN]: level(lv[SCREEN], `$.storage.levels.${SCREEN}`, baselines),
    [DECISION]: level(lv[DECISION], `$.storage.levels.${DECISION}`, baselines),
  } as Record<Contract, LevelStorage>;

  const speed = arr(root.speed, "$.speed").map((r, i) => speedRow(r, `$.speed[${i}]`));
  need(speed.length > 0, "$.speed", "expected at least one row");
  need(new Set(speed.map((r) => r.path)).size === speed.length, "$.speed", "duplicate path");

  const t = obj(root.tile_scale, "$.tile_scale");
  const tile: TileScale = {
    tile: str(t.tile, "$.tile_scale.tile"),
    original_files_bytes: int(t.original_files_bytes, "$.tile_scale.original_files_bytes", 1),
    lossless_zstd19_yardstick_bytes: int(t.lossless_zstd19_yardstick_bytes, "$.tile_scale.lossless_zstd19_yardstick_bytes", 1),
    screen_bytes: int(t.screen_bytes, "$.tile_scale.screen_bytes", 1),
    decision_bytes: int(t.decision_bytes, "$.tile_scale.decision_bytes", 1),
  };

  const layers = arr(root.layer_analysis, "$.layer_analysis").map((r, i): LayerRow => {
    const o = obj(r, `$.layer_analysis[${i}]`);
    return {
      plane: str(o.plane, `$.layer_analysis[${i}].plane`),
      zstd19_bytes: int(o.zstd19_bytes, `$.layer_analysis[${i}].zstd19_bytes`),
      needed_for: strings(o.needed_for, `$.layer_analysis[${i}].needed_for`),
      verdict: str(o.verdict, `$.layer_analysis[${i}].verdict`),
    };
  });
  need(layers.length > 0, "$.layer_analysis", "expected at least one row");

  const evidenceRaw = obj(root.evidence, "$.evidence");
  const evidence: Record<string, string> = {};
  for (const [name, digest] of Object.entries(evidenceRaw)) evidence[name] = sha(digest, `$.evidence.${name}`);

  const plotsRaw = obj(root.plots, "$.plots");
  const plots: Record<string, DecisionPlot> = {};
  for (const [id, entry] of Object.entries(plotsRaw)) {
    need(id.trim().length > 0, "$.plots", "empty plot id");
    const p = obj(entry, `$.plots.${id}`);
    const outs = obj(p.outputs, `$.plots.${id}.outputs`);
    need(own(outs, DECISION), `$.plots.${id}.outputs`, `${DECISION} is required`);
    plots[id] = {
      geometry_sha256: sha(p.geometry_sha256, `$.plots.${id}.geometry_sha256`),
      outputs: {
        [DECISION]: output(outs[DECISION], `$.plots.${id}.outputs.${DECISION}`, DECISION),
        ...(own(outs, SCREEN) ? { [SCREEN]: output(outs[SCREEN], `$.plots.${id}.outputs.${SCREEN}`, SCREEN) } : {}),
      },
    };
  }
  need(Object.keys(plots).length > 0, "$.plots", "expected at least one plot");

  return {
    schema: DECISION_SCHEMA,
    question: typeof root.question === "string" && root.question.trim() ? root.question : null,
    contracts,
    dropped: strings(root.dropped, "$.dropped"),
    fidelity,
    storage: { baselines, levels },
    speed,
    tile_scale: tile,
    layer_analysis: layers,
    limitations: strings(root.limitations, "$.limitations"),
    evidence,
    plots,
  };
}

/**
 * Fetch and validate the optional summary. A missing file, an HTML fallback page, invalid JSON or a
 * failed validation all reject; the caller shows nothing rather than something half-true.
 */
export async function loadDecisionSummary(signal?: AbortSignal): Promise<DecisionSummary> {
  signal?.throwIfAborted();
  let response: Response;
  try {
    response = await fetch(DECISION_URL, { cache: "no-store", signal });
  } catch (error) {
    if (signal?.aborted) throw signal.reason;
    throw new Error("Decision summary unavailable. The optional asset could not be fetched.", { cause: error });
  }
  signal?.throwIfAborted();
  if (!response.ok) throw new Error(`Decision summary unavailable (HTTP ${response.status}).`);
  let body: string;
  try {
    body = await response.text();
  } catch (error) {
    if (signal?.aborted) throw signal.reason;
    throw new Error("Could not read the decision summary response.", { cause: error });
  }
  signal?.throwIfAborted();
  let value: unknown;
  try {
    value = JSON.parse(body);
  } catch {
    throw new Error("Decision summary is not valid JSON (an HTML fallback counts as unavailable).");
  }
  return validateDecisionSummary(value);
}

export type DecisionLookup =
  | { status: "ok"; output: DecisionOutput }
  | { status: "stale" } // the plot geometry differs from the one the summary was computed for
  | { status: "missing" };

/**
 * The decision output for one plot. `geometrySha256` is the plot receipt's geometry digest when known:
 * if both digests exist and differ, the summary describes a different boundary and must not be shown.
 */
export function decisionFor(summary: DecisionSummary, plotId: string, geometrySha256?: string | null): DecisionLookup {
  const entry = Object.hasOwn(summary.plots, plotId) ? summary.plots[plotId] : undefined;
  const output = entry?.outputs[DECISION];
  if (!entry || !output) return { status: "missing" };
  if (geometrySha256 && geometrySha256 !== entry.geometry_sha256) return { status: "stale" };
  return { status: "ok", output };
}
