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
- Company data access is not established. Label sample or synthetic data and
  assumptions clearly. Agreement with original layers does not establish their
  real-world accuracy or independently prove legal compliance.

## Evaluation

- Compare storage requirements, representative plot-query speed, and resource use
  with the original layers.
- Measure decision fidelity: the percentage of plots whose compliance outputs
  **all** match the original-layer results. Assess pixel fidelity where relevant.
- Explain accuracy and information-loss tradeoffs. No numeric passing thresholds
  are specified; infrastructure and processing cost estimates are a bonus.

## Proposed project slice

- The user requested an independent public-data route on 11 October. See
  [public data and project options](docs/systemearth-open-data-options.md) for
  sources, access evidence, ranked ideas, and the recommended Brazilian example.
  Company replies are not a prerequisite for starting a documented prototype.
- Propose forest-risk screening for farm plots in one small region, using a
  forest baseline, annual forest-change observations, and restricted-use areas
  where relevant to the agreed decision. Dataset, region, rules, and stack remain
  open; this is a recommendation for discussion with SystemEarth.
- Use several years and a representative set of plot polygons. For each plot,
  return the agreed forest-at-cut-off result, subsequent change by year,
  restricted-area overlap if in scope, missing-data status, and supporting
  evidence. Confirm exact outputs before choosing what information to discard.
- Build an interactive map with a time selector, plot inspection, and original
  versus encoded results. Highlight disagreements and show measured storage,
  query performance, and fidelity alongside the visual comparison.
- Aim for one complete, reproducible demonstration. This direction combines our
  interests in measurable engineering, explainable decisions, and visualisation;
  it is a proposed scope, not an additional company requirement.

## Questions for SystemEarth

Keep these questions for when company contact is possible. Meanwhile, choose a
public sample and explicitly document provisional rules and outputs. Implement
those rules against the originals before evaluating an encoding; company answers
can revise that contract later.

1. **Use case and rules:** Which country, commodity, regulation or risk-screening
   workflow should we demonstrate? Is a narrow forest-risk screen acceptable?
   Which outputs must match, and what definitions, cut-off dates, thresholds,
   overlap rules, and missing-data behavior produce those outputs?
2. **Small data sample:** Can you provide download access to original layers for
   one region and several years, farm-plot polygons, and documentation? If company
   data is unavailable, is our proposed public-data sample suitable?
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

No company dataset or working company download access is currently confirmed.
Assemble the following from public sources now, and request company equivalents
when available:

- Plot polygons with stable identifiers and a coordinate reference system.
- Original decision-relevant layers covering the same region and relevant dates.
  Examples are a forest baseline, annual changes, and restricted-use boundaries;
  the chosen rules determine the final selection.
- Layer definitions, class codes, units, spatial resolution, coordinate reference
  systems, grid alignment, missing-value codes, observation dates, and versions.
  For boundaries that change over time, request the dates when each version applies.
- Quality or confidence information, known limitations, and permission to use
  and show the sample.
- Reference outputs and decision logic, if available. Without supplied answers,
  implement a documented original-layer baseline and ask the company to review it.

Public fallback checked on 11 October 2026: the European Commission JRC provides
[Tropical Moist Forest data](https://forobs.jrc.ec.europa.eu/TMF/data), including
annual changes for 1990–2025, degradation and deforestation years, and downloadable
GeoTIFF tiles. It is a candidate for a tropical forest example, subject to checking
coverage and definitions against the chosen use case. The site lists free use
with acknowledgement; review the full terms when acquiring the data. Its map-image
service is for visualisation, not analytical input. Plot boundaries and any
restricted-use layer still need separate selection. Data has not been downloaded
or validated locally. Synthetic plot polygons can exercise the pipeline if needed,
but must be labelled and do not establish performance on real farm plots.

## Proposed work sequence

- **11 October:** Choose a public-data use case and region, verify that sample
  files actually open, and write provisional inputs, rules, and expected outputs.
  Keep the company questions ready for later; progress does not depend on a reply.
- **12 October:** Implement queries against the original layers first. Check known
  examples, boundaries, and missing data; freeze a reproducible comparison set.
- **13–14 October:** Implement one compact representation and run the same queries.
  Candidate techniques include compact class codes and storing temporal changes;
  choose after inspecting the data. Preserve unknown values and all history needed
  by the agreed rules. Keep source and rule versions available for each result.
- **15 October:** Measure storage, query time, resource use, decision agreement,
  and relevant pixel agreement. Compare the same region, layers, dates, plots,
  and rules on the same hardware, using a reasonably configured original-layer
  baseline. Count indexes and metadata in encoded storage; report preprocessing
  cost separately and state caching conditions. Investigate every mismatch.
- **16 October:** Complete the map comparison, reproducible run instructions,
  benchmark results, and pitch. Record remaining limitations and prepare a demo
  recording in case the live demonstration fails.
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
