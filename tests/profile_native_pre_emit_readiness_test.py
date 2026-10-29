"""Actual pure-Java pre-emission controls; no Android input is emitted.

The visible-shade counterexample is controlled data shaped like a separately
captured clean WM dump. It is not a WM capture from the failed gesture instant.
"""
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest
import copy

ROOT = Path(__file__).resolve().parents[1]
HELPER = ROOT / 'tests/native-input-driver/NativePreEmitReadiness.java'
HOST = ROOT / 'tests/native-input-readiness-host/NativePreEmitReadinessHostTest.java'
SHELL = ROOT / 'tests/native-input-driver/NativeInputShell.java'
PROTOCOL = ROOT / 'tests/native-input-driver/NativeGestureProtocol.java'
PROTOCOL_SHA = 'ad7245417be77830d16f2170de992cea0f224284b49f66e161f8b2d5a1f8fdf3'
LEGACY_FOCUS_SHA = '6734a1f21a7347ad0fd7b3e6958332fb01646af379acfd327075d4f1b51c37ed'


def focus_member(source):
    start = source.index('  static JSONObject parseFocus(')
    opening = source.index('{', start)
    level, mode, escaped, index = 0, 'code', False, opening
    while index < len(source):
        char = source[index]
        following = source[index + 1:index + 2]
        if mode in ('string', 'char'):
            if escaped:
                escaped = False
            elif char == '\\':
                escaped = True
            elif char == ('"' if mode == 'string' else "'"):
                mode = 'code'
        elif mode == 'line':
            if char == '\n':
                mode = 'code'
        elif mode == 'block':
            if char == '*' and following == '/':
                mode = 'code'
                index += 1
        elif char == '"':
            mode = 'string'
        elif char == "'":
            mode = 'char'
        elif char == '/' and following in ('/', '*'):
            mode = 'line' if following == '/' else 'block'
            index += 1
        elif char == '{':
            level += 1
        elif char == '}':
            level -= 1
            if level == 0:
                return source[start:index + 1]
        index += 1
    raise ValueError('Unclosed original focus member')


class NativePreEmitReadinessTest(unittest.TestCase):
    def test_helper_is_bound_into_actual_driver_build_inputs(self):
        from gecko_native_input_driver_test import C, receipt
        self.assertEqual(Path(C.__file__).resolve(), (ROOT / 'tools/gecko/native_input_contract.py').resolve())
        helper = 'tests/native-input-driver/NativePreEmitReadiness.java'
        self.assertIn(helper, C.INPUTS)
        _, arguments = receipt()
        build = arguments['build']
        source_reader = lambda source, path: (ROOT / path).read_bytes()
        C.verify_build(build, 'a' * 40, source_reader)
        missing = copy.deepcopy(build)
        del missing['inputs'][helper]
        with self.assertRaisesRegex(ValueError, 'driver input set'):
            C.verify_build(missing, 'a' * 40, source_reader)
        substituted = copy.deepcopy(build)
        substituted['inputs'][helper] = '0' * 64
        with self.assertRaisesRegex(ValueError, 'driver source bytes'):
            C.verify_build(substituted, 'a' * 40, source_reader)

    def test_fixed_input_schedule_and_original_focus_member_are_unchanged(self):
        self.assertEqual(hashlib.sha256(PROTOCOL.read_bytes()).hexdigest(), PROTOCOL_SHA)
        legacy = focus_member(SHELL.read_text())
        self.assertEqual(hashlib.sha256(legacy.encode()).hexdigest(), LEGACY_FOCUS_SHA)

    def test_actual_java_helper_against_controlled_window_and_deadline_cases(self):
        java_home = os.environ.get('JAVA_HOME')
        java = Path(java_home) / 'bin/java' if java_home else Path(shutil.which('java') or '')
        javac = java.with_name('javac')
        self.assertTrue(java.is_file() and javac.is_file(), 'A real JDK is required; no skipped acceptance')
        self.assertTrue(HELPER.is_file() and HOST.is_file())
        legacy = focus_member(SHELL.read_text())
        self.assertEqual(hashlib.sha256(legacy.encode()).hexdigest(), LEGACY_FOCUS_SHA)
        comparator = '''package local.pocketchat.inputdriver;
import java.util.regex.Matcher;
import java.util.regex.Pattern;
final class LegacyFocusComparator {
  static final String TARGET="local.pocketchat.test";
  static final class JSONObject { JSONObject put(String key,Object value){return this;} }
%s
  static boolean accepts(String raw){try{parseFocus(raw);return true;}catch(Exception failure){return false;}}
}
''' % legacy
        before = {str(path): hashlib.sha256(path.read_bytes()).hexdigest() for path in (HELPER, HOST, SHELL, PROTOCOL)}
        with tempfile.TemporaryDirectory(prefix='native-preemit-host-') as temporary:
            directory = Path(temporary)
            old = directory / 'LegacyFocusComparator.java'
            old.write_text(comparator)
            compiled = subprocess.run([str(javac), '-encoding', 'UTF-8', '-d', temporary,
                                       str(HELPER), str(HOST), str(old)], capture_output=True, timeout=30)
            self.assertEqual(compiled.returncode, 0, (compiled.stdout + compiled.stderr).decode('utf-8', 'replace'))
            executed = subprocess.run([str(java), '-cp', temporary,
                                       'local.pocketchat.inputdriver.NativePreEmitReadinessHostTest'],
                                      capture_output=True, timeout=30)
            self.assertEqual(executed.returncode, 0, (executed.stdout + executed.stderr).decode('utf-8', 'replace'))
            report = json.loads(executed.stdout)
        self.assertEqual(before, {str(path): hashlib.sha256(path.read_bytes()).hexdigest() for path in (HELPER, HOST, SHELL, PROTOCOL)})
        self.assertEqual(report['status'], 'passed')
        self.assertEqual(report['checks'], report['passed'])
        self.assertGreaterEqual(report['checks'], 90)
        self.assertIs(report['actualAndroidExecution'], False)
        self.assertIs(report['nativeInputEmitted'], False)
        self.assertIs(report['releaseAcceptance'], False)
        self.assertIs(report['failedInstantWindowCapture'], False)
        type(self).host_report = report


if __name__ == '__main__':
    unittest.main()
