#!/usr/bin/env python3
"""Real localhost/OpenSSL controls; no Android, Gecko or public-IP claims."""
import argparse
import copy
import hashlib
import json
from pathlib import Path
import socket
import ssl
import sys
import time
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools/browser'))
sys.path.insert(0, str(ROOT / 'tools/gecko'))
import tls_cpu_ip_combo_server as wire
from ip_timezone_fixture_server import (IpFixtureCertificates, IpTimeZoneFleet,
    GEO_HOST, GEO_TARGET, exact_bytes)
from native_tls_probe_server import (Cursor, NeedMore, handshake_bytes,
    parse_client_hello)

NEGATIVES = []
REAL_TRANSPORT_EXECUTED = False
SOURCE_INPUTS = ('tools/gecko/tls_cpu_ip_combo_server.py',
    'tests/gecko_tls_cpu_ip_wire_test.py', 'tools/browser/ip_timezone_fixture_server.py',
    'tools/browser/newworker_fixture_server.py', 'tools/browser/fingerprint_fixture_server.py',
    'tools/browser/native_tls_probe_server.py', 'tests/gecko/assets/gecko-cpu-ip-combo-page.js')


def source_hashes():
    return {name: hashlib.sha256((ROOT / name).read_bytes()).hexdigest() for name in SOURCE_INPUTS}


class CombinedWireControls(unittest.TestCase):
    def setUp(self):
        self.cert = IpFixtureCertificates()
        self.addCleanup(self.cert.close)
        self.binding = dict(sourceCommit='a'*40, sourceTree='b'*40, runNonce='c'*32,
            integrationApkSha256='d'*64, sdkRunId='123', sdkRunAttempt='1')
        self.capture = wire.TlsCpuIpCapture(self.cert, self.binding)
        script = (ROOT / 'tests/gecko/assets/gecko-cpu-ip-combo-page.js').read_text()
        self.fleet = IpTimeZoneFleet(self.cert, 'const x=__WORKER_POLICY_FIXTURE__;', script, self.binding).start()
        self.closed = False
        self.addCleanup(self.close)
        self.context = ssl.create_default_context(cafile=str(self.cert.ca))
        self.context.minimum_version = self.context.maximum_version = ssl.TLSVersion.TLSv1_3
        self.context.set_alpn_protocols(['h2', 'http/1.1'])

    def close(self):
        if not self.closed:
            self.fleet.close(); self.closed = True

    def reject(self, name, call):
        with self.subTest(name=name):
            with self.assertRaises((ValueError, KeyError, TypeError, AssertionError, UnicodeError, NeedMore)):
                call()
            NEGATIVES.append(name)

    def raw_socks(self, host=wire.HOST):
        raw = socket.create_connection(('127.0.0.1', self.fleet.proxies['socks'].port), timeout=5)
        raw.sendall(b'\x05\x01\x00'); self.assertEqual(exact_bytes(raw, 2), b'\x05\x00')
        name = host.encode('ascii')
        raw.sendall(bytes([5,1,0,3,len(name)]) + name + b'\x01\xbb')
        self.assertEqual(exact_bytes(raw, 10)[:2], b'\x05\x00')
        return raw

    def channel(self, host=wire.HOST, context=None, sni=None):
        raw = self.raw_socks(host)
        try:
            return (context or self.context).wrap_socket(raw, server_hostname=sni or host)
        except BaseException:
            raw.close(); raise

    def get(self, path, host=wire.HOST, extra=''):
        global REAL_TRANSPORT_EXECUTED
        with self.channel(host) as channel:
            self.assertEqual(channel.version(), 'TLSv1.3')
            self.assertEqual(channel.selected_alpn_protocol(), 'http/1.1')
            self.assertFalse(channel.session_reused)
            channel.sendall(('GET '+path+' HTTP/1.1\r\nHost: '+host+'\r\n'+extra+'\r\n').encode('ascii'))
            raw = bytearray()
            while True:
                block = channel.recv(65536)
                if not block: break
                raw.extend(block); self.assertLessEqual(len(raw), 131072)
        REAL_TRANSPORT_EXECUTED = True
        return bytes(raw).partition(b'\r\n\r\n')

    def freeze(self):
        self.close()
        return self.capture.snapshot(self.fleet)

    def test_actual_geo_and_page_marker_keep_sni_and_full_response(self):
        head, _, body = self.get(GEO_TARGET, GEO_HOST)
        self.assertTrue(head.startswith(b'HTTP/1.1 200 OK'))
        self.assertEqual(json.loads(body), {'success':True,'ip':'8.8.8.8','timezone':{'id':'America/New_York'}})
        head, _, body = self.get('/env-policy?phase=gecko-new-york')
        self.assertTrue(head.startswith(b'HTTP/1.1 200 OK'))
        self.assertIn(b'data-gecko-cpu-ip-combo', body)
        self.assertIn(b"/env-frame?phase=gecko-new-york", body)
        document = 'a1234567-abcd-4abc-8abc-123456789abc'
        _, _, body = self.get('/worker-probe?phase=gecko-new-york&realm=document&documentId='+document)
        self.assertEqual(body, b'worker-network-synthetic-v1')
        for host in (wire.HOST, 'fp-b.pocketchat.test'):
            head, _, _ = self.get('/env-frame?phase=gecko-new-york', host)
            self.assertTrue(head.startswith(b'HTTP/1.1 200 OK'))
        head, _, body = self.get('/favicon.ico')
        self.assertTrue(head.startswith(b'HTTP/1.1 200 OK')); self.assertEqual(body, b'')
        self.reject('live fleet cannot freeze', lambda:self.capture.snapshot(self.fleet))
        evidence = self.freeze()
        self.assertEqual(evidence['binding'], self.binding)
        self.assertTrue(evidence['serverClosed'] and evidence['serverThreadsJoined'])
        self.assertFalse(evidence['recordsOverflow']); self.assertEqual(evidence['rejectedHandshakes'], 0)
        self.assertEqual(evidence['upstreamConnections'], 0)
        self.assertFalse(evidence['forwardingImplemented'] or evidence['rawFatalAlertPacketDecoded'])
        self.assertEqual(len(evidence['records']), 4) # Geo/cross-origin frame are not fp-a wire evidence.
        randoms = set()
        for index, row in enumerate(evidence['records'], 1):
            self.assertEqual(row['sequence'], index)
            self.assertTrue(row['tlsNegotiated'] and row['requestObserved'] and row['responseObserved'])
            self.assertEqual(row['negotiatedVersion'], 'TLSv1.3')
            self.assertEqual(row['negotiatedAlpn'], 'http/1.1'); self.assertFalse(row['sessionReused'])
            hello = row['clientHello']; raw = bytes.fromhex(hello['clientHelloHandshakeHex'])
            records = b'\x16\x03\x01'+len(raw).to_bytes(2,'big')+raw
            self.assertEqual(parse_client_hello(records), hello)
            self.assertEqual(hello['supportedVersions'], [772])
            self.assertEqual(hello['serverNames'], [wire.HOST]); self.assertFalse(hello['preSharedKeyOffered'])
            randoms.add(hello['clientRandomHex'])
        self.assertEqual(len(randoms), 4)
        self.assertEqual(evidence['records'][1]['documentId'], document)
        route = self.fleet.snapshot()
        self.assertEqual(route['errors'], {'socks':0,'http':0,'https':0})
        self.assertEqual([e['targetSni'] for e in route['events']], [GEO_HOST, wire.HOST, wire.HOST, wire.HOST, 'fp-b.pocketchat.test', wire.HOST])
        self.assertEqual(evidence['records'][2]['realm'], 'frame')
        self.assertEqual(evidence['records'][3]['realm'], 'auxiliary')
        evidence['records'].clear()
        self.assertEqual(len(self.capture.snapshot(self.fleet)['records']), 4) # detached immutable result

    def test_real_tls12_and_foreign_sni_never_create_success_evidence(self):
        old = ssl.create_default_context(cafile=str(self.cert.ca))
        old.minimum_version = old.maximum_version = ssl.TLSVersion.TLSv1_2
        old.set_alpn_protocols(['http/1.1'])
        for label, context, name in (('TLS12-only client', old, wire.HOST),
                ('unknown actual SNI', self.context, 'example.invalid')):
            with self.subTest(label=label):
                with self.assertRaises((ssl.SSLError, OSError, ValueError)):
                    self.channel(context=context, sni=name)
                NEGATIVES.append(label)
        result = self.freeze()
        self.assertEqual(result['records'], [])
        self.assertGreaterEqual(result['rejectedHandshakes'], 2)

    def test_observer_rejects_unknown_path_without_exporting_request_secrets(self):
        _, _, body = self.get('/unexpected-secret-path?secret=uniqueSensitiveSentinel')
        self.assertEqual(body, b'')
        result = self.freeze()
        self.assertEqual(len(result['records']), 1)
        row = result['records'][0]
        self.assertTrue(row['tlsNegotiated'] and row['requestRejected'])
        self.assertFalse(row['requestObserved'] or row['responseObserved'])
        self.assertNotIn('uniqueSensitiveSentinel', json.dumps(result)); self.assertNotIn('unexpected-secret-path', json.dumps(result))
        NEGATIVES.append('actual unknown request never exports secret or success')

    def test_partial_hello_is_quiesced_before_final_snapshot(self):
        raw = self.raw_socks()
        raw.sendall(b'\x16\x03\x01\x00\x04\x01')
        time.sleep(.02) # Allow the real bounded worker to enter the peek; not an Android readiness gate.
        try:
            result = self.freeze()
        finally:
            raw.close()
        self.assertEqual(result['records'], [])
        self.assertEqual(self.capture.active, 0)
        self.assertTrue(result['serverThreadsJoined'])
        NEGATIVES.append('incomplete real ClientHello not accepted during close')

    def test_real_second_socket_hits_the_record_bound_and_freeze_is_final(self):
        with patch.object(wire, 'MAX_RECORDS', 1):
            self.get('/env-policy?phase=gecko-new-york')
            with self.assertRaises((ssl.SSLError, OSError, ValueError)):
                self.channel()
        result = self.freeze()
        self.assertTrue(result['recordsOverflow']); self.assertEqual(len(result['records']), 1)
        left, right = socket.socketpair()
        try:
            self.reject('no TLS writer after freeze', lambda:self.capture.wrap_socket(left, server_side=True))
        finally:
            left.close(); right.close()
        NEGATIVES.append('actual overflow cannot provide complete wire evidence')

    def test_generic_sni_selector_is_bounded_and_strict(self):
        outgoing, incoming = ssl.MemoryBIO(), ssl.MemoryBIO()
        ssl_object = self.context.wrap_bio(incoming, outgoing, server_hostname=wire.HOST)
        with self.assertRaises(ssl.SSLWantReadError): ssl_object.do_handshake()
        raw = outgoing.read()
        self.assertEqual(wire.client_hello_name(raw), wire.HOST)
        self.assertEqual(parse_client_hello(raw)['serverNames'], [wire.HOST])
        for name, value in (('truncated hello', raw[:8]), ('record bound', b'x'*(65536+1)),
                ('wrong record type', b'\x17'+raw[1:]), ('wrong record version', raw[:1]+b'\x02'+raw[2:]),
                ('foreign SNI bytes', raw.replace(wire.HOST.encode(), b'x'*len(wire.HOST)))):
            self.reject(name, lambda value=value:wire.client_hello_name(value))
        handshake = handshake_bytes(raw)
        split = 17
        fragments = b''.join(b'\x16\x03\x01'+len(p).to_bytes(2,'big')+p for p in (handshake[:split], handshake[split:]))
        self.assertEqual(wire.client_hello_name(fragments), wire.HOST)
        self.assertEqual(parse_client_hello(fragments), parse_client_hello(raw))

    def test_fixed_http_metadata_drops_unknown_or_oversized_values(self):
        base = b'GET /env-policy?phase=gecko-new-york HTTP/1.1\r\nHost: fp-a.pocketchat.test\r\n\r\n'
        self.assertEqual(wire.request_metadata(base), {'path':'/env-policy','phase':'gecko-new-york','realm':'document','documentId':''})
        changes = {
            'absolute URL':base.replace(b'/env-policy?', b'https://fp-a.pocketchat.test/env-policy?'),
            'raw unknown path':base.replace(b'/env-policy', b'/secret'),
            'foreign Host':base.replace(b'Host: fp-a.pocketchat.test', b'Host: private.invalid'),
            'duplicate Host':base.replace(b'\r\n\r\n', b'\r\nHost: fp-a.pocketchat.test\r\n\r\n'),
            'duplicate phase':base.replace(b'gecko-new-york HTTP', b'gecko-new-york&phase=gecko-new-york HTTP'),
            'unknown query':base.replace(b'gecko-new-york HTTP', b'gecko-new-york&secret=private HTTP'),
            'foreign phase':base.replace(b'gecko-new-york', b'gecko-unknown'),
            'favicon query':base.replace(b'/env-policy?phase=gecko-new-york', b'/favicon.ico?secret=private'),
            'frame extra query':base.replace(b'/env-policy?phase=gecko-new-york', b'/env-frame?phase=gecko-new-york&secret=private'),
            'request body':base.replace(b'\r\n\r\n', b'\r\nContent-Length: 1\r\n\r\n'),
            'chunked body':base.replace(b'\r\n\r\n', b'\r\nTransfer-Encoding: chunked\r\n\r\n'),
            'oversized header':base[:-2]+b'X-Bound: '+b'x'*16384+b'\r\n\r\n',
            'folded header':base.replace(b'Host:', b' Host:'),
            'missing terminator':base[:-1],
            'wrong method':base.replace(b'GET ',b'POST '),
            'non ASCII':base.replace(b'Host:', b'\xffHost:'),
            'marker document malformed':base.replace(b'/env-policy?phase=gecko-new-york',b'/worker-probe?phase=gecko-new-york&realm=document&documentId=secret'),
            'marker realm wrong':base.replace(b'/env-policy?phase=gecko-new-york',b'/worker-probe?phase=gecko-new-york&realm=service-worker&documentId=a1234567-abcd-4abc-8abc-123456789abc')}
        for name, value in changes.items(): self.reject(name, lambda value=value:wire.request_metadata(value))

    def test_actual_peer_range_and_ticket_readback_are_not_constants(self):
        self.get('/env-policy?phase=gecko-new-york')
        self.close()
        context = self.capture.context
        original = context.minimum_version, context.maximum_version, context.options, context.num_tickets
        changes = (
            ('peer allows TLS12', lambda:setattr(context, 'minimum_version', ssl.TLSVersion.TLSv1_2)),
            ('ticket count changed', lambda:setattr(context, 'num_tickets', 1)),
            ('ticket option changed', lambda:setattr(context, 'options', context.options & ~ssl.OP_NO_TICKET)))
        for name, change in changes:
            try:
                change(); self.reject(name, lambda:self.capture.snapshot(self.fleet))
            finally:
                context.minimum_version, context.maximum_version, context.options, context.num_tickets = original
        self.assertTrue(self.capture.snapshot(self.fleet)['ticketsDisabled'])

    def test_exact_binding_and_real_owned_fleet_are_required(self):
        self.close()
        for name, value in (('foreign full binding', {'sourceCommit':'f'*40}),
                ('integer SDK run', {'sdkRunId':123}), ('boolean attempt', {'sdkRunAttempt':True}),
                ('unknown binding key', {'secret':'do-not-export'})):
            changed = dict(self.binding); changed.update(value)
            if name == 'foreign full binding':
                self.fleet.binding = changed
                self.reject(name, lambda:self.capture.snapshot(self.fleet))
                self.fleet.binding = dict(self.binding)
            else:
                self.reject(name, lambda changed=changed:wire.TlsCpuIpCapture(self.cert, changed))
        self.reject('foreign fleet object', lambda:self.capture.snapshot(object()))
        self.reject('nested unobserved proxy TLS', lambda:self.capture.wrap_bio(None, None, server_side=True))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path)
    args = parser.parse_args()
    before = source_hashes()
    suite = unittest.defaultTestLoader.loadTestsFromTestCase(CombinedWireControls)
    result = unittest.TextTestRunner(stream=sys.stderr, verbosity=2).run(suite)
    after = source_hashes()
    passed = result.wasSuccessful() and before == after
    report = dict(schema=1, status='passed' if passed else 'failed',
        scope='host-only actual localhost OpenSSL; synthetic clients; no Android/native-engine or public-IP qualification',
        testsRun=result.testsRun, failures=len(result.failures), errors=len(result.errors),
        negativeControls=NEGATIVES, actualHostOpenSslExecution=REAL_TRANSPORT_EXECUTED,
        actualAndroidExecution=False, actualGeckoExecution=False,
        sourceFiles=before, executionInputsUnchanged=before == after)
    raw = json.dumps(report, indent=2, sort_keys=True)+'\n'
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True); args.output.write_text(raw)
    print(raw, end='')
    raise SystemExit(0 if passed else 1)


if __name__ == '__main__': main()
