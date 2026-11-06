"""Execute the additive 2.1.1 publication/staging boundary, never an Android claim."""
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

CHECKER='tools/browser/check_fingerprint_evidence.py'
REPORT='browser-fingerprint-results.json'

class FingerprintPublicationTests(unittest.TestCase):
    def setUp(self):
        self.tool=ast.parse((ROOT/'tools/publish-gecko-release.py').read_text())
        self.workflow=workflow_tree()

    def test_source_allowlists_share_exact_version_threshold(self):
        for version in ('2.0.47','2.1.0','2.1.1','2.2.0','3.0.0'):
            expected=tuple(map(int,version.split('.'))) >= (2,1,1)
            values=[]
            for tree,name,namespace in ((self.tool,'release_tool_files',dict(version=version,browser_release=tuple(map(int,version.split('.'))) >= (2,1,0),fingerprint_release=expected,worker_timezone_release=tuple(map(int,version.split('.'))) >= (2,1,2),cpu_release=tuple(map(int,version.split('.'))) >= (2,1,3))),(self.workflow,'release_files',dict(m={'version':version}))):
                nodes=[node for node in tree.body if isinstance(node,ast.Assign) and any(isinstance(t,ast.Name) and t.id==name for t in node.targets)]
                nodes += [node for node in tree.body if isinstance(node,ast.If) and any(isinstance(v,ast.Call) and ast.unparse(v.func) in (name+'.add',name+'.update') for v in ast.walk(node))]
                execute(nodes,namespace);values.append(namespace[name])
            with self.subTest(version=version):
                self.assertEqual(values[0],values[1]);self.assertEqual(CHECKER in values[0],expected)

    def test_exact_report_and_checker_survive_standard_stage(self):
        additions=[node for node in self.tool.body if isinstance(node,ast.If) and ast.unparse(node.test)=='fingerprint_release' and any(isinstance(v,ast.Constant) and v.value==REPORT for v in ast.walk(node))]
        copies=[node for node in self.tool.body if isinstance(node,ast.If) and ast.unparse(node.test)=='fingerprint_release' and any(isinstance(v,ast.Call) and ast.unparse(v.func)=='shutil.copy2' for v in ast.walk(node))]
        self.assertEqual(len(additions),1);self.assertEqual(len(copies),1)
        exit_node=next(node for node in self.tool.body if isinstance(node,ast.If) and ast.unparse(node.test)=='args.stage_only')
        self.assertLess(copies[0].lineno,exit_node.lineno)
        report_copy=[node for node in self.tool.body if isinstance(node,ast.For) and ast.unparse(node.target)=='name' and ast.unparse(node.iter)=='performance_files']
        with tempfile.TemporaryDirectory() as temporary:
            base=Path(temporary);mirror=base/'source';stage=base/'stage';evidence=base/'evidence';stage.mkdir();evidence.mkdir()
            (mirror/CHECKER).parent.mkdir(parents=True);checker=b'# synthetic exact checker bytes\r\n';(mirror/CHECKER).write_bytes(checker)
            payload=b'{"synthetic":"both source-bound engine results"}\r\n';(evidence/REPORT).write_bytes(payload)
            namespace=dict(fingerprint_release=True,root=mirror,stage=stage,shutil=shutil,args=types.SimpleNamespace(evidence=evidence),performance_files=[])
            execute(additions+report_copy+copies,namespace)
            self.assertEqual(namespace['performance_files'],[REPORT]);self.assertEqual((stage/REPORT).read_bytes(),payload);self.assertEqual((stage/CHECKER).read_bytes(),checker)

    def test_combined_gate_requires_new_evidence_for_211_and_preserves_210(self):
        spec=importlib.util.spec_from_file_location('combined_browser_gate',ROOT/'tools/browser/check_evidence.py');gate=importlib.util.module_from_spec(spec);spec.loader.exec_module(gate)
        source='a'*40;calls=[]
        module=types.ModuleType('browser.check_fingerprint_evidence')
        def verify(directory,actual_source,expected,reader):
            calls.append((Path(directory),actual_source,expected['version']))
            raw=(Path(directory)/REPORT).read_bytes()
            if raw!=b'exact synthetic fingerprint receipt':raise ValueError('Fingerprint evidence rejected')
            return {'status':'synthetic-boundary-accepted'}
        module.verify_fingerprint_evidence=verify
        result={'buildIdentity':{},'checks':[{}],'provider':{'package':'synthetic','version':'fixture'}}
        with tempfile.TemporaryDirectory() as temporary:
            directory=Path(temporary);(directory/'browser-results.json').write_text(json.dumps({'expectedBuildIdentity':{}}))
            expected={'sourceCommit':source,'sourceTree':'b'*40,'apkSha256':'c'*64,'version':'2.1.1','sdkBuildIdentity':{'runId':'11','runAttempt':'1'}}
            def device():
                (directory/'device-results.json').write_text(json.dumps({'status':'passed','sourceCommit':source,'actualAndroidExecution':True,'eventTransport':{'buildIdentity':expected}}))
            device()
            with patch.object(gate,'validate_behavior',return_value=result),patch.object(gate,'verify_installed'),patch.dict(sys.modules,{'browser.check_fingerprint_evidence':module}):
                with self.assertRaises(FileNotFoundError):gate.verify_browser_evidence(directory,source)
                (directory/REPORT).write_bytes(b'wrong receipt')
                with self.assertRaises(ValueError):gate.verify_browser_evidence(directory,source)
                (directory/REPORT).write_bytes(b'exact synthetic fingerprint receipt')
                checked=gate.verify_browser_evidence(directory,source);self.assertIn('fingerprintRegression',checked)
                expected['version']='2.1.0';device();(directory/REPORT).unlink()
                self.assertNotIn('fingerprintRegression',gate.verify_browser_evidence(directory,source))
            self.assertEqual(len(calls),3)

if __name__=='__main__':unittest.main(verbosity=2)
