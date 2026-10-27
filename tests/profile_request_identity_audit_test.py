"""Production request-identity model controls on pinned JVM JSON implementations."""
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
SOURCES = [ROOT / 'app/src/main/java/local/pocketchat/J.java',
           ROOT / 'app/src/main/java/local/pocketchat/RequestIdentityAudit.java',
           ROOT / 'tests/request-identity/RequestIdentityAuditHost.java']
PINS = {'3ea61b2a06e31edf1c91134fe9106b0ebb16628be169f3db75bc7a2b06b45796': 'desktop',
        '3cf6cd6892e32e2b4c1c39e0f52f5248a2f5b37646fdfbb79a66b46b618414ed': 'desktop',
        'dfb7bae2f404cfe0b72b4d23944698cb716b7665171812a0a4d0f5926c0fac79': 'android-json'}


def dependencies():
    values = [os.environ.get('PROFILE_JSON_JAR'), os.environ.get('PROFILE_ANDROID_JSON_JAR'),
              ROOT / 'work/profile-host/json.jar', ROOT / 'work/profile-host/android-json.jar',
              ROOT / 'work/gecko-integration/catalog-json.jar', ROOT / 'work/gecko-integration/sharing-android-json.jar']
    result = {}
    for value in values:
        if not value or not Path(value).is_file():
            continue
        file = Path(value)
        digest = hashlib.sha256(file.read_bytes()).hexdigest()
        if digest not in PINS:
            raise AssertionError('Unexpected request-identity JSON runtime digest')
        result.setdefault(PINS[digest], file)
    if 'desktop' not in result:
        raise RuntimeError('Pinned JSON-java jar required; pass PROFILE_JSON_JAR')
    return result


class RequestIdentityAuditTest(unittest.TestCase):
    def test_extension_scope_and_late_message_controls_with_mock_browser_boundaries(self):
        node = shutil.which('node')
        if not node:
            raise RuntimeError('Node required for request-identity extension boundary controls')
        script = ROOT / 'tests/request-identity/request_identity_extension_test.cjs'
        command = [node, '--test-reporter=tap', str(script)]
        run = subprocess.run(command, cwd=ROOT, capture_output=True, text=True, timeout=15)
        counts = {name: int(match.group(1)) for name in ['tests', 'pass', 'fail']
                  if (match := re.search(r'^# ' + name + r' ([0-9]+)$', run.stdout, re.MULTILINE))}
        files = [script, ROOT / 'app/src/main/assets/gecko/request-identity-background.js',
                 ROOT / 'app/src/main/assets/gecko/request-identity-audit.js', Path(__file__)]
        receipt = dict(status='passed' if run.returncode == 0 else 'failed', returncode=run.returncode,
                       counts=counts, command=command, stdout=run.stdout, stderr=run.stderr,
                       sourceSha256={str(file.relative_to(ROOT)): hashlib.sha256(file.read_bytes()).hexdigest() for file in files},
                       actualAndroidExecution=False, actualGeckoExecution=False, actualWebRequestExecution=False,
                       actualHttpExecution=False, scope='Node VM with fake browser/WebRequest/window boundaries; not real browser or network acceptance')
        target = ROOT / 'work/fingerprint-followups/request-identity-extension-host-results.json'
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(json.dumps(receipt, indent=2) + '\n')
        self.assertEqual(run.returncode, 0, run.stdout + run.stderr)
        self.assertGreaterEqual(counts.get('tests', 0), 14)
        self.assertEqual(counts.get('pass'), counts.get('tests'))
        self.assertEqual(counts.get('fail'), 0)

    def test_independent_request_sources_and_malformed_evidence_never_imply_full_fingerprint_acceptance(self):
        java = os.environ.get('PROFILE_JAVA') or shutil.which('java')
        if not java:
            raise RuntimeError('JDK required for production request-identity model controls')
        runs = []
        for runtime, jar in dependencies().items():
            with tempfile.TemporaryDirectory(prefix='request-identity-model-host-') as temporary:
                compile_run = subprocess.run([java, '-m', 'jdk.compiler/com.sun.tools.javac.Main', '--release', '8',
                                              '-encoding', 'UTF-8', '-cp', str(jar), '-d', temporary, *map(str, SOURCES)],
                                             capture_output=True, text=True, timeout=30)
                self.assertEqual(compile_run.returncode, 0, compile_run.stdout + compile_run.stderr)
                run = subprocess.run([java, '-cp', temporary + os.pathsep + str(jar), 'local.pocketchat.RequestIdentityAuditHost'],
                                     capture_output=True, text=True, timeout=15)
                report = json.loads(run.stdout)
                runs.append(dict(jsonRuntime=runtime, jsonJarSha256=hashlib.sha256(jar.read_bytes()).hexdigest(),
                                 compileStdout=compile_run.stdout, compileStderr=compile_run.stderr,
                                 runtimeStdout=run.stdout, runtimeStderr=run.stderr, returncode=run.returncode, report=report))
        target = ROOT / 'work/fingerprint-followups/request-identity-host-results.json'
        target.parent.mkdir(parents=True, exist_ok=True)
        receipt = dict(status='passed' if all(row['returncode'] == 0 for row in runs) else 'failed',
                       actualAndroidExecution=False, actualGeckoExecution=False, actualHttpExecution=False,
                       sourceSha256={str(file.relative_to(ROOT)): hashlib.sha256(file.read_bytes()).hexdigest() for file in [*SOURCES, Path(__file__)]},
                       scope='Real production J and request-identity comparison model on pinned JSON jars, controlled payloads only', runs=runs)
        target.write_text(json.dumps(receipt, indent=2) + '\n')
        for run in runs:
            report = run['report']
            self.assertEqual(run['returncode'], 0, run['runtimeStdout'] + run['runtimeStderr'])
            self.assertEqual(report['status'], 'passed')
            self.assertEqual(report['passed'], report['total'])
            self.assertEqual(report['total'], len(report['checks']))
            self.assertGreaterEqual(report['passed'], 60)
            self.assertTrue(all(row['pass'] is True for row in report['checks']))
            self.assertFalse(report['actualAndroidExecution'])
            self.assertFalse(report['actualHttpExecution'])


if __name__ == '__main__':
    unittest.main()
