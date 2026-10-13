"""J1/J2 regression controls, confined to new JRC-owned scratch files."""
import copy
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from engine import jrc_benchmark as bench
from engine import jrc_proof as proof
from engine.jrc import ROOT, SOURCE, QML, load_jrc
from engine.package_jrc import manifest
from engine.source import canonical_bytes, object_hash, sha256_file
from engine.tests.test_jrc_proof import rehash_artifact

SCRATCH = ROOT / 'data/experimental/jrc-engine/fix-tests'


class JrcMeasurementTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        SCRATCH.mkdir(parents=True, exist_ok=True)
        cls.results = []
        cls.artifact = json.loads((ROOT / 'artifacts/jrc-baseline-v1.json').read_text())

    @classmethod
    def tearDownClass(cls):
        report = {'artifact_sha256': cls.artifact['content_sha256'],
                  'run_id': cls.artifact['benchmark']['archive']['run_id'], 'checks': cls.results}
        path = ROOT / 'data/experimental/jrc-engine' / ('J1-J2-controls-'+object_hash(report)+'.json')
        path.write_bytes(canonical_bytes(report))

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(dir=SCRATCH)
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)

    def measurement_copy(self, tile=True):
        root = self.root / 'measurement'
        ident = self.artifact['benchmark']['identity']
        for record in ident['inputs'] + ident['implementation']:
            target = root / record['path']
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(ROOT / record['path'], target)
        if tile:
            # Read-only source cache reference; no writes through this link.
            (root / SOURCE).symlink_to(ROOT / SOURCE)
        return root

    def test_runner_rejects_wrong_second_measured_source_hot_answer(self):
        root = self.measurement_copy()
        real = bench.answers
        calls = 0
        def flaky(*args, **kwargs):
            nonlocal calls
            calls += 1
            answer = real(*args, **kwargs)
            if calls == 5:  # expected, two warmups, first measurement, second measurement
                answer = copy.deepcopy(answer)
                answer[0]['selected_cell_count'] += 1
            return answer
        with patch.object(bench, 'answers', side_effect=flaky), patch.object(bench, 'cold', side_effect=AssertionError('must fail before cold')):
            with self.assertRaisesRegex(ValueError, 'timed result mismatch') as caught:
                bench.run_jrc_benchmark(root)
        self.assertEqual(calls, 5)
        self.assertEqual(list(root.glob('artifacts/jrc-stores/*/run-*.json')), [])
        self.results.append({'case': 'runner-intermediate-query', 'rejected': True, 'reason': str(caught.exception), 'no_run_archived': True})

    def test_runner_rejects_wrong_intermediate_source_load(self):
        root = self.measurement_copy()
        real = bench.load_jrc
        calls = 0
        def flaky(*args, **kwargs):
            nonlocal calls
            calls += 1
            ds = real(*args, **kwargs)
            if calls == 5: ds.mask[0, 0] = not ds.mask[0, 0]
            return ds
        with patch.object(bench, 'load_jrc', side_effect=flaky):
            with self.assertRaisesRegex(ValueError, 'timed result mismatch') as caught:
                bench.run_jrc_benchmark(root)
        self.assertEqual(calls, 5)
        self.assertEqual(list(root.glob('artifacts/jrc-stores/*/run-*.json')), [])
        self.results.append({'case': 'runner-intermediate-load', 'rejected': True, 'reason': str(caught.exception)})

    def test_timed_checks_warmups_and_every_dataset_result(self):
        for phase, bad_at in [('warmup', 1), ('sample', 4)]:
            for mode in ('query', 'dataset'):
                ds = load_jrc()
                expected = bench.dataset_fingerprint(ds) if mode == 'dataset' else object_hash({'ok': True})
                count = 0
                def fn():
                    nonlocal count
                    count += 1
                    if mode == 'query': return {'ok': count != bad_at}
                    if count == bad_at: ds.values[0, 0] ^= 1
                    return ds
                with self.subTest(phase=phase, mode=mode), self.assertRaisesRegex(ValueError, 'timed result mismatch'):
                    bench.timed(fn, fingerprint=bench.dataset_fingerprint if mode == 'dataset' else object_hash,
                                expected_sha256=expected, guard=lambda: 'stable', expected_guard='stable')

    def test_real_input_code_and_store_end_guards(self):
        root = self.measurement_copy(tile=False)
        ds, plots = load_jrc(root), bench.pinned_plots(root)
        ident = bench.identity(ds, plots, root)
        for relative, field in [(QML, 'input'), ('engine/jrc.py', 'code')]:
            target = root / relative
            original = target.read_bytes()
            def fn():
                target.write_bytes(original+b'\n')
                return True
            with self.subTest(field=field), self.assertRaisesRegex(ValueError, 'identity changed'):
                bench.timed(fn, fingerprint=object_hash, expected_sha256=object_hash(True),
                            guard=lambda: bench.snapshot_guard(ident, plots, root), expected_guard=bench.guard_digest(ident))
            target.write_bytes(original)
            self.results.append({'case': field+'-end-guard', 'rejected': True})
        rel = self.artifact['store']['path']
        shutil.copytree(ROOT / rel, root / rel)
        store = root / rel
        expected = bench.guard_digest(ident, storage=bench.store_record(store, root))
        def mutate_store():
            with (store / 'index.json').open('ab') as f: f.write(b' ')
            return True
        with self.assertRaisesRegex(ValueError, 'end guard mismatch'):
            bench.timed(mutate_store, fingerprint=object_hash, expected_sha256=object_hash(True),
                        guard=lambda: bench.snapshot_guard(ident, plots, root, path=store), expected_guard=expected)
        self.results.append({'case': 'store-end-guard', 'rejected': True})

    def test_self_consistent_forged_intermediate_digests_and_guards_rejected(self):
        edits = [
            ('query-sample', lambda b: b['baseline']['hot_17_queries']['validation']['samples'][1].update(result_sha256='0'*64)),
            ('query-warmup', lambda b: b['baseline']['hot_17_queries']['validation']['warmups'][0].update(result_sha256='0'*64)),
            ('load-sample', lambda b: b['baseline']['load']['validation']['samples'][1].update(result_sha256='0'*64)),
            ('encode-sample', lambda b: b['candidates'][0]['encode']['validation']['samples'][1].update(result_sha256='0'*64)),
            ('decode-sample', lambda b: b['candidates'][0]['decode']['validation']['samples'][1].update(result_sha256='0'*64)),
            ('store-guard', lambda b: b['candidates'][0]['hot_17_queries']['validation']['samples'][1].update(guard_after='0'*64)),
            ('run-end', lambda b: b['measurement_guards'].update(end='0'*64)),
            ('cold-child', lambda b: b['cold_source']['children'][1].update(answer_sha256='0'*64)),
            ('cold-warmup', lambda b: b['cold_smallest_encoded']['warmup_children'][0].update(dataset_sha256='0'*64)),
            ('cold-code-guard', lambda b: b['cold_source']['children'][1].update(guard_after='0'*64)),
        ]
        real_read = proof.read_json
        for name, edit in edits:
            forged = copy.deepcopy(self.artifact)
            b = forged['benchmark']; edit(b)
            body = {k: v for k, v in b.items() if k != 'archive'}
            run = 'run-'+object_hash(body)
            relative = f"artifacts/jrc-stores/{b['experiment_id']}/{run}.json"
            b['archive'] = {'path': relative, 'run_id': run}
            for plot in forged['plots']: plot['receipt']['benchmark_run'] = run
            path = self.root / (name+'.json')
            path.write_bytes(canonical_bytes(rehash_artifact(forged)))
            def read(path, *args, **kwargs):
                return copy.deepcopy(body) if Path(path) == ROOT / relative else real_read(path, *args, **kwargs)
            with patch.object(proof, 'read_json', side_effect=read):
                result = proof.verify_jrc_artifact(path)
            with self.subTest(case=name):
                self.assertFalse(result['valid'], result)
                self.assertNotIn('archive', result['failures'][0])
            self.results.append({'case': 'verifier-'+name, 'rejected': not result['valid'], 'reason': result['failures'][0]})

    def test_cold_child_rejects_wrong_parent_context(self):
        source = load_jrc(); plots = bench.pinned_plots()
        ident = bench.identity(source, plots)
        context = {'identity': ident, 'dataset_sha256': bench.dataset_fingerprint(source),
                   'answer_sha256': '0'*64, 'expected_guard': bench.guard_digest(ident)}
        process = subprocess.run([sys.executable, '-B', '-m', 'engine.jrc_benchmark', '--child', 'source',
                                  '--context', canonical_bytes(context).decode()], cwd=ROOT, capture_output=True, text=True)
        self.assertNotEqual(process.returncode, 0)
        self.assertIn('child result/end identity mismatch', process.stderr)
        self.results.append({'case': 'cold-child-context', 'rejected': True})

    def test_minimal_bundle_verify_ordinary_export_verify_no_measurement(self):
        inventory = manifest(output=self.root / 'manifest.json')
        minimal = self.root / 'minimal'
        for record in inventory['files']:
            target = minimal / record['path']
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(ROOT / record['path'], target)
        self.assertFalse((minimal / SOURCE).exists())
        artifact = minimal / 'artifacts/jrc-baseline-v1.json'
        initial = artifact.read_bytes()
        original_files = {str(p.relative_to(minimal)): sha256_file(p) for p in minimal.rglob('*') if p.is_file()}
        # Direct API must not call the measurement runner under any circumstance.
        with patch.object(proof, 'run_jrc_benchmark', side_effect=AssertionError('unexpected remeasurement')):
            fresh = proof.export_jrc(output=artifact, root=minimal)
        self.assertEqual(initial, artifact.read_bytes())
        env = {**os.environ, 'PYTHONDONTWRITEBYTECODE': '1'}
        def command(args):
            proc = subprocess.run([sys.executable, '-B', '-m', 'engine.jrc', *args], cwd=minimal,
                                  env=env, capture_output=True, text=True)
            self.assertEqual(proc.returncode, 0, proc.stderr)
            return json.loads(proc.stdout)
        before = command(['--verify', 'artifacts/jrc-baseline-v1.json'])
        command([])
        after = command(['--verify', 'artifacts/jrc-baseline-v1.json'])
        self.assertTrue(before['valid'] and after['valid'])
        self.assertFalse(before['full_source_cache_present'] or after['full_source_cache_present'])
        self.assertEqual(initial, artifact.read_bytes())
        self.assertEqual(original_files, {str(p.relative_to(minimal)): sha256_file(p) for p in minimal.rglob('*') if p.is_file()})
        self.assertEqual(fresh['benchmark']['measured_at_utc'], self.artifact['benchmark']['measured_at_utc'])
        self.results.append({'case': 'minimal-verify-export-verify', 'valid_before': True, 'valid_after': True,
                             'byte_identical': True, 'full_tile_present': False, 'measurement_mock_not_called': True,
                             'file_inventory_unchanged': True, 'file_count': len(inventory['files']),
                             'bundle_bytes': inventory['total_bytes'], 'artifact_sha256': sha256_file(artifact)})


if __name__ == '__main__': unittest.main()
