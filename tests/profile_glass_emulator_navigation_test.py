"""Disposable AVD setup controls; no emulator or Android execution is claimed.

Android 12 DisplayPolicy reads qemu.hw.mainkeys at construction: 0 forces
software navigation and 1 disables it. The workflow pins both the AVD hardware
capability and that boot property, then preserves actual readback/Insets dumps.
The pinned images may return an empty property even when navigation is visible;
an empty value remains diagnostic data, not an invented successful readback.
Only later real per-case Insets observations establish that both bars exist.
"""
import ast
import hashlib
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import unittest

import yaml


ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / '.github/workflows/glass-release-validation.yml'


def setup_step():
    workflow = yaml.safe_load(WORKFLOW.read_text())
    job = workflow['jobs']['glass-device-acceptance']
    step = next(row for row in job['steps']
                if row.get('name', '').startswith('Prepare the pinned disposable Android '))
    return workflow, job, step


def actual_config_script():
    run = setup_step()[2]['run']
    marker = "python3 - <<'PY'\n"
    if run.count(marker) != 1:
        raise AssertionError('Review the actual AVD configuration producer')
    return run.split(marker, 1)[1].split('\nPY\n', 1)[0]


def configure(avd_home, script=None):
    return subprocess.run([sys.executable, '-c', script or actual_config_script()],
                          env=dict(os.environ, ANDROID_AVD_HOME=str(avd_home)),
                          capture_output=True, text=True, timeout=10)


def actual_bar_parser():
    source = (ROOT / 'tools/gecko/glass_ui_validation.py').read_text()
    nodes = [node for node in ast.parse(source).body
             if isinstance(node, ast.FunctionDef) and node.name == 'system_bar_sources']
    if len(nodes) != 1:
        raise AssertionError('One real per-case system-bar observer required')
    namespace = {'re': re}
    exec(compile(ast.Module(body=nodes, type_ignores=[]),
                 str(ROOT / 'tools/gecko/glass_ui_validation.py'), 'exec'), namespace)
    return namespace['system_bar_sources']


class GlassEmulatorNavigation(unittest.TestCase):
    def test_actual_avd_configuration_replaces_duplicate_hardware_keys_and_preserves_other_settings(self):
        with tempfile.TemporaryDirectory(prefix='glass-avd-navigation-') as temporary:
            home = Path(temporary)
            path = home / 'glassnavigation.avd/config.ini'
            path.parent.mkdir()
            path.write_text('AvdId=glassnavigation\nhw.mainKeys=yes\n hw.mainKeys = yes\n'
                            'hw.lcd.width=1080\ndisk.dataPartition.size=6G\n')
            result = configure(home)
            self.assertEqual(result.returncode, 0, result.stderr)
            pairs = [line.split('=', 1) for line in path.read_text().splitlines()]
            keys = [key.strip() for key, value in pairs]
            self.assertEqual(keys.count('hw.mainKeys'), 1)
            self.assertEqual(dict(pairs)['hw.mainKeys'], 'no')
            self.assertEqual(dict(pairs)['hw.lcd.width'], '1236')
            self.assertEqual(dict(pairs)['hw.lcd.height'], '2676')
            self.assertEqual(dict(pairs)['hw.lcd.density'], '480')
            self.assertEqual(dict(pairs)['AvdId'], 'glassnavigation')
            self.assertEqual(dict(pairs)['disk.dataPartition.size'], '6G')
            original = path.read_bytes()
            self.assertEqual(configure(home).returncode, 0)
            self.assertEqual(path.read_bytes(), original)

    def test_missing_or_directory_config_is_rejected_instead_of_creating_unreviewed_avd(self):
        with tempfile.TemporaryDirectory(prefix='glass-avd-navigation-') as temporary:
            home = Path(temporary)
            path = home / 'glassnavigation.avd/config.ini'
            path.parent.mkdir()
            self.assertNotEqual(configure(home).returncode, 0)
            self.assertFalse(path.exists())
            path.mkdir()
            self.assertNotEqual(configure(home).returncode, 0)
            self.assertEqual(list(path.iterdir()), [])

    def test_symlink_config_and_avd_directory_are_rejected_without_writing_target(self):
        with tempfile.TemporaryDirectory(prefix='glass-avd-navigation-') as temporary:
            base = Path(temporary)
            outside = base / 'outside'
            outside.mkdir()
            target = outside / 'config.ini'
            raw = b'hw.mainKeys=yes\npreserve=actual-original\n'
            target.write_bytes(raw)
            for mode in ('file', 'directory', 'home'):
                with self.subTest(mode=mode):
                    home = base / mode
                    if mode == 'home':
                        (outside / 'glassnavigation.avd').mkdir()
                        (outside / 'glassnavigation.avd/config.ini').write_bytes(raw)
                        home.symlink_to(outside, target_is_directory=True)
                    else:
                        home.mkdir()
                        avd = home / 'glassnavigation.avd'
                        if mode == 'file':
                            avd.mkdir()
                            (avd / 'config.ini').symlink_to(target)
                        else:
                            avd.symlink_to(outside, target_is_directory=True)
                    result = configure(home)
                    self.assertNotEqual(result.returncode, 0)
                    self.assertIn('ordinary config', result.stderr)
                    self.assertEqual(target.read_bytes(), raw)

    def test_boot_property_is_on_emulator_start_before_actual_readback_and_insets_archival(self):
        run = setup_step()[2]['run']
        startup = [line for line in run.splitlines()
                   if line.startswith('"$ANDROID_HOME/emulator/emulator" ')]
        self.assertEqual(len(startup), 1)
        self.assertEqual(startup[0].count('-prop qemu.hw.mainkeys=0'), 1)
        self.assertNotIn('qemu.hw.mainkeys=1', run)
        self.assertNotIn('setprop qemu.hw.mainkeys', run)
        booted = run.index('test "$task_glass_booted" = true')
        getprop = run.index('shell getprop qemu.hw.mainkeys > work/glass-navigation/navigation-mainkeys.txt')
        displays = run.index('shell dumpsys window displays > work/glass-navigation/navigation-boot-displays.txt')
        windows = run.index('shell dumpsys window windows > work/glass-navigation/navigation-boot-windows.txt')
        self.assertLess(run.index(startup[0]), booted)
        self.assertLess(booted, getprop)
        self.assertLess(getprop, displays)
        self.assertLess(displays, windows)

    def test_actual_empty_readback_is_preserved_and_does_not_skip_the_real_insets_observers(self):
        # Both APIs in real run42485197788/a1 returned exactly this byte, while
        # the navigation-only probe42486920602 observed real API32 system bars.
        # This executes the actual shell tail with a synthetic adb transport;
        # it is not another emulator execution or an application acceptance.
        observed = b'\n'
        self.assertEqual(hashlib.sha256(observed).hexdigest(),
            '01ba4719c80b6fe911b091a7c05124b64eeece964e09c058ef8f9805daca546b')
        run = setup_step()[2]['run']
        first = 'timeout 5 "$ANDROID_HOME/platform-tools/adb" -s emulator-5554 shell getprop qemu.hw.mainkeys'
        tail = run[run.index(first):]
        bad_check = 'test "$(tr -d \'\\r\\n\' < work/glass-navigation/navigation-mainkeys.txt)" = 0\n'
        with tempfile.TemporaryDirectory(prefix='glass-mainkeys-readback-') as temporary:
            root = Path(temporary)
            sdk = root / 'sdk'
            adb = sdk / 'platform-tools/adb'
            adb.parent.mkdir(parents=True)
            adb.write_text('#!/bin/sh\n'
                'shift 2\n'
                'printf "%s\\n" "$*" >> "$GLASS_COMMAND_LOG"\n'
                'case "$*" in\n'
                ' "shell getprop qemu.hw.mainkeys") printf "\\n" ;;\n'
                ' "shell dumpsys window displays") printf "retained actual display transport\\n" ;;\n'
                ' "shell dumpsys window windows") printf "retained actual window transport\\n" ;;\n'
                ' *) exit 11 ;;\n'
                'esac\n')
            adb.chmod(0o700)
            for name, script, expected in (
                    ('current', tail, 0),
                    ('old-invalid-zero-guard', tail.replace(
                        'timeout 10 "$ANDROID_HOME/platform-tools/adb" -s emulator-5554 shell dumpsys window displays',
                        bad_check + 'timeout 10 "$ANDROID_HOME/platform-tools/adb" -s emulator-5554 shell dumpsys window displays', 1), 1)):
                with self.subTest(name=name):
                    work = root / name
                    folder = work / 'work/glass-navigation'
                    folder.mkdir(parents=True)
                    log = work / 'adb-commands.txt'
                    result = subprocess.run(['bash', '-euo', 'pipefail', '-c', script], cwd=work,
                        env=dict(os.environ, ANDROID_HOME=str(sdk), GLASS_COMMAND_LOG=str(log)),
                        capture_output=True, text=True, timeout=15)
                    self.assertEqual(result.returncode, expected, result.stderr)
                    self.assertEqual((folder / 'navigation-mainkeys.txt').read_bytes(), observed)
                    commands = log.read_text().splitlines()
                    if name == 'current':
                        self.assertEqual(commands, ['shell getprop qemu.hw.mainkeys',
                            'shell dumpsys window displays', 'shell dumpsys window windows'])
                        self.assertEqual((folder / 'navigation-boot-displays.txt').read_bytes(),
                            b'retained actual display transport\n')
                        self.assertEqual((folder / 'navigation-boot-windows.txt').read_bytes(),
                            b'retained actual window transport\n')
                    else:
                        self.assertEqual(commands, ['shell getprop qemu.hw.mainkeys'])
                        self.assertFalse((folder / 'navigation-boot-displays.txt').exists())

    def test_original_api_matrix_budgets_render_backend_and_artifact_preservation_remain(self):
        workflow, job, step = setup_step()
        self.assertEqual(workflow['permissions'], {'contents': 'read'})
        self.assertEqual(job['strategy'], {'fail-fast': False, 'matrix': {'device-api': [35, 32]}})
        self.assertEqual(job['runs-on'], 'ubuntu-24.04')
        self.assertEqual(job['timeout-minutes'], 60)
        capture = next(row for row in job['steps'] if row.get('name') == 'Run real glass rendering, input and layout acceptance')
        self.assertEqual(capture['timeout-minutes'], 20)
        self.assertIn('--acceptance-suite --device-api ${{ matrix.device-api }}', capture['run'])
        self.assertNotIn('continue-on-error', capture)
        self.assertIn('-gpu swangle -feature -Vulkan -memory 3072 -cores 2', step['run'])
        self.assertIn('test "$task_glass_booted" = true', step['run'])
        upload = next(row for row in job['steps'] if row.get('name') == 'Upload glass acceptance cases, recordings and raw diagnostics')
        self.assertIn('work/glass-navigation/**/*.txt', upload['with']['path'])

    def test_actual_missing_navigation_bar_still_fails_even_with_valid_boot_property_text(self):
        parser = actual_bar_parser()
        status = 'InsetsSource mType=ITYPE_STATUS_BAR mFrame=[0,0][1236,72] mVisible=true'
        with self.assertRaisesRegex(ValueError, 'Both actual status-bar and navigation-bar'):
            parser('qemu.hw.mainkeys=0\n' + status)
        with self.assertRaisesRegex(ValueError, 'Both actual status-bar and navigation-bar'):
            parser('InsetsSource mType=ITYPE_NAVIGATION_BAR mFrame=[0,2604][1236,2676] mVisible=true')
        for navigation in (
                'InsetsSource mType=ITYPE_NAVIGATION_BAR mFrame=[0,2604][1236,2676] mVisible=true',
                'InsetsSource type=navigationBars frame=[0,2604][1236,2676] visible=true'):
            observed = parser(status + '\n' + navigation)
            self.assertEqual(observed['navigationBars'], [{'bounds': [0, 2604, 1236, 2676], 'visible': True}])
            self.assertEqual(observed['statusBars'], [{'bounds': [0, 0, 1236, 72], 'visible': True}])


if __name__ == '__main__':
    unittest.main(verbosity=2)
