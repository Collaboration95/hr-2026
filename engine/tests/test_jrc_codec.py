from compression import zstd
import copy
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import numpy as np
from engine.jrc import ROOT, JrcDataset, load_jrc
from engine import jrc_codec as codec
from engine.source import canonical_bytes, object_hash
from engine.tests.test_jrc import fixture

SCRATCH = ROOT / 'data/experimental/jrc-engine/tests'


class JrcCodecTests(unittest.TestCase):
    def setUp(self):
        SCRATCH.mkdir(parents=True, exist_ok=True)
        self.temp = tempfile.TemporaryDirectory(dir=SCRATCH)
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)

    def make(self, candidate, ds=None):
        self.ds = fixture([[0, 1, 0], [1, 0, 1]], [[True, False, True], [False, True, True]]) if ds is None else ds
        self.path = self.root / candidate
        return codec.encode_jrc_store(self.ds, self.path, candidate, 2)

    def rewrite(self, index):
        index['index_sha256'] = object_hash({k: v for k, v in index.items() if k != 'index_sha256'})
        (self.path / 'index.json').write_bytes(canonical_bytes(index))

    def replace_first(self, raw=None, compressed=None):
        index = json.loads((self.path / 'index.json').read_bytes())
        old = (self.path / 'payload.bin').read_bytes()
        new = bytearray(codec.HEADER)
        for i, chunk in enumerate(index['chunks']):
            data = old[chunk['offset']:chunk['offset']+chunk['size']]
            if i == 0:
                if raw is not None:
                    data = zstd.compress(raw, level=codec.LEVELS[index['candidate']])
                    chunk['raw_sha256'] = codec._hash(raw)
                if compressed is not None: data = compressed
            chunk['offset'], chunk['size'], chunk['sha256'] = len(new), len(data), codec._hash(data)
            new.extend(data)
        index['payload_bytes'], index['payload_sha256'] = len(new), codec._hash(new)
        (self.path / 'payload.bin').write_bytes(new)
        self.rewrite(index)

    def test_all_real_pixels_masks_metadata_all_candidates(self):
        source = load_jrc()
        for candidate in codec.CANDIDATES:
            with self.subTest(candidate=candidate):
                path = self.root / candidate
                report = codec.encode_jrc_store(source, path, candidate, 1024)
                d = codec.decode_jrc_store(path)
                np.testing.assert_array_equal(source.values, d.values)
                np.testing.assert_array_equal(source.mask, d.mask)
                self.assertEqual(source.metadata, d.metadata)
                self.assertEqual(report['total_bytes'], sum(p.stat().st_size for p in path.iterdir()))

    def test_masked_values_random_edges_and_determinism(self):
        rng = np.random.default_rng(414)
        for candidate in codec.CANDIDATES:
            for h, w, size in [(1, 1, 1), (1, 17, 3), (13, 1, 2), (17, 19, 8)]:
                ds = fixture(rng.integers(0, 2, (h, w)), rng.random((h, w)) > .4)
                path = self.root / candidate
                codec.encode_jrc_store(ds, path, candidate, size)
                original = {p.name: p.read_bytes() for p in path.iterdir()}
                actual = codec.decode_jrc_store(path)
                np.testing.assert_array_equal(actual.values, ds.values)
                np.testing.assert_array_equal(actual.mask, ds.mask)
                codec.encode_jrc_store(ds, path, candidate, size)
                self.assertEqual(original, {p.name: p.read_bytes() for p in path.iterdir()})

    def test_invalid_inputs(self):
        for candidate in codec.CANDIDATES:
            for mutation in ('range', 'float', 'negative', 'maskdtype', 'maskshape', 'metadata'):
                ds = fixture([[0]], [[False]])
                if mutation == 'range': ds.values[0, 0] = 2
                if mutation == 'float': ds.values = ds.values.astype(float)
                if mutation == 'negative': ds.values = np.array([[-1]], dtype=np.int8)
                if mutation == 'maskdtype': ds.mask = ds.mask.astype(np.uint8)
                if mutation == 'maskshape': ds.mask = np.zeros((2, 2), dtype=bool)
                if mutation == 'metadata': ds.metadata['shape'] = [10**10, 2]
                with self.subTest(candidate=candidate, case=mutation), self.assertRaises(ValueError): self.make(candidate, ds)

    def test_malformed_index_before_allocation(self):
        for candidate in codec.CANDIDATES:
            self.make(candidate)
            original = json.loads((self.path / 'index.json').read_bytes())
            edits = [lambda x: x.update(version=2), lambda x: x.update(version=True),
                     lambda x: x.update(compression_level=9), lambda x: x.update(candidate='wrong'),
                     lambda x: x.update(chunk_size=0), lambda x: x['metadata'].update(shape=[10**12, 1]),
                     lambda x: x['chunks'][0].update(offset=0), lambda x: x['chunks'][0].update(index=3),
                     lambda x: x['chunks'][0].update(raw_size=10**12), lambda x: x['chunks'][0].update(height=0),
                     lambda x: x['chunks'][0].update(size=10**12), lambda x: x['chunks'].pop()]
            for i, edit in enumerate(edits):
                bad = copy.deepcopy(original); edit(bad); self.rewrite(bad)
                with self.subTest(candidate=candidate, case=i), patch.object(codec.np, 'empty', side_effect=AssertionError('early allocation')):
                    with self.assertRaises(ValueError): codec.decode_jrc_store(self.path)

    def test_magic_truncation_trailing_and_checksum(self):
        for candidate in codec.CANDIDATES:
            for case in ('magic', 'version', 'truncated', 'trailing', 'corruption'):
                self.make(candidate)
                data = bytearray((self.path / 'payload.bin').read_bytes())
                if case == 'magic': data[0] ^= 1
                if case == 'version': data[8] ^= 1
                if case == 'truncated': data = data[:-1]
                if case == 'trailing': data += b'junk'
                if case == 'corruption': data[-1] ^= 1
                (self.path / 'payload.bin').write_bytes(data)
                with self.subTest(candidate=candidate, case=case), self.assertRaises(ValueError): codec.decode_jrc_store(self.path)

    def test_rehashed_padding_range_and_decompression(self):
        for candidate in codec.CANDIDATES:
            for raw in (b'\x00\x80', b'\x80\x00'):
                self.make(candidate, fixture([[0]]))
                self.replace_first(raw=raw)
                with self.subTest(candidate=candidate, raw=raw), self.assertRaises(ValueError): codec.decode_jrc_store(self.path)
            for compressed in (zstd.compress(b'A'*60000), zstd.compress(b'\0\0')+b'junk',
                               zstd.compress(b'\0\0')[:-1], zstd.compress(b'\0\0')*2):
                self.make(candidate, fixture([[0]]))
                self.replace_first(compressed=compressed)
                with self.assertRaises(ValueError): codec.decode_jrc_store(self.path)

    def test_json_corruption_and_limits(self):
        for candidate in codec.CANDIDATES:
            self.make(candidate)
            for data in (b'{}', b'[]', b'{"x":1,"x":2}', b'{"a":NaN}', b'['*2000):
                (self.path / 'index.json').write_bytes(data)
                with self.assertRaises(ValueError): codec.decode_jrc_store(self.path)
            (self.path / 'index.json').write_bytes(b' '*101)
            with patch.object(codec, 'MAX_INDEX', 100), self.assertRaises(ValueError): codec.decode_jrc_store(self.path)

    def test_rehashed_large_window_and_raw_checksum(self):
        for candidate in codec.CANDIDATES:
            # Both layouts have a 300-byte raw chunk, with a real valid frame.
            n = 1200 if codec.packed(candidate) else 266
            ds = fixture(np.zeros((1, n), dtype=np.uint8))
            self.path = self.root / candidate
            codec.encode_jrc_store(ds, self.path, candidate, 2048)
            index = json.loads((self.path / 'index.json').read_bytes())
            item = index['chunks'][0]
            self.assertEqual(item['raw_size'], 300)
            payload = (self.path / 'payload.bin').read_bytes()
            frame = payload[item['offset']:item['offset']+item['size']]
            self.assertEqual(frame[4] >> 6, 1)
            oversized = frame[:4]+bytes([frame[4] & ~0x20, 0xa0])+frame[5:]
            self.replace_first(compressed=oversized)
            with self.assertRaisesRegex(ValueError, 'advertised window'):
                codec.decode_jrc_store(self.path)
            self.make(candidate)
            index = json.loads((self.path / 'index.json').read_bytes())
            index['chunks'][0]['raw_sha256'] = '0'*64
            self.rewrite(index)
            with self.assertRaisesRegex(ValueError, 'raw checksum'): codec.decode_jrc_store(self.path)


if __name__ == '__main__': unittest.main()
