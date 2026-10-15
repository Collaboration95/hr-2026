"""Bounded JRC-only same-chip experiments and content-addressed evidence."""
import argparse
import copy
import hashlib
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import platform
import resource
import statistics
import subprocess
import sys
import time

import numpy as np
import rasterio
import shapely
from compression import zstd
from .jrc import ROOT, SOURCE, QUERY_VERSION, load_jrc, evaluate_jrc, check_source_readback, file_record
from .jrc_codec import CANDIDATES, LEVELS, encode_jrc_store, decode_jrc_store
from .jrc_oracle import oracle_jrc
from .source import load_plots, object_hash, canonical_bytes, SAMPLE, CSV_NAME, GEOJSON_NAME

SETTINGS = {'repetitions': 7, 'warmups': 2, 'chunk_sizes': [256, 1024], 'candidates': list(CANDIDATES),
            'levels': LEVELS, 'cache': 'same-process OS-cache-warm; isolated children are process-cold, not disk-cold',
            'encode_scope': 'full raw values/mask/metadata to two files; buffered write, no fsync',
            'decode_scope': 'read index/payload, validate hashes/ranges, decode full arrays',
            'query_scope': 'all 17 exact native-center queries; no UI',
            'sample_validation': 'every warmup/measured result checked outside timed interval; inputs/code/store and in-memory data guarded before/after each call',
            'p95_method': 'numpy.percentile(method=linear)',
            'cold_scope': 'fresh ordinary Python process; timed source/store load plus 17 queries, imports excluded from inner time'}
CODE_PATHS = tuple('engine/'+x for x in ('jrc.py', 'jrc_codec.py', 'jrc_oracle.py', 'jrc_benchmark.py',
                                       'jrc_proof.py', 'query.py', 'codecs.py', 'oracle.py', 'source.py', 'model.py'))
IMPORT_IMPLEMENTATION = [file_record(p) for p in CODE_PATHS]
PLOT_PINS = {str(SAMPLE / CSV_NAME): '43b47916d4900d4bf2f86a8a3ca3ee107f22b1fb80702174bbb9b55403c0fca2',
             str(SAMPLE / GEOJSON_NAME): '8922eef5040120b180a86f6002f52e090ee9bb8273c3c1cf71f984b68648662b'}
ORACLE_METHOD = 'W2 scalar ray casting with exact Fraction fallback; separate scalar JRC reduction; GEOS topology validation shared'
ACCOUNTING_NOTE = 'Same full chip only; optional 197MB full source readback cache, engine/runtime, result archives and duplicate manifests excluded. Plot input files are reported as common to both paths.'


def environment():
    return {'python': platform.python_version(), 'platform': platform.platform(),
            'numpy': np.__version__, 'zstd': list(zstd.zstd_version_info),
            'rasterio': rasterio.__version__, 'gdal': rasterio.__gdal_version__,
            'shapely': shapely.__version__, 'machine': platform.machine(), 'logical_cpus': os.cpu_count()}


def pinned_plots(root=ROOT):
    for name, digest in PLOT_PINS.items():
        if file_record(name, root)['sha256'] != digest:
            raise ValueError('JRC pinned plot input mismatch: '+name)
    return load_plots(root)


def identity(dataset, plots, root=ROOT):
    inputs = [*dataset.metadata['required_inputs'], *(file_record(p, root) for p in PLOT_PINS)]
    return {'query_version': QUERY_VERSION, 'source_metadata': dataset.metadata,
            'queries_sha256': object_hash([{'plot_id': p['plot_id'], 'geometry': p['geometry']} for p in plots]),
            'inputs': inputs, 'settings': SETTINGS, 'environment': environment(),
            'implementation': [file_record(p, root) for p in CODE_PATHS]}


def samples(values):
    return {'samples': values, 'min': min(values), 'median': statistics.median(values),
            'p95': float(np.percentile(values, 95)), 'unit': 'ms'}


def dataset_fingerprint(dataset):
    dataset.validate()
    return object_hash({'values': hashlib.sha256(dataset.values.tobytes()).hexdigest(),
                        'mask': hashlib.sha256(dataset.mask.tobytes()).hexdigest(),
                        'metadata': dataset.metadata})


def guard_digest(ident, dataset_sha256=None, storage=None):
    return object_hash({'measurement_identity_sha256': object_hash(ident),
                        'dataset_sha256': dataset_sha256, 'store': storage})


def snapshot_guard(ident, plots, root=ROOT, dataset=None, path=None):
    # Reopen identities rather than recycling metadata's recorded input hashes.
    actual_inputs = [file_record(p['path'], root) for p in ident['inputs']]
    actual_code = [file_record(p, root) for p in CODE_PATHS]
    if (canonical_bytes(actual_inputs) != canonical_bytes(ident['inputs'])
            or canonical_bytes(actual_code) != canonical_bytes(ident['implementation'])
            or canonical_bytes(actual_code) != canonical_bytes(IMPORT_IMPLEMENTATION)
            or canonical_bytes(environment()) != canonical_bytes(ident['environment'])
            or canonical_bytes(SETTINGS) != canonical_bytes(ident['settings'])
            or object_hash([{'plot_id': p['plot_id'], 'geometry': p['geometry']} for p in plots]) != ident['queries_sha256']):
        raise ValueError('JRC measurement source/code/query identity changed')
    return guard_digest(ident, dataset_fingerprint(dataset) if dataset is not None else None,
                        store_record(path, root) if path is not None else None)


def timed(fn, *, fingerprint, expected_sha256, guard, expected_guard):
    wall, cpu, warmups, measured = [], [], [], []
    result = None
    for i in range(SETTINGS['warmups'] + SETTINGS['repetitions']):
        before = guard()
        if before != expected_guard: raise ValueError('JRC timing start guard mismatch')
        a, b = time.perf_counter_ns(), time.process_time_ns()
        result = fn()
        elapsed_wall, elapsed_cpu = (time.perf_counter_ns()-a)/1e6, (time.process_time_ns()-b)/1e6
        digest = fingerprint(result)
        if digest != expected_sha256:
            phase = 'warmup' if i < SETTINGS['warmups'] else 'sample'
            number = i+1 if phase == 'warmup' else i-SETTINGS['warmups']+1
            raise ValueError(f'JRC timed result mismatch at {phase} {number}')
        after = guard()
        if after != expected_guard: raise ValueError('JRC timing end guard mismatch')
        record = {'result_sha256': digest, 'guard_before': before, 'guard_after': after}
        if i < SETTINGS['warmups']:
            warmups.append(record)
        else:
            measured.append(record); wall.append(elapsed_wall); cpu.append(elapsed_cpu)
    return result, {'wall': samples(wall), 'cpu': samples(cpu),
                    'validation': {'expected_sha256': expected_sha256, 'expected_guard': expected_guard,
                                   'warmups': warmups, 'samples': measured}}


def answers(dataset, plots):
    return [evaluate_jrc(dataset, p['geometry']) for p in plots]


def store_record(path, root=ROOT):
    path = Path(path)
    if {p.name for p in path.iterdir()} != {'index.json', 'payload.bin'}:
        raise ValueError('JRC uncounted or missing store files')
    files = [file_record(str((path / name).relative_to(root)), root) for name in ('index.json', 'payload.bin')]
    return {'path': str(path.relative_to(root)), 'files': files,
            'total_bytes': sum(f['bytes'] for f in files), 'metadata_index_bytes': files[0]['bytes'],
            'payload_bytes': files[1]['bytes']}


def cold(path, root=ROOT, *, ident, dataset_sha256, answer_sha256):
    results, outer, warmups = [], [], []
    plots = pinned_plots(root)
    store_path = None if str(path) == 'source' else Path(root) / path
    expected_guard = guard_digest(ident, storage=store_record(store_path, root) if store_path else None)
    context = {'identity': ident, 'dataset_sha256': dataset_sha256,
               'answer_sha256': answer_sha256, 'expected_guard': expected_guard}
    for i in range(SETTINGS['warmups'] + SETTINGS['repetitions']):
        if snapshot_guard(ident, plots, root, path=store_path) != expected_guard:
            raise ValueError('JRC cold parent start guard mismatch')
        start = time.perf_counter_ns()
        process = subprocess.run([sys.executable, '-B', '-m', 'engine.jrc_benchmark', '--child', str(path),
                                  '--context', canonical_bytes(context).decode()],
                                 cwd=root, check=True, capture_output=True, text=True,
                                 env={**os.environ, 'PYTHONDONTWRITEBYTECODE': '1'})
        elapsed = (time.perf_counter_ns()-start)/1e6
        record = json.loads(process.stdout)
        if (record['answer_sha256'] != answer_sha256 or record['dataset_sha256'] != dataset_sha256
                or record['guard_before'] != expected_guard or record['guard_after'] != expected_guard
                or snapshot_guard(ident, plots, root, path=store_path) != expected_guard):
            raise ValueError('JRC cold child result/identity guard mismatch')
        if i >= SETTINGS['warmups']:
            results.append(record); outer.append(elapsed)
        else:
            warmups.append(record)
    return {'load_and_17_queries_wall': samples([r['wall_ms'] for r in results]),
            'load_and_17_queries_cpu': samples([r['cpu_ms'] for r in results]),
            'parent_spawn_inclusive_wall': samples(outer), 'children': results, 'warmup_children': warmups,
            'expected_guard': expected_guard,
            'cache': 'new process per repetition; OS file cache warm, not disk-cold',
            'rss_note': 'whole child high-water RSS including imports and post-timing result/identity validation; bytes on macOS, KiB on Linux'}


def write_once(path, data):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    encoded = canonical_bytes(data)
    if path.exists():
        if path.read_bytes() != encoded: raise ValueError('immutable JRC experiment collision')
    else:
        temp = path.with_suffix('.tmp')
        with temp.open('xb') as f: f.write(encoded)
        temp.replace(path)


def run_jrc_benchmark(root=ROOT):
    root = Path(root)
    source, plots = load_jrc(root), pinned_plots(root)
    expected = answers(source, plots)
    oracle = [oracle_jrc(source, p['geometry']) for p in plots]
    if canonical_bytes(expected) != canonical_bytes(oracle): raise ValueError('independent JRC oracle mismatch')
    readback = check_source_readback(root, source)
    ident = copy.deepcopy(identity(source, plots, root))
    source_sha, answer_sha = dataset_fingerprint(source), object_hash(expected)
    expected_run_guard = guard_digest(ident, source_sha)
    start_guard = snapshot_guard(ident, plots, root, source)
    if start_guard != expected_run_guard: raise ValueError('JRC run start guard mismatch')
    experiment = 'exp-'+object_hash(ident)
    folder = root / 'artifacts/jrc-stores' / experiment
    write_once(folder / 'identity.json', ident)
    _, baseline_load = timed(lambda: load_jrc(root), fingerprint=dataset_fingerprint, expected_sha256=source_sha,
                            guard=lambda: snapshot_guard(ident, plots, root), expected_guard=guard_digest(ident))
    _, source_hot = timed(lambda: answers(source, plots), fingerprint=object_hash, expected_sha256=answer_sha,
                         guard=lambda: snapshot_guard(ident, plots, root, source), expected_guard=expected_run_guard)
    support_files = source.metadata['required_inputs']
    baseline = {'candidate': 'native_geotiff', 'files': support_files,
                'payload_bytes': support_files[0]['bytes'],
                'metadata_index_bytes': sum(f['bytes'] for f in support_files[1:]),
                'total_bytes': sum(f['bytes'] for f in support_files), 'load': baseline_load,
                'hot_17_queries': source_hot, 'answer_sha256': object_hash(expected)}
    records = []
    for chunk in SETTINGS['chunk_sizes']:
        for candidate in CANDIDATES:
            path = folder / f'{candidate}-{chunk}'
            def encode():
                return encode_jrc_store(source, path, candidate, chunk)
            encode_files = []
            def check_encoded(report):
                storage = store_record(path, root)
                if encode_files and canonical_bytes(storage) != canonical_bytes(encode_files[0]):
                    raise ValueError('JRC repeated encode store identity changed')
                if not encode_files: encode_files.append(storage)
                for key, value in [('candidate', candidate), ('chunk_size', chunk), ('compression_level', LEVELS[candidate]),
                                   ('total_bytes', storage['total_bytes']), ('payload_bytes', storage['payload_bytes']),
                                   ('metadata_index_bytes', storage['metadata_index_bytes'])]:
                    if canonical_bytes(report[key]) != canonical_bytes(value): raise ValueError('JRC encode report mismatch')
                return dataset_fingerprint(decode_jrc_store(path))
            _, encode_stats = timed(encode, fingerprint=check_encoded, expected_sha256=source_sha,
                                    guard=lambda: snapshot_guard(ident, plots, root, source), expected_guard=expected_run_guard)
            storage = store_record(path, root)
            decoded, decode_stats = timed(lambda: decode_jrc_store(path), fingerprint=dataset_fingerprint,
                                          expected_sha256=source_sha, guard=lambda: snapshot_guard(ident, plots, root, path=path),
                                          expected_guard=guard_digest(ident, storage=storage))
            actual, hot = timed(lambda: answers(decoded, plots), fingerprint=object_hash, expected_sha256=answer_sha,
                                guard=lambda: snapshot_guard(ident, plots, root, decoded, path),
                                expected_guard=guard_digest(ident, source_sha, storage))
            equal = (np.array_equal(source.values, decoded.values) and np.array_equal(source.mask, decoded.mask)
                     and canonical_bytes(source.metadata) == canonical_bytes(decoded.metadata))
            mismatches = [p['plot_id'] for p, x, y in zip(plots, expected, actual) if canonical_bytes(x) != canonical_bytes(y)]
            if not equal or mismatches: raise ValueError('JRC candidate fidelity failure')
            records.append({'candidate': candidate, 'chunk_size': chunk, 'compression_level': LEVELS[candidate],
                            'storage': store_record(path, root), 'encode': encode_stats, 'decode': decode_stats,
                            'hot_17_queries': hot, 'answer_sha256': object_hash(actual),
                            'full_pixel_count': int(source.values.size), 'full_raw_equal': equal, 'full_masks_equal': equal,
                            'full_metadata_equal': equal, 'plot_mismatches': mismatches, 'fully_exact': True})
    chosen = min(records, key=lambda r: (r['storage']['total_bytes'], r['candidate'], r['chunk_size']))
    result = {'schema_version': 'plotline.jrc-benchmark.v1', 'identity': ident, 'experiment_id': experiment,
              'measured_at_utc': datetime.now(timezone.utc).isoformat(),
              'environment': environment(),
              'source_window_readback': readback, 'independent_oracle': {'plot_count': len(plots), 'equal': True,
                  'method': ORACLE_METHOD},
              'baseline': baseline, 'candidates': records, 'smallest_encoded': {
                  'candidate': chosen['candidate'], 'chunk_size': chosen['chunk_size'],
                  'store_path': chosen['storage']['path'], 'total_bytes': chosen['storage']['total_bytes']},
              'overall_storage_choice': 'native_geotiff' if baseline['total_bytes'] <= chosen['storage']['total_bytes'] else chosen['candidate'],
              'common_plot_inputs': [file_record(p, root) for p in PLOT_PINS],
              'accounting_note': ACCOUNTING_NOTE,
              'cold_source': cold('source', root, ident=ident, dataset_sha256=source_sha, answer_sha256=answer_sha),
              'cold_smallest_encoded': cold(chosen['storage']['path'], root, ident=ident, dataset_sha256=source_sha, answer_sha256=answer_sha)}
    end_guard = snapshot_guard(ident, plots, root, source)
    if end_guard != start_guard: raise ValueError('JRC run end guard mismatch')
    for entry in records:
        if canonical_bytes(store_record(root / entry['storage']['path'], root)) != canonical_bytes(entry['storage']):
            raise ValueError('JRC measured store changed before archive')
    if canonical_bytes(file_record(SOURCE, root)) != canonical_bytes(readback['source']):
        raise ValueError('JRC full source readback input changed during run')
    result['measurement_guards'] = {'start': start_guard, 'end': end_guard, 'dataset_sha256': source_sha,
                                    'source_readback_sha256': object_hash(readback['source'])}
    run_id = 'run-'+object_hash(result)
    archive = folder / (run_id+'.json')
    write_once(archive, result)
    return {**result, 'archive': {'path': str(archive.relative_to(root)), 'run_id': run_id}}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--child')
    parser.add_argument('--context')
    args = parser.parse_args()
    if args.child:
        if not args.context: raise ValueError('JRC cold child requires pinned parent context')
        context = json.loads(args.context)
        plots = pinned_plots()
        path = None if args.child == 'source' else ROOT / args.child
        before = snapshot_guard(context['identity'], plots, path=path)
        if before != context['expected_guard']: raise ValueError('JRC child start identity mismatch')
        a, b = time.perf_counter_ns(), time.process_time_ns()
        ds = load_jrc() if args.child == 'source' else decode_jrc_store(ROOT / args.child)
        output = answers(ds, plots)
        wall_ms, cpu_ms = (time.perf_counter_ns()-a)/1e6, (time.process_time_ns()-b)/1e6
        digest, ds_digest = object_hash(output), dataset_fingerprint(ds)
        after = snapshot_guard(context['identity'], plots, path=path)
        if (digest != context['answer_sha256'] or ds_digest != context['dataset_sha256']
                or after != context['expected_guard']): raise ValueError('JRC child result/end identity mismatch')
        print(json.dumps({'wall_ms': wall_ms, 'cpu_ms': cpu_ms, 'dataset_sha256': ds_digest,
                          'guard_before': before, 'guard_after': after,
                          'answer_sha256': digest, 'rss_peak': resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
                          'rss_unit': 'bytes' if sys.platform == 'darwin' else 'KiB'}))
    else:
        result = run_jrc_benchmark()
        print(json.dumps({'archive': result['archive'], 'smallest_encoded': result['smallest_encoded'],
                          'overall_storage_choice': result['overall_storage_choice']}, indent=2))


if __name__ == '__main__': main()
