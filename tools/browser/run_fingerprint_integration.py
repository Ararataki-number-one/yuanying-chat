#!/usr/bin/env python3
"""Run both production browser UIs and early-document fingerprint probes on real Android."""
import argparse
import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys
import time
import uuid

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'tools/gecko'))
from profile_invocation_contract import expected_build,verify_installed
sys.path.insert(0,str(Path(__file__).resolve().parent))
from fingerprint_fixture_server import EphemeralCertificates,FingerprintServer,AndroidUserCa,GUEST_PORT


def source_inputs():
    paths=[ROOT/'tools/browser/run_fingerprint_integration.py',ROOT/'tools/browser/check_fingerprint_evidence.py',ROOT/'tools/browser/fingerprint_fixture_server.py',ROOT/'tests/gecko/AndroidManifest.xml',ROOT/'app/build.gradle',ROOT/'app/src/main/AndroidManifest.xml',ROOT/'app/src/main/res/xml/network_security.xml',ROOT/'.github/workflows/browser-2_1-acceptance.yml']
    paths+=list((ROOT/'app/src/main/java/local/pocketchat').glob('*.java'))
    paths+=list((ROOT/'app/src/main/assets').rglob('*.js'))
    paths+=list((ROOT/'tests/gecko').glob('BrowserFingerprint*.java'))
    paths+=[ROOT/'tests/gecko/IntegrationBuildIdentity.java',ROOT/'tests/gecko/assets/browser-fingerprint-page.js']
    paths+=[ROOT/'tests/gecko/res/xml/network_security.xml']
    return sorted(set(paths))


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--adb',default='adb');p.add_argument('--serial',default='emulator-5554');p.add_argument('--output',type=Path,default=ROOT/'work/browser-acceptance');a=p.parse_args()
    if a.serial!='emulator-5554':p.error('Only the controlled emulator target is allowed')
    if subprocess.check_output(['git','status','--porcelain'],cwd=ROOT,text=True).strip():raise ValueError('Clean committed source required')
    a.output.mkdir(parents=True,exist_ok=True)
    def adb(*args,check=True,timeout=30):return subprocess.run([a.adb,'-s',a.serial,*args],check=check,capture_output=True,timeout=timeout)
    source=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip();tree=subprocess.check_output(['git','rev-parse','HEAD^{tree}'],cwd=ROOT,text=True).strip()
    settings=(ROOT/'app/build.gradle').read_text();identity=expected_build(ROOT/'app/build/outputs/apk/integration/app-x86_64-integration.apk',source,tree,re.search(r"versionName '([^']+)'",settings).group(1),int(re.search(r'versionCode (\d+)',settings).group(1)))
    paths=source_inputs();hashes={str(path.relative_to(ROOT)):hashlib.sha256(path.read_bytes()).hexdigest() for path in paths}
    nonce=uuid.uuid4().hex;results={};error=None;certificates=None;server=None;ca=None;reversed_port=False;host_tls={}
    report=dict(schema=1,status='running',sourceCommit=source,sourceTree=tree,runNonce=nonce,expectedBuildIdentity=identity,actualAndroidExecution=False,actualAndroidWebViewExecution=False,actualGeckoExecution=False,actualDesktopChromiumExecution=False,actualPublicWebsiteExecution=False,actualDevicePerformanceMeasurement=False)
    try:
        if adb('shell','getprop','ro.kernel.qemu').stdout.decode().strip()!='1':raise ValueError('Actual controlled Android emulator required')
        installed=json.loads(adb('exec-out','content','read','--uri','content://local.pocketchat.test.evidence/build-identity').stdout);verify_installed(installed,identity)
        certificates=EphemeralCertificates()
        binding=dict(sourceCommit=source,sourceTree=tree,runNonce=nonce,integrationApkSha256=identity['apkSha256'],sdkRunId=identity['sdkBuildIdentity']['runId'],sdkRunAttempt=identity['sdkBuildIdentity']['runAttempt'])
        server=FingerprintServer(certificates,(ROOT/'tests/gecko/assets/browser-fingerprint-page.js').read_text(),binding).start()
        ca=AndroidUserCa(adb,certificates);ca.install()
        reverse_list=adb('reverse','--list').stdout.decode('ascii')
        if any(('tcp:'+str(GUEST_PORT)) in line.split() for line in reverse_list.splitlines()):raise ValueError('Guest fixture port already mapped; refusing replacement')
        reversed_port=True;adb('reverse','tcp:'+str(GUEST_PORT),'tcp:'+str(server.port))
        host_tls=dict(certificates.public,binding=binding,trustInstallation=ca.receipt,guestPort=GUEST_PORT)
        # Fresh test-only data prevents a previous run's desktop policy, receipts or WebView profile from qualifying.
        if adb('shell','pm','clear','local.pocketchat.test').stdout.decode().strip()!='Success':raise ValueError('Fresh integration-only app data required')
        for engine,component,budget in [('chromium','BrowserFingerprintIntegrationActivity',330),('gecko','BrowserFingerprintIntegrationActivity$Gecko',150)]:
            adb('shell','am','force-stop','local.pocketchat.test')
            server.begin(engine)
            adb('shell','am','start','-W','-n','local.pocketchat.test/local.pocketchat.'+component,'--es','runNonce',nonce,'--es','sourceCommit',source,'--ei','fixturePort',str(GUEST_PORT),'--es','fixtureEngine',engine,'--es','expectedLeafSha256',certificates.leaf_sha,'--es','publicCaPemSha256',certificates.ca_sha)
            deadline=time.monotonic()+budget;current=None
            while time.monotonic()<deadline:
                raw=adb('exec-out','content','read','--uri','content://local.pocketchat.test.browser-fingerprint-evidence/'+engine,check=False,timeout=15).stdout
                if len(raw)>1024*1024:raise ValueError('Synthetic report exceeds bound')
                try:value=json.loads(raw)
                except (ValueError,UnicodeDecodeError):time.sleep(.2);continue
                if value.get('runNonce')!=nonce:time.sleep(.2);continue
                if value.get('sourceCommit')!=source or value.get('engine')!=engine:raise ValueError('Fixture invocation source/engine differs')
                verify_installed(value.get('buildIdentity',{}),identity);current=value
                if value.get('status') in ('passed','failed'):break
                time.sleep(.2)
            if current is None or current.get('status')!='passed':
                if current is not None:results[engine]=current
                raise AssertionError(engine+' fixture failed or timed out: '+str((current or {}).get('stage','unavailable'))+' / '+str((current or {}).get('failure','no terminal report')))
            current['fixture']=server.snapshot(engine)
            results[engine]=current
        report.update(status='passed',actualAndroidExecution=True,actualAndroidWebViewExecution=True,actualGeckoExecution=True)
    except Exception as failure:
        error=failure;report.update(status='failed',error=type(failure).__name__+': '+str(failure))
    finally:
        # No private bytes or certificate files enter the output directory or APK.
        cleanup=[lambda:adb('shell','am','force-stop','local.pocketchat.test')]
        if server is not None:cleanup.append(server.close)
        if reversed_port:
            def remove_reverse():
                adb('reverse','--remove','tcp:'+str(GUEST_PORT));host_tls['reverseRemoved']=True
            cleanup.append(remove_reverse)
        if ca is not None:cleanup.append(ca.remove)
        if certificates is not None:
            def remove_material():
                certificates.close();host_tls['privateMaterialRemoved']=not certificates.directory.exists()
            cleanup.append(remove_material)
        for action in cleanup:
            try:action()
            except Exception as cleanup_failure:
                report.setdefault('cleanupErrors',[]).append(type(cleanup_failure).__name__)
                if error is None:error=cleanup_failure;report['error']='Ephemeral fixture cleanup failed'
                report['status']='failed'
        unchanged=all(path.is_file() and hashlib.sha256(path.read_bytes()).hexdigest()==hashes[str(path.relative_to(ROOT))] for path in paths)
        report.update(hostTls=host_tls,sourceFiles=hashes,executionInputsUnchanged=unchanged,results=results,fingerprintProtectionVerified=False,workerCoverageVerified=False,serviceWorkerCoverageVerified=False,scope='Actual controlled Android/production browser UIs, native UA/UA-CH and document-start frames on two domain-scoped user-CA HTTPS origins using a fresh host-only /tmp TLS key. Ordinary Gecko URL UI and rejection of ChatGPT-only automation are also required. No screenshots, page/account content, cookies, public-site, physical-phone speed or complete fingerprint-protection claim.')
        if not unchanged:error=error or ValueError('Execution inputs changed');report.update(status='failed',error='Execution inputs changed')
        (a.output/'browser-fingerprint-results.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
        print(json.dumps(dict(status=report['status'],sourceCommit=source,runNonce=nonce,engines=list(results),output=str(a.output/'browser-fingerprint-results.json'))))
    if error:raise error


if __name__=='__main__':main()
