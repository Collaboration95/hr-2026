"""Isolated-process benchmark of the decision layers against the original-layers baselines.

Run with `.venv-data/bin/python -B -m engine.decision_benchmark [--quick]`. It follows the
retained harness (engine/benchmark.py): every timed path runs in its own fresh child with one
thread, answers are bound by digest to pinned expected outputs before anything is published,
and p95 is the nearest rank. Writes artifacts/decision/benchmark-v1.json.

Paths (each in its own child process):

  P0  original_v1        load_source + engine.query.evaluate (3 Hansen bands, the retained v1 question)
  P1  original_eudr      load_source + load_jrc + evaluate_original (original layers, same contract question)
  P2  screen_store       read_store(screen.plds) + evaluate_store
  P3  decision_store     read_store(decision.plds) + evaluate_store
  P4  fast_select        decision store + evaluate_store(select=fast_select_cells)
  P4B batch_select       decision store + engine.decision_batch.evaluate_many: the whole workload in ONE call, one
                         vectorized pass (answers unregistered polygons like P4; needs the whole batch in hand)
  P5  registry           store + registry.bin + registry_evaluate_store (registered plots only)
  P5L lite re-check      store + registry.bin read without numpy, codes decoded at the registered cells straight from
                         the packed bit-planes (engine.decision_lite; registered plots only, stdlib only)
  P6  table              table.json + table_lookup (registered plots only, stdlib only)

Workloads: W1 the 17 supplied plots; W2 the same 17 geometries treated as unregistered (the same
computation as W1 for P0-P4B, which ignore registration); W3 500 seeded synthetic plot-like polygons
(synthetic, not company data); W4 100 boundary-stressing polygons from the test fuzz generator.

A path flagged `batch` (P4B) is called once per workload with the whole item list instead of once per
item; its per-plot figures are batch time / items, like every other path's.

Metrics: hot batches (two fresh children per path per run), process-cold (load + query after
imports), end-to-end fresh interpreter including imports, peak RSS, bytes held in memory, bytes
read from disk. The whole benchmark runs twice per invocation and the samples are pooled; the
spread between runs and between hot children is reported. `--replicate-of FILE` embeds and compares
an earlier independent invocation. Outputs are mapped observations, never legal findings.
"""
import hashlib
import json
import os
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCHEMA = 'plotline.decision-benchmark.v1'
RESULT = ROOT / 'artifacts/decision/benchmark-v1.json'
SCREEN, DECISION = 'eudr-screen.v1', 'eudr-decision.v1'
LEVEL_NAME = {'screen': SCREEN, 'decision': DECISION}
STORE_FILE = {'screen': 'screen.plds', 'decision': 'decision.plds'}
PATHS = {
    'P0': {'name': 'original_v1', 'level': None, 'kind': 'v1', 'registered': False,
           'what': 'load_source (3 Hansen GeoTIFFs) + engine.query.evaluate; answers the bigger v1 question'},
    'P1s': {'name': 'original_eudr', 'level': 'screen', 'kind': 'screen', 'registered': False,
            'what': 'load_source + load_jrc + evaluate_original, eudr-screen.v1'},
    'P1d': {'name': 'original_eudr', 'level': 'decision', 'kind': 'decision', 'registered': False,
            'what': 'load_source + load_jrc + evaluate_original, eudr-decision.v1'},
    'P2': {'name': 'screen_store', 'level': 'screen', 'kind': 'screen', 'registered': False,
           'what': 'read_store(screen.plds) + evaluate_store'},
    'P3': {'name': 'decision_store', 'level': 'decision', 'kind': 'decision', 'registered': False,
           'what': 'read_store(decision.plds) + evaluate_store'},
    'P4': {'name': 'decision_store_fast_select', 'level': 'decision', 'kind': 'decision', 'registered': False,
           'what': 'read_store(decision.plds) + evaluate_store with fast_select_cells'},
    'P4B': {'name': 'decision_store_batch_select', 'level': 'decision', 'kind': 'decision', 'registered': False, 'batch': True,
            'what': 'read_store(decision.plds) + evaluate_many (whole workload in one call, one vectorized pass)'},
    'P5s': {'name': 'screen_registry', 'level': 'screen', 'kind': 'screen', 'registered': True,
            'what': 'read_store(screen.plds) + load_registry + registry_evaluate_store, registered plots only'},
    'P5d': {'name': 'decision_registry', 'level': 'decision', 'kind': 'decision', 'registered': True,
            'what': 'read_store(decision.plds) + load_registry + registry_evaluate_store, registered plots only'},
    'P5Ls': {'name': 'screen_registry_lite', 'level': 'screen', 'kind': 'screen', 'registered': True,
             'what': 'decision_lite.load (screen.plds + registry.bin, no numpy, packed planes) + evaluate, registered plots only'},
    'P5Ld': {'name': 'decision_registry_lite', 'level': 'decision', 'kind': 'decision', 'registered': True,
             'what': 'decision_lite.load (decision.plds + registry.bin, no numpy, packed planes) + evaluate, registered plots only'},
    'P6s': {'name': 'screen_table', 'level': 'screen', 'kind': 'screen', 'registered': True,
            'what': 'load_table + table_lookup (screen level), registered plots only, stdlib only'},
    'P6d': {'name': 'decision_table', 'level': 'decision', 'kind': 'decision', 'registered': True,
            'what': 'load_table + table_lookup (decision level), registered plots only, stdlib only'}}
ORDER = tuple(PATHS)
GEOMETRY_PATHS = ('P0', 'P1s', 'P1d', 'P2', 'P3', 'P4', 'P4B')  # answer unregistered polygons
HOT_W4_PATHS = ('P3', 'P4', 'P4B')
CHILD_ENV = {'PYTHONDONTWRITEBYTECODE': '1', 'OMP_NUM_THREADS': '1', 'OPENBLAS_NUM_THREADS': '1',
             'MKL_NUM_THREADS': '1', 'VECLIB_MAXIMUM_THREADS': '1'}
PYC_MODULES = ('model', 'source', 'query', 'jrc', 'decision', 'decision_original', 'decision_store',
               'decision_index', 'decision_batch', 'decision_summary', 'decision_format', 'decision_lite', 'decision_benchmark')


class BenchmarkError(RuntimeError):
    """A measurement cannot be bound to its expected implementation, inputs or answers."""


# ---- shared by parent and children (stdlib only) -----------------------------------------------

def canonical_bytes(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=True, allow_nan=False).encode()


def digest(value):
    """Same definition as engine.experiments.content_hash."""
    return hashlib.sha256(canonical_bytes(value)).hexdigest()


def sha256_file(path):
    h = hashlib.sha256()
    with open(path, 'rb') as stream:
        for block in iter(lambda: stream.read(1 << 20), b''):
            h.update(block)
    return h.hexdigest()


def rss_record():
    import resource
    native = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    unit = 'bytes' if sys.platform == 'darwin' else 'KiB'
    return {'native_value': native, 'native_unit': unit, 'bytes': int(native if unit == 'bytes' else native * 1024),
            'scope': 'child lifetime high-water mark including Python/imports, inputs and operation'}


def _need(value):
    if value is None:
        raise BenchmarkError('registered lookup missed: stale or unknown key')
    return value


def _bind(pid, ctx):
    """Import only what this path needs; return (load, variants, held_bytes).

    Everything that would import lazily at first use is imported here, so process-cold timing
    covers load + query after imports exactly as in the retained harness.
    """
    spec, root = PATHS[pid], Path(ctx['root'])
    out = root / 'artifacts/decision'
    level = LEVEL_NAME.get(spec['level'])
    if pid == 'P0':
        from .query import evaluate
        from .source import load_source
        return (lambda: load_source(root), {'default': lambda s, it: evaluate(s, it['geometry'])},
                lambda s: int(s.bands.nbytes + s.masks.nbytes))
    if pid in ('P1s', 'P1d'):
        from .decision_original import evaluate_original
        from .jrc import load_jrc
        from .source import load_source
        return (lambda: (load_source(root), load_jrc(root)),
                {'default': lambda s, it: evaluate_original(s[0], s[1], it['geometry'], level)},
                lambda s: int(s[0].bands.nbytes + s[0].masks.nbytes + s[1].values.nbytes + s[1].mask.nbytes))
    if pid in ('P2', 'P3'):
        from .decision import evaluate_store
        from .decision_store import read_store
        from .query import select_cells  # noqa: F401  (evaluate_store imports it lazily)
        store = out / STORE_FILE[spec['level']]
        return (lambda: read_store(store),
                {'default': lambda s, it: evaluate_store(s[0], s[1], it['geometry'], level)},
                lambda s: int(s[0].nbytes))
    if pid == 'P4B':
        from . import decision_batch, decision_index as di
        from .decision_store import read_store
        di._numpy()
        di._geos()
        store = out / STORE_FILE[spec['level']]
        return (lambda: read_store(store),
                {'default': lambda s, items: decision_batch.evaluate_many(s[0], s[1], [it['geometry'] for it in items], level)},
                lambda s: int(s[0].nbytes))
    if pid in ('P4', 'P5s', 'P5d'):
        from . import decision_index as di
        from .decision import evaluate_store
        from .decision_store import read_store
        di._numpy()
        store = out / STORE_FILE[spec['level']]
        if pid == 'P4':
            di._geos()
            return (lambda: read_store(store),
                    {'default': lambda s, it: evaluate_store(s[0], s[1], it['geometry'], level, di.fast_select_cells)},
                    lambda s: int(s[0].nbytes))

        def load():
            codes, header = read_store(store)
            return codes, header, di.load_registry(out / 'registry.bin')

        def pre(s, it):
            entry = s[2]['plots'][it['plot_id']]
            if entry['geometry_sha256'] != it['geometry_sha256']:
                raise BenchmarkError('registry entry does not match the registered geometry hash')
            return di.registry_evaluate_store(s[0], s[1], entry, level)  # level and grid checked on every call

        def geom(s, it):
            entry = _need(di.registry_lookup(s[2], it['plot_id'], it['geometry'], s[1]))
            return di.registry_evaluate_store(s[0], s[1], entry, level)
        return (load, {'precomputed_hash': pre, 'hash_geometry_per_call': geom},
                lambda s: int(s[0].nbytes + sum(e['flat_index'].nbytes for e in s[2]['plots'].values())))
    if pid in ('P5Ls', 'P5Ld'):
        from . import decision_lite as lite  # stdlib only: numpy is never imported on this path
        from .decision_index import geometry_sha256
        store, sha = out / STORE_FILE[spec['level']], ctx['store_sha256'][spec['level']]  # layer identity from the request, as P6
        return (lambda: lite.load(store, out / 'registry.bin', expected_sha256=sha, level=level),
                {'precomputed_hash': lambda s, it: s.evaluate(it['plot_id'], it['geometry_sha256']),
                 'hash_geometry_per_call': lambda s, it: s.evaluate(it['plot_id'], geometry_sha256(it['geometry']))},
                lambda s: int(sum(len(p[3]) for p in s.plots.values())))
    if pid in ('P6s', 'P6d'):
        from .decision_index import geometry_sha256, load_table, table_lookup
        sha = ctx['store_sha256'][spec['level']]  # layer-version identity supplied with the request
        return (lambda: load_table(out / 'table.json'),
                {'precomputed_hash': lambda t, it: _need(table_lookup(t, it['plot_id'], it['geometry_sha256'], sha, level)),
                 'hash_geometry_per_call': lambda t, it: _need(table_lookup(
                     t, it['plot_id'], geometry_sha256(it['geometry']), sha, level))},
                lambda t: 0)
    raise ValueError(f'unknown path {pid}')


def _answers(pid, fn, state, items):
    """The answers for `items`: one call per item, or for a batch path (PATHS[pid]['batch']) one call for all of them."""
    return fn(state, items) if PATHS[pid].get('batch') else [fn(state, it) for it in items]


def _timed(fn, cpu_clock=time.process_time_ns):
    wall, cpu = time.perf_counter_ns(), cpu_clock()
    value = fn()
    return value, (time.perf_counter_ns() - wall) / 1e6, (cpu_clock() - cpu) / 1e6


def _hot(req):
    load, variants, held = _bind(req['path'], req)
    state, load_wall, load_cpu = _timed(load)
    out = {'load_ms': load_wall, 'load_cpu_ms': load_cpu, 'held_bytes': held(state), 'variants': {}}
    for name, fn in variants.items():
        per_workload = {}
        for workload, items in req['workloads'].items():
            warmups, repetitions = req['plan'][workload]

            def batch(fn=fn, items=items):
                return _answers(req['path'], fn, state, items)
            for _ in range(warmups):
                batch()
            walls, cpus, digests = [], [], set()
            for _ in range(repetitions):
                wall, cpu = time.perf_counter_ns(), time.thread_time_ns()
                answers = batch()
                walls.append((time.perf_counter_ns() - wall) / 1e6)
                cpus.append((time.thread_time_ns() - cpu) / 1e6)
                digests.add(digest(answers))
            per_workload[workload] = {'wall_ms': walls, 'cpu_ms': cpus, 'answer_sha256': sorted(digests),
                                      'plots_per_batch': len(items)}
        out['variants'][name] = per_workload
    out['peak_rss'] = rss_record()
    return out


def _cold(req):
    load, variants, held = _bind(req['path'], req)
    fn = next(iter(variants.values()))
    state, load_wall, load_cpu = _timed(load)
    answers, query_wall, query_cpu = _timed(lambda: _answers(req['path'], fn, state, req['items']))
    return {'load_ms': load_wall, 'query_ms': query_wall, 'wall_ms': load_wall + query_wall,
            'cpu_ms': load_cpu + query_cpu, 'answer_sha256': digest(answers), 'peak_rss': rss_record(),
            'held_bytes': held(state)}


def _memory(req):
    """Untimed: Python/numpy-level allocations held after load (tracemalloc; GDAL's C buffers are not seen)."""
    import gc
    import tracemalloc
    load, variants, held = _bind(req['path'], req)
    fn = next(iter(variants.values()))
    gc.collect()
    tracemalloc.start()
    state = load()
    gc.collect()
    after_load, peak_load = tracemalloc.get_traced_memory()
    answers = _answers(req['path'], fn, state, req['items'])
    gc.collect()
    after_query, peak_query = tracemalloc.get_traced_memory()
    tracemalloc.stop()
    return {'held_array_bytes': held(state), 'traced_after_load_bytes': after_load, 'traced_peak_load_bytes': peak_load,
            'traced_after_query_bytes': after_query, 'traced_peak_query_bytes': peak_query,
            'answer_sha256': digest(answers)}


def _worker(req):
    return {'hot': _hot, 'cold': _cold, 'memory': _memory}[req['mode']](req)


def _e2e(pid):
    """Fresh interpreter: import only what the path needs, load, answer the request, print the digest.

    The parent measures the whole process, so interpreter start-up and every import are included.
    `NOOP` does the request parse and digest only: the harness floor.
    """
    t0 = time.perf_counter()
    request = json.load(sys.stdin)
    if pid == 'NOOP':
        t1 = t2 = t3 = time.perf_counter()
        answers = []
    else:
        load, variants, _ = _bind(pid, request)
        fn = next(iter(variants.values()))
        t1 = time.perf_counter()
        state = load()
        t2 = time.perf_counter()
        answers = _answers(pid, fn, state, request['items'])
        t3 = time.perf_counter()
    sys.stdout.write(json.dumps({
        'answer_sha256': digest(answers), 'peak_rss': rss_record(),
        'phase_ms': {'imports': (t1 - t0) * 1e3, 'load': (t2 - t1) * 1e3, 'query': (t3 - t2) * 1e3}}))


# ---- parent: fingerprints, workloads, expected answers -------------------------------------------

def full_config():
    return {'name': 'full', 'runs': 2, 'hot_rounds': 2, 'w3_polygons': 500, 'w4_polygons': 100, 'seed': 20261015,
            'cold_reps': 21, 'e2e_reps': 21, 'baseline_reps': 21,
            'plan': {'W1': (50, 500), 'W1_registered': (100, 1000), 'W3': (3, 40), 'W4': (2, 40)}}


def quick_config():
    return {'name': 'quick', 'runs': 1, 'hot_rounds': 1, 'w3_polygons': 60, 'w4_polygons': 20, 'seed': 20261015,
            'cold_reps': 3, 'e2e_reps': 3, 'baseline_reps': 3,
            'plan': {'W1': (5, 10), 'W1_registered': (5, 50), 'W3': (1, 3), 'W4': (1, 3)}}


def run_child(args, request=None, timeout=900):
    """One fresh `python -B` process; returns (stdout bytes, parent-measured wall ms)."""
    import subprocess
    wall = time.perf_counter_ns()
    done = subprocess.run([sys.executable, '-B', *args], input=b'' if request is None else canonical_bytes(request),
                          capture_output=True, cwd=ROOT, env=dict(os.environ, **CHILD_ENV), timeout=timeout,
                          check=False)
    elapsed = (time.perf_counter_ns() - wall) / 1e6
    if done.returncode:
        raise BenchmarkError(done.stderr.decode(errors='replace')[-4000:])
    return done.stdout, elapsed


def worker(request):
    out, elapsed = run_child(['-m', 'engine.decision_benchmark', '--worker'], request)
    result = json.loads(out)
    result['subprocess_wall_ms'] = elapsed
    return result


def end_to_end(pid, request):
    out, elapsed = run_child(['-m', 'engine.decision_benchmark', '--e2e', pid], request)
    result = json.loads(out)
    result['wall_ms'] = elapsed
    return result


def input_files():
    from . import jrc, source
    data = ROOT / 'data/public'
    files = [data / 'provenance.json', *sorted(data.glob('hansen_*_sample.tif')),
             *(ROOT / n for n in (jrc.CHIP, jrc.PROVENANCE, jrc.QML, jrc.XML)),
             ROOT / source.SAMPLE / source.CSV_NAME, ROOT / source.SAMPLE / source.GEOJSON_NAME]
    files += [ROOT / 'artifacts/decision' / n for n in
              ('screen.plds', 'decision.plds', 'registry.bin', 'table.json', 'proof-v1.json')]
    return files


def fingerprints():
    code = {f'engine/{n}.py': sha256_file(ROOT / 'engine' / f'{n}.py') for n in PYC_MODULES}
    return {'implementation': code,
            'inputs': {str(p.relative_to(ROOT)): sha256_file(p) for p in input_files()}}


def warm_bytecode():
    """Compile every module a child imports, so old and new modules start with bytecode caches.

    Children run `python -B`: they read an existing __pycache__ but never write one. Without this the
    uncached decision modules would be recompiled at every start-up and the comparison would charge
    them for it while the older modules were free. The caches are gitignored build products.
    """
    import importlib.util
    import py_compile
    state = {}
    for name in PYC_MODULES:
        path = ROOT / 'engine' / f'{name}.py'
        py_compile.compile(str(path), cfile=importlib.util.cache_from_source(str(path)), doraise=True)
        state[f'engine/{name}.py'] = Path(importlib.util.cache_from_source(str(path))).is_file()
    return state


def uncached_compile_ms():
    """What start-up would add per module without a bytecode cache (compile only, no import)."""
    out = {}
    for name in PYC_MODULES:
        path = ROOT / 'engine' / f'{name}.py'
        source = path.read_text()
        samples = []
        for _ in range(5):
            wall = time.perf_counter_ns()
            compile(source, str(path), 'exec')
            samples.append((time.perf_counter_ns() - wall) / 1e6)
        out[f'engine/{name}.py'] = round(sorted(samples)[2], 3)
    return out


def synthetic_polygons(count, seed, metadata, land):
    """Seeded plot-like polygons: synthetic, not company data.

    Star-shaped about an interior point (sorted angles with gaps under 0.9 pi, radii 0.35-1 of the
    unit), then stretched 1-2.2x and rotated: concave, elongated, valid. About 15% carry a hole
    (the shell scaled by 0.3). Net area is log-uniform in 0.5-20 ha, measured with local
    metres-per-degree. Centres sit on land cells of the screen layer; polygons stay inside the chip.
    """
    import numpy as np
    from shapely.geometry import Polygon
    a, _, c, _, e, f = metadata['transform']
    height, width = metadata['shape']
    rng = np.random.default_rng(seed)
    rows, cols = np.nonzero(land)
    west, east, north, south = c, c + width * a, f, f + height * e
    polygons, meta = [], []
    while len(polygons) < count:
        target = float(np.exp(rng.uniform(np.log(.5), np.log(20.))))
        n = int(rng.integers(7, 25))
        ang = np.sort(rng.uniform(0, 2 * np.pi, n))
        gaps = np.diff(np.append(ang, ang[0] + 2 * np.pi))
        rad = rng.uniform(.35, 1., n)
        stretch, turn, has_hole = rng.uniform(1., 2.2), rng.uniform(0, np.pi), bool(rng.random() < .15)
        k = int(rng.integers(len(rows)))
        lon0 = c + (cols[k] + .5 + rng.uniform(-.5, .5)) * a
        lat0 = f + (rows[k] + .5 + rng.uniform(-.5, .5)) * e
        if gaps.max() > .9 * np.pi or gaps.min() < 1e-3:
            continue
        x, y = rad * np.cos(ang) * stretch, rad * np.sin(ang)
        x, y = x * np.cos(turn) - y * np.sin(turn), x * np.sin(turn) + y * np.cos(turn)
        unit_area = .5 * abs(float(np.dot(x, np.roll(y, -1)) - np.dot(y, np.roll(x, -1))))
        phi = np.radians(lat0)
        m_lat = 111132.92 - 559.82 * np.cos(2 * phi) + 1.175 * np.cos(4 * phi)
        m_lon = 111412.84 * np.cos(phi) - 93.5 * np.cos(3 * phi)
        scale = float(np.sqrt(target * 1e4 / (unit_area * (1 - .09 * has_hole))))

        def ring(factor, reverse):
            pts = [[round(float(lon0 + factor * u * scale / m_lon), 7), round(float(lat0 + factor * v * scale / m_lat), 7)]
                   for u, v in zip(x, y)]
            pts = pts[::-1] if reverse else pts
            return pts + [pts[0]]
        rings = [ring(1., False)] + ([ring(.3, True)] if has_hole else [])
        polygon = Polygon(rings[0], rings[1:])
        minx, miny, maxx, maxy = polygon.bounds
        area_ha = polygon.area * m_lon * m_lat / 1e4
        if (not polygon.is_valid or not (west < minx and maxx < east and south < miny and maxy < north)
                or not .5 <= area_ha <= 20.):
            continue
        polygons.append({'plot_id': f'S-{len(polygons) + 1:04d}',
                         'geometry': {'type': 'Polygon', 'coordinates': rings}})
        meta.append({'area_ha': area_ha, 'vertices': n, 'hole': has_hole})
    return polygons, meta


def boundary_polygons(count, seed, metadata):
    """Adversarial polygons for fast selection: the test fuzz generator minus its generic shapes."""
    from . import decision_index as di
    from .query import select_cells
    from .tests.test_decision_index import fuzz_geometries
    labels = []
    geometries = fuzz_geometries(metadata, 8 * count, seed, labels)
    chosen, kinds = [], {}
    for geometry, label in zip(geometries, labels):
        if label in ('convex', 'star', 'blob') or len(chosen) >= count:
            continue
        try:
            select_cells(metadata, geometry)
            di.fast_select_cells(metadata, geometry)
        except ValueError:
            continue
        chosen.append({'plot_id': f'B-{len(chosen) + 1:04d}', 'geometry': geometry})
        kinds[label] = kinds.get(label, 0) + 1
    if len(chosen) < count:
        raise BenchmarkError('boundary workload generator produced too few accepted polygons')
    return chosen, kinds


def _equal(label, left, right, binding):
    bad = [i for i, (a, b) in enumerate(zip(left, right)) if a != b]
    if len(left) != len(right) or bad:
        raise BenchmarkError(f'{label}: {len(bad)} of {len(left)} answers differ (first at {bad[:5]})')
    binding.append({'check': label, 'compared': len(left), 'equal': len(left)})


def build_context(cfg):
    """Load pinned inputs, build every workload, and bind expected answers before any timing."""
    import numpy as np
    from . import decision, decision_batch, decision_index as di
    from . import decision_lite
    from .decision_original import evaluate_original
    from .decision_store import read_store
    from .jrc import load_jrc
    from .query import evaluate
    from .source import load_plots, load_source
    di._numpy()
    out = ROOT / 'artifacts/decision'
    hansen, jrc, plots = load_source(), load_jrc(), load_plots()
    stores = {k: read_store(out / STORE_FILE[k]) for k in STORE_FILE}
    store_sha = {k: sha256_file(out / STORE_FILE[k]) for k in STORE_FILE}
    proof = json.loads((out / 'proof-v1.json').read_text())
    if not proof['summary']['all_pass']:
        raise BenchmarkError('proof-v1.json does not record all checks passing')
    table, registry = di.load_table(out / 'table.json'), di.load_registry(out / 'registry.bin')
    items = {'W1': [{'plot_id': p['plot_id'], 'geometry': p['geometry'],
                     'geometry_sha256': di.geometry_sha256(p['geometry'])} for p in plots]}
    binding, expected, proof_outputs = [], {'W1': {}, 'W3': {}, 'W4': {}}, {}
    for key, name in LEVEL_NAME.items():
        block = proof['plot_proof'][name]
        rows = block['plots']
        if [r['plot_id'] for r in rows] != [it['plot_id'] for it in items['W1']]:
            raise BenchmarkError('proof plot IDs or order differ from the supplied plots')
        for r, it in zip(rows, items['W1']):
            if r['geometry_sha256'] != it['geometry_sha256'] or digest(r['output']) != r['output_sha256']:
                raise BenchmarkError(f'proof entry for {it["plot_id"]} differs from the geometry or its own hash')
        if block['equal_derived'] != len(rows) or block['equal_store'] != len(rows):
            raise BenchmarkError('proof does not record every plot equal at ' + name)
        if proof['stores'][name]['sha256'] != store_sha[key] or table['stores'][name] != store_sha[key]:
            raise BenchmarkError('store file differs from the store the proof and table are bound to')
        proof_outputs[key] = [r['output'] for r in rows]
        expected['W1'][key] = digest(proof_outputs[key])
    codes_s, head_s = stores['screen']
    codes_d, head_d = stores['decision']

    def original(geoms):
        return {'v1': [evaluate(hansen, g) for g in geoms],
                'screen': [evaluate_original(hansen, jrc, g, SCREEN) for g in geoms],
                'decision': [evaluate_original(hansen, jrc, g, DECISION) for g in geoms]}

    def stored(geoms):
        return {'screen': [decision.evaluate_store(codes_s, head_s, g, SCREEN) for g in geoms],
                'decision': [decision.evaluate_store(codes_d, head_d, g, DECISION) for g in geoms],
                'fast': [decision.evaluate_store(codes_d, head_d, g, DECISION, di.fast_select_cells) for g in geoms],
                'batch': decision_batch.evaluate_many(codes_d, head_d, geoms, DECISION)}  # the whole workload, one call

    def bind(workload, geoms, with_v1=True):
        o, s = original(geoms), stored(geoms)
        _equal(f'{workload}: P1s original == P2 screen store', o['screen'], s['screen'], binding)
        _equal(f'{workload}: P1d original == P3 decision store', o['decision'], s['decision'], binding)
        _equal(f'{workload}: P3 select_cells == P4 fast_select_cells', s['decision'], s['fast'], binding)
        _equal(f'{workload}: P4 fast_select_cells loop == P4B evaluate_many', s['fast'], s['batch'], binding)
        for kind in ('screen', 'decision'):
            expected[workload].setdefault(kind, digest(o[kind]))
        expected[workload]['v1'] = digest(o['v1'])
        return o

    o1 = bind('W1', [it['geometry'] for it in items['W1']])
    for key in ('screen', 'decision'):
        _equal(f'W1: P1 original == proof outputs ({key})', o1[key], proof_outputs[key], binding)
        _equal(f'W1: P5 registry == proof outputs ({key})',
               [di.registry_evaluate_store(*stores[key], registry['plots'][it['plot_id']], LEVEL_NAME[key])
                for it in items['W1']], proof_outputs[key], binding)
        lite = decision_lite.load(out / STORE_FILE[key], out / 'registry.bin', expected_sha256=store_sha[key], level=LEVEL_NAME[key])
        _equal(f'W1: P5L lite == proof outputs ({key})',
               [lite.evaluate(it['plot_id'], it['geometry_sha256']) for it in items['W1']], proof_outputs[key], binding)
        _equal(f'W1: P6 table == proof outputs ({key})',
               [di.table_lookup(table, it['plot_id'], it['geometry_sha256'], store_sha[key], LEVEL_NAME[key])
                for it in items['W1']], proof_outputs[key], binding)
        if expected['W1'][key] != digest(proof_outputs[key]):
            raise BenchmarkError('W1 expected digest is not the proof digest')
    retained = json.loads((ROOT / 'artifacts/benchmark-v1.json').read_text())['baseline']['queries']['hot']['answer_sha256']
    if retained != [expected['W1']['v1']]:
        raise BenchmarkError('P0 v1 answers differ from the retained artifacts/benchmark-v1.json digest')
    binding.append({'check': 'W1: P0 evaluate digest == retained benchmark-v1.json digest', 'compared': 17, 'equal': 17})

    w3, w3_meta = synthetic_polygons(cfg['w3_polygons'], cfg['seed'], head_d, codes_s >= decision.LAND)
    items['W3'] = [dict(p, geometry_sha256=di.geometry_sha256(p['geometry'])) for p in w3]
    o3 = bind('W3', [p['geometry'] for p in w3])
    w4, w4_kinds = boundary_polygons(cfg['w4_polygons'], cfg['seed'], head_d)
    items['W4'] = [dict(p, geometry_sha256=di.geometry_sha256(p['geometry'])) for p in w4]
    s4, o4 = stored([p['geometry'] for p in w4]), [evaluate_original(hansen, jrc, p['geometry'], DECISION) for p in w4]
    _equal('W4: P1d original == P3 decision store', o4, s4['decision'], binding)
    _equal('W4: P3 select_cells == P4 fast_select_cells', s4['decision'], s4['fast'], binding)
    _equal('W4: P4 fast_select_cells loop == P4B evaluate_many', s4['fast'], s4['batch'], binding)
    expected['W4'] = {'decision': digest(o4)}

    def spread(values):
        v = sorted(values)
        return {'min': v[0], 'median': v[len(v) // 2], 'max': v[-1]}
    d3 = o3['decision']
    stats = {
        'W1': {'what': 'the 17 supplied company plots (real geometry)', 'plots': 17,
               'selected_cells': spread([o['selected_cell_count'] for o in o1['decision']])},
        'W2': {'what': 'the same 17 geometries treated as unregistered (no registry or table): for P0-P4B this is '
                       'computationally identical to W1, which never uses registration, so it is measured once '
                       'and reported under both names; P5/P6 cannot answer it'},
        'W3': {'what': 'SYNTHETIC plot-like polygons (not company data), seeded', 'polygons': len(w3), 'seed': cfg['seed'],
               'area_ha': spread([m['area_ha'] for m in w3_meta]), 'vertices_per_shell': spread([m['vertices'] for m in w3_meta]),
               'with_hole_share': sum(m['hole'] for m in w3_meta) / len(w3_meta),
               'selected_cells': spread([o['selected_cell_count'] for o in d3]),
               'with_valid_land_share': sum(o['valid_land_cell_count'] > 0 for o in d3) / len(d3),
               'forest_2020_present_share': sum(o['forest_2020']['present'] is True for o in d3) / len(d3),
               'deforestation_present_share': sum(o['deforestation_after_2020']['present'] is True for o in d3) / len(d3),
               'generator': synthetic_polygons.__doc__.strip()},
        'W4': {'what': 'adversarial boundary-stressing polygons from the test fuzz generator (aligned edges, vertices '
                       'on cell centres, ulp offsets, slivers, lattices); P3, P4 and P4B only',
               'polygons': len(w4), 'kinds': w4_kinds, 'selected_cells': spread([o['selected_cell_count'] for o in o4])}}
    return {'root': str(ROOT), 'store_sha256': store_sha, 'items': items, 'expected': expected, 'binding': binding,
            'workload_stats': stats, 'np_version': np.__version__}


def storage_record():
    """Bytes each path must read from disk, taken from the files themselves."""
    from . import jrc
    data, out = ROOT / 'data/public', ROOT / 'artifacts/decision'
    hansen = [data / f'hansen_{b}_sample.tif' for b in ('treecover2000', 'lossyear', 'datamask')]
    v1 = [data / 'provenance.json', *hansen]
    jrc_files = [ROOT / n for n in (jrc.CHIP, jrc.PROVENANCE, jrc.QML, jrc.XML)]
    files = {'P0': v1, 'P1s': v1 + jrc_files, 'P1d': v1 + jrc_files, 'P2': [out / 'screen.plds'],
             'P3': [out / 'decision.plds'], 'P4': [out / 'decision.plds'], 'P4B': [out / 'decision.plds'],
             'P5s': [out / 'screen.plds', out / 'registry.bin'], 'P5d': [out / 'decision.plds', out / 'registry.bin'],
             'P5Ls': [out / 'screen.plds', out / 'registry.bin'], 'P5Ld': [out / 'decision.plds', out / 'registry.bin'],
             'P6s': [out / 'table.json'], 'P6d': [out / 'table.json']}
    record = {}
    for pid, paths in files.items():
        entries = [{'path': str(p.relative_to(ROOT)), 'bytes': p.stat().st_size} for p in paths]
        record[pid] = {'bytes': sum(e['bytes'] for e in entries), 'files': entries}
    minimal = [data / 'hansen_lossyear_sample.tif', data / 'hansen_datamask_sample.tif', ROOT / jrc.CHIP]
    record['note'] = ('P0/P1 load all three Hansen chips because load_source does; the loader also reads '
                      'data/public/provenance.json (and the JRC provenance, QML and XML for P1). Geometry and supplier '
                      'inputs are common to every path and excluded. A table path that must also verify the layer '
                      'version reads the 6.1 KB decision store or 38.5 KB screen store in addition.')
    record['original_contract_minimum_bytes'] = {
        'bytes': sum(p.stat().st_size for p in minimal), 'files': [str(p.relative_to(ROOT)) for p in minimal],
        'note': 'what the contract question needs from the originals (lossyear, datamask, JRC chip) if a reader skipped '
                'treecover2000; the implemented P1 does not'}
    return record


def side_measurements():
    out = ROOT / 'artifacts/decision'
    verify = {}
    for key, name in STORE_FILE.items():
        samples = []
        for _ in range(500):
            wall = time.perf_counter_ns()
            hashlib.sha256((out / name).read_bytes()).hexdigest()
            samples.append((time.perf_counter_ns() - wall) / 1e3)
        verify[key] = round(sorted(samples)[250], 2)
    return {'store_file_read_and_sha256_us_median': verify,
            'note': 'cost of verifying the layer version by hashing the store file, which the table path does not do '
                    'itself (its table_lookup takes the layer sha256 from the request)',
            'uncached_compile_ms': uncached_compile_ms()}


# ---- parent: one measurement pass ----------------------------------------------------------------

def _plan_for(cfg, pid, workload):
    key = 'W1_registered' if workload == 'W1' and PATHS[pid]['registered'] else workload
    return list(cfg['plan'][key])


def _expect(ctx, workload, pid):
    return [ctx['expected'][workload][PATHS[pid]['kind']]]


def measure_run(cfg, ctx, index, log):
    run = {'index': index, 'loadavg_start': os.getloadavg(), 'hot': {p: [] for p in ORDER}, 'cold': {p: [] for p in ORDER},
           'end_to_end': {p: [] for p in (*ORDER, 'NOOP')}, 'python_pass_ms': [], 'memory': {}}
    started = time.perf_counter()
    base = {'root': ctx['root'], 'store_sha256': ctx['store_sha256']}
    for round_index in range(cfg['hot_rounds']):  # alternate direction so a path is not always first or last
        for pid in (ORDER if round_index % 2 == 0 else ORDER[::-1]):
            workloads = {'W1': ctx['items']['W1']}
            if pid in GEOMETRY_PATHS:
                workloads['W3'] = ctx['items']['W3']
            if pid in HOT_W4_PATHS:
                workloads['W4'] = ctx['items']['W4']
            plan = {w: _plan_for(cfg, pid, w) for w in workloads}
            result = worker(dict(base, mode='hot', path=pid, workloads=workloads, plan=plan))
            for variant, per_workload in result['variants'].items():
                for w, got in per_workload.items():
                    if got['answer_sha256'] != _expect(ctx, w, pid):
                        raise BenchmarkError(f'{pid}/{variant}/{w}: timed hot answers differ from the pinned answers')
                    if len(got['wall_ms']) != plan[w][1]:
                        raise BenchmarkError(f'{pid}/{variant}/{w}: wrong number of measured batches')
            result['peak_rss_bytes'] = result.pop('peak_rss')['bytes']
            run['hot'][pid].append(result)
            log(f'  run {index} hot round {round_index + 1} {pid} done')
    n = len(ORDER)
    for rep in range(cfg['cold_reps']):
        for pid in ORDER[rep % n:] + ORDER[:rep % n]:
            got = worker(dict(base, mode='cold', path=pid, items=ctx['items']['W1']))
            if got['answer_sha256'] != _expect(ctx, 'W1', pid)[0]:
                raise BenchmarkError(f'{pid}: process-cold answers differ from the pinned answers')
            got['peak_rss_bytes'] = got.pop('peak_rss')['bytes']
            run['cold'][pid].append(got)
    log(f'  run {index} process-cold done')
    sequence = (*ORDER, 'NOOP')
    for rep in range(max(cfg['e2e_reps'], cfg['baseline_reps'])):
        if rep < cfg['baseline_reps']:
            _, elapsed = run_child(['-c', 'pass'])
            run['python_pass_ms'].append(elapsed)
        if rep >= cfg['e2e_reps']:
            continue
        k = rep % len(sequence)
        for pid in sequence[k:] + sequence[:k]:
            if pid == 'NOOP':
                items = []
            elif PATHS[pid]['registered']:
                items = [{'plot_id': it['plot_id'], 'geometry_sha256': it['geometry_sha256']} for it in ctx['items']['W1']]
            else:
                items = [{'plot_id': it['plot_id'], 'geometry': it['geometry']} for it in ctx['items']['W1']]
            got = end_to_end(pid, dict(base, items=items))
            want = digest([]) if pid == 'NOOP' else _expect(ctx, 'W1', pid)[0]
            if got['answer_sha256'] != want:
                raise BenchmarkError(f'{pid}: end-to-end answers differ from the pinned answers')
            got['peak_rss_bytes'] = got.pop('peak_rss')['bytes']
            run['end_to_end'][pid].append(got)
    log(f'  run {index} end-to-end done')
    for pid in ORDER:
        got = worker(dict(base, mode='memory', path=pid, items=ctx['items']['W1']))
        if got['answer_sha256'] != _expect(ctx, 'W1', pid)[0]:
            raise BenchmarkError(f'{pid}: memory-run answers differ from the pinned answers')
        run['memory'][pid] = got
    run['loadavg_end'] = os.getloadavg()
    run['wall_seconds'] = round(time.perf_counter() - started, 1)
    return run


# ---- parent: summaries, speedups, decomposition --------------------------------------------------

def _stat(per_run):
    """Nearest-rank summary pooled over runs, plus each run's own median and the spread between them."""
    import statistics
    from .benchmark import summarize
    pooled = summarize([x for run in per_run for x in run])
    pooled.pop('samples')
    medians = [statistics.median(run) for run in per_run]
    pooled.update(per_run_median=medians, runs=len(per_run),
                  spread_between_runs=None if len(medians) < 2 else (max(medians) - min(medians)) / pooled['median'])
    return pooled


def _primary(entry):
    return next(iter(entry['hot']))


def summarise(runs, storage):
    import statistics
    paths = {}
    pass_ms = _stat([r['python_pass_ms'] for r in runs])
    noop_ms = _stat([[e['wall_ms'] for e in r['end_to_end']['NOOP']] for r in runs])
    for pid, spec in PATHS.items():
        hot_children = [r['hot'][pid] for r in runs]  # per run: the children (one per hot round)
        first = hot_children[0][0]
        entry = {'name': spec['name'], 'what': spec['what'], 'level': LEVEL_NAME.get(spec['level']),
                 'answers': spec['kind'], 'registered_plots_only': spec['registered'], 'hot': {}}
        for variant in first['variants']:
            entry['hot'][variant] = {}
            for w in first['variants'][variant]:
                n = first['variants'][variant][w]['plots_per_batch']

                def samples(key):
                    return [[x for c in children for x in c['variants'][variant][w][key]] for children in hot_children]
                wall, cpu = _stat(samples('wall_ms')), _stat(samples('cpu_ms'))
                child_medians = [statistics.median(c['variants'][variant][w]['wall_ms'])
                                 for children in hot_children for c in children]
                wall['per_child_median'] = child_medians
                wall['spread_between_children'] = (max(child_medians) - min(child_medians)) / wall['median']
                entry['hot'][variant][w] = {
                    'plots_per_batch': n, 'children': len(child_medians),
                    'batches_per_child': len(first['variants'][variant][w]['wall_ms']),
                    'batch_wall_ms': wall, 'batch_cpu_ms': cpu,
                    'per_plot_wall_us': {'median': wall['median'] / n * 1e3, 'p95': wall['p95'] / n * 1e3},
                    'per_plot_cpu_us': {'median': cpu['median'] / n * 1e3, 'p95': cpu['p95'] / n * 1e3}}
        entry['hot_load_ms'] = _stat([[c['load_ms'] for c in children] for children in hot_children])
        entry['hot_child_peak_rss_bytes'] = _stat([[c['peak_rss_bytes'] for c in children] for children in hot_children])
        cold = [r['cold'][pid] for r in runs]
        entry['process_cold'] = {
            'repetitions_per_run': len(cold[0]),
            **{k: _stat([[c[k] for c in run] for run in cold]) for k in ('wall_ms', 'load_ms', 'query_ms', 'cpu_ms')},
            'peak_rss_bytes': _stat([[c['peak_rss_bytes'] for c in run] for run in cold])}
        e2e = [r['end_to_end'][pid] for r in runs]
        wall = _stat([[c['wall_ms'] for c in run] for run in e2e])
        entry['end_to_end'] = {
            'repetitions_per_run': len(e2e[0]), 'wall_ms': wall,
            'net_of_python_pass_ms_median': wall['median'] - pass_ms['median'],
            'net_of_harness_floor_ms_median': wall['median'] - noop_ms['median'],
            'phase_ms': {k: _stat([[c['phase_ms'][k] for c in run] for run in e2e]) for k in ('imports', 'load', 'query')},
            'peak_rss_bytes': _stat([[c['peak_rss_bytes'] for c in run] for run in e2e])}
        mem = [r['memory'][pid] for r in runs]
        entry['memory'] = {k: mem[0][k] for k in ('held_array_bytes', 'traced_after_load_bytes', 'traced_peak_load_bytes',
                                                  'traced_after_query_bytes', 'traced_peak_query_bytes')}
        entry['memory']['traced_after_load_bytes_per_run'] = [m['traced_after_load_bytes'] for m in mem]
        entry['storage'] = storage[pid]
        paths[pid] = entry
    baselines = {'python_pass_ms': pass_ms, 'harness_floor_ms': noop_ms,
                 'harness_floor_note': 'fresh `python -B -m engine.decision_benchmark --e2e NOOP`: interpreter start-up, '
                                       'this module\'s import, reading the request on stdin, hashing and printing nothing',
                 'noop_peak_rss_bytes': _stat([[c['peak_rss_bytes'] for c in r['end_to_end']['NOOP']] for r in runs])}
    return paths, baselines


def metric_table(paths, baselines):
    metrics = {}
    for pid, e in paths.items():
        v = e['hot'][_primary(e)]
        wall = e['end_to_end']['wall_ms']['median']
        metrics[pid] = {
            'hot_W1_batch_ms': v['W1']['batch_wall_ms']['median'],
            'hot_W3_batch_ms': v['W3']['batch_wall_ms']['median'] if 'W3' in v else None,
            'hot_W4_batch_ms': v['W4']['batch_wall_ms']['median'] if 'W4' in v else None,
            'process_cold_ms': e['process_cold']['wall_ms']['median'],
            'end_to_end_ms': wall,
            'end_to_end_net_of_harness_floor_ms': wall - baselines['harness_floor_ms']['median']}
    return metrics


def ratio(metrics, slow, fast, key):
    a, b = metrics[slow][key], metrics[fast][key]
    return None if a is None or b is None or b <= 0 else a / b


def speedups(metrics):
    """slower / faster for each metric; above 1 means the path is faster than the baseline."""
    out = {}
    for pid in ORDER:
        level_baseline = 'P1d' if PATHS[pid]['level'] == 'decision' else 'P1s' if PATHS[pid]['level'] == 'screen' else None
        out[pid] = {'vs_P0_original_v1': {k: ratio(metrics, 'P0', pid, k) for k in metrics[pid]}}
        if level_baseline:
            out[pid]['vs_P1_original_eudr_same_level'] = {'baseline': level_baseline,
                                                          **{k: ratio(metrics, level_baseline, pid, k) for k in metrics[pid]}}
    return out


DECOMPOSITION = {
    'decision_level': [
        ('representation: derived decision codes instead of original layers, same selection', 'P1d', 'P3'),
        ('selection algorithm: fast_select_cells instead of select_cells', 'P3', 'P4'),
        ('P4 → P4B (one vectorized pass per batch)', 'P4', 'P4B'),
        ('registry index: precomputed cells instead of selection', 'P3', 'P5d'),
        ('P5d → P5Ld (no numpy, packed planes)', 'P5d', 'P5Ld'),
        ('decision table: stored outputs instead of a bincount and reduction', 'P5d', 'P6d'),
        ('total, original layers to table', 'P1d', 'P6d')],
    'screen_level': [
        ('representation: derived screen codes instead of original layers, same selection', 'P1s', 'P2'),
        ('registry index: precomputed cells instead of selection', 'P2', 'P5s'),
        ('P5s → P5Ls (no numpy, packed planes)', 'P5s', 'P5Ls'),
        ('screen table: stored outputs instead of a bincount and reduction', 'P5s', 'P6s'),
        ('total, original layers to table', 'P1s', 'P6s')]}


def decomposition(metrics):
    out = {}
    for level, steps in DECOMPOSITION.items():
        out[level] = [{'step': label, 'from': a, 'to': b,
                       **{f'{k}_speedup': ratio(metrics, a, b, k) for k in metrics[a]}} for label, a, b in steps]
    return out


def stability(paths):
    """How much the medians move between whole-benchmark runs, and between hot children within the pooled data."""
    runs_rows, child_rows = {}, {}
    for pid, e in paths.items():
        v = e['hot'][_primary(e)]
        for w, rec in v.items():
            runs_rows[f'{pid} hot {w}'] = rec['batch_wall_ms']['spread_between_runs']
            child_rows[f'{pid} hot {w}'] = rec['batch_wall_ms']['spread_between_children']
        runs_rows[f'{pid} process-cold'] = e['process_cold']['wall_ms']['spread_between_runs']
        runs_rows[f'{pid} end-to-end'] = e['end_to_end']['wall_ms']['spread_between_runs']

    def digest_rows(rows):
        known = {k: v for k, v in rows.items() if v is not None}
        if not known:
            return {'note': 'only one sample group: no comparison'}
        values = sorted(known.values())
        return {'metrics_compared': len(known), 'median_spread': values[len(values) // 2], 'max_spread': values[-1],
                'worst': sorted(known, key=known.get, reverse=True)[:6],
                'above_10_percent': {k: round(v, 4) for k, v in known.items() if v > .10},
                'by_metric': {k: round(v, 5) for k, v in known.items()}}
    return {'definition': '(largest group median - smallest group median) / pooled median, per metric; groups are '
                          'whole-benchmark runs (all metrics) or individual hot children (hot metrics only)',
            'between_runs': digest_rows(runs_rows), 'between_hot_children': digest_rows(child_rows)}


METHOD = {
    'hot': 'per run, `hot_rounds` (2) fresh children per path, run in opposite path order so no path is always first or last; '
           'in each, imports and the single load happen first, then warmups, then N measured batches per workload. Wall is perf_counter_ns around the whole batch. CPU is the main thread (thread_time_ns, 42 ns '
           'resolution; the process clock is 1 microsecond on macOS, too coarse for table batches). The batch answer digest is '
           'checked outside the timer after every batch. Load time is excluded as in the retained harness.',
    'process_cold': 'retained definition: fresh Python child per repetition, timed full load + one 17-plot batch AFTER imports '
                    'and geometry read. Everything a lazy import would pull in at first call is imported before the timer. '
                    'Repetitions are interleaved across paths and rotated, so machine drift hits every path alike. The OS file '
                    'cache is uncontrolled and warm; this is not disk-cold.',
    'end_to_end': 'parent-measured wall of a fresh `python -B -m engine.decision_benchmark --e2e <path>` that reads the request '
                  '(plot IDs and hashes, or geometries) on stdin, imports only what the path needs, loads, answers the 17 '
                  'registered plots and prints the answer digest. Includes interpreter start-up, imports, the stdin parse and '
                  'process exit. Two floors are measured the same way: `python -B -c pass` and the harness no-op (module '
                  'import + request parse); the net columns subtract them. Engine bytecode caches are pre-built and read.',
    'memory': 'peak RSS is the child lifetime high-water mark (retained rss_record) taken from the process-cold and end-to-end '
              'children; "held" is the loaded arrays\' nbytes; "traced" is Python/numpy allocation after load from tracemalloc '
              '(GDAL C buffers are not seen) in a separate untimed child. The traced peak counts requested allocations, '
              'including calloc pages never touched, so it can exceed the resident peak; RSS is the resident figure.',
    'storage': 'bytes of the files each path opens, read with stat() from the files in this checkout (provenance and JRC '
               'side files included for the original paths); geometry and supplier inputs are common and excluded.',
    'p95': 'nearest rank (engine.benchmark.summarize); hot batches pool all runs, so p95 is the 95th of the pooled batches',
    'pooling': 'the whole benchmark runs `runs` times back to back in this one parent; every child is a fresh process. The '
               'headline median and p95 pool the samples of all runs; per-run medians and the spread between them are reported.',
    'binding': 'before timing, the parent recomputes every path in-process and requires equality: original vs screen store vs '
               'decision store vs fast selection vs the one-call batch evaluator on W1, W3 and W4, and the registry, the numpy-free lite re-check and the table '
               'against the proof outputs on W1. '
               'Every timed child returns an answer digest that must equal the pinned one, or nothing is published. W1 '
               'expected outputs are proof-v1.json\'s; P0 is checked against engine.query.evaluate and the retained '
               'benchmark-v1.json digest.',
    'thread_limits': 'children run with OMP, OpenBLAS, MKL and VECLIB threads set to 1; sequential, never in parallel'}
LIMITATIONS = [
    'P0 answers a bigger question than P1-P6: it returns the 101-bin canopy histogram and the full lossyear histogram. '
    'P1 is the apples-to-apples original-layers baseline for the contract question.',
    'P5L (decision_lite) binds the store level and grid once at load and keeps each plot\'s decoded codes; it does not check the '
    'header\'s decoded-raster hash (the request supplies the pinned store sha256 instead). It reads only split-encoded stores.',
    'The registry and the table exist only for registered plots. A plot that is new or whose geometry changed has no entry '
    'and takes the P3/P4 path.',
    'P4B answers a whole batch in one call, so it needs the batch in hand: a single new plot gains nothing (below '
    'decision_batch.MIN_BATCH = 4 it just runs the P4 loop), and the 17-plot W1 batch is small, so the roughly 100 us '
    'fixed per-call cost of its numpy passes is spread over few plots. Its per-plot figures are batch time / items; the '
    'gain is larger on the 500-plot W3 batch.',
    'Fast selection is exact (fuzz-equal to select_cells) but faster only on ordinary plot shapes; on boundary-heavy '
    'adversarial polygons (W4) it can be slower, because many centres go to exact GEOS.',
    'The OS file cache is warm and uncontrolled: nothing here is disk-cold, object-store or network latency.',
    'One Apple M5 laptop, other processes running, AC power. Medians and p95 are reported with the spread between two runs; '
    'differences under that spread are not findings.',
    'Small AOI: a 1233 x 604 cell chip (744,732 cells) and 17 real plots. Whole-tile or global behaviour is not measured here.',
    'W3 is synthetic: seeded random concave polygons, not company data; its shapes and land placement are assumptions.',
    'The table path takes the layer version (store sha256) from the request. Verifying it by hashing the store file costs the '
    'file read and a sha256 (side_measurements) and is not in the table timings.',
    'End-to-end numbers assume engine bytecode caches exist. Without them each module is compiled at start-up '
    '(side_measurements.uncached_compile_ms), which would hit the larger new modules hardest.',
    'Outputs are mapped observations, never legal compliance findings.']


def headline(paths, baselines):
    rows = []
    for pid, e in paths.items():
        v = e['hot'][_primary(e)]['W1']
        rows.append({
            'path': pid, 'name': e['name'] + (f" ({e['level'].split('.')[0].split('-')[1]})" if e['level'] else ''),
            'hot_17_plots_ms': {'median': v['batch_wall_ms']['median'], 'p95': v['batch_wall_ms']['p95']},
            'hot_per_plot_us': v['per_plot_wall_us']['median'],
            'process_cold_ms': {'median': e['process_cold']['wall_ms']['median'], 'p95': e['process_cold']['wall_ms']['p95']},
            'end_to_end_ms': {'median': e['end_to_end']['wall_ms']['median'], 'p95': e['end_to_end']['wall_ms']['p95']},
            'end_to_end_net_of_python_start_ms': e['end_to_end']['net_of_python_pass_ms_median'],
            'peak_rss_mb_process_cold': e['process_cold']['peak_rss_bytes']['median'] / 1e6,
            'peak_rss_mb_end_to_end': e['end_to_end']['peak_rss_bytes']['median'] / 1e6,
            'bytes_read': e['storage']['bytes'], 'held_array_bytes': e['memory']['held_array_bytes'],
            'python_allocations_after_load_bytes': e['memory']['traced_after_load_bytes']})
    return rows


def render_table(rows):
    lines = ['| Path | Hot 17 plots, ms (median / p95) | Hot per plot, us | Process-cold, ms (median / p95) | End-to-end, ms (median / p95) | RSS cold / e2e, MB | Bytes read | Held arrays, B |',
             '| --- | --- | --- | --- | --- | --- | --- | --- |']
    for r in rows:
        lines.append(f"| {r['path']} {r['name']} | {r['hot_17_plots_ms']['median']:.4f} / {r['hot_17_plots_ms']['p95']:.4f} | "
                     f"{r['hot_per_plot_us']:.2f} | {r['process_cold_ms']['median']:.2f} / {r['process_cold_ms']['p95']:.2f} | "
                     f"{r['end_to_end_ms']['median']:.1f} / {r['end_to_end_ms']['p95']:.1f} | "
                     f"{r['peak_rss_mb_process_cold']:.0f} / {r['peak_rss_mb_end_to_end']:.0f} | {r['bytes_read']:,} | {r['held_array_bytes']:,} |")
    return '\n'.join(lines)


def atomic_write(path, value):
    import re
    import tempfile
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(prefix='.' + path.name + '-', dir=path.parent)
    try:
        with os.fdopen(fd, 'w') as stream:
            text = json.dumps(value, indent=1, allow_nan=False)
            number = r'-?\d+(?:\.\d+)?(?:[eE][+-]?\d+)?'
            text = re.sub(rf'\[\s*({number}(?:,\s*{number})*)\s*\]',
                          lambda m: '[' + re.sub(r',\s*', ', ', m.group(1)) + ']', text)
            stream.write(text + '\n')
        os.chmod(tmp, 0o644)
        os.replace(tmp, path)
    finally:
        Path(tmp).unlink(missing_ok=True)


def round_floats(value, places=6):
    """Rounds to 1 ns in ms units; raw samples keep that resolution."""
    if isinstance(value, float):
        return round(value, places)
    if isinstance(value, dict):
        return {k: round_floats(v, places) for k, v in value.items()}
    if isinstance(value, list):
        return [round_floats(v, places) for v in value]
    return value


def environment_record():
    import subprocess
    from .benchmark import environment
    env = environment()
    for key, command in (('power', ['pmset', '-g', 'batt']), ('power_settings', ['pmset', '-g'])):
        try:
            text = subprocess.run(command, capture_output=True, text=True, timeout=10).stdout
            env[key] = [line.strip() for line in text.splitlines()
                        if 'Power' in line or 'lowpowermode' in line][:3]
        except (OSError, subprocess.SubprocessError):
            env[key] = None
    env['children'] = {'command': 'python -B -m engine.decision_benchmark (--worker | --e2e <path>)',
                       'env': CHILD_ENV, 'executable': sys.executable}
    return env


def replication(metrics, cost_inputs, other, cfg):
    """Compare this invocation's medians with an earlier, independent invocation of the whole benchmark."""
    plan = {w: list(v) for w, v in cfg['plan'].items()}
    if (other['config']['plan'] != plan
            or any(other['config'][k] != cfg[k] for k in ('name', 'hot_rounds', 'w3_polygons', 'w4_polygons', 'seed'))):
        raise BenchmarkError('the replicated result used a different workload or plan')
    rows = {}
    for pid, mine in metrics.items():
        for key, value in mine.items():
            if key.startswith('end_to_end_net'):
                continue  # a difference of two noisy medians, compared through end_to_end_ms instead
            theirs = other['metrics_median'].get(pid, {}).get(key)
            if value is not None and theirs is not None:
                rows[f'{pid} {key}'] = {'this': value, 'other': theirs,
                                        'relative_difference': abs(value - theirs) / ((value + theirs) / 2)}
    diffs = sorted(r['relative_difference'] for r in rows.values())
    return {'definition': '|this - other| / mean of the two pooled medians, per metric',
            'other_invocation': {'runs': other['config']['runs'], 'total_wall_seconds': other['total_wall_seconds'],
                                 'loadavg_start': other['runs'][0]['loadavg_start'],
                                 'metrics_median': other['metrics_median'], 'cost_inputs': other['cost_inputs']},
            'metrics_compared': len(rows), 'median_difference': diffs[len(diffs) // 2], 'max_difference': diffs[-1],
            'above_10_percent': {k: round(r['relative_difference'], 4) for k, r in rows.items()
                                 if r['relative_difference'] > .10},
            'cost_inputs_this': cost_inputs, 'by_metric': rows}


def retained_reference():
    """Medians quoted from the retained artifacts/benchmark-v1.json, for context only (P0 is re-measured here)."""
    winner = json.loads((ROOT / 'artifacts/benchmark-v1.json').read_text())['winner']
    return {'source': 'artifacts/benchmark-v1.json winner block',
            'source_geotiff_hot_batch_ms': winner['source_hot_batch_median_ms'],
            'source_geotiff_process_cold_ms': winner['source_process_cold_batch_median_ms'],
            f"{winner['candidate']}_hot_batch_ms": winner['hot_batch_median_ms'],
            f"{winner['candidate']}_process_cold_ms": winner['process_cold_batch_median_ms'],
            'note': 'different run, different day: use for context. P0 here is the same code path as source_geotiff, '
                    're-measured in this harness alongside every other path'}


def run_cli(argv):
    import argparse
    import tempfile
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--quick', action='store_true', help='fewer polygons and repetitions (smoke test); writes to the temp dir')
    parser.add_argument('--runs', type=int, help='whole-benchmark repetitions (default 2; quick 1)')
    parser.add_argument('--out', type=Path, help='result path (default artifacts/decision/benchmark-v1.json)')
    parser.add_argument('--replicate-of', type=Path, help='an earlier result file from an independent invocation; '
                        'its medians are embedded and compared with this run')
    args = parser.parse_args(argv)
    cfg = quick_config() if args.quick else full_config()
    if args.runs:
        cfg['runs'] = args.runs
    out = args.out or (Path(tempfile.gettempdir()) / 'decision-benchmark-quick.json' if args.quick else RESULT)

    def log(message):
        print(message, file=sys.stderr, flush=True)

    started = time.perf_counter()
    bytecode = warm_bytecode()
    guard = fingerprints()
    log('binding expected answers (in-parent equality on W1, W3, W4) ...')
    ctx = build_context(cfg)
    storage = storage_record()
    side = side_measurements()
    runs = []
    for index in range(1, cfg['runs'] + 1):
        log(f'measurement run {index} of {cfg["runs"]} ...')
        runs.append(measure_run(cfg, ctx, index, log))
        if fingerprints() != guard:
            raise BenchmarkError('implementation or input fingerprint changed during the run; nothing published')
    paths, baselines = summarise(runs, storage)
    metrics = metric_table(paths, baselines)
    rows = headline(paths, baselines)
    p5, p0, p4 = paths['P5d'], paths['P0'], paths['P4']
    cost_inputs = {
        'registry_us': round(p5['hot']['precomputed_hash']['W1']['per_plot_wall_us']['median'], 2),
        'original_us': round(p0['hot']['default']['W1']['per_plot_wall_us']['median'], 2),
        'new_polygon_us': round(p4['hot']['default']['W1']['per_plot_wall_us']['median'], 2),
        'source': 'pooled hot medians, 17 supplied plots (W1): P5d precomputed-hash variant, P0, P4',
        'new_polygon_us_w3_synthetic': round(p4['hot']['default']['W3']['per_plot_wall_us']['median'], 2)}
    result = {
        'schema': SCHEMA, 'config': {k: (v if k != 'plan' else {w: list(p) for w, p in v.items()}) for k, v in cfg.items()},
        'status': 'quick smoke run: not publishable evidence' if args.quick else 'measured',
        'question': 'How much faster, smaller and lighter is answering the EUDR screen/decision question from the decision '
                    'layers than from the original layers, and which lever (representation, selection, registry, table) '
                    'contributes what?',
        'environment': environment_record(), 'bytecode_caches_present': bytecode,
        'identity': guard, 'store_sha256': ctx['store_sha256'],
        'method': METHOD, 'limitations': LIMITATIONS, 'paths': {p: dict(PATHS[p]) for p in PATHS},
        'workloads': ctx['workload_stats'], 'expected_answer_sha256': ctx['expected'],
        'answer_binding': {'checks': ctx['binding'], 'all_equal': True,
                           'timed_children_returned_expected_digests': True},
        'retained_v1_reference': retained_reference(),
        'baselines': baselines, 'side_measurements': side, 'summary': {'paths': paths},
        'headline_table': rows, 'metrics_median': metrics, 'speedups': speedups(metrics),
        'decomposition': decomposition(metrics), 'stability': stability(paths), 'cost_inputs': cost_inputs,
        'runs': runs, 'total_wall_seconds': round(time.perf_counter() - started, 1)}
    if args.replicate_of:
        result['independent_replication'] = replication(metrics, cost_inputs, json.loads(args.replicate_of.read_text()), cfg)
    atomic_write(out, round_floats(result))
    print(render_table(rows))
    brief = {k: {kk: vv for kk, vv in v.items() if kk != 'by_metric'}
             for k, v in result['stability'].items() if isinstance(v, dict)}
    print(json.dumps({'stability': brief,
                      'cost_inputs': cost_inputs, 'written': str(out), 'seconds': result['total_wall_seconds']}, indent=1))
    print('refresh the cost estimate (it reads cost_inputs from the result file) with:\n'
          '  .venv-data/bin/python -B -m engine.decision_scale --cost')


def main(argv=None):
    argv = sys.argv[1:] if argv is None else list(argv)
    if argv[:1] == ['--worker']:
        sys.stdout.write(json.dumps(_worker(json.load(sys.stdin)), allow_nan=False))
    elif argv[:1] == ['--e2e']:
        _e2e(argv[1])
    else:
        run_cli(argv)


if __name__ == '__main__':
    main()
