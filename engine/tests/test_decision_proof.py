"""Independent original-layers path and fidelity proof for the decision contracts."""
import contextlib
import io
import json
import math
from pathlib import Path
import random
import sys
import tempfile
import types
import unittest
from unittest import mock

import numpy as np

from engine import decision as D
from engine import decision_original as O
from engine import decision_proof as P
from engine.jrc import JrcDataset, load_jrc
from engine.model import Dataset
from engine.query import select_cells
from engine.source import canonical_bytes, load_plots, load_source

SCREEN, DECISION = D.SCREEN_VERSION, D.DECISION_VERSION


def hansen_ds(loss, datamask, masks=None):
    """Hansen-like dataset on a 3-unit lattice; masks is [3,h,w] (treecover, lossyear, datamask)."""
    loss, datamask = np.array(loss, np.uint8), np.array(datamask, np.uint8)
    h, w = loss.shape
    bands = np.stack([np.full((h, w), 50, np.uint8), loss, datamask])
    valid = np.ones(bands.shape, bool) if masks is None else masks
    return Dataset(bands, valid, {'shape': [h, w], 'transform': [3.0, 0.0, 0.0, 0.0, -3.0, 3.0 * h],
                                  'crs': 'EPSG:4326'}).validate()


def jrc_ds(forest, valid=None, trim_left=0, trim_bottom=0):
    """JRC lattice nesting the Hansen one 3:1; non-centre cells are random so a wrong lookup shows."""
    forest = np.array(forest, np.uint8)
    h, w = forest.shape
    values = np.random.default_rng(7).integers(0, 2, (3 * h, 3 * w)).astype(np.uint8)
    values[1::3, 1::3] = forest
    mask = np.ones(values.shape, bool)
    if valid is not None:
        mask[1::3, 1::3] = np.array(valid, bool)
    rows = 3 * h - trim_bottom
    values, mask = values[:rows, trim_left:].copy(), mask[:rows, trim_left:].copy()
    return JrcDataset(values, mask, {'shape': list(values.shape), 'transform': [1.0, 0.0, float(trim_left), 0.0, -1.0, 3.0 * h],
                                     'crs': 'EPSG:4326'}).validate()


def box(x0, y0, x1, y1):
    return {'type': 'Polygon', 'coordinates': [[[x0, y0], [x1, y0], [x1, y1], [x0, y1], [x0, y0]]]}


def cover(hansen, extra_cols=0):
    h, w = hansen.metadata['shape']
    return box(0, 0, 3 * (w + extra_cols), 3 * h)


def same(a, b):
    return canonical_bytes(a) == canonical_bytes(b)


class SyntheticTests(unittest.TestCase):
    def check(self, hansen, jrc, geometry):
        """Original path equals the decision module on both levels and every cell; returns outputs."""
        screen = D.derive_screen_codes(hansen, jrc)
        derived = {SCREEN: screen, DECISION: D.project_decision(screen)}
        out = {}
        for level, codes in derived.items():
            self.assertTrue(np.array_equal(O.exhaustive_attribute_codes(hansen, jrc, level), codes), level)
            out[level] = O.evaluate_original(hansen, jrc, geometry, level)
            self.assertTrue(same(out[level], D.evaluate_codes(codes, hansen.metadata, geometry, level)), level)
        return out

    def test_water_nodata_and_mask_invalid(self):
        masks = np.ones((3, 1, 6), bool)
        masks[1, 0, 3] = masks[2, 0, 4] = masks[0, 0, 5] = False
        hansen = hansen_ds([[0, 23, 22, 22, 22, 0]], [[1, 2, 0, 1, 1, 1]], masks)
        out = self.check(hansen, jrc_ds([[1] * 6]), cover(hansen))[SCREEN]
        # the treecover2000 mask counts too (v1's known_bands): cells 2, 3, 4, 5 are unknown, only cell 0 is land
        self.assertEqual((out['selected_cell_count'], out['valid_land_cell_count'], out['water_cell_count'],
                          out['unknown_cell_count']), (6, 1, 1, 4))
        self.assertEqual(out['forest_2020'], {'cell_counts': {'nonforest': 0, 'forest': 1, 'unknown': 0}, 'present': True})
        self.assertEqual(out['hansen_loss_after_2020']['yearly_cell_counts']['2022'], 0)  # unknown and water loss ignored
        self.assertIsNone(out['deforestation_after_2020']['present'])  # three unknown cells could hide loss
        self.assertEqual(out['support'], 'partial')

    def test_any_invalid_band_mask_makes_a_cell_unknown_in_both_paths(self):
        for band in range(3):
            masks = np.ones((3, 1, 3), bool)
            masks[band, 0, 1] = False
            hansen = hansen_ds([[0, 22, 0]], [[1, 1, 1]], masks)
            self.assertEqual(D.derive_screen_codes(hansen, jrc_ds([[1, 1, 1]])).tolist()[0][1], D.UNKNOWN, band)
            out = self.check(hansen, jrc_ds([[1, 1, 1]]), cover(hansen))[SCREEN]
            self.assertEqual((out['valid_land_cell_count'], out['unknown_cell_count']), (2, 1), band)
            self.assertEqual(out['deforestation_after_2020']['yearly_cell_counts']['2022'], 0, band)  # loss on the unknown cell

    def test_out_of_range_values_on_valid_cells_are_refused_but_invalid_cells_are_not_read(self):
        jrc = jrc_ds([[1, 1, 1]])
        for loss, datamask in (([[0, 26, 0]], [[1, 1, 1]]), ([[0, 0, 0]], [[1, 3, 1]]), ([[0, 255, 0]], [[1, 1, 1]])):
            hansen = hansen_ds([[0, 0, 0]], [[1, 1, 1]])
            hansen.bands[1], hansen.bands[2] = np.array(loss, np.uint8), np.array(datamask, np.uint8)
            with self.subTest(loss=loss, datamask=datamask):
                with self.assertRaises(ValueError):
                    D.derive_screen_codes(hansen, jrc)
                with self.assertRaises(ValueError):
                    O.exhaustive_attribute_codes(hansen, jrc, SCREEN)
                for band in range(3):  # the same value under an invalid mask is never read, in either path
                    masked = np.ones((3, 1, 3), bool)
                    masked[band, 0, 1] = False
                    ok = Dataset(hansen.bands, masked, hansen.metadata)
                    self.assertEqual(D.derive_screen_codes(ok, jrc)[0, 1], D.UNKNOWN)
                    self.assertTrue(np.array_equal(O.exhaustive_attribute_codes(ok, jrc, SCREEN), D.derive_screen_codes(ok, jrc)))

    def test_pre_cutoff_loss_on_jrc_forest_stays_forest(self):
        hansen = hansen_ds([[5, 15, 20, 21]], [[1, 1, 1, 1]])
        out = self.check(hansen, jrc_ds([[1, 1, 1, 1]]), cover(hansen))[DECISION]
        self.assertEqual(out['forest_2020']['cell_counts'], {'nonforest': 0, 'forest': 4, 'unknown': 0})
        self.assertEqual(out['deforestation_after_2020']['cell_count'], 1)  # only the 2021 loss

    def test_jrc_outside_chip_is_unknown(self):
        hansen = hansen_ds([[0, 22, 0], [0, 0, 24]], [[1, 1, 1], [1, 1, 1]])
        jrc = jrc_ds([[1, 1, 1], [1, 1, 1]], trim_left=3, trim_bottom=3)
        out = self.check(hansen, jrc, cover(hansen))[SCREEN]
        self.assertEqual(out['forest_2020']['cell_counts'], {'nonforest': 0, 'forest': 2, 'unknown': 4})
        self.assertEqual(out['deforestation_after_2020']['yearly_cell_counts']['2022'], 1)
        self.assertEqual(out['deforestation_after_2020']['yearly_cell_counts']['2024'], 0)  # unknown-forest loss is not deforestation
        self.assertEqual(out['hansen_loss_after_2020']['yearly_cell_counts']['2024'], 1)
        self.assertIs(out['deforestation_after_2020']['present'], True)
        self.assertEqual(out['support'], 'partial')  # JRC class unknown on 4 land cells

    def test_jrc_mask_invalid_unknown_and_zero_is_nonforest(self):
        hansen = hansen_ds([[0, 22, 0, 0]], [[1, 1, 1, 1]])
        out = self.check(hansen, jrc_ds([[1, 1, 0, 1]], [[True, False, True, True]]), cover(hansen))[SCREEN]
        self.assertEqual(out['forest_2020']['cell_counts'], {'nonforest': 1, 'forest': 2, 'unknown': 1})
        self.assertEqual(out['deforestation_after_2020']['cell_count'], 0)
        self.assertIsNone(out['deforestation_after_2020']['present'])

    def test_forest_unknown_with_loss_makes_deforestation_none(self):
        hansen = hansen_ds([[0, 0, 23]], [[1, 1, 1]])
        jrc = jrc_ds([[1, 1, 1]], [[True, True, False]])
        for level, out in self.check(hansen, jrc, cover(hansen)).items():
            self.assertIsNone(out['deforestation_after_2020']['present'], level)
            self.assertIs(out['forest_2020']['present'], True)
        screen = self.check(hansen, jrc, cover(hansen))[SCREEN]
        self.assertIs(screen['hansen_loss_after_2020']['periods']['2021-2023']['mapped_loss_present'], True)
        hansen = hansen_ds([[22, 0, 23]], [[1, 1, 1]])
        for level, out in self.check(hansen, jrc, cover(hansen)).items():
            self.assertIs(out['deforestation_after_2020']['present'], True, level)

    def test_decision_level_drops_nonforest_loss(self):
        hansen = hansen_ds([[23, 24, 15, 0]], [[1, 1, 1, 1]])
        jrc = jrc_ds([[0, 1, 0, 1]])
        out = self.check(hansen, jrc, cover(hansen))
        screen, decision = out[SCREEN], out[DECISION]
        self.assertEqual({k: v for k, v in screen['hansen_loss_after_2020']['yearly_cell_counts'].items() if v}, {'2023': 1, '2024': 1})
        self.assertNotIn('hansen_loss_after_2020', decision)
        self.assertEqual(screen['deforestation_after_2020'], decision['deforestation_after_2020'])
        self.assertEqual(decision['deforestation_after_2020']['cell_count'], 1)
        # nonforest 0, forest 1: 2 + 6*state + (year - 2020); 2015 is before the cut-off
        self.assertEqual(O.exhaustive_attribute_codes(hansen, jrc, SCREEN).tolist(), [[5, 12, 2, 8]])
        self.assertEqual(O.exhaustive_attribute_codes(hansen, jrc, DECISION).tolist(), [[2, 12, 2, 8]])

    def test_partial_out_of_chip_support(self):
        for loss, flag in (([[0, 0, 0]], None), ([[0, 22, 0]], True)):
            hansen = hansen_ds(loss, [[1, 1, 1]])
            out = self.check(hansen, jrc_ds([[1, 1, 1]]), cover(hansen, extra_cols=1))[SCREEN]
            self.assertEqual((out['selected_cell_count'], out['out_of_coverage_cell_count'], out['unknown_cell_count']), (4, 1, 1))
            self.assertEqual(out['support'], 'partial')
            self.assertIs(out['deforestation_after_2020']['present'], flag)

    def test_empty_all_outside_and_water_only_selections(self):
        hansen = hansen_ds([[0, 0, 0]], [[1, 1, 1]])
        jrc = jrc_ds([[1, 1, 1]])
        empty = self.check(hansen, jrc, box(.1, .1, 1.2, 1.2))
        for level, out in empty.items():
            self.assertEqual(out['selected_cell_count'], 0, level)
            self.assertEqual(out['support'], 'none')
            self.assertIsNone(out['forest_2020']['cell_counts'])
            self.assertIsNone(out['forest_2020']['present'])
            self.assertIsNone(out['deforestation_after_2020']['cell_count'])
        outside = self.check(hansen, jrc, box(30, 0, 33, 3))[SCREEN]
        self.assertEqual((outside['selected_cell_count'], outside['out_of_coverage_cell_count'], outside['unknown_cell_count']), (1, 1, 1))
        self.assertEqual(outside['support'], 'none')
        wet = hansen_ds([[0, 22]], [[2, 2]])
        water = self.check(wet, jrc_ds([[1, 1]]), cover(wet))[SCREEN]
        self.assertEqual((water['water_cell_count'], water['valid_land_cell_count'], water['support']), (2, 0, 'none'))
        self.assertIsNone(water['hansen_loss_after_2020']['periods']['2021-2023']['observed_loss_cell_count'])

    def test_float_lookup_matches_integer_offsets(self):
        hansen = hansen_ds([[0] * 5] * 4, [[1] * 5] * 4)
        for trim in (0, 2, 3):
            jrc = jrc_ds([[1] * 5] * 4, trim_left=trim)
            k, row_offset, col_offset = D.nested_offsets(hansen.metadata, jrc.metadata)
            rows, cols = np.meshgrid(np.arange(4), np.arange(5), indexing='ij')
            attrs = O.cell_attributes(hansen, jrc, rows, cols)
            expected_row, expected_col = k * rows + row_offset, k * cols + col_offset
            inside = ((expected_row >= 0) & (expected_row < jrc.values.shape[0])
                      & (expected_col >= 0) & (expected_col < jrc.values.shape[1]))
            self.assertTrue(np.array_equal(attrs['jrc_row'], np.where(inside, expected_row, -1)))
            self.assertTrue(np.array_equal(attrs['jrc_col'], np.where(inside, expected_col, -1)))
            self.assertEqual(int(inside.sum()), 4 * (5 - max(0, math.ceil((trim - 1) / 3))))

    def test_random_datasets_and_polygons_agree(self):
        rng, polygons = random.Random(11), 0
        seen = set()
        for trial in range(6):
            h, w = rng.randint(3, 7), rng.randint(3, 8)
            loss = [[rng.choice((0, 0, 0, 15, 20, 21, 22, 23, 24, 25)) for _ in range(w)] for _ in range(h)]
            datamask = [[rng.choices((0, 1, 2), (1, 7, 2))[0] for _ in range(w)] for _ in range(h)]
            masks = np.array([[[rng.random() < .93 for _ in range(w)] for _ in range(h)] for _ in range(3)])
            forest = [[rng.randint(0, 1) for _ in range(w)] for _ in range(h)]
            valid = [[rng.random() < .9 for _ in range(w)] for _ in range(h)]
            hansen = hansen_ds(loss, datamask, masks)
            jrc = jrc_ds(forest, valid, trim_left=rng.choice((0, 0, 1, 3)), trim_bottom=rng.choice((0, 0, 1, 3)))
            screen = D.derive_screen_codes(hansen, jrc)
            for level, codes in ((SCREEN, screen), (DECISION, D.project_decision(screen))):
                self.assertTrue(np.array_equal(O.exhaustive_attribute_codes(hansen, jrc, level), codes))
                for _ in range(40):
                    x0, y0 = rng.uniform(-4, 3 * w), rng.uniform(-4, 3 * h)
                    x1, y1 = x0 + rng.uniform(.2, 14), y0 + rng.uniform(.2, 14)
                    if rng.random() < .5:  # edges through exact centres
                        x0, x1, y0, y1 = (math.floor(v / 3) * 3 + 1.5 for v in (x0, x1, y0, y1))
                        if x1 <= x0 or y1 <= y0:
                            continue
                    geometry = box(x0, y0, x1, y1)
                    got, want = D.evaluate_codes(codes, hansen.metadata, geometry, level), O.evaluate_original(hansen, jrc, geometry, level)
                    self.assertTrue(same(got, want))
                    polygons += 1
                    seen.update([('forest', want['forest_2020']['present']), ('defor', want['deforestation_after_2020']['present']),
                                 ('support', want['support'])])
        self.assertGreater(polygons, 300)
        self.assertTrue({('forest', True), ('forest', None), ('defor', None), ('support', 'partial'), ('support', 'none')} <= seen)

    def test_refusals(self):
        hansen = hansen_ds([[0]], [[1]])
        jrc = jrc_ds([[1]])
        with self.assertRaises(ValueError):
            O.evaluate_original(hansen, jrc, cover(hansen), 'eudr-bogus.v1')
        with self.assertRaises(ValueError):
            O.exhaustive_attribute_codes(hansen, jrc, 'eudr-bogus.v1')
        with self.assertRaises(ValueError):
            O.cell_attributes(hansen, jrc, [0], [1])
        with self.assertRaises(ValueError):
            O.evaluate_original(hansen, jrc, {'type': 'Point', 'coordinates': [0, 0]})

    def test_nested_offsets_refuses_even_ratio_and_misaligned_origin(self):
        def meta(size, x0=0.0, y0=0.0):
            return {'transform': [size, 0.0, x0, 0.0, -size, y0], 'crs': 'EPSG:4326'}
        self.assertEqual(D.nested_offsets(meta(3.0, 3.0, 9.0), meta(1.0, 0.0, 9.0)), (3, 1, 4))
        with self.assertRaisesRegex(ValueError, 'odd integer ratio'):
            D.nested_offsets(meta(4.0), meta(1.0))
        with self.assertRaisesRegex(ValueError, 'odd integer ratio'):
            D.nested_offsets(meta(3.0), meta(2.0))
        with self.assertRaisesRegex(ValueError, 'not aligned'):
            D.nested_offsets(meta(3.0, .5, 9.0), meta(1.0, 0.0, 9.0))
        with self.assertRaisesRegex(ValueError, 'not aligned'):
            D.nested_offsets(meta(3.0, 0.0, 9.4), meta(1.0, 0.0, 9.0))
        with self.assertRaisesRegex(ValueError, 'same CRS'):
            D.nested_offsets(meta(3.0), {**meta(1.0), 'crs': 'EPSG:3857'})


class RealDataTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.hansen, cls.jrc, cls.plots = load_source(), load_jrc(), load_plots()
        cls.screen = D.derive_screen_codes(cls.hansen, cls.jrc)
        cls.derived = {SCREEN: cls.screen, DECISION: D.project_decision(cls.screen)}

    def test_exhaustive_cells_equal_for_both_levels(self):
        for level, codes in self.derived.items():
            original = O.exhaustive_attribute_codes(self.hansen, self.jrc, level)
            self.assertEqual(original.size, 744_732)
            self.assertEqual(int((original != codes).sum()), 0, level)

    def test_float_lookup_matches_nested_offsets_on_real_grids(self):
        k, row_offset, col_offset = D.nested_offsets(self.hansen.metadata, self.jrc.metadata)
        rows, cols = np.meshgrid(np.arange(604), np.arange(1233), indexing='ij')
        attrs = O.cell_attributes(self.hansen, self.jrc, rows, cols)
        expected_row, expected_col = k * rows + row_offset, k * cols + col_offset
        inside = (expected_row >= 0) & (expected_row < 1809) & (expected_col >= 0) & (expected_col < 3695)
        self.assertTrue(np.array_equal(attrs['jrc_row'], np.where(inside, expected_row, -1)))
        self.assertTrue(np.array_equal(attrs['jrc_col'], np.where(inside, expected_col, -1)))
        # Hansen col 0, col 1232 and row 603 centres lie outside the JRC chip, so their forest state is unknown.
        for edge in (attrs['forest'][:, 0], attrs['forest'][:, 1232], attrs['forest'][603, :]):
            self.assertTrue((edge == 'unknown').all())

    def test_17_plots_full_dict_equality_on_both_levels(self):
        self.assertEqual(len(self.plots), 17)
        for plot in self.plots:
            for level, codes in self.derived.items():
                with self.subTest(plot=plot['plot_id'], level=level):
                    want = O.evaluate_original(self.hansen, self.jrc, plot['geometry'], level)
                    self.assertTrue(same(want, D.evaluate_codes(codes, self.hansen.metadata, plot['geometry'], level)))

    def test_p0001_known_values(self):
        geometry = self.plots[0]['geometry']
        self.assertEqual(self.plots[0]['plot_id'], 'P-0001')
        screen = O.evaluate_original(self.hansen, self.jrc, geometry, SCREEN)
        decision = O.evaluate_original(self.hansen, self.jrc, geometry, DECISION)
        self.assertEqual(screen['deforestation_after_2020']['cell_count'], 2)
        self.assertEqual(decision['deforestation_after_2020']['cell_count'], 2)
        self.assertEqual(screen['hansen_loss_after_2020']['periods']['2021-2023']['observed_loss_cell_count'], 38)
        self.assertEqual(screen['hansen_loss_after_2020']['yearly_cell_counts']['2022'], 38)

    def test_v1_crosscheck_equal(self):
        outputs = {(SCREEN, p['plot_id']): O.evaluate_original(self.hansen, self.jrc, p['geometry'], SCREEN) for p in self.plots}
        check = P.v1_crosscheck(self.hansen, self.plots, outputs)
        self.assertTrue(check['equal'] and check['accounting_equal'])
        self.assertEqual(check['plots'], 17)

    def test_fuzz_is_deterministic_and_exercises_branches(self):
        first = P.fuzz(self.hansen, self.jrc, self.derived, {l: (None, {}) for l in self.derived}, 400, seed=3)
        again = P.fuzz(self.hansen, self.jrc, self.derived, {l: (None, {}) for l in self.derived}, 400, seed=3)
        other = P.fuzz(self.hansen, self.jrc, self.derived, {l: (None, {}) for l in self.derived}, 400, seed=4)
        self.assertEqual(first['output_digest_sha256'], again['output_digest_sha256'])
        self.assertNotEqual(first['geometry_set_sha256'], other['geometry_set_sha256'])
        self.assertEqual((first['generated'], first['mismatch_count']), (400, 0))
        self.assertEqual(first['compared'] + first['rejected_invalid'], 400)
        self.assertEqual(first['equal'], first['compared'])
        self.assertEqual(set(first['rejected_by_category']), {'invalid'})
        labels = first['branch_coverage'][SCREEN]
        for label in ('selected=0', 'selected=1', 'outside>0', 'water>0', 'forest_unknown>0', 'support=partial'):
            self.assertGreater(labels.get(label, 0), 0, label)

    def test_build_proof_passes_with_small_fuzz(self):
        proof = P.build_proof(fuzz_count=200)
        self.assertTrue(proof['summary']['all_pass'], proof['summary']['checks'])
        self.assertEqual(proof['summary']['cells_compared'], 744_732)
        for level in D.LEVELS:
            self.assertEqual(proof['exhaustive_cell_proof'][level]['original_vs_derived']['mismatches'], 0)
            self.assertEqual(proof['plot_proof'][level]['equal_derived'], 17)
            self.assertTrue(all(len(p['output_sha256']) == 64 for p in proof['plot_proof'][level]['plots']))
        controls = proof['negative_controls']
        self.assertEqual(controls['flipped_code']['levels'][SCREEN]['exhaustive_mismatches'], 1)
        self.assertTrue(controls['moved_vertex']['detected'] and controls['flipped_jrc_forest_bit']['detected'])
        self.assertTrue(controls['dropped_detail']['ignored_as_designed'])
        json.dumps(proof, allow_nan=False)

    def test_store_comparison_activates_and_detects_one_flipped_code(self):
        sizes = {}

        def reader_for(codes_by_name):
            module = types.ModuleType('engine.decision_store')
            grid = {k: self.hansen.metadata[k] for k in ('shape', 'transform', 'crs')}
            module.read_store = lambda path: (codes_by_name[Path(path).name].copy(),
                                              {**grid, 'level': SCREEN if 'screen' in Path(path).name else DECISION})
            return module

        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp) / 'artifacts/decision'
            folder.mkdir(parents=True)
            (folder / 'screen.plds').write_bytes(b'screen')
            (folder / 'decision.plds').write_bytes(b'decision')
            good = {'screen.plds': self.derived[SCREEN], 'decision.plds': self.derived[DECISION]}
            bad = {name: codes.copy() for name, codes in good.items()}
            rows, cols = select_cells(self.hansen.metadata, self.plots[0]['geometry'])
            row, col = int(rows[0]), int(cols[0])
            bad['screen.plds'][row, col] = 0 if self.screen[row, col] else 1
            affected = sum(any((r, c) == (row, col) for r, c in zip(*select_cells(self.hansen.metadata, p['geometry'])))
                           for p in self.plots)
            for label, store in (('good', good), ('bad', bad)):
                with mock.patch.dict(sys.modules, {'engine.decision_store': reader_for(store)}):
                    stores = P.decode_stores(tmp)
                self.assertEqual(stores[SCREEN][1]['status'], 'decoded')
                originals, cells = P.exhaustive(self.hansen, self.jrc, self.derived, stores)
                sizes[label] = cells[SCREEN]['original_vs_store']['mismatches'], cells[DECISION]['original_vs_store']['mismatches']
                plots, _ = P.plot_proof(self.hansen, self.jrc, self.plots, self.derived, stores)
                sizes[label + '_plots'] = plots[SCREEN]['equal_store']
        self.assertEqual(sizes['good'], (0, 0))
        self.assertEqual(sizes['bad'], (1, 0))
        self.assertEqual(sizes['good_plots'], 17)
        self.assertEqual(sizes['bad_plots'], 17 - affected)
        absent = P.decode_stores(Path(tempfile.gettempdir()) / 'no-such-root')
        self.assertTrue(all(info['status'] == 'file_absent' for _, info in absent.values()))

    def test_store_comparison_refuses_a_store_whose_header_names_the_other_level(self):
        header = {**{k: self.hansen.metadata[k] for k in ('shape', 'transform', 'crs')}, 'level': DECISION}
        decoded = {level: (self.derived[DECISION], {'status': 'decoded', 'header': header}) for level in (SCREEN, DECISION)}
        with self.assertRaisesRegex(ValueError, 'store holds'):
            P.plot_proof(self.hansen, self.jrc, self.plots[:1], self.derived, decoded)
        result = P.fuzz(self.hansen, self.jrc, self.derived, decoded, count=30)
        self.assertGreater(result['mismatch_count'], 0)  # a mislabelled store is a recorded mismatch, never silently equal

    def test_missing_store_fails_the_gate_unless_allowed(self):
        absent = {level: (None, {'path': path, 'status': 'file_absent'}) for level, path in P.STORES.items()}
        with mock.patch.object(P, 'decode_stores', return_value=absent):
            strict = P.build_proof(fuzz_count=20)
            lax = P.build_proof(fuzz_count=20, allow_missing_stores=True)
        self.assertFalse(strict['summary']['all_pass'])
        self.assertFalse(strict['summary']['checks']['stores_present_and_readable'])
        self.assertEqual([k for k, v in strict['summary']['checks'].items() if not v], ['stores_present_and_readable'])
        self.assertTrue(lax['summary']['all_pass'], lax['summary']['checks'])
        self.assertFalse(lax['summary']['store_comparison'])
        with mock.patch.object(P, 'build_proof', return_value=strict) as build, contextlib.redirect_stdout(io.StringIO()), \
                mock.patch.object(P.Path, 'write_text'), mock.patch.object(P.Path, 'mkdir'):
            self.assertEqual(P.main(['--fuzz', '5']), 1)
            self.assertFalse(build.call_args.kwargs['allow_missing_stores'])
            build.return_value = lax
            self.assertEqual(P.main(['--fuzz', '5', '--allow-missing-stores']), 0)
            self.assertTrue(build.call_args.kwargs['allow_missing_stores'])


if __name__ == '__main__':
    unittest.main()
