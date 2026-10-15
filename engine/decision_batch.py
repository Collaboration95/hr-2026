"""Bulk answers for many new (unregistered) plot boundaries in one vectorized pass.

evaluate_many(codes, header, geometries) returns exactly what
[evaluate_store(codes, header, g, level, select=fast_select_cells) for g in geometries] returns, and
raises what that loop would raise first. It is the same exact scheme as decision_index.fast_select_cells
(scanline even-odd parity on native centre rows, shapely.covers only for centres near a crossing, a
vertex on a centre row, or a horizontal edge on one), run over every edge of every polygon at once:

- clean GeoJSON is validated and flattened for the whole batch, polygons come from one vectorized
  linearrings/polygons call and one is_valid call, windows from vectorized bounds;
- crossings of all polygons are expanded with np.repeat, sorted by (row, column) in one np.sort, and
  consecutive pairs are the inside spans; the code histogram reads those spans directly (no per-cell
  dense grid), clipped to the chip, with out-of-chip centres counted in selected_count as usual;
- ambiguous centres of all polygons are decided by ONE vectorized shapely.covers call, and replace the
  parity answer for exactly those centres.

Column and row indices come from the analytic inverse of the lattice formula, and are re-derived with the
exact float lattice only where a value lies within 1e-3 cells of a centre, so they match the formula
used by select_cells bit for bit. Anything the batch path does not handle (non-list containers, tuples,
bool or str numbers, non-finite or huge coordinates, invalid polygons, big windows, odd headers, GEOS
errors) is answered by the single-polygon call itself, so rejections are the loop's own exceptions.
Depends on the pinned shapely 2.x (vectorized polygons with None-padded holes, multipolygons(indices=)).
"""
from array import array
from itertools import chain

import numpy as np

from . import decision, decision_index as di

MIN_BATCH = 4  # below this the fixed ~100 us of numpy calls loses to the plain loop, so the loop answers
MAX_SLAB = 20_000  # polygons per pass: bounds the GEOS objects alive at once
MAX_ITEM_CELLS = 400_000  # window cells above which a polygon takes the single path (it row-chunks)
MAX_ITEM_CROSSINGS = 2_000_000  # edge x row crossings above which a polygon takes the single path
CHUNK_COST = 4_000_000  # window cells + 4 x crossings per vectorized chunk
INDEX_LIMIT = 2.0 ** 27  # |lattice index| below which the analytic inverse is accurate to ~1e-7 cells
SUSPECT = 1e-3  # cells: a value this close to a centre/row takes the exact float re-derivation
MAX_EXACT_ROUNDS = 64
_stats = {'batched': 0, 'single': 0}  # items answered by each path in the last call (tests assert on it)


class _Fallback(Exception):
    """The vectorized invariants did not hold; the affected items take the single path."""


def evaluate_many(codes, header, geometries, level=None, on_error='raise'):
    """One summarize_selection output per geometry, in order, equal to the fast_select_cells loop.

    on_error='raise': the exception the loop would raise first (type and message) propagates, after the whole
    batch is evaluated. on_error='return': nothing is raised for a bad geometry; its slot holds the exception
    instance the single call raised. A bad level/header/raster still raises up front, as the loop's first call
    would. An empty input returns [] without looking at the header, as the loop does.
    """
    if on_error not in ('raise', 'return'):
        raise ValueError("on_error must be 'raise' or 'return'")
    geometries = list(geometries)
    if not geometries:
        return []
    held = decision.bind_level(header, level)
    if list(codes.shape) != list(header['shape']):
        raise ValueError('code raster shape differs from the store header')
    out = [None] * len(geometries)
    slow = list(range(len(geometries)))
    lat = _lattice(codes, header) if len(geometries) >= MIN_BATCH else None
    if lat is not None:
        slow = []
        for s in range(0, len(geometries), MAX_SLAB):
            _run(lat, codes, held, geometries, list(range(s, min(s + MAX_SLAB, len(geometries)))), out, slow)
    _stats['batched'], _stats['single'] = len(geometries) - len(slow), len(slow)
    for i in slow:
        try:
            out[i] = decision.evaluate_store(codes, header, geometries[i], level, select=di.fast_select_cells)
        except Exception as exc:
            out[i] = exc
    if on_error == 'raise':
        for item in out:
            if isinstance(item, Exception):
                raise item
    return out


def _lattice(codes, header):
    """(a, c, e, f) when the header is one the vectorized path may take, else None."""
    try:
        if codes.dtype != np.uint8 or codes.ndim != 2:
            return None
        transform = header.get('transform', [])
        if len(transform) != 6 or any(type(v) not in (float, int) or abs(v) >= 2.0 ** 53 for v in transform):
            return None
        a, b, c, d, e, f = (float(v) for v in transform)
        if not all(np.isfinite((a, c, e, f))) or b != 0 or d != 0 or a <= 0 or e >= 0 or header.get('crs') != 'EPSG:4326':
            return None
        if max(abs(c), abs(f)) + 2 ** 51 * max(a, -e) > 1e100:
            return None
        # The analytic index error (cells) must sit far below the SUSPECT band.
        err_c = 8 * 2.0 ** -52 * (2 * abs(c) + 2.2 * INDEX_LIMIT * a) / a
        err_r = 8 * 2.0 ** -52 * (2 * abs(f) + 2.2 * INDEX_LIMIT * -e) / -e
        return (a, c, e, f) if err_c < 1e-4 and err_r < 1e-4 else None
    except Exception:
        return None


def _run(lat, codes, held, geoms, idxs, out, slow):
    try:
        got = _pipeline(lat, codes, held, geoms, idxs)
    except Exception:  # an unexpected GEOS/numpy failure: bisect so one bad item cannot cost the batch
        if len(idxs) == 1:
            slow.extend(idxs)
            return
        mid = len(idxs) // 2
        _run(lat, codes, held, geoms, idxs[:mid], out, slow)
        _run(lat, codes, held, geoms, idxs[mid:], out, slow)
        return
    done, rest = got
    for i, v in done.items():
        out[i] = v
    slow.extend(rest)


# ---- parsing --------------------------------------------------------------------------------------

def _parse(geoms, order, limit):
    """Flatten the items that are exact lists (as decision_index._flat requires); others are left to the single path."""
    pts, kept, npts, ring_lens, part_rings, item_parts, multi = [], [], [], [], [], [], []
    for i in order:
        g = geoms[i]
        mark, rmark, pmark = len(pts), len(ring_lens), len(part_rings)
        try:
            if type(g) is not dict:
                continue
            kind, co = g.get('type'), g.get('coordinates')
            if type(kind) is not str:
                continue
            if kind == 'Polygon':
                parts = (co,)
            elif kind == 'MultiPolygon' and type(co) is list and co:
                parts = co
            else:
                continue
            for rings in parts:
                if type(rings) is not list or not rings:
                    raise ValueError
                for ring in rings:
                    if type(ring) is not list or len(ring) < 4 or ring[0] != ring[-1]:
                        raise ValueError
                    ring_lens.append(len(ring))
                    pts += ring
                part_rings.append(len(rings))
            n = len(pts) - mark
            if n > limit:
                raise ValueError
        except Exception:
            del pts[mark:], ring_lens[rmark:], part_rings[pmark:]
            continue
        kept.append(i)
        npts.append(n)
        item_parts.append(len(parts))
        multi.append(kind == 'MultiPolygon')
    return pts, kept, npts, ring_lens, part_rings, item_parts, multi


def _screen(pts):
    """Positions array when every position is exactly [float|int, float|int] with a representable value, else None."""
    if not pts:
        return np.empty((0, 2))
    if set(map(type, pts)) != {list} or set(map(len, pts)) != {2}:
        return None
    vals = list(chain.from_iterable(pts))
    if not set(map(type, vals)) <= {float, int}:
        return None
    try:
        return np.frombuffer(array('d', vals)).reshape(-1, 2)
    except OverflowError:  # an int beyond float range, as math.isfinite raises in select_cells
        return None


def _clean_parse(geoms, idxs, limit):
    """_parse, then drop (and re-parse without) items whose numbers fail the bulk checks: type, finiteness, size."""
    order = idxs
    while True:
        parsed = _parse(geoms, order, limit)
        pts, kept, npts = parsed[0], parsed[1], parsed[2]
        xy = _screen(pts)
        bad = set()
        if xy is None:
            starts = np.concatenate(([0], np.cumsum(npts))).tolist()
            bad = {q for q in range(len(kept)) if _screen(pts[starts[q]:starts[q + 1]]) is None}
        else:
            ok = (np.abs(xy) < 1e100).all(axis=1)
            if not ok.all():
                bad = set(np.unique(np.repeat(np.arange(len(kept)), npts)[~ok]).tolist())
        if not bad:
            return parsed, xy
        order = [i for q, i in enumerate(kept) if q not in bad]


# ---- exact lattice inverse ------------------------------------------------------------------------

def _first(pred, v, k):
    """Smallest integer k with pred(k, v) true (pred monotone false->true in k), from a guess k that is near.

    Moves k in place, one step per round, only where the guess is off; the guess is exact almost always.
    """
    step = (~pred(k, v)).astype(np.int64) - pred(k - 1, v)  # +1 if too low, -1 if too high
    live = np.flatnonzero(step)
    step = step[live]
    for _ in range(MAX_EXACT_ROUNDS):
        if not live.size:
            return k
        k[live] += step
        kk, vv = k[live], v[live]
        step = (~pred(kk, vv)).astype(np.int64) - pred(kk - 1, vv)
        moving = step != 0
        live, step = live[moving], step[moving]
    if live.size:
        raise _Fallback
    return k


def _col_gt(c, a, v):
    """Per value: number of centres c + (j + .5) * a that are <= v, as the first j with centre > v (searchsorted 'right')."""
    guess = np.floor((v - c) / a - .5).astype(np.int64) + 1
    return _first(lambda j, w: c + (j + .5) * a > w, v, guess)


def _col_ge(c, a, v):
    """First j with centre >= v (searchsorted 'left')."""
    guess = np.ceil((v - c) / a - .5).astype(np.int64)
    return _first(lambda j, w: c + (j + .5) * a >= w, v, guess)


# ---- the batch --------------------------------------------------------------------------------------

def _pipeline(lat, codes, held, geoms, idxs):
    """({index: output}, [indices left to the single path]) for one slab."""
    a, c, e, f = lat
    limit = di._geos()['query'].MAX_GEOMETRY_VERTICES
    parsed, xy = _clean_parse(geoms, idxs, limit)
    pts, kept, npts, ring_lens, part_rings, item_parts, multi = parsed
    done = set(kept)
    rest = [i for i in idxs if i not in done]
    m = len(kept)
    if not m:
        return {}, rest
    g = di._geos()
    shapely, lib = g['shapely'], g['lib']
    with np.errstate(all='ignore'):
        x, y = xy[:, 0], xy[:, 1]
        npts = np.array(npts)
        vstart = np.cumsum(npts) - npts
        vi = np.repeat(np.arange(m), npts)
        minx, maxx = np.minimum.reduceat(x, vstart), np.maximum.reduceat(x, vstart)
        miny, maxy = np.minimum.reduceat(y, vstart), np.maximum.reduceat(y, vstart)
        ext = np.stack(((minx - c) / a - .5, (maxx - c) / a - .5, (maxy - f) / e - .5, (miny - f) / e - .5))
        fast = (np.isfinite(ext) & (np.abs(ext) < INDEX_LIMIT)).all(axis=0)
        ext = np.where(fast, ext, 0.)
        c0, c1 = np.floor(ext[0]).astype(np.int64) - 1, np.ceil(ext[1]).astype(np.int64) + 1
        r0, r1 = np.floor(ext[2]).astype(np.int64) - 1, np.ceil(ext[3]).astype(np.int64) + 1
        R, C = r1 - r0 + 1, c1 - c0 + 1
        fast &= R * C <= MAX_ITEM_CELLS
        tol = di.TOL_ABS + di.TOL_REL * np.maximum(np.abs(minx), np.abs(maxx))
        fast &= tol / a <= 0.05  # tolerance a small fraction of a cell, so near-centre bands stay rare
        tol = np.where(fast, tol, 0.)
        # polygons: one linearrings call, parts with None-padded holes, multipolygons grouped by index
        nr = len(ring_lens)
        rings = shapely.linearrings(xy, indices=np.repeat(np.arange(nr), ring_lens))
        pr = np.array(part_rings)
        pstart = np.cumsum(pr) - pr
        shells = rings[pstart]
        most = int(pr.max()) - 1
        if most:
            holes = np.full((len(pr), most), None, object)
            for h in range(most):
                sel = np.flatnonzero(pr > h + 1)
                holes[sel, h] = rings[pstart[sel] + 1 + h]
            parts = shapely.polygons(shells, holes)
        else:
            parts = lib.polygons(shells, g['no_holes'])
        item_parts = np.array(item_parts)
        first = np.cumsum(item_parts) - item_parts
        polys = parts[first]
        multi = np.array(multi)
        if multi.any():
            part_item = np.repeat(np.arange(m), item_parts)
            pm = multi[part_item]
            rank = np.cumsum(multi) - 1
            polys[multi] = shapely.multipolygons(parts[pm], indices=rank[part_item[pm]])
        live = np.flatnonzero(fast)
        fast[live] = lib.is_valid(polys[live])  # only polygons whose window we use: nothing else is validated or warned about
        R, C = np.where(fast, R, 0), np.where(fast, C, 0)

        # vertex rows: first row k whose centre y is below the vertex (exact where a centre row is close)
        vf = fast[vi]
        u = (y - f) / e - .5
        t = np.where(vf, np.floor(u), 0).astype(np.int64) + 1
        near = vf & (np.abs(u - np.rint(u)) < SUSPECT)
        s = np.flatnonzero(near)
        on_v = np.zeros(len(x), bool)
        rlo_v = np.zeros(len(x), np.int64)
        rect_parts = []
        if s.size:
            ys = y[s]
            rows_lt = lambda k, w: f + (k + .5) * e < w
            ts = _first(rows_lt, ys, t[s])
            klo = _first(lambda k, w: f + (k + .5) * e <= w, ys, ts.copy())
            t[s] = ts
            on = klo < ts
            v_on = s[on]
            on_v[v_on] = True
            rlo_v[v_on] = klo[on]
            item_on = vi[v_on]
            tl = tol[item_on]
            xo = x[v_on]
            rect_parts.append((item_on, klo[on], ts[on], _col_ge(c, a, xo - tl), _col_gt(c, a, xo + tl)))
        ev = np.flatnonzero(_edge_mask(ring_lens, len(x)))
        ev = ev[fast[vi[ev]]]
        eitem = vi[ev]
        x1, x2, y1, y2 = x[ev], x[ev + 1], y[ev], y[ev + 1]
        dx, dy = x2 - x1, y2 - y1
        flat_edge = on_v[ev] & (dy == 0)
        if flat_edge.any():
            fe = np.flatnonzero(flat_edge)
            ie = eitem[fe]
            tl = tol[ie]
            rect_parts.append((ie, rlo_v[ev[fe]], t[ev[fe]], _col_ge(c, a, np.minimum(x1[fe], x2[fe]) - tl),
                               _col_gt(c, a, np.maximum(x1[fe], x2[fe]) + tl)))
        if rect_parts:
            rect = [np.concatenate(p) for p in zip(*rect_parts)]
            o = np.argsort(rect[0], kind='stable')
            rect = [p[o] for p in rect]
        else:
            rect = [np.empty(0, np.int64)] * 5
        t1, t2 = t[ev], t[ev + 1]
        lo = np.maximum(np.minimum(t1, t2), r0[eitem])
        hi = np.minimum(np.maximum(t1, t2), r1[eitem] + 1)
        nc = np.maximum(hi - lo, 0)
        crossings = np.bincount(eitem, weights=nc, minlength=m).astype(np.int64)
        over = fast & (crossings > MAX_ITEM_CROSSINGS)
        if over.any():
            fast &= ~over
            R, C = np.where(fast, R, 0), np.where(fast, C, 0)
            live = fast[eitem]
            ev, eitem, x1, y1, dx, dy, lo, nc = (v[live] for v in (ev, eitem, x1, y1, dx, dy, lo, nc))
        cost = R * C + 4 * crossings * fast
        total = np.cumsum(cost)
        counts = np.zeros((m, decision.CODE_COUNT), np.int64)
        selected = np.zeros(m, np.int64)
        outside = np.zeros(m, np.int64)
        failed = np.zeros(m, bool)
        flat_codes = codes.reshape(-1)
        i0 = 0
        while i0 < m:
            i1 = max(int(np.searchsorted(total, (total[i0 - 1] if i0 else 0) + CHUNK_COST, 'right')), i0 + 1)
            try:
                _chunk(lat, codes, flat_codes, polys, (r0, c0, R, C, tol), (x1, y1, dx, dy, lo, nc, eitem), rect,
                       i0, i1, counts, selected, outside, g)
            except (_Fallback, MemoryError):
                failed[i0:i1] = True
            i0 = i1
    ok = np.flatnonzero(fast & ~failed)
    bad = np.flatnonzero(~(fast & ~failed))
    rest = rest + [kept[q] for q in bad.tolist()]
    return dict(zip((kept[q] for q in ok.tolist()), _summaries(counts[ok], selected[ok], outside[ok], held))), rest


def _summaries(counts, selected, outside, level):
    """decision.summarize_counts for every row (identical dicts), with the sums taken once over the whole array."""
    n = len(counts)
    s = counts[:, decision.LAND:].reshape(n, 3, 6)  # per JRC forest state, per post-2020 year index
    sums = s.sum(axis=2)
    screen = level == decision.SCREEN_VERSION
    land = sums.sum(axis=1)
    unknown = outside + counts[:, 0]
    post = s[:, 1, 1:]
    if screen:
        loss = s[:, :, 1:].sum(axis=1)
        loss_rows = loss.tolist()
        periods = [(key, loss[:, sl].sum(axis=1).tolist()) for key, sl in decision._PERIOD_SLICES]
    keys = decision._YEAR_KEYS
    forest_states = decision.FOREST_STATES
    out = []
    rows = zip(selected.tolist(), outside.tolist(), unknown.tolist(), counts[:, 1].tolist(), land.tolist(), sums.tolist(),
               post.tolist(), post.sum(axis=1).tolist(), s[:, 2, 1:].sum(axis=1).tolist())
    for i, (sel, outs, unk, water, ld, (nf, fo, fu), yr, total, fu_post) in enumerate(rows):
        ok = ld > 0
        res = {'contract': level, 'selected_cell_count': sel, 'out_of_coverage_cell_count': outs,
               'valid_land_cell_count': ld, 'water_cell_count': water, 'unknown_cell_count': unk,
               'forest_2020': {'cell_counts': dict(zip(forest_states, (nf, fo, fu))) if ok else None,
                               'present': None if not ok else True if fo > 0 else (False if unk + fu == 0 else None)},
               'deforestation_after_2020': {
                   'yearly_cell_counts': dict(zip(keys, yr)) if ok else None, 'cell_count': total if ok else None,
                   'present': None if not ok else True if total > 0 else (False if unk + fu_post == 0 else None)}}
        if screen:
            res['hansen_loss_after_2020'] = {
                'yearly_cell_counts': dict(zip(keys, loss_rows[i])) if ok else None,
                'periods': {key: {'observed_loss_cell_count': v[i] if ok else None,
                                  'mapped_loss_present': None if not ok else True if v[i] > 0 else (False if unk == 0 else None)}
                            for key, v in periods}}
        res['support'] = 'none' if sel == 0 or ld == 0 else 'partial' if unk or fu else 'complete'
        out.append(res)
    return out


def _edge_mask(ring_lens, n):
    """Start-vertex mask of the segments inside rings: all vertex pairs except those joining two rings."""
    keep = np.ones(n - 1, bool)
    keep[np.cumsum(ring_lens)[:-1] - 1] = False
    return keep


def _chunk(lat, codes, flat_codes, polys, win, edges, rect, i0, i1, counts, selected, outside, g):
    """Fill counts/selected/outside for items [i0, i1) of a slab."""
    a, c, e, f = lat
    r0, c0, R, C, tol = (v[i0:i1] for v in win)
    n = i1 - i0
    H, W = codes.shape
    x1, y1, dx, dy, lo, nc, eitem = edges
    e0, e1 = np.searchsorted(eitem, (i0, i1))
    nce = nc[e0:e1]
    # window rows as groups; flat cell index = rowflat[group] + column in window
    rowbase = np.cumsum(R) - R
    Rt = int(R.sum())
    Cg = np.repeat(C, R)
    rowflat = np.cumsum(Cg) - Cg
    item_g = np.repeat(np.arange(n), R)
    rowabs_g = np.repeat(r0 - rowbase, R) + np.arange(Rt)
    c0_g = np.repeat(c0, R)
    W1 = int(C.max(initial=0)) + 1
    # crossings of every row with every edge that spans it, at the same float formula as fast_select_cells
    E = int(nce.sum())
    cs = np.cumsum(nce) - nce
    ie = eitem[e0:e1] - i0
    k = np.repeat(lo[e0:e1] - cs, nce) + np.arange(E)
    grp = np.repeat(rowbase[ie] - r0[ie], nce) + k
    xc = np.repeat(x1[e0:e1], nce) + (f + (k + .5) * e - np.repeat(y1[e0:e1], nce)) \
        / np.repeat(dy[e0:e1], nce) * np.repeat(dx[e0:e1], nce)
    u = (xc - c) / a - .5
    j = np.floor(u).astype(np.int64) + 1  # centres <= crossing: first centre right of it
    thr = SUSPECT + 4 * float(tol.max(initial=0.)) / a
    s = np.flatnonzero(np.abs(u - np.rint(u)) < thr)
    near_flat = []
    if s.size:
        xs, gs_ = xc[s], grp[s]
        it = item_g[gs_]
        j[s] = _col_gt(c, a, xs)
        tl = tol[it]
        jl, jh = _col_ge(c, a, xs - tl) - c0[it], _col_gt(c, a, xs + tl) - c0[it]
        lo_c, hi_c = np.clip(jl, 0, C[it]), np.clip(jh, 0, C[it])
        nr = hi_c > lo_c
        near_flat = [(gs_[nr], lo_c[nr], hi_c[nr])]
    key = np.sort(grp * W1 + np.clip(j - c0_g[grp], 0, Cg[grp]), kind='stable')  # runs per edge: timsort ~2x quicksort
    if E & 1:
        raise _Fallback
    ss, ee = key[0::2], key[1::2]
    gsp = ss // W1
    if (ee // W1 != gsp).any():
        raise _Fallback
    ks, ke = ss - gsp * W1, ee - gsp * W1
    nz = ke > ks
    gsp, ks, ke = gsp[nz], ks[nz], ke[nz]
    s_item, s_row, s_c0 = item_g[gsp], rowabs_g[gsp], c0_g[gsp]
    lens = ke - ks
    sel = np.bincount(s_item, weights=lens, minlength=n).astype(np.int64)
    # in-chip part of every span; out-of-chip centres stay in the selected count only
    ca, cb = np.maximum(s_c0 + ks, 0), np.minimum(s_c0 + ke, W)
    ln = np.where((s_row >= 0) & (s_row < H), np.maximum(cb - ca, 0), 0)
    total = int(ln.sum())
    ics = np.cumsum(ln) - ln
    idx = np.repeat(s_row * W + ca - ics, ln) + np.arange(total)
    cv = flat_codes.take(idx)
    if total and cv.max() >= decision.CODE_COUNT:
        raise _Fallback
    hist = np.bincount(np.repeat(s_item * decision.CODE_COUNT, ln) + cv, minlength=n * decision.CODE_COUNT)
    # ambiguous centres: union of the intervals, decided by exact covers, replacing the parity answer
    a0, a1 = np.searchsorted(rect[0], (i0, i1))
    lo_f, hi_f = [], []
    if a0 < a1:
        it = rect[0][a0:a1] - i0
        rl, rh = np.clip(rect[1][a0:a1] - r0[it], 0, R[it]), np.clip(rect[2][a0:a1] - r0[it], 0, R[it])
        cl, ch = np.clip(rect[3][a0:a1] - c0[it], 0, C[it]), np.clip(rect[4][a0:a1] - c0[it], 0, C[it])
        v = (rh > rl) & (ch > cl)
        it, rl, rh, cl, ch = it[v], rl[v], rh[v], cl[v], ch[v]
        nrw = rh - rl
        cn = np.cumsum(nrw) - nrw
        gg = np.repeat(rowbase[it] + rl - cn, nrw) + np.arange(int(nrw.sum()))
        lo_f.append(rowflat[gg] + np.repeat(cl, nrw))
        hi_f.append(rowflat[gg] + np.repeat(ch, nrw))
    for gn, lc, hc in near_flat:
        lo_f.append(rowflat[gn] + lc)
        hi_f.append(rowflat[gn] + hc)
    if lo_f:
        lo_f, hi_f = np.concatenate(lo_f), np.concatenate(hi_f)
        ln_f = hi_f - lo_f
        cf = np.cumsum(ln_f) - ln_f
        af = np.unique(np.repeat(lo_f - cf, ln_f) + np.arange(int(ln_f.sum())))
    else:
        af = np.empty(0, np.int64)
    if af.size:
        ga = np.searchsorted(rowflat, af, 'right') - 1
        ia, ra, ca_ = item_g[ga], rowabs_g[ga], c0_g[ga] + af - rowflat[ga]
        sf = rowflat[gsp] + ks
        pos = np.searchsorted(sf, af, 'right') - 1
        par = (pos >= 0) & (af < (rowflat[gsp] + ke)[np.maximum(pos, 0)]) if sf.size else np.zeros(af.size, bool)
        coords = np.empty((af.size, 2))
        coords[:, 0], coords[:, 1] = c + (ca_ + .5) * a, f + (ra + .5) * e
        counts_a = np.bincount(ia, minlength=n)
        if (counts_a > di.PREPARE_POINTS).any():
            g['shapely'].prepare(polys[i0:i1][counts_a > di.PREPARE_POINTS])
        truth = g['lib'].covers(polys[i0:i1][ia], g['lib'].points(coords, g['allow']))
        delta = truth.astype(np.int64) - par
        ch_ = np.flatnonzero(delta)
        if ch_.size:
            sel += np.bincount(ia[ch_], weights=delta[ch_], minlength=n).astype(np.int64)
            inc = (ra[ch_] >= 0) & (ra[ch_] < H) & (ca_[ch_] >= 0) & (ca_[ch_] < W)
            w_ = ch_[inc]
            cva = flat_codes.take(ra[w_] * W + ca_[w_])
            if cva.size and cva.max() >= decision.CODE_COUNT:
                raise _Fallback
            hist = hist + np.rint(np.bincount(ia[w_] * decision.CODE_COUNT + cva, weights=delta[w_],
                                              minlength=n * decision.CODE_COUNT)).astype(np.int64)
    counts[i0:i1] = hist.reshape(n, decision.CODE_COUNT)
    selected[i0:i1] = sel
    outside[i0:i1] = sel - hist.reshape(n, decision.CODE_COUNT).sum(axis=1)
