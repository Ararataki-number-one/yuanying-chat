"""Host diagnostics may observe recorder exit, but may never replace it."""
import ast
import copy
import hashlib
import importlib.util
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT/'tools/gecko/capture_glass_navigation.py'
sys.path.insert(0, str(SOURCE.parent))
SPEC = importlib.util.spec_from_file_location('recorder_capture', SOURCE)
CAPTURE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(CAPTURE)


class Clock:
    def __init__(self):
        self.value = 0.0

    def __call__(self):
        return self.value

    def advance(self, seconds):
        self.value += seconds


class Log:
    name = 'controlled-screenrecord.log'

    def __init__(self, raw=b'', hook=None):
        self.raw, self.hook, self.reads = raw, hook, 0

    def read_bytes(self):
        self.reads += 1
        if self.hook:
            self.hook(self)
        return self.raw


class Process:
    args = ['controlled-recorder']

    def __init__(self, clock, return_code=None, poll_hook=None, wait_hook=None):
        self.clock, self.returncode = clock, return_code
        self.poll_hook, self.wait_hook = poll_hook, wait_hook
        self.polls, self.waits = 0, []

    def poll(self):
        self.polls += 1
        if self.poll_hook:
            self.poll_hook(self)
        return self.returncode

    def wait(self, timeout):
        self.waits.append(timeout)
        self.clock.advance(timeout)
        if self.wait_hook:
            self.wait_hook(self)
        if self.returncode is None:
            raise subprocess.TimeoutExpired(self.args, timeout)
        return self.returncode


def actual_stop_consumer():
    """Compile the real stop statements without launching an Android fixture."""
    tree = ast.parse(SOURCE.read_text())
    motion = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == 'capture_motion')
    owners = [node for node in ast.walk(motion) if isinstance(node, ast.Try)
              and any(isinstance(row, ast.If) and ast.unparse(row.test) == "not signal_owned('INT')"
                      for row in node.body)]
    if len(owners) != 1:
        raise AssertionError('Exactly one actual owned-recorder stop consumer is required')
    body = owners[0].body
    start = next(i for i, row in enumerate(body) if isinstance(row, ast.If)
                 and ast.unparse(row.test) == "not signal_owned('INT')")
    end = next(i for i, row in enumerate(body) if isinstance(row, ast.If)
               and ast.unparse(row.test) == 'process.returncode != 0')
    function = ast.parse('def stop(process, log, motion, recorder_row, signal_owned):\n    pass\n').body[0]
    function.body = copy.deepcopy(body[start:end + 1])
    namespace = dict(vars(CAPTURE))
    module = ast.fix_missing_locations(ast.Module(body=[function], type_ignores=[]))
    exec(compile(module, str(SOURCE), 'exec'), namespace)
    return namespace['stop']


class RecorderExitObservationTest(unittest.TestCase):
    def observe(self, process, log):
        observation = {}
        with patch.object(CAPTURE.time, 'monotonic', process.clock):
            result = CAPTURE.wait_for_recorder_exit(process, log, 8, observation)
        return result, observation

    def assert_times_out(self, process, log):
        observation = {}
        with patch.object(CAPTURE.time, 'monotonic', process.clock):
            with self.assertRaises(subprocess.TimeoutExpired) as caught:
                CAPTURE.wait_for_recorder_exit(process, log, 8, observation)
        self.assertEqual(caught.exception.timeout, 8)
        self.assertEqual(observation['status'], 'timed-out')
        self.assertEqual(observation['deadlineMonotonic'], 8)
        self.assertFalse(observation['applicationAcceptance'])
        self.assertTrue(observation['diagnosticOnly'])
        return observation

    def test_real_file_backed_child_exit_and_exact_incremental_bytes_are_observed(self):
        with tempfile.TemporaryDirectory() as temporary:
            log = Path(temporary)/'controlled-screenrecord.log'
            code = "import time; print('encoding frames',flush=True); time.sleep(.15); print('muxer finalized',flush=True)"
            with log.open('wb') as output:
                process = subprocess.Popen([sys.executable, '-c', code], stdout=output, stderr=output)
                try:
                    observation = {}
                    self.assertEqual(CAPTURE.wait_for_recorder_exit(process, log, 8, observation), 0)
                finally:
                    if process.poll() is None:
                        process.terminate()
                    process.wait(timeout=3)
            self.assertEqual(observation['status'], 'exited')
            self.assertEqual(observation['returnCode'], 0)
            self.assertTrue(observation['diagnosticOnly'])
            self.assertFalse(observation['applicationAcceptance'])
            self.assertLess(observation['completedAtMonotonic'], observation['deadlineMonotonic'])
            rows = observation['observations']
            self.assertTrue(rows[0]['initialSnapshot'])
            self.assertEqual(b''.join(bytes.fromhex(row['newBytesHex']) for row in rows), log.read_bytes())
            for row in rows:
                raw = bytes.fromhex(row['newBytesHex'])
                self.assertEqual(row['newBytesSha256'], hashlib.sha256(raw).hexdigest())
                self.assertEqual(row['byteEnd'] - row['byteStart'], len(raw))

    def test_output_completion_words_never_substitute_for_process_exit(self):
        clock = Clock()
        observation = self.assert_times_out(Process(clock), Log(b'Broadcast completed\nMP4 finalized\n'))
        self.assertEqual(clock.value, 8)
        self.assertNotIn('returnCode', observation)
        self.assertIn('MP4 finalized', observation['observations'][0]['text'])

    def test_zero_exit_observed_at_deadline_is_still_late(self):
        clock = Clock()
        process = Process(clock, return_code=0, poll_hook=lambda _: clock.advance(8))
        observation = self.assert_times_out(process, Log())
        self.assertEqual(observation['observations'][0]['returnCode'], 0)
        self.assertEqual(process.waits, [])

    def test_slow_log_read_does_not_extend_exit_budget(self):
        clock = Clock()
        process = Process(clock, return_code=0)
        self.assert_times_out(process, Log(hook=lambda _: clock.advance(8)))
        self.assertEqual(clock.value, 8)
        self.assertEqual(process.waits, [])

    def test_continuous_output_does_not_reset_deadline(self):
        clock, log = Clock(), Log(b'initial\n')
        process = Process(clock, wait_hook=lambda _: setattr(log, 'raw', log.raw + b'phase\n'))
        observation = self.assert_times_out(process, log)
        self.assertEqual(clock.value, 8)
        self.assertAlmostEqual(sum(process.waits), 8)
        self.assertTrue(all(0 < wait <= .1 for wait in process.waits))
        self.assertGreater(len(observation['observations']), 2)

    def test_shrinking_log_is_diagnostic_and_actual_exit_is_still_required(self):
        clock, log = Clock(), Log(b'original bytes')

        def advance(process):
            log.raw = b'x'
            if len(process.waits) == 2:
                process.returncode = 0

        process = Process(clock, wait_hook=advance)
        result, observation = self.observe(process, log)
        self.assertEqual(result, 0)
        self.assertEqual(len(process.waits), 2)
        self.assertEqual(observation['status'], 'exited')
        self.assertTrue(observation['logReadErrors'])
        self.assertEqual(observation['logReadErrors'][0]['errorType'], 'ValueError')
        self.assertEqual(observation['observations'][1]['returnCode'], None)

    def test_read_failure_does_not_turn_pending_process_into_success(self):
        def unreadable(_):
            raise PermissionError('controlled unreadable log')

        for exit_code in (None, 0):
            with self.subTest(exit_code=exit_code):
                clock = Clock()
                process, log = Process(clock, return_code=exit_code), Log(hook=unreadable)
                if exit_code is None:
                    observation = self.assert_times_out(process, log)
                    self.assertEqual(clock.value, 8)
                else:
                    result, observation = self.observe(process, log)
                    self.assertEqual(result, 0)
                    self.assertEqual(observation['status'], 'exited')
                self.assertEqual(observation['logReadErrors'][0]['errorType'], 'PermissionError')

    def test_actual_stop_consumer_preserves_owned_int_and_nonzero_exit_failure(self):
        stop = actual_stop_consumer()
        for exit_code in (0, 7):
            with self.subTest(exit_code=exit_code):
                clock, signals, motion, row = Clock(), [], {}, {}
                process = Process(clock, return_code=exit_code)

                def owned(value):
                    signals.append(value)
                    return True

                with patch.object(CAPTURE.time, 'monotonic', clock):
                    if exit_code:
                        with self.assertRaisesRegex(RuntimeError, 'Screenrecord exited with code 7'):
                            stop(process, Log(), motion, row, owned)
                    else:
                        stop(process, Log(), motion, row, owned)
                self.assertEqual(signals, ['INT'])
                self.assertEqual(motion['recorderExitObservation']['status'], 'exited')
                self.assertEqual(motion['recorderExitObservation']['timeoutSeconds'], 8)
                self.assertEqual(row['exitCode'], exit_code)
                self.assertEqual(motion['recorderStoppedAtUnixNs'], row['completedAtUnixNs'])

    def test_actual_stop_consumer_rejects_pending_late_and_unowned_recorders(self):
        stop = actual_stop_consumer()
        for case in ('pending', 'late-zero', 'unowned'):
            with self.subTest(case=case):
                clock, signals, motion, row = Clock(), [], {}, {}
                process = Process(clock, return_code=0 if case == 'late-zero' else None,
                                  poll_hook=(lambda _: clock.advance(8)) if case == 'late-zero' else None)

                def owned(value):
                    signals.append(value)
                    return case != 'unowned'

                with patch.object(CAPTURE.time, 'monotonic', clock):
                    with self.assertRaises(RuntimeError if case == 'unowned' else subprocess.TimeoutExpired):
                        stop(process, Log(b'MP4 ready\n'), motion, row, owned)
                self.assertEqual(signals, ['INT'])
                self.assertEqual(row, {})
                self.assertNotIn('recorderStoppedAtUnixNs', motion)
                if case == 'unowned':
                    self.assertNotIn('recorderExitObservation', motion)
                    self.assertEqual(process.polls, 0)
                else:
                    self.assertEqual(motion['recorderExitObservation']['status'], 'timed-out')


if __name__ == '__main__':
    unittest.main()
