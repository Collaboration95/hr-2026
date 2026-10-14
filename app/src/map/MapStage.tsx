import "../styles/map.css";
import { useCallback, useEffect, useId, useLayoutEffect, useMemo, useRef, useState, useSyncExternalStore } from "react";
import type * as React from "react";
import type { Cell, Plot } from "../types";
import { availableBand, canopyLabel, isYearEvent, lossLabel, maskLabel } from "../cell-values";
import { Chip, Glyph, Icon } from "../components/Primitives";
import {
  paintHansen, paintJrc, readPalette, sampleHansen, sampleJrc, useRegionRaster,
  type HansenSample, type JrcSample, type RasterGrid,
} from "./region-raster";
import {
  MAX_PX_PER_DEG, boundsOfRings, cellPx, clampCamera, fitBounds, fitBoundsFill, panBy, project, sameCamera,
  tweenCamera, unionBounds, unproject, zoomAt,
  type Bounds, type Camera, type Viewport,
} from "./projection";

export type MapLayer = "loss" | "canopy" | "mask";
export type MapStageProps = {
  plots: Plot[];
  selectedPlotId: string | null;
  year: number;
  layer: MapLayer;
  onLayerChange: (l: MapLayer) => void;
  showJrc: boolean;
  onShowJrcChange: (v: boolean) => void;
  onSelectPlot: (id: string | null) => void;
  pinnedCell: Cell | null;
  onPinCell: (c: Cell | null) => void;
};

/* ------------------------------------------------------------------ geometry */

type PlotShape = { id: string; plot: Plot; rings: number[][][]; bounds: Bounds; centroid: [number, number] };
type CellShape = { cell: Cell; key: string; ring: number[][]; bounds: Bounds; center: [number, number] };

function centroidOf(ring: number[][], b: Bounds): [number, number] {
  let a = 0, cx = 0, cy = 0;
  for (let i = 0; i < ring.length; i++) {
    const [x0, y0] = ring[i];
    const [x1, y1] = ring[(i + 1) % ring.length];
    const k = x0 * y1 - x1 * y0;
    a += k; cx += (x0 + x1) * k; cy += (y0 + y1) * k;
  }
  return Math.abs(a) < 1e-18 ? [(b[0] + b[2]) / 2, (b[1] + b[3]) / 2] : [cx / (3 * a), cy / (3 * a)];
}

function pathD(rings: readonly (readonly number[][])[], cam: Camera, vp: Viewport): string {
  let d = "";
  for (const ring of rings) {
    for (let i = 0; i < ring.length; i++) {
      const [x, y] = project(cam, vp, ring[i][0], ring[i][1]);
      d += `${i ? "L" : "M"}${x.toFixed(1)} ${y.toFixed(1)}`;
    }
    d += "Z";
  }
  return d;
}

const cellKey = (c: Cell) => `${c.properties.row}:${c.properties.col}`;
const fmtCoord = (v: number) => v.toFixed(5);

/** Greedy label placement: higher priority first; labels never overlap a marker or an earlier label. */
function placeLabels(items: { id: string; x: number; y: number; priority: number }[], width: number): Map<string, "right" | "left"> {
  const taken: { x: number; y: number; w: number; h: number }[] = items.map((i) => ({ x: i.x - 6, y: i.y - 6, w: 12, h: 12 }));
  const out = new Map<string, "right" | "left">();
  const free = (r: { x: number; y: number; w: number; h: number }) =>
    taken.every((t) => r.x >= t.x + t.w || r.x + r.w <= t.x || r.y >= t.y + t.h || r.y + r.h <= t.y);
  for (const it of [...items].sort((a, b) => b.priority - a.priority)) {
    const w = it.id.length * 6.8 + 6;
    const right = { x: it.x + 8, y: it.y - 8, w, h: 16 };
    const left = { x: it.x - 8 - w, y: it.y - 8, w, h: 16 };
    const tryOrder = it.x + 8 + w > width ? [left, right] : [right, left];
    for (const r of tryOrder) {
      if (r.x < 0 || r.x + r.w > width || !free(r)) continue;
      taken.push(r);
      out.set(it.id, r === right ? "right" : "left");
      break;
    }
  }
  return out;
}

/* ---------------------------------------------------------------- environment */

function cameraMs(): number {
  if (typeof window === "undefined") return 0;
  if (window.matchMedia?.("(prefers-reduced-motion: reduce)").matches) return 0;
  const raw = getComputedStyle(document.documentElement).getPropertyValue("--pl-slow").trim();
  const v = parseFloat(raw);
  if (!Number.isFinite(v)) return 600;
  return raw.endsWith("ms") ? v : raw.endsWith("s") ? v * 1000 : v;
}

function subscribeTheme(cb: () => void) {
  const mo = new MutationObserver(cb);
  mo.observe(document.documentElement, { attributes: true, attributeFilter: ["data-theme", "class"] });
  return () => mo.disconnect();
}
const themeKey = () => document.documentElement.getAttribute("data-theme") ?? "";
function useThemeKey(): string {
  return useSyncExternalStore(subscribeTheme, themeKey, () => "");
}

/** Draw the visible part of a native-resolution layer into the viewport, snapped to source pixels. */
function drawLayer(ctx: CanvasRenderingContext2D, src: HTMLCanvasElement, grid: RasterGrid, cam: Camera, vp: Viewport, dpr: number) {
  const [x0, y0] = project(cam, vp, grid.bounds[0], grid.bounds[3]);
  const [x1, y1] = project(cam, vp, grid.bounds[2], grid.bounds[1]);
  const cw = (x1 - x0) / src.width;
  const ch = (y1 - y0) / src.height;
  if (!(cw > 0 && ch > 0)) return;
  const sx0 = Math.max(0, Math.floor(-x0 / cw));
  const sx1 = Math.min(src.width, Math.ceil((vp.width - x0) / cw));
  const sy0 = Math.max(0, Math.floor(-y0 / ch));
  const sy1 = Math.min(src.height, Math.ceil((vp.height - y0) / ch));
  if (sx1 <= sx0 || sy1 <= sy0) return;
  // Crisp native pixels when magnified. Minified past one device pixel per cell, average instead of dropping cells.
  ctx.imageSmoothingEnabled = cw * dpr < 1;
  ctx.imageSmoothingQuality = "high";
  ctx.drawImage(src, sx0, sy0, sx1 - sx0, sy1 - sy0, x0 + sx0 * cw, y0 + sy0 * ch, (sx1 - sx0) * cw, (sy1 - sy0) * ch);
}

/* ------------------------------------------------------------------ component */

type Hover = { x: number; y: number };

export default function MapStage({
  plots, selectedPlotId, year, layer, onLayerChange, showJrc, onShowJrcChange, onSelectPlot, pinnedCell, onPinCell,
}: MapStageProps) {
  const raster = useRegionRaster();
  const data = raster.data;
  const theme = useThemeKey();
  const hatchId = `pl-map-hatch-${useId().replace(/[^a-zA-Z0-9]/g, "")}`;

  const shapes = useMemo<PlotShape[]>(
    () =>
      plots.map((plot) => {
        const rings = plot.geometry.coordinates;
        const bounds = boundsOfRings(rings);
        return { id: plot.plot_id, plot, rings, bounds, centroid: centroidOf(rings[0] ?? [], bounds) };
      }),
    [plots],
  );
  const selected = useMemo(() => shapes.find((s) => s.id === selectedPlotId) ?? null, [shapes, selectedPlotId]);
  const features = selected?.plot.evidence?.features ?? null;
  const cellShapes = useMemo<CellShape[] | null>(
    () =>
      features
        ? features.map((cell) => {
            const ring = cell.geometry.coordinates[0] ?? [];
            const bounds = boundsOfRings([ring]);
            const c = cell.properties.center;
            const center: [number, number] =
              Array.isArray(c) && Number.isFinite(c[0]) && Number.isFinite(c[1]) ? [c[0], c[1]] : [(bounds[0] + bounds[2]) / 2, (bounds[1] + bounds[3]) / 2];
            return { cell, key: cellKey(cell), ring, bounds, center };
          })
        : null,
    [features],
  );
  const cellFlags = useMemo(
    () =>
      cellShapes?.map(({ cell }) => ({
        event: isYearEvent(cell, year),
        unknown: !cell.properties.valid_land || availableBand(cell, 0) == null || availableBand(cell, 1) == null || availableBand(cell, 2) == null,
      })) ?? null,
    [cellShapes, year],
  );

  /* ---- viewport size ---- */
  const viewportRef = useRef<HTMLDivElement>(null);
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const [vp, setVp] = useState<Viewport>({ width: 0, height: 0 });
  useLayoutEffect(() => {
    const el = viewportRef.current;
    if (!el) return;
    const measure = () => {
      const r = el.getBoundingClientRect();
      const width = Math.round(r.width), height = Math.round(r.height);
      setVp((p) => (p.width === width && p.height === height ? p : { width, height }));
    };
    measure();
    const ro = new ResizeObserver(measure);
    ro.observe(el);
    return () => ro.disconnect();
  }, []);
  const [dpr, setDpr] = useState(() => window.devicePixelRatio || 1);
  useEffect(() => {
    const onResize = () => setDpr(window.devicePixelRatio || 1);
    window.addEventListener("resize", onResize);
    return () => window.removeEventListener("resize", onResize);
  }, []);

  /* ---- camera targets ---- */
  const rasterBounds = raster.status === "unavailable" ? null : raster.chipBounds;
  // Wait for the manifest (a few ms) so the camera does not fit the plots first and then re-fit the chip.
  const awaitingBounds = raster.status === "loading" && !raster.chipBounds;
  const regionBounds = useMemo<Bounds | null>(() => rasterBounds ?? unionBounds(shapes.map((s) => s.bounds)), [rasterBounds, shapes]);
  const regionCam = useMemo(
    () => (regionBounds && vp.width > 0 && !awaitingBounds ? fitBounds(regionBounds, vp.width, vp.height, Math.min(64, vp.width * 0.1)) : null),
    [regionBounds, rasterBounds, awaitingBounds, vp],
  );
  const minPx = regionCam ? regionCam.pxPerDeg * 0.9 : 1;
  const plotCam = useMemo(() => {
    if (!selected || vp.width <= 0) return null;
    const fit = fitBoundsFill(selected.bounds, vp.width, vp.height, 0.6);
    return { ...fit, pxPerDeg: Math.min(fit.pxPerDeg, MAX_PX_PER_DEG) };
  }, [selected, vp]);
  const target = selected ? plotCam : regionCam;
  const targetKey = target ? `${selected?.id ?? "region"}|${vp.width}x${vp.height}|${regionBounds?.join(",") ?? ""}` : "";

  const [cam, setCam] = useState<Camera | null>(null);
  const camRef = useRef<Camera | null>(null);
  const tween = useRef<(() => void) | null>(null);
  const frame = useRef(0);
  const live = useRef({ vp, minPx, regionBounds });
  live.current = { vp, minPx, regionBounds };

  const stopTween = useCallback(() => {
    tween.current?.();
    tween.current = null;
  }, []);
  const apply = useCallback((c: Camera) => {
    camRef.current = c;
    setCam(c);
  }, []);
  /** User gestures: update the camera ref now, render at most once per animation frame. */
  const commit = useCallback((c: Camera) => {
    camRef.current = c;
    if (!frame.current)
      frame.current = requestAnimationFrame(() => {
        frame.current = 0;
        if (camRef.current) setCam(camRef.current);
      });
  }, []);
  const flyTo = useCallback((to: Camera, opts?: { instant?: boolean; ms?: number }) => {
    stopTween();
    const from = camRef.current;
    const ms = opts?.instant || !from ? 0 : (opts?.ms ?? cameraMs());
    if (!from || ms <= 0 || sameCamera(from, to)) {
      apply(to);
      return;
    }
    tween.current = tweenCamera(from, to, ms, apply, () => { tween.current = null; });
  }, [apply, stopTween]);
  useEffect(() => () => {
    stopTween();
    cancelAnimationFrame(frame.current);
  }, [stopTween]);

  const last = useRef<{ sel: string | null; w: number; h: number } | null>(null);
  useLayoutEffect(() => {
    if (!target) return;
    const prev = last.current;
    const sel = selected?.id ?? null;
    last.current = { sel, w: vp.width, h: vp.height };
    const resizedOnly = !!prev && prev.sel === sel && (prev.w !== vp.width || prev.h !== vp.height);
    flyTo(target, { instant: !prev || resizedOnly });
    // Re-run only when the destination changes, not on every render.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [targetKey]);

  /* ---- raster layers on the canvas ---- */
  const hansenLayer = useRef<HTMLCanvasElement | null>(null);
  const jrcLayer = useRef<HTMLCanvasElement | null>(null);
  const painted = useRef<{ hansen: string | null; jrc: string | null; data: unknown }>({ hansen: null, jrc: null, data: null });
  useLayoutEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas || vp.width < 1 || vp.height < 1) return;
    const W = Math.round(vp.width * dpr), H = Math.round(vp.height * dpr);
    if (canvas.width !== W || canvas.height !== H) {
      canvas.width = W;
      canvas.height = H;
    }
    const ctx = canvas.getContext("2d");
    if (!ctx) return;
    ctx.setTransform(1, 0, 0, 1, 0, 0);
    ctx.clearRect(0, 0, W, H);
    if (!cam || !data) return;
    if (painted.current.data !== data) painted.current = { hansen: null, jrc: null, data };
    const hKey = `${layer}|${layer === "loss" ? year : 0}|${theme}`;
    let palette: ReturnType<typeof readPalette> | null = null;
    if (!hansenLayer.current) hansenLayer.current = document.createElement("canvas");
    if (painted.current.hansen !== hKey) {
      const t0 = performance.now();
      palette = readPalette();
      paintHansen(hansenLayer.current, data.hansen, layer, year, palette);
      painted.current.hansen = hKey;
      canvas.dataset.paintMs = (performance.now() - t0).toFixed(1);
    }
    if (showJrc) {
      if (!jrcLayer.current) jrcLayer.current = document.createElement("canvas");
      if (painted.current.jrc !== theme) {
        paintJrc(jrcLayer.current, data.jrc, palette ?? readPalette());
        painted.current.jrc = theme;
      }
    }
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    drawLayer(ctx, hansenLayer.current, data.hansen, cam, vp, dpr);
    if (showJrc && jrcLayer.current) drawLayer(ctx, jrcLayer.current, data.jrc, cam, vp, dpr);
  }, [cam, vp, dpr, data, layer, year, showJrc, theme]);

  /* ---- gestures: wheel zoom, drag pan, double-click zoom ---- */
  const [dragging, setDragging] = useState(false);
  const drag = useRef<{ id: number; x: number; y: number; cam: Camera; active: boolean } | null>(null);
  useEffect(() => {
    const el = viewportRef.current;
    if (!el) return;
    const onWheel = (e: WheelEvent) => {
      const c = camRef.current;
      if (!c) return;
      e.preventDefault();
      stopTween();
      const { vp: v, minPx: lo, regionBounds: rb } = live.current;
      const r = el.getBoundingClientRect();
      const dy = e.deltaY * (e.deltaMode === 1 ? 16 : e.deltaMode === 2 ? 400 : 1);
      const factor = Math.exp(-dy * (e.ctrlKey ? 0.01 : 0.0016));
      commit(clampCamera(zoomAt(c, v, e.clientX - r.left, e.clientY - r.top, factor, lo, MAX_PX_PER_DEG), rb, lo, MAX_PX_PER_DEG));
    };
    el.addEventListener("wheel", onWheel, { passive: false });
    return () => el.removeEventListener("wheel", onWheel);
  }, [commit, stopTween]);

  const [hover, setHover] = useState<Hover | null>(null);
  const hoverRaw = useRef<Hover | null>(null);
  const hoverFrame = useRef(0);
  const clearHover = useCallback(() => {
    hoverRaw.current = null;
    cancelAnimationFrame(hoverFrame.current);
    hoverFrame.current = 0;
    setHover(null);
  }, []);
  useEffect(() => () => cancelAnimationFrame(hoverFrame.current), []);

  const onPointerDown = (e: React.PointerEvent<HTMLDivElement>) => {
    if (e.pointerType === "touch" || e.button !== 0 || !camRef.current) return;
    drag.current = { id: e.pointerId, x: e.clientX, y: e.clientY, cam: camRef.current, active: false };
  };
  const onPointerMove = (e: React.PointerEvent<HTMLDivElement>) => {
    const d = drag.current;
    if (d && d.id === e.pointerId) {
      const dx = e.clientX - d.x, dy = e.clientY - d.y;
      if (!d.active && Math.hypot(dx, dy) > 4) {
        d.active = true;
        stopTween();
        e.currentTarget.setPointerCapture(e.pointerId);
        setDragging(true);
        clearHover();
      }
      if (d.active) {
        const { minPx: lo, regionBounds: rb } = live.current;
        commit(clampCamera(panBy(d.cam, dx, dy), rb, lo, MAX_PX_PER_DEG));
        return;
      }
    }
    if (e.pointerType === "touch") return;
    const r = e.currentTarget.getBoundingClientRect();
    hoverRaw.current = { x: e.clientX - r.left, y: e.clientY - r.top };
    if (!hoverFrame.current)
      hoverFrame.current = requestAnimationFrame(() => {
        hoverFrame.current = 0;
        setHover(hoverRaw.current ? { ...hoverRaw.current } : null);
      });
  };
  const endDrag = (e: React.PointerEvent<HTMLDivElement>) => {
    if (drag.current?.id === e.pointerId) {
      drag.current = null;
      setDragging(false);
    }
  };
  const onDoubleClick = (e: React.MouseEvent<HTMLDivElement>) => {
    if ((e.target as Element).closest("[data-map-hit]") || !camRef.current) return;
    const { vp: v, minPx: lo, regionBounds: rb } = live.current;
    const r = e.currentTarget.getBoundingClientRect();
    const to = clampCamera(zoomAt(camRef.current, v, e.clientX - r.left, e.clientY - r.top, 2, lo, MAX_PX_PER_DEG), rb, lo, MAX_PX_PER_DEG);
    flyTo(to, { ms: cameraMs() > 0 ? 220 : 0 });
  };

  /* ---- derived read-outs ---- */
  const lonLat = hover && cam && !dragging ? unproject(cam, vp, hover.x, hover.y) : null;
  const samples = useMemo(() => {
    if (!lonLat || !data) return null;
    const hs = sampleHansen(data.hansen, lonLat[0], lonLat[1]);
    const js = showJrc ? sampleJrc(data.jrc, lonLat[0], lonLat[1]) : null;
    return { hs, js, jrcOn: showJrc };
  }, [lonLat?.[0], lonLat?.[1], data, showJrc]); // eslint-disable-line react-hooks/exhaustive-deps

  const pinned = useMemo(() => {
    if (!pinnedCell || !cellShapes) return null;
    return cellShapes.find((c) => c.key === cellKey(pinnedCell)) ?? null;
  }, [pinnedCell, cellShapes]);

  // Legend starts open on a roomy stage and collapsed on a narrow one, until the user chooses.
  const [legendChoice, setLegendChoice] = useState<boolean | null>(null);
  // In plot view the legend would cover the plot, so it starts collapsed there.
  const legendOpen = legendChoice ?? (vp.width >= 740 && !selected);
  const ariaLabel = selected
    ? cellShapes
      ? `Map: ${selected.id} exact boundary and ${cellShapes.length} native cell footprints`
      : `Map: ${selected.id} exact boundary; native cells not computed`
    : `Map: all ${plots.length} supplied plots`;

  const rasterDown = raster.status === "unavailable";
  const fitRegion = () => {
    onSelectPlot(null);
    if (regionCam) flyTo(regionCam);
  };

  return (
    <section className={`pl-map${legendOpen ? " is-legend-open" : ""}`} aria-label={ariaLabel} data-raster={raster.status} data-layer={layer} data-jrc={showJrc && !!data ? "true" : undefined}>
      <div className="pl-map__body">
        <div
          ref={viewportRef}
          className="pl-map__viewport"
          data-dragging={dragging || undefined}
          onPointerDown={onPointerDown}
          onPointerMove={onPointerMove}
          onPointerUp={endDrag}
          onPointerCancel={endDrag}
          onPointerLeave={() => { if (!drag.current?.active) clearHover(); }}
          onDoubleClick={onDoubleClick}
        >
          <canvas ref={canvasRef} className="pl-map__canvas" aria-hidden="true" />
          {cam && vp.width > 0 && (
            <svg className="pl-map__svg" width={vp.width} height={vp.height} viewBox={`0 0 ${vp.width} ${vp.height}`} role="group" aria-label="Plot outlines and native cells" focusable="false">
              <defs>
                <pattern id={hatchId} width="6" height="6" patternUnits="userSpaceOnUse" patternTransform="rotate(45)">
                  <rect width="6" height="6" style={{ fill: "var(--pl-void)", fillOpacity: 0.55 }} />
                  <path d="M0 3H6" style={{ stroke: "var(--pl-unknown)", strokeWidth: 1.5 }} />
                </pattern>
              </defs>
              {!selected && <Graticule cam={cam} vp={vp} bounds={regionBounds} legendOpen={legendOpen} />}
              <PlotsLayer shapes={shapes} selectedId={selected?.id ?? null} cam={cam} vp={vp} onSelect={onSelectPlot} />
              {selected && cellShapes && cellFlags && (
                <CellsLayer cells={cellShapes} flags={cellFlags} cam={cam} vp={vp} pinnedKey={pinned?.key ?? null} hatchId={hatchId} onPin={onPinCell} />
              )}
              {selected && (
                <g className="pl-map__boundary" aria-hidden="true">
                  <path className="pl-map__halo" d={pathD(selected.rings, cam, vp)} />
                  <path className="pl-map__outline is-selected" d={pathD(selected.rings, cam, vp)} />
                </g>
              )}
              {pinned && <PinRing cell={pinned} cam={cam} vp={vp} />}
            </svg>
          )}
        </div>

        {samples && hover && lonLat && (
          <HoverTip x={hover.x} y={hover.y} vp={vp} samples={samples} />
        )}

        <div className="pl-map__controls pl-map__controls--left">
          <div className="pl-segmented" role="group" aria-label="Map layer">
            {([["loss", "Loss"], ["canopy", "Canopy 2000"], ["mask", "Land mask"]] as const).map(([id, name]) => (
              <button key={id} type="button" aria-pressed={layer === id} disabled={rasterDown} title={rasterDown ? "Display raster unavailable" : undefined} onClick={() => onLayerChange(id)}>{name}</button>
            ))}
          </div>
          <button type="button" className="pl-btn pl-btn--sm pl-map__toggle" aria-pressed={showJrc} disabled={rasterDown} title={rasterDown ? "Display raster unavailable" : undefined} onClick={() => onShowJrcChange(!showJrc)}>
            <Glyph kind="forest" />JRC 2020 forest
          </button>
        </div>

        <div className="pl-map__right">
          <div className="pl-map__controls pl-map__controls--right">
            <button type="button" className="pl-btn pl-btn--sm" onClick={fitRegion}><Icon name="map" size={14} />Region</button>
            {selected && plotCam && (
              <button type="button" className="pl-btn pl-btn--sm" onClick={() => flyTo(plotCam)}><Icon name="target" size={14} />Fit plot</button>
            )}
          </div>
          {selected && !cellShapes && (
            <div className="pl-map__float-chip"><Chip tone="unknown" title="plot.evidence is null for this plot, so only the exact boundary is drawn.">Native cells not computed</Chip></div>
          )}
          {pinned && <PinnedCard cell={pinned.cell} onClose={() => onPinCell(null)} />}
        </div>

        <Legend open={legendOpen} onToggle={() => setLegendChoice(!legendOpen)} layer={layer} year={year} showJrc={showJrc && !!data} raster={raster.status !== "unavailable"} plotView={!!selected} cells={!!cellShapes} />

        <div className="pl-map__float pl-map__coords">
          <span className="pl-map__ll pl-num" aria-live="off">
            {lonLat ? `${fmtCoord(lonLat[0])}°E  ${fmtCoord(lonLat[1])}°N` : "Cursor: —"}
          </span>
          <span>EPSG:4326 · cell ≈ 28 m</span>
        </div>
      </div>

      <footer className="pl-map__foot">
        <span>Rendered from the source rasters, not imagery. Counts come from the verified export.</span>
        {raster.status === "loading" && (
          <span className="pl-chip pl-map__status" role="status"><span className="pl-spinner" aria-hidden="true" />Loading display raster…</span>
        )}
        {raster.status === "unavailable" && (
          <span className="pl-chip pl-chip--error pl-map__status" role="status" title={raster.error}>Display raster unavailable · vector view</span>
        )}
      </footer>
    </section>
  );
}

/* ------------------------------------------------------------------ overlays */

/** Geographic context beyond the source chip, using the raster's display camera. */
function Graticule({ cam, vp, bounds, legendOpen }: { cam: Camera; vp: Viewport; bounds: Bounds | null; legendOpen: boolean }) {
  const [west, north] = unproject(cam, vp, 0, 0);
  const [east, south] = unproject(cam, vp, vp.width, vp.height);
  const target = (east - west) * 140 / vp.width;
  const magnitude = 10 ** Math.floor(Math.log10(target));
  const interval = [1, 2, 5, 10].find((n) => n * magnitude >= target)! * magnitude;
  const decimals = Math.max(0, -Math.floor(Math.log10(interval)));
  // Reserve the top controls and bottom legend/read-out; label only clear void.
  const chipTop = bounds ? project(cam, vp, bounds[0], bounds[3])[1] : 0;
  const chipBottom = bounds ? project(cam, vp, bounds[0], bounds[1])[1] : vp.height;
  const longitudeY = chipTop >= 122 ? Math.min(chipTop - 12, vp.height - 76)
    : chipBottom <= vp.height - 100 ? Math.max(110, chipBottom + 18) : null;
  const meridians: { value: number; x: number }[] = [];
  const parallels: { value: number; y: number }[] = [];
  for (let value = Math.ceil(west / interval) * interval; value <= east; value += interval)
    meridians.push({ value, x: project(cam, vp, value, cam.lat)[0] });
  for (let value = Math.ceil(south / interval) * interval; value <= north; value += interval)
    parallels.push({ value, y: project(cam, vp, cam.lon, value)[1] });
  return (
    <g className="pl-map__graticule" aria-hidden="true">
      {meridians.map(({ value, x }) => (
        <g key={`lon-${value}`}>
          <line x1={x} x2={x} y1={0} y2={vp.height} />
          {longitudeY !== null && x > 48 && x < vp.width - 48 && <text x={x + 5} y={longitudeY}>{Math.abs(value).toFixed(decimals)}°{value < 0 ? "W" : "E"}</text>}
        </g>
      ))}
      {parallels.map(({ value, y }) => (
        <g key={`lat-${value}`}>
          <line x1={0} x2={vp.width} y1={y} y2={y} />
          {y > 105 && y < vp.height - (legendOpen ? 240 : 90) && <text x={8} y={y - 5}>{Math.abs(value).toFixed(decimals)}°{value < 0 ? "S" : "N"}</text>}
        </g>
      ))}
    </g>
  );
}

function PlotsLayer({ shapes, selectedId, cam, vp, onSelect }: {
  shapes: PlotShape[]; selectedId: string | null; cam: Camera; vp: Viewport; onSelect: (id: string) => void;
}) {
  const projected = shapes.map((s) => ({ s, c: project(cam, vp, s.centroid[0], s.centroid[1]) }));
  const labelSide = placeLabels(
    projected.filter((p) => p.s.id !== selectedId).map((p) => ({ id: p.s.id, x: p.c[0], y: p.c[1], priority: selectedId ? 0 : 1 })),
    vp.width,
  );
  return (
    <g className="pl-map__plots">
      {projected.filter((p) => p.s.id !== selectedId).map(({ s, c }) => {
        const d = pathD(s.rings, cam, vp);
        const side = labelSide.get(s.id);
        const select = () => onSelect(s.id);
        return (
          <g
            key={s.id}
            className={`pl-map__plot${selectedId ? " is-faint" : ""}`}
            role="button"
            tabIndex={selectedId ? -1 : 0}
            aria-label={`Select ${s.id} on map`}
            data-map-hit=""
            onClick={select}
            onKeyDown={(e) => {
              if (e.key === "Enter" || e.key === " ") {
                e.preventDefault();
                select();
              }
            }}
          >
            <circle className="pl-map__hit" cx={c[0]} cy={c[1]} r={12} />
            <circle className="pl-map__ring" cx={c[0]} cy={c[1]} r={14} />
            <path className="pl-map__halo" d={d} />
            <path className="pl-map__outline" d={d} />
            <circle className="pl-map__marker-halo" cx={c[0]} cy={c[1]} r={3.8} />
            <circle className="pl-map__marker" cx={c[0]} cy={c[1]} r={2.2} />
            <text
              className={`pl-map__label${side ? "" : " is-hidden"}`}
              x={side === "left" ? c[0] - 8 : c[0] + 8}
              y={c[1] + 4}
              textAnchor={side === "left" ? "end" : "start"}
            >
              {s.id}
            </text>
          </g>
        );
      })}
    </g>
  );
}

function CellsLayer({ cells, flags, cam, vp, pinnedKey, hatchId, onPin }: {
  cells: CellShape[]; flags: { event: boolean; unknown: boolean }[]; cam: Camera; vp: Viewport;
  pinnedKey: string | null; hatchId: string; onPin: (c: Cell | null) => void;
}) {
  const px = cellPx(cam);
  const margin = 24;
  const [west, north] = unproject(cam, vp, -margin, -margin);
  const [east, south] = unproject(cam, vp, vp.width + margin, vp.height + margin);
  const visible: { c: CellShape; f: { event: boolean; unknown: boolean } }[] = [];
  cells.forEach((c, i) => {
    const b = c.bounds;
    if (b[2] >= west && b[0] <= east && b[3] >= south && b[1] <= north) visible.push({ c, f: flags[i] });
  });
  const ordered = [...visible.filter((v) => !v.f.event), ...visible.filter((v) => v.f.event)];
  const showDots = px >= 10;
  return (
    <g className={`pl-map__cells${px < 4 ? " is-fine" : ""}`}>
      {ordered.map(({ c, f }) => (
        <path
          key={c.key}
          d={pathD([c.ring], cam, vp)}
          className={`native-cell${f.event ? " is-event" : ""}${f.unknown && !f.event ? " is-unknown" : ""}${c.key === pinnedKey ? " is-pinned" : ""}`}
          style={f.unknown && !f.event ? { fill: `url(#${hatchId})` } : undefined}
          data-event={f.event ? "true" : undefined}
          data-unknown={f.unknown && !f.event ? "true" : undefined}
          data-cell={c.key}
          data-map-hit=""
          role="button"
          tabIndex={-1}
          aria-label={`Native cell ${c.key}`}
          aria-pressed={c.key === pinnedKey}
          onClick={() => onPin(c.cell)}
          onKeyDown={(e) => {
            if (e.key === "Enter" || e.key === " ") {
              e.preventDefault();
              onPin(c.cell);
            }
          }}
        />
      ))}
      {showDots && (
        <g className="pl-map__dots" aria-hidden="true">
          {visible.map(({ c }) => {
            const [x, y] = project(cam, vp, c.center[0], c.center[1]);
            return <circle key={c.key} className="pl-map__dot" cx={x} cy={y} r={1.5} />;
          })}
        </g>
      )}
    </g>
  );
}

function PinRing({ cell, cam, vp }: { cell: CellShape; cam: Camera; vp: Viewport }) {
  const d = pathD([cell.ring], cam, vp);
  return (
    <g className="pl-map__pin" aria-hidden="true">
      <path className="pl-map__pin-halo" d={d} />
      <path className="pl-map__pin-ring" d={d} />
    </g>
  );
}

function PinnedCard({ cell, onClose }: { cell: Cell; onClose: () => void }) {
  const { row, col } = cell.properties;
  return (
    <aside
      className="pl-map__float pl-map__pinned"
      aria-label={`Pinned native cell ${row}:${col}`}
      onKeyDown={(e) => {
        if (e.key === "Escape") {
          e.stopPropagation();
          onClose();
        }
      }}
    >
      <header>
        <span className="pl-eyebrow">Native cell <span className="pl-num">{row}:{col}</span></span>
        <button type="button" className="pl-btn pl-btn--ghost pl-btn--sm pl-btn--icon" aria-label="Close cell details" onClick={onClose}>
          <Icon name="close" size={14} />
        </button>
      </header>
      <dl className="pl-dl">
        <div><dt>Canopy 2000</dt><dd>{canopyLabel(cell)}</dd></div>
        <div><dt>Loss year</dt><dd>{lossLabel(cell)}</dd></div>
        <div><dt>Land mask</dt><dd>{maskLabel(cell)}</dd></div>
      </dl>
      <p className="pl-fine">Exact values from the verified export.</p>
    </aside>
  );
}

const MASK_NAME = ["no data", "land", "water"];
function HoverTip({ x, y, vp, samples }: {
  x: number; y: number; vp: Viewport;
  samples: { hs: HansenSample | null; js: JrcSample | null; jrcOn: boolean };
}) {
  const { hs, js, jrcOn } = samples;
  const flipX = x > vp.width - 250, flipY = y > vp.height - 170;
  const style: React.CSSProperties = {
    left: flipX ? undefined : x + 14, right: flipX ? vp.width - x + 14 : undefined,
    top: flipY ? undefined : y + 14, bottom: flipY ? vp.height - y + 14 : undefined,
  };
  const land = hs?.datamask === 1;
  return (
    <div className="pl-map__float pl-map__tip" style={style} aria-hidden="true">
      {hs ? (
        <dl>
          <div><dt>Hansen cell</dt><dd>{hs.row}:{hs.col}</dd></div>
          <div><dt>Canopy 2000</dt><dd>{hs.treecover}%{land ? "" : " · raw, excluded"}</dd></div>
          <div><dt>Loss</dt><dd>{!land ? `raw code ${hs.lossyear} · excluded` : hs.lossyear === 0 ? "no loss" : 2000 + hs.lossyear}</dd></div>
          <div><dt>Mask</dt><dd>{MASK_NAME[hs.datamask] ?? `code ${hs.datamask}`}</dd></div>
        </dl>
      ) : (
        <p>Outside the Hansen chip</p>
      )}
      {jrcOn && (
        <dl className="pl-map__tip-jrc">
          {js ? (
            <div>
              <dt>JRC 2020</dt>
              <dd>{js.klass === 1 ? "forest" : "non-forest (valid)"} · {js.row}:{js.col}</dd>
            </div>
          ) : (
            <div><dt>JRC 2020</dt><dd>outside its grid</dd></div>
          )}
        </dl>
      )}
      <p className="pl-map__tip-foot">display raster · counts come from the verified export</p>
    </div>
  );
}

function Legend({ open, onToggle, layer, year, showJrc, raster, plotView, cells }: {
  open: boolean; onToggle: () => void; layer: MapLayer; year: number; showJrc: boolean; raster: boolean; plotView: boolean; cells: boolean;
}) {
  const rows: { sw: string; text: string }[] = [];
  if (!raster) {
    // Vector-only view: no raster layers to explain.
  } else if (layer === "loss") {
    rows.push({ sw: "loss", text: `Loss in ${year}` });
    if (year > 2001) rows.push({ sw: "past", text: year === 2002 ? "Loss in 2001" : `Loss 2001–${year - 1}` });
    rows.push({ sw: "ramp-dim", text: "Canopy 2000, 0→100% (dimmed)" });
  } else if (layer === "canopy") {
    rows.push({ sw: "ramp", text: "Canopy 2000, 0→100%" });
  } else {
    rows.push({ sw: "land", text: "Land" });
  }
  if (raster) rows.push({ sw: "water", text: "Water" }, { sw: "nodata", text: "No data" });
  return (
    <div className="pl-map__float pl-map__legend">
      <button type="button" className="pl-map__legend-head" aria-expanded={open} onClick={onToggle}>
        <span className="pl-eyebrow">Legend</span>
        <Icon name="chevron" size={12} />
      </button>
      {open && (
        <div className="pl-map__legend-body">
          <ul>
            {rows.map((r) => (
              <li key={r.sw}><i className={`pl-map__sw pl-map__sw--${r.sw}`} aria-hidden="true" />{r.text}</li>
            ))}
            {showJrc && (
              <li>
                <i className="pl-map__sw pl-map__sw--forest" aria-hidden="true" />
                <span>JRC 2020 forest (class 1) · class 0 non-forest shown transparent<small>Class 0 is valid Non-forest, not missing data.</small></span>
              </li>
            )}
            {plotView && (
              <li><i className="pl-map__sw pl-map__sw--boundary" aria-hidden="true" />Exact plot boundary</li>
            )}
            {plotView && cells && (
              <li><i className="pl-map__sw pl-map__sw--cell" aria-hidden="true" />Selected native cells · dot = centre</li>
            )}
          </ul>
          {raster ? (
            <p className="pl-map__legend-src">Hansen GFC 2025 v1.13 · display raster</p>
          ) : (
            <p className="pl-map__legend-src">Display raster unavailable · plot geometry and native cells only</p>
          )}
          {showJrc && <p className="pl-map__legend-src">JRC GFC 2020 v4 · own grid · display raster</p>}
        </div>
      )}
    </div>
  );
}
