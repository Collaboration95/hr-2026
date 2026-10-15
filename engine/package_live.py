"""Inventory the optional loopback service and its exact retained input dependencies."""
import argparse,json
from pathlib import Path
from .live_query import LiveSnapshot
from .source import ROOT,canonical_bytes,sha256_file

def manifest(output=None):
    health=LiveSnapshot.load().health()
    paths={f['path'] for f in health['snapshot']['verified_files']}
    paths.update(('engine/__init__.py','engine/live_server.py','engine/package_live.py',
                  'engine/requirements.txt','engine/oracle.py','artifacts/demo-v1.json',
                  'engine/tests/test_live_query.py','engine/tests/test_live_server.py',
                  'docs/lab/engine-live-interface-v1.md','docs/lab/engine-live-report.md'))
    if (ROOT/'engine/tests/__init__.py').exists():paths.add('engine/tests/__init__.py')
    files=[]
    for name in sorted(paths):
        path=ROOT/name
        if not path.resolve().is_relative_to(ROOT) or not path.is_file():raise ValueError('Unsafe/missing live bundle file: '+name)
        files.append({'path':name,'bytes':path.stat().st_size,'sha256':sha256_file(path)})
    result={'schema_version':'plotline.live-bundle.v1','snapshot_id':health['snapshot_id'],
            'retained':health['snapshot']['retained'],'files':files,'total_bytes':sum(f['bytes'] for f in files),
            'notes':['Optional loopback service; frozen Hansen benchmark and cohort stay unchanged.',
                     'All measured retained candidate files are required by startup proof validation.',
                     'No full source tiles, historical stores, generated examples, virtualenv or frontend assets.',
                     'Includes frozen demo only for regression comparison, not as live query input.',
                     'Contains local company inputs; no publication permission.',
                     'Runtime snapshot stays fixed until service restart; no request filesystem writes.']}
    target=Path(output) if output else ROOT/'artifacts/live-bundle-manifest.json'
    target.parent.mkdir(parents=True,exist_ok=True)
    temporary=target.with_suffix('.tmp');temporary.write_bytes(canonical_bytes(result));temporary.replace(target)
    return result
if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--output',type=Path)
    result=manifest(parser.parse_args().output)
    print(json.dumps({'file_count':len(result['files']),'total_bytes':result['total_bytes'],'snapshot_id':result['snapshot_id']},indent=2))
