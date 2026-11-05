#!/usr/bin/env python3
"""Host-only actual OpenSSL transport + explicit modeled device/checker refusal controls."""
import argparse
import ast
import copy
import hashlib
import io
import json
import os
from pathlib import Path
import socket
import ssl
import subprocess
import sys
import tempfile
import time
import unittest
from unittest.mock import patch
import yaml
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'tests'));sys.path.insert(0,str(ROOT/'tools/gecko'));sys.path.insert(0,str(ROOT/'tools/browser'))
from tls_product_test_support import HostModelEvidence,model_device,model_identity,request,SOURCE,TREE,RUN
from tls_acceptance_server import CASE_SPECS,HOST,GUEST_PORT,TlsAcceptanceServer,strict_json,read_application_header
import tls_acceptance_contract as contract
import check_gecko_tls_evidence as checker
import run_gecko_tls_acceptance as runner
from check_gecko_tls_package import components,TEST_CLASSES,PRODUCTION_CLASSES,ASSETS
from fingerprint_fixture_server import EphemeralCertificates
NEGATIVE_CONTROLS=[]
SEMANTIC_MUTANTS=[]

class ProductTlsControls(unittest.TestCase):
    @classmethod
    def setUpClass(cls):cls.evidence=HostModelEvidence()
    def verify(self,directory):
        def same(actual,expected):self.assertEqual(actual,expected)
        def reader(source,path):self.assertEqual(source,SOURCE);return (ROOT/path).read_bytes()
        with patch.object(checker,'verify_installed',side_effect=same):return checker.verify_gecko_tls_evidence(directory,SOURCE,self.evidence.identity,reader=reader)
    def device(self,index=0):return copy.deepcopy(self.evidence.entries[index]['device'])
    def validate(self,value,index=0):
        entry=self.evidence.entries[index]
        with patch.object(contract,'verify_installed',side_effect=lambda actual,expected:self.assertEqual(actual,expected)):
            return contract.validate_device(value,spec=CASE_SPECS[index],binding=entry['binding'],run=RUN,source=SOURCE,tree=TREE,identity=self.evidence.identity,leaf=self.evidence.leaf)
    def rejected(self,name,call):
        with self.subTest(name=name):
            with self.assertRaises((ValueError,AssertionError,KeyError,TypeError)):call()
            NEGATIVE_CONTROLS.append(name)
    def test_real_host_openssl_versions_originals_and_bounded_cleanup(self):
        host=self.evidence.host
        self.assertTrue(host['serverClosed'] and host['serverThreadsJoined']);self.assertEqual(host['upstreamConnections'],0)
        self.assertFalse(host['recordsOverflow']);self.assertEqual(len(self.evidence.wire['cases']),11)
        self.assertGreaterEqual(self.evidence.wire['uniqueClientRandoms'],11)
        for name in ('strict-tls12','pending-default-tls12','concurrent-strict-resample-tls12'):self.assertTrue(self.evidence.wire['cases'][name]['protocolRejected'])
        self.assertFalse(self.evidence.wire['rawFatalAlertPacketDecoded']);self.assertFalse(self.evidence.wire['quicWireVerified'])
    def test_all_actual_selected_device_methods_on_explicit_model_packets(self):
        for i,entry in enumerate(self.evidence.entries):self.assertEqual(self.validate(self.device(i),i),entry['finding'])
    def test_native_ack_and_false_progress_cannot_replace_owned_native_evidence(self):
        changes={
         'unknown private field':lambda v:v.update(rawPrivate='/do-not-export'),
         'old source':lambda v:v.update(sourceCommit='f'*40),'old nonce':lambda v:v.update(caseNonce='f'*32),
         'boolean schema':lambda v:v.update(schema=True),'boolean slot':lambda v:v.update(slot=True),
         'missing title':lambda v:v['navigation'].update(titleMatched=False),'missing location':lambda v:v['navigation'].update(targetLocation=False),
         'only URL-less stop':lambda v:v['navigation'].update(nativeStopOwnershipVerified=True),'invent security URL':lambda v:v['navigation'].update(nativeSecurityUrlOwnershipVerified=True),
         'missing native admission':lambda v:v['navigation'].update(productionAdmissionReady=False),
         'no original admitted request':lambda v:v['nativeEvents'][0].update(admissionReady=False),
         'wrong native cert':lambda v:v['security'].update(leafSha256='f'*64),'certificate exception':lambda v:v['security'].update(isException=True),
         'TLS is wire proof':lambda v:v.update(nativeSettingReadbackIsWireProof=True),'whole-app stack claim':lambda v:v['tlsPolicy'].update(proxyEntranceTlsCovered=True),
         'JS TLS override':lambda v:v.update(javascriptTlsOverrideUsed=True),'debug endpoint':lambda v:v.update(debuggingEndpointUsed=True),
         'native unconfirmed':lambda v:v['tlsPolicy'].update(nativeSettingReadback=False),'USER retained':lambda v:v['tlsPolicy'].update(hasUserMin=True),
         'RFP null':lambda v:v['tlsPolicy'].update(rfpPriority=None),'H2 disabled':lambda v:v['tlsPolicy'].update(h2Enabled=False),
         'boolean min':lambda v:v['tlsPolicy'].update(configuredMin=True),'string min':lambda v:v['tlsPolicy'].update(configuredMin='3'),
         'obsolete default':lambda v:v['tlsPolicy'].update(defaultMin=2,configuredMin=2),
         'DEFAULT differs':lambda v:v['tlsPolicy'].update(defaultMin=4),'unknown mode':lambda v:v['tlsPolicy'].update(activeBootMode='future'),
         'wrong PID':lambda v:v['tlsPolicy'].update(pid=999),'wrong UUID':lambda v:v['tlsPolicy'].update(environmentId='other'),
         'native scope changed':lambda v:v['tlsPolicy'].update(connectionScope='whole-app'),
         'owned path link':lambda v:v['storagePathEvidence'].update(privateComponentsNoSymlinks=False),
         'post-native profile oracle':lambda v:v['startupPreparation'].update(scope='runtime-file-snapshot'),
         'nonowned profile bytes changed':lambda v:v['startupPreparation'].update(nonTlsPrefsAfterSha256='f'*64),
         'closed CPU config weakened':lambda v:v['startupPreparation'].update(closedRouteConfigPrefixPreserved=False),
         'unverified service coverage':lambda v:v.update(serviceWorkerCoverageVerified=True),
         'old installed APK':lambda v:v['buildIdentity'].update(apkSha256='f'*64)}
        for name,change in changes.items():
            value=self.device();change(value);self.rejected(name,lambda value=value:self.validate(value))
    def test_protocol_rejection_is_real_uri_error_not_timeout_or_bad_certificate(self):
        for key,bad in (('errorCategory',0),('errorCode',0),('nativeErrorUrlMatched',False),('titleMatched',True)):
            value=self.device(1);value['navigation'][key]=bad;self.rejected('strict native '+key,lambda value=value:self.validate(value,1))
        value=self.device(1);value['tlsPolicy'].update(defaultMin=3,configuredMin=3);self.rejected('strict native leaked TLS12',lambda:self.validate(value,1))
        for reason in ('TLSV1_ALERT_UNKNOWN_CA','OTHER_SSL_ERROR','TimeoutError'):
            host=copy.deepcopy(self.evidence.host)
            row=next(r for r in host['records'] if r['destinationPort']==self.evidence.entries[1]['binding']['port']);row['tlsErrorReason']=reason
            self.rejected('strict peer '+reason,lambda host=host:contract.validate_wire(host,self.evidence.entries,run=RUN,source=SOURCE))
    def test_wire_is_reparsed_from_original_bytes_and_cannot_be_missing_or_replayed(self):
        for name,mutate in {
          'missing originals':lambda h:h['records'].clear(),
          'native ACK without HTTP':lambda h:h['records'][0].update(httpReceived=False),
          'wrong actual protocol':lambda h:h['records'][0].update(negotiatedVersion='TLSv1.3'),
          'resume':lambda h:h['records'][0].update(sessionReused=True),
          'parsed fields not raw':lambda h:h['records'][0]['clientHello'].update(supportedVersions=[772]),
          'raw hex differs':lambda h:h['records'][0]['clientHello'].update(clientHelloHandshakeHex=h['records'][0]['clientHello']['clientHelloHandshakeHex'][:-2]+'ff'),
          'duplicate random':lambda h:h['records'][1].update(clientHello=copy.deepcopy(h['records'][0]['clientHello'])),
          'late sockets not joined':lambda h:h.update(serverThreadsJoined=False),
          'truncated records':lambda h:h.update(recordsOverflow=True),
          'forwarded request':lambda h:h.update(upstreamConnections=1),
          'invent alert decode':lambda h:h.update(rawFatalAlertPacketDecoded=True)}.items():
            host=copy.deepcopy(self.evidence.host);mutate(host);self.rejected(name,lambda host=host:contract.validate_wire(host,self.evidence.entries,run=RUN,source=SOURCE))
    def test_ui_save_itself_cannot_restart_navigate_or_mutate_pending_work(self):
        for key,bad in (('runtimeNonce','f'*32),('pid',999),('navigationEpoch',999),('connectionEpoch',999),('urlSha256','f'*64),('pendingSha256','f'*64),('loadCalls',999),('operation',True)):
            value=self.device(3);value['uiAfter'][key]=bad;self.rejected('UI changed '+key,lambda value=value:self.validate(value,3))
        value=self.device(3);value['tlsPolicy'].update(activeBootMode='default');self.rejected('UI hot applied default',lambda:self.validate(value,3))
        value=self.device(3);value['uiSaveCompleted']=False;self.rejected('UI not saved',lambda:self.validate(value,3))
    def test_persistent_worker_requires_actual_fetch_not_script_download_or_page(self):
        for label in ('persistent-before','persistent-after'):
            host=copy.deepcopy(self.evidence.host);entry=next(e for e in self.evidence.entries if e['label']==label)
            host['records']=[r for r in host['records'] if not(r.get('caseNonce')==entry['binding']['caseNonce'] and r.get('requestRole')=='service-fetch')]
            for i,r in enumerate(host['records'],1):r['sequence']=i
            self.rejected(label+' no actual worker fetch',lambda host=host:contract.validate_wire(host,self.evidence.entries,run=RUN,source=SOURCE))
        entries=copy.deepcopy(self.evidence.entries);entries[7]['device']['serviceObservation']['existingRegistration']=False;self.rejected('new worker disguised as persisted',lambda:contract.validate_cross(entries,self.evidence.process_checks))
        entries=copy.deepcopy(self.evidence.entries);entries[7]['finding']['serviceBootNonce']=entries[6]['finding']['serviceBootNonce'];self.rejected('old worker survived supposed cold start',lambda:contract.validate_cross(entries,self.evidence.process_checks))
    def test_true_cold_reapply_and_concurrent_live_process_identity_are_mandatory(self):
        for label,key,other in (('restored-default-tls12','processNonce','pending-default-tls12'),('restored-default-tls12','runtimeNonce','pending-default-tls12'),('concurrent-default-tls12','environmentId','concurrent-strict-tls13'),('concurrent-strict-resample-tls12','runtimeNonce','concurrent-default-tls12')):
            entries=copy.deepcopy(self.evidence.entries);a=next(e for e in entries if e['label']==label);b=next(e for e in entries if e['label']==other);a['finding'][key]=b['finding'][key];self.rejected(label+key,lambda entries=entries:contract.validate_cross(entries,self.evidence.process_checks))
        checks=copy.deepcopy(self.evidence.process_checks);checks[-1]['observedPid']='999';self.rejected('second environment killed',lambda:contract.validate_cross(self.evidence.entries,checks))
    def test_actual_contract_semantic_guard_mutations_are_detected(self):
        source=(ROOT/'tools/gecko/tls_acceptance_contract.py').read_text()
        controls=[
          ('strict-native',"if mode=='tls13':require(value['defaultMin']==value['defaultMax']==4,'strict native DEFAULT4/4')",'pass',1,lambda v:v['tlsPolicy'].update(defaultMin=3,configuredMin=3)),
          ('USER-readback',"('hasUserMin','hasUserMax','wireObservationVerified'","('wireObservationVerified'",0,lambda v:v['tlsPolicy'].update(hasUserMin=True)),
          ('nonce-title',"('targetStarted','targetLocation','titleMatched')","('targetStarted','targetLocation')",0,lambda v:v['navigation'].update(titleMatched=False)),
          ('UI-live-work',"and equal(before,after),'save itself must not navigate, restart or mutate live task state'","and True,'save itself must not navigate, restart or mutate live task state'",3,lambda v:v['uiAfter'].update(navigationEpoch=999))]
        for label,before,after,index,change in controls:
            self.assertEqual(source.count(before),1,label)
            bad=self.device(index);change(bad);self.rejected('actual baseline '+label,lambda bad=bad,index=index:self.validate(bad,index))
            namespace=dict(contract.__dict__);namespace['verify_installed']=lambda actual,expected:self.assertEqual(actual,expected)
            parsed=ast.parse(source.replace(before,after,1));functions=[n for n in parsed.body if isinstance(n,ast.FunctionDef)]
            exec(compile(ast.Module(body=functions,type_ignores=[]),'actual-product-tls-'+label,'exec'),namespace)
            entry=self.evidence.entries[index]
            # This compile-success/runtime-accept result means the false state
            # escapes only after removing the exact current production guard.
            finding=namespace['validate_device'](bad,spec=CASE_SPECS[index],binding=entry['binding'],run=RUN,source=SOURCE,tree=TREE,identity=self.evidence.identity,leaf=self.evidence.leaf)
            self.assertEqual(finding['label'],entry['label'])
            NEGATIVE_CONTROLS.append('compiled semantic guard mutant '+label);SEMANTIC_MUTANTS.append(label)

    def test_source_bound_checker_executes_all_original_packets(self):
        with tempfile.TemporaryDirectory() as temp:
            self.evidence.write(temp);result=self.verify(temp);self.assertEqual(result['caseCount'],11);self.assertEqual(set(result['caseSha256']),{r[0] for r in CASE_SPECS});self.assertFalse(result['rawFatalAlertPacketDecoded']);self.assertFalse(result['independentDownloaderTlsCovered'])
    def test_missing_extra_symlink_private_alias_and_duplicate_raw_json_refused(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);self.evidence.write(root);path=root/checker.CASE_FILES[0];original=path.read_bytes()
            for name in checker.CASE_FILES:
                p=root/name;saved=p.read_bytes();p.unlink();self.rejected('missing '+name,lambda:self.verify(root));p.write_bytes(saved)
            for name in ('extra.json','private.log','private.key'):
                p=root/name;p.write_text('host-negative-only');self.rejected('extra '+name,lambda:self.verify(root));p.unlink()
            p=root/'directory';p.mkdir();self.rejected('extra directory',lambda:self.verify(root));p.rmdir()
            p=root/'alias.json';p.symlink_to(path);self.rejected('symlink original',lambda:self.verify(root));p.unlink()
            path.write_bytes(b'{"schema":1,'+original[1:]);self.rejected('duplicate raw device key',lambda:self.verify(root));path.write_bytes(original)
            path.write_bytes(b'x'*262145);self.rejected('oversized raw device',lambda:self.verify(root));path.write_bytes(original)
            (root/checker.REPORT_NAME).write_bytes((root/'results.json').read_bytes()+b' ');self.rejected('different alias bytes',lambda:self.verify(root))
    def test_changed_source_sdk_apk_attempt_or_cleanup_cannot_be_rehashed_into_gate(self):
        for name,change in {
          'old source':lambda v:v.update(sourceCommit='f'*40),'old tree':lambda v:v.update(sourceTree='f'*40),
          'old APK':lambda v:v['expectedBuildIdentity'].update(apkSha256='f'*64),
          'old SDK attempt':lambda v:v['expectedBuildIdentity']['sdkBuildIdentity'].update(runAttempt='2'),
          'wrong run attempt':lambda v:v.update(runAttempt='2'),'missing original private cleanup':lambda v:v['cleanup'].update(privateMaterialRemoved=False),
          'no actual CPUs':lambda v:v['guest'].update(onlineCpus=True),
          'whole-app claim':lambda v:v.update(appIndependentTlsStacksCovered=True),
          'source hash changed':lambda v:v['sourceFiles'].update({'tools/gecko/tls_acceptance_contract.py':'f'*64}),
          'missing original case':lambda v:v['caseRecords'].pop(),
          'missing native checker evidence':lambda v:v['caseRecords'][0].update(reportSha256='f'*64),
          'certificate exception':lambda v:v['hostTls'].update(certificateExceptionUsed=True)}.items():
            with tempfile.TemporaryDirectory() as temp:
                root=Path(temp);value=self.evidence.write(root);change(value);(root/'results.json').write_text(json.dumps(value));self.rejected(name,lambda root=root:self.verify(root))
    def test_originals_rewritten_during_validator_callback_are_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);self.evidence.write(root);actual=checker.selected_contract
            def late(source,reader):
                chosen=actual(source,reader);original=chosen['validate_device'];done=[False]
                def callback(*args,**kwargs):
                    result=original(*args,**kwargs)
                    if not done[0]:done[0]=True;p=root/checker.CASE_FILES[-1];p.write_bytes(p.read_bytes()+b' ')
                    return result
                chosen['validate_device']=callback;return chosen
            with patch.object(checker,'selected_contract',side_effect=late):self.rejected('late raw rewrite',lambda:self.verify(root))
    def test_duplicate_nonfinite_headers_and_unsafe_application_bodies_refused(self):
        for raw in (b'{"x":1,"x":2}',b'{"x":NaN}',b'{"x":Infinity}',b'\xff'):
            self.rejected('strict original JSON '+repr(raw),lambda raw=raw:strict_json(raw))
        for raw in (b'GET / HTTP/1.1\r\nHost: x\r\nHost: y\r\n\r\n',b'POST / HTTP/1.1\r\nContent-Length: 9000\r\n\r\n',b'POST / HTTP/1.1\r\nTransfer-Encoding: chunked\r\n\r\n',b'GET / HTTP/1.1\r\nContent-Length: 1\r\n\r\n'):
            a,b=socket.socketpair()
            try:b.sendall(raw);b.shutdown(socket.SHUT_WR);self.rejected('strict application header',lambda:read_application_header(a))
            finally:a.close();b.close()
        a,b=socket.socketpair()
        try:
            b.sendall(b'POST / HTTP/1.1\r\nContent-Length: 4\r\n\r\nBODY');method,path,headers=read_application_header(a);self.assertEqual((method,path,headers['content-length']),('POST','/','4'));self.assertEqual(a.recv(4),b'BODY')
        finally:a.close();b.close()

class ProducerBoundaryControls(unittest.TestCase):
    def test_finally_helper_freezes_after_late_socket_and_all_cleanup_even_on_failure(self):
        events=[];errors=[];cleanup={k:False for k in ('appStopped','appDataCleared','reverseRemoved','serverClosed','serverThreadsJoined','caRemoved','privateMaterialRemoved','shellUidRestored')}
        class Server:
            closed=False;joined=False
            def close(self):events.append('server-close');self.closed=self.joined=True
            def snapshot(self):events.append('snapshot');return {'lateRecordRetained':self.closed and self.joined}
        class Ca:
            def remove(self):events.append('ca-remove')
        with tempfile.TemporaryDirectory() as temp:
            folder=Path(temp)/'ephemeral';folder.mkdir()
            class Cert:
                directory=folder
                def close(self):events.append('private-remove');folder.rmdir()
            def adb(*args,**kw):
                events.append(args[:2]);return subprocess.CompletedProcess(args,0,b'Success\n' if args[:3]==('shell','pm','clear') else b'2000\n',b'')
            def stop():events.append('app-stop')
            host=runner.finish_resources(adb,stop,Server(),Cert(),Ca(),True,cleanup,errors,{})
            self.assertTrue(host['lateRecordRetained']);self.assertEqual(events[-1],'snapshot');self.assertLess(events.index('app-stop'),events.index('server-close'));self.assertLess(events.index('server-close'),events.index('ca-remove'));self.assertTrue(all(cleanup.values()));self.assertFalse(errors)
        with tempfile.TemporaryDirectory() as temp:
            class Cert2:
                directory=Path(temp)/'absent'
                def close(self):events.append('private-remove-after-stop-failure')
            def failing_stop():raise RuntimeError('Controlled app boundary failure')
            runner.finish_resources(adb,failing_stop,Server(),Cert2(),Ca(),True,cleanup,errors,{})
            self.assertTrue(errors);self.assertIn('private-remove-after-stop-failure',events)
    def test_activity_preserves_production_entry_and_never_sets_native_tls_or_js_getters(self):
        java=(ROOT/'tests/gecko/GeckoTlsAcceptanceActivity.java').read_text();provider=(ROOT/'tests/gecko/GeckoTlsAcceptanceProvider.java').read_text()
        for text in ('extends MainActivity','GeckoTlsStore.save','super.onCreate(null)','super.newSession()','GeckoTlsUi.saveDesired','uiBefore=taskSnapshot()','uiAfter=taskSnapshot()','remote.tlsBoot.preparation.evidence()','GeckoCpuProfile.storage(this)','GeckoTlsProfile.withoutTls','navigation.onLoadRequest(s,request)','content.onCrash(s)'):self.assertIn(text,java)
        for forbidden in ('GeckoRuntime.create','new GeckoRuntime','setGeckoPref(','clearGeckoUserPref(','evaluateJavascript(','remoteDebuggingEnabled','setDefaultSSL'):self.assertNotIn(forbidden,java)
        stop=java[java.index('public void onPageStop'):java.index('public void onProgressChange')];self.assertNotIn('terminal=true',stop);self.assertNotIn('titleMatched=true',stop)
        self.assertIn('Binder.getCallingUid()!=2000',provider);self.assertIn('Files.isSymbolicLink',provider)
        original=subprocess.check_output(['git','show','9f5d8913060f3b97c042120570eb5bfcb71e5dd8:tests/gecko/AndroidManifest.xml'],cwd=ROOT,text=True)
        current=(ROOT/'tests/gecko/AndroidManifest.xml').read_text();filtered='\n'.join(line for line in current.split('\n') if 'GeckoTlsAcceptance' not in line)
        self.assertEqual(filtered,original)
        for name in ('tls-acceptance-page.js','tls-acceptance-worker.js'):
            text=(ROOT/'tests/gecko/assets'/name).read_text()
            for forbidden in ('Object.defineProperty','__defineGetter__','.prototype.','hardwareConcurrency','setGeckoPref','RTCPeerConnection'):self.assertNotIn(forbidden,text)
            subprocess.run(['node','--check',str(ROOT/'tests/gecko/assets'/name)],check=True,capture_output=True)
    def test_packaging_rejects_integration_components_assets_or_missing_production_classes(self):
        integration=' '.join(['GeckoTlsAcceptanceActivity$Profile1','GeckoTlsAcceptanceActivity$Profile2','GeckoTlsAcceptanceProvider','local.pocketchat.test.tls-acceptance',':profile1',':profile2'])
        components(PRODUCTION_CLASSES|TEST_CLASSES,integration,ASSETS,True);components(PRODUCTION_CLASSES,'release',set(),False)
        for definitions,manifest,assets,flag in ((PRODUCTION_CLASSES|TEST_CLASSES,'release',set(),False),(PRODUCTION_CLASSES,'GeckoTlsAcceptanceProvider',set(),False),(PRODUCTION_CLASSES,'release',ASSETS,False),(PRODUCTION_CLASSES,integration,ASSETS,True),(TEST_CLASSES,integration,ASSETS,True)):
            with self.assertRaises(ValueError):components(definitions,manifest,assets,flag)
    def test_new_workflow_is_diagnostic_only_same_build_source_and_no_writes(self):
        value=yaml.safe_load((ROOT/'.github/workflows/gecko-tls-acceptance.yml').read_text());self.assertEqual(value['permissions'],{'contents':'read'});self.assertEqual(value['on']['push']['branches'],['diagnostics/gecko-tls-*']);self.assertEqual(set(value['jobs']),{'build','gecko_tls_acceptance'});self.assertEqual(value['jobs']['gecko_tls_acceptance']['needs'],'build')
        text='\n'.join(str(step.get('run','')) for d in value['jobs'].values() for step in d['steps'])
        for token in ('run_gecko_tls_acceptance.py','check_gecko_tls_evidence.py','--apk app/build/outputs/apk/integration/app-x86_64-integration.apk','--source "$GITHUB_SHA"','-cores 4','check_gecko_tls_package.py','gecko-tls-host/run.py','gecko-tls-ui-host/run.py'):self.assertIn(token,text)
        self.assertNotIn('continue-on-error',str(value));self.assertNotIn('workflow_dispatch',value['on']);self.assertNotIn('git push',text);self.assertNotIn('gh release',text)
        self.assertEqual(os.environ.get('GIT_NO_LAZY_FETCH'),'1')

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--output',type=Path);args,extra=parser.parse_known_args()
    inputs=set(checker.SOURCE_INPUTS)|{'tests/gecko_tls_acceptance_test.py','tests/tls_product_test_support.py','docs/diagnostics/GECKO-TLS-ACCEPTANCE.md'}
    source_files={name:hashlib.sha256((ROOT/name).read_bytes()).hexdigest() for name in sorted(inputs)}
    suite=unittest.defaultTestLoader.loadTestsFromModule(sys.modules[__name__]);result=unittest.TextTestRunner(verbosity=2).run(suite)
    stable=all((ROOT/name).is_file() and not (ROOT/name).is_symlink() and hashlib.sha256((ROOT/name).read_bytes()).hexdigest()==value for name,value in source_files.items())
    report=dict(schema=1,status='passed' if result.wasSuccessful() and stable else 'failed',sourceFiles=source_files,executionInputsUnchanged=stable,tests=result.testsRun,failures=len(result.failures),errors=len(result.errors),negativeVariants=len(NEGATIVE_CONTROLS),compiledSemanticGuardMutants=len(SEMANTIC_MUTANTS),actualAndroidExecution=False,actualGeckoExecution=False,actualNativeTlsPreferenceExecution=False,actualServiceWorkerExecution=False,actualHostOpenSslWireExecution=hasattr(ProductTlsControls,"evidence"),signatureOrReleaseQualified=False,scope='Real host OpenSSL TLS sockets/parser and selected-source validator controls with explicitly synthetic device/process/SW/CA-install metadata. No Android, native Gecko, persistent Worker or product acceptance is inferred.')
    if args.output:args.output.parent.mkdir(parents=True,exist_ok=True);args.output.write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(report));raise SystemExit(0 if result.wasSuccessful() and stable else 1)
