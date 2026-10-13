"""Content-addressed experiment identities and atomic, append-only run evidence.

An experiment identifies inputs, implementation and settings. A run identifies
the measured result, so reruns keep earlier timings rather than replacing them.
The small index is protected with a local POSIX file lock, not a remote service.
"""
import argparse
import fcntl
import hashlib
import json
import os
from pathlib import Path
import tempfile

ROOT = Path(__file__).resolve().parents[1]


def canonical_bytes(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'),
                      ensure_ascii=True, allow_nan=False).encode('utf-8')


def content_hash(value):
    return hashlib.sha256(canonical_bytes(value)).hexdigest()


def experiment_id(identity):
    return 'exp-' + content_hash(identity)


def atomic_write_json(path, value):
    """Replace a JSON file atomically after flushing its complete contents."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix='.' + path.name + '-', dir=path.parent)
    try:
        with os.fdopen(fd, 'wb') as stream:
            stream.write(canonical_bytes(value) + b'\n')
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        Path(temporary).unlink(missing_ok=True)


def record_experiment(identity, result, directory=None):
    """Preserve each distinct result; an exact retry identifies the existing run.

    If interrupted after writing a run but before its index update, calling this
    function again repairs that index entry without changing the run evidence.
    """
    directory = Path(directory) if directory is not None else ROOT / 'artifacts/experiments'
    exp_id = experiment_id(identity)
    run_id = 'run-' + content_hash(result)
    folder = directory / exp_id
    folder.mkdir(parents=True, exist_ok=True)
    with (directory / '.registry.lock').open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        identity_path = folder / 'identity.json'
        if identity_path.exists():
            if json.loads(identity_path.read_text()) != identity:
                raise ValueError('experiment identity collision')
        else:
            atomic_write_json(identity_path, identity)
        run_path = folder / (run_id + '.json')
        duplicate = run_path.exists()
        if duplicate:
            if canonical_bytes(json.loads(run_path.read_text())) != canonical_bytes(result):
                raise ValueError('run content collision')
        else:
            atomic_write_json(run_path, result)
        index_path = directory / 'index.json'
        index = json.loads(index_path.read_text()) if index_path.exists() else {
            'schema_version': 'plotline.experiments.v1', 'experiments': {}}
        runs = sorted(p.stem for p in folder.glob('run-*.json'))
        index['experiments'][exp_id] = {'identity': exp_id + '/identity.json', 'runs': runs}
        atomic_write_json(index_path, index)
    return {'experiment_id': exp_id, 'run_id': run_id, 'duplicate_result': duplicate,
            'run_count': len(runs), 'is_repeat': len(runs) > 1,
            'result_path': exp_id + '/' + run_path.name}


def publish_benchmark(result, directory, canonical_path):
    """Publish an exploratory result only while no explicit choice is frozen."""
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)
    with (directory / '.registry.lock').open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        if (directory / 'retained-choice.json').exists():
            return False
        atomic_write_json(canonical_path, result)
    return True


def freeze_selection(result, reason, directory, canonical_path):
    """Bind canonical output to immutable measured evidence and an explicit reason.

    Calling this function deliberately can replace a prior retained decision;
    ordinary experiment runs cannot. Every decision is itself archived by hash.
    The benchmark wrapper additionally checks live inputs and store file hashes.
    """
    if not isinstance(reason, str) or not reason.strip():
        raise ValueError('explicit nonempty retention reason required')
    directory = Path(directory)
    registry = result['registry']
    exp_id, run_id = registry['experiment_id'], registry['run_id']
    if exp_id != experiment_id(result['identity']):
        raise ValueError('retained identity does not match experiment ID')
    run_path = directory / exp_id / (run_id + '.json')
    archived = json.loads(run_path.read_text())
    payload = {k: v for k, v in result.items() if k not in
               ('registry', 'publication', 'retained_selection')}
    if content_hash(payload) != content_hash(archived) or run_id != 'run-' + content_hash(archived):
        raise ValueError('retention must reference unchanged registered evidence')
    eligible = [c for c in archived['candidates'] if c.get('fully_exact')]
    if not eligible or not archived['baseline']['queries']['timed_answers_exact']:
        raise ValueError('no fully exact, timed source/compact evidence to retain')
    smallest = min(eligible, key=lambda c: (c['storage']['total_bytes'], c['candidate']))
    if archived['winner']['candidate'] != smallest['candidate']:
        raise ValueError('retained winner differs from minimum fully exact encoded candidate')
    overall = ('source_geotiff' if archived['baseline']['storage']['total_bytes'] <=
               smallest['storage']['total_bytes'] else smallest['candidate'])
    if archived['overall_storage_choice'] != overall:
        raise ValueError('retained overall storage choice is inconsistent')
    selection = {'schema_version': 'plotline.retained-benchmark.v1',
                 'experiment_id': exp_id, 'run_id': run_id,
                 'result_path': exp_id + '/' + run_path.name,
                 'reason': reason.strip(), 'smallest_encoded': {
                     'candidate': smallest['candidate'],
                     'chunk_size': archived['identity']['settings']['chunk_size'],
                     'total_bytes': smallest['storage']['total_bytes'],
                     'store_path': f'artifacts/stores/{exp_id}/{smallest["candidate"]}'},
                 'overall_storage_choice': overall,
                 'source_total_bytes': archived['baseline']['storage']['total_bytes']}
    selection_id = 'choice-' + content_hash(selection)
    with (directory / '.registry.lock').open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        atomic_write_json(directory / 'selections' / (selection_id + '.json'), selection)
        # Commit the selection first. Later exploratory publication is now blocked
        # even if canonical write fails; rerunning this deliberate call repairs it.
        atomic_write_json(directory / 'retained-choice.json', selection)
        atomic_write_json(canonical_path, dict(archived, registry=registry,
                                             retained_selection=selection))
    return selection


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--repetitions', type=int, default=7)
    parser.add_argument('--warmups', type=int, default=2)
    parser.add_argument('--chunk-size', type=int, default=128)
    parser.add_argument('--no-publish', action='store_true')
    args = parser.parse_args()
    from .benchmark import run_benchmark
    result = run_benchmark(repetitions=args.repetitions, warmups=args.warmups,
                           chunk_size=args.chunk_size, publish=not args.no_publish)
    print(json.dumps({'registry': result['registry'], 'winner': result['winner'],
                      'publication': result['publication']}, indent=2))


if __name__ == '__main__':
    main()
