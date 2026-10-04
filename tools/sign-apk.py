#!/usr/bin/env python3
"""Sign the assembled production ARM64 APK locally; never upload the keystore."""
import argparse, hashlib, json, os, pathlib, re, subprocess

root=pathlib.Path(__file__).resolve().parents[1]
settings=(root/'app/build.gradle').read_text()
version=re.search(r"versionName '([0-9]+\.[0-9]+\.[0-9]+)'",settings).group(1)
version_code=int(re.search(r'versionCode ([0-9]+)',settings).group(1))
parser=argparse.ArgumentParser()
parser.add_argument('apk',type=pathlib.Path)
parser.add_argument('--key',type=pathlib.Path,default=root/'work/android-test/private/local-test.jks')
parser.add_argument('--tools',type=pathlib.Path,default=root/'work/gecko-sdk-validation/sdk/build-tools/37.0.0')
parser.add_argument('--output',type=pathlib.Path,default=root/f'dist/PocketChat-{version}-gecko-arm64.apk')
local_java=root/'work/cloud-setup/jdk/usr/lib/jvm/java-17-openjdk-amd64/bin/java'
parser.add_argument('--java',default=str(local_java) if local_java.exists() else 'java')
args=parser.parse_args()
if not args.key.is_file():parser.error('Original keystore is missing; do not generate a replacement key.')
args.output.parent.mkdir(parents=True,exist_ok=True)
aligned=args.output.parent/'gecko-aligned-unsigned.apk'
java=args.java
signer=args.tools/'lib/apksigner.jar'
env=dict(os.environ)
# User-supplied original test keystore uses the project's documented local passwords.
env['POCKET_STORE_PASSWORD']='android';env['POCKET_KEY_PASSWORD']='android'
subprocess.run([str(args.tools/'zipalign'),'-f','-P','16','4',str(args.apk),str(aligned)],check=True)
subprocess.run([str(java),'-jar',str(signer),'sign','--ks',str(args.key),'--ks-key-alias','local',
    '--ks-pass','env:POCKET_STORE_PASSWORD','--key-pass','env:POCKET_KEY_PASSWORD','--out',str(args.output),str(aligned)],check=True,env=env)
cert=subprocess.check_output([str(java),'-jar',str(signer),'verify','--verbose','--print-certs',str(args.output)],text=True)
digests=re.findall(r'certificate SHA-256 digest: ([0-9a-f]{64})',cert)
assert digests and set(digests)=={'f0afa2ef2b9ac68020b374276318b12d2bb4de65d2a3b788194de551356b9434'},'Signing certificate does not match original app.'
badging=subprocess.check_output([str(args.tools/'aapt2'),'dump','badging',str(args.output)],text=True)
assert f"package: name='local.pocketchat' versionCode='{version_code}' versionName='{version}'" in badging,badging.splitlines()[0]
import zipfile
with zipfile.ZipFile(args.output) as archive:assert 'assets/network-fixture.p12' not in archive.namelist(),'Synthetic TLS key must never appear in production APK'
assert 'application-debuggable' not in badging,'Release must not enable debugging.'
manifest=subprocess.check_output([str(args.tools/'aapt2'),'dump','xmltree',str(args.output),'--file','AndroidManifest.xml'],text=True)
assert all(name not in manifest for name in ['GeckoIntegrationTestActivity','ProfileGeckoIntegrationActivity','AppUpdateIntegrationActivity','GeckoUploadFixtureProvider','EnvironmentManagementIntegrationActivity','UiVisualIntegrationActivity','NetworkOptimizationIntegrationActivity']),'Test component present in release.'
subprocess.run([str(args.tools/'zipalign'),'-c','-P','16','4',str(args.output)],check=True)
receipt={'file':args.output.name,'package':'local.pocketchat','version':version,'versionCode':version_code,'bytes':args.output.stat().st_size,
    'sha256':hashlib.sha256(args.output.read_bytes()).hexdigest(),'unsignedSha256':hashlib.sha256(args.apk.read_bytes()).hexdigest(),'signerSha256':digests[0],'debuggable':False,'testActivitiesPresent':False}
(args.output.parent/'gecko-apk-verification.json').write_text(json.dumps(receipt,indent=2)+'\n')
print(json.dumps(receipt))
