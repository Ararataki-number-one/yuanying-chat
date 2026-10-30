"""Explicit client coverage is independent of optional service support claims."""
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / 'app/src/main/java/local/pocketchat'
FILES = [SOURCE / p for p in ['J.java', 'RequestIdentityAudit.java', 'RequestIdentityLanguages.java', 'RequestIdentityServiceProbe.java']]
FILES += [ROOT / 'tests/service-probe/RequestIdentityServiceProbeHost.java', ROOT / 'tests/service-probe/SystemClock.java', ROOT / 'tests/request-identity/RequestIdentityAuditHost.java', ROOT / 'tests/background-coverage44/BackgroundCoverage44Host.java']


class BackgroundWorkerCoverageTests(unittest.TestCase):
    def test_models_and_summaries_do_not_promote_server_declarations(self):
        from profile_service_probe_test import dependencies
        java = os.environ.get('PROFILE_JAVA') or shutil.which('java')
        self.assertTrue(java, 'JDK required')
        hashes = {str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest() for p in FILES}
        runs = []
        for runtime, jar in dependencies().items():
            with tempfile.TemporaryDirectory(prefix='background-coverage44-') as temp:
                compiled = subprocess.run([java, '-m', 'jdk.compiler/com.sun.tools.javac.Main', '--release', '8', '-encoding', 'UTF-8', '-cp', str(jar), '-d', temp, *map(str, FILES)], capture_output=True, text=True, timeout=30)
                self.assertEqual(compiled.returncode, 0, compiled.stdout + compiled.stderr)
                ran = subprocess.run([java, '-cp', temp + os.pathsep + str(jar), 'local.pocketchat.BackgroundCoverage44Host'], capture_output=True, text=True, timeout=15)
                self.assertEqual(ran.returncode, 0, ran.stdout + ran.stderr)
                result = json.loads(ran.stdout)
                self.assertEqual(result['status'], 'passed')
                self.assertEqual(result['passed'], result['total'])
                self.assertEqual(result['total'], 37)
                self.assertTrue(all(x['passed'] is True for x in result['checks']))
                runs.append(dict(runtime=runtime, jsonJarSha256=hashlib.sha256(jar.read_bytes()).hexdigest(), result=result))
        self.assertEqual(hashes, {str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest() for p in FILES})
        out = ROOT / 'work/44-worker-coverage/model-results.json'
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(dict(status='passed', sourceFiles=hashes, executionInputsUnchanged=True, runs=runs, actualAndroidExecution=False, actualGeckoExecution=False), indent=2) + '\n')

    def test_reference_tls_service_declares_limits_and_rejects_new_paths(self):
        script = ROOT / 'tests/background-coverage44/background_coverage_tls_test.cjs'
        ran = subprocess.run(['node', '--test-reporter=tap', str(script)], cwd=ROOT, capture_output=True, text=True, timeout=20)
        self.assertEqual(ran.returncode, 0, ran.stdout + ran.stderr)
        out = ROOT / 'work/44-worker-coverage/tls-test.log'
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(ran.stdout + ran.stderr)

    def test_service_promotion_and_string_coercion_counterexamples_fail(self):
        from profile_service_probe_test import dependencies
        java = os.environ.get('PROFILE_JAVA') or shutil.which('java')
        self.assertTrue(java, 'JDK required')
        jar = dependencies()['desktop-json']
        path = SOURCE / 'RequestIdentityAudit.java'
        original = path.read_text()
        changes = [
            ('server claim promoted to observation', '"state","not-covered","serviceStatement"', '"state",Boolean.TRUE.equals(value)?"observed":"not-covered","serviceStatement"'),
            ('string true coerced to support', 'String statement=Boolean.TRUE.equals(value)?', 'String statement="true".equals(String.valueOf(value))?'),
        ]
        outcomes = []
        for label, before, after in changes:
            with self.subTest(label=label):
                self.assertEqual(original.count(before), 1)
                injected = original.replace(before, after, 1)
                with tempfile.TemporaryDirectory(prefix='background-coverage44-counterexample-') as temp:
                    mutated = Path(temp) / 'RequestIdentityAudit.java'
                    mutated.write_text(injected)
                    sources = [mutated if p == path else p for p in FILES]
                    compiled = subprocess.run([java, '-m', 'jdk.compiler/com.sun.tools.javac.Main', '--release', '8', '-encoding', 'UTF-8', '-cp', str(jar), '-d', temp, *map(str, sources)], capture_output=True, text=True, timeout=30)
                    self.assertEqual(compiled.returncode, 0, compiled.stdout + compiled.stderr)
                    ran = subprocess.run([java, '-cp', temp + os.pathsep + str(jar), 'local.pocketchat.BackgroundCoverage44Host'], capture_output=True, text=True, timeout=15)
                    self.assertNotEqual(ran.returncode, 0)
                    self.assertIn('AssertionError', ran.stderr)
                    outcomes.append(dict(label=label, injectedSourceSha256=hashlib.sha256(injected.encode()).hexdigest(), exitCode=ran.returncode, stderr=ran.stderr))
        self.assertEqual(original, path.read_text())
        out = ROOT / 'work/44-worker-coverage/negative-model-results.json'
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(dict(status='counterexamples-rejected', counterexamples=outcomes, originalSourceSha256=hashlib.sha256(original.encode()).hexdigest(), actualAndroidExecution=False), indent=2) + '\n')


if __name__ == '__main__':
    unittest.main()
