"""Real cohort and deliberately adversarial research-control tests."""
import copy
import json
from pathlib import Path
import tempfile
import unittest
from compression import zstd
import numpy as np
import rasterio
from control import *
from engine.jrc import load_jrc, evaluate_jrc
from engine.jrc_oracle import oracle_jrc
from engine.source import load_plots, object_hash
from engine.jrc_codec import decode_jrc_store
import study

AREA = Path(__file__).resolve().parent

def rectangle(x0,y0,x1,y1):
    return {'type':'Polygon','coordinates':[[[x0,y0],[x1,y0],[x1,y1],[x0,y1],[x0,y0]]]}

class ControlTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(dir=AREA,prefix='test-')
        self.addCleanup(self.tmp.cleanup)
        self.path = Path(self.tmp.name)/'store'
        self.ds = JrcDataset(np.array([[0,1,1],[0,1,0]],dtype=np.uint8),
                             np.array([[1,0,1],[1,1,1]],dtype=bool),
                             {'shape':[2,3],'transform':[1.,0.,0.,0.,-1.,2.], 'crs':'EPSG:4326','nodata':None})
    def write(self):
        encode(self.ds,self.path)
    def mutate(self,fn):
        x=json.loads((self.path/'manifest.json').read_text());fn(x)
        (self.path/'manifest.json').write_bytes(canonical_bytes(seal(x)))
    def test_raw_masked_one_and_independent_mask(self):
        self.write();d=decode(self.path)
        self.assertTrue(np.array_equal(d.values,self.ds.values))
        self.assertTrue(np.array_equal(d.mask,self.ds.mask))
        self.assertEqual(int(d.values[0,1]),1)
        self.assertFalse(d.mask[0,1])
        self.assertGreater(storage(self.path)['mask_bytes'],0)
    def test_valid_zero_unknown_partial_and_missing(self):
        self.write();d=decode(self.path)
        for geo in [rectangle(0,1,1,2),rectangle(1,1,2,2),rectangle(-1,1,1,2),rectangle(0,0,3,2)]:
            for missing in (False,True):
                self.assertEqual(evaluate_jrc(d,geo,missing),oracle_jrc(d,geo,missing))
        self.assertIs(evaluate_jrc(d,rectangle(0,1,1,2))['mapped_forest_present'],False)
        self.assertIsNone(evaluate_jrc(d,rectangle(1,1,2,2))['mapped_forest_present'])
        partial=evaluate_jrc(d,rectangle(-1,1,1,2))
        self.assertEqual(partial['support'],'partial');self.assertIsNone(partial['mapped_forest_present'])
    def test_reject_invalid_raw_even_masked(self):
        self.ds.values[0,1]=2
        with self.assertRaises(ValueError):self.write()
        self.assertFalse(self.path.exists())
    def test_all_valid_has_no_sidecar(self):
        self.ds.mask[:]=True;self.write()
        self.assertEqual(storage(self.path)['mask_bytes'],0)
        self.assertTrue(decode(self.path).mask.all())
    def test_unsafe_path(self):
        self.write();self.mutate(lambda x:x['files'][0].update(path='../outside.tif'))
        with self.assertRaises(ValueError):decode(self.path)
    def test_symlink(self):
        self.write();p=self.path/'values.tif';target=Path(self.tmp.name)/'target.tif';p.rename(target);p.symlink_to(target)
        with self.assertRaises(ValueError):decode(self.path)
    def test_extra_uncounted_file(self):
        self.write();(self.path/'values.tif.msk').write_bytes(b'extra')
        with self.assertRaises(ValueError):decode(self.path)
    def test_truncated_changed_payload(self):
        self.write();p=self.path/'values.tif';p.write_bytes(p.read_bytes()[:-1])
        with self.assertRaises(ValueError):decode(self.path)
    def test_malformed_tiff_with_rebound_hash(self):
        self.write();(self.path/'values.tif').write_bytes(b'bad TIFF header')
        self.mutate(lambda x:x['files'].__setitem__(0,record(self.path/'values.tif')))
        with self.assertRaises((ValueError,rasterio.errors.RasterioIOError)):decode(self.path)
    def test_contradictory_grid_and_type(self):
        self.write();self.mutate(lambda x:x['metadata']['transform'].__setitem__(2,1.))
        with self.assertRaises(ValueError):decode(self.path)
        self.mutate(lambda x:x['settings'].update(dtype='uint16'))
        with self.assertRaises(ValueError):decode(self.path)
    def test_huge_metadata_rejected_before_allocation(self):
        self.write();self.mutate(lambda x:x['metadata'].update(shape=[16384,16384]))
        with self.assertRaises(ValueError):decode(self.path)
    def test_mask_mode_contradiction(self):
        self.write();self.mutate(lambda x:x.update(mask_mode='all_valid'))
        with self.assertRaises(ValueError):decode(self.path)
    def test_malformed_mask_and_nonzero_padding(self):
        self.write();p=self.path/'mask.bin'
        for raw in (b'',b'\xff',b'\x3f\x00'):
            p.write_bytes(zstd.compress(raw,level=3))
            self.mutate(lambda x:x['files'].__setitem__(1,record(p)))
            with self.assertRaises(ValueError):decode(self.path)
    def test_manifest_bounds_duplicates_and_hash(self):
        self.write();p=self.path/'manifest.json';original=p.read_bytes()
        for raw in (b' '* (MAX_MANIFEST+1),b'{"format":1,"format":2}',original.replace(b'"invalid_cells":1',b'"invalid_cells":2')):
            p.write_bytes(raw)
            with self.assertRaises(ValueError):decode(self.path)
    def test_guard_rejects_changed_input(self):
        p=Path(self.tmp.name)/'guard.bin';p.write_bytes(b'old')
        guard={**study.BOOT,**study.pin([p])};study.guard_check(guard)
        p.write_bytes(b'new')
        with self.assertRaisesRegex(ValueError,'MIXED RUN'):study.guard_check(guard)
    def test_guard_rejects_import_fingerprint(self):
        guard=dict(study.BOOT);guard[next(iter(guard))]='0'*64
        with self.assertRaisesRegex(ValueError,'MIXED RUN'):study.guard_check(guard)
    def test_false_sample_digest_rejected(self):
        with self.assertRaisesRegex(ValueError,'full raw/mask/metadata'):
            study.equal(self.ds,{'raw':'wrong','mask':'wrong','metadata':'wrong'})
    def test_wrong_answer_in_second_hot_sample_rejected(self):
        from unittest.mock import patch
        fake=[{'geometry':rectangle(0,1,1,2)}]
        good=study.answers(self.ds,fake)
        req={'guard':study.BOOT,'operation':'hot','data_digest':study.data_digest(self.ds),
             'answer_sha256':object_hash(good)}
        with patch.object(study,'load',return_value=self.ds), patch.object(study,'load_plots',return_value=fake), \
             patch.object(study,'answers',side_effect=[good,good,good,[{'wrong':True}]]):
            with self.assertRaisesRegex(ValueError,'timed hot answer mismatch'):study.worker(req)
    def test_child_rejects_wrong_input_identity(self):
        p=Path(self.tmp.name)/'identity.bin';p.write_bytes(b'old')
        guard={**study.BOOT,**study.pin([p])};p.write_bytes(b'new')
        import subprocess,sys
        result=subprocess.run([sys.executable,'-B',str(AREA/'study.py'),'--child'],
                              input=canonical_bytes({'guard':guard}),capture_output=True)
        self.assertNotEqual(result.returncode,0)
        self.assertIn(b'MIXED RUN',result.stderr)
    def test_offplot_rehashed_change_is_not_proof(self):
        self.write();original=study.data_digest(self.ds)
        self.ds.values[1,2]^=1
        other=Path(self.tmp.name)/'other';encode(self.ds,other)
        with self.assertRaisesRegex(ValueError,'full raw/mask/metadata'):study.equal(decode(other),original)
    def test_real_native_roundtrips_all17_and_scalar_oracle(self):
        source=load_jrc();plots=load_plots();expected=[evaluate_jrc(source,p['geometry']) for p in plots]
        self.assertEqual(len(plots),17)
        self.assertEqual(expected,[oracle_jrc(source,p['geometry']) for p in plots])
        self.assertEqual(source.values.size,6684255)
        self.assertTrue(source.mask.all())
        custom=json.loads((ROOT/'artifacts/jrc-baseline-v1.json').read_text())['store']['path']
        decoded=[decode_jrc_store(ROOT/custom)]
        for level in (3,19):
            path=Path(self.tmp.name)/str(level);encode(source,path,level);decoded.append(decode(path))
        for ds in decoded:
            study.equal(ds,study.data_digest(source))
            self.assertEqual(expected,[evaluate_jrc(ds,p['geometry']) for p in plots])

if __name__ == '__main__':
    unittest.main(verbosity=2)
