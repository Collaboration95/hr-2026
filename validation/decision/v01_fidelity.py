"""Claim 1 and 3: fidelity against an independent rational-arithmetic derivation, plus semantics probes.

Exit 0 when every check passes. Prints a JSON summary and writes validation/decision/out/v01.json.
"""
import json
import random
import sys
import time

import numpy as np

from _common import (ART, OUT, ROOT, exact_select, facts_to_codes, independent_facts, load_plots, read_raw,
                     reduce_facts, same_json)

from engine import decision as D
from engine.decision_original import cell_attributes
from engine.decision_store import read_store
from engine.query import select_cells

res, fail = {}, []


def check(name, ok, **info):
    res[name] = {'ok': bool(ok), **info}
    if not ok:
        fail.append(name)


raw = read_raw()
F = independent_facts(raw)
h, w = raw['lossyear']['shape']
check('grid_size', h * w == 744_732, cells=h * w)
check('jrc_lookup_hansen_centre_is_jrc_centre', F['margin'] < 1e-6, max_deviation_from_jrc_cell_centre_in_jrc_cells=F['margin'])

# --- A. exhaustive cell equality: independent derivation vs decoded stores vs engine derive ----------
stores, derived = {}, {}
for level, fn in ((D.SCREEN_VERSION, 'screen.plds'), (D.DECISION_VERSION, 'decision.plds')):
    codes, header = read_store(ART / fn)
    stores[level] = (codes, header)
mine = {lv: facts_to_codes(F, lv) for lv in stores}
for level in stores:
    codes, header = stores[level]
    check(f'cells_store_vs_independent[{level}]', np.array_equal(codes, mine[level]),
          mismatches=int((codes != mine[level]).sum()), cells=int(codes.size))
screen = mine[D.SCREEN_VERSION]
check('decision_is_projection_of_screen', np.array_equal(mine[D.DECISION_VERSION], D.project_decision(screen)))

# Hansen/Dataset from the engine loaders vs raw read (shared-input sanity)
from engine.source import load_source
from engine.jrc import load_jrc
hansen, jrc = load_source(), load_jrc()
check('engine_derive_equals_independent', np.array_equal(D.derive_screen_codes(hansen, jrc), screen))

# JRC lookup three ways at every Hansen cell: exact rational, engine integer offsets, float affine (decision_original)
k, ro, co = D.nested_offsets(hansen.metadata, jrc.metadata)
int_r = k * np.arange(h) + ro
int_c = k * np.arange(w) + co
rows, cols = np.meshgrid(np.arange(h), np.arange(w), indexing='ij')
attrs = cell_attributes(hansen, jrc, rows, cols)
exact_r = np.broadcast_to(F['jrow'][:, None], (h, w))
exact_c = np.broadcast_to(F['jcol'][None, :], (h, w))
check('jrc_index_three_way', np.array_equal(int_r, F['jrow']) and np.array_equal(int_c, F['jcol'])
      and np.array_equal(np.where(attrs['jrc_row'] >= 0, attrs['jrc_row'], exact_r),
                         np.where(attrs['jrc_row'] >= 0, exact_r, exact_r)),
      ratio=k, row_offset=ro, col_offset=co)
inside = attrs['jrc_row'] >= 0
check('jrc_float_vs_exact_inside', np.array_equal(attrs['jrc_row'][inside], exact_r[inside])
      and np.array_equal(attrs['jrc_col'][inside], exact_c[inside]))
jh, jw = raw['jrc']['v'].shape
exact_inside = (exact_r >= 0) & (exact_r < jh) & (exact_c >= 0) & (exact_c < jw)
check('jrc_inside_set_equal', np.array_equal(inside, exact_inside), cells_without_jrc=int((~exact_inside).sum()),
      fringe_rows=sorted({int(r) for r in np.where(~exact_inside)[0]})[:3] + ['...'],
      fringe_cols=sorted({int(c) for c in np.where(~exact_inside)[1]})[:3] + ['...'])

# --- B. JRC chip geometry vs Hansen chip (is any out-of-Hansen-chip centre inside the JRC chip?) -------
from fractions import Fraction as Fr
a, _, c, _, e, f = (Fr(v) for v in raw['lossyear']['t'])
ja, _, jc, _, je, jf = (Fr(v) for v in raw['jrc']['t'])
hx0, hx1, hy0, hy1 = c, c + w * a, f, f + h * e
jx0, jx1, jy0, jy1 = jc, jc + jw * ja, jf, jf + jh * je
check('jrc_chip_inside_hansen_chip', hx0 <= jx0 and jx1 <= hx1 and hy1 <= jy1 and jy0 <= hy0,
      note='JRC chip extent is strictly inside the Hansen chip extent, so no out-of-Hansen-chip centre can have a JRC value',
      margins_in_jrc_cells={'west': float((jx0 - hx0) / ja), 'east': float((hx1 - jx1) / ja),
                            'north': float((hy0 - jy0) / (-je)), 'south': float((jy1 - hy1) / (-je))})
bad = 0
for r in range(-6, h + 6):
    for kk in list(range(-6, 3)) + list(range(w - 3, w + 6)):
        if 0 <= r < h and 0 <= kk < w:
            continue
        x = c + (kk + Fr(1, 2)) * a
        y = f + (r + Fr(1, 2)) * e
        if jx0 <= x < jx1 and jy1 < y <= jy0:
            bad += 1
check('no_outside_hansen_centre_in_jrc_chip', bad == 0, violations=bad)

# --- C. 17 plots: exact selection and own reducer vs store path, table.json, proof-v1.json ------------
plots = load_plots()
check('plots_17', len(plots) == 17)
table = json.loads((ART / 'table.json').read_text())
proof = json.loads((ART / 'proof-v1.json').read_text())
meta = hansen.metadata
hdr_grid = {'shape': stores[D.SCREEN_VERSION][1]['shape'], 'transform': stores[D.SCREEN_VERSION][1]['transform'],
            'crs': stores[D.SCREEN_VERSION][1]['crs']}
sel_equal, out_equal, tab_equal, proof_equal, hdr_equal, reg_equal, st_equal, regst_equal = 0, 0, 0, 0, 0, 0, 0, 0
from engine import decision_index as DI
registry = DI.load_registry(ART / 'registry.bin')
for plot in plots:
    pid, geom = plot['plot_id'], plot['geometry']
    er, ec = exact_select(raw['lossyear']['t'], geom)
    sr, sc = select_cells(meta, geom)
    sel_equal += (np.array_equal(er, sr) and np.array_equal(ec, sc))
    ins = (er >= 0) & (er < h) & (ec >= 0) & (ec < w)
    cells = [(int(F['land'][r, k_]), int(F['forest'][r, k_]), int(F['year'][r, k_])) for r, k_ in zip(er[ins], ec[ins])]
    for level in stores:
        want = reduce_facts(cells, int((~ins).sum()), level)
        got = D.evaluate_codes(stores[level][0], meta, geom, level)
        out_equal += same_json(want, got)
        hdr_equal += same_json(want, D.evaluate_codes(stores[level][0], hdr_grid, geom, level))
        tab_equal += same_json(want, table['plots'][pid]['outputs'][level])
        reg_equal += same_json(want, DI.registry_evaluate(stores[level][0], registry['plots'][pid], level))
        st_equal += same_json(want, D.evaluate_store(stores[level][0], stores[level][1], geom))  # level and grid from the header
        regst_equal += same_json(want, DI.registry_evaluate_store(stores[level][0], stores[level][1], registry['plots'][pid]))
        pf = next(p for p in proof['plot_proof'][level]['plots'] if p['plot_id'] == pid)
        proof_equal += same_json(want, pf['output'])
n = len(plots)
check('plots_exact_selection_equals_select_cells', sel_equal == n, equal=sel_equal, of=n)
check('plots_independent_output_equals_store_path', out_equal == 2 * n, equal=out_equal, of=2 * n)
check('plots_output_via_header_grid', hdr_equal == 2 * n, equal=hdr_equal, of=2 * n)
check('plots_independent_output_equals_table_json', tab_equal == 2 * n, equal=tab_equal, of=2 * n)
check('plots_independent_output_equals_registry_evaluate', reg_equal == 2 * n, equal=reg_equal, of=2 * n)
check('plots_independent_output_equals_evaluate_store', st_equal == 2 * n, equal=st_equal, of=2 * n)
check('plots_independent_output_equals_registry_evaluate_store', regst_equal == 2 * n, equal=regst_equal, of=2 * n)
check('plots_independent_output_equals_proof_json', proof_equal == 2 * n, equal=proof_equal, of=2 * n)

# --- D. independent random-polygon fuzz (exact rational selection, own reducer) -----------------------
rng = random.Random(7)
a_f, c_f, e_f, f_f = raw['lossyear']['t'][0], raw['lossyear']['t'][2], raw['lossyear']['t'][4], raw['lossyear']['t'][5]


def pt(u, v):
    return [c_f + u * a_f, f_f + v * e_f]


def ring(uv):
    p = [pt(u, v) for u, v in uv]
    return p + [list(p[0])]


def rand_geom():
    kind = rng.choice(('rect', 'snap', 'tri', 'hole', 'multi', 'edge', 'outside', 'water'))
    u, v = rng.uniform(-6, w + 6), rng.uniform(-6, h + 6)
    if kind in ('edge', 'water'):
        if kind == 'edge':  # straddle the JRC fringe (col 0 / last col / last row) or the chip boundary
            side = rng.choice(('c0', 'c1', 'r1', 'rb', 'cb'))
            u, v = {'c0': (0, rng.uniform(0, h - 8)), 'c1': (w - 4, rng.uniform(0, h - 8)),
                    'r1': (rng.uniform(0, w - 8), h - 4), 'rb': (rng.uniform(0, w - 8), h - 3),
                    'cb': (w - 2, rng.uniform(0, h - 8))}[side]
        else:
            wr = np.argwhere(raw['datamask']['v'] == 2)
            r0_, c0_ = wr[rng.randrange(len(wr))]
            u, v = float(c0_) - rng.uniform(0, 4), float(r0_) - rng.uniform(0, 4)
        s = rng.uniform(1.5, 9)
        sn = rng.random() < .5
        if sn:
            u, v = np.floor(u) + .5, np.floor(v) + .5
        return {'type': 'Polygon', 'coordinates': [ring([(u, v), (u + s, v), (u + s, v + s * .7), (u, v + s * .7)])]}
    s = rng.uniform(.4, 10)
    if kind in ('rect', 'outside'):
        if kind == 'outside':
            u, v = rng.choice((-1, w + 1)) + rng.uniform(-3, 3), rng.uniform(-3, h + 3)
        if rng.random() < .5:
            u, v = np.floor(u) + .5, np.floor(v) + .5
            s = np.floor(s) + 1
        return {'type': 'Polygon', 'coordinates': [ring([(u, v), (u + s, v), (u + s, v + s), (u, v + s)])]}
    if kind == 'tri':
        return {'type': 'Polygon', 'coordinates': [ring([(u, v), (u + s, v + rng.uniform(0, s)), (u + rng.uniform(0, s), v + s)])]}
    if kind == 'hole':
        s = max(s, 5)
        return {'type': 'Polygon', 'coordinates': [ring([(u, v), (u + s, v), (u + s, v + s), (u, v + s)]),
                                                    ring([(u + 1, v + 1), (u + 1, v + s - 1), (u + s - 1, v + s - 1), (u + s - 1, v + 1)])]}
    return {'type': 'MultiPolygon', 'coordinates': [
        [ring([(u, v), (u + s, v), (u + s, v + s), (u, v + s)])],
        [ring([(u + s + 1, v), (u + 2 * s + 1, v), (u + 2 * s + 1, v + s * .5)])]]}


t0 = time.time()
fuzz_total = fuzz_ok = 0
branches = {}
for i in range(400):
    g = rand_geom()
    try:
        sr, sc = select_cells(meta, g)
    except ValueError:
        continue
    er, ec = exact_select(raw['lossyear']['t'], g)
    if not (np.array_equal(er, sr) and np.array_equal(ec, sc)):
        fail.append(f'fuzz_selection_mismatch_{i}')
        continue
    ins = (er >= 0) & (er < h) & (ec >= 0) & (ec < w)
    cells = [(int(F['land'][r, k_]), int(F['forest'][r, k_]), int(F['year'][r, k_])) for r, k_ in zip(er[ins], ec[ins])]
    for level in stores:
        want = reduce_facts(cells, int((~ins).sum()), level)
        got = D.evaluate_codes(stores[level][0], meta, g, level)
        fuzz_total += 1
        fuzz_ok += same_json(want, got)
        if level == D.SCREEN_VERSION:
            for lab in (f"support={want['support']}", f"forest={want['forest_2020']['present']}",
                        f"defo={want['deforestation_after_2020']['present']}", f"outside>0={want['out_of_coverage_cell_count'] > 0}",
                        f"water>0={want['water_cell_count'] > 0}"):
                branches[lab] = branches.get(lab, 0) + 1
check('independent_fuzz_equal', fuzz_total > 500 and fuzz_ok == fuzz_total, compared=fuzz_total, equal=fuzz_ok,
      seconds=round(time.time() - t0, 1), branch_coverage=dict(sorted(branches.items())))

# --- E. what do the outputs depend on? perturb things the contract claims to drop ---------------------
from engine.model import Dataset
from engine.jrc import JrcDataset
base = D.derive_screen_codes(hansen, jrc)
prng = np.random.default_rng(5)
tc = hansen.bands.copy()
tc[0] = prng.integers(0, 101, tc[0].shape).astype(np.uint8)
check('perturb_treecover_values', np.array_equal(D.derive_screen_codes(Dataset(tc, hansen.masks, hansen.metadata), jrc), base))
old = hansen.bands.copy()
mask_old = (old[1] >= 1) & (old[1] <= 20)
old[1][mask_old] = prng.integers(1, 21, int(mask_old.sum())).astype(np.uint8)
check('perturb_lossyear_2001_2020', np.array_equal(D.derive_screen_codes(Dataset(old, hansen.masks, hansen.metadata), jrc), base))
jv = jrc.values.copy()
centre = np.zeros(jv.shape, bool)
ok_ = (F['jrow'][:, None] >= 0) & (F['jrow'][:, None] < jh) & (F['jcol'][None, :] >= 0) & (F['jcol'][None, :] < jw)
centre[np.broadcast_to(F['jrow'][:, None], (h, w))[ok_], np.broadcast_to(F['jcol'][None, :], (h, w))[ok_]] = True
jv[~centre] = prng.integers(0, 2, int((~centre).sum())).astype(np.uint8)
check('perturb_jrc_noncentre', np.array_equal(D.derive_screen_codes(hansen, JrcDataset(jv, jrc.mask, jrc.metadata)), base),
      noncentre_cells_randomised=int((~centre).sum()))
# treecover2000 VALUES are ignored, its MASK is not (since 15 Oct): invalid there makes the cell unknown, as in v1
tm = hansen.masks.copy()
tm[0, 100:110, 100:110] = False
tc2 = D.derive_screen_codes(Dataset(hansen.bands, tm, hansen.metadata), jrc)
check('treecover_mask_invalid_makes_cells_unknown', int((tc2 != base).sum()) == int((base[100:110, 100:110] != 0).sum()) and (tc2[100:110, 100:110] == 0).all(),
      cells_changed=int((tc2 != base).sum()))
# JRC mask False at a centre -> forest unknown; JRC mask False elsewhere -> no change
jm = jrc.mask.copy()
jm[~centre] = False
check('perturb_jrc_mask_noncentre', np.array_equal(D.derive_screen_codes(hansen, JrcDataset(jrc.values, jm, jrc.metadata)), base))

# --- F. semantics cross-checks (claim 3) ---------------------------------------------------------------
p1 = next(p for p in plots if p['plot_id'] == 'P-0001')
out1 = D.evaluate_codes(stores[D.SCREEN_VERSION][0], meta, p1['geometry'], D.SCREEN_VERSION)
y = out1['hansen_loss_after_2020']['yearly_cell_counts']
check('p0001_numbers', out1['deforestation_after_2020']['cell_count'] == 2 and
      out1['hansen_loss_after_2020']['periods']['2021-2023']['observed_loss_cell_count'] == 38,
      deforestation_cells=out1['deforestation_after_2020']['cell_count'], hansen_2021_23=out1['hansen_loss_after_2020']['periods']['2021-2023']['observed_loss_cell_count'],
      yearly_hansen_loss=y, yearly_deforestation=out1['deforestation_after_2020']['yearly_cell_counts'])

# Layer-coherence facts the docs may not state: JRC forest at 2020 but Hansen says cleared 2001-2020
Lraw = raw['lossyear']['v']
land_m = F['land'] == 2
f1 = (F['forest'] == 1) & land_m
res['semantics_jrc_forest_with_hansen_loss_before_cutoff'] = {
    'cells': int((f1 & (Lraw >= 1) & (Lraw <= 20)).sum()), 'of_jrc_forest_land_cells': int(f1.sum()),
    'note': 'JRC 2020 forest cells where Hansen records loss in 2001-2020; contract keeps them as forest at the cut-off (JRC is the baseline)'}
res['semantics_p0001_plot_cells'] = {
    'selected': out1['selected_cell_count'], 'forest_counts': out1['forest_2020']['cell_counts']}

# --- G. tri-state probes on synthetic count histograms (water-only, nodata-only, JRC-unknown, outside-only) ---
def hist(**kw):
    c = [0] * D.CODE_COUNT
    for key, v in kw.items():
        c[int(key[1:])] = v
    return c


probes = {}
def probe(name, counts, selected, outside, level=D.SCREEN_VERSION):
    probes[name] = D.summarize_counts(counts, selected, outside, level)

probe('water_only', hist(c1=5), 5, 0)
probe('nodata_only', hist(c0=3), 3, 0)
probe('outside_only', hist(), 4, 4)
probe('empty', hist(), 0, 0)
probe('land_nonforest_noloss', hist(c2=10), 10, 0)
probe('land_nonforest_loss_screen', hist(c2=9, c4=1), 10, 0)
probe('land_nonforest_loss_decision', hist(c2=10), 10, 0, D.DECISION_VERSION)
probe('forestunknown_noloss', hist(c14=7), 7, 0)
probe('forestunknown_loss', hist(c14=6, c16=1), 7, 0)
probe('forest_noloss_plus_outside', hist(c8=10), 12, 2)
probe('forest_loss_plus_outside', hist(c8=9, c9=1), 12, 2)
probe('forest_plus_water', hist(c8=3, c1=2), 5, 0)
exp = {
    'water_only': (None, None, 'none'), 'nodata_only': (None, None, 'none'), 'outside_only': (None, None, 'none'),
    'empty': (None, None, 'none'), 'land_nonforest_noloss': (False, False, 'complete'),
    'land_nonforest_loss_screen': (False, False, 'complete'), 'land_nonforest_loss_decision': (False, False, 'complete'),
    'forestunknown_noloss': (None, False, 'partial'), 'forestunknown_loss': (None, None, 'partial'),
    'forest_noloss_plus_outside': (True, None, 'partial'), 'forest_loss_plus_outside': (True, True, 'partial'),
    'forest_plus_water': (True, False, 'complete')}
bad = {}
for name, (fo, de, sup) in exp.items():
    got = probes[name]
    if (got['forest_2020']['present'], got['deforestation_after_2020']['present'], got['support']) != (fo, de, sup):
        bad[name] = (got['forest_2020']['present'], got['deforestation_after_2020']['present'], got['support'], 'expected', (fo, de, sup))
check('tristate_probes', not bad, mismatches=bad, cases=len(exp))

summary = {'failed': fail, 'checks': res}
(OUT / 'v01.json').write_text(json.dumps(summary, indent=1, default=str) + '\n')
print(json.dumps({k: v['ok'] for k, v in res.items() if isinstance(v, dict) and 'ok' in v}, indent=1))
for k in ('jrc_lookup_hansen_centre_is_jrc_centre', 'jrc_index_three_way', 'jrc_inside_set_equal', 'jrc_chip_inside_hansen_chip', 'p0001_numbers',
          'independent_fuzz_equal'):
    print(k, json.dumps(res[k], default=str))
for k in ('semantics_jrc_forest_with_hansen_loss_before_cutoff',):
    print(k, res[k])
print('FAILED:', fail)
sys.exit(1 if fail else 0)
