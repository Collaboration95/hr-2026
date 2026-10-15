import type { Plot } from "./types";
/** Structural equality ignores JSON object key order and never coerces null/false/zero. */
export function sameValue(a: unknown, b: unknown): boolean {
  if (Object.is(a, b)) return true;
  if (
    a === null ||
    b === null ||
    typeof a !== "object" ||
    typeof b !== "object"
  )
    return false;
  if (Array.isArray(a) || Array.isArray(b))
    return (
      Array.isArray(a) &&
      Array.isArray(b) &&
      a.length === b.length &&
      a.every((v, i) => sameValue(v, b[i]))
    );
  const av = a as Record<string, unknown>,
    bv = b as Record<string, unknown>;
  const keys = Object.keys(av);
  return (
    keys.length === Object.keys(bv).length &&
    keys.every((k) => Object.hasOwn(bv, k) && sameValue(av[k], bv[k]))
  );
}
export function comparisonState(
  plot: Plot,
): "match" | "mismatch" | "unavailable" {
  if (!plot.source_result || !plot.compact_result) return "unavailable";
  if (
    !sameValue(plot.source_result, plot.compact_result) ||
    plot.comparison?.equal === false
  )
    return "mismatch";
  return plot.comparison?.equal === true ? "match" : "unavailable";
}
