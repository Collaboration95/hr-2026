#!/usr/bin/env python3
"""Additional matching-level control audit, using development costs only.

All control settings/outcomes were in the original registered measurement set.
This audit is made after challenge; it never changes the frozen selector.
"""
from pathlib import Path
import statistics

import numpy as np

import study


def main():
    frozen = study.filehash(study.HERE / 'policy.json')
    before = study.guard()
    development = study.observations('train') + study.observations('dev')
    holdout = study.observations('holdout')
    candidates = [c['id'] for c in study.CONTROLS if c['level'] == 3]
    choice = min(candidates, key=lambda c: sum(study.outcome(r, c)['total_bytes'] for r in development))
    pack = study.package(holdout, [choice]*len(holdout), 'optimized-geotiff-level3-fixed')
    samples, full_count, window_count = [], 0, 0
    for r in holdout:
        b, m, _ = study.read_patch(r['patch'], study.read(study.HERE / 'dataset-manifest.json'))
        path = study.ROOT / pack['path'] / r['patch']['id']
        db, dm, meta = study.tiff_read(path)
        if not (np.array_equal(db, b) and np.array_equal(dm, m) and meta == r['metadata']):
            raise AssertionError('matching-level retained control differs from original source')
        full_count += 1
        for q in study.QUERIES:
            for repeat in range(3):
                (wb, wm, _), t = study.timed(lambda: study.package_window(study.ROOT / pack['path'], r['patch']['id'], q))
                if not (np.array_equal(wb, b[:, q[0]:q[1], q[2]:q[3]]) and
                        np.array_equal(wm, m[:, q[0]:q[1], q[2]:q[3]])):
                    raise AssertionError('matching-level control window differs')
                samples.append(t)
                window_count += 1
    main_result = study.read(study.HERE / 'results.json')
    selected = main_result['models']['level3']['packages']['selected']['total_bytes']
    outcome = {'completed_utc': study.now(), 'guard': before, 'script_sha256': study.filehash(Path(__file__)),
               'policy_sha256': frozen, 'result_sha256': study.filehash(study.HERE / 'results.json'),
               'fixed_config': choice, 'development_only_choice': True,
               'timing_of_analysis': 'After sealed challenge; all four settings were registered and measured before this additional matching-level comparison. No model change or holdout-based choice.',
               'package': pack, 'selected_level3_minus_control_bytes': selected-pack['total_bytes'],
               'selected_level3_larger_percent': (selected/pack['total_bytes']-1)*100,
               'encode_wall_ms_total': sum(study.outcome(r, choice)['encode']['wall_ms'] for r in holdout),
               'encode_cpu_ms_total': sum(study.outcome(r, choice)['encode']['cpu_ms'] for r in holdout),
               'package_window_wall_ms_median': statistics.median(t['wall_ms'] for t in samples),
               'package_window_cpu_ms_median': statistics.median(t['cpu_ms'] for t in samples),
               'window_samples': samples, 'verification': {'source_reread': True, 'full_roundtrips': full_count,
                                                         'window_roundtrips': window_count, 'passed': True},
               'integrity_scope': 'all file hashes preserved in package; GeoTIFF window timings do not perform engine-style per-stream SHA checks'}
    if frozen != study.filehash(study.HERE / 'policy.json') or before != study.guard():
        raise ValueError('frozen policy/implementation changed')
    study.write(study.HERE / 'matching-level-control.json', outcome)
    print(study.canonical({k: v for k, v in outcome.items() if k in
                          ('fixed_config', 'selected_level3_minus_control_bytes', 'selected_level3_larger_percent',
                           'encode_wall_ms_total', 'package_window_wall_ms_median', 'verification')}).decode())
    print('complete control bytes', pack['total_bytes'])


if __name__ == '__main__':
    main()
