import type { Cell } from "./types";
/** Availability is independent of a stored raw zero or a non-land mask. */
export function availableBand(cell: Cell, band: 0 | 1 | 2): number | null {
  const value = [
    cell.properties.treecover2000,
    cell.properties.lossyear,
    cell.properties.datamask,
  ][band];
  return cell.properties.in_coverage === false ||
    cell.properties.band_validity?.[band] === false ||
    typeof value !== "number" ||
    !Number.isFinite(value)
    ? null
    : value;
}
export function canopyLabel(cell: Cell): string {
  const v = availableBand(cell, 0);
  return v == null
    ? "Unavailable"
    : `${v}%${cell.properties.valid_land ? "" : " · raw, excluded"}`;
}
export function lossLabel(cell: Cell): string {
  const v = availableBand(cell, 1);
  return v == null
    ? "Unavailable"
    : !cell.properties.valid_land
      ? `Raw code ${v} · excluded`
      : v === 0
        ? "No mapped event"
        : String(2000 + v);
}
export function maskLabel(cell: Cell): string {
  const v = availableBand(cell, 2);
  return v == null
    ? "Unavailable"
    : `${v} · ${v === 0 ? "No data" : v === 1 ? "Mapped land" : v === 2 ? "Permanent water" : "Unsupported code"}`;
}
export function isYearEvent(cell: Cell, year: number): boolean {
  return (
    cell.properties.valid_land === true &&
    availableBand(cell, 1) === year - 2000
  );
}
