import { useId, useMemo, useState, type CSSProperties } from "react";
import type { Demo, Plot } from "./types";
import type { JrcArtifact } from "./jrc-data";
import { Glyph, Icon } from "./components/Primitives";
import {
  ANALYSIS_PERIOD,
  YEARS,
  cleanLabel,
  declaredIndication,
  lossYears,
  mappedLoss,
  yearCount,
} from "./review/plot-facts";
import "./styles/cohort.css";

type Props = {
  data: Demo;
  jrc: JrcArtifact | null;
  onReview: (plotId: string, year: number) => void;
};
const views = [
  { key: "all", label: "All years · 2001–2025", start: 2001, end: 2025 },
  { key: "earlier", label: "2021–2023", start: 2021, end: 2023 },
  { key: "recent", label: "2024–2025", start: 2024, end: 2025 },
] as const;

// Supplier analysis window and EUDR cut-off (31 Dec 2020).
const WINDOW = { start: 2021, end: 2023 };

// Quote every field and neutralize spreadsheet formula prefixes in free text.
// Exported declarations retain their literal text in this explicitly escaped CSV.
function csvField(value: string | number): string {
  const raw = String(value);
  const escaped = /^[\s]*[=+\-@]/.test(raw) ? `'${raw}` : raw;
  return `"${escaped.replaceAll('"', '""')}"`;
}

/** Hansen loss-cell intensity on a log scale, as a color-mix percentage of the ember hue. */
function emberPct(count: number, max: number): number {
  return Math.round(20 + 80 * (Math.log1p(count) / Math.log1p(Math.max(max, 1))));
}

const declLabel = (d: boolean | null) => (d === true ? "declared indication" : d === false ? "declared none" : "declaration unknown");
const mapLabel = (m: boolean | null) => (m === true ? "mapped loss" : m === false ? "no mapped loss" : "mapped unknown");

/** JRC forest-class cells over selected JRC cells, on the JRC grid. Never combined with Hansen counts. */
function jrcCells(jrc: JrcArtifact, plotId: string): string | null {
  const r = jrc.plots.find((p) => p.plot_id === plotId)?.source_result;
  const forest = r?.class_counts?.["1"];
  return r && typeof forest === "number" && typeof r.selected_cell_count === "number"
    ? `${forest.toLocaleString("en-US")} / ${r.selected_cell_count.toLocaleString("en-US")}`
    : null;
}

/** Navigation over validated, frozen source results. No new queries or verdicts. */
export default function CohortIndex({ data, jrc, onReview }: Props) {
  const [viewKey, setViewKey] = useState<(typeof views)[number]["key"]>("all");
  const [exportStatus, setExportStatus] = useState("");
  const uid = useId();
  const view = views.find((v) => v.key === viewKey)!;
  const years = useMemo(() => YEARS.filter((y) => y >= view.start && y <= view.end), [view]);
  const plots = useMemo(
    () => [...data.plots].sort((a, b) => a.plot_id.localeCompare(b.plot_id)),
    [data.plots],
  );
  const rows = plots.map((plot) => {
    const counts = years.map((year) => yearCount(plot, year));
    const positiveYears = years.filter((_, i) => counts[i] !== null && counts[i]! > 0);
    return { plot, counts, reviewYear: positiveYears.at(-1) ?? view.end };
  });
  // One scale for every period view, so intensities stay comparable when the chips change.
  const maxCount = useMemo(
    () => Math.max(1, ...plots.flatMap((p) => YEARS.map((y) => yearCount(p, y) ?? 0))),
    [plots],
  );
  const sourceProduct =
    typeof data.dataset.product === "string" && data.dataset.product.trim()
      ? data.dataset.product
      : "Mapped source unavailable";

  /* ----- declared vs mapped matrix (2021–2023, the supplier's analysis window) ----- */
  const facts = plots.map((plot) => ({
    plot,
    d: declaredIndication(plot),
    m: mappedLoss(plot, ANALYSIS_PERIOD),
    year: lossYears(plot, WINDOW.start, WINDOW.end).at(-1) ?? WINDOW.end,
  }));
  const declRows: { d: boolean | null; label: string }[] = [
    { d: true, label: "Declared indication" },
    { d: false, label: "Declared none" },
    ...(facts.some((f) => f.d === null) ? [{ d: null, label: "Declared unknown" }] : []),
  ];
  const mapCols: { m: boolean | null; label: string }[] = [
    { m: true, label: "Mapped loss" },
    { m: false, label: "No mapped loss" },
    { m: null, label: "Unknown" },
  ];

  function exportCsv() {
    let url: string | undefined;
    try {
      const header = [
        "plot_id",
        "year",
        "observed_loss_cell_count",
        "count_state",
        "selected_support",
        "supplier_indication_declared",
        "source_product",
        "query_version",
        "artifact_content_sha256",
        "view_start_year",
        "view_end_year",
        "count_basis",
      ];
      const body = rows.flatMap(({ plot, counts }) =>
        years.map((year, i) => [
          plot.plot_id,
          year,
          counts[i] === null ? "Unknown" : counts[i]!,
          counts[i] === null ? "unavailable" : "observed",
          plot.source_result?.support ?? "unavailable",
          plot.supplier.c2_deforestation_spatial_analysis_result ?? "Not supplied",
          sourceProduct,
          data.query_version,
          data.content_sha256 ?? "Unavailable",
          view.start,
          view.end,
          "Frozen source export; native cells per plot; overlapping plots can repeat cells; not area or a legal verdict",
        ]),
      );
      const csv = [header, ...body].map((row) => row.map(csvField).join(",")).join("\r\n") + "\r\n";
      url = URL.createObjectURL(new Blob(["﻿", csv], { type: "text/csv;charset=utf-8" }));
      const link = document.createElement("a");
      link.href = url;
      link.download = `plotline-source-counts-${view.start}-${view.end}.csv`;
      document.body.append(link);
      try {
        link.click();
      } finally {
        link.remove();
      }
      const exportedUrl = url;
      window.setTimeout(() => URL.revokeObjectURL(exportedUrl), 1000);
      setExportStatus(
        `CSV download requested: ${plots.length} plots × ${years.length} years. Unknown values are explicit; spreadsheet formula prefixes in text are escaped.`,
      );
    } catch {
      if (url) URL.revokeObjectURL(url);
      setExportStatus("The CSV download could not be prepared. Your evidence is unchanged; try again.");
    }
  }

  /* ----- column overlays ----- */
  const compact = years.length <= 12; // few columns: show full years and let cells grow
  const cutVisible = years.includes(2021);
  const beforeCut = years.filter((y) => y < 2021).length;
  const windowYears = years.filter((y) => y >= WINDOW.start && y <= WINDOW.end);
  const beforeWindow = years.filter((y) => y < WINDOW.start).length;
  const afterWindow = years.length - beforeWindow - windowYears.length;
  const yearClass = (y: number) =>
    `${y === 2021 ? " co-cut" : ""}${y >= WINDOW.start && y <= WINDOW.end ? " co-window" : ""}`;
  const partialNote = (p: Plot) => (p.source_result?.support === "partial" ? "; partial support" : "");

  return (
    <section className="cohort" aria-labelledby="cohort-heading">
      <header className="co-head">
        <div className="co-head__title">
          <p className="pl-eyebrow">Cohort</p>
          <h2 id="cohort-heading" tabIndex={-1}>
            {plots.length} plots × 25 years
          </h2>
          <p className="pl-muted co-scope">
            All {plots.length} plots. Rail filters on the Map don&apos;t apply here.
          </p>
        </div>
        <div className="co-tools">
          <div className="co-periods" role="group" aria-label="Period shown in the loss barcode">
            {views.map((v) => (
              <button
                type="button"
                className="pl-chip"
                key={v.key}
                aria-pressed={viewKey === v.key}
                onClick={() => {
                  setViewKey(v.key);
                  setExportStatus("");
                }}
              >
                {v.label}
              </button>
            ))}
          </div>
          <button type="button" className="pl-btn" onClick={exportCsv} disabled={!plots.length}>
            <Icon name="download" size={16} />
            Export displayed counts · CSV
          </button>
        </div>
      </header>

      {!plots.length && <p className="pl-muted">No supplied plots are available in this export.</p>}

      {/* ---------------- Declared vs mapped ---------------- */}
      <section className="co-matrix-block" aria-labelledby={`${uid}-matrix`}>
        <h3 id={`${uid}-matrix`}>
          Declared vs mapped <span className="pl-muted">· 2021–2023</span>
        </h3>
        <p className="pl-muted co-matrix-sub">
          <span className="co-matrix-sub__item">
            <Glyph kind="declared" /> what the supplier declared
          </span>
          <span className="co-matrix-sub__item">
            <Glyph kind="loss" /> what the Hansen layer maps under the centre rule
          </span>
          <span>Two accounts, never merged.</span>
        </p>
        <div className="pl-table-wrap">
          <table className="pl-table co-matrix">
            <caption>
              Plots by supplier declaration (rows) and mapped tree-cover loss in 2021–2023 (columns). Plot IDs open the
              plot on the map.
            </caption>
            <colgroup><col className="co-matrix__decl" /><col className="co-matrix__mapped" /><col className="co-matrix__mapped" /><col className="co-matrix__unknown" /></colgroup>
            <thead>
              <tr>
                <th scope="col">
                  <span className="pl-sr-only">Supplier declaration</span>
                </th>
                {mapCols.map((c) => (
                  <th scope="col" key={String(c.m)} className="co-matrix__col">
                    <Glyph kind={c.m === null ? "unknown" : "loss"} hollow={c.m === false} /> {c.label}
                    <span className="co-matrix__total pl-num">{facts.filter((f) => f.m === c.m).length}</span>
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {declRows.map((r) => (
                <tr key={String(r.d)}>
                  <th scope="row" className="co-matrix__row">
                    <Glyph kind={r.d === null ? "unknown" : "declared"} hollow={r.d === false} /> {r.label}
                    <span className="co-matrix__total pl-num">{facts.filter((f) => f.d === r.d).length}</span>
                  </th>
                  {mapCols.map((c) => {
                    const cell = facts.filter((f) => f.d === r.d && f.m === c.m);
                    const disagree = r.d !== null && c.m !== null && r.d !== c.m;
                    return (
                      <td key={String(c.m)} className={disagree ? "co-matrix__ask" : undefined}>
                        {cell.length === 0 ? (
                          <span className="co-matrix__none pl-num">0</span>
                        ) : (
                          <span className="co-ids">
                            {cell.map((f) => (
                              <button
                                type="button"
                                className="co-id"
                                key={f.plot.plot_id}
                                aria-label={`${f.plot.plot_id}, ${declLabel(f.d)}, ${mapLabel(f.m)}: open ${f.year}`}
                                onClick={() => onReview(f.plot.plot_id, f.year)}
                              >
                                {f.plot.plot_id}
                              </button>
                            ))}
                          </span>
                        )}
                        {disagree && cell.length > 0 && (
                          <span className="co-matrix__q">
                            <Glyph kind="review" /> review question
                          </span>
                        )}
                      </td>
                    );
                  })}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <p className="pl-fine co-footnote">
          Two explanations were tested and do not account for the difference: Hansen 2023 v1.11 (the supplier&apos;s era)
          gives the same 2021–23 counts, and a footprint-overlap rule flags different plots. Differences are review
          questions, not findings.
        </p>
      </section>

      {/* ---------------- Loss barcode ---------------- */}
      <section className="co-barcode-block" aria-labelledby={`${uid}-barcode`}>
        <h3 id={`${uid}-barcode`}>Loss barcode</h3>
        <p className="co-legend" aria-label="Legend">
          <span>
            <Glyph kind="declared" /> declared indication <Glyph kind="declared" hollow /> none
          </span>
          <span className="co-legend__ramp">
            <Glyph kind="loss" /> mapped loss cells, log scale
            <i className="co-ramp" aria-hidden="true" />
            <span className="pl-num">1 to {maxCount}</span>
          </span>
          <span>
            <i className="co-dot co-dot--legend" aria-hidden="true" /> 0
          </span>
          <span>
            <Glyph kind="unknown" /> unknown
          </span>
          {jrc && (
            <span>
              <Glyph kind="forest" /> JRC forest cells (own grid)
            </span>
          )}
        </p>
        <div
          className="co-scroll"
          role="region"
          aria-label="Loss barcode, plots by year; scroll horizontally for more years"
          tabIndex={0}
        >
          <table
            className={`co-barcode${compact ? " is-compact" : ""}${jrc ? " has-jrc" : ""}`}
            style={{ "--co-n": years.length } as CSSProperties}
          >
            <caption className="pl-sr-only">
              {plots.length} plots, {view.start}–{view.end}: observed tree-cover-loss cells per year from {sourceProduct}.
              Zero is a known zero; unknown is a count that is unavailable. Native cells, not hectares. 2021–2023 is the
              supplier&apos;s analysis window and the EUDR cut-off is 31 December 2020.
            </caption>
            <colgroup>
              <col className="co-col-id" />
              <col className="co-col-decl" />
              {years.map((y) => (
                <col key={y} />
              ))}
              {jrc && <col className="co-col-jrc" />}
            </colgroup>
            <thead>
              {cutVisible && (
                <tr className="co-overlay" aria-hidden="true">
                  <th colSpan={2} className="co-sticky co-sticky--ov" />
                  {beforeCut > 0 ? (
                    <>
                      <th colSpan={beforeCut} className="co-ov">
                        <span className="co-ov__label co-ov__label--end">EUDR cut-off · 31 Dec 2020</span>
                      </th>
                      <th colSpan={years.length - beforeCut} className="co-ov co-cut" />
                    </>
                  ) : (
                    <th colSpan={years.length} className="co-ov co-cut">
                      <span className="co-ov__label co-ov__label--start">EUDR cut-off · 31 Dec 2020</span>
                    </th>
                  )}
                  {jrc && <th className="co-ov" />}
                </tr>
              )}
              {windowYears.length > 0 && (
                <tr className="co-overlay" aria-hidden="true">
                  <th colSpan={2} className="co-sticky co-sticky--ov" />
                  {beforeWindow > 0 && <th colSpan={beforeWindow} className="co-ov" />}
                  <th colSpan={windowYears.length} className="co-ov co-ov--window">
                    <span className={`co-ov__label ${beforeWindow > 0 ? "co-ov__label--end" : "co-ov__label--center"}`}>
                      Supplier analysis 2021–23
                    </span>
                  </th>
                  {afterWindow > 0 && <th colSpan={afterWindow} className="co-ov" />}
                  {jrc && <th className="co-ov" />}
                </tr>
              )}
              <tr>
                <th scope="col" className="co-sticky co-sticky--id">
                  Plot
                </th>
                <th scope="col" className="co-sticky co-sticky--decl">
                  <Glyph kind="declared" />{" "}
                  <span className="co-decl-text">
                    Declared <span className="co-faint">2021–23</span>
                  </span>
                </th>
                {years.map((y) => (
                  <th scope="col" key={y} className={`co-year${yearClass(y)}`}>
                    {compact ? (
                      y
                    ) : (
                      <>
                        <span aria-hidden="true">{String(y).slice(2)}</span>
                        <span className="pl-sr-only">{y}</span>
                      </>
                    )}
                  </th>
                ))}
                {jrc && (
                  <th scope="col" className="co-jrc">
                    <Glyph kind="forest" /> JRC 2020 forest cells
                    <span className="co-faint co-jrc__sub">(JRC grid)</span>
                  </th>
                )}
              </tr>
            </thead>
            <tbody>
              {rows.map(({ plot, counts, reviewYear }) => {
                const d = declaredIndication(plot);
                return (
                  <tr key={plot.plot_id}>
                    <th scope="row" className="co-sticky co-sticky--id">
                      <button
                        type="button"
                        className="co-plot"
                        onClick={() => onReview(plot.plot_id, reviewYear)}
                        aria-label={`Open ${plot.plot_id}, ${reviewYear}`}
                      >
                        {plot.plot_id}
                      </button>
                    </th>
                    <td className="co-sticky co-sticky--decl" title={declLabel(d)}>
                      <Glyph kind={d === null ? "unknown" : "declared"} hollow={d === false} />{" "}
                      <span className="co-decl-text">
                        {cleanLabel(plot.supplier?.c2_deforestation_spatial_analysis_result)}
                      </span>
                    </td>
                    {years.map((year, i) => {
                      const count = counts[i];
                      const cls = `co-cell${yearClass(year)}`;
                      if (count === null)
                        return (
                          <td key={year} className={`${cls} co-cell--unknown pl-hatch`} title={`${plot.plot_id}, ${year}: unknown`}>
                            <span className="pl-sr-only">unknown</span>
                          </td>
                        );
                      if (count > 0) {
                        const pct = emberPct(count, maxCount);
                        return (
                          <td key={year} className={`${cls} co-cell--hit`} style={{ "--co-pct": `${pct}%` } as CSSProperties}>
                            <button
                              type="button"
                              className={`co-hit${pct >= 72 ? " is-strong" : ""}`}
                              onClick={() => onReview(plot.plot_id, year)}
                              aria-label={`Review ${plot.plot_id}, ${year}: ${count} observed loss ${count === 1 ? "cell" : "cells"}${partialNote(plot)}`}
                            >
                              {count.toLocaleString("en-US")}
                            </button>
                          </td>
                        );
                      }
                      const partial = plot.source_result?.support !== "complete";
                      return (
                        <td key={year} className={`${cls} co-cell--zero`}>
                          <i className={`co-dot${partial ? " is-partial" : ""}`} aria-hidden="true" />
                          <span className="pl-sr-only">
                            0 observed loss cells{partial ? "; support not complete, absence unknown" : ""}
                          </span>
                        </td>
                      );
                    })}
                    {jrc && (
                      <td className="co-jrc pl-num">
                        {jrcCells(jrc, plot.plot_id) ?? <span className="co-faint">Unavailable</span>}
                      </td>
                    )}
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
        <p className="pl-fine co-context">
          {sourceProduct} · query <code>{data.query_version}</code> · native cells per plot, not hectares; overlapping
          plots can repeat cells. A plot ID opens the latest year with loss in the shown period.
          {jrc && " JRC counts are forest-class cells on JRC's own grid and are never added to Hansen counts."}
        </p>
      </section>

      <p className="co-export-status pl-fine" role="status" aria-live="polite">
        {exportStatus}
      </p>
    </section>
  );
}
