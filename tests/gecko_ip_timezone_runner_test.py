"""Real runner functions/JVM choices at explicit synthetic Android/ADB boundaries."""
import ast
import contextlib
import copy
import hashlib
import importlib.util
import io
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

os.environ.setdefault('GIT_NO_LAZY_FETCH','1')
ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('ip_actual_runner',ROOT/'tools/browser/run_gecko_ip_timezone_integration.py')
runner=importlib.util.module_from_spec(spec);spec.loader.exec_module(runner)
import gecko_ip_timezone_evidence_test as modeled


class RunnerTests(unittest.TestCase):
    def test_source_nonce_shell_framing_and_no_extra_input_actions(self):
        source,nonce='a'*40,'b'*32
        args=runner.scope_command('prepare',source,nonce)
        import shlex
        words=shlex.split(args[1]);self.assertEqual(words[0:2],['content','call'])
        self.assertEqual(words.count('--method'),1);self.assertIn('sourceCommit:s:'+source,words)
        self.assertIn('runNonce:s:'+nonce,words)
        launch=shlex.split(runner.activity_args(source,nonce,'c'*64)[1])
        self.assertEqual(launch[:3],['am','start','-W']);self.assertIn(runner.ACTIVITY,launch)
        for bad in ('','a'*39,'a'*40+';id','$(id)','a'*40+'\n'):
            with self.subTest(bad=bad),self.assertRaises(ValueError):runner.scope_command('prepare',bad,nonce)
        with self.assertRaises(ValueError):runner.scope_command('delete',source,nonce)
        with self.assertRaises(ValueError):runner.activity_args(source,nonce,'c'*63)
        tree=ast.parse(Path(runner.__file__).read_text())
        self.assertEqual(sum(isinstance(n,ast.Call) and isinstance(n.func,ast.Name) and n.func.id=='activity_args' for n in ast.walk(tree)),1)
        for node in ast.walk(tree):
            if isinstance(node,ast.Constant) and type(node.value) is str:
                self.assertNotIn('input tap',node.value);self.assertNotIn('input swipe',node.value)
                self.assertNotIn('/rerun',node.value)

    def test_device_report_duplicate_keys_apk_source_and_invocation(self):
        report,expected=modeled.IpEvidenceTests().fixture();activity=report['activity']
        def actual(value,reference):return modeled.gate.installed(value,reference,modeled.source_reader)
        with patch.object(runner,'verify_installed',actual):
            raw=json.dumps(activity).encode()
            self.assertEqual(runner.read_activity(raw,modeled.SOURCE,modeled.NONCE,expected)['status'],'passed')
            self.assertIsNone(runner.read_activity(b'Error: provider unavailable',modeled.SOURCE,modeled.NONCE,expected))
            self.assertIsNone(runner.read_activity(raw,modeled.SOURCE,'f'*32,expected))
            for change in (lambda r:r.update(sourceCommit='d'*40),lambda r:r.update(sourceTree='d'*40),lambda r:r['buildIdentity'].update(apkSha256='0'*64),lambda r:r['buildIdentity']['sdkBuildIdentity'].update(runAttempt='2')):
                value=copy.deepcopy(activity);change(value)
                with self.assertRaises(ValueError):runner.read_activity(json.dumps(value).encode(),modeled.SOURCE,modeled.NONCE,expected)
            duplicate=raw[:-1]+b',"status":"passed"}'
            with self.assertRaises(ValueError):runner.read_activity(duplicate,modeled.SOURCE,modeled.NONCE,expected)
            with self.assertRaises(ValueError):runner.read_activity(b' '* (runner.MAX_ACTIVITY_BYTES+1),modeled.SOURCE,modeled.NONCE,expected)

    def test_trust_export_is_only_actual_typed_installation_fields_no_path_or_keys(self):
        value=dict(installedPublicCaBytesMatch=True,evidenceShellUid=2000,storePath='/data/private',privateKey='secret',arbitraryLog='secret',removedAfterExecution=True)
        self.assertEqual(runner.safe_trust(value),dict(installedPublicCaBytesMatch=True,evidenceShellUid=2000,removedAfterExecution=True))

    def execute_failed_main(self,where):
        report,expected=modeled.IpEvidenceTests().fixture();activity=copy.deepcopy(report['activity']);activity.update(status='failed',stage='failed',failedAtStage='default-socks',failure='AssertionError')
        actions=[];directory=tempfile.TemporaryDirectory();self.addCleanup(directory.cleanup);temporary=Path(directory.name);out=temporary/'out';apk=temporary/'integration.apk';apk.write_bytes(b'Explicit modeled APK boundary only')
        setup=copy.deepcopy(activity['setup']);setup['actualDefaultStoreLoadYet']=False
        class Certificates:
            def __init__(self):
                self.directory=temporary/'ephemeral-private';self.directory.mkdir();self.public={key:report['hostTls'][key] for key in ('caPemSha256','leafDerSha256')};self.leaf_sha='f'*64
            def close(self):actions.append('private-removed');self.directory.rmdir()
        class Server:
            def __init__(self,*args):self.closed=False
            def start(self):return self
            def ports(self):return {18766:10001,18767:10002,18768:10003,18769:10004}
            def close(self):
                self.closed=True;actions.append('server-closed')
                if where=='server-close':raise RuntimeError('modeled close failure')
            def snapshot(self):
                if where=='final-snapshot':raise RuntimeError('modeled collector failure')
                value=copy.deepcopy(report['routeReceipts']);value['closed']=self.closed;return value
        class Ca:
            def __init__(self,*args):self.receipt={}
            def install(self):actions.append('ca-installed')
            def remove(self):actions.append('ca-removed');self.receipt.update(removedAfterExecution=True)
        def command(values,**kwargs):
            words=values[3:];actions.append(tuple(words))
            raw=b''
            if words==['shell','getprop','ro.kernel.qemu']:raw=b'1\n'
            elif words==['shell','id','-u']:raw=b'2000\n'
            elif words==['shell','getprop','persist.sys.timezone']:raw=b'UTC\n'
            elif words==['shell','pm','clear','local.pocketchat.test']:raw=b'Success\n'
            elif len(words)==2 and words[0]=='shell' and '--method prepare' in words[1]:
                if where=='prepare':raise subprocess.CalledProcessError(1,values)
            elif len(words)==2 and words[0]=='shell' and '--method clear' in words[1]:actions.append('scope-cleared')
            elif words==['exec-out','content','read','--uri',runner.URI+'/setup']:raw=json.dumps(setup).encode()
            elif words==['exec-out','content','read','--uri',runner.URI+'/report']:raw=json.dumps(activity).encode()
            return subprocess.CompletedProcess(values,0,stdout=raw,stderr=b'')
        def git(values,**kwargs):
            if values[-1]=='HEAD':return modeled.SOURCE+'\n'
            if values[-1]=='HEAD^{tree}':return modeled.TREE+'\n'
            if values[-1]=='--porcelain':return ''
            raise AssertionError('Unexpected modeled command')
        def actual(value,reference):return modeled.gate.installed(value,reference,modeled.source_reader)
        with patch.object(sys,'argv',['run','--serial','emulator-5554','--apk',str(apk),'--source',modeled.SOURCE,'--output',str(out)]),patch.object(runner.subprocess,'check_output',git),patch.object(runner.subprocess,'run',command),patch.object(runner,'expected_build',lambda *args:expected),patch.object(runner,'verify_installed',actual),patch.object(runner,'source_inputs',lambda:[Path(runner.__file__)]),patch.object(runner.uuid,'uuid4',lambda:type('Nonce',(),{'hex':modeled.NONCE})()),patch.object(runner,'IpFixtureCertificates',Certificates),patch.object(runner,'IpTimeZoneFleet',Server),patch.object(runner,'AndroidUserCa',Ca),contextlib.redirect_stdout(io.StringIO()):
            with self.assertRaises(SystemExit) as failed:runner.main()
            self.assertEqual(failed.exception.code,1)
        return json.loads((out/runner.REPORT_NAME).read_text()),actions,out

    def test_actual_finally_keeps_original_failure_and_runs_all_cleanups(self):
        for where in ('server-close','final-snapshot','prepare'):
            with self.subTest(where=where):
                value,actions,out=self.execute_failed_main(where)
                self.assertEqual(value['status'],'failed');self.assertFalse(value['actualAndroidExecution'])
                self.assertIn('scope-cleared',actions);self.assertIn('ca-removed',actions);self.assertIn('private-removed',actions)
                self.assertIn('server-closed',actions);self.assertTrue(value['cleanup']['caRemoved'])
                self.assertTrue(value['cleanup']['privateMaterialRemoved']);self.assertTrue(value['cleanup']['scopeCleared'])
                if where=='server-close':self.assertEqual(value['errorType'],'ValueError');self.assertFalse(value['cleanup']['serverQuiesced'])
                if where=='final-snapshot':self.assertEqual(value['errorType'],'ValueError')
                if where=='prepare':self.assertEqual(value['errorType'],'CalledProcessError')
                self.assertEqual({p.name for p in (out/runner.RAW_DIRECTORY).iterdir()},set(runner.RAW_FILES))
                starts=[row for row in actions if isinstance(row,tuple) and len(row)==2 and row[0]=='shell' and row[1].startswith('am start ')]
                self.assertEqual(len(starts),0 if where=='prepare' else 1,'Failed workload must never replay')

    def test_actual_ui_mode_and_old_fixture_indices_execute_with_both_real_json_jars(self):
        java_home=Path(os.environ.get('PROFILE_JAVA_HOME') or os.environ.get('JAVA_HOME',''))
        jars=[Path(os.environ.get(key,'')) for key in ('PROFILE_JSON_JAR','PROFILE_ANDROID_JSON_JAR')]
        self.assertTrue((java_home/'bin/javac').is_file() and (java_home/'bin/java').is_file() and all(jar.is_file() for jar in jars),'Explicit real JDK and both JSON jars required; no skip')
        sys.path.insert(0,str(ROOT/'tests/gecko-navigation-host'));from run import member_at
        ui=(ROOT/'app/src/main/java/local/pocketchat/GeckoTimeZoneUi.java').read_text();fixture=(ROOT/'tests/gecko/GeckoEnvironmentPolicyIntegrationActivity.java').read_text()
        methods=[member_at(ui,ui.index(marker)) for marker in ('static int selectionFor(','static GeckoTimeZoneSpec selected(')]
        expression=re.findall(r'mode\.setSelection\((zone\.isEmpty\(\)\?.*?)\);',fixture)
        self.assertEqual(len(expression),1)
        conflict=member_at(fixture,fixture.index('void attemptRfpConflict('));self.assertEqual(conflict.count('setSelection(3)'),1)
        host='''package local.pocketchat;public class ChoiceHost {public static void main(String[]args){int n=0;for(String zone:new String[]{"","UTC","Asia/Kathmandu"}){int choice=choose(zone);GeckoTimeZoneSpec selected=GeckoTimeZoneUi.selected(choice,zone);if(selected.followsIp()||!(zone.isEmpty()?selected.followsSystem():selected.zoneId.equals(zone)))throw new AssertionError("Original fixture explicit mode changed");if(GeckoTimeZoneUi.selectionFor(selected)!=choice)throw new AssertionError("Actual UI mode mismatch");n+=2;}if(!GeckoTimeZoneUi.selected(0,"").followsIp())throw new AssertionError("IP mode missing");System.out.println(n+1);}static int choose(String zone){return EXPR;}}'''.replace('EXPR',expression[0])
        for jar in jars:
            with self.subTest(jar=jar.name),tempfile.TemporaryDirectory() as temporary:
                path=Path(temporary);wrapper=path/'GeckoTimeZoneUi.java';wrapper.write_text('package local.pocketchat;final class GeckoTimeZoneUi {'+'\n'.join(methods)+'}')
                chosen=path/'ChoiceHost.java';chosen.write_text(host)
                sources=[ROOT/'app/src/main/java/local/pocketchat/GeckoTimeZoneSpec.java',ROOT/'app/src/main/java/local/pocketchat/J.java',wrapper,chosen]
                command=[str(java_home/'bin/javac'),'-cp',str(jar),'-d',str(path/'classes'),*map(str,sources)]
                compiled=subprocess.run(command,capture_output=True,text=True,timeout=30);self.assertEqual(compiled.returncode,0,compiled.stderr)
                command=[str(java_home/'bin/java'),'-cp',str(path/'classes')+os.pathsep+str(jar),'local.pocketchat.ChoiceHost']
                current=subprocess.run(command,capture_output=True,text=True,timeout=30);self.assertEqual(current.returncode,0,current.stderr);self.assertEqual(current.stdout.strip(),'7')
                # A compiled old zero-based mapping must fail the actual new
                # selected() policy, rather than merely a source text check.
                chosen.write_text(host.replace(expression[0],'zone.isEmpty()?0:zone.equals("UTC")?1:2'))
                altered=subprocess.run([str(java_home/'bin/javac'),'-cp',str(jar)+os.pathsep+str(path/'classes'),'-d',str(path/'classes'),str(chosen)],capture_output=True,text=True,timeout=30);self.assertEqual(altered.returncode,0,altered.stderr)
                rejected=subprocess.run(command,capture_output=True,text=True,timeout=30);self.assertEqual(rejected.returncode,1);self.assertIn('Original fixture explicit mode changed',rejected.stderr)

if __name__=='__main__':unittest.main()
