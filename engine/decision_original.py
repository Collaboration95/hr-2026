"""Independent original-layers path for the decision contracts.

Facts are read straight from the original Hansen and JRC arrays: the JRC cell under
each Hansen centre comes from a float affine lookup, not the integer ratio and offset
used by engine.decision. Nothing here calls engine.decision or its code space. The
proof compares this path with the derived and decoded code rasters, cell by cell
and polygon by polygon. Outputs are mapped observations, never legal findings.
"""
import numpy as np

from .query import select_cells

SCREEN, DECISION = 'eudr-screen.v1', 'eudr-decision.v1'
YEARS = range(2021, 2026)
PERIODS = {'2021-2023': (2021, 2023), '2024-2025': (2024, 2025)}
FOREST = ('nonforest', 'forest', 'unknown')


def cell_attributes(hansen, jrc, rows, cols):
    """Facts for in-chip Hansen cells (arrays of any shape) from the original layers.

    hansen: unknown unless all three Hansen band masks are valid (v1's known_bands; the
    treecover2000 value is ignored but its mask counts), else water/land by the datamask
    value. forest: JRC 2020 class at the Hansen centre, unknown outside the JRC chip or
    under a False JRC mask. loss_year: 2000+lossyear for lossyear >= 21, else 0 (none).
    A valid cell with lossyear above 25 or datamask above 2 is refused.
    """
    rows, cols = np.asarray(rows, np.int64), np.asarray(cols, np.int64)
    height, width = hansen.metadata['shape']
    if rows.shape != cols.shape or ((rows < 0) | (rows >= height) | (cols < 0) | (cols >= width)).any():
        raise ValueError('cells must lie inside the Hansen chip')
    a, _, c, _, e, f = hansen.metadata['transform']
    ja, _, jc, _, je, jf = jrc.metadata['transform']
    x, y = c + (cols + .5) * a, f + (rows + .5) * e
    jcol = np.floor((x - jc) / ja).astype(np.int64)
    jrow = np.floor((y - jf) / je).astype(np.int64)
    jh, jw = jrc.values.shape
    within = (jrow >= 0) & (jrow < jh) & (jcol >= 0) & (jcol < jw)
    jr, jcc = np.where(within, jrow, 0), np.where(within, jcol, 0)
    usable = within & jrc.mask[jr, jcc]
    class_value = jrc.values[jr, jcc]
    forest = np.full(rows.shape, 'unknown', 'U9')
    forest[usable & (class_value == 0)] = 'nonforest'
    forest[usable & (class_value == 1)] = 'forest'
    known = hansen.masks[:, rows, cols].all(axis=0)
    mask_value = hansen.bands[2][rows, cols]
    if (mask_value[known] > 2).any():
        raise ValueError('datamask above 2 on a valid cell')
    land_class = np.full(rows.shape, 'unknown', 'U7')
    land_class[known & (mask_value == 1)] = 'land'
    land_class[known & (mask_value == 2)] = 'water'
    lossyear = hansen.bands[1][rows, cols].astype(np.int16)
    year = np.where(lossyear >= 21, 2000 + lossyear, 0).astype(np.int16)
    if (year[known] > YEARS[-1]).any():
        raise ValueError('loss year beyond the supported 2025 horizon')
    return {'hansen': land_class, 'forest': forest, 'loss_year': year,
            'jrc_row': np.where(within, jrow, -1), 'jrc_col': np.where(within, jcol, -1)}


def _effective_year(attrs, level):
    """Loss year the contract keeps: the decision level forgets loss on non-forest land."""
    if level not in (SCREEN, DECISION):
        raise ValueError('unknown contract level')
    year = attrs['loss_year']
    return np.where(attrs['forest'] == 'nonforest', 0, year) if level == DECISION else year


def exhaustive_attribute_codes(hansen, jrc, level=SCREEN):
    """One uint8 code per Hansen cell from float-path attributes.

    unknown 0, water 1, land 2 + 6*forest_state + post_index with forest_state
    nonforest 0 / forest 1 / unknown 2 and post_index 0 none or 1..5 for 2021..2025.
    """
    height, width = hansen.metadata['shape']
    rows, cols = np.meshgrid(np.arange(height), np.arange(width), indexing='ij')
    attrs = cell_attributes(hansen, jrc, rows, cols)
    year = _effective_year(attrs, level)
    state = np.select([attrs['forest'] == 'nonforest', attrs['forest'] == 'forest'], [0, 1], 2)
    post = np.where(year > 0, year - 2020, 0)
    codes = np.zeros((height, width), np.uint8)
    codes[attrs['hansen'] == 'water'] = 1
    land = attrs['hansen'] == 'land'
    codes[land] = (2 + 6 * state + post)[land]
    return codes


def reduce_cells(attrs, selected, outside, level=SCREEN):
    """Contract output from in-chip cell attributes plus the out-of-chip selected count."""
    year = _effective_year(attrs, level)
    land_class, forest = attrs['hansen'], attrs['forest']
    is_land = land_class == 'land'
    unknown = outside + int((land_class == 'unknown').sum())
    land = int(is_land.sum())
    analytical = land > 0

    def flag(count, blockers):
        return None if not analytical else True if count > 0 else (False if blockers == 0 else None)

    by_forest = {s: int((is_land & (forest == s)).sum()) for s in FOREST}
    deforested = {str(y): int((is_land & (forest == 'forest') & (year == y)).sum()) for y in YEARS}
    blocked_loss = int((is_land & (forest == 'unknown') & (year > 0)).sum())
    total = sum(deforested.values())
    out = {'contract': level, 'selected_cell_count': int(selected), 'out_of_coverage_cell_count': int(outside),
           'valid_land_cell_count': land, 'water_cell_count': int((land_class == 'water').sum()),
           'unknown_cell_count': unknown,
           'forest_2020': {'cell_counts': by_forest if analytical else None,
                           'present': flag(by_forest['forest'], unknown + by_forest['unknown'])},
           'deforestation_after_2020': {'yearly_cell_counts': deforested if analytical else None,
                                        'cell_count': total if analytical else None,
                                        'present': flag(total, unknown + blocked_loss)}}
    if level == SCREEN:
        loss = {str(y): int((is_land & (year == y)).sum()) for y in YEARS}
        periods = {}
        for key, (first, last) in PERIODS.items():
            count = int((is_land & (year >= first) & (year <= last)).sum())
            periods[key] = {'observed_loss_cell_count': count if analytical else None,
                            'mapped_loss_present': flag(count, unknown)}
        out['hansen_loss_after_2020'] = {'yearly_cell_counts': loss if analytical else None, 'periods': periods}
    out['support'] = ('none' if not selected or not land else
                      'partial' if unknown or by_forest['unknown'] else 'complete')
    return out


def evaluate_original(hansen, jrc, geometry, level=SCREEN):
    """Answer one polygon from the original layers with the shared centre rule."""
    if level not in (SCREEN, DECISION):
        raise ValueError('unknown contract level')
    rows, cols = select_cells(hansen.metadata, geometry)
    height, width = hansen.metadata['shape']
    inside = (rows >= 0) & (rows < height) & (cols >= 0) & (cols < width)
    attrs = cell_attributes(hansen, jrc, rows[inside], cols[inside])
    return reduce_cells(attrs, rows.size, int((~inside).sum()), level)
