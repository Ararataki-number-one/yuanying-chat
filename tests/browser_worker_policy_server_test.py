"""Real host TLS/closed proxy tests; no Android execution or private-key artifact."""
from pathlib import Path
import json
import shlex
import socket
import ssl
import subprocess
import sys
import threading
import time
import unittest

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'tools/browser'))
import fingerprint_fixture_server as original
import newworker_fixture_server as host
import run_worker_policy_integration as runner

BINDING=dict(sourceCommit='a'*40,sourceTree='b'*40,runNonce='c'*32,integrationApkSha256='d'*64,sdkRunId='123',sdkRunAttempt=1)
DOCUMENT='00000000-0000-0000-0000-000000000001'

def response(connection):
    data=bytearray()
    while not data.endswith(b'\r\n\r\n'):
        value=connection.recv(1)
        if not value:raise ValueError('Synthetic response incomplete')
        data+=value
    length=int(next(line.split(b':',1)[1] for line in data.split(b'\r\n') if line.lower().startswith(b'content-length:')));body=bytearray()
    while len(body)<length:body+=connection.recv(length-len(body))
    return bytes(data),bytes(body)

class WorkerHostTlsTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):cls.certificates=original.EphemeralCertificates()
    @classmethod
    def tearDownClass(cls):cls.certificates.close()
    def setUp(self):self.server=host.WorkerFixtureServer(self.certificates,(ROOT/'tests/gecko/assets/worker-policy-page.js').read_text(),BINDING).start();self.server.begin('chromium')
    def tearDown(self):self.server.close()
    def tls(self,hostname=None,trusted=True,target=original.HOSTS[0]):
        stream=socket.create_connection(('127.0.0.1',self.server.port),timeout=3);stream.sendall(('CONNECT '+target+':443 HTTP/1.1\r\nHost: '+target+':443\r\n\r\n').encode());head=b''
        while not head.endswith(b'\r\n\r\n'):head+=stream.recv(1)
        self.assertEqual(head,b'HTTP/1.1 200 Connection Established\r\n\r\n');context=ssl.create_default_context(cafile=self.certificates.ca) if trusted else ssl.create_default_context()
        try:return context.wrap_socket(stream,server_hostname=hostname or target)
        except BaseException:stream.close();raise
    def idle(self):
        until=time.monotonic()+3
        while time.monotonic()<until:
            with self.server._lock:
                if not self.server._clients:return
            time.sleep(.01)
        self.fail('Host connection did not finish')
    def get(self,path,authority=original.HOSTS[0]):
        with self.tls(target=authority) as connection:
            self.assertEqual(original.digest(connection.getpeercert(binary_form=True)),self.certificates.leaf_sha)
            connection.sendall(('GET '+path+' HTTP/1.1\r\nHost: '+authority+'\r\nUser-Agent: real-controlled-UA\r\nSec-CH-UA-Mobile: ?1\r\nCookie: must-not-export\r\nAuthorization: must-not-export\r\n\r\n').encode());return response(connection)
    def test_actual_tls_realm_phase_document_and_allowlisted_native_headers(self):
        header,body=self.get('/worker-probe?phase=allow&realm=dedicated-classic&documentId='+DOCUMENT);self.assertEqual(body,b'worker-network-synthetic-v1');self.assertIn(b'Accept-CH:',header);self.idle()
        value=self.server.snapshot('chromium');row=value['requests'][0]
        self.assertEqual(value['binding'],BINDING);self.assertEqual(row,dict(origin='https://fp-a.pocketchat.test',path='/worker-probe',tls=True,method='GET',phase='allow',realm='dedicated-classic',documentId=DOCUMENT,**{'user-agent':'real-controlled-UA','sec-ch-ua-mobile':'?1'}));self.assertNotIn('must-not-export',json.dumps(value));self.assertEqual(value['upstreamConnections'],0)
    def test_actual_chain_and_hostname_validation_cannot_be_bypassed(self):
        with self.assertRaises(ssl.SSLCertVerificationError):self.tls(trusted=False)
        with self.assertRaises(ssl.SSLCertVerificationError):self.tls(hostname='fp-c.pocketchat.test')
        self.idle();self.assertEqual(self.server.snapshot('chromium')['accepted'],0)
    def test_unknown_duplicated_or_cross_realm_queries_are_refused(self):
        paths=['/unknown?phase=allow','/worker-probe?phase=old&realm=dedicated-classic&documentId='+DOCUMENT,'/worker-probe?phase=allow&phase=restrict&realm=dedicated-classic&documentId='+DOCUMENT,'/module.js?phase=allow&realm=shared-worker&documentId='+DOCUMENT,'/worker-probe?phase=restrict&realm=dedicated-classic&documentId=bad','/worker-document?phase=allow&extra=1']
        for path in paths:
            with self.subTest(path=path),self.tls() as connection:
                connection.sendall(('GET '+path+' HTTP/1.1\r\nHost: '+original.HOSTS[0]+'\r\n\r\n').encode());self.assertEqual(connection.recv(1),b'')
        self.idle();self.assertEqual(self.server.snapshot('chromium')['accepted'],0)
    def test_document_script_and_worker_scripts_are_real_separate_resources(self):
        _,page=self.get('/worker-document?phase=allow');self.assertIn(b'firstInline: true',page);self.assertNotIn(host.TOKEN.encode(),page);self.assertIn(('https://'+original.HOSTS[1]+'/worker-frame?phase=allow').encode(),page)
        for path,realm in [('/dedicated.js','dedicated-classic'),('/module.js','dedicated-module'),('/shared.js','shared-worker'),('/service.js','service-worker')]:
            header,body=self.get(path+'?phase=restore&realm='+realm+'&documentId='+DOCUMENT);self.assertIn(b'text/javascript',header);self.assertIn(b'networkAllowed',body);self.assertIn(b'navigator.userAgent',body)
            checked=subprocess.run(['node','--check','--input-type=module' if path=='/module.js' else '--input-type=commonjs'],input=body,capture_output=True,timeout=10);self.assertEqual(checked.returncode,0,checked.stderr.decode())
        self.assertEqual(original.PATHS,('/document','/frame','/hints','/worker.js','/favicon.ico'))
    def test_engine_receipt_epoch_is_fresh_and_gecko_can_capture_ordinary_http_headers(self):
        self.get('/worker-probe?phase=allow&realm=dedicated-classic&documentId='+DOCUMENT);self.idle();self.server.begin('gecko')
        with socket.create_connection(('127.0.0.1',self.server.port),timeout=3) as connection:
            connection.sendall(('GET http://'+original.HOSTS[0]+'/worker-probe?phase=gecko-native&realm=dedicated-classic&documentId='+DOCUMENT+' HTTP/1.1\r\nHost: '+original.HOSTS[0]+'\r\nUser-Agent: actual-Gecko-observation-placeholder\r\n\r\n').encode());_,body=response(connection);self.assertEqual(body,b'worker-network-synthetic-v1')
        self.idle();self.assertEqual(self.server.snapshot('chromium')['accepted'],1);gecko=self.server.snapshot('gecko');self.assertEqual(gecko['accepted'],1);self.assertFalse(gecko['requests'][0]['tls']);self.assertEqual(gecko['requests'][0]['phase'],'gecko-native')
    def test_runner_uses_one_quoted_shell_command_and_only_public_binding(self):
        command=runner.activity_start_args('c'*32,'a'*40,'e'*64,'f'*64);self.assertEqual(len(command),2);tokens=shlex.split(command[1]);self.assertEqual(tokens[:5],['am','start','-W','-n','local.pocketchat.test/local.pocketchat.WorkerPolicyIntegrationActivity']);self.assertNotIn('.key',' '.join(tokens));self.assertIn('expectedLeafSha256',tokens)
        for values in [('bad','a'*40,'e'*64,'f'*64),('c'*32,'bad','e'*64,'f'*64),('c'*32,'a'*40,'bad','f'*64)]:
            with self.assertRaises(ValueError):runner.activity_start_args(*values)
    def test_gecko_coop_is_a_real_header_only_on_its_owned_top_document_phase(self):
        self.server.begin('gecko');header,body=self.get('/env-policy?phase=gecko-coop',original.HOSTS[1]);self.assertIn(b'Cross-Origin-Opener-Policy: same-origin\r\n',header);self.assertIn(b'https://fp-a.pocketchat.test/env-frame?phase=gecko-coop',body);self.assertIn(b'https://fp-b.pocketchat.test/env-frame?phase=gecko-coop',body)
        self.assertIn(b"<form><textarea id='gecko-policy-draft' name='geckoPolicyDraft'></textarea></form>",body)
        self.idle();self.assertEqual(self.server.snapshot('gecko')['requests'][0]['responseCoop'],'same-origin')
        for path in ('/env-frame?phase=gecko-coop','/env-policy?phase=gecko-reload','/worker-document?phase=allow'):
            header,page=self.get(path);self.assertNotIn(b'Cross-Origin-Opener-Policy',header)
            if not path.startswith('/env-policy'):self.assertNotIn(b'id=\'gecko-policy-draft\'',page)
        self.idle();self.assertTrue(all('responseCoop' not in row for row in self.server.snapshot('gecko')['requests'][1:]))
    def test_coop_receipt_cannot_precede_or_survive_a_failed_socket_write(self):
        self.server.begin('gecko');sent=[]
        class RefusingSocket:
            def sendall(inner,data):
                snapshot=self.server.snapshot('gecko');self.assertNotIn('responseCoop',snapshot['requests'][-1]);sent.append(data);raise OSError('Controlled response socket refused')
        with self.assertRaises(OSError):self.server._respond(RefusingSocket(),'gecko',original.HOSTS[0],True,'GET','/env-policy?phase=gecko-coop',{'host':original.HOSTS[0],'user-agent':'controlled-native-UA'})
        self.assertIn(b'Cross-Origin-Opener-Policy: same-origin\r\n',sent[0]);self.assertNotIn('responseCoop',self.server.snapshot('gecko')['requests'][-1])
    def test_timezone_measurement_is_read_from_real_native_date_and_intl(self):
        ran=subprocess.run(['node','-e',host.TIMEZONE_SOURCE+'console.log(JSON.stringify(nativeZone()))'],capture_output=True,text=True,timeout=10);self.assertEqual(ran.returncode,0,ran.stderr);value=json.loads(ran.stdout);self.assertTrue(value['timeZone']);self.assertEqual(value['january']['month'],1);self.assertEqual(value['july']['month'],7);self.assertEqual(value['january']['year'],2026);self.assertIsInstance(value['january']['offsetMinutes'],int)
    def blocked_writer(self):
        entered,release=threading.Event(),threading.Event()
        def work():
            entered.set();release.wait()
            try:
                with self.server._lock:
                    row=self.server.rows['chromium'];row['requests'].append({'phase':'restrict','realm':'dedicated-classic','path':'/worker-probe'});row['accepted']+=1
            finally:
                with self.server._lock:self.server._threads.discard(threading.current_thread())
        worker=threading.Thread(target=work,daemon=True)
        with self.server._lock:self.server._threads.add(worker)
        worker.start();self.assertTrue(entered.wait(2),'Controlled host writer did not start')
        return worker,release
    def test_close_rejects_a_real_blocked_late_writer_before_final_snapshot(self):
        worker,release=self.blocked_writer()
        try:
            with self.assertRaisesRegex(ValueError,'did not quiesce'):self.server.close()
            self.assertTrue(worker.is_alive());self.assertEqual(self.server.snapshot('chromium')['accepted'],0)
        finally:release.set();worker.join(2)
        self.assertFalse(worker.is_alive());self.server.close();self.assertEqual(self.server.snapshot('chromium')['accepted'],1)
    def test_legacy_close_is_an_explicit_negative_control_for_the_live_writer(self):
        worker,release=self.blocked_writer()
        try:
            # The unchanged old server returns after its bounded join although
            # this actual thread can still append a restricted request later.
            original.FingerprintServer.close(self.server)
            self.assertTrue(worker.is_alive());self.assertEqual(self.server.snapshot('chromium')['accepted'],0)
            with self.assertRaisesRegex(ValueError,'did not quiesce'):self.server.close()
        finally:release.set();worker.join(2)
        self.assertFalse(worker.is_alive());self.assertEqual(self.server.snapshot('chromium')['accepted'],1)

if __name__=='__main__':unittest.main(verbosity=2)
