import type { Cell, Geometry, Result } from "./types";

export type LiveGrid = {
  shape: [number, number];
  crs: "EPSG:4326";
  transform: [number, number, number, number, number, number];
};
export type LiveSnapshot = {
  query_version: "hansen-centers.v1";
  product: string;
  source_metadata_sha256: string;
  grid: LiveGrid;
  full_raw_masks_equal: true;
  sources: Array<{
    band: string;
    path: string;
    sha256: string;
    bytes: number;
    [key: string]: unknown;
  }>;
  retained: {
    experiment_id: string;
    run_id: string;
    store_path: string;
    candidate: string;
    files: LiveFile[];
  };
  query_implementation_sha256: Record<string, string>;
  verified_files: LiveFile[];
  [key: string]: unknown;
};
export type LiveFile = { path: string; sha256: string; bytes: number };
export type LiveHealth = {
  schema_version: "plotline.live-health.v1";
  status: "ready";
  snapshot_id: string;
  snapshot: LiveSnapshot;
  snapshot_canonical_json: string;
  limits: {
    max_body_bytes: 65536;
    max_vertices: 512;
    max_candidate_cells: 4096;
    max_selected_cells: 4096;
    evidence_mode: "all_selected_cells";
  };
  periods: Record<"2021-2023" | "2024-2025", [number, number]>;
  lifetime: "immutable_loaded_snapshot_until_restart";
};
export type LiveRequest = {
  schema_version: "plotline.live-request.v1";
  request_id: string;
  expected_snapshot_id: string;
  geometry: Geometry;
};
export type LiveEvidence = {
  complete: true;
  selected_cell_count: number;
  returned_cell_count: number;
  cells: { type: "FeatureCollection"; features: Cell[] };
};
export type LiveReceiptPayload = {
  request_id: string;
  request_body_sha256: string;
  snapshot_id: string;
  query_version: "hansen-centers.v1";
  geometry_sha256: string;
  source_result_sha256: string;
  compact_result_sha256: string;
  evidence_sha256: string;
  boundary_rule: string;
  valid_land_rule: string;
  partial_support_rule: string;
  periods: LiveHealth["periods"];
  [key: string]: unknown;
};
export type LiveReceipt = {
  payload: LiveReceiptPayload;
  canonical_json: string;
  sha256: string;
};
export type LiveQueryResponse = {
  schema_version: "plotline.live-query.v1";
  request_id: string;
  request_body_sha256: string;
  snapshot_id: string;
  query_version: "hansen-centers.v1";
  region_kind: "temporary_user_geometry";
  geometry: Geometry;
  geometry_sha256: string;
  source_result: Result;
  compact_result: Result;
  comparison: { equal: true; differing_fields: string[] };
  native_grid: LiveGrid;
  evidence: LiveEvidence;
  receipt: LiveReceipt;
  runtime: {
    source_query_ms: number;
    compact_query_ms: number;
    evidence_ms: number;
    total_request_ms: number;
    scope: "single_request_preloaded_arrays_no_network_or_UI";
    benchmark: false;
  };
  interpretation: string;
};
export type LiveErrorKind =
  | "unavailable"
  | "http"
  | "service"
  | "invalid_response"
  | "invalid_request"
  | "unsupported";
export class LiveClientError extends Error {
  readonly kind: LiveErrorKind;
  readonly code: string;
  readonly status: number | null;
  readonly requestId: string | null;
  constructor(
    kind: LiveErrorKind,
    code: string,
    message: string,
    status: number | null = null,
    requestId: string | null = null,
  ) {
    super(message);
    this.name = "LiveClientError";
    this.kind = kind;
    this.code = code;
    this.status = status;
    this.requestId = requestId;
  }
}

type Obj = Record<string, unknown>;
const PERIODS = { "2021-2023": [2021, 2023], "2024-2025": [2024, 2025] };
const LIMITS = {
  max_body_bytes: 65536,
  max_vertices: 512,
  max_candidate_cells: 4096,
  max_selected_cells: 4096,
  evidence_mode: "all_selected_cells",
};
const BANDS = ["treecover2000", "lossyear", "datamask"];
const RULES = {
  boundary_rule:
    "native cell centers covered by polygon, including polygon and hole boundaries",
  valid_land_rule:
    "datamask == 1 and every required band validity mask is true",
  partial_support_rule:
    "retain observed valid-land counts; witnessed loss true; absent loss unknown",
};
const errorStatuses: Record<string, number> = {
  INVALID_JSON: 400,
  INVALID_REQUEST: 400,
  ORIGIN_NOT_ALLOWED: 403,
  HOST_NOT_ALLOWED: 403,
  NOT_FOUND: 404,
  METHOD_NOT_ALLOWED: 405,
  SNAPSHOT_MISMATCH: 409,
  BODY_TOO_LARGE: 413,
  UNSUPPORTED_MEDIA_TYPE: 415,
  INVALID_GEOMETRY: 422,
  QUERY_TOO_LARGE: 422,
  COMPARISON_MISMATCH: 500,
  INTERNAL_ERROR: 500,
  NOT_READY: 503,
  BUSY: 503,
};
function check(ok: unknown, path: string, message: string): asserts ok {
  if (!ok)
    throw new LiveClientError(
      "invalid_response",
      "INVALID_RESPONSE",
      `Live response rejected at ${path}: ${message}.`,
    );
}
function obj(v: unknown, path: string): Obj {
  check(
    v !== null && typeof v === "object" && !Array.isArray(v),
    path,
    "expected an object",
  );
  check(
    Object.getPrototypeOf(v) === Object.prototype ||
      Object.getPrototypeOf(v) === null,
    path,
    "expected a JSON object",
  );
  return v as Obj;
}
function arr(v: unknown, path: string): unknown[] {
  check(Array.isArray(v), path, "expected an array");
  return v;
}
function str(v: unknown, path: string): string {
  check(
    typeof v === "string" && v.length > 0,
    path,
    "expected a nonempty string",
  );
  return v;
}
function num(v: unknown, path: string): number {
  check(
    typeof v === "number" && Number.isFinite(v),
    path,
    "expected a finite number",
  );
  return v;
}
function int(v: unknown, path: string, min = 0): number {
  check(
    Number.isSafeInteger(v) && (v as number) >= min,
    path,
    `expected an integer >= ${min}`,
  );
  return v as number;
}
function digest(v: unknown, path: string): string {
  check(
    typeof v === "string" && /^[0-9a-f]{64}$/.test(v),
    path,
    "expected a lowercase SHA-256 digest",
  );
  return v;
}
function exactKeys(o: Obj, expected: string[], path: string) {
  check(
    Object.keys(o).length === expected.length &&
      expected.every((k) => Object.hasOwn(o, k)),
    path,
    "unexpected or missing fields",
  );
}
function same(a: unknown, b: unknown, depth = 0): boolean {
  check(depth <= 64, "JSON", "nesting exceeds the supported depth");
  if (a === b) return true;
  if (Array.isArray(a) && Array.isArray(b))
    return a.length === b.length && a.every((v, i) => same(v, b[i], depth + 1));
  if (
    a !== null &&
    b !== null &&
    typeof a === "object" &&
    typeof b === "object" &&
    !Array.isArray(a) &&
    !Array.isArray(b)
  ) {
    const x = obj(a, "JSON"),
      y = obj(b, "JSON"),
      keys = Object.keys(x);
    return (
      keys.length === Object.keys(y).length &&
      keys.every((k) => Object.hasOwn(y, k) && same(x[k], y[k], depth + 1))
    );
  }
  return false;
}
function parse(text: string, path: string): unknown {
  try {
    return JSON.parse(text);
  } catch {
    throw new LiveClientError(
      "invalid_response",
      "INVALID_JSON_RESPONSE",
      `Live response at ${path} is not valid JSON.`,
    );
  }
}
function copy<T>(v: T): T {
  return JSON.parse(JSON.stringify(v)) as T;
}
function cancelled(signal?: AbortSignal) {
  signal?.throwIfAborted();
}
async function sha(text: string, signal?: AbortSignal): Promise<string> {
  cancelled(signal);
  if (!globalThis.crypto?.subtle)
    throw new LiveClientError(
      "unsupported",
      "CRYPTO_UNAVAILABLE",
      "This browser cannot check live receipts. Use the local app in a secure browser context.",
    );
  const bytes = await globalThis.crypto.subtle.digest(
    "SHA-256",
    new TextEncoder().encode(text),
  );
  cancelled(signal);
  return [...new Uint8Array(bytes)]
    .map((v) => v.toString(16).padStart(2, "0"))
    .join("");
}
async function canonical(
  text: unknown,
  value: unknown,
  hash: unknown,
  path: string,
  signal?: AbortSignal,
) {
  const encoded = str(text, `${path}.canonical_json`);
  check(
    same(parse(encoded, path), value),
    path,
    "canonical JSON does not match the supplied object",
  );
  check(
    (await sha(encoded, signal)) === digest(hash, `${path}.sha256`),
    path,
    "canonical bytes do not match the declared digest",
  );
}
function grid(value: unknown, path: string): LiveGrid {
  const g = obj(value, path),
    shape = arr(g.shape, `${path}.shape`),
    t = arr(g.transform, `${path}.transform`);
  check(shape.length === 2, path, "expected height and width");
  shape.forEach((n, i) => int(n, `${path}.shape[${i}]`, 1));
  check(t.length === 6, path, "expected six affine values");
  t.forEach((n, i) => num(n, `${path}.transform[${i}]`));
  check(
    g.crs === "EPSG:4326" &&
      (t[0] as number) > 0 &&
      t[1] === 0 &&
      t[3] === 0 &&
      (t[4] as number) < 0,
    path,
    "expected the north-up EPSG:4326 grid",
  );
  return value as LiveGrid;
}
function files(value: unknown, path: string): LiveFile[] {
  const list = arr(value, path),
    seen = new Set<string>();
  check(list.length > 0, path, "source/store identity requires files");
  list.forEach((v, i) => {
    const p = `${path}[${i}]`,
      f = obj(v, p),
      name = str(f.path, `${p}.path`);
    check(!seen.has(name), p, "duplicate file identity");
    seen.add(name);
    digest(f.sha256, `${p}.sha256`);
    int(f.bytes, `${p}.bytes`);
  });
  return value as LiveFile[];
}

/** Pure-response gate, exported for paired fixture checks. Hash checks are integrity, not authentication. */
export async function validateLiveHealth(
  value: unknown,
  signal?: AbortSignal,
): Promise<LiveHealth> {
  const h = obj(value, "health");
  check(
    h.schema_version === "plotline.live-health.v1" && h.status === "ready",
    "health",
    "service must publish the ready v1 schema",
  );
  check(
    h.lifetime === "immutable_loaded_snapshot_until_restart",
    "health.lifetime",
    "unexpected snapshot lifetime",
  );
  check(
    same(h.limits, LIMITS) && same(h.periods, PERIODS),
    "health",
    "limits or periods differ from the v1 contract",
  );
  const s = obj(h.snapshot, "snapshot");
  check(
    s.query_version === "hansen-centers.v1" && s.full_raw_masks_equal === true,
    "snapshot",
    "expected checked source/store equality under hansen-centers.v1",
  );
  str(s.product, "snapshot.product");
  digest(s.source_metadata_sha256, "snapshot.source_metadata_sha256");
  grid(s.grid, "snapshot.grid");
  const sources = files(s.sources, "snapshot.sources") as Array<
    LiveFile & { band?: unknown }
  >;
  check(
    sources.length === 3 &&
      BANDS.every((b) => sources.filter((s) => s.band === b).length === 1),
    "snapshot.sources",
    "expected each Hansen band exactly once",
  );
  const retained = obj(s.retained, "snapshot.retained");
  check(
    /^exp-[a-f0-9]{64}$/.test(
      str(retained.experiment_id, "retained.experiment_id"),
    ) && /^run-[a-f0-9]{64}$/.test(str(retained.run_id, "retained.run_id")),
    "snapshot.retained",
    "invalid retained experiment/run identity",
  );
  str(retained.store_path, "retained.store_path");
  str(retained.candidate, "retained.candidate");
  const storeFiles = files(retained.files, "retained.files");
  const code = obj(
    s.query_implementation_sha256,
    "snapshot.query_implementation_sha256",
  );
  check(
    Object.keys(code).length > 0,
    "snapshot.query_implementation_sha256",
    "implementation identity is missing",
  );
  Object.entries(code).forEach(([name, hash]) =>
    digest(hash, `snapshot.query_implementation_sha256.${name}`),
  );
  const verified = files(s.verified_files, "snapshot.verified_files");
  for (const f of [...sources, ...storeFiles])
    check(
      verified.some(
        (v) =>
          v.path === f.path && v.bytes === f.bytes && v.sha256 === f.sha256,
      ),
      "snapshot.verified_files",
      "source/store file identity is absent or inconsistent",
    );
  for (const [name, hash] of Object.entries(code))
    check(
      verified.some((f) => f.path === `engine/${name}` && f.sha256 === hash),
      "snapshot.verified_files",
      "implementation identity is absent or inconsistent",
    );
  await canonical(
    h.snapshot_canonical_json,
    s,
    h.snapshot_id,
    "snapshot",
    signal,
  );
  return value as LiveHealth;
}

function geometry(value: unknown, maxVertices: number) {
  const g = obj(value, "geometry");
  exactKeys(g, ["type", "coordinates"], "geometry");
  check(
    g.type === "Polygon" || g.type === "MultiPolygon",
    "geometry.type",
    "expected Polygon or MultiPolygon",
  );
  const polygons =
    g.type === "Polygon"
      ? [g.coordinates]
      : arr(g.coordinates, "geometry.coordinates");
  check(polygons.length > 0, "geometry", "expected polygons");
  let positions = 0;
  polygons.forEach((polygon, i) => {
    const rings = arr(polygon, `geometry[${i}]`);
    check(rings.length > 0, "geometry", "expected exterior ring");
    rings.forEach((value, j) => {
      const ring = arr(value, `geometry[${i}][${j}]`);
      positions += ring.length;
      check(
        ring.length >= 4 && positions <= maxVertices,
        "geometry",
        `rings need at least four positions; maximum ${maxVertices} positions`,
      );
      ring.forEach((v) => {
        const p = arr(v, "geometry.position");
        check(
          p.length === 2 &&
            Math.abs(num(p[0], "longitude")) <= 180 &&
            Math.abs(num(p[1], "latitude")) <= 90,
          "geometry.position",
          "expected finite longitude/latitude in range",
        );
      });
      check(
        same(ring[0], ring.at(-1)),
        "geometry",
        "rings must be explicitly closed",
      );
    });
  });
}
function result(value: unknown, path: string): Result {
  const r = obj(value, path);
  const n = int(r.selected_cell_count, `${path}.selected_cell_count`),
    inside = int(r.in_coverage_cell_count, `${path}.in_coverage_cell_count`),
    outside = int(
      r.out_of_coverage_cell_count,
      `${path}.out_of_coverage_cell_count`,
    );
  const land = int(r.valid_land_cell_count, `${path}.valid_land_cell_count`),
    unknown = int(r.unknown_cell_count, `${path}.unknown_cell_count`);
  check(
    n <= 4096 &&
      n === inside + outside &&
      land <= inside &&
      unknown >= outside &&
      land + unknown <= n,
    path,
    "invalid selected/covered/land/unknown accounting or selected-cell limit",
  );
  const reasons = arr(r.unknown_reasons, `${path}.unknown_reasons`).map((v) =>
    str(v, `${path}.unknown_reasons`),
  );
  check(
    new Set(reasons).size === reasons.length,
    path,
    "duplicate unknown reason",
  );
  const missing = reasons.filter((x) => x.startsWith("missing_band:"));
  check(
    missing.every((x) => BANDS.includes(x.slice(13))),
    path,
    "invalid missing-band name",
  );
  check(
    reasons.includes("no_selected_cells") === (n === 0) &&
      reasons.includes("out_of_coverage") === outside > 0 &&
      reasons.includes("no_valid_land") === (n > 0 && land === 0),
    path,
    "unknown reasons contradict support",
  );
  const mask = obj(r.datamask_counts, `${path}.datamask_counts`);
  exactKeys(mask, ["0", "1", "2"], path);
  const masks = ["0", "1", "2"].map((k) =>
      int(mask[k], `${path}.datamask_counts.${k}`),
    ),
    total = masks.reduce((a, b) => a + b, 0);
  check(
    total <= inside &&
      land <= masks[1] &&
      unknown >= outside + masks[0] &&
      unknown >= outside + inside - total,
    path,
    "diagnostic mask counts contradict support",
  );
  check(
    reasons.includes("nodata") === masks[0] > 0,
    path,
    "nodata reason contradicts diagnostics",
  );
  if (missing.length)
    check(
      land === 0 &&
        unknown === n &&
        (!inside || reasons.includes("band_mask_invalid")),
      path,
      "missing bands must suppress analytical support",
    );
  if (missing.includes("missing_band:datamask"))
    check(
      total === 0,
      path,
      "missing datamask requires zero diagnostic counts",
    );
  if (reasons.includes("band_mask_invalid"))
    check(
      inside > 0 && unknown > outside,
      path,
      "invalid-band reason needs covered unknowns",
    );
  if (unknown > outside && masks[0] === 0 && !missing.length)
    check(
      reasons.includes("band_mask_invalid"),
      path,
      "covered unknowns require invalid-band reason",
    );
  const support = missing.length
    ? "unavailable"
    : !n || !land
      ? "none"
      : unknown
        ? "partial"
        : "complete";
  check(r.support === support, `${path}.support`, "support contradicts counts");
  const analytic = land > 0 && !missing.length;
  for (const [key, length] of [
    ["canopy_histogram", 101],
    ["lossyear_histogram", 26],
  ] as const) {
    if (!analytic)
      check(
        r[key] === null,
        `${path}.${key}`,
        "unavailable analytics require null",
      );
    else {
      const bins = arr(r[key], `${path}.${key}`).map((v) =>
        int(v, `${path}.${key}`),
      );
      check(
        bins.length === length && bins.reduce((a, b) => a + b, 0) === land,
        `${path}.${key}`,
        "integer bins must have the native length and sum to valid land",
      );
    }
  }
  const loss = r.lossyear_histogram as number[] | null;
  if (analytic) {
    const annual = obj(r.yearly_loss_counts, `${path}.yearly_loss_counts`);
    const years = Array.from({ length: 25 }, (_, i) => String(2001 + i));
    exactKeys(annual, years, path);
    years.forEach((y, i) =>
      check(
        annual[y] === loss![i + 1],
        `${path}.yearly_loss_counts.${y}`,
        "year must match histogram",
      ),
    );
  } else
    check(
      r.yearly_loss_counts === null,
      path,
      "unavailable annual counts require null",
    );
  const ps = obj(r.periods, `${path}.periods`);
  exactKeys(ps, Object.keys(PERIODS), path);
  for (const [name, [start, end]] of Object.entries(PERIODS)) {
    const p = obj(ps[name], `${path}.periods.${name}`),
      count = analytic
        ? loss!.slice(start - 2000, end - 1999).reduce((a, b) => a + b, 0)
        : null;
    check(
      p.observed_loss_cell_count === count &&
        p.mapped_loss_present ===
          (count === null
            ? null
            : count > 0
              ? true
              : support === "complete"
                ? false
                : null),
      `${path}.periods.${name}`,
      "count/tri-state signal must follow observed evidence and support",
    );
  }
  return value as Result;
}

function evidence(value: unknown, source: Result, g: LiveGrid): LiveEvidence {
  const e = obj(value, "evidence"),
    n = source.selected_cell_count;
  check(
    e.complete === true &&
      e.selected_cell_count === n &&
      e.returned_cell_count === n,
    "evidence",
    "v1 requires all selected cells; truncation is not accepted",
  );
  const collection = obj(e.cells, "evidence.cells"),
    features = arr(collection.features, "evidence.cells.features");
  check(
    collection.type === "FeatureCollection" && features.length === n,
    "evidence.cells",
    "feature count must match complete selected support",
  );
  const seen = new Set<string>(),
    mask = [0, 0, 0],
    canopy = Array(101).fill(0) as number[],
    loss = Array(26).fill(0) as number[];
  let covered = 0,
    land = 0,
    unknown = 0,
    invalid = false;
  const [a, , x0, , , y0] = g.transform,
    yStep = g.transform[4];
  for (const [i, v] of features.entries()) {
    const path = `evidence.cells.features[${i}]`,
      f = obj(v, path),
      p = obj(f.properties, `${path}.properties`);
    check(f.type === "Feature", path, "expected Feature");
    const row = int(p.row, `${path}.row`, Number.MIN_SAFE_INTEGER),
      col = int(p.col, `${path}.col`, Number.MIN_SAFE_INTEGER),
      id = `${row}:${col}`;
    check(!seen.has(id), path, "duplicate native cell");
    seen.add(id);
    if (f.id !== undefined)
      check(f.id === id, path, "cell ID differs from native indices");
    const inside = row >= 0 && col >= 0 && row < g.shape[0] && col < g.shape[1];
    check(p.in_coverage === inside, path, "coverage differs from native grid");
    const validity = arr(p.band_validity, `${path}.band_validity`);
    check(
      validity.length === 3 && validity.every((v) => typeof v === "boolean"),
      path,
      "expected three band-validity booleans",
    );
    BANDS.forEach((b, j) => {
      if (inside)
        check(
          int(p[b], `${path}.${b}`) <= [100, 25, 2][j],
          path,
          "raw value outside native band domain",
        );
      else
        check(
          p[b] === null && validity[j] === false,
          path,
          "outside cells need null raw values and invalid masks",
        );
    });
    const valid =
      inside && p.datamask === 1 && validity.every((v) => v === true);
    check(
      p.valid_land === valid,
      path,
      "valid land contradicts raw mask/validity",
    );
    const west = x0 + col * a,
      east = x0 + (col + 1) * a,
      north = y0 + row * yStep,
      south = y0 + (row + 1) * yStep;
    check(
      same(p.center, [x0 + (col + 0.5) * a, y0 + (row + 0.5) * yStep]),
      path,
      "cell center differs from native lattice",
    );
    check(
      same(f.geometry, {
        type: "Polygon",
        coordinates: [
          [
            [west, north],
            [east, north],
            [east, south],
            [west, south],
            [west, north],
          ],
        ],
      }),
      path,
      "cell footprint differs from native lattice",
    );
    if (inside) {
      covered++;
      if (validity[2]) mask[p.datamask as number]++;
      if (valid) {
        land++;
        canopy[p.treecover2000 as number]++;
        loss[p.lossyear as number]++;
      }
      if (
        validity.some((v) => v === false) ||
        (validity[2] && p.datamask === 0)
      )
        unknown++;
      if (validity.some((v) => v === false)) invalid = true;
    } else unknown++;
  }
  const missing = source.unknown_reasons.filter((v) =>
    v.startsWith("missing_band:"),
  );
  check(
    covered === source.in_coverage_cell_count &&
      source.valid_land_cell_count === (missing.length ? 0 : land) &&
      source.unknown_cell_count === (missing.length ? n : unknown),
    "evidence",
    "evidence support differs from source result",
  );
  check(
    same(
      source.datamask_counts,
      Object.fromEntries(
        (missing.includes("missing_band:datamask") ? [0, 0, 0] : mask).map(
          (n, i) => [String(i), n],
        ),
      ),
    ),
    "evidence",
    "diagnostic masks differ from source result",
  );
  if (!missing.length) {
    check(
      source.unknown_reasons.includes("band_mask_invalid") === invalid,
      "evidence",
      "invalid-mask reason differs from evidence",
    );
    if (land)
      check(
        same(source.canopy_histogram, canopy) &&
          same(source.lossyear_histogram, loss),
        "evidence",
        "observed histogram differs from supplied valid native cells",
      );
  }
  return value as LiveEvidence;
}

async function transport(
  path: "/v1/health" | "/v1/query",
  signal?: AbortSignal,
  body?: string,
  requestId: string | null = null,
): Promise<unknown> {
  cancelled(signal);
  let response: Response;
  try {
    response = await fetch(path, {
      method: body === undefined ? "GET" : "POST",
      body,
      headers:
        body === undefined
          ? { Accept: "application/json" }
          : { Accept: "application/json", "Content-Type": "application/json" },
      cache: "no-store",
      mode: "same-origin",
      credentials: "omit",
      redirect: "error",
      signal,
    });
  } catch (error) {
    cancelled(signal);
    if (error instanceof Error && error.name === "AbortError") throw error;
    throw new LiveClientError(
      "unavailable",
      "SERVICE_UNAVAILABLE",
      "The optional local query service could not be reached. Start the loopback service and retry; frozen review remains available.",
      null,
      requestId,
    );
  }
  let text: string;
  try {
    text = await response.text();
  } catch (error) {
    cancelled(signal);
    if (error instanceof Error && error.name === "AbortError") throw error;
    throw new LiveClientError(
      "unavailable",
      "RESPONSE_UNREADABLE",
      "The local service response was interrupted. Retry the query.",
      response.status,
      requestId,
    );
  }
  cancelled(signal);
  if (!response.ok) {
    let value: unknown;
    try {
      value = JSON.parse(text);
    } catch {
      throw new LiveClientError(
        response.status >= 500 ? "unavailable" : "http",
        response.status >= 500 ? "SERVICE_UNAVAILABLE" : "HTTP_ERROR",
        `Local query request failed (HTTP ${response.status}); the service or loopback proxy did not return a JSON error. Retry after checking the local service.`,
        response.status,
        requestId,
      );
    }
    const envelope = obj(value, "error response"),
      e = obj(envelope.error, "error response.error");
    check(
      envelope.schema_version === "plotline.live-error.v1" &&
        typeof e.code === "string" &&
        errorStatuses[e.code] === response.status,
      "error response",
      "unexpected error schema/code/status",
    );
    check(
      envelope.request_id === null || envelope.request_id === requestId,
      "error response.request_id",
      "error belongs to a different request",
    );
    const message = str(e.message, "error response.message");
    throw new LiveClientError(
      "service",
      e.code as string,
      message,
      response.status,
      envelope.request_id as string | null,
    );
  }
  check(
    response.status === 200,
    "HTTP status",
    "successful live responses require HTTP 200",
  );
  check(
    /^application\/json(?:\s*;|$)/i.test(
      response.headers.get("content-type") ?? "",
    ),
    "Content-Type",
    "expected application/json",
  );
  check(text.trim().length > 0, "body", "empty successful response");
  return parse(text, "body");
}

export async function getLiveHealth(signal?: AbortSignal): Promise<LiveHealth> {
  return validateLiveHealth(await transport("/v1/health", signal), signal);
}

/** Freeze submitted values before the first await; caller owns active-request sequencing. */
export async function runLiveQuery(
  geometryValue: Geometry,
  requestId: string,
  health: LiveHealth,
  signal?: AbortSignal,
): Promise<LiveQueryResponse> {
  cancelled(signal);
  try {
    check(
      typeof requestId === "string" && /^[A-Za-z0-9_-]{1,64}$/.test(requestId),
      "request_id",
      "use 1–64 ASCII letters/digits/underscore/hyphen",
    );
    geometry(geometryValue, 512);
  } catch (error) {
    if (error instanceof LiveClientError)
      throw new LiveClientError(
        "invalid_request",
        "INVALID_REQUEST",
        error.message,
        null,
        requestId,
      );
    throw error;
  }
  const submitted = copy(geometryValue),
    frozenHealth = copy(health);
  const request: LiveRequest = {
    schema_version: "plotline.live-request.v1",
    request_id: requestId,
    expected_snapshot_id: frozenHealth.snapshot_id,
    geometry: submitted,
  };
  const body = JSON.stringify(request);
  if (new TextEncoder().encode(body).length > 65536)
    throw new LiveClientError(
      "invalid_request",
      "BODY_TOO_LARGE",
      "The submitted geometry exceeds the 65536-byte request limit.",
      null,
      requestId,
    );
  await validateLiveHealth(frozenHealth, signal);
  const bodyHash = await sha(body, signal);
  const response = await transport("/v1/query", signal, body, requestId);
  return validateLiveQueryResponse(
    response,
    request,
    bodyHash,
    frozenHealth,
    signal,
  );
}

/** Validate one response against the exact request context. No source queries or guessed canonical serializer. */
export async function validateLiveQueryResponse(
  value: unknown,
  request: LiveRequest,
  bodyHash: string,
  health: LiveHealth,
  signal?: AbortSignal,
): Promise<LiveQueryResponse> {
  const r = obj(value, "query");
  check(
    r.schema_version === "plotline.live-query.v1" &&
      r.query_version === "hansen-centers.v1" &&
      r.region_kind === "temporary_user_geometry",
    "query",
    "unexpected live schema/query/scope",
  );
  check(
    r.request_id === request.request_id && r.request_body_sha256 === bodyHash,
    "query",
    "request identity or exact body digest differs",
  );
  check(
    r.snapshot_id === health.snapshot_id &&
      r.snapshot_id === request.expected_snapshot_id &&
      same(r.native_grid, health.snapshot.grid),
    "query",
    "response snapshot/grid differs from submitted health",
  );
  check(
    same(r.geometry, request.geometry),
    "query.geometry",
    "response geometry differs from the exact submitted geometry",
  );
  digest(r.geometry_sha256, "geometry_sha256");
  const source = result(r.source_result, "source_result");
  result(r.compact_result, "compact_result");
  const comparison = obj(r.comparison, "comparison");
  check(
    comparison.equal === true &&
      same(comparison.differing_fields, []) &&
      same(r.source_result, r.compact_result),
    "comparison",
    "v1 success requires actual identical source/compact outputs",
  );
  evidence(r.evidence, source, health.snapshot.grid);
  const receipt = obj(r.receipt, "receipt"),
    payload = obj(receipt.payload, "receipt.payload");
  await canonical(
    receipt.canonical_json,
    payload,
    receipt.sha256,
    "receipt",
    signal,
  );
  for (const key of [
    "request_id",
    "request_body_sha256",
    "snapshot_id",
    "query_version",
    "geometry_sha256",
  ])
    check(
      payload[key] === r[key],
      `receipt.payload.${key}`,
      "receipt differs from response/request context",
    );
  for (const key of [
    "geometry_sha256",
    "source_result_sha256",
    "compact_result_sha256",
    "evidence_sha256",
  ])
    digest(payload[key], `receipt.payload.${key}`);
  check(
    payload.source_result_sha256 === payload.compact_result_sha256,
    "receipt",
    "identical results must have identical declared digests",
  );
  for (const [key, rule] of Object.entries(RULES))
    check(
      payload[key] === rule,
      `receipt.payload.${key}`,
      "query rule differs from accepted contract",
    );
  check(
    same(payload.periods, health.periods),
    "receipt.payload.periods",
    "period definitions differ from health",
  );
  // Required exact-byte evidence/result bindings await the additive engine contract.
  // Do not silently accept a valid self-hashed receipt with unbound observations.
  if (
    !Object.hasOwn(r, "evidence_canonical_json") ||
    !Object.hasOwn(r, "source_result_canonical_json") ||
    !Object.hasOwn(r, "compact_result_canonical_json")
  )
    throw new LiveClientError(
      "invalid_response",
      "BINDING_UNAVAILABLE",
      "The live response lacks canonical result/evidence bytes needed to check receipt bindings. Restart with the compatible local service.",
      200,
      request.request_id,
    );
  await canonical(
    r.source_result_canonical_json,
    r.source_result,
    payload.source_result_sha256,
    "source_result",
    signal,
  );
  await canonical(
    r.compact_result_canonical_json,
    r.compact_result,
    payload.compact_result_sha256,
    "compact_result",
    signal,
  );
  await canonical(
    r.evidence_canonical_json,
    r.evidence,
    payload.evidence_sha256,
    "evidence",
    signal,
  );
  const timing = obj(r.runtime, "runtime");
  for (const k of [
    "source_query_ms",
    "compact_query_ms",
    "evidence_ms",
    "total_request_ms",
  ])
    check(
      num(timing[k], `runtime.${k}`) >= 0,
      `runtime.${k}`,
      "timing must be nonnegative",
    );
  check(
    timing.scope === "single_request_preloaded_arrays_no_network_or_UI" &&
      timing.benchmark === false,
    "runtime",
    "request timing must not claim benchmark scope",
  );
  check(
    r.interpretation ===
      "Mapped observations for a temporary geometry on a frozen local snapshot; no supplier or legal finding.",
    "interpretation",
    "temporary observation scope must remain explicit",
  );
  cancelled(signal);
  return value as LiveQueryResponse;
}
