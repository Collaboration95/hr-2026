# 3 · What we ship for the hackathon (and what we deliberately don't)

## The product: Plotline

**Plotline lets an analyst follow a supplier's plot declaration back to the map layers, and lets an engineer verify that a compact copy of those layers gives exactly the same answer.**

It is one local app (React + TypeScript, Python engine). It runs offline with no cloud, no API keys and no map-tile service. It has four views:

| View | What it shows | Why it matters for judging |
| --- | --- | --- |
| **Map** | The real Hansen raster as the map. Scrub or play 2001→2025 and watch loss burn in. Toggle canopy 2000, land/water and the JRC 2020 forest overlay. Click a plot to zoom in to its actual ~28 m native cells, with the centre rule drawn as dots. The side panel puts **Declared by supplier** next to **Mapped by Plotline** and ends with a question for a human reviewer. | Multi-layer, multi-year, a specific use case, and a working query, all visible in seconds |
| **Cohort** | All 17 plots × 25 years in a single "loss barcode", plus the declared-vs-mapped matrix. Any cell opens that plot and year. CSV export. | The whole dataset and the headline finding on one screen |
| **Proof** | Leads with **"Keep the decision, not the data"**: the 6.1 KB decision layer (99% smaller), 744,732/744,732 cells identical, registered plots 44× faster, the layer ladder, what we dropped and why, and the standard-format control. Below it is the lossless audit tier: 17/17 identical, 100% pixel fidelity, every losing candidate, and receipts. | Directly answers the brief's evaluation list: layer analysis, storage, speed, resources, decision fidelity, pixel fidelity |
| **Live query** | Ask a new region (an exact plot or a rectangle) and get a fresh original-vs-compact answer with cell evidence and a downloadable receipt. | Proves it is a working system, not a slideshow |

## In scope (done)

- Hansen 2025 v1.13: three bands, 25 annual loss years, 17 real plots, compact store plus original path, an exact fidelity proof and receipts
- JRC 2020 v4 forest baseline as a separate, verified companion layer
- Measured storage, hot/cold timing, CPU and memory, with the standard-format control and the losing experiments kept
- An infrastructure cost estimate (bonus) at list-price assumptions for one tile, the tropical belt and global land: [`cost-v1.json`](../../artifacts/decision/cost-v1.json)
- A local live-query API with bounded limits
- Tests and verifiers, reproducible setup (`scripts/setup-local.sh`, `scripts/verify-local.sh`) and a recorded walkthrough
- **Decision layers (15 Oct):** layer analysis; screening and decision layers with an exhaustive cell proof, fuzzing, a registered-plot index and answer table; whole-tile storage; a cost estimate; independent validation. Four speed-up phases followed over 15 and 16 Oct (faster decode, reduction and selection; a batch evaluator and a numpy-free re-check; a faster shared reducer; a leaner reducer entry and a better scan rule), plus a research pass, with no change to any output. See the [report](../lab/decision-layer-report.md).
- **New today:** the redesigned UI (see [design decisions](05-redesign-decisions.md)) and a reusable design system for slides, videos and HTML writeups ([`design/`](../../design/DESIGN.md))

## Deliberately out of scope

These are good scope cuts and can be said proudly.

| Not built | Why |
| --- | --- |
| A legal "compliant / non-compliant" classifier | The challenge is about *preserving* decisions, and nobody gave us the company's legal rule set. A fake verdict would be a liability. |
| An AI risk score trained on supplier declarations | The declarations aren't ground truth, and our learned codec selector already showed ML must earn its place on measurements. |
| Protected areas (WDPA) | Licence terms are unclear |
| Cloud deployment, global scale, monitoring | Not asked for in a one-week slice. The 17-plot workload can't justify global performance claims. |
| A new compression algorithm | Explicitly not required. Our decision-layer encoding (bit-planes + sparse loss events) is 28% smaller than a plain GeoTIFF of the same codes, but most of the win is the layer analysis. |
| RuleLens (an interactive explainer of centre vs overlap rules) | The research is done but the UI is unbuilt. Optional. |

## Still open (needs humans, not code)

**From SystemEarth:**
- Which layer version and inclusion rule did the supplier's analysis actually use?
- What is behind `hyperlink-RG1-P-0002`?
- What is the representative workload: one plot at a time, big batches, or re-checking after layer updates?

**From the organisers:**
- The submission channel and deadline (the challenge page says 17 Oct 00:00 SGT, but it's unclear whether that is the application or project deadline)
- Pitch length and format, whether it's in person or online, and who presents

**Data use:** confirm that the supplied sample may appear in slides. It is no longer in the repository: on 15 Oct the repository was made private and the sample and its derived copies were removed from git history (see the README).

## How to run it

```sh
scripts/setup-local.sh            # first time only
scripts/verify-local.sh           # re-checks the retained proofs and builds
npm run dev:local --prefix app    # app at :5173, live API at :8765
# other ports: PLOTLINE_WEB_PORT=5183 PLOTLINE_LIVE_PORT=8766 npm run dev:local --prefix app
```

Useful deep links: `#/map/P-0001/2022`, `#/cohort`, `#/proof/P-0005/2025`, `#/live`.
