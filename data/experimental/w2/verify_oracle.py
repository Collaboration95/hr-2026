"""Local W2 verification evidence. Run as a module from the repository root."""
import hashlib
import json
from pathlib import Path
import platform
import sys
from time import perf_counter
import unittest

import numpy as np
import shapely

from engine.oracle import oracle_evaluate
from engine.query import evaluate
from engine.source import load_plots, load_source


ROOT = Path(__file__).resolve().parents[3]
HERE = Path(__file__).resolve().parent
TRACKED = (
    'engine/model.py', 'engine/source.py', 'engine/query.py', 'engine/oracle.py',
    'engine/tests/test_query_oracle.py', 'engine/tests/test_adversarial.py',
    'data/experimental/w2/verify_oracle.py', 'docs/lab/interface-v1.md',
)


def sha256(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    before = {name: sha256(ROOT / name) for name in TRACKED}
    suite = unittest.defaultTestLoader.loadTestsFromNames([
        'engine.tests.test_query_oracle', 'engine.tests.test_adversarial',
    ])
    start = perf_counter()
    outcome = unittest.TextTestRunner(verbosity=1).run(suite)
    test_ms = (perf_counter() - start) * 1000
    source, plots = load_source(), load_plots()
    checks = []
    start = perf_counter()
    for plot in plots:
        expected = oracle_evaluate(source, plot['geometry'])
        actual = evaluate(source, plot['geometry'])
        differences = sorted(name for name in set(expected) | set(actual) if expected.get(name) != actual.get(name))
        checks.append({
            'plot_id': plot['plot_id'], 'differing_fields': differences,
            'selected_cell_count': expected['selected_cell_count'],
            'valid_land_cell_count': expected['valid_land_cell_count'],
            'unknown_cell_count': expected['unknown_cell_count'],
            'support': expected['support'], 'periods': expected['periods'],
        })
    real_comparison_ms = (perf_counter() - start) * 1000
    after = {name: sha256(ROOT / name) for name in TRACKED}
    stable = before == after
    payload = {
        'evidence_version': 'plotline.w2-oracle.v1',
        'environment': {'python': sys.version.split()[0], 'numpy': np.__version__,
                        'shapely': shapely.__version__, 'platform': platform.platform()},
        'implementation_sha256': before,
        'inputs': {'shape_height_width': source.metadata['shape'], 'sources': source.metadata['sources'],
                   'geometry_sha256': sha256(ROOT / 'data/company-sample/2026-10-12/200001-17plots-valid.geojson')},
        'implementation_stable_during_run': stable,
        'tests': {'test_methods': outcome.testsRun, 'failures': len(outcome.failures),
                  'errors': len(outcome.errors), 'skips': len(outcome.skipped),
                  'suite_wall_ms': test_ms, 'randomized_fixtures': 360,
                  'random_seeds': [20261013, 20261014], 'exhaustive_single_cell_fixtures': 144,
                  'invalid_geometry_fixtures': 22},
        'real_plots': {'count': len(checks), 'equal': sum(not p['differing_fields'] for p in checks),
                       'selected_cells_sum_across_plots': sum(p['selected_cell_count'] for p in checks),
                       'combined_oracle_core_wall_ms': real_comparison_ms, 'checks': checks},
        'limitations': ['Oracle and core share GEOS topology validation; membership/reduction are independent.',
                        'This does not verify satellite accuracy or legal compliance.',
                        'Timings are a single correctness-run duration, not a comparative performance benchmark.',
                        'Scalar oracle work limit is 2,000,000 candidate cells and 10,000 vertices.'],
    }
    (HERE / 'verification.json').write_text(json.dumps(payload, indent=2, sort_keys=True, allow_nan=False) + '\n')
    print(json.dumps({'tests': payload['tests'], 'real_equal': payload['real_plots']['equal'],
                      'real_count': len(checks), 'selected_cells_sum': payload['real_plots']['selected_cells_sum_across_plots'],
                      'real_comparison_ms': real_comparison_ms, 'stable': stable}, sort_keys=True))
    return 0 if outcome.wasSuccessful() and stable and all(not p['differing_fields'] for p in checks) else 1


if __name__ == '__main__':
    raise SystemExit(main())
