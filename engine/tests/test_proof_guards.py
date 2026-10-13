"""Reject rehashed but semantically false proofs, including off-plot mutations."""
from copy import deepcopy
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from engine.codecs import encode_store
from engine.export import export
from engine.source import load_source, object_hash, sha256_file
from engine.verify import verify_artifact
import engine.export as exporter


def resign(value):
    for plot in value['plots']:
        receipt = plot['receipt']
        receipt['receipt_sha256'] = object_hash({k: v for k, v in receipt.items() if k != 'receipt_sha256'})
    value['content_sha256'] = object_hash({k: v for k, v in value.items() if k != 'content_sha256'})

class ProofGuards(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.root = Path(cls.tmp.name)
        cls.source = load_source()
        cls.store = cls.root / 'valid-store'
        encode_store(cls.source.bands, cls.source.masks, cls.source.metadata, cls.store, 'separate_zstd', 128)
        cls.base = export(cls.store, cls.root/'valid.json', include_benchmark=False)

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def verify(self, value):
        resign(value)
        path = self.root/'case.json'
        path.write_text(json.dumps(value))
        return verify_artifact(path)

    def test_untampered_proof_passes_without_benchmark_claims(self):
        self.assertTrue(self.verify(deepcopy(self.base))['valid'])

    def test_rehashed_receipt_contract_cannot_change(self):
        for key, wrong in [('query_version','wrong.v99'), ('observed_periods',{'2021-2023':[2099,2099]}),
                           ('boundary_rule','all touched'), ('supplier_sources',[]), ('sources',[]),
                           ('partial_support_rule','unknown means false')]:
            with self.subTest(key=key):
                value = deepcopy(self.base)
                value['plots'][0]['receipt'][key] = wrong
                result = self.verify(value)
                self.assertFalse(result['valid'])
                self.assertTrue(any('receipt contract' in s for s in result['failures']))

    def test_rehashed_summary_and_periods_cannot_change(self):
        for key in ('selected_cell_count_sum','exact_match_count','supplier_indication_count'):
            value = deepcopy(self.base)
            value['summary'][key] = -1
            self.assertIn('derived summary',self.verify(value)['failures'])
        value = deepcopy(self.base)
        value['periods']['2021-2023']['start_year'] = 2099
        self.assertIn('period envelope',self.verify(value)['failures'])

    def test_all_receipts_validate_store_claims_not_only_first_cache_entry(self):
        value = deepcopy(self.base)
        value['plots'][-1]['receipt']['compact_store']['files'][0]['bytes'] = 1
        self.assertFalse(self.verify(value)['valid'])

    def test_offplot_pixels_and_masks_cannot_fake_full_fidelity(self):
        selected = {(f['properties']['row'],f['properties']['col']) for p in self.base['plots'] for f in p['evidence']['features']}
        self.assertNotIn((0,0),selected)
        for change in ('raw','mask'):
            bands, masks = self.source.bands.copy(), self.source.masks.copy()
            if change == 'raw':
                bands[0,0,0] = (int(bands[0,0,0])+1)%101
            else:
                masks[0,0,0] = not masks[0,0,0]
            store = self.root / ('bad-'+change)
            encode_store(bands,masks,self.source.metadata,store,'separate_zstd',128)
            value = deepcopy(self.base)
            files = [{'path':p.name,'bytes':p.stat().st_size,'sha256':sha256_file(p)} for p in sorted(store.iterdir())]
            for plot in value['plots']:
                plot['receipt']['compact_store'].update(path=str(store),files=files)
            result = self.verify(value)
            self.assertFalse(result['valid'])
            self.assertTrue(any('full raw-value fidelity' in x if change=='raw' else 'full band-mask fidelity' in x for x in result['failures']))
            with self.assertRaisesRegex(ValueError,'full raw-value or mask fidelity'):
                export(store,self.root/'rejected.json',include_benchmark=False)

    def test_forged_benchmark_rejected_in_verifier_and_exporter(self):
        wrong = {'schema_version':'plotline.benchmark.v1','identity':{'query_version':'hansen-centers.v1',
                 'source_metadata':{'product':'FALSE VINTAGE'}}}
        value = deepcopy(self.base)
        value['benchmark'] = wrong
        value['benchmark_status'] = {'state':'bound_retained'}
        self.assertTrue(any('unbound benchmark: source metadata' in x for x in self.verify(value)['failures']))
        root = self.root/'fake-export-root'
        (root/'artifacts').mkdir(parents=True,exist_ok=True)
        (root/'artifacts/benchmark-v1.json').write_text(json.dumps(wrong))
        with patch.object(exporter,'ROOT',root):
            with self.assertRaisesRegex(ValueError,'unbound benchmark: source metadata'):
                exporter.export(self.store,root/'must-not-exist.json')
        self.assertFalse((root/'must-not-exist.json').exists())

    def test_pending_comparison_cannot_invent_hash(self):
        value = export(output=self.root/'pending.json',include_benchmark=False)
        value['plots'][0]['comparison']['compact_result_sha256'] = 'a'*64
        self.assertFalse(self.verify(value)['valid'])

if __name__ == '__main__':
    unittest.main()
