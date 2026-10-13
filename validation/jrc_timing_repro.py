"""One wrong timed answer followed by correct answers must invalidate a run.

Own scratch experiment only. Cold records are replayed from the existing valid
run to keep this negative-control experiment bounded; this is NOT new timing
evidence. Actual source load/encode/decode/hot loops execute unchanged.
"""
from copy import deepcopy
import argparse
import json
from pathlib import Path
import shutil
import sys
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
import engine.jrc_benchmark as benchmark
from engine.jrc import load_jrc
from engine.jrc_proof import validate_benchmark

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--scratch',type=Path,default=ROOT/'validation/jrc/transient-timing-repro')
    parser.add_argument('--report',type=Path,default=ROOT/'docs/lab/validator-jrc-timing-repro.json')
    args=parser.parse_args()
    original=json.loads((ROOT/'artifacts/jrc-baseline-v1.json').read_text())
    root=args.scratch.resolve();root.mkdir(parents=True,exist_ok=True)
    if not (root/'data').exists():(root/'data').symlink_to(ROOT/'data',target_is_directory=True)
    for relative in benchmark.CODE_PATHS:
        path=root/relative;path.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(ROOT/relative,path)
    real_answers=benchmark.answers
    calls=0;injected=[]
    def flaky_answers(*args,**kwargs):
        nonlocal calls
        calls+=1
        result=real_answers(*args,**kwargs)
        # Call1 pins expected output; source hot calls2/3 warm up; calls4..10
        # are measured. Corrupt only the second measured source-hot answer.
        if calls==5:
            result=deepcopy(result);result[0]['selected_cell_count']+=1
            injected.append({'call':calls,'plot':'P-0001','selected_cell_count':result[0]['selected_cell_count']})
        return result
    def replay_cold(path,root,**kwargs):
        return deepcopy(original['benchmark']['cold_source' if str(path)=='source' else 'cold_smallest_encoded'])
    try:
        with patch.object(benchmark,'answers',flaky_answers),patch.object(benchmark,'cold',replay_cold):
            result=benchmark.run_jrc_benchmark(root)
        accepted_run=True;error=None
    except (ValueError,RuntimeError) as exc:
        accepted_run=False;error=str(exc);result=None
    accepted_proof=False
    if result:
        try:
            validate_benchmark(result,load_jrc(root),benchmark.pinned_plots(root),root/result['smallest_encoded']['store_path'],root)
            accepted_proof=True
        except ValueError as exc:error=str(exc)
    report={'scope':'synthetic negative control; scratch-only archive; cold samples replayed, not new measurements',
            'injected_wrong_measured_answer':injected,'benchmark_runner_accepted':accepted_run,
            'benchmark_proof_accepted':accepted_proof,'error':error,
            'expected':'runner must reject a wrong intermediate timed query answer',
            'actual_archive':result['archive'] if result else None}
    args.report.write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(report,indent=2))
    return int(accepted_run)

if __name__=='__main__':sys.exit(main())
