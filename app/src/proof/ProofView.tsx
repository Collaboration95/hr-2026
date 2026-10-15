// Redesign per design/DESIGN.md section 5.3. Keep ids #proof-heading and #proof-selected-year.
import { useState } from "react";
import Benchmark from "../Benchmark";
import EdgeLab from "../EdgeLab";
import { Chip } from "../components/Primitives";
import type { Demo, Plot } from "../types";
import type { DecisionState } from "../shell/useDecisionSummary";
import Comparison from "./Comparison";
import DecisionProof from "./DecisionProof";
import HeroStats from "./HeroStats";
import Research from "./Research";
import "../styles/proof.css";

function JsonDisclosure({ title, value }: { title: string; value: unknown }) {
  return (
    <details className="pl-disclosure">
      <summary>{title}</summary>
      <div className="pl-disclosure__body">
        <pre>
          {value == null ? "Unavailable: not computed or supplied." : JSON.stringify(value, null, 2)}
        </pre>
      </div>
    </details>
  );
}

/** Mounts the lab (and fetches its synthetic fixtures) only once it is first opened. */
function QueryLimitsLab() {
  const [opened, setOpened] = useState(false);
  return (
    <details
      className="pl-disclosure proof-lab"
      onToggle={(e) => {
        if ((e.currentTarget as HTMLDetailsElement).open) setOpened(true);
      }}
    >
      <summary>
        Query limits lab
        <span className="pl-disclosure__meta">fictitious 4×4 grid · synthetic</span>
      </summary>
      <div className="pl-disclosure__body">{opened && <EdgeLab />}</div>
    </details>
  );
}

export default function ProofView({
  plot,
  data,
  year,
  decision,
  onReceipt,
  onOpenPlot,
}: {
  plot: Plot;
  data: Demo;
  year: number;
  /** Optional decision-layer summary; the lossless audit tier below stands alone without it. */
  decision?: DecisionState;
  onReceipt: () => void;
  onOpenPlot: (id: string, year: number) => void;
}) {
  const summary = decision?.status === "ready" ? decision.summary : null;
  const auditLead =
    "Same boundary, grid, masks and query contract, compared on the original GeoTIFF inputs and on the compact store.";
  return (
    <section className="proof-view" aria-labelledby="proof-heading">
      {summary ? (
        <>
          <header className="proof-head">
            <p className="pl-eyebrow">Proof</p>
            <div className="proof-head__row">
              <h2 id="proof-heading" tabIndex={-1}>
                Keep the decision, <span>not the data.</span>
              </h2>
            </div>
            <p className="proof-head__lead">
              Not every pixel is needed to answer the EUDR screening question. These layers keep what the decision needs, and
              the answers are checked against the original layers.
            </p>
          </header>
          <DecisionProof summary={summary} />
        </>
      ) : (
        <header className="proof-head">
          <p className="pl-eyebrow">Proof</p>
          <div className="proof-head__row">
            <h2 id="proof-heading" tabIndex={-1}>
              Same question. <span>Two representations.</span>
            </h2>
            <Chip>
              {plot.plot_id} · {year}
            </Chip>
          </div>
          <p className="proof-head__lead">{auditLead}</p>
        </header>
      )}

      <section className="proof-audit" aria-labelledby={summary ? "proof-audit-title" : undefined} data-tier="audit">
        {summary && (
          <header className="proof-head proof-audit__head">
            <p className="pl-eyebrow">Audit tier</p>
            <div className="proof-head__row">
              <h3 id="proof-audit-title">
                Lossless audit tier (v1) <span>· same question, two representations</span>
              </h3>
              <Chip>
                {plot.plot_id} · {year}
              </Chip>
            </div>
            <p className="proof-head__lead">{auditLead}</p>
          </header>
        )}

        <HeroStats data={data} />

        <Comparison plot={plot} data={data} year={year} onReceipt={onReceipt} onOpenPlot={onOpenPlot} />

        <Benchmark value={data.benchmark} />
      </section>

      <div className="proof-more">
        <Research />
        <QueryLimitsLab />
        <JsonDisclosure title="Cohort summary (JSON)" value={data.summary} />
        <JsonDisclosure
          title="Full source and compact query outputs"
          value={{ source: plot.source_result, compact: plot.compact_result }}
        />
      </div>
    </section>
  );
}
