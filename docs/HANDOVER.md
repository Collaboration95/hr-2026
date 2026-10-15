# Plotline — complete project handover

> **Current status (15 October 2026):** The UI redesign described below as the "next authorized task" is complete. It is merged to `Main` (PR #1); see [redesign decisions](writeups/05-redesign-decisions.md). Decision layers were then added on `guru/decision-layer`: a 6.1 KB decision layer, 99% smaller than the original layers, with identical answers proven for all 744,732 cells and registered plots re-checked 44× faster (65× with the numpy-free re-check; new plot boundaries 5.3× faster). Three speed-up phases on 15 October got there: Phase 1 faster decode, reduction and selection; Phase 2 co-design experiments (a scalar scan, a batch evaluator and a numpy-free re-check); Phase 3 two small wins (a faster shared histogram reducer and no `numpy.ma` import in the batch path). None changed any output. See the [decision-layer report](lab/decision-layer-report.md). Start from the [writeups](writeups/README.md). The material below is the historical 13–14 October handover.

**Completion checkpoint: 14 October 2026.** The user resumed work to finish the existing local prototype. The scientific/engine checkpoint below is preserved; this pass closes delivery and verification gaps without changing retained measurements or production query semantics.

- Clean tracked-file exports reproduced the retained Hansen and JRC proofs, both P-0003 query access paths and the frontend build with new dependencies and no full-tile caches. This was on the same machine, not a cross-platform test.
- `scripts/setup-local.sh` and `scripts/verify-local.sh` provide explicit setup and retained-proof/build commands.
- The second independent integrated JRC browser review passed nine focused checks. A lead replay uses the portable `npm run qa:jrc --prefix app` command. The horizontally scrolling mobile native-cell table remains a documented non-blocking usability suggestion.
- Frozen browser suites and the 14-check actual-service live suite pass on a configured alternate port. New runs preserve historical evidence and write into a unique ignored cache directory.
- A [25-second silent walkthrough](lab/completion-demo.webm), [chapter metadata](lab/completion-demo.json), and [updated narration](lab/demo-script.md) provide a fallback demonstration. A recording command reproduces the journey against the actual app and live service.
- [Completion verification](lab/completion-verification.json), [reproduction report](lab/completion-reproducibility.md), and [independent JRC review](lab/completion-browser-report.md) are the current evidence. The 13 October final-verification file remains historical.

The agreed local software/demo slice is complete. Company-approved source/rule semantics, mitigation evidence, a representative production workload, team presenter and final organizer logistics remain external handoffs. No submission, company message, cloud deployment or legal approval is implied.

**Next authorized task:** The user requested a complete UI redesign by Claude. [HANDOFF.md](../HANDOFF.md) is the current redesign brief; the verified implementation below is its baseline. Astra prepared the handoff without changing the UI.

## 1. What exists now

Plotline is a working local geospatial evidence-review product for SystemEarth's Hack & Hire challenge. It connects supplier declarations to mapped observations and makes the original-versus-compact computation inspectable. The implementation is Python 3.14 plus React/TypeScript/Vite.

The **Review desk** links a plot queue, exact supplied geometry, native source cells, annual observations, supplier declaration steps, missing evidence references, and local analyst notes. **Evidence index** displays the actual 17-plot × 25-year cohort and opens a selected observation in context. **Encoding proof** exposes the retained experiment, complete storage accounting, timings and receipts. **Query lab** performs new bounded requests for an exact supplied polygon or temporary rectangle using a read-only local backend.

A separate **JRC 2020 baseline disclosure** is mounted below Hansen review. It has its own source version, native grid, class counts, support, proof and receipt. It never silently becomes another Hansen band or a combined deforestation verdict.

The optional **RuleLens** educational UI was deliberately deferred at wrap-up. No component code was written or mounted. The completed spatial-rule study and its 15 witness cells are retained for a future implementation.

Start with these documents:

| Need | Read |
| --- | --- |
| Agent-swarm research method and retrospective | [Research methodology](lab/research-methodology.md) |
| Current run instructions and context | [README](../README.md), [app instructions](../app/README.md), [engine instructions](../engine/README.md) |
| Stable app status, servers, checks and gaps | [experience integration handoff](lab/experience-integration-status.md) |
| Final engine state and minimal bundles | [engine report](lab/engine-report.md), [engine final checkpoint](lab/engine-checkpoint.md) |
| Computational semantics | [frozen interface](lab/interface-v1.md), [live interface](lab/engine-live-interface-v1.md), [JRC interface](lab/engine-jrc-interface.md) |
| Independent evidence | [main validator](lab/validator-report.md), [JRC validator](lab/validator-jrc-report.md), [strong/spatial validator](lab/validator-strong-spatial-report.md) |
| Demo rehearsal | [demo script](lab/demo-script.md) |
| Next company conversation | [concrete discussion brief](lab/company-next-conversation.md) |
| Final assessment | [mock judge review](lab/final-judge-review.md) |

## 2. Run it and verify it

For a new checkout with Python 3.14 and Node/npm installed, run `scripts/setup-local.sh`, then `scripts/verify-local.sh`. The completion review used **http://127.0.0.1:5183/** with its API on **http://127.0.0.1:8766/**. Earlier port/PID records are historical; inspect current process ownership before stopping anything.

On free ports, launch both services from the repository root:

```sh
npm run dev:local --prefix app
```

The launcher checks prerequisites and occupied ports, starts the API, waits for verified health, copies local exports and starts Vite. Ctrl-C terminates only its own children. It does not install dependencies, publish data or kill an existing server. For a second isolated instance:

```sh
PLOTLINE_WEB_PORT=5183 PLOTLINE_LIVE_PORT=8766 npm run dev:local --prefix app
```

For frozen review without the optional API:

```sh
npm run dev --prefix app -- --port 5173 --strictPort
```

The Query lab then shows an explicit unavailable state until its backend is available; frozen review continues to work. A live snapshot stays immutable until API restart. Reconnect after restart. Editing a temporary region invalidates the previous answer; cancellation and request identity checks prevent late responses from replacing a newer answer.

Useful verification commands, from the repository root:

```sh
.venv-data/bin/python -B -m engine.verify
.venv-data/bin/python -B -m engine.jrc --verify artifacts/jrc-baseline-v1.json
.venv-data/bin/python -B -m unittest discover -s engine/tests -q
npm test --prefix app
npm run build --prefix app
npm run qa:browser --prefix app
npm run qa:live --prefix app
npm run qa:jrc --prefix app
```

The live browser suite requires actual healthy API responses; missing health exits with an explicit blocked result, not a successful skip. Browser setup is a separate, explicit command: `npm run qa:install-browser --prefix app`. Tests use app-local Playwright and its ignored project cache. They do not download browsers during a test run.

For a new machine, install Python **3.14** (required for standard-library Zstd), create `.venv-data`, install `engine/requirements.txt`, and run `npm ci --prefix app`. Verified versions are Python 3.14.7, NumPy 2.5.4, Rasterio 1.5.2, Shapely 2.1.2, Node 26.3.1 and npm 11.16.0. The lockfile pins the actual frontend dependency tree. Full raw source tiles are unnecessary for ordinary retained queries, exports and proof verification.

Do not run a fresh benchmark merely to launch or export the app. Ordinary export uses deliberately retained evidence. Code/input changes can correctly invalidate that evidence; a new measurement and an explicit retained selection are then separate engineering actions.

## 3. The actual customer sample

The company supplied **17 CSV records and 17 polygons**, joined one-to-one with exact original strings and geometry. The records label the location **Surat Thani / Chai Buri, Thailand**, around 98.77–99.08°E and 8.43–8.58°N. This is not the teammate's proposed Songkhla cohort. The correct public Hansen tile is `10N_090E`, not `10N_100E`.

Five records—P-0003, P-0005, P-0008, P-0010 and P-0013—declare an indication, mitigation with evidence, and final deforestation-free/compliant status. They are **declaration-backed review leads**, not proven violations. Their referenced mitigation files were not supplied. P-0003 contains the opaque key `hyperlink-RG1-P-0002`; its meaning remains unresolved.

The supplied analysis interval is 2021–2023. The latest acquired Hansen release is 2025 v1.13. Release identity, observation year, supplier processing date and harvest date are different concepts. The sample's processing/harvest chronology requires company interpretation. Do not silently repair it or infer misconduct.

Original files and the initial message/image context were saved and committed before lab implementation. The [sample audit](research/company-sample-audit.md) and [recovered conversation context](research/prior-thread-context.md) explain provenance and earlier decisions.

## 4. Computation and trust boundaries

Hansen uses three aligned native bands: `treecover2000`, `lossyear`, `datamask`. The sample grid has **604 × 1233 = 744,732 spatial cells**, or 2,234,196 raw band values, with independent band-validity masks. No resampling or silent geometry repair is used.

The accepted query `hansen-centers.v1` selects native cell centers covered by the polygon, including boundary centers. Coordinates come from the original global chip lattice. Reassociating floating-point arithmetic through a shifted window origin caused a real one-ULP membership error during research; the indexed path now selects on the original lattice first.

Analytical events require supported valid land. A witnessed loss remains true with partial support. An absent event becomes false only with complete known selected support and valid land; otherwise it remains unknown. Zero selected centers, outside coverage, missing bands, masked pixels and water-only support must never turn into a reassuring zero/false result.

Source/compact equality covers full result dictionaries, raw values, masks, metadata, native evidence and receipts—not just the displayed loss count. The independent scalar oracle provides another membership/reduction implementation, while its shared GEOS topology dependency is disclosed. A passing local hash identifies integrity; it is not a signature or proof of satellite accuracy.

The live service binds only IPv4 loopback. Requests cannot choose arbitrary paths or modify supplier records. Limits include 65,536 request bytes, 512 positions and 4,096 candidate/selected cells; oversized work is rejected rather than truncated. Complete selected-cell evidence, exact request-body hashes, geometry association, snapshot identity, and canonical result/evidence/receipt bytes are validated. Per-request timings are explicitly not benchmarks.

JRC v4 has a **different 1809 × 3695 native grid**. Valid class 0 means Non-forest, class 1 means Forest. A transparent class-0 map style is not a nodata mask. Reference year 2020 differs from release/version dates; the pinned official metadata contains an older date/report-link inconsistency that is preserved. Do not add or compare JRC and Hansen cell counts as common area, and do not reconstruct forest-2020 from Hansen canopy-2000 minus losses.

## 5. Measured decisions

| Result | Meaning and decision |
| --- | --- |
| All 17 accepted Hansen queries match source and compact; full values/masks are preserved | Computational fidelity for pinned inputs and declared rules. It does not establish real-world or legal accuracy. |
| Retained custom store: 535,012 B; necessary supplied source inputs: 585,293 B | 8.59% reduction at that stated loader-input boundary. With identical common review inputs, 604,558 → 562,571 B is 6.95%. |
| Retained hot 17-query medians: source 1.418 ms, compact 1.446 ms | No meaningful hot-query speedup is established. |
| Retained fresh-process full load + 17 queries: 11.182 ms → 5.800 ms | A bounded full-load benefit. Imports/common geometry loading are excluded; OS cache is uncontrolled, not disk-cold. |
| Strong standard Hansen control: 532,444 B | 2,568 B / 0.48% smaller than custom. It has faster indexed medians, while custom full loading and encoding cost fare better. Separate study and verifier status apply. |
| JRC custom: 21,459 B; standard control: 19,901 B | Standard is 7.26% smaller at complete accounting. Custom loads faster and uses less peak memory in that separate experiment. No new production codec was selected. |
| Adaptive held-out policy: 811,164 B vs fixed custom 810,764 B and fixed standard 806,058 B | Reject ML selector integration. A losing learned approach is retained evidence, not hidden. |

Never splice the fastest columns from different runs into an invented composite benchmark. Include metadata/index/mask overhead. Source chips and compact stores cover identical support; whole-tile download versus crop size is not a compression saving. Seven-repeat p95 is a small-sample statistic, not a population confidence guarantee. Hardware/cache/library versions and raw samples are in the detailed reports.

The historical custom/strong-control studies remain distinct from the accepted frozen experiment. The strongest-standard comparison is visible in the UI. The revised Hansen control verifier passed its fresh positive and all six original independent forgery reproducers in the master’s final replay. The JRC standard-format study remains research, with no production adapter or promoted research proof gate.

## 6. Research outcomes worth preserving

**Spatial inclusion matters.** On the same 17 polygons, positive-area footprint overlap adds 337 plot/cell memberships and changes five period flags compared with center inclusion. Both rules preserve 17/17 original/compact agreement. All 15 changed-flag witness cells were independently reproduced. P-0003 gains a 2025 witness under overlap although its center is outside and only about 0.7429% of that cell's angular footprint intersects the parcel. This is an intentional rule difference, not an encoding error. It does not explain any of the five supplied 2021–2023 indications. Production remains center-based.

**The tested vintage does not explain the historical declarations.** Luna preregistered official Hansen 2023 v1.11 before inspecting values, downloaded all three historical bands and compared only the shared 2021–2023 period. All 17 period/annual counts and flags remain unchanged. The 47 selected-cell raw changes are later-year 0→24/25 additions. Unsupported future periods are omitted from historical outputs. The company’s actual release remains unknown. Read [vintage report](lab/engine-vintage-report.md), including its cache-restoration limitation.

**The learned selector lost the useful comparison.** The source-only study separated training, validation and sealed spatial holdout, retained model/feature overhead and checked all codec roundtrips. Its final joint policy lost to a fixed option; optimized standard storage also challenged custom formats. Keep the experiment for a pitch about decision quality, not as an ML success claim.

**Negative controls improved the product.** Independent review found forged measurement acceptance, off-plot corruption hidden by plot-only agreement, receipt inconsistencies, null-as-zero UI, a redundant baseline file, false equality rendering, intermediate timed-answer acceptance and an export that unnecessarily depended on a full source cache. Accepted Hansen V1–V7 and JRC J1/J2 have documented positive and negative verification. The six reproduced strong-control proof gates also close in the master’s final replay. No claim is made that all possible adversarial inputs are covered.

## 7. Validation evidence and what is still missing

The stable experience handoff records production build/typecheck success, **112 live-client checks**, **14 actual live browser checks**, **76 JRC loader checks**, **12 synthetic JRC display cases**, and real desktop/mobile JRC integration. Earlier frozen browser suites cover the queue, proof, notes, cohort index and receipts. Do not sum overlapping historical runs into a fabricated unique-test count. The final master run passed 198 engine tests, 298 frontend checks, the production build, both retained verifiers and the six strong-control negatives. Exact commands and artifact hashes are in [final-verification.json](lab/final-verification.json).

Actual live browser checks use unaugmented service responses. They include exact P-0003 reproduction, edited bounds, tiny/no-center, outside, partial, oversized, cancellation, delayed older responses, unavailable/retry, complete cells, receipt bytes and a 390px keyboard journey. At the 13 October checkpoint a second independent pass was deferred. The 14 October independent JRC review now closes that gap; its nine checks and limitations are recorded separately, not added to historical totals.

Missing external proof includes company-approved query semantics, historical evidence files, independent environmental ground truth, a representative production workload, broad geographic scaling and user studies. WDPA is not included; its use remains conditional on applicable terms. No legal decision engine, cloud deployment, public release, monitoring daemon or notification integration was built.

## 8. Repository and data map

| Path | Purpose |
| --- | --- |
| `engine/` | Native queries, safe codecs, oracle, proofs, benchmarks, optional live service and package inventories |
| `app/src/` | Review workflow, evidence index, receipts, live client/view and separate JRC consumer |
| `artifacts/demo-v1.json`, `benchmark-v1.json` | Canonical frozen Hansen export and deliberately retained measurement |
| `artifacts/jrc-baseline-v1.json` | Separately verified JRC companion |
| `artifacts/*bundle-manifest.json` | Exact minimal retained reproduction inventories; overlapping files are not additive storage metrics |
| `data/public/` | Pinned current source chips and acquisition provenance |
| `data/experimental/selector/` | Source-only learned selector, splits, measurements and retained packages |
| `data/experimental/spatial-sensitivity/` | Rule comparison, analytic fixtures, full results and witnesses |
| `data/experimental/hansen-vintage/` | Preregistered historical acquisition, chips, comparison and scalar checks |
| `data/experimental/jrc-standard/` | Separate standard-format JRC study |
| `validation/` | Independent reproducers and verification scripts |
| `docs/lab/` | Lead/worker reports, contracts, scientific reviews, QA evidence and demo narrative |

Full source tiles and disposable validation/measurement caches stay local and ignored. Small native chips, provenance, code, measured records and selected packages are retained. Some research commands need the raw cache to repeat original-download verification; normal product execution does not. Do not delete original files or overwrite a retained experiment to make a test pass.

Branch: **`guru/plotline-research-lab`**. Initial data/context and planning were committed before the lab. `7cecd05` preserves the first verified prototype; `20cd47c` preserves adaptive research and the live direction. The final checkpoint commit is recorded in the final response and Git log. At the initial checkpoint no push or PR had been requested. The user subsequently authorized pushing all tracked project work and documentation to the existing public repository on this branch. All GitHub access uses authenticated `gh` exclusively.

## 9. Next work, in priority order

1. **One company review, one plot, one receipt.** Use P-0003 and ask for the exact historical source version/rule, mitigation reference meaning, and expected reviewer action. Request a reproducible expected-result case. The two bounded rule/vintage studies do not explain the supplied indications; do not invent an explanation.
2. **Agree on the workload and output contract.** Interactive arbitrary regions, fixed-cohort batches and layer updates imply different representation choices. Select the format based on measured needs rather than protecting the custom codec or adding ML for its own sake.
3. **Rehearse a narrow demonstration.** Show declaration → native evidence → original/compact proof → live temporary region → explicit unknown state. Include a losing candidate and the stronger standard baseline. Confirm sample-use permission and exact submission/pitch logistics before external presentation/publication.
4. **Finish optional polish only if it supports that story.** RuleLens has a vetted 22.8 KB witness projection and a design handoff, but no implemented component. Keep it educational and separate from production query semantics. The second independent JRC browser review is now complete; its mobile table suggestion is optional.
5. **Scale after the company clarifies the workload.** Add independent geographical cohorts, update/vintage handling and representative performance tests. Avoid an opaque risk score, supplier-label training, unsupported hectares or global performance extrapolation.

## 10. Restart instructions for another agent

Read AGENTS.md, README and this handover first, then the relevant source references and latest lead/validator report. The 14 October instruction resumed and completed the existing software/demo slice after the early checkpoint. Do not treat the unused portion of the earlier four-hour lab as authorization for an open-ended new research program. Ask only if a genuinely new decision blocks a newly requested task.

Treat original company inputs, current source chips and retained experiments as immutable. Use `guru/` branches and project commit conventions. Keep new write scopes disjoint if delegation is newly requested. Prefer `rg`; use `gh` for all GitHub access. Browser work must use T3 preview first, with documented unsupported/unavailable failures before switching systems.

A new agent should verify the current retained state before editing, keep source uncertainty distinct from encoding errors, and update the accepted artifact only through its explicit export/measurement lifecycle. The follow-up user instruction authorizes publication of this tracked repository checkpoint; deployment, unrelated uploads and messages to people are separate actions.
