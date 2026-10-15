import { useEffect, useState } from "react";
import { Glyph, Icon } from "./components/Primitives";
import { canopyLabel, lossLabel, maskLabel, isYearEvent } from "./cell-values";
import type { Cell } from "./types";
import "./styles/review.css";

/**
 * Native cells behind the counts, as an accessible table. Selection uses each cell's centre;
 * the footprint may extend beyond the boundary. Canopy and land mask are secondary columns:
 * in a narrow panel they sit behind a "More columns" toggle instead of forcing a sideways scroll.
 */
export default function CellTable({
  plotId,
  available,
  cells,
  year,
  onInspect,
}: {
  plotId: string;
  available: boolean;
  cells: Cell[];
  year: number;
  onInspect: (cell: Cell) => void;
}) {
  const [onlyEvents, setOnlyEvents] = useState(false);
  const [more, setMore] = useState(false);
  useEffect(() => setOnlyEvents(false), [cells]);
  const events = cells.filter((c) => isYearEvent(c, year));
  const rows = onlyEvents ? events : cells;
  return (
    <details className="pl-disclosure cell-table">
      <summary>
        Native cells
        <span className="pl-disclosure__meta">{available ? `${plotId} · ${cells.length} selected` : "Unavailable"}</span>
      </summary>
      <div className="pl-disclosure__body">
        <p className="pl-fine">Exact values from the selected cells. A cell is selected when its centre is inside the plot; its footprint may extend beyond the boundary.</p>
        <label className="pl-check">
          <input type="checkbox" disabled={!available} checked={onlyEvents} onChange={(e) => setOnlyEvents(e.target.checked)} />
          <span>Only {year} valid-land loss events ({events.length})</span>
        </label>
        {rows.length ? (
          <div className="pl-cells" data-more={more}>
            <div className="pl-cells__tools">
              <button type="button" className="pl-btn pl-btn--sm" aria-pressed={more} onClick={() => setMore(!more)}>
                {more ? "Fewer columns" : "More columns"}
              </button>
            </div>
            <div className="pl-table-wrap pl-cells__scroll" tabIndex={0} role="region" aria-label="Scrollable native cell values">
              <table className="pl-table">
                <caption className="pl-sr-only">{`${rows.length} native cells for ${plotId}`}</caption>
                <thead>
                  <tr>
                    <th scope="col">Row : col</th>
                    <th scope="col" className="pl-cells__extra">Canopy 2000</th>
                    <th scope="col">Loss event</th>
                    <th scope="col" className="pl-cells__extra">Land mask</th>
                    <th scope="col"><span className="pl-sr-only">Inspect</span></th>
                  </tr>
                </thead>
                <tbody>
                  {rows.map((c) => {
                    const event = isYearEvent(c, year);
                    return (
                      <tr key={`${c.properties.row}:${c.properties.col}`} className={event ? "is-event" : undefined}>
                        <th scope="row">{c.properties.row} : {c.properties.col}</th>
                        <td className="pl-cells__extra">{canopyLabel(c)}</td>
                        <td className="pl-cells__loss">{event && <><Glyph kind="loss" />{" "}</>}{lossLabel(c)}</td>
                        <td className="pl-cells__extra">{maskLabel(c)}</td>
                        <td>
                          <button type="button" className="pl-btn pl-btn--sm" aria-label={`Inspect cell ${c.properties.row}:${c.properties.col}`} onClick={() => onInspect(c)}>
                            <Icon name="target" size={14} />Show on map
                          </button>
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          </div>
        ) : (
          <p className="pl-fine cell-table-empty">
            {onlyEvents
              ? `No observed event cells are available for ${year}. Support may be incomplete; check the unknown reasons. This is not a legal conclusion.`
              : "No cell footprints available. Check the query support and unknown reasons."}
          </p>
        )}
      </div>
    </details>
  );
}
