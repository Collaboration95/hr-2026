# Engine lab report — accepted Hansen slice and additive research

**Current:** a working, independently checked Python query/codec/export subsystem and the17-plot demo are accepted at master checkpoint7cecd05. All V1–V7 findings from the xhigh validator are resolved in its focused follow-up. The accepted Hansen benchmark/store remains immutable. JRC2020v4 and stronger-format/adaptive research are separate pending review.

Detailed chronological milestones are preserved in [engine-milestones.md](engine-milestones.md). This report leads with the currently accepted evidence.

## Accepted result and interpretation

- Three verified Hansen2025v1.13 bands share a604×1233native EPSG4326grid. All744732cells,2234196rawbandvalues and2234196validitybits round-trip exactly. All17complete query dictionaries match original and compact paths.
- Query contract `hansen-centers.v1` selects cells whose centers are covered by the exact plot geometry, including exterior/hole boundaries. Native grid, raw values and masks are retained; no resampling.
- Histograms include canopy0–100 and lossyear0–25. Code0loss remains distinct from annualevents. Periods2021–23 and2024–25 are separate from supplier historical source/version/date claims.
- Partial support retains observed counts and witnessed positive loss; absence remains unknown. False requires complete known selected support and valid land. Tiny/no-center, water-only/no-valid-land and missing-band cases never become a clear result.
- Exact supplier strings/geometries remain untouched. Five supplier-declared indication/mitigation/final-status rows are review leads, not proven violations or independent compliance findings. Current mapped loss is present on3plots for2021–23 and5plots for2024–25. These are different concepts.

Accepted representation: **separate-band Zstandard19,1024-cell chunks**,535012bytes including531847payload and3165metadata/index. Packed14 was implemented and rejected on measured storage; fewer raw bits did not yield a smaller compressed store.

| Storage scope | Original bytes | Encoded bytes | Reduction |
|---|---:|---:|---:|
| Actual query-loader requirements |585293|535012|8.59%|
| Conservative store versus original TIFF payload; encoded metadata included |576999|535012|7.28%|
| Symmetric review inputs; both retain acquisition provenance and supplier/geometry files |604558|562571|6.95%|

The symmetric6.95%view is a conservative presentation figure. Each view covers the same full AOI; none counts224MBfull-tile-to-chip cropping as a codec saving. The original loader needs576999TIFFbytes plus8294acquisition-provenance bytes. An unused948-byte generated metadata file is separately classified as research overhead, excluded from denominators. UI assets, common runtime dependencies and network acquisition are outside these data-storage scopes.

These results establish preservation under a declared query, not satellite accuracy, legal deforestation, a2020forest baseline, or supplier compliance. A new optimized GeoTIFF control may narrow/reverse the custom-store advantage; its additive review is described below. “Winner” means minimum total bytes among the accepted experiment's tested candidates, not a universal optimum.

## Retained identity and proof gates

- Experiment: `exp-0109a8d6c4782217871315b92c63a971d11ebd164585c80981f24c55b4f68fea`.
- Run: `run-71a5b90b05bdce363044d8e232ae33d20b31f3868a6f5ba50bf61372b98194a9`.
- Store: `artifacts/stores/exp-0109a8d6c4782217871315b92c63a971d11ebd164585c80981f24c55b4f68fea/separate_zstd_l19`.
- Canonical export: `artifacts/demo-v1.json`; representative P-0003: `artifacts/example-v1.json`.
- Frozen measurement/decision: `artifacts/benchmark-v1.json` and `artifacts/experiments/retained-choice.json`.
- Interface: [interface-v1.md](interface-v1.md).

Export and verification bind current input/query/implementation hashes, exact measured files and byte accounting, immutable registered run/identity, explicit retained choice and its archived selection, and the chosen store. They recompute full raw-array/mask equality, every plot result, native map evidence, receipt contract/source fields and derived summaries. Self-rehashed false proofs are rejected. Hashes support integrity/reproducibility, not authentication.

The independent validator accepted fresh retained and metric-free positive controls, rejected12specific forgeries, independently decoded level3/9/19retained stores, and confirmed canonical/retained/served content agreement. Its membership/reduction and codec decoding do not call production helpers. See [validator-report.md](validator-report.md) and `validation/verify_fixes.py`. Its scope is the tested current cohort and bounded adverse cases, not exhaustive arbitrary-input or source-accuracy certification.

## Runnable commands and evidence

```sh
.venv-data/bin/python -B -m engine.export
.venv-data/bin/python -B -m engine.verify
.venv-data/bin/python -B -m engine --plot P-0003
.venv-data/bin/python -B -m engine --plot P-0003 --access indexed
.venv-data/bin/python -B -m unittest discover -s engine/tests -v
.venv-data/bin/python -B -m engine.package
```

Python3.14.7/rasterio1.5.2/numpy2.5.4/shapely2.1.2; dependencies in engine/requirements.txt. `engine.export --without-benchmark` explicitly omits metrics during experiments; without a store its compact results stay pending. Errors are structured and never converted into false/no-loss. `engine.synthetic` emits six separate unknown-state fixtures, excluded from real-cohort metrics.

The integrated suite passed102methods before two additional CLI checks, which also passed. W2 contributes45oracle/adversarial methods,360seeded differential cases and144exhaustive mask/class/event cases. Source membership/reduction uses GEOS vector predicates; W2 uses scalar ray casting with exact-fraction orientation fallback. GEOS topology validation is shared and documented. The separate xhigh validator added196bounded adversarial checks. These counts are tests, not additional real plots.

The minimal accepted-Hansen bundle is listed in `artifacts/retained-bundle-manifest.json` (about4.28MB/50files at the working checkpoint). It includes required sources/cohort, engine code/tests, canonical artifacts, retained run/identity/selection and all candidates whose measured files the proof gate checks. It excludes other scratch stores, virtualenv and full-tile cache. Lead copied only that bundle into a fresh project-local root and successfully ran verify→export→verify using existing isolated dependencies; evidence is data/experimental/lead/bundle-smoke.json. Re-run engine.package after documentation changes to refresh hashes. Optional JRC/strong-baseline components require separate review/bundling. Master alone stages/commits/publishes; this lead performs no Git mutations.

## Timing, resources and indexed tradeoff

Accepted full-load measurements use seven repetitions/two hot warmups on AppleM5/Mac17,2/arm64,10logicalCPUs,32GiB RAM. Children run sequentially with numerical thread limits. Milliseconds are per complete17-plot batch.

| Scope | Original | Retained compact |
|---|---:|---:|
| Hot median; arrays already loaded |1.418ms|1.446ms|
| Fresh-process native load+query median |11.182ms|5.800ms|

Imports/common geometry read are outside operation timers and included in separate subprocess-wall samples. OS cache is uncontrolled and likely warm: **process-cold is not disk-cold**. Hot results establish no speedup. Encoding costs212.443mswall/212.037msCPU. Encoding child peak RSS101629952bytes; compact cold child maximum72630272bytes. RSS includes interpreter/imports/input data, not only incremental operation memory. Full samples/p95/CPU/environment and historical losing runs remain archived.

`engine/indexed.py` selects on the original global chip lattice before fetching a bounding window. This avoids a confirmed1ULPshift from reusing a translated affine origin: native row1/col1 center98.772625 versus98.77262499999999 changed a boundary-inclusive query1→0 despite identical pixels. Regression and independent checks preserve exact behavior; no tolerance/buffering is introduced.

The separately recorded accepted-store window experiment was slower: source hot2.404ms/process-cold8.976ms; compact28.150ms/32.193ms. Compact repeatedly decompresses large chunks and revalidates indexes without a decoded-chunk cache. All timed answers match. Full preload remains default for this small AOI. See artifacts/window-benchmark-v1.json and artifacts/window-experiments/; accepted full-load measurement is unchanged.

## Additive research underway

**JRC baseline.** Luna acquired officialJRC2020v4 N10_E90 (197739699bytes) and a46238-byte native1809×3695chip. Lead independently verified source-window pixels ANDmasks. Officialv4QML explicitly labels0Non-forest/1Forest; transparent0 is not nodata when valid. Version-specific XML carries older dates/prior-method links; preserve the discrepancy. A separately scoped Sol worker is implementing native queries, binary-class codecs, full fidelity,17plot results and proof gates under engine/jrc*.py, artifacts/jrc-*, and [engine-jrc-task.md](engine-jrc-task.md). Contract draft: [engine-jrc-interface.md](engine-jrc-interface.md). No resampling/fusion/legal flag. Main Hansen proof stays unchanged.

**Stronger standard-format control.** The selector researcher's separate seen-company-AOI audit found a preliminary531953-byte GeoTIFFZstd19/predictor1/block256 control versus535012custom. Its initial timing/integrity work is not equivalent yet; no adoption or generalized claim follows. [engine-strong-baseline-task.md](engine-strong-baseline-task.md) assigns an additive, isolated full/query/window/resource comparison with accurate masks/metadata/hash costs. If the standard format wins after review, retain that scientific conclusion rather than defend a custom codec.

**Adaptive selection.** Another Solxhigh researcher owns data/experimental/selector/ and its report, using content-blind spatial splits from existing public raw tiles, frozen policies, held-out regions, overhead, fixed-format controls and regret. No supplier labels or complianceML. On current company-AOI chunks at128/256/512/1024, separate_zstd_l19 is already smallest for every tested chunk; hypothetical per-chunk switching saves0payloadbytes before policy overhead. That rejects adaptive complexity for this AOI unless new measured evidence changes the decision. Broader results remain under independent review.

## Sources, constraints and team execution

Actual charter, AGENTS, README, printed/spoken/kickoff references, product direction, sample audit, acquisition and judge review were read before implementation. Relevant official semantics were rechecked: [Hansen catalog](https://developers.google.com/earth-engine/datasets/catalog/UMD_hansen_global_forest_change_2025_v1_13), [Shapely covers](https://shapely.readthedocs.io/en/stable/reference/shapely.covers.html), [JRC product page](https://forobs.jrc.ec.europa.eu/GFC), [JRC catalog](https://developers.google.com/earth-engine/datasets/catalog/JRC_GFC2020_V4), [v4 class symbology](https://forobs.jrc.ec.europa.eu/GFC/download?output=qgis&type=symbology&version=v4). Dataset citations/version/limitations remain in source provenance and companion evidence.

No nested spawn/send_input tools exist in this lead session. Master proxy dispatched W1codec, W2oracle, W3benchmark; the lead published disjoint tasks, reviewed code/reports and independently ran integration checks. Completed workers were closed/resumed through master. Luna handled bounded public acquisition; additional Solresearch remains isolated. No fast-mode control is exposed or claimed. Coordination IDs/task ownership are in engine-worker-tasks.md. No source mutation, private upload, external publication/messaging or cloud spending occurred. Company publication permission remains unresolved; keep the supplied/derived demo local.

## Selector review completed

Lead decision: **do not integrate the ML selector**. Independent accounting/protocol audit passed; [engine-selector-review.md](engine-selector-review.md) records what was checked and its limits. The1.17%level3family gain loses to a matching-level standard GeoTIFF control; allowingstrongerlevels, selection loses400bytes to fixedlevel19. Threeheldoutregions/one source tile and missingmixedvalidationcoverage limit generalization. Strong-format seen-AOI control is being independently implemented/measured in its separate task; no acceptedbenchmark mutation.

## Current parallel assignments

Additional nativeJRCcompanion and additive optimizedGeoTIFFcontrol workers are active with disjointengine/artifact paths. A bounded spatial-rule sensitivity assignment is published in engine-spatial-sensitivity-task.md (research-only paths), following the master's agenda. It will comparefixedcentercoveragewithstrictpositiveareaoverlap, preserving masks/unknowns and recording nativewitnesses; no productionrulechange or declaration-groundtruth fitting. Experience-facing source/metric distinctions are recorded in engine-experience-handoff.md.

## Additive progress at03:44UTC

Published the master-selected live-loopback milestone contract (`engine-live-interface-v1.md`) and disjoint backend task (`engine-live-worker-task.md`). Temporary geometry requests will use the frozen retained Hansen snapshot, complete native evidence, explicit4096candidate-cell budget and request/body/snapshot/geometry binding. All17actualplots fit the interactive budget (largest728candidatecells); no supplierrecord or acceptedmeasurement change. Implementation is delegated through master proxy; no live service claimed before it runs.

JRC21tests rerun successfully and a separate45file~1.15MBbundle verifies without its197.7MBacquisitiontile. Ordinaryexport still remeasures and requires thattile; W1operationalfix request and concrete reproduction are in engine-review-notes.md. Lead's18standard-format JRCcontrols all preserve fullraw/masks/grid; best one-bitGeoTIFF plusrequiredmetadata is19791bytes vs21459custom. This is a preliminarysamechipcontrol, not yet fairrepeatedquerybenchmark; boundedfollow-up assignment is engine-jrc-standard-task.md.

StrongHansencontrol final19tests pass; actualcompleteGeoTIFF256store532444bytes is2568bytes smaller than535012custom, with workload-dependenttiming/resource tradeoffs. Lead found integer1accepted in booleanproof fields afterself-consistentrehasing; focusedW3verifierrevisionrequested before acceptance. Canonicaldata/measurements remain unchanged. Strong-control claims are separate from the accepted comparison againstprovidedDEFLATEinputs.

Lead now accepts the additive standard-format storagecomparison afterdirectTIFFreadback, exactmetadata/masks and17source+oraclequerychecks:532444bytes vs535012custom (2568bytes/0.480%smaller). See engine-strong-baseline-review.md for truthfullyscopeduser-facingcomparison and engine-experience-handoff.md forHooke. Newverifierhardening remainsopen independently ofcanonicaldata validity. Separatemanifest artifacts/strong-baseline-bundle-manifest.json inventoriesonlycurrentstrongexperiment+specificretainedHansenproofdependencies;43files/about3.72MBclean-copyverificationpassed. AcceptedHansenchoiceunchanged.

## Consolidated acceptance milestone

Current review and packaging status is in [engine-status-0413.md](engine-status-0413.md). Live canonical binding is resolved (46 backend +112 client checks; clean-bundle17 real HTTP queries exact). JRC J1/J2 fixes pass28tests and byte-identical no-full-tile ordinary regeneration. Separate live/JRC minimal inventories are current. Strong-control proof hardening and independent audit rechecks remain explicit gates; accepted Hansen choice is unchanged. Spatial sensitivity is approved only as an optional educational comparison, with no default-rule change.

Independent follow-up now accepts refreshed JRC J1/J2 and all spatial sensitivity results. The regenerated46-file JRC inventory passes another clean-copy no-tile byte-identical lifecycle. Strong-control proof hardening remains the only pending engine research-proof gate; actual standard-storage/readback comparisons are independently confirmed. The earlier claimed missing export.py dependency was incorrect: the actual helper comes from already-guarded engine.benchmark; review notes and task are corrected.

## User-requested early stop / checkpoint

New research and features stopped. Final ready/gated scope and minimal file handoff are in [engine-checkpoint.md](engine-checkpoint.md). Stable Hansen/JRC/live inventories are regenerated and hash-audited. The optional strong-control verifier revision and vintage study must remain explicitly unaccepted if they do not complete their existing gates before master integration. No new benchmark run was launched to close the session.
