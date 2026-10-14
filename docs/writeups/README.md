# Plotline writeups (plain English)

Written 15 October 2026 to catch up on everything done so far, mostly by earlier AI agent sessions, without reading 200 lab reports.

| # | Read this | If you want to know |
| --- | --- | --- |
| 1 | [The brief and the data](01-the-brief-and-the-data.md) | What SystemEarth asked for, what the company gave us, which public layers we added |
| 2 | [What we tried and found](02-what-we-tried-and-found.md) | What was built, what worked, what failed, and the interesting findings |
| 3 | [What we ship](03-what-we-ship.md) | The scope for the finals, the deliberate cuts and open questions |
| 4 | [The pitch](04-pitch.md) | One-liner, 30-second elevator pitch, 3-minute demo script, and likely judge questions |
| 5 | [Redesign decisions](05-redesign-decisions.md) | What changed in the UI today and why, plus what was verified |

## The two-minute version

- **The challenge:** keep multi-layer, multi-year satellite map data for farm plots compact and fast to query, *without changing any plot-level compliance answer*.
- **Our use case:** EUDR-style deforestation screening for **17 real supplier plots in Surat Thani, Thailand**. The company supplied the plot boundaries and the supplier's declarations.
- **The layers:**
  - **Hansen** tree-cover data: canopy in 2000, the year of loss for 2001–2025, and a land/water mask, at ~28 m.
  - **JRC 2020 forest map** as a separate baseline layer.
- **What we built:** a compact store and the original path, one written query rule, and a **proof that all 17 plot answers are identical** with **every pixel preserved**. It also has receipts, a live query API, and the **Plotline** app to explore it.
- **Honest numbers:**
  - 8.6% smaller.
  - ~1.9× faster cold start; no hot-query speedup.
  - A tuned standard GeoTIFF is 0.5% smaller still, and we show it.
  - Our ML codec selector lost, and was rejected.
- **The headline finding:** the supplier's five "indication of deforestation" plots show **no** loss on the layer they cite. Three plots they cleared **do** show loss. Neither the older data release nor a different boundary rule explains it. That is not an accusation. It is why decisions need receipts.
- **Bonus insight (exploratory):** in this plantation landscape, under 1% of post-2020 loss falls inside 2020 forest. Using one layer on its own raises far too many alarms, and stacking the layers answers the question that actually matters.
