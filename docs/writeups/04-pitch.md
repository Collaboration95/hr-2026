# 4 · The pitch

Every number below is in the app or the retained evidence ([decision-layer report](../lab/decision-layer-report.md)). Stick to these numbers and this wording: the judges are engineers and will probe.

## One line

> **Plotline keeps the decision, not the data: a 6 KB decision layer gives the same EUDR screening answers as 623 KB of original map layers, proven for every cell in the region.**

## Elevator pitch (~30 seconds, ~80 words)

> To sell into the EU, every farm plot must be shown deforestation-free: forest at the end of 2020, lost since? SystemEarth asked us to keep that decision, not the data.
>
> We worked out what the decision actually reads, and dropped the rest. On 17 real supplier plots, the decision layer is **99% smaller**. Registered plots are re-checked **33× faster**, and every one of 744,732 cells gives the **same answer** as the original layers.

## Longer version (~60–90 seconds, opens the demo)

> **Problem.** EUDR screening is a geospatial join that gets re-run: plot boundaries × forest at the 2020 cut-off × annual loss since, every time a layer updates.
>
> **Layer analysis.** The decision needs three facts per map cell: land or water, forest on 31 December 2020, and the year of any loss since. Hansen's canopy percentages are 72% of its bytes, and no question reads them. Loss years before the cut-off and JRC's sub-cell detail don't change the answer either. We drop all of it and keep a 20-value code per cell.
>
> **Proof.** An independent path rebuilds every code from the original GeoTIFFs: **744,732 of 744,732 cells identical**. Every output is a function of the selected cells' codes, so every possible plot boundary gets the same answer, not just the 17. Fuzzing 9,829 polygons agrees, and an independent validator re-derived it with exact arithmetic.
>
> **Numbers.**
> - **Smaller:** 6.1 KB vs 623 KB, **99% smaller**. On a whole 10° × 10° tile, 422 MB becomes 8.2 MB (94.5% smaller even against a zstd recompression of the originals).
> - **Faster:** registered plots **33× faster** hot through a precomputed plot index, and **417×** from a stored answer table. New boundaries are **5.0×** faster with exact scanline selection. If a batch of new boundaries is in hand, a batch evaluator reaches about 14× on 500 synthetic polygons; it needs the batch, and on 17 plots it is only 1.2× ahead of the one-at-a-time path. The fresh-process load + query time falls from 11.1 ms to 1.3 ms (index), or 1.0 ms with the numpy-free re-check. Peak memory falls from 75 MB to 37 MB (23 MB numpy-free). These are hot-query and load + query times for registered plots, on one region and one laptop with a warm cache. The whole fresh-interpreter run is mostly Python and NumPy start-up, so end-to-end barely moves, except for the numpy-free re-check of registered plots (49.7 to 24.6 ms).
> - **Honest controls:** a plain GeoTIFF of our decision codes is already 98.6% smaller. The win is the layer analysis; our encoding adds the last 28%. We show that in the product.
>
> **What it finds.** Hansen alone flags 7 of the 17 plots for loss after 2020. Against JRC's 2020 forest map, only **P-0001** shows mapped loss on mapped 2020 forest: **2 cells in 2022**. The supplier's own declarations don't line up with either.

## Three-minute demo: follow one plot

Open the app at `#/map/P-0001/2022`. If the live API is down, Map, Cohort and Proof still work offline.

| Time | Do | Say |
| --- | --- | --- |
| 0:00 | Region view; press ▶ on the year scrubber, then pause at 2022. | "This map *is* the data: the Hansen raster, recoloured in the browser. Watch loss burn in from 2001 to 2025. This is rubber and oil-palm country." |
| 0:20 | Toggle **JRC 2020 forest**. | "Now stack the EU's 2020 forest map. Much of the mapped loss falls outside JRC's 2020 forest class. The cause needs further evidence, but it means one layer alone raises the wrong alarm." |
| 0:40 | Click **P-0001**. | "One plot. These squares are the ~28 m cells; the dots are the centres, our written inclusion rule. **Declared:** no indication. **Hansen:** 38 loss cells in 2022. **Decision layer:** 60 cells were 2020 forest, and 2 of them were lost in 2022. Plotline asks the reviewer about those 2 cells, not all 38." |
| 1:15 | **Proof** tab: decision-layer hero. | "That answer came from a 6 KB decision layer, not 623 KB of layers. Every one of 744,732 cells matches the originals, so every plot boundary gets the same answer. 99% smaller. 33× faster for registered plots." |
| 1:45 | Scroll to the ladder and speed table. | "Here's what we dropped and why: canopy percentages, pre-2021 loss years, JRC sub-cell detail. Here's the standard GeoTIFF control: most of the win is the layer analysis, not a magic codec. The lossless store stays as the audit tier." |
| 2:15 | **Cohort**, then back to P-0001. | "Zoom out: 17 plots × 25 years. We tested the declarations against our documented rule and two data releases, and they don't line up. That's a question for the evidence files, not an accusation." |
| 2:40 | Open the **Receipt**. | "Every answer has a receipt: layer versions, grid, rule and hashes. For SystemEarth, the next step is one agreed query contract, one reference plot and a representative workload." |

## Likely questions, with short answers

1. **"Isn't dropping data lossy?"** It's lossy on what the decision doesn't read, and exact on what it does. We prove the second part for every cell, not by sampling. The lossless v1 store remains the audit tier, and the public source releases are pinned by hash, so a rule change can re-derive the layer.
2. **"Why not just GeoTIFF?"** A GeoTIFF of our decision codes is already 98.6% smaller, and we show it. The value is knowing *what* to keep and proving that it's enough. Our encoding is 28% smaller again. Use whichever container suits the stack.
3. **"Isn't the 417× a cache?"** Yes: a materialised view for registered plots, keyed by plot ID, geometry hash and layer hash, so a change in either misses. EUDR plots are registered once and re-checked as layers update, which is exactly that workload. New boundaries use the decision layer at 5.0× (about 14× as a batch, which needs the batch in hand). We report every path separately.
4. **"What if the rule changes?"** Then the decision layer is re-derived from the pinned originals. It takes seconds for this region and about 3 minutes for a full tile on a laptop with 8 workers. The rule (centre inclusion, JRC at the cell centre) is written down. Swapping JRC's centre rule for a 3×3 majority or "any forest" changes no plot decision here.
5. **"Does it scale?"** Storage was measured on a whole real tile (1.6 billion cells): 98% smaller than the original files. Query timing was measured on 17 plots and 500 synthetic plots on one laptop. Cost: storing the decision layer for the tropical belt is cents a month at list prices. The bill isn't the point; time to answer and memory per worker are.
6. **"Is the supplier lying?"** We don't say that. Their result can't be reproduced from the layer they name with our rule or the older release. Their evidence files weren't supplied.
7. **"What about AI?"** We tried a learned codec selector with a sealed holdout. It lost to a fixed setting, so we rejected it. Here the intelligence is the layer analysis, grounded in the regulation's definitions.
8. **"What's not covered?"** EUDR's 0.5 ha minimum area, the "able to reach 5 m" test and protected areas (licence unclear). Counts are cells, not hectares.

## Words to use / avoid

| Use | Avoid |
| --- | --- |
| "mapped loss on mapped 2020 forest", "loss cells" | "deforestation found", "hectares deforested" |
| "identical plot-query outputs under our documented rule" | "accurate", "ground truth", "identical deforestation answers" |
| "we tested the declarations against our documented rule and two data releases" | "we replayed the supplier's own check" |
| "falls outside JRC's mapped 2020 forest class" | "it's plantation rotation" (the cause isn't established) |
| "fresh-process load + query, excluding Python start-up" | "disk-cold", "1.9× faster cold start" |
| "about 14× as a batch of hundreds" | "14× faster" for a single new plot |
| "registered plots" vs "new boundaries" | one blended "N× faster" |
| "a question for the reviewer" | "red flag", "non-compliant" |
