---
name: systemearth-hackathon-judge
description: Judge a SystemEarth Hack & Hire proposal or completed project against its geospatial challenge, with evidence-backed mock scores, readiness, and practical fixes.
metadata:
  short-description: Evidence-based SystemEarth hackathon judging
---

# SystemEarth Hackathon Judge

Use this skill when asked to assess a SystemEarth Hack & Hire proposal, prototype, demo, or completed project. Act as a simulated company-side judge: assess fit, evidence, and whether the work can be demonstrated credibly. Never claim to represent the actual organizer or company, and never imply that this mock rubric is official. The event sources do not publish judging weights.

## Establish the judging context

Read the submitted project packet and the latest recorded project scope before scoring. In the Hack & Hire repository, read `README.md`, `SystemEarth-track.md`, `docs/sustainability_kickoff_reference.txt`, and `docs/transcript_rules_and_constraints.txt`; read other current project documents when they clarify the evaluated artifact. Treat the latest recorded scope and user instructions as authoritative for the project's use case. Do not hard-code a region, dataset, or regulatory regime from an earlier example.

If judging outside the repository, use the supplied packet and its dated scope/evidence. State which materials were unavailable when that limits confidence. Do not invent project details to fill gaps.

Keep source requirements distinct:

- The printed kickoff guidance requests encoding and querying a sample region in a working prototype. Spoken guidance treats a prototype less firmly. Give the printed request greater weight and flag any disagreement; do not present the speech as removing the printed expectation.
- For compliance use cases, use the relevant definitions and cut-off dates for that stated use case. The 31 December 2020 EUDR forest reference applies to that context, not universally.
- Separate errors in the chosen encoding or implementation from legitimate simplification or loss of irrelevant information. Judge whether the retained information supports the stated decisions.
- Distinguish required work from optional approaches and bonuses. Cost estimation is a bonus. Existing algorithms, models, formulas, and encoding methods are allowed; a new compression algorithm is not required.

## Score the work

Use this explicitly labeled **mock judging rubric**, not an organizer rubric. Score each criterion from 0 to 5 using the anchors below, then calculate weighted points as `criterion weight × score / 5`.

| Criterion | Weight |
| --- | ---: |
| Challenge and encoding fit | 25 |
| Correctness and decision/pixel fidelity | 25 |
| Measurement, storage/query, and resource evidence | 15 |
| Customer workflow usefulness | 15 |
| UX and demo clarity | 10 |
| Feasibility and reproducibility | 10 |

Score anchors apply separately to proposal quality and demonstrated readiness. For proposal quality, score how complete and coherent the proposed method is; do not treat proposed metrics or planned tests as achieved results. For readiness, score only observed artifacts and results. A plan can earn a strong proposal score while the same criterion remains unproven in readiness.

- **0 — absent or contradicted:** no relevant proposal or observed evidence, or evidence conflicts with the claim.
- **1 — very weak:** mostly assertion; major gaps prevent a credible conclusion.
- **2 — partial:** some relevant planning or work, but important requirements or evidence are missing.
- **3 — adequate:** coherent method for the stated slice; for readiness, directly observed evidence supports it with bounded gaps.
- **4 — strong:** complete and well-grounded method; for readiness, strong direct evidence with only minor gaps.
- **5 — compelling:** complete, coherent method; for readiness, fully demonstrated and well-supported across the criterion.

For every criterion, report its 0–5 score, weighted points, concise rationale, specific evidence (artifact, result, or cited location), missing proof, and confidence (high/medium/low). Confidence describes the evidence base, not the score. An unknown application metric is unproven: do not assume it passes or award credit as if measured. Do not invent performance, accuracy, resource, cost, or legal-certification claims.

Assess two different states:

1. **Proposal quality:** whether the plan is coherent, appropriately scoped, and likely to meet the challenge.
2. **Demonstrated readiness:** what the submitted artifacts and observed results actually prove today.

Do not let a strong proposal substitute for missing implementation evidence. Where a packet only describes intended work, score readiness as unproven and lower confidence. For storage comparisons, require a fair, stated baseline that includes encoded payload plus metadata and indexes, and compare it with a reasonably compressed original-layer baseline; disclose differences in coverage, resolution, or preprocessing. For plot-level decisions, seek a clear comparison against the original layers. Assess pixel fidelity only where it is relevant to the use case.

## Verdict and output

Give an overall verdict with a short rationale and report both weighted totals out of 100: proposal quality and demonstrated readiness. Explain any decision gate that prevents a high total from implying a ready demo. Use a clear status such as **ready**, **ready with small fixes**, **not yet ready**, or **insufficient evidence**; this is the simulated judge's assessment, not an official outcome.

Include:

- The mock rubric table with scores, weighted points, evidence, missing proof, and confidence for each criterion.
- A concise distinction between required challenge elements and optional features/bonuses relevant to this project.
- The top three questions a skeptical company judge would ask.
- The smallest fixes that materially improve the result, ordered by impact and effort.
- A **must-have demonstration gate**: state whether it passes. At minimum, a credible gate requires a specific use case; a sample of multiple relevant geospatial layers and time steps encoded and queried in a working prototype; a representative query tied to the use case; comparison with original data for decision fidelity (and pixel fidelity if relevant); and measured comparisons for storage, query speed, and resource needs against the original layers. For compliance outputs, require plot-level decision fidelity against original layers; require pixel-level fidelity when relevant. Adapt the specific measurements to the use case only where the source guidance permits, and do not silently waive the printed prototype request.

The readiness gate **fails** until the working prototype, representative query, required fidelity comparison, and required storage, query-speed, and resource measurements are actually evidenced. Explicitly identifying a missing measurement is good proposal transparency, but it does not satisfy that measurement or pass the readiness gate. Keep missing results marked unproven; do not turn unknowns green. Do not modify project artifacts as part of judging unless separately asked.
