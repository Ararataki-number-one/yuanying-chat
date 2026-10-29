import importlib.util
import json
from contextlib import ExitStack
from pathlib import Path
import time
import struct
import subprocess
import tempfile
import unittest
from unittest.mock import Mock, patch
from urllib.parse import parse_qs, urlsplit

spec=importlib.util.spec_from_file_location('native_setup_draft',Path(__file__).resolve().parents[1] / 'tools/gecko/prepare_native_adb.py')
setup=importlib.util.module_from_spec(spec);spec.loader.exec_module(setup)


class FakeCommands:
    def __init__(self, addresses=''):
        self.calls=[];self.addresses=addresses;self.deadline=time.monotonic()+.5
    def run(self,*parts):
        self.calls.append(parts)
        if parts[:4]==('shell','ip','-4','-o'):return self.addresses
        return ''


class NativeSetupControls(unittest.TestCase):
    def test_emulator_notification_sends_one_frame_without_reading_a_status(self):
        record={}
        with patch.object(setup.socket,'create_connection') as connection:
            stream=connection.return_value.__enter__.return_value
            stream.recv.side_effect=AssertionError('One-way service has no reply')
            setup.announce_native(record)
            stream.sendall.assert_called_once_with(b'0012host:emulator:5555')
            stream.recv.assert_not_called()
        self.assertTrue(record['announcementSent'])
        self.assertNotIn('nativeReady',record)

    def test_notification_does_not_replace_actual_native_readiness(self):
        record={'announcementSent':True}
        offline=subprocess.CompletedProcess([],0,stdout='offline\n',stderr='')
        ready=subprocess.CompletedProcess([],0,stdout='device\n',stderr='')
        with patch.object(setup.subprocess,'run',side_effect=[offline,ready]),patch.object(setup.time,'sleep'):
            setup.wait_native('adb',record)
        self.assertTrue(record['nativeReady'])

    def test_missing_or_failed_native_state_still_fails_the_bounded_setup(self):
        for result in (subprocess.CompletedProcess([],0,stdout='offline\n',stderr=''),
                       subprocess.CompletedProcess([],1,stdout='device\n',stderr='error')):
            record={'announcementSent':True}
            with patch.object(setup.subprocess,'run',return_value=result),patch.object(setup.time,'monotonic',side_effect=[0,31]):
                with self.assertRaises(TimeoutError):setup.wait_native('adb',record)
            self.assertNotIn('nativeReady',record)

    def test_targets_are_explicit_and_normal_guard_is_unchanged(self):
        for serial in ('physical-phone','emulator-5554','emulator-5558'):
            with self.assertRaises(ValueError):setup.BootstrapCommands('adb',serial,{},10)
        accepted=setup.BootstrapCommands('adb','emulator-5556',{},10)
        self.assertEqual(accepted.serial,'emulator-5556')
        with self.assertRaises(ValueError):setup.normal.Commands('adb','emulator-5556',{},10)

    def test_actual_backend_and_both_addresses_are_required(self):
        valid='VLAN -1 (virtio-wifi):\n TCP[HOST_FORWARD] 115 127.0.0.1 5555 10.0.2.16 5555 0 0\n'
        setup.verify_forward(valid)
        invalid=[valid.replace('virtio-wifi','mynet'),valid.replace('10.0.2.16','10.0.2.15'),valid.replace('127.0.0.1','0.0.0.0'),valid.replace('5555','5557'),valid+valid,'']
        for value in invalid:
            with self.assertRaises(ValueError):setup.verify_forward(value)

    def test_monitor_rejects_unapproved_commands_before_connecting(self):
        with patch.object(setup.socket,'socket') as socket:
            with self.assertRaises(ValueError):setup.monitor(Path('/tmp/example.sock'),'system_reset')
            socket.assert_not_called()

    def test_unconfirmed_emulator_or_package_never_reaches_network_reset(self):
        for record in ({},{'confirmedQemu':True},{'disabledStateConfirmed':True}):
            commands=FakeCommands()
            with patch.object(setup.normal,'preflight'):
                with self.assertRaises(ValueError):setup.persistent_network(commands,record,{})
            self.assertEqual(commands.calls,[])

    def test_incomplete_teardown_does_not_connect_or_promote(self):
        commands=FakeCommands('16: wlan0 inet 10.0.2.16/24');record={'confirmedQemu':True,'disabledStateConfirmed':True}
        with patch.object(setup.normal,'preflight'),patch.object(setup.normal,'provision_sdk_wifi') as provision:
            with self.assertRaises(TimeoutError):setup.persistent_network(commands,record,{})
            provision.assert_not_called()
        self.assertNotIn('nativeReady',record)

    def test_missing_final_connectivity_is_rejected_after_provisioning(self):
        commands=FakeCommands();record={'confirmedQemu':True,'disabledStateConfirmed':True}
        with patch.object(setup.normal,'preflight'),patch.object(setup.normal,'provision_sdk_wifi') as provision,patch.object(setup.normal,'network_observation',return_value=False):
            with self.assertRaises(ValueError):setup.persistent_network(commands,record,{})
            provision.assert_called_once()
            self.assertEqual(provision.call_args.kwargs,{'reuse_observed_ap':True})
        self.assertNotIn('nativeReady',record)


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
    def invoke(self, tcpip=None, endpoint_error=None, native_error=None, *,
               scoped_route=None, addresses=None, unbound_route=None, record_extra=None):
        record = dict(record_extra or {}, confirmedQemu=True)
        original = Mock(BOOTSTRAP='emulator-5556')
        original.wait_native.side_effect = native_error
        events = []
        def command(parts, **kwargs):
            events.append(parts)
            if parts[-2:] == ['tcpip', '5555']:
                if isinstance(tcpip, BaseException):
                    raise tcpip
                return tcpip or completed('restarting in TCP mode port: 5555\n')
            if 'addr' in parts:
                return completed('16: wlan0 inet 10.0.2.16/24' if addresses is None else addresses)
            if 'from' in parts:
                return scoped_route() if callable(scoped_route) else scoped_route or completed('10.0.2.2 dev wlan0 src 10.0.2.16')
            if parts[-3:] == ['route', 'get', '10.0.2.2']:
                return unbound_route or completed('10.0.2.2 dev eth0 table 1015 src 10.0.2.15 uid 2000')
            return completed('0: from all lookup local' if 'rule' in parts else '10.0.2.0/24 dev wlan0 table 1016')
        def observed_monitor(path, operation):
            events.append(operation)
            return {'info network': NETWORK, 'help hostfwd_add': 'hostfwd_add [netdev_id] rule',
                    setup.RULE: ''}.get(operation, FORWARD if events.count('info usernet') > 1 else '')
        def ready(r):
            events.append('endpoint-probe')
            if endpoint_error:
                raise endpoint_error
            r['endpointProtocolReachable'] = True
        try:
            with patch.object(setup.subprocess, 'run', side_effect=command), \
                    patch.object(setup, 'monitor', side_effect=observed_monitor), \
                    patch.object(setup, 'wait_endpoint', side_effect=ready), \
                    patch.object(setup, 'announce_native', original.announce_native), \
                    patch.object(setup, 'wait_native', original.wait_native):
                setup.native_transport('adb', Path('/fixed/qemu.sock'), record)
        except BaseException as error:
            return record, original, events, error
        return record, original, events, None

    def test_backend_requires_actual_wifi_nic_user_link(self):
        setup.verify_backend(NETWORK)
        for text in (NETWORK.replace('virtio-wifi:', 'mynet:'), NETWORK.replace('type=user', 'type=tap'), ''):
            with self.assertRaises(ValueError):
                setup.verify_backend(text)

    def test_forward_requires_unique_loopback_wifi_rule(self):
        setup.verify_forward(FORWARD)
        for text in (FORWARD.replace('virtio-wifi', 'mynet'), FORWARD.replace('10.0.2.16', '10.0.2.15'),
                     FORWARD.replace('127.0.0.1', '0.0.0.0'), FORWARD + FORWARD, ''):
            with self.assertRaises(ValueError):
                setup.verify_forward(text)

    def test_forward_precedes_single_tcpip_and_no_vsock_command_follows(self):
        record, original, events, error = self.invoke()
        self.assertIsNone(error)
        tcpip = ['adb', '-s', 'emulator-5556', 'tcpip', '5555']
        self.assertEqual(events.count(tcpip), 1)
        self.assertLess(events.index(setup.RULE), events.index(tcpip))
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
        with patch.object(setup.socket, 'create_connection', return_value=stream):
            row = setup.endpoint_probe(setup.time.monotonic() + 8)
        self.assertEqual(row['responseCommand'], 'AUTH')
        self.assertEqual(stream.data, b'secret-auth-payload')
        self.assertEqual(len(stream.sent), 1)
        self.assertEqual(stream.sent[0][:4], b'CNXN')
        self.assertEqual(stream.sent[0][24:], b'host::\0')
        self.assertFalse(row['authResponseSent'])

    def test_short_invalid_or_clse_header_never_satisfies_endpoint_gate(self):
        stream = HeaderStream(magic=0)
        with patch.object(setup.socket, 'create_connection', return_value=stream):
            row = setup.endpoint_probe(setup.time.monotonic() + 8)
        self.assertNotIn('responseCommand', row)
        record = {}
        with patch.object(setup, 'endpoint_probe', return_value={'responseCommand': 'CLSE'}) as probe, \
                patch.object(setup.time, 'monotonic', side_effect=[0, 8]):
            with self.assertRaises(TimeoutError):
                setup.wait_endpoint(record)
        probe.assert_called_once_with(8)
        self.assertFalse(record['endpointProtocolReachable'])

    def test_monitor_rejects_unrelated_mutation(self):
        with patch.object(setup.socket, 'socket') as socket_call:
            with self.assertRaises(ValueError):
                setup.monitor(Path('/fixed/qemu.sock'), 'hostfwd_add mynet tcp:0.0.0.0:22-10.0.2.15:22')
        socket_call.assert_not_called()

    def test_wifi_source_return_route_does_not_relabel_cellular_default(self):
        cm = [{'value': {'activeNetwork': '101', 'transports': ['cellular'], 'usable': True}}]
        before = json.dumps(cm, sort_keys=True)
        for route in ('10.0.2.2 from 10.0.2.16 dev wlan0 table 1016 uid 2000\n    cache\n',
                      '10.0.2.2 dev wlan0 src 10.0.2.16 uid 2000\n    cache\n'):
            with self.subTest(route=route):
                record, original, events, error = self.invoke(
                    scoped_route=completed(route), record_extra={'networkObservations': cm})
                self.assertIsNone(error)
                self.assertEqual(json.dumps(record['networkObservations'], sort_keys=True), before)
                self.assertEqual(json.dumps(cm, sort_keys=True), before)
                scoped = ['adb', '-s', setup.BOOTSTRAP, 'shell', 'ip', '-4', 'route', 'get',
                          '10.0.2.2', 'from', '10.0.2.16']
                self.assertEqual(events.count(scoped), 1)
                self.assertEqual(record['returnRouteSource'], '10.0.2.16')
                self.assertEqual(record['routeObservations'][0]['routeSource'], '10.0.2.16')
                self.assertIn('dev eth0', record['routeDiagnostics'][0]['stdout'])
                self.assertTrue(all(row['diagnosticOnly'] for row in record['routeDiagnostics']))
                self.assertTrue(all(not row['diagnosticOnly'] for row in record['routeReadinessCommands']))
                original.announce_native.assert_called_once_with(record)
                original.wait_native.assert_called_once_with('adb', record)

    def test_unbound_success_cannot_replace_source_device_or_address_evidence(self):
        routes = [('10.0.2.2 from 10.0.2.16 dev eth0 src 10.0.2.15', None),
                  ('10.0.2.2 dev wlan0 src 10.0.2.15', None),
                  ('10.0.2.2 from 10.0.2.16 dev wlan0 src 10.0.2.15', None),
                  ('10.0.2.2 from 10.0.2.16 dev wlan0-extra', None),
                  ('10.0.2.2 dev wlan0', None),
                  ('10.0.2.2 from 10.0.2.16 dev wlan0', '16: wlan0 inet 10.0.2.15/24')]
        for route, addresses in routes:
            with self.subTest(route=route, addresses=addresses):
                clock = [0.0]
                with patch.object(setup.time, 'monotonic', side_effect=lambda: clock[0]), \
                        patch.object(setup.time, 'sleep', side_effect=lambda n: clock.__setitem__(0, clock[0] + n)):
                    record, original, events, error = self.invoke(
                        scoped_route=completed(route), addresses=addresses,
                        unbound_route=completed('10.0.2.2 dev wlan0 src 10.0.2.16'))
                self.assertIsInstance(error, TimeoutError)
                self.assertNotIn(setup.RULE, events)
                original.announce_native.assert_not_called()
                original.wait_native.assert_not_called()
                self.assertNotIn('nativeReady', record)
                self.assertEqual(clock[0], 30)

    def test_failed_source_query_never_creates_forward_or_runs_tcpip(self):
        clock = [0.0]
        with patch.object(setup.time, 'monotonic', side_effect=lambda: clock[0]), \
                patch.object(setup.time, 'sleep', side_effect=lambda n: clock.__setitem__(0, clock[0] + n)):
            record, original, events, error = self.invoke(
                scoped_route=completed('10.0.2.2 from 10.0.2.16 dev wlan0', 2, 'unsupported query'))
        self.assertIsInstance(error, TimeoutError)
        self.assertTrue(all(row['routeExit'] == 2 for row in record['routeObservations']))
        self.assertNotIn(setup.RULE, events)
        self.assertNotIn(['adb', '-s', setup.BOOTSTRAP, 'tcpip', '5555'], events)
        original.announce_native.assert_not_called()
        original.wait_native.assert_not_called()

    def test_diagnostic_reads_are_once_and_do_not_replace_transport_gates(self):
        replies = iter([completed('10.0.2.2 from 10.0.2.16 dev eth0'),
                        completed('10.0.2.2 from 10.0.2.16 dev wlan0')])
        with patch.object(setup.time, 'sleep'):
            record, original, events, error = self.invoke(
                scoped_route=lambda: next(replies), endpoint_error=TimeoutError('actual endpoint absent'))
        self.assertIsInstance(error, TimeoutError)
        self.assertEqual(len(record['routeObservations']), 2)
        self.assertEqual(len(record['routeDiagnostics']), 3)
        diagnostics = [row['command'] for row in record['routeDiagnostics']]
        self.assertEqual(diagnostics, [
            ['adb', '-s', setup.BOOTSTRAP, 'shell', 'ip', '-4', 'route', 'get', '10.0.2.2'],
            ['adb', '-s', setup.BOOTSTRAP, 'shell', 'ip', '-4', 'rule', 'show'],
            ['adb', '-s', setup.BOOTSTRAP, 'shell', 'ip', '-4', 'route', 'show', 'table', 'all']])
        self.assertTrue(all(events.count(command) == 1 for command in diagnostics))
        self.assertEqual(events.count(['adb', '-s', setup.BOOTSTRAP, 'tcpip', '5555']), 1)
        original.announce_native.assert_not_called()
        original.wait_native.assert_not_called()

    def test_all_route_reads_share_original_deadline_and_eight_second_cap(self):
        for late_success, diagnostic_timeouts in ((False, False), (True, False), (False, True)):
            with self.subTest(late_success=late_success, diagnostic_timeouts=diagnostic_timeouts):
                clock, calls, record = [0.0], [], {'confirmedQemu': True}
                def command(parts, **options):
                    timeout = options['timeout'];calls.append((parts, timeout, clock[0]))
                    duration = 2 if 'from' in parts else 5 if 'addr' in parts else 9 if diagnostic_timeouts else 8
                    clock[0] += duration if late_success else min(duration, timeout)
                    if duration > timeout and not late_success:
                        raise subprocess.TimeoutExpired(parts, timeout, output=b'partial', stderr=b'bounded')
                    return completed('16: wlan0 inet 10.0.2.16/24' if 'addr' in parts
                                     else '10.0.2.2 from 10.0.2.16 dev wlan0')
                with patch.object(setup.subprocess, 'run', side_effect=command), \
                        patch.object(setup.time, 'monotonic', side_effect=lambda: clock[0]), \
                        patch.object(setup, 'monitor') as monitor:
                    with self.assertRaises(TimeoutError if late_success else subprocess.TimeoutExpired):
                        setup.native_transport('adb', Path('/fixed/qemu.sock'), record)
                self.assertEqual([call[1] for call in calls], [8, 8, 8, 6, 1])
                self.assertTrue(all(call[1] <= 8 for call in calls))
                self.assertEqual(len(record['routeDiagnostics']), 3)
                if diagnostic_timeouts:
                    self.assertTrue(all(row['timedOut'] and row['stdout'] == 'partial'
                                        for row in record['routeDiagnostics']))
                self.assertTrue(all(row['deadlineMonotonic'] == 30
                                    for row in record['routeDiagnostics'] + record['routeReadinessCommands']))
                if not late_success:
                    self.assertEqual(clock[0], 30)
                    self.assertTrue(record['routeReadinessCommands'][-1]['timedOut'])
                    self.assertEqual(record['routeReadinessCommands'][-1]['stdout'], 'partial')
                monitor.assert_not_called()
                self.assertNotIn('tcpipCommand', record)



class PreparationTransportBoundary(Exception):
    """Stop the host control before native TCP; never claim Android acceptance."""


class PreparationBudgetControls(unittest.TestCase):
    """Complete production setup methods with counterfeit adb replies and clock.

    Git/APK discovery is a host boundary double. Commands.run, both provisioning
    passes, all CM parsing/nonce/installed-identity validation and main's failure
    persistence are real. Timing is a deterministic control, not an Android replay.
    """
    def invoke(self, *, budget=None, edit_final=None, final_seconds=7,
               timeout_with_complete_stdout=False, final_code=0, never_ready=False,
               real_native_path=False, native_path_route=None):
        spec=importlib.util.spec_from_file_location('budget_observation_controls',
            Path(__file__).with_name('gecko_emulator_bootstrap_test.py'))
        controls=importlib.util.module_from_spec(spec);spec.loader.exec_module(controls)
        expected=controls.identity();clock=controls.Clock();calls=[];cm_count=0
        # A 31.98s valid preparation prefix, then a separate seven-second read.
        # No assertion depends on a guessed decomposition of the original CI.
        durations=[6.7,2.8,2,1.7,2.2,2.6,2,1.5,6.1]
        usable=[True,False,False,False,True,True,False,False,True]

        def reply(command, **options):
            nonlocal cm_count
            self.assertEqual(command[:3],['adb','-s',setup.BOOTSTRAP])
            parts=tuple(command[3:]);duration=.02;stdout='';code=0
            if parts==('shell','getprop','ro.kernel.qemu'):stdout='1'
            elif parts[:4]==('shell','pm','list','packages'):stdout='package:'+setup.normal.PACKAGE
            elif parts==('shell','cmd','wifi','status'):stdout='Wifi is enabled'
            elif parts==('shell','cmd','wifi','list-scan-results'):
                stdout='00:13:10:85:fe:01 2447 -50 0 AndroidWifi [ESS]'
            elif parts==('shell','ip','-4','-o','addr','show','wlan0') and cm_count>=10:
                stdout='16: wlan0 inet 10.0.2.16/24'
            elif parts==('shell','ip','-4','route','get','10.0.2.2','from','10.0.2.16'):
                stdout=native_path_route() if callable(native_path_route) else native_path_route or '10.0.2.2 from 10.0.2.16 dev wlan0'
            elif parts[:4]==('exec-out','content','read','--uri'):
                parsed=urlsplit(parts[4]);self.assertEqual(parsed.netloc,setup.normal.AUTHORITY)
                self.assertEqual(parsed.path,'/default-network')
                value=controls.observation();value['runNonce']=parse_qs(parsed.query)['runNonce'][0]
                value['transports']=['wifi'];cm_count+=1
                ready=usable[cm_count-1] if cm_count<=len(usable) else True
                duration=durations[cm_count-1] if cm_count<=len(durations) else final_seconds
                if never_ready and cm_count>=7:ready=False;duration=2
                if not ready:
                    value.update(activeNetwork='',activeNetworkAfter='',capabilitiesPresent=False,
                                 internetCapability=False,stableDuringRead=False,usable=False)
                if cm_count==10 and not never_ready:
                    if edit_final:edit_final(value)
                    code=final_code
                stdout=json.dumps(value)
            timeout=options['timeout'];calls.append(dict(command=command,timeout=timeout,started=clock.now()))
            if duration>timeout or (cm_count==10 and timeout_with_complete_stdout):
                clock.sleep(timeout)
                raise subprocess.TimeoutExpired(command,timeout,
                    output=stdout.encode() if timeout_with_complete_stdout else b'',stderr=b'')
            clock.sleep(duration)
            return subprocess.CompletedProcess(command,code,stdout=stdout,
                                               stderr='synthetic failure' if code else '')

        def git(command, **unused):
            parts=command[1:]
            if parts==['status','--porcelain']:return ''
            if parts==['rev-parse','HEAD']:return expected['sourceCommit']
            if parts==['rev-parse','HEAD^{tree}']:return expected['sourceTree']
            if parts==['show',expected['sourceCommit']+':third-party/sdk/geckoview-157.0.1-editable-selection.json']:
                # The reused historical host identity has no derived manifest.
                # Keep the SDK validator's real missing-source behavior.
                raise subprocess.CalledProcessError(128,command,stderr=b'synthetic source has no manifest')
            raise AssertionError(command)

        error=None
        with tempfile.TemporaryDirectory() as temporary:
            root=Path(temporary);(root/'app').mkdir()
            (root/'app/build.gradle').write_text("versionName '1.6.0'\nversionCode 51\n")
            with ExitStack() as stack:
                stack.enter_context(patch.object(setup,'ROOT',root))
                stack.enter_context(patch.object(setup.sys,'argv',['prepare_native_adb.py','--adb','adb',
                    '--apk',str(root/'synthetic.apk'),'--monitor',str(root/'synthetic.sock')]))
                stack.enter_context(patch.dict(setup.os.environ,{'GITHUB_RUN_ID':'123','GITHUB_RUN_ATTEMPT':'1'}))
                stack.enter_context(patch.object(setup.subprocess,'check_output',side_effect=git))
                stack.enter_context(patch.object(setup.normal,'expected_build',return_value=expected))
                stack.enter_context(patch.object(setup.subprocess,'run',side_effect=reply))
                stack.enter_context(patch.object(setup.time,'monotonic',clock.now))
                stack.enter_context(patch.object(setup.time,'sleep',clock.sleep))
                # Isolate the original CM-budget controls; the new path phase
                # runs unmocked in profile_native_wifi_path_test.py controls.
                if not real_native_path:
                    stack.enter_context(patch.object(setup,'prepare_native_wifi_path'))
                transport=stack.enter_context(patch.object(setup,'native_transport',side_effect=PreparationTransportBoundary))
                if budget is not None:
                    stack.enter_context(patch.object(setup,'PREPARATION_TIMEOUT_SECONDS',budget))
                try:setup.main()
                except BaseException as failure:error=failure
            receipt=json.loads((root/'work/gecko-integration/native-adb-setup-results.json').read_text())
        self.assertFalse(receipt['applicationAcceptance'])
        self.assertFalse(receipt['originalWorkloadInvoked'])
        self.assertNotIn('nativeReady',receipt)
        # The deliberate transport boundary, like any error, remains failed in
        # main's receipt. Passing a host preparation control is not device proof.
        self.assertEqual(receipt['status'],'failed')
        return receipt,error,calls,transport.call_count,clock.now()

    def test_fixed_45_budget_leaves_full_command_cap_after_both_validated_cm_reads(self):
        receipt,error,calls,transport,ended=self.invoke()
        self.assertIsInstance(error,PreparationTransportBoundary);self.assertEqual(transport,1)
        self.assertEqual(receipt['preparationBudgetSeconds'],45)
        self.assertEqual(receipt['preparationStartedAt'],0)
        self.assertEqual(receipt['preparationDeadlineMonotonic'],45)
        self.assertAlmostEqual(calls[-1]['started'],31.98)
        self.assertAlmostEqual(ended,38.98);self.assertEqual(calls[-1]['timeout'],8)
        self.assertEqual([v['phase'] for v in receipt['networkObservations']][-2:],
            ['after-persistent-sdk-wifi','persistent-sdk-wifi-confirmation'])
        final=receipt['networkObservations'][-2:]
        self.assertTrue(all(v['value']['usable'] for v in final))
        self.assertNotEqual(final[0]['runNonce'],final[1]['runNonce'])
        self.assertTrue(all(c['timeoutSeconds']<=8 and c['deadlineMonotonic']<=45 for c in receipt['commands']))
        self.assertEqual(receipt['sdkWifiProvisioningStages'][-1]['apSelection'],'reused-observed-AP')

    def test_original_33_budget_crops_second_read_and_cannot_promote_first_success(self):
        receipt,error,calls,transport,ended=self.invoke(budget=33)
        self.assertIsInstance(error,subprocess.TimeoutExpired);self.assertEqual(transport,0)
        self.assertAlmostEqual(calls[-1]['timeout'],1.02);self.assertAlmostEqual(ended,33)
        self.assertEqual(len(receipt['networkObservations']),9)
        self.assertEqual(receipt['networkObservations'][-1]['phase'],'after-persistent-sdk-wifi')
        self.assertTrue(receipt['networkObservations'][-1]['value']['usable'])
        self.assertTrue(receipt['commands'][-1]['timedOut'])
        self.assertEqual(receipt['preparationDeadlineMonotonic'],33)

    def test_45_budget_does_not_accept_false_or_foreign_second_receipt(self):
        def unusable(value):
            value.update(activeNetwork='',activeNetworkAfter='',capabilitiesPresent=False,
                         internetCapability=False,stableDuringRead=False,usable=False)
        edits=[unusable,lambda v:v.update(runNonce='f'*32),lambda v:v.update(sourceCommit='f'*40),
               lambda v:v['buildIdentity'].update(apkSha256='f'*64),
               lambda v:v['buildIdentity'].update(dirtySource=True)]
        for edit in edits:
            with self.subTest(edit=edit):
                receipt,error,calls,transport,ended=self.invoke(edit_final=edit)
                self.assertIsInstance(error,ValueError);self.assertEqual(transport,0)
                self.assertEqual(receipt['preparationDeadlineMonotonic'],45)
                self.assertEqual(len(receipt['commands']),29)
                self.assertEqual(calls[-1]['timeout'],8)

    def test_per_command_timeout_still_fails_with_global_budget_remaining(self):
        receipt,error,calls,transport,ended=self.invoke(final_seconds=9)
        self.assertIsInstance(error,subprocess.TimeoutExpired);self.assertEqual(transport,0)
        self.assertEqual(calls[-1]['timeout'],8);self.assertLess(ended,45)
        self.assertTrue(receipt['commands'][-1]['timedOut'])
        self.assertEqual(len(receipt['networkObservations']),9)

    def test_complete_looking_stdout_from_timeout_or_nonzero_exit_cannot_pass(self):
        for options in ({'timeout_with_complete_stdout':True},{'final_code':1}):
            with self.subTest(options=options):
                receipt,error,calls,transport,ended=self.invoke(**options)
                self.assertIsInstance(error,subprocess.SubprocessError);self.assertEqual(transport,0)
                self.assertTrue(json.loads(receipt['commands'][-1]['stdout'])['usable'])
                self.assertEqual(len(receipt['networkObservations']),9)
                self.assertEqual(receipt['preparationDeadlineMonotonic'],45)

    def test_missing_connectivity_expires_without_resetting_shared_45_budget(self):
        receipt,error,calls,transport,ended=self.invoke(never_ready=True)
        self.assertIsInstance(error,(TimeoutError,subprocess.TimeoutExpired));self.assertEqual(transport,0)
        self.assertLessEqual(ended,45);self.assertGreaterEqual(ended,44)
        self.assertEqual(receipt['preparationDeadlineMonotonic'],45)
        self.assertFalse(receipt['networkObservations'][-1]['value']['usable'])
        self.assertNotIn('persistent-sdk-wifi-confirmation',[v['phase'] for v in receipt['networkObservations']])
        self.assertTrue(all(c['deadlineMonotonic']<=45 for c in receipt['commands']))

    def test_expired_45_budget_refuses_a_command_before_invoking_subprocess(self):
        record={'commands':[]};commands=setup.BootstrapCommands('adb',setup.BOOTSTRAP,record,45)
        with patch.object(setup.time,'monotonic',return_value=45),patch.object(setup.subprocess,'run') as run:
            with self.assertRaises(TimeoutError):commands.run('shell','getprop','ro.kernel.qemu')
        run.assert_not_called();self.assertEqual(commands.deadline,45);self.assertEqual(record['commands'],[])


if __name__=='__main__':unittest.main()
