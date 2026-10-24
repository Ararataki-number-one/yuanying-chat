"""Driver scheduler and fail-closed evidence controls. No device execution."""
import copy
import importlib.util
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools/gecko'))
import native_input_contract as C
import native_input_driver as D
from native_input_signature_fixture import signature_files


def receipt(purpose='qualification'):
    source, tree, nonce = 'a' * 40, 'b' * 40, 'c' * 32
    build = dict(schema=1, status='built', compileOnly=False, testOnly=True, sourceCommit=source, sourceTree=tree, runId='123', runAttempt='1',
                 packageName=C.SELF, targetPackage=C.TARGET, instrumentationTargetPackage=C.SELF,
                 instrumentation=C.SELF + '.NativeInputInstrumentation', protocols=C.PROTOCOLS,
                 inputs={name: C.sha((ROOT / name).read_bytes()) for name in C.INPUTS},
                 apkSha256='d' * 64, apkBytes=10, signerCertificateSha256='e' * 64)
    build.update(C.BACKEND)
    signature_files(build, C.sha((ROOT / C.SIGNATURE_VERIFIER).read_bytes()))
    request = dict(x=540, startY=1469, endY=567, targetPid='1234', expiresUptimeMs=21000,
                   targetByteProofSha256='f' * 64, targetApkPath='/data/app/test/base.apk', targetApkBytes=100)
    p = C.PROTOCOLS[purpose]; rows = []
    for i in range(21):
        at = 1000 + i * p['intervalMs']
        rows.append(dict(action=0 if i == 0 else 1 if i == 20 else 2, downTime=1000, plannedUptimeMs=at,
                         eventTime=at, callStartUptimeMs=at, callEndUptimeMs=at, x=540,
                         y=1469 + (567 - 1469) * i / 20, injected=True, accepted=True, cleanup=False, sync=i == 20, error=''))
    target = dict(sourceCommit=source, sourceTree=tree, dirtySource=False)
    value = dict(schema=1, status='passed', sourceCommit=source, sourceTree=tree, nonce=nonce,
                 gesture='baseline-scroll' if purpose == 'qualification' else 'formal-collapse', purpose=purpose,
                 packageName=C.SELF, targetPackage=C.TARGET, buildIdentity=copy.deepcopy(build),
                 driverApkSha256=build['apkSha256'], targetApkSha256='1' * 64,
                 signerCertificateSha256=build['signerCertificateSha256'], targetBuildIdentity=target,
                 targetBuildIdentityAfter=copy.deepcopy(target), targetPidBefore='1234', targetPidAfter='1234',
                 targetApkHashSource='preflight-installed-byte-proof', targetByteProofSha256='f' * 64,
                 targetApkPathBefore=request['targetApkPath'], targetApkPathAfter=request['targetApkPath'],
                 targetApkBytesBefore=100, targetApkBytesAfter=100, targetLastModifiedBefore=50,
                 targetLastModifiedAfter=50, targetLastUpdateBefore=40, targetLastUpdateAfter=40,
                 createdUptimeMs=480, startedUptimeMs=500, connectStartUptimeMs=700, connectEndUptimeMs=850, readyUptimeMs=900, startupMs=400, finishedUptimeMs=1400, expiresUptimeMs=21000,
                 trace=dict(startUptimeMs=1000, expiresUptimeMs=21000, **p, events=rows, error='', cleanup=None))
    focus = dict(displayId=0,packageName=C.TARGET,component=C.TARGET+'/local.pocketchat.GeckoPerformanceIntegrationActivity',
                 raw='  mCurrentFocus=Window{abcd u0 local.pocketchat.test/local.pocketchat.GeckoPerformanceIntegrationActivity}\n  mTopFocusedDisplayId=0\n')
    value.update(executionBackend=C.BACKEND['executionBackend'],executionUid=2000,inputTargetUid=10123,
                 targetUidBefore=10123,targetUidAfter=10123,targetStartTicksBefore='200',targetStartTicksAfter='200',
                 driverPid=456,driverStartTicks='300',displayId=0,focusBefore=focus,focusAfter=copy.deepcopy(focus),
                 tracePersistence='memory-until-terminal')
    kwargs = dict(build=build, purpose=purpose, nonce=nonce, gesture=value['gesture'], target_apk='1' * 64, request=request)
    return value, kwargs


class ContractControls(unittest.TestCase):
    def qualification(self, directory):
        value, kwargs = receipt(); build = kwargs['build']; nonce = value['nonce']
        for name, raw in signature_files(build, C.sha((ROOT / C.SIGNATURE_VERIFIER).read_bytes())).items():
            (directory / name).write_bytes(raw)
        (directory / 'native-input-driver-build.json').write_text(json.dumps(build))
        proof = dict(schema=1, status='verified-bytes', actualInstalledApkRead=True, compiledFileFallback=False,
                     retryPerformed=False, returnCode=0, transport='adb-shell-v2-no-pty-ranged',
                     dataSource='binary-stdout-destination-file', actualFileSha256='1' * 64, stdoutSha256='1' * 64,
                     expectedSha256='1' * 64, actualFileBytes=100, stdoutBytes=100, expectedBytes=100,
                     rangeBytes=4194304, installedApkPath='/data/app/test/base.apk',
                     ranges=[dict(index=0, offset=0, actualBytes=100, expectedBytes=100, returnCode=0,
                                  status='verified-length', sha256='2' * 64)])
        proof_raw = json.dumps(proof).encode(); proof_name = 'native-input-target-proof-' + nonce + '.json'
        (directory / proof_name).write_bytes(proof_raw)
        report = dict(actualAndroidGestures=[], actualAndroidGestureDeadlines=[], nativeInputDriver=dict(
            purpose='qualification', nonce=nonce, buildSha256=C.sha((directory / 'native-input-driver-build.json').read_bytes()),
            targetByteProofFile=proof_name, targetByteProofSha256=C.sha(proof_raw), receipts=[]))
        phases = []
        for phase in ('baseline', 'current'):
            item = copy.deepcopy(value); item['gesture'] = phase + '-scroll'; item['targetByteProofSha256'] = C.sha(proof_raw)
            request = copy.deepcopy(kwargs['request']); request['targetByteProofSha256'] = C.sha(proof_raw)
            name = 'native-input-' + nonce + '-' + item['gesture'] + '.json'
            raw = json.dumps(item).encode(); (directory / name).write_bytes(raw)
            report['nativeInputDriver']['receipts'].append(dict(file=name, sha256=C.sha(raw), gesture=item['gesture'], request=request))
            report['actualAndroidGestures'].append(dict(id=item['gesture'], x=540, startY=1469, endY=567))
            report['actualAndroidGestureDeadlines'].append(dict(id=item['gesture'], sampledElapsedMs=1000,
                sampledUptimeMs=1000, expiresElapsedMs=21000, expiresUptimeMs=21000))
            native = {key: True for key in ('sameNavigation', 'sameSession', 'sameSurface', 'sameUrl', 'windowFocused', 'webShown', 'surfaceShown', 'surfaceAttached')}
            native['browserPaused'] = False
            sample = dict(native=native, dom=dict(document=100 if phase == 'baseline' else 200, url='fixture/' + phase))
            phases.append(dict(phase=phase, outcome='passed', samples=[sample, copy.deepcopy(sample)],
                               nativeTouches=[dict(action=0, superHandled=True), dict(action=2, superHandled=True)],
                               domEvents=[dict(type='touchstart', trusted=True)]))
        scroll = dict(run=nonce, sourceCommit=build['sourceCommit'], actualAndroidFileRead=True, phases=phases)
        (directory / 'gecko-scroll-diagnostics.json').write_text(json.dumps(scroll))
        return report, scroll, build

    def test_complete_raw_qualification_and_legal_coalescing(self):
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary); report, _, build = self.qualification(directory)
            result = C.verify_qualification(directory, report, build['sourceCommit'], lambda s, p: (ROOT / p).read_bytes(), '1' * 64, ('123', '1'))
            self.assertEqual(result['receiptCount'], 2)
            # The passive receiver may stop after its first real MOVE; no
            # requirement for nineteen individual deliveries or captured UP.

    def test_missing_raw_move_document_and_run_cannot_qualify(self):
        for scenario in ('missing-receipt', 'missing-proof', 'missing-move', 'changed-document', 'wrong-run', 'forged-signature'):
            with self.subTest(scenario=scenario), tempfile.TemporaryDirectory() as temporary:
                directory = Path(temporary); report, scroll, build = self.qualification(directory)
                if scenario == 'missing-receipt': (directory / report['nativeInputDriver']['receipts'][0]['file']).unlink()
                if scenario == 'missing-proof': (directory / report['nativeInputDriver']['targetByteProofFile']).unlink()
                if scenario == 'missing-move': scroll['phases'][0]['nativeTouches'].pop()
                if scenario == 'changed-document': scroll['phases'][0]['samples'][1]['dom']['document'] += 1
                if scenario == 'forged-signature': (directory / 'native-input-driver-signature-stdout.log').write_text('not an actual signer')
                (directory / 'gecko-scroll-diagnostics.json').write_text(json.dumps(scroll))
                with self.assertRaises((ValueError, FileNotFoundError)):
                    C.verify_qualification(directory, report, build['sourceCommit'], lambda s, p: (ROOT / p).read_bytes(), '1' * 64,
                                           ('999', '1') if scenario == 'wrong-run' else ('123', '1'))

    def test_two_exact_protocols(self):
        for purpose in C.PROTOCOLS:
            value, kwargs = receipt(purpose); C.verify_receipt(value, **kwargs)
        self.assertEqual(C.PROTOCOLS['qualification']['durationMs'], 300)
        self.assertEqual(C.PROTOCOLS['formal-collapse']['durationMs'], 320)

    def test_reject_incomplete_replayed_late_and_unbound_receipts(self):
        changes = [lambda v: v.update(status='failed'), lambda v: v.update(nonce='0' * 32),
                   lambda v: v.update(targetPidAfter='999'), lambda v: v.update(targetLastUpdateAfter=41),
                   lambda v: v.update(signerCertificateSha256='0' * 64),
                   lambda v: v['trace']['events'].pop(1), lambda v: v['trace']['events'].append(copy.deepcopy(v['trace']['events'][-1])),
                   lambda v: v['trace']['events'][1].update(eventTime=1046, callStartUptimeMs=1046, callEndUptimeMs=1046),
                   lambda v: v['trace']['events'][1].update(callStartUptimeMs=1046, callEndUptimeMs=1046),
                   lambda v: v['trace']['events'][1].update(accepted=False),
                   lambda v: v['trace']['events'][1].update(downTime=1015),
                   lambda v: v['trace']['events'][1].update(plannedUptimeMs=1016),
                   lambda v: v['trace']['events'][20].update(sync=False),
                   lambda v: v['trace']['events'][1].update(sync=True),
                   lambda v: v['trace']['events'][20].update(callEndUptimeMs=22000),
                   lambda v: v['trace'].update(cleanup={'action': 3}),
                   lambda v: v['trace'].update(durationMs=1000),
                   lambda v: v['trace']['events'][1].update(y=100),
                   lambda v: v.update(targetApkHashSource='guessed')]
        for change in changes:
            value, kwargs = receipt(); change(value)
            with self.subTest(change=changes.index(change)), self.assertRaises((ValueError, KeyError)):
                C.verify_receipt(value, **kwargs)

    def test_build_uses_exact_selected_java_and_self_target(self):
        _, kwargs = receipt(); build = kwargs['build']
        reader = lambda source, name: (ROOT / name).read_bytes()
        C.verify_build(build, build['sourceCommit'], reader)
        bad = copy.deepcopy(build); bad['instrumentationTargetPackage'] = C.TARGET
        with self.assertRaises(ValueError): C.verify_build(bad, build['sourceCommit'], reader)
        bad = copy.deepcopy(build); bad['inputs'][next(iter(C.INPUTS))] = '0' * 64
        with self.assertRaises(ValueError): C.verify_build(bad, build['sourceCommit'], reader)
        bad = copy.deepcopy(build); bad['signatureVerifierSourceSha256'] = '0' * 64
        with self.assertRaises(ValueError): C.verify_build(bad, build['sourceCommit'], reader)

    def test_signature_api_rejects_semantic_substitution_even_with_rebound_file_hashes(self):
        changes = [lambda v: v.update(verified=False), lambda v: v.update(containsErrors=True),
                   lambda v: v.update(inputsUnchangedDuringVerification=False),
                   lambda v: v.pop('inputsUnchangedDuringVerification'),
                   lambda v: v.update(sourceCommit='0' * 40), lambda v: v.update(runId='999'),
                   lambda v: v.update(apkSha256='0' * 64), lambda v: v.update(apkBytes=11),
                   lambda v: v.update(apksignerJarSha256='0' * 64),
                   lambda v: v.update(loadedApksignerJarPath='shadow/apksigner.jar'),
                   lambda v: v.update(verifierSourceSha256='0' * 64),
                   lambda v: v.update(effectiveSignerCertificateSha256=['e' * 64, 'e' * 64]),
                   lambda v: v.update(lineagePresent=True, lineageCertificateSha256=['e' * 64]),
                   lambda v: v.update(ignoredV1SignerCertificateSha256=['e' * 64]),
                   lambda v: v.update(v32Detected=True),
                   lambda v: v['schemes'][0].update(signerCertificateSha256=['e' * 64]),
                   lambda v: v['schemes'][2].update(signerCertificateSha256=['f' * 64]),
                   lambda v: v['schemes'][2]['signers'][0].update(certificateChainSha256=['e' * 64, 'e' * 64]),
                   lambda v: v['schemes'][2]['signers'][0].update(containsErrors=True),
                   lambda v: v['schemes'][2]['signers'][0].update(lineagePresent=True),
                   lambda v: v['schemes'][2]['signers'][0].update(signerTargetsDevRelease=True),
                   lambda v: v['schemes'][2]['signers'][0].update(rotationTargetsDevRelease=True)]
        for change in changes:
            with self.subTest(case=changes.index(change)), tempfile.TemporaryDirectory() as temporary:
                directory = Path(temporary); _, _, build = self.qualification(directory)
                value = C.decode((directory / C.SIGNATURE_API).read_bytes()); change(value)
                raw = json.dumps(value).encode()
                (directory / C.SIGNATURE_API).write_bytes(raw)
                (directory / 'native-input-driver-signature-api-stdout.log').write_bytes(raw)
                build['signatureApiSha256'] = C.sha(raw)
                build['signatureApiLogs']['native-input-driver-signature-api-stdout.log'] = C.sha(raw)
                with self.assertRaises((ValueError, KeyError)):
                    C.verify_signature_logs(directory, build)

    def test_signature_api_original_files_and_exit_codes_are_required(self):
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary); _, _, build = self.qualification(directory)
            C.verify_signature_logs(directory, build)
            for name in (*build['signatureLogs'], *build['signatureApiLogs'], C.SIGNATURE_API):
                path = directory / name; raw = path.read_bytes(); path.unlink()
                with self.subTest(missing=name), self.assertRaises(FileNotFoundError):
                    C.verify_signature_logs(directory, build)
                path.write_bytes(raw)
                path.write_bytes(raw + b' ')
                with self.subTest(changed=name), self.assertRaises(ValueError):
                    C.verify_signature_logs(directory, build)
                path.write_bytes(raw)
            for field in ('signatureCliReturnCode', 'signatureApiReturnCode'):
                for bad in (1, False, '0'):
                    changed = copy.deepcopy(build); changed[field] = bad
                    with self.subTest(field=field, bad=bad), self.assertRaises(ValueError):
                        C.verify_signature_logs(directory, changed)

    def test_strict_json_duplicate_and_nonfinite(self):
        for raw in [b'{"x":1,"x":2}', b'{"x":NaN}']:
            with self.assertRaises(ValueError): C.decode(raw)

    def test_shell_backend_generation_uid_and_focus_required(self):
        edits = [lambda v:v.update(executionBackend='uiautomation'),lambda v:v.update(executionUid=1000),
                 lambda v:v.update(inputTargetUid=-1),lambda v:v.update(inputTargetUid=True),
                 lambda v:v.update(targetUidAfter=10124),lambda v:v.update(targetStartTicksAfter='201'),
                 lambda v:v.update(driverPid=False),lambda v:v.update(displayId=1),
                 lambda v:v.update(tracePersistence='per-event-disk'),
                 lambda v:v['focusBefore'].update(raw='mCurrentFocus=null\n'),
                 lambda v:v['focusAfter'].update(raw=v['focusAfter']['raw'].replace('DisplayId=0','DisplayId=1')),
                 lambda v:v['focusAfter'].update(component=C.TARGET+'/wrong.Activity')]
        for edit in edits:
            value,kwargs=receipt();edit(value)
            with self.subTest(edit=edits.index(edit)),self.assertRaises((ValueError,KeyError)):
                C.verify_receipt(value,**kwargs)

    def test_failed_native_command_retains_raw_and_never_replays(self):
        with tempfile.TemporaryDirectory() as temporary:
            d = object.__new__(D.NativeInputDriver); d.out = Path(temporary); d.nonce = 'a' * 32
            d.invoked = set(); d.receipts = []; d.source = 'b' * 40
            d.build = dict(sourceTree='c' * 40, apkSha256='d' * 64,**C.BACKEND)
            d.installed_path='/data/app/driver/base.apk'
            d.target_hash = 'e' * 64; d.target_proof_raw = b'actual proof'; d.target_proof = dict(installedApkPath='/data/app/test/base.apk', actualFileBytes=100)
            commands = []
            def command(*parts, **kwargs):
                commands.append(parts)
                if parts == ('shell','pidof',C.TARGET): return subprocess.CompletedProcess([],0,b'1234\n',b'')
                if parts[:2] == ('shell','pidof'): return subprocess.CompletedProcess([],1,b'',b'')
                if parts[:2] == ('shell','-T') and parts[2].startswith('exec env '):
                    raise subprocess.TimeoutExpired(parts,20,output=b'original partial stdout\xc2',stderr=b'original stderr')
                if parts[:2] in [('shell','mkdir'),('shell','test')]:return subprocess.CompletedProcess([],0,b'',b'')
                return subprocess.CompletedProcess([],1,b'',b'no device receipt')
            d.command = command
            gesture = dict(id='baseline-scroll', x=540, startY=1469, endY=567)
            with self.assertRaises(subprocess.TimeoutExpired): d.inject(gesture, expires_uptime_ms=21000)
            with self.assertRaisesRegex(ValueError, 'replay'): d.inject(gesture, expires_uptime_ms=21000)
            launches=[p for p in commands if p[:2]==('shell','-T') and p[2].startswith('exec env ')]
            self.assertEqual(len(launches),1)
            self.assertIn('CLASSPATH=/data/app/driver/base.apk',launches[0][2])
            self.assertIn('/system/bin/app_process /system/bin --nice-name=pocketchat-input-',launches[0][2])
            self.assertFalse(any('force-stop' in p or 'instrument' in p for p in commands))
            self.assertFalse(any(p[:2]==('shell','-T') and 'kill -' in p[2] for p in commands))
            self.assertEqual(next(d.out.glob('*-stdout.log')).read_bytes(), b'original partial stdout\xc2')
            self.assertIsNone(d.receipts[0]['sha256'])
            self.assertIn('no observed shell owner',next(d.out.glob('*-collection.json')).read_text())

    def test_cleanup_rejects_foreign_owner_without_any_signal(self):
        d=object.__new__(D.NativeInputDriver);d.nonce='a'*32;calls=[]
        owner=dict(nonce='b'*32,gesture='baseline-scroll',processName='owned',pid=123,uid=2000,executionUid=2000,startTicks='44')
        def command(*parts,**kwargs):
            calls.append(parts);return subprocess.CompletedProcess([],0,json.dumps(owner).encode(),b'')
        d.command=command
        with self.assertRaisesRegex(ValueError,'foreign shell owner'):
            d.stop_owned_shell('/data/local/tmp/owned','owned','baseline-scroll')
        self.assertEqual(len(calls),1)

    def test_cleanup_generation_guard_executes_against_actual_host_proc_without_signalling(self):
        # Actual shell/proc negative control; this host is not Android shell UID.
        if os.getuid()==2000:self.skipTest('This negative requires a different actual UID')
        with tempfile.TemporaryDirectory() as directory:
            d=object.__new__(D.NativeInputDriver);d.nonce='a'*32;d.out=Path(directory)
            pid=os.getpid();name=Path('/proc/self/cmdline').read_bytes().split(b'\0')[0].decode()
            ticks=Path('/proc/self/stat').read_text().rsplit(') ',1)[1].split()[19]
            owner=dict(nonce=d.nonce,gesture='baseline-scroll',processName=name,pid=pid,uid=2000,executionUid=2000,startTicks=ticks)
            codes=[]
            def command(*parts,**kwargs):
                if parts[:2]==('exec-out','cat'):return subprocess.CompletedProcess([],0,json.dumps(owner).encode(),b'')
                result=subprocess.run(['/bin/sh','-c',parts[2]],capture_output=True);codes.append(result.returncode);return result
            d.command=command
            with self.assertRaisesRegex(ValueError,'generation fence refused'):
                d.stop_owned_shell('/not-read',name,'baseline-scroll')
            self.assertEqual(codes,[6]);self.assertTrue(Path('/proc/'+str(pid)).exists())
            codes.clear();owner['startTicks']=str(int(ticks)+1)
            with self.assertRaisesRegex(ValueError,'generation fence refused'):
                d.stop_owned_shell('/not-read',name,'baseline-scroll')
            self.assertEqual(codes,[4]);self.assertTrue(Path('/proc/'+str(pid)).exists())

    def test_real_scheduler_compiled_and_executed(self):
        java_home = os.environ.get('JAVA_HOME')
        java = Path(java_home) / 'bin/java' if java_home else Path(shutil.which('java'))
        javac = java.with_name('javac')
        with tempfile.TemporaryDirectory() as temporary:
            subprocess.run([str(javac), '-encoding', 'UTF-8', '-d', temporary,
                            str(ROOT / 'tests/native-input-driver/NativeGestureProtocol.java'),
                            str(ROOT / 'tests/native-input-driver-host/NativeGestureProtocolHostTest.java')], check=True, capture_output=True)
            result = subprocess.check_output([str(java), '-cp', temporary, 'local.pocketchat.inputdriver.NativeGestureProtocolHostTest'])
            observed = json.loads(result); self.assertEqual(observed['status'], 'passed'); self.assertGreaterEqual(observed['checks'], 20)
            type(self).scheduler_result = observed

    def test_actual_shell_inject_and_focus_methods_with_explicit_host_adapters(self):
        source=(ROOT/'tests/native-input-driver/NativeInputShell.java').read_text()
        inject=source[source.index('  NativeGestureProtocol.Attempt inject('):source.index('  PackageInfo info(')]
        focus=source[source.index('  static JSONObject parseFocus('):source.index('  String required(')]
        java=r'''
package local.pocketchat.inputdriver;
import java.lang.reflect.*;import java.util.*;import java.util.regex.*;
class JSONObject extends HashMap<String,Object>{public JSONObject put(String k,Object v){super.put(k,v);return this;}}
class SystemClock{static long time=1000;public static long uptimeMillis(){return time;}}
class InputDevice{static final int SOURCE_TOUCHSCREEN=4098;}
class InputEvent{int display=-1;public void setDisplayId(int id){display=id;}}
class MotionEvent extends InputEvent{
  static final int TOOL_TYPE_FINGER=1;boolean recycled;int action;long eventTime,downTime;
  static class PointerProperties{int id,toolType;}static class PointerCoords{float x,y,size,pressure;}
  static MotionEvent obtain(long d,long t,int a,int count,PointerProperties[] p,PointerCoords[] c,int m,int b,float xp,float yp,int device,int edge,int src,int flags){MotionEvent v=new MotionEvent();v.action=a;v.eventTime=t;v.downTime=d;return v;}
  void recycle(){recycled=true;}
}
public class NativeShellBoundaryHostTest{
  static final String TARGET="local.pocketchat.test";
  Object input;Method injectMethod,setDisplay;int targetUid=10123,deviceId=7;
  NativeGestureProtocol.Profile profile=NativeGestureProtocol.profile("qualification");
  static int checks;static void check(boolean ok){if(!ok)throw new AssertionError("check "+checks);checks++;}
  public static class Global{
    int calls,mode,uid;MotionEvent last;boolean accepted=true,throwsError;
    public boolean injectInputEvent(InputEvent event,int mode,int uid){calls++;this.mode=mode;this.uid=uid;last=(MotionEvent)event;if(throwsError)throw new IllegalStateException("controlled Binder failure");return accepted;}
  }
  __INJECT__
  __FOCUS__
  static void rejects(String raw)throws Exception{try{parseFocus(raw);throw new AssertionError("accepted invalid focus");}catch(IllegalStateException expected){checks++;}}
  public static void main(String[] args)throws Exception{
    NativeShellBoundaryHostTest s=new NativeShellBoundaryHostTest();Global g=new Global();s.input=g;
    s.injectMethod=Global.class.getMethod("injectInputEvent",InputEvent.class,int.class,int.class);
    s.setDisplay=InputEvent.class.getMethod("setDisplayId",int.class);
    for(int action:new int[]{0,2,1,3}){
      NativeGestureProtocol.Attempt row=s.inject(action,1000,1000,21000,540,720,action==3);
      check(row.injected&&row.accepted&&row.error.isEmpty());
      check(g.uid==10123&&g.mode==(action==1?2:0)&&g.last.display==0&&g.last.recycled);
      check(row.eventTime==1000&&row.callStart==1000&&row.callEnd==1000&&row.downTime==1000&&row.sync==(action==1));
    }
    int before=g.calls;SystemClock.time=1031;NativeGestureProtocol.Attempt late=s.inject(2,1000,1000,21000,1,2,false);
    check(!late.injected&&g.calls==before&&!late.error.isEmpty());
    NativeGestureProtocol.Attempt cleanup=s.inject(3,1000,1000,1001,1,2,true);check(cleanup.cleanup&&cleanup.injected&&g.uid==10123&&g.mode==0);
    SystemClock.time=1000;g.accepted=false;check(!s.inject(2,1000,1000,21000,1,2,false).accepted);
    g.throwsError=true;NativeGestureProtocol.Attempt failed=s.inject(2,1000,1000,21000,1,2,false);check(failed.injected&&!failed.accepted&&!failed.error.isEmpty());
    String raw="  mCurrentFocus=Window{d4d6de4 u0 local.pocketchat.test/local.pocketchat.GeckoPerformanceIntegrationActivity}\n  mTopFocusedDisplayId=0\n";
    JSONObject actual=parseFocus(raw);check(actual.get("component").equals("local.pocketchat.test/local.pocketchat.GeckoPerformanceIntegrationActivity"));check(actual.get("displayId").equals(0));
    rejects("mTopFocusedDisplayId=0\n");rejects(raw.replace("DisplayId=0","DisplayId=1"));rejects(raw.replace("local.pocketchat.test/","other.package/"));
    rejects(raw+raw);rejects(raw.replace("mCurrentFocus=Window", "mCurrentFocus=null Window"));
    // Optional independent review inputs are real old diagnostic dumps; no device executes.
    for(String path:args){String text=new String(java.nio.file.Files.readAllBytes(java.nio.file.Paths.get(path)),java.nio.charset.StandardCharsets.UTF_8);try{parseFocus(text);System.out.println("FOCUS_ACCEPTED "+path);}catch(IllegalStateException denied){System.out.println("FOCUS_REJECTED "+path);}}
    System.out.println("{\"status\":\"passed\",\"checks\":"+checks+",\"actualAndroidExecution\":false}");
  }
}
'''.replace('__INJECT__',inject).replace('__FOCUS__',focus)
        home=os.environ.get('JAVA_HOME'); compiler=Path(home)/'bin/javac' if home else Path(shutil.which('javac'))
        with tempfile.TemporaryDirectory() as temporary:
            path=Path(temporary)/'NativeShellBoundaryHostTest.java';path.write_text(java)
            subprocess.run([str(compiler),'-encoding','UTF-8','-d',temporary,str(path),str(ROOT/'tests/native-input-driver/NativeGestureProtocol.java')],check=True,capture_output=True)
            result=subprocess.check_output([str(compiler.with_name('java')),'-cp',temporary,'local.pocketchat.inputdriver.NativeShellBoundaryHostTest'])
            self.assertEqual(json.loads(result)['checks'],23)


if __name__ == '__main__':
    result = unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(ContractControls))
    out = ROOT / 'work/gecko-integration/native-input-driver-host-results.json'; out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(dict(status='passed' if result.wasSuccessful() else 'failed', tests=result.testsRun,
        scheduler=getattr(ContractControls, 'scheduler_result', None),
        actualAndroidExecution=False, scope='Production test-driver scheduler and strict parser negative controls only'), indent=2) + '\n')
    raise SystemExit(0 if result.wasSuccessful() else 1)
