"""Claim 1/5 addendum: round-trip property test of every encoding (incl. forced split event modes) on arbitrary rasters.

Random and edge-shaped uint8 code rasters (all 20 codes, sparse/dense events, widths not multiples of 8, 1xN, Nx1,
all-zero planes) must decode bit-exactly; write_store/read_store must agree; decision-level rasters obey the 3..7 rule.
"""
import json, random, sys, tempfile
from pathlib import Path
import numpy as np
from _common import OUT
from engine import decision_store as S

rng = np.random.default_rng(99)
r = random.Random(99)
tmp = Path(tempfile.mkdtemp(dir=OUT, prefix='v05c_'))
meta = {'shape': None, 'transform': [0.00025, 0, 98.77225, 0, -0.00025, 8.582], 'crs': 'EPSG:4326',
        'sources': [{'band': b, 'sha256': '0' * 64} for b in ('treecover2000', 'lossyear', 'datamask')], 'jrc_chip_sha256': '1' * 64}
shapes = [(1, 1), (1, 7), (1, 8), (1, 9), (7, 1), (9, 1), (2, 2), (3, 17), (8, 8), (16, 24), (33, 65), (64, 63), (120, 200), (200, 333)]
fails, n_cases, modes_used = [], 0, {}


def make(shape, kind):
    h, w = shape
    if kind == 'noise':
        return rng.integers(0, 20, shape).astype(np.uint8)
    base = np.full(shape, 2, np.uint8)
    base[rng.random(shape) < .05] = 1
    base[rng.random(shape) < .02] = 0
    land = base >= 2
    state = rng.choice([0, 1, 2], shape, p=[.6, .3, .1])
    year = np.zeros(shape, int)
    p = {'sparse': .003, 'dense': .5, 'none': 0, 'all': 1.0}[kind]
    ev = rng.random(shape) < p
    year[ev] = rng.integers(1, 6, int(ev.sum()))
    codes = np.where(land, 2 + 6 * state + year, base)
    return codes.astype(np.uint8)


for shape in shapes:
    for kind in ('noise', 'sparse', 'dense', 'none', 'all'):
        for level in ('eudr-screen.v1', 'eudr-decision.v1'):
            codes = make(shape, kind)
            if level == 'eudr-decision.v1':
                codes = np.where((codes >= 3) & (codes <= 7), 2, codes).astype(np.uint8)
            n_cases += 1
            for enc in S.ENCODINGS:
                try:
                    blob = S.encode_codes(codes, enc)
                    back = S.decode_codes(blob, shape, enc)
                    if not np.array_equal(back, codes) or back.dtype != np.uint8:
                        fails.append((shape, kind, level, enc, 'roundtrip'))
                except Exception as e:
                    fails.append((shape, kind, level, enc, f'{type(e).__name__}: {e}'))
            # forced split event codings, including ones the encoder would not choose
            for mode in ('plane', 'gaps0', 'gaps1'):
                try:
                    blob = b''.join(b for _, b in S._split_parts(codes, mode))
                except KeyError:
                    continue  # mode not eligible for this raster (gaps1 needs events only in forest states)
                try:
                    back = S.decode_codes(blob, shape, 'split')
                    modes_used[mode] = modes_used.get(mode, 0) + 1
                    if not np.array_equal(back, codes):
                        fails.append((shape, kind, level, 'split/' + mode, 'roundtrip'))
                except Exception as e:
                    fails.append((shape, kind, level, 'split/' + mode, f'{type(e).__name__}: {e}'))
            # file level
            try:
                m = dict(meta, shape=list(shape))
                p = tmp / 'x.plds'
                S.write_store(codes, m, p, level=level, encoding=r.choice(S.ENCODINGS))
                back, hdr = S.read_store(p)
                if not np.array_equal(back, codes):
                    fails.append((shape, kind, level, 'file', 'roundtrip'))
            except ValueError as e:
                # screen rasters with codes 3..7 are legal at the screen level; decision rasters were scrubbed above
                fails.append((shape, kind, level, 'file', f'ValueError: {e}'))
import shutil
shutil.rmtree(tmp, ignore_errors=True)
res = {'cases': n_cases, 'encodings': list(S.ENCODINGS), 'forced_split_modes_exercised': modes_used, 'failures': fails[:20], 'failure_count': len(fails)}
(OUT / 'v05c.json').write_text(json.dumps(res, indent=1, default=str) + '\n')
print(json.dumps(res, indent=1, default=str))
sys.exit(1 if fails else 0)
