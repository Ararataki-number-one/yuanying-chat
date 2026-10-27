"""Actual Java semantic models plus TLS/VM stream boundaries; never phone evidence."""
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
JAVA_SOURCES = [ROOT / 'app/src/main/java/local/pocketchat' / name for name in
                ['J.java', 'RequestIdentityAudit.java', 'RequestIdentityLanguages.java']]
JAVA_SOURCES += [ROOT / 'tests/request-identity' / name for name in
                 ['RequestIdentityAuditHost.java', 'RequestIdentityCoverageHost.java']]
PINS = {'3ea61b2a06e31edf1c91134fe9106b0ebb16628be169f3db75bc7a2b06b45796': 'desktop',
        '3cf6cd6892e32e2b4c1c39e0f52f5248a2f5b37646fdfbb79a66b46b618414ed': 'desktop',
        'dfb7bae2f404cfe0b72b4d23944698cb716b7665171812a0a4d0f5926c0fac79': 'android-json'}


def dependencies():
    choices = [os.environ.get('PROFILE_JSON_JAR'), os.environ.get('PROFILE_ANDROID_JSON_JAR'),
               ROOT / 'work/profile-host/json.jar', ROOT / 'work/profile-host/android-json.jar',
               ROOT / 'work/gecko-integration/sharing-android-json.jar']
    out = {}
    for choice in choices:
        if choice and Path(choice).is_file():
            path = Path(choice);digest = hashlib.sha256(path.read_bytes()).hexdigest()
            if digest not in PINS:
                raise AssertionError('Unpinned request-identity JSON dependency')
            out.setdefault(PINS[digest], path)
    if 'desktop' not in out:
        raise RuntimeError('Pinned desktop JSON required')
    return out


def save(name, value):
    output = ROOT / 'work/coverage-protocol' / name
    output.parent.mkdir(parents=True, exist_ok=True)
    if output.exists():
        old = output.read_bytes();archive = output.parent / 'executions' / (hashlib.sha256(old).hexdigest() + '.json')
        archive.parent.mkdir(exist_ok=True)
        if archive.exists():
            if archive.read_bytes() != old:
                raise AssertionError('Existing evidence archive differs')
        else:
            archive.write_bytes(old)
    output.write_text(json.dumps(value, indent=2) + '\n')


class RequestIdentityCoverageTest(unittest.TestCase):
    def test_languages_and_optional_frame_are_independent_bounded_observations(self):
        inputs = [*JAVA_SOURCES, Path(__file__)];before = {str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest() for p in inputs}
        java = os.environ.get('PROFILE_JAVA') or shutil.which('java')
        if not java:
            raise RuntimeError('JDK17+ required')
        runs = []
        for runtime, jar in dependencies().items():
            with tempfile.TemporaryDirectory(prefix='request-identity-coverage-') as classes:
                compilation = subprocess.run([java, '-m', 'jdk.compiler/com.sun.tools.javac.Main', '--release', '8', '-encoding', 'UTF-8',
                                              '-cp', str(jar), '-d', classes, *map(str, JAVA_SOURCES)], capture_output=True, text=True, timeout=30)
                self.assertEqual(compilation.returncode, 0, compilation.stdout + compilation.stderr)
                executed = subprocess.run([java, '-cp', classes + os.pathsep + str(jar), 'local.pocketchat.RequestIdentityCoverageHost'],
                                          capture_output=True, text=True, timeout=15)
                report = json.loads(executed.stdout)
                runs.append(dict(runtime=runtime, jsonSha256=hashlib.sha256(jar.read_bytes()).hexdigest(),
                                 compileStdout=compilation.stdout, compileStderr=compilation.stderr,
                                 runtimeStdout=executed.stdout, runtimeStderr=executed.stderr, exitCode=executed.returncode, report=report))
        unchanged = before == {str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest() for p in inputs}
        receipt = dict(status='passed' if unchanged and all(x['exitCode'] == 0 for x in runs) else 'failed', sourceSha256=before,
                       executionInputsUnchanged=unchanged, runs=runs, actualAndroidExecution=False, actualGeckoExecution=False,
                       scope='Actual production Java language/admission/frame parsing on controlled JSON only')
        save('language-frame-model-results.json', receipt)
        self.assertTrue(unchanged)
        for row in runs:
            self.assertEqual(row['exitCode'], 0, row['runtimeStdout'] + row['runtimeStderr'])
            report = row['report'];self.assertEqual(report['status'], 'passed')
            self.assertEqual(report['total'], report['passed']);self.assertEqual(report['total'], len(report['checks']))
            self.assertEqual(report['total'], 109)
            self.assertTrue(all(check['pass'] is True for check in report['checks']))

    def test_actual_tls_service_and_generated_worker_stream_boundaries(self):
        node = shutil.which('node')
        if not node:
            raise RuntimeError('Node required')
        inputs = [ROOT / 'tools/fingerprint/request_identity_server.cjs', ROOT / 'tools/fingerprint/context_graphics_probe.cjs',
                  ROOT / 'tests/request-identity/request_identity_server_test.cjs', ROOT / 'tests/request-identity/worker_response_bounds_test.cjs',
                  ROOT / 'tests/request-identity/fixtures/worker-script-before-d0d648cc.js', Path(__file__)]
        before = {str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest() for p in inputs}
        runs = []
        for script, count in [('request_identity_server_test.cjs', 18), ('worker_response_bounds_test.cjs', 10)]:
            cmd = [node, '--test-reporter=tap', str(ROOT / 'tests/request-identity' / script)]
            result = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True, timeout=20)
            counts = {key: int(match.group(1)) for key in ['tests', 'pass', 'fail']
                      if (match := re.search(r'^# ' + key + r' (\d+)$', result.stdout, re.MULTILINE))}
            runs.append(dict(script=script, command=cmd, exitCode=result.returncode, stdout=result.stdout, stderr=result.stderr,
                             counts=counts, expectedTests=count))
        unchanged = before == {str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest() for p in inputs}
        save('tls-generated-worker-results.json', dict(status='passed' if unchanged and all(x['exitCode'] == 0 for x in runs) else 'failed',
             sourceSha256=before, executionInputsUnchanged=unchanged, runs=runs, actualTlsExecution=True,
             actualWorkerRuntime='Node VM with controlled byte streams', actualGeckoExecution=False, actualAndroidExecution=False,
             scope='Actual Node TLS receiver and production-generated Worker parser; VM signals are not browser, Gecko or phone evidence'))
        self.assertTrue(unchanged)
        for row in runs:
            self.assertEqual(row['exitCode'], 0, row['stdout'] + row['stderr'])
            self.assertEqual(row['counts'].get('tests'), row['expectedTests'])
            self.assertEqual(row['counts'].get('pass'), row['expectedTests']);self.assertEqual(row['counts'].get('fail'), 0)


if __name__ == '__main__':
    unittest.main()
