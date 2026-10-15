# Decision layers: results (15 Oct 2026)

**SystemEarth's slide title was "Keep the decision, not the data". This is that, measured.** We worked out which facts the EUDR screen actually reads, reduced each map cell to those facts, and proved that the reduced layer gives the same answer as the original layers for every cell in the region, not just the 17 plots.

Plan and feasibility: [decision-layer-plan.md](decision-layer-plan.md). Semantics: [`engine/decision.py`](../../engine/decision.py). Evidence: [`artifacts/decision/`](../../artifacts/decision/). Independent validation: [validation/decision/report.md](../../validation/decision/report.md).

## The questions and what each needs

| Question | Needs | Doesn't need |
| --- | --- | --- |
| Q1. Was it forest on 31 Dec 2020? | JRC 2020 forest class, land/water/unknown | Canopy % in 2000 (Hansen `treecover2000`) |
| Q2. Has 2020 forest been lost since? | Q1 + Hansen loss year 2021–2025 | Loss years 2001–2020 |
| Q3. The supplier's own check: any Hansen loss in 2021–23? | Hansen loss year 2021–2025 on all land | Canopy %, older loss years |

`treecover2000` is 72% of the original Hansen bytes, and no question reads it. Loss years before the cut-off are most of what remains in `lossyear`. JRC is at about 9 m; the Hansen loss cell is about 28 m and nests exactly 3×3 JRC cells. [Layer analysis with byte attribution](decision-scale-notes.md#what-each-attribute-costs-and-who-needs-it-the-744732-cell-chip).

## Two derived layers, one code per cell

Each Hansen cell becomes one of 20 codes: unknown, water, or land × {2020 non-forest, 2020 forest, forest state unknown} × {no post-2020 loss, 2021, …, 2025}.

- **Screening layer (`eudr-screen.v1`)** answers Q1–Q3.
- **Decision layer (`eudr-decision.v1`)** answers Q1–Q2. It forgets the loss year on land that was not forest in 2020: the plantation rotation that the supplier's Hansen-only check trips over.

The lossless v1 store stays as the audit tier for rule changes.

## Same answers, proven for every cell

| Check | Result |
| --- | --- |
| Every cell: decoded store vs the original GeoTIFFs, via an independent float-affine path | **744,732 / 744,732** at both levels |
| The 17 supplied plots, every output field | **17 / 17** at both levels, across the store, registry and table paths |
| Fuzzed polygons: holes, multipolygons, edges through cell centres, chip edges, water | **9,829 / 9,829** (171 invalid shapes rejected identically by both paths) |
| Hansen 2021–25 counts and flags vs the retained v1 outputs | Equal |
| Negative controls: one flipped cell, a moved vertex, a flipped JRC bit | All detected |
| Independent validator (exact rational arithmetic, its own reducer) | Confirmed; 216,360 extra adversarial polygons for the fast selector, 0 mismatches |

Why "every cell" means "every plot": each output is a function only of the codes of the selected cells and the out-of-chip count. If every cell's code matches, every possible plot boundary in the region gets identical outputs under the shared centre rule.

Pixel fidelity "where relevant": 100% on every attribute the decision reads. Dropped attributes are listed, not called lossless.

## How much smaller

On the 34 × 17 km sample region:

| Representation | Bytes | vs 623,237 B original layers |
| --- | --- | --- |
| Original layers: Hansen 3 bands + JRC chip | 623,237 | baseline |
| L0 lossless store, retained v1 (Hansen only) | 535,012 | 14% smaller |
| L1 screening store | 38,513 | **93.8% smaller (16×)** |
| L2 decision store | **6,146** | **99.0% smaller (101×)** |
| Best standard GeoTIFF of the same decision codes | 8,532 | 98.6% smaller |

- **Most of the gain is the layer analysis, not the codec.** A plain GeoTIFF of the decision codes is already 98.6% smaller. Our structure-aware encoding (bit-planes and sparse loss events) adds the last 28%. We show both.
- **Against only the files the decision reads** (lossyear + datamask + JRC, 209,095 B), the decision store is 97.1% smaller.

On a whole real tile (Hansen 10N_090E + JRC N10_E90, 1.6 billion cells, every strip processed):

| Representation | Bytes | vs original files | vs a zstd-19 recompression of the originals |
| --- | --- | --- | --- |
| Original files | 421.9 MB | baseline | — |
| Lossless zstd-19 yardstick | 148.9 MB | 64.7% smaller | baseline |
| L1 screening | 13.6 MB | 96.8% smaller | 90.8% smaller |
| L2 decision | 8.2 MB | 98.0% smaller | 94.5% smaller |

## How much faster

The 17 supplied plots, isolated child processes, two full runs, and every timed answer checked against the proof. [Method and caveats](decision-benchmark-notes.md).

| Path | Hot, 17 plots | Fresh process: load + query | End-to-end incl. Python start | Peak memory |
| --- | --- | --- | --- | --- |
| Original layers, retained v1 query | 1.44 ms | 11.1 ms | 115 ms | 75 MB |
| Original layers, same EUDR question | 1.88 ms | 19.0 ms | 125 ms | 97 MB |
| Decision layer | 1.17 ms | 2.7 ms | 57 ms | 40 MB |
| Decision layer + exact fast selection | 0.27 ms (**5.2×**) | 1.5 ms | 57 ms | 40 MB |
| Decision layer + batch evaluator (needs a batch in hand) | 0.22 ms (**6.5×**) | 1.5 ms | 57 ms | 40 MB |
| Decision layer + registered-plot index | **0.032 ms (44×)** | 1.3 ms (8.7×) | 50 ms | 37 MB |
| Registered-plot index, numpy-free re-check | **0.017 ms (83×)** | 1.0 ms (10.9×) | **25 ms (4.6×)** | 23 MB |
| Registered-plot answer table | **0.0035 ms (410×)** | 0.24 ms (46×) | 21.6 ms (5.3×) | 21 MB |

Multiples are against the retained v1 path. These are the Phase 4 figures, the latest. How each phase got here is in [Speed-up phases](#speed-up-phases).

- **Where the speed comes from.** The representation alone gives 1.6× hot and 7.0× fresh-process speedups, because there is one small band instead of three plus a 101-bin canopy histogram. Exact scanline selection gives about 4× on new polygons. The big hot-path gain needs the **registered-plot index**: EUDR plots are registered once and re-checked whenever a layer updates, so their cells are found once (44×). The **answer table** goes further: it holds each registered plot's precomputed answer, keyed by plot ID, geometry hash and store hash (410×).
- **New, unregistered plots** take the decision layer + fast selection path: about 46,000 synthetic plot-sized polygons per second, against about 9,300 on the original path (5.0×). If the polygons arrive as a batch, the batch evaluator answers about 146,000 per second (15.8×, and 3.2× over the one-at-a-time fast path). It needs a batch in hand: a single new plot gains nothing, and on the 17-plot batch it is only 1.2× ahead of the fast path. From a cold start it is level with the fast path (1.5 ms each). Before Phase 3 it was slower (3.6 ms), because its first call imported a NumPy module it did not need.
- **Cold start.** The decision paths never import GDAL/rasterio, and the table path needs only the Python standard library. The numpy-free re-check of registered plots is the one change that also moves end-to-end time: it halves the fresh-process time of the index path (50.0 to 24.9 ms) because it never imports NumPy. Its remaining time is interpreter start-up plus the benchmark harness's own floor, not the re-check. The other paths still spend most of their end-to-end time on interpreter start-up (about 15 ms) and importing NumPy (about 25 ms).

## Speed-up phases

The decision layers were built on the afternoon of 15 Oct and benchmarked once. That is the starting point. Four phases of speed-ups followed, from that evening to the early morning of 16 Oct. No phase changed any output, store byte or file format: the proof, the validators and the tests are the same. Every multiple is against the retained v1 path (P0), re-measured in each run. Each phase's figures come from its own full benchmark re-run (2 runs, every timed answer bound to the same digests). Phase 4 is the last round.

| Hot, 17 plots, vs P0 | Decision layers (start) | Phase 1 | Phase 2 | Phase 3 | Phase 4 |
| --- | --- | --- | --- | --- | --- |
| New boundaries (P4) | 0.66 ms (2.2×) | 0.49 ms (3.0×) | 0.29 ms (5.0×) | 0.27 ms (5.3×) | 0.27 ms (5.2×) |
| 500 synthetic new polygons (P4) | 22,100/s | 28,500/s | 42,000/s | 43,700/s | 46,000/s |
| Adversarial shapes, fast vs reference selector | 0.81× | 1.16× | 1.88× | 1.92× | 1.92× |
| Batch of 500 new polygons (P4B) | — | — | 128,000/s (14×) | 141,000/s (15×) | 146,000/s (15.8×) |
| Batch path, fresh-process load + query | — | — | 3.6 ms | 1.5 ms | 1.5 ms |
| Registered index (P5d) | 0.060 ms (24×) | 0.048 ms (31×) | 0.044 ms (33×) | 0.033 ms (44×) | 0.032 ms (44×) |
| Numpy-free re-check (P5Ld) | — | — | 0.033 ms (44×) | 0.022 ms (65×) | 0.017 ms (83×) |
| Registered, fresh-process load + query | 3.5 ms | 1.3 ms | 1.3 ms; 1.0 ms numpy-free | 1.3 ms; 1.0 ms numpy-free | 1.3 ms; 1.0 ms numpy-free |
| Registered, end-to-end incl. Python start | 52 ms | 50 ms | 50 ms; 24.6 ms numpy-free | 50 ms; 24.8 ms numpy-free | 50 ms; 24.9 ms numpy-free |
| Registered, peak memory | 43 MB | 37 MB | 37 MB; 23 MB numpy-free | unchanged | unchanged |
| Answer table (P6d) | ~420× | ~430× | 417× | 417× | 410× |
| Cost, 10M new plots, tropical belt (Lambda compute) | $0.0069 | $0.0053 | $0.0032 | $0.0031 | $0.0031 |

- **The phases.** [Phase 1](#phase-1-15-oct-evening-faster-decode-reduction-and-selection) made the existing code faster. [Phase 2](#phase-2-15-oct-night-co-design-experiments) built new paths shaped to the workload. [Phase 3](#phase-3-15-oct-late-night-two-small-wins) was two small wins. [Phase 4](#phase-4-16-oct-early-morning-two-small-changes-and-a-research-pass) was two more small changes and a research pass over papers, forums and engineering options. Its one clear gain is the numpy-free re-check (65× to 83×).
- **The answer table did not change.** Its time stayed at about 0.0035 ms for 17 plots (0.2 µs per plot) within noise. The Phase 1 figure of about 430× came from a slightly higher P0 baseline in that run (1.46 ms, against 1.44 ms later); the 417× is the same table time against the later baseline. In Phase 4 the table time was 0.206 µs per plot, against 0.203 in Phase 3 (within noise), and P0 came out 0.5% lower (84.51 µs, against 84.92). So the multiple reads 410×, not 417×. It is not a slowdown.
- **New boundaries read 5.2×, not 5.3×, because of the P0 re-measure and rounding.** P4's time did not change (16.1 µs, then 16.15 µs, within noise). The Phase 3 multiple was 84.92 / 16.1 and the Phase 4 multiple is 84.51 / 16.15. On these 17 plots every polygon was already under 500 rows × edges, so the Phase 4 scan-rule change does not touch them.
- **Where the batch row comes from.** The batch evaluator exists from Phase 2. The 500-polygon figures need a batch in hand. On the 17-plot batch it is only 1.2× ahead of the one-at-a-time path.
- **Cost.** Lambda compute for re-checking 10 million new, unregistered plots over the tropical belt, at the cost model's list-price assumptions. The registered-plot lines are in the [scale notes](decision-scale-notes.md).

## Phase 1 (15 Oct, evening): faster decode, reduction and selection

After the first benchmark of the decision layers we made three speed-ups that change no output, then re-ran everything. The figures quoted in this section are the Phase 1 re-run; the table under "How much faster" is from the latest re-run (Phase 4). The starting figures (15 Oct afternoon) were 2.2× (new boundaries), 24× (registered index) and 3.5 ms fresh-process for the index.

- **What changed.**
  - **Histogram reduction** (`summarize_counts` in `engine/decision.py`): the 20-bin histogram becomes the contract outputs in fewer Python passes (one `tolist`, shared sums, precomputed keys). It is 1.6–2.2× faster on its own.
  - **Store decoding** (`_decode_split` and `read_store` in `engine/decision_store.py`): the store is decoded on the packed bit-planes (93 KB) instead of expanding every plane to 744,732 cells. The sparse loss years are applied only at event positions, and ranked event cells are found by popcount. The file format and bytes are unchanged. Reading the decision store went from 2.5 to 0.67 ms (3.8×) and the screen store from 3.7 to 1.65 ms. A side effect: the validator's crafted-blob memory case now peaks near 6 MB instead of about 50 MB.
  - **Polygon selection** (`fast_select_cells` and `_checked` in `engine/decision_index.py`): clean GeoJSON is validated in bulk and the polygon is built straight from one coordinate array, ambiguous-cell rectangles are painted without `np.add.at`, and the polygon is prepared before exact covers when many centres are ambiguous. It calls a few `shapely.lib` functions directly, so it depends on the pinned shapely 2.1.2; input that is not clean falls back to the original per-point checks.
- **What it bought (against the unchanged retained v1 path).** New boundaries 2.2× → 3.0× (synthetic set 2.4× → 3.1×). Registered index 24× → 31×, with fresh-process load + query 3.5 → 1.3 ms and peak memory 43 → 37 MB. Decision layer alone: fresh-process load + query 4.9 → 2.7 ms, peak memory 46 → 40 MB. On the adversarial boundary-heavy set, fast selection against the reference selector went from 0.81× (slower) to 1.16×. The answer table did not change.
- **Looked at, not changed.** Fresh-interpreter end-to-end time is dominated by `import numpy` (about 25 of roughly 50 ms) and interpreter start-up (about 14 ms). The honest trims left (pathlib, hashlib) are under 2 ms each, so end-to-end barely moved (index path 52.4 → 50.0 ms). Do not quote Phase 1 as an end-to-end gain. Phase 2 below changed this for registered re-checks only. The answer-table path was already about 0.2 µs per plot.
- **How it was checked.** The official benchmark was re-run (2 full runs, every timed answer bound to the same expected digests, baselines unchanged). The proof is unchanged: 9,829 of 9,829 fuzzed polygons and 744,732 of 744,732 cells identical. All 17 independent validator scripts exit 0. 300 engine tests and 311 app tests pass. The new code was also compared with the old code on corrupted and random inputs: identical decodes and rejection messages over about 16,000 corrupted store blobs, 180,000 differential comparisons of the histogram reduction, and zero mismatches against both the old fast path and `select_cells` over about 9,000 polygons plus the validator's fast-selection check.

## Phase 2 (15 Oct, night): co-design experiments

Phase 2 fitted the code to the shape of the workload instead of tuning what was there: small polygons, many polygons at once, and plots that are registered in advance. It made three more changes. None changes any output, store byte or file format. The benchmark was re-run (2 full runs, AC power) and the evidence in `artifacts/decision/` was regenerated.

- **What changed.**
  - **Scalar scan for new polygons** (`fast_select_cells` in `engine/decision_index.py`): small windows (up to 500 rows × edges and 4,096 cells) are scanned in pure Python instead of through NumPy. The centre and crossing float expressions are the same as before, and centres are found by bisect on the same computed lists. The ambiguity rule is unchanged: ambiguous centres still go to exact GEOS covers. Big windows keep the NumPy path. `fast_summarize` also builds the histogram straight from runs of selected centres, and the evaluator uses it when the selector offers it. So P4 now has a fused reduction as well, and "P3 to P4 is only the selection algorithm" is no longer exactly true.
  - **Batch evaluator** (`evaluate_many` in `engine/decision_batch.py`, path P4B): many new polygons are answered in one vectorized pass. One scanline runs over all edges, one exact covers call handles all ambiguous centres, one bincount builds the histograms, and the shared `summarize_counts` (now in `engine/decision_summary.py`, re-exported by `engine.decision`) turns each into outputs. Items the batch does not take are answered by the single path, so rejections are identical. Below `MIN_BATCH` = 4 it just loops.
  - **Numpy-free re-check of registered plots** (`engine/decision_lite.py`, paths P5Ls and P5Ld): standard library only. It validates the store (prefix, header CRC, header rules, payload sha256, every split-decode check over the whole payload, and the decision-level rule on all events) and the registry (every registry parse check). It then decodes codes only at registered cells, from the packed bit-planes and sparse loss events. It never imports NumPy and never expands the 744,732-cell raster. The store-format helpers moved unchanged into `engine/decision_format.py`, and re-encoding reproduces the store files byte for byte.
- **What it bought (against the unchanged retained v1 path).**
  - New boundaries, 17 plots: 3.0× → 5.0× (0.49 → 0.29 ms; 17.0 µs per plot). Fresh-process load + query 1.9 → 1.6 ms.
  - 500 synthetic polygons: 28,500 → 42,000 per second with the fast path (23.8 µs each), and about 128,000 per second with the batch evaluator (7.8 µs each, 14× the original path, 3.05× the fast path).
  - Adversarial boundary-heavy set (100 polygons): fast selection against the reference selector 1.16× → 1.88× (25.9 against 48.7 µs). The batch evaluator takes 9.0 µs per polygon there.
  - 17-plot batch: the batch evaluator takes 14.2 µs per plot (6.0×), only 1.2× ahead of the fast path because the batch is small. Its fresh-process time is 3.6 ms, slower than the fast path's 1.6 ms.
  - Registered index with NumPy: 31× → 33× hot (2.61 µs per plot), 50 ms end-to-end.
  - Numpy-free index: 1.93 µs per plot hot (44×, 1.35× over the NumPy index), 1.0 ms fresh-process load + query (10.8×), 24.6 ms end-to-end against 49.7 ms (2.0×, or 4.6× against the original path), peak memory 23 MB against 37. The screen level is the same shape: 26.6 ms against 50.9 ms.
  - Answer table: about 0.2 µs per plot (417×), unchanged within noise; 21.3 ms end-to-end.
- **End-to-end is different this time.** Phase 1 could not move end-to-end time, and the same is still true for the fast path, the batch path and the NumPy index. The numpy-free re-check is the exception, because skipping `import numpy` removes about 25 ms. What is left is interpreter start-up plus the benchmark harness's own floor (19.7 ms for a no-op child).
- **Not checked by the numpy-free path.** It does not check the decoded raster's `codes_sha256`, because that needs a full decode. Pinning the store file's sha256 closes the gap: the benchmark pins it, as the table path does. Without that pin, the NumPy index path is the one that checks the decoded raster.
- **How it was checked.** Every timed answer is bound to the same expected digests, and the proof is unchanged: 9,829 of 9,829 fuzzed polygons and 744,732 of 744,732 cells identical. The new scan was compared with a verbatim copy of the old code and with `select_cells` on 58,896 polygon and grid cases: zero mismatches in cells, dtype, exception type and message. The batch evaluator was compared with the single path on about 185,000 cases: zero mismatches. For the numpy-free re-check, about 118,000 corrupted store blobs were all rejected with `ValueError`, and its decoded cells were checked against the full-raster path at both levels.

## Phase 3 (15 Oct, late night): two small wins

Phase 3 made two small changes. Neither changes any output, store byte or file format. The benchmark was re-run (2 full runs, AC power) and the evidence in `artifacts/decision/` was regenerated.

- **What changed.**
  - **Histogram reduction** (`summarize_counts` in `engine/decision_summary.py`): the one shared reducer that turns a 20-code histogram into the contract answer now unpacks the 20 codes by name and builds the answer dicts directly, instead of slicing, zipping and calling a nested helper. It is about 2× faster on its own (about 1.6 to 0.8 µs per call). A module guard raises if the code layout constants ever change. It speeds up every path that computes answers live: the registered index, the numpy-free re-check, new boundaries and the batch.
  - **First call of the batch evaluator** (`engine/decision_batch.py`): numpy 2.5's `np.unique` imports `numpy.ma` on first use, which costs about 2 ms. A small sort-and-dedupe helper replaces it, with an identical result.
- **What it bought.** Hot time is per plot on the 17 plots. The multiple is against the retained v1 path (P0, 84.9 µs per plot).

| Path | Phase 2 | Phase 3 |
| --- | --- | --- |
| Registered index (P5d) | 2.61 µs (33×) | 1.93 µs (44×) |
| Numpy-free re-check (P5Ld) | 1.93 µs (44×) | 1.31 µs (65×) |
| Registered index, screen level (P5s) | 3.48 µs | 2.29 µs |
| Numpy-free re-check, screen level (P5Ls) | 2.82 µs | 1.67 µs |
| New boundaries (P4) | 17.0 µs (5.0×) | 16.1 µs (5.3×) |
| Batch of 17 plots (P4B) | 14.2 µs (6.0×) | 13.4 µs (6.4×) |
| Batch, fresh-process load + query | 3.64 ms | 1.54 ms |
| Batch, end-to-end | 59.1 ms | 56.5 ms |
| 500 synthetic polygons, fast path (P4) | 23.8 µs (42,000 per second) | 22.9 µs (about 43,700 per second) |
| 500 synthetic polygons, batch (P4B) | 7.8 µs (128,000 per second, 14×) | 7.08 µs (about 141,000 per second, about 15×) |
| 100 adversarial polygons, fast path / batch | 25.9 / 9.0 µs | 25.0 / 8.1 µs |

- **Everything else is unchanged within noise.** The answer table (about 417×), the other paths' end-to-end times and the stored bytes did not move. The batch path's fresh-process time is now level with one-at-a-time (1.54 ms each), so it is no longer slower from a cold start.
- **The floors that are left.**
  - New boundaries: this bullet originally said that about 5 µs of the remaining ~16 µs per plot was the required geometry validity check, and that the rest was the scan and the answer. That was wrong (corrected in Phase 4): the check itself is about 0.8 µs. See [where the 16 µs goes](#where-the-16-µs-goes).
  - End-to-end: interpreter start-up (about 14 ms) plus the benchmark harness's own floor (about 20 ms) dominate.
  - The answer table did not change.
- **How it was checked.** Every timed answer is bound to the same expected digests, and the proof is unchanged: 9,829 of 9,829 fuzzed polygons and 744,732 of 744,732 cells identical. The new reducer was compared with the old one on 300,000 random histograms: identical outputs, key order and errors. A permanent test (`engine/tests/test_decision_summary.py`) pins it to the old generic reducer on 40,000 seeded cases. Between the two benchmark runs the median spread was 1.0% and the largest 3.6%. The load average was about 2.1, slightly busier than for Phase 2.

## Phase 4 (16 Oct, early morning): two small changes and a research pass

Phase 4 is the last round of speed-ups. It made two small changes and removed one unused variable. None changes any output, store byte or file format. The benchmark was re-run (2 full runs, AC power, main checkout) and the evidence in `artifacts/decision/` was regenerated. The round also included a research pass over papers, forums and engineering options. It found nothing that beats the current approach for small plots. The two ideas worth keeping are on the roadmap, not built.

### What changed

- **A trusted entry to the shared reducer** (`summarize_ints` in `engine/decision_summary.py`).
  - `summarize_counts` is the one reducer that turns the 20-code histogram into the answer. It used to convert its input to a list of Python ints on every call.
  - Callers that already hold a list of Python ints now call `summarize_ints` instead. It is the same reducer with the same checks in the same order, minus that conversion.
  - The callers are the numpy-free re-check, the batch evaluator, the NumPy registry path and the fast new-boundary path. `summarize_counts` still accepts anything and calls it.
- **When the pure-Python scan is used** (`SCALAR_SURE_ROWS` = 500, `SCALAR_EDGE_ROWS` = 2,000 and `SCALAR_CROSSINGS` = 150 in `engine/decision_index.py`).
  - New polygons with up to 500 rows × edges still always use the pure-Python scan.
  - Between 500 and 2,000 they now also use it, unless the boundary changes rows more than 150 times in total. Shapes like that are called "sawtooth" shapes here. They go to the NumPy scan, as before. The 4,096-cell window limit from Phase 2 still applies.
  - The reason is a 224-shape sweep. The NumPy scan was faster on sawtooth shapes. The Python scan costs about 0.17 µs per row that an edge crosses. Rows × edges turned out to be a poor predictor of its time (R² of 0.66), against 0.99 for a fit on edges and row crossings.
  - The two scans were already proven identical (see below).
- **Removed:** one unused variable.

### What it bought

Hot time is per plot on the 17 plots. The multiple is against the retained v1 path (P0). P0 measured 84.51 µs per plot in this run (1.437 ms for 17 plots), against 84.92 µs in Phase 3. That 0.5% difference alone moves every multiple down by 0.5%, with no code change. Fresh-process load + query for P0 was 11.11 ms and end-to-end 114.5 ms.

| Path | Phase 3 | Phase 4 |
| --- | --- | --- |
| New boundaries (P4), 17 plots | 16.1 µs (5.3×) | 16.15 µs (5.2×) |
| 500 synthetic polygons, fast path (P4) | 22.9 µs (about 43,700 per second) | 21.73 µs (about 46,000 per second; 5.0× P0's 108 µs on the same set) |
| 100 adversarial polygons, fast path against the reference selector | 1.92× | 1.92× |
| 500 synthetic polygons, batch (P4B) | 7.08 µs (about 141,000 per second, about 15×) | 6.85 µs (about 146,000 per second, 15.8×; 3.2× the one-at-a-time path) |
| Batch of 17 plots (P4B) | 13.4 µs (6.4×) | 13.04 µs (6.5×), only 1.24× ahead of P4 |
| 100 adversarial polygons, batch | 8.1 µs | 7.8 µs |
| Batch, fresh-process load + query | 1.54 ms | 1.53 ms |
| Registered index (P5d) | 1.93 µs (44×) | 1.90 µs (44×) |
| Registered index, screen level (P5s) | 2.29 µs | 2.23 µs |
| Numpy-free re-check (P5Ld) | 1.31 µs (65×) | **1.02 µs (83×)** |
| Numpy-free re-check, screen level (P5Ls) | 1.67 µs | 1.38 µs |
| Registered, fresh-process load + query | 1.3 ms; 1.0 ms numpy-free | unchanged (1.28 ms; 1.02 ms) |
| Registered, end-to-end | 50 ms; 24.8 ms numpy-free | unchanged (50.0 ms; 24.9 ms) |
| Registered, peak memory | 37 MB; 23 MB numpy-free | unchanged |
| Answer table (P6d) | 0.203 µs (417×) | 0.206 µs (410×) |
| Cost, 10M new plots, tropical belt (Lambda compute) | $0.0031 | $0.0031 (it prices P4 on the 17 plots, which did not change); registry line $0.0008 |

- **The one clear gain is the numpy-free re-check.** It went from 1.31 to 1.02 µs per plot (65× to 83×), and its screen level from 1.67 to 1.38 µs. The other hot figures moved by about 1% to 5%. Some of that is within the between-run spread (median 0.5%, largest 2.3%).
- **New boundaries on the 17 plots did not change.** Every polygon here was already under 500 rows × edges, so the scan-rule change does not touch them. The multiple dropped from 5.3× to 5.2× only because P0 re-measured slightly lower and the figures round differently. The 500-polygon synthetic set did move (22.9 to 21.73 µs). We did not separate how much came from the scan rule and how much from the reducer change.
- **The answer table is not slower.** Its time went from 0.203 to 0.206 µs per plot, which is within noise. P0 came out 0.5% lower. Together they turn 417× into 410×.
- **Fresh-process load + query, end-to-end time and memory did not move.** Phase 4 changed per-plot compute, not loading or imports.

### Where the 16 µs goes

Phase 3 said that about 5 µs of the remaining ~16 µs per new plot was the required geometry validity check. That was wrong. An independent audit of P4 on the 17 plots measured each stage:

| Stage | µs per plot |
| --- | --- |
| Coordinate parsing and validation | 1.38 |
| Building the shape | 1.59 |
| Validity check | 0.84 |
| Scanning rows | 4.93 |
| Gathering cells and the histogram | 3.14 |
| Building the answer | 0.63 |
| Other overhead (bounds, grid and window checks, dispatch) | 3.83 |
| **Total** | **16.35** |

- **No single big cost is left.** The largest stage, scanning rows, is about 30% of the total. Everything else is smaller.
- **The validity check is cheap.** The GEOS check itself is 0.8 µs on the 17 plots and 2.0 µs on the 500 synthetic polygons. It grows with vertex count: about 0.84 µs at 8 vertices, 1.25 at 16, 4.1 at 60 and 12 at 150.
- **The audit total (16.35 µs) is a separate measurement from the benchmark's 16.15 µs.** The two differ by about 1%.

### Research pass

We also checked papers, forums and engineering options for anything that would beat the current approach.

- **Papers and tools: nothing beats the current approach for small plots with an exact centre rule.**
  - The centre rule is the standard zonal-statistics default (GDAL and rasterstats).
  - Raster Join (Zacharatou et al., VLDB 2017 and CIDR 2021) aggregates data over polygons on a GPU canvas. Its exact form does what we do: a fast interior pass and exact checks at the border. Its bounded form gives up exactness, which we cannot do.
  - Raptor zonal statistics is aimed at huge rasters and huge polygons.
  - k²-raster, for querying compressed rasters directly, does not apply. Our store decodes once in about 0.7 ms.
  - Integral histograms and summed-area tables do not apply. Plots are not rectangles, and row spans of about 10 cells are cheaper to scan directly.
  - exactextract computes coverage fractions, not the centre rule.
- **Other EUDR tools publish no per-plot latency.** This covers Whisp on Earth Engine, the Global Forest Watch Data API and Earth Engine `reduceRegion`. The honest claim is "per-plot cost once the layer is local", not "faster than Whisp".
- **A GPU is not useful for queries.**
  - A plot is about 120 cells. Launch and transfer overhead on a GPU is around 10 µs, which is about the cost of the whole query.
  - Apple GPUs (Metal) have no float64, so the exact centre maths would change.
  - GEOS, the geometry engine, runs on the CPU.
- **A GPU is also not useful for building the layer.** This is a scratch measurement, not a committed artifact. It covered 6 of the 160 strips of the real tile, in a single process.

  | Build step | Time per strip | Share |
  | --- | --- | --- |
  | Read | about 0.05 s | 2% |
  | Derive codes | about 0.15 s | 6% |
  | Our compression | about 2.4 s | 92% |

  - The compression is slow because it tries 10 compressor settings per stream and keeps the smallest. The winner is mostly LZMA, which has no GPU version.
  - Even if deriving the codes cost nothing, the whole build would be only about 1.06× faster.
  - The build takes about 7 CPU-minutes per tile. For about 280 land tiles worldwide that is roughly 30 to 60 CPU-hours. This is an estimate: the tile is coastal, and inland tiles encode more slowly. The work splits cleanly across ordinary CPUs, and Hansen updates once a year.
- **Engineering options were measured or checked, then skipped.**

  | Option | Measured or known result |
  | --- | --- |
  | Python 3.14 JIT | Not in the Homebrew build. Where available, 2–3% slower |
  | Tail-calling interpreter | About 2–5% gain, and needs a different interpreter |
  | Cython on the module | About 6% gain, and needs per-platform builds |
  | mypyc | Failed to import |
  | numba | 0.2–0.7 s to compile on the first call |
  | PyPy | No shapely or numpy wheels |
  | GEOS 3.14 / shapely 2.2 | About 3% gain |
  | Hand-written validity check | About 8× slower than GEOS in Python, with risky edge cases |
  | Python start-up flags | About 0.5 ms |

- **Roadmap ideas, not built.**
  - Change-only re-checks. When a layer updates, re-check only the plots whose cells changed. This needs an inverted cell-to-plot index. It is incremental view maintenance (DBSP, VLDB 2023).
  - Calling GEOS directly through `ctypes` for new polygons, which skips NumPy and shapely. A prototype cut a fresh new-plot process from about 48 to about 20 ms and saved about 2.7 µs per plot, with 0 mismatches on 60,000 degenerate polygons. It is 3 to 5 hours of careful work.

### Looked at, not changed

- **Keeping the `pathlib` import off the numpy-free path.** It saves about 2 ms in a bare numpy-free process. The official benchmark's harness imports `pathlib` itself, so the saving cannot show up there, and it added code. Tested and dropped.
- **`shapely.lib`.** We keep calling `shapely.lib` directly, with shapely pinned at 2.1.2. Switching every call to the public shapely API was measured at +5.2 µs per plot on new boundaries (about 31% slower) and about 1% on the batch path, with identical answers.
- **Dead code.** The audit found almost none. The one unused variable was removed. Two diagnostic timing commands stay on purpose: `python -B -m engine.decision_batch_measure` and the timing printed by `python -B -m engine.decision_index`.
- **Two ideas rejected because they would only game the benchmark.**
  - Caching each plot's histogram across calls.
  - Moving the per-plot counting into load time.
  - In real use each plot is re-checked once per layer update, so neither would help a real workload.

### How it was checked

- **Benchmark.** Two full runs, AC power, main checkout. The load average was about 2.3–2.8. The median spread between the runs was 0.5% and the largest was 2.3%. Every timed answer is bound to the same expected digests.
- **Proof unchanged.** 9,829 of 9,829 fuzzed polygons and 744,732 of 744,732 cells are identical. The proof's `all_pass` is true.
- **Tests and validators.** 361 engine tests pass, and all 17 independent validators exit 0.
- **The reducer.** The existing test that pins it to the old generic reducer on 40,000 seeded cases passes unchanged. A new test (`test_decision_summary.py`) compares `summarize_ints` with `summarize_counts` on 20,000 seeded cases: results, key order, exception type and message.
- **The scan.** The differential check against `select_cells` was re-run on 14,500 polygons. There were 0 mismatches in cells, dtype, exception type and message.

## What the decision layer says about the 17 plots

- **P-0001:** 60 of its 121 cells were JRC 2020 forest. **2 cells** were lost in 2022: mapped loss on mapped 2020 forest. Its other 36 loss cells from 2022 were on land JRC did not map as forest.
- **The other 16 plots:** no mapped 2020 forest, so no mapped deforestation, with complete support. Six of them (P-0005, P-0006, P-0013, P-0014, P-0016, P-0018) do have Hansen loss after 2020. That loss was all on land JRC did not map as forest in 2020.
- **The JRC sampling rule doesn't move any plot decision.** Reading the centre JRC cell, the 3×3 majority, or "any forest in the block" gives the same forest-present and deforestation-present flags for all 17 plots. Only P-0001 has forest, so this is a weak test, and we say so.

These are mapped observations from public layers under a written rule. They are not a compliance verdict.

## Honest limits

- One 34 × 17 km sample region and one laptop. The OS file cache was warm. The whole-tile figures are storage sizes only; we did not run queries at tile scale.
- The JRC 2020 class is read at each Hansen cell centre (one of 9 JRC cells). This is a documented simplification, tested for sensitivity above.
- No layer here applies EUDR's 0.5 ha minimum area or the "able to reach 5 m in situ" test. "Deforestation" here means mapped loss on mapped 2020 forest.
- Protected areas (WDPA) are not included because their licence is unclear.
- The registered-plot index and the answer table only answer plots registered in advance. New boundaries go through the decision layer.
- The batch figure needs a batch in hand. A single new plot gains nothing from it, and on a small batch the gain is small.
- The numpy-free re-check trusts a pinned store file hash instead of checking the decoded raster's hash.
- Other EUDR tools publish no per-plot latency, so every multiple here is against our own retained v1 path. We make no "faster than" claim about other tools. The claim is per-plot cost once the layer is local.
- The layer build figures from the research pass (about 7 CPU-minutes per tile, roughly 30 to 60 CPU-hours for about 280 land tiles) are estimates. They come from a scratch measurement on 6 of the 160 strips of one coastal tile, and are not a committed artifact.
- The audit's stage breakdown of the 16 µs (Phase 4) is a separate measurement from the benchmark, and it comes from the 17 plots only.

## Validation

The independent validator confirmed fidelity, independence, semantics, storage accounting, fast-selection exactness and the whole-tile figures.

It also found hardening issues:

- an unprotected store header;
- an `OverflowError` path;
- level/raster mix-ups;
- allocation amplification from crafted input;
- missing content binding on the table and registry;
- an overstated cost-model read time.

Each was fixed with a test that fails on the old code. After the fixes and a full evidence rebuild, the validator updated its scripts to the new formats and re-ran them: all 17 now pass. One residual it found, an aggregate memory bound in the registry parser, was then closed too. The remaining accepted risk is deliberate forgery with recomputed hashes, which is out of scope for integrity checks; callers that need authenticity pin the genuine file hash. See [validation/decision/report.md](../../validation/decision/report.md).

## Reproduce

```sh
.venv-data/bin/python -B -m engine.decision_store       # stores + controls (≈20 s)
.venv-data/bin/python -B -m engine.decision_proof       # exhaustive + 17 plots + fuzz (≈15 s)
.venv-data/bin/python -B -m engine.decision_index       # registry + table
.venv-data/bin/python -B -m engine.decision_benchmark   # timing, paths P0-P6 incl. P4B, P5L (≈2.5 min)
.venv-data/bin/python -B -m engine.decision_scale       # layer analysis, whole tile (needs raw tiles), cost
.venv-data/bin/python -B -m engine.decision_export      # app summary
.venv-data/bin/python -B -m unittest discover -s engine/tests -p 'test_decision*.py'   # decision-layer tests (≈30 s)
.venv-data/bin/python -B validation/decision/run_all.py # independent checks
```

The modules added in the speed-up phases are libraries, not commands:

- [`decision_summary.py`](../../engine/decision_summary.py): the code space and the shared reducer (Phase 2 split it out of `decision.py`; Phase 3 sped it up; Phase 4 added the trusted-integer entry `summarize_ints`). Test: `test_decision_summary.py`.
- [`decision_format.py`](../../engine/decision_format.py): the store file format without NumPy, shared by `decision_store.py` and `decision_lite.py` (Phase 2). Tested through `test_decision_store.py` and `test_decision_lite.py`.
- [`decision_batch.py`](../../engine/decision_batch.py): the batch evaluator, path P4B (Phase 2; Phase 3 removed its `np.unique` import cost). Tests: `test_decision_batch.py`, and `test_decision_scalar_scan.py` for the scalar scan in `decision_index.py`.
- [`decision_lite.py`](../../engine/decision_lite.py): the numpy-free re-check of registered plots, paths P5Ls and P5Ld (Phase 2). Test: `test_decision_lite.py`.
- `python -B -m engine.decision_batch_measure` times the loop against the batch in one process. It writes nothing. It and the timing printed by `python -B -m engine.decision_index` are diagnostics kept on purpose.
