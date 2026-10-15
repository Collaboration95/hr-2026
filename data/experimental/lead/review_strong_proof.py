"""Independent strong-control typed-proof probe in a disposable bundle copy."""
from pathlib import Path
import json,hashlib,shutil,subprocess,sys,tempfile
ROOT=Path(__file__).resolve().parents[3]
def canonical(v):return json.dumps(v,sort_keys=True,separators=(',',':'),allow_nan=False).encode()
def digest(v):return hashlib.sha256(canonical(v)).hexdigest()
def main():
 source=json.loads((ROOT/'artifacts/strong-baseline-v1.json').read_text())
 paths={f['path'] for f in json.loads((ROOT/'artifacts/retained-bundle-manifest.json').read_text())['files']}
 paths.update(source['identity']['guard'])
 paths.update(['engine/strong_baseline.py','engine/strong_baseline_measure.py','artifacts/strong-baseline-v1.json',source['archive']['path'],f"artifacts/strong-baseline-stores/{source['experiment_id']}/identity.json"])
 for row in source['controls']:
  paths.update(str(Path(row['store_path'])/f['path']) for f in row['storage']['files'])
 records=[]
 with tempfile.TemporaryDirectory(prefix='strong-proof-',dir=ROOT/'data/experimental/lead') as d:
  copy=Path(d)
  for name in paths:
   target=copy/name;target.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(ROOT/name,target)
  def run(label,path):
   r=subprocess.run([sys.executable,'-B','-m','engine.strong_baseline','--verify',str(path)],cwd=copy,text=True,capture_output=True)
   records.append({'case':label,'returncode':r.returncode,'stdout':r.stdout[-1500:],'stderr':r.stderr[-1500:]})
  run('fresh_positive','artifacts/strong-baseline-v1.json')
  altered=json.loads(json.dumps(source));altered['controls'][0]['proof']['raw_values_equal']=1
  altered['controls'][0]['proof']['comparisons'][0]['equal']=1
  payload={k:v for k,v in altered.items() if k!='archive'}
  archive=Path(source['archive']['path']).parent/('run-'+digest(payload)+'.json')
  (copy/archive).write_bytes(canonical(payload))
  altered['archive']={'path':str(archive),'sha256':hashlib.sha256((copy/archive).read_bytes()).hexdigest()}
  target=copy/'artifacts/type-forgery.json';target.write_bytes(canonical(altered))
  run('integer_in_boolean_proof_with_rehashed_archive',target)
 output={'records':records,'canonical_files_modified':False,'method':'separate manifest-only copy; fresh positive then rehashed typed-proof forgery'}
 (ROOT/'data/experimental/lead/strong-proof-review.json').write_text(json.dumps(output,indent=2)+'\n')
 print(json.dumps(output,indent=2))
if __name__=='__main__':main()
