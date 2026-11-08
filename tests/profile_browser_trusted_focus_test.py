"""Original unfocused target regression and synthetic controller/JVM controls.

No host model establishes Android input delivery or DocumentsUI acceptance.
The actual workload still needs its original single taps, two real chooser
cancellations, download roundtrip and separate engine tasks.
"""
import ast
import copy
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tests'))
SPEC = importlib.util.spec_from_file_location('focused_browser_controller',
    ROOT / 'tools/browser/run_integration.py')
controller = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(controller)
import browser_targeting_test as legacy

FIXTURE = ROOT / 'tests/fixtures/browser-focused-target-06.json'
FIXTURE_SHA = 'f114ddefa1eca848ddedf8b4d5d8f6cbbf2523502bca79abd1933539b3448431'
OLD_VALIDATOR_SHA = 'e5d1027ff12d4f192c0921d1c1c3e73da0ed43c47d08acd3447721634d73d20b'
OLD_JAVA_HELPER_SHAS = {'nativeTargetReady': 'd5f0e35f904ff144ab7e1d09b6ebbebf115e1dc0528a31d5277acad03b5ee5c7',
    'sameNativeTarget': 'c8f0b456fbc725096c0df45a24143c3617d3f68feb364807ed651aa3f711a4d5', 'sameDomTarget': 'b726aea328916eb2bdd3ee36ceecb55e2759a4d4f8b5b8682621dfe53a1d7e30',
    'nativeVisualTargetReady': 'cc6f1c9266385c0458fa417b62898b9693c14b6b93e973f73b21cf001a09c4f0'}
OLD_HTML_SHA = 'a4333f0f343f320d6b75c3f68219689cb59c169386a380573714eeac780be827'


def fixture():
    raw = FIXTURE.read_bytes()
    if hashlib.sha256(raw).hexdigest() != FIXTURE_SHA:
        raise AssertionError('Original reduced target packet changed')
    return json.loads(raw)


def focused():
    """An explicit host mutation, never a new device focus observation."""
    value = fixture()['current']
    value['tapTarget']['nativeFrame']['viewFocus'] = True
    value['tapTarget']['dom']['documentFocus'] = True
    return value


def java_method(source, name):
    match = re.search(r'^  static boolean ' + name + r'\(', source, re.M)
    if match is None:
        raise AssertionError('Missing actual Java readiness method: ' + name)
    opened = source.index('{', match.start())
    depth, end = 1, opened + 1
    while depth:
        depth += (source[end] == '{') - (source[end] == '}')
        end += 1
    return source[match.start():end]


class BrowserTrustedFocusTest(unittest.TestCase):
    def test_original_ready_packet_lacks_focus_and_cannot_authorize_input(self):
        data = fixture()
        self.assertEqual((data['origin']['sourceCommit'], data['origin']['runId'], data['origin']['jobId']),
            ('06a802663075664b75aa9d19184d9c02b6bab7c9', '42492356825', '128777268063'))
        current = data['current']
        self.assertEqual(controller.validate_tap_target(current), (160, 390))
        self.assertIs(current['tapTarget']['nativeFrame']['viewFocus'], False)
        self.assertIs(current['tapTarget']['dom']['documentFocus'], False)
        self.assertEqual(current['nativeInputEvents'], [])
        self.assertEqual(current['pickerBarrier']['events'], [])
        with self.assertRaisesRegex(AssertionError, 'do not both have focus'):
            controller.validate_focused_tap_target(current)

    def test_explicit_focused_host_packets_preserve_the_original_transform(self):
        for stage in ('file-picker-1', 'file-picker-2', 'download-click'):
            current = focused()
            current['stage'] = stage
            identifier = 'download' if stage == 'download-click' else 'upload'
            current['tapTarget']['id'] = current['tapTarget']['dom']['id'] = identifier
            before = copy.deepcopy(current)
            self.assertEqual(controller.validate_focused_tap_target(current), (160, 390))
            self.assertEqual(current, before)

    def test_missing_false_or_wrongly_typed_focus_is_rejected(self):
        for section, key in (('nativeFrame', 'viewFocus'), ('dom', 'documentFocus')):
            for bad in (False, None, 0, 1, 'true', []):
                with self.subTest(section=section, bad=repr(bad)):
                    current = focused()
                    current['tapTarget'][section][key] = bad
                    before = copy.deepcopy(current)
                    with self.assertRaises(AssertionError):
                        controller.validate_focused_tap_target(current)
                    self.assertEqual(current, before)
            current = focused()
            del current['tapTarget'][section][key]
            with self.assertRaises(AssertionError):
                controller.validate_focused_tap_target(current)

    def test_focus_cannot_bypass_existing_geometry_or_foreground_guards(self):
        for section, key, bad in (('nativeFrame', 'shown', False),
                ('nativeFrame', 'windowFocus', False), ('nativeFrame', 'foreground', False),
                ('nativeFrame', 'layoutRequested', True), ('nativeFrame', 'nativeScale', .5),
                ('dom', 'hitTarget', False), ('dom', 'visualOffsetTop', 0)):
            current = focused()
            current['tapTarget'][section][key] = bad
            with self.subTest(key=key), self.assertRaises(AssertionError):
                controller.validate_focused_tap_target(current)

    def test_actual_controller_rejects_bad_focus_before_any_single_tap(self):
        host = legacy.BrowserTargetingTests()
        for section, key in (('nativeFrame', 'viewFocus'), ('dom', 'documentFocus')):
            value = host.current()
            value['tapTarget'][section][key] = False
            with mock.patch.object(host, 'current', return_value=value):
                failure, report, diagnostic, calls = host.run_controller_failure(True)
            self.assertIn('do not both have focus', failure)
            self.assertEqual(report['actualAndroidTaps'], 0)
            self.assertFalse(report['actualAndroidExecution'])
            self.assertFalse(any(row[:3] == ['shell', 'input', 'tap'] for row in calls))
            self.assertFalse(any(row == ['shell', 'dumpsys', 'window', 'windows'] for row in calls))

    def test_actual_window_observation_preserves_raw_bytes_without_input(self):
        stdout = b'mCurrentFocus=Window{synthetic current input owner}\n  synthetic overlay\n'
        stderr = b'synthetic stderr retained\n'
        calls = []
        def adb(*parts, **kwargs):
            calls.append((parts, kwargs))
            return subprocess.CompletedProcess(parts, 0, stdout=stdout, stderr=stderr)
        with tempfile.TemporaryDirectory() as directory:
            value = controller.capture_tap_window(adb, Path(directory), focused())
            self.assertEqual((Path(directory) / value['file']).read_bytes(), stdout)
            self.assertEqual((Path(directory) / value['stderrFile']).read_bytes(), stderr)
        self.assertEqual(calls, [(('shell', 'dumpsys', 'window', 'windows'), dict(check=False, timeout=5))])
        self.assertEqual(value['sha256'], hashlib.sha256(stdout).hexdigest())
        self.assertEqual(value['stderrSha256'], hashlib.sha256(stderr).hexdigest())
        self.assertNotIn('ready', value)
        self.assertNotIn('actualDocumentsUiObserved', value)

    def test_failed_window_capture_retains_raw_errors_and_propagates(self):
        def adb(*parts, **kwargs):
            return subprocess.CompletedProcess(parts, 1, stdout=b'partial raw\n', stderr=b'offline\n')
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaises(subprocess.CalledProcessError):
                controller.capture_tap_window(adb, Path(directory), focused())
            self.assertEqual((Path(directory) / 'file-picker-1-tap-windows.txt').read_bytes(), b'partial raw\n')
            self.assertEqual((Path(directory) / 'file-picker-1-tap-windows.stderr.txt').read_bytes(), b'offline\n')

    def test_unknown_stage_cannot_request_a_window_observation(self):
        value = focused()
        value['stage'] = '../unknown'
        adb = mock.Mock()
        with tempfile.TemporaryDirectory() as directory, self.assertRaises(AssertionError):
            controller.capture_tap_window(adb, Path(directory), value)
        adb.assert_not_called()

    def test_original_geometry_oracles_and_fixture_dom_remain_byte_exact(self):
        path = ROOT / 'tools/browser/run_integration.py'
        raw = path.read_text()
        node = next(node for node in ast.parse(raw).body if isinstance(node, ast.FunctionDef)
                    and node.name == 'validate_tap_target')
        self.assertEqual(hashlib.sha256(ast.get_source_segment(raw, node).encode()).hexdigest(), OLD_VALIDATOR_SHA)
        source = (ROOT / 'tests/gecko/BrowserIntegrationActivity.java').read_text()
        for name, digest in OLD_JAVA_HELPER_SHAS.items():
            self.assertEqual(hashlib.sha256(java_method(source, name).encode()).hexdigest(), digest)
        html = next(line for line in source.splitlines() if 'else{String html=' in line)
        self.assertEqual(hashlib.sha256(html.encode()).hexdigest(), OLD_HTML_SHA)

    def test_actual_java_focus_readiness_executes_on_both_pinned_json_runtimes(self):
        source = (ROOT / 'tests/gecko/BrowserIntegrationActivity.java').read_text()
        methods = '\n'.join(java_method(source, name) for name in
            ('nativeTargetReady', 'focusedNativeTargetReady', 'focusedDomTargetReady'))
        home = Path(os.environ.get('JAVA_HOME', ''))
        javac = str(home / 'bin/javac') if (home / 'bin/javac').is_file() else shutil.which('javac')
        java = str(home / 'bin/java') if (home / 'bin/java').is_file() else shutil.which('java')
        self.assertTrue(javac and java, 'Actual Java compiler/runtime required')
        body = '''static void check(boolean good){if(!good)throw new AssertionError("focus guard");}
public static void main(String[] args)throws Exception{
 JSONObject p=new JSONObject(args[0]),n=p.getJSONObject("nativeFrame"),d=p.getJSONObject("dom");
 check(nativeTargetReady(n));check(!focusedNativeTargetReady(n));check(!focusedDomTargetReady(d));
 n.put("viewFocus",true);d.put("documentFocus",true);
 check(focusedNativeTargetReady(n));check(focusedDomTargetReady(d));
 for(Object bad:new Object[]{false,0,1,"true",JSONObject.NULL}){
   n.put("viewFocus",bad);d.put("documentFocus",bad);
   check(!focusedNativeTargetReady(n));check(!focusedDomTargetReady(d));
 }
 n.remove("viewFocus");d.remove("documentFocus");
 check(!focusedNativeTargetReady(n));check(!focusedDomTargetReady(d));
 n.put("viewFocus",true);n.put("windowFocus",false);check(!focusedNativeTargetReady(n));
 System.out.println("focus-controls-passed");}'''
        code = 'import org.json.*; public class FocusHost{\n' + methods + '\n' + body + '\n}'
        for name, digest, candidates in (
                ('desktop', '3cf6cd6892e32e2b4c1c39e0f52f5248a2f5b37646fdfbb79a66b46b618414ed',
                 ('work/browser-host-deps/json.jar', 'work/gecko-integration/catalog-json.jar')),
                ('android-json', 'dfb7bae2f404cfe0b72b4d23944698cb716b7665171812a0a4d0f5926c0fac79',
                 ('work/browser-host-deps/android-json.jar', 'work/profile-host/android-json.jar'))):
            jar = next((ROOT / candidate for candidate in candidates
                        if (ROOT / candidate).is_file()
                        and hashlib.sha256((ROOT / candidate).read_bytes()).hexdigest() == digest), None)
            self.assertIsNotNone(jar, 'Pinned browser/profile JSON runtime required: ' + name)
            self.assertEqual(hashlib.sha256(jar.read_bytes()).hexdigest(), digest)
            with self.subTest(runtime=name), tempfile.TemporaryDirectory() as directory:
                path = Path(directory)
                (path / 'FocusHost.java').write_text(code)
                run = subprocess.run([javac, '--release', '17', '-cp', str(jar), '-d', directory,
                    str(path / 'FocusHost.java')], capture_output=True, text=True, timeout=30)
                self.assertEqual(run.returncode, 0, run.stderr)
                run = subprocess.run([java, '-cp', directory + os.pathsep + str(jar), 'FocusHost',
                    json.dumps(fixture()['current']['tapTarget'])], capture_output=True, text=True, timeout=20)
                self.assertEqual(run.returncode, 0, run.stdout + run.stderr)
                self.assertEqual(run.stdout.strip(), 'focus-controls-passed')

    def test_actual_java_hook_retains_original_stability_and_target_budget(self):
        source = (ROOT / 'tests/gecko/BrowserIntegrationActivity.java').read_text()
        start = source.index('  void targetFrame(')
        end = source.index('  void preparePicker()', start)
        method = source[start:end]
        self.assertLess(method.index('view.requestFocus()'), method.index('JSONObject before='))
        self.assertEqual(method.count('focusedNativeTargetReady('), 3)
        self.assertLess(method.index('focusedDomTargetReady(dom)'), method.index('sameDomTarget(previousDom,dom)'))
        self.assertIn('view.postVisualStateCallback(', method)
        self.assertIn('"stableSamples",2', method)
        self.assertIn('probe.postDelayed(targetTimeout,45000)', source)
        self.assertNotIn('dispatchTouchEvent(', method)


if __name__ == '__main__':
    unittest.main()
