"""Provisioning controls only; these do not run Android or the input workload."""
import hashlib
import importlib.util
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import zipfile
from xml.dom import minidom

ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('image_setup',ROOT/'tools/gecko/prepare_android_image.py')
setup=importlib.util.module_from_spec(spec);spec.loader.exec_module(setup)

def archive(extra=None,revision=9):
    body=io.BytesIO()
    with zipfile.ZipFile(body,'w') as out:
        out.writestr('x86_64/source.properties',f'Pkg.Revision={revision}\nAndroidVersion.ApiLevel=35\nSystemImage.TagId=google_apis\nSystemImage.Abi=x86_64\n')
        for name in ('system.img','ramdisk.img','userdata.img','kernel-ranchu'):out.writestr('x86_64/'+name,b'fixture-image')
        if extra:out.writestr(extra,b'unexpected')
    return body.getvalue()

class Response(io.BytesIO):
    def __init__(self,data):super().__init__(data);self.headers={'Content-Length':str(len(data))}

class ImageSetupTest(unittest.TestCase):
    def test_package_registration_matches_official_pinned_revision(self):
        pin=json.loads(setup.PIN.read_text());doc=minidom.parse(str(setup.PACKAGE));root=doc.documentElement
        self.assertEqual(root.namespaceURI,'http://schemas.android.com/repository/android/generic/02')
        self.assertEqual(root.getAttribute('xmlns:sys-img'),'http://schemas.android.com/sdk/android/repo/sys-img2/03')
        local=doc.getElementsByTagName('localPackage')[0]
        self.assertEqual(local.getAttribute('path'),pin['package'])
        self.assertEqual(int(local.getElementsByTagName('major')[0].firstChild.data),pin['revision'])
        self.assertTrue(pin['url'].endswith('/x86_64-35_r09.zip'))

    def test_download_rejects_partial_body_before_accepting_verified_setup(self):
        raw=archive();pin=dict(url='https://dl.google.com/controlled-fixture.zip',bytes=len(raw),sha1=hashlib.sha1(raw).hexdigest())
        with tempfile.TemporaryDirectory() as base:
            path=Path(base)/'image.zip'
            with patch.object(setup.urllib.request,'urlopen',side_effect=[Response(raw[:-12]),Response(raw)]) as fetch:
                setup.download(pin,path)
            self.assertEqual(fetch.call_count,2);self.assertEqual(path.read_bytes(),raw)
            self.assertFalse(path.with_suffix('.partial').exists())

    def test_invalid_archive_never_becomes_cached_image(self):
        raw=b'not a zip';pin=dict(url='https://dl.google.com/controlled-fixture.zip',bytes=len(raw),sha1=hashlib.sha1(raw).hexdigest())
        with tempfile.TemporaryDirectory() as base:
            path=Path(base)/'image.zip'
            with patch.object(setup.urllib.request,'urlopen',side_effect=lambda *a,**k:Response(raw)):
                with self.assertRaises(zipfile.BadZipFile):setup.download(pin,path,attempts=2)
            self.assertFalse(path.exists());self.assertFalse(path.with_suffix('.partial').exists())

    def test_wrong_checksum_never_installs(self):
        raw=archive();pin=dict(url='https://dl.google.com/controlled-fixture.zip',bytes=len(raw),sha1='0'*40)
        with tempfile.TemporaryDirectory() as base:
            path=Path(base)/'image.zip'
            with patch.object(setup.urllib.request,'urlopen',return_value=Response(raw)):
                with self.assertRaises(ValueError):setup.download(pin,path,attempts=1)
            self.assertFalse(path.exists())

    def test_verified_setup_extracts_required_original_image_files(self):
        with tempfile.TemporaryDirectory() as base:
            path=Path(base)/'image.zip';path.write_bytes(archive());target=Path(base)/'sdk/x86_64'
            props=setup.install(path,target,setup.PACKAGE,9)
            self.assertEqual(props['Pkg.Revision'],'9');self.assertEqual((target/'system.img').read_bytes(),b'fixture-image')
            self.assertEqual((target/'package.xml').read_bytes(),setup.PACKAGE.read_bytes())

    def test_unexpected_revision_and_unsafe_zip_paths_do_not_publish(self):
        for raw in (archive(revision=8),archive('../escaped'),archive('/absolute')):
            with self.subTest(raw=hashlib.sha1(raw).hexdigest()),tempfile.TemporaryDirectory() as base:
                path=Path(base)/'image.zip';path.write_bytes(raw);target=Path(base)/'sdk/x86_64'
                with self.assertRaises(ValueError):setup.install(path,target,setup.PACKAGE,9)
                self.assertFalse(target.exists());self.assertFalse((Path(base)/'escaped').exists())

    def test_existing_installation_is_preserved(self):
        with tempfile.TemporaryDirectory() as base:
            path=Path(base)/'image.zip';path.write_bytes(archive());target=Path(base)/'sdk/x86_64';target.mkdir(parents=True);(target/'existing').write_text('keep')
            with self.assertRaises(FileExistsError):setup.install(path,target,setup.PACKAGE,9)
            self.assertEqual((target/'existing').read_text(),'keep')

    def test_crc_corruption_cannot_publish_partial_extraction(self):
        raw=bytearray(archive());pos=raw.index(b'fixture-image');raw[pos]^=1
        with tempfile.TemporaryDirectory() as base:
            path=Path(base)/'image.zip';path.write_bytes(raw);target=Path(base)/'sdk/x86_64'
            with self.assertRaises(zipfile.BadZipFile):setup.install(path,target,setup.PACKAGE,9)
            self.assertFalse(target.exists());self.assertFalse(list(target.parent.glob('verified-image-*')))

if __name__=='__main__':unittest.main()
