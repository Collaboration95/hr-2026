"""Slow, independent reference for the Hansen cell-center query contract.

Selection uses scalar ray casting; aggregation uses scalar counters. No query
module or query helpers are imported. GEOS checks input topology only; it never
selects cells. This is encoding/query evidence, not satellite ground truth.
"""
from fractions import Fraction
import math
import sys

import numpy as np
from shapely.geometry import shape

from .model import BAND_NAMES, Dataset

# Bound work before entering the scalar scan. This is not a production query.
MAX_CANDIDATE_CELLS = 2_000_000
MAX_GEOMETRY_VERTICES = 10_000


def _orientation(a, b, p):
    """Sign of the determinant, with an exact fallback near cancellation.

    The bound triggers exact arithmetic, not geometric buffering. Fractions
    preserve the input binary floats exactly, so no point is moved or snapped.
    """
    dx, dy = b[0] - a[0], b[1] - a[1]
    px, py = p[0] - a[0], p[1] - a[1]
    left, right = dx * py, dy * px
    det = left - right
    if math.isfinite(det) and abs(det) > 8 * sys.float_info.epsilon * (abs(left) + abs(right)):
        return 1 if det > 0 else -1
    ax, ay, bx, by, x, y = map(Fraction, (*a, *b, *p))
    exact = (bx - ax) * (y - ay) - (by - ay) * (x - ax)
    return (exact > 0) - (exact < 0)


def _ring_location(point, ring):
    """Return -1 outside, 0 on boundary, 1 inside a closed ring."""
    x, y = point
    inside = False
    for a, b in zip(ring, ring[1:]):
        turn = _orientation(a, b, point)
        if turn == 0 and min(a[0], b[0]) <= x <= max(a[0], b[0]) and min(a[1], b[1]) <= y <= max(a[1], b[1]):
            return 0
        # Half-open vertical test counts vertices once. Orientation replaces
        # division by the edge slope and treats horizontal edges separately.
        if (a[1] > y) != (b[1] > y):
            if (b[1] > a[1] and turn > 0) or (b[1] < a[1] and turn < 0):
                inside = not inside
    return 1 if inside else -1


def _covered(point, polygons):
    for rings in polygons:
        outer = _ring_location(point, rings[0])
        if outer < 0:
            continue
        if outer == 0:
            return True
        holes = [_ring_location(point, ring) for ring in rings[1:]]
        if 0 in holes:  # Polygon.covers includes a hole's boundary.
            return True
        if 1 not in holes:
            return True
    return False


def _polygons(geometry):
    if not isinstance(geometry, dict) or geometry.get('type') not in ('Polygon', 'MultiPolygon'):
        raise ValueError('oracle requires a Polygon or MultiPolygon geometry')
    coordinates = geometry.get('coordinates')
    polygons = [coordinates] if geometry['type'] == 'Polygon' else coordinates
    if not isinstance(polygons, (list, tuple)) or not polygons:
        raise ValueError('geometry must contain polygons')
    normalized, vertex_count = [], 0
    for rings in polygons:
        if not isinstance(rings, (list, tuple)) or not rings:
            raise ValueError('polygon must contain an exterior ring')
        normalized_rings = []
        for ring in rings:
            if not isinstance(ring, (list, tuple)) or len(ring) < 4:
                raise ValueError('rings require at least four closed positions')
            vertex_count += len(ring)
            if vertex_count > MAX_GEOMETRY_VERTICES:
                raise ValueError('geometry exceeds oracle vertex limit')
            positions = []
            for position in ring:
                if not isinstance(position, (list, tuple)) or len(position) != 2:
                    raise ValueError('positions must be two-dimensional')
                if any(isinstance(v, bool) or not isinstance(v, (int, float)) for v in position):
                    raise ValueError('positions must be finite numbers')
                try:
                    point = tuple(float(v) for v in position)
                except (OverflowError, ValueError) as exc:
                    raise ValueError('positions must be finite numbers') from exc
                if not all(math.isfinite(v) for v in point):
                    raise ValueError('positions must be finite numbers')
                positions.append(point)
            if positions[0] != positions[-1]:
                raise ValueError('ring must be explicitly closed')
            normalized_rings.append(positions)
        normalized.append(normalized_rings)
    # Validation is intentionally separate from scalar membership. It accepts
    # valid touching topology and rejects self-crossings/overlapping islands.
    try:
        parsed = shape({'type': geometry['type'], 'coordinates': normalized[0] if geometry['type'] == 'Polygon' else normalized})
        if parsed.is_empty or not parsed.is_valid:
            raise ValueError('invalid polygon topology')
    except Exception as exc:
        if isinstance(exc, ValueError):
            raise
        raise ValueError('invalid polygon topology') from exc
    return normalized


def _grid(dataset):
    bands, masks, metadata = dataset.bands, dataset.masks, dataset.metadata
    if not isinstance(bands, np.ndarray) or bands.dtype != np.uint8 or bands.ndim != 3 or bands.shape[0] != 3:
        raise ValueError('bands must be uint8 [3,height,width]')
    if not isinstance(masks, np.ndarray) or masks.dtype != np.bool_ or masks.shape != bands.shape:
        raise ValueError('masks must be bool with the bands shape')
    height, width = bands.shape[1:]
    if min(height, width) < 1 or metadata.get('shape') != [height, width]:
        raise ValueError('metadata shape must match a nonempty grid')
    for band, maximum in enumerate((100, 25, 2)):
        if np.any(bands[band] > maximum):
            raise ValueError(f'{BAND_NAMES[band]} raw value outside 0..{maximum}')
    transform = metadata.get('transform')
    if not isinstance(transform, (list, tuple)) or len(transform) != 6:
        raise ValueError('grid requires six affine coefficients')
    try:
        a, b, c, d, e, f = map(float, transform)
    except (TypeError, ValueError, OverflowError) as exc:
        raise ValueError('invalid affine coefficients') from exc
    if not all(math.isfinite(v) for v in (a, b, c, d, e, f)) or a <= 0 or e >= 0 or b != 0 or d != 0:
        raise ValueError('oracle supports only native north-up grids')
    if metadata.get('crs') != 'EPSG:4326':
        raise ValueError('oracle requires EPSG:4326')
    return height, width, a, c, e, f


def oracle_evaluate(dataset: Dataset, geometry: dict, missing_bands: tuple[str, ...] = ()) -> dict:
    """Evaluate the documented contract without using engine.query.

    A conservative bounding window includes one spare row/column at each edge;
    exact scalar membership removes those extras. Outside-chip centers remain
    in the scan. An excessive window raises ValueError rather than clipping.
    """
    height, width, a, c, e, f = _grid(dataset)
    polygons = _polygons(geometry)
    if any(name not in BAND_NAMES for name in missing_bands):
        raise ValueError('unknown missing band')
    positions = [point for polygon in polygons for ring in polygon for point in ring]
    min_x, max_x = min(p[0] for p in positions), max(p[0] for p in positions)
    min_y, max_y = min(p[1] for p in positions), max(p[1] for p in positions)
    extents = ((min_x - c) / a, (max_x - c) / a, (max_y - f) / e, (min_y - f) / e)
    if not all(math.isfinite(v) for v in extents):
        raise ValueError('geometry exceeds oracle scan limit')
    col_start, col_stop = math.floor(extents[0]) - 1, math.ceil(extents[1]) + 1
    row_start, row_stop = math.floor(extents[2]) - 1, math.ceil(extents[3]) + 1
    if (row_stop - row_start + 1) * (col_stop - col_start + 1) > MAX_CANDIDATE_CELLS:
        raise ValueError('geometry exceeds oracle scan limit')

    selected = in_coverage = outside = land = unknown = 0
    nodata = invalid_mask = False
    mask_counts = {'0': 0, '1': 0, '2': 0}
    canopy, loss = [0] * 101, [0] * 26
    for row in range(row_start, row_stop + 1):
        y = f + e * (row + 0.5)
        for col in range(col_start, col_stop + 1):
            x = c + a * (col + 0.5)
            if not _covered((x, y), polygons):
                continue
            selected += 1
            if not (0 <= row < height and 0 <= col < width):
                outside += 1
                unknown += 1
                continue
            in_coverage += 1
            values = [int(dataset.bands[i, row, col]) for i in range(3)]
            # A simulated absent band has no valid observations anywhere.
            validity = [bool(dataset.masks[i, row, col]) and BAND_NAMES[i] not in missing_bands for i in range(3)]
            if validity[2]:
                mask_counts[str(values[2])] += 1
            is_nodata = validity[2] and values[2] == 0
            is_invalid = not all(validity)
            nodata = nodata or is_nodata
            invalid_mask = invalid_mask or is_invalid
            if is_nodata or is_invalid:
                unknown += 1
            elif values[2] == 1:
                land += 1
                canopy[values[0]] += 1
                loss[values[1]] += 1

    reasons = []
    if selected == 0:
        reasons.append('no_selected_cells')
    if outside:
        reasons.append('out_of_coverage')
    if nodata:
        reasons.append('nodata')
    if invalid_mask:
        reasons.append('band_mask_invalid')
    if selected and not land:
        reasons.append('no_valid_land')
    reasons.extend(f'missing_band:{name}' for name in BAND_NAMES if name in missing_bands)
    if missing_bands:
        unknown, support = selected, 'unavailable'
    elif not selected or not land:
        support = 'none'
    else:
        support = 'partial' if unknown else 'complete'
    analytical = bool(selected and land and not missing_bands)
    periods = {}
    for name, first, last in (('2021-2023', 21, 23), ('2024-2025', 24, 25)):
        count = sum(loss[first:last + 1]) if analytical else None
        flag = (True if count else (False if unknown == 0 else None)) if analytical else None
        periods[name] = {'mapped_loss_present': flag, 'observed_loss_cell_count': count}
    return {
        'selected_cell_count': selected,
        'in_coverage_cell_count': in_coverage,
        'out_of_coverage_cell_count': outside,
        'valid_land_cell_count': land,
        'unknown_cell_count': unknown,
        'datamask_counts': mask_counts,
        'canopy_histogram': canopy if analytical else None,
        'lossyear_histogram': loss if analytical else None,
        'yearly_loss_counts': {str(2000 + year): loss[year] for year in range(1, 26)} if analytical else None,
        'periods': periods,
        'support': support,
        'unknown_reasons': reasons,
    }
