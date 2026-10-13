"""Isolated, additive GeoTIFF-control measurements and recomputable proof."""
import argparse
from compression import zstd
from copy import deepcopy
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time

import numpy as np

from .benchmark import environment, rss_record, summarize, differing_fields
from .codecs import decode_store, encode_store, _json_types
from .indexed import SourceWindowReader, CompactWindowReader, evaluate_reader
from .model import Dataset, QUERY_VERSION
from .oracle import oracle_evaluate
from .proof import validate_benchmark
from .query import evaluate
from .source import ROOT, SAMPLE, CSV_NAME, GEOJSON_NAME, load_source, load_plots, sha256_file, canonical_bytes
from .strong_baseline import encode_control, decode_control, ControlWindowReader, storage_info, digest, _settings, _pairs, _constant
from .strong_baseline_validation import same, fields, integer, number, sha, settings, measurements, preprocessing

AREA = ROOT / 'artifacts/strong-baseline-stores'
SCRATCH = ROOT / 'data/experimental/strong-baseline'
CODE_NAMES = ('strong_baseline.py', 'strong_baseline_measure.py', 'model.py', 'source.py',
              'query.py', 'indexed.py', 'codecs.py', 'oracle.py', 'proof.py', 'benchmark.py', 'experiments.py', 'export.py', 'strong_baseline_validation.py')
IMPORTED_CODE = {f'engine/{n}': sha256_file(ROOT / 'engine' / n) for n in CODE_NAMES}


def atomic_json(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(dir=path.parent, prefix='.' + path.name)
    try:
        with os.fdopen(fd, 'wb') as stream:
            stream.write(canonical_bytes(value) + b'\n')
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        Path(temporary).unlink(missing_ok=True)


def file_record(path, base=ROOT):
    path = Path(path)
    return {'path': str(path.relative_to(base)), 'bytes': path.stat().st_size, 'sha256': sha256_file(path)}


def check_files(files, base=ROOT):
    for f in files:
        fields(f, ('path','bytes','sha256'), 'file record')
        integer(f['bytes'],1,2**63-1,'file bytes')
        sha(f['sha256'],'file hash')
        if type(f['path']) is not str or Path(f['path']).is_absolute():
            raise ValueError('proof file path must be relative')
        p = Path(base) / f['path']
        if not p.resolve().is_relative_to(Path(base).resolve()):
            raise ValueError('proof file path escapes its base')
        if not p.is_file() or p.is_symlink() or p.stat().st_size != f['bytes'] or sha256_file(p) != f['sha256']:
            raise ValueError('measured file changed: ' + str(p))


def check_guard(guard):
    if type(guard) is not dict:
        raise ValueError('guard must be an object')
    for name, expected in guard.items():
        if type(name) is not str or Path(name).is_absolute() or not (ROOT/name).resolve().is_relative_to(ROOT.resolve()):
            raise ValueError('guard path escapes repository')
        sha(expected, 'guard digest')
        if sha256_file(ROOT / name) != expected:
            raise RuntimeError('strong-baseline fingerprint race: ' + name)


def accepted_context():
    benchmark_path = ROOT / 'artifacts/benchmark-v1.json'
    benchmark = json.loads(benchmark_path.read_text())
    data, plots = load_source(), load_plots()
    store = validate_benchmark(benchmark, data, plots)
    selection = benchmark['retained_selection']
    files = [benchmark_path, ROOT / 'artifacts/experiments/retained-choice.json',
             ROOT / 'artifacts/experiments' / benchmark['registry']['result_path'],
             ROOT / 'artifacts/experiments' / benchmark['experiment_id'] / 'identity.json',
             ROOT / 'artifacts/experiments/selections' / ('choice-' + digest(selection) + '.json')]
    files += sorted(store.iterdir())
    return benchmark, data, plots, store, [file_record(p) for p in files]


def prove_dataset(original, restored, plots):
    """Full grid checks precede plot checks: off-plot changes cannot hide."""
    if not np.array_equal(original.bands, restored.bands):
        raise ValueError('full raw band mismatch, including off-plot/masked cells')
    if not np.array_equal(original.masks, restored.masks):
        raise ValueError('full independent mask mismatch')
    if canonical_bytes(original.metadata) != canonical_bytes(restored.metadata):
        raise ValueError('exact source reconstruction metadata mismatch')
    comparisons = []
    for plot in plots:
        a, b = evaluate(original, plot['geometry']), evaluate(restored, plot['geometry'])
        oracle = oracle_evaluate(original, plot['geometry'])
        diff = differing_fields(a, b)
        odiff = differing_fields(oracle, b)
        comparisons.append({'plot_id': plot['plot_id'], 'equal': not diff,
                            'differing_fields': diff, 'oracle_differing_fields': odiff,
                            'result_sha256': digest(b)})
    if any(c['differing_fields'] or c['oracle_differing_fields'] for c in comparisons):
        raise ValueError('source/control/independent oracle query mismatch')
    return {'raw_values_equal': True, 'independent_masks_equal': True, 'metadata_equal': True,
            'spatial_cells': int(original.bands.shape[1] * original.bands.shape[2]),
            'raw_values_checked': int(original.bands.size), 'mask_entries_checked': int(original.masks.size),
            'raw_values_sha256': hashlib.sha256(restored.bands.tobytes()).hexdigest(),
            'raw_masks_sha256': hashlib.sha256(restored.masks.tobytes()).hexdigest(),
            'real_plot_count': len(plots), 'exact_query_count': len(comparisons),
            'independent_oracle_exact_count': len(comparisons), 'comparisons': comparisons}


def _load_rep(request):
    # Count expected metadata-file hash verification within initialization for
    # every format. Native loaders then verify all raster/payload files too.
    check_files([request['metadata_file']])
    representation, mode = request['representation'], request['mode']
    if mode == 'indexed':
        return (SourceWindowReader() if representation == 'source' else
                CompactWindowReader(ROOT / request['store']) if representation == 'custom' else
                ControlWindowReader(ROOT / request['store']))
    return (load_source() if representation == 'source' else
            Dataset(*decode_store(ROOT / request['store'])).validate() if representation == 'custom' else
            decode_control(ROOT / request['store']))


def worker(request):
    check_guard(request['guard'])
    if request['operation'] in ('encode', 'encode_custom'):
        data = load_source()
        if request['operation'] == 'encode':
            report = encode_control(data, Path(request['store']), request['block_size'])
        else:
            t, cpu = time.perf_counter_ns(), time.process_time_ns()
            report = encode_store(data.bands, data.masks, data.metadata, Path(request['store']),
                                  request['candidate'], request['chunk_size'])
            report.update(encode_wall_ms=(time.perf_counter_ns()-t)/1e6,
                          encode_cpu_ms=(time.process_time_ns()-cpu)/1e6)
        result = {'report': report, 'peak_rss': rss_record()}
    else:
        plots = load_plots()
        t, cpu = time.perf_counter_ns(), time.process_time_ns()
        loaded = _load_rep(request)
        load_ms, load_cpu = (time.perf_counter_ns()-t)/1e6, (time.process_time_ns()-cpu)/1e6
        try:
            def batch():
                query = evaluate_reader if request['mode'] == 'indexed' else evaluate
                return [query(loaded, p['geometry']) for p in plots]
            if request['operation'] == 'cold':
                t, cpu = time.perf_counter_ns(), time.process_time_ns()
                answers = batch()
                query_ms, query_cpu = (time.perf_counter_ns()-t)/1e6, (time.process_time_ns()-cpu)/1e6
                result = {'wall_ms': load_ms+query_ms, 'cpu_ms': load_cpu+query_cpu,
                          'load_ms': load_ms, 'load_cpu_ms': load_cpu, 'query_ms': query_ms,
                          'query_cpu_ms': query_cpu, 'answer_sha256': digest(answers), 'peak_rss': rss_record()}
            else:
                for _ in range(request['warmups']):
                    batch()
                walls, cpus, answers_hash = [], [], []
                for _ in range(request['repetitions']):
                    t, cpu = time.perf_counter_ns(), time.process_time_ns()
                    answers = batch()
                    walls.append((time.perf_counter_ns()-t)/1e6)
                    cpus.append((time.process_time_ns()-cpu)/1e6)
                    answers_hash.append(digest(answers))
                result = {'wall_ms': summarize(walls), 'cpu_ms': summarize(cpus),
                          'initialization_ms_excluded': load_ms, 'answer_sha256': sorted(set(answers_hash)),
                          'peak_rss': rss_record()}
        finally:
            if request['mode'] == 'indexed':
                loaded.close()
    check_guard(request['guard'])
    return result


def child(request):
    env = dict(os.environ, PYTHONDONTWRITEBYTECODE='1', GDAL_NUM_THREADS='1',
               OMP_NUM_THREADS='1', OPENBLAS_NUM_THREADS='1', MKL_NUM_THREADS='1', VECLIB_MAXIMUM_THREADS='1')
    started = time.perf_counter_ns()
    completed = subprocess.run([sys.executable, '-B', '-m', 'engine.strong_baseline_measure', '--worker'],
                               input=canonical_bytes(request), capture_output=True, cwd=ROOT, env=env, timeout=120)
    if completed.returncode:
        raise RuntimeError(completed.stderr.decode(errors='replace')[-5000:])
    result = json.loads(completed.stdout)
    result['subprocess_wall_ms'] = (time.perf_counter_ns()-started)/1e6
    return result


def measure(request, expected):
    measurements = {}
    for mode in ('full', 'indexed'):
        hot = child(dict(request, mode=mode, operation='hot'))
        cold = [child(dict(request, mode=mode, operation='cold')) for _ in range(request['repetitions'])]
        if hot['answer_sha256'] != [expected] or any(c['answer_sha256'] != expected for c in cold):
            raise ValueError('timed full/indexed result digest mismatch')
        measurements[mode] = {'hot': hot, 'process_cold': {
            key: summarize([c[key] for c in cold]) for key in
            ('wall_ms', 'cpu_ms', 'load_ms', 'load_cpu_ms', 'query_ms', 'query_cpu_ms', 'subprocess_wall_ms')},
            'process_cold_peak_rss': [c['peak_rss'] for c in cold],
            'process_cold_answer_sha256': [c['answer_sha256'] for c in cold],
            'all_timed_answers_exact': True, 'expected_answer_sha256': expected}
    return measurements


def method_record(candidates, repetitions, warmups):
    return {'cohort': '17 real plots on same full604x1233 AOI; controls selected on this seen AOI',
                  'query': 'original global center lattice for full and indexed queries; no shifted-window reselection',
                  'scope': 'ms per17-query batch; full loads and initialized indexed readers measured separately',
                  'integrity': 'all stored raster/payload files hashed during initialization; expected metadata-file SHA checked for every path',
                  'indexed_granularity': 'custom additionally checks selected chunk hashes per read; TIFF readers rely on whole-file verification at initialization and GDAL decoding',
                  'cache': 'guards hash every representation before operations; OS file cache likely warm, never disk-cold. Hot TIFF handles retain GDAL block cache; custom has no decoded-chunk cache',
                  'independent_masks': 'real masks all valid checked; nontrivial masks use independently packed3-band zstd stream loaded at initialization',
                  'warmups': warmups, 'repetitions': repetitions, 'p95': 'nearest rank; seven samples gives maximum',
                  'resources': 'isolated child lifetime RSS includes imports/inputs; native platform units retained',
                  'preprocessing': 'one encode per candidate in isolated child, source load excluded; custom reproduced byte-identically in owned scratch without changing accepted store',
                  'process_cold': 'new child per sample; load/hash-validation+17 queries timed; startup inclusive separately',
                  'excluded': ['UI', 'network', 'full-tile cropping savings', 'legal/source truth', 'universal-format superiority'],
                  'execution_order': ['source', 'accepted_custom'] + [c['candidate'] for c in candidates],
                  'confidence': 'one seen AOI, small timing sample, uncontrolled host scheduling; no population confidence interval'}


def run(block_sizes=(256,), repetitions=7, warmups=2):
    if (not block_sizes or len(set(block_sizes)) != len(block_sizes) or
            any(type(b) is not int or b not in (256, 512) for b in block_sizes)
            or type(repetitions) is not int or not 1 <= repetitions <= 100
            or type(warmups) is not int or not 0 <= warmups <= 100):
        raise ValueError('bounded block sizes256/512, repetitions1..100 and warmups0..100 required')
    check_guard(IMPORTED_CODE)
    accepted, data, plots, custom_store, accepted_files = accepted_context()
    source_files = [file_record(ROOT / s['path']) for s in data.metadata['sources']]
    provenance = file_record(ROOT / 'data/public/provenance.json')
    cohort_files = [file_record(ROOT / SAMPLE / n) for n in (CSV_NAME, GEOJSON_NAME)]
    guard = dict(IMPORTED_CODE)
    guard.update({f['path']: f['sha256'] for f in source_files + [provenance] + cohort_files + accepted_files})
    check_guard(guard)
    expected = digest([evaluate(data, p['geometry']) for p in plots])
    # Oracle proof is computed before accepting any performance result.
    source_proof = prove_dataset(data, data, plots)
    custom_proof = prove_dataset(data, Dataset(*decode_store(custom_store)).validate(), plots)
    identity = {'schema': 'plotline.strong-baseline.identity.v1', 'guard': dict(guard),
                'accepted_benchmark': file_record(ROOT / 'artifacts/benchmark-v1.json'),
                'accepted_store_path': str(custom_store.relative_to(ROOT)),
                'metadata': data.metadata, 'queries_sha256': digest([p['geometry'] for p in plots]),
                'query_version': QUERY_VERSION,
                'settings': {'block_sizes': list(block_sizes), 'level': 19, 'predictor': 1,
                             'interleave': 'band', 'repetitions': repetitions, 'warmups': warmups},
                'seen_aoi_not_heldout': True,
                'preliminary_selector_audit_sha256': sha256_file(ROOT / 'data/experimental/selector/aoi-control-results.json')}
    exp_id = 'exp-' + digest(identity)
    folder = AREA / exp_id
    folder.mkdir(parents=True, exist_ok=True)
    identity_path = folder / 'identity.json'
    if identity_path.exists() and canonical_bytes(json.loads(identity_path.read_text())) != canonical_bytes(identity):
        raise ValueError('strong control identity collision')
    if not identity_path.exists():
        atomic_json(identity_path, identity)
    SCRATCH.mkdir(parents=True, exist_ok=True)
    candidates = []
    for block in block_sizes:
        name = f'gtiff_zstd19_p1_b{block}'
        store = folder / name
        request = {'operation': 'encode', 'block_size': block, 'guard': guard, 'store': str(store)}
        if store.exists():
            with tempfile.TemporaryDirectory(dir=SCRATCH, prefix='repeat-') as tmp:
                preprocessing = child(dict(request, store=str(Path(tmp) / name)))
                if storage_info(Path(tmp) / name) != storage_info(store):
                    raise ValueError('repeat GeoTIFF encoding changed bytes; prior evidence retained')
        else:
            preprocessing = child(request)
        candidate = {'candidate': name, 'store_path': str(store.relative_to(ROOT)),
                     'block_size': block, 'storage': storage_info(store), 'preprocessing': preprocessing,
                     'proof': prove_dataset(data, decode_control(store), plots)}
        candidates.append(candidate)
    # Pin every generated file during timing as well as all immutable inputs.
    for c in candidates:
        for f in c['storage']['files']:
            guard[str(Path(c['store_path']) / f['path'])] = f['sha256']
    request = {'guard': guard, 'repetitions': repetitions, 'warmups': warmups}
    source = {'storage': {'total_bytes': sum(f['bytes'] for f in source_files + [provenance]),
                          'files': source_files + [provenance]}, 'proof': source_proof}
    source['measurements'] = measure(dict(request, representation='source', metadata_file=provenance), expected)
    custom_files = [file_record(p, custom_store) for p in sorted(custom_store.iterdir())]
    accepted_index = json.loads((custom_store / 'index.json').read_text())
    with tempfile.TemporaryDirectory(dir=SCRATCH, prefix='custom-reencode-') as tmp:
        shadow = Path(tmp) / 'store'
        custom_encode = child(dict(request, operation='encode_custom', store=str(shadow),
                                   candidate=accepted_index['candidate'], chunk_size=accepted_index['chunk_size']))
        if [file_record(p, shadow) for p in sorted(shadow.iterdir())] != custom_files:
            raise ValueError('custom scratch reproduction differs from immutable accepted store')
    custom = {'store_path': str(custom_store.relative_to(ROOT)),
              'storage': {'total_bytes': sum(f['bytes'] for f in custom_files), 'files': custom_files},
              'proof': custom_proof,
              'preprocessing': dict(custom_encode, remeasured=True, byte_identical_scratch_reproduction=True)}
    custom['measurements'] = measure(dict(request, representation='custom', store=custom['store_path'],
                                         metadata_file=file_record(custom_store / 'index.json')), expected)
    for c in candidates:
        c['measurements'] = measure(dict(request, representation='control', store=c['store_path'],
                                        metadata_file=file_record(ROOT / c['store_path'] / 'manifest.json')), expected)
    check_guard(guard)
    best = min(candidates, key=lambda c: (c['storage']['total_bytes'], c['candidate']))
    all_sizes = {'source': source['storage']['total_bytes'], 'accepted_custom': custom['storage']['total_bytes'],
                 **{c['candidate']: c['storage']['total_bytes'] for c in candidates}}
    supplier_bytes = sum(f['bytes'] for f in cohort_files)
    runtime = dict(environment(), compression='GDAL GeoTIFF ZSTD for control; Python compression.zstd for custom/masks',
                   python_libzstd_version=list(zstd.zstd_version_info),
                   gdal_libzstd_version='not asserted; GDAL and rasterio versions recorded')
    result = {'schema_version': 'plotline.strong-baseline.v1', 'experiment_id': exp_id, 'identity': identity,
              'environment': runtime, 'accepted_immutable_files': accepted_files,
              'source': source, 'accepted_custom': custom, 'controls': candidates,
              'comparison': {'smallest_exact_control': best['candidate'], 'control_total_bytes': best['storage']['total_bytes'],
                  'delta_control_minus_accepted_custom_bytes': best['storage']['total_bytes'] - custom['storage']['total_bytes'],
                  'control_smaller_percent': (1-best['storage']['total_bytes']/custom['storage']['total_bytes'])*100,
                  'smallest_measured_representation': min(all_sizes, key=lambda k: (all_sizes[k], k)),
                  'accepted_choice_changed': False},
              'common_input_view': {'supplier_geometry_files': cohort_files, 'supplier_geometry_bytes': supplier_bytes,
                  'provenance_bytes': provenance['bytes'],
                  'totals_with_same_acquisition_provenance_and_supplier_files': {
                      k: value + supplier_bytes + (0 if k == 'source' else provenance['bytes'])
                      for k, value in all_sizes.items()},
                  'note': 'acquisition provenance counted once for each representation; source already requires it'},
              'method': method_record(candidates, repetitions, warmups),
              'verified': True}
    check_guard(guard)
    run_id = 'run-' + digest(result)
    archive = folder / 'runs' / (run_id + '.json')
    if not archive.exists():
        atomic_json(archive, result)
    else:
        if canonical_bytes(json.loads(archive.read_text())) != canonical_bytes(result):
            raise ValueError('immutable run collision')
    output = dict(result, archive={'path': str(archive.relative_to(ROOT)), 'sha256': sha256_file(archive)})
    verify_artifact(output)
    check_guard(guard)
    atomic_json(ROOT / 'artifacts/strong-baseline-v1.json', output)
    return output


def read_artifact(path):
    with Path(path).open('rb') as stream:
        raw = stream.read(32*1024*1024+1)
    if len(raw) > 32*1024*1024:
        raise ValueError('strong artifact exceeds size limit')
    return json.loads(raw, object_pairs_hook=_pairs, parse_constant=_constant)


def verify_artifact(artifact):
    """Reconstruct typed proof and derived fields; validate measured data bounds."""
    a = read_artifact(artifact) if not isinstance(artifact, dict) else artifact
    _json_types(a)
    fields(a, ('schema_version','experiment_id','identity','environment','accepted_immutable_files',
               'source','accepted_custom','controls','comparison','common_input_view','method','verified','archive'),
           'strong artifact')
    same(a['schema_version'],'plotline.strong-baseline.v1','strong control schema mismatch')
    same(a['verified'],True,'verified flag mismatch')
    ident = a['identity']
    fields(ident, ('schema','guard','accepted_benchmark','accepted_store_path','metadata','queries_sha256',
                   'query_version','settings','seen_aoi_not_heldout','preliminary_selector_audit_sha256'), 'identity')
    blocks, repetitions, warmups = settings(ident['settings'])
    same(ident['schema'],'plotline.strong-baseline.identity.v1','identity schema mismatch')
    same(ident['query_version'],QUERY_VERSION,'query version mismatch')
    same(ident['seen_aoi_not_heldout'],True,'seen AOI flag mismatch')
    audit = sha(ident['preliminary_selector_audit_sha256'],'preliminary audit')
    audit_path = ROOT / 'data/experimental/selector/aoi-control-results.json'
    if audit_path.exists():
        same(audit,sha256_file(audit_path),'preliminary audit identity mismatch')
    same(a['experiment_id'],'exp-'+digest(ident),'strong-control content identity mismatch')
    fields(a['archive'],('path','sha256'),'archive')
    if type(a['archive']['path']) is not str or Path(a['archive']['path']).is_absolute():
        raise ValueError('archive must be relative')
    archive = ROOT / a['archive']['path']
    if not archive.resolve().is_relative_to(AREA.resolve()):
        raise ValueError('strong-control archive outside owned area')
    payload = {k:v for k,v in a.items() if k != 'archive'}
    same(sha256_file(archive),a['archive']['sha256'],'strong-control archive equality/hash mismatch')
    same(read_artifact(archive),payload,'strong-control archive equality/hash mismatch')
    same(str(archive.relative_to(ROOT)),str((AREA/a['experiment_id']/'runs'/('run-'+digest(payload)+'.json')).relative_to(ROOT)),
         'strong-control archive content/path mismatch')
    check_guard(ident['guard'])
    accepted, source, plots, accepted_store, accepted_files = accepted_context()
    same(a['accepted_immutable_files'],accepted_files,'accepted benchmark/store binding differs')
    same(ident['metadata'],source.metadata,'strong-control source metadata mismatch')
    same(ident['queries_sha256'],digest([p['geometry'] for p in plots]),'strong-control cohort mismatch')
    same(ident['accepted_benchmark'],file_record(ROOT/'artifacts/benchmark-v1.json'),'strong-control accepted identity mismatch')
    same(ident['accepted_store_path'],str(accepted_store.relative_to(ROOT)),'strong-control accepted store mismatch')
    same(read_artifact(AREA/a['experiment_id']/'identity.json'),ident,'strong-control archived identity differs')
    source_files = [file_record(ROOT/s['path']) for s in source.metadata['sources']]
    source_files.append(file_record(ROOT/'data/public/provenance.json'))
    cohort_files = [file_record(ROOT/SAMPLE/name) for name in (CSV_NAME,GEOJSON_NAME)]
    expected_guard = dict(IMPORTED_CODE)
    expected_guard.update({f['path']:f['sha256'] for f in source_files+cohort_files+accepted_files})
    same(ident['guard'],expected_guard,'strong-control required code/input/accepted-file fingerprint set differs')
    runtime = dict(environment(), compression='GDAL GeoTIFF ZSTD for control; Python compression.zstd for custom/masks',
                   python_libzstd_version=list(zstd.zstd_version_info),
                   gdal_libzstd_version='not asserted; GDAL and rasterio versions recorded')
    same(a['environment'],runtime,'environment fields differ')
    fields(a['source'],('storage','proof','measurements'),'source row')
    same(a['source']['storage'],{'total_bytes':sum(f['bytes'] for f in source_files),'files':source_files},
         'source byte/file claims mismatch')
    same(a['source']['proof'],prove_dataset(source,source,plots),'source/oracle proof claim mismatch')
    custom = a['accepted_custom']
    fields(custom,('store_path','storage','proof','preprocessing','measurements'),'custom row')
    same(custom['store_path'],str(accepted_store.relative_to(ROOT)),'accepted custom store differs')
    custom_files = [file_record(p,accepted_store) for p in sorted(accepted_store.iterdir())]
    same(custom['storage'],{'total_bytes':sum(f['bytes'] for f in custom_files),'files':custom_files},'custom byte/file claims mismatch')
    same(custom['proof'],prove_dataset(source,Dataset(*decode_store(accepted_store)).validate(),plots),'custom proof claim mismatch')
    index = read_artifact(accepted_store/'index.json')
    sizes_by_name = {f['path']:f['bytes'] for f in custom_files}
    preprocessing(custom['preprocessing'], {'candidate':index['candidate'],'chunk_size':index['chunk_size'],
        'compression_level':index['compression']['level'],'files':[{k:f[k] for k in ('path','bytes')} for f in custom_files],
        'payload_bytes':sizes_by_name['payload.bin'],'metadata_index_bytes':sizes_by_name['index.json'],
        'total_bytes':sum(sizes_by_name.values())},custom=True)
    controls = a['controls']
    if type(controls) is not list or len(controls) != len(blocks):
        raise ValueError('control set does not match identity settings')
    for c,block in zip(controls,blocks):
        fields(c,('candidate','store_path','block_size','storage','preprocessing','proof','measurements'),'control row')
        candidate = f'gtiff_zstd19_p1_b{block}'
        same(c['candidate'],candidate,'control candidate/settings claim mismatch')
        same(c['block_size'],block,'control block/settings claim mismatch')
        path = AREA/a['experiment_id']/candidate
        same(c['store_path'],str(path.relative_to(ROOT)),'control store path is not bound to this experiment/candidate')
        with ControlWindowReader(path) as reader:
            same(reader.manifest['candidate'],candidate,'control manifest candidate mismatch')
            same(reader.manifest['settings'],_settings(block),'control manifest settings mismatch')
            mask_mode = reader.manifest['masks']['mode']
        actual_storage = storage_info(path)
        same(c['storage'],actual_storage,'control byte/file claims differ from actual files')
        preprocessing(c['preprocessing'],dict(actual_storage,candidate=candidate,settings=_settings(block),mask_mode=mask_mode))
        same(c['proof'],prove_dataset(source,decode_control(path),plots),'control full-value/mask/metadata/query proof claim mismatch')
        with ControlWindowReader(path) as reader:
            actual_answers = [evaluate_reader(reader,p['geometry']) for p in plots]
        same(digest(actual_answers),digest([evaluate(source,p['geometry']) for p in plots]),'original-lattice indexed queries differ')
    best = min(controls,key=lambda c:(c['storage']['total_bytes'],c['candidate']))
    sizes = {'source':a['source']['storage']['total_bytes'],'accepted_custom':custom['storage']['total_bytes'],
             **{c['candidate']:c['storage']['total_bytes'] for c in controls}}
    same(a['comparison'],{'smallest_exact_control':best['candidate'],'control_total_bytes':best['storage']['total_bytes'],
         'delta_control_minus_accepted_custom_bytes':best['storage']['total_bytes']-custom['storage']['total_bytes'],
         'control_smaller_percent':(1-best['storage']['total_bytes']/custom['storage']['total_bytes'])*100,
         'smallest_measured_representation':min(sizes,key=lambda k:(sizes[k],k)),'accepted_choice_changed':False},
         'derived control comparison mismatch')
    expected_answer = digest([evaluate(source,p['geometry']) for p in plots])
    for row in [a['source'],custom]+controls:
        measurements(row['measurements'],repetitions,expected_answer)
    supplier_bytes = sum(f['bytes'] for f in cohort_files)
    provenance_bytes = source_files[-1]['bytes']
    same(a['common_input_view'],{'supplier_geometry_files':cohort_files,'supplier_geometry_bytes':supplier_bytes,
         'provenance_bytes':provenance_bytes,'totals_with_same_acquisition_provenance_and_supplier_files':{
             k:value+supplier_bytes+(0 if k=='source' else provenance_bytes) for k,value in sizes.items()},
         'note':'acquisition provenance counted once for each representation; source already requires it'},
         'symmetric common-input accounting mismatch')
    same(a['method'],method_record(controls,repetitions,warmups),'declared method/settings mismatch')
    check_guard(ident['guard'])
    for c in controls:
        check_files(c['storage']['files'],ROOT/c['store_path'])
    return {'valid':True,'experiment_id':a['experiment_id'],'controls':len(controls),
            'real_plot_count':len(plots),'accepted_artifacts_unchanged':True}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--worker', action='store_true')
    parser.add_argument('--blocks', nargs='+', type=int, default=[256])
    parser.add_argument('--repetitions', type=int, default=7)
    parser.add_argument('--warmups', type=int, default=2)
    parser.add_argument('--verify', type=Path)
    args = parser.parse_args()
    if args.worker:
        print(json.dumps(worker(json.load(sys.stdin)), allow_nan=False))
    elif args.verify:
        print(json.dumps(verify_artifact(args.verify), indent=2))
    else:
        result = run(tuple(args.blocks), args.repetitions, args.warmups)
        print(json.dumps({'experiment_id': result['experiment_id'], 'comparison': result['comparison'],
                          'archive': result['archive']}, indent=2))


if __name__ == '__main__':
    main()
