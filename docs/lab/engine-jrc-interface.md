# JRC companion interface v1 — separate native source

Canonical target `artifacts/jrc-baseline-v1.json`, schema `plotline.jrc-baseline.v1`, query `jrc2020-centers.v1`. Worker assignment is engine-jrc-task.md. Lead acceptance: the refreshed guarded companion passes28tests and clean46file bundle verify→ordinary export→verify byte-identically without the fulltile. Independent xhigh J1/J2 follow-up now passes fresh positives, original wrong-sample rejection and byte-identical no-tile lifecycle. The separate native-grid source view may integrate under this contract; do not replace acceptedHansenmeasurements or imply a combinedlegal result.

Dataset: product JRCGlobalForestCover2020, versionv4, referenceyear2020, own1809×3695EPSG4326grid/transform, pinned source/chip/provenance/class-label hashes and citation. Raw0=Non-forest and1=Forest per officialv4QML. Known0 is not unknown. Coverage/invalid masks/missingband drive unknown separately. The v4XML carries olderdates/reportlink; preserve metadata caveat.

Plot IDs and geometry_sha256 bind to main17plots. Each contains source_result/compact_result/comparison/receipt and native evidence. Result fields: selected_cell_count, in_coverage_cell_count, out_of_coverage_cell_count, valid_cell_count, unknown_cell_count, class_counts (`0`,`1`, nullable when no valid data), mapped_forest_present (true/false/null), support and unknown_reasons. Anyknown1→true; no1→false only with complete known selectedsupport; otherwise null. This is a mapped-class observation, not legal forest presence/absence or compliance.

Evidence actual form: `evidence.cells` contains `{row,col,value,valid}` records plus `evidence.index_origin`; shared `native_grid` holds shape/transform/CRS. Indexes refer to JRC chip. Do not reuse Hansenrow/col or transform. Keep source selector/legend explicit. Do not compare or add counts from the different grids as common-area units. No resampling and no derived deforestation/complianceflag. Display bothsourceperiod/version labels: JRCreference2020/v4 and Hansenobservationyears/latest2025v1.13.

Lead independently re-read JRCsourcewindow and compared pixels ANDmasks against acquiredchip; both exact. Lead source-only computation is data/experimental/lead/jrc-source-check.json; independent worker queries and full codec arrays now agree. P-0001 has554class1cells among1083selectedJRCcenters; P-0003 has793selectedclass0cells. The complete17plot cohort selects9511JRCcenters:8957validclass0 and554validclass1, with onlyP-0001mapped-class1present. These are independently checked mapped observations, not supplier findings.

Hansenacceptedbenchmark/store remains immutable. JRCbenchmark will be separate and same-JRC-AOI; any future combinedstorageview must countsharedinputs once and preserve bothnativegrids. No automatic8.59%claim extension toJRC.


## Actual JSON layout and consumer checks

Top-level keys are `schema_version`, `query_version`, `dataset`, `native_grid`, `store`, `full_chip`, `plots`, `summary`, `benchmark`, `limitations`, `content_sha256`. The benchmark is a separate JRC run, or null for an explicitly metric-free export. `dataset` retains citation, class definitions/styles, reference year, version, input identities and the XML discrepancy. `full_chip` binds all6684255 raw values and mask bits, plus exact metadata.

Each plot includes exact `geometry`, `plot_id`, `geometry_sha256`, both result dictionaries, `comparison`, `receipt`, and `evidence`. `comparison.equal` and `independent_oracle_equal` are claims to check alongside result equality and receipt binding, not a substitute for checking values. Use strict types: nullable booleans are distinct from0/1 and missing fields. A false integrity result must not display as verified. Backend `python -B -m engine.jrc --verify artifacts/jrc-baseline-v1.json` is the recomputation gate. Frontend integrity checks cannot independently prove source accuracy.

P-0001 representative result (identical source and compact):

```json
{
  "selected_cell_count": 1083,
  "in_coverage_cell_count": 1083,
  "out_of_coverage_cell_count": 0,
  "valid_cell_count": 1083,
  "unknown_cell_count": 0,
  "class_counts": {"0": 529, "1": 554},
  "mapped_forest_present": true,
  "support": "complete",
  "unknown_reasons": []
}
```

Its first native evidence record is `{"row":151,"col":205,"value":1,"valid":true}`. For a record `(r,c)`, compute corners from the shared original affine at `(c,r)`, `(c+1,r)`, `(c+1,r+1)`, `(c,r+1)`; compute the center from `(c+0.5,r+0.5)`. Use the JRC affine, not Hansen or a shifted-window affine. Grid cells can extend beyond the plot because the selection predicate concerns their centers.

Suggested consumer wording: “JRC mapped forest class, reference2020 · v4”. Valid0 is “Mapped non-forest”; missing/invalid/outside is “Unknown”. The official style makes0transparent, but class0must remain inspectable. No year selector should imply this single2020layer contains annual observations. Supplier rows remain the unchanged main contract.

## Local packaging

`python -B -m engine.package_jrc` creates `artifacts/jrc-bundle-manifest.json` from a currently valid bound companion. It inventories all8 measured candidate stores, the chip and required provenance/style/XML, exact plot inputs, source-code dependencies, run/identity archives and report/contract. The large acquisition tile is excluded. Current review inventory supports verification and byte-identical ordinary regeneration without that tile. New measurement requires explicit --measure and the fulltile. Regenerate the manifest after report/code updates. No staging, publication or private-data sharing is authorized by this manifest.


## Refreshed accepted companion binding

Experiment `exp-bfd3067040ae3fb83331667fba2ece195e9372893c81ac1930edbdfc68444f3a`; run `run-5b318b210c244c60458942f67281a8abc6f8ebcc2b3949effc12feb3013cd261`. Artifact fileSHA256 `933b3d302b8ec961444a7f252f74deb87f3f186f1b7f8d5bcb5012cb55658f71`; embedded contentSHA256 `c13127c9f6d8654a1dae0d66945c981bfc340b20467124dd2e55829d79d754a3`. Keep filehash andcontenthash distinct. Canonical outputremains artifacts/jrc-baseline-v1.json.

A separately reviewed standardGeoTIFFcontrol is19901bytes vs21459retainedcustom,7.26%smaller, with slowerfull-load+query andhigherRSS in its ownstudy. Therefore anyJRCcustomstorageclaim must say “versus the suppliedDEFLATEchip”; never implycustombeatsoptimizedstandardformats. The sourceviewdoesnotneed toswitch its verifiedcodec or mixbenchmarks. Engine-jrc-standard-review.md records the additivecomparison.
