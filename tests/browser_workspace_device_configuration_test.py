"""Execute current emulator setup snippets with local files and an explicit adb boundary.

These checks cover the committed workflow, not Android navigation-bar execution.
Actual status/navigation InsetsSources remain required by the device acceptance gate.
"""
from pathlib import Path
import os
import re
import subprocess
import tempfile
import unittest

import yaml


ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / '.github/workflows/browser-workspace-validation.yml'


class BrowserWorkspaceDeviceConfigurationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.workflow = yaml.safe_load(WORKFLOW.read_text())
        cls.job = cls.workflow['jobs']['glass-device-acceptance']
        cls.setup = next(step['run'] for step in cls.job['steps'] if step.get('id') == 'browser-emulator')

    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.directory = Path(self.temporary.name)
        self.avd = self.directory / 'avd/glassnavigation.avd'
        self.avd.mkdir(parents=True)
        self.evidence = self.directory / 'work/glass-navigation'
        self.evidence.mkdir(parents=True)
        self.config = self.avd / 'config.ini'
        self.environment = dict(os.environ, ANDROID_AVD_HOME=str(self.avd.parent))

    def configure(self, original):
        self.config.write_text(original)
        scripts = re.findall(r"^python3 - <<'PY'\n(.*?)^PY$", self.setup, re.M | re.S)
        self.assertEqual(len(scripts), 1)
        result = subprocess.run(['python3', '-c', scripts[0]], cwd=self.directory,
                                env=self.environment, capture_output=True, text=True, check=True)
        return result, self.config.read_text()

    def test_current_avd_disables_hardware_navigation_keys_and_preserves_other_properties(self):
        _, configured = self.configure('hw.mainKeys=yes\nhw.lcd.width=320\nimage.sysdir.1=owned-image/\n')
        values = dict(line.split('=', 1) for line in configured.splitlines())
        self.assertEqual(values['hw.mainKeys'], 'no')
        self.assertEqual(values['image.sysdir.1'], 'owned-image/')
        self.assertEqual((values['hw.lcd.width'], values['hw.lcd.height'], values['hw.lcd.density']),
                         ('1236', '2676', '480'))

    def test_stale_spaced_or_duplicate_navigation_keys_cannot_survive(self):
        _, configured = self.configure('hw.mainKeys = yes\n hw.mainKeys=yes\nhw.mainKeys=yes\nother=value\n')
        entries = [line.split('=', 1)[1].strip() for line in configured.splitlines()
                   if line.split('=', 1)[0].strip() == 'hw.mainKeys']
        self.assertEqual(entries, ['no'])
        self.assertIn('other=value\n', configured)

    def test_config_receipt_and_setup_log_contain_actual_written_bytes(self):
        result, configured = self.configure('hw.mainKeys=yes\nother=value\n')
        self.assertEqual((self.evidence / 'avd-config.txt').read_text(), configured)
        self.assertIn(configured, result.stdout)

    def post_boot(self, fail=False):
        sdk = self.directory / 'sdk/platform-tools'
        sdk.mkdir(parents=True)
        adb = sdk / 'adb'
        adb.write_text('#!/bin/sh\n'
            + ('exit 17\n' if fail else
               'case "$*" in\n'
               '  "-s emulator-5554 shell getprop") printf "[qemu.hw.mainkeys]: [0]\\n" ;;\n'
               '  "-s emulator-5554 shell dumpsys window displays") printf "controlled window dump\\n" ;;\n'
               '  *) echo "unsupported adb call" >&2; exit 91 ;;\n'
               'esac\n'))
        adb.chmod(0o755)
        self.environment['ANDROID_HOME'] = str(sdk.parent)
        (self.avd / 'hardware-qemu.ini').write_text('hw.mainKeys=no\nactual-emulator-generated-file=yes\n')
        marker = 'test "$task_glass_booted" = true\n'
        self.assertEqual(self.setup.count(marker), 1)
        tail = self.setup.split(marker, 1)[1]
        # This fixture owns the original hardware/getprop/window observations.
        # The following real HOME preparation runs in profile_ui_device_preparation_test.
        next_phase = 'python3 tools/gecko/prepare_ui_device.py '
        self.assertEqual(tail.count(next_phase), 1)
        tail, preparation = tail.split(next_phase, 1)
        self.assertNotIn('\n', preparation.strip())
        self.assertIn('set -euo pipefail', self.setup.splitlines()[0])
        return subprocess.run(['bash', '-c', 'set -euo pipefail\n' + tail], cwd=self.directory,
                              env=self.environment, capture_output=True, text=True)

    def test_post_boot_retains_actual_hardware_properties_and_window_observation(self):
        result = self.post_boot()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual((self.evidence / 'avd-hardware-qemu.txt').read_bytes(),
                         (self.avd / 'hardware-qemu.ini').read_bytes())
        self.assertEqual((self.evidence / 'device-getprop.txt').read_text(), '[qemu.hw.mainkeys]: [0]\n')
        self.assertEqual((self.evidence / 'device-window-displays.txt').read_text(), 'controlled window dump\n')
        self.assertIn('[qemu.hw.mainkeys]: [0]', result.stdout)
        upload = next(step for step in self.job['steps']
                      if step.get('name') == 'Upload glass acceptance cases, recordings and raw diagnostics')
        self.assertEqual(upload['if'], 'always()')
        self.assertIn('work/glass-navigation/**/*.txt', upload['with']['path'].splitlines())

    def test_failed_device_property_read_does_not_pass_preparation(self):
        result = self.post_boot(fail=True)
        self.assertNotEqual(result.returncode, 0)
        self.assertFalse((self.evidence / 'device-window-displays.txt').exists())


if __name__ == '__main__':
    unittest.main()
