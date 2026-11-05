"""Execute CPU publication contracts with synthetic metadata, never Android proof.

The original CPU packets are explicit host fixtures. The actual selected-source
CPU checker and its extracted validator execute; installed APK verification is
an equality-only boundary because these controls contain no APK or SDK.
"""
import ast
from contextlib import contextmanager
import copy
import hashlib
import importlib
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import types
import unittest
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'tools'))
sys.path.insert(0,str(ROOT/'tests'))
from browser_publish_gate_test import execute,workflow_tree
import gecko_cpu_acceptance_test as cpu_controls

SOURCE=cpu_controls.SOURCE
REPORT='gecko-cpu-results.json'
RAW='gecko-cpu-evidence'
CHECKER='tools/browser/check_gecko_cpu_evidence.py'
SERVER='tools/gecko/cpu_acceptance_server.py'


class CpuPublicationTests(unittest.TestCase):
    def setUp(self):
        self.gate=importlib.import_module('browser.check_evidence')
        self.cpu=importlib.import_module('browser.check_gecko_cpu_evidence')
        self.factory=cpu_controls.ProductionCpuControls()

    def reader(self,source,path):
        self.assertEqual(source,SOURCE)
        return (ROOT/path).read_bytes()

    def fixture(self,directory):
        raw=directory/RAW;raw.mkdir()
        summary,expected=self.factory.evidence_fixture(raw)
        payload=(json.dumps(summary,indent=2)+'\n').encode()
        (directory/REPORT).write_bytes(payload);(raw/'results.json').write_bytes(payload)
        (directory/'browser-results.json').write_text(json.dumps({'expectedBuildIdentity':expected}))
        self.device(directory,expected)
        return summary,expected

    def device(self,directory,expected):
        (directory/'device-results.json').write_text(json.dumps(dict(status='passed',sourceCommit=SOURCE,
            actualAndroidExecution=True,eventTransport={'buildIdentity':expected})))

    @contextmanager
    def prior_evidence_boundaries(self):
        calls=[];modules={}
        for name,function in (
                ('browser.check_fingerprint_evidence','verify_fingerprint_evidence'),
                ('browser.check_worker_policy_evidence','verify_worker_policy_evidence'),
                ('browser.check_gecko_environment_policy_evidence','verify_gecko_environment_policy_evidence')):
            module=types.ModuleType(name)
            def verify(directory,source,expected,reader,name=name):
                self.assertEqual(source,SOURCE);calls.append((name,expected['version']))
                return {'scope':'explicit old-gate metadata boundary; no Android claim'}
            setattr(module,function,verify);modules[name]=module
        result={'buildIdentity':{},'checks':[{}],'provider':{'package':'synthetic','version':'fixture'}}
        with patch.object(self.gate,'validate_behavior',return_value=result),\
                patch.object(self.gate,'verify_installed',side_effect=lambda actual,expected:None),\
                patch.object(self.cpu,'verify_installed',side_effect=lambda actual,expected:self.assertEqual(actual,expected)),\
                patch.dict(sys.modules,modules):
            yield calls

    def browser_block(self):
        tree=ast.parse((ROOT/'tools/publish-gecko-release.py').read_text())
        result=[node for node in tree.body if isinstance(node,ast.If)
            and any(isinstance(value,ast.Constant) and value.value=='controlledBrowserRegression' for value in ast.walk(node))]
        self.assertEqual(len(result),1)
        return result

    def test_real_publisher_cpu_threshold_is_semantic_and_additive(self):
        tree=ast.parse((ROOT/'tools/publish-gecko-release.py').read_text())
        assignments=[node for node in tree.body if isinstance(node,ast.Assign)
            and any(isinstance(target,ast.Name) and target.id=='cpu_release' for target in node.targets)]
        self.assertEqual(len(assignments),1)
        for version,required in (('2.0.99',False),('2.1.1',False),('2.1.2',False),('2.1.3',True),('2.1.4',True),('2.10.0',True),('3.0.0',True)):
            namespace={'version':version};execute(assignments,namespace)
            self.assertIs(namespace['cpu_release'],required)

    def test_combined_213_gate_replays_actual_cpu_cases_and_keeps_212_gates(self):
        with tempfile.TemporaryDirectory(prefix='cpu-publication-host-') as tmp:
            directory=Path(tmp);summary,expected=self.fixture(directory)
            with self.prior_evidence_boundaries() as calls:
                checked=self.gate.verify_browser_evidence(directory,SOURCE,reader=self.reader)
                self.assertEqual(checked['geckoCpuRegression']['caseCount'],10)
                self.assertEqual(set(checked['geckoCpuRegression']['caseSha256']),{row[0] for row in self.cpu.CASE_SPECS})
                self.assertFalse(checked['geckoCpuRegression']['workerCoverageVerified'])
                self.assertEqual([name for name,_ in calls],['browser.check_fingerprint_evidence','browser.check_worker_policy_evidence','browser.check_gecko_environment_policy_evidence'])
                expected['version']='2.1.2';self.device(directory,expected);(directory/REPORT).unlink();shutil.rmtree(directory/RAW)
                with patch.object(self.cpu,'verify_gecko_cpu_evidence',side_effect=AssertionError('CPU must not be required before 2.1.3')):
                    prior=self.gate.verify_browser_evidence(directory,SOURCE,reader=self.reader)
                self.assertNotIn('geckoCpuRegression',prior)
                self.assertIn('workerPolicyRegression',prior);self.assertIn('geckoEnvironmentPolicyRegression',prior)

    def test_213_and_later_reject_missing_cpu_summary_in_the_actual_publisher_call(self):
        for version in ('2.1.3','2.1.4','2.10.0','3.0.0'):
            with self.subTest(version=version),tempfile.TemporaryDirectory(prefix='cpu-publisher-missing-') as tmp:
                directory=Path(tmp);_,expected=self.fixture(directory);expected['version']=version;self.device(directory,expected)
                (directory/REPORT).unlink();(directory/RAW/'results.json').unlink()
                manifest={}
                with self.prior_evidence_boundaries(),self.assertRaises((ValueError,FileNotFoundError)):
                    execute(self.browser_block(),dict(browser_release=True,manifest=manifest,args=types.SimpleNamespace(evidence=directory,source=SOURCE)))
                self.assertNotIn('controlledBrowserRegression',manifest)

    def test_actual_cpu_checker_rejects_bad_original_case_bytes_through_publisher(self):
        for mode in ('missing','changed-bytes','malformed-json','symlink'):
            with self.subTest(mode=mode),tempfile.TemporaryDirectory(prefix='cpu-publisher-raw-') as tmp:
                directory=Path(tmp);summary,_=self.fixture(directory);name=summary['caseRecords'][0]['report'];path=directory/RAW/name
                if mode=='missing':path.unlink()
                elif mode=='changed-bytes':path.write_bytes(path.read_bytes()+b' ')
                elif mode=='malformed-json':path.write_bytes(b'{"schema":1,"schema":1}')
                else:path.unlink();path.symlink_to(directory/REPORT)
                manifest={}
                # Source/APK boundaries remain explicit; the actual CPU checker,
                # hashes and selected production validator are not mocked.
                with self.prior_evidence_boundaries(),patch.object(self.cpu,'source_bytes',self.reader),\
                        self.assertRaises((ValueError,FileNotFoundError)):
                    original=self.cpu.verify_gecko_cpu_evidence
                    def selected(directory,source,expected,reader=None):return original(directory,source,expected,self.reader)
                    with patch.object(self.cpu,'verify_gecko_cpu_evidence',side_effect=selected):
                        execute(self.browser_block(),dict(browser_release=True,manifest=manifest,args=types.SimpleNamespace(evidence=directory,source=SOURCE)))
                self.assertNotIn('controlledBrowserRegression',manifest)

    def test_copy_preserves_only_summary_and_ten_exact_raw_case_bytes(self):
        helper=getattr(self.gate,'copy_gecko_cpu_evidence')
        for duplicate in (True,False):
            with self.subTest(duplicate=duplicate),tempfile.TemporaryDirectory(prefix='cpu-copy-host-') as tmp:
                base=Path(tmp);source=base/'source';source.mkdir();_,expected=self.fixture(source);stage=base/'stage';stage.mkdir()
                if not duplicate:(source/RAW/'results.json').unlink()
                with self.prior_evidence_boundaries():paths=helper(source,stage,SOURCE,expected,reader=self.reader)
                wanted={REPORT,*{RAW+'/case-'+row[0]+'.json' for row in self.cpu.CASE_SPECS}}
                self.assertEqual(set(paths),wanted);self.assertEqual(len(paths),len(wanted))
                self.assertEqual({str(p.relative_to(stage)) for p in stage.rglob('*') if p.is_file()},wanted)
                for name in wanted:self.assertEqual((stage/name).read_bytes(),(source/name).read_bytes())
                self.assertFalse((stage/RAW/'results.json').exists())

    def test_copy_refuses_unrelated_private_files_alias_changes_and_symlink_destinations(self):
        helper=getattr(self.gate,'copy_gecko_cpu_evidence')
        for mode in ('private-key','arbitrary-json','nested-directory','bad-alias','source-symlink','source-directory-symlink','destination-symlink','destination-summary-dangling-symlink'):
            with self.subTest(mode=mode),tempfile.TemporaryDirectory(prefix='cpu-copy-reject-') as tmp:
                base=Path(tmp);source=base/'source';source.mkdir();summary,expected=self.fixture(source);stage=base/'stage';stage.mkdir()
                if mode=='private-key':(source/RAW/'tls-private.pem').write_bytes(b'explicit synthetic forbidden bytes')
                elif mode=='arbitrary-json':(source/RAW/'unrelated.json').write_bytes(b'{}')
                elif mode=='nested-directory':(source/RAW/'nested').mkdir()
                elif mode=='bad-alias':(source/RAW/'results.json').write_bytes(b'{}')
                elif mode=='source-symlink':
                    name=summary['caseRecords'][0]['report'];(source/RAW/name).unlink();(source/RAW/name).symlink_to(source/REPORT)
                elif mode=='source-directory-symlink':
                    outside=base/'outside-raw';(source/RAW).rename(outside);(source/RAW).symlink_to(outside,target_is_directory=True)
                elif mode=='destination-summary-dangling-symlink':(stage/REPORT).symlink_to(base/'outside-summary.json')
                else:
                    outside=base/'outside';outside.mkdir();(stage/RAW).symlink_to(outside,target_is_directory=True)
                with self.prior_evidence_boundaries(),self.assertRaises((ValueError,AssertionError,FileExistsError)):
                    helper(source,stage,SOURCE,expected,reader=self.reader)
                self.assertFalse((stage/REPORT).exists())
                self.assertFalse((base/'outside-summary.json').exists())

    def test_actual_publisher_stage_copies_original_cpu_bytes_and_checker_dependencies(self):
        tree=ast.parse((ROOT/'tools/publish-gecko-release.py').read_text())
        blocks=[node for node in tree.body if isinstance(node,ast.If) and ast.unparse(node.test)=='cpu_release']
        evidence=[node for node in blocks if any(isinstance(v,ast.Call) and ast.unparse(v.func)=='copy_gecko_cpu_evidence' for v in ast.walk(node))]
        copies=[node for node in blocks if any(isinstance(v,ast.Call) and ast.unparse(v.func)=='shutil.copy2' for v in ast.walk(node))]
        self.assertEqual(len(evidence),1);self.assertEqual(len(copies),1)
        exit_node=next(node for node in tree.body if isinstance(node,ast.If) and ast.unparse(node.test)=='args.stage_only')
        self.assertLess(evidence[0].lineno,exit_node.lineno);self.assertLess(copies[0].lineno,exit_node.lineno)
        with tempfile.TemporaryDirectory(prefix='cpu-actual-publisher-stage-') as tmp:
            base=Path(tmp);source=base/'evidence';source.mkdir();_,expected=self.fixture(source)
            stage=base/'stage';(stage/'tools/browser').mkdir(parents=True);(stage/'tools/gecko').mkdir()
            reference=copy.deepcopy(expected);observed=[];actual_helper=getattr(self.gate,'copy_gecko_cpu_evidence')
            def selected(directory,destination,actual_source,actual_expected):
                self.assertIs(actual_expected,reference);observed.append((directory,destination,actual_source))
                return actual_helper(directory,destination,actual_source,actual_expected,reader=self.reader)
            namespace=dict(cpu_release=True,root=ROOT,stage=stage,shutil=shutil,performance_files=[],
                args=types.SimpleNamespace(evidence=source,source=SOURCE),report={'eventTransport':{'buildIdentity':reference}})
            with self.prior_evidence_boundaries(),patch.object(self.gate,'copy_gecko_cpu_evidence',side_effect=selected):
                execute(evidence+copies,namespace)
            wanted={REPORT,*{RAW+'/case-'+row[0]+'.json' for row in self.cpu.CASE_SPECS}}
            self.assertEqual(set(namespace['performance_files']),wanted);self.assertEqual(len(namespace['performance_files']),len(wanted))
            self.assertEqual(observed,[(source,stage,SOURCE)])
            for name in wanted:self.assertEqual((stage/name).read_bytes(),(source/name).read_bytes())
            for name in (CHECKER,SERVER):self.assertEqual((stage/name).read_bytes(),(ROOT/name).read_bytes())
            empty=dict(namespace,cpu_release=False,performance_files=[])
            execute(evidence+copies,empty);self.assertEqual(empty['performance_files'],[])

    def test_cpu_checker_mutable_tool_lists_match_and_server_is_immutable_source_dependency(self):
        tool=ast.parse((ROOT/'tools/publish-gecko-release.py').read_text());workflow=workflow_tree()
        for version in ('2.1.0','2.1.2','2.1.3','2.1.4','3.0.0'):
            parts=tuple(map(int,version.split('.')));values=[]
            for tree,name,namespace in ((tool,'release_tool_files',dict(version=version,browser_release=parts>=(2,1,0),fingerprint_release=parts>=(2,1,1),worker_timezone_release=parts>=(2,1,2),cpu_release=parts>=(2,1,3))),(workflow,'release_files',dict(m={'version':version}))):
                nodes=[n for n in tree.body if isinstance(n,ast.Assign) and any(isinstance(t,ast.Name) and t.id==name for t in n.targets)]
                nodes += [n for n in tree.body if isinstance(n,ast.If) and any(isinstance(v,ast.Call) and ast.unparse(v.func) in (name+'.add',name+'.update') for v in ast.walk(n))]
                execute(nodes,namespace);values.append(namespace[name])
            self.assertEqual(values[0],values[1]);self.assertEqual(CHECKER in values[0],parts>=(2,1,3));self.assertNotIn(SERVER,values[0])
        dependencies=[node for node in workflow.body if isinstance(node,ast.If)
            and any(isinstance(v,ast.Constant) and v.value==SERVER for v in ast.walk(node))
            and any(isinstance(v,ast.Call) and ast.unparse(v.func)=='subprocess.check_output' for v in ast.walk(node))]
        self.assertEqual(len(dependencies),1,'CPU parser must be pinned to tested source, not mutable tools')
        with tempfile.TemporaryDirectory(prefix='cpu-parser-pin-') as tmp:
            base=Path(tmp);p=base/SERVER;p.parent.mkdir(parents=True);p.write_bytes(b'exact synthetic tested-source parser\r\n')
            def read(command,**kwargs):
                self.assertEqual(command,['git','show',SOURCE+':'+SERVER]);return b'exact synthetic tested-source parser\r\n'
            previous=Path.cwd()
            try:
                import os;os.chdir(base)
                namespace=dict(m={'version':'2.1.3','sourceCommit':SOURCE},pathlib=types.SimpleNamespace(Path=Path),subprocess=types.SimpleNamespace(check_output=read))
                execute(dependencies,namespace);p.write_bytes(b'changed parser')
                with self.assertRaises(AssertionError):execute(dependencies,namespace)
                p.unlink()
                with self.assertRaises(FileNotFoundError):execute(dependencies,namespace)
            finally:os.chdir(previous)

    def test_actual_cpu_checker_cold_import_has_only_staged_dependency_and_no_checkout_fallback(self):
        files=(CHECKER,SERVER,'tools/browser/check_evidence.py','tools/gecko/profile_invocation_contract.py','tools/gecko/sdk_identity_contract.py')
        for missing in (None,SERVER,'tools/gecko/sdk_identity_contract.py'):
            with self.subTest(missing=missing),tempfile.TemporaryDirectory(prefix='cpu-stage-cold-import-') as tmp:
                base=Path(tmp)
                for name in files:
                    if name==missing:continue
                    p=base/name;p.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(ROOT/name,p)
                program="import pathlib,sys;root=pathlib.Path(sys.argv[1]);sys.path.insert(0,str(root/'tools'));from browser.check_evidence import verify_browser_evidence,copy_gecko_cpu_evidence;import browser.check_gecko_cpu_evidence as c;assert pathlib.Path(c.__file__).is_relative_to(root);assert callable(c.verify_gecko_cpu_evidence);print('isolated-stage-import-passed;actualAndroidExecution=false')"
                ran=subprocess.run([sys.executable,'-I','-c',program,str(base)],cwd=base,capture_output=True,text=True,timeout=15)
                if missing is None:self.assertEqual(ran.returncode,0,ran.stdout+ran.stderr)
                else:self.assertNotEqual(ran.returncode,0,'Missing real staged dependency must not fall back to checkout')

if __name__=='__main__':unittest.main(verbosity=2)
