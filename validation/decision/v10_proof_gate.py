"""Fix verification: the proof gate must fail when a store is missing or unreadable (first-pass finding: all_pass stayed true).

Builds validator-owned roots (symlinked data/, own artifacts/decision/) and runs engine.decision_proof.build_proof with a
small fuzz and the CLI:
  A both stores missing        -> all_pass False, store_comparison False, check 'stores_present_and_readable' False
  B only the screen store      -> all_pass False
  C both present (copies)      -> all_pass True, store_comparison True
  D --allow-missing-stores     -> all_pass True but allow_missing_stores recorded and store_comparison False
  E a store with one flipped header bit -> not silently passing (exception or all_pass False)
  F a store whose payload differs but is internally consistent (forged cells) -> exhaustive store check fails
  G CLI exit codes for A, D and C
Exit 1 = the gate can be passed without a verified store.
"""
import json, os, shutil, subprocess, sys, tempfile, zlib
from pathlib import Path
import numpy as np
from _common import ART, OUT, ROOT
from engine import decision as D, decision_proof as P, decision_store as S

tmp = Path(tempfile.mkdtemp(dir=OUT, prefix='v10_'))
res, fail = {}, []


def make_root(name, stores=()):
    root = tmp / name
    (root / 'artifacts/decision').mkdir(parents=True)
    os.symlink(ROOT / 'data', root / 'data')
    for fn in stores:
        shutil.copy(ART / fn, root / 'artifacts/decision' / fn)
    return root


def run(root, **kw):
    try:
        proof = P.build_proof(root, fuzz_count=60, **kw)
    except BaseException as e:  # noqa: BLE001
        return {'exception': f'{type(e).__name__}: {str(e)[:80]}'}
    s = proof['summary']
    return {'all_pass': s['all_pass'], 'store_comparison': s['store_comparison'], 'allow_missing_stores': s.get('allow_missing_stores'),
            'stores_present_and_readable': s['checks']['stores_present_and_readable']}


res['A_no_stores'] = run(make_root('A'))
res['B_screen_only'] = run(make_root('B', ['screen.plds']))
res['C_both_present'] = run(make_root('C', ['screen.plds', 'decision.plds']))
res['D_allow_missing'] = run(make_root('D'), allow_missing_stores=True)
# E: one flipped header bit (CRC mismatch)
root = make_root('E', ['screen.plds', 'decision.plds'])
p = root / 'artifacts/decision/decision.plds'
b = bytearray(p.read_bytes()); b[S.PREFIX.size + 40] ^= 1; p.write_bytes(bytes(b))
res['E_corrupt_header'] = run(root)
# F: forged but self-consistent store (valid CRC and hashes, one deforestation cell erased)
root = make_root('F', ['screen.plds', 'decision.plds'])
codes, header = S.read_store(ART / 'decision.plds')
forged = codes.copy()
idx = np.argwhere((forged >= 9) & (forged <= 13))[0]
forged[idx[0], idx[1]] = 8
S.write_store(forged, {'shape': header['shape'], 'transform': header['transform'], 'crs': header['crs'],
                       'sources': [{'band': k.replace('hansen_', ''), 'sha256': v} for k, v in header['sources'].items() if k.startswith('hansen_')],
                       'jrc_chip_sha256': header['sources']['jrc_chip']}, root / 'artifacts/decision/decision.plds', level=D.DECISION_VERSION, encoding='split')
res['F_forged_consistent_store'] = run(root)
# expectations
if res['A_no_stores'].get('all_pass') is not False or res['A_no_stores'].get('store_comparison'):
    fail.append('A: missing stores pass the gate')
if res['B_screen_only'].get('all_pass') is not False:
    fail.append('B: a missing decision store passes the gate')
if res['C_both_present'].get('all_pass') is not True or not res['C_both_present'].get('store_comparison'):
    fail.append('C: genuine stores do not pass')
if res['D_allow_missing'].get('all_pass') is not True or res['D_allow_missing'].get('store_comparison') or not res['D_allow_missing'].get('allow_missing_stores'):
    fail.append('D: --allow-missing-stores semantics wrong')
if res['E_corrupt_header'].get('all_pass') is True:
    fail.append('E: corrupt store passes the gate')
if res['F_forged_consistent_store'].get('all_pass') is True:
    fail.append('F: a forged consistent store passes the gate')
# CLI exit codes
cli = {}
for name, root_name, extra in (('A_missing', 'A', []), ('D_allow_missing', 'D', ['--allow-missing-stores']), ('C_present', 'C', []), ('E_corrupt', 'E', [])):
    done = subprocess.run([sys.executable, '-B', '-m', 'engine.decision_proof', '--root', str(tmp / root_name), '--output', str(tmp / f'{name}.json'), '--fuzz', '60', *extra],
                          cwd=ROOT, capture_output=True, text=True)
    cli[name] = done.returncode
res['G_cli_exit_codes'] = cli
if cli['A_missing'] == 0 or cli['E_corrupt'] == 0 or cli['C_present'] != 0 or cli['D_allow_missing'] != 0:
    fail.append(f'CLI exit codes: {cli}')
shutil.rmtree(tmp, ignore_errors=True)
res['fail'] = fail
(OUT / 'v10.json').write_text(json.dumps(res, indent=1) + '\n')
print(json.dumps(res, indent=1))
sys.exit(1 if fail else 0)
