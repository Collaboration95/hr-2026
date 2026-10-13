"""Evidence preservation, fair timing summaries and real child-process checks."""
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from engine.benchmark import (child_measure, differing_fields, measure_queries,
                              summarize, audit_store, sha256_file, BenchmarkRaceError,
                              assert_fingerprints, verify_files, run_benchmark,
                              implementation_hashes, input_hashes)
from engine.experiments import (atomic_write_json, content_hash, experiment_id,
                                record_experiment, publish_benchmark, freeze_selection)

ROOT = Path(__file__).resolve().parents[2]
SCRATCH = ROOT / 'data/experimental/w3'


class RegistryTests(unittest.TestCase):
    def setUp(self):
        SCRATCH.mkdir(parents=True, exist_ok=True)
        self.temporary = tempfile.TemporaryDirectory(dir=SCRATCH, prefix='test-')
        self.directory = Path(self.temporary.name)
        self.identity = {'source_sha256': 'abc', 'query_version': 'v1',
                         'settings': {'chunk_size': 128}}

    def tearDown(self):
        self.temporary.cleanup()

    def test_identity_order_and_changed_inputs(self):
        reversed_keys = dict(reversed(list(self.identity.items())))
        self.assertEqual(experiment_id(self.identity), experiment_id(reversed_keys))
        for field, value in [('source_sha256', 'changed'), ('query_version', 'v2'),
                             ('settings', {'chunk_size': 64})]:
            self.assertNotEqual(experiment_id(self.identity),
                                experiment_id(dict(self.identity, **{field: value})))

    def test_reruns_preserve_old_evidence_and_duplicate_retry(self):
        first = record_experiment(self.identity, {'median_ms': 1.0}, self.directory)
        old_path = self.directory / first['result_path']
        old_bytes = old_path.read_bytes()
        second = record_experiment(self.identity, {'median_ms': 2.0}, self.directory)
        retry = record_experiment(self.identity, {'median_ms': 2.0}, self.directory)
        self.assertEqual(first['experiment_id'], second['experiment_id'])
        self.assertNotEqual(first['run_id'], second['run_id'])
        self.assertTrue(second['is_repeat'])
        self.assertTrue(retry['duplicate_result'])
        self.assertEqual(retry['run_count'], 2)
        self.assertEqual(old_path.read_bytes(), old_bytes)
        self.assertEqual(json.loads(old_path.read_text()), {'median_ms': 1.0})

    def test_interrupted_index_update_repaired(self):
        first = record_experiment(self.identity, {'median_ms': 1}, self.directory)
        (self.directory / 'index.json').unlink()
        retry = record_experiment(self.identity, {'median_ms': 1}, self.directory)
        self.assertTrue(retry['duplicate_result'])
        index = json.loads((self.directory / 'index.json').read_text())
        self.assertEqual(index['experiments'][first['experiment_id']]['runs'], [first['run_id']])

    def test_atomic_write_failure_preserves_previous_json(self):
        path = self.directory / 'value.json'
        atomic_write_json(path, {'value': 'old'})
        with patch('engine.experiments.os.replace', side_effect=OSError('simulated replace failure')):
            with self.assertRaises(OSError):
                atomic_write_json(path, {'value': 'new'})
        self.assertEqual(json.loads(path.read_text()), {'value': 'old'})
        self.assertEqual(list(self.directory.iterdir()), [path])

    def test_nonfinite_results_rejected_before_write(self):
        with self.assertRaises(ValueError):
            record_experiment(self.identity, {'median_ms': float('nan')}, self.directory)
        self.assertEqual(list(self.directory.iterdir()), [])

    def test_concurrent_writers_keep_all_runs(self):
        script = ('import json,sys; from engine.experiments import record_experiment; '
                  'record_experiment(json.loads(sys.argv[1]), {"sample":int(sys.argv[2])}, sys.argv[3])')
        env = dict(os.environ, PYTHONDONTWRITEBYTECODE='1')
        children = [subprocess.Popen([sys.executable, '-B', '-c', script,
                    json.dumps(self.identity), str(i), str(self.directory)], cwd=ROOT, env=env,
                    stdout=subprocess.PIPE, stderr=subprocess.PIPE) for i in range(4)]
        for child in children:
            stdout, stderr = child.communicate(timeout=30)
            self.assertEqual(child.returncode, 0, stderr.decode())
        index = json.loads((self.directory / 'index.json').read_text())
        entry = index['experiments'][experiment_id(self.identity)]
        self.assertEqual(len(entry['runs']), 4)
        results = [json.loads((self.directory / experiment_id(self.identity) / (run + '.json')).read_text())
                   for run in entry['runs']]
        self.assertEqual({r['sample'] for r in results}, set(range(4)))

    def measured_fixture(self, size=90):
        result = {'identity': self.identity, 'winner': {'candidate': 'codec'},
                  'baseline': {'storage': {'total_bytes': 100},
                               'queries': {'timed_answers_exact': True}},
                  'candidates': [{'candidate': 'codec', 'fully_exact': True,
                                  'storage': {'total_bytes': size}}],
                  'overall_storage_choice': 'codec' if size < 100 else 'source_geotiff'}
        result['registry'] = record_experiment(self.identity, result, self.directory)
        return result

    def test_explicit_retention_blocks_last_experiment_publication(self):
        result = self.measured_fixture()
        canonical = self.directory / 'canonical.json'
        selection = freeze_selection(result, 'measured minimum total bytes, fully exact', self.directory, canonical)
        old = canonical.read_bytes()
        later = self.measured_fixture(size=110)
        self.assertFalse(publish_benchmark(later, self.directory, canonical))
        self.assertEqual(canonical.read_bytes(), old)
        self.assertEqual(selection['overall_storage_choice'], 'codec')
        self.assertEqual(selection['smallest_encoded']['total_bytes'], 90)
        self.assertEqual(json.loads((self.directory / 'retained-choice.json').read_text()), selection)

    def test_retention_requires_registered_unchanged_evidence_and_reason(self):
        result = self.measured_fixture()
        canonical = self.directory / 'canonical.json'
        with self.assertRaises(ValueError):
            freeze_selection(result, ' ', self.directory, canonical)
        result['candidates'][0]['storage']['total_bytes'] = 1
        with self.assertRaises(ValueError):
            freeze_selection(result, 'mutated evidence', self.directory, canonical)
        self.assertFalse(canonical.exists())


class BenchmarkAccountingTests(unittest.TestCase):
    def test_summary_keeps_samples_and_nearest_rank_percentile(self):
        summary = summarize([7., 2., 5., 1., 3., 6., 4.])
        self.assertEqual((summary['min'], summary['median'], summary['p95']), (1, 4, 7))
        self.assertEqual(summary['repetitions'], 7)
        for invalid in ([], [-1], [float('inf')], [float('nan')]):
            with self.assertRaises(ValueError):
                summarize(invalid)

    def test_mismatch_paths_expose_nested_counts_types_and_absent_keys(self):
        self.assertEqual(differing_fields({'periods': {'p': [False, 1]}, 'old': None},
                                         {'periods': {'p': [None, 2]}, 'new': None}),
                         ['new', 'old', 'periods.p[0]', 'periods.p[1]'])
        self.assertEqual(differing_fields({'n': 1}, {'n': True}), ['n'])

    def test_unreported_files_cannot_disappear_from_denominator(self):
        SCRATCH.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(dir=SCRATCH, prefix='account-') as tmp:
            folder = Path(tmp)
            (folder / 'payload').write_bytes(b'abc')
            (folder / 'metadata').write_bytes(b'{}')
            report = {'total_bytes': 5, 'payload_bytes': 3, 'metadata_index_bytes': 2}
            self.assertEqual(audit_store(folder, report)['total_bytes'], 5)
            (folder / 'forgotten-index').write_bytes(b'xyz')
            with self.assertRaises(ValueError):
                audit_store(folder, report)

    def test_hot_and_cold_counts_and_digests_are_checked(self):
        requests = []
        def measurement(request):
            requests.append(request)
            if request['operation'] == 'hot':
                return {'answer_sha256': ['correct']}
            return {'wall_ms': 4., 'cpu_ms': 3., 'load_ms': 2., 'query_ms': 2.,
                    'subprocess_wall_ms': 10., 'peak_rss': {'bytes': 10},
                    'answer_sha256': 'incorrect' if len(requests) == 3 else 'correct'}
        with patch('engine.benchmark.child_measure', side_effect=measurement):
            with self.assertRaisesRegex(BenchmarkRaceError, 'process-cold answers differ'):
                measure_queries('source_geotiff', None, ROOT, 3, 2, 'correct')
        self.assertEqual([r['operation'] for r in requests], ['hot', 'cold', 'cold', 'cold'])

    def test_timed_hot_race_fails_before_cold_children(self):
        with patch('engine.benchmark.child_measure', return_value={'answer_sha256': ['wrong']}) as child:
            with self.assertRaisesRegex(BenchmarkRaceError, 'timed hot answers differ'):
                measure_queries('source_geotiff', None, ROOT, 3, 2, 'correct')
        self.assertEqual(child.call_count, 1)

    def test_fingerprint_and_measured_file_changes_fail_visibly(self):
        guard = {'implementation': {'code': 'expected'}, 'inputs': {'source': 'expected'}}
        with patch('engine.benchmark.implementation_hashes', return_value={'code': 'changed'}):
            with self.assertRaisesRegex(BenchmarkRaceError, 'implementation fingerprint'):
                assert_fingerprints(ROOT, guard)
        with patch('engine.benchmark.implementation_hashes', return_value=guard['implementation']), \
             patch('engine.benchmark.input_hashes', return_value={'source': 'changed'}):
            with self.assertRaisesRegex(BenchmarkRaceError, 'source/provenance/geometry'):
                assert_fingerprints(ROOT, guard)
        SCRATCH.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(dir=SCRATCH, prefix='race-') as tmp:
            path = Path(tmp) / 'measured'
            path.write_bytes(b'old')
            entries = [{'path': path.name, 'bytes': 3, 'sha256': sha256_file(path)}]
            path.write_bytes(b'new')
            with self.assertRaises(BenchmarkRaceError):
                verify_files(tmp, entries)

    def test_aborted_race_preserves_failure_evidence_and_reraises(self):
        SCRATCH.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(dir=SCRATCH, prefix='abort-') as tmp:
            with patch('engine.benchmark._run_benchmark', side_effect=BenchmarkRaceError('test race')):
                with self.assertRaisesRegex(BenchmarkRaceError, 'test race'):
                    run_benchmark(root=tmp)
            failures = list((Path(tmp) / 'artifacts/experiments/failures').glob('*.json'))
            self.assertEqual(len(failures), 1)
            self.assertEqual(json.loads(failures[0].read_text())['status'], 'aborted')
            self.assertFalse((Path(tmp) / 'artifacts/benchmark-v1.json').exists())


class ActualSourceChildTests(unittest.TestCase):
    @unittest.skipUnless((ROOT / 'artifacts/benchmark-v1.json').exists(), 'run benchmark CLI for artifact check')
    def test_retained_benchmark_passes_lead_proof_guard_and_rejects_unbound_changes(self):
        from copy import deepcopy
        from engine.proof import validate_benchmark
        from engine.source import load_source, load_plots
        benchmark = json.loads((ROOT / 'artifacts/benchmark-v1.json').read_text())
        if 'retained_selection' not in benchmark:
            self.skipTest('explicit retention required for proof binding check')
        source, plots = load_source(), load_plots()
        selected = ROOT / benchmark['retained_selection']['smallest_encoded']['store_path']
        self.assertEqual(validate_benchmark(benchmark, source, plots, store=selected), selected)
        mutated = deepcopy(benchmark)
        mutated['winner']['ratio_to_source_total'] = 0
        with self.assertRaisesRegex(ValueError, 'measured archive differs'):
            validate_benchmark(mutated, source, plots, store=selected)
        stale = deepcopy(benchmark)
        stale['identity']['implementation_sha256']['query.py'] = '0' * 64
        with self.assertRaisesRegex(ValueError, 'stale implementation: query.py'):
            validate_benchmark(stale, source, plots, store=selected)
        with self.assertRaisesRegex(ValueError, 'demo store differs from retained'):
            validate_benchmark(benchmark, source, plots, store=ROOT / 'artifacts/stores/wrong-store')

    def test_child_rejects_wrong_provenance_fingerprint_with_nonzero_exit(self):
        guard = {'implementation': implementation_hashes(), 'inputs': input_hashes(ROOT)}
        guard['inputs']['data/public/provenance.json'] = '0' * 64
        request = {'root': str(ROOT), 'representation': 'source_geotiff',
                   'operation': 'cold', 'guard': guard, 'repetitions': 1, 'warmups': 0}
        with self.assertRaisesRegex(BenchmarkRaceError, 'source/provenance/geometry fingerprint'):
            child_measure(request)

    def test_real_17_plot_child_answers_and_native_rss_units(self):
        from engine.source import load_source, load_plots
        from engine.query import evaluate
        expected = content_hash([evaluate(load_source(), p['geometry']) for p in load_plots()])
        request = {'root': str(ROOT), 'representation': 'source_geotiff',
                   'repetitions': 2, 'warmups': 1}
        hot = child_measure(dict(request, operation='hot'))
        cold = child_measure(dict(request, operation='cold'))
        self.assertEqual(hot['answer_sha256'], [expected])
        self.assertEqual(cold['answer_sha256'], expected)
        self.assertEqual(hot['wall_ms']['repetitions'], 2)
        self.assertAlmostEqual(cold['wall_ms'], cold['load_ms'] + cold['query_ms'])
        self.assertGreater(cold['subprocess_wall_ms'], cold['wall_ms'])
        native = cold['peak_rss']
        self.assertEqual(native['native_unit'], 'bytes' if sys.platform == 'darwin' else 'KiB')
        self.assertGreater(native['bytes'], 0)

    @unittest.skipUnless((ROOT / 'artifacts/benchmark-v1.json').exists(), 'run benchmark CLI for artifact check')
    def test_generated_real_benchmark_counts_required_provenance_and_full_cohort(self):
        benchmark = json.loads((ROOT / 'artifacts/benchmark-v1.json').read_text())
        source_inputs = benchmark['identity']['source_loader_inputs']
        self.assertEqual([f['path'] for f in source_inputs], ['data/public/provenance.json'])
        storage = benchmark['baseline']['storage']
        self.assertEqual(storage['total_bytes'], sum(f['bytes'] for f in storage['files']))
        self.assertEqual(storage['payload_bytes'] + storage['metadata_bytes'] + storage['index_bytes'],
                         storage['total_bytes'])
        self.assertIn('data/public/provenance.json', [f['path'] for f in storage['files']])
        required_paths = {f'data/public/hansen_{band}_sample.tif' for band in
                          ('treecover2000', 'lossyear', 'datamask')} | {'data/public/provenance.json'}
        self.assertEqual({f['path'] for f in storage['files']}, required_paths)
        self.assertEqual(storage['total_bytes'], 585293)
        self.assertEqual(storage['metadata_bytes'], 8294)
        research = benchmark['baseline']['research_overhead']
        self.assertEqual(research['total_bytes'], 948)
        self.assertEqual(research['total_bytes'], sum(f['bytes'] for f in research['files']))
        self.assertTrue({f['path'] for f in research['files']}.isdisjoint(required_paths))
        for entry in research['files']:
            path = ROOT / entry['path']
            self.assertEqual(entry['bytes'], path.stat().st_size)
            self.assertEqual(entry['sha256'], sha256_file(path))
        for entry in storage['files']:
            path = ROOT / entry['path']
            self.assertEqual(entry['bytes'], path.stat().st_size)
            self.assertEqual(entry['sha256'], sha256_file(path))
        self.assertEqual(benchmark['grid']['shape_rows_columns'], [604, 1233])
        self.assertEqual(benchmark['method']['query_count_per_batch'], 17)
        self.assertTrue(benchmark['baseline']['queries']['timed_answers_exact'])
        for candidate in benchmark['candidates']:
            self.assertTrue(candidate['fully_exact'], candidate.get('error'))
            self.assertEqual(candidate['fidelity']['exact_count'], 17)
            self.assertEqual(candidate['roundtrip']['raw_values_checked'], 3 * 604 * 1233)
            costs = candidate['storage']
            self.assertEqual(costs['total_bytes'], costs['payload_bytes'] +
                             costs['metadata_bytes'] + costs['index_bytes'])
            for entry in costs['files']:
                path = ROOT / 'artifacts/stores' / benchmark['experiment_id'] / candidate['candidate'] / entry['path']
                self.assertEqual(entry['bytes'], path.stat().st_size)
                self.assertEqual(entry['sha256'], sha256_file(path))


if __name__ == '__main__':
    unittest.main()
