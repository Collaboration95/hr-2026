"""Independent JRC scalar membership/reduction; GEOS validates topology only.

Uses W2's scalar ray casting with exact Fraction fallback, never production
selection/reduction. Centers use the chip affine arithmetic; no tolerance buffer.
"""
import math
from .oracle import _polygons, _covered


def oracle_jrc(dataset, geometry, missing_band=False):
    dataset.validate()
    if type(missing_band) is not bool:
        raise ValueError('missing_band must be bool')
    polygons = _polygons(geometry)
    points = [p for polygon in polygons for ring in polygon for p in ring]
    a, _, c, _, e, f = dataset.metadata['transform']
    extents = ((min(p[0] for p in points)-c)/a, (max(p[0] for p in points)-c)/a,
               (max(p[1] for p in points)-f)/e, (min(p[1] for p in points)-f)/e)
    if not all(math.isfinite(x) and abs(x) < 2**62 for x in extents):
        raise ValueError('oracle grid extent limit')
    c0, c1, r0, r1 = math.floor(extents[0])-1, math.ceil(extents[1])+1, math.floor(extents[2])-1, math.ceil(extents[3])+1
    if (c1-c0+1)*(r1-r0+1) > 2_000_000:
        raise ValueError('oracle scan exceeds limit')
    selected = covered = valid = invalid = outside = 0
    counts = {'0': 0, '1': 0}
    h, w = dataset.values.shape
    for row in range(r0, r1+1):
        for col in range(c0, c1+1):
            if not _covered((c+(col+.5)*a, f+(row+.5)*e), polygons):
                continue
            selected += 1
            if row < 0 or col < 0 or row >= h or col >= w:
                outside += 1
            else:
                covered += 1
                if missing_band or not dataset.mask[row, col]:
                    invalid += 1
                else:
                    valid += 1
                    counts[str(int(dataset.values[row, col]))] += 1
    unknown = selected if missing_band else outside + invalid
    reasons = []
    if selected == 0: reasons.append('no_selected_cells')
    if outside: reasons.append('out_of_coverage')
    if invalid: reasons.append('band_mask_invalid')
    if selected and not valid: reasons.append('no_valid_cells')
    if missing_band: reasons.append('missing_band')
    flag = None
    if valid and not missing_band:
        if counts['1'] > 0: flag = True
        elif unknown == 0: flag = False
    return {'selected_cell_count': selected, 'in_coverage_cell_count': covered,
            'out_of_coverage_cell_count': outside, 'valid_cell_count': valid,
            'unknown_cell_count': unknown, 'class_counts': counts if valid and not missing_band else None,
            'mapped_forest_present': flag,
            'support': 'unavailable' if missing_band else 'none' if valid == 0 else 'partial' if unknown else 'complete',
            'unknown_reasons': reasons}
