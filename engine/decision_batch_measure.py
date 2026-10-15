"""Loop vs batch timing in one process, interleaved: python -B -m engine.decision_batch_measure [--rounds 7].

Each round times the plain loop of evaluate_store(select=fast_select_cells) and evaluate_many back to back, as
the median of several calls; the table reports the best round for each, so a burst of machine load costs
neither side more than the other. Answers are compared once before timing. Writes nothing.
"""
import argparse
import statistics
import time
from pathlib import Path

from . import decision, decision_batch, decision_index as di
from .decision_benchmark import boundary_polygons, synthetic_polygons
from .decision_store import read_store

ROOT = Path(__file__).resolve().parents[1]


def _median_s(fn, reps):
    samples = []
    for _ in range(reps):
        start = time.perf_counter()
        fn()
        samples.append(time.perf_counter() - start)
    return statistics.median(samples)


def measure(codes, header, geometries, reps, rounds):
    def loop():
        return [decision.evaluate_store(codes, header, g, None, select=di.fast_select_cells) for g in geometries]

    def batch():
        return decision_batch.evaluate_many(codes, header, geometries)
    if loop() != batch():
        raise AssertionError('batch answers differ from the loop')
    best_loop = best_batch = float('inf')
    for _ in range(rounds):
        best_loop = min(best_loop, _median_s(loop, reps))
        best_batch = min(best_batch, _median_s(batch, reps))
    n = len(geometries)
    return {'polygons': n, 'loop_us': best_loop / n * 1e6, 'batch_us': best_batch / n * 1e6,
            'loop_per_s': n / best_loop, 'batch_per_s': n / best_batch, 'speedup': best_loop / best_batch}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument('--rounds', type=int, default=7)
    args = parser.parse_args(argv)
    codes, header = read_store(ROOT / 'artifacts/decision/decision.plds')
    codes_s, _ = read_store(ROOT / 'artifacts/decision/screen.plds')
    land = codes_s >= decision.LAND
    seed = 20261015
    workloads = [('W3 500 synthetic', [p['geometry'] for p in synthetic_polygons(500, seed, header, land)[0]], 15),
                 ('5,000 synthetic', [p['geometry'] for p in synthetic_polygons(5000, seed, header, land)[0]], 5),
                 ('W4 100 adversarial', [p['geometry'] for p in boundary_polygons(100, seed, header)[0]], 60)]
    try:
        from .source import load_plots
        workloads.insert(2, ('W1 17 supplied plots', [p['geometry'] for p in load_plots()], 200))
    except Exception as exc:  # the supplied plots are private data and may be absent
        print(f'W1 skipped: {exc}')
    print('| Workload | Polygons | Loop us/polygon | Batch us/polygon | Loop polygons/s | Batch polygons/s | Speedup |')
    print('| --- | ---: | ---: | ---: | ---: | ---: | ---: |')
    for name, geometries, reps in workloads:
        r = measure(codes, header, geometries, reps, args.rounds)
        print(f"| {name} | {r['polygons']:,} | {r['loop_us']:.1f} | {r['batch_us']:.1f} | {r['loop_per_s']:,.0f} | "
              f"{r['batch_per_s']:,.0f} | {r['speedup']:.2f}x |")


if __name__ == '__main__':
    main()
