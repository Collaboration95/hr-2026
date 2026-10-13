# Plotline research lab — 13 October 2026

Authorized session: 01:52:58–05:52:58 UTC (09:52:58–13:52:58 Singapore).

The user now authorizes implementation, original UI/UX design, experiments, useful dataset downloads, local tooling, and hierarchical agent delegation within this repository. This supersedes earlier planning-only/Claude-only design constraints. No external publication or messages to other people are part of this run.

## Organization and ownership

- Master Astra: scope, initial interface boundaries, integration, repository checkpoints, final verification and judging. Review lead reports; do not micromanage workers before leads report.
- Engine lead Astra (medium): `engine/`, `artifacts/`, `docs/lab/engine-*`, `docs/lab/interface-v1.md`, engine-specific tests/dependencies and new data under `data/experimental/`. Own reproducible source/compact queries, codec experiments, independent correctness checks, fair benchmarks and demo exports. Preserve existing source data.
- Experience lead Astra (medium): `app/`, `docs/lab/experience-*`, `docs/lab/product-research.md`, `docs/lab/demo-script.md`, `docs/lab/browser-*`. Own visual/interaction design, working frontend, inspiration research, product testing and browser evidence. Read engine outputs; copy them into app assets as needed without editing canonical artifacts.
- Each lead manages 3–4 Sol workers with disjoint writes, subject to available concurrency. Luna may handle bounded research/data/computer-use work. Leads must close completed children before replacement. Model speed controls are not exposed by the spawning API; do not claim to have changed them.

All GitHub access uses authenticated `gh`; local Git uses `git`. Workers do not stage, commit, switch branches or push. Master checkpoints reviewed changes. Avoid modifying outside this repository; use project-local environments. Parent session ID for lead reports: `01a130e9-aaf5-7a53-9cff-96d579f69b35`.

## Outcome and research loop

Deliver a runnable, distinctive evidence-review product backed by real geospatial computation and measured representation tradeoffs. Begin with the verified local Hansen three-band chips and 17 supplied plots. Expand only after a correct end-to-end slice works.

Use repeated hypothesis → bounded experiment → independent checks → measured decision → integration. Maintain experiment IDs, source/contract versions, commands, measured results, failures and reasons for retaining/rejecting candidates. Research should produce working artifacts and falsifiable results. Do not invent an ML objective or train on 17 supplier declarations as ground-truth compliance labels. Data-driven codec selection, query optimization and synthetic stress generation are sensible optional investigations if they improve measured behavior.

Required core: original and compact query paths, source pixel round-trip evidence, 17-plot fidelity, explicit unknown states, compressed-original baseline of identical support, index/metadata/preprocessing/resource accounting, a live review workflow, inspectable evidence receipts, usable keyboard/error states, and reproduction commands. Include exploratory results even when a candidate loses. Separate synthetic fixtures and real observations.

## Interface boundary

The engine lead owns a versioned JSON demo contract in `docs/lab/interface-v1.md`, publishing an initial usable form early and coordinating directly with the experience lead. Canonical outputs live in `artifacts/`; the frontend reads/copies them into `app/public/data/`. Prefer static reproducible exports for the first working integration; add a local query API only if useful and tested.

Minimum semantics: dataset/source metadata and hashes; actual plot geometries and exact supplier declarations; source and compact query results; tri-state mapped-loss signals and explicit unknown reasons; per-year observed-cell counts; source/compact agreement; measured benchmark information with units and method; receipt/provenance. Include map-ready native-grid evidence or small loss overlays for actual plot inspection. Never fabricate measures to unblock design. Uncomputed fields stay unavailable.

Product references are starting hypotheses, not a prohibition on better designs. Preserve factual semantics: supplier declarations are not independent findings; canopy2000 is not forest2020; source loss is not legal deforestation; source uncertainty differs from encoding error. Design can be ambitious while keeping those distinctions obvious.

## Cadence

Leads should operate autonomously and send substantive progress/milestone reports to the master approximately every 20–30 minutes, with changed paths, runnable commands, evidence, risks and next experiments. Report blockers sooner. Aim first integration within the first hour, iterative improvement in the middle two hours, and final QA/judging/documentation in the last hour. Do not stop at a planning report. Do not launch work likely to outlive the session without a controlled checkpoint.

Browser work uses T3 preview tools first (`preview_status`, then `preview_open` if necessary). Use official current sources for product inspiration and technical research. A live website is not a reusable data license. Do not upload the customer sample to third-party services.
