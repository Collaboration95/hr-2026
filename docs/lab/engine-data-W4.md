# Engine W4 — JRC forest baseline acquisition

**Result:** a usable official JRC Global Forest Cover Map 2020 **v4** tile and an aligned sample chip are available for review. The requested v3 tile was not recovered in this bounded attempt. V4 is a separately versioned candidate baseline; it has not been integrated into the engine or used to produce plot findings.

## Why v4 is a useful candidate

The supplied 17-plot bbox is **98.772429–99.080292°E, 8.431179–8.581888°N**, inside JRC's N10/E90 10° tile. The current JRC data-access page describes v4 as a 10°-tile GeoTIFF product in WGS84. Its Earth Engine catalog describes a 10 m, one-band forest presence/absence map for reference year 2020; it names code `1` as `Forest`. The catalog says use for EUDR is non-mandatory, non-exclusive, and not legally binding. This is a more temporally relevant forest-2020 layer than Hansen `treecover2000`, with an explicit regulatory-date context, subject to version review.

## Bounded route investigation

- The official JRC v3 page, [GFC v3 data access](https://forobs.jrc.ec.europa.eu/GFC/v3), was opened in a fresh T3 preview tab. Its own tile UI constructs `https://ies-ows.jrc.europa.eu/iforce/gfc2020/download.py?version=v3&type=tile&lat=N10&lon=E90`. That UI-generated route did not load in the preview (Chrome error page); a local HTTP HEAD could not resolve `ies-ows.jrc.europa.eu` (curl DNS error 6). The earlier `tile=N10_E90` and zero-padded routes remain recorded as HTTP 500 in the existing acquisition notes. The new `lat`/`lon` route was not reported as an HTTP 500 because no HTTP status was received here.
- The JRC page links to its official Big Data Analytics Platform. Its public directory at [GFC2020/LATEST](https://jeodpp.jrc.ec.europa.eu/ftp/jrc-opendata/FOREST/GFC2020/LATEST/) lists both `single-cog/` and `tiles/`. The `tiles/` page visibly lists `JRC_GFC2020_V4_N10_E90.tif`; this direct per-tile file is the alternative route used. The official endpoint returned HTTP 200, `image/tiff`, `Content-Length: 197739699`, ETag `bc944b3-65b6e6b114b0b`, and `Last-Modified: Mon, 14 Sep 2026 09:54:21 GMT` on HEAD.
- The official current [GFC data-access page](https://forobs.jrc.ec.europa.eu/GFC) now documents v4 and names v3 as a previous version. Its metadata-download link redirects to the same `ies-ows` host that could not be resolved locally; no XML metadata file is claimed as acquired. The per-tile GeoTIFF itself has no embedded product metadata beyond `AREA_OR_POINT=Area`; raster and official catalog metadata are recorded in the provenance JSON.
- No login, account, paid service, customer upload, global mosaic, or Hansen substitution was used. The advertised global mosaic is about 50 GB and was not downloaded.

## Acquired files and verification

Files are confined to `data/experimental/jrc/`:

- `JRC_GFC2020_V4_N10_E90.tif` — complete official v4 source tile, **197,739,699 bytes**, SHA-256 `fbae885505a5ee7a481775401f27c23b1b8ef1e5451b69156a70c04aa42f38d7`.
- `JRC_GFC2020_V4_N10_E90_company-bbox.tif` — lossless value-preserving native-grid bbox chip, **46,238 bytes**, SHA-256 `3019c19bca064ac8f31747da856f40ce04146da6759c2f36dc30d0ff2e07e7c5`.
- `provenance.json` — source response headers, checksums, raster metadata, AOI window, decoded value counts, readback result, citation, license and limitations.
- `inspect_and_chip.py` — reproducible chip/provenance command.

Decoded source metadata: one-band `uint8` GeoTIFF, **120,000 × 120,000**, EPSG:4326, source bounds `[90, 0, 100, 10]`, affine step `1/12000°`, no nodata value, and source strip block shape `[1, 120000]`. The outward-aligned AOI window is source row 17,017, column 105,269, height 1,809, width 3,695. The chip bounds are `[98.77241666666667, 8.431166666666666, 99.08033333333334, 8.581916666666666]`, which contain the supplied bbox. Chip readback matched the source window exactly.

Decoded rectangular-chip counts: code `0`: **5,618,060**; code `1`: **1,066,195**; total **6,684,255** pixels. The official catalog identifies code `1` as forest. Code `0` occurs in the raster, but the catalog's displayed class table names only code `1`; retain code `0` as raw data and confirm its exact metadata label before assigning engine semantics. These are bbox-chip counts, not plot-polygon areas or per-plot results.

Reproduce with the repo's isolated environment:

```sh
.venv-data/bin/python data/experimental/jrc/inspect_and_chip.py
```

## License, citation, and limits

The JRC v4 data-access page says the data are free of charge without restriction of use and requires acknowledgement. Required citation:

> Bourgoin, Clement; Achard, Frederic; Beuchle, Rene; Carboni, Silvia; Carreiras, Joao; Marinelli, Daniele; Rotllan-Puig, Xavier; Simonetti, Dario; Colditz, Rene (2026): Global map of forest cover 2020 - version 4. European Commission, Joint Research Centre [Dataset] doi: 10.2905/JRC.3KATEH8. PID: http://data.europa.eu/89h/cf7c49ea-8f00-4c5a-bd40-6f25dc341580

Official references: [JRC v4 product page](https://forobs.jrc.ec.europa.eu/GFC), [official JRC per-tile listing](https://jeodpp.jrc.ec.europa.eu/ftp/jrc-opendata/FOREST/GFC2020/LATEST/tiles/), and [Earth Engine v4 catalog](https://developers.google.com/earth-engine/datasets/catalog/JRC_GFC2020_V4).

The official JRC page says a separate v4 technical report is expected by December 2026, after this acquisition date. Do not assume v3 and v4 class semantics or methods are interchangeable. The layer is a mapped 2020 forest-presence product, not an independently verified supplier finding or legal compliance determination. JRC describes the map as not legally binding for EUDR. The rectangular chip is not an exact plot overlay. Keep this acquisition outside the Hansen codec and review its source contract/version before any integration.

**Handoff decision:** review v4 as an optional, separate baseline because it adds a native 2020 forest-presence layer that is absent from the existing Hansen chips. Preserve v3 as unavailable until its specific tile can be acquired and decoded; do not silently relabel this v4 data as v3.
