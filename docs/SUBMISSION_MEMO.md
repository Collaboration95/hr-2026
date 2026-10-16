# Plotline: submission memo (SystemEarth track)

## 1. What we built

Plotline keeps the decision, not the data. For an EUDR screen we worked out which facts the rule reads, cut a multi-layer, multi-year forest stack down to those facts, and showed that the reduced layer gives the same answer as the original layers for every cell in the region. Plot polygons are then answered from the small layer instead of the original rasters.

The prototype is a Python 3.14 engine and a React/TypeScript/Vite app. The app shows each plot's supplier declaration next to the mapped observations, plus a Proof view with fidelity, storage and timing. Test region: Surat Thani, Thailand (744,732 cells), 17 supplied plots.

## 2. How it works

**Data.** Hansen GFC 2025 v1.13 `treecover2000`, `lossyear` and `datamask` (tile 10N_090E, 1233 x 604 native grid) and JRC Global Forest Cover 2020 v4. No resampling.

**Rule.** The EUDR cut-off is 31 December 2020. Two questions matter: was the cell forest on the cut-off (JRC 2020 class plus the land/water mask), and has it lost forest since (Hansen loss year, 2021 to 2025). `treecover2000` is 72% of the Hansen bytes and nothing reads it, so it is dropped, as are loss years before 2021.

**Encoding.** Each cell becomes one of 20 codes: unknown, water, or land x {2020 non-forest, forest, forest state unknown} x {no loss, 2021, ..., 2025}. JRC is read at the Hansen cell centre. The store uses bit-planes and sparse loss events.

**Query.** A polygon selects the cells whose centres it covers (exact GEOS `covers`), the codes are reduced to a 20-bin histogram, and the answer comes from the histogram. Unknown stays unknown and is never reported as clear. Registered plots are also indexed by cell, with a table of precomputed answers.

**AI.** No machine-learning model is in the pipeline; the engine depends only on numpy, rasterio and shapely. AI coding assistants wrote and tested much of the code. We tried a learned codec selector and dropped it because it lost to a plain GeoTIFF.

## 3. Results

- **Fidelity:** 744,732 of 744,732 cells decode identically to the original GeoTIFFs, so every possible plot boundary in the region gets the same answer under the stated centre rule. The 17 plots match 17 of 17 on every output field. 9,829 of 9,829 fuzzed polygons match, and an independent validator found 0 mismatches on 216,360 further polygons. One-cell-flip and moved-vertex controls are caught.
- **Storage:** 623,237 B of original layers become a 6,146 B decision layer (99.0% smaller). A plain GeoTIFF of the same codes is 8,532 B, so most of the gain comes from the layer analysis. On a whole 10-degree tile, 421.9 MB becomes 8.2 MB (storage only).
- **Speed** (hot queries, 17 plots, against our retained v1 path at 1.44 ms): registered plots re-checked from the index are 44x faster (0.032 ms), 83x with the numpy-free re-check, and about 410x from the answer table. New polygons are about 5.2x faster, and a batch of 500 runs at about 146,000 polygons/s against about 9,300/s (15.8x). Four tuning phases did not change any output or stored byte.
- **Caveats:** one region, one laptop, warm cache. From a fresh process, Python and NumPy start-up (about 15 and 25 ms) dominates.
- **Cost estimate:** about 7 CPU-minutes per tile, so roughly 30 to 60 CPU-hours for about 280 land tiles. This comes from 6 of 160 strips of one tile.
- **Tests:** 361 engine tests pass and all 17 independent validator scripts exit 0.

## 4. Limitations and next steps

- The rule is our reading of the EUDR definitions; SystemEarth has not approved it.
- One region and 17 plots. 17/17 shows encoding fidelity, not supplier compliance or satellite accuracy.
- No protected-area or legality layers (WDPA licence unclear) and no mitigation files. We do not apply the 0.5 ha minimum area or the 5 m in-situ test.
- JRC is sampled once per Hansen cell. Only one plot has mapped forest, so this test is weak.
- The index and answer table cover registered plots only, and the batch gain needs a batch in hand.
- No tile-scale queries were run, and we make no "faster than other EUDR tools" claim.

Next: confirm the rule and reference answers with SystemEarth, add protected-area and legality layers, run a multi-region workload, add change-only re-checks when a layer updates, and call GEOS directly to cut start-up time.
