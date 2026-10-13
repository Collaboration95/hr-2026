"""Frozen-cohort spatial membership experiment; never changes engine contracts.

Run from repository root with the existing .venv-data interpreter and -B.
All inputs are read-only and all output paths are restricted to this directory.
"""
from __future__ import annotations

import argparse
from fractions import Fraction
import hashlib
import json
import math
from pathlib import Path
import platform
import sys

ROOT = Path(__file__).resolve().parents[3]
OWNED = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

import numpy as np
import rasterio
import shapely
from shapely.geometry import shape

from engine.codecs import decode_store
from engine.model import BAND_NAMES, Dataset, PERIODS
from engine.query import evaluate, select_cells, summarize_selected
from engine.source import CSV_NAME, GEOJSON_NAME, SAMPLE, load_plots, load_source

EXPERIMENT = 'exp-0109a8d6c4782217871315b92c63a971d11ebd164585c80981f24c55b4f68fea'
RUN = 'run-71a5b90b05bdce363044d8e232ae33d20b31f3868a6f5ba50bf61372b98194a9'
STORE = f'artifacts/stores/{EXPERIMENT}/separate_zstd_l19'
RULES = {
    'center_covers': {
        'membership': 'exact polygon covers native cell center, including exterior/hole boundary',
        'implementation': 'engine.query.select_cells',
        'center': 'x=c+(col+0.5)*a; y=f+(row+0.5)*e; original chip affine',
    },
    'positive_area_overlap': {
        'membership': 'GEOS intersection(polygon,native footprint).area > 0; strict; no tolerance',
        'cross_check': 'GEOS DE-9IM relate_pattern(polygon,footprint,"2********")',
        'footprint': 'west=c+col*a; east=c+(col+1)*a; north=f+row*e; south=f+(row+1)*e',
        'zero_area_contact': 'intersects and intersection.area == 0; excluded from selected support',
    },
    'common': {
        'geometry': 'original supplied Polygon/MultiPolygon; retain holes; no buffers or resampling',
        'reduction': 'engine.query.summarize_selected unchanged; observed valid land; tri-state periods',
        'outside': 'unbounded native lattice; selected outside chip retained as unknown',
        'units': 'selected native cells; angular overlap fractions are dimensionless, never hectares',
        'periods': {'2021-2023': [21, 23], '2024-2025': [24, 25]},
    },
}


def encoded(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()


def digest(value):
    return hashlib.sha256(encoded(value)).hexdigest()


def exact_equal(left, right):
    """Compare JSON representations, preserving false/0 and true/1 distinctions."""
    return encoded(left) == encoded(right)


def fingerprint(path):
    data = path.read_bytes()
    return {'bytes': len(data), 'sha256': hashlib.sha256(data).hexdigest()}


def write_json(path, value):
    path = path.resolve()
    if not path.is_relative_to(OWNED):
        raise ValueError('research output must be inside data/experimental/spatial-sensitivity/')
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, sort_keys=True, indent=2, allow_nan=False) + '\n')


def validate_geometry(metadata, geometry):
    # Independent input checks; GEOS topology/bounds are shared, membership is
    # not called to validate the scalar oracle or the alternative selection.
    if type(geometry) is not dict or geometry.get('type') not in ('Polygon', 'MultiPolygon'):
        raise ValueError('only Polygon and MultiPolygon are supported')
    coordinates = geometry.get('coordinates')
    polygons = [coordinates] if geometry['type'] == 'Polygon' else coordinates
    if not isinstance(polygons, (tuple, list)) or not polygons:
        raise ValueError('geometry must contain polygons')
    count = 0
    for rings in polygons:
        if not isinstance(rings, (tuple, list)) or not rings:
            raise ValueError('polygon must contain an exterior ring')
        for ring in rings:
            if not isinstance(ring, (tuple, list)) or len(ring) < 4 or ring[0] != ring[-1]:
                raise ValueError('rings must be explicitly closed with at least four positions')
            count += len(ring)
            if count > 100_000:
                raise ValueError('geometry exceeds vertex budget')
            for point in ring:
                if not isinstance(point, (tuple, list)) or len(point) != 2:
                    raise ValueError('positions must have two coordinates')
                if any(type(v) not in (int, float) or not math.isfinite(v) for v in point):
                    raise ValueError('positions must be finite numbers')
    transform = metadata.get('transform', [])
    if len(transform) != 6 or any(type(v) not in (int, float) or not math.isfinite(v) for v in transform):
        raise ValueError('finite six-value transform required')
    a, b, _, d, e, _ = transform
    if a <= 0 or e >= 0 or b != 0 or d != 0 or metadata.get('crs') != 'EPSG:4326':
        raise ValueError('only north-up EPSG:4326 grids are supported')
    polygon = shape(geometry)
    if polygon.is_empty or not polygon.is_valid or polygon.area <= 0:
        raise ValueError('geometry must be nonempty, valid and have strictly positive area')
    return polygon


def cell_bounds(metadata, row, col):
    a, _, c, _, e, f = metadata['transform']
    return c + col*a, f + (row+1)*e, c + (col+1)*a, f + row*e


def cell_center(metadata, row, col):
    a, _, c, _, e, f = metadata['transform']
    return [c + (col+.5)*a, f + (row+.5)*e]


def cell_geometry(metadata, row, col):
    west, south, east, north = cell_bounds(metadata, row, col)
    return {'type': 'Polygon', 'coordinates': [[[west, north], [east, north],
            [east, south], [west, south], [west, north]]]}


def candidates(metadata, polygon):
    """Unclipped bounding scan, with spare cells to absorb inverse rounding.

    Margins only widen enumeration. Actual area/predicate decides selection.
    Never reuse a translated window affine or form east as west+a.
    """
    a, _, c, _, e, f = metadata['transform']
    minx, miny, maxx, maxy = polygon.bounds
    extents = ((minx-c)/a, (maxx-c)/a, (maxy-f)/e, (miny-f)/e)
    if not all(math.isfinite(v) and abs(v) < 2**62 for v in extents):
        raise ValueError('geometry exceeds supported native lattice index range')
    c0, c1 = math.floor(extents[0])-1, math.ceil(extents[1])+1
    r0, r1 = math.floor(extents[2])-1, math.ceil(extents[3])+1
    if (c1-c0+1)*(r1-r0+1) > 10_000_000:
        raise ValueError('candidate budget exceeded')
    rows, cols = np.meshgrid(np.arange(r0, r1+1, dtype=np.int64),
                             np.arange(c0, c1+1, dtype=np.int64), indexing='ij')
    rows, cols = rows.ravel(), cols.ravel()
    west, south, east, north = cell_bounds(metadata, rows, cols)
    return rows, cols, shapely.box(west, south, east, north)


def cell_list(rows, cols):
    return [[int(r), int(c)] for r, c in zip(rows, cols)]


def overlap_membership(metadata, geometry):
    polygon = validate_geometry(metadata, geometry)
    rows, cols, footprints = candidates(metadata, polygon)
    areas = shapely.area(shapely.intersection(polygon, footprints))
    primary = areas > 0
    alternate = shapely.relate_pattern(polygon, footprints, '2********')
    touches = shapely.intersects(polygon, footprints) & (areas == 0)
    return {
        'selected': cell_list(rows[primary], cols[primary]),
        'zero_area_touch': cell_list(rows[touches], cols[touches]),
        'predicate_mismatches': cell_list(rows[primary != alternate], cols[primary != alternate]),
        'candidate_count': len(rows),
    }


def ring_location(point, ring):
    """Exact scalar ray casting over the supplied binary coordinates; no GEOS."""
    x, y = map(Fraction, point)
    inside = False
    for start, end in zip(ring, ring[1:]):
        ax, ay = map(Fraction, start)
        bx, by = map(Fraction, end)
        turn = (bx-ax)*(y-ay) - (by-ay)*(x-ax)
        if turn == 0 and min(ax, bx) <= x <= max(ax, bx) and min(ay, by) <= y <= max(ay, by):
            return 0
        if (ay > y) != (by > y) and ((by > ay and turn > 0) or (by < ay and turn < 0)):
            inside = not inside
    return 1 if inside else -1


def scalar_center_covers(point, geometry):
    polygons = [geometry['coordinates']] if geometry['type'] == 'Polygon' else geometry['coordinates']
    for rings in polygons:
        outer = ring_location(point, rings[0])
        if outer < 0:
            continue
        if outer == 0:
            return True
        holes = [ring_location(point, ring) for ring in rings[1:]]
        if 0 in holes or 1 not in holes:
            return True
    return False


def scalar_centers(metadata, geometry):
    # GEOS is shared for validation/bounds only, never for this membership.
    polygon = validate_geometry(metadata, geometry)
    rows, cols, _ = candidates(metadata, polygon)
    return [[int(r), int(c)] for r, c in zip(rows, cols)
            if scalar_center_covers(cell_center(metadata, int(r), int(c)), geometry)]


def selected_samples(dataset, cells):
    rc = np.array(cells, dtype=np.int64).reshape(-1, 2)
    rows, cols = rc[:, 0], rc[:, 1]
    h, w = dataset.metadata['shape']
    inside = (rows >= 0) & (rows < h) & (cols >= 0) & (cols < w)
    r, c = rows[inside], cols[inside]
    values, masks = dataset.bands[:, r, c], dataset.masks[:, r, c]
    return values, masks, int((~inside).sum())


def reduce_cells(dataset, cells, missing_bands=()):
    values, masks, outside = selected_samples(dataset, cells)
    result = summarize_selected(values, masks, len(cells), outside, missing_bands)
    diagnostics = {
        'band_invalid_cell_counts': {name: int((~masks[i]).sum()) for i, name in enumerate(BAND_NAMES)},
        'any_band_invalid_cell_count': int((~masks.all(axis=0)).sum()),
        'known_datamask_zero_cell_count': int(((values[2] == 0) & masks[2]).sum()),
        'raw_selected_values_sha256': hashlib.sha256(values.tobytes()).hexdigest(),
        'raw_selected_masks_sha256': hashlib.sha256(masks.tobytes()).hexdigest(),
    }
    return result, diagnostics


def differing_fields(left, right, prefix=''):
    if exact_equal(left, right):
        return []
    if type(left) is dict and type(right) is dict:
        result = []
        for key in sorted(set(left) | set(right)):
            path = f'{prefix}.{key}' if prefix else key
            if key not in left or key not in right:
                result.append(path)
            else:
                result.extend(differing_fields(left[key], right[key], path))
        return result
    return [prefix]


def witness(dataset, plot, row, col, center_set, overlap_set, touch_set, tile_window):
    geom = plot['geometry']
    polygon = shape(geom)
    footprint = cell_geometry(dataset.metadata, row, col)
    rectangle = shape(footprint)
    area = polygon.intersection(rectangle).area
    h, w = dataset.metadata['shape']
    inside = 0 <= row < h and 0 <= col < w
    raw = dataset.bands[:, row, col].tolist() if inside else [None]*3
    masks = dataset.masks[:, row, col].tolist() if inside else [False]*3
    return {
        'plot_id': plot['plot_id'], 'original_polygon': geom, 'geometry_sha256': digest(geom),
        'row': row, 'col': col, 'index_frame': 'global original chip lattice (never window-local)',
        'source_tile_row': row + tile_window[1], 'source_tile_col': col + tile_window[0],
        'footprint': footprint, 'center': cell_center(dataset.metadata, row, col),
        'raw_values': dict(zip(BAND_NAMES, raw)), 'band_validity': dict(zip(BAND_NAMES, masks)),
        'in_coverage': inside, 'valid_land': inside and all(masks) and raw[2] == 1,
        'inclusion': {'center_covers': (row, col) in center_set,
                      'positive_area_overlap': (row, col) in overlap_set,
                      'zero_area_touch': (row, col) in touch_set},
        'overlap_interior_dimension_2': bool(polygon.relate_pattern(rectangle, '2********')),
        'angular_cell_intersection_fraction': area / rectangle.area,
        'fraction_units': 'dimensionless EPSG:4326 angular-area ratio; not hectares or weighted loss area',
    }


def input_paths():
    return [SAMPLE / CSV_NAME, SAMPLE / GEOJSON_NAME, Path('data/public/provenance.json'),
            *(Path(f'data/public/hansen_{name}_sample.tif') for name in BAND_NAMES),
            Path('artifacts/demo-v1.json'), Path('artifacts/experiments/retained-choice.json'),
            Path(STORE) / 'index.json', Path(STORE) / 'payload.bin']


def code_paths():
    return [*(p.relative_to(ROOT) for p in sorted(OWNED.glob('*.py'))), *(Path(f'engine/{name}.py')
            for name in ('__init__', 'source', 'model', 'query', 'codecs'))]


def run_study():
    paths = input_paths() + code_paths()
    before = {str(path): fingerprint(ROOT / path) for path in paths}
    choice = json.loads((ROOT / 'artifacts/experiments/retained-choice.json').read_text())
    if (choice['experiment_id'] != EXPERIMENT or choice['run_id'] != RUN
            or choice['smallest_encoded']['store_path'] != STORE):
        raise ValueError('accepted retained identity changed; review before rerunning')
    source = load_source(ROOT)
    compact = Dataset(*decode_store(ROOT / STORE)).validate()
    canonical = json.loads((ROOT / 'artifacts/demo-v1.json').read_text())
    plots = load_plots(ROOT)
    if len(plots) != 17:
        raise ValueError('frozen cohort requires exactly 17 supplied plots')
    baseline = {p['plot_id']: p for p in canonical['plots']}
    if len(baseline) != 17 or set(baseline) != {p['plot_id'] for p in plots}:
        raise ValueError('canonical cohort differs')
    provenance = json.loads((ROOT / 'data/public/provenance.json').read_text())
    tile_window = provenance['layers'][0]['window']
    array_check = {
        'grid_metadata_equal': exact_equal(source.metadata, compact.metadata),
        'raw_values_compared': int(source.bands.size), 'mask_bits_compared': int(source.masks.size),
        'raw_value_mismatch_count': int(np.count_nonzero(source.bands != compact.bands)),
        'mask_bit_mismatch_count': int(np.count_nonzero(source.masks != compact.masks)),
        'source_raw_sha256': hashlib.sha256(source.bands.tobytes()).hexdigest(),
        'compact_raw_sha256': hashlib.sha256(compact.bands.tobytes()).hexdigest(),
        'source_masks_sha256': hashlib.sha256(source.masks.tobytes()).hexdigest(),
        'compact_masks_sha256': hashlib.sha256(compact.masks.tobytes()).hexdigest(),
    }
    records, changes, failures = [], [], []
    if not array_check['grid_metadata_equal'] or array_check['raw_value_mismatch_count'] or array_check['mask_bit_mismatch_count']:
        failures.append({'kind': 'full_grid_source_compact_mismatch', 'details': array_check})
    for plot in plots:
        pid, geom = plot['plot_id'], plot['geometry']
        center = cell_list(*select_cells(source.metadata, geom))
        center_compact = cell_list(*select_cells(compact.metadata, geom))
        independent_center = scalar_centers(source.metadata, geom)
        overlap = overlap_membership(source.metadata, geom)
        overlap_compact = overlap_membership(compact.metadata, geom)
        cs, os = set(map(tuple, center)), set(map(tuple, overlap['selected']))
        ts = set(map(tuple, overlap['zero_area_touch']))
        center_only, overlap_only = sorted(cs-os), sorted(os-cs)
        record = {'plot_id': pid, 'geometry': geom, 'geometry_sha256': digest(geom),
                  'supplier_declaration': plot['supplier']['c2_deforestation_spatial_analysis_result'],
                  'supplier_indication': plot['supplier']['c2_deforestation_spatial_analysis_result'] == 'b. Indication of deforestation',
                  'rules': {}, 'center_only_cells': [list(x) for x in center_only],
                  'overlap_only_cells': [list(x) for x in overlap_only],
                  'zero_area_touch_cells': overlap['zero_area_touch'],
                  'zero_area_touch_cell_count': len(ts),
                  'overlap_candidate_count': overlap['candidate_count'],
                  'overlap_predicate_mismatches': overlap['predicate_mismatches'],
                  'scalar_center_equal': exact_equal(center, independent_center),
                  'scalar_center_symmetric_difference': [list(x) for x in sorted(cs ^ set(map(tuple, independent_center)))]}
        for rule, cells, compact_cells in (
                ('center_covers', center, center_compact),
                ('positive_area_overlap', overlap['selected'], overlap_compact['selected'])):
            sr, sd = reduce_cells(source, cells)
            cr, cd = reduce_cells(compact, compact_cells)
            sv, sm, so = selected_samples(source, cells)
            cv, cm, co = selected_samples(compact, compact_cells)
            samples_equal = np.array_equal(sv, cv) and np.array_equal(sm, cm) and so == co
            fields = differing_fields(sr, cr)
            rule_record = {'source_result': sr, 'compact_result': cr,
                           'source_diagnostics': sd, 'compact_diagnostics': cd,
                           'selected_cells': cells, 'selected_cells_sha256': digest(cells),
                           'comparison': {'exact_query_equal': not fields,
                                          'differing_fields': fields,
                                          'selected_cells_equal': exact_equal(cells, compact_cells),
                                          'selected_raw_values_and_masks_equal': samples_equal,
                                          'source_result_sha256': digest(sr), 'compact_result_sha256': digest(cr)}}
            if rule == 'center_covers':
                rule_record['production_evaluate_equal'] = exact_equal(sr, evaluate(source, geom))
                rule_record['canonical_comparison'] = {
                    'geometry_equal': exact_equal(geom, baseline[pid]['geometry']),
                    'supplier_equal': exact_equal(plot['supplier'], baseline[pid]['supplier']),
                    'source_differing_fields': differing_fields(sr, baseline[pid]['source_result']),
                    'compact_differing_fields': differing_fields(cr, baseline[pid]['compact_result']),
                }
            record['rules'][rule] = rule_record
            if not all((rule_record['comparison']['exact_query_equal'],
                        rule_record['comparison']['selected_cells_equal'],
                        rule_record['comparison']['selected_raw_values_and_masks_equal'])):
                failures.append({'kind': 'source_compact_query_mismatch', 'plot_id': pid, 'rule': rule})
        cc = record['rules']['center_covers']['canonical_comparison']
        if not (cc['geometry_equal'] and cc['supplier_equal'] and not cc['source_differing_fields']
                and not cc['compact_differing_fields'] and record['rules']['center_covers']['production_evaluate_equal']):
            failures.append({'kind': 'canonical_or_production_center_mismatch', 'plot_id': pid, 'details': cc})
        if not record['scalar_center_equal'] or overlap['predicate_mismatches']:
            failures.append({'kind': 'membership_cross_check_mismatch', 'plot_id': pid})
        record['center_only_investigation'] = [witness(source, plot, r, c, cs, os, ts, tile_window)
                                               for r, c in center_only]
        if center_only:
            failures.append({'kind': 'center_not_subset_requires_review', 'plot_id': pid})
        for period, (start, end) in PERIODS.items():
            left = record['rules']['center_covers']['source_result']['periods'][period]
            right = record['rules']['positive_area_overlap']['source_result']['periods'][period]
            if not exact_equal(left['mapped_loss_present'], right['mapped_loss_present']):
                relevant = []
                for r, c in overlap_only + center_only:
                    w = witness(source, plot, r, c, cs, os, ts, tile_window)
                    if w['valid_land'] and start <= w['raw_values']['lossyear'] <= end:
                        relevant.append(w)
                changes.append({'plot_id': pid, 'period': period, 'center': left,
                                'positive_area_overlap': right, 'witnesses': relevant,
                                'unknown_or_support_witnesses': [] if relevant else
                                [witness(source, plot, r, c, cs, os, ts, tile_window)
                                 for r, c in overlap_only + center_only]})
        records.append(record)
    after = {str(path): fingerprint(ROOT / path) for path in paths}
    drift = [path for path in before if before[path] != after[path]]
    if drift:
        failures.append({'kind': 'input_or_code_changed_during_run', 'paths': drift})
    indications = [p for p in records if p['supplier_indication']]
    if len(indications) != 5:
        failures.append({'kind': 'supplier_indication_field_not_expected', 'count': len(indications)})
    summary = {
        'real_plot_count': 17, 'synthetic_plot_count_in_this_file': 0,
        'source_compact_exact_query_count': {rule: sum(p['rules'][rule]['comparison']['exact_query_equal']
                                                    for p in records) for rule in ('center_covers', 'positive_area_overlap')},
        'total_selected_cell_memberships': {rule: sum(p['rules'][rule]['source_result']['selected_cell_count']
                                                    for p in records) for rule in ('center_covers', 'positive_area_overlap')},
        'positive_plot_counts': {rule: {period: sum(p['rules'][rule]['source_result']['periods'][period]['mapped_loss_present'] is True
                                                  for p in records) for period in PERIODS}
                                 for rule in ('center_covers', 'positive_area_overlap')},
        'period_flag_change_count': len(changes),
        'plots_with_changed_period_flag': sorted({x['plot_id'] for x in changes}),
        'center_only_cell_membership_count': sum(len(p['center_only_cells']) for p in records),
        'overlap_only_cell_membership_count': sum(len(p['overlap_only_cells']) for p in records),
        'zero_area_touch_cell_membership_count': sum(p['zero_area_touch_cell_count'] for p in records),
        'predicate_mismatch_count': sum(len(p['overlap_predicate_mismatches']) for p in records),
        'scalar_center_match_count': sum(p['scalar_center_equal'] for p in records),
        'canonical_center_match_count': sum(
            p['rules']['center_covers']['canonical_comparison']['geometry_equal']
            and p['rules']['center_covers']['canonical_comparison']['supplier_equal']
            and not p['rules']['center_covers']['canonical_comparison']['source_differing_fields']
            and not p['rules']['center_covers']['canonical_comparison']['compact_differing_fields']
            for p in records),
        'selected_support_totals': {rule: {field: sum(p['rules'][rule]['source_result'][field] for p in records)
            for field in ('valid_land_cell_count', 'unknown_cell_count', 'out_of_coverage_cell_count')}
            for rule in ('center_covers', 'positive_area_overlap')},
        'supplier_indication_ids': [p['plot_id'] for p in indications],
        'supplier_indication_2021_2023': [
            {'plot_id': p['plot_id'], **{rule: p['rules'][rule]['source_result']['periods']['2021-2023']
                                       for rule in ('center_covers', 'positive_area_overlap')}} for p in indications],
        'supplier_indication_new_2021_2023_signal_ids': [p['plot_id'] for p in indications
            if p['rules']['center_covers']['source_result']['periods']['2021-2023']['mapped_loss_present'] is not True
            and p['rules']['positive_area_overlap']['source_result']['periods']['2021-2023']['mapped_loss_present'] is True],
    }
    artifact = {
        'schema_version': 'plotline.spatial-sensitivity.v1', 'synthetic': False,
        'scope': 'same 17 supplied polygons; frozen Hansen 2025 v1.13; spatial rule sensitivity only',
        'accepted_identity': {'experiment_id': EXPERIMENT, 'run_id': RUN, 'store_path': STORE},
        'input_fingerprints': {str(p): before[str(p)] for p in input_paths()},
        'code_fingerprints': {str(p): before[str(p)] for p in code_paths()},
        'code_bundle_sha256': digest({str(p): before[str(p)] for p in code_paths()}),
        'rules': RULES, 'rule_sha256': {name: digest({'rule': rule, 'common': RULES['common']})
                                     for name, rule in RULES.items() if name != 'common'},
        'runtime': {'python': platform.python_version(), 'numpy': np.__version__, 'shapely': shapely.__version__,
                    'geos': shapely.geos_version_string, 'rasterio': rasterio.__version__},
        'dataset': source.metadata, 'array_comparison': array_check,
        'summary': summary, 'plots': records, 'changed_period_flags': changes,
        'gates': {'pass': not failures, 'failures': failures, 'input_and_code_unchanged': not drift,
                  'positive_encoding_fidelity_claim_allowed': not failures},
        'limitations': [
            'Rule sensitivity is not encoding error or the prior translated-origin 1ULP implementation bug.',
            'Neither rule is established as the company rule; supplier source vintage and rule are unknown.',
            'Mapped tree-cover loss is not legal deforestation; no compliance or regulatory verdict.',
            'Area and DE-9IM predicates share GEOS topology/geometry; they are not independent implementations.',
            'Scalar center membership uses exact rational ray casting; GEOS remains shared for validity/bounds.',
            'All counts are selected native cells, not hectares, surveyed area, or fraction-weighted loss area.',
            'Full dictionaries are reduced using the accepted helper; this is not an independent reduction certification.',
            'Floating coordinates are not moved; no tolerance. Exact dyadic/scalar fixtures are reported separately.',
        ],
    }
    artifact['content_sha256'] = digest(artifact)
    return artifact


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, default=OWNED / 'results.json')
    args = parser.parse_args()
    result = run_study()
    write_json(args.output, result)
    write_json(OWNED / 'witnesses.json', {'schema_version': 'plotline.spatial-witnesses.v1',
               'synthetic': False, 'results_content_sha256': result['content_sha256'],
               'changed_period_flags': result['changed_period_flags']})
    print(json.dumps({'gates': result['gates'], 'array_comparison': result['array_comparison'],
                      'summary': result['summary'], 'content_sha256': result['content_sha256']}, indent=2))
    return 0 if result['gates']['pass'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
