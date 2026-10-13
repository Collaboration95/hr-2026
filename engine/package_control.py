"""Inventory the current additive strong-control proof and its retained dependencies."""
import argparse
import json
from pathlib import Path
from .source import ROOT, canonical_bytes, sha256_file
from .strong_baseline_measure import verify_artifact


def manifest(output=None):
    artifact_path=ROOT/'artifacts/strong-baseline-v1.json'
    verified=verify_artifact(artifact_path)
    if not verified['valid']:
        raise ValueError('Strong-control artifact failed current verification')
    a=json.loads(artifact_path.read_text())
    accepted=json.loads((ROOT/'artifacts/benchmark-v1.json').read_text())
    paths=set(a['identity']['guard'])
    def add(name):
        path=ROOT/str(name)
        if not path.resolve().is_relative_to(ROOT) or not path.is_file():
            raise ValueError('Required local control bundle file missing/unsafe: '+str(name))
        paths.add(str(path.relative_to(ROOT)))
    for row in a['controls']:
        for f in row['storage']['files']:
            add(Path(row['store_path'])/f['path'])
    for candidate in accepted['candidates']:
        if candidate.get('storage'):
            for f in candidate['storage']['files']:
                add(Path('artifacts/stores')/accepted['experiment_id']/candidate['candidate']/f['path'])
    for f in a['accepted_immutable_files']:
        add(f['path'])
    for name in ('artifacts/strong-baseline-v1.json',a['archive']['path'],
                 f"artifacts/strong-baseline-stores/{a['experiment_id']}/identity.json",
                 'engine/__init__.py','engine/export.py','engine/requirements.txt',
                 'engine/package_control.py','engine/tests/test_strong_baseline.py',
                 'docs/lab/engine-strong-baseline-report.md','docs/lab/engine-strong-baseline-review.md'):
        add(name)
    if (ROOT/'engine/tests/__init__.py').exists():add('engine/tests/__init__.py')
    files=[{'path':name,'bytes':(ROOT/name).stat().st_size,'sha256':sha256_file(ROOT/name)} for name in sorted(paths)]
    result={'schema_version':'plotline.strong-control-bundle.v1','experiment_id':a['experiment_id'],
            'run_id':Path(a['archive']['path']).stem,'accepted_hansen_experiment':accepted['experiment_id'],
            'control_stores':[c['store_path'] for c in a['controls']],
            'files':files,'total_bytes':sum(f['bytes'] for f in files),
            'notes':['Current additive experiment only; accepted Hansen benchmark/store stay unchanged.',
                     'Includes all retained Hansen candidate files required by the existing proof dependency.',
                     'No acquisition full tiles, old experiments, virtualenv or historical scratch caches.',
                     'Bundle bytes include code/proof archives; they are not a codec storage denominator.',
                     'Includes company inputs; inventory does not authorize publication.',
                     'Lead focused positive and rehashed-negative checks pass; a fresh independent validator rerun is not claimed.']}
    target=Path(output) if output else ROOT/'artifacts/strong-baseline-bundle-manifest.json'
    target.parent.mkdir(parents=True,exist_ok=True)
    temp=target.with_suffix('.tmp');temp.write_bytes(canonical_bytes(result));temp.replace(target)
    return result

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--output',type=Path)
    result=manifest(parser.parse_args().output)
    print(json.dumps({'file_count':len(result['files']),'total_bytes':result['total_bytes'],
                      'experiment_id':result['experiment_id'],'run_id':result['run_id']},indent=2))
