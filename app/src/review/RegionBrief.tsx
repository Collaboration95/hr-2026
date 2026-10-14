// STUB (owner: Inspector agent). See design/DESIGN.md §5.1 "Inspector, region brief".
import type { Demo } from "../types";
export type RegionBriefProps = { data: Demo; onSelectPlot: (id: string) => void };
export default function RegionBrief({ data, onSelectPlot }: RegionBriefProps) {
  return (
    <section aria-label="Region brief">
      <h2>{data.plots.length} supplier plots</h2>
      {data.plots.map((p) => <button key={p.plot_id} onClick={() => onSelectPlot(p.plot_id)}>{p.plot_id}</button>)}
    </section>
  );
}
