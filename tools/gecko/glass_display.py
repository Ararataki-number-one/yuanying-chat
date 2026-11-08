"""Source-bound disposable-emulator display setup and exact readback.

Android 12 can clamp a forced landscape width. Keep the natural display in
portrait order and rotate it, then require the observed logical frame instead
of treating the successful wm command or its natural-size text as proof.
"""
import math
import re
import struct
from pathlib import Path


def window_geometry(raw):
    frames = re.findall(r'^\s*DisplayFrames w=(\d+) h=(\d+) r=([0-3])\s*$', raw, re.M)
    summaries = re.findall(r'^\s*init=(\d+)x(\d+) (\d+)dpi (.*)$', raw, re.M)
    if (len(frames) != 1 or len(summaries) != 1
            or len(re.findall(r'^\s*DisplayFrames\b', raw, re.M)) != 1
            or len(re.findall(r'^\s*init=', raw, re.M)) != 1):
        raise ValueError('One actual logical display frame and density are required')
    initial_width, initial_height, initial_density, summary = summaries[0]
    current = re.findall(r'\bcur=(\d+)x(\d+)(?=\s|$)', summary)
    base = re.findall(r'\bbase=(\d+)x(\d+) (\d+)dpi(?=\s|$)', summary)
    if (len(current) != 1 or len(re.findall(r'\bcur=', summary)) != 1
            or len(base) > 1 or len(re.findall(r'\bbase=', summary)) != len(base)
            or min(map(int, (initial_width, initial_height, initial_density))) <= 0
            or base and min(map(int, base[0])) <= 0):
        raise ValueError('One observed current display and a complete optional base override are required')
    width, height, rotation = map(int, frames[0])
    density = int(base[0][2] if base else initial_density)
    current_width, current_height = map(int, current[0])
    if min(width, height, density) <= 0 or (width, height) != (current_width, current_height):
        raise ValueError('Window logical frame differs from current display bounds')
    return dict(width=width, height=height, rotation=rotation, density=density)


def size_setting(raw, name):
    physical = re.findall(r'^Physical ' + name + r': (\d+(?:x\d+)?)\s*$', raw, re.M)
    override = re.findall(r'^Override ' + name + r': (\d+(?:x\d+)?)\s*$', raw, re.M)
    if len(physical) != 1 or len(override) > 1:
        raise ValueError('One physical and at most one forced display ' + name + ' are required')
    return override[0] if override else 'reset'


def rotation_setting(raw):
    value = raw.strip()
    if re.fullmatch(r'free|lock [0-3]', value) is None:
        raise ValueError('Unrecognized actual wm user-rotation state')
    return value.split()


def night_setting(raw):
    match = re.fullmatch(r'Night mode: (auto|no|yes|custom)', raw.strip())
    if match is None:
        raise ValueError('Unrecognized actual Android night-mode policy')
    return match[1]


def validate_display(state, width, height, density, rotation, font, night):
    expected = dict(width=width, height=height, density=density, rotation=rotation)
    if state['logical'] != expected:
        raise ValueError('Actual logical display/rotation/density differs from the requested case')
    actual_font = float(state['fontScale'])
    requested_font = float(font)
    parts = state['configuration'].splitlines()[0].split('-')
    if (('land' if width > height else 'port') not in parts
            or ('night' if night == 'yes' else 'notnight') not in parts
            or not math.isfinite(actual_font) or not math.isfinite(requested_font)
            or actual_font <= 0 or requested_font <= 0 or abs(actual_font - requested_font) > .001
            or state['nightMode'] != night
            or state['rotationMode'] != 'lock ' + str(rotation)
            or state['accelerometerRotation'] != '0' or state['userRotation'] != str(rotation)):
        raise ValueError('Actual configuration/font/theme/rotation settings differ from the requested case')
    return state


def verify_png(path, width, height):
    raw = Path(path).read_bytes()
    if (len(raw) < 24 or raw[:8] != b'\x89PNG\r\n\x1a\n' or raw[12:16] != b'IHDR'
            or struct.unpack('>II', raw[16:24]) != (width, height)):
        raise ValueError('Original Android PNG dimensions differ from the observed logical display')
    return dict(width=width, height=height, verified=True)


class GlassDisplay:
    def __init__(self, adb, out, sha):
        self.adb, self.out, self.sha = adb, Path(out), sha

    def prepare(self, component, stem):
        """Leave launcher orientation overrides before changing display settings.

        Android may restore an earlier user rotation when its NOSENSOR home
        Activity loses the foreground. The explicit empty test-only Activity
        must already own the resumed/focused window before configure() runs.
        No glyph, document, or release acceptance observation occurs here.
        """
        if component != 'local.pocketchat.test/local.pocketchat.UiVisualIntegrationActivity':
            raise ValueError('The empty glass display preparation Activity is required')
        self.adb('shell', 'am', 'start', '-W', '-n', component,
                 '--es', 'visualAction', 'glass-display-preparation')
        raw = self.adb('shell', 'dumpsys', 'activity', 'activities').decode('utf-8', 'strict')
        path = self.out / (stem + '-activity.txt')
        path.write_text(raw)
        resumed = [line.strip() for line in raw.splitlines()
                   if re.search(r'\b(?:mResumedActivity|topResumedActivity)\s*[:=]', line)]
        if not resumed or any(re.search(re.escape(component) + r'(?=\s|})', line) is None for line in resumed):
            raise ValueError('The empty display preparation Activity is not actually resumed')
        state = self.observe(stem)
        window = (self.out / state['window']['file']).read_text()
        focused = re.findall(r'^\s*mCurrentFocus=Window\{[^\n]*\}\s*$', window, re.M)
        if len(focused) != 1 or re.search(re.escape(component) + r'(?=\s|})', focused[0]) is None:
            raise ValueError('The empty display preparation Activity does not own the focused window')
        return dict(component=component, action='glass-display-preparation',
                    activity=dict(file=path.name, sha256=self.sha(path), resumed=resumed),
                    beforeConfiguration=state, noGlyphOrDocumentObservation=True)

    def observe(self, stem):
        read = lambda *parts: self.adb('shell', *parts).decode('utf-8', 'strict').strip()
        state = dict(size=read('wm', 'size'), density=read('wm', 'density'),
            rotationMode=read('wm', 'user-rotation'),
            accelerometerRotation=read('settings', 'get', 'system', 'accelerometer_rotation'),
            userRotation=read('settings', 'get', 'system', 'user_rotation'),
            fontScale=read('settings', 'get', 'system', 'font_scale'),
            nightMode=night_setting(read('cmd', 'uimode', 'night')),
            configuration=read('am', 'get-config'))
        raw = read('dumpsys', 'window', 'displays')
        path = self.out / (stem + '-display.txt')
        path.write_text(raw)
        state.update(logical=window_geometry(raw), window=dict(file=path.name, sha256=self.sha(path)))
        size_setting(state['size'], 'size')
        size_setting(state['density'], 'density')
        rotation_setting(state['rotationMode'])
        return state

    def configure(self, width, height, density, font, night):
        if (any(type(v) is not int or v <= 0 for v in (width, height, density))
                or night not in ('no', 'yes')):
            raise ValueError('Explicit positive display geometry and light/dark mode required')
        rotation = 1 if width > height else 0
        natural = (min(width, height), max(width, height))
        self.adb('shell', 'wm', 'user-rotation', 'lock', '0')
        self.adb('shell', 'wm', 'size', str(natural[0]) + 'x' + str(natural[1]))
        self.adb('shell', 'wm', 'density', str(density))
        self.adb('shell', 'settings', 'put', 'system', 'accelerometer_rotation', '0')
        self.adb('shell', 'settings', 'put', 'system', 'user_rotation', str(rotation))
        self.adb('shell', 'wm', 'user-rotation', 'lock', str(rotation))
        self.adb('shell', 'settings', 'put', 'system', 'font_scale', str(font))
        self.adb('shell', 'cmd', 'uimode', 'night', night)
    def require(self, width, height, density, font, night, stem):
        # Read after the actual target Activity has launched: a portrait-only
        # home Activity may legitimately override the user's rotation lock.
        state = self.observe(stem)
        try:
            return validate_display(state, width, height, density,
                                    1 if width > height else 0, font, night)
        except ValueError as error:
            error.observedDisplay = state
            raise

    def restore(self, previous, stem):
        # Preserve the actual original forced/reset state, rotation mode and
        # settings. A natural-size string alone cannot verify logical bounds.
        errors = []

        def command(*parts):
            try:
                self.adb('shell', *parts, timeout=6)
            except Exception as error:
                errors.append(type(error).__name__ + ': ' + str(error))

        command('wm', 'user-rotation', 'lock', '0')
        command('wm', 'size', size_setting(previous['size'], 'size'))
        command('wm', 'density', size_setting(previous['density'], 'density'))
        for key, value in (('font_scale', previous['fontScale']),
                           ('accelerometer_rotation', previous['accelerometerRotation']),
                           ('user_rotation', previous['userRotation'])):
            if value == 'null':
                command('settings', 'delete', 'system', key)
            else:
                command('settings', 'put', 'system', key, value)
        config = previous['configuration'].splitlines()[0].split('-')
        command('cmd', 'uimode', 'night', previous['nightMode'])
        command('wm', 'user-rotation', *rotation_setting(previous['rotationMode']))
        restored = self.observe(stem)
        keys = ('size', 'density', 'rotationMode', 'accelerometerRotation', 'userRotation', 'fontScale', 'nightMode', 'logical')
        if any(restored[key] != previous[key] for key in keys):
            errors.append('Actual original display/rotation/settings were not restored')
        restored_config = restored['configuration'].splitlines()[0].split('-')
        if any((key in restored_config) != (key in config) for key in ('night', 'notnight', 'land', 'port')):
            errors.append('Actual original display orientation/theme was not restored')
        if errors:
            raise ValueError('Display restoration failed: ' + '; '.join(errors))
        return restored
