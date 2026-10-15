"""Fidelity proof for the decision layers: original layers vs derived codes vs decoded stores.

Every contract output is a function of the selected cells' codes plus the out-of-chip
count. So if each cell code derived from the original GeoTIFFs (independent float path,
engine.decision_original) equals the code in the decoded store, every polygon gets
identical outputs under the shared centre rule. This module checks that exhaustively,
then re-checks it on the 17 plots, a deterministic polygon fuzz and the retained v1
contract, and shows that deliberately broken inputs are detected. Mapped observations,
never legal findings.
"""
import argparse
import hashlib
import json
import math
from pathlib import Path
import platform
import random
import sys
import time

import numpy as np
import rasterio
import shapely
from shapely.geometry import MultiPoint

from . import decision as D
from . import decision_original as O
from .jrc import CHIP as JRC_CHIP, JrcDataset, load_jrc
from .model import Dataset
from .query import evaluate as v1_evaluate, select_cells
from .source import ROOT, CSV_NAME, GEOJSON_NAME, SAMPLE, canonical_bytes, load_plots, load_source, object_hash, sha256_file

SCHEMA = 'plotline.decision-proof.v1'
OUTPUT = 'artifacts/decision/proof-v1.json'
STORES = {D.SCREEN_VERSION: 'artifacts/decision/screen.plds', D.DECISION_VERSION: 'artifacts/decision/decision.plds'}
FUZZ_COUNT, FUZZ_SEED = 10_000, 20261015
THEOREM = ('Each contract output is a function of (the multiset of selected in-chip cell codes, the out-of-chip '
           'selected count). If the code of every Hansen cell derived from the original layers equals the stored '
           'code, then for every valid Polygon or MultiPolygon the stored path returns exactly the original-layers '
           'output under the shared centre rule (engine.query.select_cells). Exhaustive cell equality therefore '
           'implies equality for all polygons, not just the 17 plots.')
LIMITATIONS = [
    'The rule is JRC 2020 read at each Hansen cell centre, the middle cell of a 3x3 block; JRC sub-cell detail is dropped, not reproduced.',
    'Dropped attributes are listed, not called lossless: treecover2000, loss years 2001-2020 and, at eudr-decision.v1, loss years on JRC non-forest land.',
    'Counts are Hansen cells, not hectares; no area is inferred.',
    'Outputs are mapped observations from public layers, not legal compliance findings.',
    'Equality is proved against the original layers under the shared selection rule, not against satellite ground truth.',
    'The real chip has no datamask-0 cells and no invalid masks; nodata and mask-invalid branches are covered by the synthetic unit tests.',
]
CATEGORIES = (('convex', 14), ('star', 14), ('centre_rect', 13), ('mixed_rect', 6), ('holes', 10), ('multi', 10),
              ('tiny', 10), ('water', 7), ('jrc_edge', 8), ('outside', 5), ('invalid', 2), ('large', 1))


def same(left, right):
    return canonical_bytes(left) == canonical_bytes(right)


def sha(array):
    return hashlib.sha256(np.ascontiguousarray(array).tobytes()).hexdigest()


def jsonable(value):
    return json.loads(json.dumps(value, sort_keys=True, default=str))


def decode_stores(root):
    """Decoded code rasters for stores that exist; a missing reader or file is recorded (build_proof fails the gate)."""
    try:
        from .decision_store import read_store
    except ModuleNotFoundError as exc:
        if exc.name != f'{__package__}.decision_store':
            raise
        read_store = None
    out = {}
    for level, relative in STORES.items():
        path, info, codes = Path(root) / relative, {'path': relative, 'status': 'file_absent'}, None
        if path.is_file():
            info.update(bytes=path.stat().st_size, sha256=sha256_file(path), status='reader_absent')
            if read_store is not None:
                codes, header = read_store(path)
                codes = np.asarray(codes)
                info.update(status='decoded', decoded_shape=list(codes.shape), decoded_code_sha256=sha(codes),
                            header=jsonable(header))
        out[level] = (codes, info)
    return out


def compare_codes(original, other):
    if other.shape != original.shape:
        return {'status': 'shape_mismatch', 'mismatches': int(original.size)}
    return {'status': 'compared', 'mismatches': int((original != other).sum())}


def exhaustive(hansen, jrc, derived, stores):
    """Per-level cell-by-cell comparison of float-path original codes with derived and decoded codes."""
    originals, out = {}, {}
    for level, codes in derived.items():
        original = originals[level] = O.exhaustive_attribute_codes(hansen, jrc, level)
        store_codes = stores[level][0]
        out[level] = {'cells_compared': int(original.size), 'original_code_sha256': sha(original),
                      'code_histogram': np.bincount(original.ravel(), minlength=D.CODE_COUNT).tolist(),
                      'original_vs_derived': compare_codes(original, codes),
                      'original_vs_store': (compare_codes(original, store_codes) if store_codes is not None
                                            else {'status': stores[level][1]['status'], 'mismatches': None})}
    return originals, out


def plot_proof(hansen, jrc, plots, derived, stores):
    """Full-dict equality on the 17 plots: original vs derived codes and vs decoded stores."""
    out, outputs = {}, {}
    for level, codes in derived.items():
        store_codes, rows = stores[level][0], []
        for plot in plots:
            want = O.evaluate_original(hansen, jrc, plot['geometry'], level)
            via_codes = D.evaluate_codes(codes, hansen.metadata, plot['geometry'], level)
            via_store = (D.evaluate_store(store_codes, stores[level][1]['header'], plot['geometry'], level)
                         if store_codes is not None else None)
            outputs[level, plot['plot_id']] = want
            rows.append({'plot_id': plot['plot_id'], 'geometry_sha256': object_hash(plot['geometry']),
                         'output_sha256': object_hash(want), 'equal_derived': same(want, via_codes),
                         'equal_store': None if via_store is None else same(want, via_store), 'output': want})
        out[level] = {'plot_count': len(rows), 'equal_derived': sum(r['equal_derived'] for r in rows),
                      'equal_store': None if store_codes is None else sum(r['equal_store'] for r in rows),
                      'outputs_sha256': object_hash([r['output_sha256'] for r in rows]), 'plots': rows}
    return out, outputs


class Fuzz:
    """Deterministic polygon generator over the Hansen index space (centre of col k at u=k+.5)."""

    def __init__(self, hansen, seed):
        self.rng = random.Random(seed)
        self.h, self.w = hansen.metadata['shape']
        self.a, _, self.c, _, self.e, self.f = hansen.metadata['transform']
        wet = (hansen.bands[2] == 2) & hansen.masks[2]
        self.water = [(int(r), int(c)) for r, c in np.argwhere(wet)]

    def pt(self, u, v):
        return [self.c + u * self.a, self.f + v * self.e]

    def ring(self, uv):
        points = [self.pt(u, v) for u, v in uv]
        return points + [list(points[0])]

    def size(self, low=.5, high=40.):
        return math.exp(self.rng.uniform(math.log(low), math.log(high)))

    def where(self):
        m = self.rng.choice((3, 8, 20))
        return self.rng.uniform(-m, self.w + m), self.rng.uniform(-m, self.h + m)

    def span(self, u0, u1, snap):
        """Interval ends; snapped ends sit exactly on centre lines (k+.5)."""
        if snap:
            u0, u1 = math.floor(u0) + .5, math.floor(u1) + .5
            return (u0, u0 + 1) if u1 <= u0 else (u0, u1)
        return (u0, u0 + .2) if u1 - u0 < .2 else (u0, u1)

    def rect(self, u0, u1, v0, v1):
        return [self.ring([(u0, v0), (u1, v0), (u1, v1), (u0, v1)])]

    def box(self, size=None):
        u, v = self.where()
        size, ratio = size or self.size(), self.rng.uniform(.4, 2.5)
        return u, u + size * ratio, v, v + size

    def comp(self, kind, box, snap=False):
        """Polygon coordinates inside a (u0, u1, v0, v1) box."""
        u0, u1, v0, v1 = box
        if kind == 'rect':
            (u0, u1), (v0, v1) = self.span(u0, u1, snap), self.span(v0, v1, snap)
            return self.rect(u0, u1, v0, v1)
        if kind == 'star':
            n, cu, cv = self.rng.randint(5, 14), (u0 + u1) / 2, (v0 + v1) / 2
            radius, step = min(u1 - u0, v1 - v0) / 2, 2 * math.pi / n
            angles = [(i + self.rng.uniform(-.4, .4)) * step for i in range(n)]
            radii = [self.rng.uniform(.3, 1) * radius for _ in angles]
            return [self.ring([(cu + q * math.cos(t), cv + q * math.sin(t)) for q, t in zip(radii, angles)])]
        points = [self.pt(self.rng.uniform(u0, u1), self.rng.uniform(v0, v1)) for _ in range(self.rng.randint(3, 9))]
        hull = MultiPoint(points).convex_hull
        return [[list(p) for p in hull.exterior.coords]] if hull.geom_type == 'Polygon' else self.rect(u0, u1, v0, v1)

    def polygon(self, coordinates):
        return {'type': 'Polygon', 'coordinates': coordinates}

    def make(self, category):
        r = self.rng
        if category in ('convex', 'star'):
            return self.polygon(self.comp(category, self.box()))
        if category == 'centre_rect':
            return self.polygon(self.comp('rect', self.box(), snap=True))
        if category == 'mixed_rect':
            u0, u1, v0, v1 = self.box()
            (u0, u1), (v0, v1) = self.span(u0, u1, r.random() < .5), self.span(v0, v1, r.random() < .5)
            return self.polygon(self.rect(u0, u1, v0, v1))
        if category == 'holes':
            u0, u1, v0, v1 = self.box(self.size(5, 40))
            u1, v1 = max(u1, u0 + 5), max(v1, v0 + 5)
            snap = r.random() < .5
            (u0, u1), (v0, v1) = self.span(u0, u1, snap), self.span(v0, v1, snap)
            hu0 = r.uniform(u0 + 1, u1 - 3)
            hv0 = r.uniform(v0 + 1, v1 - 3)
            hu1, hv1 = r.uniform(hu0 + 2, u1 - 1), r.uniform(hv0 + 2, v1 - 1)
            (hu0, hu1), (hv0, hv1) = self.span(hu0, hu1, r.random() < .5), self.span(hv0, hv1, r.random() < .5)
            return self.polygon(self.rect(u0, u1, v0, v1) + self.rect(hu0, hu1, hv0, hv1))
        if category == 'multi':
            cursor, v = self.where()
            parts = []
            for _ in range(r.randint(2, 3)):
                width = r.uniform(1, 15)
                top = v + r.uniform(-5, 5)
                parts.append(self.comp(r.choice(('rect', 'star', 'convex')), (cursor, cursor + width, top, top + r.uniform(1, 15)),
                                       snap=r.random() < .5))
                cursor += width + r.uniform(1.5, 6)
            return {'type': 'MultiPolygon', 'coordinates': parts}
        if category == 'tiny':
            u, v = self.where()
            kind = r.choice(('centre', 'gap', 'vertex', 'sliver'))
            k, j = math.floor(u), math.floor(v)
            if kind == 'centre':
                s = r.uniform(.001, .4)
                return self.polygon(self.rect(k + .5 - s, k + .5 + s, j + .5 - s, j + .5 + s))
            if kind == 'gap':
                s = r.uniform(.01, .2)
                return self.polygon(self.rect(k + .6, k + .6 + s, j + .6, j + .6 + s))
            if kind == 'vertex':
                s = r.uniform(.01, .5)
                return self.polygon([self.ring([(k + .5, j + .5), (k + .5 + s, j + .5), (k + .5, j + .5 + s)])])
            return self.polygon(self.rect(k + .5 - .0005, k + .5 + .0005, j + .5 - r.randint(0, 6), j + .5 + r.randint(1, 6)))
        if category == 'water':
            row, col = r.choice(self.water)
            if r.random() < .5:
                u0, u1 = col + .5 - r.randint(0, 5), col + .5 + r.randint(0, 5)
                v0, v1 = row + .5 - r.randint(0, 5), row + .5 + r.randint(0, 5)
                (u0, u1), (v0, v1) = self.span(u0, u1, True), self.span(v0, v1, True)
            else:
                half = r.uniform(.5, 6)
                u0, u1, v0, v1 = col + .5 - half, col + .5 + r.uniform(.2, 6), row + .5 - half, row + .5 + r.uniform(.2, 6)
            return self.polygon(self.rect(u0, u1, v0, v1))
        if category == 'jrc_edge':
            edge, snap = r.choice(('col0', 'colN', 'rowN', 'row0')), r.random() < .5
            near, far = r.uniform(0, 3), r.uniform(0, 3)
            along = r.uniform(0, (self.h if edge.startswith('col') else self.w) - 1)
            along_end = along + r.uniform(1, 10)
            if edge.startswith('col'):
                line = .5 if edge == 'col0' else self.w - .5
                (u0, u1), (v0, v1) = self.span(line - near, line + far, snap), self.span(along, along_end, snap)
            else:
                line = .5 if edge == 'row0' else self.h - .5
                (v0, v1), (u0, u1) = self.span(line - near, line + far, snap), self.span(along, along_end, snap)
            return self.polygon(self.rect(u0, u1, v0, v1))
        if category == 'outside':
            side, snap, s = r.choice(('left', 'right', 'top', 'bottom', 'edge')), r.random() < .5, self.size(1, 8)
            if side in ('left', 'right'):
                u0 = r.uniform(-20, -s) if side == 'left' else r.uniform(self.w, self.w + 15)
                v0 = r.uniform(-5, self.h)
            elif side in ('top', 'bottom'):
                v0 = r.uniform(-20, -s) if side == 'top' else r.uniform(self.h, self.h + 15)
                u0 = r.uniform(-5, self.w)
            else:
                u0, v0 = r.uniform(-s, self.w), r.uniform(-s, self.h)
            (u0, u1), (v0, v1) = self.span(u0, u0 + s, snap), self.span(v0, v0 + s, snap)
            return self.polygon(self.rect(u0, u1, v0, v1))
        if category == 'invalid':
            u, v = self.where()
            x0, y0 = self.pt(u, v)
            x1, y1 = self.pt(u + 3, v + 3)
            kind = r.choice(('bowtie', 'unclosed', 'short', 'flat'))
            rings = {'bowtie': [[x0, y0], [x1, y1], [x1, y0], [x0, y1], [x0, y0]],
                     'unclosed': [[x0, y0], [x1, y0], [x1, y1], [x0, y1]],
                     'short': [[x0, y0], [x1, y1], [x0, y0]],
                     'flat': [[x0, y0], [x0, y0], [x0, y1], [x0, y1], [x0, y0]]}
            return self.polygon([rings[kind]])
        size = r.uniform(60, 150)  # large
        return self.polygon(self.comp(r.choice(('rect', 'star', 'convex')), self.box(size), snap=r.random() < .5))

    def geometries(self, count):
        weights = [w for _, w in CATEGORIES]
        for _ in range(count):
            category = self.rng.choices([c for c, _ in CATEGORIES], weights)[0]
            yield category, self.make(category)


def tally(output):
    """Branch labels reached by one output; shows what the fuzz exercised."""
    labels = [f"support={output['support']}", f"forest={output['forest_2020']['present']}",
              f"deforestation={output['deforestation_after_2020']['present']}"]
    labels += ['outside>0'] * (output['out_of_coverage_cell_count'] > 0)
    labels += ['water>0'] * (output['water_cell_count'] > 0)
    labels += ['selected=0'] * (output['selected_cell_count'] == 0) + ['selected=1'] * (output['selected_cell_count'] == 1)
    counts = output['forest_2020']['cell_counts']
    labels += ['forest_unknown>0'] * bool(counts and counts['unknown'])
    labels += [f"{key}={value['mapped_loss_present']}" for key, value in output.get('hansen_loss_after_2020', {'periods': {}})['periods'].items()]
    return labels


def attempt(function, *args):
    try:
        return True, function(*args)
    except ValueError as error:
        return False, str(error)


def fuzz(hansen, jrc, derived, stores, count=FUZZ_COUNT, seed=FUZZ_SEED):
    """Compare original vs derived (and decoded) outputs on seeded synthetic polygons."""
    stats = {level: {'compared': 0, 'equal_derived': 0, 'equal_store': 0 if stores[level][0] is not None else None}
             for level in derived}
    categories, rejected, geometries, coverage, mismatches = {}, {}, hashlib.sha256(), {}, []
    digest = hashlib.sha256()
    valid = equal = 0
    started = time.perf_counter()
    for index, (category, geometry) in enumerate(Fuzz(hansen, seed).geometries(count)):
        categories[category] = categories.get(category, 0) + 1
        geometries.update(canonical_bytes(geometry))
        runs = {}
        for level, codes in derived.items():
            runs[level] = {'original': attempt(O.evaluate_original, hansen, jrc, geometry, level),
                           'equal_derived': attempt(D.evaluate_codes, codes, hansen.metadata, geometry, level)}
            if stores[level][0] is not None:
                runs[level]['equal_store'] = attempt(D.evaluate_store, stores[level][0], stores[level][1]['header'], geometry, level)
        accepted = {ok for paths in runs.values() for ok, _ in paths.values()}
        if accepted == {False}:
            rejected[category] = rejected.get(category, 0) + 1
            continue
        if accepted != {True}:
            mismatches.append({'index': index, 'category': category, 'issue': 'validity differs between paths'})
            continue
        valid += 1
        every = True
        for level, paths in runs.items():
            want = paths['original'][1]
            stats[level]['compared'] += 1
            for key in paths.keys() - {'original'}:
                if same(want, paths[key][1]):
                    stats[level][key] += 1
                else:
                    every = False
                    mismatches.append({'index': index, 'category': category, 'level': level, 'path': key})
            digest.update(canonical_bytes([index, category, level, want]))
            for label in tally(want):
                coverage.setdefault(level, {})[label] = coverage.setdefault(level, {}).get(label, 0) + 1
        equal += every
    return {'seed': seed, 'generated': sum(categories.values()), 'rejected_invalid': sum(rejected.values()), 'rejected_by_category': rejected,
            'compared': valid, 'equal': equal, 'categories': dict(sorted(categories.items())), 'levels': stats,
            'mismatches': mismatches[:20], 'mismatch_count': len(mismatches),
            'geometry_set_sha256': geometries.hexdigest(), 'output_digest_sha256': digest.hexdigest(),
            'branch_coverage': {level: dict(sorted(labels.items())) for level, labels in coverage.items()},
            'store_compared': any(stats[level]['equal_store'] is not None for level in stats),
            'runtime_seconds': round(time.perf_counter() - started, 2)}


def v1_crosscheck(hansen, plots, screen_outputs):
    """eudr-screen.v1 Hansen loss 2021-2025 and period flags equal the retained v1 outputs."""
    rows = []
    for plot in plots:
        v1, l1 = v1_evaluate(hansen, plot['geometry']), screen_outputs[D.SCREEN_VERSION, plot['plot_id']]
        yearly = v1['yearly_loss_counts']
        yearly = None if yearly is None else {str(y): yearly[str(y)] for y in D.POST_YEARS}
        loss = l1['hansen_loss_after_2020']
        accounting = [v1[k] for k in ('selected_cell_count', 'out_of_coverage_cell_count', 'valid_land_cell_count',
                                      'unknown_cell_count', 'support')]
        l1_accounting = [l1[k] for k in ('selected_cell_count', 'out_of_coverage_cell_count', 'valid_land_cell_count',
                                         'unknown_cell_count', 'support')]
        rows.append({'plot_id': plot['plot_id'], 'yearly_equal': same(yearly, loss['yearly_cell_counts']),
                     'periods_equal': same(v1['periods'], loss['periods']), 'accounting_equal': same(accounting, l1_accounting)})
    return {'plots': len(rows), 'equal': all(r['yearly_equal'] and r['periods_equal'] for r in rows),
            'accounting_equal': all(r['accounting_equal'] for r in rows), 'per_plot': rows,
            'note': 'v1 and the decision layers both treat a cell as known only if all three Hansen masks are valid (the real chip has no invalid masks).'}


def negative_controls(hansen, jrc, plots, derived, originals):
    """Deliberate breakage that the proof must detect, plus dropped detail it must not."""
    plot = plots[0]
    geometry, controls = plot['geometry'], {}
    rows, cols = select_cells(hansen.metadata, geometry)
    base = O.evaluate_original(hansen, jrc, geometry, D.SCREEN_VERSION)

    flips = {}
    for level, codes in derived.items():
        r, c = int(rows[0]), int(cols[0])
        flipped = codes.copy()
        flipped[r, c] = 0 if codes[r, c] else 1
        want = O.evaluate_original(hansen, jrc, geometry, level)
        flips[level] = {'cell': [r, c], 'code_before': int(codes[r, c]), 'code_after': int(flipped[r, c]),
                        'exhaustive_mismatches': int((originals[level] != flipped).sum()),
                        'plot_output_differs': not same(want, D.evaluate_codes(flipped, hansen.metadata, geometry, level))}
    controls['flipped_code'] = {'plot_id': plot['plot_id'], 'levels': flips, 'expected_mismatches': 1,
                                'detected': all(v['exhaustive_mismatches'] == 1 and v['plot_output_differs'] for v in flips.values())}

    moved = None
    for step in range(1, 40):
        shifted = json.loads(json.dumps(geometry))
        ring = shifted['coordinates'][0]
        ring[0][0] += .0004 * step
        ring[-1] = list(ring[0])
        ok, result = attempt(O.evaluate_original, hansen, jrc, shifted, D.SCREEN_VERSION)
        if ok and not same(result, base):
            moved = {'vertex_index': 0, 'shift_degrees_x': .0004 * step, 'output_sha256_before': object_hash(base),
                     'output_sha256_after': object_hash(result), 'selected_before': base['selected_cell_count'],
                     'selected_after': result['selected_cell_count']}
            break
    controls['moved_vertex'] = {'plot_id': plot['plot_id'], **(moved or {}), 'detected': moved is not None}

    attrs = O.cell_attributes(hansen, jrc, rows, cols)
    pick = int(np.flatnonzero((attrs['hansen'] == 'land') & (attrs['forest'] == 'forest'))[0])
    jr, jc = int(attrs['jrc_row'][pick]), int(attrs['jrc_col'][pick])
    bent = jrc.values.copy()
    bent[jr, jc] = 0
    after = O.evaluate_original(hansen, JrcDataset(bent, jrc.mask, jrc.metadata), geometry, D.SCREEN_VERSION)
    stored = D.evaluate_codes(derived[D.SCREEN_VERSION], hansen.metadata, geometry, D.SCREEN_VERSION)
    controls['flipped_jrc_forest_bit'] = {
        'plot_id': plot['plot_id'], 'jrc_cell': [jr, jc], 'forest_counts_before': base['forest_2020']['cell_counts'],
        'forest_counts_after': after['forest_2020']['cell_counts'],
        'detected': after['forest_2020']['cell_counts'] != base['forest_2020']['cell_counts'] and not same(after, stored)}

    # Dropped detail must not matter: JRC cells that are no Hansen centre, canopy percentages, loss years 2001-2020.
    grid = np.meshgrid(np.arange(hansen.metadata['shape'][0]), np.arange(hansen.metadata['shape'][1]), indexing='ij')
    seen = O.cell_attributes(hansen, jrc, *grid)
    centre = np.zeros(jrc.values.shape, bool)
    centre[seen['jrc_row'][seen['jrc_row'] >= 0], seen['jrc_col'][seen['jrc_row'] >= 0]] = True
    canopy, older = hansen.bands.copy(), hansen.bands.copy()
    canopy[0] = 100 - canopy[0]
    old = (older[1] >= 1) & (older[1] <= 20)
    older[1][old] = 21 - older[1][old]
    variants = {'jrc_noncentre_inversion': (hansen, JrcDataset(np.where(centre, jrc.values, 1 - jrc.values).astype(np.uint8), jrc.mask, jrc.metadata)),
                'treecover_inversion': (Dataset(canopy, hansen.masks, hansen.metadata), jrc),
                'lossyear_2001_2020_reversal': (Dataset(older, hansen.masks, hansen.metadata), jrc)}
    changed = {name: int((O.exhaustive_attribute_codes(h, j, D.SCREEN_VERSION) != originals[D.SCREEN_VERSION]).sum())
               for name, (h, j) in variants.items()}
    controls['dropped_detail'] = {'jrc_noncentre_cells_inverted': int((~centre).sum()), 'lossyear_cells_changed': int(old.sum()),
                                  'changed_code_cells': changed, 'ignored_as_designed': not any(changed.values()),
                                  'note': 'not in either contract, so changing them must change no code'}
    return controls


def inputs(hansen, jrc, root):
    chip = next(r for r in jrc.metadata['required_inputs'] if r['path'] == JRC_CHIP)
    return {'hansen_chips': [{k: s[k] for k in ('band', 'path', 'sha256', 'bytes')} for s in hansen.metadata['sources']],
            'jrc_chip': chip,
            'supplier_files': [{'path': str(SAMPLE / name), 'sha256': sha256_file(Path(root) / SAMPLE / name)}
                               for name in (CSV_NAME, GEOJSON_NAME)]}


def build_proof(root=None, fuzz_count=FUZZ_COUNT, seed=FUZZ_SEED, allow_missing_stores=False):
    """Run every check. A missing or unreadable store file fails the gate unless allow_missing_stores."""
    root = Path(root) if root is not None else ROOT
    hansen, jrc, plots = load_source(root), load_jrc(root), load_plots(root)
    screen = D.derive_screen_codes(hansen, jrc)
    derived = {D.SCREEN_VERSION: screen, D.DECISION_VERSION: D.project_decision(screen)}
    stores = decode_stores(root)
    originals, cells = exhaustive(hansen, jrc, derived, stores)
    plot_levels, outputs = plot_proof(hansen, jrc, plots, derived, stores)
    fuzzed = fuzz(hansen, jrc, derived, stores, fuzz_count, seed)
    crosscheck = v1_crosscheck(hansen, plots, outputs)
    controls = negative_controls(hansen, jrc, plots, derived, originals)
    decoded = [level for level in derived if stores[level][0] is not None]
    passed = {
        'exhaustive_original_vs_derived': all(c['original_vs_derived']['mismatches'] == 0 for c in cells.values()),
        'plots_original_vs_derived': all(p['equal_derived'] == p['plot_count'] for p in plot_levels.values()),
        'fuzz_equal': fuzzed['mismatch_count'] == 0 and fuzzed['equal'] == fuzzed['compared'] > 0,
        'fuzz_generator_sane': fuzzed['rejected_by_category'].keys() <= {'invalid'}
        and fuzzed['rejected_by_category'].get('invalid', 0) == fuzzed['categories'].get('invalid', 0),
        'v1_crosscheck': crosscheck['equal'],
        'negative_controls_detected': all(controls[k]['detected'] for k in ('flipped_code', 'moved_vertex', 'flipped_jrc_forest_bit')),
        'dropped_detail_ignored': controls['dropped_detail']['ignored_as_designed'],
        'stores_present_and_readable': all(info['status'] in (('decoded', 'file_absent') if allow_missing_stores else ('decoded',))
                                           for _, info in stores.values())}
    if decoded:
        passed.update(
            exhaustive_original_vs_store=all(cells[level]['original_vs_store']['mismatches'] == 0 for level in decoded),
            plots_original_vs_store=all(plot_levels[level]['equal_store'] == plot_levels[level]['plot_count'] for level in decoded),
            fuzz_store_equal=all(fuzzed['levels'][level]['equal_store'] == fuzzed['levels'][level]['compared'] for level in decoded))
    return {
        'schema': SCHEMA, 'contracts': list(D.LEVELS), 'selection_rule': 'engine.query.select_cells (covered centres, boundaries included)',
        'grid_rule': D.GRID_RULE, 'inputs': inputs(hansen, jrc, root),
        'derived_codes': {level: {'shape': list(codes.shape), 'code_sha256': sha(codes)} for level, codes in derived.items()},
        'stores': {level: info for level, (_, info) in stores.items()},
        'exhaustive_cell_proof': cells, 'plot_proof': plot_levels, 'fuzz': fuzzed, 'v1_crosscheck': crosscheck,
        'negative_controls': controls, 'theorem': THEOREM, 'limitations': LIMITATIONS,
        'summary': {'checks': passed, 'all_pass': all(passed.values()), 'store_comparison': bool(decoded),
                    'allow_missing_stores': allow_missing_stores,
                    'cells_compared': cells[D.SCREEN_VERSION]['cells_compared'], 'plots': len(plots),
                    'fuzz_compared': fuzzed['compared']},
        'environment': {'python': platform.python_version(), 'numpy': np.__version__, 'shapely': shapely.__version__,
                        'rasterio': rasterio.__version__},
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, default=ROOT)
    parser.add_argument('--output', type=Path)
    parser.add_argument('--fuzz', type=int, default=FUZZ_COUNT, help='number of seeded polygons')
    parser.add_argument('--allow-missing-stores', action='store_true',
                        help='do not fail when a store file is absent (the store comparison is then skipped)')
    args = parser.parse_args(argv)
    proof = build_proof(args.root, args.fuzz, allow_missing_stores=args.allow_missing_stores)
    output = args.output or args.root / OUTPUT
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(proof, indent=1, sort_keys=True, allow_nan=False) + '\n')
    print(json.dumps({'artifact': str(output), 'summary': proof['summary'],
                      'fuzz': {k: proof['fuzz'][k] for k in ('generated', 'compared', 'equal', 'rejected_invalid', 'runtime_seconds')}}, indent=1))
    return 0 if proof['summary']['all_pass'] else 1


if __name__ == '__main__':
    sys.exit(main())
