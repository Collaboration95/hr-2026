# Plotline demonstration — evidence before verdict

> **Superseded for the redesigned UI (15 October 2026).** Use the three-minute flow in [docs/writeups/04-pitch.md](../writeups/04-pitch.md); `npm run demo:record --prefix app` records that flow. The narration below describes the pre-redesign screens, but its interpretation rules still apply.

Updated 14 October 2026. Illustrative three-minute core plus a one-minute live/JRC extension, not a claimed organizer pitch duration. The recorded user authorization covers the tracked GitHub repository; confirm organizer logistics separately. Retained measurements are frozen. Use the displayed values and their accounting boundary.

Fallback: silent recorded walkthrough (`completion-demo.webm`, kept local, not committed: it shows supplier plot outlines), with [chapter timestamps](completion-demo.json). It shows actual local responses and can accompany the narration below if the live environment fails.

## Preparation

From repository root:

```sh
scripts/setup-local.sh  # First setup only; installs dependencies
scripts/verify-local.sh
npm run dev:local --prefix app
```

Open http://127.0.0.1:5173/. Use P-0003 initially, year 2023, Review desk. Confirm all 17 plots and that the benchmark is the engine-approved bound export. Close any local analyst draft created during QA or use a fresh browser context. The app uses exact supplied polygons and real native-grid cells, no invented imagery.

## 0:00–0:35 — Explain the analyst task

“Plotline helps an analyst follow a supplier declaration back to evidence, while checking whether a smaller representation preserves the answer.”

Show the five indication→mitigation declaration records. Open P-0003. Read its supplier-declared indication, on-site verification with evidence, final deforestation-free/compliant declaration and opaque `hyperlink-RG1-P-0002` key. The evidence file is not supplied. The current query sees no 2021–23 mapped loss among 87 selected native cells, but that does not invalidate a historical declaration: source release, query rule and referenced evidence still need clarification.

Use the review summary/declaration jump rather than scrolling past the entire evidence stack on mobile. Do not call the five records violations or satellite conflicts.

## 0:35–1:10 — Link year, cells and exact values

Open Evidence index, keep the 2024–2025 view, and click the 11-cell observation for P-0005 in 2025. The app returns directly to that plot and year. Its actual source query selects 262 native cells; 11 loss events in 2025 and 7 in 2024 sum to 18 in 2024–25. Show the matching orange cell footprints and the native-cell table’s 2025 filter. Inspect one actual row/cell; canopy is 2000 context, and a raw loss code becomes a year only on valid supported land.

“Each square is a native source cell whose center is covered by this exact supplied boundary. Footprints can extend across the boundary. These are observed cell counts, not hectares or a legal land-use conclusion.”

## 1:10–1:50 — Make the engineering proof inspectable

Click the observed-cell count. The selected-year comparison is the focus destination. Original and compact 2025 counts agree; full query outputs, histograms, masks, unknowns and both periods are compared. The current real cohort has 17 exact matches, but the final retained export/verifier remains the source for that claim.

Open the named receipt. Use its readable disclosures to show the exact supplier fields, source product/version, native grid, cell-center rule, input/geometry/supplier hashes and store provenance. Raw JSON remains available below. Download the receipt JSON locally if useful. A hash is an integrity identifier, not a source-accuracy or compliance certificate.

## 1:50–2:35 — Explain the measured tradeoff honestly

Open measured tradeoffs. Choose Original GeoTIFF, then a losing compact candidate, then the experiment's retained candidate. The bars include payload and metadata/index overhead over identical support. The retained custom store is 535,012 B versus 585,293 B of necessary supplied source inputs: 8.59% smaller at that boundary. The stronger standard control is 532,444 B, which beats custom size by 0.48%. This is a measured choice, not a universal custom-codec win.

Switch Loaded query and Fresh-process load+query. Hot 17-query medians are 1.418 ms source and 1.446 ms compact: no hot-query speedup is established. Fresh-process full load plus 17 queries is 11.182 ms versus 5.800 ms, excluding imports/common geometry and with uncontrolled OS cache. State the batch scope, repetitions, units and cache limitation. Do not call the second disk-cold, treat tiny timing differences as significant, compare the crop to whole source tiles, or claim global-scale performance from 17 plots.

## 2:35–3:00 — Show an honest limit and next action

If time allows, open the clearly separated synthetic support lab: Partial support/no event remains unknown; a witnessed positive remains observed with the unknown support exposed. These fictitious fixtures are not additional suppliers or real fidelity evidence.

Return to the supplier declaration. Optionally save a local analyst question: ask what evidence and query rule support the final declaration. Notes remain a local annotation, not a change to source records or legal outcome.

Close: “The useful result is an inspectable answer with its limits, and a measured representation choice. The next company conversation is about the missing mitigation evidence and source/rule meaning.”

## Recovery paths

- If the compact/benchmark export is absent, show Unavailable and explain exactly what is not computed. Never substitute a rehearsed number.
- If runtime validation rejects an artifact, show the error, keep the last accepted data, and rerun the engine-approved export/sync. Do not bypass the validator for the pitch.
- If a source/compact mismatch exists, show the actual differing fields; do not invent a witness pixel or present agreement.
- If browser automation fails, the app can be reviewed manually at loopback. Record that automated check as unavailable rather than passed.

## Longer analyst walkthrough

The evidence index is useful when a reviewer asks for the whole cohort rather than one example. Its three period views expose actual source counts, and its declaration column remains separate. In the current fixture, the five supplier-declared indication/mitigation records and the five plots with mapped 2024–25 loss are different sets; equal group sizes do not establish correspondence. Positive counts open their exact plot/year. Export displayed counts only as a local CSV, with source/query context and explicit unknowns.

The accepted JRC companion is available in the separate disclosure below Hansen review. P-0003 has 793 mapped class-0 cells; P-0001 has 529 class-0 and 554 class-1 cells on the separate JRC grid. Explain its 2020 reference year, v4 source classes and separate proof. Non-forest does not mean no tree canopy. Never compare JRC and Hansen cell counts as common-area quantities or extend the Hansen compression percentage to the companion.

## One-minute live-query and JRC extension

Start the verified local API and app with `cd app && npm run dev:local`. Open Query lab from P-0003 and run the exact supplied polygon. Compare its real original/compact output with the frozen review, inspect the complete native-cell evidence and download the bound live receipt. Explain that this is a temporary read-only query on one immutable source/store snapshot, not an edit to supplier records.

Choose Temporary rectangle and explicitly use the plot bounds. Run again to see the actual changed selection; do not predict a loss result before computing it. The form is fully usable without drawing. Editing the bounds clears the prior answer. Demonstrate Cancel only while a request is active; if the request is already complete, do not pretend cancellation happened.

If the optional API is unavailable or receipt binding fails, show that state and return to the frozen Review desk. Single-request preloaded timings are not a benchmark or speedup claim. The live production rule remains cell-center inclusion; the separate overlap study is not a production toggle.

## Submission handoff

Use the branch `guru/plotline-research-lab`, root README for setup, this script for narration, [completion checks](completion-verification.json) for the latest evidence, and [HANDOVER](../HANDOVER.md) for technical detail. The repository and recording are ready to review; no organizer submission or company message has been sent.

The printed prototype gate is met for the stated evidence-screening slice: three aligned Hansen bands across annual loss observations, compact storage, exact original/compact queries, full raw/mask checks, and measured storage/query/resource comparisons. The separate JRC baseline has its own proof. No legal compliance classifier is claimed. RuleLens and cost estimation are optional and are not required to run this demonstration.

Before the final pitch, the team still needs the confirmed submission channel/deadline, presentation length and attendance details, plus a named presenter. SystemEarth should confirm its historical layer/rule and explain one mitigation reference. Those are human handoffs, not unfinished app features.
