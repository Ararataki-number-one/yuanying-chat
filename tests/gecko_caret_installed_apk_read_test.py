"""Real binary subprocess tests for the one-shot installed-APK reader; no Android."""
import contextlib
import hashlib
import importlib.util
import io
import json
import os
from pathlib import Path
import stat
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]
SPEC=importlib.util.spec_from_file_location('installed_apk_read',ROOT/'tools/gecko/installed_apk_read.py')
READER=importlib.util.module_from_spec(SPEC);SPEC.loader.exec_module(READER)
INSTALLED='/data/app/~~controlled-token/local.pocketchat.test-controlled/base.apk'
SERIAL='emulator-5554'
PAYLOAD=bytes(range(256))*23+b'\x00APK\r\n\xff\xfe\x80binary\x00tail\n'

FAKE_ADB=r'''import json,os,pathlib,stat,sys,time
base=pathlib.Path(__file__).parent
config=json.loads((base/'config.json').read_text())
final=pathlib.Path(config['finalPath']);fd=os.fstat(1);state=final.stat()
record=dict(argv=sys.argv[1:],stdoutIsRegularFile=stat.S_ISREG(fd.st_mode),
            outputMode=stat.S_IMODE(fd.st_mode),
            reservedFileDescriptor=(fd.st_dev,fd.st_ino)==(state.st_dev,state.st_ino),
            trace=os.environ.get('ADB_TRACE'))
with (base/'commands.jsonl').open('a') as log:log.write(json.dumps(record)+'\n')
raw=(base/'payload.bin').read_bytes();mode=config['mode']
if mode in ('empty','stderr-only'):raw=b''
if mode=='short':raw=raw[:-31]
if mode=='wrong':raw=bytes([raw[0]^255])+raw[1:]
if mode=='progress':raw=b'1 file pulled successfully\n'
if mode=='timeout':raw=raw[:31]
if mode=='replace-destination':
    unrelated=base/'unrelated.bin';unrelated.write_bytes(b'preserve unrelated bytes')
    final.unlink();final.symlink_to(unrelated)
sys.stdout.buffer.write(raw);sys.stdout.buffer.flush()
if mode in ('error','timeout','stderr-only'):
    sys.stderr.buffer.write(b'controlled remote read error\n');sys.stderr.buffer.flush()
if mode=='large-error':
    sys.stderr.buffer.write(b'E'*70000);sys.stderr.buffer.flush()
if mode=='timeout':time.sleep(5)
if mode in ('error','large-error'):raise SystemExit(17)
'''

class InstalledApkReadTests(unittest.TestCase):
    def setUp(self):
        self.temporary=tempfile.TemporaryDirectory(prefix='installed-apk-reader-');self.addCleanup(self.temporary.cleanup)
        self.directory=Path(self.temporary.name);self.adb=self.directory/'fake adb'
        self.adb.write_text('#!'+sys.executable+'\n'+FAKE_ADB);self.adb.chmod(0o700)
        (self.directory/'payload.bin').write_bytes(PAYLOAD)
        self.destination=self.directory/'actual installed.apk';self.diagnostics=self.directory/'receipt.json'
        self.mode('success')
    def mode(self,value):
        (self.directory/'config.json').write_text(json.dumps(dict(mode=value,finalPath=str(self.destination))))
    def read(self,**kwargs):
        values=dict(adb=self.adb,serial=SERIAL,installed_path=INSTALLED,destination=self.destination,
                    expected_sha256=hashlib.sha256(PAYLOAD).hexdigest(),expected_bytes=len(PAYLOAD),
                    diagnostics=self.diagnostics,label='controlled-read')
        values.update(kwargs);return READER.read_installed_apk(**values)
    def receipt(self):return json.loads(self.diagnostics.read_text())
    def commands(self):
        p=self.directory/'commands.jsonl';return [json.loads(x) for x in p.read_text().splitlines()] if p.exists() else []
    def assert_once(self):
        rows=self.commands();self.assertEqual(len(rows),1)
        self.assertEqual(rows[0]['argv'],['-s',SERIAL,'exec-out','cat',INSTALLED])
        self.assertTrue(rows[0]['stdoutIsRegularFile']);self.assertTrue(rows[0]['reservedFileDescriptor'])
        self.assertEqual(rows[0]['trace'],'transport,sockets,sysdeps')
    def failure(self,**kwargs):
        with contextlib.redirect_stderr(io.StringIO()),self.assertRaises(READER.InstalledApkReadError):self.read(**kwargs)
        receipt=self.receipt();self.assertEqual(receipt['status'],'failed')
        self.assertFalse(receipt['actualInstalledApkRead']);self.assertFalse(receipt['retryPerformed'])
        self.assertFalse(receipt['compiledFileFallback']);return receipt
    def assert_partial(self,receipt,raw):
        self.assertEqual(receipt['actualFileBytes'],len(raw))
        self.assertEqual(receipt['actualFileSha256'],hashlib.sha256(raw).hexdigest())
        self.assertEqual(receipt['stdoutBytes'],len(raw));self.assertTrue(receipt['partialCleaned'])
        self.assertFalse(self.destination.exists())
    def test_one_raw_binary_stream_targets_the_exclusively_reserved_fd(self):
        with patch.object(READER.subprocess,'run',wraps=subprocess.run) as process:r=self.read()
        process.assert_called_once();options=process.call_args.kwargs
        self.assertEqual(options['stdin'],subprocess.DEVNULL);self.assertEqual(options['stderr'],subprocess.PIPE)
        self.assertEqual(options['stdout'].name,str(self.destination));self.assertEqual(options['stdout'].mode,'xb')
        self.assertEqual(options['timeout'],30);self.assertIs(options['check'],False);self.assertFalse(options.get('shell',False))
        self.assert_once();self.assertEqual(self.destination.read_bytes(),PAYLOAD)
        self.assertEqual(r,self.receipt());self.assertEqual(r['transport'],'adb-exec-out-raw')
        self.assertEqual(r['status'],'verified-bytes');self.assertTrue(r['actualInstalledApkRead'])
        self.assertFalse(r['actualAndroidFixtureExecution']);self.assertFalse(r['retryPerformed']);self.assertFalse(r['compiledFileFallback'])
        self.assertEqual(r['actualFileBytes'],len(PAYLOAD));self.assertEqual(r['actualFileSha256'],hashlib.sha256(PAYLOAD).hexdigest())
        self.assertEqual(r['stderrBytes'],0);self.assertEqual(r['returnCode'],0)
    def test_exact_hash_cannot_replace_wrong_expected_size(self):
        r=self.failure(expected_bytes=len(PAYLOAD)+1);self.assert_once();self.assert_partial(r,PAYLOAD)
    def test_exact_size_cannot_replace_wrong_expected_hash(self):
        r=self.failure(expected_sha256='0'*64);self.assert_once();self.assert_partial(r,PAYLOAD)
    def test_empty_exit_zero_is_rejected(self):
        self.mode('empty');r=self.failure();self.assert_once();self.assert_partial(r,b'')
    def test_short_exit_zero_is_rejected_with_exact_partial_diagnostics(self):
        self.mode('short');r=self.failure();self.assert_once();self.assert_partial(r,PAYLOAD[:-31])
    def test_same_size_wrong_bytes_are_rejected(self):
        self.mode('wrong');r=self.failure();self.assert_once();self.assert_partial(r,bytes([PAYLOAD[0]^255])+PAYLOAD[1:])
    def test_cli_progress_text_cannot_substitute_for_apk_bytes(self):
        self.mode('progress');r=self.failure();self.assert_once();self.assert_partial(r,b'1 file pulled successfully\n')
    def test_other_compiled_file_and_stderr_cannot_replace_missing_device_bytes(self):
        (self.directory/'compiled.apk').write_bytes(PAYLOAD);self.mode('stderr-only')
        r=self.failure();self.assert_once();self.assert_partial(r,b'');self.assertGreater(r['stderrBytes'],0)
        self.assertEqual((self.directory/'compiled.apk').read_bytes(),PAYLOAD)
    def test_nonzero_exit_fails_even_when_every_byte_matches(self):
        self.mode('error');r=self.failure();self.assert_once();self.assertEqual(r['returnCode'],17);self.assert_partial(r,PAYLOAD)
    def test_timeout_retains_exact_flushed_partial_evidence_and_never_retries(self):
        self.mode('timeout');r=self.failure(timeout=.2);self.assert_once();self.assertEqual(r['failureType'],'TimeoutExpired')
        self.assert_partial(r,PAYLOAD[:31]);self.assertIn('remote read error',r['stderr'])
    def test_stderr_is_bounded_with_its_original_byte_count(self):
        self.mode('large-error');r=self.failure();self.assert_once();self.assertEqual(r['stderrBytes'],70000)
        self.assertEqual(len(r['stderr']),65536);self.assertTrue(r['stderrTruncated']);self.assert_partial(r,PAYLOAD)
    def test_replaced_destination_is_rejected_without_deleting_an_unrelated_target(self):
        self.mode('replace-destination');r=self.failure();self.assert_once()
        self.assertFalse(r['partialCleaned']);self.assertIn('partialCleanupSkipped',r)
        self.assertTrue(self.destination.is_symlink());self.assertEqual(self.destination.read_bytes(),b'preserve unrelated bytes')
    def test_existing_destination_prevents_execution_and_is_preserved(self):
        self.destination.write_bytes(b'old evidence');self.failure();self.assertEqual(self.commands(),[])
        self.assertEqual(self.destination.read_bytes(),b'old evidence')
    def test_existing_symlink_prevents_execution_and_target_overwrite(self):
        p=self.directory/'unrelated.bin';p.write_bytes(b'preserved');self.destination.symlink_to(p)
        self.failure();self.assertEqual(self.commands(),[]);self.assertEqual(p.read_bytes(),b'preserved')
    def test_unsafe_device_paths_are_rejected_before_execution(self):
        for path in ('/tmp/base.apk','/data/app/../base.apk','/data/app/x/base.apk;echo bad','/data/app//x/base.apk','/data/app/x/other.apk','/data/app/x/$(id)/base.apk'):
            with self.subTest(path=path):self.failure(installed_path=path)
        self.assertEqual(self.commands(),[])
    def test_invalid_timeouts_are_rejected_before_execution(self):
        for value in (True,0,-1,31,float('nan'),float('inf')):
            with self.subTest(timeout=value):self.failure(timeout=value)
        self.assertEqual(self.commands(),[])

if __name__=='__main__':unittest.main()
