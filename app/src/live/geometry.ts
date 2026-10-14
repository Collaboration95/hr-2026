import type { Geometry } from "../types";

function positions(value: unknown): number[][] {
  if (!Array.isArray(value)) return [];
  if (typeof value[0] === "number") return [value as number[]];
  return value.flatMap(positions);
}

/** [west, south, east, north] of every position in a geometry (display and prefill only). */
export function extent(g: Geometry) {
  const p = positions(g.coordinates);
  return [
    Math.min(...p.map((v) => v[0])),
    Math.min(...p.map((v) => v[1])),
    Math.max(...p.map((v) => v[0])),
    Math.max(...p.map((v) => v[1])),
  ];
}
