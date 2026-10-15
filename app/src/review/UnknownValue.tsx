import type { Plot } from "../types";

/** Human-readable reason a mapped value is unknown. Never implies zero. */
export function unknownReason(plot: Plot): string {
  const r = plot.source_result;
  if (!r) return "mapped result not computed";
  return r.unknown_reasons?.length ? r.unknown_reasons.join(", ").replaceAll("_", " ") : "not available in this export";
}

/** Grey, hatched "unknown" value with its reason. Use instead of 0, "-" or blank. */
export function UnknownValue({ reason, label = "Unknown" }: { reason?: string; label?: string }) {
  return (
    <span className="pl-unknown" title={reason ? `${label}: ${reason}` : label}>
      <span className="pl-unknown__tag pl-hatch">{label}</span>
      {reason && <small className="pl-unknown__why">{reason}</small>}
    </span>
  );
}

export const fmtCount = (n: number) => n.toLocaleString("en-US");
