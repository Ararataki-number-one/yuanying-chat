#!/usr/bin/env python3
"""Real loopback SOCKS/TLS controls for a separate transport diagnostic ledger.

Clients and the explicit write-failure injections are host test boundaries.
No Android/Gecko/public network or cause of an earlier device failure is inferred.
"""
import argparse
import ast
import concurrent.futures
import contextlib
import hashlib
import json
from pathlib import Path
import socket
import ssl
import sys
import threading
import time
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools/browser'))
import ip_timezone_fixture_server as fixture
from fingerprint_fixture_server import HOSTS
from newworker_fixture_server import WorkerFixtureServer

CHECKS, NEGATIVE_CASES, PRESERVATION = [], [], {}
SOURCE_INPUTS = (
    'tools/browser/ip_timezone_fixture_server.py',
    'tools/browser/fingerprint_fixture_server.py',
    'tools/browser/newworker_fixture_server.py',
    'tests/ip_timezone_transport_diagnostics_test.py',
)
ORIGINAL_SNAPSHOT_KEYS = {'schema', 'binding', 'syntheticGeoService',
    'actualPublicIpGeolocationVerified', 'productionEndpointOverride', 'geoSource',
    'routes', 'events', 'errors', 'controlRequests', 'upstreamConnections',
    'forwardingImplemented', 'certificateExceptionUsed', 'caPemSha256',
    'leafDerSha256', 'closed'}
DIAGNOSTIC_KEYS = {'schema', 'kind', 'binding', 'collectorClosed', 'quiescent',
    'eventLimit', 'totalFailures', 'recordedEvents', 'droppedEvents', 'counts', 'events'}
EVENT_KEYS = {'sequence', 'route', 'protocol', 'stage', 'exceptionClass', 'guardCode', 'collectorClosed'}
BASE_SOURCE = '6ee06aced87581e52aa301431f8996ed46d666b8'
BASE_PATH = 'tools/browser/ip_timezone_fixture_server.py'
BASE_BYTES = 20523
BASE_SHA256 = '3da21b0755af9b958e39e7e912fabfa5f5c89bdde878d1d25c8755bd34d273b1'
BASE_METHOD_SHA256 = {
    'error': '0e12b1700676c46182914611f7486b605ab81447774c3d256fbc77b5e737eca5',
    'snapshot': 'c00b1cd463cc9a8216af1ce3516534f96696877c74bf9e7e8ee6c58811314bba',
}


def preservation_proof():
    """Remove only enumerated diagnostic additions, then compare whole bytes.

    This inverse is test evidence only. The server and its business consumers
    always execute the complete current source; no historical reader is used.
    """
    current = (ROOT/BASE_PATH).read_text()
    tree = ast.parse(current)
    new_constants = {'MAX_TRANSPORT_DIAGNOSTICS', 'TRANSPORT_STAGES',
                     'TRANSPORT_EXCEPTION_TYPES', 'TRANSPORT_GUARD_CODES'}
    removals = set()
    found = set()
    for node in tree.body:
        if isinstance(node, ast.Assign) and len(node.targets) == 1 and isinstance(node.targets[0], ast.Name) and node.targets[0].id in new_constants:
            found.add(node.targets[0].id)
            removals.update(range(node.lineno, node.end_lineno+1))
    if found != new_constants:
        raise AssertionError('Exactly the four diagnostic constants are required')
    restored = ''.join(line for number, line in enumerate(current.splitlines(keepends=True), 1) if number not in removals)
    start = restored.index('    def _transport_failure(')
    end = restored.index('    def geo(', start)
    restored = restored[:start] + restored[end:]
    exact_lines = {
        "        previous_stage = getattr(self._response, 'transport_stage', 'http')\n",
        '            self.fleet._transport_failure(self.name, self._response.transport_stage, error)\n',
        '        self._transport_events = []\n',
        '        self._transport_counts = {name: {stage: {} for stage in TRANSPORT_STAGES} for name in ROUTES}\n',
        '        self._transport_total = 0\n',
        '        self._transport_quiescent = False\n',
    }
    for line in exact_lines:
        if restored.count(line) != 1:
            raise AssertionError('Exactly one enumerated diagnostic insertion is required')
        restored = restored.replace(line, '', 1)
    allowed_stage_lines = {'self._response.transport_stage = ' + repr(stage) + '\n'
        for stage in ('connection', 'proxy-tls', 'greeting', 'authentication',
                      'command', 'host', 'port', 'target-tls', 'http-connect', 'http', 'send')}
    allowed_stage_lines.add('self._response.transport_stage = previous_stage\n')
    retained = []
    for line in restored.splitlines(keepends=True):
        if line.lstrip().startswith('self._response.transport_stage = '):
            if line.lstrip() not in allowed_stage_lines:
                raise AssertionError('Only enumerated literal stage assignments may be removed')
        elif line != "        proxy._response.transport_stage = 'send'\n":
            retained.append(line)
    restored = ''.join(retained)
    marker = '        with self.lock:\n            self._transport_quiescent = True\n'
    if restored.count(marker) != 1:
        raise AssertionError('Exactly one diagnostic completion marker is required')
    restored = restored.replace(marker, '', 1)
    alias = '        except (ValueError, OSError, ssl.SSLError, UnicodeError) as error:\n'
    if restored.count(alias) != 1:
        raise AssertionError('Exactly one diagnostic exception alias is required')
    restored = restored.replace(alias, '        except (ValueError, OSError, ssl.SSLError, UnicodeError):\n', 1).encode()
    return dict(baseSource=BASE_SOURCE, sourcePath=BASE_PATH, originalSourceSha256=BASE_SHA256,
        restoredSourceSha256=hashlib.sha256(restored).hexdigest(),
        originalBytes=BASE_BYTES, restoredBytes=len(restored),
        completeOriginalSourceRestored=len(restored) == BASE_BYTES and hashlib.sha256(restored).hexdigest() == BASE_SHA256,
        inverseScope='Only the four new constants, two new methods, diagnostic stage assignments/call, exception alias, initialization and close-completion markers are removed.')


class TransportDiagnosticTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.certificates = fixture.IpFixtureCertificates()
        cls.context = ssl.create_default_context(cafile=str(cls.certificates.ca))

    @classmethod
    def tearDownClass(cls):
        directory = cls.certificates.directory
        cls.certificates.close()
        if directory.exists():
            raise AssertionError('Ephemeral loopback certificate material was not removed')

    def setUp(self):
        self.binding = dict(sourceCommit='a'*40, sourceTree='b'*40, runNonce='c'*32,
            integrationApkSha256='d'*64, sdkRunId='synthetic-host', sdkRunAttempt=1)
        script = 'const fixture=__WORKER_POLICY_FIXTURE__;'
        self.fleet = fixture.IpTimeZoneFleet(self.certificates, script, script, self.binding).start()
        self.clients = []
        self.addCleanup(self.fleet.close)
        self.addCleanup(self.close_clients)

    def close_clients(self):
        for client in self.clients:
            with contextlib.suppress(OSError):
                client.close()

    def check(self, name, condition):
        CHECKS.append(dict(name=name, **{'pass': bool(condition)}))
        if not condition:
            raise AssertionError(name)

    def wait(self, predicate):
        deadline = time.monotonic() + 4
        while not predicate():
            if time.monotonic() >= deadline:
                raise AssertionError('Controlled loopback handler did not settle')
            threading.Event().wait(.005)

    def raw(self, route='socks'):
        client = socket.create_connection(('127.0.0.1', self.fleet.proxies[route].port), timeout=4)
        self.clients.append(client)
        return client

    def drain(self, client):
        result = bytearray()
        while True:
            value = client.recv(16384)
            if not value:
                return bytes(result)
            result.extend(value)
            if len(result) > 262144:
                raise AssertionError('Controlled response exceeded its host-test bound')

    def reject_socks(self, payload, after_greeting=False, target_tls=False):
        client = self.raw()
        try:
            if after_greeting or target_tls:
                client.sendall(b'\x05\x01\x00')
                if fixture.exact_bytes(client, 2) != b'\x05\x00':
                    raise AssertionError('Actual SOCKS greeting response missing')
            if target_tls:
                host = fixture.GEO_HOST.encode('ascii')
                client.sendall(b'\x05\x01\x00\x03' + bytes([len(host)]) + host + b'\x01\xbb')
                if fixture.exact_bytes(client, 10)[:2] != b'\x05\x00':
                    raise AssertionError('Actual SOCKS command response missing')
            if payload:
                client.sendall(payload)
            client.shutdown(socket.SHUT_WR)
            with contextlib.suppress(ConnectionResetError):
                self.drain(client)
        finally:
            client.close()

    def channel(self, route, host=fixture.GEO_HOST):
        raw = self.raw(route)
        if route == 'https':
            raw = self.context.wrap_socket(raw, server_hostname='127.0.0.1')
            self.clients.append(raw)
        if route == 'socks':
            raw.sendall(b'\x05\x01\x00')
            self.check('Actual SOCKS greeting succeeds before controlled TLS', fixture.exact_bytes(raw, 2) == b'\x05\x00')
            name = host.encode('ascii')
            raw.sendall(b'\x05\x01\x00\x03' + bytes([len(name)]) + name + b'\x01\xbb')
            self.check('Actual domain SOCKS command succeeds before controlled TLS', fixture.exact_bytes(raw, 10)[:2] == b'\x05\x00')
        else:
            raw.sendall(('CONNECT ' + host + ':443 HTTP/1.1\r\nHost: ' + host + ':443\r\n\r\n').encode('ascii'))
            head = bytearray()
            while not head.endswith(b'\r\n\r\n'):
                value = raw.recv(1)
                if not value:
                    raise AssertionError('Actual CONNECT response missing')
                head.extend(value)
            self.check('Actual CONNECT succeeds before controlled target TLS ' + route, head.startswith(b'HTTP/1.1 200 '))
        channel = (fixture.NestedTlsChannel(raw, self.context, server_side=False, server_hostname=host)
                   if route == 'https' else self.context.wrap_socket(raw, server_hostname=host))
        self.clients.append(channel)
        return channel

    def get(self, route, host=fixture.GEO_HOST, target=fixture.GEO_TARGET, method='GET', extra=''):
        channel = self.channel(route, host)
        try:
            channel.sendall((method + ' ' + target + ' HTTP/1.1\r\nHost: ' + host + '\r\n' + extra + '\r\n').encode('ascii'))
            return self.drain(channel)
        finally:
            channel.close()

    def settled(self, total):
        self.wait(lambda: self.fleet.diagnostic_snapshot()['totalFailures'] == total)
        self.wait(lambda: all(not proxy._threads for proxy in self.fleet.proxies.values()))

    def test_real_malformed_socks_reports_each_phase_and_keeps_eof_as_error(self):
        host = fixture.GEO_HOST.encode('ascii')
        cases = [
            ('early-eof', b'', False, 'greeting', 'ValueError', 'incomplete-read'),
            ('version', b'\x04', False, 'greeting', 'ValueError', 'socks-version'),
            ('no-method', b'\x05\x00', False, 'authentication', 'ValueError', 'socks-authentication'),
            ('unsupported-method', b'\x05\x01\xff', False, 'authentication', 'ValueError', 'socks-authentication'),
            ('command-eof', b'', True, 'command', 'ValueError', 'incomplete-read'),
            ('command', b'\x05\x02\x00\x03', True, 'command', 'ValueError', 'socks-command'),
            ('host-bound', b'\x05\x01\x00\x03\x00', True, 'host', 'ValueError', 'socks-host-bound'),
            ('host-ascii', b'\x05\x01\x00\x03\x01\xff', True, 'host', 'UnicodeDecodeError', 'other-guard'),
            ('foreign-host', b'\x05\x01\x00\x03\x12PRIVATE_WIRE_TOKEN\x01\xbb', True, 'host', 'ValueError', 'socks-host'),
            ('port', b'\x05\x01\x00\x03' + bytes([len(host)]) + host + b'\x00\x50', True, 'port', 'ValueError', 'socks-port'),
        ]
        for total, (name, payload, greeted, stage, category, guard_code) in enumerate(cases, 1):
            self.reject_socks(payload, greeted)
            self.settled(total)
            diagnostic = self.fleet.diagnostic_snapshot()
            row = diagnostic['events'][-1]
            self.check('Actual rejected SOCKS stage ' + name, row['stage'] == stage and row['exceptionClass'] == category and row['route'] == 'socks')
            self.check('Fixed guard code separates actual SOCKS rejection ' + name, row['guardCode'] == guard_code)
            self.check('Exactly one original error remains for SOCKS ' + name, self.fleet.snapshot()['errors'] == dict(socks=total, http=0, https=0) and diagnostic['totalFailures'] == total)
            self.check('Open collector state is retained for SOCKS ' + name, row['collectorClosed'] is False and diagnostic['quiescent'] is False)
            NEGATIVE_CASES.append(name)
        self.check('Even early EOF still fails the original zero-error condition', self.fleet.snapshot()['errors']['socks'] == len(cases) and not all(value == 0 for value in self.fleet.snapshot()['errors'].values()))
        self.check('Malformed SOCKS input never fabricates a native event', self.fleet.snapshot()['events'] == [])
        self.check('Wire values never enter diagnostic records', 'PRIVATE_WIRE_TOKEN' not in json.dumps(self.fleet.diagnostic_snapshot()))

    def test_real_proxy_tls_target_tls_connect_and_http_failures_are_separate(self):
        client = self.raw('https')
        client.sendall(b'PRIVATE_BAD_TLS_RECORD')
        client.shutdown(socket.SHUT_WR)
        with contextlib.suppress(ConnectionResetError):
            self.drain(client)
        client.close()
        self.settled(1)
        row = self.fleet.diagnostic_snapshot()['events'][-1]
        self.check('Outer proxy TLS failure has its actual protocol stage', row['stage'] == 'proxy-tls' and row['route'] == 'https' and row['exceptionClass'] in {'SSLError', 'SSLEOFError', 'ConnectionResetError'})
        self.reject_socks(b'PRIVATE_BAD_TARGET_TLS', target_tls=True)
        self.settled(2)
        row = self.fleet.diagnostic_snapshot()['events'][-1]
        self.check('Target TLS failure is separate from proxy TLS', row['stage'] == 'target-tls' and row['route'] == 'socks' and row['exceptionClass'] in {'SSLError', 'SSLEOFError', 'ConnectionResetError'})
        client = self.raw('http')
        client.sendall(b'CONNECT private.invalid:443 HTTP/1.1\r\nHost: private.invalid\r\nAuthorization: PRIVATE_HEADER_TOKEN\r\n\r\n')
        client.shutdown(socket.SHUT_WR)
        self.drain(client)
        client.close()
        self.settled(3)
        row = self.fleet.diagnostic_snapshot()['events'][-1]
        self.check('CONNECT validation failure has the HTTP CONNECT stage', row['stage'] == 'http-connect' and row['exceptionClass'] == 'ValueError' and row['guardCode'] == 'connect-target')
        self.get('http', method='POST', extra='Cookie: PRIVATE_HEADER_TOKEN\r\n')
        self.settled(4)
        row = self.fleet.diagnostic_snapshot()['events'][-1]
        self.check('Post-TLS HTTP validation has a separate stage', row['stage'] == 'http' and row['exceptionClass'] == 'ValueError' and row['guardCode'] == 'http-authority')
        self.check('Each rejected transport increments only its original route', self.fleet.snapshot()['errors'] == dict(socks=1, http=2, https=1))
        text = json.dumps(self.fleet.diagnostic_snapshot())
        self.check('Diagnostics export no host header TLS bytes or messages', all(value not in text for value in ('private.invalid', 'PRIVATE_HEADER_TOKEN', 'PRIVATE_BAD', 'Authorization', 'Cookie', '/tmp/')))
        NEGATIVE_CASES.extend(('proxy-tls', 'target-tls', 'http-connect', 'http'))

    def test_real_three_transports_and_content_success_do_not_change_original_schema(self):
        for route in fixture.ROUTES:
            raw = self.get(route)
            head, separator, body = raw.partition(b'\r\n\r\n')
            value = json.loads(body)
            self.check('Real controlled TLS response succeeds ' + route, head.startswith(b'HTTP/1.1 200 ') and separator == b'\r\n\r\n' and value['timezone']['id'] == fixture.ROUTES[route]['zoneId'])
        self.check('Real controlled content response succeeds', self.get('socks', HOSTS[0], '/env-policy?phase=gecko-system').startswith(b'HTTP/1.1 200 '))
        self.wait(lambda: all(not proxy._threads for proxy in self.fleet.proxies.values()))
        original = self.fleet.snapshot()
        diagnostic = self.fleet.diagnostic_snapshot()
        self.check('Original snapshot field set is unchanged', set(original) == ORIGINAL_SNAPSHOT_KEYS)
        self.check('Successful requests add no original errors or diagnostic failures', original['errors'] == dict.fromkeys(fixture.ROUTES, 0) and diagnostic['totalFailures'] == 0 and diagnostic['events'] == [])
        self.check('Diagnostic side channel keeps the exact source binding', diagnostic['binding'] == original['binding'] == self.binding)
        self.check('No forwarding or public geolocation success is inferred', original['upstreamConnections'] == 0 and original['forwardingImplemented'] is False and original['actualPublicIpGeolocationVerified'] is False)

    def test_controlled_send_failures_record_only_fixed_exception_classes(self):
        private_type = type('PRIVATE_EXCEPTION_CLASS_TOKEN', (ValueError,), {})
        for total, (failure, expected) in enumerate(((BrokenPipeError('PRIVATE_MESSAGE_TOKEN'), 'BrokenPipeError'),
                (TimeoutError('PRIVATE_MESSAGE_TOKEN'), 'TimeoutError'),
                (private_type('PRIVATE_MESSAGE_TOKEN'), 'OtherValueError')), 1):
            # Only this write boundary is injected. The SOCKS handshake, target
            # TLS and HTTP parsing execute on actual fixed loopback sockets.
            with patch.object(WorkerFixtureServer, '_send', side_effect=failure):
                self.get('socks', HOSTS[0], '/env-policy?phase=gecko-system')
                self.settled(total)
            row = self.fleet.diagnostic_snapshot()['events'][-1]
            self.check('Response write failure retains its send stage ' + expected, row['stage'] == 'send' and row['exceptionClass'] == expected)
            self.check('Unrecognized write failure messages have only a fixed generic code ' + expected, row['guardCode'] == 'other-guard')
            self.check('Response write failure still increments original errors ' + expected, self.fleet.snapshot()['errors']['socks'] == total)
            NEGATIVE_CASES.append('explicit-write-boundary-' + expected)
        self.check('Neither exception message nor arbitrary class name is exported', 'PRIVATE_' not in json.dumps(self.fleet.diagnostic_snapshot()))

    def test_real_failure_volume_is_bounded_without_dropping_original_errors(self):
        total = fixture.MAX_TRANSPORT_DIAGNOSTICS + 7
        for number in range(1, total + 1):
            self.reject_socks(b'\x04')
            self.wait(lambda: self.fleet.diagnostic_snapshot()['totalFailures'] == number)
        self.settled(total)
        diagnostic = self.fleet.diagnostic_snapshot()
        self.check('Diagnostic event list keeps its fixed bound', diagnostic['eventLimit'] == 128 and diagnostic['recordedEvents'] == len(diagnostic['events']) == 128)
        self.check('Dropped diagnostics remain counted separately', diagnostic['droppedEvents'] == 7 and diagnostic['totalFailures'] == total)
        self.check('All original errors survive diagnostic truncation', self.fleet.snapshot()['errors'] == dict(socks=total, http=0, https=0))
        self.check('Per-stage exception counts retain every observed failure', diagnostic['counts']['socks']['greeting'] == {'ValueError': total})
        self.check('Only fixed route and stage keys occur in counters', set(diagnostic['counts']) == set(fixture.ROUTES) and all(set(counts) == set(fixture.TRANSPORT_STAGES) for counts in diagnostic['counts'].values()))
        self.check('First bounded failures keep monotonic sequence numbers', [row['sequence'] for row in diagnostic['events']] == list(range(1,129)))
        self.check('The side channel does not consume the native event budget', self.fleet.snapshot()['events'] == [])

    def test_close_records_inflight_failure_and_only_then_marks_quiescence(self):
        client = self.raw()
        self.wait(lambda: bool(self.fleet.proxies['socks']._threads))
        before = self.fleet.diagnostic_snapshot()
        self.check('An open collector cannot claim a final snapshot', before['collectorClosed'] is False and before['quiescent'] is False)
        self.fleet.close()
        after = self.fleet.diagnostic_snapshot()
        self.check('Close waits for the existing handler guards before final diagnostics', after['collectorClosed'] is True and after['quiescent'] is True)
        self.check('Collector-close EOF remains an original counted failure', after['totalFailures'] == 1 and self.fleet.snapshot()['errors']['socks'] == 1 and after['events'][0]['collectorClosed'] is True)
        self.check('Final diagnostics remain unchanged after the client observes closure', self.drain(client) == b'' and self.fleet.diagnostic_snapshot() == after)
        self.check('No new original snapshot key was needed for diagnostics', set(self.fleet.snapshot()) == ORIGINAL_SNAPSHOT_KEYS)

    def test_snapshot_copies_and_fixed_keys_prevent_mutable_or_raw_exports(self):
        self.reject_socks(b'\x04')
        self.settled(1)
        first = self.fleet.diagnostic_snapshot()
        self.check('Diagnostic schema has only its fixed bounded fields', set(first) == DIAGNOSTIC_KEYS and all(set(row) == EVENT_KEYS for row in first['events']))
        original = self.fleet.snapshot()
        first['binding']['runNonce'] = 'edited'
        first['events'][0]['stage'] = 'edited'
        first['counts']['socks']['greeting']['ValueError'] = 999
        second = self.fleet.diagnostic_snapshot()
        self.check('Returned diagnostics cannot mutate internal binding events or counts', second['binding'] == self.binding and second['events'][0]['stage'] == 'greeting' and second['counts']['socks']['greeting']['ValueError'] == 1)
        self.check('Reading diagnostics leaves original bytes and counters alone', self.fleet.snapshot() == original)

    def test_concurrent_real_connections_keep_thread_local_stage_ownership(self):
        cases = [(b'\x04', False), (b'\x05\x01\xff', False), (b'\x05\x02\x00\x03', True)] * 3
        with concurrent.futures.ThreadPoolExecutor(4) as pool:
            list(pool.map(lambda value: self.reject_socks(*value), cases))
        self.settled(len(cases))
        diagnostic = self.fleet.diagnostic_snapshot()
        self.check('Concurrent actual connections retain their own protocol stages', all(diagnostic['counts']['socks'][stage] == {'ValueError': 3} for stage in ('greeting', 'authentication', 'command')))
        self.check('Concurrent failures are counted exactly once on the original route', self.fleet.snapshot()['errors'] == dict(socks=9, http=0, https=0) and diagnostic['totalFailures'] == 9)

    def test_only_fixed_known_guard_messages_are_classified(self):
        PRESERVATION.update(preservation_proof())
        self.check('Removing only diagnostic additions restores the complete original source bytes', PRESERVATION['completeOriginalSourceRestored'])
        text = (ROOT/'tools/browser/ip_timezone_fixture_server.py').read_text()
        tree = ast.parse(text)
        fleet = next(node for node in tree.body if isinstance(node, ast.ClassDef) and node.name == 'IpTimeZoneFleet')
        error = next(node for node in fleet.body if isinstance(node, ast.FunctionDef) and node.name == 'error')
        snapshot = next(node for node in fleet.body if isinstance(node, ast.FunctionDef) and node.name == 'snapshot')
        error_sha = hashlib.sha256(ast.get_source_segment(text, error).encode()).hexdigest()
        snapshot_sha = hashlib.sha256(ast.get_source_segment(text, snapshot).encode()).hexdigest()
        self.check('Original error method remains whole bytes', error_sha == BASE_METHOD_SHA256['error'])
        self.check('Original snapshot method remains whole bytes', snapshot_sha == BASE_METHOD_SHA256['snapshot'])
        PRESERVATION['originalErrorMethodSha256'] = error_sha
        PRESERVATION['originalSnapshotMethodSha256'] = snapshot_sha
        for index, value in enumerate((ValueError('PRIVATE_UNKNOWN_GUARD'), ValueError('Synthetic TLS fixture: SOCKS version invalid PRIVATE_SUFFIX'), ValueError(0), ValueError(['PRIVATE_UNKNOWN_GUARD']))):
            self.fleet._transport_failure('socks', 'greeting', value)
            self.check('Only an exact fixed string can produce a known guard code ' + str(index), self.fleet.diagnostic_snapshot()['events'][-1]['guardCode'] == 'other-guard')
            NEGATIVE_CASES.append('unrecognized-guard-args-' + str(index))
        self.check('Unknown exception args are never exported', 'PRIVATE_' not in json.dumps(self.fleet.diagnostic_snapshot()))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path)
    args, extra = parser.parse_known_args()
    hashes = {name: hashlib.sha256((ROOT/name).read_bytes()).hexdigest() for name in SOURCE_INPUTS}
    suite = unittest.defaultTestLoader.loadTestsFromModule(sys.modules[__name__])
    result = unittest.TextTestRunner(stream=sys.stderr, verbosity=2).run(suite)
    stable = all(hashlib.sha256((ROOT/name).read_bytes()).hexdigest() == digest for name, digest in hashes.items())
    passed = result.wasSuccessful() and stable and CHECKS and all(row['pass'] for row in CHECKS)
    report = dict(schema=1, status='passed' if passed else 'failed', tests=result.testsRun,
        assertions=len(CHECKS), passed=sum(row['pass'] for row in CHECKS),
        total=len(CHECKS), failures=len(result.failures), errors=len(result.errors),
        negativeCases=len(NEGATIVE_CASES), checks=CHECKS, sourceFiles=hashes,
        preservationProof=PRESERVATION,
        executionInputsUnchanged=stable, actualLoopbackSocketExecution=True,
        actualTlsSocketExecution=True, injectedWriteFailureBoundary=True,
        actualAndroidExecution=False, actualGeckoExecution=False,
        actualPublicNetworkExecution=False, actualComboFailureCauseEstablished=False,
        eofErrorsExempted=False, scope='Real fixed-loopback SOCKS/CONNECT/TLS parser and shutdown controls; malformed protocol and explicitly injected response-write exception boundaries. Diagnostics remain separate from original counters/snapshot. No Android, Gecko, public endpoint, prior errors38 cause, EOF exemption or release qualification.')
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps({key: report[key] for key in ('status', 'tests', 'assertions', 'negativeCases', 'executionInputsUnchanged')}))
    raise SystemExit(0 if passed else 1)
