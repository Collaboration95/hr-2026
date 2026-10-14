import { useEffect, useRef, useState } from "react";
import { Chip, Icon } from "../components/Primitives";
import AnalystNotes, { noteContextKey, useNoteState } from "../AnalystNotes";
import CellTable from "../CellTable";
import JrcBaseline from "../JrcBaseline";
import type { JrcArtifact } from "../jrc-data";
import type { Cell, Demo, Plot } from "../types";
import TwoAccounts from "./TwoAccounts";
import type { JrcStatus } from "./TwoAccounts";
import YearDetail, { CompactCopy } from "./YearDetail";
import { cleanLabel } from "./plot-facts";
import "../styles/review.css";

export type { JrcStatus };
export type PlotInspectorProps = {
  data: Demo;
  plot: Plot;
  year: number;
  jrc: JrcArtifact | null;
  jrcStatus: JrcStatus;
  jrcError?: string;
  onLoadJrc: () => void;
  onProof: (origin: "count" | "header") => void;
  onReceipt: () => void;
  onPinCell: (cell: Cell) => void;
};

const NO_CELLS: Cell[] = [];

function downloadJson(name: string, value: unknown) {
  const url = URL.createObjectURL(new Blob([JSON.stringify(value, null, 2) + "\n"], { type: "application/json" }));
  const link = document.createElement("a");
  link.href = url;
  link.download = name;
  document.body.append(link);
  link.click();
  link.remove();
  window.setTimeout(() => URL.revokeObjectURL(url), 1000);
}

/** Separate JRC source, lazy-loaded the first time the disclosure opens. Never combined with Hansen counts. */
function JrcDisclosure({ plotId, jrc, status, error, onLoad }: { plotId: string; jrc: JrcArtifact | null; status: JrcStatus; error?: string; onLoad: () => void }) {
  const [open, setOpen] = useState(false);
  const load = useRef(onLoad);
  useEffect(() => { load.current = onLoad; });
  useEffect(() => { if (open && status === "idle") load.current(); }, [open, status]);
  const plot = jrc?.plots.find((p) => p.plot_id === plotId);
  return (
    <details className="pl-disclosure pl-jrc" onToggle={(e) => setOpen(e.currentTarget.open)}>
      <summary>JRC 2020 baseline (separate source)</summary>
      <div className="pl-disclosure__body">
        {status === "ready" && jrc ? (
          <>
            <JrcBaseline data={jrc} plotId={plotId} />
            {plot && (
              <div>
                <button
                  type="button"
                  className="pl-btn pl-btn--sm"
                  onClick={() => downloadJson(`plotline-jrc-${plotId}.json`, {
                    schema_version: jrc.schema_version,
                    content_sha256: jrc.content_sha256,
                    dataset: jrc.dataset,
                    native_grid: jrc.native_grid,
                    plot,
                    limitations: jrc.limitations,
                  })}
                >
                  <Icon name="download" size={15} />Download separate JRC receipt
                </button>
              </div>
            )}
          </>
        ) : status === "error" || status === "ready" ? (
          <div className="pl-jrc__state" role="status">
            <p>{status === "error" ? (error || "JRC companion unavailable.") : "JRC companion unavailable."}</p>
            <p className="pl-fine">Hansen review is unaffected. No baseline absence is inferred.</p>
            <div><button type="button" className="pl-btn pl-btn--sm" onClick={onLoad}>Retry JRC baseline</button></div>
          </div>
        ) : (
          <p className="pl-jrc__state" role="status"><span className="pl-spinner" aria-hidden="true" /> Loading the separate JRC source…</p>
        )}
      </div>
    </details>
  );
}

function NoteDisclosure({ plot }: { plot: Plot }) {
  const contextKey = noteContextKey(plot);
  const state = useNoteState({ plotId: plot.plot_id, contextKey });
  const meta = { none: "", saved: "Saved", draft: "Unsaved draft", issue: "Storage issue" }[state];
  return (
    <details className="pl-disclosure">
      <summary>Analyst note{meta && <span className="pl-disclosure__meta">{meta}</span>}</summary>
      <div className="pl-disclosure__body">
        <AnalystNotes plotId={plot.plot_id} contextKey={contextKey} />
      </div>
    </details>
  );
}

/** Right-hand panel for one selected plot: two accounts, the selected year, and the evidence behind them. */
export default function PlotInspector({ data, plot, year, jrc, jrcStatus, jrcError, onLoadJrc, onProof, onReceipt, onPinCell }: PlotInspectorProps) {
  const s = plot.supplier ?? {};
  const area = typeof s.a7_size_of_plot_ha === "string" && s.a7_size_of_plot_ha.trim() ? s.a7_size_of_plot_ha : null;
  const supplier = typeof s.a6_tier1_supplier_id === "string" && s.a6_tier1_supplier_id.trim() ? s.a6_tier1_supplier_id : null;
  const product = typeof data.dataset.product === "string" ? data.dataset.product : "Hansen Global Forest Change 2025 v1.13";
  const license = typeof data.dataset.license === "string" ? ` · ${data.dataset.license}` : "";
  return (
    <article className="pl-review" aria-labelledby="plot-review-heading">
      <header className="pl-review__head">
        <div className="pl-review__title">
          <div>
            <h2 id="plot-review-heading" tabIndex={-1} className="pl-review__id">{plot.plot_id}</h2>
            <p className="pl-review__area" title={area ?? undefined}>{area ? <><span className="pl-num">{area}</span> ha declared</> : "Declared area not supplied"}</p>
          </div>
          <div className="pl-review__actions">
            <button type="button" className="pl-btn" onClick={onReceipt}><Icon name="proof" size={15} />Receipt</button>
            <button type="button" className="pl-btn pl-btn--primary" onClick={() => onProof("header")}>Proof<Icon name="arrow" size={16} /></button>
          </div>
        </div>
        <div className="pl-review__chips">
          <Chip title={s.a8_plantation_size_type}>{cleanLabel(s.a8_plantation_size_type)}</Chip>
          <Chip title={s.b1_supply_chain_type}>{cleanLabel(s.b1_supply_chain_type)}</Chip>
          <Chip title={s.a6_tier1_supplier_id}>Supplier {supplier ?? "not supplied"}</Chip>
        </div>
      </header>

      <TwoAccounts plot={plot} jrc={jrc} jrcStatus={jrcStatus} jrcError={jrcError} onLoadJrc={onLoadJrc} />

      <div className="pl-review__year">
        <YearDetail plot={plot} year={year} onProof={onProof} />
        <CompactCopy plot={plot} onProof={onProof} />
      </div>

      <div className="pl-review__more">
        <CellTable plotId={plot.plot_id} available={plot.evidence !== null} cells={plot.evidence?.features ?? NO_CELLS} year={year} onInspect={onPinCell} />
        <JrcDisclosure plotId={plot.plot_id} jrc={jrc} status={jrcStatus} error={jrcError} onLoad={onLoadJrc} />
        <NoteDisclosure plot={plot} />
      </div>

      <footer className="pl-review__foot">
        {product} (Hansen, UMD, Google, USGS, NASA){license}. Supplier fields are shown as supplied; Plotline adds no verdict.
      </footer>
    </article>
  );
}
