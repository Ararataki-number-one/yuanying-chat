"""Focused original-signing delivery and public update gate controls."""
import json
from pathlib import Path
from types import SimpleNamespace
import tempfile
import unittest
from unittest.mock import patch
from zipfile import ZIP_DEFLATED, ZIP_STORED, ZipFile

import chromium_release_publication as delivery


class PublicationTest(unittest.TestCase):
    def setUp(self):
        folder = tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        self.directory = Path(folder.name)

    def test_signing_metadata_is_ignored_but_signed_payload_changes_are_rejected(self):
        def make(name, data, compression, extra_signature=False):
            path = self.directory / name
            with ZipFile(path, 'w', compression=compression) as archive:
                archive.writestr('AndroidManifest.xml', b'manifest')
                archive.writestr('assets/icu.dat', data)
                if extra_signature:
                    archive.writestr('META-INF/CERT.RSA', b'synthetic signing envelope')
            return delivery.apk_contents(path)
        unsigned = make('unsigned.apk', b'icu', ZIP_STORED)
        self.assertEqual(unsigned, make('signed.apk', b'icu', ZIP_STORED, True))
        for payload, compression in ((b'changed icu', ZIP_STORED), (b'icu', ZIP_DEFLATED)):
            self.assertNotEqual(unsigned, make('changed.apk', payload, compression, True))

    def test_android_gate_rejects_prototype_wrong_source_missing_render_and_wrong_types(self):
        release = {'versionCode': 115}
        build = {'sourceCommit': 'a' * 40, 'sourceTree': 'b' * 40}
        path = self.directory / delivery.RUNTIME_REPORT
        good = dict(build, versionCode=115, actualAndroidExecution=True, status='passed', package='local.pocketchat',
                    sourceDirty=False, actualOnlineSignedMetadataDownload=False, actualSystemInstallerConsent=False,
                    testScope='combined-debug-candidate-local-install-and-renderer', sdk=33, abi='x86_64',
                    baseSha256='e' * 64, featureSha256='f' * 64, rendererTranscriptSha256='1' * 64,
                    chromiumVersion='156.0.8078.96', nativeRendererCount=1, **dict.fromkeys(delivery.RUNTIME_CHECKS, True))
        proxy = dict(handshakes=1, pages=1, heldConnectionsClosed=1, privateTrapAccepted=0)
        identity = {key: good[key] for key in ('sourceCommit', 'sourceTree', 'versionCode', 'sdk', 'abi')}
        integration = dict(identity, package='local.pocketchat.test', androidExecution=True, noSystemWebViewProvider=True,
                           baseSha256='9' * 64, featureSha256='8' * 64, transcriptSha256='7' * 64)
        vpn = dict(integration, scope=delivery.INTEGRATION_SCOPE['vpn'],
                   vpnGeneration=1, vpnDestinationPort=58001, androidVpnConsentVerified=False,
                   **dict.fromkeys(delivery.INTEGRATION_CHECKS['vpn'], True))
        internal = dict(integration, scope=delivery.INTEGRATION_SCOPE['internal'], internalCoreSha256='6' * 64,
                        internalAuthorizedCircuits=2, internalHeldConnectionsClosed=1,
                        **dict.fromkeys(delivery.INTEGRATION_CHECKS['internal'], True))
        good.update(tlsFixtureVerified=True, originTlsVerified=False,
                    protectedHttpProxy=proxy, protectedSocksProxy=proxy, protectedHttpsProxy=dict(proxy, tlsHandshakes=1),
                    integrationRoutes={'vpn': vpn, 'internal': internal})
        path.write_text(json.dumps(good))
        self.assertEqual(delivery.runtime_summary(path, release, build), good)
        for changes in ({'package': 'local.prototype'}, {'sourceCommit': 'c' * 40}, {'nativeRenderer': False},
                        {'actualAndroidExecution': 1}, {'sourceDirty': True}, {'appendInstall': False}, {'featureSha256': ''},
                        {'actualSystemInstallerConsent': True}, {'nativeRendererCount': 0}, {'sdk': 32},
                        {'tlsFixtureVerified': False}, {'protectedHttpsProxy': proxy},
                        {'integrationRoutes': {'vpn': vpn}},
                        {'integrationRoutes': {'vpn': dict(vpn, vpnDescriptorClosed=False), 'internal': internal}}):
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                path.write_text(json.dumps(dict(good, **changes)))
                delivery.runtime_summary(path, release, build)

    def test_android_transcripts_cannot_transfer_another_artifact_or_claim_consent(self):
        apk = SimpleNamespace(nonce='a' * 32, base_sha='1' * 64, feature_sha='2' * 64, core_sha='3' * 64)
        debug = dict(sourceCommit='4' * 40, sourceTree='5' * 40, versionCode=115, sdk=33, abi='x86_64')
        identity = {k: str(v) for k, v in debug.items()}
        fields = dict(identity, runNonce=apk.nonce, package='local.pocketchat.test',
                      scope=delivery.INTEGRATION_SCOPE['vpn'], baseSha256=apk.base_sha, featureSha256=apk.feature_sha,
                      androidExecution='true', noSystemWebViewProvider='true', androidVpnConsentVerified='false',
                      vpnGeneration='1', vpnDestinationPort='52080', **dict.fromkeys(delivery.INTEGRATION_CHECKS['vpn'], 'true'))
        path = self.directory / 'android-instrumentation.txt'
        def encode(values, code='-1'):
            path.write_text('\n'.join(f'INSTRUMENTATION_RESULT: {k}={v}' for k, v in values.items()) +
                            f'\nINSTRUMENTATION_CODE: {code}\n')
        encode(fields)
        self.assertIs(delivery.parse_route_transcript(path, 'vpn', debug, apk)['vpnDescriptorClosed'], True)
        for changes in ({'sourceTree': '6' * 40}, {'runNonce': 'b' * 32}, {'featureSha256': '7' * 64},
                        {'vpnDescriptorClosed': 'false'}, {'androidVpnConsentVerified': 'true'}):
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                encode(dict(fields, **changes))
                delivery.parse_route_transcript(path, 'vpn', debug, apk)

    def test_bounded_signing_tail_roundtrip_refuses_wrong_tail_and_full_signed_hash(self):
        def blocks(*_args):
            yield from (b'common apk', b' payload unsigned tail')
        signed = self.directory / 'signed.apk'
        signed.write_bytes(b'common apk payload original signed tail')
        build = {'apks': {'chromium-master.apk': {'bytes': len(b'common apk payload unsigned tail')}}}
        stage = self.directory / 'release'
        stage.mkdir()
        with patch.object(delivery, 'unsigned_feature_blocks', side_effect=blocks):
            transport = delivery.signature_tail(signed, stage, build, 'a' * 40, [])
            self.assertEqual(transport['prefixBytes'], len(b'common apk payload '))
            target = stage / signed.name
            record = {'apkTransport': transport, 'files': [delivery.identity(signed)]}
            delivery.restore_feature(record, target, build, 'a' * 40, [])
            self.assertEqual(target.read_bytes(), signed.read_bytes())
            target.unlink()
            (stage / delivery.SIGNED_TAIL).write_bytes(b'tampered')
            with self.assertRaisesRegex(ValueError, 'signed tail'):
                delivery.restore_feature(record, target, build, 'a' * 40, [])
            self.assertFalse(target.exists())
        with patch.object(delivery, 'MAX_TAIL_BYTES', 4), patch.object(delivery, 'unsigned_feature_blocks', side_effect=blocks):
            with self.assertRaisesRegex(ValueError, 'bounded Chromium signature tail'):
                delivery.signature_tail(signed, stage, build, 'a' * 40, [])

    def test_feature_chunk_order_sizes_and_hashes_remain_exact(self):
        raw = b'immutable unsigned bytes'
        feature = self.directory / 'chromium-master.apk'
        feature.write_bytes(raw)
        proof = {'version': '2.1.13', 'apks': {'chromium-master.apk': dict(delivery.identity(feature), contentsSha256='5' * 64)}}
        with patch.object(delivery, 'CHUNK_BYTES', 8):
            parts = delivery.write_feature_chunks(proof, feature, self.directory)
            self.assertEqual([item['bytes'] for item in parts], [8, 8, 8])
            fixture = {(self.directory / part['file']).name: (self.directory / part['file']).read_bytes() for part in parts}
            with patch.object(delivery, 'git', side_effect=lambda _, _size, object_name: str(len(fixture[object_name.split(':')[1]]))), \
                    patch.object(delivery.subprocess, 'check_output', side_effect=lambda cmd: fixture[cmd[-1].split(':')[1]]):
                self.assertEqual(b''.join(delivery.unsigned_feature_blocks(proof, 'a' * 40, parts)), raw)
                fixture[parts[0]['file']] = b'z' * 8
                with self.assertRaisesRegex(ValueError, 'Immutable Chromium part bytes differ'):
                    list(delivery.unsigned_feature_blocks(proof, 'a' * 40, parts))
            with self.assertRaisesRegex(ValueError, 'part identity'):
                delivery.validate_feature_chunks(proof, list(reversed(parts)))

    def test_hosted_acceptance_requires_exact_passed_workflow_attempt(self):
        release = {'buildRunId': '202', 'buildRunAttempt': '3', 'sourceCommit': 'a' * 40}
        row = dict(head_sha=release['sourceCommit'], status='completed', conclusion='success', run_attempt=3,
                   path='.github/workflows/browser-2_1-acceptance.yml')
        with patch.object(delivery.subprocess, 'check_output', return_value=json.dumps(row).encode()) as api:
            delivery.verify_hosted_acceptance(release)
            self.assertEqual(api.call_args.args[0][-1],
                             'repos/Ararataki-number-one/yuanying-chat/actions/runs/202/attempts/3')
        for changes in ({'conclusion': 'failure'}, {'run_attempt': 1}, {'head_sha': 'b' * 40},
                        {'path': '.github/workflows/unrelated.yml'}):
            with self.subTest(changes=changes), self.assertRaises(ValueError), patch.object(delivery.subprocess,
                    'check_output', return_value=json.dumps(dict(row, **changes)).encode()):
                delivery.verify_hosted_acceptance(release)


if __name__ == '__main__':
    unittest.main()
