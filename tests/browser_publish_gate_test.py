"""Execute publication gate and staging statements with explicit evidence adapters."""
import ast
from contextlib import contextmanager
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import textwrap
import types
import unittest
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]
PUBLISHER=ROOT/'tools/publish-gecko-release.py'
WORKFLOW=ROOT/'.github/workflows/publish-gecko-release.yml'
SOURCE='a'*40
CHECKER='tools/browser/check_evidence.py'


def execute(nodes,namespace):
    exec(compile(ast.Module(body=nodes,type_ignores=[]),'actual-publication-statements','exec'),namespace)


def workflow_tree():
    source=WORKFLOW.read_text().split("python3 - <<'PY'\n",1)[1].split('\n          PY',1)[0]
    return ast.parse(textwrap.dedent(source))


@contextmanager
def directory(path):
    previous=Path.cwd();os.chdir(path)
    try:yield
    finally:os.chdir(previous)


class BrowserPublishGateTests(unittest.TestCase):
    def setUp(self):
        self.tool=ast.parse(PUBLISHER.read_text());self.workflow=workflow_tree();self.calls=[]
        self.checked={'sourceCommit':SOURCE,'integrationApkSha256':'b'*64,'reportSha256':'c'*64,
                      'actualAndroidExecution':True,'actualAndroidWebViewExecution':True,'physicalPhoneAcceptance':False}

    def browser_blocks(self,tree):
        return [node for node in tree.body if isinstance(node,ast.If)
                and any(isinstance(value,ast.Constant) and value.value=='controlledBrowserRegression' for value in ast.walk(node))]

    @contextmanager
    def verifier(self):
        module=types.ModuleType('controlled_browser_gate_adapter')
        def verify(path,source):
            self.calls.append((Path(path),source))
            raw=json.loads((Path(path)/'browser-results.json').read_text())
            if raw.get('sourceCommit')!=source or raw.get('status')!='passed':raise ValueError('Synthetic evidence adapter rejected source/status')
            return dict(self.checked)
        module.verify_browser_evidence=verify
        with patch.dict(sys.modules,{'browser.check_evidence':module,'tools.browser.check_evidence':module}):yield

    def evidence(self,path,status='passed',source=SOURCE):
        (path/'browser-results.json').write_text(json.dumps(dict(status=status,sourceCommit=source)))

    def test_real_tool_version_threshold_is_semantic_and_additive(self):
        assignments=[node for node in self.tool.body if isinstance(node,ast.Assign)
                     and any(isinstance(name,ast.Name) and name.id=='browser_release' for name in node.targets)]
        self.assertEqual(len(assignments),1)
        for version,expected in [('2.0.99',False),('2.1.0',True),('2.1.1',True),('2.10.0',True),('3.0.0',True)]:
            namespace={'version':version};execute(assignments,namespace);self.assertIs(namespace['browser_release'],expected)

    def test_publisher_requires_and_records_verifier_result(self):
        block=self.browser_blocks(self.tool);self.assertEqual(len(block),1)
        with tempfile.TemporaryDirectory() as temporary,self.verifier():
            path=Path(temporary);self.evidence(path);manifest={};args=types.SimpleNamespace(evidence=path,source=SOURCE)
            execute(block,dict(browser_release=True,manifest=manifest,args=args))
            self.assertEqual(manifest['controlledBrowserRegression'],self.checked);self.assertEqual(self.calls,[(path,SOURCE)])
            self.assertLess(block[0].lineno,next(node.lineno for node in self.tool.body if isinstance(node,ast.If) and ast.unparse(node.test)=='not args.stage_only'))

    def test_publisher_rejects_missing_failed_or_other_source_browser_report(self):
        for mode in ('missing','failed','different-source'):
            with self.subTest(mode=mode),tempfile.TemporaryDirectory() as temporary,self.verifier():
                path=Path(temporary)
                if mode!='missing':self.evidence(path,'failed' if mode=='failed' else 'passed','d'*40 if mode=='different-source' else SOURCE)
                with self.assertRaises((ValueError,FileNotFoundError)):
                    execute(self.browser_blocks(self.tool),dict(browser_release=True,manifest={},args=types.SimpleNamespace(evidence=path,source=SOURCE)))

    def test_original_older_release_does_not_invent_browser_qualification(self):
        manifest={};execute(self.browser_blocks(self.tool),dict(browser_release=False,manifest=manifest,args=None));self.assertEqual(manifest,{})
        with tempfile.TemporaryDirectory() as temporary,directory(temporary):
            execute(self.browser_blocks(self.workflow),dict(m={'version':'2.0.47','sourceCommit':SOURCE},pathlib=types.SimpleNamespace(Path=Path)))

    def test_real_publish_workflow_recomputes_and_compares_exact_browser_binding(self):
        blocks=self.browser_blocks(self.workflow);self.assertEqual(len(blocks),1)
        with tempfile.TemporaryDirectory() as temporary,self.verifier(),directory(temporary):
            path=Path(temporary);self.evidence(path);manifest=dict(version='2.1.0',sourceCommit=SOURCE,controlledBrowserRegression=dict(self.checked))
            execute(blocks,dict(m=manifest,pathlib=types.SimpleNamespace(Path=Path)))
            self.assertEqual(self.calls,[(Path('.'),SOURCE)])
            for key,value in [('reportSha256','d'*64),('integrationApkSha256','d'*64),('physicalPhoneAcceptance',True),('sourceCommit','d'*40)]:
                changed=dict(manifest,controlledBrowserRegression=dict(self.checked,**{key:value}))
                with self.subTest(key=key),self.assertRaises(AssertionError):execute(blocks,dict(m=changed,pathlib=types.SimpleNamespace(Path=Path)))
            with self.assertRaises(KeyError):execute(blocks,dict(m={'version':'2.1.0','sourceCommit':SOURCE},pathlib=types.SimpleNamespace(Path=Path)))
            self.evidence(path,status='failed')
            with self.assertRaises(ValueError):execute(blocks,dict(m=manifest,pathlib=types.SimpleNamespace(Path=Path)))

    def test_report_and_checker_are_copied_before_stage_only_exit_and_git_add(self):
        append=[node for node in self.tool.body if isinstance(node,ast.If) and ast.unparse(node.test)=='browser_release'
                and any(isinstance(value,ast.Constant) and value.value=='browser-results.json' for value in ast.walk(node))]
        copies=[node for node in self.tool.body if isinstance(node,ast.If) and ast.unparse(node.test)=='browser_release'
                and any(isinstance(value,ast.Call) and ast.unparse(value.func)=='shutil.copy2' for value in ast.walk(node))]
        self.assertEqual(len(append),1);self.assertEqual(len(copies),1)
        stage_exit=next(node for node in self.tool.body if isinstance(node,ast.If) and ast.unparse(node.test)=='args.stage_only')
        self.assertLess(copies[0].lineno,stage_exit.lineno)
        report_copy=[node for node in self.tool.body if isinstance(node,ast.For) and ast.unparse(node.target)=='name' and ast.unparse(node.iter)=='performance_files']
        self.assertEqual(len(report_copy),1)
        with tempfile.TemporaryDirectory() as temporary:
            base=Path(temporary);mirror=base/'source';stage=base/'stage';evidence=base/'evidence';stage.mkdir();evidence.mkdir()
            (mirror/CHECKER).parent.mkdir(parents=True);original=(ROOT/CHECKER).read_bytes();(mirror/CHECKER).write_bytes(original)
            payload=b'{"synthetic":"preserve exact source-bound bytes"}\r\n';(evidence/'browser-results.json').write_bytes(payload)
            namespace=dict(browser_release=True,root=mirror,stage=stage,shutil=shutil,args=types.SimpleNamespace(evidence=evidence),performance_files=[])
            execute(append+report_copy+copies,namespace)
            self.assertEqual(namespace['performance_files'],['browser-results.json']);self.assertEqual((stage/'browser-results.json').read_bytes(),payload);self.assertEqual((stage/CHECKER).read_bytes(),original)
        git_add=[node for node in ast.walk(self.tool) if isinstance(node,ast.Call) and ast.unparse(node.func)=='subprocess.run' and node.args and isinstance(node.args[0],ast.List) and any(isinstance(value,ast.Constant) and value.value=='add' for value in node.args[0].elts)]
        self.assertEqual(len(git_add),1)
        self.assertTrue(any(isinstance(value,ast.Starred) and isinstance(value.value,ast.Name) and value.value.id=='performance_files' for value in git_add[0].args[0].elts))
        self.assertTrue(any(isinstance(value,ast.Constant) and value.value=='tools' for value in git_add[0].args[0].elts))

    def release_list(self,tree,name,namespace):
        assignments=[node for node in tree.body if isinstance(node,ast.Assign) and any(isinstance(target,ast.Name) and target.id==name for target in node.targets)]
        updates=[node for node in tree.body if isinstance(node,ast.If) and any(isinstance(value,ast.Call) and ast.unparse(value.func)==name+'.add' for value in ast.walk(node))]
        self.assertEqual(len(assignments),1);self.assertEqual(len(updates),1);execute(assignments+updates,namespace);return namespace[name]

    def test_staging_and_publisher_share_checker_source_verification_list(self):
        for version,required in [('2.0.47',False),('2.1.0',True),('3.0.0',True)]:
            tool=self.release_list(self.tool,'release_tool_files',dict(browser_release=required))
            workflow=self.release_list(self.workflow,'release_files',dict(m={'version':version}))
            self.assertEqual(tool,workflow);self.assertEqual(CHECKER in tool,required)
        checks=[node for node in self.workflow.body if isinstance(node,ast.For) and ast.unparse(node.target)=='name' and 'release_files' in ast.unparse(node.iter)]
        self.assertEqual(len(checks),1)
        files=self.release_list(self.workflow,'release_files',dict(m={'version':'2.1.0'}));files.add('tools/publish-update-feed.py')
        with tempfile.TemporaryDirectory() as temporary,directory(temporary):
            expected={name:('selected commit source: '+name).encode() for name in files}
            for name,raw in expected.items():path=Path(name);path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(raw)
            fake=types.SimpleNamespace(check_output=lambda command:expected[command[-1].split(':',1)[1]])
            execute(checks,dict(release_files=files,pathlib=types.SimpleNamespace(Path=Path),subprocess=fake,tools_commit=SOURCE))
            Path(CHECKER).write_bytes(b'changed checker cannot replace publication gate')
            with self.assertRaises(AssertionError):execute(checks,dict(release_files=files,pathlib=types.SimpleNamespace(Path=Path),subprocess=fake,tools_commit=SOURCE))

    def test_actual_staged_checker_imports_without_repository_fallback(self):
        copies=[node for node in self.tool.body if isinstance(node,ast.If)
                and ast.unparse(node.test) in ('browser_release','roadmap_release','version_code >= 46')
                and any(isinstance(value,ast.Call) and ast.unparse(value.func)=='shutil.copy2' for value in ast.walk(node))]
        self.assertEqual(len(copies),3)
        with tempfile.TemporaryDirectory(prefix='browser-release-cold-import-') as temporary:
            stage=Path(temporary);(stage/'tools/gecko').mkdir(parents=True)
            execute(copies,dict(browser_release=True,roadmap_release=True,version_code=103,root=ROOT,stage=stage,shutil=shutil))
            script="""import pathlib,sys
root=pathlib.Path.cwd();sys.path.insert(0,str(root));sys.path.insert(0,str(root/'tools'))
from browser.check_evidence import verify_browser_evidence
from tools.browser.check_evidence import verify_browser_evidence as workflow_verifier
assert callable(verify_browser_evidence) and callable(workflow_verifier)
print('STAGED_BROWSER_VERIFIERS_IMPORTED')
"""
            result=subprocess.run([sys.executable,'-I','-c',script],cwd=stage,text=True,capture_output=True,timeout=20)
            self.assertEqual(result.returncode,0,result.stderr);self.assertIn('STAGED_BROWSER_VERIFIERS_IMPORTED',result.stdout)
            (stage/'tools/gecko/profile_invocation_contract.py').unlink()
            result=subprocess.run([sys.executable,'-I','-c',script],cwd=stage,text=True,capture_output=True,timeout=20)
            self.assertNotEqual(result.returncode,0);self.assertIn('profile_invocation_contract',result.stderr)


if __name__=='__main__':unittest.main()
