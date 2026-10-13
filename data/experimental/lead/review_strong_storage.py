"""Lead read-only comparison of actual TIFF pixels, masks and required files."""
from pathlib import Path
import json,sys,hashlib
ROOT=Path(__file__).resolve().parents[3];sys.path.insert(0,str(ROOT))
import numpy as np
import rasterio
from engine.source import load_source,load_plots,canonical_bytes,sha256_file
from engine.model import Dataset
from engine.query import evaluate
from engine.oracle import oracle_evaluate

def main():
 artifact=json.loads((ROOT/'artifacts/strong-baseline-v1.json').read_text())
 source=load_source();plots=load_plots();rows=[]
 for item in artifact['controls']:
  folder=ROOT/item['store_path'];m=json.loads((folder/'manifest.json').read_text())
  if m['masks']!={'mode':'implicit_all_valid','invalid_counts':[0,0,0]}:raise ValueError('This review is scoped to current real all-valid stores')
  with rasterio.open(folder/'bands.tif') as f:
   raw=f.read();mask=f.read_masks()!=0
   grid={'shape':[f.height,f.width],'crs':str(f.crs),'transform':list(f.transform)[:6]}
  assert np.array_equal(raw,source.bands) and np.array_equal(mask,source.masks)
  assert canonical_bytes(m['metadata'])==canonical_bytes(source.metadata)
  assert grid=={k:source.metadata[k] for k in grid}
  candidate=Dataset(raw,mask,m['metadata']).validate()
  queries=[]
  for plot in plots:
   expected=evaluate(source,plot['geometry']);actual=evaluate(candidate,plot['geometry']);oracle=oracle_evaluate(source,plot['geometry'])
   assert canonical_bytes(expected)==canonical_bytes(actual)==canonical_bytes(oracle)
   queries.append({'plot_id':plot['plot_id'],'exact':True})
  files=[{'path':p.name,'bytes':p.stat().st_size,'sha256':sha256_file(p)} for p in sorted(folder.iterdir())]
  assert sum(x['bytes'] for x in files)==item['storage']['total_bytes']
  rows.append({'candidate':item['candidate'],'files':files,'total_bytes':sum(x['bytes'] for x in files),'all_raw_masks_metadata_grid_exact':True,'queries':queries})
 custom=artifact['accepted_custom'];custompath=ROOT/custom['store_path'];custombytes=sum(p.stat().st_size for p in custompath.iterdir())
 best=min(rows,key=lambda r:r['total_bytes'])
 out={'experiment_id':artifact['experiment_id'],'run':artifact['archive'],'controls':rows,'accepted_custom_bytes':custombytes,'best_control_bytes':best['total_bytes'],'delta_bytes':best['total_bytes']-custombytes,'smaller_percent':100*(1-best['total_bytes']/custombytes),'scope':'Independent actual TIFF read with rasterio; source arrays and scalar query oracle; real masks all valid; not independent GDAL decoding or general parser certification.'}
 (ROOT/'data/experimental/lead/strong-storage-review.json').write_text(json.dumps(out,indent=2)+'\n');print(json.dumps({k:v for k,v in out.items() if k!='controls'},indent=2))
if __name__=='__main__':main()
