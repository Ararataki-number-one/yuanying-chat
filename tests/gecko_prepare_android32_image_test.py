"""API 32 installer controls only; no Android workload is run by these tests."""
from contextlib import redirect_stdout
import hashlib
import importlib.util
import io
import json
from pathlib import Path
import stat
import sys
import tempfile
import unittest
from unittest.mock import patch
from xml.dom import minidom
import zipfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools/gecko'))
spec = importlib.util.spec_from_file_location('android32_image_setup', ROOT / 'tools/gecko/prepare_android32_image.py')
setup = importlib.util.module_from_spec(spec)
spec.loader.exec_module(setup)
PIN = json.loads(setup.PIN.read_text())
SOURCE_PROPERTIES = (ROOT / 'tests/fixtures/android-32-r08-source.properties').read_bytes()


def properties(changes=None):
    """Keep the official 293 bytes unchanged unless a negative control asks."""
    raw = SOURCE_PROPERTIES
    original = dict(line.split('=', 1) for line in raw.decode().splitlines() if '=' in line)
    for key, value in (changes or {}).items():
        raw = raw.replace((key + '=' + original[key] + '\n').encode(),
                          (key + '=' + value + '\n').encode())
    return raw


def archive(changes=None, empty=None, omit=None, extra=None, source_properties=None):
    body = io.BytesIO()
    with zipfile.ZipFile(body, 'w') as out:
        out.writestr('x86_64/source.properties', properties(changes) if source_properties is None else source_properties)
        for name in ('system.img', 'ramdisk.img', 'kernel-ranchu'):
            if name != omit:
                out.writestr('x86_64/' + name, b'' if name == empty else b'controlled-image-bytes')
        if extra:
            out.writestr(extra, b'unsafe-entry')
    return body.getvalue()


class Android32ImageSetupTest(unittest.TestCase):
    def test_official_pin_and_sdk_registration_are_consistent(self):
        self.assertEqual(PIN['package'], 'system-images;android-32;google_apis;x86_64')
        self.assertEqual(PIN['catalog'], 'https://dl.google.com/android/repository/sys-img/google_apis/sys-img2-3.xml')
        self.assertTrue(PIN['url'].startswith('https://dl.google.com/android/repository/sys-img/google_apis/'))
        self.assertTrue(PIN['url'].endswith('/x86_64-32_r' + str(PIN['revision']).zfill(2) + '.zip'))
        self.assertGreater(PIN['bytes'], 0)
        self.assertRegex(PIN['sha1'], r'^[a-f0-9]{40}$')
        self.assertEqual(PIN['revision'], 8)
        self.assertEqual(PIN['archiveSourceRevision'], 4)
        self.assertEqual(PIN['bytes'], 1538792859)
        self.assertEqual(PIN['sha1'], '1b52794699c6889a2fd155bf235b67a592eb8f1d')
        self.assertEqual(len(SOURCE_PROPERTIES), 293)
        self.assertEqual(PIN['sourcePropertiesSha256'], '0d899ec09983dd45e45303ea5bfbc28f70b4d5303bda5e3778cbf0a3409b233e')
        self.assertEqual(hashlib.sha256(SOURCE_PROPERTIES).hexdigest(), PIN['sourcePropertiesSha256'])
        doc = minidom.parse(str(setup.PACKAGE))
        self.assertEqual(doc.documentElement.namespaceURI, 'http://schemas.android.com/repository/android/common/02')
        local = doc.getElementsByTagName('localPackage')[0]
        self.assertEqual(local.getAttribute('path'), PIN['package'])
        self.assertEqual(local.getElementsByTagName('api-level')[0].firstChild.data, '32')
        self.assertEqual(local.getElementsByTagName('abi')[0].firstChild.data, 'x86_64')
        self.assertEqual(local.getElementsByTagName('tag')[0].getElementsByTagName('id')[0].firstChild.data, 'google_apis')
        self.assertEqual(int(local.getElementsByTagName('revision')[0].getElementsByTagName('major')[0].firstChild.data), PIN['revision'])

    def install_fixture(self, base, raw):
        source = Path(base) / 'image.zip'
        source.write_bytes(raw)
        target = Path(base) / 'sdk/system-images/android-32/google_apis/x86_64'
        return source, target

    def test_verified_image_is_published_with_pinned_registration(self):
        with tempfile.TemporaryDirectory() as base:
            source, target = self.install_fixture(base, archive())
            props = setup.install(source, target, setup.PACKAGE, PIN['archiveSourceRevision'], PIN['sourcePropertiesSha256'])
            self.assertEqual(props['AndroidVersion.ApiLevel'], '32')
            self.assertEqual(props['Pkg.Revision'], str(PIN['archiveSourceRevision']))
            self.assertEqual((target / 'source.properties').read_bytes(), SOURCE_PROPERTIES)
            for name in ('system.img', 'ramdisk.img', 'kernel-ranchu'):
                self.assertEqual((target / name).read_bytes(), b'controlled-image-bytes')
            self.assertEqual((target / 'package.xml').read_bytes(), setup.PACKAGE.read_bytes())
            self.assertFalse(list(target.parent.glob('verified-*')))

    def test_wrong_api_revision_tag_and_abi_never_publish(self):
        for key, value in (
            ('AndroidVersion.ApiLevel', '35'),
            ('Pkg.Revision', str(PIN['revision'])),
            ('Pkg.Revision', str(PIN['revision'] + 1)),
            ('SystemImage.TagId', 'google_apis_playstore'),
            ('SystemImage.Abi', 'arm64-v8a'),
        ):
            with self.subTest(property=key), tempfile.TemporaryDirectory() as base:
                raw = properties({key: value})
                source, target = self.install_fixture(base, archive(source_properties=raw))
                # Pass this controlled raw hash only to reach the independent
                # semantic guard; production always supplies the fixed pin.
                with self.assertRaisesRegex(ValueError, 'pinned Google API 32'):
                    setup.install(source, target, setup.PACKAGE, PIN['archiveSourceRevision'], hashlib.sha256(raw).hexdigest())
                self.assertFalse(target.exists())

    def test_complete_official_properties_hash_rejects_any_byte_change(self):
        for raw in (properties({'Pkg.Revision': '8'}),
                    properties({'AndroidVersion.ApiLevel': '35'}),
                    properties({'SystemImage.Abi': 'arm64-v8a'}),
                    properties({'SystemImage.TagId': 'google_apis_playstore'}),
                    SOURCE_PROPERTIES.replace(b'Google APIs.', b'Google APIs!'),
                    SOURCE_PROPERTIES + b'Unexpected.NewField=true\n',
                    SOURCE_PROPERTIES.rstrip(b'\n') + b'\n'):
            with self.subTest(sha256=hashlib.sha256(raw).hexdigest()), tempfile.TemporaryDirectory() as base:
                source, target = self.install_fixture(base, archive(source_properties=raw))
                with self.assertRaisesRegex(ValueError, 'source.properties differs'):
                    setup.install(source, target, setup.PACKAGE, PIN['archiveSourceRevision'], PIN['sourcePropertiesSha256'])
                self.assertFalse(target.exists())
                self.assertFalse(list(target.parent.glob('verified-*')))

    def test_wrong_properties_hash_never_publishes_official_properties(self):
        with tempfile.TemporaryDirectory() as base:
            source, target = self.install_fixture(base, archive())
            with self.assertRaisesRegex(ValueError, 'source.properties differs'):
                setup.install(source, target, setup.PACKAGE, PIN['archiveSourceRevision'], '0' * 64)
            self.assertFalse(target.exists())

    def test_report_distinguishes_catalog_revision_from_archive_properties(self):
        with tempfile.TemporaryDirectory() as base:
            base = Path(base)
            report = base / 'setup-report.json'
            def controlled_download(pin, path):
                self.assertEqual(pin, PIN)
                path.write_bytes(archive())
                return 1
            output = io.StringIO()
            with patch.object(setup, 'download', side_effect=controlled_download), \
                    patch.object(sys, 'argv', ['prepare_android32_image.py', '--sdk-root', str(base / 'sdk'),
                                              '--cache', str(base / 'cache'), '--report', str(report)]), \
                    redirect_stdout(output):
                setup.main()
            result = json.loads(report.read_text())
            self.assertEqual(result['status'], 'passed')
            self.assertEqual(result['catalogRevision'], 8)
            self.assertEqual(result['archiveSourceRevision'], 4)
            self.assertEqual(result['properties']['Pkg.Revision'], '4')
            self.assertEqual(result['sourcePropertiesSha256'], hashlib.sha256(SOURCE_PROPERTIES).hexdigest())
            self.assertNotIn('revision', result)
            self.assertIs(result['setupOnly'], True)
            self.assertIs(result['actualAndroidExecution'], False)
            self.assertIs(result['workloadExecuted'], False)
            emitted = json.loads(output.getvalue())
            self.assertEqual((emitted['catalogRevision'], emitted['archiveSourceRevision']), (8, 4))

    def test_empty_or_missing_required_image_never_publishes(self):
        for name in ('system.img', 'ramdisk.img', 'kernel-ranchu'):
            for mode in ('empty', 'omit'):
                with self.subTest(image=name, mode=mode), tempfile.TemporaryDirectory() as base:
                    source, target = self.install_fixture(base, archive(**{mode: name}))
                    with self.assertRaises(ValueError):
                        setup.install(source, target, setup.PACKAGE, PIN['archiveSourceRevision'], PIN['sourcePropertiesSha256'])
                    self.assertFalse(target.exists())

    def test_existing_installation_is_preserved(self):
        with tempfile.TemporaryDirectory() as base:
            source, target = self.install_fixture(base, archive())
            target.mkdir(parents=True)
            (target / 'keep').write_text('original')
            with self.assertRaises(FileExistsError):
                setup.install(source, target, setup.PACKAGE, PIN['archiveSourceRevision'], PIN['sourcePropertiesSha256'])
            self.assertEqual((target / 'keep').read_text(), 'original')

    def test_file_target_and_symlink_target_or_ancestor_are_rejected(self):
        for kind in ('target-file', 'target-symlink', 'dangling-target-symlink', 'ancestor-file', 'ancestor-symlink'):
            with self.subTest(kind=kind), tempfile.TemporaryDirectory() as base:
                source, target = self.install_fixture(base, archive())
                foreign = Path(base) / 'foreign'
                foreign.mkdir()
                (foreign / 'keep').write_text('original')
                if kind == 'ancestor-file':
                    (Path(base) / 'sdk').write_text('ordinary-file')
                elif kind == 'ancestor-symlink':
                    (Path(base) / 'sdk').symlink_to(foreign, target_is_directory=True)
                else:
                    target.parent.mkdir(parents=True)
                    if kind == 'target-file':
                        target.write_text('ordinary-file')
                    elif kind == 'target-symlink':
                        target.symlink_to(foreign, target_is_directory=True)
                    else:
                        target.symlink_to(Path(base) / 'missing', target_is_directory=True)
                with self.assertRaises((ValueError, FileExistsError, OSError)):
                    setup.install(source, target, setup.PACKAGE, PIN['archiveSourceRevision'], PIN['sourcePropertiesSha256'])
                self.assertEqual((foreign / 'keep').read_text(), 'original')
                self.assertEqual(sorted(p.name for p in foreign.iterdir()), ['keep'])

    def test_unsafe_zip_paths_and_links_never_publish(self):
        link = zipfile.ZipInfo('x86_64/unsafe-link')
        link.create_system = 3
        link.external_attr = (stat.S_IFLNK | 0o777) << 16
        for extra in ('../escaped', '/absolute', 'other-root/system.img', 'x86_64/../../escaped', link):
            with self.subTest(path=str(extra)), tempfile.TemporaryDirectory() as base:
                source, target = self.install_fixture(base, archive(extra=extra))
                with self.assertRaises(ValueError):
                    setup.install(source, target, setup.PACKAGE, PIN['archiveSourceRevision'], PIN['sourcePropertiesSha256'])
                self.assertFalse(target.exists())
                self.assertFalse((Path(base) / 'escaped').exists())

    def test_crc_corruption_never_publishes_partial_extraction(self):
        raw = bytearray(archive())
        raw[raw.index(b'controlled-image-bytes')] ^= 1
        with tempfile.TemporaryDirectory() as base:
            source, target = self.install_fixture(base, raw)
            with self.assertRaises(zipfile.BadZipFile):
                setup.install(source, target, setup.PACKAGE, PIN['archiveSourceRevision'], PIN['sourcePropertiesSha256'])
            self.assertFalse(target.exists())
            self.assertFalse(list(target.parent.glob('verified-*')))

    def test_source_properties_crc_corruption_fails_before_hash_check(self):
        raw = bytearray(archive())
        raw[raw.index(SOURCE_PROPERTIES)] ^= 1
        with tempfile.TemporaryDirectory() as base:
            source, target = self.install_fixture(base, raw)
            with self.assertRaises(zipfile.BadZipFile):
                setup.install(source, target, setup.PACKAGE, PIN['archiveSourceRevision'], PIN['sourcePropertiesSha256'])
            self.assertFalse(target.exists())
            self.assertFalse(list(target.parent.glob('verified-*')))


if __name__ == '__main__':
    unittest.main()
