export type Geometry = { type: string; coordinates: number[][][] };
export type Result = {
  selected_cell_count: number;
  in_coverage_cell_count: number;
  out_of_coverage_cell_count: number;
  valid_land_cell_count: number;
  unknown_cell_count: number;
  datamask_counts: Record<string, number>;
  canopy_histogram: number[] | null;
  lossyear_histogram: number[] | null;
  yearly_loss_counts: Record<string, number> | null;
  periods: Record<
    string,
    {
      mapped_loss_present: boolean | null;
      observed_loss_cell_count: number | null;
    }
  >;
  support: "complete" | "partial" | "none" | "unavailable";
  unknown_reasons: string[];
};
export type Cell = {
  type: string;
  geometry: Geometry;
  properties: {
    row: number;
    col: number;
    treecover2000: number | null;
    lossyear: number | null;
    datamask: number | null;
    valid_land: boolean;
    in_coverage: boolean;
    band_validity: boolean[];
    center: number[];
  };
};
export type Plot = {
  plot_id: string;
  geometry: Geometry;
  supplier: Record<string, string>;
  source_result: Result | null;
  compact_result: Result | null;
  comparison: {
    equal: boolean | null;
    differing_fields: string[];
    source_result_sha256: string | null;
    compact_result_sha256: string | null;
  } | null;
  receipt: unknown;
  evidence: { type: string; features: Cell[] } | null;
};
export type Demo = {
  content_sha256?: string;
  periods?: Record<string, { start_year: number; end_year: number }> | string[];
  benchmark_status?: { state: string; [key: string]: unknown };
  schema_version: string;
  query_version: string;
  dataset: Record<string, unknown>;
  plots: Plot[];
  summary: unknown;
  benchmark: unknown;
  limitations: string[];
};
