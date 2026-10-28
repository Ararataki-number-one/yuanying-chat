"""Two owner-bound local mode snapshots; host validation is not phone acceptance."""
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
SOURCES = [PRODUCTION / name for name in (
    'FingerprintReportComparison.java', 'FingerprintContextBaselines.java',
    'FingerprintDeepBaseline.java', 'FingerprintObservationHistory.java',
    'AuditReport.java', 'BrowserIdentitySpec.java', 'J.java')]
SOURCES += [ROOT / name for name in (
    'tests/browser-runtime/fingerprint-report-stubs/BrowserNetworkGuard.java',
    'tests/fingerprint-baseline-host/FingerprintDeepBaselineHost.java',
    'tests/fingerprint-context-baseline-host/FingerprintContextBaselinesHost.java',
    'tests/fingerprint-comparison-host/FingerprintReportComparisonHost.java')]
PINS = {'desktop': '3ea61b2a06e31edf1c91134fe9106b0ebb16628be169f3db75bc7a2b06b45796',
        'android-json': 'dfb7bae2f404cfe0b72b4d23944698cb716b7665171812a0a4d0f5926c0fac79'}


def dependencies():
    paths = {'desktop': os.environ.get('PROFILE_JSON_JAR', str(ROOT / 'work/profile-host/json.jar')),
             'android-json': os.environ.get('PROFILE_ANDROID_JSON_JAR', str(ROOT / 'work/profile-host/android-json.jar'))}
    result = {}
    for runtime, value in paths.items():
        path = Path(value)
        if not path.is_file() or hashlib.sha256(path.read_bytes()).hexdigest() != PINS[runtime]:
            raise AssertionError('The pinned comparison JSON dependency is required: ' + runtime)
        result[runtime] = path
    return result


class FingerprintReportComparisonTest(unittest.TestCase):
    def test_bounded_owned_mode_pair_states_manual_findings_and_separate_conditions(self):
        java = os.environ.get('PROFILE_JAVA') or shutil.which('java')
        self.assertTrue(java, 'JDK17+ is required for production comparison controls')
        inputs = [*SOURCES, Path(__file__)]
        before = {str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest() for p in inputs}
        runs = []
        for runtime, jar in dependencies().items():
            with tempfile.TemporaryDirectory(prefix='fingerprint-comparison-host-') as classes:
                compiled = subprocess.run([java, '-m', 'jdk.compiler/com.sun.tools.javac.Main', '--release', '8',
                                           '-encoding', 'UTF-8', '-cp', str(jar), '-d', classes, *map(str, SOURCES)],
                                          capture_output=True, text=True, timeout=40)
                self.assertEqual(compiled.returncode, 0, compiled.stdout + compiled.stderr)
                run = subprocess.run([java, '-cp', classes + os.pathsep + str(jar),
                                      'local.pocketchat.FingerprintReportComparisonHost'],
                                     capture_output=True, text=True, timeout=20)
                self.assertEqual(run.returncode, 0, run.stdout + run.stderr)
                report = json.loads(run.stdout)
                self.assertEqual(report['status'], 'passed')
                self.assertEqual(report['total'], 108)
                self.assertEqual(report['total'], report['passed'])
                self.assertEqual(report['total'], len(report['checks']))
                self.assertEqual(report['total'], len({row['name'] for row in report['checks']}))
                self.assertTrue(all(row['pass'] is True for row in report['checks']))
                for field in ('actualAndroidExecution', 'actualGeckoExecution', 'physicalPhoneAcceptance',
                              'protectionEffectivenessAcceptance'):
                    self.assertIs(report[field], False)
                runs.append(dict(runtime=runtime, jsonSha256=hashlib.sha256(jar.read_bytes()).hexdigest(),
                                 compileStdout=compiled.stdout, compileStderr=compiled.stderr,
                                 runtimeStdout=run.stdout, runtimeStderr=run.stderr, report=report))
        self.assertEqual(before, {str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest() for p in inputs})
        receipt = dict(schema=1, status='passed', actualAndroidExecution=False, actualGeckoExecution=False,
                       physicalPhoneAcceptance=False, protectionEffectivenessAcceptance=False,
                       executionInputsUnchanged=True, sourceSha256=before, runs=runs,
                       scope='Production Java local two-report comparison; live document currentness, encrypted repository writes and actual manual compatibility actions are outside this host test')
        target = ROOT / 'work/fingerprint-comparison/comparison-host-results.json'
        target.parent.mkdir(parents=True, exist_ok=True)
        if target.exists():
            raw = target.read_bytes()
            archived = target.parent / 'executions' / (hashlib.sha256(raw).hexdigest() + '.json')
            archived.parent.mkdir(exist_ok=True)
            if archived.exists():
                self.assertEqual(archived.read_bytes(), raw)
            else:
                archived.write_bytes(raw)
        target.write_text(json.dumps(receipt, ensure_ascii=False, indent=2) + '\n')


if __name__ == '__main__':
    unittest.main()
