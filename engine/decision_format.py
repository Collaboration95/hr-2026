"""The decision-store file format without numpy: constants, header rules and the bounded stream decoders.

Shared by engine.decision_store (which adds numpy: encoders, raster decoders, write_store/read_store) and
engine.decision_lite (which reads registered cells straight from the packed planes). Importing this module
loads only the standard library. The layout, limits and integrity model are described in
engine.decision_store; every check here is the one read_store has always made, with the same messages.
"""
from compression import zstd
import hashlib
import json
import lzma
import math
import struct

MAGIC = b'PLDECID1'
VERSION = 2  # 2: CRC32 of the header bytes joins the fixed prefix
PREFIX = struct.Struct('<8sIII')  # magic, version, header length, header CRC32
SCREEN_VERSION, DECISION_VERSION = 'eudr-screen.v1', 'eudr-decision.v1'
LEVELS = (SCREEN_VERSION, DECISION_VERSION)
ENCODINGS = ('zstd19', 'zstd22', 'xz', 'lzma2', 'rle', 'split')
SOURCE_KEYS = ('hansen_treecover2000', 'hansen_lossyear', 'hansen_datamask', 'jrc_chip')
MAX_DIMENSION = 16384
MAX_CELLS = 16_777_216
MAX_HEADER_BYTES = 64 * 1024
MAX_PAYLOAD_BYTES = 64 * 1024 * 1024
MAX_WINDOW_LOG = 24  # 16 MiB history covers MAX_CELLS
MAX_LZMA_MEMORY = 1 << 27
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

def _varint(n):
    out = bytearray()
    while n >= 128:
        out.append(n & 127 | 128)
        n >>= 7
    out.append(n)
    return bytes(out)

def _varint_limit(count, total):
    """Most bytes `count` LEB128 values of gap or length-1 type can take when their (value + 1) sum is at most
    `total`: one byte each, plus one more per value of 2**7, 2**14 or 2**21 and up (at most total/2**k of those)."""
    return count + total // 128 + total // 16384 + total // 2097152

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

def _unlz(data, size, param):
    try:
        decoder = lzma.LZMADecompressor(format=lzma.FORMAT_RAW, filters=_lzma_filters(size, param))
        raw = decoder.decompress(data, size + 1)
    except lzma.LZMAError as exc:
        raise ValueError('invalid lzma stream') from exc
    if len(raw) != size or not decoder.eof or decoder.unused_data:
        raise ValueError('truncated, oversized or trailing lzma stream')
    return raw

def _unxz(data, size):
    try:
        decoder = lzma.LZMADecompressor(format=lzma.FORMAT_XZ, memlimit=MAX_LZMA_MEMORY)
        raw = decoder.decompress(data, size + 1)
    except lzma.LZMAError as exc:
        raise ValueError('invalid xz stream') from exc
    if len(raw) != size or not decoder.eof or decoder.unused_data:
        raise ValueError('truncated, oversized or trailing xz stream')
    return raw

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
