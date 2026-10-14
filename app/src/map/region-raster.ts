// STUB (owner: Map agent). Replace with the real display-raster loader. See design/DESIGN.md §8.
export type RegionRaster = {
  status: "loading" | "ready" | "unavailable";
  error?: string;
  /** Index 0 = 2001 … 24 = 2025; land pixels with loss in that year (display statistic). */
  yearlyLossPixels: number[] | null;
};
export function useRegionRaster(): RegionRaster {
  return { status: "unavailable", error: "Not implemented yet", yearlyLossPixels: null };
}
