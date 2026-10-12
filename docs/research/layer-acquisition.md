# Public layer acquisition notes

Research and acquisition: **13 October 2026**. Company sample: `data/company-sample/2026-10-12/200001-17plots-valid.geojson` and its joined CSV. These are reported supplier production-place geometries; this note does not establish legal parcel status or historical boundary validity.

## Geography and sample fit

All 17 features were inspected. Their combined WGS84 bounds are **98.772429–99.080292°E, 8.431179–8.581888°N**. The CSV labels the area Surat Thani / Chai Buri, Thailand. Hansen's global tile names identify the north-west corner: this sample is in `10N_090E` (10°×10° tile from 90°E to 100°E and 0°N to 10°N). The teammate suggestion `10N_100E` is east of the sample and does not cover it. The old Songkhla suggestion is a different, more southerly geography; it is not a good name for these sample plots. The earlier broad proposal of Brazil was not based on these supplier geometries and should not guide this acquisition.

## Acquired layer: Hansen Global Forest Change

Pinned latest product: **Hansen/UMD/Google/USGS/NASA Global Forest Change 2025 v1.13**, published for 2000–2025, nominal 30.92 m pixels, CC BY 4.0. Official catalog: <https://developers.google.com/earth-engine/datasets/catalog/UMD_hansen_global_forest_change_2025_v1_13>. Direct source tiles are hosted at <https://storage.googleapis.com/earthenginepartners-hansen/GFC-2025-v1.13/>.

Three source bands were downloaded as complete official tiles, then clipped by pixel window to the union bounding rectangle of the 17 plots. The provider's strip-organized GeoTIFFs do not expose a subset URL, so this bounded acquisition downloaded **224,170,336 bytes** total (about 213.8 MiB) for the three required source tiles. The cached originals live only under gitignored `data/public/raw/`; the three clipped chips total 576,999 bytes (about 0.55 MiB). The chips preserve native EPSG:4326 cell alignment and are not reprojected. Outward floor/ceil window bounds contain the full sample bbox, and each chip was read back and compared pixel-for-pixel with its source window.

`treecover2000` is percent canopy closure for vegetation taller than 5 m in 2000. `lossyear` is 0 for no mapped loss and 1–25 for detected stand-replacement forest-cover loss in 2001–2025. `datamask` codes are 0 no data, 1 mapped land, and 2 permanent water; use this band before treating loss-year zero as an observed no-loss value. In the decoded rectangular chip there are 744,732 pixels: 743,418 land and 1,314 water, with no datamask-zero pixels. Among land pixels, 424,407 have loss-year 0 and 319,011 have nonzero loss-year values; 43,519 land pixels are coded 21–23 (2021–2023). There are also 56 nonzero loss-year values on permanent-water pixels, demonstrating why the validity mask matters. The tree-cover chip spans values 0–100, with 650,827 pixels at or above 30%. These are bounding-rectangle counts, not plot-overlap area or supplier decision results. Full per-value histograms and each file's exact size, transform, bounds, checksum, and readback flags are also recorded there.

These layers describe the **latest** GFC release; the supplier CSV's `Hansen2021–23` labels and declared 2024 harvest date are recorded independently. Do not silently compare the two as if they were the same source vintage or infer supplier results from these chips. Hansen tree-cover loss is not equivalent to legal deforestation: mapped loss may have different causes and legal status.

Reproduce in a project-local isolated environment. The acquisition run used Python 3.14.7, Rasterio 1.5.2, and GDAL 3.12.2 (recorded by the script):

```sh
python3 -m venv .venv-data
.venv-data/bin/python -m pip install rasterio==1.5.2
.venv-data/bin/python scripts/acquire_public_sample.py
```

The script downloads complete source band tiles atomically to `data/public/raw/`, validates each cached TIFF, then reads and clips only the AOI pixel window and emits small native-grid GeoTIFF chips plus `data/public/provenance.json`. Provenance records acquisition time, URLs, Python/Rasterio/GDAL versions, source and chip SHA-256, byte sizes, pixel window, transform, actual bounds, bbox coverage, exact readback equality, nodata, and decoded value counts/range. A partial download uses a `.part` path and cannot be mistaken for a completed cached tile. The ignored `data/public/raw/` directory is a local cache; small derived chips and their provenance are retained in the repository.

## JRC 2020 forest baseline: verified, acquisition failed

The European Commission JRC Global Forest Cover Map 2020 **v3** is a global 10°×10° tiled GeoTIFF product. Its official page describes WGS84 tiles, a freely reusable product with required acknowledgement, and a separate ~50 GB global mosaic that is inappropriate here: <https://forobs.jrc.ec.europa.eu/GFC/v3>. The sample aligns with JRC tile `N10_E90`. This could provide a useful 2020 baseline distinct from Hansen's 2000 canopy cover.

The official tile-download route advertised by the page, `https://ies-ows.jrc.europa.eu/iforce/gfc2020/download.py?version=v3&type=tile&tile=N10_E90` (tile ID verified in the page published grid), returned **HTTP 500 Internal Server Error** on the initial request and one retry. The zero-padded spelling also returned HTTP 500. No JRC pixel values or coverage are claimed and no large mosaic was downloaded. Keep JRC missing until the official tile route works and decoded coverage is verified.

## Optional restriction layer: Protected Planet / WDPA

Protected Planet's current legal terms (<https://www.protectedplanet.net/en/legal>) prohibit commercial use without prior written permission and restrict sublicensing and redistribution, including within derivative works. Because this work is for a company challenge, do not download, embed, redistribute, or claim unrestricted use of WDPA/WDPCA data without permission. Country-level official protected-area sources may be a more suitable next option after the demo jurisdiction and license are confirmed. This layer is optional and did not delay the forest samples.

## Global Nature Watch map

The live map is available at <https://www.globalnaturewatch.org/map/>; a successful parent-browser observation on 13 October 2026 showed the layer catalog and 2001–2025 loss timeline. It is useful for visually exploring candidate layers and date coverage. This is evidence of map availability only, not proof of a stable bulk-download API, machine-readable export, or reuse license for every layer. Those need to be checked per dataset before acquisition.

For its integrated disturbance alerts, GNW's own map documentation describes a combined GLAD-L, GLAD-S2, and RADD layer (newer material also discusses the added DIST-ALERT system). It warns that disturbances may include harvest, fire, disease, or storms; alerts can have false positives and should not be used by themselves for area estimates or regional trend assessment. Treat alerts as review signals and retain source-specific definitions. Reference: <https://www.globalnaturewatch.org/map/?map=eyJkYXRhc2V0cyI6W3siZGF0YXNldCI6ImludGVncmF0ZWQtZGVmb3Jlc3RhdGlvbi1hbGVydHMtOGJpdCIsIm9wYWNpdHkiOjEsInZpc2liaWxpdHkiOnRydWUsImxheWVycyI6WyJpbnRlZ3JhdGVkLWRlZm9yZXN0YXRpb24tOGJpdCJdfV19>.

## Files and limits

- `data/public/hansen_treecover2000_sample.tif`, `data/public/hansen_lossyear_sample.tif`, and `data/public/hansen_datamask_sample.tif`: decoded sample windows on original grids.
- `data/public/provenance.json`: acquisition metadata, pixel-level decoded summaries and checksums. Raw provider tiles are locally cached under the gitignored `data/public/raw/` directory.
- `scripts/acquire_public_sample.py`: reproducible acquisition and clipping command.

Coverage is the aggregate supplier-plot bounding rectangle, not a full-country or complete regional assessment. No legal forest determination, protected-area overlap, Hansen vintage equivalence, accuracy estimate, or company compliance outcome is established by these samples.
