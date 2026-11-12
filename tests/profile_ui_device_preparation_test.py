"""Current preparation behavior with declared adb/clock boundaries, not device acceptance."""
import importlib.util
import json
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('ui_device_preparation', ROOT / 'tools/gecko/prepare_ui_device.py')
preparation = importlib.util.module_from_spec(spec)
spec.loader.exec_module(preparation)
HOME = 'com.google.android.apps.nexuslauncher/com.google.android.apps.nexuslauncher.NexusLauncherActivity'
ACTIVITY = '  topResumedActivity=ActivityRecord{1 u0 ' + HOME + ' t1}\n'
WINDOW = '  mCurrentFocus=Window{2 u0 ' + HOME + '}\n'
# Exact current-focus field from b6 / run 43200807281 / attempt 1 / API 32,
# device-window-displays.txt before application installation. Other test state is synthetic.
CAPTURED_TRANSITION = '  mCurrentFocus=Window{b4c1f9e u0 ImmersiveModeConfirmation}\n'
ANR = '  mCurrentFocus=Window{cc68d45 u0 Application Not Responding: com.android.systemui}\n'


class Clock:
    def __init__(self): self.value = 0
    def now(self): return self.value
    def sleep(self, seconds): self.value += seconds


class Adb:
    def __init__(self, snapshots=None):
        self.snapshots = snapshots or [(HOME, ACTIVITY, WINDOW)]
        self.index = 0
        self.calls = []
        self.after = lambda parts: None
        self.failure = None
        self.qemu = '1'

    def run(self, argv, **options):
        self.calls.append((argv, options))
        if argv[:2] == ['git', 'rev-parse']:
            return subprocess.CompletedProcess(argv, 0, ('a' if argv[2] == 'HEAD' else 'b') * 40 + '\n', '')
        assert argv[:3] == ['adb', '-s', 'emulator-5554']
        parts = tuple(argv[3:])
        frame = self.snapshots[min(self.index, len(self.snapshots) - 1)]
        if parts == ('shell', 'getprop', 'ro.kernel.qemu'): out = self.qemu
        elif parts == ('shell', 'am', 'get-current-user'): out = '0'
        elif parts[:4] == ('shell', 'cmd', 'package', 'resolve-activity'): out = frame[0] + '\n'
        elif parts == ('shell', 'dumpsys', 'activity', 'activities'): out = frame[1]
        elif parts == ('shell', 'dumpsys', 'window', 'displays'):
            out = frame[2]
            self.index += 1
        elif parts == ('shell', 'input', 'keyevent', 'KEYCODE_HOME'): out = ''
        else: raise AssertionError('Unexpected device action: ' + repr(parts))
        self.after(parts)
        if self.failure and parts == self.failure[0]:
            return subprocess.CompletedProcess(argv, 1, self.failure[1], self.failure[2])
        return subprocess.CompletedProcess(argv, 0, out, '')


class PreparationTests(unittest.TestCase):
    def run_preparation(self, fake, clock=None, timeout=2):
        self.clock = clock or Clock()
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'record.json'
            with patch.object(preparation.subprocess, 'run', fake.run), \
                 patch.object(preparation.time, 'monotonic', self.clock.now), \
                 patch.object(preparation.time, 'sleep', self.clock.sleep):
                try:
                    return preparation.prepare('adb', 'emulator-5554', path, timeout)
                finally:
                    self.record = json.loads(path.read_text()) if path.exists() else None

    def test_two_actual_current_snapshots_after_one_home_are_required(self):
        fake = Adb()
        record = self.run_preparation(fake)
        self.assertEqual(record['status'], 'prepared')
        self.assertFalse(record['applicationAcceptance'])
        self.assertEqual(record['homeNavigations'], 1)
        self.assertEqual(fake.index, 3)  # Initial state cannot count as a post-HOME observation.
        self.assertEqual([c[0][-3:] for c in fake.calls if 'input' in c[0]], [['input', 'keyevent', 'KEYCODE_HOME']])
        self.assertTrue(all(c[1]['timeout'] <= 2 for c in fake.calls))

    def test_captured_api32_transition_cannot_pass_even_with_resumed_home(self):
        self.assertFalse(preparation.ready_observation(HOME, ACTIVITY, CAPTURED_TRANSITION)['ready'])
        with self.assertRaises(TimeoutError):
            self.run_preparation(Adb([(HOME, ACTIVITY, CAPTURED_TRANSITION)]), timeout=1)
        self.assertEqual(self.record['status'], 'failed')
        self.assertTrue(any(c.get('stdout') == CAPTURED_TRANSITION for c in self.record['commands']))

    def test_fallback_home_is_never_ready_and_never_navigated(self):
        home = 'com.android.settings/.FallbackHome'
        frame = (home, ACTIVITY.replace(HOME, 'com.android.settings/com.android.settings.FallbackHome'),
                 WINDOW.replace(HOME, 'com.android.settings/com.android.settings.FallbackHome'))
        fake = Adb([frame])
        with self.assertRaises(TimeoutError): self.run_preparation(fake, timeout=1)
        self.assertEqual(self.record['homeNavigations'], 0)

    def test_actual_anr_or_error_focus_fails_without_hiding_or_input(self):
        for focus in [ANR, ANR.replace('Not Responding', 'Error'), ANR.replace('Application Not Responding:', 'SYSTEM_ERROR')]:
            with self.subTest(focus=focus):
                fake = Adb([(HOME, ACTIVITY, focus)])
                with self.assertRaises(ValueError): self.run_preparation(fake)
                self.assertFalse(any('input' in c[0] for c in fake.calls))
                self.assertEqual(self.record['status'], 'failed')

    def test_historical_errors_and_activities_cannot_replace_current_fields(self):
        window = 'Last ANR: com.android.systemui\n' + WINDOW
        self.assertTrue(preparation.ready_observation(HOME, ACTIVITY, window)['ready'])
        self.assertFalse(preparation.ready_observation(HOME, 'lastResumedActivity=' + ACTIVITY, WINDOW)['ready'])
        self.assertFalse(preparation.ready_observation(HOME, ACTIVITY, 'mCurrentFocus=null\n')['ready'])
        for raw in [WINDOW + WINDOW, 'lastFocus=' + WINDOW, '']:
            with self.assertRaises(ValueError): preparation.current_focus(raw)

    def test_one_matching_sample_or_changed_window_does_not_pass(self):
        frames = [(HOME, ACTIVITY, WINDOW), (HOME, ACTIVITY, WINDOW),
                  (HOME, ACTIVITY, CAPTURED_TRANSITION), (HOME, ACTIVITY, WINDOW),
                  (HOME, ACTIVITY, WINDOW.replace('Window{2', 'Window{3')),
                  (HOME, ACTIVITY, WINDOW.replace('Window{2', 'Window{3'))]
        fake = Adb(frames)
        self.assertEqual(self.run_preparation(fake)['status'], 'prepared')
        self.assertEqual(fake.index, 6)

    def test_foreign_emulator_or_ambiguous_home_is_rejected(self):
        fake = Adb(); fake.qemu = '0'
        with self.assertRaises(ValueError): self.run_preparation(fake)
        self.assertFalse(any('input' in c[0] for c in fake.calls))
        for raw in ['', HOME + '\n' + HOME, 'ResolverActivity']:
            with self.assertRaises(ValueError): preparation.home_component(raw)

    def test_command_failure_retains_original_raw_streams(self):
        fake = Adb(); fake.failure = (('shell', 'dumpsys', 'window', 'displays'), 'original output', 'original error')
        with self.assertRaises(subprocess.CalledProcessError): self.run_preparation(fake)
        row = self.record['commands'][-1]
        self.assertEqual((row['stdout'], row['stderr'], row['exitCode']), ('original output', 'original error', 1))

    def test_late_successful_command_cannot_pass(self):
        clock = Clock(); fake = Adb()
        fake.after = lambda parts: setattr(clock, 'value', 3)
        with self.assertRaises(TimeoutError): self.run_preparation(fake, clock)
        self.assertEqual(self.record['status'], 'failed')

    def test_parser_time_is_inside_shared_budget(self):
        clock = Clock(); original = preparation.home_component
        def late(raw):
            value = original(raw); clock.value = 3; return value
        with patch.object(preparation, 'home_component', late):
            with self.assertRaises(TimeoutError): self.run_preparation(Adb(), clock)
        self.assertEqual(self.record['homeNavigations'], 0)

    def test_final_persistence_time_cannot_turn_timeout_into_prepared(self):
        clock = Clock(); original = Path.write_text
        def late(path, text, *args, **kwargs):
            if json.loads(text).get('status') == 'prepared': clock.value = 3
            return original(path, text, *args, **kwargs)
        with patch.object(Path, 'write_text', late):
            with self.assertRaises(TimeoutError): self.run_preparation(Adb(), clock)
        self.assertEqual(self.record['status'], 'failed')

    def test_workflow_keeps_existing_budgets_and_prepares_before_application(self):
        workflow = (ROOT / '.github/workflows/browser-workspace-validation.yml').read_text()
        call = 'python3 tools/gecko/prepare_ui_device.py '
        self.assertEqual(workflow.count(call), 1)
        self.assertLess(workflow.index('> work/glass-navigation/device-window-displays.txt'), workflow.index(call))
        self.assertLess(workflow.index(call), workflow.index('- name: Run real glass rendering'))
        self.assertIn('timeout-minutes: 12', workflow)
        self.assertIn('timeout-minutes: 30', workflow)
        self.assertIn('--timeout 45 --output work/glass-navigation/ui-device-preparation.json', workflow)
        self.assertIn('logcat -b all -d -v threadtime > work/glass-navigation/system-logcat.txt', workflow)


if __name__ == '__main__':
    unittest.main()
