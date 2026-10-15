# Decision-layer benchmark (draft, 15 Oct 2026)

Updated after the night perf pass (see the [decision-layer report](decision-layer-report.md#second-perf-pass-15-oct-night); the earlier [evening pass](decision-layer-report.md#perf-pass-15-oct-evening) is history): the figures below are the re-run. The retained path P0 and the answer table P6 are unchanged within noise. Three new paths were added: P4B (batch evaluator), P5Ls and P5Ld (numpy-free registered-plot re-check).

Draft section for the main agent to integrate. Code: [`engine/decision_benchmark.py`](../../engine/decision_benchmark.py). Result: [`benchmark-v1.json`](../../artifacts/decision/benchmark-v1.json) (raw samples, summaries, decomposition, binding checks). Rerun with `.venv-data/bin/python -B -m engine.decision_benchmark` (about 2.6 minutes; `--quick` is a 6-second smoke test that writes to the temp directory).

It copies the retained harness (`engine/benchmark.py`): every path runs in its own fresh child with one thread, nearest-rank p95, no disk-cache control. Before anything is timed, the parent checks that original layers, both stores, fast selection, the one-call batch evaluator, the registry, the numpy-free re-check and the table give identical answers, and every timed child returns an answer digest that must match.

## Headline: the 17 supplied plots

Median, with p95 in brackets. Pooled over 2 whole runs. Each run uses 2 fresh hot children per path, plus 21 process-cold and 21 end-to-end children per path.

| Path | Hot, 17-plot batch, ms | Process-cold, ms | End-to-end fresh process, ms | Peak RSS, MB | Bytes read | Arrays held, B |
| --- | --- | --- | --- | --- | --- | --- |
| P0 original v1 (3 Hansen bands) | 1.443 (1.54) | 11.14 (11.7) | 114.0 (116.8) | 74.8 | 585,293 | 4,468,392 |
| P1 original layers, screen | 2.008 (2.11) | 19.15 (19.7) | 124.3 (126.7) | 97.2 | 642,946 | 17,836,902 |
| P1 original layers, decision | 1.860 (1.94) | 19.03 (19.7) | 124.6 (127.2) | 97.2 | 642,946 | 17,836,902 |
| P2 screen store | 1.211 (1.27) | 3.91 (4.1) | 58.4 (60.4) | 41.3 | 38,513 | 744,732 |
| P3 decision store | 1.194 (1.26) | 2.71 (2.8) | 56.9 (58.2) | 40.2 | 6,146 | 744,732 |
| P4 decision store, fast selection | 0.289 (0.313) | 1.55 (1.6) | 56.5 (58.4) | 39.9 | 6,146 | 744,732 |
| P4B decision store, batch evaluator | 0.241 (0.257) | 3.64 (3.8) | 59.1 (61.0) | 41.6 | 6,146 | 744,732 |
| P5 screen registry | 0.0592 (0.0642) | 2.53 (2.6) | 50.9 (53.6) | 37.8 | 42,609 | 748,924 |
| P5 decision registry | 0.0443 (0.0469) | 1.29 (1.3) | 49.7 (51.2) | 36.7 | 10,242 | 748,924 |
| P5L screen registry, numpy-free | 0.0480 (0.0518) | 2.67 (2.8) | 26.6 (27.6) | 23.4 | 42,609 | 1,048 |
| P5L decision registry, numpy-free | 0.0328 (0.0367) | 1.03 (1.1) | 24.6 (25.9) | 22.9 | 10,242 | 1,048 |
| P6 screen table | 0.0036 (0.0038) | 0.247 (0.26) | 21.3 (22.6) | 20.7 | 20,650 | 0 |
| P6 decision table | 0.0035 (0.0036) | 0.243 (0.26) | 21.3 (22.2) | 20.7 | 20,650 | 0 |

Definitions:

- P0 is `load_source` plus `engine.query.evaluate`. It answers a bigger question: it also returns the 101-bin canopy histogram and the full loss-year histogram.
- P1 is `load_source`, `load_jrc` and `evaluate_original`. This is the apples-to-apples baseline: the same EUDR question from the original layers.
- P2 and P3 are `read_store` plus `evaluate_codes`. P4 swaps in `fast_select_cells`, which now scans small windows in pure Python and builds the histogram straight from runs of selected centres (so P4 also has a fused reduction). P4B answers the whole workload in one `evaluate_many` call. P5 is the store plus `load_registry` plus `registry_evaluate`, which checks the store's level and grid on every call. P5L is the numpy-free version of P5 (`engine/decision_lite.py`): it validates the store and registry with the standard library only and decodes codes just at the registered cells from the packed bit-planes and sparse loss events. It does not check the decoded raster's `codes_sha256` (that would need a full decode); the request pins the store file's sha256 instead, as it does for the table. P6 is `load_table` plus `table_lookup`, stdlib only. P5, P5L and P6 answer registered plots only.
- Hot batch is the wall time of one pass over the 17 plots after loading and warmups (50 to 100 warmups, 500 to 1,000 measured batches per child). Per plot it is the batch divided by 17: P0 84.9 µs, P1 decision 109.4, P3 70.3, P4 17.0, P4B 14.2, P5 decision 2.61, P5L decision 1.93, P6 decision 0.20.
- Process-cold is the retained definition: a fresh child, timed full load plus one 17-plot batch, after imports and geometry read. The OS file cache is warm and not controlled.
- End-to-end is the parent's wall time for a fresh `python -B` that imports only what its path needs, reads the request on stdin, loads, answers the 17 plots and prints the digest. It includes interpreter start-up and imports. Measured floors on the same machine: `python -B -c pass` is 14.3 ms and the harness no-op is 19.7 ms. Net of `-c pass`, the paths cost 99.6 (P0), 110.2 (P1 decision), 42.5 (P3), 42.2 (P4), 44.7 (P4B), 35.4 (P5 decision), 10.3 (P5L decision) and 6.9 ms (P6 decision).
- Peak RSS is the child's lifetime high-water mark (`rss_record`) from the process-cold children. Arrays held is the `nbytes` of the loaded arrays. The table path holds no arrays; its parsed table is 67,004 bytes of Python objects.
- Bytes read are the files the loader opens, taken from the files. The table file holds both levels, so P6 reads 20,650 bytes either way.

## What each step is worth

Speedup is the slower path's median divided by the faster path's. Same questions and same machine, so only the lever changes.

| Step (decision level) | Hot, 17 plots | Hot, 500 synthetic | Process-cold | End-to-end |
| --- | --- | --- | --- | --- |
| Representation, P1 to P3: derived codes instead of original layers, same selection | 1.56× | 1.44× | 7.02× | 2.19× |
| Selection, P3 to P4: `fast_select_cells` (scalar scan and fused reduction) instead of `select_cells` | 4.13× | 3.88× | 1.75× | 1.01× |
| Batch, P4 to P4B: one vectorized pass for the whole workload | 1.20× | 3.05× | 0.43× (slower) | 0.96× |
| Registry index, P3 to P5: precomputed cells instead of selection | 26.9× | not applicable | 2.10× | 1.14× |
| No numpy, P5 to P5L: standard library only, packed planes | 1.35× | not applicable | 1.26× | 2.02× |
| Table, P5 to P6: stored outputs instead of a bincount and reduction | 12.8× | not applicable | 5.33× | 2.34× |
| Total, P1 to P6 | 538× | not applicable | 78× | 5.86× |
| Total, P0 to P6 | 417× | not applicable | 45.9× | 5.36× |

The screen level gives the same shape: P1 to P2 1.66× hot and 4.9× cold, P2 to P5 20.5× hot, P5 to P5L 1.23× hot and 1.91× end-to-end, P5 to P6 16.5× hot, P1 to P6 561× hot.

- The representation step lumps two things: the stored per-cell codes replace the float affine lookup of two layers, and the reduction becomes one bincount over 20 codes.
- Fast selection is much faster than `select_cells` on ordinary shapes and less so on boundary-heavy ones. On 100 adversarial boundary polygons (aligned edges, vertices on cell centres, slivers, lattices; from the test fuzz generator) P4 takes 25.9 µs per polygon against 48.7 for P3, a 1.88× speedup (it was 1.16× after the evening pass and 0.81×, slower, before it), because many centres still go to exact GEOS. P4B takes 9.0 µs there. "P3 to P4 is only the selection algorithm" is no longer exactly true: P4 also uses a fused reduction.
- P4B needs a batch in hand. Below `MIN_BATCH` = 4 it just loops over the single path, so one new plot gains nothing. On the 17-plot batch it is only 1.2× ahead of P4 (14.2 against 17.0 µs per plot), because the fixed per-call cost of its NumPy and shapely passes is spread over few plots. From a cold start it is slower than P4 (3.64 against 1.55 ms), because the first call warms NumPy and shapely. The gain shows on the 500-polygon batch (3.05×).
- Most end-to-end time is imports. P0 and P1 spend about 73 ms importing numpy, shapely and rasterio. P3, P4 and P4B spend 30 ms (no rasterio). P5 spends 24 ms (no shapely). P5L spends 3.4 ms (stdlib only, no numpy). P6 spends 1.15 ms (stdlib only). The evening pass changed none of this, which is why end-to-end barely moved then: P5 decision went from 52.4 to 50.0 ms while its load + query went from 3.5 to 1.3 ms. P5L is the exception: dropping `import numpy` takes the registered re-check from 49.7 to 24.6 ms end-to-end (2.0×; 4.6× against P0). What is left is interpreter start-up plus the harness floor. Net of the 19.7 ms harness floor, P5L decision costs 4.9 ms: 3.4 ms of imports, 0.9 ms of load and 0.05 ms of query.
- The registry adds about 0.17 ms of load (1.22 ms against 1.05 ms for the store alone) and saves about 1.6 ms of query, so P5 process-cold is 1.29 ms against 2.71 ms for P3. P5L loads in 0.97 ms because it reads and validates the store without building arrays, so its process-cold time is 1.03 ms.

## New polygons

Throughput on 500 synthetic plot-like polygons (W3), one core, hot. These are seeded random concave shapes, 0.5 to 20 ha, 15% with a hole, centred on land, between 5 and 267 cells each (median 36). They are not company data.

| Path | µs per polygon, median (p95) | Polygons per second |
| --- | --- | --- |
| P0 original v1 | 109.2 (113.4) | 9,160 |
| P1 original layers, decision | 133.3 (137.3) | 7,500 |
| P2 screen store | 93.8 (97.9) | 10,700 |
| P3 decision store | 92.4 (95.9) | 10,800 |
| P4 fast selection | 23.8 (24.6) | 42,000 |
| P4B batch evaluator (whole 500 in one call) | 7.81 (8.27) | 128,000 |

P4 is 4.6× the original path and P4B is 14× (3.05× over P4). P4B's per-polygon figure is the batch time divided by 500, so it needs the batch in hand.

On the 100 adversarial polygons (W4, P3, P4 and P4B only): P3 48.7 µs (52.3), P4 25.9 (27.0), P4B 9.0 (9.8).

Registered-plot key, hot, per plot:

| Path | Geometry hash precomputed | Geometry hashed on every call |
| --- | --- | --- |
| P5 decision registry | 2.61 µs | 6.78 µs |
| P5L decision registry, numpy-free | 1.93 µs | 5.61 µs |
| P6 decision table | 0.20 µs | 3.66 µs |

The realistic registered-plot workflow is the precomputed key. A plot is registered once, its geometry hash is stored with it, and queries arrive by plot ID. Hashing the geometry on every call is what a service does when a client re-sends the polygon and the service wants to confirm it is unchanged. It costs about 3.5 µs per plot (canonical JSON plus SHA-256) and makes the table about 18× slower than the precomputed key. The table needs the layer version (store SHA-256) as an input. Verifying it by hashing the store file costs 12 µs for the decision store and 21 µs for the screen store, once per process.

## Stability

One full invocation of the benchmark: two whole runs back to back (76.6 and 76.4 s), with the one-minute load average between 1.5 and 2.3 at the start and end of both. Power was AC.

- Between the two runs, the median spread is 0.3% across 49 metrics and the largest is 1.4% (P3 hot 17-plot batch; P4 process-cold is next at 1.4%). No metric exceeds 10%.
- Between the individual hot children of a path (23 hot metrics, 4 children each), the median spread is 1.3% and the largest is 5.2%, the P3 hot batch on the adversarial set. The next largest is 3.7%, the P5 decision hot batch. No metric exceeds 10%.
- The hot p95 is within 10% of its median for the batch timings of every path except P5L decision (12% above on the 17-plot batch). The original-layer paths, which were 11% to 20% above in the earlier runs, are now within 7%. The hash-every-call variants are looser for two paths: P5L decision 25% and P6 screen 20%.
- The cost-estimate inputs are recorded in the artifact (`cost_inputs`): registry 2.61 µs, original 84.91, new polygon 17.0, all pooled hot medians on the 17 supplied plots (P5 decision with the precomputed hash, P0, P4). The 500 synthetic polygons give 23.81 µs for new polygons; it is recorded beside the others and not used.
- The artifact embeds only this invocation. The earlier cross-invocation comparison is no longer embedded, so it is not quoted here.

## Cost estimate refresh

Ran `.venv-data/bin/python -B -m engine.decision_scale --read-timing --cost` and rewrote [`cost-v1.json`](../../artifacts/decision/cost-v1.json). `--cost` now reads the per-plot inputs from `benchmark-v1.json` (`cost_inputs`) and the original-layers tile read time from [`tile-read-v1.json`](../../artifacts/decision/tile-read-v1.json), so the model cannot drift from the measurements. Re-checking 10 million registered plots over the tropical belt (measured-tile basis):

| Representation | Compute before | Compute now | Lambda USD before | Lambda USD now |
| --- | --- | --- | --- | --- |
| Original layers | 1,069 s | 1,058 s | 0.0178 | 0.0177 |
| L1 screen registry | 58.0 s | 56.1 s | 0.0010 | 0.0010 |
| L2 decision registry | 51.4 s | 49.5 s | 0.0009 | 0.0009 |
| L2 decision, new polygons | 314 s | 193 s | 0.0053 | 0.0032 |

"Before" is the evening perf pass; "now" is the night pass. The registry lines barely move. The new-polygon line drops by 38% in time (and in cost) because the scalar scan made selection plus reduction cheaper.

The per-plot inputs changed from 94.0, 3.0 (a placeholder) and 67.1 µs to the measured 84.91, 2.61 and 17.0 (they were 85.98, 2.80 and 29.09 after the evening perf pass, and 85.36, 3.55 and 38.94 before it). The registry placeholder was 15% too low. The plan's new-polygon figure was too high: selection plus reduction now measures at 17.0 µs per plot, 75% below the plan's 67.1. The tile-read part of the original-layers row also changed: 209 s (2.091 s per tile, 100 tiles, one process) replaces 710 s, which was the sum of strip-read times across 8 workers (7.1 s per tile). The L1 and L2 decode parts are unchanged (30 s and 23 s). The descriptive labels in `cost-v1.json` now derive from the parameters, and each per-plot input names its source in `benchmark-v1.json`.

## Caveats

- P0 answers a bigger question than P1 to P6 (it also returns the canopy histogram), so it is not a like-for-like baseline. P1 is, and it is slower than P0 (1.86 against 1.44 ms hot), so speedups against P1 are larger.
- Representation alone buys little hot speed (1.6× against P1) because both paths pay for polygon selection. The large hot gains come from the registry and the table, which exist only for registered plots. A new or changed polygon takes the P3 or P4 path.
- Fast selection is exact (equal to `select_cells` on every polygon checked here, including 58,896 polygon and grid cases against a verbatim copy of the old code) but not equally faster everywhere: about 4× faster on the 17 plots and the 500 synthetic polygons, only 1.88× on the boundary-heavy adversarial set (1.16× after the evening pass, 0.81× before it). The batch evaluator was compared with the single path on about 185,000 cases with no mismatch, and it is only a gain when a batch is in hand.
- The numpy-free re-check (P5L) does not check the decoded raster's `codes_sha256`, because that needs a full decode. The benchmark pins the store file's sha256, which closes the gap; a caller that does not pin it gets every other check but not that one. About 118,000 corrupted store blobs were all rejected with `ValueError`.
- Nothing is disk-cold. The OS file cache is warm and uncontrolled, and network or object-store latency is out of scope.
- One Apple M5 laptop with other processes running (this re-run was on AC power with low-power mode off; the evening re-run was on battery), a small 1233 × 604 cell chip and 17 real plots. Differences under the reported spread (about 0.3% typical, up to 1.4% between runs) are not findings, and nothing here says how a whole tile or a larger fleet behaves.
- End-to-end numbers assume bytecode caches. The benchmark compiles the engine modules before timing (gitignored `__pycache__`; children run with `-B` and only read). Without caches, start-up compiles each module, for example 2.7 ms for `decision_store.py`, 4.0 ms for `decision_index.py`, 2.1 ms for `decision_batch.py` and 1.3 ms for `decision_lite.py`. The larger new modules are hit hardest.
- The P6 end-to-end figure includes about 5.4 ms of this harness's own imports (JSON, hashlib, pathlib) above bare `python -c pass`. Net of that harness floor, P6 decision costs 1.5 ms; the artifact breaks out 1.15 ms of imports, 0.24 ms of load and 0.01 ms of query inside the child. Quote P6 as interpreter start-up plus about 1.5 ms. The same applies to P5L decision: 24.6 ms end-to-end is interpreter start-up, the harness floor and 4.9 ms of its own work.
- W3 is synthetic and its shapes are my assumption. Outputs are mapped observations, never legal compliance findings.
