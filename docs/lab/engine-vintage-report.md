# Hansen source-vintage study — safe-checkpoint handoff

**Ready for master and Volta. Research stopped at the user's wrap request.** All three historical bands, native chips, comparison outputs, and an independent check were completed before that request. No download remains running. No production, canonical, existing JRC, or Git changes were made by this study. Writes are confined to `data/experimental/hansen-vintage/` and this report.

## Finding

Comparing the preregistered **Hansen GFC 2023 v1.11** against pinned **2025 v1.13**, using the exact 17 supplied geometries and existing `hansen-centers.v1` rule, produced **no changes to 2021–2023 observed counts, annual counts, or period flags**. All 17 current full core results matched `artifacts/demo-v1.json` exactly.

There are 1,048 distinct selected cells. Raw loss codes changed on 47 cells across five plots, entirely from old code 0 to current code 24 or 25. These are later-year additions in the current release. **Historical coverage ends in 2023; old zero does not establish observed absence in 2024–2025.** Historical exported results omit the unsupported future period, contain only 2021–2023 annual counts, and truncate the raw histogram to codes 0–23.

The company's historical release is **UNKNOWN**. This is a hypothetical comparison of one release chosen before values were inspected, not evidence of which release the company used. It does not establish a legal finding, supplier truth, or source accuracy.

## Preregistration and chronology

All times UTC, 13 October 2026. The records are in `preregistration.json` and append-only `chronology.jsonl` under the owned directory.

- **04:11:49:** recorded the single historical choice, 2023 v1.11, all-three-band requirement, unchanged plots, center rule, shared period, budget, and unknown company vintage before historical pixel inspection.
- **04:14:07–04:14:09:** the three official URLs returned HTTP 200 on HEAD; each URL was verified against its archive-published band URL list. First access result arrived within three minutes of preregistration.
- **04:14:09–04:14:24:** all three source files downloaded successfully. No alternative historical release was searched or acquired.
- **04:14:24:** historical decoding began after all three complete source files existed; native chips and acquisition provenance completed.
- **04:16:50:** 17-plot comparison completed.
- **04:18:17:** independent scalar queries and direct original-tile witness checks completed.
- User then requested an immediate safe checkpoint; no new downloads or analytical queries were started after that request.

## Official source and acquisition

Primary documentation: [official 2023 v1.11 archive](https://storage.googleapis.com/earthenginepartners-hansen/GFC-2023-v1.11/download.html) and [official Earth Engine v1.11 catalog](https://developers.google.com/earth-engine/datasets/catalog/UMD_hansen_global_forest_change_2023_v1_11). The archive links published URL lists for each band; copies are retained as `official-*-urls.txt`. The source files use the archive's exact `10N_090E` entries:

```text
https://storage.googleapis.com/earthenginepartners-hansen/GFC-2023-v1.11/Hansen_GFC-2023-v1.11_treecover2000_10N_090E.tif
https://storage.googleapis.com/earthenginepartners-hansen/GFC-2023-v1.11/Hansen_GFC-2023-v1.11_lossyear_10N_090E.tif
https://storage.googleapis.com/earthenginepartners-hansen/GFC-2023-v1.11/Hansen_GFC-2023-v1.11_datamask_10N_090E.tif
```

Full source tiles total **220,781,000 bytes**. Including the three official URL lists, new downloaded response bodies total **220,960,424 bytes**, below the 500 MB cap. Full tiles are in the already ignored owned `raw/` directory. Downloads used temporary `.part` paths and were renamed after exact content-length checks. None remains partial. Three historical chips total **564,520 bytes**.

The source is licensed **CC BY 4.0**: credit `Hansen/UMD/Google/USGS/NASA`, link the [license](https://creativecommons.org/licenses/by/4.0/), and identify the native-grid extraction and lossless recompression. Citation: Hansen et al. (2013), *High-Resolution Global Maps of 21st-Century Forest Cover Change*, Science 342, 850–853, [doi:10.1126/science.1244693](https://doi.org/10.1126/science.1244693).

The archive's stale numeric phrase says loss codes 1–20 while naming 2001–2023; the official catalog explicitly specifies 1–23. The downloaded historical chip contains no loss code above 23. Native geometry is taken from the TIFF, rather than inferred from the documentation's nominal pixel-size wording.

## Grid, masks, and query fidelity

All historical bands have one `uint8` band, EPSG:4326, 40,000 × 40,000 tile dimensions, affine `[0.00025, 0, 90, 0, -0.00025, 10]`, and no nodata value. The outward-aligned source window is `[column=35089, row=5672, width=1233, height=604]`. Chip affine is `[0.00025, 0, 98.77225, 0, -0.00025, 8.582]`, exactly matching the pinned current grid. All 744,732 cells in each band's chip have valid raster masks. Raw values and raster masks were read back exactly against their own historical source windows; no resampling or current-mask substitution occurred.

Historical data were loaded into a separate `Dataset` with explicit product identity and observation end year 2023. The existing core was imported read-only. Selection uses the accepted chip lattice and polygon `covers` on native centers, with no fitted canopy threshold. Both releases selected identical row/column pairs. Every plot has complete support and valid-land counts equal to the selected counts below; unknown and out-of-coverage counts are zero.

Source files, supplied CSV/GeoJSON, core code, current provenance, and canonical demo file hashes were bound and unchanged during comparison. The supplied geometry and supplier records also matched the canonical records. The canonical demo SHA-256 at comparison was `11d5ca337e142dcb6080028f09d5573265dc67e9826e55131aa7515876336555`.

## Per-plot result

All counts below are cells selected by the unchanged center rule. The old/current flag and count refer only to **2021–2023**. Raw transitions describe different source codes, not old-release observations of future years.

| Plot | Selected | Old count | Current count | Old/current flag | Changed raw loss cells | Raw transitions |
| --- | ---: | ---: | ---: | --- | ---: | --- |
| P-0001 | 121 | 38 | 38 | true / true | 0 | — |
| P-0003 | 87 | 0 | 0 | false / false | 0 | — |
| P-0004 | 47 | 0 | 0 | false / false | 0 | — |
| P-0005 | 262 | 0 | 0 | false / false | 18 | 0→24: 7; 0→25: 11 |
| P-0006 | 256 | 0 | 0 | false / false | 18 | 0→25: 18 |
| P-0008 | 27 | 0 | 0 | false / false | 0 | — |
| P-0009 | 28 | 0 | 0 | false / false | 0 | — |
| P-0010 | 27 | 0 | 0 | false / false | 0 | — |
| P-0011 | 42 | 0 | 0 | false / false | 0 | — |
| P-0013 | 25 | 0 | 0 | false / false | 3 | 0→25: 3 |
| P-0014 | 7 | 0 | 0 | false / false | 7 | 0→24: 7 |
| P-0015 | 39 | 0 | 0 | false / false | 0 | — |
| P-0016 | 14 | 1 | 1 | true / true | 1 | 0→24: 1 |
| P-0017 | 9 | 0 | 0 | false / false | 0 | — |
| P-0018 | 34 | 1 | 1 | true / true | 0 | — |
| P-0019 | 15 | 0 | 0 | false / false | 0 | — |
| P-0020 | 8 | 0 | 0 | false / false | 0 | — |

In both releases, P-0001's 38 period events are coded 2022, P-0016's one is coded 2023, and P-0018's one is coded 2021. All other period-year counts are zero. Canopy, datamask raw values, and all band-validity masks are unchanged on all selected cells.

Descriptive only: the five supplier-indication IDs P-0003, P-0005, P-0008, P-0010, P-0013 all retain zero mapped period events under this fixed rule in both releases. Those IDs were not used to choose the release, adjust the rule, fit thresholds, or train anything. This single comparison does not explain or invalidate the declarations.

## Whole-bbox comparison and independent checks

Across 744,732 bbox cells, canopy and datamask have zero raw differences; all three bands have zero validity-mask differences. Loss has **36,925** raw differences: **22,423** code 0→24 and **14,502** code 0→25. Both releases have **43,519** valid-land mapped 2021–2023 event cells. There are zero shared-period membership changes and zero shared-period raw-year changes. These are rectangular AOI counts, not plot area estimates.

The existing independent oracle uses scalar ray casting and scalar counters without importing `engine.query`. All **34** independent query results (17 plots × 2 releases), projected to the supported study output, agree. A separate leak check confirms every historical export has only the target period, years no later than 2023, and 24 raw loss bins.

Four deterministic witnesses were reread as individual cells from all six original source tiles, with all tile hashes checked. Raster values and band masks match the chips, and scalar point-in-polygon membership agrees:

| Witness | Plot | Chip row, col | Center lon, lat | Old → current `[canopy,loss,mask]` |
| --- | --- | --- | --- | --- |
| First selected 0→24 | P-0005 | 562, 483 | 98.893125, 8.441375 | `[89,0,1]` → `[89,24,1]` |
| First selected 0→25 | P-0005 | 557, 483 | 98.893125, 8.442625000000001 | `[89,0,1]` → `[89,25,1]` |
| Unchanged shared-period event | P-0001 | 55, 73 | 98.790625, 8.568125 | `[76,22,1]` → `[76,22,1]` |
| Unchanged zero | P-0001 | 51, 69 | 98.789625, 8.569125000000001 | `[76,0,1]` → `[76,0,1]` |

All three band masks are valid in each witness. Full original-tile indices and evidence are in `independent-check.json`.

## Files, hashes, and reproduction

Owned directory: `data/experimental/hansen-vintage/`.

- `preregistration.json`, `chronology.jsonl`: fixed choice and timing.
- `acquisition.json`: exact URLs, HTTP headers, sizes, SHA-256, native grid, masks, raw histograms, and extraction readback checks.
- `hansen_2023_v1_11_*_sample.tif`: three historical native chips.
- `comparison.json`: separate release metadata, per-plot results, raw transitions, AOI differences, canonical equality, bound code/input hashes.
- `selected-cells.json`: all 1,048 selected cells with old/current raw triplets and masks, limited period membership, and centers.
- `independent-check.json`: oracle checks, direct original-tile witness reads, six-tile hash verification, and future-output leak check.
- `acquire.py`, `compare.py`, `independent_check.py`: reproducible local scripts using existing dependencies.

Historical source tile SHA-256:

```text
treecover2000 56cdc0cda4ccb07ad1513593b4bd13b0dc8577ab1510c986c98fc89aaa807366
lossyear      a0561b8ae938b5ca18ebed5b4bc24e2701b2a83028e5c2b44121b916e201da1b
datamask      94b909dad3069ed5afe3f4b7c252dff7766382758a1a11f768293b053e6fcb7a
```

Historical chip SHA-256:

```text
treecover2000 f69b3f59e943a9830cd4076fa71c8f09c301de6f6635a683db536c5d956fdfcc
lossyear      12c3c1ed9ca108b6ba837887b1d538ec1fe4d3e9c8e298466509d711798ec14f
datamask      041e62e410f908c47a7c48fe16f8884460ea69d5103fc753bdb5bec9a044d458
```

From the repository root, with the completed local cache:

```sh
.venv-data/bin/python -B data/experimental/hansen-vintage/acquire.py
.venv-data/bin/python -B data/experimental/hansen-vintage/compare.py
.venv-data/bin/python -B data/experimental/hansen-vintage/independent_check.py
```

`acquire.py` verifies an existing complete manifest/cache; on a fresh empty acquisition directory with the preregistration present, it obtains the three published archive URLs, downloads the files, and extracts the chips. **Portability limitation left at the requested checkpoint:** if the acquisition manifest is retained but ignored raw files are absent, that script currently fails verification rather than automatically restoring the cache. The exact source URLs and hashes above identify the files to restore under `raw/`. The independent check also needs the pre-existing current original tiles in `data/public/raw/`; the comparison itself needs only the historical and current chips. No further cache-restoration feature or rerun was attempted after the wrap request.

Completed scope is this single vintage pair, these 17 unchanged polygons, and the fixed shared-period center rule. No other release, alternative spatial rule, historical company-source claim, legal conclusion, production integration, or UI change was attempted. Master and Volta can review the negative shared-period result and the explicit later-year raw-code witnesses from the saved files.
