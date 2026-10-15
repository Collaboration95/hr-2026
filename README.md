# Hack & Hire — Sustainability Edition 2026

A week-long project for Hack & Hire, organized by Projet with NUS CAT. Participants work on a real company challenge, build something useful, and present directly to company teams. The build period is **10–17 October 2026**, with finals on **17 October**. Participation is solo or in a team of two or three.

This repository holds the project context and working local implementation for the selected SystemEarth track. The aim is a practical, demonstrable outcome with clear reasoning and evidence.

## Plotline in one minute

**Plotline keeps the decision, not the data.** It reduces multi-layer, multi-year forest maps to the facts an EUDR screen reads, and proves that every plot gets the same answer as from the original layers.

- **Same answers:** 744,732 of 744,732 map cells identical to the original Hansen + JRC layers, so every plot boundary in the region gets identical outputs under the written rule. The 17 supplied plots are 17/17.
- **Smaller:** a 6.1 KB decision layer replaces 623 KB of original layers (99% smaller). On a whole 10° tile, 422 MB becomes 8.2 MB.
- **Faster:** registered plots are re-checked 24× faster (420× from a stored answer table), and new plot boundaries 2.2× faster.

**Watch** the [55-second walkthrough](docs/lab/redesign-demo.webm) → **Inspect** the evidence in the app (`npm run dev:local --prefix app`, then `#/proof`) or the [decision-layer report](docs/lab/decision-layer-report.md) → **Reproduce** with `scripts/setup-local.sh` and the commands in that report.

More: [plain-English writeups](docs/writeups/README.md) · [pitch and demo script](docs/writeups/04-pitch.md) · [design system](design/DESIGN.md) · [detailed handover](docs/HANDOVER.md)

## Current status

- **Selected track:** SystemEarth — Multi-Layer, Multi-Year Geospatial Data, selected on 10 October 2026. See [track brief](SystemEarth-track.md) for constraints, evaluation, and proposed scope.
- **Team and allocation:** User reports acceptance into the SystemEarth track on 11 October 2026; team composition not recorded.
- **Recommended product:** **Plotline**, an evidence-review workflow for supplier declarations and mapped observations, backed by a compact encoding and measured original-versus-compact query/fidelity proof. See [product direction](docs/planning/systemearth-product-direction.md). The authorized local lab implements this direction in Python 3.14 and React/TypeScript/Vite; final team presentation scope remains open.
- **Company sample acquired locally:** The [audit](docs/research/company-sample-audit.md) confirms 17 CSV records and 17 GeoJSON polygons matched one-to-one, with no duplicate or unmatched IDs. The CSV labels them Surat Thani, Chai Buri, Thailand; bounds are **98.772429–99.080292° E, 8.431179–8.581888° N**. Recommend starting with this sample. Songkhla/rubber remains a teammate proposal, not a final team decision or the supplied sample's location.
- **Review leads:** Five sample rows declare a deforestation indication, mitigation with evidence, and a final deforestation-free/compliant status. These are declaration-backed review leads; the sample does not independently verify the mapped signal, mitigation evidence, or legal outcome.
- **Public layers acquired:** Hansen GFC 2025 v1.13 `treecover2000`, `lossyear`, and `datamask` from `10N_090E`. The three native-grid chips total **576,999 bytes**, share a **1233 × 604** grid, cover the full 17-plot bounding box with outward-aligned bounds, and match their source windows pixel-for-pixel on readback. Full source tiles total 224,170,336 bytes in the ignored raw cache. See the [Hansen acquisition report](docs/research/layer-acquisition.md). A separately versioned **JRC forest-2020 v4** chip is now acquired experimentally; its v3 predecessor remains unavailable. See [JRC candidate and provenance](docs/lab/engine-data-W4.md). The separate JRC native-grid companion is verified and mounted; it is not included in the retained Hansen measurements. WDPA use remains conditional on its terms. The [October 11 catalog](docs/systemearth-open-data-options.md) remains historical research.
- **Implementation:** A working local prototype now combines a Python 3.14 geospatial engine with a React/TypeScript/Vite evidence workspace. Original and compact queries agree across the 17 supplied plots; an independent scalar oracle and separate synthetic cases test the declared computational rules. The lab is checkpointed with live local queries, independent proof checks, measured representation controls and a detailed handover. These are encoding/query results, not independently verified supplier compliance. See [engine report](docs/lab/engine-report.md) and [experience report](docs/lab/experience-report.md).
- **Completed local slice (14 October):** The existing SystemEarth prototype is verified from tracked files with new dependencies, the integrated JRC experience is independently checked, and a recorded walkthrough plus current demo narration are packaged. The user authorized this completion pass after the earlier stop. Company-approved rules, missing mitigation files, a production workload, and submission logistics remain external decisions. Optional RuleLens is outside this completed slice; its research remains available.
- **UI redesign (15 October):** Plotline was rebuilt as a map-first evidence workspace on `guru/plotline-ui-redesign`. The map draws the pinned Hansen and JRC rasters losslessly in the browser, with a 2001–2025 year scrubber, stacked layers and native cells. Supplier declarations sit beside the mapped observations, and every difference is posed as a review question. The views are Cohort (loss barcode + declared-vs-mapped matrix), Proof (export-derived fidelity, storage and timing) and Live query. The design system in [`design/`](design/DESIGN.md) is meant to be reused for slides, videos and HTML writeups. Engine, artifacts and validation boundaries are unchanged. See [redesign decisions](docs/writeups/05-redesign-decisions.md).
- **Decision layers (15 October):** Layer analysis grounded in the EUDR cut-off definitions; derived screening (38.5 KB) and decision (6.1 KB) layers with an exhaustive 744,732-cell proof, fuzzing, a registered-plot index and answer table, whole-tile scale and cost estimates, and an independent validation whose fixes were applied. The lossless v1 store remains the audit tier. See the [decision-layer report](docs/lab/decision-layer-report.md).
- **Planning window:** Use 13–16 October for the first complete slice, batch comparison, and demo preparation; conservatively aim to be ready on 16 October. See [track work sequence](SystemEarth-track.md#proposed-work-sequence).
- **Deadline clarification:** The challenge-page screenshot provided on 11 October shows an end time of 17 October at 00:00 SGT. Confirm whether this is the application closing time or project submission deadline; finals remain recorded as 17 October.

Update this section when a decision is made so subsequent work starts from the current project state.

## Running the local lab

The user authorized implementation and original UI/UX design on 13 October, superseding the earlier planning-only/Claude-only limits. The lab began at 09:52 SGT and was wrapped early at the user’s request around 12:28 SGT; [master log](docs/lab/master-log.md) records the actual agent dispatch and milestones. Prototype code is in `engine/` and `app/`; canonical computed exports and measured experiment records are in `artifacts/`.

For a new checkout, install Python 3.14 and Node/npm, then run `scripts/setup-local.sh` and `scripts/verify-local.sh`. The setup installs dependencies explicitly; verification checks the retained proofs and builds the app without rebenchmarking. The clean-export audit used a new environment on this machine, with no full-tile caches.

With dependencies ready, reproduce a query and start both the app and live API:

```sh
.venv-data/bin/python -m engine --plot P-0003
npm run dev:local --prefix app
```

The app is local at `http://127.0.0.1:5173/`. Deep links: `#/map`, `#/map/P-0001/2022`, `#/cohort`, `#/proof/P-0005/2025`, `#/live`. Map, Cohort and Proof use a frozen computed export; changing the year does not run a new query. Live query runs fresh temporary-geometry queries against an identified, immutable local snapshot when the optional service is available. To start both the API and app on free local ports, use `npm run dev:local --prefix app`; see [live run instructions](docs/lab/experience-live-run.md). [Engine instructions](engine/README.md) describe source/compact queries, benchmark generation and exports; the [versioned interface](docs/lab/interface-v1.md) defines unknown states and exact computational semantics. The [independent validator](docs/lab/validator-report.md) records concrete findings and their verification status. The [final mock judging review](docs/lab/final-judge-review.md) assesses the implemented checkpoint; the original planning score remains historical.

Useful checks:

```sh
.venv-data/bin/python -B -m unittest discover -s engine/tests -v
npm test --prefix app
npm run build --prefix app
```

The standard-library source audit remains `python3 scripts/inspect_company_sample.py`. Immutable supplied files and public source chips are preserved; experimental stores, hashes, and measurements are not legal or environmental ground truth.

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
| [Claude UI redesign handoff](HANDOFF.md) | Current complete-redesign brief, code map, data contracts and acceptance checks. The earlier planning brief is historical. |
| [Public-layer acquisition report](docs/research/layer-acquisition.md) | Final three-band Hansen acquisition evidence and missing/conditional layers. |
| [Hackathon judge review](docs/planning/hackathon-judge-review.md) | Mock project evaluation; not an official judging rubric. |

Some instructions need confirmation. Bizsu's printed lead-generation brief targets homeowners, while the spoken brief targets Singapore SMEs. SystemEarth's printed prototype request is firmer than the spoken guidance. Company sample access is now established locally; public-layer coverage and reuse terms, general scoring weights, and detailed submission logistics still need clarification.

The two original PDFs in [docs/sources](docs/sources/) are available for checking exact printed wording. The source manifest records their provenance. Use the current references for ordinary project work.

## Repository publication

After the local checkpoint, the user explicitly authorized pushing the tracked project, research evidence and documentation to the existing public GitHub repository on `guru/plotline-research-lab`. Raw acquisition caches, dependencies and disposable test bundles retain their existing exclusions. This records the user’s repository publication instruction; it does not invent additional company data-use terms or alter the sources’ licenses.

## Working with an agent

[AGENTS.md](AGENTS.md) contains the project overview, instructions for choosing the right references, source interpretation, and repository conventions. Its project context is sufficient to orient a new agent before it reads task-specific details.

When a track is confirmed, record its company, challenge, agreed scope, dataset access, and deliverable here. Add actual setup, run, and verification commands when the implementation introduces them.
