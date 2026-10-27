"""Actual service controller/helper with JVM and VM boundaries, never phone acceptance."""
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[1]
JAVA=ROOT/'app/src/main/java/local/pocketchat'
SOURCES=[JAVA/'J.java',JAVA/'RequestIdentityAudit.java',JAVA/'RequestIdentityLanguages.java',JAVA/'RequestIdentityServiceProbe.java',ROOT/'tests/service-probe/RequestIdentityServiceProbeHost.java',ROOT/'tests/service-probe/SystemClock.java']
PINS={'3ea61b2a06e31edf1c91134fe9106b0ebb16628be169f3db75bc7a2b06b45796':'desktop-json','dfb7bae2f404cfe0b72b4d23944698cb716b7665171812a0a4d0f5926c0fac79':'android-json'}

def dependencies():
    roots=[ROOT/'work/profile-host',Path('/tmp/pocketchat-fingerprint-next-20261027/work/profile-host')]
    choices=[os.environ.get('PROFILE_JSON_JAR'),os.environ.get('PROFILE_ANDROID_JSON_JAR')]+[p/name for p in roots for name in ['json.jar','android-json.jar']]
    out={}
    for value in choices:
        if not value:continue
        p=Path(value)
        if not p.is_file():continue
        sha=hashlib.sha256(p.read_bytes()).hexdigest()
        if sha not in PINS:raise AssertionError('Unexpected service probe JSON dependency')
        out.setdefault(PINS[sha],p)
    if set(out)!=set(PINS.values()):raise RuntimeError('Both pinned JSON jars are required')
    return out

class ServiceProbeTest(unittest.TestCase):
    def test_production_controller_and_real_uri_admission_with_controlled_session_boundaries(self):
        java=os.environ.get('PROFILE_JAVA') or shutil.which('java')
        self.assertTrue(java,'JDK required')
        before={str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in SOURCES}
        runs=[]
        for name,jar in dependencies().items():
            with tempfile.TemporaryDirectory(prefix='service-probe-host-') as classes:
                compiled=subprocess.run([java,'-m','jdk.compiler/com.sun.tools.javac.Main','--release','8','-encoding','UTF-8','-cp',str(jar),'-d',classes,*map(str,SOURCES)],text=True,capture_output=True,timeout=30)
                self.assertEqual(compiled.returncode,0,compiled.stdout+compiled.stderr)
                run=subprocess.run([java,'-cp',classes+os.pathsep+str(jar),'local.pocketchat.RequestIdentityServiceProbeHost'],text=True,capture_output=True,timeout=15)
                self.assertEqual(run.returncode,0,run.stdout+run.stderr)
                result=json.loads(run.stdout);self.assertEqual(result['status'],'passed');self.assertEqual(result['passed'],result['total']);self.assertEqual(result['total'],len(result['checks']));self.assertEqual(result['total'],103);self.assertTrue(all(row['pass'] is True for row in result['checks']));self.assertIs(result['actualAndroidExecution'],False)
                runs.append(dict(jsonRuntime=name,jsonJarSha256=hashlib.sha256(jar.read_bytes()).hexdigest(),compileStdout=compiled.stdout,compileStderr=compiled.stderr,stdout=run.stdout,stderr=run.stderr,result=result))
        self.assertEqual(before,{str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in SOURCES})
        p=ROOT/'work/coverage-service/controller-host-results.json';p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(dict(status='passed',sourceSha256=before,runs=runs,actualAndroidExecution=False,actualHttpExecution=False),indent=2)+'\n')
    def test_production_helper_purpose_size_and_cancellation_boundaries(self):
        script=ROOT/'tests/service-probe/service_probe_extension_test.cjs';run=subprocess.run(['node','--test-reporter=tap',str(script)],cwd=ROOT,text=True,capture_output=True,timeout=15)
        self.assertEqual(run.returncode,0,run.stdout+run.stderr)
        counts={key:int(re.search(r'^# '+key+r' (\d+)$',run.stdout,re.M).group(1)) for key in ['tests','pass','fail']};self.assertEqual(counts['tests'],21);self.assertEqual(counts['tests'],counts['pass']);self.assertEqual(counts['fail'],0)
        p=ROOT/'work/coverage-service/extension-results.json';p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(dict(status='passed',counts=counts,stdout=run.stdout,stderr=run.stderr,sourceSha256={str(f.relative_to(ROOT)):hashlib.sha256(f.read_bytes()).hexdigest() for f in [script,ROOT/'app/src/main/assets/gecko/request-identity-background.js']},actualAndroidExecution=False,actualHttpExecution=False),indent=2)+'\n')
    def test_actual_trusted_loopback_tls_and_bounded_service_failures(self):
        script=ROOT/'tests/service-probe/service_probe_tls_test.cjs';run=subprocess.run(['node','--test-reporter=tap',str(script)],cwd=ROOT,text=True,capture_output=True,timeout=15)
        self.assertEqual(run.returncode,0,run.stdout+run.stderr)
        p=ROOT/'work/coverage-service/tls-results.json';result=json.loads(p.read_text());self.assertEqual(result['status'],'passed');self.assertIs(result['executionInputsUnchanged'],True);self.assertIs(result['actualHttpsLoopbackExecution'],True);self.assertIs(result['actualGeckoExecution'],False);self.assertEqual(len(result['checks']),14);self.assertTrue(all(row['pass'] is True for row in result['checks']))
        (ROOT/'work/coverage-service/tls-wrapper-results.json').write_text(json.dumps(dict(status='passed',stdout=run.stdout,stderr=run.stderr,actualHttpsLoopbackExecution=True,actualAndroidExecution=False,reportSha256=hashlib.sha256(p.read_bytes()).hexdigest()),indent=2)+'\n')

if __name__=='__main__':unittest.main()
