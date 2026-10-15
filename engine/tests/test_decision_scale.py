"""Strip pipeline smoke tests on a tiny synthetic exactly nested Hansen/JRC pair, and the cost model's inputs."""
import json
from pathlib import Path
import tempfile
import unittest
import numpy as np
from engine import decision_scale
from engine.decision import derive_screen_codes
from engine.decision_scale import (benchmark_inputs, block_forest, cost_model, presampled_jrc, sample_forest_plane, strip_codes)
from engine.jrc import JrcDataset
from engine.model import Dataset

H, W, K = 6, 8, 3
HANSEN_STEP = 0.25
ORIGIN = (10.0, 5.0)


def hansen_meta(row0, rows):
    return {'shape': [rows, W], 'transform': [HANSEN_STEP, 0, ORIGIN[0], 0, -HANSEN_STEP, ORIGIN[1] - row0 * HANSEN_STEP],
            'crs': 'EPSG:4326'}


def jrc_meta(row0, rows, margin=0):
    step = HANSEN_STEP / K
    return {'shape': [K * rows + 2 * margin, K * W],
            'transform': [step, 0, ORIGIN[0], 0, -step, ORIGIN[1] - (K * row0 - margin) * step], 'crs': 'EPSG:4326'}


def fixture(seed=7):
    rng = np.random.default_rng(seed)
    bands = np.stack([rng.integers(0, 101, (H, W)), rng.integers(0, 26, (H, W)), rng.integers(0, 3, (H, W))]).astype(np.uint8)
    jrc = rng.integers(0, 2, (K * H, K * W)).astype(np.uint8)
    masks = np.ones(bands.shape, bool)
    masks[1, 2, 3] = False
    return bands, masks, jrc


class StripPipelineTests(unittest.TestCase):
    def test_strips_equal_whole_grid_and_presampled_plane(self):
        bands, masks, jrc = fixture()
        whole, plane = strip_codes(bands, masks, hansen_meta(0, H), jrc, np.ones(jrc.shape, bool), jrc_meta(0, H))
        pieces = []
        for r0, rows in ((0, 2), (2, 3), (5, 1)):
            part, _ = strip_codes(bands[:, r0:r0 + rows], masks[:, r0:r0 + rows], hansen_meta(r0, rows),
                                  jrc[K * r0:K * (r0 + rows)], np.ones((K * rows, K * W), bool), jrc_meta(r0, rows))
            pieces.append(part)
        np.testing.assert_array_equal(np.concatenate(pieces), whole)
        np.testing.assert_array_equal(plane, jrc[1::K, 1::K])
        again = derive_screen_codes(Dataset(bands, masks, hansen_meta(0, H)), presampled_jrc(hansen_meta(0, H), plane))
        np.testing.assert_array_equal(again, whole)

    def test_missing_jrc_rows_are_forest_unknown_not_nonforest(self):
        bands, masks, jrc = fixture()
        bands[2] = 1  # all land
        # chip two JRC rows short at the bottom: the last Hansen row has no centre cell
        short = jrc[:-2]
        meta = jrc_meta(0, H)
        meta['shape'] = list(short.shape)
        plane = sample_forest_plane(hansen_meta(0, H), JrcDataset(short, np.ones(short.shape, bool), meta))
        self.assertTrue((plane[-1] == 2).all() and (plane[:-1] < 2).all())

    def test_block_forest_counts_nine_cells(self):
        jrc = np.zeros((K * H, K * W), np.uint8)
        jrc[3:6, 3:6] = 1  # exactly the block of Hansen cell (1, 1)
        ds = JrcDataset(jrc, np.ones(jrc.shape, bool), jrc_meta(0, H))
        count, valid, k = block_forest(hansen_meta(0, H), ds)
        self.assertEqual((k, int(count[1, 1]), int(count.sum())), (3, 9, 9))
        self.assertTrue(valid.all())

    SCALE = {'sizes_bytes': {'original_geotiff': {'total': 400_000_000}, 'L0_yardstick_hansen3_plus_jrc_native_zstd19': 300_000_000,
                             'L1_screen_zstd19': 10_000_000, 'L2_decision_zstd19': 2_000_000},
             'histograms': {'land_cells': 800_000_000}, 'tile': {'hansen_cells': 1_600_000_000, 'name': 'test'},
             'gdal_read_seconds_all_strips_summed': 10.0, 'decode_timing': None}

    def test_cost_model_is_parameterised(self):
        slow = cost_model(self.SCALE, 90.0, 30.0, 40.0)
        fast = cost_model(self.SCALE, 90.0, 3.0, 40.0)
        self.assertGreater(slow['recheck_10m_plots']['L2_decision']['measured_tile']['tropical_belt']['per_plot_compute_seconds'],
                           fast['recheck_10m_plots']['L2_decision']['measured_tile']['tropical_belt']['per_plot_compute_seconds'])
        self.assertTrue(all(p['label'].startswith('list price assumption') for k, p in fast['assumptions']['prices'].items() if k != 'egress'))
        with self.assertRaises(TypeError):
            cost_model(self.SCALE, decision_registry_us_per_plot=30.0)  # no per-plot figure has a default

    def test_cost_labels_come_from_the_parameters_and_nothing_goes_stale(self):
        sources = {'original': 'bench P0', 'registry': 'bench P5d', 'new_polygon': 'bench P4'}
        out = cost_model(self.SCALE, 11.0, 2.5, 33.0, per_plot_sources=sources)
        per_plot = out['assumptions']['per_plot_microseconds']
        self.assertEqual(per_plot, {'original_v1': 11.0, 'original_v1_source': 'bench P0', 'decision_registry': 2.5,
                                    'decision_registry_source': 'bench P5d', 'decision_new_polygon': 33.0,
                                    'decision_new_polygon_source': 'bench P4'})
        self.assertIn('bench P4', out['recheck_10m_plots']['L2_decision_new_polygons']['note'])
        self.assertEqual(out['recheck_10m_plots']['L2_decision_new_polygons']['per_plot_us'], 33.0)
        text = json.dumps(cost_model(self.SCALE, 11.0, 2.5, 33.0))
        for stale in ('PLACEHOLDER', '1.6 ms', '17 plots', 'from the plan'):
            self.assertNotIn(stale, text)
        self.assertEqual(cost_model(self.SCALE, 11.0, 2.5, 33.0)['assumptions']['per_plot_microseconds']['decision_registry_source'],
                         'caller-supplied parameter')

    def test_tile_read_is_the_single_process_figure_when_given_and_the_cpu_sum_is_labelled_otherwise(self):
        measured = cost_model(self.SCALE, 11.0, 2.5, 33.0, tile_read={'seconds': 2.5, 'source': 'one process'})
        fallback = cost_model(self.SCALE, 11.0, 2.5, 33.0)
        for out, seconds in ((measured, 2.5), (fallback, 10.0)):
            self.assertEqual(out['assumptions']['tile_decode_seconds']['values']['original_layers_geotiff'], seconds)
        self.assertIn('one process', measured['assumptions']['tile_decode_seconds']['source'])
        self.assertIn('8 worker processes', fallback['assumptions']['tile_decode_seconds']['source'])
        self.assertIn('overstates', fallback['assumptions']['tile_decode_seconds']['source'])
        slower = measured['recheck_10m_plots']['original_layers_geotiff']['measured_tile']['tropical_belt']['tile_decode_seconds']
        self.assertEqual(slower, 250.0)  # 100 tiles x 2.5 s

    def test_the_container_assumption_is_stated_with_the_store_limits(self):
        container = cost_model(self.SCALE, 11.0, 2.5, 33.0)['assumptions']['container']
        self.assertIn('strip-indexed container', container['assumption'])
        self.assertIn('NOT implemented', container['assumption'])
        self.assertEqual((container['store_max_dimension'], container['store_max_cells']), (16384, 16_777_216))
        self.assertIn('16,384', container['assumption'])

    def test_per_plot_inputs_are_read_from_the_benchmark_result(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / 'benchmark-v1.json'
            self.assertIsNone(benchmark_inputs(path))
            inputs = {'registry_us': 3.33, 'original_us': 86.86, 'new_polygon_us': 38.93, 'source': 'pooled hot medians (W1)'}
            path.write_text(json.dumps({'status': 'measured', 'cost_inputs': inputs}))
            values, sources = benchmark_inputs(path)
            self.assertEqual(values, {'original': 86.86, 'registry': 3.33, 'new_polygon': 38.93})
            self.assertTrue(all('pooled hot medians (W1)' in v for v in sources.values()))
            self.assertIn('cost_inputs.registry_us', sources['registry'])
            path.write_text(json.dumps({'status': 'quick smoke run: not publishable evidence', 'cost_inputs': inputs}))
            with self.assertRaises(ValueError):
                benchmark_inputs(path)

    def test_the_shipped_benchmark_feeds_the_shipped_cost_model(self):
        found = benchmark_inputs()
        if found is None or not decision_scale.COST_PATH.is_file():
            self.skipTest('artifacts/decision has not been built')
        values, sources = found
        recorded = json.loads(decision_scale.COST_PATH.read_text())['assumptions']['per_plot_microseconds']
        self.assertEqual((recorded['original_v1'], recorded['decision_registry'], recorded['decision_new_polygon']),
                         (values['original'], values['registry'], values['new_polygon']))
        self.assertEqual(recorded['decision_registry_source'], sources['registry'])


if __name__ == '__main__':
    unittest.main()
