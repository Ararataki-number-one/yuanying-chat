"""Exact connection fixtures plus an explicit asynchronous native-admission model.

No native Gecko or Android executes in this host. The real fixture invokes the
production native timezone gate; these controls only test its prerequisite state.
"""
import hashlib,json,os,shutil,subprocess,tempfile,unittest
from pathlib import Path
from connection_timezone_fixture_contract import original_connection_fixture,legacy_pool_activity_input,manifest

ROOT=Path(__file__).resolve().parents[1]
POOL='tests/gecko/GeckoConnectionPoolIntegrationActivity.java'
PRE='tests/gecko/PreconnectIntegrationActivity.java'
HELPER=ROOT/'tests/connection-timezone-prerequisite-host/PrerequisiteHost.java.in'
def sha(raw):return hashlib.sha256(raw).hexdigest()
def member(text,signature):
    start=text.index(signature);opening=text.index('{',start);depth=1;end=opening+1
    while depth:
        if text[end]=='{':depth+=1
        elif text[end]=='}':depth-=1
        end+=1
    return text[start:end]

class ConnectionTimezonePrerequisiteTest(unittest.TestCase):
    def test_prior_whole_fixtures_assertions_and_all_deadlines_restore_exactly(self):
        for path in [POOL,PRE]:
            before=subprocess.check_output(['git','show','c0f04eb7cc328a97d7a79210f2bf6a1166123ae5:'+path],cwd=ROOT)
            current=(ROOT/path).read_bytes();self.assertEqual(original_connection_fixture(current,path),before)
            self.assertEqual(original_connection_fixture(before,path),before)
            for mutated in [current+b'\n',current.replace(b'One controlled document load',b'Altered controlled document load',1),current.replace(b'60000',b'90000',1)]:
                with self.assertRaises(ValueError):original_connection_fixture(mutated,path)
        with self.assertRaises(ValueError):original_connection_fixture(b'partial',POOL)
        with self.assertRaises(ValueError):original_connection_fixture((ROOT/POOL).read_bytes(),'app/src/main/java/local/pocketchat/GeckoWebView.java')
        mutant=(ROOT/POOL).read_text().replace('unsent pool draft','mutated original draft',1)
        self.assertEqual(legacy_pool_activity_input(mutant),mutant)
        self.assertNotEqual(sha(legacy_pool_activity_input(mutant).encode()),manifest()['files'][POOL]['beforeSha256'])
        for path in ['tests/gecko/run_gecko_pool.py','tests/gecko/run_preconnect.py']:
            self.assertEqual((ROOT/path).read_bytes(),subprocess.check_output(['git','show','c0f04eb7cc328a97d7a79210f2bf6a1166123ae5:'+path],cwd=ROOT))

    def test_real_calls_are_inside_the_original_startup_budget(self):
        pool=(ROOT/POOL).read_text();pre=(ROOT/PRE).read_text()
        for text,label in [(pool,'Gecko initialization'),(pre,'Official SDK and real default network')]:
            self.assertIn('await("'+label+'",()->ui(()->view.ready&&view.privacyReady&&session.browserDefaultNetwork.snapshot().usable()&&nativeTimeZonePrerequisite.readyFor(view)),60000);',text)
            self.assertIn('check("One controlled document load is dispatched without protection or connection queueing",after.optString("queued").isEmpty()&&after.optLong("epoch",-1)==before.optLong("epoch"));',text)
        helper=member(pool,'static final class NativeTimeZonePrerequisite')
        self.assertEqual(helper.count('view.prepareTimeZone(expected,'),1)
        self.assertNotIn('.loadUri(',helper);self.assertNotIn('.loadUrl(',helper);self.assertNotIn('.setBlocked(',helper)
        self.assertNotIn('.sleep(',helper)

    def test_actual_extracted_helper_rejects_missing_stale_and_repeated_native_probes(self):
        java=Path(os.environ.get('PROFILE_JAVA') or shutil.which('java') or '')
        self.assertTrue(java.is_file(),'JDK17 required')
        sources=[ROOT/POOL,ROOT/PRE,ROOT/'app/src/main/java/local/pocketchat/J.java',HELPER,Path(__file__).resolve(),ROOT/'tests/connection_timezone_fixture_contract.py',ROOT/'tests/fixtures/connection-timezone-prerequisite-source-deltas.json']
        before={str(p.relative_to(ROOT)):sha(p.read_bytes()) for p in sources};helper=member((ROOT/POOL).read_text(),'static final class NativeTimeZonePrerequisite');runs=[];mutations=[]
        for label,env,default in [('desktop','PROFILE_JSON_JAR','json.jar'),('android-json','PROFILE_ANDROID_JSON_JAR','android-json.jar')]:
            jar=Path(os.environ.get(env,ROOT/'work/profile-host'/default));self.assertTrue(jar.is_file())
            selected=[('current',helper)]
            if label=='desktop':
                selected += [('missing-native-readback',helper.replace('Boolean.TRUE.equals(status.opt("nativeSettingReadback"))&&','true&&',1)),('repeated-native-probe',helper.replace('if(!requested){','if(true){',1)),('stale-gate',helper.replace('(gate==null||view.timeZoneGates.get(expected)==gate)','true',1))]
            for variant,body in selected:
                with tempfile.TemporaryDirectory(prefix='connection-native-prerequisite-') as temporary:
                    folder=Path(temporary);fixture=folder/'PrerequisiteHost.java';fixture.write_text(HELPER.read_text().replace('@@HELPER@@',body));classes=folder/'classes'
                    compiled=subprocess.run([str(java),'-m','jdk.compiler/com.sun.tools.javac.Main','--release','8','-encoding','UTF-8','-cp',str(jar),'-d',str(classes),str(fixture),str(ROOT/'app/src/main/java/local/pocketchat/J.java')],capture_output=True,text=True,timeout=35)
                    self.assertEqual(compiled.returncode,0,compiled.stdout+compiled.stderr)
                    ran=subprocess.run([str(java),'-cp',str(classes)+os.pathsep+str(jar),'local.pocketchat.PrerequisiteHost'],capture_output=True,text=True,timeout=20)
                    if variant!='current':
                        self.assertNotEqual(ran.returncode,0,'Removed actual prerequisite boundary was accepted: '+variant);mutations.append({'variant':variant,'compileSucceeded':True,'runtimeRejected':True});continue
                    self.assertEqual(ran.returncode,0,ran.stdout+ran.stderr);report=json.loads(ran.stdout);self.assertEqual(report['status'],'passed');runs.append({'json':label,'jsonJarSha256':sha(jar.read_bytes()),'report':report})
        self.assertTrue(all(sha(path.read_bytes())==before[str(path.relative_to(ROOT))] for path in sources))
        report={'schema':1,'status':'passed','sourceCommit':subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),'sourceFiles':before,'executionInputsUnchanged':True,'runs':runs,'mutationControls':mutations,'actualAndroidExecution':False,'actualGeckoExecution':False,'nativeReadbackVerified':False,'scope':'Verbatim real fixture native prerequisite class. Explicit SDK session/runtime/native callback/status/main-thread boundaries model async behavior only. Real actualSDK fixture compile and Android native ACK remain independent; prior complete network fixtures, runners, assertions and deadlines are preserved byte-for-byte.'}
        out=ROOT/'work/connections-native-timezone-prerequisite/host-results.json';out.parent.mkdir(parents=True,exist_ok=True);out.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')

if __name__=='__main__':unittest.main()
