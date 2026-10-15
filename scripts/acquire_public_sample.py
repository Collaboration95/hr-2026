#!/usr/bin/env python3
"""Acquire native-grid Hansen samples over the provided supplier plots.

Install in an isolated venv with: python -m pip install rasterio==1.5.2
Run from the repository root: .venv-data/bin/python scripts/acquire_public_sample.py
"""
from __future__ import annotations

import hashlib
import json
import os
import math
import platform
import urllib.request
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

import rasterio
from rasterio.windows import from_bounds

ROOT = Path(__file__).resolve().parents[1]
PLOTS = ROOT / "data/company-sample/2026-10-12/200001-17plots-valid.geojson"
OUT = ROOT / "data/public"
RAW = OUT / "raw"
VERSION = "GFC-2025-v1.13"
BASE = f"https://storage.googleapis.com/earthenginepartners-hansen/{VERSION}"
TILE = "10N_090E"


def digest(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for b in iter(lambda: f.read(1024 * 1024), b""):
            h.update(b)
    return h.hexdigest()


def bounds(geojson: dict) -> tuple[float, float, float, float]:
    pts: list[list[float]] = []
    def visit(v):
        if isinstance(v, list) and v and isinstance(v[0], (float, int)):
            pts.append(v)
        elif isinstance(v, list):
            for x in v:
                visit(x)
    for feature in geojson["features"]:
        visit(feature["geometry"]["coordinates"])
    return min(p[0] for p in pts), min(p[1] for p in pts), max(p[0] for p in pts), max(p[1] for p in pts)


def fetch(url: str, dest: Path) -> None:
    if dest.exists() and dest.stat().st_size > 0:
        try:
            with rasterio.open(dest) as ds:
                if ds.width > 0 and ds.height > 0 and ds.count == 1:
                    return
        except rasterio.errors.RasterioError:
            pass
        dest.unlink()
    dest.parent.mkdir(parents=True, exist_ok=True)
    req = urllib.request.Request(url, headers={"User-Agent": "HackHire-Sustainability-Research/1.0"})
    partial = dest.with_suffix(dest.suffix + ".part")
    try:
        with urllib.request.urlopen(req, timeout=180) as response, partial.open("wb") as f:
            expected = int(response.headers.get("Content-Length", "0"))
            while chunk := response.read(1024 * 1024):
                f.write(chunk)
            f.flush()
            os.fsync(f.fileno())
        if partial.stat().st_size == 0 or (expected and partial.stat().st_size != expected):
            raise RuntimeError(f"Incomplete source download: {partial.stat().st_size} bytes; expected {expected or 'nonzero'}")
        # Open the complete TIFF before replacing the cache path.
        with rasterio.open(partial) as ds:
            if ds.width <= 0 or ds.height <= 0 or ds.count != 1:
                raise RuntimeError(f"Invalid source raster dimensions/bands: {ds.width}x{ds.height}, bands={ds.count}")
        partial.replace(dest)
    except Exception:
        partial.unlink(missing_ok=True)
        raise


def containing_window(src, bbox):
    # Expand outward so rounding cannot omit the east/south edge pixels.
    floating = from_bounds(*bbox, transform=src.transform)
    left = math.floor(floating.col_off)
    top = math.floor(floating.row_off)
    right = math.ceil(floating.col_off + floating.width)
    bottom = math.ceil(floating.row_off + floating.height)
    return rasterio.windows.Window(left, top, right - left, bottom - top)


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    plots = json.loads(PLOTS.read_text())
    bbox = bounds(plots)
    provenance = {
        "acquired_at_utc": datetime.now(timezone.utc).isoformat(),
        "supplier_plots": str(PLOTS.relative_to(ROOT)),
        "plot_count": len(plots["features"]),
        "plot_bounds_wgs84": bbox,
        "tile": TILE,
        "product": VERSION,
        "python_version": platform.python_version(),
        "rasterio_version": rasterio.__version__,
        "gdal_version": rasterio.__gdal_version__,
        "product_semantics": "treecover2000 is percent canopy closure for vegetation >5m in 2000; lossyear 0=no detected loss, 1..25=2001..2025 stand-replacement forest-cover loss. Loss is not legal deforestation.",
        "acquisition_method": "Download the three official source GeoTIFF tiles to a gitignored local cache, then decode only the supplier-plot bounding window with rasterio. The source GeoTIFFs are strip-organized and have no provider-side subset route; total source download is reported per layer.",
        "layers": [],
    }
    decoded = {}
    source_grids = []
    for band in ("treecover2000", "lossyear", "datamask"):
        name = f"Hansen_{VERSION}_{band}_{TILE}.tif"
        url = f"{BASE}/Hansen_{VERSION}_{band}_{TILE}.tif"
        raw = RAW / name
        fetch(url, raw)
        chip = OUT / f"hansen_{band}_sample.tif"
        with rasterio.open(raw) as src:
            source_grids.append((src.crs, src.transform, src.width, src.height))
            win = containing_window(src, bbox)
            arr = src.read(1, window=win)
            decoded[band] = arr
            profile = src.profile.copy()
            profile.update(width=arr.shape[1], height=arr.shape[0], transform=src.window_transform(win), compress="deflate", tiled=True, blockxsize=256, blockysize=256)
            with rasterio.open(chip, "w", **profile) as dst:
                dst.write(arr, 1)
            # Verify native-grid output bounds enclose the complete input bbox
            # and the decoded chip is byte-for-byte equal to the source window.
            with rasterio.open(chip) as check:
                actual_bounds = [check.bounds.left, check.bounds.bottom, check.bounds.right, check.bounds.top]
                chip_transform = list(check.transform)[:6]
                encloses = actual_bounds[0] <= bbox[0] and actual_bounds[1] <= bbox[1] and actual_bounds[2] >= bbox[2] and actual_bounds[3] >= bbox[3]
                readback_equal = bool((check.read(1) == arr).all())
                if not encloses or not readback_equal or check.transform != src.window_transform(win):
                    raise RuntimeError(f"Chip validation failed for {band}: encloses={encloses}, readback_equal={readback_equal}")
            vals = Counter(map(int, arr.ravel()))
            layer = {
                "band": band, "url": url, "source_tile_bytes": raw.stat().st_size,
                "source_tile_sha256": digest(raw), "window": [int(win.col_off), int(win.row_off), int(win.width), int(win.height)],
                "decoded_shape": list(arr.shape), "native_crs": str(src.crs), "native_transform": list(src.transform)[:6],
                "chip_transform": chip_transform, "chip_bounds_wgs84": actual_bounds,
                "chip_contains_all_plot_bounds": encloses, "source_window_readback_equal": readback_equal,
                "chip_bytes": chip.stat().st_size, "chip_sha256": digest(chip), "value_counts": {str(k): v for k, v in sorted(vals.items())},
                "min": int(arr.min()), "max": int(arr.max()), "nodata": src.nodata,
            }
            provenance["layers"].append(layer)
    by_band = {layer["band"]: layer for layer in provenance["layers"]}
    if len(set(source_grids)) != 1:
        raise RuntimeError("Source bands do not share identical CRS, transform, and raster dimensions")
    if len({tuple(layer["window"]) for layer in provenance["layers"]}) != 1:
        raise RuntimeError("Source band windows do not align")
    provenance["joint_grid_verified"] = {
        "same_crs_transform_dimensions": True,
        "crs": str(source_grids[0][0]),
        "transform": list(source_grids[0][1])[:6],
        "source_dimensions": [source_grids[0][2], source_grids[0][3]],
        "same_window": True,
    }
    mask_counts = by_band["datamask"]["value_counts"]
    loss_counts = by_band["lossyear"]["value_counts"]
    mask = decoded["datamask"]
    loss = decoded["lossyear"]
    land = mask == 1
    water = mask == 2
    loss_counts_land = {str(k): int(v) for k, v in sorted(Counter(map(int, loss[land])).items())}
    provenance["decoded_summary"] = {
        "chip_pixels": sum(int(v) for v in mask_counts.values()),
        "datamask_codes": {"0": "no data", "1": "mapped land surface", "2": "permanent water"},
        "datamask_counts": mask_counts,
        "lossyear_counts_on_land": loss_counts_land,
        "lossyear_zero_on_land": int(((loss == 0) & land).sum()),
        "lossyear_nonzero_on_land": int(((loss != 0) & land).sum()),
        "lossyear_nonzero_on_water": int(((loss != 0) & water).sum()),
        "lossyear_nonzero_where_datamask_missing": int(((loss != 0) & (mask == 0)).sum()),
        "note": "Loss-year zero on land means no mapped loss during the product period; water pixels are separated using datamask. These are counts in the bounding rectangle, not plot-level totals.",
    }
    (OUT / "provenance.json").write_text(json.dumps(provenance, indent=2) + "\n")
    print(json.dumps(provenance, indent=2))


if __name__ == "__main__":
    os.environ.setdefault("GDAL_DISABLE_READDIR_ON_OPEN", "EMPTY_DIR")
    main()
