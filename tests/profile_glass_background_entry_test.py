"""Background entry readback regressions; host models are not Android acceptance.

Run06a802's immediate HOME activity dumps were PAUSED, even when its later
HWUI window happened to remain quiet. These actual-format excerpts and typed
owner models prevent beginning the unchanged background window too early.
"""
import unittest
import ast
import copy
import hashlib
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools/gecko'))
from glass_ui_validation import background_activity_state, background_owner_hidden, quiet_window_check
import glass_ui_validation as validation

PACKAGE = 'local.pocketchat.test'
COMPONENT = PACKAGE + '/local.pocketchat.CompactChromeIntegrationActivity'
FOREIGN = 'com.google.android.apps.nexuslauncher/.NexusLauncherActivity'

# Verbatim selected Hist/state/visibility/resumed lines of the actual dumps.
# Omitted configuration/path/window text is not claimed as a complete dump.
# The complete originals were independently parsed outside the repository.
ACTUAL_EXCERPTS = {
    32: '''    * Hist  #0: ActivityRecord{7e42e40 u0 local.pocketchat.test/local.pocketchat.CompactChromeIntegrationActivity t21}
      packageName=local.pocketchat.test processName=local.pocketchat.test
      mActivityComponent=local.pocketchat.test/local.pocketchat.CompactChromeIntegrationActivity
      state=PAUSED stopped=false delayedResume=false finishing=false
      mVisibleRequested=false mVisible=true mClientVisible=true reportedDrawn=true reportedVisible=true
      nowVisible=true lastVisibleTime=-30s699ms
  ResumedActivity: ActivityRecord{57b3c64 u0 com.google.android.apps.nexuslauncher/.NexusLauncherActivity t10}
''',
    35: '''    * Hist  #0: ActivityRecord{641efa1 u0 local.pocketchat.test/local.pocketchat.CompactChromeIntegrationActivity t18}
      packageName=local.pocketchat.test processName=local.pocketchat.test
      mActivityComponent=local.pocketchat.test/local.pocketchat.CompactChromeIntegrationActivity
      state=PAUSED delayedResume=false finishing=false
      mVisibleRequested=false mVisible=true mClientVisible=true reportedDrawn=true reportedVisible=true
      nowVisible=true lastVisibleTime=-34s905ms
  ResumedActivity: ActivityRecord{5f7d949 u0 com.google.android.apps.nexuslauncher/.NexusLauncherActivity t7}
''',
}
ACTUAL_FULL_DUMP_SHA256 = {32: 'bedc9f83bbede20d12bfebc0494fcdf697a5e5d4d2065bc44d069cf2d265a59e', 35: '4e1fe280d6e704e60058af3b4f7cac549e13bcd750fe8cc3d3be2c998dc52d54'}


def stopped_counterfactual(raw):
    """Explicit modeled STOPPED state, never a claim of another device sample."""
    raw = raw.replace('state=PAUSED ', 'state=STOPPED ').replace('stopped=false', 'stopped=true')
    for key in ('mVisibleRequested', 'mVisible', 'mClientVisible', 'reportedVisible', 'nowVisible'):
        raw = raw.replace(key + '=true', key + '=false')
    return raw


IDENTITY = dict(sourceCommit='06a802663075664b75aa9d19184d9c02b6bab7c9',
                sourceTree='23c64e1e3b592e58105e888c0223859959ea5279',
                apkSha256='da741c465edf2df456688548725eb3dfa61635932f56c243699d3858541bcdb8')
NONCE = 'fce5018516f73d30974f3d16872d16b1'
COMMAND = 'background-entry-1'


def modeled_owner(hidden=True):
    """Native observation schema host model; no synthetic device receipt."""
    def host():
        return dict(rootIdentity=195699713, attached=True, shown=not hidden,
                    visibility=0, windowVisibility=8 if hidden else 0, windowFocus=False)
    return dict(schema=1, status='observed', command=COMMAND, **IDENTITY,
                runNonce=NONCE, pid=8205, uid=10209, activityRef=38517122,
                activityClass='local.pocketchat.CompactChromeIntegrationActivity', decorRef=195699713,
                active=False, windowFocus=False, capturedAtElapsedRealtimeNanos=475166944546,
                readOnly=True, pausesObservers=False,
                owners=dict(roots=[host(), host()], backdrop=dict(configuredActive=True,
                    isGlassActive=False, host=host()), materials=[dict(host=host(), drawableVisible=True,
                    animation=dict(present=True, started=False, running=False))],
                    docks=[dict(host=host(), transition=dict(present=True, started=False, running=False))]))


def hosts(observation):
    owners = observation['owners']
    return owners['roots'] + [owners['backdrop']['host']] + [entry['host'] for entry in
            owners['materials'] + owners['docks']]


class BackgroundActivityStateTest(unittest.TestCase):
    def test_both_actual_android_formats_remain_paused_and_visible(self):
        self.assertEqual(set(ACTUAL_EXCERPTS), {32, 35})
        for api, raw in ACTUAL_EXCERPTS.items():
            with self.subTest(api=api):
                result = background_activity_state(raw, PACKAGE)
                self.assertEqual(result['component'], COMPONENT)
                self.assertEqual(result['state'], 'PAUSED')
                self.assertIs(result['fullyStopped'], False)
                self.assertEqual(result['status'], 'waiting')
                self.assertIs(result['visibleFields']['mVisibleRequested'], False)
                for key in ('mVisible', 'mClientVisible', 'reportedVisible', 'nowVisible'):
                    self.assertIs(result['visibleFields'][key], True)

    def test_stopped_hidden_counterfactual_works_with_both_real_field_formats(self):
        for api, raw in ACTUAL_EXCERPTS.items():
            with self.subTest(api=api):
                result = background_activity_state(stopped_counterfactual(raw), PACKAGE)
                self.assertEqual(result['state'], 'STOPPED')
                self.assertEqual(result['status'], 'stopped')
                self.assertIs(result['fullyStopped'], True)
                self.assertTrue(all(value is False for value in result['visibleFields'].values()))

    def test_each_actual_visibility_and_transitional_state_independently_blocks_entry(self):
        stopped = stopped_counterfactual(ACTUAL_EXCERPTS[32])
        for state in ('PAUSED', 'PAUSING', 'STOPPING', 'RESUMED', 'INITIALIZING'):
            with self.subTest(state=state):
                self.assertIs(background_activity_state(stopped.replace('state=STOPPED ', 'state=' + state + ' '), PACKAGE)['fullyStopped'], False)
        for key in ('mVisibleRequested', 'mVisible', 'mClientVisible', 'reportedVisible', 'nowVisible'):
            with self.subTest(visible=key):
                self.assertIs(background_activity_state(stopped.replace(key + '=false', key + '=true'), PACKAGE)['fullyStopped'], False)
        for old, new in [('stopped=true', 'stopped=false'), ('finishing=false', 'finishing=true')]:
            self.assertIs(background_activity_state(stopped.replace(old, new), PACKAGE)['fullyStopped'], False)

    def test_missing_duplicate_and_foreign_target_records_cannot_substitute_a_stop(self):
        raw = stopped_counterfactual(ACTUAL_EXCERPTS[35])
        for bad in (raw.replace(COMPONENT, PACKAGE + '/local.pocketchat.MainActivity'),
                    raw.replace(COMPONENT, 'foreign.test/local.pocketchat.CompactChromeIntegrationActivity'),
                    raw + '\n' + raw, raw.replace('mActivityComponent=' + COMPONENT,
                    'mActivityComponent=foreign.test/local.pocketchat.CompactChromeIntegrationActivity'),
                    raw.replace('packageName=' + PACKAGE, 'packageName=foreign.test')):
            with self.subTest(raw=bad[:90]):
                with self.assertRaises(ValueError):
                    background_activity_state(bad, PACKAGE)

    def test_ambiguous_missing_or_malformed_target_fields_are_not_ready(self):
        raw = stopped_counterfactual(ACTUAL_EXCERPTS[35])
        for bad in (raw.replace('state=STOPPED ', 'state=STOPPED state=PAUSED '),
                    raw.replace('state=STOPPED ', 'state=STOPPED state=broken '),
                    raw.replace('state=STOPPED ', ''),
                    raw.replace('nowVisible=false', 'nowVisible=false nowVisible=false'),
                    raw.replace('mClientVisible=false', 'mClientVisible=0'),
                    raw.replace('nowVisible=false', 'nowVisible=false.extra'),
                    raw.replace('* Hist  #0:', '* Hist  #bad:')):
            with self.subTest(raw=bad[-100:]):
                with self.assertRaises(ValueError):
                    background_activity_state(bad, PACKAGE)

    def test_own_package_resumed_reference_or_hist_record_blocks_stopped_target(self):
        raw = stopped_counterfactual(ACTUAL_EXCERPTS[35])
        other = PACKAGE + '/local.pocketchat.MainActivity'
        for bad in (raw + '\n  topResumedActivity=ActivityRecord{abc u0 ' + other + ' t2}\n',
                    raw + '\n  mResumedActivity: ActivityRecord{abc u0 ' + other + ' t2}\n',
                    raw + '\n  Resumed: ActivityRecord{abc u0 ' + other + ' t2}\n',
                    raw + '\n  * Hist  #1: ActivityRecord{abc u0 ' + other + ' t2}\n    state=RESUMED finishing=false\n'):
            with self.subTest(raw=bad[-120:]):
                self.assertIs(background_activity_state(bad, PACKAGE)['fullyStopped'], False)

    def test_unrelated_foreign_resumed_activity_is_expected_in_background(self):
        raw = stopped_counterfactual(ACTUAL_EXCERPTS[35])
        self.assertIn(FOREIGN, raw)
        self.assertIs(background_activity_state(raw, PACKAGE)['fullyStopped'], True)
        for malformed in ('', None, True, {}, 1):
            with self.subTest(raw=malformed):
                with self.assertRaises(ValueError):
                    background_activity_state(malformed, PACKAGE)
        for bad_package in ('', 'local.pocketchat.test/extra', None, True):
            with self.assertRaises(ValueError):
                background_activity_state(raw, bad_package)


class BackgroundOwnerHiddenTest(unittest.TestCase):
    def check(self, observation):
        return background_owner_hidden(observation, IDENTITY, NONCE, COMMAND)

    def test_inactive_activity_alone_does_not_mean_roots_or_windows_are_hidden(self):
        visible = modeled_owner(False)
        self.assertIs(visible['active'], False)
        self.assertIs(self.check(visible), False)
        self.assertIs(self.check(modeled_owner()), True)
        for field in ('active', 'windowFocus'):
            observation = modeled_owner();observation[field] = True
            self.assertIs(self.check(observation), False)

    def test_every_root_backdrop_material_and_dock_host_must_be_hidden(self):
        for index in range(len(hosts(modeled_owner()))):
            for field, value in [('shown', True), ('windowVisibility', 0), ('windowFocus', True)]:
                with self.subTest(host=index, field=field):
                    observation = modeled_owner()
                    hosts(observation)[index][field] = value
                    self.assertIs(self.check(observation), False)
        observation = modeled_owner()
        for host in hosts(observation):
            host['windowVisibility'] = 4
        self.assertIs(self.check(observation), True)

    def test_source_nonce_command_activity_and_readonly_binding_are_required(self):
        changes = {'schema':True, 'sourceCommit':'0'*40, 'sourceTree':'0'*40, 'apkSha256':'0'*64,
                   'runNonce':'0'*32, 'command':'background-entry-2', 'status':'missing',
                   'activityClass':'local.pocketchat.MainActivity', 'readOnly':False, 'pausesObservers':True}
        for field, value in changes.items():
            with self.subTest(field=field):
                observation = modeled_owner();observation[field] = value
                with self.assertRaises(ValueError):
                    self.check(observation)
        for wrong in (None, True, [], {}):
            with self.assertRaises(ValueError):
                self.check(wrong)
        for identity, nonce, command in ((None, NONCE, COMMAND), ({}, NONCE, COMMAND),
                                         (IDENTITY, True, COMMAND), (IDENTITY, 'a'*31, COMMAND),
                                         (IDENTITY, NONCE, ''), (IDENTITY, NONCE, 'a'*81),
                                         (IDENTITY, NONCE, True)):
            with self.assertRaises(ValueError):
                background_owner_hidden(modeled_owner(), identity, nonce, command)

    def test_owner_identity_clocks_and_visibility_require_exact_types(self):
        for field in ('pid', 'uid', 'activityRef', 'decorRef', 'capturedAtElapsedRealtimeNanos'):
            for value in (True, -1, '0'):
                with self.subTest(field=field, value=value):
                    observation = modeled_owner();observation[field] = value
                    with self.assertRaises(ValueError):self.check(observation)
        for field, value in [('shown', 0), ('attached', 1), ('windowFocus', 0),
                             ('rootIdentity', True), ('windowVisibility', False), ('visibility', '0')]:
            with self.subTest(host_field=field):
                observation = modeled_owner();hosts(observation)[0][field] = value
                with self.assertRaises(ValueError):self.check(observation)

    def test_missing_or_foreign_owner_hierarchy_never_becomes_a_hidden_receipt(self):
        for field, value in [('roots', []), ('roots', [modeled_owner()['owners']['roots'][0]]),
                             ('materials', []), ('docks', []), ('backdrop', {})]:
            with self.subTest(field=field):
                observation = modeled_owner();observation['owners'][field] = value
                with self.assertRaises(ValueError):self.check(observation)
        observation = modeled_owner();hosts(observation)[-1]['rootIdentity'] += 1
        with self.assertRaises(ValueError):self.check(observation)

    def test_pending_hidden_animator_does_not_delay_entry_and_original_hidden_gate_rejects_it(self):
        observation = modeled_owner()
        observation['owners']['materials'][0]['animation'].update(started=True, running=False)
        self.assertIs(self.check(observation), True)
        samples = [dict(frames=10, atUnixNs=0), dict(frames=10, atUnixNs=1_500_000_000)]
        result = quiet_window_check(samples, 0, dict(status='bound', hiddenActiveAnimatorCounts=[1,1]))
        self.assertIs(result['hiddenAnimatorFailure'], True)
        self.assertIs(result['processDrawFailure'], False)
        self.assertIs(result['valid'], False)

    def test_stopped_activity_and_hidden_owner_are_both_needed(self):
        paused = ACTUAL_EXCERPTS[35]
        stopped = stopped_counterfactual(paused)
        self.assertFalse(background_activity_state(paused, PACKAGE)['fullyStopped'] and self.check(modeled_owner()))
        self.assertFalse(background_activity_state(stopped, PACKAGE)['fullyStopped'] and self.check(modeled_owner(False)))
        self.assertTrue(background_activity_state(stopped, PACKAGE)['fullyStopped'] and self.check(modeled_owner()))
        for transition in (((paused, False), (stopped, False), (stopped, True)),
                           ((paused, False), (paused, True), (stopped, True))):
            ready = [background_activity_state(raw, PACKAGE)['fullyStopped'] and self.check(modeled_owner(hidden))
                     for raw, hidden in transition]
            self.assertEqual(ready, [False, False, True])

    def test_ready_entry_never_waives_the_independent_original_zero_frame_budget(self):
        self.assertIs(self.check(modeled_owner()), True)
        samples = [dict(frames=243, atUnixNs=0), dict(frames=244, atUnixNs=1_674_000_000)]
        result = quiet_window_check(samples, 0, dict(status='bound', hiddenActiveAnimatorCounts=[0,0]))
        self.assertEqual(result['deltaFrames'], 1)
        self.assertEqual(result['allowedDeltaFrames'], 0)
        self.assertIs(result['processDrawFailure'], True)
        self.assertIs(result['hiddenAnimatorFailure'], False)
        self.assertIs(result['valid'], False)


class BackgroundEntryTransportModel:
    """Finite read-only host transport, not a device or a producer implementation."""
    def __init__(self, snapshots):
        self.snapshots = snapshots
        self.clock = SimpleNamespace(now=100.0)
        self.calls, self.owner_reads, self.sleeps, self.activity_reads = [], [], [], []
        self.deadline = None
        self.exhaust_owner = False

    def monotonic(self):
        return self.clock.now

    def sleep(self, delay):
        if not 0 <= delay <= .2 or delay > self.deadline - self.clock.now + 1e-9:
            raise AssertionError('Unbounded background-entry sleep')
        self.sleeps.append(delay)
        self.clock.now += delay

    def adb(self, *parts, **kwargs):
        timeout = kwargs.get('timeout')
        if type(timeout) not in (int, float) or not 0 < timeout <= self.deadline - self.clock.now + 1e-9:
            raise AssertionError('ADB timeout exceeds the original entry deadline')
        self.calls.append((parts, timeout, self.clock.now))
        if timeout < .02:
            self.clock.now += timeout
            raise TimeoutError('Modeled ADB command exhausted its allotted deadline')
        self.clock.now += .02
        if parts == ('shell', 'dumpsys', 'activity', 'activities'):
            index = min(len(self.activity_reads), len(self.snapshots) - 1)
            raw = self.snapshots[index][0]
            self.activity_reads.append(raw)
            return raw.encode()
        expected = ('shell', 'am', 'broadcast', '-a', PACKAGE + '.CHROME_COLLAPSE', '-p', PACKAGE,
                    '--es', 'eventNonce', NONCE, '--es', 'glassObserveCommand',
                    'background-entry-' + str(len(self.activity_reads)))
        if parts != expected:
            raise AssertionError('Entry issued an input, mutation or unsupported transport: ' + repr(parts))
        return b'Broadcast completed: result=0\n'

    def observe_owner(self, command, deadline):
        if deadline != self.deadline or self.clock.now >= deadline:
            raise AssertionError('Owner read did not retain the original absolute deadline')
        self.clock.now = deadline if self.exhaust_owner else self.clock.now + min(.02, deadline - self.clock.now)
        self.owner_reads.append(command)
        index = min(len(self.activity_reads) - 1, len(self.snapshots) - 1)
        observation = copy.deepcopy(self.snapshots[index][1])
        observation['command'] = command
        return observation


class BackgroundEntryOrchestrationTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.out = Path(self.temp.name)
        self.case = dict(name='host-background-case', runNonce=NONCE)

    def tearDown(self):
        self.temp.cleanup()

    def run_entry(self, snapshots, duration=30, exhaust_owner=False):
        self.transport = BackgroundEntryTransportModel(snapshots)
        self.transport.exhaust_owner = exhaust_owner
        self.transport.deadline = self.transport.monotonic() + duration
        with patch.object(validation, 'time', SimpleNamespace(monotonic=self.transport.monotonic,
                          sleep=self.transport.sleep, time_ns=lambda: int(self.transport.monotonic() * 1e9))):
            return validation.wait_for_background_entry(case=self.case, adb=self.transport.adb,
                observe_owner=self.transport.observe_owner, out=self.out,
                sha=lambda p: hashlib.sha256(Path(p).read_bytes()).hexdigest(), identity=IDENTITY,
                package=PACKAGE, deadline=self.transport.deadline)

    def test_three_real_state_boundaries_are_read_before_entry_can_be_verified(self):
        paused = ACTUAL_EXCERPTS[35]
        stopped = stopped_counterfactual(paused)
        result = self.run_entry([(paused, modeled_owner(False)), (stopped, modeled_owner(False)),
                                 (stopped, modeled_owner())])
        self.assertEqual(result['status'], 'verified')
        self.assertEqual(result, self.case['backgroundEntry'])
        self.assertEqual(len(result['attempts']), 3)
        self.assertEqual(self.transport.owner_reads, ['background-entry-1', 'background-entry-2', 'background-entry-3'])
        self.assertEqual(len(self.transport.calls), 6)
        self.assertEqual(len(self.transport.sleeps), 2)
        for index, raw in enumerate(self.transport.activity_reads, 1):
            path = self.out / ('host-background-case-background-entry-' + str(index) + '-activity.txt')
            self.assertEqual(path.read_bytes(), raw.encode())

    def test_already_hidden_owner_does_not_waive_a_still_paused_activity(self):
        paused = ACTUAL_EXCERPTS[32]
        result = self.run_entry([(paused, modeled_owner()),
                                 (stopped_counterfactual(paused), modeled_owner())])
        self.assertEqual(result['status'], 'verified')
        self.assertEqual(len(result['attempts']), 2)
        self.assertEqual(len(self.transport.owner_reads), 2)

    def test_never_stopped_is_rejected_after_at_most_twenty_readonly_attempts(self):
        with self.assertRaises(TimeoutError):
            self.run_entry([(ACTUAL_EXCERPTS[35], modeled_owner())])
        self.assertEqual(len(self.transport.activity_reads), 20)
        self.assertEqual(len(self.transport.owner_reads), 20)
        self.assertEqual(len(set(self.transport.owner_reads)), 20)
        self.assertLess(self.transport.monotonic(), self.transport.deadline)
        self.assertNotEqual(self.case['backgroundEntry']['status'], 'verified')
        self.assertEqual(len(self.case['backgroundEntry']['attempts']), 20)

    def test_original_deadline_truncates_pending_poll_without_input_or_quiet_replay(self):
        with self.assertRaises(TimeoutError):
            self.run_entry([(ACTUAL_EXCERPTS[35], modeled_owner())], duration=1.0)
        self.assertLess(len(self.transport.activity_reads), 20)
        self.assertLessEqual(self.transport.monotonic(), self.transport.deadline + 1e-9)
        self.assertNotEqual(self.case['backgroundEntry']['status'], 'verified')
        self.assertTrue(self.transport.calls)

    def test_expired_deadline_does_not_start_an_adb_or_owner_observation(self):
        with self.assertRaises(TimeoutError):
            self.run_entry([(ACTUAL_EXCERPTS[35], modeled_owner())], duration=0)
        self.assertEqual(self.transport.calls, [])
        self.assertEqual(self.transport.owner_reads, [])
        self.assertNotEqual(self.case['backgroundEntry']['status'], 'verified')

    def test_hidden_owner_returning_after_the_deadline_cannot_start_the_quiet_window(self):
        with self.assertRaises(TimeoutError):
            self.run_entry([(stopped_counterfactual(ACTUAL_EXCERPTS[35]), modeled_owner())], exhaust_owner=True)
        self.assertEqual(self.transport.owner_reads, ['background-entry-1'])
        self.assertEqual(self.transport.monotonic(), self.transport.deadline)
        self.assertNotEqual(self.case['backgroundEntry']['status'], 'verified')

    def test_wrong_source_is_terminal_and_cannot_be_replaced_by_a_later_good_owner(self):
        stopped = stopped_counterfactual(ACTUAL_EXCERPTS[35])
        wrong = modeled_owner();wrong['sourceCommit'] = '0' * 40
        with self.assertRaises(ValueError):
            self.run_entry([(stopped, wrong), (stopped, modeled_owner())])
        self.assertEqual(self.transport.owner_reads, ['background-entry-1'])
        self.assertNotEqual(self.case['backgroundEntry']['status'], 'verified')

    def test_duplicate_target_record_is_terminal_before_any_native_owner_request(self):
        stopped = stopped_counterfactual(ACTUAL_EXCERPTS[35])
        with self.assertRaises(ValueError):
            self.run_entry([(stopped + stopped, modeled_owner())])
        self.assertEqual(len(self.transport.calls), 1)
        self.assertEqual(self.transport.owner_reads, [])
        self.assertNotEqual(self.case['backgroundEntry']['status'], 'verified')

    def test_hidden_pending_animator_is_not_polled_until_zero_before_entry(self):
        stopped = stopped_counterfactual(ACTUAL_EXCERPTS[35])
        pending = modeled_owner();pending['owners']['materials'][0]['animation'].update(started=True, running=False)
        result = self.run_entry([(stopped, pending)])
        self.assertEqual(result['status'], 'verified')
        self.assertEqual(self.transport.owner_reads, ['background-entry-1'])
        self.assertEqual(self.transport.sleeps, [])
        samples = [dict(frames=10, atUnixNs=0), dict(frames=10, atUnixNs=1_500_000_000)]
        check = quiet_window_check(samples, 0, dict(status='bound', hiddenActiveAnimatorCounts=[1, 1]))
        self.assertIs(check['hiddenAnimatorFailure'], True)
        self.assertIs(check['valid'], False)

    def test_actual_caller_requires_entry_before_the_single_original_zero_budget_quiet_call(self):
        tree = ast.parse((ROOT / 'tools/gecko/glass_ui_validation.py').read_text())
        suite = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == 'capture_acceptance_suite')
        def named(node, name):
            return isinstance(node, ast.Expr) and isinstance(node.value, ast.Call) and isinstance(node.value.func, ast.Name) and node.value.func.id == name
        blocks = [n.body for n in ast.walk(suite) if isinstance(n, ast.Try)
                  and any(named(statement, 'wait_for_background_entry') for statement in n.body)]
        self.assertEqual(len(blocks), 1)
        body = blocks[0]
        entry_index = next(i for i, node in enumerate(body) if named(node, 'wait_for_background_entry'))
        quiet = body[entry_index + 1]
        self.assertTrue(named(quiet, 'quiet'))
        self.assertEqual([ast.literal_eval(arg) for arg in quiet.value.args[1:]], ['background', 0])
        self.assertTrue(any(named(node, 'key') and isinstance(node.value.args[1], ast.Constant)
                            and node.value.args[1].value == 3 for node in body[:entry_index]))
        quiet_calls = [n for n in ast.walk(suite) if isinstance(n, ast.Call) and isinstance(n.func, ast.Name)
                       and n.func.id == 'quiet' and len(n.args) > 1 and isinstance(n.args[1], ast.Constant)
                       and n.args[1].value == 'background']
        self.assertEqual(len(quiet_calls), 1)


if __name__ == '__main__':
    unittest.main()
