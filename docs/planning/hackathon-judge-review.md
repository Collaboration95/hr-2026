# Simulated company-side judge review

**Refreshed:** 13 October 2026

**Verdict:** **Not yet ready**

**Assessment:** Proposal quality **78/100**; demonstrated readiness **22/100**.

This is an independent simulated company-side assessment, not an official organizer or company score. The event sources publish no judging weights; the rubric below is explicitly a mock rubric. I assessed the final README, track brief, product direction, UX handoff, sample audit, layer report, provenance, and acquisition/audit scripts. The reported reruns and validation checks support the acquired inputs only; no application or engine metrics are claimed.

## Verdict

The final packet now gives a coherent and unusually specific v0 proposal. It names a bounded Hansen-only forest-change query, explains the native-cell selection rule and tri-state unknown behavior, proposes an explicit 14-bit candidate codec, requires exact source-versus-compact output equality, and specifies a fair compressed-source comparison without presuming a storage win. The final acquisition report and provenance establish three aligned native-grid Hansen bands covering the sample bounding box, checksums and source-window readback equality, and a necessary datamask caveat: loss-year values on water cannot be interpreted as land events.

This materially strengthens proposal quality. It does not establish implementation. There is still no working prototype, encoded store, executed plot query, source/compact output comparison, plot-level fidelity result, or query/resource benchmark. The printed guidance requests a working prototype, and the must-have demonstration gate therefore fails. The 22/100 readiness score recognizes direct sample/acquisition groundwork and reproducibility, while leaving the central engineering work unproven.

## Mock judging rubric

Scores are separate for proposal quality and observed readiness. Weighted points are `weight × score / 5`. Readiness uses artifacts and results only; a detailed proposal does not count as implementation evidence.

| Criterion (weight) | Proposal quality: score / weighted points and rationale | Demonstrated readiness: score / weighted points and observed evidence | Missing proof | Confidence |
|---|---|---|---|---|
| Challenge and encoding fit (25) | **4/5 · 20/25.** The provisional v0 is tied to a concrete plot-level forest-change query on the acquired `treecover2000`, annual `lossyear`, and `datamask` bands. It handles distinct periods and says this is not a 2020 baseline or EUDR determination. The 14-bit packing layout (7+5+2 bits) is specific, and the packet recognizes it may not beat compressed originals. | **2/5 · 10/25.** The 17-plot CSV/GeoJSON fixture and three verified Hansen chips are present. They are aligned inputs, not a combined compact multi-layer/time representation or query engine. | Implement the codec and query path, including chunk/index metadata; demonstrate the selected spatial and temporal query on it. | **High.** Proposed scope and observed artifacts are explicit. |
| Correctness and decision/pixel fidelity (25) | **4/5 · 20/25.** The contract specifies center-covered native cells, histograms, period-specific loss signals, tri-state false/true/null semantics, unknown reasons, and exact equality across all output fields. It preserves masked raw values and rejects unsupported ranges rather than truncating. | **0/5 · 0/25.** Parent-reported source hashes, chip coverage, readback, and script validation support acquisition integrity. No original query outputs, compact query outputs, equality comparison, plot decision-fidelity result, or codec pixel comparison are evidenced. | Execute the exact query on both paths; compare every output, unknown count/reason, and pixel value; report plot-level fidelity over the defined cohort. | **High** that the central comparison is absent; high for the stated acquisition validation. |
| Measurement, storage/query, and resource evidence (15) | **4/5 · 12/15.** The packet now requires reasonably compressed regional originals, identical AOI/grid/dates, metadata/index inclusion, and separate reporting of preprocessing. It correctly disallows treating full-tile-to-chip reduction as codec savings and expects no storage-win assumption. | **1/5 · 3/15.** Provenance records source/chip sizes and confirms source-window equality. These are acquisition measurements, not codec-versus-baseline storage, query latency, or resource evidence. No engine metrics exist. | Measure compressed originals and packed representation over identical support; include metadata/indexes; record representative query time and resources with runtime/hardware and method. | **High.** Final documents explicitly separate acquisition metrics from unmeasured engine metrics. |
| Customer workflow usefulness (15) | **4/5 · 12/15.** The evidence desk makes the query inspectable in an analyst workflow, with a receipt and separate supplier-claim, mapped-observation, source-uncertainty, and encoding-mismatch concepts. The five supplier declarations remain explicitly unverified review leads. | **1/5 · 3/15.** Actual declarations and matching plot geometries provide workflow inputs. No running queue, plot review, receipt, or user evaluation is available. | Build the smallest review flow backed by actual query output and provenance; confirm the company sample’s permitted use and opaque evidence-reference meaning. | **High** for fixture-backed relevance; low for demonstrated usability. |
| UX and demo clarity (10) | **4/5 · 8/10.** The handoff is concrete about the P-0003 flow, visible unknown states, date/version distinction, histogram scope, selected-cell support, and equality/mismatch display. It avoids claims of full-plot coverage where the query only samples covered cell centers. | **1/5 · 2/10.** The handoff is a design specification. No implemented or rendered interface has been observed. | Implement and review the key flow and state coverage with real query results; prove keyboard and non-map access in the working demo. | **High.** Design and implementation status are unambiguous. |
| Feasibility and reproducibility (10) | **3/5 · 6/10.** The one-plot-first sequence is suitably bounded, and the acquisition/query contracts include pinned data and explicit unknown behavior. The codec remains a candidate, spatial support and query rules still need execution-level confirmation, and app stack/build path remain undecided with little time left. | **2/5 · 4/10.** The sample audit and acquisition scripts are reproducible; the final report records versions, checksums, coverage, alignment, and readback. Parent reports rerunning both scripts and checking source hashes/chip coverage/readback/skill validation. These checks establish input integrity, not engine reproducibility. | Freeze runtime and commands; make one end-to-end query reproducible from pinned source to compact output and benchmark result. | **Medium-high.** Acquisition reproducibility is well documented; application feasibility remains open. |
| **Total** | **78/100** | **22/100** | **Readiness gate fails.** | **High** for the planning/evidence distinction. |

## Required work and optional work

The printed guidance requires a specific use case; multiple geospatial layers over time and space; a reasoned choice of what to retain, simplify, summarize, or drop; an encoding strategy; a working prototype encoding and querying a sample region; comparison with original layers; and measurements of storage, representative query speed, resource needs, and plot-level decision fidelity. Pixel fidelity is relevant where the representation requires it. Spoken guidance is less firm about the prototype, but does not erase the printed request.

No new compression algorithm, specified language, mandated dataset, numeric performance threshold, or full production platform is required. Cost estimation is a bonus. JRC is an optional later baseline and is presently unavailable; WDPA is conditional on its terms. The current v0’s 2000 canopy context and 2001–2025 event-year data must not be presented as a 2020 forest baseline or legal deforestation finding. The proposed tri-state signals are mapped-loss indicators under the stated query, not compliance outcomes.

## Must-have demonstration gate

**FAIL — not demonstrated.** The required gate is a specific use case; a working prototype that encodes and queries multiple relevant layers and time steps; a representative use-case query; comparison with original data for decision fidelity (and pixel fidelity where relevant); and measured storage, query speed, and resource needs against original layers. Compliance use cases require plot-level decision fidelity against original-layer results.

The proposal now specifies much of the intended contract and a codec candidate. Observed evidence establishes the source fixture and acquired three-band input package. The packet itself states that the application, compact representation, plot queries, and benchmarks have not been built. Script success, chip hashes, coverage, alignment, and pixel-identical source-window readback prove acquisition integrity only. They do not pass the prototype, fidelity, or engine measurement gates. Those results remain **unproven**.

## Three skeptical judge questions

1. Can you show P-0003’s exact selected cells and tri-state period results from both paths, including how the `covers` boundary rule, datamask, missing coverage, and null reasons affect the answer?
2. Does the packed representation preserve every source value and the full query output on the full 17-plot cohort, and what happens if an input contains an out-of-range or sentinel value?
3. After including compression, indexes, and metadata on both sides, what are the measured storage, query-time, and resource differences—and is the 14-bit candidate actually useful compared with the already compact loss-year source?

## Biggest scope risk

The central risk is spending scarce build time on the evidence-review UI or optional data acquisition before implementing and benchmarking the proposed codec/query. A usable one-plot comparison across source and compact paths is the critical demonstration; the acquisition is ready, while that implementation is not.

## Smallest fixes with the highest impact

1. Implement the proposed 14-bit pack/unpack path with explicit range rejection and metadata, then immediately round-trip all three chips and compare every decoded cell with source values.
2. Implement the P-0003 native-cell query contract once over originals and once over the compact representation. Emit a machine-readable receipt and exact field-by-field equality result, including unknown reasons.
3. Expand that comparison to all 17 plots and report decision fidelity. Investigate every difference; keep partial support, no selected cells, missing bands, and datamask unknowns distinct from false/no-loss.
4. Benchmark reasonably compressed regional originals against the packed representation on identical coverage/grid/dates. Include metadata/indexes, query speed and resource measurements, runtime/hardware, and preprocessing separately. Report the measured result even if packing increases storage.
5. Only then bind the query output into the review UI and rehearse the evidence receipt. Keep the supplier’s declaration separate from the mapped Hansen result and do not claim legal or EUDR status.

## Evidence limits

The final layer report and provenance support the three Hansen GFC 2025 v1.13 inputs on one native EPSG:4326 grid, full supplier bounding-box coverage, checksums and source-window readback equality. The rectangle contains 744,732 cells and includes 56 nonzero loss-year values over permanent-water cells, supporting the proposed need to use `datamask`. Those counts are bounding-rectangle acquisition diagnostics, not per-plot results. JRC 2020 v3 remains unavailable after HTTP 500; no 2020 baseline or restriction layer is present. The company sample’s 17-to-17 join is audited, but it supplies no independent reference answer for legal or compliance decisions.

The plan proposes selecting native cells whose centers are covered by the plot. This is a crisp computational rule, but it can omit boundary-adjacent cells and does not itself define an authoritative regulatory plot-overlap method. The query should describe the output as observed-cell counts/signals under that rule, and the plotted-cell support/unknowns must be visible. Company interpretation, sample publication permissions, final team scope, and final application stack remain unresolved. No application, codec, query-output, storage benchmark, query-speed metric, or resource metric was available in this review.
