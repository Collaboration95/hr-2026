"""Scientific fixture and fail-closed gate checks; no writes outside owned paths."""
from fractions import Fraction
import copy
import unittest
from unittest.mock import patch

import numpy as np

import fixtures as f
import study as s


class SpatialSensitivityTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.real = s.run_study()
        cls.synthetic = f.run_fixtures()
        cls.cases = {case['case_id']: case for case in cls.synthetic['cases']}
        cls.source = s.load_source(s.ROOT)

    def test_full_grid_values_masks_and_metadata_exact(self):
        a = self.real['array_comparison']
        self.assertTrue(a['grid_metadata_equal'])
        self.assertEqual(a['raw_values_compared'], 2_234_196)
        self.assertEqual(a['mask_bits_compared'], 2_234_196)
        self.assertEqual(a['raw_value_mismatch_count'], 0)
        self.assertEqual(a['mask_bit_mismatch_count'], 0)
        self.assertTrue(self.real['gates']['pass'])

    def test_both_rules_source_compact_full_results_and_selected_arrays(self):
        self.assertEqual(len(self.real['plots']), 17)
        for plot in self.real['plots']:
            for name, rule in plot['rules'].items():
                with self.subTest(plot=plot['plot_id'], rule=name):
                    self.assertTrue(s.exact_equal(rule['source_result'], rule['compact_result']))
                    self.assertTrue(rule['comparison']['selected_cells_equal'])
                    self.assertTrue(rule['comparison']['selected_raw_values_and_masks_equal'])

    def test_center_matches_existing_canonical_geometry_supplier_and_results(self):
        self.assertEqual(self.real['summary']['canonical_center_match_count'], 17)
        for plot in self.real['plots']:
            rule = plot['rules']['center_covers']
            self.assertTrue(rule['production_evaluate_equal'])
            self.assertEqual(rule['canonical_comparison']['source_differing_fields'], [])
            self.assertEqual(rule['canonical_comparison']['compact_differing_fields'], [])

    def test_real_membership_cross_checks_and_subset(self):
        summary = self.real['summary']
        self.assertEqual(summary['scalar_center_match_count'], 17)
        self.assertEqual(summary['predicate_mismatch_count'], 0)
        self.assertEqual(summary['center_only_cell_membership_count'], 0)
        self.assertEqual(summary['overlap_only_cell_membership_count'], 337)
        self.assertEqual(summary['zero_area_touch_cell_membership_count'], 0)
        self.assertEqual(summary['total_selected_cell_memberships'],
                         {'center_covers': 1048, 'positive_area_overlap': 1385})

    def test_changed_period_flags_have_actual_native_loss_witnesses(self):
        expected = {('P-0003', '2024-2025'): 1, ('P-0004', '2024-2025'): 1,
                    ('P-0014', '2021-2023'): 4, ('P-0015', '2021-2023'): 6,
                    ('P-0019', '2024-2025'): 3}
        plots = {p['plot_id']: p for p in self.real['plots']}
        self.assertEqual(len(self.real['changed_period_flags']), 5)
        for change in self.real['changed_period_flags']:
            with self.subTest(plot=change['plot_id'], period=change['period']):
                self.assertIs(change['center']['mapped_loss_present'], False)
                self.assertIs(change['positive_area_overlap']['mapped_loss_present'], True)
                self.assertEqual(len(change['witnesses']), expected[(change['plot_id'], change['period'])])
                for witness in change['witnesses']:
                    r, c = witness['row'], witness['col']
                    self.assertEqual(list(witness['raw_values'][name] for name in s.BAND_NAMES),
                                     self.source.bands[:, r, c].tolist())
                    self.assertEqual(witness['original_polygon'], plots[change['plot_id']]['geometry'])
                    self.assertTrue(witness['valid_land'])
                    self.assertIs(witness['inclusion']['center_covers'], False)
                    self.assertIs(witness['inclusion']['positive_area_overlap'], True)
                    self.assertFalse(witness['inclusion']['zero_area_touch'])
                    self.assertTrue(witness['overlap_interior_dimension_2'])
                    self.assertGreater(witness['angular_cell_intersection_fraction'], 0)
                    self.assertLess(witness['angular_cell_intersection_fraction'], 1)

    def test_five_supplier_indications_not_explained_in_2021_2023(self):
        summary = self.real['summary']
        self.assertEqual(summary['supplier_indication_ids'], ['P-0003', 'P-0005', 'P-0008', 'P-0010', 'P-0013'])
        self.assertEqual(summary['supplier_indication_new_2021_2023_signal_ids'], [])
        for row in summary['supplier_indication_2021_2023']:
            for rule in ('center_covers', 'positive_area_overlap'):
                self.assertIs(row[rule]['mapped_loss_present'], False)
                self.assertEqual(row[rule]['observed_loss_cell_count'], 0)

    def test_real_and_synthetic_denominators_are_separate(self):
        self.assertIs(self.real['synthetic'], False)
        self.assertEqual(self.real['summary']['real_plot_count'], 17)
        self.assertEqual(self.real['summary']['synthetic_plot_count_in_this_file'], 0)
        self.assertIs(self.synthetic['synthetic'], True)
        self.assertEqual(self.synthetic['real_plot_count'], 0)
        self.assertEqual(self.synthetic['valid_synthetic_case_count'], 24)
        self.assertEqual(self.synthetic['rejection_case_count'], 2)

    def test_analytic_and_scalar_fixture_cellsets_and_reductions(self):
        self.assertTrue(self.synthetic['gates']['pass'], self.synthetic['gates']['failures'])
        for case in self.synthetic['cases']:
            with self.subTest(case=case['case_id']):
                self.assertTrue(all(case['checks'].values()))
                for rule in ('center_covers', 'positive_area_overlap'):
                    self.assertTrue(s.exact_equal(case['rules'][rule]['result'], case['rules'][rule]['scalar_result']))

    def test_exact_analytic_areas_independently_bind_clipping_oracle(self):
        bounds = (1, 1, 2, 2)
        expected = {'tiny_no_center': Fraction(1, 64), 'equal_native_cell': Fraction(1),
                    'point_only_contact': Fraction(0), 'edge_only_contact': Fraction(0),
                    'hole_exact_cell_boundary': Fraction(0), 'hole_interior': Fraction(0),
                    'diagonal_triangle': Fraction(1, 2)}
        for case, area in expected.items():
            with self.subTest(case=case):
                self.assertEqual(f.scalar_area(self.cases[case]['geometry'], bounds), area)
        sliver = self.cases['dyadic_sliver_no_center']['geometry']
        self.assertEqual(f.scalar_area(sliver, (1, 1, 3, 2)), Fraction(1, 256))
        self.assertGreater(f.scalar_area(sliver, bounds), 0)
        self.assertGreater(f.scalar_area(sliver, (2, 1, 3, 2)), 0)

    def test_exact_clipping_does_not_depend_on_geos_membership(self):
        geom = self.cases['diagonal_triangle']['geometry']
        with patch.object(s.shapely, 'intersection', side_effect=AssertionError('GEOS area forbidden')), \
             patch.object(s.shapely, 'covers', side_effect=AssertionError('GEOS membership forbidden')), \
             patch.object(s.shapely, 'relate_pattern', side_effect=AssertionError('GEOS predicate forbidden')):
            self.assertEqual(f.scalar_area(geom, (1, 1, 2, 2)), Fraction(1, 2))
            self.assertTrue(s.scalar_center_covers([1.5, 1.5], geom))
            self.assertTrue(f.scalar_contact(geom, (2, 1, 3, 2)))

    def test_point_and_edge_only_contacts_are_excluded(self):
        point = self.cases['point_only_contact']
        edge = self.cases['edge_only_contact']
        self.assertEqual(point['zero_area_touch_cells'], [[0, 1], [1, 1], [1, 2]])
        self.assertEqual(edge['zero_area_touch_cells'], [[1, 1]])
        for case in (point, edge):
            self.assertNotIn([1, 1], case['rules']['positive_area_overlap']['selected_cells'])
            self.assertIn([1, 1], case['zero_area_touch_cells'])

    def test_holes_boundary_and_interior_are_distinct(self):
        self.assertIn([1, 1], self.cases['hole_boundary_center']['rules']['center_covers']['selected_cells'])
        for name in ('hole_exact_cell_boundary', 'hole_interior'):
            self.assertNotIn([1, 1], self.cases[name]['rules']['positive_area_overlap']['selected_cells'])
        self.assertIn([1, 1], self.cases['hole_exact_cell_boundary']['zero_area_touch_cells'])
        self.assertNotIn([1, 1], self.cases['hole_interior']['zero_area_touch_cells'])

    def test_tiny_sliver_and_multipart_do_not_require_a_center(self):
        for name in ('tiny_no_center', 'dyadic_sliver_no_center', 'multipart_islands'):
            case = self.cases[name]
            self.assertEqual(case['rules']['center_covers']['selected_cells'], [])
            self.assertGreater(len(case['rules']['positive_area_overlap']['selected_cells']), 0)
            self.assertIsNone(case['rules']['center_covers']['result']['periods']['2021-2023']['mapped_loss_present'])

    def test_outside_added_support_changes_absence_to_unknown(self):
        case = self.cases['partial_absence_becomes_unknown']
        center = case['rules']['center_covers']['result']
        overlap = case['rules']['positive_area_overlap']['result']
        self.assertIs(center['periods']['2021-2023']['mapped_loss_present'], False)
        self.assertEqual(center['support'], 'complete')
        self.assertIsNone(overlap['periods']['2021-2023']['mapped_loss_present'])
        self.assertEqual(overlap['periods']['2021-2023']['observed_loss_cell_count'], 0)
        self.assertEqual(overlap['support'], 'partial')
        self.assertEqual(overlap['out_of_coverage_cell_count'], 1)
        self.assertEqual(overlap['unknown_cell_count'], 1)

    def test_witnessed_positive_remains_true_with_outside_unknown(self):
        overlap = self.cases['partial_witnessed_positive']['rules']['positive_area_overlap']['result']
        self.assertIs(overlap['periods']['2021-2023']['mapped_loss_present'], True)
        self.assertEqual(overlap['periods']['2021-2023']['observed_loss_cell_count'], 1)
        self.assertEqual(overlap['unknown_cell_count'], 1)
        self.assertEqual(overlap['support'], 'partial')
        self.assertIsNone(overlap['periods']['2024-2025']['mapped_loss_present'])

    def test_masked_nodata_water_raw_values_survive_but_do_not_vote(self):
        for name, mask_code, unknown in (('invalid_band_mask_raw_loss', 1, 1),
                                          ('nodata_raw_loss', 0, 1), ('water_raw_loss', 2, 0)):
            case = self.cases[name]
            answer = case['rules']['positive_area_overlap']['result']
            self.assertEqual([case['raw_values'][i][1][1] for i in range(3)], [91, 23, mask_code])
            self.assertIsNone(answer['lossyear_histogram'])
            self.assertIsNone(answer['periods']['2021-2023']['mapped_loss_present'])
            self.assertEqual(answer['valid_land_cell_count'], 0)
            self.assertEqual(answer['unknown_cell_count'], unknown)
            dataset = s.Dataset(np.array(case['raw_values'], dtype=np.uint8),
                                np.array(case['raw_masks'], dtype=bool), case['metadata'])
            raw_before, masks_before = dataset.bands.copy(), dataset.masks.copy()
            s.reduce_cells(dataset, [[1, 1]])
            np.testing.assert_array_equal(dataset.bands, raw_before)
            np.testing.assert_array_equal(dataset.masks, masks_before)

    def test_full_histograms_include_zero_and_exclude_masked_nonland_loss(self):
        mixed = self.cases['mixed_mask_nodata_water_land']['rules']['positive_area_overlap']['result']
        self.assertEqual(mixed['valid_land_cell_count'], 3)
        self.assertEqual(mixed['unknown_cell_count'], 2)
        self.assertEqual(mixed['datamask_counts'], {'0': 1, '1': 4, '2': 1})
        self.assertEqual(len(mixed['canopy_histogram']), 101)
        self.assertEqual(len(mixed['lossyear_histogram']), 26)
        self.assertEqual(mixed['lossyear_histogram'][0], 3)
        self.assertEqual(sum(mixed['lossyear_histogram'][1:]), 0)
        self.assertEqual(len(mixed['yearly_loss_counts']), 25)
        self.assertIsNone(mixed['periods']['2021-2023']['mapped_loss_present'])
        for plot in self.real['plots']:
            for rule in plot['rules'].values():
                answer = rule['source_result']
                self.assertEqual(len(answer['canopy_histogram']), 101)
                self.assertEqual(len(answer['lossyear_histogram']), 26)
                self.assertEqual(sum(answer['lossyear_histogram']), answer['valid_land_cell_count'])

    def test_missing_band_is_unknown_and_raw_masked_values_are_preserved(self):
        case = self.cases['missing_loss_band']
        answer = case['rules']['positive_area_overlap']['result']
        self.assertEqual(case['raw_values'][1][1][1], 23)
        self.assertTrue(case['raw_masks'][1][1][1])
        self.assertIsNone(answer['lossyear_histogram'])
        self.assertEqual(answer['support'], 'unavailable')
        self.assertEqual(answer['unknown_cell_count'], 1)

    def test_native_decimal_one_ulp_is_separate_from_rule_sensitivity(self):
        for name, count in (('native_decimal_boundary', 1), ('native_decimal_boundary_one_ulp_in', 1),
                            ('native_decimal_boundary_one_ulp_out', 0)):
            case = self.cases[name]
            self.assertEqual(len(case['rules']['center_covers']['selected_cells']), count)
            self.assertEqual(case['rules']['positive_area_overlap']['selected_cells'], [[1, 1]])
        control = self.synthetic['native_decimal_reassociation_control']
        self.assertIs(control['global_center_selected'], True)
        self.assertIs(control['shifted_center_selected'], False)
        self.assertNotEqual(control['global_center_hex'][0], control['shifted_center_hex'][0])

    def test_invalid_and_zero_area_geometry_rejected(self):
        for case in self.synthetic['rejected_geometries']:
            self.assertTrue(all(decision['rejected'] for decision in case['decisions'].values()))
        invalid = [rectangle for rectangle in (
            {'type': 'Point', 'coordinates': [1, 1]},
            {'type': 'Polygon', 'coordinates': [[[0, 0], [1, 0], [1, 1], [0, 1]]]},
            {'type': 'Polygon', 'coordinates': [[[0, 0], [1, 0], [True, 1], [0, 0]]]},
            {'type': 'Polygon', 'coordinates': [[[0, 0], [1, 0], [float('nan'), 1], [0, 0]]]},
        )]
        for geometry in invalid:
            with self.assertRaises(ValueError):
                s.overlap_membership(self.source.metadata, geometry)

    def test_non_native_grid_is_rejected_instead_of_resampled(self):
        geom = self.cases['equal_native_cell']['geometry']
        for change in ({'crs': 'EPSG:3857'}, {'transform': [1, .1, 0, 0, -1, 3]},
                       {'transform': [0, 0, 0, 0, -1, 3]}):
            metadata = {**f.test_dataset().metadata, **change}
            with self.assertRaises(ValueError):
                s.overlap_membership(metadata, geom)

    def test_unselected_raw_mismatch_blocks_positive_fidelity_claim(self):
        bands, masks, metadata = s.decode_store(s.ROOT / s.STORE)
        bands[0, -1, -1] = (int(bands[0, -1, -1])+1) % 101
        with patch.object(s, 'decode_store', return_value=(bands, masks, metadata)):
            forged = s.run_study()
        self.assertFalse(forged['gates']['positive_encoding_fidelity_claim_allowed'])
        self.assertEqual(forged['array_comparison']['raw_value_mismatch_count'], 1)
        self.assertIn('full_grid_source_compact_mismatch', [x['kind'] for x in forged['gates']['failures']])

    def test_selected_mask_mismatch_blocks_query_and_fidelity_claim(self):
        bands, masks, metadata = s.decode_store(s.ROOT / s.STORE)
        r, c = self.real['plots'][0]['rules']['center_covers']['selected_cells'][0]
        masks[0, r, c] = False
        with patch.object(s, 'decode_store', return_value=(bands, masks, metadata)):
            forged = s.run_study()
        self.assertFalse(forged['gates']['pass'])
        self.assertEqual(forged['array_comparison']['mask_bit_mismatch_count'], 1)
        self.assertTrue(any(x['kind'] == 'source_compact_query_mismatch' for x in forged['gates']['failures']))

    def test_json_bool_integer_confusion_does_not_pass_exact_comparison(self):
        self.assertFalse(s.exact_equal({'flag': True}, {'flag': 1}))
        self.assertFalse(s.exact_equal({'flag': False}, {'flag': 0}))
        self.assertEqual(s.differing_fields({'flag': True}, {'flag': 1}), ['flag'])

    def test_membership_cross_check_failure_blocks_positive_claim(self):
        with patch.object(s, 'scalar_centers', return_value=[]):
            forged = s.run_study()
        self.assertFalse(forged['gates']['pass'])
        self.assertTrue(any(x['kind'] == 'membership_cross_check_mismatch' for x in forged['gates']['failures']))

    def test_input_drift_blocks_positive_claim_without_mutating_any_file(self):
        original = s.fingerprint
        calls = {}
        def drift(path):
            answer = original(path)
            calls[path] = calls.get(path, 0)+1
            if path.name == 'demo-v1.json' and calls[path] > 1:
                answer = {**answer, 'sha256': '0'*64}
            return answer
        with patch.object(s, 'fingerprint', side_effect=drift):
            result = s.run_study()
        self.assertFalse(result['gates']['input_and_code_unchanged'])
        self.assertFalse(result['gates']['positive_encoding_fidelity_claim_allowed'])

    def test_input_fingerprints_unchanged_and_content_hash_verifies(self):
        for path, fingerprint in self.real['input_fingerprints'].items():
            self.assertEqual(s.fingerprint(s.ROOT / path), fingerprint)
        unsigned = {k: v for k, v in self.real.items() if k != 'content_sha256'}
        self.assertEqual(s.digest(unsigned), self.real['content_sha256'])

    def test_rerun_is_deterministic(self):
        self.assertTrue(s.exact_equal(self.real, s.run_study()))
        self.assertTrue(s.exact_equal(self.synthetic, f.run_fixtures()))

    def test_output_path_cannot_escape_owned_directory(self):
        with self.assertRaises(ValueError):
            s.write_json(s.OWNED.parent / 'forbidden-spatial-output.json', {'must_not_write': True})


if __name__ == '__main__':
    unittest.main(verbosity=2)
