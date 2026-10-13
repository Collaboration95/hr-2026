# Additional Sol worker — native JRC v4 baseline subsystem

**Decision:** implement a separate native-grid JRC2020v4 observation/codec/evidence companion. Do not change the accepted Hansen query/codec/benchmark or infer legal compliance. This is a bounded useful second source, not a resampled fusion. Master proxy may dispatch a Sol high worker. No extra leads, Git mutations, private uploads/publication/cloud spend, or source-file edits.

## Ownership

Write only `engine/jrc.py`, optional `engine/jrc_*.py`, `engine/tests/test_jrc*.py`, `artifacts/jrc-baseline-v1.json`, `artifacts/jrc-stores/`, `data/experimental/jrc-engine/` (new files), and `docs/lab/engine-jrc-report.md`. Read but never modify acquired files under data/experimental/jrc/, lead semantic downloads, existing core/codec/oracle/proof/benchmark/export files. Lead owns final companion integration and engine/package.py. Target first artifact/tests within30–45minutes, then hardening/measurement. Report actual blockers promptly.

## Actual inputs and source semantics

Read docs/lab/engine-data-W4.md and data/experimental/jrc/provenance.json. Official v4 source197739699bytes and native chip46238bytes acquired; chip shape1809rows×3695columns,6684255pixels, EPSG4326 step1/12000degree, nodataNone. Source and chip hashes in provenance. Full source is optional cache for normalruntime, required for your independent readbackcheck. Do not rerun acquisition script (it rewrites provenance/timestamp); inspect immutable files.

Lead fetched official version-specific symbology and XML successfully after W4 handoff:

- `data/experimental/lead/jrc-semantics/JRC_GFC2020_V4.qml`, from `https://forobs.jrc.ec.europa.eu/GFC/download?output=qgis&type=symbology&version=v4`.
- QML explicitly labels code0 **Non-forest**, alpha0; code1 **Forest**, alpha255. Transparent code0 is a valid class, NOT missing/nodata merely because it is invisible.
- `data/experimental/lead/jrc-semantics/JRC_GFC2020_V4.xml`, from `https://forobs.jrc.ec.europa.eu/GFC/download?type=metadata&version=v4`, labels v4 but carries older2025dates and a v2report DOI. Record this metadata-version inconsistency; do not substitute those dates for the acquired v4release/referenceyear. Use exactv4QML class labels plus currentofficialJRC/catalog product semantics. Official current page says v4technicalreport expectedDecember2026.
- Official product page `https://forobs.jrc.ec.europa.eu/GFC`; catalog `https://developers.google.com/earth-engine/datasets/catalog/JRC_GFC2020_V4`; data catalog `https://data.jrc.ec.europa.eu/dataset/cf7c49ea-8f00-4c5a-bd40-6f25dc341580`.

Code0/1 are mapped product classes; neither is a legal conclusion. Retain all raster masks/rawvalues. Outside-chip or invalid masks are unknown, distinct from valid0. v3 remains unavailable and must not be silently relabelled v4. Product referenceyear2020 is distinct from source release/version2026. Include requireddatasetcitation from acquisitionmanifest. Exact class-label source/hash must accompany metadata.

## APIs and query contract

`load_jrc(root: Path | None=None) -> JrcDataset` dataclass with `values: uint8[H,W]`, `mask: bool[H,W]`, `metadata: dict` including shape, transform(first6coefficients), crs, product/version/referenceyear, source/chip/provenance/QMLhashes. Verify chip/provenance identity/grid; rawvalues must be0or1 even ifmasked. No resampling, thresholding, area conversion or Hansen-grid projection.

`evaluate_jrc(dataset, geometry, missing_band=False) -> dict`:

- select native centers covered by Polygon/MultiPolygon, exterior/hole boundaries included, on **the acquired chip's declared affine lattice**; record this precise querygrid. Use engine.query.select_cells for productionselection if useful. Never reselect on shifted subwindows; source/compact must use identicaloriginalchipgrid.
- selected_cell_count, in_coverage_cell_count, out_of_coverage_cell_count, valid_cell_count, unknown_cell_count; class_counts keys0and1 counting valid observed cells (null only if no valid cells or missingband); mapped_forest_present true if any observedvalid1, false only if n>0 and all selected support known with no1, otherwise null. False means no mappedclass1underquery, NOT a forest/legal finding.
- support complete/partial/none/unavailable; reasons deterministic no_selected_cells,out_of_coverage,band_mask_invalid,no_valid_cells,missing_band asapplicable. Partialpositive stays true; partialno1 staysnull. Missingband disablesanalyticalcounts/flag, keeps selected/coverage diagnostics, unknown=n.
- count cells, nothectares/wholeplotcoverage. Do not multiply or directlycompare JRC and Hansen counts as same-resolution quantities. No combineddeforestationflag or complianceML.

`export_jrc(...) -> dict`/CLI `.venv-data/bin/python -B -m engine.jrc` writes separate `artifacts/jrc-baseline-v1.json`, schema_version `plotline.jrc-baseline.v1`, query_version `jrc2020-centers.v1`, dataset metadata,17plots with plot_id,geometry_sha256,source_result,compact_result,comparison,receipt,evidence; summary and honest measuredcodeccomparison. Use exactoriginalgeometries and IDs, supplierdeclarations remain in mainartifact (do not reinterpret).

Evidence can be compact cell records `{row,col,value,valid}` plus shared nativegrid transform, or GeoJSONcellfootprints if small. Prefer compact records to avoid duplicating~9000cellpolygons. Include allselectedcenters needed for inspectability; outsidecells have value=null/validfalse. Pin whether row/col indexes refer to chip (recommended). LabelJRCdata/referenceyear/versionexplicitly.

## Codec and fair proof

Implement a separate binaryclass codec, never stuffJRC into the threeHansenbands. Test bit-packedclass+mask compressedzstd vs uint8+zstd (levels3/19ifuseful) over the **same full6684255pixelchip**. Chunk/indexmetadata included. Reuse boundedzstdframe validation from corecodecs if appropriate; don't edit it. Preserve raw0/1oninvalidmasks, reject out-of-range values. Include malformed/truncation/padding/shape/masktests.

Baseline is actual reasonablycompressed nativechip plus genuinelynecessarymetadata/provenance; optionalduplicate metadata is separatelyreported, neverdenominatorpadding. Reportallcandidatepayload/index/metadatabytes, chosenstore bymeasuredtotalonlyafterfullroundtripand17exactqueries. Packedbinarymaylose vs sparse TIFF; retainhonestwinner/losers. Do notcount197MBtile-to46KBchipcrop ascodec saving. BenchmarkseparatelyfromHansen; noaggregate8.59%claim mixinglayers. Fullraw/mask equality over6684255pixels and17queryequality required; source uncertainty notcodecerror.

At minimum measure repeatedpreprocess/decode/query timings with explicit scopes/cachewarmness; if feasible ordinaryPythonisolatedcoldprocess/RSS. Keep itbounded, defaultn7warmups2; noUIcost. Content-address result/settings/source/codefingerprints and preserveexperimentalreports. Avoid importing benchmark.run_benchmark becauseits3bandHansencontract isnotthislayer.

## Independent checks and handoff

Independent query reduction/membership on17plots: use W2scalar raycasting helpers or implement scalaroracle independentlyfrom productionselection. SharedGEOSvaliditycheck isallowedbutreportthatlimit. Testsvalid0vsunknown, code1positive, missingmask/band, tiny/no-centers, holes/multipart, partial/outside, exactdecimalboundaries, allrawvalues/masks. Include source-windowpixelANDmaskreadback, notonlyW4's pixelassertion.

Final report names actual artifact/storepaths, bytes/timing/resource methods,17results, class-label evidence, data/codehashes, missingmetadata caveats, and reproduciblecommands. Do NOT modify mainartifact orfrontend. Lead reviews before integration; engine-jrcreport ismasterrelayhandoff.
