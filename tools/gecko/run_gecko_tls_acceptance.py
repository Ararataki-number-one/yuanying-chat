#!/usr/bin/env python3
"""Real production Gecko-web TLS cold profile/UI/persistent-SW/concurrent acceptance."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import shlex
import subprocess
import sys
import time
import uuid
from profile_invocation_contract import expected_build,verify_installed
from tls_acceptance_server import TlsAcceptanceServer,CASE_SPECS,GUEST_PORT,strict_json,require
from tls_acceptance_contract import validate_device,validate_wire,validate_cross
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'tools/browser'))
from fingerprint_fixture_server import EphemeralCertificates,AndroidUserCa
PACKAGE='local.pocketchat.test'

def sha(path):
    digest=hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda:stream.read(65536),b''):digest.update(block)
    return digest.hexdigest()

def snapshot():
    paths=subprocess.check_output(['git','ls-files','-z'],cwd=ROOT).decode().split('\0')
    return {name:sha(ROOT/name) for name in paths if name and (ROOT/name).is_file()}

def finish_resources(adb,cold_stop,server,certificates,ca,reversed_port,cleanup,errors,host_tls):
    try:
        cold_stop();cleanup['appStopped']=True
        require(adb('shell','pm','clear',PACKAGE).stdout.strip()==b'Success','integration data/proxy cleanup');cleanup['appDataCleared']=True
    except Exception as error:errors.append(dict(stage='app-cleanup',errorType=type(error).__name__))
    if reversed_port:
        try:adb('reverse','--remove','tcp:'+str(GUEST_PORT));cleanup['reverseRemoved']=True;host_tls['reverseRemoved']=True
        except Exception as error:errors.append(dict(stage='reverse-cleanup',errorType=type(error).__name__))
    if server is not None:
        try:server.close();cleanup['serverClosed']=server.closed;cleanup['serverThreadsJoined']=server.joined
        except Exception as error:errors.append(dict(stage='server-cleanup',errorType=type(error).__name__))
    if ca is not None:
        try:ca.remove();cleanup['caRemoved']=True
        except Exception as error:errors.append(dict(stage='public-ca-cleanup',errorType=type(error).__name__))
    if certificates is not None:
        try:certificates.close();cleanup['privateMaterialRemoved']=not certificates.directory.exists();host_tls['privateMaterialRemoved']=cleanup['privateMaterialRemoved']
        except Exception as error:errors.append(dict(stage='private-material-cleanup',errorType=type(error).__name__))
    try:cleanup['shellUidRestored']=adb('shell','id','-u').stdout.strip()==b'2000'
    except Exception as error:errors.append(dict(stage='shell-cleanup',errorType=type(error).__name__))
    return server.snapshot() if server else None

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--adb',default='adb');p.add_argument('--serial',default='emulator-5554');p.add_argument('--apk',required=True,type=Path);p.add_argument('--source',required=True);p.add_argument('--output',required=True,type=Path);a=p.parse_args()
    source=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip();tree=subprocess.check_output(['git','rev-parse','HEAD^{tree}'],cwd=ROOT,text=True).strip()
    require(a.serial=='emulator-5554' and a.source==source and re.fullmatch('[0-9a-f]{40}',source),'exact controlled source/emulator')
    require(not subprocess.check_output(['git','status','--porcelain'],cwd=ROOT,text=True).strip(),'clean immutable selected source')
    output=a.output.absolute();require(not output.exists() and all(not q.is_symlink() for q in (output,*output.parents)),'fresh ordinary output')
    gradle=(ROOT/'app/build.gradle').read_text();identity=expected_build(a.apk,source,tree,re.search(r"versionName '([^']+)'",gradle)[1],int(re.search(r'versionCode ([0-9]+)',gradle)[1]))
    before=snapshot();output.mkdir(parents=True);run=uuid.uuid4().hex
    server=certificates=ca=None;reversed_port=False;entries=[];process_checks=[];errors=[];host_tls={};guest={};checked=None
    cleanup=dict(appStopped=False,appDataCleared=False,reverseRemoved=False,serverClosed=False,serverThreadsJoined=False,caRemoved=False,privateMaterialRemoved=False,shellUidRestored=False)
    def adb(*parts,check=True,timeout=25):return subprocess.run([a.adb,'-s',a.serial,*parts],capture_output=True,check=check,timeout=timeout)
    def cold_stop():
        adb('shell','am','force-stop',PACKAGE)
        for slot in (1,2):require(not adb('shell','pidof',PACKAGE+':profile'+str(slot),check=False).stdout.strip(),'old environment remains alive')
    def collect(spec):
        label,slot,mode,rfp,retain,stale,resample,version,success,service=spec;case=uuid.uuid4().hex;binding=server.begin(label,case)
        entry=dict(label=label,binding=binding,status='failed');entries.append(entry)
        command=['am','start','-W','-n',PACKAGE+'/local.pocketchat.GeckoTlsAcceptanceActivity$Profile'+str(slot),'--es','runNonce',run,'--es','caseNonce',case,'--es','sourceCommit',source,'--es','tlsMode',mode,'--es','expectedLeafSha256',certificates.leaf_sha,'--ei','peerPort',str(binding['port'])]
        for key,value in dict(rfp=rfp,retain=retain,staleUser=stale,resample=resample,expectSuccess=success,service=service,saveDefault=label=='pending-default-tls12').items():command+=['--ez',key,str(value).lower()]
        adb('shell',shlex.join(command));deadline=time.monotonic()+150;device=None
        while time.monotonic()<deadline:
            raw=adb('exec-out','content','read','--uri','content://'+PACKAGE+'.tls-acceptance/report/'+case+'/'+str(slot),check=False).stdout
            try:value=strict_json(raw)
            except (ValueError,UnicodeError):time.sleep(.25);continue
            require(value.get('runNonce')==run and value.get('caseNonce')==case and value.get('sourceCommit')==source,'stale or foreign original packet')
            if value.get('status') in ('passed','failed'):
                path=output/('case-'+label+'.json');path.write_bytes(raw);entry.update(report=path.name,reportSha256=hashlib.sha256(raw).hexdigest());device=value;break
            time.sleep(.25)
        require(device is not None,'workload did not terminate; timeout is not protocol rejection')
        entry['device']=device
        finding=validate_device(device,spec=spec,binding=binding,run=run,source=source,tree=tree,identity=identity,leaf=certificates.leaf_sha)
        require(adb('shell','pidof',PACKAGE+':profile'+str(slot)).stdout.decode('ascii').strip()==str(finding['pid']),'actual native report PID owner')
        entry.update(status='passed',finding=finding)
    def resident(stage):
        require(adb('shell','id','-u').stdout.strip()==b'2000','actual shell UID2000')
        selected={e['label']:e for e in entries}
        for label in ('concurrent-strict-tls13','concurrent-default-tls12'):
            finding=selected[label]['finding'];observed=adb('shell','pidof',PACKAGE+':profile'+str(finding['slot'])).stdout.decode('ascii').strip()
            row=dict(stage=stage,slot=finding['slot'],expectedPid=finding['pid'],observedPid=observed,shellUid=2000);process_checks.append(row);require(observed==str(finding['pid']),'both different environment runtimes must remain resident')
    try:
        emulator=adb('shell','getprop','ro.kernel.qemu').stdout.strip();sdk=adb('shell','getprop','ro.build.version.sdk').stdout.strip();cpus=adb('shell','getconf','_NPROCESSORS_ONLN').stdout.strip();uid=adb('shell','id','-u').stdout.strip()
        require(emulator==b'1' and sdk==b'35' and cpus==b'4' and uid==b'2000','actual API35/four CPUs/shell2000; no fallback')
        guest=dict(actualEmulator=True,api=35,onlineCpus=4,evidenceShellUid=2000)
        verify_installed(strict_json(adb('exec-out','content','read','--uri','content://'+PACKAGE+'.evidence/build-identity').stdout),identity)
        require(not any('tcp:'+str(GUEST_PORT) in line.split() for line in adb('reverse','--list').stdout.decode('ascii').splitlines()),'existing guest mapping cannot be replaced')
        certificates=EphemeralCertificates();ca=AndroidUserCa(adb,certificates);ca.install()
        host_tls=dict(certificates.public,trustInstallation=ca.receipt,guestPort=GUEST_PORT,binding=dict(sourceCommit=source,sourceTree=tree,runNonce=run,integrationApkSha256=identity['apkSha256'],sdkRunId=identity['sdkBuildIdentity']['runId'],sdkRunAttempt=identity['sdkBuildIdentity']['runAttempt']))
        server=TlsAcceptanceServer(certificates,run,source,(ROOT/'tests/gecko/assets/tls-acceptance-page.js').read_text(),(ROOT/'tests/gecko/assets/tls-acceptance-worker.js').read_text()).start()
        adb('reverse','tcp:'+str(GUEST_PORT),'tcp:'+str(server.port));reversed_port=True
        require(adb('shell','pm','clear',PACKAGE).stdout.strip()==b'Success','fresh integration-only initial data')
        for spec in CASE_SPECS:
            label=spec[0]
            if not spec[6] and label!='concurrent-default-tls12':cold_stop()
            collect(spec)
            if label=='concurrent-default-tls12':resident('both-resident')
            if label=='concurrent-strict-resample-tls12':resident('after-resample')
        validate_cross(entries,process_checks)
    except Exception as error:errors.append(dict(stage='actual-production-native-and-wire',errorType=type(error).__name__,reason=str(error)[:400] if isinstance(error,ValueError) and str(error).startswith(('Gecko product TLS evidence:','Product TLS fixture:')) else 'actual-production-workload-failed'))
    finally:
        host=finish_resources(adb,cold_stop,server,certificates,ca,reversed_port,cleanup,errors,host_tls)
    if len(entries)==len(CASE_SPECS) and all(e['status']=='passed' for e in entries) and host is not None:
        try:checked=validate_wire(host,entries,run=run,source=source)
        except Exception as error:errors.append(dict(stage='final-original-wire-replay',errorType=type(error).__name__,reason=str(error)[:400]))
    stable=snapshot()==before;passed=checked is not None and not errors and all(cleanup.values()) and stable
    public_entries=[{k:v for k,v in e.items() if k!='device'} for e in entries]
    result=dict(schema=1,kind='gecko-production-tls-v1',status='passed' if passed else 'failed',diagnosticOnly=True,releaseAcceptance=False,sourceCommit=source,sourceTree=tree,runId=os.environ.get('GITHUB_RUN_ID'),runAttempt=os.environ.get('GITHUB_RUN_ATTEMPT'),runNonce=run,expectedBuildIdentity=identity,guest=guest,caseRecords=public_entries,processChecks=process_checks,hostTls=host_tls,host=host,cleanup=cleanup,errors=errors,checked=checked,sourceFiles=before,executionInputsUnchanged=stable,actualAndroidExecution=any(e['status']=='passed' for e in entries),actualGeckoExecution=any(e['status']=='passed' for e in entries),productionGeckoWebTlsWorkloadPassed=passed,persistentServiceWorkerTlsMeasured=passed,workerCoverageVerified=False,serviceWorkerCoverageVerified=False,fullTlsFingerprintEmulation=False,quicWireVerified=False,rawFatalAlertPacketDecoded=False,appIndependentTlsStacksCovered=False,scope='Actual production Gecko web connections under per-environment cold native TLS policy, exact native DEFAULT/effective readback, trusted controlled TLS12/TLS13 peers and original ClientHello bytes. Real desired-only UI pending state, nonempty old USER reconciliation, retained registration with separately measured Service Worker fetch across true cold start, and simultaneous isolated environments. Independent app downloader/connection checks/proxy entrance Java or other TLS stacks, arbitrary TLS fingerprints and QUIC are not covered.')
    raw=(json.dumps(result,ensure_ascii=False,indent=2)+'\n').encode();require(len(raw)<=4*1024*1024,'bounded final original summary');(output/'results.json').write_bytes(raw)
    print(json.dumps({k:result[k] for k in ('status','sourceCommit','productionGeckoWebTlsWorkloadPassed','executionInputsUnchanged')}));return 0 if passed else 1

if __name__=='__main__':raise SystemExit(main())
