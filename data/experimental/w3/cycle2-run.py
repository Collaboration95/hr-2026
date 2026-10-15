"""Lead-requested bounded full-AOI level/chunk measurements; does not publish."""
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
from engine.benchmark import run_benchmark
from engine.experiments import atomic_write_json

CANDIDATES = ('separate_zstd', 'separate_zstd_l9', 'separate_zstd_l19')
results = []
for chunk in (256, 512):
    result = run_benchmark(candidates=CANDIDATES, chunk_size=chunk, publish=False)
    results.append(result)
    atomic_write_json(ROOT / 'data/experimental/w3/cycle2-results.json', results)
    print(json.dumps({'chunk': chunk, 'registry': result['registry'], 'winner': result['winner']}), flush=True)

# A >0.5% whole-store index cost warrants one additional larger-chunk measurement.
# This is an explicit bounded decision based on measured 512 results, not tuning.
smallest = min((c for c in results[-1]['candidates'] if c['fully_exact']),
               key=lambda c: (c['storage']['total_bytes'], c['candidate']))
index_ratio = smallest['storage']['index_bytes'] / smallest['storage']['total_bytes']
if index_ratio > 0.005:
    print(json.dumps({'adaptive_1024_reason': '512 index exceeds 0.5% of total bytes',
                      'index_ratio': index_ratio}), flush=True)
    result = run_benchmark(candidates=CANDIDATES, chunk_size=1024, publish=False)
    results.append(result)
    atomic_write_json(ROOT / 'data/experimental/w3/cycle2-results.json', results)
    print(json.dumps({'chunk': 1024, 'registry': result['registry'], 'winner': result['winner']}), flush=True)
