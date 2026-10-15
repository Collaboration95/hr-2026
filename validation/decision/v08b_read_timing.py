"""Claim 8b addendum: independent timings behind the cost inputs.

1. Single-process whole-tile read of all 160 strips (4 files) vs tile-read-v1.json (2.091 s) used by cost-v1 (the
   first-pass cost model used a contended 8-worker CPU-sum of 7.1 s).
2. Hot per-plot figures on the 17 plots vs benchmark-v1.json cost_inputs: v1 evaluate (original_us 85.36),
   registry_evaluate_store (registry_us 3.55), evaluate_store with fast_select_cells (new_polygon_us 38.94).
Tolerance is generous (timings are machine-dependent): within 0.6x..1.5x of the recorded value. Exit 1 outside it.
"""
import json, sys, time
import numpy as np, rasterio
from rasterio.windows import Window
from _common import ROOT, ART
from engine import decision as D, decision_index as I
from engine.decision_store import read_store
from engine.query import evaluate
from engine.source import load_plots, load_source

H = [rasterio.open(ROOT / f'data/public/raw/Hansen_GFC-2025-v1.13_{b}_10N_090E.tif') for b in ('treecover2000', 'lossyear', 'datamask')]
J = rasterio.open(ROOT / 'data/experimental/jrc/JRC_GFC2020_V4_N10_E90.tif')
passes = []
for _ in range(2):
    t = time.perf_counter(); n = 0
    for r0 in range(0, 40000, 250):
        for h in H:
            n += h.read(1, window=Window(0, r0, 40000, 250)).size
        n += J.read(1, window=Window(0, 3 * r0, 120000, 750)).size
    passes.append(time.perf_counter() - t)
rec = json.loads((ART / 'tile-read-v1.json').read_text())
bench = json.loads((ART / 'benchmark-v1.json').read_text())['cost_inputs']
src = load_source(); plots = load_plots(); geoms = [p['geometry'] for p in plots]
codes, head = read_store(ART / 'decision.plds'); reg = I.load_registry(ART / 'registry.bin')
ents = [reg['plots'][p['plot_id']] for p in plots]


def med(fn, n=100, k=5):
    for _ in range(20):
        fn()
    r = []
    for _ in range(k):
        t = time.perf_counter_ns()
        for _ in range(n):
            fn()
        r.append((time.perf_counter_ns() - t) / n)
    return min(r) / 1e3 / len(plots)


mine = {'original_us': med(lambda: [evaluate(src, g) for g in geoms]),
        'registry_us': med(lambda: [I.registry_evaluate_store(codes, head, e, D.DECISION_VERSION) for e in ents], 300),
        'new_polygon_us': med(lambda: [D.evaluate_store(codes, head, g, D.DECISION_VERSION, I.fast_select_cells) for g in geoms])}
out = {'tile_read_seconds_validator': [round(p, 3) for p in passes], 'tile_read_seconds_recorded': rec['single_process_tile_read_seconds'],
       'first_pass_contended_cpu_sum_seconds': 7.1, 'per_plot_us_validator': {k: round(v, 2) for k, v in mine.items()},
       'per_plot_us_recorded': {k: bench[k] for k in mine}}
ok = all(0.6 <= mine[k] / bench[k] <= 1.5 for k in mine) and all(0.6 <= p / rec['single_process_tile_read_seconds'] <= 1.5 for p in passes)
out['within_tolerance'] = bool(ok)
(__import__('_common').OUT / 'v08b.json').write_text(json.dumps(out, indent=1) + '\n')
print(json.dumps(out, indent=1))
sys.exit(0 if ok else 1)
