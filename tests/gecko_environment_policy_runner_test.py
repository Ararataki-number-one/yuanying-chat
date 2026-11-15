"""Runner transport controls only; this file does not execute Android/Gecko."""
import copy
import importlib.util
import json
from pathlib import Path
import shlex
import socket
import subprocess
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch
import xml.etree.ElementTree as ET

import browser_fingerprint_evidence_test as schema_fixture

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location('gecko_environment_runner', ROOT / 'tools/browser/run_gecko_environment_policy_integration.py')
runner = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(runner)
SOURCE, TREE, NONCE = 'a' * 40, 'b' * 40, 'c' * 32


class GeckoEnvironmentRunnerTests(unittest.TestCase):
    def identity(self):
        return schema_fixture.FingerprintEvidenceTests().document()['expectedBuildIdentity']

    def activity(self):
        return dict(fixtureType=runner.FIXTURE_TYPE, engine='gecko', status='running',
                    sourceCommit=SOURCE, sourceTree=TREE, runNonce=NONCE,
                    buildIdentity=self.identity())

    def read(self, value):
        return runner.read_activity(json.dumps(value).encode(), NONCE, SOURCE, TREE, self.identity())

    def test_launch_is_source_bound_to_actual_registered_component_and_provider(self):
        command = runner.activity_start_args(NONCE, SOURCE, 'd' * 64, 'e' * 64)
        self.assertEqual(command[0], 'shell')
        tokens = shlex.split(command[1])
        self.assertEqual(tokens[:5], ['am', 'start', '-W', '-n', runner.ACTIVITY])
        self.assertEqual(tokens[tokens.index('fixtureEngine') + 1], 'gecko')
        ns = '{http://schemas.android.com/apk/res/android}'
        application = ET.parse(ROOT / 'tests/gecko/AndroidManifest.xml').getroot().find('application')
        self.assertEqual(sum(row.get(ns + 'name') == runner.ACTIVITY.split('/')[1] for row in application.findall('activity')), 1)
        authority = runner.REPORT_URI.split('/')[2]
        self.assertEqual(sum(row.get(ns + 'authorities') == authority and row.get(ns + 'name') == 'local.pocketchat.GeckoEnvironmentPolicyProvider' for row in application.findall('provider')), 1)

    def test_invalid_source_or_certificate_launch_never_reaches_shell(self):
        valid = [NONCE, SOURCE, 'd' * 64, 'e' * 64]
        for index in range(4):
            for bad in ('', 'not-a-hash; id', valid[index].upper(), valid[index] + '0'):
                with self.subTest(index=index, bad=bad):
                    changed = list(valid)
                    changed[index] = bad
                    with self.assertRaises(ValueError):
                        runner.activity_start_args(*changed)

    def test_poll_ignores_missing_and_other_invocation_but_accepts_exact_current(self):
        for raw in (b'', b'not-json', b'null', b'[]', b'{}'):
            self.assertIsNone(runner.read_activity(raw, NONCE, SOURCE, TREE, self.identity()))
        changed = self.activity()
        changed['runNonce'] = 'f' * 32
        self.assertIsNone(self.read(changed))
        self.assertEqual(self.read(self.activity()), self.activity())

    def test_current_invocation_rejects_foreign_source_tree_engine_apk_sdk(self):
        changes = [lambda row: row.update(sourceCommit='f' * 40),
                   lambda row: row.update(sourceTree='f' * 40),
                   lambda row: row.update(engine='chromium'),
                   lambda row: row.update(fixtureType='other'),
                   lambda row: row['buildIdentity'].update(apkSha256='f' * 64),
                   lambda row: row['buildIdentity']['sdkBuildIdentity'].update(runAttempt=2)]
        for change in changes:
            value = self.activity()
            change(value)
            with self.subTest(value=value), self.assertRaises(ValueError):
                self.read(value)
        with self.assertRaises(ValueError):
            runner.read_activity(b'x' * (runner.MAX_ACTIVITY_BYTES + 1), NONCE, SOURCE, TREE, self.identity())
        raw = json.dumps(self.activity()).encode()
        for malformed in (raw[:-1] + b',"status":"passed"}', raw[:-1] + b',"nonFinite":NaN}'):
            with self.subTest(malformed=malformed[:80]), self.assertRaises(ValueError):
                runner.read_activity(malformed, NONCE, SOURCE, TREE, self.identity())

    def test_bound_report_is_atomically_written_and_temporary_file_removed(self):
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / runner.REPORT_NAME
            runner.write_report(target, {'status': 'running'})
            runner.write_report(target, {'status': 'failed', 'failure': 'synthetic fixture error'})
            self.assertEqual(json.loads(target.read_bytes())['status'], 'failed')
            self.assertFalse(target.with_suffix('.tmp').exists())
            with self.assertRaises(ValueError):
                runner.write_report(target, {'oversize': 'x' * (4 * 1024 * 1024)})
            self.assertEqual(json.loads(target.read_bytes())['status'], 'failed')

    def test_failure_summary_exports_only_bounded_synthetic_diagnostic_fields(self):
        value = dict(self.activity(), privateKey='never export', pageText='never export',
                     stage='native-context', nativeEvents=[{'kind': 'page-stop-false'}],
                     lastPageObservation=dict(page=dict(nativeTimeZone={'timeZone': 'UTC'}, inputText='never export'), frames=[], workers={}))
        summary = runner.failure_summary(value)
        self.assertNotIn('privateKey', summary)
        self.assertNotIn('pageText', summary)
        self.assertNotIn('buildIdentity', summary)
        self.assertEqual(summary['nativeEvents'], [{'kind': 'page-stop-false'}])
        self.assertEqual(summary['lastPageObservation']['page'], {'nativeTimeZone': {'timeZone': 'UTC'}})
        self.assertEqual(runner.failure_summary(None), {'stage': 'unavailable'})

    def test_failure_summary_preserves_bounded_stale_contract_evidence_only(self):
        proof = dict(actualStoreRecordAttempt=True, oldRecordRejected=True,
                     oldReceiptEmpty=False, oldToken='d' * 64, privateKey='never export')
        value = dict(self.activity(), staleTicketProof=proof,
                     staleRevisionProof=dict(proof, actualStoreReceiptAttempt=True,
                                             oldReceiptRejected=True, newRevision=3,
                                             newToken='x' * 161))
        summary = runner.failure_summary(value)
        self.assertEqual(summary['staleTicketProof']['oldReceiptEmpty'], False)
        self.assertEqual(summary['staleRevisionProof']['oldReceiptRejected'], True)
        for name in ('staleTicketProof', 'staleRevisionProof'):
            self.assertNotIn('privateKey', summary[name])
        self.assertNotIn('newToken', summary['staleRevisionProof'])

    def test_source_inventory_binds_every_required_producer_and_real_app_source(self):
        paths = runner.source_inputs()
        self.assertEqual(len(paths), len(set(paths)))
        self.assertTrue(all(path.is_file() and path.is_relative_to(ROOT) for path in paths))
        self.assertTrue({ROOT / name for name in runner.SOURCE_INPUTS} <= set(paths))
        self.assertIn(ROOT / 'app/src/main/java/org/mozilla/geckoview/AppSessionIdentity.java', paths)
        self.assertIn(ROOT / 'app/src/main/assets/gecko/native-timezone-api.js', paths)

    def test_failed_android_boundary_keeps_original_failure_and_real_transport_diagnostic(self):
        identity=self.identity();activity=dict(self.activity(),status='failed',stage='startup',failure='controlled startup failure')
        original_run=subprocess.run;servers=[];certificates=[];actions=[]
        real_server=runner.WorkerFixtureServer;real_certificates=runner.EphemeralCertificates
        def make_server(*args,**kwargs):
            value=real_server(*args,**kwargs);servers.append(value);return value
        def make_certificates():
            value=real_certificates();certificates.append(value);return value
        class CaBoundary:
            def __init__(self,*args):self.receipt={'scope':'modeled Android CA boundary'}
            def install(self):actions.append('ca-installed')
            def remove(self):actions.append('ca-removed')
        def run(command,**kwargs):
            if command[0]!='adb':return original_run(command,**kwargs)
            words=command[3:];out=b''
            if words==['shell','getprop','ro.kernel.qemu']:out=b'1\n'
            elif words==['shell','getprop','persist.sys.timezone']:out=b'UTC\n'
            elif words==['shell','id','-u']:out=b'2000\n'
            elif words==['shell','pm','clear','local.pocketchat.test']:out=b'Success\n'
            elif words==['reverse','--list']:out=b''
            elif words[:2]==['reverse','--remove']:actions.append('reverse-removed')
            elif words[:1]==['reverse']:actions.append('reverse-installed')
            elif words==['shell','am','force-stop','local.pocketchat.test']:actions.append('app-stopped')
            elif words[:2]==['exec-out','content']:
                out=json.dumps(identity if words[-1].endswith('/build-identity') else activity).encode()
            elif len(words)==2 and words[0]=='shell' and shlex.split(words[1])[:2]==['am','start']:
                with socket.create_connection(('127.0.0.1',servers[0].port),timeout=3) as connection:
                    connection.sendall(('GET /__evidence?engine=gecko&nonce='+NONCE+'&source='+SOURCE+' HTTP/1.1\r\nHost: private-host.invalid\r\n\r\n').encode())
                    self.assertEqual(connection.recv(1),b'')
            else:raise AssertionError('Unexpected modeled adb command: '+repr(words))
            return subprocess.CompletedProcess(command,0,out,b'')
        def check_output(command,**kwargs):
            if command==['git','status','--porcelain']:return ''
            if command==['git','rev-parse','HEAD']:return SOURCE+'\n'
            if command==['git','rev-parse','HEAD^{tree}']:return TREE+'\n'
            # This existing synthetic build-identity fixture models the legacy
            # official SDK; it has no selected-source derived SDK manifest.
            if command==['git','show',SOURCE+':third-party/sdk/geckoview-157.0.1-editable-selection.json']:
                raise subprocess.CalledProcessError(128,command,stderr=b'modeled source has no derived manifest')
            raise AssertionError(command)
        with tempfile.TemporaryDirectory() as directory:
            with patch.object(sys,'argv',['runner','--output',directory]),patch.object(runner.subprocess,'run',run),patch.object(runner.subprocess,'check_output',check_output),patch.object(runner,'expected_build',return_value=identity),patch.object(runner.uuid,'uuid4',return_value=SimpleNamespace(hex=NONCE)),patch.object(runner,'WorkerFixtureServer',make_server),patch.object(runner,'EphemeralCertificates',make_certificates),patch.object(runner,'AndroidUserCa',CaBoundary):
                with self.assertRaisesRegex(AssertionError,'Gecko environment fixture failed'):
                    runner.main()
            report=json.loads((Path(directory)/runner.REPORT_NAME).read_text())
            diagnostic=json.loads((Path(directory)/runner.TRANSPORT_DIAGNOSTIC_NAME).read_text())
            self.assertEqual(report['status'],'failed');self.assertEqual(report['activity']['failure'],'controlled startup failure')
            self.assertTrue(all(report['cleanup'].values()));self.assertIn('ca-removed',actions);self.assertIn('reverse-removed',actions)
            self.assertFalse(certificates[0].directory.exists());self.assertTrue(diagnostic['collectorQuiesced'])
            self.assertEqual(diagnostic['rejected'],1);self.assertEqual(diagnostic['events'][0]['guardCode'],'control-authority')
            self.assertTrue(diagnostic['diagnosticOnly']);self.assertFalse(diagnostic['qualificationEvidence'])
            self.assertNotIn('private-host',json.dumps(diagnostic));self.assertNotIn('events',report['activity']['fixture'])


if __name__ == '__main__':
    unittest.main(verbosity=2)
