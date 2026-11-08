"""Drive the real v2 workload at controlled host boundaries, never on Android.

Only source/APK reads and the external device/emission boundaries are synthetic.
The real run(), HOME barrier, EventTransfer, case verifier and final independent
verifier execute. Passing these controls grants no Android or release qualification.
"""
import copy
import hashlib
import json
import pathlib
import subprocess
import sys
import tempfile
import types
import unittest
from contextlib import ExitStack
from unittest.mock import patch

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / 'tests'), str(ROOT / 'tests/gecko'), str(ROOT / 'tools/gecko')]

import profile_chrome_collapse_v2_test as packets
import run_chrome_collapse_v2 as driver
import chrome_collapse_contract_v2 as contract
import chrome_first_tap_readiness
import chrome_header_readiness
from integration_event_contract import EventTransfer, event_uri

SOURCE = packets.SOURCE
COMPONENT = packets.COMPONENT
HOME = 'controlled.launcher/controlled.launcher.Home'
PACKAGE = 'local.pocketchat.test'
ADB = '/controlled device/adb'
CLI = ['chrome-v2-driver-test', '--adb', ADB, '--serial', 'emulator-5554']
SIZES = ((360, 1), (412, 1), (360, 2))
NONCES = tuple(str(n) * 32 for n in (1, 2, 3))

# This independent protocol inventory must not shrink with the implementation.
INPUT_SPEC = (
    ('tap', 'addressOpen'), ('tap', 'addressCancel'), ('swipe', 'up'),
    ('swipe', 'down'), ('tap', 'compactAddressOpen'), ('tap', 'compactAddressCancel'),
    ('swipe', 'horizontal'), ('swipe', 'short'), ('swipe', 'upBeforeLongPress'),
    ('longpress', 'environmentMenu'), ('key', 'environmentMenuReturn'),
    ('tap', 'longPressAddressOpen'), ('tap', 'longPressAddressCancel'),
    ('tap', 'moreMenu'), ('key', 'moreReturn'), ('tap', 'environmentActivity'),
    ('key', 'environmentReturn'), ('swipe', 'upBeforeNetwork'), ('tap', 'network'),
    ('key', 'networkReturn'), ('tap', 'downloads'), ('key', 'downloadsReturn'),
    ('tap', 'reading'), ('tap', 'readingReturn'), ('swipe', 'upBeforeResume'),
    ('key', 'home'), ('activity-start', 'activityResume'),
    ('tap', 'resumeAddressOpen'), ('tap', 'resumeAddressCancel'), ('swipe', 'headerUp'),
)
SNAPSHOT_SPEC = (
    ('ready', 0), ('addressOpen', 1), ('initial', 2), ('up', 3), ('down', 4),
    ('compactAddressOpen', 5), ('compactReturn', 6), ('horizontal', 7),
    ('short', 8), ('upBeforeLongPress', 9), ('environmentMenu', 10),
    ('environmentMenuReturn', 11), ('longPressAddressOpen', 12),
    ('longPressReturn', 13), ('moreMenu', 14), ('moreReturn', 15),
    ('environmentReturn', 17), ('upBeforeNetwork', 18), ('network', 19),
    ('networkReturn', 20), ('downloads', 21), ('downloadsReturn', 22),
    ('reading', 23), ('readingReturn', 24), ('upBeforeResume', 25),
    ('activityResume', 27), ('resumeAddressOpen', 28), ('resumeReturn', 29),
    ('headerUp', 30),
)
CANCEL_PHASE = {'addressCancel': 'initial', 'compactAddressCancel': 'compactReturn',
                'longPressAddressCancel': 'longPressReturn', 'resumeAddressCancel': 'resumeReturn'}


class ControlledDevice:
    """A protocol peer: no matching input means no successful native transition."""

    def __init__(self, first_tap='emit'):
        self.first_tap_mode = first_tap
        self.now = 1.0
        self.commands = []
        self.emissions = []
        self.snapshots = []
        self.provider_reads = []
        self.captures = []
        self.first_tap_calls = []
        self.header_calls = []
        self.focus_calls = []
        self.source_reads = []
        self.sdk_source_reads = []
        self.build_reads = []
        self.final_verifications = []
        self.case_index = -1
        self.action_index = 0
        self.published = []
        self.payloads = {}
        self.component = COMPONENT
        self.native_phase = 'ready'
        self.cases = []
        for (width, scale), nonce in zip(SIZES, NONCES):
            case = packets.make_case(width, scale, nonce)
            # Three controlled documents make the real trace filter case-specific.
            for sample in case['observations'].values():
                sample['document'] = nonce
                sample['fixtureInputTelemetry']['document'] = nonce
            case['fixtureRequests'][0]['documentMarker'] = nonce
            packets.bind_events(case)
            assert [(a['kind'], a['label']) for a in case['actualAndroidInputs']] == list(INPUT_SPEC)
            self.cases.append(case)
        self.trace = [copy.deepcopy(case['fixtureRequests'][0]) for case in self.cases]

    @property
    def case(self):
        return self.cases[self.case_index]

    def clock(self):
        return self.now

    def sleep(self, duration):
        assert 0 < duration <= .2, duration
        self.now += duration

    def source_inputs(self, source):
        assert source == SOURCE
        self.source_reads.append(source)
        return {path: hashlib.sha256(packets.source_material(path)).hexdigest()
                for path in contract.INPUT_PATHS}

    def source_bytes(self, source, path):
        assert source == SOURCE and path in contract.INPUT_PATHS
        return packets.source_material(path)

    def expected_build(self, apk, source, tree, version, code):
        assert apk.name == 'ui-current.apk' and source == SOURCE and tree == 'b' * 40
        assert isinstance(version, str) and type(code) is int
        self.build_reads.append((apk.name, source, tree, version, code))
        return packets.identity()

    def git_output(self, args, **kwargs):
        manifest = 'third-party/sdk/geckoview-157.0.1-editable-selection.json'
        if args == ['git', 'show', SOURCE + ':' + manifest]:
            # The shared packet builder uses its explicit historical 1.7 APK
            # identity. Model only that synthetic source's missing manifest;
            # the real installed/SDK validators still decide whether it is legal.
            self.sdk_source_reads.append(manifest)
            raise subprocess.CalledProcessError(128, args, stderr=b'controlled historical manifest absent')
        assert args == ['git', 'rev-parse', 'HEAD^{tree}'] and kwargs['text'] is True
        return 'b' * 40 + '\n'

    def native_record(self):
        return self.case['nativeUiObservations'].get(self.native_phase, packets.native(()))

    def capture_factory(self, **kwargs):
        assert kwargs['adb'] == ADB and kwargs['serial'] == 'emulator-5554'
        assert kwargs['source'] == SOURCE and self.case['runNonce'] in kwargs['diagnostics'].name
        device = self

        class Capture:
            def read(self, *, deadline):
                assert device.now < deadline
                device.now += .01
                device.captures.append((device.case_index, device.native_phase))
                return device.native_record()['xml']
        return Capture()

    def expected_command(self, action):
        kind = action['kind']
        if kind == 'tap':
            return ('shell', 'input', 'tap', *map(str, action['point']))
        if kind in ('swipe', 'longpress'):
            start = action['from'] if kind == 'swipe' else action['point']
            end = action['to'] if kind == 'swipe' else action['point']
            return ('shell', 'input', 'swipe', *map(str, start), *map(str, end), str(action['durationMs']))
        if kind == 'key':
            return ('shell', 'input', 'keyevent', action['key'])
        assert kind == 'activity-start'
        return ('shell', 'am', 'start', '-W', '--activity-single-top', '-n', COMPONENT)

    def emit(self, parts):
        assert self.action_index < len(INPUT_SPEC), ('extra input', parts)
        expected = self.case['actualAndroidInputs'][self.action_index]
        assert parts == self.expected_command(expected), ('actual input target/order', expected['label'], parts)
        self.emissions.append((self.case_index, expected['kind'], expected['label'], parts))
        self.action_index += 1
        label = expected['label']
        self.native_phase = CANCEL_PHASE.get(label, label)
        self.component = (HOME if label == 'home' else
                          PACKAGE + '/local.pocketchat.WindowHomeActivity' if label == 'environmentActivity'
                          else COMPONENT)

    def publish(self, phase):
        index = len(self.published)
        assert index < len(SNAPSHOT_SPEC), ('extra snapshot', phase)
        assert (phase, self.action_index) == SNAPSHOT_SPEC[index], ('snapshot before its real inputs', phase, self.action_index)
        row = self.case['eventTransfer']['events'][index]
        assert json.loads(row['rawUtf8'])['event']['result']['command'] == phase
        self.published.append(row)
        self.payloads[event_uri(row['receipt'])] = row['rawUtf8'].encode()
        self.snapshots.append((self.case_index, phase, self.action_index))

    def adb(self, *parts):
        parts = tuple(parts)
        self.now += .01
        self.commands.append((self.case_index, parts))
        if parts == ('exec-out', 'content', 'read', '--uri', 'content://' + PACKAGE + '.evidence/build-identity'):
            return json.dumps(packets.identity())
        if parts == ('shell', 'getprop', 'ro.build.version.sdk'):
            return '35\n'
        if parts == ('shell', 'am', 'force-stop', PACKAGE):
            if self.case_index >= 0:
                assert self.action_index == 30 and len(self.published) == 29
            self.case_index += 1
            assert self.case_index < 3
            self.action_index = 0
            self.published = []
            self.native_phase = 'ready'
            self.component = COMPONENT
            return ''
        if parts == ('logcat', '-c'):
            assert not self.published
            return ''
        if parts[:3] == ('shell', 'wm', 'size'):
            assert parts == ('shell', 'wm', 'size', str(self.case['viewport'] * 3) + 'x1920')
            return ''
        if parts == ('shell', 'wm', 'density', '480'):
            return ''
        if parts[:5] == ('shell', 'settings', 'put', 'system', 'font_scale'):
            assert parts[5:] == (str(self.case['fontScale']),)
            return ''
        if parts[:5] == ('shell', 'am', 'start', '-W', '-n'):
            assert parts == ('shell', 'am', 'start', '-W', '-n', COMPONENT, '--es', 'compactAction',
                             'collapseStart', '--es', 'eventNonce', self.case['runNonce'],
                             '--ei', 'chromeNavigationVersion', '2')
            self.publish('ready')
            return 'Status: ok\n'
        if parts[:3] == ('shell', 'input', 'tap') or parts[:3] == ('shell', 'input', 'swipe') or parts[:3] == ('shell', 'input', 'keyevent') or parts[:5] == ('shell', 'am', 'start', '-W', '--activity-single-top'):
            self.emit(parts)
            return ''
        if parts[:3] == ('shell', 'am', 'broadcast'):
            prefix = ('shell', 'am', 'broadcast', '-a', PACKAGE + '.CHROME_COLLAPSE', '-p', PACKAGE,
                      '--es', 'eventNonce', self.case['runNonce'], '--es', 'collapseCommand')
            assert parts[:-1] == prefix
            if parts[-1] == 'clear':
                assert self.case['actualAndroidInputs'][self.action_index]['kind'] == 'swipe'
            else:
                self.publish(parts[-1])
            return 'Broadcast completed: result=0\n'
        if parts == ('logcat', '-d', '-s', 'PocketGeckoIntegration:I', 'AndroidRuntime:E', '*:S'):
            return '\n'.join(json.dumps(row['receipt']) for row in self.published)
        if parts == ('shell', 'am', 'get-current-user'):
            return '0\n'
        if parts == ('shell', 'dumpsys', 'activity', 'activities'):
            return packets.activity(self.component)
        if parts == ('shell', 'dumpsys', 'input_method'):
            return self.native_record()['inputMethod']
        if parts == ('shell', 'dumpsys', 'window'):
            return self.native_record()['windowState']
        if parts == ('shell', 'cmd', 'package', 'resolve-activity', '--brief', '--user', '0',
                     '-a', 'android.intent.action.MAIN', '-c', 'android.intent.category.HOME'):
            return HOME + '\n'
        raise AssertionError(('unexpected external command', parts))

    def adb_bytes(self, *parts):
        assert parts[:4] == ('exec-out', 'content', 'read', '--uri') and len(parts) == 5
        uri = parts[4]
        assert uri in self.payloads, ('unpublished provider event', uri)
        self.provider_reads.append(uri)
        return self.payloads[uri]

    def subprocess_run(self, args, **kwargs):
        assert args[:3] == [ADB, '-s', 'emulator-5554']
        assert kwargs['check'] is True and kwargs['text'] is True
        assert kwargs['stdout'] == subprocess.PIPE and kwargs['stderr'] == subprocess.PIPE
        assert 0 < kwargs['timeout'] <= 20 and 'shell' not in kwargs
        return subprocess.CompletedProcess(args, 0, self.adb(*args[3:]), '')

    def first_tap(self, **kwargs):
        assert kwargs['argv'] == CLI[1:] and kwargs['source'] == SOURCE
        assert kwargs['identity'] == packets.identity() and kwargs['nonce'] == self.case['runNonce']
        point = list(kwargs['before']['compactTap'])
        self.first_tap_calls.append((self.case_index, point))
        if self.first_tap_mode != 'omit':
            emitted = [point[0] + 1, point[1]] if self.first_tap_mode == 'wrong-point' else point
            self.adb('shell', 'input', 'tap', *map(str, emitted))
        return {'point': point}

    def header(self, **kwargs):
        assert kwargs['argv'] == CLI[1:] and kwargs['source'] == SOURCE
        assert kwargs['identity'] == packets.identity() and kwargs['nonce'] == self.case['runNonce']
        self.header_calls.append((self.case_index, kwargs['start'], kwargs['end']))
        self.adb('shell', 'input', 'swipe', *map(str, kwargs['start']), *map(str, kwargs['end']), '320')
        return {'status': 'passed', 'gestureInvocations': 1}

    def focus(self, activity):
        assert activity == COMPONENT.split('/')[1]
        assert driver.current_resumed(self.adb('shell', 'dumpsys', 'activity', 'activities')) == {(0, COMPONENT)}
        assert self.action_index == 30 and len(self.published) == 29
        self.focus_calls.append(self.case_index)

    def verify_report(self, value, source, apk_sha):
        # Reopen all complete events in the unmodified independent validator.
        checked = contract.verify_auto_collapse_v2(value, source, apk_sha, source_reader=self.source_bytes)
        self.final_verifications.append(checked)
        return checked


class ChromeV2DriverBoundaryTests(unittest.TestCase):
    def run_driver(self, device, out):
        self.assertEqual(len(INPUT_SPEC), 30)
        self.assertEqual(len(SNAPSHOT_SPEC), 29)
        self.assertEqual(tuple(contract.INPUTS), INPUT_SPEC)
        self.assertEqual(tuple(contract.PHASES), tuple(phase for phase, _ in SNAPSHOT_SPEC))
        self.assertIs(driver.EventTransfer, EventTransfer)
        with ExitStack() as stack:
            stack.enter_context(patch.object(driver.sys, 'argv', CLI))
            stack.enter_context(patch.object(driver.time, 'monotonic', device.clock))
            stack.enter_context(patch.object(driver.time, 'sleep', device.sleep))
            stack.enter_context(patch.object(driver.subprocess, 'check_output', device.git_output))
            stack.enter_context(patch.object(driver.subprocess, 'run', device.subprocess_run))
            stack.enter_context(patch.object(driver, 'immutable_inputs', device.source_inputs))
            stack.enter_context(patch.object(driver, 'expected_build', device.expected_build))
            stack.enter_context(patch.object(driver, 'UiVisualCapture', device.capture_factory))
            stack.enter_context(patch.object(driver.uuid, 'uuid4', side_effect=[types.SimpleNamespace(hex=n) for n in NONCES]))
            stack.enter_context(patch.object(chrome_first_tap_readiness, 'first_tap_once', device.first_tap))
            stack.enter_context(patch.object(chrome_header_readiness, 'header_up_once', device.header))
            case_verify = stack.enter_context(patch.object(driver, 'verify_case', wraps=contract.verify_case))
            stack.enter_context(patch.object(driver, 'verify_auto_collapse_v2', device.verify_report))
            result = driver.run(device.adb, device.adb_bytes, SOURCE, device.trace, out, device.focus)
            self.assertEqual(case_verify.call_count, 3)
            return result

    def test_real_run_emits_the_complete_three_case_protocol_before_verified_passes(self):
        device = ControlledDevice()
        with tempfile.TemporaryDirectory(prefix='chrome-v2-driver-host-') as temporary:
            result = self.run_driver(device, pathlib.Path(temporary))
        self.assertEqual(device.case_index, 2)
        self.assertEqual(device.focus_calls, [0, 1, 2])
        self.assertEqual(len(device.build_reads), 1)
        self.assertEqual(device.source_reads, [SOURCE, SOURCE])
        self.assertTrue(device.sdk_source_reads)
        self.assertEqual(len(device.first_tap_calls), 3)
        self.assertEqual(len(device.header_calls), 3)
        self.assertEqual(device.final_verifications[0]['checks'], 48)
        self.assertEqual(len(device.final_verifications), 1)
        self.assertEqual(len(device.provider_reads), 87)
        self.assertEqual(len(set(device.provider_reads)), 87)
        for index, case in enumerate(result['cases']):
            self.assertEqual((case['viewport'], case['fontScale']), SIZES[index])
            self.assertEqual(case['runNonce'], NONCES[index])
            self.assertEqual([(a['kind'], a['label']) for a in case['actualAndroidInputs']], list(INPUT_SPEC))
            self.assertEqual([(kind, label) for owner, kind, label, _ in device.emissions if owner == index], list(INPUT_SPEC))
            self.assertEqual([(phase, after) for owner, phase, after in device.snapshots if owner == index], list(SNAPSHOT_SPEC))
            self.assertEqual(len(case['eventTransfer']['events']), 29)
            self.assertEqual(len(case['checks']), 16)
            self.assertFalse({'chat', 'settings', 'chatTap', 'settingsTap'} & {a['label'] for a in case['actualAndroidInputs']})
        commands = [parts for _, parts in device.commands]
        self.assertEqual(sum(p[:3] == ('shell', 'input', 'tap') for p in commands), 42)
        self.assertEqual(sum(p[:3] == ('shell', 'input', 'swipe') and p[-1] == '320' for p in commands), 24)
        self.assertEqual(sum(p[:3] == ('shell', 'input', 'swipe') and p[-1] == '750' for p in commands), 3)
        self.assertEqual(sum(p == ('shell', 'input', 'keyevent', 'KEYCODE_HOME') for p in commands), 3)
        self.assertEqual(sum(p == ('shell', 'input', 'keyevent', 'KEYCODE_BACK') for p in commands), 15)
        self.assertEqual(sum(p[:5] == ('shell', 'am', 'start', '-W', '-n') and p[-2:] == ('chromeNavigationVersion', '2') for p in commands), 3)
        self.assertEqual(sum(p == ('shell', 'am', 'start', '-W', '--activity-single-top', '-n', COMPONENT) for p in commands), 3)

    def assert_first_action_rejected_before_an_address_snapshot(self, device):
        self.assertEqual(device.snapshots, [(0, 'ready', 0)])
        self.assertEqual(len(device.provider_reads), 1)
        self.assertEqual(device.action_index, 0)
        self.assertEqual(device.final_verifications, [])
        self.assertFalse(any(parts[-2:] == ('collapseCommand', 'addressOpen') for _, parts in device.commands))

    def test_a_first_tap_emitter_that_does_not_emit_cannot_receive_a_dialog_packet(self):
        device = ControlledDevice(first_tap='omit')
        with tempfile.TemporaryDirectory(prefix='chrome-v2-no-tap-host-') as temporary:
            with self.assertRaisesRegex(TimeoutError, 'actual native window'):
                self.run_driver(device, pathlib.Path(temporary))
        self.assertEqual(device.emissions, [])
        self.assert_first_action_rejected_before_an_address_snapshot(device)

    def test_a_wrong_first_tap_is_rejected_at_the_device_boundary_before_a_snapshot(self):
        device = ControlledDevice(first_tap='wrong-point')
        with tempfile.TemporaryDirectory(prefix='chrome-v2-wrong-tap-host-') as temporary:
            with self.assertRaisesRegex(AssertionError, 'actual input target/order'):
                self.run_driver(device, pathlib.Path(temporary))
        self.assertEqual(device.emissions, [])
        self.assert_first_action_rejected_before_an_address_snapshot(device)


if __name__ == '__main__':
    unittest.main(verbosity=2)
