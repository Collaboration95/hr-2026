# SystemEarth — Multi-Layer, Multi-Year Geospatial Data

Selected on **10 October 2026**. Organizer allocation and team composition are
not yet confirmed. Build period: **10–17 October 2026**; finals: **17 October**.

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
  spoken guidance is less firm. Plan to deliver the prototype.
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

- Start with one small region, a few essential layers, selected years, and a
  representative set of plot queries. Dataset, use case, and stack remain open.
- Build an interactive map with a time selector, plot inspection, and original
  versus encoded results. Highlight disagreements and show measured storage,
  query performance, and fidelity alongside the visual comparison.
- Aim for one complete, reproducible demonstration. This direction combines our
  interests in measurable engineering, explainable decisions, and visualisation;
  it is a proposed scope, not an additional company requirement.

## Open questions

- Confirm allocation, team, prototype expectations, and evaluation thresholds.
- Select accessible datasets and a region; confirm licensing, attributes,
  resolution, time coverage, and the decision rules to preserve.
- Confirm pitch length, submission format, deadline, and judging weights.

## Sources

- [Printed problem statement](docs/problem_statement_reference.txt) — booklet p. 9.
- [Kickoff guidance](docs/sustainability_kickoff_reference.txt) — slides pp. 21–25.
- [Spoken guidance](docs/transcript_rules_and_constraints.txt) — SystemEarth section.
- [Event rules and open questions](docs/event_rules_and_open_questions.txt).
