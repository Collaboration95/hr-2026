# C2-C task-focused design audit

Owner: resumed Sol W1 / C2-C. New ownership only: this report and `experience-design-evidence/`. Delivered 13 October 2026, approximately 02:28 UTC. Five bounded recommendations below; lead retains strategy and implementation.

## Browser access and early finding

- Read updated assignment, current App/Benchmark/CellTable/CSS, interface, product research, lead report and W3 QA. This cycle does not edit the earlier research files or application.
- Own T3 status succeeded; opened a separate local app tab `tab_l`. Never navigated another worker's tab. Actual desktop viewport was 1536×960 despite a 1280×800 setting.
- Own T3 tablet resize to 834×1112 timed out after 5000ms. The documented fallback condition is met; continue in a separately launched, existing Playwright Chromium instance. No dependency installation or external upload.
- Early observed comprehension issue: P-0003 shows the declared 2021–2023 indication, unavailable reference `hyperlink-RG1-P-0002`, and zero mapped cells. Both period results and complete 87/87 support are available, but the source-vintage explanation is at y1189.5 in 9px text on the 960px-tall initial desktop viewport. This is a placement/readability issue; not a proven declaration error or encoding mismatch.

## What was actually reviewed

Live loopback app, existing Playwright Chromium, isolated contexts at 1440×1000, 834×1112 and 390×844, reduced-motion setting. All three captured the same artifact content hash `9186daad50c07579369b3e918da8a7e72f86958806dce925c96f507344741add`. App, Benchmark, CellTable and app.css hashes were stable across the three-viewport capture. Details and source hashes are in [observations.json](experience-design-evidence/observations.json). These are reproducible expert observations, not a user study or measured time-to-task improvement.

| Journey | Observed evidence | Assessment |
| --- | --- | --- |
| P-0003 declaration → reference → mapped result | Declaration says indication in 2021–2023, then on-site verification with evidence, then deforestation-free/compliant. Reference is `hyperlink-RG1-P-0002`, explicitly unavailable. Current release returns zero cells in both displayed periods, complete support, 87/87 valid/selected, zero unknown. | Truthful content; the explanation that the historical declaration and current release can differ is visually separated from the apparent disagreement. No evidence proves that either source is wrong. |
| P-0005 → 2025 cells → proof → receipt | 262 selected cells; 11 orange year-2025 cells; event-filtered table has 11 rows. Keyboard activation opens an actual cell inspector. Proof shows 11/11 annual and 18/18 period counts. Receipt opens with a named dialog and Escape restores its trigger. | Number-to-proof link works and preserves plot/year values, but the transition loses focus and may arrive below the comparison. Receipt behavior worked in this inspection. |
| Original storage → candidate overhead → method | Current served experiment `exp-26ba2d043721e20e770efc52bd46f9536eb02b494eed7264aa01e3d41cf5f856` chooses `separate_zstd_l19`, 535,012 bytes versus 586,241 baseline bytes. Selecting Original GeoTIFF shows 572.5 KiB; selecting Separate bands shows 574.8 KiB and 0.4% larger, split into payload and metadata/index. Method expands to actual JSON. | The requested original-overall-winner scenario is now historical, not the current UI outcome. The live route still supports inspecting a losing candidate and its overhead. Raw candidate identifiers and technical method text add avoidable reading work. |

The actual archived [original-winning experiment](../../artifacts/experiments/exp-a4ab76966b51b94e381504da38ec59e95c571ded8fd4e14a059359939c5346bd/run-68ee10380a8d6b541b4a5a71db97c63f0e562adc861a779afc7dea0d98745e18.json) records `source_geotiff`, 586,241 bytes, with best exact compact candidate `separate_zstd` at 786,400 bytes. This was read from disk, not replayed as a fabricated live state. Preserve historical experiment scope. A different experiment winner is not evidence of an encoding mismatch; engine binding verification remains outside this critique.

## Five prioritized changes

### 1. P1 — Give proof navigation an explicit reading and focus destination

Reproduce: select P-0005, choose year 2025, open the native-cell table, filter its 11 events, inspect a row, then focus the annual-count proof button and press Enter. At desktop width, the captured transition moved scrollY 564→1409, left focus on BODY and placed the comparison table above the viewport (top −837px). Next Tab reached the receipt button without reading the comparison. [Arrival screenshot](experience-design-evidence/desktop-proof-arrival-viewport.png), [capture](experience-design-evidence/observations.json).

A separate minimal reproduction without opening the cell table confirmed focus on BODY at both widths; at 390px the old scrollY590 persisted and the proof heading began at −141px. Desktop without the table arrived at the top, so the extreme desktop scroll outcome depends on preceding layout/scroll state. [Independent minimal observations](experience-design-evidence/proof-minimal.json), [mobile arrival](experience-design-evidence/390-proof-minimal.png).

Change: on entry, move focus to a programmatically focusable proof heading or selected-year comparison row and bring that target into view. On Back to review, restore the originating count/plot context. Preserve normal Tab order afterward. Expected benefit: the user reaches the basis for the clicked number immediately and knows where keyboard navigation continues. Recheck the expanded-table route; do not rely only on top-of-page Show proof.

### 2. P1 — Put the review reason and source-vintage qualification together

On desktop, the declaration begins at y201 but current-release qualification is at y1189.5; on tablet the entire declaration moves to y1241.8; on mobile its reference begins at y1832.7 on an 844px viewport. The responsive stack presents section 02 before section 01. An analyst must retain the queue's reason while traversing geometry, cells, time and support before seeing the reference. [Tablet](experience-design-evidence/tablet-p3-review.png), [mobile](experience-design-evidence/mobile-p3-review.png).

Change: put a compact plot-specific review summary near the plot header: “Supplier declares a 2021–2023 indication; referenced mitigation evidence is unavailable. Current Hansen 2025 v1.13 query observes no loss in that period.” Include a direct jump to the exact declaration/reference and a short note that release/rule differences remain unresolved. At narrow widths, put this compact summary before the map, retaining the full declaration below. For P-0003, the P-0002 reference suffix remains an unresolved key, not an automatic error verdict. Expected benefit: users understand why this zero-loss plot still requires evidence review without treating source-vintage differences as encoding failure.

### 3. P2 — Increase the type size of evidence-bearing text before adding density

Computed mobile map legend and time-context labels are 7px; tablet legend is 8px. Desktop timing-mode controls are 8px; batch scope, payload values and measurement qualification are 9px. This includes the distinction between full data already loaded and fresh-process load+query. Large promotional headings receive substantially more space than these decision-bearing details. [Computed font evidence](experience-design-evidence/detail-observations.json), [benchmark panel](experience-design-evidence/desktop-benchmark-closed.png).

Change: make evidence labels/method qualifications about 12–14px and retain current larger main values; allow wrapping or a slightly taller panel. On mobile, expose the selected full year and period key legibly instead of shrinking all context to fit 25 year labels. Preserve all years in the control. Fix the tablet heading's observed “What supportsthe final declaration?” join while adjusting that typography. Expected benefit: users can read the units, year and limits that govern interpretation at normal zoom. This is a readability recommendation, not an asserted WCAG font-size failure.

### 4. P2 — Translate measured choices into a short comparison explanation

The served chart displays `separate_zstd_l9` and `separate_zstd_l19` as raw primary names; the 8.7% winner and 0.4% losing candidate are truthful. The method exists in two disclosures, one full benchmark JSON above the chart and one method JSON below it. The current chart tells readers which bar is smaller, but makes them decode identifiers and JSON to explain what changed and what was timed. [Benchmark evidence](experience-design-evidence/desktop-benchmark-closed.png), [observations](experience-design-evidence/observations.json).

Change: label variants “Separate bands · Zstd level 9/19,” retaining exact IDs as secondary selectable text. Place one concise method block beside the comparison: full identical region; payload plus metadata/index; shared inputs excluded on both sides; median of 7 measured batches of 17 plots; loaded versus fresh-process scope; OS cache uncontrolled. Make experiment identity reachable from that block and retain raw JSON. In a historical source-winning experiment, keep the explicit original-wins statement; do not force the current winner to match it. Expected benefit: the analyst can explain candidate overhead and benchmark limits using the visible comparison without interpreting a serialization format.

### 5. P2 — Make overview mode explain locations and retain explicit plot scope

All 17 overview markers have accessible IDs but no visible text or SVG title; the selected P-0003 and P-0001 marker rectangles intersect the map-title overlay. Overview still shows the Annual loss/Canopy/Land mask controls, despite drawing no evidence cells, and its coordinate labels remain bounds of P-0003 rather than the full overview. The cell-table summary says “87 selected” without identifying its plot while the map heading says 17 locations. [Overview screenshot](experience-design-evidence/desktop-overview.png), [marker intersection evidence](experience-design-evidence/detail-observations.json).

Change: reserve space for the overview title; label the selected and hovered/focused markers with plot IDs; label the evidence table “P-0003 · 87 selected cells.” Hide or disable evidence-layer controls in location overview and label coordinates as selected-plot coordinates or use actual overview extents. Keep it a simple spatial index without adding a basemap/service. Expected benefit: the analyst can find a named plot and understands that the nearby cell count belongs to one plot, not the cohort.

## Delivery, reproduction and limits

- Run from repo root: `node docs/lab/experience-design-evidence/observe.mjs`. It uses the already installed Playwright at the documented absolute local path, launches its own headless browser, restricts requests to the loopback origin, captures three viewports and closes every context/browser. No app files or shared QA files are changed. The path is environment-specific, not a new project dependency.
- Successful capture: 2026-10-13 02:26:15–02:26:18 UTC, three viewport journeys, no captured page errors, one shared artifact hash, stable four-file source hashes. These checks establish observations, not a new global accessibility/engine pass.
- First capture assumed the old “14-bit packed” candidate and stopped when it was absent. Corrected the observer to use an actual rendered candidate; the complete successful rerun supersedes that observer failure. No application bug is inferred from the absent historical candidate.
- The P-0005 table filter/cell inspector, receipt keyboard close/return, explicit source-versus-declaration copy and honest overhead display are useful existing behaviors to retain. No invented metric, legal verdict, missing-band result or mismatch witness was added.
- Independent minimal proof and detail-observation snippets were executed locally and their outputs saved in this evidence directory. Screenshots are local company-sample evidence; none was uploaded or published.
- Ready for master relay: prioritize findings 1–2, then integrate 3–5 as small local refinements. W3 can validate the proof return/arrival behavior after the lead fixes it. No app implementation, earlier research, other worker output, package or Git mutation in this cycle.
