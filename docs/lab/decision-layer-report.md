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
| Original layers, retained v1 query | 1.45 ms | 11.3 ms | 116 ms | 75 MB |
| Original layers, same EUDR question | 1.87 ms | 19.3 ms | 125 ms | 97 MB |
| Decision layer | 1.21 ms | 4.9 ms | 60 ms | 46 MB |
| Decision layer + exact fast selection | 0.66 ms (**2.2×**) | 4.3 ms | 59 ms | 46 MB |
| Decision layer + registered-plot index | **0.060 ms (24×)** | 3.5 ms (3.2×) | 52 ms | 43 MB |
| Registered-plot answer table | **0.0035 ms (420×)** | 0.25 ms (45×) | 22 ms (5.4×) | 21 MB |

Multiples are against the retained v1 path.

- **Where the speed comes from.** The representation alone gives 1.5× hot and 3.9× fresh-process speedups, because there is one small band instead of three plus a 101-bin canopy histogram. Exact scanline selection gives 1.8–2.1× on new polygons. The big hot-path gain needs the **registered-plot index**: EUDR plots are registered once and re-checked whenever a layer updates, so their cells are found once (24×). The **answer table** goes further: it holds each registered plot's precomputed answer, keyed by plot ID, geometry hash and store hash (420×).
- **New, unregistered plots** take the decision layer + fast selection path: about 22,100 synthetic plot-sized polygons per second, against 9,100 on the original path (2.4×).
- **Cold start.** The decision paths never import GDAL/rasterio, and the table path needs only the Python standard library. Most of the remaining end-to-end time is interpreter start-up (about 15 ms).

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
.venv-data/bin/python -B -m engine.decision_benchmark   # timing (≈2.5 min)
.venv-data/bin/python -B -m engine.decision_scale       # layer analysis, whole tile (needs raw tiles), cost
.venv-data/bin/python -B -m engine.decision_export      # app summary
.venv-data/bin/python -B validation/decision/run_all.py # independent checks
```
