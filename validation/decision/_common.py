"""Shared helpers for the decision-layer validator scripts (independent of engine.decision*).

Run any script from the repo root:  .venv-data/bin/python -B validation/decision/<script>.py
Only rasterio/numpy/shapely/stdlib are used to read the originals. engine.* is imported only
for the objects under test (read_store, evaluate_codes, fast_select_cells, ...).
"""
from fractions import Fraction
import json
import math
from pathlib import Path
import sys

import numpy as np
import rasterio

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
ART = ROOT / 'artifacts/decision'
HANSEN = {b: ROOT / f'data/public/hansen_{b}_sample.tif' for b in ('treecover2000', 'lossyear', 'datamask')}
JRC_CHIP = ROOT / 'data/experimental/jrc/JRC_GFC2020_V4_N10_E90_company-bbox.tif'
PLOTS_GEOJSON = ROOT / 'data/company-sample/2026-10-12/200001-17plots-valid.geojson'
OUT = Path(__file__).resolve().parent / 'out'
OUT.mkdir(exist_ok=True)

UNKNOWN, WATER, LAND = 0, 1, 2  # contract convention from the plan: 0 unknown, 1 water, 2+6*forest_state+post_index


def read_raw():
    """Raw arrays, validity masks and transforms straight from rasterio."""
    out = {}
    for name, path in HANSEN.items():
        with rasterio.open(path) as s:
            out[name] = dict(v=s.read(1), m=s.read_masks(1) != 0, t=tuple(s.transform)[:6], shape=s.shape)
    with rasterio.open(JRC_CHIP) as s:
        out['jrc'] = dict(v=s.read(1), m=s.read_masks(1) != 0, t=tuple(s.transform)[:6], shape=s.shape)
    return out


def axis_index(origin, step, n, jorigin, jstep):
    """Exact (Fraction) JRC index for each Hansen centre along one axis.

    Returns (floor index list, fractional offset list in JRC cell units) with rational arithmetic on the
    exact binary values of the float transforms.
    """
    o, s = Fraction(origin), Fraction(step)
    jo, js = Fraction(jorigin), Fraction(jstep)
    idx, frac = [], []
    for k in range(n):
        x = o + (k + Fraction(1, 2)) * s
        q = (x - jo) / js
        f = math.floor(q)
        idx.append(f)
        frac.append(q - f)
    return idx, frac


def independent_facts(raw):
    """Per Hansen cell facts from the originals, own code (exact rational JRC lookup).

    Returns dict of arrays: land_class ('u','w','l' as 0/1/2), forest_state (0 nonforest, 1 forest, 2 unknown),
    year (0 none else 2021..2025), plus jrc row/col index arrays and the min distance to a JRC cell boundary.
    """
    h, w = raw['lossyear']['shape']
    a, _, c, _, e, f = raw['lossyear']['t']
    ja, _, jc, _, je, jf = raw['jrc']['t']
    jr, frow = axis_index(f, e, h, jf, je)
    jcx, fcol = axis_index(c, a, w, jc, ja)
    jr, jcx = np.array(jr, np.int64), np.array(jcx, np.int64)
    margin = max(max(abs(float(v) - .5) for v in frow), max(abs(float(v) - .5) for v in fcol))  # max deviation of a Hansen centre from a JRC cell centre, in JRC cells
    JV, JM = raw['jrc']['v'], raw['jrc']['m']
    jh, jw = JV.shape
    rin = (jr >= 0) & (jr < jh)
    cin = (jcx >= 0) & (jcx < jw)
    forest = np.full((h, w), 2, np.uint8)
    rr, cc = np.where(rin, jr, 0)[:, None], np.where(cin, jcx, 0)[None, :]
    ok = rin[:, None] & cin[None, :] & JM[rr, cc]
    forest[ok & (JV[rr, cc] == 0)] = 0
    forest[ok & (JV[rr, cc] == 1)] = 1
    L, D = raw['lossyear']['v'], raw['datamask']['v']
    known = raw['treecover2000']['m'] & raw['lossyear']['m'] & raw['datamask']['m']  # all three band masks, as v1's known_bands (changed 15 Oct: the first pass ignored treecover's)
    land = np.zeros((h, w), np.uint8)
    land[known & (D == 1)] = 2
    land[known & (D == 2)] = 1
    year = np.where(L >= 21, 2000 + L.astype(np.int32), 0).astype(np.int32)
    return dict(land=land, forest=forest, year=year, jrow=jr, jcol=jcx, margin=margin, loss=L)


def facts_to_codes(F, level):
    """Contract code from facts (spec in docs/lab/decision-layer-plan.md)."""
    land, forest, year = F['land'], F['forest'], F['year']
    y = year.copy()
    if level == 'eudr-decision.v1':
        y = np.where(forest == 0, 0, y)
    post = np.where(y > 0, y - 2020, 0)
    codes = np.zeros(land.shape, np.uint8)
    codes[land == 1] = WATER
    is_land = land == 2
    codes[is_land] = (LAND + 6 * forest + post)[is_land]
    return codes


def reduce_facts(cells, outside, level):
    """Own reducer from the contract prose. cells: list of (land, forest, year) tuples for in-chip cells."""
    land_cells = [t for t in cells if t[0] == 2]
    unknown = outside + sum(1 for t in cells if t[0] == 0)
    water = sum(1 for t in cells if t[0] == 1)

    def yr(t):
        return 0 if (level == 'eudr-decision.v1' and t[1] == 0) else t[2]

    analytical = len(land_cells) > 0
    fc = {n: sum(1 for t in land_cells if t[1] == i) for i, n in enumerate(('nonforest', 'forest', 'unknown'))}
    defo = {str(y): sum(1 for t in land_cells if t[1] == 1 and yr(t) == y) for y in range(2021, 2026)}
    unk_loss = sum(1 for t in land_cells if t[1] == 2 and yr(t) > 0)

    def tri(n, blockers):
        if not analytical:
            return None
        return True if n > 0 else (False if blockers == 0 else None)

    out = {'contract': level, 'selected_cell_count': len(cells) + outside, 'out_of_coverage_cell_count': outside,
           'valid_land_cell_count': len(land_cells), 'water_cell_count': water, 'unknown_cell_count': unknown,
           'forest_2020': {'cell_counts': fc if analytical else None,
                           'present': tri(fc['forest'], unknown + fc['unknown'])},
           'deforestation_after_2020': {'yearly_cell_counts': defo if analytical else None,
                                        'cell_count': sum(defo.values()) if analytical else None,
                                        'present': tri(sum(defo.values()), unknown + unk_loss)}}
    if level == 'eudr-screen.v1':
        loss = {str(y): sum(1 for t in land_cells if yr(t) == y) for y in range(2021, 2026)}
        periods = {}
        for key, (lo, hi) in {'2021-2023': (2021, 2023), '2024-2025': (2024, 2025)}.items():
            n = sum(loss[str(y)] for y in range(lo, hi + 1))
            periods[key] = {'observed_loss_cell_count': n if analytical else None, 'mapped_loss_present': tri(n, unknown)}
        out['hansen_loss_after_2020'] = {'yearly_cell_counts': loss if analytical else None, 'periods': periods}
    out['support'] = ('none' if out['selected_cell_count'] == 0 or not land_cells else
                      'partial' if unknown or fc['unknown'] else 'complete')
    return out


def load_plots():
    gj = json.loads(PLOTS_GEOJSON.read_text())
    plots = [{'plot_id': f['properties']['ProductionPlace'], 'geometry': f['geometry']} for f in gj['features']]
    return sorted(plots, key=lambda p: p['plot_id'])


# ---- exact selection oracle -------------------------------------------------------------
def _ring_segments(geometry):
    polys = [geometry['coordinates']] if geometry['type'] == 'Polygon' else geometry['coordinates']
    out = []
    for rings in polys:
        out.append([[(Fraction(x), Fraction(y)) for x, y in ring] for ring in rings])
    return out


def _on_segment(p, a, b):
    (px, py), (ax, ay), (bx, by) = p, a, b
    cross = (bx - ax) * (py - ay) - (by - ay) * (px - ax)
    return cross == 0 and min(ax, bx) <= px <= max(ax, bx) and min(ay, by) <= py <= max(ay, by)


def _ring_state(p, ring):
    """'boundary', or inside flag by exact even-odd crossing with the half-open rule."""
    inside = False
    px, py = p
    for a, b in zip(ring[:-1], ring[1:]):
        if _on_segment(p, a, b):
            return 'boundary'
        (ax, ay), (bx, by) = a, b
        if (ay > py) != (by > py):
            # x of crossing > px  <=>  strictly to the right of the point
            t = (py - ay) / (by - ay)
            if ax + t * (bx - ax) > px:
                inside = not inside
    return inside


def exact_covers(p, parts):
    for rings in parts:
        shell = _ring_state(p, rings[0])
        if shell == 'boundary':
            return True
        if not shell:
            continue
        in_hole = False
        for hole in rings[1:]:
            st = _ring_state(p, hole)
            if st == 'boundary':
                return True
            if st:
                in_hole = True
                break
        if not in_hole:
            return True
    return False


def exact_select(transform, geometry, pad=2):
    """Exact (rows, cols) of covered Hansen centres; boundary-inclusive; own rational arithmetic.

    Centres are the float64 values c + (k + .5) * a (the rule's definition), taken as exact rationals.
    """
    af, cf, ef, ff = transform[0], transform[2], transform[4], transform[5]
    a, c, e, f = Fraction(af), Fraction(cf), Fraction(ef), Fraction(ff)
    parts = _ring_segments(geometry)
    xs = [x for rings in parts for ring in rings for x, _ in ring]
    ys = [y for rings in parts for ring in rings for _, y in ring]
    c0, c1 = math.floor((min(xs) - c) / a) - pad, math.ceil((max(xs) - c) / a) + pad
    r0, r1 = math.floor((max(ys) - f) / e) - pad, math.ceil((min(ys) - f) / e) + pad
    rows, cols = [], []
    for r in range(r0, r1 + 1):
        py = Fraction(ff + (r + .5) * ef)
        for k in range(c0, c1 + 1):
            px = Fraction(cf + (k + .5) * af)
            if exact_covers((px, py), parts):
                rows.append(r)
                cols.append(k)
    return np.array(rows, np.int64), np.array(cols, np.int64)


def same_json(a, b):
    return json.dumps(a, sort_keys=True) == json.dumps(b, sort_keys=True)
