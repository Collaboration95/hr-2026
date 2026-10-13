"""Golden synthetic cases, deterministic differential fixtures, and 17 plots."""
import ast
import importlib
import itertools
import math
from pathlib import Path
import unittest

import numpy as np

from engine.model import BAND_NAMES, Dataset
from engine.oracle import oracle_evaluate


SEED = 20261013
RANDOM_FIXTURES = 240
RESULT_KEYS = {
    'selected_cell_count', 'in_coverage_cell_count', 'out_of_coverage_cell_count',
    'valid_land_cell_count', 'unknown_cell_count', 'datamask_counts',
    'canopy_histogram', 'lossyear_histogram', 'yearly_loss_counts', 'periods',
    'support', 'unknown_reasons',
}


def core_evaluator():
    """Allow independent golden tests before the lead's module arrives."""
    try:
        return importlib.import_module('engine.query').evaluate
    except ModuleNotFoundError as exc:
        if exc.name == 'engine.query':
            return None
        raise


def rectangle(x0, y0, x1, y1):
    return {'type': 'Polygon', 'coordinates': [[[x0, y0], [x1, y0], [x1, y1], [x0, y1], [x0, y0]]]}


def dataset(canopy=None, loss=None, datamask=None, masks=None, transform=None):
    """Small native grid; each cell has side length one by default."""
    loss = np.asarray([[0]] if loss is None else loss, dtype=np.uint8)
    canopy = np.full(loss.shape, 50, dtype=np.uint8) if canopy is None else np.asarray(canopy, dtype=np.uint8)
    datamask = np.ones(loss.shape, dtype=np.uint8) if datamask is None else np.asarray(datamask, dtype=np.uint8)
    bands = np.stack([canopy, loss, datamask])
    masks = np.ones(bands.shape, dtype=bool) if masks is None else np.asarray(masks, dtype=bool)
    h, w = loss.shape
    return Dataset(bands, masks, {'shape': [h, w], 'transform': transform or [1, 0, 0, 0, -1, h], 'crs': 'EPSG:4326'})


class OracleAssertions(unittest.TestCase):
    def query(self, source, geometry, missing_bands=()):
        result = oracle_evaluate(source, geometry, missing_bands)
        self.assert_contract(result)
        evaluate = core_evaluator()
        if evaluate is not None:
            actual = evaluate(source, geometry, missing_bands)
            differences = {k: (result[k], actual.get(k)) for k in RESULT_KEYS if result[k] != actual.get(k)}
            self.assertEqual(set(actual), RESULT_KEYS)
            self.assertFalse(differences, differences)
        return result

    def assert_contract(self, result):
        self.assertEqual(set(result), RESULT_KEYS)
        n = result['selected_cell_count']
        self.assertEqual(n, result['in_coverage_cell_count'] + result['out_of_coverage_cell_count'])
        self.assertLessEqual(result['valid_land_cell_count'], result['in_coverage_cell_count'])
        self.assertLessEqual(result['unknown_cell_count'], n)
        self.assertGreaterEqual(result['unknown_cell_count'], result['out_of_coverage_cell_count'])
        self.assertEqual(set(result['datamask_counts']), {'0', '1', '2'})
        self.assertLessEqual(sum(result['datamask_counts'].values()), result['in_coverage_cell_count'])
        self.assertEqual(set(result['periods']), {'2021-2023', '2024-2025'})
        for value in result['periods'].values():
            self.assertEqual(set(value), {'mapped_loss_present', 'observed_loss_cell_count'})
            if value['mapped_loss_present'] is False:
                self.assertEqual(result['unknown_cell_count'], 0)
                self.assertGreater(result['valid_land_cell_count'], 0)
            if value['mapped_loss_present'] is True:
                self.assertGreater(value['observed_loss_cell_count'], 0)
        if result['canopy_histogram'] is not None:
            self.assertEqual(len(result['canopy_histogram']), 101)
            self.assertEqual(len(result['lossyear_histogram']), 26)
            self.assertEqual(sum(result['canopy_histogram']), result['valid_land_cell_count'])
            self.assertEqual(sum(result['lossyear_histogram']), result['valid_land_cell_count'])
            self.assertEqual(result['yearly_loss_counts'], {str(2000 + year): result['lossyear_histogram'][year] for year in range(1, 26)})
        else:
            self.assertIsNone(result['lossyear_histogram'])
            self.assertIsNone(result['yearly_loss_counts'])
            for value in result['periods'].values():
                self.assertIsNone(value['mapped_loss_present'])
                self.assertIsNone(value['observed_loss_cell_count'])


class TestGoldenQueries(OracleAssertions):
    def test_complete_one_cell_full_expected_result(self):
        result = self.query(dataset(canopy=[[100]], loss=[[25]]), rectangle(0, 0, 1, 1))
        canopy, loss = [0] * 101, [0] * 26
        canopy[100], loss[25] = 1, 1
        self.assertEqual(result, {
            'selected_cell_count': 1, 'in_coverage_cell_count': 1,
            'out_of_coverage_cell_count': 0, 'valid_land_cell_count': 1,
            'unknown_cell_count': 0, 'datamask_counts': {'0': 0, '1': 1, '2': 0},
            'canopy_histogram': canopy, 'lossyear_histogram': loss,
            'yearly_loss_counts': {str(2000 + y): int(y == 25) for y in range(1, 26)},
            'periods': {'2021-2023': {'mapped_loss_present': False, 'observed_loss_cell_count': 0},
                        '2024-2025': {'mapped_loss_present': True, 'observed_loss_cell_count': 1}},
            'support': 'complete', 'unknown_reasons': [],
        })

    def test_tiny_polygon_has_no_cell_centers(self):
        result = self.query(dataset(), rectangle(0.125, 0.125, 0.25, 0.25))
        self.assertEqual(result['selected_cell_count'], 0)
        self.assertEqual(result['support'], 'none')
        self.assertEqual(result['unknown_reasons'], ['no_selected_cells'])

    def test_grid_boundary_centers_include_outside_center(self):
        result = self.query(dataset(loss=[[0, 0]]), rectangle(-0.5, 0.5, 1.5, 0.75))
        self.assertEqual((result['selected_cell_count'], result['in_coverage_cell_count'], result['out_of_coverage_cell_count']), (3, 2, 1))
        self.assertEqual(result['unknown_reasons'], ['out_of_coverage'])

    def test_hole_boundary_is_covered(self):
        polygon = rectangle(0, 0, 5, 5)
        polygon['coordinates'].append(rectangle(1.5, 1.5, 3.5, 3.5)['coordinates'][0])
        result = self.query(dataset(loss=np.zeros((5, 5))), polygon)
        self.assertEqual(result['selected_cell_count'], 24)
        self.assertEqual(result['support'], 'complete')

    def test_hole_interior_is_excluded_and_winding_is_irrelevant(self):
        polygon = rectangle(0, 0, 5, 5)
        polygon['coordinates'].append(rectangle(1, 1, 4, 4)['coordinates'][0])
        source = dataset(loss=np.zeros((5, 5)))
        result = self.query(source, polygon)
        self.assertEqual(result['selected_cell_count'], 16)
        polygon['coordinates'] = [list(reversed(r)) for r in polygon['coordinates']]
        self.assertEqual(self.query(source, polygon), result)

    def test_multipart_islands(self):
        geometry = {'type': 'MultiPolygon', 'coordinates': [rectangle(0, 0, 1, 1)['coordinates'], rectangle(2, 0, 3, 1)['coordinates']]}
        result = self.query(dataset(loss=[[21, 22, 25]]), geometry)
        self.assertEqual(result['selected_cell_count'], 2)
        self.assertEqual(result['lossyear_histogram'][22], 0)
        self.assertEqual(result['periods']['2024-2025']['observed_loss_cell_count'], 1)

    def test_fully_outside_coverage(self):
        result = self.query(dataset(), rectangle(-3, -2, -1, -1))
        self.assertEqual((result['selected_cell_count'], result['in_coverage_cell_count'], result['unknown_cell_count']), (2, 0, 2))
        self.assertEqual(result['unknown_reasons'], ['out_of_coverage', 'no_valid_land'])
        self.assertEqual(result['support'], 'none')

    def test_partial_positive_stays_true(self):
        result = self.query(dataset(loss=[[21, 0]]), rectangle(0, 0, 3, 1))
        self.assertEqual(result['support'], 'partial')
        self.assertEqual(result['unknown_cell_count'], 1)
        self.assertEqual(result['periods']['2021-2023'], {'mapped_loss_present': True, 'observed_loss_cell_count': 1})
        self.assertEqual(result['periods']['2024-2025'], {'mapped_loss_present': None, 'observed_loss_cell_count': 0})
        self.assertEqual(sum(result['canopy_histogram']), 2)

    def test_partial_absence_is_never_false(self):
        result = self.query(dataset(loss=[[0, 0]]), rectangle(0, 0, 3, 1))
        self.assertEqual(result['support'], 'partial')
        for value in result['periods'].values():
            self.assertIsNone(value['mapped_loss_present'])
            self.assertEqual(value['observed_loss_cell_count'], 0)

    def test_nodata_and_water_are_distinct(self):
        for mask_class, unknown, reasons in ((0, 1, ['nodata', 'no_valid_land']), (2, 0, ['no_valid_land'])):
            with self.subTest(mask_class=mask_class):
                result = self.query(dataset(datamask=[[mask_class]], loss=[[25]]), rectangle(0, 0, 1, 1))
                self.assertEqual(result['support'], 'none')
                self.assertEqual(result['unknown_cell_count'], unknown)
                self.assertEqual(result['unknown_reasons'], reasons)
                self.assertEqual(result['datamask_counts'][str(mask_class)], 1)

    def test_known_water_does_not_make_complete_land_unknown(self):
        result = self.query(dataset(datamask=[[1, 2]], loss=[[0, 25]]), rectangle(0, 0, 2, 1))
        self.assertEqual(result['valid_land_cell_count'], 1)
        self.assertEqual(result['unknown_cell_count'], 0)
        self.assertEqual(result['support'], 'complete')
        self.assertFalse(result['periods']['2024-2025']['mapped_loss_present'])

    def test_masked_raw_event_is_not_observed(self):
        masks = np.ones((3, 1, 2), dtype=bool)
        masks[1, 0, 0] = False
        result = self.query(dataset(loss=[[25, 0]], masks=masks), rectangle(0, 0, 2, 1))
        self.assertEqual(result['valid_land_cell_count'], 1)
        self.assertEqual(result['unknown_cell_count'], 1)
        self.assertEqual(result['lossyear_histogram'][25], 0)
        self.assertIsNone(result['periods']['2024-2025']['mapped_loss_present'])

    def test_unknown_union_and_datamask_diagnostics(self):
        masks = np.ones((3, 1, 4), dtype=bool)
        masks[0, 0, 0] = False  # nodata and invalid mask, counted once
        masks[2, 0, 1] = False  # raw datamask 0 is not a diagnostic
        result = self.query(dataset(datamask=[[0, 0, 2, 1]], masks=masks, loss=[[25, 25, 25, 21]]), rectangle(-1, 0, 4, 1))
        self.assertEqual(result['selected_cell_count'], 5)
        self.assertEqual(result['unknown_cell_count'], 3)
        self.assertEqual(result['datamask_counts'], {'0': 1, '1': 1, '2': 1})
        self.assertEqual(result['unknown_reasons'], ['out_of_coverage', 'nodata', 'band_mask_invalid'])
        self.assertTrue(result['periods']['2021-2023']['mapped_loss_present'])

    def test_all_missing_band_subsets_disable_analysis(self):
        source = dataset(loss=[[25]])
        for size in range(1, 4):
            for names in itertools.combinations(BAND_NAMES, size):
                with self.subTest(names=names):
                    result = self.query(source, rectangle(0, 0, 1, 1), tuple(reversed(names)))
                    self.assertEqual(result['support'], 'unavailable')
                    self.assertEqual(result['valid_land_cell_count'], 0)
                    self.assertEqual(result['unknown_cell_count'], 1)
                    self.assertEqual(result['unknown_reasons'], ['band_mask_invalid', 'no_valid_land'] + [f'missing_band:{name}' for name in names])
                    self.assertEqual(result['datamask_counts']['1'], 0 if 'datamask' in names else 1)

    def test_missing_bands_with_no_centers(self):
        result = self.query(dataset(), rectangle(0.125, 0.125, 0.25, 0.25), BAND_NAMES)
        self.assertEqual(result['unknown_cell_count'], 0)
        self.assertEqual(result['unknown_reasons'], ['no_selected_cells'] + [f'missing_band:{name}' for name in BAND_NAMES])
        self.assertEqual(result['support'], 'unavailable')

    def test_all_years_including_zero_and_25(self):
        source = dataset(loss=[list(range(26))], canopy=[[4 * year for year in range(26)]])
        result = self.query(source, rectangle(0, 0, 26, 1))
        self.assertEqual(result['lossyear_histogram'], [1] * 26)
        self.assertEqual(result['canopy_histogram'], [int(v % 4 == 0) for v in range(101)])
        self.assertEqual(result['yearly_loss_counts'], {str(y): 1 for y in range(2001, 2026)})
        self.assertEqual(result['periods']['2021-2023']['observed_loss_cell_count'], 3)
        self.assertEqual(result['periods']['2024-2025']['observed_loss_cell_count'], 2)

    def test_period_edges(self):
        for year in (0, 1, 20, 21, 22, 23, 24, 25):
            with self.subTest(year=year):
                result = self.query(dataset(loss=[[year]]), rectangle(0, 0, 1, 1))
                self.assertEqual(result['periods']['2021-2023']['mapped_loss_present'], 21 <= year <= 23)
                self.assertEqual(result['periods']['2024-2025']['mapped_loss_present'], 24 <= year <= 25)

    def test_query_does_not_mutate_dataset(self):
        source = dataset(loss=[[25, 0]])
        bands, masks, metadata = source.bands.copy(), source.masks.copy(), dict(source.metadata)
        self.query(source, rectangle(-1, 0, 3, 1), ('lossyear',))
        np.testing.assert_array_equal(source.bands, bands)
        np.testing.assert_array_equal(source.masks, masks)
        self.assertEqual(source.metadata, metadata)

    def test_exhaustive_single_cell_masks_classes_and_events(self):
        # 8 validity combinations x 3 datamask classes x 6 event years.
        for validity in itertools.product((False, True), repeat=3):
            for mask_class in range(3):
                for year in (0, 20, 21, 23, 24, 25):
                    with self.subTest(validity=validity, datamask=mask_class, year=year):
                        result = self.query(dataset(loss=[[year]], datamask=[[mask_class]], masks=np.array(validity).reshape(3, 1, 1)), rectangle(0, 0, 1, 1))
                        unknown = not all(validity) or mask_class == 0
                        land = all(validity) and mask_class == 1
                        self.assertEqual(result['unknown_cell_count'], int(unknown))
                        self.assertEqual(result['valid_land_cell_count'], int(land))
                        self.assertEqual(result['datamask_counts'], {str(v): int(v == mask_class and validity[2]) for v in range(3)})
                        self.assertEqual(result['support'], 'complete' if land else 'none')
                        expected_reasons = []
                        if mask_class == 0 and validity[2]:
                            expected_reasons.append('nodata')
                        if not all(validity):
                            expected_reasons.append('band_mask_invalid')
                        if not land:
                            expected_reasons.append('no_valid_land')
                        self.assertEqual(result['unknown_reasons'], expected_reasons)

    def test_every_applicable_reason_in_documented_order(self):
        source = dataset(datamask=[[0, 1]], loss=[[25, 21]])
        result = self.query(source, rectangle(-1, 0, 3, 1), ('lossyear', 'treecover2000'))
        self.assertEqual(result['unknown_reasons'], ['out_of_coverage', 'nodata', 'band_mask_invalid', 'no_valid_land', 'missing_band:treecover2000', 'missing_band:lossyear'])
        self.assertEqual(result['unknown_cell_count'], 4)

    def test_partial_support_from_every_band_mask(self):
        for band in range(3):
            masks = np.ones((3, 1, 2), dtype=bool)
            masks[band, 0, 1] = False
            for year, expected_flag in ((0, None), (25, True)):
                with self.subTest(band=band, observed_year=year):
                    result = self.query(dataset(loss=[[year, 25]], masks=masks), rectangle(0, 0, 2, 1))
                    self.assertEqual(result['support'], 'partial')
                    self.assertEqual(result['unknown_cell_count'], 1)
                    self.assertIs(result['periods']['2024-2025']['mapped_loss_present'], expected_flag)
                    self.assertEqual(result['periods']['2024-2025']['observed_loss_cell_count'], int(year == 25))

    def test_oracle_has_no_core_query_imports(self):
        source = Path(__file__).resolve().parents[1] / 'oracle.py'
        tree = ast.parse(source.read_text())
        modules = []
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom):
                modules.append(node.module or '')
            elif isinstance(node, ast.Import):
                modules.extend(alias.name for alias in node.names)
        self.assertFalse(any(m in ('query', 'engine.query') for m in modules))


class TestRandomizedQueries(OracleAssertions):
    def test_seeded_differential_fixtures(self):
        rng = np.random.default_rng(SEED)
        for index in range(RANDOM_FIXTURES):
            h, w = int(rng.integers(1, 9)), int(rng.integers(1, 9))
            source = dataset(
                canopy=rng.integers(0, 101, size=(h, w), dtype=np.uint8),
                loss=rng.integers(0, 26, size=(h, w), dtype=np.uint8),
                datamask=rng.integers(0, 3, size=(h, w), dtype=np.uint8),
                masks=rng.random((3, h, w)) > 0.17,
                transform=[0.25, 0, 16, 0, -0.5, 12],
            )
            # Coordinates are dyadic, including centers and wholly outside cases.
            x0 = 16 + int(rng.integers(-8, 2 * w + 6)) * 0.125
            y0 = 12 - int(rng.integers(-6, 2 * h + 8)) * 0.25
            x1, y1 = x0 + int(rng.integers(1, 14)) * 0.125, y0 + int(rng.integers(1, 14)) * 0.25
            mode = index % 4
            geometry = rectangle(x0, y0, x1, y1)
            if mode == 1:
                geometry['coordinates'].append(rectangle(x0 + (x1 - x0) / 4, y0 + (y1 - y0) / 4, x1 - (x1 - x0) / 4, y1 - (y1 - y0) / 4)['coordinates'][0])
            elif mode == 2:
                geometry = {'type': 'MultiPolygon', 'coordinates': [geometry['coordinates'], rectangle(x1 + 0.25, y0, x1 + 0.5, y1)['coordinates']]}
            elif mode == 3:
                geometry = {'type': 'Polygon', 'coordinates': [[[x0, y0], [x1, y0], [x0, y1], [x0, y0]]]}
            missing = (BAND_NAMES[index % 3],) if index % 11 == 0 else ()
            with self.subTest(seed=SEED, fixture=index, mode=mode, missing=missing):
                self.query(source, geometry, missing)

    def test_native_decimal_grid_near_boundary_fixtures(self):
        rng = np.random.default_rng(SEED + 1)
        source = dataset(
            canopy=rng.integers(0, 101, size=(8, 9), dtype=np.uint8),
            loss=rng.integers(0, 26, size=(8, 9), dtype=np.uint8),
            transform=[0.00025, 0, 98.77225, 0, -0.00025, 8.582],
        )
        for index in range(120):
            row0, col0 = int(rng.integers(-3, 10)), int(rng.integers(-3, 11))
            x0, y0 = 98.77225 + (col0 + 0.5) * 0.00025, 8.582 + (row0 + 0.5) * -0.00025
            x1 = x0 + int(rng.integers(1, 9)) * 0.00025
            y1 = y0 + int(rng.integers(1, 9)) * 0.00025
            if index % 3 == 0:
                x0 = math.nextafter(x0, math.inf)
            elif index % 3 == 1:
                x0 = math.nextafter(x0, -math.inf)
            geometry = rectangle(x0, y0, x1, y1)
            if index % 2:
                geometry = {'type': 'Polygon', 'coordinates': [[[x0, y0], [x1, y0], [x0, y1], [x0, y0]]]}
            with self.subTest(seed=SEED + 1, fixture=index):
                self.query(source, geometry)


class TestActualPlots(OracleAssertions):
    def test_all_17_supplied_plots(self):
        if core_evaluator() is None:
            self.skipTest('lead core evaluator is not available yet')
        from engine.source import load_plots, load_source
        source, plots = load_source(), load_plots()
        self.assertEqual(len(plots), 17)
        counts = []
        for plot in plots:
            with self.subTest(plot_id=plot['plot_id']):
                result = self.query(source, plot['geometry'])
                counts.append(result['selected_cell_count'])
        self.assertEqual(counts, [121, 87, 47, 262, 256, 27, 28, 27, 42, 25, 7, 39, 14, 9, 34, 15, 8])


if __name__ == '__main__':
    unittest.main()
