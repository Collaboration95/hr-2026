"""Current accepted positives, per-sample bound forgeries, and 46-file lifecycle."""
from copy import deepcopy
import json,shutil,subprocess,sys,tempfile
from pathlib import Path
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from validation.run_checks import digest,file_hash
import engine.jrc_proof as proof
from engine.package_jrc import manifest as package_manifest

def encoded(v):return json.dumps(v,sort_keys=True,separators=(',',':'),allow_nan=False).encode()
def main():
    base=ROOT/'validation/jrc-fix';base.mkdir(exist_ok=True)
    canonical=ROOT/'artifacts/jrc-baseline-v1.json';real=json.loads(canonical.read_text())
    with patch.object(proof,'run_jrc_benchmark',side_effect=AssertionError('ordinary export tried to remeasure')):
        fresh=proof.export_jrc(output=base/'fresh-positive.json')
    report={'fresh_positive':proof.verify_jrc_artifact(base/'fresh-positive.json'),'fresh_byte_identical':(base/'fresh-positive.json').read_bytes()==canonical.read_bytes(),'current_content':real['content_sha256'],'current_experiment':real['benchmark']['experiment_id']}
    assert report['fresh_positive']['valid'] and report['fresh_byte_identical'],report
    prior_manifest=json.loads((ROOT/'artifacts/jrc-bundle-manifest.json').read_text())
    report['canonical_manifest_stale_files']=[f['path'] for f in prior_manifest['files'] if file_hash(ROOT/f['path'])!=f['sha256']]
    manifest=package_manifest(output=base/'current-bundle-manifest.json')
    bundle=Path(tempfile.mkdtemp(prefix='minimal-46-',dir=base))
    for f in manifest['files']:
        source=ROOT/f['path'];target=bundle/f['path'];target.parent.mkdir(parents=True,exist_ok=True)
        assert file_hash(source)==f['sha256'],f['path'];shutil.copy2(source,target)
    def snapshot():return {str(p.relative_to(bundle)):file_hash(p) for p in bundle.rglob('*') if p.is_file()}
    before=snapshot();tile=bundle/'data/experimental/jrc/JRC_GFC2020_V4_N10_E90.tif';assert not tile.exists()
    commands=[]
    for args in [('--verify','artifacts/jrc-baseline-v1.json'),(),('--verify','artifacts/jrc-baseline-v1.json')]:
        r=subprocess.run([sys.executable,'-B','-m','engine.jrc',*args],cwd=bundle,capture_output=True,text=True,timeout=30)
        commands.append({'argv':list(args),'exit':r.returncode,'stdout':r.stdout,'stderr':r.stderr})
    after=snapshot()
    report['minimal']={'path':str(bundle.relative_to(ROOT)),'file_count':len(before),'full_tile_absent':not tile.exists(),'commands':commands,'all_bytes_identical':before==after,'new_files':sorted(set(after)-set(before))}
    # Rehash both archive and artifact so rejection must check sample evidence.
    report['negative_samples']=[]
    cases=[
      ('warmup-result',lambda b:b['baseline']['hot_17_queries']['validation']['warmups'][0].update(result_sha256='0'*64)),
      ('intermediate-result',lambda b:b['baseline']['hot_17_queries']['validation']['samples'][1].update(result_sha256='0'*64)),
      ('intermediate-guard',lambda b:b['candidates'][0]['decode']['validation']['samples'][1].update(guard_after='0'*64)),
      ('cold-child',lambda b:b['cold_smallest_encoded']['children'][1].update(answer_sha256='0'*64)),
      ('cold-warmup-guard',lambda b:b['cold_source']['warmup_children'][0].update(guard_before='0'*64)),
    ]
    cli="""import json,sys
from engine.jrc_proof import verify_jrc_artifact
print(json.dumps(verify_jrc_artifact(sys.argv[1])))
"""
    for label,mutate in cases:
        d=deepcopy(real);b=d['benchmark'];mutate(b);b.pop('archive');run='run-'+digest(b)
        relative='artifacts/jrc-stores/'+b['experiment_id']+'/'+run+'.json';archive=bundle/relative;archive.write_bytes(encoded(b))
        b['archive']={'path':relative,'run_id':run}
        for p in d['plots']:
            receipt=p['receipt'];receipt['benchmark_run']=run;receipt['receipt_sha256']=digest({k:v for k,v in receipt.items() if k!='receipt_sha256'})
        d['content_sha256']=digest({k:v for k,v in d.items() if k!='content_sha256'});path=bundle/(label+'.json');path.write_bytes(encoded(d))
        r=subprocess.run([sys.executable,'-B','-c',cli,str(path)],cwd=bundle,capture_output=True,text=True,timeout=30);assert r.returncode==0,r.stderr
        report['negative_samples'].append({'label':label,'actual':json.loads(r.stdout)})
    report['original_j1_repro']=json.loads((ROOT/'docs/lab/validator-jrc-fix-timing.json').read_text())
    report['pass']=report['fresh_positive']['valid'] and report['fresh_byte_identical'] and len(before)==46 and before==after and all(c['exit']==0 for c in commands) and all(not n['actual']['valid'] for n in report['negative_samples']) and not report['original_j1_repro']['benchmark_runner_accepted'] and report['original_j1_repro']['error']=='JRC timed result mismatch at sample 2'
    (ROOT/'docs/lab/validator-jrc-fix-verification.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(report,indent=2));return int(not report['pass'])
if __name__=='__main__':sys.exit(main())
