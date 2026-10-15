"""Claim 4 addendum: CCITT G4 (bilevel standard) and PNG 1-bit controls for the decision-layer planes."""
import io, sys, warnings, zlib, struct
import numpy as np
from rasterio.io import MemoryFile
from rasterio.transform import Affine
from _common import facts_to_codes, independent_facts, read_raw

raw = read_raw(); F = independent_facts(raw); h, w = raw['lossyear']['shape']
codes = facts_to_codes(F, 'eudr-decision.v1').astype(np.int16)
land = codes >= 2; state = np.where(land, (codes - 2) // 6, 0); year = np.where(land, (codes - 2) % 6, 0)
planes = {'water': codes == 1, 'forest': land & (state == 1), 'unknown_forest': land & (state == 2)}
events = {f'year{2020 + i}': year == i for i in range(1, 6)}
prof = dict(driver='GTiff', height=h, width=w, count=1, dtype='uint8', nbits=1, crs='EPSG:4326',
            transform=Affine(*raw['lossyear']['t']), tiled=False)
def size(p, compress, **kw):
    with warnings.catch_warnings():
        warnings.simplefilter('ignore')
        try:
            with MemoryFile() as m:
                with m.open(**prof, compress=compress, **kw) as d:
                    d.write(p.astype(np.uint8)[None])
                return len(m.read())
        except Exception as e:
            return f'err:{str(e)[:50]}'
tot = {}
for name, p in {**planes, **events}.items():
    row = {c: size(p, c, **({'zstd_level': 22} if c == 'zstd' else {}), **({'blockysize': h} if c in ('zstd','deflate','lzw') else {})) for c in ('ccittfax4', 'zstd', 'deflate', 'lzw', 'packbits')}
    print(name, int(p.sum()), row)
    for c, v in row.items():
        if isinstance(v, int): tot[c] = tot.get(c, 0) + v
print('totals (all 8 planes, one file each):', tot)
