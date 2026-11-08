"""Run only actual source-copy AST statements, never the publisher entrypoint.

The isolated import proves module closure, not a qualified stage, signed APK,
Chrome report, native transport or publication.
"""
import ast
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
PUBLISHER = ROOT / 'tools/publish-gecko-release.py'
ADDED_COPY = b"    if (root/'tools/gecko/chrome_collapse_contract_v2.py').is_file():shutil.copy2(root/'tools/gecko/chrome_collapse_contract_v2.py',stage/'tools/gecko/chrome_collapse_contract_v2.py')\n"
BEFORE_SHA256 = '9b41088840c79d2ae8bab5ca00ef357faabdaa53fe6c65499a8ea1c928a967d4'
IMPORT_PROBE = r'''
import importlib,json,pathlib,sys
root=pathlib.Path(sys.argv[1]).resolve()
sys.path.insert(0,str(root))
def no_external_actions(event,args):
    if event in ('subprocess.Popen','socket.connect','socket.bind'):
        raise AssertionError('Import probe attempted an external action: '+event)
sys.addaudithook(no_external_actions)
performance=importlib.import_module('tools.gecko.check_performance_evidence')
wrapper=importlib.import_module('tools.gecko.chrome_collapse_contract')
assert pathlib.Path(performance.__file__).resolve()==root/'tools/gecko/check_performance_evidence.py'
assert pathlib.Path(wrapper.__file__).resolve()==root/'tools/gecko/chrome_collapse_contract.py'
assert performance.verify_auto_collapse is wrapper.verify_auto_collapse
try:
    performance.verify_auto_collapse({'navigationContract':2,'status':'failed'},'a'*40,'b'*64)
except AssertionError as rejected:
    assert str(rejected)=='Chrome navigation v2: report version/source/status'
else:
    raise AssertionError('Invalid Chrome report was accepted')
v2=sys.modules['tools.gecko.chrome_collapse_contract_v2']
assert pathlib.Path(v2.__file__).resolve()==root/'tools/gecko/chrome_collapse_contract_v2.py'
print(json.dumps({'isolatedImportClosure':True,'invalidReportRejected':True,'stageQualified':False,'networkOrGitExecuted':False}))
'''


def actual_copy_nodes():
    source = PUBLISHER.read_text()
    tree = ast.parse(source)
    # These are the original copy blocks containing the existing dependencies.
    # Execute no argument parsing, source checks, stage deletion or publishers.
    markers = ('check_performance_evidence.py', 'check_profile_evidence.py',
               'check_template_evidence.py', 'check_chain_evidence.py')
    result = []
    for marker in markers:
        found = [n for n in tree.body if isinstance(n, ast.If)
                 and marker in ast.get_source_segment(source, n)]
        if len(found) != 1:
            raise AssertionError('Exactly one original copy block required: ' + marker)
        result.append(found[0])
    # Restrict the executable slice to source copies/directory creation/branches.
    for node in ast.walk(ast.Module(body=result, type_ignores=[])):
        if isinstance(node, ast.Call):
            allowed = (isinstance(node.func, ast.Attribute) and node.func.attr in ('mkdir', 'copy2', 'is_file'))
            if not allowed:
                raise AssertionError('Non-copy operation in stage-copy slice: ' + ast.dump(node.func))
        if isinstance(node, (ast.Import, ast.ImportFrom, ast.With, ast.While, ast.Try)):
            raise AssertionError('Unexpected operation in stage-copy slice')
    return result


def copy_tools(stage):
    (stage / 'tools').mkdir()
    namespace = dict(root=ROOT, stage=stage, version_code=106, roadmap_release=True,
                     template_release=True, shutil=shutil)
    exec(compile(ast.Module(body=actual_copy_nodes(), type_ignores=[]), str(PUBLISHER) + '::<copy-only>', 'exec'), namespace)


class ChromeStageModuleClosureTest(unittest.TestCase):
    def test_only_new_source_copy_added_old_publisher_gates_exactly_preserved(self):
        raw = PUBLISHER.read_bytes()
        self.assertEqual(raw.count(ADDED_COPY), 1)
        before = raw.replace(ADDED_COPY, b'', 1)
        self.assertEqual(hashlib.sha256(before).hexdigest(), BEFORE_SHA256)

    def test_actual_stage_copy_slice_closes_v2_import_and_keeps_source_bytes(self):
        with tempfile.TemporaryDirectory(prefix='chrome-stage-import-') as temp:
            stage = Path(temp)
            copy_tools(stage)
            paths = ('check_performance_evidence.py', 'ui_visual_contract.py',
                     'chrome_collapse_contract.py', 'chrome_collapse_contract_v2.py',
                     'integration_event_contract.py', 'profile_invocation_contract.py', 'sdk_identity_contract.py')
            for name in paths:
                self.assertEqual((stage / 'tools/gecko' / name).read_bytes(), (ROOT / 'tools/gecko' / name).read_bytes())
            ran = subprocess.run([sys.executable, '-I', '-B', '-c', IMPORT_PROBE, str(stage)],
                                 cwd=stage, capture_output=True, text=True)
            self.assertEqual(ran.returncode, 0, ran.stderr)
            result = json.loads(ran.stdout)
            self.assertTrue(result['isolatedImportClosure'])
            self.assertTrue(result['invalidReportRejected'])
            self.assertFalse(result['stageQualified'])
            self.assertFalse(result['networkOrGitExecuted'])

    def test_missing_v2_module_reproduces_original_import_failure(self):
        with tempfile.TemporaryDirectory(prefix='chrome-stage-negative-') as temp:
            stage = Path(temp)
            copy_tools(stage)
            (stage / 'tools/gecko/chrome_collapse_contract_v2.py').unlink()
            ran = subprocess.run([sys.executable, '-I', '-B', '-c', IMPORT_PROBE, str(stage)],
                                 cwd=stage, capture_output=True, text=True)
            self.assertNotEqual(ran.returncode, 0)
            self.assertIn('ModuleNotFoundError', ran.stderr)
            self.assertIn('chrome_collapse_contract_v2', ran.stderr)


if __name__ == '__main__':
    unittest.main()
