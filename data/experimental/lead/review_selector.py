"""Read-only scientific/accounting audit of the isolated selector study."""
from collections import Counter
from datetime import datetime
import hashlib
import json
from pathlib import Path

ROOT=Path(__file__).resolve().parents[3]
STUDY=ROOT/'data/experimental/selector'
def read(name):return json.loads((STUDY/name).read_text())
def digest(path):return hashlib.sha256(path.read_bytes()).hexdigest()

def main():
    manifest,policy,results=read('dataset-manifest.json'),read('policy.json'),read('results.json')
    assert policy['manifest_sha256']==digest(STUDY/'dataset-manifest.json')
    assert results['policy_sha256']==digest(STUDY/'policy.json')
    for path,value in policy['guard'].items():assert digest(ROOT/path)==value
    patches=manifest['patches'];counts=Counter(p['split'] for p in patches)
    assert counts=={'train':36,'dev':18,'holdout':18}
    assert len({p['id'] for p in patches})==72
    for i,a in enumerate(patches):
        assert 0<=a['row']<=40000-512 and 0<=a['col']<=40000-512
        assert not (a['row']<6276 and a['row']+512>5672 and a['col']<36322 and a['col']+512>35089)
        for b in patches[i+1:]:
            assert not (a['row']<b['row']+512 and b['row']<a['row']+512 and a['col']<b['col']+512 and b['col']<a['col']+512)
    development={p['id'] for p in patches if p['split']!='holdout'}
    assert set(policy['development_measurement_sha256'])==development
    for name,value in policy['development_measurement_sha256'].items():
        assert digest(STUDY/f'measurements/{name}.json')==value
    observations={p['id']:read(f'measurements/{p["id"]}.json') for p in patches}
    frozen=datetime.fromisoformat(policy['frozen_utc'])
    holdout=[r for r in observations.values() if r['patch']['split']=='holdout']
    assert all(datetime.fromisoformat(r['measured_utc'])>frozen for r in holdout)
    assert all(len(r['measurements'])==26 and all(x['roundtrip'] and x['window_exact'] for x in r['measurements']) for r in observations.values())
    checked_packages=[]
    for family,model in results['models'].items():
        ids=policy['models'][family]['candidate_ids']
        def cost(row,config):return next(v['total_bytes'] for v in row['measurements'] if v['config']==config)
        best=min(ids,key=lambda c:sum(cost(observations[p],c) for p in development))
        assert best==model['fixed_best_development']
        for kind,package in model['packages'].items():
            folder=ROOT/package['path'];total=0
            actual={str(p.relative_to(folder)) for p in folder.rglob('*') if p.is_file()}
            assert actual=={f['path'] for f in package['files']}
            for f in package['files']:
                path=folder/f['path'];assert path.stat().st_size==f['bytes'] and digest(path)==f['sha256'];total+=f['bytes']
            assert total==package['total_bytes']
            checked_packages.append({'family':family,'kind':kind,'total_bytes':total})
        assert model['complete_package_delta_bytes']==model['packages']['selected']['total_bytes']-model['packages']['fixed']['total_bytes']
    matching=read('matching-level-control.json')
    assert matching['selected_level3_minus_control_bytes']==results['models']['level3']['packages']['selected']['total_bytes']-matching['package']['total_bytes']==10217
    result={'passed':True,'split_counts':dict(counts),'no_patch_overlap':True,'company_aoi_excluded':True,'frozen_before_recorded_holdout_reads':True,'development_hashes_checked':len(development),'candidate_control_measurements_checked':len(observations)*26,'complete_packages_recounted':checked_packages,'decision':'Do not integrate selector; no advantage over strong fixed control after total package/model accounting. Strong seen-AOI GeoTIFF control gets a separate fair query/proof study.','limits':['Audit reads existing timestamps/hash evidence; it is not a cryptographic proof of historical non-access.','No second satellite ground truth or legal labels; no new generalization cohort.','No independent replay of all1872encodes in this lead audit; worker full replay and source readbacks are separately recorded.']}
    (ROOT/'data/experimental/lead/selector-review.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps(result,indent=2))

if __name__=='__main__':main()
