/**
 * Shared, strictly typed facts about a plot used by the rail, inspector and cohort.
 * Owner: design owner. Read-only for implementation agents (import, do not edit).
 *
 * "Declared" = the supplier's own field, verbatim. "Mapped" = the validated
 * Hansen export under hansen-centers.v1. Neither is a verdict; a difference is
 * a question for a human, never a finding about the supplier.
 */
import type { Plot } from "../types";

/** The supplier's named analysis window ("Hansen Tree Cover Loss 2021-2023"). */
export const ANALYSIS_PERIOD = "2021-2023";
export const RECENT_PERIOD = "2024-2025";
export const YEARS = Array.from({ length: 25 }, (_, i) => 2001 + i);

const INDICATION = "b. Indication of deforestation";
const NO_INDICATION = /^a\. No Indication of deforestation$/i;

/** true = declared indication, false = declared none, null = missing/unrecognised. */
export function declaredIndication(plot: Plot): boolean | null {
  const v = plot.supplier?.c2_deforestation_spatial_analysis_result;
  if (typeof v !== "string") return null;
  if (v === INDICATION) return true;
  if (NO_INDICATION.test(v.trim())) return false;
  return null;
}

/** Mapped loss present in a period: boolean only when the export says so; otherwise null (unknown). */
export function mappedLoss(plot: Plot, period = ANALYSIS_PERIOD): boolean | null {
  const v = plot.source_result?.periods?.[period]?.mapped_loss_present;
  return typeof v === "boolean" ? v : null;
}

/** Observed loss cells in a period, or null when unavailable. Never coerces unknown to 0. */
export function periodCount(plot: Plot, period: string): number | null {
  const v = plot.source_result?.periods?.[period]?.observed_loss_cell_count;
  return typeof v === "number" && Number.isFinite(v) ? v : null;
}

/** Observed loss cells for one year, or null when unavailable. */
export function yearCount(plot: Plot, year: number): number | null {
  const v = plot.source_result?.yearly_loss_counts?.[String(year)];
  return typeof v === "number" && Number.isFinite(v) ? v : null;
}

/** 25 entries (2001..2025) for the scrubber; null when the whole series is unavailable. */
export function yearSeries(plot: Plot): (number | null)[] | null {
  if (!plot.source_result?.yearly_loss_counts) return null;
  return YEARS.map((y) => yearCount(plot, y));
}

/** Years within [start, end] with a positive observed count. */
export function lossYears(plot: Plot, start: number, end: number): number[] {
  return YEARS.filter((y) => y >= start && y <= end && (yearCount(plot, y) ?? 0) > 0);
}

/** true/false only when both accounts are known for the supplier's window. */
export function differs(plot: Plot): boolean | null {
  const d = declaredIndication(plot), m = mappedLoss(plot);
  return d === null || m === null ? null : d !== m;
}

/** Strip the CSV option letter ("b. ") for display. Keep the exact string for receipts/titles. */
export const cleanLabel = (s: string | undefined | null): string =>
  typeof s === "string" && s.trim() ? s.replace(/^[a-z]\.\s+/i, "") : "Not supplied";

/** Evidence reference key, or null when the supplier wrote "Not Applicable"/nothing. */
export function evidenceReference(plot: Plot): string | null {
  const v = plot.supplier?.c4_reference_or_link_if_applicable;
  return typeof v === "string" && v.trim() && !/^not applicable$/i.test(v.trim()) ? v : null;
}

export type ReviewQuestion = { kind: "question" | "agree" | "unknown"; text: string };

/** Copy templates from design/DESIGN.md §6. */
export function reviewQuestion(plot: Plot): ReviewQuestion {
  const d = declaredIndication(plot), m = mappedLoss(plot), ref = evidenceReference(plot);
  const reasons = plot.source_result?.unknown_reasons?.length
    ? plot.source_result.unknown_reasons.join(", ").replaceAll("_", " ")
    : "the mapped result is not available";
  if (m === null) return { kind: "unknown", text: `Mapped result unknown: ${reasons}. No conclusion either way.` };
  if (d === null) return { kind: "unknown", text: "The supplier's analysis result is missing or unrecognised, so the two accounts cannot be compared." };
  const years = lossYears(plot, 2021, 2023);
  if (d && !m)
    return { kind: "question", text: `The supplier reports an indication in 2021–23; the current layer shows no loss under the centre rule. Which layer version and inclusion rule produced it${ref ? `, and what is in ${ref}` : ""}?` };
  if (!d && m)
    return { kind: "question", text: `The layer shows loss in ${years.length ? years.join(", ") : "2021–23"} that the declaration does not mention. Was it assessed, and was it forest or plantation rotation? Compare the JRC 2020 forest layer.` };
  if (d && m)
    return { kind: "question", text: `Both accounts report loss in 2021–23.${ref ? ` Inspect ${ref} for the mitigation evidence.` : " No evidence reference was supplied."}` };
  return { kind: "agree", text: "Declaration and map agree for 2021–23." };
}
