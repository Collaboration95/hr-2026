import json
from pathlib import Path
import tempfile
import unittest
import numpy as np
from engine.codecs import CANDIDATES, encode_store
from engine.indexed import CompactWindowReader, SourceWindowReader, evaluate_reader
from engine.model import Dataset
from engine.oracle import oracle_evaluate
from engine.query import evaluate
from engine.source import load_plots, load_source
from engine.synthetic import rectangle

class IndexedTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.source = load_source()
        cls.plots = load_plots()
        cls.tmp = tempfile.TemporaryDirectory()
        cls.store = Path(cls.tmp.name) / 'store'
        encode_store(cls.source.bands, cls.source.masks, cls.source.metadata, cls.store, 'separate_zstd', 128)

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def test_all_real_plots_both_readers_and_independent_oracle(self):
        with SourceWindowReader() as source, CompactWindowReader(self.store) as compact:
            for plot in self.plots:
                expected = oracle_evaluate(self.source, plot['geometry'])
                self.assertEqual(evaluate_reader(source, plot['geometry']), expected)
                self.assertEqual(evaluate_reader(compact, plot['geometry']), expected)

    def test_decimal_window_origin_witness_keeps_original_lattice(self):
        # Original x0+(col+.5)*a != (x0+col*a)+.5*a at native row1,col1.
        a, _, x0, _, e, y0 = self.source.metadata['transform']
        x, y = x0+1.5*a, y0+1.5*e
        self.assertNotEqual(x, (x0+a)+.5*a)
        geometry = rectangle(x, y-.00001, x+.00001, y+.00001)
        expected = oracle_evaluate(self.source, geometry)
        self.assertEqual(expected['selected_cell_count'], 1)
        with SourceWindowReader() as source, CompactWindowReader(self.store) as compact:
            self.assertEqual(evaluate_reader(source, geometry), expected)
            self.assertEqual(evaluate_reader(compact, geometry), expected)

    def test_partial_and_fully_outside_and_missing_band(self):
        a, _, x0, _, e, y0 = self.source.metadata['transform']
        cases = [rectangle(x0-a, y0+e*2, x0+a, y0),
                 rectangle(x0-a*3, y0+e*2, x0-a*2, y0),
                 rectangle(x0+.01*a, y0+.1*e, x0+.1*a, y0+.01*e)]
        with SourceWindowReader() as source, CompactWindowReader(self.store) as compact:
            for geometry in cases:
                for missing in ((), ('lossyear',), ('datamask',)):
                    expected = oracle_evaluate(self.source, geometry, missing)
                    self.assertEqual(evaluate_reader(source, geometry, missing), expected)
                    self.assertEqual(evaluate_reader(compact, geometry, missing), expected)

    def test_closed_source_reader_fails(self):
        reader = SourceWindowReader()
        reader.close()
        reader.close()
        with self.assertRaises(ValueError):
            reader.read_window(0, 1, 0, 1)

    def test_queries_read_only_the_selected_bbox(self):
        class RecordingReader:
            metadata = self.source.metadata
            windows = []
            def read_window(inner, r0, r1, c0, c1):
                inner.windows.append((r0, r1, c0, c1))
                return self.source.bands[:,r0:r1,c0:c1], self.source.masks[:,r0:r1,c0:c1]
        reader = RecordingReader()
        result = evaluate_reader(reader, self.plots[1]['geometry'])
        self.assertEqual(result, evaluate(self.source, self.plots[1]['geometry']))
        self.assertEqual(len(reader.windows), 1)
        r0,r1,c0,c1 = reader.windows[0]
        self.assertLess((r1-r0)*(c1-c0), 1000)

if __name__ == '__main__':
    unittest.main()
