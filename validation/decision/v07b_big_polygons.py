"""Claim 7 addendum: very large vertex counts, huge row spans and a time check for fast_select_cells vs select_cells."""
import math, time, json, sys
import _common  # noqa: F401  (puts the repo root on sys.path)
import numpy as np
from engine import decision_index as di
from engine.query import select_cells
BASE = {'shape': [604, 1233], 'transform': [0.00025, 0.0, 98.77225, 0.0, -0.00025, 8.582], 'crs': 'EPSG:4326'}
a, c, e, f = 0.00025, 98.77225, -0.00025, 8.582
res = {}
def ring(n, rx, ry, cx, cy, wobble=0.0):
    ang = np.linspace(0, 2 * math.pi, n, endpoint=False)
    r = 1 + wobble * np.sin(37 * ang)
    pts = [[cx + math.cos(t) * rx * q, cy + math.sin(t) * ry * q] for t, q in zip(ang, r)]
    return pts + pts[:1]
cases = {
    'circle_99990_vertices_r300': {'type': 'Polygon', 'coordinates': [ring(99_990, 300 * a, 300 * -e, c + 600 * a, f + 302 * e)]},
    'wobbly_50000_vertices_r250': {'type': 'Polygon', 'coordinates': [ring(50_000, 250 * a, 250 * -e, c + 600 * a, f + 302 * e, .05)]},
    'comb_20000_teeth': {'type': 'Polygon', 'coordinates': [[[c + (i // 2 * 0.06 + (0.03 if i % 4 in (1, 2) else 0)) * a * 10, f + (50 + (i % 2) * 200) * e] for i in range(2000)] + [[c + 1200 * a, f + 300 * e], [c, f + 300 * e], [c, f + 50 * e]]]},
}
for name, geom in cases.items():
    try:
        t = time.perf_counter(); r0, c0 = select_cells(BASE, geom); t1 = time.perf_counter() - t
    except ValueError as ex:
        r0 = None; t1 = 0; ref = str(ex)
    try:
        t = time.perf_counter(); r1, c1 = di.fast_select_cells(BASE, geom); t2 = time.perf_counter() - t
    except ValueError as ex:
        r1 = None; t2 = 0
    ok = (r0 is None and r1 is None) or (r0 is not None and r1 is not None and np.array_equal(r0, r1) and np.array_equal(c0, c1))
    res[name] = {'equal': bool(ok), 'cells': None if r0 is None else int(len(r0)), 'select_cells_ms': round(t1 * 1e3, 1), 'fast_ms': round(t2 * 1e3, 1)}
print(json.dumps(res, indent=1))
sys.exit(0 if all(v['equal'] for v in res.values()) else 1)
