# Final mock SystemEarth judging review

**14 October 2026 — completed local demo slice.** Applied the `systemearth-hackathon-judge` skill as a simulated company-side reviewer. These weights and scores are a **mock rubric**, not published organizer criteria or a prediction of winning. This updates the earlier 13 October assessment after clean-export reproduction, independent JRC browser review and demo packaging. Optional unshipped features receive no credit. Scores assess evidence quality, not percentage of implementation complete.

## Verdict

**Ready for a scoped local demonstration. Proposal quality: 90/100. Demonstrated readiness: 87/100.**

The project delivers the printed prototype requirement: multiple native layers and years, a real plot query, compact encoding, original-layer comparisons, full pixel/mask preservation and measured storage/query/resource tradeoffs. The product makes that engineering evidence usable. It is not yet a company-approved compliance workflow or independently validated environmental decision system.

The strongest pitch is the combination of inspectable evidence and honest representation choices. The standard-format controls sometimes beat the custom format; the learned selector loses the strongest comparison. Showing those results improves the engineering argument. Hiding them would materially weaken it.

## Proposal quality

Scores use a 0–5 scale; points are weight × score / 5. Proposed future work is evaluated as a plan, not credited as an observed result.

| Criterion | Weight | Score | Points | Rationale, evidence and remaining gap | Confidence |
| --- | ---: | ---: | ---: | --- | --- |
| Challenge and encoding fit | 25 | 4.5 | 22.5 | Specific plot-evidence task; native multi-layer/year encoding and exact reference comparison. README, track brief and interface define the slice. Company-approved decision semantics remain open. | High |
| Correctness and decision/pixel fidelity | 25 | 4.5 | 22.5 | Explicit masks, unknowns, source versions, independent oracle, full raw preservation and adversarial receipts. Sound method; no external environmental truth or agreed legal rule set. | High |
| Measurement and resources | 15 | 4.5 | 13.5 | Complete accounting, repeated queries, CPU/RSS, standard controls, held-out selector study and clear cache limits. Production-scale/update workload remains undefined. | High |
| Customer workflow usefulness | 15 | 4.5 | 13.5 | Declaration-to-cell-to-receipt workflow matches the supplied company description; local questions and live exploration are coherent. Customer interviews and expected-result acceptance are outstanding. | Medium |
| UX and demo clarity | 10 | 4.5 | 9 | Linked views, readable receipts, keyboard alternatives, explicit failure states and a short demonstration narrative. RuleLens is a documented optional concept, not shipped work. | High |
| Feasibility and reproducibility | 10 | 4.5 | 9 | Explicit setup/verification, pinned inputs and bounded scope; clean-export reproduction recorded in completion-reproducibility.md. Cross-platform installation and final presentation logistics remain open. | High |
| **Total** | **100** | | **90** | | |

## Demonstrated readiness

| Criterion | Weight | Score | Points | Observed evidence and missing proof | Confidence |
| --- | ---: | ---: | ---: | --- | --- |
| Challenge and encoding fit | 25 | 4.5 | 22.5 | Running Python/React prototype; three Hansen bands, annual loss codes, 17 supplied polygons, separate JRC native baseline and a real local query service. Core scope is screening/evidence preservation, not a completed legal decision contract. | High |
| Correctness and decision/pixel fidelity | 25 | 4.5 | 22.5 | 17/17 exact source/compact dictionaries, full raw/mask checks, scalar oracle, native cell evidence, independent V1–V7 and J1/J2 closure. Geographical generalization and satellite accuracy are unproven. | High |
| Measurement and resources | 15 | 4 | 12 | Retained complete storage, hot and process-cold timings, encoding CPU/RSS, stronger standard controls and preserved losing candidates. One small AOI, uncontrolled OS cache and short repeated samples limit generalization. Research verifier hardening has its own bounded review status. | High |
| Customer workflow usefulness | 15 | 4 | 12 | Actual declarations, missing references, linked evidence index, local notes, proof and downloaded receipts. The customer has not validated the review workflow or supplied mitigation files/reference decisions. | Medium |
| UX and demo clarity | 10 | 4.5 | 9 | Actual live browser acceptance: 14 checks, exact P-0003, complete evidence, stale/cancel/recovery and 390px keyboard path. Independent JRC integrated review passes nine checks; a real silent walkthrough and current narration are retained. The mobile cell table requires horizontal scrolling. | High |
| Feasibility and reproducibility | 10 | 4.5 | 9 | Clean exports with new Python/npm environments pass both retained verifiers, full/indexed P-0003 queries and production build without full tiles. Portable QA supports alternate ports and isolated output. Same host only: cross-platform and full historical reacquisition remain unproven. | High |
| **Total** | **100** | | **87** | | |

Evidence: [engine report](engine-report.md), [stable experience handoff](experience-integration-status.md), [browser QA](browser-qa.md), [independent validator](validator-report.md), [JRC independent verification](validator-jrc-report.md), [strong/spatial verification](validator-strong-spatial-report.md), [current command record](completion-verification.json), [clean-export audit](completion-reproducibility.md), [independent integrated JRC review](completion-browser-report.md) and [detailed handover](../HANDOVER.md). The numerical scores are reviewer judgments, not statistical confidence measures.

## Must-have demonstration gate: PASS for the stated slice

| Required element | Evidence | Gate |
| --- | --- | --- |
| Specific use case | Supplier-declaration and mapped-evidence review on the supplied Surat Thani-labelled sample | Pass; provisional company semantics disclosed |
| Working multi-layer/year encoding and query | Three Hansen native bands, 2001–2025 loss codes, compact stores, CLI and live bounded geometry service | Pass |
| Representative plot query | P-0003 exact 87 selected cells; P-0005 annual evidence; all 17 batch comparisons | Pass |
| Original-layer output fidelity | Exact full result dictionaries and independent membership/reduction checks | Pass for declared screening outputs; not an agreed legal classifier |
| Relevant pixel fidelity | Full raw values, independent masks and metadata preserved, including off-plot corruption checks | Pass |
| Storage/query/resource measurements | Complete required storage, repeated hot/process-cold queries, encoding wall/CPU and child peak RSS | Pass with stated small-sample/cache limits |

The printed kickoff asks for a working prototype; the less-firm speech does not waive it. The current implementation satisfies that stronger request. A novel compression algorithm, ML model, near-real-time monitoring, cloud deployment and cost estimate are not prerequisites. Existing algorithms are allowed; infrastructure cost estimates are a bonus. WDPA and legal classification should not be invented to make an optional layer list look complete.

## Three skeptical company questions

1. **What exact decision are you preserving, and who approved the rule?** Answer with the declared center-selection/mask/period contract and its source comparison. State that company historical semantics and legal interpretation remain unresolved.
2. **Why use the custom representation when standard GeoTIFF is smaller in your stronger control?** Show complete storage and the workload-specific full-load/indexed/encoding resource tradeoffs. The method should choose the appropriate representation; custom novelty is not the objective.
3. **Can I reproduce an answer or failure without your machine and huge source downloads?** Show the minimal bundle, verifier and ordinary export, then a live unknown/outside case. Identify the Python/dependency setup and distinguish retained checks from reacquiring the original raw tiles.

## Smallest improvements, ordered by value

1. Obtain one company-reviewed plot and reproducible expected result, including source vintage, inclusion rule and mitigation evidence meaning. This changes confidence more than another UI panel.
2. Use the recorded walkthrough and updated narration to rehearse with the actual presenter; confirm submission deadline, channel and pitch length. Tracked repository publication is already authorized; no organizer submission has been sent.
3. After workload confirmation, evaluate another geography and the target deployment platform. The independent JRC pass and same-host clean-environment reproduction are complete. RuleLens remains optional; no need to expand scope to demonstrate the accepted slice.

No score establishes legal compliance, real-world source accuracy, public-release readiness or an official event outcome.
