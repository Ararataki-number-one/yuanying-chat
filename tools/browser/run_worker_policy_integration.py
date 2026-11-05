#!/usr/bin/env python3
"""Run a fresh real Android production Worker-policy save/reload/route workload."""
import argparse
import hashlib
import json
from pathlib import Path
import re
import shlex
import subprocess
import sys
import time
import uuid

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'tools/gecko'))
from profile_invocation_contract import expected_build,verify_installed
sys.path.insert(0,str(Path(__file__).resolve().parent))
from fingerprint_fixture_server import EphemeralCertificates,AndroidUserCa,GUEST_PORT
from newworker_fixture_server import WorkerFixtureServer
from check_worker_policy_evidence import verify_worker_policy_evidence,strict_json


def activity_start_args(nonce,source,leaf,ca):
    if not re.fullmatch('[0-9a-f]{32}',nonce) or not re.fullmatch('[0-9a-f]{40}',source) or not all(re.fullmatch('[0-9a-f]{64}',value) for value in (leaf,ca)):raise ValueError('Invalid source-bound Worker launch')
    tokens=['am','start','-W','-n','local.pocketchat.test/local.pocketchat.WorkerPolicyIntegrationActivity','--es','runNonce',nonce,'--es','sourceCommit',source,'--ei','fixturePort',str(GUEST_PORT),'--es','fixtureEngine','chromium','--es','expectedLeafSha256',leaf,'--es','publicCaPemSha256',ca]
    return ['shell',shlex.join(tokens)]

def source_inputs():
    paths=[ROOT/name for name in ['tools/browser/run_worker_policy_integration.py','tools/browser/check_worker_policy_evidence.py','tools/browser/newworker_fixture_server.py','tools/browser/fingerprint_fixture_server.py','tests/gecko/AndroidManifest.xml','tests/gecko/WorkerPolicyIntegrationActivity.java','tests/gecko/WorkerPolicyEvidenceProvider.java','tests/gecko/BrowserFingerprintFixture.java','tests/gecko/BrowserFingerprintIntegrationActivity.java','tests/gecko/IntegrationBuildIdentity.java','tests/gecko/assets/worker-policy-page.js','tests/gecko/res/xml/network_security.xml','app/build.gradle','app/src/main/AndroidManifest.xml','app/src/main/res/xml/network_security.xml','.github/workflows/browser-2_1-acceptance.yml']]
    paths+=list((ROOT/'app/src/main/java/local/pocketchat').glob('*.java'))+list((ROOT/'app/src/main/assets').rglob('*.js'))
    return sorted(set(paths))

def read_activity(raw,nonce,source,identity):
    if len(raw)>1024*1024:raise ValueError('Synthetic Worker report exceeds bound')
    try:value=json.loads(raw)
    except (ValueError,UnicodeDecodeError):return None
    if type(value) is not dict or value.get('runNonce')!=nonce:return None
    # Reject duplicate fields and non-finite values in the original device
    # bytes before reserialization can hide them from the final strict checker.
    value=strict_json(raw)
    if value.get('sourceCommit')!=source or value.get('engine')!='chromium':raise ValueError('Worker source/engine differs')
    verify_installed(value.get('buildIdentity',{}),identity)
    return value

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--adb',default='adb');p.add_argument('--serial',default='emulator-5554');p.add_argument('--output',type=Path,default=ROOT/'work/browser-acceptance');a=p.parse_args()
    if a.serial!='emulator-5554':p.error('Only the controlled emulator target is allowed')
    if subprocess.check_output(['git','status','--porcelain'],cwd=ROOT,text=True).strip():raise ValueError('Clean committed Worker source required')
    a.output.mkdir(parents=True,exist_ok=True)
    def adb(*args,check=True,timeout=30):return subprocess.run([a.adb,'-s',a.serial,*args],check=check,capture_output=True,timeout=timeout)
    source=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip();tree=subprocess.check_output(['git','rev-parse','HEAD^{tree}'],cwd=ROOT,text=True).strip();settings=(ROOT/'app/build.gradle').read_text()
    identity=expected_build(ROOT/'app/build/outputs/apk/integration/app-x86_64-integration.apk',source,tree,re.search(r"versionName '([^']+)'",settings).group(1),int(re.search(r'versionCode (\d+)',settings).group(1)))
    paths=source_inputs();hashes={str(path.relative_to(ROOT)):hashlib.sha256(path.read_bytes()).hexdigest() for path in paths};nonce=uuid.uuid4().hex
    results={};error=None;certificates=None;server=None;ca=None;reversed_port=False;host_tls={}
    report=dict(schema=1,status='running',sourceCommit=source,sourceTree=tree,runNonce=nonce,expectedBuildIdentity=identity,actualAndroidExecution=False,actualAndroidWebViewExecution=False,actualNativeServiceWorkerSettingExecution=False,actualGeckoExecution=False,actualDesktopChromiumExecution=False,actualPublicWebsiteExecution=False,actualDevicePerformanceMeasurement=False)
    try:
        if adb('shell','getprop','ro.kernel.qemu').stdout.decode().strip()!='1':raise ValueError('Actual controlled Android emulator required')
        installed=json.loads(adb('exec-out','content','read','--uri','content://local.pocketchat.test.evidence/build-identity').stdout);verify_installed(installed,identity)
        certificates=EphemeralCertificates();binding=dict(sourceCommit=source,sourceTree=tree,runNonce=nonce,integrationApkSha256=identity['apkSha256'],sdkRunId=identity['sdkBuildIdentity']['runId'],sdkRunAttempt=identity['sdkBuildIdentity']['runAttempt'])
        server=WorkerFixtureServer(certificates,(ROOT/'tests/gecko/assets/worker-policy-page.js').read_text(),binding).start();ca=AndroidUserCa(adb,certificates);ca.install()
        if any(('tcp:'+str(GUEST_PORT)) in line.split() for line in adb('reverse','--list').stdout.decode('ascii').splitlines()):raise ValueError('Guest Worker port already mapped; refusing replacement')
        reversed_port=True;adb('reverse','tcp:'+str(GUEST_PORT),'tcp:'+str(server.port));host_tls=dict(certificates.public,binding=binding,trustInstallation=ca.receipt,guestPort=GUEST_PORT)
        if adb('shell','pm','clear','local.pocketchat.test').stdout.decode().strip()!='Success':raise ValueError('Fresh integration-only Worker data required')
        if adb('shell','id','-u').stdout.decode().strip()!='2000':raise ValueError('Worker shell evidence requires UID2000')
        adb('shell','am','force-stop','local.pocketchat.test');server.begin('chromium');adb(*activity_start_args(nonce,source,certificates.leaf_sha,certificates.ca_sha));deadline=time.monotonic()+300;current=None
        while time.monotonic()<deadline:
            raw=adb('exec-out','content','read','--uri','content://local.pocketchat.test.worker-policy-evidence/chromium',check=False,timeout=15).stdout
            value=read_activity(raw,nonce,source,identity)
            if value is None:time.sleep(.2);continue
            current=value
            if value.get('status') in ('passed','failed'):break
            time.sleep(.2)
        if current is not None:results['chromium']=current
        if current is None or current.get('status')!='passed':raise AssertionError('Worker fixture failed or timed out: '+str((current or {}).get('phase','unavailable'))+' / '+str((current or {}).get('failure','no terminal report')))
        report.update(status='passed',actualAndroidExecution=True,actualAndroidWebViewExecution=True,actualNativeServiceWorkerSettingExecution=True)
    except Exception as failure:error=failure;report.update(status='failed',error=type(failure).__name__+': '+str(failure))
    finally:
        cleanup=[lambda:adb('shell','am','force-stop','local.pocketchat.test')]
        if server is not None:cleanup.append(server.close)
        if reversed_port:
            def remove_reverse():adb('reverse','--remove','tcp:'+str(GUEST_PORT));host_tls['reverseRemoved']=True
            cleanup.append(remove_reverse)
        if ca is not None:cleanup.append(ca.remove)
        if certificates is not None:
            def remove_material():certificates.close();host_tls['privateMaterialRemoved']=not certificates.directory.exists()
            cleanup.append(remove_material)
        for action in cleanup:
            try:action()
            except Exception as cleanup_failure:
                report.setdefault('cleanupErrors',[]).append(type(cleanup_failure).__name__)
                if error is None:error=cleanup_failure;report['error']='Ephemeral Worker cleanup failed'
                report['status']='failed'
        if server is not None and 'chromium' in results:
            # Stop the native app and close/join host connections first. The
            # final absence check must include requests arriving after terminal
            # publication, rather than freeze a still-running host snapshot.
            results['chromium']['fixture']=server.snapshot('chromium')
        unchanged=all(path.is_file() and hashlib.sha256(path.read_bytes()).hexdigest()==hashes[str(path.relative_to(ROOT))] for path in paths)
        report.update(hostTls=host_tls,sourceFiles=hashes,executionInputsUnchanged=unchanged,results=results,fingerprintProtectionVerified=False,workerCoverageVerified=False,serviceWorkerCoverageVerified=False,existingExecutionControlled=False,scope='Actual controlled Android BrowserActivity policy save/reload and native SW network settings with same/cross-origin new-Worker probes and independent HTTPS host requests. Existing cache execution explicitly remains; no full Worker fingerprint, termination, in-flight cancellation, public-site or performance claim.')
        if not unchanged:error=error or ValueError('Worker execution inputs changed');report.update(status='failed',error='Worker execution inputs changed')
        output=a.output/'worker-policy-results.json';output.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
        if error is None:
            try:verify_worker_policy_evidence(a.output,source,identity)
            except Exception as rejected:error=rejected;report.update(status='failed',validationError=str(rejected));output.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
        print(json.dumps(dict(status=report['status'],sourceCommit=source,runNonce=nonce,output=str(output))))
    if error:raise error

if __name__=='__main__':main()
