"""Focused release staging controls with synthetic APKs and an isolated signer."""

import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch
from zipfile import ZIP_DEFLATED, ZIP_STORED, ZipFile

import stage_chromium_module as stage


def tree(role='', minimum=26, native='arm64_v8a', debuggable='false'):
    header = ['  E: manifest (line=2)', '    A: package="local.pocketchat" (Raw: "local.pocketchat")',
              '    A: android:versionCode(0x0101021b)=115']
    app_attributes = [f'        A: android:debuggable(0x0101000f)={debuggable}']
    if role == 'chromium':
        header.extend(['    A: split="chromium"', '    A: android:isFeatureSplit(0x0101055b)=true',
                       '    A: android:requiredSplitTypes(0x0101064e)="chromium__abi"'])
    elif role:
        header.extend([f'    A: split="chromium.config.{native}"', '    A: configForSplit="chromium"',
                       '    A: android:splitTypes(0x0101064f)="chromium__abi"'])
        app_attributes.append('        A: android:hasCode(0x0101000c)=false')
    if not role or role == 'chromium':
        header.append('    A: android:versionName(0x0101021c)="2.1.13" (Raw: "2.1.13")')
    metadata = [] if role else ['          E: meta-data (line=26)',
                                '            A: android:name(0x01010003)="local.pocketchat.CHROMIUM_DELIVERY"',
                                '            A: android:value(0x01010024)=true']
    return '\n'.join(header + ['      E: uses-sdk (line=7)', f'        A: android:minSdkVersion(0x0101020c)={minimum}',
                               '      E: application (line=15)', *app_attributes, *metadata]).encode()


def fake_apk(file, members, compression=ZIP_STORED):
    with ZipFile(file, 'w', compression=compression) as apk:
        apk.writestr('AndroidManifest.xml', b'host test only')
        for name, data in members.items():
            apk.writestr(name, data)


class StagingTest(unittest.TestCase):
    def setUp(self):
        folder = tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        self.root = Path(folder.name)
        self.apks = self.root / 'apks'
        self.apks.mkdir()
        self.base = self.apks / 'base.apk'
        self.feature = self.apks / 'feature.apk'
        self.native = self.apks / 'native.apk'
        self.args = SimpleNamespace(aapt2='test-aapt2', apksigner='test-apksigner', openssl='openssl',
                                    abi='arm64-v8a', version='2.1.13', version_code=115, candidate=None,
                                    base_apk=self.base, split_set=self.apks, output=self.root / 'prepare',
                                    manifest=None, signature=None)

    def test_manifest_validates_roles_sdk_version_and_abi(self):
        for section, role in (('', ''), ('chromium', 'chromium'), ('config', 'chromium.config.arm64_v8a')):
            with self.subTest(role=role), patch.object(stage, 'apk_command', return_value=tree(section)):
                self.assertEqual(stage.manifest_role('aapt2', self.base, '2.1.13', 115, 'arm64-v8a')[0], role)
        for value in (tree(minimum=29), tree('config', native='x86_64'), tree(debuggable='true'),
                      tree().replace(b')=115', b')=114'), tree().replace(b'local.pocketchat', b'wrong.package'),
                      tree().replace(b'debuggable(0x0101000f)=false',
                                     b'debuggable(0x0101000f)=false\n        A: android:extractNativeLibs(0x010104ea)=false'),
                      tree().replace(b'value(0x01010024)=true', b'value(0x01010024)="true"'),
                      tree().replace(b'CHROMIUM_DELIVERY', b'SOME_OTHER_FLAG'),
                      tree() + b'\n      E: provider\n        A: android:name="com.cefrium.CefriumInitProvider"',
                      tree() + b'\n      E: provider\n        A: android:name="local.pocketchat.CefriumSetupProvider"'):
            with self.subTest(value=value), patch.object(stage, 'apk_command', return_value=value):
                with self.assertRaises(ValueError):
                    stage.manifest_role('aapt2', self.base, '2.1.13', 115, 'arm64-v8a')

    def test_base_cannot_contain_chromium_library_assets_or_classes(self):
        members = {'lib/arm64-v8a/libxul.so': b'Gecko', 'lib/arm64-v8a/libmozglue.so': b'Gecko',
                   'classes.dex': b'synthetic'}
        definitions = {'Lorg/mozilla/geckoview/GeckoView;', *stage.ACTIVITY_RESULT_CLASSES}
        with patch.object(stage, 'dex_definitions', return_value=definitions):
            fake_apk(self.base, members)
            stage.check_payload(self.base, '', 'arm64-v8a')
            for unexpected in ('lib/arm64-v8a/libcef.so', 'assets/icudtl.dat+com.cefrium+'):
                fake_apk(self.base, {**members, unexpected: b'Chromium'})
                with self.assertRaisesRegex(ValueError, 'found in the Gecko base'):
                    stage.check_payload(self.base, '', 'arm64-v8a')
        for name in ('Lcom/cefrium/Cefrium;', 'Llocal/pocketchat/CefriumSetupProvider;'):
            with self.subTest(name=name), patch.object(stage, 'dex_definitions', return_value={name}):
                fake_apk(self.base, members)
                with self.assertRaisesRegex(ValueError, 'found in the Gecko base'):
                    stage.check_payload(self.base, '', 'arm64-v8a')

    def test_shared_activity_result_api_must_be_defined_by_the_base(self):
        fake_apk(self.base, {'lib/arm64-v8a/libxul.so': b'Gecko', 'lib/arm64-v8a/libmozglue.so': b'Gecko',
                             'classes.dex': b'synthetic'})
        owner = 'Landroidx/activity/result/ActivityResultRegistryOwner;'
        with patch.object(stage, 'dex_definitions', return_value=stage.ACTIVITY_RESULT_CLASSES - {owner}):
            with self.assertRaisesRegex(ValueError, 'base lacks the shared AndroidX Activity Result API'):
                stage.check_payload(self.base, '', 'arm64-v8a')
        fake_apk(self.feature, {'classes.dex': b'synthetic'})
        with patch.object(stage, 'dex_definitions', return_value={'Lcom/cefrium/Cefrium;', owner}):
            with self.assertRaisesRegex(ValueError, 'feature duplicates the shared AndroidX Activity Result API'):
                stage.check_payload(self.feature, 'chromium', 'arm64-v8a')

    def test_feature_resources_require_exact_uncompressed_bytes(self):
        resource = next(iter(stage.ASSET_SHA))
        fake_payload = b'fixture' * 4000
        expected = {resource: hashlib.sha256(fake_payload).hexdigest()}
        members = {'classes.dex': b'synthetic', resource: fake_payload}
        with patch.object(stage, 'dex_definitions', return_value={'Lcom/cefrium/Cefrium;'}), patch.object(stage, 'ASSET_SHA', expected):
            fake_apk(self.feature, members)
            stage.check_payload(self.feature, 'chromium', 'arm64-v8a')
            for entries, compression in ((members, ZIP_DEFLATED), ({**members, resource: b'changed'}, ZIP_STORED),
                                         ({'classes.dex': b'synthetic'}, ZIP_STORED)):
                fake_apk(self.feature, entries, compression)
                with self.assertRaisesRegex(ValueError, 'asset missing, compressed or changed'):
                    stage.check_payload(self.feature, 'chromium', 'arm64-v8a')

    def test_manifest_binds_exact_base_and_requires_native_split_and_capability(self):
        for path in (self.base, self.feature, self.native):
            path.write_bytes(path.name.encode())
        info = {'base.apk': ('', set(), set()), 'feature.apk': ('chromium', {'chromium__abi'}, set()),
                'native.apk': ('chromium.config.arm64_v8a', set(), {'chromium__abi'})}
        with patch.object(stage, 'manifest_role', side_effect=lambda _, path, *_args: info[path.name]), \
                patch.object(stage, 'apk_signer', return_value=b'test verified certificate'), patch.object(stage, 'check_payload', side_effect=lambda path, *_args: path == self.native):
            raw, roles, _ = stage.read_set(self.args, self.apks, self.base)
            metadata = json.loads(raw)
            self.assertEqual(metadata['baseSha256'], stage.digest(self.base))
            self.assertEqual(metadata['signerSha256'], stage.SIGNER)
            self.assertEqual(metadata['tag'], 'v2.1.13-gecko')
            self.assertEqual(metadata['nativeSplit'], 'chromium.config.arm64_v8a')
            self.assertEqual(list(roles), ['', 'chromium', 'chromium.config.arm64_v8a'])
            self.assertEqual([row['name'] for row in metadata['splits']], ['chromium', 'chromium.config.arm64_v8a'])
            self.args.candidate = 2
            self.assertEqual(json.loads(stage.read_set(self.args, self.apks, self.base)[0])['tag'], 'v2.1.13-candidate2-gecko')
            with self.assertRaisesRegex(ValueError, 'differs from the exact APK'):
                stage.read_set(self.args, self.apks, self.native)
            info['native.apk'] = ('chromium.config.arm64_v8a', set(), set())
            with self.assertRaisesRegex(ValueError, 'configuration type'):
                stage.read_set(self.args, self.apks, self.base)

    def test_folded_native_engine_belongs_to_the_only_feature_apk(self):
        for path in (self.base, self.feature):
            path.write_bytes(path.name.encode())
        with patch.object(stage, 'manifest_role', side_effect=[('', set(), set()), ('chromium', set(), set())]), \
                patch.object(stage, 'apk_signer', return_value=b'test verified certificate'), \
                patch.object(stage, 'check_payload', side_effect=lambda path, *_args: path == self.feature):
            metadata = json.loads(stage.read_set(self.args, self.apks, self.base)[0])
            self.assertEqual(metadata['nativeSplit'], 'chromium')
            self.assertEqual([row['name'] for row in metadata['splits']], ['chromium'])

    @unittest.skipUnless(shutil.which('openssl'), 'OpenSSL not available')
    def test_detached_original_cert_and_exact_payload(self):
        cert = self.root / 'cert-source.pem'
        key = self.root / 'key-synthetic.pem'
        payload = self.root / 'unsigned.payload'
        signature = self.root / 'module.sig'
        raw = b'{"schema":1}\n'
        stage.apk_command('openssl', 'req', '-new', '-newkey', 'rsa:2048', '-x509', '-nodes', '-days', '1',
                          '-subj', '/CN=PocketChat Synthetic Test', '-keyout', key, '-out', cert)
        payload.write_bytes(stage.PREFIX + raw)
        stage.apk_command('openssl', 'dgst', '-sha256', '-sign', key, '-out', signature, payload)
        stage.verify_detached('openssl', self.root, raw, signature, cert.read_bytes())
        with self.assertRaisesRegex(ValueError, 'does not match the manifest'):
            stage.verify_detached('openssl', self.root, raw + b' ', signature, cert.read_bytes())

    def test_staged_outputs_replace_neither_invalid_nor_existing_packages(self):
        for path in (self.base, self.feature, self.native):
            path.write_bytes(path.name.encode())

        def checked(_args, inputs, _base):
            roles = {'': (inputs / self.base.name, {}), 'chromium': (inputs / self.feature.name, {}),
                     'chromium.config.arm64_v8a': (inputs / self.native.name, {})}
            return b'{"schema":1}\n', roles, b'test verified certificate'

        prefix = 'PocketChat-2.1.13-chromium-arm64-v8a'
        with patch.object(stage, 'read_set', side_effect=checked):
            stage.run(self.args)
            self.args.signature = self.root / 'test.sig'
            self.args.signature.write_bytes(b'test signature')
            self.args.manifest = self.args.output / (prefix + '.json')
            self.assertEqual((self.args.output / 'manifest.payload').read_bytes(), stage.PREFIX + self.args.manifest.read_bytes())
            self.args.output = self.root / 'stage'
            with patch.object(stage, 'verify_detached', side_effect=ValueError('invalid')):
                with self.assertRaisesRegex(ValueError, 'invalid'):
                    stage.run(self.args)
            self.assertFalse(self.args.output.exists())
            with patch.object(stage, 'verify_detached'):
                stage.run(self.args)
                self.assertEqual(sorted(path.name for path in self.args.output.iterdir()), sorted([
                    prefix + '.json', prefix + '.sig', f'{prefix}--chromium.apk',
                    f'{prefix}--chromium.config.arm64_v8a.apk', 'PocketChat-2.1.13-gecko-arm64.apk']))
                with self.assertRaisesRegex(ValueError, 'already exists'):
                    stage.run(self.args)


if __name__ == '__main__':
    unittest.main()
