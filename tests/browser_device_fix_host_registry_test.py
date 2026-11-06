"""Preserve the original complete host cohort while admitting actual new controls."""
import hashlib
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
RUNNER = ROOT / 'tools/browser/run_host_checks.py'
BEFORE_SHA = '6a5e736f71da5391f64b4cb7737973c813cdfbe45ce71ac61963488ac67d8513'
ADDITION_SHA = 'ca7cb8b1311f8bd5be28be0b22a9d2bdc6906808173fcec0a51340aceebee0ed'
BEGIN = b'    # BEGIN_DEVICE_FIX_HOSTS\n'
END = b'    # END_DEVICE_FIX_HOSTS\n'


def declaration():
    raw = RUNNER.read_bytes()
    if raw.count(BEGIN) != 1 or raw.count(END) != 1:
        raise ValueError('One reviewed append block is required')
    begin = raw.index(BEGIN)
    end = raw.index(END, begin) + len(END)
    block = raw[begin:end]
    if hashlib.sha256(block).hexdigest() != ADDITION_SHA:
        raise ValueError('Reviewed append block changed')
    return raw, raw[:begin] + raw[end:], block


class DeviceFixHostRegistryTests(unittest.TestCase):
    def test_every_byte_of_the_original_169_suite_cohort_is_preserved(self):
        _, original, _ = declaration()
        self.assertEqual(len(original), 19230)
        self.assertEqual(hashlib.sha256(original).hexdigest(), BEFORE_SHA)
        self.assertIn(b'timeout=300', original)

    def test_twenty_one_real_controls_are_unconditional_unique_and_source_bound(self):
        before, _, block = declaration()
        namespace = {}
        # The exact hash-locked block only declares commands. This does not run
        # a host suite, compiler, browser or Android workload.
        exec(compile('def capture(out, java, desktop, android_json, add):\n' + block.decode(),
                     '<reviewed-host-declarations>', 'exec'), namespace)
        rows = []
        def add(name, script, arguments=(), report=None):
            rows.append((name, script, list(map(str, arguments)), report))
        namespace['capture'](Path('/declared-output'), ['--java-home', '/declared-jdk'],
                             Path('/declared-json.jar'), Path('/declared-android-json.jar'), add)
        self.assertEqual([row[0] for row in rows], [
            'gecko-environment-identity-scope',
            'gecko-cpu-ip-combo-transport-diagnostic',
            'ip-timezone-transport-diagnostics',
            'profile-fixture-root-source-history',
            'profile-fixture-root-desktop',
            'fixture-ui-hotpath-desktop',
            'network-internal-admission-desktop',
            'profile-fixture-root-android-json',
            'fixture-ui-hotpath-android-json',
            'network-internal-admission-android-json',
            'device-fix-host-registry',
            'tls-fixture-update-cause',
            'resource-recovery-desktop',
            'resource-recovery-android-json',
            'resource-startup-source-history',
            'ui-checkpoint-publication',
            'automatic-latency-desktop',
            'combo-native-admission-desktop',
            'automatic-latency-android-json',
            'combo-native-admission-android-json',
            'combo-native-admission-collector',
        ])
        self.assertEqual(len({row[0] for row in rows}), 21)
        for _, script, _, _ in rows:
            self.assertTrue((ROOT / script).is_file(), script)
        for row in rows[4:10]:
            self.assertEqual(row[2][:2], ['--java-home', '/declared-jdk'])
            self.assertIn('--json-jar', row[2])
            self.assertIn('--output', row[2])
            self.assertIsNotNone(row[3])
        for row in rows[12:14]:
            self.assertEqual(row[2][:2], ['--java-home', '/declared-jdk'])
            self.assertIn('--json-jar', row[2])
            self.assertIn('--output', row[2])
            self.assertIsNotNone(row[3])
        for row in rows[16:20]:
            self.assertEqual(row[2][:2], ['--java-home', '/declared-jdk'])
            self.assertIn('--json-jar', row[2])
            self.assertIn('--output', row[2])
            self.assertIsNotNone(row[3])
        self.assertEqual(before, RUNNER.read_bytes())


if __name__ == '__main__':
    unittest.main(verbosity=2)
