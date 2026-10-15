"""Decision store round trips, negative controls, bounded decoding and cold-path imports (unittest)."""
from compression import zstd
import hashlib
import json
from pathlib import Path
import subprocess
import struct
import sys
import tempfile
import time
import tracemalloc
import unittest
from unittest import mock
import zlib

import numpy as np

from engine import decision_store as S

ROOT = Path(__file__).resolve().parents[2]
BANDS = ('treecover2000', 'lossyear', 'datamask')


def metadata(h, w):
    return {'shape': [h, w], 'transform': [0.00025, 0.0, 98.77225, 0.0, -0.00025, 8.582], 'crs': 'EPSG:4326',
            'sources': [{'band': b, 'sha256': hashlib.sha256(b.encode()).hexdigest()} for b in BANDS],
            'jrc_chip_sha256': hashlib.sha256(b'jrc').hexdigest()}


def structured(h=40, w=53, seed=7, events='forest'):
    """Blobby forest/water/unknown regions with sparse or dense post-2020 loss events."""
    rng = np.random.default_rng(seed)
    yy, xx = np.mgrid[0:h, 0:w]
    state = np.where(((yy - h / 2) ** 2 + (xx - w / 3) ** 2) < (h / 3) ** 2, 1, 0)
    state[:3] = 2
    codes = (2 + 6 * state).astype(np.uint8)
    codes[(yy > h - 6) & (xx < 9)] = 1
    codes[(yy == h - 1) & (xx > w - 5)] = 0
    land = codes >= 2
    pick = rng.random((h, w))
    if events == 'forest':
        mask = land & (state >= 1) & (pick < 0.08)
    elif events == 'anywhere':
        mask = land & (pick < 0.06)
    else:
        mask = land & (pick < 0.7)
    codes[mask] += rng.integers(1, 6, int(mask.sum())).astype(np.uint8)
    return codes


def edge_rasters():
    rng = np.random.default_rng(11)
    cases = {'all-unknown': np.zeros((5, 9), np.uint8), 'every-code': np.arange(20, dtype=np.uint8).reshape(4, 5),
             'tiled-every-code': np.tile(np.arange(20, dtype=np.uint8), (9, 7)), 'row-1xN': rng.integers(0, 20, (1, 37), dtype=np.uint8),
             'column-Nx1': rng.integers(0, 20, (37, 1), dtype=np.uint8),
             'random-dense': rng.integers(0, 20, (33, 41), dtype=np.uint8),
             'structured-forest-events': structured(), 'structured-any-events': structured(events='anywhere'),
             'structured-dense-events': structured(events='dense')}
    for code in (0, 1, 2, 8, 13, 14, 19):
        cases[f'single-cell-{code}'] = np.array([[code]], np.uint8)
        cases[f'all-code-{code}'] = np.full((6, 11), code, np.uint8)
    for h, w in ((1, 8), (1, 9), (7, 7), (8, 8), (9, 16), (16, 17), (2, 3)):
        cases[f'random-{h}x{w}'] = rng.integers(0, 20, (h, w), dtype=np.uint8)
    return cases


def replace_header(blob, **changes):
    """Rebuild a store file with edited header fields and a canonical header."""
    _, _, length, _ = S.PREFIX.unpack_from(blob)
    header = json.loads(blob[S.PREFIX.size:S.PREFIX.size + length])
    header.update(changes)
    return S._file_bytes(header, blob[S.PREFIX.size + length:])  # recomputes the CRC: only the header checks can object


def crafted_split(n):
    """The validator's split blob: four empty planes, then n declared events in a stream of 4n zero bytes."""
    raw = bytes(4 * n)
    frame = zstd.compress(raw, level=3)
    return bytes([1]) + b'\x00' * 4 + S._varint(n) + bytes([S.ZSTD << 4]) + S._varint(len(raw)) + S._varint(len(frame)) + frame


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


class RoundTripTest(unittest.TestCase):
    def test_encodings_cover_the_required_candidates(self):
        self.assertTrue({'zstd19', 'zstd22', 'xz', 'split'} <= set(S.ENCODINGS))
        self.assertEqual(len(set(S.ENCODINGS)), len(S.ENCODINGS))

    def test_every_encoding_round_trips_edge_rasters(self):
        for name, codes in edge_rasters().items():
            for encoding in S.ENCODINGS:
                with self.subTest(raster=name, encoding=encoding):
                    back = S.decode_codes(S.encode_codes(codes, encoding), codes.shape, encoding)
                    self.assertEqual(back.dtype, np.uint8)
                    np.testing.assert_array_equal(back, codes)
                    self.assertTrue(back.flags.writeable and back.flags.c_contiguous)

    def test_split_event_codings_all_round_trip(self):
        for events in ('forest', 'anywhere', 'dense'):
            codes = structured(events=events)
            land_state = (codes.astype(int) - 2) // 6
            for mode in ('plane', 'gaps0', 'gaps1'):
                with self.subTest(events=events, mode=mode):
                    try:
                        parts = S._split_parts(codes, mode)
                    except KeyError:
                        self.assertEqual(mode, 'gaps1')  # nonforest events cannot use forest-eligible ranks
                        self.assertTrue((codes[(codes > 2) & (land_state == 0) & (codes < 8)]).size)
                        continue
                    blob = b''.join(part for _, part in parts)
                    np.testing.assert_array_equal(S.decode_codes(blob, codes.shape, 'split'), codes)

    def test_split_picks_the_eligible_rank_coding_for_forest_only_loss(self):
        blob = S.encode_codes(structured(events='forest'), 'split')
        self.assertEqual(blob[0], 3)
        self.assertIn(S.encode_codes(structured(events='anywhere'), 'split')[0], (0, 1))

    def test_encoders_reject_invalid_input(self):
        good = np.zeros((3, 3), np.uint8)
        for bad in (good.astype(np.int16), good[0], np.zeros((2, 2, 2), np.uint8), np.full((2, 2), 20, np.uint8),
                    np.zeros((0, 4), np.uint8), 'codes'):
            with self.subTest(bad=type(bad).__name__ + str(getattr(bad, 'shape', ''))):
                with self.assertRaises(ValueError):
                    S.encode_codes(bad, 'zstd19')
        with self.assertRaises(ValueError):
            S.encode_codes(good, 'gzip')
        with self.assertRaises(ValueError):
            S.decode_codes(b'', (3, 3), 'gzip')

    def test_varints_round_trip_and_reject_noncanonical(self):
        values = np.array([0, 1, 127, 128, 16383, 16384, 2 ** 21 - 1, 2 ** 21, 2 ** 28 - 1], np.int64)
        raw = S._varints(values)
        self.assertEqual(raw, b''.join(S._varint(int(v)) for v in values))
        np.testing.assert_array_equal(S._unvarints(raw, len(values)), values)
        for bad, count in ((b'\x80\x00', 1), (b'\x80', 1), (b'\x01\x02', 1), (b'\xff\xff\xff\xff\x01', 1)):
            with self.subTest(bad=bad), self.assertRaises(ValueError):
                S._unvarints(bad, count)
        with self.assertRaises(ValueError):
            S._varints([2 ** 28])

    def test_varint_limit_covers_every_stream_the_encoder_can_make(self):
        total = 10_000_000  # gaps (and run lengths minus 1) plus one sum to at most the cell count
        cases = ([0] * 40, [total - 1], [127, 128, 16383, 16384, 2 ** 21, 2 ** 21 - 1] * 2, [0, 2 ** 21 + 5, 3],
                 [128] * (total // 129), [16384] * (total // 16385), [2 ** 21] * (total // (2 ** 21 + 1)), [127] * (total // 128))
        for gaps in cases:
            values = np.array(gaps, np.int64)
            self.assertLessEqual(int((values + 1).sum()), total)
            self.assertLessEqual(len(S._varints(values)), S._varint_limit(len(values), total), gaps[:3])


class BoundedDecodeTest(unittest.TestCase):
    def test_crafted_varint_streams_are_refused_before_large_allocations(self):
        shape, blob = (1024, 1024), crafted_split(1_000_000)  # n events declared, 4n zero bytes behind them
        self.assertLess(len(blob), 300)
        started = time.perf_counter()
        # the output raster is 1 MB and the plane checks hold a few temporaries (3 MB measured); the old decoder
        # peaked at 43 MB here because it built an int64 index per stream byte
        self.assertLess(peak_bytes(lambda: S.decode_codes(blob, shape, 'split')), 8_000_000)
        self.assertLess(time.perf_counter() - started, 2.0)
        with self.assertRaisesRegex(ValueError, 'out of bounds'):
            S.decode_codes(blob, shape, 'split')

    def test_unvarints_counts_terminators_before_allocating_index_arrays(self):
        zeros = bytes(8_000_000)  # 8M one-byte values where 2M were declared
        self.assertLess(peak_bytes(lambda: S._unvarints(zeros, 2_000_000)), 16_000_000)  # was ~72 MB: int64 index per terminator
        with self.assertRaises(ValueError):
            S._unvarints(zeros, 2_000_000)
        with self.assertRaises(ValueError):
            S._unvarints(b'\x80' * 100, 100)  # no terminator at all
        np.testing.assert_array_equal(S._unvarints(bytes(range(100)), 100), np.arange(100))  # all one-byte fast path

    def test_event_and_run_counts_are_bounded_by_the_grid(self):
        for encoding_blob in (bytes([1]) + b'\x00' * 4 + S._varint(4096 * 4096 + 1), bytes([3]) + b'\x00' * 4 + S._varint(10 ** 9)):
            with self.assertRaises(ValueError):
                S.decode_codes(encoding_blob, (4096, 4096), 'split')
        with self.assertRaises(ValueError):
            S.decode_codes(S._varint(10 ** 9) + b'\x00', (4096, 4096), 'rle')

    def test_wrong_shape_is_rejected_for_every_encoding(self):
        codes = structured()
        for encoding in S.ENCODINGS:
            blob = S.encode_codes(codes, encoding)
            for shape in ((codes.shape[0] + 1, codes.shape[1]), (codes.shape[0], codes.shape[1] - 1), (1, 1)):
                with self.subTest(encoding=encoding, shape=shape), self.assertRaises(ValueError):
                    S.decode_codes(blob, shape, encoding)

    def test_shape_bounds(self):
        for shape in ((0, 3), (3, 0), (-1, 3), (S.MAX_DIMENSION + 1, 1), (S.MAX_DIMENSION, S.MAX_DIMENSION), (3,), (3.0, 3)):
            with self.subTest(shape=shape), self.assertRaises(ValueError):
                S.decode_codes(b'\x00', shape, 'zstd19')

    def test_decompression_bombs_are_not_inflated(self):
        bomb = zstd.compress(bytes(4_000_000))
        with self.assertRaises(ValueError):
            S.decode_codes(bomb, (10, 10), 'zstd19')
        with self.assertRaises(ValueError):
            S._unlz(S._lz(bytes(2_000_000), 0), 100, 0)
        with self.assertRaises(ValueError):
            S._unxz(S._xz(bytes(2_000_000)), 100)
        with self.assertRaises(ValueError):
            S._unzstd(zstd.compress(bytes(100)) + b'x', 100)

    def test_single_byte_mutations_and_truncations_never_escape_value_error(self):
        rng = np.random.default_rng(3)
        for events in ('forest', 'anywhere'):
            codes = structured(h=12, w=21, events=events)
            for encoding in S.ENCODINGS:
                blob = S.encode_codes(codes, encoding)
                variants = [blob[:n] for n in range(0, len(blob), max(1, len(blob) // 40))]
                for _ in range(150):
                    data = bytearray(blob)
                    data[int(rng.integers(len(data)))] ^= int(rng.integers(1, 256))
                    variants.append(bytes(data))
                for data in variants:
                    try:
                        back = S.decode_codes(data, codes.shape, encoding)
                    except ValueError:
                        continue
                    self.assertEqual(back.shape, codes.shape)
                    self.assertLess(int(back.max()), S.CODE_COUNT)


class StoreFileTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.dir = Path(self.temp.name)
        self.codes = structured(h=18, w=26)  # h != w so a shape swap keeps the cell count
        self.meta = metadata(*self.codes.shape)

    def write(self, encoding='split', level=S.SCREEN_VERSION, name='store.plds', codes=None):
        path = self.dir / name
        manifest = S.write_store(self.codes if codes is None else codes, self.meta, path,
                                 level=level, encoding=encoding)
        return path, manifest

    def check_rejected(self, blob, name='bad.plds', **kwargs):
        path = self.dir / name
        path.write_bytes(blob)
        with self.assertRaises(ValueError):
            S.read_store(path, **kwargs)

    def test_write_and_read_round_trip_with_manifest(self):
        for level in S.LEVELS:
            codes = self.codes.copy()
            if level == S.DECISION_VERSION:
                codes[(codes > 2) & (codes < 8)] = 2
            for encoding in S.ENCODINGS:
                with self.subTest(level=level, encoding=encoding):
                    path, manifest = self.write(encoding, level, f'{level}-{encoding}.plds', codes)
                    blob = path.read_bytes()
                    self.assertEqual(manifest['file_bytes'], len(blob))
                    self.assertEqual(manifest['file_sha256'], hashlib.sha256(blob).hexdigest())
                    self.assertEqual(manifest['header_bytes'] + manifest['payload_bytes'] + S.PREFIX.size, len(blob))
                    self.assertEqual(blob[:8], b'PLDECID1')
                    magic, version, length, crc = S.PREFIX.unpack_from(blob)
                    self.assertEqual((version, S.VERSION, S.PREFIX.size), (2, 2, 20))
                    self.assertEqual(crc, zlib.crc32(blob[S.PREFIX.size:S.PREFIX.size + length]))
                    back, header = S.read_store(path, expected_sha256=manifest['file_sha256'])
                    np.testing.assert_array_equal(back, codes)
                    self.assertEqual((header['level'], header['encoding'], header['shape']),
                                     (level, encoding, list(codes.shape)))
                    self.assertEqual(header['transform'], self.meta['transform'])
                    self.assertEqual(header['sources']['jrc_chip'], self.meta['jrc_chip_sha256'])
                    self.assertEqual(header['sources']['hansen_lossyear'], self.meta['sources'][1]['sha256'])
                    self.assertEqual({k: manifest[k] for k in header}, header)
        self.assertEqual([p.name for p in self.dir.iterdir() if p.name.startswith('.')], [])

    def test_identical_inputs_write_identical_bytes(self):
        first, _ = self.write(name='a.plds')
        second, _ = self.write(name='b.plds')
        self.assertEqual(first.read_bytes(), second.read_bytes())

    def test_write_rejects_inconsistent_inputs(self):
        decision_with_loss = self.codes.copy()
        decision_with_loss[5, 5] = 3
        wrong_shape = {**self.meta, 'shape': [9, 9]}
        no_sources = {k: v for k, v in self.meta.items() if k != 'sources'}
        bad_transform = {**self.meta, 'transform': [1, 2, 3]}
        for label, call in (
                ('decision level with code 3', lambda: S.write_store(decision_with_loss, self.meta, self.dir / 'x', level=S.DECISION_VERSION, encoding='split')),
                ('unknown level', lambda: S.write_store(self.codes, self.meta, self.dir / 'x', level='eudr-screen.v2', encoding='split')),
                ('unknown encoding', lambda: S.write_store(self.codes, self.meta, self.dir / 'x', level=S.SCREEN_VERSION, encoding='gzip')),
                ('metadata shape', lambda: S.write_store(self.codes, wrong_shape, self.dir / 'x', level=S.SCREEN_VERSION, encoding='split')),
                ('missing Hansen identities', lambda: S.write_store(self.codes, no_sources, self.dir / 'x', level=S.SCREEN_VERSION, encoding='split')),
                ('bad transform', lambda: S.write_store(self.codes, bad_transform, self.dir / 'x', level=S.SCREEN_VERSION, encoding='split'))):
            with self.subTest(label), self.assertRaises(ValueError):
                call()
        self.assertEqual(list(self.dir.iterdir()), [])

    def test_flipped_payload_byte_is_rejected(self):
        for encoding in S.ENCODINGS:
            with self.subTest(encoding=encoding):
                path, manifest = self.write(encoding)
                blob = bytearray(path.read_bytes())
                for offset in (len(blob) - 1, len(blob) - manifest['payload_bytes'] // 2, len(blob) - manifest['payload_bytes']):
                    data = bytearray(blob)
                    data[offset] ^= 0x01
                    self.check_rejected(bytes(data))

    def test_truncated_and_extended_files_are_rejected(self):
        for encoding in S.ENCODINGS:
            with self.subTest(encoding=encoding):
                path, _ = self.write(encoding)
                blob = path.read_bytes()
                for length in (0, 7, S.PREFIX.size - 1, S.PREFIX.size + 5, len(blob) // 2, len(blob) - 1):
                    self.check_rejected(blob[:length])
                self.check_rejected(blob + b'\x00')

    def test_wrong_magic_and_version_are_rejected(self):
        path, _ = self.write()
        blob = path.read_bytes()
        self.check_rejected(b'PLDECID2' + blob[8:])
        self.check_rejected(b'plcodec1' + blob[8:])
        self.check_rejected(blob[:8] + struct.pack('<I', 1) + blob[12:])  # the previous format
        self.check_rejected(blob[:8] + struct.pack('<I', 3) + blob[12:])
        self.check_rejected(blob[:8] + struct.pack('<I', 0) + blob[12:])

    def test_every_bit_flip_in_the_prefix_and_header_is_rejected(self):
        path, _ = self.write()
        blob = path.read_bytes()
        _, _, length, _ = S.PREFIX.unpack_from(blob)
        for position in range(S.PREFIX.size + length):
            for bit in range(8):
                data = bytearray(blob)
                data[position] ^= 1 << bit
                with self.subTest(position=position, bit=bit):
                    self.check_rejected(bytes(data))

    def test_header_checksum_is_verified_before_the_header_is_parsed(self):
        path, _ = self.write()
        blob = path.read_bytes()
        magic, version, length, crc = S.PREFIX.unpack_from(blob)
        wrong = S.PREFIX.pack(magic, version, length, crc ^ 1) + blob[S.PREFIX.size:]
        self.check_rejected(wrong)
        garbage = b'{' * length  # not JSON, but with a matching CRC the parser (not the checksum) must refuse it
        framed = S.PREFIX.pack(magic, version, length, zlib.crc32(garbage)) + garbage + blob[S.PREFIX.size + length:]
        with mock.patch.object(S, '_parse_header', side_effect=AssertionError('parsed')):
            self.check_rejected(wrong)
        self.check_rejected(framed)

    def test_rehashed_forgery_is_accepted_but_not_with_the_trusted_file_digest(self):
        path, manifest = self.write()
        blob = path.read_bytes()
        forged = replace_header(blob, transform=[0.00025, 0.0, 98.77235, 0.0, -0.00025, 8.582])  # every hash recomputed
        forged_path = self.dir / 'forged.plds'
        forged_path.write_bytes(forged)
        _, header = S.read_store(forged_path)  # integrity, not authenticity: nothing inside the file can object
        self.assertEqual(header['transform'][2], 98.77235)
        with self.assertRaises(ValueError):
            S.read_store(forged_path, expected_sha256=manifest['file_sha256'])

    def test_overflowing_header_numbers_are_value_errors(self):
        path, _ = self.write()
        blob = path.read_bytes()
        for value in (10 ** 400, -10 ** 400, 1e999, float('nan')):
            transform = [value, 0.0, 98.77225, 0.0, -0.00025, 8.582]
            with self.subTest(value=str(value)[:12]):
                if value == value and abs(value) != float('inf'):  # finite Python ints still reach the header
                    self.check_rejected(replace_header(blob, transform=transform))
                with self.assertRaises(ValueError):
                    S.write_store(self.codes, {**self.meta, 'transform': transform}, self.dir / 'w.plds',
                                  level=S.SCREEN_VERSION, encoding='split')
        self.assertTrue(S._finite(1.5) and S._finite(7))
        self.assertFalse(any(map(S._finite, (10 ** 400, True, float('inf'), float('nan'), '1', None))))

    def test_header_shape_mismatch_is_rejected(self):
        for encoding in S.ENCODINGS:
            with self.subTest(encoding=encoding):
                path, _ = self.write(encoding)
                blob = path.read_bytes()
                h, w = self.codes.shape
                for shape in ([h + 1, w], [h, w - 1], [w, h], [1, 1], [h * w, 1]):
                    self.check_rejected(replace_header(blob, shape=shape))
                self.check_rejected(replace_header(blob, shape=[0, w]))
                self.check_rejected(replace_header(blob, shape=[h, S.MAX_DIMENSION + 1]))
                self.check_rejected(replace_header(blob, shape=[h, 'x']))

    def test_header_field_tampering_is_rejected(self):
        path, _ = self.write()
        blob = path.read_bytes()
        _, _, length, _ = S.PREFIX.unpack_from(blob)
        raw = blob[S.PREFIX.size:S.PREFIX.size + length]
        rest = blob[S.PREFIX.size + length:]

        def framed(header):
            return S.PREFIX.pack(S.MAGIC, S.VERSION, len(header), zlib.crc32(header)) + header + rest
        header = json.loads(raw)
        bad_headers = {
            'duplicate key': raw[:-1] + b',"crs":"EPSG:4326"}',
            'not canonical': json.dumps(header, indent=1).encode(),
            'extra field': S._canonical({**header, 'extra': 1}),
            'missing field': S._canonical({k: v for k, v in header.items() if k != 'crs'}),
            'unknown level': S._canonical({**header, 'level': 'eudr-screen.v2'}),
            'unknown encoding': S._canonical({**header, 'encoding': 'gzip'}),
            'short digest': S._canonical({**header, 'payload_sha256': header['payload_sha256'][:-1]}),
            'upper-case digest': S._canonical({**header, 'codes_sha256': header['codes_sha256'].upper()}),
            'bad source key': S._canonical({**header, 'sources': {'x': 'a' * 64}}),
            'wrong codes hash': S._canonical({**header, 'codes_sha256': '0' * 64}),
            'oversized payload claim': S._canonical({**header, 'payload_bytes': S.MAX_PAYLOAD_BYTES + 1}),
            'bool payload size': S._canonical({**header, 'payload_bytes': True}),
            'nan': raw.replace(b'0.00025', b'NaN', 1),
            'not json': b'{' * 200,
            'deeply nested': b'[' * 20000 + b']' * 20000,
            'not an object': b'[]',
            'bad transform': S._canonical({**header, 'transform': [1, 2, 3]}),
            'empty crs': S._canonical({**header, 'crs': ''})}
        for label, bad in bad_headers.items():
            with self.subTest(label):
                self.check_rejected(framed(bad))
        for claimed in (0, 1, S.MAX_HEADER_BYTES + 1, 2 ** 32 - 1):
            with self.subTest(claimed=claimed):
                self.check_rejected(S.PREFIX.pack(S.MAGIC, S.VERSION, claimed, zlib.crc32(raw)) + raw + rest)

    def test_code_outside_the_code_space_is_rejected(self):
        for code in (20, 21, 255):
            raster = self.codes.copy()
            raster[2, 3] = code
            raw = raster.tobytes()
            payloads = {'zstd19': S._zstd(raw, 19), 'zstd22': S._zstd(raw, 22), 'xz': S._xz(raw),
                        'lzma2': S._encode_lzma2(raster), 'rle': S._encode_rle(raster),
                        'split': b''.join(part for _, part in S._split_parts(raster))}
            self.assertEqual(set(payloads), set(S.ENCODINGS))
            for encoding, payload in payloads.items():
                for level in S.LEVELS:
                    with self.subTest(code=code, encoding=encoding, level=level):
                        header = S._header(raster, self.meta, level, encoding, payload)
                        self.check_rejected(S._file_bytes(header, payload))

    def test_decision_store_with_nonforest_loss_is_rejected(self):
        for code in S.NO_DECISION_CODES:
            raster = self.codes.copy()
            raster[(raster > 2) & (raster < 8)] = 2
            raster[4, 4] = code
            for encoding in S.ENCODINGS:
                with self.subTest(code=code, encoding=encoding):
                    payload = S.encode_codes(raster, encoding)
                    header = S._header(raster, self.meta, S.DECISION_VERSION, encoding, payload)
                    self.check_rejected(S._file_bytes(header, payload))
                    # the same bytes are a valid screen store
                    screen = S._file_bytes({**header, 'level': S.SCREEN_VERSION}, payload)
                    path = self.dir / 'screen-ok.plds'
                    path.write_bytes(screen)
                    np.testing.assert_array_equal(S.read_store(path)[0], raster)

    def test_decision_store_accepts_everything_outside_the_dropped_codes(self):
        raster = np.tile(np.array([c for c in range(S.CODE_COUNT) if c not in S.NO_DECISION_CODES], np.uint8), (4, 3))
        meta = metadata(*raster.shape)
        S.write_store(raster, meta, self.dir / 'd.plds', level=S.DECISION_VERSION, encoding='split')
        np.testing.assert_array_equal(S.read_store(self.dir / 'd.plds')[0], raster)

    def test_expected_hash_and_unusual_paths(self):
        path, manifest = self.write()
        S.read_store(path, expected_sha256=manifest['file_sha256'])
        for bad in ('0' * 64, 'xyz', manifest['file_sha256'].upper(), 5):
            with self.subTest(bad=bad), self.assertRaises(ValueError):
                S.read_store(path, expected_sha256=bad)
        with self.assertRaises(ValueError):
            S.read_store(self.dir / 'missing.plds')
        with self.assertRaises(ValueError):
            S.read_store(self.dir)
        link = self.dir / 'link.plds'
        link.symlink_to(path)
        with self.assertRaises(ValueError):
            S.read_store(link)


class ContractTest(unittest.TestCase):
    def test_constants_match_engine_decision(self):
        from engine import decision
        self.assertEqual(S.CODE_COUNT, decision.CODE_COUNT)
        self.assertEqual((S.SCREEN_VERSION, S.DECISION_VERSION), (decision.SCREEN_VERSION, decision.DECISION_VERSION))
        self.assertEqual(S.LEVELS, decision.LEVELS)
        self.assertEqual(list(S.NO_DECISION_CODES), list(range(decision.LAND + 1, decision.LAND + 6)))
        screen = np.arange(decision.CODE_COUNT, dtype=np.uint8).reshape(4, 5)
        projected = decision.project_decision(screen)
        self.assertTrue(np.isin(screen, list(S.NO_DECISION_CODES)).any())
        self.assertFalse(np.isin(projected, list(S.NO_DECISION_CODES)).any())
        self.assertEqual(S.CODE_COUNT, 20)

    def test_reader_stays_off_rasterio_and_shapely(self):
        code = "import engine.decision_store, sys; print('rasterio' in sys.modules, 'shapely' in sys.modules)"
        result = subprocess.run([sys.executable, '-B', '-c', code], cwd=ROOT, capture_output=True, text=True, check=True)
        self.assertEqual(result.stdout.split(), ['False', 'False'])

    def test_read_store_works_without_loading_the_heavy_geospatial_stack(self):
        with tempfile.TemporaryDirectory() as temp:
            codes = structured(h=18, w=26)
            path = Path(temp) / 's.plds'
            S.write_store(codes, metadata(18, 26), path, level=S.SCREEN_VERSION, encoding='split')
            code = ("import sys, numpy; from engine.decision_store import read_store; "
                    f"codes, header = read_store({str(path)!r}); "
                    "print(codes.shape, header['encoding'], 'rasterio' in sys.modules, 'shapely' in sys.modules)")
            result = subprocess.run([sys.executable, '-B', '-c', code], cwd=ROOT, capture_output=True, text=True, check=True)
            self.assertEqual(result.stdout.split()[-3:], ['split', 'False', 'False'])


class RealCodesTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from engine import decision, jrc, source
        cls.hansen, cls.chip = source.load_source(), jrc.load_jrc()
        screen = decision.derive_screen_codes(cls.hansen, cls.chip)
        cls.levels = {S.SCREEN_VERSION: screen, S.DECISION_VERSION: decision.project_decision(screen)}
        cls.meta = {**cls.hansen.metadata, 'jrc_chip_sha256': cls.chip.metadata['chip_sha256']}
        cls.payloads = {(level, encoding): S.encode_codes(codes, encoding)
                        for level, codes in cls.levels.items() for encoding in S.ENCODINGS}

    def test_every_encoding_round_trips_the_derived_codes(self):
        for (level, encoding), payload in self.payloads.items():
            with self.subTest(level=level, encoding=encoding):
                codes = self.levels[level]
                np.testing.assert_array_equal(S.decode_codes(payload, codes.shape, encoding), codes)

    def test_decision_level_has_no_dropped_codes_and_screen_has_them(self):
        decision = self.levels[S.DECISION_VERSION]
        self.assertFalse(np.isin(decision, list(S.NO_DECISION_CODES)).any())
        self.assertTrue(np.isin(self.levels[S.SCREEN_VERSION], list(S.NO_DECISION_CODES)).any())

    def test_structure_aware_encoding_beats_every_generic_encoding(self):
        for level in S.LEVELS:
            sizes = {encoding: len(self.payloads[level, encoding]) for encoding in S.ENCODINGS}
            with self.subTest(level=level, sizes=sizes):
                self.assertEqual(min(sizes, key=sizes.get), 'split')

    def test_encoding_is_deterministic(self):
        for level, codes in self.levels.items():
            for encoding in ('zstd19', 'rle', 'split'):
                with self.subTest(level=level, encoding=encoding):
                    self.assertEqual(S.encode_codes(codes, encoding), self.payloads[level, encoding])

    def test_split_decodes_within_the_budget_and_stores_round_trip(self):
        with tempfile.TemporaryDirectory() as temp:
            for level, codes in self.levels.items():
                path = Path(temp) / f'{level}.plds'
                manifest = S.write_store(codes, self.meta, path, level=level, encoding='split')
                back, header = S.read_store(path, expected_sha256=manifest['file_sha256'])
                np.testing.assert_array_equal(back, codes)
                self.assertEqual(header['sources']['hansen_lossyear'], self.hansen.metadata['sources'][1]['sha256'])
                self.assertEqual(header['sources']['jrc_chip'], self.chip.metadata['chip_sha256'])
                self.assertEqual(header['shape'], self.hansen.metadata['shape'])
                self.assertEqual(header['transform'], self.hansen.metadata['transform'])
                payload = self.payloads[level, 'split']
                self.assertLess(S._median_ms(lambda: S.decode_codes(payload, codes.shape, 'split'), runs=5), 50 * S.DECODE_BUDGET_MS)

    def test_one_flipped_cell_is_caught_by_the_header_hash(self):
        codes = self.levels[S.DECISION_VERSION]
        flipped = codes.copy()
        flipped[100, 100] = 8 if flipped[100, 100] != 8 else 2
        payload = S.encode_codes(flipped, 'split')
        header = S._header(codes, self.meta, S.DECISION_VERSION, 'split', payload)  # hash of the original codes
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / 'flipped.plds'
            path.write_bytes(S._file_bytes(header, payload))
            with self.assertRaises(ValueError):
                S.read_store(path)

    def test_store_aware_evaluation_binds_the_level_to_the_raster(self):
        from engine import decision, source
        geometry = next(p for p in source.load_plots() if p['plot_id'] == 'P-0005')['geometry']
        with tempfile.TemporaryDirectory() as temp:
            stored = {}
            for level, codes in self.levels.items():
                path = Path(temp) / f'{level}.plds'
                S.write_store(codes, self.meta, path, level=level, encoding='split')
                stored[level] = S.read_store(path)
        for level, (codes, header) in stored.items():
            self.assertEqual(decision.evaluate_store(codes, header, geometry),
                             decision.evaluate_codes(codes, self.hansen.metadata, geometry, level))
            self.assertEqual(decision.evaluate_store(codes, header, geometry, level)['contract'], level)
        screen_codes, screen_header = stored[S.SCREEN_VERSION]
        periods = decision.evaluate_store(screen_codes, screen_header, geometry)['hansen_loss_after_2020']['periods']
        self.assertIs(periods['2024-2025']['mapped_loss_present'], True)
        decision_codes, decision_header = stored[S.DECISION_VERSION]
        # the silent false negative: this raster read as screen reports no Hansen loss for P-0005 (mapped_loss_present False)
        self.assertIs(decision.evaluate_codes(decision_codes, self.hansen.metadata, geometry, S.SCREEN_VERSION)
                      ['hansen_loss_after_2020']['periods']['2024-2025']['mapped_loss_present'], False)
        with self.assertRaisesRegex(ValueError, 'store holds eudr-decision.v1, not eudr-screen.v1'):
            decision.evaluate_store(decision_codes, decision_header, geometry, S.SCREEN_VERSION)
        with self.assertRaises(ValueError):  # the raster must be the header's grid
            decision.evaluate_store(decision_codes[:100, :100], decision_header, geometry)
        for bad in ({}, None, {**decision_header, 'level': 'eudr-screen.v2'}):
            with self.assertRaises(ValueError):
                decision.evaluate_store(decision_codes, bad, geometry)
        rows, cols = np.array([0]), np.array([0])
        for call in (lambda: decision.evaluate_codes(decision_codes, self.hansen.metadata, geometry),
                     lambda: decision.summarize_selection(decision_codes, rows, cols),
                     lambda: decision.summarize_counts([0] * decision.CODE_COUNT, 0, 0)):
            with self.assertRaises(TypeError):  # no function guesses the level
                call()

    def test_committed_stores_decode_to_the_derived_codes(self):
        record_path = ROOT / S.OUTPUT / 'stores.json'
        if not record_path.exists():
            self.skipTest('artifacts/decision has not been built')
        record = json.loads(record_path.read_text())
        for level, codes in self.levels.items():
            with self.subTest(level=level):
                entry = record['levels'][level]
                path = ROOT / entry['file']
                back, header = S.read_store(path, expected_sha256=entry['store']['file_sha256'])
                np.testing.assert_array_equal(back, codes)
                self.assertEqual(header['encoding'], entry['chosen'])
                self.assertEqual(path.stat().st_size, entry['store']['file_bytes'])
                self.assertEqual(entry['store']['codes_sha256'], S.codes_digest(codes))
                self.assertTrue(all(c['lossless'] for c in entry['candidates']))
                self.assertEqual({c['encoding'] for c in entry['candidates']}, set(S.ENCODINGS))


if __name__ == '__main__':
    unittest.main()
