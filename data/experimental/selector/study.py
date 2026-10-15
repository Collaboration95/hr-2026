#!/usr/bin/env python3
"""Bounded spatial codec-selector study; writes only beside this script.

Run prepare, pilot, develop, freeze, challenge, verify, in that order.
The challenge command cannot fit or change a policy. No supplier labels are read.
"""
from __future__ import annotations

import argparse
from contextlib import ExitStack
from datetime import datetime, timezone
import hashlib
import json
import math
from pathlib import Path
import platform
import random
import shutil
import statistics
import sys
import time

import numpy as np
import rasterio
from rasterio.windows import Window

ROOT = Path(__file__).resolve().parents[3]
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
from engine import codecs  # read-only import; run Python with -B

SEED = 20261013
SIDE = 512
NAMES = ['treecover2000', 'lossyear', 'datamask']
FEATURES = ['canopy_entropy', 'loss_entropy', 'land_fraction',
            'water_fraction', 'loss_fraction', 'canopy_zero_fraction',
            'canopy_change_fraction', 'loss_change_fraction']
QUERIES = [(0, 32, 0, 32), (127, 159, 127, 159),
           (240, 272, 240, 272), (255, 287, 255, 287),
           (480, 512, 480, 512)]
CONFIGS = [{'id': f'{c}__{s}', 'kind': 'engine', 'candidate': c,
            'chunk': s, 'level': codecs.CANDIDATE_LEVELS[c]}
           for c in codecs.CANDIDATES for s in (128, 256, 512)]
CONTROLS = [{'id': f'gtiff_zstd_l{level}_p{p}__{s}', 'kind': 'gtiff',
             'level': level, 'predictor': p, 'chunk': s}
            for level in (3, 19) for p in (1, 2) for s in (256, 512)]


def canonical(x):
    return json.dumps(x, sort_keys=True, separators=(',', ':'),
                      allow_nan=False).encode()


def digest(x):
    return hashlib.sha256(x).hexdigest()


def filehash(path):
    h = hashlib.sha256()
    with path.open('rb') as f:
        for b in iter(lambda: f.read(1024 * 1024), b''):
            h.update(b)
    return h.hexdigest()


def now():
    return datetime.now(timezone.utc).isoformat()


def write(path, x):
    path.parent.mkdir(parents=True, exist_ok=True)
    data = canonical(x)
    tmp = path.with_suffix(path.suffix + '.tmp')
    tmp.write_bytes(data)
    tmp.replace(path)
    return len(data)


def read(path):
    return json.loads(path.read_bytes())


def guard():
    return {str(p.relative_to(ROOT)): filehash(p) for p in
            [Path(__file__), ROOT / 'engine/codecs.py',
             ROOT / 'data/public/provenance.json']}


def verify_sources(manifest):
    for s in manifest['sources']:
        p = ROOT / s['path']
        if p.stat().st_size != s['bytes'] or filehash(p) != s['sha256']:
            raise ValueError(f'changed source: {p}')


def prepare():
    target = HERE / 'dataset-manifest.json'
    if target.exists():
        raise ValueError('manifest already registered; never silently resample')
    provenance = read(ROOT / 'data/public/provenance.json')
    sources = []
    for layer in provenance['layers']:
        p = ROOT / 'data/public/raw' / Path(layer['url']).name
        if filehash(p) != layer['source_tile_sha256']:
            raise ValueError('raw source hash differs from acquisition manifest')
        with rasterio.open(p) as ds:
            if (ds.shape != (40000, 40000) or ds.crs.to_string() != 'EPSG:4326'
                    or list(ds.transform)[:6] != [0.00025, 0, 90, 0, -0.00025, 10]):
                raise ValueError('unexpected native source grid')
        sources.append({'band': layer['band'], 'path': str(p.relative_to(ROOT)),
                        'sha256': filehash(p), 'bytes': p.stat().st_size,
                        'url': layer['url']})
    rb = [(0, 9500), (10500, 19500), (20500, 29500), (30500, 40000)]
    cb = [(27000, 30500), (31500, 35500), (36500, 40000)]
    assignment = [['train', 'holdout', 'train'], ['dev', 'train', 'holdout'],
                  ['train', 'dev', 'train'], ['holdout', 'train', 'dev']]
    patches = []
    # Six bins per macroregion. Pick uniformly among native-grid-aligned
    # non-overlapping origins that fit in each bin. No pixel values are consulted.
    # Exclude the existing supplier bounding chip by geometry alone.
    def overlaps_chip(r, c):
        return r < 6276 and r + SIDE > 5672 and c < 36322 and c + SIDE > 35089
    for ri, (r0, r1) in enumerate(rb):
        for ci, (c0, c1) in enumerate(cb):
            region = f'R{ri}C{ci}'
            rng = random.Random(SEED + ri * 100 + ci)
            for by in range(3):
                for bx in range(2):
                    lo_r = r0 + (r1 - r0) * by // 3
                    hi_r = r0 + (r1 - r0) * (by + 1) // 3
                    lo_c = c0 + (c1 - c0) * bx // 2
                    hi_c = c0 + (c1 - c0) * (bx + 1) // 2
                    origins = [(r, c) for r in range(math.ceil(lo_r / SIDE) * SIDE, hi_r - SIDE + 1, SIDE)
                               for c in range(math.ceil(lo_c / SIDE) * SIDE, hi_c - SIDE + 1, SIDE)
                               if not overlaps_chip(r, c)]
                    r, c = rng.choice(origins)
                    patches.append({'id': f'{region}-B{by}{bx}', 'region': region,
                                    'split': assignment[ri][ci], 'row': r, 'col': c,
                                    'height': SIDE, 'width': SIDE,
                                    'bounds_wgs84': [90 + c * .00025, 10 - (r + SIDE) * .00025,
                                                     90 + (c + SIDE) * .00025, 10 - r * .00025]})
    for i, a in enumerate(patches):
        for b in patches[i + 1:]:
            if (a['row'] < b['row'] + SIDE and b['row'] < a['row'] + SIDE
                    and a['col'] < b['col'] + SIDE and b['col'] < a['col'] + SIDE):
                raise AssertionError('overlapping patches')
    manifest = {'study': 'selector-spatial-v1', 'registered_utc': now(), 'seed': SEED,
                'grid': {'shape': [40000, 40000], 'transform': [.00025, 0, 90, 0, -.00025, 10],
                         'crs': 'EPSG:4326'}, 'patch_side': SIDE,
                'sampling': '12 disjoint eastern-belt macroregions; six geometric bins each; no content screening',
                'region_row_bounds': rb, 'region_col_bounds': cb,
                'split_assignment': assignment, 'sources': sources, 'patches': patches,
                'candidate_configs': CONFIGS, 'optimized_geotiff_controls': CONTROLS,
                'feature_names': FEATURES, 'feature_sample_stride': 16,
                'query_windows': QUERIES,
                'protocol': {'primary': 'level3 codec+chunk; train cost-sensitive trees depth0/1/2; dev selects depth including model bytes',
                             'secondary': 'level19 chunk selection; same protocol',
                             'exploratory': 'all existing levels joint selection; CPU costs descriptive, no assumed exchange rate',
                             'holdout': '18 patches in three sealed regions; read only after policy.json frozen',
                             'geo_control': 'fixed optimized GeoTIFF chosen on train+dev, then applied unchanged to holdout',
                             'oracle': 'per-patch measured best; upper bound only',
                             'bootstrap': 'resample macroregions, 2000 draws; three holdout regions are not a population guarantee'}}
    write(target, manifest)
    print(json.dumps({'manifest_bytes': target.stat().st_size, 'sha256': filehash(target),
                      'patches': len(patches), 'split_counts': {s: sum(p['split'] == s for p in patches)
                                                            for s in ('train', 'dev', 'holdout')}}), flush=True)


def features(b, m):
    v = b[:, ::16, ::16]
    def entropy(a):
        counts = np.bincount(a.reshape(-1), minlength=256)
        q = counts[counts > 0] / a.size
        return float(-(q * np.log2(q)).sum())
    def changes(a):
        return float((np.count_nonzero(a[:, 1:] != a[:, :-1]) +
                      np.count_nonzero(a[1:] != a[:-1])) /
                     (a[:, 1:].size + a[1:].size))
    return [entropy(v[0]), entropy(v[1]), float(np.mean(v[2] == 1)),
            float(np.mean(v[2] == 2)), float(np.mean(v[1] != 0)),
            float(np.mean(v[0] == 0)), changes(v[0]), changes(v[1])]


def timed(fn):
    w, c = time.perf_counter_ns(), time.process_time_ns()
    out = fn()
    return out, {'wall_ms': (time.perf_counter_ns() - w) / 1e6,
                 'cpu_ms': (time.process_time_ns() - c) / 1e6}


def metadata(patch, manifest):
    return {'shape': [SIDE, SIDE], 'transform': [.00025, 0, 90 + patch['col'] * .00025,
                                               0, -.00025, 10 - patch['row'] * .00025],
            'crs': 'EPSG:4326', 'bands': NAMES, 'source_window': [patch['row'], patch['col'], SIDE, SIDE],
            'source_product': 'GFC-2025-v1.13',
            'sources': [{'band': x['band'], 'sha256': x['sha256'], 'url': x['url']}
                        for x in manifest['sources']]}


def read_patch(p, manifest):
    t = time.perf_counter()
    arrays, masks = [], []
    with rasterio.Env(GDAL_CACHEMAX=128 * 1024 * 1024):
        with ExitStack() as stack:
            for source in manifest['sources']:
                ds = stack.enter_context(rasterio.open(ROOT / source['path']))
                win = Window(p['col'], p['row'], SIDE, SIDE)
                arrays.append(ds.read(1, window=win))
                masks.append(ds.read_masks(1, window=win) != 0)
    return np.stack(arrays), np.stack(masks), (time.perf_counter() - t) * 1000


def tiff_encode(b, m, meta, path, config):
    path.mkdir(parents=True, exist_ok=True)
    profile = dict(driver='GTiff', height=SIDE, width=SIDE, count=3, dtype='uint8',
                   crs=meta['crs'], transform=rasterio.Affine(*meta['transform']),
                   tiled=True, blockxsize=config['chunk'], blockysize=config['chunk'],
                   compress='ZSTD', zstd_level=config['level'], predictor=config['predictor'],
                   interleave='band', photometric='MINISBLACK', num_threads=1)
    with rasterio.open(path / 'bands.tif', 'w', **profile) as ds:
        ds.write(b)
        for i, n in enumerate(NAMES, 1):
            ds.set_band_description(i, n)
    # All-valid masks cost zero payload in this control, exactly as source TIFFs.
    # For arbitrary independent invalid masks retain all three mask arrays.
    if not m.all():
        with rasterio.open(path / 'masks.tif', 'w', **{**profile, 'predictor': 1}) as ds:
            ds.write(m.astype(np.uint8))
    write(path / 'metadata.json', meta)


def tiff_read(path, window=None):
    meta = read(path / 'metadata.json')
    win = None if window is None else Window(window[2], window[0], window[3]-window[2], window[1]-window[0])
    with rasterio.open(path / 'bands.tif') as ds:
        b = ds.read(window=win)
        if ds.crs.to_string() != meta['crs'] or list(ds.transform)[:6] != meta['transform']:
            raise ValueError('TIFF grid differs from identical metadata')
    if (path / 'masks.tif').exists():
        with rasterio.open(path / 'masks.tif') as ds:
            m = ds.read(window=win).astype(bool)
    else:
        m = np.ones(b.shape, dtype=bool)
    return b, m, meta


def files(path):
    return [{'path': p.name, 'bytes': p.stat().st_size, 'sha256': filehash(p)}
            for p in sorted(path.iterdir()) if p.is_file()]


def measure_config(b, m, meta, path, config):
    if config['kind'] == 'engine':
        report, encode = timed(lambda: codecs.encode_store(b, m, meta, path, config['candidate'], config['chunk']))
        fn = lambda: codecs.decode_store(path)
        wfn = lambda q: codecs.read_window(path, *q)
    else:
        _, encode = timed(lambda: tiff_encode(b, m, meta, path, config))
        report = {}
        fn = lambda: tiff_read(path)
        wfn = lambda q: tiff_read(path, q)
    (db, dm, dmeta), decode = timed(fn)
    if not (np.array_equal(db, b) and np.array_equal(dm, m) and dmeta == meta):
        raise AssertionError('full bands/masks/metadata mismatch')
    window_samples, touched = [], []
    for q in QUERIES:
        samples = []
        for repeat in range(3):
            (wb, wm, _), timing = timed(lambda: wfn(q))
            if not (np.array_equal(wb, b[:, q[0]:q[1], q[2]:q[3]]) and
                    np.array_equal(wm, m[:, q[0]:q[1], q[2]:q[3]])):
                raise AssertionError('window mismatch')
            samples.append(timing)
        window_samples.append(samples)
        s = config['chunk']
        chunks = ((q[1]-1)//s - q[0]//s + 1) * ((q[3]-1)//s - q[2]//s + 1)
        touched.append({'chunks': chunks, 'spatial_pixels_decoded': chunks*s*s,
                        'amplification_over_32_square': chunks*s*s/1024})
    listing = files(path)
    if config['kind'] == 'engine' and sum(x['bytes'] for x in listing) != report['total_bytes']:
        raise AssertionError('store accounting differs from filesystem')
    return {'config': config['id'], 'total_bytes': sum(x['bytes'] for x in listing),
            'files': listing, 'payload_bytes': report.get('payload_bytes'),
            'metadata_index_bytes': report.get('metadata_index_bytes'),
            'encode': encode, 'full_decode': decode, 'window_samples': window_samples,
            'window_touched': touched, 'roundtrip': True, 'window_exact': True}


def measure(split, limit=None, controls=True):
    manifest = read(HERE / 'dataset-manifest.json')
    verify_sources(manifest)
    before = guard()
    if split == 'holdout':
        policy = read(HERE / 'policy.json')
        if policy['manifest_sha256'] != filehash(HERE / 'dataset-manifest.json') or policy['guard'] != before:
            raise ValueError('frozen policy/code/manifest binding is stale')
    patches = [p for p in manifest['patches'] if p['split'] == split]
    if limit:
        # Round-robin regions for the first pilot, rather than only easy water.
        regions = sorted({p['region'] for p in patches})
        patches = [p for k in range(6) for r in regions
                   for p in patches if p['region'] == r and p['id'].endswith(f'B{k//2}{k%2}')][:limit]
    for n, patch in enumerate(patches, 1):
        target = HERE / 'measurements' / f"{patch['id']}.json"
        if target.exists():
            old = read(target)
            if old['guard'] == before and old['controls_measured'] == controls:
                print(f"cached {patch['id']}", flush=True)
                continue
            raise ValueError('existing measurement has different implementation/settings')
        b, m, source_ms = read_patch(patch, manifest)
        meta = metadata(patch, manifest)
        f, feature_timing = timed(lambda: features(b, m))
        cache = HERE / 'patches' / f"{patch['id']}.npz"
        cache.parent.mkdir(parents=True, exist_ok=True)
        np.savez(cache, bands=b, masks=m)
        observations = []
        # Rotate order deterministically to reduce monotone heating/order bias.
        configs = CONFIGS + (CONTROLS if controls else [])
        shift = int(digest(patch['id'].encode())[:8], 16) % len(configs)
        for config in configs[shift:] + configs[:shift]:
            path = HERE / 'stores' / patch['id'] / config['id']
            observations.append(measure_config(b, m, meta, path, config))
        result = {'patch': patch, 'metadata': meta, 'raw_band_sha256': digest(b.tobytes()),
                  'raw_mask_sha256': digest(m.tobytes()), 'cache_sha256': filehash(cache),
                  'all_masks_valid': bool(m.all()), 'guard': before,
                  'measured_utc': now(), 'source_read_ms': source_ms,
                  'features': f, 'feature_timing': feature_timing,
                  'full_statistics': {'land_fraction': float(np.mean(b[2] == 1)),
                                      'water_fraction': float(np.mean(b[2] == 2)),
                                      'nodata_fraction': float(np.mean(b[2] == 0)),
                                      'loss_fraction': float(np.mean(b[1] != 0))},
                  'controls_measured': controls, 'measurements': observations}
        if guard() != before:
            raise ValueError('implementation changed during measurement; refusing result')
        write(target, result)
        best = min(observations, key=lambda x: x['total_bytes'])
        print(json.dumps({'progress': f'{n}/{len(patches)}', 'patch': patch['id'],
                          'split': split, 'land': round(result['full_statistics']['land_fraction'], 3),
                          'best': best['config'], 'bytes': best['total_bytes']}), flush=True)
    verify_sources(manifest)
    if guard() != before:
        raise ValueError('guard changed')


def observations(split):
    manifest = read(HERE / 'dataset-manifest.json')
    out = []
    for p in manifest['patches']:
        if p['split'] == split:
            path = HERE / 'measurements' / f"{p['id']}.json"
            if not path.exists():
                raise ValueError(f'missing measurement {path}')
            r = read(path)
            if r['guard'] != guard():
                raise ValueError('measurement code guard stale')
            out.append(r)
    return out


def fit_tree(x, costs, ids, depth, minimum=6):
    choice = int(costs.sum(axis=0).argmin())
    leaf = {'config': ids[choice]}
    if depth == 0 or len(x) < minimum*2:
        return leaf
    best = float(costs[:, choice].sum())
    chosen = None
    for f in range(x.shape[1]):
        values = np.unique(x[:, f])
        # At most seven train quantile thresholds per feature, never holdout.
        thresholds = np.unique(np.quantile(values, [.125, .25, .375, .5, .625, .75, .875]))
        for threshold in thresholds:
            left = x[:, f] <= threshold
            if left.sum() < minimum or (~left).sum() < minimum:
                continue
            cost = float(costs[left].sum(axis=0).min() + costs[~left].sum(axis=0).min())
            if cost < best:
                best, chosen = cost, (f, float(threshold), left)
    if chosen is None:
        return leaf
    f, threshold, left = chosen
    return {'feature': FEATURES[f], 'threshold': threshold,
            'le': fit_tree(x[left], costs[left], ids, depth-1, minimum),
            'gt': fit_tree(x[~left], costs[~left], ids, depth-1, minimum)}


def predict(tree, f):
    while 'config' not in tree:
        tree = tree['le'] if f[FEATURES.index(tree['feature'])] <= tree['threshold'] else tree['gt']
    return tree['config']


def outcome(row, config):
    return next(x for x in row['measurements'] if x['config'] == config)


def freeze():
    target = HERE / 'policy.json'
    if target.exists():
        raise ValueError('policy already frozen; holdout cannot tune it')
    if any((HERE / 'measurements' / f"{p['id']}.json").exists()
           for p in read(HERE / 'dataset-manifest.json')['patches'] if p['split'] == 'holdout'):
        raise ValueError('holdout was already opened')
    train, dev = observations('train'), observations('dev')
    families = {'level3': [c['id'] for c in CONFIGS if c['level'] == 3],
                'level19_chunks': [c['id'] for c in CONFIGS if c['level'] == 19],
                'all_levels': [c['id'] for c in CONFIGS]}
    models = {}
    for family, ids in families.items():
        x = np.array([r['features'] for r in train])
        costs = np.array([[outcome(r, c)['total_bytes'] for c in ids] for r in train])
        trees = [fit_tree(x, costs, ids, d) for d in (0, 1, 2)]
        candidates = []
        for d, tree in enumerate(trees):
            model = {'format': 'selector.cost-tree.v1', 'sample_stride': 16,
                     'feature_names': FEATURES, 'tree': tree}
            predictions = [predict(tree, r['features']) for r in dev]
            payload_cost = sum(outcome(r, c)['total_bytes'] for r, c in zip(dev, predictions))
            # Count the entire serialized inference model, even for depth zero.
            candidates.append({'depth': d, 'model': model, 'model_bytes': len(canonical(model)),
                               'dev_store_bytes': payload_cost,
                               'dev_total_with_model': payload_cost+len(canonical(model)),
                               'dev_predictions': dict(zip([r['patch']['id'] for r in dev], predictions))})
        chosen = min(candidates, key=lambda c: (c['dev_total_with_model'], c['depth']))
        # Strong fixed baseline chosen on ALL development data; never on holdout.
        fixed = min(ids, key=lambda c: sum(outcome(r, c)['total_bytes'] for r in train+dev))
        models[family] = {'chosen': chosen, 'development_candidates': candidates,
                          'fixed_best_development': fixed, 'candidate_ids': ids}
    geo = min([c['id'] for c in CONTROLS],
              key=lambda c: sum(outcome(r, c)['total_bytes'] for r in train+dev))
    policy = {'format': 'selector.freeze.v1', 'frozen_utc': now(), 'guard': guard(),
              'manifest_sha256': filehash(HERE / 'dataset-manifest.json'),
              'development_measurement_sha256': {r['patch']['id']: filehash(HERE / 'measurements' / f"{r['patch']['id']}.json")
                                                 for r in train+dev},
              'models': models, 'fixed_geo_control': geo,
              'note': 'No holdout pixels/features/outcomes were opened before this freeze.'}
    write(target, policy)
    print(json.dumps({'policy_sha256': filehash(target), 'models': {
        f: {'depth': v['chosen']['depth'], 'tree': v['chosen']['model']['tree'],
            'fixed': v['fixed_best_development']} for f, v in models.items()},
                      'geo': geo}), flush=True)


def package(rows, choices, name, model=None):
    """Materialize the actual data-only queryable package, including global index."""
    path = HERE / 'heldout-packages' / name
    path.mkdir(parents=True, exist_ok=True)
    entries = []
    for row, config in zip(rows, choices):
        p = row['patch']
        dest = path / p['id']
        dest.mkdir(exist_ok=True)
        measured = outcome(row, config)
        for f in measured['files']:
            src = HERE / 'stores' / p['id'] / config / f['path']
            if filehash(src) != f['sha256']:
                raise ValueError('measured store changed')
            shutil.copyfile(src, dest / f['path'])
        entries.append({'id': p['id'], 'region': p['region'], 'row': p['row'], 'col': p['col'],
                        'height': SIDE, 'width': SIDE, 'config': config,
                        'directory': p['id'], 'files': measured['files']})
    schema = {'format': 'selector.patch-store.v1', 'entries': entries,
              'native_grid': read(HERE / 'dataset-manifest.json')['grid'],
              'coverage': 'only listed disjoint patches; gaps unavailable',
              'reader': 'study.py package-window; native row/col coordinates',
              'model_file': 'model.json' if model else None,
              'mask_contract': 'all three independent bool validity masks preserved; implicit true only if all valid'}
    write(path / 'store.json', schema)
    if model:
        write(path / 'model.json', model)
    # Common original acquisition evidence retained symmetrically.
    shutil.copyfile(ROOT / 'data/public/provenance.json', path / 'provenance.json')
    listing = [{'path': str(p.relative_to(path)), 'bytes': p.stat().st_size, 'sha256': filehash(p)}
               for p in sorted(path.rglob('*')) if p.is_file()]
    return {'path': str(path.relative_to(ROOT)), 'total_bytes': sum(f['bytes'] for f in listing),
            'per_patch_store_bytes': sum(outcome(r, c)['total_bytes'] for r, c in zip(rows, choices)),
            'model_bytes': (path / 'model.json').stat().st_size if model else 0,
            'global_index_schema_bytes': (path / 'store.json').stat().st_size,
            'common_provenance_bytes': (path / 'provenance.json').stat().st_size,
            'dictionary_bytes': 0, 'files': listing}


def bootstrap(rows, deltas):
    groups = sorted({r['patch']['region'] for r in rows})
    totals = [sum(d for r, d in zip(rows, deltas) if r['patch']['region'] == g) for g in groups]
    rng = random.Random(SEED + 19)
    values = sorted(sum(rng.choice(totals) for _ in groups) for _ in range(2000))
    return {'region_deltas': dict(zip(groups, totals)), 'cluster_count': len(groups),
            'resampled_delta_95_interval_bytes': [values[49], values[1949]],
            'note': 'Three spatial clusters: descriptive resampling interval, not robust population inference. Model/global overhead excluded here.'}


def evaluate():
    rows = observations('holdout')
    policy = read(HERE / 'policy.json')
    models = {}
    for family, v in policy['models'].items():
        tree = v['chosen']['model']['tree']
        choices, selector_samples = [], []
        for r in rows:
            choice, cost = timed(lambda: predict(tree, r['features']))
            choices.append(choice)
            selector_samples.append(cost)
        baseline = v['fixed_best_development']
        fixed_choices = [baseline] * len(rows)
        oracle = [min(v['candidate_ids'], key=lambda c: outcome(r, c)['total_bytes']) for r in rows]
        # Test-best fixed is an audit/upper-bound comparator, never a tuned deploy policy.
        test_fixed = min(v['candidate_ids'], key=lambda c: sum(outcome(r, c)['total_bytes'] for r in rows))
        packs = {'selected': package(rows, choices, family + '-selected', v['chosen']['model']),
                 'fixed': package(rows, fixed_choices, family + '-fixed'),
                 'oracle': package(rows, oracle, family + '-oracle')}
        base_cost = packs['fixed']['per_patch_store_bytes']
        chosen_cost = packs['selected']['per_patch_store_bytes']
        oracle_cost = packs['oracle']['per_patch_store_bytes']
        per_patch = []
        for r, c, oc, sc in zip(rows, choices, oracle, selector_samples):
            a, b, o = outcome(r, c), outcome(r, baseline), outcome(r, oc)
            per_patch.append({'patch': r['patch']['id'], 'region': r['patch']['region'],
                              'selected': c, 'fixed': baseline, 'oracle': oc,
                              'selected_bytes': a['total_bytes'], 'fixed_bytes': b['total_bytes'],
                              'oracle_bytes': o['total_bytes'], 'regret_bytes': a['total_bytes']-o['total_bytes'],
                              'feature': r['feature_timing'], 'selection': sc,
                              'selected_encode': a['encode'], 'fixed_encode': b['encode'],
                              'selected_full_decode': a['full_decode'], 'fixed_full_decode': b['full_decode'],
                              'selected_window_median_ms': statistics.median(s['wall_ms'] for q in a['window_samples'] for s in q),
                              'fixed_window_median_ms': statistics.median(s['wall_ms'] for q in b['window_samples'] for s in q),
                              'selected_query_amplifications': a['window_touched'],
                              'fixed_query_amplifications': b['window_touched']})
        models[family] = {'chosen_depth': v['chosen']['depth'], 'tree': tree,
                          'fixed_best_development': baseline,
                          'heldout_best_fixed_posthoc': test_fixed,
                          'heldout_best_fixed_posthoc_bytes': sum(outcome(r, test_fixed)['total_bytes'] for r in rows),
                          'packages': packs, 'store_only_delta_bytes': chosen_cost-base_cost,
                          'store_only_delta_percent': (chosen_cost/base_cost-1)*100,
                          'complete_package_delta_bytes': packs['selected']['total_bytes']-packs['fixed']['total_bytes'],
                          'complete_package_delta_percent': (packs['selected']['total_bytes']/packs['fixed']['total_bytes']-1)*100,
                          'selector_regret_bytes': chosen_cost-oracle_cost,
                          'fixed_regret_bytes': base_cost-oracle_cost,
                          'wins_ties_losses': [sum(a['selected_bytes'] < a['fixed_bytes'] for a in per_patch),
                                               sum(a['selected_bytes'] == a['fixed_bytes'] for a in per_patch),
                                               sum(a['selected_bytes'] > a['fixed_bytes'] for a in per_patch)],
                          'cluster_uncertainty': bootstrap(rows, [p['selected_bytes']-p['fixed_bytes'] for p in per_patch]),
                          'feature_wall_ms_total': sum(r['feature_timing']['wall_ms'] for r in rows),
                          'selection_wall_ms_total': sum(s['wall_ms'] for s in selector_samples),
                          'selected_encode_wall_ms_total': sum(p['selected_encode']['wall_ms'] for p in per_patch),
                          'fixed_encode_wall_ms_total': sum(p['fixed_encode']['wall_ms'] for p in per_patch),
                          'per_patch': per_patch}
    geo_choice = policy['fixed_geo_control']
    geo_pack = package(rows, [geo_choice]*len(rows), 'optimized-geotiff-fixed')
    output = {'study': 'selector-spatial-v1', 'completed_utc': now(), 'guard': guard(),
              'manifest_sha256': filehash(HERE / 'dataset-manifest.json'),
              'policy_sha256': filehash(HERE / 'policy.json'),
              'environment': {'python': sys.version, 'platform': platform.platform(), 'numpy': np.__version__,
                              'rasterio': rasterio.__version__, 'gdal': rasterio.__gdal_version__,
                              'libzstd': list(codecs.zstd.zstd_version_info)},
              'cohort': {'train': 36, 'dev': 18, 'holdout': 18, 'holdout_regions': 3,
                         'total_spatial_cells': len(rows)*SIDE*SIDE,
                         'source_tiles_only': True, 'supplier_labels': 0,
                         'all_masks_valid': all(r['all_masks_valid'] for r in rows)},
              'models': models, 'optimized_geotiff': {'config': geo_choice, 'package': geo_pack,
                    'per_patch': [{'patch': r['patch']['id'], 'measurement': outcome(r, geo_choice)} for r in rows]},
              'runtime_code_bytes_separate': Path(__file__).stat().st_size,
              'measurement_scope': {'encode': 'one wall/CPU sample; arrays preloaded; validation, checksums, buffered writes; no fsync',
                                    'decode': 'one full decode; three window repetitions each of five 32x32 windows; handles recreated; OS cache uncontrolled',
                                    'source_read': 'bounded windows; source strips decompress wider than requested; excluded from codec encode',
                                    'selector_cost': 'feature extraction and tree walk at ingestion, no selector invocation required at query time',
                                    'query': 'raster window reads, not polygon semantics or supplier compliance',
                                    'geotiff_integrity': 'TIFF control lacks engine per-stream SHA verification; file hashes verified outside timings'},
              'limitations': ['one Hansen tile, geographically restricted eastern belt, tiny sample and spatial autocorrelation',
                              'complete sparse-patch package is queryable only within retained patches; not a seamless production AOI',
                              'engine runtime and dependencies excluded symmetrically; script bytes disclosed separately',
                              'oracle knows measured compression outcomes, cannot be called deployment performance',
                              'no legal/source accuracy inference or 17-plot generalization claim']}
    write(HERE / 'results.json', output)
    print(json.dumps({'results': str(HERE / 'results.json'), 'summaries': {f: {
        k: v[k] for k in ('chosen_depth', 'store_only_delta_bytes', 'complete_package_delta_bytes',
                         'selector_regret_bytes', 'wins_ties_losses')} for f, v in models.items()},
                      'geo_complete_bytes': geo_pack['total_bytes']}), flush=True)


def package_window(path, patch_id, q):
    index = read(path / 'store.json')
    entry = next(e for e in index['entries'] if e['id'] == patch_id)
    if entry['config'].startswith('gtiff_'):
        return tiff_read(path / entry['directory'], q)
    return codecs.read_window(path / entry['directory'], *q)


def verify():
    manifest = read(HERE / 'dataset-manifest.json')
    verify_sources(manifest)
    result = read(HERE / 'results.json')
    policy = read(HERE / 'policy.json')
    if result['guard'] != guard() or result['policy_sha256'] != filehash(HERE / 'policy.json'):
        raise ValueError('changed result/code/policy binding')
    for pid, h in policy['development_measurement_sha256'].items():
        if filehash(HERE / 'measurements' / f'{pid}.json') != h:
            raise ValueError('development evidence changed since freeze')
    packs = [p for v in result['models'].values() for p in v['packages'].values()]
    packs.append(result['optimized_geotiff']['package'])
    full_count = query_count = 0
    for pack in packs:
        path = ROOT / pack['path']
        if sum(f['bytes'] for f in pack['files']) != pack['total_bytes']:
            raise ValueError('package accounting mismatch')
        for f in pack['files']:
            p = path / f['path']
            if p.stat().st_size != f['bytes'] or filehash(p) != f['sha256']:
                raise ValueError('package file changed')
        index = read(path / 'store.json')
        for e in index['entries']:
            patch = next(p for p in manifest['patches'] if p['id'] == e['id'])
            b, m, _ = read_patch(patch, manifest)  # independently reread raw source
            meta = metadata(patch, manifest)
            if e['config'].startswith('gtiff_'):
                db, dm, dmta = tiff_read(path / e['directory'])
            else:
                db, dm, dmta = codecs.decode_store(path / e['directory'])
            if not (np.array_equal(db, b) and np.array_equal(dm, m) and dmta == meta):
                raise AssertionError('retained full prediction roundtrip failed')
            full_count += 1
            for q in QUERIES:
                wb, wm, _ = package_window(path, e['id'], q)
                if not (np.array_equal(wb, b[:, q[0]:q[1], q[2]:q[3]]) and
                        np.array_equal(wm, m[:, q[0]:q[1], q[2]:q[3]])):
                    raise AssertionError('retained indexed window failed')
                query_count += 1
    proof = {'verified_utc': now(), 'full_store_roundtrips': full_count,
             'window_roundtrips': query_count, 'result_sha256': filehash(HERE / 'results.json'),
             'policy_sha256': filehash(HERE / 'policy.json'), 'guard': guard(),
             'source_reread': True, 'passed': True}
    write(HERE / 'verification.json', proof)
    print(json.dumps(proof), flush=True)


def pilot_summary():
    rows = [read(p) for p in sorted((HERE / 'measurements').glob('*.json'))]
    data = {'reported_utc': now(), 'patches': len(rows), 'regions': len({r['patch']['region'] for r in rows}),
            'heldout_opened': any(r['patch']['split'] == 'holdout' for r in rows),
            'land_range': [min(r['full_statistics']['land_fraction'] for r in rows),
                           max(r['full_statistics']['land_fraction'] for r in rows)],
            'totals_by_config': {c['id']: sum(outcome(r, c['id'])['total_bytes'] for r in rows)
                                for c in CONFIGS+CONTROLS},
            'all_exact': all(m['roundtrip'] and m['window_exact'] for r in rows for m in r['measurements'])}
    write(HERE / 'pilot-results.json', data)
    # Early useful evidence in the assigned handoff file, before all study work.
    report = ROOT / 'docs/lab/engine-selector-report.md'
    best = min(data['totals_by_config'], key=data['totals_by_config'].get)
    report.write_text('# Source-only spatial codec selector — pilot checkpoint\n\n'
                      f"Measured {data['reported_utc']}: {len(rows)} training patches from {data['regions']} regions; "
                      f"native 512×512 windows. Land fraction range {data['land_range']}. "
                      f"All {len(rows)*26} candidate/control full roundtrips and sampled window reads exact.\n\n"
                      f"Smallest fixed pilot control: `{best}`, {data['totals_by_config'][best]:,} complete patch-store bytes. "
                      'These pilot bytes exclude global dataset index and policy overhead; no deployment win claimed.\n\n'
                      'Final holdout remains unopened. Read-only source hashes, seeded region selection, candidate settings, '
                      'raw hashes, timings and exactness evidence are under `data/experimental/selector/`. '
                      'Next: all development measurements, frozen interpretable policy, then single spatial holdout challenge.\n')
    print(json.dumps(data), flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', choices=['prepare', 'pilot', 'develop', 'freeze', 'challenge', 'verify', 'package-window'])
    parser.add_argument('--package')
    parser.add_argument('--patch')
    parser.add_argument('--window', nargs=4, type=int)
    args = parser.parse_args()
    if args.command == 'prepare':
        prepare()
    elif args.command == 'pilot':
        measure('train', limit=12)
        pilot_summary()
    elif args.command == 'develop':
        measure('train')
        measure('dev')
    elif args.command == 'freeze':
        freeze()
    elif args.command == 'challenge':
        frozen = filehash(HERE / 'policy.json')
        measure('holdout')
        evaluate()
        if filehash(HERE / 'policy.json') != frozen:
            raise ValueError('policy changed during challenge')
    elif args.command == 'verify':
        verify()
    elif args.command == 'package-window':
        if not (args.package and args.patch and args.window):
            parser.error('package-window requires --package, --patch, --window')
        b, m, meta = package_window(HERE / 'heldout-packages' / args.package, args.patch, tuple(args.window))
        print(json.dumps({'shape': list(b.shape), 'bands_sha256': digest(b.tobytes()),
                          'masks_sha256': digest(m.tobytes()), 'metadata': meta}))


if __name__ == '__main__':
    main()
