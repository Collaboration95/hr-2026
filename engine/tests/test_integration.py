"""Contract, input preservation, export evidence and receipts integration gates."""
import csv
import json
from pathlib import Path
import tempfile
import unittest
from engine.export import export, differing_fields
from engine.source import ROOT, SAMPLE, CSV_NAME, GEOJSON_NAME, load_plots, object_hash

class IntegrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.artifact = export(output=Path(cls.tmp.name) / 'demo-v1.json', include_benchmark=False)

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def test_exact_source_join_preserved(self):
        with (ROOT / SAMPLE / CSV_NAME).open(newline='', encoding='utf-8-sig') as stream:
            rows = list(csv.DictReader(stream))
        features = json.loads((ROOT / SAMPLE / GEOJSON_NAME).read_text())['features']
        originals = {f['properties']['ProductionPlace']: f['geometry'] for f in features}
        self.assertEqual(len(self.artifact['plots']), 17)
        for row, plot in zip(rows, self.artifact['plots']):
            self.assertEqual(row, plot['supplier'])
            self.assertEqual(originals[row['a3_plot_id']], plot['geometry'])

    def test_review_leads_not_all_rows(self):
        self.assertEqual(self.artifact['summary']['supplier_indication_count'], 5)

    def test_receipts_bind_inputs(self):
        for plot in self.artifact['plots']:
            receipt = dict(plot['receipt'])
            claimed = receipt.pop('receipt_sha256')
            self.assertEqual(claimed, object_hash(receipt))
            self.assertEqual(receipt['geometry_sha256'], object_hash(plot['geometry']))
            self.assertEqual(receipt['supplier_row_sha256'], object_hash(plot['supplier']))
            self.assertEqual(plot['comparison']['source_result_sha256'], object_hash(plot['source_result']))
        value = dict(self.artifact)
        claimed = value.pop('content_sha256')
        self.assertEqual(claimed, object_hash(value))

    def test_map_evidence_independently_reduces_to_result(self):
        for plot in self.artifact['plots']:
            result = plot['source_result']
            cells = [f['properties'] for f in plot['evidence']['features']]
            self.assertEqual(result['selected_cell_count'], len(cells))
            valid = [c for c in cells if c['valid_land']]
            self.assertEqual(result['valid_land_cell_count'], len(valid))
            self.assertEqual(result['canopy_histogram'], [sum(c['treecover2000'] == n for c in valid) for n in range(101)])
            self.assertEqual(result['lossyear_histogram'], [sum(c['lossyear'] == n for c in valid) for n in range(26)])

    def test_pending_is_not_equal_or_mismatch(self):
        self.assertIsNone(self.artifact['summary']['exact_match_count'])
        for plot in self.artifact['plots']:
            self.assertIsNone(plot['compact_result'])
            self.assertIsNone(plot['comparison']['equal'])
            self.assertEqual(plot['comparison']['status'], 'pending_codec')

    def test_difference_paths_preserve_type_distinctions(self):
        self.assertEqual(differing_fields({'a': [False]}, {'a': [0]}), ['a[0]'])
        self.assertEqual(differing_fields({'a': None}, {'a': False}), ['a'])
        self.assertEqual(differing_fields({'a': 1}, {}), ['a'])

    def test_deterministic_export(self):
        second = export(output=Path(self.tmp.name) / 'second.json', include_benchmark=False)
        self.assertEqual(self.artifact, second)

if __name__ == '__main__':
    unittest.main()
