"""Host package integrity controls; no Android workload or acceptance."""
import io
import json
from pathlib import Path
import sys
import tempfile
import unittest
import zipfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools/gecko'))
import prepare_platform_tools as setup


def archive(revision='35.0.2', extra=None):
    body = io.BytesIO()
    with zipfile.ZipFile(body, 'w') as out:
        out.writestr('platform-tools/source.properties', 'Pkg.UserSrc=false\nPkg.Revision=' + revision + '\n')
        for name in ('adb', 'fastboot'):
            entry = zipfile.ZipInfo('platform-tools/' + name)
            entry.external_attr = 0o100755 << 16
            out.writestr(entry, b'controlled-executable')
        if extra:
            out.writestr(extra, b'escape')
    return body.getvalue()


class PlatformToolsTest(unittest.TestCase):
    def test_pin_records_limited_diagnostic_scope(self):
        pin = json.loads(setup.PIN.read_text())
        self.assertEqual(pin['revision'], '35.0.2')
        self.assertEqual(pin['bytes'], 7472902)
        self.assertEqual(pin['diagnosticRun'], 39916977314)
        self.assertIn('does not establish the cause', pin['scope'])

    def test_complete_package_replaces_old_tools_preserving_other_sdk_directories(self):
        with tempfile.TemporaryDirectory() as base:
            root = Path(base); packed = root / 'tools.zip'; packed.write_bytes(archive())
            target = root / 'sdk/platform-tools'; target.mkdir(parents=True)
            (target / 'source.properties').write_text('Pkg.UserSrc=false\nPkg.Revision=37.0.1\n')
            (target / 'adb').write_text('previous'); (target / 'fastboot').write_text('previous')
            (target / 'old').write_text('old'); (target.parent / 'other').write_text('keep')
            setup.install(packed, target, '35.0.2')
            self.assertFalse((target / 'old').exists())
            self.assertTrue((target / 'adb').stat().st_mode & 0o100)
            self.assertEqual((target.parent / 'other').read_text(), 'keep')

    def test_wrong_revision_unsafe_paths_and_crc_corruption_preserve_existing_install(self):
        corrupt = bytearray(archive()); corrupt[corrupt.index(b'controlled-executable')] ^= 1
        for raw in (archive('37.0.1'), archive(extra='../escape'), archive(extra='/absolute'), bytes(corrupt)):
            with self.subTest(size=len(raw)), tempfile.TemporaryDirectory() as base:
                root = Path(base); packed = root / 'tools.zip'; packed.write_bytes(raw)
                target = root / 'sdk/platform-tools'; target.mkdir(parents=True)
                (target / 'source.properties').write_text('Pkg.UserSrc=false\nPkg.Revision=37.0.1\n')
                (target / 'adb').write_text('previous'); (target / 'fastboot').write_text('previous')
                (target / 'keep').write_text('keep')
                with self.assertRaises((ValueError, zipfile.BadZipFile)):
                    setup.install(packed, target, '35.0.2')
                self.assertEqual((target / 'keep').read_text(), 'keep')
                self.assertFalse((root / 'sdk/escape').exists())

    def test_foreign_directory_cannot_be_replaced(self):
        with tempfile.TemporaryDirectory() as base:
            root = Path(base); packed = root / 'tools.zip'; packed.write_bytes(archive())
            target = root / 'sdk/platform-tools'; target.mkdir(parents=True); (target / 'keep').write_text('keep')
            with self.assertRaises(ValueError):
                setup.install(packed, target, '35.0.2')
            self.assertEqual((target / 'keep').read_text(), 'keep')

    def test_actual_archive_hash_and_size_are_both_required(self):
        with tempfile.TemporaryDirectory() as base:
            packed = Path(base) / 'tools.zip'; packed.write_bytes(archive())
            import hashlib
            pin = dict(bytes=packed.stat().st_size, sha256=hashlib.sha256(packed.read_bytes()).hexdigest())
            self.assertTrue(setup.verified(packed, pin))
            pin['sha256'] = '0' * 64
            self.assertFalse(setup.verified(packed, pin))


if __name__ == '__main__':
    unittest.main()
