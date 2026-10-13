# Engine lead consolidated milestone — 13 October, 04:13 UTC

The accepted Hansen benchmark, retained store, frozen17-plot artifact and supplier inputs remain unchanged. The live service and JRC companion are separate additions. No Git mutations, publication or uploads were performed by this lead.

## Ready for integration

**Live Hansen:** lead reran46 backend tests and112 client checks. All pass. Actual responses now supply the three canonical result/evidence strings; the client confirms no fixture augmentation. A clean copy of the37-file service bundle starts on an ephemeral loopback port and answers all17 supplied geometries exactly over real HTTP, with request and canonical receipt bindings checked. Hooke owns persistent8765 startup/proxy integration. Master reports14 actual browser checks by Parfit; this lead does not claim to have performed them. The service remains center-based, bounded, read-only and snapshot-bound.

**JRC native source:** lead reran28 tests after J1/J2 fixes; all pass. The46-file bundle supports verify→ordinary export→verify without the197.7MB acquisition tile; regeneration is byte-identical and performs no new measurement. Every timed sample and child now has result/identity guards. Accept the separate native-grid source view at lead level, pending Feynman's focused fix recheck. It preserves valid0=Non-forest, unknown masks/support, reference2020/versionv4 and the XML date caveat. No grid fusion, count addition or legal verdict.

Current JRC experiment: exp-bfd3067040ae3fb83331667fba2ece195e9372893c81ac1930edbdfc68444f3a. Run: run-5b318b210c244c60458942f67281a8abc6f8ebcc2b3949effc12feb3013cd261. Artifact file SHA256:933b3d302b8ec961444a7f252f74deb87f3f186f1b7f8d5bcb5012cb55658f71.

## Reviewed comparisons and gates

**Hansen standard control:** actual complete store532444bytes versus retained custom535012;2568bytes/0.480% smaller. Lead independently read every TIFF pixel/mask/grid/metadata and all17 query outputs;19 tests pass. Scientific byte comparison is sound, but a rehashed integer-for-boolean proof is accepted by the research verifier. Galileo is now fixing strict types/settings/timings and the missing export.py code dependency. Hold product proof promotion until the fresh gate passes. No new tuning or canonical choice change.

**JRC standard control:** actual complete store19901bytes versus custom21459;1558bytes/7.26% smaller. Lead21 tests, retained-run verification and direct full TIFF readback pass. Custom loads faster and uses less RSS in that separate study. Keep this additive research distinct from the canonical custom-versus-provided-DEFLATE measurement; do not promote a new production decoder. Research verifier type hardening would be required before using it as a product proof gate. Current retained research pointer is data/experimental/jrc-standard/retained.json.

**Spatial rule sensitivity:**29 tests pass; lead's exact read-only replay matches the entire recorded result and all15 changed-flag witnesses independently match source values/masks and native geometry. Positive overlap adds337 memberships and changes five period flags, but explains none of the five supplier-indication2021–23 signals. Approve an optional labelled educational witness, not a default-rule change. artifacts/spatial-rule-witness-v1.json is22.8KB and contains all15 witnesses. Independent audit remains pending.

**Historical vintage:** master has dispatched bounded optional Luna research on preselected Hansen2023v1.11. It does not block live/JRC acceptance. No assumption that the company used that release, no release hunting and no2024–25 absence claim.

## Minimal bundles

Use the regenerated manifests, not every historical cache:

- artifacts/retained-bundle-manifest.json — accepted Hansen,50 files, about4.29MB.
- artifacts/live-bundle-manifest.json — optional live service,37 files, about4.09MB; includes only current retained dependencies and frozen demo for regression comparison.
- artifacts/jrc-bundle-manifest.json — separate current JRC companion,46 files, about1.33MB; excludes the acquisition tile.
- artifacts/strong-baseline-bundle-manifest.json — current additive Hansen control plus its specific retained dependencies,43 files, about3.72MB. Regenerate after Galileo's imminent revised run before checkpointing it.

These bundles overlap in shared engine/input files; do not add their totals as an application-storage metric. Manifest bytes include code/proof artifacts and are not compression denominators. They contain company inputs and are for local reproduction, not publication permission.

## Runnable verification

```sh
.venv-data/bin/python -B -m unittest engine.tests.test_live_query engine.tests.test_live_server -q
node --test app/checks/live-client-binding.test.mjs
.venv-data/bin/python -B -m engine.jrc --verify artifacts/jrc-baseline-v1.json
.venv-data/bin/python -B data/experimental/lead/smoke_bundle.py jrc
.venv-data/bin/python -B data/experimental/jrc-standard/study.py --verify data/experimental/jrc-standard/retained.json
```

Regenerate manifests with engine.package, engine.package_live, engine.package_jrc and engine.package_control after the corresponding report/code/run changes. Current package functions verify their inputs before inventory. Experience coordination and adoption details are in engine-experience-handoff.md and the separate live/JRC/strong/spatial review documents.

Next lead work: review Galileo's bounded proof fix, reconcile independent audits, regenerate final inventories, and support integrated live/native-source QA. Avoid additional broad research or performance tuning during these acceptance gates.

## Independent audit update

Feynman now independently confirms JRC J1/J2 closure and the46-file no-tile byte-identical lifecycle. The canonical JRC inventory has been regenerated after interface changes and the lead repeated that lifecycle successfully. Spatial membership, allfiveflags and15witnesses also pass independent Fraction clipping; the educational artifact now records that audit acceptance. Defaultcenterquery unchanged.

Strong-control hardening remains in progress for six reproduced semantic inconsistencies. Correction to the earlier dependency note: differing_fields is imported from engine.benchmark, already guarded. The alleged missing export.py dependency was a lead mistake, independently identified and retracted. Do not treat it as an unresolved defect.
