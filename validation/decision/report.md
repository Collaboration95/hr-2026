# Decision-layer independent validation (15 Oct 2026)

The validator's reference side never imports `engine.decision`. It reads the GeoTIFFs with rasterio, locates JRC cells with exact `Fraction` arithmetic, selects cells with an exact rational point-in-polygon test, and reduces with its own reducer written from the contract prose (`_common.py`). Run everything with `.venv-data/bin/python -B validation/decision/run_all.py` (about 80 s). Exit 0 means the claim holds; exit 1 means a defect was reproduced.

## Verdicts

| # | Claim | Verdict | Evidence | Repro |
| --- | --- | --- | --- | --- |
| 1 | Decoded stores equal the originals cell for cell, so every polygon gets identical outputs | **Confirmed** | 744,732/744,732 cells at both levels. JRC lookup agrees three ways (rational, integer offsets, float affine); the Hansen centre is within 6.6e-11 of a JRC centre. The tile-wide float affine equals `3k+1` on every row and column. 17 plots × 2 levels are equal across the store, registry, table and proof (34/34). 800 independent polygon evaluations are equal. 29,444 injected unknown cells agree, and so do 600 polygons over them. | `v01_fidelity.py`, `v01b_axis_float_tile.py`, `v01c_synthetic_unknowns.py` |
| 2 | The original path is independent; the proof compares like with like | **Confirmed**, with the shared parts disclosed | Shared: `select_cells`, the loaders and the code formula. Six seeded mutations each make the proof fail. The exhaustive check carries the weight, because the 17-plot check misses an erased-2021-loss mutation. | `v02_independence.py` |
| 3 | P-0001 has 2 deforestation cells and 38 Hansen cells in 2021–23; the tri-state semantics hold | **Confirmed** | Matches `explore_cross_layer.py` and `demo-v1.json`. 59,904 histogram cases equal a possible-worlds definition. P-0005, P-0006, P-0013, P-0014, P-0016 and P-0018 have Hansen post-2020 loss but no JRC 2020 forest, so their deforestation is False. 4,813 JRC-forest cells carry 2001–2020 loss and are kept as forest. | `v03_tristate_exhaustive.py` |
| 4 | Storage accounting and the GeoTIFF control | **Confirmed**; the plan's table estimate was **overstated** | Full-file bytes are counted. Baselines omit 19,709 B of provenance files, which is conservative. The best standard composite (NBITS planes, CCITT G4 and others) is 7,038 B against 6,142 B for the custom store. About 96% of the reduction comes from dropping attributes, not from the codec. `table.json` is 20,566 B (1,665 B with zstd), not 1–2 KB. | `v04_storage_controls.py`, `v04b_ccitt_png.py` |
| 5a | The decoder raises only `ValueError` | **Broken** | A `10**400` value in a header transform raises `OverflowError`. | `v05_store_robustness.py` |
| 5b | Checksums detect accidental corruption | **Overstated** | The JSON header was unprotected: 15.3% of single-bit header flips were accepted, and one changed P-0001's forest count. | `v05b_header_unprotected.py` |
| 5c | Decoders are bounded | **Overstated** | A crafted 63–282 B `split` blob allocated 60–130 MB (`_unvarints`). | `v05_store_robustness.py` |
| 5d | A forged store with a rehashed header is detected | Accepted, within the integrity-not-authenticity model | Rejected by `read_store(expected_sha256=...)`, and the file-sha-keyed table misses. | `v05_store_robustness.py` |
| 5e | The level is part of the answer | **Broken** (API footgun) | Evaluating a decision raster at screen level silently returned 0 Hansen loss. | `v05_store_robustness.py` |
| 6 | Registry and table invalidate on change | **Overstated** | There was no grid check without `metadata`, no table content digest, an unchecked registry header, and allocation amplification. | `v06_registry_table.py` |
| 7 | `fast_select_cells` matches `select_cells` exactly | **Confirmed** | 216,360 new adversarial geometries with 0 mismatches, including 1–2 ULP vertices, 1e-18 needles, 1e-12 cells and a 99,990-vertex circle. | `v07_fast_select.py`, `v07b_big_polygons.py` |
| 8a | Whole-tile scale numbers | **Confirmed** | Two strips recomputed from the raw tiles are byte-equal. | `v08_scale_cost.py` |
| 8b | Cost model | **Overstated** | It used an 8-worker CPU sum (7.1 s/tile) instead of a single-process read (2.36 s). The registry cost still used a placeholder. A strip-indexed container is assumed but not implemented. | `v08_scale_cost.py`, `v08b_read_timing.py` |
| 9 | Dropped attributes are unused | **Confirmed**; **overstated** on masks | The treecover mask is ignored, unlike v1's `known_bands`; this has no effect on the pinned data. There was no `lossyear <= 25` guard. | `v09_layer_analysis.py` |

## Re-verification after fixes

All 17 scripts exit 0 against the fixed engine (`run_all.py`; `--heavy` adds the large-polygon run), and `out/*.json` is refreshed. The scripts were updated for store format v2, the `PLDREG2` registry, the table `content_sha256` and the required `level`/`metadata` arguments. No verdict logic was weakened.

| Finding | Verdict | Evidence |
| --- | --- | --- |
| 1 Fidelity | Holds | 744,732 cells × 2 levels, 0 mismatches. The 17 plots are identical across 10 paths, including `evaluate_store`, `registry_evaluate_store` and `table.json`. Treecover-mask unknowns now match v1. |
| 2 Independence | Confirmed | Mutations M1–M6 each fail the proof. Shared selection is validated separately (finding 7). |
| 4 Storage | Confirmed | Screen 38,513 B (93.82% smaller); decision 6,146 B (99.01%). Registry 4,096 B and table 20,650 B are reported as sidecars. |
| 5a Header corruption | **Fixed** | A CRC32 covers exactly the header. Only the true header length is accepted. Every 1–3-bit error and 9,000 random or burst corruptions are refused. |
| 5b Header scalars | **Fixed** | 25 forgeries (1e400, NaN, bool, deep nesting, wrong sizes) raise `ValueError`. |
| 5c Varint amplification | **Fixed** | Sizes are checked before allocation. A 16 MB hostile stream peaks at 16 MB (it was 128 MB). Tight honest data is accepted, with 0 bound violations in 20,000 streams. |
| 5d Corrupt payloads | **Fixed** at `read_store` | Payload and decoded-raster hashes refuse every flip that the raw codecs would decode. |
| 5e Level binding | **Fixed** for store-aware paths; accepted risk for raw rasters | `level` is required. `evaluate_store` and `registry_evaluate_store` take it from the header and raise on conflict. A deliberately wrong level on a raw raster stays the caller's responsibility. |
| 6a Registry grid | **Fixed** | `metadata` is required; a shifted grid or another shape misses. |
| 6b Registry parser | **Fixed** | Header sha256, typed grid, and run bounds checked before expansion. The residual aggregate amplification (20 plots × 3M cells from 3.4 KB, 300 MB) is closed by `MAX_REGISTRY_CELLS`, with a regression test that fails on the earlier parser. |
| 6c Table staleness | **Fixed** | `content_sha256` is verified on load. Edits, a missing hash, an old schema, or edited store or grid fields are refused. A raster-keyed table needs the live grid. |
| 7 Fast selection | Confirmed | 216,360 geometries, 0 mismatches. |
| 8a/8b Cost model | **Fixed** | Inputs come from `benchmark-v1.json` (85.36 / 3.55 / 38.94 µs). The single-process tile read is 2.091 s. The strip-container assumption is stated. |
| 9 Layer analysis | Confirmed | Every region fact and plane size recomputes. |
| 10 Proof gate | **Fixed** | A missing store fails `all_pass` and the CLI exits 1. An explicit opt-out is available. |

## Accepted risks (integrity, not authenticity)

CRC32 and self-hashes detect accidents, not deliberate forgery. Someone who edits a store, table or registry and recomputes its hashes is accepted by the loaders. Such edits are rejected when the caller pins the genuine file hash: `read_store(expected_sha256=...)`, and the table, which is keyed by store-file hashes. The table's own `content_sha256` is not yet pinned anywhere external. A tagged (codes, level, grid) raster object would remove the last raw-path footgun. Neither change is needed for the demo.
