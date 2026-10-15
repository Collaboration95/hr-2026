# Layer analysis, whole-tile scale and cost (draft, 15 Oct 2026)

Draft section for the main agent to integrate. Code: [`engine/decision_scale.py`](../../engine/decision_scale.py). Artifacts: [`layer-analysis-v1.json`](../../artifacts/decision/layer-analysis-v1.json), [`scale-v1.json`](../../artifacts/decision/scale-v1.json), [`tile-read-v1.json`](../../artifacts/decision/tile-read-v1.json), [`cost-v1.json`](../../artifacts/decision/cost-v1.json). Rerun with `.venv-data/bin/python -B -m engine.decision_scale [--analysis] [--scale] [--read-timing] [--cost]`.

All sizes use one yardstick: zstd level 19 of the raw row-major uint8 plane, no chunking or header. It is a way to compare attributes, not a proposed container. The original GeoTIFF sizes are shown next to it.

## What each attribute costs, and who needs it (the 744,732-cell chip)

| Attribute | zstd-19 bytes | GeoTIFF file | Which question needs it | Verdict |
| --- | --- | --- | --- | --- |
| treecover2000, exact % | 397,973 | 414,142 | None | Drop. 75% of the Hansen bytes. |
| lossyear 2001–2020 detail | 107,371 | (part of 159,863) | None | Drop. Before the cut-off, and JRC supplies forest at the cut-off. |
| lossyear 2021–2025 | 40,688 | (part of 159,863) | Deforestation since; the supplier's Hansen 2021–23 check | Keep |
| datamask | 853 | 2,994 | All three | Keep. Cheap, and it keeps "unknown" distinct from "no loss". |
| JRC 2020 forest, native 9 m | 26,558 | 46,238 | Forest at the cut-off | Reduce. The contract reads 1 of every 9 JRC cells. |
| JRC sampled at Hansen centres | 8,726 | none | Forest at the cut-off; deforestation | Keep |
| Post-2020 loss on JRC non-forest land | 40,865 | none | Only the supplier's own Hansen check | In L1, forgotten by L2 |
| Screen codes (L1) | 45,745 | none | All three | Ship |
| Decision codes (L2) | 9,874 | none | Forest at the cut-off; deforestation | Ship |

Separable planes are not additive. Full lossyear is 133,810. The Hansen three bands total 532,636, which sits close to the retained 535,012 B store. L1 is 92.7% smaller than the 623,237 B of original files (91.8% smaller than the yardstick). L2 is 98.4% smaller (98.2%). xz-9e saves a further 8–14% on the code planes (L1 42,008, L2 8,548). The shipped store files are smaller than these yardstick sizes because the store splits the codes into bit-planes and sparse loss events: L1 is 38,513 B and L2 is 6,146 B (`stores.json`).

Region facts for the chip:

- 42.9% of land cells show Hansen loss at some point since 2001 (319,011 of 743,418).
- 80,429 land cells (10.8%) show loss after 2020. Of these, 341 (0.42%) sit on JRC 2020 forest and count as deforestation. The other 79,871 are on non-forest land, plus 217 on edge cells where JRC has no value.
- A Hansen-only forest proxy (canopy above 10%, no loss to 2020) marks 58.4% of land as forest and 71,030 post-2020 loss cells on it. JRC marks 15.9%. That gap is why the rubber and oil-palm mosaic needs the second layer.

## Grounding in the EUDR definition

The pinned JRC metadata states the definition: land over 0.5 ha with trees over 5 m and canopy over 10%, or trees able to reach those in situ, excluding land predominantly in agricultural or urban use. Cattle, cocoa, coffee, oil palm, rubber and soya plantations are excluded from forest. The cut-off is 31 December 2020. Check the wording against Regulation (EU) 2023/1115 before quoting.

- **Captured through JRC only:** the plantation exclusion and the 10% / 5 m tests. We rely on JRC's own claim; its technical report is still pending.
- **Captured at year resolution:** the cut-off. Loss in 2020 cannot be told from loss on 31 Dec 2020.
- **Not captured by any step here:** the 0.5 ha minimum area (a Hansen cell is 0.076 ha, a JRC cell 0.0085 ha, so 0.5 ha is about 6.6 or 59 cells; no contiguity test is applied), "trees able to reach the thresholds in situ", and degradation.
- **A proxy:** "deforestation" here is mapped tree-cover loss on mapped 2020 forest. Hansen loss includes fire and logging and does not say what the land became.

## JRC aggregation sensitivity

The shipped rule reads the middle JRC cell of each exactly nested 3×3 block. The study also tried "any forest in the block" and "at least 5 of 9". Totals are over the 741,062 cells whose whole block lies inside the JRC chip. All 17 plots lie inside it.

| Rule | Forest share of land | Deforested cells |
| --- | --- | --- |
| Centre cell (shipped) | 15.998% | 341 |
| Majority (5 of 9) | 16.005% | 332 |
| Any forest | 16.575% | 506 |

- **No plot decision changes under either alternative.** All 17 forest-present and deforestation-present flags are identical.
- **Weak test.** Only P-0001 has any forest cells: 60 centre, 60 majority, 65 any. Its deforested cells are 2, 2 and 4. The other 16 plots have no forest cell under any rule.
- **"Any" is the only rule that moves region totals.** It adds 4,272 forest cells and 165 deforested cells.

## One real tile

Hansen 10N_090E (3 bands, 40,000 × 40,000) plus the 120,000 × 120,000 JRC tile. Both cover 0–10°N, 90–100°E. The JRC lattice nests Hansen exactly (ratio 3, offsets 1 and 1), and every strip returns the same offsets. Streaming took 160 strips of 250 Hansen rows with 8 workers; all strips were processed, nothing is extrapolated. Wall time is 168 s for everything, including xz-9e on every strip.

| Representation | Bytes | Share of original |
| --- | --- | --- |
| Original files: Hansen 3 bands + JRC (LZW GeoTIFF) | 421,910,035 | 100% |
| Hansen 3 bands alone, original | 224,170,336 | 53.1% |
| L0 yardstick: Hansen 3 bands, zstd-19 | 130,828,454 | 31.0% |
| L0 yardstick plus JRC native, zstd-19 | 148,892,092 | 35.3% |
| L1 screen codes, zstd-19 | 13,647,704 | 3.2% |
| L2 decision codes, zstd-19 | 8,242,423 | 1.95% |
| L1 / L2 with xz-9e | 12,288,728 / 6,951,364 | 2.9% / 1.6% |

- **Fair comparison.** The original LZW files are not a tight lossless format on this tile. Plain zstd-19 of the same layers is 65% smaller. Against the yardstick, L1 is 90.8% smaller and L2 is 94.5% smaller. Quote both.
- **Chip gaps close on the tile.** L2 is 60% of L1 on the tile but 22% on the chip, because the tile's rotation loss is a smaller share of the cells and map structure dominates.
- **Where the tile bytes go.** Exact canopy is 104.6 MB and loss years 24.0 MB. L1 is 13.6 MB and L2 8.2 MB.
- **Decode.** Reading the four source files in one process takes 2.09 s per tile: the median of three back-to-back GDAL passes over all of them (2.24, 2.09 and 2.09 s; warm cache; [`tile-read-v1.json`](../../artifacts/decision/tile-read-v1.json)). The cost model uses this in place of the 7.1 s in `scale-v1.json`, which sums the strip-read times across the 8 workers. Decoding the L2 frames takes about 0.23 s and L1 about 0.30 s (sampled on 20 strips, scaled).
- **Tile content.** 13.7% of the 1.6 billion cells are land. 24.8% are water, and 61.5% are no data, mostly open sea, coded unknown. This is a coastal tile, which flatters every representation.
- **Forest and loss.** JRC forest at Hansen centres is 48.3% of land. Loss after 2020 is 12.49 M cells, of which 2.81 M (22.5%) sit on JRC 2020 forest. Deforested cells by year are 383,565 (2021), 414,441, 516,574, 545,973 and 947,705 (2025). 23.6% of land has any Hansen loss.

Checks:

- **Chip position.** The chip sits at Hansen row 5672, column 35089, and JRC row 17017, column 105269. All four chip rasters equal the tile windows pixel for pixel.
- **Strip codes vs chip codes.** On the 742,293 chip cells that have JRC coverage, the strip codes equal `derive_screen_codes` on the chips exactly. The other 2,439 cells are a one-row, two-column fringe where the JRC chip stops short. The chip marks forest unknown there and the tile knows the state.
- **Sampling.** On three strips, a decimated JRC read equals explicit indexing. On all 160 strips, the sampled forest plane fed back as a ratio-1 JRC grid reproduces the pinned codes.
- **Masks.** All four tile files are all-valid with no nodata, so no JRC cell is invalid.

## Cost estimate (bonus)

Every price is a **list price assumption, verify before quoting**, dated 2026-10-15, with no web lookup: S3 Standard $0.023 per GB-month, GET $0.0004 per 1,000, Lambda $0.0000166667 per GB-second (plus $0.20 per million invocations), egress ignored. Tile counts are assumptions, not counts: 216 ten-degree cells lie between 30°N and 30°S; I assume about 100 hold substantial land, and about 280 Hansen land tiles globally.

The measured tile is 13.7% land, so storage is shown on three bases. "Measured" uses the tile as it is. "All land" scales bytes per land cell to a fully land tile and is a rough ceiling.

| Per month, 1 copy of the layers | Original | L0 yardstick | L1 | L2 |
| --- | --- | --- | --- | --- |
| One tile, measured | 0.39 GB, $0.009 | 0.14 GB, $0.0032 | 0.013 GB, $0.0003 | 0.008 GB, $0.0002 |
| Tropical belt (100 tiles), measured | 39.3 GB, $0.90 | 13.9 GB, $0.32 | 1.27 GB, $0.029 | 0.77 GB, $0.018 |
| Tropical belt, all-land ceiling | 286 GB, $6.58 | 101 GB, $2.32 | 9.3 GB, $0.21 | 5.6 GB, $0.13 |
| Global (280 tiles), measured | 110 GB, $2.53 | 38.8 GB, $0.89 | 3.6 GB, $0.082 | 2.1 GB, $0.049 |
| Global, all-land ceiling | 801 GB, $18.43 | 283 GB, $6.51 | 25.9 GB, $0.60 | 15.7 GB, $0.36 |

Five kept vintages multiply these by five.

Re-checking 10 million registered plots after a layer update, belt, measured basis, one Lambda GB:

| Path | Per-plot time | CPU seconds | Cost |
| --- | --- | --- | --- |
| Original v1 | 85.98 µs | 1,069 (860 per plot, 209 reading tiles) | $0.020 |
| L2 registry | 2.80 µs | 51 | $0.0009 |
| L2, new polygons (not registered) | 29.09 µs (selection plus reduction) | 314 | $0.0053 |

- **Measured inputs and their sources.** `--cost` reads the per-plot times from [`benchmark-v1.json`](../../artifacts/decision/benchmark-v1.json) (`cost_inputs`: pooled hot medians on the 17 supplied plots), so they cannot drift: original v1 is P0, the registry is P5 decision with the precomputed hash, and new polygons is P4 fast selection. The original layers' tile read is the 2.091 s single-process figure from `tile-read-v1.json` (arm64, 10 cores). The L0, L1 and L2 decode times (1.24, 0.30 and 0.23 s per tile) come from the zstd decode timing in `scale-v1.json`: single thread, warm cache, 20 strips scaled to 160. The formulas are in `cost-v1.json`.
- **Container assumption.** Ranged GETs and per-strip working memory assume a strip-indexed container that is not implemented. The shipped store (`engine.decision_store`) holds at most 16,384 cells per side and 16,777,216 cells, far below this tile's 1,600,000,000. Tile sizes here are zstd-19 per-strip sums (the yardstick), and the GET count is the byte size divided by 8 MiB, rounded up. Both hold only for such a container.
- **Plain reading.** L2 storage is about 98% smaller, and the re-check of registered plots is about 95% cheaper ($0.0009 against $0.020; 51 s of compute against 1,069 s). New polygons are about 73% cheaper, because polygon selection dominates once a plot is not registered. At these prices storage is cents to tens of dollars a month and a full re-check costs cents. The case for the work is time to answer, memory per worker and being able to re-run, not the bill.
- **Not priced.** Cold object-store latency, network time, the original path's extra JRC sampling step, and the 15-minute Lambda limit.
