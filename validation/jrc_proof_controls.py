"""Fresh JRC positives and independently specified rehashed corruptions.
All fixtures stay under validation/jrc; canonical artifacts and sources untouched.
"""
from copy import deepcopy
import json
from pathlib import Path
import shutil
import sys
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from validation.run_checks import digest
from engine.jrc import load_jrc,JrcDataset
from engine.jrc_codec import encode_jrc_store
from engine.jrc_proof import export_jrc,verify_jrc_artifact

def resign(d):
    for p in d['plots']:
        r=p['receipt'];r['source_result_sha256']=digest(p['source_result']);r['compact_result_sha256']=digest(p['compact_result']);r['evidence_sha256']=digest(p['evidence']);r['receipt_sha256']=digest({k:v for k,v in r.items() if k!='receipt_sha256'})
    d['content_sha256']=digest({k:v for k,v in d.items() if k!='content_sha256'})

def main():
    base=ROOT/'validation/jrc';base.mkdir(parents=True,exist_ok=True)
    real=json.loads((ROOT/'artifacts/jrc-baseline-v1.json').read_text())
    fresh=export_jrc(output=base/'fresh-positive.json',store=real['store']['path'],benchmark=real['benchmark'])
    free=export_jrc(output=base/'metric-free-positive.json',store=real['store']['path'])
    positive=verify_jrc_artifact(base/'fresh-positive.json');free_positive=verify_jrc_artifact(base/'metric-free-positive.json')
    report={'fresh_positive':positive,'fresh_equals_canonical':fresh==real,'metric_free_positive':free_positive,'negatives':[]}
    # Freeze JSON to remove shared Python object aliases before one-field mutations.
    measured=json.loads(json.dumps(fresh));unmeasured=json.loads(json.dumps(free))
    def negative(name,d,expected):
        resign(d);path=base/(name+'.json');path.write_text(json.dumps(d)+'\n');result=verify_jrc_artifact(path)
        report['negatives'].append({'name':name,'expected_failure':expected,'actual':result,'pass':not result['valid'] and any(expected in s for s in result['failures'])})
    controls=[
      ('zero-as-unknown',lambda d:d['plots'][1]['source_result'].update(mapped_forest_present=None),'source_result'),
      ('flag-bool-to-int',lambda d:d['plots'][0]['source_result'].update(mapped_forest_present=1),'source_result'),
      ('count-zero-to-bool',lambda d:d['plots'][1]['source_result']['class_counts'].update({'1':False}),'source_result'),
      ('evidence-zero-to-bool',lambda d:d['plots'][1]['evidence']['cells'][0].update(value=False),'receipt mismatch'),
      ('mask-bool-to-int',lambda d:d['plots'][0]['evidence']['cells'][0].update(valid=1),'receipt mismatch'),
      ('comparison-bool-to-int',lambda d:d['plots'][0]['comparison'].update(equal=1),'comparison'),
      ('summary-count',lambda d:d['summary'].update(selected_cell_count_sum=1),'summary'),
      ('summary-bool-for-one',lambda d:d['summary']['mapped_forest_plot_counts'].update({'true':True}),'summary'),
      ('receipt-year',lambda d:d['plots'][0]['receipt'].update(reference_year=2025),'receipt'),
      ('receipt-query',lambda d:d['plots'][0]['receipt'].update(query_version='hansen-centers.v1'),'receipt'),
      ('receipt-mask-claim',lambda d:d['plots'][0]['receipt']['full_chip'].update(mask_equal=1),'receipt'),
      ('cohort-missing-plot',lambda d:d['plots'].pop(),'plot cohort'),
      ('dataset-vintage',lambda d:d['dataset'].update(version='v3'),'dataset'),
    ]
    for name,mutate,error in controls:
        d=deepcopy(unmeasured);mutate(d);negative(name,d,error)
    d=deepcopy(unmeasured);g=d['plots'][0]['geometry'];g['coordinates'][0][0][0]+=0.00001;g['coordinates'][0][-1]=g['coordinates'][0][0][:];d['plots'][0]['geometry_sha256']=digest(g);d['plots'][0]['receipt']['geometry_sha256']=digest(g);negative('rehashed-geometry',d,'geometry')
    for name,mutate,error in [
      ('benchmark-cohort',lambda d:d['benchmark']['identity'].update(queries_sha256='0'*64),'identity'),
      ('benchmark-vintage',lambda d:d['benchmark']['identity']['source_metadata'].update(reference_year=2025),'identity'),
      ('benchmark-size',lambda d:d['benchmark']['baseline'].update(total_bytes=1),'measured archive'),
      ('benchmark-timing',lambda d:d['benchmark']['baseline']['hot_17_queries']['wall'].update(median=0),'measured archive'),
    ]:
        d=deepcopy(measured);mutate(d);negative(name,d,error)
    ds=load_jrc();selected={(c['row'],c['col']) for p in real['plots'] for c in p['evidence']['cells']}
    row,col=next((r,c) for r in range(ds.values.shape[0]) for c in range(ds.values.shape[1]) if (r,c) not in selected)
    for kind in ('raw','mask'):
        v,m=ds.values.copy(),ds.mask.copy()
        if kind=='raw':v[row,col]^=1
        else:m[row,col]=not m[row,col]
        path=base/(kind+'-offplot-store');encode_jrc_store(JrcDataset(v,m,ds.metadata),path)
        d=deepcopy(unmeasured);d['store']['path']=str(path.relative_to(ROOT));negative(kind+'-offplot',d,'raw values mismatch' if kind=='raw' else 'mask mismatch')
    report['offplot_witness']={'row':row,'col':col,'original_value':int(ds.values[row,col]),'original_valid':bool(ds.mask[row,col])}
    # Build a real minimal copy, never moving/deleting the actual full source.
    minimal=base/'minimal-bundle';minimal.mkdir(exist_ok=True)
    files={f['path'] for f in real['dataset']['required_inputs']+real['benchmark']['common_plot_inputs']+real['benchmark']['identity']['implementation']}
    for c in real['benchmark']['candidates']:files.update(f['path'] for f in c['storage']['files'])
    files.add(real['benchmark']['archive']['path']);files.add('artifacts/jrc-stores/'+real['benchmark']['experiment_id']+'/identity.json')
    for relative in sorted(files):
        dst=minimal/relative;dst.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(ROOT/relative,dst)
    export_jrc(output=minimal/'artifacts/jrc-baseline-v1.json',store=real['store']['path'],benchmark=real['benchmark'],root=minimal)
    report['minimal_explicit_positive']=verify_jrc_artifact(minimal/'artifacts/jrc-baseline-v1.json',root=minimal)
    try:
        export_jrc(output=minimal/'ordinary-export.json',root=minimal)
        report['ordinary_export_without_full_cache']={'accepted':True}
    except (ValueError,OSError) as exc:
        report['ordinary_export_without_full_cache']={'accepted':False,'error':str(exc)}
    report['proof_controls_pass']=positive['valid'] and free_positive['valid'] and all(x['pass'] for x in report['negatives'])
    (ROOT/'docs/lab/validator-jrc-proof-controls.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps({k:v for k,v in report.items() if k!='negatives'},indent=2))
    print('rejection outcomes',[(x['name'],x['pass'],x['actual']['failures']) for x in report['negatives']])
    return int(not report['proof_controls_pass'])

if __name__=='__main__':sys.exit(main())
