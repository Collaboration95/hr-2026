# Claude handoff — complete Plotline UI redesign

> **Status, 15 October 2026: delivered** on `guru/plotline-ui-redesign`. Decisions, the design system and verification are in [docs/writeups/05-redesign-decisions.md](docs/writeups/05-redesign-decisions.md) and [design/DESIGN.md](design/DESIGN.md). The brief below is kept as the record of what was asked.

**Prepared 14 October 2026 by Astra.** Implementation baseline: `b3a49ac170d2aefc37c9239b24b75b87fd04e0a8` on `guru/plotline-research-lab`. Repository: `Collaboration95/hr-2026`. Local workspace: `/Users/speedpowermac/Documents/projects/CODE_MAIN/personal/hack_roll`.

## 1. Your assignment and authority

The user’s latest instruction is: **“I want Claude to redo the UI completely.”** They asked Astra to prepare this handoff first. This document transfers the project context; it does not mean Claude has already started or that a redesign has been implemented.

When the user starts your redesign task, deliver a working replacement UI in the existing application. You own its information architecture, visual system, navigation, layout, typography, color, responsive behavior, interaction design and presentation components. You can replace the existing shell and reorganize every screen. This is a complete redesign, not a request to preserve the current appearance or merely adjust CSS. The user has not specified a visual reference, palette, light/dark preference, or new brand name. Make coherent design decisions without asking for permission on routine reversible choices.

The product already works. Your task is to make its evidence workflow substantially clearer and more compelling while retaining its real capabilities and verified meaning. Do not restart backend research or substitute a disconnected mockup for the application. Keep the Plotline working name unless the user directs otherwise; its current logo treatment and visual style are replaceable.

**This handoff supersedes the design-only instructions in `docs/planning/claude-ux-handoff.md`.** That earlier document predates implementation. Its “no application code,” “stack undecided,” provisional codec, and “JRC unavailable” descriptions are historical. Likewise, the 13 October early-stop instruction was followed by explicit user authorization to complete the project on 14 October, and now by this redesign request. Those historical milestones must not block current authorized work.

Current user instructions and `AGENTS.md` take precedence. Treat the scientific contracts below as correctness requirements, not as reasons to preserve the current screen layout. If the user changes the scope, record the change explicitly.

## 2. Read this context in order

All paths in this document are relative to the repository root unless noted otherwise. Read the actual files; links and filenames are pointers, not evidence that their contents have been read.

1. [AGENTS.md](AGENTS.md), [README.md](README.md), and this handoff.
2. [Project handover](docs/HANDOVER.md), [app instructions](app/README.md), and [current demo script](docs/lab/demo-script.md).
3. SystemEarth sections of [printed brief](docs/problem_statement_reference.txt), [spoken guidance](docs/transcript_rules_and_constraints.txt), and [kickoff guidance](docs/sustainability_kickoff_reference.txt).
4. Run the app and inspect its actual data and behavior. The 25-second silent walkthrough (`docs/lab/completion-demo.webm`, kept local, not committed: it shows supplier plot outlines) and [chapter metadata](docs/lab/completion-demo.json) are a quick orientation to the old design, not an aesthetic specification.
5. Before changing data-consuming components, read [frozen interface](docs/lab/interface-v1.md), [live interface](docs/lab/engine-live-interface-v1.md), [JRC interface](docs/lab/engine-jrc-interface.md), and the current consumer code. Interface documents contain dated additive updates; current validated artifacts and implementation resolve early “pending” descriptions.

Use the deep reference index at the end for focused research. You do not need to reread every experiment log before designing the shell.

## 3. What this project is for

This is the SystemEarth track of **Hack & Hire Sustainability Edition 2026**, organized by Projet with NUS CAT. The recorded build period is 10–17 October; finals are 17 October. A supplied challenge screenshot says 17 October at 00:00 SGT, but its meaning as application or project deadline is unresolved. The team aimed to be ready on 16 October. Pitch length, final submission channel and presenter are unconfirmed. Do not invent an organizer requirement or submission completion.

SystemEarth’s challenge is compact storage and efficient querying of multiple geospatial layers over space and time while preserving the information needed for plot-level decisions. The printed guidance requests a working sample-region prototype; the spoken brief is less firm. We satisfy the stronger printed request.

Required engineering evidence includes original-versus-compact storage, query speed, resource use, plot-query fidelity and relevant pixel fidelity. Existing algorithms are allowed. A novel codec, ML model, infrastructure cost estimate or cloud deployment is not required; cost estimation is a bonus.

**Plotline’s user:** an analyst reviewing supplier declarations, exact farm boundaries and mapped observations, with a technical reviewer who needs to inspect the representation proof.

**Core task:** “What does this plot’s evidence say, what is missing, and did the compact representation preserve the same answer?”

The project is an evidence-review and forest-change screening prototype. It is not a legal compliance classifier, autonomous enforcement system, global monitoring platform or generic ESG dashboard. Engineering proof is part of its purpose; a beautiful map that hides the original/compact comparison would miss the challenge.

## 4. Actual data and representative cases

The company supplied 17 CSV rows and 17 polygons, joined one-to-one with no duplicate or unmatched IDs. CSV `a3_plot_id` joins GeoJSON `ProductionPlace`. Gaps in numeric IDs, including P-0002/P-0007/P-0012, are not missing joins.

Original inputs:

- `data/company-sample/2026-10-12/200001-17plots-valid_2025-08-02T09_11_12Z.csv`
- `data/company-sample/2026-10-12/200001-17plots-valid.geojson`

The records label their location **Surat Thani / Chai Buri, Thailand**. Bounds are 98.772429–99.080292° E and 8.431179–8.581888° N. Songkhla/rubber was a teammate proposal, not this sample’s established location or final commodity. An older Brazil proposal is also historical. Preserve supplied labels and exact geometry; do not silently infer a different region.

Five IDs—P-0003, P-0005, P-0008, P-0010, P-0013—declare an indication of deforestation, mitigation/on-site verification with evidence, and a final deforestation-free/compliant status. These are **supplier declarations and review leads**, not five proven violations or five measured satellite conflicts. The mitigation files were not supplied. Reference keys are opaque strings, not working URLs.

Useful real specimens, to verify against the canonical JSON when implementing:

| Case | What the current evidence actually says | Why it is useful |
| --- | --- | --- |
| P-0003 | Hansen selects 87 native cells; no mapped loss in 2021–2023 under the accepted rule. Supplier reference is `hyperlink-RG1-P-0002`; the referenced evidence is missing. | Shows declaration versus observation and the next review question without accusing a supplier. |
| P-0005 | Hansen selects 262 cells; 7 loss cells in 2024 and 11 in 2025, totaling 18 for 2024–2025. | Shows cohort → plot/year → native cells → proof navigation. |
| P-0003 JRC | 793 selected cells, all valid class 0 (Non-forest), no class 1. | Known zero is different from missing evidence. |
| P-0001 JRC | 1,083 selected cells: 529 class 0 and 554 class 1. | Shows a real positive mapped forest-class result on JRC’s own grid. |

The five supplier-indication records and the five plots with mapped 2024–2025 loss are different sets. Equal group sizes do not imply correspondence.

Supplier analysis window 2021–2023, 2024 processing/harvest dates, observation year, source release/version and JRC reference year are distinct concepts. The processing/harvest chronology needs company interpretation. Display it faithfully; do not repair it or infer misconduct. Supplier-reported hectares can be displayed as declared area, but do not convert observed raster cell counts into hectares.

## 5. Layers and computational meaning

### Hansen: accepted production screening rule

Pinned input is Hansen GFC **2025 v1.13**, tile `10N_090E`, with `treecover2000`, `lossyear` and `datamask`. The native chip is 604 rows × 1,233 columns: 744,732 spatial cells. All three band-validity masks are independent. The current app displays annual observations for 2001–2025 and period summaries for 2021–2023 and 2024–2025.

The query is `hansen-centers.v1`. A cell is selected when its native center is covered by the exact polygon, including boundary centers. The displayed cell polygon is its whole footprint, so it may extend beyond the plot boundary. Do not replace center selection with footprint overlap, clipped cells, a rounded geometry or a screen-space hit test. A map projection is for display; original geometry and query coordinates stay unchanged.

Tree-cover loss is not a legal deforestation determination. Canopy2000 is context, not a forest2020 baseline. Do not reconstruct a forest2020 layer by subtracting loss from canopy2000.

### JRC: separately verified companion

JRC Global Forest Cover 2020 **v4 is acquired, verified and integrated**. The attempted v3 acquisition failed earlier; that does not mean v4 is unavailable.

JRC uses a different 1,809 × 3,695 native grid. Its reference year is 2020; it has no annual time series. Valid class 0 is Non-forest; valid class 1 is Forest. Transparent source styling for class 0 does not make it nodata. JRC’s metadata contains a dated XML/report-link discrepancy that is already disclosed in its source information.

Keep its source/version, native grid, counts, receipt and proof identifiable. You may place Hansen and JRC in a more coherent workspace, but do not merge their cell counts as common area, add them together, reuse one source’s affine/indexes for the other, or invent a combined legal verdict. Do not apply the Hansen annual year selector to JRC as though it had yearly observations.

### Truth-state rules that the redesign must preserve

| State | Required meaning |
| --- | --- |
| Known zero | A supported computed zero, not an absent value. |
| Positive with partial support | A witnessed event can remain true; unknown support must remain visible. |
| No witnessed event with partial support | Unknown, not false or clear. |
| No centers, no valid land, missing required band or unavailable analysis | Explicit unknown/unavailable reason; never a reassuring zero. |
| Source/compact equal | The same declared computation agrees for pinned inputs; not satellite truth or legal certification. |
| Comparison pending/unavailable | No comparison has been established; distinct from mismatch. |
| Encoding mismatch | A technical discrepancy between execution paths; not evidence against a supplier. |
| Supplier final “Compliant” field | Exact supplied declaration with attribution; not an app-issued badge. |
| Fetch/integrity failure | Failed/unavailable, with recovery where supported; no fabricated fallback success. |

Treat booleans, numbers, null and missing fields distinctly. Avoid `value || 0`, blanket `Number(value)`, or fallback copy that converts an unknown to “no loss.” Derive display states through validated data and the existing semantic helpers.

## 6. Capabilities to retain in the redesigned experience

The following are behavior requirements; the current four-tab layout, names, DOM structure and CSS classes are not requirements.

**Review a plot.** Search/filter the real cohort; select a plot; inspect exact declarations and missing references; see native geometry and evidence; choose an annual observation; inspect raw cells through an accessible table or equivalent non-map route. The existing overview locates all 17 plots without pretending they share the selected plot’s layer footprint.

**Explore the cohort.** Inspect all 17 plots across 25 annual observations, with meaningful period views and separately attributed supplier declarations. Selecting a positive cohort cell carries its exact plot and year into detail. Export the displayed counts as a real CSV with context and unknowns. Review-queue filtering currently does not secretly filter the full cohort index; any new filter scope must be clear.

**Inspect proof.** Compare the selected plot/year and full query on original and compact paths. Show actual equality or differing fields, provenance and measured tradeoffs. Preserve selection and a useful focus/return destination. Do not invent a witness pixel when no mismatch exists.

**Inspect and export receipts.** Human-readable source/grid/rule/hash/declaration details, raw JSON, and local receipt downloads remain available. Export the actual bound data. File SHA, embedded content SHA and receipt SHA are different identities. Hashes indicate local integrity; they are not signatures or certificates.

**Keep analyst notes.** Notes are local annotations, separate from original supplier data and receipts. Saved notes survive refresh; unsaved drafts survive plot/view switches in the tab. Storage denial/quota errors retain the draft and explain recovery. Keep note exports labeled saved versus draft. Preserve existing saved notes or provide an explicit compatible migration if the storage format changes.

**Run a live query.** The optional local service accepts an exact supplied polygon or a temporary rectangle, returns real original/compact results, complete selected-cell evidence and a bound downloadable receipt. Changing temporary bounds invalidates the old answer. Cancel, late-response rejection, unavailable/retry and snapshot changes are real interaction states. This never edits supplier records or frozen cohort observations.

**Inspect JRC independently.** Provide the real class counts, known-zero/unknown distinction, native cells, source/grid information and separate receipt/proof. A JRC loading failure must not prevent Hansen review. Current mobile tables scroll horizontally; a compact accessible redesign is welcome.

**Explain support limits.** The existing six-case synthetic lab uses a fictitious 4×4 grid. Keep it explicitly separate from real supplier counts and proof metrics if presented. Preserve test coverage of those states even if the instructional surface is reorganized.

Keyboard shortcuts currently include J/K for plots outside editable controls, `/` for search, Cmd/Ctrl+K for commands and Escape for dialogs. You may redesign their presentation, but retain efficient keyboard access, visible focus, dialog focus trapping/restoration, and a complete non-pointer path. Respect reduced motion. A map must not be the only way to inspect evidence.

## 7. Architecture and practical code map

The existing stack is **React 19, TypeScript and Vite**, with a **Python 3.14** engine and optional standard-library HTTP service. There is no required stack migration, cloud account, login system, remote database, tile service or external font dependency. Current dependencies and exact resolved versions are in `app/package.json` and `app/package-lock.json`. Python pins are in `engine/requirements.txt`; Python 3.14 supplies standard-library Zstd.

Prefer the current stack unless a concrete redesign requirement justifies a change. New libraries are routine implementation decisions within scope, but document their purpose, update the lockfile, preserve reliable local setup and avoid introducing unnecessary network dependencies into the demo.

| File or area | Responsibility / redesign guidance |
| --- | --- |
| `app/src/main.tsx` | React root and global stylesheet imports. |
| `app/src/App.tsx` | Current shell, selected plot/year/view, filters, map/overview, dialogs and focus coordination. Splitting this large component is reasonable. |
| `app/src/app.css`, `app/src/styles/`, `app/src/components/Primitives.tsx` | Existing visual system; freely replace or reorganize. |
| `app/src/CohortIndex.tsx` | Cohort/period tables, plot-year navigation and CSV export. |
| `app/src/CellTable.tsx`, `cell-values.ts` | Native evidence inspection and mask-aware display helpers. |
| `app/src/Benchmark.tsx` | Retained measurements and stronger standard controls; preserve units and accounting boundaries. |
| `app/src/ReceiptDetails.tsx` | Readable receipt fields plus raw representation. |
| `app/src/AnalystNotes.tsx` | Draft lifetime, storage errors, saved notes and exports. |
| `app/src/LiveQueryLab.tsx`, `styles/live-query.css` | Live form, request lifecycle, results, map/table and receipt. |
| `app/src/JrcBaseline.tsx`, `styles/jrc-baseline.css` | Separate native JRC presentation. |
| `app/src/EdgeLab.tsx` | Clearly synthetic support-state demonstrations. |
| `app/src/types.ts`, `data.ts`, `comparison-state.ts` | Frozen types, runtime ingestion checks and comparison semantics. Preserve this validation boundary during presentation changes. |
| `app/src/jrc-data.ts` | JRC validation, geometry binding, equality and affine/cell helpers. |
| `app/src/live-client.ts` | Validated health/query client; exact request, geometry, snapshot, result/evidence/receipt binding. Reuse it rather than replacing it with bare fetch calls. |
| `app/scripts/sync-data.py` | Copies canonical artifacts into ignored `app/public/data/`; checks the accepted JRC file pin. Do not remove the pin to make changed data display. |
| `app/scripts/dev-local.mjs`, `app/vite.config.ts` | Owned-process launcher and loopback `/v1` proxy. |
| `app/scripts/qa-config.mjs`, `browser-qa.mjs` | Shared loopback test origin, app-local browser, isolated QA output and suites. |
| `app/scripts/record-demo.mjs` | Actual UI walkthrough recording; update its navigation after the redesign. |
| `engine/`, `artifacts/`, `data/`, `validation/` | Computation, canonical inputs/results, retained measurements and independent proofs. Normally read-only for this UI assignment. |

The current app has no dedicated client routing/state library. Selection starts at P-0003, year 2023, review view. Do not hard-code those example outcomes into a new design; render from validated data.

The saved note key is `plotline:analyst-note:v1:${JSON.stringify([contextKey, plotId])}`, where the context identifies the exact supplier row. A note must not silently attach to a changed declaration that happens to reuse the plot ID. The current 4,000-character limit and draft/export semantics are implemented in `AnalystNotes.tsx`.

## 8. Data flow and integration boundaries

Frozen review:

1. `artifacts/demo-v1.json` is the canonical engine export (`plotline.demo.v1`).
2. Startup/build copies it to `app/public/data/demo-v1.json`.
3. `loadDemo()` fetches `/data/demo-v1.json` and `validateDemo()` checks shape and semantic consistency.
4. React renders the accepted object. Changing plot/year in frozen review does **not** execute a new engine query.
5. A failed reload retains the prior accepted artifact and exposes the error.

A plot contains `plot_id`, exact `geometry`, exact string-valued `supplier`, nullable `source_result`, `compact_result`, `comparison`, `receipt`, and `evidence`. Results include selected/in/out/valid/unknown counts, histograms, yearly counts, period flags, support state and reasons. Use `types.ts` and the canonical JSON for exact nesting.

JRC loads separately from `artifacts/jrc-baseline-v1.json` through `loadJrc(main, signal)` / `validateJrc(value, main)`, checking association with the main plots. Its native cells use row/column/value/valid records and a shared JRC affine; their layout is not the Hansen GeoJSON-cell layout.

`artifacts/synthetic-v1.json` is a separate fixture. `artifacts/benchmark-v1.json` and `artifacts/strong-baseline-v1.json` preserve different measured studies. The UI must not choose the newest experiment automatically or splice them into a new result.

If the main export is missing, the sync script can produce a declaration-only fallback. That has uncomputed/null analytical fields and is not a passing full-proof artifact. Display its limits explicitly.

Live queries:

- `GET /v1/health` establishes a verified immutable snapshot. `getLiveHealth(signal)` validates it.
- `runLiveQuery(geometry, requestId, health, signal)` sends `POST /v1/query` and validates the actual response against the exact request and snapshot.
- Health/response include canonical JSON strings used for byte-level hash verification across Python and JavaScript. Do not reserialize those strings with a guessed canonicalizer.
- The caller must still manage active-request identity and draft association; an AbortController alone is insufficient when a late transport response ignores cancellation.
- Snapshot changes require reconnecting. Single-request timings are labeled `benchmark: false` and are not evidence of a speedup.
- Service bounds: 65,536 request bytes, 512 positions, 4,096 candidate/selected cells. Oversized requests reject; they do not silently clip or sample the answer. Limits apply to outside-chip candidates too.
- Backend is Hansen-only, read-only, IPv4 loopback. No arbitrary paths, source selection, supplier mutation or rule toggles are accepted.

Keep the UI’s service-ready, connecting, running, canceled, rejected, unavailable, invalid-response and completed states understandable. Do not display “verified” merely because HTTP returned 200.

## 9. Measured results and research lessons

These numbers are orientation, not values to hard-code into components. Read the retained export for display and preserve its labels/method.

| Retained result | Permitted interpretation |
| --- | --- |
| 17/17 source/compact query matches and preserved full raw values/masks | Exact computational preservation for pinned inputs and rules; no environmental ground truth claim. |
| 535,012 B custom versus 585,293 B necessary supplied source inputs | 8.59% reduction at that loader-input boundary. |
| With identical common review inputs: 562,571 B versus 604,558 B | 6.95% reduction at this different complete-review boundary. Do not interchange denominators. |
| Hot 17-query medians: source 1.418 ms, compact 1.446 ms | No meaningful hot-query speedup is established. |
| Fresh-process full load + 17 queries: 11.182 ms source, 5.800 ms compact | Bounded full-load benefit; imports/common geometry excluded and OS cache uncontrolled. Not disk-cold. |
| Strong standard Hansen control: 532,444 B | Standard is 2,568 B / 0.48% smaller than custom in the separate control study; custom does not win every workload. |
| JRC custom 21,459 B; standard control 19,901 B | Separate JRC study; standard is 7.26% smaller. Do not extend Hansen’s percentage to JRC. |

CPU, memory/RSS, encoding costs, repetitions and raw samples are retained in detailed reports. Tiny differences and seven-repeat p95 values are not universal performance guarantees. Never compare full downloaded source tiles with a cropped sample and label the crop saving “compression.”

Research that affects interpretation:

- **Spatial inclusion:** footprint overlap adds 337 plot/cell memberships and changes five period flags compared with center inclusion; 15 witness cells were independently reproduced. P-0003 gains a 2025 overlap witness even though its center is outside. This is a rule difference, not an encoding defect. Neither rule study explains the five supplier 2021–2023 indications. Production remains center-based.
- **Historical vintage:** the preregistered Hansen 2023 v1.11 comparison left all shared 2021–2023 counts/flags unchanged across the 17 plots. The company’s actual source remains unknown. Later-year additions are not evidence that the declaration was wrong.
- **Learned codec selector:** the held-out adaptive policy lost to fixed alternatives. It was rejected for production. Do not add an “AI optimized” success story or train a risk score on supplier final declarations.
- **Independent validation mattered:** prior fixes include null-as-zero UI, false equality rendering, off-plot corruption missed by plot-only comparison, forged-but-rehashed receipts, intermediate timed-answer failures and stale live responses. Those checks should survive the redesign.

**RuleLens** is an optional educational UI concept, not implemented. Its projection is `artifacts/spatial-rule-witness-v1.json`; design notes are `docs/lab/experience-rule-lens-report.md`. It is not necessary for the redesign. If used, retain its artifact’s stated review status, identify frozen research, and do not turn overlap into a production query toggle or compliance explanation.

## 10. Design opportunities, not a prescribed aesthetic

The current app uses a green/cream evidence-workspace treatment, a persistent queue, top navigation, an SVG map, dense tables, a timeline, disclosures and dialogs. None of those visual choices is mandatory.

Astra’s assessment of useful redesign opportunities:

- Give a first-time viewer a clear entry: what is being reviewed, which source/time is selected, what was observed and what needs a human next.
- Make declaration, mapped observation, missing evidence and encoding proof visibly distinct without repeating dense disclaimers at every step.
- Make the transition from an annual count to its native cells and receipt feel connected. Keep plot/year/source context visible when navigating.
- Make the engineering comparison legible at a glance, with deeper accounting and integrity details available on demand. Preserve the stronger standard baseline and losing candidates.
- Integrate the separate JRC evidence into a coherent review experience without hiding source/grid differences.
- Reduce scrolling and information overload on mobile. The independent review found a 980px JRC table inside a 296px scroll region at a 390px viewport. It works, but better prioritization of the analytical observation would help.
- Use a consistent hierarchy, responsive behavior, focus treatment and intentional empty/error states across the whole product.

These are suggestions, not user-mandated wireframes. Choose and implement your own coherent direction. Avoid adding irrelevant dashboard statistics, invented activity feeds, unactionable controls, fake satellite imagery, simulated live results or arbitrary risk scores to fill space. The real data is sufficient for a strong design.

## 11. Run and inspect locally

Commands below run from the repository root. A new environment requires Python 3.14 and Node/npm. Previously verified versions: Python 3.14.7, NumPy 2.5.4, Rasterio 1.5.2, Shapely 2.1.2, Node 26.3.1, npm 11.16.0. The clean-export audit used newly installed dependencies without full satellite-tile caches on this same machine; it did not establish cross-platform support.

```sh
# First setup only: explicitly installs the pinned/locked dependencies.
scripts/setup-local.sh

# Retained Hansen/JRC proofs, full/indexed P-0003 reproduction and build.
scripts/verify-local.sh

# Normal combined launch: app 5173, API 8765.
npm run dev:local --prefix app

# Isolated alternative when those ports are occupied.
PLOTLINE_WEB_PORT=5183 PLOTLINE_LIVE_PORT=8766 npm run dev:local --prefix app
```

The prior completion session left 5183/8766 healthy, but do not assume those processes still exist. Inspect current ownership. The launcher refuses occupied ports, starts only its own children, and stops them on Ctrl-C. Do not kill a shared service merely to reuse a port.

Frozen review alone: `npm run dev --prefix app -- --port 5173 --strictPort`. Build: `npm run build --prefix app`. Preview the built app: `npm run preview --prefix app -- --port 4173 --strictPort`. Frozen review works through local static serving; the live lab still requires its API. `file://` is not the supported app launch method.

For T3 browser work, start with `preview_status`, then `preview_open` if necessary. Use the active runtime’s browser instructions and respect human tab ownership. The repository also documents app-local Playwright QA. Earlier T3 recording failed twice with `Preview automation recordingStart timed out after 15000ms.` That is a historical limitation, not proof that the current preview is unavailable. Use the current tools first where required.

## 12. Verification and adapting tests to a new UI

Baseline at `b3a49ac`:

- 198 engine tests and 298 frontend checks passed.
- Retained Hansen and JRC verifiers passed; six independent strong-control forgeries were rejected while the valid artifact passed.
- Frozen browser suites passed 18, 14 and 11 checks, plus index/overview checks at desktop and 390px.
- Actual-service live browser suite passed 14 checks.
- Independent integrated JRC browser review passed nine focused checks; a portable lead replay also passed.
- Production build, clean-export reproduction and a real silent walkthrough passed. Historical overlapping suites must not be added together as a fabricated unique test count.

Evidence: [completion verification](docs/lab/completion-verification.json), [independent JRC review](docs/lab/completion-browser-report.md), [browser evidence](docs/lab/completion-evidence/), [clean-export report](docs/lab/completion-reproducibility.md).

Run checks appropriate to changed code:

```sh
npm test --prefix app
npm run build --prefix app

# Install the app-local browser once if it is absent; tests never install it.
npm run qa:install-browser --prefix app

# With the real app/API running at the chosen origin:
PLOTLINE_QA_ORIGIN=http://127.0.0.1:5183 npm run qa:browser --prefix app
PLOTLINE_QA_ORIGIN=http://127.0.0.1:5183 npm run qa:live --prefix app
PLOTLINE_QA_ORIGIN=http://127.0.0.1:5183 npm run qa:jrc --prefix app
PLOTLINE_QA_ORIGIN=http://127.0.0.1:5183 npm run demo:record --prefix app
```

The runner prints a unique output directory under ignored `app/.cache/qa/`. `PLOTLINE_QA_OUTPUT` can choose another directory. Preserve historical evidence; retain a newly named redesign evidence set when finished. The legacy `PLOTLINE_QA_URL` is an alias for the origin. The independent JRC command uses app-local Playwright, not a machine-specific npm cache.

**The browser tests and recording script contain current UI labels and CSS selectors.** A full redesign will legitimately change these. Update navigation/locators and focus expectations to match the new interaction design while preserving the tested behavior and assertions. Do not keep an inferior layout just to satisfy a selector, and do not delete a meaningful assertion merely to obtain a pass. Explain deliberate behavior changes and their replacement checks. Keep fixture validation, null/mask handling, equality, receipt binding, race/cancel/error coverage and actual-service acceptance intact.

Missing live health is an explicit blocked check, not a successful skip. Do not fabricate successful API bodies to satisfy live acceptance. Test-only transport failures/delays may exercise recovery; label them as such.

After integration, recheck the retained proofs with `scripts/verify-local.sh`. A pure UI redesign should not need to regenerate source exports, codec stores or benchmarks. Engine code/input changes can invalidate retained bindings; if a real backend defect is found, address it explicitly with its own evidence lifecycle rather than bypassing verification.

## 13. Suggested execution and completion contract

1. Read the current context and inspect the real desktop/mobile app. Record any baseline failures before editing.
2. Choose a visual and interaction direction; briefly explain how it serves the analyst and the technical proof. Start implementation without a new approval loop for ordinary design choices.
3. Rebuild the shell and primary plot-review flow first. Reuse validated data/client boundaries while restructuring presentation code.
4. Integrate cohort navigation/export, receipts/notes, measured proof, live query and JRC. No essential feature should be left as a visual placeholder.
5. Update UI-specific tests and recording navigation. Verify the real service, desktop/mobile layouts, keyboard paths, reduced motion and failure states.
6. Review actual screenshots and fix clipping, unreadable tables, focus loss, stale results and inconsistent states. Keep the first demo journey short and comprehensible.
7. Update run instructions, demo narration and the redesign handoff; report changes, checks, known limitations and exact Git state.

Completion means a visibly redesigned, coherent application with actual data and functional controls; preserved source/compact proof and trust boundaries; usable desktop and mobile flows; meaningful passing checks; and a new demonstrable walkthrough. A design-only report, screenshots without working behavior, or a static mockup does not complete the intended next task.

## 14. Scope, publication and collaboration rules

- Use authenticated `gh` exclusively for all GitHub access. Do not use GitHub connectors or browser access. Local Git operations use `git`.
- Use `guru/` for new branches; `guru/plotline-ui-redesign` is a suitable name if available. Check the working tree and the user’s current branch preference before branching. Do not discard unrelated changes.
- Commit format is `<type>(<scope>): <imperative summary>`, for example `feat(ui): rebuild Plotline evidence workspace`.
- The user previously authorized tracked publication to the existing public repository. That does not authorize cloud deployment, an organizer submission, unrelated uploads or messages to people. Do not ask again for routine actions already authorized by the current session.
- Preserve company originals, source chips, provenance and accepted measured artifacts. Keep raw acquisition caches, dependencies and disposable outputs excluded as documented.
- The user prefers autonomous progress and dislikes unnecessary confirmations. Ask only when a genuinely missing decision blocks the work; distinguish that from routine reversible implementation choices.
- When delegating authorized grunt work, prefer GPT-6 Luna when available. Use disjoint write scopes and review the results. The present request is specifically for Claude to own the redesign; no delegation hierarchy or fixed budget is required by this handoff.
- If operating in T3, discover current capabilities rather than copying historical model IDs or old agent-session IDs blindly. Use child-task tools for subagents; top-level threads require the user’s request. Register any PR actually created or worked on if the runtime provides PR-link tools.

No company-approved rule set, supplied mitigation file, independent environmental truth, broad geographic validation, representative production workload or user study has been added. The mock judge review scored proposal quality 90/100 and demonstrated readiness 87/100; these are informal rubric judgments, not completion percentages, official scores or a claim of winning.

## 15. Deeper reference index

| Topic | Read |
| --- | --- |
| Full current technical handover and measured decisions | [docs/HANDOVER.md](docs/HANDOVER.md) |
| Track expectations and unresolved logistics | [SystemEarth-track.md](SystemEarth-track.md), [event notes](docs/event_rules_and_open_questions.txt) |
| Original sample interpretation and corrected earlier claims | [sample audit](docs/research/company-sample-audit.md), [prior context](docs/research/prior-thread-context.md) |
| Native source acquisition/provenance | [Hansen report](docs/research/layer-acquisition.md), [JRC acquisition](docs/lab/engine-data-W4.md) |
| Engine implementation and minimal reproduction | [engine README](engine/README.md), [engine report](docs/lab/engine-report.md), [engine checkpoint](docs/lab/engine-checkpoint.md) |
| Full interface contracts | [frozen](docs/lab/interface-v1.md), [live](docs/lab/engine-live-interface-v1.md), [JRC](docs/lab/engine-jrc-interface.md) |
| Validation findings and fixes | [main validator](docs/lab/validator-report.md), [JRC validator](docs/lab/validator-jrc-report.md), [strong/spatial validator](docs/lab/validator-strong-spatial-report.md) |
| Research rationale and negative results | [methodology](docs/lab/research-methodology.md), [results index](docs/lab/results-index.md), [spatial sensitivity](docs/lab/engine-spatial-sensitivity-report.md), [vintage study](docs/lab/engine-vintage-report.md) |
| Historical design thinking; not current authority | [old Claude brief](docs/planning/claude-ux-handoff.md), [old product direction](docs/planning/systemearth-product-direction.md), [product research](docs/lab/product-research.md) |
| Current demo and company questions | [demo script](docs/lab/demo-script.md), [unsent discussion brief](docs/lab/company-next-conversation.md) |
| Current assessment and verification | [mock judge review](docs/lab/final-judge-review.md), [completion checks](docs/lab/completion-verification.json) |

This is the relevant known context, with pointers to the durable evidence. It does not claim to recover unrecorded company conversations, team decisions or hidden prior preferences.

## 16. Copy-paste starter prompt for Claude

> Read `AGENTS.md`, `README.md` and `HANDOFF.md` in this repository, then inspect the running Plotline app and its actual artifacts. I want you to completely redesign and implement the UI, not merely restyle it or return a design proposal. Own the visual system, information architecture and interactions. Preserve the real evidence workflows, validation, unknown states, original/compact proof, separate JRC semantics and live-query correctness described in the handoff. The old design-only planning brief is historical. Use the existing stack unless a concrete requirement justifies a change. Update UI-specific tests to the new design without weakening behavior coverage, verify desktop/mobile and actual-service flows, and leave a working, documented, demonstrable result. Make routine reversible design decisions autonomously. Use `gh` exclusively for GitHub access and follow the repository’s branch/commit conventions.
