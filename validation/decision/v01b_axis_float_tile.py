"""Claim 1 addendum: decision_original's float-affine JRC lookup vs the integer 3k+1 rule on the whole 10x10 degree tile axes."""
import sys
import numpy as np
import rasterio
from _common import ROOT
h = rasterio.open(ROOT / 'data/public/raw/Hansen_GFC-2025-v1.13_lossyear_10N_090E.tif')
j = rasterio.open(ROOT / 'data/experimental/jrc/JRC_GFC2020_V4_N10_E90.tif')
a, _, c, _, e, f = h.transform[:6]
ja, _, jc, _, je, jf = j.transform[:6]
k = np.arange(40000)
x = c + (k + .5) * a
y = f + (k + .5) * e
jcol = np.floor((x - jc) / ja).astype(np.int64)
jrow = np.floor((y - jf) / je).astype(np.int64)
frac_c = ((x - jc) / ja) - jcol
frac_r = ((y - jf) / je) - jrow
ok = np.array_equal(jcol, 3 * k + 1) and np.array_equal(jrow, 3 * k + 1)
print({'float_affine_equals_3k+1_on_all_40000_rows_and_cols': bool(ok),
       'max_deviation_from_jrc_cell_centre': float(max(abs(frac_c - .5).max(), abs(frac_r - .5).max()))})
sys.exit(0 if ok else 1)
