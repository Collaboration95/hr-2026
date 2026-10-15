"""Claim 2: is the proof sensitive to bugs in engine.decision, and what is common-mode?

(a) static: imports shared between engine.decision, engine.decision_original and engine.decision_proof.
(b) mutation tests: patch one thing at a time in-process and rerun engine.decision_proof.build_proof with a
    small fuzz; the proof must flip to fail for bugs the independent path can see (M1-M6) and, by design, cannot
    see a bug in the shared selection rule (M7). No artifact is written.
(c) rerun the full proof to a validator-owned path and compare with artifacts/decision/proof-v1.json.
"""
import ast
import json
import subprocess
import sys
from pathlib import Path
from unittest import mock

import numpy as np

from _common import ART, OUT, ROOT

res = {}


def imports(path):
    tree = ast.parse(Path(path).read_text())
    out = set()
    for n in ast.walk(tree):
        if isinstance(n, ast.ImportFrom):
            out.add(('.' * n.level) + (n.module or '') + ':' + ','.join(a.name for a in n.names))
        elif isinstance(n, ast.Import):
            out.update(a.name for a in n.names)
    return sorted(out)


res['imports'] = {m: imports(ROOT / f'engine/{m}.py') for m in ('decision', 'decision_original', 'decision_proof')}

from engine import decision as D, decision_original as O, decision_proof as P, query

FUZZ = 400


def run(label, patches):
    stack = [mock.patch(*a, **k) if isinstance(a, tuple) else a for a, k in patches]
    for s in stack:
        s.start()
    try:
        proof = P.build_proof(ROOT, fuzz_count=FUZZ)
    finally:
        for s in reversed(stack):
            s.stop()
    checks = proof['summary']['checks']
    failed = sorted(k for k, v in checks.items() if not v)
    res.setdefault('mutations', {})[label] = {'all_pass': proof['summary']['all_pass'], 'failed_checks': failed}
    return proof


# baseline sanity
run('M0_no_mutation', [])

# M1: wrong cut-off year in the derivation (engine.decision only)
run('M1_cutoff_21', [(('engine.decision.CUTOFF_LOSSYEAR', 21), {})])

# M2: JRC read one Hansen cell to the right (wrong nesting offset)
orig_off = D.nested_offsets
run('M2_col_offset_plus_1', [(('engine.decision.nested_offsets', lambda a, b: (lambda k, r, c: (k, r, c + 1))(*orig_off(a, b))), {})])

# M3: decision projection forgets too much (also erases forest loss in 2021)
orig_proj = D.project_decision


def bad_proj(codes):
    out = orig_proj(codes)
    out[out == 9] = 8
    return out


run('M3_projection_erases_2021_forest_loss', [(('engine.decision.project_decision', bad_proj), {})])

# M4: reducer treats forest-unknown cells as non-blocking for forest_2020.present
orig_sum = D.summarize_counts


def lax_summary(counts, selected, outside, level=D.SCREEN_VERSION):
    out = orig_sum(counts, selected, outside, level)
    fc = out['forest_2020']['cell_counts']
    if fc and out['forest_2020']['present'] is None and fc['forest'] == 0 and out['unknown_cell_count'] == 0:
        out['forest_2020']['present'] = False
    return out


run('M4_forest_unknown_not_blocking', [(('engine.decision.summarize_counts', lax_summary), {})])

# M5: reducer drops out-of-chip cells from unknown
def no_outside(counts, selected, outside, level=D.SCREEN_VERSION):
    return orig_sum(counts, selected - outside, 0, level)


run('M5_outside_not_counted', [(('engine.decision.summarize_counts', no_outside), {})])

# M6: 'support' complete even with forest-unknown cells
def support_lax(counts, selected, outside, level=D.SCREEN_VERSION):
    out = orig_sum(counts, selected, outside, level)
    if out['support'] == 'partial' and out['unknown_cell_count'] == 0:
        out['support'] = 'complete'
    return out


run('M6_support_ignores_forest_unknown', [(('engine.decision.summarize_counts', support_lax), {})])

# M7: a bug in the SHARED selection rule (strict interior instead of covers): both paths use query.select_cells
import shapely
from shapely.geometry import shape


def select_strict(metadata, geometry):
    # same as query.select_cells but shapely.contains (boundary excluded)
    with mock.patch.object(shapely, 'covers', shapely.contains):
        return _orig_select(metadata, geometry)


_orig_select = query.select_cells
run('M7_shared_selection_uses_contains', [(('engine.query.select_cells', select_strict), {}),
                                           (('engine.decision_original.select_cells', select_strict), {}),
                                           (('engine.decision_proof.select_cells', select_strict), {})])

res['note_M7'] = ('M7 is expected to still pass: selection is a deliberately shared rule, validated outside the proof '
                  '(exact rational ray casting in v01_fidelity.py and the earlier validator).')

# ---- (c) rerun the full proof to a validator-owned path and compare --------------------------------------------------
out = OUT / 'proof-rerun.json'
done = subprocess.run([sys.executable, '-B', '-m', 'engine.decision_proof', '--output', str(out)], cwd=ROOT,
                      capture_output=True, text=True)
res['rerun_exit_code'] = done.returncode
new, old = json.loads(out.read_text()), json.loads((ART / 'proof-v1.json').read_text())


def strip_runtime(p):
    p = json.loads(json.dumps(p))
    p['fuzz'].pop('runtime_seconds', None)
    p.get('environment', None)
    return p


a, b = strip_runtime(new), strip_runtime(old)
diff = [k for k in sorted(set(a) | set(b)) if a.get(k) != b.get(k)]
res['rerun_vs_artifact'] = {'differing_top_level_keys': diff, 'artifact_all_pass': old['summary']['all_pass'], 'rerun_all_pass': new['summary']['all_pass']}
(OUT / 'v02.json').write_text(json.dumps(res, indent=1, default=str) + '\n')
print(json.dumps(res, indent=1, default=str))
