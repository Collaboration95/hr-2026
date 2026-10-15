/**
 * Hash routing. The hash is the single source of truth for view, plot and year.
 *
 *   #/map                      region overview (landing)
 *   #/map/P-0005[/2025]        plot focus
 *   #/cohort
 *   #/proof[/P-0005[/2025]]    representation proof
 *   #/live
 *
 * Parsing is strict: anything else is invalid and the shell redirects to #/map.
 * A well-formed plot ID that is not in the export is reported by the caller.
 */
import { useSyncExternalStore } from "react";

export type View = "map" | "cohort" | "proof" | "live";
export type Route = { view: View; plotId: string | null; year: number | null };
export type ParsedRoute = { ok: true; route: Route } | { ok: false };

export const FIRST_YEAR = 2001;
export const DEFAULT_YEAR = 2025;
export const HOME: Route = { view: "map", plotId: null, year: null };
export const VIEWS: readonly View[] = ["map", "cohort", "proof", "live"];
export const VIEW_LABEL: Record<View, string> = {
  map: "Map",
  cohort: "Cohort",
  proof: "Proof",
  live: "Live query",
};

const BAD: ParsedRoute = { ok: false };
const isView = (value: string): value is View =>
  (VIEWS as readonly string[]).includes(value);
const takesPlot = (view: View) => view === "map" || view === "proof";

export function parseHash(hash: string): ParsedRoute {
  const parts = hash.replace(/^#\/?/, "").split("/");
  while (parts.length && parts[parts.length - 1] === "") parts.pop();
  const [view, rawId, rawYear, ...rest] = parts;
  if (!view || !isView(view) || rest.length) return BAD;
  if (rawId === undefined) return { ok: true, route: { view, plotId: null, year: null } };
  if (!takesPlot(view)) return BAD;
  let plotId: string;
  try {
    plotId = decodeURIComponent(rawId);
  } catch {
    return BAD;
  }
  if (!plotId) return BAD;
  if (rawYear === undefined) return { ok: true, route: { view, plotId, year: null } };
  if (!/^\d{4}$/.test(rawYear)) return BAD;
  const year = Number.parseInt(rawYear, 10);
  if (year < FIRST_YEAR || year > DEFAULT_YEAR) return BAD;
  return { ok: true, route: { view, plotId, year } };
}

export function formatRoute(route: Route): string {
  let hash = `#/${route.view}`;
  if (takesPlot(route.view) && route.plotId) {
    hash += `/${encodeURIComponent(route.plotId)}`;
    if (route.year !== null) hash += `/${route.year}`;
  }
  return hash;
}

const subscribe = (notify: () => void) => {
  window.addEventListener("hashchange", notify);
  return () => window.removeEventListener("hashchange", notify);
};

/** The current location hash; re-renders on back/forward and manual edits. */
export function useHash(): string {
  return useSyncExternalStore(subscribe, () => window.location.hash, () => "");
}

/** Push (or replace) a route. Returns false when the hash was already current. */
export function navigate(route: Route, replace = false): boolean {
  const next = formatRoute(route);
  if (window.location.hash === next) return false;
  if (replace) window.location.replace(next);
  else window.location.hash = next;
  return true;
}
