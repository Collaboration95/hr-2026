"""Run the bounded study/fixture/suite commands and retain their actual output."""
from datetime import datetime, timezone
import json
from pathlib import Path
import subprocess
import sys

import study as s


def main():
    relative = s.OWNED.relative_to(s.ROOT)
    commands = [
        [str(s.ROOT / '.venv-data/bin/python'), '-B', str(relative / 'study.py')],
        [str(s.ROOT / '.venv-data/bin/python'), '-B', str(relative / 'fixtures.py')],
        [str(s.ROOT / '.venv-data/bin/python'), '-B', '-m', 'unittest', 'discover', '-s', str(relative),
         '-p', 'test_*.py', '-v'],
    ]
    records = []
    for command in commands:
        started = datetime.now(timezone.utc).isoformat()
        completed = subprocess.run(command, cwd=s.ROOT, capture_output=True, text=True, check=False)
        records.append({'argv': command, 'cwd': str(s.ROOT), 'started_utc': started,
                        'finished_utc': datetime.now(timezone.utc).isoformat(),
                        'exit_code': completed.returncode, 'stdout': completed.stdout, 'stderr': completed.stderr})
        print(json.dumps({'command': command, 'exit_code': completed.returncode}))
        if completed.returncode:
            print(completed.stdout)
            print(completed.stderr, file=sys.stderr)
            break
    success = len(records) == len(commands) and all(r['exit_code'] == 0 for r in records)
    results = json.loads((s.OWNED / 'results.json').read_text())
    fixtures = json.loads((s.OWNED / 'fixtures.json').read_text()) if len(records) > 1 else None
    fingerprint_checks = {path: s.fingerprint(s.ROOT / path) == expected
                          for path, expected in results['input_fingerprints'].items()}
    evidence = {
        'schema_version': 'plotline.spatial-sensitivity-verification.v1',
        'addressed_to': {'master': '01a130e9-aaf5-7a53-9cff-96d579f69b35',
                         'science_lead_volta': '01a132f8-f774-7b32-9eef-2c0f572c1df0'},
        'handoff': 'Shared local files; no callable agent/thread messaging tool available.',
        'commands': records,
        'results_content_sha256': results['content_sha256'],
        'fixtures_content_sha256': fixtures['content_sha256'] if fixtures else None,
        'final_input_fingerprint_checks': fingerprint_checks,
        'outputs': {str(p.relative_to(s.ROOT)): s.fingerprint(p)
                    for p in (s.OWNED / 'results.json', s.OWNED / 'witnesses.json', s.OWNED / 'fixtures.json')
                    if p.exists()},
        'pass': success and results['gates']['pass'] and bool(fixtures and fixtures['gates']['pass'])
                and all(fingerprint_checks.values()),
        'note': 'Times are execution records only, not a query benchmark; no performance claim.',
    }
    evidence['content_sha256'] = s.digest(evidence)
    s.write_json(s.OWNED / 'verification.json', evidence)
    print(json.dumps({'pass': evidence['pass'], 'results_content_sha256': results['content_sha256'],
                      'fixtures_content_sha256': evidence['fixtures_content_sha256'],
                      'input_fingerprints_unchanged': all(fingerprint_checks.values())}, indent=2))
    return 0 if evidence['pass'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
