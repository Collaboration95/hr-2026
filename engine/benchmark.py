"""Fair full-AOI storage and isolated full-load/17-plot query measurements.

Run with `.venv-data/bin/python -B -m engine.benchmark`. Each representation
loads the same full native grid. Hot timings exclude load for every format;
process-cold timings include load for every format. No disk cache is evicted.
"""
import argparse
import hashlib
import json
import math
import os
from pathlib import Path
import platform
import resource
import statistics
import subprocess
import sys
import time

from .experiments import (atomic_write_json, canonical_bytes, content_hash, experiment_id,
                          record_experiment, publish_benchmark, freeze_selection)

ROOT = Path(__file__).resolve().parents[1]
BENCHMARK_VERSION = 'plotline.benchmark.v1'


class BenchmarkRaceError(RuntimeError):
    """A measurement cannot be bound to its expected implementation/input/answers."""
    def __init__(self, message, details=None):
        super().__init__(message)
        self.details = details


def sha256_file(path):
    digest = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            digest.update(block)
    return digest.hexdigest()


def input_hashes(root):
    root = Path(root)
    files = [root / 'data/public/provenance.json',
             root / 'data/company-sample/2026-10-12/200001-17plots-valid_2025-08-02T09_11_12Z.csv',
             root / 'data/company-sample/2026-10-12/200001-17plots-valid.geojson']
    for band in ('treecover2000', 'lossyear', 'datamask'):
        files.extend(sorted((root / 'data/public').glob(f'hansen_{band}_sample.tif*')))
    return {str(p.relative_to(root)): sha256_file(p) for p in files if p.is_file()}


def assert_fingerprints(root, guard):
    current = implementation_hashes()
    if current != guard['implementation']:
        raise BenchmarkRaceError('implementation fingerprint changed; start a fresh Python runner',
                                 {'expected': guard['implementation'], 'observed': current})
    inputs = input_hashes(root)
    if inputs != guard['inputs']:
        raise BenchmarkRaceError('source/provenance/geometry fingerprint changed during measurement',
                                 {'expected': guard['inputs'], 'observed': inputs})


def summarize(samples):
    """Nearest-rank p95, suitable for small explicitly reported sample counts."""
    if not samples or any(not math.isfinite(x) or x < 0 for x in samples):
        raise ValueError('finite nonnegative timing samples required')
    values = sorted(samples)
    return {'samples': samples, 'repetitions': len(samples), 'min': values[0],
            'median': statistics.median(values), 'p95': values[math.ceil(.95 * len(values)) - 1]}


def differing_fields(left, right, prefix=''):
    """Return deterministic JSON field paths, including absent keys and indices."""
    if type(left) is not type(right):
        return [prefix or '$']
    if isinstance(left, dict):
        out = []
        for key in sorted(left.keys() | right.keys()):
            path = f'{prefix}.{key}' if prefix else key
            out.extend([path] if key not in left or key not in right else
                       differing_fields(left[key], right[key], path))
        return out
    if isinstance(left, list):
        if len(left) != len(right):
            return [prefix]
        return [path for i, (a, b) in enumerate(zip(left, right))
                for path in differing_fields(a, b, f'{prefix}[{i}]')]
    return [] if left == right else [prefix or '$']


def rss_record():
    # getrusage returns bytes on macOS, KiB on Linux. Keep native unit and conversion.
    native = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    unit = 'bytes' if sys.platform == 'darwin' else 'KiB'
    return {'native_value': native, 'native_unit': unit,
            'bytes': int(native if unit == 'bytes' else native * 1024),
            'scope': 'child lifetime high-water mark including Python/imports, inputs and operation'}


def _load(representation, store, root):
    from .source import load_source
    if representation == 'source_geotiff':
        return load_source(root)
    from .codecs import decode_store
    from .model import Dataset
    return Dataset(*decode_store(Path(store))).validate()


def _worker_operation(request):
    """One ordinary Python process: never reuse parent RSS or loaded candidate data."""
    from .source import load_source, load_plots
    from .query import evaluate
    root = Path(request['root'])
    operation = request['operation']
    if operation == 'encode':
        from .codecs import encode_store
        dataset = load_source(root)
        wall, cpu = time.perf_counter_ns(), time.process_time_ns()
        report = encode_store(dataset.bands, dataset.masks, dataset.metadata,
                              Path(request['store']), request['representation'], request['chunk_size'])
        return {'codec_report': report, 'wall_ms': (time.perf_counter_ns() - wall) / 1e6,
                'cpu_ms': (time.process_time_ns() - cpu) / 1e6, 'peak_rss': rss_record()}
    plots = load_plots(root)  # Common geometry/supplier read is outside all timed batches.
    if request['representation'] != 'source_geotiff':
        # Both loader modules must be imported before the operation timer.
        # Source is already imported for common plot reading above.
        from .codecs import decode_store
    wall, cpu = time.perf_counter_ns(), time.process_time_ns()
    dataset = _load(request['representation'], request.get('store'), root)
    load_wall = (time.perf_counter_ns() - wall) / 1e6
    load_cpu = (time.process_time_ns() - cpu) / 1e6
    def batch():
        return [evaluate(dataset, p['geometry']) for p in plots]
    if operation == 'cold':
        wall, cpu = time.perf_counter_ns(), time.process_time_ns()
        answers = batch()
        query_wall = (time.perf_counter_ns() - wall) / 1e6
        query_cpu = (time.process_time_ns() - cpu) / 1e6
        return {'load_ms': load_wall, 'query_ms': query_wall, 'wall_ms': load_wall + query_wall,
                'cpu_ms': load_cpu + query_cpu, 'answer_sha256': content_hash(answers),
                'peak_rss': rss_record()}
    for _ in range(request['warmups']):
        batch()
    walls, cpus, digests = [], [], []
    for _ in range(request['repetitions']):
        wall, cpu = time.perf_counter_ns(), time.process_time_ns()
        answers = batch()
        walls.append((time.perf_counter_ns() - wall) / 1e6)
        cpus.append((time.process_time_ns() - cpu) / 1e6)
        digests.append(content_hash(answers))
    return {'wall_ms': summarize(walls), 'cpu_ms': summarize(cpus),
            'answer_sha256': sorted(set(digests)), 'peak_rss': rss_record()}


def _worker(request):
    guard = request.get('guard')
    if guard:
        assert_fingerprints(request['root'], guard)
    result = _worker_operation(request)
    if guard:
        assert_fingerprints(request['root'], guard)
    return result


def child_measure(request, timeout=120):
    env = dict(os.environ, PYTHONDONTWRITEBYTECODE='1', OMP_NUM_THREADS='1',
               OPENBLAS_NUM_THREADS='1', MKL_NUM_THREADS='1', VECLIB_MAXIMUM_THREADS='1')
    wall = time.perf_counter_ns()
    completed = subprocess.run([sys.executable, '-B', '-m', 'engine.benchmark', '--worker'],
                               input=canonical_bytes(request), capture_output=True,
                               cwd=ROOT, env=env, timeout=timeout, check=False)
    elapsed = (time.perf_counter_ns() - wall) / 1e6
    if completed.returncode:
        message = completed.stderr.decode(errors='replace')[-4000:]
        if 'BenchmarkRaceError' in message:
            raise BenchmarkRaceError(message)
        raise RuntimeError(message)
    result = json.loads(completed.stdout)
    result['subprocess_wall_ms'] = elapsed
    return result


def measure_queries(representation, store, root, repetitions, warmups, expected_digest, guard=None):
    request = {'representation': representation, 'store': str(store) if store else None,
               'root': str(root), 'repetitions': repetitions, 'warmups': warmups, 'guard': guard}
    hot = child_measure(dict(request, operation='hot'))
    if hot['answer_sha256'] != [expected_digest]:
        raise BenchmarkRaceError(f'{representation} timed hot answers differ from pinned source answers',
                                 {'expected': expected_digest, 'observed': hot['answer_sha256']})
    cold = [child_measure(dict(request, operation='cold')) for _ in range(repetitions)]
    if any(r['answer_sha256'] != expected_digest for r in cold):
        raise BenchmarkRaceError(f'{representation} timed process-cold answers differ from pinned source answers',
                                 {'expected': expected_digest, 'observed': [r['answer_sha256'] for r in cold]})
    return {'hot': hot, 'process_cold': {
        'wall_ms': summarize([r['wall_ms'] for r in cold]),
        'cpu_ms': summarize([r['cpu_ms'] for r in cold]),
        'load_ms': summarize([r['load_ms'] for r in cold]),
        'query_ms': summarize([r['query_ms'] for r in cold]),
        'subprocess_wall_ms': summarize([r['subprocess_wall_ms'] for r in cold]),
        'peak_rss': [r['peak_rss'] for r in cold],
        'answer_sha256': sorted({r['answer_sha256'] for r in cold})},
        'timed_answers_exact': hot['answer_sha256'] == [expected_digest] and
                               all(r['answer_sha256'] == expected_digest for r in cold)}


def audit_store(path, report):
    """Measure actual files, not a favorable encoder estimate."""
    files = [{'path': str(p.relative_to(path)), 'bytes': p.stat().st_size,
              'sha256': sha256_file(p)} for p in sorted(Path(path).rglob('*')) if p.is_file()]
    total = sum(f['bytes'] for f in files)
    payload, metadata = report['payload_bytes'], report['metadata_index_bytes']
    if any(type(n) is not int or n < 0 for n in (payload, metadata, report['total_bytes'])):
        raise ValueError('codec byte accounting must be nonnegative integer bytes')
    if total != report['total_bytes'] or payload + metadata != total:
        raise ValueError('codec byte accounting does not match complete on-disk store')
    storage = {'total_bytes': total, 'payload_bytes': payload, 'metadata_index_bytes': metadata,
               'files': files, 'metadata_note': 'metadata and chunk index combined; includes original source identity'}
    if (Path(path) / 'index.json').exists():
        if ((Path(path) / 'index.json').stat().st_size != metadata or
                (Path(path) / 'payload.bin').stat().st_size != payload):
            raise ValueError('codec payload/index breakdown differs from actual files')
        index = json.loads((Path(path) / 'index.json').read_text())
        metadata_bytes = len(canonical_bytes(index['metadata']))
        storage.update(metadata_bytes=metadata_bytes, index_bytes=metadata - metadata_bytes,
                       codec_settings=index.get('compression'),
                       metadata_note='metadata_bytes is embedded canonical metadata JSON value; index_bytes is all remaining index/format overhead')
    return storage


def implementation_hashes():
    return {name: sha256_file(ROOT / 'engine' / name) for name in
            ('model.py', 'source.py', 'query.py', 'codecs.py', 'benchmark.py', 'experiments.py')}


# A long-lived runner must not reuse cached imports after shared code changes.
_PROCESS_IMPLEMENTATION_HASHES = {name: sha256_file(ROOT / 'engine' / name) for name in
    ('model.py', 'source.py', 'query.py', 'codecs.py', 'benchmark.py', 'experiments.py')
    if (ROOT / 'engine' / name).exists()}


def environment():
    import numpy, rasterio, shapely
    hardware = {'machine': platform.machine(), 'processor': platform.processor(),
                'logical_cpu_count': os.cpu_count()}
    if sys.platform == 'darwin':
        for key in ('hw.model', 'hw.memsize', 'machdep.cpu.brand_string'):
            value = subprocess.run(['sysctl', '-n', key], capture_output=True, text=True)
            if value.returncode == 0:
                hardware[key] = value.stdout.strip()
    return {'python': sys.version, 'platform': platform.platform(), 'hardware': hardware,
            'numpy': numpy.__version__, 'rasterio': rasterio.__version__,
            'gdal': rasterio.__gdal_version__, 'shapely': shapely.__version__,
            'compression': 'Python standard-library compression.zstd; codec defines settings',
            'child_thread_limits': 1}


def _run_benchmark(*, root=None, repetitions=7, warmups=2, chunk_size=128, candidates=None, publish=True):
    code_hashes = implementation_hashes()
    if code_hashes != _PROCESS_IMPLEMENTATION_HASHES:
        raise BenchmarkRaceError('cached runner implementation changed; restart with a fresh Python process')
    import numpy as np
    from .source import load_source, load_plots, SAMPLE, CSV_NAME, GEOJSON_NAME
    from .query import evaluate
    from .model import Dataset, QUERY_VERSION
    from .codecs import CANDIDATES, decode_store
    if (any(type(v) is not int for v in (repetitions, warmups, chunk_size)) or
            not 1 <= repetitions <= 100 or not 0 <= warmups <= 100 or not 1 <= chunk_size <= 1024):
        raise ValueError('integer repetitions 1..100, warmups 0..100 and chunk size 1..1024 required')
    root = Path(root).resolve() if root is not None else ROOT
    guard = {'implementation': code_hashes, 'inputs': input_hashes(root)}
    (root / 'data/experimental/w3').mkdir(parents=True, exist_ok=True)
    candidates = tuple(CANDIDATES if candidates is None else candidates)
    if not candidates or len(set(candidates)) != len(candidates) or any(c not in CANDIDATES for c in candidates):
        raise ValueError('unique available codec candidates required')
    dataset, plots = load_source(root), load_plots(root)
    source_results = [evaluate(dataset, p['geometry']) for p in plots]
    expected_digest = content_hash(source_results)
    assert_fingerprints(root, guard)
    common = [{'path': str(SAMPLE / name), 'bytes': (root / SAMPLE / name).stat().st_size,
               'sha256': sha256_file(root / SAMPLE / name)} for name in (CSV_NAME, GEOJSON_NAME)]
    # The lead's pinned source loader requires acquisition provenance in addition
    # to the TIFFs. Count that actual dependency, not just a generated manifest.
    source_loader_inputs = [{'path': 'data/public/provenance.json',
                            'bytes': (root / 'data/public/provenance.json').stat().st_size,
                            'sha256': sha256_file(root / 'data/public/provenance.json')}]
    identity = {'benchmark_version': BENCHMARK_VERSION, 'query_version': QUERY_VERSION,
                'implementation_sha256': code_hashes, 'input_sha256': guard['inputs'],
                'source_metadata': dataset.metadata,
                'common_inputs': common, 'source_loader_inputs': source_loader_inputs,
                'queries_sha256': content_hash([
                    {'plot_id': p['plot_id'], 'geometry': p['geometry']} for p in plots]),
                'settings': {'candidates': list(candidates), 'chunk_size': chunk_size,
                             'repetitions': repetitions, 'warmups': warmups}}
    exp_id = experiment_id(identity)
    stores = root / 'artifacts/stores' / exp_id
    # A content-addressed store is reused only after complete verification below.
    stores.mkdir(parents=True, exist_ok=True)
    baseline_manifest = stores / 'source_geotiff/metadata.json'
    atomic_write_json(baseline_manifest, dataset.metadata)
    source_files = []
    for source in dataset.metadata['sources']:
        path = root / source['path']
        source_files.extend({'path': str(p.relative_to(root)), 'bytes': p.stat().st_size,
                             'sha256': sha256_file(p)} for p in sorted(path.parent.glob(path.name + '*'))
                            if p.is_file())
    manifest_bytes = baseline_manifest.stat().st_size
    # The generated identity JSON is experiment evidence only: load_source never
    # reads it. Required query storage includes TIFFs and acquisition provenance.
    source_metadata_bytes = sum(f['bytes'] for f in source_loader_inputs)
    research_files = [{'path': str(baseline_manifest.relative_to(root)), 'bytes': manifest_bytes,
                       'sha256': sha256_file(baseline_manifest)}]
    baseline = {'candidate': 'source_geotiff', 'storage': {
        'payload_bytes': sum(f['bytes'] for f in source_files), 'metadata_index_bytes': source_metadata_bytes,
        'metadata_bytes': source_metadata_bytes, 'index_bytes': 0,
        'total_bytes': sum(f['bytes'] for f in source_files) + source_metadata_bytes,
        'files': source_files + source_loader_inputs,
        'metadata_note': 'GeoTIFF embedded grids/masks/index included in payload; only loader-required acquisition provenance counted externally'},
        'research_overhead': {'total_bytes': manifest_bytes, 'files': research_files,
                              'note': 'generated duplicate metadata.json is not read by the loader; excluded from necessary bytes and all storage ratios'},
        'preprocessing': {'wall_ms': None, 'cpu_ms': None,
                          'note': 'existing acquired DEFLATE chips; historical chip production not remeasured'}}
    baseline['queries'] = measure_queries('source_geotiff', None, root, repetitions, warmups, expected_digest, guard)
    outcomes = []
    for candidate in candidates:
        outcome = {'candidate': candidate, 'role': 'recompressed_separate_band_baseline' if
                   candidate == 'separate_zstd' else 'encoding_candidate'}
        try:
            store = stores / candidate
            if store.exists():
                # Do not overwrite evidence referenced by previous runs. A fresh
                # encode uses a bounded sibling directory, checked for identical bytes.
                import tempfile
                with tempfile.TemporaryDirectory(prefix='encode-', dir=root / 'data/experimental/w3') as tmp:
                    preprocessing = child_measure({'operation': 'encode', 'root': str(root), 'guard': guard,
                        'representation': candidate, 'store': str(Path(tmp) / candidate), 'chunk_size': chunk_size})
                    storage = audit_store(Path(tmp) / candidate, preprocessing['codec_report'])
                stored = audit_store(store, preprocessing['codec_report'])
                if stored != storage:
                    raise ValueError('repeat encoding not byte-identical; prior store preserved')
            else:
                preprocessing = child_measure({'operation': 'encode', 'root': str(root), 'guard': guard,
                    'representation': candidate, 'store': str(store), 'chunk_size': chunk_size})
                storage = audit_store(store, preprocessing['codec_report'])
            reconstructed = Dataset(*decode_store(store)).validate()
            band_equal = np.array_equal(dataset.bands, reconstructed.bands)
            mask_equal = np.array_equal(dataset.masks, reconstructed.masks)
            metadata_equal = dataset.metadata == reconstructed.metadata
            answers = [evaluate(reconstructed, p['geometry']) for p in plots]
            comparisons = [{'plot_id': p['plot_id'], 'equal': a == b,
                            'differing_fields': differing_fields(a, b)}
                           for p, a, b in zip(plots, source_results, answers)]
            queries = measure_queries(candidate, store, root, repetitions, warmups, expected_digest, guard)
            exact = band_equal and mask_equal and metadata_equal and all(c['equal'] for c in comparisons)
            outcome.update(status='measured', storage=storage, preprocessing=preprocessing,
                roundtrip={'raw_bands_equal': band_equal, 'all_band_masks_equal': mask_equal,
                           'metadata_equal': metadata_equal, 'pixel_count': int(dataset.bands.shape[1] * dataset.bands.shape[2]),
                           'raw_values_checked': int(dataset.bands.size)},
                fidelity={'cohort': '17 real company-supplied plots; no synthetic cases in benchmark',
                          'plot_count': len(plots), 'exact_count': sum(c['equal'] for c in comparisons),
                          'comparisons': comparisons, 'source_answer_sha256': expected_digest,
                          'compact_answer_sha256': content_hash(answers)}, queries=queries,
                fully_exact=bool(exact and queries['timed_answers_exact']))
        except BenchmarkRaceError:
            raise
        except Exception as exc:
            outcome.update(status='failed', fully_exact=False, error=f'{type(exc).__name__}: {exc}')
        outcomes.append(outcome)
    eligible = [c for c in outcomes if c['fully_exact']]
    winner = min(eligible, key=lambda c: (c['storage']['total_bytes'], c['candidate'])) if eligible else None
    # Detect concurrent implementation/source updates rather than mislabel a mixed run.
    assert_fingerprints(root, guard)
    if load_source(root).metadata != dataset.metadata:
        raise BenchmarkRaceError('source metadata changed during run; repeat after integration settles')
    verify_files(root, baseline['storage']['files'])
    verify_files(root, baseline['research_overhead']['files'])
    for candidate in outcomes:
        if candidate.get('storage'):
            verify_files(root, candidate['storage']['files'], stores / candidate['candidate'])
    result = {'schema_version': BENCHMARK_VERSION, 'experiment_id': exp_id, 'identity': identity,
              'environment': environment(), 'grid': {'shape_rows_columns': dataset.metadata['shape'],
                'width': dataset.bands.shape[2], 'height': dataset.bands.shape[1],
                'transform': dataset.metadata['transform'], 'crs': dataset.metadata['crs']},
              'method': {'query_count_per_batch': len(plots), 'timing_unit': 'ms per complete plot batch',
                'repetitions': repetitions, 'warmups_per_hot_child': warmups,
                'p95_method': 'nearest rank; with 7 repetitions p95 equals maximum',
                'hot': 'one isolated child per representation; load full AOI once then warmups and measured batches',
                'process_cold': 'fresh Python child per repetition; timed full load+query after imports and geometry read',
                'os_file_cache': 'uncontrolled and likely warm after verification/encoding; NOT disk-cold',
                'subprocess_wall': 'includes startup/imports/common geometry read/JSON output and exit',
                'load': 'includes validation and integrity hashing performed by each native loader',
                'resources': 'separate child lifetime peak RSS; not incremental operation-only memory',
                'storage': 'only files required by actual loaders; original TIFFs plus acquisition provenance; generated duplicate metadata counted separately as research overhead',
                'common_inputs': 'geometry and supplier input bytes reported separately and excluded symmetrically',
                'excluded': ['UI', 'network acquisition', 'full source tiles', 'tile-to-chip crop savings',
                             'disk-cold claims', 'legal compliance or satellite ground-truth accuracy'],
                'execution_order': ['source_geotiff', *candidates], 'parallel_benchmark_children': False},
              'common_input_bytes': sum(f['bytes'] for f in common), 'baseline': baseline,
              'candidates': outcomes, 'winner': None if winner is None else {
                'candidate': winner['candidate'], 'criterion': 'minimum total stored bytes among fully exact candidates',
                'total_bytes': winner['storage']['total_bytes'],
                'ratio_to_source_total': winner['storage']['total_bytes'] / baseline['storage']['total_bytes'],
                'hot_batch_median_ms': winner['queries']['hot']['wall_ms']['median'],
                'process_cold_batch_median_ms': winner['queries']['process_cold']['wall_ms']['median'],
                'source_hot_batch_median_ms': baseline['queries']['hot']['wall_ms']['median'],
                'source_process_cold_batch_median_ms': baseline['queries']['process_cold']['wall_ms']['median'],
                'smaller_than_source': winner['storage']['total_bytes'] < baseline['storage']['total_bytes']},
              'overall_storage_choice': 'source_geotiff' if winner is None or
                baseline['storage']['total_bytes'] <= winner['storage']['total_bytes'] else winner['candidate']}
    assert_fingerprints(root, guard)
    result['registry'] = record_experiment(identity, result, root / 'artifacts/experiments')
    updated = publish and publish_benchmark(result, root / 'artifacts/experiments',
                                            root / 'artifacts/benchmark-v1.json')
    result['publication'] = {'canonical_updated': bool(updated), 'requested': publish}
    return result


def verify_files(root, files, base=None):
    base = Path(base) if base is not None else Path(root)
    for entry in files:
        path = base / entry['path']
        if (not path.is_file() or path.stat().st_size != entry['bytes'] or
                sha256_file(path) != entry['sha256']):
            raise BenchmarkRaceError(f'measured file changed: {path}')


def run_benchmark(*, root=None, repetitions=7, warmups=2, chunk_size=128, candidates=None, publish=True):
    """Record failed runs visibly and never publish a timing/fingerprint race."""
    try:
        return _run_benchmark(root=root, repetitions=repetitions, warmups=warmups,
                              chunk_size=chunk_size, candidates=candidates, publish=publish)
    except Exception as exc:
        failure = {'schema_version': 'plotline.benchmark-failure.v1',
                   'status': 'aborted', 'error': f'{type(exc).__name__}: {exc}',
                   'details': getattr(exc, 'details', None),
                   'settings': {'repetitions': repetitions, 'warmups': warmups,
                                'chunk_size': chunk_size, 'candidates': list(candidates) if candidates else None}}
        target = Path(root) if root is not None else ROOT
        atomic_write_json(target / 'artifacts/experiments/failures' / ('failure-' + content_hash(failure) + '.json'), failure)
        raise


def retain_benchmark(result, reason, root=None):
    """Freeze deliberate retained evidence after checking live fingerprints/files."""
    root = Path(root) if root is not None else ROOT
    identity = result['identity']
    guard = {'implementation': identity['implementation_sha256'], 'inputs': identity['input_sha256']}
    assert_fingerprints(root, guard)
    verify_files(root, result['baseline']['storage']['files'])
    verify_files(root, result['baseline'].get('research_overhead', {}).get('files', []))
    for candidate in result['candidates']:
        if candidate.get('storage'):
            verify_files(root, candidate['storage']['files'],
                         root / 'artifacts/stores' / result['experiment_id'] / candidate['candidate'])
    assert_fingerprints(root, guard)
    return freeze_selection(result, reason, root / 'artifacts/experiments', root / 'artifacts/benchmark-v1.json')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--worker', action='store_true', help=argparse.SUPPRESS)
    parser.add_argument('--repetitions', type=int, default=7)
    parser.add_argument('--warmups', type=int, default=2)
    parser.add_argument('--chunk-size', type=int, default=128)
    parser.add_argument('--candidates', nargs='+')
    parser.add_argument('--no-publish', action='store_true')
    parser.add_argument('--retain-reason', help='deliberately freeze this measured run')
    args = parser.parse_args()
    if args.worker:
        print(json.dumps(_worker(json.load(sys.stdin)), allow_nan=False))
        return
    (ROOT / 'data/experimental/w3').mkdir(parents=True, exist_ok=True)
    result = run_benchmark(repetitions=args.repetitions, warmups=args.warmups, chunk_size=args.chunk_size,
                           candidates=args.candidates, publish=not args.no_publish)
    if args.retain_reason:
        retain_benchmark(result, args.retain_reason)
    print(json.dumps({'registry': result['registry'], 'winner': result['winner'],
                      'publication': result['publication'],
                      'failed': [c['candidate'] for c in result['candidates'] if not c['fully_exact']]}, indent=2))
    if any(not c['fully_exact'] for c in result['candidates']):
        raise SystemExit(1)


if __name__ == '__main__':
    main()
