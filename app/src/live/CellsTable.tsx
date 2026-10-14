import { useId, useState } from "react";
import type { Cell } from "../types";
import { canopyLabel, lossLabel, maskLabel } from "../cell-values";

/** Unavailable is hatched, never a plain empty or zero cell. */
const mark = (label: string) =>
  label.startsWith("Unavailable") ? "live-unavailable" : undefined;

function centerLabel(cell: Cell): string {
  const c = cell.properties.center;
  return Array.isArray(c) &&
    c.length >= 2 &&
    Number.isFinite(c[0]) &&
    Number.isFinite(c[1])
    ? `${c[0].toFixed(6)}, ${c[1].toFixed(6)}`
    : "Unavailable";
}

/**
 * Every selected native cell, no truncation. Row:column, loss event and mask are
 * the priority columns; canopy and the center coordinate sit behind
 * "More columns" when the container is narrow.
 */
export default function CellsTable({ cells }: { cells: Cell[] }) {
  const [more, setMore] = useState(false);
  const region = useId();
  return (
    <div className="live-cells" data-more={more}>
      <div className="live-cells__bar">
        <p className="pl-fine">
          Raw invalid values are labelled and excluded from counts. Scroll the
          table or focus it and use the arrow keys.
        </p>
        <button
          type="button"
          className="pl-btn pl-btn--sm live-more-toggle"
          aria-pressed={more}
          aria-controls={region}
          onClick={() => setMore(!more)}
        >
          More columns
        </button>
      </div>
      <div
        id={region}
        className="pl-table-wrap live-table-scroll"
        role="region"
        aria-label="Selected native cells, scrollable"
        tabIndex={0}
      >
        <table className="pl-table">
          <thead>
            <tr>
              <th scope="col">Row : column</th>
              <th scope="col">Loss event</th>
              <th scope="col">Mask</th>
              <th scope="col" className="live-col-more">
                Canopy 2000
              </th>
              <th scope="col" className="live-col-more">
                Center (°E, °N)
              </th>
            </tr>
          </thead>
          <tbody>
            {cells.map((cell) => {
              const loss = lossLabel(cell),
                mask = maskLabel(cell),
                canopy = canopyLabel(cell),
                center = centerLabel(cell);
              return (
                <tr key={`${cell.properties.row}:${cell.properties.col}`}>
                  <th scope="row">
                    {cell.properties.row} : {cell.properties.col}
                  </th>
                  <td className={mark(loss)}>{loss}</td>
                  <td className={mark(mask)}>{mask}</td>
                  <td className={`live-col-more ${mark(canopy) ?? ""}`}>
                    {canopy}
                  </td>
                  <td className={`live-col-more ${mark(center) ?? ""}`}>
                    {center}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </div>
  );
}
