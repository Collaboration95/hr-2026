import { useEffect, useLayoutEffect, useMemo, useRef, useState } from "react";
import { Icon, Pill, EmptyState } from "./components/Primitives";
import Benchmark from "./Benchmark";
import CellTable from "./CellTable";
import EdgeLab from "./EdgeLab";
import {
  availableBand,
  canopyLabel,
  lossLabel,
  maskLabel,
  isYearEvent,
} from "./cell-values";
import { comparisonState } from "./comparison-state";
import { loadDemo } from "./data";
import AnalystNotes from "./AnalystNotes";
import type { Demo, Plot, Geometry, Cell, Result } from "./types";

const fmt = (n: number | null | undefined) =>
  n == null ? "Unavailable" : n.toLocaleString();
const lead = (p: Plot) =>
  p.supplier.c2_deforestation_spatial_analysis_result ===
  "b. Indication of deforestation";
const dateLabel = (value?: string) => {
  if (!value || !/^\d{8}$/.test(value)) return value || "Not supplied";
  const d = new Date(
    `${value.slice(0, 4)}-${value.slice(4, 6)}-${value.slice(6, 8)}T00:00:00Z`,
  );
  return Number.isNaN(d.valueOf())
    ? value
    : new Intl.DateTimeFormat("en-GB", {
        day: "2-digit",
        month: "short",
        year: "numeric",
        timeZone: "UTC",
      }).format(d);
};
const clean = (s?: string) => s?.replace(/^[a-z]\. /, "") || "Not supplied";
const years = Array.from({ length: 25 }, (_, i) => 2001 + i);
function bounds(g: Geometry[]) {
  const a = g.flatMap((v) => v.coordinates.flat());
  return [
    Math.min(...a.map((p) => p[0])),
    Math.min(...a.map((p) => p[1])),
    Math.max(...a.map((p) => p[0])),
    Math.max(...a.map((p) => p[1])),
  ];
}
function projector(gs: Geometry[], w = 800, h = 470, pad = 58) {
  const [x0, y0, x1, y1] = bounds(gs);
  const c = Math.cos((((y0 + y1) / 2) * Math.PI) / 180);
  const scale = Math.min(
    (w - pad * 2) / ((x1 - x0) * c || 1),
    (h - pad * 2) / (y1 - y0 || 1),
  );
  return (p: number[]) => [
    (p[0] - (x0 + x1) / 2) * c * scale + w / 2,
    h / 2 - (p[1] - (y0 + y1) / 2) * scale,
  ];
}
function path(g: Geometry, project: (p: number[]) => number[]) {
  return g.coordinates
    .map(
      (r) =>
        r.map((p, i) => `${i ? "L" : "M"}${project(p).join(",")}`).join(" ") +
        "Z",
    )
    .join(" ");
}
function download(name: string, value: unknown) {
  const u = URL.createObjectURL(
    new Blob([JSON.stringify(value, null, 2)], { type: "application/json" }),
  );
  const a = document.createElement("a");
  a.href = u;
  a.download = name;
  a.click();
  setTimeout(() => URL.revokeObjectURL(u), 1000);
}
function signal(value: boolean | null | undefined) {
  return value === true
    ? "Mapped loss observed"
    : value === false
      ? "No mapped loss under this query"
      : "Mapped result unknown";
}

function MapPanel({
  plot,
  plots,
  year,
  onSelect,
}: {
  plot: Plot;
  plots: Plot[];
  year: number;
  onSelect: (id: string) => void;
}) {
  const [layer, setLayer] = useState<"loss" | "canopy" | "mask">("loss");
  const [cell, setCell] = useState<Cell | null>(null);
  const [overview, setOverview] = useState(false);
  useEffect(() => {
    setCell(null);
    setOverview(false);
  }, [plot.plot_id]);
  const cells = plot.evidence?.features || [];
  const project = useMemo(
    () =>
      projector(
        overview
          ? plots.map((p) => p.geometry)
          : [plot.geometry, ...cells.map((c) => c.geometry)],
        800,
        470,
        overview ? 100 : 58,
      ),
    [plot, overview, plots],
  );
  const count = plot.source_result?.yearly_loss_counts?.[year];
  const mapBounds = bounds(
    overview ? plots.map((p) => p.geometry) : [plot.geometry],
  );
  const color = (c: Cell) =>
    !c.properties.valid_land ||
    availableBand(c, layer === "canopy" ? 0 : layer === "loss" ? 1 : 2) == null
      ? "#b7c2c2"
      : layer === "canopy"
        ? `hsl(146 24% ${88 - (availableBand(c, 0) ?? 0) * 0.48}%)`
        : layer === "mask"
          ? "#9caf8e"
          : isYearEvent(c, year)
            ? "#df743f"
            : "#d8e2cd";
  return (
    <section
      className="map-panel"
      aria-label="Plot geometry and native-grid evidence"
    >
      <div className="map-toolbar">
        <div className="segmented" aria-label="Map layer">
          {(["loss", "canopy", "mask"] as const).map((v) => (
            <button
              key={v}
              aria-pressed={layer === v}
              disabled={overview}
              onClick={() => setLayer(v)}
            >
              {v === "loss"
                ? "Annual loss"
                : v === "canopy"
                  ? "Canopy · 2000"
                  : "Land mask"}
            </button>
          ))}
        </div>
        <button className="map-fit" onClick={() => setOverview(!overview)}>
          <Icon name="layers" />
          {overview ? "Focus plot" : "All 17 plots"}
        </button>
      </div>
      <div className="map-canvas">
        <svg
          className="spatial-map"
          viewBox="0 0 800 470"
          aria-label={
            overview
              ? "All supplied plot locations"
              : `${plot.plot_id} exact boundary and ${cells.length} native cell footprints`
          }
        >
          <defs>
            <pattern
              id="coordinate-grid"
              width="40"
              height="40"
              patternUnits="userSpaceOnUse"
            >
              <path
                d="M40 0H0V40"
                fill="none"
                stroke="#c6d1c5"
                strokeWidth=".6"
              />
            </pattern>
          </defs>
          <rect width="800" height="470" fill="url(#coordinate-grid)" />
          {!overview &&
            cells.map((c, i) => (
              <path
                key={i}
                d={path(c.geometry, project)}
                fill={color(c)}
                stroke="#f0f3e9"
                strokeWidth="1"
                className={`native-cell ${cell === c ? "cell-selected" : ""}`}
                onClick={() => setCell(c)}
              >
                <title>{`Cell ${c.properties.row}:${c.properties.col}; canopy ${canopyLabel(c)}; loss ${lossLabel(c)}; mask ${maskLabel(c)}`}</title>
              </path>
            ))}
          {(overview ? plots : [plot]).map((p) => (
            <g
              key={p.plot_id}
              className="plot-geometry"
              role={overview ? "button" : undefined}
              tabIndex={overview ? 0 : undefined}
              aria-label={overview ? `Select ${p.plot_id} on map` : undefined}
              onClick={() => overview && onSelect(p.plot_id)}
              onKeyDown={(e) => {
                if (overview && (e.key === "Enter" || e.key === " ")) {
                  e.preventDefault();
                  onSelect(p.plot_id);
                }
              }}
            >
              <title>
                {p.plot_id} · {p.supplier.a7_size_of_plot_ha} ha declared
              </title>
              <path
                d={path(p.geometry, project)}
                fill={
                  overview
                    ? p.plot_id === plot.plot_id
                      ? "#c2ed58"
                      : "#6d8b72"
                    : "none"
                }
                stroke="#173e32"
                strokeWidth={overview ? 1.5 : 3}
                fillRule="evenodd"
              />
              {overview && (
                <circle
                  cx={project(p.geometry.coordinates[0][0])[0]}
                  cy={project(p.geometry.coordinates[0][0])[1]}
                  r="9"
                  fill={p.plot_id === plot.plot_id ? "#c2ed58" : "#163b30"}
                  stroke="#fafbf6"
                  strokeWidth="2"
                />
              )}
              {overview && p.plot_id === plot.plot_id && (
                <text
                  x={project(p.geometry.coordinates[0][0])[0] + 14}
                  y={project(p.geometry.coordinates[0][0])[1] + 4}
                  className="overview-selected-label"
                >
                  {p.plot_id}
                </text>
              )}
            </g>
          ))}
          <text x="620" y="34" className="map-coordinate">
            {mapBounds[3].toFixed(5)}° N
          </text>
          <text x="28" y="448" className="map-coordinate">
            {mapBounds[0].toFixed(5)}° E · EPSG:4326
          </text>
          <g transform="translate(750,28)">
            <path d="M0 30V0l-5 10M0 0l5 10" stroke="#163b30" fill="none" />
            <text x="-5" y="-8" className="map-coordinate">
              N
            </text>
          </g>
        </svg>
        <div className="map-title">
          <span className="eyebrow">
            {overview
              ? "Supplier sample / spatial index"
              : "Exact supplied boundary"}
          </span>
          <strong>{overview ? "Chai Buri, Thailand" : plot.plot_id}</strong>
          <span>
            {overview
              ? "17 plot locations · Select a marker"
              : `${plot.supplier.a7_size_of_plot_ha} ha declared · ${plot.source_result ? `${fmt(plot.source_result.selected_cell_count)} selected cells` : "Selected support unavailable"}`}
          </span>
        </div>
        {!overview && (
          <div className="map-legend">
            <span className={`legend-chip ${layer}`} />
            <span>
              {layer === "loss"
                ? count == null
                  ? `${year} observations unavailable`
                  : `${year} mapped loss · ${fmt(count)} cells`
                : layer === "canopy"
                  ? "2000 canopy closure · light 0% → dark 100%"
                  : "Valid land / unknown or water"}{" "}
            </span>
          </div>
        )}
        {cell && (
          <div className="cell-inspector">
            <button
              aria-label="Close cell details"
              onClick={() => setCell(null)}
            >
              <Icon name="close" size={15} />
            </button>
            <strong>
              Native cell {cell.properties.row}:{cell.properties.col}
            </strong>
            <span>Canopy 2000: {canopyLabel(cell)}</span>
            <span>Loss year: {lossLabel(cell)}</span>
            <span>Datamask: {maskLabel(cell)}</span>
          </div>
        )}
        {!plot.evidence && !overview && (
          <div className="map-unavailable">
            Boundary available. Mapped cells have not been computed.
          </div>
        )}
      </div>
      <div className="map-footnote">
        <Icon name="info" size={14} />
        <span>
          Source grid, not satellite imagery. Whole native cells are selected
          when their centers fall within the plot. Cell counts are not hectares.
        </span>
      </div>
      <CellTable
        plotId={plot.plot_id}
        available={plot.evidence !== null}
        cells={cells}
        year={year}
        onInspect={setCell}
      />
    </section>
  );
}

function Timeline({
  plot,
  year,
  setYear,
  onProof,
}: {
  plot: Plot;
  year: number;
  setYear: (n: number) => void;
  onProof: () => void;
}) {
  const barRef = useRef<HTMLDivElement>(null);
  useEffect(() => {
    const bar = barRef.current;
    const active = bar?.querySelector<HTMLElement>("[aria-pressed=true]");
    if (bar && active)
      bar.scrollLeft =
        active.offsetLeft -
        bar.offsetLeft -
        bar.clientWidth / 2 +
        active.clientWidth / 2;
  }, [year]);
  const counts = plot.source_result?.yearly_loss_counts;
  const max = Math.max(1, ...Object.values(counts || {}));
  return (
    <section className="timeline" aria-label="Annual mapped-loss timeline">
      <div className="section-title">
        <div>
          <span className="eyebrow">Observation year</span>
          <h3>
            {year}
            <span> / Hansen 2025 v1.13</span>
          </h3>
        </div>
        <button
          id="annual-proof-trigger"
          className="year-stat"
          onClick={onProof}
          aria-label={`Inspect proof for ${year} observed loss cells`}
        >
          <strong>{fmt(counts?.[year])}</strong>
          <span>
            observed loss cells <Icon name="arrow" size={12} />
          </span>
        </button>
      </div>
      {!counts && (
        <p className="timeline-unavailable">
          Annual observations are unavailable. This does not mean zero events.
        </p>
      )}
      <div ref={barRef} className="year-bars">
        {years.map((y) => (
          <button
            key={y}
            className={`${year === y ? "selected" : ""} ${y >= 2021 && y <= 2023 ? "supplier-period" : ""}`}
            aria-label={`Year ${y}, ${counts?.[y] ?? "unavailable"} observed loss cells`}
            aria-pressed={year === y}
            disabled={!counts}
            onClick={() => setYear(y)}
          >
            <span
              className={`year-bar ${!counts ? "unavailable" : counts[y] === 0 ? "no-events" : ""}`}
              style={{
                height: `${counts ? Math.max(3, ((counts[y] || 0) / max) * 58) : 3}px`,
              }}
            />
            <span className="year-label">
              <span className="year-short">{String(y).slice(2)}</span>
              <span className="year-full">{y}</span>
            </span>
          </button>
        ))}
      </div>
      <div className="time-context">
        <span>2001–2025 · scroll / select a year</span>
        <span>
          <i /> Supplier’s declared analysis: 2021–23
        </span>
      </div>
      <div className="supplier-dates">
        <span>
          Supplier processing{" "}
          <b>
            {plot.supplier.a4_processing_date
              ?.split("-")
              .map(dateLabel)
              .join(" – ") || "Not supplied"}
          </b>
        </span>
        <span>
          Supplier harvest{" "}
          <b>{dateLabel(plot.supplier.a5_production_harvest_date)}</b>
        </span>
        <span>Field meanings require clarification</span>
      </div>
    </section>
  );
}

function Declaration({ plot }: { plot: Plot }) {
  const s = plot.supplier;
  const receipt = plot.receipt as { supplier_row_sha256?: string } | null;
  const contextKey =
    receipt?.supplier_row_sha256 ||
    JSON.stringify(Object.entries(s).sort(([a], [b]) => a.localeCompare(b)));
  return (
    <section className="declaration" id="supplier-declaration" tabIndex={-1}>
      <div className="section-title">
        <span className="eyebrow">01 / Supplier declaration</span>
        <Pill tone={lead(plot) ? "warning" : "neutral"}>
          {lead(plot) ? "Review lead" : "Declared record"}
        </Pill>
      </div>
      <h2>
        What supports
        <br />
        the final declaration?
      </h2>
      <div className="claim-step">
        <span>1</span>
        <div>
          <small>Analysis · 2021–2023</small>
          <strong>{clean(s.c2_deforestation_spatial_analysis_result)}</strong>
        </div>
      </div>
      <div className="claim-step">
        <span>2</span>
        <div>
          <small>Mitigation reported</small>
          <strong>{clean(s.c3_mitigation_if_indication_found)}</strong>
        </div>
      </div>
      <div className="claim-step">
        <span>3</span>
        <div>
          <small>Final supplier declaration</small>
          <strong>{clean(s.c5_deforestation_final_status)}</strong>
          <small>EUDR declaration: {clean(s.i1_eudr_status)}</small>
        </div>
      </div>
      <div className="reference-note">
        <span className="eyebrow">Evidence reference</span>
        <code>{s.c4_reference_or_link_if_applicable}</code>
        <p>
          {lead(plot)
            ? "Referenced by the supplier; the evidence file is not supplied. This key is not an accessible link."
            : "The sample supplies declarations, not independently verified mitigation evidence."}
        </p>
      </div>
      <p className="fineprint">
        A declaration is not a finding. These records do not establish a
        violation or verify a legal outcome.
      </p>
      <AnalystNotes plotId={plot.plot_id} contextKey={contextKey} />
    </section>
  );
}
function Observation({ plot }: { plot: Plot }) {
  const r = plot.source_result;
  return (
    <section className="observation">
      <span className="eyebrow">02 / Mapped observation</span>
      <div className="observation-periods">
        {Object.entries(
          r?.periods || { "2021-2023": null, "2024-2025": null },
        ).map(([k, v]) => (
          <div key={k}>
            <span>{k.replace("-", "–")}</span>
            <strong>{signal(v?.mapped_loss_present)}</strong>
            <small>
              {fmt(v?.observed_loss_cell_count)} observed loss cells
            </small>
          </div>
        ))}
      </div>
      <div className="support-line">
        <span>Selected support</span>
        <strong>{r?.support || "Unavailable"}</strong>
      </div>
      <div className="support-line">
        <span>Valid land / selected cells</span>
        <strong>
          {fmt(r?.valid_land_cell_count)} / {fmt(r?.selected_cell_count)}
        </strong>
      </div>
      <div className="support-line">
        <span>Unknown cells</span>
        <strong>{fmt(r?.unknown_cell_count)}</strong>
      </div>
      {!!r?.unknown_reasons.length && (
        <p className="unknown-note">
          Unknown reasons: {r.unknown_reasons.join(", ")}
        </p>
      )}
      <p className="fineprint">
        Tree-cover loss is not a legal deforestation finding. This release may
        differ from the supplier’s historical source. Canopy 2000 is not a
        forest-2020 baseline.
      </p>
    </section>
  );
}
function JsonDetails({ title, value }: { title: string; value: unknown }) {
  return (
    <details className="json-details">
      <summary>{title}</summary>
      <pre>
        {value == null
          ? "Unavailable — not computed or supplied."
          : JSON.stringify(value, null, 2)}
      </pre>
    </details>
  );
}
function Proof({
  plot,
  data,
  year,
  onReceipt,
}: {
  plot: Plot;
  data: Demo;
  year: number;
  onReceipt: () => void;
}) {
  const fields: [string, keyof Result][] = [
    ["Selected native cells", "selected_cell_count"],
    ["Valid land cells", "valid_land_cell_count"],
    ["Unknown cells", "unknown_cell_count"],
    ["Out-of-coverage cells", "out_of_coverage_cell_count"],
    ["Support", "support"],
  ];
  const state = comparisonState(plot);
  const same = state === "match" ? true : state === "mismatch" ? false : null;
  return (
    <section className="proof-view">
      <div className="proof-heading">
        <span className="eyebrow">03 / Representation proof</span>
        <h2 id="proof-heading" tabIndex={-1}>
          Same question.
          <br />
          <em>Two representations.</em>
        </h2>
        <Pill>
          {plot.plot_id} · selected year {year}
        </Pill>
        <p>
          The same boundary, source grid, validity mask and query contract.
          Compare outputs without changing the question.
        </p>
      </div>
      <div className={`agreement ${same === true ? "matches" : ""}`}>
        <Icon name={same === true ? "check" : "info"} size={26} />
        <div>
          <strong>
            {same === true
              ? "Same query outputs"
              : same === false
                ? "Encoding mismatch"
                : "Compact comparison unavailable"}
          </strong>
          <span>
            {same === true
              ? "Exact output equality for this plot. This establishes encoding agreement, not source accuracy or compliance."
              : same === false
                ? "An engineering difference requires review. Inspect the differing fields below."
                : "The source answer is available when computed. Compact results and agreement are not yet measured."}
          </span>
        </div>
      </div>
      <div className="comparison-table">
        <table>
          <thead>
            <tr>
              <th>
                {plot.plot_id} · {data.query_version}
              </th>
              <th>Original source</th>
              <th>Compact</th>
            </tr>
          </thead>
          <tbody>
            <tr id="proof-selected-year" tabIndex={-1}>
              <th>{year} observed loss cells</th>
              <td>{fmt(plot.source_result?.yearly_loss_counts?.[year])}</td>
              <td>{fmt(plot.compact_result?.yearly_loss_counts?.[year])}</td>
            </tr>
            {fields.map(([label, k]) => (
              <tr key={k}>
                <th>{label}</th>
                <td>
                  {plot.source_result
                    ? String(plot.source_result[k])
                    : "Unavailable"}
                </td>
                <td>
                  {plot.compact_result
                    ? String(plot.compact_result[k])
                    : "Unavailable"}
                </td>
              </tr>
            ))}
            {Object.keys(plot.source_result?.periods || {}).map((k) => (
              <tr key={k}>
                <th>{k} loss cells</th>
                <td>
                  {fmt(plot.source_result?.periods[k].observed_loss_cell_count)}
                </td>
                <td>
                  {fmt(
                    plot.compact_result?.periods[k]?.observed_loss_cell_count,
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      {same === false && (
        <p className="unknown-note">
          Differing fields: {plot.comparison?.differing_fields.join(", ")}
        </p>
      )}
      <div className="proof-actions">
        <button className="pl-button--accent" onClick={onReceipt}>
          <Icon name="proof" />
          Inspect provenance receipt
        </button>
        <button
          onClick={() =>
            download(`${plot.plot_id}-comparison.json`, {
              plot_id: plot.plot_id,
              query_version: data.query_version,
              source_result: plot.source_result,
              compact_result: plot.compact_result,
              comparison: plot.comparison,
            })
          }
        >
          <Icon name="download" />
          Download comparison
        </button>
      </div>
      <div className="proof-secondary">
        <div>
          <h3>Full-cohort evidence</h3>
          <p>
            {data.plots.filter((p) => comparisonState(p) === "match").length} /{" "}
            {data.plots.length} plots with measured matching outputs
          </p>
          <JsonDetails title="Inspect cohort summary" value={data.summary} />
        </div>
        <div>
          <h3>Measured experiments</h3>
          <p>
            {data.benchmark
              ? "Engine benchmark artifact is available. Inspect its units, cohort and method."
              : "Storage, query time and resource benchmarks are not yet available."}
          </p>
          <JsonDetails
            title="Inspect benchmark and method"
            value={data.benchmark}
          />
        </div>
      </div>
      <Benchmark value={data.benchmark} />
      <details className="support-lab-disclosure">
        <summary>Explore query limits · 6 separate synthetic cases</summary>
        <EdgeLab />
      </details>
      <JsonDetails
        title="Full source and compact query outputs"
        value={{ source: plot.source_result, compact: plot.compact_result }}
      />
    </section>
  );
}

export default function App() {
  const [data, setData] = useState<Demo | null>(null),
    [error, setError] = useState(""),
    [loading, setLoading] = useState(false),
    [selected, setSelected] = useState("P-0003"),
    [query, setQuery] = useState(""),
    [filter, setFilter] = useState<"all" | "leads">("all"),
    [year, setYear] = useState(2023),
    [view, setView] = useState<"review" | "proof">("review"),
    [dialog, setDialog] = useState<"receipt" | "commands" | null>(null);
  const search = useRef<HTMLInputElement>(null),
    modal = useRef<HTMLDialogElement>(null),
    pendingSearchFocus = useRef(false),
    request = useRef<AbortController | null>(null),
    proofOrigin = useRef<"header" | "count">("header"),
    previousView = useRef(view);
  function load() {
    request.current?.abort();
    const controller = new AbortController();
    request.current = controller;
    setError("");
    setLoading(true);
    loadDemo(controller.signal)
      .then((x) => {
        if (!controller.signal.aborted) setData(x);
      })
      .catch((e) => {
        if (!controller.signal.aborted)
          setError(e instanceof Error ? e.message : "Evidence loading failed.");
      })
      .finally(() => {
        if (!controller.signal.aborted) setLoading(false);
      });
  }
  useEffect(() => {
    load();
    return () => request.current?.abort();
  }, []);
  function showProof(origin: "header" | "count" = "header") {
    proofOrigin.current = origin;
    setView("proof");
  }
  useLayoutEffect(() => {
    if (previousView.current === view) return;
    previousView.current = view;
    if (!dialog && modal.current?.open) modal.current.close();
    const id =
      view === "proof"
        ? proofOrigin.current === "count"
          ? "proof-selected-year"
          : "proof-heading"
        : proofOrigin.current === "count"
          ? "annual-proof-trigger"
          : "plot-proof-trigger";
    const target = document.getElementById(id);
    target?.focus({ preventScroll: true });
    target?.scrollIntoView({
      block:
        view === "proof" && proofOrigin.current === "count"
          ? "center"
          : "start",
      behavior: "auto",
    });
  }, [view]);
  const plots = useMemo(
    () =>
      [...(data?.plots || [])].sort(
        (a, b) =>
          Number(lead(b)) - Number(lead(a)) ||
          a.plot_id.localeCompare(b.plot_id),
      ),
    [data],
  );
  const filtered = plots.filter(
    (p) =>
      (filter === "all" || lead(p)) &&
      `${p.plot_id} ${p.supplier.a6_tier1_supplier_id} ${p.supplier.c2_deforestation_spatial_analysis_result}`
        .toLowerCase()
        .includes(query.toLowerCase()),
  );
  const plot = plots.find((p) => p.plot_id === selected) || plots[0];
  const selectionFiltered = !filtered.some((p) => p.plot_id === plot.plot_id);
  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key === "k") {
        e.preventDefault();
        setDialog("commands");
        return;
      }
      if (
        e.target instanceof HTMLInputElement ||
        e.target instanceof HTMLTextAreaElement ||
        dialog
      )
        return;
      if (e.key === "/") {
        e.preventDefault();
        search.current?.focus();
      }
      if ((e.key === "j" || e.key === "k") && filtered.length) {
        e.preventDefault();
        const i = filtered.findIndex((p) => p.plot_id === selected);
        setSelected(
          filtered[
            (i + (e.key === "j" ? 1 : -1) + filtered.length) % filtered.length
          ].plot_id,
        );
      }
    };
    window.addEventListener("keydown", handler);
    return () => window.removeEventListener("keydown", handler);
  }, [filtered, selected, dialog]);
  useEffect(() => {
    if (dialog) {
      if (!modal.current?.open) modal.current?.showModal();
    } else {
      modal.current?.close();
      if (pendingSearchFocus.current) {
        pendingSearchFocus.current = false;
        search.current?.focus();
      }
    }
  }, [dialog]);
  if (!data)
    return (
      <main className="load-screen">
        <div className="brand">
          plotline<span>↗</span>
        </div>
        {error ? (
          <>
            <EmptyState title="Evidence could not be loaded" detail={error} />
            <button onClick={load}>Retry loading</button>
          </>
        ) : (
          <p role="status">Loading local evidence…</p>
        )}
      </main>
    );
  return (
    <div className="app-shell">
      <header className="topbar">
        <a className="brand" href="#main">
          plotline<span>↗</span>
        </a>
        <div className="workspace-title">
          <span>Evidence workspace</span>
          <b>Lot 200001</b>
        </div>
        <nav aria-label="Workspace view">
          <button
            aria-pressed={view === "review"}
            onClick={() => setView("review")}
          >
            Review desk
          </button>
          <button aria-pressed={view === "proof"} onClick={() => showProof()}>
            Encoding proof
          </button>
        </nav>
        <button
          className="command-trigger"
          onClick={() => setDialog("commands")}
          aria-label="Open commands"
        >
          <Icon name="command" />
          <span>Commands</span>
          <kbd>⌘ K</kbd>
        </button>
        <span className="local-status">
          <i />
          Local sample
        </span>
      </header>
      <div className="workspace">
        <aside className="queue" aria-label="Supplier plot review queue">
          <div className="queue-heading">
            <span className="eyebrow">Submission / 200001</span>
            <h1>
              Follow the
              <br />
              evidence.
            </h1>
            <p>
              {plots.length} supplied plots.
              <br />
              Every answer has a trail.
            </p>
          </div>
          <div className="queue-summary">
            <strong>
              {String(plots.filter(lead).length).padStart(2, "0")}
            </strong>
            <span>
              declared indication
              <br />+ mitigation records
            </span>
          </div>
          <div className="search-field">
            <Icon name="search" size={16} />
            <input
              ref={search}
              aria-label="Search plots"
              value={query}
              placeholder="Find plot or supplier"
              onChange={(e) => setQuery(e.target.value)}
            />
            <kbd>/</kbd>
          </div>
          <div className="queue-filters">
            <button
              aria-pressed={filter === "all"}
              onClick={() => setFilter("all")}
            >
              All plots <span>{plots.length}</span>
            </button>
            <button
              aria-pressed={filter === "leads"}
              onClick={() => setFilter("leads")}
            >
              Review leads <span>{plots.filter(lead).length}</span>
            </button>
          </div>
          <div className="queue-list">
            {filtered.length ? (
              filtered.map((p) => (
                <button
                  key={p.plot_id}
                  className={`queue-row ${p.plot_id === selected ? "active" : ""}`}
                  aria-pressed={p.plot_id === selected}
                  onClick={() => setSelected(p.plot_id)}
                >
                  <div>
                    <strong>{p.plot_id}</strong>
                    <span>{p.supplier.a7_size_of_plot_ha} ha</span>
                  </div>
                  <small>
                    {lead(p)
                      ? "Indication → mitigation declared"
                      : "Supplier record"}
                  </small>
                  <span className="queue-row-bottom">
                    <i className={lead(p) ? "lead-dot" : "record-dot"} />
                    {lead(p)
                      ? "Evidence reference unresolved"
                      : "Inspect declared evidence"}
                    <Icon name="chevron" size={14} />
                  </span>
                </button>
              ))
            ) : (
              <>
                <EmptyState
                  title="No matching plots"
                  detail="Try a plot ID or clear the search."
                />
                <button
                  onClick={() => {
                    setQuery("");
                    setFilter("all");
                  }}
                >
                  Clear filters
                </button>
              </>
            )}
          </div>
          <div className="queue-footer">
            <span>Surat Thani · Chai Buri</span>
            <small>Origin as declared by supplier</small>
            <span className="keyboard-hint">
              <kbd>J</kbd>
              <kbd>K</kbd> Move through queue
            </span>
          </div>
        </aside>
        <main id="main" className="main-workspace">
          {error && (
            <div role="alert" className="selection-notice">
              Latest reload failed: {error}. Showing the last loaded evidence.
              <button onClick={load}>Retry</button>
            </div>
          )}
          <div className="plot-header">
            <div>
              <span className="eyebrow">
                Supplier {plot.supplier.a6_tier1_supplier_id}{" "}
                <span className="divider">/</span> Thailand{" "}
                <span className="divider">/</span>{" "}
                {view === "review" ? "Plot review" : "Encoding proof"}
              </span>
              <h2>
                {plot.plot_id}
                <span>
                  {plot.supplier.a7_size_of_plot_ha} <small>ha declared</small>
                </span>
              </h2>
            </div>
            <div className="plot-actions">
              <button onClick={() => setDialog("receipt")}>
                <Icon name="proof" />
                Receipt
              </button>
              <button
                className="pl-button--accent"
                id="plot-proof-trigger"
                onClick={() =>
                  view === "review" ? showProof() : setView("review")
                }
              >
                {view === "review" ? "Show proof" : "Back to review"}
                <Icon name="arrow" />
              </button>
            </div>
          </div>
          {selectionFiltered && (
            <div className="selection-notice">
              {plot.plot_id} remains open but is outside the current queue
              filter.{" "}
              <button
                onClick={() => {
                  setQuery("");
                  setFilter("all");
                }}
              >
                Show all plots
              </button>
            </div>
          )}
          {view === "review" && (
            <section
              className="review-brief"
              aria-label="Review reason and source context"
            >
              <div>
                <span className="eyebrow">Why this plot is in view</span>
                <p>
                  {lead(plot)
                    ? "Supplier declares an indication in 2021–2023 and mitigation with evidence. The referenced evidence file is unavailable."
                    : "Inspect the supplier’s declaration alongside the mapped observations; the supplied record is not independent verification."}
                </p>
                <p className="source-context">
                  <b>Current Hansen 2025 v1.13:</b>{" "}
                  {signal(
                    plot.source_result?.periods["2021-2023"]
                      ?.mapped_loss_present,
                  )}{" "}
                  in 2021–2023. Historical source release and query-rule
                  differences remain unresolved.
                </p>
              </div>
              <button
                onClick={() => {
                  const el = document.getElementById("supplier-declaration");
                  el?.focus({ preventScroll: true });
                  el?.scrollIntoView({ block: "start", behavior: "auto" });
                }}
              >
                Inspect declaration
                <Icon name="arrow" size={14} />
              </button>
            </section>
          )}
          {view === "review" ? (
            <div className="review-layout">
              <div className="spatial-column">
                <MapPanel
                  plot={plot}
                  plots={plots}
                  year={year}
                  onSelect={setSelected}
                />
                <Timeline
                  plot={plot}
                  year={year}
                  setYear={setYear}
                  onProof={() => showProof("count")}
                />
                <Observation plot={plot} />
              </div>
              <Declaration plot={plot} />
            </div>
          ) : (
            <Proof
              plot={plot}
              data={data}
              year={year}
              onReceipt={() => setDialog("receipt")}
            />
          )}
          <footer className="workspace-footer">
            <span>Hansen Global Forest Change 2025 v1.13 · CC BY 4.0</span>
            <span>Reproducible evidence. No legal determination.</span>
          </footer>
        </main>
      </div>
      <dialog
        ref={modal}
        aria-labelledby="workspace-dialog-title"
        onCancel={() => setDialog(null)}
        onClick={(e) => {
          if (e.target === e.currentTarget) setDialog(null);
        }}
      >
        <div className="dialog-header">
          <div>
            <span className="eyebrow">
              {dialog === "receipt" ? "Evidence receipt" : "Workspace commands"}
            </span>
            <h2 id="workspace-dialog-title">
              {dialog === "receipt"
                ? `${plot.plot_id} evidence receipt`
                : "Go directly to the evidence."}
            </h2>
          </div>
          <button aria-label="Close dialog" onClick={() => setDialog(null)}>
            <Icon name="close" />
          </button>
        </div>
        {dialog === "receipt" ? (
          <div className="receipt-body">
            <p>
              A reproducibility record, not a certification. Original supplier
              values and source metadata remain inspectable.
            </p>
            <dl className="receipt-summary">
              <div>
                <dt>Source product</dt>
                <dd>{String(data.dataset.product || "Unavailable")}</dd>
              </div>
              <div>
                <dt>Query contract</dt>
                <dd>{data.query_version}</dd>
              </div>
              <div>
                <dt>Spatial rule</dt>
                <dd>Native cell centers covered by exact plot polygon</dd>
              </div>
              <div>
                <dt>Observation / release</dt>
                <dd>Annual events 2001–2025 / Hansen 2025 v1.13</dd>
              </div>
              <div>
                <dt>Unknowns</dt>
                <dd>
                  {plot.source_result
                    ? plot.source_result.unknown_reasons.join(", ") ||
                      "None reported under this query"
                    : "Mapped result unavailable"}
                </dd>
              </div>
            </dl>
            <button
              className="pl-button--accent"
              onClick={() =>
                download(`${plot.plot_id}-receipt.json`, {
                  schema_version: data.schema_version,
                  plot_id: plot.plot_id,
                  receipt: plot.receipt,
                  supplier: plot.supplier,
                  comparison: plot.comparison,
                })
              }
            >
              <Icon name="download" />
              Download receipt JSON
            </button>
            <JsonDetails
              title="Hashes, grid and source provenance"
              value={plot.receipt}
            />
            <JsonDetails
              title="Exact supplier CSV fields"
              value={plot.supplier}
            />
            <JsonDetails title="Dataset metadata" value={data.dataset} />
            <JsonDetails
              title="Evidence limitations"
              value={data.limitations}
            />
          </div>
        ) : (
          <div className="command-list">
            <button
              onClick={() => {
                pendingSearchFocus.current = true;
                setDialog(null);
              }}
            >
              <Icon name="search" />
              Find a plot<kbd>/</kbd>
            </button>
            <button
              onClick={() => {
                showProof();
                setDialog(null);
              }}
            >
              <Icon name="layers" />
              Compare original and compact
              <Icon name="arrow" />
            </button>
            <button onClick={() => setDialog("receipt")}>
              <Icon name="proof" />
              Inspect {plot.plot_id} receipt
              <Icon name="arrow" />
            </button>
            <button
              disabled={loading}
              onClick={() => {
                load();
                setDialog(null);
              }}
            >
              <Icon name="layers" />
              {loading ? "Reloading local evidence…" : "Reload local evidence"}
              <Icon name="arrow" />
            </button>
          </div>
        )}
      </dialog>
    </div>
  );
}
