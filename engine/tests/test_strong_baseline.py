"""Independent-mask, original-lattice, bounded-decoder and full-grid controls."""
from compression import zstd
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import shutil
import tempfile
import unittest
from unittest.mock import patch

import numpy as np
import rasterio

from engine.indexed import evaluate_reader
from engine.model import Dataset
from engine.oracle import oracle_evaluate
from engine.query import evaluate
from engine.source import ROOT, load_source, load_plots, canonical_bytes, sha256_file
from engine.strong_baseline import (encode_control, decode_control, ControlWindowReader,
                                    storage_info, digest, MAX_MANIFEST)
from engine.strong_baseline_measure import prove_dataset, verify_artifact, atomic_json, AREA, check_guard, child

SCRATCH = ROOT / 'data/experimental/strong-baseline'


def fixture(h=3, w=4, independent=False, native=False):
    bands = np.empty((3, h, w), dtype=np.uint8)
    bands[0], bands[1], bands[2] = 70, 0, 1
    masks = np.ones(bands.shape, dtype=bool)
    if independent:
        masks[0, 0, 0] = False
        masks[1, 0, 1] = False
        masks[2, 1, 0] = False
        bands[0, 0, 0], bands[1, 0, 1], bands[2, 1, 0] = 99, 25, 2
    transform = [0.00025, 0, 98.77225, 0, -0.00025, 8.582] if native else [1, 0, 0, 0, -1, h]
    return Dataset(bands, masks, {'shape': [h, w], 'transform': transform,
                                 'crs': 'EPSG:4326', 'synthetic': True})


def box(x0, y0, x1, y1):
    return {'type': 'Polygon', 'coordinates': [[[x0, y0], [x1, y0], [x1, y1], [x0, y1], [x0, y0]]]}


def resign(path, manifest):
    manifest.pop('manifest_sha256', None)
    manifest['manifest_sha256'] = digest(manifest)
    (path / 'manifest.json').write_bytes(canonical_bytes(manifest))


def refresh_files(path, manifest):
    for f in manifest['files']:
        p = path / f['path']
        f.update(bytes=p.stat().st_size, sha256=sha256_file(p))
    resign(path, manifest)


class ControlTests(unittest.TestCase):
    def setUp(self):
        SCRATCH.mkdir(parents=True, exist_ok=True)
        self.tmp = tempfile.TemporaryDirectory(dir=SCRATCH, prefix='test-')
        self.base = Path(self.tmp.name)
        self.counter = 0

    def tearDown(self):
        self.tmp.cleanup()

    def store(self, dataset=None):
        self.counter += 1
        path = self.base / str(self.counter)
        encode_control(dataset if dataset is not None else fixture(), path)
        return path, json.loads((path / 'manifest.json').read_text())

    def test_distinct_band_masks_and_raw_masked_values_roundtrip(self):
        data = fixture(independent=True)
        path, m = self.store(data)
        restored = decode_control(path)
        self.assertTrue(np.array_equal(restored.bands, data.bands))
        self.assertTrue(np.array_equal(restored.masks, data.masks))
        self.assertEqual(restored.metadata, data.metadata)
        self.assertEqual(m['masks']['mode'], 'independent_bitpack_zstd')
        self.assertEqual(m['masks']['invalid_counts'], [1, 1, 1])
        self.assertGreater(storage_info(path)['mask_bytes'], 0)
        with ControlWindowReader(path) as reader:
            b, masks = reader.read_window(0, 2, 0, 3)
            self.assertTrue(np.array_equal(b, data.bands[:, :2, :3]))
            self.assertTrue(np.array_equal(masks, data.masks[:, :2, :3]))

    def test_implicit_masks_checked_and_no_shared_tiff_mask(self):
        path, m = self.store()
        self.assertEqual(m['masks'], {'mode': 'implicit_all_valid', 'invalid_counts': [0, 0, 0]})
        self.assertEqual(storage_info(path)['mask_bytes'], 0)
        with rasterio.open(path / 'bands.tif') as src:
            self.assertTrue((src.read_masks() == 255).all())
        m['masks']['invalid_counts'][1] = 1
        resign(path, m)
        with self.assertRaisesRegex(ValueError, 'implicit mask'):
            decode_control(path)

    def test_deterministic_encoding_and_no_existing_store_overwrite(self):
        data = fixture(independent=True)
        original_b, original_m, original_meta = data.bands.copy(), data.masks.copy(), deepcopy(data.metadata)
        a, _ = self.store(data)
        b, _ = self.store(data)
        self.assertEqual(storage_info(a), storage_info(b))
        before = storage_info(a)
        with self.assertRaises(ValueError):
            encode_control(data, a)
        self.assertEqual(storage_info(a), before)
        self.assertTrue(np.array_equal(data.bands, original_b))
        self.assertTrue(np.array_equal(data.masks, original_m))
        self.assertEqual(data.metadata, original_meta)

    def test_rejects_invalid_raw_ranges_even_when_masked(self):
        for band, bad in enumerate((101, 26, 3)):
            data = fixture()
            data.bands[band, 0, 0] = bad
            data.masks[band, 0, 0] = False
            with self.subTest(band=band), self.assertRaises(ValueError):
                encode_control(data, self.base / f'bad-{band}')
            self.assertFalse((self.base / f'bad-{band}').exists())

    def test_input_dtype_shape_crs_metadata_bounds_rejected(self):
        variants = []
        for dtype in (np.float32, np.int16):
            d = fixture(); d.bands = d.bands.astype(dtype); variants.append(d)
        d = fixture(); d.masks = d.masks.astype(np.uint8); variants.append(d)
        d = fixture(); d.masks = d.masks[:1]; variants.append(d)
        d = fixture(); d.metadata['shape'] = [2, 4]; variants.append(d)
        d = fixture(); d.metadata['crs'] = 'EPSG:3857'; variants.append(d)
        d = fixture(); d.metadata['transform'][1] = .1; variants.append(d)
        d = fixture(); d.metadata['transform'][0] = float('nan'); variants.append(d)
        d = fixture(); d.metadata['object'] = Path('not-json'); variants.append(d)
        d = fixture(); d.bands = np.ma.array(d.bands, mask=np.zeros_like(d.bands, dtype=bool)); variants.append(d)
        for i, d in enumerate(variants):
            with self.subTest(i=i), self.assertRaises(ValueError):
                encode_control(d, self.base / f'invalid-{i}')
        for block in (True, 1, 128, 1024):
            with self.assertRaises(ValueError):
                encode_control(fixture(), self.base / 'block', block)

    def test_malformed_manifest_and_checksum_rejected(self):
        for value in (b'{', b'[]', b'{"version":1,"version":1}', b' '*(MAX_MANIFEST+1)):
            path, _ = self.store()
            (path / 'manifest.json').write_bytes(value)
            with self.subTest(value=value[:20]), self.assertRaises(ValueError):
                decode_control(path)
        path, m = self.store()
        m['metadata']['synthetic'] = False
        (path / 'manifest.json').write_bytes(canonical_bytes(m))
        with self.assertRaisesRegex(ValueError, 'checksum'):
            decode_control(path)

    def test_changed_truncated_file_or_missing_manifest_rejected_before_open(self):
        for mode in ('changed', 'truncated', 'missing'):
            path, _ = self.store()
            f = path / 'bands.tif'
            raw = f.read_bytes()
            if mode == 'missing':
                (path / 'manifest.json').unlink()
            else:
                f.write_bytes(raw[:-1] if mode == 'truncated' else raw[:-1] + bytes([raw[-1] ^ 1]))
            with patch('engine.strong_baseline.rasterio.open', side_effect=AssertionError('opened invalid file')):
                with self.subTest(mode=mode), self.assertRaises(ValueError):
                    decode_control(path)

    def test_header_shape_dtype_and_mask_claim_mismatch(self):
        path, m = self.store()
        m['metadata']['shape'][1] += 1
        resign(path, m)
        with self.assertRaisesRegex(ValueError, 'header/grid/type/mask'):
            decode_control(path)
        path, m = self.store()
        with rasterio.open(path / 'bands.tif') as src:
            profile = dict(src.profile, dtype='uint16')
        with rasterio.open(path / 'bands.tif', 'w', **profile) as dst:
            dst.write(np.ones((3, 3, 4), dtype=np.uint16))
        refresh_files(path, m)
        with self.assertRaisesRegex(ValueError, 'header/grid/type/mask'):
            decode_control(path)

    def test_excessive_allocation_claim_and_path_escape_rejected(self):
        for shape in ([16384, 16384], [2**50, 1]):
            path, m = self.store()
            m['metadata']['shape'] = shape
            resign(path, m)
            with patch('engine.strong_baseline.rasterio.open', side_effect=AssertionError('allocated/opened')):
                with self.assertRaises(ValueError):
                    decode_control(path)
        path, m = self.store()
        m['files'][0]['path'] = '../bands.tif'
        resign(path, m)
        with self.assertRaisesRegex(ValueError, 'known fixed filenames'):
            decode_control(path)

    def test_mask_padding_counts_and_mode_forgeries(self):
        for corruption in ('padding', 'counts', 'implicit'):
            path, m = self.store(fixture(h=3, w=3, independent=True))
            if corruption == 'padding':
                raw = bytearray(zstd.decompress((path / 'masks.zst').read_bytes()))
                raw[-1] |= 128
                (path / 'masks.zst').write_bytes(zstd.compress(bytes(raw), level=3))
                m['masks']['raw_sha256'] = hashlib.sha256(raw).hexdigest()
            elif corruption == 'counts':
                m['masks']['invalid_counts'][0] = 2
            else:
                m['masks'] = {'mode': 'implicit_all_valid', 'invalid_counts': [0, 0, 0]}
            refresh_files(path, m)
            with self.subTest(corruption=corruption), self.assertRaises(ValueError):
                decode_control(path)

    def test_reader_close_window_validation_and_changed_file_detection(self):
        path, _ = self.store()
        with ControlWindowReader(path) as reader:
            for bounds in ((0, 0, 0, 1), (-1, 1, 0, 1), (0, 4, 0, 1), (False, 1, 0, 1)):
                with self.assertRaises(ValueError):
                    reader.read_window(*bounds)
            with (path / 'bands.tif').open('ab') as stream:
                stream.write(b'x')
            with self.assertRaisesRegex(ValueError, 'changed after initialization'):
                reader.read_window(0, 1, 0, 1)
        with self.assertRaisesRegex(ValueError, 'closed'):
            reader.read_window(0, 1, 0, 1)

    def test_guard_rejects_changed_file_and_child_code_fingerprint(self):
        path = self.base / 'guarded-file'
        path.write_bytes(b'first')
        guard = {str(path.relative_to(ROOT)): sha256_file(path)}
        check_guard(guard)
        path.write_bytes(b'other')
        with self.assertRaisesRegex(RuntimeError, 'fingerprint race'):
            check_guard(guard)
        with self.assertRaisesRegex(RuntimeError, 'fingerprint race'):
            child({'guard': {'engine/strong_baseline.py': '0'*64}, 'operation': 'hot'})

    def test_original_lattice_one_ulp_boundary(self):
        data = fixture(native=True)
        path, _ = self.store(data)
        g = box(98.772625, 8.581615000000001, 98.77263500000001, 8.581635)
        expected = evaluate(data, g)
        self.assertEqual(expected['selected_cell_count'], 1)
        self.assertEqual(oracle_evaluate(data, g), expected)
        with ControlWindowReader(path) as reader:
            self.assertEqual(evaluate_reader(reader, g), expected)
            b, m = reader.read_window(1, 2, 1, 2)
            self.assertEqual(reader.metadata, data.metadata)
        shifted = dict(data.metadata, shape=[1, 1], transform=[.00025, 0, 98.7725, 0, -.00025, 8.581750000000001])
        self.assertEqual(evaluate(Dataset(b, m, shifted), g)['selected_cell_count'], 0)

    def test_partial_outside_missing_band_and_independent_masks_query(self):
        data = fixture(independent=True)
        data.bands[1, 2, 2] = 25
        path, _ = self.store(data)
        with ControlWindowReader(path) as reader:
            for g in (box(-2, 0, 4, 3), box(-3, 0, -1, 3), box(0, 0, 4, 3)):
                for missing in ((), ('lossyear',), ('treecover2000', 'datamask')):
                    expected = evaluate(data, g, missing)
                    self.assertEqual(evaluate_reader(reader, g, missing), expected)
                    self.assertEqual(oracle_evaluate(data, g, missing), expected)
            self.assertEqual(evaluate_reader(reader, box(-2, 0, 4, 3))['support'], 'partial')

    def test_full_proof_rejects_offplot_pixel_mask_and_metadata_forgeries(self):
        data = fixture()
        plots = [{'plot_id': 'synthetic-one-cell', 'geometry': box(0, 2, 1, 3)}]
        for what in ('pixel', 'mask', 'metadata'):
            forged = Dataset(data.bands.copy(), data.masks.copy(), deepcopy(data.metadata))
            if what == 'pixel':
                forged.bands[1, 2, 3] = 25  # Outside the only tested plot.
            elif what == 'mask':
                forged.masks[1, 2, 3] = False
            else:
                forged.metadata['synthetic'] = False
            self.assertEqual(evaluate(data, plots[0]['geometry']), evaluate(forged, plots[0]['geometry']))
            with self.subTest(what=what), self.assertRaises(ValueError):
                prove_dataset(data, forged, plots)


class RealControlTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        SCRATCH.mkdir(parents=True, exist_ok=True)
        cls.tmp = tempfile.TemporaryDirectory(dir=SCRATCH, prefix='real-test-')
        cls.path = Path(cls.tmp.name) / 'control'
        cls.data, cls.plots = load_source(), load_plots()
        cls.accepted = {str(p): sha256_file(p) for p in (ROOT / 'artifacts/benchmark-v1.json',
                        ROOT / 'artifacts/experiments/retained-choice.json')}
        cls.report = encode_control(cls.data, cls.path)

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def test_all_real_raw_values_masks_metadata_17_queries_and_oracle(self):
        proof = prove_dataset(self.data, decode_control(self.path), self.plots)
        self.assertEqual(proof['raw_values_checked'], 2234196)
        self.assertEqual(proof['spatial_cells'], 744732)
        self.assertEqual(proof['real_plot_count'], 17)
        self.assertEqual(proof['independent_oracle_exact_count'], 17)
        self.assertEqual(self.report['total_bytes'], sum(p.stat().st_size for p in self.path.iterdir()))
        self.assertGreater(self.report['manifest_bytes'], 947)
        self.assertEqual(self.report['mask_bytes'], 0)

    def test_all_real_original_lattice_indexed_queries_and_nonmutation(self):
        with ControlWindowReader(self.path) as reader:
            for plot in self.plots:
                self.assertEqual(evaluate_reader(reader, plot['geometry']), evaluate(self.data, plot['geometry']))
        self.assertEqual({p: sha256_file(Path(p)) for p in self.accepted}, self.accepted)

    @unittest.skipUnless((ROOT / 'artifacts/strong-baseline-v1.json').exists(), 'generate additive benchmark first')
    def test_additive_artifact_positive_and_altered_byte_claim(self):
        path = ROOT / 'artifacts/strong-baseline-v1.json'
        self.assertTrue(verify_artifact(path)['valid'])
        forged = json.loads(path.read_text())
        forged['controls'][0]['storage']['total_bytes'] -= 948
        with self.assertRaisesRegex(ValueError, 'archive equality'):
            verify_artifact(forged)

    @unittest.skipUnless((ROOT / 'artifacts/strong-baseline-v1.json').exists(), 'generate additive benchmark first')
    def test_fresh_positive_and_six_validator_rehashed_controls(self):
        original = json.loads((ROOT / 'artifacts/strong-baseline-v1.json').read_text())
        positive = verify_artifact(original)
        self.assertIs(positive['valid'], True)
        zero = {'samples':[0.0], 'repetitions':1, 'min':0.0, 'median':0.0, 'p95':0.0}
        def remove_control(a):
            removed = a['controls'].pop()
            a['common_input_view']['totals_with_same_acquisition_provenance_and_supplier_files'].pop(removed['candidate'])
        cases = [
            ('bool-as-int', lambda a:a['controls'][0]['proof'].update(raw_values_equal=1), 'proof claim mismatch'),
            ('hot-one-sample', lambda a:a['controls'][0]['measurements']['full']['hot'].update(wall_ms=deepcopy(zero)), 'timing sample count'),
            ('cold-one-sample', lambda a:a['controls'][0]['measurements']['full']['process_cold'].update(wall_ms=deepcopy(zero)), 'timing sample count'),
            ('negative-encode-time', lambda a:a['controls'][0]['preprocessing']['report'].update(encode_wall_ms=-1), 'finite nonnegative'),
            ('settings-level-3', lambda a:a['identity']['settings'].update(level=3), 'unsupported constant settings'),
            ('missing-declared-control', remove_control, 'control set'),
            ('source-float-count', lambda a:a['source']['proof'].update(real_plot_count=17.0), 'proof claim mismatch'),
            ('custom-numeric-bool', lambda a:a['accepted_custom']['proof'].update(metadata_equal=1), 'proof claim mismatch'),
            ('nested-numeric-bool', lambda a:a['controls'][0]['proof']['comparisons'][0].update(equal=1), 'proof claim mismatch'),
            ('unknown-proof-key', lambda a:a['controls'][0]['proof'].update(unexpected=True), 'proof claim mismatch'),
            ('common-float-count', lambda a:a['common_input_view'].update(supplier_geometry_bytes=float(a['common_input_view']['supplier_geometry_bytes'])), 'common-input'),
            ('unknown-comparison-key', lambda a:a['comparison'].update(unexpected=True), 'derived control comparison'),
        ]
        records = []
        for label, mutate, error in cases:
            forged = deepcopy(original)
            mutate(forged)
            forged['experiment_id'] = 'exp-' + digest(forged['identity'])
            folder = AREA / forged['experiment_id']
            fresh_folder = forged['experiment_id'] != original['experiment_id']
            archive = None
            if fresh_folder:
                self.assertFalse(folder.exists())
                folder.mkdir(parents=True)
            try:
                if fresh_folder:
                    for c in forged['controls']:
                        target = folder / c['candidate']
                        shutil.copytree(ROOT/c['store_path'], target)
                        c['store_path'] = str(target.relative_to(ROOT))
                    atomic_json(folder/'identity.json', forged['identity'])
                payload = {k:v for k,v in forged.items() if k != 'archive'}
                archive = folder/'runs'/('run-'+digest(payload)+'.json')
                self.assertFalse(archive.exists())
                atomic_json(archive, payload)
                forged['archive'] = {'path':str(archive.relative_to(ROOT)), 'sha256':sha256_file(archive)}
                with self.subTest(label=label), self.assertRaisesRegex(ValueError, error) as caught:
                    verify_artifact(forged)
                records.append({'case':label,'rejected':True,'reason':str(caught.exception),
                                'rehashed_payload_sha256':digest(payload)})
            finally:
                if fresh_folder:
                    shutil.rmtree(folder)
                elif archive is not None:
                    archive.unlink(missing_ok=True)
        atomic_json(SCRATCH/'proof-hardening-checks.json', {'positive':positive,'negative_controls':records,
                    'all_six_validator_controls_rejected':True,'all_rehashed_controls_rejected':True,
                    'artifact_sha256':sha256_file(ROOT/'artifacts/strong-baseline-v1.json')})

    @unittest.skipUnless((ROOT / 'artifacts/strong-baseline-v1.json').exists(), 'generate additive benchmark first')
    def test_rehashed_archive_cannot_hide_offplot_pixel_mask_metadata_or_byte_forgery(self):
        original = json.loads((ROOT / 'artifacts/strong-baseline-v1.json').read_text())
        for kind, expected_error in [('pixel', 'full raw band mismatch'), ('mask', 'full independent mask mismatch'),
                                     ('metadata', 'exact source reconstruction metadata mismatch'),
                                     ('bytes', 'control byte/file claims')]:
            forged = deepcopy(original)
            forged['identity']['settings']['warmups'] += 1 + ['pixel','mask','metadata','bytes'].index(kind)
            forged['method']['warmups'] = forged['identity']['settings']['warmups']
            forged['experiment_id'] = 'exp-' + digest(forged['identity'])
            folder = AREA / forged['experiment_id']
            self.assertFalse(folder.exists())
            folder.mkdir(parents=True)
            try:
                for c in forged['controls']:
                    target = folder / c['candidate']
                    shutil.copytree(ROOT / c['store_path'], target)
                    c['store_path'] = str(target.relative_to(ROOT))
                c = forged['controls'][0]
                store = ROOT / c['store_path']
                manifest = json.loads((store / 'manifest.json').read_text())
                if kind == 'pixel':
                    with rasterio.open(store / 'bands.tif', 'r+') as dst:
                        dst.write(np.array([[(int(self.data.bands[0, 0, 0])+1)%101]], dtype=np.uint8),
                                  1, window=rasterio.windows.Window(0, 0, 1, 1))
                elif kind == 'mask':
                    masks = self.data.masks.copy()
                    masks[1, 0, 0] = False
                    raw = np.packbits(masks.reshape(-1), bitorder='little').tobytes()
                    p = store / 'masks.zst'
                    p.write_bytes(zstd.compress(raw, level=3))
                    manifest['masks'] = {'mode': 'independent_bitpack_zstd', 'invalid_counts': [0, 1, 0],
                                         'raw_bytes': len(raw), 'raw_sha256': hashlib.sha256(raw).hexdigest(),
                                         'level': 3, 'bitorder': 'little'}
                    manifest['files'].append({'path': 'masks.zst', 'bytes': p.stat().st_size, 'sha256': sha256_file(p)})
                elif kind == 'metadata':
                    manifest['metadata']['product'] += ' forged'
                if kind != 'bytes':
                    refresh_files(store, manifest)
                    c['storage'] = storage_info(store)
                    c['preprocessing']['report'].update(c['storage'])
                    c['preprocessing']['report']['mask_mode'] = manifest['masks']['mode']
                    restored = decode_control(store)
                    # The altered raster/mask cell is outside every real plot.
                    for plot in self.plots:
                        self.assertEqual(evaluate(restored, plot['geometry']), evaluate(self.data, plot['geometry']))
                else:
                    c['storage']['total_bytes'] -= 1
                atomic_json(folder / 'identity.json', forged['identity'])
                payload = {k: v for k, v in forged.items() if k != 'archive'}
                archive = folder / 'runs' / ('run-' + digest(payload) + '.json')
                atomic_json(archive, payload)
                forged['archive'] = {'path': str(archive.relative_to(ROOT)), 'sha256': sha256_file(archive)}
                with self.subTest(kind=kind), self.assertRaisesRegex(ValueError, expected_error):
                    verify_artifact(forged)
            finally:
                shutil.rmtree(folder)


if __name__ == '__main__':
    unittest.main()
