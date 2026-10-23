"""Guards for true Wi-Fi endpoint identity and uncertain tcpip completion."""
import importlib.util
from pathlib import Path
import struct
import subprocess
import sys
import unittest
from unittest.mock import Mock, patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools/gecko'))
SPEC = importlib.util.spec_from_file_location('wifi_adapter', ROOT / 'tools/gecko/prepare_native_wifi.py')
DIAG = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(DIAG)

NETWORK = 'virtio-net-pci.0: index=0,type=nic,model=virtio-net-pci\r\n \\ mynet: index=0,type=user,net=10.0.2.0,restrict=off\r\nvirtio-wifi-device: index=0,type=nic,\r\n \\ virtio-wifi: index=0,type=user,net=10.0.2.0,restrict=off\r\n(qemu) '
FORWARD = 'VLAN -1 (virtio-wifi):\r\n  TCP[HOST_FORWARD] 100 127.0.0.1 5555 10.0.2.16 5555 0 0\r\n'


def completed(stdout='', code=0, stderr=''):
    return subprocess.CompletedProcess(['adb'], code, stdout=stdout, stderr=stderr)


class HeaderStream:
    def __init__(self, name='AUTH', magic=None):
        command = int.from_bytes(name.encode(), 'little')
        self.data = struct.pack('<6I', command, 1, 0, 20, 0,
                                command ^ 0xffffffff if magic is None else magic) + b'secret-auth-payload'
        self.sent, self.reads = [], []
    def recv(self, count):
        self.reads.append(count)
        block, self.data = self.data[:min(3, count)], self.data[min(3, count):]
        return block
    def settimeout(self, seconds):
        self.timeout = seconds
    def sendall(self, data):
        self.sent.append(data)
    def __enter__(self):
        return self
    def __exit__(self, *unused):
        return False


class WifiNativeTest(unittest.TestCase):
    def invoke(self, tcpip=None, endpoint_error=None, native_error=None):
        record = {'confirmedQemu': True}
        original = Mock(BOOTSTRAP='emulator-5556')
        original.wait_native.side_effect = native_error
        events = []
        def command(parts, **kwargs):
            events.append(parts)
            if parts[-2:] == ['tcpip', '5555']:
                if isinstance(tcpip, BaseException):
                    raise tcpip
                return tcpip or completed('restarting in TCP mode port: 5555\n')
            return completed('16: wlan0 inet 10.0.2.16/24' if 'addr' in parts else '10.0.2.2 dev wlan0 src 10.0.2.16')
        def observed_monitor(path, operation):
            events.append(operation)
            return {'info network': NETWORK, 'help hostfwd_add': 'hostfwd_add [netdev_id] rule',
                    DIAG.RULE: ''}.get(operation, FORWARD if events.count('info usernet') > 1 else '')
        def ready(r):
            events.append('endpoint-probe')
            if endpoint_error:
                raise endpoint_error
            r['endpointProtocolReachable'] = True
        try:
            with patch.object(DIAG.subprocess, 'run', side_effect=command), \
                    patch.object(DIAG, 'monitor', side_effect=observed_monitor), \
                    patch.object(DIAG, 'wait_endpoint', side_effect=ready):
                DIAG.native_transport('adb', Path('/fixed/qemu.sock'), record, original)
        except BaseException as error:
            return record, original, events, error
        return record, original, events, None

    def test_backend_requires_actual_wifi_nic_user_link(self):
        DIAG.verify_backend(NETWORK)
        for text in (NETWORK.replace('virtio-wifi:', 'mynet:'), NETWORK.replace('type=user', 'type=tap'), ''):
            with self.assertRaises(ValueError):
                DIAG.verify_backend(text)

    def test_forward_requires_unique_loopback_wifi_rule(self):
        DIAG.verify_forward(FORWARD)
        for text in (FORWARD.replace('virtio-wifi', 'mynet'), FORWARD.replace('10.0.2.16', '10.0.2.15'),
                     FORWARD.replace('127.0.0.1', '0.0.0.0'), FORWARD + FORWARD, ''):
            with self.assertRaises(ValueError):
                DIAG.verify_forward(text)

    def test_forward_precedes_single_tcpip_and_no_vsock_command_follows(self):
        record, original, events, error = self.invoke()
        self.assertIsNone(error)
        tcpip = ['adb', '-s', 'emulator-5556', 'tcpip', '5555']
        self.assertEqual(events.count(tcpip), 1)
        self.assertLess(events.index(DIAG.RULE), events.index(tcpip))
        self.assertEqual(events[events.index(tcpip) + 1:], ['endpoint-probe'])
        original.announce_native.assert_called_once_with(record)
        original.wait_native.assert_called_once_with('adb', record)

    def test_closed_remains_uncertain_and_requires_protocol_and_original_device_gate(self):
        record, original, events, error = self.invoke(completed('', 1, 'error: closed\n'))
        self.assertIsNone(error)
        self.assertEqual(record['tcpipCommand']['exitCode'], 1)
        self.assertFalse(record['tcpipCommand']['commandSucceeded'])
        self.assertTrue(record['tcpipCommand']['completionUncertainClosed'])
        original.announce_native.assert_called_once()
        original.wait_native.assert_called_once()

    def test_other_error_and_timeout_never_become_ready(self):
        for failure in (completed('', 1, 'error: device not found\n'), completed('', 2, 'error: closed\n'),
                        subprocess.TimeoutExpired(['adb'], 8)):
            record, original, events, error = self.invoke(failure)
            self.assertIsNotNone(error)
            self.assertNotIn('endpoint-probe', events)
            original.announce_native.assert_not_called()
            original.wait_native.assert_not_called()

    def test_closed_with_unreachable_endpoint_remains_failure_without_announce(self):
        record, original, events, error = self.invoke(completed('', 1, 'error: closed'), TimeoutError('not ready'))
        self.assertIsInstance(error, TimeoutError)
        original.announce_native.assert_not_called()
        original.wait_native.assert_not_called()

    def test_protocol_reachability_does_not_bypass_original_get_state_failure(self):
        record, original, events, error = self.invoke(native_error=TimeoutError('Native TCP target did not become ready'))
        self.assertTrue(record['endpointProtocolReachable'])
        self.assertIsInstance(error, TimeoutError)
        original.announce_native.assert_called_once()
        original.wait_native.assert_called_once()

    def test_auth_header_does_not_read_or_answer_challenge(self):
        stream = HeaderStream()
        with patch.object(DIAG.socket, 'create_connection', return_value=stream):
            row = DIAG.endpoint_probe(DIAG.time.monotonic() + 8)
        self.assertEqual(row['responseCommand'], 'AUTH')
        self.assertEqual(stream.data, b'secret-auth-payload')
        self.assertEqual(len(stream.sent), 1)
        self.assertEqual(stream.sent[0][:4], b'CNXN')
        self.assertEqual(stream.sent[0][24:], b'host::\0')
        self.assertFalse(row['authResponseSent'])

    def test_short_invalid_or_clse_header_never_satisfies_endpoint_gate(self):
        stream = HeaderStream(magic=0)
        with patch.object(DIAG.socket, 'create_connection', return_value=stream):
            row = DIAG.endpoint_probe(DIAG.time.monotonic() + 8)
        self.assertNotIn('responseCommand', row)
        record = {}
        with patch.object(DIAG, 'endpoint_probe', return_value={'responseCommand': 'CLSE'}) as probe, \
                patch.object(DIAG.time, 'monotonic', side_effect=[0, 8]):
            with self.assertRaises(TimeoutError):
                DIAG.wait_endpoint(record)
        probe.assert_called_once_with(8)
        self.assertFalse(record['endpointProtocolReachable'])

    def test_monitor_rejects_unrelated_mutation(self):
        with patch.object(DIAG.socket, 'socket') as socket_call:
            with self.assertRaises(ValueError):
                DIAG.monitor(Path('/fixed/qemu.sock'), 'hostfwd_add mynet tcp:0.0.0.0:22-10.0.2.15:22')
        socket_call.assert_not_called()


if __name__ == '__main__':
    unittest.main()
