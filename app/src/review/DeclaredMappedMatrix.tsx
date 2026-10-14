import { Glyph } from "../components/Primitives";
import type { Plot } from "../types";
import { ANALYSIS_PERIOD, declaredIndication, mappedLoss } from "./plot-facts";
import "../styles/review.css";

type Declared = boolean | null;
type Mapped = boolean | null;

export type DeclaredMappedMatrixProps = {
  plots: Plot[];
  onSelectPlot: (id: string) => void;
  /** Mapped period used for the columns. Defaults to the supplier's 2021-2023 window. */
  period?: string;
  /** Visible caption. Defaults to a short description of the period. */
  caption?: string;
};

const rows: { key: string; declared: Declared; glyph: "declared" | "unknown"; hollow?: boolean; label: string }[] = [
  { key: "indication", declared: true, glyph: "declared", label: "Declared indication" },
  { key: "none", declared: false, glyph: "declared", hollow: true, label: "Declared none" },
  { key: "unrecognised", declared: null, glyph: "unknown", label: "Declared unknown" },
];
const cols: { key: string; mapped: Mapped; glyph: "loss" | "unknown"; hollow?: boolean; label: string }[] = [
  { key: "loss", mapped: true, glyph: "loss", label: "Mapped loss" },
  { key: "clear", mapped: false, glyph: "loss", hollow: true, label: "No mapped loss" },
  { key: "unknown", mapped: null, glyph: "unknown", label: "Unknown" },
];

/**
 * Declared (supplier) vs mapped (Hansen export) for one period. Plot IDs are buttons.
 * Where the two accounts differ the cell is amber: a question for review, not a finding.
 * Reusable: it only needs validated plots and a select handler.
 */
export default function DeclaredMappedMatrix({ plots, onSelectPlot, period = ANALYSIS_PERIOD, caption }: DeclaredMappedMatrixProps) {
  const label = period.replace("-", "–");
  const idsFor = (d: Declared, m: Mapped) => plots.filter((p) => declaredIndication(p) === d && mappedLoss(p, period) === m).map((p) => p.plot_id);
  // The "declared unknown" row only appears when a supplier result is missing or unrecognised.
  const visibleRows = rows.filter((r) => r.declared !== null || plots.some((p) => declaredIndication(p) === null));
  return (
    <div className="pl-matrix-wrap">
      <table className="pl-matrix">
        <caption>{caption ?? `Supplier declaration vs mapped loss, ${label}`}</caption>
        <colgroup><col className="is-rowhead" /><col className="is-main" /><col className="is-main" /><col className="is-unknown" /></colgroup>
        <thead>
          <tr>
            <td aria-hidden="true" />
            {cols.map((c) => (
              <th key={c.key} scope="col"><Glyph kind={c.glyph} hollow={c.hollow} /> {c.label}</th>
            ))}
          </tr>
        </thead>
        <tbody>
          {visibleRows.map((r) => (
            <tr key={r.key}>
              <th scope="row"><Glyph kind={r.glyph} hollow={r.hollow} /> {r.label}</th>
              {cols.map((c) => {
                const ids = idsFor(r.declared, c.mapped);
                const differs = r.declared !== null && c.mapped !== null && r.declared !== c.mapped;
                const unknown = r.declared === null || c.mapped === null;
                return (
                  <td key={c.key} className={`pl-matrix__cell${differs ? " is-differ" : ""}${unknown ? " is-unknown pl-hatch" : ""}`}>
                    <span className={`pl-matrix__n${ids.length ? "" : " is-zero"}`}>{ids.length}{differs && ids.length > 0 && <Glyph kind="review" />}</span>
                    {ids.length > 0 && (
                      <span className="pl-matrix__ids">
                        {ids.map((id) => (
                          <button key={id} type="button" className="pl-matrix__id" onClick={() => onSelectPlot(id)}>{id}</button>
                        ))}
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
  );
}
