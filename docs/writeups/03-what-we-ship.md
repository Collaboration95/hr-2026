# 3 · What we ship for the hackathon (and what we deliberately don't)

## The product: Plotline

**Plotline lets an analyst follow a supplier's plot declaration back to the map layers, and lets an engineer verify that a compact copy of those layers gives exactly the same answer.**

It is one local app (React + TypeScript, Python engine). It runs offline with no cloud, no API keys and no map-tile service. It has four views:

| View | What it shows | Why it matters for judging |
| --- | --- | --- |
| **Map** | The real Hansen raster as the map. Scrub or play 2001→2025 and watch loss burn in. Toggle canopy 2000, land/water and the JRC 2020 forest overlay. Click a plot to zoom in to its actual ~28 m native cells, with the centre rule drawn as dots. The side panel puts **Declared by supplier** next to **Mapped by Plotline** and ends with a question for a human reviewer. | Multi-layer, multi-year, a specific use case, and a working query, all visible in seconds |
| **Cohort** | All 17 plots × 25 years in a single "loss barcode", plus the declared-vs-mapped matrix. Any cell opens that plot and year. CSV export. | The whole dataset and the headline finding on one screen |
| **Proof** | "Same question, two representations": 17/17 identical, 100% pixel fidelity, storage and timing with their exact boundaries, every losing candidate and the standard-format control, the research summary, and receipts. | Directly answers the brief's evaluation list: storage, speed, resources, decision fidelity, pixel fidelity |
| **Live query** | Ask a new region (an exact plot or a rectangle) and get a fresh original-vs-compact answer with cell evidence and a downloadable receipt. | Proves it is a working system, not a slideshow |

## In scope (done)

- Hansen 2025 v1.13: three bands, 25 annual loss years, 17 real plots, compact store plus original path, an exact fidelity proof and receipts
- JRC 2020 v4 forest baseline as a separate, verified companion layer
- Measured storage, hot/cold timing, CPU and memory, with the standard-format control and the losing experiments kept
- A local live-query API with bounded limits
- Tests and verifiers, reproducible setup (`scripts/setup-local.sh`, `scripts/verify-local.sh`) and a recorded walkthrough
- **New today:** the redesigned UI (see [design decisions](05-redesign-decisions.md)) and a reusable design system for slides, videos and HTML writeups ([`design/`](../../design/DESIGN.md))

## Deliberately out of scope

These are good scope cuts and can be said proudly.

| Not built | Why |
| --- | --- |
| A legal "compliant / non-compliant" classifier | The challenge is about *preserving* decisions, and nobody gave us the company's legal rule set. A fake verdict would be a liability. |
| An AI risk score trained on supplier declarations | The declarations aren't ground truth, and our learned codec selector already showed ML must earn its place on measurements. |
| Protected areas (WDPA) | Licence terms are unclear |
| Cloud deployment, global scale, monitoring | Not asked for in a one-week slice. The 17-plot workload can't justify global performance claims. |
| A new compression algorithm | Explicitly not required. A standard format is within 0.5% of ours. |
| Infrastructure cost estimate | A bonus item. Do it only if there's time after the pitch is solid. |
| RuleLens (an interactive explainer of centre vs overlap rules) | The research is done but the UI is unbuilt. Optional. |

## Still open (needs humans, not code)

**From SystemEarth:**
- Which layer version and inclusion rule did the supplier's analysis actually use?
- What is behind `hyperlink-RG1-P-0002`?
- What is the representative workload: one plot at a time, big batches, or re-checking after layer updates?

**From the organisers:**
- The submission channel and deadline (the challenge page says 17 Oct 00:00 SGT, but it's unclear whether that is the application or project deadline)
- Pitch length and format, whether it's in person or online, and who presents

**Data use:** confirm that the supplied sample may appear in a public repo or slides.

## How to run it

```sh
scripts/setup-local.sh            # first time only
scripts/verify-local.sh           # re-checks the retained proofs and builds
npm run dev:local --prefix app    # app at :5173, live API at :8765
# other ports: PLOTLINE_WEB_PORT=5183 PLOTLINE_LIVE_PORT=8766 npm run dev:local --prefix app
```

Useful deep links: `#/map/P-0001/2022`, `#/cohort`, `#/proof/P-0005/2025`, `#/live`.
