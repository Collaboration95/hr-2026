import { Glyph, Icon, Stat } from "../components/Primitives";
import { comparisonState } from "../comparison-state";
import type { Demo, Plot } from "../types";
import DeclaredMappedMatrix from "./DeclaredMappedMatrix";
import { RECENT_PERIOD, YEARS, declaredIndication, mappedLoss, periodCount } from "./plot-facts";
import "../styles/review.css";

export type RegionBriefProps = { data: Demo; onSelectPlot: (id: string) => void };

type Start = { id: string; reason: string };

/** Up to three entry points chosen from the data, never hard-coded. */
function startingPlots(plots: Plot[]): Start[] {
  const picks: Start[] = [];
  const taken = new Set<string>();
  const add = (plot: Plot | undefined, reason: string) => {
    if (plot && !taken.has(plot.plot_id)) { taken.add(plot.plot_id); picks.push({ id: plot.plot_id, reason }); }
  };
  add(plots.find((p) => declaredIndication(p) === true && mappedLoss(p) === false), "Declared indication, no mapped loss");
  add(plots.find((p) => declaredIndication(p) === false && mappedLoss(p) === true), "Mapped loss the declaration doesn't mention");
  const recent = plots
    .map((p) => ({ p, n: periodCount(p, RECENT_PERIOD) }))
    .filter((x): x is { p: Plot; n: number } => x.n !== null && x.n > 0 && !taken.has(x.p.plot_id))
    .reduce<{ p: Plot; n: number } | null>((best, x) => (best === null || x.n > best.n ? x : best), null);
  if (recent) add(recent.p, `Most recent loss: ${recent.n.toLocaleString("en-US")} cells in 2024–25`);
  return picks;
}

/** Inspector content when no plot is selected: the region at a glance. */
export default function RegionBrief({ data, onSelectPlot }: RegionBriefProps) {
  const plots = data.plots;
  const n = plots.length;
  const states = plots.map(comparisonState);
  // The cohort is only "n/n" when every plot has been compared; otherwise the answer is not computed.
  const matches = n > 0 && states.every((s) => s !== "unavailable") ? states.filter((s) => s === "match").length : null;
  const mismatches = states.filter((s) => s === "mismatch").length;
  const declared = plots.filter((p) => declaredIndication(p) === true).length;
  const declaredUnknown = plots.filter((p) => declaredIndication(p) === null).length;
  const mapped = plots.filter((p) => mappedLoss(p) === true).length;
  const mappedUnknown = plots.filter((p) => mappedLoss(p) === null).length;
  const starts = startingPlots(plots);
  return (
    <section className="pl-brief" aria-label="Region brief">
      <header className="pl-brief__head">
        <span className="pl-eyebrow">Region</span>
        <h2>{n} supplier plots, three layers, {YEARS.length} years</h2>
        <p className="pl-brief__lede">The map is the Hansen 2025 v1.13 raster itself. Pick a plot to see what the layers say and what the supplier declared.</p>
      </header>

      <div className="pl-brief__stats">
        <div className="pl-brief__stat pl-brief__stat--wide">
          {matches === null
            ? <Stat value={<span className="pl-unknown__tag pl-hatch pl-brief__notcomputed">Not computed</span>} label="Compact-store comparison has not been run for every plot" />
            : <Stat size="lg" tone={matches === n ? "proof" : undefined} value={`${matches}/${n}`}
                label={<>plots give identical answers from the compact store{mismatches > 0 && <span className="pl-brief__flag"> · {mismatches} encoding mismatch{mismatches > 1 ? "es" : ""}</span>}</>} />}
        </div>
        <div className="pl-brief__stat">
          <Stat tone="declared" value={declared}
            label={<><Glyph kind="declared" /> declared indications{declaredUnknown > 0 && <span className="pl-fine"> · {declaredUnknown} unrecognised</span>}</>} />
        </div>
        <div className="pl-brief__stat">
          <Stat tone="loss" value={mapped}
            label={<><Glyph kind="loss" /> plots with mapped loss in 2021–23{mappedUnknown > 0 && <span className="pl-fine"> · {mappedUnknown} unknown</span>}</>} />
        </div>
      </div>

      <section className="pl-brief__block" aria-labelledby="pl-brief-matrix">
        <h3 id="pl-brief-matrix" className="pl-eyebrow">Declared vs mapped</h3>
        <DeclaredMappedMatrix plots={plots} onSelectPlot={onSelectPlot} />
        <p className="pl-fine">Amber cells: the two accounts differ. That is a question for review, not a finding.</p>
      </section>

      {starts.length > 0 && (
        <section className="pl-brief__block" aria-labelledby="pl-brief-start">
          <h3 id="pl-brief-start" className="pl-eyebrow">Good places to start</h3>
          <ul className="pl-start-list">
            {starts.map((s) => (
              <li key={s.id}>
                <button type="button" className="pl-start" onClick={() => onSelectPlot(s.id)}>
                  <span className="pl-start__id">{s.id}</span>
                  <span className="pl-start__why">{s.reason}</span>
                  <Icon name="arrow" size={14} />
                </button>
              </li>
            ))}
          </ul>
        </section>
      )}

      <p className="pl-brief__keys pl-fine">
        <kbd>J</kbd> <kbd>K</kbd> step through plots · <kbd>/</kbd> search · <kbd>←</kbd> <kbd>→</kbd> change year
      </p>
    </section>
  );
}
