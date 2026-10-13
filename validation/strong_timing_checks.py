"""Inject one wrong measured sample into real worker loops, check parent rejection.
Runs in-process for this negative test only; produces no performance claim/files.
"""
from copy import deepcopy
import json
from pathlib import Path
import sys
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
import engine.strong_baseline_measure as s

def main():
    a=json.loads((ROOT/'artifacts/strong-baseline-v1.json').read_text());guard=dict(a['identity']['guard'])
    for c in a['controls']:
        guard.update({str(Path(c['store_path'])/f['path']):f['sha256'] for f in c['storage']['files']})
    representations=[('source',None,'data/public/provenance.json'),('custom',a['accepted_custom']['store_path'],a['accepted_custom']['store_path']+'/index.json')]+[('control',c['store_path'],c['store_path']+'/manifest.json') for c in a['controls']]
    checks=[]
    for representation,store,meta in representations:
        for target_mode in ('full','indexed'):
            count=0;injected=[];real=s.evaluate if target_mode=='full' else s.evaluate_reader
            def flaky(*args,**kwargs):
                nonlocal count
                count+=1;r=real(*args,**kwargs)
                # Two warmups ×17, then second measured batch's first plot.
                if count==52:
                    r=deepcopy(r);r['selected_cell_count']+=1;injected.append(count)
                return r
            def local_child(request):
                # Only the chosen HOT worker sees the injected query function.
                if request['mode']==target_mode and request['operation']=='hot':
                    with patch.object(s,'evaluate' if target_mode=='full' else 'evaluate_reader',flaky):out=s.worker(request)
                else:out=s.worker(request)
                return dict(out,subprocess_wall_ms=0.0)
            request={'representation':representation,'store':store,'metadata_file':s.file_record(ROOT/meta),'guard':guard,'repetitions':3,'warmups':2}
            rejected=False;error=None
            with patch.object(s,'child',local_child):
                try:s.measure(request,a['source']['measurements']['full']['expected_answer_sha256'])
                except ValueError as exc:rejected='digest mismatch' in str(exc);error=str(exc)
            checks.append({'representation':store or representation,'mode':target_mode,'injected':injected,'rejected':rejected,'error':error})
    request={'operation':'cold','mode':'full','representation':'source','metadata_file':s.file_record(ROOT/'data/public/provenance.json'),'guard':dict(guard),'repetitions':1,'warmups':0}
    request['guard']['engine/query.py']='0'*64
    try:s.worker(request);race=False
    except RuntimeError as exc:race='fingerprint race' in str(exc)
    report={'scope':'synthetic transient sample failures; in-process worker loops; no timing-performance claim','checks':checks,'mismatched_guard_rejected':race,'pass':all(c['rejected'] and c['injected'] for c in checks) and race}
    (ROOT/'docs/lab/validator-strong-timing.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report,indent=2));return int(not report['pass'])
if __name__=='__main__':sys.exit(main())
