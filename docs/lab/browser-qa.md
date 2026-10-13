# W3 browser and interaction QA

## Current cycle3 verdict — 02:41 UTC

**14 focused browser checks pass after the lead increased mobile year labels.** Proof count arrival/return, local notes, all six separate synthetic cases and revised overview controls/coordinates are verified. **Residual P2 visual issue:** overview title still overlaps P-0003 and P-0001 markers; see cycle3 final delivery. Earlier18-check results are historical and were not blindly rerun.

## Latest verdict — live QA complete, 2026-10-13 02:20 UTC

**18 live checks passed, 0 failed** after lead fixes. The three observed implementation issues (unnamed dialog, commands search focus, and mobile map clipping) are resolved in the tested live build. W3 changed only its harness/report/evidence paths. Lead owns all implementation fixes. See final delivery below; earlier pending/blocker entries are historical.

## Early status — 2026-10-13 01:59 UTC

- Owned writes only: `app/tests/`, `app/scripts/browser-check.mjs`, this report, and `docs/lab/browser-evidence/`. No package or application edits, Git mutations, uploads, or publication.
- Read actual AGENTS, README, charter, interface-v1, worker assignment, and SystemEarth sections of the printed, spoken, and kickoff references.
- Blocker: `docs/lab/experience-report.md`, `app/`, and `artifacts/demo-v1.json` were absent at initial inspection. No endpoint is announced. A real journey cannot yet be exercised; this is not a passing browser result.
- T3 tools discovered through ALL_TOOLS. `preview_status` succeeded and identified an unrelated existing forest-map tab. `preview_open` with a separate background blank tab returned an actual automation-open failure. No existing tab was navigated, and no fallback browser was used. Retry T3 with the lead's actual HTTP endpoint once announced.
- Independent preparation underway: Node built-in contract validator and repeatable HTTP/data harness, followed by browser checks grounded in the delivered interface. Node is v26.3.1. No browser dependency is currently installed in the app.

## Lead action

- Publish the ready loopback endpoint and run command in `docs/lab/experience-report.md`.
- Retain accessible names for search, plot selection, year/period, proof, and receipt controls so journey checks can use the real semantic interface.
- No dependency request yet. A future automated browser runner needs an already installed browser driver or lead-owned package addition; T3 can provide immediate real-browser feedback without package changes.

## Required real-browser checks

- Follow queue → actual plot → year/period → source/compact proof → inspectable receipt. Record selected plot identity, displayed period counts, agreement, provenance, and any console/network errors. Compare against actual JSON, not mock outcomes.
- Enter a query absent from all actual plot fields. Verify explicit zero results, selection behavior, and recovery after clearing it.
- Inspect a narrow 390px viewport for horizontal overflow and reachable map, proof, and receipt controls; restore desktop viewport afterward.
- Use Tab/Shift+Tab and Enter/Space on the actual controls; check visible focus, logical order, modal focus/escape if the interface provides dialogs, and return focus after closure.
- Emulate reduced motion if the browser tooling supports it; otherwise explicitly record that live emulation was not performed and inspect the CSS independently.
- Save screenshots only within the assigned evidence folder after a real page is ready. Do not claim screenshots, outcomes, metrics, or data that have not been observed.

## Evidence semantics

- Supplier fields are declarations. Hansen mapped tree-cover loss is not a legal deforestation verdict; canopy2000 is not forest2020.
- A partial/no-data absence stays unknown. A witnessed positive can be true under partial support. Complete known support plus valid land is required for false.
- Source/compact equality proves representation agreement only. Null/unmeasured benchmark fields must remain unavailable.

## First bounded delivery — 2026-10-13 02:01 UTC

- Added `app/tests/contract-check.mjs`: read-only v1 artifact checks for IDs, supplier string preservation, counts/histograms/year/period consistency, unknown semantics, actual equality versus advertised equality, digest shape, and explicit unmeasured benchmarks. This does not independently requery rasters or recompute engine hashes.
- Added `app/tests/contract-check.test.mjs`: eight Node built-in regression tests using explicitly synthetic contract fixtures. Tests cover complete absence, partial unknown, partial witnessed positive, missing bands, unsupported claims of equality, type coercion, inconsistent counts, duplicates, and malformed input.
- Added `app/scripts/browser-check.mjs`: dependency-free real-artifact/HTTP checker. HTTP requests are restricted to explicit loopback addresses, do not follow redirects, and time out after 10 seconds. When both file and URL are supplied it checks that the frontend copy equals the canonical artifact. It always reports `browserJourneyTested: false` so static success cannot be mistaken for an interaction pass.
- Verified `node --test app/tests/contract-check.test.mjs`: **8 passed, 0 failed**. Verified CLI help. Running the default artifact check correctly exits 1 with the missing canonical-file diagnostic; this is an observed blocker, not a dataset failure.
- During preparation, lead-owned package/types/sync files appeared. No browser driver is declared in `app/package.json`. The sync script can publish a declaration-only fallback with null computed fields; the full v1 validator will reject that fallback as incomplete evidence, deliberately. It must not be described as a complete engine proof.
- No live endpoint has yet been announced in the required experience report. No screenshots or real-browser results are claimed.

## Commands for lead/master

Run from repository root:

```sh
node --test app/tests/contract-check.test.mjs
node app/scripts/browser-check.mjs --file artifacts/demo-v1.json
node app/scripts/browser-check.mjs --file artifacts/demo-v1.json --url http://127.0.0.1:5173
```

Lead may add a package script such as `"qa:contract": "node --test tests/contract-check.test.mjs"`; no dependency addition is necessary for this deliverable. The CLI's default file path is relative to repository root; a script run from `app/` should explicitly pass `--file ../artifacts/demo-v1.json`.

## Next actionable checkpoint

Publish the ready endpoint in the experience report and request W3 follow-up via master. Retry `preview_status` then `preview_open` with the actual HTTP endpoint; exercise the real semantic controls and save evidence under `docs/lab/browser-evidence/`. Add repeatable interaction checks only after inspecting the real DOM. Browser verdict remains **pending**.

## Live QA early findings — 02:14 UTC

T3 status/open succeeded with actual endpoint; W3 exclusively uses `tab_i`, never lead `tab_h`. Canonical/served JSON validation passes. P-0005 via J, year2024 click, Tab+Enter→2025: 262 native cells, 7/11 highlighted loss cells, period total18 all match JSON. Proof table and 17/17 summary agree. Expanded receipt equals actual plot receipt; Escape closes and returns visible focus to its opener.

**Action for lead (P2): give the dialog an accessible name.** Live `dialog` has neither aria-label nor aria-labelledby. Add an ID to the existing title and aria-labelledby on dialog, with a clear receipt/commands title. Native modal behavior works; naming is missing.

Responsive check in progress: T3 resize of own tab to390×844 timed out after5000ms, matching lead failure; this is a tool limitation, not an app pass. Desktop and receipt screenshots saved in browser-evidence. More journey/empty-search findings follow.

### Browser transport blocker — 02:15 UTC

After the second bounded resize attempt (iPhone12Pro preset,5000ms), T3 reported no available automation host and instructed no retry. Further calls already queued in that tool batch also failed; none of the planned empty-search/commands actions executed. Stopped T3 use. Checking an already installed local browser fallback; no package changes or installation authorized to W3. Initial T3 screenshots/verified journey remain valid.

### Live fallback findings — 02:17 UTC

Used pre-existing Playwright1.63.0 at `.npm/_npx/e41f203b7505f1fb/node_modules/playwright/index.mjs` and cached Chromium in an isolated headless context after T3's actual failure. No installation/package changes. Repeatable runner: `app/tests/live-journey.mjs`; run results and desktop/mobile images are in browser-evidence.

**Confirmed P2 for lead: Commands → Find a plot does not focus Search plots.** It closes the dialog then focus returns to `Open commands`; typing cannot search. Reproduced with actual click and activeElement. Current handler calls search.focus() before the dialog close effect releases inert background/restores opener. Move focus until after dialog closes (e.g. explicit pending-focus state handled after close).

Earlier unnamed-dialog finding is already fixed in the live app and passed rerun (`P-0005 evidence receipt`). Empty search/recovery, actual downloaded receipt vs JSON, modal focus trap/Escape return, reduced-motion emulation and390px document width checks passed. Mobile screenshot visually shows the plot/timeline clipped inside their panels despite no document overflow; investigating panel bounds before final verdict. A cell-keyboard test raced map transition while lead added an alternate native-cell table; adapting test to actual accessible table instead of assuming every SVG cell needs a tab stop.

### Confirmed mobile clipping — lead action P1 — 02:18 UTC

At real390×844 viewport, `.map-panel` width358px (x16→374), but `.map-canvas` and `.spatial-map` width527.656px (x17→544.656). Computed canvas min-height310px plus aspect-ratio800/470 forces this larger width. `.map-panel{overflow:hidden}` masks document overflow while cutting off the plot and **entire legend** (legend x406→534.656, outside panel). Repro default P-0003 or P-0001; screenshot `w3-mobile-review.png`. Fix mobile canvas sizing explicitly (e.g. width:100%; aspect-ratio:auto; height/min-height310px) and recheck full native boundary + visible legend. Desktop uses aspect-ratio:auto already. Timeline bounds are valid; earlier visual suspicion of timeline clipping was not confirmed. Add a panel-containment assertion; document scrollWidth alone misses this bug.

## Final live delivery — 02:20 UTC

### Verified results

- Ran own T3 `tab_i` for real queue→P-0005→2024/2025→proof→receipt before its host became unavailable. Never navigated `tab_h`. Used already installed Playwright1.63.0/cached Chromium only after the actual T3 failures; no package/dependency installation. Isolated browser was closed after each run.
- Final repeatable live run: **18 passed,0 failed**, with no captured application console errors/page errors. Checks use canonical JSON read from disk and actual controls. Browser-served JSON equals canonical artifact (content SHA recorded in results).
- J advances P-0003→P-0005; Tab+Enter advances2024→2025 with visible3px focus. Actual map counts262selected,7/11year-loss cells and18period cells match canonical output. All17plots expose the correct425annual labels and native-cell counts.
- Proof rows, source/compact results,17/17summary, expanded benchmark and receipt payload agree with JSON. Actual local download `P-0005-receipt.json` matches receipt, exact supplier strings and comparison. No external upload.
- Benchmark display correctly names compressed original GeoTIFF as storage choice. Tested586241source bytes versus786400best compact candidate bytes; source loaded-query median1.449166ms and fresh-process load+query11.331416ms are rendered with KiB/ms units and17-plot batch scope. These are engine artifact values, not new W3 benchmark measurements. The UI states that fresh-process timing is not disk-cold.
- Receipt dialog name, keyboard trap, Escape return, slash-search, empty search/retained-selection notice/recovery, and Commands→Find a plot focus pass. All17map locations are keyboard-selectable. Native-cell table opens with keyboard, exposes actual rows, and activates a cell inspector with Enter.
- Actual390×844viewport: document width390, proof/receipt reachable, empty search recovers, full map boundary and legend fit inside panel. Verified final mobile screenshot visually. Reduced-motion emulation matches and computes0.01msanimation/transition with auto scrolling.

### Bugs delivered and resolved by lead

| Finding | Reproduction and evidence | Final status |
| --- | --- | --- |
| Dialog lacked accessible name | T3 receipt had no aria-label/aria-labelledby. | PASS: title now labels dialog as P-0005 evidence receipt. |
| Commands search lost focus | Open commands→Find a plot returned activeElement to Open commands. | PASS: search receives focus after modal closes. |
| Mobile map cropped boundary and hid legend |390pxviewport;358pxpanel contained527.656pxcanvas; legend lay wholly beyond clipped edge. | PASS: explicit panel containment test and corrected screenshot. |

The initial cell-focus test was replaced with the actual accessible-table workflow as the lead introduced it; zero cells immediately after a map transition was a harness timing issue, not a proven app defect. The mobile timeline clipping suspicion was disproved by measured bounds.

### Repeat commands

From repository root (existing local Playwright installation):

```sh
PLAYWRIGHT_MODULE=/Users/speedpowermac/.npm/_npx/e41f203b7505f1fb/node_modules/playwright/index.mjs node app/tests/live-journey.mjs
node app/scripts/browser-check.mjs --file artifacts/demo-v1.json --url http://127.0.0.1:5173
node --test app/tests/contract-check.test.mjs
```

`PLAYWRIGHT_MODULE` can point to another already installed Playwright index.mjs. Without it, runner attempts ordinary app-local package resolution. Lead may add Playwright to package ownership later; no addition needed for this machine. The live runner intentionally exits nonzero on failures and closes its isolated browser in finally. It tests this source-winning experiment; a new benchmark winner requires updating that expectation.

### Evidence and limits

- `app/tests/live-journey.mjs`: repeatable actual-interface browser harness.
- `docs/lab/browser-evidence/w3-live-results.json`: final18-check result, artifact identity, viewport measurements, values and focus evidence.
- `w3-desktop-initial.png`, `w3-desktop-year-2025.png`, `w3-desktop-proof.png`, `w3-benchmark-source.png`, `w3-receipt.png`, `w3-receipt-expanded.png`, `w3-empty-search.png`, `w3-mobile-review.png`, `w3-mobile-empty.png`, `w3-mobile-proof.png`, `w3-mobile-receipt.png`: local screenshots; subsequent runs overwrite matching harness screenshots with latest verified state.
- `w3-P-0005-receipt.json`: actual downloaded receipt. `w3-mobile-clipping-before.json`: measured pre-fix bounds preserved from actual browser output. Current mobile screenshot shows the fix.
- This pass covers a desktop1440×1000and mobile390×844Chromium layout, plus the initial T3desktop viewport. It does not claim every viewport, assistive technology, browser engine, or source-raster accuracy. No real cohort unknown cases exist; unknown semantics have contract regression coverage, but no synthetic UI route was exercised.

**Master relay:** W3 live QA complete;18/18checks pass after lead fixes. No open blocking issue found in this tested journey. Re-run harness after the next app/artifact integration; screenshots and JSON remain local under owned paths.

## Cycle3 started — 02:36 UTC

Read02:32milestone and full C2-C design audit plus notes implementation/report. T3 status/open on own `tab_i` succeeded today; subsequent checkbox/action/evaluate calls intermittently failed and390pxresize timed out5000ms. Observed proof row received focus at y470.64–514.14 within960pxviewport, but unreliable action transport prevents treating the whole route as verified. Using existing isolated Playwright fallback; lead/validator browser sessions are untouched. Cycle3 targets changed behavior and separate real synthetic lab; V5/V7malicious fixtures remain with validator.

### Cycle3 first bounded verification — 02:39 UTC

Focused new runner `app/tests/cycle3-journey.mjs`: **13passed,1failed**. Proof arrival/return, notes integrated drafts/saved persistence/export/context versions/quota/read-denial, overview controls/extents/scope, all6actualsyntheticcases×2periods and separate17cohort, mobile proof focus and integrated notes layout pass. No page errors. Existing18checks were not blindly rerun.

**P2 lead action: mobile year labels are still9px.** At390×844, `.year-bars` is scrollable497px/358px with scrollLeft139, and2025remains visible (x357–374). However computed `.year-label` font-size is9px, below C2-C's12–14pxreading recommendation and milestone's readable-mobile intent. Increase mobile year label size and allow wider year targets/horizontal scrolling. This is a concrete readability recommendation, not a claimed WCAG minimum-font violation. Selected full-year heading remains readable, focus/scroll behavior passes. Screenshot will be captured even when the readability assertion fails.

Measured proof desktop arrival `proof-selected-year` is in viewport and focused; Back restores `annual-proof-trigger` withP-0005/year2025retained. Expanded table itself remounts closed; count/plot context is retained as C2-C requested. Notes tests only use disposable browser storage, including synthetic TEST context-version mount; canonical artifacts remain unchanged. Storage fault overrides are restored and isolated browsers closed.

## Cycle3 final delivery — 02:41 UTC

**14/14focused checks pass**, using current canonical artifact and the actual running5173app. The mobile readability failure was reproduced at9px, reported, fixed by lead, and rerun successfully. Earlier result is retained in `w3-cycle3-initial-results.json`. Final values/screenshots are in `w3-cycle3-results.json` and `w3-c3-*.png`.

**Residual P2 for lead: overview title still covers two markers.** With P-0005selected and All17plots, actual plot groups `Select P-0003 on map` and `Select P-0001 on map` intersect `.map-title` bounds. This reproduces the remaining title-space part of C2-Cfinding5. Layer controls disabled, extent coordinates, marker titles, selected label and plot-specific table all pass; marker/title spatial separation does not. Screenshot `w3-c3-overview.png`, measurements `w3-c3-overview-title-overlap.json`. Move the title outside the spatial drawing or reserve top/left projection space; preserve named marker keyboard access. This is nonblocking for the tested functional journey.

### Changed paths and reproduction

- Added `app/tests/cycle3-journey.mjs`: changed-flow regression using existing local Playwright, disposable browser storage and actual canonical/synthetic exports.
- Adapted only the obsolete benchmark expectation in `app/tests/live-journey.mjs`: selects and verifies the actual embedded overall storage choice instead of requiring historical source_geotiff. The old18-checksuite was not rerun this cycle.
- Updated this report and new evidence under `docs/lab/browser-evidence/`. No app implementation, package, raw data, validator files, Git or third-party service changes.

```sh
PLAYWRIGHT_MODULE=/Users/speedpowermac/.npm/_npx/e41f203b7505f1fb/node_modules/playwright/index.mjs node app/tests/cycle3-journey.mjs
```

### Scope and observed details

- Desktop expanded-cell-table→2025eventfilter→cellinspection→annual-count keyboard activation focuses `proof-selected-year`, scrolls11/11comparison into viewport, and Back restores visible `annual-proof-trigger` plus P-0005/year2025. Mobile count route also passes. Cell table expansion resets on remount; original count/plot/year context remains.
- Local drafts survive plot/proof switches without autosave. Save/reload retains exact text keyed by actual supplier-row hash. Saved and unsaved exports correctly distinguish `saved_locally`/`saved_at`; downloaded JSON stays local. Canonical data is unchanged by notes.
- Quota failure retains the prior saved record and revised draft; restoring storage and retrying succeeds. Separate-context read denial shows an explicit alert while plot evidence loads. Same synthetic QA plot under contextA/B isolates drafts in a temporary mount of the actual notes component; this is not a fabricated company artifact or a V5/V7malicious fixture. Browser contexts close after tests.
- Actual `synthetic-v1.json` is byte-content-equivalent after JSON parse to the served export. All6cases×2periods compare to actual results: partial absence remainsUnknownwith0observed; partial positive changes fromUnknownin2021–23toObservedwith1in2024–25; tiny/water/missing-band counts remainUnavailable. Case/raw-result labels remainSynthetic; queue and proof cohort stay17. No cohort pollution.
- Overview uses actual full-cohort north/west extent (8.58189°N,98.77243°E), disables3irrelevantlayerbuttons, names17markers, visibly labels selectedP-0005, and scopes table toP-0005/262cells. Residual title collision is above.
- Mobile timeline scrolls horizontally with selectedyear visible; final computed font/target values are recorded in results. Integrated notes fit358pxcontent inside390pxviewport. Screenshots for proof arrival/return, storage failure, overview, missing-band lab, mobile timeline/proof/notes are local.
- No page errors captured. This cycle does not duplicate C2-B102ingestionchecks or independent validator'sV5/V7malformedfixture suite. Storage mocks only affect notes in disposable contexts.

**Master relay:** cycle3 bounded regression complete;14/14functional/design-target checks pass after mobile text fix; residual overview title/marker collision is documented for lead. Current experiment winner is read from the artifact, not forced to the historical source-winning run.
