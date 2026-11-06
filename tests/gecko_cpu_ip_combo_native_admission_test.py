"""Actual native snapshot collector at explicit synthetic byte/ADB boundaries.

These tests exercise the current Python collector and main cleanup ordering.
Packets and ADB are modeled; this is not Android or Gecko route execution.
"""
import copy
import hashlib
import json
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

import gecko_cpu_ip_combo_runner_test as previous
import gecko_cpu_ip_combo_evidence_test as modeled

runner = previous.runner
HASHES = {
    'remote-settings': '3a89382624c14be6f9b46ba27222e537fa59f5a36c63aacd6cd762965f1aff0d',
    'remote-settings-attachments': '329ef95339e0fd70cc2fa20c8ea4b30288dc5ad57c8c96dc860d4479a61c9b79',
}
CLOSED = dict(type='socks', host='127.0.0.1', port=9, proxyDNS=True, failoverTimeout=1)


def fixture(count=2):
    report, expected = modeled.fixture()
    identity = copy.deepcopy(expected)
    identity['scope'] = 'Installed synthetic integration APK bytes and embedded source stamp only'
    roles = tuple(HASHES)
    events = [dict(sequence=index + 1, role=roles[index % 2],
                   hostSha256=HASHES[roles[index % 2]], runtimeInstance=1234,
                   viewInstance=-5678, sessionId='' if index == 0 else 'sdk-session:1',
                   admissionPredicateObserved=True, closedRoute=True,
                   superRoute=copy.deepcopy(CLOSED)) for index in range(min(count, 128))]
    return dict(schema=1, kind='gecko-cpu-ip-combo-native-admission-v1',
                sourceCommit=modeled.SOURCE, sourceTree=expected['sourceTree'], runNonce=modeled.NONCE,
                buildIdentity=identity, process=copy.deepcopy(report['activity']['process']),
                scope='integration-only-exact-remote-settings-https-admission',
                automaticLatencyChecks=False, eventLimit=128, totalRefusals=count,
                droppedEvents=count - len(events), events=events,
                snapshotScope='persisted-async-snapshot-before-force-stop-later-events-not-covered',
                diagnosticOnly=True, qualificationEvidence=False), expected


def encode(value):
    # Visible whitespace/CRLF intentionally differs from any normal reserialization.
    return (json.dumps(value, ensure_ascii=False, indent=3) + '\r\n').encode('utf-8')


def installed(value, expected):
    # Existing real identity checker, with its declared synthetic source reader.
    return modeled.gate.ip.installed(value, expected, modeled.modeled.source_reader)


class NativeAdmissionTests(unittest.TestCase):
    def setUp(self):
        self.identity_check = patch.object(runner, 'verify_installed', installed)
        self.identity_check.start()
        self.addCleanup(self.identity_check.stop)

    def validate(self, value, expected=None):
        return runner.validate_native_admission(encode(value), modeled.SOURCE,
                                                modeled.NONCE, expected or fixture()[1])

    def reject(self, changes):
        for index, change in enumerate(changes):
            value, expected = fixture()
            change(value)
            with self.subTest(index=index), self.assertRaises((ValueError, KeyError, TypeError)):
                self.validate(value, expected)

    def adb(self, raw, calls):
        def read(*args, **kwargs):
            calls.append((args, kwargs))
            return subprocess.CompletedProcess(args, 0, stdout=raw, stderr=b'')
        return read

    def test_exact_identity_roles_and_routes_round_trip_without_mutation(self):
        value, expected = fixture()
        original = copy.deepcopy(value)
        self.assertEqual(runner.NATIVE_ADMISSION_HASHES, HASHES)
        self.assertEqual(self.validate(value, expected), original)
        self.assertEqual(value, original)
        self.assertFalse(value['qualificationEvidence'])
        self.assertFalse(value['automaticLatencyChecks'])

    def test_zero_events_and_bounded_overflow_are_observations_not_success(self):
        for count in (0, 1, 2, 128, 145):
            with self.subTest(count=count):
                value, expected = fixture(count)
                result = self.validate(value, expected)
                self.assertEqual(len(result['events']), min(128, count))
                self.assertEqual(result['droppedEvents'], max(0, count - 128))
                self.assertIs(result['qualificationEvidence'], False)
                self.assertNotIn('passed', result)

    def test_unobserved_predicate_and_failed_super_route_remain_raw_failure(self):
        value, expected = fixture()
        value['events'][0].update(admissionPredicateObserved=False, closedRoute=False, superRoute=None)
        before = copy.deepcopy(value)
        result = self.validate(value, expected)
        self.assertEqual(result, before)
        self.assertIs(result['events'][0]['admissionPredicateObserved'], False)
        self.assertIsNone(result['events'][0]['superRoute'])
        self.assertIs(result['events'][0]['closedRoute'], False)

    def test_capture_preserves_original_bytes_and_uses_one_bounded_provider_read(self):
        value, expected = fixture()
        raw = encode(value)
        calls = []
        with tempfile.TemporaryDirectory() as name:
            root = Path(name)
            result = runner.capture_native_admission(self.adb(raw, calls), root, modeled.SOURCE, modeled.NONCE, expected)
            saved = (root / runner.NATIVE_ADMISSION_NAME).read_bytes()
            self.assertEqual(result, value)
            self.assertEqual(saved, raw)
            self.assertEqual(hashlib.sha256(saved).digest(), hashlib.sha256(raw).digest())
            self.assertEqual([p.name for p in root.iterdir()], [runner.NATIVE_ADMISSION_NAME])
        self.assertEqual(calls, [(('exec-out', 'content', 'read', '--uri', runner.URI + '/admission'),
                                 dict(check=False, timeout=20))])

    def test_capture_invalid_or_missing_snapshot_creates_no_diagnostic_file(self):
        value, expected = fixture()
        bad_identity = copy.deepcopy(value)
        bad_identity['runNonce'] = 'f' * 32
        for raw in (b'', b'No result found.', b'Error while accessing provider: unavailable',
                    b'{}', b'\xff', encode(bad_identity)):
            with self.subTest(raw=raw[:30]), tempfile.TemporaryDirectory() as name:
                with self.assertRaises((ValueError, UnicodeError)):
                    runner.capture_native_admission(self.adb(raw, []), Path(name), modeled.SOURCE, modeled.NONCE, expected)
                self.assertEqual(list(Path(name).iterdir()), [])

    def test_capture_never_overwrites_existing_file_or_follows_symlink(self):
        value, expected = fixture()
        for symlink in (False, True):
            with self.subTest(symlink=symlink), tempfile.TemporaryDirectory() as name:
                root = Path(name)
                target = root / runner.NATIVE_ADMISSION_NAME
                outside = root / 'unchanged.txt'
                outside.write_bytes(b'UNCHANGED')
                if symlink:
                    target.symlink_to(outside)
                else:
                    target.write_bytes(b'EXISTING')
                with self.assertRaises(OSError):
                    runner.capture_native_admission(self.adb(encode(value), []), root, modeled.SOURCE, modeled.NONCE, expected)
                self.assertEqual(outside.read_bytes(), b'UNCHANGED')
                self.assertEqual(target.read_bytes(), b'UNCHANGED' if symlink else b'EXISTING')

    def test_json_is_strict_before_identity_or_foreign_nonce_filtering(self):
        value, expected = fixture()
        raw = json.dumps(value).encode()
        invalid = [b'', b'\xff', b'[]', b'null', b'{"x":NaN}', b'{"x":Infinity}',
                   raw + b'trailing', b' ' * 262145, raw.decode(), bytearray(raw)]
        for first, last in ((modeled.NONCE, 'f' * 32), ('f' * 32, modeled.NONCE)):
            duplicate = copy.deepcopy(value)
            duplicate['runNonce'] = first
            invalid.append(json.dumps(duplicate).encode()[:-1] + b',"runNonce":' + json.dumps(last).encode() + b'}')
        for item in invalid:
            with self.subTest(raw=str(item)[:40]), self.assertRaises((ValueError, UnicodeError)):
                runner.validate_native_admission(item, modeled.SOURCE, modeled.NONCE, expected)

    def test_missing_and_unknown_top_level_fields_are_rejected(self):
        value, _ = fixture()
        self.reject([lambda v, key=key: v.pop(key) for key in value] +
                    [lambda v: v.update(extra='unknown'), lambda v: v.update(rawUrl='https://secret.invalid/')])

    def test_invocation_scope_and_default_off_flags_are_exact(self):
        self.reject([
            lambda v: v.update(schema=True), lambda v: v.update(schema=1.0),
            lambda v: v.update(kind='other'), lambda v: v.update(sourceCommit='f' * 40),
            lambda v: v.update(sourceTree='f' * 40), lambda v: v.update(runNonce='f' * 32),
            lambda v: v.update(sourceCommit=True), lambda v: v.update(runNonce=1),
            lambda v: v.update(scope='production'), lambda v: v.update(snapshotScope='complete-all-events'),
            lambda v: v.update(automaticLatencyChecks=True), lambda v: v.update(automaticLatencyChecks=0),
            lambda v: v.update(diagnosticOnly=1), lambda v: v.update(diagnosticOnly=False),
            lambda v: v.update(qualificationEvidence=0), lambda v: v.update(qualificationEvidence=True),
        ])

    def test_installed_apk_source_sdk_and_every_expected_field_are_exact(self):
        value, expected = fixture()
        changes = [lambda v: v['buildIdentity'].update(scope='different scope'),
                   lambda v: v['buildIdentity'].update(extra='unknown')]
        for key in expected:
            changes.append(lambda v, key=key: v['buildIdentity'].pop(key))
            # Wrong type also rejects Python's otherwise equal True/1 and 1.0/1.
            replacement = True if type(expected[key]) is int else None
            changes.append(lambda v, key=key, replacement=replacement: v['buildIdentity'].__setitem__(key, replacement))
        changes.extend([
            lambda v: v['buildIdentity'].update(schema=True),
            lambda v: v['buildIdentity'].update(versionCode=float(expected['versionCode'])),
            lambda v: v['buildIdentity'].update(apkBytes=float(expected['apkBytes'])),
            lambda v: v['buildIdentity'].update(apkSha256='f' * 64),
            lambda v: v['buildIdentity']['sdkBuildIdentity'].update(runAttempt='2'),
            lambda v: v['buildIdentity']['sdkBuildIdentity'].update(runAttempt=1.0),
        ])
        self.reject(changes)

    def test_process_fields_and_typed_profile6_identity_are_exact(self):
        self.reject([
            lambda v: v['process'].pop('pid'), lambda v: v['process'].update(extra=1),
            lambda v: v['process'].update(pid=0), lambda v: v['process'].update(pid=True),
            lambda v: v['process'].update(pid=7711.0), lambda v: v['process'].update(uid=2000),
            lambda v: v['process'].update(uid=True), lambda v: v['process'].update(uid=10123.0),
            lambda v: v['process'].update(name='local.pocketchat.test'),
            lambda v: v['process'].update(name='local.pocketchat.test:profile1'),
        ])

    def test_counters_types_counts_order_and_cap_are_enforced(self):
        self.reject([
            lambda v: v.update(eventLimit=129), lambda v: v.update(eventLimit=128.0),
            lambda v: v.update(eventLimit=True), lambda v: v.update(totalRefusals=-1),
            lambda v: v.update(totalRefusals=2.0), lambda v: v.update(totalRefusals=True),
            lambda v: v.update(droppedEvents=True), lambda v: v.update(droppedEvents=0.0),
            lambda v: v.update(droppedEvents=1), lambda v: v.update(events={}),
            lambda v: v['events'].pop(), lambda v: v['events'].append(copy.deepcopy(v['events'][0])),
            lambda v: v['events'][0].update(sequence=2), lambda v: v['events'][0].update(sequence=True),
            lambda v: v['events'][0].update(sequence=1.0), lambda v: v['events'].reverse(),
        ])
        value, expected = fixture(129)
        value['events'].append(copy.deepcopy(value['events'][-1]))
        value['events'][-1]['sequence'] = 129
        value['droppedEvents'] = 0
        with self.assertRaises(ValueError):
            self.validate(value, expected)

    def test_event_fields_target_hashes_and_owner_types_cannot_expand_scope(self):
        value, _ = fixture()
        changes = [lambda v, key=key: v['events'][0].pop(key) for key in value['events'][0]]
        changes.extend([
            lambda v: v['events'][0].update(rawUrl='https://secret.invalid/'),
            lambda v: v['events'][0].update(role='other'),
            lambda v: v['events'][0].update(hostSha256='f' * 64),
            lambda v: v['events'][0].update(hostSha256=HASHES['remote-settings-attachments']),
            lambda v: v['events'][0].update(runtimeInstance=0),
            lambda v: v['events'][0].update(runtimeInstance=True),
            lambda v: v['events'][0].update(runtimeInstance=1234.0),
            lambda v: v['events'][0].update(viewInstance=0),
            lambda v: v['events'][0].update(viewInstance=False),
            lambda v: v['events'][0].update(viewInstance=-5678.0),
            lambda v: v['events'][0].update(sessionId='secret/path'),
            lambda v: v['events'][0].update(sessionId='x' * 161),
            lambda v: v['events'][0].update(sessionId=None),
            lambda v: v['events'][0].update(admissionPredicateObserved=1),
            lambda v: v['events'][0].update(admissionPredicateObserved=None),
            lambda v: v['events'][0].update(closedRoute=1),
        ])
        self.reject(changes)

    def test_actual_super_route_is_exact_original_five_key_typed_closed_route(self):
        changes = [lambda v, key=key: v['events'][0]['superRoute'].pop(key) for key in CLOSED]
        changes.extend([
            lambda v: v['events'][0]['superRoute'].update(extra='unknown'),
            lambda v: v['events'][0]['superRoute'].update(type='http'),
            lambda v: v['events'][0]['superRoute'].update(host='localhost'),
            lambda v: v['events'][0]['superRoute'].update(port=9.0),
            lambda v: v['events'][0]['superRoute'].update(port=True),
            lambda v: v['events'][0]['superRoute'].update(proxyDNS=1),
            lambda v: v['events'][0]['superRoute'].update(failoverTimeout=1.0),
            lambda v: v['events'][0].update(closedRoute=False),
            lambda v: v['events'][0].update(superRoute=None),
            lambda v: v['events'][0].update(superRoute={}),
        ])
        self.reject(changes)

    def execute_main_with_capture(self, where='passed', change=None, failure=None):
        boundary = previous.ComboRunnerTests()
        self.addCleanup(boundary.doCleanups)
        captures = []

        def capture(adb, directory, source, nonce, expected):
            captures.append((directory, source, nonce, copy.deepcopy(expected)))
            # Actual main's private ADB closure, captured by the existing explicit
            # modeled subprocess boundary. No Android result is asserted here.
            raw = adb('exec-out', 'content', 'read', '--uri', runner.URI + '/admission',
                      check=False, timeout=20).stdout
            result = runner.validate_native_admission(raw, source, nonce, expected)
            if failure:
                raise failure
            if change:
                change(result)
            return result

        with patch.object(runner, 'capture_native_admission', capture):
            result = boundary.execute_main(where)
        return result, captures

    def test_actual_main_captures_once_before_force_stop_clear_and_server_close(self):
        (report, actions, out, original, status, checks), captures = self.execute_main_with_capture()
        read = ('exec-out', 'content', 'read', '--uri', runner.URI + '/admission')
        self.assertEqual(actions.count(read), 1)
        capture_index = actions.index(read)
        self.assertLess(capture_index, actions.index(('shell', 'am', 'force-stop', 'local.pocketchat.test')))
        self.assertLess(capture_index, actions.index('scope-cleared'))
        self.assertLess(capture_index, actions.index('server-closed'))
        self.assertEqual(len(captures), 1)
        self.assertEqual(captures[0][1:3], (modeled.SOURCE, modeled.NONCE))
        self.assertEqual(status['status'], 'passed')
        self.assertEqual(len(checks), 1)
        self.assertEqual(set(report['casePins']), set(runner.RAW_FILES))
        self.assertEqual((out / runner.RAW_DIRECTORY / 'combo.json').read_bytes(), original)
        self.assertFalse(report.get('qualificationEvidence', False))

    def test_main_retains_original_device_failure_and_still_collects_before_cleanup(self):
        (report, actions, out, original, status, checks), captures = self.execute_main_with_capture('device-failed')
        self.assertEqual(status['status'], 'failed')
        self.assertEqual(report['activity']['status'], 'failed')
        self.assertEqual((out / runner.RAW_DIRECTORY / 'combo.json').read_bytes(), original)
        self.assertEqual(len(captures), 1)
        self.assertTrue(all(report['cleanup'].values()))
        self.assertEqual(checks, [])
        self.assertLess(actions.index(('exec-out', 'content', 'read', '--uri', runner.URI + '/admission')),
                        actions.index(('shell', 'am', 'force-stop', 'local.pocketchat.test')))

    def test_main_snapshot_failure_fails_command_without_rewriting_original_device_outcome(self):
        (report, actions, out, original, status, checks), captures = self.execute_main_with_capture(
            'checker', failure=ValueError('EXPLICIT MODELED SNAPSHOT FAILURE'))
        self.assertEqual(status['status'], 'failed')
        self.assertEqual(status['errorType'], 'ValueError')
        self.assertEqual(report['status'], 'passed')
        self.assertEqual(report['activity']['status'], 'passed')
        self.assertEqual((out / runner.RAW_DIRECTORY / 'combo.json').read_bytes(), original)
        self.assertEqual(checks, [])
        self.assertEqual(len(captures), 1)
        self.assertTrue(all(report['cleanup'].values()))

    def test_main_rejects_foreign_process_even_with_valid_snapshot_identity(self):
        for key, value in (('pid', 7712), ('uid', 10124), ('pid', 7711.0)):
            with self.subTest(key=key, value=value):
                (report, actions, out, original, status, checks), captures = self.execute_main_with_capture(
                    'checker', change=lambda result, key=key, value=value: result['process'].__setitem__(key, value))
                self.assertEqual(status['status'], 'failed')
                self.assertEqual(checks, [])
                self.assertEqual(report['activity']['process'], json.loads(original)['process'])
                self.assertEqual(report['status'], 'passed')
                self.assertEqual(len(captures), 1)
                self.assertTrue(all(report['cleanup'].values()))

    def test_main_unsafe_route_fails_after_preserving_original_snapshot_and_device_outcome(self):
        value, expected = fixture()
        value['events'][0].update(closedRoute=False, superRoute=None)
        raw = encode(value)
        boundary = previous.ComboRunnerTests()
        self.addCleanup(boundary.doCleanups)
        actual_capture = runner.capture_native_admission
        captures = []

        def capture(adb, directory, source, nonce, identity):
            self.assertEqual(identity, expected)
            captures.append(directory)

            def read(*args, **kwargs):
                # Only the provider bytes are modeled. Actual validation, exact
                # byte persistence and main's unsafe-route check all execute.
                result = adb(*args, **kwargs)
                return subprocess.CompletedProcess(result.args, result.returncode,
                                                   stdout=raw, stderr=result.stderr)

            return actual_capture(read, directory, source, nonce, identity)

        with patch.object(runner, 'capture_native_admission', capture):
            report, actions, out, original, status, checks = boundary.execute_main('checker')
        self.assertEqual(captures, [out])
        self.assertEqual((out / runner.NATIVE_ADMISSION_NAME).read_bytes(), raw)
        self.assertEqual(json.loads(raw)['events'][0]['superRoute'], None)
        self.assertEqual(status['status'], 'failed')
        self.assertEqual(status['errorType'], 'ValueError')
        self.assertEqual(checks, [], 'Unsafe admission fails before acceptance checker')
        self.assertEqual(report['status'], 'passed')
        self.assertEqual(report['activity']['status'], 'passed')
        self.assertEqual((out / runner.RAW_DIRECTORY / 'combo.json').read_bytes(), original)
        self.assertEqual(set(report['casePins']), set(runner.RAW_FILES))
        self.assertTrue(all(report['cleanup'].values()))
        self.assertLess(actions.index(('exec-out', 'content', 'read', '--uri', runner.URI + '/admission')),
                        actions.index(('shell', 'am', 'force-stop', 'local.pocketchat.test')))


if __name__ == '__main__':
    unittest.main()
