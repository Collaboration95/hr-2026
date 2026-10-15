"""The numpy-free registered re-check (engine.decision_lite) against read_store + registry_evaluate_store (unittest).

Seeded and deterministic. Plot coordinates never appear here: synthetic registries come from seeded polygons
and random runs; the real registry.bin is read from artifacts/ when present, as the other decision tests do.
DECISION_LITE_COUNTS=1 prints how many differential and fuzz cases ran.
"""
import hashlib
import json
import os
from pathlib import Path
import struct
import subprocess
import sys
import tempfile
import time
import tracemalloc
import unittest
import zlib

import numpy as np

from engine import decision, decision_benchmark as bench, decision_index as di, decision_lite as L
from engine import decision_format as F, decision_store as S, decision_summary
from engine.tests.test_decision_index import forge_registry, plot_record, sealed_registry
from engine.tests.test_decision_store import crafted_split, edge_rasters, metadata, replace_header, structured

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / 'artifacts/decision'
COUNTS = {}


def count(name, n=1):
    COUNTS[name] = COUNTS.get(name, 0) + n


def tearDownModule():
    if os.environ.get('DECISION_LITE_COUNTS'):
        print('\ndecision_lite case counts:', json.dumps(COUNTS, sort_keys=True))


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


def split_file(codes, level, mode=None, meta=None):
    """(file bytes, payload) of a split store holding `codes`; mode forces the event coding."""
    payload = b''.join(part for _, part in S._split_parts(codes, mode))
    header = S._header(codes, meta or metadata(*codes.shape), level, 'split', payload)
    return S._file_bytes(header, payload), payload


def project(codes, level):
    return decision.project_decision(codes) if level == S.DECISION_VERSION else codes


def modes_for(codes):
    state = (codes.astype(int) - 2) // 6
    nonforest_loss = bool(((codes > 2) & (codes < 8) & (state == 0)).any())
    return ('plane', 'gaps0') if nonforest_loss else ('plane', 'gaps0', 'gaps1')


def reference(payload, header):
    """What read_store accepts of a payload, short of the decoded raster's hash: the codes or a ValueError."""
    codes = S.decode_codes(payload, header['shape'], 'split')
    S._level_checked(codes, header['level'])
    return codes


def random_plots(rng, h, w, plots, max_runs=7):
    """Seeded plots as lists of (start, length) runs: sorted, disjoint, never touching, some crossing row ends."""
    cells, out = h * w, []
    for _ in range(plots):
        runs, at = [], int(rng.integers(0, max(1, cells // 4)))
        for _ in range(int(rng.integers(0, max_runs + 1))):
            if at >= cells:
                break
            n = min(int(rng.integers(1, 2 * w + 5)), cells - at)
            runs.append((at, n))
            at += n + int(rng.integers(1, max(2, w)))
        out.append(runs)
    return out


def expected_codes(codes, runs):
    flat = codes.reshape(-1)
    return b''.join(flat[s:s + n].tobytes() for s, n in runs)


class ContractTest(unittest.TestCase):
    def test_format_layer_is_shared_with_decision_store_and_stays_off_numpy(self):
        for name in ('MAGIC', 'VERSION', 'PREFIX', 'ENCODINGS', 'SOURCE_KEYS', 'MAX_DIMENSION', 'MAX_CELLS', 'MAX_HEADER_BYTES',
                     'MAX_PAYLOAD_BYTES', 'MAX_WINDOW_LOG', 'MAX_LZMA_MEMORY', 'STORED', 'ZSTD', 'LZMA', 'LZMA_SETS', 'HEX',
                     'LEVELS', 'SCREEN_VERSION', 'DECISION_VERSION', '_Reader', '_get_stream', '_unzstd', '_unlz', '_unxz',
                     '_parse_header', '_canonical', '_digest', '_varint_limit', '_varint', '_shape', '_finite'):
            self.assertIs(getattr(S, name), getattr(F, name), name)
        for name in ('MAGIC', 'PREFIX', 'VERSION', '_Reader', '_get_stream', '_parse_header', '_varint_limit'):
            self.assertIs(getattr(L, name), getattr(F, name), name)
        self.assertEqual(F.LEVELS, decision_summary.LEVELS)
        done = subprocess.run([sys.executable, '-B', '-c', "import sys; import engine.decision_format; print('numpy' in sys.modules)"],
                              cwd=ROOT, capture_output=True, text=True, check=True)
        self.assertEqual(done.stdout.strip(), 'False')

    def test_the_reducer_is_shared_and_decision_reexports_it(self):
        self.assertIs(decision.summarize_counts, decision_summary.summarize_counts)
        self.assertIs(L.summarize_counts, decision_summary.summarize_counts)
        for name in ('SCREEN_VERSION', 'DECISION_VERSION', 'LEVELS', 'POST_YEARS', 'PERIODS', 'FOREST_STATES', 'UNKNOWN',
                     'WATER', 'LAND', 'CODE_COUNT'):
            self.assertIs(getattr(decision, name), getattr(decision_summary, name), name)
        counts = np.arange(decision.CODE_COUNT)
        self.assertEqual(decision.summarize_counts(counts, int(counts.sum()) + 3, 3, S.SCREEN_VERSION),
                         decision.summarize_counts(counts.tolist(), int(counts.sum()) + 3, 3, S.SCREEN_VERSION))
        with self.assertRaises(ValueError):
            decision.summarize_counts(counts.astype(float)[:5], 1, 0, S.SCREEN_VERSION)

    def test_stdlib_only_import_and_answer(self):
        with tempfile.TemporaryDirectory() as tmp:
            registry = Path(tmp) / 'registry.bin'
            grid = di.grid_identity(S.read_store(OUT / 'decision.plds')[1])
            registry.write_bytes(forge_registry([plot_record(2, 10, 2), plot_record(1, 4, plot_id='Y')], [10, 400, 900], [3, 5, 4], grid))
            code = ("import json, sys\nfrom engine import decision_lite as L\n"
                    f"lite = L.load({str(OUT / 'decision.plds')!r}, {str(registry)!r})\n"
                    "out = lite.evaluate('X')\n"
                    "print(json.dumps([out['selected_cell_count'], sorted(m for m in ('numpy', 'shapely', 'rasterio', 'engine.query', "
                    "'engine.source', 'engine.decision', 'engine.decision_store') if m in sys.modules)]))")
            done = subprocess.run([sys.executable, '-B', '-c', code], cwd=ROOT, capture_output=True, text=True, check=True)
        self.assertEqual(json.loads(done.stdout), [10, []])


class FullRasterTest(unittest.TestCase):
    """Every cell through the lite decoder equals read_store's codes."""

    def check(self, label, codes, level, mode):
        blob, payload = split_file(codes, level, mode)
        store = L.open_store(blob)
        h, w = codes.shape
        self.assertEqual(store.codes([[(0, h * w)]])[0], codes.tobytes(), (label, level, mode))
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'store.plds'
            path.write_bytes(blob)
            np.testing.assert_array_equal(S.read_store(path)[0], codes)  # read_store accepts the same file
        count('full raster decodes')

    def test_edge_rasters_every_event_coding_and_level(self):
        for name, raster in edge_rasters().items():
            for level in S.LEVELS:
                codes = project(raster, level)
                for mode in modes_for(codes):
                    with self.subTest(raster=name, level=level, mode=mode):
                        try:
                            self.check(name, codes, level, mode)
                        except KeyError:
                            self.assertEqual(mode, 'gaps1')

    def test_random_plots_over_random_rasters_match_fancy_indexing(self):
        rng = np.random.default_rng(20261015)
        for events in ('forest', 'anywhere', 'dense'):
            for h, w in ((40, 53), (17, 8), (9, 9), (64, 130), (1, 40), (31, 1)):
                codes = structured(h, w, seed=int(rng.integers(1000)), events=events)
                for level in S.LEVELS:
                    raster = project(codes, level)
                    for mode in modes_for(raster):
                        blob, _ = split_file(raster, level, mode)
                        store = L.open_store(blob)
                        plots = random_plots(rng, h, w, 25)
                        got = store.codes(plots)
                        for runs, codes_bytes in zip(plots, got):
                            self.assertEqual(codes_bytes, expected_codes(raster, runs), (events, h, w, level, mode))
                        count('random plots', len(plots))

    def test_real_stores_decode_to_read_store_codes(self):
        for name in ('screen', 'decision'):
            codes, header = S.read_store(OUT / f'{name}.plds')
            store = L.read_store_lite(OUT / f'{name}.plds')
            h, w = header['shape']
            self.assertEqual(store.codes([[(0, h * w)]])[0], codes.tobytes())
            self.assertEqual(store.header, header)
            count('full raster decodes')

    def test_the_store_is_what_the_answer_depends_on(self):
        """Not a table: change a few layer cells and the answers change with them."""
        base = structured(h=30, w=37, events='forest')
        changed = base.copy()
        changed[5:9, 3:20] = 8 + 1  # forest, first loss year
        plots = [[(5 * 37 + 3, 17), (6 * 37 + 3, 17), (7 * 37 + 3, 17)]]
        answers = []
        for raster in (base, changed):
            lite = L.Lite(L.open_store(split_file(raster, S.SCREEN_VERSION)[0]), di.grid_identity(metadata(30, 37)),
                          [dict(plot_record(3, 51, plot_id='X'), runs=plots[0])])
            answers.append(lite.evaluate('X'))
        self.assertNotEqual(answers[0], answers[1])
        self.assertEqual(answers[1]['deforestation_after_2020']['cell_count'], 51)


class RegisteredPlotsTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.stores = {level: S.read_store(OUT / name) for level, name in
                      ((S.SCREEN_VERSION, 'screen.plds'), (S.DECISION_VERSION, 'decision.plds'))}
        cls.header = cls.stores[S.SCREEN_VERSION][1]

    def lite(self, level, registry_bytes):
        grid, plots = L.parse_registry(registry_bytes)
        return L.Lite(L.read_store_lite(OUT / di.STORE_FILES[level]), grid, plots)

    def compare(self, registry, label):
        data = di.registry_to_bytes(registry)
        loaded = di.registry_from_bytes(data)
        for level, (codes, header) in self.stores.items():
            lite = self.lite(level, data)
            self.assertEqual(list(lite.plots), list(loaded['plots']))
            for plot_id, entry in loaded['plots'].items():
                self.assertEqual(lite.evaluate(plot_id), di.registry_evaluate_store(codes, header, entry), (label, plot_id, level))
                self.assertEqual(lite.evaluate(plot_id, entry['geometry_sha256']), lite.evaluate(plot_id))
            count(f'registered plots {label}', len(loaded['plots']))

    @unittest.skipUnless((OUT / 'registry.bin').is_file(), 'private registry.bin not present')
    def test_the_17_registered_plots_at_both_levels(self):
        data = (OUT / 'registry.bin').read_bytes()
        registry = di.registry_from_bytes(data)
        self.assertEqual(len(registry['plots']), 17)
        for level, (codes, header) in self.stores.items():
            store = OUT / di.STORE_FILES[level]
            pinned = hashlib.sha256(store.read_bytes()).hexdigest()
            for lite in (L.load(store, OUT / 'registry.bin'), L.load(store, OUT / 'registry.bin', expected_sha256=pinned, level=level)):
                for plot_id, entry in registry['plots'].items():
                    self.assertEqual(lite.evaluate(plot_id), di.registry_evaluate_store(codes, header, entry))
                    count('registered plots real 17')

    def test_synthetic_polygons_500_and_5000(self):
        land = self.stores[S.SCREEN_VERSION][0] >= decision.LAND
        for n in (500, 5000):
            polygons, _ = bench.synthetic_polygons(n, 20261015 + n, self.header, land)
            self.compare(di.build_registry(polygons, self.header), f'synthetic {n}')

    def test_boundary_polygons(self):
        for n, seed in ((150, 20261015), (150, 7)):
            polygons, _ = bench.boundary_polygons(n, seed, self.header)
            self.compare(di.build_registry(polygons, self.header), 'boundary')

    def test_empty_out_of_chip_and_edge_selections(self):
        a, e, c, f = self.header['transform'][0], self.header['transform'][4], self.header['transform'][2], self.header['transform'][5]
        h, w = self.header['shape']

        def square(row, col, rows, cols):
            x0, x1, y1, y0 = c + col * a, c + (col + cols) * a, f + row * e, f + (row + rows) * e
            return {'type': 'Polygon', 'coordinates': [[[x0, y0], [x1, y0], [x1, y1], [x0, y1], [x0, y0]]]}
        plots = [{'plot_id': name, 'geometry': square(*box)} for name, box in
                 (('top-left', (-4, -4, 8, 8)), ('bottom-right', (h - 3, w - 3, 5, 5)), ('gone', (-80, 40, 3, 3)),
                  ('row', (100, 0, 1, w)), ('column', (0, 300, h, 1)), ('single', (200, 300, 1, 1)))]
        plots.append({'plot_id': 'sliver', 'geometry': {'type': 'Polygon', 'coordinates': [[
            [c + 300.2 * a, f + 300.2 * e], [c + 300.4 * a, f + 300.2 * e], [c + 300.4 * a, f + 300.4 * e], [c + 300.2 * a, f + 300.2 * e]]]}})
        self.compare(di.build_registry(plots, self.header), 'edges')


class StoreChecksTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.dir = Path(self.tmp.name)
        self.rng = np.random.default_rng(31)

    def rejected(self, blob, **kwargs):
        count('store corruptions')
        with self.assertRaises(ValueError):
            L.open_store(blob, **kwargs)

    def stores(self):
        """Small split stores in every event coding at both levels, plus a dense-event one."""
        for events, h, w in (('forest', 12, 21), ('anywhere', 12, 21), ('dense', 9, 11)):
            raster = structured(h=h, w=w, events=events)
            for level in S.LEVELS:
                codes = project(raster, level)
                for mode in modes_for(codes):
                    yield f'{events}-{level}-{mode}', *split_file(codes, level, mode), codes

    def test_every_bit_flip_truncation_and_extension_is_rejected(self):
        for label, blob, payload, codes in self.stores():
            with self.subTest(store=label):
                for position in range(len(blob)):
                    for bit in range(8):
                        data = bytearray(blob)
                        data[position] ^= 1 << bit
                        self.rejected(bytes(data))
                for n in range(len(blob)):
                    self.rejected(blob[:n])
                self.rejected(blob + b'\x00')
                self.rejected(blob + blob[-8:])

    def test_pinned_whole_file_digest(self):
        blob, _ = split_file(structured(h=12, w=21), S.SCREEN_VERSION)
        L.open_store(blob, expected_sha256=hashlib.sha256(blob).hexdigest())
        for bad in ('0' * 64, 'xyz', hashlib.sha256(blob).hexdigest().upper(), 5, 3.5):
            with self.subTest(bad=bad):
                self.rejected(blob, expected_sha256=bad)
        forged = replace_header(blob, transform=[0.00025, 0.0, 98.77235, 0.0, -0.00025, 8.582])
        self.assertEqual(L.open_store(forged).header['transform'][2], 98.77235)  # integrity, not authenticity
        self.rejected(forged, expected_sha256=hashlib.sha256(blob).hexdigest())

    def test_header_tampering_matches_read_store(self):
        blob, payload = split_file(structured(h=12, w=21), S.SCREEN_VERSION)
        _, _, length, _ = S.PREFIX.unpack_from(blob)
        raw = blob[S.PREFIX.size:S.PREFIX.size + length]
        rest = blob[S.PREFIX.size + length:]
        header = json.loads(raw)

        def framed(head):
            return S.PREFIX.pack(S.MAGIC, S.VERSION, len(head), zlib.crc32(head)) + head + rest
        bad = {
            'duplicate key': raw[:-1] + b',"crs":"EPSG:4326"}', 'not canonical': json.dumps(header, indent=1).encode(),
            'extra field': S._canonical({**header, 'extra': 1}), 'missing field': S._canonical({k: v for k, v in header.items() if k != 'crs'}),
            'unknown level': S._canonical({**header, 'level': 'eudr-screen.v2'}),
            'unknown encoding': S._canonical({**header, 'encoding': 'gzip'}),
            'short digest': S._canonical({**header, 'payload_sha256': header['payload_sha256'][:-1]}),
            'upper-case digest': S._canonical({**header, 'codes_sha256': header['codes_sha256'].upper()}),
            'bad source key': S._canonical({**header, 'sources': {'x': 'a' * 64}}),
            'oversized payload claim': S._canonical({**header, 'payload_bytes': S.MAX_PAYLOAD_BYTES + 1}),
            'bool payload size': S._canonical({**header, 'payload_bytes': True}),
            'wrong payload size': S._canonical({**header, 'payload_bytes': header['payload_bytes'] + 1}),
            'wrong payload hash': S._canonical({**header, 'payload_sha256': '0' * 64}),
            'nan': raw.replace(b'0.00025', b'NaN', 1), 'not json': b'{' * 200, 'deeply nested': b'[' * 20000 + b']' * 20000,
            'not an object': b'[]', 'bad transform': S._canonical({**header, 'transform': [1, 2, 3]}),
            'huge transform': S._canonical({**header, 'transform': [10 ** 400] + header['transform'][1:]}),
            'empty crs': S._canonical({**header, 'crs': ''}), 'invalid utf8': b'\xff\xfe' + raw}
        for label, head in bad.items():
            with self.subTest(label):
                self.rejected(framed(head))
        for claimed in (0, 1, S.MAX_HEADER_BYTES + 1, 2 ** 32 - 1):
            self.rejected(S.PREFIX.pack(S.MAGIC, S.VERSION, claimed, zlib.crc32(raw)) + raw + rest)
        h, w = 12, 21
        for shape in ([h + 1, w], [h, w - 1], [w, h], [1, 1], [h * w, 1], [0, w], [h, S.MAX_DIMENSION + 1], [h, 'x'], [h, w, 1], 'hw'):
            with self.subTest(shape=shape):
                self.rejected(replace_header(blob, shape=shape))
        for encoding in S.ENCODINGS[:-1]:  # a valid store of another encoding is not this path's to read
            codes = structured(h=12, w=21)
            data = S.encode_codes(codes, encoding)
            other = S._file_bytes(S._header(codes, metadata(12, 21), S.SCREEN_VERSION, encoding, data), data)
            with self.assertRaises(L.LiteUnsupported):
                L.open_store(other)
            self.assertTrue(issubclass(L.LiteUnsupported, ValueError))

    def test_a_wrong_raster_hash_is_the_one_check_not_made(self):
        """Documented gap: the header's codes_sha256 needs every cell decoded."""
        blob, _ = split_file(structured(h=12, w=21), S.SCREEN_VERSION)
        forged = replace_header(blob, codes_sha256='0' * 64)
        path = self.dir / 'forged.plds'
        path.write_bytes(forged)
        with self.assertRaisesRegex(ValueError, 'decoded raster differs'):
            S.read_store(path)
        self.assertEqual(L.open_store(forged).codes([[(0, 12 * 21)]])[0], structured(h=12, w=21).tobytes())
        with self.assertRaises(ValueError):  # the trusted whole-file digest closes it
            L.open_store(forged, expected_sha256=hashlib.sha256(blob).hexdigest())

    def test_file_path_checks(self):
        blob, _ = split_file(structured(h=12, w=21), S.SCREEN_VERSION)
        path = self.dir / 'store.plds'
        path.write_bytes(blob)
        self.assertEqual(L.read_store_lite(path).header['shape'], [12, 21])
        link = self.dir / 'link.plds'
        link.symlink_to(path)
        for bad in (link, self.dir / 'missing.plds', self.dir):
            with self.subTest(path=str(bad.name)), self.assertRaises(ValueError):
                L.read_store_lite(bad)

    def test_decision_level_rejects_nonforest_loss_like_read_store(self):
        base = structured(h=12, w=21, events='forest')
        for code in S.NO_DECISION_CODES:
            raster = base.copy()
            raster[(raster > 2) & (raster < 8)] = 2
            raster[4, 4] = code
            payload = S.encode_codes(raster, 'split')
            self.assertIn(payload[0], (0, 1))
            self.rejected(S._file_bytes(S._header(raster, metadata(12, 21), S.DECISION_VERSION, 'split', payload), payload))
            screen = S._file_bytes(S._header(raster, metadata(12, 21), S.SCREEN_VERSION, 'split', payload), payload)
            self.assertEqual(L.open_store(screen).codes([[(0, 12 * 21)]])[0], raster.tobytes())
            count('level rule cases')

    def test_crafted_inconsistent_planes_and_events(self):
        """Hand-made payloads that break one rule each; the reference decoder and lite must agree on every one."""
        raster = structured(h=12, w=21, events='forest')
        meta = metadata(12, 21)
        h, w = raster.shape
        parts = dict(S._split_parts(raster, 'gaps1'))
        bands = S._bands(w)
        one = S._pack_stream(np.packbits(np.ones(bands * h * 8, np.uint8)).tobytes())  # a plane with every bit set
        none_set = b'\x00'
        cases = {
            'unknown and water overlap': bytes([0]) + one + one + none_set + none_set + none_set,
            'forest on unknown': bytes([0]) + one + none_set + one + none_set + none_set,
            'forest and unknown-forest overlap': bytes([0]) + none_set + none_set + one + one + none_set,
            'padding bits set': bytes([0]) + none_set + one + none_set + none_set + none_set,
            'event on water': bytes([0]) + none_set + S._put_plane(np.ones((h, w), bool)) + none_set + none_set
            + S._put_plane(np.ones((h, w), bool)) + S._pack_stream(bytes(h * w)),
            'unknown flag': bytes([2]) + none_set * 5, 'trailing byte': bytes([1]) + none_set * 4 + S._varint(0) + b'\x00',
            'flag 3 events with no eligible cells': bytes([3]) + none_set * 4 + S._varint(1) + S._pack_stream(b'\x00', explicit=True)
            + S._pack_stream(b'\x00'),
            'flag 1 event past the grid': bytes([1]) + none_set * 4 + S._varint(1)
            + S._pack_stream(S._varint(10 ** 6), explicit=True) + S._pack_stream(b'\x00'),
            'flag 1 event on non-land': bytes([1]) + none_set * 4 + S._varint(1) + S._pack_stream(b'\x00', explicit=True)
            + S._pack_stream(b'\x00'),
            'bad year symbol': bytes([3]) + b''.join(parts[k] for k in ('unknown', 'water', 'forest', 'unknown_forest', 'events'))
            + S._pack_stream(bytes([9]) * 100, 0),
            'truncated': b''.join(blob for _, blob in S._split_parts(raster, 'gaps1'))[:-3],
            'event count exceeds grid': bytes([1]) + none_set * 4 + S._varint(12 * 21 + 1),
            'empty': b'', 'only a flag': bytes([3]),
        }
        for label, payload in cases.items():
            header = S._header(raster, meta, S.SCREEN_VERSION, 'split', payload)
            blob = S._file_bytes(header, payload)
            with self.subTest(label):
                try:
                    reference(payload, header)
                    ok = True
                except ValueError:
                    ok = False
                if ok:
                    L.open_store(blob)
                else:
                    self.rejected(blob)
                count('crafted payloads')

    def test_random_payload_mutations_agree_with_the_reference_decoder(self):
        accepted = rejected = 0
        for label, blob, payload, codes in self.stores():
            _, _, length, _ = S.PREFIX.unpack_from(blob)
            header = json.loads(blob[S.PREFIX.size:S.PREFIX.size + length])
            h, w = codes.shape
            for i in range(300):
                data = bytearray(payload)
                kind = i % 5
                if kind == 0:
                    data[int(self.rng.integers(len(data)))] ^= int(self.rng.integers(1, 256))
                elif kind == 1:
                    data = data[:int(self.rng.integers(0, len(data)))]
                elif kind == 2:
                    at = int(self.rng.integers(0, len(data) + 1))
                    data[at:at] = bytes(self.rng.integers(0, 256, int(self.rng.integers(1, 6)), dtype=np.uint8))
                elif kind == 3:
                    at = int(self.rng.integers(0, len(data)))
                    del data[at:at + int(self.rng.integers(1, 6))]
                else:
                    for _ in range(3):
                        data[int(self.rng.integers(len(data)))] = int(self.rng.integers(0, 256))
                data = bytes(data)
                if not data:
                    continue
                head = dict(header, payload_bytes=len(data), payload_sha256=hashlib.sha256(data).hexdigest())
                file = S._file_bytes(head, data)
                try:
                    want = reference(data, head)
                except ValueError:
                    want = None
                try:
                    store = L.open_store(file)
                except ValueError:
                    got = None
                else:
                    got = store.codes([[(0, h * w)]])[0]
                self.assertEqual(want is None, got is None, (label, i, kind))
                if want is not None:
                    self.assertEqual(got, want.tobytes(), (label, i, kind))
                    accepted += 1
                else:
                    rejected += 1
        count('payload mutations accepted by both', accepted)
        count('payload mutations rejected by both', rejected)
        self.assertGreater(rejected, 1000)

    def craft(self, rng, h, w):
        """A random split payload: usually consistent, sometimes breaking one rule (planes, padding, events, years)."""
        bands = S._bands(w)
        nbytes = bands * h
        state = rng.choice(5, (h, w), p=[.06, .08, .3, .4, .16])  # unknown, water, nonforest, forest, unknown-forest

        def packed(bits):
            return np.packbits(S._to_strip(bits.astype(np.uint8))).tobytes()
        raw = [bytearray(packed(state == k)) for k in (0, 1, 3, 4)]
        for plane in raw:
            if rng.random() < .12:  # break something: stray bits, possibly in the padding or on another plane's cells
                for _ in range(int(rng.integers(1, 4))):
                    plane[int(rng.integers(nbytes))] |= 1 << int(rng.integers(8))
        stream = lambda b: b'\x00' if not any(b) and rng.random() < .8 else S._pack_stream(bytes(b))
        out = [stream(plane) for plane in raw]
        f, uf = (int.from_bytes(plane, 'big') for plane in raw[2:])
        nonforest = int.from_bytes(packed(state == 2), 'big')
        land = np.unpackbits(np.frombuffer((f | uf | nonforest).to_bytes(nbytes, 'big'), np.uint8))  # strip positions of land
        flag = int(rng.choice([0, 1, 3]))
        wild = rng.random() < .15
        size = nbytes * 8
        if flag == 3:
            eligible = (f | uf).bit_count()
            pool = np.arange(eligible + (3 if wild else 0))
        elif flag == 1:
            pool = np.arange(size + (3 if wild else 0)) if wild else np.flatnonzero(land)
        else:
            pool = np.flatnonzero(land) if not wild else np.arange(size)
        picks = np.sort(rng.choice(pool, min(len(pool), int(rng.integers(0, 40))), replace=False)) if len(pool) else np.zeros(0, int)
        n = len(picks)
        if flag == 0:
            event = bytearray(nbytes)
            for p in picks:
                event[p >> 3] |= 0x80 >> (p & 7)
            out.append(stream(event))
            n = sum(bin(b).count('1') for b in event)
        else:
            gaps = np.diff(picks, prepend=-1) - 1
            if rng.random() < .05:
                n_claimed = n + int(rng.integers(1, 3))
            else:
                n_claimed = n
            raw_gaps = bytearray(S._varints(gaps))
            if n and rng.random() < .12:  # a byte-level defect in the gap stream: continuation bits, zero tails, long varints
                for _ in range(int(rng.integers(1, 3))):
                    raw_gaps[int(rng.integers(len(raw_gaps)))] = int(rng.choice([0, 1, 0x80, 0xFF, 0x81, 0x7F]))
                if rng.random() < .3:
                    raw_gaps += bytes([0xFF, 0xFF, 0xFF, 0xFF, 0x01][:int(rng.integers(2, 6))])
            out.append(S._varint(n_claimed) + (S._pack_stream(bytes(raw_gaps), explicit=True) if n else b''))
            n = n_claimed
        if n:
            years = rng.integers(0, 5 if rng.random() > .08 else 9, n).astype(np.uint8)
            delta = rng.random() < .5
            data = np.concatenate(([years[0]], np.diff(years.astype(np.int64)) % 5)).astype(np.uint8) if delta and years.max() < 5 else years
            out.append(S._pack_stream(data.tobytes(), int(delta)))
        if rng.random() < .03:
            out.append(b'\x00')
        return bytes([flag]) + b''.join(out)

    def test_semantic_fuzz_agrees_with_the_reference_decoder(self):
        """Structurally valid streams that break (or keep) the rules one at a time, all three event codings."""
        rng = np.random.default_rng(2026)
        both = {True: 0, False: 0}
        for i in range(4000):
            h, w = int(rng.integers(1, 15)), int(rng.integers(1, 42))
            level = S.LEVELS[i % 2]
            payload = self.craft(rng, h, w)
            header = S._header(np.zeros((h, w), np.uint8), metadata(h, w), level, 'split', payload)
            try:
                want = reference(payload, header)
            except ValueError:
                want = None
            try:
                got = L.open_store(S._file_bytes(header, payload)).codes([[(0, h * w)]])[0]
            except ValueError:
                got = None
            self.assertEqual(want is None, got is None, (i, h, w, level, payload.hex()))
            if want is not None:
                self.assertEqual(got, want.tobytes(), (i, h, w, level))
            both[want is not None] += 1
        count('semantic fuzz accepted by both', both[True])
        count('semantic fuzz rejected by both', both[False])
        self.assertGreater(both[True], 300)
        self.assertGreater(both[False], 300)

    def test_varint_gap_decoder_agrees_with_unvarints(self):
        rng = np.random.default_rng(77)
        pool = [0, 1, 2, 0x7F, 0x80, 0x81, 0xFF, 0xFE, 0x7E, 5]
        agreed = 0
        for _ in range(20000):
            raw = bytes(int(rng.choice(pool)) if rng.random() < .8 else int(rng.integers(256)) for _ in range(int(rng.integers(1, 12))))
            n = int(rng.integers(1, len(raw) + 1))
            try:
                want = S._unvarints(raw, n).tolist()
            except ValueError:
                want = None
            try:
                got = list(L._gaps(raw, n))
            except ValueError:
                got = None
            self.assertEqual(want, got, (raw, n))
            agreed += want is not None
        count('varint streams compared', 20000)
        self.assertGreater(agreed, 500)
        for raw, n in ((b'\x80\x00', 1), (b'\x80', 1), (b'\x01\x80', 2), (b'\xff\xff\xff\xff\x01', 1), (b'\x01\x02', 1)):
            with self.assertRaises(ValueError):
                L._gaps(raw, n)
        self.assertEqual(list(L._gaps(b'\xff\xff\xff\x7f\x80\x01', 2)), [2 ** 28 - 1, 128])

    def test_crafted_counts_are_bounded(self):
        shape = (1024, 1024)
        meta = metadata(*shape)
        codes = np.full(shape, 2, np.uint8)
        for n in (1_000_000, 1_048_576, 1_048_577, 10 ** 9, 2 ** 32 - 1):
            payload = crafted_split(n) if n <= 1_048_577 else bytes([1]) + b'\x00' * 4 + S._varint(n)  # no 4n-byte stream to build
            blob = S._file_bytes(S._header(codes, meta, S.SCREEN_VERSION, 'split', payload), payload)
            started = time.perf_counter()
            self.assertLess(peak_bytes(lambda: L.open_store(blob)), 8_000_000, n)
            self.assertLess(time.perf_counter() - started, 2.0)
            self.rejected(blob)
        n = 1_000_000  # within the declared limit: the declared events are all read, in memory linear in n, then refused (nonforest land with loss at the decision level)
        payload = bytes([1]) + b'\x00' * 4 + S._varint(n) + S._pack_stream(bytes(n), explicit=True) + S._pack_stream(bytes(n))
        blob = S._file_bytes(S._header(codes, meta, S.DECISION_VERSION, 'split', payload), payload)
        started = time.perf_counter()
        self.assertLess(peak_bytes(lambda: L.open_store(blob)), 30_000_000)
        self.assertLess(time.perf_counter() - started, 10.0)
        self.rejected(blob)
        # a legitimate gap stream of the maximum plausible length is read in bounded memory
        raster = structured(h=64, w=130, events='dense')
        blob, _ = split_file(raster, S.SCREEN_VERSION)
        self.assertLess(peak_bytes(lambda: L.open_store(blob).codes([[(0, 64 * 130)]])), 2_000_000)
        # a zstd bomb for a plane and a lying frame size
        bomb = bytes([0]) + bytes([S.ZSTD << 4]) + S._varint(40) + S._pack_stream(bytes(4_000_000))[2:]
        header = S._header(raster, metadata(64, 130), S.SCREEN_VERSION, 'split', bomb)
        self.assertLess(peak_bytes(lambda: L.open_store(S._file_bytes(header, bomb))), 4_000_000)
        self.rejected(S._file_bytes(header, bomb))

    def test_unsupported_and_level_and_grid_binding(self):
        raster = structured(h=12, w=21)
        blob, _ = split_file(raster, S.SCREEN_VERSION)
        store = L.open_store(blob)
        grid = di.grid_identity(metadata(12, 21))
        plot = dict(plot_record(1, 4, plot_id='X'), runs=[(5, 4)])
        lite = L.Lite(store, grid, [plot], S.SCREEN_VERSION)
        self.assertEqual(lite.evaluate('X')['contract'], S.SCREEN_VERSION)
        with self.assertRaises(ValueError):
            L.Lite(store, grid, [plot], S.DECISION_VERSION)
        for bad in (dict(grid, shape=[21, 12]), dict(grid, crs='EPSG:3857'), dict(grid, transform=[1.0] + grid['transform'][1:])):
            with self.subTest(grid=bad), self.assertRaises(ValueError):
                L.Lite(store, bad, [plot])
        with self.assertRaises(ValueError):
            lite.evaluate('X', '1' * 64)
        with self.assertRaises(KeyError):
            lite.evaluate('missing')


class RegistryChecksTest(unittest.TestCase):
    GRID = di.grid_identity(metadata(600, 1200))

    def accepts(self, data):
        try:
            return di.registry_from_bytes(data)
        except ValueError:
            return None

    def lite_runs(self, data):
        try:
            return L.parse_registry(data)
        except ValueError:
            return None

    def same(self, data, label):
        """Both parsers accept or both refuse; accepted runs expand to the same flat cell indices."""
        want, got = self.accepts(data), self.lite_runs(data)
        self.assertEqual(want is None, got is None, label)
        if want is not None:
            grid, plots = got
            self.assertEqual(grid, want['grid'])
            self.assertEqual([p['id'] for p in plots], list(want['plots']))
            for p in plots:
                flat = np.concatenate([np.arange(s, s + n) for s, n in p['runs']] or [np.zeros(0, np.int64)])
                np.testing.assert_array_equal(flat, want['plots'][p['id']]['flat_index'])
                self.assertEqual(p['selected_count'], want['plots'][p['id']]['selected_count'])
        count('registry parses compared')
        return got is not None

    def sample(self):
        plots = [plot_record(3, 3 + 4 + 7 + 2, 2, 'A'), plot_record(2, 3 + 4, 0, 'B'), plot_record(0, 3, 3, 'C'), plot_record(1, 8 + 1, 1, 'D')]
        return plots, [10, 50, 400, 1000, 1010, 70000], [3, 4, 7, 3, 4, 8]

    def test_real_registry_equals_the_numpy_parse(self):
        path = OUT / 'registry.bin'
        if not path.is_file():
            self.skipTest('private registry.bin not present')
        self.assertTrue(self.same(path.read_bytes(), 'real registry'))

    def test_valid_forged_registry_parses_identically(self):
        plots, starts, lengths = self.sample()
        data = forge_registry(plots, starts, lengths, self.GRID)
        self.assertTrue(self.same(data, 'sample'))
        grid, parsed = L.parse_registry(data)
        self.assertEqual(parsed[0]['runs'], [(10, 3), (50, 4), (400, 7)])
        self.assertEqual(parsed[2]['runs'], [])

    def test_every_bit_flip_and_truncation_is_rejected(self):
        data = forge_registry(*self.sample(), self.GRID)
        self.assertLess(len(data), 1500)
        for position in range(len(data)):
            for bit in range(8):
                flipped = bytearray(data)
                flipped[position] ^= 1 << bit
                count('registry corruptions')
                with self.assertRaises(ValueError):
                    L.parse_registry(bytes(flipped))
        for n in range(len(data)):
            count('registry corruptions')
            with self.assertRaises(ValueError):
                L.parse_registry(data[:n])
        with self.assertRaises(ValueError):
            L.parse_registry(data + b'\x00')

    def test_hostile_runs_headers_and_grids_agree_with_the_numpy_parser(self):
        grid = self.GRID
        cells = grid['shape'][0] * grid['shape'][1]
        hostile = {
            'run longer than the grid': ([plot_record(1, 2 ** 24)], [0], [2 ** 24]),
            'run past the last cell': ([plot_record(1, 10)], [cells - 5], [10]),
            'start before the grid': ([plot_record(1, 3)], [-1], [3]), 'zero-length run': ([plot_record(1, 0)], [5], [0]),
            'negative length': ([plot_record(1, 0)], [5], [-3]), 'overlapping runs': ([plot_record(2, 8)], [0, 3], [5, 3]),
            'unsorted runs': ([plot_record(2, 6)], [10, 0], [3, 3]), 'touching runs': ([plot_record(2, 6)], [0, 3], [3, 3]),
            'accounting mismatch': ([plot_record(1, 4)], [0], [3]), 'whole grid in one plot': ([plot_record(1, cells)], [0], [cells]),
            'int32 extremes': ([plot_record(1, 4)], [2 ** 31 - 1], [2 ** 31 - 1]), 'negative extremes': ([plot_record(1, 4)], [-2 ** 31], [-2 ** 31]),
            'last cell': ([plot_record(1, 1)], [cells - 1], [1]), 'runs claimed but payload short': ([plot_record(5, 5)], [0], [1]),
            'payload longer than claimed': ([plot_record(1, 1)], [0, 9], [1, 1]),
            'unclaimed bytes after the runs': ([plot_record(1, 1)], [0], [1, 5, 5]),
        }
        for label, (plots, starts, lengths) in hostile.items():
            with self.subTest(case=label):
                self.same(forge_registry(plots, starts, lengths, grid), label)
        big = dict(grid, shape=[4000, 4000])
        for label, plots, starts, lengths in (
                ('11M cells in one plot', [plot_record(1, 11_000_000)], [0], [11_000_000]),
                ('4 x 3M cells', [plot_record(1, 3_000_000, plot_id=f'P{i}') for i in range(4)], [0] * 4, [3_000_000] * 4)):
            data = forge_registry(plots, starts, lengths, big)
            self.assertFalse(self.same(data, label))
            self.assertLess(peak_bytes(lambda: L.parse_registry(data)), 1_000_000)
        header_defects = {
            'shape is text': dict(grid, shape='ab'), 'shape has a bool': dict(grid, shape=[True, 5]),
            'shape too big': dict(grid, shape=[2 ** 16, 2 ** 16]), 'zero shape': dict(grid, shape=[0, 5]),
            'empty transform': dict(grid, transform=[]), 'transform overflow': dict(grid, transform=[10 ** 400] + grid['transform'][1:]),
            'crs not text': dict(grid, crs=4326), 'extra grid key': dict(grid, extra=1), 'grid is a list': [1, 2]}
        for label, bad in header_defects.items():
            self.assertFalse(self.same(forge_registry([plot_record()], [0], [1], bad), label))
        for label, plots in {'runs is a float': [plot_record(1.5)], 'runs is a bool': [plot_record(True)], 'negative runs': [plot_record(-1)],
                             'duplicate ids': [plot_record(), plot_record()], 'bad digest': [dict(plot_record(), geometry_sha256='XY')],
                             'extra plot key': [dict(plot_record(), extra=1)], 'plot not an object': [5],
                             'id not text': [plot_record(plot_id=7)], 'negative outside count': [plot_record(1, 0, -1)]}.items():
            self.assertFalse(self.same(forge_registry(plots, [0, 10], [1, 1], grid), label))
        for label, extra in {'payload_bytes is text': {'payload_bytes': '8'}, 'bad payload digest': {'payload_sha256': 'x'},
                             'unknown key': {'extra': 1}, 'selection rule not text': {'selection_rule': 3},
                             'old schema': {'schema': 'plotline.decision-registry.v1'}}.items():
            self.assertFalse(self.same(forge_registry([plot_record()], [0], [1], grid, extra), label))
        for label, blob in (('list header', sealed_registry(b'[1,2]', b'')), ('nested', sealed_registry(b'[' * 20000 + b']' * 20000, b'')),
                            ('empty', b''), ('bad magic', b'x' * 100), ('invalid utf8', sealed_registry(b'\xff\xfe{}', b''))):
            self.assertFalse(self.same(blob, label))

    def test_random_run_tables_agree_with_the_numpy_parser(self):
        rng = np.random.default_rng(5)
        grid = self.GRID
        cells = grid['shape'][0] * grid['shape'][1]
        for i in range(400):
            plots, starts, lengths = [], [], []
            for p in range(int(rng.integers(0, 5))):
                runs, at = [], int(rng.integers(0, cells // 2))
                for _ in range(int(rng.integers(0, 6))):
                    n = int(rng.integers(-1, 2000))
                    gap = int(rng.integers(0, 50))
                    runs.append((at, n))
                    at += max(n, 0) + gap
                outside = int(rng.integers(0, 3))
                bad = int(rng.integers(0, 12)) == 0  # sometimes break the accounting
                plots.append(plot_record(len(runs), sum(max(n, 0) for _, n in runs) + outside + bad, outside, f'P{p}'))
                starts += [s for s, _ in runs]
                lengths += [n for _, n in runs]
            self.same(forge_registry(plots, starts, lengths, grid), f'random {i}')

    def test_resealed_mutations_agree_with_the_numpy_parser(self):
        plots, starts, lengths = self.sample()
        data = forge_registry(plots, starts, lengths, self.GRID)
        size = struct.unpack_from('<I', data, len(di.MAGIC))[0]
        header, payload = data[di.PREFIX_BYTES:di.PREFIX_BYTES + size], data[di.PREFIX_BYTES + size:]
        rng = np.random.default_rng(9)
        meta = json.loads(header)
        accepted = 0
        for i in range(1500):
            body, head = bytearray(payload), bytearray(header)
            target = body if i % 2 else head
            target[int(rng.integers(len(target)))] ^= int(rng.integers(1, 256))
            if i % 2:  # keep the payload hash honest so only the run rules object
                meta_i = dict(meta, payload_sha256=hashlib.sha256(bytes(body)).hexdigest())
                head = bytearray(di.canonical_bytes(meta_i))
            accepted += self.same(sealed_registry(bytes(head), bytes(body)), f'mutation {i}')
        count('registry resealed mutations', 1500)
        self.assertGreater(accepted, 0)


if __name__ == '__main__':
    unittest.main()
