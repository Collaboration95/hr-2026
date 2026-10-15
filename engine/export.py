"""Generate private, reproducible JSON for the evidence-review experience.

Run: .venv-data/bin/python -m engine.export
No network requests or source writes. Compact outputs stay null until available.
"""
import argparse
import json
import os
from pathlib import Path
import tempfile
import numpy as np
from .model import Dataset, PERIODS, QUERY_VERSION
from .query import evaluate, select_cells
from .proof import receipt_for, summary_for, validate_benchmark
from .source import ROOT, SAMPLE, CSV_NAME, GEOJSON_NAME, load_plots, load_source, object_hash, sha256_file

LIMITATIONS = [
    'Mapped tree-cover loss is not legal deforestation or a compliance verdict.',
    'Treecover2000 describes year-2000 canopy context, not a 2020 forest baseline.',
    'The latest Hansen release may differ from the supplier historical analysis vintage.',
    'Supplier declarations and opaque evidence references are unverified; referenced evidence is unavailable.',
    'Cell counts use native centers covered by each polygon; they are not hectares or complete polygon area.',
    'Exact source/compact agreement measures encoding fidelity, not satellite or legal accuracy.',
    'The 17 supplied plots are a small local cohort, not a representative global evaluation.',
    'JRC 2020 baseline and restriction/legality layers are unavailable in this export.',
    'Company sample publication rights are unresolved; keep this generated demo local.',
]


def atomic_json(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(prefix='.' + path.name, dir=path.parent)
    try:
        with os.fdopen(fd, 'w', encoding='utf-8') as stream:
            json.dump(value, stream, ensure_ascii=False, sort_keys=True, indent=2, allow_nan=False)
            stream.write('\n')
        os.replace(tmp, path)
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)


def differing_fields(left, right, prefix=''):
    if type(left) is not type(right):
        return [prefix or '$']
    if isinstance(left, dict):
        return [item for key in sorted(left.keys() | right.keys()) for item in
                ([f'{prefix}.{key}'.lstrip('.')] if key not in left or key not in right else
                 differing_fields(left[key], right[key], f'{prefix}.{key}'.lstrip('.')))]
    if isinstance(left, list):
        if len(left) != len(right):
            return [prefix]
        return [item for i, (a, b) in enumerate(zip(left, right))
                for item in differing_fields(a, b, f'{prefix}[{i}]')]
    return [] if left == right else [prefix]


def evidence_cells(dataset, geometry):
    rows, cols = select_cells(dataset.metadata, geometry)
    h, w = dataset.metadata['shape']
    a, _, x0, _, e, y0 = dataset.metadata['transform']
    features = []
    for row, col in zip(rows.tolist(), cols.tolist()):
        inside = 0 <= row < h and 0 <= col < w
        props = {'row': row, 'col': col, 'in_coverage': inside,
                 'center': [x0 + (col+.5)*a, y0 + (row+.5)*e]}
        if inside:
            canopy, loss, mask = dataset.bands[:, row, col].tolist()
            validity = dataset.masks[:, row, col].tolist()
            props.update(treecover2000=canopy, lossyear=loss, datamask=mask,
                         band_validity=validity, valid_land=mask == 1 and all(validity))
        else:
            props.update(treecover2000=None, lossyear=None, datamask=None,
                         band_validity=[False]*3, valid_land=False)
        west, east = x0 + col*a, x0 + (col+1)*a
        north, south = y0 + row*e, y0 + (row+1)*e
        features.append({'type': 'Feature', 'id': f'{row}:{col}', 'properties': props,
                         'geometry': {'type': 'Polygon', 'coordinates': [[[west, north], [east, north],
                                       [east, south], [west, south], [west, north]]]}})
    return {'type': 'FeatureCollection', 'features': features}


def export(store=None, output=None, include_benchmark=True):
    source = load_source()
    original_plots = load_plots()
    benchmark_path = ROOT / 'artifacts/benchmark-v1.json'
    benchmark = json.loads(benchmark_path.read_text()) if include_benchmark and benchmark_path.exists() else None
    if benchmark is not None:
        retained_store = validate_benchmark(benchmark, source, original_plots, store=store, root=ROOT)
        if store is None:
            store = retained_store
    compact = None
    store_info = None
    if store is not None:
        from .codecs import decode_store
        bands, masks, metadata = decode_store(Path(store))
        compact = Dataset(bands, masks, metadata).validate()
        if metadata != source.metadata:
            raise ValueError('compact metadata differs from pinned source metadata')
        store_path = Path(store)
        try:
            display_path = str(store_path.resolve().relative_to(ROOT))
        except ValueError:
            display_path = str(store_path.resolve())
        store_info = {'path': display_path,
                      'files': [{'path': str(p.relative_to(store_path)), 'bytes': p.stat().st_size,
                                 'sha256': sha256_file(p)} for p in sorted(store_path.rglob('*')) if p.is_file()],
                      'raw_bands_equal': bool(np.array_equal(bands, source.bands)),
                      'band_masks_equal': bool(np.array_equal(masks, source.masks))}
        if not store_info['raw_bands_equal'] or not store_info['band_masks_equal']:
            raise ValueError('compact store failed full raw-value or mask fidelity')
    plots = []
    for plot in original_plots:
        result = evaluate(source, plot['geometry'])
        compact_result = evaluate(compact, plot['geometry']) if compact else None
        comparison = {'equal': result == compact_result if compact else None,
                      'status': 'computed' if compact else 'pending_codec',
                      'differing_fields': differing_fields(result, compact_result) if compact else [],
                      'source_result_sha256': object_hash(result),
                      'compact_result_sha256': object_hash(compact_result) if compact else None}
        receipt = receipt_for(source, plot, result, store_info, root=ROOT)
        plot.update(source_result=result, compact_result=compact_result, comparison=comparison,
                    receipt=receipt, evidence=evidence_cells(source, plot['geometry']))
        plots.append(plot)
    summary = summary_for(plots)
    artifact = {'schema_version': 'plotline.demo.v1', 'query_version': QUERY_VERSION,
                'dataset': source.metadata, 'periods': {key: {'start_year': 2000+v[0], 'end_year': 2000+v[1]} for key, v in PERIODS.items()},
                'plots': plots, 'summary': summary, 'benchmark': benchmark, 'limitations': LIMITATIONS,
                'benchmark_status': {'state': 'bound_retained' if benchmark else 'not_included'}}
    artifact['content_sha256'] = object_hash(artifact)
    output = Path(output) if output else ROOT / 'artifacts/demo-v1.json'
    atomic_json(output, artifact)
    example = {k: v for k, v in artifact.items() if k not in ('plots', 'content_sha256', 'summary', 'benchmark')}
    example['plot'] = next(p for p in plots if p['plot_id'] == 'P-0003')
    atomic_json(output.parent / 'example-v1.json', example)
    return artifact


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--store', type=Path, help='validated compact store directory')
    parser.add_argument('--output', type=Path)
    parser.add_argument('--without-benchmark', action='store_true', help='omit all benchmark claims explicitly')
    args = parser.parse_args()
    result = export(args.store, args.output, include_benchmark=not args.without_benchmark)
    print(json.dumps(result['summary'], indent=2))
