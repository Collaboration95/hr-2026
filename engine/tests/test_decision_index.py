"""Registry, table and exact fast selection must equal the full paths, and go stale on any key change."""
import contextlib
import copy
import hashlib
import io
import json
import math
import os
from pathlib import Path
import subprocess
import struct
import sys
import tempfile
import time
import tracemalloc
import unittest
from unittest import mock
import warnings

import numpy as np

from engine import decision, decision_index as di
from engine.jrc import load_jrc
from engine.query import select_cells
from engine.source import load_plots, load_source, object_hash
from engine.tests.test_adversarial import INVALID_GEOMETRIES

ROOT = Path(__file__).resolve().parents[2]
FUZZ_COUNT = int(os.environ.get('DECISION_FUZZ_N', 2000))


def fuzz_geometries(metadata, n, seed=20261015, labels=None):
    """Seeded polygons stressing the centre rule: aligned edges, vertices on centres, ulp offsets.

    If `labels` is a list, the generator kind of each polygon is appended to it.
    """
    a, _, c, _, e, f = metadata['transform']
    height, width = metadata['shape']
    rng = np.random.default_rng(seed)
    nxt = np.nextafter

    def cx(col):
        return c + (col + .5) * a

    def cy(row):
        return f + (row + .5) * e

    def jitter(v):
        """A coordinate exactly on, a few ulps from, or a tiny distance from v."""
        k = int(rng.integers(0, 9))
        return (v, float(nxt(v, np.inf)), float(nxt(v, -np.inf)), float(nxt(nxt(v, np.inf), np.inf)),
                v + 1e-12 * rng.choice((-1, 1)), v + 1e-10 * rng.choice((-1, 1)),
                v + 1e-9 * rng.choice((-1, 1)), v + 1e-8 * rng.choice((-1, 1)),
                v + rng.uniform(-.5, .5) * a)[k]

    def ring(points, reverse=None):
        pts = [[float(x), float(y)] for x, y in points]
        if reverse is None:
            reverse = bool(rng.integers(0, 2))
        if reverse:
            pts.reverse()
        return pts + [pts[0]]

    def rounded(points):
        k = int(rng.integers(0, 4))
        return [(round(x, 6 - k), round(y, 6 - k)) for x, y in points] if k < 2 else points

    def anchor():
        return int(rng.integers(-30, height + 30)), int(rng.integers(-30, width + 30))

    def rect(x0, y0, x1, y1):
        return [(x0, y0), (x1, y0), (x1, y1), (x0, y1)]

    def edge(centre, step):
        """A coordinate on a centre, a jittered centre, a cell edge, or random nearby."""
        k = int(rng.integers(0, 4))
        return (centre, jitter(centre), centre + .5 * step * rng.choice((-1, 1)),
                centre + rng.uniform(-3, 3) * step)[k]

    def poly(*rings):
        return {'type': 'Polygon', 'coordinates': list(rings)}

    def convex():
        r, col = anchor()
        ang = np.sort(rng.uniform(0, 2 * math.pi, int(rng.integers(3, 11))))
        rx, ry = rng.uniform(.2, 6) * a, rng.uniform(.2, 6) * -e
        x0, y0 = cx(col) + rng.uniform(-.5, .5) * a, cy(r) + rng.uniform(-.5, .5) * -e
        return poly(ring(rounded([(x0 + math.cos(t) * rx, y0 + math.sin(t) * ry) for t in ang])))

    def star():
        r, col = anchor()
        k, s = int(rng.integers(4, 9)), rng.uniform(.5, 8)
        pts = []
        for i in range(2 * k):
            rad = s * (1 if i % 2 == 0 else rng.uniform(.2, .7))
            pts.append((cx(col) + math.cos(math.pi * i / k) * rad * a, cy(r) + math.sin(math.pi * i / k) * rad * -e))
        return poly(ring(rounded(pts)))

    def aligned_rect():
        r, col = anchor()
        w, h = int(rng.integers(0, 6)), int(rng.integers(0, 6))
        x0, x1 = sorted((edge(cx(col), a), edge(cx(col + w), a)))
        y0, y1 = sorted((edge(cy(r), e), edge(cy(r + h), e)))
        return poly(ring(rect(x0, y0, x1, y1)))

    def lattice_polygon():
        r, col = anchor()
        offs = {(int(rng.integers(-4, 5)), int(rng.integers(-4, 5))) for _ in range(int(rng.integers(3, 8)))}
        pts = [(cx(col + dc), cy(r + dr)) for dr, dc in offs]
        mx, my = sum(p[0] for p in pts) / len(pts), sum(p[1] for p in pts) / len(pts)
        pts.sort(key=lambda p: math.atan2(p[1] - my, p[0] - mx))
        return poly(ring(pts))

    def diagonal():
        r, col = anchor()
        k, sx, sy = int(rng.integers(1, 9)), int(rng.choice((-1, 1))), int(rng.choice((-1, 1)))
        pts = [(cx(col), cy(r)), (cx(col + sx * k), cy(r + sy * k)), (cx(col + sx * k), cy(r))]
        if rng.integers(0, 2):
            pts[2] = (cx(col), cy(r + sy * k))
        return poly(ring(pts))

    def staircase():
        """Orthogonal polygon whose horizontal edges sit on centre rows."""
        r, col = anchor()
        xs, ys = [cx(col)], [cy(r)]
        for _ in range(int(rng.integers(1, 5))):
            xs.append(edge(cx(col + int(rng.integers(1, 6))), a))
            ys.append(edge(cy(r + int(rng.integers(1, 6))), e))
        xs, ys = sorted(xs), sorted(ys, reverse=bool(rng.integers(0, 2)))
        pts = [(xs[0], ys[0])]
        for i in range(1, len(xs)):
            pts += [(xs[i], ys[i - 1]), (xs[i], ys[i])]
        pts.append((xs[0], ys[-1]))
        return poly(ring([p for i, p in enumerate(pts) if p != pts[i - 1]], reverse=False))

    def holes():
        r, col = anchor()
        w, h = int(rng.integers(3, 12)), int(rng.integers(3, 12))
        rings = [ring(rect(edge(cx(col), a), edge(cy(r + h), e), edge(cx(col + w), a), edge(cy(r), e)))]
        for _ in range(int(rng.integers(1, 3))):
            hr, hc = r + int(rng.integers(1, h - 1)), col + int(rng.integers(1, w - 1))
            x0, x1 = sorted((edge(cx(hc), a), edge(cx(hc + int(rng.integers(0, 2))), a)))
            y0, y1 = sorted((edge(cy(hr), e), edge(cy(hr + int(rng.integers(0, 2))), e)))
            rings.append(ring(rect(x0, y0, x1, y1)))
        return poly(*rings)

    def multi():
        r, col = anchor()
        if rng.integers(0, 3) == 0:  # island inside a hole
            w = int(rng.integers(5, 9))
            outer = rect(cx(col - w), cy(r + w), cx(col + w), cy(r - w))
            hole = rect(cx(col - w + 1), cy(r + w - 1), cx(col + w - 1), cy(r - w + 1))
            island = rect(cx(col - 1) + a * .3, cy(r + 1), cx(col + 1), cy(r - 1))
            return {'type': 'MultiPolygon', 'coordinates': [[ring(outer), ring(hole)], [ring(island)]]}
        parts = []
        for _ in range(int(rng.integers(2, 4))):
            gr, gc = r + int(rng.integers(-8, 9)), col + int(rng.integers(-8, 9))
            x0, x1 = sorted((edge(cx(gc), a), edge(cx(gc + int(rng.integers(0, 4))), a)))
            y0, y1 = sorted((edge(cy(gr), e), edge(cy(gr + int(rng.integers(0, 4))), e)))
            parts.append([ring(rect(x0, y0, x1, y1))])
        return {'type': 'MultiPolygon', 'coordinates': parts}

    def tiny():
        r, col = anchor()
        x, y = cx(col), cy(r)
        if rng.integers(0, 3) == 0:
            x, y = x + rng.uniform(-1, 1) * a, y + rng.uniform(-1, 1) * -e
        s = float(rng.choice((1e-13, 1e-12, 1e-10, 1e-8, 1e-6, .1 * a, .6 * a)))
        shapes = ([(x - s, y), (x, y - s), (x + s, y), (x, y + s)], rect(x - s, y - s, x + s, y + s),
                  [(x, y), (x + s, y), (x, y + s)])
        return poly(ring(shapes[int(rng.integers(0, 3))]))

    def sliver():
        r, col = anchor()
        y, s = jitter(cy(r)), float(rng.choice((1e-14, 1e-13, 1e-12, 1e-10, 1e-7)))
        x0, x1 = cx(col) - rng.uniform(0, 3) * a, cx(col + int(rng.integers(1, 12))) + rng.uniform(0, 1) * a
        pts = rect(x0, y, x1, y + s) if rng.integers(0, 2) else [(x0, y), (x1, y + s * rng.choice((-1, 1))), (x1, y)]
        return poly(ring(pts))

    def blob():
        """Random radial polygon; may self-intersect, in which case both paths must reject alike."""
        r, col = anchor()
        k = int(rng.integers(5, 40))
        ang = np.sort(rng.uniform(0, 2 * math.pi, k))
        rad = rng.uniform(.5, 12, k) if rng.integers(0, 2) else rng.uniform(3, 12) * rng.uniform(.7, 1, k)
        return poly(ring(rounded([(cx(col) + math.cos(t) * q * a, cy(r) + math.sin(t) * q * -e) for t, q in zip(ang, rad)])))

    def int_square():
        x0, y0 = int(rng.integers(95, 100)), int(rng.integers(5, 9))
        return poly([[x0, y0], [x0 + 1, y0], [x0 + 1, y0 + 1], [x0, y0 + 1], [x0, y0]])

    kinds = (convex, convex, star, aligned_rect, aligned_rect, aligned_rect, lattice_polygon, diagonal,
             staircase, holes, multi, tiny, sliver, blob)
    out = []
    for _ in range(n):
        kind = int_square if rng.random() < .002 else kinds[int(rng.integers(0, len(kinds)))]
        out.append(kind())
        if labels is not None:
            labels.append(kind.__name__)
    return out


def peak_bytes(function):
    tracemalloc.start()
    try:
        function()
    except ValueError:
        pass
    finally:
        _, peak = tracemalloc.get_traced_memory()
        tracemalloc.stop()
    return peak


def forge_registry(plots, starts, lengths, grid, header=None):
    """A registry file with a valid header hash and payload hash around arbitrary runs (the parser must still refuse)."""
    payload = np.array(starts, '<i4').tobytes() + np.array(lengths, '<i4').tobytes()
    meta = {'schema': di.REGISTRY_SCHEMA, 'selection_rule': 'x', 'grid': grid, 'plots': plots,
            'payload_bytes': len(payload), 'payload_sha256': hashlib.sha256(payload).hexdigest(), **(header or {})}
    return sealed_registry(di.canonical_bytes(meta), payload)


def sealed_registry(header, payload):
    return di.MAGIC + struct.pack('<I', len(header)) + hashlib.sha256(header).digest() + header + payload


def plot_record(runs=1, selected=1, outside=0, plot_id='X'):
    return {'id': plot_id, 'geometry_sha256': '0' * 64, 'runs': runs, 'selected_count': selected, 'outside_count': outside}


def outcome(fn, metadata, geometry):
    try:
        with warnings.catch_warnings():
            warnings.simplefilter('ignore', RuntimeWarning)
            return 'ok', fn(metadata, geometry)
    except ValueError as exc:
        return 'err', str(exc)


class DecisionIndexTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.source, cls.plots, cls.jrc = load_source(), load_plots(), load_jrc()
        cls.metadata = cls.source.metadata
        screen = decision.derive_screen_codes(cls.source, cls.jrc)
        cls.codes = {decision.SCREEN_VERSION: screen, decision.DECISION_VERSION: decision.project_decision(screen)}
        cls.registry = di.build_registry(cls.plots, cls.metadata)
        cls.stores = {level: di.store_sha256(level, raster, '/nonexistent') for level, raster in cls.codes.items()}
        cls.table = di.build_table(cls.plots, cls.codes, {k: v[0] for k, v in cls.stores.items()},
                                   cls.metadata, {k: v[1] for k, v in cls.stores.items()})
        cls.tmp = tempfile.TemporaryDirectory()
        cls.dir = Path(cls.tmp.name)
        a, _, c, _, e, f = cls.metadata['transform']
        cls.cx = lambda self, col: c + (col + .5) * a
        cls.cy = lambda self, row: f + (row + .5) * e

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def assertSameSelection(self, geometry, metadata=None):
        metadata = metadata or self.metadata
        want, got = outcome(select_cells, metadata, geometry), outcome(di.fast_select_cells, metadata, geometry)
        self.assertEqual(want[0], got[0])
        if want[0] == 'err':
            return self.assertEqual(want[1], got[1])
        for expected, actual in zip(want[1], got[1]):
            self.assertEqual(expected.dtype, actual.dtype)
            np.testing.assert_array_equal(expected, actual)
        return len(want[1][0])

    def square(self, row, col, half=0.0, rows=1, cols=1):
        """Square through the centres of cells (row..row+rows-1, col..col+cols-1), grown by `half` cells."""
        a, e = self.metadata['transform'][0], self.metadata['transform'][4]
        x0, x1 = self.cx(col) - half * a, self.cx(col + cols - 1) + half * a
        y1, y0 = self.cy(row) - half * e, self.cy(row + rows - 1) + half * e
        return {'type': 'Polygon', 'coordinates': [[[x0, y0], [x1, y0], [x1, y1], [x0, y1], [x0, y0]]]}

    # ---- registry ----

    def test_registry_equals_evaluate_codes_for_every_plot_and_level(self):
        loaded = di.registry_from_bytes(di.registry_to_bytes(self.registry))
        for registry in (self.registry, loaded):
            for plot in self.plots:
                for level, codes in self.codes.items():
                    with self.subTest(plot=plot['plot_id'], level=level):
                        self.assertEqual(di.registry_evaluate(codes, registry['plots'][plot['plot_id']], level),
                                         decision.evaluate_codes(codes, self.metadata, plot['geometry'], level))
                        self.assertEqual(di.registry_evaluate_store(codes, self.header(level), registry['plots'][plot['plot_id']]),
                                         decision.evaluate_store(codes, self.header(level), plot['geometry']))

    def test_registry_entries_are_the_selection_under_the_shared_rule(self):
        height, width = self.metadata['shape']
        for plot in self.plots:
            rows, cols = select_cells(self.metadata, plot['geometry'])
            inside = (rows >= 0) & (rows < height) & (cols >= 0) & (cols < width)
            entry = self.registry['plots'][plot['plot_id']]
            self.assertEqual(entry['flat_index'].dtype, np.int32)
            np.testing.assert_array_equal(entry['flat_index'], rows[inside] * width + cols[inside])
            self.assertTrue(np.all(np.diff(entry['flat_index']) > 0))
            self.assertEqual(entry['selected_count'], rows.size)
            self.assertEqual(entry['outside_count'], int((~inside).sum()))
            self.assertEqual(entry['geometry_sha256'], object_hash(plot['geometry']))
        self.assertEqual(self.registry['grid'], di.grid_identity(self.metadata))

    def test_registry_evaluate_needs_no_selection_and_rejects_foreign_codes(self):
        entry = next(iter(self.registry['plots'].values()))
        with mock.patch('engine.query.select_cells', side_effect=AssertionError('selected')):
            di.registry_evaluate(self.codes[decision.SCREEN_VERSION], entry, decision.SCREEN_VERSION)
        bad = self.codes[decision.SCREEN_VERSION].copy()
        bad[tuple(divmod(int(entry['flat_index'][0]), bad.shape[1]))] = 25
        with self.assertRaises(ValueError):
            di.registry_evaluate(bad, entry, decision.SCREEN_VERSION)

    def test_registry_with_out_of_chip_and_empty_selections(self):
        a, _, c, _, e, f = self.metadata['transform']
        plots = [{'plot_id': 'edge', 'geometry': self.square(-3, -3, rows=6, cols=6)},
                 {'plot_id': 'gone', 'geometry': self.square(-50, -50, rows=2, cols=2)},
                 {'plot_id': 'none', 'geometry': {'type': 'Polygon', 'coordinates': [[
                     [c + .1 * a, f + .1 * e], [c + .2 * a, f + .1 * e], [c + .2 * a, f + .2 * e], [c + .1 * a, f + .1 * e]]]}}]
        registry = di.build_registry(plots, self.metadata)
        again = di.registry_from_bytes(di.registry_to_bytes(registry))
        codes = self.codes[decision.SCREEN_VERSION]
        for plot in plots:
            want = decision.evaluate_codes(codes, self.metadata, plot['geometry'], decision.SCREEN_VERSION)
            self.assertEqual(di.registry_evaluate(codes, registry['plots'][plot['plot_id']], decision.SCREEN_VERSION), want)
            self.assertEqual(di.registry_evaluate(codes, again['plots'][plot['plot_id']], decision.SCREEN_VERSION), want)
        self.assertEqual(registry['plots']['gone']['flat_index'].size, 0)
        self.assertEqual(registry['plots']['none']['selected_count'], 0)

    def test_registry_save_load_is_deterministic(self):
        first, second = self.dir / 'r1.bin', self.dir / 'r2.bin'
        size = di.save_registry(self.registry, first)
        di.save_registry(copy.deepcopy(self.registry), second)
        self.assertEqual(first.read_bytes(), second.read_bytes())
        self.assertEqual(size, first.stat().st_size)
        loaded = di.load_registry(first)
        self.assertEqual(loaded['grid'], self.registry['grid'])
        self.assertEqual(list(loaded['plots']), list(self.registry['plots']))
        for plot_id, entry in self.registry['plots'].items():
            got = loaded['plots'][plot_id]
            np.testing.assert_array_equal(got['flat_index'], entry['flat_index'])
            self.assertEqual(got['flat_index'].dtype, np.int32)
            self.assertEqual({k: v for k, v in got.items() if k != 'flat_index'},
                             {k: v for k, v in entry.items() if k != 'flat_index'})
        di.save_registry(loaded, self.dir / 'r3.bin')
        self.assertEqual(first.read_bytes(), (self.dir / 'r3.bin').read_bytes())
        rebuilt = di.registry_to_bytes(di.build_registry(self.plots, self.metadata))
        self.assertEqual(rebuilt, first.read_bytes())

    def header(self, level):
        """What read_store would return alongside the level's raster."""
        return {**di.grid_identity(self.metadata), 'level': level}

    def test_registry_file_corruption_is_rejected(self):
        data = di.registry_to_bytes(self.registry)
        flipped = bytearray(data)
        flipped[-3] ^= 1
        header_size = int.from_bytes(data[8:12], 'little')
        header = json.loads(data[di.PREFIX_BYTES:di.PREFIX_BYTES + header_size])
        header['plots'][0]['outside_count'] += 1
        tampered = json.dumps(header, sort_keys=True, separators=(',', ':')).encode()
        no_keys = b'{"schema":"plotline.decision-registry.v2"}'
        for name, blob in (('header without fields', sealed_registry(no_keys, b'')),
                           ('bit flip', bytes(flipped)), ('truncated payload', data[:-4]), ('truncated header', data[:20]),
                           ('magic', b'x' + data[1:]), ('previous magic', b'PLDREG1\n' + data[8:]), ('empty', b''),
                           ('header counts, hash not updated', data[:8] + len(tampered).to_bytes(4, 'little')
                            + data[12:di.PREFIX_BYTES] + tampered + data[di.PREFIX_BYTES + header_size:]),
                           ('header counts, hash recomputed', sealed_registry(tampered, data[di.PREFIX_BYTES + header_size:]))):
            with self.subTest(case=name), self.assertRaises(ValueError):
                di.registry_from_bytes(blob)

    def test_every_bit_flip_in_a_registry_file_is_rejected(self):
        data = di.registry_to_bytes(di.build_registry(self.plots[:2], self.metadata))
        self.assertLess(len(data), 1000)
        for position in range(len(data)):
            for bit in range(8):
                flipped = bytearray(data)
                flipped[position] ^= 1 << bit
                with self.subTest(position=position, bit=bit), self.assertRaises(ValueError):
                    di.registry_from_bytes(bytes(flipped))

    def test_registry_runs_are_bounded_before_they_are_expanded(self):
        grid = di.grid_identity(self.metadata)
        cells = grid['shape'][0] * grid['shape'][1]
        hostile = {
            'run longer than the grid': ([plot_record(1, 2 ** 24)], [0], [2 ** 24]),
            'run past the last cell': ([plot_record(1, 10)], [cells - 5], [10]),
            'start before the grid': ([plot_record(1, 3)], [-1], [3]),
            'zero-length run': ([plot_record(1, 0)], [5], [0]),
            'negative length': ([plot_record(1, 0)], [5], [-3]),
            'overlapping runs': ([plot_record(2, 8)], [0, 3], [5, 3]),
            'unsorted runs': ([plot_record(2, 6)], [10, 0], [3, 3]),
            'touching runs are not maximal': ([plot_record(2, 6)], [0, 3], [3, 3]),
            'accounting mismatch': ([plot_record(1, 4)], [0], [3]),
        }
        for name, (plots, starts, lengths) in hostile.items():
            with self.subTest(case=name), self.assertRaises(ValueError):
                di.registry_from_bytes(forge_registry(plots, starts, lengths, grid))
        with self.assertRaises(ValueError):  # a whole 4000 x 4000 grid in one plot is more than select_cells can produce
            di.registry_from_bytes(forge_registry([plot_record(1, 11_000_000)], [0], [11_000_000], dict(grid, shape=[4000, 4000])))
        whole = di.registry_from_bytes(forge_registry([plot_record(1, cells)], [0], [cells], grid))  # legitimate: every cell
        self.assertEqual(whole['plots']['X']['flat_index'].size, cells)
        blob = forge_registry([plot_record(1, 2 ** 24)], [0], [2 ** 24], grid)
        self.assertLess(len(blob), 600)
        started = time.perf_counter()
        self.assertLess(peak_bytes(lambda: di.registry_from_bytes(blob)), 1_000_000)  # 270 MB when expanded first
        self.assertLess(time.perf_counter() - started, 1.0)
        ok = forge_registry([plot_record(2, 8, 2)], [0, 100], [3, 3], grid)
        np.testing.assert_array_equal(di.registry_from_bytes(ok)['plots']['X']['flat_index'], [0, 1, 2, 100, 101, 102])
        self.assertEqual(di.MAX_PLOT_CELLS, __import__('engine.query', fromlist=['x']).MAX_CANDIDATE_CELLS)
        big = dict(grid, shape=[4000, 4000])  # 4 plots of 3M cells: each within the per-plot cap, 12M in total
        many = forge_registry([plot_record(1, 3_000_000, plot_id=f'P{i}') for i in range(4)], [0] * 4, [3_000_000] * 4, big)
        self.assertLess(len(many), 2000)
        with self.assertRaises(ValueError):
            di.registry_from_bytes(many)
        started = time.perf_counter()
        self.assertLess(peak_bytes(lambda: di.registry_from_bytes(many)), 1_000_000)  # 12M int32 cells if expanded
        self.assertLess(time.perf_counter() - started, 1.0)

    def test_registry_header_types_and_grid_are_validated(self):
        grid = di.grid_identity(self.metadata)
        good = [plot_record()]
        bad_headers = {
            'shape is text': dict(grid, shape='ab'), 'shape has a bool': dict(grid, shape=[True, 5]),
            'shape too big for int32 flat index': dict(grid, shape=[2 ** 16, 2 ** 16]), 'zero shape': dict(grid, shape=[0, 5]),
            'empty transform': dict(grid, transform=[]), 'transform text': dict(grid, transform=['a'] * 6),
            'transform overflow': dict(grid, transform=[10 ** 400] + grid['transform'][1:]),
            'crs not text': dict(grid, crs=4326), 'extra grid key': dict(grid, extra=1), 'grid is a list': [1, 2]}
        for name, bad in bad_headers.items():
            with self.subTest(grid=name), self.assertRaises(ValueError):
                di.registry_from_bytes(forge_registry(good, [0], [1], bad))
        bad_plots = {  # each defect on an otherwise consistent file (one run of one cell per record)
            'runs is a float': [plot_record(1.5)], 'runs is a bool': [plot_record(True)], 'negative runs': [plot_record(-1)],
            'duplicate ids': [plot_record(), plot_record()], 'bad digest': [dict(plot_record(), geometry_sha256='XY')],
            'extra plot key': [dict(plot_record(), extra=1)], 'plot not an object': [5], 'id not text': [plot_record(plot_id=7)],
            'negative outside count': [plot_record(1, 0, -1)]}
        for name, plots in bad_plots.items():
            with self.subTest(plots=name), self.assertRaises(ValueError):
                di.registry_from_bytes(forge_registry(plots, [0, 10], [1, 1], grid))
        self.assertEqual(list(di.registry_from_bytes(forge_registry([plot_record(), plot_record(plot_id='Y')], [0, 10], [1, 1], grid))['plots']), ['X', 'Y'])
        for name, extra in {'payload_bytes is text': {'payload_bytes': '8'}, 'bad payload digest': {'payload_sha256': 'x'},
                            'unknown top-level key': {'extra': 1}, 'selection rule not text': {'selection_rule': 3},
                            'old schema': {'schema': 'plotline.decision-registry.v1'}}.items():
            with self.subTest(header=name), self.assertRaises(ValueError):
                di.registry_from_bytes(forge_registry(good, [0], [1], grid, extra))
        with self.assertRaises(ValueError):
            di.registry_from_bytes(sealed_registry(b'[1,2]', b''))
        with self.assertRaises(ValueError):
            di.registry_from_bytes(sealed_registry(b'[' * 20000 + b']' * 20000, b''))

    def test_registry_evaluate_binds_the_level_and_the_raster_to_the_registry(self):
        pid = self.plots[4]['plot_id']
        entry = self.registry['plots'][pid]
        screen, decision_codes = self.codes[decision.SCREEN_VERSION], self.codes[decision.DECISION_VERSION]
        with self.assertRaises(TypeError):
            di.registry_evaluate(screen, entry)  # the level has no default
        with self.assertRaises(ValueError):
            di.registry_evaluate(screen[:100, :100], entry, decision.SCREEN_VERSION)
        with self.assertRaises(ValueError):
            di.registry_evaluate(np.ascontiguousarray(screen.T), entry, decision.SCREEN_VERSION)
        for level, codes in self.codes.items():
            other = decision.DECISION_VERSION if level == decision.SCREEN_VERSION else decision.SCREEN_VERSION
            header = self.header(level)
            self.assertEqual(di.registry_evaluate_store(codes, header, entry),
                             decision.evaluate_codes(codes, self.metadata, self.plots[4]['geometry'], level))
            self.assertEqual(di.registry_evaluate_store(codes, header, entry, level)['contract'], level)
            with self.assertRaisesRegex(ValueError, 'store holds'):
                di.registry_evaluate_store(codes, header, entry, other)
            for broken in ({**header, 'shape': [604, 1234]}, {**header, 'crs': 'EPSG:3857'},
                           {**header, 'transform': [header['transform'][0], 0.0, header['transform'][2] + 1e-9, *header['transform'][3:]]}):
                with self.assertRaisesRegex(ValueError, 'grid'):
                    di.registry_evaluate_store(codes, broken, entry)
        for header in ({'shape': [604, 1233]}, {**self.header(decision.SCREEN_VERSION), 'level': 'eudr-screen.v2'}):
            with self.assertRaises(ValueError):
                di.registry_evaluate_store(screen, header, entry)
        # the footgun: a decision raster read as screen drops the Hansen loss on non-forest land; the store-aware API cannot be asked
        p5 = next(p for p in self.plots if p['plot_id'] == 'P-0005')
        header = self.header(decision.DECISION_VERSION)
        with self.assertRaises(ValueError):
            di.registry_evaluate_store(decision_codes, header, self.registry['plots']['P-0005'], decision.SCREEN_VERSION)
        with self.assertRaises(ValueError):
            decision.evaluate_store(decision_codes, header, p5['geometry'], decision.SCREEN_VERSION)

    def test_registry_lookup_goes_stale_on_geometry_or_grid_change(self):
        plot = self.plots[0]
        pid, geometry = plot['plot_id'], plot['geometry']
        self.assertIs(di.registry_lookup(self.registry, pid, geometry, self.metadata), self.registry['plots'][pid])
        with self.assertRaises(TypeError):
            di.registry_lookup(self.registry, pid, geometry)  # the grid is always compared, so it is always required
        nudged = copy.deepcopy(geometry)
        nudged['coordinates'][0][0][0] = float(np.nextafter(nudged['coordinates'][0][0][0], 1e9))
        reordered = copy.deepcopy(geometry)
        reordered['coordinates'][0] = reordered['coordinates'][0][1:-1] + reordered['coordinates'][0][1:2]
        self.assertIsNone(di.registry_lookup(self.registry, pid, nudged, self.metadata))
        self.assertIsNone(di.registry_lookup(self.registry, pid, reordered, self.metadata))
        self.assertIsNone(di.registry_lookup(self.registry, 'missing', geometry, self.metadata))
        self.assertIsNone(di.registry_lookup(self.registry, self.plots[1]['plot_id'], geometry, self.metadata))
        shifted = dict(self.metadata, transform=[self.metadata['transform'][0], 0, np.nextafter(self.metadata['transform'][2], 1e9),
                                                 *self.metadata['transform'][3:]])
        for name, grid in (('transform', shifted), ('shape', dict(self.metadata, shape=[604, 1234])),
                           ('crs', dict(self.metadata, crs='EPSG:3857'))):
            with self.subTest(grid=name):
                self.assertIsNone(di.registry_lookup(self.registry, pid, geometry, grid))
        loaded = di.registry_from_bytes(di.registry_to_bytes(self.registry))
        self.assertIsNotNone(di.registry_lookup(loaded, pid, geometry, self.metadata))
        self.assertIsNone(di.registry_lookup(loaded, pid, geometry, shifted))

    def test_duplicate_plot_ids_are_rejected(self):
        with self.assertRaises(ValueError):
            di.build_registry(self.plots + self.plots[:1], self.metadata)
        with self.assertRaises(ValueError):
            di.build_table(self.plots + self.plots[:1], self.codes, {k: v[0] for k, v in self.stores.items()}, self.metadata)

    def test_geometry_hash_is_canonical_and_matches_object_hash(self):
        for plot in self.plots:
            self.assertEqual(di.geometry_sha256(plot['geometry']), object_hash(plot['geometry']))
        a = {'type': 'Polygon', 'coordinates': [[[0, 0], [1, 0], [1, 1], [0, 0]]]}
        b = {'coordinates': [[[0, 0], [1, 0], [1, 1], [0, 0]]], 'type': 'Polygon'}
        self.assertEqual(di.geometry_sha256(a), di.geometry_sha256(b))
        with self.assertRaises(ValueError):
            di.geometry_sha256({'type': 'Polygon', 'coordinates': [[[0, float('nan')]]]})

    # ---- table ----

    def test_table_equals_evaluate_codes_before_and_after_json_round_trip(self):
        path = self.dir / 'table.json'
        di.save_table(self.table, path)
        loaded = di.load_table(path)
        for table in (self.table, loaded):
            for plot in self.plots:
                digest = di.geometry_sha256(plot['geometry'])
                for level, codes in self.codes.items():
                    with self.subTest(plot=plot['plot_id'], level=level):
                        got = di.table_lookup(table, plot['plot_id'], digest, self.stores[level][0], level, self.metadata)
                        self.assertEqual(got, decision.evaluate_codes(codes, self.metadata, plot['geometry'], level))

    def test_table_lookup_goes_stale_on_any_key_change(self):
        plot = self.plots[3]
        pid, digest = plot['plot_id'], di.geometry_sha256(plot['geometry'])
        level = decision.SCREEN_VERSION
        store, grid = self.stores[level][0], self.metadata
        self.assertIsNotNone(di.table_lookup(self.table, pid, digest, store, level, grid))
        other = decision.DECISION_VERSION
        self.assertIsNone(di.table_lookup(self.table, pid, digest, self.stores[other][0], level, grid))  # other level's store
        self.assertIsNone(di.table_lookup(self.table, pid, digest, '0' * 64, level, grid))
        self.assertIsNone(di.table_lookup(self.table, pid, '0' * 64, store, level, grid))
        self.assertIsNone(di.table_lookup(self.table, 'missing', digest, store, level, grid))
        self.assertIsNone(di.table_lookup(self.table, pid, digest, store, 'eudr-screen.v2', grid))
        changed = self.codes[level].copy()
        changed[0, 0] = (changed[0, 0] + 1) % decision.CODE_COUNT
        self.assertNotEqual(di.store_sha256(level, changed, '/nonexistent')[0], store)

    def test_table_content_hash_is_verified_on_load(self):
        path = self.dir / 'sealed.json'
        di.save_table(self.table, path)
        self.assertEqual(self.table['content_sha256'], di.table_digest(self.table))
        self.assertEqual(self.table['content_sha256'],
                         hashlib.sha256(di.canonical_bytes({k: v for k, v in self.table.items() if k != 'content_sha256'})).hexdigest())
        self.assertEqual(di.load_table(path), self.table)
        pid, level = self.plots[0]['plot_id'], decision.DECISION_VERSION
        edited = json.loads(path.read_bytes())
        edited['plots'][pid]['outputs'][level]['deforestation_after_2020']['present'] = False  # True -> False, as the validator did
        grid_edit = json.loads(path.read_bytes())
        grid_edit['grid']['transform'][2] += 0.0001
        stale = json.loads(path.read_bytes())
        del stale['content_sha256']
        for name, content in (('edited output', edited), ('edited grid', grid_edit), ('hash removed', stale),
                              ('hash wrong', {**edited, 'content_sha256': '0' * 64}), ('hash not text', {**stale, 'content_sha256': 5}),
                              ('old schema', {**stale, 'schema': 'plotline.decision-table.v1'})):
            bad = self.dir / 'edited.json'
            bad.write_bytes(di.canonical_bytes(content))
            with self.subTest(case=name), self.assertRaises(ValueError):
                di.load_table(bad)
        resealed = {**edited, 'content_sha256': di.table_digest(edited)}  # whoever can recompute the hash can forge: integrity only
        bad.write_bytes(di.canonical_bytes(resealed))
        self.assertIs(di.table_lookup(di.load_table(bad), pid, di.geometry_sha256(self.plots[0]['geometry']),
                                      self.stores[level][0], level, self.metadata)['deforestation_after_2020']['present'], False)
        for blob in (b'', b'[1]', b'{', b'[' * 20000 + b']' * 20000):
            bad.write_bytes(blob)
            with self.assertRaises(ValueError):
                di.load_table(bad)

    def test_table_lookup_needs_the_live_grid_unless_keyed_by_a_store_file(self):
        pid, geometry = self.plots[0]['plot_id'], self.plots[0]['geometry']
        digest, level = di.geometry_sha256(geometry), decision.DECISION_VERSION
        store = self.stores[level][0]
        self.assertEqual(self.table['store_basis'][level], 'code-raster-bytes')  # the cell bytes do not bind the grid
        with self.assertRaisesRegex(ValueError, 'live grid'):
            di.table_lookup(self.table, pid, digest, store, level)
        shifted = dict(self.metadata, transform=[self.metadata['transform'][0], 0, self.metadata['transform'][2] + 0.00025,
                                                 *self.metadata['transform'][3:]])
        self.assertIsNone(di.table_lookup(self.table, pid, digest, store, level, shifted))
        self.assertIsNone(di.table_lookup(self.table, pid, digest, store, level, dict(self.metadata, shape=[605, 1233])))
        self.assertIsNotNone(di.table_lookup(self.table, pid, digest, store, level, self.metadata))
        self.assertIsNotNone(di.table_lookup(self.table, pid, digest, store, level, self.header(level)))  # a store header works too
        keyed = di.build_table(self.plots[:2], self.codes, {k: v[0] for k, v in self.stores.items()}, self.metadata,
                               {level: f'file:{di.STORE_FILES[level]}' for level in decision.LEVELS})
        self.assertIsNotNone(di.table_lookup(keyed, pid, digest, store, level))  # the file hash binds the header's grid
        self.assertIsNone(di.table_lookup(keyed, pid, digest, store, level, shifted))  # a grid that is passed is still compared

    def test_table_save_load_is_deterministic_and_records_store_basis(self):
        one, two = self.dir / 't1.json', self.dir / 't2.json'
        di.save_table(self.table, one)
        di.save_table(di.load_table(one), two)
        self.assertEqual(one.read_bytes(), two.read_bytes())
        self.assertEqual(self.table['store_basis'], {level: 'code-raster-bytes' for level in decision.LEVELS})
        self.assertEqual(self.table['stores'][decision.SCREEN_VERSION],
                         hashlib.sha256(self.codes[decision.SCREEN_VERSION].tobytes()).hexdigest())
        self.assertEqual(self.table['grid'], di.grid_identity(self.metadata))
        with self.assertRaises(ValueError):
            (self.dir / 'bad.json').write_text('{"schema":"other"}')
            di.load_table(self.dir / 'bad.json')

    def test_store_identity_prefers_a_verified_store_file(self):
        from engine.decision_store import write_store
        folder = self.dir / 'stores'
        folder.mkdir()
        level, codes = decision.SCREEN_VERSION, self.codes[decision.SCREEN_VERSION]
        self.assertEqual(di.store_sha256(level, codes, folder)[1], 'code-raster-bytes')
        self.assertFalse(di.check_store(level, codes, folder))
        metadata = {**self.metadata, 'jrc_chip_sha256': self.jrc.metadata['chip_sha256']}
        write_store(codes, metadata, folder / 'screen.plds', level=level, encoding='zstd19')
        digest, basis = di.store_sha256(level, codes, folder)
        self.assertEqual((digest, basis), (hashlib.sha256((folder / 'screen.plds').read_bytes()).hexdigest(), 'file:screen.plds'))
        self.assertNotEqual(digest, di.store_sha256(level, codes, '/nonexistent')[0])
        self.assertTrue(di.check_store(level, codes, folder))
        self.assertTrue(di.check_store(level, codes, folder, self.metadata))
        with self.assertRaisesRegex(ValueError, 'grid'):
            di.check_store(level, codes, folder, dict(self.metadata, transform=[*self.metadata['transform'][:2],
                                                                                 self.metadata['transform'][2] + 1e-4,
                                                                                 *self.metadata['transform'][3:]]))
        with self.assertRaisesRegex(ValueError, 'store holds'):  # the screen file does not hold the decision level
            (folder / 'decision.plds').write_bytes((folder / 'screen.plds').read_bytes())
            di.check_store(decision.DECISION_VERSION, decision.project_decision(codes), folder)
        changed = codes.copy()
        changed[0, 0] = (changed[0, 0] + 1) % decision.CODE_COUNT
        with self.assertRaises(ValueError):
            di.check_store(level, changed, folder)

    # ---- exact fast selection ----

    def test_fast_selection_is_exact_on_the_real_plots(self):
        for plot in self.plots:
            with self.subTest(plot=plot['plot_id']):
                self.assertGreater(self.assertSameSelection(plot['geometry']), 0)

    def test_fast_selection_exact_on_boundary_cases(self):
        a, e = self.metadata['transform'][0], self.metadata['transform'][4]
        r, c = 200, 300
        cx, cy = self.cx, self.cy
        up, down = np.inf, -np.inf

        def triangle(*pts):  # any closed ring from points
            return {'type': 'Polygon', 'coordinates': [[list(p) for p in pts] + [list(pts[0])]]}

        def hole_poly(outer, *holes):
            def ring(x0, y0, x1, y1):
                return [[x0, y0], [x1, y0], [x1, y1], [x0, y1], [x0, y0]]
            return {'type': 'Polygon', 'coordinates': [ring(*outer)] + [ring(*h) for h in holes]}

        cases = {
            'rect edges through centres': self.square(r, c, rows=4, cols=5),
            'rect edges on cell boundaries': self.square(r, c, half=.5, rows=3, cols=3),
            'rect shifted one ulp left': triangle(*[(float(np.nextafter(x, 0)), y) for x, y in
                                              [(cx(c), cy(r)), (cx(c + 3), cy(r)), (cx(c + 3), cy(r + 3)), (cx(c), cy(r + 3))]]),
            'rect one ulp outside left': triangle((float(np.nextafter(cx(c), down)), cy(r)), (cx(c + 3), cy(r)),
                                                  (cx(c + 3), cy(r + 3)), (float(np.nextafter(cx(c), down)), cy(r + 3))),
            'rect top edge one ulp above row': triangle((cx(c), float(np.nextafter(cy(r), up))), (cx(c + 3), float(np.nextafter(cy(r), up))),
                                                        (cx(c + 3), cy(r + 3)), (cx(c), cy(r + 3))),
            'triangle vertices on centres': triangle((cx(c), cy(r)), (cx(c + 6), cy(r)), (cx(c), cy(r + 6))),
            'diagonal through many centres': triangle((cx(c), cy(r)), (cx(c + 40), cy(r + 40)), (cx(c + 40), cy(r))),
            'steep lattice line': triangle((cx(c), cy(r)), (cx(c + 7), cy(r + 31)), (cx(c + 30), cy(r + 3))),
            'diamond on plus-shaped centres': triangle((cx(c), cy(r - 2)), (cx(c + 2), cy(r)), (cx(c), cy(r + 2)), (cx(c - 2), cy(r))),
            'vertex-only touch at local extremum': triangle((cx(c), cy(r)), (cx(c - 3), cy(r + 4)), (cx(c + 3), cy(r + 4))),
            'L shape with horizontal edges on rows': {'type': 'Polygon', 'coordinates': [[
                [cx(c), cy(r + 3)], [cx(c), cy(r)], [cx(c + 3), cy(r)], [cx(c + 3), cy(r + 1)],
                [cx(c + 1), cy(r + 1)], [cx(c + 1), cy(r + 3)], [cx(c), cy(r + 3)]]]},
            'hole edges through centres': hole_poly((cx(c), cy(r + 8), cx(c + 8), cy(r)), (cx(c + 2), cy(r + 6), cx(c + 5), cy(r + 2))),
            'hole one ulp inside centres': hole_poly((cx(c) - a, cy(r + 8) + e, cx(c + 8) + a, cy(r) - e),
                                                     (float(np.nextafter(cx(c + 2), up)), cy(r + 6), cx(c + 5), cy(r + 2))),
            'two holes sharing a centre row': hole_poly((cx(c), cy(r + 9), cx(c + 12), cy(r)), (cx(c + 2), cy(r + 6), cx(c + 4), cy(r + 3)),
                                                        (cx(c + 7), cy(r + 6), cx(c + 10), cy(r + 3))),
            'tiny around a centre': self.square(r, c, half=1e-13 / abs(a)),
            'sub-cell between centres': triangle((cx(c) + .2 * a, cy(r) + .2 * e), (cx(c) + .4 * a, cy(r) + .2 * e),
                                                 (cx(c) + .4 * a, cy(r) + .4 * e)),
            'partly out of chip top-left': self.square(-4, -4, rows=8, cols=8),
            'partly out of chip bottom-right': self.square(self.metadata['shape'][0] - 3, self.metadata['shape'][1] - 3,
                                                           half=.5, rows=3, cols=3),
            'fully out of chip': self.square(-80, 40, rows=3, cols=3),
            'multipolygon touching at a centre': {'type': 'MultiPolygon', 'coordinates': [
                self.square(r, c, rows=3, cols=3)['coordinates'], self.square(r + 2, c + 2, rows=3, cols=3)['coordinates']]},
            'island inside a hole': {'type': 'MultiPolygon', 'coordinates': [
                hole_poly((cx(c), cy(r + 12), cx(c + 12), cy(r)), (cx(c + 2), cy(r + 10), cx(c + 10), cy(r + 2)))['coordinates'],
                self.square(r + 4, c + 4, rows=3, cols=3)['coordinates']]},
        }
        counts = {name: self.assertSameSelection(geometry) for name, geometry in cases.items()}
        self.assertEqual(counts['sub-cell between centres'], 0)
        self.assertTrue(all(n > 0 for name, n in counts.items() if name != 'sub-cell between centres'), counts)

    def test_fast_selection_exact_across_row_chunks(self):
        geometries = [self.square(150, 250, half=.5, rows=30, cols=30), self.plots[4]['geometry'],
                      *fuzz_geometries(self.metadata, 300, seed=5)]
        for pairs in (4, 12):  # forces many row chunks per polygon
            with mock.patch.object(di, 'MAX_ROW_PAIRS', pairs):
                for geometry in geometries:
                    self.assertSameSelection(geometry)

    def test_fast_selection_exact_on_large_polygons(self):
        rng = np.random.default_rng(11)
        a, e = self.metadata['transform'][0], self.metadata['transform'][4]
        centre = (self.cx(600), self.cy(300))

        def radial(n, radius, wave, jitter=1.0):
            ang = np.linspace(0, 2 * math.pi, n, endpoint=False)
            rad = radius * (1 + wave * np.sin(7 * ang)) + rng.uniform(-jitter, jitter, n)
            pts = [[centre[0] + math.cos(t) * q * a, centre[1] + math.sin(t) * q * -e] for t, q in zip(ang, rad)]
            return {'type': 'Polygon', 'coordinates': [pts + pts[:1]]}

        steps = [[self.cx(100), self.cy(100)]]
        for i in range(1, 60):  # vertices exactly on centres, horizontal and vertical edges on centre rows and columns
            steps += [[self.cx(100 + i), self.cy(99 + i)], [self.cx(100 + i), self.cy(100 + i)]]
        steps += [[self.cx(100), self.cy(160)], steps[0]]
        for name, geometry in {'wavy circle': radial(400, 120, .3), 'spiky star': radial(300, 100, .6, 0),
                               'lattice staircase': {'type': 'Polygon', 'coordinates': [steps]}}.items():
            with self.subTest(case=name):
                self.assertGreater(self.assertSameSelection(geometry), 1000)

    def test_fast_selection_exact_on_seeded_fuzz(self):
        accepted = rejected = cells = 0
        for i, geometry in enumerate(fuzz_geometries(self.metadata, FUZZ_COUNT)):
            status = outcome(select_cells, self.metadata, geometry)
            with self.subTest(index=i):
                self.assertSameSelection(geometry)
            accepted += status[0] == 'ok'
            rejected += status[0] == 'err'
            cells += len(status[1][0]) if status[0] == 'ok' else 0
        self.assertGreater(accepted, FUZZ_COUNT * .8)
        self.assertGreater(rejected, 0)  # invalid blobs must be rejected identically
        self.assertGreater(cells, 10 * FUZZ_COUNT)

    def test_fast_selection_rejects_exactly_like_select_cells(self):
        extra = {
            'tuple_positions': {'type': 'Polygon', 'coordinates': [[(0, 0), (1, 0), (1, 1), (0, 0)]]},
            'numpy_scalar_coordinates': {'type': 'Polygon', 'coordinates': [[[np.float64(98.8), np.int64(8)], [98.9, 8], [98.9, 8.1], [np.float64(98.8), np.int64(8)]]]},
            'huge_int': {'type': 'Polygon', 'coordinates': [[[0, 0], [10 ** 400, 0], [1, 1], [0, 0]]]},
            'float_subclass': {'type': 'Polygon', 'coordinates': [[[type('F', (float,), {})(98.8), 8.0], [98.9, 8.0], [98.9, 8.1], [98.8, 8.0]]]},
            'ring_not_list': {'type': 'Polygon', 'coordinates': ['abc']},
            'polygon_not_list': {'type': 'MultiPolygon', 'coordinates': [5]},
            'coordinates_is_dict': {'type': 'Polygon', 'coordinates': {}},
            'too_many_vertices': {'type': 'Polygon', 'coordinates': [[[98.8 + i * 1e-9, 8.0] for i in range(100_001)] + [[98.8, 8.0]]]},
            'bounds_too_large_for_lattice': {'type': 'Polygon', 'coordinates': [[[0, 0], [1e300, 0], [1e300, 1e300], [0, 0]]]},
            'candidate_cap': {'type': 'Polygon', 'coordinates': [[[0, 0], [1, 0], [1, 1], [0, 0]]]},
            'valid_but_degenerate_spike': {'type': 'Polygon', 'coordinates': [[[98.8, 8.5], [98.9, 8.5], [98.85, 8.5], [98.8, 8.5]]]},
        }
        for name, geometry in {**INVALID_GEOMETRIES, **extra}.items():
            with self.subTest(case=name):
                if name in INVALID_GEOMETRIES:
                    self.assertEqual(outcome(select_cells, self.metadata, geometry)[0], 'err')
                self.assertSameSelection(geometry)
        square = self.square(100, 100)
        grids = {'rotated_b': [1, .5, 0, 0, -1, 1], 'rotated_d': [1, 0, 0, .5, -1, 1], 'south_up': [1, 0, 0, 0, 1, 1],
                 'west_up': [-1, 0, 0, 0, -1, 1], 'zero_scale': [0, 0, 0, 0, -1, 1],
                 'nonfinite': [1, 0, float('nan'), 0, -1, 1], 'short': [1, 0, 0]}
        for name, transform in grids.items():
            with self.subTest(grid=name):
                metadata = dict(self.metadata, transform=transform)
                self.assertEqual(outcome(select_cells, metadata, square)[0], 'err')
                self.assertSameSelection(square, metadata)
        for metadata in (dict(self.metadata, crs='EPSG:3857'), {k: v for k, v in self.metadata.items() if k != 'transform'}):
            self.assertEqual(outcome(select_cells, metadata, square)[0], 'err')
            self.assertSameSelection(square, metadata)

    def test_fast_selection_falls_back_outside_its_numeric_envelope(self):
        tiny_grid = dict(self.metadata, transform=[1e-16, 0, 0, 0, -1e-16, 0])
        far = {'type': 'Polygon', 'coordinates': [[[.5, .5], [.5 + 1e-15, .5], [.5 + 1e-15, .5 - 1e-15], [.5, .5]]]}
        self.assertGreater(.5 / 1e-16, 2 ** 50)
        with mock.patch('engine.query.select_cells', wraps=select_cells) as spy:
            self.assertSameSelection(far, tiny_grid)
        self.assertEqual(spy.call_count, 1)  # the fallback; the reference call uses the unpatched name
        with mock.patch('engine.query.select_cells', wraps=select_cells) as spy:
            di.fast_select_cells(self.metadata, self.plots[0]['geometry'])
        spy.assert_not_called()

    # ---- cold start ----

    def run_python(self, code):
        done = subprocess.run([sys.executable, '-B', '-c', code], cwd=ROOT, capture_output=True, text=True, check=True)
        return json.loads(done.stdout)

    def test_light_import_paths(self):
        table, registry = self.dir / 'light-table.json', self.dir / 'light-registry.bin'
        di.save_table(self.table, table)
        di.save_registry(self.registry, registry)
        probe = ("import json, sys\nloaded = lambda: sorted(m for m in ('numpy', 'shapely', 'rasterio', 'engine.query', 'engine.source') "
                 "if m in sys.modules)\n")
        plain = self.run_python(probe + "import engine.decision_index\nprint(json.dumps(loaded()))")
        self.assertEqual(plain, [])
        pid = self.plots[0]['plot_id']
        digest = di.geometry_sha256(self.plots[0]['geometry'])
        level, store = decision.SCREEN_VERSION, self.stores[decision.SCREEN_VERSION][0]
        via_table = self.run_python(probe + f"from engine import decision_index as di\nt = di.load_table({str(table)!r})\n"
                                    f"out = di.table_lookup(t, {pid!r}, di.geometry_sha256({self.plots[0]['geometry']!r}), {store!r}, {level!r}, "
                                    f"{di.grid_identity(self.metadata)!r})\n"
                                    "print(json.dumps([loaded(), out['selected_cell_count']]))")
        self.assertEqual(via_table[0], [])
        self.assertEqual(via_table[1], self.table['plots'][pid]['outputs'][level]['selected_cell_count'])
        self.assertEqual(digest, object_hash(self.plots[0]['geometry']))
        via_registry = self.run_python(probe + f"import numpy as np\nfrom engine import decision_index as di\nr = di.load_registry({str(registry)!r})\n"
                                       "codes = np.full(tuple(r['grid']['shape']), 2, np.uint8)\n"
                                       f"out = di.registry_evaluate(codes, r['plots'][{pid!r}], {level!r})\n"
                                       "print(json.dumps([loaded(), out['selected_cell_count']]))")
        self.assertEqual(via_registry[0], ['numpy'])
        self.assertEqual(via_registry[1], self.registry['plots'][pid]['selected_count'])

    def test_cli_writes_registry_and_table_that_answer_like_the_full_path(self):
        out = self.dir / 'cli'
        with contextlib.redirect_stdout(io.StringIO()) as printed:
            di.main(['--out', str(out), '--no-timing'])
        self.assertIn('registry.bin', printed.getvalue())
        registry, table = di.load_registry(out / 'registry.bin'), di.load_table(out / 'table.json')
        for plot in self.plots:
            for level, codes in self.codes.items():
                want = decision.evaluate_codes(codes, self.metadata, plot['geometry'], level)
                self.assertEqual(di.registry_evaluate(codes, registry['plots'][plot['plot_id']], level), want)
                self.assertEqual(table['plots'][plot['plot_id']]['outputs'][level], want)


if __name__ == '__main__':
    unittest.main()
