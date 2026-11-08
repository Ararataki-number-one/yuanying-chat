"""Launcher reversion transport regressions, never Android acceptance.

Run42480589643/a1's original API35 default-light window dump records the
NOSENSOR launcher restoring ROTATION_90 when the UNSPECIFIED fixture opens.
The model below exercises that observed ordering; it does not simulate app
rendering, glyph observations, network behavior, or physical-device smoothness.
"""
import ast
import hashlib
from pathlib import Path
import re
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools/gecko'))
sys.path.insert(0, str(ROOT / 'tests'))
from glass_display import GlassDisplay, validate_display
from profile_glass_display_test import Android32DisplayModel

COMPONENT = 'local.pocketchat.test/local.pocketchat.UiVisualIntegrationActivity'
LAUNCHER = 'com.google.android.apps.nexuslauncher/.NexusLauncherActivity'

# Original lines193–221 of default-light-typography-display.txt from the
# source2671934b API35 capture. They identify the concrete OS writer; a
# successful lock command was not proof of the later measurement orientation.
ACTUAL_REVERSION_HISTORY = '''    RotationHistory
      11-08 12:41:19.312 ROTATION_0 to ROTATION_90
        source=ActivityRecord{c240382 u0 local.pocketchat.test/local.pocketchat.UiVisualIntegrationActivity t13} SCREEN_ORIENTATION_UNSPECIFIED
        mode=USER_ROTATION_LOCKED user=ROTATION_90 sensor=ROTATION_0
       halfFoldSavedRotation=-1 mInHalfFoldTransition=false mFoldState=FOLDED
      DisplayRotationCompatPolicy{ isTreatmentEnabledForDisplay=false }
       reversionSlots= NOSENSOR false, CAMERA false HALF_FOLD false
      11-08 12:41:35.250 ROTATION_90 to ROTATION_0
        source=ActivityRecord{920f69d u0 com.google.android.apps.nexuslauncher/.NexusLauncherActivity t7} SCREEN_ORIENTATION_NOSENSOR
        mode=USER_ROTATION_LOCKED user=ROTATION_0 sensor=ROTATION_0
       halfFoldSavedRotation=-1 mInHalfFoldTransition=false mFoldState=FOLDED
      DisplayRotationCompatPolicy{ isTreatmentEnabledForDisplay=false }
       reversionSlots= NOSENSOR true, CAMERA false HALF_FOLD false
      11-08 12:41:40.706 ROTATION_0 to ROTATION_90
        source=ActivityRecord{fb317d8 u0 local.pocketchat.test/local.pocketchat.UiVisualIntegrationActivity t14} SCREEN_ORIENTATION_UNSPECIFIED
        mode=USER_ROTATION_LOCKED user=ROTATION_90 sensor=ROTATION_0
       halfFoldSavedRotation=-1 mInHalfFoldTransition=false mFoldState=FOLDED
      DisplayRotationCompatPolicy{ isTreatmentEnabledForDisplay=false }
       reversionSlots= NOSENSOR false, CAMERA false HALF_FOLD false

        RotationLockHistory
          11-08 12:41:16.924: mode=USER_ROTATION_LOCKED, rotation=ROTATION_90, caller=WindowManagerShellCommand#lock
          11-08 12:41:26.128: mode=USER_ROTATION_LOCKED, rotation=ROTATION_90, caller=UiAutomationConnection#restoreRotationStateLocked
          11-08 12:41:30.957: mode=USER_ROTATION_LOCKED, rotation=ROTATION_90, caller=UiAutomationConnection#restoreRotationStateLocked
          11-08 12:41:34.493: mode=USER_ROTATION_LOCKED, rotation=ROTATION_0, caller=WindowManagerShellCommand#lock
          11-08 12:41:36.694: mode=USER_ROTATION_FREE, rotation=ROTATION_0, caller=WindowManagerShellCommand#free
          11-08 12:41:39.718: mode=USER_ROTATION_LOCKED, rotation=ROTATION_0, caller=WindowManagerShellCommand#lock
          11-08 12:41:40.174: mode=USER_ROTATION_LOCKED, rotation=ROTATION_0, caller=WindowManagerShellCommand#lock
          11-08 12:41:40.548: mode=USER_ROTATION_LOCKED, rotation=ROTATION_90, caller=DisplayRotationReversionController#revertOverride
'''


class NoSensorReversionModel(Android32DisplayModel):
    """Only shell configuration and observed NOSENSOR reversion are modeled."""
    def __init__(self):
        super().__init__()
        self.mode = 'lock 1'
        self.settings['user_rotation'] = '1'
        self.foreground = LAUNCHER
        self.target_allows_rotation = False
        self.saved_rotation = 1
        self.resumed_override = None
        self.focus_override = None
        self.preparation_ignored = False

    def __call__(self, *parts, **kwargs):
        if parts[:5] == ('shell', 'am', 'start', '-W', '-n'):
            self.calls.append(parts)
            if parts == self.fail_next:
                self.fail_next = None
                raise OSError('controlled launch transport failure')
            if not self.preparation_ignored:
                # AOSP DisplayRotationReversionController.revertOverride()
                # restores the saved locked user rotation on leaving NOSENSOR.
                if self.saved_rotation is not None and self.mode.startswith('lock '):
                    self.mode = 'lock ' + str(self.saved_rotation)
                    self.settings['user_rotation'] = str(self.saved_rotation)
                self.saved_rotation = None
                self.foreground = parts[5]
                self.target_allows_rotation = True
            return b'Status: ok\n'
        if parts == ('shell', 'dumpsys', 'activity', 'activities'):
            self.calls.append(parts)
            if self.resumed_override is not None:
                return self.resumed_override.encode()
            return ('topResumedActivity=ActivityRecord{123 u0 ' + self.foreground + ' t1}\n').encode()
        raw = super().__call__(*parts, **kwargs)
        if parts == ('shell', 'dumpsys', 'window', 'displays'):
            focus = self.focus_override if self.focus_override is not None else (
                'mCurrentFocus=Window{123 u0 ' + self.foreground + '}\n')
            return raw + focus.encode()
        return raw


class GlassDisplayPreparationRegressionTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.out = Path(self.temp.name)
        self.android = NoSensorReversionModel()
        self.display = GlassDisplay(self.android, self.out,
            lambda p: hashlib.sha256(Path(p).read_bytes()).hexdigest())

    def tearDown(self):
        self.temp.cleanup()

    def start_typography(self):
        self.android('shell', 'am', 'start', '-W', '-n', COMPONENT,
                     '--es', 'visualAction', 'navigation-typography')

    def test_actual_history_identifies_launcher_override_and_later_os_reversion(self):
        history, locks = ACTUAL_REVERSION_HISTORY.split('        RotationLockHistory\n')
        self.assertIn(LAUNCHER, history)
        self.assertIn('SCREEN_ORIENTATION_NOSENSOR', history)
        self.assertIn('NOSENSOR true, CAMERA false HALF_FOLD false', history)
        self.assertIn('12:41:40.706 ROTATION_0 to ROTATION_90', history)
        self.assertIn('12:41:39.718: mode=USER_ROTATION_LOCKED, rotation=ROTATION_0', locks)
        self.assertIn('12:41:40.174: mode=USER_ROTATION_LOCKED, rotation=ROTATION_0', locks)
        self.assertIn('12:41:40.548: mode=USER_ROTATION_LOCKED, rotation=ROTATION_90, '
                      'caller=DisplayRotationReversionController#revertOverride', locks)

    def test_old_configure_on_launcher_is_reverted_and_still_rejected(self):
        self.display.configure(1236, 2676, 480, 1.0, 'no')
        self.start_typography()
        state = self.display.observe('old-failed-order')
        self.assertEqual(state['logical'], dict(width=2676, height=1236, rotation=1, density=480))
        self.assertEqual(state['rotationMode'], 'lock 1')
        self.assertEqual(state['userRotation'], '1')
        with self.assertRaises(ValueError):
            validate_display(state, 1236, 2676, 480, 0, 1.0, 'no')

    def test_preparation_leaves_launcher_before_settings_then_true_measurement_configuration(self):
        proof = self.display.prepare(COMPONENT, 'neutral')
        self.assertEqual(proof['beforeConfiguration']['rotationMode'], 'lock 1')
        first_setting = len(self.android.calls)
        self.display.configure(1236, 2676, 480, 1.3, 'no')
        self.display.require(1236, 2676, 480, 1.3, 'no', 'before-glyphs')
        self.start_typography()
        state = self.display.require(1236, 2676, 480, 1.3, 'no', 'actual-measurement')
        self.assertEqual(state['logical']['rotation'], 0)
        self.assertTrue(proof['noGlyphOrDocumentObservation'])
        self.assertEqual(proof['action'], 'glass-display-preparation')
        self.assertTrue((self.out / proof['activity']['file']).is_file())
        self.assertTrue((self.out / proof['beforeConfiguration']['window']['file']).is_file())
        self.assertEqual(self.android.calls[0], ('shell', 'am', 'start', '-W', '-n', COMPONENT,
                         '--es', 'visualAction', 'glass-display-preparation'))
        self.assertFalse(any(c[:3] == ('shell', 'settings', 'put') or c[:3] == ('shell', 'wm', 'size') and len(c) > 3
                             for c in self.android.calls[:first_setting]))

    def test_all_seven_literal_cases_keep_exact_requested_geometry_font_and_theme(self):
        source = ast.parse((ROOT / 'tools/gecko/glass_ui_validation.py').read_text())
        node = next(n.value for n in source.body if isinstance(n, ast.Assign)
                    and any(isinstance(t, ast.Name) and t.id == 'CONFIGURATIONS' for t in n.targets))
        configurations = ast.literal_eval(node)
        self.assertEqual(len(configurations), 7)
        for name, width, height, font, night in configurations:
            with self.subTest(name=name):
                android = NoSensorReversionModel()
                display = GlassDisplay(android, self.out,
                    lambda p: hashlib.sha256(Path(p).read_bytes()).hexdigest())
                display.prepare(COMPONENT, name + '-neutral')
                display.configure(width * 3, height * 3, 480, font, night)
                display.require(width * 3, height * 3, 480, font, night, name + '-configured')
                android('shell', 'am', 'start', '-W', '-n', COMPONENT,
                        '--es', 'visualAction', 'navigation-typography')
                actual = display.require(width * 3, height * 3, 480, font, night, name + '-glyphs')
                self.assertEqual(actual['logical']['rotation'], int(width > height))

    def test_failed_or_wrong_preparation_cannot_touch_display_settings(self):
        for raw in ('', 'topResumedActivity=ActivityRecord{123 u0 ' + LAUNCHER + ' t1}\n',
                    'topResumedActivity=ActivityRecord{123 u0 ' + COMPONENT + ' t1}\n'
                    'mResumedActivity: ActivityRecord{456 u0 ' + LAUNCHER + ' t2}\n'):
            with self.subTest(resumed=raw):
                self.android = NoSensorReversionModel()
                self.android.resumed_override = raw
                display = GlassDisplay(self.android, self.out, lambda p: '0' * 64)
                with self.assertRaises(ValueError):
                    display.prepare(COMPONENT, 'wrong-resumed')
                self.assertFalse(any(c[:2] == ('shell', 'settings') for c in self.android.calls))

    def test_resumed_activity_without_its_actual_focused_window_is_rejected(self):
        for focus in ('', 'mCurrentFocus=Window{123 u0 ' + LAUNCHER + '}\n',
                      ('mCurrentFocus=Window{123 u0 ' + COMPONENT + '}\n') * 2):
            with self.subTest(focus=focus):
                self.android.focus_override = focus
                with self.assertRaises(ValueError):
                    self.display.prepare(COMPONENT, 'wrong-focus')

    def test_failed_launch_or_wrong_component_never_becomes_prepared(self):
        with self.assertRaises(ValueError):
            self.display.prepare(LAUNCHER, 'wrong-component')
        self.assertEqual(self.android.calls, [])
        self.android.fail_next = ('shell', 'am', 'start', '-W', '-n', COMPONENT,
                                  '--es', 'visualAction', 'glass-display-preparation')
        with self.assertRaises(OSError):
            self.display.prepare(COMPONENT, 'launch-failed')
        self.assertEqual(self.android.foreground, LAUNCHER)

    def test_empty_test_only_branch_precedes_seeding_and_has_no_observer_or_data_actions(self):
        source = (ROOT / 'tests/gecko/UiVisualIntegrationActivity.java').read_text()
        marker = 'if("glass-display-preparation".equals(action)){'
        start = source.index(marker)
        end = source.index('\n    }', start)
        branch = source[start + len(marker):end]
        branch = re.sub(r'//[^\n]*', '', branch)
        self.assertEqual(re.sub(r'\s+', '', branch), 'setContentView(newFrameLayout(this));return;')
        self.assertLess(start, source.index('if("navigation-typography".equals(action))'))
        self.assertLess(start, source.index('try{seed();}'))

    def test_required_loading_and_all_case_paths_prepare_then_configure_then_require_before_measurement(self):
        tree = ast.parse((ROOT / 'tools/gecko/glass_ui_validation.py').read_text())
        for name in ('capture_loading_landscape', 'capture_acceptance_suite'):
            method = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == name)
            calls = sorted((n.lineno, n.func.attr) for n in ast.walk(method)
                if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute)
                and isinstance(n.func.value, ast.Name) and n.func.value.id == 'display')
            configured = next(line for line, action in calls if action == 'configure')
            prepared = next(line for line, action in calls if action == 'prepare')
            required = min(line for line, action in calls if action == 'require' and line > configured)
            self.assertLess(prepared, configured)
            self.assertLess(configured, required)
            if name == 'capture_acceptance_suite':
                typography = next(n.lineno for n in ast.walk(method) if isinstance(n, ast.Call)
                    and isinstance(n.func, ast.Name) and n.func.id == 'typography')
                self.assertLess(required, typography)


if __name__ == '__main__':
    unittest.main()
