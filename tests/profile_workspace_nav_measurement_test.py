"""Actual workspace sizing/centering methods with declared measurement boundaries.

Host checks cover growth, equal columns, padding feedback and reflow. Native
Android compile checks API use; actual glyph/clipping evidence remains the
unchanged-purpose NavigationTypographyEvidence device fixture.
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
PRODUCTION = ROOT / 'app/src/main/java/local/pocketchat/ReferenceUi.java'
SPEC = importlib.util.spec_from_file_location('workspace_nav_members', ROOT / 'tests/default-environment-host/run.py')
MEMBERS = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MEMBERS)


class WorkspaceNavMeasurement(unittest.TestCase):
    def test_native_measurement_drives_height_and_stabilizes_after_centering(self):
        raw = PRODUCTION.read_bytes()
        source = raw.decode()
        bar = MEMBERS.member(source, 'private static final class WorkspaceNavBar')
        center = MEMBERS.member(source, 'private static void centerDockContents(')
        java = Path(os.environ.get('PROFILE_JAVA') or shutil.which('java') or '')
        fixture = (ROOT / 'tests/workspace-nav-host/WorkspaceNavLayoutHost.java.in').read_text()
        fixture = fixture.replace('/* PRODUCTION_BAR */', bar).replace('/* PRODUCTION_CENTER */', center)
        with tempfile.TemporaryDirectory(prefix='workspace-nav-measurement-') as directory:
            base = Path(directory)
            host = base / 'WorkspaceNavLayoutHost.java'
            host.write_text(fixture)
            result = subprocess.run([str(java), '-m', 'jdk.compiler/com.sun.tools.javac.Main', '-encoding', 'UTF-8', '-d', str(base), str(host)], capture_output=True, text=True, timeout=30)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            result = subprocess.run([str(java), '-cp', str(base), 'local.pocketchat.WorkspaceNavLayoutHost'], capture_output=True, text=True, timeout=15)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            report = json.loads(result.stdout)
            self.assertGreaterEqual(report['passed'], 75)
            self.assertFalse(report['actualAndroidExecution'])
            android = Path(os.environ.get('PROFILE_ANDROID_JAR', '/tmp/pocketchat-shared-tools/android-35/android.jar'))
            self.assertTrue(android.is_file(), 'Pinned Android 35 API required for native measure compilation')
            self.assertEqual(hashlib.sha256(android.read_bytes()).hexdigest(), '4566663c3876e022b4fa4ced8c8697c4ab1688267f090114fd92d027b32e619b')
            native = base / 'WorkspaceNavNative.java'
            native.write_text('package local.pocketchat;import android.content.Context;import android.view.View;import android.widget.LinearLayout;'
                              'class WorkspaceNavNative {static int dp(Context c,int value){return value;}'+bar+'}'
                              'class GlassDock extends LinearLayout {GlassDock(Context c){super(c);}}')
            result = subprocess.run([str(java), '-m', 'jdk.compiler/com.sun.tools.javac.Main', '-encoding', 'UTF-8', '-cp', str(android), '-d', str(base/'native'), str(native)], capture_output=True, text=True, timeout=30)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(PRODUCTION.read_bytes(), raw, 'Production changed during verification')
        report.update(status='passed', scope=__doc__.strip(), nativeAndroidApiCompilation=True,
                      sourceSha256=hashlib.sha256(raw).hexdigest(), androidJarSha256=hashlib.sha256(android.read_bytes()).hexdigest())
        if os.environ.get('WORKSPACE_NAV_REPORT'):
            Path(os.environ['WORKSPACE_NAV_REPORT']).write_text(json.dumps(report, indent=2)+'\n')


if __name__ == '__main__':
    unittest.main(verbosity=2)
