import { Icon } from "../components/Primitives";
import { comparisonState, sameValue } from "../comparison-state";
import type { Demo, Plot, Result } from "../types";

type Mark = "same" | "differs" | "unavailable" | "both-unknown";
type Row = { key: string; label: string; source: unknown; compact: unknown; id?: string };

const yearOf = (r: Result | null, year: number): number | null => {
  const v = r?.yearly_loss_counts?.[String(year)];
  return typeof v === "number" && Number.isFinite(v) ? v : null;
};
const periodField = (r: Result | null, period: string, field: "observed_loss_cell_count" | "mapped_loss_present") =>
  r?.periods?.[period]?.[field] ?? null;

function show(v: unknown): string {
  if (v === null || v === undefined) return "Unavailable";
  if (typeof v === "number") return v.toLocaleString("en-US");
  if (typeof v === "boolean") return v ? "yes" : "no";
  return String(v);
}

/** Row-level agreement. Two unknowns agree about being unknown, which is not a proof mark. */
function markFor(state: ReturnType<typeof comparisonState>, a: unknown, b: unknown): Mark {
  if (state === "unavailable") return "unavailable";
  const missA = a === null || a === undefined;
  const missB = b === null || b === undefined;
  if (missA && missB) return "both-unknown";
  return sameValue(a, b) ? "same" : "differs";
}

function MarkCell({ mark }: { mark: Mark }) {
  if (mark === "same")
    return (
      <span className="proof-mark proof-mark--same">
        <Icon name="check" size={14} />
        <span className="pl-sr-only">same</span>
      </span>
    );
  if (mark === "differs") return <span className="proof-mark proof-mark--differs">differs</span>;
  return (
    <span className="proof-mark proof-mark--unknown pl-hatch">
      {mark === "both-unknown" ? "both unknown" : "unavailable"}
    </span>
  );
}

function download(name: string, value: unknown) {
  const u = URL.createObjectURL(new Blob([JSON.stringify(value, null, 2)], { type: "application/json" }));
  const a = document.createElement("a");
  a.href = u;
  a.download = name;
  a.click();
  setTimeout(() => URL.revokeObjectURL(u), 1000);
}

export default function Comparison({
  plot,
  data,
  year,
  onReceipt,
  onOpenPlot,
}: {
  plot: Plot;
  data: Demo;
  year: number;
  onReceipt: () => void;
  onOpenPlot: (id: string, year: number) => void;
}) {
  const state = comparisonState(plot);
  const src = plot.source_result;
  const cmp = plot.compact_result;
  const periodKeys = Object.keys(src?.periods ?? cmp?.periods ?? {});
  const fieldRows: [string, keyof Result][] = [
    ["Selected native cells", "selected_cell_count"],
    ["Valid land cells", "valid_land_cell_count"],
    ["Unknown cells", "unknown_cell_count"],
    ["Out-of-coverage cells", "out_of_coverage_cell_count"],
    ["Support", "support"],
  ];
  const rows: Row[] = [
    { key: "year", id: "proof-selected-year", label: `${year} observed loss cells`, source: yearOf(src, year), compact: yearOf(cmp, year) },
    ...fieldRows.map(([label, k]) => ({ key: k, label, source: src ? src[k] : null, compact: cmp ? cmp[k] : null })),
    ...periodKeys.flatMap((k) => [
      {
        key: `${k}-count`,
        label: `${k.replace("-", "–")} loss cells`,
        source: periodField(src, k, "observed_loss_cell_count"),
        compact: periodField(cmp, k, "observed_loss_cell_count"),
      },
      {
        key: `${k}-flag`,
        label: `${k.replace("-", "–")} mapped loss present`,
        source: periodField(src, k, "mapped_loss_present"),
        compact: periodField(cmp, k, "mapped_loss_present"),
      },
    ]),
  ];
  const differing = plot.comparison?.differing_fields ?? [];

  return (
    <section className="proof-block" aria-labelledby="proof-compare-title">
      <header className="proof-block__head">
        <p className="pl-eyebrow">Selected plot</p>
        <h3 id="proof-compare-title">
          {plot.plot_id} <span className="pl-muted">· original vs compact</span>
        </h3>
      </header>

      {state === "match" && (
        <div className="pl-callout pl-callout--proof proof-verdict" role="status">
          <Icon name="check" size={20} />
          <div>
            <strong>Same query outputs</strong>
            <p>Exact equality of the full result for this plot. It shows encoding agreement, not source accuracy or compliance.</p>
          </div>
        </div>
      )}
      {state === "mismatch" && (
        <div className="pl-callout pl-callout--error proof-verdict" role="alert">
          <Icon name="alert" size={20} />
          <div>
            <strong>Encoding mismatch</strong>
            <p>
              A technical discrepancy between the two execution paths, not evidence about a supplier. Differing fields:{" "}
              {differing.length ? <code>{differing.join(", ")}</code> : "none listed in the export"}.
            </p>
          </div>
        </div>
      )}
      {state === "unavailable" && (
        <div className="pl-callout pl-callout--unknown proof-verdict" role="status">
          <Icon name="info" size={20} />
          <div>
            <strong>Compact comparison unavailable</strong>
            <p>The original answer is shown when computed. Compact results and agreement have not been measured for this plot.</p>
          </div>
        </div>
      )}

      <div className="pl-table-wrap proof-compare">
        <table className="pl-table">
          <caption>
            {plot.plot_id} · query {data.query_version} · native cells, not hectares
          </caption>
          <thead>
            <tr>
              <th scope="col">Field</th>
              <th scope="col">Original (GeoTIFF)</th>
              <th scope="col">Compact store</th>
              <th scope="col">Agree</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((r) => {
              const mark = markFor(state, r.source, r.compact);
              return (
                <tr key={r.key} id={r.id} tabIndex={r.id ? -1 : undefined} className={mark === "differs" ? "is-differs" : undefined}>
                  <th scope="row">{r.label}</th>
                  <td className={r.source == null ? "is-unknown pl-hatch" : undefined}>{show(r.source)}</td>
                  <td className={r.compact == null ? "is-unknown pl-hatch" : undefined}>{show(r.compact)}</td>
                  <td>
                    <MarkCell mark={mark} />
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>

      <div className="proof-actions">
        <button type="button" className="pl-btn pl-btn--primary" onClick={onReceipt}>
          <Icon name="proof" />
          Inspect provenance receipt
        </button>
        <button
          type="button"
          className="pl-btn"
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

      <div className="proof-plots" role="group" aria-label="Switch the proof to another plot">
        <span className="pl-eyebrow">All plots</span>
        {[...data.plots]
          .sort((a, b) => a.plot_id.localeCompare(b.plot_id))
          .map((p) => {
            const st = comparisonState(p);
            const word = st === "match" ? "same query outputs" : st === "mismatch" ? "encoding mismatch" : "comparison unavailable";
            return (
              <button
                type="button"
                key={p.plot_id}
                className={`pl-chip proof-plots__chip proof-plots__chip--${st}`}
                aria-pressed={p.plot_id === plot.plot_id}
                aria-label={`Proof for ${p.plot_id}: ${word}`}
                title={word}
                onClick={() => onOpenPlot(p.plot_id, year)}
              >
                {st === "match" && <Icon name="check" size={12} />}
                {st === "mismatch" && <Icon name="alert" size={12} />}
                {p.plot_id}
              </button>
            );
          })}
      </div>
    </section>
  );
}
