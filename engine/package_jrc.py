"""Inventory the separate JRC proof bundle without staging or copying files."""
import argparse
import json
from pathlib import Path

from .jrc import ROOT, SOURCE
from .jrc_proof import local, read_json, verify_jrc_artifact
from .source import canonical_bytes, sha256_file


def manifest(root=ROOT, artifact='artifacts/jrc-baseline-v1.json', output=None):
    root = Path(root).resolve()
    artifact_path = local(root, artifact)
    checked = verify_jrc_artifact(artifact_path, root=root)
    if not checked['valid']:
        raise ValueError('JRC companion is not ready for packaging: '+str(checked))
    data = read_json(artifact_path)
    benchmark = data['benchmark']
    if benchmark is None:
        raise ValueError('JRC proof bundle requires an explicitly bound measurement')
    paths = set()

    def add(name):
        path = local(root, str(name))
        if not path.is_file():
            raise ValueError('JRC bundle file missing: '+str(name))
        paths.add(str(path.relative_to(root)))

    for record in benchmark['identity']['implementation']:
        add(record['path'])
    for record in benchmark['identity']['inputs']:
        add(record['path'])
    for candidate in benchmark['candidates']:
        for record in candidate['storage']['files']:
            add(record['path'])
    add(artifact)
    add(benchmark['archive']['path'])
    add(f"artifacts/jrc-stores/{benchmark['experiment_id']}/identity.json")
    for name in ('engine/__init__.py', 'engine/requirements.txt', 'engine/package_jrc.py',
                 'docs/lab/engine-jrc-interface.md', 'docs/lab/engine-jrc-report.md',
                 'docs/lab/engine-jrc-task.md'):
        add(name)
    for path in sorted((root/'engine/tests').glob('test_jrc*.py')):
        add(path.relative_to(root))
    if (root/'engine/tests/__init__.py').exists():
        add('engine/tests/__init__.py')
    if SOURCE in paths:
        raise ValueError('Optional full acquisition tile must not enter the runtime proof bundle')
    files = [{'path': name, 'bytes': (root/name).stat().st_size,
              'sha256': sha256_file(root/name)} for name in sorted(paths)]
    result = {
        'schema_version': 'plotline.jrc-bundle-manifest.v1',
        'experiment_id': benchmark['experiment_id'],
        'run_id': benchmark['archive']['run_id'],
        'artifact': artifact,
        'selected_store': data['store']['path'],
        'files': files,
        'total_bytes': sum(record['bytes'] for record in files),
        'notes': [
            'Separate native-grid JRC component; no accepted Hansen artifact or measurement is replaced.',
            'All measured candidate files are included because the proof gate verifies each candidate.',
            'Excludes the optional 197739699-byte source acquisition tile, other experiments and the virtualenv.',
            'Without the acquisition tile, verification checks the bound archived readback claim; it cannot reread the absent tile.',
            'Bundle bytes include proof outputs/code and are not a compression denominator.',
            'Contains original company geometry/CSV inputs; this manifest grants no publication permission.',
            'Generation validates current evidence; release acceptance also requires independent review and a clean-bundle smoke test.',
        ],
    }
    destination = Path(output) if output else root/'artifacts/jrc-bundle-manifest.json'
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = destination.with_suffix('.tmp')
    temporary.write_bytes(canonical_bytes(result))
    temporary.replace(destination)
    return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path)
    args = parser.parse_args()
    result = manifest(output=args.output)
    print(json.dumps({key: result[key] for key in ('experiment_id', 'run_id', 'total_bytes', 'selected_store')}
                     | {'file_count': len(result['files'])}, indent=2))
