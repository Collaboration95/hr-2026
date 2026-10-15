"""Pinned, isolated full-chip JRC control measurements. All writes local."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import resource
import statistics
import subprocess
import sys
import tempfile
import time
AREA = Path(__file__).resolve().parent
ROOT = AREA.parents[2]
sys.path.insert(0, str(ROOT))

def file_hash(path):
    with Path(path).open('rb') as f:
        return hashlib.file_digest(f, 'sha256').hexdigest()

def pin(paths):
    return {str(Path(p).relative_to(ROOT)): file_hash(p) for p in sorted(set(paths))}

CODE = [*ROOT.glob('engine/jrc*.py'), *[ROOT/'engine'/n for n in ('codecs.py','source.py','model.py','query.py','oracle.py','__init__.py')], *AREA.glob('*.py')]
BOOT = pin(CODE)  # Before importing any project code.
import numpy as np
import rasterio
import shapely
from compression import zstd
from control import encode, decode, storage, require, record, digest
from engine.jrc import load_jrc, evaluate_jrc, CHIP, PROVENANCE, QML, XML
from engine.jrc_codec import decode_jrc_store, encode_jrc_store, read_jrc_index
from engine.jrc_oracle import oracle_jrc
from engine.source import canonical_bytes, object_hash, load_plots, SAMPLE, CSV_NAME, GEOJSON_NAME

REPS, WARMUPS = 7, 2
PLOT_PINS = {str(SAMPLE/CSV_NAME): '43b47916d4900d4bf2f86a8a3ca3ee107f22b1fb80702174bbb9b55403c0fca2',
             str(SAMPLE/GEOJSON_NAME): '8922eef5040120b180a86f6002f52e090ee9bb8273c3c1cf71f984b68648662b'}

def guard_check(guard):
    for name, expected in guard.items():
        require(file_hash(ROOT/name) == expected, 'MIXED RUN: fingerprint changed: '+name)
    for name, expected in BOOT.items():
        require(guard.get(name) == expected, 'MIXED RUN: imported code differs: '+name)


def data_digest(ds):
    return {'raw': digest(ds.values.tobytes()), 'mask': digest(ds.mask.tobytes()),
            'metadata': object_hash(ds.metadata)}


def answers(ds, plots):
    return [evaluate_jrc(ds, p['geometry']) for p in plots]


def equal(ds, expected):
    require(data_digest(ds) == expected, 'full raw/mask/metadata mismatch')


def summary(values):
    return {'samples': values, 'min': min(values), 'median': statistics.median(values),
            'p95_nearest_rank': sorted(values)[-1], 'unit': 'ms'}


def rss():
    return {'value': resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
            'unit': 'bytes' if sys.platform == 'darwin' else 'KiB'}


def load(req):
    # External identity checks are in the timed initialization, including the
    # required manifest/index. Native load also independently checks fixed pins.
    for f in req['representation_files']:
        require(file_hash(ROOT/f) == req['guard'][f], 'initialization identity mismatch: '+f)
    if req['name'] == 'source':
        return load_jrc()
    if req['name'] == 'custom':
        return decode_jrc_store(ROOT/req['store'])
    return decode(ROOT/req['store'])


def worker(req):
    guard_check(req['guard'])
    plots = load_plots()
    operation = req['operation']
    samples = []
    if operation == 'encode':
        source = load_jrc()
        equal(source, req['data_digest'])
        with tempfile.TemporaryDirectory(dir=AREA, prefix='encode-') as tmp:
            for i in range(WARMUPS+REPS):
                guard_check(req['guard'])
                path = Path(tmp)/str(i)
                a,b = time.perf_counter_ns(),time.process_time_ns()
                if req['name'] == 'custom':
                    result = encode_jrc_store(source,path,req['candidate'],req['chunk_size'])
                else:
                    result = encode(source,path,req['level'])
                elapsed = {'wall_ms': (time.perf_counter_ns()-a)/1e6, 'cpu_ms': (time.process_time_ns()-b)/1e6}
                ds = decode_jrc_store(path) if req['name'] == 'custom' else decode(path)
                equal(ds, req['data_digest'])
                actual = [record(p) for p in sorted(path.iterdir())]
                require(actual == req['store_records'], 'nondeterministic encoding bytes')
                elapsed['file_set_sha256'] = object_hash(actual)
                elapsed['full_data_digest'] = data_digest(ds)
                samples.append(elapsed)
                guard_check(req['guard'])
    elif operation == 'hot':
        ds = load(req)
        equal(ds,req['data_digest'])
        for _ in range(WARMUPS+REPS):
            guard_check(req['guard'])
            a,b = time.perf_counter_ns(),time.process_time_ns()
            output = answers(ds,plots)
            elapsed = {'wall_ms': (time.perf_counter_ns()-a)/1e6, 'cpu_ms': (time.process_time_ns()-b)/1e6}
            elapsed['answer_sha256'] = object_hash(output)
            require(elapsed['answer_sha256'] == req['answer_sha256'], 'timed hot answer mismatch')
            samples.append(elapsed)
            guard_check(req['guard'])
        equal(ds,req['data_digest'])
    elif operation == 'cold':
        a,b = time.perf_counter_ns(),time.process_time_ns()
        ds = load(req)
        load_wall,load_cpu = (time.perf_counter_ns()-a)/1e6,(time.process_time_ns()-b)/1e6
        output = answers(ds,plots)
        elapsed = {'wall_ms': (time.perf_counter_ns()-a)/1e6, 'cpu_ms': (time.process_time_ns()-b)/1e6,
                   'load_wall_ms': load_wall, 'load_cpu_ms': load_cpu}
        elapsed['answer_sha256'] = object_hash(output)
        require(elapsed['answer_sha256'] == req['answer_sha256'], 'timed process-cold answer mismatch')
        equal(ds,req['data_digest'])
        samples.append(elapsed)
    else:
        raise ValueError('unknown worker operation')
    guard_check(req['guard'])
    if operation == 'cold':
        return {'sample': samples[0], 'peak_rss': rss()}
    measured = samples[WARMUPS:]
    return {'warmup_samples': samples[:WARMUPS], 'samples': measured,
            'wall_ms': summary([s['wall_ms'] for s in measured]),
            'cpu_ms': summary([s['cpu_ms'] for s in measured]), 'peak_rss': rss()}


def child(req):
    guard_check(req['guard'])
    a = time.perf_counter_ns()
    p = subprocess.run([sys.executable,'-B',str(AREA/'study.py'),'--child'], cwd=ROOT,
                       input=canonical_bytes(req), capture_output=True, timeout=120,
                       env={**os.environ,'PYTHONDONTWRITEBYTECODE':'1','GDAL_NUM_THREADS':'1'})
    outer = (time.perf_counter_ns()-a)/1e6
    if p.returncode:
        raise ValueError('child rejected run: '+p.stderr.decode(errors='replace')[-4000:])
    result = json.loads(p.stdout)
    result['spawn_inclusive_wall_ms'] = outer
    guard_check(req['guard'])
    return result


def measure(req):
    hot = child(dict(req, operation='hot'))
    cold = [child(dict(req,operation='cold')) for _ in range(WARMUPS+REPS)]
    measured = cold[WARMUPS:]
    return {'hot_17_queries': hot, 'process_cold_load_and_17_queries': {
        'warmup_children': cold[:WARMUPS], 'children': measured,
        'wall_ms': summary([c['sample']['wall_ms'] for c in measured]),
        'cpu_ms': summary([c['sample']['cpu_ms'] for c in measured]),
        'spawn_inclusive_wall_ms': summary([c['spawn_inclusive_wall_ms'] for c in measured])}}


def environment():
    import platform
    return {'python':platform.python_version(),'platform':platform.platform(),'machine':platform.machine(),
            'numpy':np.__version__,'rasterio':rasterio.__version__,'gdal':rasterio.__gdal_version__,
            'shapely':shapely.__version__,'python_zstd':list(zstd.zstd_version_info),'logical_cpus':os.cpu_count()}


def write(path, value):
    with Path(path).open('xb') as f:
        f.write(canonical_bytes(value))


def run():
    guard = dict(BOOT)
    input_names = [CHIP,PROVENANCE,QML,XML,str(SAMPLE/CSV_NAME),str(SAMPLE/GEOJSON_NAME),'artifacts/jrc-baseline-v1.json']
    guard.update(pin([ROOT/n for n in input_names]))
    require(all(guard[n] == h for n,h in PLOT_PINS.items()), 'exact real plot inputs changed')
    artifact = json.loads((ROOT/'artifacts/jrc-baseline-v1.json').read_text())
    store_name = artifact['store']['path']
    store = ROOT/store_name
    require(store.resolve().is_relative_to((ROOT/'artifacts/jrc-stores').resolve()), 'unexpected custom store path')
    require({p.name for p in store.iterdir()} == {'index.json','payload.bin'}, 'custom uncounted files')
    guard.update(pin(store.iterdir()))
    guard_check(guard)
    source,plots = load_jrc(),load_plots()
    expected_data = data_digest(source)
    expected = answers(source,plots)
    oracle = [oracle_jrc(source,p['geometry']) for p in plots]
    require(canonical_bytes(expected) == canonical_bytes(oracle), 'source versus independent oracle mismatch')
    require(len(plots) == 17, 'real cohort changed')
    equal(decode_jrc_store(store), expected_data)
    index = read_jrc_index(store)
    identity = {'guard':dict(guard),'metadata':source.metadata,'query_inputs':[
        {'plot_id':p['plot_id'],'geometry':p['geometry']} for p in plots],
        'custom_store':store_name,'repetitions':REPS,'warmups':WARMUPS,'levels':[3,19],'block':1024,
        'environment':environment(),'data_digest':expected_data,'answer_sha256':object_hash(expected)}
    exp = 'exp-'+object_hash(identity)
    stamp = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')
    folder = AREA/exp/stamp
    folder.mkdir(parents=True)
    write(folder/'identity.json',identity)
    source_files = source.metadata['required_inputs']
    rows = [{'name':'source','files':[f['path'] for f in source_files],
             'storage':{'files':source_files,'payload_bytes':source_files[0]['bytes'],
                        'metadata_index_bytes':sum(f['bytes'] for f in source_files[1:]),
                        'total_bytes':sum(f['bytes'] for f in source_files)}},
            {'name':'custom','store':store_name,'candidate':index['candidate'],'chunk_size':index['chunk_size'],
             'files':[str(p.relative_to(ROOT)) for p in sorted(store.iterdir())],
             'storage':{'files':[record(p) for p in sorted(store.iterdir())],
                        'payload_bytes':(store/'payload.bin').stat().st_size,
                        'metadata_index_bytes':(store/'index.json').stat().st_size,
                        'total_bytes':sum(p.stat().st_size for p in store.iterdir())}}]
    for level in (3,19):
        path = folder/f'gtiff_onebit_zstd{level}_b1024'
        size = encode(source,path,level)
        equal(decode(path),expected_data)
        rows.append({'name':path.name,'store':str(path.relative_to(ROOT)),'level':level,'storage':size,
                     'files':[str(p.relative_to(ROOT)) for p in sorted(path.iterdir())]})
        guard.update(pin(path.iterdir()))
    guard_check(guard)
    for row in rows:
        print('measuring '+row['name'], file=sys.stderr, flush=True)
        ds = source if row['name'] == 'source' else decode_jrc_store(ROOT/row['store']) if row['name'] == 'custom' else decode(ROOT/row['store'])
        equal(ds,expected_data)
        require(canonical_bytes(answers(ds,plots)) == canonical_bytes(expected), 'representation query mismatch')
        row['proof'] = {'full_data_digest':data_digest(ds),'pixel_count':int(ds.values.size),
                        'plot_count':len(plots),'answers':answers(ds,plots),'independent_oracle_equal':True}
        req = {**row,'guard':guard,'data_digest':expected_data,'answer_sha256':object_hash(expected),
               'representation_files':row['files']}
        if row['name'] != 'source':
            req['store_records'] = [record(p) for p in sorted((ROOT/row['store']).iterdir())]
            row['encoding'] = child(dict(req,operation='encode'))
        else:
            row['encoding'] = {'measured':False,'reason':'native acquired source; no equivalent acquisition/recompression task measured'}
        row['measurements'] = measure(req)
    guard_check(guard)
    provenance = sum(f['bytes'] for f in source_files[1:])
    plots_bytes = sum((ROOT/SAMPLE/n).stat().st_size for n in (CSV_NAME,GEOJSON_NAME))
    result = {'schema':'research.jrc-standard-study.v1','identity':identity,'measurement_guard':guard,
              'experiment_id':exp,'created_utc':stamp,'representations':rows,'oracle_answers':oracle,
              'storage_views':{'source_chip_only_bytes':source_files[0]['bytes'],'common_provenance_bytes':provenance,
                  'common_plot_input_bytes':plots_bytes,
                  'common_input_files':[{'path':n,'bytes':(ROOT/n).stat().st_size,'sha256':file_hash(ROOT/n)} for n in input_names[1:6]],
                  'totals_with_same_provenance_and_exact_plot_inputs':{
                      row['name']:row['storage']['total_bytes']+plots_bytes+(0 if row['name']=='source' else provenance) for row in rows}},
              'method':{'cache':'OS cache not evicted; guards pre-read files; process-cold, never disk-cold',
                  'query':'17 full dictionaries on preloaded native arrays; original global JRC center lattice',
                  'cold':'new ordinary Python process per repetition/warmup; imports and plot read excluded from inner load+query time; startup-inclusive wall separately',
                  'integrity':'whole-file expected hashes including manifest/index inside every initialization; additional format/decoder integrity checks retained',
                  'all_samples':'all nine hot/encode calls and all nine cold children validated; seven retained timing samples plus two recorded warmups',
                  'validation_timing':'answer/full-array digests and guard checks outside inner timing; loaders own checks inside',
                  'rss':'isolated child lifetime peak, imports/validation included; encode child contains nine trials, not incremental memory',
                  'encoding':'source already loaded; new files, manifest and encoder validation; buffered writes without fsync; deterministic bytes checked each trial',
                  'p95':'nearest rank, maximum of seven samples',
                  'order':[row['name'] for row in rows],
                  'scope':'one seen sparse native JRC chip; not universal format superiority or legal/source accuracy; no indexed measurements',
                  'production_choice_changed':False},
              'commands':['.venv-data/bin/python -B data/experimental/jrc-standard/test_control.py',
                          '.venv-data/bin/python -B data/experimental/jrc-standard/study.py'],
              'scientific_decision':{
                  'smallest_required_store':min(rows,key=lambda row:row['storage']['total_bytes'])['name'],
                  'standard19_minus_custom_bytes':rows[3]['storage']['total_bytes']-rows[1]['storage']['total_bytes'],
                  'fastest_process_cold_in_this_run':min(rows,key=lambda row:row['measurements']['process_cold_load_and_17_queries']['wall_ms']['median'])['name'],
                  'fastest_encoding_in_this_run':min(rows[1:],key=lambda row:row['encoding']['cpu_ms']['median'])['name'],
                  'decision':'Retain both standard controls as research evidence. Level19 challenges custom storage; custom load/RSS and fast-level3 encoding are separate tradeoffs. Lead decides any production adapter.',
                  'production_choice_changed':False}}
    run_id = 'run-'+object_hash(result)
    output = folder/(run_id+'.json')
    write(output,result)
    guard_check(guard)
    pointer = {'path':str(output.relative_to(ROOT)),'sha256':file_hash(output),'run_id':run_id}
    # Pointer is only within our owned scratch area. Prior immutable runs remain.
    (AREA/'latest.json').write_bytes(canonical_bytes(pointer))
    return pointer


def verify(pointer):
    pointer = json.loads(Path(pointer).read_text())
    path = ROOT/pointer['path']
    require(path.resolve().is_relative_to(AREA.resolve()), 'archive outside research area')
    require(file_hash(path) == pointer['sha256'], 'archive file hash mismatch')
    result = json.loads(path.read_text())
    require(path.stem == pointer['run_id'] == 'run-'+object_hash(result), 'archive content identity mismatch')
    require(result['experiment_id'] == 'exp-'+object_hash(result['identity']), 'experiment identity mismatch')
    require(json.loads((path.parent/'identity.json').read_text()) == result['identity'], 'archived identity mismatch')
    guard_check(result['measurement_guard'])
    require(all(result['measurement_guard'].get(k) == v for k,v in result['identity']['guard'].items()), 'measurement identity changed')
    source,plots=load_jrc(),load_plots()
    expected=answers(source,plots)
    expected_hash=object_hash(expected)
    require(canonical_bytes(expected) == canonical_bytes([oracle_jrc(source,p['geometry']) for p in plots]), 'oracle differs')
    require(result['oracle_answers'] == expected, 'archived oracle differs')
    require(result['identity']['data_digest'] == data_digest(source), 'archived full data differs')
    require(result['identity']['query_inputs'] == [{'plot_id':p['plot_id'],'geometry':p['geometry']} for p in plots], 'plot binding differs')
    artifact=json.loads((ROOT/'artifacts/jrc-baseline-v1.json').read_text())
    require(artifact['store']['path'] == result['identity']['custom_store'], 'custom store binding differs')
    expected_names=set(BOOT)|{f['path'] for f in source.metadata['required_inputs']}|set(PLOT_PINS)|{'artifacts/jrc-baseline-v1.json'}
    expected_names.update(n for row in result['representations'] for n in row['files'])
    require(set(result['measurement_guard'])==expected_names,'required measurement fingerprints missing/extra')
    sizes={}
    for row in result['representations']:
        if row['name']=='source':
            ds=source
            files=source.metadata['required_inputs']
            require(row['storage']['files']==files, 'source required files differ')
            size=sum(f['bytes'] for f in files)
        else:
            store=ROOT/row['store']
            ds=decode_jrc_store(store) if row['name']=='custom' else decode(store)
            actual=[record(p) for p in sorted(store.iterdir())]
            require(sorted(row['storage']['files'],key=lambda f:f['path'])==actual, 'recorded file accounting differs')
            size=sum(f['bytes'] for f in actual)
            if row['name']!='custom':
                require(row['storage']==storage(store), 'control accounting differs')
            else:
                require(row['store']==result['identity']['custom_store'], 'custom representation binding differs')
            enc=row['encoding']
            require(len(enc['samples'])==REPS and len(enc['warmup_samples'])==WARMUPS,'encode sample count')
            for sample in enc['warmup_samples']+enc['samples']:
                require(sample['file_set_sha256']==object_hash(actual) and sample['full_data_digest']==data_digest(source),'encode sample proof differs')
            for key in ('wall_ms','cpu_ms'):
                require(enc[key]==summary([s[key] for s in enc['samples']]),'encode summary differs')
        equal(ds,data_digest(source))
        require(row['proof']['full_data_digest']==data_digest(source) and row['proof']['answers']==expected
                and row['proof']['pixel_count']==source.values.size and row['proof']['plot_count']==17
                and row['proof']['independent_oracle_equal'] is True,'proof claim differs')
        require(answers(ds,plots)==expected,'full queries differ')
        require(row['storage']['total_bytes']==size,'total necessary bytes differ')
        sizes[row['name']]=size
        hot=row['measurements']['hot_17_queries']
        cold=row['measurements']['process_cold_load_and_17_queries']
        require(len(hot['samples'])==REPS and len(hot['warmup_samples'])==WARMUPS,'hot sample count')
        require(len(cold['children'])==REPS and len(cold['warmup_children'])==WARMUPS,'cold sample count')
        for sample in hot['warmup_samples']+hot['samples']+[c['sample'] for c in cold['warmup_children']+cold['children']]:
            require(sample['answer_sha256']==expected_hash,'measured answer hash differs')
        for key in ('wall_ms','cpu_ms'):
            require(hot[key]==summary([s[key] for s in hot['samples']]),'hot summary differs')
            require(cold[key]==summary([c['sample'][key] for c in cold['children']]),'cold summary differs')
        require(cold['spawn_inclusive_wall_ms']==summary([c['spawn_inclusive_wall_ms'] for c in cold['children']]),'startup summary differs')
    common=result['storage_views']
    provenance=sum(f['bytes'] for f in source.metadata['required_inputs'][1:])
    plots_bytes=sum((ROOT/n).stat().st_size for n in PLOT_PINS)
    require(common['common_provenance_bytes']==provenance and common['common_plot_input_bytes']==plots_bytes,'common accounting differs')
    require(common['totals_with_same_provenance_and_exact_plot_inputs']=={n:s+plots_bytes+(0 if n=='source' else provenance) for n,s in sizes.items()},'symmetric totals differ')
    guard_check(result['measurement_guard'])
    return {'valid':True,'representations':len(sizes),'real_plots':17,'pixels':int(source.values.size),'run_id':pointer['run_id']}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--child',action='store_true')
    parser.add_argument('--verify',type=Path)
    args = parser.parse_args()
    if args.verify:
        print(json.dumps(verify(args.verify),indent=2))
    elif args.child:
        print(json.dumps(worker(json.load(sys.stdin)),allow_nan=False))
    else:
        try:
            print(json.dumps(run(),indent=2))
        except Exception as exc:
            stamp=datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')
            write(AREA/('failed-'+stamp+'.json'), {'status':'rejected','error':str(exc),'boot_code':BOOT})
            raise

if __name__ == '__main__':
    main()
