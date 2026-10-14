"""Adversarial archive/DEX unit fixtures; no claim of real Android execution."""
import hashlib
import json
import pathlib
import struct
import tempfile
import unittest
import zipfile
import zlib
import sys
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / 'tools/gecko'))
from caret_build_identity import CARET_HELPER, EDITABLE, FIXTURE, OBSERVER_ASSET, audit_apk, dex_definitions


def minimal_dex(definitions, references=()):
    descriptors = list(dict.fromkeys([*definitions, *references]))
    string_at = 112
    type_at = string_at + 4 * len(descriptors)
    class_at = type_at + 4 * len(descriptors)
    text_at = class_at + 32 * len(definitions)
    data = bytearray(text_at)
    data[:8] = b'dex\n035\0'
    def write(offset, value):
        struct.pack_into('<I', data, offset, value)
    write(36, 112); write(40, 0x12345678)
    write(56, len(descriptors)); write(60, string_at)
    write(64, len(descriptors)); write(68, type_at)
    write(96, len(definitions)); write(100, class_at)
    for i, descriptor in enumerate(descriptors):
        write(string_at + 4 * i, len(data)); write(type_at + 4 * i, i)
        length = len(descriptor)
        while length >= 128:
            data.append((length & 127) | 128); length >>= 7
        data.append(length); data.extend(descriptor.encode()); data.append(0)
    for i, descriptor in enumerate(definitions):
        write(class_at + 32 * i, descriptors.index(descriptor))
    write(32, len(data))
    data[12:32] = hashlib.sha1(data[32:]).digest()
    write(8, zlib.adler32(data[12:]) & 0xffffffff)
    return bytes(data)


class DexIdentityTests(unittest.TestCase):
    def test_only_class_defs_count_not_strings(self):
        observer = 'Lorg/mozilla/geckoview/PocketGeckoEditableTrace;'
        data = minimal_dex([EDITABLE, FIXTURE], [observer])
        self.assertEqual(dex_definitions(data), {EDITABLE, FIXTURE})

    def test_corrupted_checksum_rejected(self):
        data = bytearray(minimal_dex([EDITABLE, FIXTURE])); data[-2] ^= 1
        with self.assertRaises(ValueError):
            dex_definitions(bytes(data))

    def test_truncated_and_bad_table_rejected(self):
        with self.assertRaises(ValueError):
            dex_definitions(minimal_dex([EDITABLE])[:-1])
        data = bytearray(minimal_dex([EDITABLE]))
        struct.pack_into('<I', data, 96, 100000)
        data[12:32] = hashlib.sha1(data[32:]).digest()
        struct.pack_into('<I', data, 8, zlib.adler32(data[12:]) & 0xffffffff)
        with self.assertRaises(ValueError):
            dex_definitions(bytes(data))

    def test_duplicate_definitions_rejected(self):
        with self.assertRaises(ValueError):
            dex_definitions(minimal_dex([EDITABLE, EDITABLE]))

    def test_apk_definition_presence_and_observer_negatives(self):
        with tempfile.TemporaryDirectory() as temp:
            root = pathlib.Path(temp)
            def package(name, definitions, references=(), extra=None):
                path = root / name
                with zipfile.ZipFile(path, 'w') as archive:
                    archive.writestr('classes.dex', minimal_dex(definitions, references))
                    if extra:
                        archive.writestr('classes2.dex', minimal_dex(extra))
                    archive.writestr('assets/caret-build-identity.json', json.dumps({'schema': 1}))
                    archive.writestr('assets/caret-document-observer.js', 'synthetic fixture script')
                return path
            observer = 'Lorg/mozilla/geckoview/PocketGeckoEditableTrace;'
            positive = audit_apk(package('normal.apk', [EDITABLE, FIXTURE, CARET_HELPER], [observer]))
            self.assertEqual(positive['observerDefinitions'], [])
            self.assertEqual(positive['observerScriptSha256'], hashlib.sha256(b'synthetic fixture script').hexdigest())
            self.assertEqual(positive['dex'][0]['classDefinitions'], sorted([EDITABLE, FIXTURE, CARET_HELPER]))
            for name, definitions, extra in [('observer.apk', [EDITABLE, FIXTURE, CARET_HELPER, observer], None),
                                             ('missing.apk', [EDITABLE], None),
                                             ('duplicate.apk', [EDITABLE, FIXTURE, CARET_HELPER], [EDITABLE])]:
                with self.subTest(name=name), self.assertRaises(ValueError):
                    audit_apk(package(name, definitions, extra=extra))

    def test_passive_fixture_asset_is_required_only_in_integration_and_excluded_from_release(self):
        with tempfile.TemporaryDirectory() as temp:
            root=pathlib.Path(temp)
            def package(name, definitions, observer=False, identity=False):
                path=root/name
                with zipfile.ZipFile(path,'w') as archive:
                    archive.writestr('classes.dex',minimal_dex(definitions))
                    if observer:archive.writestr(OBSERVER_ASSET,'synthetic passive observer')
                    if identity:archive.writestr('assets/caret-build-identity.json','{"schema":1}')
                return path
            release=package('release.apk',[EDITABLE])
            self.assertIsNone(audit_apk(release,package='local.pocketchat',component=None,require_fixture=False)['observerScriptSha256'])
            with self.assertRaises(ValueError):
                audit_apk(package('leaked-asset.apk',[EDITABLE],observer=True),package='local.pocketchat',component=None,require_fixture=False)
            with self.assertRaises(ValueError):
                audit_apk(package('missing-asset.apk',[EDITABLE,FIXTURE,CARET_HELPER],identity=True))


if __name__ == '__main__':
    unittest.main()
