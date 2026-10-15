"""Reproduce W2 cycle-2 proof without modifying the lead's witness or core."""
import hashlib
import json
import math
from pathlib import Path
from time import perf_counter
import unittest

import numpy as np

from engine.oracle import oracle_evaluate
from engine.tests.test_adversarial import WINDOW_ORIGIN_WITNESS, window_origin_fixture


ROOT = Path(__file__).resolve().parents[3]
OUTPUT = Path(__file__).with_name('cycle2-verification.json')
WITNESS = ROOT / 'data/experimental/lead/window-origin-witness.json'
TRACKED = ('engine/query.py', 'engine/oracle.py', 'engine/tests/test_adversarial.py',
           'engine/tests/test_query_oracle.py')


def sha256(raw):
    return hashlib.sha256(raw).hexdigest()


def main():
    witness_before = WITNESS.read_bytes()
    recorded = json.loads(witness_before)
    assert all(recorded[key] == value for key, value in WINDOW_ORIGIN_WITNESS.items())
    before = {name: sha256((ROOT / name).read_bytes()) for name in TRACKED}
    suite = unittest.defaultTestLoader.loadTestsFromNames([
        'engine.tests.test_query_oracle', 'engine.tests.test_adversarial',
    ])
    start = perf_counter()
    result = unittest.TextTestRunner(verbosity=1).run(suite)
    elapsed_ms = (perf_counter() - start) * 1000
    full, window = window_origin_fixture()
    geometry = WINDOW_ORIGIN_WITNESS['geometry']
    original_result = oracle_evaluate(full, geometry)
    shifted_result = oracle_evaluate(window, geometry)
    a, _, c, _, _, _ = full.metadata['transform']
    col = WINDOW_ORIGIN_WITNESS['col']
    original_x = c + a * (col + 0.5)
    shifted_x = (c + a * col) + a * 0.5
    after = {name: sha256((ROOT / name).read_bytes()) for name in TRACKED}
    proof = {
        'scope': 'cycle2 original-lattice boundary regression; synthetic event fixture',
        'test_methods': result.testsRun, 'failures': len(result.failures),
        'errors': len(result.errors), 'skips': len(result.skipped), 'suite_wall_ms': elapsed_ms,
        'witness_sha256': sha256(witness_before),
        'witness_unchanged': witness_before == WITNESS.read_bytes(),
        'implementation_sha256': before, 'implementation_stable_during_run': before == after,
        'original_center_x': original_x, 'shifted_center_x': shifted_x,
        'original_center_hex': original_x.hex(), 'shifted_center_hex': shifted_x.hex(),
        'delta_degrees': original_x - shifted_x, 'delta_ulps': (original_x - shifted_x) / math.ulp(original_x),
        'window_raw_bands_identical': bool(np.array_equal(window.bands, full.bands[:, 1:2, 1:2])),
        'window_masks_identical': bool(np.array_equal(window.masks, full.masks[:, 1:2, 1:2])),
        'original_result': original_result, 'shifted_result': shifted_result,
        'limitations': ['No indexed-query API is exercised; lead owns its integration.',
                        'No geometric tolerance, snapping, or center reassociation is accepted.',
                        'This is a query arithmetic witness, not a codec pixel mismatch or speed benchmark.'],
    }
    OUTPUT.write_text(json.dumps(proof, indent=2, sort_keys=True, allow_nan=False) + '\n')
    print(json.dumps({key: proof[key] for key in (
        'test_methods', 'failures', 'errors', 'skips', 'suite_wall_ms', 'witness_unchanged',
        'implementation_stable_during_run', 'delta_degrees', 'delta_ulps',
        'window_raw_bands_identical', 'window_masks_identical',
    )}, sort_keys=True))
    return 0 if result.wasSuccessful() and proof['witness_unchanged'] and before == after else 1


if __name__ == '__main__':
    raise SystemExit(main())
