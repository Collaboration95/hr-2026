"""Validate a manifest-only local copy without source acquisition caches.

Run after regenerating the chosen bundle manifest. Never edits canonical files.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

ROOT=Path(__file__).resolve().parents[3]
CONFIG={
 'jrc':('artifacts/jrc-bundle-manifest.json','artifacts/jrc-baseline-v1.json',
        ['-m','engine.jrc','--verify'],['-m','engine.jrc','--output']),
 'hansen':('artifacts/retained-bundle-manifest.json','artifacts/demo-v1.json',
           ['-m','engine.verify'],['-m','engine.export','--output']),
}

def digest(path):
 return hashlib.sha256(path.read_bytes()).hexdigest()

def smoke(component):
 manifest_name,artifact,verify,export=CONFIG[component]
 manifest=json.loads((ROOT/manifest_name).read_text())
 owned=ROOT/'data/experimental/lead'
 results=[]
 with tempfile.TemporaryDirectory(prefix=component+'-bundle-smoke-',dir=owned) as name:
  copy=Path(name)
  for item in manifest['files']:
   relative=Path(item['path'])
   if relative.is_absolute() or '..' in relative.parts: raise ValueError('Unsafe manifest path')
   source=ROOT/relative
   if source.stat().st_size!=item['bytes'] or digest(source)!=item['sha256']:
    raise ValueError('Regenerate stale bundle manifest: '+str(relative))
   target=copy/relative;target.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(source,target)
  original_digest=digest(copy/artifact)
  rebuilt='artifacts/bundle-smoke-rebuilt.json'
  commands=[('verify_before',verify+[artifact]),('ordinary_export',export+[rebuilt]),('verify_after',verify+[rebuilt])]
  env={**os.environ,'PYTHONDONTWRITEBYTECODE':'1','PYTHONPATH':''}
  for label,args in commands:
   run=subprocess.run([sys.executable,'-B',*args],cwd=copy,env=env,text=True,capture_output=True,timeout=120)
   results.append({'step':label,'args':args,'returncode':run.returncode,'stdout':run.stdout[-3000:],'stderr':run.stderr[-3000:]})
   if run.returncode: break
  equal=(copy/rebuilt).is_file() and digest(copy/rebuilt)==original_digest
  # Results are byte deterministic only when the same retained run is reused.
  passed=len(results)==3 and all(r['returncode']==0 for r in results) and equal
  output={'component':component,'manifest_sha256':digest(ROOT/manifest_name),'experiment_id':manifest['experiment_id'],
          'run_id':manifest['run_id'],'file_count':len(manifest['files']),'bundle_bytes':manifest['total_bytes'],
          'only_manifest_files_copied':True,'reexport_byte_identical':equal,'passed':passed,'steps':results}
 (owned/(component+'-bundle-smoke-current.json')).write_text(json.dumps(output,indent=2)+'\n')
 return output

if __name__=='__main__':
 parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('component',choices=CONFIG)
 result=smoke(parser.parse_args().component)
 print(json.dumps({k:v for k,v in result.items() if k!='steps'},indent=2))
 sys.exit(0 if result['passed'] else 1)
