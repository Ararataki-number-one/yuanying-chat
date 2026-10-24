"""Builder guard/byte controls with synthetic tools; no key, APK or Android acceptance."""
import importlib.util
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest
from unittest.mock import patch
import zipfile

ROOT=Path(__file__).resolve().parents[1]
SPEC=importlib.util.spec_from_file_location('native_driver_build',ROOT/'tools/gecko/build_native_input_driver.py')
B=importlib.util.module_from_spec(SPEC);SPEC.loader.exec_module(B)


class InputDriverBuildTest(unittest.TestCase):
    def setUp(self):
        temp=tempfile.TemporaryDirectory();self.addCleanup(temp.cleanup);self.root=Path(temp.name)
        self.git('init','-q');(self.root/'.gitignore').write_text('work/\n')
        folder=self.root/'tests/native-input-driver';folder.mkdir(parents=True)
        (folder/'NativeInputInstrumentation.java').write_text('// Synthetic builder input, never executed\n')
        self.manifest=folder/'AndroidManifest.xml'
        self.manifest.write_text('<manifest xmlns:android="http://schemas.android.com/apk/res/android" package="local.pocketchat.inputdriver"><application/><instrumentation android:name="local.pocketchat.inputdriver.NativeInputInstrumentation" android:targetPackage="local.pocketchat.inputdriver"/></manifest>')
        self.git('add','.');self.git('commit','-qm','Synthetic source')
        self.key=self.root/'work/gecko-integration/integration-test.jks';self.key.parent.mkdir(parents=True)
        self.key.write_bytes(b'synthetic-not-a-key')
        self.chain={name:self.root/'work/tools'/name for name in ('java','javac','jar','androidJar','aapt2','zipalign','apksigner','d8')}
        for name,path in self.chain.items():path.parent.mkdir(parents=True,exist_ok=True);path.write_text('synthetic tool '+name)
        self.calls=[];self.mutate=False
        self.certificates=b'Signer #1 certificate SHA-256 digest: '+b'c'*64+b'\n'
        self.verify_code=0
        self.real_run=subprocess.run
        self.env=patch.dict(os.environ,GITHUB_RUN_ID='1234',GITHUB_RUN_ATTEMPT='1');self.env.start();self.addCleanup(self.env.stop)

    def git(self,*args):
        return subprocess.check_output(['git','-c','user.name=Driver fixture','-c','user.email=fixture@example.invalid',*args],cwd=self.root,text=True,stderr=subprocess.PIPE).strip()

    def tool(self,parts,**kwargs):
        if parts[0]=='git':return self.real_run(parts,**kwargs)
        self.calls.append(parts);name=Path(parts[0]).name
        if name=='jar':Path(parts[2]).write_bytes(b'synthetic jar')
        elif name=='java':(Path(parts[parts.index('--output')+1])/'classes.dex').write_bytes(b'synthetic dex')
        elif name=='aapt2':
            with zipfile.ZipFile(parts[parts.index('-o')+1],'w') as archive:
                assets=Path(parts[parts.index('-A')+1]);archive.write(assets/B.ASSET,'assets/'+B.ASSET)
        elif name=='zipalign':shutil.copy2(parts[-2],parts[-1])
        elif name=='apksigner' and parts[1]=='sign':shutil.copy2(parts[-1],parts[parts.index('--out')+1])
        elif name=='apksigner' and parts[1]=='verify':
            if self.mutate:(self.root/'tests/native-input-driver/NativeInputInstrumentation.java').write_text('changed mid-build')
            return subprocess.CompletedProcess(parts,self.verify_code,stdout=self.certificates,stderr=b'original signature diagnostics\n')
        return subprocess.CompletedProcess(parts,0,stdout=b'',stderr=b'')

    def build(self,**kwargs):
        with patch.object(B,'tools',return_value=(self.chain,{'syntheticTools':True})),patch.object(B.subprocess,'run',side_effect=self.tool):
            return B.build(self.root,self.root/'jdk',self.root/'sdk',key=kwargs.pop('key',self.key),**kwargs)

    def test_exact_asset_and_signed_bytes_bound_to_current_source(self):
        result=self.build();out=self.key.parent
        self.assertEqual(result['status'],'built');self.assertFalse(result['actualAndroidExecution'])
        self.assertFalse(result['releaseAcceptance']);self.assertFalse(result['compileOnly'])
        self.assertEqual(result['sourceCommit'],self.git('rev-parse','HEAD'))
        self.assertEqual(result['runId'],'1234');self.assertEqual(result['runAttempt'],'1')
        self.assertEqual(result['targetPackage'],'local.pocketchat.test')
        self.assertEqual(result['instrumentationTargetPackage'],result['packageName'])
        self.assertEqual(result['protocols'],B.PROTOCOLS)
        self.assertEqual(result['apkSha256'],B.sha(out/'native-input-driver.apk'))
        self.assertEqual(result['signerCertificateSha256'],'c'*64)
        for name,digest in result['signatureLogs'].items():self.assertEqual(B.sha(out/name),digest)
        self.assertEqual(json.loads((out/B.ASSET).read_bytes()),result)
        with zipfile.ZipFile(out/'native-input-driver.apk') as archive:asset=json.loads(archive.read('assets/'+B.ASSET))
        self.assertNotIn('apkSha256',asset);self.assertEqual(asset['inputs'],result['inputs'])
        signs=[c for c in self.calls if Path(c[0]).name=='apksigner' and c[1]=='sign']
        self.assertEqual(len(signs),1);self.assertEqual(signs[0][signs[0].index('--ks')+1],str(self.key))

    def test_foreign_instrumentation_target_rejected_before_compile(self):
        self.manifest.write_text(self.manifest.read_text().replace('android:targetPackage="local.pocketchat.inputdriver"','android:targetPackage="local.pocketchat.test"'))
        with self.assertRaisesRegex(ValueError,'target only'):B.inputs(self.root)
        self.assertEqual(self.calls,[])

    def test_privileged_permission_and_ui_activity_rejected(self):
        original=self.manifest.read_text()
        for text in [original.replace('<application/>','<application><activity android:name="Bad"/></application>'),
                     original.replace('<application/>','<uses-permission android:name="android.permission.INJECT_EVENTS"/><application/>')]:
            self.manifest.write_text(text)
            with self.assertRaises(ValueError):B.inputs(self.root)

    def test_symlink_source_rejected(self):
        source=self.root/'tests/native-input-driver/NativeInputInstrumentation.java';source.unlink();source.symlink_to(self.manifest)
        with self.assertRaisesRegex(ValueError,'regular'):B.inputs(self.root)

    def test_dirty_source_rejected_before_tools_or_key_use(self):
        (self.root/'dirty.txt').write_text('uncommitted')
        with self.assertRaisesRegex(ValueError,'clean committed'):self.build()
        self.assertEqual(self.calls,[])

    def test_non_ci_and_aliased_key_paths_rejected(self):
        other=self.root/'work/other.jks';other.write_bytes(b'synthetic-not-a-key')
        with self.assertRaisesRegex(ValueError,'explicit integration-test'):self.build(key=other)
        self.key.unlink();self.key.symlink_to(other)
        with self.assertRaisesRegex(ValueError,'explicit integration-test'):self.build()
        self.assertFalse(any(Path(c[0]).name=='apksigner' for c in self.calls))

    def test_source_changed_after_compile_cannot_publish(self):
        self.mutate=True
        with self.assertRaisesRegex(ValueError,'clean committed'):self.build()
        self.assertFalse((self.key.parent/'native-input-driver.apk').exists())
        self.assertFalse((self.key.parent/B.ASSET).exists())

    def test_compile_only_allows_dirty_but_never_signs_or_writes_runtime_receipt(self):
        (self.root/'dirty.txt').write_text('compile-only investigation')
        result=self.build(key=None,compile_only=True,android_jar=self.chain['androidJar'])
        self.assertTrue(result['compileOnly']);self.assertEqual(result['status'],'compiled')
        self.assertNotIn('sourceCommit',result);self.assertNotIn('apkSha256',result)
        self.assertEqual([Path(c[0]).name for c in self.calls],['javac'])
        self.assertFalse((self.key.parent/B.ASSET).exists())

    def test_full_build_cannot_override_pinned_platform(self):
        with self.assertRaisesRegex(ValueError,'compile-only'):self.build(android_jar=self.chain['androidJar'])
        self.assertEqual(self.calls,[])

    def test_missing_or_multiple_verified_signers_cannot_publish(self):
        for certificates in (b'No certificate\n',self.certificates+self.certificates.replace(b'#1',b'#2')):
            self.certificates=certificates
            with self.assertRaisesRegex(ValueError,'Exactly one'):self.build()
            self.assertFalse((self.key.parent/'native-input-driver.apk').exists())
            self.assertEqual((self.key.parent/'native-input-driver-signature-stdout.log').read_bytes(),certificates)

    def test_signature_failure_keeps_original_output_and_cannot_publish(self):
        self.verify_code=1
        with self.assertRaises(subprocess.CalledProcessError):self.build()
        self.assertEqual((self.key.parent/'native-input-driver-signature-stdout.log').read_bytes(),self.certificates)
        self.assertEqual((self.key.parent/'native-input-driver-signature-stderr.log').read_bytes(),b'original signature diagnostics\n')
        self.assertFalse((self.key.parent/B.ASSET).exists())

    def test_protocol_whitelist_fixed_before_measurement(self):
        self.assertEqual(B.PROTOCOLS,{'qualification':{'durationMs':300,'moveCount':19,'intervalMs':15,'maxLateMs':30,'upSynchronous':True},
                                     'formal-collapse':{'durationMs':320,'moveCount':19,'intervalMs':16,'maxLateMs':32,'upSynchronous':True}})


if __name__=='__main__':
    result=unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(InputDriverBuildTest))
    out=ROOT/'work/gecko-integration';out.mkdir(parents=True,exist_ok=True)
    (out/'native-input-driver-build-host-results.json').write_text(json.dumps(dict(status='passed' if result.wasSuccessful() else 'failed',
        testCount=result.testsRun,failures=len(result.failures),errors=len(result.errors),actualAndroidExecution=False,
        scope='Synthetic build-tool adapter and real local source-identity controls; no real APK or signature acceptance'),indent=2)+'\n')
    raise SystemExit(0 if result.wasSuccessful() else 1)
