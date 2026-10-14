// STUB (owner: Inspector agent). See design/DESIGN.md §5.1 "Inspector, plot detail".
import type { Cell, Demo, Plot } from "../types";
import type { JrcArtifact } from "../jrc-data";
export type JrcStatus = "idle" | "loading" | "ready" | "error";
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
export default function PlotInspector({ plot, year, onProof, onReceipt }: PlotInspectorProps) {
  return (
    <section aria-label="Plot detail">
      <h2 id="plot-review-heading" tabIndex={-1}>{plot.plot_id}</h2>
      <button onClick={onReceipt}>Receipt</button>
      <button id="annual-proof-trigger" aria-label={`Inspect proof for ${year} observed loss cells`} onClick={() => onProof("count")}>
        {plot.source_result?.yearly_loss_counts?.[String(year)] ?? "Unavailable"}
      </button>
    </section>
  );
}
