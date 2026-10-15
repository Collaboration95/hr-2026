/**
 * Pure view-models and formatters for the decision-layer UI. Nothing here reads the DOM or React;
 * every figure is derived from a validated `DecisionSummary`, so the same code is unit-tested in node.
 * Erasable TypeScript only (see decision-data.ts).
 */
import { DECISION, SCREEN, percentSmaller } from "./decision-data.ts";
import type { DecisionOutput, DecisionSummary, SpeedRow } from "./decision-data.ts";

// ---------- formatting ----------
export const fmtInt = (n: number): string => n.toLocaleString("en-US");
/** Decimal units (1 KB = 1,000 B) so "6,142 B" reads as "6.1 KB" and "623,237 B" as "623 KB". */
export function fmtSize(bytes: number): string {
  if (bytes >= 1e6) return `${(bytes / 1e6).toFixed(1)} MB`;
  if (bytes >= 1e3) {
    const kb = bytes / 1e3;
    return `${kb >= 100 ? Math.round(kb).toLocaleString("en-US") : kb.toFixed(1)} KB`;
  }
  return `${bytes} B`;
}
export const fmtPct = (p: number, digits = 1): string => `${p.toFixed(digits)}%`;
/** Speed-up factor: 529×, 26×, 2.2×, 0.79×. */
export function fmtX(x: number): string {
  if (x >= 100) return `${Math.round(x).toLocaleString("en-US")}×`;
  if (x >= 10) return `${x.toFixed(0)}×`;
  if (x >= 1) return `${x.toFixed(1)}×`;
  return `${x.toFixed(2)}×`;
}
/** Three significant figures without exponents: 117, 1.48, 0.0566, 0.00279. */
export function fmtSig(n: number, digits = 3): string {
  if (n >= 1000) return Math.round(n).toLocaleString("en-US");
  return Number(n.toPrecision(digits)).toLocaleString("en-US", { maximumFractionDigits: 8 });
}

// ---------- proof headline ----------
export function heroModel(s: DecisionSummary) {
  const level = s.storage.levels[DECISION];
  const vs = level.vs_baselines.original_all_layers;
  const f = s.fidelity;
  const plotsTotal = Object.keys(s.plots).length;
  const mismatches = f.cell_mismatches;
  const byPath = (path: string): SpeedRow | null => s.speed.find((r) => r.path === path) ?? null;
  const exact =
    mismatches === 0 &&
    f.plots_equal === plotsTotal &&
    f.fuzz_polygons_equal === f.fuzz_polygons_compared &&
    f.v1_hansen_counts_equal;
  return {
    storage: { percent: vs.percent_smaller, ratio: vs.ratio, decisionBytes: level.file_bytes, originalBytes: vs.baseline_bytes },
    same: {
      cells: f.cells_compared,
      equalCells: mismatches === null ? null : f.cells_compared - mismatches,
      mismatches,
      plotsEqual: f.plots_equal,
      plotsTotal,
      fuzzEqual: f.fuzz_polygons_equal,
      fuzzCompared: f.fuzz_polygons_compared,
      v1Equal: f.v1_hansen_counts_equal,
      exact,
    },
    speed: { index: byPath("P5d"), table: byPath("P6d"), newPolygon: byPath("P4"), baseline: byPath("P0") },
  };
}

// ---------- the ladder ----------
export type LadderRow = {
  key: "l0" | "l1" | "l2" | "table";
  tag: string | null;
  name: string;
  contract: string | null;
  answers: string;
  keeps: string;
  drops: string[];
  bytes: number;
  bytesNote: string | null;
  percent: number;
  ratio: number;
  shipped: boolean;
};

const DECISION_ONLY = /^decision level only:\s*/i;

export function ladderRows(s: DecisionSummary): LadderRow[] {
  const original = s.storage.baselines.original_all_layers;
  const shared = s.dropped.filter((d) => !DECISION_ONLY.test(d));
  const decisionOnly = s.dropped.filter((d) => DECISION_ONLY.test(d)).map((d) => d.replace(DECISION_ONLY, ""));
  const size = (bytes: number) => ({ bytes, percent: percentSmaller(bytes, original), ratio: original / bytes });
  const rows: LadderRow[] = [
    {
      key: "l0", tag: "L0", name: "Lossless archive (v1)", contract: null,
      answers: "Every v1 question, audits and rule changes.",
      keeps: "Every pixel of the three Hansen bands, losslessly.",
      drops: ["Nothing"],
      bytesNote: null, shipped: false,
      ...size(s.storage.baselines.retained_lossless_l0),
    },
    {
      key: "l1", tag: "L1", name: "Screening layer", contract: SCREEN,
      answers: s.contracts[SCREEN],
      keeps: "Land, water and unknown; JRC 2020 forest at each Hansen cell centre; Hansen loss year 2021–2025 on all land.",
      drops: shared,
      bytesNote: null, shipped: true,
      ...size(s.storage.levels[SCREEN].file_bytes),
    },
    {
      key: "l2", tag: "L2", name: "Decision layer", contract: DECISION,
      answers: s.contracts[DECISION],
      keeps: "Land, water and unknown; forest at the cut-off; loss year 2021–2025 on land that was forest in 2020.",
      drops: [...shared, ...decisionOnly],
      bytesNote: null, shipped: true,
      ...size(s.storage.levels[DECISION].file_bytes),
    },
  ];
  const table = s.speed.find((r) => r.path === "P6d");
  if (table) {
    rows.push({
      key: "table", tag: null, name: "Registered-plot table", contract: null,
      answers: "Both contracts, for registered plots only. New polygons use L1 or L2.",
      keeps: "Precomputed outputs per registered plot, keyed by plot ID, geometry hash and layer hash.",
      drops: ["Any polygon that is not a registered plot"],
      bytesNote: `read by the lookup · ${fmtInt(Object.keys(s.plots).length)} plots, both contracts`,
      shipped: false,
      ...size(table.bytes_read),
    });
  }
  return rows;
}

// ---------- standard-format control and scale ----------
export function controlRows(s: DecisionSummary) {
  const original = s.storage.baselines.original_all_layers;
  return ([[DECISION, "L2 decision layer"], [SCREEN, "L1 screening layer"]] as const).map(([contract, name]) => {
    const l = s.storage.levels[contract];
    return {
      contract,
      name,
      ours: l.file_bytes,
      control: l.best_standard_control_bytes,
      controlName: l.best_standard_control,
      oursPercent: percentSmaller(l.file_bytes, original),
      controlPercent: percentSmaller(l.best_standard_control_bytes, original),
      oursIsSmaller: l.file_bytes < l.best_standard_control_bytes,
    };
  });
}

export function scaleModel(s: DecisionSummary) {
  const t = s.tile_scale;
  return {
    tile: t.tile,
    original: t.original_files_bytes,
    screen: t.screen_bytes,
    decision: t.decision_bytes,
    yardstick: t.lossless_zstd19_yardstick_bytes,
    screenPercent: percentSmaller(t.screen_bytes, t.original_files_bytes),
    decisionPercent: percentSmaller(t.decision_bytes, t.original_files_bytes),
    screenVsYardstick: percentSmaller(t.screen_bytes, t.lossless_zstd19_yardstick_bytes),
    decisionVsYardstick: percentSmaller(t.decision_bytes, t.lossless_zstd19_yardstick_bytes),
  };
}

export const isBaselineRow = (r: SpeedRow): boolean =>
  r.speedup_vs_v1.hot === 1 && r.speedup_vs_v1.process_cold === 1 && r.speedup_vs_v1.end_to_end === 1;

// ---------- the map panel ----------
export type ForestFact =
  | { kind: "count"; count: number; landCells: number; nonforest: number; unknown: number }
  | { kind: "none"; landCells: number }
  | { kind: "unknown"; reason: string };
export type DeforestFact =
  | { kind: "count"; count: number; years: [string, number][] }
  | { kind: "none" }
  | { kind: "unknown"; reason: string };

/** Forest at the 31 Dec 2020 cut-off. Known zero is "none"; anything that could hide forest is "unknown". */
export function forestFact(o: DecisionOutput): ForestFact {
  const { cell_counts: c, present } = o.forest_2020;
  if (!c) return { kind: "unknown", reason: "no analysed land cells in this plot" };
  if (present === true) return { kind: "count", count: c.forest, landCells: o.valid_land_cell_count, nonforest: c.nonforest, unknown: c.unknown };
  if (present === false) return { kind: "none", landCells: o.valid_land_cell_count };
  return { kind: "unknown", reason: `no forest seen; ${(o.unknown_cell_count + c.unknown).toLocaleString("en-US")} cells unknown` };
}

/** Mapped loss on land that was forest at the cut-off, by year. Never reports a zero it cannot support. */
export function deforestFact(o: DecisionOutput): DeforestFact {
  const d = o.deforestation_after_2020;
  if (d.cell_count === null || d.yearly_cell_counts === null) return { kind: "unknown", reason: "no analysed land cells in this plot" };
  if (d.present === true) {
    const years = Object.entries(d.yearly_cell_counts).filter(([, n]) => n > 0).sort(([a], [b]) => a.localeCompare(b));
    return { kind: "count", count: d.cell_count, years };
  }
  if (d.present === false) return { kind: "none" };
  return { kind: "unknown", reason: "none seen; unknown cells remain" };
}

/** "in 2022" for one year, "2022: 2 · 2024: 3" for several. */
export function yearsText(years: [string, number][]): string {
  if (years.length === 1) return `in ${years[0][0]}`;
  return years.map(([y, n]) => `${y}: ${n.toLocaleString("en-US")}`).join(" · ");
}

/** One-line observational reading, used for accessible names and tests. */
export function describeFacts(o: DecisionOutput): { forest: string; deforestation: string } {
  const f = forestFact(o);
  const d = deforestFact(o);
  return {
    forest: f.kind === "count" ? `${f.count.toLocaleString("en-US")} cells` : f.kind === "none" ? "none" : "unknown",
    deforestation:
      d.kind === "count" ? `${d.count.toLocaleString("en-US")} cells ${yearsText(d.years)}` : d.kind === "none" ? "none mapped" : "unknown",
  };
}
