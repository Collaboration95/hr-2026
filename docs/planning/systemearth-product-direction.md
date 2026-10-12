# SystemEarth product direction

## Recommendation

**Working name: Plotline** (creative placeholder; unconfirmed). Plotline helps an analyst answer: **“Which supplier claims need review—and can we answer using less data without changing the evidence?”**

The primary user is a company analyst reconciling a supplier due-diligence CSV with farm boundaries and mapped observations. The product face is an evidence-review desk. Under it sits the actual challenge: a compact multi-layer, multi-year query engine that can reproduce plot-level answers while reducing storage and supporting practical queries.

This direction uses the company sample as the most concrete initial workflow, subject to its reuse terms and the limits of its supplied evidence. It does not assert legal compliance, certify ESG performance, or infer that a supplier declaration is true or false. The engineering comparison remains essential; the UI makes its behavior inspectable.

## Why this fits the challenge

The printed challenge asks for a specific use case, multiple geospatial layers across time and space, compact representation, efficient queries, and reproducible plot-level decisions. The kickoff requests essential-layer analysis, a sample encoding and query prototype, comparison with original layers, storage/query/resource measures, plot decision fidelity, and pixel fidelity where relevant. Spoken guidance likewise calls for accuracy, information-loss evaluation, and clear pipeline choices; it treats the working-prototype requirement less firmly than the printed guidance. Preserve that distinction in the pitch and delivery plan.

Evidence: [printed brief](../problem_statement_reference.txt), [spoken rules](../transcript_rules_and_constraints.txt), [kickoff guidance](../sustainability_kickoff_reference.txt). The exact project-level decision rules and performance thresholds are not specified by these sources.

## Three product directions

| Direction | User value and role | Decision |
| --- | --- | --- |
| **Evidence Review Desk** | Triage supplier declarations against mapped observations; inspect each plot, its time context, evidence sources, and whether a compact query preserves the original answer. | **Recommended core.** Gives the company sample a useful job and exposes the engine’s outputs. |
| **Encoding Observatory** | Explore representations, footprint, query behavior, and mismatches through benchmark controls and witness pixels. | Judge-proof mode inside the desk. It should support the review flow and be directly accessible for technical explanation. |
| **Change Replay** | Re-run affected plots when a source layer or version changes, showing which evidence and outputs changed. | Stretch only, after original and compact query results agree on the frozen cohort. |

Do not grow this into a full ESG certification dashboard. A polished dashboard without a compact representation, reproducible query contract, original-layer baseline, and fidelity evidence would miss the engineering challenge.

## Real fixture and honest interpretation

The supplied fixture is `data/company-sample/2026-10-12/200001-17plots-valid_2025-08-02T09_11_12Z.csv` plus `data/company-sample/2026-10-12/200001-17plots-valid.geojson`. The reproducible audit is [company-sample-audit.md](../research/company-sample-audit.md) and [company-sample-audit.json](../research/company-sample-audit.json). It finds 17 CSV rows and 17 Polygon features joined one-to-one by CSV `a3_plot_id` and GeoJSON `ProductionPlace`; there are no repeated, unmatched, or missing IDs. Numbering gaps P-0002, P-0007, and P-0012 are not missing records absent an external expected-record manifest. A prior thread summary alleged a mismatch; the fresh audit corrects that mistaken analysis. Do not present it as an actual data defect.

Use these concrete review examples: P-0003, P-0005, P-0008, P-0010, and P-0013 declare “Indication of deforestation” using “Hansen Tree Cover Loss 2021-2023”; each records on-site verification with evidence and declares “Deforestation-free” and “Compliant” for EUDR. The evidence itself is not available through the supplied fixture: reference values are opaque keys, not inspectable evidence links. Frame the desk question as: **what evidence and decision rule support this transition?** Show the supplier’s indication, stated mitigation, reference key, and final declared status together. These are supplier-declared review leads, not independently discovered satellite conflicts. The sample does not prove whether the evidence is adequate, whether the mapped observation is correct, or whether a legal requirement is met. Never label these five rows unmitigated violations.

The sample describes processing on 4–6 September 2024, harvest on 16 September 2024, and a 2021–2023 loss layer. The relationship between processing and harvest dates needs company semantic clarification; do not characterize their order as expected or anomalous until clarified. Keep the periods distinct: supplier-declared Hansen 2021–23 is one time window; a current screening window such as 2024–25, if supported by acquired source data, is a separate observation window. Do not imply one validates the other. A current release may revise its historical observations, so preserve both observation period and release/version date and do not silently replace the supplier’s historical basis. Opaque references such as `hyperlink-RG1-P-0005` are keys, not working links; P-0003 references a P-0002 key. Present them as unresolved references until the data owner explains them. Declared area and calculated geometry area differ slightly; treat this as method/rounding context, not an error verdict.

The audit reports CSV origin fields as province Surat Thani and district Chai Buri for all 17 rows; the geometry coordinates are consistent with those labels. Preserve the distinction between reported origin and coordinate-derived location in the receipt, but the current audit does not identify a province/origin mismatch. Do not infer that the company fixture is the final geographic scope.

The company sample is the primary **workflow candidate** because it supplies actual declarations and plot boundaries. The audit does not establish external reference answers, regulatory sufficiency, or publication permission. Public datasets can supplement the map observations if license, date, coverage, and provenance are checked. Songkhla/rubber remains a teammate-suggested candidate, not the team’s final choice. The older Brazil direction is superseded only as the current planning preference; it was never a confirmed selection. Keep region/commodity open until sample and access findings support a choice.

## Four separate review concepts

These concepts must remain visually and semantically distinct; none should collapse into a single invented risk score.

| Concept | What the desk can say | What it must not imply |
| --- | --- | --- |
| Input, join, or geometry issue | A record did not join, geometry is invalid/unsupported, or an expected input is absent. | That the supplier or plot is non-compliant. The current sample has a complete 17-to-17 join. |
| Supplier claim vs mapped observation | The declared analysis/mitigation/final status differs in wording or period from mapped evidence. Sort by actionable review reason. | That a mapped indication proves a violation, or that a final declaration is independently verified. Show original supplier status as **declaration**. |
| Source-to-source uncertainty | Selected source layers disagree, use different definitions, dates, coverage, or resolution, or contain nodata. | That a majority vote or one source is ground truth. |
| Encoding mismatch | Compact query output differs from the same query on the source representation. Expose the field, geometry/pixel witness, and query context. | That the supplier evidence changed. This is an engineering fidelity issue. |

Unknown, unavailable, unjoined, or unsupported evidence must never render as green, clear, safe, or no issue. Use explicit unknown/missing/unsupported states. “No flag under this query” describes only the tested data and rule, not a legal conclusion.

## Core interaction and purpose

1. **Review queue, sorted by actionable reason.** The analyst sees source status, period, reason, evidence availability, and plot ID. They can distinguish supplier declaration, mapped signal, source uncertainty, and encoding mismatch. Avoid numeric risk scores. Keep filters tied to real fields and explain why each row appears.
2. **Claim → farm spotlight.** Selecting a review lead links the CSV declaration to the exact plot outline and relevant mapped footprint. Preserve supplier values and source labels. A map highlight gives spatial orientation, not a verdict.
3. **Year → observed mask/evidence.** Selecting a year reveals the corresponding mapped mask/geometry and its source details. Keep supplier-declared Hansen 2021–23, 2024 processing/harvest context, and any confirmed current interval distinct; show observation period separately from release/version date.
4. **Show proof → same-answer comparison.** Run the same query contract against original and compact paths. Show equality and a provenance receipt when answers match. Open a witness pixel/geometry only when an actual mismatch exists, including plot, layer/year, values, CRS/grid/resolution, inclusion rule, source/version, and witness location.

Missing evidence and provenance are core content throughout, not a secondary inspector. The receipt should expose input file/source, version/date, checksum where available, CRS, native resolution, query/rule version, mask/nodata handling, and transformation/encoding notes. It supports reproduction; it is not a certification badge.

### Inspiration reference

Observed in this planning session via T3 preview of the [Global Nature Watch map](https://globalnaturewatch.org/map/): the inspected controls included a broad layer catalog (ForestChange, LandCover, LandUse, Climate, Biodiversity), separate gain/loss year sliders, canopy-density choices, layer information, opacity, and care in describing tree loss versus deforestation. Borrow the clarity of legend, time, and source controls. Plotline should enter through a company submission and review question, then reveal only the layers relevant to that case. This is a bounded interaction reference from one live inspection, not a claim about the full product or a reason to copy its catalog scope.

## Query and benchmark contract

Freeze one query definition and use it unchanged for source and encoded paths. Candidate outputs include source-specific mapped values by plot and year, event/overlap summaries, coverage/unknown indicators, and an explicit reason state. Final fields and inclusion rules depend on the inspected layers; do not imply that every candidate layer is in the core. Keep plot boundaries exact for the query unless a documented transformation is itself measured.

Comparison requirements:

- Match source date/version, CRS, grid origin, native resolution, masks/nodata, time selection, and geometry inclusion rule on both paths. Record any unavoidable normalization separately.
- Do not hide truth-changing behavior in nearest-neighbor resampling. If resampling is tested, expose it as a transformation and measure its effect separately from encoding.
- Do not convert Hansen `treecover2000` into a supposed 2020 forest baseline by subtracting loss. The product definition does not establish that equivalence.
- Count complete representation footprint, including indexes and metadata needed to answer the declared query. Compare with reasonably compressed originals. Report preprocessing separately; do not compare an indexed compact store with an uncompressed source and call the result a fair win.
- Report the real small cohort separately from explicitly synthetic scale/edge cohorts. Never let synthetic cases inflate real-world fidelity claims.
- Measure storage, representative query time and resource use, preprocessing, plot-level decision fidelity, and pixel fidelity where the representation makes it relevant. The brief sets no numeric performance target; report observed values with environment, cohort, and method rather than inventing thresholds.

### Provisional v0 engineering candidate

The [final layer acquisition report](../research/layer-acquisition.md) confirms Hansen v1.13 `treecover2000`, `lossyear`, and `datamask` chips on an aligned native 1,233 × 604 grid enclosing the full 17-plot bounding box; source-window readback is pixel-identical. Chips total 576,999 bytes; the ignored raw source cache totals 224,170,336 bytes. JRC Global Forest Cover Map 2020 v3 tile retries failed with HTTP 500, so JRC remains unavailable and is only an optional later baseline upgrade. Keep annual loss as an event-year code; do not expand it into repeated annual masks by default. JRC and Hansen remain separate because their native grids and product meanings differ; any alignment/join is an explicit, documented operation. Do not bit-pack a resampled grid and describe it as exact fidelity to the original native data.

Optional later JRC-upgrade query: add a JRC baseline-class/coverage summary alongside the Hansen result only if the official tile becomes available and its native grid is explicitly handled. It is not required for provisional v0.

The Hansen-only forest-change query specified below is the provisional v0: use `treecover2000` as 2000 canopy context and annual `lossyear` with `datamask`; it is not a 2020 forest baseline or EUDR screening.

### Recommended provisional v0 to freeze next

Use actual plot P-0003 and the acquired Hansen native-grid `treecover2000`, `lossyear`, and `datamask` chips. This is a concrete, engineered forest-change screening rule, provisional pending company clarification and not a final team/regulatory selection.

- Select cells whose native-grid centers are covered by the polygon; document boundary inclusion as covered (`covers`). Zero selected cells means **insufficient spatial support**, never “clear.”
- Return selected-cell count; per-plot `datamask` counts for 0 nodata, 1 land, 2 water; `treecover2000` integer histogram 0–100 on valid land; and `lossyear` histogram with code 0 (no mapped loss) separate from years 1–25 (2001–2025). Label partial histograms as observed-cell counts and include unknown-cell counts; they are never complete-plot answers. The report's decoded rectangle land/water totals are acquisition QA only, not plot results.
- For each period, `mapped_loss_present` is true if any valid selected land cell has a loss event in that period. It is false only when selected support is fully known (no datamask 0, out-of-coverage, or missing band) and at least one valid land cell exists with no event. Otherwise it is null/unknown. These are mapped-loss signals, not deforestation findings.
- Return null analytical histograms/flags with explicit reasons when no selected cells or no valid-land cells exist, a required band is unavailable, or the plot falls outside chip coverage. Keep available selected-cell/datamask diagnostic counts; preserve nodata and out-of-coverage separately.
- Outputs are counts, not hectares or whole-plot coverage estimates. No 2020 baseline and no legal/EUDR conclusion; this evidence receipt cannot validate the EUDR forest cut-off.
- Receipt binds plot hash, input/chip hashes, product/version, grid/transform, query version, boundary rule, and unknown reason. Source and compact paths must match exactly on all integer, enum, boolean/null, histogram (including loss code 0 separately), unknown-count, and reason fields.
- Candidate codec packs raw canopy 0–100 (7 bits), loss year 0–25 (5 bits), and datamask 0–2 (2 bits) into 14 bits per cell on this shared native grid, with chunk metadata/index. Preserve raw values even where a mask makes them non-analytical. Validate ranges before packing; if a source uses an out-of-range nodata/sentinel code, mark this codec unsupported pending a revised encoding contract—never truncate or silently remap it.
- Compare against the three reasonably compressed source bands over the same AOI, coverage, grid, and dates. Do not count full-tile-to-AOI cropping as a codec saving. Hansen loss is already event-coded; the packed representation may be larger than the sources (for example, after deflate), and no storage win is assumed.

This contract gives the coding agent a locally executable next goal using the verified Hansen chips; JRC remains an optional later baseline upgrade. The source metadata, extent enclosure, alignment, and source-window pixel equality are confirmed in the acquisition report. Company semantic clarification and final team scope remain open.

Benchmark only regional rasters with the same coverage, grid, and dates on both sides. Compare the packed representation with reasonably compressed regional originals, including necessary chunk indexes/metadata; do not compare a crop against a full global tile. Make no storage-win assumption: Hansen `lossyear` is already a compact event-year encoding, so the packed store may not be smaller after indexes and metadata. Finalize or reject this candidate only after source acquisition confirms product metadata, coverage, dates, and native grid.

## First vertical slice

The first goal is **one real plot, one reviewable evidence receipt, two execution paths returning identical answers**. Make the three must-have moments visible: claim → farm spotlight; year → observed mask/evidence; Show proof → same-answer comparison. Then expand to the audited 17-plot batch, and only after that report a separate synthetic stress cohort. This ordering proves the query contract and provenance on a human-checkable example before adding scale or edge cases.

- Start with P-0003, its supplier row and exact polygon, and the provisional Hansen query above; create one inspectable receipt from pinned inputs.
- Run the identical query contract through original-source and compact paths. Both must match every output field exactly; show equality and source/version, query/rule, time, CRS/grid, masks, and geometry method.
- Expand the proven path to all 17 audited rows and polygons; put the five supplier-declared indication-to-final-status rows in the review queue while stating that their referenced mitigation evidence is unavailable in the fixture.
- Add an optional synthetic boundary lab only after the real batch, explicitly tagged synthetic and kept separate from the 17 real rows in every result.
- Include the four review concepts and all required empty/error states. Show observed storage/query/resource measurements when measured; do not fabricate them to complete the story.

Acceptance gates: one real plot has a reviewable receipt and identical answers from both paths; ID joins reconcile; fixture values match source files; period and release/version labels do not merge supplier declaration and mapped observation windows; batch results trace to every input; source/encoding disagreement classes remain separate; unknowns are never presented as a pass; benchmark totals include indexes/metadata and describe compression/method; synthetic results stay separate. No result may be described as legal certification.

## Three-minute illustrative pitch (duration unconfirmed)

Treat three minutes as a rehearsal format, not an organizer requirement. Open with the concrete analyst task: reconcile a supplier claim with a mapped observation and explain what remains to review. Show the five sample rows as declarations that report a deforestation indication, mitigation, and a final “Compliant” declaration; make clear the records do not independently establish a violation or validate that status. Spotlight one plot and its two distinct time contexts. Then switch to the same plot query on original and compact data; show the witness if they differ, or the measured preservation and storage/query comparison if they agree. Close on the practical engineering question: how much data can be reduced while keeping the evidence and decision reproducible? Mention sample size, synthetic cohort separation, and unresolved access/rule assumptions plainly.

## Roles and critical path to 16 October

| Owner | Near-term responsibility | Handoff |
| --- | --- | --- |
| Backend/evidence | Confirm sample schema and province/origin relationship; apply the v0 contract to the verified Hansen chips; optionally revisit JRC if its tile route becomes available; freeze query contract, source versions and benchmark cohort; calculate original reference results. | Fixture map, provenance, query contract, reference outputs, known unknowns. |
| Product/story (main agent) | Hold scope to the review desk; align claims with evidence; maintain decision log and company questions; shape demo/pitch story and review fidelity evidence. | Approved product states, narrative, acceptance gates. |
| Claude design | Create a distinctive visual system and interaction design for the linked evidence-review moments, including keyboard behavior and states. | Reviewable UX handoff; evidence semantics remain fixed. |
| UI coding agent (later authorization) | Implement the approved product states against real fixture/query output after handoff. | Functional demo; coding is a later task, not authorized by this planning document. |

**13 Oct:** settle fixture interpretation, province/origin audit, reuse constraints, and the v0 query contract. **14 Oct:** use the verified Hansen chips for one-plot original answer and receipt; compare compact path. **15 Oct:** expand to 17, investigate every mismatch, then add synthetic stress cases if core is stable. **16 Oct:** freeze demo data and story, verify acceptance gates, prepare fallback screenshots/recording if live data loading is fragile. This is a planning sequence, not an event-published schedule; preserve time for actual build, and confirm the submission cutoff separately.

## Questions to send the company when practical

- What evidence and decision rule underpin the five indication-to-final-status transitions, and what do the reference keys resolve to?
- Are the CSV/GeoJSON sample and derived screenshots permitted in a private demo, public pitch, repository, or only internal analysis? What attribution or retention terms apply?
- Does `ProductionPlace` identify each geometry with the same business meaning as `a3_plot_id`; are numbering gaps expected, and how should origin fields be interpreted against coordinate location?
- Which mapped layers, exact observation windows, definitions, versions, and spatial predicates does the company use? Are 2024–25/latest screening observations available and comparable with the fixture’s stated Hansen 2021–23 interval?
- Which compactness/query workload matters operationally: batch plot review, repeated per-plot queries, updates, or another pattern? What hardware/runtime context should be reported?
- Is a runnable prototype mandatory for judging, and what is the actual final submission cutoff?

These questions refine the prototype; public-data planning can proceed without answers. Keep organizer requirements, company preferences, assumptions, and stretch ideas labelled separately.
