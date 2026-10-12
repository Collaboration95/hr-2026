# Local company sample audit

Inspected locally on 13 October 2026. The audit reads only the two files under
`data/company-sample/2026-10-12/`; it does not upload or modify them. Reproduce
the machine-readable results with `python3 scripts/inspect_company_sample.py`.
The script uses only the Python standard library. Its output is
[`company-sample-audit.json`](company-sample-audit.json).

## Pair structure and identifiers

The CSV contains 17 data rows and 35 columns. The GeoJSON is a FeatureCollection
of 17 Polygon features. `a3_plot_id` in the CSV matches `ProductionPlace` in
the geometry file one-to-one: all 17 IDs match, with no repeated IDs, missing
geometries, or unjoined features. The IDs are P-0001, P-0003 through P-0006,
P-0008 through P-0011, and P-0013 through P-0020. Thus the “17plots” pair is
internally consistent despite gaps in the numbering; the absent P-0002,
P-0007, and P-0012 are not missing records unless some external manifest says
they were expected.

Every CSV column has at least one nonblank value in this sample. Commonly
constant fields include factory RG1, lot 200001, processing period
2024-09-04 to 2024-09-06, harvest date 2024-09-16, supplier D001, the named
Hansen 2021–2023 loss layer, and the final status fields. Variable fields include
plot ID and area (17 distinct values), supply-chain type (3), deforestation
analysis result (2), mitigation result (2), reference/link (5), and plot dry
weight and quota (8 values each). The JSON contains per-field distinct value
counts and exact value distributions so the full schema can be reviewed without
duplicating a large table here.

## Geometry and location

All 17 features are single-ring Polygons with closed rings, nonzero area, and no
proper self-crossings under the script's checks. These checks are deliberately
limited; they are not a complete OGC geometry-validity certification. There is
no explicit `crs` member. Under the GeoJSON convention, coordinates are WGS 84
longitude/latitude decimal degrees. Bounds are 98.772429–99.080292° E and
8.431179–8.581888° N. The extent is consistent with the 10N_090E tile-area
assumption and appears to exclude Songkhla. This is a sample-coverage
observation only. The CSV's Surat Thani, Chai Buri, Thailand labels were not
independently checked against administrative boundaries.

Each feature has a declared `Area` matching CSV `a7_size_of_plot_ha`. An
independent spherical area approximation from the outer ring is 0.12%–1.19%
higher than the declared value (mean absolute percentage difference 0.59%).
For example, P-0014 is declared as 0.53 ha and calculates to about 0.5363 ha;
P-0005 is 20.07 ha declared and about 20.1674 ha calculated. This small,
consistent difference can arise from rounding, measurement method, or source
geometry; it is a review note, not proof of a bad polygon or incorrect declared
area. Use an appropriate projected CRS and documented area method if precise
area comparison becomes a project requirement.

Separately, the CSV's declared `a7_size_of_plot_ha` and GeoJSON's declared
`Area` were compared numerically after joining by plot ID. All 17 pairs are
equal; there are no missing or mismatched declared area values between these
two files. This equality is distinct from the geometry-derived estimate above.

## Dates and supplier-declared review leads

The script parses every processing-range endpoint and harvest date as a real
calendar date. All 17 rows parse: processing is 2024-09-04 through 2024-09-06,
and stated harvest is 2024-09-16. Processing therefore precedes harvest in all
17 rows. This needs semantic clarification about what “processing” and
“production harvest date” mean; the ordering is not classified as an error.
The cited tree-cover-loss layer spans 2021–2023, which is temporal context for
review, not a contradiction by itself.

Five rows (P-0003, P-0005, P-0008, P-0010, P-0013) state “Indication of
deforestation” using “Hansen Tree Cover Loss 2021-2023,” and record on-site
verification with evidence. Each nevertheless declares “Deforestation-free”
and “Compliant” for EUDR. This pattern is an excellent evidence-review demo:
show the original signal, mitigation declaration, linked reference, and final
declared decision together, then ask what evidence supports resolving the
signal. It does not establish a violation, falsity, or legal status. These are
supplier-record declarations, not independently checked satellite findings or
legal determinations.

The reference values are generic-looking identifiers (`hyperlink-RG1-P-0002`,
`...P-0004`, `...P-0005`, `...P-0006`) rather than accessible links in the
sample. Notably, P-0003 points to a P-0002 reference although P-0002 is not one
of the sample plots. That may be a valid external evidence key, a cross-plot
reference, or a placeholder; resolve its meaning before treating it as a broken
reference. P-0005 and P-0003 share the P-0002 reference. The JSON preserves the
exact references and associated declarations.

## Interpretation and next evidence questions

Treat as data-quality/review prompts: the five indication-to-final-status
transitions; the unavailable or opaque reference keys; the declared-vs-derived
area differences; and the distinction between the 2021–2023 analysis period and
2024 harvest. None is itself a demonstrated source error or environmental
violation. The apparently uniform “no indication of non-compliance” declarations
across environmental, labor, land, and EUDR fields should also be understood as
reported values, not verified facts.

For a useful demo, ask the data owner what evidence and decision rule underpin
the five final statuses, what the reference keys resolve to, what area method
produced the declared hectare values, and whether P-0002/P-0007/P-0012 are
intentionally outside this 17-plot extract. Keep the supplied values visible
alongside any interpretation and label unknown evidence as unknown.

## Source integrity

The reproducible JSON records byte sizes and SHA-256 hashes. Both files were
also compared read-only with the exact user-supplied attachment paths recorded
in `docs/sources/manifest.json`; both SHA-256 values match exactly, confirming
byte-identical copies at the time of comparison. The script skips an attachment
comparison when that local attachment path is unavailable, so it remains
portable to another machine:

- `200001-17plots-valid_2025-08-02T09_11_12Z.csv`:
  `43b47916d4900d4bf2f86a8a3ca3ee107f22b1fb80702174bbb9b55403c0fca2`
- `200001-17plots-valid.geojson`:
  `8922eef5040120b180a86f6002f52e090ee9bb8273c3c1cf71f984b68648662b`
