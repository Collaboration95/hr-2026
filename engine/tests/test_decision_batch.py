"""evaluate_many must equal a loop of evaluate_store(select=fast_select_cells): outputs and rejections, any batch size."""
import copy
import math
import os
from pathlib import Path
import unittest
from unittest import mock

import numpy as np

from engine import decision, decision_batch as db, decision_index as di
from engine.decision_benchmark import boundary_polygons, synthetic_polygons
from engine.decision_store import read_store
from engine.tests.test_adversarial import INVALID_GEOMETRIES
from engine.tests.test_decision_index import fuzz_geometries

ROOT = Path(__file__).resolve().parents[2]
N = int(os.environ.get('DECISION_BATCH_N', 2400))  # polygons per generator; 50000+ for the long differential run
SIZES = (1, 2, 17, 500, 5000)


def loop(codes, header, geometries, level=None):
    out = []
    for geometry in geometries:
        try:
            out.append(decision.evaluate_store(codes, header, geometry, level, select=di.fast_select_cells))
        except Exception as exc:
            out.append(exc)
    return out


def batches(items, sizes=SIZES):
    """Consecutive slices of varied sizes, cycling through `sizes`."""
    pos, k = 0, 0
    while pos < len(items):
        size = sizes[k % len(sizes)]
        yield items[pos:pos + size]
        pos += size
        k += 1


def same(a, b):
    if isinstance(a, Exception) or isinstance(b, Exception):
        return type(a) is type(b) and str(a) == str(b)
    return a == b


def raster_store(shape, transform, seed):
    rng = np.random.default_rng(seed)
    header = {'level': decision.DECISION_VERSION, 'shape': list(shape), 'transform': transform, 'crs': 'EPSG:4326'}
    return rng.integers(0, decision.CODE_COUNT, shape, dtype=np.uint8), header


class DecisionBatchTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.codes, cls.header = read_store(ROOT / 'artifacts/decision/decision.plds')
        cls.screen_codes, cls.screen_header = read_store(ROOT / 'artifacts/decision/screen.plds')
        cls.stores = {'decision store': (cls.codes, cls.header), 'screen store': (cls.screen_codes, cls.screen_header),
                      'random raster A': raster_store((130, 170), [0.00025, 0.0, 98.77225, 0.0, -0.00025, 8.582], 5),
                      'random raster B': raster_store((60, 90), [0.003, 0, -121.3333, 0, -0.0017, 47.9], 6)}

    def setUp(self):
        patch = mock.patch.object(db, 'MIN_BATCH', 1)  # exercise the vectorized path even for one or two polygons
        patch.start()
        self.addCleanup(patch.stop)

    def test_tiny_batches_use_the_loop_by_default(self):
        geometries = fuzz_geometries(self.header, 3, seed=19)
        with mock.patch.object(db, 'MIN_BATCH', 4):
            got = db.evaluate_many(self.codes, self.header, geometries, on_error='return')
            self.assertEqual((db._stats['batched'], db._stats['single']), (0, 3))
        self.assertTrue(all(same(a, b) for a, b in zip(loop(self.codes, self.header, geometries), got)))

    def check(self, geometries, stores=None, sizes=SIZES, **kw):
        """Batch == loop on every store, for every slice; returns the loop outputs of the last store."""
        for name, (codes, header) in (stores or self.stores).items():
            want = loop(codes, header, geometries)
            got = []
            for part in batches(geometries, sizes):
                got += db.evaluate_many(codes, header, part, on_error='return', **kw)
            self.assertEqual(len(got), len(want))
            bad = [i for i, (a, b) in enumerate(zip(want, got)) if not same(a, b)]
            self.assertEqual(bad, [], f'{name}: {len(bad)} of {len(want)} differ, first at {bad[:5]}')
        return want

    def test_every_output_is_summarize_counts_of_the_selected_histogram(self):
        geometries = fuzz_geometries(self.header, 300, seed=21)
        with mock.patch.object(decision, 'summarize_counts', wraps=decision.summarize_counts) as spy:
            got = db.evaluate_many(self.codes, self.header, geometries, on_error='return')
        self.assertEqual(spy.call_count, db._stats['batched'])
        self.assertGreater(spy.call_count, 200)
        for call in spy.call_args_list:
            row, selected, outside, level = call.args
            self.assertTrue(type(row) is list and all(type(v) is int for v in row) and type(selected) is int and type(outside) is int)
            self.assertEqual(level, decision.DECISION_VERSION)
        self.assertTrue(all(same(a, b) for a, b in zip(got, loop(self.codes, self.header, geometries))))

    # ---- generators ----

    def test_synthetic_polygons_match(self):
        polygons, _ = synthetic_polygons(max(N // 4, 200), 20261015, self.header, self.screen_codes >= decision.LAND)
        geometries = [p['geometry'] for p in polygons]
        self.check(geometries, {'decision store': (self.codes, self.header)})
        self.assertEqual(db._stats['single'], 0)  # clean plots all take the vectorized path

    def test_fuzz_adversarial_polygons_match(self):
        for name, (codes, header) in self.stores.items():
            geometries = fuzz_geometries(header, N, seed=20261015 + len(name))
            self.check(geometries, {name: (codes, header)})

    def test_boundary_polygons_match(self):
        polygons, _ = boundary_polygons(max(N // 8, 100), 20261015, self.header)
        self.check([p['geometry'] for p in polygons], {'decision store': (self.codes, self.header)})

    def test_batch_path_handles_adversarial_input_not_just_the_fallback(self):
        geometries = fuzz_geometries(self.header, 600, seed=7)
        db.evaluate_many(self.codes, self.header, geometries, on_error='return')
        self.assertGreater(db._stats['batched'], 0.7 * len(geometries))

    # ---- shapes the generators do not make ----

    def cell_polygons(self, header, rng):
        a, _, c, _, e, f = header['transform']
        height, width = header['shape']
        out = []
        for _ in range(300):
            r, col = int(rng.integers(-5, height + 5)), int(rng.integers(-5, width + 5))
            w, h = int(rng.integers(0, 4)), int(rng.integers(0, 4))
            x0, x1 = c + (col + .5) * a, c + (col + w + .5) * a
            y1, y0 = f + (r + .5) * e, f + (r + h + .5) * e
            pad = float(rng.choice((0.0, 1e-12, -1e-12, .49 * a, .5 * a, .51 * a)))
            x0, x1, y0, y1 = x0 - pad, x1 + pad, y0 + pad * e, y1 - pad * e
            ring = [[x0, y0], [x1, y0], [x1, y1], [x0, y1], [x0, y0]]
            out.append({'type': 'Polygon', 'coordinates': [ring if rng.integers(2) else ring[::-1]]})
        return out

    def offset_polygons(self, header, n, seed):
        """Polygons whose vertices sit at centre-lattice points plus offsets around the analytic/exact switch (1e-3 cell)
        and around the tolerance (1e-9 deg), with repeated vertices, thin slants and rectangles, so crossings land on centres."""
        rng = np.random.default_rng(seed)
        a, _, c, _, e, f = header['transform']
        height, width = header['shape']
        menu = np.array([0, 1e-14, 1e-12, 1e-9 / a, 1e-6, 4.9e-4, 9.99e-4, 1e-3, 1.0001e-3, 2e-3, .01, .1, .5, .5 + 1e-9]) * rng.choice((-1, 1), 14)
        out = []
        for _ in range(n):
            r0, c0 = int(rng.integers(-8, height + 8)), int(rng.integers(-8, width + 8))
            kind = int(rng.integers(0, 4))
            if kind == 0:  # rectangle with offset sides
                dr, dc = int(rng.integers(0, 5)), int(rng.integers(0, 5))
                xs = sorted(c + (c0 + dc * i + .5 + rng.choice(menu)) * a for i in (0, 1))
                ys = sorted((f + (r0 + dr * i + .5 + rng.choice(menu)) * e for i in (0, 1)))
                pts = [(xs[0], ys[0]), (xs[1], ys[0]), (xs[1], ys[1]), (xs[0], ys[1])]
            elif kind == 1:  # slanted quadrilateral with vertices near lattice points
                offs = [(int(rng.integers(-5, 6)), int(rng.integers(-5, 6))) for _ in range(int(rng.integers(3, 7)))]
                pts = [(c + (c0 + dc + .5 + rng.choice(menu)) * a, f + (r0 + dr + .5 + rng.choice(menu)) * e) for dr, dc in offs]
                mx, my = np.mean([p[0] for p in pts]), np.mean([p[1] for p in pts])
                pts.sort(key=lambda p: math.atan2(p[1] - my, p[0] - mx))
            elif kind == 2:  # thin parallelogram: long edges cross many rows near centre columns
                k = int(rng.integers(2, 30))
                x0, y0 = c + (c0 + .5) * a, f + (r0 + .5) * e
                dx = (c0 + k + .5 + rng.choice(menu)) * a + c - x0
                w = (int(rng.integers(1, 3)) + rng.choice(menu)) * a
                dy = (k + rng.choice(menu)) * e
                pts = [(x0, y0), (x0 + w, y0), (x0 + w + dx, y0 + dy), (x0 + dx, y0 + dy)]
            else:  # a triangle through three lattice points, one vertex repeated
                pts = [(c + (c0 + int(rng.integers(0, 9)) + .5) * a, f + (r0 + int(rng.integers(0, 9)) + .5) * e) for _ in range(3)]
                pts.insert(int(rng.integers(0, 3)), pts[int(rng.integers(0, 3))])
            ring = [[float(x), float(y)] for x, y in pts]
            if rng.integers(2):
                ring.reverse()
            out.append({'type': 'Polygon', 'coordinates': [ring + [ring[0]]]})
        return out

    def test_offsets_around_the_exact_switch_and_tolerance(self):
        for name, (codes, header) in self.stores.items():
            self.check(self.offset_polygons(header, N, 31 + len(name)), {name: (codes, header)})

    def test_cell_aligned_squares_and_chip_edges(self):
        rng = np.random.default_rng(3)
        for name, (codes, header) in self.stores.items():
            self.check(self.cell_polygons(header, rng), {name: (codes, header)})

    def test_outside_the_chip_and_empty_selections(self):
        a, _, c, _, e, f = self.header['transform']
        height, width = self.header['shape']

        def box(x0, y0, x1, y1):
            return {'type': 'Polygon', 'coordinates': [[[x0, y0], [x1, y0], [x1, y1], [x0, y1], [x0, y0]]]}
        geometries = [box(c - 40 * a, f + 40 * e, c - 20 * a, f + 20 * e),  # wholly outside
                      box(c + (width - 5) * a, f + (height - 5) * e, c + (width + 9) * a, f + (height + 9) * e),  # straddles
                      box(c - 3 * a, f + 3 * e, c + 3 * a, f - 3 * e),
                      box(c + 1e-9, f - 1e-9, c + 2e-9, f - 2e-9),  # inside a cell, no centre
                      box(0, 0, 1, 1), box(-170, -80, -169.9, -79.9), box(179.5, 80, 179.6, 80.1)]
        want = self.check(geometries, {'decision store': (self.codes, self.header)})
        self.assertEqual(want[0]['selected_cell_count'], want[0]['out_of_coverage_cell_count'])
        self.assertTrue(any(w['selected_cell_count'] == 0 for w in want))
        self.assertTrue(any(0 < w['out_of_coverage_cell_count'] < w['selected_cell_count'] for w in want))

    def test_holes_multipolygons_and_vertex_heavy_rings(self):
        a, _, c, _, e, f = self.header['transform']
        cx = lambda col: c + (col + .5) * a
        cy = lambda row: f + (row + .5) * e
        ring = lambda pts: [list(p) for p in pts] + [list(pts[0])]
        sq = lambda r, k, h: ring([(cx(k), cy(r)), (cx(k + h), cy(r)), (cx(k + h), cy(r + h)), (cx(k), cy(r + h))])
        geometries = [{'type': 'Polygon', 'coordinates': [sq(100, 100, 10), sq(103, 103, 3)[::-1], sq(106, 105, 2)]},
                      {'type': 'MultiPolygon', 'coordinates': [[sq(30, 30, 4)], [sq(50, 52, 6), sq(52, 54, 2)]]},
                      {'type': 'MultiPolygon', 'coordinates': [[sq(30, 30, 4)]]},
                      {'type': 'MultiPolygon', 'coordinates': [[sq(30, 30, 4), sq(31, 31, 1)], [sq(100, 80, 3)], [sq(10, 70, 2)]]}]
        n = 4000  # a polygon with thousands of vertices (a fine circle) and many ambiguous-free rows
        t = np.linspace(0, 2 * math.pi, n, endpoint=False)
        geometries.append({'type': 'Polygon', 'coordinates': [ring(list(zip(cx(200) + 25 * a * np.cos(t), cy(200) + 25 * a * np.sin(t))))]})
        self.check(geometries * 3)

    def test_prepared_path_for_many_ambiguous_centres(self):
        a, _, c, _, e, f = self.header['transform']
        pts = [[c + (j + .5) * a, f + (60 + .5) * e] for j in range(40, 140)]
        ring = [[pts[0][0], pts[0][1]]] + [[p[0], p[1]] for p in pts[1:]] + [[pts[-1][0], f + 80.5 * e], [pts[0][0], f + 80.5 * e], pts[0]]
        self.check([{'type': 'Polygon', 'coordinates': [ring]}])

    # ---- errors and malformed input ----

    def malformed(self):
        base = {'type': 'Polygon', 'coordinates': [[[98.80, 8.55], [98.81, 8.55], [98.81, 8.56], [98.80, 8.56], [98.80, 8.55]]]}
        tup = lambda ring: tuple(tuple(p) for p in ring)
        mut = lambda f: (lambda g: (f(g["coordinates"][0]), g)[1])(copy.deepcopy(base))
        out = list(INVALID_GEOMETRIES.values())
        out += [{'type': 'Polygon', 'coordinates': (tup(base['coordinates'][0]),)},
                {'type': 'Polygon', 'coordinates': [tup(base['coordinates'][0])]},
                {'type': 'Polygon', 'coordinates': [[tuple(p) for p in base['coordinates'][0]]]},
                {'type': 'MultiPolygon', 'coordinates': (base['coordinates'],)},
                {'type': 'MultiPolygon', 'coordinates': [[]]}, {'type': 'MultiPolygon', 'coordinates': [base['coordinates'], []]},
                {'type': 'MultiPolygon', 'coordinates': 'x'}, {'type': 'Polygon', 'coordinates': 'x'},
                {'type': 'Polygon', 'coordinates': [[1, 2, 3, 4]]}, {'type': 5, 'coordinates': base['coordinates']},
                {'type': b'Polygon', 'coordinates': base['coordinates']}, {'type': 'Polygon', 'coordinates': [[[1, 2], [3, 4], [5, 6]]]},
                type('D', (dict,), {})(base), [base], 'Polygon', 7, 7.5, {'type': 'Polygon', 'coordinates': None}]
        for value in (np.float64(98.80), np.float32(98.8), True, '98.8', None, float('nan'), float('inf'), -float('inf'), 10 ** 400,
                      10 ** 30, 1e300, -1e100, 1e99, 5e-324, np.int64(3), complex(1, 2), [98.8], 98):
            for where in (0, 2, -1):
                geometry = copy.deepcopy(base)
                ring = geometry['coordinates'][0]
                ring[where][0] = value
                if where == 0:
                    ring[-1][0] = value
                out.append(geometry)
        out.append(mut(lambda r: r[2].append(0.0)))
        out.append(mut(lambda r: r.__setitem__(2, [98.81])))
        out.append(mut(lambda r: r.__setitem__(1, 'ab')))
        out.append(mut(lambda r: r.__setitem__(1, {'x': 1})))
        out.append({'type': 'Polygon', 'coordinates': [[[0, 0]] * 100_001 + [[0, 0]]]})  # vertex limit
        out.append({'type': 'Polygon', 'coordinates': [[[0, 0], [1e5, 0], [1e5, 1e5], [0, 1e5], [0, 0]]]})  # candidate cells
        out.append({'type': 'Polygon', 'coordinates': [[[98.0, 8.0], [98.4, 8.0], [98.4, 8.4], [98.0, 8.4], [98.0, 8.0]]]})  # big, valid
        out.append({'type': 'Polygon', 'coordinates': [[[0.0, 0.0], [0.0, 0.0], [0.0, 0.0], [0.0, 0.0]]]})
        out.append({'type': 'Polygon', 'coordinates': [[[1e150, 1e150], [1e150, -1e150], [-1e150, 1e150], [1e150, 1e150]]]})
        return out

    def test_malformed_items_mixed_with_valid_ones(self):
        bad = self.malformed()
        good = fuzz_geometries(self.header, 120, seed=11)
        rng = np.random.default_rng(1)
        mixed = []
        for i, geometry in enumerate(bad):
            mixed += [good[int(rng.integers(len(good)))], geometry, good[int(rng.integers(len(good)))]]
        want = self.check(mixed + bad + good)
        self.assertGreater(sum(isinstance(w, Exception) for w in want), 30)
        self.assertGreater(sum(not isinstance(w, Exception) for w in want), 100)

    def test_raise_mode_raises_what_the_loop_raises_first(self):
        bad = self.malformed()
        good = fuzz_geometries(self.header, 40, seed=12)
        rng = np.random.default_rng(2)
        for _ in range(60):
            items = [good[int(rng.integers(len(good)))] for _ in range(int(rng.integers(0, 12)))]
            for geometry in rng.choice(len(bad), int(rng.integers(0, 4)), replace=False):
                items.insert(int(rng.integers(len(items) + 1)), bad[int(geometry)])
            want = [w for w in loop(self.codes, self.header, items) if isinstance(w, Exception)]
            if want:
                with self.assertRaises(type(want[0])) as caught:
                    db.evaluate_many(self.codes, self.header, items)
                self.assertEqual(str(caught.exception), str(want[0]))
            else:
                self.assertEqual(db.evaluate_many(self.codes, self.header, items), loop(self.codes, self.header, items))

    def test_header_level_and_raster_errors_match_the_loop(self):
        geometries = fuzz_geometries(self.header, 5, seed=13)
        broken = {'foreign level': (self.codes, dict(self.header, level='eudr-screen.v1'), decision.DECISION_VERSION),
                  'no level': (self.codes, {k: v for k, v in self.header.items() if k != 'level'}, None),
                  'wrong shape': (self.codes[:-1], self.header, None),
                  'not a header': (self.codes, None, None)}
        for name, (codes, header, level) in broken.items():
            with self.subTest(name):
                want = loop(codes, header, geometries, level)
                self.assertTrue(isinstance(want[0], Exception))
                with self.assertRaises(type(want[0])) as caught:
                    db.evaluate_many(codes, header, geometries, level)
                self.assertEqual(str(caught.exception), str(want[0]))
        self.assertEqual(db.evaluate_many(self.codes, None, []), [])
        self.assertEqual(db.evaluate_many(self.codes, self.header, iter(()), 'anything'), [])
        with self.assertRaises(ValueError):
            db.evaluate_many(self.codes, self.header, geometries, on_error='ignore')

    def test_unusual_transforms_and_rasters_take_the_loop(self):
        geometries = fuzz_geometries(self.header, 40, seed=14)
        variants = {'int transform': dict(self.header, transform=[1, 0, 98, 0, -1, 9]),
                    'rotated': dict(self.header, transform=[0.00025, 0.1, 98.77225, 0, -0.00025, 8.582]),
                    'south up': dict(self.header, transform=[0.00025, 0, 98.77225, 0, 0.00025, 8.582]),
                    'short': dict(self.header, transform=[0.00025, 0, 98.77225]),
                    'other crs': dict(self.header, crs='EPSG:3857'),
                    'nan': dict(self.header, transform=[0.00025, 0, float('nan'), 0, -0.00025, 8.582]),
                    'tiny cells': dict(self.header, transform=[1e-12, 0, 98.77225, 0, -1e-12, 8.582]),
                    'huge origin': dict(self.header, transform=[0.00025, 0, 1e90, 0, -0.00025, 8.582])}
        for name, header in variants.items():
            with self.subTest(name):
                want = loop(self.codes, header, geometries)
                got = db.evaluate_many(self.codes, header, geometries, on_error='return')
                self.assertTrue(all(same(a, b) for a, b in zip(want, got)))
        for codes in (self.codes.astype(np.int64), np.asfortranarray(self.codes), self.codes.astype(np.int8)):
            want = loop(codes, self.header, geometries)
            got = db.evaluate_many(codes, self.header, geometries, on_error='return')
            self.assertTrue(all(same(a, b) for a, b in zip(want, got)))

    def test_codes_outside_the_contract_space_raise_for_the_polygons_that_select_them(self):
        codes = self.codes.copy()
        a, _, c, _, e, f = self.header['transform']
        codes[200:203, 300:303] = 25
        hit = {'type': 'Polygon', 'coordinates': [[[c + 299 * a, f + 199 * e], [c + 305 * a, f + 199 * e], [c + 305 * a, f + 206 * e], [c + 299 * a, f + 206 * e], [c + 299 * a, f + 199 * e]]]}
        miss = {'type': 'Polygon', 'coordinates': [[[c + 10 * a, f + 10 * e], [c + 15 * a, f + 10 * e], [c + 15 * a, f + 15 * e], [c + 10 * a, f + 15 * e], [c + 10 * a, f + 10 * e]]]}
        items = [miss, hit, miss]
        want = loop(codes, self.header, items)
        self.assertTrue(isinstance(want[1], ValueError) and not isinstance(want[0], Exception))
        got = db.evaluate_many(codes, self.header, items, on_error='return')
        self.assertTrue(all(same(a, b) for a, b in zip(want, got)))

    # ---- chunking ----

    def test_tiny_slabs_and_chunks_do_not_change_answers(self):
        geometries = fuzz_geometries(self.header, 400, seed=15) + self.malformed()
        want = loop(self.codes, self.header, geometries)
        for slab, chunk in ((7, 4_000_000), (100_000, 5_000), (3, 1), (100_000, 1)):
            with mock.patch.object(db, 'MAX_SLAB', slab), mock.patch.object(db, 'CHUNK_COST', chunk):
                got = db.evaluate_many(self.codes, self.header, geometries, on_error='return')
            self.assertTrue(all(same(a, b) for a, b in zip(want, got)), (slab, chunk))

    def test_items_over_the_window_or_crossing_caps_take_the_single_path(self):
        geometries = fuzz_geometries(self.header, 200, seed=16)
        want = loop(self.codes, self.header, geometries)
        for patch in ({'MAX_ITEM_CELLS': 30}, {'MAX_ITEM_CROSSINGS': 3}):
            with mock.patch.multiple(db, **patch):
                got = db.evaluate_many(self.codes, self.header, geometries, on_error='return')
                self.assertGreater(db._stats['single'], 20)
            self.assertTrue(all(same(a, b) for a, b in zip(want, got)), patch)

    def test_a_failing_vectorized_stage_falls_back_without_losing_items(self):
        geometries = fuzz_geometries(self.header, 60, seed=17)
        want = loop(self.codes, self.header, geometries)
        with mock.patch.object(db, '_chunk', side_effect=db._Fallback):
            got = db.evaluate_many(self.codes, self.header, geometries, on_error='return')
        self.assertTrue(all(same(a, b) for a, b in zip(want, got)))
        with mock.patch.object(db, '_pipeline', side_effect=RuntimeError('boom')):
            got = db.evaluate_many(self.codes, self.header, geometries, on_error='return')
        self.assertTrue(all(same(a, b) for a, b in zip(want, got)))
        self.assertEqual(db._stats['single'], len(geometries))

    def test_same_selection_as_select_cells_through_the_batch(self):
        from engine.query import select_cells
        geometries = [g for g in fuzz_geometries(self.header, 300, seed=18)]
        got = db.evaluate_many(self.codes, self.header, geometries, on_error='return')
        for geometry, answer in zip(geometries, got):
            try:
                rows, cols = select_cells(self.header, geometry)
            except ValueError as exc:
                self.assertTrue(isinstance(answer, ValueError) and str(answer) == str(exc))
                continue
            self.assertEqual(answer, decision.summarize_selection(self.codes, rows, cols, decision.DECISION_VERSION))


if __name__ == '__main__':
    unittest.main()
