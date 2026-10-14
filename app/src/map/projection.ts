/*
 * Equirectangular map camera for the Plotline map stage (display only).
 *
 * Longitude is scaled by cos(mid-latitude of the Hansen chip) so that one native
 * cell (0.00025 deg x 0.00025 deg, about 28 m) is almost square on screen. This
 * is the same convention the original SVG projector used. The projection never
 * changes plot geometry or query coordinates; it only places them on screen.
 */

export type Bounds = readonly [west: number, south: number, east: number, north: number];
export type Camera = { lon: number; lat: number; pxPerDeg: number };
export type Viewport = { width: number; height: number };

/** Hansen chip latitude range 8.431 to 8.582 N, so the mid-latitude is 8.5065 N. */
export const CHIP_MID_LAT = (8.431 + 8.582) / 2;
export const COS_LAT = Math.cos((CHIP_MID_LAT * Math.PI) / 180);
/** Native Hansen cell size in degrees. */
export const HANSEN_CELL_DEG = 0.00025;
/** Zoom limit: one Hansen cell is 80 css px tall. */
export const MAX_PX_PER_DEG = 80 / HANSEN_CELL_DEG;

export function project(cam: Camera, vp: Viewport, lon: number, lat: number): [number, number] {
  return [
    vp.width / 2 + (lon - cam.lon) * cam.pxPerDeg * COS_LAT,
    vp.height / 2 - (lat - cam.lat) * cam.pxPerDeg,
  ];
}

export function unproject(cam: Camera, vp: Viewport, x: number, y: number): [number, number] {
  return [
    cam.lon + (x - vp.width / 2) / (cam.pxPerDeg * COS_LAT),
    cam.lat - (y - vp.height / 2) / cam.pxPerDeg,
  ];
}

/** Screen size in css px of one native cell at this camera (height). */
export function cellPx(cam: Camera, cellDeg = HANSEN_CELL_DEG): number {
  return cellDeg * cam.pxPerDeg;
}

export function boundsOfRings(rings: readonly (readonly (readonly number[])[])[]): Bounds {
  let w = Infinity, s = Infinity, e = -Infinity, n = -Infinity;
  for (const ring of rings)
    for (const p of ring) {
      if (p[0] < w) w = p[0];
      if (p[0] > e) e = p[0];
      if (p[1] < s) s = p[1];
      if (p[1] > n) n = p[1];
    }
  return [w, s, e, n];
}

export function unionBounds(list: readonly Bounds[]): Bounds | null {
  if (!list.length) return null;
  let [w, s, e, n] = list[0];
  for (const b of list) {
    if (b[0] < w) w = b[0];
    if (b[1] < s) s = b[1];
    if (b[2] > e) e = b[2];
    if (b[3] > n) n = b[3];
  }
  return [w, s, e, n];
}

/** Fit `bounds` inside the viewport with a fixed pixel padding on every side. */
export function fitBounds(bounds: Bounds, viewportW: number, viewportH: number, paddingPx = 0): Camera {
  const bw = Math.max((bounds[2] - bounds[0]) * COS_LAT, 1e-9);
  const bh = Math.max(bounds[3] - bounds[1], 1e-9);
  const aw = Math.max(viewportW - 2 * paddingPx, 1);
  const ah = Math.max(viewportH - 2 * paddingPx, 1);
  return {
    lon: (bounds[0] + bounds[2]) / 2,
    lat: (bounds[1] + bounds[3]) / 2,
    pxPerDeg: Math.min(aw / bw, ah / bh),
  };
}

/** Fit `bounds` so that it fills at most `fill` (0..1) of each viewport dimension. */
export function fitBoundsFill(bounds: Bounds, viewportW: number, viewportH: number, fill = 0.6): Camera {
  const bw = Math.max((bounds[2] - bounds[0]) * COS_LAT, 1e-9);
  const bh = Math.max(bounds[3] - bounds[1], 1e-9);
  return {
    lon: (bounds[0] + bounds[2]) / 2,
    lat: (bounds[1] + bounds[3]) / 2,
    pxPerDeg: Math.min((viewportW * fill) / bw, (viewportH * fill) / bh),
  };
}

export const clamp = (v: number, lo: number, hi: number) => Math.min(hi, Math.max(lo, v));

/** Keep the zoom inside [minPx, maxPx] and the centre inside `region`. */
export function clampCamera(cam: Camera, region: Bounds | null, minPx: number, maxPx: number): Camera {
  const pxPerDeg = clamp(cam.pxPerDeg, minPx, Math.max(minPx, maxPx));
  return region
    ? { pxPerDeg, lon: clamp(cam.lon, region[0], region[2]), lat: clamp(cam.lat, region[1], region[3]) }
    : { ...cam, pxPerDeg };
}

/** Zoom by `factor` keeping the geographic point under screen position (x, y) fixed. */
export function zoomAt(cam: Camera, vp: Viewport, x: number, y: number, factor: number, minPx: number, maxPx: number): Camera {
  const pxPerDeg = clamp(cam.pxPerDeg * factor, minPx, Math.max(minPx, maxPx));
  const [lon, lat] = unproject(cam, vp, x, y);
  return {
    pxPerDeg,
    lon: lon - (x - vp.width / 2) / (pxPerDeg * COS_LAT),
    lat: lat + (y - vp.height / 2) / pxPerDeg,
  };
}

/** Move the camera so the map follows a drag of (dx, dy) screen pixels. */
export function panBy(cam: Camera, dx: number, dy: number): Camera {
  return { ...cam, lon: cam.lon - dx / (cam.pxPerDeg * COS_LAT), lat: cam.lat + dy / cam.pxPerDeg };
}

export const easeInOutCubic = (t: number) => (t < 0.5 ? 4 * t * t * t : 1 - Math.pow(-2 * t + 2, 3) / 2);

/**
 * Fraction of the centre travel completed at time t for a zoom from z0 to z1.
 * Zooming in uses a schedule that keeps the destination's screen offset shrinking
 * linearly (it never leaves the screen). Zooming out is the same flight reversed.
 */
function centerFraction(z0: number, z1: number, t: number): number {
  if (Math.abs(Math.log(z1 / z0)) < 1e-6) return t;
  if (z1 > z0) return 1 - (1 - t) * Math.pow(z0 / z1, t);
  return t * Math.pow(z1 / z0, 1 - t);
}

/** Interpolate cameras: zoom geometrically, centre along the schedule above. */
export function lerpCamera(a: Camera, b: Camera, t: number): Camera {
  if (t <= 0) return a;
  if (t >= 1) return b;
  const pxPerDeg = a.pxPerDeg * Math.pow(b.pxPerDeg / a.pxPerDeg, t);
  const u = centerFraction(a.pxPerDeg, b.pxPerDeg, t);
  return { pxPerDeg, lon: a.lon + (b.lon - a.lon) * u, lat: a.lat + (b.lat - a.lat) * u };
}

export function sameCamera(a: Camera, b: Camera, eps = 1e-9): boolean {
  return Math.abs(a.lon - b.lon) < eps && Math.abs(a.lat - b.lat) < eps && Math.abs(a.pxPerDeg / b.pxPerDeg - 1) < 1e-6;
}

/**
 * Animate between two cameras on requestAnimationFrame. Returns a cancel function.
 * `onFrame` runs for every frame including the final one; `onDone` after the last.
 */
export function tweenCamera(
  from: Camera,
  to: Camera,
  durationMs: number,
  onFrame: (cam: Camera) => void,
  onDone?: () => void,
  ease: (t: number) => number = easeInOutCubic,
): () => void {
  let raf = 0;
  let live = true;
  const start = performance.now();
  const step = (now: number) => {
    if (!live) return;
    const t = durationMs <= 0 ? 1 : Math.min(1, (now - start) / durationMs);
    onFrame(lerpCamera(from, to, ease(t)));
    if (t < 1) raf = requestAnimationFrame(step);
    else onDone?.();
  };
  raf = requestAnimationFrame(step);
  return () => {
    live = false;
    cancelAnimationFrame(raf);
  };
}
