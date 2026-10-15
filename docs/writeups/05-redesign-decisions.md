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

1. **Design and contracts (Claude Opus).** I read the brief, the data, the research and the old UI. Then I wrote the spec, tokens, base styles, shared primitives, the shared declared/mapped logic (`review/plot-facts.ts`) and the raster packer (`app/scripts/render-region.py`, which reads its own PNG back and checks every pixel against the source). Every cross-module interface was stubbed first so parallel work compiled from minute one.
2. **Implementation (5 × Claude Sonnet 5.5, in parallel, disjoint files):** map, app shell, inspector, cohort + proof, and live + JRC.
3. **Your mid-session instruction:** you asked that workhorse work go to subagents, with **GPT-6.1 Sol** preferred over Sonnet. The two Sonnet test agents had just restarted after a usage limit and had written nothing, so I stopped them and relaunched the remaining work on Sol:
   - one rewrote the frozen-review browser suites and added a new redesign suite;
   - one rewrote the live and JRC suites and the demo recorder;
   - one did a visual QA and polish pass across 5 viewports and 76 screenshots.
4. **Review and integration (me):**
   - A design review of screenshots, which gave the issue lists handed to the agents.
   - A few direct fixes: the supplier dates restored to the Declared column, no focus box on programmatically focused headings, the JRC toggle state, the plot-view legend collapsed by default, and 12px phone year labels (a real bug the tests caught).
   - Loss cells now go translucent under the JRC overlay, so the "was this 2020 forest?" question can be read off the map.

## Verification (15 October, on `guru/plotline-ui-redesign`)

| Check | Result |
| --- | --- |
| TypeScript (`npx tsc -b`) | clean |
| Frontend checks (`npm test --prefix app`) | **298 / 298** |
| Frozen browser suites (`qa:browser`) | **66 / 66**: review 18, cycle3 14, index/receipt 11, index 3, overview 3, **new redesign suite 17** |
| Actual-service live suite (`qa:live`) | **15 / 15** |
| Integrated JRC suite (`qa:jrc`) | **13 / 13** |
| `scripts/verify-local.sh` | pass: Hansen and JRC verifiers, P-0003 full and indexed source = compact, and the production build |
| Display raster exactness | Browser-decoded bands hash-equal the source GeoTIFF bands (map agent), and the new suite checks the browser decode against the PNG bytes |

The new redesign suite checks:
- deep links and back/forward;
- the exact decode of the display raster;
- that the region scrubber totals equal pixel counts computed in Node;
- scrubber and native-cell counts against the JSON (P-0001/2022: 121 cells and 38 events; P-0005/2025: 262 and 11);
- that every plot lands in the right matrix cell;
- rail filter counts;
- the JRC overlay state;
- Esc back to the region view;
- no horizontal page overflow at 390px on every route.

Every old assertion was ported to an equivalent check on the new design. None were deleted to get a pass. The written audit (old check → new check → why) is in each run's QA output and in the test reports.

**Demo fallback video:** [`docs/lab/redesign-demo.webm`](../lab/redesign-demo.webm), with [chapters](../lab/redesign-demo.json). It is 55 s at 1440×900 and was recorded against the real app and API. It follows the pitch flow: region playback, JRC overlay, P-0001's two accounts, the cohort, P-0005 proof, the receipt, then a live query. It was recorded just before the last two visual tweaks; re-record with `npm run demo:record --prefix app` if you want those included.

## Known limits

- Touch devices can't pan or zoom the map, although tap, Region and Fit plot all work. The rail and tables are the full non-map path.
- Native cells on the map are not individual Tab stops. Keyboard access to them is through the inspector's Native cells table.
- The JRC overlay and hover tooltip are display-only renderings of the source raster. All counts shown as evidence come from the validated exports.
- Exploratory cross-layer figures, such as "under 1% of post-2020 loss in 2020 forest", come from `scripts/explore_cross_layer.py`. They are not in the app as verified results.
