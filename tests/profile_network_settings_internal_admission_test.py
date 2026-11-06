"""Current internal fixture requires actual observer admission, without native claims."""
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
import unittest

import network_settings_callback_source_compatibility as compat

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = 'tests/gecko/NetworkSettingsInternalApplication.java'


class InternalAdmissionTests(unittest.TestCase):
    def test_current_fixture_and_production_idle_gate_with_both_json_libraries(self):
        java = os.environ.get('PROFILE_JAVA') or shutil.which('java')
        self.assertTrue(java, 'Mandatory current JDK is required')
        home = Path(java).resolve().parents[1]
        jars = [Path(os.environ.get('PROFILE_JSON_JAR', ROOT / 'work/profile-host/json.jar')),
                Path(os.environ.get('PROFILE_ANDROID_JSON_JAR', ROOT / 'work/profile-host/android-json.jar'))]
        for jar in jars:
            self.assertTrue(jar.is_file(), 'Mandatory real JSON implementation is required: ' + str(jar))
        with tempfile.TemporaryDirectory(prefix='internal-admission-controls-') as directory:
            for index, jar in enumerate(jars):
                output = Path(directory) / str(index) / 'results.json'
                args = [shutil.which('python3'), str(ROOT / 'tests/network-internal-admission-host/run.py'),
                        '--java-home', str(home), '--json-jar', str(jar), '--output', str(output)]
                result = subprocess.run(args, text=True, capture_output=True, timeout=45)
                self.assertEqual(result.returncode, 0, result.stderr[-5000:])
                report = json.loads(output.read_text())
                self.assertEqual(report['status'], 'passed')
                self.assertEqual(report['passed'], 26)
                self.assertTrue(all(row['pass'] is True for row in report['checks']))
                self.assertFalse(report['actualAndroidExecution'])
                self.assertFalse(report['actualGeckoExecution'])
                self.assertFalse(report['actualCoreVerification'])
                self.assertEqual(report['files'][FIXTURE], hashlib.sha256((ROOT / FIXTURE).read_bytes()).hexdigest())
                output.unlink()
                mutant = subprocess.run(args + ['--mutation', 'discard-fresh-guard'],
                                        text=True, capture_output=True, timeout=45)
                self.assertNotEqual(mutant.returncode, 0)
                self.assertFalse(output.exists(), 'A cached-idle mutant must not publish a positive receipt')
                self.assertIn('Fixture waits for the real callback despite all legacy busy flags being idle', mutant.stderr)

    def test_all_original_application_checks_and_wait_budgets_remain(self):
        current = (ROOT / FIXTURE).read_bytes()
        previous = compat.source_input(current, FIXTURE)
        calls = lambda raw: re.findall(rb'a\.check\([^;]+?\);', raw)
        self.assertEqual(calls(current), calls(previous))
        self.assertGreater(len(calls(current)), 10)
        for anchor in [b'Actual idle observation before saved internal change',
                       b'Actual internal provider completion',
                       b'Original internal ApplicationAttempt captured']:
            self.assertEqual(current.count(anchor), 1)
            self.assertEqual(previous.count(anchor), 1)
        for wait in [b'),15000);a.session.environmentIo.submit', b')),120000);', b'}),60000);']:
            self.assertIn(wait, current)
        self.assertNotIn(b'resolveChoice(', current)
        self.assertNotIn(b'"immediate"', current)

    def test_current_fixture_is_the_only_runtime_input_and_unknown_changes_rejected(self):
        current = (ROOT / FIXTURE).read_bytes()
        prior = compat.source_input(current, FIXTURE)
        self.assertEqual(hashlib.sha256(prior).hexdigest(), compat.BASE_SOURCES[FIXTURE])
        for needle in [b'currentIdleGuard(a.session,guard.getNow(null))',
                       b'a.session.requestTaskGuardStatus("internal-application-idle",guard::complete)',
                       b'"applicationAdmission",J.parse(admissionEvidence.toString())']:
            self.assertEqual(current.count(needle), 1)
            with self.assertRaises(ValueError):
                compat.source_input(current.replace(needle, needle + b' ', 1), FIXTURE)
        runner = (ROOT / 'tests/network-internal-admission-host/run.py').read_text()
        self.assertNotIn('compat.source_input', runner)
        self.assertIn('source = fixture.read_text()', runner)


if __name__ == '__main__':
    unittest.main(verbosity=2)
