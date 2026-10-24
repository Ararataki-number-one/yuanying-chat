"""Exercise the real additional-sample staging path; no Android execution."""
import hashlib
import importlib.util
import json
import pathlib
import sys
import tempfile
import types
import unittest
from unittest.mock import patch

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools/gecko'))
SPEC = importlib.util.spec_from_file_location('scroll_stage', ROOT / 'tools/gecko/key_order_samples.py')
STAGE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(STAGE)


class ScrollStageTest(unittest.TestCase):
    def stage(self, present):
        with tempfile.TemporaryDirectory() as temporary:
            root = pathlib.Path(temporary); source = root / 'input'; source.mkdir()
            payload = b'{\r\n  "status": "failed", "label": "\xe6\xbb\x9a\xe5\x8a\xa8"\r\n}\n'
            names = (*STAGE.SCROLL_DIAGNOSTICS, 'native-input-driver-signature-api.json',
                     'native-input-driver-signature-api-stdout.log', 'native-input-driver-signature-api-stderr.log')
            if present:
                for name in names:
                    (source / name).write_bytes(payload)
            args = types.SimpleNamespace(input=source, out=root / 'out', sample='2')
            with patch.object(STAGE, 'verify_caret_evidence', side_effect=ValueError('original workload failed')), \
                 patch.object(STAGE.subprocess, 'check_output', return_value='a' * 40 + '\n'), \
                 patch.dict(STAGE.os.environ, GITHUB_RUN_ID='123', GITHUB_RUN_ATTEMPT='1'):
                with self.assertRaisesRegex(AssertionError, 'original workload failed'):
                    STAGE.stage(args)
            receipt = json.loads((args.out / 'sample-receipt.json').read_bytes())
            self.assertEqual(receipt['status'], 'failed')
            self.assertFalse(receipt['workloadRerun'])
            for name in names:
                self.assertEqual((args.out / name).exists(), present)
                self.assertEqual(name in receipt['files'], present)
                if present:
                    self.assertEqual((args.out / name).read_bytes(), payload)
                    self.assertEqual(receipt['files'][name], hashlib.sha256(payload).hexdigest())

    def test_failed_original_bytes_retained_and_indexed(self):
        self.stage(True)

    def test_absent_originals_not_fabricated(self):
        self.stage(False)


if __name__ == '__main__':
    unittest.main()
