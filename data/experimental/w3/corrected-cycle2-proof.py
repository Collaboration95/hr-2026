"""Read-only proof positive/negative checks; write only W3 scratch evidence."""
from copy import deepcopy
import json
from pathlib import Path
import sys
ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
from engine.benchmark import implementation_hashes, input_hashes, sha256_file
from engine.experiments import atomic_write_json, content_hash
from engine.proof import validate_benchmark
from engine.source import load_source, load_plots

benchmark = json.loads((ROOT / 'artifacts/benchmark-v1.json').read_text())
source, plots = load_source(), load_plots()
selection = benchmark['retained_selection']
store = ROOT / selection['smallest_encoded']['store_path']
assert validate_benchmark(benchmark, source, plots, store=store) == store
registry = benchmark['registry']
archive_path = ROOT / 'artifacts/experiments' / registry['result_path']
archive = json.loads(archive_path.read_text())
payload = {k: v for k, v in benchmark.items() if k not in ('registry', 'publication', 'retained_selection')}
assert payload == archive
assert registry['run_id'] == 'run-' + content_hash(archive)
assert benchmark['identity']['implementation_sha256'] == implementation_hashes()
assert benchmark['identity']['input_sha256'] == input_hashes(ROOT)
required = benchmark['baseline']['storage']
assert required['total_bytes'] == 585293
assert len(required['files']) == 4
assert benchmark['baseline']['research_overhead']['total_bytes'] == 948

negatives = []
mutated = deepcopy(benchmark)
mutated['winner']['ratio_to_source_total'] = 0
negatives.append(('altered_archive', mutated, store))
stale = deepcopy(benchmark)
stale['identity']['implementation_sha256']['query.py'] = '0' * 64
negatives.append(('stale_code', stale, store))
wrong_store = store.parent / 'separate_zstd_l9'
assert wrong_store.is_dir()
negatives.append(('valid_but_unbound_other_codec_store', benchmark, wrong_store))
old_paths = list((ROOT / 'data/experimental/w3').glob('retained-before-required-baseline-correction-*.json'))
assert old_paths
old = json.loads(old_paths[-1].read_text())
negatives.append(('superseded_retained_baseline', old, ROOT / old['retained_selection']['smallest_encoded']['store_path']))
rejections = {}
for name, artifact, path in negatives:
    try:
        validate_benchmark(artifact, source, plots, store=path)
    except ValueError as exc:
        rejections[name] = str(exc)
    else:
        raise AssertionError('false benchmark accepted: ' + name)

result = {'valid_retained_binding': True, 'experiment_id': benchmark['experiment_id'],
          'run_id': registry['run_id'], 'archive_path': registry['result_path'],
          'archive_file_sha256': sha256_file(archive_path), 'archive_equality': True,
          'implementation_sha256': implementation_hashes(), 'input_sha256': input_hashes(ROOT),
          'required_source_bytes': required['total_bytes'], 'research_only_bytes': 948,
          'store_path': selection['smallest_encoded']['store_path'],
          'store_files': next(c['storage']['files'] for c in benchmark['candidates']
                              if c['candidate'] == selection['smallest_encoded']['candidate']),
          'negative_test_rejections': rejections}
atomic_write_json(ROOT / 'data/experimental/w3/corrected-cycle2-proof.json', result)
print(json.dumps(result, indent=2))
