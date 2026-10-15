"""Attack the new varint bound (store format v2): _varint_limit(count, total) and the count-first _unvarints.

1. _unvarints round trip on edge values and random streams; random byte streams only raise ValueError.
2. No big index array before the count check: a 16 MB stream of zero bytes with a wrong count must fail with a small peak.
3. The bound must not reject honest data: rasters whose run lengths / event gaps sit exactly on the 7-bit, 14-bit and 21-bit
   varint boundaries (the tightest cases) round-trip through 'rle' and 'split' (forced gaps0 and gaps1).
4. The bound must reject over-long streams: declared size limit+1 is refused before decompression, limit is not.
5. Randomised adversarial search for a legitimate stream that exceeds the bound: 3000 random gap/length sequences with
   sum <= total, compare actual LEB128 size with _varint_limit.
Exit 1 = a defect (honest data rejected, non-ValueError, or a bound violation).
"""
import json, random, sys, tracemalloc
import numpy as np
from compression import zstd
from _common import OUT
from engine import decision_store as S

res, fail = {}, []
rng = random.Random(21)
nrng = np.random.default_rng(21)

# 1. round trip and fuzz
edge = [0, 1, 126, 127, 128, 129, 16382, 16383, 16384, 16385, 2 ** 21 - 1, 2 ** 21, 2 ** 21 + 1, 2 ** 28 - 1]
ok = np.array_equal(S._unvarints(S._varints(edge), len(edge)), np.array(edge))
for _ in range(300):
    v = nrng.integers(0, 2 ** nrng.integers(1, 29), nrng.integers(1, 200))
    ok &= np.array_equal(S._unvarints(S._varints(v), len(v)), v)
res['roundtrip_edge_and_random'] = bool(ok)
if not ok:
    fail.append('varint roundtrip')
kinds = {}
for _ in range(20000):
    raw = bytes(nrng.integers(0, 256, nrng.integers(0, 40), dtype=np.uint8))
    try:
        S._unvarints(raw, int(nrng.integers(0, 45)))
        kinds['accepted'] = kinds.get('accepted', 0) + 1
    except ValueError:
        kinds['ValueError'] = kinds.get('ValueError', 0) + 1
    except BaseException as e:  # noqa: BLE001
        kinds[type(e).__name__] = kinds.get(type(e).__name__, 0) + 1
        fail.append(f'_unvarints {type(e).__name__}')
res['fuzz_20000_random_streams'] = kinds

# 2. count check precedes any index array
for fill, label in ((0, 'zero_bytes_16MB'), (0x80, 'continuation_bytes_16MB')):
    raw = bytes([fill]) * 16_000_000
    tracemalloc.start()
    try:
        S._unvarints(raw, 5)
        out = 'accepted'
    except ValueError:
        out = 'ValueError'
    cur, pk = tracemalloc.get_traced_memory(); tracemalloc.stop()
    res[f'peak_{label}'] = {'outcome': out, 'peak_bytes': pk, 'first_pass_would_allocate_about_bytes': 8 * 16_000_000 if fill == 0 else 0}
    if out != 'ValueError' or pk > 40_000_000:
        fail.append(f'unvarints peak {label} {pk}')

# 3. tight honest data
def roundtrip(codes, enc=None, split_mode=None):
    shape = codes.shape
    if split_mode:
        try:
            blob = b''.join(b for _, b in S._split_parts(codes, split_mode))
        except KeyError:
            return 'n/a'
        enc = 'split'
    else:
        blob = S.encode_codes(codes, enc)
    try:
        return bool(np.array_equal(S.decode_codes(blob, shape, enc), codes))
    except ValueError as e:
        return f'REJECTED: {e}'


tight = {}
# rle: runs of exactly L cells alternating two codes (lengths-1 = L-1 sits on a varint boundary)
for L in (128, 129, 16384, 16385, 2 ** 21, 2 ** 21 + 1):
    total = 4096 * 4096 if L >= 2 ** 21 else 129 * 128 * 8
    h, w = (4096, 4096) if L >= 2 ** 21 else (129 * 8, 128)
    flat = (np.arange(h * w) // L) % 2 + 2
    tight[f'rle_run_length_{L}'] = roundtrip(flat.astype(np.uint8).reshape(h, w), 'rle')
# split: loss events spaced so gaps equal 127/128/129 (1 vs 2 bytes) in strip order, forced gaps0 and gaps1
for gap in (127, 128, 129, 16383, 16384, 16385):
    h, w = 512, 256
    size = ((w + 7) // 8) * 8 * h
    flat = np.full(size, 8, np.uint8)  # forest, no loss
    pos = np.arange(gap, size, gap + 1)
    codes_strip = flat.copy()
    codes_strip[pos] = 9
    codes = S._from_strip(codes_strip, (h, w)).astype(np.uint8)
    for mode in ('plane', 'gaps0', 'gaps1'):
        tight[f'split_gap_{gap}_{mode}'] = roundtrip(codes, split_mode=mode)
    tight[f'split_gap_{gap}_auto'] = roundtrip(codes, 'split')
res['tight_honest_data'] = tight
rejected = {k: v for k, v in tight.items() if isinstance(v, str) and v.startswith('REJECTED')}
wrong = {k: v for k, v in tight.items() if v is False}
if rejected or wrong:
    fail.append(f'honest data rejected or wrong: {rejected} {wrong}')

# 4. boundary of the declared size
def blob_with_stream(n, stream_size):
    raw = bytes(stream_size)
    frame = zstd.compress(raw, level=3)
    stream = bytes([S.ZSTD << 4]) + S._varint(len(raw)) + S._varint(len(frame)) + frame
    return bytes([1]) + b'\x00' * 4 + S._varint(n) + stream


h, w = 512, 256
size = ((w + 7) // 8) * 8 * h
n = 1000
limit = S._varint_limit(n, size)
msgs = {}
for sz in (limit, limit + 1):
    try:
        S.decode_codes(blob_with_stream(n, sz), (h, w), 'split')
        msgs[sz] = 'accepted'
    except ValueError as e:
        msgs[sz] = str(e)
res['declared_size_boundary'] = {'limit': limit, 'at_limit': msgs[limit], 'limit_plus_1': msgs[limit + 1]}
if 'out of bounds' in msgs[limit] or 'out of bounds' not in msgs[limit + 1]:
    fail.append('size bound boundary behaves unexpectedly')

# 5. random legitimate sequences: actual LEB128 bytes never exceed the bound
viol = 0
worst = 0.0
for _ in range(3000):
    total = rng.choice((1 << 12, 1 << 16, 1 << 20, 1 << 24))
    n = rng.randrange(1, min(total, 60000))
    kind = rng.choice(('boundary128', 'boundary16384', 'random', 'big'))
    if kind == 'boundary128':
        v = np.full(n, 128)
    elif kind == 'boundary16384':
        v = np.full(n, 16384)
    elif kind == 'big':
        v = np.full(n, 2 ** 21)
    else:
        v = nrng.integers(0, 300, n)
    # legit streams have sum(v + 1) <= total (gaps/lengths-1 inside the grid); scale down to respect it
    while int((v + 1).sum()) > total and n > 1:
        n = max(1, n // 2)
        v = v[:n]
    if int((v + 1).sum()) > total:
        continue
    nbytes = len(S._varints(v))
    lim = S._varint_limit(n, total)
    worst = max(worst, nbytes / lim)
    if nbytes > lim:
        viol += 1
res['random_legit_sequences'] = {'violations_of_bound': viol, 'worst_bytes_over_limit': round(worst, 4)}
if viol:
    fail.append('legitimate stream exceeds the bound')
res['fail'] = fail
(OUT / 'v05d.json').write_text(json.dumps(res, indent=1, default=str) + '\n')
print(json.dumps(res, indent=1, default=str))
sys.exit(1 if fail else 0)
