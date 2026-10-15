# Decision layers: plan and feasibility (15 Oct 2026)

SystemEarth's slide title was "Keep the decision, not the data". The retained build kept every pixel, which is why storage is only 8.6% smaller and hot queries are not faster. This plan derives smaller layers from an explicit layer analysis and keeps the existing fidelity proof discipline.

## Where the bytes and time go today

Quick plan-time measurements on the pinned chips, 15 Oct (one process, before the isolated benchmark; current figures are in the [results report](decision-layer-report.md)):

- `treecover2000` is 414 KB of the 577 KB Hansen chip (72%). No EUDR screening output needs exact canopy percentages.
- `lossyear` (160 KB) mostly encodes loss years from 2001 to 2020. They fall before the cut-off and are not needed when JRC 2020 supplies forest at the cut-off.
- The JRC chip (46 KB) is at about 9 m. The decision is evaluated on Hansen's about 28 m loss cells. The JRC lattice nests the Hansen lattice exactly at a 3:1 ratio, so each Hansen centre is the centre of one JRC cell.
- Hot v1 batch for 17 plots: 1.6 ms. Of that, 1.09 ms is polygon selection (`select_cells`) and the rest is the v1 reduction, mostly the 101-bin canopy histogram. Reducing a uint8 decision raster takes 0.05 ms.

## The ladder: each rung drops something and states what is lost

| Rung | Contract | Keeps | Drops | Size (measured) |
| --- | --- | --- | --- | --- |
| L0 lossless archive (retained) | `hansen-centers.v1` | Every pixel of 3 Hansen bands | Nothing | 535,012 B, 8.6% smaller |
| L1 screening layer | `eudr-screen.v1` | Land/water/unknown, JRC 2020 forest at the Hansen centre, post-2020 loss year on all land (the supplier's own Hansen check) | Canopy %, loss years 2001–2020, JRC sub-cell detail | 38,513 B (`screen.plds`) vs 623,237 B of original layers, 93.8% smaller |
| L2 decision layer | `eudr-decision.v1` | Forest at the 2020 cut-off, plus deforestation (loss on 2020 forest) by year 2021–2025 | Additionally, loss on land that was not forest in 2020 (rotation) | 6,146 B (`decision.plds`), 99.0% smaller |
| L4 registered-plot table | Both contracts, registered plots only | Precomputed outputs keyed by plot ID, geometry hash and store hash | The ability to answer *new* polygons (L1/L2 answer those) | 20,650 B (`table.json`: both levels, 17 plots, about 1.2 KB per plot) plus 4,096 B (`registry.bin`: the cell index); O(1) lookup |

These sizes began as feasibility estimates (about 45 KB, about 10 KB and about 1–2 KB for L1, L2 and L4) and were updated with the measured file sizes on 15 Oct.

Semantics are pinned in [`engine/decision.py`](../../engine/decision.py). It defines one uint8 code space with 20 codes, `derive_screen_codes`, `project_decision`, and a reducer. L0 is unchanged and stays the audit tier. The public source releases are versioned and pinned by hash, so they can be re-acquired for a rule change.

## Fidelity: stronger than 17/17

Each output is a pure function of the selected cells' codes plus the out-of-chip count. If every decoded cell code equals the code derived from the original layers (exhaustive over all 744,732 cells), then **every possible polygon** gets identical outputs under the shared centre rule, not just the 17 plots. The evidence:

1. Exhaustive cell proof. An independent original path derives per-cell attributes from the original GeoTIFFs using float affine lookup and compares them with the decoded store.
2. 17/17 full output equality on every path: original, screen store, decision store, registry and table.
3. A fuzz test of 10,000 synthetic polygons (9,829 valid shapes compared and equal; 171 invalid shapes rejected identically), including edges through cell centres, holes, multipolygons, partial out-of-chip and water.
4. A cross-check showing that L1's 2021–25 Hansen counts and period flags equal the retained v1 outputs.
5. Negative controls: one flipped code, a truncated payload or a wrong hash must fail.

Pixel fidelity is reported "where relevant": 100% on retained attributes. Dropped attributes are listed rather than called lossless.

## Speed levers

- **Representation:** the decision reduction is about 10× cheaper than the v1 reduction because it uses a 20-bin histogram on 1 band instead of 3 bands with a 101-bin canopy histogram.
- **Registered plot index:** EUDR plots are registered once and re-checked as layers update, so a plot's selected cells are precomputed once (`flat_index`). This removes the 1.09 ms selection cost from the hot path for registered plots.
- **Decision table:** a lookup for registered plots, invalidated by the store or geometry hash.
- **Exact fast selection for new polygons:** a scanline over centre rows, with exact `shapely.covers` only for cells near an edge. It is kept only if it is fuzz-equal to `select_cells` and measurably faster.
- **Cold start:** decision paths need neither rasterio nor GDAL. The table path needs only the stdlib. We measure end-to-end process time *including imports* as well as the retained "load + query after imports" definition.

Every speedup is reported as a decomposition (representation vs index vs table), measured against the same baseline harness.

## What is not possible, or not worth it

- Lossless L0 cannot get much smaller. Tuned standard GeoTIFF is within 0.5% of it. Further context-modelling codecs might save 10–30% at a large complexity cost, so we don't pursue them.
- 100% raw pixel fidelity on dropped attributes is impossible by definition. That is the point of the layer analysis, and we say so.
- A legal compliance verdict is out of scope. Outputs remain mapped observations with tri-state unknowns.
- The supplier's 5 declared indications cannot be reproduced. Their method is unknown.
- Global performance cannot be measured. Whole-tile scale is measured on one real 10°×10° tile. Global cost is an extrapolation with labelled assumptions.
- Protected areas (WDPA) stay out because the licence is unclear.

## Deliberate simplification to disclose

JRC 2020 is read at the Hansen cell centre, which is the middle JRC cell of each 3×3 block. A sensitivity study compares this with "any forest in the block" and "majority of the block" on the 17 plots and region totals.

## Work packages

| Package | Files (owned) | Output |
| --- | --- | --- |
| Store and codecs | `engine/decision_store.py`, `engine/tests/test_decision_store.py` | `artifacts/decision/` stores and candidate/control sizes |
| Original path and proofs | `engine/decision_original.py`, `engine/decision_proof.py`, `engine/tests/test_decision_proof.py` | `artifacts/decision/proof-v1.json` |
| Fast paths | `engine/decision_index.py`, `engine/tests/test_decision_index.py` | Registry, table, fast selection |
| Layer analysis, scale and cost | `engine/decision_scale.py` | `artifacts/decision/layer-analysis-v1.json`, `scale-v1.json` |
| Benchmark | `engine/decision_benchmark.py` | `artifacts/decision/benchmark-v1.json` |
| Independent validation | `validation/decision/` | Validator report |
