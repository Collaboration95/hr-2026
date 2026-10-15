"""Numpy-free re-check of registered plots, straight from the compressed bit-planes of a split store.

Registered plots are re-checked whenever a layer updates. engine.decision_index does that with
read_store (a full 744,732-cell raster) plus a bincount. This module needs only the codes of the
registered cells, so it never imports numpy and never expands the raster: it reads the store's packed
strip-order planes (byte = band * h + row, first cell in the top bit), places the sparse post-2020 loss
events that land on registered bytes, and keeps each plot's codes as one compact bytes object.
Every answer is computed from the current layer at query time (bytes.count, then the shared reducer);
nothing is precomputed from it, so a changed store gives changed answers.

Checked, as read_store does before any decoding: prefix, magic and version, header CRC32, header
parse rules and canonical form, payload size and sha256, optional whole-file sha256. Checked on the
whole payload, not only on registered cells, as _decode_split does: every stream's framing, size and
trailing bytes, plane padding bits, plane consistency, event count and varint canonical form, event
bounds, year symbols, events on non-land cells, and (decision level) nonforest land with loss.
NOT checked: the sha256 of the decoded raster (header codes_sha256), which needs every cell decoded.
Given the payload sha256 the decode is deterministic, so that hash only matters against a forged
header+payload pair; pin the whole-file digest (expected_sha256) to exclude that. Registry: every
check of decision_index._parse_registry. Only the 'split' encoding is supported (LiteUnsupported, a
ValueError, otherwise: fall back to read_store). Integrity, not authenticity.
"""
from array import array
from bisect import bisect_left
import hashlib
from itertools import accumulate
import json
from operator import add
import os
import struct
import zlib

from . import decision_index as di
from .decision_format import (MAX_HEADER_BYTES, MAX_PAYLOAD_BYTES, MAGIC, PREFIX, VERSION, _Reader, _digest, _get_stream,
                              _parse_header, _varint_limit)
from .decision_summary import CODE_COUNT, DECISION_VERSION, summarize_ints


class LiteUnsupported(ValueError):
    """The store is valid but not one this path reads (not split encoded): use read_store."""


# --- store header and streams (the format helpers are shared with decision_store) --------------


def _padding_clear(raw, h, w):
    """False when the last band's unused low bits are set (raw is a packed plane, byte = band * h + row)."""
    valid = w - 8 * (((w + 7) >> 3) - 1)
    return valid == 8 or not int.from_bytes(raw[-h:], 'big') & int.from_bytes(bytes([0xFF >> valid]) * h, 'big')


def _plane(reader, h, w, nbytes):
    raw, _ = _get_stream(reader, nbytes, empty_ok=True)
    if raw is not None and not _padding_clear(raw, h, w):
        raise ValueError('nonzero padding bits in plane')
    return raw


def _gaps(raw, n):
    """n canonical LEB128 values of at most four bytes from a stream (bytes when every value is one byte)."""
    if len(raw) == n:
        if max(raw) > 127:
            raise ValueError('malformed varint stream')
        return raw
    vals, v, k = [], 0, 0
    for b in raw:
        v |= (b & 127) << 7 * k
        k += 1
        if b < 128:
            if b == 0 and k > 1:
                raise ValueError('non-canonical or oversized varint')
            vals.append(v)
            v = k = 0
        elif k == 4:
            raise ValueError('non-canonical or oversized varint')
    if k or len(vals) != n:
        raise ValueError('malformed varint stream')
    return vals


# --- the validated store ----------------------------------------------------------------------

_ONES, _LANES8 = 0x0101010101010101, bytes((128, 64, 32, 16, 8, 4, 2, 1))


def _spread(packed):
    """Packed plane bytes as one little-endian int of 0/1 byte lanes, first cell (top bit) in the lowest lane."""
    k = len(packed)
    buf = bytearray(8 * k)
    buf[::8] = packed  # each byte at the foot of its own 64-bit word
    x = int.from_bytes(buf, 'little') * _ONES & int.from_bytes(_LANES8 * k, 'little')  # lane i keeps bit 7 - i
    return (x + int.from_bytes(b'\x7f' * (8 * k), 'little') >> 7) & int.from_bytes(b'\x01' * (8 * k), 'little')


class Store:
    """A split store whose planes are held packed and whose loss events are resolved on demand."""

    def __init__(self, header, planes, flag, n, occ, ranks, years, delta):
        self.header, self.level, (self.h, self.w) = header, header['level'], header['shape']
        self.planes, self.flag, self.n, self.occ, self.ranks = planes, flag, n, occ, ranks
        self.years, self.delta, self._cum = years, delta, None

    def _year(self, k):
        if self.delta:
            if self._cum is None:
                self._cum = array('q', accumulate(self.years))
            return self._cum[k] % 5
        return self.years[k]

    def events(self, needed):
        """{strip byte: ((lane, year symbol + 1), ...)} for the ascending strip bytes `needed` that hold loss events."""
        out, occ, ranks = {}, self.occ, self.ranks
        if not self.n or occ is None:
            return out
        rank = prev = 0  # set bits of occ before `prev`
        for b in needed:
            v = occ[b]
            if not v:
                continue
            rank += int.from_bytes(occ[prev:b], 'big').bit_count()
            prev = b
            count = v.bit_count()
            if ranks is None:  # every set bit is an event, in order
                pairs = [(t, rank + t) for t in range(count)]
            else:  # events are chosen ranks among the eligible cells
                at = bisect_left(ranks, rank)
                pairs = [(ranks[j] - rank, j) for j in range(at, min(self.n, at + count)) if ranks[j] < rank + count]
            if pairs:
                lanes = [i for i in range(8) if v >> (7 - i) & 1]
                out[b] = tuple((lanes[t], self._year(k) + 1) for t, k in pairs)
        return out

    def codes(self, plots):
        """For each plot, a list of (start, length) runs of row-major flat cell indices: its codes as bytes.

        Never expands a plane: only the packed bytes under the runs are gathered, spread to byte lanes and
        combined (2 + 6 forest + 12 unknown-forest - 2 unknown - 1 water), then loss events are added.
        """
        h, w = self.h, self.w
        los, ks, plans, g = [], [], [], 0  # first strip byte and byte count per row segment; lane slices per plot
        for runs in plots:
            plan = []
            for s, n in runs:
                r, c = divmod(s, w)
                while n:
                    take = min(n, w - c)
                    b0 = c >> 3
                    k = ((c + take - 1) >> 3) - b0 + 1
                    los.append(b0 * h + r)
                    ks.append(k)
                    plan.append((8 * g + c - 8 * b0, take))
                    g += k
                    n -= take
                    r += 1
                    c = 0
            plans.append(plan)
        total = 8 * g
        v = int.from_bytes(b'\x02' * total, 'little')
        for plane, scale in zip(self.planes, (-2, -1, 6, 12)):  # unknown, water, forest, unknown_forest
            if plane is not None:
                got = b''.join([plane[lo:lo + (k - 1) * h + 1:h] for lo, k in zip(los, ks)])
                if any(got):
                    v += scale * _spread(got)
        cells = bytearray(v.to_bytes(total, 'little'))
        needed = set()
        for lo, k in zip(los, ks):
            needed.update(range(lo, lo + k * h, h))
        hits = self.events(sorted(needed))
        if hits:
            at = 0
            for lo, k in zip(los, ks):
                for j in range(k):
                    for lane, year in hits.get(lo + j * h, ()):
                        cells[8 * (at + j) + lane] += year
                at += k
        return [b''.join([cells[a:a + t] for a, t in plan]) for plan in plans]


def _decode_split(payload, header):
    h, w = header['shape']
    bands = (w + 7) >> 3
    nbytes = bands * h
    size = nbytes * 8
    reader = _Reader(payload)
    flag = reader.byte()
    if flag not in (0, 1, 3):
        raise ValueError('unknown split flags')
    planes = [_plane(reader, h, w, nbytes) for _ in range(4)]
    unknown, water, forest, ufor = (0 if p is None else int.from_bytes(p, 'big') for p in planes)
    if unknown & water or (forest | ufor) & (unknown | water) or forest & ufor:
        raise ValueError('inconsistent split planes')
    n, occ, ranks, eventbits = 0, None, None, None
    if flag:
        n = reader.varint()
        if n > h * w:
            raise ValueError('event count exceeds grid')
        if n:
            gaps = _get_stream(reader, limit=_varint_limit(n, size))[0]
            ranks = array('q', map(add, accumulate(_gaps(gaps, n)), range(n)))
            if flag == 3:
                eligible = forest | ufor
                if ranks[-1] >= eligible.bit_count():
                    raise ValueError('event outside eligible cells')
                occ = eligible.to_bytes(nbytes, 'big')
            else:
                if ranks[-1] >= size:
                    raise ValueError('event outside grid')
                plane = bytearray(nbytes)
                for p in ranks:
                    plane[p >> 3] |= 0x80 >> (p & 7)
                if not _padding_clear(plane, h, w):
                    raise ValueError('loss event outside land')
                occ, eventbits, ranks = bytes(plane), int.from_bytes(plane, 'big'), None
    else:
        occ = _plane(reader, h, w, nbytes)
        if occ is not None:
            eventbits = int.from_bytes(occ, 'big')
            n = eventbits.bit_count()
    if eventbits is not None:  # flags 0 and 1: events sit on set bits of one plane
        if eventbits & (unknown | water):
            raise ValueError('loss event outside land')
        if header['level'] == DECISION_VERSION and eventbits & ~(forest | ufor):
            raise ValueError('decision level cannot hold nonforest land with loss (codes 3..7)')
    years, delta = None, False
    if n:
        years, flags = _get_stream(reader, n, flags_ok=1)
        if max(years) > 4:
            raise ValueError('year symbol outside 0..4')
        delta = bool(flags & 1)
    reader.end()
    return Store(header, planes, flag, n, occ if n else None, ranks, years, delta)


def open_store(blob, *, expected_sha256=None):
    """Validate a store file's bytes as read_store does before decoding, then parse its split payload."""
    if expected_sha256 is not None and hashlib.sha256(blob).hexdigest() != _digest(expected_sha256):
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
    if hashlib.sha256(payload).hexdigest() != header['payload_sha256']:
        raise ValueError('payload checksum mismatch')
    if header['encoding'] != 'split':
        raise LiteUnsupported(f"lite re-check reads split stores, not {header['encoding']}")
    return _decode_split(payload, header)


def _read(path, limit):
    path = os.fspath(path)
    if os.path.islink(path) or not os.path.isfile(path):
        raise ValueError('store must be a regular local file')
    with open(path, 'rb') as stream:
        return stream.read(limit)


def read_store_lite(path, *, expected_sha256=None):
    return open_store(_read(path, PREFIX.size + MAX_HEADER_BYTES + MAX_PAYLOAD_BYTES + 1), expected_sha256=expected_sha256)


# --- the registry -------------------------------------------------------------------------------

def parse_registry(data):
    """decision_index._parse_registry without numpy: (grid, [plot record with 'runs' as (start, length) pairs])."""
    try:
        return _parse_registry(data)
    except (KeyError, TypeError, AttributeError, IndexError, UnicodeError, RecursionError, OverflowError) as exc:
        raise ValueError('malformed registry header') from exc


def _parse_registry(data):
    if len(data) < di.PREFIX_BYTES or data[:len(di.MAGIC)] != di.MAGIC:
        raise ValueError('not a decision registry file')
    (size,) = struct.unpack_from('<I', data, len(di.MAGIC))
    if di.PREFIX_BYTES + size > len(data):
        raise ValueError('truncated registry header')
    raw = data[di.PREFIX_BYTES:di.PREFIX_BYTES + size]
    if hashlib.sha256(raw).digest() != data[len(di.MAGIC) + 4:di.PREFIX_BYTES]:
        raise ValueError('registry header hash mismatch')
    meta = json.loads(raw)
    grid, plots = di._check_registry_meta(meta)
    payload = data[di.PREFIX_BYTES + size:]
    if len(payload) != meta['payload_bytes'] or hashlib.sha256(payload).hexdigest() != meta['payload_sha256']:
        raise ValueError('registry payload size or hash mismatch')
    total = sum(p['runs'] for p in plots)
    if len(payload) != 8 * total:
        raise ValueError('registry payload size mismatch')
    values = array('i')
    if values.itemsize != 4:
        raise ValueError('unsupported platform int size')
    values.frombytes(payload)
    if struct.pack('=i', 1) != struct.pack('<i', 1):
        values.byteswap()
    starts, lengths = values[:total].tolist(), values[total:].tolist()
    cells = grid['shape'][0] * grid['shape'][1]
    if sum(n for n in lengths if n > 0) > di.MAX_REGISTRY_CELLS:
        raise ValueError('registry selections exceed the aggregate cell budget')
    out, offset = [], 0
    for p in plots:
        s, n = starts[offset:offset + p['runs']], lengths[offset:offset + p['runs']]
        offset += p['runs']
        if n:  # every run is checked against the grid before anything is expanded
            ends = [a + b for a, b in zip(s, n)]
            if (min(n) < 1 or min(s) < 0 or max(ends) > cells or sum(n) > min(cells, di.MAX_PLOT_CELLS)
                    or any(a <= b for a, b in zip(s[1:], ends))):
                raise ValueError('registry runs out of range, unsorted or oversized')
        if p['selected_count'] != sum(n) + p['outside_count']:
            raise ValueError('registry selection accounting mismatch')
        out.append(dict(p, runs=list(zip(s, n))))
    return grid, out


# --- the re-check ----------------------------------------------------------------------------------

class Lite:
    """Registered plots bound to one split store: .evaluate(plot_id) equals registry_evaluate_store's output."""

    def __init__(self, store, grid, plots, level=None):
        header = store.header
        if level is not None and level != store.level:
            raise ValueError(f'store holds {store.level}, not {level}')
        if header['shape'] != grid['shape'] or header['transform'] != grid['transform'] or header['crs'] != grid['crs']:
            raise ValueError('store grid differs from the registry grid')
        self.level, self.header, self.grid = store.level, header, grid
        decoded = store.codes([p['runs'] for p in plots])
        self.plots = {p['id']: (p['geometry_sha256'], p['selected_count'], p['outside_count'], codes)
                      for p, codes in zip(plots, decoded)}

    def evaluate(self, plot_id, geometry_sha256=None):
        digest, selected, outside, codes = self.plots[plot_id]
        if geometry_sha256 is not None and geometry_sha256 != digest:
            raise ValueError('registry entry does not match the registered geometry hash')
        counts = [0] * CODE_COUNT
        for code in set(codes):
            counts[code] = codes.count(code)
        return summarize_ints(counts, selected, outside, self.level)  # counts: a list of ints by construction


def load(store_path, registry_path, *, expected_sha256=None, level=None):
    """Validate the store and the registry and bind them: the numpy-free P5."""
    store = read_store_lite(store_path, expected_sha256=expected_sha256)
    with open(os.fspath(registry_path), 'rb') as stream:
        grid, plots = parse_registry(stream.read())
    return Lite(store, grid, plots, level)
