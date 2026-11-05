"""Actual host TLS/proxy and controlled adb-boundary tests; no Android execution claim."""
import importlib.util
from pathlib import Path
import socket
import ssl
import subprocess
import sys
import time
from types import SimpleNamespace
import unittest

ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('ephemeral_fingerprint_server',ROOT/'tools/browser/fingerprint_fixture_server.py');host=importlib.util.module_from_spec(spec);spec.loader.exec_module(host)
BINDING=dict(sourceCommit='a'*40,sourceTree='b'*40,runNonce='c'*32,integrationApkSha256='d'*64,sdkRunId='123',sdkRunAttempt=1)


def response(connection):
    data=bytearray()
    while not data.endswith(b'\r\n\r\n'):
        value=connection.recv(1)
        if not value:raise ValueError('Incomplete host response')
        data+=value
    length=int(next(line.split(b':',1)[1] for line in data.split(b'\r\n') if line.lower().startswith(b'content-length:')))
    body=bytearray()
    while len(body)<length:
        value=connection.recv(length-len(body))
        if not value:raise ValueError('Truncated host response')
        body+=value
    return bytes(data),bytes(body)


def refused(connection):
    try:return connection.recv(1)==b''
    except ConnectionResetError:return True


class EphemeralHostTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):cls.certificates=host.EphemeralCertificates()
    @classmethod
    def tearDownClass(cls):cls.certificates.close()
    def setUp(self):self.server=host.FingerprintServer(self.certificates,'window.__synthetic=true;',BINDING).start();self.server.begin('chromium')
    def tearDown(self):self.server.close()
    def connect(self):
        connection=socket.create_connection(('127.0.0.1',self.server.port),timeout=3);connection.settimeout(3);return connection
    def tls(self,context=None,hostname=host.HOSTS[0]):
        connection=self.connect();connection.sendall(('CONNECT '+host.HOSTS[0]+':443 HTTP/1.1\r\nHost: '+host.HOSTS[0]+':443\r\n\r\n').encode());data=b''
        while not data.endswith(b'\r\n\r\n'):data+=connection.recv(1)
        self.assertEqual(data,b'HTTP/1.1 200 Connection Established\r\n\r\n')
        context=context or ssl.create_default_context(cafile=self.certificates.ca)
        try:return context.wrap_socket(connection,server_hostname=hostname)
        except BaseException:connection.close();raise
    def wait_idle(self):
        until=time.monotonic()+3
        while time.monotonic()<until:
            with self.server._lock:
                if not self.server._clients:return
            time.sleep(.01)
        self.fail('Host clients did not close')

    def test_actual_native_host_tls_validates_exact_leaf_and_captures_only_headers(self):
        with self.tls() as connection:
            self.assertEqual(host.digest(connection.getpeercert(binary_form=True)),self.certificates.leaf_sha)
            self.assertEqual(connection.getpeercert()['subjectAltName'],(('DNS',host.HOSTS[0]),('DNS',host.HOSTS[1])))
            connection.sendall(('GET /hints HTTP/1.1\r\nHost: '+host.HOSTS[0]+'\r\nUser-Agent: synthetic-UA\r\nSec-CH-UA-Mobile: ?1\r\nCookie: forbidden-report-content\r\nAuthorization: forbidden-report-credential\r\n\r\n').encode())
            header,body=response(connection);self.assertIn(b'Accept-CH:',header);self.assertEqual(body,b'{"synthetic":true}')
        self.wait_idle();snapshot=self.server.snapshot('chromium');self.assertEqual(snapshot['binding'],BINDING);self.assertEqual(snapshot['tlsConnections'],1);self.assertEqual(snapshot['accepted'],1)
        self.assertEqual(snapshot['requests'],[{'origin':'https://'+host.HOSTS[0],'path':'/hints','tls':True,'method':'GET','user-agent':'synthetic-UA','sec-ch-ua-mobile':'?1'}]);self.assertNotIn('forbidden',str(snapshot));self.assertEqual(snapshot['upstreamConnections'],0)

    def test_actual_tls_rejects_untrusted_ca_and_wrong_hostname(self):
        with self.assertRaises(ssl.SSLCertVerificationError):self.tls(ssl.create_default_context())
        with self.assertRaises(ssl.SSLCertVerificationError):self.tls(hostname='fp-c.pocketchat.test')
        self.wait_idle();self.assertEqual(self.server.snapshot('chromium')['accepted'],0)

    def test_restricted_proxy_rejects_nonfixture_hosts_paths_methods_duplicate_authority_and_bodies(self):
        packets=[b'CONNECT example.com:443 HTTP/1.1\r\nHost: example.com:443\r\n\r\n',('GET http://'+host.HOSTS[0]+'/other HTTP/1.1\r\nHost: '+host.HOSTS[0]+'\r\n\r\n').encode(),('POST http://'+host.HOSTS[0]+'/hints HTTP/1.1\r\nHost: '+host.HOSTS[0]+'\r\n\r\n').encode(),('GET http://'+host.HOSTS[0]+'/hints HTTP/1.1\r\nHost: '+host.HOSTS[1]+'\r\n\r\n').encode(),('GET http://'+host.HOSTS[0]+'/hints HTTP/1.1\r\nHost: '+host.HOSTS[0]+'\r\nHost: '+host.HOSTS[0]+'\r\n\r\n').encode(),('GET http://'+host.HOSTS[0]+'/hints HTTP/1.1\r\nHost: '+host.HOSTS[0]+'\r\nContent-Length: 1\r\n\r\nx').encode()]
        for packet in packets:
            with self.subTest(packet=packet),self.connect() as connection:connection.sendall(packet);self.assertTrue(refused(connection))
        self.wait_idle();self.assertEqual(self.server.snapshot('chromium')['accepted'],0);self.assertEqual(self.server.snapshot('chromium')['rejected'],len(packets))

    def test_per_engine_counts_and_control_receipts_cannot_carry_chromium_success_into_gecko(self):
        with self.connect() as connection:
            connection.sendall(('GET http://'+host.HOSTS[0]+'/document HTTP/1.1\r\nHost: '+host.HOSTS[0]+'\r\n\r\n').encode());_,body=response(connection);self.assertIn(b'<script>window.__synthetic=true;</script>',body)
        self.wait_idle();self.server.begin('gecko');self.assertEqual(self.server.snapshot('gecko')['accepted'],0);self.assertEqual(self.server.snapshot('chromium')['accepted'],1)
        for source,nonce in [('f'*40,BINDING['runNonce']),(BINDING['sourceCommit'],'e'*32)]:
            with self.connect() as connection:
                connection.sendall(('GET /__evidence?engine=gecko&nonce='+nonce+'&source='+source+' HTTP/1.1\r\nHost: 127.0.0.1:18765\r\n\r\n').encode());self.assertEqual(connection.recv(1),b'')
        with self.connect() as connection:
            connection.sendall(('GET /__evidence?engine=gecko&nonce='+BINDING['runNonce']+'&source='+BINDING['sourceCommit']+' HTTP/1.1\r\nHost: 127.0.0.1:18765\r\n\r\n').encode());_,body=response(connection);self.assertIn(b'"engine":"gecko"',body);self.assertIn(b'"accepted":0',body)

    def test_ephemeral_private_material_is_under_tmp_only_and_is_destroyed(self):
        directory=self.certificates.directory;self.assertTrue(directory.is_relative_to('/tmp'));self.assertFalse(directory.is_relative_to(ROOT));self.assertEqual(directory.stat().st_mode&0o777,0o700)
        self.assertTrue(all(p.stat().st_mode&0o777==0o600 for p in directory.iterdir()));self.assertFalse(self.certificates.public['privateMaterialExported']);self.assertNotIn('BEGIN',str(self.certificates.public));self.assertNotIn(str(directory),str(self.certificates.public))
        with host.EphemeralCertificates() as second:
            generated=second.directory;self.assertNotEqual(second.ca_sha,self.certificates.ca_sha);self.assertNotEqual(second.leaf_sha,self.certificates.leaf_sha)
        self.assertFalse(generated.exists())

    def test_header_reader_preserves_tls_bytes_and_refuses_oversized_headers(self):
        left,right=socket.socketpair()
        try:
            right.sendall(b'CONNECT fp-a.pocketchat.test:443 HTTP/1.1\r\nHost: fp-a.pocketchat.test:443\r\n\r\n\x16\x03\x01')
            self.assertEqual(host.read_header(left)[0],'CONNECT');self.assertEqual(left.recv(3),b'\x16\x03\x01')
        finally:left.close();right.close()
        left,right=socket.socketpair()
        try:
            right.sendall(b'GET / HTTP/1.1\r\nX: '+b'x'*host.HEADER_LIMIT+b'\r\n\r\n')
            with self.assertRaises(ValueError):host.read_header(left)
        finally:left.close();right.close()


class ControlledAdb:
    def __init__(self,certificates,fault=''):self.certificates=certificates;self.fault=fault;self.calls=[];self.present=False
    def __call__(self,*args,check=True,timeout=30):
        self.calls.append(args);code=0;out=b''
        if args==('shell','getprop','ro.kernel.qemu'):out=b'1\n'
        elif args==('shell','id','-u'):out=b'2000\n' if self.fault=='root' else b'0\n'
        elif args==('shell','am','get-current-user'):out=b'1\n' if self.fault=='user' else b'0\n'
        elif args==('shell','getenforce'):out=b'Permissive\n' if self.fault=='selinux' else b'Enforcing\n'
        elif args[:3]==('shell','test','-e'):code=0 if self.present or self.fault=='collision' else 1
        elif args[0]=='push':self.present=True
        elif args[:2]==('exec-out','cat'):code=0 if self.present else 1;out=(b'changed' if self.fault=='bytes' else self.certificates.ca_bytes) if self.present else b''
        elif args[:3]==('shell','stat','-c'):out=b'600:0:0\n' if self.fault=='mode' else b'644:1000:1000\n'
        elif args[:3]==('shell','ls','-Zd'):out=b'u:object_r:unlabeled:s0 path\n' if self.fault=='label' else b'u:object_r:usercacerts_file:s0 path\n'
        elif args[:2]==('shell','rm'):self.present=False
        if check and code:raise subprocess.CalledProcessError(code,args)
        return SimpleNamespace(returncode=code,stdout=out,stderr=b'')


class UserCaInstallationBoundaryTests(unittest.TestCase):
    def setUp(self):self.certificates=SimpleNamespace(subject_hash='1234abcd',ca=Path('/tmp/public-ca.pem'),ca_bytes=b'PUBLIC CA certificate only',ca_sha='e'*64,leaf_sha='f'*64)
    def test_exact_public_ca_only_is_installed_read_back_and_removed(self):
        adb=ControlledAdb(self.certificates);installer=host.AndroidUserCa(adb,self.certificates);receipt=installer.install();self.assertTrue(receipt['installedPublicCaBytesMatch']);self.assertFalse(receipt['removedAfterExecution']);installer.remove();self.assertTrue(receipt['removedAfterExecution']);self.assertFalse(adb.present)
        self.assertEqual([a for a in adb.calls if a[0]=='push'],[('push','/tmp/public-ca.pem','/data/misc/user/0/cacerts-added/1234abcd.0')]);self.assertFalse(any('.key' in str(a) for a in adb.calls))
        self.assertIn(('shell','am','force-stop','local.pocketchat.test'),adb.calls)
    def test_root_user_selinux_collision_readback_mode_and_context_fail_closed(self):
        for fault in ('root','user','selinux','collision','bytes','mode','label'):
            with self.subTest(fault=fault):
                adb=ControlledAdb(self.certificates,fault);installer=host.AndroidUserCa(adb,self.certificates)
                with self.assertRaises(ValueError):installer.install()
                self.assertFalse(installer.receipt)
                if fault in ('root','user','selinux','collision'):self.assertFalse(any(a[0]=='push' for a in adb.calls))
    def test_cleanup_refuses_to_remove_changed_or_preexisting_certificate(self):
        adb=ControlledAdb(self.certificates);installer=host.AndroidUserCa(adb,self.certificates);installer.install();adb.fault='bytes'
        with self.assertRaises(ValueError):installer.remove()
        self.assertTrue(adb.present);self.assertFalse(any(a[:2]==('shell','rm') for a in adb.calls))


if __name__=='__main__':unittest.main(verbosity=2)
