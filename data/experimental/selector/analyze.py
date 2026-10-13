#!/usr/bin/env python3
"""Descriptive follow-up only: no holdout fitting or policy replacement."""
import csv
from pathlib import Path
import statistics

import numpy as np

import study


def distribution(samples):
    samples = sorted(samples)
    return {'n': len(samples), 'median_ms': statistics.median(samples),
            'minimum_ms': samples[0], 'p95_ms': samples[int(np.ceil(.95*len(samples)))-1]}


def main():
    results = study.read(study.HERE / 'results.json')
    policy = study.read(study.HERE / 'policy.json')
    proof = study.read(study.HERE / 'verification.json')
    if results['guard'] != study.guard() or proof['result_sha256'] != study.filehash(study.HERE / 'results.json'):
        raise ValueError('verification/result/implementation binding differs')
    rows = {s: study.observations(s) for s in ('train', 'dev', 'holdout')}
    groups = {'water_dominated': lambda v: v <= .01,
              'mixed': lambda v: .01 < v < .99,
              'land_dominated': lambda v: v >= .99}
    strata = {s: {g: sum(fn(r['full_statistics']['land_fraction']) for r in cohort)
                   for g, fn in groups.items()} for s, cohort in rows.items()}
    land_loss_stats = {}
    query_timing = {}
    for family, value in results['models'].items():
        per = {p['patch']: p for p in value['per_patch']}
        land_loss_stats[family] = {}
        for group, fn in groups.items():
            selected = [per[r['patch']['id']] for r in rows['holdout'] if fn(r['full_statistics']['land_fraction'])]
            land_loss_stats[family][group] = {'patches': len(selected),
                'selected_minus_fixed_bytes': sum(p['selected_bytes']-p['fixed_bytes'] for p in selected),
                'regret_bytes': sum(p['regret_bytes'] for p in selected)}
        query_timing[family] = {}
        for name in ('selected', 'fixed'):
            pack = value['packages'][name]
            path = study.ROOT / pack['path']
            samples, cpu, by_patch = [], [], {}
            for r in rows['holdout']:
                pid = r['patch']['id']
                with np.load(study.HERE / 'patches' / f'{pid}.npz') as cache:
                    b, m = cache['bands'], cache['masks']
                one = []
                for q in study.QUERIES:
                    for repeat in range(3):
                        (wb, wm, _), cost = study.timed(lambda: study.package_window(path, pid, q))
                        if not (np.array_equal(wb, b[:, q[0]:q[1], q[2]:q[3]]) and
                                np.array_equal(wm, m[:, q[0]:q[1], q[2]:q[3]])):
                            raise AssertionError('package query differs from preserved source cache')
                        samples.append(cost['wall_ms'])
                        cpu.append(cost['cpu_ms'])
                        one.append(cost['wall_ms'])
                by_patch[pid] = statistics.median(one)
            query_timing[family][name] = {'wall': distribution(samples), 'cpu': distribution(cpu),
                                         'patch_median_wall_ms': by_patch,
                                         'scope': 'global index read/JSON parse + patch lookup + checked 32x32 window decode; 18 patches ×5 windows ×3 repeats; OS cache warm/uncontrolled'}
    # Refit only on original training rows, checking exact frozen tree identity.
    # This estimates training computation after the original untimed freeze;
    # it is neither a new model selection nor heldout training.
    training_samples = {}
    x = np.array([r['features'] for r in rows['train']])
    for family, frozen in policy['models'].items():
        ids = frozen['candidate_ids']
        costs = np.array([[study.outcome(r, c)['total_bytes'] for c in ids] for r in rows['train']])
        timings = []
        for repeat in range(3):
            trees, cost = study.timed(lambda: [study.fit_tree(x, costs, ids, d) for d in (0, 1, 2)])
            expected = [c['model']['tree'] for c in frozen['development_candidates']]
            if trees != expected:
                raise ValueError('training-only refit differs from frozen development trees')
            timings.append(cost)
        training_samples[family] = {'samples': timings, 'frozen_tree_equality': True,
                                    'scope': 'refit depths0/1/2; source reads, outcome generation and dev scoring excluded'}
    development = rows['train'] + rows['dev']
    research = {'development_encode_wall_ms_sum': sum(m['encode']['wall_ms'] for r in development for m in r['measurements']),
                'development_encode_cpu_ms_sum': sum(m['encode']['cpu_ms'] for r in development for m in r['measurements']),
                'development_source_window_wall_ms_sum': sum(r['source_read_ms'] for r in development),
                'development_measurement_count': sum(len(r['measurements']) for r in development),
                'all_measured_store_count': sum(len(r['measurements']) for s in rows for r in rows[s]),
                'all_full_roundtrips_exact': all(m['roundtrip'] for s in rows for r in rows[s] for m in r['measurements']),
                'holdout_first_measurement_utc': min(r['measured_utc'] for r in rows['holdout']),
                'policy_frozen_utc': policy['frozen_utc'],
                'artifact_bytes_current': sum(p.stat().st_size for p in study.HERE.rglob('*') if p.is_file()),
                'scratch_note': 'research candidates/caches/manifests/measurement JSON are excluded from deployment packages, disclosed here; no source tile copy retained'}
    csv_path = study.HERE / 'heldout-per-patch.csv'
    with csv_path.open('w', newline='') as f:
        writer = csv.writer(f)
        writer.writerow(['family', 'patch', 'region', 'land_fraction', 'selected', 'fixed', 'oracle',
                         'selected_bytes', 'fixed_bytes', 'oracle_bytes', 'regret_bytes',
                         'feature_wall_ms', 'selection_wall_ms', 'selected_encode_wall_ms',
                         'fixed_encode_wall_ms'])
        mapping = {r['patch']['id']: r for r in rows['holdout']}
        for family, v in results['models'].items():
            for p in v['per_patch']:
                writer.writerow([family, p['patch'], p['region'], mapping[p['patch']]['full_statistics']['land_fraction'],
                                 p['selected'], p['fixed'], p['oracle'], p['selected_bytes'], p['fixed_bytes'],
                                 p['oracle_bytes'], p['regret_bytes'], p['feature']['wall_ms'],
                                 p['selection']['wall_ms'], p['selected_encode']['wall_ms'], p['fixed_encode']['wall_ms']])
    analysis = {'completed_utc': study.now(), 'result_sha256': study.filehash(study.HERE / 'results.json'),
                'policy_sha256': study.filehash(study.HERE / 'policy.json'), 'guard': study.guard(),
                'script_sha256': study.filehash(Path(__file__)), 'stratum_definition':
                'Descriptive only: land<=1% water-dominated; >=99% land-dominated; otherwise mixed. No resampling or policy changes.',
                'stratum_counts': strata, 'stratum_losses': land_loss_stats,
                'package_window_timings': query_timing, 'training_cost_reproduction': training_samples,
                'research_costs': research, 'per_patch_csv_sha256': study.filehash(csv_path)}
    study.write(study.HERE / 'analysis.json', analysis)
    print(study.canonical({'strata': strata, 'research': research,
                         'package_window_median_ms': {family: {k: v['wall']['median_ms'] for k, v in values.items()}
                                                     for family, values in query_timing.items()}}).decode())


if __name__ == '__main__':
    main()
