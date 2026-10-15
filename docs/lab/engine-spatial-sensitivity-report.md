# Spatial-rule sensitivity — bounded research handoff

**Complete; awaiting lead science review.** On the same 17 supplied polygons, strictly positive footprint overlap adds 337 native-cell memberships and changes five period flags compared with accepted center inclusion. Source/compact results remain exactly equal under **both** rules. This rule change creates **no 2021–23 mapped-loss signal on any of the five supplier-indication IDs**.

Addressed to master `01a130e9-aaf5-7a53-9cff-96d579f69b35` and science lead Volta `01a132f8-f774-7b32-9eef-2c0f572c1df0`. No callable agent/thread messaging tool exists in this session; this shared report and `verification.json` are the handoff, not a claim that messages were delivered. All implementation and verification were performed here without delegation. Fast mode has no callable control and is not claimed.

## Frozen experiment and method

Read `AGENTS.md`, `README.md`, the full spatial assignment, research agenda, interface v1, accepted `engine-report.md` (the task's `acceptedengine-report` means this file), printed/spoken/kickoff SystemEarth guidance, sample audit, acquisition guidance and actual source/query/store code.

Inputs are unchanged supplier polygons/CSV and Hansen **2025 v1.13** chips: 604 × 1233 native EPSG:4326 cells, affine `[0.00025, 0, 98.77225, 0, -0.00025, 8.582]`. Immutable retained store:

`artifacts/stores/exp-0109a8d6c4782217871315b92c63a971d11ebd164585c80981f24c55b4f68fea/separate_zstd_l19`

Retained run: `run-71a5b90b05bdce363044d8e232ae33d20b31f3868a6f5ba50bf61372b98194a9`. The CLI rejects a changed retained identity. No re-encoding was needed.

- `center_covers` uses accepted `engine.query.select_cells`: boundary-inclusive coverage of native cell centers.
- `positive_area_overlap` uses GEOS intersection area **strictly greater than zero**. Footprints come directly from the original chip affine and global chip row/column: west/east use `c + col*a` and `c + (col+1)*a`; north/south use `f + row*e` and `f + (row+1)*e`. No translated window origin controls selection.
- Point/edge-only contact is recorded separately and excluded from analytical support. Holes/multipart are preserved. The scan is not clipped to chip coverage; spare candidate margins only prevent enumeration loss from inverse rounding. No tolerance, buffer, simplification, resampling, canopy threshold or declaration fitting is used.
- Both rules use unchanged `summarize_selected`: valid-land histograms include canopy 0–100 and loss code 0–25. Outside/nodata/invalid-mask support remains unknown. A witnessed loss stays true with partial support; absence requires complete selected support and valid land to become false.

Complete raw arrays, masks and metadata are compared exactly, then selected arrays and full query dictionaries are compared exactly per rule/plot. JSON comparisons preserve true/1 and false/0 distinctions. Center outputs also match production `evaluate` and canonical `artifacts/demo-v1.json` source/compact results; exact original geometry and supplier strings match that export.

## Real cohort — 17 original polygons

All **2,234,196 raw values**, **2,234,196 validity bits**, and complete metadata match original versus compact; **zero mismatches**. Both rules have **17/17 exact query and selected-array matches**. Canonical center results match **17/17**. Scalar center membership matches **17/17**; area versus DE-9IM membership has **zero discrepancies**.

Center selects **1,048** plot/cell memberships; overlap selects **1,385**. These are per-plot memberships, not deduplicated regional area. There are **0 center-only**, **337 overlap-only**, and **0 zero-area-touch** memberships. Every selected real cell is known valid land: per plot/rule, valid-land and in-coverage counts equal selected counts; datamask-zero, water, invalid-mask, unknown and outside counts are all zero. Both rules have complete support on all 17 plots. Full diagnostic counts, histograms and cellsets are in `results.json`.

Pairs below are **center / overlap**. Period columns count observed valid-land loss cells. A positive count means true; zero means false here because real support is complete.

| Plot | Selected cells | 2021–23 loss cells | 2024–25 loss cells | Changed flag |
| --- | ---: | ---: | ---: | --- |
| P-0001 | 121 / 149 | 38 / 38 | 0 / 0 | — |
| P-0003 | 87 / 114 | 0 / 0 | 0 / 1 | 2024–25 false→true |
| P-0004 | 47 / 66 | 0 / 0 | 0 / 1 | 2024–25 false→true |
| P-0005 | 262 / 314 | 0 / 0 | 18 / 29 | — |
| P-0006 | 256 / 301 | 0 / 0 | 18 / 29 | — |
| P-0008 | 27 / 43 | 0 / 0 | 0 / 0 | — |
| P-0009 | 28 / 47 | 0 / 0 | 0 / 0 | — |
| P-0010 | 27 / 39 | 0 / 0 | 0 / 0 | — |
| P-0011 | 42 / 59 | 0 / 0 | 0 / 0 | — |
| P-0013 | 25 / 40 | 0 / 0 | 3 / 9 | — |
| P-0014 | 7 / 16 | 0 / 4 | 7 / 8 | 2021–23 false→true |
| P-0015 | 39 / 59 | 0 / 6 | 0 / 0 | 2021–23 false→true |
| P-0016 | 14 / 28 | 1 / 5 | 1 / 3 | — |
| P-0017 | 9 / 27 | 0 / 0 | 0 / 0 | — |
| P-0018 | 34 / 46 | 1 / 1 | 0 / 0 | — |
| P-0019 | 15 / 19 | 0 / 0 | 0 / 3 | 2024–25 false→true |
| P-0020 | 8 / 18 | 0 / 0 | 0 / 0 | — |
| Total memberships / events | 1048 / 1385 | 40 / 54 | 47 / 83 | 5 plot-period changes |

Mapped-loss-positive plot counts increase **3→5** for 2021–23 and **5→8** for 2024–25. Five distinct plots change one period flag each. No center-only counterexample was found; the script records an investigation and blocks its positive gate if one appears rather than assuming the subset property.

## Native witnesses and descriptive declaration comparison

`witnesses.json` contains **all 15 added valid-land loss cells responsible for the five changed flags**. Each witness includes plot ID, exact original polygon and geometry hash, global chip and original source-tile indices, full footprint, center, raw canopy/lossyear/datamask, every band-validity bit, both inclusion decisions and the dimension-2 cross-check.

| Changed plot/period | Witness count | Representative chip row,col | Raw canopy / loss code / datamask | Angular cell fraction |
| --- | ---: | --- | --- | ---: |
| P-0003, 2024–25 | 1 | 7,12 | 83 / 25 / 1 | 0.007428989625 |
| P-0004, 2024–25 | 1 | 109,208 | 100 / 25 / 1 | 0.095801801930 |
| P-0014, 2021–23 | 4 | 447,1182 | 76 / 23 / 1 | 0.151117053407 |
| P-0015, 2021–23 | 6 | 358,1228 | 100 / 22 / 1 | 0.332204963970 |
| P-0019, 2024–25 | 3 | 281,1183 | 94 / 25 / 1 | 0.105119415302 |

For example, P-0003's center `[98.775375, 8.580125]` lies outside the plot. Its footprint corners are `[98.77525, 8.580250000000001]`, `[98.7755, 8.580250000000001]`, `[98.7755, 8.58]`, `[98.77525, 8.58]`. A small positive intersection selects the whole native cell under overlap. Loss code 25 and all three valid masks produce a witnessed 2025 signal; center selection omits the cell. P-0014 also has a changed-period witness at row447/col1183 with fraction only `0.00030992448793`, illustrating the absence of a minimum overlap threshold.

Fractions are **dimensionless angular-area ratios in geographic coordinates**, not surveyed area/hectares or fraction-weighted loss area. JSON retains full precision; table values are rounded only for display.

Supplier-indication IDs **P-0003, P-0005, P-0008, P-0010, P-0013** each remain **false with zero 2021–23 loss cells under both rules**. This spatial change does **not explain those five supplied 2021–23 indications**. P-0003's later-period change does not explain its earlier-period declaration. Supplier strings are descriptive context, not ground-truth labels; neither method was optimized for agreement.

## Synthetic fixtures — separate denominators and independent checks

`fixtures.json` contains **24 valid synthetic cases and two rejected geometries**, with **zero real plots**. It never enters the 17-plot denominator. All cases pass explicit analytic expected cellsets, exact scalar membership and full scalar reduction comparisons.

- Dyadic cases cover tiny/no-center plots, exact cell equality, point-only/edge-only contact, exterior/hole-boundary center coverage, an exact-cell hole, hole interior, multipart islands, a diagonal triangle and a thin diagonal sliver.
- Outside support is retained. One parcel has complete center absence=false but overlap adds an outside cell, making absence=null. Another keeps witnessed 2021 loss=true despite that unknown cell; its unwitnessed later period is null. Outside-only support remains unknown.
- Invalid masks, datamask-zero nodata, water, mixed available/unknown support and a missing band are tested. Raw masked/nonland loss codes remain intact and cannot vote in analytical histograms.
- Five fixtures use the original native decimal affine: exact cell equality, tiny overlap, exact center boundary, and adjacent representable boundary values on either side. All preserve the global affine. The regression control records longitude `98.772625` versus reassociated window longitude `98.77262499999999`; only the former is selected at the exact boundary. The shifted coordinate is never used analytically.
- Collinear zero-area and self-crossing polygons are rejected under both rules.

Area is cross-checked against **DE-9IM interior intersection dimension 2**, a distinct predicate, but both share **GEOS 3.13.1 topology/geometry**, not independent implementations. Center membership also uses exact-rational scalar ray casting. Synthetic footprint membership/contact additionally uses independent **Fraction-based Sutherland–Hodgman rectangle clipping, shoelace area and segment-contact checks**, limited to these simple convex rings/holes/islands. Analytic areas bind the oracle: 1/64 for the tiny plot, 1/2 for the diagonal triangle, 1/256 for the full sliver, and zero for pure contact/hole-only cells. A test disables GEOS membership/area calls while exercising those scalar primitives.

GEOS remains shared for topology/bounds; native coordinate construction is shared and bound by analytic dyadic fixtures. Fractions represent supplied binary coordinates, not an ideal surveyed parcel. Native decimal GEOS operations remain subject to machine precision; no tolerance changes the rule. Real reductions use the accepted helper; synthetic full-result reduction is independent. This is bounded evidence, not arbitrary-input geometry certification.

## Commands, proof gates and fingerprints

From repository root, with existing dependencies:

```sh
.venv-data/bin/python -B data/experimental/spatial-sensitivity/run_checks.py
```

It ran these actual commands sequentially; all exited **0**:

```sh
.venv-data/bin/python -B data/experimental/spatial-sensitivity/study.py
.venv-data/bin/python -B data/experimental/spatial-sensitivity/fixtures.py
.venv-data/bin/python -B -m unittest discover -s data/experimental/spatial-sensitivity -p 'test_*.py' -v
```

Final recorded checks completed **2026-10-13 03:58:06 UTC / 11:58:06 SGT**. **29 test methods passed**. Controls inject an unselected raw-value discrepancy, selected mask discrepancy, failed scalar-membership check and input fingerprint drift entirely in memory; each blocks a positive fidelity claim. Boolean/integer confusion is rejected, output paths cannot escape the owned directory, immutable input hashes remain unchanged and reruns are deterministic. Actual argv/stdout/stderr/exit records and final hash checks are in `verification.json`; timestamps are execution records, not query benchmarks.

SHA-256 bindings (JSON content hashes exclude their own `content_sha256` field):

| Binding | SHA-256 |
| --- | --- |
| Original GeoJSON bytes | `8922eef5040120b180a86f6002f52e090ee9bb8273c3c1cf71f984b68648662b` |
| Original CSV bytes | `43b47916d4900d4bf2f86a8a3ca3ee107f22b1fb80702174bbb9b55403c0fca2` |
| Research/core code bundle | `80486c8628ed98d1ba73addcf310a03ea711e74536371f8240514b91470e3d38` |
| Center rule definition | `109a8477b515ab8711dc51b5ae87e780412ae44d960bdf7f8cd0b3a877750b84` |
| Overlap rule definition | `ef45ab33f931bff2a9ceb6ee5f55b5192f608a92099185fbecf818f38d84ccdd` |
| Real result content | `37ddeb70c8dfd7c0b6f8169bb1063232510ac4cfd5a26f935c73f24cd276e045` |
| Synthetic fixture content | `bb884dc40689b5386e46ebad7f4f41224b7ef45b853158e176572640dcc0c8bc` |
| Recorded verification content | `42ca1206ec1bb0e41fe0ee4fd8a2608709f4045eb6e16d7db3def57ea97049be` |

`results.json` additionally records each input/source/store/canonical/code file's byte count and hash, exact per-plot geometry hashes, full source metadata and rule definitions. Runtime: Python3.14.7, NumPy2.5.4, Rasterio1.5.2, Shapely2.1.2. All ten input file fingerprints passed the final read-only check.

Exact written files:

- `data/experimental/spatial-sensitivity/study.py`
- `data/experimental/spatial-sensitivity/fixtures.py`
- `data/experimental/spatial-sensitivity/test_study.py`
- `data/experimental/spatial-sensitivity/run_checks.py`
- `data/experimental/spatial-sensitivity/results.json`
- `data/experimental/spatial-sensitivity/witnesses.json`
- `data/experimental/spatial-sensitivity/fixtures.json`
- `data/experimental/spatial-sensitivity/verification.json`
- `docs/lab/engine-spatial-sensitivity-report.md`

## Interpretation and adoption recommendation

The five flag changes are **intentional spatial-rule sensitivity**, **not encoding error**, and **not the earlier shifted-window 1ULP implementation bug**. Exact source/compact agreement establishes preservation under each declared rule, not satellite accuracy or environmental ground truth. Supplier historical data vintage and inclusion rule remain unknown. **Neither alternative is established as the company rule. No legal, regulatory or supplier-compliance conclusion is made.**

Retain this as additive research for lead review. Keep accepted center selection as the production default; any future alternative must identify its rule explicitly and preserve the unknown-support contract. The negative supplier-indication result rules out this particular inclusion change as an explanation on these pinned inputs, while native witnesses demonstrate that rule choice can affect small-plot screening.

No core/app/canonical/source/other-research file was edited. No Git mutation, dependency installation, download, external message, private upload/publication, cloud action or extra agent was used.
