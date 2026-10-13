# Engine implementation report

## Coordination and constraints

Session started from charter and actual README, printed/spoken/kickoff references, product-direction, sample audit, layer acquisition, and judge review. Ownership: engine/, artifacts/, docs/lab/engine-*, docs/lab/interface-v1.md, new data/experimental/. No Git mutations, source-file modifications, publication, private uploads, cloud spending, or external messaging.

Available tool inventory contains no worker spawning or inter-agent `send_input`. Therefore requested 3–4 Sol workers plus Luna cannot be instantiated from this session. No hidden runtime workaround is used; implementation proceeds serially in bounded modules with independent oracle tests. This is an actual tool limitation, not completion of the requested hierarchy. No fast-mode setting is exposed or changed. Master and experience lead should read interface-v1.md; their IDs are recorded there.

## Initial milestone

Versioned contract published in interface-v1.md. Resolves partial support explicitly: witnessed positives remain true; absent events with unknown support remain null. Observed histograms remain available if valid land exists. Missing required bands, zero centers, or no valid land suppress analytical results. Engine work underway.

## Source slice ready (early handoff)

Master proxy dispatched W1 codec `01a132fd-ac26-75d2-9abb-3196038cea62`, W2 oracle `01a132fd-ac79-7c61-9e4d-d7921ec99665`, and W3 benchmark `01a132fe-e706-7f53-a398-67b42b904884`. Disjoint task/API ownership is published in engine-worker-tasks.md; workers return own report files and master relays. Lead retains integration and independent review.

`engine/model.py`, source.py, query.py, export.py now implement actual source loading and all17native-center queries. `artifacts/demo-v1.json` and example-v1.json exist with exact supplier strings/geometries, source results, receipts/hashes and native-grid cell footprints. Early export intentionally sets compact_result=null, comparison.equal=null, comparison.status=pending_codec, benchmark=null. UI must not infer equality from pending fields. `engine.export --store PATH` upgrades to measured comparisons when W1 store arrives. Core APIs match taskfile.

Run `.venv-data/bin/python -m engine.export`. Preliminary (not yet independent-oracle-reviewed): 3 plots have mapped2021–23loss,5 have mapped2024–25loss; five supplier-declared indication rows remain a separate concept. P-0003 has87selectedcenters and no observed2021–23/2024–25loss under the current release/query. This does not invalidate the supplier's historical declaration. All17currently have complete known selected support.

## Source semantics verification and core hardening

Official sources rechecked on13October2026: [Hansen v1.13 catalog](https://developers.google.com/earth-engine/datasets/catalog/UMD_hansen_global_forest_change_2025_v1_13) defines canopy2000percent for vegetation taller than5m, event-year codes0–25, and datamask0/1/2. The local chips preserve their native0.00025degree grid; nominal catalog pixel-size labels must not become a hectare conversion. [Shapely covers](https://shapely.readthedocs.io/en/stable/reference/shapely.covers.html) includes polygon/hole boundary points; our query uses exact predicate evaluation, no geometry buffer or resampling.

Core now explicitly rejects unclosed rings,3D/nonfinite/non-numeric coordinates, invalid topology, unsupported geometry types, excessive vertices and candidate-cell windows. Added a local CLI: `.venv-data/bin/python -m engine --plot P-0003` (optional `--store PATH`; custom local `--geometry FILE`). Errors are structured stderr JSON with exit2; comparison mismatches exit1. Added `artifacts/synthetic-v1.json` via `.venv-data/bin/python -m engine.synthetic`: six clearly labelled examples for tiny/no-center, partial absent, partial positive, water, nodata and missing-band states. They remain separate from the17realplots and fidelity denominators.

## Core/API stabilization checkpoint

Source loader now verifies chip hash/byte size, grid and source-window-readback flag against existing `data/public/provenance.json`, not merely the files' current self-reported identity. It never regenerates acquisition or source data. Shape/transform/metadata return API unchanged. W2 preliminary independent scalar oracle matches all17outputs. W2 flagged malformed ring/3D/non-dict inputs; core already added explicit rejection while their tests were being authored. Missing-band diagnostic side effects are now explicit in interface-v1.md. Core stabilized for worker benchmarks after this checkpoint; implementation-hash checks should reject any racing earlier run.

## First full slice — 02:10 UTC

Lead independently ran `.venv-data/bin/python -B -m unittest discover -s engine/tests -v`: **73tests passed**, including the W2 independent oracle on all17realplots and synthetic/adversarial cases, W1 all-pixel codec roundtrips and malformed-store rejection, W3 registry/concurrency/accounting checks, and lead source/export integration checks. Worker final reports are still arriving; this is lead-run evidence, not just worker assertion.

Canonical demo-v1.json now includes actual compact results and exact comparison receipts from the current smallest encoded candidate. All17source/compact results agree; all744732cells and2234196raw band values plus masks round-trip. Initial four chunk128 candidates are all larger than the compressed originals. Keep original as overall storage choice; encoded candidate is a correctness/prototype comparison, not a claimed storage win. W3 is measuring a chunk-size sweep. Baseline provenance-file accounting review remains open in engine-review-notes.md before final accepted metrics.

A lead payload-only probe (`data/experimental/lead/filter-payload-probe.json`) found horizontal/vertical byte-delta filters worsen this cohort. Raw separate-band zstd level19 reduces whole-AOI compressed payload vs level3 (532636 vs587534bytes) but this excludes metadata/index/masks and is NOT a complete storage claim. This justifies a bounded stronger-compression follow-up; it does not justify adopting delta filters or claiming a win yet.

## W2 accepted by lead

Read the final W2 report and implementation, including exact-arithmetic orientation fallback, scalar membership/reduction, work limits and shared GEOS topology validation. The integrated73-test lead run includes all41W2methods;360seeded and144exhaustive synthetic cases remain separately labelled. All17realplot outputs match. W2 is accepted for current query correctness with its stated independence limits. Re-run these tests after any query refactor. Master has closed that worker slot; cycle2regression request remains optional.

Lead also verified `python -B -m engine.verify` against the canonical demo: all17actual source/compact queries, source values, native evidence, receipt/content hashes and store files pass. The native-origin/window boundary hazard is recorded in data/experimental/lead/window-origin-witness.json; current full-grid outputs remain correct.

## Cycle2 — original-lattice indexed reads

Added `engine/indexed.py`: original GeoTIFF and compact readers fetch only the selected-center bounding window. They select on the original global lattice first, then reduce fetched rawvalues/masks. This fixes the confirmed shifted-origin boundary hazard without any tolerance or resampling. Both reader initializations verify full stored input identity; compact window calls additionally verify selected chunk streams. Source handles are context-managed; compact index/payload stay immutable during a reader lifetime. W1read_window's lower-level selected-chunk-only integrity limitation remains documented separately.

Refactored query reduction into summarize_selected and source identity/header opening into open_sources, preserving public load_source/evaluate return contracts.50indexed+oracle/adversarial test methods passed, including both readers on17plots, partial/outside/missingband states and the actual native-decimal boundary witness. New `engine/tests/test_indexed.py` is lead-owned. No window speedup claim yet: this small AOI may favor full preload. W3 final metrics must fingerprint updated source.py/query.py; prior experiments remain historical.

## Independent validator V1–V3 fixes — proof gate hardened

Read and reproduced validator report. Accepted V1–V3: initial verifier accepted self-consistent but false benchmark metadata, off-plot full-fidelity claims, and forged receipt/summary contract fields. These were proof acceptance gaps; independently checked canonical pixels/query results were correct. Prior “verifier passes” evidence did not cover these negative cases.

Added engine/proof.py and strengthened exporter/verifier. Export now requires benchmark binding to actual source/query/input hashes, current measured implementation hashes, immutable registered run and identity, every measured file byte/hash, explicit retained-choice and archived selection, winner/accounting, and the exact retained compact store. Default export selects that retained store. Unbound/stale benchmark raises ValueError; `--without-benchmark` explicitly emits no metric claims. Verifier now recomputes full raw-array/mask equality (not only17plotanswers), every receipt field/source list, every derived summary and period envelope, every per-plot store claim including cached stores, and the benchmark binding. Hashes remain integrity evidence, not authentication or source accuracy.

`.venv-data/bin/python -B validation/repro_proof_gaps.py` now exits0: all three rehashed false-proof fixtures rejected and forged benchmark export rejected. Seven new lead regression tests in test_proof_guards.py pass, including off-plot raw/mask mutations, later-receipt tampering, forged periods/source lists/summary, and pending-hash forgery. Canonical export regenerated from W3's deliberately retained benchmark and verified successfully. V4 final UI refresh still belongs to coordinated integration; experience must copy this refreshed canonical JSON.

## Corrected retained proof and package checkpoint — 02:30 UTC

W3 removed the unused948-byte metadata manifest from necessary source storage. Current retained experiment `exp-0109a8d6c4782217871315b92c63a971d11ebd164585c80981f24c55b4f68fea`, run `run-71a5b90b05bdce363044d8e232ae33d20b31f3868a6f5ba50bf61372b98194a9`: separate_zstd_l19 atchunk1024,535012bytes total vs585293necessary original bytes. Exact all-pixel/mask/17plot preservation. This is a measured8.59%necessary-loader-storage reduction, not a new-algorithm or universal-compression claim. Source TIFF payload alone is576999bytes; no crop denominator. Higher compression has ingestion cost and larger chunks have window-query tradeoffs.

Fresh positive control now passes after corrected retention: `python -B -m engine.export` then `python -B -m engine.verify` succeeds,17computed comparisons. Canonical demo matches the explicit retained choice and current code/input/archive/store files. V1–V3 false-proof regressions remain covered; validator can recheck positive and negative cases now. Experience should refresh appdata from this canonical file forV4.

`engine/package.py` emits `artifacts/retained-bundle-manifest.json`: exact required paths/hashes/bytes for a minimal local retained proof bundle. Includes source chips/provenance/supplier inputs, enginecode/tests, canonicaldemo/example/synthetic/benchmark, retainedrun+identity+selection and all candidates in that retainedrun (because benchmark verification checks them). Excludes~64MBscratch/otherexperimentalstores, `.venv-data`, and224MBfulltilecache. Master alone chooses/stages/commits; no Git action taken here. Re-run `.venv-data/bin/python -B -m engine.package` after final report/code edits to refresh manifest hashes.

## Minimal-bundle reproduction and conservative accounting views

Lead copied only the manifest-listed50files (~4.28MB) into a fresh project-local temporary root, with no full source tile cache or other experimentstores. Using the existing isolated Python dependencies, `engine.verify`, `engine.export`, and `engine.verify` all exited0 there. Evidence: data/experimental/lead/bundle-smoke.json. The tiny optional948-byte research manifest is preserved in the bundle as measurement evidence but remains excluded from necessary-storage denominators.

Storage scopes must not be conflated:

| Scope | Original bytes | Encoded bytes | Reduction |
|---|---:|---:|---:|
| Actual query-loader requirements |585293|535012|8.59%|
| Conservative store vs original TIFF payload (encoded metadata included) |576999|535012|7.28%|
| Symmetric full review inputs: both retain8294-byte acquisition provenance and19265-byte supplier/geometry files |604558|562571|6.95%|

The symmetric6.95%view is a useful conservative presentation figure. All views cover the same604×1233native grid; no full-tile-to-AOI crop saving. Full preload hot query medians do not establish a speedup (source1.418ms,compact1.446ms per17queries). Measured fresh-process load+query medians are11.182ms source and5.800ms compact, excluding imports/common geometry read; OS cache likely warm. Level19 ingestion measured212.443ms wall /212.037msCPU and101629952bytes child peak RSS. Compact cold child peak RSS maximum72630272bytes. These are local small-cohort observations, not throughput promises.

Optional indexed first experiment was slower for compact on this tiny AOI (20.337ms hot17querybatch vs2.364ms source; a supersededsmall-chunk store). No production-default change was made. Fresh selected-store measurement follows separately; no mixing with full-load metrics. Original-lattice correctness is retained regardless of performance.

## JRC acquisition review and separate-source decision

LunaW4 acquired officialJRC2020**v4** (v3 remains unavailable):197739699byteN10_E90tile and46238byte nativebboxchip,1809×3695pixels. Read actual report/provenance/script and currentofficial[JRCproductpage](https://forobs.jrc.ec.europa.eu/GFC), [EarthEnginev4catalog](https://developers.google.com/earth-engine/datasets/catalog/JRC_GFC2020_V4) and[JRCdatacatalog](https://data.jrc.ec.europa.eu/dataset/cf7c49ea-8f00-4c5a-bd40-6f25dc341580).

Lead fetched officialversion-specific[QMLsymbology](https://forobs.jrc.ec.europa.eu/GFC/download?output=qgis&type=symbology&version=v4): code0 explicitly**Non-forest** (alpha0), code1**Forest**. Transparent0 is notunknown/nodata when bandvalidity/coverage areknown. Evidence/files/hashes in data/experimental/lead/jrc-semantics/. The officialv4XML also downloaded, but carries older2025dates and a v2reportDOI; preserve that inconsistency and do not treat it as v4method/release evidence. Currentpage says v4technicalreport expectedDecember2026.

Published engine-jrc-task.md for a bounded Solnative-grid baseline/codec/evidence companion. It must retain its ownJRCgrid/masks/values, version/referenceyear/class-labelprovenance, independent17plotchecks, exactfullpixelroundtrip and same-chipstoragebaseline. Noresampling intoHansen, no directsame-resolutioncountcomparison, no combineddeforestation/complianceflag. MainHansenproof remainsaccepted and unchanged while this companion is implemented/reviewed.

## Independent fixed-proof acceptance

Read the xhigh validator's completed focused follow-up (02:33–02:41UTC), not merely the relay. It accepts fresh retained and metric-free positive controls, rejects12specificforgeries, independently decodes all retainedlevel3/9/19stores to matching2234196rawvalues/masks/metadata, and confirms currentcanonical/retained/serveddata agree. V1–V7resolved within that statedscope; no global/sourceaccuracy/accessibilitycertification is inferred. Follow-up evidence and commands are in validator-report.md /validation/verify_fixes.py. Accepted Hansen benchmark/store remain immutable while new research is additive.

## Indexed access measurement — retain full preload

Fresh additive window experiment on the acceptedlevel19/chunk1024store:17queries/batch,7repetitions,2hotwarmups, isolatedordinaryPythonprocesses, bothfullinputhashesverified atreaderinit. Sourcewindow hotmedian2.404ms /process-coldmedian8.976ms; compactwindow28.150ms /32.193ms. Everytimedanswerhash exactlymatches the source querycohort. Compact repeatedlydecompresses largechunks and revalidatesindex for eachsmallplot; no decodedchunkcache is present. Fullpreloadremains default because its acceptedcompacthotbatchmedian is1.446ms. Windowaccess demonstrates correctboundedfetching, not a speedwin here. Complete samples/resourceenvironment/fingerprints are separately archived under artifacts/window-experiments/ and artifacts/window-benchmark-v1.json; accepted Hansen benchmark unchanged.
