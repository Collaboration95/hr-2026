import { useEffect, useRef, useState } from "react";
import type { Demo, Geometry, Cell } from "./types";
import {
  getLiveHealth,
  LiveClientError,
  runLiveQuery,
  type LiveHealth,
  type LiveQueryResponse,
} from "./live-client";
import { canopyLabel, lossLabel, maskLabel, isYearEvent } from "./cell-values";
import "./styles/live-query.css";

function positions(value: unknown): number[][] {
  if (!Array.isArray(value)) return [];
  if (typeof value[0] === "number") return [value as number[]];
  return value.flatMap(positions);
}
function extent(g: Geometry) {
  const p = positions(g.coordinates);
  return [
    Math.min(...p.map((v) => v[0])),
    Math.min(...p.map((v) => v[1])),
    Math.max(...p.map((v) => v[0])),
    Math.max(...p.map((v) => v[1])),
  ];
}
function save(value: unknown, name: string) {
  const url = URL.createObjectURL(
    new Blob([JSON.stringify(value, null, 2)], { type: "application/json" }),
  );
  const a = document.createElement("a");
  a.href = url;
  a.download = name;
  a.click();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}
function NativePreview({
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
    <div className="live-native">
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
            <path d="M0 7L7 0" stroke="#677469" strokeWidth="2" />
          </pattern>
        </defs>
        {cells.map((cell: Cell) => (
          <path
            key={`${cell.properties.row}:${cell.properties.col}`}
            d={shape(cell.geometry)}
            fill={
              !cell.properties.in_coverage ||
              cell.properties.band_validity.some((v) => !v) ||
              (cell.properties.datamask !== 1 && cell.properties.datamask !== 2)
                ? "url(#live-unknown)"
                : isYearEvent(cell, year)
                  ? "#bd4a25"
                  : cell.properties.datamask === 1
                    ? "#adc8a2"
                    : "#a5cad4"
            }
            stroke="#edf2e8"
            strokeWidth=".5"
          />
        ))}
        <path
          d={shape(result.geometry)}
          fill="none"
          stroke="#193f30"
          strokeWidth="2"
          fillRule="evenodd"
        />
      </svg>
      <p>
        Exact native footprints · dark outline: submitted region · orange:{" "}
        {year} mapped loss · green: mapped land · blue: permanent water · hatch:
        no data, unavailable band or outside support. Centers select cells;
        footprints may cross the outline. No satellite imagery.
      </p>
    </div>
  );
}
export default function LiveQueryLab({
  data,
  selectedPlotId,
}: {
  data: Demo;
  selectedPlotId: string;
}) {
  const [plotId, setPlotId] = useState(selectedPlotId),
    [mode, setMode] = useState<"plot" | "bounds">("plot");
  const [bounds, setBounds] = useState(["", "", "", ""]);
  const [health, setHealth] = useState<LiveHealth | null>(null),
    [checking, setChecking] = useState(false);
  const [result, setResult] = useState<LiveQueryResponse | null>(null),
    [busy, setBusy] = useState(false),
    [message, setMessage] = useState(
      "Connect to the optional local service to query a temporary region.",
    );
  const [year, setYear] = useState(2025);
  const sequence = useRef(0),
    request = useRef<AbortController | null>(null),
    healthRequest = useRef<AbortController | null>(null);
  const resultHeading = useRef<HTMLHeadingElement>(null);
  const plot = data.plots.find((p) => p.plot_id === plotId) || data.plots[0];
  function invalidate(
    note = "Draft changed. Run this region to compute a new answer.",
  ) {
    sequence.current++;
    request.current?.abort();
    setBusy(false);
    setResult(null);
    setMessage(note);
  }
  async function connect() {
    invalidate("Checking the local service…");
    healthRequest.current?.abort();
    const control = new AbortController();
    healthRequest.current = control;
    setChecking(true);
    setHealth(null);
    try {
      const h = await getLiveHealth(control.signal);
      if (!control.signal.aborted) {
        setHealth(h);
        setMessage(
          "Local snapshot ready. Choose a region and run it explicitly.",
        );
      }
    } catch (e) {
      if (!control.signal.aborted)
        setMessage(
          e instanceof Error ? e.message : "Local service unavailable.",
        );
    } finally {
      if (!control.signal.aborted) setChecking(false);
    }
  }
  useEffect(() => {
    void connect();
    return () => {
      sequence.current++;
      request.current?.abort();
      healthRequest.current?.abort();
    };
  }, []);
  useEffect(() => {
    if (result) resultHeading.current?.focus();
  }, [result]);
  function geometry(): Geometry {
    if (mode === "plot") return plot.geometry;
    if (bounds.some((v) => !v.trim()))
      throw new Error("Enter all four bounds. Empty fields are not zero.");
    const [w, s, e, n] = bounds.map(Number);
    if (![w, s, e, n].every(Number.isFinite))
      throw new Error("Bounds must be finite decimal degrees.");
    if (w < -180 || e > 180 || s < -90 || n > 90 || w >= e || s >= n)
      throw new Error(
        "Use west < east and south < north, within longitude ±180 and latitude ±90.",
      );
    return {
      type: "Polygon",
      coordinates: [
        [
          [w, s],
          [e, s],
          [e, n],
          [w, n],
          [w, s],
        ],
      ],
    };
  }
  async function run() {
    invalidate("Computing original and compact answers…");
    if (!health) {
      setMessage(
        "Local service unavailable. Check the connection before running.",
      );
      return;
    }
    let g: Geometry;
    try {
      g = geometry();
    } catch (e) {
      setMessage((e as Error).message);
      return;
    }
    const version = sequence.current,
      control = new AbortController();
    request.current = control;
    setBusy(true);
    try {
      const answer = await runLiveQuery(
        g,
        `local_${crypto.randomUUID().replaceAll("-", "")}`,
        health,
        control.signal,
      );
      if (version === sequence.current && !control.signal.aborted) {
        setResult(answer);
        setMessage(
          "Original and compact answers match. Complete selected-cell evidence received.",
        );
      }
    } catch (e) {
      if (version === sequence.current && !control.signal.aborted) {
        if (
          e instanceof LiveClientError &&
          (e.kind === "unavailable" || e.code === "SNAPSHOT_MISMATCH")
        )
          setHealth(null);
        setMessage(
          e instanceof Error
            ? e.message
            : "The query failed. No result is available.",
        );
      }
    } finally {
      if (version === sequence.current) setBusy(false);
    }
  }
  return (
    <section className="live-lab" aria-labelledby="live-heading">
      <header className="live-heading">
        <div>
          <span className="eyebrow">Local experiment · Hansen</span>
          <h2 id="live-heading" tabIndex={-1}>
            Ask a spatial question.
          </h2>
          <p>
            Try an exact supplied polygon or a temporary rectangle. This does
            not edit supplier records or the frozen 17-plot results.
          </p>
        </div>
        <span className={`live-connection ${health ? "ready" : ""}`}>
          {checking
            ? "Connecting"
            : health
              ? "Local snapshot ready"
              : "Service unavailable"}
        </span>
      </header>
      <div className="live-workbench">
        <form
          className="live-controls"
          onSubmit={(e) => {
            e.preventDefault();
            void run();
          }}
        >
          <h3>1. Define the region</h3>
          <fieldset>
            <legend>Geometry source</legend>
            <label>
              <input
                type="radio"
                name="live-mode"
                checked={mode === "plot"}
                onChange={() => {
                  invalidate();
                  setMode("plot");
                }}
              />{" "}
              Exact supplied polygon
            </label>
            <label>
              <input
                type="radio"
                name="live-mode"
                checked={mode === "bounds"}
                onChange={() => {
                  invalidate();
                  setMode("bounds");
                }}
              />{" "}
              Temporary rectangle
            </label>
          </fieldset>
          <label>
            Reference plot
            <select
              value={plotId}
              onChange={(e) => {
                invalidate();
                setPlotId(e.target.value);
              }}
            >
              {data.plots.map((p) => (
                <option key={p.plot_id}>{p.plot_id}</option>
              ))}
            </select>
          </label>
          {mode === "bounds" && (
            <>
              <button
                type="button"
                onClick={() => {
                  invalidate();
                  setBounds(extent(plot.geometry).map(String));
                }}
              >
                Use {plotId} bounds
              </button>
              <div className="live-bounds">
                {[
                  "West longitude",
                  "South latitude",
                  "East longitude",
                  "North latitude",
                ].map((name, i) => (
                  <label key={name}>
                    {name}
                    <input
                      type="number"
                      step="any"
                      value={bounds[i]}
                      onChange={(e) => {
                        invalidate();
                        setBounds((old) =>
                          old.map((v, j) => (j === i ? e.target.value : v)),
                        );
                      }}
                    />
                  </label>
                ))}
              </div>
              <p>
                A bounding rectangle can include cells outside the supplied
                polygon. It is not a revised farm boundary.
              </p>
            </>
          )}
          <p>
            Cell-center selection · at most 4,096 candidate cells. Larger
            regions are rejected, not clipped.
          </p>
          <div className="live-actions">
            <button
              className="pl-button--accent"
              disabled={!health || busy || checking}
              type="submit"
            >
              {busy ? "Computing…" : "Run region"}
            </button>
            {busy && (
              <button
                type="button"
                onClick={() =>
                  invalidate("Query cancelled. No result is displayed.")
                }
              >
                Cancel query
              </button>
            )}
            <button
              type="button"
              disabled={checking}
              onClick={() => void connect()}
            >
              Check connection
            </button>
          </div>
          <p className="live-status" role="status" aria-live="polite">
            {message}
          </p>
          {!health && (
            <p>
              Run the local API on port 8765, then check the connection. The
              Review desk and Evidence index remain available.
            </p>
          )}
        </form>
        <div className="live-answer">
          {!result ? (
            <div className="live-await">
              <span className="eyebrow">2. Compare the answer</span>
              <h3>
                {busy
                  ? "Reading the same region twice…"
                  : "Your next question stays separate."}
              </h3>
              <p>
                Original source and retained compact storage will answer the
                same submitted geometry on one identified local snapshot. No
                answer is shown until validation succeeds.
              </p>
              <div className="live-diagram" aria-hidden="true">
                <span>Region</span>
                <span>Original ↔ Compact</span>
                <span>Bound receipt</span>
              </div>
            </div>
          ) : (
            <>
              <div className="live-result-heading">
                <div>
                  <span className="eyebrow">
                    Validated response · temporary geometry
                  </span>
                  <h3 ref={resultHeading} tabIndex={-1}>
                    Same answer. Inspect the evidence.
                  </h3>
                </div>
                <button
                  onClick={() =>
                    save(
                      { snapshot: health, response: result },
                      `plotline-${result.request_id}.json`,
                    )
                  }
                >
                  Download live receipt
                </button>
              </div>
              <p>{result.interpretation}</p>
              <div className="live-table-scroll">
                <table>
                  <caption>
                    Original and compact · actual returned counts
                  </caption>
                  <thead>
                    <tr>
                      <th>Measure</th>
                      <th>Original</th>
                      <th>Compact</th>
                    </tr>
                  </thead>
                  <tbody>
                    {(
                      [
                        "selected_cell_count",
                        "valid_land_cell_count",
                        "unknown_cell_count",
                        "out_of_coverage_cell_count",
                      ] as const
                    ).map((key) => (
                      <tr key={key}>
                        <th>{key.replaceAll("_", " ")}</th>
                        <td>{result.source_result[key]}</td>
                        <td>{result.compact_result[key]}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
              <p>
                <b>Support: {result.source_result.support}.</b>{" "}
                {result.source_result.unknown_reasons.join(" · ")}
              </p>
              <div className="live-periods">
                {Object.entries(result.source_result.periods).map(
                  ([period, value]) => (
                    <div key={period}>
                      <b>{period}</b>
                      <strong>
                        {value.observed_loss_cell_count === null
                          ? "Unavailable"
                          : `${value.observed_loss_cell_count} mapped loss cells`}
                      </strong>
                      <span>
                        {value.mapped_loss_present === null
                          ? "Mapped result unknown"
                          : value.mapped_loss_present
                            ? "Mapped loss observed"
                            : "No mapped loss under this query"}
                      </span>
                    </div>
                  ),
                )}
              </div>
              <label className="live-year">
                Native evidence year
                <select
                  value={year}
                  onChange={(e) => setYear(Number(e.target.value))}
                >
                  {Array.from({ length: 25 }, (_, i) => 2001 + i).map((y) => (
                    <option key={y}>{y}</option>
                  ))}
                </select>
                <span>
                  {result.source_result.yearly_loss_counts?.[String(year)] ??
                    "Unavailable"}{" "}
                  mapped loss cells
                </span>
              </label>
              <NativePreview result={result} year={year} />
              <details>
                <summary>
                  All {result.evidence.returned_cell_count} selected native
                  cells
                </summary>
                <div className="live-table-scroll" tabIndex={0}>
                  <table>
                    <thead>
                      <tr>
                        <th>Row : column</th>
                        <th>Canopy 2000</th>
                        <th>Loss event</th>
                        <th>Mask</th>
                      </tr>
                    </thead>
                    <tbody>
                      {result.evidence.cells.features.map((cell) => (
                        <tr
                          key={`${cell.properties.row}:${cell.properties.col}`}
                        >
                          <th>
                            {cell.properties.row} : {cell.properties.col}
                          </th>
                          <td>{canopyLabel(cell)}</td>
                          <td>{lossLabel(cell)}</td>
                          <td>{maskLabel(cell)}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </details>
              <details>
                <summary>Request, snapshot and receipt identity</summary>
                <dl>
                  <dt>Request</dt>
                  <dd>{result.request_id}</dd>
                  <dt>Snapshot SHA-256</dt>
                  <dd>{result.snapshot_id}</dd>
                  <dt>Receipt SHA-256</dt>
                  <dd>{result.receipt.sha256}</dd>
                  <dt>Query</dt>
                  <dd>{result.query_version}</dd>
                </dl>
                <p>
                  Hashes bind this local response; they are not signatures or
                  legal verification.
                </p>
                <pre>{JSON.stringify(result.receipt.payload, null, 2)}</pre>
              </details>
              <p className="live-timing">
                This request: original{" "}
                {result.runtime.source_query_ms.toFixed(2)} ms · compact{" "}
                {result.runtime.compact_query_ms.toFixed(2)} ms. Preloaded
                arrays; network and UI excluded. These are single-request
                timings, not the retained benchmark.
              </p>
            </>
          )}
        </div>
      </div>
      {health && (
        <details className="live-snapshot">
          <summary>Dataset snapshot · {health.snapshot.product}</summary>
          <p>
            Immutable loaded snapshot until service restart. A snapshot mismatch
            requires reconnecting.
          </p>
          <code>{health.snapshot_id}</code>
          <pre>{JSON.stringify(health.snapshot, null, 2)}</pre>
        </details>
      )}
    </section>
  );
}
