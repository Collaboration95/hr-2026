import { useState } from "react";
import { Icon, Pill } from "./components/Primitives";

type Stats = {
  median?: number;
  p95?: number;
  repetitions?: number;
  samples?: number[];
};
type Candidate = {
  candidate: string;
  status?: string;
  fully_exact?: boolean;
  storage?: {
    total_bytes?: number;
    payload_bytes?: number;
    metadata_index_bytes?: number;
  };
  queries?: {
    hot?: { wall_ms?: Stats; peak_rss?: { bytes?: number } };
    process_cold?: { wall_ms?: Stats; peak_rss?: { bytes?: number }[] };
  };
  preprocessing?: { wall_ms?: number; codec_report?: { chunk_size?: number } };
  fidelity?: { exact_count?: number; plot_count?: number };
  roundtrip?: unknown;
};
type Bench = {
  schema_version: string;
  experiment_id: string;
  baseline: Candidate;
  candidates: Candidate[];
  overall_storage_choice?: string;
  winner?: { candidate?: string; criterion?: string };
  method: Record<string, unknown>;
  environment: Record<string, unknown>;
  common_input_bytes?: number;
  identity?: { settings?: { chunk_size?: number; repetitions?: number } };
};
const labels: Record<string, string> = {
  source_geotiff: "Original GeoTIFF",
  packed14_zstd: "14-bit packed",
  uint16_zstd: "16-bit words",
  separate_zstd: "Separate bands",
  bitplane_zstd: "Bitplanes",
  separate_zstd_l9: "Separate bands · Zstd level 9",
  separate_zstd_l19: "Separate bands · Zstd level 19",
};
const num = (n: number | undefined, d = 2) =>
  typeof n === "number" && Number.isFinite(n)
    ? n.toLocaleString(undefined, {
        maximumFractionDigits: d,
        minimumFractionDigits: d,
      })
    : "Unavailable";
const kib = (n: number | undefined) =>
  n == null ? "Unavailable" : `${num(n / 1024, 1)} KiB`;
function MiniDistribution({ stats }: { stats: Stats | undefined }) {
  if (!stats?.samples?.length) return <span>Unmeasured</span>;
  const max = Math.max(...stats.samples),
    min = Math.min(...stats.samples);
  return (
    <div
      className="distribution"
      title={`Range ${num(min, 3)}–${num(max, 3)} ms; each dot is one measured repetition`}
    >
      <span>{num(min, 2)}</span>
      <svg
        viewBox="0 0 200 22"
        aria-label={`${stats.samples.length} measured repetitions, range ${min} to ${max} milliseconds`}
      >
        <line x1="6" x2="194" y1="11" y2="11" stroke="#bac9ac" />
        {stats.samples.map((n, i) => (
          <circle
            key={i}
            cx={6 + ((n - min) / (max - min || 1)) * 188}
            cy={7 + (i % 3) * 4}
            r="3"
            fill="#416b39"
            opacity=".7"
          />
        ))}
      </svg>
      <span>{num(max, 2)} ms</span>
    </div>
  );
}
export default function Benchmark({ value }: { value: unknown }) {
  const [choice, setChoice] = useState("");
  const [timing, setTiming] = useState<"hot" | "process_cold">("hot");
  const b = value as Bench | null;
  if (
    !b ||
    b.schema_version !== "plotline.benchmark.v1" ||
    !b.baseline ||
    !Array.isArray(b.candidates)
  )
    return (
      <section className="benchmark-empty">
        <h3>Measurements unavailable</h3>
        <p>
          A benchmark is shown only after the engine exports its result, units
          and method.
        </p>
      </section>
    );
  const all = [b.baseline, ...b.candidates];
  const selected =
    all.find((c) => c.candidate === choice) ||
    all.find((c) => c.candidate === b.winner?.candidate) ||
    all[0];
  const max = Math.max(...all.map((c) => c.storage?.total_bytes || 0), 1);
  const total = selected.storage?.total_bytes;
  const baseline = b.baseline.storage?.total_bytes;
  const delta = total != null && baseline ? 100 * (total / baseline - 1) : null;
  const stats = selected.queries?.[timing]?.wall_ms;
  return (
    <section className="benchmark" aria-label="Measured encoding experiments">
      <div className="section-title">
        <div>
          <span className="eyebrow">04 / Measured tradeoffs</span>
          <h2>
            Keep the answer.
            <br />
            <em>Question the representation.</em>
          </h2>
        </div>
        <Pill>Frozen experiment</Pill>
      </div>
      <p className="benchmark-intro">
        Identical regional grid. All required payload, indexes and metadata
        included. A compact format earns its place through measurements.
      </p>
      <div className="benchmark-decision">
        <Icon name="info" />
        <p>
          <strong>
            {b.overall_storage_choice === "source_geotiff"
              ? "Compressed originals remain the storage choice."
              : `Storage choice: ${labels[b.overall_storage_choice || ""] || b.overall_storage_choice || "Not selected"}.`}
          </strong>
          <span>
            Prototype encoding agreement does not guarantee smaller storage.
            Select a representation to inspect its measured tradeoffs.
          </span>
        </p>
      </div>
      <div className="benchmark-grid">
        <div className="storage-chart">
          <div className="chart-heading">
            <span>Complete stored footprint</span>
            <span>KiB · lower is smaller</span>
          </div>
          {all.map((c) => (
            <button
              key={c.candidate}
              aria-pressed={c.candidate === selected.candidate}
              onClick={() => setChoice(c.candidate)}
              className="storage-row"
            >
              <div>
                <strong>{labels[c.candidate] || c.candidate}</strong>
                <span>{kib(c.storage?.total_bytes)}</span>
              </div>
              <div className="storage-track">
                <span
                  className="payload-bar"
                  style={{
                    width: `${((c.storage?.payload_bytes || 0) / max) * 100}%`,
                  }}
                />
                <span
                  className="metadata-bar"
                  style={{
                    width: `${((c.storage?.metadata_index_bytes || 0) / max) * 100}%`,
                  }}
                />
              </div>
              <small>
                {c === b.baseline
                  ? "Compressed source baseline"
                  : c.fully_exact === true
                    ? `${c.fidelity?.exact_count ?? "—"}/${c.fidelity?.plot_count ?? "—"} plot outputs match`
                    : "Fidelity not established"}
                {c.candidate === b.overall_storage_choice
                  ? " · storage choice"
                  : ""}
              </small>
            </button>
          ))}
          <div className="storage-legend">
            <span>
              <i />
              Payload
            </span>
            <span>
              <i />
              Metadata + indexes
            </span>
          </div>
        </div>
        <div className="candidate-detail">
          <span className="eyebrow">Selected representation</span>
          <h3>{labels[selected.candidate] || selected.candidate}</h3>
          <code className="candidate-id">{selected.candidate}</code>
          <div className="candidate-size">
            <strong>{kib(total)}</strong>
            <span>
              {delta == null
                ? "Comparison unavailable"
                : delta === 0
                  ? "Original-source baseline"
                  : `${num(Math.abs(delta), 1)}% ${delta > 0 ? "larger" : "smaller"} than original`}
            </span>
          </div>
          <dl>
            <div>
              <dt>Payload</dt>
              <dd>{kib(selected.storage?.payload_bytes)}</dd>
            </div>
            <div>
              <dt>Metadata + indexes</dt>
              <dd>{kib(selected.storage?.metadata_index_bytes)}</dd>
            </div>
            <div>
              <dt>Preprocessing wall time</dt>
              <dd>
                {selected.preprocessing?.wall_ms == null
                  ? "Not measured"
                  : `${num(selected.preprocessing.wall_ms)} ms`}
              </dd>
            </div>
            <div>
              <dt>Native chunk width</dt>
              <dd>
                {selected === b.baseline
                  ? "Source organization"
                  : `${selected.preprocessing?.codec_report?.chunk_size ?? b.identity?.settings?.chunk_size ?? "Unavailable"} cells`}
              </dd>
            </div>
          </dl>
          <div className="timing-tabs">
            <button
              aria-pressed={timing === "hot"}
              onClick={() => setTiming("hot")}
            >
              Loaded query
            </button>
            <button
              aria-pressed={timing === "process_cold"}
              onClick={() => setTiming("process_cold")}
            >
              Fresh-process load + query
            </button>
          </div>
          <div className="timing-number">
            <strong>
              {num(stats?.median)}
              <small> ms</small>
            </strong>
            <span>
              Median / {String(b.method.query_count_per_batch ?? 17)}-plot batch
            </span>
          </div>
          <MiniDistribution stats={stats} />
          <p>
            {timing === "hot"
              ? "Full regional data loaded before query timing."
              : "Includes full data loading and integrity validation. OS file cache is uncontrolled; this is not disk-cold."}{" "}
            {stats?.repetitions ?? "Unavailable"} measured repetitions.
          </p>
        </div>
      </div>
      <div className="benchmark-method">
        <span>
          <b>Frozen experiment</b>
          <code title={b.experiment_id}>{b.experiment_id.slice(0, 20)}…</code>
        </span>
        <span>
          <b>Cohort</b>17 real supplied plots
        </span>
        <span>
          <b>Shared inputs</b>
          {kib(b.common_input_bytes)} excluded on both sides
        </span>
        <span>
          <b>Grid</b>Same coverage, bands and native cells
        </span>
      </div>
      <details className="json-details">
        <summary>
          Inspect measurement method, environment and experiment identity
        </summary>
        <pre>
          {JSON.stringify(
            {
              experiment_id: b.experiment_id,
              method: b.method,
              environment: b.environment,
              settings: b.identity?.settings,
            },
            null,
            2,
          )}
        </pre>
      </details>
      <details className="json-details">
        <summary>Inspect full selected-candidate evidence</summary>
        <pre>{JSON.stringify(selected, null, 2)}</pre>
      </details>
    </section>
  );
}
