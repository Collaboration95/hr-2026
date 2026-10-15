"""Fresh accepted positive controls paired with individually corrupted proofs.
Writes only validation/fix-verification and docs/lab/validator-fix-engine.json.
"""
from copy import deepcopy
import json
from pathlib import Path
import sys
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from engine.export import export
from engine.verify import verify_artifact
from engine.source import load_source, sha256_file
from engine.codecs import encode_store
from validation.repro_proof_gaps import resign, write


def main():
    base = ROOT/'validation/fix-verification'
    base.mkdir(parents=True, exist_ok=True)
    watched = [*sorted((ROOT/'engine').glob('*.py')), ROOT/'artifacts/demo-v1.json', ROOT/'artifacts/benchmark-v1.json', ROOT/'artifacts/experiments/retained-choice.json']
    before = {str(p.relative_to(ROOT)): sha256_file(p) for p in watched}
    positive = export(output=base/'positive/demo-v1.json')
    positive_check = verify_artifact(base/'positive/demo-v1.json')
    if not positive_check['valid']:
        raise RuntimeError('No fresh positive control: '+str(positive_check))
    positive = json.loads((base/'positive/demo-v1.json').read_text())
    store = ROOT/positive['plots'][0]['receipt']['compact_store']['path']
    unmeasured = export(store, output=base/'metric-free/demo-v1.json', include_benchmark=False)
    unmeasured_check = verify_artifact(base/'metric-free/demo-v1.json')
    assert unmeasured_check['valid'], unmeasured_check
    unmeasured = json.loads((base/'metric-free/demo-v1.json').read_text())
    report = {'positive':positive_check, 'metric_free_positive':unmeasured_check,
              'positive_content':positive['content_sha256'], 'retained':positive['benchmark']['retained_selection'], 'negative_controls':[]}
    def negative(label, artifact, expected):
        resign(artifact)
        path = base/(label+'.json')
        write(path, artifact)
        actual = verify_artifact(path)
        targeted = any(expected in message for message in actual['failures'])
        report['negative_controls'].append({'label':label,'expected_failure':expected,'pass':not actual['valid'] and targeted,'actual':actual})
    for label, mutate, expected in [
        ('wrong-vintage',lambda d:d['benchmark']['identity']['source_metadata'].update(product='WRONG VALIDATOR VINTAGE'),'source metadata'),
        ('wrong-cohort',lambda d:d['benchmark']['identity'].update(queries_sha256='0'*64),'query cohort'),
        ('forged-measured-size',lambda d:d['benchmark']['baseline']['storage'].update(total_bytes=1),'measured archive differs'),
        ('receipt-version',lambda d:d['plots'][0]['receipt'].update(query_version='wrong.v99'),'receipt contract'),
        ('receipt-period',lambda d:d['plots'][0]['receipt'].update(observed_periods={'2021-2023':[2099,2099]}),'receipt contract'),
        ('summary-count',lambda d:d['summary'].update(selected_cell_count_sum=1),'derived summary'),
        ('receipt-source',lambda d:d['plots'][0]['receipt']['sources'][0].update(sha256='0'*64),'receipt contract'),
    ]:
        fixture = deepcopy(positive)
        mutate(fixture)
        negative(label,fixture,expected)
    # Reuse the original one-off-plot-pixel reproducer, but remove benchmark
    # claims so rejecting a non-retained path cannot mask the pixel-fidelity gate.
    source = load_source()
    for kind in ('raw','mask'):
        bands, masks = source.bands.copy(), source.masks.copy()
        if kind == 'raw': bands[0,0,0] = (int(bands[0,0,0])+1)%101
        else: masks[0,0,0] = not masks[0,0,0]
        corrupt = base/(kind+'-offplot-store')
        encode_store(bands,masks,source.metadata,corrupt,'separate_zstd',256)
        files = [{'path':p.name,'bytes':p.stat().st_size,'sha256':sha256_file(p)} for p in sorted(corrupt.iterdir())]
        fixture = deepcopy(unmeasured)
        for p in fixture['plots']:
            p['receipt']['compact_store'] = {'path':str(corrupt.relative_to(ROOT)),'files':files,'raw_bands_equal':True,'band_masks_equal':True}
        negative(kind+'-offplot',fixture,'full raw-value fidelity' if kind=='raw' else 'full band-mask fidelity')
        try:
            export(corrupt,output=base/(kind+'-must-not-export/demo-v1.json'),include_benchmark=False)
            rejected = False
            error = 'accepted'
        except ValueError as exc:
            rejected = 'full raw-value or mask fidelity' in str(exc)
            error = str(exc)
        report['negative_controls'].append({'label':kind+'-export','pass':rejected,'error':error})
    # Inject one wrong benchmark body into this process's read only. All other
    # real files remain accessible, proving rejection is not a missing-root gate.
    fake = deepcopy(positive['benchmark'])
    fake['identity']['queries_sha256'] = '0'*64
    original_read = Path.read_text
    def read_fixture(path, *args, **kwargs):
        if path == ROOT/'artifacts/benchmark-v1.json': return json.dumps(fake)
        return original_read(path,*args,**kwargs)
    with patch.object(Path,'read_text',read_fixture):
        try:
            export(output=base/'wrong-benchmark-must-not-export/demo-v1.json')
            rejected,error = False,'accepted'
        except ValueError as exc:
            rejected,error = 'query cohort' in str(exc),str(exc)
    report['negative_controls'].append({'label':'upstream-export-wrong-benchmark','pass':rejected,'error':error})
    benchmark = positive['benchmark']
    report['baseline'] = benchmark['baseline']
    report['required_baseline_sum'] = sum((ROOT/f['path']).stat().st_size for f in benchmark['baseline']['storage']['files'])
    report['required_baseline_paths'] = [f['path'] for f in benchmark['baseline']['storage']['files']]
    report['canonical_equals_fresh_positive'] = json.loads((ROOT/'artifacts/demo-v1.json').read_text()) == positive
    report['stable_files'] = before == {str(p.relative_to(ROOT)):sha256_file(p) for p in watched}
    report['pass'] = all(p['pass'] for p in report['negative_controls']) and report['stable_files'] and report['canonical_equals_fresh_positive'] and report['required_baseline_sum']==585293
    write(ROOT/'docs/lab/validator-fix-engine.json',report)
    print(json.dumps({k:v for k,v in report.items() if k not in ('baseline','negative_controls')},indent=2))
    for p in report['negative_controls']: print(p['label'],p['pass'],p.get('error',p.get('actual',{}).get('failures')))
    return int(not report['pass'])

if __name__=='__main__': sys.exit(main())
