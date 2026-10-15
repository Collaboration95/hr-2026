"""Claim 5b (header corruption), re-verified for store format v2 (CRC32 of the header in the prefix).

1. Real read_store on EVERY single-bit flip of the prefix + header of both stores: none may be accepted.
2. Exact algebra: CRC-32 is linear, so a header corruption is undetected iff the XOR of the single-bit syndromes of its
   flipped bits (plus any flipped CRC-field bits) is zero. Enumerate every 1-, 2- and 3-bit pattern over header bits
   plus the 32 CRC-field bits and report the smallest undetected pattern (minimum distance of this code).
3. Real read_store on random 4..64-bit corruptions and on bursts (<=32 bits) of the header.
4. The first-pass targeted edit (one transform digit) must now be refused.
5. Deliberate tampering with a recomputed CRC is accepted (CRC32 is not an authenticator): documented, out of scope.
Exit 1 = a header corruption was accepted.
"""
import json, random, shutil, struct, sys, tempfile, zlib
from pathlib import Path
import numpy as np
from _common import ART, OUT
from engine import decision as D, decision_store as S
from engine.source import load_plots, load_source

tmp = Path(tempfile.mkdtemp(dir=OUT, prefix='v05b_'))
res, fail = {}, []
rng = random.Random(5)
P = S.PREFIX.size


def accepted(blob):
    p = tmp / 'm.plds'
    p.write_bytes(blob)
    try:
        S.read_store(p)
        return True
    except ValueError:
        return False
    except Exception as e:  # noqa: BLE001
        fail.append(f'non-ValueError {type(e).__name__}')
        return False


for fn in ('decision.plds', 'screen.plds'):
    blob = (ART / fn).read_bytes()
    _, _, hl, crc = S.PREFIX.unpack_from(blob)
    span = P + hl  # prefix (incl. magic, version, length, CRC) + header
    one_bit = [(pos, bit) for pos in range(span) for bit in range(8) if accepted(blob[:pos] + bytes([blob[pos] ^ (1 << bit)]) + blob[pos + 1:])]
    # exact algebra over (header bits + 32 CRC-field bits)
    header = blob[P:span]
    nbits = 8 * hl
    base = zlib.crc32(header)
    syn = np.empty(nbits, np.uint32)
    for i in range(nbits):
        b = bytearray(header)
        b[i // 8] ^= 1 << (i % 8)
        syn[i] = zlib.crc32(bytes(b)) ^ base  # syndrome of a single flipped header bit
    crc_bits = np.array([1 << k for k in range(32)], np.uint32)  # a flipped CRC-field bit changes the stored value by that bit
    allsyn = np.concatenate([syn, crc_bits])
    mindist = None
    n1 = int((allsyn == 0).sum())
    # 2-bit undetected iff two syndromes equal; 3-bit iff s_i ^ s_j == s_k (k distinct)
    uniq, counts = np.unique(allsyn, return_counts=True)
    dup2 = int((counts > 1).sum())
    pair = (allsyn[:, None] ^ allsyn[None, :])[np.triu_indices(len(allsyn), 1)]
    s3 = np.isin(pair, allsyn)
    # exclude pairs whose xor equals one of their own members (impossible unless the other is zero)
    triples = int(s3.sum())
    min_weight_syndrome = int(min(bin(int(v)).count('1') for v in syn))
    mindist = 1 if n1 else (2 if dup2 else (3 if triples else '>=4'))
    # random multi-bit and burst corruptions through the real reader
    multi_acc = 0
    trials = 0
    for _ in range(6000):
        k = rng.choice((2, 3, 4, 8, 16, 64))
        b = bytearray(blob)
        for pos in {rng.randrange(span * 8) for _ in range(k)}:
            b[pos // 8] ^= 1 << (pos % 8)
        trials += 1
        if bytes(b) != blob and accepted(bytes(b)):
            multi_acc += 1
    burst_acc = 0
    for _ in range(3000):
        L = rng.randrange(2, 33)
        start = rng.randrange(span * 8 - L)
        pat = rng.getrandbits(L) | 1 | (1 << (L - 1))
        b = bytearray(blob)
        for j in range(L):
            if pat >> j & 1:
                q = start + j
                b[q // 8] ^= 1 << (q % 8)
        if bytes(b) != blob and accepted(bytes(b)):
            burst_acc += 1
    res[fn] = {'prefix_plus_header_bits': 8 * span, 'single_bit_flips_accepted': len(one_bit), 'minimum_distance_of_header_crc_code': mindist,
               'undetected_2bit_patterns': dup2, 'undetected_3bit_patterns': triples, 'min_popcount_of_single_bit_syndrome': min_weight_syndrome,
               'random_multibit_trials': trials, 'random_multibit_accepted': multi_acc, 'bursts_up_to_32_bits': 3000, 'bursts_accepted': burst_acc}
    if one_bit or dup2 or triples or multi_acc or burst_acc:
        fail.append(f'{fn}: header corruption accepted')
# targeted: transform digit edit (first-pass repro)
blob = (ART / 'decision.plds').read_bytes()
assert b'98.77225' in blob
res['targeted_digit_edit_98.77225_to_98.77235_accepted'] = accepted(blob.replace(b'98.77225', b'98.77235', 1))
if res['targeted_digit_edit_98.77225_to_98.77235_accepted']:
    fail.append('targeted digit edit accepted')
# deliberate tampering with the CRC recomputed (out of scope: CRC32 is not an authenticator)
_, _, hl, _ = S.PREFIX.unpack_from(blob)
raw = blob[P:P + hl].replace(b'98.77225', b'98.77235', 1)
forged = S.PREFIX.pack(S.MAGIC, S.VERSION, len(raw), zlib.crc32(raw)) + raw + blob[P + hl:]
p = tmp / 'f.plds'; p.write_bytes(forged)
codes, h2 = S.read_store(p)
geom = next(q for q in load_plots() if q['plot_id'] == 'P-0001')['geometry']
res['deliberate_edit_with_recomputed_crc'] = {'read_store': 'accepted', 'edited_transform_origin': h2['transform'][2],
                                              'P-0001_forest_cells_true_60': D.evaluate_store(codes, h2, geom)['forest_2020']['cell_counts']['forest'],
                                              'note': 'in-scope only if forgery is in the threat model; mitigation is expected_sha256 from a trusted record'}
shutil.rmtree(tmp, ignore_errors=True)
res['fail'] = fail
(OUT / 'v05b.json').write_text(json.dumps(res, indent=1, default=str) + '\n')
print(json.dumps(res, indent=1, default=str))
sys.exit(1 if fail else 0)
