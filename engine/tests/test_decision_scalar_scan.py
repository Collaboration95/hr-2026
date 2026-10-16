"""The pure-Python scan for small polygons must equal select_cells and the array scan: cells, rejections, and the fused reduction.

Synthetic grids and rasters only (no plot data): seeded polygons that sit on, an ulp from, or a tolerance from cell centres.
"""
import math
import unittest
from unittest import mock
import warnings

import numpy as np

from engine import decision, decision_index as di
from engine.decision_benchmark import synthetic_polygons
from engine.query import select_cells
from engine.tests.test_adversarial import INVALID_GEOMETRIES
from engine.tests.test_decision_index import fuzz_geometries

LEVEL = decision.DECISION_VERSION
SHAPE = [400, 600]
GRIDS = {  # the dyadic ones put cell centres exactly on slanted edges, where the computed crossing is an ulp off
    'hansen_like': [0.00025, 0, 100.0, 0, -0.00025, 10.0],
    'unit': [1.0, 0, 0.0, 0, -1.0, 100.0],
    'half': [.5, 0, -10.25, 0, -.25, 7.75],
    'nonsquare': [0.0003, 0, 12.3456, 0, -0.0002, -40.123],
}


def meta_for(transform):
    return {'transform': transform, 'crs': 'EPSG:4326', 'shape': SHAPE, 'level': LEVEL}


def result(fn, *args):
    """Comparable outcome: bytes of the arrays or repr of the answer, or the exception type and message."""
    try:
        with warnings.catch_warnings():
            warnings.simplefilter('ignore')
            out = fn(*args)
    except Exception as exc:
        return 'err', type(exc).__name__, str(exc)
    if isinstance(out, tuple):
        return 'ok', [(v.dtype.str, v.shape, v.tobytes()) for v in out]
    return 'ok', repr(out)


def forced(edge_rows, cells):
    def select(metadata, geometry):
        with mock.patch.object(di, 'SCALAR_EDGE_ROWS', edge_rows), mock.patch.object(di, 'SCALAR_CELLS', cells), \
                mock.patch.object(di, 'SCALAR_CROSSINGS', 10 ** 9):  # and no sawtooth guard
            return di.fast_select_cells(metadata, geometry)

    def summarize(codes, header, geometry, level):
        with mock.patch.object(di, 'SCALAR_EDGE_ROWS', edge_rows), mock.patch.object(di, 'SCALAR_CELLS', cells), \
                mock.patch.object(di, 'SCALAR_CROSSINGS', 10 ** 9):
            return di.fast_summarize(codes, header, geometry, level)
    select.summarize = summarize
    return select


ARRAY, SCALAR = forced(0, 0), forced(10 ** 9, 10 ** 9)  # the array scan for everything; the scalar scan for everything it can take


def adversarial(meta, rng, n):
    """Polygons built on the centre lattice: vertices on centres, ulp and tolerance offsets, edges and rows through
    centres, holes, multipolygons, slivers, tiny shapes, repeated points, partly or wholly outside the chip."""
    a, _, c, _, e, f = meta['transform']

    def cx(col):
        return c + (col + .5) * a

    def cy(row):
        return f + (row + .5) * e

    def nudge(v, kind):
        if kind == 1:  # a few ulps
            k = int(rng.choice([1, -1, 2, -2, 3, -3, 8, -8]))
            for _ in range(abs(k)):
                v = float(np.nextafter(v, np.inf if k > 0 else -np.inf))
            return v
        if kind == 2:  # around the scan tolerance
            tol = di.TOL_ABS + di.TOL_REL * abs(v)
            return v + float(rng.choice([.5, .99, 1.0, 1.01, 2.0])) * tol * float(rng.choice([-1, 1]))
        if kind == 3:
            return v + float(rng.choice([1e-14, 1e-12, 1e-10, 1e-8, 1e-6])) * float(rng.choice([-1, 1]))
        if kind == 4:
            return v + float(rng.uniform(-.5, .5)) * abs(a)
        return v

    def pt(col, row, k=0):
        return [nudge(cx(col), k), nudge(cy(row), k)]

    out = []
    for _ in range(n):
        r0, c0 = int(rng.integers(-30, SHAPE[0] + 30)), int(rng.integers(-30, SHAPE[1] + 30))
        if rng.random() < .03:
            r0, c0 = int(rng.integers(-5000, 5000)), int(rng.integers(-5000, 5000))
        kind, k = int(rng.integers(0, 15)), int(rng.choice([0, 0, 0, 1, 2, 3, 4]))
        if kind == 0:  # lattice vertices
            offs = {(int(rng.integers(-5, 6)), int(rng.integers(-5, 6))) for _ in range(int(rng.integers(3, 9)))}
            pts = [pt(c0 + dc, r0 + dr, k) for dr, dc in offs]
            mx, my = sum(p[0] for p in pts) / len(pts), sum(p[1] for p in pts) / len(pts)
            pts.sort(key=lambda p: math.atan2(p[1] - my, p[0] - mx))
            rings = [pts]
        elif kind == 1:  # rectangle with independently nudged sides
            w, h = int(rng.integers(0, 7)), int(rng.integers(0, 7))
            xl, xr = sorted((pt(c0, r0, k)[0], pt(c0 + w, r0, k)[0]))
            yb, yt = sorted((pt(c0, r0, k)[1], pt(c0, r0 + h, k)[1]))
            rings = [[[xl, yb], [xr, yb], [xr, yt], [xl, yt]]]
        elif kind == 2:  # triangle on lattice vertices: other centres lie on its edges
            p, q = int(rng.integers(1, 12)), int(rng.integers(1, 12))
            rings = [[pt(c0, r0, k), pt(c0 + p, r0 + q, k), pt(c0 + p, r0, k)]]
        elif kind == 3:  # diamond
            d = int(rng.integers(1, 6))
            rings = [[pt(c0, r0 - d, k), pt(c0 + d, r0, k), pt(c0, r0 + d, k), pt(c0 - d, r0, k)]]
        elif kind == 4:  # horizontal edges on centre rows, slanted sides
            d = int(rng.integers(1, 8))
            rings = [[pt(c0, r0), pt(c0 + d, r0), pt(c0 + d + int(rng.integers(-2, 3)), r0 + d, k), pt(c0 + int(rng.integers(-2, 3)), r0 + d, k)]]
        elif kind == 5:  # shell with holes
            w, h = int(rng.integers(4, 12)), int(rng.integers(4, 12))
            rings = [[pt(c0, r0, k), pt(c0 + w, r0, k), pt(c0 + w, r0 + h, k), pt(c0, r0 + h, k)]]
            for _ in range(int(rng.integers(1, 3))):
                hc, hr, hw, hh = c0 + int(rng.integers(1, w - 1)), r0 + int(rng.integers(1, h - 1)), int(rng.integers(0, 2)), int(rng.integers(0, 2))
                rings.append([pt(hc, hr, k), pt(hc + hw, hr, k), pt(hc + hw, hr + hh, k), pt(hc, hr + hh, k)])
        elif kind == 6:  # staircase
            xs, ys = [c0], [r0]
            for _ in range(int(rng.integers(1, 5))):
                xs.append(xs[-1] + int(rng.integers(1, 5)))
                ys.append(ys[-1] + int(rng.integers(1, 5)))
            ring = [pt(xs[0], ys[0], k)]
            for i in range(1, len(xs)):
                ring += [pt(xs[i], ys[i - 1], k), pt(xs[i], ys[i], k)]
            rings = [ring + [pt(xs[0], ys[-1], k)]]
        elif kind == 7:  # sliver along a centre row or column
            s, d = float(rng.choice([0, 1e-15, 1e-13, 1e-12, 1e-10, 1e-9, 1e-7])), int(rng.integers(1, 12))
            if rng.random() < .5:
                y = nudge(cy(r0), k)
                rings = [[[cx(c0), y], [cx(c0 + d), y + s], [cx(c0 + d), y]]]
            else:
                x = nudge(cx(c0), k)
                rings = [[[x, cy(r0)], [x + s, cy(r0 + d)], [x, cy(r0 + d)]]]
        elif kind == 8:  # tiny, often selecting nothing
            s = float(rng.choice([1e-15, 1e-13, 1e-11, 1e-9, 1e-7, .1 * abs(a), .6 * abs(a)]))
            x, y = cx(c0) + float(rng.uniform(-1, 1)) * abs(a) * (rng.random() < .3), cy(r0)
            rings = [[[x - s, y - s], [x + s, y - s], [x + s, y + s], [x - s, y + s]]] if rng.random() < .5 else [[[x - s, y], [x, y - s], [x + s, y]]]
        elif kind == 9:  # repeated and collinear points
            ring = []
            for p in (pt(c0, r0), pt(c0 + 3, r0), pt(c0 + 3, r0 + 3), pt(c0, r0 + 3)):
                ring += [p, list(p)] if rng.random() < .5 else [p]
            if rng.random() < .5:
                ring.insert(1, [(ring[0][0] + ring[1][0]) / 2, ring[0][1]])
            rings = [ring]
        elif kind == 10:  # bowtie: invalid
            rings = [[pt(c0, r0, k), pt(c0 + 4, r0 + 4, k), pt(c0 + 4, r0, k), pt(c0, r0 + 4, k)]]
        elif kind == 11:  # larger rounded polygon (the array scan takes it by default)
            ang, rad = np.sort(rng.uniform(0, 2 * math.pi, int(rng.integers(6, 30)))), rng.uniform(3, 25, 30)
            rings = [[pt(c0 + int(round(math.cos(t) * q)), r0 + int(round(math.sin(t) * q)), k) for t, q in zip(ang, rad)]]
        elif kind == 12:  # free float polygon
            ang, rad = np.sort(rng.uniform(0, 2 * math.pi, int(rng.integers(3, 12)))), rng.uniform(.3, 9, 12)
            rings = [[[cx(c0) + math.cos(t) * q * a, cy(r0) + math.sin(t) * q * -e] for t, q in zip(ang, rad)]]
        elif kind == 13:  # multipolygon of touching and overlapping rectangles
            parts = []
            for _ in range(int(rng.integers(2, 4))):
                gr, gc, w, h = r0 + int(rng.integers(-4, 5)), c0 + int(rng.integers(-4, 5)), int(rng.integers(0, 4)), int(rng.integers(0, 4))
                ring = [pt(gc, gr, k), pt(gc + w, gr, k), pt(gc + w, gr + h, k), pt(gc, gr + h, k)]
                parts.append([ring + [list(ring[0])]])
            out.append({'type': 'MultiPolygon', 'coordinates': parts})
            continue
        else:  # long exact diagonals: many centres exactly on the edge, large denominators
            u, v, g = int(rng.integers(1, 7)), int(rng.integers(1, 7)), int(rng.integers(3, 30))
            rings = [[pt(c0, r0), pt(c0 + u * g, r0 + v * g), pt(c0 + u * g, r0)]]
        rings = [ring + [list(ring[0])] for ring in rings]
        if rng.random() < .1:  # integers where exact
            rings = [[[int(x) if float(x).is_integer() and abs(x) < 2 ** 53 else x for x in p] for p in ring] for ring in rings]
        out.append({'type': 'Polygon', 'coordinates': rings})
    return out


def malformed(meta):
    a, _, c, _, e, f = meta['transform']
    x, y = c + 10.5 * a, f + 10.5 * e
    sq = [[x, y], [x + a, y], [x + a, y + e], [x, y + e], [x, y]]
    nan, inf = float('nan'), float('inf')
    cases = dict(INVALID_GEOMETRIES)
    cases.update({
        'none': None, 'list': [], 'int': 5, 'empty': {}, 'no_coordinates': {'type': 'Polygon'}, 'point': {'type': 'Point', 'coordinates': [x, y]},
        'coordinates_none': {'type': 'Polygon', 'coordinates': None}, 'ring_empty': {'type': 'Polygon', 'coordinates': [[]]},
        'ring_three': {'type': 'Polygon', 'coordinates': [sq[:3]]}, 'ring_open': {'type': 'Polygon', 'coordinates': [sq[:4]]},
        'multi_empty': {'type': 'MultiPolygon', 'coordinates': []}, 'tuple_positions': {'type': 'Polygon', 'coordinates': [[tuple(p) for p in sq]]},
        'tuple_polygon': {'type': 'Polygon', 'coordinates': tuple([sq])}, 'three_coordinates': {'type': 'Polygon', 'coordinates': [[p + [0.0] for p in sq]]},
        'bool_coordinates': {'type': 'Polygon', 'coordinates': [[[True, False], [1, 0], [1, 1], [True, False]]]},
        'string_coordinates': {'type': 'Polygon', 'coordinates': [[[str(v) for v in p] for p in sq]]},
        'nan': {'type': 'Polygon', 'coordinates': [sq[:2] + [[nan, y]] + sq[3:]]}, 'inf': {'type': 'Polygon', 'coordinates': [sq[:2] + [[inf, y]] + sq[3:]]},
        'huge_int': {'type': 'Polygon', 'coordinates': [[[0, 0], [10 ** 400, 0], [1, 1], [0, 0]]]},
        'big_int': {'type': 'Polygon', 'coordinates': [[[0, 0], [10 ** 30, 0], [1, 1], [0, 0]]]},
        'huge_float': {'type': 'Polygon', 'coordinates': [[[-1e308, -1e308], [1e308, -1e308], [1e308, 1e308], [-1e308, 1e308], [-1e308, -1e308]]]},
        'sum_overflows': {'type': 'Polygon', 'coordinates': [[[1e308, 1e308], [1e308, 1e308], [-1e308, 0], [1e308, 1e308]]]},
        'float_subclass': {'type': 'Polygon', 'coordinates': [[[type('F', (float,), {})(v) for v in p] for p in sq]]},
        'numpy_scalars': {'type': 'Polygon', 'coordinates': [[[np.float64(v) for v in p] for p in sq]]},
        'bad_type': {'type': 'polygon', 'coordinates': [sq]}, 'dict_subclass': type('D', (dict,), {})({'type': 'Polygon', 'coordinates': [sq]}),
        'nested_too_deep': {'type': 'Polygon', 'coordinates': [[[[x, y]]]]}, 'point_ring': {'type': 'Polygon', 'coordinates': [[[x, y]] * 4]},
        'line_ring': {'type': 'Polygon', 'coordinates': [[[x, y], [x + a, y], [x + 2 * a, y], [x, y]]]},
        'spike': {'type': 'Polygon', 'coordinates': [[[x, y], [x + a, y], [x + a, y + e], [x + a, y], [x, y]]]},
        'hole_outside': {'type': 'Polygon', 'coordinates': [sq, [[x + 5 * a, y], [x + 6 * a, y], [x + 6 * a, y + e], [x + 5 * a, y]]]},
        'hole_is_shell': {'type': 'Polygon', 'coordinates': [sq, sq]}, 'overlapping_parts': {'type': 'MultiPolygon', 'coordinates': [[sq], [sq]]},
        'part_not_list': {'type': 'MultiPolygon', 'coordinates': [[sq], 5]}, 'ring_is_string': {'type': 'Polygon', 'coordinates': ['abc']},
        'point_is_none': {'type': 'Polygon', 'coordinates': [[None, None, None, None]]},
        'too_many_vertices': {'type': 'Polygon', 'coordinates': [[[x + i * 1e-9, y] for i in range(100_001)] + [[x, y]]]},
        'candidate_cap': {'type': 'Polygon', 'coordinates': [[[0, 0], [1, 0], [1, 1], [0, 0]]]},
    })
    return cases


def bad_metadata(meta):
    t = meta['transform']
    return {
        'rotated_b': dict(meta, transform=[t[0], .5, t[2], 0, t[4], t[5]]), 'rotated_d': dict(meta, transform=[t[0], 0, t[2], .5, t[4], t[5]]),
        'south_up': dict(meta, transform=[t[0], 0, t[2], 0, -t[4], t[5]]), 'west_up': dict(meta, transform=[-t[0], 0, t[2], 0, t[4], t[5]]),
        'zero_scale': dict(meta, transform=[0, 0, 0, 0, -1, 1]), 'nan': dict(meta, transform=[1, 0, float('nan'), 0, -1, 1]),
        'inf_last': dict(meta, transform=[1, 0, 0, 0, -1, float('inf')]), 'short': dict(meta, transform=[1, 0, 0]),
        'long': dict(meta, transform=list(t) + [0]), 'tuple': dict(meta, transform=tuple(t)), 'strings': dict(meta, transform=['a'] * 6),
        'string_inside': dict(meta, transform=[t[0], 'x', t[2], 0, t[4], t[5]]), 'none': dict(meta, transform=None),
        'dict': dict(meta, transform={k: 1 for k in 'abcdef'}), 'wrong_crs': dict(meta, crs='EPSG:3857'),
        'no_crs': {'transform': t}, 'no_transform': {'crs': 'EPSG:4326'}, 'bool': dict(meta, transform=[True, 0, 0, 0, -1, 0]),
        'numpy_array': dict(meta, transform=np.array(t)), 'numpy_scalars': dict(meta, transform=[np.float64(v) for v in t]),
        'huge_origin': dict(meta, transform=[t[0], 0, 1e95, 0, t[4], t[5]]), 'huge_scale': dict(meta, transform=[1e300, 0, 1e300, 0, -1e300, 1e300]),
        'tiny_scale': dict(meta, transform=[1e-300, 0, 0, 0, -1e-300, 0]),
    }


class ScalarScanTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        di._numpy()
        rng = np.random.default_rng(20261015)
        cls.codes = rng.integers(0, decision.CODE_COUNT, SHAPE, dtype=np.uint8)
        cls.meta = meta_for(GRIDS['hansen_like'])

    def assertSameSelection(self, metadata, geometry):
        want = result(select_cells, metadata, geometry)
        for name, select in (('default', di.fast_select_cells), ('array', ARRAY), ('scalar', SCALAR)):
            self.assertEqual(result(select, metadata, geometry), want, name)
        return want

    def assertSameAnswer(self, geometry, codes=None, header=None, level=LEVEL):
        codes, header = self.codes if codes is None else codes, header or self.meta
        want = result(decision.evaluate_store, codes, header, geometry, level)
        for name, select in (('default', di.fast_select_cells), ('array', ARRAY), ('scalar', SCALAR)):
            self.assertEqual(result(decision.evaluate_store, codes, header, geometry, level, select), want, name)
        return want

    def test_selection_equals_select_cells_on_adversarial_polygons(self):
        accepted = rejected = cells = 0
        for index, (name, transform) in enumerate(GRIDS.items()):
            metadata = meta_for(transform)
            for geometry in adversarial(metadata, np.random.default_rng(100 + index), 900 if index == 0 else 400):
                want = self.assertSameSelection(metadata, geometry)
                accepted += want[0] == 'ok'
                rejected += want[0] == 'err'
                cells += int(want[1][0][1][0]) if want[0] == 'ok' else 0
        self.assertGreater(accepted, 1500)
        self.assertGreater(rejected, 50)  # bowties and the like are rejected identically
        self.assertGreater(cells, 20_000)

    def test_selection_equals_select_cells_on_fuzz_and_synthetic_plots(self):
        for geometry in fuzz_geometries(self.meta, 1500, seed=9):
            self.assertSameSelection(self.meta, geometry)
        plots, _ = synthetic_polygons(150, 5, self.meta, self.codes >= decision.LAND)
        self.assertEqual(len(plots), 150)
        for plot in plots:
            self.assertEqual(self.assertSameSelection(self.meta, plot['geometry'])[0], 'ok')

    def test_rejections_are_identical(self):
        for name, geometry in malformed(self.meta).items():
            with self.subTest(case=name):
                self.assertSameSelection(self.meta, geometry)
                self.assertSameAnswer(geometry)
        a, _, c, _, e, f = self.meta['transform']
        square = {'type': 'Polygon', 'coordinates': [[[c, f], [c + 4 * a, f], [c + 4 * a, f + 4 * e], [c, f + 4 * e], [c, f]]]}
        for name, metadata in bad_metadata(self.meta).items():
            with self.subTest(grid=name):
                self.assertSameSelection(metadata, square)

    def test_fused_reduction_equals_the_generic_one(self):
        geometries = adversarial(self.meta, np.random.default_rng(7), 700) + fuzz_geometries(self.meta, 300, seed=3)
        for geometry in geometries:
            self.assertSameAnswer(geometry)
        # a plain selector (no summarize attribute) is unaffected, and a selector with one is reduced through it
        geometry = geometries[0]
        plain = lambda header, geom: select_cells(header, geom)  # noqa: E731
        self.assertEqual(decision.evaluate_store(self.codes, self.meta, geometry, LEVEL, plain),
                         decision.evaluate_store(self.codes, self.meta, geometry, LEVEL))
        with_summarize = lambda header, geom: select_cells(header, geom)  # noqa: E731
        with_summarize.summarize = lambda codes, header, geom, level: {'reduced': level}
        self.assertEqual(decision.evaluate_store(self.codes, self.meta, geometry, None, with_summarize), {'reduced': LEVEL})

    def test_fused_reduction_on_other_rasters_and_headers(self):
        h, w = SHAPE
        outside = self.codes.copy()
        outside[::7, ::5] = 200
        negative = self.codes.astype(np.int8)
        negative[::9, ::4] = -1
        read_only = self.codes.copy()
        read_only.setflags(write=False)
        rasters = {'fortran_order': (np.asfortranarray(self.codes), self.meta), 'int64': (self.codes.astype(np.int64), self.meta),
                   'bool': (self.codes > 5, self.meta), 'object': (self.codes.astype(object), self.meta), 'read_only': (read_only, self.meta),
                   'values_outside_code_space': (outside, self.meta), 'negative_int8': (negative, self.meta),
                   'row_view': (self.codes[5:h - 5], dict(self.meta, shape=[h - 10, w])), 'transposed': (self.codes.T, dict(self.meta, shape=[w, h])),
                   'shape_differs': (self.codes[:10], self.meta), 'shape_as_string': (self.codes, dict(self.meta, shape='ab')),
                   'no_level': (self.codes, {k: v for k, v in self.meta.items() if k != 'level'}),
                   'other_level': (self.codes, dict(self.meta, level=decision.SCREEN_VERSION)), 'list': (self.codes.tolist()[:2], self.meta)}
        geometries = adversarial(self.meta, np.random.default_rng(11), 60)
        for name, (codes, header) in rasters.items():
            for geometry in geometries:
                for level in (LEVEL, None, decision.SCREEN_VERSION):
                    with self.subTest(raster=name, level=level):
                        self.assertSameAnswer(geometry, codes, header, level)

    def test_window_partly_or_wholly_outside_the_chip(self):
        a, _, c, _, e, f = self.meta['transform']
        for row, col in ((-3, -3), (-3, 10), (SHAPE[0] - 4, SHAPE[1] - 4), (0, 0), (SHAPE[0] - 2, 5), (5, SHAPE[1] - 2), (-100, 50), (50, 5000)):
            x0, y0 = c + (col + .5) * a, f + (row + .5) * e
            geometry = {'type': 'Polygon', 'coordinates': [[[x0, y0], [x0 + 5 * a, y0], [x0 + 5 * a, y0 + 5 * e], [x0, y0 + 5 * e], [x0, y0]]]}
            with self.subTest(row=row, col=col):
                self.assertSameSelection(self.meta, geometry)
                self.assertSameAnswer(geometry)

    def test_dispatch_and_fallback(self):
        a, _, c, _, e, f = self.meta['transform']

        def square(cells):
            return {'type': 'Polygon', 'coordinates': [[[c + 50.5 * a, f + 50.5 * e], [c + (50.5 + cells) * a, f + 50.5 * e],
                                                        [c + (50.5 + cells) * a, f + (50.5 + cells) * e], [c + 50.5 * a, f + (50.5 + cells) * e],
                                                        [c + 50.5 * a, f + 50.5 * e]]]}
        small, large = square(4), square(200)
        for geometry, scalar_calls in ((small, 1), (large, 0)):
            with mock.patch.object(di, '_scalar_runs', wraps=di._scalar_runs) as spy:
                self.assertEqual(result(di.fast_select_cells, self.meta, geometry), result(select_cells, self.meta, geometry))
            self.assertEqual(spy.call_count, scalar_calls)
        # odd crossing parity cannot happen for closed rings; if the scalar scan ever gave up, the array scan answers
        with mock.patch.object(di, '_scalar_runs', return_value=None):
            self.assertEqual(result(di.fast_select_cells, self.meta, small), result(select_cells, self.meta, small))
            self.assertSameAnswer(small)
        with mock.patch.object(di, 'SCALAR_EDGE_ROWS', 0), mock.patch.object(di, '_scalar_runs') as spy:
            self.assertEqual(result(decision.evaluate_store, self.codes, self.meta, small, LEVEL, di.fast_select_cells),
                             result(decision.evaluate_store, self.codes, self.meta, small, LEVEL))
        spy.assert_not_called()


    def cell_polygon(self, points, row=100, col=200, hole=None):
        """A polygon with vertices at (x, y) offsets in cells from the centre of cell (row, col)."""
        a, _, c, _, e, f = self.meta['transform']

        def ring(pts):
            out = [[c + (col + .5 + x) * a, f + (row + .5 + y) * e] for x, y in pts]
            return out + [out[0]]
        return {'type': 'Polygon', 'coordinates': [ring(points)] + ([ring(hole)] if hole else [])}

    @staticmethod
    def ngon(n, radius, turn=.1):
        return [(radius * math.cos(turn + 2 * math.pi * k / n), radius * math.sin(turn + 2 * math.pi * k / n)) for k in range(n)]

    @staticmethod
    def sawtooth(teeth, width, height, depth):
        """A flat bottom and a top edge of tall slanted teeth: every slanted edge crosses many rows."""
        top = [(width / 2 - width * k / (2 * teeth), -(height if k % 2 == 0 else height - depth)) for k in range(2 * teeth + 1)]
        return [(-width / 2, 0), (width / 2, 0), *top]

    def test_sawtooth_boundaries_stay_on_the_array_scan_and_gentle_ones_move_to_the_scalar_scan(self):
        gentle = self.cell_polygon(self.ngon(60, 6.3))  # ~14 rows x 60 edges: past SCALAR_SURE_ROWS, ~30 rows crossed
        teeth = self.cell_polygon(self.sawtooth(8, 40, 30, 24))  # ~32 rows x 19 edges, ~380 rows crossed
        for name, geometry, scalar_runs, array_scans in (('gentle', gentle, 1, 0), ('sawtooth', teeth, 1, 1)):
            with mock.patch.object(di, '_scalar_runs', wraps=di._scalar_runs) as scalar, \
                    mock.patch.object(di, '_array_select', wraps=di._array_select) as array:
                got = result(di.fast_select_cells, self.meta, geometry)
            self.assertEqual(got, result(select_cells, self.meta, geometry), name)
            self.assertEqual((scalar.call_count, array.call_count), (scalar_runs, array_scans), name)
            self.assertEqual(scalar.call_args.args[-1], di.SCALAR_CROSSINGS, name)  # past SCALAR_SURE_ROWS the guard is on
        # at or under SCALAR_SURE_ROWS (rows x edges) there is no guard, whatever the shape
        small = self.cell_polygon(self.sawtooth(2, 16, 12, 9))
        with mock.patch.object(di, '_scalar_runs', wraps=di._scalar_runs) as scalar:
            self.assertEqual(result(di.fast_select_cells, self.meta, small), result(select_cells, self.meta, small))
        self.assertIsNone(scalar.call_args.args[-1])
        # the outer bound is unchanged in kind: more rows x edges than SCALAR_EDGE_ROWS goes straight to the array scan
        many = self.cell_polygon(self.ngon(400, 12))
        with mock.patch.object(di, '_scalar_runs', wraps=di._scalar_runs) as scalar:
            self.assertEqual(result(di.fast_select_cells, self.meta, many), result(select_cells, self.meta, many))
        scalar.assert_not_called()

    def test_every_crossing_budget_gives_the_same_selection(self):
        rng = np.random.default_rng(20261016)
        geometries = []
        for turn in rng.uniform(0, 1, 6):
            for n in (24, 60, 150):
                geometries.append(self.cell_polygon(self.ngon(n, float(rng.uniform(4, 14)), float(turn))))
        for teeth in (2, 5, 9, 16):
            for height in (6, 14, 30):
                geometries.append(self.cell_polygon(self.sawtooth(teeth, 3 * teeth + 10, height, .8 * height),
                                                    row=int(rng.integers(60, 300)), col=int(rng.integers(60, 500))))
        angles = np.sort(rng.uniform(0, 2 * np.pi, 120))
        radii = rng.uniform(.4, 1, 120) * 9  # a spiky star with a hole
        geometries.append(self.cell_polygon(list(zip(radii * np.cos(angles), radii * np.sin(angles))), hole=self.ngon(8, 1.5)[::-1]))
        for geometry in geometries:
            want = result(select_cells, self.meta, geometry)
            answer = result(decision.evaluate_store, self.codes, self.meta, geometry, LEVEL)
            for budget in (0, 40, di.SCALAR_CROSSINGS, 10 ** 9):
                with mock.patch.object(di, 'SCALAR_CROSSINGS', budget), mock.patch.object(di, 'SCALAR_EDGE_ROWS', 10 ** 9):
                    self.assertEqual(result(di.fast_select_cells, self.meta, geometry), want, budget)
                    self.assertEqual(result(decision.evaluate_store, self.codes, self.meta, geometry, LEVEL, di.fast_select_cells),
                                     answer, budget)


if __name__ == '__main__':
    unittest.main()
