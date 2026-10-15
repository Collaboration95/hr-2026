"""Live API identity, bounded native-grid work, fidelity and snapshot lifetime."""
import copy
import hashlib
import json
import math
from pathlib import Path
import shutil
import tempfile
import unittest
from unittest.mock import patch

import numpy as np

from engine.export import differing_fields, evidence_cells
from engine.live_query import (LiveError, LiveSnapshot, _immutable_dataset, parse_request,
                               preflight_geometry)
from engine.model import Dataset
from engine.oracle import oracle_evaluate
from engine.query import select_cells
from engine.source import ROOT, canonical_bytes, load_plots, object_hash

SCRATCH = ROOT / 'data/experimental/live-service'


def rectangle(x0, y0, x1, y1):
    return {'type': 'Polygon', 'coordinates': [[[x0, y0], [x1, y0], [x1, y1], [x0, y1], [x0, y0]]]}


def request_for(snapshot, geometry, request_id='test-1'):
    return {'schema_version': 'plotline.live-request.v1', 'request_id': request_id,
            'expected_snapshot_id': snapshot.snapshot_id, 'geometry': geometry}


def ask(snapshot, geometry, request_id='test-1'):
    request = request_for(snapshot, geometry, request_id)
    return snapshot.query(request, canonical_bytes(request))


def synthetic_snapshot():
    bands = np.array([[[50, 60, 70], [0, 100, 90]],
                      [[21, 25, 25], [0, 25, 0]],
                      [[1, 0, 2], [1, 1, 1]]], dtype=np.uint8)
    masks = np.ones(bands.shape, dtype=bool)
    masks[0, 1, 1] = False
    source = Dataset(bands, masks, {'shape': [2, 3], 'transform': [1, 0, 0, 0, -1, 2],
                                    'crs': 'EPSG:4326', 'product': 'synthetic test fixture'})
    return LiveSnapshot(_immutable_dataset(source), _immutable_dataset(source),
                        canonical_bytes({'synthetic_test_fixture': True}))


def copy_verified_root(snapshot, destination):
    for item in snapshot.health()['snapshot']['verified_files']:
        target = destination / item['path']
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(ROOT / item['path'], target)


class LiveAssertions(unittest.TestCase):
    def assert_canonical_bindings(self, response):
        for field in ('source_result', 'compact_result', 'evidence'):
            encoded = response[field + '_canonical_json']
            self.assertIs(type(encoded), str)
            self.assertEqual(differing_fields(json.loads(encoded), response[field]), [])
            self.assertEqual(hashlib.sha256(encoded.encode('utf-8')).hexdigest(),
                             response['receipt']['payload'][field + '_sha256'])
            self.assertEqual(encoded.encode('utf-8'), canonical_bytes(response[field]))

    def assert_error(self, status, code, callback):
        with self.assertRaises(LiveError) as raised:
            callback()
        self.assertEqual((raised.exception.status, raised.exception.code), (status, code))
        return raised.exception


class TestLiveQuery(LiveAssertions):
    @classmethod
    def setUpClass(cls):
        cls.snapshot = LiveSnapshot.load()

    def test_health_descriptor_hash_and_defensive_copies(self):
        health = self.snapshot.health()
        self.assertEqual(hashlib.sha256(health['snapshot_canonical_json'].encode()).hexdigest(), health['snapshot_id'])
        self.assertEqual(json.loads(health['snapshot_canonical_json']), health['snapshot'])
        self.assertIs(health['snapshot']['full_raw_masks_equal'], True)
        self.assertEqual(health['lifetime'], 'immutable_loaded_snapshot_until_restart')
        self.assertEqual(health['limits']['max_candidate_cells'], 4096)
        health['snapshot']['grid']['shape'][0] = 0
        health['periods']['2021-2023'][0] = 0
        self.assertEqual(self.snapshot.health()['snapshot']['grid']['shape'], [604, 1233])
        self.assertEqual(self.snapshot.health()['periods']['2021-2023'], [2021, 2023])

    def test_all_17_match_frozen_answers_and_complete_evidence(self):
        frozen = json.loads((ROOT / 'artifacts/demo-v1.json').read_text())
        self.assertEqual(len(frozen['plots']), 17)
        for plot in frozen['plots']:
            with self.subTest(plot=plot['plot_id']):
                result = ask(self.snapshot, plot['geometry'], plot['plot_id'])
                self.assertEqual(result['source_result'], plot['source_result'])
                self.assertEqual(result['compact_result'], plot['compact_result'])
                self.assertEqual(result['evidence']['cells'], plot['evidence'])
                self.assertEqual(result['geometry'], plot['geometry'])
                self.assertEqual(result['evidence']['returned_cell_count'], result['source_result']['selected_cell_count'])
                self.assertEqual(result['comparison'], {'equal': True, 'differing_fields': []})
                self.assertNotIn('supplier', result)
                self.assertNotIn('plot_id', result)
                self.assertEqual(result['region_kind'], 'temporary_user_geometry')
                self.assert_canonical_bindings(result)

    def test_receipt_binds_exact_body_geometry_results_and_evidence(self):
        request = request_for(self.snapshot, load_plots()[0]['geometry'])
        body = json.dumps(request, indent=2).encode() + b'\n'
        result = self.snapshot.query(request, body)
        receipt = result['receipt']
        self.assert_canonical_bindings(result)
        self.assertEqual(json.loads(receipt['canonical_json']), receipt['payload'])
        self.assertEqual(hashlib.sha256(receipt['canonical_json'].encode()).hexdigest(), receipt['sha256'])
        self.assertEqual(result['request_body_sha256'], hashlib.sha256(body).hexdigest())
        self.assertEqual(result['geometry_sha256'], object_hash(request['geometry']))
        payload = receipt['payload']
        for field in ('request_id', 'request_body_sha256', 'snapshot_id', 'query_version', 'geometry_sha256'):
            self.assertEqual(payload[field], result[field])
        for field in ('source_result', 'compact_result', 'evidence'):
            self.assertEqual(payload[field + '_sha256'], object_hash(result[field]))
        for name, value in result['runtime'].items():
            if name.endswith('_ms'):
                self.assertTrue(math.isfinite(value) and value >= 0)
        self.assertIs(result['runtime']['benchmark'], False)
        self.assertGreaterEqual(result['runtime']['total_request_ms'], result['runtime']['source_query_ms'] + result['runtime']['compact_query_ms'])

    def test_whitespace_and_request_ids_change_bindings_not_observations(self):
        source = synthetic_snapshot()
        request = request_for(source, rectangle(0, 0, 1, 1), 'old')
        a = source.query(request, canonical_bytes(request))
        b = source.query(request, json.dumps(request, indent=1).encode())
        request['request_id'] = 'current'
        c = source.query(request, canonical_bytes(request))
        self.assertEqual(a['source_result'], c['source_result'])
        self.assertNotEqual(a['request_body_sha256'], b['request_body_sha256'])
        self.assertNotEqual(b['receipt']['sha256'], c['receipt']['sha256'])
        self.assertEqual((a['request_id'], c['request_id']), ('old', 'current'))

    def test_altered_dict_and_numeric_types_cannot_bind_unrelated_body(self):
        source = synthetic_snapshot()
        request = request_for(source, rectangle(0, 0, 1, 1))
        body = canonical_bytes(request)
        for mutation in ('request_id', 'geometry', 'numeric_type', 'boolean_type'):
            altered = copy.deepcopy(request)
            if mutation == 'request_id':
                altered['request_id'] = 'other'
            elif mutation == 'geometry':
                altered['geometry'] = rectangle(1, 0, 2, 1)
            else:
                altered['geometry']['coordinates'][0][0][0] = 0.0 if mutation == 'numeric_type' else False
            with self.subTest(mutation=mutation):
                self.assert_error(400, 'INVALID_REQUEST', lambda: source.query(altered, body))

    def test_stale_expected_snapshot_is_conflict(self):
        request = request_for(self.snapshot, rectangle(0, 0, .0001, .0001))
        request['expected_snapshot_id'] = '0' * 64
        error = self.assert_error(409, 'SNAPSHOT_MISMATCH', lambda: self.snapshot.query(request, canonical_bytes(request)))
        self.assertEqual(error.request_id, 'test-1')

    def test_actual_edited_rectangle_changes_selection(self):
        a = ask(self.snapshot, rectangle(98.77225, 8.58175, 98.7725, 8.582))
        b = ask(self.snapshot, rectangle(98.77225, 8.5815, 98.77275, 8.582))
        self.assertEqual((a['source_result']['selected_cell_count'], b['source_result']['selected_cell_count']), (1, 4))

    def test_tiny_partial_positive_partial_absent_fully_outside(self):
        source = synthetic_snapshot()
        cases = [(rectangle(.01, .01, .02, .02), 0, 'none', None),
                 (rectangle(-1, 1, 2, 2), 3, 'partial', True),
                 (rectangle(-1, 0, 1, 1), 2, 'partial', None),
                 (rectangle(-3, 0, -2, 1), 1, 'none', None)]
        for geometry, selected, support, period_flag in cases:
            with self.subTest(geometry=geometry):
                result = ask(source, geometry)
                self.assert_canonical_bindings(result)
                self.assertEqual(result['source_result'], oracle_evaluate(source._source, geometry))
                self.assertEqual(result['source_result']['selected_cell_count'], selected)
                self.assertEqual(result['source_result']['support'], support)
                self.assertIs(result['source_result']['periods']['2021-2023']['mapped_loss_present'], period_flag)
                self.assertEqual(result['evidence']['cells'], evidence_cells(source._source, geometry))

    def test_raw_masked_values_and_outside_evidence_are_retained(self):
        source = synthetic_snapshot()
        result = ask(source, rectangle(-1, 0, 3, 2))
        cells = {c['id']: c for c in result['evidence']['cells']['features']}
        self.assertEqual(len(cells), result['source_result']['selected_cell_count'])
        props = cells['1:1']['properties']
        self.assertEqual((props['treecover2000'], props['lossyear'], props['datamask']), (100, 25, 1))
        self.assertEqual(props['band_validity'], [False, True, True])
        self.assertIs(props['valid_land'], False)
        self.assertIsNone(cells['0:-1']['properties']['lossyear'])
        self.assertFalse(cells['0:-1']['properties']['in_coverage'])
        self.assertTrue(result['evidence']['complete'])

    def test_holes_and_multipart_match_independent_oracle(self):
        source = synthetic_snapshot()
        hole = rectangle(0, 0, 3, 2)
        hole['coordinates'].append(rectangle(1.25, .25, 1.75, .75)['coordinates'][0])
        multi = {'type': 'MultiPolygon', 'coordinates': [rectangle(0, 0, 1, 1)['coordinates'], rectangle(2, 0, 3, 1)['coordinates']]}
        for geometry in (hole, multi):
            result = ask(source, geometry)
            self.assertEqual(result['source_result'], oracle_evaluate(source._source, geometry))

    def test_strict_type_comparison_rejects_boolean_integer_forgery(self):
        source = synthetic_snapshot()
        real_evaluate = __import__('engine.query', fromlist=['evaluate']).evaluate
        def forged(dataset, geometry):
            result = real_evaluate(dataset, geometry)
            if dataset is source._compact:
                result['periods']['2021-2023']['mapped_loss_present'] = 1
            return result
        with patch('engine.live_query.evaluate', side_effect=forged):
            self.assert_error(500, 'COMPARISON_MISMATCH', lambda: ask(source, rectangle(0, 1, 1, 2)))

    def test_incomplete_evidence_fails_without_receipt(self):
        with patch('engine.live_query.evidence_cells', return_value={'type': 'FeatureCollection', 'features': []}):
            self.assert_error(500, 'INTERNAL_ERROR', lambda: ask(synthetic_snapshot(), rectangle(0, 0, 1, 1)))

    def test_response_and_request_mutation_cannot_change_snapshot(self):
        source = synthetic_snapshot()
        geometry = rectangle(0, 0, 1, 1)
        first = ask(source, geometry)
        expected = copy.deepcopy(first['source_result'])
        first['native_grid']['transform'][0] = 999
        first['geometry']['coordinates'][0][0][0] = 999
        self.assertEqual(ask(source, geometry)['source_result'], expected)
        for dataset in (self.snapshot._source, self.snapshot._compact):
            for array in (dataset.bands, dataset.masks):
                self.assertFalse(array.flags.writeable)
                with self.assertRaises(ValueError):
                    array.setflags(write=True)
                with self.assertRaises(ValueError):
                    array.flat[0] = 0


class TestLiveValidation(LiveAssertions):
    def setUp(self):
        self.snapshot = synthetic_snapshot()

    def test_strict_json_rejects_duplicates_utf8_constants_and_recursion(self):
        bodies = [b'{"x":1,"x":2}', b'\xff', b'{', b'NaN', b'Infinity', b'-Infinity',
                  b'{"geometry":{"type":"Polygon","type":"Point"}}']
        for body in bodies:
            with self.subTest(body=body[:30]):
                self.assert_error(400, 'INVALID_JSON', lambda: parse_request(body))
        # Parser recursion thresholds differ across Python releases. A deeply
        # nested top-level array is invalid either as JSON or as a request.
        with self.assertRaises(LiveError) as raised:
            parse_request(b'[' * 2000 + b']' * 2000)
        self.assertEqual(raised.exception.status, 400)
        self.assertIn(raised.exception.code, ('INVALID_JSON', 'INVALID_REQUEST'))

    def test_body_limit_before_parse(self):
        self.assert_error(413, 'BODY_TOO_LARGE', lambda: parse_request(b' ' * 65537))
        request = request_for(self.snapshot, rectangle(0, 0, 1, 1))
        body = canonical_bytes(request)
        self.assertEqual(parse_request(body + b' ' * (65536-len(body))), request)

    def test_request_shape_and_identifiers(self):
        valid = request_for(self.snapshot, rectangle(0, 0, 1, 1))
        cases = [[], {}, {**valid, 'supplier': 'forbidden'}, {**valid, 'missing_bands': []},
                 {**valid, 'schema_version': 'wrong'}, {**valid, 'expected_snapshot_id': True},
                 {**valid, 'expected_snapshot_id': 'x' * 64}]
        cases.extend({**valid, 'request_id': value} for value in ('', 'x' * 65, '☃', 'a b', True, 123))
        for request in cases:
            with self.subTest(request=request):
                self.assert_error(400, 'INVALID_REQUEST', lambda: parse_request(canonical_bytes(request)))

    def test_geometry_types_ranges_closed_rings_and_topology(self):
        invalid = [None, [], {'type': 'Feature', 'geometry': rectangle(0, 0, 1, 1)},
                   {**rectangle(0, 0, 1, 1), 'properties': {}},
                   {'type': 'Point', 'coordinates': [0, 0]},
                   {'type': 'Polygon', 'coordinates': []},
                   {'type': 'Polygon', 'coordinates': [[[0, 0], [1, 0], [1, 1], [0, 1]]]},
                   {'type': 'Polygon', 'coordinates': [[[0, 0], [1, 1], [0, 1], [1, 0], [0, 0]]]},
                   rectangle(180, 0, 181, 1), rectangle(0, 90, 1, 91)]
        for value in (True, '0', float('nan'), float('inf'), 10**400):
            geometry = rectangle(0, 0, 1, 1)
            geometry['coordinates'][0][1][0] = value
            invalid.append(geometry)
        xyz = rectangle(0, 0, 1, 1)
        xyz['coordinates'][0][1].append(0)
        invalid.append(xyz)
        for geometry in invalid:
            with self.subTest(geometry=geometry):
                self.assert_error(422, 'INVALID_GEOMETRY', lambda: preflight_geometry(geometry, self.snapshot._source.metadata))

    def test_vertex_and_candidate_limits_precede_core_allocation(self):
        too_many = {'type': 'Polygon', 'coordinates': [[[0, 0]] * 513]}
        for geometry in (too_many, rectangle(-100, -80, 100, 80)):
            with patch('engine.live_query.evaluate') as evaluate:
                self.assert_error(422, 'QUERY_TOO_LARGE', lambda: ask(self.snapshot, geometry))
                evaluate.assert_not_called()

    def test_exact_4096_boundary_and_one_ulp_over(self):
        metadata = {'shape': [1, 1], 'crs': 'EPSG:4326', 'transform': [1, 0, 0, 0, -1, 0]}
        exact = rectangle(.5, -61.5, 61.5, -.5)
        self.assertEqual(preflight_geometry(exact, metadata)['candidate_cell_count'], 4096)
        excessive = rectangle(.5, -61.5, math.nextafter(61.5, math.inf), -.5)
        self.assert_error(422, 'QUERY_TOO_LARGE', lambda: preflight_geometry(excessive, metadata))

    def test_preflight_rectangle_equals_actual_core_allocation(self):
        metadata = {'shape': [604, 1233], 'crs': 'EPSG:4326', 'transform': [.00025, 0, 98.77225, 0, -.00025, 8.582]}
        rng = np.random.default_rng(20261013)
        original_meshgrid = np.meshgrid
        for index in range(60):
            row, col = (int(v) for v in rng.integers(-10, 1300, size=2))
            x, y = 98.77225 + (col + .5) * .00025, 8.582 - (row + .5) * .00025
            if index % 3:
                x = math.nextafter(x, math.inf if index % 3 == 1 else -math.inf)
            geometry = rectangle(x, y, x+.0008, y+.0006)
            preflight = preflight_geometry(geometry, metadata)
            with patch('engine.query.np.meshgrid', wraps=original_meshgrid) as mesh:
                select_cells(metadata, geometry)
            rows, cols = mesh.call_args.args
            self.assertEqual((rows[0], rows[-1]+1, cols[0], cols[-1]+1),
                             (preflight['row_start'], preflight['row_stop'], preflight['col_start'], preflight['col_stop']))
            self.assertEqual(len(rows)*len(cols), preflight['candidate_cell_count'])

    def test_window_origin_witness_retains_exact_original_lattice(self):
        snapshot = LiveSnapshot.load()
        geometry = rectangle(98.772625, 8.581615000000001, 98.77263500000001, 8.581635)
        result = ask(snapshot, geometry)
        self.assertEqual(result['source_result']['selected_cell_count'], 1)
        self.assertEqual(result['evidence']['cells']['features'][0]['id'], '1:1')
        self.assertEqual(result['source_result'], oracle_evaluate(snapshot._source, geometry))


class TestLiveSnapshotLoad(LiveAssertions):
    @classmethod
    def setUpClass(cls):
        cls.snapshot = LiveSnapshot.load()
        SCRATCH.mkdir(parents=True, exist_ok=True)

    def test_snapshot_identity_is_repeatable(self):
        self.assertEqual(self.snapshot.health(), LiveSnapshot.load().health())

    def test_raw_mask_and_strict_metadata_mismatch_rejected(self):
        original = self.snapshot._compact
        for fault in ('raw', 'mask', 'metadata', 'metadata_type'):
            bands, masks, metadata = original.bands.copy(), original.masks.copy(), copy.deepcopy(original.metadata)
            if fault == 'raw':
                bands[0, 0, 0] = (int(bands[0, 0, 0]) + 1) % 101
            elif fault == 'mask':
                masks[0, 0, 0] = not masks[0, 0, 0]
            elif fault == 'metadata':
                metadata['product'] = 'altered'
            else:
                metadata['sources'][0]['bytes'] = float(metadata['sources'][0]['bytes'])
            with self.subTest(fault=fault), patch('engine.live_query.decode_store', return_value=(bands, masks, metadata)):
                self.assert_error(503, 'NOT_READY', LiveSnapshot.load)

    def test_minimal_required_files_load_without_full_tile_cache(self):
        with tempfile.TemporaryDirectory(dir=SCRATCH) as directory:
            root = Path(directory)
            copy_verified_root(self.snapshot, root)
            loaded = LiveSnapshot.load(root)
            self.assertEqual(loaded.snapshot_id, self.snapshot.snapshot_id)
            self.assertFalse((root / 'data/raw').exists())

    def test_disk_changes_after_start_do_not_refresh_loaded_snapshot(self):
        with tempfile.TemporaryDirectory(dir=SCRATCH) as directory:
            root = Path(directory)
            copy_verified_root(self.snapshot, root)
            loaded = LiveSnapshot.load(root)
            geometry = load_plots()[0]['geometry']
            before = ask(loaded, geometry)
            path = root / 'data/public/provenance.json'
            path.write_bytes(path.read_bytes() + b'\n')
            self.assertEqual(ask(loaded, geometry)['source_result'], before['source_result'])
            self.assertEqual(loaded.snapshot_id, before['snapshot_id'])
            self.assert_error(503, 'NOT_READY', lambda: LiveSnapshot.load(root))

    def test_concurrent_disk_edit_during_load_rejected(self):
        from engine.codecs import decode_store
        with tempfile.TemporaryDirectory(dir=SCRATCH) as directory:
            root = Path(directory)
            copy_verified_root(self.snapshot, root)
            def racing_decode(path):
                decoded = decode_store(path)
                provenance = root / 'data/public/provenance.json'
                provenance.write_bytes(provenance.read_bytes() + b'\n')
                return decoded
            with patch('engine.live_query.decode_store', side_effect=racing_decode):
                self.assert_error(503, 'NOT_READY', lambda: LiveSnapshot.load(root))

    def test_stale_retained_proof_and_changed_runtime_code_rejected(self):
        for target in ('artifacts/benchmark-v1.json', 'engine/query.py'):
            with tempfile.TemporaryDirectory(dir=SCRATCH) as directory:
                root = Path(directory)
                copy_verified_root(self.snapshot, root)
                path = root / target
                if target.endswith('.json'):
                    value = json.loads(path.read_bytes())
                    value['retained_selection']['run_id'] = 'run-' + '0' * 64
                    path.write_bytes(canonical_bytes(value))
                else:
                    path.write_bytes(path.read_bytes() + b'\n# stale code\n')
                with self.subTest(target=target):
                    self.assert_error(503, 'NOT_READY', lambda: LiveSnapshot.load(root))


if __name__ == '__main__':
    unittest.main()
