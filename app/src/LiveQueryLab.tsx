import { useEffect, useRef, useState } from "react";
import type { Demo, Geometry } from "./types";
import {
  getLiveHealth,
  LiveClientError,
  runLiveQuery,
  type LiveHealth,
  type LiveQueryResponse,
} from "./live-client";
import { Chip } from "./components/Primitives";
import { extent } from "./live/geometry";
import AnswerResult from "./live/AnswerResult";
import StatePanel, { phaseLabel, type Phase } from "./live/StatePanel";
import "./styles/live-query.css";

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

/** Presentation only: a transient end state that is not an answer. */
type Outcome = {
  kind: "cancelled" | "rejected" | "invalid";
  reason: string;
  notSent?: boolean;
} | null;
/** Presentation only: a sticky connection problem, cleared by a successful health check. */
type Outage = { kind: "unavailable" | "snapshot" | "invalid"; reason: string } | null;

const BOUND_LABELS = [
  "West longitude",
  "South latitude",
  "East longitude",
  "North latitude",
];
/** Visual compass order (north, west, east, south) as indexes into the [w, s, e, n] draft. */
const COMPASS = [3, 0, 2, 1];

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
    [checking, setChecking] = useState(true);
  const [result, setResult] = useState<LiveQueryResponse | null>(null),
    [busy, setBusy] = useState(false),
    [message, setMessage] = useState(
      "Connect to the optional local service to query a temporary region.",
    );
  const [outcome, setOutcome] = useState<Outcome>(null),
    [outage, setOutage] = useState<Outage>(null);
  const [year, setYear] = useState(2025);
  const sequence = useRef(0),
    request = useRef<AbortController | null>(null),
    healthRequest = useRef<AbortController | null>(null);
  const resultHeading = useRef<HTMLHeadingElement>(null);
  const plot = data.plots.find((p) => p.plot_id === plotId) || data.plots[0];
  function invalidate(
    note = "Draft changed. Run this region to compute a new answer.",
    next: Outcome = null,
  ) {
    sequence.current++;
    request.current?.abort();
    setBusy(false);
    setResult(null);
    setMessage(note);
    setOutcome(next);
  }
  async function connect() {
    invalidate("Checking the local service…");
    healthRequest.current?.abort();
    const control = new AbortController();
    healthRequest.current = control;
    setChecking(true);
    setHealth(null);
    setOutage(null);
    try {
      const h = await getLiveHealth(control.signal);
      if (!control.signal.aborted) {
        setHealth(h);
        setMessage(
          "Local snapshot ready. Choose a region and run it explicitly.",
        );
      }
    } catch (e) {
      if (!control.signal.aborted) {
        const reason =
          e instanceof Error ? e.message : "Local service unavailable.";
        setMessage(reason);
        setOutage({
          kind:
            e instanceof LiveClientError && e.kind === "invalid_response"
              ? "invalid"
              : "unavailable",
          reason,
        });
      }
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
      const reason =
        "Local service unavailable. Check the connection before running.";
      setMessage(reason);
      setOutage({ kind: "unavailable", reason });
      return;
    }
    let g: Geometry;
    try {
      g = geometry();
    } catch (e) {
      const reason = (e as Error).message;
      setMessage(reason);
      setOutcome({ kind: "rejected", reason, notSent: true });
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
        const reason =
          e instanceof Error
            ? e.message
            : "The query failed. No result is available.";
        if (
          e instanceof LiveClientError &&
          (e.kind === "unavailable" || e.code === "SNAPSHOT_MISMATCH")
        ) {
          setHealth(null);
          setOutage({
            kind: e.code === "SNAPSHOT_MISMATCH" ? "snapshot" : "unavailable",
            reason,
          });
        } else
          setOutcome({
            kind:
              e instanceof LiveClientError && e.kind === "invalid_response"
                ? "invalid"
                : "rejected",
            reason,
          });
        setMessage(reason);
      }
    } finally {
      if (version === sequence.current) setBusy(false);
    }
  }

  const phase: Phase | "completed" = result
    ? "completed"
    : busy
      ? "running"
      : checking
        ? "connecting"
        : outcome
          ? outcome.kind
          : health
            ? "idle"
            : (outage?.kind ?? "unavailable");
  const connection = checking
    ? { label: "Connecting", tone: "neutral" as const }
    : health
      ? { label: "Local snapshot ready", tone: "proof" as const }
      : outage?.kind === "snapshot"
        ? { label: "Snapshot changed", tone: "error" as const }
        : { label: "Service unavailable", tone: "unknown" as const };
  const reason =
    phase === "completed"
      ? ""
      : outcome && outcome.kind === phase
        ? outcome.reason
        : outage && outage.kind === phase
          ? outage.reason
          : "";

  return (
    <section className="live-lab" aria-labelledby="live-heading">
      <header className="live-heading">
        <div>
          <span className="pl-eyebrow">Live query · Hansen 2025 v1.13</span>
          <h2 id="live-heading" tabIndex={-1}>
            Ask the layers a new question
          </h2>
          <p>
            Runs a read-only query on an identified local snapshot. It never
            edits supplier records or the frozen 17-plot results.
          </p>
        </div>
        <span
          className={`live-connection pl-chip pl-chip--${connection.tone}${health ? " ready" : ""}`}
          data-state={checking ? "connecting" : health ? "ready" : (outage?.kind ?? "unavailable")}
        >
          <span className="live-dot" aria-hidden="true" />
          {connection.label}
        </span>
      </header>

      <div className="live-workbench">
        <form
          className="live-controls pl-card"
          aria-labelledby="live-define-heading"
          onSubmit={(e) => {
            e.preventDefault();
            void run();
          }}
        >
          <h3 id="live-define-heading" className="live-card-title">
            1 · Define a region
          </h3>
          <fieldset className="live-source">
            <legend className="pl-eyebrow">Geometry source</legend>
            <div className="live-choices">
              <label className="live-choice">
                <input
                  type="radio"
                  name="live-mode"
                  checked={mode === "plot"}
                  onChange={() => {
                    invalidate();
                    setMode("plot");
                  }}
                />
                <span>Exact supplied polygon</span>
              </label>
              <label className="live-choice">
                <input
                  type="radio"
                  name="live-mode"
                  checked={mode === "bounds"}
                  onChange={() => {
                    invalidate();
                    setMode("bounds");
                  }}
                />
                <span>Temporary rectangle</span>
              </label>
            </div>
          </fieldset>
          <label className="pl-field">
            Reference plot
            <select
              className="pl-select"
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
            <div className="live-rectangle">
              <button
                type="button"
                className="pl-btn pl-btn--sm"
                onClick={() => {
                  invalidate();
                  setBounds(extent(plot.geometry).map(String));
                }}
              >
                Use {plotId} bounds
              </button>
              <div className="live-bounds">
                {COMPASS.map((i) => (
                  <label
                    key={BOUND_LABELS[i]}
                    className={`pl-field live-bound live-bound--${"wsen"[i]}`}
                  >
                    {BOUND_LABELS[i]}
                    <input
                      className="pl-input pl-num"
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
              <p className="pl-fine">
                A rectangle can include cells outside the supplied polygon. It
                is not a revised farm boundary.
              </p>
            </div>
          )}
          <p className="pl-fine live-limits">
            Cell-center selection · at most 4,096 candidate cells. Larger
            regions are rejected, not clipped.
          </p>
          <div className="live-actions">
            <button
              className="pl-btn pl-btn--primary"
              disabled={!health || busy || checking}
              type="submit"
            >
              {busy ? "Computing…" : "Run region"}
            </button>
            {busy && (
              <button
                type="button"
                className="pl-btn"
                onClick={() =>
                  invalidate("Query cancelled. No result is displayed.", {
                    kind: "cancelled",
                    reason: "",
                  })
                }
              >
                Cancel query
              </button>
            )}
            <button
              type="button"
              className="pl-btn pl-btn--ghost"
              disabled={checking}
              onClick={() => void connect()}
            >
              Check connection
            </button>
          </div>
          <p
            className="live-status"
            role="status"
            aria-live="polite"
            data-phase={phase}
          >
            {message}
          </p>
        </form>

        <section className="live-answer pl-card" aria-labelledby="live-answer-heading">
          <div className="live-card-head">
            <h3 id="live-answer-heading" className="live-card-title">
              2 · Original ↔ compact answer
            </h3>
            <Chip
              tone={
                phase === "completed"
                  ? "proof"
                  : phase === "rejected"
                    ? "review"
                    : phase === "unavailable"
                      ? "unknown"
                      : phase === "snapshot" || phase === "invalid"
                        ? "error"
                        : "neutral"
              }
            >
              {phaseLabel[phase]}
            </Chip>
          </div>
          {phase === "completed" && result ? (
            <AnswerResult
              result={result}
              year={year}
              onYear={setYear}
              headingRef={resultHeading}
              onDownload={() =>
                save(
                  { snapshot: health, response: result },
                  `plotline-${result.request_id}.json`,
                )
              }
            />
          ) : (
            <StatePanel
              phase={phase as Phase}
              reason={reason}
              notSent={outcome?.notSent === true}
              onRetry={() => void connect()}
            />
          )}
        </section>
      </div>

      {health && (
        <details className="live-snapshot pl-disclosure">
          <summary>
            <span>Dataset snapshot · {health.snapshot.product}</span>
          </summary>
          <div className="pl-disclosure__body">
            <p className="pl-fine">
              Immutable loaded snapshot until service restart. A snapshot
              mismatch requires reconnecting.
            </p>
            <code>{health.snapshot_id}</code>
            <pre>{JSON.stringify(health.snapshot, null, 2)}</pre>
          </div>
        </details>
      )}
    </section>
  );
}
