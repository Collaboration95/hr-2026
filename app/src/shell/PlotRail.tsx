import { useEffect, useMemo, useRef, useState, type KeyboardEvent } from "react";
import { EmptyState, Glyph, Icon } from "../components/Primitives";
import { declaredIndication, differs, mappedLoss } from "../review/plot-facts";
import type { Plot } from "../types";

export type RailFilter = "all" | "declared" | "mapped" | "differs";

const FILTERS: { key: RailFilter; label: string; test: (plot: Plot) => boolean }[] = [
  { key: "all", label: "All", test: () => true },
  { key: "declared", label: "Declared indication", test: (p) => declaredIndication(p) === true },
  { key: "mapped", label: "Mapped loss 2021–23", test: (p) => mappedLoss(p) === true },
  { key: "differs", label: "Declared ≠ mapped", test: (p) => differs(p) === true },
];

export const sortPlots = (plots: Plot[]): Plot[] =>
  [...plots].sort((a, b) => a.plot_id.localeCompare(b.plot_id, "en", { numeric: true }));

/** Rail-only search and filter state. These never affect the map, cohort or proof. */
export function useRailFilter(plots: Plot[]) {
  const [query, setQuery] = useState("");
  const [filter, setFilter] = useState<RailFilter>("all");
  const counts = useMemo(
    () => Object.fromEntries(FILTERS.map((f) => [f.key, plots.filter(f.test).length])) as Record<RailFilter, number>,
    [plots],
  );
  const visible = useMemo(() => {
    const test = FILTERS.find((f) => f.key === filter)!.test;
    const needle = query.trim().toLowerCase();
    return plots.filter(
      (plot) =>
        test(plot) &&
        (!needle || `${plot.plot_id} ${plot.supplier?.a6_tier1_supplier_id ?? ""}`.toLowerCase().includes(needle)),
    );
  }, [plots, filter, query]);
  const clear = () => {
    setQuery("");
    setFilter("all");
  };
  return { query, setQuery, filter, setFilter, counts, visible, clear, active: filter !== "all" || query.trim() !== "" };
}
export type RailState = ReturnType<typeof useRailFilter>;

const area = (plot: Plot) => {
  const ha = plot.supplier?.a7_size_of_plot_ha;
  return typeof ha === "string" && ha.trim() ? `${ha} ha` : "area not supplied";
};

function rowLabel(plot: Plot): string {
  const declared = declaredIndication(plot);
  const mapped = mappedLoss(plot);
  return [
    plot.plot_id,
    area(plot),
    declared === null ? "declaration unknown" : declared ? "declared indication" : "declared no indication",
    mapped === null ? "mapped loss unknown" : mapped ? "mapped loss 2021–23" : "no mapped loss 2021–23",
    differs(plot) === true ? "declaration differs from map" : null,
  ]
    .filter(Boolean)
    .join(" · ");
}

function PlotRow({ plot, selected, onSelect }: { plot: Plot; selected: boolean; onSelect: (id: string) => void }) {
  const declared = declaredIndication(plot);
  const mapped = mappedLoss(plot);
  return (
    <button
      type="button"
      className="plot-row"
      aria-pressed={selected}
      aria-label={rowLabel(plot)}
      data-plot-id={plot.plot_id}
      onClick={() => onSelect(plot.plot_id)}
    >
      <span className="plot-row__id pl-num">{plot.plot_id}</span>
      <span className="plot-row__area pl-num">{area(plot)}</span>
      <span className="plot-row__marks" aria-hidden="true">
        {declared === null ? <Glyph kind="unknown" /> : <Glyph kind="declared" hollow={!declared} />}
        {mapped === null ? <Glyph kind="unknown" /> : <Glyph kind="loss" hollow={!mapped} />}
        <span className="plot-row__q">{differs(plot) === true && <Glyph kind="review" />}</span>
      </span>
    </button>
  );
}

export default function PlotRail({
  plots,
  rail,
  selectedId,
  onSelect,
}: {
  plots: Plot[];
  rail: RailState;
  selectedId: string | null;
  onSelect: (id: string) => void;
}) {
  const { query, setQuery, filter, setFilter, counts, visible, clear } = rail;
  const list = useRef<HTMLUListElement>(null);
  const hidden = selectedId !== null && !visible.some((plot) => plot.plot_id === selectedId);

  // Keep the selected row visible by scrolling only the rail list, never the page.
  useEffect(() => {
    const box = list.current;
    const row = box?.querySelector<HTMLElement>('[aria-pressed="true"]');
    if (!box || !row) return;
    const b = box.getBoundingClientRect();
    const r = row.getBoundingClientRect();
    if (r.top < b.top) box.scrollTop -= b.top - r.top + 4;
    else if (r.bottom > b.bottom) box.scrollTop += r.bottom - b.bottom + 4;
    if (r.left < b.left) box.scrollLeft -= b.left - r.left + 12;
    else if (r.right > b.right) box.scrollLeft += r.right - b.right + 12;
  }, [selectedId, visible]);

  const onSearchKey = (event: KeyboardEvent<HTMLInputElement>) => {
    if (event.key === "Escape") {
      event.preventDefault();
      if (query) setQuery("");
      else event.currentTarget.blur();
    } else if (event.key === "Enter" && visible[0]) {
      event.preventDefault();
      onSelect(visible[0].plot_id);
    }
  };

  return (
    <aside className="pl-rail" aria-label="Supplier plots">
      <div className="pl-rail__head">
        <div className="pl-search">
          <Icon name="search" size={15} />
          <input
            id="plot-search"
            className="pl-input"
            type="text"
            aria-label="Search plots"
            aria-keyshortcuts="/"
            placeholder="Find plot"
            autoComplete="off"
            spellCheck={false}
            value={query}
            onChange={(event) => setQuery(event.target.value)}
            onKeyDown={onSearchKey}
          />
          <kbd className="pl-kbd" aria-hidden="true">/</kbd>
        </div>
        <div className="pl-rail__filters" role="group" aria-label="Filter plots">
          {FILTERS.map((f) => (
            <button
              key={f.key}
              type="button"
              className="pl-chip"
              aria-pressed={filter === f.key}
              onClick={() => setFilter(f.key)}
            >
              {f.label} <span className="pl-chip__count">{counts[f.key]}</span>
            </button>
          ))}
        </div>
        <p className="pl-rail__legend pl-fine" aria-hidden="true">
          <span><Glyph kind="declared" /> declared</span>
          <span><Glyph kind="loss" /> mapped 2021–23</span>
          <span><Glyph kind="review" /> differ</span>
        </p>
        <p className="pl-rail__scope pl-fine">
          {visible.length} of {plots.length} plots · filters change this list only
        </p>
      </div>
      {hidden && selectedId && (
        <div className="pl-rail__notice" role="status">
          <span>{selectedId} is open but hidden by this filter</span>
          <button type="button" className="pl-btn pl-btn--sm" onClick={clear}>Show all</button>
        </div>
      )}
      {visible.length ? (
        <ul className="pl-rail__list" ref={list}>
          {visible.map((plot) => (
            <li key={plot.plot_id}>
              <PlotRow plot={plot} selected={plot.plot_id === selectedId} onSelect={onSelect} />
            </li>
          ))}
        </ul>
      ) : (
        <div className="pl-rail__empty">
          <EmptyState title="No matching plots" detail="Try a plot ID, or clear the search and filters." />
          <button type="button" className="pl-btn pl-btn--sm" onClick={clear}>Clear filters</button>
        </div>
      )}
    </aside>
  );
}
