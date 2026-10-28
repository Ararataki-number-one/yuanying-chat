"""Current configuration, native confirmation and document observation stay distinct."""
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
PINS = {'desktop': '3ea61b2a06e31edf1c91134fe9106b0ebb16628be169f3db75bc7a2b06b45796',
        'android-json': 'dfb7bae2f404cfe0b72b4d23944698cb716b7665171812a0a4d0f5926c0fac79'}


class EnvironmentIdentityStatusTest(unittest.TestCase):
    def test_current_ownership_native_receipts_and_document_boundaries(self):
        java = os.environ.get('PROFILE_JAVA') or shutil.which('java')
        self.assertTrue(java, 'JDK17+ required')
        sources = [PRODUCTION / name for name in ['J.java', 'EnvironmentSpec.java', 'BrowserIdentitySpec.java', 'EnvironmentIdentityStatus.java']]
        sources.append(ROOT / 'tests/environment-identity-status-host/EnvironmentIdentityStatusHost.java')
        before = {str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest() for p in [*sources, Path(__file__)]}
        jars = {'desktop': Path(os.environ.get('PROFILE_JSON_JAR', ROOT / 'work/profile-host/json.jar')),
                'android-json': Path(os.environ.get('PROFILE_ANDROID_JSON_JAR', ROOT / 'work/profile-host/android-json.jar'))}
        runs = []
        for runtime, jar in jars.items():
            self.assertTrue(jar.is_file(), 'Pinned JSON jar required: ' + str(jar))
            self.assertEqual(hashlib.sha256(jar.read_bytes()).hexdigest(), PINS[runtime])
            with tempfile.TemporaryDirectory(prefix='environment-identity-status-') as classes:
                built = subprocess.run([java, '-m', 'jdk.compiler/com.sun.tools.javac.Main', '--release', '8', '-encoding', 'UTF-8',
                                        '-cp', str(jar), '-d', classes, *map(str, sources)], capture_output=True, text=True, timeout=30)
                self.assertEqual(built.returncode, 0, built.stdout + built.stderr)
                result = subprocess.run([java, '-cp', classes + os.pathsep + str(jar), 'local.pocketchat.EnvironmentIdentityStatusHost'],
                                        capture_output=True, text=True, timeout=10)
                self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
                report = json.loads(result.stdout)
                self.assertEqual(report['status'], 'passed')
                self.assertGreaterEqual(report['passed'], 40)
                self.assertTrue(all(row['pass'] for row in report['checks']))
                self.assertIs(report['actualAndroidExecution'], False)
                self.assertIs(report['actualUiExecution'], False)
                runs.append(dict(runtime=runtime, report=report))
        self.assertEqual(before, {str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest() for p in [*sources, Path(__file__)]})
        output = ROOT / 'work/environment-identity-status/host-results.json'
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps(dict(status='passed', sourceSha256=before, runs=runs,
                                         actualAndroidExecution=False, actualUiExecution=False), ensure_ascii=False, indent=2) + '\n')


if __name__ == '__main__':
    unittest.main()
