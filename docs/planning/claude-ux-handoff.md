# Claude UX handoff: Plotline evidence review

## How to use this brief

Design an exceptional, coherent UX for the **Evidence Review Desk** described here and in [systemearth-product-direction.md](systemearth-product-direction.md). Treat **Plotline** as an unconfirmed creative working name. Claude owns the visual design: choose and define typography, color, layout, motion, and the visual system. The evidence semantics and truth constraints in this brief are immutable. Do not implement application code, choose a final runtime/stack, or fabricate data. Implementation will be planned separately after the evidence/query contract is ready.

Return a coherent, functional design concept with screen hierarchy, annotated key states, interaction details, responsive behavior, a distinctive visual system, and a short rationale for each high-value interaction. Favor craft in the three priority moments: claim → farm spotlight; year → observed mask/evidence; Show proof → same-answer comparison. Missing evidence and provenance are core content. A witness pixel/geometry appears only when an actual mismatch exists.

## Product and user

**User:** a company analyst reconciling a supplier due-diligence CSV with farm boundaries and mapped observations.

**Job:** find which supplier claims need review, inspect what the supplied records and mapped layers actually say, and verify that a compact multi-layer/year query returns the same answer as its source path.

**Product question:** “Which supplier claims need review—and can we answer using less data without changing the evidence?”

The desk is the product face of a compact multi-layer, multi-year geospatial query engine. It must make the engineering proof legible: the same query contract on original and compact representations, with provenance and a witness for any mismatch. It is not a full ESG certification dashboard. No numeric risk score, compliance badge, legal verdict, or invented probability.

## Experiential priorities and inspiration

Design three must-have moments:

1. **Claim → farm spotlight:** from a supplier review lead, reveal its exact plot and relevant mapped footprint while keeping the declaration visible.
2. **Year → observed mask/evidence:** choosing a year reveals the corresponding mask/geometry and source details. Supplier-declared Hansen 2021–23, 2024 processing/harvest context, and any confirmed current interval remain separate; observation period and release/version date are distinct.
3. **Show proof → same-answer comparison:** run the same query through original and compact paths, then show the matching answer and receipt. Show a witness pixel/geometry only if an actual mismatch occurs.

Missing evidence and provenance are core content in these moments. A synthetic boundary lab is optional, explicitly tagged synthetic, and follows the real 17-plot batch. Do not create a broad multi-view catalog experience.

**Bounded inspiration:** observed in this planning session via T3 preview of the [Global Nature Watch map](https://globalnaturewatch.org/map/). The inspected interface exposed ForestChange/LandCover/LandUse/Climate/Biodiversity catalogs, separate gain/loss year sliders, canopy-density choices, layer information and opacity controls, and careful wording that tree loss does not always mean deforestation. Borrow the transparent legend, time, and source controls. Plotline’s entry remains a company submission and review question, which then reveals relevant layers. This describes observed controls only; it makes no claim about GNW’s full capabilities and does not ask to reproduce its broad catalog.

## Source-backed fixture facts

Read the actual sources before designing content:

- [Product direction](systemearth-product-direction.md) gives recommendation, requirements, limitations, query contract, demo sequence, and open questions.
- [Company sample audit](../research/company-sample-audit.md) and [machine-readable audit](../research/company-sample-audit.json) describe the actual fixture.
- CSV: `data/company-sample/2026-10-12/200001-17plots-valid_2025-08-02T09_11_12Z.csv`.
- Boundaries: `data/company-sample/2026-10-12/200001-17plots-valid.geojson`.
- [Printed challenge](../problem_statement_reference.txt), [spoken challenge rules](../transcript_rules_and_constraints.txt), and [kickoff requirements](../sustainability_kickoff_reference.txt) define the engineering objective.

The fresh audit establishes 17 rows and 17 polygons joined one-to-one (`a3_plot_id` ↔ `ProductionPlace`), with no duplicate or unmatched IDs. A prior summary alleged mismatches; that was mistaken and is corrected. Do not put a data-defect badge on numbering gaps P-0002/P-0007/P-0012.

The [final layer acquisition report](../research/layer-acquisition.md) confirms native Hansen v1.13 `treecover2000`, `lossyear`, and `datamask` chips on an aligned 1,233 × 604 grid enclosing the full 17-plot bounding box, with pixel-identical source-window readback. The chips total 576,999 bytes; the ignored raw source cache totals 224,170,336 bytes. Its land/water totals describe the bounding rectangle only, never individual plot results. JRC Global Forest Cover Map 2020 v3 tile retries failed HTTP 500; it is an optional later baseline upgrade, with no JRC values/coverage available. The actual plots fall in Hansen tile `10N_090E`; the teammate-mentioned `10N_100E` tile does not cover them. Songkhla is also not the location of these sample plots. Treat these as acquisition findings, not a final geography/commodity selection.

The Hansen-only forest-change query in the product document is the provisional v0 using verified chips: 2000 canopy context, annual loss, and datamask. It is not a 2020 baseline or EUDR screening. JRC may be added later if its source tile becomes available.

### Provisional v0 content contract

Design the first review around **P-0003** and the exact provisional query in the product direction’s “Recommended provisional v0 to freeze next” section. The three verified native Hansen bands are `treecover2000`, `lossyear`, and `datamask`. The analyst selects native cells whose centers are covered by the plot (`covers`, including boundary centers). Show selected-cell count; per-plot datamask counts (0 nodata, 1 land, 2 water); a 2000 canopy integer histogram on valid land; and a loss-year histogram with code 0 separate from years 1–25 (2001–25). Label partial histograms as observed-cell counts and show unknown-cell counts; never present them as complete-plot answers. Show `mapped_loss_present` for 2021–23 and 2024–25 as separate tri-state signals.

These are count-based observations, not hectares or whole-plot coverage. Zero selected cells means insufficient spatial support. For each period, the flag is true if any valid selected land cell has an event; it is false only with fully known selected support, no missing band/out-of-coverage/datamask 0, and at least one valid land cell with no event. Otherwise it is null/unknown. If no selected cells or no valid-land cells exist, or a required band is unavailable/out of coverage, show null analytical histograms/flags plus the precise unknown reason; retain available selected-cell and datamask diagnostic counts. This contract makes no 2020 baseline, deforestation determination, regulatory pass, or EUDR conclusion; the receipt cannot validate the EUDR forest cut-off.

The original and compact paths must return exact equality for every integer, enum, boolean/null, histogram (including loss code 0 separately), unknown count, and reason field. The provisional 14-bit codec is canopy 0–100 in 7 bits, loss year 0–25 in 5 bits, and datamask 0–2 in 2 bits, with chunk index/metadata on the shared native grid. Preserve raw values under masks, validate ranges, and never silently truncate unknown codes; an out-of-range nodata/sentinel code makes this codec unsupported until its encoding contract is revised. Compare reasonably compressed three-band sources and packed data over identical AOI, coverage, grid, and dates; make no storage-win claim. Acquisition metadata, coverage, alignment, and source-window pixel equality are confirmed; company interpretation and final team scope remain open.

Five rows—P-0003, P-0005, P-0008, P-0010, P-0013—declare “Indication of deforestation” using “Hansen Tree Cover Loss 2021-2023”; they also record on-site verification with evidence and declare “Deforestation-free” and “Compliant” for EUDR. The fixture does not include inspectable mitigation evidence; references are opaque keys. These are **supplier-declared review leads**, not independently discovered satellite conflicts and not violations. Keep the original supplier status visibly labelled as a declaration.

The fixture references 2021–23 loss observations and 2024 processing/harvest facts (processing Sep 4–6, harvest Sep 16). Keep those contexts separate from the acquired Hansen v1.13 observation window through 2025. A newer release may revise its historical observations: show observation window and source release/version date separately. The current mapped observation input is confirmed Hansen; JRC remains unavailable. Make content layouts resilient to an optional later baseline source.

The audit reports CSV province Surat Thani and district Chai Buri for all 17 rows; coordinates are consistent with those labels. Preserve reported origin and coordinate-derived location as distinct provenance fields. The current audit finds no province/origin mismatch. The project geography/commodity remains unresolved. Songkhla/rubber is a teammate suggestion; an older Brazil proposal is only superseded as a planning preference, not a confirmed selection.

## Required product concepts

Show four separate classes with explicit labels and distinguishable non-color cues:

1. **Input / join / geometry issue:** data ingest or spatial validity problem.
2. **Supplier claim vs mapped observation:** compare declared analysis, mitigation, final status, and independently sourced map observation without declaring a verdict.
3. **Source uncertainty:** source layers differ in definition, coverage, observation date, version, resolution, or nodata.
4. **Encoding mismatch:** original-source and compact execution paths disagree for the same query. Make this an engineering fidelity issue, not a supplier issue.

Unknown, unavailable, unsupported, or missing evidence must never look green or like a pass. “No flag under this query” must be scoped to the selected data/rule. No aggregate risk score.

## Content / state / action / data matrix

| Surface or state | Content to show | Primary action | Required data and truthful fallback |
| --- | --- | --- | --- |
| Review queue | Plot ID; supplier-declared fields; observation window; actionable review reason; evidence availability; source/version | Open plot review; sort/filter by real reason | Fixture CSV fields and join. If mapped data is not loaded, say “Mapped observation unavailable,” not “clear.” |
| Review lead detail | Original indication, mitigation declaration, final declared status, opaque reference, date context | Inspect receipt; reveal map/timeline | For five IDs above, label evidence “Referenced by supplier; not available in supplied sample.” Do not assert satellite disagreement. |
| Claim-to-map spotlight | CSV claim linked to exact polygon and selected layer footprint | Toggle layer/year; focus geometry | GeoJSON feature by ID plus actual acquired layer. If layer unavailable, keep boundary and explain what is missing. |
| Plot timeline | Supplier-declared Hansen 2021–23; 2024 processing/harvest; mapped observation intervals; release/version dates | Select time item and spotlight corresponding mask/geometry | Store interval and release as separate fields. Current 2024–25 candidate appears only when a source report confirms it. |
| Execution comparison | Same query and selected plot on original and compact paths; answer fields and observed footprint | Compare; inspect witness on mismatch | Identical query, CRS/grid, resolution, masks, date/version and polygon rule. Do not invent metric values. |
| Provenance receipt | Source/file, checksum, version/date, CRS, native resolution, query/rule version, mask/nodata, transformations, execution path | Expand/copy or inspect source | Show unknown metadata as unknown. Receipt must remain usable when optional fields are absent. |
| Source disagreement | Per-source values and their definitions/date/coverage | Inspect each source independently | Do not resolve by majority vote or present one as truth. |
| Encoding mismatch witness | Plot, layer/year, original vs compact value, location/pixel/geometry, query context | Jump to witness in map and receipt | Only render when outputs differ. Identify transformation/encoding causes separately. |
| Loading | What is being loaded and which stage | Cancel/retry if supported | No premature success tone; keep keyboard focus stable. |
| No overlap | Query completed; geometry/layer have no overlap under stated predicate | Inspect geometry/query predicate or return | Distinguish true zero overlap from missing/nodata. |
| No data | No observations for selected period/source | Change source/time or inspect coverage | Never substitute zero or a pass. |
| Failed | Which operation failed, safe human-readable reason, retry path | Retry or return to prior stable view | Preserve selection/query context if possible. |
| Unsupported query | Which selected operation is unsupported by this representation | Compare supported query or inspect limitation | Do not silently fall back to different semantics. |

## Interaction priorities

1. The user can enter from a specific review reason, then follow that row to the exact plot without losing the declaration context.
2. Map and table are linked in both directions. Selecting a plot focuses its outline; selecting the outline identifies the table row. Use a visible focus/selection state beyond color.
3. Timeline selection links to a specific year mask or geometry. The display must distinguish the event/observation interval from dataset publication/release date.
4. Original/compact controls run semantically identical queries. A mismatch opens a witness and provenance; equality still exposes cohort and query context.
5. Every key action works by keyboard. Provide logical focus order, visible focus, accessible names for map controls, and a non-map route to all plot evidence.
6. Respect reduced-motion preferences. Any time transition remains understandable as a state change without animation.

## First demo flow

Design around this sequence: **one real plot → one reviewable evidence receipt → two execution paths returning identical answers → batch of 17 → optional synthetic boundary lab**. The three moments are claim-to-farm spotlight, year-to-observed-mask/evidence, and Show proof-to-same-answer comparison. The first five queue leads arise from supplier declarations whose referenced mitigation evidence is unavailable in the sample. They are not proof of mapped conflict. A synthetic cohort is a later, distinct stress dataset and must never be visually or numerically blended into the 17 real fixture plots.

For the illustrative three-minute pitch (duration unconfirmed): show the analyst task; one of the five declarations and the missing inspectable evidence; the plot boundary and clearly separated date contexts; the source/compact answer equality and receipt; then the batch and measured benchmark only if actual results exist. End with the engineering claim: reduce data while preserving reproducible answers. Do not fabricate storage, latency, accuracy, or performance targets.

## Measurable UX acceptance checks

The design handoff should let a reviewer verify each point without guessing:

- Starting from P-0003 (or another confirmed lead), a reviewer can reach its CSV declaration, matching polygon, timeline, and provenance receipt in no more than three deliberate selections after the queue is visible.
- The five review leads are presented as supplier declarations; each states that referenced mitigation evidence cannot be inspected in the supplied fixture. None receives a violation or satellite-conflict label by default.
- The 2021–23 supplier window, 2024 processing/harvest context, and any confirmed 2024–25 screening interval have visibly distinct labels; observation dates and release/version dates are not conflated.
- In the comparison state, users can tell which two execution paths are being compared, that the query contract is identical, and where a mismatch witness would appear. No unmeasured numeric result is shown as fact.
- Unknown, unavailable, failed, unsupported, and no-overlap states can be distinguished without color alone and without interpreting blank as zero/pass.
- Table-to-map and map-to-table navigation is available by keyboard with visible focus. Reduced-motion mode preserves the same information and actions.
- The design has explicit loading, no overlap, no data, failed, and unsupported-query states, each with a clear recovery or explanation action where one is possible.
- The real 17 and synthetic stress cohort have separate labels, counts, and result groupings.

## Requested design deliverable

Provide:

- A short design rationale tied to this user task and the challenge’s compact storage/query/fidelity requirements.
- A concise flow specification centered on the three must-have moments; define the key review state and its linked map, time, comparison, and receipt behavior without adding unnecessary views.
- State coverage for the matrix above, with particular care around unknown evidence and source/encoding disagreement.
- Interaction notes for keyboard, reduced motion, selection retention, responsive layout, and dense table/map coordination.
- A content specimen using actual fixture IDs and exact declaration wording from the audited files; mark unmapped/acquisition-dependent content as a placeholder instead of inventing it.
- Open assumptions that depend on the incoming data-agent report, company answers, or later product decisions.

Keep the output actionable for a future UI coding agent. Describe hierarchy, visual system, behavior, states, and data bindings. Do not make a final stack decision, create implementation code, or claim that source acquisition, current screening observations, or company data reuse terms are confirmed.
