"""Current template TLS entry dependency; no TLS policy/native/wire proof."""
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[1]
HOST=ROOT/'tests/review-host/identity-controller/local/pocketchat/GeckoTlsUiEntryBoundaryHost.java'
UI=ROOT/'app/src/main/java/local/pocketchat/FingerprintTemplateUi.java'
RUNNER=ROOT/'tests/review-host/run_identity_controller_host.py'
SHA=lambda path:hashlib.sha256(path.read_bytes()).hexdigest()
PINS={'desktop':'3cf6cd6892e32e2b4c1c39e0f52f5248a2f5b37646fdfbb79a66b46b618414ed','android-json':'dfb7bae2f404cfe0b72b4d23944698cb716b7665171812a0a4d0f5926c0fac79'}

class TlsUiEntryBoundaryTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.java=os.environ.get('PROFILE_JAVA') or shutil.which('java')
        if not cls.java:raise AssertionError('Actual JDK required, no skipped entry controls')
        cls.jars={'desktop':Path(os.environ.get('TLS_ENTRY_JSON_JAR',ROOT/'work/gecko-integration/catalog-json.jar')),'android-json':Path(os.environ.get('PROFILE_ANDROID_JSON_JAR',ROOT/'work/profile-host/android-json.jar'))}
        for name,path in cls.jars.items():
            if not path.is_file() or SHA(path)!=PINS[name]:raise AssertionError('Exact existing '+name+' dependency required for TLS-entry boundary: '+str(path))
        cls.sources=[ROOT/'app/src/main/java/local/pocketchat'/name for name in ('J.java','EnvironmentSpec.java','BrowserIdentitySpec.java','NetworkHealthPolicy.java','IdentityTemplateController.java','FingerprintTemplateUi.java')]+sorted((ROOT/'tests/review-host/identity-controller').rglob('*.java'))
        cls.inputs=[*cls.sources,RUNNER,Path(__file__)];cls.before={str(path.relative_to(ROOT)):SHA(path) for path in cls.inputs};cls.positive=[];cls.counterfeits=[]

    @classmethod
    def tearDownClass(cls):
        if cls.before!={str(path.relative_to(ROOT)):SHA(path) for path in cls.inputs}:raise AssertionError('Raw current entry/controller sources changed during checks')
        report=dict(schema=1,status='passed' if len(cls.positive)==2 and len(cls.counterfeits)==7 else 'failed',sourceFiles=cls.before,executionInputsUnchanged=True,jsonDependencies={name:SHA(path) for name,path in cls.jars.items()},positive=cls.positive,compiledSemanticCounterfeits=cls.counterfeits,actualAndroidExecution=False,actualGeckoExecution=False,actualSdkApiCompile=False,actualTlsNativeExecution=False,actualNetworkExecution=False,nativeSettingReadback=False,scope='Original identity-controller runner and all original renderer/CPU/timezone assertions remain raw and unchanged. Current production template TLS action executes through default/unavailable typed dependency only. No TLS desired store, controller, native ACK, boot or wire policy is represented; seven compiled guards/false-readiness counterfeits must fail the same new boundary checks.')
        out=ROOT/'work/tls-ui-entry-boundary';out.mkdir(parents=True,exist_ok=True);(out/'results.json').write_text(json.dumps(report,indent=2)+'\n')

    def run_main(self,classes,jar,name):
        return subprocess.run([self.java,'-cp',str(classes)+os.pathsep+str(jar),name],cwd=ROOT,capture_output=True,text=True,timeout=20)

    def test_original_renderer_and_current_tls_entry_on_both_actual_json_jars(self):
        for name,jar in self.jars.items():
            with self.subTest(runtime=name),tempfile.TemporaryDirectory(prefix='tls-entry-original-') as folder:
                output=Path(folder)/'original.json'
                original=subprocess.run([os.sys.executable,str(RUNNER),'--json-jar',str(jar),'--output',str(output)],cwd=ROOT,capture_output=True,text=True,timeout=60)
                self.assertEqual(original.returncode,0,original.stdout+original.stderr)
                renderer=json.loads(output.read_text());self.assertEqual(renderer['status'],'passed');self.assertEqual(renderer['passed'],renderer['total']);self.assertIs(renderer['sourceUnchangedDuringChecks'],True)
                self.assertEqual(renderer['timezoneEntryBoundary']['passed'],13)
                classes=ROOT/'work/identity-controller-host/classes'
                cpu=self.run_main(classes,jar,'local.pocketchat.GeckoCpuUiEntryBoundaryHost');self.assertEqual(cpu.returncode,0,cpu.stdout+cpu.stderr);cpu_report=json.loads(cpu.stdout);self.assertEqual(cpu_report['passed'],13)
                tls=self.run_main(classes,jar,'local.pocketchat.GeckoTlsUiEntryBoundaryHost');self.assertEqual(tls.returncode,0,tls.stdout+tls.stderr);value=json.loads(tls.stdout)
                self.assertEqual(value['status'],'passed');self.assertEqual(value['passed'],18);self.assertEqual(value['total'],18);self.assertEqual(len(value['checks']),18);self.assertTrue(all(row['pass'] is True for row in value['checks']))
                for flag in ('nativeSettingReadback','customSupported','coldApplied','actualAndroidExecution','actualGeckoExecution','actualTlsNativeExecution','actualSdkApiCompile','actualNetworkExecution'):self.assertIs(value[flag],False)
                self.positive.append(dict(runtime=name,originalControllerPassed=renderer['passed'],originalControllerTotal=renderer['total'],originalTimezonePassed=13,originalCpuPassed=13,tlsEntryPassed=18,actualTlsNativeExecution=False))

    def compile_counterfeit(self,ui_source,host_source,folder):
        root=Path(folder);classes=root/'classes';classes.mkdir();sources=[]
        layout=ROOT/'tests/review-host/identity-controller/android/widget/LinearLayout.java'
        for path in self.sources:
            source=None
            if path==UI:source=ui_source
            elif path==HOST:source=host_source
            elif path==layout:
                original=path.read_text();needle='public void addView(android.view.View view){}';self.assertEqual(original.count(needle),1)
                source=original.replace(needle,'public final java.util.List<android.view.View> children=new java.util.ArrayList<>(); public void addView(android.view.View view){children.add(view);}',1)
            if source is None:sources.append(path)
            else:
                target=root/path.relative_to(ROOT);target.parent.mkdir(parents=True,exist_ok=True);target.write_text(source);sources.append(target)
        built=subprocess.run([self.java,'-m','jdk.compiler/com.sun.tools.javac.Main','-source','8','-target','8','-encoding','UTF-8','-cp',str(self.jars['desktop']),'-d',str(classes),*map(str,sources)],cwd=ROOT,capture_output=True,text=True,timeout=40)
        self.assertEqual(built.returncode,0,built.stdout+built.stderr)
        return self.run_main(classes,self.jars['desktop'],'local.pocketchat.GeckoTlsUiEntryBoundaryHost')

    def test_compiled_lambda_guards_and_unobserved_dependency_cannot_be_counterfeited(self):
        ui=UI.read_text();host=HOST.read_text();tls_line=next(line for line in ui.splitlines(keepends=True) if '"Gecko TLS 协议"' in line);self.assertEqual(ui.count(tls_line),1)
        cases=[]
        for name,needle,reason in [('destroyed','!a.isDestroyed()&&','Actual TLS action rejects destroyed Activity'),('finishing','!a.isFinishing()&&','Actual TLS action rejects finishing Activity'),('deleted','!edited.deleted&&','Actual TLS action rejects deleted environment'),('foreign-session','&&a.session==edited','Actual TLS action rejects replacement environment')]:
            self.assertEqual(tls_line.count(needle),1);cases.append((name,ui.replace(tls_line,tls_line.replace(needle,'',1),1),host,reason))
        for name,needle,replacement,reason in [('false-native-readback','nativeSettingReadback=false','nativeSettingReadback=true','TLS entry facade cannot claim native readback'),('custom-supported','if(!"automatic".equals(mode)||nativeReady)','if(nativeReady)','TLS13-only cannot claim support'),('opaque-readiness','static boolean nativeConfirmed(ChatSession session,Object runtime){return false;}','static boolean nativeConfirmed(ChatSession session,Object runtime){return runtime!=null;}','Opaque runtime identity is not an observed TLS confirmation')]:
            self.assertEqual(host.count(needle),1);cases.append((name,ui,host.replace(needle,replacement,1),reason))
        for name,changed_ui,changed_host,reason in cases:
            with self.subTest(counterfeit=name),tempfile.TemporaryDirectory(prefix='tls-entry-counterfeit-') as folder:
                result=self.compile_counterfeit(changed_ui,changed_host,folder);self.assertNotEqual(result.returncode,0);self.assertIn('AssertionError: '+reason,result.stderr)
                self.counterfeits.append(dict(name=name,compiled=True,rejectedByBoundaryAssertion=reason))

if __name__=='__main__':unittest.main(verbosity=2)
