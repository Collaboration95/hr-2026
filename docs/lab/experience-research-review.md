# W1 experience research and interaction review

Initial delivery: 2026-10-13 02:01 UTC (rounded from tool clock 02:00:58). Owner: Sol W1; recipient: experience lead Hooke through shared files. Only this file and `docs/lab/product-research.md` are W1 write paths.

## Early blocker

- `rg --files app docs/lab` showed no app files at the initial inspection. `docs/lab/experience-report.md` was absent. No application implementation or live endpoint has been inspected; no browser or accessibility pass is claimed.
- Continue independent research and contract checks now. Lead should publish the local URL and integration checkpoint in its report; W3 owns browser harness/evidence. W1 will provide source-specific interaction critique when implementation exists.

## Immediate integration guidance

- Render `mapped_loss_present` with explicit `true`, `false`, and `null` branches. Null means unknown; never pass it through truthiness to a no-loss label. Partial support plus witnessed loss remains true; partial support with no witnessed loss remains unknown.
- Show support and unknown reasons beside each mapped result, even when loss is witnessed. Counts are observed native cells, not hectares or full-polygon coverage.
- Keep supplier mitigation/final status under a persistent “Supplier declaration” label. The five declared mitigation leads are not independently detected violations. Opaque reference keys are copyable text with “Evidence file not supplied,” not hyperlinks.
- Distinguish observation period from release vintage: supplier-declared 2021–2023 basis versus current Hansen 2025 v1.13 observations. Year selection must update map evidence and textual counts together.
- Label agreement “Same query outputs” or “Encoding agreement.” Source/compact equality does not establish satellite accuracy, evidence sufficiency, forest in 2020, or legal compliance.
- Prefer queue → plot → year → proof → receipt as one selection state. Proof and receipt must retain selected plot/year and avoid opening a global summary that loses context.

## Evidence read

- Read actual `AGENTS.md`, `README.md`, `docs/lab/charter.md`, `docs/lab/interface-v1.md`, all three project requirement references, product direction, and company-sample audit. No raw source edits, app edits, Git mutations, external publication, or private uploads.
- Interface v1 is authoritative over the older product direction where partial-support semantics differ. The older prose says outside coverage can null analytical outputs; v1 explicitly retains observed histograms on partial valid support. This difference is a concrete integration trap.

## Next actions for lead

- Implement explicit result-state mapping and a selected-plot receipt before introducing general metrics.
- Publish app URL when ready. Read `docs/lab/product-research.md` for sourced interaction adaptations and bounded acceptance checks.

## First bounded delivery

- Complete: `docs/lab/product-research.md` contains five sourced lessons, actual source dates/date discrepancies, original adaptations, a tri-state display table and concrete keyboard/proof checks. Sources include the current 8 October 2026 Anthropic Dashboards release and 3 September 2026 Linear Priority Inbox release, plus citations, comparison and contextual keyboard patterns.
- Complete: this report contains early blockers, contract traps and immediate lead actions. No app implementation writes.
- T3 tools discovered by names/descriptions through `ALL_TOOLS`. Used `preview_status`, then `preview_open` with a new background tab (`tab_f`), then `preview_snapshot` on the public Anthropic article. Existing shared `tab_b` was left untouched. No company fixture entered a public website; no screenshot file written. Public release documentation was inspected, not the authenticated product.
- Latest app inspection now finds package/config, `main.tsx`, `types.ts`, W2 primitives/styles and sync script. `App.tsx`, `app.css` and endpoint report are still absent at this checkpoint. This supersedes the initial no-files inventory; live application critique remains pending.

## Static integration observations

- `app/src/types.ts` includes nullable source/compact results, nullable comparison/evidence and tri-state period flags. UI needs separate loading, unavailable result and comparison-unavailable states; a missing comparison must not show a success badge.
- `Result.support` is currently unrestricted `string`; consider the interface's four-value union (`complete`, `partial`, `none`, `unavailable`) to make display-state omissions visible during integration.
- `Demo` currently omits the contract's top-level `periods`. If year/period controls rely on hardcoded windows, they may diverge from the loaded artifact. Lead should represent periods when adding those controls.
- `receipt`, `benchmark` and `summary` are `unknown`: runtime narrowing is required before rendering. Do not interpolate raw objects or coerce absent numeric metrics to zero. These are static review findings, not observed UI failures.

## Verification and handoff

- Commands run: `cat` for assigned task/guidance/reference files; `rg --files app docs/lab` and `rg --files app artifacts docs/lab` for changing inventory; `cat app/src/types.ts app/src/main.tsx app/package.json` for bounded static review.
- Ran a Python standard-library check on both owned Markdown files: readable UTF-8, no NUL bytes, local-link target checks, and exactly five numbered research lessons. Passed. External supporting pages were opened through web tools; failed Artifacts article and guessed attribution URL were excluded from the deliverable.
- No build/test was run because the application implementation is not yet present and W1 owns no app paths. No browser journey, responsive, focus or performance pass is claimed.
- First deliverable is ready for master to relay to Hooke. Next bounded follow-up: inspect actual `App.tsx` and the announced endpoint, then append concrete reproduced UX findings here. W3 owns harness/screenshots; lead owns all fixes and integration.
