"""Host-only chrome-header readiness controls; never emits Android input.

The visible-shade input is a controlled counterexample shaped like a separate
clean WM capture. It is not a WM capture from a failed gesture instant.
"""
from contextlib import ExitStack, redirect_stdout
import base64
import copy
import hashlib
import importlib.util
import io
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import time
import unittest
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
HELPER = ROOT / 'tests/native-input-driver/NativePreEmitReadiness.java'
CLI = ROOT / 'tests/native-input-readiness-host/NativePreEmitReadinessCli.java'
HELPER_SHA = '40130991cd673e5b38a5e1ca18c3bcca71cff74ec69550126cd6303ef0b66348'
COMPONENT = 'local.pocketchat.test/local.pocketchat.CompactChromeIntegrationActivity'
TOKEN = '44918a3'
PRIVATE = 'PRIVATE_HEADER_READINESS_SENTINEL_14589'


def window_block(index, token, title, uid, package, visible):
    flag = str(visible).lower()
    return (f'  Window #{index} Window{{{token} u0 {title}}}:\n'
            '    mDisplayId=0 rootTaskId=1\n'
            f'    mOwnerUid={uid} showForAllUsers=true package={package} appop=NONE\n'
            f'    mHasSurface={flag} mWindowRemovalAllowed=false\n'
            f'    isOnScreen={flag}\n    isVisible={flag}\n')


def window(shade=False):
    return ('WINDOW MANAGER DISPLAY CONTENTS (dumpsys window displays)\n'
            f'  mCurrentFocus=Window{{{TOKEN} u0 {COMPONENT}}}\n'
            'WINDOW MANAGER WINDOWS (dumpsys window windows)\n'
            + window_block(0, '9b057bb', 'NotificationShade', 10181,
                           'com.android.systemui', shade)
            + window_block(1, TOKEN, COMPONENT, 10209, 'local.pocketchat.test', True)
            + '  mTopFocusedDisplayId=0\n'
            'WINDOW MANAGER TRACE (dumpsys window trace)\nStatus: Disabled\n')


class ChromeHeaderReadinessCliTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        java_home = os.environ.get('JAVA_HOME')
        java = Path(java_home) / 'bin/java' if java_home else Path(shutil.which('java') or '')
        javac = java.with_name('javac')
        if not java.is_file() or not javac.is_file():
            raise AssertionError('A real JDK is required; no skipped acceptance')
        cls.before = {path: hashlib.sha256(path.read_bytes()).hexdigest()
                      for path in (HELPER, CLI)}
        if cls.before[HELPER] != HELPER_SHA:
            raise AssertionError('The original helper bytes must remain unchanged')
        cls.temporary = tempfile.TemporaryDirectory(prefix='chrome-header-readiness-host-')
        cls.addClassCleanup(cls.temporary.cleanup)
        compiled = subprocess.run([str(javac), '-encoding', 'UTF-8', '-d', cls.temporary.name,
                                   str(HELPER), str(CLI)], capture_output=True, timeout=30)
        if compiled.returncode:
            raise AssertionError((compiled.stdout + compiled.stderr).decode('utf-8', 'replace'))
        cls.command = [str(java), '-cp', cls.temporary.name,
                       'local.pocketchat.inputdriver.NativePreEmitReadinessCli']

    @classmethod
    def tearDownClass(cls):
        if cls.before != {path: hashlib.sha256(path.read_bytes()).hexdigest()
                          for path in (HELPER, CLI)}:
            raise AssertionError('Actual parser source changed during host controls')

    def run_cli(self, raw, args=None):
        if isinstance(raw, str):
            raw = raw.encode('utf-8')
        return subprocess.run(self.command + (args if args is not None else
                              ['10209', '10181', COMPONENT, TOKEN]),
                              input=raw, capture_output=True, timeout=5)

    def reject(self, raw, args=None):
        result = self.run_cli(raw, args)
        self.assertEqual(result.returncode, 2)
        self.assertEqual(result.stdout, b'')
        self.assertEqual(result.stderr, b'invalid-observation\n')
        self.assertNotIn(PRIVATE.encode(), result.stderr)

    def test_actual_parser_clear_and_controlled_visible_shade(self):
        for shade, expected in ((False, b'CLEAR\n'), (True, b'SHADE_VISIBLE\n')):
            with self.subTest(shade=shade):
                result = self.run_cli(window(shade))
                self.assertEqual((result.returncode, result.stdout, result.stderr),
                                 (0, expected, b''))
        result = self.run_cli(window().replace('\n', '\r\n'))
        self.assertEqual((result.returncode, result.stdout, result.stderr), (0, b'CLEAR\n', b''))

    def test_exact_focused_activity_token_user_and_owners_are_required(self):
        clean = window()
        for raw, args in (
            (clean, ['10209', '10181', COMPONENT, '0000000']),
            (clean, ['10209', '10181', COMPONENT.replace('CompactChrome', 'GeckoPerformance'), TOKEN]),
            (clean.replace(COMPONENT, COMPONENT.replace('CompactChrome', 'GeckoPerformance')), None),
            (clean.replace(TOKEN + ' u0 ', TOKEN + ' u10 '), None),
            (clean.replace('mTopFocusedDisplayId=0', 'mTopFocusedDisplayId=1'), None),
            (clean.replace('mOwnerUid=10209', 'mOwnerUid=10210'), None),
            (clean.replace('mOwnerUid=10181', 'mOwnerUid=10182'), None),
            (clean.replace('package=local.pocketchat.test', 'package=' + PRIVATE), None),
            (clean.replace('package=com.android.systemui', 'package=' + PRIVATE), None),
            (clean.replace('  mTopFocusedDisplayId=0',
                           f'  mCurrentFocus=Window{{{TOKEN} u0 {COMPONENT}}}\n  mTopFocusedDisplayId=0'), None),
        ):
            with self.subTest(raw=raw[:70], args=args):
                self.reject(raw, args)

    def test_strict_argument_utf8_input_and_complete_snapshot_bounds(self):
        clean = window()
        for args in ([], ['10209', '10181', COMPONENT],
                     ['10209', '10181', COMPONENT, TOKEN, PRIVATE],
                     ['010209', '10181', COMPONENT, TOKEN],
                     ['+10209', '10181', COMPONENT, TOKEN],
                     ['10209', '10209', COMPONENT, TOKEN],
                     ['10209', '10181', COMPONENT, TOKEN.upper()],
                     ['10209', '10181', COMPONENT, TOKEN + ' ']):
            with self.subTest(args=args):
                self.reject(clean, args)
        for raw in (b'', b'\xc3', (clean + '\0' + PRIVATE).encode(),
                    b'x' * (2097152 + 1),
                    clean.replace('Window #0 Window{', 'Window #0 Broken{'),
                    clean[:clean.index('WINDOW MANAGER TRACE')],
                    clean.replace('isVisible=false', 'isVisible=' + PRIVATE),
                    clean.replace('WINDOW MANAGER WINDOWS (dumpsys window windows)', PRIVATE)):
            with self.subTest(raw_type=type(raw).__name__, size=len(raw)):
                self.reject(raw)
        exact_bound = clean.encode('utf-8')
        exact_bound += b'x' * (2097152 - len(exact_bound))
        result = self.run_cli(exact_bound)
        self.assertEqual((result.returncode, result.stdout, result.stderr), (0, b'CLEAR\n', b''))


class FakeClock:
    def __init__(self):
        self.value = 1000.0
        self.sleeps = []
        self.frozen = False

    def now(self):
        return self.value

    def sleep(self, seconds):
        self.sleeps.append(seconds)
        if not self.frozen:
            self.value += seconds


class HeaderControllerHarness:
    """Controlled host dependencies only; no adb or Android subprocess is run."""
    def __init__(self, adapter, out):
        self.adapter, self.out, self.clock = adapter, out, FakeClock()
        self.source = 'a' * 40
        self.identity = {'sourceCommit': self.source, 'sourceTree': 'b' * 40}
        self.owner = dict(pid='4914', uid=10209, startTicks='12120', systemUiUid=10181)
        self.binding = dict(self.identity, sourceSha256={adapter.HELPER: HELPER_SHA,
                            adapter.CLI: hashlib.sha256(CLI.read_bytes()).hexdigest(),
                            adapter.ADAPTER: 'c' * 64})
        self.states, self.snapshots = [b'CLEAR\n'], [window().encode()]
        self.owner_values = [self.owner]
        self.sources, self.compiles, self.identities = [], [], []
        self.probes, self.parsers, self.actions = [], [], []
        self.preflight = []
        self.device_values = {
            ('shell', 'getprop', 'ro.kernel.qemu'): b'1\n',
            ('shell', 'getprop', 'ro.build.version.sdk'): b'35\n',
            ('shell', 'am', 'get-current-user'): b'0\n',
            ('shell', 'getprop', 'ro.hardware'): b'ranchu\n',
        }
        self.compile_seconds = self.action_seconds = 0
        self.source_error = self.parse_error = None
        self.changed_source = False
        self.action_code = 0
        self.command = ['java-test', '-cp', 'classes-test', adapter.CLASS]
        self.classes = {'NativePreEmitReadinessCli.class': 'd' * 64}
        self.compiled = dict(parserClassesSha256='e' * 64, cache=out/'cache', classes=self.classes)

    def source_binding(self, root, source, identity, deadline):
        self.sources.append(deadline)
        if self.source_error:
            raise self.adapter.HeaderReadinessFailure(self.source_error)
        value = dict(self.binding)
        if self.changed_source and len(self.sources) > 1:
            value['sourceTree'] = 'f' * 40
        return value

    def compile(self, root, binding, deadline):
        self.compiles.append(deadline)
        self.clock.value += self.compile_seconds
        return self.command, self.compiled

    def check_owner(self, prefix, identity, deadline):
        self.identities.append(deadline)
        value = self.owner_values[min(len(self.identities)-1, len(self.owner_values)-1)]
        if isinstance(value, Exception):
            raise value
        return value

    def checked(self, parts, deadline, **kwargs):
        if tuple(parts[3:]) in self.device_values:
            self.preflight.append((parts, deadline))
            return self.device_values[tuple(parts[3:])]
        if parts[-3:] == ['shell', 'dumpsys', 'window']:
            self.probes.append((parts, deadline))
            return self.snapshots[min(len(self.probes)-1, len(self.snapshots)-1)]
        if parts[:len(self.command)] == self.command:
            self.parsers.append((parts, deadline, kwargs))
            if self.parse_error:
                raise self.adapter.HeaderReadinessFailure(self.parse_error)
            return self.states[min(len(self.parsers)-1, len(self.states)-1)]
        raise AssertionError('Unexpected controlled command')

    def run_action(self, parts, deadline, **kwargs):
        self.actions.append((parts, deadline, kwargs))
        self.clock.value += self.action_seconds
        return subprocess.CompletedProcess(parts, self.action_code, b'', b'')

    def invoke(self, argv=None):
        with ExitStack() as stack:
            for name, replacement in (('_source_bindings', self.source_binding),
                                      ('_compile_parser', self.compile),
                                      ('_identity', self.check_owner),
                                      ('_checked', self.checked),
                                      ('_bounded_run', self.run_action),
                                      ('_class_hashes', lambda _: self.classes)):
                stack.enter_context(patch.object(self.adapter, name, side_effect=replacement))
            stack.enter_context(redirect_stdout(io.StringIO()))
            try:
                result = self.adapter.header_up_once(
                    argv=['--adb', 'adb-test', '--serial', 'emulator-5554'] if argv is None else argv,
                    source=self.source, identity=self.identity, start=[140, 260], end=[140, 110],
                    nonce='1' * 32, out=self.out, root=ROOT,
                    clock=self.clock.now, sleep=self.clock.sleep)
                return result, None
            except self.adapter.HeaderReadinessFailure as failure:
                return None, failure.reason

    def receipt(self):
        return json.loads((self.out/('chrome-header-readiness-' + '1' * 32 + '.json')).read_text())


class ChromeHeaderReadinessControllerTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        directory = str(ROOT / 'tools/gecko')
        sys.path.insert(0, directory)
        try:
            spec = importlib.util.spec_from_file_location(
                'chrome_header_readiness_under_test', ROOT / 'tools/gecko/chrome_header_readiness.py')
            cls.adapter = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(cls.adapter)
        finally:
            sys.path.remove(directory)

    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix='chrome-header-controller-host-')
        self.addCleanup(self.temporary.cleanup)
        self.h = HeaderControllerHarness(self.adapter, Path(self.temporary.name))

    def test_clear_observation_emits_original_swipe_exactly_once_without_delay(self):
        result, failure = self.h.invoke()
        self.assertIsNone(failure)
        self.assertEqual(result['status'], 'passed')
        self.assertEqual(result['observations'], 1)
        self.assertEqual(result['gestureInvocations'], 1)
        self.assertEqual(self.h.clock.sleeps, [])
        self.assertEqual(self.h.actions, [(['adb-test', '-s', 'emulator-5554', 'shell', 'input',
                                          'swipe', '140', '260', '140', '110', '320'], 1090.0, {})])
        self.assertEqual(self.h.sources, [1020.0, 1020.0])
        self.assertEqual(self.h.compiles, [1020.0])
        self.assertTrue(all(deadline == 1020.0 for deadline in self.h.identities))
        self.assertEqual(self.h.parsers[0][0][-4:], ['10209', '10181', COMPONENT, TOKEN])
        self.assertEqual(self.h.parsers[0][2], dict(input_bytes=window().encode(), stdout_limit=64, stderr_limit=64))
        self.assertEqual(self.h.receipt(), result)
        self.assertIs(result['preEmitOnly'], True)
        self.assertIs(result['applicationAcceptance'], False)
        self.assertIs(result['releaseAcceptance'], False)

    def test_only_valid_visible_shade_is_polled_before_single_original_action(self):
        self.h.states = [b'SHADE_VISIBLE\n', b'CLEAR\n']
        self.h.snapshots = [window(True).encode(), window().encode()]
        result, failure = self.h.invoke()
        self.assertIsNone(failure)
        self.assertEqual(result['observations'], 2)
        self.assertIs(result['shadeObserved'], True)
        self.assertEqual(self.h.clock.sleeps, [.2])
        self.assertEqual(len(self.h.actions), 1)
        self.assertEqual(self.h.actions[0][1], 1090.0)
        self.assertEqual(self.h.compiles, [1020.0])
        self.assertTrue(all(deadline == 1020.0 for _, deadline in self.h.probes))

    def test_javac_time_is_inside_original_twenty_second_preparation_budget(self):
        self.h.compile_seconds = 20
        result, failure = self.h.invoke()
        self.assertIsNone(result)
        self.assertEqual(failure, 'deadline')
        self.assertEqual(self.h.actions, [])
        self.assertEqual(self.h.probes, [])
        self.assertEqual(self.h.receipt()['preparationBudgetMs'], 20000)
        self.assertEqual(self.h.receipt()['elapsedMs'], 20000)

    def test_stuck_shade_has_bounded_original_deadline_and_never_emits(self):
        self.h.states = [b'SHADE_VISIBLE\n']
        result, failure = self.h.invoke()
        self.assertIsNone(result)
        self.assertEqual(failure, 'deadline')
        self.assertEqual(self.h.actions, [])
        self.assertLessEqual(len(self.h.probes), 101)
        self.assertTrue(all(0 < value <= .2 for value in self.h.clock.sleeps))
        self.assertLessEqual(self.h.clock.value, 1020.0)
        self.assertTrue(all(deadline == 1020.0 for _, deadline in self.h.probes))

    def test_frozen_fake_clock_still_has_finite_observation_limit(self):
        self.h.states = [b'SHADE_VISIBLE\n']
        self.h.clock.frozen = True
        _, failure = self.h.invoke()
        self.assertEqual(failure, 'deadline')
        self.assertEqual(len(self.h.probes), 101)
        self.assertEqual(self.h.actions, [])

    def test_identity_change_and_foreign_focus_fail_without_retry_or_action(self):
        self.h.owner_values = [self.h.owner, dict(self.h.owner, startTicks='12121')]
        _, failure = self.h.invoke()
        self.assertEqual(failure, 'identity-changed')
        self.assertEqual(self.h.probes, [])
        self.assertEqual(self.h.actions, [])
        self.assertEqual(self.h.clock.sleeps, [])
        with tempfile.TemporaryDirectory(prefix='chrome-header-focus-host-') as temporary:
            other = HeaderControllerHarness(self.adapter, Path(temporary))
            other.snapshots = [window().replace(COMPONENT, 'other.application/.Main').encode()]
            _, failure = other.invoke()
            self.assertEqual(failure, 'identity-changed')
            self.assertEqual(other.parsers, [])
            self.assertEqual(other.actions, [])
            self.assertEqual(other.clock.sleeps, [])

    def test_owner_change_after_snapshot_or_source_change_before_action_is_blocked(self):
        self.h.owner_values = [self.h.owner, self.h.owner, dict(self.h.owner, pid='4915')]
        _, failure = self.h.invoke()
        self.assertEqual(failure, 'identity-changed')
        self.assertEqual(len(self.h.probes), 1)
        self.assertEqual(self.h.actions, [])
        with tempfile.TemporaryDirectory(prefix='chrome-header-source-host-') as temporary:
            other = HeaderControllerHarness(self.adapter, Path(temporary))
            other.changed_source = True
            _, failure = other.invoke()
            self.assertEqual(failure, 'identity-changed')
            self.assertEqual(other.actions, [])

    def test_focus_token_change_while_waiting_is_not_retargeted(self):
        self.h.states = [b'SHADE_VISIBLE\n', b'CLEAR\n']
        self.h.snapshots = [window(True).encode(), window().replace(TOKEN, '123abcd').encode()]
        _, failure = self.h.invoke()
        self.assertEqual(failure, 'identity-changed')
        self.assertEqual(len(self.h.parsers), 1)
        self.assertEqual(self.h.actions, [])

    def test_invalid_snapshot_and_parser_errors_are_not_polled_or_emitted(self):
        for error in ('observation-failed', 'output-too-large', 'invalid-observation'):
            with self.subTest(error=error), tempfile.TemporaryDirectory(prefix='chrome-header-error-host-') as temporary:
                h = HeaderControllerHarness(self.adapter, Path(temporary))
                h.parse_error = error
                _, failure = h.invoke()
                self.assertEqual(failure, error)
                self.assertEqual(len(h.parsers), 1)
                self.assertEqual(h.actions, [])
                self.assertEqual(h.clock.sleeps, [])
        self.h.states = [b'CLEAR\n' + PRIVATE.encode()]
        _, failure = self.h.invoke()
        self.assertEqual(failure, 'invalid-observation')
        self.assertNotIn(PRIVATE, json.dumps(self.h.receipt()))
        self.assertEqual(self.h.actions, [])

    def test_shared_ninety_second_action_budget_is_not_restarted_after_preparation(self):
        self.h.compile_seconds = 10
        self.h.action_seconds = 81
        _, failure = self.h.invoke()
        self.assertEqual(failure, 'deadline')
        self.assertEqual(len(self.h.actions), 1)
        self.assertEqual(self.h.actions[0][1], 1090.0)
        self.assertEqual(self.h.receipt()['gestureInvocations'], 1)

    def test_failed_original_action_is_not_replayed(self):
        self.h.action_code = 1
        _, failure = self.h.invoke()
        self.assertEqual(failure, 'action-failed')
        self.assertEqual(len(self.h.actions), 1)
        self.assertEqual(self.h.receipt()['gestureInvocations'], 1)

    def test_only_explicit_emulator_target_and_arguments_are_accepted(self):
        for args in ([], ['--adb', 'adb-test'], ['--serial', 'emulator-5554'],
                     ['--adb', 'adb-test', '--serial', 'physical-phone'],
                     ['--adb', 'adb-test', '--serial', 'emulator-5556']):
            with self.subTest(args=args), tempfile.TemporaryDirectory(prefix='chrome-header-target-host-') as temporary:
                h = HeaderControllerHarness(self.adapter, Path(temporary))
                _, failure = h.invoke(args)
                self.assertEqual(failure, 'invalid-request')
                self.assertEqual(h.actions, [])
                self.assertEqual(h.sources, [])

    def test_emulator_api_user_and_hardware_are_independently_required(self):
        for field, invalid in ((('shell', 'getprop', 'ro.kernel.qemu'), b'0\n'),
                               (('shell', 'getprop', 'ro.build.version.sdk'), b'34\n'),
                               (('shell', 'am', 'get-current-user'), b'10\n'),
                               (('shell', 'getprop', 'ro.hardware'), b'physical-device\n')):
            with self.subTest(field=field), tempfile.TemporaryDirectory(prefix='chrome-header-device-host-') as temporary:
                h = HeaderControllerHarness(self.adapter, Path(temporary))
                h.device_values[field] = invalid
                _, failure = h.invoke()
                self.assertEqual(failure, 'identity-changed')
                self.assertEqual(h.identities, [])
                self.assertEqual(h.actions, [])

    def test_unverified_source_or_changed_parser_cache_never_emits(self):
        self.h.source_error = 'source-unverified'
        _, failure = self.h.invoke()
        self.assertEqual(failure, 'source-unverified')
        self.assertEqual(self.h.compiles, [])
        self.assertEqual(self.h.actions, [])
        with tempfile.TemporaryDirectory(prefix='chrome-header-cache-host-') as temporary:
            other = HeaderControllerHarness(self.adapter, Path(temporary))
            # The new observation differs from the retained compile receipt.
            other.classes = {'changed': '0' * 64}
            _, failure = other.invoke()
            self.assertEqual(failure, 'cache-unverified')
            self.assertEqual(other.parsers, [])
            self.assertEqual(other.actions, [])

    def test_duplicate_nonce_never_overwrites_prior_receipt_or_replays_input(self):
        path = self.h.out/('chrome-header-readiness-' + '1' * 32 + '.json')
        existing = b'{"prior":"owned-by-previous-invocation"}\n'
        path.write_bytes(existing)
        _, failure = self.h.invoke()
        self.assertEqual(failure, 'already-invoked')
        self.assertEqual(path.read_bytes(), existing)
        self.assertEqual(self.h.actions, [])
        self.assertEqual(self.h.sources, [])

    def test_real_owned_host_children_enforce_both_stream_caps(self):
        script = ('import os,sys; '
                  'os.write(1,b"o"*int(sys.argv[1])); '
                  'os.write(2,b"e"*int(sys.argv[2]))')
        result = self.adapter._bounded_run(
            [sys.executable, '-c', script, '65536', '65536'], time.monotonic()+3,
            stdout_limit=65536, stderr_limit=65536)
        self.assertEqual((result.returncode, len(result.stdout), len(result.stderr)), (0, 65536, 65536))
        for stdout, stderr in ((65537, 0), (0, 65537)):
            with self.subTest(stdout=stdout, stderr=stderr):
                with self.assertRaises(self.adapter.HeaderReadinessFailure) as failure:
                    self.adapter._bounded_run(
                        [sys.executable, '-c', script, str(stdout), str(stderr)], time.monotonic()+3,
                        stdout_limit=65536, stderr_limit=65536)
                self.assertEqual(failure.exception.reason, 'output-too-large')

    def test_real_owned_host_child_timeout_is_reaped_without_replay(self):
        pid_file = self.h.out/'owned-timeout-child.pid'
        script = ('import os,pathlib,sys,time; '
                  'pathlib.Path(sys.argv[1]).write_text(str(os.getpid())); time.sleep(10)')
        started = time.monotonic()
        with self.assertRaises(self.adapter.HeaderReadinessFailure) as failure:
            self.adapter._bounded_run(
                [sys.executable, '-c', script, str(pid_file)], started+.5)
        self.assertEqual(failure.exception.reason, 'deadline')
        self.assertLess(time.monotonic()-started, 3)
        self.assertTrue(pid_file.is_file(), 'The controlled owned child actually started')
        with self.assertRaises(ProcessLookupError):
            os.kill(int(pid_file.read_text()), 0)

    def test_real_git_source_binding_jdk_cache_reuse_and_tamper_rejection(self):
        with tempfile.TemporaryDirectory(prefix='chrome-header-git-host-') as temporary:
            root = Path(temporary)

            def git(*parts):
                result = subprocess.run(
                    ['git', '-c', 'core.hooksPath=/dev/null', '-c', 'commit.gpgsign=false', *parts],
                    cwd=root, capture_output=True, timeout=10)
                self.assertEqual(result.returncode, 0, result.stderr.decode('utf-8', 'replace'))
                return result.stdout.decode('ascii').strip()

            for name in (self.adapter.HELPER, self.adapter.CLI, self.adapter.ADAPTER):
                destination = root/name
                destination.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(ROOT/name, destination)
            (root/'.gitignore').write_text('/work/\n')
            git('init', '--quiet')
            git('config', 'user.name', 'Local Host Fixture')
            git('config', 'user.email', 'host-fixture@example.invalid')
            git('add', '.')
            git('commit', '--quiet', '--no-verify', '-m', 'Synthetic local parser fixture')
            source, tree = git('rev-parse', 'HEAD'), git('rev-parse', 'HEAD^{tree}')
            identity = dict(sourceCommit=source, sourceTree=tree)
            deadline = time.monotonic()+20
            binding = self.adapter._source_bindings(root, source, identity, deadline)
            self.assertEqual(binding['sourceSha256'][self.adapter.HELPER], HELPER_SHA)
            command, compiled = self.adapter._compile_parser(root, binding, deadline)
            files = list((compiled['cache']/'classes').rglob('*.class'))
            mtimes = {str(path): path.stat().st_mtime_ns for path in files}
            again_command, again = self.adapter._compile_parser(root, binding, deadline)
            self.assertEqual((again_command, again), (command, compiled))
            self.assertEqual(mtimes, {str(path): path.stat().st_mtime_ns for path in files})
            actual = self.adapter._bounded_run(command+['10209', '10181', COMPONENT, TOKEN],
                                               deadline, input_bytes=window().encode())
            self.assertEqual((actual.returncode, actual.stdout, actual.stderr), (0, b'CLEAR\n', b''))

            changed_class = compiled['cache']/'classes/local/pocketchat/inputdriver/NativePreEmitReadinessCli.class'
            original_class = changed_class.read_bytes()
            changed_class.write_bytes(original_class[:-1]+bytes([original_class[-1] ^ 1]))
            with self.assertRaises(self.adapter.HeaderReadinessFailure) as failure:
                self.adapter._compile_parser(root, binding, deadline)
            self.assertEqual(failure.exception.reason, 'cache-unverified')
            changed_class.write_bytes(original_class)
            manifest = compiled['cache']/'manifest.json'
            original_manifest = manifest.read_bytes()
            changed_manifest = json.loads(original_manifest)
            changed_manifest['binding']['sourceCommit'] = '0' * 40
            manifest.write_text(json.dumps(changed_manifest))
            with self.assertRaises(self.adapter.HeaderReadinessFailure) as failure:
                self.adapter._compile_parser(root, binding, deadline)
            self.assertEqual(failure.exception.reason, 'cache-unverified')
            manifest.write_bytes(original_manifest)

            cli = root/self.adapter.CLI
            original_cli = cli.read_bytes()
            cli.write_bytes(original_cli+b'\n// Controlled dirty fixture mutation\n')
            with self.assertRaises(self.adapter.HeaderReadinessFailure) as failure:
                self.adapter._source_bindings(root, source, identity, deadline)
            self.assertEqual(failure.exception.reason, 'source-unverified')
            cli.write_bytes(original_cli)
            dirty = root/'unexpected-fixture-file.txt'
            dirty.write_text('Controlled untracked file\n')
            with self.assertRaises(self.adapter.HeaderReadinessFailure) as failure:
                self.adapter._source_bindings(root, source, identity, deadline)
            self.assertEqual(failure.exception.reason, 'source-unverified')
            dirty.unlink()
            self.assertEqual(self.adapter._source_bindings(root, source, identity, deadline), binding)
            git('commit', '--quiet', '--no-verify', '--allow-empty', '-m', 'Synthetic different HEAD')
            self.assertNotEqual(git('rev-parse', 'HEAD'), source)
            with self.assertRaises(self.adapter.HeaderReadinessFailure) as failure:
                self.adapter._source_bindings(root, source, identity, deadline)
            self.assertEqual(failure.exception.reason, 'source-unverified')


class ChromeIdentityBatchTest(unittest.TestCase):
    """Actual generated POSIX shell, with explicit host command/process edges."""
    @classmethod
    def setUpClass(cls):
        directory = str(ROOT/'tools/gecko')
        sys.path.insert(0, directory)
        try:
            spec = importlib.util.spec_from_file_location(
                'chrome_identity_batch_under_test', ROOT/'tools/gecko/chrome_header_readiness.py')
            cls.adapter = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(cls.adapter)
        finally:
            sys.path.remove(directory)

    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix='identity-raw-shell-host-')
        self.addCleanup(self.temporary.cleanup)
        self.out = Path(self.temporary.name)
        self.bin = self.out/'bin'; self.bin.mkdir()
        self.journal = self.out/'commands.jsonl'
        self.config_path = self.out/'boundary.json'
        self.apk = self.out/'synthetic-apk-bytes'
        self.apk.write_bytes(b'Explicit host-only APK hash boundary, not an Android APK.')
        sdk = self.adapter.verify_installed.__globals__['_sdk']
        source = subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip()
        tree = subprocess.check_output(['git','rev-parse','HEAD^{tree}'],cwd=ROOT,text=True).strip()
        manifest, manifest_sha = sdk.selected_manifest(source)
        receipt = dict(manifest,sourceCommit=source,sourceTree=tree,runId='42',runAttempt='1',sdkManifestSha256=manifest_sha)
        asset = sdk.identity_from_receipt(json.dumps(receipt).encode(),manifest,manifest_sha,source,tree)
        self.identity = dict(schema=1,package='local.pocketchat.test',sourceCommit=source,sourceTree=tree,
            dirtySource=False,version='2.1.1',versionCode=103,sdkCoordinate=sdk.SDK_COORDINATE,
            apkSha256=hashlib.sha256(self.apk.read_bytes()).hexdigest(),apkBytes=self.apk.stat().st_size,
            buildStampSha256='f'*64,sdkBuildIdentity=asset)
        self.stat = ('4914 (owned fixture) '+' '.join(['S']+['0']*18+['12120']+['0']*4)+'\n').encode()
        self.values = [b'4914\n',self.stat,b'Name:\tfixture\nUid:\t10209\t10209\t10209\t10209\n',
                       b'local.pocketchat.test\0--controlled\0',self.stat,
                       b'package:com.android.systemui uid:10181\n',
                       b'package:local.pocketchat.test uid:10209\n',json.dumps(self.identity).encode()]
        self.commands = [['pidof','local.pocketchat.test'],
                         ['cat','/proc/4914/stat'],['cat','/proc/4914/status'],
                         ['cat','/proc/4914/cmdline'],['cat','/proc/4914/stat'],
                         ['pm','list','packages','-U','--user','0','com.android.systemui'],
                         ['pm','list','packages','-U','--user','0','local.pocketchat.test'],
                         ['content','read','--uri','content://local.pocketchat.test.evidence/build-identity']]
        self.config = dict(commands=self.commands,values=[base64.b64encode(v).decode() for v in self.values],
                           identity=self.identity,apk=str(self.apk),journal=str(self.journal))
        # Each original Android command is an explicit host boundary. The
        # adapter's actual shell script/frames, byte pipes, parser and installed
        # identity validator execute unmodified; no Android claim is made.
        boundary = self.bin/'boundary'
        boundary.write_text('#!'+sys.executable+'\n'+r'''
import base64,hashlib,json,os,pathlib,sys
config=json.loads(pathlib.Path(os.environ['IDENTITY_BOUNDARY_CONFIG']).read_text())
journal=pathlib.Path(config['journal'])
rows=journal.read_text().splitlines() if journal.exists() else []
index=len(rows)%8
command=[pathlib.Path(sys.argv[0]).name]+sys.argv[1:]
if command!=config['commands'][index]:
    raise SystemExit('Unexpected controlled command')
with journal.open('a') as output:output.write(json.dumps(command)+'\n')
if config.get('fault')==index:
    os.write(1,base64.b64decode(config.get('faultOutput','')))
    os.write(2,config.get('faultStderr','').encode())
    raise SystemExit(config.get('faultExit',0))
raw=base64.b64decode(config['values'][index])
if index==7:
    apk=pathlib.Path(config['apk']);identity=dict(config['identity'])
    identity.update(apkSha256=hashlib.sha256(apk.read_bytes()).hexdigest(),apkBytes=apk.stat().st_size)
    raw=json.dumps(identity).encode()
os.write(1,raw)
''')
        boundary.chmod(0o700)
        for name in ('pidof','cat','pm','content'):(self.bin/name).symlink_to(boundary.name)
        self.calls = []

    def invoke(self, deadline=None):
        deadline = time.monotonic()+10 if deadline is None else deadline
        self.config_path.write_text(json.dumps(self.config))
        real_checked = self.adapter._checked
        def transport(parts, actual_deadline, **kwargs):
            self.calls.append((parts,actual_deadline,dict(kwargs)))
            self.assertEqual(parts,['adb-host','-s','emulator-5554','shell','-T','sh','-s'])
            self.assertEqual(actual_deadline,deadline)
            self.assertEqual(set(kwargs),{'input_bytes','stdout_limit'})
            return real_checked(['/bin/sh','-s'],actual_deadline,**kwargs)
        with patch.dict(os.environ,PATH=str(self.bin)+os.pathsep+os.environ.get('PATH',''),
                        IDENTITY_BOUNDARY_CONFIG=str(self.config_path)),\
                patch.object(self.adapter,'_checked',side_effect=transport):
            return self.adapter._identity(['adb-host','-s','emulator-5554'],self.identity,deadline)

    def frames(self, values=None, token='1'*32, statuses=None):
        raw=b''
        for index,((name,_),value) in enumerate(zip(self.adapter.IDENTITY_FRAMES,values or self.values)):
            status=0 if statuses is None else statuses[index]
            raw+=(f'PCHR1 {token} {index} {name}\n'.encode()+value+
                  f'\nPCHR1 {token} {index} exit {status}\n'.encode())
        return raw

    def test_actual_shell_preserves_eight_ordered_reads_in_one_transport_per_fence(self):
        owner=self.invoke()
        self.assertEqual(owner,dict(pid='4914',uid=10209,startTicks='12120',systemUiUid=10181))
        self.assertEqual(len(self.calls),1)
        self.assertEqual([json.loads(v) for v in self.journal.read_text().splitlines()],self.commands)
        self.assertIn(b'"/proc/$identity_pid/cmdline"',self.calls[0][2]['input_bytes'])
        self.assertNotIn(b'input tap',self.calls[0][2]['input_bytes'])
        self.assertNotIn(b'input swipe',self.calls[0][2]['input_bytes'])
        self.assertEqual(self.invoke(),owner)
        self.assertEqual(len(self.calls),2)
        self.assertEqual([json.loads(v) for v in self.journal.read_text().splitlines()],self.commands*2)
        first_token=self.calls[0][2]['input_bytes'].split(b'PCHR1 ')[1][:32]
        second_token=self.calls[1][2]['input_bytes'].split(b'PCHR1 ')[1][:32]
        self.assertNotEqual(first_token,second_token)

    def test_actual_provider_hash_is_fresh_at_every_identity_fence(self):
        self.invoke()
        self.apk.write_bytes(self.apk.read_bytes()+b' changed')
        with self.assertRaises(self.adapter.HeaderReadinessFailure) as failed:self.invoke()
        self.assertEqual(failed.exception.reason,'identity-changed')
        self.assertEqual([json.loads(v) for v in self.journal.read_text().splitlines()],self.commands*2)
        self.assertEqual(len(self.calls),2)

    def test_every_native_command_exit_and_stderr_remains_fail_closed(self):
        for index in range(8):
            with self.subTest(index=index):
                self.journal.unlink(missing_ok=True)
                self.config.update(fault=index,faultOutput='',faultExit=7)
                with self.assertRaises(self.adapter.HeaderReadinessFailure) as failed:self.invoke()
                self.assertEqual(failed.exception.reason,'observation-failed')
                self.assertEqual(len(self.journal.read_text().splitlines()),index+1)
        self.journal.unlink();self.config.update(fault=7,faultExit=0,faultStderr='controlled error')
        with self.assertRaises(self.adapter.HeaderReadinessFailure) as failed:self.invoke()
        self.assertEqual(failed.exception.reason,'observation-failed')

    def test_framing_rejects_truncation_reorder_replay_extra_bytes_and_injected_markers(self):
        token='1'*32;raw=self.frames(token=token)
        self.assertEqual(self.adapter._identity_frames(raw,token),self.values)
        marker=f'PCHR1 {token}'.encode()
        corruptions=[raw[:-1],raw+b'x',b'x'+raw,raw.replace(marker,marker+b'x',1),
                     raw.replace(b' 1 first-stat\n',b' 2 first-stat\n',1),
                     raw.replace(b' 3 cmdline\n',b' 3 status\n',1),
                     raw.replace(b' 7 exit 0\n',b' 7 exit 00\n'),
                     raw.replace(b' 7 exit 0\n',b' 7 exit 256\n'),
                     raw.replace(b' 7 exit 0\n',b' 7 exit true\n')]
        collision=copy.deepcopy(self.values);collision[2]+=b'\n'+marker+b' 2 exit 0\nSECRET'
        corruptions.append(self.frames(collision))
        for changed in corruptions:
            with self.subTest(sha256=hashlib.sha256(changed).hexdigest()):
                with self.assertRaises(self.adapter.HeaderReadinessFailure):self.adapter._identity_frames(changed,token)
        for index,(_,maximum) in enumerate(self.adapter.IDENTITY_FRAMES):
            values=list(self.values);values[index]=b'1'*(maximum+1)
            with self.subTest(overlong=index),self.assertRaises(self.adapter.HeaderReadinessFailure) as failed:
                self.adapter._identity_frames(self.frames(values),token)
            self.assertEqual(failed.exception.reason,'output-too-large')

    def test_original_process_and_package_fences_reject_controlled_mutations(self):
        mutations=[
            (0,b'4914 4915\n'),(0,b'0\n'),(0,b'04914\n'),
            (1,self.stat.replace(b'4914 (',b'4915 (')),
            (4,self.stat.replace(b'12120',b'12121')),
            (2,b'Uid:\t10209\t10209\t10210\t10209\n'),
            (2,b'Uid:\t999\t999\t999\t999\n'),
            (2,self.values[2]+self.values[2]),
            (3,b'other.application\0'),(5,b'package:com.android.systemui uid:10209\n'),
            (6,b'package:local.pocketchat.test uid:10210\n'),
            (6,self.values[6]*2)]
        for index,value in mutations:
            with self.subTest(index=index,value=repr(value)):
                self.journal.unlink(missing_ok=True)
                self.config.update(fault=index,faultOutput=base64.b64encode(value).decode(),faultExit=0)
                with self.assertRaises(self.adapter.HeaderReadinessFailure) as failed:self.invoke()
                self.assertEqual(failed.exception.reason,'identity-changed')

    def test_script_rejects_untrusted_tokens_and_package_quoting_inputs(self):
        for token in ('',None,'1'*31,'1'*33,'a'*31+';','a'*31+"'",'a'*31+'\n'):
            with self.subTest(token=token),self.assertRaises(self.adapter.HeaderReadinessFailure):
                self.adapter._identity_script(token)
        for package in ("local.test; touch /tmp/forbidden", "local.test'bad", 'local.test\nbad', 'local.test$(false)'):
            with self.subTest(package=package),patch.object(self.adapter,'PACKAGE',package),\
                    self.assertRaises(self.adapter.HeaderReadinessFailure):
                self.adapter._identity_script('1'*32)
        self.assertEqual(self.calls,[])

    def test_expired_original_deadline_never_launches_a_native_command(self):
        with self.assertRaises(self.adapter.HeaderReadinessFailure) as failed:self.invoke(time.monotonic()-1)
        self.assertEqual(failed.exception.reason,'deadline')
        self.assertFalse(self.journal.exists())
        self.assertEqual(len(self.calls),1)


if __name__ == '__main__':
    unittest.main()
