// Starting point extracted from the old App.tsx (owner: Cohort + proof agent).
// Redesign per design/DESIGN.md §5.3. Keep ids #proof-heading and #proof-selected-year.
import Benchmark from "../Benchmark";
import EdgeLab from "../EdgeLab";
import { Icon, Pill } from "../components/Primitives";
import { comparisonState } from "../comparison-state";
import type { Demo, Plot, Result } from "../types";

const fmt = (n: number | null | undefined) =>
  n == null ? "Unavailable" : n.toLocaleString();
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
export default function ProofView({
  plot,
  data,
  year,
  onReceipt,
}: {
  plot: Plot;
  data: Demo;
  year: number;
  onReceipt: () => void;
  onOpenPlot?: (id: string, year: number) => void;
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

