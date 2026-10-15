"""Codec fidelity, format rejection and bounded decoding checks (unittest)."""
from compression import zstd
import copy
from functools import wraps
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import numpy as np

from engine import codecs

SCRATCH = Path(__file__).resolve().parents[2] / 'data/experimental/w1/test-runs'


def metadata(h, w):
    return {'shape': [h, w], 'transform': [0.25, 0, 98, 0, -0.25, 9],
            'crs': 'EPSG:4326', 'identity': {'note': 'raw masked values retained',
                                           'empty': None, 'items': [True, 3, 2.5]}}


def fixture(h=7, w=9, seed=13514):
    rng = np.random.default_rng(seed)
    bands = np.stack([rng.integers(0, maxval+1, (h, w), dtype=np.uint8)
                      for maxval in (100, 25, 2)])
    masks = rng.integers(0, 2, bands.shape, dtype=np.uint8).astype(bool)
    return bands, masks, metadata(h, w)


def all_candidates(test_method):
    """Run each shared malformed-store scenario against every declared codec."""
    @wraps(test_method)
    def wrapped(self):
        for candidate in codecs.CANDIDATES:
            self.candidate = candidate
            with self.subTest(candidate=candidate):
                test_method(self)
    return wrapped


class CodecTest(unittest.TestCase):
    def setUp(self):
        SCRATCH.mkdir(parents=True, exist_ok=True)
        self.temp = tempfile.TemporaryDirectory(dir=SCRATCH)
        self.root = Path(self.temp.name)
        self.candidate = 'packed14_zstd'
        self.addCleanup(self.temp.cleanup)

    def encode(self, candidate=None, h=7, w=9, size=4):
        candidate = self.candidate if candidate is None else candidate
        self.bands, self.masks, self.metadata = fixture(h, w)
        self.path = self.root / candidate
        report = codecs.encode_store(self.bands, self.masks, self.metadata,
                                     self.path, candidate, size)
        return report

    def index(self):
        return json.loads((self.path / 'index.json').read_bytes())

    def write_index(self, index):
        unsigned = {k: v for k, v in index.items() if k != 'index_sha256'}
        index['index_sha256'] = codecs._hash(codecs._canonical(unsigned))
        (self.path / 'index.json').write_bytes(codecs._canonical(index))

    def replace_stream(self, name, raw=None, compressed=None):
        """Rewrite checksums too, so deeper validation is exercised."""
        index = self.index()
        old_payload = (self.path / 'payload.bin').read_bytes()
        new_payload = bytearray(codecs.HEADER)
        for i, chunk in enumerate(index['chunks']):
            sizes = codecs._stream_sizes(index['candidate'], chunk['height'] * chunk['width'])
            for key in sizes:
                item = chunk['streams'][key]
                data = old_payload[item['offset']:item['offset']+item['size']]
                if i == 0 and key == name:
                    if raw is not None:
                        data = zstd.compress(raw, level=codecs.CANDIDATE_LEVELS[index['candidate']])
                        item['raw_sha256'] = codecs._hash(raw)
                    if compressed is not None:
                        data = compressed
                item['offset'], item['size'] = len(new_payload), len(data)
                item['sha256'] = codecs._hash(data)
                new_payload.extend(data)
        index['payload_bytes'] = len(new_payload)
        index['payload_sha256'] = codecs._hash(new_payload)
        (self.path / 'payload.bin').write_bytes(new_payload)
        self.write_index(index)

    def test_random_roundtrip_determinism_and_accounting(self):
        for candidate in codecs.CANDIDATES:
            with self.subTest(candidate=candidate):
                report = self.encode(candidate)
                decoded = codecs.decode_store(self.path)
                np.testing.assert_array_equal(decoded[0], self.bands)
                np.testing.assert_array_equal(decoded[1], self.masks)
                self.assertEqual(decoded[2], self.metadata)
                files = {p.name: p.read_bytes() for p in self.path.iterdir()}
                second = codecs.encode_store(self.bands, self.masks, self.metadata,
                                              self.path, candidate, 4)
                self.assertEqual(files, {p.name: p.read_bytes() for p in self.path.iterdir()})
                self.assertEqual(report['total_bytes'], sum(len(v) for v in files.values()))
                self.assertEqual(report['total_bytes'], report['payload_bytes'] + report['metadata_index_bytes'])
                self.assertEqual(report['files'], second['files'])
                self.assertNotIn('encode_ms', self.index())

    def test_candidate_specific_levels_and_mismatched_declarations(self):
        for candidate in codecs.CANDIDATES:
            self.encode(candidate)
            original = self.index()
            expected = codecs.CANDIDATE_LEVELS[candidate]
            self.assertEqual(original['compression']['level'], expected)
            # All other fixed levels and malformed numeric declarations fail,
            # even with a recomputed valid index checksum.
            for declared in (True, float(expected), None, -1, 0, 3, 9, 19, 22):
                if type(declared) is int and declared == expected:
                    continue
                with self.subTest(candidate=candidate, declared=declared):
                    index = copy.deepcopy(original)
                    index['compression']['level'] = declared
                    self.write_index(index)
                    with self.assertRaisesRegex(ValueError, 'compression settings'):
                        codecs.decode_store(self.path)
            for alias in codecs.CANDIDATES:
                if codecs.CANDIDATE_LEVELS[alias] == expected:
                    continue
                with self.subTest(candidate=candidate, relabeled=alias):
                    index = copy.deepcopy(original)
                    index['candidate'] = alias
                    self.write_index(index)
                    with self.assertRaisesRegex(ValueError, 'compression settings'):
                        codecs.decode_store(self.path)

    def test_frozen_cycle1_v1_byte_compatibility(self):
        # SHA256 captured from the original implementation before cycle2 edits,
        # in libzstd 1.5.7. Stores made before the change remain in W1 scratch.
        if zstd.zstd_version_info != (1, 5, 7):
            self.skipTest('frozen compressor bytes require recorded libzstd 1.5.7')
        golden = {
            'packed14_zstd': ('64515019440f352cf74f9e21f32abef8e6607f81dded059f72f2c006ca52ae02',
                              '9867196e6a9cb57484068526dd3f407547e15848d15513b4195f2608434756f0'),
            'uint16_zstd': ('64515019440f352cf74f9e21f32abef8e6607f81dded059f72f2c006ca52ae02',
                            'b4d1eff846c05bfc5fe2583a2e76fef0a50ed6bcf0ff9b1adc76195561318d67'),
            'separate_zstd': ('d77e243ab618c05c75ef969d23aa4b0f5efc0a8c5f8e29105aa108fcd9e0687e',
                              '6c6350812c0ea1d52a0172af7e5f5b6e2255c9a76217370d47dca4169c2d9dac'),
            'bitplane_zstd': ('64515019440f352cf74f9e21f32abef8e6607f81dded059f72f2c006ca52ae02',
                              '59201103250ccf5ef66aeb11dd85f9331edfc81bfe90368d8801e013e6c9a1bb')}
        bands = np.array([100, 25, 2], dtype=np.uint8).reshape(3, 1, 1)
        masks = np.zeros_like(bands, dtype=bool)
        md = {'shape': [1, 1], 'transform': [1, 0, 0, 0, -1, 1], 'crs': 'EPSG:4326'}
        for candidate, (payload_hash, index_hash) in golden.items():
            with self.subTest(candidate=candidate):
                path = self.root / candidate
                codecs.encode_store(bands, masks, md, path, candidate)
                self.assertEqual(codecs._hash((path / 'payload.bin').read_bytes()), payload_hash)
                self.assertEqual(codecs._hash((path / 'index.json').read_bytes()), index_hash)
                b, m, actual_md = codecs.decode_store(path)
                np.testing.assert_array_equal(b, bands)
                np.testing.assert_array_equal(m, masks)
                self.assertEqual(md, actual_md)

    def test_single_cells_uniform_extremes_and_noncontiguous_input(self):
        for candidate in codecs.CANDIDATES:
            for h, w in [(1, 1), (1, 9), (9, 1), (8, 10)]:
                with self.subTest(candidate=candidate, shape=(h, w)):
                    bands = np.zeros((3, h, w*2), dtype=np.uint8)[:, :, ::2]
                    bands[0], bands[1], bands[2] = 100, 25, 2
                    masks = np.zeros_like(bands, dtype=bool)
                    path = self.root / f'{candidate}-{h}-{w}'
                    codecs.encode_store(bands, masks, metadata(h, w), path, candidate, 4)
                    actual = codecs.decode_store(path)
                    np.testing.assert_array_equal(actual[0], bands)
                    np.testing.assert_array_equal(actual[1], masks)

    def test_all_value_combinations_including_masked_values(self):
        # Exhaustive legal triplets: 101 * 26 * 3 = 7878 independent words.
        tree, loss, dm = np.meshgrid(np.arange(101, dtype=np.uint8),
                                    np.arange(26, dtype=np.uint8),
                                    np.arange(3, dtype=np.uint8), indexing='ij')
        bands = np.stack([tree.ravel(), loss.ravel(), dm.ravel()]).reshape(3, 101, 78)
        masks = np.zeros_like(bands, dtype=bool)
        for candidate in codecs.CANDIDATES:
            path = self.root / candidate
            codecs.encode_store(bands, masks, metadata(101, 78), path, candidate, 32)
            result = codecs.decode_store(path)
            np.testing.assert_array_equal(result[0], bands)
            np.testing.assert_array_equal(result[1], masks)

    def test_all_real_pixels_all_candidates(self):
        from engine.source import load_source
        source = load_source()
        for candidate in codecs.CANDIDATES:
            with self.subTest(candidate=candidate):
                path = self.root / candidate
                codecs.encode_store(source.bands, source.masks, source.metadata, path, candidate)
                bands, masks, md = codecs.decode_store(path)
                np.testing.assert_array_equal(bands, source.bands)
                np.testing.assert_array_equal(masks, source.masks)
                self.assertEqual(md, source.metadata)

    def test_all_real_plot_window_query_equivalence(self):
        from engine.model import Dataset
        from engine.query import evaluate, select_cells
        from engine.source import load_plots, load_source
        source = load_source()
        plots = load_plots()
        self.assertEqual(len(plots), 17)
        for candidate in codecs.CANDIDATES:
            path = self.root / candidate
            codecs.encode_store(source.bands, source.masks, source.metadata, path, candidate)
            for plot in plots:
                with self.subTest(candidate=candidate, plot=plot['plot_id']):
                    rows, cols = select_cells(source.metadata, plot['geometry'])
                    self.assertGreater(len(rows), 0)
                    window = tuple(map(int, (rows.min(), rows.max()+1, cols.min(), cols.max()+1)))
                    bands, masks, md = codecs.read_window(path, *window)
                    self.assertEqual(evaluate(Dataset(bands, masks, md), plot['geometry']),
                                     evaluate(source, plot['geometry']))

    @all_candidates
    def test_invalid_inputs_create_no_store(self):
        bands, masks, md = fixture()
        bad = []
        for i, invalid in enumerate((101, 26, 3)):
            values = bands.copy()
            values[i, 0, 0] = invalid
            bad.append((values, np.zeros_like(masks), md, 4))
        bad.extend([(bands.astype(float), masks, md, 4),
                    (bands.astype(np.int16)-100, masks, md, 4),
                    (bands[:2], masks[:2], md, 4),
                    (bands, masks.astype(np.uint8), md, 4),
                    (bands, masks[:, :1], md, 4),
                    (bands, masks, {**md, 'shape': [0, 9]}, 4),
                    (bands, masks, {**md, 'shape': [True, 9]}, 4),
                    (bands, masks, {**md, 'shape': [16384, 16384]}, 4),
                    (bands, masks, {**md, 'shape': (7, 9)}, 4),
                    (bands, masks, {**md, 'transform': [0]*6}, 4),
                    (bands, masks, {**md, 'transform': [10**1000, 0, 98, 0, -1, 9]}, 4),
                    (bands, masks, {**md, 'other': float('nan')}, 4),
                    (bands, masks, {**md, 'other': {1: 'wrong key'}}, 4),
                    (bands, masks, md, 0), (bands, masks, md, True),
                    (bands, masks, md, 1025)])
        for i, (b, m, data, size) in enumerate(bad):
            with self.subTest(case=i):
                path = self.root / f'{self.candidate}-bad-{i}'
                with self.assertRaises(ValueError):
                    codecs.encode_store(b, m, data, path, self.candidate, size)
                self.assertFalse(path.exists())
        with self.assertRaises(ValueError):
            codecs.encode_store(bands, masks, md, self.root / 'bad-name', 'unknown')

    def test_window_pixels_and_transform(self):
        for candidate in codecs.CANDIDATES:
            self.encode(candidate, 11, 13)
            for rs, re, cs, ce in [(0, 11, 0, 13), (1, 2, 1, 2), (3, 10, 3, 11), (8, 11, 12, 13)]:
                with self.subTest(candidate=candidate, window=(rs, re, cs, ce)):
                    bands, masks, md = codecs.read_window(self.path, rs, re, cs, ce)
                    np.testing.assert_array_equal(bands, self.bands[:, rs:re, cs:ce])
                    np.testing.assert_array_equal(masks, self.masks[:, rs:re, cs:ce])
                    self.assertEqual(md['shape'], [re-rs, ce-cs])
                    self.assertEqual(md['transform'], [0.25, 0, 98+cs*.25, 0, -.25, 9-rs*.25])
                    self.assertEqual(self.index()['metadata'], self.metadata)

    @all_candidates
    def test_rotated_affine_window_and_invalid_windows(self):
        self.encode()
        self.metadata['transform'] = [0.25, 0.125, 98, 0.125, -0.25, 9]
        codecs.encode_store(self.bands, self.masks, self.metadata, self.path, self.candidate, 4)
        _, _, md = codecs.read_window(self.path, 3, 7, 2, 9)
        self.assertEqual(md['transform'], [.25, .125, 98.875, .125, -.25, 8.5])
        for window in [(-1, 2, 0, 1), (0, 8, 0, 1), (0, 1, 0, 10),
                       (1, 1, 0, 1), (2, 1, 0, 1), (False, 1, 0, 1), (0., 1, 0, 1)]:
            with self.subTest(window=window), self.assertRaises(ValueError):
                codecs.read_window(self.path, *window)

    @all_candidates
    def test_window_only_decompresses_intersecting_chunks(self):
        self.encode(h=9, w=9)
        original = codecs._decompress
        with patch.object(codecs, '_decompress', wraps=original) as wrapped:
            codecs.read_window(self.path, 0, 1, 0, 1)
            self.assertEqual(wrapped.call_count, len(codecs._stream_sizes(self.candidate, 16)))
        # An unselected chunk corruption is deliberately outside window integrity.
        index = self.index()
        name = next(iter(codecs._stream_sizes(self.candidate, 1)))
        item = index['chunks'][-1]['streams'][name]
        payload = bytearray((self.path / 'payload.bin').read_bytes())
        payload[item['offset']] ^= 1
        (self.path / 'payload.bin').write_bytes(payload)
        codecs.read_window(self.path, 0, 1, 0, 1)
        with self.assertRaises(ValueError):
            codecs.decode_store(self.path)

    @all_candidates
    def test_magic_version_truncation_trailing_and_checksums(self):
        for case in ('magic', 'version', 'truncate', 'append', 'corrupt', 'index', 'raw-hash', 'payload-hash'):
            with self.subTest(case=case):
                self.encode()
                payload_path = self.path / 'payload.bin'
                data = bytearray(payload_path.read_bytes())
                index = self.index()
                if case == 'magic': data[0] ^= 1
                if case == 'version': data[8] = 2
                if case == 'truncate': data = data[:-1]
                if case == 'append': data += b'X'
                if case == 'corrupt': data[len(codecs.HEADER)+5] ^= 1
                payload_path.write_bytes(data)
                if case == 'index':
                    (self.path / 'index.json').write_bytes(b'{}')
                elif case == 'raw-hash':
                    name = next(iter(codecs._stream_sizes(self.candidate, 16)))
                    index['chunks'][0]['streams'][name]['raw_sha256'] = '0'*64
                    self.write_index(index)
                elif case == 'payload-hash':
                    index['payload_sha256'] = '0'*64
                    self.write_index(index)
                with self.assertRaises(ValueError):
                    codecs.decode_store(self.path)

    @all_candidates
    def test_illegal_index_rejected_before_allocation(self):
        self.encode()
        original = self.index()
        name = next(iter(codecs._stream_sizes(self.candidate, 16)))
        mutations = [lambda x: x.update(version=2), lambda x: x.update(version=True),
                     lambda x: x.update(candidate='unknown'), lambda x: x.update(chunk_size=0),
                     lambda x: x.update(chunk_size=True), lambda x: x.update(shape=[99, 9]),
                     lambda x: x['metadata'].update(shape=[16385, 9]),
                     lambda x: x['metadata'].update(shape=[16384, 16384]),
                     lambda x: x['chunks'].pop(), lambda x: x['chunks'][0].update(index=1),
                     lambda x: x['chunks'][0].update(row=-1),
                     lambda x: x['chunks'][0].update(col=True),
                     lambda x: x['chunks'][0].update(height=1024),
                     lambda x: x['chunks'][0]['streams'][name].update(offset=0),
                     lambda x: x['chunks'][0]['streams'][name].update(size=-1),
                     lambda x: x['chunks'][0]['streams'][name].update(size=10**12),
                     lambda x: x['chunks'][0]['streams'][name].update(raw_size=10**12),
                     lambda x: x['chunks'][1]['streams'][name].update(offset=12),
                     lambda x: x['chunks'][0]['streams'].update(unexpected={}),
                     lambda x: x.update(payload_bytes=10**12),
                     lambda x: x['chunks'][0]['streams'][name].update(sha256='../payload.bin')]
        for i, mutate in enumerate(mutations):
            with self.subTest(case=i):
                index = copy.deepcopy(original)
                mutate(index)
                self.write_index(index)
                with patch.object(codecs.np, 'empty', side_effect=AssertionError('allocated before validation')):
                    with self.assertRaises(ValueError):
                        codecs.decode_store(self.path)
        self.write_index(original)
        with patch.object(codecs, 'MAX_CHUNKS', 1), self.assertRaises(ValueError):
            codecs.decode_store(self.path)

    @all_candidates
    def test_bad_json_and_bounded_index(self):
        self.encode()
        for raw in [b'[]', b'{', b'{"x":1,"x":2}', b'{"x":NaN}', b'\xff',
                    b'['*1500 + b']'*1500, b'{} trailing']:
            (self.path / 'index.json').write_bytes(raw)
            with self.subTest(raw=raw[:30]), self.assertRaises(ValueError):
                codecs.decode_store(self.path)
        (self.path / 'index.json').write_bytes(b' '*101)
        with patch.object(codecs, 'MAX_INDEX_BYTES', 100), self.assertRaises(ValueError):
            codecs.decode_store(self.path)

    def test_packed_padding_reserved_bits_and_illegal_raw_values(self):
        for candidate, name, raw in [
            ('packed14_zstd', 'values', b'\x01\x80'),
            ('bitplane_zstd', 'values', b'\x01\x80'),
            ('uint16_zstd', 'values', b'\x01\x40'),
            ('packed14_zstd', 'masks', b'\x80'),
            ('packed14_zstd', 'values', b'\x7f\x00'),
            ('packed14_zstd', 'values', b'\x00\x0f'),
            ('packed14_zstd', 'values', b'\x00\x30'),
            *[(candidate, name, raw) for candidate in codecs.SEPARATE_CANDIDATES
              for name, raw in [('treecover2000', b'\x65'), ('lossyear', b'\x1a'),
                                ('datamask', b'\x03'), ('masks', b'\x80')]]]:
            with self.subTest(candidate=candidate, stream=name, raw=raw):
                self.encode(candidate, h=1, w=1)
                self.replace_stream(name, raw=raw)
                with self.assertRaises(ValueError):
                    codecs.decode_store(self.path)

    @all_candidates
    def test_decompression_bounds_and_trailing_frames(self):
        self.encode(h=1, w=1)
        original = self.index()
        name = next(iter(codecs._stream_sizes(self.candidate, 1)))
        item = original['chunks'][0]['streams'][name]
        data = (self.path / 'payload.bin').read_bytes()[item['offset']:item['offset']+item['size']]
        for malicious in (data+b'X', data+data, data[:-1], zstd.compress(b'X'*100000),
                          zstd.compress(b'\0\0', options={zstd.CompressionParameter.content_size_flag: 0})):
            with self.subTest(length=len(malicious)):
                self.encode(h=1, w=1)
                self.replace_stream(name, compressed=malicious)
                with self.assertRaises(ValueError):
                    codecs.decode_store(self.path)
        # Exercise output limit even if a frame's advertised size is forged.
        info = type('FrameInfo', (), {'decompressed_size': 2, 'dictionary_id': 0})()
        with patch.object(codecs.zstd, 'get_frame_info', return_value=info):
            with self.assertRaises(ValueError):
                codecs._decompress(zstd.compress(b'X'*100000), 2)

    def test_actual_frame_advertised_window_bound(self):
        raw = b'A'*300
        frame = zstd.compress(raw)
        self.assertTrue(frame[4] & 0x20)  # single segment
        self.assertEqual(frame[4] >> 6, 1)  # two-byte content size retained
        # RFC 8878: remove single-segment flag and insert window descriptor.
        # 0 -> 1KiB, 0xa0 -> 1GiB. Both retain the actual 300-byte contents.
        small = frame[:4]+bytes([frame[4] & ~0x20, 0])+frame[5:]
        large = frame[:4]+bytes([frame[4] & ~0x20, 0xa0])+frame[5:]
        self.assertEqual(codecs._decompress(small, len(raw)), raw)
        with self.assertRaisesRegex(ValueError, 'advertised window'):
            codecs._decompress(large, len(raw))

    def test_seeded_random_chunk_boundaries(self):
        for seed in range(13514, 13524):
            h, w, size = seed % 19 + 1, seed % 23 + 1, (1, 3, 7, 8, 17)[seed % 5]
            bands, masks, md = fixture(h, w, seed)
            for candidate in codecs.CANDIDATES:
                with self.subTest(seed=seed, candidate=candidate, size=size):
                    path = self.root / f'{candidate}-{seed}'
                    codecs.encode_store(bands, masks, md, path, candidate, size)
                    b, m, actual_md = codecs.decode_store(path)
                    np.testing.assert_array_equal(b, bands)
                    np.testing.assert_array_equal(m, masks)
                    self.assertEqual(actual_md, md)

    @all_candidates
    def test_refuses_unrelated_files_and_symlinks(self):
        self.encode()
        unrelated = self.path / 'keep.txt'
        unrelated.write_text('retain')
        with self.assertRaises(ValueError):
            codecs.encode_store(self.bands, self.masks, self.metadata, self.path, self.candidate)
        self.assertEqual(unrelated.read_text(), 'retain')
        unrelated.unlink()
        link = self.root / f'linked-store-{self.candidate}'
        link.symlink_to(self.path, target_is_directory=True)
        with self.assertRaises(ValueError): codecs.decode_store(link)
        payload = self.path / 'payload.bin'
        target = self.root / f'payload-original-{self.candidate}.bin'
        payload.rename(target)
        payload.symlink_to(target)
        with self.assertRaises(ValueError): codecs.decode_store(self.path)


if __name__ == '__main__':
    unittest.main()
