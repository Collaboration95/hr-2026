"""JRC native-grid source and independent query checks, separate from Hansen."""
import copy
import unittest
import numpy as np
from engine.jrc import JrcDataset, load_jrc, check_source_readback, evaluate_jrc, evidence_jrc
from engine.jrc_oracle import oracle_jrc
from engine.jrc_benchmark import pinned_plots


def fixture(values, mask=None, transform=None):
    v = np.array(values, dtype=np.uint8)
    m = np.ones_like(v, dtype=bool) if mask is None else np.array(mask, dtype=bool)
    return JrcDataset(v, m, {'shape': list(v.shape), 'transform': transform or [1, 0, 0, 0, -1, v.shape[0]],
                            'crs': 'EPSG:4326'}).validate()


def box(x0, y0, x1, y1):
    return {'type': 'Polygon', 'coordinates': [[[x0, y0], [x1, y0], [x1, y1], [x0, y1], [x0, y0]]]}


class JrcQueryTests(unittest.TestCase):
    def compare(self, ds, geom, missing=False):
        actual = evaluate_jrc(ds, geom, missing)
        self.assertEqual(actual, oracle_jrc(ds, geom, missing))
        return actual

    def test_all_source_pixels_masks_and_17_independent_plots(self):
        source = load_jrc()
        result = check_source_readback(dataset=source)
        self.assertEqual(result['pixel_count'], 6_684_255)
        self.assertTrue(result['raw_values_equal'] and result['masks_equal'])
        plots = pinned_plots()
        self.assertEqual(len(plots), 17)
        for plot in plots:
            with self.subTest(plot=plot['plot_id']): self.compare(source, plot['geometry'])

    def test_zero_is_valid_class_not_qml_alpha_nodata(self):
        ds = fixture([[0]])
        r = self.compare(ds, box(0, 0, 1, 1))
        self.assertEqual(r['class_counts'], {'0': 1, '1': 0})
        self.assertIs(r['mapped_forest_present'], False)
        self.assertEqual(r['support'], 'complete')
        real = load_jrc()
        self.assertEqual(real.metadata['class_styles']['0']['alpha'], '0')
        self.assertEqual(real.metadata['classes'], {'0': 'Non-forest', '1': 'Forest'})
        self.assertTrue(real.mask[real.values == 0].all())
        self.assertIn('2025', real.metadata['xml_observations']['revision_date'])
        self.assertEqual(real.metadata['publication_year'], 2026)
        self.assertEqual(real.metadata['reference_year'], 2020)

    def test_partial_positive_and_partial_absence(self):
        for value, expected in [(1, True), (0, None)]:
            r = self.compare(fixture([[value]]), box(-1, 0, 1, 1))
            self.assertEqual(r['selected_cell_count'], 2)
            self.assertEqual(r['unknown_cell_count'], 1)
            self.assertIs(r['mapped_forest_present'], expected)
            self.assertEqual(r['support'], 'partial')

    def test_invalid_mask_missing_band_outside_and_unknown_union(self):
        ds = fixture([[1, 0]], [[False, True]])
        r = self.compare(ds, box(-1, 0, 2, 1))
        self.assertEqual(r['unknown_cell_count'], 2)
        self.assertEqual(r['class_counts'], {'0': 1, '1': 0})
        self.assertIsNone(r['mapped_forest_present'])
        self.assertEqual(r['unknown_reasons'], ['out_of_coverage', 'band_mask_invalid'])
        missing = self.compare(ds, box(-1, 0, 2, 1), True)
        self.assertEqual(missing['unknown_cell_count'], 3)
        self.assertIsNone(missing['class_counts'])
        self.assertEqual(missing['support'], 'unavailable')
        self.assertEqual(missing['unknown_reasons'], ['out_of_coverage', 'band_mask_invalid', 'no_valid_cells', 'missing_band'])
        outside = self.compare(ds, box(-2, -2, -1, -1))
        self.assertEqual(outside['support'], 'none')
        self.assertIsNone(outside['class_counts'])
        cells = evidence_jrc(ds, box(-1, 0, 2, 1))
        self.assertEqual(cells[0], {'row': 0, 'col': -1, 'value': None, 'valid': False})
        self.assertEqual(cells[1], {'row': 0, 'col': 0, 'value': 1, 'valid': False})

    def test_tiny_empty_selection_and_holes_boundary_multipart(self):
        ds = fixture(np.zeros((3, 3), dtype=np.uint8))
        tiny = self.compare(ds, box(.01, .01, .1, .1))
        self.assertEqual(tiny['unknown_reasons'], ['no_selected_cells'])
        self.assertEqual(tiny['support'], 'none')
        outer = box(0, 0, 3, 3)
        outer['coordinates'].append(box(.5, .5, 2.5, 2.5)['coordinates'][0])
        result = self.compare(ds, outer)
        self.assertEqual(result['selected_cell_count'], 8)  # hole boundary covered; interior excluded
        multipart = {'type': 'MultiPolygon', 'coordinates': [box(0, 0, 1, 1)['coordinates'], box(2, 2, 3, 3)['coordinates']]}
        self.assertEqual(self.compare(ds, multipart)['selected_cell_count'], 2)

    def test_decimal_boundary_uses_original_chip_lattice(self):
        ds = fixture([[0, 1], [1, 0]], transform=[1/12000, 0, 98.77241666666667, 0, -1/12000, 8.581916666666666])
        a, _, c, _, e, f = ds.metadata['transform']
        x, y = c + 1.5*a, f + 1.5*e
        r = self.compare(ds, box(x, y-abs(e)/8, x+a/8, y+abs(e)/8))
        self.assertEqual(r['selected_cell_count'], 1)
        # No epsilon/tolerance expands coverage by one representable step.
        r = self.compare(ds, box(np.nextafter(x, np.inf).item(), y-abs(e)/8, x+a/8, y+abs(e)/8))
        self.assertEqual(r['selected_cell_count'], 0)

    def test_seeded_random_unknown_states(self):
        rng = np.random.default_rng(20261013)
        for i in range(80):
            ds = fixture(rng.integers(0, 2, (5, 7)), rng.random((5, 7)) > .2)
            xs, ys = sorted(rng.uniform(-2, 9, 2)), sorted(rng.uniform(-2, 7, 2))
            with self.subTest(case=i): self.compare(ds, box(xs[0], ys[0], xs[1], ys[1]), i % 9 == 0)

    def test_invalid_geometry_and_raw_values(self):
        ds = fixture([[0]])
        for g in ({'type': 'Point', 'coordinates': [0, 0]},
                  {'type': 'Polygon', 'coordinates': [[[0, 0], [1, 1], [1, 0], [0, 1], [0, 0]]]},
                  {'type': 'Polygon', 'coordinates': [[[0, 0], [1, 0], [1, 1], [0, 1]]]}):
            with self.subTest(g=g), self.assertRaises(ValueError): evaluate_jrc(ds, g)
            with self.assertRaises(ValueError): oracle_jrc(ds, g)
        bad = fixture([[0]], [[False]])
        bad.values[0, 0] = 2
        with self.assertRaises(ValueError): bad.validate()
        for md in (None, {'shape': [True, 1]}, {'shape': [1., 1]},
                   {'shape': [1, 1], 'transform': [10**1000, 0, 0, 0, -1, 1], 'crs': 'EPSG:4326'}):
            bad = fixture([[0]])
            bad.metadata = md
            with self.assertRaises(ValueError): bad.validate()


if __name__ == '__main__': unittest.main()
