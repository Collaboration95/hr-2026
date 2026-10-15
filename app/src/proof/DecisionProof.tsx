import type * as React from "react";
import { Chip, Info, Stat, type Tone } from "../components/Primitives";
import type { DecisionSummary } from "../decision-data";
import {
  controlRows,
  fmtInt,
  fmtPct,
  fmtSig,
  fmtSize,
  fmtX,
  heroModel,
  isBaselineRow,
  ladderRows,
  scaleModel,
} from "../decision-model";

const Sub = ({ children }: { children: React.ReactNode }) => <span className="proof-hero__sub">{children}</span>;

function HeroCell({
  info,
  infoLabel,
  wide,
  children,
}: {
  info: React.ReactNode;
  infoLabel: string;
  wide?: boolean;
  children: React.ReactNode;
}) {
  return (
    <li className={`proof-hero__cell dec-hero__cell${wide ? " dec-hero__cell--wide" : ""}`}>
      {children}
      <span className="proof-hero__info">
        <Info label={infoLabel}>{info}</Info>
      </span>
    </li>
  );
}

/** Storage, identical answers and speed. Every figure comes from the validated summary. */
function Hero({ summary }: { summary: DecisionSummary }) {
  const { storage, same, speed } = heroModel(summary);
  const index = speed.index;
  const table = speed.table;
  return (
    <ul className="dec-hero" aria-label="Headline results of the decision layer">
      <HeroCell
        infoLabel="About the storage figure"
        info={
          <>
            The decision store ({fmtInt(storage.decisionBytes)} B) against the original source layers (
            {fmtInt(storage.originalBytes)} B: the Hansen bands and the JRC 2020 chip as supplied). It keeps what the EUDR
            decision needs, not every pixel; the ladder below lists what is dropped.
          </>
        }
      >
        <Stat
          tone="proof"
          value={fmtPct(storage.percent)}
          label={
            <>
              smaller than the original layers · {fmtX(storage.ratio)}
              <Sub>
                {fmtSize(storage.decisionBytes)} decision store vs {fmtSize(storage.originalBytes)} originals
              </Sub>
            </>
          }
        />
      </HeroCell>

      <HeroCell
        wide
        infoLabel="About identical answers"
        info={
          <>
            Every cell code derived from the original layers equals the stored code
            {same.mismatches === null ? " (exhaustive comparison not recorded)" : ""}, so under the shared centre rule
            every polygon returns the same output, not only the registered plots. {summary.fidelity.theorem}{" "}
            {same.v1Equal
              ? "The screening layer's Hansen counts also equal the retained v1 outputs."
              : "The screening layer's Hansen counts differ from the retained v1 outputs."}
          </>
        }
      >
        <Stat
          tone={same.exact ? "proof" : undefined}
          value={same.equalCells === null ? "Unavailable" : `${fmtInt(same.equalCells)}/${fmtInt(same.cells)}`}
          label={
            <>
              cells identical to the original layers
              <Sub>
                {same.mismatches === 0
                  ? "so every polygon is identical, not just the registered plots"
                  : same.mismatches === null
                    ? "exhaustive comparison not recorded"
                    : `${fmtInt(same.mismatches)} cells differ`}
              </Sub>
              <Sub>
                {fmtInt(same.plotsEqual)}/{fmtInt(same.plotsTotal)} plots · {fmtInt(same.fuzzEqual)}/{fmtInt(same.fuzzCompared)}{" "}
                fuzzed polygons
              </Sub>
            </>
          }
        />
      </HeroCell>

      <HeroCell
        infoLabel="About the speed figure"
        info={
          <>
            Hot batch: the {fmtInt(same.plotsTotal)} registered plots with the layers already loaded, against the retained
            v1 query on the original layers. It applies to registered plots only.
            {index && (
              <>
                {" "}
                End to end, including starting Python, the same path is {fmtX(index.speedup_vs_v1.end_to_end)}
                {table && <> and the answer table {fmtX(table.speedup_vs_v1.end_to_end)}</>}.
              </>
            )}
            {speed.newPolygon && (
              <>
                {" "}
                New polygons use the decision layer with exact fast selection: {fmtX(speed.newPolygon.speedup_vs_v1.hot)} hot.
              </>
            )}
          </>
        }
      >
        <Stat
          value={index ? fmtX(index.speedup_vs_v1.hot) : "Unavailable"}
          label={
            <>
              faster hot batch · registered plots only
              <Sub>
                {fmtInt(same.plotsTotal)}-plot batch, decision layer + plot index vs v1
              </Sub>
              {table && <Sub>registered-plot answer table: {fmtX(table.speedup_vs_v1.hot)}</Sub>}
            </>
          }
        />
      </HeroCell>
    </ul>
  );
}

function BlockHead({ id, eyebrow, title, lead }: { id: string; eyebrow: string; title: string; lead?: React.ReactNode }) {
  return (
    <header className="proof-block__head">
      <p className="pl-eyebrow">{eyebrow}</p>
      <h3 id={id}>{title}</h3>
      {lead && <p className="dec-lead">{lead}</p>}
    </header>
  );
}

function Ladder({ summary }: { summary: DecisionSummary }) {
  const rows = ladderRows(summary);
  const original = summary.storage.baselines.original_all_layers;
  return (
    <section className="proof-block" aria-labelledby="dec-ladder-title">
      <BlockHead
        id="dec-ladder-title"
        eyebrow="Storage ladder"
        title="Each rung keeps less, and says what it drops"
      />
      <div className="pl-table-wrap dec-wrap">
        <table className="pl-table dec-table dec-ladder">
          <caption>
            Percent smaller is measured against the original source layers ({fmtInt(original)} B). The audit tier below
            counts a different boundary (the v1 loader&rsquo;s inputs), so its percentage differs for the same archive.
            A lime edge marks a layer we ship.
          </caption>
          <thead>
            <tr>
              <th scope="col">Layer</th>
              <th scope="col">Answers</th>
              <th scope="col">Keeps</th>
              <th scope="col">Drops</th>
              <th scope="col" className="is-num">Bytes</th>
              <th scope="col" className="is-num">Smaller than originals<small>and ratio</small></th>
            </tr>
          </thead>
          <tbody>
            {rows.map((r) => (
              <tr key={r.key} className={r.shipped ? "is-ship" : undefined} data-rung={r.key}>
                <th scope="row" className="dec-ladder__name">
                  <span className="dec-ladder__title">
                    {r.tag && <span className="dec-tag">{r.tag}</span>}
                    {r.name}
                  </span>
                  {r.contract && <code>{r.contract}</code>}
                </th>
                <td className="is-prose">{r.answers}</td>
                <td className="is-prose">{r.keeps}</td>
                <td className="is-prose">
                  <ul className="dec-list">
                    {r.drops.map((d) => (
                      <li key={d}>{d}</li>
                    ))}
                  </ul>
                </td>
                <td className="is-num">
                  <b>{fmtInt(r.bytes)} B</b>
                  <small>{fmtSize(r.bytes)}</small>
                  {r.bytesNote && <small className="dec-note">{r.bytesNote}</small>}
                </td>
                <td className="is-num">
                  <b>{fmtPct(r.percent)}</b>
                  <small>{fmtX(r.ratio)}</small>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </section>
  );
}

const verdictTone = (verdict: string): Tone => (verdict === "keep" || verdict === "ship" ? "proof" : "neutral");
const sentence = (s: string) => s.charAt(0).toUpperCase() + s.slice(1);

function Layers({ summary }: { summary: DecisionSummary }) {
  const rows = summary.layer_analysis;
  const max = Math.max(...rows.map((r) => r.zstd19_bytes), 1);
  return (
    <section className="proof-block" aria-labelledby="dec-layers-title">
      <BlockHead
        id="dec-layers-title"
        eyebrow="Layer analysis"
        title="What the decision needs"
        lead="Each plane compressed alone, and the EUDR question that needs it. A plane no question needs is not stored."
      />
      <div className="pl-table-wrap dec-wrap">
        <table className="pl-table dec-table dec-layers">
          <caption>Bytes are each plane compressed alone with zstd level 19.</caption>
          <thead>
            <tr>
              <th scope="col">Plane</th>
              <th scope="col" className="is-num">Bytes</th>
              <th scope="col">Needed for</th>
              <th scope="col">Verdict</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((r) => (
              <tr key={r.plane} data-verdict={r.verdict} className={r.verdict === "ship" ? "is-ship" : undefined}>
                <th scope="row">{r.plane}</th>
                <td className="is-num">
                  <b>{fmtInt(r.zstd19_bytes)}</b>
                  <span className="dec-bar" aria-hidden="true">
                    <i style={{ width: `${(100 * r.zstd19_bytes) / max}%` }} />
                  </span>
                </td>
                <td className="is-prose">
                  {r.needed_for.length ? (
                    <ul className="dec-list">
                      {r.needed_for.map((q) => (
                        <li key={q}>{q}</li>
                      ))}
                    </ul>
                  ) : (
                    <span className="pl-muted">No question needs it</span>
                  )}
                </td>
                <td>
                  <Chip tone={verdictTone(r.verdict)}>{sentence(r.verdict)}</Chip>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </section>
  );
}

function Speed({ summary }: { summary: DecisionSummary }) {
  const plots = fmtInt(Object.keys(summary.plots).length);
  return (
    <section className="proof-block" aria-labelledby="dec-speed-title">
      <BlockHead
        id="dec-speed-title"
        eyebrow="Speed"
        title="Same answers, less work"
        lead="Median of repeated runs; every row returns the same answers as the original layers."
      />
      <div className="pl-table-wrap dec-wrap">
        <table className="pl-table dec-table dec-speed">
          <caption>
            Hot batch: {plots} plots with the layers already loaded. Load + query: a fresh process, after imports. End to
            end: a fresh Python process including its start. Speed-ups are against P0, the retained v1 query.
          </caption>
          <thead>
            <tr>
              <th scope="col">Path</th>
              <th scope="col" className="is-num">Hot batch<small>ms</small></th>
              <th scope="col" className="is-num">Per plot<small>µs</small></th>
              <th scope="col" className="is-num">Load + query<small>ms</small></th>
              <th scope="col" className="is-num">End to end<small>ms</small></th>
              <th scope="col" className="is-num">Peak memory<small>MB</small></th>
              <th scope="col" className="is-num">Bytes read<small>B</small></th>
              <th scope="col" className="is-num">Hot vs v1</th>
              <th scope="col" className="is-num">End to end vs v1</th>
            </tr>
          </thead>
          <tbody>
            {summary.speed.map((r) => (
              <tr key={r.path} data-path={r.path} data-registered={r.registered_plots_only}>
                <th scope="row" className="dec-speed__name">
                  <span className="dec-speed__title">
                    <code>{r.path}</code>
                    {r.label}
                  </span>
                  {r.registered_plots_only ? (
                    <Chip tone="neutral" title="Answers registered plots only; new polygons use the decision layer">
                      registered plots only
                    </Chip>
                  ) : (
                    <span className="dec-speed__any">any polygon</span>
                  )}
                </th>
                <td className="is-num">{fmtSig(r.hot_17_plots_ms)}</td>
                <td className="is-num">{fmtSig(r.hot_per_plot_us)}</td>
                <td className="is-num">{fmtSig(r.process_cold_ms)}</td>
                <td className="is-num">{fmtSig(r.end_to_end_ms)}</td>
                <td className="is-num">{fmtSig(r.peak_rss_mb)}</td>
                <td className="is-num">{fmtInt(r.bytes_read)}</td>
                <td className="is-num">{isBaselineRow(r) ? <span className="pl-muted">baseline</span> : fmtX(r.speedup_vs_v1.hot)}</td>
                <td className="is-num">{isBaselineRow(r) ? <span className="pl-muted">baseline</span> : fmtX(r.speedup_vs_v1.end_to_end)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <p className="pl-fine dec-caveat">
        Registered-plot rows answer registered plots only; a new polygon uses the decision layer (P3, P4). Timing conditions
        are listed under limits below.
      </p>
    </section>
  );
}

function Scale({ summary }: { summary: DecisionSummary }) {
  const scale = scaleModel(summary);
  const controls = controlRows(summary);
  const lead = controls[0];
  return (
    <section className="proof-block" aria-labelledby="dec-scale-title">
      <BlockHead id="dec-scale-title" eyebrow="Scale and controls" title="It scales, and the codec is not the story" />
      <div className="dec-cards">
        <div className="dec-card" data-card="tile">
          <h4>Whole tile</h4>
          <p className="dec-card__line">
            Originals <b>{fmtSize(scale.original)}</b>
            <span className="dec-arrow" aria-hidden="true">→</span>
            screening <b>{fmtSize(scale.screen)}</b> ({fmtPct(scale.screenPercent)} smaller)
            <span className="dec-arrow" aria-hidden="true">→</span>
            decision <b>{fmtSize(scale.decision)}</b> ({fmtPct(scale.decisionPercent)} smaller)
          </p>
          <p className="pl-fine">
            {scale.tile}. Against a lossless zstd-19 copy of the same layers ({fmtSize(scale.yardstick)}):{" "}
            {fmtPct(scale.screenVsYardstick)} and {fmtPct(scale.decisionVsYardstick)} smaller.
          </p>
        </div>
        <div className="dec-card" data-card="control">
          <h4>Standard-format control</h4>
          <ul className="dec-control">
            {controls.map((c) => (
              <li key={c.contract}>
                <span>{c.name}</span>
                <span>
                  ours <b>{fmtInt(c.ours)} B</b> · {c.controlName} <b>{fmtInt(c.control)} B</b>
                </span>
              </li>
            ))}
          </ul>
          <p className="pl-fine">
            Most of the saving comes from what the layers keep, not from the container: a standard GeoTIFF of the same
            codes is already {fmtPct(lead.controlPercent)} smaller than the originals; our store is{" "}
            {fmtPct(lead.oursPercent)}.
          </p>
        </div>
      </div>
    </section>
  );
}

/** "Keep the decision, not the data": the headline section above the lossless audit tier. */
export default function DecisionProof({ summary }: { summary: DecisionSummary }) {
  return (
    <div className="dec" data-section="decision-layer">
      <Hero summary={summary} />
      <Ladder summary={summary} />
      <Layers summary={summary} />
      <Speed summary={summary} />
      <Scale summary={summary} />
      <section className="dec-limits" aria-labelledby="dec-limits-title">
        <p className="pl-eyebrow" id="dec-limits-title">Limits</p>
        <ul>
          {summary.limitations.map((l) => (
            <li key={l}>{l}</li>
          ))}
        </ul>
      </section>
      <div className="dec-more">
        <details className="pl-disclosure">
          <summary>
            Evidence files<span className="pl-disclosure__meta">{Object.keys(summary.evidence).length} SHA-256 digests</span>
          </summary>
          <div className="pl-disclosure__body">
            <dl className="dec-evidence">
              {Object.entries(summary.evidence).map(([name, digest]) => (
                <div key={name}>
                  <dt>{name}</dt>
                  <dd>{digest}</dd>
                </div>
              ))}
            </dl>
          </div>
        </details>
      </div>
    </div>
  );
}
