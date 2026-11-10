"""Host-only counterfeit I/O controls for the explicit cellular preparation.

These tests execute the real CM, route, forwarding and ADB-header parsers.
Only subprocess/socket boundaries and elapsed time are substituted. No Android,
network reachability, application workload or release acceptance is claimed.
Run with the workflow's GIT_NO_LAZY_FETCH=1 environment.
"""
from contextlib import ExitStack, contextmanager, redirect_stderr
import importlib.util
import io
import json
from pathlib import Path
import struct
import subprocess
import sys
from types import SimpleNamespace
import unittest
from unittest.mock import patch
from urllib.parse import parse_qs, urlsplit

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools/gecko'))
SPEC = importlib.util.spec_from_file_location('cellular_controls', ROOT / 'tools/gecko/prepare_cellular_adb.py')
setup = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(setup)
REAL_RUN = subprocess.run

NETWORK = ('virtio-net-pci.0: index=0,type=nic,model=virtio-net-pci\r\n'
           ' \\ mynet: index=0,type=user,net=10.0.2.0,restrict=off\r\n'
           'virtio-wifi-device: index=0,type=nic,\r\n'
           ' \\ virtio-wifi: index=0,type=user,net=10.0.2.0,restrict=off\r\n(qemu) ')
FORWARD = 'VLAN -1 (mynet):\r\n  TCP[HOST_FORWARD] 100 127.0.0.1 5555 10.0.2.15 5555 0 0\r\n'
ADDRESS = '2: eth0 inet 10.0.2.15/24 brd 10.0.2.255 scope global eth0 valid_lft forever preferred_lft forever\n'
ROUTE = '10.0.2.2 from 10.0.2.15 dev eth0 table 1015 uid 2000\n    cache\n'


def identity():
    return dict(schema=1, package='local.pocketchat.test', sourceCommit='a' * 40,
                sourceTree='b' * 40, dirtySource=False, version='1.6.0', versionCode=51,
                sdkCoordinate='org.mozilla.geckoview:geckoview:157.0.20261005135250',
                apkSha256='c' * 64, apkBytes=100, buildStampSha256='d' * 64)


def observation(nonce):
    return dict(schema=1, runNonce=nonce, sourceCommit='a' * 40, buildIdentity=identity(),
                actualAndroidExecution=True, actualConnectivityManagerExecution=True,
                actualGeckoExecution=False, applicationAcceptance=False, physicalPhoneAcceptance=False,
                androidSdk=35, pid=100, observedAtElapsedRealtime=123,
                activeNetwork='101', activeNetworkAfter='101', capabilitiesPresent=True,
                internetCapability=True, stableDuringRead=True, usable=True, transports=['cellular'])


def empty_default(value):
    value.update(activeNetwork='', activeNetworkAfter='', capabilitiesPresent=False,
                 internetCapability=False, stableDuringRead=False, usable=False,
                 transports=[], capabilities='')


def initial_wifi(value):
    value.update(activeNetwork='100', activeNetworkAfter='100', transports=['wifi'],
                 capabilities='[ Transports: WIFI Capabilities: INTERNET ]')


def record():
    return dict(sourceCommit='a' * 40, sourceTree='b' * 40, networkMode='cellular',
                commands=[], networkObservations=[], initialInputSettings={},
                confirmedQemu=False, disabledStateConfirmed=False,
                applicationAcceptance=False, originalWorkloadInvoked=False,
                sdkWifiProvisioningRequested=False, sdkWifiProvisioningStages=[])


class Clock:
    def __init__(self): self.value = 0.0
    def now(self): return self.value
    def nanos(self): return int(self.value * 1_000_000_000)
    def sleep(self, seconds): self.value += seconds


class HeaderStream:
    """Synthetic ADB header; the advertised body must remain unread."""
    def __init__(self, name='AUTH', magic=None):
        command = int.from_bytes(name.encode(), 'little')
        self.body = b'synthetic-header-tail'
        self.data = struct.pack('<6I', command, 1, 0, len(self.body), 0,
                                command ^ 0xffffffff if magic is None else magic) + self.body
        self.sent, self.reads, self.timeouts = [], [], []
    def __enter__(self): return self
    def __exit__(self, *unused): return None
    def settimeout(self, seconds): self.timeouts.append(seconds)
    def sendall(self, data): self.sent.append(data)
    def recv(self, count):
        self.reads.append(count)
        block, self.data = self.data[:min(3, count)], self.data[min(3, count):]
        return block


class Announcement:
    def __init__(self): self.sent = []
    def __enter__(self): return self
    def __exit__(self, *unused): return None
    def sendall(self, data): self.sent.append(data)
    def recv(self, count): raise AssertionError('One-way announcement must not read a reply')


class MonitorStream:
    def __init__(self, device): self.device, self.pending = device, b'(qemu) '
    def __enter__(self): return self
    def __exit__(self, *unused): return None
    def settimeout(self, seconds): self.device.socket_timeouts.append(seconds)
    def connect(self, path):
        if path != '/synthetic/qemu.sock': raise AssertionError('Unexpected monitor path')
    def recv(self, count):
        block, self.pending = self.pending[:count], self.pending[count:]
        return block
    def sendall(self, raw):
        command = raw.decode('ascii').strip()
        self.device.events.append(('monitor', command))
        if command == 'info network': response = self.device.backend
        elif command == 'help hostfwd_add': response = 'hostfwd_add [netdev_id] rule'
        elif command == 'info usernet':
            response = self.device.after_forward if self.device.forward_installed else self.device.before_forward
        elif command == setup.RULE:
            self.device.forward_installed = True
            response = ''
        else: raise AssertionError('Unexpected monitor operation: ' + command)
        self.pending = (command + '\r\n' + response + '\r\n(qemu) ').encode()


class DeviceIO:
    """Counterfeit command bytes only; all admission decisions run unmocked."""
    def __init__(self, *, wifi=True, edits=None):
        self.clock = Clock()
        self.wifi = wifi
        self.edits = edits or {}
        self.observations = 0
        self.package_present = True
        self.package_disabled = False
        self.properties = {'ro.kernel.qemu': '1', 'ro.build.version.sdk': '35',
                           'ro.product.cpu.abi': 'x86_64', 'ro.hardware': 'ranchu',
                           'vendor.qemu.keyboard_layout': 'qwerty2'}
        self.wifi_statuses = []
        self.wlan_reads_remaining = 0
        self.wlan_stuck = False
        self.command_delay = .01
        self.route_delay = .01
        self.addresses, self.route, self.route_stderr = ADDRESS, ROUTE, ''
        self.backend, self.before_forward, self.after_forward = NETWORK, '', FORWARD
        self.forward_installed = False
        self.tcpip_result = (0, 'restarting in TCP mode port: 5555\n', '')
        self.tcpip_timeout = False
        self.native_state = 'device\n'
        self.header_name, self.header_magic = 'AUTH', None
        self.provider_timeout_at = None
        self.provider_raw_at = {}
        self.provider_exit_at = {}
        self.events, self.calls, self.headers, self.announcements, self.socket_timeouts = [], [], [], [], []

    def run(self, command, **kwargs):
        # The unchanged SDK identity validator may read an absent synthetic Git
        # object. Keep that real local reader; the workflow forbids lazy fetch.
        if command[0] == 'git': return REAL_RUN(command, **kwargs)
        if command[:2] != ['adb', '-s'] or command[2] not in ('emulator-5556', 'emulator-5554'):
            raise AssertionError('Unexpected command target')
        parts = tuple(command[3:])
        self.calls.append((list(command), kwargs['timeout']))
        self.events.append(('adb', parts))
        stdout, stderr, code = '', '', 0
        provider_index = None
        if parts[:2] == ('shell', 'getprop'):
            stdout = self.properties[parts[2]]
        elif parts[:4] == ('shell', 'settings', 'get', 'secure'):
            stdout = 'synthetic-read-only-input-setting'
        elif parts[:4] == ('shell', 'pm', 'list', 'packages'):
            stdout = ('package:' + setup.normal.PACKAGE
                      if self.package_present and ('-d' not in parts or self.package_disabled) else '')
        elif parts == ('shell', 'am', 'force-stop', setup.normal.PACKAGE): pass
        elif parts == ('shell', 'pm', 'disable-user', '--user', '0', setup.normal.PACKAGE):
            self.package_disabled = True
        elif parts[:4] == ('exec-out', 'content', 'read', '--uri'):
            uri = urlsplit(parts[4])
            query = parse_qs(uri.query)
            if uri.netloc != setup.normal.AUTHORITY or uri.path != '/default-network' or set(query) != {'runNonce'}:
                raise AssertionError('Unexpected provider request')
            value = observation(query['runNonce'][0])
            provider_index = self.observations
            if provider_index in self.edits: self.edits[provider_index](value)
            stdout = self.provider_raw_at.get(provider_index, json.dumps(value))
            code = self.provider_exit_at.get(provider_index, 0)
            self.observations += 1
        elif parts == ('shell', 'cmd', 'wifi', 'status'):
            stdout = self.wifi_statuses.pop(0) if self.wifi_statuses else 'Wifi is ' + ('enabled' if self.wifi else 'disabled')
        elif parts == ('shell', 'cmd', 'wifi', 'set-wifi-enabled', 'disabled'):
            self.wifi = False
        elif parts == ('shell', 'ip', '-4', '-o', 'addr', 'show', 'wlan0'):
            if self.wlan_stuck or self.wlan_reads_remaining:
                stdout = '16: wlan0 inet 10.0.2.16/24'
                self.wlan_reads_remaining = max(0, self.wlan_reads_remaining - 1)
        elif parts == ('shell', 'ip', '-4', '-o', 'addr', 'show', 'eth0'):
            stdout = self.addresses
        elif parts == ('shell', 'ip', '-4', 'route', 'get', '10.0.2.2', 'from', '10.0.2.15'):
            stdout, stderr = self.route, self.route_stderr
        elif parts == ('shell', 'ip', '-4', 'route', 'get', '10.0.2.2'):
            stdout = '10.0.2.2 dev eth0 table 1015 src 10.0.2.15 uid 2000\n'
        elif parts == ('shell', 'ip', '-4', 'rule', 'show'): stdout = '0: from all lookup local\n'
        elif parts == ('shell', 'ip', '-4', 'route', 'show', 'table', 'all'): stdout = '10.0.2.0/24 dev eth0 table 1015\n'
        elif parts == ('tcpip', '5555'): code, stdout, stderr = self.tcpip_result
        elif parts == ('get-state',): stdout = self.native_state
        else: raise AssertionError('Unexpected command: ' + repr(parts))
        duration = self.route_delay if parts[:3] == ('shell', 'ip', '-4') and 'wlan0' not in parts else self.command_delay
        self.clock.value += min(duration, kwargs['timeout'])
        if duration > kwargs['timeout'] or provider_index == self.provider_timeout_at and provider_index is not None or parts == ('tcpip', '5555') and self.tcpip_timeout:
            raise subprocess.TimeoutExpired(command, kwargs['timeout'], output=stdout, stderr=stderr)
        return subprocess.CompletedProcess(command, code, stdout=stdout, stderr=stderr)

    def connection(self, address, timeout):
        self.events.append(('connect', address))
        self.socket_timeouts.append(timeout)
        if address == ('127.0.0.1', 5555):
            stream = HeaderStream(self.header_name, self.header_magic)
            self.headers.append(stream)
            return stream
        if address == ('127.0.0.1', 5037):
            stream = Announcement()
            self.announcements.append(stream)
            return stream
        raise AssertionError('Unexpected TCP endpoint')

    @contextmanager
    def installed(self):
        with ExitStack() as stack:
            stack.enter_context(patch.object(setup.subprocess, 'run', side_effect=self.run))
            stack.enter_context(patch.object(setup.socket, 'socket', side_effect=lambda *a, **k: MonitorStream(self)))
            stack.enter_context(patch.object(setup.socket, 'create_connection', side_effect=self.connection))
            stack.enter_context(patch.object(setup.time, 'monotonic', side_effect=self.clock.now))
            stack.enter_context(patch.object(setup.time, 'monotonic_ns', side_effect=self.clock.nanos))
            stack.enter_context(patch.object(setup.time, 'sleep', side_effect=self.clock.sleep))
            yield

    def prepare(self, receipt, *, normal=False, budget=45):
        cls = setup.normal.Commands if normal else setup.native.BootstrapCommands
        serial = 'emulator-5554' if normal else 'emulator-5556'
        commands = cls('adb', serial, receipt, self.clock.now() + budget)
        setup.cellular_preflight(commands, receipt, identity())


class CellularPreparationControls(unittest.TestCase):
    def assert_no_network_policy_rewrite(self, device):
        parts = [tuple(c[0][3:]) for c in device.calls]
        self.assertFalse(any(p[:3] == ('shell', 'settings', 'put') or p[:2] == ('shell', 'svc') for p in parts))
        self.assertFalse(any('connect-network' in p or 'start-scan' in p or 'list-scan-results' in p for p in parts))
        self.assertFalse(any('set-wifi-enabled' in p and p[-1] != 'disabled' for p in parts))
        self.assertTrue(all(timeout <= 8 for _, timeout in device.calls))

    def test_original_initial_wifi_is_retained_then_two_real_parsed_cellular_samples(self):
        device = DeviceIO(edits={0: lambda v: v.update(transports=['wifi'])})
        receipt = record()
        with device.installed(): device.prepare(receipt)
        stage = receipt['cellularPreparation']
        self.assertEqual(stage['status'], 'passed')
        self.assertEqual(receipt['networkObservations'][0]['value']['transports'], ['wifi'])
        first, second = receipt['networkObservations'][1:]
        self.assertEqual(first['value']['activeNetwork'], second['value']['activeNetwork'])
        self.assertNotEqual(first['runNonce'], second['runNonce'])
        self.assertEqual(stage['wifiDisableAttempts'], 1)
        self.assertEqual(stage['deadlineMonotonic'], 45)
        self.assertFalse(stage['applicationAcceptance'])
        self.assertFalse(stage['originalWorkloadInvoked'])
        self.assert_no_network_policy_rewrite(device)

    def test_already_disabled_wifi_is_read_without_mutation_on_normal_target(self):
        device, receipt = DeviceIO(wifi=False), record()
        with device.installed(): device.prepare(receipt, normal=True, budget=33)
        self.assertEqual(receipt['cellularPreparation']['wifiDisableAttempts'], 0)
        self.assertEqual(receipt['cellularPreparation']['deadlineMonotonic'], 33)
        self.assertTrue(all(c[0][2] == 'emulator-5554' for c in device.calls))
        self.assert_no_network_policy_rewrite(device)

    def test_empty_handover_reads_are_not_promoted_and_two_cellular_proofs_still_required(self):
        for normal, budget in ((False, 45), (True, 33)):
            with self.subTest(normal=normal):
                device = DeviceIO(edits={1: empty_default, 2: empty_default})
                receipt = record()
                with device.installed(): device.prepare(receipt, normal=normal, budget=budget)
                stage, rows = receipt['cellularPreparation'], receipt['networkObservations']
                self.assertEqual(stage['status'], 'passed')
                self.assertEqual(stage['deadlineMonotonic'], budget)
                self.assertEqual(stage['emptyDefaultNetworkObservationIndices'], [1, 2])
                self.assertEqual(stage['firstCellularObservationIndex'], 3)
                self.assertEqual(stage['confirmationCellularObservationIndex'], 4)
                self.assertEqual(len({row['runNonce'] for row in rows}), 5)
                for row in rows[1:3]:
                    self.assertIs(row['value']['usable'], False)
                    self.assertEqual(row['value']['transports'], [])
                for row in rows[3:]:
                    self.assertIs(row['value']['usable'], True)
                    self.assertEqual(row['value']['transports'], ['cellular'])
                self.assertEqual(rows[3]['value']['activeNetwork'], rows[4]['value']['activeNetwork'])
                self.assertEqual(stage['wifiDisableAttempts'], 1)
                self.assertFalse(stage['originalWorkloadInvoked'])
                self.assert_no_network_policy_rewrite(device)

    def test_no_cellular_network_exhausts_existing_budget_without_mutation_or_fallback(self):
        device, receipt = DeviceIO(edits={i: empty_default for i in range(1, 100)}), record()
        with device.installed(), self.assertRaises(TimeoutError): device.prepare(receipt, budget=3)
        stage = receipt['cellularPreparation']
        self.assertEqual(stage['status'], 'failed')
        self.assertEqual(stage['deadlineMonotonic'], 3)
        self.assertLessEqual(device.clock.now(), 3)
        self.assertGreater(len(stage['emptyDefaultNetworkObservationIndices']), 1)
        self.assertNotIn('firstCellularObservationIndex', stage)
        self.assertEqual(stage['wifiDisableAttempts'], 0)
        self.assertTrue(all(timeout <= 3 for _, timeout in device.calls))
        self.assert_no_network_policy_rewrite(device)

    def test_only_exact_empty_default_can_wait_after_confirmed_sdk_teardown(self):
        edits = [lambda v: v.pop('capabilities'), lambda v: v.update(capabilities=None),
                 lambda v: v.update(capabilities='unknown'), lambda v: v.pop('transports'),
                 lambda v: v.update(transports=['wifi']), lambda v: v.update(transports=['vpn']),
                 lambda v: v.update(transports=['cellular', 'wifi']),
                 lambda v: v.update(activeNetworkAfter='102'), lambda v: v.update(activeNetwork='101'),
                 lambda v: v.update(androidSdk=36), lambda v: v.update(schema=True),
                 lambda v: v.update(usable=0), lambda v: v.update(stableDuringRead=0),
                 lambda v: v.update(internetCapability=0), lambda v: v.update(capabilitiesPresent=0)]
        for number, edit in enumerate(edits):
            def changed(value):
                empty_default(value)
                edit(value)
            with self.subTest(mutation=number):
                device, receipt = DeviceIO(edits={1: changed}), record()
                with device.installed(), self.assertRaises(ValueError): device.prepare(receipt)
                self.assertEqual(device.observations, 2)
                self.assertEqual(receipt['cellularPreparation']['wifiDisableAttempts'], 0)
                self.assertNotIn('emptyDefaultNetworkObservationIndices', receipt['cellularPreparation'])
        device, receipt = DeviceIO(edits={1: empty_default}), record()
        device.package_present = False
        with device.installed(), self.assertRaises(ValueError): device.prepare(receipt)
        self.assertFalse(receipt['disabledStateConfirmed'])
        self.assertEqual(device.observations, 2)

    def test_wait_does_not_swallow_later_invalid_identity_json_or_command_timeout(self):
        for failure in ('source', 'apk', 'scope', 'json', 'timeout'):
            with self.subTest(failure=failure):
                device, receipt = DeviceIO(edits={1: empty_default}), record()
                if failure == 'source': device.edits[2] = lambda v: v.update(sourceCommit='f' * 40)
                elif failure == 'apk': device.edits[2] = lambda v: v['buildIdentity'].update(apkSha256='f' * 64)
                elif failure == 'scope': device.edits[2] = lambda v: v.update(applicationAcceptance=True)
                elif failure == 'json': device.provider_raw_at[2] = '{"unfinished":'
                else: device.provider_timeout_at = 2
                with device.installed(), self.assertRaises((ValueError, subprocess.TimeoutExpired)):
                    device.prepare(receipt)
                self.assertEqual(device.observations, 3)
                self.assertEqual(receipt['cellularPreparation']['wifiDisableAttempts'], 0)
                self.assertEqual(receipt['cellularPreparation']['emptyDefaultNetworkObservationIndices'], [1])

    def test_empty_default_at_initial_or_final_observation_is_not_retried(self):
        for index in (0, 2):
            with self.subTest(index=index):
                device, receipt = DeviceIO(edits={index: empty_default}), record()
                with device.installed(), self.assertRaises(ValueError): device.prepare(receipt)
                self.assertEqual(device.observations, index + 1)
                self.assertNotIn('emptyDefaultNetworkObservationIndices', receipt['cellularPreparation'])

    def test_duplicate_nonce_during_handover_stops_before_another_read(self):
        for letters in (('e', 'e'), ('e', 'f', 'f'), ('e', 'f', 'e')):
            with self.subTest(letters=letters):
                device, receipt = DeviceIO(edits={1: empty_default, 2: empty_default}), record()
                values = [SimpleNamespace(hex=x * 32) for x in letters]
                with device.installed(), patch.object(setup.normal.uuid, 'uuid4', side_effect=values), self.assertRaises(ValueError):
                    device.prepare(receipt)
                self.assertEqual(device.observations, len(letters))
                self.assertEqual(receipt['cellularPreparation']['wifiDisableAttempts'], 0)

    def test_verified_initial_wifi_can_wait_then_empty_then_two_cellular_proofs(self):
        def retained(value):
            initial_wifi(value)
            value['capabilities'] += ' Link speed: 2Mbps'
        for normal, budget in ((False, 45), (True, 33)):
            with self.subTest(normal=normal):
                device = DeviceIO(edits={0: initial_wifi, 1: retained, 2: initial_wifi, 3: empty_default})
                receipt = record()
                with device.installed(): device.prepare(receipt, normal=normal, budget=budget)
                stage, rows = receipt['cellularPreparation'], receipt['networkObservations']
                self.assertEqual(stage['status'], 'passed')
                self.assertEqual(stage['deadlineMonotonic'], budget)
                self.assertEqual(stage['retainedInitialWifiObservationIndices'], [1, 2])
                self.assertEqual(stage['emptyDefaultNetworkObservationIndices'], [3])
                self.assertEqual(stage['firstCellularObservationIndex'], 4)
                self.assertEqual(stage['confirmationCellularObservationIndex'], 5)
                self.assertEqual(len({row['runNonce'] for row in rows}), 6)
                for row in rows[1:3]:
                    self.assertEqual(row['value']['transports'], ['wifi'])
                    self.assertEqual(row['value']['activeNetwork'], rows[0]['value']['activeNetwork'])
                self.assertIs(rows[3]['value']['usable'], False)
                for row in rows[4:]:
                    self.assertEqual(row['value']['transports'], ['cellular'])
                    self.assertIs(row['value']['usable'], True)
                self.assertEqual(rows[4]['value']['activeNetwork'], rows[5]['value']['activeNetwork'])
                self.assertEqual(stage['wifiDisableAttempts'], 1)
                self.assertFalse(stage['originalWorkloadInvoked'])
                self.assert_no_network_policy_rewrite(device)

    def test_retained_initial_wifi_exhausts_original_budget_without_mutation(self):
        device, receipt = DeviceIO(edits={i: initial_wifi for i in range(100)}), record()
        with device.installed(), self.assertRaises(TimeoutError): device.prepare(receipt, budget=3)
        stage = receipt['cellularPreparation']
        self.assertEqual(stage['status'], 'failed')
        self.assertEqual(stage['deadlineMonotonic'], 3)
        self.assertLessEqual(device.clock.now(), 3)
        self.assertGreater(len(stage['retainedInitialWifiObservationIndices']), 1)
        self.assertNotIn('firstCellularObservationIndex', stage)
        self.assertNotIn('emptyDefaultNetworkObservationIndices', stage)
        self.assertEqual(stage['wifiDisableAttempts'], 0)
        self.assertTrue(device.wifi)
        self.assert_no_network_policy_rewrite(device)

    def test_only_same_verified_initial_pure_usable_wifi_can_wait(self):
        def cellular_same_id(value): value.update(activeNetwork='100', activeNetworkAfter='100')
        def initial_bad_schema(value): initial_wifi(value); value.update(schema=True)
        def initial_missing_caps(value): initial_wifi(value); value.pop('capabilities')
        edits = [lambda v: v.update(activeNetwork='102', activeNetworkAfter='102'),
                 lambda v: v.update(transports=['wifi', 'cellular']),
                 lambda v: v.update(transports=['wifi', 'vpn']),
                 lambda v: v.update(transports=['ethernet']),
                 lambda v: v.update(capabilities=None), lambda v: v.update(capabilities=''),
                 lambda v: v.update(internetCapability=False, usable=False),
                 lambda v: v.update(activeNetworkAfter='', stableDuringRead=False, usable=False),
                 lambda v: v.update(androidSdk=36), lambda v: v.update(schema=True)]
        cases = [(initial_wifi, edit) for edit in edits]
        cases += [(first, lambda value: None) for first in
                  (cellular_same_id, initial_bad_schema, initial_missing_caps)]
        for number, (first, edit) in enumerate(cases):
            def changed(value): initial_wifi(value); edit(value)
            with self.subTest(mutation=number):
                device, receipt = DeviceIO(edits={0: first, 1: changed}), record()
                with device.installed(), self.assertRaises(ValueError): device.prepare(receipt)
                stage = receipt['cellularPreparation']
                self.assertEqual(device.observations, 2)
                self.assertEqual(stage['wifiDisableAttempts'], 0)
                self.assertNotIn('retainedInitialWifiObservationIndices', stage)
                self.assertNotIn('firstCellularObservationIndex', stage)
        device, receipt = DeviceIO(edits={0: initial_wifi, 1: initial_wifi}), record()
        device.package_present = False
        with device.installed(), self.assertRaises(ValueError): device.prepare(receipt)
        self.assertFalse(receipt['disabledStateConfirmed'])
        self.assertEqual(device.observations, 2)

    def test_initial_wifi_must_not_return_after_an_empty_default_observation(self):
        device = DeviceIO(edits={0: initial_wifi, 1: empty_default, 2: initial_wifi})
        receipt = record()
        with device.installed(), self.assertRaises(ValueError): device.prepare(receipt)
        stage = receipt['cellularPreparation']
        self.assertEqual(device.observations, 3)
        self.assertEqual(stage['emptyDefaultNetworkObservationIndices'], [1])
        self.assertNotIn('retainedInitialWifiObservationIndices', stage)
        self.assertNotIn('firstCellularObservationIndex', stage)
        self.assertEqual(stage['wifiDisableAttempts'], 0)

    def test_retained_wifi_wait_does_not_retry_identity_json_exit_or_timeout_errors(self):
        for failure in ('source', 'apk', 'scope', 'json', 'exit', 'timeout'):
            with self.subTest(failure=failure):
                device, receipt = DeviceIO(edits={0: initial_wifi, 1: initial_wifi}), record()
                if failure == 'source': device.edits[2] = lambda v: v.update(sourceCommit='f' * 40)
                elif failure == 'apk': device.edits[2] = lambda v: v['buildIdentity'].update(apkSha256='f' * 64)
                elif failure == 'scope': device.edits[2] = lambda v: v.update(applicationAcceptance=True)
                elif failure == 'json': device.provider_raw_at[2] = '{"unfinished":'
                elif failure == 'exit': device.provider_exit_at[2] = 1
                else: device.provider_timeout_at = 2
                with device.installed(), self.assertRaises((ValueError, subprocess.CalledProcessError, subprocess.TimeoutExpired)):
                    device.prepare(receipt)
                self.assertEqual(device.observations, 3)
                self.assertEqual(receipt['cellularPreparation']['retainedInitialWifiObservationIndices'], [1])
                self.assertEqual(receipt['cellularPreparation']['wifiDisableAttempts'], 0)
                self.assertNotIn('firstCellularObservationIndex', receipt['cellularPreparation'])

    def test_retained_wifi_nonce_reuse_and_wifi_at_final_proof_are_rejected(self):
        for letters in (('e', 'e'), ('e', 'f', 'f')):
            with self.subTest(letters=letters):
                device, receipt = DeviceIO(edits={i: initial_wifi for i in range(3)}), record()
                values = [SimpleNamespace(hex=x * 32) for x in letters]
                with device.installed(), patch.object(setup.normal.uuid, 'uuid4', side_effect=values), self.assertRaises(ValueError):
                    device.prepare(receipt)
                self.assertEqual(device.observations, len(letters))
                self.assertEqual(receipt['cellularPreparation']['wifiDisableAttempts'], 0)
        device = DeviceIO(edits={0: initial_wifi, 1: initial_wifi, 3: initial_wifi})
        receipt = record()
        with device.installed(), self.assertRaises(ValueError): device.prepare(receipt)
        self.assertEqual(device.observations, 4)
        self.assertEqual(receipt['cellularPreparation']['firstCellularObservationIndex'], 2)
        self.assertEqual(receipt['cellularPreparation']['wifiDisableAttempts'], 1)
        self.assertEqual(receipt['cellularPreparation']['status'], 'failed')

    def test_async_wifi_teardown_repeats_reads_but_only_one_disable(self):
        device, receipt = DeviceIO(), record()
        device.wlan_reads_remaining = 3
        with device.installed(): device.prepare(receipt)
        self.assertEqual(receipt['cellularPreparation']['wifiDisableAttempts'], 1)
        self.assertEqual(len(receipt['cellularPreparation']['wifiAddressObservations']), 4)
        self.assertEqual(sum('set-wifi-enabled' in c for c, _ in device.calls), 1)

    def test_wrong_image_stops_before_package_or_wifi_mutations(self):
        for key, wrong in [('ro.kernel.qemu', '0'), ('ro.build.version.sdk', '34'),
                           ('ro.product.cpu.abi', 'arm64-v8a'), ('ro.hardware', 'physical')]:
            with self.subTest(key=key):
                device, receipt = DeviceIO(), record()
                device.properties[key] = wrong
                with device.installed(), self.assertRaises(ValueError): device.prepare(receipt)
                self.assertEqual(receipt['cellularPreparation']['status'], 'failed')
                self.assertTrue(all(tuple(c[3:5]) == ('shell', 'getprop') for c, _ in device.calls))

    def test_cellular_transport_is_an_exact_single_item_list_in_both_samples(self):
        values = [None, 'cellular', [], ['wifi'], ['vpn'], ['cellular', 'vpn'],
                  ['cellular', 'wifi'], ['cellular', 'cellular'], ['CELLULAR'], ['cellular ']]
        for index in (1, 2):
            for value in values:
                with self.subTest(index=index, transport=value):
                    device = DeviceIO(edits={index: lambda v, x=value: v.update(transports=x)})
                    receipt = record()
                    with device.installed(), self.assertRaises(ValueError): device.prepare(receipt)
                    self.assertEqual(receipt['cellularPreparation']['status'], 'failed')
                    self.assert_no_network_policy_rewrite(device)
            device, receipt = DeviceIO(edits={index: lambda v: v.pop('transports')}), record()
            with device.installed(), self.assertRaises(ValueError): device.prepare(receipt)

    def test_stale_identity_nonce_missing_internet_or_promoted_scope_are_rejected(self):
        edits = [lambda v: v.update(runNonce='0' * 32),
                 lambda v: v.update(sourceCommit='f' * 40),
                 lambda v: v['buildIdentity'].update(apkSha256='f' * 64),
                 lambda v: v['buildIdentity'].update(dirtySource=True),
                 lambda v: v.update(buildIdentity=None),
                 lambda v: v.update(internetCapability=False, usable=False),
                 lambda v: v.update(internetCapability=1),
                 lambda v: v.update(activeNetworkAfter='102', stableDuringRead=False, usable=False),
                 lambda v: v.update(activeNetwork='', activeNetworkAfter='', capabilitiesPresent=False,
                                    internetCapability=False, stableDuringRead=False, usable=False),
                 lambda v: v.update(androidSdk=36),
                 lambda v: v.update(applicationAcceptance=True),
                 lambda v: v.update(actualGeckoExecution=True)]
        for index in (0, 1, 2):
            for number, edit in enumerate(edits):
                with self.subTest(index=index, mutation=number):
                    device, receipt = DeviceIO(edits={index: edit}), record()
                    with device.installed(), self.assertRaises(ValueError): device.prepare(receipt)
                    self.assertNotEqual(receipt['cellularPreparation']['status'], 'passed')
                    self.assert_no_network_policy_rewrite(device)

    def test_two_individually_usable_cellular_networks_must_have_same_identity(self):
        device = DeviceIO(edits={2: lambda v: v.update(activeNetwork='102', activeNetworkAfter='102')})
        receipt = record()
        with device.installed(), self.assertRaises(ValueError): device.prepare(receipt)
        self.assertEqual(device.observations, 3)

    def test_duplicate_generated_invocation_nonce_is_rejected(self):
        for letters in (('e', 'f', 'f'), ('e', 'e', 'f'), ('e', 'f', 'e')):
            with self.subTest(letters=letters):
                device, receipt = DeviceIO(), record()
                values = [SimpleNamespace(hex=x * 32) for x in letters]
                with device.installed(), patch.object(setup.normal.uuid, 'uuid4', side_effect=values), self.assertRaises(ValueError):
                    device.prepare(receipt)

    def test_invalid_json_and_timed_out_complete_json_never_become_observations(self):
        for timed_out in (False, True):
            with self.subTest(timed_out=timed_out):
                device, receipt = DeviceIO(), record()
                if timed_out: device.provider_timeout_at = 1
                else: device.provider_raw_at[1] = '{"unfinished":'
                with device.installed(), self.assertRaises((ValueError, subprocess.TimeoutExpired)):
                    device.prepare(receipt)
                self.assertEqual(receipt['cellularPreparation']['status'], 'failed')

    def test_ambiguous_or_reenabled_wifi_is_rejected(self):
        for statuses in (['unknown'], ['Wifi is enabled\nWifi is disabled'],
                         ['Wifi is disabled', 'Wifi is enabled']):
            with self.subTest(statuses=statuses):
                device, receipt = DeviceIO(wifi=False), record()
                device.wifi_statuses = statuses.copy()
                with device.installed(), self.assertRaises(ValueError): device.prepare(receipt)
                self.assertEqual(receipt['cellularPreparation']['wifiDisableAttempts'], 0)

    def test_stuck_teardown_exhausts_original_budget_without_second_mutation(self):
        device, receipt = DeviceIO(), record()
        device.wlan_stuck = True
        with device.installed(), self.assertRaises(TimeoutError): device.prepare(receipt, budget=1)
        self.assertLessEqual(device.clock.now(), 1)
        self.assertEqual(receipt['cellularPreparation']['wifiDisableAttempts'], 1)
        self.assertEqual(receipt['cellularPreparation']['status'], 'failed')

    def test_same_receipt_cannot_be_reused_for_a_second_preparation(self):
        device, receipt = DeviceIO(), record()
        with device.installed():
            device.prepare(receipt)
            calls = len(device.calls)
            with self.assertRaises(ValueError): device.prepare(receipt)
        self.assertEqual(len(device.calls), calls)


class CellularRouteControls(unittest.TestCase):
    def test_exact_backend_and_forward_are_parsed(self):
        setup.verify_backend(NETWORK)
        setup.verify_forward(FORWARD)
        setup.verify_source_path(ADDRESS, ROUTE)
        setup.verify_source_path(ADDRESS, '10.0.2.2 from 10.0.2.15 dev eth0 src 10.0.2.15 uid 2000\n')

    def test_wifi_near_named_and_duplicate_backend_records_are_rejected(self):
        values = ['', NETWORK.replace('mynet:', 'mynet-extra:'), NETWORK.replace('type=user', 'type=tap'),
                  NETWORK.replace('model=virtio-net-pci', 'model=virtio-net-pci-fake'),
                  NETWORK.replace('restrict=off', 'restrict=on'), NETWORK + NETWORK]
        for value in values:
            with self.subTest(value=value[:50]), self.assertRaises(ValueError): setup.verify_backend(value)

    def test_only_one_exact_loopback_native_forward_is_accepted(self):
        values = ['', FORWARD.replace('mynet', 'virtio-wifi'), FORWARD.replace('mynet', 'mynet-extra'),
                  FORWARD.replace('127.0.0.1', '0.0.0.0'), FORWARD.replace('10.0.2.15', '10.0.2.16'),
                  FORWARD.replace('5555', '5557'), FORWARD + FORWARD,
                  FORWARD + FORWARD.replace('mynet', 'virtio-wifi'), FORWARD.replace(' 0 0', ' 0')]
        for value in values:
            with self.subTest(value=value[:50]), self.assertRaises(ValueError): setup.verify_forward(value)

    def test_address_and_source_route_cannot_use_the_wifi_or_wrong_path(self):
        addresses = ['', ADDRESS.replace('eth0', 'wlan0'), ADDRESS.replace('10.0.2.15/', '10.0.2.16/'),
                     ADDRESS.replace('/24', '/33'), ADDRESS + ADDRESS,
                     ADDRESS.replace('inet 10.0.2.15', 'inet6 10.0.2.15')]
        routes = ['', ROUTE.replace('10.0.2.2 from', '10.0.2.3 from'), ROUTE.replace('eth0', 'wlan0'),
                  ROUTE.replace('10.0.2.15', '10.0.2.16'), ROUTE.replace('from 10.0.2.15 ', ''),
                  ROUTE.replace('table 1015', 'table foreign'), ROUTE.replace('dev eth0', 'dev eth0 dev eth0'),
                  ROUTE.replace('uid 2000', 'src 10.0.2.16 uid 2000'), ROUTE + 'unexpected\n']
        for address in addresses:
            with self.subTest(address=address[:40]), self.assertRaises(ValueError): setup.verify_source_path(address, ROUTE)
        for route in routes:
            with self.subTest(route=route[:40]), self.assertRaises(ValueError): setup.verify_source_path(ADDRESS, route)


class CellularNativeProtocolControls(unittest.TestCase):
    def execute(self, device):
        receipt = record()
        with device.installed():
            device.prepare(receipt)
            setup.native_transport('adb', Path('/synthetic/qemu.sock'), receipt)
        return receipt

    def test_original_protocol_functions_run_with_single_tcpip_cnxn_and_announcement(self):
        device = DeviceIO()
        receipt = self.execute(device)
        self.assertTrue(receipt['nativeReady'])
        self.assertEqual(receipt['returnRouteSource'], '10.0.2.15')
        self.assertEqual(receipt['tcpipCommand']['invocations'], 1)
        self.assertEqual(receipt['endpointDeadlineSeconds'], 8)
        self.assertEqual(sum(p == ('adb', ('tcpip', '5555')) for p in device.events), 1)
        self.assertEqual(len(device.headers), 1)
        self.assertEqual(len(device.headers[0].sent), 1)
        self.assertEqual(device.headers[0].sent[0][:4], b'CNXN')
        self.assertEqual(device.headers[0].sent[0][24:], b'host::\0')
        self.assertEqual(device.headers[0].data, device.headers[0].body)
        self.assertEqual([s.sent for s in device.announcements], [[b'0012host:emulator:5555']])
        transition = next(i for i, (c, _) in enumerate(device.calls) if c[-2:] == ['tcpip', '5555'])
        self.assertTrue(all(c[2] == 'emulator-5554' for c, _ in device.calls[transition + 1:]))
        self.assertTrue(all(t <= 8 for _, t in device.calls))
        self.assertFalse(receipt['applicationAcceptance'])

    def test_route_backend_or_forward_failure_never_reaches_tcpip(self):
        mutations = [lambda d: setattr(d, 'route', ROUTE.replace('eth0', 'wlan0')),
                     lambda d: setattr(d, 'addresses', ADDRESS.replace('10.0.2.15', '10.0.2.16')),
                     lambda d: setattr(d, 'route_stderr', 'synthetic route error'),
                     lambda d: setattr(d, 'backend', NETWORK.replace('mynet:', 'foreign:')),
                     lambda d: setattr(d, 'before_forward', FORWARD),
                     lambda d: setattr(d, 'after_forward', FORWARD + FORWARD)]
        for number, mutate in enumerate(mutations):
            with self.subTest(mutation=number):
                device = DeviceIO(); mutate(device)
                with self.assertRaises((ValueError, subprocess.CalledProcessError)): self.execute(device)
                self.assertFalse(any(c[-2:] == ['tcpip', '5555'] for c, _ in device.calls))
                self.assertFalse(device.headers or device.announcements)

    def test_cnxn_response_reaches_the_same_native_device_gate(self):
        device = DeviceIO(); device.header_name = 'CNXN'
        receipt = self.execute(device)
        self.assertTrue(receipt['nativeReady'])
        self.assertEqual(receipt['endpointProbeAttempts'][0]['responseCommand'], 'CNXN')
        self.assertEqual(len(device.headers), 1)
        self.assertEqual(len(device.headers[0].sent), 1)
        self.assertEqual(device.headers[0].data, device.headers[0].body)

    def test_route_budget_is_not_extended_and_failed_reads_do_not_create_forward(self):
        device = DeviceIO(); device.route_delay = 10
        receipt = record()
        with device.installed():
            device.prepare(receipt)
            started = device.clock.now()
            with self.assertRaises(subprocess.TimeoutExpired):
                setup.native_transport('adb', Path('/synthetic/qemu.sock'), receipt)
        self.assertAlmostEqual(receipt['routeReadinessDeadlineMonotonic'] - started, 30)
        self.assertLessEqual(device.clock.now() - started, 30)
        self.assertFalse(device.forward_installed or device.headers)

    def test_closed_tcpip_still_requires_actual_header_and_device_gate(self):
        device = DeviceIO(); device.tcpip_result = (1, '', 'error: closed\n')
        receipt = self.execute(device)
        self.assertFalse(receipt['tcpipCommand']['commandSucceeded'])
        self.assertTrue(receipt['tcpipCommand']['completionUncertainClosed'])
        self.assertTrue(receipt['endpointProtocolReachable'] and receipt['nativeReady'])

    def test_tcpip_timeout_is_not_retried_or_promoted_by_valid_stdout(self):
        device = DeviceIO(); device.tcpip_timeout = True
        with self.assertRaises(subprocess.TimeoutExpired): self.execute(device)
        self.assertEqual(sum(c[-2:] == ['tcpip', '5555'] for c, _ in device.calls), 1)
        self.assertFalse(device.headers or device.announcements)

    def test_unexpected_tcpip_failure_is_not_treated_as_closed_transition(self):
        device = DeviceIO(); device.tcpip_result = (1, '', 'permission denied\n')
        with self.assertRaises(subprocess.CalledProcessError): self.execute(device)
        self.assertFalse(device.headers or device.announcements)

    def test_invalid_or_clse_headers_exhaust_only_original_endpoint_budget(self):
        for name, magic in [('CLSE', None), ('AUTH', 0), ('NOPE', None)]:
            with self.subTest(name=name, magic=magic):
                device = DeviceIO(); device.header_name, device.header_magic = name, magic
                receipt = record()
                with device.installed():
                    device.prepare(receipt)
                    with self.assertRaises(TimeoutError): setup.native_transport('adb', Path('/synthetic/qemu.sock'), receipt)
                self.assertEqual(receipt['endpointDeadlineSeconds'], 8)
                self.assertFalse(receipt['endpointProtocolReachable'])
                self.assertFalse(device.announcements)
                self.assertEqual(sum(c[-2:] == ['tcpip', '5555'] for c, _ in device.calls), 1)

    def test_auth_header_and_announcement_cannot_replace_native_get_state(self):
        device = DeviceIO(); device.native_state = 'offline\n'
        with self.assertRaises(TimeoutError): self.execute(device)
        self.assertEqual(len(device.headers), 1)
        self.assertEqual(len(device.announcements), 1)

    def test_native_missing_original_run_id_is_rejected_before_any_io(self):
        argv = ['prepare_cellular_adb.py', '--phase', 'native', '--adb', 'adb',
                '--apk', '/synthetic/app.apk', '--monitor', '/synthetic/qemu.sock']
        with ExitStack() as stack:
            stack.enter_context(patch.object(sys, 'argv', argv))
            stack.enter_context(patch.dict(setup.os.environ, {}, clear=True))
            commands = stack.enter_context(patch.object(setup.subprocess, 'run'))
            source_reads = stack.enter_context(patch.object(setup.subprocess, 'check_output'))
            monitor = stack.enter_context(patch.object(setup.socket, 'socket'))
            tcp = stack.enter_context(patch.object(setup.socket, 'create_connection'))
            with self.assertRaises(KeyError) as error:
                setup.main()
            self.assertEqual(error.exception.args, ('GITHUB_RUN_ID',))
            for boundary in (commands, source_reads, monitor, tcp):
                boundary.assert_not_called()

    def test_cli_refuses_wrong_target_mode_or_expanded_budgets_before_io(self):
        base = ['prepare_cellular_adb.py', '--adb', 'adb', '--apk', '/synthetic/app.apk']
        invalid = [[], ['--phase', 'normal'], ['--phase', 'native'],
                   ['--phase', 'normal', '--serial', 'physical-phone'],
                   ['--phase', 'normal', '--serial', 'emulator-5556'],
                   ['--phase', 'normal', '--serial', 'emulator-5554', '--timeout', '46'],
                   ['--phase', 'normal', '--serial', 'emulator-5554', '--timeout', '14'],
                   ['--phase', 'normal', '--serial', 'emulator-5554', '--monitor', '/synthetic/qemu.sock'],
                   ['--phase', 'native', '--monitor', '/synthetic/qemu.sock', '--serial', 'emulator-5554'],
                   ['--phase', 'native', '--monitor', '/synthetic/qemu.sock', '--timeout', '46'],
                   ['--phase', 'native', '--monitor', '/synthetic/qemu.sock', '--timeout', '44'],
                   ['--phase', 'native', '--monitor', '/synthetic/qemu.sock', '--network-mode', 'legacy']]
        for args in invalid:
            with self.subTest(args=args), patch.object(sys, 'argv', base + args), redirect_stderr(io.StringIO()), \
                    patch.object(setup.subprocess, 'run') as command:
                with self.assertRaises(SystemExit) as error: setup.main()
                self.assertEqual(error.exception.code, 2)
                command.assert_not_called()


if __name__ == '__main__':
    unittest.main()
