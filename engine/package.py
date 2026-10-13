"""Describe the minimal local retained proof bundle; never stage or publish it."""
import argparse
import json
from pathlib import Path
from .export import atomic_json
from .proof import validate_benchmark
from .source import ROOT, load_plots, load_source, object_hash, sha256_file
from .verify import verify_artifact


def manifest(output=None):
    benchmark = json.loads((ROOT/'artifacts/benchmark-v1.json').read_text())
    validate_benchmark(benchmark, load_source(), load_plots())
    checked = verify_artifact(ROOT/'artifacts/demo-v1.json')
    if not checked['valid']:
        raise ValueError('canonical demo is not ready for packaging: '+ '; '.join(checked['failures']))
    selection = benchmark['retained_selection']
    paths = set()
    def add(path):
        path = Path(path)
        if not path.is_absolute():
            path = ROOT/path
        relative = path.resolve().relative_to(ROOT)
        if not path.is_file():
            raise ValueError('required file missing: '+str(relative))
        paths.add(str(relative))
    for p in (ROOT/'engine').rglob('*'):
        if p.is_file() and '__pycache__' not in p.parts and p.suffix in ('.py','.txt','.md'):
            add(p)
    for item in benchmark['baseline']['storage']['files']:
        add(item['path'])
    # Preserve the tiny optional research manifest as evidence, never in the storage denominator.
    for item in benchmark['baseline'].get('research_overhead', {}).get('files', []):
        add(item['path'])
    for candidate in benchmark['candidates']:
        if candidate.get('storage'):
            for item in candidate['storage']['files']:
                add(Path('artifacts/stores')/benchmark['experiment_id']/candidate['candidate']/item['path'])
    for path in benchmark['identity']['input_sha256']:
        add(path)
    exp = benchmark['experiment_id']
    run = benchmark['registry']['run_id']
    for path in ('artifacts/demo-v1.json','artifacts/example-v1.json','artifacts/synthetic-v1.json',
                 'artifacts/benchmark-v1.json','artifacts/experiments/retained-choice.json',
                 f'artifacts/experiments/{exp}/identity.json',f'artifacts/experiments/{exp}/{run}.json',
                 f'artifacts/experiments/selections/choice-{object_hash(selection)}.json',
                 'docs/lab/interface-v1.md','docs/lab/engine-report.md'):
        add(path)
    files = [{'path':p,'bytes':(ROOT/p).stat().st_size,'sha256':sha256_file(ROOT/p)} for p in sorted(paths)]
    result = {'schema_version':'plotline.bundle-manifest.v1','purpose':'local retained proof bundle; no staging/publication performed',
              'experiment_id':exp,'run_id':run,'retained_store':selection['smallest_encoded']['store_path'],
              'files':files,'total_bytes':sum(f['bytes'] for f in files),
              'notes':['Includes every measured candidate in the retained run because the proof gate verifies their files.',
                       'Excludes all other experimental stores/runs, temporary files, virtualenv and source full-tile cache.',
                       'Includes local private supplier data; this manifest is not publication permission.',
                       'The full-tile acquisition cache is optional for original-download readback validation; native verified chips are the runtime inputs.',
                       'Historical research evidence and reports may be selected separately by the integration owner.']}
    atomic_json(output or ROOT/'artifacts/retained-bundle-manifest.json',result)
    return result

if __name__ == '__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path)
    args=parser.parse_args()
    value=manifest(args.output)
    print(json.dumps({'file_count':len(value['files']),'total_bytes':value['total_bytes'],'retained_store':value['retained_store']},indent=2))
