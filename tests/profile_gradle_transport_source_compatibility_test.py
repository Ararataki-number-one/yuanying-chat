"""Fixed workflow history; actual current browser step controls remain current."""
import copy
import os
from pathlib import Path
import subprocess
import unittest
from unittest.mock import patch

import yaml

import browser_acceptance_workflow_test as browser_workflow
import gradle_transport_source_compatibility as transport
import ui_checkpoint_source_compatibility as checkpoint
from environment_workspace_workflow_source_compatibility import PATH as ENVIRONMENT_WORKFLOW_PATH, source_input as environment_workflow_source_input
from cellular_workflow_source_compatibility import historical_input as cellular_workflow_source_input
from historical_source_inputs import historical_bytes

ROOT = Path(__file__).resolve().parents[1]
ASSET = b'https://api.github.com/repos/gradle/gradle-distributions/releases/assets/586068844'
CHECKSUM = b'bafd5ce9cfaea0fbccfdc8439a1ac42fbd4cd9c89dc9a988228d8a2639a58e6c'


class GradleTransportSourceCompatibilityTests(unittest.TestCase):
    def test_three_current_whole_images_restore_actual_git_and_every_original_step(self):
        value = transport.manifest()
        environment = dict(os.environ, GIT_NO_LAZY_FETCH='1')
        tree = subprocess.check_output(['git', '--no-replace-objects', 'rev-parse', value['baseCommit'] + '^{tree}'], cwd=ROOT, env=environment).decode().strip()
        self.assertEqual(tree, value['baseTree'])
        for path, row in value['files'].items():
            raw = environment_workflow_source_input(historical_bytes(path), path) if path == ENVIRONMENT_WORKFLOW_PATH else historical_bytes(path)
            raw = cellular_workflow_source_input(raw, path)
            before = subprocess.check_output(['git', '--no-replace-objects', 'show', value['baseCommit'] + ':' + path], cwd=ROOT, env=environment)
            self.assertEqual(transport.source_input(raw, path), before)
            delta = row['deltas'][0]
            self.assertEqual(before.count(delta['previous'].encode()), 1)
            self.assertEqual(before.replace(delta['previous'].encode(), delta['current'].encode(), 1), raw)
            self.assertEqual(raw.count(ASSET), 1)
            self.assertEqual(raw.count(b'151611662'), 1)
            self.assertEqual(raw.count(CHECKSUM), 1)
            # Equality after the sole inverse includes every original step,
            # SDK input, matrix and budget, not only selected required fields.
            self.assertEqual(yaml.safe_load(transport.source_input(raw, path)), yaml.safe_load(before))

    def test_fixed_asset_size_checksum_and_unknown_missing_moved_hunks_fail_closed(self):
        for path, row in transport.manifest()['files'].items():
            raw = environment_workflow_source_input(historical_bytes(path), path) if path == ENVIRONMENT_WORKFLOW_PATH else historical_bytes(path)
            raw = cellular_workflow_source_input(raw, path)
            current = row['deltas'][0]['current'].encode()
            remaining = raw.replace(current, b'', 1)
            changes = [raw + b'\n', raw[:1024], remaining,
                       raw.replace(current, current * 2, 1), current + remaining,
                       raw.replace(ASSET, ASSET[:-1] + b'5', 1),
                       raw.replace(b'151611662', b'151611663', 1),
                       raw.replace(CHECKSUM, b'0' * 64, 1),
                       raw.replace(b"-H 'Accept: application/octet-stream' ", b'', 1),
                       raw.replace(b'--max-time 240', b'--max-time 241', 1),
                       raw.replace(b'https://services.gradle.org/', b'https://unreviewed.invalid/', 1),
                       raw.replace(b'timeout-minutes:', b'unreviewed-timeout-minutes:', 1)]
            fallback = next(line for line in raw.splitlines(keepends=True) if ASSET in line)
            checksum = next(line for line in raw.splitlines(keepends=True) if CHECKSUM in line)
            changes.extend((raw.replace(fallback, b'', 1), raw.replace(checksum, b'', 1)))
            for candidate in changes:
                self.assertNotEqual(candidate, raw)
                with self.subTest(path=path, sha256=transport.sha(candidate)), self.assertRaises(AssertionError):
                    transport.source_input(candidate, path)
            with self.assertRaises(AssertionError):transport.source_input(transport.source_input(raw, path), path)

    def test_canonical_historical_oracle_runs_after_current_transport_is_verified(self):
        raw = historical_bytes(transport.CANONICAL)
        previous = transport.canonical_history_input(raw)
        self.assertEqual(transport.sha(previous), checkpoint.WORKFLOW_CURRENT_SHA256)
        self.assertEqual(transport.sha(checkpoint.checkpoint_workflow_input(raw)), checkpoint.WORKFLOW_PREVIOUS_SHA256)
        for candidate in (raw + b' ', raw[:64], raw.replace(ASSET, b'https://unreviewed.invalid/asset', 1),
                          raw.replace(CHECKSUM, b'0' * 64, 1)):
            self.assertEqual(transport.canonical_history_input(candidate), candidate)
            with self.assertRaises(AssertionError):checkpoint.checkpoint_workflow_input(candidate)
        self.assertEqual(historical_bytes(transport.CANONICAL), raw)
        for candidate in (None, raw.decode(), bytearray(raw), memoryview(raw), True, b''):
            with self.assertRaises(AssertionError):transport.source_input(candidate, transport.CANONICAL)
        for path in (None, Path(transport.CANONICAL), '/' + transport.CANONICAL, '../' + transport.CANONICAL):
            with self.assertRaises(AssertionError):transport.source_input(raw, path)

    def test_actual_step_guard_keeps_raw_yaml_and_rejects_transport_or_original_drift(self):
        cls = browser_workflow.BrowserWorkflowTests
        cls.setUpClass()
        raw = yaml.safe_load((ROOT / transport.CANONICAL).read_bytes())
        self.assertEqual(cls.new, raw)
        current = copy.deepcopy(cls.new)
        step = next(s for s in cls.new['jobs']['build']['steps'] if s.get('name') == 'Prepare locked toolchain')
        expected = next(s for s in cls.old['jobs']['build']['steps'] if s.get('name') == step['name'])
        restored = transport.historical_toolchain_step(step)
        self.assertIsNot(restored, step)
        self.assertEqual(restored, expected)
        self.assertEqual(cls.new, current)
        case = cls('test_original_checks_retained_in_order')
        case.test_original_checks_retained_in_order()
        for before, after in [(ASSET.decode(), ASSET.decode()[:-1] + '5'),
                              ('151611662', '151611663'), (CHECKSUM.decode(), '0' * 64),
                              ('unzip -q ', 'unzip -v '), ('keytool" -genkeypair', 'keytool" -list')]:
            changed = copy.deepcopy(current)
            selected = next(s for s in changed['jobs']['build']['steps'] if s.get('name') == step['name'])
            self.assertEqual(selected['run'].count(before), 1)
            selected['run'] = selected['run'].replace(before, after, 1)
            self.assertIs(transport.historical_toolchain_step(selected), selected)
            with patch.object(cls, 'new', changed), self.assertRaises(AssertionError):case.test_original_checks_retained_in_order()
        for change in ('step-field', 'budget', 'other-step'):
            changed = copy.deepcopy(current)
            if change == 'step-field':
                next(s for s in changed['jobs']['build']['steps'] if s.get('name') == step['name'])['continue-on-error'] = True
            elif change == 'budget':
                changed['jobs']['build']['timeout-minutes'] = 61
            else:
                changed['jobs']['build']['steps'][0]['uses'] += '-unreviewed'
            with patch.object(cls, 'new', changed), self.assertRaises(AssertionError):case.test_original_checks_retained_in_order()
        self.assertEqual(cls.new, current)
        self.assertEqual(cls.new, raw)


if __name__ == '__main__':
    unittest.main(verbosity=2)
