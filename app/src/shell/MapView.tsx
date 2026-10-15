import { useEffect, useRef, type ComponentProps } from "react";
import MapStage from "../map/MapStage";
import TimeScrubber from "../map/TimeScrubber";
import { useRegionRaster } from "../map/region-raster";
import { yearSeries } from "../review/plot-facts";
import PlotInspector from "../review/PlotInspector";
import RegionBrief from "../review/RegionBrief";
import type { Cell, Demo, Plot } from "../types";
import PlotRail, { type RailState } from "./PlotRail";
import type { DecisionState } from "./useDecisionSummary";
import type { JrcStatus } from "./useJrcCompanion";
import type { JrcArtifact } from "../jrc-data";

type StageProps = ComponentProps<typeof MapStage>;

/**
 * Map view: plot rail, map stage with time scrubber, and the inspector.
 * Desktop is three columns with internal scrolling; narrower screens restack (see shell.css).
 */
export default function MapView({
  data, plots, rail, plot, year,
  layer, onLayerChange, showJrc, onShowJrcChange, pinnedCell, onPinCell,
  jrc, decision, onSelectPlot, onYear, onProof, onReceipt,
}: {
  data: Demo;
  plots: Plot[];
  rail: RailState;
  plot: Plot | null;
  year: number;
  layer: StageProps["layer"];
  onLayerChange: StageProps["onLayerChange"];
  showJrc: boolean;
  onShowJrcChange: (value: boolean) => void;
  pinnedCell: Cell | null;
  onPinCell: (cell: Cell | null) => void;
  jrc: { jrc: JrcArtifact | null; status: JrcStatus; error?: string; load: () => void };
  decision?: DecisionState;
  onSelectPlot: (id: string | null) => void;
  onYear: (year: number) => void;
  onProof: (origin: "count" | "header") => void;
  onReceipt: () => void;
}) {
  const raster = useRegionRaster();
  const inspector = useRef<HTMLElement>(null);
  const plotId = plot?.plot_id ?? null;
  useEffect(() => {
    inspector.current?.scrollTo({ top: 0 });
  }, [plotId]);

  return (
    <div className="pl-mapview">
      <PlotRail plots={plots} rail={rail} selectedId={plotId} onSelect={onSelectPlot} />
      <div className="pl-mapview__stage">
        <div className="pl-mapview__map">
          <MapStage
            plots={plots}
            selectedPlotId={plotId}
            year={year}
            layer={layer}
            onLayerChange={onLayerChange}
            showJrc={showJrc}
            onShowJrcChange={onShowJrcChange}
            onSelectPlot={onSelectPlot}
            pinnedCell={pinnedCell}
            onPinCell={onPinCell}
          />
        </div>
        <div className="pl-mapview__scrub">
          {plot ? (
            <TimeScrubber
              mode="plot"
              year={year}
              onYear={onYear}
              counts={yearSeries(plot)}
              label={`${plot.plot_id} · observed loss cells · Hansen 2025 v1.13`}
              onProof={() => onProof("count")}
            />
          ) : (
            <TimeScrubber
              mode="region"
              year={year}
              onYear={onYear}
              counts={raster.yearlyLossPixels}
              label="Region · loss pixels (display raster)"
            />
          )}
        </div>
      </div>
      <aside className="pl-inspector" ref={inspector} aria-label="Inspector">
        {plot ? (
          <PlotInspector
            data={data}
            plot={plot}
            year={year}
            jrc={jrc.jrc}
            jrcStatus={jrc.status}
            jrcError={jrc.error}
            onLoadJrc={jrc.load}
            decision={decision}
            onProof={onProof}
            onReceipt={onReceipt}
            onPinCell={onPinCell}
          />
        ) : (
          <RegionBrief data={data} onSelectPlot={onSelectPlot} />
        )}
      </aside>
      <p className="pl-attribution">
        Hansen GFC 2025 v1.13 · CC BY 4.0 · JRC GFC2020 v4 · Reproducible evidence, no legal determination.
      </p>
    </div>
  );
}
