#!/usr/bin/env python3
"""Create a native-grid AOI chip and provenance for the JRC GFC 2020 v4 tile."""

from __future__ import annotations

import hashlib
import json
import math
import platform
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import rasterio
from rasterio.windows import Window, from_bounds


ROOT = Path(__file__).resolve().parent
SOURCE = ROOT / "JRC_GFC2020_V4_N10_E90.tif"
CHIP = ROOT / "JRC_GFC2020_V4_N10_E90_company-bbox.tif"
PROVENANCE = ROOT / "provenance.json"
SOURCE_URL = (
    "https://jeodpp.jrc.ec.europa.eu/ftp/jrc-opendata/FOREST/"
    "GFC2020/LATEST/tiles/JRC_GFC2020_V4_N10_E90.tif"
)
METADATA_PAGE = "https://forobs.jrc.ec.europa.eu/GFC"
METADATA_XML = "https://forobs.jrc.ec.europa.eu/GFC/download?version=v4&type=metadata"
EARTH_ENGINE_CATALOG = "https://developers.google.com/earth-engine/datasets/catalog/JRC_GFC2020_V4"
PLOT_BOUNDS = (98.772429, 8.431179, 99.080292, 8.581888)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def main() -> None:
    if not SOURCE.is_file():
        raise SystemExit(f"Missing complete source tile: {SOURCE}")

    with rasterio.open(SOURCE) as src:
        if src.crs != rasterio.crs.CRS.from_epsg(4326):
            raise SystemExit(f"Unexpected source CRS: {src.crs}")
        if not (src.bounds.left <= PLOT_BOUNDS[0] and src.bounds.bottom <= PLOT_BOUNDS[1]
                and src.bounds.right >= PLOT_BOUNDS[2] and src.bounds.top >= PLOT_BOUNDS[3]):
            raise SystemExit("Source tile does not cover the complete company bbox")

        float_window = from_bounds(*PLOT_BOUNDS, transform=src.transform)
        col0 = math.floor(float_window.col_off)
        row0 = math.floor(float_window.row_off)
        col1 = math.ceil(float_window.col_off + float_window.width)
        row1 = math.ceil(float_window.row_off + float_window.height)
        window = Window(col0, row0, col1 - col0, row1 - row0)
        values = src.read(1, window=window)
        chip_transform = src.window_transform(window)
        source_block_shapes = src.block_shapes
        source_tags = src.tags()

        profile = src.profile.copy()
        profile.update(
            width=values.shape[1],
            height=values.shape[0],
            transform=chip_transform,
            compress="DEFLATE",
            predictor=2,
            tiled=True,
            blockxsize=256,
            blockysize=256,
        )
        with rasterio.open(CHIP, "w", **profile) as dst:
            dst.write(values, 1)
            dst.update_tags(
                source_product="JRC Global Forest Cover Map 2020 version 4",
                source_tile="JRC_GFC2020_V4_N10_E90.tif",
                extraction="outward-aligned native-grid rectangle containing supplied plot bbox",
                plot_bbox_wgs84=",".join(map(str, PLOT_BOUNDS)),
            )

        with rasterio.open(CHIP) as check:
            readback = check.read(1)
            if not np.array_equal(values, readback):
                raise SystemExit("Chip readback differs from the source tile window")
            unique, frequencies = np.unique(readback, return_counts=True)
            class_counts = {str(int(k)): int(v) for k, v in zip(unique, frequencies)}
            chip_bounds = tuple(check.bounds)
            chip_transform_tuple = tuple(check.transform)
            width, height = check.width, check.height
            dtype, nodata = check.dtypes[0], check.nodata

    now = datetime.now(timezone.utc).isoformat(timespec="seconds")
    record = {
        "acquired_at_utc": now,
        "product": "JRC Global Forest Cover Map 2020",
        "version": "v4",
        "version_note": "This is an explicitly versioned newer alternative; it is not v3 and is not interchangeable with v3 without review.",
        "provider_page": METADATA_PAGE,
        "provider_metadata_xml": METADATA_XML,
        "official_band_catalog": EARTH_ENGINE_CATALOG,
        "source_url": SOURCE_URL,
        "source_file": SOURCE.name,
        "source_bytes": SOURCE.stat().st_size,
        "source_sha256": sha256(SOURCE),
        "source_http_observation": {
            "status": 200,
            "content_type": "image/tiff",
            "content_length_bytes": 197739699,
            "etag": "bc944b3-65b6e6b114b0b",
            "last_modified": "Mon, 14 Sep 2026 09:54:21 GMT",
            "observed_via": "HTTP HEAD of official JRC tile URL; listing also exposes the linked tile",
        },
        "licence": "Official JRC page states the data are free of charge without restriction of use; proper acknowledgement is required.",
        "required_citation": "Bourgoin, Clement; Achard, Frederic; Beuchle, Rene; Carboni, Silvia; Carreiras, Joao; Marinelli, Daniele; Rotllan-Puig, Xavier; Simonetti, Dario; Colditz, Rene (2026): Global map of forest cover 2020 - version 4. European Commission, Joint Research Centre [Dataset] doi: 10.2905/JRC.3KATEH8 PID: http://data.europa.eu/89h/cf7c49ea-8f00-4c5a-bd40-6f25dc341580",
        "download_route_note": "Official GFC v3 page's UI-generated ies-ows route could not be reached in this environment. The official JRC LATEST/tiles/ directory provided this per-tile v4 GeoTIFF, avoiding the ~50 GB mosaic.",
        "software": {
            "python": platform.python_version(),
            "rasterio": rasterio.__version__,
            "gdal": rasterio.__gdal_version__,
            "numpy": np.__version__,
        },
        "source_raster": {
            "driver": "GTiff",
            "width": 120000,
            "height": 120000,
            "bands": 1,
            "dtype": dtype,
            "crs": "EPSG:4326",
            "bounds_wgs84": [90.0, 0.0, 100.0, 10.0],
            "transform": [8.333333333333333e-05, 0.0, 90.0, 0.0, -8.333333333333333e-05, 10.0],
            "nodata": nodata,
            "block_shapes": [list(shape) for shape in source_block_shapes],
            "nominal_pixel_size": "10 m per official JRC/Google Earth Engine catalog; raster affine step is 1/12000 degree",
            "tags": source_tags,
        },
        "company_bbox_wgs84": list(PLOT_BOUNDS),
        "chip_file": CHIP.name,
        "chip_bytes": CHIP.stat().st_size,
        "chip_sha256": sha256(CHIP),
        "chip_window_source_row_col_height_width": [row0, col0, int(window.height), int(window.width)],
        "chip_dimensions_width_height": [width, height],
        "chip_crs": "EPSG:4326",
        "chip_transform": list(chip_transform_tuple),
        "chip_bounds_wgs84": list(chip_bounds),
        "chip_contains_company_bbox": (
            chip_bounds[0] <= PLOT_BOUNDS[0] and chip_bounds[1] <= PLOT_BOUNDS[1]
            and chip_bounds[2] >= PLOT_BOUNDS[2] and chip_bounds[3] >= PLOT_BOUNDS[3]
        ),
        "pixel_readback_equal_to_source_window": True,
        "decoded_bbox_pixel_count": width * height,
        "decoded_value_counts": class_counts,
        "decoded_min": int(readback.min()),
        "decoded_max": int(readback.max()),
        "value_semantics": {
            "official_product_description": "Spatial representation of forest presence and absence for reference year 2020 at 10 m; for EUDR use it is non-mandatory, non-exclusive and not legally binding.",
            "official_band": "Map",
            "official_class_table": {"1": "Forest"},
            "decoded_codes_in_chip": class_counts,
            "zero_note": "0 is present in the decoded raster; the catalog describes both presence and absence but its displayed class table names only value 1. Preserve raw 0 and confirm its exact metadata label before semantic integration.",
        },
        "limits": [
            "This is a rectangular bbox chip, not plot-polygon statistics.",
            "The product represents mapped forest cover for reference year 2020; it does not independently establish legal compliance or supplier declarations.",
            "The current official page says v4 technical documentation is expected by December 2026; review version-specific methods and class definitions before semantic integration.",
            "This v4 acquisition does not resolve availability of the requested v3 tile.",
        ],
    }
    PROVENANCE.write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({key: record[key] for key in (
        "source_sha256", "source_bytes", "chip_sha256", "chip_bytes",
        "chip_dimensions_width_height", "chip_bounds_wgs84", "decoded_value_counts",
        "pixel_readback_equal_to_source_window",
    )}, indent=2))


if __name__ == "__main__":
    main()
