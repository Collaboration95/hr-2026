import "../styles/map.css";
import { useCallback, useEffect, useRef, useState } from "react";
import type * as React from "react";
import { Icon } from "../components/Primitives";

export type TimeScrubberProps = {
  year: number;
  onYear: (y: number) => void;
  /** 25 entries for 2001..2025; a null entry means unknown; null means unavailable. */
  counts: (number | null)[] | null;
  mode: "plot" | "region";
  label: string;
  /** Plot mode: activate the proof for the selected year. */
  onProof?: () => void;
};

const FIRST = 2001;
const LAST = 2025;
const YEARS = Array.from({ length: LAST - FIRST + 1 }, (_, i) => FIRST + i);
const STEP_MS = 350;
const fmt = new Intl.NumberFormat("en-US");

/** Window and cut-off positions as fractions of the 25-column track. */
const WINDOW_START = (2021 - FIRST) / YEARS.length;
const WINDOW_END = (2024 - FIRST) / YEARS.length;

function reducedMotion() {
  return typeof window !== "undefined" && !!window.matchMedia?.("(prefers-reduced-motion: reduce)").matches;
}

function columnName(mode: TimeScrubberProps["mode"], y: number, count: number | null | undefined, loaded: boolean): string {
  if (mode === "region")
    return typeof count === "number" ? `Year ${y}, ${fmt.format(count)} loss pixels in region display raster` : `Year ${y}, ${loaded ? "loss pixel count unknown" : "region display raster not loaded"}`;
  return typeof count === "number" ? `Year ${y}, ${fmt.format(count)} observed loss cells` : `Year ${y}, observed loss count unknown`;
}

export default function TimeScrubber({ year, onYear, counts, mode, label, onProof }: TimeScrubberProps) {
  const [playing, setPlaying] = useState(false);
  const expected = useRef<number | null>(null);
  const scroller = useRef<HTMLDivElement>(null);
  const track = useRef<HTMLDivElement>(null);

  const entries = YEARS.map((_, i) => (counts && i < counts.length ? counts[i] : null));
  const known = entries.filter((v): v is number => typeof v === "number");
  const max = Math.max(1, ...known);
  const idx = year - FIRST;
  const current = entries[idx];

  /** Any manual year choice (click, key, or an outside change) cancels playback. */
  const choose = useCallback((y: number) => {
    setPlaying(false);
    expected.current = null;
    onYear(y);
  }, [onYear]);

  // Playback: step once per STEP_MS, stop at 2025, cancel if the year changes for any other reason.
  // `expected` is the year we asked the parent for; it may arrive a tick later (hash routing).
  const onYearRef = useRef(onYear);
  onYearRef.current = onYear;
  const seen = useRef(year);
  useEffect(() => {
    const changed = seen.current !== year;
    seen.current = year;
    if (!playing) return;
    if (expected.current !== null) {
      if (year !== expected.current) {
        if (changed) {
          expected.current = null;
          setPlaying(false);
        }
        return; // still waiting for our own change to arrive
      }
      expected.current = null;
    } else if (changed) {
      setPlaying(false);
      return;
    }
    if (year >= LAST) {
      setPlaying(false);
      return;
    }
    const id = window.setTimeout(() => {
      expected.current = year + 1;
      onYearRef.current(year + 1);
    }, STEP_MS);
    return () => window.clearTimeout(id);
  }, [playing, year]);

  const togglePlay = () => {
    if (playing) {
      expected.current = null;
      setPlaying(false);
      return;
    }
    const start = year >= LAST ? FIRST : year;
    expected.current = start;
    if (start !== year) onYear(start);
    setPlaying(true);
  };

  // Keep the selected column in view (narrow widths scroll horizontally).
  useEffect(() => {
    const box = scroller.current;
    const col = box?.querySelector<HTMLElement>('[aria-pressed="true"]');
    if (!box || !col || box.scrollWidth <= box.clientWidth + 1) return;
    box.scrollTo({ left: col.offsetLeft - box.clientWidth / 2 + col.offsetWidth / 2, behavior: reducedMotion() ? "auto" : "smooth" });
  }, [year]);

  const onKeyDown = (e: React.KeyboardEvent<HTMLDivElement>) => {
    const next =
      e.key === "ArrowLeft" ? Math.max(FIRST, year - 1)
      : e.key === "ArrowRight" ? Math.min(LAST, year + 1)
      : e.key === "Home" ? FIRST
      : e.key === "End" ? LAST
      : null;
    if (next === null) return;
    e.preventDefault();
    if (next !== year) choose(next);
    track.current?.querySelector<HTMLElement>(`[data-year="${next}"]`)?.focus();
  };

  const loaded = counts !== null;
  const unit = mode === "region" ? "loss pixels" : "loss cells";
  const countText =
    typeof current === "number" ? <><strong className="pl-num">{fmt.format(current)}</strong> {unit}</>
    : !loaded ? <span className="pl-scrub__unknown">{mode === "region" ? "not loaded" : "unavailable"}</span>
    : <span className="pl-scrub__unknown">unknown</span>;

  return (
    <section className="pl-scrub" aria-label="Year scrubber" data-mode={mode}>
      <div className="pl-scrub__layout">
      <div className="pl-scrub__head">
        <button
          type="button"
          className="pl-btn pl-btn--icon pl-scrub__play"
          aria-label={playing ? "Pause years" : "Play years"}
          aria-pressed={playing}
          onClick={togglePlay}
        >
          <Icon name={playing ? "pause" : "play"} size={16} />
        </button>
        <div className="pl-scrub__info">
          <p className="pl-scrub__label" title={label}>{label}</p>
          <div className="pl-scrub__now">
            <span className="pl-scrub__year pl-num">{year}</span>
            <span className="pl-scrub__count">{countText}</span>
          </div>
          {mode === "plot" && onProof && (
            <button type="button" className="pl-btn pl-btn--ghost pl-btn--sm pl-scrub__proof" onClick={onProof}>
              Open proof for {year}
            </button>
          )}
        </div>
      </div>

      <div className="pl-scrub__chart" ref={scroller}>
        <div className="pl-scrub__track" ref={track} role="group" aria-label={`Years ${FIRST} to ${LAST}`} onKeyDown={onKeyDown}>
          <div className="pl-scrub__marks">
            <span className="pl-scrub__window-label">Supplier analysis 2021–23</span>
            <span className="pl-scrub__cutoff-label" style={{ right: `${(1 - WINDOW_START) * 100}%` }}>EUDR cut-off · 31 Dec 2020</span>
            <span className="pl-scrub__bracket" aria-hidden="true" style={{ left: `${WINDOW_START * 100}%`, width: `${(WINDOW_END - WINDOW_START) * 100}%` }} />
          </div>
          <span className="pl-scrub__cutoff" aria-hidden="true" style={{ left: `${WINDOW_START * 100}%` }} />
          <div className="pl-scrub__cols">
            {YEARS.map((y, i) => {
              const v = entries[i];
              const cls = typeof v !== "number" ? "is-unknown" : v === 0 ? "is-zero" : "";
              const state = y === year ? "is-selected" : y < year ? "is-past" : "is-future";
              // sqrt scale to the largest count; a positive count is never shorter than 3px.
              const h = typeof v === "number" && v > 0 ? `max(3px, calc(${Math.sqrt(v / max).toFixed(4)} * var(--pl-scrub-bar-h)))` : undefined;
              return (
                <button
                  key={y}
                  type="button"
                  className={`pl-scrub__col ${state}`}
                  data-year={y}
                  aria-pressed={y === year}
                  aria-label={columnName(mode, y, v, loaded)}
                  tabIndex={y === year || (y === FIRST && (idx < 0 || idx >= YEARS.length)) ? 0 : -1}
                  onClick={() => choose(y)}
                >
                  <span className={`pl-scrub__bar ${cls}`} style={h ? { height: h } : undefined} aria-hidden="true" />
                  <span className="pl-scrub__yr" aria-hidden="true">
                    <span className="pl-scrub__yr-short">&rsquo;{String(y).slice(2)}</span>
                    <span className="pl-scrub__yr-full">{y}</span>
                  </span>
                </button>
              );
            })}
          </div>
        </div>
      </div>
      </div>
    </section>
  );
}
