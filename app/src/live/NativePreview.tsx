import type { Cell, Geometry } from "../types";
import type { LiveQueryResponse } from "../live-client";
import { isYearEvent } from "../cell-values";
import { extent } from "./geometry";

type Kind = "event" | "land" | "water" | "unknown";

/** Same classification as the table: unknown is never drawn as land, water or zero. */
function kindOf(cell: Cell, year: number): Kind {
  const p = cell.properties;
  if (
    !p.in_coverage ||
    p.band_validity.some((v) => !v) ||
    (p.datamask !== 1 && p.datamask !== 2)
  )
    return "unknown";
  if (isYearEvent(cell, year)) return "event";
  return p.datamask === 1 ? "land" : "water";
}

/**
 * Exact native footprints of the returned evidence. Display only: every count
 * comes from the validated response, never from this drawing.
 * Keep exactly one direct-child <path> per cell plus one boundary path.
 */
export default function NativePreview({
  result,
  year,
}: {
  result: LiveQueryResponse;
  year: number;
}) {
  const cells = result.evidence.cells.features;
  const allBounds = [
    extent(result.geometry),
    ...cells.map((cell) => extent(cell.geometry)),
  ];
  const [west, south, east, north] = [
    Math.min(...allBounds.map((b) => b[0])),
    Math.min(...allBounds.map((b) => b[1])),
    Math.max(...allBounds.map((b) => b[2])),
    Math.max(...allBounds.map((b) => b[3])),
  ];
  const c = Math.cos((((south + north) / 2) * Math.PI) / 180);
  const scale = Math.min(
    650 / ((east - west) * c || 1),
    310 / (north - south || 1),
  );
  const project = (p: number[]) => [
    360 + (p[0] - (west + east) / 2) * c * scale,
    175 - (p[1] - (south + north) / 2) * scale,
  ];
  const ring = (r: number[][]) =>
    r.map((p, i) => `${i ? "L" : "M"}${project(p).join(",")}`).join(" ") + "Z";
  const shape = (g: Geometry) =>
    g.type === "MultiPolygon"
      ? (g.coordinates as unknown as number[][][][])
          .flatMap((v) => v.map(ring))
          .join(" ")
      : g.coordinates.map(ring).join(" ");
  return (
    <figure className="live-native">
      <svg
        viewBox="0 0 720 350"
        role="img"
        aria-label={`Temporary region and all ${cells.length} selected native cell footprints; orange marks ${year} valid-land loss events`}
      >
        <defs>
          <pattern
            id="live-unknown"
            width="7"
            height="7"
            patternUnits="userSpaceOnUse"
          >
            <rect className="live-hatch-bg" width="7" height="7" />
            <path className="live-hatch-line" d="M0 7L7 0" />
          </pattern>
        </defs>
        {cells.map((cell: Cell) => {
          const kind = kindOf(cell, year);
          return (
            <path
              key={`${cell.properties.row}:${cell.properties.col}`}
              className={`live-cell live-cell--${kind}`}
              d={shape(cell.geometry)}
              fill={kind === "unknown" ? "url(#live-unknown)" : undefined}
              vectorEffect="non-scaling-stroke"
            />
          );
        })}
        <path
          className="live-region-line"
          d={shape(result.geometry)}
          fill="none"
          fillRule="evenodd"
          vectorEffect="non-scaling-stroke"
        />
      </svg>
      <figcaption>
        <ul className="live-legend" aria-label="Map legend">
          <li>
            <span className="live-swatch live-swatch--region" aria-hidden="true" />
            Submitted region
          </li>
          <li>
            <span className="live-swatch live-swatch--event" aria-hidden="true" />
            {year} mapped loss
          </li>
          <li>
            <span className="live-swatch live-swatch--land" aria-hidden="true" />
            Mapped land
          </li>
          <li>
            <span className="live-swatch live-swatch--water" aria-hidden="true" />
            Permanent water
          </li>
          <li>
            <span className="live-swatch live-swatch--unknown" aria-hidden="true" />
            No data, unavailable band or outside support
          </li>
        </ul>
        <p className="pl-fine">
          Exact native footprints, not imagery. Cell centers select cells, so a
          footprint can cross the outline.
        </p>
      </figcaption>
    </figure>
  );
}
