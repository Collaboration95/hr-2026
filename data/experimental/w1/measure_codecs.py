"""Bounded W1 measurements; canonical benchmark/final artifacts belong to W3.

Run from repository root: .venv-data/bin/python data/experimental/w1/measure_codecs.py
All generated files remain under this worker's scratch directory.
"""
from compression import zstd
import argparse
from datetime import datetime, timezone
import json
import platform
from pathlib import Path
import statistics
import sys
import time

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))

import numpy as np
from engine.codecs import CANDIDATES, CANDIDATE_LEVELS, decode_store, encode_store, read_window
from engine.model import Dataset
from engine.query import evaluate
from engine.source import (canonical_bytes, load_plots, load_source, sha256_file,
                           object_hash, SAMPLE, CSV_NAME, GEOJSON_NAME)

SCRATCH = Path(__file__).resolve().parent
REPETITIONS = 5
WARMUPS = 1
CHUNK_SIZES = (128, 256, 512, 1024)
WINDOW = (256, 288, 256, 288)


def stats(values):
    return {'median': statistics.median(values), 'min': min(values),
            'p95': float(np.percentile(values, 95)), 'samples': values}


def timed(operation):
    for _ in range(WARMUPS):
        operation()
    wall, cpu = [], []
    result = None
    for _ in range(REPETITIONS):
        w0, c0 = time.perf_counter_ns(), time.process_time_ns()
        result = operation()
        wall.append((time.perf_counter_ns()-w0)/1e6)
        cpu.append((time.process_time_ns()-c0)/1e6)
    return result, {'wall_ms': stats(wall), 'cpu_ms': stats(cpu)}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--cycle2', action='store_true', help='levels 3/9/19; preserve first handoff measurements')
    args = parser.parse_args()
    candidates = (('separate_zstd', 'separate_zstd_l9', 'separate_zstd_l19') if args.cycle2
                  else tuple(c for c in CANDIDATES if CANDIDATE_LEVELS[c] == 3))
    source = load_source(ROOT)
    plots = load_plots(ROOT)
    expected = [evaluate(source, p['geometry']) for p in plots]
    baseline_metadata = SCRATCH / 'baseline-metadata.json'
    baseline_metadata.write_bytes(canonical_bytes(source.metadata))
    provenance_path = ROOT / 'data/public/provenance.json'
    acquisition_bytes = provenance_path.stat().st_size
    shared_paths = [provenance_path, ROOT / SAMPLE / CSV_NAME, ROOT / SAMPLE / GEOJSON_NAME]
    shared_inputs = [{'path': str(p.relative_to(ROOT)), 'bytes': p.stat().st_size,
                      'sha256': sha256_file(p)} for p in shared_paths]
    common_bytes = sum(p['bytes'] for p in shared_inputs)
    chip_bytes = sum(v['bytes'] for v in source.metadata['sources'])
    report = {
        'scope': 'same full native source AOI; W1 preliminary size/codec measurements',
        'cycle': 2 if args.cycle2 else 1,
        'measured_at_utc': datetime.now(timezone.utc).isoformat(),
        'method': {'repetitions': REPETITIONS, 'warmups': WARMUPS,
                   'cache': 'same process, OS cache warm; not process-cold or disk-cold',
                   'source_load_excluded': True, 'timing_units': 'ms',
                   'encode_durability': 'buffered file write/close/replace; no fsync',
                   'window': list(WINDOW), 'window_semantics': '32x32 in-coverage grid read, not plot query',
                   'p95': 'numpy.percentile linear interpolation of five samples'},
        'environment': {'python': platform.python_version(), 'platform': platform.platform(),
                        'machine': platform.machine(), 'numpy': np.__version__,
                        'zstd': list(zstd.zstd_version_info)},
        'shape': source.metadata['shape'], 'real_plot_count': len(plots),
        'source_hashes': {v['band']: v['sha256'] for v in source.metadata['sources']},
        'code_hashes': {name: sha256_file(ROOT / name) for name in
                       ('engine/codecs.py', 'engine/query.py', 'engine/source.py',
                        'data/experimental/w1/measure_codecs.py')},
        'shared_review_inputs': {'files': shared_inputs, 'total_bytes': common_bytes,
                                'note': 'acquisition manifest plus exact CSV/GeoJSON retained symmetrically for full review data accounting'},
        'baseline_reference': {'geotiff_payload_bytes': chip_bytes,
                               'acquisition_provenance_bytes': acquisition_bytes,
                               'same_metadata_manifest_bytes': baseline_metadata.stat().st_size,
                               'source_loader_required_bytes': chip_bytes + acquisition_bytes,
                               'total_bytes_with_manifest': chip_bytes + acquisition_bytes + baseline_metadata.stat().st_size,
                               'full_review_input_bytes': chip_bytes + common_bytes,
                               'full_review_with_metadata_archive_bytes': chip_bytes + common_bytes + baseline_metadata.stat().st_size,
                               'note': 'GeoTIFF grid is already inside payload; source loader requires acquisition provenance; generated metadata archive is optional and its bytes are reported separately'},
        'candidates': []}
    if args.cycle2:
        original = json.loads((SCRATCH / 'codec-measurements.json').read_text())
        verified = []
        for entry in original['candidates']:
            path = SCRATCH / 'measure-stores' / f"{entry['candidate']}-{entry['chunk_size']}"
            for name, digest in entry['file_hashes'].items():
                assert sha256_file(path / name) == digest
            b, m, md = decode_store(path)
            assert np.array_equal(b, source.bands) and np.array_equal(m, source.masks) and md == source.metadata
            verified.append(str(path.relative_to(ROOT)))
        report['legacy_v1_stores_verified_unchanged'] = verified
    for size in CHUNK_SIZES:
        for candidate in candidates:
            folder = 'measure-stores-cycle2' if args.cycle2 else 'measure-stores'
            path = SCRATCH / folder / f'{candidate}-{size}'
            result, encode_timings = timed(lambda: encode_store(source.bands, source.masks,
                                                                 source.metadata, path, candidate, size))
            (bands, masks, md), decode_timings = timed(lambda: decode_store(path))
            exact = (np.array_equal(bands, source.bands)
                     and np.array_equal(masks, source.masks) and md == source.metadata)
            compact = Dataset(bands, masks, md)
            mismatches = [plots[i]['plot_id'] for i, p in enumerate(plots)
                          if evaluate(compact, p['geometry']) != expected[i]]
            (wb, wm, wmd), window_timings = timed(lambda: read_window(path, *WINDOW))
            rs, re, cs, ce = WINDOW
            window_exact = (np.array_equal(wb, source.bands[:, rs:re, cs:ce])
                            and np.array_equal(wm, source.masks[:, rs:re, cs:ce]))
            _, source_query = timed(lambda: [evaluate(source, p['geometry']) for p in plots])
            _, compact_query = timed(lambda: [evaluate(compact, p['geometry']) for p in plots])
            result.pop('encode_ms')
            result.update({'encode': encode_timings, 'full_decode': decode_timings,
                           'decode_required_total_bytes': result['total_bytes'],
                           'total_bytes_with_retained_acquisition_provenance': result['total_bytes'] + acquisition_bytes,
                           'full_review_input_bytes': result['total_bytes'] + common_bytes,
                           'window_read': window_timings, 'source_17_hot_queries': source_query,
                           'compact_17_hot_queries': compact_query,
                           'full_raw_and_masks_exact': bool(exact), 'metadata_exact': md == source.metadata,
                           'window_raw_and_masks_exact': bool(window_exact),
                           'plot_mismatches': mismatches,
                           'file_hashes': {p.name: sha256_file(p) for p in path.iterdir()}})
            report['candidates'].append(result)
            print(candidate, size, result['total_bytes'],
                  'encode', round(encode_timings['wall_ms']['median'], 3),
                  'decode', round(decode_timings['wall_ms']['median'], 3),
                  'window', round(window_timings['wall_ms']['median'], 3),
                  'mismatches', len(mismatches), flush=True)
    assert all(c['full_raw_and_masks_exact'] and c['window_raw_and_masks_exact']
               and not c['plot_mismatches'] for c in report['candidates'])
    output = SCRATCH / ('codec-measurements-cycle2.json' if args.cycle2 else 'codec-measurements.json')
    if output.exists():
        output = output.with_stem(output.stem + '-' + object_hash(report)[:12])
    output.write_text(json.dumps(report, indent=2, allow_nan=False)+'\n')
    print(output.relative_to(ROOT))


if __name__ == '__main__':
    main()
