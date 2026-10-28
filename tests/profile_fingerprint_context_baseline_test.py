"""Per-context pinned observations on both supported JVM JSON implementations."""
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
    'FingerprintContextBaselines.java', 'FingerprintDeepBaseline.java',
    'FingerprintObservationHistory.java', 'AuditReport.java', 'J.java')]
SOURCES += [ROOT / 'tests/browser-runtime/fingerprint-report-stubs/BrowserNetworkGuard.java',
            ROOT / 'tests/fingerprint-baseline-host/FingerprintDeepBaselineHost.java',
            ROOT / 'tests/fingerprint-context-baseline-host/FingerprintContextBaselinesHost.java']
PINS = {'desktop': '3ea61b2a06e31edf1c91134fe9106b0ebb16628be169f3db75bc7a2b06b45796',
        'android-json': 'dfb7bae2f404cfe0b72b4d23944698cb716b7665171812a0a4d0f5926c0fac79'}
COUNT = 90
FIXTURE = ROOT / 'tests/fingerprint-context-baseline-host/actual-gecko-cross-origin-report-v1.json'
CAPTURE = ROOT / 'tests/fingerprint-context-baseline-host/actual-gecko-cross-origin-report-v1.capture.json'
FIXTURE_SHA256 = '2f984963d6fcea5b425be676900772cc4a46991167fee23c9aa37338c56c8058'


def dependencies():
    paths = {'desktop': os.environ.get('PROFILE_JSON_JAR', str(ROOT / 'work/profile-host/json.jar')),
             'android-json': os.environ.get('PROFILE_ANDROID_JSON_JAR', str(ROOT / 'work/profile-host/android-json.jar'))}
    result = {}
    for runtime, value in paths.items():
        path = Path(value)
        if not path.is_file():
            raise AssertionError('Both pinned JSON runtimes are required for context baseline controls: ' + runtime)
        if hashlib.sha256(path.read_bytes()).hexdigest() != PINS[runtime]:
            raise AssertionError('Unexpected context baseline JSON dependency digest: ' + runtime)
        result[runtime] = path
    return result


class FingerprintContextBaselineTest(unittest.TestCase):
    def test_owned_independent_contexts_and_same_context_comparison(self):
        local = Path('/workspace/yuanying-chat/work/cloud-setup/jdk/usr/lib/jvm/java-17-openjdk-amd64/bin/java')
        java = os.environ.get('PROFILE_JAVA') or (str(local) if local.is_file() else shutil.which('java'))
        self.assertTrue(java, 'JDK17+ is required for context baseline controls')
        inputs = [*SOURCES, FIXTURE, CAPTURE, Path(__file__)]
        before = {str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest() for p in inputs}
        self.assertEqual(before[str(FIXTURE.relative_to(ROOT))], FIXTURE_SHA256)
        capture = json.loads(CAPTURE.read_bytes())
        self.assertEqual(capture['sourceCommit'], '092ffbbaf79badb00b418fa7987c8b2d4ad44ade')
        self.assertEqual(capture['runId'], '40514997310')
        self.assertEqual(capture['runAttempt'], '1')
        self.assertEqual(capture['parentZipSha256'], '9b889f6943ffc5c7238b75f0a88e3e3f7e3d5ccd6cef88d38b336b6af33d1310')
        self.assertEqual(capture['parentMemberSha256'], '43ee69f393977c65b2aa0bc9ccf35b26d2837fefc6b632175c6436d2d6990d3e')
        self.assertEqual(capture['selectedSha256'], FIXTURE_SHA256)
        self.assertEqual(capture['selectedBytes'], FIXTURE.stat().st_size)
        self.assertIs(capture['originalCaptureActualAndroidExecution'], True)
        self.assertIs(capture['originalCaptureActualGeckoExecution'], True)
        self.assertIs(capture['originalCapturePhysicalPhoneAcceptance'], False)
        self.assertIs(capture['newActualAndroidExecution'], False)
        self.assertIs(capture['newActualGeckoExecution'], False)
        runs = []
        for runtime, jar in dependencies().items():
            with tempfile.TemporaryDirectory(prefix='fingerprint-context-baseline-') as classes:
                compiled = subprocess.run([java, '-m', 'jdk.compiler/com.sun.tools.javac.Main', '--release', '8',
                                           '-encoding', 'UTF-8', '-cp', str(jar), '-d', classes, *map(str, SOURCES)],
                                          capture_output=True, text=True, timeout=30)
                self.assertEqual(compiled.returncode, 0, compiled.stdout + compiled.stderr)
                run = subprocess.run([java, '-cp', classes + os.pathsep + str(jar),
                                      'local.pocketchat.FingerprintContextBaselinesHost', str(FIXTURE)],
                                     capture_output=True, text=True, timeout=15)
                self.assertEqual(run.returncode, 0, run.stdout + run.stderr)
                report = json.loads(run.stdout)
                self.assertEqual(report['status'], 'passed')
                self.assertEqual(report['total'], COUNT)
                self.assertEqual(report['passed'], COUNT)
                self.assertEqual(len(report['checks']), COUNT)
                self.assertTrue(all(x['pass'] is True for x in report['checks']))
                for field in ('actualAndroidExecution', 'actualGeckoExecution', 'actualChromiumExecution',
                              'protectionEffectivenessAcceptance'):
                    self.assertIs(report[field], False)
                self.assertIs(report['usesPreviouslyCapturedActualGeckoInput'], True)
                runs.append(dict(runtime=runtime, jsonSha256=hashlib.sha256(jar.read_bytes()).hexdigest(),
                                 compilerRelease=8, compileStdout=compiled.stdout, compileStderr=compiled.stderr,
                                 runtimeStdout=run.stdout, runtimeStderr=run.stderr, report=report))
        self.assertEqual(before, {str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest() for p in inputs})
        receipt = dict(schema=1, status='passed', actualAndroidExecution=False, actualGeckoExecution=False,
                       actualChromiumExecution=False, protectionEffectivenessAcceptance=False,
                       usesPreviouslyCapturedActualGeckoInput=True, capture=capture,
                       executionInputsUnchanged=True, sourceSha256=before, runs=runs,
                       scope='Production pure-Java per-context reference ownership and comparison on pinned JSON jars; host-constructed observations plus an exact prior AVD Gecko report, caller live-document validation and encrypted persistence are outside this model test')
        target = ROOT / 'work/coverage-context-baseline/context-baseline-host-results.json'
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
