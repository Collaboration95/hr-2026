"""Deterministic, bounded, lossless chunk stores for the three Hansen bands.

Two files are necessary: index.json and payload.bin. Chunk streams are independent
Zstandard frames. All integers and packed bits are little endian. Checksums detect
accidental corruption; an editable index is not an authenticity mechanism.
"""
from compression import zstd
import hashlib
import json
import math
from pathlib import Path
import struct
import time

import numpy as np

CANDIDATES = ('packed14_zstd', 'uint16_zstd', 'separate_zstd', 'bitplane_zstd',
              'separate_zstd_l9', 'separate_zstd_l19')
SEPARATE_CANDIDATES = ('separate_zstd', 'separate_zstd_l9', 'separate_zstd_l19')
CANDIDATE_LEVELS = {name: (9 if name == 'separate_zstd_l9' else
                         19 if name == 'separate_zstd_l19' else 3)
                    for name in CANDIDATES}
FORMAT = 'plotline.codec.v1'
VERSION = 1
MAGIC = b'PLCODEC1'
HEADER = struct.pack('<8sI', MAGIC, VERSION)
LEVEL = 3
MAX_DIMENSION = 16384
MAX_CELLS = 16_777_216
MAX_CHUNK_SIZE = 1024
MAX_CHUNKS = 65536
MAX_INDEX_BYTES = 16 * 1024 * 1024
MAX_PAYLOAD_BYTES = 128 * 1024 * 1024
MAX_WINDOW_LOG = 23


def _canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'),
                      ensure_ascii=True, allow_nan=False).encode('ascii')


def _hash(data):
    return hashlib.sha256(data).hexdigest()


def _integer(value, label, low, high):
    if type(value) is not int or not low <= value <= high:
        raise ValueError(f'{label} must be an integer in {low}..{high}')
    return value


def _json_types(value, depth=0):
    if depth > 32:
        raise ValueError('metadata nesting exceeds 32 levels')
    if type(value) is dict:
        if any(type(k) is not str for k in value):
            raise ValueError('metadata keys must be strings')
        for item in value.values():
            _json_types(item, depth + 1)
    elif type(value) is list:
        for item in value:
            _json_types(item, depth + 1)
    elif type(value) is float:
        if not math.isfinite(value):
            raise ValueError('metadata floats must be finite')
    elif type(value) not in (str, int, bool, type(None)):
        raise ValueError('metadata must contain JSON-native types')


def _metadata(metadata):
    if type(metadata) is not dict:
        raise ValueError('metadata must be a dictionary')
    _json_types(metadata)
    shape = metadata.get('shape')
    if type(shape) is not list or len(shape) != 2:
        raise ValueError('metadata shape must be [height,width]')
    h, w = [_integer(v, 'dimension', 1, MAX_DIMENSION) for v in shape]
    if h * w > MAX_CELLS:
        raise ValueError('grid exceeds maximum cell count')
    transform = metadata.get('transform')
    if type(transform) is not list or len(transform) != 6:
        raise ValueError('metadata transform must contain six numbers')
    try:
        if any(type(v) not in (int, float) or not math.isfinite(v) for v in transform):
            raise ValueError('transform values must be finite numbers')
        a, b, _, d, e, _ = transform
        determinant = a * e - b * d
        if not math.isfinite(determinant) or determinant == 0:
            raise ValueError('transform must be invertible')
    except OverflowError as exc:
        raise ValueError('transform numbers exceed finite arithmetic bounds') from exc
    if type(metadata.get('crs')) is not str or not metadata['crs']:
        raise ValueError('metadata crs must be a nonempty string')
    return h, w


def _arrays(bands, masks, shape):
    if not isinstance(bands, np.ndarray) or bands.dtype != np.uint8:
        raise ValueError('bands must be raw uint8 integers')
    if bands.shape != (3, *shape):
        raise ValueError('bands must have shape [3,height,width] matching metadata')
    if (not isinstance(masks, np.ndarray) or masks.dtype != np.bool_
            or masks.shape != bands.shape):
        raise ValueError('masks must be bool with the same shape as bands')
    for i, maximum in enumerate((100, 25, 2)):
        if np.any(bands[i] > maximum):
            raise ValueError(f'raw band {i} value outside 0..{maximum}')


def _layout(h, w, size):
    count = ((h + size - 1) // size) * ((w + size - 1) // size)
    if count > MAX_CHUNKS:
        raise ValueError('grid exceeds maximum chunk count')
    return [(r, c, min(size, h-r), min(size, w-c))
            for r in range(0, h, size) for c in range(0, w, size)]


def _stream_sizes(candidate, n):
    if candidate in SEPARATE_CANDIDATES:
        result = {name: n for name in ('treecover2000', 'lossyear', 'datamask')}
    else:
        result = {'values': 2*n if candidate == 'uint16_zstd' else (14*n+7)//8}
    result['masks'] = (3*n+7)//8
    return result


def _pack(bands, masks, candidate):
    flat = bands.reshape(3, -1)
    if candidate in SEPARATE_CANDIDATES:
        values = {name: flat[i].tobytes() for i, name in
                  enumerate(('treecover2000', 'lossyear', 'datamask'))}
    else:
        words = (flat[0].astype(np.uint16) | (flat[1].astype(np.uint16) << 7)
                 | (flat[2].astype(np.uint16) << 12))
        if candidate == 'uint16_zstd':
            raw = words.astype('<u2').tobytes()
        else:
            bits = ((words[:, None] >> np.arange(14, dtype=np.uint16)) & 1)
            if candidate == 'bitplane_zstd':
                bits = bits.T
            raw = np.packbits(bits.reshape(-1), bitorder='little').tobytes()
        values = {'values': raw}
    values['masks'] = np.packbits(masks.reshape(-1), bitorder='little').tobytes()
    return values


def _unpack_bits(data, count):
    # Nonzero unused bits indicate corruption, even if checksums were rewritten.
    if count % 8 and data[-1] >> (count % 8):
        raise ValueError('nonzero packed padding bits')
    return np.unpackbits(np.frombuffer(data, dtype=np.uint8), bitorder='little')[:count]


def _unpack(streams, shape, candidate):
    h, w = shape
    n = h*w
    if candidate in SEPARATE_CANDIDATES:
        bands = np.stack([np.frombuffer(streams[name], dtype=np.uint8).reshape(h, w)
                          for name in ('treecover2000', 'lossyear', 'datamask')])
    else:
        if candidate == 'uint16_zstd':
            words = np.frombuffer(streams['values'], dtype='<u2')
            if np.any(words & 0xc000):
                raise ValueError('nonzero uint16 reserved bits')
        else:
            bits = _unpack_bits(streams['values'], 14*n)
            bits = bits.reshape(14, n).T if candidate == 'bitplane_zstd' else bits.reshape(n, 14)
            words = np.sum(bits.astype(np.uint16) << np.arange(14, dtype=np.uint16),
                           axis=1, dtype=np.uint16)
        bands = np.stack([words & 127, (words >> 7) & 31, (words >> 12) & 3])
        bands = bands.astype(np.uint8).reshape(3, h, w)
    masks = _unpack_bits(streams['masks'], 3*n).astype(bool).reshape(3, h, w)
    _arrays(bands, masks, (h, w))
    return bands, masks


def encode_store(bands: np.ndarray, masks: np.ndarray, metadata: dict,
                 path: Path, candidate: str, chunk_size: int = 128) -> dict:
    """Encode into a dedicated directory; refuse unrelated files/symlinks.

    Repeat writes to an existing two-file store are supported. Concurrent reads
    during a replacement may reject a checksum; concurrent writers unsupported.
    Timing is returned only and is absent from the deterministic stored format.
    """
    started = time.perf_counter()
    if type(candidate) is not str or candidate not in CANDIDATES:
        raise ValueError('unknown codec candidate')
    level = CANDIDATE_LEVELS[candidate]
    shape = _metadata(metadata)
    _arrays(bands, masks, shape)
    size = _integer(chunk_size, 'chunk_size', 1, MAX_CHUNK_SIZE)
    layout = _layout(*shape, size)
    # Validate serializability/size before creating any files.
    if len(_canonical(metadata)) > MAX_INDEX_BYTES // 2:
        raise ValueError('metadata exceeds size limit')
    path = Path(path)
    if path.is_symlink():
        raise ValueError('store directory must not be a symlink')
    if path.exists():
        for child in path.iterdir():
            if child.name not in ('payload.bin', 'index.json') or child.is_symlink() or not child.is_file():
                raise ValueError('store directory contains unrelated files or symlinks')
    else:
        path.mkdir(parents=True)
    payload_tmp = path / '.payload.bin.tmp'
    index_tmp = path / '.index.json.tmp'
    chunks, payload_hash = [], hashlib.sha256(HEADER)
    made_payload_tmp = made_index_tmp = False
    try:
        with payload_tmp.open('xb') as stream:
            made_payload_tmp = True
            stream.write(HEADER)
            for number, (r, c, h, w) in enumerate(layout):
                chunk = {'index': number, 'row': r, 'col': c, 'height': h, 'width': w, 'streams': {}}
                raw_streams = _pack(bands[:, r:r+h, c:c+w], masks[:, r:r+h, c:c+w], candidate)
                for name, raw in raw_streams.items():
                    compressed = zstd.compress(raw, level=level)
                    chunk['streams'][name] = {'offset': stream.tell(), 'size': len(compressed),
                                              'raw_size': len(raw), 'sha256': _hash(compressed),
                                              'raw_sha256': _hash(raw)}
                    stream.write(compressed)
                    payload_hash.update(compressed)
                chunks.append(chunk)
            payload_bytes = stream.tell()
        if payload_bytes > MAX_PAYLOAD_BYTES:
            raise ValueError('payload exceeds size limit')
        index = {'format': FORMAT, 'version': VERSION, 'candidate': candidate,
                 'compression': {'codec': 'zstd', 'level': level}, 'chunk_size': size,
                 'metadata': metadata, 'shape': list(shape), 'chunks': chunks,
                 'payload_bytes': payload_bytes, 'payload_sha256': payload_hash.hexdigest()}
        index['index_sha256'] = _hash(_canonical(index))
        encoded_index = _canonical(index)
        if len(encoded_index) > MAX_INDEX_BYTES:
            raise ValueError('index exceeds size limit')
        with index_tmp.open('xb') as stream:
            made_index_tmp = True
            stream.write(encoded_index)
        payload_tmp.replace(path / 'payload.bin')
        index_tmp.replace(path / 'index.json')
    finally:
        if made_payload_tmp:
            payload_tmp.unlink(missing_ok=True)
        if made_index_tmp:
            index_tmp.unlink(missing_ok=True)
    files = [{'path': 'index.json', 'bytes': len(encoded_index)},
             {'path': 'payload.bin', 'bytes': payload_bytes}]
    return {'candidate': candidate, 'total_bytes': payload_bytes + len(encoded_index),
            'payload_bytes': payload_bytes, 'metadata_index_bytes': len(encoded_index),
            'encode_ms': (time.perf_counter()-started)*1000, 'chunk_size': size,
            'compression_level': level, 'files': files}


def _pairs(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError('duplicate JSON key')
        result[key] = value
    return result


def _invalid_constant(value):
    raise ValueError(f'invalid JSON constant: {value}')


def _digest(value):
    if (type(value) is not str or len(value) != 64
            or any(c not in '0123456789abcdef' for c in value)):
        raise ValueError('invalid SHA256 digest')
    return value


def _read_index(path):
    index_path = path / 'index.json'
    if path.is_symlink() or index_path.is_symlink() or not index_path.is_file():
        raise ValueError('store/index must be regular local files')
    with index_path.open('rb') as stream:
        raw = stream.read(MAX_INDEX_BYTES + 1)
    if len(raw) > MAX_INDEX_BYTES:
        raise ValueError('index exceeds size limit')
    try:
        index = json.loads(raw, object_pairs_hook=_pairs, parse_constant=_invalid_constant)
        if type(index) is not dict:
            raise ValueError('index must be a JSON object')
        digest = _digest(index.get('index_sha256'))
        unsigned = {k: v for k, v in index.items() if k != 'index_sha256'}
        if _hash(_canonical(unsigned)) != digest:
            raise ValueError('index checksum mismatch')
        if index.get('format') != FORMAT or type(index.get('version')) is not int or index['version'] != VERSION:
            raise ValueError('unsupported format/version')
        candidate = index.get('candidate')
        if type(candidate) is not str or candidate not in CANDIDATES:
            raise ValueError('unknown codec candidate')
        settings = index.get('compression')
        if (type(settings) is not dict or type(settings.get('level')) is not int
                or settings != {'codec': 'zstd', 'level': CANDIDATE_LEVELS[candidate]}):
            raise ValueError('unsupported/mismatched candidate compression settings')
        h, w = _metadata(index.get('metadata'))
        shape = index.get('shape')
        if type(shape) is not list or len(shape) != 2 or any(type(v) is not int for v in shape) or shape != [h, w]:
            raise ValueError('index shape differs from metadata')
        size = _integer(index.get('chunk_size'), 'chunk_size', 1, MAX_CHUNK_SIZE)
        layout = _layout(h, w, size)
        chunks = index.get('chunks')
        if type(chunks) is not list or len(chunks) != len(layout):
            raise ValueError('invalid chunk count')
        offset = len(HEADER)
        for number, (chunk, (r, c, ch, cw)) in enumerate(zip(chunks, layout)):
            if type(chunk) is not dict:
                raise ValueError('chunk must be an object')
            for key, expected in [('index', number), ('row', r), ('col', c), ('height', ch), ('width', cw)]:
                if type(chunk.get(key)) is not int or chunk[key] != expected:
                    raise ValueError(f'illegal chunk {key}')
            sizes = _stream_sizes(candidate, ch*cw)
            streams = chunk.get('streams')
            if type(streams) is not dict or set(streams) != set(sizes):
                raise ValueError('illegal chunk streams')
            for name, raw_size in sizes.items():
                item = streams[name]
                if type(item) is not dict:
                    raise ValueError('stream must be an object')
                if type(item.get('offset')) is not int or item['offset'] != offset:
                    raise ValueError('stream offsets must be contiguous and nonoverlapping')
                if type(item.get('raw_size')) is not int or item['raw_size'] != raw_size:
                    raise ValueError('illegal stream raw size')
                compressed_size = _integer(item.get('size'), 'stream size', 1, raw_size+raw_size//128+1024)
                _digest(item.get('sha256'))
                _digest(item.get('raw_sha256'))
                offset += compressed_size
        if offset != _integer(index.get('payload_bytes'), 'payload_bytes', len(HEADER), MAX_PAYLOAD_BYTES):
            raise ValueError('payload size differs from stream layout')
        _digest(index.get('payload_sha256'))
        return index
    except (KeyError, TypeError, OverflowError, RecursionError, UnicodeError) as exc:
        raise ValueError('malformed codec index') from exc


def _decompress(data, raw_size):
    """One frame, bounded output and back-reference window; no trailing frames."""
    try:
        # Explicitly check the advertised window as well as the library option.
        # Some small frames decode without allocating their advertised large
        # history, so the library option alone does not always reject them.
        # RFC 8878 sections 3.1.1.1.1 and 3.1.1.1.2 define these two bytes.
        if len(data) < 6 or data[:4] != b'\x28\xb5\x2f\xfd':
            raise ValueError('invalid zstd frame header')
        descriptor = data[4]
        if descriptor & 0x18:
            raise ValueError('unsupported zstd header reserved/unused bits')
        if not descriptor & 0x20:
            window_byte = data[5]
            window_base = 1 << (10 + (window_byte >> 3))
            window_size = window_base + (window_base >> 3)*(window_byte & 7)
            if window_size > 1 << MAX_WINDOW_LOG:
                raise ValueError('zstd advertised window exceeds size limit')
        info = zstd.get_frame_info(data)
        if info.decompressed_size != raw_size or info.dictionary_id != 0:
            raise ValueError('zstd frame content size/dictionary does not match stream')
        decoder = zstd.ZstdDecompressor(options={zstd.DecompressionParameter.window_log_max: MAX_WINDOW_LOG})
        raw = decoder.decompress(data, max_length=raw_size+1)
        while not decoder.eof and not decoder.needs_input and len(raw) <= raw_size:
            more = decoder.decompress(b'', max_length=raw_size+1-len(raw))
            if not more and not decoder.eof:
                raise ValueError('decompression made no progress')
            raw += more
        if len(raw) != raw_size or not decoder.eof or decoder.unused_data:
            raise ValueError('truncated, oversized, or trailing compressed stream')
        return raw
    except zstd.ZstdError as exc:
        raise ValueError('invalid zstd stream') from exc


def _read(path, window):
    path = Path(path)
    index = _read_index(path)
    h, w = index['shape']
    if window is None:
        rs, re, cs, ce = 0, h, 0, w
    else:
        rs, re, cs, ce = window
        rs, re = _integer(rs, 'row_start', 0, h), _integer(re, 'row_stop', 0, h)
        cs, ce = _integer(cs, 'col_start', 0, w), _integer(ce, 'col_stop', 0, w)
        if re <= rs or ce <= cs:
            raise ValueError('window must be nonempty')
    payload_path = path / 'payload.bin'
    if payload_path.is_symlink() or not payload_path.is_file():
        raise ValueError('payload must be a regular local file')
    with payload_path.open('rb') as stream:
        # Check bytes and header before any array allocation.
        stream.seek(0, 2)
        if stream.tell() != index['payload_bytes']:
            raise ValueError('truncated or trailing payload data')
        stream.seek(0)
        if stream.read(len(HEADER)) != HEADER:
            raise ValueError('bad payload magic/version')
        bands = np.empty((3, re-rs, ce-cs), dtype=np.uint8)
        masks = np.empty(bands.shape, dtype=bool)
        payload_hash = hashlib.sha256(HEADER)
        for chunk in index['chunks']:
            r, c, ch, cw = [chunk[k] for k in ('row', 'col', 'height', 'width')]
            if r >= re or r+ch <= rs or c >= ce or c+cw <= cs:
                continue
            raw_streams = {}
            for name in _stream_sizes(index['candidate'], ch*cw):
                item = chunk['streams'][name]
                stream.seek(item['offset'])
                data = stream.read(item['size'])
                if len(data) != item['size'] or _hash(data) != item['sha256']:
                    raise ValueError('compressed stream checksum mismatch/truncation')
                raw = _decompress(data, item['raw_size'])
                if _hash(raw) != item['raw_sha256']:
                    raise ValueError('raw stream checksum mismatch')
                raw_streams[name] = raw
                if window is None:
                    payload_hash.update(data)
            cb, cm = _unpack(raw_streams, (ch, cw), index['candidate'])
            r0, r1, c0, c1 = max(rs, r), min(re, r+ch), max(cs, c), min(ce, c+cw)
            target = (slice(None), slice(r0-rs, r1-rs), slice(c0-cs, c1-cs))
            source = (slice(None), slice(r0-r, r1-r), slice(c0-c, c1-c))
            bands[target], masks[target] = cb[source], cm[source]
        if window is None and payload_hash.hexdigest() != index['payload_sha256']:
            raise ValueError('payload checksum mismatch')
    metadata = index['metadata']
    if window is not None:
        a, b, c, d, e, f = metadata['transform']
        metadata['shape'] = [re-rs, ce-cs]
        metadata['transform'] = [a, b, c+cs*a+rs*b, d, e, f+cs*d+rs*e]
    return bands, masks, metadata


def decode_store(path: Path) -> tuple[np.ndarray, np.ndarray, dict]:
    """Decode/check all chunks and return identical JSON-native metadata."""
    return _read(path, None)


def read_window(path: Path, row_start: int, row_stop: int,
                col_start: int, col_stop: int) -> tuple[np.ndarray, np.ndarray, dict]:
    """Read intersecting chunks only; validate their streams and the full index.

    Integrity of unselected chunks is intentionally not checked. Returned grid
    shape/transform describe the window; other metadata including sources is kept.
    Select query centers on the original global lattice before reading: shifted
    affine arithmetic can change exact boundary membership through rounding.
    """
    return _read(path, (row_start, row_stop, col_start, col_stop))
