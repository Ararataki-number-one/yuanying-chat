"""Real production SitePermissions model on JDK17; no Android/Gecko execution.

The backend owns manually delivered callbacks and a controlled timer. Nothing
grants an OS permission, navigates a page, contacts a server, or mocks a JVM run.
"""
import os
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
MODEL = ROOT / 'app/src/main/java/local/pocketchat/SitePermissions.java'
HOST = ROOT / 'tests/site-permissions-host/SitePermissionsHost.java'
PINNED_JAVA = Path('/workspace/yuanying-chat/work/cloud-setup/jdk/usr/lib/jvm/java-17-openjdk-amd64/bin/java')


def java_command():
    candidates = []
    if os.environ.get('JAVA_HOME'):
        candidates.append(Path(os.environ['JAVA_HOME']) / 'bin/java')
    found = shutil.which('java')
    if found:
        candidates.append(Path(found))
    candidates.append(PINNED_JAVA)
    for candidate in candidates:
        if candidate.is_file() and os.access(candidate, os.X_OK):
            version = subprocess.run([str(candidate), '-version'], capture_output=True, text=True, timeout=15)
            if version.returncode == 0 and re.search(r'version "17(?:\.|["+])', version.stdout + version.stderr):
                return str(candidate)
    raise AssertionError('JDK17 is required to compile and execute the production permission model')


class SitePermissionsModelTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.java = java_command()
        cls.workspace = tempfile.TemporaryDirectory(prefix='site-permissions-production-host-')
        cls.addClassCleanup(cls.workspace.cleanup)
        cls.classes = Path(cls.workspace.name) / 'classes'
        cls.classes.mkdir()
        compiled = subprocess.run(
            [cls.java, '-m', 'jdk.compiler/com.sun.tools.javac.Main', '--release', '8',
             '-encoding', 'UTF-8', '-d', str(cls.classes), str(MODEL), str(HOST)],
            capture_output=True, text=True, timeout=45)
        if compiled.returncode:
            raise AssertionError('Actual production model compilation failed:\n' + compiled.stdout + compiled.stderr)

    def run_suite(self, suite, minimum):
        executed = subprocess.run(
            [self.java, '-cp', str(self.classes), 'local.pocketchat.SitePermissionsHost', suite],
            capture_output=True, text=True, timeout=20)
        self.assertEqual(executed.returncode, 0, executed.stdout + executed.stderr)
        matched = re.fullmatch(
            r'SITE_PERMISSIONS_HOST suite=' + re.escape(suite) + r' checks=(\d+) android=false gecko=false\n',
            executed.stdout)
        self.assertIsNotNone(matched, executed.stdout)
        self.assertGreaterEqual(int(matched.group(1)), minimum)

    def test_https_origin_and_port_boundaries(self):
        self.run_suite('origins', 19)

    def test_every_native_scope_field_and_null_empty_context(self):
        self.run_suite('scopes', 23)

    def test_exact_entries_third_party_and_safe_operation_matrix(self):
        self.run_suite('entries', 45)

    def test_actual_refresh_validation_and_readonly_snapshot(self):
        self.run_suite('refresh', 11)

    def test_fresh_native_object_required_and_concurrent_value_changes(self):
        self.run_suite('fresh-write', 20)

    def test_single_write_three_readbacks_and_default_only_absence(self):
        self.run_suite('readback', 19)

    def test_revisions_close_duplicate_callbacks_and_retry_cancellation(self):
        self.run_suite('revisions', 9)

    def test_before_and_after_write_timeouts_and_native_exceptions(self):
        self.run_suite('timeouts', 11)

    def test_document_env_and_same_session_reopen_retire_operations(self):
        self.run_suite('stale', 8)


if __name__ == '__main__':
    unittest.main()
