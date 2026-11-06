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
import shlex
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
from tls_product_test_support import HostModelEvidence,model_device,model_identity,request,SOURCE,TREE,RUN,model_manual_checks
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
            self.evidence.write(temp);result=self.verify(temp);self.assertEqual(result['caseCount'],12);self.assertEqual(set(result['caseSha256']),{r[0] for r in CASE_SPECS}|{'combined-cpu-ip-tls13'});self.assertFalse(result['rawFatalAlertPacketDecoded']);self.assertFalse(result['independentDownloaderTlsCovered'])
    def test_explicit_manual_scope_never_borrows_cold_native_or_user_choice(self):
        selected=checker.selected_manual_contract(SOURCE,lambda source,path:(ROOT/path).read_bytes(),contract.__dict__)
        for index,entry in enumerate(self.evidence.entries):
            selected['validate_manual_scope'](self.device(index),spec=CASE_SPECS[index],binding=entry['binding'],run=RUN,source=SOURCE,tree=TREE,identity=self.evidence.identity)
        for key,bad in (('purpose','foreign.Activity'),('processName','local.pocketchat.test'),('sourceCommit','f'*40),('apkSha256','f'*64),('sdkRunAttempt','2'),('caseNonce','f'*32),('slot',6),('recordReadOnly',False),('scopeOnly',False),('nativeAdmissionGranted',True),('coldRuntimeProvenByScope',True)):
            value=self.device();value['manualScope'][key]=bad;entry=self.evidence.entries[0]
            self.rejected('manual scope '+key,lambda value=value:selected['validate_manual_scope'](value,spec=CASE_SPECS[0],binding=entry['binding'],run=RUN,source=SOURCE,tree=TREE,identity=self.evidence.identity))
        for mode in ('ip','iana'):
            value=self.device();value['manualScope']['timezoneDesired']['mode']=mode;entry=self.evidence.entries[0]
            self.rejected('manual refuses '+mode,lambda value=value:selected['validate_manual_scope'](value,spec=CASE_SPECS[0],binding=entry['binding'],run=RUN,source=SOURCE,tree=TREE,identity=self.evidence.identity))
        checks=model_manual_checks(self.evidence.entries)
        selected['validate_manual_cross'](self.evidence.entries,checks,run=RUN,source=SOURCE)
        bad=copy.deepcopy(checks);bad[0]['processAbsent']=False;self.rejected('marker cannot prove process cold',lambda:selected['validate_manual_cross'](self.evidence.entries,bad,run=RUN,source=SOURCE))
        entries=copy.deepcopy(self.evidence.entries);entries[2]['device']['manualScope']['claimNonce']='f'*32;self.rejected('warm resample replaced scope',lambda:selected['validate_manual_cross'](entries,checks,run=RUN,source=SOURCE))
        for key,bad_value in (('preparationBeforeLabel','concurrent-default-tls12'),('allListedFixtureProcessesAbsentAtPreparation',False),('scopeProcessesChecked',['local.pocketchat.test:profile2']),('reuseAtLabel','concurrent-strict-tls13'),('scopeInspectionVerified',False)):
            bad=copy.deepcopy(checks);bad[-1][key]=bad_value;self.rejected('concurrent scope ordering '+key,lambda bad=bad:selected['validate_manual_cross'](self.evidence.entries,bad,run=RUN,source=SOURCE))
    def test_twelfth_is_mandatory_same_installed_source_and_selected_current_contract(self):
        for name,change in {
          'missing combination':lambda v:v.pop('combinedCase'),
          'old eleven-only outcome':lambda v:v.update(coldCpuIpTlsCombinationMeasured=False),
          'wrong original combination hash':lambda v:v['combinedCase'].update(reportSha256='f'*64),
          'missing independent process observation':lambda v:v['combinedCase']['processSample'].update(observedPid='999'),
          'old callback runtime':lambda v:v['combinedFinding'].update(tlsRuntimeNonce='f'*32),
          'missing manual setup':lambda v:v.pop('manualScopeChecks')}.items():
            with tempfile.TemporaryDirectory() as temp:
                root=Path(temp);value=self.evidence.write(root);change(value);(root/'results.json').write_text(json.dumps(value));self.rejected(name,lambda root=root:self.verify(root))
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);value=self.evidence.write(root);path=root/checker.CASE_FILES[-1];raw=path.read_bytes();path.write_bytes(b'{"schema":1,'+raw[1:]);value['combinedCase']['reportSha256']=hashlib.sha256(path.read_bytes()).hexdigest();(root/'results.json').write_text(json.dumps(value));self.rejected('duplicate twelfth raw key before tuple checks',lambda:self.verify(root))

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

class ManualPreparationOrderingControls(unittest.TestCase):
    def boundary(self):
        live=set();markers={};events=[];serial=[0]
        def adb(*args,**kwargs):
            if args[:3]==('shell','am','force-stop'):live.clear();events.append(('stop',));raw=b''
            elif args[:3]==('shell','id','-u'):raw=b'2000\n'
            elif args[:2]==('shell','pidof'):events.append(('pidof',args[2]));raw=b'2401\n' if args[2] in live else b''
            elif len(args)==2 and args[0]=='shell':
                parts=shlex.split(args[1]);self.assertEqual(parts[:2],['content','call']);action=parts[parts.index('--method')+1];fields=[parts[i+1] for i,p in enumerate(parts) if p=='--extra'];slot=int(next(x.split(':',2)[2] for x in fields if x.startswith('slot:i:')));events.append((action,slot))
                if action=='clear':markers.pop(slot,None);raw=b'Bundle[{status=cleared}]'
                elif action=='prepare':
                    self.assertFalse(live,'No live generic fixture writer may overlap a new preparation');serial[0]+=1;markers[slot]=format(serial[0]+700,'032x');raw=('Bundle[{claimNonce='+markers[slot]+', status=armed}]').encode()
                elif action=='inspect':raw=('Bundle[{claimNonce='+markers[slot]+', status=armed}]').encode()
                else:raise AssertionError('Unknown modeled shell scope action')
            else:raise AssertionError('Unmodeled native boundary')
            return subprocess.CompletedProcess(args,0,raw,b'')
        main=next(n for n in ast.parse((ROOT/'tools/gecko/run_gecko_tls_acceptance.py').read_text()).body if isinstance(n,ast.FunctionDef) and n.name=='main')
        cold=next(n for n in main.body if isinstance(n,ast.FunctionDef) and n.name=='cold_stop');namespace=dict(runner.__dict__,adb=adb)
        exec(compile(ast.Module(body=[cold],type_ignores=[]),'actual-TLS-cold-stop','exec'),namespace)
        return live,markers,events,adb,namespace['cold_stop']
    def exercise(self,loop=runner.run_original_cases):
        live,markers,events,adb,stop=self.boundary();rows=[];started=[];original_second=[]
        def prepare(spec,before,prearmed):return runner.prepare_manual_scope(adb,SOURCE,RUN,spec,before,prearmed)
        def collect(spec,row):
            label,slot=spec[:2];events.append(('start',label));started.append(label)
            if row is not None:rows.append(row)
            if label=='concurrent-strict-tls13':self.assertIn(2,markers,'Second manual record must precede first concurrent runtime');original_second.append(markers[2])
            if label=='concurrent-default-tls12':self.assertIn(runner.PACKAGE+':profile1',live);self.assertEqual(markers[2],original_second[0]);self.assertTrue(row['scopeReusedBeforeStart'] and row['scopeInspectionVerified'])
            live.add(runner.PACKAGE+':profile'+str(slot))
        loop(stop,prepare,collect,lambda stage:events.append(('resident',stage)))
        self.assertEqual(started,[s[0] for s in CASE_SPECS]);self.assertEqual([r['label'] for r in rows],[s[0] for s in CASE_SPECS if not s[6]])
        first=events.index(('start','concurrent-strict-tls13'));second=events.index(('start','concurrent-default-tls12'))
        self.assertIn(('prepare',2),events[:first]);self.assertNotIn(('prepare',2),events[first:second]);self.assertNotIn(('clear',2),events[first:second]);self.assertIn(('inspect',2),events[first:second]);self.assertNotIn(('stop',),events[first:second])
        for row in rows:self.assertEqual(row['scopeProcessesChecked'],runner.scope_processes());self.assertTrue(row['allListedFixtureProcessesAbsentAtPreparation'])
        return rows
    def test_actual_loop_prearms_second_scope_before_any_concurrent_runtime(self):self.exercise()
    def test_actual_scope_preparation_rejects_any_listed_live_writer_before_mutation(self):
        for process in runner.scope_processes():
            live,markers,events,adb,stop=self.boundary();live.add(process)
            with self.subTest(process=process):
                with self.assertRaises(ValueError):runner.prepare_manual_scope(adb,SOURCE,RUN,CASE_SPECS[9],'concurrent-strict-tls13')
                self.assertEqual(markers,{});self.assertFalse(any(e[0] in ('clear','prepare') for e in events));NEGATIVE_CONTROLS.append('live fixture writer before prepare '+process)
    def test_concurrent_inspection_cannot_replace_claim_or_silently_create(self):
        rows=self.exercise();row=next(r for r in rows if r['slot']==2)
        live,markers,events,adb,stop=self.boundary();live.add(runner.PACKAGE+':profile1');markers[2]='f'*32
        with self.assertRaises(ValueError):runner.prepare_manual_scope(adb,SOURCE,RUN,CASE_SPECS[9],'concurrent-strict-tls13',row)
        self.assertEqual(markers[2],'f'*32);self.assertFalse(any(e[0] in ('clear','prepare') for e in events));NEGATIVE_CONTROLS.append('changed concurrent scope claim rejected without rewrite')
        for raw in (b'Bundle[{status=armed}]',b'Bundle[{status=armed, claimNonce='+b'a'*33+b'}]',b'Bundle[{status=armed, claimNonce='+b'a'*32+b', claimNonce='+b'b'*32+b'}]',b'Bundle[{status=failed, claimNonce='+b'a'*32+b'}]'):
            with self.assertRaises(ValueError):runner.manual_claim(raw)
            NEGATIVE_CONTROLS.append('strict provider claim response '+str(len(raw)))
    def test_compiled_ordering_mutants_restore_the_rejected_live_writer_race(self):
        source=(ROOT/'tools/gecko/run_gecko_tls_acceptance.py').read_text()
        changes=[('late-second-prepare','prearmed=prepare_scope(next_spec,label,None)','prearmed=None'),('reprepare-concurrent-live',"prepare_scope(spec,'concurrent-strict-tls13',prearmed)","prepare_scope(spec,spec[0],None)")]
        for label,before,after in changes:
            self.assertEqual(source.count(before),1);namespace=dict(runner.__dict__);parsed=ast.parse(source.replace(before,after,1));functions=[n for n in parsed.body if isinstance(n,ast.FunctionDef)]
            exec(compile(ast.Module(body=functions,type_ignores=[]),'actual-TLS-order-'+label,'exec'),namespace)
            with self.assertRaises((ValueError,AssertionError)):self.exercise(namespace['run_original_cases'])
            SEMANTIC_MUTANTS.append(label);NEGATIVE_CONTROLS.append('compiled producer ordering mutant '+label)
        before="for process in scope_processes():require(not adb('shell','pidof',process,check=False).stdout.strip(),'all generic fixture writers must be absent before manual preparation')"
        self.assertEqual(source.count(before),1);namespace=dict(runner.__dict__);parsed=ast.parse(source.replace(before,'pass',1));functions=[n for n in parsed.body if isinstance(n,ast.FunctionDef)]
        exec(compile(ast.Module(body=functions,type_ignores=[]),'actual-TLS-writer-absence-mutant','exec'),namespace)
        live,markers,events,adb,stop=self.boundary();live.add(runner.PACKAGE+':profile3')
        # Actual baseline rejects above; the compiled mutant reaches its first
        # forbidden mutation, which this explicit writer boundary refuses.
        with self.assertRaises(AssertionError):namespace['prepare_manual_scope'](adb,SOURCE,RUN,CASE_SPECS[9],'concurrent-strict-tls13')
        self.assertIn(('clear',2),events);self.assertIn(('prepare',2),events);SEMANTIC_MUTANTS.append('missing-all-listed-pidof');NEGATIVE_CONTROLS.append('compiled writer absence mutant')

class FixtureProcessObservationControls(unittest.TestCase):
    def observe(self,result,*,process=None,phase='manual-prepare',label='restored-default-tls12',rows=None):
        rows=[] if rows is None else rows
        return runner.observe_fixture_process(('shell','pidof',process or runner.PACKAGE),result,rows,phase,label),rows
    def test_actual_pidof_outcomes_keep_typed_live_pid_and_absence_distinct(self):
        for process in runner.scope_processes():
            row,rows=self.observe(subprocess.CompletedProcess([],0,b'4767\n',b''),process=process)
            self.assertEqual((row['status'],row['pids'],row['returnCode']),('present',[4767],0));self.assertEqual(row['processName'],process);self.assertEqual(rows,[row])
            row,rows=self.observe(subprocess.CompletedProcess([],1,b'',b''),process=process)
            self.assertEqual((row['status'],row['pids'],row['returnCode']),('absent',[],1));self.assertEqual(row['label'],'restored-default-tls12')
    def test_unknown_pidof_output_cannot_become_absence_and_never_exports_raw_text(self):
        results=[(0,b'',b''),(1,b'4767\n',b''),(2,b'',b''),(-9,b'',b''),(0,b'unknown-private-content',b''),(1,b'',b'private-adb-error'),(0,b'0\n',b''),(0,b'4767 4767\n',b''),(True,b'4767\n',b''),(0,b'1'*513,b''),(1,b'',b'x'*4097)]
        for code,out,err in results:
            rows=[]
            with self.subTest(code=code,out=out[:20],stderr=len(err)):
                with self.assertRaises(ValueError):self.observe(subprocess.CompletedProcess([],code,out,err),rows=rows)
                self.assertEqual(len(rows),1);self.assertEqual(rows[0]['status'],'invalid-command-result');self.assertEqual(rows[0]['pids'],[])
                self.assertNotIn('private',json.dumps(rows));NEGATIVE_CONTROLS.append('typed pidof refuses ambiguous result '+str(len(NEGATIVE_CONTROLS)))
        for process,phase,label in ((runner.PACKAGE+':unknown','manual-prepare','restored-default-tls12'),(runner.PACKAGE,'unowned','restored-default-tls12'),(runner.PACKAGE,'manual-prepare','unknown-case')):
            with self.assertRaises(ValueError):self.observe(subprocess.CompletedProcess([],1,b'',b''),process=process,phase=phase,label=label)
            NEGATIVE_CONTROLS.append('fixed pidof metadata owner '+process+phase+label)
    def test_actual_adb_wrapper_records_failure_before_original_guard_and_preserves_check(self):
        main=next(n for n in ast.parse((ROOT/'tools/gecko/run_gecko_tls_acceptance.py').read_text()).body if isinstance(n,ast.FunctionDef) and n.name=='main')
        adb=next(n for n in main.body if isinstance(n,ast.FunctionDef) and n.name=='adb');rows=[]
        namespace=dict(runner.__dict__,a=argparse.Namespace(adb='declared-adb-boundary',serial='emulator-5554'),fixture_process_observations=rows,observation_context=['manual-prepare','restored-default-tls12'])
        exec(compile(ast.Module(body=[adb],type_ignores=[]),'actual-TLS-observed-adb','exec'),namespace)
        seen=[]
        def completed(parts,**kwargs):
            seen.append((parts,kwargs))
            if parts[-3:]==['shell','id','-u']:return subprocess.CompletedProcess(parts,0,b'2000\n',b'')
            self.assertEqual(parts[-3:-1],['shell','pidof'],'No mutation may occur before all writers are absent')
            live=parts[-1]==runner.PACKAGE
            return subprocess.CompletedProcess(parts,0 if live else 1,b'4767\n' if live else b'',b'')
        with patch.object(runner.subprocess,'run',side_effect=completed):
            with self.assertRaises(ValueError):runner.prepare_manual_scope(namespace['adb'],SOURCE,RUN,CASE_SPECS[4],'restored-default-tls12')
        self.assertEqual(len(rows),2);self.assertEqual(rows[0]['status'],'absent');self.assertEqual(rows[1]['pids'],[4767])
        self.assertEqual(rows[1]['processName'],runner.PACKAGE);self.assertEqual(rows[1]['phase'],'manual-prepare')
        self.assertTrue(seen[0][1]['check']);self.assertTrue(all(not options['check'] for _,options in seen[1:]))
        with patch.object(runner.subprocess,'run',return_value=subprocess.CompletedProcess([],1,b'',b'')):
            with self.assertRaises(subprocess.CalledProcessError):namespace['adb']('shell','pidof',runner.PACKAGE)
        self.assertEqual(rows[-1]['status'],'absent')
        with patch.object(runner.subprocess,'run',return_value=subprocess.CompletedProcess([],2,b'',b'')):
            with self.assertRaises(ValueError):namespace['adb']('shell','pidof',runner.PACKAGE,check=False)
        self.assertEqual(rows[-1]['returnCode'],2);self.assertEqual(rows[-1]['status'],'invalid-command-result')
        for failure,kind in ((subprocess.TimeoutExpired('controlled-adb',25,output=b'not-a-pid'),'TimeoutExpired'),(OSError('controlled transport exception'),'OSError')):
            with patch.object(runner.subprocess,'run',side_effect=failure):
                with self.assertRaises(type(failure)):namespace['adb']('shell','pidof',runner.PACKAGE,check=False)
            self.assertEqual(rows[-1]['commandErrorType'],kind);self.assertEqual(rows[-1]['processName'],runner.PACKAGE);self.assertEqual(rows[-1]['status'],'invalid-command-result')
            NEGATIVE_CONTROLS.append('actual pidof wrapper preserves '+kind)
    def test_compiled_observation_mutants_cannot_drop_failure_or_accept_query_errors(self):
        source=(ROOT/'tools/gecko/run_gecko_tls_acceptance.py').read_text()
        changes=[('drop-observation','observations.append(row)','pass'),('accept-query-error',"require(valid,'fixed process observation failed for '+parts[2])",'pass')]
        for label,before,after in changes:
            self.assertEqual(source.count(before),1);parsed=ast.parse(source.replace(before,after,1));function=next(n for n in parsed.body if isinstance(n,ast.FunctionDef) and n.name=='observe_fixture_process');namespace=dict(runner.__dict__)
            exec(compile(ast.Module(body=[function],type_ignores=[]),'actual-TLS-observation-'+label,'exec'),namespace);rows=[]
            def invariant():
                try:namespace['observe_fixture_process'](('shell','pidof',runner.PACKAGE),subprocess.CompletedProcess([],2,b'',b''),rows,'manual-prepare','restored-default-tls12')
                except ValueError:pass
                else:raise AssertionError('An unsuccessful query was accepted')
                self.assertEqual(len(rows),1,'The failed native query must remain in the original report')
                self.assertEqual(rows[0]['status'],'invalid-command-result')
            with self.assertRaises(AssertionError):invariant()
            SEMANTIC_MUTANTS.append(label);NEGATIVE_CONTROLS.append('compiled process observation mutant '+label)

    def test_original_writer_guard_still_rejects_recorded_live_process_without_mutation(self):
        rows=[];events=[]
        def adb(*parts,**kwargs):
            if parts==('shell','id','-u'):return subprocess.CompletedProcess(parts,0,b'2000\n',b'')
            if parts[:2]==('shell','pidof'):
                live=parts[2]==runner.PACKAGE+':profile3';result=subprocess.CompletedProcess(parts,0 if live else 1,b'8492\n' if live else b'',b'')
                runner.observe_fixture_process(parts,result,rows,'manual-prepare','restored-default-tls12');return result
            events.append(parts);raise AssertionError('Scope mutation after live writer')
        with self.assertRaises(ValueError):runner.prepare_manual_scope(adb,SOURCE,RUN,CASE_SPECS[4],'restored-default-tls12')
        self.assertFalse(events);self.assertEqual(rows[-1]['processName'],runner.PACKAGE+':profile3');self.assertEqual(rows[-1]['pids'],[8492])
        self.assertEqual(rows[-1]['phase'],'manual-prepare');NEGATIVE_CONTROLS.append('recorded live writer still blocks original mutation guard')

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
        original=subprocess.check_output(['git','show','e4a20469326f16dc8ff8cfabd4fe67bf3d0148de:tests/gecko/AndroidManifest.xml'],cwd=ROOT,text=True)
        current=(ROOT/'tests/gecko/AndroidManifest.xml').read_text();filtered='\n'.join(line for line in current.split('\n') if not any(name in line for name in ('GeckoTlsAcceptance','NativeTlsProbe','GeckoTlsCpuIpCombo')))
        self.assertEqual(filtered,original)
        for name in ('tls-acceptance-page.js','tls-acceptance-worker.js'):
            text=(ROOT/'tests/gecko/assets'/name).read_text()
            for forbidden in ('Object.defineProperty','__defineGetter__','.prototype.','hardwareConcurrency','setGeckoPref','RTCPeerConnection'):self.assertNotIn(forbidden,text)
            subprocess.run(['node','--check',str(ROOT/'tests/gecko/assets'/name)],check=True,capture_output=True)
    def test_packaging_rejects_integration_components_assets_or_missing_production_classes(self):
        integration=' '.join(['GeckoTlsAcceptanceActivity$Profile1','GeckoTlsAcceptanceActivity$Profile2','GeckoTlsAcceptanceProvider','local.pocketchat.test.tls-acceptance',':profile1',':profile2','GeckoTlsCpuIpComboIntegrationActivity','GeckoTlsCpuIpComboEvidenceProvider','local.pocketchat.test.gecko-tls-cpu-ip-combo-evidence',':profile6',':ip_timezone_setup'])
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
    inputs=set(checker.SOURCE_INPUTS)|{'tests/gecko_tls_acceptance_test.py','tests/tls_product_test_support.py','tests/tls_cpu_ip_combo_test_support.py','tests/gecko_cpu_ip_combo_evidence_test.py','tests/gecko_ip_timezone_evidence_test.py','docs/diagnostics/GECKO-TLS-ACCEPTANCE.md'}
    source_files={name:hashlib.sha256((ROOT/name).read_bytes()).hexdigest() for name in sorted(inputs)}
    suite=unittest.defaultTestLoader.loadTestsFromModule(sys.modules[__name__]);result=unittest.TextTestRunner(verbosity=2).run(suite)
    stable=all((ROOT/name).is_file() and not (ROOT/name).is_symlink() and hashlib.sha256((ROOT/name).read_bytes()).hexdigest()==value for name,value in source_files.items())
    report=dict(schema=1,status='passed' if result.wasSuccessful() and stable else 'failed',sourceFiles=source_files,executionInputsUnchanged=stable,tests=result.testsRun,failures=len(result.failures),errors=len(result.errors),negativeVariants=len(NEGATIVE_CONTROLS),compiledSemanticGuardMutants=len(SEMANTIC_MUTANTS),actualAndroidExecution=False,actualGeckoExecution=False,actualNativeTlsPreferenceExecution=False,actualServiceWorkerExecution=False,actualHostOpenSslWireExecution=hasattr(ProductTlsControls,"evidence"),signatureOrReleaseQualified=False,scope='Real host OpenSSL TLS sockets/parser and selected-source validator controls with explicitly synthetic device/process/SW/CA-install metadata. No Android, native Gecko, persistent Worker or product acceptance is inferred.')
    if args.output:args.output.parent.mkdir(parents=True,exist_ok=True);args.output.write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(report));raise SystemExit(0 if result.wasSuccessful() and stable else 1)
