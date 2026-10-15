"""Real ephemeral-loopback HTTP tests, with bounded deterministic adverse cases."""
from contextlib import contextmanager
import hashlib
import http.client
import io
import json
from pathlib import Path
import socket
import subprocess
import sys
import threading
import time
import unittest
from unittest.mock import patch

from engine.live_query import LiveSnapshot
from engine.live_server import DEFAULT_ORIGINS, LiveHTTPServer, validate_origin
from engine.source import ROOT, canonical_bytes, load_plots, sha256_file
from engine.tests.test_live_query import rectangle, request_for, synthetic_snapshot


@contextmanager
def running(snapshot, **options):
    server = LiveHTTPServer(snapshot, port=0, **options)
    worker = threading.Thread(target=server.serve_forever, kwargs={'poll_interval': .01}, daemon=True)
    worker.start()
    try:
        yield server
    finally:
        server.shutdown()
        server.server_close()
        worker.join(timeout=2)


def exchange(server, method='GET', path='/v1/health', body=None, headers=None):
    connection = http.client.HTTPConnection('127.0.0.1', server.server_port, timeout=3)
    try:
        connection.request(method, path, body=body, headers=headers or {})
        response = connection.getresponse()
        raw = response.read()
        return response.status, dict(response.getheaders()), json.loads(raw) if raw else None
    finally:
        connection.close()


def raw_exchange(server, headers, body=b'', method='POST', path='/v1/query', half_close=False):
    wire = f'{method} {path} HTTP/1.1\r\n'.encode()
    wire += b''.join(f'{key}: {value}\r\n'.encode() for key, value in headers) + b'\r\n' + body
    connection = socket.create_connection(('127.0.0.1', server.server_port), timeout=3)
    try:
        connection.sendall(wire)
        if half_close:
            connection.shutdown(socket.SHUT_WR)
        response = http.client.HTTPResponse(connection)
        response.begin()
        raw = response.read()
        return response.status, dict(response.getheaders()), json.loads(raw) if raw else None
    finally:
        connection.close()


class TestLiveHTTP(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.snapshot = LiveSnapshot.load()
        cls.context = running(cls.snapshot)
        cls.server = cls.context.__enter__()

    @classmethod
    def tearDownClass(cls):
        cls.context.__exit__(None, None, None)

    def request_body(self, request_id='http-1'):
        return canonical_bytes(request_for(self.snapshot, load_plots()[0]['geometry'], request_id))

    def assert_error_response(self, response, status, code):
        actual, headers, value = response
        self.assertEqual(actual, status)
        self.assertEqual(value['schema_version'], 'plotline.live-error.v1')
        self.assertEqual(value['error']['code'], code)
        self.assertEqual(headers['Connection'], 'close')
        self.assertNotIn('Traceback', json.dumps(value))
        self.assertNotIn(str(ROOT), json.dumps(value))
        return value

    def test_real_health_and_query_over_http(self):
        self.assertEqual(self.server.server_address[0], '127.0.0.1')
        status, headers, health = exchange(self.server)
        self.assertEqual(status, 200)
        self.assertEqual(health, self.snapshot.health())
        body = self.request_body()
        status, headers, result = exchange(self.server, 'POST', '/v1/query', body, {'Content-Type': 'application/json; charset=UTF-8'})
        self.assertEqual(status, 200)
        self.assertEqual(result['request_body_sha256'], hashlib.sha256(body).hexdigest())
        self.assertEqual(result['source_result']['selected_cell_count'], 121)
        self.assertEqual(result['comparison'], {'equal': True, 'differing_fields': []})
        for field in ('source_result', 'compact_result', 'evidence'):
            encoded = result[field + '_canonical_json']
            self.assertEqual(json.loads(encoded), result[field])
            self.assertEqual(hashlib.sha256(encoded.encode('utf-8')).hexdigest(),
                             result['receipt']['payload'][field + '_sha256'])
        self.assertEqual(headers['Cache-Control'], 'no-store')

    def test_exact_origin_allowlist_and_no_credentials(self):
        self.assertEqual(len(DEFAULT_ORIGINS), 4)
        for origin in DEFAULT_ORIGINS:
            status, headers, _ = exchange(self.server, headers={'Origin': origin})
            self.assertEqual(status, 200)
            self.assertEqual(headers['Access-Control-Allow-Origin'], origin)
            self.assertNotIn('Access-Control-Allow-Credentials', headers)
        for origin in ('null', 'https://localhost:5173', 'http://localhost:5173.evil.example',
                       'http://localhost:51730', 'http://127.0.0.2:5173', 'http://user@localhost:5173',
                       'http://localhost:5173/', '*'):
            with self.subTest(origin=origin):
                response = exchange(self.server, headers={'Origin': origin})
                self.assert_error_response(response, 403, 'ORIGIN_NOT_ALLOWED')
                self.assertNotIn('Access-Control-Allow-Origin', response[1])
        self.assertNotIn('Access-Control-Allow-Origin', exchange(self.server)[1])

    def test_host_exact_port_and_duplicate_host_rejection(self):
        for host in (f'localhost:{self.server.server_port}', f'127.0.0.1:{self.server.server_port}'):
            self.assertEqual(exchange(self.server, headers={'Host': host})[0], 200)
        for host in ('localhost', '127.0.0.1:8765', f'evil.example:{self.server.server_port}',
                     f'localhost.evil.example:{self.server.server_port}', f'user@localhost:{self.server.server_port}'):
            self.assert_error_response(exchange(self.server, headers={'Host': host}), 403, 'HOST_NOT_ALLOWED')
        duplicate = [('Host', f'localhost:{self.server.server_port}')] * 2
        self.assert_error_response(raw_exchange(self.server, duplicate, method='GET', path='/v1/health'), 403, 'HOST_NOT_ALLOWED')
        self.assert_error_response(raw_exchange(self.server, [], method='GET', path='/v1/health'), 403, 'HOST_NOT_ALLOWED')

    def test_duplicate_origins_rejected(self):
        headers = [('Host', f'localhost:{self.server.server_port}'), ('Origin', 'http://localhost:5173'),
                   ('Origin', 'http://localhost:5173')]
        self.assert_error_response(raw_exchange(self.server, headers, method='GET', path='/v1/health'), 403, 'ORIGIN_NOT_ALLOWED')

    def test_preflight_valid_origin_method_headers_only(self):
        headers = {'Origin': 'http://localhost:5173', 'Access-Control-Request-Method': 'POST',
                   'Access-Control-Request-Headers': 'content-type'}
        status, response_headers, body = exchange(self.server, 'OPTIONS', '/v1/query', headers=headers)
        self.assertEqual(status, 204)
        self.assertIsNone(body)
        self.assertEqual(response_headers['Access-Control-Allow-Methods'], 'POST')
        self.assertEqual(response_headers['Access-Control-Allow-Headers'], 'Content-Type')
        self.assert_error_response(exchange(self.server, 'OPTIONS', '/v1/query', headers={**headers, 'Access-Control-Request-Method': 'DELETE'}), 405, 'METHOD_NOT_ALLOWED')
        self.assert_error_response(exchange(self.server, 'OPTIONS', '/v1/query', headers={**headers, 'Access-Control-Request-Headers': 'authorization'}), 400, 'INVALID_REQUEST')
        self.assert_error_response(exchange(self.server, 'OPTIONS', '/v1/query', headers={**headers, 'Origin': 'http://evil.example'}), 403, 'ORIGIN_NOT_ALLOWED')
        self.assert_error_response(exchange(self.server, 'OPTIONS', '/v1/query'), 403, 'ORIGIN_NOT_ALLOWED')
        self.assertEqual(exchange(self.server, 'OPTIONS', '/v1/health', headers={**headers, 'Access-Control-Request-Method': 'GET'})[0], 204)

    def test_invalid_json_and_content_types(self):
        for body in (b'\xff', b'{', b'{"request_id":"a","request_id":"b"}', b'NaN'):
            response = exchange(self.server, 'POST', '/v1/query', body, {'Content-Type': 'application/json'})
            value = self.assert_error_response(response, 400, 'INVALID_JSON')
            self.assertIsNone(value['request_id'])
        for content_type in (None, 'text/plain', 'application/json; charset=latin-1', 'application/json; foo=bar'):
            headers = {'Content-Type': content_type} if content_type else {}
            self.assert_error_response(exchange(self.server, 'POST', '/v1/query', self.request_body(), headers), 415, 'UNSUPPORTED_MEDIA_TYPE')

    def test_ambiguous_malformed_missing_length_and_chunked_rejected(self):
        base = [('Host', f'localhost:{self.server.server_port}'), ('Content-Type', 'application/json')]
        cases = [[], [('Content-Length', '-1')], [('Content-Length', '+1')], [('Content-Length', '1,1')],
                 [('Content-Length', '0'), ('Content-Length', '0')],
                 [('Transfer-Encoding', 'chunked')], [('Content-Length', '0'), ('Transfer-Encoding', 'identity')],
                 [('Content-Length', '0'), ('Expect', '100-continue')]]
        for extra in cases:
            with self.subTest(headers=extra):
                self.assert_error_response(raw_exchange(self.server, base+extra), 400, 'INVALID_REQUEST')
        self.assert_error_response(raw_exchange(self.server, base+[('Content-Length', '65537')]), 413, 'BODY_TOO_LARGE')
        self.assert_error_response(raw_exchange(self.server, base+[('Content-Length', '100')], b'{}', half_close=True), 400, 'INVALID_REQUEST')

    def test_forbidden_methods_and_paths(self):
        for method, path in (('POST', '/v1/health'), ('GET', '/v1/query'), ('PUT', '/v1/query'),
                             ('DELETE', '/v1/query'), ('TRACE', '/v1/health'), ('CONNECT', '/v1/health'),
                             ('UNRECOGNIZED', '/v1/query')):
            self.assert_error_response(exchange(self.server, method, path), 405, 'METHOD_NOT_ALLOWED')
        for path in ('/', '/v1/query?store=secret', '/v1/health/', '/../../data/public/provenance.json',
                     'http://localhost/v1/health'):
            self.assert_error_response(exchange(self.server, path=path, headers={'Host': f'localhost:{self.server.server_port}'}), 404, 'NOT_FOUND')

    def test_snapshot_conflict_and_invalid_geometry_http_statuses(self):
        request = request_for(self.snapshot, rectangle(0, 0, .0001, .0001))
        request['expected_snapshot_id'] = '0' * 64
        response = exchange(self.server, 'POST', '/v1/query', canonical_bytes(request), {'Content-Type': 'application/json'})
        self.assert_error_response(response, 409, 'SNAPSHOT_MISMATCH')
        request['expected_snapshot_id'] = self.snapshot.snapshot_id
        request['geometry'] = {'type': 'Point', 'coordinates': [0, 0]}
        response = exchange(self.server, 'POST', '/v1/query', canonical_bytes(request), {'Content-Type': 'application/json'})
        self.assert_error_response(response, 422, 'INVALID_GEOMETRY')

    def test_http_late_response_keeps_its_own_request_binding(self):
        entered, release = threading.Event(), threading.Event()
        original = LiveSnapshot.query
        def delayed(snapshot, request, body):
            if request['request_id'] == 'old':
                entered.set()
                if not release.wait(timeout=2):
                    raise RuntimeError('test release timeout')
            return original(snapshot, request, body)
        responses = {}
        old_body, current_body = self.request_body('old'), self.request_body('current')
        with patch.object(LiveSnapshot, 'query', delayed):
            old_thread = threading.Thread(target=lambda: responses.update(old=exchange(self.server, 'POST', '/v1/query', old_body, {'Content-Type': 'application/json'})))
            old_thread.start()
            try:
                self.assertTrue(entered.wait(timeout=1))
                responses['current'] = exchange(self.server, 'POST', '/v1/query', current_body, {'Content-Type': 'application/json'})
                self.assertEqual(responses['current'][2]['request_id'], 'current')
            finally:
                release.set()
                old_thread.join(timeout=2)
        for name, body in (('old', old_body), ('current', current_body)):
            self.assertEqual(responses[name][0], 200)
            self.assertEqual(responses[name][2]['request_id'], name)
            self.assertEqual(responses[name][2]['request_body_sha256'], hashlib.sha256(body).hexdigest())

    def test_requests_do_not_write_or_mutate_pinned_inputs(self):
        paths = [ROOT / item['path'] for item in self.snapshot.health()['snapshot']['verified_files']]
        paths.extend((ROOT / name) for name in ('artifacts/demo-v1.json', 'artifacts/example-v1.json'))
        before = {str(path): sha256_file(path) for path in paths}
        # File I/O is forbidden during the request, not merely absent afterward.
        with patch('builtins.open', side_effect=AssertionError('request attempted file I/O')), \
             patch.object(Path, 'open', side_effect=AssertionError('request attempted file I/O')):
            self.assertEqual(exchange(self.server)[0], 200)
            body = canonical_bytes(request_for(self.snapshot, rectangle(0, 0, .0001, .0001)))
            self.assertEqual(exchange(self.server, 'POST', '/v1/query', body, {'Content-Type': 'application/json'})[0], 200)
        self.assertEqual(before, {str(path): sha256_file(path) for path in paths})


class TestLiveTransportLimits(unittest.TestCase):
    def test_actual_running_query_enforces_capacity(self):
        snapshot = synthetic_snapshot()
        entered, release = threading.Event(), threading.Event()
        original = LiveSnapshot.query
        def slow(snapshot, request, body):
            entered.set()
            if not release.wait(timeout=2):
                raise RuntimeError('test release timeout')
            return original(snapshot, request, body)
        body = canonical_bytes(request_for(snapshot, rectangle(0, 0, 1, 1)))
        first = []
        with running(snapshot, max_queries=1) as server, patch.object(LiveSnapshot, 'query', slow):
            worker = threading.Thread(target=lambda: first.append(exchange(server, 'POST', '/v1/query', body, {'Content-Type': 'application/json'})))
            worker.start()
            try:
                self.assertTrue(entered.wait(timeout=1))
                overloaded = exchange(server, 'POST', '/v1/query', body, {'Content-Type': 'application/json'})
                self.assertEqual(overloaded[0], 503)
                self.assertEqual(overloaded[2]['error']['code'], 'BUSY')
                self.assertEqual(exchange(server)[0], 200)
            finally:
                release.set()
                worker.join(timeout=2)
        self.assertEqual(first[0][0], 200)

    def test_added_origins_are_only_exact_http_loopback(self):
        valid = 'http://127.0.0.1:9123'
        self.assertEqual(validate_origin(valid), valid)
        for origin in ('*', 'http://localhost', 'https://localhost:1234', 'http://user@localhost:1234',
                       'http://localhost:1234/', 'http://localhost:1234?q=1', 'http://localhost:1234#x',
                       'http://[::1]:1234', 'http://localhost:0', 'http://localhost:65536'):
            with self.subTest(origin=origin), self.assertRaises(ValueError):
                validate_origin(origin)
        with running(synthetic_snapshot(), allow_origins=[valid]) as server:
            self.assertEqual(exchange(server, headers={'Origin': valid})[0], 200)

    def test_busy_query_returns_503_without_waiting_and_recovers(self):
        snapshot = synthetic_snapshot()
        with running(snapshot, max_queries=1) as server:
            body = canonical_bytes(request_for(snapshot, rectangle(0, 0, 1, 1)))
            server._query_slots.acquire()
            try:
                response = exchange(server, 'POST', '/v1/query', body, {'Content-Type': 'application/json', 'Origin': 'http://localhost:5173'})
                self.assertEqual(response[0], 503)
                self.assertEqual(response[2]['error']['code'], 'BUSY')
                self.assertEqual(response[2]['request_id'], 'test-1')
                self.assertEqual(response[1]['Access-Control-Allow-Origin'], 'http://localhost:5173')
            finally:
                server._query_slots.release()
            self.assertEqual(exchange(server, 'POST', '/v1/query', body, {'Content-Type': 'application/json'})[0], 200)

    def test_connection_capacity_is_bounded_and_reports_busy(self):
        with running(synthetic_snapshot(), max_connections=1) as server:
            server._connection_slots.acquire()
            try:
                response = exchange(server)
                self.assertEqual(response[0], 503)
                self.assertEqual(response[2]['error']['code'], 'BUSY')
            finally:
                server._connection_slots.release()
            self.assertEqual(exchange(server)[0], 200)

    def test_short_body_read_timeout_closes_connection(self):
        with running(synthetic_snapshot(), read_timeout=.1, request_timeout=1) as server:
            start = time.monotonic()
            response = raw_exchange(server, [('Host', f'localhost:{server.server_port}'),
                                    ('Content-Type', 'application/json'), ('Content-Length', '100')], b'{')
            self.assertEqual(response[0], 400)
            self.assertEqual(response[2]['error']['code'], 'INVALID_REQUEST')
            self.assertLess(time.monotonic()-start, 1)

    def test_absolute_connection_deadline_bounds_incomplete_headers(self):
        with running(synthetic_snapshot(), read_timeout=1, request_timeout=.15) as server:
            connection = socket.create_connection(('127.0.0.1', server.server_port), timeout=1)
            try:
                start = time.monotonic()
                connection.sendall(b'GET /v1/health HTTP/1.1\r\nHost: ')
                received = connection.recv(4096)
                self.assertEqual(received, b'')
                self.assertLess(time.monotonic()-start, .8)
            finally:
                connection.close()

    def test_not_ready_and_internal_error_are_structured(self):
        with running(None) as server:
            response = exchange(server)
            self.assertEqual(response[0], 503)
            self.assertEqual(response[2]['error']['code'], 'NOT_READY')
        snapshot = synthetic_snapshot()
        with running(snapshot) as server, patch.object(LiveSnapshot, 'query', side_effect=RuntimeError('secret internal path')):
            body = canonical_bytes(request_for(snapshot, rectangle(0, 0, 1, 1)))
            response = exchange(server, 'POST', '/v1/query', body, {'Content-Type': 'application/json'})
            self.assertEqual(response[0], 500)
            self.assertEqual(response[2]['error']['code'], 'INTERNAL_ERROR')
            self.assertNotIn('secret', json.dumps(response))

    def test_startup_cli_rejects_host_flag_and_remote_origin(self):
        for args in (['--host', '0.0.0.0'], ['--allow-origin', 'https://remote.example'], ['--port', '65536']):
            process = subprocess.run([sys.executable, '-B', '-m', 'engine.live_server', *args], cwd=ROOT,
                                     capture_output=True, timeout=5)
            self.assertEqual(process.returncode, 2)
            self.assertNotIn(b'Traceback', process.stderr)


if __name__ == '__main__':
    unittest.main()
