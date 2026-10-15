"""Claim 9: recompute layer-analysis-v1.json facts independently and probe the dropped-attribute semantics.

(a) region facts, plane sizes (zstd-19 / xz-9e), the 3x3 JRC sensitivity study, from raw rasterio reads.
(b) static check that engine.decision never reads treecover2000 values or masks[0].
(c) mask semantics: v1 `known_bands` (all three masks) vs the decision layers (lossyear + datamask masks only).
"""
import inspect
import json
import lzma
import sys

import numpy as np
from compression import zstd

from _common import ART, OUT, facts_to_codes, independent_facts, read_raw

res, bad = {}, []
A = json.loads((ART / 'layer-analysis-v1.json').read_text())
raw = read_raw()
F = independent_facts(raw)
h, w = raw['lossyear']['shape']
L, D, T = raw['lossyear']['v'], raw['datamask']['v'], raw['treecover2000']['v']
land = F['land'] == 2
forest = F['forest']
post = np.where(L > 20, L.astype(int) - 20, 0)
rf = A['region_facts']


def eq(name, mine, theirs):
    ok = mine == theirs
    res.setdefault('region_facts', {})[name] = {'mine': mine, 'recorded': theirs, 'ok': ok}
    if not ok:
        bad.append(name)


eq('land_cells', int(land.sum()), rf['land_cells'])
eq('water_cells', int((F['land'] == 1).sum()), rf['water_cells'])
eq('any_loss_land', int((land & (L > 0)).sum()), rf['land_cells_with_any_hansen_loss'])
eq('post2020_loss', int((land & (post > 0)).sum()), rf['post2020_loss_cells'])
eq('deforested', int((land & (post > 0) & (forest == 1)).sum()), rf['post2020_loss_on_jrc_forest_cells_deforested'])
eq('loss_on_nonforest', int((land & (post > 0) & (forest == 0)).sum()), rf['post2020_loss_on_jrc_nonforest_cells'])
eq('loss_on_unknown_forest', int((land & (post > 0) & (forest == 2)).sum()), rf['post2020_loss_on_unknown_forest_state_cells'])
eq('deforested_by_year', {str(2020 + i): int((land & (post == i) & (forest == 1)).sum()) for i in range(1, 6)}, rf['deforested_by_year'])
eq('jrc_forest_at_centres_on_land', int((land & (forest == 1)).sum()), rf['jrc_forest_cells_at_hansen_centres_on_land'])
eq('unknown_forest_land', int((land & (forest == 2)).sum()), rf['land_cells_with_unknown_forest_state'])
proxy = land & (T > 10) & ((L == 0) | (L > 20))
eq('proxy_forest_cells', int(proxy.sum()), rf['hansen_only_proxy_forest_2020']['cells'])
eq('proxy_post_loss', int((proxy & (post > 0)).sum()), rf['hansen_only_proxy_forest_2020']['post2020_loss_cells_on_proxy_forest'])
eq('proxy_overlap_jrc', int((proxy & (forest == 1)).sum()), rf['hansen_only_proxy_forest_2020']['overlap_with_jrc_forest_cells'])
eq('jrc_native_forest_share', round(100 * float((raw['jrc']['v'] == 1).mean()), 4), rf['jrc_native_forest_share_percent'])

# plane sizes (same yardstick: whole-plane, row-major, zstd 19 / xz 9e)
z19 = lambda a: len(zstd.compress(np.ascontiguousarray(a).reshape(-1), level=19))
x9 = lambda a: len(lzma.compress(np.ascontiguousarray(a).reshape(-1), format=lzma.FORMAT_XZ, preset=9 | lzma.PRESET_EXTREME))
screen, decision = facts_to_codes(F, 'eudr-screen.v1'), facts_to_codes(F, 'eudr-decision.v1')
planes = {'treecover2000_exact': T, 'lossyear_full': L, 'datamask': D, 'jrc_native_9m': raw['jrc']['v'],
          'screen_codes_L1': screen, 'decision_codes_L2': decision}
rec = {r['plane']: r for r in A['attribution']}
sizes = {}
for name, plane in planes.items():
    sizes[name] = {'mine_z19': z19(plane), 'rec_z19': rec[name]['zstd19_bytes'], 'mine_xz': x9(plane), 'rec_xz': rec[name]['xz_bytes']}
    if sizes[name]['mine_z19'] != sizes[name]['rec_z19'] or sizes[name]['mine_xz'] != sizes[name]['rec_xz']:
        bad.append(f'size {name}')
res['plane_sizes'] = sizes

# JRC 3x3 sensitivity: block of Hansen (r,c) = JRC rows jr-1..jr+1, cols jc-1..jc+1 around the centre index
JV, JM = raw['jrc']['v'], raw['jrc']['m']
jh, jw = JV.shape
jr, jc = F['jrow'], F['jcol']
pad = np.pad(JV.astype(np.int16), 2, constant_values=0)
inside_pad = np.pad(JM, 2, constant_values=False)
cnt = np.zeros((h, w), np.int16)
full = np.ones((h, w), bool)
for dr in (-1, 0, 1):
    for dc in (-1, 0, 1):
        rr = (jr + dr + 2)[:, None] * np.ones((1, w), int)
        cc = (jc + dc + 2)[None, :] * np.ones((h, 1), int)
        ok = (rr >= 2) & (rr < jh + 2) & (cc >= 2) & (cc < jw + 2)
        rr, cc = np.clip(rr, 0, jh + 3), np.clip(cc, 0, jw + 3)
        cnt += np.where(ok, pad[rr, cc], 0)
        full &= ok & inside_pad[rr, cc]
univ = full & land
sens = {}
for name, f in (('centre', forest == 1), ('any', cnt >= 1), ('majority', cnt >= 5)):
    fo = f & full
    sens[name] = {'land': int(univ.sum()), 'forest': int((univ & fo).sum()), 'deforested': int((univ & fo & (post > 0)).sum())}
R = A['aggregation_sensitivity']['region']
chk = {'centre': R['centre_cell'], 'any': R['any_forest_in_block'], 'majority': R['majority_forest_in_block']}
for k, v in sens.items():
    ok = (v['land'], v['forest'], v['deforested']) == (chk[k]['land_cells'], chk[k]['forest_cells'], chk[k]['deforested_cells'])
    sens[k]['matches_recorded'] = ok
    if not ok:
        bad.append(f'sensitivity {k}')
sens['universe_hansen_cells'] = (int(full.sum()), A['aggregation_sensitivity']['universe']['cells_in_universe'])
res['sensitivity_3x3'] = sens

# plot-level sensitivity: only P-0001 has any forest, so the study cannot distinguish rules at plot level
plot_forest = {r['plot_id']: r['centre_cell']['forest_cells'] for r in A['aggregation_sensitivity']['plots']}
res['sensitivity_discriminating_plots'] = {k: v for k, v in plot_forest.items() if v}

# ---- (b) static: which masks does derive_screen_codes consult? -------------------------------------------
from engine import decision as Dm
src = inspect.getsource(Dm.derive_screen_codes)
res['static_derive_source_mentions'] = {'bands[0] (treecover values)': 'bands[0]' in src, 'masks.all(axis=0)': 'masks.all(axis=0)' in src,
                                        'MAX_LOSSYEAR guard': 'MAX_LOSSYEAR' in src}
if 'bands[0]' in src or 'masks.all(axis=0)' not in src or 'MAX_LOSSYEAR' not in src:
    bad.append('derive_screen_codes source no longer matches the documented rule')

# ---- (c) mask semantics vs v1 (changed 15 Oct: all three band masks, as v1's known_bands) ----------------------
from engine.model import Dataset
from engine.query import evaluate as v1_evaluate, select_cells
from engine.source import load_source, load_plots
from engine.jrc import load_jrc
hansen, jrc = load_source(), load_jrc()
plots = {p['plot_id']: p for p in load_plots()}
res['real_data_masks'] = {'all_true_hansen_masks': bool(hansen.masks.all()), 'jrc_mask_all_true': bool(jrc.mask.all()),
                          'datamask_zero_cells': int((hansen.bands[2] == 0).sum())}
geom = plots['P-0001']['geometry']
rows, cols = select_cells(hansen.metadata, geom)
codes = Dm.derive_screen_codes(hansen, jrc)
for band, label in ((0, 'treecover2000'), (1, 'lossyear'), (2, 'datamask')):
    masks = hansen.masks.copy()
    masks[band, rows[:10], cols[:10]] = False
    syn = Dataset(hansen.bands, masks, hansen.metadata)
    v1 = v1_evaluate(syn, geom)
    new = Dm.evaluate_codes(Dm.derive_screen_codes(syn, jrc), hansen.metadata, geom, Dm.SCREEN_VERSION)
    row = {'v1_unknown': v1['unknown_cell_count'], 'v1_support': v1['support'], 'v1_valid_land': v1['valid_land_cell_count'],
           'decision_unknown': new['unknown_cell_count'], 'decision_support': new['support'], 'decision_valid_land': new['valid_land_cell_count']}
    row['equal_to_v1'] = (row['v1_unknown'], row['v1_valid_land'], row['v1_support']) == (row['decision_unknown'], row['decision_valid_land'], row['decision_support'])
    res[f'{label}_mask_invalid_at_10_cells'] = row
    if not row['equal_to_v1'] or row['decision_unknown'] != 10:
        bad.append(f'{label} mask semantics differ from v1')
# lossyear / datamask guards
def guard(label, band, value, masked):
    bands2 = hansen.bands.copy()
    r0, c0 = int(rows[0]), int(cols[0])
    bands2[band, r0, c0] = value
    masks2 = hansen.masks.copy()
    if masked:
        masks2[band, r0, c0] = False
    try:
        c3 = Dm.derive_screen_codes(Dataset(bands2, masks2, hansen.metadata), jrc)
        res[label] = {'accepted': True, 'code_before': int(codes[r0, c0]), 'code_after': int(c3[r0, c0])}
        return True
    except ValueError as e:
        res[label] = {'accepted': False, 'error': str(e)}
        return False
if guard('lossyear_26_valid_cell', 1, 26, False):
    bad.append('derive_screen_codes still accepts lossyear 26 on a valid cell (code aliasing)')
if guard('lossyear_255_valid_cell', 1, 255, False):
    bad.append('lossyear 255 accepted')
if guard('datamask_3_valid_cell', 2, 3, False):
    bad.append('datamask 3 accepted on a valid cell')
if not guard('lossyear_26_masked_cell', 1, 26, True):
    bad.append('lossyear 26 on an already-unknown (masked) cell is refused (over-strict)')
if not guard('lossyear_25_valid_cell', 1, 25, False):
    bad.append('lossyear 25 (the horizon) refused')

res['bad'] = bad
(OUT / 'v09.json').write_text(json.dumps(res, indent=1, default=str) + '\n')
print(json.dumps({k: v for k, v in res.items() if k != 'region_facts'}, indent=1, default=str))
print('region facts all ok:', all(v['ok'] for v in res['region_facts'].values()))
print('bad:', bad)
sys.exit(1 if bad else 0)  # exit 1 = defect reproduced
