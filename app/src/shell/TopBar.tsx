import { useMemo } from "react";
import { Icon } from "../components/Primitives";
import { comparisonState } from "../comparison-state";
import type { Demo, Plot } from "../types";
import { VIEWS, VIEW_LABEL, type View } from "./route";

/** The value every plot agrees on, or null when it is missing or mixed. Never invented. */
function commonSupplierValue(plots: Plot[], key: string): string | null {
  const values = new Set<string>();
  for (const plot of plots) {
    const value = plot.supplier?.[key];
    if (typeof value !== "string" || !value.trim()) return null;
    values.add(value.trim());
  }
  return values.size === 1 ? [...values][0] : null;
}

function context(plots: Plot[]): { lot: string | null; place: string | null; count: string } {
  const lot = commonSupplierValue(plots, "a2_lot_number");
  const place = ["j5_district_of_origin", "j4_province_of_origin", "j3_country_of_origin"]
    .map((key) => commonSupplierValue(plots, key))
    .filter((value): value is string => value !== null);
  return {
    lot,
    place: place.length ? `${place.join(", ")} (declared)` : null,
    count: `${plots.length} ${plots.length === 1 ? "plot" : "plots"}`,
  };
}

type Tone = "proof" | "review" | "unknown";

function exportStatus(plots: Plot[]): { tone: Tone; prefix: string; label: string } {
  let match = 0;
  let mismatch = 0;
  for (const plot of plots) {
    const state = comparisonState(plot);
    if (state === "match") match++;
    else if (state === "mismatch") mismatch++;
  }
  const missing = plots.length - match - mismatch;
  const prefix = "Frozen export · ";
  if (match === 0 && mismatch === 0) return { tone: "unknown", prefix, label: "Not computed" };
  const parts = [`${match}/${plots.length} identical`];
  if (mismatch) parts.push(`${mismatch} differ`);
  if (missing) parts.push(`${missing} not computed`);
  return { tone: mismatch ? "review" : missing ? "unknown" : "proof", prefix, label: parts.join(" · ") };
}

export default function TopBar({
  data,
  view,
  onTab,
  onCommands,
}: {
  data: Demo;
  view: View;
  onTab: (view: View) => void;
  onCommands: () => void;
}) {
  const ctx = useMemo(() => context(data.plots), [data.plots]);
  const status = useMemo(() => exportStatus(data.plots), [data.plots]);
  const parts = [ctx.lot && `Lot ${ctx.lot}`, ctx.place, ctx.count].filter(Boolean) as string[];
  return (
    <header className="pl-topbar">
      <a className="pl-brand" href="#/map" title="Region overview">
        <svg width="18" height="18" viewBox="0 0 18 18" fill="none" aria-hidden="true" focusable="false">
          <path d="M2 13.5 6.5 8l3 3L15 4" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" />
          <circle cx="15" cy="4" r="1.9" fill="currentColor" />
        </svg>
        <span>plotline</span>
      </a>
      <p className="pl-topbar__ctx" title={parts.join(" · ")}>
        {parts.map((part, i) => (
          <span key={part}>
            {i > 0 && <span className="pl-topbar__sep"> · </span>}
            {part}
          </span>
        ))}
      </p>
      <nav className="pl-segmented pl-tabs" aria-label="Workspace view">
        {VIEWS.map((key) => (
          <button key={key} type="button" aria-current={key === view ? "page" : undefined} onClick={() => onTab(key)}>
            {VIEW_LABEL[key]}
          </button>
        ))}
      </nav>
      <button
        type="button"
        className="pl-btn pl-btn--sm pl-topbar__cmd"
        aria-label="Open commands"
        aria-keyshortcuts="Meta+K Control+K"
        title="Commands · ⌘K (Ctrl+K on Windows and Linux)"
        onClick={onCommands}
      >
        <Icon name="command" size={15} />
        <span className="pl-topbar__cmd-label">Commands</span>
        <kbd className="pl-kbd" aria-hidden="true">⌘K</kbd>
      </button>
      <span
        className={`pl-chip pl-chip--${status.tone} pl-topbar__status`}
        title={data.content_sha256 ?? "No content hash in this export"}
      >
        {status.tone === "proof" && <Icon name="check" size={13} />}
        <span>
          <span className="pl-topbar__status-prefix">{status.prefix}</span>
          {status.label}
        </span>
      </span>
    </header>
  );
}
