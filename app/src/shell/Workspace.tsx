import { useEffect, useLayoutEffect, useMemo, useRef, useState, type ComponentProps } from "react";
import CohortIndex from "../CohortIndex";
import { Icon } from "../components/Primitives";
import LiveQueryLab from "../LiveQueryLab";
import type MapStage from "../map/MapStage";
import type { Cell, Demo } from "../types";
import CommandPalette, { type Command } from "./CommandPalette";
import { focusWhenReady, isEditable, useStableCallback } from "./dom";
import MapView from "./MapView";
import { sortPlots, useRailFilter } from "./PlotRail";
import ProofRoute from "./ProofRoute";
import ReceiptDialog from "./ReceiptDialog";
import {
  DEFAULT_YEAR, HOME, VIEW_LABEL, formatRoute, navigate, parseHash, useHash,
  type Route, type View,
} from "./route";
import TopBar from "./TopBar";
import { useJrcCompanion } from "./useJrcCompanion";

type Dialog = { kind: "commands" } | { kind: "receipt"; plotId: string } | null;
type Focus = { id: string; block?: ScrollLogicalPosition };
type PendingFocus = Focus & { hash: string };
type ProofOrigin = "count" | "header" | "other";

const POPOVER = '.pl-info__panel, [role="menu"], [aria-haspopup][aria-expanded="true"]';

const defaultFocus = (view: View, hasPlot: boolean): Focus => {
  switch (view) {
    case "map":
      return { id: hasPlot ? "plot-review-heading" : "main-content" };
    case "cohort":
      return { id: "cohort-heading", block: "start" };
    case "proof":
      return { id: "proof-heading", block: "start" };
    case "live":
      return { id: "live-heading", block: "start" };
  }
};

export default function Workspace({ data, reloadError, reloading, onReload }: {
  data: Demo;
  reloadError: string;
  reloading: boolean;
  onReload: () => void;
}) {
  const plots = useMemo(() => sortPlots(data.plots), [data]);
  const byId = useMemo(() => new Map(plots.map((p) => [p.plot_id, p])), [plots]);
  const rail = useRailFilter(plots);
  const jrc = useJrcCompanion(data);

  // ---- Route: the hash is the source of truth for view, plot and year ----
  const hash = useHash();
  const parsed = useMemo(() => parseHash(hash), [hash]);
  const route: Route = parsed.ok ? parsed.route : HOME;
  const routePlot = route.plotId ? (byId.get(route.plotId) ?? null) : null;
  const [freeYear, setFreeYear] = useState(DEFAULT_YEAR);
  const year = routePlot ? (route.year ?? DEFAULT_YEAR) : freeYear;
  useEffect(() => {
    if (routePlot) setFreeYear(route.year ?? DEFAULT_YEAR);
  }, [routePlot, route.year]);

  // Remembered context so tabs, Proof and Live land somewhere sensible.
  const [memory, setMemory] = useState<{ last: string | null; map: string | null }>({ last: null, map: null });
  useEffect(() => {
    setMemory((m) => {
      const last = routePlot ? routePlot.plot_id : m.last;
      const map = route.view === "map" ? (routePlot?.plot_id ?? null) : route.view === "proof" && routePlot ? routePlot.plot_id : m.map;
      return last === m.last && map === m.map ? m : { last, map };
    });
  }, [route.view, routePlot]);
  const proofPlotId = routePlot?.plot_id ?? memory.last ?? plots[0]?.plot_id ?? null;

  const [notice, setNotice] = useState<string | null>(null);
  useEffect(() => {
    if (!parsed.ok) {
      navigate(HOME, true);
      return;
    }
    const r = parsed.route;
    if (r.plotId && !byId.has(r.plotId)) {
      setNotice(`Plot ${r.plotId} is not in this export. Showing the region view.`);
      navigate(HOME, true);
    } else if (r.view === "proof" && !r.plotId && proofPlotId) {
      navigate({ view: "proof", plotId: proofPlotId, year: r.year ?? freeYear }, true);
    }
  }, [parsed, byId, proofPlotId, freeYear]);

  // ---- Focus management: an explicit request wins, otherwise a view change focuses its heading ----
  const [, bump] = useState(0);
  const pendingFocus = useRef<PendingFocus | null>(null);
  const cancelFocus = useRef<(() => void) | null>(null);
  const prevView = useRef<View | null>(null);
  const proofOrigin = useRef<ProofOrigin>("other");

  const go = useStableCallback((target: Route, opts: { replace?: boolean; focus?: Focus } = {}) => {
    setNotice(null);
    const focus = opts.focus ? { ...opts.focus, hash: formatRoute(target) } : null;
    if (navigate(target, opts.replace)) {
      pendingFocus.current = focus;
    } else if (focus) {
      pendingFocus.current = focus; // same hash: nothing re-renders by itself
      bump((n) => n + 1);
    }
  });

  useLayoutEffect(() => {
    const view = parsed.ok ? parsed.route.view : null;
    if (!view) return;
    if (prevView.current !== null && prevView.current !== view) {
      window.scrollTo(0, 0);
      pendingFocus.current ??= { ...defaultFocus(view, routePlot !== null), hash };
    }
    prevView.current = view;
  }, [hash]);

  const [dialog, setDialog] = useState<Dialog>(null);
  const dialogRef = useRef<Dialog>(dialog);
  const opener = useRef<HTMLElement | null>(null);
  const hadDialog = useRef(false);
  useLayoutEffect(() => {
    dialogRef.current = dialog;
    if (dialog) {
      hadDialog.current = true;
      return;
    }
    if (hadDialog.current) {
      hadDialog.current = false;
      const back = opener.current;
      opener.current = null;
      if (!pendingFocus.current && back?.isConnected) back.focus({ preventScroll: true });
    }
    const intent = pendingFocus.current;
    if (intent && intent.hash === hash) {
      pendingFocus.current = null;
      cancelFocus.current?.();
      cancelFocus.current = focusWhenReady(intent.id, intent.block);
    }
  });
  useEffect(() => () => cancelFocus.current?.(), []);

  const openDialog = useStableCallback((next: NonNullable<Dialog>) => {
    if (!dialogRef.current) {
      const active = document.activeElement;
      opener.current = active instanceof HTMLElement && active !== document.body ? active : null;
    }
    setDialog(next);
  });
  const closeDialog = useStableCallback(() => setDialog(null));

  // ---- Map-view state kept here so it survives tab switches ----
  const [layer, setLayer] = useState<ComponentProps<typeof MapStage>["layer"]>("loss");
  const [showJrc, setShowJrc] = useState(false);
  const [pinnedCell, setPinnedCell] = useState<Cell | null>(null);
  const routePlotId = routePlot?.plot_id ?? null;
  useEffect(() => setPinnedCell(null), [routePlotId]);

  // The JRC column in the cohort is optional: load it when the cohort opens, never block on it.
  useEffect(() => {
    if (route.view === "cohort" && jrc.status === "idle") jrc.load();
  }, [route.view, jrc.status, jrc.load]);

  // ---- Navigation actions (stable identities; safe to hand to the map and inspector) ----
  const mapYear = year === DEFAULT_YEAR ? null : year;
  const selectPlot = useStableCallback((id: string | null) => {
    go(id ? { view: "map", plotId: id, year: mapYear } : HOME);
  });
  const setYear = useStableCallback((next: number) => {
    if (route.view === "map" && routePlot) go({ view: "map", plotId: routePlot.plot_id, year: next }, { replace: true });
    else setFreeYear(next);
  });
  const openProof = useStableCallback((plotId: string, forYear: number, origin: ProofOrigin) => {
    proofOrigin.current = origin;
    go(
      { view: "proof", plotId, year: forYear },
      { focus: origin === "count" ? { id: "proof-selected-year", block: "center" } : { id: "proof-heading", block: "start" } },
    );
  });
  const onProof = useStableCallback((origin: "count" | "header") => {
    if (routePlot) openProof(routePlot.plot_id, year, origin);
  });
  const backToMap = useStableCallback(() => {
    const plotId = routePlot?.plot_id ?? proofPlotId;
    go(
      { view: "map", plotId, year },
      { focus: { id: proofOrigin.current === "count" ? "annual-proof-trigger" : "plot-review-heading" } },
    );
    proofOrigin.current = "other";
  });
  const review = useStableCallback((plotId: string, forYear: number) => {
    go({ view: "map", plotId, year: forYear }, { focus: { id: "plot-review-heading" } });
  });
  const switchProof = useStableCallback((plotId: string, forYear: number) => {
    go({ view: "proof", plotId, year: forYear });
  });
  const proofYear = useStableCallback((next: number) => {
    if (proofPlotId) go({ view: "proof", plotId: proofPlotId, year: next }, { replace: true });
  });
  const openReceipt = useStableCallback((plotId: string | null = proofPlotId) => {
    if (plotId) openDialog({ kind: "receipt", plotId });
  });
  const openTab = useStableCallback((view: View) => {
    if (view === route.view) return;
    if (view === "map") go({ view, plotId: memory.map, year: memory.map ? mapYear : null });
    else if (view === "proof") {
      if (proofPlotId) openProof(proofPlotId, year, "other");
    } else go({ view, plotId: null, year: null });
  });
  const focusSearch = useStableCallback(() => {
    if (route.view === "map") {
      if (dialogRef.current) {
        // A modal is still open (command palette): focus once it has closed.
        pendingFocus.current = { id: "plot-search", hash };
        bump((n) => n + 1);
        return;
      }
      const search = document.getElementById("plot-search");
      if (search instanceof HTMLInputElement) {
        search.focus();
        search.select();
      }
    } else {
      go(
        { view: "map", plotId: memory.map, year: memory.map ? mapYear : null },
        { focus: { id: "plot-search" } },
      );
    }
  });
  // Key repeat can outrun React's commit, so shortcuts read the live hash rather than render state.
  const liveRoute = (): Route => {
    const live = parseHash(window.location.hash);
    return live.ok ? live.route : route;
  };
  const stepPlot = useStableCallback((direction: 1 | -1) => {
    const now = liveRoute();
    const list = now.view === "proof" ? plots : rail.visible;
    if (!list.length) return;
    const at = list.findIndex((p) => p.plot_id === now.plotId);
    const next = at === -1 ? (direction === 1 ? 0 : list.length - 1) : (at + direction + list.length) % list.length;
    const id = list[next].plot_id;
    const nowYear = now.plotId ? (now.year ?? DEFAULT_YEAR) : freeYear;
    if (now.view === "proof") go({ view: "proof", plotId: id, year: nowYear });
    else go({ view: "map", plotId: id, year: nowYear === DEFAULT_YEAR ? null : nowYear });
  });

  // ---- Keyboard ----
  const onKey = useRef<(event: KeyboardEvent) => void>(() => {});
  useLayoutEffect(() => {
    onKey.current = (event) => {
      if ((event.metaKey || event.ctrlKey) && !event.altKey && !event.shiftKey && event.key.toLowerCase() === "k") {
        event.preventDefault();
        if (dialog?.kind === "commands") closeDialog();
        else if (!dialog) openDialog({ kind: "commands" });
        return;
      }
      if (event.defaultPrevented || event.isComposing || dialog || document.querySelector("dialog[open]")) return;
      const editable = isEditable(event.target);
      if (event.key === "Escape") {
        if (editable || document.querySelector(POPOVER)) return;
        const now = liveRoute();
        if (now.view === "map" && now.plotId) {
          event.preventDefault();
          if (pinnedCell) setPinnedCell(null);
          else selectPlot(null);
        }
        return;
      }
      if (editable || event.metaKey || event.ctrlKey || event.altKey) return;
      const key = event.key.toLowerCase();
      if (event.key === "/") {
        event.preventDefault();
        focusSearch();
      } else if ((key === "j" || key === "k") && ["map", "proof"].includes(liveRoute().view)) {
        event.preventDefault();
        stepPlot(key === "j" ? 1 : -1);
      }
    };
  });
  useEffect(() => {
    const handler = (event: KeyboardEvent) => onKey.current(event);
    window.addEventListener("keydown", handler);
    return () => window.removeEventListener("keydown", handler);
  }, []);

  // ---- Commands ----
  const buildCommands = (): Command[] => {
    const receiptId = proofPlotId;
    const nav = (view: View, icon: Command["icon"]): Command => ({
      id: `go-${view}`,
      group: "Navigate",
      label: `Go to ${VIEW_LABEL[view]}`,
      icon,
      run: () => openTab(view),
    });
    return [
      nav("map", "map"),
      nav("cohort", "grid"),
      nav("proof", "proof"),
      nav("live", "bolt"),
      ...(receiptId
        ? [{ id: "receipt", group: "Evidence", label: `Inspect ${receiptId} receipt`, icon: "proof" as const, run: () => openReceipt(receiptId) }]
        : []),
      { id: "find", group: "Evidence", label: "Find a plot", icon: "search", kbd: "/", run: focusSearch },
      {
        id: "reload",
        group: "Evidence",
        label: reloading ? "Reloading local evidence…" : "Reload local evidence",
        icon: "layers",
        disabled: reloading,
        run: onReload,
      },
      ...plots.map((p): Command => ({
        id: `plot-${p.plot_id}`,
        group: "Plots",
        label: `Open ${p.plot_id}`,
        hint: p.supplier?.a7_size_of_plot_ha ? `${p.supplier.a7_size_of_plot_ha} ha` : undefined,
        keywords: "plot",
        icon: "target",
        run: () => go({ view: "map", plotId: p.plot_id, year: mapYear }, { focus: { id: "plot-review-heading" } }),
      })),
    ];
  };
  const runCommand = (command: Command) => {
    if (command.disabled) return;
    setDialog(null);
    command.run();
  };

  const receiptPlot = dialog?.kind === "receipt" ? (byId.get(dialog.plotId) ?? null) : null;
  const liveStart = proofPlotId;

  return (
    <div className="pl-app" data-view={route.view}>
      <a
        className="pl-skip"
        href="#main-content"
        onClick={(event) => {
          event.preventDefault();
          document.getElementById("main-content")?.focus();
        }}
      >
        Skip to main content
      </a>
      <TopBar data={data} view={route.view} onTab={openTab} onCommands={() => openDialog({ kind: "commands" })} />
      {reloadError && (
        <div role="alert" className="pl-banner pl-banner--error">
          <Icon name="alert" size={16} />
          <span>Latest reload failed: {reloadError}. Showing the last loaded evidence.</span>
          <button type="button" className="pl-btn pl-btn--sm" onClick={onReload}>Retry</button>
        </div>
      )}
      {notice && (
        <div role="status" className="pl-banner">
          <Icon name="info" size={16} />
          <span>{notice}</span>
          <button type="button" className="pl-btn pl-btn--sm pl-btn--ghost" onClick={() => setNotice(null)}>Dismiss</button>
        </div>
      )}
      <main id="main-content" className="pl-main" tabIndex={-1}>
        {route.view === "map" && (
          <MapView
            data={data}
            plots={plots}
            rail={rail}
            plot={routePlot}
            year={year}
            layer={layer}
            onLayerChange={setLayer}
            showJrc={showJrc}
            onShowJrcChange={setShowJrc}
            pinnedCell={pinnedCell}
            onPinCell={setPinnedCell}
            jrc={jrc}
            onSelectPlot={selectPlot}
            onYear={setYear}
            onProof={onProof}
            onReceipt={() => openReceipt(routePlot?.plot_id)}
          />
        )}
        {route.view === "cohort" && (
          <div className="pl-view">
            <div className="pl-page">
              {jrc.status === "loading" && (
                <div className="pl-callout pl-callout--unknown pl-view__note" role="status">
                  <span className="pl-spinner" aria-hidden="true" />
                  <span>Loading the separate JRC forest column…</span>
                </div>
              )}
              {jrc.status === "error" && (
                <div className="pl-callout pl-callout--error pl-view__note" role="status">
                  <Icon name="alert" size={16} />
                  <span>JRC forest column unavailable: {jrc.error} Hansen counts below are unaffected.</span>
                  <button type="button" className="pl-btn pl-btn--sm" onClick={jrc.load}>Retry JRC</button>
                </div>
              )}
              <CohortIndex data={data} jrc={jrc.jrc} onReview={review} />
            </div>
          </div>
        )}
        {route.view === "proof" && routePlot && (
          <ProofRoute
            data={data}
            plots={plots}
            plot={routePlot}
            year={year}
            onBack={backToMap}
            onOpen={switchProof}
            onYear={proofYear}
            onReceipt={() => openReceipt(routePlot.plot_id)}
          />
        )}
        {route.view === "live" && liveStart && (
          <div className="pl-view">
            <div className="pl-page">
              <LiveQueryLab data={data} selectedPlotId={liveStart} />
            </div>
          </div>
        )}
      </main>
      {dialog?.kind === "commands" && (
        <CommandPalette commands={buildCommands()} onClose={closeDialog} onRun={runCommand} />
      )}
      {dialog?.kind === "receipt" && receiptPlot && (
        <ReceiptDialog data={data} plot={receiptPlot} year={year} onClose={closeDialog} />
      )}
    </div>
  );
}
