import type * as React from "react";
import type { LiveQueryResponse } from "../live-client";
import { Chip, Glyph, Icon, Info } from "../components/Primitives";
import NativePreview from "./NativePreview";
import CellsTable from "./CellsTable";

const MEASURES = [
  ["selected_cell_count", "Selected cells"],
  ["valid_land_cell_count", "Valid land cells"],
  ["unknown_cell_count", "Unknown cells"],
  ["out_of_coverage_cell_count", "Outside coverage"],
] as const;

const YEARS = Array.from({ length: 25 }, (_, i) => 2001 + i);

/** The completed state: a validated response, shown with its evidence. */
export default function AnswerResult({
  result,
  year,
  onYear,
  headingRef,
  onDownload,
}: {
  result: LiveQueryResponse;
  year: number;
  onYear: (year: number) => void;
  headingRef: React.RefObject<HTMLHeadingElement | null>;
  onDownload: () => void;
}) {
  const source = result.source_result;
  const agrees =
    result.comparison.equal === true &&
    result.comparison.differing_fields.length === 0;
  const yearCount = source.yearly_loss_counts?.[String(year)];
  return (
    <div className="live-result" data-phase="completed">
      <div className="live-result-heading">
        <div>
          <span className="pl-eyebrow">
            Validated response · temporary geometry
          </span>
          <h3 ref={headingRef} tabIndex={-1}>
            Same answer. Inspect the evidence.
          </h3>
        </div>
        <button type="button" className="pl-btn" onClick={onDownload}>
          <Icon name="download" size={15} />
          Download live receipt
        </button>
      </div>

      <div className="live-agree">
        {agrees ? (
          <Chip tone="proof">
            <Icon name="check" size={13} />
            Original = compact
          </Chip>
        ) : (
          <Chip tone="error">
            <Icon name="alert" size={13} />
            Original ≠ compact
          </Chip>
        )}
        <span className="pl-fine">
          {result.comparison.differing_fields.length} differing fields
        </span>
        <Info label="What original = compact means">
          Both stores returned the same result for this region on one
          identified snapshot. This is an engineering agreement, not
          satellite truth or a legal finding.
        </Info>
      </div>

      <p className="live-interpretation">{result.interpretation}</p>

      <div className="pl-table-wrap live-measures">
        <table className="pl-table">
          <caption>Original and compact · actual returned counts</caption>
          <thead>
            <tr>
              <th scope="col">Measure</th>
              <th scope="col">Original</th>
              <th scope="col">Compact</th>
              <th scope="col">Match</th>
            </tr>
          </thead>
          <tbody>
            {MEASURES.map(([key, label]) => {
              const a = source[key],
                b = result.compact_result[key];
              return (
                <tr key={key}>
                  <th scope="row">{label}</th>
                  <td>{a}</td>
                  <td>{b}</td>
                  <td className={a === b ? "live-match" : "live-mismatch"}>
                    {a === b ? (
                      <>
                        <Icon name="check" size={13} />
                        <span className="pl-sr-only">Equal</span>
                      </>
                    ) : (
                      "Differs"
                    )}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>

      <p className="live-support">
        <Chip tone={source.support === "complete" ? "neutral" : "unknown"}>
          {source.support !== "complete" && <Glyph kind="unknown" />}
          Support: {source.support}
        </Chip>
        {source.unknown_reasons.length > 0 && (
          <span>{source.unknown_reasons.join(" · ")}</span>
        )}
      </p>

      <div className="live-periods">
        {Object.entries(source.periods).map(([period, value]) => (
          <div
            key={period}
            className="live-period"
            data-state={
              value.mapped_loss_present === null
                ? "unknown"
                : value.mapped_loss_present
                  ? "loss"
                  : "zero"
            }
          >
            <b className="pl-eyebrow">{period}</b>
            <strong>
              {value.observed_loss_cell_count === null ? (
                "Unavailable"
              ) : (
                <>
                  <span className="live-period__n">
                    {value.observed_loss_cell_count}
                  </span>{" "}
                  mapped loss cells
                </>
              )}
            </strong>
            <span className="live-period__state">
              {value.mapped_loss_present === null ? (
                <>
                  <Glyph kind="unknown" />
                  Mapped result unknown
                </>
              ) : value.mapped_loss_present ? (
                <>
                  <Glyph kind="loss" />
                  Mapped loss observed · support {source.support}
                </>
              ) : (
                <>
                  <Glyph kind="loss" hollow />
                  Known zero · support {source.support}
                </>
              )}
            </span>
          </div>
        ))}
      </div>

      <div className="live-map-head">
        <label className="live-year">
          <span>Native evidence year</span>
          <select
            className="pl-select"
            value={year}
            onChange={(e) => onYear(Number(e.target.value))}
          >
            {YEARS.map((y) => (
              <option key={y}>{y}</option>
            ))}
          </select>
        </label>
        <span
          className="live-year__count"
          data-loss={typeof yearCount === "number" && yearCount > 0}
        >
          <b className="pl-num">{yearCount ?? "Unavailable"}</b> mapped loss
          cells in {year}
        </span>
      </div>
      <NativePreview result={result} year={year} />

      <details className="pl-disclosure">
        <summary>
          <span>
            All {result.evidence.returned_cell_count} selected native cells
          </span>
        </summary>
        <div className="pl-disclosure__body">
          <CellsTable cells={result.evidence.cells.features} />
        </div>
      </details>

      <details className="pl-disclosure">
        <summary>
          <span>Request, snapshot and receipt identity</span>
        </summary>
        <div className="pl-disclosure__body">
          <dl className="pl-dl live-identity">
            <div>
              <dt>Request</dt>
              <dd>{result.request_id}</dd>
            </div>
            <div>
              <dt>Snapshot SHA-256</dt>
              <dd>{result.snapshot_id}</dd>
            </div>
            <div>
              <dt>Receipt SHA-256</dt>
              <dd>{result.receipt.sha256}</dd>
            </div>
            <div>
              <dt>Query</dt>
              <dd>{result.query_version}</dd>
            </div>
          </dl>
          <p className="pl-fine">
            Hashes bind this local response; they are not signatures or legal
            verification.
          </p>
          <pre>{JSON.stringify(result.receipt.payload, null, 2)}</pre>
        </div>
      </details>

      <p className="live-timing pl-fine">
        This request: original {result.runtime.source_query_ms.toFixed(2)} ms ·
        compact {result.runtime.compact_query_ms.toFixed(2)} ms on preloaded
        arrays, network and UI excluded. Single-request timings, not the
        retained benchmark (<code>benchmark: {String(result.runtime.benchmark)}</code>).
      </p>
    </div>
  );
}
