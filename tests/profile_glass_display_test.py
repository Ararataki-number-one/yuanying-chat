"""Host display-transport regressions; never substitute for Android capture.

The API32 clamp excerpt is from b5abba run42474937531/a1's original window
dump. The transport model exercises the required natural-size/rotation
protocol and readback failures; it is explicitly not an emulator result.
"""
import ast
import copy
import hashlib
from pathlib import Path
import struct
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools/gecko'))
from glass_display import GlassDisplay, validate_display, verify_png, window_geometry


API32_CLAMP = '''WINDOW MANAGER DISPLAY CONTENTS (dumpsys window displays)
  Display: mDisplayId=0 rootTasks=5
    init=1236x2676 480dpi base=2472x1236 480dpi cur=2472x1236 app=2472x1236 rng=1236x1164-2472x2400
  DisplayFrames w=2472 h=1236 r=0
'''
API35_FORCED = '''WINDOW MANAGER DISPLAY CONTENTS (dumpsys window displays)
  Display: mDisplayId=0 (organized)
    init=1236x2676 480dpi mMinSizeOfResizeableTaskDp=220 base=2676x1236 480dpi cur=2676x1236 app=2676x1236 rng=1236x1236-2676x2676
  DisplayFrames w=2676 h=1236 r=0
'''


class Android32DisplayModel:
    """Faithful scope: observed forced-width cap, logical rotation, settings.

    No Android rendering, lifecycle, input or device acceptance is simulated.
    """
    def __init__(self):
        self.physical = (1236, 2676)
        self.forced = None
        self.density = None
        self.mode = 'lock 0'
        self.settings = dict(font_scale='1.0', accelerometer_rotation='0', user_rotation='0')
        self.night = 'no'
        self.target_allows_rotation = True
        self.calls = []
        self.fail_next = None

    def frame(self):
        width, height = self.forced or self.physical
        rotation = int(self.mode[-1]) if self.mode.startswith('lock ') else 0
        if not self.target_allows_rotation:
            rotation = 0
        if rotation % 2:
            width, height = height, width
        return width, height, rotation

    def __call__(self, *parts, **kwargs):
        self.calls.append(parts)
        if parts == self.fail_next:
            self.fail_next = None
            raise OSError('controlled transport failure')
        if parts[:2] != ('shell', 'wm') and parts[:2] != ('shell', 'settings') and parts[:2] not in (('shell', 'am'), ('shell', 'cmd'), ('shell', 'dumpsys')):
            raise AssertionError('Unexpected input or UI mutation: ' + repr(parts))
        p = parts[1:]
        if p == ('wm', 'size'):
            text = 'Physical size: 1236x2676\n'
            if self.forced:
                text += 'Override size: %dx%d\n' % self.forced
            return text.encode()
        if p[:2] == ('wm', 'size'):
            value = p[2]
            requested = None if value == 'reset' else tuple(map(int, value.split('x')))
            self.forced = None if requested in (None, self.physical) else tuple(min(v, 2472) for v in requested)
        elif p == ('wm', 'density'):
            return ('Physical density: 480\n' + (('Override density: %d\n' % self.density) if self.density else '')).encode()
        elif p[:2] == ('wm', 'density'):
            self.density = None if p[2] in ('reset', '480') else int(p[2])
        elif p == ('wm', 'user-rotation'):
            return (self.mode + '\n').encode()
        elif p[:2] == ('wm', 'user-rotation'):
            self.mode = ' '.join(p[2:])
            self.settings['accelerometer_rotation'] = '1' if self.mode == 'free' else '0'
            if self.mode.startswith('lock '):
                self.settings['user_rotation'] = p[3]
        elif p[:3] == ('settings', 'get', 'system'):
            return (self.settings.get(p[3], 'null') + '\n').encode()
        elif p[:3] == ('settings', 'put', 'system'):
            self.settings[p[3]] = p[4]
        elif p[:3] == ('settings', 'delete', 'system'):
            self.settings.pop(p[3], None)
        elif p == ('cmd', 'uimode', 'night'):
            return ('Night mode: ' + self.night + '\n').encode()
        elif p[:3] == ('cmd', 'uimode', 'night'):
            self.night = p[3]
        elif p == ('am', 'get-config'):
            w, h, r = self.frame()
            return ('config: en-rUS-w%ddp-h%ddp-%s-%s-xxhdpi-v32\nabi: x86_64\n' %
                    (w // 3, h // 3, 'land' if w > h else 'port', 'night' if self.night == 'yes' else 'notnight')).encode()
        elif p == ('dumpsys', 'window', 'displays'):
            w, h, r = self.frame()
            base = self.forced or self.physical
            return ('  Display: mDisplayId=0 rootTasks=5\n'
                    '    init=1236x2676 480dpi base=%dx%d %ddpi cur=%dx%d app=%dx%d rng=0x0-0x0\n'
                    '  DisplayFrames w=%d h=%d r=%d\n' %
                    (*base, self.density or 480, w, h, w, h, w, h, r)).encode()
        else:
            raise AssertionError('Unmodeled command: ' + repr(parts))
        return b''


class GlassDisplayRegressionTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.out = Path(self.temp.name)
        self.android = Android32DisplayModel()
        self.display = GlassDisplay(self.android, self.out, lambda p: hashlib.sha256(Path(p).read_bytes()).hexdigest())

    def tearDown(self):
        self.temp.cleanup()

    def test_original_api32_clamp_is_observed_not_requested_width(self):
        self.assertEqual(window_geometry(API32_CLAMP), dict(width=2472, height=1236, rotation=0, density=480))
        self.android('shell', 'wm', 'size', '2676x1236')
        observed = self.display.observe('old-command')
        self.assertEqual(observed['logical']['width'], 2472)
        with self.assertRaises(ValueError):
            validate_display(observed, 2676, 1236, 480, 0, 1, 'no')

    def test_api35_actual_forced_landscape_format_is_read_exactly(self):
        self.assertEqual(window_geometry(API35_FORCED), dict(width=2676, height=1236, rotation=0, density=480))

    def test_natural_portrait_plus_real_rotation_obtains_requested_landscape(self):
        self.display.configure(2676, 1236, 480, 1.0, 'no')
        state = self.display.require(2676, 1236, 480, 1.0, 'no', 'rotated')
        self.assertEqual(state['logical'], dict(width=2676, height=1236, density=480, rotation=1))
        self.assertEqual(state['size'], 'Physical size: 1236x2676')
        self.assertIn(('shell', 'wm', 'size', '1236x2676'), self.android.calls)
        self.assertNotIn(('shell', 'wm', 'size', '2676x1236'), self.android.calls)
        self.assertIn(('shell', 'wm', 'user-rotation', 'lock', '1'), self.android.calls)
        self.assertTrue((self.out / state['window']['file']).is_file())

    def test_portrait_only_home_is_not_accepted_as_target_activity_rotation(self):
        self.android.target_allows_rotation = False
        self.display.configure(2676, 1236, 480, 1.0, 'no')
        with self.assertRaises(ValueError):
            self.display.require(2676, 1236, 480, 1.0, 'no', 'home')
        self.android.target_allows_rotation = True
        self.assertEqual(self.display.require(2676, 1236, 480, 1.0, 'no', 'target')['logical']['rotation'], 1)

    def test_next_portrait_case_restores_rotation_zero_and_preserves_narrow_case(self):
        self.display.configure(2676, 1236, 480, 1.0, 'no')
        self.display.configure(960, 2220, 480, 1.6, 'no')
        state = self.display.require(960, 2220, 480, 1.6, 'no', 'narrow')
        self.assertEqual(state['logical'], dict(width=960, height=2220, density=480, rotation=0))

    def test_natural_size_text_cannot_replace_logical_frame_or_rotation(self):
        state = self.display.observe('before')
        for values in (dict(width=2676, height=1236, rotation=0), dict(width=2472, height=1236, rotation=1)):
            bad = copy.deepcopy(state)
            bad['logical'].update(values)
            with self.subTest(values=values), self.assertRaises(ValueError):
                validate_display(bad, 2676, 1236, 480, 1, 1, 'no')

    def test_wrong_density_font_theme_orientation_or_rotation_settings_reject(self):
        self.display.configure(2676, 1236, 480, 1.3, 'yes')
        state = self.display.require(2676, 1236, 480, 1.3, 'yes', 'good')
        changes = [('density', 'wrong'), ('fontScale', 'nan'), ('fontScale', '1.0'),
                   ('configuration', 'config: en-rUS-land-notnight-v32'),
                   ('configuration', 'config: en-rUS-port-night-v32'),
                   ('rotationMode', 'free'), ('accelerometerRotation', '1'), ('userRotation', '0'),
                   ('nightMode', 'auto')]
        for key, value in changes:
            bad = copy.deepcopy(state)
            if key == 'density':
                bad['logical']['density'] = 320
            else:
                bad[key] = value
            with self.subTest(key=key, value=value), self.assertRaises(ValueError):
                validate_display(bad, 2676, 1236, 480, 1, 1.3, 'yes')

    def test_missing_duplicate_or_disagreeing_window_readback_rejects(self):
        for raw in ('', API32_CLAMP.replace('DisplayFrames', 'UnknownFrames'), API32_CLAMP + API32_CLAMP,
                    API32_CLAMP.replace('cur=2472x1236', 'cur=2676x1236')):
            with self.subTest(raw=raw), self.assertRaises(ValueError):
                window_geometry(raw)

    def test_original_png_must_match_exact_logical_dimensions(self):
        p = self.out / 'original.png'
        p.write_bytes(b'\x89PNG\r\n\x1a\n' + struct.pack('>I', 13) + b'IHDR' + struct.pack('>II', 2676, 1236))
        self.assertTrue(verify_png(p, 2676, 1236)['verified'])
        p.write_bytes(p.read_bytes()[:16] + struct.pack('>II', 2472, 1236))
        with self.assertRaises(ValueError):
            verify_png(p, 2676, 1236)

    def test_restore_preserves_original_overrides_free_mode_and_settings(self):
        self.android('shell', 'wm', 'size', '1080x2160')
        self.android('shell', 'wm', 'density', '420')
        self.android('shell', 'wm', 'user-rotation', 'free')
        self.android.settings['font_scale'] = '1.15'
        self.android.night = 'yes'
        previous = self.display.observe('previous')
        self.display.configure(2676, 1236, 480, 1.0, 'no')
        restored = self.display.restore(previous, 'restored')
        for key in ('size', 'density', 'rotationMode', 'userRotation', 'accelerometerRotation', 'fontScale', 'nightMode', 'logical'):
            self.assertEqual(restored[key], previous[key], key)

    def test_auto_and_custom_night_policies_are_restored_as_policies(self):
        for policy in ('auto', 'custom'):
            with self.subTest(policy=policy):
                self.android.night = policy
                previous = self.display.observe('policy-previous')
                self.display.configure(2676, 1236, 480, 1.0, 'yes')
                restored = self.display.restore(previous, 'policy-restored')
                self.assertEqual(restored['nightMode'], policy)
                self.assertEqual(self.android.night, policy)
                self.assertIn('notnight', restored['configuration'])

    def test_failed_restore_still_attempts_other_settings_and_refuses_pass(self):
        previous = self.display.observe('previous')
        self.display.configure(2676, 1236, 480, 1.3, 'yes')
        self.android.fail_next = ('shell', 'wm', 'size', 'reset')
        with self.assertRaisesRegex(ValueError, 'restoration failed'):
            self.display.restore(previous, 'failed-restore')
        self.assertEqual(self.android.settings['font_scale'], '1.0')
        self.assertEqual(self.android.settings['user_rotation'], '0')
        self.assertEqual(self.android.night, 'no')

    def test_both_required_loading_and_seven_case_paths_share_real_setup(self):
        source = (ROOT / 'tools/gecko/glass_ui_validation.py').read_text()
        tree = ast.parse(source)
        for name in ('capture_loading_landscape', 'capture_acceptance_suite'):
            method = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == name)
            calls = [n.func.attr for n in ast.walk(method) if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute)
                     and isinstance(n.func.value, ast.Name) and n.func.value.id == 'display']
            with self.subTest(path=name):
                self.assertIn('configure', calls)
                self.assertIn('require', calls)
                self.assertIn('restore', calls)
        configurations = next(n.value for n in tree.body if isinstance(n, ast.Assign)
            and any(isinstance(t, ast.Name) and t.id == 'CONFIGURATIONS' for t in n.targets))
        self.assertEqual(ast.literal_eval(configurations), (
            ('default-light', 412, 892, 1.0, 'no'), ('enlarged-light', 412, 892, 1.3, 'no'),
            ('narrow-light', 320, 740, 1.6, 'no'), ('landscape-light', 892, 412, 1.0, 'no'),
            ('default-dark', 412, 892, 1.0, 'yes'), ('enlarged-dark', 412, 892, 1.3, 'yes'),
            ('safearea-light', 412, 892, 1.0, 'no')))


if __name__ == '__main__':
    unittest.main()
