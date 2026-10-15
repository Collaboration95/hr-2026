"""Optional read-only IPv4 loopback service for the retained Hansen snapshot.

Run: .venv-data/bin/python -B -m engine.live_server --port 8765
"""
import argparse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import re
import socket
import sys
import threading
from time import monotonic

from .live_query import LIMITS, LiveError, LiveSnapshot, parse_request
from .source import canonical_bytes

DEFAULT_ORIGINS = frozenset(('http://127.0.0.1:5173', 'http://localhost:5173',
                             'http://127.0.0.1:4173', 'http://localhost:4173'))


def validate_origin(origin):
    if type(origin) is not str:
        raise ValueError('origin must be an exact HTTP loopback origin with an explicit port')
    match = re.fullmatch(r'http://(?:localhost|127\.0\.0\.1):([0-9]{1,5})', origin)
    if not match or not 1 <= int(match[1]) <= 65535:
        raise ValueError('origin must be an exact HTTP loopback origin with an explicit port')
    return origin


class LiveHTTPServer(ThreadingHTTPServer):
    daemon_threads = True
    block_on_close = False
    request_queue_size = 8

    def __init__(self, snapshot, port=8765, allow_origins=(), *, max_connections=8,
                 max_queries=2, read_timeout=2.0, request_timeout=5.0):
        if type(port) is not int or not 0 <= port <= 65535:
            raise ValueError('port must be between 0 and 65535')
        if max_connections < 1 or max_queries < 1 or read_timeout <= 0 or request_timeout <= 0:
            raise ValueError('service capacity and timeouts must be positive')
        self.snapshot = snapshot
        self.allow_origins = DEFAULT_ORIGINS | frozenset(validate_origin(v) for v in allow_origins)
        self._connection_slots = threading.BoundedSemaphore(max_connections)
        self._query_slots = threading.BoundedSemaphore(max_queries)
        self.read_timeout, self.request_timeout = read_timeout, request_timeout
        # Deliberately no configurable bind host, root or store parameter.
        super().__init__(('127.0.0.1', port), LiveHandler)

    def process_request(self, request, client_address):
        if not self._connection_slots.acquire(blocking=False):
            body = canonical_bytes(LiveError(503, 'BUSY', 'Local request capacity is busy; retry shortly.').envelope())
            try:
                request.settimeout(0.1)
                request.sendall(b'HTTP/1.0 503 Service Unavailable\r\nContent-Type: application/json\r\n'
                                b'Connection: close\r\nContent-Length: ' + str(len(body)).encode('ascii') + b'\r\n\r\n' + body)
            except OSError:
                pass
            finally:
                self.shutdown_request(request)
            return
        try:
            super().process_request(request, client_address)
        except Exception:
            self._connection_slots.release()
            raise

    def process_request_thread(self, request, client_address):
        try:
            super().process_request_thread(request, client_address)
        finally:
            self._connection_slots.release()

    def handle_error(self, request, client_address):
        # Transport failures never print request/body or tracebacks.
        pass


class LiveHandler(BaseHTTPRequestHandler):
    protocol_version = 'HTTP/1.0'  # one bounded request per connection
    server_version = 'PlotlineLoopback/1'
    sys_version = ''

    def setup(self):
        super().setup()
        self.connection.settimeout(self.server.read_timeout)
        self._origin = None
        self._deadline = monotonic() + self.server.request_timeout
        # Absolute connection lifetime also bounds slowly dribbled headers/body.
        self._expiry = threading.Timer(self.server.request_timeout, self._expire)
        self._expiry.daemon = True
        self._expiry.start()

    def _expire(self):
        try:
            self.connection.shutdown(socket.SHUT_RDWR)
        except OSError:
            pass

    def finish(self):
        self._expiry.cancel()
        try:
            super().finish()
        except OSError:
            pass

    def log_message(self, format, *args):
        pass

    def _send(self, status, value=None, extra_headers=()):
        body = b'' if value is None else canonical_bytes(value)
        self.close_connection = True
        self.send_response(status)
        self.send_header('Content-Type', 'application/json; charset=utf-8')
        self.send_header('Content-Length', str(len(body)))
        self.send_header('Connection', 'close')
        self.send_header('Cache-Control', 'no-store')
        self.send_header('X-Content-Type-Options', 'nosniff')
        self.send_header('Vary', 'Origin')
        if self._origin:
            self.send_header('Access-Control-Allow-Origin', self._origin)
        for key, item in extra_headers:
            self.send_header(key, item)
        self.end_headers()
        if self.command != 'HEAD':
            self.wfile.write(body)

    def send_error(self, code, message=None, explain=None):
        # Base parser errors are JSON too; never reflect its raw request text.
        status, name = (405, 'METHOD_NOT_ALLOWED') if code == 501 else (400, 'INVALID_REQUEST')
        try:
            self._send(status, LiveError(status, name, 'Unsupported method or malformed HTTP request.').envelope())
        except OSError:
            pass

    def _single(self, name, required=False):
        values = self.headers.get_all(name, [])
        if len(values) > 1 or (required and len(values) != 1):
            raise LiveError(400, 'INVALID_REQUEST', f'Exactly one {name} header is required.')
        return values[0] if values else None

    def _access(self):
        hosts = self.headers.get_all('Host', [])
        port = self.server.server_address[1]
        if len(hosts) != 1 or hosts[0].lower() not in (f'127.0.0.1:{port}', f'localhost:{port}'):
            raise LiveError(403, 'HOST_NOT_ALLOWED', 'Host must identify this bound loopback port.')
        origins = self.headers.get_all('Origin', [])
        if len(origins) > 1 or (origins and origins[0] not in self.server.allow_origins):
            raise LiveError(403, 'ORIGIN_NOT_ALLOWED', 'Browser origin is not allowed for this local service.')
        self._origin = origins[0] if origins else None

    def _length(self, required=False):
        if self.headers.get_all('Transfer-Encoding') or self.headers.get_all('Expect'):
            raise LiveError(400, 'INVALID_REQUEST', 'Transfer-Encoding and Expect are unsupported; send a bounded Content-Length body.')
        value = self._single('Content-Length', required=required)
        if value is None:
            return 0
        if not re.fullmatch('[0-9]{1,10}', value):
            raise LiveError(400, 'INVALID_REQUEST', 'Content-Length must be an unambiguous nonnegative integer.')
        length = int(value)
        if length > LIMITS['max_body_bytes']:
            raise LiveError(413, 'BODY_TOO_LARGE', 'Request body exceeds 65536 bytes.')
        return length

    def _read_body(self, size):
        parts, remaining = [], size
        while remaining:
            budget = self._deadline - monotonic()
            if budget <= 0:
                raise TimeoutError('request deadline')
            self.connection.settimeout(min(self.server.read_timeout, budget))
            chunk = self.rfile.read1(min(remaining, 65536))
            if not chunk:
                raise LiveError(400, 'INVALID_REQUEST', 'Request body ended before Content-Length.')
            parts.append(chunk)
            remaining -= len(chunk)
        return b''.join(parts)

    def _route(self):
        self._access()
        if self.path not in ('/v1/health', '/v1/query'):
            raise LiveError(404, 'NOT_FOUND', 'No such live API path.')
        expected = 'GET' if self.path == '/v1/health' else 'POST'
        if self.command == 'OPTIONS':
            if self._length() != 0:
                raise LiveError(400, 'INVALID_REQUEST', 'Preflight requests must not contain a body.')
            if self._origin is None:
                raise LiveError(403, 'ORIGIN_NOT_ALLOWED', 'Preflight requires an allowed Origin.')
            method = self._single('Access-Control-Request-Method', required=True)
            headers = self._single('Access-Control-Request-Headers')
            requested = [v.strip().lower() for v in headers.split(',')] if headers else []
            if method != expected:
                raise LiveError(405, 'METHOD_NOT_ALLOWED', 'Preflight method is not allowed for this path.')
            if any(v != 'content-type' for v in requested) or len(set(requested)) != len(requested):
                raise LiveError(400, 'INVALID_REQUEST', 'Only the Content-Type request header is allowed in preflight.')
            self._send(204, extra_headers=(('Access-Control-Allow-Methods', expected),
                                           ('Access-Control-Allow-Headers', 'Content-Type')))
            return
        if self.command != expected:
            raise LiveError(405, 'METHOD_NOT_ALLOWED', 'Method is not allowed for this path.')
        length = self._length(required=self.command == 'POST')
        if self.server.snapshot is None:
            raise LiveError(503, 'NOT_READY', 'The verified local snapshot is not ready.')
        if self.command == 'GET':
            if length != 0:
                raise LiveError(400, 'INVALID_REQUEST', 'Health requests must not contain a body.')
            self._send(200, self.server.snapshot.health())
            return
        content_type = self._single('Content-Type')
        if content_type is None or not re.fullmatch(r'application/json(?:\s*;\s*charset\s*=\s*(?:utf-8|"utf-8"))?', content_type, re.IGNORECASE):
            raise LiveError(415, 'UNSUPPORTED_MEDIA_TYPE', 'Use application/json with optional UTF-8 charset.')
        body = self._read_body(length)
        request = parse_request(body)
        if not self.server._query_slots.acquire(blocking=False):
            raise LiveError(503, 'BUSY', 'Local query capacity is busy; retry shortly.', request['request_id'])
        try:
            response = self.server.snapshot.query(request, body)
        finally:
            self.server._query_slots.release()
        self._send(200, response)

    def _dispatch(self):
        try:
            self._route()
        except LiveError as exc:
            try:
                self._send(exc.status, exc.envelope())
            except OSError:
                pass
        except (TimeoutError, OSError):
            try:
                self._send(400, LiveError(400, 'INVALID_REQUEST', 'Request read timed out or connection closed.').envelope())
            except OSError:
                pass
        except Exception:
            try:
                self._send(500, LiveError(500, 'INTERNAL_ERROR', 'Local query failed; no agreement receipt was issued.').envelope())
            except OSError:
                pass

    do_GET = do_POST = do_OPTIONS = do_PUT = do_DELETE = do_PATCH = do_HEAD = do_TRACE = do_CONNECT = _dispatch


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--port', type=int, default=8765)
    parser.add_argument('--allow-origin', action='append', default=[])
    args = parser.parse_args(argv)
    try:
        for origin in args.allow_origin:
            validate_origin(origin)
        if not 0 <= args.port <= 65535:
            raise ValueError('port must be between 0 and 65535')
        snapshot = LiveSnapshot.load()
        server = LiveHTTPServer(snapshot, args.port, args.allow_origin)
    except (ValueError, OSError) as exc:
        message = exc.message if isinstance(exc, LiveError) else 'Invalid local configuration or loopback port unavailable.'
        print('Live service startup failed: ' + message, file=sys.stderr)
        return 2
    print(json.dumps({'status': 'ready', 'url': f'http://127.0.0.1:{server.server_address[1]}',
                      'snapshot_id': snapshot.snapshot_id}), flush=True)
    try:
        server.serve_forever(poll_interval=0.2)
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
