"""Host-only coverage for Chromium startup and owned-group retirement."""
import hashlib
import importlib.util
import io
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import tempfile
import time
import unittest
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location('chromium_process', ROOT/'tools/browser/chromium_process.py')
PROCESS = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(PROCESS)


class Clock:
    def __init__(self):
        self.value = 0.0

    def __call__(self):
        return self.value

    def advance(self, seconds):
        self.value += seconds


class PortFile:
    def __init__(self, raw=b'9222\n/devtools/browser/owned-child\n', present=True, read_hook=None):
        self.raw, self.present, self.read_hook = raw, present, read_hook

    def is_file(self):
        return self.present

    def open(self, mode):
        outer = self

        class Reader(io.BytesIO):
            def read(self, count):
                if outer.read_hook:
                    outer.read_hook()
                return super().read(count)

        return Reader(self.raw)


class PollProcess:
    def __init__(self, results=(None,), hook=None):
        self.results, self.hook, self.calls = list(results), hook, 0

    def poll(self):
        self.calls += 1
        if self.hook:
            self.hook(self.calls)
        return self.results[min(self.calls - 1, len(self.results) - 1)]


def is_live(pid):
    try:
        state = (Path('/proc')/str(pid)/'stat').read_bytes().rsplit(b')', 1)[1].split()[0]
        return state not in (b'Z', b'X')
    except FileNotFoundError:
        return False


def eventually(predicate, timeout=3):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if predicate():
            return
        time.sleep(.01)
    raise AssertionError('The controlled child did not reach its expected state')


class EndpointTest(unittest.TestCase):
    def endpoint(self, port=None, process=None, clock=None):
        clock = clock or Clock()
        receipt = {}
        value = PROCESS._endpoint(process or PollProcess(), port or PortFile(), receipt,
                                  clock=clock, sleep=clock.advance)
        return value, receipt

    def test_valid_endpoint_is_yielded_without_changing_address(self):
        endpoint, receipt = self.endpoint()
        self.assertEqual(endpoint, 'ws://127.0.0.1:9222/devtools/browser/owned-child')
        self.assertEqual(receipt['status'], 'endpoint-ready')
        self.assertEqual(receipt['startupElapsedMs'], 0)

    def test_malformed_ports_and_browser_paths_fail_closed(self):
        for raw in (b'', b'0\n/devtools/browser/id', b'65536\n/devtools/browser/id',
                    b'x\n/devtools/browser/id', b'9222', b'9222\n/devtools/page/id',
                    b'9222\n/devtools/browser/../x', b'9222\n/devtools/browser/'):
            with self.subTest(raw=raw), self.assertRaisesRegex(RuntimeError, 'invalid debugging endpoint'):
                self.endpoint(PortFile(raw))

    def test_launcher_exit_before_ready_is_failure(self):
        with self.assertRaisesRegex(RuntimeError, 'exited before'):
            self.endpoint(process=PollProcess((17,)))

    def test_launcher_exit_during_endpoint_read_is_failure(self):
        with self.assertRaisesRegex(RuntimeError, 'exited while'):
            self.endpoint(process=PollProcess((None, 0)))

    def test_missing_file_uses_one_twelve_second_deadline(self):
        clock, receipt = Clock(), {}
        with self.assertRaisesRegex(RuntimeError, 'within 12 seconds'):
            PROCESS._endpoint(PollProcess(), PortFile(present=False), receipt,
                              clock=clock, sleep=clock.advance)
        self.assertEqual(clock.value, 12)
        self.assertEqual(receipt['startupElapsedMs'], 12000)
        self.assertEqual(receipt['status'], 'deadline')

    def test_valid_but_slow_file_read_cannot_extend_deadline(self):
        clock = Clock()
        with self.assertRaisesRegex(RuntimeError, 'after the 12-second deadline'):
            self.endpoint(PortFile(read_hook=lambda: clock.advance(12)), clock=clock)
        self.assertEqual(clock.value, 12)

    def test_non_utf8_file_is_rejected(self):
        with self.assertRaisesRegex(RuntimeError, 'non-UTF-8'):
            self.endpoint(PortFile(b'9222\n/devtools/browser/\xff'))

    def test_oversized_file_is_rejected(self):
        with self.assertRaisesRegex(RuntimeError, 'invalid debugging endpoint'):
            self.endpoint(PortFile(b'9222\n/devtools/browser/' + b'a'*4096))

    def test_slow_final_poll_cannot_accept_a_late_endpoint(self):
        clock = Clock()
        child = PollProcess(hook=lambda calls: clock.advance(12) if calls == 2 else None)
        with self.assertRaisesRegex(RuntimeError, 'after the 12-second deadline'):
            self.endpoint(process=child, clock=clock)

    def test_file_backed_logs_allow_chatty_child_and_preserve_consumer_error(self):
        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary)
            profile, output = base/'profile', base/'output'
            profile.mkdir()
            output.mkdir()
            code = """import os, pathlib, sys, time
os.write(1, b'o'*262144)
os.write(2, b'e'*262144)
pathlib.Path(sys.argv[1]).write_text('9222\\n/devtools/browser/controlled-child\\n')
time.sleep(60)
"""
            command = [sys.executable, '-c', code, str(profile/'DevToolsActivePort')]
            calls = []
            with self.assertRaisesRegex(ValueError, 'consumer-sentinel'):
                with PROCESS.chromium_endpoint(command=command, environment=dict(os.environ),
                        profile=profile, output=output, version='controlled-python-child',
                        source_files={'fixture': 'controlled'}) as endpoint:
                    calls.append(endpoint)
                    raise ValueError('consumer-sentinel')
            self.assertEqual(calls, ['ws://127.0.0.1:9222/devtools/browser/controlled-child'])
            receipt = json.loads((output/'chromium.startup.json').read_text())
            self.assertEqual(receipt['scope'], 'desktop-child-startup-only')
            self.assertEqual(receipt['status'], 'endpoint-ready')
            self.assertEqual(receipt['startupBudgetMs'], 12000)
            self.assertEqual(receipt['errorType'], 'ValueError')
            self.assertEqual(receipt['cleanup'], 'sigterm')
            self.assertFalse(is_live(receipt['pid']))
            for name, value in (('chromium.stdout.log', b'o'), ('chromium.stderr.log', b'e')):
                raw = (output/name).read_bytes()
                self.assertEqual(raw, value*262144)
                self.assertEqual(receipt['logs'][name],
                                 dict(bytes=len(raw), sha256=hashlib.sha256(raw).hexdigest()))


@unittest.skipUnless(sys.platform.startswith('linux') and hasattr(os, 'WNOWAIT'), 'Linux ownership proof')
class OwnedGroupTest(unittest.TestCase):
    def launch_fork(self, base, *, launcher_exits, grandchild_ignores_term):
        marker = base/'grandchild.pid'
        code = """import os, pathlib, signal, sys, time
child = os.fork()
if child == 0:
    if sys.argv[2] == 'ignore':
        signal.signal(signal.SIGTERM, signal.SIG_IGN)
    pathlib.Path(sys.argv[1]).write_text(str(os.getpid()))
    while True:
        time.sleep(1)
if sys.argv[3] == 'exit':
    os._exit(0)
while True:
    time.sleep(1)
"""
        child = subprocess.Popen([sys.executable, '-c', code, str(marker),
                                  'ignore' if grandchild_ignores_term else 'default',
                                  'exit' if launcher_exits else 'wait'],
                                 stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                                 start_new_session=True)
        group = PROCESS._OwnedProcessGroup(child)
        try:
            eventually(lambda: marker.is_file() and marker.read_text().isdigit())
            grandchild = int(marker.read_text())
            if launcher_exits:
                eventually(lambda: group.poll() == 0)
            return child, group, grandchild
        except BaseException:
            group.retire({})
            raise

    def cleanup(self, child, group):
        if child.returncode is None:
            group.retire({})

    def test_launcher_exit_does_not_hide_live_same_group_grandchild(self):
        with tempfile.TemporaryDirectory() as temporary:
            child, group, grandchild = self.launch_fork(Path(temporary), launcher_exits=True,
                                                       grandchild_ignores_term=False)
            try:
                self.assertEqual(group.poll(), 0)
                self.assertIsNone(child.returncode)
                self.assertTrue(is_live(grandchild))
                receipt = {}
                group.retire(receipt)
                self.assertFalse(is_live(grandchild))
                self.assertEqual(receipt['returnCodeBeforeCleanup'], 0)
                self.assertEqual(receipt['cleanup'], 'sigterm')
                self.assertEqual(receipt['returnCodeAfterCleanup'], 0)
            finally:
                self.cleanup(child, group)

    def test_term_ignoring_grandchild_requires_kill_and_foreign_group_survives(self):
        with tempfile.TemporaryDirectory() as temporary:
            child, group, grandchild = self.launch_fork(Path(temporary), launcher_exits=False,
                                                       grandchild_ignores_term=True)
            foreign = subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(60)'],
                                       start_new_session=True)
            try:
                started, receipt = time.monotonic(), {}
                group.retire(receipt)
                elapsed = time.monotonic() - started
                self.assertGreaterEqual(elapsed, 5)
                self.assertLess(elapsed, 10.5)
                self.assertEqual(receipt['cleanup'], 'sigkill')
                self.assertEqual(receipt['cleanupBudgetMs'], dict(term=5000, kill=5000))
                self.assertFalse(is_live(grandchild))
                self.assertIsNone(foreign.poll())
            finally:
                self.cleanup(child, group)
                foreign.terminate()
                foreign.wait(timeout=3)

    def test_repeated_poll_keeps_exited_launcher_waitable_until_cleanup(self):
        child = subprocess.Popen([sys.executable, '-c', 'raise SystemExit(23)'], start_new_session=True)
        group = PROCESS._OwnedProcessGroup(child)
        try:
            eventually(lambda: group.poll() == 23)
            self.assertEqual(group.poll(), 23)
            self.assertIsNone(child.returncode)
            self.assertEqual(os.getpgid(child.pid), child.pid)
            self.assertEqual(os.getsid(child.pid), child.pid)
            receipt = {}
            group.retire(receipt)
            self.assertEqual(child.returncode, 23)
            self.assertEqual(receipt['cleanup'], 'already-exited')
        finally:
            self.cleanup(child, group)

    def test_lost_waitable_child_never_authorizes_a_group_signal(self):
        child = subprocess.Popen([sys.executable, '-c', 'pass'], start_new_session=True)
        group = PROCESS._OwnedProcessGroup(child)
        child.wait(timeout=3)
        with patch.object(PROCESS.os, 'killpg') as killpg:
            with self.assertRaisesRegex(RuntimeError, 'ownership was lost'):
                group.signal(signal.SIGKILL)
            killpg.assert_not_called()

    def test_cleanup_deadlines_include_observation_and_final_reap(self):
        clock = Clock()

        class Child:
            pid = 123
            returncode = None

            def wait(self, timeout):
                self.timeout = timeout
                self.returncode = -signal.SIGKILL

        child = Child()
        group = PROCESS._OwnedProcessGroup(child)
        calls, sent, receipt = [], [], {}

        def members():
            calls.append(clock.value)
            if len(calls) == 1:
                return [child.pid]
            # An empty result at the deadline is not proof observed in budget.
            clock.advance(5)
            return []

        with patch.object(PROCESS.time, 'monotonic', clock), \
                patch.object(PROCESS.time, 'sleep', clock.advance), \
                patch.object(group, 'poll', return_value=None), \
                patch.object(group, 'live_members', side_effect=members), \
                patch.object(group, 'signal', side_effect=sent.append):
            with self.assertRaisesRegex(RuntimeError, 'did not retire within'):
                group.retire(receipt)
        self.assertEqual(sent, [signal.SIGTERM, signal.SIGKILL])
        self.assertEqual(clock.value, 10)
        self.assertEqual(child.timeout, 0)
        self.assertEqual(receipt['cleanup'], 'sigkill')
        self.assertEqual(receipt['groupCleanupError'], 'RuntimeError')


if __name__ == '__main__':
    unittest.main()
