"""Separate synthetic membership/reduction evidence, with exact scalar clipping.

The clipping oracle supports these deliberately simple convex rings, convex
holes and disjoint islands. It is not claimed as an arbitrary polygon library.
Fractions preserve binary input coordinates exactly; no snapping/tolerance.
"""
from fractions import Fraction as F
import json
from pathlib import Path

import numpy as np
import shapely
from shapely.geometry import shape

import study as s


def rectangle(west, south, east, north):
    return {'type': 'Polygon', 'coordinates': [[[west, north], [east, north],
            [east, south], [west, south], [west, north]]]}


def polygon(points, holes=()):
    return {'type': 'Polygon', 'coordinates': [points + [points[0]], *holes]}


def clipping_area(ring, bounds):
    """Sutherland-Hodgman rectangle clipping and shoelace area, exact arithmetic.

    No shapely, engine membership helper or float tolerance participates here.
    Convex rings can yield only one connected clipped polygon. Hole areas are
    subtracted separately by scalar_area; orientation is irrelevant.
    """
    points = [tuple(map(F, point)) for point in ring[:-1]]
    west, south, east, north = map(F, bounds)
    for axis, bound, keep_greater in ((0, west, True), (0, east, False),
                                      (1, south, True), (1, north, False)):
        output = []
        if not points:
            return F(0)
        start = points[-1]
        for end in points:
            start_in = start[axis] >= bound if keep_greater else start[axis] <= bound
            end_in = end[axis] >= bound if keep_greater else end[axis] <= bound
            if start_in != end_in:
                t = (bound-start[axis]) / (end[axis]-start[axis])
                output.append(tuple(start[i] + t*(end[i]-start[i]) for i in (0, 1)))
            if end_in:
                output.append(end)
            start = end
        points = output
    if len(points) < 3:
        return F(0)
    return abs(sum(p[0]*q[1] - q[0]*p[1] for p, q in zip(points, points[1:]+points[:1]))) / 2


def scalar_area(geometry, bounds):
    polygons = [geometry['coordinates']] if geometry['type'] == 'Polygon' else geometry['coordinates']
    total = F(0)
    for rings in polygons:
        total += clipping_area(rings[0], bounds) - sum(clipping_area(hole, bounds) for hole in rings[1:])
    if total < 0:
        raise AssertionError('negative clipped area: fixture/oracle scope invalid')
    return total


def orientation(a, b, p):
    ax, ay, bx, by, px, py = map(F, (*a, *b, *p))
    return (bx-ax)*(py-ay) - (by-ay)*(px-ax)


def segment_contact(a, b, c, d):
    def on(p, q, r):
        return (orientation(p, q, r) == 0 and min(p[0], q[0]) <= r[0] <= max(p[0], q[0])
                and min(p[1], q[1]) <= r[1] <= max(p[1], q[1]))
    turns = (orientation(a, b, c), orientation(a, b, d), orientation(c, d, a), orientation(c, d, b))
    return (turns[0]*turns[1] < 0 and turns[2]*turns[3] < 0
            or on(a, b, c) or on(a, b, d) or on(c, d, a) or on(c, d, b))


def scalar_contact(geometry, bounds):
    west, south, east, north = bounds
    corners = [(west, south), (east, south), (east, north), (west, north)]
    if any(s.scalar_center_covers(p, geometry) for p in corners):
        return True
    polygons = [geometry['coordinates']] if geometry['type'] == 'Polygon' else geometry['coordinates']
    for rings in polygons:
        for ring in rings:
            if any(west <= p[0] <= east and south <= p[1] <= north for p in ring):
                return True
            if any(segment_contact(a, b, c, d) for a, b in zip(ring, ring[1:])
                   for c, d in zip(corners, corners[1:]+corners[:1])):
                return True
    return False


def scalar_memberships(metadata, geometry):
    # Bounds/validation share GEOS; every actual rectangle/point membership
    # uses exact arithmetic. Analytic expected cellsets below also bind the scan.
    rows, cols, _ = s.candidates(metadata, s.validate_geometry(metadata, geometry))
    centers, overlap, touches = [], [], []
    for row, col in zip(rows.tolist(), cols.tolist()):
        bounds = s.cell_bounds(metadata, row, col)
        if s.scalar_center_covers(s.cell_center(metadata, row, col), geometry):
            centers.append([row, col])
        area = scalar_area(geometry, bounds)
        if area > 0:
            overlap.append([row, col])
        elif scalar_contact(geometry, bounds):
            touches.append([row, col])
    return {'center_covers': centers, 'positive_area_overlap': overlap, 'zero_area_touch': touches}


def scalar_summary(dataset, cells, missing_bands=()):
    """Independent scalar reduction of fixture support; no summarize_selected."""
    h, w = dataset.metadata['shape']
    valid_land, unknown, outside, covered = [], 0, 0, 0
    datamask = {str(x): 0 for x in range(3)}
    nodata_count = invalid_count = 0
    for r, c in cells:
        if not (0 <= r < h and 0 <= c < w):
            outside += 1
            unknown += 1
            continue
        covered += 1
        values = dataset.bands[:, r, c].tolist()
        masks = dataset.masks[:, r, c].tolist()
        for i, name in enumerate(s.BAND_NAMES):
            if name in missing_bands:
                masks[i] = False
        if masks[2]:
            datamask[str(values[2])] += 1
        nodata = masks[2] and values[2] == 0
        invalid = not all(masks)
        nodata_count += nodata
        invalid_count += invalid
        unknown += nodata or invalid
        if not invalid and values[2] == 1:
            valid_land.append(values)
    if missing_bands:
        unknown = len(cells)
    analytical = bool(valid_land) and not missing_bands
    canopy, loss = ([0]*101, [0]*26) if analytical else (None, None)
    if analytical:
        for a, b, _ in valid_land:
            canopy[a] += 1
            loss[b] += 1
    periods = {}
    for key, years in s.PERIODS.items():
        count = sum(loss[years[0]:years[1]+1]) if analytical else None
        flag = True if analytical and count else False if analytical and unknown == 0 else None
        periods[key] = {'mapped_loss_present': flag, 'observed_loss_cell_count': count}
    reasons = []
    if not cells:
        reasons.append('no_selected_cells')
    if outside:
        reasons.append('out_of_coverage')
    if nodata_count:
        reasons.append('nodata')
    if invalid_count:
        reasons.append('band_mask_invalid')
    if cells and not valid_land:
        reasons.append('no_valid_land')
    reasons.extend(f'missing_band:{name}' for name in s.BAND_NAMES if name in missing_bands)
    return {'selected_cell_count': len(cells), 'in_coverage_cell_count': covered,
            'out_of_coverage_cell_count': outside, 'valid_land_cell_count': len(valid_land),
            'unknown_cell_count': int(unknown), 'datamask_counts': datamask,
            'canopy_histogram': canopy, 'lossyear_histogram': loss,
            'yearly_loss_counts': {str(2000+y): loss[y] for y in range(1, 26)} if analytical else None,
            'periods': periods, 'unknown_reasons': reasons,
            'support': 'unavailable' if missing_bands else 'none' if not valid_land else 'partial' if unknown else 'complete'}


def test_dataset(metadata=None):
    metadata = metadata or {'shape': [3, 3], 'transform': [1, 0, 0, 0, -1, 3], 'crs': 'EPSG:4326',
                            'product': 'SYNTHETIC — never real Hansen observations'}
    bands = np.zeros((3, *metadata['shape']), dtype=np.uint8)
    bands[0] = 80
    bands[2] = 1
    return s.Dataset(bands, np.ones(bands.shape, dtype=bool), metadata).validate()


def definitions(native_metadata):
    all9 = [[r, c] for r in range(3) for c in range(3)]
    outer = rectangle(.25, .25, 2.75, 2.75)
    hole = rectangle(1.5, 1.25, 1.75, 1.75)['coordinates'][0]
    hole_boundary = {'type': 'Polygon', 'coordinates': [outer['coordinates'][0], hole]}
    hole_cell = {'type': 'Polygon', 'coordinates': [rectangle(0, 0, 3, 3)['coordinates'][0],
                                                  rectangle(1, 1, 2, 2)['coordinates'][0]]}
    hole_interior = {'type': 'Polygon', 'coordinates': [outer['coordinates'][0],
                                                      rectangle(.75, .75, 2.25, 2.25)['coordinates'][0]]}
    tiny = rectangle(1.125, 1.125, 1.25, 1.25)
    partial = rectangle(2.25, 1.25, 3.25, 1.75)
    cases = [
        ('tiny_no_center', tiny, [], [[1, 1]], None),
        ('equal_native_cell', rectangle(1, 1, 2, 2), [[1, 1]], [[1, 1]], None),
        ('point_only_contact', rectangle(2, 2, 2.25, 2.25), [], [[0, 2]], None),
        ('edge_only_contact', rectangle(2, 1.25, 2.25, 1.75), [], [[1, 2]], None),
        ('exterior_boundary_center', rectangle(1.5, 1.25, 1.75, 1.75), [[1, 1]], [[1, 1]], None),
        ('hole_boundary_center', hole_boundary, all9, all9, None),
        ('hole_exact_cell_boundary', hole_cell, [p for p in all9 if p != [1, 1]],
         [p for p in all9 if p != [1, 1]], None),
        ('hole_interior', hole_interior, [p for p in all9 if p != [1, 1]],
         [p for p in all9 if p != [1, 1]], None),
        ('multipart_islands', {'type': 'MultiPolygon', 'coordinates': [
            rectangle(.125, 2.125, .25, 2.25)['coordinates'],
            rectangle(2.125, .125, 2.25, .25)['coordinates']]}, [], [[0, 0], [2, 2]], None),
        ('partial_absence_becomes_unknown', partial, [[1, 2]], [[1, 2], [1, 3]], None),
        ('partial_witnessed_positive', partial, [[1, 2]], [[1, 2], [1, 3]], 'positive'),
        ('outside_only', rectangle(3.125, 1.125, 3.25, 1.25), [], [[1, 3]], None),
        ('invalid_band_mask_raw_loss', tiny, [], [[1, 1]], 'invalid'),
        ('nodata_raw_loss', tiny, [], [[1, 1]], 'nodata'),
        ('water_raw_loss', tiny, [], [[1, 1]], 'water'),
        ('mixed_mask_nodata_water_land', rectangle(0, 1, 3, 3),
         [[r, c] for r in range(2) for c in range(3)],
         [[r, c] for r in range(2) for c in range(3)], 'mixed'),
        ('missing_loss_band', rectangle(1, 1, 2, 2), [[1, 1]], [[1, 1]], 'missing'),
        ('diagonal_triangle', polygon([[1, 1], [2, 1], [1, 2]]), [[1, 1]], [[1, 1]], None),
        ('dyadic_sliver_no_center', polygon([[1.875, 1.125], [2.125, 1.125], [2.125, 1.15625]]),
         [], [[1, 1], [1, 2]], None),
    ]
    output = []
    for name, geom, centers, overlaps, mutation in cases:
        dataset = test_dataset()
        missing = ()
        if mutation == 'positive':
            dataset.bands[1, 1, 2] = 21
        elif mutation in ('invalid', 'nodata', 'water'):
            dataset.bands[:, 1, 1] = [91, 23, {'invalid': 1, 'nodata': 0, 'water': 2}[mutation]]
            if mutation == 'invalid':
                dataset.masks[0, 1, 1] = False
        elif mutation == 'mixed':
            dataset.bands[:, 0, 0] = [81, 22, 0]
            dataset.bands[:, 0, 1] = [82, 23, 1]
            dataset.masks[1, 0, 1] = False
            dataset.bands[:, 1, 0] = [83, 25, 2]
        elif mutation == 'missing':
            dataset.bands[1, 1, 1] = 23
            missing = ('lossyear',)
        output.append({'case_id': name, 'dataset': dataset, 'geometry': geom,
                       'expected_centers': centers, 'expected_overlap': overlaps, 'missing_bands': missing})
    # Native decimal fixtures use the original global chip affine. Geometry is
    # deliberately synthetic. No shifted affine controls analytical membership.
    a, _, x, _, e, y = native_metadata['transform']
    cx, cy = s.cell_center(native_metadata, 1, 1)
    native_geoms = [
        ('native_decimal_equal_cell', s.cell_geometry(native_metadata, 1, 1), [[1, 1]]),
        ('native_decimal_tiny', rectangle(cx+a/8, cy+e/4, cx+a/4, cy+e/8), []),
        ('native_decimal_boundary', rectangle(cx, cy+e/4, cx+a/4, cy-e/4), [[1, 1]]),
        ('native_decimal_boundary_one_ulp_in', rectangle(float(np.nextafter(cx, -np.inf)), cy+e/4, cx+a/4, cy-e/4), [[1, 1]]),
        ('native_decimal_boundary_one_ulp_out', rectangle(float(np.nextafter(cx, np.inf)), cy+e/4, cx+a/4, cy-e/4), []),
    ]
    for name, geom, centers in native_geoms:
        m = {**native_metadata, 'shape': [3, 3], 'product': 'SYNTHETIC VALUES ON NATIVE DECIMAL AFFINE'}
        output.append({'case_id': name, 'dataset': test_dataset(m), 'geometry': geom,
                       'expected_centers': centers, 'expected_overlap': [[1, 1]], 'missing_bands': ()})
    return output


def run_fixtures():
    native_metadata = s.load_source(s.ROOT).metadata
    cases = []
    failures = []
    for definition in definitions(native_metadata):
        dataset, geometry, missing = definition['dataset'], definition['geometry'], definition['missing_bands']
        centers = s.cell_list(*s.select_cells(dataset.metadata, geometry))
        overlap = s.overlap_membership(dataset.metadata, geometry)
        scalar = scalar_memberships(dataset.metadata, geometry)
        checks = {
            'analytic_centers_equal': s.exact_equal(centers, definition['expected_centers']),
            'analytic_overlap_equal': s.exact_equal(overlap['selected'], definition['expected_overlap']),
            'scalar_centers_equal': s.exact_equal(centers, scalar['center_covers']),
            'scalar_overlap_equal': s.exact_equal(overlap['selected'], scalar['positive_area_overlap']),
            'scalar_zero_area_touches_equal': s.exact_equal(overlap['zero_area_touch'], scalar['zero_area_touch']),
            'geos_distinct_predicates_equal': not overlap['predicate_mismatches'],
        }
        results = {}
        for rule, cells in (('center_covers', centers), ('positive_area_overlap', overlap['selected'])):
            answer, diagnostics = s.reduce_cells(dataset, cells, missing)
            independent = scalar_summary(dataset, cells, missing)
            checks[f'{rule}_scalar_reduction_equal'] = s.exact_equal(answer, independent)
            results[rule] = {'selected_cells': cells, 'result': answer, 'diagnostics': diagnostics,
                             'scalar_result': independent}
        case = {'case_id': definition['case_id'], 'synthetic': True, 'geometry': geometry,
                'metadata': dataset.metadata, 'raw_values': dataset.bands.tolist(),
                'raw_masks': dataset.masks.tolist(), 'missing_bands': list(missing),
                'analytic_expected_centers': definition['expected_centers'],
                'analytic_expected_overlap': definition['expected_overlap'],
                'zero_area_touch_cells': overlap['zero_area_touch'], 'scalar_membership': scalar,
                'rules': results, 'checks': checks, 'pass': all(checks.values())}
        if not case['pass']:
            failures.append({'case_id': case['case_id'], 'checks': checks})
        cases.append(case)
    rejected = []
    for name, geom in [('zero_area', polygon([[1, 1], [1.5, 1.5], [2, 2]])),
                       ('self_crossing', polygon([[0, 0], [2, 2], [0, 2], [2, 0]]))]:
        decisions = {}
        for rule, fn in (('center_covers', s.select_cells), ('positive_area_overlap', s.overlap_membership)):
            try:
                fn(native_metadata, geom)
                decisions[rule] = {'rejected': False}
                failures.append({'case_id': name, 'rule': rule, 'accepted_invalid_geometry': True})
            except ValueError as exc:
                decisions[rule] = {'rejected': True, 'error': str(exc)}
        rejected.append({'case_id': name, 'synthetic': True, 'geometry': geom, 'decisions': decisions})
    a, _, x, _, e, y = native_metadata['transform']
    global_center = s.cell_center(native_metadata, 1, 1)
    shifted_center = [(x+a)+.5*a, (y+e)+.5*e]
    boundary = next(c for c in cases if c['case_id'] == 'native_decimal_boundary')['geometry']
    reassociation = {
        'synthetic': True, 'row': 1, 'col': 1, 'global_center': global_center, 'shifted_center': shifted_center,
        'global_center_hex': [v.hex() for v in global_center], 'shifted_center_hex': [v.hex() for v in shifted_center],
        'global_center_selected': s.scalar_center_covers(global_center, boundary),
        'shifted_center_selected': s.scalar_center_covers(shifted_center, boundary),
        'note': 'Shifted value is a regression demonstration only, never used to select research/production cells.',
    }
    artifact = {'schema_version': 'plotline.spatial-sensitivity-fixtures.v1', 'synthetic': True,
                'real_plot_count': 0, 'valid_synthetic_case_count': len(cases),
                'rejection_case_count': len(rejected), 'cases': cases, 'rejected_geometries': rejected,
                'native_decimal_reassociation_control': reassociation,
                'code_fingerprints': {p.name: s.fingerprint(p) for p in (Path(__file__), s.OWNED / 'study.py')},
                'oracle_scope': 'Exact Fraction ray casting/rectangle clipping/segment contact on simple convex rings, holes and islands. No GEOS membership or area. GEOS validation/bounds and native coordinate construction are shared.',
                'gates': {'pass': not failures, 'failures': failures}}
    artifact['content_sha256'] = s.digest(artifact)
    return artifact


if __name__ == '__main__':
    result = run_fixtures()
    s.write_json(s.OWNED / 'fixtures.json', result)
    print(json.dumps({'valid_synthetic_case_count': result['valid_synthetic_case_count'],
                      'rejection_case_count': result['rejection_case_count'],
                      'gates': result['gates'], 'content_sha256': result['content_sha256']}, indent=2))
    raise SystemExit(0 if result['gates']['pass'] else 1)
