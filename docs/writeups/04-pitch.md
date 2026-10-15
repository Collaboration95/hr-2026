# 4 · The pitch

Every number below is in the app or the retained evidence. Stick to these numbers and wording, because the judges are engineers and will probe.

## One line

> **Plotline keeps every plot-level deforestation answer identical while storing the map layers compactly, and gives every answer a receipt you can re-check.**

## Elevator pitch (~30 seconds)

> To sell into the EU, every farm plot has to be shown deforestation-free. You take its boundary and check it against satellite layers: was it forest at the end of 2020, and has it lost trees since? Do that for millions of plots and years of layers and the data gets heavy. SystemEarth asked whether you can shrink it without changing a single decision.
>
> Plotline does that for 17 real supplier plots in Thailand. It stores three Hansen layers across 25 years, plus the EU's 2020 forest map, in a compact form. All 17 plot answers come out **identical** to the original, down to the pixel, and each one ships with a receipt.
>
> And when we replayed the supplier's own check, none of the five plots they flagged show loss on the layer they cite, while three they cleared do. That's not an accusation. It's exactly why a decision needs a receipt.

## Longer version (~60–90 seconds, opens the demo)

> **Problem.** EUDR compliance is a geospatial join at scale: plot polygons × forest baseline × annual loss × protected areas, re-run whenever a layer updates. SystemEarth's question is how to store that compactly, query it fast, and still reproduce every plot decision.
>
> **What we built.** A working pipeline on the company's own sample: 17 smallholder plots in Surat Thani, three Hansen bands, 25 years of annual loss and the JRC 2020 forest baseline.
> - One written query rule: a cell counts if its centre is inside the plot.
> - Two ways to answer it: from the original GeoTIFFs and from our compact store.
> - Proof they agree: **17/17 plots identical on every output field**, with every raw pixel and mask preserved.
>
> **Honest numbers.**
> - The store is **8.6% smaller** at the loader boundary.
> - Fresh start plus all 17 queries runs **about 1.9× faster**. Once data is in memory there is no speed difference.
> - A tuned standard GeoTIFF is within half a percent of us, and our ML codec selector lost on held-out data, so we rejected it. We show those losses in the product.
>
> **Why it matters.** The supplier's declarations can't be reproduced from the layer they name, even with the older data release or a looser boundary rule. And in this plantation landscape, Hansen alone would flag rotation harvests as deforestation: under 1% of post-2020 loss sits inside the 2020 forest map. Multi-layer, multi-year, reproducible answers aren't a nice-to-have. They're the product.

*Caveat for you:* the "under 1%" figure is an **exploratory** count from [`scripts/explore_cross_layer.py`](../../scripts/explore_cross_layer.py), which samples JRC at each Hansen cell centre. It is not part of the verified engine. If a judge asks, say that. The map overlay shows the same thing visually.

## Three-minute demo (new UI)

Open the app at `#/map`. If the live API is down, the Map, Cohort and Proof views still work offline.

| Time | Do | Say |
| --- | --- | --- |
| 0:00 | Region view. Press ▶ on the year scrubber. | "This map *is* the data: the Hansen raster we encode, recoloured in the browser, with no satellite photos. Watch tree-cover loss burn in from 2001 to 2025. This is plantation country, so loss is everywhere." |
| 0:25 | Toggle **JRC 2020 forest**. | "Now stack the EU's 2020 forest map. Most of that loss is outside forest; it's plantation rotation. That's why one layer isn't enough." |
| 0:45 | Click **P-0001** (or `#/map/P-0001/2022`). | "Zoom into one plot. These squares are the actual ~28 m cells, and the dots are cell centres, which is our written inclusion rule. **Declared:** the supplier says no indication. **Mapped:** 38 loss cells in 2022. Plotline doesn't issue a verdict; it asks the reviewer a specific question." |
| 1:15 | **Cohort** tab. | "All 17 plots × 25 years on one screen. Look at the matrix: five declared indications, three mapped plots, zero overlap. We tested the older data release and a different boundary rule, and neither explains it." |
| 1:40 | Click a barcode cell (e.g. P-0005, 2025), then the year count → **Proof**. | "Every number is clickable down to its proof. Same question, two representations: identical outputs, field by field." |
| 2:00 | Scroll the Proof hero and storage chart. | "17 of 17 plots identical, 100% pixel fidelity. 8.6% smaller, 1.9× faster cold start, no hot-query gain. And here's the standard GeoTIFF that beats us by half a percent. We show where we lose." |
| 2:30 | Open **Receipt**, then the **Live query** tab → **Run region**. | "Every answer has a receipt with source versions, grid, rule and hashes. And it's live: ask any new region, and both representations answer with the full cell evidence." |
| 2:50 | Close. | "Plotline: compact layers, identical decisions, answers you can re-check." |

## Likely questions, with short answers

1. **"8.6% isn't much compression."** True on a 34 × 17 km chip of already-compressed GeoTIFFs. We report the honest boundary. The point is a verified pipeline that lets you choose the format by workload, and we show a standard GeoTIFF is competitive. The larger opportunity is dropping what decisions don't need (bands, years, areas away from plots). The fidelity proof is what tells you a drop is safe. We haven't measured that at scale yet.
2. **"What exactly is preserved?"** The full result for every plot: selected cells, land/water/unknown counts, annual loss histogram, period flags and support state. Plus every raw pixel value and validity mask in the region. Not just the headline number.
3. **"Who decided the centre rule?"** We did, and we wrote it down. An "any overlap" rule changes five answers, so the rule has to be part of the contract. We'd adopt SystemEarth's rule. Changing the rule doesn't change the fidelity claim, because both rules give 17/17 on both stores.
4. **"Is the supplier lying?"** We can't say that, and we don't. Their result can't be reproduced from the layer they name with our rule or the older release. That's a question for the evidence files, which weren't supplied.
5. **"Why not use AI?"** We tried a learned codec selector with a sealed spatial holdout. It lost to a fixed setting, so we rejected it. ML should earn its place on measurements.
6. **"Does it scale?"** We measured 17 plots on one region. We won't extrapolate. The next step is a representative workload from SystemEarth: plot counts, batch sizes, update frequency.
7. **"Why is JRC separate?"** It has a different grid (~9 m vs ~28 m) and different definitions. Adding its counts to Hansen's would be wrong, so each layer keeps its own native grid, store and proof.
8. **"Can I reproduce this?"** Yes. `scripts/setup-local.sh` then `scripts/verify-local.sh` rebuilds the proofs from tracked files, and there's no need for the 224 MB source tiles.

## Words to use / avoid

| Use | Avoid |
| --- | --- |
| "mapped tree-cover loss", "loss cells" | "deforestation found", "hectares deforested" |
| "declared by the supplier" | "the supplier is compliant", "violation" |
| "identical outputs", "encoding fidelity" | "accurate", "ground truth" |
| "fresh-process load + query" | "disk-cold", "always faster" |
| "a question for the reviewer" | "red flag", "non-compliant" |
