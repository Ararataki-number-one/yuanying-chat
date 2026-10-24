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
        for name in ('NativeInputInstrumentation.java','NativeGestureProtocol.java','NativeInputShell.java'):
            (folder/name).write_text('// Synthetic builder input, never executed: '+name+'\n')
        self.manifest=folder/'AndroidManifest.xml'
        self.manifest.write_text('<manifest xmlns:android="http://schemas.android.com/apk/res/android" package="local.pocketchat.inputdriver"><application/><instrumentation android:name="local.pocketchat.inputdriver.NativeInputInstrumentation" android:targetPackage="local.pocketchat.inputdriver"/></manifest>')
        verifier=self.root/B.VERIFIER;verifier.parent.mkdir(parents=True);verifier.write_text('// synthetic verifier source\n')
        self.git('add','.');self.git('commit','-qm','Synthetic source')
        self.key=self.root/'work/gecko-integration/integration-test.jks';self.key.parent.mkdir(parents=True)
        self.key.write_bytes(b'synthetic-not-a-key')
        self.chain={name:self.root/'work/tools'/name for name in ('java','javac','jar','androidJar','aapt2','zipalign','apksigner','apksignerJar','d8')}
        for name,path in self.chain.items():path.parent.mkdir(parents=True,exist_ok=True);path.write_text('synthetic tool '+name)
        self.calls=[];self.mutate=False;self.mutate_shell=False;self.mutate_jar=False
        self.certificates=b'Verifies\nNumber of signers: 1\nV3.0 Signer: certificate SHA-256 digest: '+b'c'*64+b'\n'
        self.api_mutation=lambda value:None;self.api_raw=None;self.api_code=0
        self.verify_code=0
        self.real_run=subprocess.run
        self.env=patch.dict(os.environ,GITHUB_RUN_ID='1234',GITHUB_RUN_ATTEMPT='1');self.env.start();self.addCleanup(self.env.stop)

    def git(self,*args):
        return subprocess.check_output(['git','-c','user.name=Driver fixture','-c','user.email=fixture@example.invalid',*args],cwd=self.root,text=True,stderr=subprocess.PIPE).strip()

    def tool(self,parts,**kwargs):
        if parts[0]=='git':return self.real_run(parts,**kwargs)
        self.calls.append(parts);name=Path(parts[0]).name
        if name=='jar':Path(parts[2]).write_bytes(b'synthetic jar')
        elif name=='java' and 'com.android.tools.r8.D8' in parts:(Path(parts[parts.index('--output')+1])/'classes.dex').write_bytes(b'synthetic dex')
        elif name=='aapt2':
            with zipfile.ZipFile(parts[parts.index('-o')+1],'w') as archive:
                assets=Path(parts[parts.index('-A')+1]);archive.write(assets/B.ASSET,'assets/'+B.ASSET)
        elif name=='zipalign':shutil.copy2(parts[-2],parts[-1])
        elif name=='java' and '-jar' in parts and 'sign' in parts:shutil.copy2(parts[-1],parts[parts.index('--out')+1])
        elif name=='java' and '-jar' in parts and 'verify' in parts:
            if self.mutate_shell:(self.root/'tests/native-input-driver/NativeInputShell.java').write_text('shell changed mid-build')
            if self.mutate_jar:self.chain['apksignerJar'].write_text('changed after stamp')
            if self.mutate:(self.root/'tests/native-input-driver/NativeInputInstrumentation.java').write_text('changed mid-build')
            return subprocess.CompletedProcess(parts,self.verify_code,stdout=self.certificates,stderr=b'original signature diagnostics\n')
        elif name=='java' and 'VerifyNativeInputSignature' in parts:
            at=parts.index('VerifyNativeInputSignature');apk,verifier,source,tree,run,attempt=parts[at+1:]
            value=dict(schema=1,status='passed',error='',sourceCommit=source,sourceTree=tree,runId=run,runAttempt=attempt,
                apkSha256=B.sha(apk),apkBytes=Path(apk).stat().st_size,apksignerJarSha256=B.sha(self.chain['apksignerJar']),
                verifierSourceSha256=B.sha(verifier),loadedApksignerJarPath=str(self.chain['apksignerJar'].resolve()),
                inputsUnchangedDuringVerification=True,verified=True,containsErrors=False,
                effectiveSignerCertificateSha256=['c'*64],lineagePresent=False,lineageCertificateSha256=[],noRotation=True,
                ignoredV1SignerCertificateSha256=[],v32Detected=False,signerCertificateSha256='c'*64,
                schemes=[dict(name=n,verified=n in ('v2','v3'),signerCertificateSha256=['c'*64] if n in ('v2','v3') else [],
                  signers=[dict(certificateSha256='c'*64,certificateChainSha256=['c'*64],containsErrors=False,
                    lineagePresent=False,lineageCertificateSha256=[],rotationTargetsDevRelease=False,signerTargetsDevRelease=False)]
                    if n in ('v2','v3') else []) for n in ('v1','v2','v3','v31','v4')])
            self.api_mutation(value)
            raw=self.api_raw if self.api_raw is not None else (json.dumps(value)+'\n').encode()
            return subprocess.CompletedProcess(parts,self.api_code,stdout=raw,stderr=b'original API diagnostics\xff\n')
        return subprocess.CompletedProcess(parts,0,stdout=b'',stderr=b'')

    def build(self,**kwargs):
        with patch.object(B,'tools',return_value=(self.chain,{'syntheticTools':True,'buildTools':'37.0.0','tools':{k:dict(path=str(v.resolve()),sha256=B.sha(v)) for k,v in self.chain.items()}})),patch.object(B.subprocess,'run',side_effect=self.tool):
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
        for field in ('signatureLogs','signatureApiLogs'):
            for name,digest in result[field].items():self.assertEqual(B.sha(out/name),digest)
        self.assertEqual(result['signatureApiSha256'],B.sha(out/B.API))
        self.assertEqual(result['signatureCliReturnCode'],0);self.assertEqual(result['signatureApiReturnCode'],0)
        self.assertEqual(json.loads((out/B.ASSET).read_bytes()),result)
        with zipfile.ZipFile(out/'native-input-driver.apk') as archive:asset=json.loads(archive.read('assets/'+B.ASSET))
        self.assertNotIn('apkSha256',asset);self.assertEqual(asset['inputs'],result['inputs'])
        expected_execution=dict(executionBackend='shell-input-manager-global-v1',
            entryPoint='local.pocketchat.inputdriver.NativeInputShell',executionUid=2000,inputTargetUidEnforced=True)
        for key,value in expected_execution.items():
            self.assertEqual(result[key],value);self.assertIs(type(result[key]),type(value))
            self.assertEqual(asset[key],value);self.assertIs(type(asset[key]),type(value))
        self.assertEqual(set(result['inputs']),{'tests/native-input-driver/'+name for name in
            ('NativeInputInstrumentation.java','NativeGestureProtocol.java','NativeInputShell.java','AndroidManifest.xml')})
        shell='tests/native-input-driver/NativeInputShell.java'
        self.assertEqual(asset['inputs'][shell],B.sha(self.root/shell))
        self.assertTrue(any(Path(c[0]).name=='javac' and str(self.root/shell) in c for c in self.calls))
        self.assertEqual(set(result['signatureLogs'])|set(result['signatureApiLogs'])|{B.API,'native-input-driver.apk',B.ASSET},
            {'native-input-driver-signature-stdout.log','native-input-driver-signature-stderr.log',
             'native-input-driver-signature-api-stdout.log','native-input-driver-signature-api-stderr.log',
             'native-input-driver-signature-api.json','native-input-driver.apk','native-input-driver-build.json'})
        signs=[c for c in self.calls if Path(c[0]).name=='java' and 'sign' in c]
        self.assertEqual(len(signs),1);self.assertEqual(signs[0][signs[0].index('--ks')+1],str(self.key))
        self.assertEqual(signs[0][:3],[str(self.chain['java']),'-jar',str(self.chain['apksignerJar'])])
        self.assertFalse(any(Path(c[0]).name=='apksigner' for c in self.calls))

    def test_missing_shell_entry_source_rejected_before_compile(self):
        (self.root/'tests/native-input-driver/NativeInputShell.java').unlink()
        self.git('add','.');self.git('commit','-qm','Synthetic missing shell source')
        with self.assertRaisesRegex(ValueError,'shell entry source'):self.build()
        self.assertEqual(self.calls,[])

    def test_shell_entry_changed_after_compile_cannot_publish(self):
        self.mutate_shell=True
        with self.assertRaisesRegex(ValueError,'clean committed'):self.build()
        self.assertFalse((self.key.parent/'native-input-driver.apk').exists())
        self.assertFalse((self.key.parent/B.ASSET).exists())

    def test_foreign_instrumentation_target_rejected_before_compile(self):
        self.manifest.write_text(self.manifest.read_text().replace('android:targetPackage="local.pocketchat.inputdriver"','android:targetPackage="local.pocketchat.test"'))
        with self.assertRaisesRegex(ValueError,'target only'):B.inputs(self.root)
        self.assertEqual(self.calls,[])

    def test_shared_uid_rejected_before_compile_or_signing(self):
        original=self.manifest.read_text()
        for shared_uid in ('android.uid.system','android.uid.shell',''):
            self.manifest.write_text(original.replace(
                'package="local.pocketchat.inputdriver"',
                'package="local.pocketchat.inputdriver" android:sharedUserId="'+shared_uid+'"'))
            self.git('add','.');self.git('commit','-qm','Synthetic shared UID '+repr(shared_uid))
            with self.subTest(shared_uid=shared_uid),self.assertRaisesRegex(ValueError,'sharedUserId'):self.build()
            self.assertEqual(self.calls,[])
            self.assertFalse((self.key.parent/B.ASSET).exists())

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
        self.assertFalse(any('sign' in c for c in self.calls))

    def test_source_changed_after_compile_cannot_publish(self):
        self.mutate=True
        with self.assertRaisesRegex(ValueError,'clean committed'):self.build()
        self.assertFalse((self.key.parent/'native-input-driver.apk').exists())
        self.assertFalse((self.key.parent/B.ASSET).exists())

    def test_loaded_jar_changed_after_toolchain_stamp_rejected(self):
        self.mutate_jar=True
        with self.assertRaisesRegex(ValueError,'API implementation identity'):self.build()
        self.assertFalse((self.key.parent/B.ASSET).exists())
        self.assertFalse((self.key.parent/'native-input-driver.apk').exists())

    def test_signature_verifier_symlink_rejected_before_signing(self):
        verifier=self.root/B.VERIFIER;verifier.unlink();verifier.symlink_to(self.manifest)
        self.git('add','.');self.git('commit','-qm','Synthetic linked verifier')
        with self.assertRaisesRegex(ValueError,'regular signature verifier'):self.build()
        self.assertFalse(any('sign' in c for c in self.calls))

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

    def test_cli_format_is_diagnostic_only_and_raw_preserved(self):
        for raw in (self.certificates,b'Signer #1 certificate SHA-256 digest: '+b'c'*64+b'\n',b'changed future CLI formatting\xff\n'):
            self.certificates=raw
            result=self.build()
            self.assertEqual(result['signerCertificateSha256'],'c'*64)
            self.assertEqual((self.key.parent/'native-input-driver-signature-stdout.log').read_bytes(),raw)

    def test_api_false_identities_and_signer_evidence_fail_closed(self):
        changes=[('sourceCommit','0'*40),('sourceTree','0'*40),('runId','2'),('runAttempt','2'),('apkSha256','0'*64),
                 ('apkBytes',0),('apksignerJarSha256','0'*64),('verifierSourceSha256','0'*64),('loadedApksignerJarPath','/other.jar'),
                 ('inputsUnchangedDuringVerification',False),('verified',False),('containsErrors',True),('status','failed'),
                 ('effectiveSignerCertificateSha256',[]),('effectiveSignerCertificateSha256',['c'*64,'d'*64]),
                 ('lineagePresent',True),('lineageCertificateSha256',['c'*64]),('noRotation',False),
                 ('ignoredV1SignerCertificateSha256',['c'*64]),('v32Detected',True),('error','failed')]
        for key,value in changes:
            with self.subTest(key=key,value=value):
                self.api_mutation=lambda row,k=key,v=value:row.update({k:v})
                with self.assertRaises((ValueError,KeyError)):self.build()
                self.assertFalse((self.key.parent/B.ASSET).exists())
                self.assertFalse((self.key.parent/'native-input-driver.apk').is_file())
        for change in ('missing','multi','different','unverified','chain','error','lineage','rotationDev','signerDev'):
            def mutate(row):
                scheme=row['schemes'][2];signer=scheme['signers'][0]
                if change=='missing':scheme['signerCertificateSha256']=[]
                elif change=='multi':scheme['signerCertificateSha256'].append('c'*64)
                elif change=='different':scheme['signerCertificateSha256']=['d'*64]
                elif change=='unverified':scheme['verified']=False
                elif change=='chain':signer['certificateChainSha256'].append('d'*64)
                elif change=='error':signer['containsErrors']=True
                elif change=='lineage':signer['lineagePresent']=True
                elif change=='rotationDev':signer['rotationTargetsDevRelease']=True
                elif change=='signerDev':signer['signerTargetsDevRelease']=True
            self.api_mutation=mutate
            with self.subTest(change=change),self.assertRaises(ValueError):self.build()

    def test_api_bad_json_nonzero_and_original_bytes_kept(self):
        for raw in (b'not json\xff',b'{"schema":1,"schema":1}',b'{"schema":NaN}'):
            self.api_raw=raw
            with self.assertRaises((ValueError,UnicodeError)):self.build()
            self.assertEqual((self.key.parent/B.API).read_bytes(),raw)
            self.assertEqual((self.key.parent/'native-input-driver-signature-api-stdout.log').read_bytes(),raw)
            self.assertEqual((self.key.parent/'native-input-driver-signature-api-stderr.log').read_bytes(),b'original API diagnostics\xff\n')
        self.api_raw=None;self.api_code=1
        with self.assertRaises(subprocess.CalledProcessError):self.build()
        self.assertFalse((self.key.parent/B.ASSET).exists())

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
