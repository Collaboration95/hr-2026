/* Constants for the technical brief. Every figure is copied from a repository file; the source is named beside each block.
   GitHub blob links use the Main branch. */
window.BR = (() => {
  const GH = 'https://github.com/Collaboration95/hr-2026';
  const blob = p => `${GH}/blob/Main/${p}`;

  /* artifacts/decision/stores.json : code_histogram per level (index = code 0..19) */
  const hist = {
    screen:   [0, 1314, 542696, 15423, 11026, 16747, 22307, 14368, 118071, 64, 50, 73, 85, 69, 2222, 32, 47, 57, 30, 51],
    decision: [0, 1314, 622567, 0, 0, 0, 0, 0, 118071, 64, 50, 73, 85, 69, 2222, 32, 47, 57, 30, 51],
  };

  /* artifacts/decision/stores.json : baselines, store, candidates[split].sections */
  const bytes = {
    originals: [
      { id: 'treecover2000', label: 'Hansen treecover2000', b: 414142, file: 'hansen_treecover2000_sample.tif' },
      { id: 'lossyear', label: 'Hansen lossyear', b: 159863, file: 'hansen_lossyear_sample.tif' },
      { id: 'datamask', label: 'Hansen datamask', b: 2994, file: 'hansen_datamask_sample.tif' },
      { id: 'jrc', label: 'JRC 2020 forest', b: 46238, file: 'JRC_GFC2020_V4_N10_E90_company-bbox.tif' },
    ],
    total: 623237, contractInputs: 209095, retainedL0: 535012,
    screenStore: 38513, decisionStore: 6146, decisionPayload: 5451, decisionHeader: 675, prefix: 20,
    bestGeotiffDecision: 8532, bestGeotiffScreen: 45859,
    zstd19Screen: 45745, zstd19Decision: 9874,           /* layer-analysis-v1.json : yardstick */
    zstd19Lossyear: 133810, zstd19Loss2001_2020: 107371, zstd19Loss2021_2025: 40688,
    sections: { flags: 1, unknown: 1, water: 449, forest: 4453, unknown_forest: 36, events: 366, years: 145 },
    registry: 4096, table: 20650,
    decisionFileSha256: 'bf6368445b609dc335ee6ad4422fc927e391ad48da722c3f613a9b5b4526b839',   /* stores.json */
    tableContentSha256: '0b94ed4eee0c58e035dd66798a1cda64b588fa5e029da7b8420b0490f5908701',    /* artifacts/decision/table.json content_sha256 */
  };

  /* artifacts/decision/scale-v1.json : one real tile (storage only) */
  const tile = [
    { label: 'Original files (LZW GeoTIFF)', b: 421910035, kind: 'orig' },
    { label: 'Lossless zstd-19 yardstick', b: 148892092, kind: 'ctrl' },
    { label: 'L1 screening', b: 13647704, kind: 'l1' },
    { label: 'L2 decision', b: 8242423, kind: 'l2' },
  ];

  /* artifacts/decision/benchmark-v1.json : headline_table (Phase 4). hot = 17-plot batch, ms; cold = process-cold, ms;
     e2e = fresh process end to end, ms; rss = peak MB. perPlot = hot / 17 in microseconds, as the notes quote it. */
  const paths = [
    { id: 'P0', short: 'v1 query',   name: 'Original layers, retained v1 query', grp: 'base', hot: 1.437,  cold: 11.11, e2e: 114.5, rss: 74.8, perPlot: 84.5,  x: '1×' },
    { id: 'P1', short: 'original, EUDR Q',   name: 'Original layers, same EUDR question', grp: 'base', hot: 1.880,  cold: 18.95, e2e: 124.9, rss: 97.1, perPlot: 110.6, x: '' },
    { id: 'P3', short: 'decision store',   name: 'Decision store, general selection', grp: 'new',  hot: 1.175,  cold: 2.68,  e2e: 57.2,  rss: 40.2, perPlot: 69.1,  x: '' },
    { id: 'P4', short: 'fast selection',   name: 'Decision store, exact fast selection', grp: 'new',  hot: 0.275,  cold: 1.55,  e2e: 56.9,  rss: 39.9, perPlot: 16.15, x: '5.2×' },
    { id: 'P4B', short: 'batch evaluator',  name: 'Decision store, batch evaluator', grp: 'new',  hot: 0.222,  cold: 1.53,  e2e: 56.9,  rss: 40.3, perPlot: 13.04, x: '6.5×', note: 'one pass over a batch' },
    { id: 'P5', short: 'registered index',   xc: '8.7×', name: 'Registered-plot index', grp: 'reg',  hot: 0.0323, cold: 1.28,  e2e: 50.0,  rss: 36.7, perPlot: 1.90,  x: '44×' },
    { id: 'P5L', short: 'index, numpy-free',  xc: '10.9×', xe: '4.6×', name: 'Registered-plot index, numpy-free', grp: 'reg',  hot: 0.0173, cold: 1.02,  e2e: 24.9,  rss: 22.9, perPlot: 1.02,  x: '83×' },
    { id: 'P6', short: 'answer table',   xc: '46×', xe: '5.3×', name: 'Registered-plot answer table', grp: 'reg',  hot: 0.0035, cold: 0.244, e2e: 21.6,  rss: 20.7, perPlot: 0.206, x: '410×' },
  ];

  /* artifacts/decision/benchmark-v1.json speedups at commits e7f5264, 3afeb02, 8808f55, 4ca3628, 35fd625. null = path did not exist yet. */
  const phases = ['Decision layers', 'Phase 1', 'Phase 2', 'Phase 3', 'Phase 4'];
  const phaseSeries = {
    newb: [
      { id: 'P4',  label: 'New boundary, one at a time (P4)', v: [2.2, 3.0, 5.0, 5.3, 5.2] },
      { id: 'P4B', label: 'Batch of 500 new polygons (P4B)', v: [null, null, 14, 15, 15.8] },
    ],
    reg: [
      { id: 'P5',  label: 'Registered index (P5d)', v: [24, 31, 33, 44, 44] },
      { id: 'P5L', label: 'Numpy-free re-check (P5Ld)', v: [null, null, 44, 65, 83] },
    ],
  };
  const phaseNotes = [
    ['Decision layers', 'Keep only what the decision reads; registered-plot index and answer table.'],
    ['Phase 1', 'Decode on packed bit-planes, quicker reducer, quicker polygon selection.'],
    ['Phase 2', 'Pure-Python scan for small polygons, batch evaluator, numpy-free re-check.'],
    ['Phase 3', 'Leaner shared reducer; no hidden import in the batch path.'],
    ['Phase 4', 'Trusted-integer reducer entry, scan-selection rule, research pass.'],
  ];

  return { GH, blob, hist, bytes, tile, paths, phases, phaseSeries, phaseNotes };
})();
