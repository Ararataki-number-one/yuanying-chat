"""Controls for passive original observations and the post-result ADB probe."""
import importlib.util
from pathlib import Path
import socket
import struct
import subprocess
import unittest
from unittest.mock import Mock, patch

SPEC = importlib.util.spec_from_file_location('readiness_observer', Path(__file__).resolve().parents[1] / 'tools/gecko/diagnose_native_readiness.py')
DIAG = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(DIAG)


def header(name='AUTH', size=20, magic=None):
    command = int.from_bytes(name.encode(), 'little')
    return struct.pack('<6I', command, 1, 0, size, 0,
                       command ^ 0xffffffff if magic is None else magic)


class HeaderStream:
    def __init__(self, data, fragment=24):
        self.data, self.fragment, self.reads, self.sent = data, fragment, [], []
    def recv(self, count):
        self.reads.append(count)
        result, self.data = self.data[:min(count, self.fragment)], self.data[min(count, self.fragment):]
        return result
    def sendall(self, data):
        self.sent.append(data)
    def settimeout(self, seconds):
        self.timeout = seconds
    def __enter__(self):
        return self
    def __exit__(self, *unused):
        return False


class ReadinessObservationTest(unittest.TestCase):
    def test_original_command_and_result_are_forwarded_once_unchanged(self):
        command = ['/pinned/adb', '-s', 'emulator-5554', 'get-state']
        result = subprocess.CompletedProcess(command, 1, stdout='', stderr='device not found\n')
        original = Mock(return_value=result)
        observe = DIAG.StateObserver(original, '/pinned/adb')
        self.assertIs(observe(command, capture_output=True, text=True, timeout=5), result)
        original.assert_called_once_with(command, capture_output=True, text=True, timeout=5)
        self.assertEqual(len(observe.rows), 1)
        self.assertEqual(observe.rows[0]['exitCode'], 1)
        self.assertEqual(observe.rows[0]['stderr'], 'device not found\n')
        self.assertFalse(observe.rows[0]['timedOut'])

    def test_timeout_is_preserved_without_retry_or_synthetic_success(self):
        failure = subprocess.TimeoutExpired(['adb'], 5, output='offline\n', stderr='blocked')
        original = Mock(side_effect=failure)
        observe = DIAG.StateObserver(original, 'adb')
        with self.assertRaises(subprocess.TimeoutExpired) as seen:
            observe(['adb', '-s', 'emulator-5554', 'get-state'], capture_output=True, text=True, timeout=5)
        self.assertIs(seen.exception, failure)
        self.assertEqual(original.call_count, 1)
        self.assertTrue(observe.rows[0]['timedOut'])
        self.assertIsNone(observe.rows[0]['exitCode'])

    def test_other_commands_are_not_collected_or_changed(self):
        original = Mock(return_value=object())
        observe = DIAG.StateObserver(original, 'adb')
        command = ['adb', '-s', 'emulator-5556', 'shell', 'getprop', 'ro.kernel.qemu']
        self.assertIs(observe(command, timeout=8), original.return_value)
        original.assert_called_once_with(command, timeout=8)
        self.assertEqual(observe.rows, [])

    def test_fragmented_auth_header_never_reads_the_challenge(self):
        challenge = b'private-challenge-not-for-artifact'
        stream = HeaderStream(header(size=len(challenge)) + challenge, fragment=3)
        result = DIAG.probe_header(stream)
        self.assertEqual(result['responseCommand'], 'AUTH')
        self.assertFalse(result['payloadRead'])
        self.assertEqual(stream.data, challenge)
        self.assertEqual(stream.sent, [])

    def test_bad_or_oversized_header_is_rejected_without_payload(self):
        for raw in (header(magic=0), header(size=1024 * 1024 + 1), header('OPEN')):
            stream = HeaderStream(raw + b'payload')
            with self.assertRaises(ValueError):
                DIAG.probe_header(stream)
            self.assertEqual(stream.data, b'payload')

    def test_fragmented_header_keeps_one_total_deadline(self):
        stream = HeaderStream(header() + b'challenge', fragment=1)
        with patch.object(DIAG.time, 'monotonic', side_effect=[0, 1, 4]):
            with self.assertRaises(TimeoutError):
                DIAG.probe_header(stream)
        self.assertEqual(len(stream.reads), 1)
        self.assertEqual(stream.timeout, 2)

    def test_post_probe_connects_once_sends_only_cnxn_and_never_answers_auth(self):
        stream = HeaderStream(header() + b'challenge')
        with patch.object(DIAG.socket, 'create_connection', return_value=stream) as connect:
            result = DIAG.post_tcp_probe()
        connect.assert_called_once_with(('127.0.0.1', 5555), timeout=3)
        self.assertEqual(len(stream.sent), 1)
        self.assertEqual(stream.sent[0][:4], b'CNXN')
        self.assertEqual(stream.sent[0][24:], b'host::\0')
        self.assertEqual(stream.data, b'challenge')
        self.assertTrue(result['tcpAccepted'])
        self.assertFalse(result['authResponseSent'])
        self.assertFalse(result['applicationCommandsSent'])

    def test_refused_post_probe_remains_one_failed_observation(self):
        with patch.object(DIAG.socket, 'create_connection', side_effect=ConnectionRefusedError('refused')) as connect:
            result = DIAG.post_tcp_probe()
        self.assertEqual(connect.call_count, 1)
        self.assertFalse(result['tcpAccepted'])
        self.assertEqual(result['errorType'], 'ConnectionRefusedError')
        self.assertNotIn('nativeReady', result)


if __name__ == '__main__':
    unittest.main()
