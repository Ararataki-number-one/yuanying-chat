#!/usr/bin/env python3
"""Execute the actual runner cleanup helper with controlled local ADB responses.

No Android process, installed APK, Keystore operation or device is exercised.
"""
import hashlib
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
HELPER = ROOT / 'tests/gecko/source_route_cleanup.py'
spec = importlib.util.spec_from_file_location('source_route_cleanup_under_test', HELPER)
cleanup = importlib.util.module_from_spec(spec)
spec.loader.exec_module(cleanup)
SOURCE, NONCE, SHA = 'a' * 40, 'b' * 32, 'c' * 64
IDENTITY = dict(package=cleanup.PACKAGE, sourceCommit=SOURCE, apkSha256=SHA,
                sourceTree='d' * 40, schema=1, dirtySource=False, apkBytes=123)


def event(**changes):
    value = dict(sourceCommit=SOURCE, runNonce=NONCE, package=cleanup.PACKAGE,
                 pid=431, uid=10123, buildIdentity=dict(IDENTITY))
    value.update(changes)
    return ('10-24 12:00:00.123   431   432 I PocketNetworkSourceRoute: '
            + json.dumps(dict(kind='invocation', value=value), separators=(',', ':')) + '\n').encode()


def stat(pid, ticks):
    # State is field 3, starttime field 22; comm may contain spaces and ')'.
    return (str(pid) + ' (worker ) main) S ' + ' '.join(['0'] * 18 + [str(ticks)] + ['0'] * 3) + '\n').encode()


class Device:
    def __init__(self):
        self.serial = 'emulator-5554'
        self.path = '/data/app/~~controlled/test/base.apk'
        self.sha, self.uid, self.pid, self.ticks = SHA, 10123, 431, 90001
        self.cmdline = cleanup.PACKAGE.encode() + b'\0'
        self.calls, self.timeline = [], []
        self.alive, self.old_pid_readable = True, False
        self.stop_failed, self.stop_leaves_alive, self.proc_denied = False, False, False
        self.pid_still_listed, self.process_list_invalid = False, False
        self.change_ticks_after_read, self.stat_reads = False, 0

    def run(self, command, **kwargs):
        self.calls.append(command)
        assert command[:3] == ['controlled-adb', '-s', 'emulator-5554']
        assert kwargs == dict(capture_output=True, timeout=30, check=False)
        parts, rc, out, err = command[3:], 0, b'', b''
        if parts == ['get-serialno']:
            out = (self.serial + '\n').encode()
        elif parts == ['shell', 'pm', 'path', cleanup.PACKAGE]:
            out = ('package:' + self.path + '\n').encode()
        elif parts == ['shell', 'sha256sum', self.path]:
            out = (self.sha + '  ' + self.path + '\n').encode()
        elif parts == ['shell', 'cmd', 'package', 'list', 'packages', '-U', cleanup.PACKAGE]:
            out = ('package:' + cleanup.PACKAGE + ' uid:' + str(self.uid) + '\n').encode()
        elif parts == ['shell', 'pidof', cleanup.PACKAGE]:
            out, rc = ((str(self.pid) + '\n').encode(), 0) if self.alive else (b'', 1)
        elif parts == ['shell', 'ps', '-A', '-o', 'PID']:
            out = b'PID\n1\n100\n'
            if self.alive or self.pid_still_listed:
                out += (str(self.pid) + '\n').encode()
            if self.process_list_invalid:
                out = b'PID\n<unavailable>\n'
        elif parts[:2] in (['shell', 'cat'], ['exec-out', 'cat']):
            if not self.alive and not self.old_pid_readable or self.proc_denied:
                rc, err = 1, b'cat: unavailable\n'
            elif parts[-1].endswith('/stat'):
                out = stat(self.pid, self.ticks)
                self.stat_reads += 1
                if self.change_ticks_after_read and self.stat_reads == 1:
                    self.ticks += 1
            elif parts[-1].endswith('/status'):
                out = ('Name:\tcontrolled\nUid:\t' + '\t'.join([str(self.uid)] * 4) + '\n').encode()
            elif parts[-1].endswith('/cmdline'):
                out = self.cmdline
            else:
                raise AssertionError(parts)
        elif parts == ['shell', 'am', 'force-stop', cleanup.PACKAGE]:
            self.timeline.append('force-stop')
            if self.stop_failed:
                rc, err = 1, b'force-stop denied\n'
            elif not self.stop_leaves_alive:
                self.alive = False
        else:
            raise AssertionError(parts)
        return subprocess.CompletedProcess(command, rc, out, err)

    def stops(self):
        return [call for call in self.calls if call[3:6] == ['shell', 'am', 'force-stop']]


class CleanupContract(unittest.TestCase):
    def setUp(self):
        self.device = Device()
        self.fence = cleanup.RouteCleanupFence('controlled-adb', 'emulator-5554',
                                              SOURCE, NONCE, IDENTITY, run=self.device.run)
        self.fence.preflight()

    def own(self):
        self.fence.poll(event())
        self.assertIsNotNone(self.fence.owner)

    def finish(self, raw=None, saved=True):
        def snapshot():
            self.device.timeline.append('final-raw-saved')
            return event() if raw is None else raw
        return self.fence.cleanup(snapshot, saved)

    def unknown(self, raw=None, saved=True):
        receipt = self.finish(raw, saved)
        self.assertEqual(receipt['status'], 'cleanupUnknown')
        self.assertEqual(self.device.stops(), [])
        self.assertFalse(receipt['originalPidGone'])
        self.assertFalse(receipt['fixtureResultChanged'])
        self.assertFalse(receipt['nativeOperationCancelled'])
        return receipt

    def test_actual_prelaunch_transport_apk_and_uid_are_required(self):
        self.assertEqual(self.fence.receipt['beforeLaunch'], dict(serial='emulator-5554',
            package=cleanup.PACKAGE, installedApkPath=self.device.path, apkSha256=SHA,
            sourceCommit=SOURCE, uid=10123))
        self.assertEqual(len(self.device.calls), 4)

    def test_wrong_actual_apk_hash_refuses_prelaunch_without_stop(self):
        self.device.sha = 'e' * 64
        candidate = cleanup.RouteCleanupFence('controlled-adb', 'emulator-5554',
                                             SOURCE, NONCE, IDENTITY, run=self.device.run)
        with self.assertRaises(cleanup.CleanupUnknown):
            candidate.preflight()
        self.assertIsNone(candidate.installation)
        self.assertEqual(self.device.stops(), [])

    def test_owned_failure_cleans_fixed_test_package_after_raw_and_confirms_pid_disappearance(self):
        self.own()
        receipt = self.finish()
        self.assertEqual(receipt['status'], 'cleaned')
        self.assertTrue(receipt['originalPidGone'])
        self.assertEqual(self.device.timeline, ['final-raw-saved', 'force-stop'])
        self.assertEqual(self.device.stops(), [['controlled-adb', '-s', 'emulator-5554',
                                               'shell', 'am', 'force-stop', cleanup.PACKAGE]])
        self.assertFalse(receipt['fixtureResultChanged'])
        self.assertFalse(receipt['nativeOperationCancelled'])

    def test_same_original_snapshot_in_many_polls_is_not_duplicate_invocation(self):
        self.own()
        for _ in range(4):
            self.fence.poll(event())
        self.assertEqual(self.finish()['status'], 'cleaned')

    def test_no_original_diagnostics_prevents_cleanup(self):
        self.own()
        self.unknown(saved=False)

    def test_no_first_owned_event_prevents_cleanup(self):
        self.fence.poll(b'10-24 unrelated startup\n')
        self.unknown()

    def test_missing_final_invocation_is_unknown(self):
        self.own()
        self.unknown(b'')

    def test_foreign_nonce_is_sticky_even_if_later_snapshot_looks_owned(self):
        self.own()
        self.fence.poll(event(runNonce='e' * 32))
        self.unknown()

    def test_foreign_source_is_sticky(self):
        self.own()
        self.fence.poll(event(sourceCommit='e' * 40))
        self.unknown()

    def test_new_invocation_with_same_nonce_is_not_accepted(self):
        self.own()
        self.unknown(event() + event())

    def test_final_new_nonce_is_not_stopped(self):
        self.own()
        self.unknown(event() + event(runNonce='e' * 32))

    def test_logcat_pid_must_equal_event_pid(self):
        self.fence.poll(event(pid=432))
        self.unknown()

    def test_event_uid_must_equal_package_uid(self):
        self.fence.poll(event(uid=10124))
        self.unknown()

    def test_formal_package_event_never_authorizes_stop(self):
        self.fence.poll(event(package='local.pocketchat'))
        self.unknown()

    def test_pid_reuse_with_new_startticks_is_not_stopped(self):
        self.own()
        self.device.ticks += 1
        self.unknown()

    def test_generation_change_during_first_uid_cmdline_read_is_rejected(self):
        self.device.change_ticks_after_read = True
        self.fence.poll(event())
        self.unknown()

    def test_android_cmdline_trailing_nul_padding_keeps_exact_test_name(self):
        self.device.cmdline += b'\0' * 40
        self.own()
        self.assertEqual(self.finish()['status'], 'cleaned')

    def test_main_pid_change_is_not_stopped(self):
        self.own()
        self.device.pid += 1
        self.unknown()

    def test_installed_uid_change_is_not_stopped(self):
        self.own()
        self.device.uid += 1
        self.unknown()

    def test_formal_process_cmdline_is_not_stopped(self):
        self.own()
        self.device.cmdline = b'local.pocketchat\0'
        self.unknown()

    def test_installed_apk_hash_change_is_not_stopped(self):
        self.own()
        self.device.sha = 'e' * 64
        self.unknown()

    def test_installed_path_change_is_not_stopped_even_when_hash_matches(self):
        self.own()
        self.device.path = '/data/app/~~new/test/base.apk'
        self.unknown()

    def test_transport_change_is_not_stopped(self):
        self.own()
        self.device.serial = 'emulator-5556'
        self.unknown()

    def test_invalid_raw_utf8_is_not_display_decoded_for_acceptance(self):
        self.own()
        self.unknown(b'noise\xff\n' + event())

    def test_unreadable_proc_cannot_authorize_stop(self):
        self.device.proc_denied = True
        self.fence.poll(event())
        self.unknown()

    def test_final_snapshot_failure_is_unknown_and_does_not_stop(self):
        self.own()
        def unavailable():
            raise OSError('raw logcat unavailable')
        receipt = self.fence.cleanup(unavailable, True)
        self.assertEqual(receipt['status'], 'cleanupUnknown')
        self.assertEqual(self.device.stops(), [])

    def test_force_stop_failure_is_unknown_and_never_retried(self):
        self.own()
        self.device.stop_failed = True
        receipt = self.finish()
        self.assertEqual(receipt['status'], 'cleanupUnknown')
        self.assertEqual(len(self.device.stops()), 1)
        self.assertFalse(receipt['originalPidGone'])

    def test_force_stop_return_zero_does_not_prove_process_exit(self):
        self.own()
        self.device.stop_leaves_alive = True
        receipt = self.finish()
        self.assertEqual(receipt['status'], 'cleanupUnknown')
        self.assertEqual(len(self.device.stops()), 1)
        self.assertFalse(receipt['originalPidGone'])

    def test_pidof_absence_without_original_proc_absence_is_unknown(self):
        self.own()
        self.device.old_pid_readable = True
        receipt = self.finish()
        self.assertEqual(receipt['status'], 'cleanupUnknown')
        self.assertFalse(receipt['originalPidGone'])

    def test_proc_read_failure_does_not_hide_pid_still_listed(self):
        self.own()
        self.device.pid_still_listed = True
        receipt = self.finish()
        self.assertEqual(receipt['status'], 'cleanupUnknown')
        self.assertFalse(receipt['originalPidGone'])

    def test_incomplete_process_list_does_not_prove_exit(self):
        self.own()
        self.device.process_list_invalid = True
        receipt = self.finish()
        self.assertEqual(receipt['status'], 'cleanupUnknown')
        self.assertFalse(receipt['originalPidGone'])

    def test_event_build_identity_must_equal_verified_actual_identity(self):
        self.fence.poll(event(buildIdentity=dict(IDENTITY, apkSha256='e' * 64)))
        self.unknown()

    def test_constructor_rejects_formal_package_identity(self):
        with self.assertRaises(cleanup.CleanupUnknown):
            cleanup.RouteCleanupFence('adb', 'emulator-5554', SOURCE, NONCE,
                                      dict(IDENTITY, package='local.pocketchat'))

    def test_proc_parser_uses_field22_after_complete_parenthesized_name(self):
        got = cleanup.process_identity(431, 10123, stat(431, 90001),
            b'Uid:\t10123\t10123\t10123\t10123\n', cleanup.PACKAGE.encode() + b'\0')
        self.assertEqual(got['startTicks'], 90001)

    def test_missing_zero_startticks_is_rejected(self):
        with self.assertRaises(cleanup.CleanupUnknown):
            cleanup.process_identity(431, 10123, stat(431, 0),
                b'Uid:\t10123\t10123\t10123\t10123\n', cleanup.PACKAGE.encode() + b'\0')


class ActualRunnerFailureContract(unittest.TestCase):
    """Actual main + actual cleanup helper; external ADB/server remain controlled."""
    def setUp(self):
        test_path = ROOT / 'tests/gecko_source_route_logcat_test.py'
        selected = importlib.util.spec_from_file_location('retained_source_route_logcat_cases', test_path)
        self.boundary = importlib.util.module_from_spec(selected)
        selected.loader.exec_module(self.boundary)
        self.tmp = tempfile.TemporaryDirectory(prefix='source-route-cleanup-main-')
        self.out = Path(self.tmp.name)
        self.boundary.RUNNER.OUT = self.out
        self.device = Device()
        self.identity = dict(IDENTITY, sourceCommit=self.boundary.COMMIT)
        self.fence = cleanup.RouteCleanupFence('controlled-adb', 'emulator-5554',
            self.boundary.COMMIT, self.boundary.NONCE, self.identity, run=self.device.run)
        self.fence.preflight()
        self.log = event(sourceCommit=self.boundary.COMMIT, runNonce=self.boundary.NONCE,
                         buildIdentity=self.identity) + b'FATAL EXCEPTION: original-business-failure\n'

    def tearDown(self):
        self.tmp.cleanup()

    def execute(self, scenario):
        scenario.cleanupFence = self.fence
        with self.assertRaises(AssertionError) as failure:
            scenario.execute()
        self.assertIn('FATAL EXCEPTION: original-business-failure', str(failure.exception))
        self.assertNotIn('"status": "passed"', scenario.stdout.getvalue())
        launches = [command for command, _ in scenario.run_calls
                    if command[3:7] == ['shell', 'am', 'start', '-W']]
        self.assertEqual(len(launches), 1)
        self.assertEqual((self.out / 'network-source-route-logcat-stdout.raw.log').read_bytes(), self.log)
        self.assertEqual((self.out / 'network-source-route-failure-logcat-stdout.raw.log').read_bytes(), self.log)
        self.assertEqual(json.loads((self.out / 'network-source-route-server-failure.json').read_text()),
                         {'server': 'must-survive'})
        return json.loads((self.out / 'network-source-route-cleanup.json').read_text())

    def test_original_main_failure_and_raw_survive_verified_cleanup(self):
        scenario = self.boundary.MainScenario(log=self.log)
        observed = {}
        test = self
        class ObservedNode(self.boundary.Node):
            def __init__(self, command, **kwargs):
                super().__init__(command, **kwargs)
                observed['server'] = Path(command[-1])
            def terminate(self):
                test.assertEqual((test.out / 'network-source-route-server-cleanup-after.json').read_bytes(),
                                 b'{"server":"must-survive","lateContacts":1}')
                super().terminate()
        original_run = self.device.run
        def stop_with_late_contacts(command, **kwargs):
            if command[3:] == ['shell', 'am', 'force-stop', cleanup.PACKAGE]:
                # The first failure copy must predate this controlled late IO.
                self.assertEqual((self.out / 'network-source-route-server-failure.json').read_bytes(),
                                 b'{"server":"must-survive"}')
                observed['server'].write_bytes(b'{"server":"must-survive","lateContacts":1}')
            return original_run(command, **kwargs)
        self.fence.run = stop_with_late_contacts
        with mock.patch.object(self.boundary, 'Node', ObservedNode):
            receipt = self.execute(scenario)
        self.assertEqual(receipt['status'], 'cleaned')
        self.assertTrue(receipt['runnerFailed'])
        self.assertTrue(receipt['originalPidGone'])
        self.assertEqual(len(self.device.stops()), 1)
        self.assertEqual((self.out / 'network-source-route-server-failure.json').read_bytes(),
                         b'{"server":"must-survive"}')
        after = (self.out / 'network-source-route-server-cleanup-after.json').read_bytes()
        self.assertEqual(after, b'{"server":"must-survive","lateContacts":1}')
        self.assertEqual(receipt['serverAfterCleanupSnapshot']['sha256'], hashlib.sha256(after).hexdigest())

    def test_failed_prelaunch_records_unknown_and_launches_or_stops_nothing(self):
        scenario = self.boundary.MainScenario(log=self.log)
        scenario.cleanupPreparationError = OSError('Selected source/APK identity unavailable')
        with self.assertRaises(OSError) as failure:
            scenario.execute()
        self.assertIn('Selected source/APK identity unavailable', str(failure.exception))
        self.assertEqual(scenario.run_calls, [])
        receipt = json.loads((self.out / 'network-source-route-cleanup.json').read_text())
        self.assertEqual(receipt['stage'], 'prelaunch')
        self.assertEqual(receipt['status'], 'cleanupUnknown')
        self.assertFalse(receipt['forceStopAttempted'])

    def test_new_invocation_at_final_snapshot_never_stops_or_advances_original_main(self):
        boundary, log = self.boundary, self.log
        foreign = event(sourceCommit=boundary.COMMIT, runNonce='e' * 32,
                        buildIdentity=self.identity)
        class NewInvocation(boundary.MainScenario):
            def run(self, command, **kwargs):
                if command[3:5] == ['logcat', '-d'] and self.logs >= 2:
                    self.log = log + foreign
                return super().run(command, **kwargs)
        scenario = NewInvocation(log=log)
        receipt = self.execute(scenario)
        self.assertEqual(receipt['status'], 'cleanupUnknown')
        self.assertTrue(receipt['runnerFailed'])
        self.assertFalse(receipt['forceStopAttempted'])
        self.assertEqual(self.device.stops(), [])
        self.assertEqual((self.out / 'network-source-route-cleanup-logcat-stdout.raw.log').read_bytes(), log + foreign)


class RecordedResult(unittest.TextTestResult):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.rows = []

    def addSuccess(self, test):
        super().addSuccess(test)
        self.rows.append(dict(name=test.id(), passed=True))

    def addFailure(self, test, error):
        super().addFailure(test, error)
        self.rows.append(dict(name=test.id(), passed=False, error=self._exc_info_to_string(error, test)))

    def addError(self, test, error):
        super().addError(test, error)
        self.rows.append(dict(name=test.id(), passed=False, error=self._exc_info_to_string(error, test)))


if __name__ == '__main__':
    result = unittest.TextTestRunner(verbosity=2, resultclass=RecordedResult).run(
        unittest.defaultTestLoader.loadTestsFromModule(sys.modules[__name__]))
    out = ROOT / 'work/reservation-host/cleanup-contract-results.json'
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(dict(status='passed' if result.wasSuccessful() else 'failed',
        actualAndroidExecution=False, actualProcessStopped=False, nativeOperationCancelled=False,
        helperSha256=hashlib.sha256(HELPER.read_bytes()).hexdigest(),
        runnerSha256=hashlib.sha256((ROOT / 'tests/gecko/run_network_sources_route.py').read_bytes()).hexdigest(),
        retainedLogcatTestSha256=hashlib.sha256((ROOT / 'tests/gecko_source_route_logcat_test.py').read_bytes()).hexdigest(),
        testSha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        scope='Actual Python cleanup helper plus actual runner failure flow; controlled ADB/server replies, existing expected-build preflight adapter in three main controls; no device qualification',
        tests=result.rows), indent=2) + '\n')
    raise SystemExit(0 if result.wasSuccessful() else 1)
