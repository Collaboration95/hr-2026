import { Icon } from "../components/Primitives";
import ProofView from "../proof/ProofView";
import type { Demo, Plot } from "../types";
import { DEFAULT_YEAR, FIRST_YEAR } from "./route";

const YEAR_OPTIONS = Array.from({ length: DEFAULT_YEAR - FIRST_YEAR + 1 }, (_, i) => DEFAULT_YEAR - i);

/** Proof route: a slim context bar (back, plot, year) above the proof view. */
export default function ProofRoute({ data, plots, plot, year, onBack, onOpen, onYear, onReceipt }: {
  data: Demo;
  plots: Plot[];
  plot: Plot;
  year: number;
  onBack: () => void;
  /** Switch the proof to another plot (a new history entry). */
  onOpen: (id: string, year: number) => void;
  /** Change only the year (replaces the history entry). */
  onYear: (year: number) => void;
  onReceipt: () => void;
}) {
  return (
    <div className="pl-view pl-view--proof">
      <div className="pl-ctxbar">
        <button type="button" className="pl-btn pl-btn--sm pl-btn--ghost" onClick={onBack}>
          <Icon name="arrow-left" size={15} />
          Back to map
        </button>
        <label className="pl-ctxbar__field">
          <span className="pl-eyebrow">Plot</span>
          <select className="pl-select" aria-label="Proof plot" value={plot.plot_id} onChange={(e) => onOpen(e.target.value, year)}>
            {plots.map((p) => (
              <option key={p.plot_id} value={p.plot_id}>
                {p.plot_id}
                {p.supplier?.a7_size_of_plot_ha ? ` · ${p.supplier.a7_size_of_plot_ha} ha` : ""}
              </option>
            ))}
          </select>
        </label>
        <label className="pl-ctxbar__field">
          <span className="pl-eyebrow">Year</span>
          <select className="pl-select" aria-label="Proof year" value={year} onChange={(e) => onYear(Number.parseInt(e.target.value, 10))}>
            {YEAR_OPTIONS.map((y) => (
              <option key={y} value={y}>{y}</option>
            ))}
          </select>
        </label>
      </div>
      <div className="pl-page">
        <ProofView plot={plot} data={data} year={year} onReceipt={onReceipt} onOpenPlot={onOpen} />
      </div>
    </div>
  );
}
