// STUB (owner: Map agent). Replace with the real map stage. See design/DESIGN.md §5.1 and §8.
import type { Cell, Plot } from "../types";
export type MapLayer = "loss" | "canopy" | "mask";
export type MapStageProps = {
  plots: Plot[];
  selectedPlotId: string | null;
  year: number;
  layer: MapLayer;
  onLayerChange: (l: MapLayer) => void;
  showJrc: boolean;
  onShowJrcChange: (v: boolean) => void;
  onSelectPlot: (id: string | null) => void;
  pinnedCell: Cell | null;
  onPinCell: (c: Cell | null) => void;
};
export default function MapStage({ plots, selectedPlotId, onSelectPlot }: MapStageProps) {
  return (
    <section aria-label="Map" style={{ padding: 16 }}>
      {plots.map((p) => (
        <button key={p.plot_id} aria-pressed={p.plot_id === selectedPlotId} onClick={() => onSelectPlot(p.plot_id)}>
          {p.plot_id}
        </button>
      ))}
    </section>
  );
}
