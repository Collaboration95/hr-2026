"""Claim 5 (store decoder robustness, forgery, level binding). Updated for store format v2 and the level-bound APIs.

Sections:
 A  random single/multi byte flips (prefix, header and payload) and truncations of both stores -> only ValueError
 B  header forgeries WITH a correct CRC32 (so the parser, not the CRC, is tested) -> only ValueError;
    the same forgeries with a stale CRC must be rejected too
 C  payload-level fuzz of every encoding via decode_codes (random + truncated + bit-flipped + junk)
 D  memory amplification of crafted tiny payloads (tracemalloc peak, scaled down, extrapolated):
    the first-pass blob (4n zero bytes) and the largest blob the new varint bound still admits (about n bytes)
 E  a consistent forged store (valid CRC and hashes, wrong cells) is accepted: integrity vs authenticity
 F  level binding: store-aware APIs refuse a conflicting level; the raw-raster path still trusts the caller
 G  CRC placement attacks: every header-length value, CRC field edits, v1-layout files, header/payload boundary
Exit 1 = a defect was reproduced. Writes validation/decision/out/v05.json.
"""
import hashlib
import json
import os
import random
import shutil
import struct
import sys
import tempfile
import tracemalloc
import zlib
from pathlib import Path

import numpy as np
from compression import zstd

from _common import ART, OUT
from engine import decision as D
from engine import decision_index as DI
from engine import decision_store as S
from engine.query import select_cells
from engine.source import load_plots, load_source

report, bad = {}, []
rng = random.Random(11)
tmp = Path(tempfile.mkdtemp(prefix='v05_', dir=OUT))
P = S.PREFIX.size  # 20 in format v2


def try_read(blob, name='x.plds'):
    p = tmp / name
    p.write_bytes(blob)
    try:
        codes, header = S.read_store(p)
        return 'accepted', codes, header
    except ValueError as e:
        return 'ValueError', str(e), None
    except BaseException as e:  # noqa: BLE001 - this is the point of the test
        return type(e).__name__, str(e)[:120], None


def parts(fn):
    blob = (ART / fn).read_bytes()
    magic, ver, hl, crc = S.PREFIX.unpack_from(blob)
    return json.loads(blob[P:P + hl]), blob[P + hl:], (ver, hl, crc)


def build(raw_header, payload, crc=None, version=S.VERSION):
    """A v2 file from raw header bytes; crc defaults to the correct CRC32 (an attacker can always compute it)."""
    return S.PREFIX.pack(S.MAGIC, version, len(raw_header), zlib.crc32(raw_header) if crc is None else crc) + raw_header + payload


# ---- A. flips and truncations -------------------------------------------------------------------------------
A = {}
for fn in ('decision.plds', 'screen.plds'):
    blob = (ART / fn).read_bytes()
    base_codes, base_header = S.read_store(ART / fn)
    kinds, accepted_changed = {}, 0
    for i in range(1500):
        b = bytearray(blob)
        for _ in range(rng.choice((1, 1, 1, 2, 4, 16))):
            b[rng.randrange(len(b))] ^= 1 << rng.randrange(8)
        r = try_read(bytes(b))
        kinds[r[0]] = kinds.get(r[0], 0) + 1
        if r[0] == 'accepted' and (not np.array_equal(r[1], base_codes) or r[2] != base_header) and bytes(b) != blob:
            accepted_changed += 1
        if r[0] not in ('ValueError', 'accepted'):
            bad.append(f'A:{fn}:{r}')
    for cut in list(range(0, 200)) + [rng.randrange(200, len(blob)) for _ in range(150)] + [len(blob) - 1]:
        r = try_read(blob[:cut])
        kinds['trunc_' + r[0]] = kinds.get('trunc_' + r[0], 0) + 1
        if r[0] != 'ValueError':
            bad.append(f'A-trunc:{fn}:{cut}:{r}')
    for extra in (b'\x00', b'x' * 1000):
        r = try_read(blob + extra)
        kinds['trailing_' + r[0]] = kinds.get('trailing_' + r[0], 0) + 1
        if r[0] != 'ValueError':
            bad.append(f'A-trailing:{fn}')
    A[fn] = {'outcomes': kinds, 'accepted_with_different_header_or_codes': accepted_changed}
    if accepted_changed:
        bad.append(f'A:{fn}: {accepted_changed} corrupted stores accepted with a different header or codes')
report['A_flips_truncations'] = A

# ---- B. header forgeries (CRC recomputed) ---------------------------------------------------------------------
B = {}
header, payload, _ = parts('decision.plds')
B['control_unmodified_rebuild'] = try_read(build(S._canonical(header), payload))[0]


def forge(name, mutate=None, raw=None):
    if raw is None:
        h = json.loads(json.dumps(header))
        mutate(h)
        try:
            raw = S._canonical(h)
        except Exception as e:
            B[name] = f'build-error {type(e).__name__}'
            return
    r = try_read(build(raw, payload))                    # correct CRC: the parser must refuse
    r2 = try_read(build(raw, payload, crc=zlib.crc32(raw) ^ 1))  # stale CRC: must be refused whatever the content
    B[name] = r[0] if r[0] in ('ValueError', 'accepted') else f'NON-ValueError {r[0]}: {r[1]}'
    if r[0] not in ('ValueError', 'accepted'):
        bad.append(f'B:{name}:{r}')
    if r2[0] != 'ValueError':
        bad.append(f'B:{name}: stale CRC not refused ({r2[0]})')


forge('transform_huge_int_1e400', lambda h: h['transform'].__setitem__(0, 10 ** 400))
forge('transform_huge_negative_int', lambda h: h['transform'].__setitem__(3, -10 ** 320))
forge('transform_bool', lambda h: h['transform'].__setitem__(0, True))
forge('transform_float_overflow_string', lambda h: h['transform'].__setitem__(0, '1e999'))
forge('shape_huge', lambda h: h.__setitem__('shape', [10 ** 30, 1]))
forge('shape_16384x1024', lambda h: h.__setitem__('shape', [16384, 1024]))
forge('shape_zero', lambda h: h.__setitem__('shape', [0, 5]))
forge('shape_float', lambda h: h.__setitem__('shape', [604.0, 1233.0]))
forge('payload_bytes_wrong', lambda h: h.__setitem__('payload_bytes', h['payload_bytes'] + 1))
forge('payload_bytes_huge_int', lambda h: h.__setitem__('payload_bytes', 10 ** 400))
forge('level_unknown', lambda h: h.__setitem__('level', 'eudr-decision.v2'))
forge('encoding_unknown', lambda h: h.__setitem__('encoding', 'zstd3'))
forge('extra_key', lambda h: h.__setitem__('extra', 1))
forge('source_hash_uppercase', lambda h: h['sources'].__setitem__('jrc_chip', h['sources']['jrc_chip'].upper()))
forge('crs_non_string', lambda h: h.__setitem__('crs', 4326))
forge('noncanonical_whitespace', raw=json.dumps(header, sort_keys=True).encode())
forge('deep_nesting_header', raw=b'[' * 20000 + b']' * 20000)
forge('header_utf16', raw='{"a":1}'.encode('utf-16'))
forge('header_not_object', raw=b'[1,2]')
forge('duplicate_key', raw=S._canonical(header)[:-1] + b',"crs":"EPSG:4326"}')
forge('nan_constant', raw=S._canonical(header).replace(b'0.00025', b'NaN', 1))
forge('big_digit_string_5000', raw=S._canonical(header).replace(b'0.00025', b'9' * 5000, 1))
forge('tiny_header_2_bytes', raw=b'{}')
for label, bad_transform in (('write_store_transform_huge_int', [10 ** 400, 0, 98.7, 0, -1e-4, 8.5]), ('write_store_transform_nan', [float('nan'), 0, 98.7, 0, -1e-4, 8.5])):
    try:
        S.write_store(np.zeros((4, 4), np.uint8), {'shape': [4, 4], 'transform': bad_transform, 'crs': 'EPSG:4326', 'sources': [{'band': b, 'sha256': '0' * 64} for b in ('treecover2000', 'lossyear', 'datamask')], 'jrc_chip_sha256': '1' * 64},
                      tmp / 'w.plds', level=D.SCREEN_VERSION, encoding='zstd19')
        B[label] = 'accepted'
        bad.append(f'B:{label} accepted')
    except ValueError:
        B[label] = 'ValueError'
    except BaseException as e:  # noqa: BLE001
        B[label] = f'NON-ValueError {type(e).__name__}'
        bad.append(f'B:{label}:{type(e).__name__}')
report['B_header_forgeries'] = B

# ---- C. payload fuzz per encoding --------------------------------------------------------------------------
base = {lv: S.read_store(ART / fn)[0] for lv, fn in ((D.SCREEN_VERSION, 'screen.plds'), (D.DECISION_VERSION, 'decision.plds'))}
Cres = {}
for level, codes in base.items():
    for enc in S.ENCODINGS:
        payload_e = S.encode_codes(codes, enc)
        kinds, silent = {}, 0
        for i in range(250):
            b = bytearray(payload_e)
            for _ in range(rng.choice((1, 1, 2, 8))):
                b[rng.randrange(len(b))] ^= 1 << rng.randrange(8)
            try:
                out = S.decode_codes(bytes(b), codes.shape, enc)
                kinds['accepted'] = kinds.get('accepted', 0) + 1
                silent += not np.array_equal(out, codes)  # decoder alone accepts different codes; the header hashes catch it
            except ValueError:
                kinds['ValueError'] = kinds.get('ValueError', 0) + 1
            except BaseException as e:  # noqa: BLE001
                kinds[type(e).__name__] = kinds.get(type(e).__name__, 0) + 1
                bad.append(f'C:{level}:{enc}:{type(e).__name__}:{str(e)[:80]}')
        for cut in [0, 1, 2, 5, len(payload_e) // 2, len(payload_e) - 1]:
            try:
                S.decode_codes(payload_e[:cut], codes.shape, enc)
                kinds['trunc_accepted'] = kinds.get('trunc_accepted', 0) + 1
            except ValueError:
                pass
            except BaseException as e:  # noqa: BLE001
                bad.append(f'C-trunc:{level}:{enc}:{cut}:{type(e).__name__}:{str(e)[:80]}')
        for i in range(60):
            junk = os.urandom(rng.randrange(0, 300))
            try:
                S.decode_codes(junk, codes.shape, enc)
                kinds['junk_accepted'] = kinds.get('junk_accepted', 0) + 1
            except ValueError:
                pass
            except BaseException as e:  # noqa: BLE001
                bad.append(f'C-junk:{enc}:{type(e).__name__}:{str(e)[:80]}')
        Cres[f'{level}:{enc}'] = {'outcomes': kinds, 'decoder_accepted_different_codes_before_header_hash_check': silent}
report['C_payload_fuzz'] = Cres


# ---- D. memory amplification of crafted tiny payloads ----------------------------------------------------------
def peak(fn):
    tracemalloc.start()
    outcome = 'accepted'
    try:
        fn()
    except ValueError as e:
        outcome = 'ValueError: ' + str(e)[:50]
    except BaseException as e:  # noqa: BLE001
        outcome = type(e).__name__
    cur, pk = tracemalloc.get_traced_memory()
    tracemalloc.stop()
    return outcome, pk


def crafted_split(stream_bytes, n):
    """split blob (flag 1: gaps) declaring n events whose gap stream is `stream_bytes` zero bytes."""
    raw = bytes(stream_bytes)
    frame = zstd.compress(raw, level=3)
    stream = bytes([S.ZSTD << 4]) + S._varint(len(raw)) + S._varint(len(frame)) + frame
    return bytes([1]) + b'\x00' * 4 + S._varint(n) + stream


D_res = {}
shape = (4096, 4096)
for n in (250_000, 1_000_000, 2_000_000):
    for label, nbytes in (('first_pass_blob_4n_bytes', 4 * n), ('largest_blob_new_bound_admits', n)):
        blob = crafted_split(nbytes, n)
        out, pk = peak(lambda: S.decode_codes(blob, shape, 'split'))
        D_res[f'{label}:n={n}'] = {'file_bytes': len(blob), 'outcome': out, 'peak_bytes': pk, 'amplification': round(pk / len(blob))}
n = 8_000_000  # direct measurement closer to the cap, new bound only
blob = crafted_split(n, n)
out, pk = peak(lambda: S.decode_codes(blob, shape, 'split'))
D_res[f'largest_blob_new_bound_admits:n={n}'] = {'file_bytes': len(blob), 'outcome': out, 'peak_bytes': pk, 'amplification': round(pk / len(blob))}
# an honest dense event store: every land cell has a loss event (what the bound must still admit)
n = 2_000_000
dense = np.full((1414, 1414), 2 + 6 + 1, np.uint8)  # forest + 2021 loss everywhere
blob = S.encode_codes(dense, 'split')
out, pk = peak(lambda: S.decode_codes(blob, dense.shape, 'split'))
D_res['honest_dense_events_1414x1414'] = {'file_bytes': len(blob), 'outcome': out, 'peak_bytes': pk, 'cells': int(dense.size),
                                          'decoded_bytes': int(dense.size)}
# extrapolation to the 16.7M-cell cap from the admitted-bound blob
a2 = D_res['largest_blob_new_bound_admits:n=2000000']['peak_bytes']
a1 = D_res['largest_blob_new_bound_admits:n=1000000']['peak_bytes']
per_event = (a2 - a1) / 1_000_000
a8 = D_res['largest_blob_new_bound_admits:n=8000000']['peak_bytes']
per_event = (a8 - a2) / 6_000_000
D_res['extrapolated_at_MAX_CELLS'] = {'bytes_per_event': round(per_event, 1), 'estimated_peak_mb': round((a8 + per_event * (16_777_216 - 8_000_000)) / 1e6),
                                      'first_pass_estimate_mb': 1093, 'note': 'linear in n; MAX_CELLS bounds n'}
report['D_memory_amplification'] = D_res

# ---- E. consistent forgery: valid CRC and hashes, wrong cells ------------------------------------------------------
hansen = load_source()
meta = {**hansen.metadata, 'jrc_chip_sha256': header['sources']['jrc_chip']}
forged = base[D.DECISION_VERSION].copy()
ep = {p['plot_id']: p for p in load_plots()}
geom = ep['P-0001']['geometry']
rr, cc = select_cells(hansen.metadata, geom)
dc = forged[rr, cc]
idx = np.where((dc >= 9) & (dc <= 13))[0]
forged[rr[idx], cc[idx]] = 8  # erase P-0001's two deforestation events
fpath = tmp / 'forged.plds'
S.write_store(forged, meta, fpath, level=D.DECISION_VERSION, encoding='split')
genuine_sha = hashlib.sha256((ART / 'decision.plds').read_bytes()).hexdigest()
try:
    c, hd = S.read_store(fpath)
    out = D.evaluate_store(c, hd, geom)
    E = {'read_store': 'accepted', 'P-0001 deforestation_after_2020': out['deforestation_after_2020']['cell_count'],
         'present': out['deforestation_after_2020']['present'], 'true_value': 2, 'header_sources_equal_pinned': hd['sources'] == header['sources']}
except ValueError as e:
    E = {'read_store': 'ValueError ' + str(e)}
table = DI.load_table(ART / 'table.json')
forged_sha = hashlib.sha256(fpath.read_bytes()).hexdigest()
E['table_lookup_with_forged_store_hash'] = DI.table_lookup(table, 'P-0001', DI.geometry_sha256(geom), forged_sha, D.DECISION_VERSION)
E['table_lookup_with_genuine_hash'] = DI.table_lookup(table, 'P-0001', DI.geometry_sha256(geom), table['stores'][D.DECISION_VERSION],
                                                      D.DECISION_VERSION)['deforestation_after_2020']['cell_count']
E['proof_records_file_sha'] = json.loads((ART / 'proof-v1.json').read_text())['stores'][D.DECISION_VERSION]['sha256'] == genuine_sha
E['stores_json_records_file_sha'] = json.loads((ART / 'stores.json').read_text())['levels'][D.DECISION_VERSION]['store']['file_sha256'] == genuine_sha
try:
    S.read_store(fpath, expected_sha256=genuine_sha)
    E['expected_sha256_of_genuine_rejects_forgery'] = 'NOT rejected'
    bad.append('E: expected_sha256 did not reject a forged store')
except ValueError as e:
    E['expected_sha256_of_genuine_rejects_forgery'] = 'ValueError: ' + str(e)
report['E_consistent_forgery'] = E

# ---- F. level binding -----------------------------------------------------------------------------------------------
F = {}
p5 = ep['P-0005']['geometry']
stores = {lv: S.read_store(ART / fn) for lv, fn in ((D.SCREEN_VERSION, 'screen.plds'), (D.DECISION_VERSION, 'decision.plds'))}
true_screen = D.evaluate_store(*stores[D.SCREEN_VERSION], p5)
F['P-0005_true_screen_2024_25'] = true_screen['hansen_loss_after_2020']['periods']['2024-2025']


def expect(label, fn, exc):
    try:
        out = fn()
        F[label] = 'NOT refused'
        bad.append(f'F: {label} not refused')
        return out
    except exc as e:
        F[label] = f'{type(e).__name__}: {str(e)[:70]}'
    except BaseException as e:  # noqa: BLE001
        F[label] = f'WRONG EXCEPTION {type(e).__name__}'
        bad.append(f'F: {label} raised {type(e).__name__}')


codes_d, head_d = stores[D.DECISION_VERSION]
codes_s, head_s = stores[D.SCREEN_VERSION]
reg = DI.load_registry(ART / 'registry.bin')
entry5 = reg['plots']['P-0005']
expect('evaluate_store_conflicting_level', lambda: D.evaluate_store(codes_d, head_d, p5, D.SCREEN_VERSION), ValueError)
expect('registry_evaluate_store_conflicting_level', lambda: DI.registry_evaluate_store(codes_d, head_d, entry5, D.SCREEN_VERSION), ValueError)
expect('evaluate_codes_without_level', lambda: D.evaluate_codes(codes_d, hansen.metadata, p5), TypeError)
expect('registry_evaluate_without_level', lambda: DI.registry_evaluate(codes_d, entry5), TypeError)
expect('summarize_counts_without_level', lambda: D.summarize_counts([0] * 20, 0, 0), TypeError)
expect('summarize_selection_without_level', lambda: D.summarize_selection(codes_d, np.array([0]), np.array([0])), TypeError)
expect('evaluate_store_raster_shape_differs', lambda: D.evaluate_store(codes_d[:100, :100], head_d, p5), ValueError)
expect('registry_evaluate_smaller_raster', lambda: DI.registry_evaluate(codes_d[:100, :100], entry5, D.DECISION_VERSION), ValueError)
expect('registry_evaluate_unknown_level', lambda: DI.registry_evaluate(codes_d, entry5, 'eudr-decision.v2'), ValueError)
expect('bind_level_header_without_level', lambda: D.bind_level({}, None), ValueError)
shifted_meta = dict(meta, transform=[meta['transform'][0], 0.0, meta['transform'][2] + 0.00025, 0.0, meta['transform'][4], meta['transform'][5]])
sp = tmp / 'shifted.plds'
S.write_store(codes_d, shifted_meta, sp, level=D.DECISION_VERSION, encoding='zstd19')
c_sh, h_sh = S.read_store(sp)
expect('registry_evaluate_store_shifted_grid_same_shape', lambda: DI.registry_evaluate_store(c_sh, h_sh, entry5), ValueError)
# residual: pair trust and the raw path
wrong = D.evaluate_codes(codes_d, hansen.metadata, p5, D.SCREEN_VERSION)  # caller states the wrong level explicitly
F['raw_path_explicit_wrong_level_still_silent'] = {
    'periods_2024_25': wrong['hansen_loss_after_2020']['periods']['2024-2025'],
    'note': 'by design: evaluate_codes/registry_evaluate trust the caller-supplied level; only the store-aware APIs bind it'}
mismatch_pair = D.evaluate_store(codes_s, head_d, p5)  # screen codes with the decision header: pair is trusted
F['store_aware_pair_swap_silent'] = {'contract': mismatch_pair['contract'], 'note': 'evaluate_store trusts that (codes, header) came from one read_store call'}
report['F_level_binding'] = F

# ---- G. CRC placement attacks -----------------------------------------------------------------------------------------
G = {}
blob = (ART / 'decision.plds').read_bytes()
_, _, hl0, crc0 = S.PREFIX.unpack_from(blob)
# every header-length value (the length field is outside the CRC): only the true length may be accepted
acc = []
for L in range(0, hl0 + 80):
    b = bytearray(blob)
    struct.pack_into('<I', b, 12, L)
    r = try_read(bytes(b))
    if r[0] == 'accepted':
        acc.append(L)
    elif r[0] != 'ValueError':
        bad.append(f'G: header length {L} -> {r[0]}')
G['header_length_values_tried'] = hl0 + 80
G['header_length_values_accepted'] = acc
if acc != [hl0]:
    bad.append(f'G: header length edits accepted: {acc}')
# CRC field edits
crc_acc = [v for v in (0, 0xFFFFFFFF, crc0 ^ 1, crc0 ^ 0x80000000, zlib.adler32(blob[P:P + hl0])) if try_read(blob[:16] + struct.pack('<I', v) + blob[20:])[0] == 'accepted']
G['crc_field_wrong_values_accepted'] = crc_acc
if crc_acc:
    bad.append('G: wrong CRC accepted')
# CRC computed over the wrong span (header+payload, payload only, header minus last byte, prefix included)
spans = {'header_plus_payload': blob[P:], 'payload_only': blob[P + hl0:], 'header_minus_last_byte': blob[P:P + hl0 - 1], 'prefix_and_header': blob[:P + hl0]}
G['crc_over_wrong_span_accepted'] = [k for k, sp_ in spans.items()
                                     if try_read(build(blob[P:P + hl0], blob[P + hl0:], crc=zlib.crc32(sp_)))[0] == 'accepted']
if G['crc_over_wrong_span_accepted']:
    bad.append('G: CRC over a wrong span accepted')
# v1-layout file (magic, version 1, header length, header, payload) and a v2 prefix on a v1 body
v1 = struct.pack('<8sII', S.MAGIC, 1, hl0) + blob[P:]
G['v1_layout_file'] = try_read(v1)[0]
G['v2_version_with_v1_body'] = try_read(struct.pack('<8sIII', S.MAGIC, 2, hl0 + 4, 0) + blob[P - 4 + 4:])[0]
G['version_3'] = try_read(build(blob[P:P + hl0], blob[P + hl0:], version=3))[0]
for k in ('v1_layout_file', 'v2_version_with_v1_body', 'version_3'):
    if G[k] != 'ValueError':
        bad.append(f'G: {k} -> {G[k]}')
# the payload starts where the header ends: moving one byte across the boundary must fail
b = bytearray(blob)
struct.pack_into('<I', b, 12, hl0 + 1)
G['boundary_shift_plus_1'] = try_read(bytes(b))[0]
b2 = bytearray(blob)
struct.pack_into('<I', b2, 12, hl0 - 1)
G['boundary_shift_minus_1'] = try_read(bytes(b2))[0]
# the payload is covered only by header fields: payload edit + matching payload_sha256 edit + correct CRC = consistent forgery
G['note_forgery'] = 'a header edit with a recomputed CRC32 is a consistent forgery (see E); CRC32 is not an authenticator'
report['G_crc_placement'] = G

report['non_valueerror_or_silent_acceptance'] = bad
shutil.rmtree(tmp, ignore_errors=True)
(OUT / 'v05.json').write_text(json.dumps(report, indent=1, default=str) + '\n')
print(json.dumps(report, indent=1, default=str))
print('FINDINGS:', len(bad))
for b_ in bad:
    print('  -', b_)
sys.exit(1 if bad else 0)
