"""Run every validator script in sequence and print its exit code.

Convention: exit 0 = the claim (or the fix) holds; exit 1 = a defect was reproduced. After the 15 Oct fixes every script is expected to exit 0. v07b (35 s of single-core GEOS
on a 100k-vertex polygon) runs only with --heavy.
    .venv-data/bin/python -B validation/decision/run_all.py [--heavy]
"""
import subprocess
import sys
import time
from pathlib import Path

here = Path(__file__).resolve().parent
scripts = ['v01_fidelity.py', 'v01b_axis_float_tile.py', 'v01c_synthetic_unknowns.py', 'v02_independence.py', 'v03_tristate_exhaustive.py',
           'v04_storage_controls.py', 'v04b_ccitt_png.py', 'v05_store_robustness.py', 'v05b_header_unprotected.py', 'v05c_codec_property.py', 'v05d_varint_bounds.py',
           'v06_registry_table.py', 'v07_fast_select.py', 'v08_scale_cost.py', 'v08b_read_timing.py', 'v09_layer_analysis.py', 'v10_proof_gate.py']
if '--heavy' in sys.argv:
    scripts.insert(scripts.index('v08_scale_cost.py'), 'v07b_big_polygons.py')
for name in scripts:
    t = time.time()
    done = subprocess.run([sys.executable, '-B', str(here / name)], cwd=here.parents[1], capture_output=True, text=True)
    print(f'{name:32s} exit={done.returncode} {time.time() - t:5.1f}s')
