# 5 · Redesign decisions (15 October 2026)

You asked for the UI to be designed first and then implemented, with Sonnet 5.5 subagents doing the implementation, and for me to make the decisions and write them up. This is that record.

## The diagnosis of the old UI

The old app worked and was rigorous, but for a three-minute pitch:

- **There was no sense of place.** The plot floated on a beige grid. Nothing said "geospatial, multi-layer, multi-year" at a glance.
- **Every panel repeated a 2–3 line disclaimer.** The truth was there, but it was buried.
- **The best finding was invisible.** Declared vs mapped never appeared side by side across the cohort.
- **Proof numbers were spread across long text blocks.**

## The decisions

| # | Decision | Why |
| --- | --- | --- |
| 1 | **The basemap is the actual Hansen raster**, packed losslessly into a PNG and recoloured in the browser (no tiles, no photos, no API keys) | It is the data we encode, so it's honest. It looks striking and works offline. Zooming in shows the real ~28 m native cells, so the encoding is literally visible. |
| 2 | **A year scrubber with ▶ play** (2001→2025), with the EUDR cut-off and the supplier's 2021–23 window marked | It turns 25 layers into one gesture: you watch loss burn in. The timeline carries the regulatory story too. |
| 3 | **Stackable layers** (loss, canopy 2000, land/water, + JRC 2020 forest overlay on its own grid) | It shows "multi-layer" instead of describing it. The JRC overlay makes the plantation-vs-forest insight obvious. |
| 4 | **Two accounts, side by side**: ◆ *Declared by supplier* (lilac) next to ■ *Mapped by Plotline* (ember), ending in an amber *Question for review* | It keeps the strict rule (no verdicts) but makes the gap the hero. The questions are generated from data via fixed templates. |
| 5 | **One hue per meaning**: lilac = declared, ember = loss, mint = forest, lime = proof, amber = question, red = failure only, hatched = unknown | Colour carries meaning consistently in the app, slides and videos. Red is never used on a supplier. |
| 6 | **Cohort becomes a "loss barcode"** (17 × 25 heat-table) plus the declared-vs-mapped matrix | The whole dataset and the headline finding fit on one screen, and every cell still opens its plot and year. |
| 7 | **Proof leads with five big numbers**, each with its exact boundary in an ⓘ popover, and keeps every losing candidate and the standard-format control | It answers the judges' checklist directly while staying honest. |
| 8 | **Landing page = region overview**, not a hard-coded plot | First impression: the place, then "pick a plot". Suggested starting plots are chosen from data. |
| 9 | **Hash routes** (`#/map/P-0001/2022`, `#/cohort`, `#/proof/…`, `#/live`) | They give deep links for the demo, recordings, tests and future videos. |
| 10 | **Dark "Night survey" theme**, plus a **paper** light variant for writeups | Dark makes the raster glow on a projector and in video, while paper suits print and HTML writeups. Both share the same tokens. |
| 11 | **Caveats said once** (ⓘ popovers, a single legend, short labels) | They keep their meaning without the noise. |
| 12 | **System fonts only, no new dependencies** | The demo runs offline and stays reproducible. |

**Kept exactly:** all validation boundaries (`data.ts`, `jrc-data.ts`, `live-client.ts`), unknown ≠ zero, the separate JRC semantics, live-query lifecycle and race handling, the analyst-note storage format, receipt payloads, keyboard shortcuts (J/K, `/`, ⌘K, Esc) and CSV export semantics.

**Deliberately not added:** RuleLens, cost estimate, map drawing for live queries, an AI risk score, and any combined Hansen+JRC verdict.

## The design system (for videos and writeups later)

- `design/DESIGN.md`: the spec, including principles, colour meanings, screens, copy rules and truth-state rules.
- `app/src/styles/tokens.css`: every colour, type size, spacing value and motion value. Use `data-theme="paper"` for light pages.
- `design/style-guide.html`: a living style guide with a **reusable 16:9 map hero frame** drawn from the real raster, plus a year slider, play button and JRC toggle. Serve the repo root (`python3 -m http.server 8090`) and open `/design/style-guide.html`.

## How it was built

1. I (Claude Opus) read the brief, the data, the research and the old UI. I wrote the spec, tokens, base styles, shared primitives, shared plot-fact logic and the raster packer, then stubbed every cross-module interface so parallel work would compile.
2. **Five Claude Sonnet 5.5 agents** built in parallel, each owning separate files: map, app shell, inspector, cohort + proof, and live + JRC.
3. Then integration review, a test-update pass and verification (results below).

## Verification

*To be completed after integration; see the session summary.*
