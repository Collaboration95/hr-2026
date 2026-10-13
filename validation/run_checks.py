"""Independent, read-only raster/codec/query/export audit; no production helpers.

Run from repository root: .venv-data/bin/python -B validation/run_checks.py
Writes only docs/lab/validator-checks.json. Source selection uses scalar exact
ray casting; codec decoding follows the published bit layout independently.
"""
import argparse
from compression import zstd
from collections import Counter
import csv
from fractions import Fraction
import hashlib
import json
import math
from pathlib import Path
import statistics
import struct
import sys
import time
import urllib.request

import numpy as np
import rasterio
from rasterio.windows import Window

ROOT = Path(__file__).resolve().parents[1]
NAMES = ('treecover2000', 'lossyear', 'datamask')
PERIODS = {'2021-2023': (21, 23), '2024-2025': (24, 25)}


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':'),
                                     allow_nan=False).encode()).hexdigest()


def file_hash(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for data in iter(lambda: stream.read(1024 * 1024), b''):
            h.update(data)
    return h.hexdigest()


def ring_contains(ring, x, y):
    """Exact arithmetic over input binary floats; returns inside or boundary."""
    x, y = Fraction(x), Fraction(y)
    inside = False
    for p, q in zip(ring, ring[1:]):
        ax, ay = map(Fraction, p)
        bx, by = map(Fraction, q)
        cross = (bx-ax)*(y-ay)-(by-ay)*(x-ax)
        if cross == 0 and min(ax, bx) <= x <= max(ax, bx) and min(ay, by) <= y <= max(ay, by):
            return 2
        if (ay > y) != (by > y):
            hit = ax + (y-ay)*(bx-ax)/(by-ay)
            if x < hit:
                inside = not inside
    return int(inside)


def selected_cells(metadata, geometry):
    polygons = [geometry['coordinates']] if geometry['type'] == 'Polygon' else geometry['coordinates']
    points = [p for polygon in polygons for ring in polygon for p in ring]
    a, _, ox, _, e, oy = metadata['transform']
    left, right = min(p[0] for p in points), max(p[0] for p in points)
    bottom, top = min(p[1] for p in points), max(p[1] for p in points)
    r0, r1 = math.floor((top-oy)/e)-2, math.ceil((bottom-oy)/e)+2
    c0, c1 = math.floor((left-ox)/a)-2, math.ceil((right-ox)/a)+2
    if (r1-r0+1)*(c1-c0+1) > 200000:
        raise ValueError('independent check exceeds bounded 200000 candidate cells')
    selected = []
    for r in range(r0, r1+1):
        y = oy + (r+.5)*e
        for c in range(c0, c1+1):
            x = ox + (c+.5)*a
            for polygon in polygons:
                outer = ring_contains(polygon[0], x, y)
                holes = [ring_contains(h, x, y) for h in polygon[1:]]
                if outer and not any(h == 1 for h in holes):
                    selected.append((r, c))
                    break
    return selected


def result_for(bands, masks, metadata, geometry, missing=()):
    cells = selected_cells(metadata, geometry)
    h, w = metadata['shape']
    outside = 0
    inside = 0
    unknown = 0
    canopy = [0]*101
    losses = [0]*26
    mask_counts = {'0': 0, '1': 0, '2': 0}
    reasons = set()
    valid_land = 0
    for r, c in cells:
        if not (0 <= r < h and 0 <= c < w):
            outside += 1
            unknown += 1
            reasons.add('out_of_coverage')
            continue
        inside += 1
        values = [int(bands[i, r, c]) for i in range(3)]
        valid = [bool(masks[i, r, c]) and NAMES[i] not in missing for i in range(3)]
        if valid[2]:
            mask_counts[str(values[2])] += 1
        nodata = valid[2] and values[2] == 0
        invalid = not all(valid)
        if nodata:
            reasons.add('nodata')
        if invalid:
            reasons.add('band_mask_invalid')
        if nodata or invalid:
            unknown += 1
        if all(valid) and values[2] == 1:
            valid_land += 1
            canopy[values[0]] += 1
            losses[values[1]] += 1
    if not cells:
        reasons.add('no_selected_cells')
    if cells and not valid_land:
        reasons.add('no_valid_land')
    if missing:
        unknown = len(cells)
    ordered = [r for r in ('no_selected_cells', 'out_of_coverage', 'nodata', 'band_mask_invalid', 'no_valid_land') if r in reasons]
    ordered += ['missing_band:'+n for n in NAMES if n in missing]
    analytical = valid_land > 0 and not missing
    periods = {}
    for key, (lo, hi) in PERIODS.items():
        count = sum(losses[lo:hi+1]) if analytical else None
        flag = (True if count else None if unknown else False) if analytical else None
        periods[key] = {'mapped_loss_present': flag, 'observed_loss_cell_count': count}
    support = 'unavailable' if missing else 'none' if not cells or not valid_land else 'partial' if unknown else 'complete'
    return {'selected_cell_count': len(cells), 'in_coverage_cell_count': inside,
            'out_of_coverage_cell_count': outside, 'valid_land_cell_count': valid_land,
            'unknown_cell_count': unknown, 'datamask_counts': mask_counts,
            'canopy_histogram': canopy if analytical else None,
            'lossyear_histogram': losses if analytical else None,
            'yearly_loss_counts': {str(2000+y): losses[y] for y in range(1, 26)} if analytical else None,
            'periods': periods, 'support': support, 'unknown_reasons': ordered}, cells


def independent_decode(path):
    index = json.loads((path/'index.json').read_text())
    payload = (path/'payload.bin').read_bytes()
    assert payload[:12] == struct.pack('<8sI', b'PLCODEC1', 1)
    assert len(payload) == index['payload_bytes']
    assert hashlib.sha256(payload).hexdigest() == index['payload_sha256']
    assert digest({k: v for k, v in index.items() if k != 'index_sha256'}) == index['index_sha256']
    h, w = index['shape']
    bands = np.zeros((3, h, w), dtype=np.uint8)
    masks = np.zeros_like(bands, dtype=bool)
    occupancy = np.zeros((h, w), dtype=np.uint8)
    for chunk in index['chunks']:
        ch, cw = chunk['height'], chunk['width']
        n = ch*cw
        raw = {}
        for name, entry in chunk['streams'].items():
            data = payload[entry['offset']:entry['offset']+entry['size']]
            assert hashlib.sha256(data).hexdigest() == entry['sha256']
            # Checked valid-format streams only; upper bound precedes decompression.
            assert zstd.get_frame_info(data).decompressed_size == entry['raw_size'] <= 3*1024*1024
            dec = zstd.ZstdDecompressor()
            raw[name] = dec.decompress(data, max_length=entry['raw_size']+1)
            assert len(raw[name]) == entry['raw_size'] and dec.eof and not dec.unused_data
            assert hashlib.sha256(raw[name]).hexdigest() == entry['raw_sha256']
        candidate = index['candidate']
        if candidate.startswith('separate_zstd'):
            cb = np.stack([np.frombuffer(raw[name], dtype=np.uint8) for name in NAMES])
        else:
            if candidate == 'uint16_zstd':
                words = np.frombuffer(raw['values'], dtype='<u2')
            else:
                packed = np.unpackbits(np.frombuffer(raw['values'], dtype=np.uint8), bitorder='little')[:14*n]
                columns = packed.reshape(14, n) if candidate == 'bitplane_zstd' else packed.reshape(n, 14).T
                words = sum(columns[bit].astype(np.uint16)*(1 << bit) for bit in range(14))
            cb = np.stack((words & 127, (words // 128) & 31, (words // 4096) & 3)).astype(np.uint8)
        cm = np.unpackbits(np.frombuffer(raw['masks'], dtype=np.uint8), bitorder='little')[:3*n].reshape(3, ch, cw).astype(bool)
        r, c = chunk['row'], chunk['col']
        bands[:, r:r+ch, c:c+cw] = cb.reshape(3, ch, cw)
        masks[:, r:r+ch, c:c+cw] = cm
        occupancy[r:r+ch, c:c+cw] += 1
    assert np.all(occupancy == 1)
    return bands, masks, index['metadata']


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--artifact', type=Path, default=ROOT/'artifacts/demo-v1.json')
    parser.add_argument('--output', type=Path, default=ROOT/'docs/lab/validator-checks.json')
    parser.add_argument('--skip-http', action='store_true')
    args = parser.parse_args()
    started = time.perf_counter()
    report = {'scope': 'independent first-pass checks', 'checks': [], 'failures': [], 'freshness': {}}
    def check(ok, description, evidence=None):
        report['checks'].append({'pass': bool(ok), 'description': description, 'evidence': evidence})
        if not ok:
            report['failures'].append(description)
    initial = {str(p.relative_to(ROOT)): file_hash(p) for p in [args.artifact, *sorted((ROOT/'engine').glob('*.py'))]}
    artifact = json.loads(args.artifact.read_text())
    provenance = json.loads((ROOT/'data/public/provenance.json').read_text())
    arrays, validity = [], []
    for layer in provenance['layers']:
        chip = ROOT/'data/public'/f"hansen_{layer['band']}_sample.tif"
        raw_path = ROOT/'data/public/raw'/Path(layer['url']).name
        check(file_hash(chip) == layer['chip_sha256'], layer['band']+': acquisition chip digest')
        check(file_hash(raw_path) == layer['source_tile_sha256'], layer['band']+': original source tile digest')
        with rasterio.open(chip) as src, rasterio.open(raw_path) as original:
            col, row, width, height = layer['window']
            window = Window(col, row, width, height)
            values = src.read(1)
            masks = src.read_masks(1) != 0
            check(np.array_equal(values, original.read(1, window=window)), layer['band']+': independent original-window pixel equality')
            check(np.array_equal(masks, original.read_masks(1, window=window) != 0), layer['band']+': original-window validity equality')
            check(list(src.transform)[:6] == list(original.window_transform(window))[:6] == artifact['dataset']['transform'], layer['band']+': grid exactly aligns with source window')
            counts = {str(k): int(v) for k, v in zip(*np.unique(values, return_counts=True))}
            check(counts == layer['value_counts'], layer['band']+': independent full pixel histogram')
            arrays.append(values)
            validity.append(masks)
    bands, masks = np.stack(arrays), np.stack(validity)
    sample = ROOT/'data/company-sample/2026-10-12'
    with next(sample.glob('*.csv')).open(encoding='utf-8-sig', newline='') as stream:
        rows = {r['a3_plot_id']: r for r in csv.DictReader(stream)}
    geometries = {f['properties']['ProductionPlace']: f['geometry'] for f in json.loads(next(sample.glob('*.geojson')).read_text())['features']}
    answers = []
    stores = set()
    for plot in artifact['plots']:
        pid = plot['plot_id']
        check(plot['supplier'] == rows[pid] and plot['geometry'] == geometries[pid], pid+': exact independent supplier/geometry join')
        expected, cells = result_for(bands, masks, artifact['dataset'], geometries[pid])
        answers.append(expected)
        check(expected == plot['source_result'] == plot['compact_result'], pid+': independent scalar complete query agreement', expected['periods'])
        features = plot['evidence']['features']
        check([(f['properties']['row'], f['properties']['col']) for f in features] == cells, pid+': independent native evidence selected set/order')
        a, _, ox, _, e, oy = artifact['dataset']['transform']
        for feature in features:
            p = feature['properties']
            r, c = p['row'], p['col']
            expected_ring = [[ox+c*a, oy+r*e], [ox+(c+1)*a, oy+r*e], [ox+(c+1)*a, oy+(r+1)*e], [ox+c*a, oy+(r+1)*e], [ox+c*a, oy+r*e]]
            assert feature['geometry']['coordinates'] == [expected_ring]
            assert p['center'] == [ox+(c+.5)*a, oy+(r+.5)*e]
            assert [p[n] for n in NAMES] == bands[:, r, c].tolist()
            assert p['band_validity'] == masks[:, r, c].tolist()
        check(True, pid+': every native evidence value/mask/center/footprint checked independently')
        receipt = plot['receipt']
        check(receipt['receipt_sha256'] == digest({k: v for k, v in receipt.items() if k != 'receipt_sha256'}), pid+': receipt digest')
        if receipt.get('compact_store'):
            stores.add(ROOT/receipt['compact_store']['path'])
    check(artifact['content_sha256'] == digest({k: v for k, v in artifact.items() if k != 'content_sha256'}), 'artifact complete content digest')
    check(sum(a['selected_cell_count'] for a in answers) == artifact['summary']['selected_cell_count_sum'], 'summary selected support sum')
    synthetic = json.loads((ROOT/'artifacts/synthetic-v1.json').read_text())
    for case in synthetic['cases']:
        b = np.zeros((3, 4, 4), dtype=np.uint8)
        b[0] = 80
        b[2] = 1
        if case['case_id'] == 'partial_positive_known': b[1, 2, 0] = 24
        if case['case_id'] == 'water_only': b[2] = 2
        if case['case_id'] == 'nodata': b[2, 2, 0] = 0
        expected, _ = result_for(b, np.ones_like(b, dtype=bool), synthetic['dataset'], case['geometry'], case['missing_bands'])
        check(expected == case['result'], 'synthetic '+case['case_id']+': independently reduced unknown contract')
    benchmark = artifact['benchmark']
    source_answer_hash = digest(answers)
    check(source_answer_hash == benchmark['baseline']['queries']['hot']['answer_sha256'][0], 'benchmark timed answers bind to independent real cohort')
    for candidate in benchmark['candidates']:
        if candidate.get('status') != 'measured': continue
        path = ROOT/'artifacts/stores'/benchmark['experiment_id']/candidate['candidate']
        stores.add(path)
        storage = candidate['storage']
        check(sum(p.stat().st_size for p in path.iterdir() if p.is_file()) == storage['total_bytes'], candidate['candidate']+': complete actual stored bytes')
        for f in storage['files']:
            p = path/f['path']
            check(p.stat().st_size == f['bytes'] and file_hash(p) == f['sha256'], candidate['candidate']+': measured file '+f['path'])
        for timing in ('hot', 'process_cold'):
            check(candidate['queries'][timing]['answer_sha256'] == [source_answer_hash], candidate['candidate']+': '+timing+' timed answer digest')
            stats = candidate['queries'][timing]['wall_ms']
            samples = stats['samples']
            check(stats['median'] == statistics.median(samples) and stats['p95'] == sorted(samples)[math.ceil(.95*len(samples))-1], candidate['candidate']+': '+timing+' reported statistics')
    baseline_files = benchmark['baseline']['storage']['files']
    check(sum((ROOT/f['path']).stat().st_size for f in baseline_files) == benchmark['baseline']['storage']['total_bytes'], 'baseline complete storage independently sums')
    for path in sorted(stores):
        b, m, metadata = independent_decode(path)
        check(np.array_equal(b, bands) and np.array_equal(m, masks) and metadata == artifact['dataset'], str(path.relative_to(ROOT))+': independent all-pixel/mask/metadata decode')
    current_benchmark = json.loads((ROOT/'artifacts/benchmark-v1.json').read_text())
    report['freshness']['embedded_equals_canonical_benchmark'] = benchmark == current_benchmark
    report['freshness']['embedded_experiment'] = benchmark['experiment_id']
    report['freshness']['canonical_experiment'] = current_benchmark['experiment_id']
    report['freshness']['embedded_changed_implementation'] = [k for k, v in benchmark['identity']['implementation_sha256'].items() if file_hash(ROOT/'engine'/k) != v]
    if not args.skip_http:
        with urllib.request.urlopen('http://127.0.0.1:5173/data/demo-v1.json', timeout=10) as response:
            served = json.load(response)
        check(served == artifact, 'loopback served artifact equals independently checked canonical demo')
    final = {p: file_hash(ROOT/p) for p in initial}
    check(initial == final, 'artifact/implementation stable during audit', [p for p in initial if initial[p] != final[p]])
    report['source_hashes'] = {str(p.relative_to(ROOT)): file_hash(p) for p in sorted((ROOT/'data/public').glob('*')) if p.is_file()}
    report['raw_values_checked_per_store'] = int(bands.size)
    report['plots'] = len(answers)
    report['selected_count_sum'] = sum(a['selected_cell_count'] for a in answers)
    report['wall_seconds'] = time.perf_counter()-started
    report['pass'] = not report['failures']
    args.output.write_text(json.dumps(report, indent=2)+'\n')
    print(json.dumps({k: v for k, v in report.items() if k != 'checks'}, indent=2))
    return 0 if report['pass'] else 1


if __name__ == '__main__':
    sys.exit(main())
