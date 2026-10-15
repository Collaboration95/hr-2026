"""Hot-path speed for plot queries: registered-plot index, decision table, exact fast selection.

Three levers, each keyed by hashes so a changed input can never answer from a stale index:

- Registry (an index): the in-chip flat cell indices a registered plot selects under the
  shared centre rule, keyed by geometry hash and grid identity. Re-checking a plot against
  updated layers is then one bincount over the code raster, with no polygon selection. The
  file carries a sha256 of its header and of its payload, and its parser bounds every run
  against the grid before expanding it. Evaluation needs the level; registry_evaluate_store
  takes it (and the grid) from a read_store header.
- Table (a materialised view): both contracts' outputs per registered plot, keyed by geometry
  hash and per-level store hash, sealed with a content sha256 that load_table verifies. Lookup
  is a dict hit and needs only the stdlib; a table keyed by raster bytes (not a store file)
  also needs the live grid, because those bytes do not bind it.
- Fast selection (new polygons): scanline even-odd parity on native centre rows, with exact
  GEOS covers only for centres near an edge, vertex or horizontal edge. Exact w.r.t. select_cells.
  Small windows run the same scan in pure Python (numpy's per-call cost dominates there), and
  evaluate_store reduces them to the code histogram straight from the runs of selected centres.

`import engine.decision_index` pulls in only the stdlib. numpy loads on first registry use;
shapely/GEOS only for building a registry/table or selecting new polygons.
"""
import hashlib
import json
import math
import struct
from bisect import bisect_left, bisect_right
from itertools import chain
from math import ceil, floor, inf, isfinite
from operator import sub
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'artifacts/decision'
REGISTRY_SCHEMA = 'plotline.decision-registry.v2'
TABLE_SCHEMA = 'plotline.decision-table.v2'
MAGIC = b'PLDREG2\n'  # MAGIC | u32 header length | sha256 of header | header | payload
PREFIX_BYTES = len(MAGIC) + 4 + 32
HEX = frozenset('0123456789abcdef')
MAX_PLOT_CELLS = 10_000_000  # engine.query.MAX_CANDIDATE_CELLS: no registered selection can be larger
MAX_REGISTRY_CELLS = 10_000_000  # aggregate across plots, so many small runs cannot add up to an unbounded expansion
STORE_FILES = {'eudr-screen.v1': 'screen.plds', 'eudr-decision.v1': 'decision.plds'}
SELECTION_RULE = 'engine.query.select_cells: exact GEOS covers on native cell centres, boundary-inclusive'
# Scanline tolerance: any centre within TOL_ABS + TOL_REL*max|x| of an edge crossing is decided by
# exact GEOS. The computed crossing is within ~1 ulp(x) + 8*2**-53*|dx| of the true one (about 1e-14
# degrees at x~100), so this margin is >1e5 times the error and still delegates ~0 centres per row.
TOL_ABS, TOL_REL = 1e-9, 2.0 ** -40
MAX_ROW_PAIRS = 2_000_000  # row-chunk x edge matrix cap for bounded memory
PREPARE_POINTS = 16  # ambiguous centres above which the polygon is prepared before exact covers
LATTICE_LIMIT = 2.0 ** 62
MAX_RECT_LOOP = 64  # ambiguous rectangles up to which they are painted one by one, not via a 2-D difference array
SCALAR_SURE_ROWS = 500  # candidate rows x edges up to which a pure-Python scan beats numpy's per-call overhead, whatever the shape
SCALAR_EDGE_ROWS = 2000  # up to which it still does if the boundary changes rows at most SCALAR_CROSSINGS times in all
SCALAR_CROSSINGS = 150  # the Python scan pays ~0.17 us per row an edge crosses (rows x edges is only a bound on that), numpy's does not
SCALAR_CELLS = 4096  # and candidate cells up to which it stays cheaper

np = summarize_ints = summarize_selection = bind_level = None
CODE_COUNT = 20


def _numpy():
    """Bind numpy and the pure reducers on first use; keeps the module import stdlib-only."""
    global np, summarize_ints, summarize_selection, bind_level, CODE_COUNT
    import numpy
    from . import decision
    np, summarize_ints, summarize_selection = numpy, decision.summarize_ints, decision.summarize_selection
    bind_level, CODE_COUNT = decision.bind_level, decision.CODE_COUNT


def canonical_bytes(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()


def geometry_sha256(geometry):
    """SHA-256 of the canonical JSON; equals engine.source.object_hash without its rasterio import."""
    return hashlib.sha256(canonical_bytes(geometry)).hexdigest()


def grid_identity(metadata):
    return {'shape': [int(v) for v in metadata['shape']],
            'transform': [float(v) for v in metadata['transform']], 'crs': metadata['crs']}


# ---- registered-plot index ----------------------------------------------------------------

def build_registry(plots, metadata):
    """Precompute each plot's in-chip flat cell indices (row*W+col, int32, sorted) with select_cells."""
    if np is None:
        _numpy()
    from .query import select_cells
    height, width = metadata['shape']
    if height * width >= 2 ** 31:
        raise ValueError('flat index requires fewer than 2**31 cells')
    grid, entries = grid_identity(metadata), {}
    for plot in plots:
        plot_id = plot['plot_id']
        if plot_id in entries:
            raise ValueError(f'duplicate plot ID: {plot_id}')
        rows, cols = select_cells(metadata, plot['geometry'])
        inside = (rows >= 0) & (rows < height) & (cols >= 0) & (cols < width)
        flat = (rows[inside] * width + cols[inside]).astype(np.int32)
        if flat.size > 1 and not np.all(np.diff(flat) > 0):
            raise ValueError('selected cells are not strictly row-major')
        entries[plot_id] = {'geometry_sha256': geometry_sha256(plot['geometry']), 'flat_index': flat,
                            'selected_count': int(rows.size), 'outside_count': int(rows.size - flat.size), 'grid': grid}
    return {'schema': REGISTRY_SCHEMA, 'selection_rule': SELECTION_RULE, 'grid': grid, 'plots': entries}


def registry_evaluate(codes, entry, level):
    """Contract outputs for a registered plot at `level`: bincount of the precomputed cells, no selection.

    level is required: the codes cannot say which contract they hold, and a decision raster read as
    screen reports no Hansen loss. The raster must have the registry's grid shape. For a raster from
    read_store use registry_evaluate_store, which takes the level from the header.
    """
    if np is None:
        _numpy()
    if codes.shape != tuple(entry['grid']['shape']):
        raise ValueError('code raster shape differs from the registry grid')
    counts = np.bincount(codes.ravel()[entry['flat_index']], minlength=CODE_COUNT)
    if counts.size != CODE_COUNT:
        raise ValueError('code raster holds values outside the contract code space')
    return summarize_ints(counts.tolist(), entry['selected_count'], entry['outside_count'], level)  # bincount: int64


def registry_evaluate_store(codes, header, entry, level=None):
    """registry_evaluate for a read_store result: level and grid come from its header.

    level, if given, must equal header['level']; the header's grid must be the entry's grid.
    """
    if np is None:
        _numpy()
    held, grid = bind_level(header, level), entry['grid']
    if header['shape'] != grid['shape'] or header['transform'] != grid['transform'] or header['crs'] != grid['crs']:
        raise ValueError('store grid differs from the registry grid')
    return registry_evaluate(codes, entry, held)


def registry_lookup(registry, plot_id, geometry, metadata):
    """The entry only if geometry and the current grid (`metadata`, required) still match, else None.

    None means the caller selects afresh; the grid is always compared with the registry's.
    """
    entry = registry['plots'].get(plot_id)
    if entry is None or entry['geometry_sha256'] != geometry_sha256(geometry) or grid_identity(metadata) != registry['grid']:
        return None
    return entry


def _runs(flat):
    """Maximal consecutive runs of a sorted index array as (starts, lengths)."""
    breaks = np.flatnonzero(np.diff(flat) != 1) + 1
    first = np.concatenate(([0], breaks)) if flat.size else breaks
    last = np.concatenate((breaks, [flat.size])) if flat.size else breaks
    return flat[first].astype('<i4'), (last - first).astype('<i4')


def registry_to_bytes(registry):
    """Deterministic file: magic, u32 header length, sha256 of the header, canonical JSON header, run-length payload."""
    if np is None:
        _numpy()
    starts, lengths, plots = [], [], []
    for plot_id, entry in registry['plots'].items():
        s, n = _runs(entry['flat_index'])
        starts.append(s)
        lengths.append(n)
        plots.append({'id': plot_id, 'geometry_sha256': entry['geometry_sha256'], 'runs': int(s.size),
                      'selected_count': entry['selected_count'], 'outside_count': entry['outside_count']})
    payload = b''.join(a.tobytes() for a in starts + lengths)
    header = canonical_bytes({'schema': registry['schema'], 'selection_rule': registry['selection_rule'],
                              'grid': registry['grid'], 'plots': plots,
                              'payload_bytes': len(payload), 'payload_sha256': hashlib.sha256(payload).hexdigest()})
    return MAGIC + struct.pack('<I', len(header)) + hashlib.sha256(header).digest() + header + payload


def registry_from_bytes(data):
    """Parse and verify a registry file (numpy + stdlib only); any malformed input is a ValueError."""
    if np is None:
        _numpy()
    try:
        return _parse_registry(data)
    except (KeyError, TypeError, AttributeError, IndexError, UnicodeError, RecursionError, OverflowError) as exc:
        raise ValueError('malformed registry header') from exc


def _digest(value):
    return type(value) is str and len(value) == 64 and HEX.issuperset(value)


def _check_registry_meta(meta):
    """Types and bounds of a parsed registry header, before any payload is read or expanded."""
    if type(meta) is not dict:
        raise ValueError('registry header must be a JSON object')
    grid, plots = meta.get('grid'), meta.get('plots')
    if (set(meta) != {'schema', 'selection_rule', 'grid', 'plots', 'payload_bytes', 'payload_sha256'}
            or meta['schema'] != REGISTRY_SCHEMA or type(meta['selection_rule']) is not str
            or type(meta['payload_bytes']) is not int or not _digest(meta['payload_sha256']) or type(plots) is not list
            or type(grid) is not dict or set(grid) != {'shape', 'transform', 'crs'} or type(grid['crs']) is not str
            or type(grid['shape']) is not list or len(grid['shape']) != 2
            or any(type(v) is not int or v < 1 for v in grid['shape']) or grid['shape'][0] * grid['shape'][1] >= 2 ** 31
            or type(grid['transform']) is not list or len(grid['transform']) != 6
            or not all(type(v) in (int, float) and math.isfinite(v) for v in grid['transform'])):
        raise ValueError('registry header is malformed or has an invalid grid')
    keys = {'id', 'geometry_sha256', 'runs', 'selected_count', 'outside_count'}
    for p in plots:
        if (type(p) is not dict or set(p) != keys or type(p['id']) is not str or not _digest(p['geometry_sha256'])
                or any(type(p[k]) is not int or p[k] < 0 for k in ('runs', 'selected_count', 'outside_count'))):
            raise ValueError('registry plot record is malformed')
    if len({p['id'] for p in plots}) != len(plots):
        raise ValueError('duplicate plot ID in registry')
    return grid, plots


def _parse_registry(data):
    if len(data) < PREFIX_BYTES or data[:len(MAGIC)] != MAGIC:
        raise ValueError('not a decision registry file')
    (size,) = struct.unpack_from('<I', data, len(MAGIC))
    if PREFIX_BYTES + size > len(data):
        raise ValueError('truncated registry header')
    raw = data[PREFIX_BYTES:PREFIX_BYTES + size]
    if hashlib.sha256(raw).digest() != data[len(MAGIC) + 4:PREFIX_BYTES]:
        raise ValueError('registry header hash mismatch')
    meta = json.loads(raw)
    grid, plots = _check_registry_meta(meta)
    payload = data[PREFIX_BYTES + size:]
    if len(payload) != meta['payload_bytes'] or hashlib.sha256(payload).hexdigest() != meta['payload_sha256']:
        raise ValueError('registry payload size or hash mismatch')
    total = sum(p['runs'] for p in plots)
    if len(payload) != 8 * total:
        raise ValueError('registry payload size mismatch')
    values = np.frombuffer(payload, '<i4')
    starts, lengths = values[:total].astype(np.int64), values[total:].astype(np.int64)
    cells = grid['shape'][0] * grid['shape'][1]
    if int(np.clip(lengths, 0, None).sum()) > MAX_REGISTRY_CELLS:
        raise ValueError('registry selections exceed the aggregate cell budget')
    entries, offset = {}, 0
    for p in plots:
        s, n = starts[offset:offset + p['runs']], lengths[offset:offset + p['runs']]
        offset += p['runs']
        if n.size:  # every run is checked against the grid before anything is expanded
            ends = s + n
            if (n.min() < 1 or s.min() < 0 or int(ends.max()) > cells or int(n.sum()) > min(cells, MAX_PLOT_CELLS)
                    or not np.all(s[1:] > ends[:-1])):
                raise ValueError('registry runs out of range, unsorted or oversized')
        count = int(n.sum())
        if p['selected_count'] != count + p['outside_count']:
            raise ValueError('registry selection accounting mismatch')
        flat = np.repeat(s - (np.cumsum(n) - n), n) + np.arange(count)
        entries[p['id']] = {'geometry_sha256': p['geometry_sha256'], 'flat_index': flat.astype(np.int32),
                            'selected_count': p['selected_count'], 'outside_count': p['outside_count'], 'grid': grid}
    return {'schema': meta['schema'], 'selection_rule': meta['selection_rule'], 'grid': grid, 'plots': entries}


def save_registry(registry, path):
    data = registry_to_bytes(registry)
    Path(path).write_bytes(data)
    return len(data)


def load_registry(path):
    return registry_from_bytes(Path(path).read_bytes())


# ---- decision table (materialised view) ---------------------------------------------------

def build_table(plots, codes_by_level, store_sha256_by_level, metadata, store_basis_by_level=None):
    """Both contracts' full outputs per plot, keyed by geometry hash and per-level store hash."""
    if np is None:
        _numpy()
    from .query import select_cells
    if set(codes_by_level) != set(store_sha256_by_level):
        raise ValueError('every level needs a store sha256')
    out = {}
    for plot in plots:
        plot_id = plot['plot_id']
        if plot_id in out:
            raise ValueError(f'duplicate plot ID: {plot_id}')
        rows, cols = select_cells(metadata, plot['geometry'])
        out[plot_id] = {'geometry_sha256': geometry_sha256(plot['geometry']),
                        'outputs': {level: summarize_selection(codes, rows, cols, level)
                                    for level, codes in codes_by_level.items()}}
    table = {'schema': TABLE_SCHEMA, 'selection_rule': SELECTION_RULE, 'grid': grid_identity(metadata),
             'stores': dict(store_sha256_by_level), 'store_basis': dict(store_basis_by_level or {}), 'plots': out}
    return {**table, 'content_sha256': table_digest(table)}


def table_digest(table):
    """sha256 of the canonical JSON of the table without its content_sha256 field."""
    return hashlib.sha256(canonical_bytes({k: v for k, v in table.items() if k != 'content_sha256'})).hexdigest()


def table_lookup(table, plot_id, geometry_sha256, store_sha256, level, grid=None):
    """Stored outputs (do not mutate) only on an exact plot/geometry/store/level key match, else None.

    A table keyed by a store file's sha256 (store_basis 'file:...') is bound to that file's grid. One keyed by
    raster bytes ('code-raster-bytes') binds only the cells, so `grid` (the live metadata or header) is then
    required, and a different grid is a miss. A grid passed with a file basis is checked too.
    """
    entry = table['plots'].get(plot_id)
    if entry is None or entry['geometry_sha256'] != geometry_sha256 or table['stores'].get(level) != store_sha256:
        return None
    if grid is not None:
        if grid_identity(grid) != table['grid']:
            return None
    elif not table['store_basis'].get(level, '').startswith('file:'):
        raise ValueError('a table keyed by raster bytes needs the live grid')
    return entry['outputs'].get(level)


def table_to_bytes(table):
    return canonical_bytes(table)


def save_table(table, path):
    data = table_to_bytes(table)
    Path(path).write_bytes(data)
    return len(data)


def load_table(path):
    """Read a table and verify its content_sha256; an edited or truncated file is a ValueError."""
    try:
        table = json.loads(Path(path).read_bytes())
        if type(table) is not dict or table.get('schema') != TABLE_SCHEMA:
            raise ValueError('not a decision table')
        if table.get('content_sha256') != table_digest(table):
            raise ValueError('decision table content hash mismatch')
    except (RecursionError, UnicodeError, TypeError) as exc:
        raise ValueError('malformed decision table') from exc
    return table


def store_sha256(level, codes, out_dir=OUT):
    """(sha256, basis): the level's store file when present, else the derived code raster bytes."""
    path = Path(out_dir) / STORE_FILES[level]
    if path.is_file():
        return hashlib.sha256(path.read_bytes()).hexdigest(), f'file:{path.name}'
    return hashlib.sha256(codes.tobytes()).hexdigest(), 'code-raster-bytes'


def check_store(level, codes, out_dir=OUT, metadata=None):
    """If the level's store file exists, decode it and require it to equal `codes` (and, if given, its
    header to name `level` and the grid of `metadata`); True when checked."""
    path = Path(out_dir) / STORE_FILES[level]
    if not path.is_file():
        return False
    if np is None:
        _numpy()
    from .decision_store import read_store
    decoded, header = read_store(path)
    bind_level(header, level)
    if metadata is not None and grid_identity(header) != grid_identity(metadata):
        raise ValueError(f'{path.name} grid differs from the grid the table would be built on')
    if decoded.shape != codes.shape or not np.array_equal(decoded, codes):
        raise ValueError(f'{path.name} differs from the code raster the table would be built from')
    return True


def zstd_size(data, level=19):
    try:
        from compression import zstd
    except ImportError:
        return None
    return len(zstd.compress(data, level=level))


# ---- exact fast selection for new polygons ------------------------------------------------

_G = {}


def _geos():
    if not _G:
        import numpy
        import shapely
        from shapely.geometry import shape
        from . import query
        # HandleNaN.allow: the positions are finite, so any mode builds the same ring
        _G.update(shapely=shapely, shape=shape, query=query, lib=shapely.lib,
                  allow=numpy.intc(0), no_holes=numpy.empty(0, object))
    return _G


def _flat(polygons, limit):
    """(xy, ring lengths, rings per polygon) when the input is exact lists of [float|int, float|int] positions that
    pass select_cells' checks, else None, leaving those checks to decide (and raise) as select_cells does."""
    try:
        pts, lens, counts = [], [], []
        for rings in polygons:
            if type(rings) is not list or not rings:
                return None
            counts.append(len(rings))
            for ring in rings:
                if type(ring) is not list or len(ring) < 4 or ring[0] != ring[-1]:
                    return None
                lens.append(len(ring))
                pts += ring
        if len(pts) > limit or set(map(type, pts)) != {list} or set(map(len, pts)) != {2}:
            return None
        vals = list(chain.from_iterable(pts))
        if not set(map(type, vals)) <= {float, int}:
            return None
        xy = np.array(vals, float).reshape(-1, 2)  # an int beyond float range raises OverflowError, as math.isfinite does
        return (xy, lens, counts) if math.isfinite(sum(vals)) else None  # a finite sum means every value is finite
    except Exception:
        return None


def _polygon(g, geometry, xy, lens, counts):
    """The geometry shape() builds, from the validated array (None if GEOS refuses; shape() then reports it)."""
    try:
        if len(lens) == 1 and geometry['type'] == 'Polygon':  # one shell
            return g['lib'].polygons(g['lib'].linearrings(xy, g['allow']), g['no_holes'])
        make, lib, polygons, pos, i = g['shapely'], g['lib'], [], 0, 0
        for count in counts:
            rings = []
            for n in lens[i:i+count]:
                rings.append(lib.linearrings(xy[pos:pos+n], g['allow']))  # shapely.linearrings minus its wrappers
                pos += n
            i += count
            polygons.append(make.polygons(rings[0], rings[1:]) if count > 1 else lib.polygons(rings[0], g['no_holes']))
        return polygons[0] if geometry['type'] == 'Polygon' else make.multipolygons(polygons)
    except Exception:
        return None


def _checked(g, metadata, geometry):
    """select_cells' validation and candidate window (differential-tested): the checks line for line, except that
    clean input (see _flat) passes them in bulk. Also returns the positions array of clean input, else None."""
    query = g['query']
    if not isinstance(geometry, dict) or geometry.get('type') not in ('Polygon', 'MultiPolygon'):
        raise ValueError('only Polygon and MultiPolygon are supported')
    coordinates = geometry.get('coordinates')
    polygons = [coordinates] if geometry['type'] == 'Polygon' else coordinates
    if not isinstance(polygons, (list, tuple)) or not polygons:
        raise ValueError('geometry must contain polygons')
    flat = _flat(polygons, query.MAX_GEOMETRY_VERTICES)
    if flat:  # clean input: the checks below would all pass
        xy, lens, counts = flat
    else:
        xy = None
        vertex_count, lens = 0, []
        for rings in polygons:
            if not isinstance(rings, (list, tuple)) or not rings:
                raise ValueError('polygon must contain an exterior ring')
            for ring in rings:
                if not isinstance(ring, (list, tuple)) or len(ring) < 4 or ring[0] != ring[-1]:
                    raise ValueError('rings must have at least four positions and be explicitly closed')
                vertex_count += len(ring)
                lens.append(len(ring))
                if vertex_count > query.MAX_GEOMETRY_VERTICES:
                    raise ValueError('geometry exceeds 100000 vertices')
                for point in ring:
                    if type(point) is list and len(point) == 2:  # exact-type fast accept; all else takes the checks below
                        u, v = point
                        if (type(u) is float or type(u) is int) and (type(v) is float or type(v) is int):
                            try:
                                if math.isfinite(u) and math.isfinite(v):
                                    continue
                            except OverflowError:
                                pass
                    if not isinstance(point, (list, tuple)) or len(point) != 2:
                        raise ValueError('positions must have exactly two coordinates')
                    try:
                        valid = all(not isinstance(v, bool) and isinstance(v, (int, float)) and math.isfinite(v) for v in point)
                    except (OverflowError, ValueError):
                        valid = False
                    if not valid:
                        raise ValueError('positions must be finite numbers')
    polygon = _polygon(g, geometry, xy, lens, counts) if flat else None
    if polygon is None:
        try:
            polygon = g['shape'](geometry)
        except Exception as exc:
            raise ValueError('malformed geometry') from exc
    minx, miny, maxx, maxy = g['lib'].bounds(polygon).tolist()  # polygon.bounds: NaN when empty
    if -1e100 < minx and maxx < 1e100 and -1e100 < miny and maxy < 1e100:
        invalid = not g['lib'].is_valid(polygon)  # nonempty, and too small to overflow, so shapely.is_valid has no warnings to suppress
    else:
        invalid = polygon.is_empty or not polygon.is_valid
    if invalid:
        raise ValueError('geometry must be nonempty and valid')
    transform = metadata.get('transform', [])
    if type(transform) is list and len(transform) == 6:  # the checks below, unrolled
        a, b, c, d, e, f = transform
        finite = isfinite(a) and isfinite(b) and isfinite(c) and isfinite(d) and isfinite(e) and isfinite(f)
    else:
        finite = len(transform) == 6 and all(isfinite(v) for v in transform)
        if finite:
            a, b, c, d, e, f = transform
    if not finite:
        raise ValueError('finite six-value transform required')
    if b != 0 or d != 0 or a <= 0 or e >= 0 or metadata.get('crs') != 'EPSG:4326':
        raise ValueError('only north-up EPSG:4326 grids are supported')
    if not (isfinite(minx) and isfinite(miny) and isfinite(maxx) and isfinite(maxy)):
        raise ValueError('geometry bounds must be finite')
    x0, x1, y0, y1 = (minx-c)/a-.5, (maxx-c)/a-.5, (maxy-f)/e-.5, (miny-f)/e-.5
    if not (-LATTICE_LIMIT < x0 < LATTICE_LIMIT and -LATTICE_LIMIT < x1 < LATTICE_LIMIT  # finite and below 2**62
            and -LATTICE_LIMIT < y0 < LATTICE_LIMIT and -LATTICE_LIMIT < y1 < LATTICE_LIMIT):
        raise ValueError('geometry exceeds supported native lattice index range')
    c0, c1 = floor(x0) - 1, ceil(x1) + 1
    r0, r1 = floor(y0) - 1, ceil(y1) + 1
    if (r1-r0+1) * (c1-c0+1) > query.MAX_CANDIDATE_CELLS:
        raise ValueError('geometry exceeds 10000000 candidate cells; partition explicitly')
    return polygon, xy, lens, (a, c, e, f), (r0, r1, c0, c1), max(abs(minx), abs(maxx))


def fast_select_cells(metadata, geometry):
    """Same (rows, cols) as engine.query.select_cells, same rejections, no per-cell GEOS.

    For each candidate row, edge crossings at the row's centre y give even-odd parity for every
    centre (all rings together, so holes and multipolygons need no special case). Centres whose
    class could differ from exact predicates go to shapely.covers: those within the tolerance of a
    crossing (exact ties included), within it of a vertex lying exactly on a centre row (which
    includes local extrema that count no crossing), or on a horizontal edge lying on one.
    Anything outside the tested numeric envelope falls back to select_cells itself. Small windows
    run the same scan in pure Python (_scalar_runs), because numpy's per-call cost dominates there.
    """
    selection = _select(metadata, geometry)
    return selection if len(selection) == 2 else _run_cells(*selection)


def _run_cells(runs, stride, base, r0, c0):
    rows, cols = [], []
    for s, e in zip(runs[::2], runs[1::2]):
        i, k = divmod(s - (base or 0), stride)
        rows += [i + r0] * (e - s)
        cols += range(k + c0, k + c0 + e - s)
    return np.array(rows, np.intp), np.array(cols, np.intp)


def _select(metadata, geometry, shape=None):
    """(rows, cols) from the array scan, or (runs, stride, base, r0, c0) from the scalar scan.

    runs is [start, end, start, end, ...] for runs of selected centres (possibly empty), each within one row, ascending,
    where a centre in local window row i and column k has position base + i * stride + k. With the chip's `shape` given
    and the window inside it, positions are indices into the flattened raster."""
    if np is None:
        _numpy()
    g = _geos()
    polygon, xy, lens, (a, c, e, f), (r0, r1, c0, c1), reach = _checked(g, metadata, geometry)
    R, C = r1 - r0 + 1, c1 - c0 + 1
    flat = xy is not None
    if not flat:
        xy = g['shapely'].get_coordinates(polygon)
    small_grid = abs(c) < 1e90 and abs(f) < 1e90 and a < 1e80 and -e < 1e80  # quick sufficient test for the last condition
    if (len(xy) != sum(lens) or not (-2**50 <= r0 and r1 <= 2**50 and -2**50 <= c0 and c1 <= 2**50)  # r0 < r1, c0 < c1
            or not small_grid and max(abs(c), abs(f)) + 2**51 * max(a, -e) > 1e100):
        return g['query'].select_cells(metadata, geometry)
    rows_edges = R * (len(xy) - len(lens))
    if flat and R * C <= SCALAR_CELLS and rows_edges <= SCALAR_EDGE_ROWS:
        stride = base = None
        if shape is not None and 0 <= r0 and r1 < shape[0] and 0 <= c0 and c1 < shape[1]:
            stride, base = shape[1], r0 * shape[1] + c0
        runs = _scalar_runs(g, polygon, xy, lens, (a, c, e, f), (r0, c0, R, C), reach, stride, base,
                            None if rows_edges <= SCALAR_SURE_ROWS else SCALAR_CROSSINGS)
        if runs is not None:
            return runs, stride or C + 1, base, r0, c0
    return _array_select(g, polygon, xy, lens, (a, c, e, f), (r0, r1, c0, c1), reach)


def _scalar_runs(g, polygon, xy, lens, grid, window, reach, stride, base, max_crossings=None):
    """The array scan below in plain Python, edge by edge: same arithmetic, same ambiguity rule, same answers.

    Rows and columns are located by bisect on lists of the centre coordinates, computed with the
    same expressions as the array scan (bisect and searchsorted agree on any sorted list). A
    crossing is clean when no centre lies within tol of it, which is exactly when its tolerance
    band holds no centre; otherwise the centres in the band, and those near vertices on centre
    rows and horizontal edges on them, are decided by exact covers. Returns None if the crossing
    parity were odd, which closed rings rule out, or if the boundary changes rows more than max_crossings
    times in all (a sawtooth: the loop below costs per crossing), so the caller falls back to the array scan.
    """
    a, c, e, f = grid
    r0, c0, R, C = window
    xs, ys = xy.T.tolist()
    tol = TOL_ABS + TOL_REL * reach
    c0h, r0h, L = c0 + .5, r0 + .5, C + 1
    W, off = (stride, base - 1) if stride else (L, -1)  # event = off + 1 + row * W + count of centres left of a crossing
    py = [f + (i + r0h) * e for i in range(R)]
    npy = [-v for v in py]  # ascending, so exact row equality is a bisect
    above = [bisect_right(npy, -y) for y in ys]  # centre rows with py >= y
    if max_crossings is not None and sum(map(abs, map(sub, above, above[1:]))) > max_crossings:  # ring joins included
        return None
    pp = [-inf, *[c + (j + c0h) * a for j in range(C)], inf]  # centre x, padded: bisect - 1 counts the centres
    events, rects = [], []  # rects: ambiguous (row lo, row hi, col lo, col hi)
    edges = list(zip(xs, ys, xs[1:], ys[1:], above, above[1:]))
    if len(lens) > 1:
        end = 0
        for n in lens[:-1]:
            end += n
            edges[end-1] = None  # joins two rings
        edges = [edge for edge in edges if edge]
    for x1, y1, x2, y2, ra, rb in edges:
        if ra == rb:  # no centre row in [ylo, yhi): horizontal edges included
            continue
        if ra > rb:
            ra, rb = rb, ra
        dy, dx = y2 - y1, x2 - x1
        for i in range(ra, rb):  # rows with ylo <= py < yhi
            xc = x1 + (py[i] - y1) / dy * dx
            k = bisect_right(pp, xc)
            events.append(off + i * W + k)
            if not (pp[k-1] < xc - tol and pp[k] > xc + tol):  # centres within tol of the crossing
                rects.append((i, i + 1, bisect_left(pp, xc - tol) - 1, bisect_right(pp, xc + tol) - 1))
    events.sort()
    if len(events) & 1:
        return None
    on_rows = set(py).intersection(ys)  # y values exactly on a centre row
    if on_rows:
        for x, y in zip(xs, ys):  # a vertex on a centre row: the centres near it are ambiguous
            if y in on_rows:
                rects.append((bisect_left(npy, -y), bisect_right(npy, -y),
                              bisect_left(pp, x - tol) - 1, bisect_right(pp, x + tol) - 1))
        for x1, y1, x2, y2, _, _ in edges:
            if y1 == y2 and y1 in on_rows:  # horizontal edge on a centre row: its whole span is boundary
                rects.append((bisect_left(npy, -y1), bisect_right(npy, -y1),
                              bisect_left(pp, min(x1, x2) - tol) - 1, bisect_right(pp, max(x1, x2) + tol) - 1))
    ambiguous = set()
    for ra, rb, lo, hi in rects:
        for i in range(ra, rb):
            ambiguous.update(range(i * L + lo, i * L + hi))
    if not ambiguous:
        return events
    cells = set()
    for s, e in zip(events[::2], events[1::2]):
        i, k = divmod(s - off - 1, W)
        cells.update(range(i * L + k, i * L + k + e - s))
    cells -= ambiguous
    order = sorted(ambiguous)
    coords = np.array([(pp[o % L + 1], py[o // L]) for o in order])
    if len(order) > PREPARE_POINTS:
        g['lib'].prepare(polygon)
    covered = g['lib'].covers(polygon, g['lib'].points(coords, g['allow'])).tolist()
    cells.update(o for o, hit in zip(order, covered) if hit)
    runs, last = [], -2
    for o in sorted(cells):
        i, k = divmod(o, L)
        o = off + 1 + i * W + k
        if o == last:  # the next centre in the same row
            runs[-1] += 1
        else:
            runs += [o, o + 1]
        last = o + 1
    return runs


def _array_select(g, polygon, xy, lens, grid, window, reach):
    """The numpy scan: whole candidate window at once."""
    a, c, e, f = grid
    r0, r1, c0, c1 = window
    R, C = r1 - r0 + 1, c1 - c0 + 1
    # Centre coordinates computed exactly as select_cells does: c + (col + .5) * a.
    px = c + (np.arange(C) + (c0 + .5)) * a
    py = f + (np.arange(R) + (r0 + .5)) * e
    x, y = xy[:, 0], xy[:, 1]
    if len(lens) == 1:
        x1, y1, x2, y2, keep = x[:-1], y[:-1], x[1:], y[1:], None
    else:
        keep = np.ones(len(x) - 1, bool)
        keep[np.cumsum(lens)[:-1] - 1] = False  # drop segments joining two rings
        x1, y1, x2, y2 = x[:-1][keep], y[:-1][keep], x[1:][keep], y[1:][keep]
    dx, dy = x2 - x1, y2 - y1
    tol = TOL_ABS + TOL_REL * reach
    inside = np.empty((R, C), bool)
    rects = []  # ambiguous index rectangles (row lo, row hi, col lo, col hi)
    step = max(1, MAX_ROW_PAIRS // len(x1))
    for ra in range(0, R, step):
        rb = min(R, ra + step)
        pc = py[ra:rb, None]
        ri, ei = ((y1 > pc) != (y2 > pc)).nonzero()  # half-open: min(y) <= py < max(y)
        xc = x1[ei] + (py[ra:rb][ri] - y1[ei]) / dy[ei] * dx[ei]  # t in [0, 1): no overflow, never 0/0
        k = px.searchsorted(xc, 'right')  # first centre right of the crossing
        d = np.bincount(ri * (C + 1) + k, minlength=(rb - ra) * (C + 1)).reshape(rb - ra, C + 1)
        inside[ra:rb] = d.cumsum(1)[:, :C] & 1  # crossings left of each centre, parity
        lo, hi = px.searchsorted(xc - tol, 'left'), px.searchsorted(xc + tol, 'right')
        near = hi > lo
        if near.any():
            rects.append((ri[near] + ra, ri[near] + ra + 1, lo[near], hi[near]))
    npy = -py  # ascending, so exact row equality is a searchsorted
    negy = -y
    on_row = npy[np.minimum(npy.searchsorted(negy, 'left'), R - 1)] == negy
    if on_row.any():
        ny, vx = negy[on_row], x[on_row]
        rects.append((npy.searchsorted(ny, 'left'), npy.searchsorted(ny, 'right'),
                      px.searchsorted(vx - tol, 'left'), px.searchsorted(vx + tol, 'right')))
        first = on_row[:-1] if keep is None else on_row[:-1][keep]
        flat = first & (dy == 0)  # horizontal edge on a centre row: whole span is boundary
        if flat.any():
            ny, hx0, hx1 = -y1[flat], np.minimum(x1[flat], x2[flat]), np.maximum(x1[flat], x2[flat])
            rects.append((npy.searchsorted(ny, 'left'), npy.searchsorted(ny, 'right'),
                          px.searchsorted(hx0 - tol, 'left'), px.searchsorted(hx1 + tol, 'right')))
    if rects:
        if sum(len(rect[0]) for rect in rects) <= MAX_RECT_LOOP:
            ambiguous = np.zeros((R, C), bool)
            for rect in rects:
                for lo_r, hi_r, lo_c, hi_c in zip(*(v.tolist() for v in rect)):
                    ambiguous[lo_r:hi_r, lo_c:hi_c] = True
        else:  # 2-D difference array of the rectangles
            ra, rb, ca, cb = (np.concatenate(v) for v in zip(*rects))
            w = C + 1
            mark = np.bincount(np.concatenate((ra * w + ca, rb * w + cb)), minlength=(R + 1) * w) \
                - np.bincount(np.concatenate((ra * w + cb, rb * w + ca)), minlength=(R + 1) * w)
            ambiguous = mark.reshape(R + 1, w).cumsum(0).cumsum(1)[:R, :C] > 0
        ar, ac = ambiguous.nonzero()
        coords = np.empty((len(ar), 2))
        coords[:, 0], coords[:, 1] = px[ac], py[ar]
        if len(ar) > PREPARE_POINTS:
            g['lib'].prepare(polygon)  # same answers, indexed edges
        inside[ar, ac] = g['lib'].covers(polygon, g['lib'].points(coords, g['allow']))  # shapely.covers/points minus wrappers
    rows, cols = inside.nonzero()
    return rows + r0, cols + c0


def fast_summarize(codes, header, geometry, level):
    """summarize_selection(codes, *fast_select_cells(header, geometry), level), reduced from the runs of selected
    centres directly: one slice of the raster per run and one bincount, no row and column arrays. evaluate_store
    uses it when handed fast_select_cells, so the answers and the rejections are the same."""
    if np is None:
        _numpy()
    try:
        flat = memoryview(codes) if type(codes) is np.ndarray else None
        direct = flat is not None and flat.format == 'B' and flat.ndim == 2 and flat.c_contiguous
    except (TypeError, ValueError):
        direct = False
    if not direct:
        return summarize_selection(codes, *fast_select_cells(header, geometry), level)
    selection = _select(header, geometry, codes.shape)
    if len(selection) == 2:
        return summarize_selection(codes, *selection, level)
    if selection[2] is None:  # the window is not inside the chip: runs are in window coordinates
        return summarize_selection(codes, *_run_cells(*selection), level)
    runs = selection[0]  # positions in the flattened raster
    flat = flat.cast('B')
    selected = b''.join([flat[s:e] for s, e in zip(runs[::2], runs[1::2])])
    counts = np.bincount(np.frombuffer(selected, np.uint8), minlength=CODE_COUNT)
    if counts.size != CODE_COUNT:
        raise ValueError('code raster holds values outside the contract code space')
    return summarize_ints(counts.tolist(), len(selected), 0, level)  # bincount: int64


fast_select_cells.summarize = fast_summarize  # evaluate_store reduces through it


# ---- measurement and artifacts CLI --------------------------------------------------------

def _median_ms(fn, repeats=200, warmup=30, rounds=3):
    """Best of `rounds` medians of `repeats` timed calls: robust to bursts of machine load."""
    import statistics
    import time
    for _ in range(warmup):
        fn()
    medians = []
    for _ in range(rounds):
        samples = []
        for _ in range(repeats):
            start = time.perf_counter_ns()
            fn()
            samples.append(time.perf_counter_ns() - start)
        medians.append(statistics.median(samples) / 1e6)
    return min(medians)


def _import_ms(statement, repeats=7):
    import statistics
    import subprocess
    import sys
    code = f'import time;t=time.perf_counter();{statement};print((time.perf_counter()-t)*1e3)'
    runs = [float(subprocess.run([sys.executable, '-B', '-c', code], cwd=ROOT, check=True,
                                 capture_output=True, text=True).stdout) for _ in range(repeats)]
    return round(statistics.median(runs), 1)


def import_costs():
    """Median cold-process import time (ms) for each path, in fresh interpreters."""
    return {'stdlib table path: import engine.decision_index': _import_ms('import engine.decision_index'),
            'numpy': _import_ms('import numpy'),
            'registry path: numpy + engine.decision': _import_ms('import engine.decision_index as m;m._numpy()'),
            'numpy + shapely': _import_ms('import numpy, shapely'),
            'v1 select path: engine.query (numpy+shapely)': _import_ms('import engine.query'),
            'rasterio (source/jrc loaders)': _import_ms('import rasterio')}


def fuzz_report(metadata, count, seed=20261015):
    """Exactness and speed of fast_select_cells against select_cells on seeded random polygons.

    `generic` polygons (convex, star, blob) sit in arbitrary position; `boundary` ones put edges,
    vertices and holes exactly on or an ulp from cell centres, which sends centres to exact GEOS.
    """
    from .query import select_cells
    from .tests.test_decision_index import fuzz_geometries
    labels = []
    geoms = fuzz_geometries(metadata, count, seed, labels)
    mismatches, rejected, cells = [], 0, 0
    groups = {'generic': [], 'boundary': []}
    for i, (geometry, label) in enumerate(zip(geoms, labels)):
        results = []
        for fn in (select_cells, fast_select_cells):
            try:
                results.append(('ok', fn(metadata, geometry)))
            except ValueError as exc:
                results.append(('err', str(exc)))
        (ka, a), (kb, b) = results
        if ka != kb or (ka == 'err' and a != b) or (ka == 'ok' and not (
                a[0].dtype == b[0].dtype and np.array_equal(a[0], b[0]) and np.array_equal(a[1], b[1]))):
            mismatches.append(i)
        elif ka == 'err':
            rejected += 1
        else:
            groups['generic' if label in ('convex', 'star', 'blob') else 'boundary'].append(geometry)
            cells += a[0].size
    timing = {}
    for name, members in {**groups, 'all': groups['generic'] + groups['boundary']}.items():
        ms = {fn.__name__: _median_ms(lambda: [fn(metadata, g) for g in members], repeats=3, warmup=1, rounds=3)
              for fn in (select_cells, fast_select_cells)}
        timing[name] = {'polygons': len(members), **{k: round(v, 1) for k, v in ms.items()},
                        'speedup': round(ms['select_cells'] / ms['fast_select_cells'], 2)}
    return {'polygons': count, 'accepted': len(groups['generic']) + len(groups['boundary']),
            'rejected_identically': rejected, 'selected_cells': cells, 'mismatches': len(mismatches),
            'mismatch_indices': mismatches[:10], 'batch_ms': timing}


def main(argv=None):
    import argparse
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out', type=Path, default=OUT)
    parser.add_argument('--fuzz', type=int, default=0, help='also compare fast selection on N seeded random polygons')
    parser.add_argument('--imports', action='store_true', help='also measure cold import costs')
    parser.add_argument('--no-timing', action='store_true')
    args = parser.parse_args(argv)
    if np is None:
        _numpy()
    from . import decision
    from .jrc import load_jrc
    from .query import evaluate, select_cells
    from .source import load_plots, load_source
    source, plots, jrc = load_source(), load_plots(), load_jrc()
    metadata = source.metadata
    screen = decision.derive_screen_codes(source, jrc)
    codes = {decision.SCREEN_VERSION: screen, decision.DECISION_VERSION: decision.project_decision(screen)}
    stores = {level: store_sha256(level, raster, args.out) for level, raster in codes.items()}
    verified = [level for level, raster in codes.items() if check_store(level, raster, args.out, metadata)]
    registry = build_registry(plots, metadata)
    table = build_table(plots, codes, {k: v[0] for k, v in stores.items()}, metadata,
                        {k: v[1] for k, v in stores.items()})
    args.out.mkdir(parents=True, exist_ok=True)
    registry_bytes, table_bytes = registry_to_bytes(registry), table_to_bytes(table)
    (args.out / 'registry.bin').write_bytes(registry_bytes)
    (args.out / 'table.json').write_bytes(table_bytes)
    raw_flat = sum(e['flat_index'].nbytes for e in registry['plots'].values())
    header = struct.unpack_from('<I', registry_bytes, len(MAGIC))[0]
    print(f'registry.bin {len(registry_bytes)} B = {PREFIX_BYTES + header} B header (incl. {PREFIX_BYTES} B prefix and hash) + '
          f'{len(registry_bytes) - PREFIX_BYTES - header} B run-length payload (zstd-19 {zstd_size(registry_bytes)} B; '
          f'plain int32 flat arrays would be {raw_flat} B for '
          f'{sum(e["flat_index"].size for e in registry["plots"].values())} in-chip cells)')
    print(f'table.json {len(table_bytes)} B (zstd-19 {zstd_size(table_bytes)} B); store basis {table["store_basis"]}; '
          f'store files verified equal to derived codes: {verified or "none present"}')
    if not args.no_timing:
        geoms = [p['geometry'] for p in plots]
        ids = [p['plot_id'] for p in plots]
        hashes = [geometry_sha256(g) for g in geoms]
        entries = [registry['plots'][i] for i in ids]
        rows = {'v1 evaluate (17 plots)': _median_ms(lambda: [evaluate(source, g) for g in geoms]),
                'select_cells only': _median_ms(lambda: [select_cells(metadata, g) for g in geoms]),
                'fast_select_cells only': _median_ms(lambda: [fast_select_cells(metadata, g) for g in geoms])}
        for level, raster in codes.items():
            tag = level.split('.')[0].split('-')[1]
            rows[f'{tag}: select_cells + reduce'] = _median_ms(
                lambda: [decision.summarize_selection(raster, *select_cells(metadata, g), level) for g in geoms])
            rows[f'{tag}: fast_select + reduce'] = _median_ms(
                lambda: [decision.summarize_selection(raster, *fast_select_cells(metadata, g), level) for g in geoms])
            rows[f'{tag}: registry_evaluate'] = _median_ms(
                lambda: [registry_evaluate(raster, e, level) for e in entries])
            rows[f'{tag}: registry_lookup + evaluate (hash checked)'] = _median_ms(
                lambda: [registry_evaluate(raster, registry_lookup(registry, i, g, metadata), level)
                         for i, g in zip(ids, geoms)])
            sha = stores[level][0]
            live = {} if stores[level][1].startswith('file:') else {'grid': metadata}  # raster-bytes basis needs the grid
            rows[f'{tag}: table_lookup (precomputed hash)'] = _median_ms(
                lambda: [table_lookup(table, i, h, sha, level, **live) for i, h in zip(ids, hashes)])
            rows[f'{tag}: table_lookup incl. geometry hash'] = _median_ms(
                lambda: [table_lookup(table, i, geometry_sha256(g), sha, level, **live) for i, g in zip(ids, geoms)])
        for name, ms in rows.items():
            print(f'{ms:8.4f} ms  {name}')
    if args.fuzz:
        print(json.dumps(fuzz_report(metadata, args.fuzz)))
    if args.imports:
        print(json.dumps(import_costs(), indent=1))


if __name__ == '__main__':
    main()
