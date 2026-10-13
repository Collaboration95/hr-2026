"""Separate, fair indexed-reader experiment; never replaces the full-load baseline."""
import argparse
import json
from pathlib import Path
import subprocess
import sys
import time
from .benchmark import rss_record, summarize, environment
from .experiments import content_hash, record_experiment
from .export import atomic_json
from .indexed import SourceWindowReader, CompactWindowReader, evaluate_reader
from .model import QUERY_VERSION
from .query import evaluate
from .source import ROOT, load_plots, load_source, sha256_file


def worker(request):
    # Both readers imported before operation timing. Common inputs excluded
    # symmetrically, while subprocess_wall retains startup and import costs.
    plots = load_plots()
    t, cpu = time.perf_counter_ns(), time.process_time_ns()
    reader = SourceWindowReader() if request['representation'] == 'source' else CompactWindowReader(request['store'])
    load_ms = (time.perf_counter_ns()-t)/1e6
    load_cpu_ms = (time.process_time_ns()-cpu)/1e6
    try:
        def batch():
            return [evaluate_reader(reader, p['geometry']) for p in plots]
        if request['operation'] == 'cold':
            t, cpu = time.perf_counter_ns(), time.process_time_ns()
            answers = batch()
            query_ms = (time.perf_counter_ns()-t)/1e6
            query_cpu_ms = (time.process_time_ns()-cpu)/1e6
            return {'wall_ms': load_ms+query_ms, 'query_ms': query_ms, 'load_ms': load_ms,
                    'cpu_ms': load_cpu_ms+query_cpu_ms, 'answer_sha256': content_hash(answers),
                    'peak_rss': rss_record()}
        for _ in range(request['warmups']):
            batch()
        walls, cpus, hashes = [], [], []
        for _ in range(request['repetitions']):
            t, cpu = time.perf_counter_ns(), time.process_time_ns()
            answers = batch()
            walls.append((time.perf_counter_ns()-t)/1e6)
            cpus.append((time.process_time_ns()-cpu)/1e6)
            hashes.append(content_hash(answers))
        return {'wall_ms': summarize(walls), 'cpu_ms': summarize(cpus),
                'answer_sha256': sorted(set(hashes)), 'peak_rss': rss_record()}
    finally:
        reader.close()


def child(request):
    import os
    env = dict(os.environ, PYTHONDONTWRITEBYTECODE='1', OMP_NUM_THREADS='1',
               OPENBLAS_NUM_THREADS='1', MKL_NUM_THREADS='1', VECLIB_MAXIMUM_THREADS='1')
    t = time.perf_counter_ns()
    completed = subprocess.run([sys.executable, '-B', '-m', 'engine.window_benchmark', '--worker'],
                               input=json.dumps(request), text=True, capture_output=True, cwd=ROOT,
                               env=env, timeout=60)
    if completed.returncode:
        raise RuntimeError(completed.stderr)
    result = json.loads(completed.stdout)
    result['subprocess_wall_ms'] = (time.perf_counter_ns()-t)/1e6
    return result


def run(store, repetitions=7, warmups=2):
    if type(repetitions) is not int or not 1 <= repetitions <= 100 or type(warmups) is not int or not 0 <= warmups <= 100:
        raise ValueError('repetitions1..100 and warmups0..100 required')
    store = Path(store).resolve()
    data, plots = load_source(), load_plots()
    expected = content_hash([evaluate(data, p['geometry']) for p in plots])
    names = ['indexed.py', 'source.py', 'model.py', 'query.py', 'codecs.py', 'window_benchmark.py', 'benchmark.py', 'experiments.py']
    hashes = {name: sha256_file(ROOT / 'engine' / name) for name in names}
    identity = {'experiment': 'indexed-window-v1', 'query_version': QUERY_VERSION,
                'implementation_sha256': hashes, 'source_metadata': data.metadata,
                'store_files': [{'name': p.name, 'sha256': sha256_file(p), 'bytes': p.stat().st_size}
                                for p in sorted(store.iterdir()) if p.is_file()],
                'queries_sha256': content_hash([p['geometry'] for p in plots]),
                'repetitions': repetitions, 'warmups': warmups}
    results = {}
    for representation in ('source', 'compact'):
        request = {'representation': representation, 'store': str(store), 'repetitions': repetitions, 'warmups': warmups}
        hot = child(dict(request, operation='hot'))
        cold = [child(dict(request, operation='cold')) for _ in range(repetitions)]
        exact = hot['answer_sha256'] == [expected] and all(r['answer_sha256'] == expected for r in cold)
        results[representation] = {'hot': hot, 'process_cold': {
            'wall_ms': summarize([r['wall_ms'] for r in cold]),
            'cpu_ms': summarize([r['cpu_ms'] for r in cold]),
            'load_ms': summarize([r['load_ms'] for r in cold]),
            'query_ms': summarize([r['query_ms'] for r in cold]),
            'subprocess_wall_ms': summarize([r['subprocess_wall_ms'] for r in cold]),
            'peak_rss': [r['peak_rss'] for r in cold]}, 'all_timed_answers_exact': exact}
    if hashes != {name: sha256_file(ROOT / 'engine' / name) for name in names}:
        raise RuntimeError('implementation changed during experiment; rerun stable code')
    if not all(r['all_timed_answers_exact'] for r in results.values()):
        raise ValueError('indexed query mismatch; no performance acceptance')
    result = {'schema_version': 'plotline.window-benchmark.v1', 'identity': identity,
              'environment': environment(), 'results': results,
              'method': {'cohort': '17 real company plots; identical native full-AOI stores',
                         'query_count_per_batch': 17, 'timing_unit': 'ms per 17-plot batch',
                         'selection': 'original global native center lattice; fetch bbox of selected known cells',
                         'integrity': 'both reader initializations hash whole stored inputs; compact selected chunks checked per query',
                         'hot': 'initialized readers, two default warmup batches; original GDAL block cache may be warm',
                         'compact_cache': 'no decoded chunk cache; index revalidated by codec for each read',
                         'cold': 'fresh process reader initialization+batch after symmetric imports/common geometry read',
                         'disk_cache': 'uncontrolled, likely warm; not disk-cold',
                         'resources': 'isolated child lifetime peak RSS, including Python/imports; no UI',
                         'scope': 'optional indexed access; full-load benchmark remains separate and is not silently replaced'}}
    result['registry'] = record_experiment(identity, result, ROOT / 'artifacts/window-experiments')
    atomic_json(ROOT / 'artifacts/window-benchmark-v1.json', result)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--worker', action='store_true')
    parser.add_argument('--store', type=Path)
    parser.add_argument('--repetitions', type=int, default=7)
    parser.add_argument('--warmups', type=int, default=2)
    args = parser.parse_args()
    if args.worker:
        print(json.dumps(worker(json.load(sys.stdin)), allow_nan=False))
        return
    if not args.store:
        parser.error('--store is required')
    result = run(args.store, args.repetitions, args.warmups)
    print(json.dumps({k: {'hot_median_ms': v['hot']['wall_ms']['median'],
                         'process_cold_median_ms': v['process_cold']['wall_ms']['median']}
                      for k, v in result['results'].items()}, indent=2))

if __name__ == '__main__':
    main()
