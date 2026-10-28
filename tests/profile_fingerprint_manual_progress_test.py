"""2.0.28 manual checklist projection over both pinned production JSON runtimes."""
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

from profile_fingerprint_report_comparison_test import SOURCES, dependencies

ROOT = Path(__file__).resolve().parents[1]
HOST = ROOT / 'tests/fingerprint-manual-progress-host/FingerprintManualProgressHost.java'


class FingerprintManualProgressTest(unittest.TestCase):
    def test_owned_manual_progress_counts_states_timestamps_and_reset(self):
        java = os.environ.get('PROFILE_JAVA') or shutil.which('java')
        self.assertTrue(java, 'JDK17+ is required for production manual-progress controls')
        sources = [*SOURCES, HOST]
        inputs = [*sources, Path(__file__),
                  ROOT / 'tests/profile_fingerprint_report_comparison_test.py']
        before = {str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest() for p in inputs}
        runs = []
        for runtime, jar in dependencies().items():
            with tempfile.TemporaryDirectory(prefix='fingerprint-manual-progress-') as classes:
                compiled = subprocess.run([java, '-m', 'jdk.compiler/com.sun.tools.javac.Main',
                                           '--release', '8', '-encoding', 'UTF-8', '-cp', str(jar),
                                           '-d', classes, *map(str, sources)], capture_output=True,
                                          text=True, timeout=40)
                self.assertEqual(compiled.returncode, 0, compiled.stdout + compiled.stderr)
                run = subprocess.run([java, '-cp', classes + os.pathsep + str(jar),
                                      'local.pocketchat.FingerprintManualProgressHost'],
                                     capture_output=True, text=True, timeout=20)
                self.assertEqual(run.returncode, 0, run.stdout + run.stderr)
                report = json.loads(run.stdout)
                self.assertEqual(report['status'], 'passed')
                self.assertEqual(report['versionScope'], '2.0.28-only')
                self.assertGreaterEqual(report['total'], 40)
                self.assertEqual(report['passed'], report['total'])
                self.assertEqual(report['total'], len(report['checks']))
                self.assertEqual(report['total'], len({item['name'] for item in report['checks']}))
                self.assertTrue(all(item['pass'] is True for item in report['checks']))
                for field in ('actualAndroidExecution', 'actualGeckoExecution', 'physicalPhoneAcceptance',
                              'protectionEffectivenessAcceptance'):
                    self.assertIs(report[field], False)
                runs.append(dict(runtime=runtime, jsonSha256=hashlib.sha256(jar.read_bytes()).hexdigest(),
                                 compileStdout=compiled.stdout, compileStderr=compiled.stderr,
                                 runtimeStdout=run.stdout, runtimeStderr=run.stderr, report=report))
        self.assertEqual(before, {str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest() for p in inputs})
        receipt = dict(schema=1, status='passed', versionScope='2.0.28-only', sourceSha256=before,
                       executionInputsUnchanged=True, runs=runs, actualAndroidExecution=False,
                       actualGeckoExecution=False, physicalPhoneAcceptance=False,
                       protectionEffectivenessAcceptance=False,
                       scope='Only production 2.0.28 manual checklist projection; no 2.0.29 reference overview, Android UI execution, encryption or real manual-action acceptance')
        target = ROOT / 'work/preflight-tests/manual-progress-host-results.json'
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
