# SystemEarth — Multi-Layer, Multi-Year Geospatial Data

Selected on **10 October 2026**. The user reports acceptance into this track on
**11 October 2026**; team composition is not recorded. The original event notes
give a build period of **10–17 October 2026** and finals on **17 October**.

The challenge-page screenshot supplied on 11 October lists a start of **11 October,
00:00 SGT** and an end of **17 October, 00:00 SGT**. Midnight is the start of
17 October. Confirm whether the page's end time closes applications or project
submissions, and confirm the actual submission and pitch times. Until clarified,
plan to have the deliverable ready on 16 October.

## Problem

Plot-level risk analysis combines geospatial layers across years, such as forest
baselines, tree-cover loss, and restricted-use areas. Build a compact representation
that supports efficient queries while preserving the information needed to
reproduce the original layers' plot-level compliance decisions.

## Requirements and constraints

- Choose a specific use case, relevant layers, attributes, and time periods.
- Explain what can be simplified, summarised, or dropped, and why. For a
  compliance use case, ground those choices in the applicable definitions.
- Describe an encoding strategy combining layers and time steps; encode and
  query a sample region. The printed guidance requests a working prototype;
  spoken guidance is less firm. The challenge-page screenshot supplied on
  11 October also explicitly requests a working prototype. Plan to deliver it.
- Compare against the original layers and explain pipeline choices, information
  loss, and any AI outputs used.
- Existing algorithms, models, and encoding methods are allowed. A new compression
  algorithm is not required. No dataset, language, region, resolution, or time span
  is mandated in the recorded guidance.
- A company CSV/GeoJSON sample is acquired locally; original analytical layers
  and reference rules are separate inputs. Label supplied and synthetic data and
  assumptions clearly. Agreement with original layers does not establish their
  real-world accuracy or independently prove legal compliance.

## Evaluation

- Compare storage requirements, representative plot-query speed, and resource use
  with the original layers.
- Measure decision fidelity: the percentage of plots whose compliance outputs
  **all** match the original-layer results. Assess pixel fidelity where relevant.
- Explain accuracy and information-loss tradeoffs. No numeric passing thresholds
  are specified; infrastructure and processing cost estimates are a bonus.

## Recommended project slice

- **Plotline** is the recommended working name and product direction: an analyst
  reviews supplier declarations alongside mapped evidence, then inspects proof
  that a compact multi-layer, multi-year representation preserves the same query
  outputs as the original layers. See [product direction](docs/planning/systemearth-product-direction.md)
  and [Claude UX handoff](docs/planning/claude-ux-handoff.md). This is a recommendation,
  not a final team selection or an additional company requirement.
- Start with the locally acquired company sample: **17 CSV records and 17 polygons
  matched one-to-one**, with no duplicate or unmatched IDs. The CSV labels all
  records Surat Thani, Chai Buri, Thailand. Bounds are **98.772429–99.080292° E,
  8.431179–8.581888° N**. These are audited labels and coordinates, not independent
  verification of administrative location. See the [sample audit](docs/research/company-sample-audit.md).
- Five records (P-0003, P-0005, P-0008, P-0010, P-0013) declare a deforestation
  indication, on-site verification with evidence, and a final deforestation-free/
  compliant status. Use them as declaration-backed evidence-review leads. Their
  referenced mitigation evidence is not inspectable in the supplied fixture;
  these records do not establish violations or independently validate compliance.
- Recommend the Surat Thani-labelled sample as the initial region. Songkhla/rubber
  remains a teammate proposal; the earlier Brazil direction is historical research
  in [public data and project options](docs/systemearth-open-data-options.md).
  Final team geography and commodity remain open; the authorized local lab uses
  Python 3.14 and React/TypeScript/Vite for this sample-first prototype.
- First complete **one real plot, a reviewable evidence receipt, and identical
  declared outputs from original and compact query paths**. Then expand to all
  17 plots. A receipt should identify the exact plot, source versions, observation
  period, rule/query, grid and geometry method, coverage/unknowns, result, and
  evidence needed to reproduce it. Keep supplier declarations distinct from
  mapped observations, source uncertainty, and encoding mismatches.
- Compare storage, query time, resource use, and fidelity on the same inputs and
  rules. The interface should make the evidence and measured comparison easy to
  inspect. Change replay and a separately labelled synthetic edge/scale cohort
  follow the real sample comparison if time permits.
- The local app and original/compact query paths are implemented for all 17 plots.
  Independent verification and measured optimization continue in the
  [research lab](docs/lab/charter.md); [README](README.md) records current run/test
  commands. The existing sample audit uses Python's standard library:
  `python3 scripts/inspect_company_sample.py` regenerates
  `docs/research/company-sample-audit.json` from the two local sample files.

## Public-layer acquisition status

The final [layer report](docs/research/layer-acquisition.md) and
[provenance](data/public/provenance.json) document acquired Hansen GFC 2025
**v1.13** `treecover2000`, `lossyear`, and `datamask` from `10N_090E`.
The three chips total **576,999 bytes**, share an aligned **1233 × 604** native
EPSG:4326 grid, contain the full 17-plot bounding box using outward floor/ceil
bounds, and equal the source windows pixel-for-pixel on readback. Full source
tiles total **224,170,336 bytes** in the ignored raw cache. Acquisition of these
inputs is complete. The [engine report](docs/lab/engine-report.md) now records
plot-query, codec, and benchmark implementation evidence; acquisition checks
alone do not establish those results. Apply the datamask before interpreting loss-year zero as observed
no loss. Bounding-rectangle pixel counts are not plot-overlap results.

The sample lies around 99° E; the teammate's Songkhla tile `10N_100E` does not
cover it. The source-acquisition setup and command are recorded in the final
layer report; current application commands are in README.

The official JRC Global Forest Cover 2020 v3 tile request returned HTTP 500 on retry.
The lab subsequently acquired an official **v4** native-grid chip and provenance;
its separate companion is under independent review, as recorded in
[the JRC report](docs/lab/engine-jrc-report.md). This does not retroactively supply v3
or change the retained Hansen benchmark. WDPA is conditional on applicable use and
redistribution terms. Do not reconstruct a claimed 2020 forest baseline merely
by subtracting Hansen loss from 2000 canopy cover. Keep the supplier's stated
2021–2023 Hansen interval separate from a newer source release and any new
observation window. Acquisition does not establish a query benchmark or an
independent compliance result.

## Questions for SystemEarth

Confirm these questions in parallel with the first plot demonstration. Use the
acquired sample and explicitly documented provisional rules/outputs to progress;
company answers can refine the contract. Compute results against original layers
before evaluating an encoding. Unknown field meanings or missing evidence must
remain visible rather than becoming assumed approvals.

1. **Use case and rules:** Which country, commodity, regulation or risk-screening
   workflow should we demonstrate? Is a narrow forest-risk screen acceptable?
   Which outputs must match, and what definitions, cut-off dates, thresholds,
   overlap rules, and missing-data behavior produce those outputs?
2. **Sample and field meanings:** For the supplied CSV/GeoJSON pair, what do the
   processing/harvest dates and opaque evidence-reference keys mean? What evidence
   and rules support the five indication-to-final-status transitions? Can you
   identify original layer versions for the reported 2021–2023 analysis and
   provide supporting documentation? Is the proposed public-layer supplement suitable?
3. **Reference answers:** Can you provide a few plots with expected outputs and
   explanations, or the existing query/rule logic? Include an unflagged plot, a
   flagged plot, a boundary case, and a plot with missing or uncertain data. Who
   can review our interpretation promptly?
4. **Representative workload and fidelity:** What plot sizes, batch sizes, time
   queries, and update frequency matter most? Must all selected outputs match
   exactly, which pixel values must be recoverable, and are any tolerances or
   numeric performance targets expected?
5. **Data use:** May supplied data appear in the public repository, demo, and
   slides? Are there attribution, anonymisation, or redistribution conditions?

## Questions for the organizers

- Does the displayed **17 October, 00:00 SGT** end time apply to applications or
  project submissions? What is the exact project submission deadline and timezone?
- Where should we submit, what artifacts are required, how long is the pitch,
  and when and where do we present? The screenshot says on-site, while earlier
  event guidance offered online pitching; confirm the applicable arrangement.
- What are the judging weights, and which company contact or group should handle
  technical questions? Confirm that team membership is correctly recorded.

## Minimum data package

The supplier CSV and plot GeoJSON are acquired and audited locally. The retained Hansen
benchmark package implements the following requirements; new layers must meet
them separately while company clarification proceeds:

- Preserve the 17 exact plot geometries, stable join IDs, supplied declarations,
  and source checksums. The audit's complete join does not validate declarations.
- Freeze the decision-relevant subset and dates from the acquired three Hansen
  bands. A separately versioned JRC2020v4 companion is under review; any
  restriction layer remains conditional. The chosen query determines which
  layers are essential and which can be left outside the first slice.
- Record layer definitions, class codes, units, resolution, CRS, grid alignment,
  masks/nodata, observation dates, release versions, and coverage. Preserve
  source differences; a current release may revise historical values.
- Record quality limits and permitted sample uses. Local possession does not
  establish permission for external publication, public pitches, or redistribution.
- Compute a documented original-layer reference answer and retain its evidence
  receipt. Supplier final statuses are declarations, not reference answers for
  assessing encoding fidelity or independent legal compliance.

The [October 11 public-source catalog](docs/systemearth-open-data-options.md)
remains historical research, including JRC Tropical Moist Forest as an alternative
candidate. Its earlier access checks are not evidence that those products are
acquired for this sample. The [layer acquisition report](docs/research/layer-acquisition.md)
records current acquisition; keep failed or conditional inputs explicitly missing.

## Proposed work sequence

This is a conservative project plan, not an organizer-published schedule. Target
readiness on 16 October while confirming the actual deadline separately.

- **13 October:** Reconcile the audited fixture and layer acquisition, freeze the
  first plot and provisional query contract, and keep company questions moving
  in parallel. Pin masks, versions, dates, and coverage before declaring inputs ready.
- **14 October:** Produce one real plot's original-layer result and reviewable
  receipt, then compare one compact representation against exactly that query.
  Preserve unknown values and necessary history; investigate every mismatch.
- **15 October:** Expand to all 17 real plots. Measure storage, query time, resource
  use, plot fidelity, and relevant pixel fidelity on identical inputs and hardware.
  Compare with a reasonably configured compressed-original baseline, include
  indexes/metadata in compact storage, and report preprocessing and caching
  separately. Only then consider a separate synthetic edge/scale cohort.
- **16 October:** Freeze the demonstrable slice, run instructions, evidence and
  benchmark results, and pitch. Complete the planned interface work through the
  design handoff and subsequent implementation task. Record limitations and
  prepare a fallback recording. Use the [mock judge review](docs/planning/hackathon-judge-review.md),
  to prioritize remaining gaps; it is not an official rubric.
- **17 October:** Present at the organizer-confirmed time.

Aim for every agreed output to match on every test plot; this is our proposed
engineering target, not a company-specified passing threshold. Report the test-set
size and mismatches, and do not infer correctness on unseen plots from the test
percentage alone. Agreement with the source layers measures preservation, not
independent legal compliance. Optional cost estimates follow the working comparison.

## Sources

- [Printed problem statement](docs/problem_statement_reference.txt) — booklet p. 9.
- [Kickoff guidance](docs/sustainability_kickoff_reference.txt) — slides pp. 21–25.
- [Spoken guidance](docs/transcript_rules_and_constraints.txt) — SystemEarth section.
- [Event rules and open questions](docs/event_rules_and_open_questions.txt).
- User-provided challenge-page screenshot, received 11 October 2026, titled
  "Building Multi-Layer, Multi-Year Geospatial Data". Confirms the prototype and
  evaluation deliverables and supplies the page dates; it provides no dataset links
  or decision rules.
- [Company sample audit](docs/research/company-sample-audit.md), [layer acquisition report](docs/research/layer-acquisition.md), and [thread recovery](docs/research/prior-thread-context.md) — current local evidence and active/prior-session distinctions.
