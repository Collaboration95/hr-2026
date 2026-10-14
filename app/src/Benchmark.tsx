import { useMemo, useState } from "react";
import type * as React from "react";
import { Chip, EmptyState, Icon, Info } from "./components/Primitives";
import {
  fmtBytes,
  fmtFixed,
  fmtInt,
  fmtKiB,
  fmtPct,
  pctChange,
  readBenchmark,
  rowLabel,
  type BenchRow,
  type BenchView,
  type TimingStats,
} from "./proof/bench-data";
import "./styles/proof.css";

/**
 * Reviewed constants from the SEPARATE strong-baseline study (own fingerprints,
 * own timings; see docs/lab/engine-strong-baseline-report.md). They are not part
 * of the frozen run in `data.benchmark` and are never mixed into its numbers.
 */
const STANDARD_STUDY = { standardBytes: 532_444, customBytes: 535_012 } as const;

const isObj = (v: unknown): v is Record<string, unknown> => v !== null && typeof v === "object" && !Array.isArray(v);
function rawCandidate(value: unknown, id: string): unknown {
  if (!isObj(value)) return null;
  const all = [value.baseline, ...(Array.isArray(value.candidates) ? value.candidates : [])];
  return all.find((c) => isObj(c) && c.candidate === id) ?? null;
}

function fidelityText(r: BenchRow): string {
  if (r.isBaseline) return "Reference answers";
  return r.fullyExact === true && r.exactCount !== null && r.plotCount !== null
    ? `${r.exactCount}/${r.plotCount} plot outputs match`
    : "Fidelity not established";
}

/* ------------------------------------------------------------------ storage */

function StorageChart({ b, selected, onSelect }: { b: BenchView; selected: BenchRow; onSelect: (id: string) => void }) {
  const max = Math.max(...b.rows.map((r) => r.total ?? 0), STANDARD_STUDY.standardBytes, 1);
  const pct = (n: number | null) => `${((n ?? 0) / max) * 100}%`;
  const studyGain = (100 * (STANDARD_STUDY.customBytes - STANDARD_STUDY.standardBytes)) / STANDARD_STUDY.customBytes;
  return (
    <section className="proof-block" aria-labelledby="bench-storage-title">
      <header className="proof-block__head">
        <p className="pl-eyebrow">Storage</p>
        <h3 id="bench-storage-title">Complete stored bytes, losers included</h3>
        <p className="proof-lead">
          A standard format with the right settings is within 0.5%. What we ship is the verified pipeline, not a magic
          codec.
        </p>
        <p className="pl-fine">
          Every candidate from the frozen run, with payload, metadata and index counted. Bars start at zero. Select a row
          for details.
        </p>
      </header>

      <ol className="bench-rows">
        {b.rows.map((r) => {
          const kept = r === b.retained;
          const delta = r.isBaseline ? null : pctChange(r.total, b.baseline.total);
          return (
            <li key={r.id}>
              <button
                type="button"
                className={`bench-row${kept ? " is-retained" : ""}${r.isBaseline ? " is-baseline" : ""}`}
                aria-pressed={r.id === selected.id}
                onClick={() => onSelect(r.id)}
              >
                <span className="bench-row__top">
                  <span className="bench-row__name">
                    {rowLabel(r)}
                    <code>{r.id}</code>
                    {r.isBaseline && <Chip>Original · reference</Chip>}
                    {kept && <Chip tone="proof">Retained</Chip>}
                  </span>
                  <span className="bench-row__total pl-num">
                    {fmtKiB(r.total)}
                    <small>{fmtBytes(r.total)}</small>
                  </span>
                </span>
                <span className="bench-bar" aria-hidden="true">
                  <span className="bench-bar__payload" style={{ width: pct(r.payload) }} />
                  <span className="bench-bar__meta" style={{ width: pct(r.metadataIndex) }} />
                </span>
                <span className="bench-row__foot">
                  <span>
                    payload {fmtKiB(r.payload)} + metadata/index {fmtKiB(r.metadataIndex)}
                  </span>
                  <span className={r.fullyExact === true ? "is-ok" : undefined}>
                    {r.fullyExact === true && <Icon name="check" size={12} />} {fidelityText(r)}
                  </span>
                  {delta !== null && <span className="pl-num">{fmtPct(delta)} vs original</span>}
                </span>
              </button>
            </li>
          );
        })}
        <li className="bench-row bench-row--study">
          <span className="bench-row__top">
            <span className="bench-row__name">
              Standard GeoTIFF control
              <Chip title="Measured in a different experiment with its own fingerprints and timings">
                Separate study · not part of this run
              </Chip>
            </span>
            <span className="bench-row__total pl-num">
              {fmtKiB(STANDARD_STUDY.standardBytes)}
              <small>{fmtBytes(STANDARD_STUDY.standardBytes)}</small>
            </span>
          </span>
          <span className="bench-bar bench-bar--study" aria-hidden="true">
            <span className="bench-bar__study" style={{ width: pct(STANDARD_STUDY.standardBytes) }} />
          </span>
          <span className="bench-row__foot">
            <span>
              {fmtFixed(studyGain, 2)}% smaller than the custom store ({fmtBytes(STANDARD_STUDY.customBytes)}) in that
              study: an optimized standard GeoTIFF on the same Hansen chip.
            </span>
          </span>
        </li>
      </ol>

      <div className="bench-legend" aria-hidden="true">
        <span>
          <i className="bench-swatch bench-swatch--payload" /> Payload
        </span>
        <span>
          <i className="bench-swatch bench-swatch--meta" /> Metadata + index
        </span>
        <span>
          <i className="bench-swatch bench-swatch--study" /> Separate study
        </span>
      </div>

      <div className="bench-detail" aria-live="polite">
        <p className="pl-eyebrow">Selected · {rowLabel(selected)}</p>
        <dl className="bench-detail__grid">
          <div>
            <dt>Payload</dt>
            <dd>{fmtBytes(selected.payload)}</dd>
          </div>
          <div>
            <dt>Metadata + index</dt>
            <dd>{fmtBytes(selected.metadataIndex)}</dd>
          </div>
          <div>
            <dt>Encoding wall time</dt>
            <dd>
              {selected.isBaseline
                ? "Not measured (existing chips)"
                : selected.preprocessingMs === null
                  ? "Not measured"
                  : `${fmtFixed(selected.preprocessingMs, 1)} ms`}
            </dd>
          </div>
          <div>
            <dt>Chunk width</dt>
            <dd>{selected.isBaseline ? "Source organization" : selected.chunkSize === null ? "Unavailable" : `${selected.chunkSize} cells`}</dd>
          </div>
        </dl>
      </div>
    </section>
  );
}

/* ------------------------------------------------------------------- timing */

/** A tidy axis ceiling just above `max` (always starts at zero). */
function axisCeil(max: number): number {
  if (!(max > 0)) return 1;
  const mag = 10 ** Math.floor(Math.log10(max));
  const step = mag / 2;
  return Math.ceil((max * 1.06) / step) * step;
}

function DotRow({ label, stats, axis, tone }: { label: string; stats: TimingStats | null; axis: number; tone: "base" | "kept" | "other" }) {
  const samples = stats?.samples ?? [];
  const sorted = [...samples].sort((a, b) => a - b);
  const left = (n: number) => `${Math.min(100, Math.max(0, (n / axis) * 100))}%`;
  return (
    <li className={`bench-timing-row bench-timing-row--${tone}`}>
      <span className="bench-timing-row__name">{label}</span>
      {stats && samples.length ? (
        <span
          className="bench-dots"
          role="img"
          aria-label={`${samples.length} measured repetitions from ${fmtFixed(sorted[0], 2)} to ${fmtFixed(sorted.at(-1), 2)} milliseconds; median ${fmtFixed(stats.median, 2)} milliseconds`}
        >
          {sorted.map((n, i) => (
            <i key={i} className="bench-dots__dot" style={{ left: left(n), top: `${50 + ((i % 3) - 1) * 24}%` }} />
          ))}
          {stats.median !== null && <i className="bench-dots__median" style={{ left: left(stats.median) }} />}
        </span>
      ) : (
        <span className="bench-dots bench-dots--none pl-hatch" role="img" aria-label="Unmeasured" />
      )}
      <span className="bench-timing-row__num pl-num">
        {stats?.median != null ? (
          <>
            <b>{fmtFixed(stats.median, 2)} ms</b> median
            <small>
              p95 {fmtFixed(stats.p95, 2)} · n={stats.repetitions ?? "?"}
            </small>
          </>
        ) : (
          "Unmeasured"
        )}
      </span>
    </li>
  );
}

function TimingPanel({
  title,
  sub,
  info,
  rows,
  pick,
  kept,
}: {
  title: string;
  sub: string;
  info: React.ReactNode;
  rows: BenchRow[];
  pick: (r: BenchRow) => TimingStats | null;
  kept: BenchRow | null;
}) {
  const everything = rows.flatMap((r) => pick(r)?.samples ?? []);
  const axis = axisCeil(Math.max(...everything, 0));
  return (
    <section className="bench-panel" aria-label={title}>
      <header className="bench-panel__head">
        <h4>{title}</h4>
        <Info label={`About ${title.toLowerCase()} timing`}>{info}</Info>
      </header>
      <p className="pl-fine">{sub}</p>
      <ul className="bench-timing">
        {rows.map((r) => (
          <DotRow key={r.id} label={rowLabel(r)} stats={pick(r)} axis={axis} tone={r.isBaseline ? "base" : r === kept ? "kept" : "other"} />
        ))}
      </ul>
      <div className="bench-axis pl-num" aria-hidden="true">
        <span>0</span>
        <span>{fmtFixed(axis / 2, axis < 5 ? 2 : 1)}</span>
        <span>{fmtFixed(axis, axis < 5 ? 2 : 1)} ms</span>
      </div>
    </section>
  );
}

function TimingMultiples({ b }: { b: BenchView }) {
  const batch = b.queryBatch;
  const reps = b.retained?.fresh?.repetitions ?? b.baseline.fresh?.repetitions ?? null;
  return (
    <section className="proof-block" aria-labelledby="bench-timing-title">
      <header className="proof-block__head">
        <p className="pl-eyebrow">Timing</p>
        <h3 id="bench-timing-title">Hot query vs fresh-process load + query</h3>
        <p className="pl-fine">
          Each dot is one measured repetition ({reps ?? "?"} per row); the vertical bar is the median. Same axis within a
          panel, starting at zero. With {reps ?? "?"} repetitions the nearest-rank p95 equals the maximum, a small-sample
          statistic, not a guarantee.
        </p>
      </header>
      <div className="bench-panels">
        <TimingPanel
          title="Hot query"
          sub={`Full regional data already loaded; ${batch ?? "?"}-plot batch, wall ms.`}
          info={<>Only the query batch is timed. Imports and shared geometry are excluded. Both representations run the same query code on the same arrays, so these differences are noise-level.</>}
          rows={b.rows}
          pick={(r) => r.hot}
          kept={b.retained}
        />
        <TimingPanel
          title="Fresh-process load + query"
          sub={`New process per repetition: full load, integrity validation, ${batch ?? "?"}-plot batch, wall ms.`}
          info={<>Times the full load plus queries after imports and the shared geometry read, which are excluded. The OS file cache was uncontrolled and probably warm: process-fresh, not disk-cold.</>}
          rows={b.rows}
          pick={(r) => r.fresh}
          kept={b.retained}
        />
      </div>
    </section>
  );
}

/* --------------------------------------------------------------------- root */

export default function Benchmark({ value }: { value: unknown }) {
  const b = useMemo(() => readBenchmark(value), [value]);
  const [choice, setChoice] = useState("");
  if (!b)
    return (
      <section className="proof-block" aria-label="Measured encoding experiments">
        <EmptyState
          title="Measurements unavailable"
          detail="A benchmark is shown only after the engine exports its result, units and method."
        />
      </section>
    );
  const selected = b.rows.find((r) => r.id === choice) ?? b.retained ?? b.baseline;
  return (
    <>
      <StorageChart b={b} selected={selected} onSelect={setChoice} />
      <TimingMultiples b={b} />
      <section className="proof-block" aria-label="Measurement method">
        <ul className="bench-method">
          <li>
            <b>Frozen experiment</b>
            <code title={b.experimentId ?? undefined}>{b.experimentId ? `${b.experimentId.slice(0, 20)}…` : "Unavailable"}</code>
          </li>
          <li>
            <b>Cohort</b>
            {b.retained?.plotCount != null ? `${b.retained.plotCount} real supplied plots` : "Unavailable"}
          </li>
          <li>
            <b>Shared inputs</b>
            {fmtInt(b.commonInputBytes)} B geometry + supplier files, excluded on both sides
          </li>
          <li>
            <b>Grid</b>
            Same coverage, bands and native cells
          </li>
        </ul>
        <details className="pl-disclosure">
          <summary>Measurement method, environment and experiment identity</summary>
          <div className="pl-disclosure__body">
            <pre>{JSON.stringify({ experiment_id: b.experimentId, method: b.raw.method, environment: b.raw.environment, settings: b.raw.settings }, null, 2)}</pre>
          </div>
        </details>
        <details className="pl-disclosure">
          <summary>
            Full evidence for the selected candidate <span className="pl-disclosure__meta">{selected.id}</span>
          </summary>
          <div className="pl-disclosure__body">
            <pre>{JSON.stringify(rawCandidate(value, selected.id), null, 2)}</pre>
          </div>
        </details>
      </section>
    </>
  );
}
