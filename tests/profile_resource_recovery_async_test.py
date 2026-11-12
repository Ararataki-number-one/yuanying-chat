"""Actual production retry and fixture startup continuation; no native execution claim."""
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]


class ResourceRecoveryAsync(unittest.TestCase):
    def test_exact_methods_with_dual_json_and_synchronous_assumption_counterfeits(self):
        java = os.environ.get('PROFILE_JAVA') or shutil.which('java')
        self.assertTrue(java, 'Existing mandatory JDK required')
        home = Path(java).resolve().parents[1]
        jars = [Path(os.environ.get('PROFILE_JSON_JAR', ROOT/'work/profile-host/json.jar')),
                Path(os.environ.get('PROFILE_ANDROID_JSON_JAR', ROOT/'work/profile-host/android-json.jar'))]
        with tempfile.TemporaryDirectory(prefix='resource-recovery-controls-') as temporary:
            for index, jar in enumerate(jars):
                self.assertTrue(jar.is_file(), 'Both real JSON implementations are mandatory')
                output = Path(temporary)/str(index)/'results.json'
                cmd = [shutil.which('python3'), str(ROOT/'tests/resource-recovery-host/run.py'),
                       '--java-home', str(home), '--json-jar', str(jar), '--output', str(output)]
                run = subprocess.run(cmd, text=True, capture_output=True, timeout=45)
                self.assertEqual(run.returncode, 0, run.stderr[-4000:])
                report = json.loads(output.read_text())
                self.assertEqual(report['status'], 'passed')
                self.assertEqual(report['originalChecks'], 34)
                self.assertEqual(report['passed'], 40)
                self.assertTrue(all(row['pass'] is True for row in report['checks']))
                self.assertFalse(report['actualAndroidExecution'])
                self.assertFalse(report['actualGeckoExecution'])
                self.assertFalse(report['actualNativeStartup'])
                for name, expected in [('sync-runtime-only', 'Asynchronous admitted recovery renews original navigation deadline'),
                                       ('pretend-allocation-ready', 'Durable user recovery outranks synthetic low memory'),
                                       ('obsolete-navigation-owner', 'Superseded resource retry cannot wake an older navigation')]:
                    output.unlink(missing_ok=True)
                    mutant = subprocess.run(cmd+['--mutation', name], text=True, capture_output=True, timeout=45)
                    self.assertNotEqual(mutant.returncode, 0)
                    self.assertFalse(output.exists(), 'Counterfeit must not publish a positive report')
                    self.assertIn(expected, mutant.stderr)

    def test_all_original_resource_assertions_and_absolute_startup_budget_remain(self):
        raw = (ROOT/'tests/gecko/ResourcePressureIntegrationActivity.java').read_bytes()
        calls = re.findall(rb'resourceCheck\("[^;]+?\);', raw)
        self.assertEqual(len(calls), 42)
        self.assertEqual(hashlib.sha256(b'\n'.join(calls)).hexdigest(),
                         'aa59f223095d298144fb972ba73e279688e5cb4494e5826e469c9b98ba8295e6')
        parent = (ROOT/'tests/gecko/GeckoIdentityPrototypeIntegrationActivity.java').read_text()
        guard = 'handler.postDelayed(()->{if(!finished&&caseIndex<0)finish(new IOException("Official Gecko startup did not become ready"));},60000);'
        self.assertEqual(parent.count(guard), 1)
        self.assertNotIn(b'60000', raw)
        self.assertIn(b'if(finished)return;', raw)
        self.assertIn(b'if(owner.deleted||view.destroyed||view.failed)', raw)
        self.assertIn(b'if(!recoveryAllocationComplete){resourceReadyForControls=true;return;}', raw)

    def test_original_cpu_and_tls_startup_guards_remain(self):
        path = ROOT/'tests/resource-recovery-host/run.py'
        spec = importlib.util.spec_from_file_location('current_resource_recovery_extraction', path)
        runner = importlib.util.module_from_spec(spec); spec.loader.exec_module(runner)
        source = (ROOT/'app/src/main/java/local/pocketchat/GeckoWebView.java').read_text()
        # The retry now also fences synchronous navigation reentry. Its actual
        # behavior and former synchronous-only admission run above; a historical
        # whole-member hash would reject this intentional maintenance change.
        initializer = runner.member(source, 'private void initialize()')
        for guard in ['if(!enabled||destroyed||owner.deleted||runtime!=null||failed)return;',
                      'owner.cpu.prepareStartup(', 'owner.tls.prepareStartup(',
                      'if(!owner.tls.claimRuntime(tlsBoot))', 'if(!owner.cpu.claimRuntime(cpuBoot))']:
            self.assertIn(guard, initializer)
        self.assertLess(initializer.index('owner.cpu.prepareStartup('), initializer.index('GeckoRuntime.create('))
        self.assertLess(initializer.index('owner.tls.prepareStartup('), initializer.index('GeckoRuntime.create('))


if __name__ == '__main__':
    unittest.main(verbosity=2)
