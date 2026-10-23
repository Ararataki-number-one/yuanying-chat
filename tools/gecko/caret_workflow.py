#!/usr/bin/env python3
"""Prepare exact source SDK inputs and record actual APKs for controlled editing."""
import argparse
import hashlib
import http.client
import json
import os
from pathlib import Path
import subprocess
import urllib.request
import zipfile
from sdk_identity_contract import ROOT, file_digest, sdk_from_apk
from caret_build_identity import audit_apk, embedded_identity, validate_sdk_receipt

ANNOTATION_SHA256='ddd072ddbb553178e205517ce777b2f05aa9e412982d9ecb4eedc74f1212f697'

def download_annotation(url, target, expected=ANNOTATION_SHA256):
    """Retry a locked build dependency only; no Android workload runs here."""
    if target.is_file() and file_digest(target)==expected:return
    for attempt in range(1,4):
        try:
            with urllib.request.urlopen(url,timeout=60) as response:data=response.read(1024*1024+1)
            if len(data)>1024*1024 or hashlib.sha256(data).hexdigest()!=expected:raise ValueError('Locked annotation dependency differs')
            staged=target.with_suffix('.download');staged.write_bytes(data);staged.replace(target);return
        except (OSError,http.client.HTTPException,ValueError) as error:
            print(json.dumps(dict(dependencyDownloadAttempt=attempt,status='failed',reason=str(error))),flush=True)
            if isinstance(error,urllib.error.HTTPError) and error.code in (401,403,404):raise
            if attempt==3:raise


def main():
    p=argparse.ArgumentParser()
    p.add_argument('mode',choices=['prepare','record'])
    p.add_argument('--work',required=True,type=Path)
    a=p.parse_args()
    native=ROOT/'work/native-caret-sdk'
    work=a.work.resolve()
    gradle=work/'gradle/gradle-9.8.0'
    annotation=work/'annotation-jvm-1.10.0.jar'
    base=['python3',str(ROOT/'tools/gecko/build_caret_sdk.py'),
          '--aar',str(work/'geckoview.aar'),'--pom',str(work/'geckoview.pom'),
          '--sources',str(work/'geckoview-sources.jar'),
          '--android-jar',str(Path(os.environ['ANDROID_HOME'])/'platforms/android-37.1/android.jar'),
          '--annotations-jar',str(annotation),'--kotlin-jar',str(gradle/'lib/kotlin-stdlib-2.4.10.jar'),
          '--javac',str(Path(os.environ['JAVA_HOME'])/'bin/javac'),
          '--out',str(native),'--run-id',os.environ['GITHUB_RUN_ID'],
          '--run-attempt',os.environ.get('GITHUB_RUN_ATTEMPT','1')]
    if a.mode=='prepare':
        url='https://dl.google.com/dl/android/maven2/androidx/annotation/annotation-jvm/1.10.0/annotation-jvm-1.10.0.jar'
        download_annotation(url,annotation)
        assert file_digest(annotation)==ANNOTATION_SHA256
        subprocess.run(base,cwd=ROOT,check=True)
        subprocess.run(['python3',str(ROOT/'tools/gecko/stage_caret_build_identity.py'),
            '--sdk-receipt',str(native/'sdk-build-receipt.json'),'--sdk-aar',str(native/'geckoview-caret.aar'),
            '--official-sdk-aar',str(work/'geckoview.aar'),'--root',str(ROOT),
            '--output',str(native/'integration-assets/caret-build-identity.json')],cwd=ROOT,check=True)
    else:
        subprocess.run(base+['--resolved-artifacts',str(native/'resolved-artifacts.json')],cwd=ROOT,check=True)
        sdk=validate_sdk_receipt(native/'sdk-build-receipt.json',native/'geckoview-caret.aar',ROOT,work/'geckoview.aar')
        identity=embedded_identity(sdk,native/'sdk-build-receipt.json')
        integration=ROOT/'app/build/outputs/apk/integration/app-x86_64-integration.apk'
        release=ROOT/'app/build/outputs/apk/release/app-arm64-v8a-release-unsigned.apk'
        audit=audit_apk(integration)
        assert audit['embeddedBuildIdentity']==identity
        audit_apk(release,package='local.pocketchat',component=None,require_fixture=False)
        for apk in (integration,release):
            with zipfile.ZipFile(apk)as archive:
                actual=sdk_from_apk(archive,sdk['sourceCommit'],sdk['sourceTree'])
                assert actual['sdkBuildReceiptSha256']==file_digest(native/'sdk-build-receipt.json')
        build=dict(identity,integrationApkSha256=file_digest(integration),releaseApkSha256=file_digest(release),
                   embeddedIdentityAssetSha256=audit['embeddedIdentityAssetSha256'])
        (work/'caret-apk-build-receipt.json').write_text(json.dumps(build,indent=2)+'\n')
        for source,target in [(native/'sdk-build-receipt.json',work/'sdk-build-receipt.json'),
                              (native/'derived-sdk-verification.json',work/'derived-sdk-verification.json'),
                              (ROOT/'third-party/sdk/geckoview-157.0.1-editable-selection.json',work/'derived-sdk-input.json')]:
            target.write_bytes(source.read_bytes())
        print(json.dumps(dict(status='passed',sourceCommit=sdk['sourceCommit'],
            actualCompiledApkHashes=True,actualAndroidExecution=False,releaseAcceptance=False)))


if __name__=='__main__':main()
