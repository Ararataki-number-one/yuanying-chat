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
        updates=[node for node in tree.body if isinstance(node,ast.If) and any(isinstance(value,ast.Call) and ast.unparse(value.func) in (name+'.add',name+'.update') for value in ast.walk(node))]
        self.assertEqual(len(assignments),1);self.assertEqual(len(updates),5);execute(assignments+updates,namespace);return namespace[name]

    def test_staging_and_publisher_share_checker_source_verification_list(self):
        policies=(
            ('browser_release',(2,1,0),{CHECKER}),
            ('fingerprint_release',(2,1,1),{'tools/browser/check_fingerprint_evidence.py'}),
            ('worker_timezone_release',(2,1,2),{'tools/browser/check_worker_policy_evidence.py','tools/browser/check_gecko_environment_policy_evidence.py','tools/browser/ip_timezone_publication.py'}),
            ('cpu_release',(2,1,3),{'tools/browser/check_gecko_cpu_evidence.py','tools/browser/cpu_ip_combo_publication.py'}),
            ('tls_release',(2,1,4),{'tools/browser/tls_publication.py'}),
        )
        flags=[node for node in self.tool.body if isinstance(node,ast.Assign) and any(isinstance(target,ast.Name) and target.id in {name for name,_,_ in policies} for target in node.targets)]
        self.assertEqual(len(flags),5)
        self.assertEqual({target.id for node in flags for target in node.targets},{name for name,_,_ in policies})
        base={'.github/workflows/publish-gecko-release.yml','tools/publish-gecko-release.py','tools/gecko/release_channel_contract.py','tools/gecko/release_channel_contract_test.py'}
        for version,required in [('2.0.47',False),('2.1.0',True),('2.1.1',True),('2.1.2',True),('2.1.3',True),('2.1.4',True),('3.0.0',True)]:
            parts=tuple(map(int,version.split('.')));namespace=dict(version=version);execute(flags,namespace)
            for flag,minimum,_ in policies:self.assertIs(namespace[flag],parts>=minimum)
            tool=self.release_list(self.tool,'release_tool_files',namespace)
            workflow=self.release_list(self.workflow,'release_files',dict(m={'version':version}))
            self.assertEqual(tool,workflow);self.assertEqual(CHECKER in tool,required)
            expected=set(base)
            for _,minimum,files in policies:
                self.assertEqual(tool&files,files if parts>=minimum else set())
                if parts>=minimum:expected.update(files)
            self.assertEqual(tool,expected)
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
        files=self.release_list(self.workflow,'release_files',dict(m={'version':'2.1.4'}));files.add('tools/publish-update-feed.py')
        with tempfile.TemporaryDirectory() as temporary,directory(temporary):
            expected={name:('selected commit source: '+name).encode() for name in files}
            for name,raw in expected.items():path=Path(name);path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(raw)
            fake=types.SimpleNamespace(check_output=lambda command:expected[command[-1].split(':',1)[1]])
            namespace=dict(release_files=files,pathlib=types.SimpleNamespace(Path=Path),subprocess=fake,tools_commit=SOURCE)
            execute(checks,namespace)
            for name,raw in expected.items():
                with self.subTest(tampered=name):
                    Path(name).write_bytes(b'changed release tool cannot replace selected source')
                    with self.assertRaises(AssertionError):execute(checks,namespace)
                    Path(name).write_bytes(raw)

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

    def test_actual_staged_settings_verifier_has_its_complete_dependency_set(self):
        copies=[node for node in self.tool.body if isinstance(node,ast.If)
                and ast.unparse(node.test)=='version_code >= 70'
                and any(isinstance(value,ast.Constant) and value.value=='tests/gecko/assets/sharing-schema-matrix.json'
                        for value in ast.walk(node))]
        self.assertEqual(len(copies),1)
        stage_exit=next(node for node in self.tool.body if isinstance(node,ast.If) and ast.unparse(node.test)=='args.stage_only')
        self.assertLess(copies[0].lineno,stage_exit.lineno)
        dependencies=['tools/gecko/network_settings_callback_contract.py',
                      'tests/network_settings_callback_source_compatibility.py',
                      'tests/fixtures/network-settings-callback-source-deltas.json']
        with tempfile.TemporaryDirectory(prefix='settings-release-cold-import-') as temporary:
            stage=Path(temporary);(stage/'tools/gecko').mkdir(parents=True)
            execute(copies,dict(version_code=102,root=ROOT,stage=stage,shutil=shutil))
            shutil.copy2(ROOT/'tools/gecko/network_sources_contract.py',stage/'tools/gecko/network_sources_contract.py')
            origins=['tests/gecko/network_settings_callback_contract.py',dependencies[1],dependencies[2]]
            for target,origin in zip(dependencies,origins):
                self.assertEqual((stage/target).read_bytes(),(ROOT/origin).read_bytes())
            script="""import pathlib,sys
root=pathlib.Path.cwd();sys.path.insert(0,str(root/'tools/gecko'))
from network_sources_contract import _settings_verifier
module,path=_settings_verifier('internal')
assert callable(module.verify) and path==root/'tools/gecko/run_network_settings_internal.py'
print('STAGED_SETTINGS_VERIFIER_IMPORTED')
"""
            result=subprocess.run([sys.executable,'-I','-c',script],cwd=stage,text=True,capture_output=True,timeout=20)
            self.assertEqual(result.returncode,0,result.stderr);self.assertIn('STAGED_SETTINGS_VERIFIER_IMPORTED',result.stdout)
            for target in dependencies:
                path=stage/target;data=path.read_bytes();path.unlink()
                result=subprocess.run([sys.executable,'-I','-c',script],cwd=stage,text=True,capture_output=True,timeout=20)
                self.assertNotEqual(result.returncode,0,target);path.write_bytes(data)
        git_add=[node for node in ast.walk(self.tool) if isinstance(node,ast.Call)
                 and ast.unparse(node.func)=='subprocess.run' and node.args
                 and isinstance(node.args[0],ast.List)
                 and any(isinstance(value,ast.Constant) and value.value=='add' for value in node.args[0].elts)]
        self.assertEqual(len(git_add),1)
        namespace=dict(version_code=102,manual_raw=None,authorization_raw=None,performance_files=[],manifest={'parts':[]})
        paths=eval(compile(ast.Expression(git_add[0].args[0]),'actual-public-git-paths','eval'),namespace)
        for target in dependencies[1:]:self.assertIn(target,paths)

    def test_public_workflow_pins_each_settings_dependency_to_tested_source(self):
        blocks=[node for node in self.workflow.body if isinstance(node,ast.If)
                and any(isinstance(value,ast.Constant) and isinstance(value.value,str)
                        and value.value.startswith('Network settings dependency differs from tested source:')
                        for value in ast.walk(node))]
        self.assertEqual(len(blocks),1)
        self.assertLess(blocks[0].lineno,self.browser_blocks(self.workflow)[0].lineno)
        mapping={'tools/gecko/network_settings_callback_contract.py':'tests/gecko/network_settings_callback_contract.py',
                 'tests/network_settings_callback_source_compatibility.py':'tests/network_settings_callback_source_compatibility.py',
                 'tests/fixtures/network-settings-callback-source-deltas.json':'tests/fixtures/network-settings-callback-source-deltas.json'}
        expected={name:(ROOT/origin).read_bytes() for name,origin in mapping.items()}
        commands=[]
        def git_show(command):
            commands.append(command)
            self.assertEqual(command[:2],['git','show'])
            commit,origin=command[-1].split(':',1);self.assertEqual(commit,SOURCE)
            return (ROOT/origin).read_bytes()
        with tempfile.TemporaryDirectory(prefix='settings-release-source-pins-') as temporary,directory(temporary):
            for name,data in expected.items():path=Path(name);path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(data)
            namespace=dict(m={'version':'2.1.0','sourceCommit':SOURCE,'releaseToolsCommit':'d'*40},
                           pathlib=types.SimpleNamespace(Path=Path),subprocess=types.SimpleNamespace(check_output=git_show))
            execute(blocks,namespace);self.assertEqual(len(commands),3)
            for name,data in expected.items():
                with self.subTest(tampered=name):
                    Path(name).write_bytes(b'def verify_callback_cohort(*args): return None\n')
                    with self.assertRaises(AssertionError):execute(blocks,namespace)
                    Path(name).unlink()
                    with self.assertRaises(FileNotFoundError):execute(blocks,namespace)
                    Path(name).write_bytes(data)


if __name__=='__main__':unittest.main()
