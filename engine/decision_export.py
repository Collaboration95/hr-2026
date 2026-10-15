"""Condense retained decision-layer evidence into one app-facing summary.

Reads only artifacts/decision/*.json; never recomputes or edits evidence. Run
`.venv-data/bin/python -B -m engine.decision_export` after the store, proof,
index, benchmark and scale steps.
"""
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DIR = ROOT / 'artifacts/decision'
OUT = DIR / 'summary-v1.json'
SCHEMA = 'plotline.decision-summary.v1'
LEVELS = ('eudr-screen.v1', 'eudr-decision.v1')
PATHS = ('P0', 'P1d', 'P3', 'P4', 'P4B', 'P5d', 'P5Ld', 'P6d')
REGISTERED = ('P5d', 'P5Ld', 'P6d')
LABELS = {'P0': 'Original layers, retained v1 query',
          'P1d': 'Original layers, same EUDR question',
          'P3': 'Decision layer',
          'P4': 'Decision layer + exact fast selection',
          'P4B': 'Decision layer + fast selection, whole batch in one call',
          'P5d': 'Decision layer + registered-plot index',
          'P5Ld': 'Registered-plot index, no numpy, read from the packed layer',
          'P6d': 'Registered-plot answer table'}


def _load(name):
    path = DIR / name
    return json.loads(path.read_text()), hashlib.sha256(path.read_bytes()).hexdigest()


def build_summary():
    stores, stores_sha = _load('stores.json')
    proof, proof_sha = _load('proof-v1.json')
    bench, bench_sha = _load('benchmark-v1.json')
    scale, scale_sha = _load('scale-v1.json')
    layers, layers_sha = _load('layer-analysis-v1.json')
    table, table_sha = _load('table.json')
    if not proof['summary']['all_pass'] or not bench['answer_binding']['all_equal']:
        raise ValueError('refusing to export: proof or benchmark answer binding did not pass')
    rows = {r['path']: r for r in bench['headline_table']}
    p0 = rows['P0']
    speed = [{'path': p, 'label': LABELS[p], 'registered_plots_only': p in REGISTERED,
              'hot_17_plots_ms': rows[p]['hot_17_plots_ms']['median'],
              'hot_per_plot_us': rows[p]['hot_per_plot_us'],
              'process_cold_ms': rows[p]['process_cold_ms']['median'],
              'end_to_end_ms': rows[p]['end_to_end_ms']['median'],
              'peak_rss_mb': rows[p]['peak_rss_mb_process_cold'],
              'bytes_read': rows[p]['bytes_read'],
              'speedup_vs_v1': {k: p0[m]['median'] / rows[p][m]['median']
                                for k, m in (('hot', 'hot_17_plots_ms'), ('process_cold', 'process_cold_ms'),
                                             ('end_to_end', 'end_to_end_ms'))}}
             for p in PATHS]
    storage = {'baselines': {k: v['bytes'] for k, v in stores['baselines'].items()},
               'levels': {level: {'file_bytes': stores['levels'][level]['store']['file_bytes'],
                                  'encoding': stores['levels'][level]['chosen'],
                                  'best_standard_control_bytes': stores['levels'][level]['best_control']['bytes'],
                                  'best_standard_control': stores['levels'][level]['best_control']['name'],
                                  'vs_baselines': stores['levels'][level]['vs_baselines']}
                          for level in LEVELS}}
    tile = scale['sizes_bytes']
    plots = {pid: {'geometry_sha256': entry['geometry_sha256'], 'outputs': entry['outputs']}
             for pid, entry in table['plots'].items()}
    return {
        'schema': SCHEMA,
        'question': 'Keep the decision, not the data: how small and fast can the EUDR screen get '
                    'while every plot answer stays identical to the original layers?',
        'contracts': {
            'eudr-screen.v1': 'Forest at the 31 Dec 2020 cut-off (JRC 2020 at each Hansen centre), '
                              'deforestation since, and the supplier\'s own Hansen post-2020 loss check.',
            'eudr-decision.v1': 'Forest at the cut-off and deforestation since; loss on land that was '
                                'not forest in 2020 is forgotten.'},
        'dropped': ['treecover2000 exact canopy %', 'loss years 2001-2020',
                    'JRC sub-cell detail (8 of 9 cells per Hansen cell)',
                    'decision level only: loss years on JRC 2020 non-forest land'],
        'fidelity': {'cells_compared': proof['summary']['cells_compared'],
                     'cell_mismatches': 0 if proof['summary']['checks']['exhaustive_original_vs_store'] else None,
                     'plots_equal': proof['summary']['plots'],
                     'fuzz_polygons_equal': proof['fuzz']['equal'],
                     'fuzz_polygons_compared': proof['fuzz']['compared'],
                     'v1_hansen_counts_equal': proof['summary']['checks']['v1_crosscheck'],
                     'theorem': proof['theorem']},
        'storage': storage,
        'speed': speed,
        'tile_scale': {'tile': 'Hansen 10N_090E + JRC N10_E90, 1.6 billion Hansen cells',
                       'original_files_bytes': tile['original_geotiff']['total'],
                       'lossless_zstd19_yardstick_bytes': tile['L0_yardstick_hansen3_plus_jrc_native_zstd19'],
                       'screen_bytes': tile['L1_screen_zstd19'], 'decision_bytes': tile['L2_decision_zstd19'],
                       'percent_smaller': {k: v for k, v in scale['ratios'].items() if 'percent' in k}},
        'layer_analysis': [{'plane': a['label'], 'zstd19_bytes': a['zstd19_bytes'],
                            'needed_for': [q['question'] for q in a['needed_for']], 'verdict': a['verdict']}
                           for a in layers['attribution']],
        'jrc_rule_sensitivity': {'plot_decisions_changed': layers['aggregation_sensitivity']['plot_decisions_changed']},
        'plots': plots,
        'limitations': ['Counts are Hansen cells, not hectares; outputs are mapped observations, not legal findings.',
                        'JRC 2020 is read at each Hansen cell centre; sub-cell detail is dropped by design.',
                        'Registered-plot index and table answer only registered plots; new polygons use the decision layer.',
                        'Timings are one laptop with a warm OS file cache; the sample region is small.',
                        'The lossless v1 archive stays available for audits and rule changes.'],
        'evidence': {'stores.json': stores_sha, 'proof-v1.json': proof_sha, 'benchmark-v1.json': bench_sha,
                     'scale-v1.json': scale_sha, 'layer-analysis-v1.json': layers_sha, 'table.json': table_sha},
    }


def main():
    summary = build_summary()
    OUT.write_text(json.dumps(summary, indent=1, sort_keys=True) + '\n')
    print(f'wrote {OUT.relative_to(ROOT)} ({OUT.stat().st_size} B)')


if __name__ == '__main__':
    main()
