"""Reopen sources/stores and verify every exported proof claim before integration."""
import argparse
import json
from pathlib import Path
import numpy as np
from .export import LIMITATIONS, differing_fields, evidence_cells
from .model import Dataset, PERIODS, QUERY_VERSION
from .proof import receipt_for, same, summary_for, validate_benchmark
from .query import evaluate
from .source import ROOT, load_plots, load_source, object_hash, sha256_file


def verify_artifact(path):
    artifact = json.loads(Path(path).read_text())
    failures = []
    def check(condition, message):
        if not condition:
            failures.append(message)
    check(artifact.get('schema_version') == 'plotline.demo.v1', 'schema_version')
    check(artifact.get('query_version') == QUERY_VERSION, 'query_version')
    unsigned = {k: v for k, v in artifact.items() if k != 'content_sha256'}
    check(artifact.get('content_sha256') == object_hash(unsigned), 'content_sha256')
    source, actual = load_source(), load_plots()
    check(same(artifact.get('dataset'), source.metadata), 'dataset metadata')
    check(same(artifact.get('periods'), {k: {'start_year': 2000+v[0], 'end_year': 2000+v[1]} for k, v in PERIODS.items()}), 'period envelope')
    check(same(artifact.get('limitations'), LIMITATIONS), 'limitations')
    plots = artifact.get('plots', [])
    check([p['plot_id'] for p in plots] == [p['plot_id'] for p in actual], 'exact plot IDs/order')
    compact_cache, files_cache = {}, {}
    recomputed_plots, store_paths = [], set()
    for plot, original in zip(plots, actual):
        name = plot['plot_id']
        for key in ('geometry', 'supplier', 'geometry_properties'):
            check(same(plot.get(key), original.get(key)), f'{name}: exact {key}')
        expected = evaluate(source, original['geometry'])
        check(not differing_fields(expected, plot.get('source_result')), f'{name}: source result')
        check(same(plot.get('evidence'), evidence_cells(source, original['geometry'])), f'{name}: native evidence')
        receipt, comparison = plot['receipt'], plot['comparison']
        supplied_store = receipt.get('compact_store')
        store_info = None
        compact_result = None
        if supplied_store is not None:
            store_path = Path(supplied_store['path'])
            if not store_path.is_absolute():
                store_path = ROOT / store_path
            key = str(store_path.resolve())
            store_paths.add(key)
            if key not in compact_cache:
                from .codecs import decode_store
                decoded = Dataset(*decode_store(store_path)).validate()
                compact_cache[key] = decoded
                check(same(decoded.metadata, source.metadata), f'{name}: store metadata')
                # Full-grid fidelity is separate from selected-plot fidelity.
                check(np.array_equal(decoded.bands, source.bands), f'{name}: full raw-value fidelity')
                check(np.array_equal(decoded.masks, source.masks), f'{name}: full band-mask fidelity')
                files_cache[key] = [{'path': str(p.relative_to(store_path)), 'bytes': p.stat().st_size, 'sha256': sha256_file(p)}
                                    for p in sorted(store_path.rglob('*')) if p.is_file()]
            decoded = compact_cache[key]
            store_info = {'path': supplied_store['path'], 'files': files_cache[key],
                          'raw_bands_equal': bool(np.array_equal(decoded.bands, source.bands)),
                          'band_masks_equal': bool(np.array_equal(decoded.masks, source.masks))}
            check(same(supplied_store, store_info), f'{name}: store files/full-fidelity claims')
            compact_result = evaluate(decoded, original['geometry'])
        check(not differing_fields(compact_result, plot.get('compact_result')), f'{name}: compact result')
        diff = differing_fields(expected, compact_result) if compact_result is not None else []
        expected_comparison = {'equal': not diff if compact_result is not None else None,
                               'status': 'computed' if compact_result is not None else 'pending_codec',
                               'differing_fields': diff, 'source_result_sha256': object_hash(expected),
                               'compact_result_sha256': object_hash(compact_result) if compact_result is not None else None}
        check(same(comparison, expected_comparison), f'{name}: comparison claims')
        check(same(receipt, receipt_for(source, original, expected, store_info)), f'{name}: receipt contract/source/hash claims')
        recomputed_plots.append(dict(original, source_result=expected, compact_result=compact_result, comparison=expected_comparison))
    check(same(artifact.get('summary'), summary_for(recomputed_plots)), 'derived summary')
    check(len(store_paths) <= 1, 'one artifact must bind one compact store')
    benchmark = artifact.get('benchmark')
    check(same(artifact.get('benchmark_status'), {'state': 'bound_retained' if benchmark else 'not_included'}), 'benchmark status')
    if benchmark is not None:
        try:
            check(len(store_paths) == 1, 'benchmark requires computed compact store')
            validate_benchmark(benchmark, source, actual, store=next(iter(store_paths), None))
        except ValueError as exc:
            failures.append(str(exc))
    return {'valid': not failures, 'plot_count': len(actual),
            'compact_plot_count': sum(p['compact_result'] is not None for p in recomputed_plots),
            'checks': 'exact inputs/contract/summary, all raw values/masks, query outputs, native cells, receipts, retained benchmark archive/current files/code',
            'failures': failures}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('path', nargs='?', type=Path, default=ROOT / 'artifacts/demo-v1.json')
    args = parser.parse_args()
    try:
        result = verify_artifact(args.path)
    except (OSError, ValueError, KeyError, TypeError) as exc:
        result = {'valid': False, 'failures': [f'{type(exc).__name__}: {exc}']}
    print(json.dumps(result, indent=2))
    return 0 if result['valid'] else 1

if __name__ == '__main__':
    raise SystemExit(main())
