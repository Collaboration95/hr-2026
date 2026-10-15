import type { ReactNode } from "react";
import { Glyph, Info } from "../components/Primitives";
import { decisionFor, type DecisionOutput } from "../decision-data";
import { deforestFact, forestFact, yearsText } from "../decision-model";
import type { DecisionState } from "../shell/useDecisionSummary";
import type { Plot } from "../types";
import { UnknownValue, fmtCount } from "./UnknownValue";

function Fact({ label, glyph, title, children }: { label: string; glyph?: ReactNode; title?: string; children: ReactNode }) {
  return (
    <div className="pl-fact">
      <dt title={title}>
        {glyph}
        {label}
      </dt>
      <dd>{children}</dd>
    </div>
  );
}

/** The plot receipt carries the geometry digest the summary was computed for; absent means "cannot check". */
function receiptGeometry(plot: Plot): string | null {
  const r = plot.receipt;
  if (r === null || typeof r !== "object") return null;
  const v = (r as Record<string, unknown>).geometry_sha256;
  return typeof v === "string" ? v : null;
}

function Forest({ output }: { output: DecisionOutput }) {
  const f = forestFact(output);
  if (f.kind === "unknown") return <UnknownValue reason={f.reason} />;
  if (f.kind === "none")
    return (
      <>
        <span className="pl-fact__plain">none</span>
        <span className="pl-fact__note">0 of {fmtCount(f.landCells)} land cells</span>
      </>
    );
  return (
    <>
      <span>
        <span className="pl-fact__num is-forest">{fmtCount(f.count)}</span> <span className="pl-fact__unit">cells</span>
      </span>
      <span className="pl-fact__note">
        of {fmtCount(f.landCells)} land cells · {fmtCount(f.nonforest)} not forest · {fmtCount(f.unknown)} unknown
      </span>
    </>
  );
}

function Deforestation({ output }: { output: DecisionOutput }) {
  const d = deforestFact(output);
  if (d.kind === "unknown") return <UnknownValue reason={d.reason} />;
  if (d.kind === "none")
    return (
      <>
        <span className="pl-fact__plain">none mapped</span>
        <span className="pl-fact__note">0 cells, 2021–2025</span>
      </>
    );
  return (
    <>
      <span>
        <span className="pl-fact__num is-loss">{fmtCount(d.count)}</span> <span className="pl-fact__unit">cells</span>
      </span>
      <span className="pl-fact__note">{yearsText(d.years)}</span>
    </>
  );
}

function Support({ output }: { output: DecisionOutput }) {
  if (output.support === "complete") return <span>complete</span>;
  if (output.support === "partial")
    return (
      <>
        <span>partial</span>
        <span className="pl-fact__note">some selected cells are outside coverage or lack a JRC class</span>
      </>
    );
  return <UnknownValue label="none" reason="no analysed land cells" />;
}

/**
 * EUDR decision layer for one plot, from the optional decision-layer summary: forest at the 31 Dec 2020
 * cut-off and mapped loss on that forest since. Observational counts of Hansen cells; never a verdict.
 * Renders nothing while the summary is loading or unavailable, so the panel never shows a broken block.
 */
export default function DecisionLayer({ plot, decision }: { plot: Plot; decision?: DecisionState }) {
  if (decision?.status !== "ready" || !decision.summary) return null;
  const found = decisionFor(decision.summary, plot.plot_id, receiptGeometry(plot));
  if (found.status === "missing") return null;
  if (found.status === "stale")
    return (
      <section className="pl-decision" aria-label="EUDR decision layer" data-state="stale">
        <p className="pl-fine">
          EUDR decision layer not shown: this plot&rsquo;s boundary differs from the one the layer was computed for.
        </p>
      </section>
    );
  const output = found.output;
  return (
    <section className="pl-decision" aria-label="EUDR decision layer" data-state="ready">
      <header className="pl-decision__head">
        <h4>EUDR decision layer</h4>
        <span className="pl-info-end">
          <Info label="About the EUDR decision layer">
            Mapped observations from the decision layer ({output.contract}), the same answer as the original layers under
            the centre rule. Counts are Hansen cells, not hectares; JRC 2020 forest is read at each Hansen cell centre.
            Deforestation here counts only loss on land mapped as forest at the cut-off, so it can be lower than the
            Hansen loss cells above. This is not a legal finding.
          </Info>
        </span>
      </header>
      <dl className="pl-facts">
        <Fact label="Forest at 31 Dec 2020" glyph={<Glyph kind="forest" />} title="Forest at the EUDR cut-off, 31 Dec 2020">
          <Forest output={output} />
        </Fact>
        <Fact label="Loss on 2020 forest since cut-off" glyph={<Glyph kind="loss" />}>
          <Deforestation output={output} />
        </Fact>
        <Fact label="Decision-layer support">
          <Support output={output} />
        </Fact>
      </dl>
      <p className="pl-decision__source">{output.contract} · JRC at Hansen centres</p>
    </section>
  );
}
