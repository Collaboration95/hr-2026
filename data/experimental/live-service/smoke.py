"""Write local response examples and verify all 17 through ephemeral loopback.

Run from repository root:
PYTHONPATH=. .venv-data/bin/python -B data/experimental/live-service/smoke.py
"""
import hashlib
import http.client
import json
from pathlib import Path
import threading
from time import perf_counter

from engine.live_query import LiveSnapshot
from engine.live_server import LiveHTTPServer
from engine.source import ROOT, canonical_bytes, object_hash, sha256_file

OUT = Path(__file__).resolve().parent


def rectangle(x0, y0, x1, y1):
    return {'type': 'Polygon', 'coordinates': [[[x0, y0], [x1, y0], [x1, y1], [x0, y1], [x0, y0]]]}


def main():
    started = perf_counter()
    snapshot = LiveSnapshot.load()
    load_ms = (perf_counter()-started)*1000
    pinned = snapshot.health()['snapshot']['verified_files']
    hashes_before = {item['path']: sha256_file(ROOT / item['path']) for item in pinned}
    frozen = json.loads((ROOT / 'artifacts/demo-v1.json').read_bytes())
    canonical_before = sha256_file(ROOT / 'artifacts/demo-v1.json')
    server = LiveHTTPServer(snapshot, port=0)
    thread = threading.Thread(target=server.serve_forever, kwargs={'poll_interval': .01}, daemon=True)
    thread.start()

    def call(method, path, body=None):
        connection = http.client.HTTPConnection('127.0.0.1', server.server_port, timeout=3)
        try:
            connection.request(method, path, body=body, headers={
                'Origin': 'http://localhost:5173', 'Content-Type': 'application/json'})
            response = connection.getresponse()
            payload = json.loads(response.read())
            if response.status != 200:
                raise AssertionError((response.status, payload))
            return payload
        finally:
            connection.close()

    checks = []
    try:
        health = call('GET', '/v1/health')
        assert hashlib.sha256(health['snapshot_canonical_json'].encode()).hexdigest() == health['snapshot_id']
        (OUT / 'health-example.json').write_bytes(canonical_bytes(health) + b'\n')
        examples = {'known-plot': frozen['plots'][0]['geometry'],
                    'temporary-tiny': rectangle(98.77225, 8.58199, 98.77226, 8.582),
                    'outside': rectangle(0, 0, .0003, .0003)}
        for name, geometry in examples.items():
            request = {'schema_version': 'plotline.live-request.v1', 'request_id': name,
                       'expected_snapshot_id': health['snapshot_id'], 'geometry': geometry}
            body = canonical_bytes(request)
            result = call('POST', '/v1/query', body)
            (OUT / (name + '-request.json')).write_bytes(body)
            (OUT / (name + '-response.json')).write_bytes(canonical_bytes(result) + b'\n')
        for plot in frozen['plots']:
            request = {'schema_version': 'plotline.live-request.v1', 'request_id': 'http-' + plot['plot_id'],
                       'expected_snapshot_id': health['snapshot_id'], 'geometry': plot['geometry']}
            body = canonical_bytes(request)
            result = call('POST', '/v1/query', body)
            receipt = result['receipt']
            canonical_fields_bound = all(
                json.loads(result[name + '_canonical_json']) == result[name]
                and hashlib.sha256(result[name + '_canonical_json'].encode('utf-8')).hexdigest()
                    == receipt['payload'][name + '_sha256']
                for name in ('source_result', 'compact_result', 'evidence'))
            exact = (result['source_result'] == plot['source_result']
                     and result['compact_result'] == plot['compact_result']
                     and result['evidence']['cells'] == plot['evidence']
                     and result['request_body_sha256'] == hashlib.sha256(body).hexdigest()
                     and result['geometry_sha256'] == object_hash(plot['geometry'])
                     and receipt['payload']['evidence_sha256'] == object_hash(result['evidence'])
                     and json.loads(receipt['canonical_json']) == receipt['payload']
                     and hashlib.sha256(receipt['canonical_json'].encode()).hexdigest() == receipt['sha256']
                     and canonical_fields_bound)
            assert exact, plot['plot_id']
            checks.append({'plot_id': plot['plot_id'], 'exact': exact,
                           'selected_cell_count': result['source_result']['selected_cell_count']})
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)
    unchanged = hashes_before == {item['path']: sha256_file(ROOT / item['path']) for item in pinned}
    assert unchanged and canonical_before == sha256_file(ROOT / 'artifacts/demo-v1.json')
    proof = {'snapshot_id': snapshot.snapshot_id, 'load_ms': load_ms, 'actual_http_plot_count': len(checks),
             'matching_plots': sum(check['exact'] for check in checks), 'checks': checks,
             'selected_cells_sum_across_plots': sum(check['selected_cell_count'] for check in checks),
             'pinned_files_unchanged': unchanged, 'canonical_demo_unchanged': True,
             'http_port': server.server_port, 'listener_stopped_after_check': True,
             'method': 'one startup observation; real ephemeral IPv4 loopback HTTP; all17 frozen answers/evidence and request receipts checked; no performance claim',
             'implementation_sha256': {name: sha256_file(ROOT / 'engine' / name) for name in ('live_query.py', 'live_server.py')}}
    (OUT / 'verification.json').write_bytes(canonical_bytes(proof) + b'\n')
    print(json.dumps({key: proof[key] for key in ('snapshot_id', 'load_ms', 'matching_plots', 'actual_http_plot_count',
                                                'selected_cells_sum_across_plots', 'pinned_files_unchanged', 'listener_stopped_after_check')}, indent=2))


if __name__ == '__main__':
    main()
