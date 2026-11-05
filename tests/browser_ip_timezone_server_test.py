#!/usr/bin/env python3
"""Actual local sockets/TLS; synthetic clients, never Android or public geo proof."""
import concurrent.futures
import hashlib
import http.client
import json
from pathlib import Path
import socket
import ssl
import sys
import threading
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools/browser'))
from ip_timezone_fixture_server import (IpFixtureCertificates, IpTimeZoneFleet,
    NestedTlsChannel, GEO_HOST, GEO_TARGET, ROUTES, exact_bytes)
from fingerprint_fixture_server import HOSTS


class NativeProxyTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.cert = IpFixtureCertificates()
        cls.ctx = ssl.create_default_context(cafile=str(cls.cert.ca))

    @classmethod
    def tearDownClass(cls):
        path = cls.cert.directory
        cls.cert.close()
        assert not path.exists()

    def setUp(self):
        self.binding = dict(sourceCommit='a'*40, sourceTree='b'*40, runNonce='c'*32,
            integrationApkSha256='d'*64, sdkRunId='123', sdkRunAttempt='1')
        self.fleet = IpTimeZoneFleet(self.cert, 'const x=__WORKER_POLICY_FIXTURE__;',
                                    'const x=__WORKER_POLICY_FIXTURE__;', self.binding).start()
        self.addCleanup(self.fleet.close)

    def command(self, action, **values):
        return self.fleet.control(dict(sourceCommit=self.binding['sourceCommit'],
            runNonce=self.binding['runNonce'], action=action, **values))

    def channel(self, route, host=GEO_HOST, socks_type=3, port=443):
        raw = socket.create_connection(('127.0.0.1', self.fleet.proxies[route].port), timeout=5)
        try:
            if route == 'https':
                raw = self.ctx.wrap_socket(raw, server_hostname='127.0.0.1')
            if route == 'socks':
                raw.sendall(b'\x05\x01\x00')
                self.assertEqual(exact_bytes(raw, 2), b'\x05\x00')
                name = host.encode()
                raw.sendall(bytes([5,1,0,socks_type,len(name)])+name+port.to_bytes(2,'big'))
                self.assertEqual(exact_bytes(raw, 10)[:2], b'\x05\x00')
            else:
                raw.sendall(('CONNECT '+host+':'+str(port)+' HTTP/1.1\r\nHost: '+host+':'+str(port)+'\r\n\r\n').encode())
                head = b''
                while not head.endswith(b'\r\n\r\n'):
                    data = raw.recv(1)
                    if not data:
                        raise ValueError('CONNECT rejected')
                    head += data
                self.assertTrue(head.startswith(b'HTTP/1.1 200 '))
            return (NestedTlsChannel(raw, self.ctx, server_side=False, server_hostname=host)
                    if route == 'https' else self.ctx.wrap_socket(raw, server_hostname=host))
        except BaseException:
            raw.close()
            raise

    def get(self, route, target=GEO_TARGET, host=GEO_HOST, extra=''):
        channel = self.channel(route, host)
        try:
            channel.sendall(('GET '+target+' HTTP/1.1\r\nHost: '+host+'\r\n'+extra+'\r\n').encode())
            raw = b''
            while True:
                value = channel.recv(65536)
                if not value:
                    break
                raw += value
                self.assertLessEqual(len(raw), 262144)
            return raw.partition(b'\r\n\r\n')
        finally:
            channel.close()

    def test_three_real_tls_transports_and_route_specific_responses(self):
        for route in ROUTES:
            with self.subTest(route=route):
                head, separator, body = self.get(route)
                self.assertTrue(head.startswith(b'HTTP/1.1 200 '))
                self.assertEqual(separator, b'\r\n\r\n')
                self.assertEqual(json.loads(body), dict(success=True, ip=ROUTES[route]['ip'],
                    timezone={'id': ROUTES[route]['zoneId']}))
                row = self.fleet.snapshot()['events'][-1]
                self.assertTrue(row['tls'] and row['responseWritten'])
                self.assertEqual(row['responseSha256'], hashlib.sha256(body).hexdigest())
                self.assertEqual(row['proxyTls'], route == 'https')
                self.assertEqual(row['targetSni'], GEO_HOST)
                self.assertFalse(row['credentialsPresent'])
        self.assertEqual(self.fleet.snapshot()['upstreamConnections'], 0)

    def test_fixed_source_exact_query_credentials_and_no_upstream(self):
        for target, extra in ((GEO_TARGET+'&secret=x',''), ('/',''),
                (GEO_TARGET,'Authorization: secret\r\n'), (GEO_TARGET,'Cookie: secret\r\n')):
            with self.subTest(target=target, extra=bool(extra)):
                _, _, body = self.get('http', target, extra=extra)
                self.assertEqual(body, b'')
        self.assertEqual(self.fleet.snapshot()['events'], [])
        self.assertEqual(self.fleet.snapshot()['upstreamConnections'], 0)

    def test_actual_socks_remote_dns_rejects_numeric_atyp_and_port(self):
        for atyp, port in ((1,443),(3,80)):
            with self.subTest(atyp=atyp,port=port):
                with self.assertRaises((ValueError,OSError)):
                    self.channel('socks', socks_type=atyp, port=port)
        self.assertFalse(self.fleet.snapshot()['events'])

    def test_connect_rejects_other_target_and_bad_tls_name(self):
        with self.assertRaises((ValueError,OSError)):
            self.channel('http', host='example.invalid')
        raw = socket.create_connection(('127.0.0.1', self.fleet.proxies['https'].port), timeout=5)
        with self.assertRaises(ssl.SSLCertVerificationError):
            self.ctx.wrap_socket(raw, server_hostname='example.invalid')
        raw.close()
        self.assertFalse(self.fleet.snapshot()['events'])

    def test_hold_release_retains_original_request_sequence(self):
        self.command('stage', case='cancel-late')
        self.command('behavior', route='http', behavior='hold')
        with concurrent.futures.ThreadPoolExecutor(1) as pool:
            future = pool.submit(self.get, 'http')
            # Condition-based synchronization, no invented native receipt.
            for _ in range(250):
                if self.fleet.snapshot()['events']:
                    break
                threading.Event().wait(.01)
            row = self.fleet.snapshot()['events'][0]
            self.assertEqual(row['sequence'], 1)
            self.assertFalse(row['responseWritten'])
            self.assertFalse(future.done())
            self.command('release', route='http')
            self.assertTrue(future.result(timeout=5)[0].startswith(b'HTTP/1.1 200 '))
        self.assertEqual(self.fleet.snapshot()['events'][0]['case'], 'cancel-late')

    def test_redirect_and_invalid_are_explicit_fixture_failures(self):
        self.command('behavior', route='http', behavior='redirect')
        head, _, body = self.get('http')
        self.assertTrue(head.startswith(b'HTTP/1.1 302 '))
        self.assertIn(b'Location: https://fp-a.pocketchat.test/forbidden-geo-redirect', head)
        self.command('behavior', route='http', behavior='invalid')
        head, _, body = self.get('http')
        self.assertEqual(json.loads(body)['timezone']['id'], 'Invalid/ControlledFixtureZone')

    def test_content_real_tls_same_server_no_geo_fabrication(self):
        head, _, body = self.get('socks', '/env-policy?phase=gecko-new-york', HOSTS[0])
        self.assertTrue(head.startswith(b'HTTP/1.1 200 '))
        self.assertIn(b'const x=', body)
        self.assertIn(self.binding['runNonce'].encode(), body)
        self.assertEqual(self.fleet.snapshot()['events'][-1]['kind'], 'content')
        self.assertTrue(all(row['kind'] != 'geo' for row in self.fleet.snapshot()['events']))

    def test_control_real_http_rejects_duplicate_wrong_nonce_and_extra(self):
        host, port = self.fleet.control_server.server_address
        for value in (b'{"sourceCommit":"'+b'a'*40+b'","runNonce":"'+b'c'*32+b'","action":"snapshot","action":"stage"}',
                      json.dumps(dict(self.binding, action='snapshot')).encode(),
                      json.dumps(dict(sourceCommit='a'*40,runNonce='e'*32,action='snapshot')).encode()):
            connection = http.client.HTTPConnection(host,port,timeout=5)
            connection.request('POST','/__ip-control',value,{'Content-Type':'application/json'})
            response = connection.getresponse()
            self.assertEqual(response.status,400)
            response.read();connection.close()

    def test_control_polling_does_not_consume_native_bound(self):
        for _ in range(520):
            self.command('snapshot')
        self.assertEqual(self.fleet.snapshot()['events'], [])
        self.assertEqual(self.fleet.snapshot()['controlRequests'], 520)
        self.get('http')
        self.assertEqual(len(self.fleet.snapshot()['events']), 1)

    def test_no_certificates_private_paths_or_credentials_in_snapshot(self):
        self.get('https')
        raw = json.dumps(self.fleet.snapshot())
        for secret in ('PRIVATE KEY','BEGIN CERTIFICATE','/tmp/','secret','Authorization','Cookie'):
            self.assertNotIn(secret, raw)
        self.assertTrue(self.fleet.snapshot()['syntheticGeoService'])
        self.assertFalse(self.fleet.snapshot()['actualPublicIpGeolocationVerified'])
        self.assertFalse(self.fleet.snapshot()['productionEndpointOverride'])


if __name__ == '__main__':
    unittest.main()
