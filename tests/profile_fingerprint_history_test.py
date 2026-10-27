"""Production local history/report controls on JVM JSON implementations, not Gecko."""
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
PRODUCTION = ROOT / 'app/src/main/java/local/pocketchat'
HOST = ROOT / 'tests/fingerprint-history-host/FingerprintObservationHistoryHost.java'
SOURCES = [PRODUCTION / 'FingerprintObservationHistory.java', PRODUCTION / 'AuditReport.java',
           ROOT / 'tests/browser-runtime/fingerprint-report-stubs/J.java',
           ROOT / 'tests/browser-runtime/fingerprint-report-stubs/BrowserNetworkGuard.java', HOST]
PINS = {'3ea61b2a06e31edf1c91134fe9106b0ebb16628be169f3db75bc7a2b06b45796': 'desktop',
        '3cf6cd6892e32e2b4c1c39e0f52f5248a2f5b37646fdfbb79a66b46b618414ed': 'desktop',
        'dfb7bae2f404cfe0b72b4d23944698cb716b7665171812a0a4d0f5926c0fac79': 'android-json'}


def dependencies():
    choices = [os.environ.get('PROFILE_JSON_JAR'), os.environ.get('PROFILE_ANDROID_JSON_JAR'),
               ROOT / 'work/profile-host/json.jar', ROOT / 'work/profile-host/android-json.jar',
               ROOT / 'work/gecko-integration/catalog-json.jar', ROOT / 'work/gecko-integration/sharing-android-json.jar']
    result = {}; seen = set()
    for value in choices:
        if not value:
            continue
        path = Path(value)
        if not path.is_file():
            continue
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        if digest not in PINS:
            raise AssertionError('Unexpected JSON runtime dependency digest')
        if digest not in seen:
            result.setdefault(PINS[digest], path); seen.add(digest)
    if 'desktop' not in result:
        raise RuntimeError('Pinned JSON-java jar required; pass PROFILE_JSON_JAR')
    return result


class FingerprintObservationHistoryTest(unittest.TestCase):
    def test_bounded_owned_history_and_honest_operation_states(self):
        inputs = [*SOURCES, Path(__file__)]
        before = {str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest() for p in inputs}
        java = os.environ.get('PROFILE_JAVA') or shutil.which('java')
        if not java:
            raise RuntimeError('JDK17+ required for production fingerprint history checks')
        reports = []
        for runtime, jar in dependencies().items():
            with tempfile.TemporaryDirectory(prefix='fingerprint-history-host-') as classes:
                compile_run = subprocess.run([java, '-m', 'jdk.compiler/com.sun.tools.javac.Main', '--release', '8',
                                              '-encoding', 'UTF-8', '-cp', str(jar), '-d', classes, *map(str, SOURCES)],
                                             capture_output=True, text=True, timeout=30)
                self.assertEqual(compile_run.returncode, 0, compile_run.stdout + compile_run.stderr)
                run = subprocess.run([java, '-cp', classes + os.pathsep + str(jar), 'local.pocketchat.FingerprintObservationHistoryHost'],
                                     capture_output=True, text=True, timeout=15)
                self.assertEqual(run.returncode, 0, run.stdout + run.stderr)
                result = json.loads(run.stdout)
                self.assertEqual(result['status'], 'passed')
                self.assertEqual(result['passed'], result['total'])
                self.assertEqual(result['total'], len(result['checks']))
                self.assertEqual(result['total'], 82)
                self.assertTrue(all(row['pass'] is True for row in result['checks']))
                self.assertFalse(result['actualAndroidExecution'])
                reports.append(dict(jsonRuntime=runtime, jsonJarSha256=hashlib.sha256(jar.read_bytes()).hexdigest(),
                                    compileStdout=compile_run.stdout, compileStderr=compile_run.stderr,
                                    runtimeStdout=run.stdout, runtimeStderr=run.stderr, report=result))
        self.assertEqual(before, {str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest() for p in inputs})
        receipt = dict(status='passed', actualAndroidExecution=False, actualGeckoExecution=False, executionInputsUnchanged=True,
                       sourceSha256=before, originalControlCount=60, retainedGapControlCount=18, addedEvictionControlCount=4,
                       runs=reports, scope='Local pure-Java history and report processing on pinned JSON jars; no phone, Gecko or privacy-effectiveness verdict')
        target = ROOT / 'work/fingerprint-history-eviction-fix-20261027/history-host-results.json'
        target.parent.mkdir(parents=True, exist_ok=True)
        if target.exists():
            original = target.read_bytes()
            archive = target.parent / 'history-host-executions' / (hashlib.sha256(original).hexdigest() + '.json')
            archive.parent.mkdir(exist_ok=True)
            if archive.exists():
                self.assertEqual(archive.read_bytes(), original)
            else:
                archive.write_bytes(original)
        target.write_text(json.dumps(receipt, indent=2) + '\n')


if __name__ == '__main__':
    unittest.main()
