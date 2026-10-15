"""Claim 1 addendum: the real chip has no nodata/invalid-mask cells, so the unknown branches are never hit by the
exhaustive proof. Inject them (synthetic, labelled) and rerun the three-way comparison:
  engine.decision derive  vs  engine.decision_original (float path)  vs  this validator's rational-arithmetic facts,
plus codec round-trip and polygon outputs (exact selection + own reducer).
"""
import json, random, sys, tempfile
from pathlib import Path
import numpy as np
from _common import OUT, exact_select, facts_to_codes, independent_facts, read_raw, reduce_facts, same_json, load_plots
from engine import decision as D, decision_original as O, decision_store as S
from engine.model import Dataset
from engine.jrc import JrcDataset
from engine.source import load_source
from engine.jrc import load_jrc

rng = np.random.default_rng(2026)
raw = read_raw()
h, w = raw['lossyear']['shape']
mut = {k: dict(v, v=v['v'].copy(), m=v['m'].copy()) for k, v in raw.items()}
# synthetic damage (explicitly synthetic): nodata datamask cells, invalid masks on each Hansen band, invalid JRC cells
mut['datamask']['v'][rng.random((h, w)) < .02] = 0
for b in ('lossyear', 'datamask'):
    mut[b]['m'][rng.random((h, w)) < .01] = False
mut['treecover2000']['m'][rng.random((h, w)) < .05] = False  # since 15 Oct this DOES matter: a cell is known only if all three band masks are valid (as v1)
jh, jw = raw['jrc']['v'].shape
mut['jrc']['m'][rng.random((jh, jw)) < .03] = False
# make sure some invalid JRC cells are exactly the ones under Hansen centres
F0 = independent_facts(raw)
rr, cc = rng.integers(0, h, 3000), rng.integers(1, w - 1, 3000)
ok = (F0['jrow'][rr] >= 0) & (F0['jrow'][rr] < jh)
mut['jrc']['m'][F0['jrow'][rr][ok], F0['jcol'][cc][ok]] = False

hansen = load_source()
jrc = load_jrc()
bands = np.stack([mut[b]['v'] for b in ('treecover2000', 'lossyear', 'datamask')])
masks = np.stack([mut[b]['m'] for b in ('treecover2000', 'lossyear', 'datamask')])
H = Dataset(bands, masks, hansen.metadata)
J = JrcDataset(mut['jrc']['v'], mut['jrc']['m'], jrc.metadata)
F = independent_facts(mut)
res = {}
fails = []
derived = D.derive_screen_codes(H, J)
for level in D.LEVELS:
    d = derived if level == D.SCREEN_VERSION else D.project_decision(derived)
    o = O.exhaustive_attribute_codes(H, J, level)
    m = facts_to_codes(F, level)
    res[f'cells[{level}]'] = {'derive_vs_original_mismatch': int((d != o).sum()), 'derive_vs_independent_mismatch': int((d != m).sum()),
                             'unknown_cells': int((d == 0).sum()), 'forest_unknown_land': int(((d >= 14)).sum()), 'water': int((d == 1).sum())}
    if (d != o).any() or (d != m).any():
        fails.append(f'cells {level}')
    # codec round trip on a raster full of unknowns
    for enc in S.ENCODINGS:
        if not np.array_equal(S.decode_codes(S.encode_codes(d, enc), d.shape, enc), d):
            fails.append(f'codec {enc} {level}')
# polygon outputs
r = random.Random(5)
plots = load_plots()
a_, c_, e_, f_ = raw['lossyear']['t'][0], raw['lossyear']['t'][2], raw['lossyear']['t'][4], raw['lossyear']['t'][5]
n = ok_n = 0
for i in range(300):
    u, v = r.uniform(-3, w + 3), r.uniform(-3, h + 3)
    s = r.uniform(1, 12)
    pts = [[c_ + u * a_, f_ + v * e_], [c_ + (u + s) * a_, f_ + v * e_], [c_ + (u + s) * a_, f_ + (v + s * .8) * e_], [c_ + u * a_, f_ + (v + s * .8) * e_]]
    g = {'type': 'Polygon', 'coordinates': [pts + [pts[0]]]}
    er, ec = exact_select(raw['lossyear']['t'], g)
    ins = (er >= 0) & (er < h) & (ec >= 0) & (ec < w)
    cells = [(int(F['land'][a, b]), int(F['forest'][a, b]), int(F['year'][a, b])) for a, b in zip(er[ins], ec[ins])]
    for level in D.LEVELS:
        want = reduce_facts(cells, int((~ins).sum()), level)
        dd = derived if level == D.SCREEN_VERSION else D.project_decision(derived)
        got = D.evaluate_codes(dd, hansen.metadata, g, level)
        orig = O.evaluate_original(H, J, g, level)
        n += 1
        ok_n += same_json(want, got) and same_json(want, orig)
res['polygons'] = {'compared': n, 'three_way_equal': ok_n}
# damaged-data cross-check against the frozen v1 query (known_bands = all three masks)
from engine.query import evaluate as v1_evaluate
r2 = random.Random(8)
v1_ok = v1_n = 0
for i in range(300):
    u, v = r2.uniform(-3, w + 3), r2.uniform(-3, h + 3)
    s_ = r2.uniform(1, 14)
    pts = [[c_ + u * a_, f_ + v * e_], [c_ + (u + s_) * a_, f_ + v * e_], [c_ + (u + s_) * a_, f_ + (v + s_ * .8) * e_], [c_ + u * a_, f_ + (v + s_ * .8) * e_]]
    g = {'type': 'Polygon', 'coordinates': [pts + [pts[0]]]}
    old = v1_evaluate(H, g)
    new = D.evaluate_codes(derived, hansen.metadata, g, D.SCREEN_VERSION)
    same_ = (old['valid_land_cell_count'] == new['valid_land_cell_count'] and old['unknown_cell_count'] == new['unknown_cell_count']
             and old['selected_cell_count'] == new['selected_cell_count'] and old['out_of_coverage_cell_count'] == new['out_of_coverage_cell_count'])
    if old['yearly_loss_counts'] is not None:
        same_ &= {k: old['yearly_loss_counts'][k] for k in map(str, range(2021, 2026))} == new['hansen_loss_after_2020']['yearly_cell_counts']
        same_ &= old['periods'] == new['hansen_loss_after_2020']['periods']
    else:
        same_ &= new['hansen_loss_after_2020']['yearly_cell_counts'] is None
    v1_n += 1
    v1_ok += same_
res['v1_crosscheck_on_damaged_data'] = {'compared': v1_n, 'equal': v1_ok,
                                       'note': 'valid land, unknown, selected, outside, 2021-2025 yearly loss and period flags equal frozen v1 evaluate when treecover/lossyear/datamask masks are damaged'}
if v1_ok != v1_n:
    fails.append('v1 cross-check on damaged data')
if ok_n != n:
    fails.append('polygon outputs')
res['fails'] = fails
(OUT / 'v01c.json').write_text(json.dumps(res, indent=1) + '\n')
print(json.dumps(res, indent=1))
sys.exit(1 if fails else 0)
