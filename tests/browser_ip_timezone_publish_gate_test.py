"""Additive publication control flow with explicit synthetic checker boundaries."""
import ast
import importlib.util
import json
from pathlib import Path
import sys
import tempfile
import types
import unittest
from unittest.mock import patch
import yaml

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tests'))
from browser_publish_gate_test import execute, workflow_tree

SOURCE = 'a' * 40
REPORT = 'gecko-ip-timezone-results.json'
KEY = 'geckoIpTimeZoneRegression'
CHECKER = 'tools/browser/check_gecko_ip_timezone_evidence.py'
COPY_TOOL = 'tools/browser/ip_timezone_publication.py'
SOURCE_ONLY = {CHECKER, 'tools/browser/run_gecko_ip_timezone_integration.py',
               'tools/browser/ip_timezone_fixture_server.py',
               'tools/browser/fingerprint_fixture_server.py',
               'tools/browser/newworker_fixture_server.py'}


class IpTimezonePublishGateTests(unittest.TestCase):
    def test_212_requires_the_extra_ip_proof_and_preserves_the_exact_reference_reader(self):
        spec = importlib.util.spec_from_file_location('ip_combined_gate', ROOT / 'tools/browser/check_evidence.py')
        gate = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(gate)
        calls = []
        modules = {}
        for name, function in (
            ('browser.check_fingerprint_evidence', 'verify_fingerprint_evidence'),
            ('browser.check_worker_policy_evidence', 'verify_worker_policy_evidence'),
            ('browser.check_gecko_environment_policy_evidence', 'verify_gecko_environment_policy_evidence'),
        ):
            module = types.ModuleType(name)
            setattr(module, function, lambda *args, **kwargs: {'scope': 'Explicit existing checker boundary'})
            modules[name] = module
        module = types.ModuleType('browser.check_gecko_ip_timezone_evidence')
        def verify(directory, source, expected, reader):
            calls.append((Path(directory), source, expected, reader))
            value = json.loads((Path(directory) / REPORT).read_text())
            if value != dict(sourceCommit=source, status='passed', syntheticBoundaryOnly=True):
                raise ValueError('Explicit IP checker boundary rejected source/status')
            return dict(sourceCommit=source, scope='Synthetic metadata boundary only')
        module.verify_gecko_ip_timezone_evidence = verify
        modules[module.__name__] = module
        reader = object()
        expected = dict(sourceCommit=SOURCE, sourceTree='b' * 40, apkSha256='c' * 64,
                        version='2.1.1', sdkBuildIdentity=dict(runId='19', runAttempt='2'))
        result = dict(buildIdentity={}, checks=[{}], provider=dict(package='synthetic', version='fixture'))
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary)
            (directory / 'browser-results.json').write_text(json.dumps(dict(expectedBuildIdentity={})))
            def device():
                (directory / 'device-results.json').write_text(json.dumps(dict(status='passed', sourceCommit=SOURCE,
                    actualAndroidExecution=True, syntheticBoundaryOnly=True, eventTransport=dict(buildIdentity=expected))))
            device()
            with patch.object(gate, 'validate_behavior', return_value=result), patch.object(gate, 'verify_installed'), patch.dict(sys.modules, modules):
                previous = gate.verify_browser_evidence(directory, SOURCE, reader=reader)
                self.assertNotIn(KEY, previous)
                self.assertEqual(calls, [])
                expected['version'] = '2.1.2'
                device()
                with self.assertRaises(FileNotFoundError):
                    gate.verify_browser_evidence(directory, SOURCE, reader=reader)
                for value in (dict(sourceCommit='d' * 40, status='passed', syntheticBoundaryOnly=True),
                              dict(sourceCommit=SOURCE, status='failed', syntheticBoundaryOnly=True)):
                    (directory / REPORT).write_text(json.dumps(value))
                    with self.assertRaises(ValueError):
                        gate.verify_browser_evidence(directory, SOURCE, reader=reader)
                (directory / REPORT).write_text(json.dumps(dict(sourceCommit=SOURCE, status='passed', syntheticBoundaryOnly=True)))
                checked = gate.verify_browser_evidence(directory, SOURCE, reader=reader)
                self.assertEqual(checked[KEY], dict(sourceCommit=SOURCE, scope='Synthetic metadata boundary only'))
                self.assertIn('workerPolicyRegression', checked)
                self.assertIn('geckoEnvironmentPolicyRegression', checked)
            self.assertTrue(calls)
            self.assertTrue(all(path == directory and source == SOURCE and reference == expected and actual_reader is reader
                                for path, source, reference, actual_reader in calls))

    def test_selected_source_checker_and_servers_are_not_mutable_release_tools(self):
        tool = ast.parse((ROOT / 'tools/publish-gecko-release.py').read_text())
        workflow = workflow_tree()
        for version in ('2.1.1', '2.1.2', '2.1.3', '3.0.0'):
            parts = tuple(map(int, version.split('.')))
            sets = []
            for tree, name, namespace in (
                (tool, 'release_tool_files', dict(version=version, browser_release=parts >= (2, 1, 0),
                    fingerprint_release=parts >= (2, 1, 1), worker_timezone_release=parts >= (2, 1, 2), cpu_release=parts >= (2, 1, 3))),
                (workflow, 'release_files', dict(m=dict(version=version))),
            ):
                nodes = [node for node in tree.body if isinstance(node, ast.Assign)
                         and any(isinstance(target, ast.Name) and target.id == name for target in node.targets)]
                nodes += [node for node in tree.body if isinstance(node, ast.If)
                          and any(isinstance(value, ast.Call) and ast.unparse(value.func) in (name + '.add', name + '.update')
                                  for value in ast.walk(node))]
                execute(nodes, namespace)
                sets.append(namespace[name])
            self.assertEqual(sets[0], sets[1])
            self.assertEqual(COPY_TOOL in sets[0], parts >= (2, 1, 2))
            self.assertTrue(SOURCE_ONLY.isdisjoint(sets[0]))
        source_checks = [node for node in workflow.body if isinstance(node, ast.If)
                         and 'IP timezone dependency differs from tested source' in ast.unparse(node)]
        self.assertEqual(len(source_checks), 1)
        names = {value.value for value in ast.walk(source_checks[0]) if isinstance(value, ast.Constant) and isinstance(value.value, str)}
        self.assertTrue(SOURCE_ONLY <= names)

    def test_stage_only_copies_all_raw_evidence_against_the_saved_original_regression(self):
        tree = ast.parse((ROOT / 'tools/publish-gecko-release.py').read_text())
        assignment = next(node for node in tree.body if isinstance(node, ast.Assign)
                          and any(isinstance(target, ast.Name) and target.id == 'ip_timezone_required' for target in node.targets))
        block = next(node for node in tree.body if isinstance(node, ast.If)
                     and any(isinstance(value, ast.ImportFrom) and value.module == 'browser.ip_timezone_publication' for value in ast.walk(node)))
        stage_exit = next(node for node in tree.body if isinstance(node, ast.If) and ast.unparse(node.test) == 'args.stage_only')
        self.assertLess(block.lineno, stage_exit.lineno)
        module = types.ModuleType('browser.ip_timezone_publication')
        calls = []
        saved = dict(sourceCommit=SOURCE, scope='Synthetic saved original regression')
        expected = dict(sourceCommit=SOURCE, scope='Synthetic original installed reference')
        files = [REPORT, *('gecko-ip-timezone-evidence/case-' + str(index) + '.json' for index in range(13))]
        def copy(directory, stage, source, reference, required_regression):
            self.assertIs(reference, expected)
            self.assertIs(required_regression, saved)
            self.assertEqual(source, SOURCE)
            calls.append('evidence')
            return dict(files=files, regression=saved)
        module.copy_gecko_ip_timezone_evidence = copy
        module.copy_gecko_ip_timezone_tools = lambda *args: calls.append('tools')
        namespace = dict(worker_timezone_release=True, manifest=dict(controlledBrowserRegression={KEY: saved}),
                         report=dict(eventTransport=dict(buildIdentity=expected)), root=Path('/synthetic/source'),
                         stage=Path('/synthetic/stage'), args=types.SimpleNamespace(evidence=Path('/synthetic/evidence'), source=SOURCE),
                         performance_files=['all-original-required-reports-retained'])
        with patch.dict(sys.modules, {module.__name__: module}):
            execute([assignment, block], namespace)
        self.assertEqual(calls, ['evidence', 'tools'])
        self.assertEqual(namespace['performance_files'], ['all-original-required-reports-retained', *files])
        execute([assignment, block], dict(worker_timezone_release=False, manifest={}))

    def test_ip_android_step_and_verified_raw_transfer_are_mandatory_without_new_jobs(self):
        current = yaml.safe_load((ROOT / '.github/workflows/browser-2_1-acceptance.yml').read_text())
        original = yaml.safe_load((ROOT / '.github/workflows/gecko-integration.yml').read_text())
        self.assertEqual(set(current['jobs']), set(original['jobs']) | {'browser'})
        self.assertIn('timeout-minutes',original['jobs']['build']);self.assertIn('timeout-minutes',current['jobs']['build'])
        self.assertIs(type(original['jobs']['build']['timeout-minutes']),int);self.assertEqual(original['jobs']['build']['timeout-minutes'],40)
        for name, previous in original['jobs'].items():
            for field in ('timeout-minutes', 'permissions', 'strategy', 'continue-on-error', 'if', 'needs'):
                expected = previous.get(field)
                if (name,field)==('build','timeout-minutes'):
                    self.assertIs(type(current['jobs'][name].get(field)),int);expected=60
                elif name == 'verify' and field == 'needs':
                    expected = expected + ['browser']
                self.assertEqual(current['jobs'][name].get(field), expected, (name, field))
        browser = current['jobs']['browser']
        self.assertEqual(browser['timeout-minutes'], 35)
        self.assertEqual(browser['needs'], 'build')
        self.assertEqual(browser['permissions'], {'contents': 'read', 'actions': 'read'})
        steps = browser['steps']
        wanted = 'Execute production exit-IP timezone defaults and route transitions'
        selected = [step for step in steps if step.get('name') == wanted]
        self.assertEqual(len(selected), 1)
        step = selected[0]
        self.assertEqual(step['if'], '${{ !cancelled() }}')
        self.assertNotIn('continue-on-error', step)
        self.assertIn('tools/browser/run_gecko_ip_timezone_integration.py', step['run'])
        for argument in ('--serial emulator-5554', '--apk app/build/outputs/apk/integration/app-x86_64-integration.apk',
                         '--source "$GITHUB_SHA"', '--output work/browser-acceptance'):
            self.assertIn(argument, step['run'])
        names = [step.get('name') for step in steps]
        self.assertLess(names.index('Execute production Gecko timezone and public Worker identity controls'), names.index(wanted))
        self.assertLess(names.index(wanted), names.index('Preserve bounded source-bound browser evidence'))
        upload = next(step for step in steps if step.get('name') == 'Preserve bounded source-bound browser evidence')
        self.assertIn('work/browser-acceptance/gecko-ip-timezone-evidence/*.json', upload['with']['path'].splitlines())
        verification = next(step for step in current['jobs']['verify']['steps']
                            if step.get('name') == 'Require the additional real Android browser release gate')
        body = verification['run']
        self.assertEqual(verification['env']['BROWSER_RESULT'], '${{ needs.browser.result }}')
        self.assertLess(body.index('test "$BROWSER_RESULT" = success'), body.index('tools/browser/ip_timezone_publication.py'))
        self.assertLess(body.index('tools/browser/ip_timezone_publication.py'), body.index('tools/browser/check_evidence.py'))
        self.assertIn('--device-reference work/gecko-integration/public/device-results.json', body)
        qualification = next(step for step in current['jobs']['verify']['steps']
                             if step.get('name') == 'Preserve the additional browser qualification receipt')
        paths = qualification['with']['path'].splitlines()
        self.assertIn('work/gecko-integration/public/gecko-ip-timezone-results.json', paths)
        self.assertIn('work/gecko-integration/public/gecko-ip-timezone-evidence/*.json', paths)


if __name__ == '__main__':
    unittest.main(verbosity=2)
