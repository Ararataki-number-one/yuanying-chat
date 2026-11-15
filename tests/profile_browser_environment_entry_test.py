"""Production browser entry identity/dispatch methods on declared UI boundaries.

The host executes the real Intent creation, nonce/identity/expiry validation,
direct-vs-details branch, ownership check and transient dismissal. Android View,
dialog and preference storage are controlled boundaries; no rendered UI or
browser engine execution is claimed.
"""
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
PROD = ROOT / 'app/src/main/java/local/pocketchat'
SPEC = importlib.util.spec_from_file_location('browser_entry_members', ROOT / 'tests/default-environment-host/run.py')
MEMBERS = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MEMBERS)


class BrowserEnvironmentEntry(unittest.TestCase):
    def test_direct_entry_retains_identity_and_live_document(self):
        java = Path(os.environ.get('PROFILE_JAVA') or shutil.which('java') or '')
        jar = next((Path(p) for p in (os.environ.get('PROFILE_JSON_JAR'),
                   ROOT / 'work/profile-host/json.jar', ROOT / 'work/profile-host/android-json.jar')
                   if p and Path(p).is_file()), None)
        self.assertIsNotNone(jar, 'Source-pinned JSON runtime is required')
        self.assertIn(hashlib.sha256(jar.read_bytes()).hexdigest(), {
            '3ea61b2a06e31edf1c91134fe9106b0ebb16628be169f3db75bc7a2b06b45796',
            'dfb7bae2f404cfe0b72b4d23944698cb716b7665171812a0a4d0f5926c0fac79'})
        source = (PROD / 'EnvironmentOverviewUi.java').read_text()
        methods = MEMBERS.opening_helpers(source) + '\n' + '\n'.join(
            MEMBERS.member(source, signature) for signature in (
                'boolean consume(', 'boolean current(', 'void browserReady('))
        fixture = (ROOT / 'tests/browser-entry-host/BrowserEntryHost.java.in').read_text().replace('/* PRODUCTION_METHODS */', methods)
        with tempfile.TemporaryDirectory(prefix='browser-entry-host-') as folder:
            folder = Path(folder)
            (folder / 'BrowserEntryHost.java').write_text(fixture)
            (folder / 'TextUtils.java').write_text('package android.text;public class TextUtils{public static String join(String delimiter,Iterable<String> values){return String.join(delimiter,values);}}')
            (folder / 'Build.java').write_text('package android.os;public class Build{public static class VERSION{public static int SDK_INT=35;}}')
            for name in ('EnvironmentOverviewState.java', 'BrowserStartupGate.java'):
                (folder / name).write_bytes((PROD / name).read_bytes())
            result = subprocess.run([str(java), '-m', 'jdk.compiler/com.sun.tools.javac.Main', '-encoding', 'UTF-8', '-cp', str(jar), '-d', str(folder), *map(str, folder.glob('*.java'))], text=True, capture_output=True, timeout=40)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            result = subprocess.run([str(java), '-cp', str(folder)+os.pathsep+str(jar), 'local.pocketchat.BrowserEntryHost'], text=True, capture_output=True, timeout=20)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            report = json.loads(result.stdout)
            self.assertGreaterEqual(report['passed'], 30)
            self.assertFalse(report['actualAndroidExecution'])
            report.update(status='passed', scope=__doc__.strip(), sourceSha256={name: hashlib.sha256((PROD/name).read_bytes()).hexdigest() for name in ('EnvironmentOverviewUi.java', 'EnvironmentOverviewState.java', 'BrowserStartupGate.java')})
            if os.environ.get('BROWSER_ENTRY_REPORT'):
                Path(os.environ['BROWSER_ENTRY_REPORT']).write_text(json.dumps(report, indent=2)+'\n')


if __name__ == '__main__':
    unittest.main(verbosity=2)
