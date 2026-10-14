# 1 · The brief and the data

*Plain-English orientation, written 15 October 2026. The sources for every claim are linked at the end.*

## The event

**Hack & Hire Sustainability Edition 2026** is run by Projet with NUS CAT. Teams of one to three work on a real company problem from **10 to 17 October**, then pitch to that company's team at the finals on **17 October**. We picked the **SystemEarth** track on 10 October and were accepted on 11 October.

## What SystemEarth asked for, in one paragraph

Companies that sell commodities such as rubber, palm oil, cocoa or coffee into the EU must show that each farm plot is **deforestation-free**. This is the EU Deforestation Regulation (EUDR). In practice, you take each plot's boundary and check it against satellite-derived map layers:

- Was there **forest on 31 December 2020** (the cut-off)?
- Has any **tree cover been lost since**?
- Does the plot overlap **protected or restricted land**?

The layers come from different sources, at different resolutions, and they get updated every year. Multiply that by millions of plots and many years, and the data becomes very large. SystemEarth's question:

> **Can you store several geospatial layers across time and space compactly, query them efficiently, and still reproduce exactly the same plot-level decisions as the original layers?**

## What they asked us to deliver

The printed brief, the kickoff slides and the spoken briefing differ a little. The table shows what each source asked for.

| Ask | Firmness |
| --- | --- |
| Pick a specific use case | Required |
| Choose the essential layers and time periods; say what can be simplified or dropped | Required |
| Choose an encoding, then encode **and query** a sample region | The printed slides ask for a **working prototype**; the speaker was less firm. We built the prototype. |
| Compare with the original layers on **storage, query speed, resource use, plot-decision fidelity** (% of plots whose outputs *all* match) and **pixel fidelity** | Required |
| Explain pipeline choices and any AI output | Required |
| Estimate infrastructure cost | Bonus |
| Invent a new compression algorithm | Explicitly **not** required; existing algorithms are fine |

No dataset, region, resolution, time span, passing threshold, pitch length or scoring rubric was specified.

## The data the company gave us (12 October)

Two small files describing **one shipment lot (Lot 200001)** from **one supplier (D001)**:

- **A CSV of 17 rows and 35 columns.** Each row is a supplier's due-diligence declaration for one farm plot: plot size, supply-chain tier, which deforestation layer they checked, what it showed, what they did about it, a link to evidence, and final statuses for deforestation, protected areas, land tenure, labour, and EUDR overall.
- **A GeoJSON file with the 17 matching plot boundaries** (polygons).

The two files join perfectly: 17 IDs, no duplicates and nothing unmatched. Numbering gaps such as P-0002 are just gaps. The plots are **smallholdings of 0.53–20.07 ha**, labelled **Chai Buri, Surat Thani, Thailand**.

What the declarations say:

- **All 17** declare a final status of *Deforestation-free* and *EUDR: Compliant*.
- **All 17** say they used *"Hansen Tree Cover Loss 2021-2023"* for their check.
- **Five plots** (P-0003, P-0005, P-0008, P-0010, P-0013) say the check found an *"Indication of deforestation"*, which was then resolved by *"On-site verification with evidence"*. Their evidence link is an opaque key such as `hyperlink-RG1-P-0002`, and **the evidence files themselves were not supplied**.

Supplier declarations are not facts. We treat them as **claims to check**, never as ground truth.

## The data we fetched ourselves (public layers)

| Layer | What it is | What we kept |
| --- | --- | --- |
| **Hansen Global Forest Change 2025 v1.13** (University of Maryland) | `treecover2000`: canopy % in 2000. `lossyear`: the year (2001–2025) in which tree cover was lost, if ever. `datamask`: land, water or no data. About 28 m cells. | A 1,233 × 604-cell chip from tile `10N_090E` covering all 17 plots (about 34 × 17 km, **744,732 cells × 3 bands**). It is 577 KB on disk; the full source tiles were 224 MB. |
| **JRC Global Forest Cover 2020 v4** (EU Joint Research Centre) | Forest / non-forest at **2020**, the EUDR cut-off year. About 9 m cells, on a different grid from Hansen. | A 3,695 × 1,809-cell chip, kept as a **separate** layer with its own grid, store and proof. |

Two corrections happened along the way. A teammate had proposed Songkhla, rubber and Hansen tile `10N_100E`, but that tile does not cover this sample, so we used `10N_090E`. JRC v3 also failed to download (HTTP 500), so we used v4. The protected-areas layer (WDPA) was not used because its terms are unclear.

## What the place looks like

The app's map *is* the Hansen raster, recoloured; it is not a photo. Two things jump out:

- A big **forest block** sits in the middle of the area, surrounded by a **plantation mosaic** (rubber and oil palm country).
- Tree-cover loss is everywhere in that mosaic. In an exploratory count, about **43% of land cells** show loss at some point since 2001, because plantations are cut and replanted on rotation. JRC's 2020 map marks only about **16%** of the area as forest, mostly the central block.

The second point turns out to matter a lot for the pitch (see [findings](02-what-we-tried-and-found.md#what-we-found)).

## Sources

[Printed brief](../problem_statement_reference.txt) · [spoken guidance](../transcript_rules_and_constraints.txt) · [kickoff slides](../sustainability_kickoff_reference.txt) · [event rules](../event_rules_and_open_questions.txt) · [track brief](../../SystemEarth-track.md) · [sample audit](../research/company-sample-audit.md) · [Hansen acquisition](../research/layer-acquisition.md) · [JRC acquisition](../lab/engine-data-W4.md) · [exploratory cross-layer script](../../scripts/explore_cross_layer.py)
