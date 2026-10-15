"""Claim 3: exhaustive semantic check of the tri-state flags against a possible-worlds definition.

For every multiset of up to 3 in-chip cells over all 20 codes, plus 0..2 out-of-chip cells, at both contract
levels, the reported flag must equal the possible-worlds answer: True when every way of resolving the unknown
cells still gives count > 0, False when no resolution gives count > 0, otherwise None. Unknown cells are
Hansen-unknown (code 0) or outside the chip (anything), and forest-unknown land cells (JRC missing: forest or
non-forest, loss year known). The only documented deviation is gating: with no known land cell the reducer
reports None (and support 'none') instead of the possible-worlds answer.
"""
import itertools
import json
import sys

from _common import OUT
from engine import decision as D
from engine import decision_original as O

# a resolved cell is described by (land, forest_cell, deforest_p1, deforest_p2, loss_p1, loss_p2, water)
WATER, NF0, NF1, NF2, F0, F1, F2 = ((0, 0, 0, 0, 0, 0, 1), (1, 0, 0, 0, 0, 0, 0), (1, 0, 0, 0, 1, 0, 0), (1, 0, 0, 0, 0, 1, 0),
                                    (1, 1, 0, 0, 0, 0, 0), (1, 1, 1, 0, 1, 0, 0), (1, 1, 0, 1, 0, 1, 0))
# year index 1..5 = 2021..2025; period 1 = 2021-2023 (idx 1-3), period 2 = 2024-2025 (idx 4-5)


def world_set(code, level, outside=False):
    """Set of cell descriptors consistent with what is known about this cell."""
    if outside or code == 0:
        base = {WATER, NF0, NF1, NF2, F0, F1, F2}
        if level == D.DECISION_VERSION:
            base = {WATER, NF0, F0, F1, F2}
        return base
    if code == 1:
        return {WATER}
    state, y = (code - 2) // 6, (code - 2) % 6
    per = 0 if y == 0 else (1 if y <= 3 else 2)

    def land(forest):
        loss1, loss2 = int(per == 1), int(per == 2)
        if level == D.DECISION_VERSION and not forest:
            loss1 = loss2 = 0
        return (1, int(forest), int(forest) * loss1, int(forest) * loss2, loss1, loss2, 0)
    if state == 0:
        return {land(False)}
    if state == 1:
        return {land(True)}
    return {land(False), land(True)}


def sums(cell_sets):
    acc = {(0,) * 7}
    for s in cell_sets:
        acc = {tuple(a + b for a, b in zip(x, c)) for x in acc for c in s}
    return acc


def classify(values, gate):
    if gate:
        return None
    if all(v > 0 for v in values):
        return True
    if not any(v > 0 for v in values):
        return False
    return None


bad, n, deviations = [], 0, {}
REPS = (0, 1, 2, 3, 6, 8, 9, 12, 14, 15, 18)  # one code per behavioural class (3 and 6 do not exist at the decision level)
SWEEPS = [('all_codes_up_to_3_cells', range(D.CODE_COUNT), 3), ('class_representatives_up_to_6_cells', REPS, 6)]
for sweep, alphabet, kmax in SWEEPS:
  for level in D.LEVELS:
    for k in range(0, kmax + 1):
        for combo in itertools.combinations_with_replacement(alphabet, k):
            if level == D.DECISION_VERSION and any(3 <= c <= 7 for c in combo):
                continue
            for outside in (0, 1, 2):
                counts = [0] * D.CODE_COUNT
                for c in combo:
                    counts[c] += 1
                got = D.summarize_counts(counts, k + outside, outside, level)
                sets = [world_set(c, level) for c in combo] + [world_set(0, level, True) for _ in range(outside)]
                worlds = sums(sets)
                known_land = sum(1 for c in combo if c >= 2)
                gate = known_land == 0
                exp = {'forest': classify([w[1] for w in worlds], gate), 'defo': classify([w[2] + w[3] for w in worlds], gate)}
                if level == D.SCREEN_VERSION:
                    exp['p1'] = classify([w[4] for w in worlds], gate)
                    exp['p2'] = classify([w[5] for w in worlds], gate)
                unknown_cells = sum(1 for c in combo if c == 0) + outside
                fu = sum(1 for c in combo if c >= 14)
                exp_support = 'none' if (k + outside == 0 or gate) else ('partial' if (unknown_cells or fu) else 'complete')
                res = {'forest': got['forest_2020']['present'], 'defo': got['deforestation_after_2020']['present']}
                if level == D.SCREEN_VERSION:
                    pr = got['hansen_loss_after_2020']['periods']
                    res['p1'], res['p2'] = pr['2021-2023']['mapped_loss_present'], pr['2024-2025']['mapped_loss_present']
                n += 1
                if res != exp or got['support'] != exp_support:
                    bad.append({'level': level, 'codes': list(combo), 'outside': outside, 'got': res, 'expected': exp,
                                'support': (got['support'], exp_support)})
                # the independent original-path reducer must agree too (cells described by facts)
                import numpy as np
                attrs = {'hansen': np.array(['unknown' if c == 0 else 'water' if c == 1 else 'land' for c in combo], 'U7'),
                         'forest': np.array(['unknown' if c < 2 or (c - 2) // 6 == 2 else 'nonforest' if (c - 2) // 6 == 0 else 'forest' for c in combo], 'U9'),
                         'loss_year': np.array([0 if c < 2 or (c - 2) % 6 == 0 else 2020 + (c - 2) % 6 for c in combo], np.int16)}
                want = O.reduce_cells(attrs, k + outside, outside, level)
                if want != got:
                    bad.append({'level': level, 'codes': list(combo), 'outside': outside, 'issue': 'original-path reducer differs', 'diff': [kk for kk in want if want[kk] != got.get(kk)]})
                if gate and k + outside > 0 and not unknown_cells and not fu:
                    deviations['water_only_none_vs_possible_worlds_false'] = deviations.get('water_only_none_vs_possible_worlds_false', 0) + 1
res = {'sweeps': [x[0] for x in SWEEPS], 'cases': n, 'violations': len(bad), 'first_violations': bad[:5], 'documented_gating_cases_water_only': deviations}
(OUT / 'v03.json').write_text(json.dumps(res, indent=1) + '\n')
print(json.dumps(res, indent=1))
sys.exit(1 if bad else 0)
