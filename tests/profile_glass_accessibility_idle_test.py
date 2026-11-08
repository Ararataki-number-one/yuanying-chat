"""Bounded read-only recovery of the actual API35 dump idle failure.

Run 42471139648/a1, API35 hierarchy attempt124 returned exit0, empty stdout,
and the exact 33-byte stderr below. Host transports model acquisition only;
they do not stand in for Android UI or animation acceptance.
"""
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools/gecko'))
import ui_visual_capture as capture

ACTUAL_IDLE_STDERR = b'ERROR: could not get idle state.\n'
XML = b'<?xml version="1.0"?><hierarchy rotation="0"><node package="local.pocketchat.test"/></hierarchy>'


class Clock:
    def __init__(self):
        self.seconds = 0.0

    def monotonic(self):
        return self.seconds

    def nanos(self):
        return int(self.seconds * 1e9)

    def sleep(self, seconds):
        self.seconds += seconds


class GlassAccessibilityIdle(unittest.TestCase):
    def run_capture(self, responses, *, deadline=30):
        clock, calls = Clock(), []
        with tempfile.TemporaryDirectory() as temporary:
            reader = capture.UiVisualCapture(adb='observed-adb', serial='emulator-5554',
                source='8abdce2ae93189a63603d28a49caaf00f689d536',
                diagnostics=Path(temporary) / 'attempts.json')

            def command(argv, **options):
                self.assertEqual(argv[:3], ['observed-adb', '-s', 'emulator-5554'])
                parts = argv[3:]
                self.assertIn(parts[:2], (['shell', 'uiautomator'], ['shell', 'cat']))
                self.assertLessEqual(options['timeout'], 30 - clock.seconds if deadline is not None else 90)
                calls.append((parts, options['timeout']))
                item = responses[min(len(calls) - 1, len(responses) - 1)]
                duration, code, stdout, stderr = item
                if duration > options['timeout']:
                    clock.sleep(options['timeout'])
                    raise subprocess.TimeoutExpired(argv, options['timeout'])
                clock.sleep(duration)
                if stdout == b'ACK':
                    stdout = ('UI hierchary dumped to: ' + parts[-1] + '\n').encode()
                return subprocess.CompletedProcess(argv, code, stdout=stdout, stderr=stderr)

            with patch.object(capture.subprocess, 'run', side_effect=command), \
                    patch.object(capture.time, 'monotonic', side_effect=clock.monotonic), \
                    patch.object(capture.time, 'monotonic_ns', side_effect=clock.nanos), \
                    patch.object(capture.time, 'time_ns', side_effect=clock.nanos), \
                    patch.object(capture.time, 'sleep', side_effect=clock.sleep):
                try:
                    value = reader.read(deadline=deadline)
                    error = None
                except Exception as caught:
                    value, error = None, caught
            return value, error, reader.report, calls, clock.seconds

    def test_actual_idle_failure_reacquires_only_a_fresh_hierarchy_within_same_deadline(self):
        value, error, report, calls, elapsed = self.run_capture([
            (11.745561894, 0, b'', ACTUAL_IDLE_STDERR),
            (1, 0, b'ACK', b''),
            (.1, 0, XML, b''),
        ])
        self.assertIsNone(error)
        self.assertEqual(value, XML.decode())
        self.assertEqual([row['status'] for row in report['attempts']], ['not-ready', 'captured'])
        self.assertEqual(report['attempts'][0]['commands'][0]['stderr']['bytes'], 33)
        self.assertEqual(report['attempts'][0]['commands'][0]['stderr']['text'], ACTUAL_IDLE_STDERR.decode())
        self.assertEqual({row['existingSceneDeadline'] for row in report['attempts']}, {30})
        self.assertNotEqual(report['attempts'][0]['remotePath'], report['attempts'][1]['remotePath'])
        self.assertEqual([parts[:2] for parts, _ in calls],
                         [['shell', 'uiautomator'], ['shell', 'uiautomator'], ['shell', 'cat']])
        self.assertEqual(calls[2][0][-1], report['attempts'][1]['remotePath'])
        self.assertLess(calls[1][1], calls[0][1])
        self.assertLess(elapsed, 30)

    def test_continuous_idle_failure_still_exhausts_original_deadline(self):
        value, error, report, calls, elapsed = self.run_capture([(11.745561894, 0, b'', ACTUAL_IDLE_STDERR)])
        self.assertIsNone(value)
        self.assertIsInstance(error, (TimeoutError, subprocess.TimeoutExpired))
        self.assertEqual(elapsed, 30)
        self.assertEqual(len(calls), 3)
        self.assertTrue(all(parts[:2] == ['shell', 'uiautomator'] for parts, _ in calls))
        self.assertEqual({row['existingSceneDeadline'] for row in report['attempts']}, {30})
        self.assertEqual(report['attempts'][-1]['status'], 'failed')

    def test_no_deadline_does_not_retry_an_idle_failure(self):
        value, error, report, calls, _ = self.run_capture([(1, 0, b'', ACTUAL_IDLE_STDERR)], deadline=None)
        self.assertIsNone(value)
        self.assertIsInstance(error, capture.CaptureNotReady)
        self.assertEqual(len(calls), 1)
        self.assertEqual(report['attempts'][0]['status'], 'not-ready')

    def test_other_failures_and_mixed_acknowledgements_are_not_hidden(self):
        for code, stdout, stderr in (
            (1, b'', ACTUAL_IDLE_STDERR),
            (2, b'', ACTUAL_IDLE_STDERR),
            (0, b'', b'ERROR: permission denied.\n'),
            (0, b'ACK', ACTUAL_IDLE_STDERR),
            (0, b'', ACTUAL_IDLE_STDERR + b'additional failure\n'),
        ):
            with self.subTest(code=code, stdout=stdout, stderr=stderr):
                value, error, report, calls, _ = self.run_capture([(1, code, stdout, stderr)])
                self.assertIsNone(value)
                self.assertIsInstance(error, (RuntimeError, subprocess.CalledProcessError))
                self.assertEqual(len(calls), 1)
                self.assertEqual(report['attempts'][0]['status'], 'failed')


if __name__ == '__main__':
    unittest.main()
