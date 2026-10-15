# Plotline writeups (plain English)

Written 15 October 2026 to catch up on everything done so far, mostly by earlier AI agent sessions, without reading 200 lab reports.

| # | Read this | If you want to know |
| --- | --- | --- |
| 1 | [The brief and the data](01-the-brief-and-the-data.md) | What SystemEarth asked for, what the company gave us, which public layers we added |
| 2 | [What we tried and found](02-what-we-tried-and-found.md) | What was built, what worked, what failed, and the interesting findings |
| 3 | [What we ship](03-what-we-ship.md) | The scope for the finals, the deliberate cuts and open questions |
| 4 | [The pitch](04-pitch.md) | One-liner, 30-second elevator pitch, 3-minute demo script, and likely judge questions |
| 5 | [Redesign decisions](05-redesign-decisions.md) | What changed in the UI today and why, plus what was verified |
| 6 | [Decision layers](../lab/decision-layer-report.md) | The layer analysis, the 6 KB decision layer, its proof, the storage and speed results, and the three speed-up phases |

## The two-minute version

- **The challenge:** keep multi-layer, multi-year satellite map data for farm plots compact and fast to query, *without changing any plot-level compliance answer*.
- **Our use case:** EUDR-style deforestation screening for **17 real supplier plots in Surat Thani, Thailand**. The company supplied the plot boundaries and the supplier's declarations.
- **The layers:**
  - **Hansen** tree-cover data: canopy in 2000, the year of loss for 2001–2025, and a land/water mask, at ~28 m.
  - **JRC 2020 forest map** as a separate baseline layer.
- **What we built:** a written query rule, the original path and a lossless store, with a **proof that all 17 plot answers are identical**. On 15 Oct we added **decision layers**: we kept only what the EUDR decision reads and proved it gives the same answer for **every one of 744,732 cells**. It also has receipts, a live query API, and the **Plotline** app to explore it.
- **Numbers:**
  - The decision layer is **6.1 KB vs 623 KB of original layers: 99% smaller**. On a whole 10° tile it is 98% smaller (94.5% vs a zstd recompression).
  - Registered plots are re-checked **44× faster** hot (65× with the numpy-free re-check, 417× from a stored answer table). New boundaries are 5.3× faster, or about 15× when they arrive as a batch (a batch must be in hand). Fresh-process end-to-end time is dominated by Python and NumPy start-up; only the numpy-free re-check of registered plots moves it, from 49.8 to 24.8 ms. Three speed-up phases on 15 Oct took the index from 24× to 44× and new boundaries from 2.2× to 5.3×, with no change to any output.
  - A plain GeoTIFF of our decision codes is already 98.6% smaller: the win is the layer analysis, and we show it. The lossless store is only 8.6% smaller and stays as the audit tier.
  - Our ML codec selector lost, and was rejected.
- **The headline finding:** the supplier's five "indication of deforestation" plots show **no** loss on the layer they cite. Three plots they cleared **do** show loss. Neither the older data release nor a different boundary rule explains it. That is not an accusation. It is why decisions need receipts.
- **What the decision layer shows:** Hansen alone shows post-2020 loss on 7 of 17 plots. Only P-0001 has mapped loss on JRC-mapped 2020 forest (2 cells in 2022). Region-wide, 341 of 80,429 post-2020 loss cells (0.4%) sit on mapped 2020 forest.
