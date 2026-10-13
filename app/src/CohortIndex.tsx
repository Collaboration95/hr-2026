import { useId, useState } from "react";
import type { Demo, Plot } from "./types";
import { Icon } from "./components/Primitives";
import "./styles/cohort.css";

type Props = { data: Demo; onReview: (plotId: string, year: number) => void };
const views = [
  { key: "recent", label: "2024–2025", start: 2024, end: 2025 },
  { key: "earlier", label: "2021–2023", start: 2021, end: 2023 },
  { key: "all", label: "All years · 2001–2025", start: 2001, end: 2025 },
] as const;

const observed = (plot: Plot, year: number): number | null =>
  plot.source_result?.yearly_loss_counts?.[String(year)] ?? null;

function supportLabel(plot: Plot): string {
  switch (plot.source_result?.support) {
    case "complete":
      return "Complete support";
    case "partial":
      return "Partial support";
    case "none":
      return "No analytical support";
    default:
      return "Unavailable support";
  }
}

// Quote every field and neutralize spreadsheet formula prefixes in free text.
// Exported declarations retain their literal text in this explicitly escaped CSV.
function csvField(value: string | number): string {
  const raw = String(value);
  const escaped = /^[\s]*[=+\-@]/.test(raw) ? `'${raw}` : raw;
  return `"${escaped.replaceAll('"', '""')}"`;
}

/** Navigation over validated, frozen source results. No new queries or verdicts. */
export default function CohortIndex({ data, onReview }: Props) {
  const [viewKey, setViewKey] =
    useState<(typeof views)[number]["key"]>("recent");
  const [exportStatus, setExportStatus] = useState("");
  const id = useId();
  const view = views.find((v) => v.key === viewKey)!;
  const years = Array.from(
    { length: view.end - view.start + 1 },
    (_, i) => view.start + i,
  );
  const plots = [...data.plots].sort((a, b) =>
    a.plot_id.localeCompare(b.plot_id),
  );
  const rows = plots.map((plot) => {
    const counts = years.map((year) => observed(plot, year));
    const positiveYears = years.filter(
      (_, i) => counts[i] !== null && counts[i]! > 0,
    );
    return {
      plot,
      counts,
      reviewYear: positiveYears.at(-1) ?? view.end,
      hasLoss: positiveYears.length > 0,
      incomplete:
        plot.source_result?.support !== "complete" ||
        counts.some((n) => n === null),
    };
  });
  const availableCounts = rows.flatMap((row) =>
    row.counts.filter((n): n is number => n !== null),
  );
  const observedSum = availableCounts.length
    ? availableCounts.reduce((a, b) => a + b, 0)
    : null;
  const positivePlots = rows.filter((row) => row.hasLoss).length;
  const incompletePlots = rows.filter((row) => row.incomplete).length;
  const sourceProduct =
    typeof data.dataset.product === "string" && data.dataset.product.trim()
      ? data.dataset.product
      : "Mapped source unavailable";

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
          plot.supplier.c2_deforestation_spatial_analysis_result ??
            "Not supplied",
          sourceProduct,
          data.query_version,
          data.content_sha256 ?? "Unavailable",
          view.start,
          view.end,
          "Frozen source export; native cells per plot; overlapping plots can repeat cells; not area or a legal verdict",
        ]),
      );
      const csv =
        [header, ...body]
          .map((row) => row.map(csvField).join(","))
          .join("\r\n") + "\r\n";
      url = URL.createObjectURL(
        new Blob(["\uFEFF", csv], { type: "text/csv;charset=utf-8" }),
      );
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
      setExportStatus(
        "The CSV download could not be prepared. Your evidence is unchanged; try again.",
      );
    }
  }

  return (
    <section className="cohort-index" aria-labelledby={`${id}-title`}>
      <header className="cohort-heading">
        <div>
          <p className="cohort-kicker">Across the supplied plots</p>
          <h2 id={`${id}-title`}>Cohort / year evidence index</h2>
          <p className="cohort-intro">
            Follow an observed count to its plot and year. This navigates the
            frozen export; it does not run a new remote query.
          </p>
        </div>
        <button
          type="button"
          className="cohort-export"
          onClick={exportCsv}
          disabled={!plots.length}
        >
          <Icon name="download" size={16} />
          Export displayed counts · CSV
        </button>
      </header>
      <div
        className="cohort-controls"
        role="group"
        aria-label="Evidence index period"
      >
        {views.map((v) => (
          <button
            type="button"
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
      <p className="cohort-context">
        {sourceProduct} <span aria-hidden="true">·</span> Query:{" "}
        <code>{data.query_version}</code>
      </p>
      <dl
        className="cohort-overview"
        aria-label="Displayed source observations"
      >
        <div>
          <dt>Plots with observed loss</dt>
          <dd>
            {positivePlots} <span>/ {plots.length} in this view</span>
          </dd>
        </div>
        <div>
          <dt>Observed cells summed across plots</dt>
          <dd>
            {observedSum === null
              ? "Unavailable"
              : observedSum.toLocaleString()}{" "}
            <span>
              {observedSum !== null
                ? "available counts"
                : "no available counts"}
            </span>
          </dd>
        </div>
        <div>
          <dt>Incomplete or unavailable support</dt>
          <dd>
            {incompletePlots} <span>plots</span>
          </dd>
        </div>
      </dl>
      <p className="cohort-guide" id={`${id}-guide`}>
        <strong>0</strong> = zero observed cells. <strong>Unknown</strong> =
        count unavailable. For partial support, zero does not establish absence;
        positive observations remain evidence. Supplier indications are
        declarations, separate from mapped tree-cover loss. Neither is a
        compliance verdict.
      </p>
      <div
        className="cohort-table-scroll"
        role="region"
        aria-label="Plot and year evidence table; scroll horizontally for more columns"
        aria-describedby={`${id}-guide ${id}-navigation`}
        tabIndex={0}
      >
        <table className="cohort-table">
          <caption>
            {plots.length} supplied plots · {view.start}–{view.end} · source
            observed tree-cover-loss cells
          </caption>
          <thead>
            <tr>
              <th scope="col" rowSpan={2} className="cohort-identity">
                Plot / support
              </th>
              <th scope="colgroup" colSpan={years.length}>
                Observed tree-cover-loss cells
              </th>
              <th scope="col" rowSpan={2} className="cohort-declaration">
                Supplier indication{" "}
                <span>Declared · not independently verified</span>
              </th>
            </tr>
            <tr>
              {years.map((year) => (
                <th scope="col" key={year}>
                  {year}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {rows.map(({ plot, counts, reviewYear }) => (
              <tr key={plot.plot_id}>
                <th scope="row" className="cohort-identity">
                  <button
                    type="button"
                    onClick={() => onReview(plot.plot_id, reviewYear)}
                    aria-label={`Review ${plot.plot_id}, ${reviewYear}`}
                  >
                    {plot.plot_id}
                    <Icon name="arrow" size={13} />
                  </button>
                  <span className="cohort-support">{supportLabel(plot)}</span>
                </th>
                {years.map((year, i) => {
                  const count = counts[i];
                  return (
                    <td
                      key={year}
                      className={
                        count === null
                          ? "cohort-unknown"
                          : count > 0
                            ? "cohort-positive"
                            : "cohort-zero"
                      }
                    >
                      {count === null ? (
                        <span>Unknown</span>
                      ) : count > 0 ? (
                        <button
                          type="button"
                          onClick={() => onReview(plot.plot_id, year)}
                          aria-label={`Review ${plot.plot_id}, ${year}: ${count} observed loss ${count === 1 ? "cell" : "cells"}${plot.source_result?.support === "partial" ? "; partial support" : ""}`}
                        >
                          {count.toLocaleString()}
                          <Icon name="arrow" size={12} />
                        </button>
                      ) : (
                        <span>
                          0
                          <span className="pl-sr-only">
                            {" "}
                            observed loss cells
                            {plot.source_result?.support === "partial"
                              ? "; partial support, absence unknown"
                              : ""}
                          </span>
                        </span>
                      )}
                    </td>
                  );
                })}
                <td className="cohort-declaration">
                  {plot.supplier.c2_deforestation_spatial_analysis_result ||
                    "Not supplied"}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      {!plots.length && (
        <p className="cohort-guide">
          No supplied plots are available in this export.
        </p>
      )}
      <p className="cohort-guide" id={`${id}-navigation`}>
        Plot IDs open the latest year with observed loss in the displayed
        period, or its final year when none is observed. Positive counts open
        that exact year. Scroll the table horizontally to inspect more columns.
      </p>
      <p className="cohort-footnote">
        Summed cells are observations per plot. Overlapping polygons can count
        the same cell more than once; these totals are not unique regional cells
        or hectares.
      </p>
      <p className="cohort-export-status" role="status" aria-live="polite">
        {exportStatus}
      </p>
    </section>
  );
}
