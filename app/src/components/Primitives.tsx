import { useEffect, useId, useRef, useState } from "react";
import type * as React from "react";

export type IconName =
  | "arrow" | "arrow-left" | "search" | "layers" | "proof" | "close" | "download"
  | "chevron" | "command" | "check" | "info" | "play" | "pause" | "target"
  | "map" | "grid" | "bolt" | "question" | "alert" | "note" | "expand";

const iconPaths: Record<IconName, React.ReactNode> = {
  arrow: <path d="M4 12h15M13 5l7 7-7 7" />,
  "arrow-left": <path d="M20 12H5M11 5l-7 7 7 7" />,
  search: <><circle cx="10.5" cy="10.5" r="6.5" /><path d="m16 16 5 5" /></>,
  layers: <path d="m12 3 10 5-10 5L2 8l10-5Zm-9 9 9 4.5 9-4.5M3 16l9 4.5 9-4.5" />,
  proof: <path d="M14 3H5v18h14V8l-5-5ZM14 3v5h5M8 12h8m-8 4h5" />,
  close: <path d="m6 6 12 12M6 18 18 6" />,
  download: <path d="M12 3v12m-5-5 5 5 5-5M4 16v5h16v-5" />,
  chevron: <path d="m9 5 7 7-7 7" />,
  command: <><path d="M8 8h8v8H8z" /><path d="M8 8H5a3 3 0 1 1 3-3v3Zm8 0V5a3 3 0 1 1 3 3h-3Zm0 8h3a3 3 0 1 1-3 3v-3Zm-8 0v3a3 3 0 1 1-3-3h3Z" /></>,
  check: <path d="m4 12 5 5L20 6" />,
  info: <><circle cx="12" cy="12" r="9" /><path d="M12 11v6" /><circle cx="12" cy="7.5" r=".75" fill="currentColor" stroke="none" /></>,
  play: <path d="M7 4.5v15l12-7.5-12-7.5Z" />,
  pause: <path d="M8 5v14M16 5v14" />,
  target: <><circle cx="12" cy="12" r="8" /><circle cx="12" cy="12" r="2" /><path d="M12 2v3M12 19v3M2 12h3M19 12h3" /></>,
  map: <path d="m3 6 6-3 6 3 6-3v15l-6 3-6-3-6 3V6Zm6-3v15m6-12v15" />,
  grid: <path d="M4 4h16v16H4zM4 9.3h16M4 14.6h16M9.3 4v16M14.6 4v16" />,
  bolt: <path d="M13 2 4 14h7l-1 8 9-12h-7l1-8Z" />,
  question: <><circle cx="12" cy="12" r="9" /><path d="M9.5 9.2a2.6 2.6 0 1 1 3.6 2.4c-.7.3-1.1.9-1.1 1.6v.6" /><circle cx="12" cy="16.9" r=".8" fill="currentColor" stroke="none" /></>,
  alert: <><path d="M12 3 2 20h20L12 3Z" /><path d="M12 10v4.5" /><circle cx="12" cy="17.2" r=".8" fill="currentColor" stroke="none" /></>,
  note: <path d="M5 4h14v11l-5 5H5V4Zm9 16v-5h5M8 9h8M8 12.5h5" />,
  expand: <path d="M4 9V4h5M20 9V4h-5M4 15v5h5M20 15v5h-5" />,
};

/** Decorative icon. Give the containing control an accessible text label. */
export function Icon({ name, size = 18 }: { name: IconName; size?: number }) {
  return (
    <svg className="pl-icon" width={size} height={size} viewBox="0 0 24 24" fill="none"
      stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round"
      aria-hidden="true" focusable="false">
      {iconPaths[name]}
    </svg>
  );
}

export type Tone = "neutral" | "declared" | "loss" | "forest" | "proof" | "review" | "error" | "unknown";

/** Always include meaningful text; tone alone never communicates a finding. */
export function Chip({ children, tone = "neutral", title }: { children: React.ReactNode; tone?: Tone; title?: string }) {
  return <span className={`pl-chip${tone === "neutral" ? "" : ` pl-chip--${tone}`}`} title={title}>{children}</span>;
}

/** Back-compat for components not yet migrated. */
export function Pill({ children, tone = "neutral" }: { children: React.ReactNode; tone?: "neutral" | "accent" | "warning" | "positive" }) {
  const map: Record<string, Tone> = { neutral: "neutral", accent: "proof", warning: "review", positive: "proof" };
  return <Chip tone={map[tone]}>{children}</Chip>;
}

/**
 * Semantic glyph: ◆ declared, ■ mapped loss, ▲ forest, ▨ unknown, ? review.
 * `hollow` = the field is known and negative (e.g. declared "no indication").
 * Decorative unless `label` is given.
 */
export function Glyph({ kind, hollow = false, label }: { kind: "declared" | "loss" | "forest" | "unknown" | "review"; hollow?: boolean; label?: string }) {
  if (kind === "review")
    return <span className="pl-glyph pl-glyph--review" role={label ? "img" : undefined} aria-label={label} aria-hidden={label ? undefined : true}>?</span>;
  return <span className={`pl-glyph pl-glyph--${kind}${hollow ? " is-hollow" : ""}`} role={label ? "img" : undefined} aria-label={label} aria-hidden={label ? undefined : true} />;
}

export function Stat({ value, label, tone, size, unit }: { value: React.ReactNode; label: React.ReactNode; tone?: "proof" | "loss" | "declared" | "forest"; size?: "lg" | "xl"; unit?: string }) {
  return (
    <div className={`pl-stat${tone ? ` pl-stat--${tone}` : ""}${size ? ` pl-stat--${size}` : ""}`}>
      <span className="pl-stat__value">{value}{unit && <small> {unit}</small>}</span>
      <span className="pl-stat__label">{label}</span>
    </div>
  );
}

/** ⓘ explanation popover. Keyboard: Enter/Space toggles, Escape closes and restores focus. */
export function Info({ label, children }: { label: string; children: React.ReactNode }) {
  const [open, setOpen] = useState(false);
  const id = useId();
  const root = useRef<HTMLSpanElement>(null);
  const button = useRef<HTMLButtonElement>(null);
  useEffect(() => {
    if (!open) return;
    const close = (e: MouseEvent | KeyboardEvent) => {
      if (e instanceof KeyboardEvent) {
        if (e.key === "Escape") { e.stopPropagation(); setOpen(false); button.current?.focus(); }
        return;
      }
      if (!root.current?.contains(e.target as Node)) setOpen(false);
    };
    document.addEventListener("mousedown", close);
    document.addEventListener("keydown", close, true);
    return () => { document.removeEventListener("mousedown", close); document.removeEventListener("keydown", close, true); };
  }, [open]);
  return (
    <span className="pl-info" ref={root}>
      <button ref={button} type="button" aria-label={label} aria-expanded={open} aria-controls={id} onClick={() => setOpen(!open)}>
        <Icon name="info" size={14} />
      </button>
      {open && <span className="pl-info__panel" id={id} role="note">{children}</span>}
    </span>
  );
}

export function EmptyState({ title, detail }: { title: string; detail: string }) {
  return (
    <section className="pl-empty-state" aria-label={title}>
      <span className="pl-empty-state__mark"><Icon name="search" size={22} /></span>
      <h2 className="pl-empty-state__title">{title}</h2>
      <p className="pl-empty-state__detail">{detail}</p>
    </section>
  );
}
