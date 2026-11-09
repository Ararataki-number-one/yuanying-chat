"""Host-only controls for the actual release touch gate and staged readers."""
import ast
import copy
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
PUBLISHER = ROOT / 'tools/publish-gecko-release.py'
SOURCE = 'a' * 40
V2_READERS = ('compact_chrome_layout_v2.py', 'chrome_collapse_contract_v2.py',
              'workspace_navigation_contract.py')
sys.path.insert(0, str(ROOT / 'tools'))
from profile_workspace_navigation_v2_test import complete_case


def publisher_tree():
    return ast.parse(PUBLISHER.read_text())


def load_actual_gate():
    functions = [node for node in publisher_tree().body if isinstance(node, ast.FunctionDef)
                 and node.name == 'verify_compact_touch_evidence']
    assert len(functions) == 1
    namespace = {}
    exec(compile(ast.Module(body=functions, type_ignores=[]), str(PUBLISHER), 'exec'), namespace)
    return namespace['verify_compact_touch_evidence']


def v2_report():
    # Parser fixtures only. These values are never saved as Android evidence.
    cases = []
    for width, scale in ((360, 1), (412, 1), (360, 2)):
        case = complete_case()
        case.update(viewport=width, fontScale=scale)
        case['layout'].update(viewportDp=width, fontScale=scale)
        case['layout']['toolbar'][2] = width * 3
        if scale == 2:
            case['layout']['texts'][0]['ellipsized'] = True
        cases.append(case)
    return dict(status='passed', actualAndroidExecution=True, sourceCommit=SOURCE, cases=cases)


def legacy_report(explicit=False):
    cases = [dict(readOnlyStatus=True, actualAndroidTaps=[dict(control=name)
             for name in ('drawer', 'environment', 'more')]) for _ in range(3)]
    if explicit:
        for case in cases:
            case['navigationContract'] = 1
    return dict(status='passed', actualAndroidExecution=True, sourceCommit=SOURCE, cases=cases)


def stage_actual_reader_blocks(stage):
    # Execute the unchanged real prerequisite-copy blocks as well as the compact
    # copy block. Do not populate a missing reader through a test-only fallback.
    conditions = {'version_code >= 43', 'roadmap_release', 'template_release',
                  'version_code >= 46'}
    blocks = [node for node in publisher_tree().body
              if isinstance(node, ast.If) and ast.unparse(node.test) in conditions
              and any(isinstance(call, ast.Call) and ast.unparse(call.func) == 'shutil.copy2'
                      for call in ast.walk(node))]
    assert len(blocks) == 4
    publisher_copies = [node for node in publisher_tree().body if isinstance(node, ast.Expr)
                       and isinstance(node.value, ast.Call)
                       and ast.unparse(node.value.func) == 'shutil.copy2'
                       and any(isinstance(value, ast.Constant)
                               and value.value == 'tools/publish-gecko-release.py'
                               for value in ast.walk(node))]
    assert len(publisher_copies) == 1
    (stage / 'tools').mkdir(parents=True)
    exec(compile(ast.Module(body=publisher_copies + blocks, type_ignores=[]),
                 str(PUBLISHER), 'exec'),
         dict(root=ROOT, stage=stage, shutil=shutil, version_code=106,
              roadmap_release=True, template_release=True))


ISOLATED_IMPORT = '''
import ast, importlib, json, pathlib, sys
stage = pathlib.Path.cwd().resolve()
report = json.loads(sys.stdin.read())
for entry in (stage, stage / 'tools', stage / 'tools/gecko'):
    sys.path.insert(0, str(entry))
names = ('check_performance_evidence', 'chrome_collapse_contract',
         'compact_chrome_layout_v2', 'chrome_collapse_contract_v2',
         'workspace_navigation_contract')
for prefix in ('tools.gecko.', 'gecko.', ''):
    for name in names:
        module = importlib.import_module(prefix + name)
        assert pathlib.Path(module.__file__).resolve().is_relative_to(stage)
        if name == 'compact_chrome_layout_v2':
            for case in report['cases']:
                module.verify_case(case)
for name, module in list(sys.modules.items()):
    if name.startswith(('tools.gecko', 'gecko.')) or name in names or name.startswith('selected_sdk_'):
        filename = getattr(module, '__file__', None)
        if filename:
            assert pathlib.Path(filename).resolve().is_relative_to(stage), (name, filename)
tree = ast.parse((stage / 'tools/publish-gecko-release.py').read_text())
function = next(node for node in tree.body if isinstance(node, ast.FunctionDef)
                and node.name == 'verify_compact_touch_evidence')
namespace = {}
exec(compile(ast.Module(body=[function], type_ignores=[]), 'actual-staged-gate', 'exec'), namespace)
assert namespace['verify_compact_touch_evidence'](report, report['sourceCommit']) is True
print('all actual reader imports resolved inside the empty staging directory')
'''


class ReleaseNavigationV2GateTests(unittest.TestCase):
    def setUp(self):
        self.verify = load_actual_gate()

    def test_original_three_tap_contract_is_preserved(self):
        for explicit in (False, True):
            with self.subTest(explicit=explicit):
                self.assertTrue(self.verify(legacy_report(explicit), SOURCE))

    def test_new_four_taps_and_independent_long_press_use_the_actual_reader(self):
        report = v2_report()
        self.assertTrue(self.verify(report, SOURCE))
        self.assertEqual([len(case['actualAndroidTaps']) for case in report['cases']], [4, 4, 4])
        self.assertTrue(all(case['actualAndroidLongPress']['durationMs'] == 700 for case in report['cases']))

    def test_legacy_missing_extra_or_nonreadonly_taps_are_rejected(self):
        for count in (2, 4):
            report = legacy_report()
            report['cases'][0]['actualAndroidTaps'] = [{} for _ in range(count)]
            with self.subTest(count=count), self.assertRaises(AssertionError):
                self.verify(report, SOURCE)
        report = legacy_report(); report['cases'][0]['readOnlyStatus'] = False
        with self.assertRaises(AssertionError):
            self.verify(report, SOURCE)

    def test_unknown_boolean_numeric_string_and_mixed_versions_are_rejected(self):
        for version in (None, False, True, 0, 3, 2.0, '2'):
            report = v2_report()
            for case in report['cases']:
                case['navigationContract'] = version
            with self.subTest(version=version), self.assertRaises(AssertionError):
                self.verify(report, SOURCE)
        report = v2_report(); report['cases'][1] = legacy_report()['cases'][1]
        with self.assertRaises(AssertionError):
            self.verify(report, SOURCE)
        report = v2_report()
        for case in report['cases']:
            del case['navigationContract']
        with self.assertRaises(AssertionError):
            self.verify(report, SOURCE)

    def test_v2_cannot_reuse_three_taps_or_forge_long_press_or_capsule_target(self):
        mutations = (
            lambda report: report['cases'][0]['actualAndroidTaps'].pop(1),
            lambda report: report['cases'][0].pop('actualAndroidLongPress'),
            lambda report: report['cases'][0].pop('layout'),
            lambda report: report['cases'][0].pop('statusObservation'),
            lambda report: report['cases'][0].pop('addressDialog'),
            lambda report: report['cases'][0].pop('environmentSheet'),
            lambda report: report['cases'][0].update(readOnlyStatus=False),
            lambda report: report['cases'][0]['actualAndroidTaps'][1].update(actualAndroidTap=False),
            lambda report: report['cases'][0]['addressDialog'].update(cancelled=False),
            lambda report: report['cases'][0]['actualAndroidLongPress'].update(durationMs=700.0),
            lambda report: report['cases'][0]['actualAndroidLongPress'].update(actionsAfter=1),
            lambda report: report['cases'][0]['actualAndroidLongPress'].update(point=[30, 30], bounds=[0, 0, 60, 60]),
            lambda report: report['cases'][0]['actualAndroidTaps'][1].update(point=[30, 30], bounds=[0, 0, 60, 60]),
            lambda report: report['cases'].__setitem__(1, copy.deepcopy(report['cases'][0])),
        )
        for index, mutate in enumerate(mutations):
            report = v2_report(); mutate(report)
            with self.subTest(mutation=index), self.assertRaises((AssertionError, KeyError)):
                self.verify(report, SOURCE)

    def test_v2_android_execution_requires_true_not_truthy_values(self):
        for value in (1, 'true', [True], None):
            report = v2_report(); report['actualAndroidExecution'] = value
            with self.subTest(value=value), self.assertRaises(AssertionError):
                self.verify(report, SOURCE)

    def test_same_source_three_cases_and_actual_android_requirements_remain(self):
        mutations = (
            lambda report: report.update(status='failed'),
            lambda report: report.update(actualAndroidExecution=False),
            lambda report: report.update(sourceCommit='b' * 40),
            lambda report: report['cases'].pop(),
            lambda report: report['cases'].append(copy.deepcopy(report['cases'][0])),
        )
        for maker in (legacy_report, v2_report):
            for index, mutate in enumerate(mutations):
                report = maker(); mutate(report)
                with self.subTest(contract=maker.__name__, mutation=index), self.assertRaises(AssertionError):
                    self.verify(report, SOURCE)

    def test_actual_publisher_calls_the_gate_before_the_complete_performance_check(self):
        tree = publisher_tree()
        touch = [node for node in ast.walk(tree) if isinstance(node, ast.Call)
                 and isinstance(node.func, ast.Name) and node.func.id == 'verify_compact_touch_evidence']
        performance = [node for node in ast.walk(tree) if isinstance(node, ast.Call)
                       and isinstance(node.func, ast.Name) and node.func.id == 'verify_performance_evidence']
        self.assertEqual(len(touch), 1); self.assertEqual(len(performance), 1)
        self.assertEqual([ast.unparse(arg) for arg in touch[0].args], ['chrome', 'args.source'])
        self.assertLess(touch[0].lineno, performance[0].lineno)


class StandaloneReleaseNavigationV2Tests(unittest.TestCase):
    def run_isolated(self, stage):
        environment = os.environ.copy()
        environment.pop('PYTHONPATH', None)
        return subprocess.run([sys.executable, '-I', '-c', ISOLATED_IMPORT], cwd=stage,
                              env=environment, input=json.dumps(v2_report()),
                              text=True, capture_output=True, timeout=30)

    def test_empty_stage_uses_actual_copy_blocks_and_imports_without_checkout_paths(self):
        with tempfile.TemporaryDirectory(prefix='release-v2-staging-') as folder:
            stage = Path(folder) / 'public'
            stage_actual_reader_blocks(stage)
            for name in V2_READERS:
                self.assertEqual((stage / 'tools/gecko' / name).read_bytes(),
                                 (ROOT / 'tools/gecko' / name).read_bytes())
            result = self.run_isolated(stage)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertIn('all actual reader imports resolved', result.stdout)

    def test_each_missing_v2_dependency_fails_without_repository_fallback(self):
        for name in V2_READERS:
            with self.subTest(reader=name), tempfile.TemporaryDirectory(prefix='release-v2-missing-') as folder:
                stage = Path(folder) / 'public'
                stage_actual_reader_blocks(stage)
                (stage / 'tools/gecko' / name).unlink()
                result = self.run_isolated(stage)
                self.assertNotEqual(result.returncode, 0, result.stdout)
                self.assertIn('ModuleNotFoundError', result.stderr)
                self.assertIn(name[:-3], result.stderr)


if __name__ == '__main__':
    unittest.main()
