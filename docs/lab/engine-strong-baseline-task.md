# Additive strong-original-format control — Sol worker assignment

Master may resume W3 or dispatch a Sol high worker. Existing accepted Hansen benchmark/store/archive are IMMUTABLE. Own only `engine/strong_baseline.py`, optional `engine/strong_baseline_*.py`, `engine/tests/test_strong_baseline*.py`, `artifacts/strong-baseline-v1.json`, `artifacts/strong-baseline-stores/`, `data/experimental/strong-baseline/`, `docs/lab/engine-strong-baseline-report.md`. Do not edit source/query/codecs/model/benchmark/experiments/proof/export/verify/app or selector/JRC worker files. No Git mutations, dependencies, source writes, private uploads/publication/cloud spending. Ordinary local Python measurement processes allowed; no nested agents.

## Why this experiment is justified

Read actual `data/experimental/selector/aoi-control-results.json` and selectorstudy.py read-only. Besides its spatialholdoutstudy, researcher made a **seen company-AOI control audit**: multi-band GeoTIFFZstd19 predictor1 block256 measured531953bytes including947-byte reconstructionmetadata, vs acceptedcustom535012bytes. Allpixels/masks and sampledwindows roundtrip, but it has no17plot/per-processqueryproof and no per-fileSHA checks in timedreads. Oneencode/decode sample andfivewarmwindows are preliminary only; do NOT adopt or overclaim this~0.57%difference yet.

Question: after equivalent input-integrity/mask preservation/metadata accounting and isolated17plotquery checks, does a well-tuned standard GeoTIFF beat the customstore? If yes, report that honest negativecontrol; keep acceptedbenchmark unmodified. Lead decides later UI/retention changes after scientific review.

## Control store/API

Use immutable load_source()Dataset and all17exactgeometries. Create a standard three-banduint8GeoTIFF with nativeEPSG4326shape/transform, Zstdlevel19, predictor1, tiled256(default). Optionally256vs512ifjustified; no broadnewtuning. Include required reconstructionmetadata, exactsourceidentity, format/settings, fileSHA/bytes and masks in a small canonicalmanifest. Hashvalidation atinitialization/read must be counted comparably with currentengine. CandidateIDs explicit, no silentoverwritingexistingstore.

Currentrealbandmasks are alltrue, so implicitallvalid is valid only after encoderchecks everymask and recordsmode. Support nontrivial independentlydifferentbandmasks via a separatelystored lossless packedmaskstream or explicitrasterbands; do not use a singlesharedTIFFmask that loses differences. Preserve rawmaskedvalues, rejectknownrange/type/shape/CRSunsupportedinputs. Recordmaskstoragebytes and verifyfullmasks. The manifest is needed bydecoder (unlike the discardedduplicatebaselinefile); avoid optionaloverheadindenominators.

API in yourmodule: `encode_control(dataset,path,block_size=256)->dict`; `decode_control(path)->Dataset`; context-managed `ControlWindowReader(path)` exposes metadata/read_window compatible with engine.indexed.evaluate_reader. Optionalvalidator uses boundedmanifestJSON, knownfixedfilenames/pathtraversalrejection, sizecaps, fullfilehashes beforedataallocation and headerdimension/typecheck. Reuse coreboundedframevalidator ifusingmaskzstd; don't modify it. No generalmaliciousGeoTIFFsecuritycertification claimed.

## Full proof and measurements

CLI `.venv-data/bin/python -B -m engine.strong_baseline` writes separate artifact with schema `plotline.strong-baseline.v1`. Identify acceptedbenchmark/store byhash/path but neverreplaceit. Include source/code/settings hashes, originalAOI/grid/dateequality, everyrawvalue/mask/metadata fullroundtrip,17exactquerydictcomparisons, W2independentoracle equivalence, and accuratefilesizes.

Compare originalthreeDEFLATETIFF+requiredprovenance585293bytes, acceptedcustom535012bytes, and completecontrolstore. Also report symmetriccommonprovenance/supplier view ifhelpful, with eachcommoninput counted equally. Do not hide the941/947bytes reconstructionmanifest nor addunusedmetadata tosource. No tilecroppingdenominator; allrepresentations cover604×1233fullAOI.

Measure hotfull-preload17queries, freshprocessload+17queries, and indexedwindow17queries forcontrol vsacceptedcustom/source using **same**geometryselection and sameintegrityscope. SeparateordinaryPythonchildren, sevenrepetitions/twowarmups, wall/CPU/peakRSS and rawsamples. LabelOSfilecacheuncontrolled/likelywarm, notdiskcold; reportstartupinclusive separately. Countpreprocessing separately and notecompressedGeoTIFF may have differentper-window integritygranularity; wholefileshashverified atreaderinit isrequiredforallcomparedpaths. NoUIcost, no crosscandidatewarmingmistakes, noasymmetricpreloadedbaseline.

Reproduction must rejectcode/input/storechangesduringrun, preserveearlierresults, and leave acceptedHansenmeasurement byteidentical. Use separatecontent-addressed experimentfolderwithin yourartifacts area; don't write existingW3registry. Reportminima onlyafterfidelitypasses, andconfidence limits ofoneAOI/smalltimingsamples. No 'bestuniversalformat' claim.

## Tests and handoff

Tests includeallrealpixels/masks,17plots, source-to-controlmetadataexact, rawmaskedvalues and differingbandmasks, implicitmaskmodevalidation, malformed/truncated/changedfilehash, mismatchedheaders/manifestshape, excessiveallocationclaims, metadata/pathrejection, original-latticeoneULPboundaryregression viaevaluate_reader, partial/outside/missingband, and nonmutation. Add freshpositive proof plus offplotpixel/mask/metadata/byteclaimforgeries rejected if you expose artifactverifier. Lead will independentlyreviewandrunchecks.

Targetfirstreviewablecontrol+results within30–45minutes. Finalreport explicitpaths/commands/bytes/runtime/resource/evidence, limitations and whethercontroladvantage survivesproperaccounting. Lead mayretainstandardformatasnextversionlater; thisworkisadditiveonly.

## Final bounded hardening follow-up

Master has resumed Galileo in this same write set. Do not tune codecs or change the accepted Hansen run. Read engine-review-notes.md and engine-strong-baseline-review.md, including the lead's reproducible integer-for-boolean forgery.

Acceptance checklist:

- Strict type-aware equality for reconstructed source/custom/control proof, identity, settings, derived comparison and common-input accounting. Reject integer1 for true, false for0, float counts, missing/extra proof fields and contradictory nested structures.
- Validate the identity's supported settings, unique candidate/block set, repetitions/warmups bounds and matching measured control set. Do not accept omitted, repeated or substituted candidates through rehashed archives.
- Check every timing sample is a finite nonnegative number of the proper type, enforce expected lengths, and reconstruct summaries from those samples. Retain real outliers; no new timing selection policy.
- Keep the actual proof dependencies fingerprinted. Correction after independent audit: differing_fields is imported from engine.benchmark, already in the guard; the earlier request to add engine/export.py was mistaken and is withdrawn.
- Pair each rehashed negative with a fresh valid positive. Rerun the lead reproduction; it must retain the fresh positive and reject the integer proof forgery for the semantic reason.
- Refresh only the additive code-bound experiment/artifact and current report. Preserve historical evidence and accepted Hansen files. Provide new run/store paths for lead inventory regeneration and independent validator review.

The actual532444-byte standard store and full raw/mask/query equality already passed lead checks. This follow-up repairs the evidence gate, not the measured data. No product proof promotion until the revised gate passes. Lead owns engine/package_control.py and manifests; do not edit them.

Independent audit supplied six concrete controls in validator-strong-spatial-report.md / validation/strong_proof_controls.py: boolean→integer, hot wall sample count7→1, cold wall sample count7→1, negative encode time, identity level19→3 with actual manifests unchanged, and missing block512 while settings still declare it. Reject all six after rebinding their archive/identity hashes, paired with a fresh positive. No new exploration is needed.
