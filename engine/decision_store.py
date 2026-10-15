"""Single-file lossless stores for the decision layers (eudr-screen.v1, eudr-decision.v1).

Layout: PLDECID1 | u32 version (2) | u32 header length | u32 CRC32 of the header | canonical
JSON header | payload. The header binds grid, level, encoding, source identities, the payload
hash and a digest of the decoded raster (codes_digest: shape plus row-major cells). Integers
are little endian. Decoders are bounded: every declared count and size is checked against the
header's cell count before anything is allocated, and every stream must end exactly where its
declared size says.

Integrity, not authenticity: the header (CRC32) and the payload (sha256 plus the decoded
raster's sha256) are covered against accidental corruption. A deliberate forgery that
recomputes every hash is out of scope and is caught only if the caller passes expected_sha256,
the whole-file digest from a trusted record.

The read path needs only numpy and the standard library. Derivation, the GeoTIFF
controls and the build import rasterio/shapely lazily inside build_stores.
"""
from compression import zstd
import hashlib
import json
import lzma
import math
from pathlib import Path
import struct
import sys
import time
import zlib

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = 'artifacts/decision'
MAGIC = b'PLDECID1'
VERSION = 2  # 2: CRC32 of the header bytes joins the fixed prefix
PREFIX = struct.Struct('<8sIII')  # magic, version, header length, header CRC32
SCREEN_VERSION, DECISION_VERSION = 'eudr-screen.v1', 'eudr-decision.v1'
LEVELS = (SCREEN_VERSION, DECISION_VERSION)
CODE_COUNT = 20  # mirrors engine.decision.CODE_COUNT; a test pins equality
NO_DECISION_CODES = range(3, 8)  # nonforest land with post-2020 loss; absent from the decision level
ENCODINGS = ('zstd19', 'zstd22', 'xz', 'lzma2', 'rle', 'split')
SOURCE_KEYS = ('hansen_treecover2000', 'hansen_lossyear', 'hansen_datamask', 'jrc_chip')
MAX_DIMENSION = 16384
MAX_CELLS = 16_777_216
MAX_HEADER_BYTES = 64 * 1024
MAX_PAYLOAD_BYTES = 64 * 1024 * 1024
MAX_WINDOW_LOG = 24  # 16 MiB history covers MAX_CELLS
MAX_LZMA_MEMORY = 1 << 27
DECODE_BUDGET_MS = 5.0
STORED, ZSTD, LZMA = 1, 2, 3  # stream methods; 0 marks an all-zero plane
LZMA_SETS = ((0, 0, 0), (1, 0, 0), (2, 0, 0), (3, 0, 0), (4, 0, 0), (0, 0, 2), (3, 0, 2), (4, 0, 3))
HEX = frozenset('0123456789abcdef')


def _canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'),
                      ensure_ascii=True, allow_nan=False).encode('ascii')


def _hash(data):
    return hashlib.sha256(data).hexdigest()


def _digest(value):
    if type(value) is not str or len(value) != 64 or not HEX.issuperset(value):
        raise ValueError('invalid SHA256 digest')
    return value


def codes_digest(codes):
    """sha256 over height and width (little-endian u32) then the row-major cells."""
    codes = np.ascontiguousarray(codes)
    digest = hashlib.sha256(struct.pack('<II', *codes.shape))
    digest.update(codes.data)  # the buffer itself: no copy of the raster
    return digest.hexdigest()


def _finite(value):
    """True for a finite int or float; an int too large for a float (OverflowError) is not finite."""
    try:
        return type(value) in (int, float) and math.isfinite(value)
    except OverflowError:
        return False


def _shape(shape):
    if (not isinstance(shape, (tuple, list)) or len(shape) != 2
            or any(type(v) is not int or not 1 <= v <= MAX_DIMENSION for v in shape)
            or shape[0] * shape[1] > MAX_CELLS):
        raise ValueError(f'shape must be [height,width] within 1..{MAX_DIMENSION}, at most {MAX_CELLS} cells')
    return int(shape[0]), int(shape[1])


def _checked(codes, level=None):
    """Validate a code raster (and the level's code subset when a level is given)."""
    if not isinstance(codes, np.ndarray) or codes.dtype != np.uint8 or codes.ndim != 2:
        raise ValueError('codes must be a uint8 [height,width] array')
    _shape(codes.shape)
    if codes.max() >= CODE_COUNT:
        raise ValueError(f'code outside 0..{CODE_COUNT - 1}')
    if level is not None:
        _level_checked(codes, level)
    return codes


def _level_checked(codes, level):
    if level not in LEVELS:
        raise ValueError('unknown contract level')
    if level == DECISION_VERSION and np.any((codes - np.uint8(NO_DECISION_CODES.start)) < len(NO_DECISION_CODES)):
        raise ValueError('decision level cannot hold nonforest land with loss (codes 3..7)')


# --- byte-level helpers -------------------------------------------------------

def _varint(n):
    out = bytearray()
    while n >= 128:
        out.append(n & 127 | 128)
        n >>= 7
    out.append(n)
    return bytes(out)


def _varints(values):
    """LEB128 for an integer array, vectorised; values must stay below 2**28."""
    v = np.asarray(values, np.uint64)
    if not v.size:
        return b''
    if v.max() >= 1 << 28:
        raise ValueError('varint value exceeds 28 bits')
    lens = 1 + (v >= 1 << 7).astype(np.int64) + (v >= 1 << 14) + (v >= 1 << 21)
    starts = np.cumsum(lens) - lens
    out = np.zeros(int(lens.sum()), np.uint8)
    for k in range(int(lens.max())):
        sel = lens > k
        byte = ((v[sel] >> np.uint64(7 * k)) & np.uint64(127)).astype(np.uint8)
        out[starts[sel] + k] = byte | ((lens[sel] > k + 1).astype(np.uint8) << 7)
    return out.tobytes()


def _varint_limit(count, total):
    """Most bytes `count` LEB128 values of gap or length-1 type can take when their (value + 1) sum is at most
    `total`: one byte each, plus one more per value of 2**7, 2**14 or 2**21 and up (at most total/2**k of those)."""
    return count + total // 128 + total // 16384 + total // 2097152


def _unvarints(raw, count):
    a = np.frombuffer(raw, np.uint8)
    final = a < 128
    if int(np.count_nonzero(final)) != count or (a.size and not final[-1]):  # before any index array exists
        raise ValueError('malformed varint stream')
    if not count:
        return np.zeros(0, np.int64)
    if a.size == count:  # every value is one byte
        return a.astype(np.int64)
    ends = np.flatnonzero(final)
    starts = np.concatenate(([0], ends[:-1] + 1))
    lens = ends - starts + 1
    if lens.max() > 4 or np.any((lens > 1) & (a[ends] == 0)):
        raise ValueError('non-canonical or oversized varint')
    out = np.zeros(count, np.int64)
    for k in range(int(lens.max())):
        sel = lens > k
        out[sel] |= (a[starts[sel] + k].astype(np.int64) & 127) << (7 * k)
    return out


class _Reader:
    def __init__(self, data):
        self.data, self.pos = bytes(data), 0

    def take(self, n):
        if n < 0 or self.pos + n > len(self.data):
            raise ValueError('truncated stream')
        out = self.data[self.pos:self.pos + n]
        self.pos += n
        return out

    def byte(self):
        return self.take(1)[0]

    def varint(self):
        value = 0
        for shift in range(0, 35, 7):
            b = self.byte()
            value |= (b & 127) << shift
            if b < 128:
                if b == 0 and shift:
                    raise ValueError('non-canonical varint')
                return value
        raise ValueError('varint too long')

    def end(self):
        if self.pos != len(self.data):
            raise ValueError('trailing bytes after stream')


# --- compressors --------------------------------------------------------------

def _window_log(n):
    return min(MAX_WINDOW_LOG, max(10, (max(n, 1) - 1).bit_length()))


def _zstd(raw, level):
    options = {zstd.CompressionParameter.compression_level: level,
               zstd.CompressionParameter.window_log: _window_log(len(raw))}
    return zstd.compress(raw, options=options)


def _unzstd(data, size):
    """One frame with the advertised size, bounded output and window, no trailing data."""
    try:
        info = zstd.get_frame_info(data)
        if info.decompressed_size != size or info.dictionary_id:
            raise ValueError('zstd frame size or dictionary does not match the stream')
        decoder = zstd.ZstdDecompressor(options={zstd.DecompressionParameter.window_log_max: MAX_WINDOW_LOG})
        raw = decoder.decompress(data, size + 1)
        while not decoder.eof and not decoder.needs_input and len(raw) <= size:
            more = decoder.decompress(b'', size + 1 - len(raw))
            if not more and not decoder.eof:
                raise ValueError('zstd decompression made no progress')
            raw += more
    except zstd.ZstdError as exc:
        raise ValueError('invalid zstd stream') from exc
    if len(raw) != size or not decoder.eof or decoder.unused_data:
        raise ValueError('truncated, oversized or trailing zstd stream')
    return raw


def _dict_size(n):
    return max(4096, 1 << (max(n, 1) - 1).bit_length())


def _lzma_filters(n, param):
    lc, lp, pb = LZMA_SETS[param]
    return [{'id': lzma.FILTER_LZMA2, 'preset': 9 | lzma.PRESET_EXTREME,
             'lc': lc, 'lp': lp, 'pb': pb, 'dict_size': _dict_size(n)}]


def _lz(raw, param):
    return lzma.compress(raw, format=lzma.FORMAT_RAW, filters=_lzma_filters(len(raw), param))


def _unlz(data, size, param):
    try:
        decoder = lzma.LZMADecompressor(format=lzma.FORMAT_RAW, filters=_lzma_filters(size, param))
        raw = decoder.decompress(data, size + 1)
    except lzma.LZMAError as exc:
        raise ValueError('invalid lzma stream') from exc
    if len(raw) != size or not decoder.eof or decoder.unused_data:
        raise ValueError('truncated, oversized or trailing lzma stream')
    return raw


def _xz(raw):
    filters = [{'id': lzma.FILTER_LZMA2, 'preset': 9 | lzma.PRESET_EXTREME, 'dict_size': _dict_size(len(raw))}]
    return lzma.compress(raw, format=lzma.FORMAT_XZ, check=lzma.CHECK_NONE, filters=filters)


def _unxz(data, size):
    try:
        decoder = lzma.LZMADecompressor(format=lzma.FORMAT_XZ, memlimit=MAX_LZMA_MEMORY)
        raw = decoder.decompress(data, size + 1)
    except lzma.LZMAError as exc:
        raise ValueError('invalid xz stream') from exc
    if len(raw) != size or not decoder.eof or decoder.unused_data:
        raise ValueError('truncated, oversized or trailing xz stream')
    return raw


def _pack_stream(raw, flags=0, explicit=False):
    """Smallest of stored, zstd 22 and tuned raw LZMA2: method byte, [raw size], size, data."""
    options = [(STORED, 0, raw), (ZSTD, 0, _zstd(raw, 22))]
    options += [(LZMA, i, _lz(raw, i)) for i in range(len(LZMA_SETS))]
    comp, param, data = min(options, key=lambda o: len(o[2]))  # first minimum: deterministic ties
    head = bytes([flags << 6 | comp << 4 | param]) + (_varint(len(raw)) if explicit else b'')
    return head + _varint(len(data)) + data


def _get_stream(reader, size=None, empty_ok=False, flags_ok=0, limit=0):
    """Inverse of _pack_stream. size: exact raw size, or None when stored explicitly (at most limit).

    Returns (raw, flags); raw is None for an all-zero plane when empty_ok. Flag bits outside
    flags_ok are rejected.
    """
    method = reader.byte()
    comp, param, flags = (method >> 4) & 3, method & 15, method >> 6
    if comp == 0:
        if method or not empty_ok:
            raise ValueError('invalid stream method')
        return None, 0
    if flags & ~flags_ok:
        raise ValueError('unknown stream flags')
    if size is None:
        size = reader.varint()
        if not 0 < size <= limit:
            raise ValueError('stream size out of bounds')
    data = reader.take(reader.varint())
    if comp == STORED and not param and len(data) == size:
        return data, flags
    if comp == ZSTD and not param:
        return _unzstd(data, size), flags
    if comp == LZMA and param < len(LZMA_SETS):
        return _unlz(data, size, param), flags
    raise ValueError('invalid stream method or size')


# --- bit planes ---------------------------------------------------------------
# Strip order: bands of 8 adjacent columns, then rows top to bottom, then the 8
# columns of the band; one packed byte is one 8-cell row segment. Measured smallest
# of rows/strips/transposed layouts on the real rasters, and a cheap decode.

def _bands(w):
    return -(-w // 8)


def _to_strip(a):
    h, w = a.shape
    p = np.zeros((h, _bands(w) * 8), a.dtype)
    p[:, :w] = a
    return p.reshape(h, -1, 8).transpose(1, 0, 2).reshape(-1)


def _from_strip(flat, shape):
    h, w = shape
    return np.ascontiguousarray(flat.reshape(-1, h, 8).transpose(1, 0, 2).reshape(h, -1)[:, :w])


def _put_plane(bits):
    """Packed strip bytes through the smallest stream; one zero byte marks an empty plane."""
    if not bits.any():
        return b'\x00'
    return _pack_stream(np.packbits(_to_strip(bits.astype(np.uint8))).tobytes())


def _get_plane(reader, shape):
    """A plane as packed strip-order bytes (index band * h + row), or None when all zero."""
    h, w = shape
    raw, _ = _get_stream(reader, _bands(w) * h, empty_ok=True)
    if raw is None:
        return None
    packed = np.frombuffer(raw, np.uint8)
    valid = w - 8 * (_bands(w) - 1)
    if valid < 8 and (packed[-h:] & (0xFF >> valid)).any():  # the last band's unused low bits
        raise ValueError('nonzero padding bits in plane')
    return packed


# A byte's eight cells as 0/1 uint8 lanes of one uint64, first cell in the lowest lane.
_LANES = np.unpackbits(np.arange(256, dtype=np.uint8)[:, None], axis=1).view(np.uint64).reshape(256)


def _set_cells(packed):
    """Strip positions of a packed plane's set cells, ascending."""
    nz = np.flatnonzero(packed != 0)
    bit = np.flatnonzero(np.unpackbits(packed[nz]).view(bool))  # a bool view: nonzero is 4x faster than on uint8
    return bit + ((nz - np.arange(nz.size)) * 8)[bit >> 3]  # index in the unpacked bytes, plus the skipped zero bytes


def _ranked_cells(forest, ufor, count, ranks):
    """Strip positions of the cells at ascending `ranks` among forest | ufor cells (None: empty plane)."""
    cells = np.zeros(-(-count // 8) * 8, np.uint8)
    for plane in (forest, ufor):
        if plane is not None:
            cells[:count] |= plane
    words = cells.view('>u8').astype(np.uint64)  # first cell in the top bit
    counts = np.bitwise_count(words)
    upto = np.cumsum(counts, dtype=np.int64)
    if ranks[-1] >= upto[-1]:
        raise ValueError('event outside eligible cells')
    word = np.searchsorted(upto, ranks, side='right')
    k = ranks - (upto[word] - counts[word])  # rank within the word
    bits, at = words[word], np.zeros(ranks.size, np.int64)
    for width in (32, 16, 8, 4, 2, 1):  # narrow to the k-th set bit from the top
        have = np.bitwise_count(bits >> np.uint64(64 - width))
        past = k >= have
        k -= past * have
        at += past * width
        bits = np.where(past, bits << np.uint64(width), bits)
    return word * 64 + at


# --- encodings ------------------------------------------------------------------

def _split_parts(codes, mode=None):
    """Named sections of the structure-aware encoding; mode forces the event coding (tests).

    A code is unknown (0), water (1) or land 2 + 6 * state + year, state in
    nonforest/forest/unknown and year 0 or 1..5 for 2021..2025. Four bit planes carry
    unknown, water, forest and unknown-forest; post-2020 loss is a sparse event set in
    strip order with one year symbol per event.
    """
    c = codes.astype(np.int16)
    land = c >= 2
    state = np.where(land, (c - 2) // 6, 0)
    year = np.where(land, (c - 2) % 6, 0)
    planes = [('unknown', _put_plane(c == 0)), ('water', _put_plane(c == 1)),
              ('forest', _put_plane(state == 1)), ('unknown_forest', _put_plane(state == 2))]
    pos = np.flatnonzero(_to_strip(year > 0))
    n = int(pos.size)
    years = _to_strip(year)[pos].astype(np.int64) - 1
    options = {'plane': (0, _put_plane(year > 0))}
    eligible = _to_strip(state >= 1)
    for name, flag, ranks in (('gaps0', 1, pos), ('gaps1', 3, np.cumsum(eligible)[pos] - 1)):
        if name == 'gaps1' and not eligible[pos].all():
            continue
        gaps = np.diff(ranks, prepend=-1) - 1
        options[name] = (flag, _varint(n) + (_pack_stream(_varints(gaps), explicit=True) if n else b''))
    choice = min(options, key=lambda k: len(options[k][1])) if mode is None else mode
    flag, events = options[choice]
    parts = [('flags', bytes([flag]))] + planes + [('events', events)]
    if n:
        delta = np.concatenate(([years[0]], np.diff(years) % 5))
        blobs = [_pack_stream(years.astype(np.uint8).tobytes(), 0), _pack_stream(delta.astype(np.uint8).tobytes(), 1)]
        parts.append(('years', min(blobs, key=len)))
    return parts


def _decode_split(blob, shape):
    """Works on the packed strip-order planes (an 8-cell row segment per byte): checks, the code
    raster and the event positions never expand a plane except the dense forest one."""
    h, w = shape
    bands = _bands(w)
    size = bands * 8 * h
    reader = _Reader(blob)
    flag = reader.byte()
    if flag not in (0, 1, 3):
        raise ValueError('unknown split flags')
    unknown, water, forest, ufor = (_get_plane(reader, shape) for _ in range(4))
    zero = np.zeros(bands * h, np.uint8)
    u, wa, f, uf = (zero if p is None else p for p in (unknown, water, forest, ufor))
    if (u & wa).any() or ((f | uf) & (u | wa)).any() or (f & uf).any():
        raise ValueError('inconsistent split planes')
    if flag:
        n = reader.varint()
        if n > h * w:
            raise ValueError('event count exceeds grid')
        pos = np.zeros(0, np.int64)
        if n:
            ranks = np.cumsum(_unvarints(_get_stream(reader, limit=_varint_limit(n, size))[0], n) + 1) - 1
            if flag == 3:
                pos = _ranked_cells(forest, ufor, bands * h, ranks)
            elif ranks[-1] >= size:
                raise ValueError('event outside grid')
            else:
                pos = ranks
    else:
        plane = _get_plane(reader, shape)
        pos = np.zeros(0, np.int64) if plane is None else _set_cells(plane)
        n = int(pos.size)
    # 2 + 6 forest + 12 unknown-forest, less 2 for unknown and 1 for water: one 8-cell lane word per byte
    if forest is None:
        out = np.full(bands * h, 0x0202020202020202, np.uint64)
    else:
        out = np.unpackbits(forest).view(np.uint64)
        out *= np.uint64(6)
        out += np.uint64(0x0202020202020202)
    for plane, scale, apply in ((ufor, 12, np.add), (unknown, 2, np.subtract), (water, 1, np.subtract)):
        if plane is not None:  # sparse: only the nonzero bytes
            nz = np.flatnonzero(plane != 0)
            out[nz] = apply(out[nz], _LANES[plane[nz]] * np.uint64(scale))
    cells = out.view(np.uint8)
    if n:
        raw, flags = _get_stream(reader, n, flags_ok=1)
        years = np.frombuffer(raw, np.uint8)
        if years.max() > 4:
            raise ValueError('year symbol outside 0..4')
        if flags & 1:
            years = (np.cumsum(years.astype(np.int64)) % 5).astype(np.uint8)
        valid = w - 8 * (bands - 1)
        tail = pos[np.searchsorted(pos, size - 8 * h):]  # ascending; only the last band has cells past the width
        base = cells[pos]
        if (valid < 8 and ((tail & 7) >= valid).any()) or (base < 2).any():  # codes 0 and 1 are not land
            raise ValueError('loss event outside land')
        cells[pos] = base + years + 1
    reader.end()
    rows = np.ascontiguousarray(out.reshape(bands, h).T).view(np.uint8).reshape(h, -1)
    return np.ascontiguousarray(rows[:, :w])


def _encode_rle(codes):
    flat = codes.reshape(-1)
    starts = np.concatenate(([0], np.flatnonzero(flat[1:] != flat[:-1]) + 1))
    lengths = np.diff(np.append(starts, flat.size))
    return (_varint(starts.size) + _pack_stream(flat[starts].tobytes())
            + _pack_stream(_varints(lengths - 1), explicit=True))


def _decode_rle(blob, shape):
    reader = _Reader(blob)
    runs = reader.varint()
    if not 0 < runs <= shape[0] * shape[1]:
        raise ValueError('run count out of bounds')
    values = np.frombuffer(_get_stream(reader, runs)[0], np.uint8)
    lengths = _unvarints(_get_stream(reader, limit=_varint_limit(runs, shape[0] * shape[1]))[0], runs) + 1
    reader.end()
    if int(lengths.sum()) != shape[0] * shape[1]:
        raise ValueError('run lengths do not cover the grid')
    return np.repeat(values, lengths)


def _encode_lzma2(codes):
    """Whole raster as raw LZMA2: best of row- or column-major and three tuned settings."""
    options = [(bytes([param | transpose << 4]), _lz((codes.T if transpose else codes).tobytes(), param))
               for transpose in (0, 1) for param in (0, 4, 7)]
    head, data = min(options, key=lambda o: len(o[1]))
    return head + data


def _decode_lzma2(blob, shape):
    if not blob or blob[0] >> 5 or (blob[0] & 15) >= len(LZMA_SETS):
        raise ValueError('invalid lzma2 header')
    transpose = blob[0] >> 4
    raw = _unlz(blob[1:], shape[0] * shape[1], blob[0] & 15)
    a = np.frombuffer(raw, np.uint8)
    return a.reshape(shape[::-1]).T if transpose else a.reshape(shape)


def encode_codes(codes: np.ndarray, encoding: str) -> bytes:
    """Encode a code raster losslessly; every encoding decodes to the identical array."""
    if encoding not in ENCODINGS:
        raise ValueError('unknown encoding')
    codes = _checked(codes)
    raw = np.ascontiguousarray(codes).tobytes()
    if encoding == 'zstd19':
        return _zstd(raw, 19)
    if encoding == 'zstd22':
        return _zstd(raw, 22)
    if encoding == 'xz':
        return _xz(raw)
    if encoding == 'lzma2':
        return _encode_lzma2(codes)
    if encoding == 'rle':
        return _encode_rle(codes)
    return b''.join(blob for _, blob in _split_parts(codes))


def decode_codes(blob: bytes, shape: tuple, encoding: str) -> np.ndarray:
    """Decode to a writable uint8 [height,width] array or raise ValueError."""
    if encoding not in ENCODINGS:
        raise ValueError('unknown encoding')
    h, w = _shape(tuple(shape))
    if not isinstance(blob, (bytes, bytearray, memoryview)) or len(blob) > MAX_PAYLOAD_BYTES:
        raise ValueError('payload must be bytes within the size limit')
    blob = bytes(blob)
    if encoding in ('zstd19', 'zstd22'):
        flat = np.frombuffer(_unzstd(blob, h * w), np.uint8)
    elif encoding == 'xz':
        flat = np.frombuffer(_unxz(blob, h * w), np.uint8)
    elif encoding == 'lzma2':
        flat = _decode_lzma2(blob, (h, w))
    elif encoding == 'rle':
        flat = _decode_rle(blob, (h, w))
    else:
        flat = _decode_split(blob, (h, w))
    codes = flat.reshape(h, w)
    if not (codes.flags.writeable and codes.flags.c_contiguous):
        codes = np.array(codes, order='C')
    if codes.max() >= CODE_COUNT:
        raise ValueError(f'code outside 0..{CODE_COUNT - 1}')
    return codes


# --- store files ------------------------------------------------------------------

def _identity(metadata):
    """sha256 identities of the Hansen chips and the JRC chip; JRC falls back to engine.jrc's pin."""
    found = {f"hansen_{s['band']}": s['sha256'] for s in metadata.get('sources', [])}
    jrc = metadata.get('jrc_chip_sha256')
    if jrc is None:
        from . import jrc as jrc_module
        jrc = jrc_module.PINS[jrc_module.CHIP]
    found['jrc_chip'] = jrc
    if set(found) != set(SOURCE_KEYS):
        raise ValueError('metadata must identify the three Hansen chips')
    return {key: _digest(found[key]) for key in SOURCE_KEYS}


def _grid(metadata, shape):
    if list(metadata.get('shape', [])) != list(shape):
        raise ValueError('metadata shape differs from the code raster')
    transform, crs = metadata.get('transform'), metadata.get('crs')
    if (type(transform) is not list or len(transform) != 6
            or not all(map(_finite, transform)) or type(crs) is not str or not crs):
        raise ValueError('metadata needs a six-number transform and a nonempty crs')
    return {'shape': [int(shape[0]), int(shape[1])], 'transform': list(transform), 'crs': crs}


def _header(codes, metadata, level, encoding, payload):
    return {**_grid(metadata, codes.shape), 'level': level, 'encoding': encoding,
            'sources': _identity(metadata), 'payload_bytes': len(payload),
            'payload_sha256': _hash(payload), 'codes_sha256': codes_digest(codes)}


def _file_bytes(header, payload):
    raw = _canonical(header)
    return PREFIX.pack(MAGIC, VERSION, len(raw), zlib.crc32(raw)) + raw + payload


def write_store(codes, metadata, path, *, level, encoding) -> dict:
    """Write one self-contained store file and return its manifest (header + file facts)."""
    codes = _checked(codes, level)
    payload = encode_codes(codes, encoding)
    header = _header(codes, metadata, level, encoding, payload)
    blob = _file_bytes(header, payload)
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name('.' + path.name + '.tmp')
    try:
        tmp.write_bytes(blob)
        tmp.replace(path)
    finally:
        tmp.unlink(missing_ok=True)
    return {**header, 'header_bytes': len(blob) - len(payload) - PREFIX.size,
            'file_bytes': len(blob), 'file_sha256': _hash(blob)}


def _pairs(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError('duplicate JSON key')
        result[key] = value
    return result


def _invalid_constant(value):
    raise ValueError(f'invalid JSON constant: {value}')


def _parse_header(raw):
    try:
        header = json.loads(raw, object_pairs_hook=_pairs, parse_constant=_invalid_constant)
    except (RecursionError, UnicodeError) as exc:
        raise ValueError('malformed store header') from exc
    keys = {'shape', 'transform', 'crs', 'level', 'encoding', 'sources', 'payload_bytes',
            'payload_sha256', 'codes_sha256'}
    if type(header) is not dict or set(header) != keys:
        raise ValueError('store header must hold exactly the contract fields')
    if header['level'] not in LEVELS or header['encoding'] not in ENCODINGS:
        raise ValueError('unknown store level or encoding')
    header['shape'] = list(_shape(header['shape']))
    sources = header['sources']
    if type(sources) is not dict or set(sources) != set(SOURCE_KEYS):
        raise ValueError('store header must identify every source')
    for value in (*sources.values(), header['payload_sha256'], header['codes_sha256']):
        _digest(value)
    transform = header['transform']
    if (type(transform) is not list or len(transform) != 6
            or not all(map(_finite, transform)) or type(header['crs']) is not str or not header['crs']):
        raise ValueError('store header transform or crs is invalid')
    if type(header['payload_bytes']) is not int or not 0 < header['payload_bytes'] <= MAX_PAYLOAD_BYTES:
        raise ValueError('payload size out of bounds')
    if _canonical(header) != raw:
        raise ValueError('store header is not canonical JSON')
    return header


def read_store(path, *, expected_sha256=None):
    """Validate and decode a store: (codes, header). expected_sha256 is the whole-file digest.

    Rejects a bad magic or version, a header whose CRC32 differs (checked before it is parsed),
    oversized or non-canonical headers, size and payload hash mismatches, a decoded raster that
    differs from the header's shape or hash, codes outside the code space, and, for the decision
    level, nonforest land with loss. Integrity, not authenticity: see the module docstring.
    """
    path = Path(path)
    if path.is_symlink() or not path.is_file():
        raise ValueError('store must be a regular local file')
    with path.open('rb') as stream:
        blob = stream.read(PREFIX.size + MAX_HEADER_BYTES + MAX_PAYLOAD_BYTES + 1)
    if expected_sha256 is not None and _hash(blob) != _digest(expected_sha256):
        raise ValueError('store file hash differs from the expected digest')
    if len(blob) < PREFIX.size:
        raise ValueError('truncated store')
    magic, version, header_bytes, header_crc = PREFIX.unpack_from(blob)
    if magic != MAGIC or version != VERSION:
        raise ValueError('bad store magic or unsupported version')
    if not 2 <= header_bytes <= MAX_HEADER_BYTES or PREFIX.size + header_bytes > len(blob):
        raise ValueError('header length out of bounds or truncated')
    raw = blob[PREFIX.size:PREFIX.size + header_bytes]
    if zlib.crc32(raw) != header_crc:
        raise ValueError('store header checksum mismatch')
    header = _parse_header(raw)
    payload = blob[PREFIX.size + header_bytes:]
    if len(payload) != header['payload_bytes']:
        raise ValueError('truncated or trailing payload data')
    if _hash(payload) != header['payload_sha256']:
        raise ValueError('payload checksum mismatch')
    codes = decode_codes(payload, header['shape'], header['encoding'])
    if codes_digest(codes) != header['codes_sha256']:
        raise ValueError('decoded raster differs from the header hash')
    _level_checked(codes, header['level'])  # decode_codes already holds type, shape and code range
    return codes, header


# --- build -------------------------------------------------------------------------

def _median_ms(function, runs=9):
    function()
    samples = []
    for _ in range(runs):
        started = time.perf_counter()
        function()
        samples.append((time.perf_counter() - started) * 1000)
    return float(np.median(samples))


def _geotiff_controls(codes, metadata):
    """Standard-format controls: never stores, reported even when they beat a custom encoding."""
    import warnings
    from rasterio.io import MemoryFile
    from rasterio.transform import Affine
    h, w = codes.shape
    layouts = (('striped', {'tiled': False}), ('one-strip', {'tiled': False, 'blockysize': h}),
               ('tiled256', {'tiled': True, 'blockxsize': 256, 'blockysize': 256}),
               ('tiled128', {'tiled': True, 'blockxsize': 128, 'blockysize': 128}))
    methods = (('DEFLATE-z9', {'compress': 'deflate', 'zlevel': 9}), ('ZSTD22', {'compress': 'zstd', 'zstd_level': 22}),
               ('LZW', {'compress': 'lzw'}), ('PACKBITS', {'compress': 'packbits'}))
    rows = []
    for method, options in methods:
        for predictor in (None, 2):
            for nbits in (None, 5):
                for layout, blocks in layouts:
                    if predictor and method == 'PACKBITS':
                        continue
                    name = (f"GTiff {method}{'-p2' if predictor else ''} {layout}"
                            + (' NBITS=5' if nbits else ''))
                    profile = {'driver': 'GTiff', 'height': h, 'width': w, 'count': 1, 'dtype': 'uint8',
                               'crs': metadata['crs'], 'transform': Affine(*metadata['transform']),
                               **options, **blocks, **({'predictor': predictor} if predictor else {}),
                               **({'nbits': nbits} if nbits else {})}
                    try:
                        with warnings.catch_warnings():
                            warnings.simplefilter('ignore')
                            with MemoryFile() as memory:
                                with memory.open(**profile) as target:
                                    target.write(codes, 1)
                                data = memory.read()
                            with MemoryFile(data) as memory, memory.open() as source:
                                exact = bool(np.array_equal(source.read(1), codes))
                        rows.append({'name': name, 'bytes': len(data), 'lossless': exact})
                    except Exception as exc:  # GDAL rejects some option combinations
                        rows.append({'name': name, 'bytes': None, 'lossless': None,
                                     'rejected': str(exc).split(': ', 1)[-1][:90]})
    return sorted(rows, key=lambda r: (r['bytes'] is None, r['bytes'] or 0, r['name']))


def _baselines(root):
    sizes = lambda names: {'files': [{'path': n, 'bytes': (root / n).stat().st_size} for n in names]}
    hansen = [f'data/public/hansen_{b}_sample.tif' for b in ('treecover2000', 'lossyear', 'datamask')]
    jrc = 'data/experimental/jrc/JRC_GFC2020_V4_N10_E90_company-bbox.tif'
    contract = [hansen[1], hansen[2], jrc]
    result = {'original_all_layers': sizes(hansen + [jrc]), 'original_contract_inputs': sizes(contract)}
    for entry in result.values():
        entry['bytes'] = sum(f['bytes'] for f in entry['files'])
    benchmark = json.loads((root / 'artifacts/benchmark-v1.json').read_text())
    winner = benchmark['winner']
    result['retained_lossless_l0'] = {'bytes': winner['total_bytes'], 'candidate': winner['candidate'],
                                      'source': 'artifacts/benchmark-v1.json winner.total_bytes'}
    return result


def _compare(store, baselines):
    return {name: {'baseline_bytes': b['bytes'], 'percent_smaller': round(100 * (1 - store / b['bytes']), 3),
                   'ratio': round(b['bytes'] / store, 2)} for name, b in baselines.items()}


def build_stores(root=None) -> dict:
    """Derive both levels from the originals, compare encodings, write the smallest in-budget ones."""
    import rasterio
    from . import decision, jrc, source
    root = ROOT if root is None else Path(root)
    hansen, chip = source.load_source(root), jrc.load_jrc(root)
    metadata = {**hansen.metadata, 'jrc_chip_sha256': chip.metadata['chip_sha256']}
    screen = decision.derive_screen_codes(hansen, chip)
    levels = {decision.SCREEN_VERSION: screen, decision.DECISION_VERSION: decision.project_decision(screen)}
    if tuple(levels) != LEVELS or decision.CODE_COUNT != CODE_COUNT:
        raise ValueError('decision_store constants differ from engine.decision')
    baselines = _baselines(root)
    out = root / OUTPUT
    files = {SCREEN_VERSION: 'screen.plds', DECISION_VERSION: 'decision.plds'}
    record = {'schema': 'plotline.decision-stores.v1', 'format': {'magic': MAGIC.decode(), 'version': VERSION},
              'grid': _grid(metadata, screen.shape), 'sources': _identity(metadata),
              'decode_budget_ms': DECODE_BUDGET_MS, 'baselines': baselines,
              'environment': {'python': sys.version.split()[0], 'numpy': np.__version__,
                              'zstd': zstd.zstd_version, 'rasterio': rasterio.__version__,
                              'gdal': rasterio.__gdal_version__, 'cell_count': int(screen.size)},
              'levels': {}}
    for level, codes in levels.items():
        _checked(codes, level)
        candidates = []
        for encoding in ENCODINGS:
            started = time.perf_counter()
            payload = encode_codes(codes, encoding)
            encode_ms = (time.perf_counter() - started) * 1000
            if not np.array_equal(decode_codes(payload, codes.shape, encoding), codes):
                raise ValueError(f'{encoding} is not lossless at {level}')
            header = _header(codes, metadata, level, encoding, payload)
            candidates.append({'encoding': encoding, 'payload_bytes': len(payload),
                               'file_bytes': len(_file_bytes(header, payload)), 'lossless': True,
                               'decode_ms_median': round(_median_ms(lambda: decode_codes(payload, codes.shape, encoding)), 3),
                               'encode_ms': round(encode_ms, 1)})
        candidates[-1]['sections'] = {name: len(blob) for name, blob in _split_parts(codes)}
        smallest = min(candidates, key=lambda c: c['file_bytes'])
        within = [c for c in candidates if c['decode_ms_median'] <= DECODE_BUDGET_MS]
        chosen = min(within or candidates, key=lambda c: (c['file_bytes'] if within else c['decode_ms_median']))
        reason = (f"smallest encoding ({chosen['encoding']}) decodes in {chosen['decode_ms_median']} ms, within the "
                  f"{DECODE_BUDGET_MS} ms budget" if chosen is smallest else
                  f"smallest encoding ({smallest['encoding']}, {smallest['file_bytes']} B) decodes in "
                  f"{smallest['decode_ms_median']} ms, over the {DECODE_BUDGET_MS} ms budget; chose the smallest within it")
        manifest = write_store(codes, metadata, out / files[level], level=level, encoding=chosen['encoding'])
        back, header = read_store(out / files[level], expected_sha256=manifest['file_sha256'])
        if not np.array_equal(back, codes):
            raise ValueError(f'{level} store read-back differs')
        controls = _geotiff_controls(codes, metadata)
        valid = [c for c in controls if c['bytes'] is not None and c['lossless']]
        record['levels'][level] = {
            'file': f'{OUTPUT}/{files[level]}', 'chosen': chosen['encoding'], 'smallest': smallest['encoding'],
            'reason': reason, 'candidates': candidates, 'controls': controls,
            'best_control': valid[0] if valid else None,
            'store': {k: manifest[k] for k in ('file_bytes', 'header_bytes', 'payload_bytes', 'file_sha256',
                                               'payload_sha256', 'codes_sha256')},
            'code_histogram': np.bincount(codes.reshape(-1), minlength=CODE_COUNT).tolist(),
            'vs_baselines': _compare(manifest['file_bytes'], baselines),
            'vs_baselines_payload_only': _compare(manifest['payload_bytes'], baselines)}
        if valid and valid[0]['bytes'] < manifest['file_bytes']:
            record['levels'][level]['note'] = 'a standard-format control is smaller than the chosen store'
    path = out / 'stores.json'
    path.write_text(json.dumps(record, indent=2, sort_keys=True) + '\n')
    return record


def main():
    record = build_stores()
    print(f"baselines: " + ', '.join(f"{k}={v['bytes']} B" for k, v in record['baselines'].items()))
    for level, entry in record['levels'].items():
        print(f"{level}: chosen={entry['chosen']} smallest={entry['smallest']} file={entry['store']['file_bytes']} B "
              f"payload={entry['store']['payload_bytes']} B")
        for c in sorted(entry['candidates'], key=lambda c: c['file_bytes']):
            print(f"  {c['encoding']:7s} payload={c['payload_bytes']:7d} file={c['file_bytes']:7d} "
                  f"decode={c['decode_ms_median']:7.3f} ms")
        best = entry['best_control']
        print(f"  best control: {best['name']} {best['bytes']} B" if best else '  no valid control')
        for name, v in entry['vs_baselines'].items():
            print(f"  vs {name}: {v['percent_smaller']}% smaller, {v['ratio']}x")
        print(f"  {entry['reason']}")


if __name__ == '__main__':
    main()
