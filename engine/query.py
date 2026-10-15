"""Native cell-center query, with explicit unknown support and no area inference."""
import math
import numpy as np
import shapely
from shapely.geometry import shape
from .model import BAND_NAMES, PERIODS

MAX_CANDIDATE_CELLS = 10_000_000
MAX_GEOMETRY_VERTICES = 100_000


def select_cells(metadata, geometry):
    """Return covered centers on the unbounded native lattice, including outside chip.

    Vectorized GEOS covers includes exterior and hole boundaries. The chip is not
    used to clip geometry: selected out-of-coverage cells remain countable unknowns.
    """
    if not isinstance(geometry, dict) or geometry.get('type') not in ('Polygon', 'MultiPolygon'):
        raise ValueError('only Polygon and MultiPolygon are supported')
    coordinates = geometry.get('coordinates')
    polygons = [coordinates] if geometry['type'] == 'Polygon' else coordinates
    if not isinstance(polygons, (list, tuple)) or not polygons:
        raise ValueError('geometry must contain polygons')
    vertex_count = 0
    for rings in polygons:
        if not isinstance(rings, (list, tuple)) or not rings:
            raise ValueError('polygon must contain an exterior ring')
        for ring in rings:
            if not isinstance(ring, (list, tuple)) or len(ring) < 4 or ring[0] != ring[-1]:
                raise ValueError('rings must have at least four positions and be explicitly closed')
            vertex_count += len(ring)
            if vertex_count > MAX_GEOMETRY_VERTICES:
                raise ValueError('geometry exceeds 100000 vertices')
            for point in ring:
                if not isinstance(point, (list, tuple)) or len(point) != 2:
                    raise ValueError('positions must have exactly two coordinates')
                try:
                    valid = all(not isinstance(v, bool) and isinstance(v, (int, float)) and math.isfinite(v) for v in point)
                except (OverflowError, ValueError):
                    valid = False
                if not valid:
                    raise ValueError('positions must be finite numbers')
    try:
        polygon = shape(geometry)
    except Exception as exc:
        raise ValueError('malformed geometry') from exc
    if polygon.is_empty or not polygon.is_valid:
        raise ValueError('geometry must be nonempty and valid')
    transform = metadata.get('transform', [])
    if len(transform) != 6 or not all(math.isfinite(v) for v in transform):
        raise ValueError('finite six-value transform required')
    a, b, c, d, e, f = transform
    if b != 0 or d != 0 or a <= 0 or e >= 0 or metadata.get('crs') != 'EPSG:4326':
        raise ValueError('only north-up EPSG:4326 grids are supported')
    minx, miny, maxx, maxy = polygon.bounds
    if not all(math.isfinite(v) for v in polygon.bounds):
        raise ValueError('geometry bounds must be finite')
    # One candidate margin avoids losing boundary centers to inverse-transform
    # floating point rounding. Exact covers below decides membership, no buffer.
    extents = ((minx-c)/a-.5, (maxx-c)/a-.5, (maxy-f)/e-.5, (miny-f)/e-.5)
    if not all(math.isfinite(v) and abs(v) < 2**62 for v in extents):
        raise ValueError('geometry exceeds supported native lattice index range')
    c0 = math.floor(extents[0]) - 1
    c1 = math.ceil(extents[1]) + 1
    r0 = math.floor(extents[2]) - 1
    r1 = math.ceil(extents[3]) + 1
    if (r1-r0+1) * (c1-c0+1) > MAX_CANDIDATE_CELLS:
        raise ValueError('geometry exceeds 10000000 candidate cells; partition explicitly')
    rows, cols = np.meshgrid(np.arange(r0, r1+1, dtype=np.int64),
                             np.arange(c0, c1+1, dtype=np.int64), indexing='ij')
    covered = shapely.covers(polygon, shapely.points(c + (cols + .5) * a,
                                                     f + (rows + .5) * e))
    return rows[covered], cols[covered]


def evaluate(dataset, geometry, missing_bands=()):
    """Evaluate the frozen v1 query. Dataset validation occurs at source/codec load."""
    if any(name not in BAND_NAMES for name in missing_bands):
        raise ValueError('unknown missing band name')
    rows, cols = select_cells(dataset.metadata, geometry)
    height, width = dataset.metadata['shape']
    inside = (rows >= 0) & (rows < height) & (cols >= 0) & (cols < width)
    r, c = rows[inside], cols[inside]
    values = dataset.bands[:, r, c]
    masks = dataset.masks[:, r, c]
    return summarize_selected(values, masks, len(rows), int((~inside).sum()), missing_bands)


def summarize_selected(values, masks, selected_count, outside_count, missing_bands=()):
    """Reduce already-selected in-coverage samples; retain global selection counts.

    Internal query primitive used by full and indexed paths. Selection always
    uses the original lattice; window transform reassociation never decides it.
    """
    if values.shape != masks.shape or values.ndim != 2 or values.shape[0] != 3:
        raise ValueError('selected samples require [3,count] values and masks')
    if selected_count != values.shape[1] + outside_count or outside_count < 0:
        raise ValueError('selected sample accounting mismatch')
    if any(name not in BAND_NAMES for name in missing_bands):
        raise ValueError('unknown missing band name')
    masks = masks.copy()
    for name in missing_bands:
        masks[BAND_NAMES.index(name)] = False
    n = selected_count
    outside = outside_count
    mask_valid = masks[2]
    known_bands = masks.all(axis=0)
    nodata = mask_valid & (values[2] == 0)
    land = known_bands & (values[2] == 1)
    land_count = int(land.sum())
    invalid = ~known_bands
    unknown = outside + int((nodata | invalid).sum())
    if missing_bands:
        unknown = n
    reasons = []
    if n == 0:
        reasons.append('no_selected_cells')
    if outside:
        reasons.append('out_of_coverage')
    if np.any(nodata):
        reasons.append('nodata')
    if np.any(invalid):
        reasons.append('band_mask_invalid')
    if n > 0 and land_count == 0:
        reasons.append('no_valid_land')
    reasons.extend(f'missing_band:{name}' for name in BAND_NAMES if name in missing_bands)
    analytical = land_count > 0 and not missing_bands
    canopy = np.bincount(values[0, land], minlength=101).tolist() if analytical else None
    loss = np.bincount(values[1, land], minlength=26).tolist() if analytical else None
    periods = {}
    for key, (start, end) in PERIODS.items():
        count = sum(loss[start:end+1]) if analytical else None
        flag = (True if count > 0 else (False if unknown == 0 else None)) if analytical else None
        periods[key] = {'mapped_loss_present': flag, 'observed_loss_cell_count': count}
    support = ('unavailable' if missing_bands else
               'none' if n == 0 or land_count == 0 else
               'partial' if unknown else 'complete')
    return {'selected_cell_count': n, 'in_coverage_cell_count': values.shape[1],
            'out_of_coverage_cell_count': outside, 'valid_land_cell_count': land_count,
            'unknown_cell_count': unknown,
            'datamask_counts': {str(v): int(((values[2] == v) & mask_valid).sum()) for v in range(3)},
            'canopy_histogram': canopy, 'lossyear_histogram': loss,
            'yearly_loss_counts': {str(2000+y): loss[y] for y in range(1, 26)} if analytical else None,
            'periods': periods, 'support': support, 'unknown_reasons': reasons}
