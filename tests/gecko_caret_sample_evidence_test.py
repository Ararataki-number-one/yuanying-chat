"""Host-only controls for retaining failed setup evidence; no input acceptance."""
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'tools/gecko'))
spec=importlib.util.spec_from_file_location('sample_evidence_controls',ROOT/'tools/gecko/key_order_samples.py')
samples=importlib.util.module_from_spec(spec);spec.loader.exec_module(samples)


class SetupEvidenceControls(unittest.TestCase):
    def stage(self,source,target):
        args=SimpleNamespace(input=source,out=target,sample='1')
        with patch.object(samples.subprocess,'check_output',return_value='a'*40+'\n'),patch.dict(os.environ,{'GITHUB_RUN_ID':'123','GITHUB_RUN_ATTEMPT':'1'}),patch.object(samples,'verify_caret_evidence',side_effect=ValueError('Original input evidence missing')) as verify:
            with self.assertRaisesRegex(AssertionError,'Original input evidence missing'):samples.stage(args)
            verify.assert_called_once_with(target,'a'*40)
        return json.loads((target/'sample-receipt.json').read_text())

    def test_setup_failure_keeps_every_available_original_diagnostic_and_stays_failed(self):
        with tempfile.TemporaryDirectory() as folder:
            base=Path(folder);source=base/'source';source.mkdir();target=base/'out'
            contents={name:(name+'\nraw setup evidence\n').encode() for name in samples.SETUP_DIAGNOSTICS}
            contents['native-test.log']=b'Original setup traceback\n'
            for name,data in contents.items():(source/name).write_bytes(data)
            report=self.stage(source,target)
            self.assertEqual(report['status'],'failed')
            self.assertFalse(report['workloadRerun'])
            self.assertFalse(report['physicalPhoneAcceptance'])
            self.assertEqual(report['error'],'Original input evidence missing')
            self.assertEqual(set(report['files']),set(contents))
            for name,data in contents.items():
                self.assertEqual((target/name).read_bytes(),data)
                self.assertEqual(report['files'][name],hashlib.sha256(data).hexdigest())

    def test_missing_diagnostics_are_not_manufactured_or_used_as_input_success(self):
        with tempfile.TemporaryDirectory() as folder:
            base=Path(folder);source=base/'source';source.mkdir();target=base/'out'
            report=self.stage(source,target)
            self.assertEqual(report['status'],'failed')
            self.assertEqual(report['files'],{})
            self.assertEqual([path.name for path in target.iterdir()],['sample-receipt.json'])

    def test_truncated_setup_json_is_preserved_verbatim_for_diagnosis(self):
        with tempfile.TemporaryDirectory() as folder:
            base=Path(folder);source=base/'source';source.mkdir();target=base/'out'
            name='native-adb-setup-results.json';raw=b'{"status":"failed","commands":[\n'
            (source/name).write_bytes(raw)
            report=self.stage(source,target)
            self.assertEqual((target/name).read_bytes(),raw)
            self.assertEqual(report['files'][name],hashlib.sha256(raw).hexdigest())
            self.assertEqual(report['status'],'failed')


if __name__=='__main__':unittest.main()
