import { useEffect, useState } from "react";
import { canopyLabel, lossLabel, maskLabel, isYearEvent } from "./cell-values";
import type { Cell } from "./types";
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
  useEffect(() => setOnlyEvents(false), [cells]);
  const events = cells.filter((c) => isYearEvent(c, year));
  const rows = onlyEvents ? events : cells;
  return (
    <details className="cell-table">
      <summary>
        Inspect native cells as a table{" "}
        <span>
          {available ? `${plotId} · ${cells.length} selected` : "Unavailable"}
        </span>
      </summary>
      <div className="cell-table-body">
        <p>
          Exact values from selected source cells. Selection uses each cell’s
          center; the footprint may extend beyond the plot boundary.
        </p>
        <label className="cell-filter">
          <input
            type="checkbox"
            disabled={!available}
            checked={onlyEvents}
            onChange={(e) => setOnlyEvents(e.target.checked)}
          />
          Only {year} valid-land loss events ({events.length})
        </label>
        {rows.length ? (
          <div
            className="cell-table-scroll"
            tabIndex={0}
            aria-label="Scrollable native cell values"
          >
            <table>
              <thead>
                <tr>
                  <th>Native row : column</th>
                  <th>Canopy 2000</th>
                  <th>Loss event</th>
                  <th>Land mask</th>
                  <th>Inspect</th>
                </tr>
              </thead>
              <tbody>
                {rows.map((c) => (
                  <tr key={`${c.properties.row}:${c.properties.col}`}>
                    <th>
                      {c.properties.row} : {c.properties.col}
                    </th>
                    <td>{canopyLabel(c)}</td>
                    <td>{lossLabel(c)}</td>
                    <td>{maskLabel(c)}</td>
                    <td>
                      <button
                        aria-label={`Inspect cell ${c.properties.row}:${c.properties.col}`}
                        onClick={() => onInspect(c)}
                      >
                        Show on map
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <p className="cell-table-empty">
            {onlyEvents
              ? `No observed event cells are available for ${year}. Support may be incomplete; inspect the query’s unknown reasons. This is not a legal conclusion.`
              : "No cell footprints available. Inspect the query support and unknown reasons."}
          </p>
        )}
      </div>
    </details>
  );
}
