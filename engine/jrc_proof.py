"""Recompute JRC evidence from pinned inputs, not editable self-hash claims."""
import json
import hashlib
import math
from pathlib import Path
import re

import numpy as np
from .codecs import _pairs, _invalid_constant
from .jrc import (ROOT, SCHEMA, QUERY_VERSION, QUERY_GRID, LIMITATIONS, SOURCE,
                  load_jrc, evaluate_jrc, evidence_jrc, check_source_readback)
from .jrc_codec import decode_jrc_store, read_jrc_index, CANDIDATES, LEVELS
from .jrc_benchmark import (pinned_plots, identity, SETTINGS, run_jrc_benchmark,
                            store_record, answers, samples, environment, ORACLE_METHOD, ACCOUNTING_NOTE,
                            dataset_fingerprint, guard_digest)
from .jrc_oracle import oracle_jrc
from .source import canonical_bytes, object_hash


def same(a, b):
    return canonical_bytes(a) == canonical_bytes(b)


def require(ok, message):
    if not ok: raise ValueError(message)


def local(root, name):
    require(type(name) is str and not Path(name).is_absolute(), 'JRC path must be repository-relative')
    path = Path(root) / name
    require(path.resolve().is_relative_to(Path(root).resolve()), 'JRC path escapes repository')
    return path


def read_json(path, maximum=32*1024*1024):
    with Path(path).open('rb') as f: data = f.read(maximum+1)
    require(len(data) <= maximum, 'JRC JSON exceeds size limit')
    return json.loads(data, object_pairs_hook=_pairs, parse_constant=_invalid_constant)


def full_equal(source, compact):
    require(np.array_equal(source.values, compact.values), 'JRC full-chip raw values mismatch')
    require(np.array_equal(source.mask, compact.mask), 'JRC full-chip mask mismatch')
    require(same(source.metadata, compact.metadata), 'JRC full-chip metadata mismatch')


def info_for(path, root):
    record = store_record(path, root)
    index = read_jrc_index(path)
    return {**record, 'candidate': index['candidate'], 'chunk_size': index['chunk_size'],
            'compression_level': index['compression_level']}


def _verify_timings(timing, expected_sha256, expected_guard):
    require(type(timing) is dict and set(timing) == {'wall', 'cpu', 'validation'}, 'JRC timing fields mismatch')
    for key in ('wall', 'cpu'):
        s = timing[key]['samples']
        require(type(s) is list and len(s) == SETTINGS['repetitions']
                and all(type(v) in (int, float) and math.isfinite(v) and v >= 0 for v in s),
                'JRC invalid timing samples')
        require(same(timing[key], samples(s)), 'JRC timing statistics mismatch')
    record = {'result_sha256': expected_sha256, 'guard_before': expected_guard, 'guard_after': expected_guard}
    expected = {'expected_sha256': expected_sha256, 'expected_guard': expected_guard,
                'warmups': [record]*SETTINGS['warmups'], 'samples': [record]*SETTINGS['repetitions']}
    require(same(timing['validation'], expected), 'JRC intermediate timing result/guard mismatch')


def validate_benchmark(benchmark, source, plots, selected_path, root=ROOT):
    require(type(benchmark) is dict, 'JRC benchmark must be object')
    require(set(benchmark) == {'schema_version', 'identity', 'experiment_id', 'measured_at_utc', 'environment',
                              'source_window_readback', 'independent_oracle', 'baseline', 'candidates',
                              'smallest_encoded', 'overall_storage_choice', 'common_plot_inputs',
                              'accounting_note', 'cold_source', 'cold_smallest_encoded', 'measurement_guards', 'archive'},
            'JRC benchmark fields mismatch')
    expected_identity = identity(source, plots, root)
    require(same(benchmark['identity'], expected_identity), 'JRC benchmark input/code/query identity mismatch')
    exp = 'exp-'+object_hash(expected_identity)
    require(benchmark['experiment_id'] == exp, 'JRC benchmark experiment identity mismatch')
    run = benchmark['archive']['run_id']
    require(type(run) is str and re.fullmatch(r'run-[0-9a-f]{64}', run), 'JRC invalid run ID')
    relative = f'artifacts/jrc-stores/{exp}/{run}.json'
    require(benchmark['archive']['path'] == relative, 'JRC benchmark archive path mismatch')
    archive = read_json(local(root, relative))
    require('run-'+object_hash(archive) == run, 'JRC archived run content mismatch')
    require(same({k: v for k, v in benchmark.items() if k != 'archive'}, archive), 'JRC benchmark differs from measured archive')
    require(same(read_json(local(root, f'artifacts/jrc-stores/{exp}/identity.json')), expected_identity),
            'JRC archived identity mismatch')
    require(benchmark['schema_version'] == 'plotline.jrc-benchmark.v1', 'JRC benchmark schema mismatch')
    require(same(benchmark['environment'], environment()), 'JRC benchmark environment mismatch')
    require(benchmark['accounting_note'] == ACCOUNTING_NOTE, 'JRC accounting scope mismatch')
    expected_answers = answers(source, plots)
    digest = object_hash(expected_answers)
    dataset_sha = dataset_fingerprint(source)
    run_guard = guard_digest(expected_identity, dataset_sha)
    expected_readback_source = {k: source.metadata['source'][k] for k in ('path', 'sha256', 'bytes')}
    require(same(benchmark['measurement_guards'], {'start': run_guard, 'end': run_guard,
                 'dataset_sha256': dataset_sha, 'source_readback_sha256': object_hash(expected_readback_source)}),
            'JRC measurement start/end guards mismatch')
    files = source.metadata['required_inputs']
    baseline = benchmark['baseline']
    for key, value in {'candidate': 'native_geotiff', 'files': files,
                       'payload_bytes': files[0]['bytes'], 'metadata_index_bytes': sum(f['bytes'] for f in files[1:]),
                       'total_bytes': sum(f['bytes'] for f in files), 'answer_sha256': digest}.items():
        require(same(baseline[key], value), 'JRC baseline accounting/identity mismatch: '+key)
    _verify_timings(baseline['load'], dataset_sha, guard_digest(expected_identity))
    _verify_timings(baseline['hot_17_queries'], digest, run_guard)
    expected_configs = {(c, s) for c in CANDIDATES for s in SETTINGS['chunk_sizes']}
    require(len(benchmark['candidates']) == len(expected_configs), 'JRC benchmark candidate count mismatch')
    seen = set()
    for candidate in benchmark['candidates']:
        key = candidate['candidate'], candidate['chunk_size']
        require(key in expected_configs and key not in seen, 'JRC benchmark unexpected/duplicate candidate')
        seen.add(key)
        name, size = key
        path = local(root, f'artifacts/jrc-stores/{exp}/{name}-{size}')
        require(same(candidate['storage'], store_record(path, root)), 'JRC measured store files/bytes mismatch')
        decoded = decode_jrc_store(path)
        full_equal(source, decoded)
        index = read_jrc_index(path)
        require(same(index['candidate'], name) and same(index['chunk_size'], size) and same(candidate['compression_level'], LEVELS[name]),
                'JRC measured store settings mismatch')
        actual = answers(decoded, plots)
        require(same(actual, expected_answers) and candidate['answer_sha256'] == digest,
                'JRC measured answers mismatch')
        for field in ('full_raw_equal', 'full_masks_equal', 'full_metadata_equal', 'fully_exact'):
            require(candidate[field] is True, 'JRC candidate fidelity claim mismatch')
        require(same(candidate['full_pixel_count'], int(source.values.size)) and candidate['plot_mismatches'] == [],
                'JRC candidate pixel/plot claim mismatch')
        _verify_timings(candidate['encode'], dataset_sha, run_guard)
        _verify_timings(candidate['decode'], dataset_sha, guard_digest(expected_identity, storage=candidate['storage']))
        _verify_timings(candidate['hot_17_queries'], digest, guard_digest(expected_identity, dataset_sha, candidate['storage']))
    winner = min(benchmark['candidates'], key=lambda c: (c['storage']['total_bytes'], c['candidate'], c['chunk_size']))
    chosen = {'candidate': winner['candidate'], 'chunk_size': winner['chunk_size'],
              'store_path': winner['storage']['path'], 'total_bytes': winner['storage']['total_bytes']}
    require(same(chosen, benchmark['smallest_encoded']), 'JRC smallest encoded selection mismatch')
    require(Path(selected_path).resolve() == local(root, chosen['store_path']).resolve(), 'JRC selected store differs from measured winner')
    overall = 'native_geotiff' if baseline['total_bytes'] <= chosen['total_bytes'] else chosen['candidate']
    require(benchmark['overall_storage_choice'] == overall, 'JRC overall storage choice mismatch')
    require(same(benchmark['common_plot_inputs'], expected_identity['inputs'][4:]), 'JRC common plot accounting mismatch')
    independent = [oracle_jrc(source, p['geometry']) for p in plots]
    require(same(independent, expected_answers), 'JRC independent oracle mismatch')
    require(same(benchmark['independent_oracle'], {'equal': True, 'plot_count': len(plots), 'method': ORACLE_METHOD}),
            'JRC oracle claim mismatch')
    if (Path(root) / SOURCE).exists():
        require(same(benchmark['source_window_readback'], check_source_readback(root, source)), 'JRC source-window readback mismatch')
    else:
        recorded = benchmark['source_window_readback']
        expected_readback = {'source': {k: source.metadata['source'][k] for k in ('path', 'sha256', 'bytes')},
                             'pixel_count': int(source.values.size), 'raw_values_equal': True, 'masks_equal': True,
                             'window_row_col_height_width': source.metadata['source']['window_row_col_height_width'],
                             'transform_equal': True}
        require(same(recorded, expected_readback),
                'JRC archived source-window claim mismatch')
    for name in ('cold_source', 'cold_smallest_encoded'):
        cold = benchmark[name]
        expected_guard = guard_digest(expected_identity, storage=winner['storage'] if name == 'cold_smallest_encoded' else None)
        require(cold['expected_guard'] == expected_guard, 'JRC cold expected guard mismatch')
        require(len(cold['children']) == SETTINGS['repetitions'], 'JRC process-cold repetition mismatch')
        require(len(cold['warmup_children']) == SETTINGS['warmups'], 'JRC process-cold warmup mismatch')
        for child in cold['warmup_children'] + cold['children']:
            require(type(child) is dict and set(child) == {'wall_ms', 'cpu_ms', 'answer_sha256', 'dataset_sha256',
                                                          'guard_before', 'guard_after', 'rss_peak', 'rss_unit'},
                    'JRC child fields mismatch')
            require(child['answer_sha256'] == digest and type(child['rss_peak']) is int and child['rss_peak'] > 0
                    and child['dataset_sha256'] == dataset_sha
                    and child['guard_before'] == expected_guard and child['guard_after'] == expected_guard
                    and child['rss_unit'] in ('bytes', 'KiB')
                    and all(type(child[k]) in (int, float) and math.isfinite(child[k]) and child[k] >= 0
                            for k in ('wall_ms', 'cpu_ms')), 'JRC child answer/RSS mismatch')
        for stat, field in [('load_and_17_queries_wall', 'wall_ms'), ('load_and_17_queries_cpu', 'cpu_ms')]:
            require(same(cold[stat], samples([c[field] for c in cold['children']])), 'JRC cold timing summary mismatch')
        spawn_samples = cold['parent_spawn_inclusive_wall']['samples']
        require(len(spawn_samples) == SETTINGS['repetitions']
                and all(type(v) in (int, float) and math.isfinite(v) and v >= 0 for v in spawn_samples)
                and same(cold['parent_spawn_inclusive_wall'], samples(spawn_samples)),
                'JRC spawn timing summary mismatch')


def compose(source, compact, plots, store_info, benchmark, root=ROOT):
    full_equal(source, compact)
    full = {'pixel_count': int(source.values.size), 'raw_values_equal': True, 'mask_equal': True, 'metadata_equal': True,
            'raw_sha256': hashlib.sha256(source.values.tobytes()).hexdigest(),
            'mask_sha256': hashlib.sha256(source.mask.tobytes()).hexdigest()}
    rows = []
    for original in plots:
        geometry = original['geometry']
        result, encoded = evaluate_jrc(source, geometry), evaluate_jrc(compact, geometry)
        oracle = oracle_jrc(source, geometry)
        require(same(result, encoded), 'JRC compact plot mismatch')
        require(same(result, oracle), 'JRC independent plot mismatch')
        cells = evidence_jrc(source, geometry)
        evidence = {'index_origin': 'zero-based JRC chip row/col', 'cells': cells}
        receipt = {'query_version': QUERY_VERSION, 'query_grid': QUERY_GRID,
                   'boundary_rule': 'native centers covered by polygon; exterior and hole boundaries included',
                   'product': source.metadata['product'], 'version': 'v4', 'reference_year': 2020,
                   'geometry_sha256': object_hash(geometry), 'dataset_sha256': object_hash(source.metadata),
                   'source_result_sha256': object_hash(result), 'compact_result_sha256': object_hash(encoded),
                   'evidence_sha256': object_hash(evidence), 'full_chip': full, 'store': store_info,
                   'benchmark_run': benchmark['archive']['run_id'] if benchmark else None}
        receipt['receipt_sha256'] = object_hash(receipt)
        rows.append({'plot_id': original['plot_id'], 'geometry': geometry, 'geometry_sha256': object_hash(geometry),
                     'source_result': result, 'compact_result': encoded,
                     'comparison': {'equal': True, 'mismatch_fields': [], 'independent_oracle_equal': True},
                     'receipt': receipt, 'evidence': evidence})
    summary = {'plot_count': len(rows), 'exact_match_count': len(rows), 'independent_match_count': len(rows),
               'selected_cell_count_sum': sum(p['source_result']['selected_cell_count'] for p in rows),
               'class_counts_sum': {str(v): sum((p['source_result']['class_counts'] or {}).get(str(v), 0) for p in rows) for v in (0, 1)},
               'mapped_forest_plot_counts': {name: sum(p['source_result']['mapped_forest_present'] is val for p in rows)
                                             for name, val in [('true', True), ('false', False), ('unknown', None)]},
               'count_note': 'Sum over plots; overlapping geometries may count a native cell more than once.'}
    artifact = {'schema_version': SCHEMA, 'query_version': QUERY_VERSION, 'dataset': source.metadata,
                'native_grid': {k: source.metadata[k] for k in ('shape', 'transform', 'crs', 'query_grid')},
                'store': store_info, 'full_chip': full, 'plots': rows, 'summary': summary,
                'benchmark': benchmark, 'limitations': LIMITATIONS}
    artifact['content_sha256'] = object_hash(artifact)
    return artifact


def export_jrc(output=None, store=None, benchmark=None, root=ROOT, new_measurement=False):
    root = Path(root)
    if type(new_measurement) is not bool: raise ValueError('new_measurement must be bool')
    if new_measurement:
        require(store is None and benchmark is None, 'new measurement cannot also select an existing store/benchmark')
        benchmark = run_jrc_benchmark(root)
    elif store is None and benchmark is None:
        retained_path = root / 'artifacts/jrc-baseline-v1.json'
        if not retained_path.is_file():
            raise ValueError('No retained JRC measurement; run engine.jrc --measure explicitly with the full source cache')
        retained_check = verify_jrc_artifact(retained_path, root)
        require(retained_check['valid'], 'Retained JRC companion is invalid/stale; explicit --measure may be required: '+str(retained_check['failures']))
        retained = read_json(retained_path)
        require(retained['benchmark'] is not None, 'Ordinary JRC export requires a retained measured companion')
        benchmark = retained['benchmark']
    source, plots = load_jrc(root), pinned_plots(root)
    if store is None:
        store = local(root, benchmark['smallest_encoded']['store_path'])
    path = Path(store)
    if not path.is_absolute(): path = root / path
    require(path.resolve().is_relative_to(root.resolve()), 'JRC store outside repository')
    compact = decode_jrc_store(path)
    full_equal(source, compact)
    if benchmark is not None: validate_benchmark(benchmark, source, plots, path, root)
    artifact = compose(source, compact, plots, info_for(path, root), benchmark, root)
    if output is not None:
        output = Path(output)
        output.parent.mkdir(parents=True, exist_ok=True)
        temp = output.with_suffix('.tmp')
        with temp.open('wb') as f: f.write(canonical_bytes(artifact))
        temp.replace(output)
    return artifact


def verify_jrc_artifact(path, root=ROOT):
    try:
        root = Path(root)
        supplied = read_json(path)
        source, plots = load_jrc(root), pinned_plots(root)
        require(type(supplied) is dict, 'JRC artifact must be object')
        store = local(root, supplied['store']['path'])
        compact = decode_jrc_store(store)
        # This precedes archive/path bindings so off-plot corruption cannot hide
        # behind a stale benchmark rejection. Rehashed false raw/mask claims fail.
        full_equal(source, compact)
        benchmark = supplied['benchmark']
        if benchmark is not None: validate_benchmark(benchmark, source, plots, store, root)
        expected = compose(source, compact, plots, info_for(store, root), benchmark, root)
        for key in expected:
            if key == 'plots':
                require(type(supplied.get(key)) is list and len(supplied[key]) == len(expected[key]), 'JRC artifact plot cohort mismatch')
                for actual, original in zip(supplied[key], expected[key]):
                    for field in original:
                        require(same(actual.get(field), original[field]), 'JRC artifact plot '+original['plot_id']+' '+field+' mismatch')
                    require(set(actual) == set(original), 'JRC unexpected plot fields')
            else:
                require(same(supplied.get(key), expected[key]), 'JRC artifact '+key+' mismatch')
        require(set(supplied) == set(expected), 'JRC unexpected artifact fields')
        return {'valid': True, 'failures': [], 'plot_count': len(plots), 'full_pixel_count': int(source.values.size),
                'source_and_compact_raw_masks_equal': True, 'independent_plot_checks': len(plots),
                'benchmark_bound': benchmark is not None,
                'full_source_cache_present': (root / SOURCE).is_file(),
                'note': 'Local pinned-input recomputation; hashes are integrity identities, not signatures or source-accuracy claims.'}
    except (ValueError, KeyError, TypeError, OSError, OverflowError, RecursionError, AttributeError) as exc:
        return {'valid': False, 'failures': [str(exc)]}
