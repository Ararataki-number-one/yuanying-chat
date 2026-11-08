"""Read-only owner attribution never relaxes the original process-frame gate.

The 315/324 counter and Android clock/PID/epoch headers are taken from the
actual enlarged-light API35 failure in run 42471139648/a1. Owner observations
below are host schema controls, not observations from a device.
"""
import copy
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools/gecko'))
import glass_ui_validation as glass

IDENTITY = dict(sourceCommit='a' * 40, sourceTree='b' * 40, apkSha256='c' * 64)
NONCE = 'd' * 32
COMMANDS = ('glass-hidden-reading-before', 'glass-hidden-reading-after')
GFX = '''Applications Graphics Acceleration Info:
Uptime: 418726 Realtime: 418726
** Graphics info for pid 7379 [local.pocketchat.test] **
Stats since: 335141069052ns
Total frames rendered: 315
'''


def samples():
    return [dict(pid=7379, statsSinceNs=335141069052, realtimeMillis=418726,
                 frames=315, atUnixNs=1794134114680922392),
            dict(pid=7379, statsSinceNs=335141069052, realtimeMillis=420356,
                 frames=324, atUnixNs=1794134116305892317)]


def owners(command, nanos):
    host = dict(rootIdentity=100, shown=False, windowVisibility=0,
                visibility=8, attached=True, viewIdentity=123)
    animation = dict(present=False, started=False, running=False)
    return dict(schema=1, status='observed', command=command, runNonce=NONCE,
        **IDENTITY, readOnly=True, pausesObservers=False, pid=7379, uid=10123,
        activityClass='local.pocketchat.CompactChromeIntegrationActivity',
        activityRef=42, decorRef=100, capturedAtElapsedRealtimeNanos=nanos,
        owners=dict(roots=[copy.deepcopy(host), copy.deepcopy(host)],
            materials=[dict(host=copy.deepcopy(host), drawableVisible=False, animation=animation.copy())],
            docks=[dict(host=copy.deepcopy(host), transition=animation.copy())],
            backdrop=dict(host=copy.deepcopy(host), configuredActive=False, isGlassActive=False)))


class GlassOwnerWindowTest(unittest.TestCase):
    def setUp(self):
        self.before = owners(COMMANDS[0], 418725500000)
        self.after = owners(COMMANDS[1], 420357000000)
        self.samples = samples()

    def bind(self):
        return glass.validate_glass_owner_window(self.before, self.after, self.samples,
                                                IDENTITY, NONCE, COMMANDS)

    def test_actual_process_delta_nine_stays_failed_when_all_glass_is_dormant(self):
        bound = self.bind()
        self.assertEqual(bound['hiddenActiveAnimatorCounts'], [0, 0])
        check = glass.quiet_window_check(self.samples, 2, bound)
        self.assertEqual(check['deltaFrames'], 9)
        self.assertFalse(check['valid'])
        self.assertTrue(check['processDrawFailure'])
        self.assertFalse(check['ownerBindingFailure'])
        self.assertFalse(check['hiddenAnimatorFailure'])
        self.assertEqual(check['allowedDeltaFrames'], 2)
        self.assertEqual(check['requestedObservationSeconds'], 1.5)

    def test_background_one_frame_still_fails_zero_limit(self):
        self.samples[1]['frames'] = self.samples[0]['frames'] + 1
        self.assertFalse(glass.quiet_window_check(self.samples, 0, self.bind())['valid'])

    def test_hidden_live_material_and_dock_are_reported_without_mutating_input(self):
        for value in (self.before, self.after):
            value['owners']['materials'][0]['animation'] = dict(present=True, started=True, running=True)
            value['owners']['docks'][0]['transition'] = dict(present=True, started=True, running=True)
        original = copy.deepcopy((self.before, self.after, self.samples))
        self.assertEqual(self.bind()['hiddenActiveAnimatorCounts'], [2, 2])
        self.assertEqual((self.before, self.after, self.samples), original)

    def test_zero_process_frames_cannot_hide_a_pending_hidden_animator(self):
        self.samples[1]['frames'] = self.samples[0]['frames']
        for value in (self.before, self.after):
            value['owners']['materials'][0]['animation'] = dict(present=True, started=True, running=False)
        check = glass.quiet_window_check(self.samples, 2, self.bind())
        self.assertFalse(check['valid'])
        self.assertFalse(check['processDrawFailure'])
        self.assertFalse(check['ownerBindingFailure'])
        self.assertTrue(check['hiddenAnimatorFailure'])

    def test_visible_glass_press_is_not_a_hidden_animator_failure(self):
        self.samples[1]['frames'] = self.samples[0]['frames']
        for value in (self.before, self.after):
            material = value['owners']['materials'][0]
            material['host']['shown'] = True
            material['drawableVisible'] = True
            material['animation'] = dict(present=True, started=True, running=True)
        check = glass.quiet_window_check(self.samples, 2, self.bind())
        self.assertTrue(check['valid'])
        self.assertFalse(check['hiddenAnimatorFailure'])

    def test_missing_owner_binding_is_a_separate_failure_even_with_zero_frames(self):
        self.samples[1]['frames'] = self.samples[0]['frames']
        check = glass.quiet_window_check(self.samples, 2, dict(status='failed'))
        self.assertFalse(check['valid'])
        self.assertTrue(check['ownerBindingFailure'])
        self.assertFalse(check['processDrawFailure'])
        self.assertFalse(check['hiddenAnimatorFailure'])

    def test_process_or_reset_epoch_change_cannot_bind(self):
        for key in ('pid', 'statsSinceNs'):
            with self.subTest(key=key):
                self.samples = samples()
                self.samples[1][key] += 1
                with self.assertRaises(ValueError):
                    self.bind()

    def test_wrong_source_nonce_command_process_and_mutating_scope_are_rejected(self):
        original = copy.deepcopy(self.after)
        for key, damaged in (('sourceCommit', 'e' * 40), ('sourceTree', 'f' * 40),
                ('apkSha256', '0' * 64), ('runNonce', 'e' * 32), ('command', 'old-observation'),
                ('pid', 7000), ('readOnly', False), ('pausesObservers', True),
                ('activityClass', 'local.pocketchat.OtherActivity'), ('status', 'failed')):
            with self.subTest(key=key):
                self.after = copy.deepcopy(original)
                self.after[key] = damaged
                with self.assertRaises(ValueError):
                    self.bind()

    def test_activity_decor_uid_and_actual_host_root_cannot_change(self):
        original = copy.deepcopy(self.after)
        for key in ('activityRef', 'decorRef', 'uid'):
            with self.subTest(key=key):
                self.after = copy.deepcopy(original)
                self.after[key] += 1
                with self.assertRaises(ValueError):
                    self.bind()
        self.after = copy.deepcopy(original)
        self.after['owners']['materials'][0]['host']['rootIdentity'] = 999
        with self.assertRaises(ValueError):
            self.bind()

    def test_missing_reflection_result_is_not_silently_interpreted_as_idle(self):
        self.after['owners']['materials'][0]['animation'] = {}
        with self.assertRaises(ValueError):
            self.bind()

    def test_boolean_schema_or_untyped_native_visibility_cannot_bind(self):
        original = copy.deepcopy(self.after)
        mutations = (
            lambda value: value.update(schema=True),
            lambda value: value['owners']['materials'][0]['host'].update(shown=1),
            lambda value: value['owners']['materials'][0]['host'].update(attached='true'),
            lambda value: value['owners']['materials'][0]['host'].update(windowVisibility=False),
            lambda value: value['owners']['materials'][0].update(drawableVisible='false'),
            lambda value: value['owners']['backdrop'].update(isGlassActive=0),
        )
        for mutation in mutations:
            self.after = copy.deepcopy(original)
            mutation(self.after)
            with self.assertRaises(ValueError):
                self.bind()

    def test_owner_reads_must_bracket_the_counter_clock(self):
        self.before['capturedAtElapsedRealtimeNanos'] = 419000000000
        with self.assertRaises(ValueError):
            self.bind()

    def test_actual_gfx_header_and_broadcast_ack_are_separable(self):
        expected = dict(pid=7379, statsSinceNs=335141069052, realtimeMillis=418726)
        self.assertEqual(glass.gfxinfo_owner(GFX, 'local.pocketchat.test'), expected)
        self.assertEqual(glass.gfxinfo_owner('Broadcast completed: result=0\n' + GFX,
                                           'local.pocketchat.test'), expected)
        self.assertEqual(glass.gfxinfo_owner(GFX + 'Broadcast completed: result=0\n',
                                           'local.pocketchat.test'), expected)

    def test_missing_or_ambiguous_process_epoch_clock_is_rejected(self):
        for raw in ('', GFX.replace('Stats since:', 'unknown epoch:'), GFX + GFX,
                    GFX.replace('local.pocketchat.test', 'other.process')):
            with self.subTest(raw=raw[:60]), self.assertRaises(ValueError):
                glass.gfxinfo_owner(raw, 'local.pocketchat.test')


if __name__ == '__main__':
    unittest.main()
