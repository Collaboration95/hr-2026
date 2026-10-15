"""Claim 6 (+ claim 5 for the registry file): registry v2 / table v2 staleness, integrity and parser bounds.

Updated for: PLDREG2 (sha256 of the header in the prefix), parser bounds before expansion, required `metadata` in
registry_lookup, required `level`, registry_evaluate_store, table `content_sha256` verified by load_table, table_lookup
`grid`. Memory probes use scaled-down sizes (tracemalloc). Exit 1 = a defect was reproduced.
Writes validation/decision/out/v06.json.
"""
import copy
import hashlib
import json
import random
import shutil
import struct
import sys
import tempfile
import tracemalloc
from pathlib import Path

import numpy as np

from _common import ART, OUT
from engine import decision as D
from engine import decision_index as I
from engine import decision_store as S
from engine.source import load_plots, load_source

res, findings = {}, []
hansen = load_source()
meta = hansen.metadata
plots = load_plots()
by = {p['plot_id']: p for p in plots}
stores = {lv: S.read_store(ART / fn) for lv, fn in ((D.SCREEN_VERSION, 'screen.plds'), (D.DECISION_VERSION, 'decision.plds'))}
codes = {lv: v[0] for lv, v in stores.items()}
registry = I.load_registry(ART / 'registry.bin')
table = I.load_table(ART / 'table.json')
rng = random.Random(3)
tmp = Path(tempfile.mkdtemp(dir=OUT, prefix='v06_'))


def refused(label, fn, exc=ValueError, store=None):
    store = res if store is None else store
    try:
        fn()
        store[label] = 'NOT refused'
        findings.append(f'{label} not refused')
    except exc as e:
        store[label] = f'{type(e).__name__}: {str(e)[:70]}'
    except BaseException as e:  # noqa: BLE001
        store[label] = f'WRONG EXCEPTION {type(e).__name__}'
        findings.append(f'{label} raised {type(e).__name__}')


# ---- registry lookups --------------------------------------------------------------------------------------
g = by['P-0001']['geometry']
r = {}
r['genuine_hit'] = I.registry_lookup(registry, 'P-0001', g, meta) is not None
g2 = copy.deepcopy(g)
g2['coordinates'][0][0][0] = float(np.nextafter(g2['coordinates'][0][0][0], 1e9))
g2['coordinates'][0][-1] = list(g2['coordinates'][0][0])
r['one_ulp_vertex_change_misses'] = I.registry_lookup(registry, 'P-0001', g2, meta) is None
g3 = copy.deepcopy(g); g3['coordinates'][0].reverse()
r['reversed_ring_misses'] = I.registry_lookup(registry, 'P-0001', g3, meta) is None
r['key_order_only_still_hits'] = I.registry_lookup(registry, 'P-0001', {'coordinates': g['coordinates'], 'type': g['type']}, meta) is not None
g5 = copy.deepcopy(g); g5['bbox'] = [0, 0, 1, 1]
r['extra_key_misses'] = I.registry_lookup(registry, 'P-0001', g5, meta) is None
r['wrong_plot_id_misses'] = I.registry_lookup(registry, 'P-0003', g, meta) is None
shifted = dict(meta, transform=[meta['transform'][0], 0, meta['transform'][2] + 0.00025, 0, meta['transform'][4], meta['transform'][5]])
r['shifted_grid_misses'] = I.registry_lookup(registry, 'P-0001', g, shifted) is None
r['different_shape_misses'] = I.registry_lookup(registry, 'P-0001', g, dict(meta, shape=[meta['shape'][0] + 1, meta['shape'][1]])) is None
refused('registry_lookup_without_metadata', lambda: I.registry_lookup(registry, 'P-0001', g), TypeError, r)
entry = registry['plots']['P-0001']
refused('registry_evaluate_without_level', lambda: I.registry_evaluate(codes[D.DECISION_VERSION], entry), TypeError, r)
refused('registry_evaluate_smaller_raster', lambda: I.registry_evaluate(codes[D.DECISION_VERSION][:100, :100], entry, D.DECISION_VERSION), ValueError, r)
# a same-shape raster from a different grid: raw API cannot know; the store-aware API must refuse
sp = tmp / 'shifted.plds'
S.write_store(codes[D.DECISION_VERSION], {**meta, 'jrc_chip_sha256': stores[D.DECISION_VERSION][1]['sources']['jrc_chip'], 'transform': shifted['transform']},
              sp, level=D.DECISION_VERSION, encoding='zstd19')
cs, hs = S.read_store(sp)
r['raw_registry_evaluate_other_grid_same_shape'] = {'answers_silently': True, 'differs_from_true': I.registry_evaluate(cs, entry, D.DECISION_VERSION)
                                                    != I.registry_evaluate(codes[D.DECISION_VERSION], entry, D.DECISION_VERSION),
                                                    'verdict': 'raw path trusts the caller (accepted risk)'}
refused('registry_evaluate_store_other_grid_same_shape', lambda: I.registry_evaluate_store(cs, hs, entry), ValueError, r)
res['registry_lookup'] = r

# ---- table -------------------------------------------------------------------------------------------------
t = {}
gh = I.geometry_sha256(g)
sha = dict(table['stores'])
t['genuine_hit_file_basis_no_grid'] = I.table_lookup(table, 'P-0001', gh, sha[D.DECISION_VERSION], D.DECISION_VERSION) is not None
t['genuine_hit_with_header_grid'] = I.table_lookup(table, 'P-0001', gh, sha[D.DECISION_VERSION], D.DECISION_VERSION, grid=stores[D.DECISION_VERSION][1]) is not None
t['shifted_grid_with_file_basis_misses'] = I.table_lookup(table, 'P-0001', gh, sha[D.DECISION_VERSION], D.DECISION_VERSION, grid=shifted) is None
t['wrong_store_sha_misses'] = I.table_lookup(table, 'P-0001', gh, '0' * 64, D.DECISION_VERSION) is None
t['screen_hash_for_decision_level_misses'] = I.table_lookup(table, 'P-0001', gh, sha[D.SCREEN_VERSION], D.DECISION_VERSION) is None
t['one_ulp_geometry_misses'] = I.table_lookup(table, 'P-0001', I.geometry_sha256(g2), sha[D.DECISION_VERSION], D.DECISION_VERSION) is None
# independent recomputation of content_sha256 (own canonicalisation)
body = {k: v for k, v in table.items() if k != 'content_sha256'}
t['content_sha256_independent_recompute_equal'] = hashlib.sha256(json.dumps(body, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()).hexdigest() == table['content_sha256']
fresh = I.build_table(plots, {lv: c for lv, c in codes.items()}, sha, meta, table['store_basis'])
t['shipped_table_equals_fresh_build'] = I.table_to_bytes(fresh) == (ART / 'table.json').read_bytes()
# edits
edited = json.loads(json.dumps(table))
edited['plots']['P-0001']['outputs'][D.DECISION_VERSION]['deforestation_after_2020'].update(present=False, cell_count=0)


def write_tbl(obj, name):
    p = tmp / name
    p.write_bytes(I.table_to_bytes(obj))
    return p


refused('edited_output_stale_hash', lambda: I.load_table(write_tbl(edited, 'a.json')), ValueError, t)
no_hash = {k: v for k, v in table.items() if k != 'content_sha256'}
refused('content_sha256_removed', lambda: I.load_table(write_tbl(no_hash, 'b.json')), ValueError, t)
wrong_sch = dict(table, schema='plotline.decision-table.v1')
refused('old_schema', lambda: I.load_table(write_tbl(wrong_sch, 'c.json')), ValueError, t)
edited_store = json.loads(json.dumps(table)); edited_store['stores'][D.DECISION_VERSION] = forged = '1' * 64
refused('store_sha_edited_stale_hash', lambda: I.load_table(write_tbl(edited_store, 'd.json')), ValueError, t)
edited_grid = json.loads(json.dumps(table)); edited_grid['grid']['transform'][2] += 0.00025
refused('grid_edited_stale_hash', lambda: I.load_table(write_tbl(edited_grid, 'e.json')), ValueError, t)
(tmp / 'f.json').write_bytes(I.table_to_bytes(table)[:-10])
refused('truncated_file', lambda: I.load_table(tmp / 'f.json'), ValueError, t)
(tmp / 'g.json').write_bytes(b'[' * 30000)
refused('deep_nesting', lambda: I.load_table(tmp / 'g.json'), ValueError, t)
(tmp / 'h.json').write_bytes(b'{"schema":"plotline.decision-table.v2","content_sha256":NaN}')
refused('nan_constant', lambda: I.load_table(tmp / 'h.json'), ValueError, t)
(tmp / 'i.json').write_bytes(b'\xff\xfe\x00bad')
refused('bad_utf8', lambda: I.load_table(tmp / 'i.json'), ValueError, t)
for name, payload_ in {'list_root': b'[1,2]', 'number_root': b'5', 'null_root': b'null'}.items():
    (tmp / 'j.json').write_bytes(payload_)
    refused(name, lambda: I.load_table(tmp / 'j.json'), ValueError, t)
# self-consistent edit (recomputed content hash): accepted by design - integrity not authenticity
selfhash = json.loads(json.dumps(edited)); selfhash['content_sha256'] = I.table_digest(selfhash)
lt = I.load_table(write_tbl(selfhash, 'k.json'))
t['edited_output_with_recomputed_content_hash'] = {
    'accepted_by_load_table': True,
    'lookup_value': I.table_lookup(lt, 'P-0001', gh, sha[D.DECISION_VERSION], D.DECISION_VERSION)['deforestation_after_2020']['present'],
    'true_value': True,
    'verdict': 'consistent forgery: the hash detects accidental edits only; pin load_table output to a trusted digest to exclude it'}
# is the table digest recorded anywhere trusted?
recorded = {}
for name in ('stores.json', 'proof-v1.json', 'summary-v1.json', 'benchmark-v1.json', 'cost-v1.json'):
    text = (ART / name).read_text()
    recorded[name] = table['content_sha256'] in text
t['table_content_sha256_recorded_in_artifacts'] = recorded
# raster-bytes basis binds only the cells: needs the live grid
raster_sha = {lv: hashlib.sha256(c.tobytes()).hexdigest() for lv, c in codes.items()}
fb = I.build_table(plots, codes, raster_sha, meta, {lv: 'code-raster-bytes' for lv in codes})
refused('raster_basis_without_grid_raises', lambda: I.table_lookup(fb, 'P-0001', gh, raster_sha[D.DECISION_VERSION], D.DECISION_VERSION), ValueError, t)
t['raster_basis_with_live_grid_hits'] = I.table_lookup(fb, 'P-0001', gh, raster_sha[D.DECISION_VERSION], D.DECISION_VERSION, grid=meta) is not None
t['raster_basis_with_shifted_grid_misses'] = I.table_lookup(fb, 'P-0001', gh, raster_sha[D.DECISION_VERSION], D.DECISION_VERSION, grid=shifted) is None
t['raster_basis_content_sha_verified'] = I.table_digest(fb) == fb['content_sha256']
res['table'] = t

# ---- registry file parser (PLDREG2) -----------------------------------------------------------------------
data = (ART / 'registry.bin').read_bytes()
PB = I.PREFIX_BYTES
Pr = {}
kinds = {}
for i in range(2500):
    b = bytearray(data)
    for _ in range(rng.choice((1, 1, 2, 8))):
        b[rng.randrange(len(b))] ^= 1 << rng.randrange(8)
    try:
        reg2 = I.registry_from_bytes(bytes(b))
        same = (reg2['grid'] == registry['grid'] and set(reg2['plots']) == set(registry['plots'])
                and all(np.array_equal(reg2['plots'][k]['flat_index'], registry['plots'][k]['flat_index'])
                        and reg2['plots'][k]['geometry_sha256'] == registry['plots'][k]['geometry_sha256'] for k in registry['plots'])
                and reg2['selection_rule'] == registry['selection_rule'])
        key = 'accepted_same' if same else 'ACCEPTED_DIFFERENT'
        kinds[key] = kinds.get(key, 0) + 1
        if not same:
            findings.append('registry flip accepted with different content')
    except ValueError:
        kinds['ValueError'] = kinds.get('ValueError', 0) + 1
    except BaseException as e:  # noqa: BLE001
        kinds[type(e).__name__] = kinds.get(type(e).__name__, 0) + 1
        findings.append(f'registry flip fuzz: {type(e).__name__}: {str(e)[:80]}')
for cut in list(range(0, 120)) + [len(data) - 1]:
    try:
        I.registry_from_bytes(data[:cut])
        kinds['trunc_accepted'] = kinds.get('trunc_accepted', 0) + 1
        findings.append(f'registry truncation {cut} accepted')
    except ValueError:
        pass
    except BaseException as e:  # noqa: BLE001
        findings.append(f'registry truncation {cut}: {type(e).__name__}')
Pr['flip_fuzz_2500_and_truncations'] = kinds
Pr['shipped_registry_equals_fresh_build_bytes'] = I.registry_to_bytes(I.build_registry(plots, meta)) == data
Pr['load_then_save_roundtrip_bytes_equal'] = I.registry_to_bytes(registry) == data
if not (Pr['shipped_registry_equals_fresh_build_bytes'] and Pr['load_then_save_roundtrip_bytes_equal']):
    findings.append('shipped registry.bin is stale or not deterministic')
Pr['old_PLDREG1_magic_refused'] = False
try:
    I.registry_from_bytes(b'PLDREG1\n' + data[8:])
except ValueError:
    Pr['old_PLDREG1_magic_refused'] = True


def forge(plots_meta, starts, lengths, grid=None, mutate=None, bad_hash=False):
    """A PLDREG2 file with a CORRECT header sha256 and payload hash (an attacker can always compute them)."""
    payload = np.array(starts, '<i4').tobytes() + np.array(lengths, '<i4').tobytes()
    meta_ = {'schema': I.REGISTRY_SCHEMA, 'selection_rule': 'x', 'grid': grid or I.grid_identity(meta), 'plots': plots_meta,
             'payload_bytes': len(payload), 'payload_sha256': hashlib.sha256(payload).hexdigest()}
    if mutate:
        mutate(meta_)
    header = json.dumps(meta_, sort_keys=True, separators=(',', ':')).encode()  # allow_nan: the forgery may contain NaN
    digest = hashlib.sha256(header).digest()
    if bad_hash:
        digest = bytes(32)
    return I.MAGIC + struct.pack('<I', len(header)) + digest + header + payload


def rec(pid='X', runs=1, sel=1, out=0, geo='0' * 64):
    return {'id': pid, 'geometry_sha256': geo, 'runs': runs, 'selected_count': sel, 'outside_count': out}


def peak(fn):
    tracemalloc.start()
    outcome = 'accepted'
    try:
        fn()
    except ValueError as e:
        outcome = 'ValueError: ' + str(e)[:60]
    except BaseException as e:  # noqa: BLE001
        outcome = type(e).__name__
    cur, pk = tracemalloc.get_traced_memory()
    tracemalloc.stop()
    return outcome, pk


# bound checks with a correct header hash: every one must be ValueError before expansion
cases = {
    'run_length_2^24_grid_4096x4097': (forge([rec(sel=1 << 24)], [0], [1 << 24], grid={'shape': [4096, 4097], 'transform': [1, 0, 0, 0, -1, 0], 'crs': 'EPSG:4326'})),
    'run_length_int32_max': forge([rec(sel=2 ** 31 - 1)], [0], [2 ** 31 - 1]),
    'run_beyond_grid': forge([rec(sel=meta['shape'][0] * meta['shape'][1] + 1)], [0], [meta['shape'][0] * meta['shape'][1] + 1]),
    'start_plus_length_beyond_grid': forge([rec(sel=10)], [meta['shape'][0] * meta['shape'][1] - 5], [10]),
    'negative_start': forge([rec(sel=3)], [-1], [3]),
    'zero_length': forge([rec(sel=0)], [5], [0]),
    'negative_length': forge([rec(sel=1)], [5], [-2]),
    'unsorted_runs': forge([rec(runs=2, sel=4)], [100, 10], [2, 2]),
    'overlapping_runs': forge([rec(runs=2, sel=8)], [10, 12], [5, 5]),
    'adjacent_runs_unmerged': forge([rec(runs=2, sel=4)], [10, 12], [2, 2]),
    'accounting_mismatch': forge([rec(sel=7)], [0], [3]),
    'outside_exceeds_selected': forge([rec(sel=3, out=5)], [0], [3]),
    'runs_total_vs_payload_mismatch': forge([rec(runs=5, sel=5)], [0], [1]),
    'duplicate_plot_ids': forge([rec('A'), rec('A')], [0, 10], [1, 1]),
    'runs_is_bool': forge([rec(runs=True)], [0], [1]),
    'runs_is_float': forge([rec(runs=1.0)], [0], [1]),
    'negative_runs': forge([rec(runs=-1), rec('B', runs=3, sel=3)], [0, 10], [1, 1]),
    'huge_int_runs': forge([rec(runs=10 ** 400)], [0], [1]),
    'grid_shape_bool': forge([rec()], [0], [1], grid={'shape': [True, 5], 'transform': [1, 0, 0, 0, -1, 0], 'crs': 'x'}),
    'grid_cells_2^31': forge([rec()], [0], [1], grid={'shape': [65536, 32768], 'transform': [1, 0, 0, 0, -1, 0], 'crs': 'x'}),
    'grid_transform_huge_int': forge([rec()], [0], [1], grid={'shape': [10, 10], 'transform': [10 ** 400, 0, 0, 0, -1, 0], 'crs': 'x'}),
    'grid_transform_nan': forge([rec()], [0], [1], mutate=lambda m: None, grid={'shape': [10, 10], 'transform': [float('nan'), 0, 0, 0, -1, 0], 'crs': 'x'}),
    'grid_shape_string': forge([rec()], [0], [1], grid={'shape': 'ab', 'transform': [], 'crs': 'x'}),
    'extra_header_key': forge([rec()], [0], [1], mutate=lambda m: m.__setitem__('extra', 1)),
    'plots_not_list': forge([rec()], [0], [1], mutate=lambda m: m.__setitem__('plots', {})),
    'geometry_sha_uppercase': forge([rec(geo='A' * 64)], [0], [1]),
    'old_schema': forge([rec()], [0], [1], mutate=lambda m: m.__setitem__('schema', 'plotline.decision-registry.v1')),
    'stale_header_hash': forge([rec()], [0], [1], bad_hash=True),
}
bounds = {}
for name, blob in cases.items():
    try:
        I.registry_from_bytes(blob)
        bounds[name] = 'accepted'
        findings.append(f'registry bounds: {name} accepted')
    except ValueError:
        bounds[name] = 'ValueError'
    except BaseException as e:  # noqa: BLE001
        bounds[name] = f'NON-ValueError {type(e).__name__}: {str(e)[:60]}'
        findings.append(f'registry bounds: {name} -> {type(e).__name__}')
Pr['forged_with_correct_hashes_must_be_refused'] = bounds
# deep JSON / bad JSON under a correct header hash
for name, raw in {'deep_json': b'[' * 20000 + b']' * 20000, 'not_json': b'\xff\xfe', 'json_list': b'[1]'}.items():
    blob = I.MAGIC + struct.pack('<I', len(raw)) + hashlib.sha256(raw).digest() + raw
    try:
        I.registry_from_bytes(blob)
        Pr[name] = 'accepted'
        findings.append(f'registry {name} accepted')
    except ValueError:
        Pr[name] = 'ValueError'
    except BaseException as e:  # noqa: BLE001
        Pr[name] = f'NON-ValueError {type(e).__name__}'
        findings.append(f'registry {name} -> {type(e).__name__}')

# memory: the largest forgery the bounds still admit, and the aggregate over many plots
mem = {}
cells = 3_000_000
big_grid = {'shape': [1500, 2000], 'transform': [1, 0, 0, 0, -1, 0], 'crs': 'EPSG:4326'}
blob = forge([rec('A', sel=cells)], [0], [cells], grid=big_grid)
out, pk = peak(lambda: I.registry_from_bytes(blob))
mem['one_plot_one_run_3M_cells'] = {'file_bytes': len(blob), 'outcome': out, 'peak_bytes': pk, 'amplification': round(pk / len(blob))}
mem['per_cell_bytes_peak'] = round(pk / cells, 1)
blob2 = forge([rec(f'P{i}', sel=cells) for i in range(20)], [0] * 20, [cells] * 20, grid=big_grid)
out2, pk2 = peak(lambda: I.registry_from_bytes(blob2))
mem['twenty_plots_each_3M_cells'] = {'file_bytes': len(blob2), 'outcome': out2, 'peak_bytes': pk2, 'amplification': round(pk2 / len(blob2))}
mem['extrapolated_cap_per_plot'] = 'MAX_PLOT_CELLS = 10,000,000 cells per plot (about %d MB retained + temporaries per plot); no cap on the sum over plots' % round(10e6 * pk / cells / 1e6)
mem['extrapolated_1000_plots_each_chip_sized_744k'] = {'estimated_peak_gb': round(1000 * 744_732 * 4 / 1e9, 2), 'file_bytes_estimate': 1000 * 230,
                                                       'note': 'well-formed (every plot covers the whole chip); bounded per plot, not in aggregate'}
Pr['memory'] = mem
res['registry_file_parser'] = Pr
res['findings'] = findings
shutil.rmtree(tmp, ignore_errors=True)
(OUT / 'v06.json').write_text(json.dumps(res, indent=1, default=str) + '\n')
print(json.dumps(res, indent=1, default=str))
sys.exit(1 if findings else 0)  # exit 1 = defect reproduced
