"""Actual foreign-stack regression and host-only crash ownership controls."""
import ast
import copy
import hashlib
from pathlib import Path
import sys
import tempfile
import time
from types import SimpleNamespace
import unittest


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools/gecko'))
import glass_ui_validation as glass


PACKAGE = 'local.pocketchat.test'
FIXTURE = ROOT / 'tests/fixtures/glass-api32-foreign-crash.txt'


def fatal(process=PACKAGE, pid=2026):
    """Explicit synthetic AndroidRuntime brief block, never device evidence."""
    return ('E/AndroidRuntime( ' + str(pid) + '): FATAL EXCEPTION: main\n'
            'E/AndroidRuntime( ' + str(pid) + '): Process: ' + process + ', PID: ' + str(pid) + '\n'
            'E/AndroidRuntime( ' + str(pid) + '): java.lang.IllegalStateException: host negative\n').encode()


class GlassCrashOwnershipTest(unittest.TestCase):
    def test_actual_foreign_stack_is_retained_with_exact_process_pid_and_digest(self):
        raw = FIXTURE.read_bytes()
        self.assertEqual(len(raw), 1230)
        self.assertEqual(hashlib.sha256(raw).hexdigest(),
                         '94694313dd8dec3a78a97bccff7277e171dbace92a12ae1f33a87f0fd03078ff')
        # This is the exact a9daef/API32/attempt2 failure, not a new app PASS.
        self.assertIn(b'FATAL EXCEPTION', raw)
        value = glass.android_runtime_crash_ownership(raw, PACKAGE)
        self.assertEqual(value['rawBytes'], len(raw))
        self.assertEqual(value['rawSha256'], hashlib.sha256(raw).hexdigest())
        self.assertEqual(value['fatalBlockCount'], 1)
        self.assertEqual(value['crashes'], [dict(pid=1774,
            process='com.google.android.apps.youtube.music', targetPackage=False,
            fatalLine=2, processLine=3)])

    def test_current_package_and_each_child_process_fatal_are_rejected(self):
        for process in (PACKAGE, PACKAGE + ':profile1', PACKAGE + ':tab0', PACKAGE + ':Gecko_IO'):
            with self.subTest(process=process), self.assertRaisesRegex(ValueError, 'current Android application'):
                glass.android_runtime_crash_ownership(fatal(process), PACKAGE)

    def test_similar_package_prefix_and_target_class_in_foreign_stack_are_not_owner(self):
        raw = fatal(PACKAGE + 'ed') + b'E/AndroidRuntime( 2026): at local.pocketchat.test.MainActivity.run(MainActivity.java:1)\n'
        value = glass.android_runtime_crash_ownership(raw, PACKAGE)
        self.assertEqual(value['crashes'][0]['process'], PACKAGE + 'ed')
        self.assertIs(value['crashes'][0]['targetPackage'], False)

    def test_foreign_first_cannot_hide_later_target_and_target_first_cannot_be_overwritten(self):
        for raw in (FIXTURE.read_bytes() + fatal(), fatal() + FIXTURE.read_bytes(),
                    fatal('org.example.foreign') + fatal(PACKAGE + ':profile2')):
            with self.subTest(raw=raw[:60]), self.assertRaises(ValueError):
                glass.android_runtime_crash_ownership(raw, PACKAGE)

    def test_multiple_explicit_foreign_blocks_are_each_retained(self):
        value = glass.android_runtime_crash_ownership(FIXTURE.read_bytes() + fatal('org.example.other', 2900), PACKAGE)
        self.assertEqual(value['fatalBlockCount'], 2)
        self.assertEqual([v['pid'] for v in value['crashes']], [1774, 2900])
        self.assertEqual([v['targetPackage'] for v in value['crashes']], [False, False])

    def test_missing_ambiguous_or_malformed_owner_fails_closed(self):
        original = fatal('org.example.foreign')
        header, owner, stack = original.splitlines(keepends=True)
        for raw in (header + stack, header + owner + owner + stack,
                    header + owner + owner.replace(b'org.example.foreign', PACKAGE.encode()) + stack,
                    header + owner.replace(b'PID: 2026', b'PID: 2027') + stack,
                    header + owner.replace(b'( 2026)', b'( 2027)') + stack,
                    header + owner.replace(b'PID: 2026', b'PID: 0') + stack,
                    header + owner.replace(b'PID: 2026', b'PID: unknown') + stack,
                    header + owner.replace(b', PID: 2026', b'') + stack,
                    header + owner.replace(b'org.example.foreign', b'') + stack,
                    header + owner.replace(b'E/AndroidRuntime', b'X/AndroidRuntime') + stack,
                    header + owner + stack.replace(b'( 2026)', b'( 2027)'),
                    header + owner + stack.replace(b'( 2026)', b'( unknown)')):
            with self.subTest(raw=raw), self.assertRaises(ValueError):
                glass.android_runtime_crash_ownership(raw, PACKAGE)

    def test_unknown_fatal_format_or_borrowing_another_block_owner_fails_closed(self):
        for raw in (b'FATAL EXCEPTION: main\nProcess: org.example.foreign, PID: 2026\n',
                    fatal('org.example.foreign').replace(b'FATAL EXCEPTION: main', b'FATAL EXCEPTION:'),
                    fatal('org.example.foreign').replace(b'E/AndroidRuntime', b'I/OtherTag', 1),
                    b'E/AndroidRuntime( 2026): FATAL EXCEPTION: first\n' + fatal('org.example.foreign'),
                    b'E/AndroidRuntime( 2026): Process: org.example.foreign, PID: 2026\n'
                    b'E/AndroidRuntime( 2026): FATAL EXCEPTION: main\n',
                    b'E/AndroidRuntime( 2026): Process: local.pocketchat.test, PID: 2026\n',
                    b'E/AndroidRuntime( 2026): Process: local.pocketchat.test, PID: 2026\n'
                    + FIXTURE.read_bytes()):
            with self.subTest(raw=raw), self.assertRaises(ValueError):
                glass.android_runtime_crash_ownership(raw, PACKAGE)

    def test_explicit_current_package_and_valid_utf8_bytes_are_required(self):
        for raw, package in ((b'', ''), (b'', PACKAGE + ':child'), ('', PACKAGE),
                             (b'FATAL EXCEPTION\xff', PACKAGE)):
            with self.subTest(package=package), self.assertRaises((ValueError, UnicodeError)):
                glass.android_runtime_crash_ownership(raw, package)
        for raw in (b'', b'I/PocketGeckoIntegration( 2026): no crash\n'):
            self.assertEqual(glass.android_runtime_crash_ownership(raw, PACKAGE)['fatalBlockCount'], 0)

    def driver(self, name, raw, package=PACKAGE):
        """Execute the actual nested producer body with bounded host I/O doubles."""
        tree = ast.parse((ROOT / 'tools/gecko/glass_ui_validation.py').read_text())
        suite = next(v for v in tree.body if isinstance(v, ast.FunctionDef)
                     and v.name == 'capture_acceptance_suite')
        function = copy.deepcopy(next(v for v in ast.walk(suite)
                     if isinstance(v, ast.FunctionDef) and v.name == name))
        # Only the I/O and unrelated document result are modeled; the actual
        # producer's crash check, package argument and raw-byte write execute.
        seen = []
        case = dict(name='host-case', runNonce='a' * 32)
        with tempfile.TemporaryDirectory() as directory:
            def receipt(line):
                if line.startswith('I/HostReceipt: '):
                    return dict(runNonce=case['runNonce'], command=line.removeprefix('I/HostReceipt: '))
                return None
            class Reader:
                def read(self, value):
                    seen.append(value['command'])
                    return dict(kind='collapseSnapshot' if name == 'observed_event' else 'glassOwnerObservation',
                                result=dict(command=value['command']))
            env = dict(time=time, package=package, args=SimpleNamespace(out=Path(directory)),
                adb=lambda *args, **kwargs: raw, parse_receipt_line=receipt,
                observations={case['runNonce']: Reader()}, require_document_viewport=lambda value: value,
                android_runtime_crash_ownership=glass.android_runtime_crash_ownership)
            exec(compile(ast.fix_missing_locations(ast.Module(body=[function], type_ignores=[])),
                         '<actual producer host driver>', 'exec'), env)
            try:
                if name == 'observed_event':
                    value = env[name](case, 'ready', request=False)
                else:
                    value = env[name](case, ['before', 'after'])
            finally:
                self.assertEqual((Path(directory) / 'host-case-events.log').read_bytes(), raw)
            return case, value, seen

    def test_both_actual_producer_gates_keep_foreign_raw_and_continue_to_bound_receipt(self):
        for name, suffix, commands in (
                ('observed_event', b'I/HostReceipt: ready\n', ['ready']),
                ('observed_glass_pair', b'I/HostReceipt: before\nI/HostReceipt: after\n', ['before', 'after'])):
            with self.subTest(name=name):
                raw = FIXTURE.read_bytes() + suffix
                case, value, seen = self.driver(name, raw)
                self.assertEqual(seen, commands)
                self.assertEqual(case['androidRuntimeCrashOwnership']['rawSha256'], hashlib.sha256(raw).hexdigest())
                self.assertEqual(case['androidRuntimeCrashOwnership']['fatalBlockCount'], 1)

    def test_both_actual_producer_gates_reject_target_and_unknown_before_receipt(self):
        for name in ('observed_event', 'observed_glass_pair'):
            for raw in (fatal(), fatal(PACKAGE + ':profile1'),
                        b'E/AndroidRuntime( 2026): FATAL EXCEPTION: missing owner\n'):
                with self.subTest(name=name, raw=raw), self.assertRaises(ValueError):
                    self.driver(name, raw + b'I/HostReceipt: ready\n')

    def test_actual_producer_uses_current_runtime_package_for_attribution(self):
        for name in ('observed_event', 'observed_glass_pair'):
            with self.subTest(name=name), self.assertRaises(ValueError):
                self.driver(name, fatal('org.example.current'), package='org.example.current')


if __name__ == '__main__':
    unittest.main()
