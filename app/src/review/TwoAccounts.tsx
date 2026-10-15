import { useId } from "react";
import type { ReactNode } from "react";
import { Glyph, Icon, Info } from "../components/Primitives";
import { JrcSummary } from "../JrcBaseline";
import type { JrcArtifact } from "../jrc-data";
import type { Plot } from "../types";
import type { DecisionState } from "../shell/useDecisionSummary";
import DecisionLayer from "./DecisionLayer";
import { cleanLabel, declaredIndication, evidenceReference, mappedLoss, periodCount, reviewQuestion } from "./plot-facts";
import { UnknownValue, fmtCount, unknownReason } from "./UnknownValue";
import "../styles/review.css";

export type JrcStatus = "idle" | "loading" | "ready" | "error";
export type TwoAccountsProps = {
  plot: Plot;
  jrc: JrcArtifact | null;
  jrcStatus: JrcStatus;
  jrcError?: string;
  onLoadJrc: () => void;
  /** Optional decision-layer summary; the EUDR decision block is omitted without it. */
  decision?: DecisionState;
};

function Fact({ label, title, children }: { label: string; title?: string; children: ReactNode }) {
  return (
    <div className="pl-fact">
      <dt>{label}</dt>
      <dd title={title}>{children}</dd>
    </div>
  );
}

/** Supplier text, verbatim. Missing is "Not supplied", never blank. */
const supplied = (v: string | undefined) => (typeof v === "string" && v.trim() ? v : "Not supplied");

/** YYYYMMDD → "04 Sep 2024"; anything else is shown verbatim. Never repairs or reorders dates. */
function supplierDate(v: string | undefined): string {
  if (typeof v !== "string" || !/^\d{8}$/.test(v)) return supplied(v);
  const d = new Date(`${v.slice(0, 4)}-${v.slice(4, 6)}-${v.slice(6, 8)}T00:00:00Z`);
  return Number.isNaN(d.valueOf()) ? v : new Intl.DateTimeFormat("en-GB", { day: "2-digit", month: "short", year: "numeric", timeZone: "UTC" }).format(d);
}

/** Observed loss cells for a period. Unknown (including partial support with no event) is hatched, never 0. */
function PeriodCount({ plot, period }: { plot: Plot; period: string }) {
  const count = periodCount(plot, period);
  if (count === null || mappedLoss(plot, period) === null) return <UnknownValue reason={unknownReason(plot)} />;
  return <span className={`pl-fact__num${count > 0 ? " is-loss" : ""}`}>{fmtCount(count)}</span>;
}

function Support({ plot }: { plot: Plot }) {
  const r = plot.source_result;
  if (!r) return <UnknownValue reason="not computed" />;
  if (r.support === "complete") return <span>complete</span>;
  return <UnknownValue label={r.support} reason={unknownReason(plot)} />;
}

function SelectedCells({ plot }: { plot: Plot }) {
  const n = plot.source_result?.selected_cell_count;
  return typeof n === "number" && Number.isFinite(n)
    ? <span className="pl-fact__num">{fmtCount(n)}</span>
    : <UnknownValue reason="not computed" />;
}

/** Wraps the evidence reference key in <code> so it reads as an opaque identifier. */
function QuestionText({ text, reference }: { text: string; reference: string | null }) {
  const at = reference ? text.indexOf(reference) : -1;
  if (!reference || at < 0) return <>{text}</>;
  return <>{text.slice(0, at)}<code>{reference}</code>{text.slice(at + reference.length)}</>;
}

function ReviewBand({ plot }: { plot: Plot }) {
  const q = reviewQuestion(plot);
  const body = <QuestionText text={q.text} reference={evidenceReference(plot)} />;
  if (q.kind === "question")
    return (
      <div className="pl-callout pl-callout--review">
        <Icon name="question" size={18} />
        <div className="pl-band__body"><strong>Question for review</strong><p>{body}</p></div>
      </div>
    );
  if (q.kind === "agree")
    return (
      <div className="pl-callout">
        <Icon name="check" size={18} />
        <div className="pl-band__body"><p>{body}</p></div>
      </div>
    );
  return (
    <div className="pl-callout pl-callout--unknown">
      <Icon name="info" size={18} />
      <div className="pl-band__body"><strong>Cannot compare</strong><p>{body}</p></div>
    </div>
  );
}

/**
 * ◆ Declared by supplier and ■ Mapped by Plotline, side by side with equal weight.
 * The two accounts are never merged into a verdict; the band asks a human a question.
 */
export default function TwoAccounts({ plot, jrc, jrcStatus, jrcError, onLoadJrc, decision }: TwoAccountsProps) {
  const uid = useId();
  const s = plot.supplier ?? {};
  const d = declaredIndication(plot);
  const reference = evidenceReference(plot);
  const rawReference = s.c4_reference_or_link_if_applicable;
  const c2 = s.c2_deforestation_spatial_analysis_result;
  return (
    <section className="pl-accounts" aria-label="Declared and mapped accounts">
      <div className="pl-accounts__cols">
        <section className="pl-account pl-account--declared" id="supplier-declaration" tabIndex={-1} aria-labelledby={`${uid}-declared`}>
          <header className="pl-account__head">
            <div className="pl-account__title"><h3 id={`${uid}-declared`}><Glyph kind="declared" /> Declared by supplier</h3></div>
            <p className="pl-account__source">Supplier fields, as supplied</p>
          </header>
          <dl className="pl-facts">
            <Fact label="Analysis layer" title={s.c1_indicate_deforestation_analysis_layer_used}>
              {supplied(s.c1_indicate_deforestation_analysis_layer_used)}
            </Fact>
            <Fact label="Result" title={c2}>
              <span className="pl-fact__flag">
                <Glyph kind={d === null ? "unknown" : "declared"} hollow={d === false} />
                <span>{cleanLabel(c2)}</span>
              </span>
            </Fact>
            <Fact label="Mitigation" title={s.c3_mitigation_if_indication_found}>{cleanLabel(s.c3_mitigation_if_indication_found)}</Fact>
            <Fact label="Final status" title={s.c5_deforestation_final_status}>{cleanLabel(s.c5_deforestation_final_status)}</Fact>
            <Fact label="EUDR (as declared)" title={s.i1_eudr_status}>{cleanLabel(s.i1_eudr_status)}</Fact>
            <Fact label="Processing dates" title={s.a4_processing_date}>
              {typeof s.a4_processing_date === "string" ? s.a4_processing_date.split("-").map(supplierDate).join(" – ") : "Not supplied"}
            </Fact>
            <Fact label="Harvest date" title={s.a5_production_harvest_date}>
              {supplierDate(s.a5_production_harvest_date)}
              <span className="pl-fact__note">date meanings need company clarification</span>
            </Fact>
            <Fact label="Evidence reference" title={typeof rawReference === "string" ? rawReference : undefined}>
              {reference ? (
                <>
                  <code className="pl-ref">{reference}</code>
                  <span className="pl-fact__note">file not supplied</span>
                </>
              ) : (
                <span>{typeof rawReference === "string" ? "Not applicable" : "Not supplied"}</span>
              )}
            </Fact>
          </dl>
        </section>

        <section className="pl-account pl-account--mapped" aria-labelledby={`${uid}-mapped`}>
          <header className="pl-account__head">
            <div className="pl-account__title">
              <h3 id={`${uid}-mapped`}><Glyph kind="loss" /> Mapped by Plotline</h3>
              <span className="pl-info-end">
                <Info label="About mapped values">
                  Mapped tree-cover loss is not a legal deforestation finding. Counts are native cells, not hectares. The current release may differ from the supplier&rsquo;s historical source.
                </Info>
              </span>
            </div>
            <p className="pl-account__source">Hansen 2025 v1.13 · centre rule</p>
          </header>
          <dl className="pl-facts pl-facts--grid">
            <Fact label="2021–23 loss cells"><PeriodCount plot={plot} period="2021-2023" /></Fact>
            <Fact label="2024–25 loss cells"><PeriodCount plot={plot} period="2024-2025" /></Fact>
            <Fact label="Support"><Support plot={plot} /></Fact>
            <Fact label="Selected cells"><SelectedCells plot={plot} /></Fact>
          </dl>
          <DecisionLayer plot={plot} decision={decision} />
          <div className="pl-account__jrc">
            <JrcSummary data={jrc} status={jrcStatus} error={jrcError} plotId={plot.plot_id} onLoad={onLoadJrc} />
          </div>
        </section>
      </div>
      <div className="pl-accounts__band"><ReviewBand plot={plot} /></div>
    </section>
  );
}
