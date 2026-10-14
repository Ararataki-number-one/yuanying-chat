"""Counterfeit wrapper controls only; no adb, Android, SDK build or performance acceptance."""
import contextlib
import io
import hashlib
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
import zipfile

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location('caret_bound_performance', ROOT / 'tests/gecko/run_caret_bound_performance.py')
W = importlib.util.module_from_spec(SPEC); SPEC.loader.exec_module(W)
SOURCE, TREE = 'a' * 40, 'b' * 40


class BoundPerformanceControls(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name); self.out = self.root / 'work/gecko-integration'
        self.out.mkdir(parents=True)
        self.runner = self.root / W.RUNNER; self.runner.parent.mkdir(parents=True)
        self.runner.write_bytes(b'original runner bytes\n')
        self.activity = self.root / W.ACTIVITY; self.activity.write_bytes(b'original activity bytes\n')
        self.sdk_receipt = self.root / 'sdk.json'; self.sdk_receipt.write_text('{"syntheticUnitFixture":true}\n')
        self.sdk_hash = hashlib.sha256(self.sdk_receipt.read_bytes()).hexdigest()
        self.sdk = dict(sourceCommit=SOURCE, sourceTree=TREE, runId='1234', runAttempt='1', sdkManifestSha256='c'*64)
        self.embedded = dict(schema=1, sourceCommit=SOURCE, runId='1234', runAttempt='1', sdkReceiptSha256=self.sdk_hash,
                             sdkAarSha256='d'*64, sdkClassJarSha256='e'*64, sdkEditableClassSha256='f'*64,
                             sdkManifestSha256='c'*64, normalMode=True, sdkObserverIncluded=False)
        self.apk = self.root / 'integration.apk'
        self.stamp = dict(schema=1, sourceCommit=SOURCE, sourceTree=TREE, dirtySource=False, version='2.0.0', versionCode=53)
        with zipfile.ZipFile(self.apk, 'w') as archive:
            archive.writestr(W.STAMP, json.dumps(self.stamp))
        self.apk_hash = W.digest(self.apk)
        self.build = dict(self.embedded, integrationApkSha256=self.apk_hash)
        self.build_receipt = self.root / 'build.json'; self.build_receipt.write_text(json.dumps(self.build))
        self.asset = dict(schema=1, sourceCommit=SOURCE, sourceTree=TREE, runId='1234', runAttempt='1',
                          **{name: 'c'*64 for name in W.sdk_contract.SDK_FIELDS})
        self.asset.update(sdkBuildReceiptSha256=self.sdk_hash)
        self.argv = ['run_caret_bound_performance.py', '--adb', 'synthetic-adb', '--root', str(self.root), '--out', str(self.out),
                     '--build-receipt', str(self.build_receipt), '--sdk-receipt', str(self.sdk_receipt),
                     '--sdk-aar', str(self.root/'derived.aar'), '--official-sdk-aar', str(self.root/'official.aar'),
                     '--integration-apk', str(self.apk)]
        self.raw = b'{"status":"passed","actualAndroidExecution":true,"sourceCommit":"' + SOURCE.encode() + b'"}\n'
        self.returncode = 0; self.invocations = []; self.installed_reads = 0; self.change_after = False

    def output(self, command, **kwargs):
        if command[:3] == ['git', 'rev-parse', 'HEAD']:
            return SOURCE + '\n'
        if command[:2] == ['git', 'rev-parse']:
            return TREE + '\n'
        if command[:3] == ['git', 'diff', '--name-only']:
            return ''
        if command[:2] == ['git', 'show']:
            name = command[2].split(':', 1)[1]
            return b'original runner bytes\n' if name == W.RUNNER else b'original activity bytes\n'
        if command[-4:] == ['shell', 'pm', 'path', W.PACKAGE]:
            return 'package:/data/app/controlled/base.apk\n'
        raise AssertionError(command)

    def run_once(self, command, **kwargs):
        if command[3:] == ['exec-out','cat','/data/app/controlled/base.apk']:
            self.installed_reads += 1
            data=self.apk.read_bytes()+(b'changed' if self.change_after and self.installed_reads == 2 else b'')
            kwargs['stdout'].write(data)
            return subprocess.CompletedProcess(command,0,stderr=b'')
        self.invocations.append(command)
        (self.out/'gecko-performance-results.json').write_bytes(self.raw)
        return subprocess.CompletedProcess(command, self.returncode)

    def invoke(self):
        with contextlib.redirect_stdout(io.StringIO()), patch.object(sys, 'argv', self.argv), patch.object(W, 'validate_sdk_receipt', return_value=self.sdk), \
             patch.object(W, 'embedded_identity', return_value=self.embedded), \
             patch.object(W, 'audit_apk', return_value={'syntheticAudit': True}), \
             patch.object(W.sdk_contract, 'sdk_from_apk', return_value=self.asset), \
             patch.object(W.subprocess, 'check_output', side_effect=self.output), \
             patch.object(W.subprocess, 'run', side_effect=self.run_once):
            W.main()

    def test_one_original_call_preserves_exact_raw_bytes(self):
        self.invoke()
        self.assertEqual(len(self.invocations), 1)
        self.assertEqual(self.invocations[0][1:], [str(self.runner), '--adb', 'synthetic-adb', '--serial', 'emulator-5554'])
        self.assertEqual((self.out/'gecko-performance-results.json').read_bytes(), self.raw)
        sidecar = json.loads((self.out/'gecko-performance-build-identity.json').read_bytes())
        self.assertEqual(sidecar['rawReportSha256'], hashlib.sha256(self.raw).hexdigest())
        self.assertEqual(sidecar['before'], sidecar['after'])
        self.assertEqual(sidecar['invocationCount'], 1)
        self.assertEqual(sidecar['invocationRepositoryRoot'], str(self.root))
        self.assertEqual(self.installed_reads, 2)
        self.assertEqual(self.runner.read_bytes(), b'original runner bytes\n')

    def test_failed_original_is_retained_without_retry_or_waiver(self):
        self.returncode = 1; self.raw = self.raw.replace(b'"passed"', b'"failed"')
        with self.assertRaises(ValueError):
            self.invoke()
        self.assertEqual(len(self.invocations), 1)
        self.assertEqual((self.out/'gecko-performance-results.json').read_bytes(), self.raw)
        sidecar = json.loads((self.out/'gecko-performance-build-identity.json').read_bytes())
        self.assertEqual(sidecar['runnerExitCode'], 1)

    def test_existing_report_prevents_a_second_invocation(self):
        (self.out/'gecko-performance-results.json').write_bytes(self.raw)
        with self.assertRaises(ValueError):
            self.invoke()
        self.assertEqual(self.invocations, [])
        self.assertEqual(self.installed_reads, 0)

    def test_protected_runner_mutation_prevents_invocation(self):
        self.runner.write_bytes(b'changed original runner')
        with self.assertRaises(ValueError):
            self.invoke()
        self.assertEqual(self.invocations, [])

    def test_changed_installed_apk_prevents_sidecar_acceptance(self):
        self.change_after = True
        with self.assertRaises(ValueError):
            self.invoke()
        self.assertEqual(len(self.invocations), 1)
        self.assertEqual((self.out/'gecko-performance-results.json').read_bytes(), self.raw)
        self.assertFalse((self.out/'gecko-performance-build-identity.json').exists())


if __name__ == '__main__':
    unittest.main()
