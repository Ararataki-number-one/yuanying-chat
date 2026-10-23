"""Locked dependency download controls, never input or device acceptance."""
import hashlib
import io
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools/gecko'))
import caret_workflow as workflow

class DependencyTest(unittest.TestCase):
    def test_timeout_then_verified_body_is_atomically_published(self):
        raw=b'controlled-annotation';digest=hashlib.sha256(raw).hexdigest()
        with tempfile.TemporaryDirectory() as base:
            target=Path(base)/'annotation.jar'
            with patch.object(workflow.urllib.request,'urlopen',side_effect=[TimeoutError('controlled download timeout'),io.BytesIO(raw)]) as request:
                workflow.download_annotation('https://dl.google.com/controlled.jar',target,digest)
            self.assertEqual(request.call_count,2);self.assertEqual(target.read_bytes(),raw)
            with patch.object(workflow.urllib.request,'urlopen') as request:
                workflow.download_annotation('https://dl.google.com/controlled.jar',target,digest)
                request.assert_not_called()
    def test_mismatched_body_never_replaces_previous_dependency(self):
        with tempfile.TemporaryDirectory() as base:
            target=Path(base)/'annotation.jar';target.write_bytes(b'previous')
            with patch.object(workflow.urllib.request,'urlopen',side_effect=lambda *a,**k:io.BytesIO(b'wrong')):
                with self.assertRaises(ValueError):workflow.download_annotation('https://dl.google.com/controlled.jar',target,'0'*64)
            self.assertEqual(target.read_bytes(),b'previous');self.assertFalse(target.with_suffix('.download').exists())

if __name__=='__main__':unittest.main()
