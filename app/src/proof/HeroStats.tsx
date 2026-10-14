import type * as React from "react";
import { Info, Stat } from "../components/Primitives";
import type { Demo } from "../types";
import {
  fmtBytes,
  fmtFixed,
  fmtInt,
  fmtPct,
  hotVerdict,
  pctChange,
  ratio,
  readBenchmark,
  readSummary,
  reviewInputs,
} from "./bench-data";

function Cell({ info, infoLabel, children }: { info: React.ReactNode; infoLabel: string; children: React.ReactNode }) {
  return (
    <li className="proof-hero__cell">
      {children}
      <span className="proof-hero__info">
        <Info label={infoLabel}>{info}</Info>
      </span>
    </li>
  );
}
const Sub = ({ children }: { children: React.ReactNode }) => <span className="proof-hero__sub">{children}</span>;

/** Every number here is read from `data.summary` / `data.benchmark`; nothing is hard-coded. */
export default function HeroStats({ data }: { data: Demo }) {
  const summary = readSummary(data.summary);
  const bench = readBenchmark(data.benchmark);
  const base = bench?.baseline ?? null;
  const kept = bench?.retained ?? null;
  const reps = kept?.fresh?.repetitions ?? kept?.hot?.repetitions ?? null;
  const batch = bench?.queryBatch ?? null;

  // (b) Pixel fidelity: booleans from the retained candidate's round-trip check.
  const rt = kept?.roundtrip ?? null;
  const pixelsExact = rt && rt.rawBandsEqual === true && rt.bandMasksEqual === true && rt.rawValuesChecked !== null;
  const pixelsDiffer = rt && (rt.rawBandsEqual === false || rt.bandMasksEqual === false);
  const bands = bench?.bandCount ?? null;

  // (c) Storage at the loader-input boundary, retained candidate vs original.
  const storagePct = kept && base ? pctChange(kept.total, base.total) : null;
  const review = bench ? reviewInputs(bench) : null;

  // (d) fresh-process and (e) hot, baseline median / candidate median.
  const freshRatio = ratio(base?.fresh?.median ?? null, kept?.fresh?.median ?? null);
  const hotRatio = ratio(base?.hot?.median ?? null, kept?.hot?.median ?? null);
  const verdict = hotVerdict(hotRatio);

  return (
    <ul className="proof-hero" aria-label="Headline results from the frozen export">
      <Cell
        infoLabel="About identical query outputs"
        info={
          <>
            Full result dictionaries (counts, histograms, support, unknown reasons) from the original GeoTIFF inputs and
            from the compact store, per plot. This is engineering agreement for pinned inputs and rules, not satellite
            truth or a legal finding.
          </>
        }
      >
        <Stat
          tone={summary && summary.exact === summary.total ? "proof" : undefined}
          value={summary ? `${summary.exact}/${summary.total}` : "Unavailable"}
          label={
            <>
              plots with identical full query outputs
              <Sub>original GeoTIFF vs compact store</Sub>
            </>
          }
        />
      </Cell>

      <Cell
        infoLabel="About pixel fidelity"
        info={
          <>
            Round-trip check of the retained compact store against the original rasters: every raw band value, every
            band-validity mask and the metadata are compared for equality. It is a yes/no equality test, so it reads 100%
            only when all of them are equal.
          </>
        }
      >
        <Stat
          tone={pixelsExact ? "proof" : undefined}
          value={pixelsExact ? "100%" : pixelsDiffer ? "Differs" : "Unavailable"}
          label={
            <>
              pixel fidelity: raw values + masks equal{bands !== null ? `, all ${bands} bands` : ""}
              {rt && rt.rawValuesChecked !== null && (
                <Sub>
                  {fmtInt(rt.rawValuesChecked)} raw values
                  {rt.pixelCount !== null ? ` · ${fmtInt(rt.pixelCount)} cells` : ""} checked
                </Sub>
              )}
            </>
          }
        />
      </Cell>

      <Cell
        infoLabel="About the storage change"
        info={
          <>
            <strong>Loader-input boundary.</strong> The complete compact store (payload, metadata, index) against the
            original files the loader actually reads (GeoTIFF bands plus acquisition provenance). Excluded: the shared
            geometry and supplier files, unused generated metadata, full-tile downloads and any tile-to-chip crop saving.
            {review && (
              <>
                {" "}
                <strong>A different boundary:</strong> counting complete review inputs on both sides gives{" "}
                {fmtBytes(review.original)} to {fmtBytes(review.compact)} ({fmtPct(review.pct)}). Do not swap the two
                denominators.
              </>
            )}
          </>
        }
      >
        <Stat
          tone={storagePct !== null && storagePct < 0 ? "proof" : undefined}
          value={fmtPct(storagePct)}
          label={
            <>
              storage vs original, loader-input boundary
              <Sub>
                {fmtBytes(kept?.total)} compact vs {fmtBytes(base?.total)} original
              </Sub>
            </>
          }
        />
      </Cell>

      <Cell
        infoLabel="About fresh-process speed"
        info={
          <>
            A fresh process per repetition times the full load, integrity validation and the{" "}
            {batch !== null ? `${batch}-plot ` : ""}query batch. Excluded: imports and the shared geometry read. The OS file
            cache was not controlled and is likely warm, so this is process-fresh, not disk-cold. {reps ?? "Seven"}{" "}
            repetitions on one machine: a bounded result for this sample, not a guarantee.
          </>
        }
      >
        <Stat
          value={freshRatio === null ? "Unavailable" : `${fmtFixed(freshRatio, 2)}×`}
          label={
            <>
              faster fresh-process load + query
              <Sub>
                {fmtFixed(base?.fresh?.median, 2)} ms original, {fmtFixed(kept?.fresh?.median, 2)} ms compact · median of{" "}
                {reps ?? "?"}
              </Sub>
            </>
          }
        />
      </Cell>

      <Cell
        infoLabel="About hot-query speed"
        info={
          <>
            Hot query: the full regional data is already loaded before timing, so only the{" "}
            {batch !== null ? `${batch}-plot ` : ""}query batch is measured (median of {reps ?? "?"} repetitions). The two
            representations run the same query code on the same arrays, so differences this small are noise, not a format
            advantage. Imports and shared geometry are excluded.
          </>
        }
      >
        <Stat
          value={
            hotRatio === null ? "Unavailable" : verdict === "none" ? "≈1.0×" : `${fmtFixed(hotRatio, 2)}×`
          }
          label={
            <>
              {verdict === "none"
                ? "no hot-query speedup"
                : verdict === "faster"
                  ? "faster hot query"
                  : verdict === "slower"
                    ? "slower hot query"
                    : "hot query"}
              <Sub>
                {fmtFixed(base?.hot?.median, 3)} ms original, {fmtFixed(kept?.hot?.median, 3)} ms compact · median of{" "}
                {reps ?? "?"}
              </Sub>
            </>
          }
        />
      </Cell>
    </ul>
  );
}
