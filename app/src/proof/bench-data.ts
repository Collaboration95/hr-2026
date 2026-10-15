/**
 * Typed, defensive readers for the frozen benchmark (`data.benchmark`) and the
 * cohort summary (`data.summary`). Both arrive as `unknown`; nothing here
 * coerces a missing value into zero. A reader returns null when a field is
 * absent so the UI can say "Unavailable" instead of inventing a number.
 *
 * One benchmark run only: values from other studies are never merged in.
 */
type Obj = Record<string, unknown>;
const isObj = (v: unknown): v is Obj => v !== null && typeof v === "object" && !Array.isArray(v);
const finite = (v: unknown): number | null => (typeof v === "number" && Number.isFinite(v) ? v : null);
const nonNeg = (v: unknown): number | null => {
  const n = finite(v);
  return n !== null && n >= 0 ? n : null;
};
const bool = (v: unknown): boolean | null => (typeof v === "boolean" ? v : null);
const str = (v: unknown): string | null => (typeof v === "string" && v.trim() ? v : null);

export type TimingStats = {
  median: number | null;
  p95: number | null;
  repetitions: number | null;
  samples: number[];
};

export type Roundtrip = {
  rawBandsEqual: boolean | null;
  bandMasksEqual: boolean | null;
  metadataEqual: boolean | null;
  rawValuesChecked: number | null;
  pixelCount: number | null;
};

export type BenchRow = {
  id: string;
  isBaseline: boolean;
  total: number | null;
  payload: number | null;
  metadataIndex: number | null;
  fullyExact: boolean | null;
  exactCount: number | null;
  plotCount: number | null;
  roundtrip: Roundtrip | null;
  hot: TimingStats | null;
  fresh: TimingStats | null;
  preprocessingMs: number | null;
  chunkSize: number | null;
  codecLevel: number | null;
};

export type BenchView = {
  experimentId: string | null;
  baseline: BenchRow;
  rows: BenchRow[]; // baseline first, then every candidate (losers included)
  retained: BenchRow | null;
  commonInputBytes: number | null;
  /** Sum of loader-required acquisition provenance files the original side already counts. */
  provenanceBytes: number | null;
  queryBatch: number | null;
  bandCount: number | null;
  raw: { method: unknown; environment: unknown; settings: unknown };
};

function stats(v: unknown): TimingStats | null {
  if (!isObj(v)) return null;
  const rawSamples = Array.isArray(v.samples) ? v.samples : [];
  const samples = rawSamples.every((s) => finite(s) !== null) ? (rawSamples as number[]) : [];
  return { median: finite(v.median), p95: finite(v.p95), repetitions: nonNeg(v.repetitions), samples };
}

function readRow(c: unknown, isBaseline: boolean): BenchRow | null {
  if (!isObj(c)) return null;
  const id = str(c.candidate);
  if (!id) return null;
  const storage = isObj(c.storage) ? c.storage : {};
  const queries = isObj(c.queries) ? c.queries : {};
  const hot = isObj(queries.hot) ? stats(queries.hot.wall_ms) : null;
  const fresh = isObj(queries.process_cold) ? stats(queries.process_cold.wall_ms) : null;
  const fidelity = isObj(c.fidelity) ? c.fidelity : null;
  const rt = isObj(c.roundtrip) ? c.roundtrip : null;
  const pre = isObj(c.preprocessing) ? c.preprocessing : {};
  const report = isObj(pre.codec_report) ? pre.codec_report : {};
  const settings = isObj(storage.codec_settings) ? storage.codec_settings : {};
  return {
    id,
    isBaseline,
    total: nonNeg(storage.total_bytes),
    payload: nonNeg(storage.payload_bytes),
    metadataIndex: nonNeg(storage.metadata_index_bytes),
    fullyExact: bool(c.fully_exact),
    exactCount: fidelity ? nonNeg(fidelity.exact_count) : null,
    plotCount: fidelity ? nonNeg(fidelity.plot_count) : null,
    roundtrip: rt
      ? {
          rawBandsEqual: bool(rt.raw_bands_equal),
          bandMasksEqual: bool(rt.all_band_masks_equal),
          metadataEqual: bool(rt.metadata_equal),
          rawValuesChecked: nonNeg(rt.raw_values_checked),
          pixelCount: nonNeg(rt.pixel_count),
        }
      : null,
    hot,
    fresh,
    preprocessingMs: nonNeg(pre.wall_ms),
    chunkSize: nonNeg(report.chunk_size),
    codecLevel: nonNeg(settings.level),
  };
}

export function readBenchmark(value: unknown): BenchView | null {
  if (!isObj(value) || value.schema_version !== "plotline.benchmark.v1") return null;
  const baseline = readRow(value.baseline, true);
  if (!baseline || !Array.isArray(value.candidates)) return null;
  const candidates = value.candidates.map((c) => readRow(c, false)).filter((r): r is BenchRow => r !== null);
  const rows = [baseline, ...candidates];
  const retainedSel = isObj(value.retained_selection) ? str(value.retained_selection.overall_storage_choice) : null;
  const winner = isObj(value.winner) ? str(value.winner.candidate) : null;
  const retainedId = retainedSel ?? str(value.overall_storage_choice) ?? winner;
  const retained = retainedId ? (candidates.find((r) => r.id === retainedId) ?? null) : null;
  const identity = isObj(value.identity) ? value.identity : {};
  const loaderInputs = Array.isArray(identity.source_loader_inputs) ? identity.source_loader_inputs : null;
  const provenanceParts = loaderInputs?.map((f) => (isObj(f) ? nonNeg(f.bytes) : null));
  const provenanceBytes =
    provenanceParts && provenanceParts.length && provenanceParts.every((n) => n !== null)
      ? (provenanceParts as number[]).reduce((a, b) => a + b, 0)
      : null;
  const meta = isObj(identity.source_metadata) ? identity.source_metadata : {};
  const method = isObj(value.method) ? value.method : {};
  return {
    experimentId: str(value.experiment_id),
    baseline,
    rows,
    retained,
    commonInputBytes: nonNeg(value.common_input_bytes),
    provenanceBytes,
    queryBatch: nonNeg(method.query_count_per_batch),
    bandCount: Array.isArray(meta.band_names) ? meta.band_names.length : null,
    raw: { method: value.method, environment: value.environment, settings: identity.settings },
  };
}

export type CohortSummary = { exact: number; total: number };
export function readSummary(value: unknown): CohortSummary | null {
  if (!isObj(value)) return null;
  const exact = nonNeg(value.exact_match_count);
  const total = nonNeg(value.plot_count);
  return exact !== null && total !== null && total > 0 && exact <= total ? { exact, total } : null;
}

/** Percent change of `value` against `base` (negative = smaller), or null. */
export function pctChange(value: number | null, base: number | null): number | null {
  return value !== null && base !== null && base > 0 ? 100 * (value / base - 1) : null;
}
export function ratio(num: number | null, den: number | null): number | null {
  return num !== null && den !== null && den > 0 ? num / den : null;
}

/** Hot-query verdict. Within +/-5% of the baseline median is "no speedup" (noise-level). */
export function hotVerdict(r: number | null): "faster" | "slower" | "none" | null {
  if (r === null) return null;
  if (r >= 1.05) return "faster";
  if (r <= 0.95) return "slower";
  return "none";
}

/**
 * The different "complete review inputs" boundary: both sides add the shared
 * geometry and supplier files, and the compact side also keeps the acquisition
 * provenance the original loader already counts. Only derivable when all three
 * accounting inputs are present; never swap it into the loader-input percentage.
 */
export function reviewInputs(b: BenchView): { original: number; compact: number; pct: number } | null {
  const r = b.retained;
  if (!r || r.total === null || b.baseline.total === null || b.commonInputBytes === null || b.provenanceBytes === null)
    return null;
  const original = b.baseline.total + b.commonInputBytes;
  const compact = r.total + b.commonInputBytes + b.provenanceBytes;
  return { original, compact, pct: 100 * (compact / original - 1) };
}

// ---------- formatting ----------
export const fmtInt = (n: number | null | undefined): string => (n == null ? "Unavailable" : n.toLocaleString("en-US"));
export const fmtFixed = (n: number | null | undefined, d = 2): string =>
  n == null || !Number.isFinite(n)
    ? "Unavailable"
    : n.toLocaleString("en-US", { minimumFractionDigits: d, maximumFractionDigits: d });
export const fmtKiB = (n: number | null | undefined): string => (n == null ? "Unavailable" : `${fmtFixed(n / 1024, 1)} KiB`);
export const fmtBytes = (n: number | null | undefined): string => (n == null ? "Unavailable" : `${fmtInt(n)} B`);
/** Signed percent with a true minus sign. */
export function fmtPct(p: number | null, d = 2): string {
  if (p === null) return "Unavailable";
  const s = Math.abs(p).toLocaleString("en-US", { minimumFractionDigits: d, maximumFractionDigits: d });
  return `${p < 0 ? "−" : p > 0 ? "+" : ""}${s}%`;
}

const CANDIDATE_NAMES: Record<string, string> = {
  source_geotiff: "Original GeoTIFF",
  separate_zstd: "Separate bands",
  separate_zstd_l9: "Separate bands",
  separate_zstd_l19: "Separate bands",
  packed14_zstd: "14-bit packed",
  uint16_zstd: "16-bit words",
  bitplane_zstd: "Bitplanes",
};
/** Human label from the candidate id plus its measured codec level when present. */
export function rowLabel(r: BenchRow): string {
  if (r.isBaseline) return "Original GeoTIFF";
  const base = CANDIDATE_NAMES[r.id] ?? r.id;
  return r.codecLevel !== null ? `${base} · Zstd ${r.codecLevel}` : base;
}
