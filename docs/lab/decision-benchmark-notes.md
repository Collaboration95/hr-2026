# Decision-layer benchmark (draft, 15 Oct 2026)

Updated after the evening perf pass (see the [decision-layer report](decision-layer-report.md#perf-pass-15-oct-evening)): the figures below are the re-run. The retained path P0 and the answer table P6 are unchanged within noise.

Draft section for the main agent to integrate. Code: [`engine/decision_benchmark.py`](../../engine/decision_benchmark.py). Result: [`benchmark-v1.json`](../../artifacts/decision/benchmark-v1.json) (raw samples, summaries, decomposition, binding checks). Rerun with `.venv-data/bin/python -B -m engine.decision_benchmark` (about 2.5 minutes; `--quick` is a 6-second smoke test that writes to the temp directory).

It copies the retained harness (`engine/benchmark.py`): every path runs in its own fresh child with one thread, nearest-rank p95, no disk-cache control. Before anything is timed, the parent checks that original layers, both stores, fast selection, the registry and the table give identical answers, and every timed child returns an answer digest that must match.

## Headline: the 17 supplied plots

Median, with p95 in brackets. Pooled over 2 whole runs. Each run uses 2 fresh hot children per path, plus 21 process-cold and 21 end-to-end children per path.

| Path | Hot, 17-plot batch, ms | Process-cold, ms | End-to-end fresh process, ms | Peak RSS, MB | Bytes read | Arrays held, B |
| --- | --- | --- | --- | --- | --- | --- |
| P0 original v1 (3 Hansen bands) | 1.462 (1.66) | 11.28 (11.6) | 116.7 (121.1) | 74.8 | 585,293 | 4,468,392 |
| P1 original layers, screen | 2.021 (2.42) | 19.33 (21.0) | 126.0 (146.4) | 97.1 | 642,946 | 17,836,902 |
| P1 original layers, decision | 1.877 (2.09) | 19.22 (22.6) | 126.4 (141.6) | 97.1 | 642,946 | 17,836,902 |
| P2 screen store | 1.223 (1.33) | 3.97 (4.2) | 59.8 (67.7) | 41.3 | 38,513 | 744,732 |
| P3 decision store | 1.201 (1.29) | 2.72 (2.9) | 58.2 (68.9) | 40.1 | 6,146 | 744,732 |
| P4 decision store, fast selection | 0.494 (0.53) | 1.87 (2.0) | 57.5 (73.5) | 40.0 | 6,146 | 744,732 |
| P5 screen registry | 0.0628 (0.0657) | 2.55 (2.6) | 51.4 (53.9) | 37.7 | 42,609 | 748,924 |
| P5 decision registry | 0.0476 (0.0496) | 1.31 (1.4) | 50.0 (52.7) | 36.5 | 10,242 | 748,924 |
| P6 screen table | 0.0035 (0.0037) | 0.25 (0.27) | 22.0 (23.2) | 20.6 | 20,650 | 0 |
| P6 decision table | 0.0034 (0.0036) | 0.25 (0.26) | 21.5 (23.2) | 20.6 | 20,650 | 0 |

Definitions:

- P0 is `load_source` plus `engine.query.evaluate`. It answers a bigger question: it also returns the 101-bin canopy histogram and the full loss-year histogram.
- P1 is `load_source`, `load_jrc` and `evaluate_original`. This is the apples-to-apples baseline: the same EUDR question from the original layers.
- P2 and P3 are `read_store` plus `evaluate_codes`. P4 swaps in `fast_select_cells`. P5 is the store plus `load_registry` plus `registry_evaluate`, which checks the store's level and grid on every call. P6 is `load_table` plus `table_lookup`, stdlib only. P5 and P6 answer registered plots only.
- Hot batch is the wall time of one pass over the 17 plots after loading and warmups (50 to 100 warmups, 500 to 1,000 measured batches per child). Per plot it is the batch divided by 17: P0 86.0 µs, P1 decision 110.4, P3 70.7, P4 29.1, P5 decision 2.80, P6 decision 0.20.
- Process-cold is the retained definition: a fresh child, timed full load plus one 17-plot batch, after imports and geometry read. The OS file cache is warm and not controlled.
- End-to-end is the parent's wall time for a fresh `python -B` that imports only what its path needs, reads the request on stdin, loads, answers the 17 plots and prints the digest. It includes interpreter start-up and imports. Measured floors on the same machine: `python -B -c pass` is 14.8 ms and the harness no-op is 20.3 ms. Net of `-c pass`, the paths cost 102.0 (P0), 111.6 (P1 decision), 43.4 (P3), 35.2 (P5 decision) and 6.7 ms (P6 decision).
- Peak RSS is the child's lifetime high-water mark (`rss_record`) from the process-cold children. Arrays held is the `nbytes` of the loaded arrays. The table path holds no arrays; its parsed table is 67,004 bytes of Python objects.
- Bytes read are the files the loader opens, taken from the files. The table file holds both levels, so P6 reads 20,650 bytes either way.

## What each step is worth

Speedup is the slower path's median divided by the faster path's. Same questions and same machine, so only the lever changes.

| Step (decision level) | Hot, 17 plots | Hot, 500 synthetic | Process-cold | End-to-end |
| --- | --- | --- | --- | --- |
| Representation, P1 to P3: derived codes instead of original layers, same selection | 1.56× | 1.45× | 7.06× | 2.17× |
| Selection algorithm, P3 to P4: `fast_select_cells` instead of `select_cells` | 2.43× | 2.66× | 1.46× | 1.01× |
| Registry index, P3 to P5: precomputed cells instead of selection | 25.2× | not applicable | 2.08× | 1.16× |
| Table, P5 to P6: stored outputs instead of a bincount and reduction | 13.9× | not applicable | 5.19× | 2.33× |
| Total, P1 to P6 | 549× | not applicable | 76× | 5.89× |
| Total, P0 to P6 | 428× | not applicable | 45× | 5.4× |

The screen level gives the same shape: P1 to P2 1.65× hot and 4.9× cold, P2 to P5 19.5× hot, P5 to P6 17.7× hot, P1 to P6 571× hot.

- The representation step lumps two things: the stored per-cell codes replace the float affine lookup of two layers, and the reduction becomes one bincount over 20 codes.
- Fast selection is faster than `select_cells` only on ordinary shapes. On 100 adversarial boundary polygons (aligned edges, vertices on cell centres, slivers, lattices; from the test fuzz generator) P4 takes 42.7 µs per polygon against 49.7 for P3, a 1.16× speedup (it was 0.81×, slower, before the perf pass), because many centres still go to exact GEOS.
- Most end-to-end time is imports. P0 and P1 spend about 75 ms importing numpy, shapely and rasterio. P3 and P4 spend 30 ms (no rasterio). P5 spends 24 ms (no shapely). P6 spends 0.85 ms (stdlib only). The perf pass changed none of this, which is why end-to-end barely moved: P5 decision went from 52.4 to 50.0 ms end-to-end while its load + query went from 3.5 to 1.3 ms.
- The registry adds about 0.17 ms of load (1.23 ms against 1.06 ms for the store alone) and saves about 1.6 ms of query, so P5 process-cold is 1.31 ms against 2.72 ms for P3.

## New polygons

Throughput on 500 synthetic plot-like polygons (W3), one core, hot. These are seeded random concave shapes, 0.5 to 20 ha, 15% with a hole, centred on land, between 5 and 267 cells each (median 36). They are not company data.

| Path | µs per polygon, median (p95) | Polygons per second |
| --- | --- | --- |
| P0 original v1 | 110.4 (120.0) | 9,100 |
| P1 original layers, decision | 135.3 (140.9) | 7,400 |
| P2 screen store | 95.9 (105.7) | 10,400 |
| P3 decision store | 93.4 (97.3) | 10,700 |
| P4 fast selection | 35.1 (37.0) | 28,500 |

Registered-plot key, hot, per plot:

| Path | Geometry hash precomputed | Geometry hashed on every call |
| --- | --- | --- |
| P5 decision registry | 2.80 µs | 7.03 µs |
| P6 decision table | 0.20 µs | 3.66 µs |

The realistic registered-plot workflow is the precomputed key. A plot is registered once, its geometry hash is stored with it, and queries arrive by plot ID. Hashing the geometry on every call is what a service does when a client re-sends the polygon and the service wants to confirm it is unchanged. It costs about 3.5 µs per plot (canonical JSON plus SHA-256) and makes the table about 18× slower than the precomputed key. The table needs the layer version (store SHA-256) as an input. Verifying it by hashing the store file costs 12 µs for the decision store and 23 µs for the screen store, once per process.

## Stability

One full invocation of the benchmark: two whole runs back to back (73.1 and 71.9 s), with the one-minute load average between 1.7 and 2.9 at the start and end of both.

- Between the two runs, the median spread is 0.9% across 38 metrics and the largest is 2.9% (P4 process-cold). No metric exceeds 10%.
- Between the individual hot children of a path (18 hot metrics, 4 children each), the median spread is 1.7% and the largest is 4.9%, the P6 decision hot batch (3.4 µs for 17 plots). The next largest is the P6 screen hot batch at 4.7%. No metric exceeds 10%.
- The hot p95 is within 10% of its median for every decision-layer path (P2 to P6). It is 11% to 20% above for the three original-layer paths (P0, P1 screen, P1 decision).
- The cost-estimate inputs are recorded in the artifact (`cost_inputs`): registry 2.80 µs, original 85.98, new polygon 29.09, all pooled hot medians on the 17 supplied plots (P5 decision with the precomputed hash, P0, P4). The 500 synthetic polygons give 35.11 µs for new polygons; it is recorded beside the others and not used.
- The artifact embeds only this invocation. The earlier cross-invocation comparison is no longer embedded, so it is not quoted here.

## Cost estimate refresh

Ran `.venv-data/bin/python -B -m engine.decision_scale --read-timing --cost` and rewrote [`cost-v1.json`](../../artifacts/decision/cost-v1.json). `--cost` now reads the per-plot inputs from `benchmark-v1.json` (`cost_inputs`) and the original-layers tile read time from [`tile-read-v1.json`](../../artifacts/decision/tile-read-v1.json), so the model cannot drift from the measurements. Re-checking 10 million registered plots over the tropical belt (measured-tile basis):

| Representation | Compute before | Compute now | Lambda USD before | Lambda USD now |
| --- | --- | --- | --- | --- |
| Original layers | 1,650 s | 1,069 s | 0.0275 | 0.0178 |
| L1 screen registry | 60.0 s | 58.0 s | 0.0010 | 0.0010 |
| L2 decision registry | 53.4 s | 51.4 s | 0.0009 | 0.0009 |
| L2 decision, new polygons | 694 s | 314 s | 0.0116 | 0.0053 |

The per-plot inputs changed from 94.0, 3.0 (a placeholder) and 67.1 µs to the measured 85.98, 2.80 and 29.09 (they were 85.36, 3.55 and 38.94 before the evening perf pass; "Compute now" is after it). The registry placeholder was 15% too low. The plan's new-polygon figure was too high: selection plus reduction measures at 29.1 µs per plot, 57% below the plan's 67.1. The tile-read part of the original-layers row also changed: 209 s (2.091 s per tile, 100 tiles, one process) replaces 710 s, which was the sum of strip-read times across 8 workers (7.1 s per tile). The L1 and L2 decode parts are unchanged (30 s and 23 s). The descriptive labels in `cost-v1.json` now derive from the parameters, and each per-plot input names its source in `benchmark-v1.json`.

## Caveats

- P0 answers a bigger question than P1 to P6 (it also returns the canopy histogram), so it is not a like-for-like baseline. P1 is, and it is slower than P0 (1.88 against 1.46 ms hot), so speedups against P1 are larger.
- Representation alone buys little hot speed (1.6× against P1) because both paths pay for polygon selection. The large hot gains come from the registry and the table, which exist only for registered plots. A new or changed polygon takes the P3 or P4 path.
- Fast selection is exact (equal to `select_cells` on every polygon checked here) but not much faster everywhere: about 2.4 to 2.7× faster on the 17 plots and the 500 synthetic polygons, only 1.16× on the boundary-heavy adversarial set (0.81× before the perf pass).
- Nothing is disk-cold. The OS file cache is warm and uncontrolled, and network or object-store latency is out of scope.
- One Apple M5 laptop with other processes running (the evening re-run was on battery power with low-power mode off; the first run was on AC), a small 1233 × 604 cell chip and 17 real plots. Differences under the reported spread (about 1% typical, up to 3% between runs) are not findings, and nothing here says how a whole tile or a larger fleet behaves.
- End-to-end numbers assume bytecode caches. The benchmark compiles the engine modules before timing (gitignored `__pycache__`; children run with `-B` and only read). Without caches, start-up compiles each module, for example 3.4 ms for `decision_store.py` and 2.9 ms for `decision_index.py`.
- The P6 end-to-end figure includes about 5.5 ms of this harness's own imports (JSON, hashlib, pathlib) above bare `python -c pass`. Net of that harness floor, P6 decision costs 1.2 ms; the artifact breaks out 0.85 ms of imports, 0.24 ms of load and 0.01 ms of query inside the child. Quote P6 as interpreter start-up plus about 1.2 ms.
- W3 is synthetic and its shapes are my assumption. Outputs are mapped observations, never legal compliance findings.
