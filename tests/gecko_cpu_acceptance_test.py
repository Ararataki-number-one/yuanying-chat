"""Host controls for actual production CPU gate; no host fixture is Android proof."""
import argparse
import contextlib
import copy
import hashlib
import http.client
import importlib.util
import io
import json
import os
from pathlib import Path
import shutil
import shlex
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
from zipfile import ZipFile
import yaml
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'tools/gecko'))
sys.path.insert(0,str(ROOT/'tools/browser'))
import run_gecko_cpu_acceptance as runner
import check_gecko_cpu_evidence as checker
import run_gecko_cpu_integration as cpu_wrapper
from cpu_acceptance_server import CpuAcceptanceServer,GUEST_PORT,ROLES,strict_json
SOURCE='a'*40;TREE='b'*40;NONCE='c'*32;CASE='d'*32;IDENTITY={'controlledHostInputOnly':True}

def packet(role='page',mode='2',rfp=False,retain=False):
    count=2 if rfp else (4 if mode=='automatic' else int(mode));prefix='/cpu/slot1/'
    return dict(schema=1,runNonce=NONCE,caseNonce=CASE,sourceCommit=SOURCE,slot=1,role=role,status='observed',
        observation=dict(hardwareConcurrency=count,nativeGetter=True,firstInline=True,bootNonce=('e' if role=='service' else 'f')*32),error=None,
        service=dict(existingRegistration=retain,controlledBeforeRegistration=retain,scriptPath=prefix+'service.js',scopePath=prefix) if role=='service' else None)

def report(mode='2',rfp=False,retain=False,stale=False):
    cap=128 if mode=='automatic' else int(mode)
    cpu=dict(schema=1,engine='gecko',desiredRevision=3,desiredMode=mode,activeBootRevision=3,activeBootMode=mode,
        state='ready',issue='',failureCode='',pendingColdStart=False,configuredCap=cap,defaultCap=cap,hasUserValue=False,rfpPriority=rfp,
        nativeSettingReadback=True,startupReconciled=True,scope='runtime-wide',processNonce='1'*32,pid=1234,runtimeNonce='2'*32,
        environmentId='00000000-0000-0000-0000-000000000001',environmentGeneration=1,slot=1,
        pageObservationVerified=False,workerCoverageVerified=False,serviceWorkerCoverageVerified=False,persistentWorkerColdStartVerified=False)
    return dict(schema=1,fixtureType='gecko-production-cpu-v1',status='passed',stage='complete',failure='',diagnosticOnly=True,releaseAcceptance=False,
        sourceCommit=SOURCE,sourceTree=TREE,runNonce=NONCE,caseNonce=CASE,slot=1,mode=mode,rfpRequested=rfp,retainedProfile=retain,staleUserPrefSeeded=stale,
        identityApplyInvoked=False,identityApplyCompleted=False,identityPolicyBefore=0,identityPolicyRevision=2,buildIdentity=copy.deepcopy(IDENTITY),tls=dict(isSecure=True,isException=False,enterpriseRootsReadback=True,leafSha256='a'*64),process=dict(pid=1234,uid=10234,name='local.pocketchat.test:profile1'),cpuPolicy=cpu,runtimeCpuPolicy=copy.deepcopy(cpu),
        navigation=dict(targetStarted=True,targetLocation=True,targetStopSuccessful=True,loadError=False,targetPath='/cpu/slot1/page'),
        nativeEvents=[dict(event=name,targetOwned=True,success=True if name=='stop' else None,errorCategory=None,errorCode=None,nativeUrlAvailable=name!='stop') for name in ('start','location','stop')],
        observations=[packet(role,mode,rfp,retain) for role in ROLES],actualAndroidExecution=True,actualGeckoExecution=True,productionChatSession=True,
        productionCpuBootstrap=True,navigatorGetterOverrideUsed=False,debuggingEndpointUsed=False,workerCoverageVerified=False,fingerprintProtectionVerified=False)

class ProductionCpuControls(unittest.TestCase):
    def validate(self,value,mode='2',rfp=False,retain=False,stale=False):
        with patch.object(runner,'verify_installed',side_effect=lambda actual,expected:self.assertEqual(actual,expected)):
            return runner.validate_report(value,run=NONCE,case=CASE,source=SOURCE,tree=TREE,identity=IDENTITY,slot=1,mode=mode,rfp=rfp,retain=retain,stale_user=stale)
    def test_production_default_and_capped_first_inline_contexts_are_independent_of_ack(self):
        for mode in ('1','2','automatic'):
            value=report(mode);before=copy.deepcopy(value);result=self.validate(value,mode)
            self.assertEqual(value,before);self.assertEqual(set(result['counts']),set(ROLES))
            self.assertEqual(set(result['counts'].values()),{4 if mode=='automatic' else int(mode)})
            self.assertFalse(result['workerCoverageVerified']);self.assertFalse(result['fingerprintProtectionVerified'])
        value=report();value['observations'][1]['observation']['hardwareConcurrency']=4
        with self.assertRaises(ValueError):self.validate(value)
    def test_rfp_raw_mismatch_does_not_weaken_rfp_or_fabricate_cap_coverage(self):
        value=report('1',True);result=self.validate(value,'1',True)
        self.assertEqual(set(result['counts'].values()),{2});self.assertFalse(any(result['capObeyed'].values()))
        value['cpuPolicy']['rfpPriority']=False;value['runtimeCpuPolicy']['rfpPriority']=False
        with self.assertRaises(ValueError):self.validate(value,'1',True)
    def test_missing_stale_boolean_native_ack_and_getter_substitutions_are_rejected(self):
        mutations={
          'unknown top field':lambda v:v.update(private='never'),
          'runtime Boolean count':lambda v:v['runtimeCpuPolicy'].update(configuredCap=True),
          'source':lambda v:v.update(sourceCommit='f'*40),'nonce':lambda v:v.update(caseNonce='f'*32),
          'boolean schema':lambda v:v.update(schema=True),'unbound slot':lambda v:v.update(slot=True),
          'native pending':lambda v:v['cpuPolicy'].update(pendingColdStart=True),
          'different runtime status':lambda v:v['runtimeCpuPolicy'].update(runtimeNonce='f'*32),
          'unconfirmed native':lambda v:v['cpuPolicy'].update(nativeSettingReadback=False),
          'user pref retained':lambda v:v['cpuPolicy'].update(hasUserValue=True),
          'wrong boot mode':lambda v:v['cpuPolicy'].update(activeBootMode='1'),
          'worker missing':lambda v:v['observations'].pop(),
          'duplicate role':lambda v:v['observations'].__setitem__(1,copy.deepcopy(v['observations'][0])),
          'stale worker':lambda v:v['observations'][1].update(caseNonce='f'*32),
          'boolean count':lambda v:v['observations'][1]['observation'].update(hardwareConcurrency=True),
          'shim getter':lambda v:v['observations'][1]['observation'].update(nativeGetter=False),
          'late sample':lambda v:v['observations'][1]['observation'].update(firstInline=False),
          'worker unsupported':lambda v:v['observations'][1].update(status='unsupported',observation=None,error='Unavailable'),
          'target missing location':lambda v:v['navigation'].update(targetLocation=False),
          'target load error':lambda v:v['navigation'].update(loadError=True),
          'old native stop':lambda v:v['nativeEvents'].pop(),
          'stop URL invention':lambda v:v['nativeEvents'][2].update(nativeUrlAvailable=True),
          'private raw native field':lambda v:v['nativeEvents'][0].update(url='http://private/'),
          'TLS exception':lambda v:v['tls'].update(isException=True),
          'debugging':lambda v:v.update(debuggingEndpointUsed=True),'getter override':lambda v:v.update(navigatorGetterOverrideUsed=True)}
        for name,mutate in mutations.items():
            with self.subTest(name=name):
                value=report();mutate(value)
                with self.assertRaises((ValueError,AssertionError)):self.validate(value)
    def test_retained_profile_requires_existing_registration_and_prior_control(self):
        self.validate(report(retain=True),retain=True)
        for field in ('existingRegistration','controlledBeforeRegistration'):
            value=report(retain=True);value['observations'][-1]['service'][field]=False
            with self.assertRaises(ValueError):self.validate(value,retain=True)
    def evidence_fixture(self,directory):
        # Synthetic original transport bytes for checker controls only. No APK,
        # SDK, Android process, private key or signing operation is involved.
        expected=dict(schema=1,package='local.pocketchat.test',sourceCommit=SOURCE,sourceTree=TREE,dirtySource=False,
            version='2.1.3',versionCode=213,apkSha256='a'*64,apkBytes=123,buildStampSha256='b'*64,sdkBuildIdentity=dict(runId='7',runAttempt='1'))
        expected.update({key:'controlled-host-'+key for key in checker.SDK_FIELDS})
        hashes={name:hashlib.sha256((ROOT/name).read_bytes()).hexdigest() for name in checker.SOURCE_INPUTS}
        host=dict(schema=1,tlsConnections=12,upstreamConnections=0,forwardingImplemented=False,certificateExceptionUsed=False,
            trustMethod='domain-scoped-user-ca',eventsTruncated=False,cases={})
        installation=dict(method='domain-scoped-user-ca',androidUser=0,ownerAndMode='644:1000:1000',selinuxContext='u:object_r:keystore_data_file:s0',
            subjectHashOld='1234abcd',storePath='/data/misc/user/0/cacerts-added/1234abcd.0',publicCaPemSha256='b'*64,expectedLeafDerSha256='a'*64,
            evidenceShellUid=2000,cleanupRootUid=0,cleanupShellUid=2000)
        installation.update({key:True for key in ('adbRoot','selinuxEnforcing','installedPublicCaBytesMatch','appForceStoppedAfterInstall',
            'removedAfterExecution','shellRestoredAfterInstall','shellRestoredAfterCleanup')})
        tls=dict(ephemeral=True,opensslChainVerified=True,privateMaterialRemoved=True,reverseRemoved=True,privateMaterialLocation='host-tmp-only',
            privateMaterialExported=False,certificateExceptionUsed=False,hostnameVerified=['fp-a.pocketchat.test','fp-b.pocketchat.test'],guestPort=18766,
            caPemSha256='b'*64,leafDerSha256='a'*64,subjectHashOld='1234abcd',trustInstallation=installation,
            binding=dict(sourceCommit=SOURCE,sourceTree=TREE,runNonce=NONCE,integrationApkSha256='a'*64,sdkRunId='7',sdkRunAttempt='1'))
        summary=dict(schema=1,status='passed',sourceCommit=SOURCE,sourceTree=TREE,runNonce=NONCE,executionInputsUnchanged=True,errors=[],
            expectedBuildIdentity=expected,runId='7',runAttempt='1',sourceFiles=hashes,hostTls=tls,host=host,caseRecords=[],processChecks=[],
            cleanup=dict(appStopped=True,reverseRemoved=True,caRemoved=True,privateMaterialRemoved=True))
        summary.update({key:True for key in ('diagnosticOnly','actualAndroidExecution','actualGeckoExecution','productionColdCpuWorkloadPassed')})
        summary.update({key:False for key in ('releaseAcceptance','debuggingEndpointUsed','navigatorGetterOverrideUsed','workerCoverageVerified','fingerprintProtectionVerified')})
        for index,(label,slot,mode,rfp,retain,stale,template) in enumerate(checker.CASE_SPECS):
            value=report(mode,rfp,retain,stale);nonce=format(index+30,'032x');owner=index+1 if index<8 else 7
            value.update(caseNonce=nonce,slot=slot,buildIdentity=expected,identityApplyInvoked=template,identityApplyCompleted=template)
            if template:value.update(identityPolicyBefore=2,identityPolicyRevision=3)
            value['process'].update(pid=2000+owner,name='local.pocketchat.test:profile'+str(slot))
            for key in ('cpuPolicy','runtimeCpuPolicy'):
                value[key].update(pid=2000+owner,slot=slot,processNonce=format(owner,'032x'),runtimeNonce=format(owner+100,'032x'),
                    environmentId='00000000-0000-0000-0000-'+str(slot).zfill(12))
            value['navigation']['targetPath']='/cpu/slot'+str(slot)+'/page'
            for row in value['observations']:
                row.update(caseNonce=nonce,slot=slot)
                if row['role']=='service':
                    row['observation']['bootNonce']=format(owner+200,'032x')
                    row['service'].update(scriptPath='/cpu/slot'+str(slot)+'/service.js',scopePath='/cpu/slot'+str(slot)+'/')
            filename='case-'+label+'.json';raw=(json.dumps(value)+'\n\n').encode();(directory/filename).write_bytes(raw)
            summary['caseRecords'].append(dict(label=label,status='passed',caseNonce=nonce,report=filename,reportSha256=hashlib.sha256(raw).hexdigest(),finding={'untrustedSummary':True}))
            host['cases'][nonce]=dict(binding=dict(runNonce=NONCE,caseNonce=nonce,sourceCommit=SOURCE,slot=slot),observations=value['observations'])
        for stage,slot in (('both-resident',1),('both-resident',2),('after-resample',1),('after-resample',2)):
            owner=slot+6;record=summary['caseRecords'][slot+5]
            summary['processChecks'].append(dict(stage=stage,slot=slot,caseNonce=record['caseNonce'],processName='local.pocketchat.test:profile'+str(slot),
                expectedPid=2000+owner,observedPid=str(2000+owner),shellUid=2000))
        return summary,expected
    def replay_evidence(self,directory,summary,expected,reader=None):
        (directory/'results.json').write_text(json.dumps(summary))
        if reader is None:reader=lambda source,name:(ROOT/name).read_bytes()
        with patch.object(checker,'verify_installed',side_effect=lambda actual,wanted:self.assertEqual(actual,wanted)):
            return checker.verify_gecko_cpu_evidence(directory,SOURCE,expected,reader)
    def mutate_case(self,directory,summary,index,mutate):
        record=summary['caseRecords'][index];path=directory/record['report'];value=json.loads(path.read_bytes());mutate(value)
        raw=(json.dumps(value)+'\n').encode();path.write_bytes(raw);record['reportSha256']=hashlib.sha256(raw).hexdigest()
        summary['host']['cases'][record['caseNonce']]['observations']=copy.deepcopy(value['observations'])
    def test_checker_replays_selected_source_and_original_cases_without_trusting_summary_findings(self):
        with tempfile.TemporaryDirectory(prefix='cpu-evidence-host-') as name:
            directory=Path(name);summary,expected=self.evidence_fixture(directory);seen=[]
            def reader(source,path):self.assertEqual(source,SOURCE);seen.append(path);return (ROOT/path).read_bytes()
            finding=self.replay_evidence(directory,summary,expected,reader)
            self.assertEqual(finding['caseCount'],10);self.assertEqual(finding['pageAndWorkerCounts']['cap1'],dict.fromkeys(ROLES,1))
            self.assertFalse(finding['workerCoverageVerified']);self.assertIn('tools/gecko/run_gecko_cpu_acceptance.py',seen)
            raw=directory/summary['caseRecords'][0]['report'];raw.write_bytes(raw.read_bytes()+b' ')
            with self.assertRaises(ValueError):self.replay_evidence(directory,summary,expected)
    def test_checker_rejects_omitted_stale_foreign_or_shared_cpu_evidence(self):
        def change_cpu(value,**changes):
            for key in ('cpuPolicy','runtimeCpuPolicy'):value[key].update(changes)
        changes={
            'missing case':lambda d,s:s['caseRecords'].pop(),
            'stale sdk run':lambda d,s:s.update(runAttempt='2'),
            'host nonce':lambda d,s:s['hostTls']['binding'].update(runNonce='f'*32),
            'missing cleanup':lambda d,s:s['cleanup'].update(caRemoved=False),
            'missing resident check':lambda d,s:s['processChecks'].pop(),
            'wrong resident PID':lambda d,s:s['processChecks'][-1].update(observedPid='999'),
            'host receipt differs':lambda d,s:s['host']['cases'][s['caseRecords'][0]['caseNonce']]['observations'][0]['observation'].update(hardwareConcurrency=4),
            'omitted role':lambda d,s:self.mutate_case(d,s,0,lambda v:v['observations'].pop()),
            'stale packet':lambda d,s:self.mutate_case(d,s,0,lambda v:v['observations'][0].update(caseNonce='f'*32)),
            'boolean ack':lambda d,s:self.mutate_case(d,s,0,lambda v:change_cpu(v,configuredCap=True)),
            'same live SW':lambda d,s:self.mutate_case(d,s,5,lambda v:v['observations'][-1]['observation'].update(bootNonce=format(205,'032x'))),
            'concurrent runtime reused':lambda d,s:self.mutate_case(d,s,7,lambda v:change_cpu(v,runtimeNonce=format(107,'032x'))),
            'template boot changed':lambda d,s:self.mutate_case(d,s,9,lambda v:change_cpu(v,runtimeNonce='f'*32)),
            'source hash substituted':lambda d,s:s['sourceFiles'].update({'tools/gecko/run_gecko_cpu_acceptance.py':'f'*64}),
            'source path escape':lambda d,s:s['sourceFiles'].update({'../private':'f'*64})}
        for label,change in changes.items():
            with self.subTest(label=label),tempfile.TemporaryDirectory(prefix='cpu-evidence-negative-') as name:
                directory=Path(name);summary,expected=self.evidence_fixture(directory);change(directory,summary)
                with self.assertRaises((ValueError,AssertionError)):self.replay_evidence(directory,summary,expected)
    def test_checker_uses_selected_validator_code_and_rejects_selected_source_drift(self):
        with tempfile.TemporaryDirectory(prefix='cpu-source-reader-host-') as name:
            directory=Path(name);summary,expected=self.evidence_fixture(directory)
            path='tools/gecko/run_gecko_cpu_acceptance.py'
            selected=(ROOT/path).read_bytes().replace(b"'A production first-inline CPU cap/default mismatch remains'",b"'Selected validator mismatch'")
            # A source-bound validator rule must affect replay, even if the local
            # imported runner would otherwise accept the original case.
            selected=selected.replace(b"expected=4 if mode=='automatic' else int(mode)",b"expected=999")
            summary['sourceFiles'][path]=hashlib.sha256(selected).hexdigest()
            def reader(source,current):return selected if current==path else (ROOT/current).read_bytes()
            with self.assertRaises(ValueError):self.replay_evidence(directory,summary,expected,reader)
            with self.assertRaises(ValueError):self.replay_evidence(directory,summary,expected)
    def test_browser_wrapper_preserves_exact_original_bytes_and_propagates_failure(self):
        for exit_code in (0,1):
            with self.subTest(exit_code=exit_code),tempfile.TemporaryDirectory(prefix='cpu-wrapper-host-') as name:
                directory=Path(name);original=b'{"expectedBuildIdentity":{"controlledHostOnly":true}}\n\n'
                def run(command,cwd):
                    self.assertEqual(cwd,ROOT);self.assertIn('--apk',command);self.assertIn('--source',command)
                    raw=Path(command[command.index('--output')+1]);raw.mkdir();(raw/'results.json').write_bytes(original)
                    return subprocess.CompletedProcess(command,exit_code)
                args=['wrapper','--adb','host-only-adb','--apk','not-opened.apk','--source',SOURCE,'--output',str(directory)]
                with patch.object(cpu_wrapper.subprocess,'run',side_effect=run),patch.object(sys,'argv',args),\
                        patch.object(checker,'verify_gecko_cpu_evidence',return_value={'caseCount':10}) as checked,contextlib.redirect_stdout(io.StringIO()):
                    self.assertEqual(cpu_wrapper.main(),exit_code)
                self.assertEqual((directory/'gecko-cpu-results.json').read_bytes(),original)
                self.assertEqual(checked.call_count,1 if exit_code==0 else 0)
    def test_real_host_fixture_rejects_unbound_routes_replay_and_extra_packet_fields(self):
        server=CpuAcceptanceServer('/* host-only page */','/* host-only worker */',NONCE,SOURCE).start();self.addCleanup(server.close);server.begin(1,CASE)
        def request(method,path,body=None):
            connection=http.client.HTTPConnection('127.0.0.1',server.port,timeout=3)
            connection.request(method,path,body=body,headers={'Content-Type':'application/json'} if body else {})
            response=connection.getresponse();raw=response.read();connection.close();return response.status,raw
        path='/cpu/slot1/report?run='+NONCE+'&case='+CASE
        self.assertEqual(request('GET','http://public.invalid/private')[0],403)
        value=packet();self.assertEqual(request('POST',path,json.dumps(value))[0],200)
        self.assertEqual(request('POST',path,json.dumps(value))[0],400)
        value=packet('dedicated');value['private']='never-accepted'
        self.assertEqual(request('POST',path,json.dumps(value))[0],400)
        self.assertEqual(request('GET','/cpu/slot1/page?run='+NONCE+'&case='+'f'*32)[0],400)
        self.assertEqual(request('GET','/cpu/slot1/service.js')[0],200)
        self.assertEqual(request('GET','/cpu/slot1/service.js?case='+CASE)[0],400)
        self.assertEqual(len(server.evidence(CASE)['observations']),1)
        self.assertEqual(server.snapshot()['upstreamConnections'],0)
        self.assertFalse(server.snapshot()['forwardingImplemented'])
        for _ in range(520):server.response('GET','/__cpu-evidence?run='+NONCE+'&case='+CASE,{},io.BytesIO())
        snapshot=server.snapshot();self.assertEqual(snapshot['controlRequests'],520)
        self.assertFalse(snapshot['eventsTruncated']);self.assertNotIn('/__cpu-evidence',[event['path'] for event in snapshot['events']])
    def test_original_json_bounds_duplicates_and_nonfinite_rejected(self):
        for raw in (b'{"a":1,"a":2}',b'{"a":NaN}',b'[]',b'x'*262145):
            with self.assertRaises(ValueError):strict_json(raw)
    def test_actual_worker_asset_samples_before_messages_and_never_changes_getter(self):
        node=shutil.which('node');self.assertIsNotNone(node)
        program=r"""
const vm=require('node:vm'),fs=require('node:fs'),crypto=require('node:crypto').webcrypto;
const navigator=new ArrayBuffer(2),get=Object.getOwnPropertyDescriptor(ArrayBuffer.prototype,'byteLength').get;
Object.defineProperty(navigator,'hardwareConcurrency',{get});let result;
const self={postMessage(value){result=value;}};
vm.runInNewContext(fs.readFileSync(process.argv[1],'utf8'),{self,navigator,crypto});
self.onmessage({data:{kind:'cpu-first-inline',caseNonce:'d'.repeat(32)}});
if(result.observation.hardwareConcurrency!==2||result.observation.nativeGetter!==true||result.observation.firstInline!==true)throw Error('actual first sample absent');
if(Object.getOwnPropertyDescriptor(navigator,'hardwareConcurrency').get!==get)throw Error('getter replaced');
process.stdout.write(JSON.stringify({hostAsset:true,actualAndroidExecution:false,actualGeckoExecution:false}));
"""
        result=subprocess.run([node,'-e',program,str(ROOT/'tests/gecko/assets/cpu-acceptance-worker.js')],capture_output=True,text=True,timeout=10)
        self.assertEqual(result.returncode,0,result.stderr);value=json.loads(result.stdout);self.assertFalse(value['actualAndroidExecution']);self.assertFalse(value['actualGeckoExecution'])
    def test_runner_dispatch_preserves_real_cold_restart_then_same_runtime_concurrent_and_template_sequence(self):
        self.run_dispatch_fixture()
    def test_runner_server_close_failure_keeps_prior_error_and_runs_ca_uid_and_private_cleanup(self):
        for first_case_failure in (False,True):
            with self.subTest(first_case_failure=first_case_failure):
                self.run_dispatch_fixture(close_error=True,first_case_failure=first_case_failure)
    def run_dispatch_fixture(self,close_error=False,first_case_failure=False):
        # Explicit host command/transport fixtures only. No APK, ADB, certificates,
        # profile, native SDK or Android process is created by this test.
        with tempfile.TemporaryDirectory(prefix='cpu-production-dispatch-') as directory:
            base=Path(directory);output=base/'results';events=[];active={};payloads={};case_bindings={};serial=0
            class Certificates:
                leaf_sha='a'*64;ca_sha='b'*64;public={'controlledHostInputOnly':True}
                def __init__(self):self.directory=base/'fake-cert-directory';self.directory.mkdir()
                def close(self):events.append(('private-close',));self.directory.rmdir()
            class Ca:
                def __init__(self,adb,certificates):self.adb=adb;self.receipt={'controlledHostInputOnly':True}
                def install(self):pass
                def remove(self):
                    events.append(('ca-remove',))
                    uid=self.adb('shell','id','-u').stdout.strip();runner.require(uid==b'2000','Declared fake cleanup shell UID differs')
                    self.receipt.update(removedAfterExecution=True,cleanupShellUid=int(uid),shellRestoredAfterCleanup=True)
            class Server:
                port=32123
                def __init__(self,page,worker,run,source,cert):self.run=run
                def start(self):return self
                def close(self):
                    events.append(('server-close',))
                    if close_error:raise RuntimeError('Declared host-only server close failure')
                def begin(self,slot,case):case_bindings[case]=slot
                def evidence(self,case):return {'observations':payloads[case]['observations']}
                def snapshot(self):return {'controlledHostInputOnly':True,'upstreamConnections':0,'forwardingImplemented':False}
            def git(command,**kwargs):
                if command==['git','rev-parse','HEAD']:return SOURCE+'\n'
                if command==['git','rev-parse','HEAD^{tree}']:return TREE+'\n'
                if command==['git','status','--porcelain']:return ''
                raise AssertionError(command)
            def adb(command,**kwargs):
                nonlocal serial
                self.assertEqual(command[:3],['host-only-adb','-s','emulator-5554']);parts=command[3:];raw=b''
                if parts==['shell','getprop','ro.kernel.qemu']:raw=b'1'
                elif parts==['shell','getprop','ro.build.version.sdk']:raw=b'35'
                elif parts==['shell','id','-u']:events.append(('shell-uid',2000));raw=b'2000'
                elif parts==['shell','getconf','_NPROCESSORS_ONLN']:raw=b'4'
                elif parts==['exec-out','content','read','--uri','content://local.pocketchat.test.evidence/build-identity']:raw=json.dumps(IDENTITY).encode()
                elif parts[:1]==['reverse']:events.append(('reverse',tuple(parts)))
                elif parts==['shell','pm','clear','local.pocketchat.test']:raw=b'Success'
                elif parts==['shell','am','force-stop','local.pocketchat.test']:events.append(('stop',));active.clear()
                elif parts[:2]==['shell','pidof']:
                    slot=int(parts[2][-1]);raw=str(active[slot]['pid']).encode() if slot in active else b''
                elif len(parts)==2 and parts[0]=='shell':
                    tokens=shlex.split(parts[1]);self.assertEqual(tokens[:3],['am','start','-W']);slot=int(tokens[4][-1])
                    extras={tokens[index+1]:tokens[index+2] for index in range(5,len(tokens),3)}
                    mode=extras['cpuMode'];rfp=extras['rfp']=='true';retain=extras['retain']=='true';stale=extras['staleUser']=='true'
                    resample=extras['resample']=='true';template=extras['templateApply']=='true'
                    if slot not in active:
                        self.assertFalse(resample or template);serial+=1;active[slot]={'pid':2000+serial,'nonce':format(serial,'032x')}
                    else:self.assertTrue(resample or template)
                    owner=active[slot];value=report(mode,rfp,retain,stale);value['runNonce']=extras['runNonce'];value['caseNonce']=extras['caseNonce'];value['slot']=slot
                    value['identityApplyInvoked']=template;value['identityApplyCompleted']=template
                    if template:value['identityPolicyBefore']=2;value['identityPolicyRevision']=3
                    value['process'].update(pid=owner['pid'],name='local.pocketchat.test:profile'+str(slot))
                    for key in ('cpuPolicy','runtimeCpuPolicy'):
                        value[key].update(pid=owner['pid'],slot=slot,processNonce=owner['nonce'],runtimeNonce=owner['nonce'],environmentId='00000000-0000-0000-0000-'+str(slot).zfill(12))
                    value['navigation']['targetPath']='/cpu/slot'+str(slot)+'/page'
                    for row in value['observations']:
                        row.update(runNonce=extras['runNonce'],caseNonce=extras['caseNonce'],slot=slot)
                        if row['role']=='service':row['observation']['bootNonce']=owner['nonce'];row['service']['scriptPath']='/cpu/slot'+str(slot)+'/service.js';row['service']['scopePath']='/cpu/slot'+str(slot)+'/'
                    if first_case_failure and len(payloads)==0:value['observations'][0]['observation']['nativeGetter']=False
                    payloads[extras['caseNonce']]=value;events.append(('launch',slot,mode,rfp,resample,template))
                elif parts[:4]==['exec-out','content','read','--uri']:
                    case=parts[4].split('/')[-2];raw=(json.dumps(payloads[case],indent=1)+'\n\n').encode()
                else:raise AssertionError(command)
                return subprocess.CompletedProcess(command,0,stdout=raw,stderr=b'')
            args=['runner','--adb','host-only-adb','--apk',str(base/'never-opened.apk'),'--source',SOURCE,'--output',str(output)]
            with patch.object(runner.subprocess,'check_output',side_effect=git),patch.object(runner.subprocess,'run',side_effect=adb),\
                    patch.object(runner,'snapshot',return_value={}),patch.object(runner,'expected_build',return_value=IDENTITY),\
                    patch.object(runner,'verify_installed'),patch.object(runner,'CpuAcceptanceServer',Server),\
                    patch.object(runner,'EphemeralCertificates',Certificates),patch.object(runner,'AndroidUserCa',Ca),\
                    patch.object(sys,'argv',args),contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(runner.main(),1 if close_error or first_case_failure else 0)
            value=json.loads((output/'results.json').read_text());self.assertEqual(len(value['caseRecords']),10)
            launches=[event for event in events if event[0]=='launch'];self.assertEqual(len(launches),10)
            self.assertEqual(launches[-4:],[('launch',1,'1',False,False,False),('launch',2,'2',False,False,False),('launch',1,'1',False,True,False),('launch',1,'1',True,False,True)])
            positions=[index for index,event in enumerate(events) if event[0]=='launch'];first=positions[-4];last=positions[-1];self.assertNotIn(('stop',),events[first:last])
            self.assertFalse(value['releaseAcceptance']);self.assertFalse(value['workerCoverageVerified'])
            self.assertEqual(value['status'],'failed' if close_error or first_case_failure else 'passed')
            self.assertTrue(all(value['cleanup'].values()));self.assertFalse((base/'fake-cert-directory').exists())
            installation=value['hostTls']['trustInstallation'];self.assertTrue(installation['removedAfterExecution'])
            self.assertTrue(installation['shellRestoredAfterCleanup']);self.assertEqual(installation['cleanupShellUid'],2000)
            self.assertLess(events.index(('server-close',)),events.index(('ca-remove',)))
            self.assertLess(events.index(('ca-remove',)),events.index(('private-close',)))
            if close_error:
                self.assertIn(dict(stage='server-close-cleanup',errorType='RuntimeError'),value['errors'])
                if first_case_failure:self.assertEqual(value['errors'][0],dict(label='cap1',errorType='ValueError'))
                else:self.assertEqual(value['errors'],[dict(stage='server-close-cleanup',errorType='RuntimeError')])
            for entry in value['caseRecords']:
                raw=(output/entry['report']).read_bytes();self.assertEqual(raw,(json.dumps(payloads[entry['caseNonce']],indent=1)+'\n\n').encode())

    def test_gate_uses_only_production_bootstrap_and_readonly_observation(self):
        activity=(ROOT/'tests/gecko/GeckoCpuAcceptanceActivity.java').read_text();provider=(ROOT/'tests/gecko/GeckoCpuAcceptanceProvider.java').read_text()
        self.assertIn('extends MainActivity',activity);self.assertIn('extends GeckoWebView',activity)
        self.assertIn('session.cpu.status()',activity);self.assertIn('remote.nativeRuntimeCapabilities()',activity)
        self.assertIn('GeckoCpuStore.save',activity);self.assertIn('seed.join(8000)',activity)
        for token in ('setIntPref','nsIPrefBranch','setPreference','getPreferenceController','evaluateJavascript','TimeZone.setDefault'):
            self.assertNotIn(token,activity)
        self.assertIn('Binder.getCallingUid()!=2000',provider);self.assertIn('262144',provider)
        production=(ROOT/'app/src/main/AndroidManifest.xml').read_text();self.assertNotIn('GeckoCpuAcceptance',production)
        for name in ('page','worker'):
            asset=(ROOT/('tests/gecko/assets/cpu-acceptance-'+name+'.js')).read_text()
            for token in ('Object.defineProperty','Reflect.defineProperty','__defineGetter__','navigator.hardwareConcurrency ='):
                self.assertNotIn(token,asset)
    def test_workflow_exact_source_same_run_restore_fixed_four_cpu_and_readonly_permissions(self):
        workflow=yaml.safe_load((ROOT/'.github/workflows/gecko-cpu-acceptance.yml').read_text())
        original=yaml.safe_load((ROOT/'.github/workflows/browser-2_1-acceptance.yml').read_text())
        self.assertEqual(workflow['permissions'],{'contents':'read'});self.assertEqual(workflow['on']['push']['branches'],['diagnostics/gecko-cpu-*'])
        self.assertEqual(workflow['env'],original['env']);self.assertEqual(set(workflow['jobs']),{'build','gecko_cpu_acceptance'})
        build=workflow['jobs']['build'];diagnostic=workflow['jobs']['gecko_cpu_acceptance'];self.assertEqual(diagnostic['needs'],'build')
        self.assertEqual(build['steps'][:5],original['jobs']['build']['steps'][:5])
        upload=next(s for s in build['steps'] if s.get('name')=='Transfer exact same-run diagnostic APKs and SDK classpath')
        download=next(s for s in diagnostic['steps'] if s.get('name')=='Download only this run and attempt diagnostic build')
        self.assertEqual(upload['with']['name'],download['with']['name']);self.assertIn('${{ github.run_attempt }}',upload['with']['name'])
        boot=next(s for s in diagnostic['steps'] if s.get('id')=='boot')['run']
        for token in ('-cores 4','-accel on','ANDROID_CAPACITY_PREFLIGHT'):self.assertIn(token,boot)
        for job in workflow['jobs'].values():
            for step in job['steps']:
                code=step.get('run','');result=subprocess.run(['bash','-n'],input=code,capture_output=True,text=True,timeout=5);self.assertEqual(result.returncode,0,result.stderr)
                for marker in ('PYCODE','CPU_BUILD','CPU_RESTORE','CPU_HEALTH'):
                    start="python3 - <<'"+marker+"'"
                    if start in code:compile(code.split(start,1)[1].split('\n'+marker,1)[0].lstrip('\n'),step.get('name','shell'),'exec')
        compile(workflow['env']['ANDROID_CAPACITY_PREFLIGHT'],'capacity','exec')
        self.assertNotIn('native_hardware_probe',str(workflow));self.assertNotIn('nsIPref',str(workflow))

    def test_actual_health_collector_is_bounded_and_reads_only_fixed_emulator_log(self):
        value=yaml.safe_load((ROOT/'.github/workflows/gecko-cpu-acceptance.yml').read_text())
        step=next(s for s in value['jobs']['gecko_cpu_acceptance']['steps']
                  if s.get('name')=='Capture bounded read-only emulator startup health')
        code=step['run'].split("python3 - <<'CPU_HEALTH'",1)[1].split('\nCPU_HEALTH',1)[0].lstrip('\n')
        for symlink in (False,True):
            with self.subTest(symlink=symlink),tempfile.TemporaryDirectory(prefix='hardware-health-host-') as directory:
                temporary=Path(directory);base=temporary/'work/gecko-integration';base.mkdir(parents=True)
                (base/'gecko-cpu-acceptance-boot.exit').write_text('124\n')
                (base/'gecko-cpu-acceptance-emulator.exit').write_text('1\n')
                (base/'gecko-cpu-acceptance-emulator.pid').write_text('../../private')
                (base/'other-private.log').write_text('NEVER_READ_OTHER_LOG')
                if symlink:(base/'emulator.log').symlink_to(base/'other-private.log')
                else:(base/'emulator.log').write_text('x'*100000+'\nPANIC: controlled emulator failure\n')
                ran=subprocess.run([sys.executable,'-c',code],cwd=temporary,
                    env=dict(os.environ,ANDROID_HOME=str(temporary/'missing-sdk'),BOOT_STEP_OUTCOME='failure'),
                    capture_output=True,text=True,timeout=10)
                self.assertEqual(ran.returncode,0,ran.stderr)
                path=temporary/'work/gecko-cpu-acceptance-probe-host/emulator-health.json'
                raw=path.read_bytes();result=json.loads(raw)
                self.assertLessEqual(len(raw),32768)
                self.assertEqual(result['bootExitCode'],124);self.assertEqual(result['emulatorExitCode'],1)
                self.assertFalse(result['rootCauseEstablished'])
                self.assertNotIn('NEVER_READ_OTHER_LOG',raw.decode())
                if symlink:self.assertEqual(result['emulatorLog']['error'],'missing-or-nonregular')
                else:
                    self.assertLessEqual(result['emulatorLog']['tailBytes'],8192)
                    self.assertIn('controlled emulator failure',result['emulatorLog']['tailUtf8'])
                    self.assertTrue(result['emulatorLog']['tailOnly'])

    def test_actual_restore_rejects_stale_or_corrupt_transport_before_native_execution(self):
        # Transport-only synthetic byte fixtures. No fixture is opened as an APK
        # or SDK, compiled, run on Android, or described as a real engine input.
        workflow=yaml.safe_load((ROOT/'.github/workflows/gecko-cpu-acceptance.yml').read_text())
        step=next(s for s in workflow['jobs']['gecko_cpu_acceptance']['steps']
                  if s.get('name')=='Verify and restore exact selected-source SDK and APK bytes')
        code=step['run'].split("python3 - <<'CPU_RESTORE'",1)[1].split('\nCPU_RESTORE',1)[0].lstrip('\n')
        namespace={}
        prefix=code.split("root=pathlib.Path('work/gecko-cpu-acceptance-build-download')",1)[0]
        exec(compile(prefix,'restore-allowlist','exec'),namespace)
        allowed=namespace['allowed']
        for fault in (None,'source','tree','run','attempt','unknown-path','duplicate',
                      'extra-file','corrupt-bytes','boolean-size','symlink','existing-target'):
            with self.subTest(fault=fault),tempfile.TemporaryDirectory(prefix='hardware-transfer-host-') as directory:
                temporary=Path(directory);download=temporary/'work/gecko-cpu-acceptance-build-download'
                rows=[]
                for index,name in enumerate(allowed):
                    p=download/name;p.parent.mkdir(parents=True,exist_ok=True)
                    raw=('Explicit transport-only synthetic byte fixture '+str(index)).encode();p.write_bytes(raw)
                    rows.append(dict(path=name,bytes=len(raw),sha256=hashlib.sha256(raw).hexdigest()))
                value=dict(schema=1,kind='gecko-cpu-acceptance-build',sourceCommit=SOURCE,sourceTree=TREE,
                           runId='7',runAttempt='1',diagnosticOnly=True,releaseAcceptance=False,files=rows)
                if fault=='source':value['sourceCommit']='f'*40
                if fault=='tree':value['sourceTree']='f'*40
                if fault=='run':value['runId']='8'
                if fault=='attempt':value['runAttempt']='2'
                if fault=='unknown-path':rows[0]['path']='../../never-read'
                if fault=='duplicate':rows[1]=copy.deepcopy(rows[0])
                if fault=='extra-file':(download/'unknown-file').write_text('Never copied')
                if fault=='corrupt-bytes':(download/allowed[0]).write_bytes(b'corrupt')
                if fault=='boolean-size':rows[0]['bytes']=True
                if fault=='symlink':
                    (download/allowed[0]).unlink();(download/allowed[0]).symlink_to(download/allowed[1])
                if fault=='existing-target':
                    target=temporary/allowed[0];target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(b'old')
                manifest=download/'work/gecko-cpu-acceptance-build/manifest.json'
                manifest.parent.mkdir(parents=True,exist_ok=True);manifest.write_text(json.dumps(value))
                def git(command,**kwargs):
                    if command==['git','rev-parse','HEAD']:return SOURCE+'\n'
                    if command==['git','rev-parse','HEAD^{tree}']:return TREE+'\n'
                    if command==['git','status','--porcelain']:return ''
                    raise AssertionError('Unexpected transport command')
                previous=Path.cwd()
                try:
                    os.chdir(temporary)
                    with patch.dict(os.environ,GITHUB_SHA=SOURCE,GITHUB_REPOSITORY='Ararataki-number-one/yuanying-chat',
                                    GITHUB_REPOSITORY_ID='1401080063',GITHUB_RUN_ID='7',GITHUB_RUN_ATTEMPT='1'),\
                            patch.object(subprocess,'check_output',side_effect=git),\
                            contextlib.redirect_stdout(io.StringIO()):
                        if fault is None:
                            exec(compile(code,'actual-restore-protocol','exec'),{})
                            for row in rows:
                                self.assertEqual(hashlib.sha256((temporary/row['path']).read_bytes()).hexdigest(),row['sha256'])
                            proof=json.loads((temporary/'work/gecko-cpu-acceptance-probe-host/build-restore.json').read_text())
                            self.assertFalse(proof['actualAndroidExecution'])
                        else:
                            with self.assertRaises(AssertionError):exec(compile(code,'actual-restore-protocol','exec'),{})
                            self.assertFalse((temporary/'work/gecko-cpu-acceptance-probe-host/build-restore.json').exists())
                finally:os.chdir(previous)
def check_packages(args):
    from caret_build_identity import dex_definitions
    require=lambda condition,message:None if condition else (_ for _ in ()).throw(ValueError(message))
    require(all(path is not None and path.is_file() for path in (args.integration_apk,args.release_apk,args.aapt2)),'Actual compiled APKs/aapt2 required')
    definitions=[]
    for path in (args.integration_apk,args.release_apk):
        classes=set()
        with ZipFile(path) as archive:
            for name in archive.namelist():
                if name.endswith('.dex'):classes.update(dex_definitions(archive.read(name)))
        definitions.append(classes)
    prefix='Llocal/pocketchat/GeckoCpuAcceptance'
    require({prefix+'Activity;',prefix+'Activity$Profile1;',prefix+'Activity$Profile2;',prefix+'Provider;'}<=definitions[0],'Actual integration gate definitions absent')
    require(not any(name.startswith(prefix) for name in definitions[1]),'Gate classes leaked into production')
    require({'Llocal/pocketchat/'+name+';' for name in ('GeckoCpuController','GeckoCpuNative','GeckoCpuStore','GeckoCpuSpec')}<=definitions[1],'Actual production CPU implementation absent')
    with ZipFile(args.integration_apk) as archive:
        require(all(archive.namelist().count('assets/cpu-acceptance-'+name+'.js')==1 for name in ('page','worker')),'Actual integration first-inline scripts absent/duplicated')
    with ZipFile(args.release_apk) as archive:require(not any(name.startswith('assets/cpu-acceptance-') for name in archive.namelist()),'Gate assets leaked into production')
    manifest=[]
    for path in (args.integration_apk,args.release_apk):manifest.append(subprocess.check_output([str(args.aapt2),'dump','xmltree',str(path),'--file','AndroidManifest.xml'],text=True))
    require(all(name in manifest[0] for name in ('GeckoCpuAcceptanceActivity$Profile1','GeckoCpuAcceptanceActivity$Profile2','GeckoCpuAcceptanceProvider','local.pocketchat.test.cpu-acceptance')),'Actual integration gate manifest absent')
    require('GeckoCpuAcceptance' not in manifest[1],'Gate component leaked into production')
    source=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip();tree=subprocess.check_output(['git','rev-parse','HEAD^{tree}'],cwd=ROOT,text=True).strip()
    require(not subprocess.check_output(['git','status','--porcelain'],cwd=ROOT,text=True).strip(),'Package audit requires clean selected source')
    value=dict(schema=1,status='passed',sourceCommit=source,sourceTree=tree,diagnosticOnly=True,releaseAcceptance=False,actualAndroidExecution=False,
        integrationApkSha256=runner.sha(args.integration_apk),releaseApkSha256=runner.sha(args.release_apk),productionCpuDefinitionsPresent=True,
        testGateDefinitionsAbsentInProduction=True,testGateAssetsAbsentInProduction=True,testGateComponentsAbsentInProduction=True)
    args.output.parent.mkdir(parents=True,exist_ok=True);args.output.write_text(json.dumps(value,indent=2)+'\n');print(json.dumps(value))

if __name__=='__main__':
    parser=argparse.ArgumentParser(add_help=False);parser.add_argument('--check-packages',action='store_true');parser.add_argument('--integration-apk',type=Path)
    parser.add_argument('--release-apk',type=Path);parser.add_argument('--aapt2',type=Path);parser.add_argument('--output',type=Path);args,remaining=parser.parse_known_args()
    if args.check_packages:
        if args.output is None:parser.error('--output required')
        check_packages(args)
    else:unittest.main(argv=[sys.argv[0],*remaining],verbosity=2)
