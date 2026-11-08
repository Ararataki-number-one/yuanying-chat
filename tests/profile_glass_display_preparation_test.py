"""Launcher reversion transport regressions, never Android acceptance.

Run42480589643/a1's original API35 default-light window dump records the
NOSENSOR launcher restoring ROTATION_90 when the UNSPECIFIED fixture opens.
The model below exercises that observed ordering; it does not simulate app
rendering, glyph observations, network behavior, or physical-device smoothness.
"""
import ast
import copy
import hashlib
import json
from pathlib import Path
import re
import sys
import tempfile
from types import SimpleNamespace
import unittest
import xml.etree.ElementTree as ET

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


class StandardRootSceneModel(NoSensorReversionModel):
    """Explicit host Activity/task transport model, never native layout evidence.

    AOSP android-15.0.0_r1 Intent.FLAG_ACTIVITY_CLEAR_TOP and
    Task.performClearTop/ActivityStarter document the standard/non-singleTop
    finish/recreate branch. ActivityManagerShellCommand adds NEW_TASK to am
    start. Without CLEAR_TOP an existing root receives onNewIntent; this real
    fixture's download-only handler does not dispatch a different visualAction.
    Synthetic typography rows below exercise the unchanged Python verifier;
    they make no glyph, viewport, rendering, or Android execution claim.
    """
    def __init__(self):
        super().__init__()
        self.instance = 0
        self.scene = None
        self.delivered_intents = []
        self.records = []
        self.identity = dict(sourceCommit='1' * 40, sourceTree='2' * 40, apkSha256='3' * 64)
        self.bad_nonce = False
        self.bad_glyph = False

    def typography_rows(self, nonce):
        rows = []
        for selected in range(-1, 4):
            for index, label in enumerate(('环境', '网络', '下载', '阅读')):
                rows.append(dict(schema=1, kind='label', nonce=nonce,
                    actualAndroidLayout=True, **self.identity,
                    fontScale=float(self.settings['font_scale']), selectedIndex=selected,
                    measurement=dict(buttonIndex=index, label=label,
                        valid=not self.bad_glyph, checks=dict(wholeLabel=not self.bad_glyph))))
        rows.append(dict(schema=1, kind='summary', nonce=nonce,
            actualAndroidLayout=True, **self.identity,
            fontScale=float(self.settings['font_scale']), status='verified', observationCount=20))
        return rows

    def __call__(self, *parts, **kwargs):
        if parts[:5] == ('shell', 'am', 'start', '-W', '-n'):
            action = next((parts[i + 1] for i, value in enumerate(parts[:-1])
                           if value == 'visualAction'), None)
            clear = '--activity-clear-top' in parts
            single_top = '--activity-single-top' in parts
            if self.foreground == parts[5] and self.scene is not None and (not clear or single_top):
                self.calls.append(parts)
                self.delivered_intents.append(action)
                return b'Warning: Activity not started, intent delivered to current instance.\n'
            raw = super().__call__(*parts, **kwargs)
            self.instance += 1
            self.scene = action
            if action == 'navigation-typography':
                nonce = parts[parts.index('visualNonce') + 1]
                self.records.extend(self.typography_rows('0' * 32 if self.bad_nonce else nonce))
            elif action == 'chat':
                self.foreground = 'local.pocketchat.test/local.pocketchat.MainActivity'
                self.scene = 'actual-main-loading'
            return raw
        if parts[:3] == ('logcat', '-d', '-v'):
            self.calls.append(parts)
            return ('\n'.join(json.dumps(row) for row in self.records) + '\n').encode()
        if parts[:3] == ('shell', 'am', 'force-stop'):
            self.calls.append(parts)
            self.foreground = LAUNCHER
            self.scene = None
            return b''
        return super().__call__(*parts, **kwargs)


class GlassPreparedSceneLaunchRegressionTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.out = Path(self.temp.name)
        self.android = StandardRootSceneModel()
        self.display = GlassDisplay(self.android, self.out,
            lambda p: hashlib.sha256(Path(p).read_bytes()).hexdigest())
        self.tree = ast.parse((ROOT / 'tools/gecko/glass_ui_validation.py').read_text())

    def tearDown(self):
        self.temp.cleanup()

    def prepare(self, width=1236, height=2676, font=1.0, night='no'):
        self.display.prepare(COMPONENT, 'neutral')
        self.display.configure(width, height, 480, font, night)
        self.display.require(width, height, 480, font, night, 'configured')
        self.assertEqual(self.android.scene, 'glass-display-preparation')

    def typography(self, *, remove_clear=False, single_top=False, font=1.0,
                   width=412, height=892, night='no'):
        suite = next(n for n in self.tree.body if isinstance(n, ast.FunctionDef)
                     and n.name == 'capture_acceptance_suite')
        method = copy.deepcopy(next(n for n in suite.body if isinstance(n, ast.FunctionDef)
                                   and n.name == 'typography'))
        for call in ast.walk(method):
            if isinstance(call, ast.Call) and isinstance(call.func, ast.Name) and call.func.id == 'adb':
                if any(isinstance(a, ast.Constant) and a.value == 'navigation-typography' for a in call.args):
                    if remove_clear:
                        call.args = [a for a in call.args if not isinstance(a, ast.Constant)
                                     or a.value != '--activity-clear-top']
                    if single_top:
                        call.args.insert(6, ast.Constant('--activity-single-top'))
        clock = SimpleNamespace(now=0.0)
        def sleep(delay):
            clock.now += delay
        env = dict(adb=self.android, api=dict(COMPONENT=COMPONENT,
            LABELS=('环境', '网络', '下载', '阅读')), identity=self.android.identity,
            args=SimpleNamespace(out=self.out), display=self.display, package='local.pocketchat.test',
            time=SimpleNamespace(monotonic=lambda: clock.now, sleep=sleep),
            secrets=SimpleNamespace(token_hex=lambda size: 'a' * 32), json=json,
            sha=lambda p: hashlib.sha256(Path(p).read_bytes()).hexdigest())
        exec(compile(ast.fix_missing_locations(ast.Module(body=[method], type_ignores=[])),
                     'actual-glass-typography-function', 'exec'), env)
        case = dict(name='host-scene', widthDp=width, heightDp=height, fontScale=font, requestedNight=night)
        env['typography'](case)
        return case

    def loading_launch(self, remove_clear=False, single_top=False):
        method = next(n for n in self.tree.body if isinstance(n, ast.FunctionDef)
                      and n.name == 'capture_loading_landscape')
        call = copy.deepcopy(next(n for n in ast.walk(method) if isinstance(n, ast.Call)
            and isinstance(n.func, ast.Name) and n.func.id == 'adb'
            and any(isinstance(a, ast.Constant) and a.value == 'chat' for a in n.args)))
        if remove_clear:
            call.args = [a for a in call.args if not isinstance(a, ast.Constant)
                         or a.value != '--activity-clear-top']
        if single_top:
            call.args.insert(6, ast.Constant('--activity-single-top'))
        eval(compile(ast.fix_missing_locations(ast.Expression(body=call)), 'actual-loading-launch', 'eval'),
             dict(adb=self.android, api=dict(COMPONENT=COMPONENT)))

    def test_actual_fixture_is_standard_and_new_intent_cannot_dispatch_these_scenes(self):
        manifest = ET.fromstring((ROOT / 'tests/gecko/AndroidManifest.xml').read_bytes())
        android = '{http://schemas.android.com/apk/res/android}'
        matches = [a for a in manifest.iter('activity') if a.get(android + 'name') ==
                   'local.pocketchat.UiVisualIntegrationActivity']
        self.assertEqual(len(matches), 1)
        self.assertEqual(matches[0].get(android + 'launchMode', 'standard'), 'standard')
        source = (ROOT / 'tests/gecko/UiVisualIntegrationActivity.java').read_text()
        handler = source.split('@Override protected void onNewIntent(Intent request){', 1)[1].split(
            '\n  String downloadObservationRejection', 1)[0]
        self.assertNotIn('navigation-typography', handler)
        self.assertNotIn('"chat"', handler)
        self.assertIn('downloadObservationRejection(request)', handler)

    def test_old_launch_reuses_empty_root_and_cannot_borrow_baseline_glyph_nonce(self):
        self.android.records.extend(self.android.typography_rows('b' * 32))
        self.prepare()
        with self.assertRaisesRegex(ValueError, 'typography observation is incomplete or failed'):
            self.typography(remove_clear=True)
        self.assertEqual(self.android.instance, 1)
        self.assertEqual(self.android.scene, 'glass-display-preparation')
        self.assertEqual(self.android.delivered_intents, ['navigation-typography'])
        self.assertFalse(any(r['nonce'] == 'a' * 32 for r in self.android.records))

    def test_fresh_standard_instance_runs_actual_typography_verifier_for_all_seven_cases(self):
        node = next(n.value for n in self.tree.body if isinstance(n, ast.Assign)
                    and any(isinstance(t, ast.Name) and t.id == 'CONFIGURATIONS' for t in n.targets))
        for name, width, height, font, night in ast.literal_eval(node):
            with self.subTest(name=name):
                self.android = StandardRootSceneModel()
                self.display = GlassDisplay(self.android, self.out,
                    lambda p: hashlib.sha256(Path(p).read_bytes()).hexdigest())
                self.prepare(width * 3, height * 3, font, night)
                case = self.typography(font=font, width=width, height=height, night=night)
                self.assertEqual(self.android.instance, 2)
                self.assertEqual(self.android.delivered_intents, [])
                labels = [r for r in case['typography']['records'] if r['kind'] == 'label']
                self.assertEqual(len(labels), 20)
                self.assertEqual(len({(r['selectedIndex'], r['measurement']['buttonIndex']) for r in labels}), 20)
                self.assertEqual({r['nonce'] for r in labels}, {'a' * 32})
                self.assertEqual(case['typography']['status'], 'verified')
                self.assertEqual(case['typography']['display']['logical']['rotation'], int(width > height))

    def test_loading_launch_recreates_empty_root_then_reaches_main_without_launcher(self):
        self.prepare(2676, 1236)
        before = len(self.android.calls)
        self.loading_launch()
        self.assertEqual(self.android.instance, 2)
        self.assertEqual(self.android.scene, 'actual-main-loading')
        self.assertEqual(self.android.foreground, 'local.pocketchat.test/local.pocketchat.MainActivity')
        self.display.require(2676, 1236, 480, 1.0, 'no', 'actual-loading')
        launches = self.android.calls[before:]
        self.assertFalse(any(c[:3] == ('shell', 'am', 'force-stop') or c[:3] == ('shell', 'input', 'keyevent') for c in launches))

    def test_old_loading_launch_and_single_top_still_leave_preparation_empty(self):
        for options in (dict(remove_clear=True), dict(single_top=True)):
            with self.subTest(options=options):
                self.android = StandardRootSceneModel()
                self.display = GlassDisplay(self.android, self.out, lambda p: '0' * 64)
                self.prepare(2676, 1236)
                self.loading_launch(**options)
                self.assertEqual(self.android.instance, 1)
                self.assertEqual(self.android.scene, 'glass-display-preparation')
                self.assertNotIn('MainActivity', self.android.foreground)

    def test_single_top_cannot_fake_fresh_typography_scene(self):
        self.prepare()
        with self.assertRaisesRegex(ValueError, 'typography observation is incomplete or failed'):
            self.typography(single_top=True)
        self.assertEqual(self.android.instance, 1)

    def test_fresh_scene_must_still_pass_current_nonce_and_all_glyph_checks(self):
        for invalid in ('bad_nonce', 'bad_glyph'):
            with self.subTest(invalid=invalid):
                self.android = StandardRootSceneModel()
                self.display = GlassDisplay(self.android, self.out, lambda p: '0' * 64)
                setattr(self.android, invalid, True)
                self.prepare()
                with self.assertRaises(ValueError):
                    self.typography()
                self.assertEqual(self.android.instance, 2)


if __name__ == '__main__':
    unittest.main()
