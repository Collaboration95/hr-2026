"""Pack the pinned source chips into lossless PNG display rasters for the map.

Display only. The map recolours these pixels in the browser; every count shown
as evidence still comes from the validated engine exports, never from these
images. Run with the repository engine environment:

    .venv-data/bin/python app/scripts/render-region.py

Outputs (tracked, regenerated deterministically):
  app/public/region/hansen-bands.png   RGBA = lossyear, datamask, treecover2000, 255
  app/public/region/jrc-forest-2020.png RGBA = class (0/1), 255, 0, 255
  app/public/region/manifest.json      grids, bounds, channel map and SHA-256s
Each PNG is decoded again after writing and must equal its source bands exactly.
"""
import hashlib, json, pathlib, struct, zlib

import numpy as np
import rasterio

root = pathlib.Path(__file__).resolve().parents[2]
out = root / "app/public/region"
out.mkdir(parents=True, exist_ok=True)
sha = lambda p: hashlib.sha256(pathlib.Path(p).read_bytes()).hexdigest()


def write_png(path, rgba):
    h, w, _ = rgba.shape
    raw = b"".join(b"\x00" + rgba[y].tobytes() for y in range(h))
    chunk = lambda t, d: struct.pack(">I", len(d)) + t + d + struct.pack(">I", zlib.crc32(t + d) & 0xFFFFFFFF)
    # No gAMA/iCCP/sRGB chunks: browsers then apply no colour conversion.
    path.write_bytes(b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", w, h, 8, 6, 0, 0, 0))
                     + chunk(b"IDAT", zlib.compress(raw, 9)) + chunk(b"IEND", b""))


def read_png(path):
    data = path.read_bytes()
    pos, idat, w, h = 8, b"", 0, 0
    while pos < len(data):
        n = struct.unpack(">I", data[pos:pos + 4])[0]
        t, body = data[pos + 4:pos + 8], data[pos + 8:pos + 8 + n]
        if t == b"IHDR":
            w, h = struct.unpack(">II", body[:8])
        elif t == b"IDAT":
            idat += body
        pos += 12 + n
    rows = np.frombuffer(zlib.decompress(idat), np.uint8).reshape(h, 1 + w * 4)
    assert (rows[:, 0] == 0).all(), "unexpected PNG filter"
    return rows[:, 1:].reshape(h, w, 4)


def band(path):
    with rasterio.open(root / path) as r:
        values, mask = r.read(1), r.read_masks(1)
        assert (mask == 255).all(), f"{path}: masked pixels need an explicit display encoding"
        return values, r.transform, r.crs.to_string(), r.shape


def grid(transform, shape):
    a, b, c, d, e, f = transform[:6]
    return {"shape_rows_columns": list(shape), "transform": [a, b, c, d, e, f],
            "bounds_west_south_east_north": [c, f + e * shape[0], c + a * shape[1], f]}


hansen = {name: f"data/public/hansen_{name}_sample.tif" for name in ("lossyear", "datamask", "treecover2000")}
loss, t, crs, shape = band(hansen["lossyear"])
mask, t2, _, s2 = band(hansen["datamask"])
cover, t3, _, s3 = band(hansen["treecover2000"])
assert t == t2 == t3 and shape == s2 == s3 and crs == "EPSG:4326"
rgba = np.dstack([loss, mask, cover, np.full(shape, 255, np.uint8)]).astype(np.uint8)
write_png(out / "hansen-bands.png", rgba)
assert (read_png(out / "hansen-bands.png") == rgba).all()

jrc_path = "data/experimental/jrc/JRC_GFC2020_V4_N10_E90_company-bbox.tif"
jrc, jt, jcrs, jshape = band(jrc_path)
assert jcrs == "EPSG:4326" and set(np.unique(jrc)) <= {0, 1}
jrgba = np.dstack([jrc, np.full(jshape, 255, np.uint8), np.zeros(jshape, np.uint8),
                   np.full(jshape, 255, np.uint8)]).astype(np.uint8)
write_png(out / "jrc-forest-2020.png", jrgba)
assert (read_png(out / "jrc-forest-2020.png") == jrgba).all()

manifest = {
    "schema_version": "plotline.region-display.v1",
    "purpose": "Display rasters for the map. Not evidence: all counts come from validated engine exports.",
    "hansen": {
        "product": "Hansen Global Forest Change 2025 v1.13", "crs": crs, **grid(t, shape),
        "png": "hansen-bands.png", "png_sha256": sha(out / "hansen-bands.png"),
        "channels": {"r": "lossyear (0 = no loss, n = 2000 + n)", "g": "datamask (0 no data, 1 land, 2 water)",
                     "b": "treecover2000 (percent)", "a": "always 255"},
        "sources": {k: {"path": v, "sha256": sha(root / v)} for k, v in hansen.items()},
    },
    "jrc": {
        "product": "JRC Global Forest Cover 2020 v4", "crs": jcrs, **grid(jt, jshape),
        "png": "jrc-forest-2020.png", "png_sha256": sha(out / "jrc-forest-2020.png"),
        "channels": {"r": "class (0 = valid Non-forest, 1 = Forest)", "g": "validity (255 = valid)", "b": "unused", "a": "always 255"},
        "sources": {"class": {"path": jrc_path, "sha256": sha(root / jrc_path)}},
    },
}
(out / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
print(json.dumps({k: [manifest[k]["png"], (out / manifest[k]["png"]).stat().st_size] for k in ("hansen", "jrc")}))
