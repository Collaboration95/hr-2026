"""Claim 8: spot-check scale-v1.json strips independently, check internal consistency, recompute cost-v1.json.

Strip codes are rebuilt here from rasterio window reads with this validator's own derivation (exact integer
mapping verified with rational arithmetic on the tile transforms), then compressed with zstd level 19.
Two strips by default: one containing the AOI chip, one in the middle of the tile. ~20 s, one process.
"""
from fractions import Fraction
import json
import math
import sys
import time

import numpy as np
import rasterio
from rasterio.windows import Window
from compression import zstd

from _common import ART, OUT, ROOT
from engine.decision_store import MAX_CELLS as S_MAX_CELLS, MAX_DIMENSION as S_MAX_DIM

HANSEN = ['treecover2000', 'lossyear', 'datamask']
scale = json.loads((ART / 'scale-v1.json').read_text())
cost = json.loads((ART / 'cost-v1.json').read_text())
res, bad = {}, []

# ---- internal consistency of scale-v1.json -----------------------------------------------------------------
rows = scale['strips_table']['rows']
cols = scale['strips_table']['columns']
col = {n: i for i, n in enumerate(cols)}
sums = {n: sum(r[col[n]] for r in rows) for n in cols if n not in ('hansen_row_start', 'rows')}
sz = scale['sizes_bytes']
res['sums_vs_headline'] = {
    'L1': (sums['L1_zstd19'], sz['L1_screen_zstd19']), 'L2': (sums['L2_zstd19'], sz['L2_decision_zstd19']),
    'hansen3_zstd19': (sums['treecover_zstd19'] + sums['lossyear_zstd19'] + sums['datamask_zstd19'], sz['L0_yardstick_hansen3_zstd19']),
    'land_cells': (sums['land_cells'], scale['histograms']['land_cells'])}
for k, (a, b) in res['sums_vs_headline'].items():
    if a != b:
        bad.append(f'strips table sum != headline for {k}: {a} vs {b}')
files = scale['tile']['grid']['files']
orig = sum(v['bytes'] for v in files.values())
res['original_total_bytes'] = (orig, sz['original_geotiff']['total'])
res['percents_recomputed'] = {
    'L1_vs_original': round(100 * (1 - sz['L1_screen_zstd19'] / orig), 2), 'L2_vs_original': round(100 * (1 - sz['L2_decision_zstd19'] / orig), 2),
    'L1_vs_yardstick': round(100 * (1 - sz['L1_screen_zstd19'] / sz['L0_yardstick_hansen3_plus_jrc_native_zstd19']), 2),
    'L2_vs_yardstick': round(100 * (1 - sz['L2_decision_zstd19'] / sz['L0_yardstick_hansen3_plus_jrc_native_zstd19']), 2),
    'recorded': {k: scale['ratios'][k] for k in scale['ratios'] if 'percent' in k}}

# ---- independent strips ------------------------------------------------------------------------------------
hp = [ROOT / f'data/public/raw/Hansen_GFC-2025-v1.13_{b}_10N_090E.tif' for b in HANSEN]
jp = ROOT / 'data/experimental/jrc/JRC_GFC2020_V4_N10_E90.tif'
H = [rasterio.open(p) for p in hp]
J = rasterio.open(jp)
ha, _, hc, _, he, hf = H[0].transform[:6]
ja, _, jc, _, je, jf = J.transform[:6]
# exact nesting: Hansen centre index -> JRC index with rational arithmetic, spot-checked on 200 rows and columns + extremes
rng = np.random.default_rng(1)
ks = list(rng.integers(0, 40000, 200)) + [0, 1, 39999]
bad_map = 0
for k in ks:
    k = int(k)
    xr = (Fraction(hc) + (k + Fraction(1, 2)) * Fraction(ha) - Fraction(jc)) / Fraction(ja)
    yr = (Fraction(hf) + (k + Fraction(1, 2)) * Fraction(he) - Fraction(jf)) / Fraction(je)
    bad_map += (math.floor(xr) != 3 * k + 1) or (math.floor(yr) != 3 * k + 1)
res['tile_nesting_rational_check'] = {'indices_checked': len(ks), 'violations_of_3k+1': bad_map,
                                      'max_centre_deviation_cells': float(max(abs((Fraction(hc) + (k + Fraction(1, 2)) * Fraction(ha) - Fraction(jc)) / Fraction(ja) - (3 * k + Fraction(3, 2))) for k in ks))}
if bad_map:
    bad.append('tile nesting offsets differ from 3k+1')


def strip(r0, n=250):
    t0 = time.perf_counter()
    hb = np.stack([h.read(1, window=Window(0, r0, 40000, n)) for h in H])
    jv = J.read(1, window=Window(0, 3 * r0, 120000, 3 * n))
    read_s = time.perf_counter() - t0
    L, D, T = hb[1], hb[2], hb[0]
    forest = jv[1::3, 1::3]  # middle cell of each 3x3 block (rows 3r+1, cols 3c+1)
    assert forest.shape == (n, 40000) and forest.max() <= 1
    post = np.where(L > 20, L.astype(np.int16) - 20, 0)
    scr = np.zeros((n, 40000), np.uint8)
    scr[D == 2] = 1
    land = D == 1
    scr[land] = (2 + 6 * forest.astype(np.int16) + post)[land]
    dec = scr.copy()
    dec[(scr > 2) & (scr < 8)] = 2
    comp = lambda a: len(zstd.compress(np.ascontiguousarray(a).reshape(-1), level=19))
    out = {'r0': r0, 'rows': n, 'read_seconds': round(read_s, 2), 'L1_zstd19': comp(scr), 'L2_zstd19': comp(dec),
           'treecover_zstd19': comp(T), 'lossyear_zstd19': comp(L), 'datamask_zstd19': comp(D), 'jrc_native_zstd19': comp(jv),
           'land_cells': int(land.sum()), 'max_lossyear': int(L.max()), 'jrc_values': sorted(int(v) for v in np.unique(jv)),
           'datamask_values': sorted(int(v) for v in np.unique(D))}
    return out


starts = [int(a) for a in sys.argv[1:]] or [5500, 20000]
for r0 in starts:
    mine = strip(r0)
    rec = next(r for r in rows if r[0] == r0)
    theirs = {n: rec[col[n]] for n in cols}
    cmp = {n: (mine[n], theirs[n]) for n in ('L1_zstd19', 'L2_zstd19', 'treecover_zstd19', 'lossyear_zstd19', 'datamask_zstd19', 'jrc_native_zstd19', 'land_cells')}
    res[f'strip_{r0}'] = {'independent_vs_recorded': cmp, 'all_equal': all(a == b for a, b in cmp.values()),
                          'read_seconds_single_strip_single_process': mine['read_seconds'], 'jrc_values': mine['jrc_values'],
                          'datamask_values': mine['datamask_values'], 'max_lossyear': mine['max_lossyear']}
    if not res[f'strip_{r0}']['all_equal']:
        bad.append(f'strip {r0} differs: {cmp}')

# ---- cost-v1 recomputation ----------------------------------------------------------------------------------
GB = 2 ** 30
reps = cost['representations']
chk = {}
for name, rep in reps.items():
    b = rep['bytes_per_tile_measured']
    storage = round(b * 100 * 1 / GB * 0.023, 4)
    rec = rep['storage_by_basis']['measured_tile']['tropical_belt']['versions_1']['usd_per_month']
    chk[name] = {'belt_1_version_usd_recomputed': storage, 'recorded': rec, 'equal': abs(storage - rec) < 1e-4}
res['cost_storage_recomputed'] = chk
bench = json.loads((ART / 'benchmark-v1.json').read_text())
tile_read = json.loads((ART / 'tile-read-v1.json').read_text())
ci = bench['cost_inputs']
pp = cost['assumptions']['per_plot_microseconds']
res['cost_inputs_from_benchmark'] = {
    'benchmark_cost_inputs': {k: ci[k] for k in ('original_us', 'registry_us', 'new_polygon_us')},
    'cost_v1_per_plot_us': {'original_v1': pp['original_v1'], 'decision_registry': pp['decision_registry'], 'decision_new_polygon': pp['decision_new_polygon']},
    'equal': (ci['original_us'], ci['registry_us'], ci['new_polygon_us']) == (pp['original_v1'], pp['decision_registry'], pp['decision_new_polygon']),
    'registry_placeholder_flag_present': any('PLACEHOLDER' in json.dumps(v) for v in pp.values())}
if not res['cost_inputs_from_benchmark']['equal'] or res['cost_inputs_from_benchmark']['registry_placeholder_flag_present']:
    bad.append('cost-v1 per-plot inputs differ from benchmark-v1 cost_inputs, or a placeholder remains')
import statistics
passes = tile_read['pass_seconds']
dec_vals = cost['assumptions']['tile_decode_seconds']['values']
res['tile_read'] = {'pass_seconds': passes, 'median_recomputed': statistics.median(passes), 'recorded_single_process': tile_read['single_process_tile_read_seconds'],
                    'cost_v1_original_tile_decode': dec_vals['original_layers_geotiff'], 'cells_read': tile_read['cells_read'],
                    'equal': statistics.median(passes) == tile_read['single_process_tile_read_seconds'] == dec_vals['original_layers_geotiff']}
if not res['tile_read']['equal']:
    bad.append('tile-read median differs from cost-v1 original decode')
rc = cost['recheck_10m_plots']['original_layers_geotiff']['measured_tile']['tropical_belt']
per_plot = 10_000_000 * ci['original_us'] / 1e6
prices = cost['assumptions']['prices']
lam = (per_plot + 100 * dec_vals['original_layers_geotiff']) * 1.0 * prices['lambda_compute']['value'] + 100 * prices['lambda_requests']['value'] / 1e6
gets = 100 * -(-cost['representations']['original_layers_geotiff']['bytes_per_tile_measured'] // 8388608)
get_usd = gets / 1000 * prices['s3_get_requests']['value']
res['cost_original_recheck'] = {'per_plot_seconds': round(per_plot, 2), 'tile_decode_seconds_total': round(100 * dec_vals['original_layers_geotiff'], 2),
                                'recomputed_total_seconds': round(per_plot + 100 * dec_vals['original_layers_geotiff'], 2), 'recorded': rc['total_compute_seconds'],
                                'recomputed_usd': round(lam + get_usd, 5), 'recorded_usd': rc['total_usd'], 'gets': (gets, rc['gets'])}
l2 = cost['recheck_10m_plots']['L2_decision']['measured_tile']['tropical_belt']
l2_s = 10_000_000 * ci['registry_us'] / 1e6 + 100 * dec_vals['L2_decision']
res['cost_l2_registry_recheck'] = {'recomputed_total_seconds': round(l2_s, 2), 'recorded': l2['total_compute_seconds']}
newp = cost['recheck_10m_plots']['L2_decision_new_polygons']['measured_tile']['tropical_belt']
res['cost_l2_new_polygon_recheck'] = {'recomputed_total_seconds': round(10_000_000 * ci['new_polygon_us'] / 1e6 + 100 * dec_vals['L2_decision'], 2), 'recorded': newp['total_compute_seconds']}
for k, v in (('cost_original_recheck', (res['cost_original_recheck']['recomputed_total_seconds'], rc['total_compute_seconds'])),
             ('cost_l2_registry_recheck', (res['cost_l2_registry_recheck']['recomputed_total_seconds'], l2['total_compute_seconds'])),
             ('cost_l2_new_polygon_recheck', (res['cost_l2_new_polygon_recheck']['recomputed_total_seconds'], newp['total_compute_seconds']))):
    if abs(v[0] - v[1]) > 0.06:
        bad.append(f'{k} does not recompute: {v}')
if abs(res['cost_original_recheck']['recomputed_usd'] - rc['total_usd']) > 2e-5:
    bad.append('original recheck USD does not recompute')
cont = cost['assumptions'].get('container', {})
res['container_caveat'] = {'present': bool(cont), 'says_not_implemented': 'NOT implemented' in cont.get('assumption', ''),
                           'store_max_cells': cont.get('store_max_cells'), 'store_max_dimension': cont.get('store_max_dimension')}
if not (res['container_caveat']['present'] and res['container_caveat']['says_not_implemented'] and cont.get('store_max_cells') == S_MAX_CELLS and cont.get('store_max_dimension') == S_MAX_DIM):
    bad.append('container/memory caveat missing or wrong')
cells = scale['tile']['hansen_cells']
res['memory_feasibility'] = {'decoded_tile_bytes_uint8': cells, 'lambda_memory_bytes': int(cost['assumptions']['lambda']['memory_gb'] * GB),
                             'whole_tile_fits': cells < cost['assumptions']['lambda']['memory_gb'] * GB, 'tile_width': 40000,
                             'note': 'cost-v1 now states the strip-indexed container is not implemented; strips of 250 rows (10 MB) fit'}
res['bad'] = bad
(OUT / 'v08.json').write_text(json.dumps(res, indent=1, default=str) + '\n')
print(json.dumps(res, indent=1, default=str))
sys.exit(1 if bad else 0)
