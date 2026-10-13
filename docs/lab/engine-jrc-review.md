# Current lead acceptance — JRC J1/J2 revised

At04:10UTC, reviewed currentcode/report, reran all28JRCtests (pass7.306s), regenerated46file inventory and independently reran clean-bundle verify→ordinaryexport→verify withoutfullsourcecache. Reexport isbyte-identical; no remeasurement occurs. Newmeasurement isexplicit --measure. Per-call warmup/sample/child result andsource/code/store guards now bind measuredwork; tests reject anincorrectintermediateanswer andrehashedsample/guardforgeries.

Accept the refreshedcompanion for separate-native-source integration. Independent Feynman focused recheck now passes the original J1 attack, fresh positives, all source/codec/query checks and the no-tile lifecycle. JRC backend acceptance is independently confirmed. UI remains a separate integration check. No Hansenchoice orfrozenartifact changes. Currentexperiment/run/artifacthashes are in engine-jrc-interface-v1.md; JRCbundlemanifest is regeneratedafterfinaldocs.

The strongerstandardcontrol nowtotals19901bytes including4196requiredmanifest, superseding19791preliminaryprobe. It is1558bytes/7.26%smaller thancustom21459; customloads faster/lowerRSS in theadditivestudy. Lead21tests+retainedstudyverificationpass anddirectTIFFsource/mask/metadatareadbackpass. Scope anycustomsavings tosuppliedDEFLATE; retain binarycodec asverifiedcomparisonpath without claimingformatoptimality. See engine-jrc-standard-review.md.

## Historical initial review follows

# Lead review of separate JRC companion

Status at2026-10-13 03:36UTC: source, native-query and full-array codec evidence pass lead checks. Final companion integration is pending two reproducibility gates and the independent xhigh review. Accepted Hansen artifact/store/measurement remain unchanged.

## Evidence reviewed

Read engine-jrc-report.md and all five worker modules, inspected actual artifact/query/receipt schema, reran21JRC unit methods (2.692s, allpass). Lead separately read the original source window before this handoff: all6684255rawvalues and masks match the chip. Worker scalar membership/reduction agrees on all17plots; shared GEOS topology validation is disclosed. These checks preserve mapped observations, not source accuracy or legal conclusions.

The official pinned v4QML labels0Non-forest and1Forest. Its alpha0 style is not a nodata mask. The chip has no nodata and allmasksvalid. Product referenceyear2020 is distinct from versionv4/publication2026. The pinned v4XML has older dates and an older report link; the artifact preserves that discrepancy. Official links and exact file hashes are in engine-jrc-report.md and the artifact dataset metadata. No JRC/Hansen resampling or combined compliance rule was introduced.

Native selected centers total9511 over17plots; valid0=8957, valid1=554. P-0001 contains all554observed1cells among1083selected; otherplots have valid0only. These are cell counts at JRC resolution, not hectares or comparable same-area Hansen counts. Supplier declarations remain separate.

## Reproducibility gates

1. Ordinary export currently invokes a new benchmark rather than regenerating from a retained measurement. In an exact manifest-only copy without the197739699byte source acquisition tile, artifact verification passes but ordinary export fails FileNotFoundError at the readback. Evidence: data/experimental/lead/jrc-bundle-first-review.json. W1 should provide explicit new-measurement command and ordinary retained export, with verify→export→verify and byte-identical regeneration.
2. Measurement needs start/end source/input/code/store checks and cold-child binding, with each timed answer checked. The current source only validates the final repeated answer and computes identity once. This does not invalidate the independently checked canonical pixels, but can admit mixed-state measurements during shared-workspace changes. Label the percentile interpolation method.

Both requests were already appended to engine-jrc-task.md; engine-review-notes.md repeats the concrete reproduction for master relay. W1 retains JRC core ownership. Lead owns packaging.

`engine/package_jrc.py` generates a separate45file inventory, initially about1.15MB, containing required chip/provenance/QML/XML, all8measuredstores, run/identity records, code/tests/contract/report and exactplotinputs. It excludes the197.7MBacquisitioncache and allHansenmeasurements. It is a review inventory, not final acceptance. Regenerate after worker fixes. `data/experimental/lead/smoke_bundle.py jrc` automates clean-copy verification and ordinary deterministic export; it should pass after the lifecycle fix. Without the fulltile, verification checks the archived readback identity, not a new absent-source read.

## Stronger standard-format control

A custom-versus-provided-DEFLATE result is not proof that a custom format beats optimized standard encodings. Lead's additive18control probe uses the exact same6684255pixelchip; allvalues,masks,nativegrid pass roundtrip. Required reconstruction metadata and file integrity manifest are counted. No baseline crop savings are counted.

| Candidate | TIFF | Required metadata | Total bytes |
| --- | ---: | ---: | ---: |
| One-bit GeoTIFF, Zstd19, block1024 | 15705 | 4086 | 19791 |
| One-bit GeoTIFF, Zstd19, block512 | 16406 | 4084 | 20490 |
| Current custom packed19/block1024 | 15310 payload | 6149 index/metadata | 21459 |

The standard1024control is1668bytes (7.77%) smaller than the customstore at this probe's scope. Rawpayload alone would favor custom; index/metadata reverses the choice. This is a useful counterexample to extrapolating payload ratios. The full probe includes one-bit and eight-bit physical storage, levels3/19, blocks256/512/1024 and applicable predictors1/2. Its single encode/decode times are exploratory, not a fair isolated benchmark; only real all-valid masks were exercised. No production standard decoder or malformed-input guarantees are yet claimed.

Reproduce: `.venv-data/bin/python -B data/experimental/lead/jrc_standard_probe.py`. Results: data/experimental/lead/jrc-standard-probe/results.json. Published engine-jrc-standard-task.md for a bounded research worker to add necessary safety/independent-mask support,17query/oracle comparisons and fair repeated timings. Complete manifests may add bytes; retain the measured result either way. Do not present the current42.98%symmetric-provenance saving against the providedDEFLATEchip as a win over optimizedGeoTIFF.
