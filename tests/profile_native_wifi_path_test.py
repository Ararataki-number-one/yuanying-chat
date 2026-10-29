"""Counterfeit host controls for native-bootstrap preparation, never Android proof."""
import ast
from contextlib import ExitStack
import hashlib
import importlib.util
import json
from pathlib import Path
import subprocess
import unittest
from unittest.mock import Mock, patch
from urllib.parse import parse_qs, urlsplit


ROOT = Path(__file__).resolve().parents[1]


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


old = load('native_wifi_original_controls', ROOT / 'tests/gecko_native_adb_setup_test.py')
controls = load('native_wifi_cm_controls', ROOT / 'tests/gecko_emulator_bootstrap_test.py')
setup = old.setup
ADDRESS = '16: wlan0 inet 10.0.2.16/24'
GOOD = '10.0.2.2 from 10.0.2.16 dev wlan0 table 1016 uid 2000\n    cache\n'
BAD = '10.0.2.2 from 10.0.2.16 dev eth0 table 1015 uid 2000\n    cache\n'


class NativeWifiPathControls(unittest.TestCase):
    def invoke(self, *, routes=(GOOD,), addresses=ADDRESS, deadline=45, started=0,
               scan='00:13:10:85:fe:01 2447 -50 0 AndroidWifi [ESS]',
               edit_cm=None, edit_before=None, edit_reply=None, route_failure=None,
               after_repair=None):
        identity = controls.identity()
        record = dict(commands=[], networkObservations=[], sdkWifiProvisioningStages=[],
                      confirmedQemu=True, disabledStateConfirmed=True,
                      sourceCommit=identity['sourceCommit'], sourceTree=identity['sourceTree'])
        commands = setup.BootstrapCommands('adb', setup.BOOTSTRAP, record, deadline)
        clock, calls, route_index = [started], [], [0]
        if edit_before:
            edit_before(commands, record, identity)

        def reply(command, **options):
            self.assertEqual(command[:3], ['adb', '-s', setup.BOOTSTRAP])
            parts = tuple(command[3:])
            calls.append(parts)
            if parts == ('shell', 'ip', '-4', '-o', 'addr', 'show', 'wlan0'):
                stdout = addresses() if callable(addresses) else addresses
            elif parts == ('shell', 'ip', '-4', 'route', 'get', '10.0.2.2', 'from', '10.0.2.16'):
                failure = route_failure() if callable(route_failure) else route_failure
                if failure:
                    return subprocess.CompletedProcess(command, 2, '', failure)
                stdout = routes[min(route_index[0], len(routes) - 1)]
                route_index[0] += 1
            elif parts == ('shell', 'cmd', 'wifi', 'status'):
                stdout = 'Wifi is enabled'
            elif parts == ('shell', 'cmd', 'wifi', 'list-scan-results'):
                stdout = scan
            elif parts[:4] == ('exec-out', 'content', 'read', '--uri'):
                parsed = urlsplit(parts[4])
                self.assertEqual(parsed.netloc, setup.normal.AUTHORITY)
                value = controls.observation()
                value['runNonce'] = parse_qs(parsed.query)['runNonce'][0]
                value['transports'] = ['cellular']
                if edit_cm:
                    edit_cm(value)
                stdout = json.dumps(value)
            elif parts in (('shell', 'cmd', 'wifi', 'set-wifi-enabled', 'enabled'),
                            ('shell', 'cmd', 'wifi', 'start-scan'),
                            ('shell', 'cmd', 'wifi', 'connect-network', 'AndroidWifi', 'open')):
                stdout = ''
            else:
                raise AssertionError('Unexpected preparation mutation/read: ' + repr(parts))
            if edit_reply:
                edit_reply(parts, commands, record, identity)
            return subprocess.CompletedProcess(command, 0, stdout, '')

        error = None
        original_provision = setup.normal.provision_sdk_wifi

        def provision(*args, **kwargs):
            original_provision(*args, **kwargs)
            if after_repair:
                after_repair(commands, record, identity)

        def git(command, **unused):
            expected = ['git', 'show', identity['sourceCommit'] +
                        ':third-party/sdk/geckoview-157.0.1-editable-selection.json']
            if command == expected:
                # The reused synthetic identity has no derived SDK manifest.
                # Exercise the real validator's missing-manifest branch.
                raise subprocess.CalledProcessError(128, command, stderr=b'synthetic source has no manifest')
            raise AssertionError(command)

        with patch.object(setup.subprocess, 'run', side_effect=reply), \
                patch.object(setup.subprocess, 'check_output', side_effect=git), \
                patch.object(setup.time, 'monotonic', side_effect=lambda: clock[0]), \
                patch.object(setup.time, 'sleep', side_effect=lambda n: clock.__setitem__(0, clock[0] + n)), \
                patch.object(setup.normal, 'provision_sdk_wifi', side_effect=provision) as repair:
            try:
                setup.prepare_native_wifi_path(commands, record, identity)
            except BaseException as failure:
                error = failure
        self.last_commands = commands
        return record, error, calls, repair, clock[0]

    def test_good_source_path_needs_no_repair_even_when_cm_default_is_cellular(self):
        record, error, calls, repair, elapsed = self.invoke()
        self.assertIsNone(error)
        self.assertEqual(len(calls), 2)
        self.assertEqual(record['nativeWifiPathPreparation']['status'], 'passed')
        self.assertFalse(record['nativeWifiPathPreparation']['repairAttempted'])
        self.assertEqual(record['nativeWifiPathPreparation']['repairAttempts'], 0)
        repair.assert_not_called()
        self.assertEqual(elapsed, 0)

    def test_bad_then_good_uses_one_fresh_sdk_scan_connect_without_relabeling_cm(self):
        record, error, calls, repair, elapsed = self.invoke(routes=(BAD, GOOD))
        self.assertIsNone(error)
        stage = record['nativeWifiPathPreparation']
        self.assertEqual([v['ready'] for v in stage['observations']], [False, True])
        self.assertEqual(stage['repairAttempts'], 1)
        repair.assert_called_once()
        self.assertEqual(repair.call_args.kwargs, {'reuse_observed_ap': False})
        self.assertEqual(calls.count(('shell', 'cmd', 'wifi', 'start-scan')), 1)
        self.assertEqual(calls.count(('shell', 'cmd', 'wifi', 'connect-network', 'AndroidWifi', 'open')), 1)
        self.assertEqual(record['sdkWifiProvisioningStages'][0]['apSelection'], 'current-scan')
        self.assertEqual(record['networkObservations'][0]['value']['transports'], ['cellular'])
        self.assertEqual(record['networkObservations'][0]['value']['activeNetwork'], '101')
        self.assertFalse(stage['applicationAcceptance'])
        self.assertFalse(stage['originalWorkloadInvoked'])
        self.assertLessEqual(elapsed, 45)

    def test_persistent_bad_path_expires_original_deadline_without_second_repair(self):
        record, error, calls, repair, elapsed = self.invoke(routes=(BAD,))
        self.assertIsInstance(error, TimeoutError)
        self.assertEqual(elapsed, 45)
        self.assertEqual(record['nativeWifiPathPreparation']['deadlineMonotonic'], 45)
        self.assertEqual(record['nativeWifiPathPreparation']['status'], 'failed')
        repair.assert_called_once()
        self.assertEqual(calls.count(('shell', 'cmd', 'wifi', 'connect-network', 'AndroidWifi', 'open')), 1)
        self.assertTrue(all(v['deadlineMonotonic'] <= 45 and v['timeoutSeconds'] <= 8
                            for v in record['commands']))

    def test_insufficient_or_expired_budget_cannot_begin_repair_or_gain_new_time(self):
        for started in (35, 44, 45, 46):
            with self.subTest(started=started):
                record, error, calls, repair, elapsed = self.invoke(routes=(BAD,), started=started)
                self.assertIsInstance(error, TimeoutError)
                repair.assert_not_called()
                self.assertFalse(record['nativeWifiPathPreparation']['repairAttempted'])
                self.assertEqual(elapsed, started)
                self.assertEqual(len(calls), 0 if started >= 45 else 2)

    def test_unknown_or_foreign_source_observations_cannot_authorize_repair(self):
        cases = [('', ADDRESS), ('garbage', ADDRESS),
                 (BAD.replace('10.0.2.16', '10.0.2.15'), ADDRESS),
                 (GOOD.replace('dev wlan0', 'dev unknown0'), ADDRESS),
                 (GOOD + 'unexpected\n', ADDRESS),
                 (GOOD.replace('dev wlan0', 'dev wlan0 dev eth0'), ADDRESS),
                 (BAD, ADDRESS.replace('10.0.2.16', '10.0.2.15')),
                 (BAD, ADDRESS + '\n17: wlan0 inet 10.0.2.17/24')]
        for route, address in cases:
            with self.subTest(route=route, address=address):
                record, error, calls, repair, elapsed = self.invoke(routes=(route,), addresses=address)
                self.assertIsInstance(error, ValueError)
                repair.assert_not_called()
                self.assertFalse(record['nativeWifiPathPreparation']['repairAttempted'])

    def test_actual_ip_oneline_metadata_passes_but_unknown_address_tail_cannot_repair(self):
        actual = ('16: wlan0    inet 10.0.2.16/24 brd 10.0.2.255 scope global wlan0\\'
                  '       valid_lft forever preferred_lft forever')
        for address in (actual, ADDRESS + ' scope global wlan0',
                        ADDRESS + ' brd 10.0.2.255 scope global wlan0\\ valid_lft 30sec preferred_lft 20sec'):
            with self.subTest(address=address):
                record, error, calls, repair, elapsed = self.invoke(routes=(BAD, GOOD), addresses=address)
                self.assertIsNone(error)
                repair.assert_called_once()
        for address in (ADDRESS + ' garbage', actual + ' garbage',
                        ADDRESS + ' brd 999.0.2.255 scope global wlan0',
                        ADDRESS + ' scope unknown wlan0', ADDRESS + ' scope global wlan0\\',
                        actual.replace('valid_lft forever', 'valid_lft unknown')):
            with self.subTest(address=address):
                record, error, calls, repair, elapsed = self.invoke(routes=(BAD, GOOD), addresses=address)
                self.assertIsInstance(error, ValueError)
                repair.assert_not_called()
                self.assertEqual(sum('from' in c for c in calls), 0)
                self.assertFalse(record['nativeWifiPathPreparation']['repairAttempted'])

    def test_failed_source_query_is_not_an_instruction_to_repair(self):
        record, error, calls, repair, elapsed = self.invoke(route_failure='unreachable')
        self.assertIsInstance(error, ValueError)
        repair.assert_not_called()
        self.assertFalse(record['nativeWifiPathPreparation']['repairAttempted'])

    def test_empty_address_pending_then_good_never_queries_missing_source_or_repairs(self):
        addresses = iter(['', ADDRESS])
        record, error, calls, repair, elapsed = self.invoke(addresses=lambda: next(addresses))
        self.assertIsNone(error)
        self.assertEqual([v['ready'] for v in record['nativeWifiPathPreparation']['observations']], [None, True])
        self.assertEqual(sum('from' in c for c in calls), 1)
        self.assertEqual(elapsed, .25)
        repair.assert_not_called()

    def test_empty_address_pending_expires_45_seconds_without_source_query_or_repair(self):
        record, error, calls, repair, elapsed = self.invoke(addresses='')
        self.assertIsInstance(error, TimeoutError)
        self.assertEqual(elapsed, 45)
        self.assertFalse(any('from' in c for c in calls))
        repair.assert_not_called()
        self.assertFalse(record['nativeWifiPathPreparation']['repairAttempted'])

    def test_recorded_known_route_failure_can_be_pending_but_unknown_errors_cannot(self):
        for known in ('RTNETLINK answers: Network is unreachable',
                      'RTNETLINK answers: Cannot assign requested address'):
            with self.subTest(known=known):
                failures = iter([known, None])
                record, error, calls, repair, elapsed = self.invoke(route_failure=lambda: next(failures))
                self.assertIsNone(error)
                rows = record['nativeWifiPathPreparation']['observations']
                self.assertEqual([v['ready'] for v in rows], [None, True])
                self.assertEqual(rows[0]['routeExit'], 2)
                self.assertEqual(rows[0]['routeErrors'], known)
                repair.assert_not_called()
                record, error, calls, repair, elapsed = self.invoke(route_failure=known)
                self.assertIsInstance(error, TimeoutError)
                self.assertEqual(elapsed, 45)
                repair.assert_not_called()
        for unknown in ('RTNETLINK answers: Operation not permitted',
                        'RTNETLINK answers: Invalid argument', 'unknown failure'):
            with self.subTest(unknown=unknown):
                record, error, calls, repair, elapsed = self.invoke(route_failure=unknown)
                self.assertIsInstance(error, ValueError)
                self.assertEqual(elapsed, 0)
                repair.assert_not_called()

    def test_one_repair_can_be_followed_by_pending_dhcp_then_good_without_second_repair(self):
        addresses = iter([ADDRESS, '', ADDRESS])
        record, error, calls, repair, elapsed = self.invoke(
            routes=(BAD, GOOD), addresses=lambda: next(addresses))
        self.assertIsNone(error)
        self.assertEqual([v['ready'] for v in record['nativeWifiPathPreparation']['observations']],
                         [False, None, True])
        repair.assert_called_once()
        self.assertEqual(record['nativeWifiPathPreparation']['repairAttempts'], 1)
        self.assertEqual(sum('from' in c for c in calls), 2)

    def test_wrong_ap_never_connects_and_foreign_cm_never_promotes(self):
        record, error, calls, repair, elapsed = self.invoke(routes=(BAD,), scan='00:11:22:33:44:55 2412 -40 0 WrongAP [ESS]')
        self.assertIsInstance(error, ValueError)
        self.assertFalse(any(c[:4] == ('shell', 'cmd', 'wifi', 'connect-network') for c in calls))
        for edit in (lambda v: v.update(sourceCommit='f' * 40),
                     lambda v: v.update(runNonce='f' * 32),
                     lambda v: v['buildIdentity'].update(apkSha256='f' * 64)):
            with self.subTest(edit=edit):
                record, error, calls, repair, elapsed = self.invoke(routes=(BAD, GOOD), edit_cm=edit)
                self.assertIsInstance(error, ValueError)
                self.assertEqual(len(record['nativeWifiPathPreparation']['observations']), 1)
                self.assertEqual(record['nativeWifiPathPreparation']['status'], 'failed')

    def test_initial_owner_source_or_trust_mismatch_prevents_every_probe_and_repair(self):
        edits = [lambda c, r, i: setattr(c, 'serial', 'emulator-5554'),
                 lambda c, r, i: setattr(c, 'record', {}),
                 lambda c, r, i: r.update(sourceCommit='f' * 40),
                 lambda c, r, i: r.update(sourceTree='f' * 40),
                 lambda c, r, i: r.update(confirmedQemu=False),
                 lambda c, r, i: r.update(disabledStateConfirmed=False),
                 lambda c, r, i: r.update(nativeWifiPathPreparation={}),
                 lambda c, r, i: setattr(c, 'run', lambda *a, **k: '')]
        for edit in edits:
            with self.subTest(edit=edit):
                record, error, calls, repair, elapsed = self.invoke(edit_before=edit)
                self.assertIsInstance(error, ValueError)
                self.assertEqual(calls, [])
                repair.assert_not_called()

    def test_owner_or_identity_change_between_commands_or_after_repair_fails_closed(self):
        edits = [lambda c, r, i: setattr(c, 'serial', 'emulator-5554'),
                 lambda c, r, i: setattr(c, 'executable', 'other-adb'),
                 lambda c, r, i: setattr(c, 'deadline', 46),
                 lambda c, r, i: setattr(c, '_sdk_wifi_session', object()),
                 lambda c, r, i: r.update(nativeWifiPathPreparation={}),
                 lambda c, r, i: i.update(version='foreign')]
        for edit in edits:
            with self.subTest(edit=edit):
                record, error, calls, repair, elapsed = self.invoke(
                    edit_reply=lambda p, c, r, i: edit(c, r, i))
                self.assertIsInstance(error, ValueError)
                self.assertEqual(len(calls), 1)
                repair.assert_not_called()
                record, error, calls, repair, elapsed = self.invoke(routes=(BAD, GOOD), after_repair=edit)
                self.assertIsInstance(error, ValueError)
                self.assertEqual(sum('from' in c for c in calls), 1)

    def test_repair_checks_owner_after_each_original_command_before_any_following_command(self):
        edits = [lambda c, r, i: setattr(c, 'serial', 'emulator-5554'),
                 lambda c, r, i: setattr(c, 'executable', 'other-adb'),
                 lambda c, r, i: setattr(c, 'deadline', 46),
                 lambda c, r, i: setattr(c, '_sdk_wifi_session', object()),
                 lambda c, r, i: setattr(c, 'run', lambda *a, **k: ''),
                 lambda c, r, i: r.update(sourceCommit='f' * 40),
                 lambda c, r, i: i.update(version='foreign')]
        for edit in edits:
            with self.subTest(edit=edit):
                def during_repair(parts, commands, record, identity):
                    if parts == ('shell', 'cmd', 'wifi', 'set-wifi-enabled', 'enabled'):
                        edit(commands, record, identity)
                record, error, calls, repair, elapsed = self.invoke(
                    routes=(BAD, GOOD), edit_reply=during_repair)
                self.assertIsInstance(error, ValueError)
                self.assertEqual(len(calls), 3)  # Initial pair, then one repair command.
                self.assertEqual(calls[-1], ('shell', 'cmd', 'wifi', 'set-wifi-enabled', 'enabled'))
                self.assertFalse(any('connect-network' in c for c in calls))
                self.assertNotIn('run', vars(self.last_commands))
                self.assertIs(self.last_commands.run.__func__, setup.BootstrapCommands.run)

    def test_repair_command_dispatch_is_restored_on_success_and_failure(self):
        for options in ({'routes': (BAD, GOOD)},
                        {'routes': (BAD, GOOD), 'scan': '00:11:22:33:44:55 2412 -40 0 WrongAP [ESS]'},
                        {'routes': (BAD, GOOD), 'edit_cm': lambda v: v.update(sourceCommit='f' * 40)},
                        {'routes': (BAD, GOOD), 'after_repair': lambda c, r, i: setattr(c, 'run', lambda *a, **k: '')}):
            with self.subTest(options=options):
                record, error, calls, repair, elapsed = self.invoke(**options)
                if len(options) == 1:
                    self.assertIsNone(error)
                else:
                    self.assertIsInstance(error, ValueError)
                repair.assert_called_once()
                self.assertNotIn('run', vars(self.last_commands))
                self.assertIs(self.last_commands.run.__func__, setup.BootstrapCommands.run)

    def test_original_cellular_usable_shortcut_is_reproduced_but_new_main_checks_path(self):
        source = (ROOT / 'tools/gecko/prepare_native_adb.py').read_text()
        node = next(n for n in ast.parse(source).body if isinstance(n, ast.FunctionDef) and n.name == 'persistent_network')
        current = ast.get_source_segment(source, node)
        addition = '\n    prepare_native_wifi_path(commands, record, identity)'
        self.assertEqual(current.count(addition), 1)
        original = current.replace(addition, '', 1)
        self.assertEqual(hashlib.sha256(original.encode()).hexdigest(),
                         '7ba14f08d40864df8e0d414d5f7549c677fabb0a25eb091148ae5d85064eadec')
        record = dict(confirmedQemu=True, disabledStateConfirmed=True, networkObservations=[])
        def cellular(*args):
            record['networkObservations'].append(dict(value=dict(
                usable=True, activeNetwork='101', transports=['cellular'])))
            return True
        network = Mock()
        network.network_observation.side_effect = cellular
        commands = Mock()
        commands.run.return_value = ''  # Valid completed Wi-Fi teardown.
        namespace = dict(normal=network)
        exec(compile(original, '<exact-original-persistent-network>', 'exec'), namespace)
        namespace['persistent_network'](commands, record, controls.identity())
        self.assertEqual(record['networkObservations'][0]['value']['transports'], ['cellular'])
        self.assertEqual(commands.run.call_args_list[1].args,
                         ('shell', 'ip', '-4', '-o', 'addr', 'show', 'wlan0'))
        self.assertEqual(commands.run.call_count, 2)  # No source-path readiness read.
        fixture = old.PreparationBudgetControls()
        old_receipt, old_error, _, old_transport, old_end = fixture.invoke(native_path_route=BAD)
        self.assertIsInstance(old_error, old.PreparationTransportBoundary)
        self.assertEqual(old_transport, 1)
        self.assertNotIn('nativeWifiPathPreparation', old_receipt)
        self.assertAlmostEqual(old_end, 38.98)
        receipt, error, _, transport, ended = fixture.invoke(real_native_path=True, native_path_route=BAD)
        self.assertIsInstance(error, TimeoutError)
        self.assertEqual(transport, 0)
        self.assertFalse(receipt['nativeWifiPathPreparation']['repairAttempted'])
        self.assertEqual(receipt['preparationDeadlineMonotonic'], 45)
        self.assertLess(ended, 45)

    def test_full_main_good_path_fits_after_original_38_98_second_preparation(self):
        receipt, error, calls, transport, ended = old.PreparationBudgetControls().invoke(real_native_path=True)
        self.assertIsInstance(error, old.PreparationTransportBoundary)
        self.assertEqual(transport, 1)
        self.assertEqual(receipt['nativeWifiPathPreparation']['status'], 'passed')
        self.assertAlmostEqual(ended, 39.02)
        self.assertTrue(all(c['timeoutSeconds'] <= 8 and c['deadlineMonotonic'] <= 45
                            for c in receipt['commands']))

    def test_full_main_repairs_once_then_good_or_fails_at_same_45_deadline(self):
        for becomes_ready in (True, False):
            with self.subTest(becomes_ready=becomes_ready):
                seen = [0]
                def route():
                    seen[0] += 1
                    return GOOD if becomes_ready and seen[0] > 1 else BAD
                receipt, error, calls, transport, ended = old.PreparationBudgetControls().invoke(
                    real_native_path=True, native_path_route=route, final_seconds=1)
                stage = receipt['nativeWifiPathPreparation']
                self.assertEqual(stage['repairAttempts'], 1)
                self.assertEqual(receipt['preparationDeadlineMonotonic'], 45)
                if becomes_ready:
                    self.assertIsInstance(error, old.PreparationTransportBoundary)
                    self.assertEqual(transport, 1)
                    self.assertEqual(stage['status'], 'passed')
                    self.assertLess(ended, 45)
                else:
                    self.assertIsInstance(error, (TimeoutError, subprocess.TimeoutExpired))
                    self.assertEqual(transport, 0)
                    self.assertEqual(stage['status'], 'failed')
                    self.assertEqual(ended, 45)

    def test_original_transport_and_normal_preflight_source_are_unchanged(self):
        source = (ROOT / 'tools/gecko/prepare_native_adb.py').read_text()
        node = next(n for n in ast.parse(source).body if isinstance(n, ast.FunctionDef) and n.name == 'native_transport')
        raw = ''.join(source.splitlines(keepends=True)[node.lineno - 1:node.end_lineno]).encode()
        self.assertEqual(hashlib.sha256(raw).hexdigest(),
                         '2373207b56f5a1af208379bdfbecf6356028822f5fe618d676528458c99978db')
        self.assertEqual(hashlib.sha256((ROOT / 'tools/gecko/prepare_emulator.py').read_bytes()).hexdigest(),
                         '78457c11434d9ee8149899d7062a284376950e48ee24c4c9b5d08de6a3c9e033')


if __name__ == '__main__':
    unittest.main()
