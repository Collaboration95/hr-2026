# Decision-layer benchmark (draft, 15 Oct 2026)

Updated after Phase 4 (16 Oct, early morning), the last round of the speed-up work. The consolidated phase table is in the [decision-layer report](decision-layer-report.md#speed-up-phases); the phases are [Phase 1](decision-layer-report.md#phase-1-15-oct-evening-faster-decode-reduction-and-selection) (faster decode, reduction and selection), [Phase 2](decision-layer-report.md#phase-2-15-oct-night-co-design-experiments) (co-design experiments), [Phase 3](decision-layer-report.md#phase-3-15-oct-late-night-two-small-wins) (two small wins) and [Phase 4](decision-layer-report.md#phase-4-16-oct-early-morning-two-small-changes-and-a-research-pass) (a trusted entry to the shared reducer, a better rule for when the pure-Python scan is used, and a research pass). The figures below are the latest re-run (Phase 4). The retained path P0 and the answer table P6 are unchanged within noise; P0 re-measured 0.5% lower this run (84.51 µs per plot, against 84.92), which lowers every multiple by about 0.5% before any code change. Phase 2 added three paths: P4B (batch evaluator), P5Ls and P5Ld (numpy-free registered-plot re-check). Phase 3 sped up the shared histogram reducer (every live-answer path) and the batch evaluator's first call. Phase 4's one clear gain is the numpy-free re-check (1.31 to 1.02 µs per plot). The Phase 2 and Phase 3 figures are kept in the comparison tables below the headline table.

Draft section for the main agent to integrate. Code: [`engine/decision_benchmark.py`](../../engine/decision_benchmark.py). Result: [`benchmark-v1.json`](../../artifacts/decision/benchmark-v1.json) (raw samples, summaries, decomposition, binding checks). Rerun with `.venv-data/bin/python -B -m engine.decision_benchmark` (about 2.6 minutes; `--quick` is a 6-second smoke test that writes to the temp directory).

It copies the retained harness (`engine/benchmark.py`): every path runs in its own fresh child with one thread, nearest-rank p95, no disk-cache control. Before anything is timed, the parent checks that original layers, both stores, fast selection, the one-call batch evaluator, the registry, the numpy-free re-check and the table give identical answers, and every timed child returns an answer digest that must match.

## Headline: the 17 supplied plots

Median, with p95 in brackets. Pooled over 2 whole runs. Each run uses 2 fresh hot children per path, plus 21 process-cold and 21 end-to-end children per path.

| Path | Hot, 17-plot batch, ms | Process-cold, ms | End-to-end fresh process, ms | Peak RSS, MB | Bytes read | Arrays held, B |
| --- | --- | --- | --- | --- | --- | --- |
| P0 original v1 (3 Hansen bands) | 1.437 (1.50) | 11.11 (11.5) | 114.5 (116.1) | 74.8 | 585,293 | 4,468,392 |
| P1 original layers, screen | 1.988 (2.10) | 19.13 (19.7) | 124.5 (128.3) | 97.2 | 642,946 | 17,836,902 |
| P1 original layers, decision | 1.880 (1.96) | 18.95 (19.6) | 124.9 (129.2) | 97.1 | 642,946 | 17,836,902 |
| P2 screen store | 1.179 (1.22) | 3.87 (4.0) | 58.8 (60.3) | 41.4 | 38,513 | 744,732 |
| P3 decision store | 1.175 (1.23) | 2.68 (2.8) | 57.2 (59.0) | 40.2 | 6,146 | 744,732 |
| P4 decision store, fast selection | 0.275 (0.290) | 1.55 (1.6) | 56.9 (58.9) | 39.9 | 6,146 | 744,732 |
| P4B decision store, batch evaluator | 0.222 (0.236) | 1.53 (1.6) | 56.9 (59.1) | 40.3 | 6,146 | 744,732 |
| P5 screen registry | 0.0379 (0.0393) | 2.50 (2.6) | 51.4 (53.5) | 37.8 | 42,609 | 748,924 |
| P5 decision registry | 0.0323 (0.0338) | 1.28 (1.3) | 50.0 (52.0) | 36.7 | 10,242 | 748,924 |
| P5L screen registry, numpy-free | 0.0234 (0.0244) | 2.63 (2.8) | 27.1 (27.6) | 23.4 | 42,609 | 1,048 |
| P5L decision registry, numpy-free | 0.0173 (0.0181) | 1.02 (1.1) | 24.9 (25.8) | 22.9 | 10,242 | 1,048 |
| P6 screen table | 0.0036 (0.0037) | 0.246 (0.26) | 21.8 (22.3) | 20.7 | 20,650 | 0 |
| P6 decision table | 0.0035 (0.0036) | 0.244 (0.26) | 21.6 (22.2) | 20.7 | 20,650 | 0 |

### Phase 3 against Phase 2

Same 17 plots. "Phase 2" is the night re-run that the headline table showed before. Multiples are against P0.

| Path | Hot per plot, Phase 2 | Hot per plot, Phase 3 | Fresh process, Phase 2 | Fresh process, Phase 3 | End-to-end, Phase 2 | End-to-end, Phase 3 |
| --- | --- | --- | --- | --- | --- | --- |
| P4 fast selection | 17.0 µs (5.0×) | 16.1 µs (5.3×) | 1.55 ms | 1.54 ms | 56.5 ms | 56.8 ms |
| P4B batch evaluator | 14.2 µs (6.0×) | 13.4 µs (6.4×) | 3.64 ms | 1.54 ms | 59.1 ms | 56.5 ms |
| P5 decision registry | 2.61 µs (33×) | 1.93 µs (44×) | 1.29 ms | 1.28 ms | 49.7 ms | 49.8 ms |
| P5 screen registry | 3.48 µs | 2.29 µs | 2.53 ms | 2.50 ms | 50.9 ms | 51.3 ms |
| P5L decision registry | 1.93 µs (44×) | 1.31 µs (65×) | 1.03 ms | 1.01 ms | 24.6 ms | 24.8 ms |
| P5L screen registry | 2.82 µs | 1.67 µs | 2.67 ms | 2.66 ms | 26.6 ms | 27.0 ms |

Only the hot columns and the batch's fresh-process time moved. The other differences are within the between-run spread.

### Phase 4 against Phase 3

Same 17 plots. "Phase 3" is the late-night re-run that the headline table showed before. Multiples are against P0, which re-measured at 84.51 µs per plot in Phase 4 against 84.92 in Phase 3.

| Path | Hot per plot, Phase 3 | Hot per plot, Phase 4 | Fresh process, Phase 3 | Fresh process, Phase 4 | End-to-end, Phase 3 | End-to-end, Phase 4 |
| --- | --- | --- | --- | --- | --- | --- |
| P4 fast selection | 16.1 µs (5.3×) | 16.15 µs (5.2×) | 1.54 ms | 1.55 ms | 56.8 ms | 56.9 ms |
| P4B batch evaluator | 13.4 µs (6.4×) | 13.04 µs (6.5×) | 1.54 ms | 1.53 ms | 56.5 ms | 56.9 ms |
| P5 decision registry | 1.93 µs (44×) | 1.90 µs (44×) | 1.28 ms | 1.28 ms | 49.8 ms | 50.0 ms |
| P5 screen registry | 2.29 µs | 2.23 µs | 2.50 ms | 2.50 ms | 51.3 ms | 51.4 ms |
| P5L decision registry | 1.31 µs (65×) | 1.02 µs (83×) | 1.01 ms | 1.02 ms | 24.8 ms | 24.9 ms |
| P5L screen registry | 1.67 µs | 1.38 µs | 2.66 ms | 2.63 ms | 27.0 ms | 27.1 ms |
| P6 decision table | 0.203 µs (417×) | 0.206 µs (410×) | 0.243 ms | 0.244 ms | 21.3 ms | 21.6 ms |

The clear gain is P5L (1.31 to 1.02 µs per plot). The other hot differences are small, and several are inside the between-run spread. The fresh-process and end-to-end columns did not move beyond that spread. The P6 multiple fell from 417× to 410× only because the table time is the same within noise (0.203 to 0.206 µs) and P0 re-measured 0.5% lower. It is not a slowdown. P4 on the 17 plots did not change either: every polygon was already under 500 rows × edges, so the Phase 4 scan-rule change does not touch them.

Definitions:

- P0 is `load_source` plus `engine.query.evaluate`. It answers a bigger question: it also returns the 101-bin canopy histogram and the full loss-year histogram.
- P1 is `load_source`, `load_jrc` and `evaluate_original`. This is the apples-to-apples baseline: the same EUDR question from the original layers.
- P2 and P3 are `read_store` plus `evaluate_codes`. P4 swaps in `fast_select_cells`, which now scans small windows in pure Python (always up to 500 rows × edges; up to 2,000 unless the boundary changes rows more than 150 times in total) and builds the histogram straight from runs of selected centres (so P4 also has a fused reduction). P4B answers the whole workload in one `evaluate_many` call. P5 is the store plus `load_registry` plus `registry_evaluate`, which checks the store's level and grid on every call. P5L is the numpy-free version of P5 (`engine/decision_lite.py`): it validates the store and registry with the standard library only and decodes codes just at the registered cells from the packed bit-planes and sparse loss events. It does not check the decoded raster's `codes_sha256` (that would need a full decode); the request pins the store file's sha256 instead, as it does for the table. P6 is `load_table` plus `table_lookup`, stdlib only. P5, P5L and P6 answer registered plots only.
- Hot batch is the wall time of one pass over the 17 plots after loading and warmups (50 to 100 warmups, 500 to 1,000 measured batches per child). Per plot it is the batch divided by 17: P0 84.5 µs, P1 decision 110.6, P3 69.1, P4 16.15, P4B 13.0, P5 decision 1.90, P5L decision 1.02, P6 decision 0.21.
- Process-cold is the retained definition: a fresh child, timed full load plus one 17-plot batch, after imports and geometry read. The OS file cache is warm and not controlled.
- End-to-end is the parent's wall time for a fresh `python -B` that imports only what its path needs, reads the request on stdin, loads, answers the 17 plots and prints the digest. It includes interpreter start-up and imports. Measured floors on the same machine: `python -B -c pass` is 14.6 ms and the harness no-op is 20.1 ms. Net of `-c pass`, the paths cost 99.9 (P0), 110.3 (P1 decision), 42.7 (P3), 42.3 (P4), 42.4 (P4B), 35.4 (P5 decision), 10.4 (P5L decision) and 7.1 ms (P6 decision).
- Peak RSS is the child's lifetime high-water mark (`rss_record`) from the process-cold children. Arrays held is the `nbytes` of the loaded arrays. The table path holds no arrays; its parsed table is 67,004 bytes of Python objects.
- Bytes read are the files the loader opens, taken from the files. The table file holds both levels, so P6 reads 20,650 bytes either way.

## What each step is worth

Speedup is the slower path's median divided by the faster path's. Same questions and same machine, so only the lever changes.

| Step (decision level) | Hot, 17 plots | Hot, 500 synthetic | Process-cold | End-to-end |
| --- | --- | --- | --- | --- |
| Representation, P1 to P3: derived codes instead of original layers, same selection | 1.60× | 1.47× | 7.06× | 2.18× |
| Selection, P3 to P4: `fast_select_cells` (scalar scan and fused reduction) instead of `select_cells` | 4.28× | 4.17× | 1.73× | 1.01× |
| Batch, P4 to P4B: one vectorized pass for the whole workload | 1.24× | 3.17× | 1.01× (was 0.43×, slower, before Phase 3) | 1.00× |
| Registry index, P3 to P5: precomputed cells instead of selection | 36.3× | not applicable | 2.10× | 1.14× |
| No numpy, P5 to P5L: standard library only, packed planes | 1.87× | not applicable | 1.26× | 2.00× |
| Table, P5 to P6: stored outputs instead of a bincount and reduction | 9.24× | not applicable | 5.25× | 2.31× |
| Total, P1 to P6 | 537× | not applicable | 77.7× | 5.77× |
| Total, P0 to P6 | 410× | not applicable | 45.5× | 5.29× |

The screen level gives the same shape: P1 to P2 1.69× hot and 4.9× cold, P2 to P5 31.1× hot, P5 to P5L 1.62× hot and 1.90× end-to-end, P5 to P6 10.6× hot, P1 to P6 555× hot.

- The representation step lumps two things: the stored per-cell codes replace the float affine lookup of two layers, and the reduction becomes one bincount over 20 codes.
- Fast selection is much faster than `select_cells` on ordinary shapes and less so on boundary-heavy ones. On 100 adversarial boundary polygons (aligned edges, vertices on cell centres, slivers, lattices; from the test fuzz generator) P4 takes 24.9 µs per polygon against 47.7 for P3, a 1.92× speedup (it was 1.92× after Phase 3, 1.88× after Phase 2, 1.16× after Phase 1 and 0.81×, slower, at the start), because many centres still go to exact GEOS. P4B takes 7.8 µs there. "P3 to P4 is only the selection algorithm" is no longer exactly true: P4 also uses a fused reduction.
- P4B needs a batch in hand. Below `MIN_BATCH` = 4 it just loops over the single path, so one new plot gains nothing. On the 17-plot batch it is only 1.2× ahead of P4 (13.04 against 16.15 µs per plot), because the fixed per-call cost of its NumPy and shapely passes is spread over few plots. From a cold start it is level with P4 (1.53 and 1.55 ms). It was slower before Phase 3 (3.64 against 1.55 ms) because numpy 2.5's `np.unique` imports `numpy.ma` on first use, about 2 ms; a small sort-and-dedupe helper replaced it with an identical result. The gain shows on the 500-polygon batch (3.17×).
- Most end-to-end time is imports. P0 and P1 spend about 73 ms importing numpy, shapely and rasterio. P3, P4 and P4B spend 30 ms (no rasterio). P5 spends 24 ms (no shapely). P5L spends 3.4 ms (stdlib only, no numpy). P6 spends 1.15 ms (stdlib only). Phase 1 changed none of this, which is why end-to-end barely moved then: P5 decision went from 52.4 to 50.0 ms while its load + query went from 3.5 to 1.3 ms. P5L is the exception: dropping `import numpy` takes the registered re-check from 50.0 to 24.9 ms end-to-end (2.0×; 4.6× against P0). What is left is interpreter start-up (about 14 ms) plus the harness floor (about 20 ms). Net of the 20.1 ms harness floor, P5L decision costs 4.8 ms. Phase 3 did not move end-to-end times except the batch path's (59.1 to 56.5 ms), and Phase 4 did not move them at all beyond the between-run spread.
- The registry adds about 0.17 ms of load (1.22 ms against 1.05 ms for the store alone) and saves about 1.6 ms of query, so P5 process-cold is 1.28 ms against 2.69 ms for P3. P5L loads in 0.97 ms because it reads and validates the store without building arrays, so its process-cold time is 1.02 ms.

## New polygons

Throughput on 500 synthetic plot-like polygons (W3), one core, hot. These are seeded random concave shapes, 0.5 to 20 ha, 15% with a hole, centred on land, between 5 and 267 cells each (median 36). They are not company data.

| Path | µs per polygon, median (p95) | Polygons per second |
| --- | --- | --- |
| P0 original v1 | 108.1 (112.5) | 9,260 |
| P1 original layers, decision | 133.1 (137.2) | 7,510 |
| P2 screen store | 91.7 (95.2) | 10,900 |
| P3 decision store | 90.6 (92.8) | 11,000 |
| P4 fast selection | 21.73 (22.82) | 46,000 |
| P4B batch evaluator (whole 500 in one call) | 6.85 (7.18) | 146,000 |

Earlier phases for the two live paths: Phase 3 P4 22.9 µs (43,700 per second), P4B 7.08 µs (141,000 per second); Phase 2 P4 23.8 µs (42,000 per second), P4B 7.81 µs (128,000 per second). The Phase 4 gain on this set (22.9 to 21.73 µs for P4) comes from the scan-rule change and the leaner reducer call together; they were not measured separately.

P4 is 5.0× the original path and P4B is 15.8× (3.2× over P4). P4B's per-polygon figure is the batch time divided by 500, so it needs the batch in hand.

On the 100 adversarial polygons (W4, P3, P4 and P4B only): P3 47.7 µs (49.1), P4 24.9 (26.0), P4B 7.8 (8.5). Phase 3: P3 47.9, P4 25.0, P4B 8.1. Phase 2: P3 48.7, P4 25.9, P4B 9.0.

Registered-plot key, hot, per plot:

| Path | Geometry hash precomputed | Geometry hashed on every call |
| --- | --- | --- |
| P5 decision registry | 1.90 µs | 5.97 µs |
| P5L decision registry, numpy-free | 1.02 µs | 4.55 µs |
| P6 decision table | 0.21 µs | 3.65 µs |

The realistic registered-plot workflow is the precomputed key. A plot is registered once, its geometry hash is stored with it, and queries arrive by plot ID. Hashing the geometry on every call is what a service does when a client re-sends the polygon and the service wants to confirm it is unchanged. It costs about 3.5 µs per plot (canonical JSON plus SHA-256) and makes the table about 18× slower than the precomputed key. The table needs the layer version (store SHA-256) as an input. Verifying it by hashing the store file costs 11 µs for the decision store and 21 µs for the screen store, once per process.

## Stability

One full invocation of the benchmark: two whole runs back to back (75.6 and 75.7 s), with a load average of about 2.3 to 2.8 (the one-minute readings at the start and end of the runs were 2.3 to 3.0). That is a little busier than Phase 3 (1.9 to 2.6) and Phase 2 (1.5 to 2.3). Power was AC, on the main checkout.

- Between the two runs, the median spread is 0.5% across 49 metrics and the largest is 2.3% (P6 screen hot 17-plot batch; P6 screen process-cold is next at 2.2%). No metric exceeds 10%. Phase 3 had 1.0% and 3.6%, and Phase 2 had 0.3% and 1.4%.
- Between the individual hot children of a path (23 hot metrics, 4 children each), the median spread is 1.3% and the largest is 4.6% (P6 screen hot batch). The next largest is 2.8%, the P4B adversarial batch. No metric exceeds 10%.
- The hot p95 is within 10% of its median for the batch timings of every path and workload in this run, including the hash-every-call variants.
- The cost-estimate inputs are recorded in the artifact (`cost_inputs`): registry 1.90 µs, original 84.51, new polygon 16.15, all pooled hot medians on the 17 supplied plots (P5 decision with the precomputed hash, P0, P4). The 500 synthetic polygons give 21.73 µs for new polygons; it is recorded beside the others and not used.
- The artifact embeds only this invocation. The earlier cross-invocation comparison is no longer embedded, so it is not quoted here.

## Cost estimate refresh

Ran `.venv-data/bin/python -B -m engine.decision_scale --read-timing --cost` and rewrote [`cost-v1.json`](../../artifacts/decision/cost-v1.json). `--cost` now reads the per-plot inputs from `benchmark-v1.json` (`cost_inputs`) and the original-layers tile read time from [`tile-read-v1.json`](../../artifacts/decision/tile-read-v1.json), so the model cannot drift from the measurements. Re-checking 10 million registered plots over the tropical belt (measured-tile basis):

| Representation | Compute, Phase 1 | Compute, Phase 2 | Lambda USD, Phase 1 | Lambda USD, Phase 2 |
| --- | --- | --- | --- | --- |
| Original layers | 1,069 s | 1,058 s | 0.0178 | 0.0177 |
| L1 screen registry | 58.0 s | 56.1 s | 0.0010 | 0.0010 |
| L2 decision registry | 51.4 s | 49.5 s | 0.0009 | 0.0009 |
| L2 decision, new polygons | 314 s | 193 s | 0.0053 | 0.0032 |

The registry lines barely move. The new-polygon line drops by 38% in time (and in cost) because the scalar scan made selection plus reduction cheaper.

Phase 3, same basis. The cost column is the Phase 3 total (Lambda plus GET requests):

| Representation | Compute, Phase 2 | Compute, Phase 3 | Cost, Phase 3 |
| --- | --- | --- | --- |
| Original layers | 1,058 s | 1,058 s | 0.020 |
| L1 screen registry | 56.1 s | 49.3 s | 0.0009 |
| L2 decision registry | 49.5 s | 42.7 s | 0.0008 |
| L2 decision, new polygons | 193 s | 184 s | 0.0031 |

The registry lines drop by about 14% in time because the shared reducer is faster. The original-layers line is unchanged. New polygons drop by about 5%.

Phase 4, same basis. The cost column is the Phase 4 total (Lambda plus GET requests). The cost line is unchanged:

| Representation | Compute, Phase 3 | Compute, Phase 4 | Cost, Phase 4 |
| --- | --- | --- | --- |
| Original layers | 1,058 s | 1,054 s | 0.020 |
| L1 screen registry | 49.3 s | 49.0 s | 0.0009 |
| L2 decision registry | 42.7 s | 42.4 s | 0.0008 |
| L2 decision, new polygons | 184 s | 185 s | 0.0031 |

Every line is within 1% of Phase 3. The new-polygon line is priced on P4 for the 17 plots (16.15 µs), which did not change, so its cost stays at $0.0031.

Phase 4 moved the inputs by under 1%, to 84.51, 1.90 and 16.15 µs. Phase 3 had moved them to 84.92, 1.93 and 16.1 µs (original, registry, new polygon); the tables above show the effect. Before that, the per-plot inputs changed from 94.0, 3.0 (a placeholder) and 67.1 µs to the measured 84.91, 2.61 and 17.0 in Phase 2. They were 85.98, 2.80 and 29.09 after Phase 1, and 85.36, 3.55 and 38.94 at the start. The registry placeholder was 15% too low. The plan's new-polygon figure was too high: selection plus reduction now measures at 17.0 µs per plot, 75% below the plan's 67.1. The tile-read part of the original-layers row also changed: 209 s (2.091 s per tile, 100 tiles, one process) replaces 710 s, which was the sum of strip-read times across 8 workers (7.1 s per tile). The L1 and L2 decode parts are unchanged (30 s and 23 s). The descriptive labels in `cost-v1.json` now derive from the parameters, and each per-plot input names its source in `benchmark-v1.json`.

## Caveats

- P0 answers a bigger question than P1 to P6 (it also returns the canopy histogram), so it is not a like-for-like baseline. P1 is, and it is slower than P0 (1.86 against 1.44 ms hot), so speedups against P1 are larger.
- Representation alone buys little hot speed (1.6× against P1) because both paths pay for polygon selection. The large hot gains come from the registry and the table, which exist only for registered plots. A new or changed polygon takes the P3 or P4 path.
- Fast selection is exact (equal to `select_cells` on every polygon checked here, including 58,896 polygon and grid cases against a verbatim copy of the old code) but not equally faster everywhere: about 4× faster on the 17 plots and the 500 synthetic polygons, only 1.92× on the boundary-heavy adversarial set (1.92× after Phase 3, 1.88× after Phase 2, 1.16× after Phase 1, 0.81× at the start). After the Phase 4 scan-rule change the differential check against `select_cells` was re-run on 14,500 polygons with no mismatch in cells, dtype, exception type or message. The batch evaluator was compared with the single path on about 185,000 cases with no mismatch, and it is only a gain when a batch is in hand.
- The numpy-free re-check (P5L) does not check the decoded raster's `codes_sha256`, because that needs a full decode. The benchmark pins the store file's sha256, which closes the gap; a caller that does not pin it gets every other check but not that one. About 118,000 corrupted store blobs were all rejected with `ValueError`.
- Nothing is disk-cold. The OS file cache is warm and uncontrolled, and network or object-store latency is out of scope.
- One Apple M5 laptop with other processes running (this re-run was on AC power with low-power mode off; the Phase 1 re-run was on battery), a small 1233 × 604 cell chip and 17 real plots. Differences under the reported spread (about 0.5% typical, up to 2.3% between runs) are not findings, and nothing here says how a whole tile or a larger fleet behaves.
- End-to-end numbers assume bytecode caches. The benchmark compiles the engine modules before timing (gitignored `__pycache__`; children run with `-B` and only read). Without caches, start-up compiles each module, for example 2.7 ms for `decision_store.py`, 4.0 ms for `decision_index.py`, 2.1 ms for `decision_batch.py` and 1.3 ms for `decision_lite.py`. The larger new modules are hit hardest.
- The P6 end-to-end figure includes about 5.4 ms of this harness's own imports (JSON, hashlib, pathlib) above bare `python -c pass`. Net of that harness floor, P6 decision costs 1.5 ms; the artifact breaks out 1.15 ms of imports, 0.24 ms of load and 0.01 ms of query inside the child. Quote P6 as interpreter start-up plus about 1.5 ms. The same applies to P5L decision: 24.9 ms end-to-end is interpreter start-up, the harness floor and 4.8 ms of its own work.
- W3 is synthetic and its shapes are my assumption. Outputs are mapped observations, never legal compliance findings.
