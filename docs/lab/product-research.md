# Plotline interaction research — W1

Research date: 13 October 2026. Official public sources were opened during this session; release/document dates below are what the pages actually display. Recommendations are original adaptations to the local SystemEarth contract, not observed Plotline behavior or measured usability results. No company data was sent to these services.

## Product lessons

### 1. Attach evidence to a specific statement

Anthropic's Citations release describes references to exact source passages rather than a general bibliography. The original news index lists the launch as 23 January 2025; the currently redirected article displays 23 June 2025 and a 30 June Bedrock update. Preserve this date discrepancy rather than claiming the redirected page is an unchanged January release. [Official article](https://claude.com/resources/articles/introducing-citations-api), [official news index](https://www.anthropic.com/news).

Adaptation: every declaration or mapped count needs a local “Inspect basis” action. A supplier status should resolve to its exact CSV field and opaque reference key; a mapped count should resolve to plot ID, observation year/period, selected native cells and source release. Keep the two origins distinct in the inspector. If a mitigation file is absent, show “Reference supplied; evidence file unavailable” rather than manufacturing a source link. P-0003's reference to a P-0002 key is unresolved metadata requiring explanation, not a proven bad claim.

Acceptance: inspecting the supplier's final status does not open a satellite result as if it substantiates that declaration. Inspecting mapped loss selects the actual plot and relevant year, with a textual cell list available alongside the map.

### 2. Let the reader inspect how each number was computed

Anthropic's 8 October 2026 Dashboards release describes clicking numbers to inspect their queries and displaying chart refresh times. This was verified both through web extraction and a T3 preview of the public article; the authenticated dashboard product itself was not tested. [Official release](https://claude.com/resources/articles/dashboards-and-motion).

Adaptation: selecting an observed-cell count opens a compact proof sheet: plot, period, `hansen-centers.v1`, center-in-polygon `covers` selection, masks, source release, and original versus compact values. Display artifact generation time only if available; separate it from source release and observation year. For a frozen export say “Frozen local evidence export,” not “Live” or “Synced.” Null benchmark fields say “Not measured.” Include units/method when engine measurements arrive.

Acceptance: one action from a count reaches its basis; proof retains plot/time selection. The count is labelled cells, never hectares. A year with zero observed events does not imply full support or legal clearance.

### 3. Prioritize actionable attention while keeping the complete cohort reachable

Linear's 3 September 2026 Priority Inbox release separates priority items from the rest and lets users customize selection through sources/filters. [Official release](https://linear.app/changelog/2026-09-03-priority-inbox).

Adaptation: provide an explicit “All plots” view and reason filters such as declared mitigation evidence unavailable, mapped loss observed, support unknown, and encoding mismatch. These categories can overlap. Show the reason on each queue item and calculate counts from the loaded artifact. Unknown support requires attention even when no loss is witnessed. Do not use an opaque risk score or quietly hide plots without leads. Orange marks a declaration needing context, not a violation; lime marks current selection, not legal safety.

Acceptance: an analyst can explain why a row appears, return to all 17 supplied plots when the artifact has them, and distinguish filter-empty from data-loading/error. “No matching plots” offers a clear-filter action. Filtering out the selected plot must not silently leave a seemingly in-scope result panel.

### 4. Make differences local and inspectable

Figma's current Dev Mode documentation provides version comparison, edited-layer lists, side-by-side and overlay inspection, and property values; selecting a changed layer moves to that layer. The document exposes no publication date; checked 13 October 2026. [Official documentation](https://help.figma.com/hc/en-us/articles/15023193382935-Compare-changes-in-Dev-Mode).

Adaptation: proof should compare source and compact results at the same plot, grid and query version. Use a small field table with field name, original, compact and match state. Expose actual `differing_fields` when nonempty, with an evidence-cell witness only when one exists. Keep an equal case quiet and useful: “Same query outputs” plus scope and receipt access. Spatial overlays should preserve exact boundaries and label native cells as selected by center, so whole-cell footprints outside an outline do not look like polygon overlap errors.

Acceptance: agreement is never labelled “Verified compliant.” A mismatch does not imply supplier deception. No mismatch witness is generated for an equal result. Engineering fidelity is clearly separate from source accuracy.

### 5. Give keyboard actions the same context as visible controls

Linear's command-menu release, whose rendered page displays 19 December 2019 despite an 18 December URL, groups commands by function and prioritizes the current context. The 3 September 2026 release adds fuzzy command search and contextual creation behavior. These are a historical foundation plus a current refinement, not a claim that keyboard navigation was newly invented in 2026. [Historical official release](https://linear.app/changelog/2019-12-18-new-command-menu), [current official release](https://linear.app/changelog/2026-09-03-priority-inbox).

Adaptation: first make ordinary Tab/Enter/Space reach queue items, year controls, proof, receipt and close. Optional Cmd/Ctrl+K lists a few meaningful actions for the selected plot (“Inspect proof,” “Open receipt,” “Find plot”), not an invented command platform. Advertise only implemented shortcuts. Escape closes an open overlay and returns focus to its trigger. Global shortcuts must ignore typing in text inputs. Use native year buttons/select controls unless a complete arrow-key tab pattern is implemented.

Acceptance: a user completes queue → plot → year → proof → receipt without a pointer, retains visible focus and gets a sensible return target after closing. No keyboard-only map requirement: provide the same evidence values as text. Reduced motion must retain all selection feedback.

## Contract-derived state copy

These are proposed labels, not computed results. Do not invent a fixture to populate the real cohort.

| Engine condition | Primary label | Required adjacent explanation |
| --- | --- | --- |
| Period flag true, complete support | Mapped loss observed | Observed cell count, period, release |
| Period flag true, partial support | Mapped loss observed · partial support | Witnessed count; remaining unknown reasons |
| Period flag false | No mapped loss in this period | Complete selected support; not legal clearance |
| Period flag null | Mapped result unknown | Explicit reasons; preserve available diagnostics |
| Comparison equal true | Same query outputs | Encoding fidelity for this query; source accuracy untested |
| Comparison equal false | Encoding mismatch | Exact differing fields and actual witness if available |
| Benchmark null | Not measured | No numeric substitute or fabricated percentage |
| Supplier final status supplied | Supplier declaration | Exact original value and missing evidence status |

## First-slice design priorities

- Keep plot identity, selection and observation period visible across map, evidence, proof and receipt. The map should explain spatial support; the queue should explain review reason.
- Give provenance one compact always-visible line (source, release, period) and a full receipt on demand. Long hashes should wrap and remain selectable/copyable; shortening them visually must not alter the downloadable value.
- Use an accessible persistent legend: selected outline, mapped loss cells, other selected native cells, unknown support. The initial chip has three Hansen bands; do not depict missing JRC/WDPA layers as available.
- Present year-2000 canopy as historical canopy context. Do not title it forest-2020 or use it to declare EUDR eligibility.
- Lead owns integration; W3 owns browser harness. This file supplies interaction hypotheses and explicit checks, not implementation or a browser pass.
