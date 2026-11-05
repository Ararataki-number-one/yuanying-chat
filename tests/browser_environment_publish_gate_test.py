"""Exercise additive release omissions using explicit metadata boundaries, no device claim."""
import ast
import importlib.util
import json
from pathlib import Path
import shutil
import sys
import tempfile
import types
import unittest
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'tests'))
from browser_publish_gate_test import execute,workflow_tree

REPORTS=('worker-policy-results.json','gecko-environment-policy-results.json')
CHECKERS=('tools/browser/check_worker_policy_evidence.py','tools/browser/check_gecko_environment_policy_evidence.py')

class EnvironmentPublicationTests(unittest.TestCase):
    def test_both_source_allowlists_require_new_checkers_at_exact_threshold(self):
        tool=ast.parse((ROOT/'tools/publish-gecko-release.py').read_text());workflow=workflow_tree()
        for version in ('2.1.0','2.1.1','2.1.2','2.1.3','3.0.0'):
            parts=tuple(map(int,version.split('.')));values=[]
            for tree,name,namespace in ((tool,'release_tool_files',dict(version=version,browser_release=parts>=(2,1,0),fingerprint_release=parts>=(2,1,1),worker_timezone_release=parts>=(2,1,2))),(workflow,'release_files',dict(m={'version':version}))):
                nodes=[n for n in tree.body if isinstance(n,ast.Assign) and any(isinstance(t,ast.Name) and t.id==name for t in n.targets)]
                nodes += [n for n in tree.body if isinstance(n,ast.If) and any(isinstance(v,ast.Call) and ast.unparse(v.func) in (name+'.add',name+'.update') for v in ast.walk(n))]
                execute(nodes,namespace);values.append(namespace[name])
            self.assertEqual(values[0],values[1])
            for path in CHECKERS:self.assertEqual(path in values[0],parts>=(2,1,2))

    def test_exact_reports_and_checkers_are_copied_before_stage_only_returns(self):
        tool=ast.parse((ROOT/'tools/publish-gecko-release.py').read_text())
        blocks=[n for n in tool.body if isinstance(n,ast.If) and ast.unparse(n.test)=='worker_timezone_release']
        additions=[n for n in blocks if any(isinstance(v,ast.Call) and ast.unparse(v.func)=='performance_files.extend' for v in ast.walk(n))]
        copies=[n for n in blocks if any(isinstance(v,ast.Call) and ast.unparse(v.func)=='shutil.copy2' for v in ast.walk(n))]
        stage_exit=next(n for n in tool.body if isinstance(n,ast.If) and ast.unparse(n.test)=='args.stage_only')
        self.assertEqual(len(additions),1);self.assertEqual(len(copies),1);self.assertLess(copies[0].lineno,stage_exit.lineno)
        report_copy=[n for n in tool.body if isinstance(n,ast.For) and ast.unparse(n.target)=='name' and ast.unparse(n.iter)=='performance_files']
        with tempfile.TemporaryDirectory() as tmp:
            base=Path(tmp);source=base/'source';stage=base/'stage';evidence=base/'evidence';(stage/'tools/browser').mkdir(parents=True);evidence.mkdir()
            for name in CHECKERS:
                f=source/name;f.parent.mkdir(parents=True,exist_ok=True);f.write_bytes(('# synthetic exact source checker: '+name+'\r\n').encode())
            for name in REPORTS:(evidence/name).write_bytes(json.dumps({'syntheticBoundaryOnly':True,'name':name}).encode()+b'\r\n')
            namespace=dict(worker_timezone_release=True,root=source,stage=stage,shutil=shutil,args=types.SimpleNamespace(evidence=evidence),performance_files=[])
            execute(additions+report_copy+copies,namespace)
            self.assertEqual(namespace['performance_files'],list(REPORTS))
            for name in CHECKERS:self.assertEqual((stage/name).read_bytes(),(source/name).read_bytes())
            for name in REPORTS:self.assertEqual((stage/name).read_bytes(),(evidence/name).read_bytes())

    def test_212_cannot_publish_when_either_additional_report_is_missing_or_rejected(self):
        spec=importlib.util.spec_from_file_location('environment_combined_gate',ROOT/'tools/browser/check_evidence.py');gate=importlib.util.module_from_spec(spec);spec.loader.exec_module(gate)
        calls=[];source='a'*40;reader=lambda commit,path:b'explicit source reader boundary'
        fp=types.ModuleType('browser.check_fingerprint_evidence');fp.verify_fingerprint_evidence=lambda *a,**k:{'scope':'synthetic fingerprint boundary'}
        modules={'browser.check_fingerprint_evidence':fp}
        ip=types.ModuleType('browser.check_gecko_ip_timezone_evidence')
        def verify_ip(directory,actual,expected,reader):
            if (Path(directory)/'gecko-ip-timezone-results.json').read_bytes()!=b'explicit synthetic IP checker boundary':raise ValueError('Required IP evidence rejected')
            return {'scope':'synthetic IP metadata boundary only'}
        ip.verify_gecko_ip_timezone_evidence=verify_ip
        modules['browser.check_gecko_ip_timezone_evidence']=ip
        for module_name,function,report in (('browser.check_worker_policy_evidence','verify_worker_policy_evidence',REPORTS[0]),('browser.check_gecko_environment_policy_evidence','verify_gecko_environment_policy_evidence',REPORTS[1])):
            module=types.ModuleType(module_name)
            def verify(directory,actual,expected,reader,report=report):
                calls.append((report,actual,expected['version'],reader));raw=(Path(directory)/report).read_bytes()
                if raw!=b'exact synthetic boundary':raise ValueError('Required additional evidence rejected')
                return {'scope':'synthetic metadata acceptance only'}
            setattr(module,function,verify);modules[module_name]=module
        result={'buildIdentity':{},'checks':[{}],'provider':{'package':'synthetic','version':'fixture'}}
        with tempfile.TemporaryDirectory() as tmp:
            directory=Path(tmp);(directory/'browser-results.json').write_text(json.dumps({'expectedBuildIdentity':{}}))
            (directory/'gecko-ip-timezone-results.json').write_bytes(b'explicit synthetic IP checker boundary')
            expected={'sourceCommit':source,'sourceTree':'b'*40,'apkSha256':'c'*64,'version':'2.1.1','sdkBuildIdentity':{'runId':'11','runAttempt':'1'}}
            def device():(directory/'device-results.json').write_text(json.dumps({'status':'passed','sourceCommit':source,'actualAndroidExecution':True,'eventTransport':{'buildIdentity':expected}}))
            device()
            with patch.object(gate,'validate_behavior',return_value=result),patch.object(gate,'verify_installed'),patch.dict(sys.modules,modules):
                prior=gate.verify_browser_evidence(directory,source,reader=reader);self.assertNotIn('workerPolicyRegression',prior);self.assertEqual(calls,[])
                expected['version']='2.1.2';device()
                with self.assertRaises(FileNotFoundError):gate.verify_browser_evidence(directory,source,reader=reader)
                (directory/REPORTS[0]).write_bytes(b'rejected')
                with self.assertRaises(ValueError):gate.verify_browser_evidence(directory,source,reader=reader)
                (directory/REPORTS[0]).write_bytes(b'exact synthetic boundary')
                with self.assertRaises(FileNotFoundError):gate.verify_browser_evidence(directory,source,reader=reader)
                (directory/REPORTS[1]).write_bytes(b'rejected')
                with self.assertRaises(ValueError):gate.verify_browser_evidence(directory,source,reader=reader)
                (directory/REPORTS[1]).write_bytes(b'exact synthetic boundary')
                checked=gate.verify_browser_evidence(directory,source,reader=reader)
                self.assertIn('workerPolicyRegression',checked);self.assertIn('geckoEnvironmentPolicyRegression',checked)
            self.assertTrue(calls);self.assertTrue(all(actual==source and version=='2.1.2' and observed_reader is reader for _,actual,version,observed_reader in calls))

if __name__=='__main__':unittest.main(verbosity=2)
