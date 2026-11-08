"""Current navigation workflow guards and retained transport input closure."""
import copy
import hashlib
import os
from pathlib import Path
import subprocess
import unittest

import glass_emulator_navigation_source_compatibility as navigation
import profile_gradle_transport_source_compatibility_test as retained

transport = retained.transport
ROOT = Path(__file__).resolve().parents[1]


class EmulatorNavigationHistoricalInputs(unittest.TestCase):
    def test_actual_public_baseline_and_reviewed_transport_compose_the_whole_current_workflow(self):
        fixture = navigation.manifest()
        row = transport.manifest()['files'][navigation.PATH]
        public = subprocess.check_output(['git', '--no-replace-objects', 'show',
            fixture['publicBaselineCommit'] + ':' + navigation.PATH], cwd=ROOT,
            env=dict(os.environ, GIT_NO_LAZY_FETCH='1'))
        self.assertEqual(navigation.sha(public), fixture['publicBaselineSha256'])
        delta = row['deltas'][0]
        self.assertEqual(public.count(delta['previous'].encode()), 1)
        prior = public.replace(delta['previous'].encode(), delta['current'].encode(), 1)
        self.assertEqual((len(prior), navigation.sha(prior)), (15629, navigation.PREVIOUS_SHA256))
        raw = (ROOT / navigation.PATH).read_bytes()
        self.assertEqual((len(raw), navigation.sha(raw)), (16509, navigation.CURRENT_SHA256))
        self.assertEqual(navigation.source_before(raw), prior)
        self.assertEqual(navigation.current_after_input(prior, navigation.PATH), raw)
        self.assertEqual(transport.source_input(raw, navigation.PATH), public)
        forward = prior
        for delta in fixture['deltas']:
            before, after = delta['previous'].encode(), delta['current'].encode()
            self.assertLessEqual(max(len(before), len(after)), 32768)
            self.assertEqual((len(before), navigation.sha(before)), (delta['previousBytes'], delta['previousSha256']))
            self.assertEqual((len(after), navigation.sha(after)), (delta['currentBytes'], delta['currentSha256']))
            self.assertEqual(forward.count(before), 1)
            forward = forward.replace(before, after, 1)
        self.assertEqual(forward, raw)
        self.assertEqual(hashlib.sha256(transport.FIXTURE.read_bytes()).hexdigest(),
            '0e34228b10f4ecb511c584f5fc071e06ffd87e6981caddd80b0510897fbcc793')

    def test_actual_navigation_hunks_and_every_unreviewed_workflow_byte_fail_closed(self):
        raw = (ROOT / navigation.PATH).read_bytes()
        variants = [raw + b' ', raw[:1000], b'unknown workflow']
        for delta in navigation.manifest()['deltas']:
            chunk = delta['current'].encode()
            self.assertEqual(raw.count(chunk), 1)
            remaining = raw.replace(chunk, b'', 1)
            variants.extend((remaining, raw.replace(chunk, chunk * 2, 1),
                raw.replace(chunk, chunk + b' ', 1), remaining + chunk))
        for before, after in (
            (b'-prop qemu.hw.mainkeys=0', b'-prop qemu.hw.mainkeys=1'),
            (b'-prop qemu.hw.mainkeys=0', b''),
            (b"'hw.mainKeys': 'no'", b"'hw.mainKeys': 'yes'"),
            (b'shell getprop qemu.hw.mainkeys', b'shell getprop unrelated'),
            (b'-memory 3072', b'-memory 4096'),
            (b'timeout-minutes: 20', b'timeout-minutes: 21'),
            (b"if not path.is_file() or any(item.is_symlink() for item in (path, *path.parents)):",
             b'if False:')):
            self.assertEqual(raw.count(before), 1)
            variants.append(raw.replace(before, after, 1))
        for candidate in variants:
            self.assertNotEqual(candidate, raw)
            self.assertIs(navigation.historical_input(candidate, navigation.PATH), candidate)
            with self.assertRaises(AssertionError):navigation.source_before(candidate)
            with self.assertRaises(AssertionError):transport.source_input(candidate, navigation.PATH)
        self.assertEqual((ROOT / navigation.PATH).read_bytes(), raw)

    def test_current_parsed_yaml_and_other_workflows_never_change(self):
        raw = (ROOT / navigation.PATH).read_bytes()
        actual = retained.yaml.safe_load(raw)
        frozen = copy.deepcopy(actual)
        restored = transport.source_input(raw, navigation.PATH)
        self.assertEqual(actual, frozen)
        self.assertNotEqual(restored, raw)
        original = retained.yaml.safe_load(restored)
        self.assertEqual(set(actual['jobs']), set(original['jobs']))
        for name, job in original['jobs'].items():
            self.assertEqual(actual['jobs'][name]['timeout-minutes'], job['timeout-minutes'])
            if 'strategy' in job:
                self.assertEqual(actual['jobs'][name]['strategy'], job['strategy'])
        for path in (None, Path(navigation.PATH), '../' + navigation.PATH,
                     '/' + navigation.PATH, transport.CANONICAL):
            self.assertIs(navigation.historical_input(raw, path), raw)
            self.assertIs(navigation.current_after_input(raw, path), raw)
        for candidate in (None, raw.decode(), bytearray(raw), memoryview(raw), b''):
            with self.assertRaises(AssertionError):navigation.source_before(candidate)
        self.assertEqual((ROOT / navigation.PATH).read_bytes(), raw)


if __name__ == '__main__':
    unittest.main()
