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
CURRENT_READERS = ('browser_observation_contract_v2', 'browser_header_contract_v5',
                   'compact_chrome_layout_v5', 'workspace_browser_header_v5')
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


class BrowserPublicationV110Tests(unittest.TestCase):
    """Real staging/import/Git gates with declared parser-only evidence controls."""

    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix='browser-110-release-stage-')
        self.addCleanup(temporary.cleanup)
        self.stage = Path(temporary.name)
        publisher, self.workflow = trees()
        conditions = {'version_code >= 43', 'roadmap_release', 'template_release', 'version_code >= 46'}
        copies = [node for node in publisher.body if isinstance(node, ast.If)
                  and ast.unparse(node.test) in conditions
                  and any(isinstance(value, ast.Call) and ast.unparse(value.func) == 'shutil.copy2'
                          for value in ast.walk(node))]
        self.assertEqual(len(copies), 4)
        (self.stage/'tools').mkdir()
        exec(compile(ast.Module(body=copies, type_ignores=[]), str(PUBLISHER), 'exec'),
             dict(root=ROOT, stage=self.stage, shutil=shutil, version_code=110,
                  roadmap_release=True, template_release=True))

    def probe(self, program, *, source=SOURCE, version=110, payload=None):
        script = '''
import ast, json, pathlib, subprocess, sys, types
stage = pathlib.Path.cwd().resolve()
sys.path[:0] = [str(stage), str(stage/'tools'), str(stage/'tools/gecko')]
data = json.load(sys.stdin)
def record(name):
    path = stage/name
    return json.loads(path.read_text()) if path.is_file() else {}
scope = dict(pathlib=pathlib, subprocess=subprocess, json=json, sys=sys, stage=stage,
    m=dict(versionCode=data['version'], sourceCommit=data['source'], releaseToolsCommit='f'*40),
    version_code=data['version'], tools_commit='f'*40,
    args=types.SimpleNamespace(evidence=stage, source=data['source']),
    quiet=record('quiet-notification-results.json'), chrome=record('compact-chrome-results.json'),
    visual=record('ui-visual-results.json'), payload=data['payload'])
exec(compile(ast.parse(data['program']), 'actual-publication-gates', 'exec'), scope)
'''
        return subprocess.run([sys.executable, '-I', '-c', script], cwd=self.stage,
                              input=json.dumps(dict(program=program, source=source, version=version,
                                                    payload=payload)), text=True,
                              capture_output=True, timeout=30)

    def source_guard(self):
        blocks = [node for node in self.workflow.body if isinstance(node, ast.If)
                  and ast.unparse(node.test) == "m['versionCode'] >= 110"
                  and any(isinstance(value, ast.Call) and ast.unparse(value.func) == 'subprocess.check_output'
                          for value in ast.walk(node))]
        self.assertEqual(len(blocks), 1)
        return ast.unparse(ast.Module(body=blocks, type_ignores=[]))

    def source_repository(self):
        def git(*args):
            return subprocess.check_output(['git', '-C', str(self.stage), *args], text=True).strip()
        git('init', '-q')
        git('add', 'tools/gecko')
        git('-c', 'user.name=Reader parser control', '-c', 'user.email=reader@example.invalid',
            '-c', 'commit.gpgsign=false', 'commit', '-qm', 'Synthetic immutable reader source')
        return git('rev-parse', 'HEAD')

    def test_actual_stage_imports_and_uses_all_four_current_readers(self):
        from profile_browser_header_v5_test import fixture
        from profile_browser_header_evidence_v5_test import current_case, native, browser_xml, NONCE, PACKAGE
        from profile_browser_observation_v2_test import checked_report, notification_report
        for name in CURRENT_READERS:
            self.assertEqual((self.stage/'tools/gecko'/(name+'.py')).read_bytes(),
                             (ROOT/'tools/gecko'/(name+'.py')).read_bytes())
        program = '''
import importlib
for prefix in ('tools.gecko.', 'gecko.', ''):
    for name in payload['names']:
        module = importlib.import_module(prefix+name)
        assert pathlib.Path(module.__file__).resolve().is_relative_to(stage)
        if name == 'browser_observation_contract_v2':
            module.verify_browser_observation(payload['observation'])
            module.verify_browser_notifications(payload['notification'])
        elif name == 'browser_header_contract_v5':
            module.verify_header(payload['header'])
        elif name == 'compact_chrome_layout_v5':
            for case in payload['cases']:
                module.verify_case(case, require_browser_chrome=True)
        else:
            native = module.native_observation(json.dumps(payload['native']), payload['nonce'], m['sourceCommit'])
            module.conversation_header(payload['xml'], payload['package'], 360, 640, 1,
                'Controlled environment', browser=True, native=native)
'''
        result = self.probe(program, payload=dict(names=CURRENT_READERS, observation=checked_report(),
            notification=notification_report(), header=fixture(), native=native(), nonce=NONCE,
            package=PACKAGE, xml=browser_xml(),
            cases=[current_case(width, scale) for width, scale in ((360,1),(412,1),(360,2))]))
        self.assertEqual(result.returncode, 0, result.stdout+result.stderr)

    def test_missing_current_reader_cannot_import_from_source_checkout(self):
        for name in CURRENT_READERS:
            path = self.stage/'tools/gecko'/(name+'.py'); original = path.read_bytes()
            try:
                path.unlink()
                with self.subTest(reader=name):
                    result = self.probe('import importlib\nimportlib.import_module("tools.gecko.'+name+'")')
                    self.assertNotEqual(result.returncode, 0, result.stdout)
                    self.assertIn('ModuleNotFoundError', result.stderr)
            finally:
                path.write_bytes(original)

    def test_workflow_binds_each_new_reader_to_immutable_tested_source_bytes(self):
        source = self.source_repository(); guard = self.source_guard()
        result = self.probe(guard, source=source)
        self.assertEqual(result.returncode, 0, result.stdout+result.stderr)
        for name in CURRENT_READERS:
            path = self.stage/'tools/gecko'/(name+'.py'); original = path.read_bytes()
            for mutation in ('missing', 'modified'):
                try:
                    if mutation == 'missing': path.unlink()
                    else: path.write_bytes(original+b'\n# Changed after source acceptance\n')
                    with self.subTest(reader=name, mutation=mutation):
                        result = self.probe(guard, source=source)
                        self.assertNotEqual(result.returncode, 0, result.stdout)
                        self.assertIn('FileNotFoundError' if mutation == 'missing' else 'AssertionError', result.stderr)
                        historical = self.probe(guard, source=source, version=109)
                        self.assertEqual(historical.returncode, 0, historical.stdout+historical.stderr)
                finally:
                    path.write_bytes(original)

    def current_records(self):
        from profile_browser_observation_v2_test import notification_report
        quiet = notification_report(); quiet['sourceCommit'] = SOURCE
        return {'quiet-notification-results.json': quiet,
                'compact-chrome-results.json': dict(cases=[dict(headerContract=5) for _ in range(3)]),
                'ui-visual-results.json': dict(screenshots=[dict(scene='chat', headerContract=5),
                                                          dict(scene='chat', headerContract=5), dict(scene='settings')]),
                'gecko-performance-results.json': dict(browserObservationContract=2),
                'interaction-host-results.json': dict(contract='browser-result-removal-v1')}

    def write_records(self, records):
        for name, value in records.items():
            (self.stage/name).write_text(json.dumps(value))

    def schema_guards(self, tree, workflow):
        expected = "m['versionCode'] >= 110" if workflow else 'version_code >= 110'
        fields = {'headerContract', 'notificationContract', 'browserObservationContract', 'browser-result-removal-v1'}
        blocks = [node for node in ast.walk(tree) if isinstance(node, ast.If)
                  and ast.unparse(node.test) == expected
                  and any(isinstance(value, ast.Constant) and isinstance(value.value, str)
                          and value.value in fields for value in ast.walk(node))]
        self.assertEqual(len(blocks), 3)
        return ast.unparse(ast.Module(body=blocks, type_ignores=[]))

    def test_publisher_and_workflow_reject_every_current_contract_downgrade(self):
        changes = (('quiet-notification-results.json', ('notificationContract',), 1),
                   ('compact-chrome-results.json', ('cases',1,'headerContract'), 4),
                   ('ui-visual-results.json', ('screenshots',1,'headerContract'), 4),
                   ('gecko-performance-results.json', ('browserObservationContract',), 1),
                   ('interaction-host-results.json', ('contract',), 'historical-result-observation'))
        for workflow, tree in enumerate(trees()):
            guard = self.schema_guards(tree, bool(workflow))
            self.write_records(self.current_records())
            result = self.probe(guard)
            self.assertEqual(result.returncode, 0, result.stdout+result.stderr)
            for filename, path, old_value in changes:
                for mutation in ('missing', 'old'):
                    records = self.current_records(); value = records[filename]
                    for key in path[:-1]: value = value[key]
                    if mutation == 'missing': value.pop(path[-1])
                    else: value[path[-1]] = old_value
                    self.write_records(records)
                    with self.subTest(workflow=bool(workflow), file=filename, mutation=mutation):
                        result = self.probe(guard)
                        self.assertNotEqual(result.returncode, 0, result.stdout)
                        self.assertIn('AssertionError', result.stderr)
                        historical = self.probe(guard, version=109)
                        self.assertEqual(historical.returncode, 0, historical.stdout+historical.stderr)

    def test_workflow_requires_current_notification_source_and_real_retirement_checks(self):
        guard = self.schema_guards(self.workflow, True)
        for mutation in ('wrong-source', 'old-service-live'):
            records = self.current_records(); quiet = records['quiet-notification-results.json']
            if mutation == 'wrong-source': quiet['sourceCommit'] = 'b'*40
            else: quiet['replyRetirementEvidence']['serviceStopped'] = False
            self.write_records(records)
            with self.subTest(mutation=mutation):
                result = self.probe(guard)
                self.assertNotEqual(result.returncode, 0, result.stdout)
                self.assertIn('AssertionError', result.stderr)


if __name__ == '__main__':
    unittest.main()
