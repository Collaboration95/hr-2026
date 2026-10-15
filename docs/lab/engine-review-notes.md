# Lead review queue / messages for proxy-dispatched workers

## 2026-10-13 early core stabilization

W2: Core explicit geometry validation now rejects unclosed rings,3Dpositions, nonfinite/boolean/nonnumeric coordinates, non-dict inputs and invalid topology. Please test latest query.py. interface-v1.md now explicitly documents missing-band diagnostic effects you identified.

W3: **Accounting review required before final benchmark.** load_source now reads/verifies data/public/provenance.json as well as chips. Therefore the claim “every file needed to load/query” must account for that manifest. Current baseline storage lists chip files and generated metadata.json only. Either count acquisition provenance bytes in baseline necessary metadata (with explicit explanation), or factor it into symmetrically counted common provenance if both representations require it in the measured path; do not silently omit it. The former matches current loaders. Re-run after source stabilization; no further core source/query changes planned until tests identify a need. source.py return metadata/API is unchanged.

W1: Early code read looks appropriately bounded and checksum-aware. Window decoder intentionally verifies selected chunks only; retain that limitation. Lead will test window-query lattice identity separately because shifted transforms can introduce floating-point reassociation at boundary centers. No worker change requested yet.

All: use report files for requests. Lead owns integration and final benchmark binding in demo; do not replace canonical demo files. Benchmark/codec outputs are not yet accepted until all independent tests and lead review pass.

## Cycle2 requested after first worker handoff

Master proxy can relay/resume W1 and W3 against these bounded tasks; lead owns decisions.

**W1 next:** A measured whole-AOI payload probe shows raw separate-band zstd level19 yields532636bytes vs587534atlevel3; filters worsen it. Add deterministic `separate_zstd_l9` and `separate_zstd_l19` candidates to your existing codec/API with candidate-specific fixed compression settings. Preserve decoding of all existingv1stores (their level3 remains valid). Keep all masks/rawvalues and chunk/index metadata. Extend all current roundtrip/malformed tests across new candidates and explicitly reject mismatched candidate/level declarations. This is a bounded compression-level experiment, not a new format/semantic change. Do not claim total-storage win from payload-only results. If already closed, master may resume same worker or delegate this bounded follow-up when slot is available; lead will not overwrite your files meanwhile.

**W3 next:** After current32/64/128/256sweep and W1candidate addition stabilize, measure the two stronger separate-band variants at256and512(or1024if measured index/ratio tradeoff justifies). Keep same full AOI, provenance accounting, full raw/mask/17plotchecks, process-cold/hot/resource scopes. Freeze a final accepted benchmark selection with explicit reason and preserve earlier failures/losing candidates. Report both smallest encoded and overall original-vs-encoded choice. Lead will consume chosen store path from your report to refresh canonical demo; do not leave it implicitly pointing at the last experimental configuration if that is not the retained decision.

**W2 next:** First delivery tests independently passed in lead's full73test run. No further core bug identified yet. Lead is testing whether window-origin floating-point reassociation can change centers exactly on boundaries; a window query path must select using the original lattice before fetching data. If useful, add a regression fixture demonstrating this hazard in independent oracle tests, without depending on unimplemented indexed API. Do not silently relax boundary tolerances.

## Exact window-boundary witness confirmed

Lead experiment `data/experimental/lead/window-origin-witness.json` demonstrates native row1/col1 xcenter98.772625 vs window-reassociated98.77262499999999. A polygon whose boundary is the original center selects1cell on full grid but0on shifted grid. This is NOT a codec pixel mismatch: it is a query-lattice arithmetic hazard. Never evaluate a window by re-running center generation on its shifted transform. Lead's forthcoming indexed path will select original global centers once, then fetch their rawvalues/masks. W2 may use the recorded witness for a regression; retain exact covers semantics rather than introducing a tolerance.

## Core cycle2 refactor notice

query.py now factors aggregation into summarize_selected(values,masks,selected_count,outside_count,missing_bands=()) so upcoming indexed reads use original-lattice selection rather than shifted-window arithmetic. Existing evaluate API and results unchanged; all41W2methods plus7lead integration tests pass. Added finite/safe inverse-grid extent rejection before integer allocation. W3 must use the new implementation fingerprint for final metrics; earlier experiment files remain historical evidence.

## W3 optional indexed experiment boundary

Lead-owned engine/indexed.py now offers SourceWindowReader(root=None), CompactWindowReader(path), evaluate_reader(reader,geometry,missing_bands=()). Context-managed readers; source hashes/full compact payload hash verified at initialization; reads only selected bounding windows afterward. Original-grid selection avoids confirmed float-origin hazard. Existing full-load benchmark stays required/default. Lead will measure indexed paths separately (owns engine/window_benchmark.py and artifacts/window-benchmark-v1.json), so W3 need not edit or benchmark this module. Core source/query APIs stable again; final full-load benchmarks should capture their updated hashes.

## Priority W3 correction from independent validator

**Accepted:** baseline counts generated source_geotiff/metadata.json (948bytes), but actual load_source reads chips plus data/public/provenance.json and does NOT need that generated duplicate identity manifest. Remove its948bytes from necessary baseline storage. It may remain a separately labelled experiment evidence file, not a required query file. Correct necessary source baseline is576999+8294=585293bytes for current files. Do not inflate denominator with optional duplicated metadata. Retain a clear symmetric comparison view if useful, but distinguish actual loader requirement from common provenance reporting.

Please correct your owned harness/tests/report, rerun strongest candidates with stable core (query/source now unchanged), and explicitly retain corrected final measurement. Notify via report. Lead's new engine/proof.py requires current identity/input/code bindings, archive equality, all measured-file bytes, and retained selection; it will reject old/stale artifacts until a fresh retained run exists. No changes needed to W3 public function APIs. Lead will refresh demo and coordinate validator recheck after correction.

V1–V3 proof fixes are ready: validation/repro_proof_gaps.py now exits0 with all false proofs rejected;7new lead regression tests pass; engine.verify recomputes full arrays/masks and all receipt/summary/source claims. Current exporter auto-selects retained store, requires valid benchmark binding, and offers --without-benchmark for explicit metric-free exports. Validator may recheck these independently now; V4freshness waits for corrected baseline retention and experiencecopy.

## New additive control assignment published

Selector researcher already has a **seen company-AOI** control audit in aoi-control-results.json, distinctfromits heldoutstudy: GeoTIFFZstd19/predictor1/block256 is531953bytes vs535012custom, but existingtimingslack17plotisolatedqueryproof and equivalenttimedhashvalidation. Lead does not extrapolate trainingpatchresults. Published engine-strong-baseline-task.md for a separatelyowned additivecontrol/measurement module (resumeW3oravailableSol). Acceptedbenchmark/filesremainimmutable; newcontrolmayjustifylaterstandard-formatadoption onlyafterreview. JRCworker remains separatelyscoped.

## JRC lead review — 03:32 UTC

Lead reran all21 JRC tests: pass in2.692s. Generated separate candidate manifest with engine/package_jrc.py:45files,1154283bytes at this review. A project-local clean copy of exactly those files, with no197739699byte full source tile, passes the positive artifact verifier. Ordinary export fails FileNotFoundError because it starts a new benchmark/readback. Reproducer output: data/experimental/lead/jrc-bundle-first-review.json. This confirms the operational gate already specified at the end of engine-jrc-task.md.

Master proxy: resume W1 on the same JRC-only ownership for the two outstanding gates: explicit new-measurement vs retained ordinary export, and source/code/store/sample identity guards. Lead owns engine/package_jrc.py and final packaging, so W1 must not edit that file. Candidate manifest is review inventory, not final acceptance. After fixes refresh the separate JRC measured artifact, report the new experiment/run, and demonstrate no-source-cache verify→ordinary export→verify. Keep accepted Hansen unchanged.

The spatial sensitivity assignment is ready in engine-spatial-sensitivity-task.md for an available Sol; no study output was present at03:32. It does not depend on the JRC fixes or strong-format control.

## JRC standard control — additive task available

Lead18-control full-chip probe found standard NBITS1/Zstd19/block1024 TIFF15705bytes +4086requiredmetadata =19791bytes, smaller than custom21459. Allraw/masks/grid exact; only single timings, not accepted fair-query proof. Published engine-jrc-standard-task.md for available Sol high; new research-only ownership data/experimental/jrc-standard/ + report, disjoint from W1 JRC core fixes and lead package. Do not delay the lifecycle fixes or claim a custom-over-standard win. Current JRC compression comparison is scoped to the provided native DEFLATE chip.

## Strong-control lead review: focused verifier revision

Lead read finalreport/measurementverifier and reran all19tests: pass0.847s. Fullfreshproof passes in an independent disposablebundle. Concrete negativecontrol also passes unexpectedly: replace controls[0].proof.raw_values_equal and its firstcomparisons.equal with integer1, rehash the archive/run. Python dict equality treats1asTrue. Reproducer data/experimental/lead/review_strong_proof.py; output strong-proof-review.json. No canonicalfile changes. This is typedfalse-proofacceptance, not rawdata corruption; actual532444vs535012bytes remain independently checked.

Master proxy: resume W3 within its existing strong_baseline-only ownership for strict type-aware equality (canonical_bytes/differing_fields or equivalent) in every reconstructedproof/derivedstructure; rejectnumericbooleans/floatcounts and unexpectedproof keys. Also validate measurement settings and controlset against identity (unique blocks/candidates, supportedconstantsettings, repetitions/warmups bounds), finite nonnegative timing samples and expected sample lengths, and declared timing summaries. Review current source/custom/controlproof comparisons and commoninputview which use Python ==. Add freshpositive plus self-consistently rehashednegative regressions, refresh only additiveexperiment/artifact after codefingerprintchanges. AcceptedHansen remains immutable. Lead will rerun ownreproducer and scientificreview afterward.

Current observedtradeoff remains: control256 is2568bytes/0.480%smaller; customfullcoldload faster; controlindexedmedians faster with cache/perchunkintegritydifferences explicitly disclosed. No production choice change requested. Avoid turning this bounded verifierfix into a new tuning study.

Additional focused W3guard correction: include engine/export.py in IMPORTED_CODE/CODE_NAMES because imported differing_fields participates in source/control/oracle proof construction. Existing canonical answer checks still pass; this is missing code dependency binding, not an observed data change. Full lead scientificdecision/storageacceptance and separate proofhardening status are now in engine-strong-baseline-review.md; experiencehandoffupdated.

JRCvalidator findings J1/J2 read in full and agree with lead's prior operationalgates. Actual transienttimedwronganswer was accepted; this is stronger than staticcodeinspection. Ramanujanfixes should reject validation/jrc_timing_repro.py's control and retainfreshpositive+no-cacheordinaryexport. Independent20forgerynegatives and168unknownchecks already pass; keepthese distinctfrommeasurement-integrityacceptance.

## Independent acceptance and correction

Feynman independently confirms JRC J1/J2 resolved, fresh positives, original wrong-second-sample rejection and46-file no-tile byte-identical regeneration. Strong actualstorage and allspatialcellsets/fiveflags/15witnesses pass independent scalar/rational checks. Spatial productionrule remainscenter.

Correction to my prior dependency note: actual strong_baseline_measure imports differing_fields from engine.benchmark, already guarded. Lead confirmed differing_fields.__module__ == engine.benchmark. The claimed missing engine/export.py dependency was mistaken; withdraw that request. No speculative dependency change is required. Six actual proof inconsistencies remain in validator-strong-spatial-report.md and are added to the bounded worker task.
