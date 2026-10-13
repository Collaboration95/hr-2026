"""Geometry rejection, bounded work, and adversarial scalar membership tests."""
import copy
from fractions import Fraction
import math
import unittest
import warnings

import numpy as np

from engine.oracle import _orientation, _ring_location, oracle_evaluate
from engine.tests.test_query_oracle import OracleAssertions, core_evaluator, dataset, rectangle


INVALID_GEOMETRIES = {
    'not_a_dict': None,
    'list_instead_of_geometry': [],
    'unsupported_point': {'type': 'Point', 'coordinates': [0.5, 0.5]},
    'unsupported_linestring': {'type': 'LineString', 'coordinates': [[0, 0], [1, 1]]},
    'unsupported_geometrycollection': {'type': 'GeometryCollection', 'geometries': []},
    'missing_type': {'coordinates': []},
    'missing_coordinates': {'type': 'Polygon'},
    'empty_polygon': {'type': 'Polygon', 'coordinates': []},
    'empty_ring': {'type': 'Polygon', 'coordinates': [[]]},
    'unclosed_rectangle': {'type': 'Polygon', 'coordinates': [[[0, 0], [1, 0], [1, 1], [0, 1]]]},
    'unclosed_triangle_three_positions': {'type': 'Polygon', 'coordinates': [[[0, 0], [1, 0], [0, 1]]]},
    'self_crossing_bowtie': {'type': 'Polygon', 'coordinates': [[[0, 0], [1, 1], [0, 1], [1, 0], [0, 0]]]},
    'zero_area_ring': {'type': 'Polygon', 'coordinates': [[[0, 0], [1, 0], [2, 0], [0, 0]]]},
    'position_missing_y': {'type': 'Polygon', 'coordinates': [[[0], [1], [2], [0]]]},
    'position_xyz': {'type': 'Polygon', 'coordinates': [[[0, 0, 1], [1, 0, 1], [1, 1, 1], [0, 1, 1], [0, 0, 1]]]},
    'string_numbers': {'type': 'Polygon', 'coordinates': [[['0', '0'], ['1', '0'], ['1', '1'], ['0', '1'], ['0', '0']]]},
    'boolean_coordinates': {'type': 'Polygon', 'coordinates': [[[False, False], [True, False], [True, True], [False, True], [False, False]]]},
    'nonfinite_nan': {'type': 'Polygon', 'coordinates': [[[0, 0], [1, 0], [1, float('nan')], [0, 1], [0, 0]]]},
    'nonfinite_inf': {'type': 'Polygon', 'coordinates': [[[0, 0], [1, 0], [1, float('inf')], [0, 1], [0, 0]]]},
    'empty_multipolygon': {'type': 'MultiPolygon', 'coordinates': []},
    'hole_outside_exterior': {'type': 'Polygon', 'coordinates': rectangle(0, 0, 1, 1)['coordinates'] + rectangle(2, 2, 3, 3)['coordinates']},
    'overlapping_islands': {'type': 'MultiPolygon', 'coordinates': [rectangle(0, 0, 2, 2)['coordinates'], rectangle(1, 1, 3, 3)['coordinates']]},
}


# Frozen copy of the lead's read-only window-origin-witness.json, SHA-256
# f3e2386ebae72e130254117bd2196c965246d7e0d44f8c47029f7ab0fa2af2ed.
# Keep this regression runnable without requiring ignored experiment scratch.
WINDOW_ORIGIN_WITNESS = {
    'row': 1,
    'col': 1,
    'original_center_x': 98.772625,
    'shifted_center_x': 98.77262499999999,
    'original_transform': [0.00025, 0.0, 98.77225, 0.0, -0.00025, 8.582],
    'shifted_transform': [0.00025, 0, 98.7725, 0, -0.00025, 8.581750000000001],
    'geometry': {'type': 'Polygon', 'coordinates': [[
        [98.772625, 8.581635],
        [98.77263500000001, 8.581635],
        [98.77263500000001, 8.581615000000001],
        [98.772625, 8.581615000000001],
        [98.772625, 8.581635],
    ]]},
}


def window_origin_fixture():
    """Synthetic event at the witnessed native cell; crop its exact raw data."""
    full = dataset(canopy=[[1, 2], [3, 100]], loss=[[0, 1], [20, 25]],
                   transform=list(WINDOW_ORIGIN_WITNESS['original_transform']))
    window = dataset(canopy=full.bands[0, 1:2, 1:2],
                     loss=full.bands[1, 1:2, 1:2],
                     datamask=full.bands[2, 1:2, 1:2],
                     masks=full.masks[:, 1:2, 1:2].copy(),
                     transform=list(WINDOW_ORIGIN_WITNESS['shifted_transform']))
    return full, window


class TestWindowOriginRegression(OracleAssertions):
    """A shifted pixel window is not a new authoritative query lattice.

    Deliberately demonstrate that evaluating the shifted transform is wrong
    for the original query. No codec or unimplemented indexed API is needed.
    """

    def test_original_center_and_reassociated_center_are_one_ulp_apart(self):
        witness = WINDOW_ORIGIN_WITNESS
        a, _, c, _, e, f = witness['original_transform']
        row, col = witness['row'], witness['col']
        original = (c + a * (col + 0.5), f + e * (row + 0.5))
        shifted_origin = (c + a * col, f + e * row)
        self.assertEqual(shifted_origin, (witness['shifted_transform'][2], witness['shifted_transform'][5]))
        reassociated = (shifted_origin[0] + a * 0.5, shifted_origin[1] + e * 0.5)
        self.assertEqual(original[0], witness['original_center_x'])
        self.assertEqual(reassociated[0], witness['shifted_center_x'])
        self.assertEqual(original[0].hex(), '0x1.8b172b020c49cp+6')
        self.assertEqual(reassociated[0].hex(), '0x1.8b172b020c49bp+6')
        self.assertEqual(original[0] - reassociated[0], math.ulp(original[0]))
        self.assertEqual(math.nextafter(original[0], -math.inf), reassociated[0])
        self.assertEqual(original[1], reassociated[1])
        ring = witness['geometry']['coordinates'][0]
        self.assertEqual(_ring_location(original, ring), 0)  # exact boundary
        self.assertEqual(_ring_location(reassociated, ring), -1)  # strictly outside
        # Independent scalar enumeration identifies the original cell itself.
        selected = [(r, k) for r in range(2) for k in range(2)
                    if _ring_location((c + a * (k + 0.5), f + e * (r + 0.5)), ring) >= 0]
        self.assertEqual(selected, [(1, 1)])

    def test_identical_raw_window_cannot_replace_original_query_lattice(self):
        full, window = window_origin_fixture()
        geometry = copy.deepcopy(WINDOW_ORIGIN_WITNESS['geometry'])
        np.testing.assert_array_equal(window.bands, full.bands[:, 1:2, 1:2])
        np.testing.assert_array_equal(window.masks, full.masks[:, 1:2, 1:2])
        original_result = self.query(full, geometry)
        shifted_result = self.query(window, geometry)
        self.assertEqual(original_result['selected_cell_count'], 1)
        self.assertEqual(original_result['valid_land_cell_count'], 1)
        self.assertEqual(original_result['canopy_histogram'][100], 1)
        self.assertEqual(original_result['lossyear_histogram'][25], 1)
        self.assertEqual(original_result['periods']['2024-2025'], {
            'mapped_loss_present': True, 'observed_loss_cell_count': 1})
        self.assertEqual(original_result['support'], 'complete')
        self.assertEqual(shifted_result['selected_cell_count'], 0)
        self.assertEqual(shifted_result['unknown_reasons'], ['no_selected_cells'])
        self.assertEqual(shifted_result['periods']['2024-2025'], {
            'mapped_loss_present': None, 'observed_loss_cell_count': None})
        self.assertEqual(shifted_result['support'], 'none')

    def test_one_ulp_boundary_changes_are_not_tolerated_or_snapped(self):
        full, window = window_origin_fixture()
        original_x = WINDOW_ORIGIN_WITNESS['original_center_x']
        cases = ((math.nextafter(original_x, -math.inf), (1, 1)),
                 (original_x, (1, 0)),
                 (math.nextafter(original_x, math.inf), (0, 0)))
        for left, expected in cases:
            for reverse_winding in (False, True):
                with self.subTest(left_hex=left.hex(), reverse=reverse_winding):
                    geometry = copy.deepcopy(WINDOW_ORIGIN_WITNESS['geometry'])
                    for position in geometry['coordinates'][0]:
                        if position[0] == original_x:
                            position[0] = left
                    if reverse_winding:
                        geometry['coordinates'][0].reverse()
                    results = (self.query(full, geometry), self.query(window, geometry))
                    self.assertEqual(tuple(result['selected_cell_count'] for result in results), expected)

    def test_actual_source_witness_preserves_original_native_cell(self):
        from engine.source import load_source
        source = load_source()
        self.assertEqual(source.metadata['transform'], WINDOW_ORIGIN_WITNESS['original_transform'])
        row, col = WINDOW_ORIGIN_WITNESS['row'], WINDOW_ORIGIN_WITNESS['col']
        original_result = self.query(source, WINDOW_ORIGIN_WITNESS['geometry'])
        self.assertEqual(source.bands[:, row, col].tolist(), [85, 0, 1])
        self.assertEqual(source.masks[:, row, col].tolist(), [True, True, True])
        self.assertEqual(original_result['selected_cell_count'], 1)
        self.assertEqual(original_result['valid_land_cell_count'], 1)
        self.assertEqual(original_result['canopy_histogram'][85], 1)
        self.assertEqual(original_result['lossyear_histogram'][0], 1)
        self.assertEqual(original_result['unknown_cell_count'], 0)
        self.assertEqual(original_result['unknown_reasons'], [])
        self.assertEqual(original_result['support'], 'complete')


class TestGeometryRejection(unittest.TestCase):
    def test_oracle_rejects_invalid_geometry(self):
        for name, geometry in INVALID_GEOMETRIES.items():
            with self.subTest(case=name), warnings.catch_warnings():
                warnings.simplefilter('ignore', RuntimeWarning)
                with self.assertRaises(ValueError):
                    oracle_evaluate(dataset(), geometry)

    def test_core_rejects_invalid_geometry_without_repair(self):
        evaluate = core_evaluator()
        if evaluate is None:
            self.skipTest('lead core evaluator is not available yet')
        for name, geometry in INVALID_GEOMETRIES.items():
            with self.subTest(case=name), warnings.catch_warnings():
                warnings.simplefilter('ignore', RuntimeWarning)
                with self.assertRaises(ValueError):
                    evaluate(dataset(), geometry)

    def test_excessive_bounding_window_is_rejected(self):
        evaluators = [oracle_evaluate]
        if core_evaluator() is not None:
            evaluators.append(core_evaluator())
        for evaluate in evaluators:
            with self.subTest(evaluator=evaluate.__module__):
                with self.assertRaises(ValueError):
                    evaluate(dataset(), rectangle(-5000, -5000, 5000, 5000))

    def test_unknown_missing_band_is_rejected(self):
        evaluators = [oracle_evaluate]
        if core_evaluator() is not None:
            evaluators.append(core_evaluator())
        for evaluate in evaluators:
            with self.subTest(evaluator=evaluate.__module__):
                with self.assertRaises(ValueError):
                    evaluate(dataset(), rectangle(0, 0, 1, 1), ('forest2020',))

    def test_unsupported_grids_are_rejected(self):
        grids = {
            'rotated_b': [1, 0.5, 0, 0, -1, 1],
            'rotated_d': [1, 0, 0, 0.5, -1, 1],
            'south_up': [1, 0, 0, 0, 1, 1],
            'west_up': [-1, 0, 0, 0, -1, 1],
            'zero_scale': [0, 0, 0, 0, -1, 1],
            'nonfinite': [1, 0, float('nan'), 0, -1, 1],
            'short': [1, 0, 0],
        }
        evaluators = [oracle_evaluate]
        if core_evaluator() is not None:
            evaluators.append(core_evaluator())
        for name, transform in grids.items():
            for evaluate in evaluators:
                with self.subTest(grid=name, evaluator=evaluate.__module__):
                    source = dataset()
                    source.metadata['transform'] = transform
                    with self.assertRaises(ValueError):
                        evaluate(source, rectangle(0, 0, 1, 1))
        for evaluate in evaluators:
            source = dataset()
            source.metadata['crs'] = 'EPSG:3857'
            with self.subTest(grid='wrong_crs', evaluator=evaluate.__module__):
                with self.assertRaises(ValueError):
                    evaluate(source, rectangle(0, 0, 1, 1))

    def test_oracle_rejects_raw_range_even_when_masked(self):
        for band, bad_value in ((0, 101), (1, 26), (2, 3)):
            source = dataset()
            source.bands[band, 0, 0] = bad_value
            source.masks[band, 0, 0] = False
            with self.subTest(band=band), self.assertRaises(ValueError):
                oracle_evaluate(source, rectangle(0, 0, 1, 1))

    def test_oracle_rejects_malformed_dataset(self):
        malformed = []
        source = dataset(); source.bands = source.bands.astype(float); malformed.append(source)
        source = dataset(); source.bands = source.bands.astype(np.int16); source.bands[0, 0, 0] = -1; malformed.append(source)
        source = dataset(); source.bands = source.bands[0]; malformed.append(source)
        source = dataset(); source.masks = source.masks.astype(np.uint8); malformed.append(source)
        source = dataset(); source.masks = np.ones((3, 2, 1), dtype=bool); malformed.append(source)
        source = dataset(); source.metadata['shape'] = [2, 2]; malformed.append(source)
        source = dataset(); source.bands = np.empty((3, 0, 1), dtype=np.uint8); source.masks = np.empty((3, 0, 1), dtype=bool); source.metadata['shape'] = [0, 1]; malformed.append(source)
        for index, source in enumerate(malformed):
            with self.subTest(case=index), self.assertRaises(ValueError):
                oracle_evaluate(source, rectangle(0, 0, 1, 1))

    def test_finite_extreme_coordinates_fail_before_scan(self):
        with self.assertRaises(ValueError):
            oracle_evaluate(dataset(transform=[1e-200, 0, 0, 0, -1, 1]), rectangle(1e200, 0, 2e200, 1))


class TestBoundaryMembership(OracleAssertions):
    def test_diagonal_passes_through_centers(self):
        geometry = {'type': 'Polygon', 'coordinates': [[[0, 0], [4, 0], [0, 4], [0, 0]]]}
        result = self.query(dataset(loss=np.zeros((4, 4))), geometry)
        self.assertEqual(result['selected_cell_count'], 10)  # 4+3+2+1, boundary included

    def test_concave_polygon(self):
        geometry = {'type': 'Polygon', 'coordinates': [[[0, 0], [2, 0], [2, 1], [1, 1], [1, 2], [0, 2], [0, 0]]]}
        result = self.query(dataset(loss=np.zeros((2, 2))), geometry)
        self.assertEqual(result['selected_cell_count'], 3)

    def test_touching_multipart_point_counted_once(self):
        # Two valid islands share one boundary vertex at a cell center.
        geometry = {'type': 'MultiPolygon', 'coordinates': [rectangle(-0.5, -0.5, 0.5, 0.5)['coordinates'], rectangle(0.5, 0.5, 1.5, 1.5)['coordinates']]}
        result = self.query(dataset(loss=np.zeros((2, 2))), geometry)
        self.assertEqual(result['selected_cell_count'], 7)
        self.assertEqual(result['in_coverage_cell_count'], 4)

    def test_one_ulp_either_side_of_vertical_boundary(self):
        source = dataset()
        on = self.query(source, rectangle(0, 0, 0.5, 1))
        inside = self.query(source, rectangle(0, 0, math.nextafter(0.5, math.inf), 1))
        outside = self.query(source, rectangle(0, 0, math.nextafter(0.5, -math.inf), 1))
        self.assertEqual([v['selected_cell_count'] for v in (on, inside, outside)], [1, 1, 0])

    def test_translated_dyadic_grid_and_hole_boundaries(self):
        source = dataset(loss=np.zeros((5, 5)), transform=[0.25, 0, 98.75, 0, -0.25, 8.75])
        geometry = rectangle(98.75, 7.5, 100, 8.75)
        geometry['coordinates'].append(rectangle(99.125, 7.875, 99.625, 8.375)['coordinates'][0])
        self.assertEqual(self.query(source, geometry)['selected_cell_count'], 24)

    def test_ring_ray_vertex_and_horizontal_edges(self):
        ring = rectangle(0, 0, 2, 2)['coordinates'][0]
        locations = {(1, 1): 1, (0, 1): 0, (1, 0): 0, (2, 2): 0, (3, 0): -1, (-1, 2): -1}
        for point, expected in locations.items():
            with self.subTest(point=point):
                self.assertEqual(_ring_location(point, ring), expected)

    def test_exact_orientation_near_cancellation(self):
        for y, expected in ((math.nextafter(0.5, -math.inf), -1), (0.5, 0), (math.nextafter(0.5, math.inf), 1)):
            self.assertEqual(_orientation((0, 0), (1, 1), (0.5, y)), expected)
        # The float products overflow, but exact input-float arithmetic works.
        a, b, p = (0.0, 0.0), (1e200, 1e200), (1e200, 1.1e200)
        self.assertEqual(_orientation(a, b, p), 1)
        ax, ay, bx, by, px, py = map(Fraction, (*a, *b, *p))
        exact = (bx - ax) * (py - ay) - (by - ay) * (px - ax)
        self.assertGreater(exact, 0)

    def test_geometry_is_not_mutated(self):
        geometry = rectangle(0, 0, 2, 2)
        before = copy.deepcopy(geometry)
        self.query(dataset(loss=np.zeros((2, 2))), geometry)
        self.assertEqual(geometry, before)


if __name__ == '__main__':
    unittest.main()
