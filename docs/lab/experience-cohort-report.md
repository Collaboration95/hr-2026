# C3-A cohort/year evidence index

Completed 2026-10-13 03:03 UTC; ready for head review. Owned writes: `app/src/CohortIndex.tsx`, `app/src/styles/cohort.css`, this report. Prior C2-B ownership has ended. No App/types/package/engine/canonical/test/Git changes.

## Component contract and integration

Default export `CohortIndex({data,onReview}:{data:Demo;onReview:(plotId:string,year:number)=>void})`. Imports its own scoped CSS and existing Icon primitive. Receives validated frozen props; no fetch, source writes, engine query, dependencies, or inferred compliance status.

Initial view is 2024–2025; controls switch to 2021–2023 or all 25 years (2001–2025). Rows are sorted by exact plot ID. Every positive observed count calls `onReview` with its exact plot/year. Plot-ID buttons select the latest positive year in the displayed range, or its final year if no positive observation exists. The rule is stated next to the table. Head owns navigation/focus after callback; no global keyboard listener or focus transfer is added by this component.

Native table caption, row/column/group headers, a keyboard-focusable horizontal-scroll region, sticky plot identity, and visible actual numbers preserve navigation without adding a tab stop for each zero/unknown cell. Declared supplier indication is a separate column with the supplied value. Observed zero, unknown/null and partial support retain separate text. Partial zero never claims absence; positive observations remain inspectable.

Overview numbers derive only from displayed source counts: plots with positive observations, summed available counts (Unavailable if none exist), and incomplete/unavailable-support plots. Per-plot sums can repeat native cells across overlapping polygons; the explanatory text excludes unique regional counts and hectares. All navigation is labelled frozen-export navigation.

CSV exports only the displayed plot/year rows with source product, query version, optional artifact digest, support, explicit Unknown values, and a separately named declared supplier field. Quoted CSV preserves commas/newlines/quotes; potentially active spreadsheet prefixes in text are escaped and that escape is disclosed. Export is a local Blob download; success text says download requested, not that a disk save was verified. Preparation failure reports a retryable error.

## Verification results

- `app/node_modules/.bin/tsc --noEmit --incremental false -p app/tsconfig.json` passed after implementation and final formatting. Existing app-local Prettier formatted only the two owned implementation files.
- Browser policy: T3 `preview_status` succeeded; `preview_open(reuseExistingTab:false)` created worker-owned `tab_q`. First component-harness `preview_evaluate` returned `Preview automation evaluate failed on client preview-3e4509251db44438efef862a7d28574e.` A separate Playwright context will be used under the permitted actual-failure fallback. No shared tab navigation.
- Inline Node harness used app-local `esbuild` with `write:false`, app-local Playwright 1.63.0, `PLAYWRIGHT_BROWSERS_PATH=app/.cache/playwright`, a fresh Chromium context and an isolated render. Loaded current system.css, app.css and cohort.css together to expose integration-style conflicts. Canonical and synthetic JSON were read once for fixtures; each test fixture passed `validateDemo` before rendering. No new test files, screenshot artifacts, downloads, source writes or external requests. Browser context and browser closed in `finally`.
- **23 grouped browser checks passed, 0 failed, 0 browser page errors** in the final run. The accepted real artifact was `d22b0cac287de0d12b1ecfdcf114aa549a886b86299ca8cd43384c6ff2e075b2`.
- Exact 17 plot rows, exact separate supplier indication strings, and exact source values for 34 cells in 2024–2025, 51 cells in 2021–2023, and all **425 cells** in 2001–2025. Both displayed overview numbers were independently calculated from those source values in each view.
- All **37 positive plot/year buttons** in the accepted artifact called the exact expected plot/year. All 17 plot-ID buttons followed the disclosed latest-positive/final-year rule. All 25 year headers were present; no zero or unknown cell had a button/tab stop. Keyboard Enter activated period controls and positive observations.
- At **1280, 768 and 390 CSS px**, document width stayed within the viewport, the full-year table scrolled within its region, and measured evidence labels were at least 12px. ArrowRight scrolled the focused region; plot identity stayed fixed when moving 800px horizontally on mobile. Reduced motion followed the system's effectively zero 0.01ms important-rule duration.
- Validated declaration-only fixture displayed 34 Unknown cells in the default period, no numeric-zero substitution and an Unavailable sum. Validated `partial_absence_unknown` retained observed zeros and an explicit absence-unknown qualification; `partial_positive_known` retained its positive 2024 observation and partial-support accessible label. These were in-memory synthetic controls, never added to canonical data or real overview measures.
- CSV check intercepted the Blob and prevented disk download: exact period filename, 51 displayed plot/year records, known zero, explicit Unknown, source/query/content context, embedded commas/quotes/newlines, escaped spreadsheet formula prefix, and readable export-preparation failure. This validates prepared content and the request action; it does not claim a saved file.

First browser run found document overflow despite a bounded table: absolutely positioned screen-reader labels inside offscreen cells extended the initial containing block. Fixed by positioning `.cohort-table-scroll` relatively. The complete responsive checks then passed. A later harness assertion expected literally zero transition duration; inspection showed the pre-existing system reduced-motion rule intentionally uses 0.01ms with `!important`, so the assertion was corrected to its effective-zero threshold. No product behavior was weakened to satisfy the test.

## Head handoff

Read-only inspection at completion shows head has imported CohortIndex into App and wired `onReview` to select the supplied plot/year and return to the review view. The integrated app typecheck passes. Worker has not changed App or independently claimed an end-to-end integrated navigation/focus pass; that remains head/W3 scope.

No component blocker or dependency request. Keep passing the accepted `Demo`; the component intentionally reads `source_result.yearly_loss_counts`, never supplier declarations or comparison flags as substitute counts. Head should retain its focus-management behavior for index entry and callback arrival. The component's own period controls are local state and default to 2024–2025 on a fresh mount.
