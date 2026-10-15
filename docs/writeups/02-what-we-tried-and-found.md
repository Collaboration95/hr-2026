# 2 · What we tried, what failed, what worked, what we found

## How the work happened

| When | What |
| --- | --- |
| 10–11 Oct | Track chosen. Early ideas (a Brazil forest-risk demo, Dutch crop parcels) were shelved once the company sent real data. |
| 12 Oct | Company sample arrived. Audit: 17 plots, clean join, Thailand. Public layers fetched. |
| 13 Oct | A **2 h 35 min autonomous "research lab"**: an AI agent swarm of 14 sessions (one GPT-6 Astra master, two leads, Sol/Luna specialists) with a separate **independent validator** whose only job was to break things. This produced the first working prototype and most of the experiments. |
| 14 Oct | Completion pass: rebuilt from a clean checkout, independent browser review, recorded walkthrough. |
| 15 Oct | This UI redesign and these writeups. |

The working loop was: **question → freeze the inputs → small experiment → someone else tries to break it → keep or reject on the measurement**. Losing experiments were kept and written up, not hidden.

## What we built

1. **One precise query rule (`hansen-centers.v1`).** A map cell belongs to a plot if the cell's **centre** falls inside the plot boundary. For each plot this gives:
   - selected cells, of which valid land, water or unknown
   - tree-cover loss per year (2001–2025)
   - a yes / no / **unknown** flag for two periods: 2021–23 (the supplier's window) and 2024–25

   "Unknown" is kept distinct from "zero". A missing value never turns into a reassuring "no loss".
2. **Two ways to answer it.**
   - **Original:** read the source GeoTIFF files.
   - **Compact:** read our own store. It keeps the bands separate, compresses them with Zstandard level 19 in 1,024-cell chunks, and adds a small index and metadata.
3. **A proof that they agree.** For every plot we compare the *entire* result from both paths, not just one number, and we check that every raw pixel value and validity mask survives. A separate "scalar oracle" recomputes membership a different way.
4. **Receipts.** Each plot gets a JSON receipt with the source versions, grid, rule, hashes of the inputs and geometry, and the supplier's exact fields, so anyone can re-check the answer.
5. **A live query service.** A local, read-only API answers a *new* polygon or rectangle on both paths and returns the complete cell evidence and a bound receipt. It handles cancellation and stale responses.
6. **JRC 2020 as a companion layer.** It has its own store, proof and receipt, and is deliberately **not** merged with Hansen counts because the grids and definitions differ.
7. **The Plotline app**, which puts all of this in front of a person (see [what we ship](03-what-we-ship.md)).

## What worked ✅

| Result | Number |
| --- | --- |
| **Decision fidelity:** plots whose full query outputs match exactly | **17 / 17** |
| **Pixel fidelity:** raw values and masks preserved across all 3 bands | **100%** (lossless) |
| **Storage:** compact store vs the source files the loader actually needs | 535,012 B vs 585,293 B = **8.6% smaller** (6.95% if you count the shared supplier files on both sides) |
| **Cold-ish start:** fresh process, load everything, answer all 17 plots | **11.18 ms → 5.80 ms** (about 1.9× faster). Imports are excluded and the OS cache is not controlled, so this is *not* "disk-cold". |
| **Independent validation:** real bugs caught before the demo | null shown as zero; "equal" shown when it wasn't; corruption *outside* the plots missed by plot-only checks; forged-but-rehashed receipts accepted; a smallest-possible (one-ULP) floating-point rounding error that moved a cell across a plot boundary; a stale live answer shown for the wrong rectangle. All were fixed, and each fix has a test that fails on the bad version. |
| **Tests at hand-off** | 198 engine tests and 298 frontend checks pass, plus browser suites and two independent verifiers. |

## What didn't work ❌ (and we kept the evidence)

| Experiment | Outcome | Decision |
| --- | --- | --- |
| Faster queries once data is loaded ("hot") | 1.418 ms original vs 1.446 ms compact: **no speedup** | Say so plainly |
| Is our custom format the smallest? | **No.** A standard GeoTIFF with tuned settings was **0.48% smaller** (532,444 B). For JRC the standard format was **7.3% smaller**. | Show the standard control in the UI. The value is the verified pipeline, not a magic codec. |
| **ML codec selector** (learn which compression to use per patch) | On a sealed held-out region it **lost** to simply picking one fixed setting | Rejected for production; kept as an honest negative result |
| Indexed partial reads from the compact store | Slower than reading the source | Kept full preload for this small region |
| Early bit-packing candidates | Some were **bigger** than the compressed originals | Kept as losing candidates in the chart |
| JRC v3 download | Server error (HTTP 500) | Used JRC v4 instead |
| Agent-swarm organisation | The runtime could not nest agents, capped concurrency at 7, and the user stopped the run early to save usage | The master acted as dispatcher. All of this is recorded in the methodology. |

## What we found 🔎

These are the interesting things to say out loud.

**1. The supplier's declarations don't line up with the layer they cite.** The supplier says it checked *Hansen 2021–2023*. Using that layer and our centre rule:

| | Map shows loss in 2021–23 | Map shows no loss |
| --- | --- | --- |
| **Supplier declared an indication** | none | **P-0003, P-0005, P-0008, P-0010, P-0013** |
| **Supplier declared none** | **P-0001** (38 cells in 2022), **P-0016** (1 in 2023), **P-0018** (1 in 2021) | 9 plots |

There is zero overlap between the two lists.

**2. We tested the two obvious explanations, and neither explains the five declared indications.**
- *Wrong data version?* We downloaded the older **Hansen 2023 v1.11** release (the one current in the supplier's era) and fixed the method before looking at the results. The 2021–23 counts are **identical**.
- *Different boundary rule?* With "any overlap" instead of "centre inside", 337 extra cell memberships appear and five period flags change (P-0014 and P-0015 gain 2021–23 loss; P-0003, P-0004 and P-0019 gain 2024–25 loss). Still none of the five declared indications are reproduced.

So the supplier's result **cannot be reproduced from the layer it names**. This is **not an accusation**. They may have used manual review, a threshold, another layer or a buffer. But it is exactly the problem SystemEarth described: a plot-level decision is only trustworthy if the exact layers, versions and rules behind it can be replayed. That is what Plotline's receipts and fidelity proof are for.

**3. The rule is part of the decision.** Changing only "centre inside" to "any overlap" flips five plot-period answers. A compact format must preserve enough to rerun *the agreed rule*, and the rule has to be written down. Our UI never treats the overlap rule as an on/off toggle.

**4. Using one layer on its own raises far too many alarms; stacking layers answers the actual question.** *(Exploratory; it is not part of the verified engine.)* In this plantation landscape:
- about 43% of land cells show Hansen loss at some point;
- only about **0.4% of the post-2020 loss** falls inside JRC's 2020 forest class;
- P-0001's 38 loss cells from 2022 mostly sit *outside* JRC's 2020 forest, with just 2 of their centres inside it.

Hansen alone would flag rotation harvests as "deforestation". EUDR asks about forest at the 2020 cut-off, which needs the forest-baseline layer stacked on top. That is the multi-layer, multi-year point of the challenge, made concrete. (Method: [`scripts/explore_cross_layer.py`](../../scripts/explore_cross_layer.py), which samples JRC at each Hansen cell centre.)

**5. JRC 2020 says only one of the 17 plots had any forest.** P-0001 has 554 forest cells out of 1,083 JRC cells. The other 16 plots are entirely non-forest in 2020 according to JRC.

**6. On a small region, compression gains are modest, and standard tools are competitive.** The honest engineering conclusion is to pick the format by **measured workload** (interactive plots vs. batch cohorts vs. layer updates) and to *prove* that it preserves every decision. Novelty for its own sake is not the goal.

## Sources

[Results index](../lab/results-index.md) · [research methodology](../lab/research-methodology.md) · [handover](../HANDOVER.md) · [engine report](../lab/engine-report.md) · [vintage study](../lab/engine-vintage-report.md) · [spatial rule study](../lab/engine-spatial-sensitivity-report.md) · [selector study](../lab/engine-selector-report.md) · [validator report](../lab/validator-report.md) · [JRC report](../lab/engine-jrc-report.md)
