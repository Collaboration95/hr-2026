"""Additive same-chip JRC standard-format control; no retained choice mutation."""
from pathlib import Path
import json, sys, time
ROOT=Path(__file__).resolve().parents[3]
sys.path.insert(0,str(ROOT))
import numpy as np
import rasterio
from affine import Affine
from engine.jrc import load_jrc
from engine.source import canonical_bytes, sha256_file

def main():
 ds=load_jrc(ROOT)
 folder=ROOT/'data/experimental/lead/jrc-standard-probe'
 folder.mkdir(exist_ok=True)
 if not ds.mask.all(): raise ValueError('This bounded probe requires verified all-valid source masks')
 rows=[]
 for level in (3,19):
  for block in (256,512,1024):
   for bits,predictor in ((8,1),(8,2),(1,1)):
    name=f'zstd{level}-block{block}-bits{bits}-predictor{predictor}'
    path=folder/(name+'.tif')
    profile=dict(driver='GTiff',height=ds.values.shape[0],width=ds.values.shape[1],count=1,dtype='uint8',crs=ds.metadata['crs'],transform=Affine(*ds.metadata['transform']),nodata=None,tiled=True,blockxsize=block,blockysize=block,compress='ZSTD',zstd_level=level,predictor=predictor,nbits=bits,num_threads=1)
    start=time.perf_counter_ns(); cpu=time.process_time_ns()
    with rasterio.open(path,'w',**profile) as dst: dst.write(ds.values,1)
    encode_wall=(time.perf_counter_ns()-start)/1e6; encode_cpu=(time.process_time_ns()-cpu)/1e6
    record={'path':path.name,'sha256':sha256_file(path),'bytes':path.stat().st_size}
    metadata={'schema_version':'plotline.jrc-standard-probe.v1','source_metadata':ds.metadata,'settings':{'compression':'ZSTD','level':level,'block':block,'nbits':bits,'predictor':predictor},'file':record,'mask_mode':'all_valid_verified'}
    sidecar=folder/(name+'.json');sidecar.write_bytes(canonical_bytes(metadata))
    start=time.perf_counter_ns()
    # The timed verification scope includes a whole-file integrity check.
    if sha256_file(path)!=record['sha256']: raise ValueError('changed probe file')
    with rasterio.open(path) as src:
     values=src.read(1); masks=src.read_masks(1)!=0
     grid_equal=(list(src.transform)[:6]==ds.metadata['transform'] and str(src.crs)==ds.metadata['crs'] and src.nodata is None and src.dtypes==('uint8',))
    decode_wall=(time.perf_counter_ns()-start)/1e6
    exact=grid_equal and np.array_equal(values,ds.values) and np.array_equal(masks,ds.mask)
    if not exact: raise ValueError('standard control fidelity failure: '+name)
    rows.append({'name':name,'tiff_bytes':record['bytes'],'metadata_bytes':sidecar.stat().st_size,'total_bytes':record['bytes']+sidecar.stat().st_size,'encode_wall_ms':encode_wall,'encode_cpu_ms':encode_cpu,'hash_and_decode_wall_ms':decode_wall,'all_raw_masks_grid_exact':exact,'raw_pixel_count':int(values.size),'sidecar_sha256':sha256_file(sidecar)})
 original=json.loads((ROOT/'artifacts/jrc-baseline-v1.json').read_text())
 output={'schema_version':'plotline.jrc-standard-probe-results.v1','inputs':ds.metadata['required_inputs'],'implementation_sha256':sha256_file(Path(__file__)),'reference_store':original['store'],'controls':rows,'smallest_control':min(rows,key=lambda r:r['total_bytes']),'limitations':['Single measurements; not a fair isolated repeated query benchmark.','All-valid real masks only; no general-purpose decoder or malformed-input validation is claimed.','Required reconstruction/source metadata and integrity manifest are counted.','No source/retained artifact or production choice changed.']}
 (folder/'results.json').write_bytes(canonical_bytes(output))
 print(json.dumps({'smallest_control':output['smallest_control'],'reference_bytes':original['store']['total_bytes'],'candidate_count':len(rows)},indent=2))
if __name__=='__main__':main()
