"""Authoritative document commits retire native requests; controlled SDK adapters."""
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest
from page_bridge42_source_compatibility import DELTAS, PREVIOUS_SHA256, bridge42_preservation_bytes

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / 'app/src/main/java/local/pocketchat'
HERE = ROOT / 'tests/page-bridge-lifecycle-host'
spec = importlib.util.spec_from_file_location('page_bridge_source_members', ROOT / 'tests/page-recovery-host/run.py')
extract = importlib.util.module_from_spec(spec)
spec.loader.exec_module(extract)


def execute(view=None):
    java = os.environ.get('PROFILE_JAVA') or shutil.which('java')
    if not java:
        raise AssertionError('Java 17 required')
    jar = next((Path(p) for p in (os.environ.get('PROFILE_JSON_JAR', ''), str(ROOT / 'work/profile-host/json.jar')) if p and Path(p).is_file()), None)
    if jar is None:
        raise AssertionError('Existing host JSON dependency required')
    raw = view if view is not None else (SOURCE / 'GeckoWebView.java').read_text()
    selected = {
        'PAGE_MESSAGES': 'final WebExtension.MessageDelegate pageMessages=',
        'APPEARANCE_COMMITTED': 'private void appearanceCommitted(',
        'APPEARANCE_READY': 'private void appearanceReady(',
        'EVALUATE': 'public void evaluateJavascript(',
        'AUDIT': 'void runEnvironmentAudit(',
        'LOCATION': '@Override public void onLocationChange(',
    }
    members = {key: extract.member(raw, needle) for key, needle in selected.items()}
    fixture = (HERE / 'PageBridgeLifecycleHost.java.in').read_text()
    for key, value in members.items():
        marker = '/* ' + key + ' */'
        if fixture.count(marker) != 1:
            raise AssertionError('Unique production member marker required')
        fixture = fixture.replace(marker, value, 1)
    files = [SOURCE / 'GeckoWebView.java', SOURCE / 'BrowserBridgeRequests.java', HERE / 'PageBridgeLifecycleHost.java.in', Path(__file__), ROOT / 'tests/page-recovery-host/run.py']
    hashes = {str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest() for p in files}
    with tempfile.TemporaryDirectory(prefix='page-bridge-lifecycle-') as temp:
        out = Path(temp)
        host = out / 'PageBridgeLifecycleHost.java'
        host.write_text(fixture)
        compiled = subprocess.run([java, '-m', 'jdk.compiler/com.sun.tools.javac.Main', '-encoding', 'UTF-8', '-cp', str(jar), '-d', str(out), str(host), str(SOURCE / 'BrowserBridgeRequests.java')], capture_output=True, text=True, timeout=40)
        if compiled.returncode:
            raise AssertionError(compiled.stdout + compiled.stderr)
        ran = subprocess.run([java, '-cp', str(out) + os.pathsep + str(jar), 'local.pocketchat.PageBridgeLifecycleHost'], capture_output=True, text=True, timeout=30)
        if ran.returncode:
            raise AssertionError(ran.stdout + ran.stderr)
        report = json.loads(ran.stdout)
        report.update(sourceCommit=subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip(), sourceFiles=hashes, executedViewSha256=hashlib.sha256(raw.encode()).hexdigest(), injectedCounterexample=view is not None, selectedMembersSha256={k: hashlib.sha256(v.encode()).hexdigest() for k, v in members.items()}, executionInputsUnchanged=all(hashlib.sha256((ROOT / k).read_bytes()).hexdigest() == v for k, v in hashes.items()), actualAndroidExecution=False, actualGeckoExecution=False, actualPhoneExecution=False, scope='Exact production bridge, authoritative location callback and request lifecycle with controlled SDK port/session and Android owner boundaries; not actual Gecko event ordering or malicious-page reachability proof.')
        return report


class PageBridgeLifecycleTests(unittest.TestCase):
    def test_authoritative_commit_and_other_document_orderings(self):
        report = execute()
        output = Path(os.environ.get('PAGE_BRIDGE_LIFECYCLE_REPORT') or ROOT / 'work/profile-host/page-bridge-lifecycle-results.json')
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps(report, indent=2) + '\n')
        self.assertEqual(report['status'], 'passed', json.dumps(report['checks'], indent=2))
        self.assertEqual(report['passed'], report['total'])
        self.assertEqual(report['total'], 32)
        self.assertTrue(report['executionInputsUnchanged'])

    def test_old_commit_gap_and_individual_protections_are_observed(self):
        raw = (SOURCE / 'GeckoWebView.java').read_bytes()
        previous = bridge42_preservation_bytes(raw)
        self.assertEqual(hashlib.sha256(previous).hexdigest(), PREVIOUS_SHA256)
        old = execute(previous.decode())
        self.assertEqual(old['status'], 'failed')
        self.assertEqual((old['passed'], old['total']), (21, 32))
        outcomes = []
        for index, (before, after) in enumerate(DELTAS):
            with self.subTest(protection=index):
                self.assertEqual(raw.count(after), 1)
                result = execute(raw.replace(after, before, 1).decode())
                self.assertEqual(result['status'], 'failed')
                self.assertTrue(result['injectedCounterexample'])
                outcomes.append(result)
        output = os.environ.get('PAGE_BRIDGE_LIFECYCLE_NEGATIVE_REPORT')
        if output:
            Path(output).write_text(json.dumps({'previous': old, 'individualCounterexamples': outcomes}, indent=2) + '\n')

    def test_exact_inverse_preserves_original_reading_guard(self):
        raw = (SOURCE / 'GeckoWebView.java').read_bytes()
        from fingerprint_source_compatibility import reading_preservation_bytes, BASELINE
        self.assertEqual(hashlib.sha256(reading_preservation_bytes(raw)).hexdigest(), BASELINE)
        self.assertEqual(hashlib.sha256(reading_preservation_bytes(bridge42_preservation_bytes(raw))).hexdigest(), BASELINE)
        geometry = b'Math.abs(next-readingLayout)<.001f'
        self.assertEqual(raw.count(geometry), 1)
        with self.assertRaises(ValueError):
            reading_preservation_bytes(raw.replace(geometry, b'Math.abs(next-readingLayout)<.002f', 1))
        for previous, current in DELTAS:
            with self.subTest(partial=current[:40]):
                with self.assertRaises(ValueError):
                    reading_preservation_bytes(raw.replace(current, previous, 1))


if __name__ == '__main__':
    unittest.main()
