"""EXPLORATORY cross-layer look: where does Hansen loss sit relative to JRC 2020 forest?

Not part of the verified engine, the frozen export or the proof. It samples
the JRC v4 class at each Hansen cell centre (nearest JRC cell on JRC's own
grid). This is a quick orientation aid for the pitch narrative, not a
reviewed result, and not a deforestation or compliance finding. Cell counts
are native cells, not hectares; the two grids differ (~28 m vs ~9 m).

    .venv-data/bin/python scripts/explore_cross_layer.py
"""
import json, pathlib

import numpy as np
import rasterio
from rasterio.transform import rowcol, xy

root = pathlib.Path(__file__).resolve().parents[1]
loss_src = rasterio.open(root / "data/public/hansen_lossyear_sample.tif")
loss = loss_src.read(1)
land = rasterio.open(root / "data/public/hansen_datamask_sample.tif").read(1) == 1
jrc_src = rasterio.open(root / "data/experimental/jrc/JRC_GFC2020_V4_N10_E90_company-bbox.tif")
jrc = jrc_src.read(1)

rows, cols = np.indices(loss.shape)
xs, ys = xy(loss_src.transform, rows.ravel(), cols.ravel())
jr, jc = rowcol(jrc_src.transform, np.asarray(xs), np.asarray(ys))
jr, jc = np.asarray(jr), np.asarray(jc)
inside = (jr >= 0) & (jr < jrc.shape[0]) & (jc >= 0) & (jc < jrc.shape[1])
jrc_at_centre = np.full(jr.shape, 255, np.uint8)
jrc_at_centre[inside] = jrc[jr[inside], jc[inside]]
forest = (jrc_at_centre.reshape(loss.shape) == 1)

out = {"note": "exploratory; Hansen cell centres sampled on the JRC grid", "region": {}}
out["region"]["land_cells"] = int(land.sum())
out["region"]["share_land_cells_jrc_forest_2020"] = round(float(forest[land].mean()), 4)
for name, mask in {"loss_any_year": loss > 0, "loss_2021_on": loss >= 21, "loss_2001_2020": (loss > 0) & (loss <= 20)}.items():
    m = mask & land
    out["region"][name] = {"cells": int(m.sum()), "share_of_land": round(float(m.sum() / land.sum()), 4),
                           "in_jrc_forest_2020": int((m & forest).sum()),
                           "share_in_jrc_forest_2020": round(float((m & forest).sum() / max(1, m.sum())), 4)}

demo = json.loads((root / "artifacts/demo-v1.json").read_text())
out["plots"] = {}
for plot in demo["plots"]:
    post = [c for c in plot["evidence"]["features"] if c["properties"]["valid_land"] and (c["properties"]["lossyear"] or 0) >= 21]
    if not post:
        continue
    hits = 0
    for c in post:
        r, k = rowcol(jrc_src.transform, *c["properties"]["center"])
        hits += int(jrc[r, k] == 1)
    out["plots"][plot["plot_id"]] = {"post_2020_loss_cells": len(post), "centres_in_jrc_forest_2020": hits}
print(json.dumps(out, indent=2))
