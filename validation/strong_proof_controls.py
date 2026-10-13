"""Rehashed proof controls in a validator-owned copy of the additive bundle."""
from copy import deepcopy
import hashlib,json,shutil,subprocess,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from validation.run_checks import digest,file_hash

def canonical(v):return json.dumps(v,sort_keys=True,separators=(',',':'),allow_nan=False).encode()+b'\n'
def stats(s):return {'samples':s,'repetitions':len(s),'min':min(s),'median':s[0],'p95':max(s)}

def main():
    base=ROOT/'validation/strong';base.mkdir(exist_ok=True)
    bundle=base/'bundle';bundle.mkdir(exist_ok=True)
    manifest=json.loads((ROOT/'artifacts/strong-baseline-bundle-manifest.json').read_text())
    for f in manifest['files']:
        source=ROOT/f['path'];target=bundle/f['path'];target.parent.mkdir(parents=True,exist_ok=True)
        assert file_hash(source)==f['sha256'];shutil.copy2(source,target)
    original=json.loads((ROOT/'artifacts/strong-baseline-v1.json').read_text())
    code="""import json,sys
from engine.strong_baseline_measure import verify_artifact
try: result=verify_artifact(sys.argv[1])
except Exception as e: result={'valid':False,'error':type(e).__name__+': '+str(e)}
print(json.dumps(result))
"""
    def verify(path):
        r=subprocess.run([sys.executable,'-B','-c',code,str(path)],cwd=bundle,text=True,capture_output=True,timeout=30)
        assert r.returncode==0,r.stderr
        return json.loads(r.stdout)
    def write_forged(label,a):
        a.pop('archive',None)
        exp='exp-'+digest(a['identity'])
        old_exp=a['experiment_id'];a['experiment_id']=exp
        folder=bundle/'artifacts/strong-baseline-stores'/exp;folder.mkdir(parents=True,exist_ok=True)
        if exp!=old_exp:
            for c in a['controls']:
                old=bundle/c['store_path'];new=folder/c['candidate']
                if not new.exists():shutil.copytree(old,new)
                c['store_path']=str(new.relative_to(bundle))
        (folder/'identity.json').write_bytes(canonical(a['identity']))
        archive=folder/'runs'/('run-'+digest(a)+'.json');archive.parent.mkdir(exist_ok=True);archive.write_bytes(canonical(a))
        a['archive']={'path':str(archive.relative_to(bundle)),'sha256':file_hash(archive)}
        path=bundle/(label+'.json');path.write_bytes(canonical(a));return path
    positive=verify(bundle/'artifacts/strong-baseline-v1.json');assert positive['valid'],positive
    report={'positive':positive,'negative_controls':[]}
    cases=[
      ('bool-as-int',lambda a:a['controls'][0]['proof'].update(raw_values_equal=1)),
      ('hot-one-sample',lambda a:a['controls'][0]['measurements']['full']['hot'].update(wall_ms=stats([0.0]))),
      ('cold-one-sample',lambda a:a['controls'][0]['measurements']['full']['process_cold'].update(wall_ms=stats([0.0]))),
      ('negative-encode-time',lambda a:a['controls'][0]['preprocessing']['report'].update(encode_wall_ms=-1)),
      ('settings-level-3',lambda a:a['identity']['settings'].update(level=3)),
    ]
    for label,mutate in cases:
        a=deepcopy(original);mutate(a);path=write_forged(label,a);result=verify(path)
        report['negative_controls'].append({'label':label,'expected':'reject rehashed semantic inconsistency','actual':result,'fixture':str(path.relative_to(ROOT))})
    a=deepcopy(original);removed=a['controls'].pop();a['common_input_view']['totals_with_same_acquisition_provenance_and_supplier_files'].pop(removed['candidate']);path=write_forged('missing-declared-control',a)
    report['negative_controls'].append({'label':'missing-declared-control','expected':'reject missing block512 still declared in settings','actual':verify(path),'fixture':str(path.relative_to(ROOT))})
    report['all_rejected']=all(not c['actual']['valid'] for c in report['negative_controls'])
    (ROOT/'docs/lab/validator-strong-proof-controls.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(report,indent=2));return int(not report['all_rejected'])
if __name__=='__main__':sys.exit(main())
