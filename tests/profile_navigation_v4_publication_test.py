"""Exercise actual publication guards with synthetic navigation parser controls.

These fixtures test rejection and staging behavior only. They are never written
as release evidence or presented as real Android execution.
"""
import ast
import copy
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import textwrap
import unittest

ROOT = Path(__file__).resolve().parents[1]
PUBLISHER = ROOT / 'tools/publish-gecko-release.py'
WORKFLOW = ROOT / '.github/workflows/publish-gecko-release.yml'
SOURCE = 'a' * 40
READERS = ('compact_chrome_layout_v4', 'chrome_collapse_contract_v4',
           'workspace_navigation_contract_v4')
sys.path.insert(0, str(ROOT / 'tools'))


def trees():
    workflow = WORKFLOW.read_text().split("python3 - <<'PY'\n", 1)[1].split('\n          PY', 1)[0]
    return ast.parse(PUBLISHER.read_text()), ast.parse(textwrap.dedent(workflow))


def version_guard(tree, workflow=False):
    expected = "m['versionCode'] >= 108" if workflow else 'version_code >= 108'
    blocks = [node for node in ast.walk(tree) if isinstance(node, ast.If)
              and ast.unparse(node.test) == expected
              and any(isinstance(child, ast.Assign)
                      and any(isinstance(target, ast.Name) and target.id == 'expected_navigation'
                              for target in child.targets) for child in node.body)]
    assert len(blocks) == 1
    body = [node for node in blocks[0].body
            if any(isinstance(value, ast.Name) and value.id == 'expected_navigation'
                   for value in ast.walk(node))]
    assert len(body) == (2 if workflow else 3)
    guard = ast.If(test=blocks[0].test, body=body, orelse=[])
    return compile(ast.fix_missing_locations(ast.Module(body=[guard], type_ignores=[])),
                   'actual-publication-navigation-guard', 'exec')


def parser_report():
    from profile_navigation_v4_test import case
    return dict(status='passed', sourceCommit=SOURCE, actualAndroidExecution=True,
                cases=[case(width, scale) for width, scale in ((360, 1), (412, 1), (360, 2))])


class NavigationPublicationV4Tests(unittest.TestCase):
    def test_current_apk_cannot_use_stale_or_mixed_navigation_evidence(self):
        for workflow, tree in enumerate(trees()):
            guard = version_guard(tree, workflow=bool(workflow))
            for version, contract in ((108, 3), (109, 4), (110, 4)):
                accepted = dict(cases=[dict(navigationContract=contract) for _ in range(3)],
                                autoCollapse=dict(navigationContract=contract))
                scope = dict(version_code=version, m={'versionCode': version}, chrome=accepted)
                with self.subTest(workflow=bool(workflow), version=version):
                    exec(guard, scope)
                    for mutation in ('old-case', 'old-collapse'):
                        rejected = copy.deepcopy(accepted)
                        if mutation == 'old-case':
                            rejected['cases'][1]['navigationContract'] = 2 if contract == 3 else 3
                        else:
                            rejected['autoCollapse']['navigationContract'] = 2 if contract == 3 else 3
                        with self.subTest(mutation=mutation), self.assertRaises(AssertionError):
                            exec(guard, dict(scope, chrome=rejected))

    def test_actual_touch_gate_checks_all_new_cases(self):
        from profile_release_navigation_v2_test import load_actual_gate
        verify = load_actual_gate()
        report = parser_report()
        self.assertTrue(verify(report, SOURCE))
        for mutation in ('wrong-source', 'mixed-contract', 'false-execution'):
            rejected = copy.deepcopy(report)
            if mutation == 'wrong-source':
                rejected['sourceCommit'] = 'b' * 40
            elif mutation == 'mixed-contract':
                rejected['cases'][1]['navigationContract'] = 3
            else:
                rejected['actualAndroidExecution'] = False
            with self.subTest(mutation=mutation), self.assertRaises((AssertionError, ValueError)):
                verify(rejected, SOURCE)

    def test_actual_stage_contains_independent_current_readers(self):
        publisher, _ = trees()
        conditions = {'version_code >= 43', 'roadmap_release', 'template_release', 'version_code >= 46'}
        copies = [node for node in publisher.body if isinstance(node, ast.If)
                  and ast.unparse(node.test) in conditions
                  and any(isinstance(value, ast.Call) and ast.unparse(value.func) == 'shutil.copy2'
                          for value in ast.walk(node))]
        self.assertEqual(len(copies), 4)
        with tempfile.TemporaryDirectory() as raw:
            stage = Path(raw)
            (stage / 'tools').mkdir()
            exec(compile(ast.Module(body=copies, type_ignores=[]), str(PUBLISHER), 'exec'),
                 dict(root=ROOT, stage=stage, shutil=shutil, version_code=109,
                      roadmap_release=True, template_release=True))
            for name in READERS:
                self.assertEqual((stage / 'tools/gecko' / (name + '.py')).read_bytes(),
                                 (ROOT / 'tools/gecko' / (name + '.py')).read_bytes())
            script = '''
import importlib, json, pathlib, sys
stage = pathlib.Path.cwd().resolve()
sys.path[:0] = [str(stage), str(stage/'tools'), str(stage/'tools/gecko')]
report = json.loads(sys.stdin.read())
names = ('compact_chrome_layout_v4', 'chrome_collapse_contract_v4', 'workspace_navigation_contract_v4')
for prefix in ('tools.gecko.', 'gecko.', ''):
    for name in names:
        module = importlib.import_module(prefix + name)
        assert pathlib.Path(module.__file__).resolve().is_relative_to(stage)
        if name == 'compact_chrome_layout_v4':
            for case in report['cases']:
                module.verify_case(case, require_browser_chrome=True)
print('Current navigation readers validated inside the real empty publication stage.')
'''
            result = subprocess.run([sys.executable, '-I', '-c', script], cwd=stage,
                                    input=json.dumps(parser_report()), text=True,
                                    capture_output=True, timeout=30)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)


if __name__ == '__main__':
    unittest.main()
