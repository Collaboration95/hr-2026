"""Separate single-binary-band stores with exact raw values and validity bits."""
from compression import zstd
import hashlib
import json
from pathlib import Path
import struct
import time

import numpy as np
from .codecs import (_canonical, _hash, _integer, _metadata, _layout, _pairs,
                     _invalid_constant, _digest, _decompress, _unpack_bits)
from .jrc import JrcDataset

CANDIDATES = ('binary_packed_zstd3', 'binary_byte_zstd3', 'binary_packed_zstd19', 'binary_byte_zstd19')
LEVELS = {name: 19 if name.endswith('19') else 3 for name in CANDIDATES}
HEADER = struct.pack('<8sI', b'JRCBIN1\0', 1)
MAX_INDEX = 8*1024*1024
MAX_PAYLOAD = 64*1024*1024


def packed(candidate):
    return candidate in ('binary_packed_zstd3', 'binary_packed_zstd19')


def raw_size(candidate, n):
    return ((n+7)//8 if packed(candidate) else n) + (n+7)//8


def encode_jrc_store(dataset, path, candidate='binary_packed_zstd19', chunk_size=1024):
    start = time.perf_counter()
    if type(candidate) is not str or candidate not in CANDIDATES:
        raise ValueError('unknown JRC candidate')
    h, w = _metadata(dataset.metadata)
    dataset.validate()
    size = _integer(chunk_size, 'JRC chunk_size', 1, 2048)
    layout = _layout(h, w, size)
    path = Path(path)
    if path.is_symlink(): raise ValueError('symlink store directory')
    if path.exists() and any(p.name not in ('index.json', 'payload.bin') or not p.is_file() or p.is_symlink() for p in path.iterdir()):
        raise ValueError('JRC store contains unrelated files')
    if len(_canonical(dataset.metadata)) > MAX_INDEX//2:
        raise ValueError('JRC metadata too large')
    path.mkdir(parents=True, exist_ok=True)
    payload = bytearray(HEADER)
    chunks = []
    for i, (row, col, ch, cw) in enumerate(layout):
        values = dataset.values[row:row+ch, col:col+cw].reshape(-1)
        mask = dataset.mask[row:row+ch, col:col+cw].reshape(-1)
        raw = (np.packbits(values, bitorder='little').tobytes() if packed(candidate) else values.tobytes())
        raw += np.packbits(mask, bitorder='little').tobytes()
        compressed = zstd.compress(raw, level=LEVELS[candidate])
        chunks.append({'index': i, 'row': row, 'col': col, 'height': ch, 'width': cw,
                       'offset': len(payload), 'size': len(compressed), 'raw_size': len(raw),
                       'sha256': _hash(compressed), 'raw_sha256': _hash(raw)})
        payload.extend(compressed)
    if len(payload) > MAX_PAYLOAD: raise ValueError('JRC payload too large')
    index = {'format': 'plotline.jrc-codec.v1', 'version': 1, 'candidate': candidate,
             'compression_level': LEVELS[candidate], 'metadata': dataset.metadata,
             'chunk_size': size, 'chunks': chunks, 'payload_bytes': len(payload), 'payload_sha256': _hash(payload)}
    index['index_sha256'] = _hash(_canonical(index))
    index_bytes = _canonical(index)
    if len(index_bytes) > MAX_INDEX: raise ValueError('JRC index too large')
    # Dedicated directories; no concurrent replacement guarantee.
    (path / 'payload.bin').write_bytes(payload)
    (path / 'index.json').write_bytes(index_bytes)
    return {'candidate': candidate, 'chunk_size': size, 'compression_level': LEVELS[candidate],
            'payload_bytes': len(payload), 'metadata_index_bytes': len(index_bytes),
            'total_bytes': len(payload)+len(index_bytes), 'encode_ms': (time.perf_counter()-start)*1000,
            'files': [{'path': 'payload.bin', 'bytes': len(payload), 'sha256': _hash(payload)},
                      {'path': 'index.json', 'bytes': len(index_bytes), 'sha256': _hash(index_bytes)}]}


def read_jrc_index(path):
    path = Path(path)
    if path.is_symlink() or (path / 'index.json').is_symlink(): raise ValueError('symlink JRC index')
    try:
        with (path / 'index.json').open('rb') as stream:
            raw = stream.read(MAX_INDEX+1)
        if len(raw) > MAX_INDEX: raise ValueError('JRC index too large')
        x = json.loads(raw, object_pairs_hook=_pairs, parse_constant=_invalid_constant)
        if type(x) is not dict: raise ValueError('JRC index must be object')
        if _hash(_canonical({k: v for k, v in x.items() if k != 'index_sha256'})) != _digest(x.get('index_sha256')):
            raise ValueError('JRC index checksum mismatch')
        if x.get('format') != 'plotline.jrc-codec.v1' or type(x.get('version')) is not int or x['version'] != 1:
            raise ValueError('JRC format/version mismatch')
        candidate = x.get('candidate')
        if type(candidate) is not str or candidate not in CANDIDATES: raise ValueError('unknown JRC candidate')
        if type(x.get('compression_level')) is not int or x['compression_level'] != LEVELS[candidate]:
            raise ValueError('JRC candidate/level mismatch')
        h, w = _metadata(x.get('metadata'))
        size = _integer(x.get('chunk_size'), 'JRC chunk_size', 1, 2048)
        layout = _layout(h, w, size)
        chunks = x.get('chunks')
        if type(chunks) is not list or len(chunks) != len(layout): raise ValueError('JRC chunk count mismatch')
        offset = len(HEADER)
        for i, (item, (r, c, ch, cw)) in enumerate(zip(chunks, layout)):
            if type(item) is not dict: raise ValueError('JRC chunk must be object')
            for key, expected in [('index', i), ('row', r), ('col', c), ('height', ch), ('width', cw),
                                  ('offset', offset), ('raw_size', raw_size(candidate, ch*cw))]:
                if type(item.get(key)) is not int or item[key] != expected:
                    raise ValueError('JRC illegal chunk '+key)
            n = item['raw_size']
            offset += _integer(item.get('size'), 'JRC compressed size', 1, n+n//128+1024)
            _digest(item.get('sha256')); _digest(item.get('raw_sha256'))
        if offset != _integer(x.get('payload_bytes'), 'JRC payload bytes', len(HEADER), MAX_PAYLOAD):
            raise ValueError('JRC payload/layout size mismatch')
        _digest(x.get('payload_sha256'))
        return x
    except (TypeError, KeyError, RecursionError, OverflowError, UnicodeError) as exc:
        raise ValueError('malformed JRC index') from exc


def decode_jrc_store(path):
    path = Path(path)
    x = read_jrc_index(path)
    h, w = x['metadata']['shape']
    if (path / 'payload.bin').is_symlink(): raise ValueError('symlink JRC payload')
    with (path / 'payload.bin').open('rb') as stream:
        stream.seek(0, 2)
        if stream.tell() != x['payload_bytes']: raise ValueError('JRC truncated/trailing payload')
        stream.seek(0)
        if stream.read(len(HEADER)) != HEADER: raise ValueError('JRC payload magic/version mismatch')
        values, mask = np.empty((h, w), dtype=np.uint8), np.empty((h, w), dtype=bool)
        digest = hashlib.sha256(HEADER)
        for item in x['chunks']:
            data = stream.read(item['size'])
            if _hash(data) != item['sha256']: raise ValueError('JRC compressed checksum mismatch')
            digest.update(data)
            raw = _decompress(data, item['raw_size'])
            if _hash(raw) != item['raw_sha256']: raise ValueError('JRC raw checksum mismatch')
            r, c, ch, cw = (item[k] for k in ('row', 'col', 'height', 'width'))
            n = ch*cw
            boundary = (n+7)//8 if packed(x['candidate']) else n
            v = (_unpack_bits(raw[:boundary], n) if packed(x['candidate'])
                 else np.frombuffer(raw[:boundary], dtype=np.uint8))
            m = _unpack_bits(raw[boundary:], n).astype(bool)
            if np.any(v > 1): raise ValueError('illegal JRC binary raw value')
            values[r:r+ch, c:c+cw], mask[r:r+ch, c:c+cw] = v.reshape(ch, cw), m.reshape(ch, cw)
        if digest.hexdigest() != x['payload_sha256']: raise ValueError('JRC payload checksum mismatch')
    return JrcDataset(values, mask, x['metadata']).validate()
