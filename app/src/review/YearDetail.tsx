import { Icon, Info } from "../components/Primitives";
import { comparisonState } from "../comparison-state";
import type { Plot } from "../types";
import { yearCount } from "./plot-facts";
import { fmtCount, unknownReason } from "./UnknownValue";
import "../styles/review.css";

type ProofOrigin = "count" | "header";

/** Selected-year observed loss cells. The count is the entry point to the proof view. */
export default function YearDetail({ plot, year, onProof }: { plot: Plot; year: number; onProof: (origin: ProofOrigin) => void }) {
  const r = plot.source_result;
  const count = yearCount(plot, year);
  const selected = r?.selected_cell_count;
  const hasSelected = typeof selected === "number" && Number.isFinite(selected);
  // A zero without complete support is not a clear: say so rather than showing a bare 0.
  const unsureZero = count === 0 && r !== null && r.support !== "complete";
  return (
    <section className="pl-year" aria-label={`${year} observed loss`}>
      <div className="pl-year__top">
        <span className="pl-eyebrow">{year} · Observed loss cells</span>
        <span className="pl-year__unit">
          cells, not hectares
          <Info label="About cell counts">
            Counts are native Hansen cells (about 28 m each) whose centre falls inside the plot. They are not hectares.
          </Info>
        </span>
      </div>
      <button
        id="annual-proof-trigger"
        type="button"
        className="pl-year__count"
        aria-label={`Inspect proof for ${year} observed loss cells`}
        onClick={() => onProof("count")}
      >
        {count === null
          ? <span className="pl-year__unknown pl-hatch">Unknown</span>
          : <span className={`pl-year__num${count > 0 ? " is-loss" : ""}`}>{fmtCount(count)}</span>}
        <span className="pl-year__of">{hasSelected ? `of ${fmtCount(selected)} selected cells` : "selected cells unavailable"}</span>
        <Icon name="arrow" size={16} />
      </button>
      {count === null && <p className="pl-year__why">Unknown, not zero: {unknownReason(plot)}.</p>}
      {unsureZero && <p className="pl-year__why"><span className="pl-unknown__tag pl-hatch">support {r.support}</span> 0 observed. This is not a clear result.</p>}
    </section>
  );
}

/** One line answering "does the compact copy give the same answer?" Always links to the proof. */
export function CompactCopy({ plot, onProof }: { plot: Plot; onProof: (origin: ProofOrigin) => void }) {
  const state = comparisonState(plot);
  const fields = plot.comparison?.differing_fields ?? [];
  return (
    <div className={`pl-copyline pl-copyline--${state}`}>
      <button type="button" className="pl-copyline__btn" onClick={() => onProof("header")}>
        {state === "match" && <><Icon name="check" size={16} /><span>Same answer from the compact store</span></>}
        {state === "mismatch" && (
          <>
            <Icon name="alert" size={16} />
            <span>Encoding mismatch: <code>{fields.length ? fields.join(", ") : "stored results differ"}</code></span>
          </>
        )}
        {state === "unavailable" && <span className="pl-copyline__unknown pl-hatch">Compact comparison unavailable</span>}
        <Icon name="arrow" size={14} />
      </button>
      <Info label="About the compact comparison">
        {state === "match" && "The original and compact stores returned identical results for this plot. That is encoding fidelity, not satellite truth or legal compliance."}
        {state === "mismatch" && "A technical discrepancy between the two stores. It is not evidence about the supplier."}
        {state === "unavailable" && "No comparison has been established for this plot yet. That is different from a mismatch."}
      </Info>
    </div>
  );
}
