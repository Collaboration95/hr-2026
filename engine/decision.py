"""Decision-preserving EUDR layers derived from the pinned Hansen and JRC chips.

Layer analysis made executable: each Hansen cell is reduced to the facts an EUDR
screen needs (valid land/water/unknown, JRC 2020 forest class at the cell centre,
post-cut-off loss year). treecover2000 and pre-2021 loss years are dropped.

Two contracts share one code space so a single uint8 raster answers both:

- eudr-screen.v1 keeps post-2020 Hansen loss on all land (the supplier's own
  Hansen-only check) and JRC 2020 forest at each Hansen centre.
- eudr-decision.v1 drops loss years on JRC 2020 non-forest land: only forest at
  the cut-off and deforestation since remain.

Every output is a function of the selected cell codes plus the out-of-chip count,
so cell-for-cell code equality implies identical outputs for every polygon under
the shared centre rule. A raster is only meaningful with its level: callers pass it
explicitly (no default), and evaluate_store takes it from the decoded store's header
and refuses a conflicting request. Outputs are mapped observations, never legal findings.
"""
import numpy as np

SCREEN_VERSION = 'eudr-screen.v1'
DECISION_VERSION = 'eudr-decision.v1'
LEVELS = (SCREEN_VERSION, DECISION_VERSION)
CUTOFF_LOSSYEAR = 20  # Hansen lossyear 20 is 2020; EUDR cut-off is 31 Dec 2020.
POST_YEARS = tuple(range(2021, 2026))
MAX_LOSSYEAR = POST_YEARS[-1] - 2000  # the last year the code space holds (post index 1..5)
PERIODS = {'2021-2023': (2021, 2023), '2024-2025': (2024, 2025)}
FOREST_STATES = ('nonforest', 'forest', 'unknown')
UNKNOWN, WATER, LAND = 0, 1, 2
CODE_COUNT = LAND + 6 * len(FOREST_STATES)  # 20 codes: 0..19
GRID_RULE = ('JRC 2020 class read at each Hansen cell centre; the JRC lattice nests '
             'the Hansen lattice by an odd integer ratio, so the centre is a JRC cell centre')


def land_code(forest_state, post_year_index):
    """forest_state 0/1/2 = nonforest/forest/unknown; post_year_index 0 none, 1..5 = 2021..2025."""
    return LAND + 6 * forest_state + post_year_index


def nested_offsets(hansen_metadata, jrc_metadata):
    """Exact integer mapping from Hansen centres to JRC cells, or refuse to resample.

    Returns (ratio, row_offset, col_offset) so Hansen centre (r, c) lies at the
    centre of JRC cell (ratio*r + row_offset, ratio*c + col_offset).
    """
    a, b, c, d, e, f = hansen_metadata['transform']
    ja, jb, jc, jd, je, jf = jrc_metadata['transform']
    if b or d or jb or jd or hansen_metadata.get('crs') != jrc_metadata.get('crs'):
        raise ValueError('grids must be north-up in the same CRS')
    ratio = a / ja
    k = round(ratio)
    if k < 1 or k % 2 == 0 or abs(ratio - k) > 1e-9 or abs(e / je - k) > 1e-9:
        raise ValueError('JRC lattice must nest Hansen cells by an odd integer ratio')
    col0, row0 = (c - jc) / ja, (f - jf) / je
    if abs(col0 - round(col0)) > 1e-6 or abs(row0 - round(row0)) > 1e-6:
        raise ValueError('Hansen and JRC lattices are not aligned; resampling is not authorized')
    half = k // 2
    return k, round(row0) + half, round(col0) + half


def derive_screen_codes(hansen, jrc):
    """Derive the eudr-screen.v1 code raster on the Hansen grid from original arrays.

    A cell is known only if all three Hansen band masks are valid (as in v1's known_bands),
    so an invalid treecover2000 mask makes the cell unknown even though its value is dropped.
    Lossyear above 25 or datamask above 2 on a known cell is refused: it would alias the next
    forest state's codes. Loss in 2001-2020 on a JRC 2020 forest cell (4,813 on the chip) is
    kept as forest: JRC 2020 is the authority for the cut-off state, Hansen loss only dates
    what happened after it.
    """
    height, width = hansen.metadata['shape']
    loss, datamask = hansen.bands[1], hansen.bands[2]
    known = hansen.masks.all(axis=0)
    if (loss[known] > MAX_LOSSYEAR).any() or (datamask[known] > 2).any():
        raise ValueError(f'Hansen lossyear above {MAX_LOSSYEAR} or datamask above 2 on a valid cell')
    k, row_offset, col_offset = nested_offsets(hansen.metadata, jrc.metadata)
    jrows = k * np.arange(height) + row_offset
    jcols = k * np.arange(width) + col_offset
    rows_ok = (jrows >= 0) & (jrows < jrc.values.shape[0])
    cols_ok = (jcols >= 0) & (jcols < jrc.values.shape[1])
    forest = np.full((height, width), 2, np.uint8)
    block = np.ix_(rows_ok, cols_ok)
    sampled = np.ix_(jrows[rows_ok], jcols[cols_ok])
    forest[block] = np.where(jrc.mask[sampled], jrc.values[sampled], 2)
    post = np.where(loss > CUTOFF_LOSSYEAR, loss - CUTOFF_LOSSYEAR, 0).astype(np.uint8)
    codes = np.full((height, width), UNKNOWN, np.uint8)
    codes[known & (datamask == 2)] = WATER
    land = known & (datamask == 1)
    codes[land] = land_code(forest[land], post[land])
    return codes


def project_decision(screen_codes):
    """eudr-decision.v1: forget loss years on JRC 2020 non-forest land."""
    codes = screen_codes.copy()
    codes[(codes > LAND) & (codes < LAND + 6)] = LAND
    return codes


_YEAR_KEYS = tuple(str(y) for y in POST_YEARS)
_PERIOD_SLICES = tuple((key, slice(lo - POST_YEARS[0], hi - POST_YEARS[0] + 1)) for key, (lo, hi) in PERIODS.items())


def summarize_counts(counts, selected_count, outside_count, level):
    """Contract outputs from a 20-bin code histogram plus out-of-chip selections."""
    if level not in LEVELS:
        raise ValueError('unknown contract level')
    if isinstance(counts, np.ndarray) and counts.dtype.kind in 'iu':
        counts = counts.tolist()
    else:
        counts = [int(v) for v in counts]
    if len(counts) != CODE_COUNT or selected_count != sum(counts) + outside_count or outside_count < 0:
        raise ValueError('code histogram accounting mismatch')
    s0, s1, s2 = (counts[LAND + 6 * s:LAND + 6 * s + 6] for s in range(3))  # per JRC forest state
    nonforest, forest, funk = sum(s0), sum(s1), sum(s2)
    land = nonforest + forest + funk
    unknown = outside_count + counts[UNKNOWN]
    analytical = land > 0
    forest_counts = {'nonforest': nonforest, 'forest': forest, 'unknown': funk}  # FOREST_STATES order
    deforested = dict(zip(_YEAR_KEYS, s1[1:]))
    total = sum(s1[1:])

    def tri(count, blockers):
        if not analytical:
            return None
        return True if count > 0 else (False if blockers == 0 else None)

    out = {'contract': level, 'selected_cell_count': selected_count,
           'out_of_coverage_cell_count': outside_count, 'valid_land_cell_count': land,
           'water_cell_count': counts[WATER], 'unknown_cell_count': unknown,
           'forest_2020': {'cell_counts': forest_counts if analytical else None,
                           'present': tri(forest, unknown + funk)},
           'deforestation_after_2020': {
               'yearly_cell_counts': deforested if analytical else None,
               'cell_count': total if analytical else None,
               'present': tri(total, unknown + sum(s2[1:]))}}
    if level == SCREEN_VERSION:
        loss = [x + y + z for x, y, z in zip(s0[1:], s1[1:], s2[1:])]
        periods = {}
        for key, sl in _PERIOD_SLICES:
            n = sum(loss[sl])
            periods[key] = {'observed_loss_cell_count': n if analytical else None,
                            'mapped_loss_present': tri(n, unknown)}
        out['hansen_loss_after_2020'] = {
            'yearly_cell_counts': dict(zip(_YEAR_KEYS, loss)) if analytical else None, 'periods': periods}
    # Support covers both layers: a land cell without a JRC 2020 class is partial.
    out['support'] = ('none' if selected_count == 0 or land == 0 else
                      'partial' if unknown or funk else 'complete')
    return out


def evaluate_codes(codes, metadata, geometry, level):
    """Answer one polygon from a code raster of a known level with the shared centre rule.

    The codes alone cannot say which level they hold (a decision raster read as screen reports
    zero Hansen loss), so level is required. For a raster decoded from a store use evaluate_store.
    """
    from .query import select_cells  # Lazy: registered-plot paths never need GEOS.
    rows, cols = select_cells(metadata, geometry)
    return summarize_selection(codes, rows, cols, level)


def bind_level(header, level=None):
    """The level a decoded store holds, from its header; a different requested level is refused."""
    held = header.get('level') if isinstance(header, dict) else None
    if held not in LEVELS:
        raise ValueError('store header does not name a contract level')
    if level is not None and level != held:
        raise ValueError(f'store holds {held}, not {level}')
    return held


def evaluate_store(codes, header, geometry, level=None, select=None):
    """Answer one polygon from a read_store result, at the level its header records.

    level, if given, must equal header['level']. select(header, geometry) -> (rows, cols)
    defaults to engine.query.select_cells; the raster must have the header's shape.
    """
    held = bind_level(header, level)
    if list(codes.shape) != list(header['shape']):
        raise ValueError('code raster shape differs from the store header')
    if select is None:
        from .query import select_cells as select  # Lazy: registered-plot paths never need GEOS.
    return summarize_selection(codes, *select(header, geometry), held)


def summarize_selection(codes, rows, cols, level):
    height, width = codes.shape
    inside = (rows >= 0) & (rows < height) & (cols >= 0) & (cols < width)
    counts = np.bincount(codes[rows[inside], cols[inside]], minlength=CODE_COUNT)
    if counts.size != CODE_COUNT:
        raise ValueError('code raster holds values outside the contract code space')
    return summarize_counts(counts, int(rows.size), int((~inside).sum()), level)
