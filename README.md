# Hack & Hire — Sustainability Edition 2026

A week-long project for Hack & Hire, organized by Projet with NUS CAT. Participants work on a real company challenge, build something useful, and present directly to company teams. The build period is **10–17 October 2026**, with finals on **17 October**. Participation is solo or in a team of two or three.

This repository holds the project context for the selected SystemEarth track and will hold its implementation. The aim is a practical, demonstrable outcome with clear reasoning and evidence.

## Current status

- **Selected track:** SystemEarth — Multi-Layer, Multi-Year Geospatial Data, selected on 10 October 2026. See [track brief](SystemEarth-track.md) for constraints, evaluation, and proposed scope.
- **Team and allocation:** User reports acceptance into the SystemEarth track on 11 October 2026; team composition not recorded.
- **Recommended product:** **Plotline**, an evidence-review workflow for supplier declarations and mapped observations, backed by a compact encoding and measured original-versus-compact query/fidelity proof. See [product direction](docs/planning/systemearth-product-direction.md). This is a planning recommendation; final team scope and stack remain undecided.
- **Company sample acquired locally:** The [audit](docs/research/company-sample-audit.md) confirms 17 CSV records and 17 GeoJSON polygons matched one-to-one, with no duplicate or unmatched IDs. The CSV labels them Surat Thani, Chai Buri, Thailand; bounds are **98.772429–99.080292° E, 8.431179–8.581888° N**. Recommend starting with this sample. Songkhla/rubber remains a teammate proposal, not a final team decision or the supplied sample's location.
- **Review leads:** Five sample rows declare a deforestation indication, mitigation with evidence, and a final deforestation-free/compliant status. These are declaration-backed review leads; the sample does not independently verify the mapped signal, mitigation evidence, or legal outcome.
- **Public layers acquired:** Hansen GFC 2025 v1.13 `treecover2000`, `lossyear`, and `datamask` from `10N_090E`. The three native-grid chips total **576,999 bytes**, share a **1233 × 604** grid, cover the full 17-plot bounding box with outward-aligned bounds, and match their source windows pixel-for-pixel on readback. Full source tiles total 224,170,336 bytes in the ignored raw cache. The JRC v3 2020 baseline remains missing after HTTP 500 on retry; WDPA use remains conditional on its terms. See the final [layer report](docs/research/layer-acquisition.md). Acquisition is complete for these Hansen inputs; plot queries, encoding, and fidelity benchmarks are still to be built. The [October 11 catalog](docs/systemearth-open-data-options.md) remains historical research.
- **Implementation:** No application has been built; application stack, dependencies, build commands, and test suite remain undecided. A Python standard-library sample audit exists: `python3 scripts/inspect_company_sample.py` regenerates `docs/research/company-sample-audit.json` from the local sample.
- **Next goal:** One real plot with a reviewable evidence receipt and the same declared query outputs from original and compact data; then expand to all 17. Confirm rules and field meanings with the company in parallel, while documenting provisional assumptions and unknowns.
- **Planning window:** Use 13–16 October for the first complete slice, batch comparison, and demo preparation; conservatively aim to be ready on 16 October. See [track work sequence](SystemEarth-track.md#proposed-work-sequence).
- **Deadline clarification:** The challenge-page screenshot provided on 11 October shows an end time of 17 October at 00:00 SGT. Confirm whether this is the application closing time or project submission deadline; finals remain recorded as 17 October.

Update this section when a decision is made so subsequent work starts from the current project state.

## Available tracks

| Company | Challenge | Main outcome |
| --- | --- | --- |
| BlueNexus | Operational data analytics | Identify abnormal or inefficient water-plant operation and suggest savings while maintaining treatment performance. |
| BlueNexus | Sustainability impact reporting | Explain and report autonomous water-system impact credibly for client ESG reporting. |
| Bizsu | Lead generation and sales | Develop a scalable approach to qualified leads and sales. Confirm the intended audience. |
| Bizsu | Brand awareness through content | Produce actual content that explains the product and motivates potential customers to act. |
| beez-fm | Building technology fit | Help building owners understand and trust an efficiency-technology recommendation using their energy profile. |
| SystemEarth | Geospatial data | Represent multiple layers across time and space compactly, with efficient queries and preserved plot-level compliance decisions. |

## Project references

These are the current references. Read the documents relevant to the task.

| Document | Use it for |
| --- | --- |
| [Problem statements](docs/problem_statement_reference.txt) | Comparing tracks, understanding the printed company briefs, and defining the intended outcome. |
| [Company discussion and project guidance](docs/transcript_rules_and_constraints.txt) | Spoken clarifications, practical scope, targets, suggested approaches, data offers, and questions for company representatives. |
| [Kickoff guidance](docs/sustainability_kickoff_reference.txt) | Slide-based requirements and SystemEarth's layer analysis, prototype expectations, and storage/query/fidelity evaluation. |
| [Event instructions and open questions](docs/event_rules_and_open_questions.txt) | Registration links, track ranking, allocation updates, finals, the optional workshop, and differences between sources. |
| [Company sample audit](docs/research/company-sample-audit.md) | Reproducible join, geography, field interpretation, and declaration-backed review leads. |
| [Recovered conversation context](docs/research/prior-thread-context.md) | October 11 history, active-session provenance, and corrected earlier claims. |
| [Product direction](docs/planning/systemearth-product-direction.md) | Recommended Plotline scope and engineering proof. |
| [Claude UX handoff](docs/planning/claude-ux-handoff.md) | Current design handoff for Claude. |
| [Public-layer acquisition report](docs/research/layer-acquisition.md) | Final three-band Hansen acquisition evidence and missing/conditional layers. |
| [Hackathon judge review](docs/planning/hackathon-judge-review.md) | Mock project evaluation; not an official judging rubric. |

Some instructions need confirmation. Bizsu's printed lead-generation brief targets homeowners, while the spoken brief targets Singapore SMEs. SystemEarth's printed prototype request is firmer than the spoken guidance. Company sample access is now established locally; public-layer coverage and reuse terms, general scoring weights, and detailed submission logistics still need clarification.

The two original PDFs in [docs/sources](docs/sources/) are available for checking exact printed wording. The source manifest records their provenance. Use the current references for ordinary project work.

## Working with an agent

[AGENTS.md](AGENTS.md) contains the project overview, instructions for choosing the right references, source interpretation, and repository conventions. Its project context is sufficient to orient a new agent before it reads task-specific details.

When a track is confirmed, record its company, challenge, agreed scope, dataset access, and deliverable here. Add actual setup, run, and verification commands when the implementation introduces them.
