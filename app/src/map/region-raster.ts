/*
 * Display rasters for the map (display only, never evidence).
 *
 * `/region/hansen-bands.png` packs Hansen lossyear / datamask / treecover2000 into
 * R / G / B and `/region/jrc-forest-2020.png` packs the JRC class into R. They are
 * decoded exactly (no colour conversion, no alpha premultiplication), validated
 * against `/region/manifest.json` and then recoloured in the browser. Every count
 * presented as evidence still comes from the verified export; the only number
 * derived here is the per-year land loss-pixel total used as a region display
 * statistic.
 */
import { useEffect, useSyncExternalStore } from "react";
import type { Bounds } from "./projection";

export type MapMode = "loss" | "canopy" | "mask";
export const YEAR_COUNT = 25;
export const FIRST_YEAR = 2001;

export type RasterGrid = {
  product: string;
  rows: number;
  cols: number;
  /** Affine [a, b, c, d, e, f]: lon = c + a*col, lat = f + e*row (north-up, e < 0). */
  transform: readonly [number, number, number, number, number, number];
  bounds: Bounds;
};
export type HansenRaster = RasterGrid & {
  /** 0 = no loss, n = 2000 + n. Values 0..25. */
  lossyear: Uint8Array;
  /** 0 no data, 1 land, 2 water. */
  datamask: Uint8Array;
  /** Percent 0..100. */
  treecover: Uint8Array;
};
export type JrcRaster = RasterGrid & {
  /** 0 = valid Non-forest, 1 = Forest. Class 0 is data, not missing. */
  klass: Uint8Array;
};
export type RegionRasterData = {
  hansen: HansenRaster;
  jrc: JrcRaster;
  /** "sha256" when the downloaded PNG bytes matched the manifest hash; "unchecked" without SubtleCrypto. */
  integrity: { hansen: "sha256" | "unchecked"; jrc: "sha256" | "unchecked" };
};
export type RegionRaster = {
  status: "loading" | "ready" | "unavailable";
  error?: string;
  /** Index 0 = 2001 ... 24 = 2025; land pixels with loss in that year (display statistic). */
  yearlyLossPixels: number[] | null;
  /** Decoded bands and grids; null until ready. */
  data: RegionRasterData | null;
  /** Hansen chip bounds, known as soon as the manifest has loaded (even while PNGs load). */
  chipBounds: Bounds | null;
};

/* ------------------------------------------------------------------ loading */

const BASE = "/region/";
type ManifestGrid = {
  product: string;
  shape_rows_columns: [number, number];
  transform: [number, number, number, number, number, number];
  bounds_west_south_east_north: [number, number, number, number];
  png: string;
  png_sha256: string;
};

function isNumArray(v: unknown, n: number): v is number[] {
  return Array.isArray(v) && v.length === n && v.every((x) => typeof x === "number" && Number.isFinite(x));
}

function parseGrid(name: string, value: unknown): ManifestGrid {
  const g = value as Partial<ManifestGrid> | null;
  if (!g || typeof g !== "object") throw new Error(`Manifest has no ${name} entry.`);
  if (typeof g.product !== "string" || !g.product) throw new Error(`Manifest ${name}.product is missing.`);
  if (!isNumArray(g.shape_rows_columns, 2) || !g.shape_rows_columns.every((n) => Number.isInteger(n) && n > 0))
    throw new Error(`Manifest ${name}.shape_rows_columns is invalid.`);
  if (!isNumArray(g.transform, 6)) throw new Error(`Manifest ${name}.transform is invalid.`);
  if (!isNumArray(g.bounds_west_south_east_north, 4)) throw new Error(`Manifest ${name}.bounds are invalid.`);
  if (typeof g.png !== "string" || !/^[A-Za-z0-9._-]+\.png$/.test(g.png)) throw new Error(`Manifest ${name}.png is not a plain file name.`);
  if (typeof g.png_sha256 !== "string" || !/^[0-9a-f]{64}$/.test(g.png_sha256)) throw new Error(`Manifest ${name}.png_sha256 is invalid.`);
  const [a, b, c, d, e, f] = g.transform;
  const [rows, cols] = g.shape_rows_columns;
  if (!(a > 0 && e < 0 && b === 0 && d === 0)) throw new Error(`Manifest ${name}.transform is not a north-up grid.`);
  const [w, s, ea, n] = g.bounds_west_south_east_north;
  const tol = Math.abs(a) * 1e-6;
  if (Math.abs(w - c) > tol || Math.abs(n - f) > tol || Math.abs(ea - (c + a * cols)) > tol || Math.abs(s - (f + e * rows)) > tol)
    throw new Error(`Manifest ${name} bounds do not match its transform and shape.`);
  return g as ManifestGrid;
}

async function sha256Hex(bytes: ArrayBuffer): Promise<string | null> {
  const subtle = globalThis.crypto?.subtle;
  if (!subtle) return null;
  const digest = await subtle.digest("SHA-256", bytes);
  return Array.from(new Uint8Array(digest), (b) => b.toString(16).padStart(2, "0")).join("");
}

/** Decode a PNG into exact RGBA bytes: no colour conversion, no premultiplication. */
async function decodeRgba(blob: Blob, width: number, height: number, label: string): Promise<Uint8ClampedArray> {
  let source: CanvasImageSource;
  let w: number;
  let h: number;
  try {
    const bitmap = await createImageBitmap(blob, { colorSpaceConversion: "none", premultiplyAlpha: "none" });
    source = bitmap;
    w = bitmap.width;
    h = bitmap.height;
  } catch {
    // Fallback decoder; the PNGs carry no colour-profile chunks so no conversion applies.
    const url = URL.createObjectURL(blob);
    try {
      const img = new Image();
      img.decoding = "sync";
      img.src = url;
      await img.decode();
      source = img;
      w = img.naturalWidth;
      h = img.naturalHeight;
    } finally {
      URL.revokeObjectURL(url);
    }
  }
  if (w !== width || h !== height) throw new Error(`${label} decoded as ${w}x${h}, but the manifest says ${width}x${height}.`);
  const canvas = document.createElement("canvas");
  canvas.width = width;
  canvas.height = height;
  const ctx = canvas.getContext("2d", { willReadFrequently: true, colorSpace: "srgb" });
  if (!ctx) throw new Error("Canvas 2D is unavailable, so the display raster cannot be decoded.");
  ctx.imageSmoothingEnabled = false;
  ctx.globalCompositeOperation = "copy";
  ctx.drawImage(source, 0, 0);
  if ("close" in source && typeof source.close === "function") source.close();
  return ctx.getImageData(0, 0, width, height, { colorSpace: "srgb" }).data;
}

async function fetchPng(grid: ManifestGrid, label: string): Promise<{ rgba: Uint8ClampedArray; integrity: "sha256" | "unchecked" }> {
  const url = BASE + grid.png;
  const res = await fetch(url);
  if (!res.ok) throw new Error(`${label}: ${url} returned HTTP ${res.status}.`);
  const bytes = await res.arrayBuffer();
  const digest = await sha256Hex(bytes);
  if (digest !== null && digest !== grid.png_sha256)
    throw new Error(`${label}: ${grid.png} does not match the manifest SHA-256, so it was not drawn.`);
  const [rows, cols] = grid.shape_rows_columns;
  const rgba = await decodeRgba(new Blob([bytes], { type: "image/png" }), cols, rows, label);
  return { rgba, integrity: digest === null ? "unchecked" : "sha256" };
}

function toGrid(g: ManifestGrid): RasterGrid {
  return {
    product: g.product,
    rows: g.shape_rows_columns[0],
    cols: g.shape_rows_columns[1],
    transform: g.transform,
    bounds: g.bounds_west_south_east_north,
  };
}

function bad(label: string, what: string, index: number, cols: number): Error {
  return new Error(`${label} failed validation: ${what} at row ${Math.floor(index / cols)}, column ${index % cols}.`);
}

function extractHansen(rgba: Uint8ClampedArray, grid: RasterGrid): HansenRaster {
  const n = grid.rows * grid.cols;
  const lossyear = new Uint8Array(n);
  const datamask = new Uint8Array(n);
  const treecover = new Uint8Array(n);
  for (let i = 0, p = 0; i < n; i++, p += 4) {
    const r = rgba[p], g = rgba[p + 1], b = rgba[p + 2], a = rgba[p + 3];
    if (r > 25) throw bad("Hansen display raster", `lossyear ${r} > 25`, i, grid.cols);
    if (g > 2) throw bad("Hansen display raster", `datamask ${g} not in {0,1,2}`, i, grid.cols);
    if (b > 100) throw bad("Hansen display raster", `treecover ${b} > 100`, i, grid.cols);
    if (a !== 255) throw bad("Hansen display raster", `alpha ${a} != 255`, i, grid.cols);
    lossyear[i] = r;
    datamask[i] = g;
    treecover[i] = b;
  }
  return { ...grid, lossyear, datamask, treecover };
}

function extractJrc(rgba: Uint8ClampedArray, grid: RasterGrid): JrcRaster {
  const n = grid.rows * grid.cols;
  const klass = new Uint8Array(n);
  for (let i = 0, p = 0; i < n; i++, p += 4) {
    const r = rgba[p], g = rgba[p + 1], a = rgba[p + 3];
    if (r > 1) throw bad("JRC display raster", `class ${r} not in {0,1}`, i, grid.cols);
    if (g !== 255) throw bad("JRC display raster", `validity ${g} != 255`, i, grid.cols);
    if (a !== 255) throw bad("JRC display raster", `alpha ${a} != 255`, i, grid.cols);
    klass[i] = r;
  }
  return { ...grid, klass };
}

function countYearlyLoss(h: HansenRaster): number[] {
  const out = new Array<number>(YEAR_COUNT).fill(0);
  for (let i = 0; i < h.lossyear.length; i++) {
    const y = h.lossyear[i];
    if (y >= 1 && h.datamask[i] === 1) out[y - 1]++;
  }
  return out;
}

/* ------------------------------------------------- shared module-level store */

let store: RegionRaster = { status: "loading", yearlyLossPixels: null, data: null, chipBounds: null };
const listeners = new Set<() => void>();
function publish(next: RegionRaster) {
  store = next;
  listeners.forEach((l) => l());
}
let inflight: Promise<void> | null = null;

async function load(): Promise<void> {
  const res = await fetch(BASE + "manifest.json");
  if (!res.ok) throw new Error(`Region manifest returned HTTP ${res.status}.`);
  const manifest = (await res.json()) as { schema_version?: string; hansen?: unknown; jrc?: unknown };
  if (manifest.schema_version !== "plotline.region-display.v1") throw new Error("Unsupported region manifest schema.");
  const hg = parseGrid("hansen", manifest.hansen);
  const jg = parseGrid("jrc", manifest.jrc);
  const hansenGrid = toGrid(hg);
  publish({ ...store, status: "loading", chipBounds: hansenGrid.bounds });
  const [h, j] = await Promise.all([fetchPng(hg, "Hansen display raster"), fetchPng(jg, "JRC display raster")]);
  const hansen = extractHansen(h.rgba, hansenGrid);
  const jrc = extractJrc(j.rgba, toGrid(jg));
  publish({
    status: "ready",
    yearlyLossPixels: countYearlyLoss(hansen),
    data: { hansen, jrc, integrity: { hansen: h.integrity, jrc: j.integrity } },
    chipBounds: hansenGrid.bounds,
  });
}

function ensureLoaded(): void {
  if (inflight) return;
  publish({ status: "loading", yearlyLossPixels: null, data: null, chipBounds: store.chipBounds });
  inflight = load().catch((err: unknown) => {
    // Cache nothing on failure: the next mount retries. Never fall back to an altered raster.
    publish({
      status: "unavailable",
      error: err instanceof Error ? err.message : String(err),
      yearlyLossPixels: null,
      data: null,
      chipBounds: store.chipBounds,
    });
    inflight = null;
  });
}

const subscribe = (l: () => void) => {
  listeners.add(l);
  return () => listeners.delete(l);
};
const snapshot = () => store;

/** Shared by every caller: one fetch/decode per page load, retried on the next mount after a failure. */
export function useRegionRaster(): RegionRaster {
  useEffect(() => {
    if (store.status !== "ready") ensureLoaded();
  }, []);
  return useSyncExternalStore(subscribe, snapshot, snapshot);
}

/* ------------------------------------------------------------- lookups */

export type GridCell = { row: number; col: number };

/** Row/column of the cell containing (lon, lat) on the raster's own grid, or null when outside it. */
export function cellAt(grid: RasterGrid, lon: number, lat: number): GridCell | null {
  const [a, , c, , e, f] = grid.transform;
  const col = Math.floor((lon - c) / a);
  const row = Math.floor((lat - f) / e);
  return col >= 0 && col < grid.cols && row >= 0 && row < grid.rows ? { row, col } : null;
}

export type HansenSample = GridCell & { treecover: number; lossyear: number; datamask: number };
export function sampleHansen(h: HansenRaster, lon: number, lat: number): HansenSample | null {
  const cell = cellAt(h, lon, lat);
  if (!cell) return null;
  const i = cell.row * h.cols + cell.col;
  return { ...cell, treecover: h.treecover[i], lossyear: h.lossyear[i], datamask: h.datamask[i] };
}
export type JrcSample = GridCell & { klass: number };
export function sampleJrc(j: JrcRaster, lon: number, lat: number): JrcSample | null {
  const cell = cellAt(j, lon, lat);
  return cell ? { ...cell, klass: j.klass[cell.row * j.cols + cell.col] } : null;
}

/* --------------------------------------------------------------- painting */

type RGB = readonly [number, number, number];
export type Palette = {
  canopy0: RGB; canopy100: RGB; loss: RGB; lossPast: RGB; water: RGB; forest: RGB; nodata: RGB; land: RGB;
};
const FALLBACK: Palette = {
  canopy0: [0x0b, 0x17, 0x13], canopy100: [0x2c, 0x7a, 0x52], loss: [0xff, 0x7a, 0x3d], lossPast: [0x9a, 0x4b, 0x2c],
  water: [0x1c, 0x4a, 0x66], forest: [0x6f, 0xe3, 0xa0], nodata: [0x33, 0x41, 0x3b], land: [0x2a, 0x3a, 0x33],
};

function parseColor(text: string, fallback: RGB): RGB {
  const s = text.trim();
  let m = /^#([0-9a-f]{3}|[0-9a-f]{6})$/i.exec(s);
  if (m) {
    const h = m[1].length === 3 ? Array.from(m[1], (c) => c + c).join("") : m[1];
    return [parseInt(h.slice(0, 2), 16), parseInt(h.slice(2, 4), 16), parseInt(h.slice(4, 6), 16)];
  }
  m = /^rgba?\(\s*([\d.]+)[\s,]+([\d.]+)[\s,]+([\d.]+)/i.exec(s);
  if (m) return [Math.round(+m[1]), Math.round(+m[2]), Math.round(+m[3])];
  return fallback;
}

/** Read the live token colours (so theme switches repaint with the right hues). */
export function readPalette(root: Element = document.documentElement): Palette {
  const cs = getComputedStyle(root);
  const get = (name: string, fb: RGB) => parseColor(cs.getPropertyValue(name), fb);
  return {
    canopy0: get("--pl-canopy-0", FALLBACK.canopy0),
    canopy100: get("--pl-canopy-100", FALLBACK.canopy100),
    loss: get("--pl-loss", FALLBACK.loss),
    lossPast: get("--pl-loss-past", FALLBACK.lossPast),
    water: get("--pl-water", FALLBACK.water),
    forest: get("--pl-forest", FALLBACK.forest),
    nodata: FALLBACK.nodata,
    land: FALLBACK.land,
  };
}

const LITTLE_ENDIAN = new Uint8Array(new Uint32Array([0x01020304]).buffer)[0] === 4;
const pack = (c: RGB, a = 255): number =>
  (LITTLE_ENDIAN ? ((a << 24) | (c[2] << 16) | (c[1] << 8) | c[0]) : ((c[0] << 24) | (c[1] << 16) | (c[2] << 8) | a)) >>> 0;
const mix = (a: RGB, b: RGB, t: number): RGB => [
  Math.round(a[0] + (b[0] - a[0]) * t), Math.round(a[1] + (b[1] - a[1]) * t), Math.round(a[2] + (b[2] - a[2]) * t),
];

/** Canopy colour for a treecover percentage (0..100); `dim` pulls it toward canopy-0. */
export function canopyColor(p: Palette, pct: number, dim = 0): RGB {
  const ramp = mix(p.canopy0, p.canopy100, Math.min(100, Math.max(0, pct)) / 100);
  return dim ? mix(p.canopy0, ramp, 1 - dim) : ramp;
}
export function rgbCss(c: RGB, alpha = 1): string {
  return alpha >= 1 ? `rgb(${c[0]} ${c[1]} ${c[2]})` : `rgb(${c[0]} ${c[1]} ${c[2]} / ${alpha})`;
}

const imageCache = new WeakMap<HTMLCanvasElement, ImageData>();
function targetPixels(canvas: HTMLCanvasElement, cols: number, rows: number): { ctx: CanvasRenderingContext2D; img: ImageData; out: Uint32Array } {
  if (canvas.width !== cols || canvas.height !== rows) {
    canvas.width = cols;
    canvas.height = rows;
  }
  const ctx = canvas.getContext("2d");
  if (!ctx) throw new Error("Canvas 2D is unavailable.");
  let img = imageCache.get(canvas);
  if (!img || img.width !== cols || img.height !== rows) {
    img = ctx.createImageData(cols, rows);
    imageCache.set(canvas, img);
  }
  return { ctx, img, out: new Uint32Array(img.data.buffer) };
}

/** Dimming applied to the canopy base in loss mode so loss pixels stand out. */
const LOSS_BASE_DIM = 0.35;

/**
 * Paint the Hansen display raster at native resolution into `canvas`.
 * loss: dimmed canopy base; loss before `year` rust, loss in `year` ember, later loss not yet drawn.
 */
export function paintHansen(canvas: HTMLCanvasElement, h: HansenRaster, mode: MapMode, year: number, p: Palette): void {
  const { ctx, img, out } = targetPixels(canvas, h.cols, h.rows);
  const water = pack(p.water), nodata = pack(p.nodata), land = pack(p.land);
  const lossC = pack(p.loss), pastC = pack(p.lossPast);
  const dim = mode === "loss" ? LOSS_BASE_DIM : 0;
  const lut = new Uint32Array(101);
  for (let t = 0; t <= 100; t++) lut[t] = pack(canopyColor(p, t, dim));
  const { lossyear, datamask, treecover } = h;
  const n = out.length;
  const sel = year - 2000;
  if (mode === "mask") {
    for (let i = 0; i < n; i++) out[i] = datamask[i] === 1 ? land : datamask[i] === 2 ? water : nodata;
  } else if (mode === "canopy") {
    for (let i = 0; i < n; i++) out[i] = datamask[i] === 1 ? lut[treecover[i]] : datamask[i] === 2 ? water : nodata;
  } else {
    for (let i = 0; i < n; i++) {
      const m = datamask[i];
      if (m === 1) {
        const l = lossyear[i];
        out[i] = l === 0 || l > sel ? lut[treecover[i]] : l === sel ? lossC : pastC;
      } else out[i] = m === 2 ? water : nodata;
    }
  }
  ctx.putImageData(img, 0, 0);
}

/** Paint the JRC forest overlay: class 1 mint at about half alpha, class 0 (valid Non-forest) transparent. */
export function paintJrc(canvas: HTMLCanvasElement, j: JrcRaster, p: Palette): void {
  const { ctx, img, out } = targetPixels(canvas, j.cols, j.rows);
  const forest = pack(p.forest, 128);
  const k = j.klass;
  for (let i = 0; i < out.length; i++) out[i] = k[i] === 1 ? forest : 0;
  ctx.putImageData(img, 0, 0);
}
