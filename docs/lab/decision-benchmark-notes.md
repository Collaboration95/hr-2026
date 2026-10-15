# Decision-layer benchmark (draft, 15 Oct 2026)

Draft section for the main agent to integrate. Code: [`engine/decision_benchmark.py`](../../engine/decision_benchmark.py). Result: [`benchmark-v1.json`](../../artifacts/decision/benchmark-v1.json) (raw samples, summaries, decomposition, binding checks). Rerun with `.venv-data/bin/python -B -m engine.decision_benchmark` (about 2.5 minutes; `--quick` is a 6-second smoke test that writes to the temp directory).

It copies the retained harness (`engine/benchmark.py`): every path runs in its own fresh child with one thread, nearest-rank p95, no disk-cache control. Before anything is timed, the parent checks that original layers, both stores, fast selection, the registry and the table give identical answers, and every timed child returns an answer digest that must match.

## Headline: the 17 supplied plots

Median, with p95 in brackets. Pooled over 2 whole runs. Each run uses 2 fresh hot children per path, plus 21 process-cold and 21 end-to-end children per path.

| Path | Hot, 17-plot batch, ms | Process-cold, ms | End-to-end fresh process, ms | Peak RSS, MB | Bytes read | Arrays held, B |
| --- | --- | --- | --- | --- | --- | --- |
| P0 original v1 (3 Hansen bands) | 1.451 (1.55) | 11.26 (11.5) | 116.1 (120.3) | 74.7 | 585,293 | 4,468,392 |
| P1 original layers, screen | 2.019 (2.19) | 19.44 (20.1) | 125.4 (132.9) | 97.1 | 642,946 | 17,836,902 |
| P1 original layers, decision | 1.874 (1.96) | 19.28 (19.9) | 125.2 (131.7) | 97.1 | 642,946 | 17,836,902 |
| P2 screen store | 1.294 (1.40) | 6.37 (6.6) | 61.7 (65.7) | 47.5 | 38,513 | 744,732 |
| P3 decision store | 1.210 (1.31) | 4.92 (5.1) | 60.2 (64.2) | 46.3 | 6,146 | 744,732 |
| P4 decision store, fast selection | 0.662 (0.70) | 4.26 (4.4) | 59.4 (62.7) | 46.1 | 6,146 | 744,732 |
| P5 screen registry | 0.1062 (0.113) | 4.94 (5.2) | 53.7 (56.8) | 43.9 | 42,609 | 748,924 |
| P5 decision registry | 0.0604 (0.066) | 3.53 (3.7) | 52.4 (54.3) | 42.6 | 10,242 | 748,924 |
| P6 screen table | 0.0035 (0.0037) | 0.25 (0.27) | 21.8 (23.3) | 20.5 | 20,650 | 0 |
| P6 decision table | 0.0035 (0.0038) | 0.25 (0.26) | 21.5 (23.6) | 20.6 | 20,650 | 0 |

Definitions:

- P0 is `load_source` plus `engine.query.evaluate`. It answers a bigger question: it also returns the 101-bin canopy histogram and the full loss-year histogram.
- P1 is `load_source`, `load_jrc` and `evaluate_original`. This is the apples-to-apples baseline: the same EUDR question from the original layers.
- P2 and P3 are `read_store` plus `evaluate_codes`. P4 swaps in `fast_select_cells`. P5 is the store plus `load_registry` plus `registry_evaluate`, which now checks the store's level and grid on every call, so it is slightly slower than in the earlier run (3.55 µs per plot against 3.33). P6 is `load_table` plus `table_lookup`, stdlib only. P5 and P6 answer registered plots only.
- Hot batch is the wall time of one pass over the 17 plots after loading and warmups (50 to 100 warmups, 500 to 1,000 measured batches per child). Per plot it is the batch divided by 17: P0 85.4 µs, P1 decision 110.2, P3 71.2, P4 38.9, P5 decision 3.55, P6 decision 0.20.
- Process-cold is the retained definition: a fresh child, timed full load plus one 17-plot batch, after imports and geometry read. The OS file cache is warm and not controlled.
- End-to-end is the parent's wall time for a fresh `python -B` that imports only what its path needs, reads the request on stdin, loads, answers the 17 plots and prints the digest. It includes interpreter start-up and imports. Measured floors on the same machine: `python -B -c pass` is 14.7 ms and the harness no-op is 20.0 ms. Net of `-c pass`, the paths cost 101.4 (P0), 110.5 (P1 decision), 45.5 (P3), 37.6 (P5 decision) and 6.7 ms (P6 decision).
- Peak RSS is the child's lifetime high-water mark (`rss_record`) from the process-cold children. Arrays held is the `nbytes` of the loaded arrays. The table path holds no arrays; its parsed table is 67,004 bytes of Python objects.
- Bytes read are the files the loader opens, taken from the files. The table file holds both levels, so P6 reads 20,650 bytes either way.

## What each step is worth

Speedup is the slower path's median divided by the faster path's. Same questions and same machine, so only the lever changes.

| Step (decision level) | Hot, 17 plots | Hot, 500 synthetic | Process-cold | End-to-end |
| --- | --- | --- | --- | --- |
| Representation, P1 to P3: derived codes instead of original layers, same selection | 1.55× | 1.43× | 3.92× | 2.08× |
| Selection algorithm, P3 to P4: `fast_select_cells` instead of `select_cells` | 1.83× | 2.08× | 1.15× | 1.01× |
| Registry index, P3 to P5: precomputed cells instead of selection | 20.0× | not applicable | 1.39× | 1.15× |
| Table, P5 to P6: stored outputs instead of a bincount and reduction | 17.5× | not applicable | 14.0× | 2.44× |
| Total, P1 to P6 | 542× | not applicable | 77× | 5.84× |
| Total, P0 to P6 | 420× | not applicable | 45× | 5.4× |

The screen level gives the same shape: P1 to P2 1.56× hot and 3.1× cold, P2 to P5 12.2× hot, P5 to P6 30.3× hot, P1 to P6 577× hot.

- The representation step lumps two things: the stored per-cell codes replace the float affine lookup of two layers, and the reduction becomes one bincount over 20 codes.
- Fast selection is faster than `select_cells` only on ordinary shapes. On 100 adversarial boundary polygons (aligned edges, vertices on cell centres, slivers, lattices; from the test fuzz generator) P4 takes 63.2 µs per polygon against 51.1 for P3, a 0.81× speedup, because many centres go to exact GEOS.
- Most end-to-end time is imports. P0 and P1 spend about 74 ms importing numpy, shapely and rasterio. P3 and P4 spend 30 ms (no rasterio). P5 spends 24 ms (no shapely). P6 spends 0.85 ms (stdlib only).
- The registry adds about 0.18 ms of load (3.43 ms against 3.25 ms for the store alone) and saves about 1.6 ms of query, so P5 process-cold is 3.53 ms against 4.92 ms for P3.

## New polygons

Throughput on 500 synthetic plot-like polygons (W3), one core, hot. These are seeded random concave shapes, 0.5 to 20 ha, 15% with a hole, centred on land, between 5 and 267 cells each (median 36). They are not company data.

| Path | µs per polygon, median (p95) | Polygons per second |
| --- | --- | --- |
| P0 original v1 | 109.4 (119.9) | 9,100 |
| P1 original layers, decision | 134.6 (144.4) | 7,400 |
| P2 screen store | 99.0 (104.0) | 10,100 |
| P3 decision store | 94.0 (97.7) | 10,600 |
| P4 fast selection | 45.2 (47.0) | 22,100 |

Registered-plot key, hot, per plot:

| Path | Geometry hash precomputed | Geometry hashed on every call |
| --- | --- | --- |
| P5 decision registry | 3.55 µs | 7.72 µs |
| P6 decision table | 0.20 µs | 3.68 µs |

The realistic registered-plot workflow is the precomputed key. A plot is registered once, its geometry hash is stored with it, and queries arrive by plot ID. Hashing the geometry on every call is what a service does when a client re-sends the polygon and the service wants to confirm it is unchanged. It costs about 3.5 µs per plot (canonical JSON plus SHA-256) and makes the table 18× slower than the precomputed key. The table needs the layer version (store SHA-256) as an input. Verifying it by hashing the store file costs 12 µs for the decision store and 23 µs for the screen store, once per process.

## Stability

One full invocation of the benchmark: two whole runs back to back (74.0 and 72.9 s), with the one-minute load average between 2.1 and 2.5 at the start and end of both.

- Between the two runs, the median spread is 0.9% across 38 metrics and the largest is 4.8% (the P6 decision hot batch, 3.5 µs for 17 plots). No metric exceeds 10%.
- Between the individual hot children of a path (18 hot metrics, 4 children each), the median spread is 1.5% and the largest is 9.6%, again the P6 decision hot batch. The next largest is P3 on the adversarial set at 6.5%. No metric exceeds 10%.
- No hot p95 in the headline table is more than 10% above its median.
- The cost-estimate inputs are recorded in the artifact (`cost_inputs`): registry 3.55 µs, original 85.36, new polygon 38.94, all pooled hot medians on the 17 supplied plots (P5 decision with the precomputed hash, P0, P4). The 500 synthetic polygons give 45.21 µs for new polygons; it is recorded beside the others and not used.
- The artifact embeds only this invocation. The earlier cross-invocation comparison is no longer embedded, so it is not quoted here.

## Cost estimate refresh

Ran `.venv-data/bin/python -B -m engine.decision_scale --read-timing --cost` and rewrote [`cost-v1.json`](../../artifacts/decision/cost-v1.json). `--cost` now reads the per-plot inputs from `benchmark-v1.json` (`cost_inputs`) and the original-layers tile read time from [`tile-read-v1.json`](../../artifacts/decision/tile-read-v1.json), so the model cannot drift from the measurements. Re-checking 10 million registered plots over the tropical belt (measured-tile basis):

| Representation | Compute before | Compute now | Lambda USD before | Lambda USD now |
| --- | --- | --- | --- | --- |
| Original layers | 1,650 s | 1,063 s | 0.0275 | 0.0177 |
| L1 screen registry | 60.0 s | 65.5 s | 0.0010 | 0.0011 |
| L2 decision registry | 53.4 s | 58.9 s | 0.0009 | 0.0010 |
| L2 decision, new polygons | 694 s | 413 s | 0.0116 | 0.0069 |

The per-plot inputs changed from 94.0, 3.0 (a placeholder) and 67.1 µs to the measured 85.36, 3.55 and 38.94. The registry placeholder was 15% too low. The plan's new-polygon figure was too high: selection plus reduction measures at 38.9 µs per plot, 42% below the plan's 67.1. The tile-read part of the original-layers row also changed: 209 s (2.091 s per tile, 100 tiles, one process) replaces 710 s, which was the sum of strip-read times across 8 workers (7.1 s per tile). The L1 and L2 decode parts are unchanged (30 s and 23 s). The descriptive labels in `cost-v1.json` now derive from the parameters, and each per-plot input names its source in `benchmark-v1.json`.

## Caveats

- P0 answers a bigger question than P1 to P6 (it also returns the canopy histogram), so it is not a like-for-like baseline. P1 is, and it is slower than P0 (1.87 against 1.45 ms hot), so speedups against P1 are larger.
- Representation alone buys little hot speed (1.5× against P1) because both paths pay for polygon selection. The large hot gains come from the registry and the table, which exist only for registered plots. A new or changed polygon takes the P3 or P4 path.
- Fast selection is exact (equal to `select_cells` on every polygon checked here) but not always faster: about 1.8 to 2.1× faster on the 17 plots and the 500 synthetic polygons, 0.81× on the boundary-heavy adversarial set.
- Nothing is disk-cold. The OS file cache is warm and uncontrolled, and network or object-store latency is out of scope.
- One Apple M5 laptop on AC power with other processes running, a small 1233 × 604 cell chip and 17 real plots. Differences under the reported spread (about 1% typical, up to 5% between runs) are not findings, and nothing here says how a whole tile or a larger fleet behaves.
- End-to-end numbers assume bytecode caches. The benchmark compiles the engine modules before timing (gitignored `__pycache__`; children run with `-B` and only read). Without caches, start-up compiles each module, for example 3.4 ms for `decision_store.py` and 2.9 ms for `decision_index.py`.
- The P6 end-to-end figure includes about 5.3 ms of this harness's own imports (JSON, hashlib, pathlib) above bare `python -c pass`. Net of that harness floor, P6 decision costs 1.4 ms; the artifact breaks out 0.85 ms of imports, 0.24 ms of load and 0.01 ms of query inside the child. Quote P6 as interpreter start-up plus about 1.4 ms.
- W3 is synthetic and its shapes are my assumption. Outputs are mapped observations, never legal compliance findings.
