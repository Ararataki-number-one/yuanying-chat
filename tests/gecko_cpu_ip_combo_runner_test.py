"""Actual runner/copy control flow at declared synthetic Android/ADB boundaries."""
import contextlib
import copy
import importlib.util
import io
import json
from pathlib import Path
import shlex
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('combo_actual_runner',ROOT/'tools/browser/run_gecko_cpu_ip_combo_integration.py');runner=importlib.util.module_from_spec(spec);spec.loader.exec_module(runner)
sys.path.insert(0,str(ROOT/'tools'));from browser import cpu_ip_combo_publication as publication
import gecko_cpu_ip_combo_evidence_test as modeled


class ComboRunnerTests(unittest.TestCase):
    def test_shell_source_nonce_leaf_and_constant_single_invocation(self):
        source,nonce=modeled.SOURCE,modeled.NONCE;words=shlex.split(runner.scope_command('prepare',source,nonce)[1]);self.assertEqual(words[:2],['content','call']);self.assertIn(runner.URI,words);self.assertIn('sourceCommit:s:'+source,words)
        self.assertIn(runner.ACTIVITY,shlex.split(runner.activity_args(source,nonce,'f'*64)[1]))
        for bad in ('','f'*39,'f'*40+';id','$(id)','f'*40+'\n'):
            with self.subTest(bad=bad),self.assertRaises(ValueError):runner.scope_command('prepare',bad,nonce)
        with self.assertRaises(ValueError):runner.scope_command('rerun',source,nonce)
        with self.assertRaises(ValueError):runner.activity_args(source,nonce,'f'*63)
    def test_strict_json_before_nonce_ignoring_damaged_foreign_packets(self):
        report,expected=modeled.fixture();activity=report['activity'];raw=json.dumps(activity).encode()
        def installed(value,reference):return modeled.gate.ip.installed(value,reference,modeled.modeled.source_reader)
        with patch.object(runner,'verify_installed',installed):
            self.assertEqual(runner.read_activity(raw,modeled.SOURCE,modeled.NONCE,expected),activity)
            self.assertIsNone(runner.read_activity(b'',modeled.SOURCE,modeled.NONCE,expected));self.assertIsNone(runner.read_activity(b'Error while accessing provider: startup',modeled.SOURCE,modeled.NONCE,expected))
            stale=copy.deepcopy(activity);stale['runNonce']='f'*32;self.assertIsNone(runner.read_activity(json.dumps(stale).encode(),modeled.SOURCE,modeled.NONCE,expected))
            for first,last in ((modeled.NONCE,'f'*32),('f'*32,modeled.NONCE)):
                invalid=raw[:-1]+b',"runNonce":'+json.dumps(last).encode()+b'}';invalid=invalid.replace(json.dumps(modeled.NONCE).encode(),json.dumps(first).encode(),1)
                with self.subTest(order=(first,last)),self.assertRaises(ValueError):runner.read_activity(invalid,modeled.SOURCE,modeled.NONCE,expected)
            for value in (b'{"x":NaN}',b'[]',b'null',b'\xff',raw+b'trailing',b' '*524289):
                with self.subTest(raw=value[:15]),self.assertRaises((ValueError,UnicodeError)):runner.read_activity(value,modeled.SOURCE,modeled.NONCE,expected)
            for change in (lambda r:r.update(schema=True),lambda r:r.update(runNonce=1),lambda r:r.update(sourceCommit='f'*40),lambda r:r['buildIdentity'].update(apkSha256='f'*64),lambda r:r['buildIdentity']['sdkBuildIdentity'].update(runAttempt='2')):
                value=copy.deepcopy(activity);change(value)
                with self.assertRaises(ValueError):runner.read_activity(json.dumps(value).encode(),modeled.SOURCE,modeled.NONCE,expected)
    def execute_main(self,where):
        report,expected=modeled.fixture();activity=copy.deepcopy(report['activity'])
        if where=='expired':activity.update(status='running',stage='production-cold-bootstrap')
        if where=='device-failed':activity.update(status='failed',stage='failed',failure='Synthetic device failure')
        device_raw=(json.dumps(activity,indent=2)+'\n').encode();actions=[];verification=[];temporary=tempfile.TemporaryDirectory();self.addCleanup(temporary.cleanup);base=Path(temporary.name);apk=base/'integration.apk';apk.write_bytes(b'EXPLICIT MODELED APK BOUNDARY');out=base/'out'
        class Certificates:
            def __init__(self):
                self.directory=base/'ephemeral';self.directory.mkdir();self.leaf_sha=report['hostTls']['leafDerSha256'];self.public={key:value for key,value in report['hostTls'].items() if key not in ('binding','trustInstallation','privateMaterialRemoved')}
            def close(self):actions.append('private-removed');self.directory.rmdir()
        class Server:
            closed=False
            diagnostic_quiescent=False
            def __init__(self,*args):pass
            def start(self):return self
            def control(self,value):
                self_case=dict(sourceCommit=modeled.SOURCE,runNonce=modeled.NONCE,action='stage',case='default-socks')
                if value!=self_case:raise AssertionError('Wrong actual host control binding')
                actions.append(('local-stage',value))
            def ports(self):return {18766:19001,18767:19002,18768:19003,18769:19004}
            def close(self):
                self.closed=True;actions.append('server-closed')
                if where=='server-close':raise RuntimeError('MODELED server close')
                self.diagnostic_quiescent=True
            def snapshot(self):
                if where=='snapshot':raise RuntimeError('MODELED snapshot')
                result=copy.deepcopy(report['routeReceipts']);result['closed']=self.closed;return result
            def diagnostic_snapshot(self):
                # Declared host collector boundary only; no Android/native data.
                if where=='diagnostic':raise ValueError('MODELED diagnostic snapshot')
                binding=report['routeReceipts']['binding']
                return dict(schema=1,kind='ip-timezone-transport-diagnostics-v1',binding=copy.deepcopy(binding),
                    collectorClosed=self.closed,quiescent=self.diagnostic_quiescent,eventLimit=128,totalFailures=0,
                    recordedEvents=0,droppedEvents=0,counts={name:{stage:{} for stage in runner.TRANSPORT_STAGES} for name in runner.ROUTES},events=[])
        class Ca:
            def __init__(self,*a):self.receipt=copy.deepcopy(report['hostTls']['trustInstallation'])
            def install(self):actions.append('ca-installed')
            def remove(self):actions.append('ca-removed')
        def adb(command,**kwargs):
            words=command[3:];actions.append(tuple(words));raw=b''
            if words==['shell','getprop','ro.kernel.qemu']:raw=b'1\n'
            elif words==['shell','id','-u']:raw=b'2000\n'
            elif words==['shell','getprop','persist.sys.timezone']:raw=b'UTC\n'
            elif words==['shell','pm','clear','local.pocketchat.test']:raw=b'Success\n'
            elif words==['shell','pidof',modeled.gate.PROCESS]:raw=b'7711 7712\n' if where=='pid' else b'7711\n'
            elif words==['exec-out','content','read','--uri',runner.URI+'/setup']:raw=json.dumps(report['prelaunchSetup']).encode()
            elif words==['exec-out','content','read','--uri',runner.URI+'/report']:
                raw=device_raw;actions.append(('report-timeout',kwargs['timeout']))
            elif len(words)==2 and words[0]=='shell' and '--method prepare' in words[1] and where=='prepare':raise subprocess.CalledProcessError(1,command)
            elif len(words)==2 and words[0]=='shell' and '--method clear' in words[1]:actions.append('scope-cleared')
            return subprocess.CompletedProcess(command,0,stdout=raw,stderr=b'')
        def git(command,**kwargs):
            if command[-1]=='HEAD':return modeled.SOURCE+'\n'
            if command[-1]=='HEAD^{tree}':return modeled.TREE+'\n'
            if command[-1]=='--porcelain':return ''
            raise AssertionError('Unexpected command boundary')
        def verify(directory,source,reference):
            verification.append((directory,source,reference))
            if where=='checker':raise ValueError('MODELED checker rejection')
            self.assertEqual((directory/runner.RAW_DIRECTORY/'combo.json').read_bytes(),device_raw)
            return dict(scope='MODELED CALL BOUNDARY ONLY')
        def installed(value,reference):return modeled.gate.ip.installed(value,reference,modeled.modeled.source_reader)
        stdout=io.StringIO();original_clock=runner.time.monotonic;clock_values=iter((0,179,179.5,181))
        def clock():return next(clock_values) if where=='expired' else original_clock()
        with patch.object(sys,'argv',['run','--serial','emulator-5554','--apk',str(apk),'--source',modeled.SOURCE,'--output',str(out)]),patch.object(runner.subprocess,'check_output',git),patch.object(runner.subprocess,'run',adb),patch.object(runner,'expected_build',lambda *args:expected),patch.object(runner,'verify_installed',installed),patch.object(runner,'source_inputs',lambda:[Path(runner.__file__)]),patch.object(runner.uuid,'uuid4',lambda:type('Nonce',(),{'hex':modeled.NONCE})()),patch.object(runner,'IpFixtureCertificates',Certificates),patch.object(runner,'IpTimeZoneFleet',Server),patch.object(runner,'AndroidUserCa',Ca),patch.object(runner,'verify_gecko_cpu_ip_combo_evidence',verify),patch.object(runner.time,'monotonic',clock),patch.object(runner.time,'sleep',lambda duration:actions.append(('sleep',duration))),contextlib.redirect_stdout(stdout):
            if where=='passed':runner.main()
            else:
                with self.assertRaises(SystemExit) as error:runner.main()
                self.assertEqual(error.exception.code,1)
        return json.loads((out/runner.REPORT_NAME).read_text()),actions,out,device_raw,json.loads(stdout.getvalue()),verification
    def test_actual_main_preserves_device_bytes_and_calls_verifier_once_at_model_boundary(self):
        report,actions,out,original,status,verify=self.execute_main('passed');self.assertEqual(status['status'],'passed');self.assertEqual(len(verify),1);self.assertEqual((out/runner.RAW_DIRECTORY/'combo.json').read_bytes(),original);self.assertEqual(set(report['casePins']),set(runner.RAW_FILES));self.assertTrue(all(report['cleanup'].values()));self.assertFalse(status['actualPublicIpGeolocationVerified'])
        launches=[a for a in actions if isinstance(a,tuple) and len(a)==2 and a[0]=='shell' and a[1].startswith('am start ')];self.assertEqual(len(launches),1);self.assertEqual(sum(isinstance(row,tuple) and row[0]=='local-stage' for row in actions),1)
    def test_every_failure_preserves_original_outcome_runs_all_cleanup_and_never_replays(self):
        for where in ('prepare','device-failed','pid','server-close','snapshot','checker'):
            with self.subTest(where=where):
                report,actions,out,original,status,verify=self.execute_main(where);self.assertEqual(status['status'],'failed');self.assertIn('scope-cleared',actions);self.assertIn('server-closed',actions);self.assertIn('ca-removed',actions);self.assertIn('private-removed',actions)
                launches=[a for a in actions if isinstance(a,tuple) and len(a)==2 and a[0]=='shell' and a[1].startswith('am start ')];self.assertEqual(len(launches),0 if where=='prepare' else 1)
                if where!='prepare':self.assertEqual((out/runner.RAW_DIRECTORY/'combo.json').read_bytes(),original)
                else:self.assertFalse((out/runner.RAW_DIRECTORY/'combo.json').exists(),'No synthesized empty device success packet')
                if where=='checker':self.assertEqual(report['status'],'passed','Device outcome remains original; command/checker fails separately')
                else:self.assertEqual(report['status'],'failed')
    def test_actual_outer_deadline_caps_provider_read_and_never_relaunches(self):
        report,actions,out,original,status,verify=self.execute_main('expired');self.assertEqual(status['status'],'failed');self.assertEqual(report['status'],'failed');self.assertEqual(verify,[])
        self.assertEqual([row[1] for row in actions if isinstance(row,tuple) and row[0]=='report-timeout'],[.5]);self.assertEqual((out/runner.RAW_DIRECTORY/'combo.json').read_bytes(),original)
        launches=[row for row in actions if isinstance(row,tuple) and len(row)==2 and row[0]=='shell' and row[1].startswith('am start ')];self.assertEqual(len(launches),1);self.assertTrue(all(report['cleanup'].values()))
    def test_new_180_second_outer_and_original_120_second_activity_budgets_are_fixed(self):
        import ast
        source=Path(runner.__file__).read_text();self.assertIn('deadline=time.monotonic()+180',source);self.assertIn('timeout=min(20,remaining)',source);self.assertNotIn('960',source)
        native=(ROOT/'tests/gecko/GeckoCpuIpComboIntegrationActivity.java').read_text();self.assertIn('deadline=SystemClock.elapsedRealtime()+120000',native)
        self.assertEqual(sum(isinstance(n,ast.Call) and isinstance(n.func,ast.Name) and n.func.id=='activity_args' for n in ast.walk(ast.parse(source))),1)


class ComboPublicationTests(unittest.TestCase):
    def test_exact_original_combo_bytes_copy_and_no_replacement(self):
        report,expected=modeled.fixture()
        with tempfile.TemporaryDirectory() as name:
            root=Path(name);source=root/'source';source.mkdir();dest=root/'dest';dest.mkdir();modeled.write(source,report)
            found=publication.copy_gecko_cpu_ip_combo_evidence(source,dest,modeled.SOURCE,expected,reader=modeled.modeled.source_reader)
            self.assertEqual(len(found),5)
            for relative in found:self.assertEqual((source/relative).read_bytes(),(dest/relative).read_bytes())
            with self.assertRaises(ValueError):publication.copy_gecko_cpu_ip_combo_evidence(source,dest,modeled.SOURCE,expected,reader=modeled.modeled.source_reader)
    def test_evidence_and_source_drift_omissions_never_produce_success(self):
        report,expected=modeled.fixture()
        with tempfile.TemporaryDirectory() as name:
            root=Path(name);source=root/'source';source.mkdir();dest=root/'dest';dest.mkdir();modeled.write(source,report);(source/runner.RAW_DIRECTORY/'combo.json').write_text('{}')
            with self.assertRaises(ValueError):publication.copy_gecko_cpu_ip_combo_evidence(source,dest,modeled.SOURCE,expected,reader=modeled.modeled.source_reader)
            self.assertEqual(list(dest.iterdir()),[])
        with tempfile.TemporaryDirectory() as name:
            dest=Path(name)
            with self.assertRaises(ValueError):publication.copy_gecko_cpu_ip_combo_tools(ROOT,dest,modeled.SOURCE,reader=lambda *_:b'changed selected source')
            self.assertEqual(list(dest.iterdir()),[])
    def test_checker_time_byte_mutation_is_detected_before_copy(self):
        report,expected=modeled.fixture()
        with tempfile.TemporaryDirectory() as name:
            root=Path(name);source=root/'source';source.mkdir();dest=root/'dest';dest.mkdir();modeled.write(source,report);actual=publication.verify_gecko_cpu_ip_combo_evidence
            def change(*args,**kwargs):
                result=actual(*args,**kwargs);packet=source/runner.RAW_DIRECTORY/'combo.json';packet.write_bytes(packet.read_bytes()+b' ');return result
            with patch.object(publication,'verify_gecko_cpu_ip_combo_evidence',change),self.assertRaisesRegex(ValueError,'inputs changed'):publication.copy_gecko_cpu_ip_combo_evidence(source,dest,modeled.SOURCE,expected,reader=modeled.modeled.source_reader)
            self.assertEqual(list(dest.iterdir()),[])
    def test_code_copier_rejects_parent_symlink_before_any_external_mkdir(self):
        for which in ('tools','browser'):
            with self.subTest(which=which),tempfile.TemporaryDirectory() as name:
                root=Path(name);dest=root/'dest';dest.mkdir();outside=root/'outside';outside.mkdir()
                if which=='tools':(dest/'tools').symlink_to(outside,target_is_directory=True)
                else:(dest/'tools').mkdir();(dest/'tools/browser').symlink_to(outside,target_is_directory=True)
                with self.assertRaises((ValueError,OSError)):publication.copy_gecko_cpu_ip_combo_tools(ROOT,dest,modeled.SOURCE,reader=lambda source,path:(ROOT/path).read_bytes())
                self.assertEqual(list(outside.iterdir()),[])
    def test_exact_source_only_tools_and_mutable_helper_classification(self):
        with tempfile.TemporaryDirectory() as name:
            dest=Path(name);copied=publication.copy_gecko_cpu_ip_combo_tools(ROOT,dest,modeled.SOURCE,reader=lambda source,path:(ROOT/path).read_bytes());self.assertEqual(len(copied),9)
            self.assertEqual(publication.COMBO_RELEASE_TOOLS,('tools/browser/cpu_ip_combo_publication.py',));self.assertNotIn('tools/browser/run_gecko_cpu_ip_combo_integration.py',publication.COMBO_RELEASE_TOOLS)
            for relative in copied:self.assertEqual((ROOT/relative).read_bytes(),(dest/relative).read_bytes())

if __name__=='__main__':unittest.main()
