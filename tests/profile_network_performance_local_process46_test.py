"""Preserve real sampling checks while adapting only local-process renderer inputs."""
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import unittest
from experience46_host_evidence import emit_evidence,new_attempt,run_recorded,INVOCATION_FILES
ROOT=Path(__file__).resolve().parents[1];PROD=ROOT/'app/src/main/java/local/pocketchat';HERE=ROOT/'tests/network-performance-read-model46-host';FIXTURE=ROOT/'tests/gecko/NetworkOptimizationIntegrationActivity.java'
CHECK_CALLS_SHA256='a468e12f21289cc2cbe6e414347348ef650a205413197436f47cb75087aff341'
PINS={'desktop':'3ea61b2a06e31edf1c91134fe9106b0ebb16628be169f3db75bc7a2b06b45796','android':'dfb7bae2f404cfe0b72b4d23944698cb716b7665171812a0a4d0f5926c0fac79'}

def check_calls(text):
    out=[]
    for match in re.finditer(r'\bcheck\(\s*"',text):
        start=match.start();opening=text.index('(',start);depth=0;quote=False;escape=False
        for at in range(opening,len(text)):
            char=text[at]
            if quote:
                if escape:escape=False
                elif char=='\\':escape=True
                elif char=='"':quote=False
            elif char=='"':quote=True
            elif char=='(':depth+=1
            elif char==')':
                depth-=1
                if depth==0:out.append(text[start:at+1]);break
    return out

class LocalProcessProjection46(unittest.TestCase):
    def test_all_original166_sampling_and_network_check_expressions_are_byte_exact(self):
        source=FIXTURE.read_text();calls=check_calls(source);self.assertEqual(len(calls),166);self.assertEqual(hashlib.sha256(json.dumps(calls,separators=(',',':')).encode()).hexdigest(),CHECK_CALLS_SHA256)
        for old,new in [('initialState.latency.matches("[0-9]+ ms")','initialState.latency.contains("ms")'),('plain.probeRequests.get()==initialRequests+2','plain.probeRequests.get()>=initialRequests+2')]:
            self.assertIn(old,source);changed=source.replace(old,new,1);self.assertNotEqual(hashlib.sha256(json.dumps(check_calls(changed),separators=(',',':')).encode()).hexdigest(),CHECK_CALLS_SHA256)
    def test_reviewed_whole_fixture_inverse_preserves_older_oracle_and_rejects_counterfeits(self):
        from unittest.mock import patch
        import network_performance46_fixture_compatibility as compatibility
        current=FIXTURE.read_bytes();prior=compatibility.restore_to_source3(current);self.assertEqual(hashlib.sha256(prior).hexdigest(),compatibility.PREVIOUS_SHA);self.assertEqual(compatibility.restore_to_source3(prior),prior)
        changes=compatibility.manifest()['changes'];mutants=[current+b'\n']
        for row in changes:
            literal=(row['before']+row['new']+row['after']).encode();self.assertEqual(current.count(literal),1)
            mutants.append(current.replace(literal,(row['before']+row['old']+row['after']).encode(),1))
            mutants.append(current.replace(literal,(row['before']+row['new']+row['new']+row['after']).encode(),1))
            mutants.append(current.replace(literal,(row['before']+row['after']).encode(),1)+row['new'].encode())
        for mutated in mutants:
            with self.subTest(mutantSha=hashlib.sha256(mutated).hexdigest()),self.assertRaises(ValueError):compatibility.restore_to_source3(mutated)
        with self.assertRaises(ValueError):compatibility.restore_to_source3(current,'other/fixture.java')
        legacy=ROOT/'tests/profile_failed_chain_fixture_config_test.py';raw=legacy.read_bytes();imported=b'from network_performance46_fixture_compatibility import input_for_original_fixture\n';normalized=b' current=input_for_original_fixture(current)\n';self.assertEqual(raw.count(imported),1);self.assertEqual(raw.count(normalized),1);self.assertEqual(hashlib.sha256(raw.replace(imported,b'',1).replace(normalized,b'',1)).hexdigest(),'f5c95f9d8422f93f97bcd012af877cceeb4ce3df615bd30107f023a2d41ccf39')
        spec=importlib.util.spec_from_file_location('exact_old_failed_chain_consumer',legacy);old=importlib.util.module_from_spec(spec);spec.loader.exec_module(old);self.assertEqual(hashlib.sha256(old.original_fixture(current.decode()).encode()).hexdigest(),old.ORIGINAL_SHA)
        with __import__('tempfile').TemporaryDirectory(prefix='performance46-inverse-negative-')as directory:
            fake=Path(directory)/compatibility.MANIFEST_PATH;fake.parent.mkdir(parents=True);fake.write_bytes((ROOT/compatibility.MANIFEST_PATH).read_bytes()+b' ')
            with patch.object(compatibility,'ROOT',Path(directory)),self.assertRaises(ValueError):compatibility.manifest()
    def test_actual_cold_producer_and_local_fixture_boundary_on_both_json_runtimes(self):
        java=Path(os.environ.get('PROFILE_JAVA') or shutil.which('java') or '').resolve();self.assertTrue(java.is_file());home=java.parents[1]
        choices=[('desktop',[os.environ.get('PROFILE_JSON_JAR',''),str(ROOT/'work/profile-host/json.jar'),str(ROOT/'work/gecko-integration/catalog-json.jar')]),('android',[os.environ.get('PROFILE_ANDROID_JSON_JAR',''),str(ROOT/'work/profile-host/android-json.jar'),str(ROOT/'work/gecko-integration/sharing-android-json.jar')])]
        spec=importlib.util.spec_from_file_location('projection46_member',ROOT/'tests/chrome-network-state-host/run.py');extract=importlib.util.module_from_spec(spec);spec.loader.exec_module(extract);member=extract.member
        names=['WindowNetworkState','NetworkCoreApplication','NativeNetwork','NetworkCatalog','LatencyRefreshPolicy','LatencyProbePolicy','NetworkStatusPolicy','NetworkOptimizationPolicy','Sha256','NetworkHealthPolicy','EnvironmentSpec','J'];text={name:(PROD/(name+'.java')).read_text() for name in names};fixture=FIXTURE.read_text();cold_template=ROOT/'tests/window-network-identity-host/ColdCoreWindowStateHost.java.in'
        inputs=[PROD/(name+'.java')for name in names]+[FIXTURE,cold_template,HERE/'LocalProcessProjection46Host.java.in',Path(__file__).resolve(),ROOT/'tests/chrome-network-state-host/run.py'];before={str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest()for p in inputs}
        replacements={'STATE_FIELDS':next(line for line in text['WindowNetworkState'].splitlines()if line.startswith('  final int slot;')),'STATE_IDENTITY':member(text['WindowNetworkState'],'static boolean sameEnvironment('),'STATE_CONSTRUCTOR':member(text['WindowNetworkState'],'WindowNetworkState(Context c,'),'STATE_RUNNING':member(text['WindowNetworkState'],'static JSONObject running('),'STATE_LIVE':member(text['WindowNetworkState'],'static JSONObject live('),'CORE_OBSERVED':member(text['NetworkCoreApplication'],'static NetworkCoreApplication observed('),'CORE_CURRENT':member(text['NetworkCoreApplication'],'boolean current('),'CATALOG_EXIT_ID':member(text['NetworkCatalog'],'static String exitId('),'CATALOG_SUBSCRIPTION':member(text['NetworkCatalog'],'static String subscriptionName('),'CATALOG_PUT':member(text['NetworkCatalog'],'static void put('),'NATIVE_METHODS':'\n'.join(member(text['NativeNetwork'],n)for n in ['static boolean subscribedExit(','static String exitIdentity(','static String hash(']),'NATIVE_ADMISSION':member(text['NativeNetwork'],'NetworkHealthPolicy.Admission connectionAdmission('),'NATIVE_RECEIPT':member(text['NativeNetwork'],'static final class ExitRouteReceipt {')}
        cold=cold_template.read_text()
        for key,value in replacements.items():cold=cold.replace('/* '+key+' */',value)
        actual_methods='\n'.join(member(fixture,n)for n in ['static JSONObject controlledReadModel(','static JSONObject controlledLocalProcessReadModel(']);test=(HERE/'LocalProcessProjection46Host.java.in').read_text().replace('/* ACTUAL_FIXTURE_METHODS */',actual_methods)
        stubs={'android/os/Process.java':'package android.os;public class Process{public static int myPid(){return 1234;}}','android/content/Context.java':'package android.content;public class Context{public static Runnable beforeRead;public SharedPreferences getSharedPreferences(String name,int mode){Runnable hook=beforeRead;beforeRead=null;if(hook!=null)hook.run();return new SharedPreferences();}}','android/content/SharedPreferences.java':'package android.content;public class SharedPreferences{public static String mode="internal",proxy="";public static boolean configured=true;public String getString(String key,String fallback){return key.equals("networkMode")?mode:key.equals("proxy")?proxy:fallback;}public boolean getBoolean(String key,boolean fallback){return key.equals("networkConfigured")?configured:fallback;}}','android/net/Uri.java':'package android.net;public class Uri{String value;public static Uri parse(String value){Uri uri=new Uri();uri.value=value;return uri;}public String getHost(){return java.net.URI.create(value).getHost();}}'}
        for label,options in choices:
            jar=next((Path(p)for p in options if p and Path(p).is_file()),None);self.assertIsNotNone(jar);self.assertEqual(hashlib.sha256(jar.read_bytes()).hexdigest(),PINS[label]);output=new_attempt(ROOT/'work/profile-host/network-performance-local46',label);src=output/'src';src.mkdir()
            (src/'ColdCoreWindowStateHost.java').write_text(cold);(src/'LocalProcessProjection46Host.java').write_text(test)
            for name in ['LatencyRefreshPolicy','LatencyProbePolicy','NetworkStatusPolicy','NetworkOptimizationPolicy','Sha256','NetworkHealthPolicy','EnvironmentSpec','J']:(src/(name+'.java')).write_text(text[name])
            for name,value in stubs.items():p=src/name;p.parent.mkdir(parents=True,exist_ok=True);p.write_text(value)
            classes=output/'classes'
            try:
                result=run_recorded([str(home/'bin/javac'),'-encoding','UTF-8','-cp',str(jar),'-d',str(classes),*map(str,sorted(src.rglob('*.java')))],output,cwd=ROOT,timeout=45);(output/'compile.stdout.log').write_bytes(result.stdout);(output/'compile.stderr.log').write_bytes(result.stderr);self.assertEqual(result.returncode,0,result.stdout+result.stderr)
                # Use a separate controlled output directory for the actual execution.
                execution=new_attempt(output,'execute')
                try:
                    result=run_recorded([str(java),'-cp',str(classes)+':'+str(jar),'local.pocketchat.LocalProcessProjection46Host'],execution,cwd=ROOT,timeout=30);self.assertEqual(result.returncode,0,result.stdout+result.stderr);report=json.loads(result.stdout);self.assertEqual(report['status'],'passed');self.assertEqual(report['passed'],22);self.assertTrue(all(c['pass']is True for c in report['checks']));report.update(sourceFiles=before,jsonJarSha256=PINS[label],executedFixtureMethodsSha256=hashlib.sha256(actual_methods.encode()).hexdigest(),sourceCommit=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),sourceDirty=bool(subprocess.check_output(['git','status','--porcelain'],cwd=ROOT,text=True).strip()));(execution/'results.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
                finally:emit_evidence(execution,('results.json',*INVOCATION_FILES),label='network-performance-local46-'+label+'-execute')
            finally:emit_evidence(output,('compile.stdout.log','compile.stderr.log',*INVOCATION_FILES),label='network-performance-local46-'+label+'-compile')
        self.assertEqual(before,{str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest()for p in inputs})
if __name__=='__main__':unittest.main(verbosity=2)
