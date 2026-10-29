"""Exercise actual SDK-boundary adapter logic over explicitly declared JVM doubles."""
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


class SitePermissionsAdapterTest(unittest.TestCase):
    def test_native_object_ownership_and_late_callbacks(self):
        java = os.environ.get('PROFILE_JAVA') or shutil.which('java')
        self.assertTrue(java, 'JDK17+ required')
        sources = [PRODUCTION / name for name in ['SitePermissions.java', 'GeckoSitePermissions.java']]
        sources += sorted((ROOT / 'tests/site-permissions-adapter-host').rglob('*.java'))
        before = {str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest() for p in [*sources, Path(__file__)]}
        with tempfile.TemporaryDirectory(prefix='site-permissions-adapter-') as classes:
            built = subprocess.run([java, '-m', 'jdk.compiler/com.sun.tools.javac.Main', '--release', '8', '-encoding', 'UTF-8',
                                    '-d', classes, *map(str, sources)], capture_output=True, text=True, timeout=30)
            self.assertEqual(built.returncode, 0, built.stdout + built.stderr)
            run = subprocess.run([java, '-cp', classes, 'local.pocketchat.GeckoSitePermissionsHost'], capture_output=True, text=True, timeout=10)
            self.assertEqual(run.returncode, 0, run.stdout + run.stderr)
            report = json.loads(run.stdout)
            self.assertEqual(report['status'], 'passed')
            self.assertGreaterEqual(report['checks'], 30)
            self.assertFalse(report['actualGeckoExecution'])
            self.assertFalse(report['actualAndroidExecution'])
        self.assertEqual(before, {str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest() for p in [*sources, Path(__file__)]})
        output = ROOT / 'work/site-permissions/adapter-host.json'
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps(dict(status='passed', sourceSha256=before, report=report, physicalPhoneAcceptance=False), indent=2) + '\n')


if __name__ == '__main__':
    unittest.main()
