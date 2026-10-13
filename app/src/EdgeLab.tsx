import { useEffect, useState } from "react";
import { Pill, EmptyState } from "./components/Primitives";
import type { Geometry, Result } from "./types";
type FixtureCell = {
  geometry: Geometry;
  properties: {
    row: number;
    col: number;
    datamask: number | null;
    lossyear: number | null;
    valid_land: boolean;
    in_coverage: boolean;
    center: number[];
  };
};
type Case = {
  case_id: string;
  synthetic: true;
  geometry: Geometry;
  missing_bands: string[];
  result: Result;
  evidence: { features: FixtureCell[] };
};
type Lab = {
  schema_version: string;
  synthetic: true;
  cases: Case[];
  limitations: string[];
};
const copy: Record<string, [string, string]> = {
  tiny_no_centers: [
    "Smaller than the grid",
    "A polygon can contain no native-cell centers. No selected cells means insufficient support, not a clear plot.",
  ],
  partial_absence_unknown: [
    "Partial support, no event",
    "Observed land has no event in this period, but part of the query falls outside the available grid. Absence remains unknown.",
  ],
  partial_positive_known: [
    "Partial support, witnessed event",
    "A witnessed event is retained in its observation period, even with incomplete support. Other periods without a witnessed event remain unknown.",
  ],
  water_only: [
    "Water without valid land",
    "Known water coverage is not valid-land evidence. The analytical answer stays unknown rather than becoming a no-loss result.",
  ],
  nodata: [
    "A cell without data",
    "Known observations are retained, and unavailable selected cells stay explicit. A zero among available cells cannot prove absence everywhere.",
  ],
  missing_loss_band: [
    "Required band unavailable",
    "Disabling a required band makes the analytical answer unavailable. Stored fixture pixels are not evidence for a query that cannot use them.",
  ],
};
const geomPath = (g: Geometry) =>
  g.coordinates
    .map(
      (r) =>
        r
          .map(
            (p, i) =>
              `${i ? "L" : "M"}${45 + (p[0] + 1) * 45},${235 - p[1] * 45}`,
          )
          .join(" ") + "Z",
    )
    .join(" ");
export default function EdgeLab() {
  const [lab, setLab] = useState<Lab | null>(null),
    [error, setError] = useState(""),
    [id, setId] = useState("partial_absence_unknown"),
    [period, setPeriod] = useState("2021-2023");
  useEffect(() => {
    const controller = new AbortController();
    fetch("/data/synthetic-v1.json", { signal: controller.signal })
      .then((r) => {
        if (!r.ok)
          throw Error(
            "Synthetic test export is unavailable. Generate it with the engine, then sync app data.",
          );
        return r.json();
      })
      .then((x) => {
        if (
          x.schema_version !== "plotline.synthetic.v1" ||
          x.synthetic !== true ||
          !Array.isArray(x.cases) ||
          !x.cases.length
        )
          throw Error("Unsupported synthetic test export.");
        setLab(x);
      })
      .catch((e) => {
        if (e.name !== "AbortError") setError(e.message);
      });
    return () => controller.abort();
  }, []);
  if (error)
    return <EmptyState title="Support lab unavailable" detail={error} />;
  if (!lab) return <p role="status">Loading separate synthetic test cases…</p>;
  const c = lab.cases.find((v) => v.case_id === id) || lab.cases[0],
    r = c.result,
    p = r.periods[period],
    limits = period.split("-").map(Number),
    disabled = c.missing_bands.length > 0;
  return (
    <section className="edge-lab" aria-label="Synthetic query-support lab">
      <div className="section-title">
        <div>
          <span className="eyebrow">Separate synthetic test grid</span>
          <h3>When is zero still unknown?</h3>
        </div>
        <Pill tone="warning">Artificial fixtures</Pill>
      </div>
      <p className="lab-disclaimer">
        These six engine-generated cases use a fictitious 4 × 4 grid. They are
        not Hansen observations, supplier records, or part of the 17-plot
        evidence cohort.
      </p>
      <div className="lab-cases" aria-label="Synthetic test case">
        {lab.cases.map((v) => (
          <button
            key={v.case_id}
            aria-pressed={v.case_id === c.case_id}
            onClick={() => setId(v.case_id)}
          >
            {copy[v.case_id]?.[0] || v.case_id}
          </button>
        ))}
      </div>
      <div className="lab-layout">
        <div className="lab-geometry">
          <svg
            viewBox="0 0 300 280"
            role="img"
            aria-label={`${copy[c.case_id]?.[0] || c.case_id}; exact synthetic query boundary and native-cell support`}
          >
            <defs>
              <pattern
                id="unknown-hatch"
                width="6"
                height="6"
                patternUnits="userSpaceOnUse"
              >
                <path d="M0 6L6 0" stroke="#ac7852" strokeWidth="1" />
              </pattern>
            </defs>
            <text x="88" y="28" className="lab-svg-label">
              AVAILABLE 4 × 4 GRID
            </text>
            {Array.from({ length: 16 }, (_, i) => (
              <rect
                key={i}
                x={90 + (i % 4) * 45}
                y={55 + Math.floor(i / 4) * 45}
                width="45"
                height="45"
                fill="#e3e8dc"
                stroke="#c4d0b9"
              />
            ))}
            {c.evidence.features.map((cell, i) => {
              const v = cell.properties;
              const event =
                v.lossyear != null &&
                v.lossyear + 2000 >= limits[0] &&
                v.lossyear + 2000 <= limits[1];
              const unavailable =
                disabled || !v.in_coverage || v.datamask === 0;
              return (
                <g key={i}>
                  <path
                    d={geomPath(cell.geometry)}
                    fill={
                      unavailable
                        ? "url(#unknown-hatch)"
                        : v.datamask === 2
                          ? "#c5d6dc"
                          : event
                            ? "#db824c"
                            : "#aabd92"
                    }
                    stroke="#f5f7ef"
                  />
                  <circle
                    cx={45 + (v.center[0] + 1) * 45}
                    cy={235 - v.center[1] * 45}
                    r="2.5"
                    fill="#244531"
                  />
                </g>
              );
            })}
            <path
              d={geomPath(c.geometry)}
              fill="none"
              stroke="#213f31"
              strokeWidth="2.5"
            />
            <text x="45" y="262" className="lab-svg-label">
              Exact query boundary · native cell centers
            </text>
          </svg>
          <div className="lab-legend">
            <span>
              <i className="hatch" />
              Unknown / disabled
            </span>
            <span>
              <i className="event" />
              Observed event
            </span>
            <span>
              <i className="land" />
              Observed land
            </span>
          </div>
        </div>
        <div className="lab-result">
          <h4>{copy[c.case_id]?.[0] || c.case_id}</h4>
          <p>{copy[c.case_id]?.[1]}</p>
          <div className="segmented lab-period">
            {Object.keys(r.periods).map((k) => (
              <button
                key={k}
                aria-pressed={period === k}
                onClick={() => setPeriod(k)}
              >
                {k.replace("-", "–")}
              </button>
            ))}
          </div>
          <div
            className={`lab-signal ${p?.mapped_loss_present == null ? "unknown" : ""}`}
          >
            <span>{period.replace("-", "–")} mapped-loss signal</span>
            <strong>
              {p?.mapped_loss_present === true
                ? "Observed"
                : p?.mapped_loss_present === false
                  ? "Not observed under this query"
                  : "Unknown"}
            </strong>
            <small>
              {p?.observed_loss_cell_count == null
                ? "Analytical count unavailable"
                : `${p.observed_loss_cell_count} observed loss cells`}{" "}
              · support: {r.support}
            </small>
          </div>
          <dl>
            <div>
              <dt>Selected / valid-land cells</dt>
              <dd>
                {r.selected_cell_count} / {r.valid_land_cell_count}
              </dd>
            </div>
            <div>
              <dt>Unknown / outside coverage</dt>
              <dd>
                {r.unknown_cell_count} / {r.out_of_coverage_cell_count}
              </dd>
            </div>
            <div>
              <dt>Required bands disabled</dt>
              <dd>{c.missing_bands.join(", ") || "None"}</dd>
            </div>
            <div>
              <dt>Unknown reasons</dt>
              <dd>{r.unknown_reasons.join(", ") || "None"}</dd>
            </div>
          </dl>
        </div>
      </div>
      <details className="json-details">
        <summary>Inspect this synthetic query result</summary>
        <pre>
          {JSON.stringify(
            {
              case_id: c.case_id,
              synthetic: true,
              missing_bands: c.missing_bands,
              result: c.result,
            },
            null,
            2,
          )}
        </pre>
      </details>
    </section>
  );
}
