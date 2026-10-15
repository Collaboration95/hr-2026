# JRC companion experience plan

Status: preparation only. Read the draft `engine-jrc-interface.md`, worker task and acquisition report on 13 October 2026. No accepted companion artifact has been loaded or represented as available in the application.

## Product boundary

Keep the existing Hansen plot map, annual timeline, source/compact proof and measured experiment intact. Add an optional **2020 baseline observation** section for the same selected plot only after the engine lead accepts the independently checked JRC export. A separate panel is preferable to switching the existing map into another source while leaving a misleading annual timeline or Hansen proof button beside it.

The companion should answer what the JRC v4 source classifies under its own query. It must not produce a fused deforestation, legal forest or compliance flag. It is not a substitute for the supplier's historical analysis or missing mitigation file.

## Display decisions

- Label the source as **JRC Global Forest Cover 2020 · v4**. Reference year 2020 and version v4 are separate concepts. Preserve the metadata-date/report-link caveat in provenance rather than silently choosing one date.
- Use the companion's own native grid and affine transform for any cell footprints. Row/column IDs refer to the JRC chip. Do not use Hansen cell indices, resample into its grid, or imply coincident native cells.
- Show raw class **0 — Non-forest** as a known mapped class when validity/coverage support it. The official QML's transparency is not nodata. Class **1 — Forest** is a mapped source classification, not a legal conclusion.
- Unknown coverage, invalid masks and missing bands are separate from class 0. Present selected/valid/unknown cell counts and reasons adjacent to analytical values.
- Suggested signal copy: true → “Mapped forest class observed”; false → “No mapped forest-class cells under this query”; null → “Baseline observation unknown.” The false branch requires complete known selected support; partial absence remains unknown.
- Counts from the two native grids are not comparable area units. Never add Hansen and JRC cell counts or infer hectares/percent plot area from them. Supplier-declared hectares remain a separately labelled declaration.
- JRC source/compact comparison and benchmark belong to the companion. Do not extend the retained Hansen 8.59% measurement to it or sum asymmetric storage totals. A future combined footprint requires an engine-defined accounting method that counts shared inputs once.

## Consumer gate

The existence of a worker-written JSON file is insufficient for integration. Wait for the engine lead's accepted artifact and successful fresh positive/negative verification. Then inspect its actual envelope, pin the implemented schema, copy it without altering canonical data, and add a separate runtime loader.

The loader should check schema/query version, exactly matching plot IDs and geometry hashes against the already accepted Hansen envelope, the JRC grid/transform, explicit class domains, tri-state rules and full actual source/compact result equality. It must preserve valid zero and reject a contradictory success flag. A missing/invalid optional companion must not erase the accepted Hansen evidence or turn an unavailable baseline into a no-forest result.

No authenticity claim follows merely from a self hash. Engine verification owns source pixels, masks, actual store files, full round-trip and measured-run binding. UI validation checks the internally consistent frozen response and source association.

## Bounded integration sequence

1. Receive engine acceptance and inspect the exact artifact, receipts, cell-record shape, benchmark scope and limitations.
2. Add a separate read-only asset copy and validated loader. Keep main Hansen artifact and experiment unchanged.
3. Render a plot-specific baseline section with source version, class counts, support, an optional native-cell mini-map/table, and a companion receipt/proof disclosure. Make all displayed values accessible without a pointer.
4. Check a valid class-0-only plot, a class-1 witness, incomplete support without a witness, incomplete support with a witness, missing band, no selected centers and contradictory equality. Artificial controls stay clearly separated from real plots.
5. Verify keyboard/mobile layout and that navigating the main proof still explicitly refers to Hansen. Recheck the portable browser suite after the new source is integrated.
6. Update the demo narrative only with accepted results. Present the two source questions separately; make no legal or same-area inference.

The design intentionally contains no preliminary source-only plot counts, unavailable layer controls or claimed JRC measurements. Those enter the product only through the accepted companion.

## Completed worker handoff reviewed; acceptance still pending

The completed worker report now specifies a separate compact record collection at `plot.evidence.cells`, with `{row,col,value,valid}` and `index_origin`; shared grid information is in `native_grid` and the dataset. Comparison uses `equal`, `independent_oracle_equal` and `mismatch_fields`. Receipt and measured identities are separate from Hansen.

A read-only consumer association check found matching IDs, exact parsed geometries and supplied geometry hashes for all 17 candidate/main records. This is an association check only, not engine acceptance or independent source/codec verification. The companion has not been copied into app assets.

Source wording must also explain that JRC “Non-forest” does not mean no tree canopy: its source definitions differ from Hansen canopy/loss. Exact release date remains unavailable; reference year, version, citation/publication year and observed HTTP Last-Modified must not be collapsed into one invented date.
