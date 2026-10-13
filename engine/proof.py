"""Bind exported evidence to actual inputs and an explicitly retained measured run.

Hashes provide integrity/reproducibility, not signatures or source truth. A
benchmark is accepted only when its archived measurement, files, current code,
current query cohort and deliberate retained choice agree.
"""
import json
from pathlib import Path
import re
from .model import PERIODS, QUERY_VERSION
from .source import ROOT, SAMPLE, CSV_NAME, GEOJSON_NAME, canonical_bytes, object_hash, sha256_file

BOUNDARY_RULE = 'native cell centers covered by polygon, including polygon and hole boundaries'
VALID_LAND_RULE = 'datamask == 1 and every required band validity mask is true'
PARTIAL_RULE = 'retain observed valid-land counts; witnessed loss true; absent loss unknown'
COUNT_NOTE = 'sum over plots; overlapping geometries could count the same native cell twice'


def same(left, right):
    return canonical_bytes(left) == canonical_bytes(right)


def supplier_sources(root=ROOT):
    return [{'path': str(SAMPLE / filename), 'sha256': sha256_file(root / SAMPLE / filename),
             'bytes': (root / SAMPLE / filename).stat().st_size} for filename in (CSV_NAME, GEOJSON_NAME)]


def receipt_for(dataset, original, result, store_info, root=ROOT):
    receipt = {'query_version': QUERY_VERSION, 'geometry_sha256': object_hash(original['geometry']),
               'supplier_row_sha256': object_hash(original['supplier']),
               'source_metadata_sha256': object_hash(dataset.metadata), 'supplier_sources': supplier_sources(root),
               'sources': dataset.metadata['sources'], 'grid': {k: dataset.metadata[k] for k in ('shape', 'crs', 'transform')},
               'boundary_rule': BOUNDARY_RULE, 'valid_land_rule': VALID_LAND_RULE,
               'partial_support_rule': PARTIAL_RULE,
               'observed_periods': {k: [2000+v[0], 2000+v[1]] for k, v in PERIODS.items()},
               'product': dataset.metadata['product'], 'unknown_reasons': result['unknown_reasons'],
               'compact_store': store_info}
    receipt['receipt_sha256'] = object_hash(receipt)
    return receipt


def summary_for(plots):
    computed = bool(plots) and all(p['compact_result'] is not None for p in plots)
    return {'plot_count': len(plots), 'selected_cell_count_sum': sum(p['source_result']['selected_cell_count'] for p in plots),
            'selected_cell_count_note': COUNT_NOTE, 'comparison_status': 'computed' if computed else 'pending_codec',
            'exact_match_count': sum(p['comparison']['equal'] is True for p in plots) if computed else None,
            'mapped_loss_plot_counts': {key: {state: sum(p['source_result']['periods'][key]['mapped_loss_present'] is val for p in plots)
                                            for state, val in [('true', True), ('false', False), ('unknown', None)]} for key in PERIODS},
            'supplier_indication_count': sum(p['supplier']['c2_deforestation_spatial_analysis_result'] == 'b. Indication of deforestation' for p in plots)}


def _local(root, relative):
    if type(relative) is not str or Path(relative).is_absolute():
        raise ValueError('benchmark path must be repository-relative')
    path = root / relative
    if not path.resolve().is_relative_to(root.resolve()):
        raise ValueError('benchmark path escapes repository')
    return path


def validate_benchmark(benchmark, dataset, plots, store=None, root=ROOT):
    """Raise ValueError on unbound/stale/altered benchmark; return retained store."""
    root = Path(root)
    try:
        def require(condition, message):
            if not condition:
                raise ValueError('unbound benchmark: ' + message)
        require(benchmark['schema_version'] == 'plotline.benchmark.v1', 'schema')
        identity = benchmark['identity']
        require(identity['query_version'] == QUERY_VERSION, 'query version')
        require(same(identity['source_metadata'], dataset.metadata), 'source metadata')
        require(identity['queries_sha256'] == object_hash([{'plot_id': p['plot_id'], 'geometry': p['geometry']} for p in plots]), 'query cohort')
        code = identity['implementation_sha256']
        require(set(code) == {'model.py', 'source.py', 'query.py', 'codecs.py', 'benchmark.py', 'experiments.py'}, 'implementation set')
        for name, digest in code.items():
            require(sha256_file(root / 'engine' / name) == digest, 'stale implementation: ' + name)
        inputs = identity['input_sha256']
        required_inputs = {s['path'] for s in dataset.metadata['sources']} | {'data/public/provenance.json', str(SAMPLE / CSV_NAME), str(SAMPLE / GEOJSON_NAME)}
        require(set(inputs) == required_inputs, 'input set')
        for name, digest in inputs.items():
            require(sha256_file(_local(root, name)) == digest, 'changed input: ' + name)
        exp_id = benchmark['experiment_id']
        registry = benchmark['registry']
        run_id = registry['run_id']
        require(bool(re.fullmatch(r'exp-[0-9a-f]{64}', exp_id)), 'experiment ID')
        require(bool(re.fullmatch(r'run-[0-9a-f]{64}', run_id)), 'run ID')
        require(exp_id == 'exp-' + object_hash(identity), 'experiment identity hash')
        require(registry['experiment_id'] == exp_id, 'registry experiment')
        require(registry['result_path'] == f'{exp_id}/{run_id}.json', 'registry path')
        folder = root / 'artifacts/experiments'
        archive = json.loads((folder / exp_id / (run_id+'.json')).read_text())
        require(run_id == 'run-' + object_hash(archive), 'archived run hash')
        payload = {k: v for k, v in benchmark.items() if k not in ('registry', 'publication', 'retained_selection')}
        require(same(payload, archive), 'measured archive differs')
        require(same(json.loads((folder / exp_id / 'identity.json').read_text()), identity), 'archived identity differs')
        selection = benchmark['retained_selection']
        require(same(selection, json.loads((folder / 'retained-choice.json').read_text())), 'retained choice differs')
        require(same(selection, json.loads((folder / 'selections' / ('choice-'+object_hash(selection)+'.json')).read_text())), 'selection archive differs')
        require(selection['experiment_id'] == exp_id and selection['run_id'] == run_id, 'retained run binding')
        require(selection['result_path'] == registry['result_path'] and bool(selection['reason'].strip()), 'retained reason/path')
        def check_storage(storage, base):
            files = storage['files']
            require(len({f['path'] for f in files}) == len(files), 'duplicate measured files')
            total = 0
            for entry in files:
                path = _local(base, entry['path'])
                require(path.is_file() and path.stat().st_size == entry['bytes'] and sha256_file(path) == entry['sha256'], 'measured file: '+entry['path'])
                total += entry['bytes']
            require(type(storage['total_bytes']) is int and total == storage['total_bytes'], 'total storage accounting')
            require(storage['payload_bytes'] + storage['metadata_index_bytes'] == total, 'payload/index accounting')
        check_storage(benchmark['baseline']['storage'], root)
        eligible = []
        for candidate in benchmark['candidates']:
            if candidate.get('status') == 'measured':
                name = candidate['candidate']
                require(bool(re.fullmatch('[a-z0-9_]+', name)), 'candidate name')
                base = root / 'artifacts/stores' / exp_id / name
                check_storage(candidate['storage'], base)
                require({p.name for p in base.iterdir()} == {f['path'] for f in candidate['storage']['files']}, 'unaccounted store files')
            if candidate.get('fully_exact') is True:
                eligible.append(candidate)
        require(bool(eligible), 'no exact candidate')
        winner = min(eligible, key=lambda c: (c['storage']['total_bytes'], c['candidate']))
        require(benchmark['winner']['candidate'] == winner['candidate'], 'winner candidate')
        require(benchmark['winner']['total_bytes'] == winner['storage']['total_bytes'], 'winner size')
        chosen = selection['smallest_encoded']
        require(chosen['candidate'] == winner['candidate'] and chosen['total_bytes'] == winner['storage']['total_bytes'], 'retained encoded choice')
        require(chosen['chunk_size'] == identity['settings']['chunk_size'], 'retained chunk size')
        expected_path = f'artifacts/stores/{exp_id}/{winner["candidate"]}'
        require(chosen['store_path'] == expected_path, 'retained store path')
        require(selection['source_total_bytes'] == benchmark['baseline']['storage']['total_bytes'], 'retained baseline')
        overall = 'source_geotiff' if benchmark['baseline']['storage']['total_bytes'] <= winner['storage']['total_bytes'] else winner['candidate']
        require(selection['overall_storage_choice'] == benchmark['overall_storage_choice'] == overall, 'overall storage choice')
        selected_path = _local(root, expected_path)
        if store is not None:
            supplied = Path(store) if Path(store).is_absolute() else root / store
            require(supplied.resolve() == selected_path.resolve(), 'demo store differs from retained benchmark store')
        return selected_path
    except (KeyError, TypeError, OSError, OverflowError) as exc:
        raise ValueError(f'unbound benchmark: malformed or missing evidence ({exc})') from exc
