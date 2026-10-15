"""Claim 7: fast_select_cells vs engine.query.select_cells on adversarial inputs beyond the shipped tests.

Categories (seeded): ulp-perturbed lattice triangles/quads/holes, needles and slivers, far-from-origin and
odd-scale grids, collinear vertex chains, repeated vertices, multipolygons touching at centres, holes touching
the shell at a vertex, spikes, nearly-degenerate rings, rows-chunking at tiny MAX_ROW_PAIRS.
Exit 0 when there are no mismatches. Writes out/v07.json (and out/v07_mismatches.json on failure).
"""
import json
import math
import random
import sys
import time
from unittest import mock

import numpy as np

from _common import OUT
from engine import decision_index as di
from engine.query import select_cells

SEED = int(sys.argv[1]) if len(sys.argv) > 1 else 424242
COUNT = int(sys.argv[2]) if len(sys.argv) > 2 else 400
rng = random.Random(SEED)
BASE = {'shape': [604, 1233], 'transform': [0.00025, 0.0, 98.77225, 0.0, -0.00025, 8.582], 'crs': 'EPSG:4326'}

GRIDS = {
    'chip': BASE,
    'origin_unit': dict(BASE, transform=[1.0, 0.0, 0.0, 0.0, -1.0, 0.0]),
    'fine_1e-6': dict(BASE, transform=[1e-6, 0.0, 98.77225, 0.0, -1e-6, 8.582]),
    'fine_1e-9': dict(BASE, transform=[1e-9, 0.0, 98.77225, 0.0, -1e-9, 8.582]),
    'fine_1e-12': dict(BASE, transform=[1e-12, 0.0, 98.77225, 0.0, -1e-12, 8.582]),
    'far_1e5': dict(BASE, transform=[0.00025, 0.0, 1e5 + 0.1, 0.0, -0.00025, -1e5 + 0.3]),
    'far_1e8': dict(BASE, transform=[0.00025, 0.0, -1e8 + 0.1, 0.0, -0.00025, 1e8 + 0.3]),
    'anisotropic': dict(BASE, transform=[0.0003, 0.0, 98.77225, 0.0, -0.00041, 8.582]),
    'coarse_0.1': dict(BASE, transform=[0.1, 0.0, -180.0, 0.0, -0.1, 90.0]),
    'odd_binary': dict(BASE, transform=[2.0 ** -12, 0.0, 98.0, 0.0, -2.0 ** -12, 8.5]),  # exact binary lattice: exact ties everywhere
}


def nudge(x, k):
    for _ in range(abs(k)):
        x = float(np.nextafter(x, math.inf if k > 0 else -math.inf))
    return x


class G:
    def __init__(self, meta, c0=None, r0=None):
        self.m = meta
        t = meta['transform']
        self.a, self.c, self.e, self.f = t[0], t[2], t[4], t[5]
        self.c0 = rng.randrange(20, 500) if c0 is None else c0
        self.r0 = rng.randrange(20, 400) if r0 is None else r0

    def cx(self, col, k=0):
        return nudge(self.c + (col + .5) * self.a, k)

    def cy(self, row, k=0):
        return nudge(self.f + (row + .5) * self.e, k)

    def p(self, col, row, kx=0, ky=0):
        return [self.cx(self.c0 + col, kx), self.cy(self.r0 + row, ky)]


def kk():
    return rng.choice((0, 0, 0, 1, -1, 1, -1, 2, -2))


def close(pts):
    pts = [list(p) for p in pts]
    return pts + [list(pts[0])]


def poly(*rings):
    return {'type': 'Polygon', 'coordinates': [close(r) for r in rings]}


def quad(g, c0, r0, c1, r1, ulp=True):
    f = (lambda: kk()) if ulp else (lambda: 0)
    return [g.p(c0, r0, f(), f()), g.p(c1, r0, f(), f()), g.p(c1, r1, f(), f()), g.p(c0, r1, f(), f())]


def gen_ulp_tri(g):
    pts = [g.p(rng.randrange(0, 12), rng.randrange(0, 12), kk(), kk()) for _ in range(3)]
    return poly(pts)


def gen_ulp_quad(g):
    c0, r0 = rng.randrange(0, 6), rng.randrange(0, 6)
    return poly(quad(g, c0, r0, c0 + rng.randrange(1, 10), r0 + rng.randrange(1, 10)))


def gen_ulp_hole(g):
    c0, r0, s = rng.randrange(0, 4), rng.randrange(0, 4), rng.randrange(6, 14)
    outer = quad(g, c0, r0, c0 + s, r0 + s)
    hc, hr = c0 + rng.randrange(1, 3), r0 + rng.randrange(1, 3)
    hole = quad(g, hc, hr, hc + rng.randrange(1, s - 3), hr + rng.randrange(1, s - 3))
    return poly(outer, hole)


def gen_needle(g):
    x0 = g.cx(g.c0 + rng.randrange(0, 8), kk())
    w = 10.0 ** -rng.randrange(8, 18) * max(1.0, abs(g.a) * 1e3)
    if rng.random() < .5:  # vertical needle across many rows
        top, bot = g.cy(g.r0, kk()), g.cy(g.r0 + rng.randrange(2, 40), kk())
        return poly([[x0, top], [x0 + w, bot], [x0, bot]] if rng.random() < .5 else [[x0, top], [x0 - w, (top + bot) / 2], [x0 + w, bot]])
    y = g.cy(g.r0 + rng.randrange(0, 8), kk())  # needle lying along a centre row
    x1 = g.cx(g.c0 + 8 + rng.randrange(1, 30), kk())
    return poly([[x0, y], [x1, y], [x1, nudge(y, rng.choice((1, -1, 2, -2)))]])


def gen_sliver(g):
    y = g.cy(g.r0 + rng.randrange(0, 8), kk())
    x0, x1 = g.cx(g.c0, kk()), g.cx(g.c0 + rng.randrange(1, 25), kk())
    return poly([[x0, y], [x1, y], [x1, nudge(y, rng.choice((1, 2, -1, -2)))], [x0, nudge(y, rng.choice((1, 2, -1, -2)))]])


def gen_collinear(g):
    mode = rng.choice(('vertical', 'horizontal', 'diagonal', 'steep'))
    n = rng.randrange(3, 120)
    if mode == 'vertical':
        chain = [g.p(0, i, kk() if rng.random() < .3 else 0, 0) for i in range(n)]
        return poly(chain + [g.p(8, n - 1), g.p(8, 0)])
    if mode == 'horizontal':
        chain = [g.p(i, 0, 0, kk() if rng.random() < .3 else 0) for i in range(n)]
        return poly(chain + [g.p(n - 1, 8), g.p(0, 8)])
    if mode == 'diagonal':
        chain = [g.p(i, i, kk() if rng.random() < .2 else 0, 0) for i in range(n)]
        return poly(chain + [g.p(n - 1, 0)])
    q = rng.randrange(2, 7)
    chain = [g.p(i, i * q, 0, kk() if rng.random() < .2 else 0) for i in range(n // 3 + 2)]
    return poly(chain + [g.p(n // 3 + 8, 0)])


def gen_dups(g):
    base = rng.choice((gen_ulp_tri, gen_ulp_quad, gen_needle))(g)
    ring = base['coordinates'][0][:-1]
    out = []
    for p in ring:
        out.append(p)
        for _ in range(rng.choice((0, 0, 1, 2))):
            out.append(list(p))
    return {'type': 'Polygon', 'coordinates': [close(out)]}


def gen_multi_touch(g):
    parts = []
    k = rng.randrange(2, 4)
    for i in range(k):  # squares touching diagonally at a centre (or ulp-near it)
        o = i * 3
        parts.append([close(quad(g, o, o, o + 3, o + 3, ulp=rng.random() < .5))])
    if rng.random() < .5:
        parts.append([close(quad(g, 12, 0, 15, 4))])
    return {'type': 'MultiPolygon', 'coordinates': parts}


def gen_hole_touch(g):
    s = rng.randrange(8, 16)
    shell = [g.p(0, 0), g.p(s, 0), g.p(s, s), g.p(0, s)]
    ulp = rng.random() < .5
    j = (lambda: kk()) if ulp else (lambda: 0)
    mode = rng.choice(('vertex_on_edge', 'vertex_on_vertex', 'two_holes_touch', 'hole_vertex_on_row'))
    if mode == 'vertex_on_edge':
        t = rng.randrange(2, s - 2)
        hole = [g.p(t, 0), g.p(t + 3, 4, j(), j()), g.p(t - 1, 5, j(), j())]
        return poly(shell, hole)
    if mode == 'vertex_on_vertex':
        hole = [g.p(0, 0), g.p(4, 2, j(), j()), g.p(2, 4, j(), j())]
        return poly(shell, hole)
    if mode == 'two_holes_touch':
        h1 = [g.p(2, 2), g.p(5, 2), g.p(5, 5), g.p(2, 5)]
        h2 = [g.p(5, 5, j(), j()), g.p(8, 5), g.p(8, 8), g.p(5, 8)]
        return poly(shell + [], h1, h2) if s >= 10 else poly(shell, h1)
    hole = [g.p(3, 3), g.p(6, 3, j(), j()), g.p(4, 6, j(), j())]
    return poly(shell, hole)


def gen_spike(g):  # concave notch whose tip is on / ulp-near a centre row and column
    s = rng.randrange(6, 14)
    tipx, tipy = rng.randrange(2, s - 2), rng.randrange(2, s - 2)
    ring = [g.p(0, 0), g.p(tipx - 1, 0), g.p(tipx, tipy, kk(), kk()), g.p(tipx + 1, 0), g.p(s, 0), g.p(s, s), g.p(0, s)]
    return poly(ring)


def gen_random_lattice(g):
    n = rng.randrange(4, 16)
    cx_, cy_ = rng.randrange(4, 10), rng.randrange(4, 10)
    angs = sorted(rng.uniform(0, 2 * math.pi) for _ in range(n))
    pts = [g.p(cx_ + round(rng.uniform(1, 6) * math.cos(t)), cy_ + round(rng.uniform(1, 6) * math.sin(t)), kk(), kk()) for t in angs]
    return poly(pts)


def gen_staircase(g):
    pts = [g.p(0, 0)]
    c = r = 0
    for _ in range(rng.randrange(3, 25)):
        c += rng.randrange(1, 3)
        pts.append(g.p(c, r, kk() if rng.random() < .3 else 0, kk() if rng.random() < .3 else 0))
        r += rng.randrange(1, 3)
        pts.append(g.p(c, r, kk() if rng.random() < .3 else 0, kk() if rng.random() < .3 else 0))
    pts += [g.p(c + 1, r + 2), g.p(-1, r + 2)]
    return poly(pts)


GENS = {'ulp_tri': gen_ulp_tri, 'ulp_quad': gen_ulp_quad, 'ulp_hole': gen_ulp_hole, 'needle': gen_needle, 'sliver': gen_sliver,
        'collinear': gen_collinear, 'dups': gen_dups, 'multi_touch': gen_multi_touch, 'hole_touch': gen_hole_touch,
        'spike': gen_spike, 'random_lattice': gen_random_lattice, 'staircase': gen_staircase}


def outcome(fn, meta, geom):
    try:
        r, c = fn(meta, geom)
        return ('ok', r.dtype.str, r.tolist(), c.tolist())
    except ValueError as e:
        return ('err', str(e))
    except BaseException as e:  # noqa: BLE001
        return ('EXC', type(e).__name__, str(e)[:80])


stats = {}
per_grid = {}
mismatches = []
t0 = time.time()
for gname, meta in GRIDS.items():
    for cat, gen in GENS.items():
        s = stats.setdefault(cat, {'generated': 0, 'accepted': 0, 'rejected_identically': 0, 'mismatches': 0, 'selected_cells': 0, 'exc': 0})
        for _ in range(COUNT // len(GRIDS) + 1):
            g = G(meta)
            try:
                geom = gen(g)
            except Exception:
                continue
            a, b = outcome(select_cells, meta, geom), outcome(di.fast_select_cells, meta, geom)
            s['generated'] += 1
            pg = per_grid.setdefault(gname, {'generated': 0, 'accepted': 0, 'selected_cells': 0, 'mismatches': 0})
            pg['generated'] += 1
            if a[0] == 'EXC' or b[0] == 'EXC':
                s['exc'] += 1
            if a != b:
                s['mismatches'] += 1
                pg['mismatches'] += 1
                if len(mismatches) < 10:
                    mismatches.append({'grid': gname, 'category': cat, 'geometry': geom, 'select_cells': a[:2] if a[0] != 'ok' else ('ok', len(a[2])),
                                       'fast': b[:2] if b[0] != 'ok' else ('ok', len(b[2]))})
            elif a[0] == 'ok':
                s['accepted'] += 1
                s['selected_cells'] += len(a[2])
                pg['accepted'] += 1
                pg['selected_cells'] += len(a[2])
            else:
                s['rejected_identically'] += 1
# row-chunk stress: same geometries forced through 1-row chunks
chunk_mismatch = 0
chunk_n = 0
with mock.patch.object(di, 'MAX_ROW_PAIRS', 1):
    for cat, gen in GENS.items():
        for _ in range(25):
            g = G(BASE)
            geom = gen(g)
            chunk_n += 1
            if outcome(select_cells, BASE, geom) != outcome(di.fast_select_cells, BASE, geom):
                chunk_mismatch += 1
tot = {k: sum(s[k] for s in stats.values()) for k in ('generated', 'accepted', 'rejected_identically', 'mismatches', 'exc', 'selected_cells')}
res = {'seed': SEED, 'grids': list(GRIDS), 'per_category': stats, 'per_grid': per_grid, 'totals': tot, 'row_chunk_1_pair': {'compared': chunk_n, 'mismatches': chunk_mismatch},
       'seconds': round(time.time() - t0, 1)}
(OUT / 'v07.json').write_text(json.dumps(res, indent=1) + '\n')
if mismatches:
    (OUT / 'v07_mismatches.json').write_text(json.dumps(mismatches, indent=1) + '\n')
print(json.dumps(res, indent=1))
sys.exit(1 if tot['mismatches'] or tot['exc'] or chunk_mismatch else 0)
