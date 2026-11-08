"""Strict canonical preparation order and its exact historical workflow input."""
import ast
import copy
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import unittest
from unittest.mock import patch

import yaml
import browser_acceptance_workflow_test as browser
import gradle_transport_source_compatibility as transport
import ui_checkpoint_source_compatibility as checkpoint

ROOT = Path(__file__).resolve().parents[1]
STEP_NAME = 'Prepare fixed public history for profile host checks'
STEP_RUN = ('set -euo pipefail\n'
            'python3 tools/gecko/prepare_profile_host_prerequisites.py --source-commit "$GITHUB_SHA" '
            '--output work/gecko-integration/profile-host-prerequisites.json\n')


class CanonicalProfilePrerequisitesTests(unittest.TestCase):
    def test_two_hunks_restore_the_complete_actual_public_git_blob(self):
        value = transport.canonical_profile_manifest()
        environment = dict(os.environ, GIT_NO_LAZY_FETCH='1')
        def git(*parts):
            return subprocess.check_output(['git', '--no-replace-objects', *parts], cwd=ROOT, env=environment)
        self.assertEqual(git('rev-parse', value['baseCommit'] + '^{tree}').decode().strip(), value['baseTree'])
        self.assertEqual(git('rev-parse', value['baseCommit'] + ':' + transport.CANONICAL).decode().strip(), value['previousBlob'])
        previous = git('show', value['baseCommit'] + ':' + transport.CANONICAL)
        raw = (ROOT / transport.CANONICAL).read_bytes()
        self.assertEqual((len(raw), transport.sha(raw)), (92665, transport.CANONICAL_PROFILE_CURRENT_SHA256))
        self.assertEqual(transport.source_input(raw, transport.CANONICAL), previous)
        self.assertEqual(transport.sha(previous), checkpoint.WORKFLOW_CURRENT_SHA256)
        forward = previous
        for delta in value['currentRow']['deltas']:
            before, after = delta['previous'].encode(), delta['current'].encode()
            self.assertEqual(forward.count(before), 1)
            forward = forward.replace(before, after, 1)
        self.assertEqual(forward, raw)
        midpoint = previous.replace(value['currentRow']['deltas'][0]['previous'].encode(),
                                    value['currentRow']['deltas'][0]['current'].encode(), 1)
        self.assertEqual((len(midpoint), transport.sha(midpoint)), (92383, '2629831d0afd9176b0ce4d92a4c03117b66a3f20c4912885b4c31b391160f83e'))
        with self.assertRaises(AssertionError):transport.source_input(midpoint, transport.CANONICAL)
        with self.assertRaises(AssertionError):checkpoint.checkpoint_workflow_input(midpoint)
        self.assertIs(transport.canonical_history_input(midpoint), midpoint)
        old = json.loads(transport.FIXTURE.read_bytes())
        current = transport.manifest()
        self.assertEqual(transport.sha(transport.FIXTURE.read_bytes()), '0e34228b10f4ecb511c584f5fc071e06ffd87e6981caddd80b0510897fbcc793')
        self.assertEqual(current['files'][transport.CANONICAL], value['currentRow'])
        self.assertEqual(len(current['files'][transport.CANONICAL]['deltas']), 2)
        for path in old['files']:
            if path != transport.CANONICAL:self.assertEqual(current['files'][path], old['files'][path])
        self.assertEqual(current['toolchainStep'], old['toolchainStep'])

    def test_actual_required_cli_precedes_profile_checks_without_changing_old_steps(self):
        raw = (ROOT / transport.CANONICAL).read_bytes()
        actual = yaml.safe_load(raw)
        snapshot = copy.deepcopy(actual)
        steps = actual['jobs']['build']['steps']
        at = [i for i, step in enumerate(steps) if step.get('name') == STEP_NAME]
        self.assertEqual(len(at), 1)
        self.assertEqual(steps[at[0]], dict(name=STEP_NAME, shell='bash', run=STEP_RUN))
        self.assertEqual(steps[at[0] + 1]['name'], 'Verify versioned environment models and authoritative intents')
        self.assertIn('tools/gecko/run_profile_host_checks.py', steps[at[0] + 1]['run'])
        self.assertNotIn('git fetch', STEP_RUN)
        restored = copy.deepcopy(actual)
        restored['jobs']['build']['steps'].pop(at[0])
        restored['jobs']['build']['steps'] = [transport.historical_toolchain_step(step)
                                             for step in restored['jobs']['build']['steps']]
        before = yaml.safe_load(transport.source_input(raw, transport.CANONICAL))
        self.assertEqual(restored, before)
        self.assertEqual(len(actual['jobs']), len(before['jobs']))
        self.assertEqual(set(actual['jobs']), set(before['jobs']))
        browser.BrowserWorkflowTests.setUpClass()
        self.assertEqual(browser.BrowserWorkflowTests.new, actual)
        browser.BrowserWorkflowTests('test_original_checks_retained_in_order').test_original_checks_retained_in_order()
        self.assertEqual(actual, snapshot)
        self.assertEqual((ROOT / transport.CANONICAL).read_bytes(), raw)

    def test_actual_context_cli_source_output_order_and_old_budget_drift_reject(self):
        raw = (ROOT / transport.CANONICAL).read_bytes()
        value = transport.canonical_profile_manifest()
        candidates = [raw + b' ', raw[:1024], b'unknown complete canonical workflow']
        for delta in value['currentRow']['deltas']:
            chunk = delta['current'].encode()
            self.assertEqual(raw.count(chunk), 1)
            remaining = raw.replace(chunk, b'', 1)
            moved = remaining + chunk
            if moved == raw:moved = chunk + remaining
            candidates.extend((remaining, raw.replace(chunk, chunk * 2, 1),
                               raw.replace(chunk, chunk + b' ', 1), moved))
        stage = value['currentRow']['deltas'][1]['current'].encode()
        for before, after in (
            (b'--source-commit "$GITHUB_SHA"', b'--source-commit HEAD'),
            (b'prepare_profile_host_prerequisites.py', b'other_history_preparer.py'),
            (b'--output work/gecko-integration/profile-host-prerequisites.json', b'--output /tmp/unbound-history.json'),
            (b'        set -euo pipefail\n', b'        set +e\n'),
            (b'      shell: bash\n', b'      continue-on-error: true\n      shell: bash\n'),
            (b'--output work/gecko-integration/profile-host-prerequisites.json\n',
             b'--output work/gecko-integration/profile-host-prerequisites.json || true\n')):
            self.assertIn(before, stage)
            candidates.append(raw.replace(stage, stage.replace(before, after, 1), 1))
        for before, after in ((b'    timeout-minutes: 60\n', b'    timeout-minutes: 61\n'),
                              (b'https://api.github.com/repos/gradle/gradle-distributions/releases/assets/586068844',
                               b'https://api.github.com/repos/gradle/gradle-distributions/releases/assets/586068845')):
            self.assertEqual(raw.count(before), 1)
            candidates.append(raw.replace(before, after, 1))
        added = stage[:-len(value['currentRow']['deltas'][1]['previous'].encode())]
        moved = raw.replace(added, b'', 1)
        earlier = b'    - name: Run all new browser and carried conversation host regressions\n'
        self.assertEqual(moved.count(earlier), 1)
        candidates.append(moved.replace(earlier, added + earlier, 1))
        for candidate in candidates:
            self.assertNotEqual(candidate, raw)
            with self.subTest(sha256=transport.sha(candidate)):
                with self.assertRaises(AssertionError):transport.source_input(candidate, transport.CANONICAL)
                self.assertIs(transport.canonical_history_input(candidate), candidate)
                with self.assertRaises(AssertionError):checkpoint.checkpoint_workflow_input(candidate)
        self.assertEqual((ROOT / transport.CANONICAL).read_bytes(), raw)

    def test_existing_strict_preparer_signature_and_activity_guard_stay_separate(self):
        source = (ROOT / 'tools/gecko/prepare_profile_host_prerequisites.py').read_text()
        functions = {node.name: node for node in ast.parse(source).body if isinstance(node, ast.FunctionDef)}
        for name in ('prepare_history', 'prepare_additional_history', 'prepare_ui_history'):
            arguments = functions[name].args
            self.assertEqual([arg.arg for arg in arguments.args], ['root'])
            self.assertEqual([arg.arg for arg in arguments.kwonlyargs], ['source_commit', 'environment'])
            self.assertIsNone(arguments.kw_defaults[0])
            self.assertIsNone(arguments.kw_defaults[1].value)
            self.assertIsNone(arguments.vararg)
            self.assertIsNone(arguments.kwarg)
        spec = importlib.util.spec_from_file_location('canonical_unprojected_activity_guard',
            ROOT / 'tests/gecko-ui-download-observer-host/run.py')
        host = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(host)
        raw = host.ACTIVITY.read_bytes()
        with patch.object(host._history_input._gradle_transport_input, 'canonical_profile_manifest',
                          side_effect=AssertionError('Activity guard read workflow-only metadata')):
            historical = host._history_input.navigation_source_input(raw, 'tests/gecko/UiVisualIntegrationActivity.java')
        self.assertEqual(transport.sha(historical), host.PINS['activity'])
        self.assertEqual(host.ACTIVITY.read_bytes(), raw)
        for candidate in (None, raw.decode(), bytearray(raw), memoryview(raw), b''):
            with self.assertRaises(AssertionError):transport.source_input(candidate, transport.CANONICAL)
        canonical = (ROOT / transport.CANONICAL).read_bytes()
        for path in (None, Path(transport.CANONICAL), '/' + transport.CANONICAL, '../' + transport.CANONICAL):
            with self.assertRaises(AssertionError):transport.source_input(canonical, path)


if __name__ == '__main__':
    unittest.main(verbosity=2)
