#!/usr/bin/env python3
"""Small synthetic controls for the posthoc evidence extraction boundary."""
import hashlib
import importlib.util
import io
import json
from pathlib import Path
import stat
import tarfile
import tempfile
import unittest
from unittest.mock import patch
import warnings
import zipfile

SPEC = importlib.util.spec_from_file_location('frozen_input_analysis', Path(__file__).resolve().parents[1] / 'tools/gecko/analyze_frozen_input_artifacts.py')
M = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(M)


class ExtractionControls(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix='input-analysis-control-')
        self.root = Path(self.temporary.name)

    def tearDown(self):
        self.temporary.cleanup()

    def zip(self, rows):
        target = self.root / 'input.zip'
        with warnings.catch_warnings():
            warnings.simplefilter('ignore', UserWarning)
            with zipfile.ZipFile(target, 'w') as archive:
                for name, value in rows:
                    archive.writestr(name, value)
        return target

    def reject_zip(self, rows):
        with self.assertRaises((ValueError, OSError)):
            M.safe_zip(self.zip(rows), self.root / 'out')
        self.assertFalse((self.root / 'escape').exists())

    def phase(self, *, path='work/gecko-integration/gecko-performance-results.json',
              sha=None, source=None, extra=False, special=False, duplicate=False):
        data = b'{"sourceCommit":"synthetic-control"}\n'
        manifest = dict(schema=1, kind='phase', phase='editing', **(source or M.SOURCE),
                        files=[dict(path=path, bytes=len(data), sha256=sha or hashlib.sha256(data).hexdigest())])
        raw = json.dumps(manifest).encode()
        target = self.root / 'phase.tar.gz'
        with tarfile.open(target, 'w:gz') as archive:
            member = tarfile.TarInfo('_ci_bundle.json'); member.size = len(raw)
            archive.addfile(member, io.BytesIO(raw))
            member = tarfile.TarInfo(path); member.size = len(data)
            if special:
                member.type = tarfile.SYMTYPE; member.linkname = '/tmp/escape'; member.size = 0
                archive.addfile(member)
            else:
                archive.addfile(member, io.BytesIO(data))
            if duplicate:
                archive.addfile(member, io.BytesIO(data))
            if extra:
                member = tarfile.TarInfo('undeclared.json'); member.size = 0
                archive.addfile(member, io.BytesIO())
        return target

    def extract_phase(self, archive):
        return M.extract_phase(archive, self.root / 'phase', self.root / 'expanded.tar')

    def test_valid_zip_preserves_bytes(self):
        archive = self.zip([('one.json', b'{"raw":true}'), ('nested/file.csv', b'a,b\n1,2\n')])
        before = M.file_identity(archive)
        M.safe_zip(archive, self.root / 'out')
        self.assertEqual((self.root / 'out/nested/file.csv').read_bytes(), b'a,b\n1,2\n')
        self.assertEqual(before, M.file_identity(archive))

    def test_zip_traversal(self):
        self.reject_zip([('../escape', b'x')])

    def test_zip_absolute_path(self):
        self.reject_zip([('/tmp/escape', b'x')])

    def test_zip_noncanonical_path(self):
        self.reject_zip([('a/./file', b'x')])

    def test_zip_duplicate_path(self):
        self.reject_zip([('same', b'a'), ('same', b'b')])

    def test_zip_symlink(self):
        member = zipfile.ZipInfo('link'); member.create_system = 3
        member.external_attr = (stat.S_IFLNK | 0o777) << 16
        self.reject_zip([(member, b'/tmp/escape')])

    def test_zip_oversized_expansion(self):
        archive = self.zip([('file', b'x' * 100)])
        with patch.object(M, 'MAX_TOTAL', 50), self.assertRaises(ValueError):
            M.safe_zip(archive, self.root / 'out')
        self.assertFalse((self.root / 'out').exists())

    def test_valid_phase_verifies_manifest_preserves_bytes(self):
        archive = self.phase()
        before = M.file_identity(archive)
        manifest = self.extract_phase(archive)
        self.assertEqual(M.SOURCE['runId'], manifest['runId'])
        self.assertEqual(before, M.file_identity(archive))
        self.assertEqual((self.root / 'phase/work/gecko-integration/gecko-performance-results.json').read_bytes(),
                         b'{"sourceCommit":"synthetic-control"}\n')

    def test_phase_hash_mismatch(self):
        with self.assertRaises(ValueError):
            self.extract_phase(self.phase(sha='0' * 64))
        self.assertFalse((self.root / 'phase').exists())

    def test_phase_wrong_source(self):
        with self.assertRaises(ValueError):
            self.extract_phase(self.phase(source=dict(M.SOURCE, runId='40720430996')))

    def test_phase_traversal(self):
        with self.assertRaises(ValueError):
            self.extract_phase(self.phase(path='../escape'))
        self.assertFalse((self.root / 'escape').exists())

    def test_phase_undeclared_member(self):
        with self.assertRaises(ValueError):
            self.extract_phase(self.phase(extra=True))

    def test_phase_duplicate_member(self):
        with self.assertRaises(ValueError):
            self.extract_phase(self.phase(duplicate=True))

    def test_phase_symlink(self):
        with self.assertRaises(ValueError):
            self.extract_phase(self.phase(special=True))

    def test_phase_gzip_expansion_bound(self):
        archive = self.phase()
        with patch.object(M, 'MAX_TOTAL', -16 * 1024 * 1024 + 32), self.assertRaises(ValueError):
            self.extract_phase(archive)
        self.assertFalse((self.root / 'phase').exists())

    def test_config_exact_bytes_and_sha(self):
        raw=b'duration_ms: 240000\n'
        path=self.root/'perfetto-config.pbtxt'; path.write_bytes(raw)
        record=dict(configSource='stdin',configFile=path.name,configBytes=len(raw),configSha256=hashlib.sha256(raw).hexdigest())
        M.validate_config(self.root,record)
        path.write_bytes(b'duration_ms: 1\n')
        with self.assertRaisesRegex(ValueError,'config bytes or SHA differs'):
            M.validate_config(self.root,record)

    def test_failed_original_status_does_not_block_posthoc_analysis(self):
        original=self.root/'original'; original.mkdir()
        phase=self.root/'phase/work/gecko-integration'; phase.mkdir(parents=True)
        config=b'duration_ms: 240000\n'; (original/'perfetto-config.pbtxt').write_bytes(config)
        trace=b'raw'; (original/'android.perfetto-trace').write_bytes(trace)
        run=dict(M.SOURCE, sample='2',status='incomplete',diagnosticOnly=True,applicationAcceptance=False,
                 physicalPhoneAcceptance=False,workloadInvocationCount=1,configSource='stdin',
                 configFile='perfetto-config.pbtxt',configBytes=len(config),configSha256=hashlib.sha256(config).hexdigest(),
                 traceBytes=len(trace),traceSha256=hashlib.sha256(trace).hexdigest())
        M.dump(original/'diagnostic-run.json',run)
        M.dump(original/'diagnostic-scope.json',dict(M.SOURCE,sample='2',status='failed',diagnosticOnly=True,
               applicationAcceptance=False,releaseAcceptance=False))
        receipt=dict(M.SOURCE,status='failed',error='synthetic process failure',buildIdentity=M.SOURCE)
        receipt_path=phase/'native-input-synthetic-current-scroll.json'; M.dump(receipt_path,receipt)
        M.dump(phase/'gecko-performance-results.json',dict(sourceCommit=M.SOURCE['sourceCommit'],status='failed',
               nativeInputDriver=dict(receipts=[dict(file=receipt_path.name,sha256=M.sha(receipt_path))])))
        checked,_,receipts=M.validate_originals(original,self.root/'phase','2')
        self.assertEqual(checked['status'],'incomplete')
        self.assertEqual(receipts,[receipt_path])

    def test_config_stdin_binding_required(self):
        record=dict(configSource='remote-file',configFile='perfetto-config.pbtxt',configBytes=1,configSha256='0'*64)
        with self.assertRaisesRegex(ValueError,'stdin config binding required'):
            M.validate_config(self.root,record)

    def test_frozen_metadata_requires_explicit_boolean_flags(self):
        path = Path(__file__).resolve().parents[1] / 'tools/gecko/input_analysis_bindings.json'
        value = M.read_json(path)
        value['status'] = 'frozen-final-original-artifact-metadata'
        value.pop('releaseAcceptance')
        target = self.root / 'bindings.json'; target.write_text(json.dumps(value))
        with self.assertRaisesRegex(ValueError, 'Every binding diagnostic flag'):
            M.bindings_for(target, '1')

    def test_pending_metadata_has_no_fallback(self):
        path = Path(__file__).resolve().parents[1] / 'tools/gecko/input_analysis_bindings.json'
        value = M.read_json(path)
        value['status'] = 'pending-final-original-artifact-metadata'
        target = self.root / 'bindings.json'; target.write_text(json.dumps(value))
        with self.assertRaisesRegex(ValueError, 'Final frozen bindings required; no fallback'):
            M.bindings_for(target, '1')


if __name__ == '__main__':
    unittest.main()
