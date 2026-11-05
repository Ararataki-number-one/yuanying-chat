#!/usr/bin/env python3
"""Run the additional actual Android cold CPU/default-IP combination gate once.

A controlled SOCKS/TLS fixture terminates one synthetic geo response.
No public geolocation accuracy, complete Worker isolation or old-gate replacement
is claimed. TLS private material stays in host /tmp and is removed on every exit.
"""
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

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'tools/gecko'))
sys.path.insert(0,str(Path(__file__).resolve().parent))
from profile_invocation_contract import expected_build,verify_installed
from fingerprint_fixture_server import AndroidUserCa
from ip_timezone_fixture_server import IpFixtureCertificates,IpTimeZoneFleet
from check_gecko_cpu_ip_combo_evidence import (SOURCE_INPUTS,REPORT_NAME,RAW_DIRECTORY,RAW_FILES,
    FIXTURE_TYPE,verify_gecko_cpu_ip_combo_evidence)
from check_gecko_ip_timezone_evidence import expected_clock,strict_json,_typed_equal

ACTIVITY='local.pocketchat.test/local.pocketchat.GeckoCpuIpComboIntegrationActivity'
URI='content://local.pocketchat.test.gecko-cpu-ip-combo-evidence'
MAX_ACTIVITY_BYTES=524288


def require(value,message):
    if not value:raise ValueError('CPU/IP combo runner: '+message)
def write_json(path,value):
    raw=(json.dumps(value,ensure_ascii=False,separators=(',',':'))+'\n').encode()
    limit=2*1024*1024 if path.name==REPORT_NAME else 262144
    require(len(raw)<=limit,'bounded JSON output exceeded')
    flags=os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW
    with os.fdopen(os.open(path,flags,0o644),'wb') as stream:stream.write(raw)
    return dict(bytes=len(raw),sha256=hashlib.sha256(raw).hexdigest())
def scope_command(action,source,nonce):
    require(action in ('prepare','clear') and re.fullmatch('[0-9a-f]{40}',source) and re.fullmatch('[0-9a-f]{32}',nonce),'invalid explicit fixture scope invocation')
    return ['shell',shlex.join(['content','call','--uri',URI,'--method',action,
        '--extra','sourceCommit:s:'+source,'--extra','runNonce:s:'+nonce])]
def activity_args(source,nonce,leaf):
    require(re.fullmatch('[0-9a-f]{40}',source) and re.fullmatch('[0-9a-f]{32}',nonce) and re.fullmatch('[0-9a-f]{64}',leaf),'invalid controlled activity invocation')
    return ['shell',shlex.join(['am','start','-W','-n',ACTIVITY,'--es','sourceCommit',source,
                              '--es','runNonce',nonce,'--es','expectedLeafSha256',leaf])]
def source_inputs():
    paths={ROOT/name for name in SOURCE_INPUTS}
    paths.update((ROOT/'app/src/main/java').rglob('*.java'))
    paths.update((ROOT/'app/src/main/assets').rglob('*.js'))
    paths.update((ROOT/'app/src/main/assets').rglob('*.json'))
    paths.update((ROOT/'tests/gecko').glob('*.java'))
    return sorted(paths)
def read_activity(raw,source,nonce,expected):
    require(len(raw)<=MAX_ACTIVITY_BYTES,'bounded device report exceeded')
    text=raw.decode('utf-8','strict')
    if not text.strip() or text.startswith(('Error while accessing provider:','Error:','No result found.')):return None
    # Strict parsing precedes all invocation comparisons. Damaged JSON must not
    # disappear behind a stale-nonce/startup retry or become an opaque timeout.
    value=strict_json(raw)
    require(type(value) is dict and type(value.get('schema')) is int and value['schema']==1 and value.get('fixtureType')==FIXTURE_TYPE and type(value.get('runNonce')) is str and re.fullmatch('[0-9a-f]{32}',value['runNonce']),'typed fixture invocation required')
    if value['runNonce']!=nonce:return None
    require(value.get('sourceCommit')==source and value.get('sourceTree')==expected['sourceTree'],'device source/fixture differs')
    verify_installed(value.get('buildIdentity',{}),expected)
    for key in ('schema','versionCode','apkBytes','sdkBuildIdentity'):
        require(_typed_equal(value['buildIdentity'].get(key),expected.get(key)),'typed installed identity differs')
    return value
def safe_trust(receipt):
    # Preserve the actual installation booleans/hashes/owner evidence. Export no
    # filesystem paths or certificate/key material, including the public path.
    allowed={'method','androidUser','adbRoot','selinuxEnforcing','installedPublicCaBytesMatch',
        'ownerAndMode','selinuxContext','subjectHashOld','appForceStoppedAfterInstall','publicCaPemSha256',
        'expectedLeafDerSha256','evidenceShellUid','shellRestoredAfterInstall','removedAfterExecution',
        'cleanupRootUid','cleanupShellUid','shellRestoredAfterCleanup'}
    return {key:value for key,value in receipt.items() if key in allowed}


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--adb',default='adb');parser.add_argument('--serial',required=True)
    parser.add_argument('--apk',type=Path,required=True);parser.add_argument('--source',required=True)
    parser.add_argument('--output',type=Path,required=True);args=parser.parse_args()
    require(re.fullmatch('[0-9a-f]{40}',args.source),'exact committed source required')
    source=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip()
    tree=subprocess.check_output(['git','rev-parse','HEAD^{tree}'],cwd=ROOT,text=True).strip()
    require(source==args.source and not subprocess.check_output(['git','status','--porcelain'],cwd=ROOT,text=True).strip(),'clean exact selected source required')
    require(args.apk.is_file() and not args.apk.is_symlink(),'actual integration APK required')
    args.output.mkdir(parents=True,exist_ok=True);require(args.output.is_dir() and not args.output.is_symlink(),'ordinary output directory required')
    require(not (args.output/REPORT_NAME).exists() and not (args.output/RAW_DIRECTORY).exists() and not (args.output/RAW_DIRECTORY).is_symlink(),'fresh output paths required')
    rawdir=args.output/RAW_DIRECTORY;rawdir.mkdir()
    settings=(ROOT/'app/build.gradle').read_text()
    identity=expected_build(args.apk,source,tree,re.search(r"versionName '([^']+)'",settings).group(1),int(re.search(r'versionCode (\d+)',settings).group(1)))
    paths=source_inputs();hashes={str(path.relative_to(ROOT)):hashlib.sha256(path.read_bytes()).hexdigest() for path in paths}
    nonce=uuid.uuid4().hex;sdk=identity['sdkBuildIdentity'];binding=dict(sourceCommit=source,sourceTree=tree,runNonce=nonce,integrationApkSha256=identity['apkSha256'],sdkRunId=sdk['runId'],sdkRunAttempt=sdk['runAttempt'])
    def adb(*values,check=True,timeout=30):
        return subprocess.run([args.adb,'-s',args.serial,*values],check=check,capture_output=True,timeout=timeout)
    certificates=server=ca=activity=None;setup_before={};process_sample={};error=None;mappings=[];scope_prepared=False;host_tls={};system={};device_raw_sha=None;device_raw=None
    cleanup=dict(appStopped=False,scopeCleared=False,reverseRemoved=False,caRemoved=False,privateMaterialRemoved=False,serverQuiesced=False)
    report=dict(schema=1,fixtureType=FIXTURE_TYPE,status='running',sourceCommit=source,sourceTree=tree,runNonce=nonce,expectedBuildIdentity=identity,
        actualAndroidExecution=False,actualGeckoExecution=False,syntheticGeoService=True,actualPublicIpGeolocationVerified=False,
        workerCoverageVerified=False,serviceWorkerCoverageVerified=False,fingerprintProtectionVerified=False)
    try:
        require(adb('shell','getprop','ro.kernel.qemu').stdout.decode().strip()=='1','actual controlled Android emulator required')
        require(adb('shell','id','-u').stdout.decode().strip()=='2000','source-bound evidence requires shell UID2000')
        system['before']=adb('shell','getprop','persist.sys.timezone').stdout.decode('ascii').strip();expected_clock(system['before'])
        certificates=IpFixtureCertificates()
        gecko=(ROOT/'tests/gecko/assets/gecko-cpu-ip-combo-page.js').read_text()
        server=IpTimeZoneFleet(certificates,(ROOT/'tests/gecko/assets/worker-policy-page.js').read_text(),gecko,binding).start()
        # Actual source-bound local host configuration; this is neither an
        # Android control HTTP observation nor a manufactured native result.
        server.control(dict(sourceCommit=source,runNonce=nonce,action='stage',case='default-socks'))
        ca=AndroidUserCa(adb,certificates);ca.install()
        existing=adb('reverse','--list').stdout.decode('ascii').splitlines()
        for guest,host in server.ports().items():
            require(not any('tcp:'+str(guest) in row.split() for row in existing),'guest fixture port already mapped; refusing replacement')
            adb('reverse','tcp:'+str(guest),'tcp:'+str(host));mappings.append(guest)
        host_tls=dict(certificates.public,binding=binding)
        require(adb('shell','pm','clear','local.pocketchat.test').stdout.decode().strip()=='Success','fresh integration-only data required')
        # No default-process provider may run before this explicit scope. The
        # separate setup process validates the actual installed bytes itself.
        # A rejected prepare may already have written its provisional marker.
        # Cleanup still attempts only this invocation's exact owner/nonce.
        scope_prepared=True;adb(*scope_command('prepare',source,nonce))
        setup=strict_json(adb('exec-out','content','read','--uri',URI+'/setup').stdout);setup_before=setup
        require(setup.get('status')=='armed' and setup.get('sourceCommit')==source and setup.get('sourceTree')==tree and setup.get('runNonce')==nonce and setup.get('integrationApkSha256')==identity['apkSha256'] and setup.get('timezoneSealedRecordMissing') is True and setup.get('actualDefaultStoreLoadYet') is False and setup.get('manualSeedAppliedToIpScope') is False,'actual unused-scope provider proof differs')
        deadline=time.monotonic()+180
        adb(*activity_args(source,nonce,certificates.leaf_sha))
        while time.monotonic()<deadline:
            remaining=deadline-time.monotonic()
            if remaining<=0:break
            raw=adb('exec-out','content','read','--uri',URI+'/report',check=False,timeout=min(20,remaining)).stdout
            current=read_activity(raw,source,nonce,identity)
            if current is not None:
                activity=current;device_raw=raw;device_raw_sha=hashlib.sha256(raw).hexdigest()
                if current.get('status') in ('passed','failed'):break
            time.sleep(.25)
        require(activity is not None and activity.get('status')=='passed','actual CPU/IP combo fixture failed or timed out')
        process=activity.get('process',{});pid=process.get('pid');require(type(pid) is int and pid>0 and process.get('name')=='local.pocketchat.test:profile6','actual profile6 process missing')
        observed=adb('shell','pidof','local.pocketchat.test:profile6').stdout.decode('ascii','strict').strip()
        require(observed==str(pid),'independent shell PID differs or is ambiguous')
        uid=adb('shell','id','-u').stdout.decode('ascii','strict').strip();require(uid=='2000','process evidence requires restored shell UID2000')
        process_sample=dict(schema=1,sourceCommit=source,sourceTree=tree,runNonce=nonce,slot=6,processName='local.pocketchat.test:profile6',expectedPid=pid,observedPid=observed,shellUid=int(uid))
        system['after']=adb('shell','getprop','persist.sys.timezone').stdout.decode('ascii').strip()
        require(system['before']==system['after'],'Android system timezone changed')
        report.update(status='passed',actualAndroidExecution=True,actualGeckoExecution=True)
    except Exception as failure:
        error=failure;report.update(status='failed',errorType=type(failure).__name__)
    finally:
        # Every independent cleanup action executes even when an earlier action
        # fails. Never mask the original fixture failure or convert cleanup to a
        # successful result. No replay/input/retry is performed here.
        actions=[('appStopped',lambda:adb('shell','am','force-stop','local.pocketchat.test'))]
        if scope_prepared:actions.append(('scopeCleared',lambda:adb(*scope_command('clear',source,nonce))))
        if server is not None:actions.append(('serverQuiesced',server.close))
        def remove_reverse():
            for guest in mappings:adb('reverse','--remove','tcp:'+str(guest))
        actions.append(('reverseRemoved',remove_reverse))
        if ca is not None:actions.append(('caRemoved',ca.remove))
        if certificates is not None:
            def remove_private():
                certificates.close();require(not certificates.directory.exists(),'ephemeral TLS private material remains');host_tls['privateMaterialRemoved']=True
            actions.append(('privateMaterialRemoved',remove_private))
        for key,action in actions:
            try:action();cleanup[key]=True
            except Exception as failure:
                report.setdefault('cleanupErrors',[]).append(dict(action=key,errorType=type(failure).__name__));error=error or failure;report.update(status='failed',errorType=type(error).__name__)
        if ca is not None:host_tls['trustInstallation']=safe_trust(ca.receipt)
        try:route_receipts=server.snapshot() if server is not None else {}
        except Exception as failure:
            route_receipts={};error=error or failure;report.update(status='failed',errorType=type(error).__name__)
        try:unchanged=all(path.is_file() and hashlib.sha256(path.read_bytes()).hexdigest()==hashes[str(path.relative_to(ROOT))] for path in paths)
        except OSError:unchanged=False
        if not unchanged:error=error or ValueError('Source changed');report.update(status='failed',errorType='SourceChanged')
        report.update(activity=activity or {},hostTls=host_tls,routeReceipts=route_receipts,systemTimeZone=system,sourceFiles=hashes,
            executionInputsUnchanged=unchanged,cleanup=cleanup,deviceReportReceivedSha256=device_raw_sha,
            prelaunchSetup=setup_before,processSample=process_sample,
            rawExtractionScope='Fixed combo is the original device JSON object, setup carries original prelaunch/actual postload states, process is an independent shell PID observation, routes are a quiescent host snapshot. Exported byte hashes are explicit.',
            scope='Real canonical MainActivity profile6 cold nativeCPU1/defaultIP first-inline combination, synthetic geo over controlled SOCKS/TLS. Control transport is a source-bound local host method; no Android-control-HTTP, public location or whole Worker coverage claim.')
        actual=activity or {};pins={}
        values={'route-receipts.json':route_receipts,
            'setup-scope.json':dict(beforeLaunch=setup_before,afterLoad=actual.get('setup',{}),cpuSetup=actual.get('cpuSetup',{}),cpuStoredState=actual.get('cpuStoredState',{})),
            'process-sample.json':process_sample}
        for name in RAW_FILES:
            if name=='combo.json':
                if device_raw is not None:
                    require(0<len(device_raw)<=524288,'original device JSON bound exceeded')
                    with os.fdopen(os.open(rawdir/name,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o644),'wb') as stream:stream.write(device_raw)
                    pins[name]=dict(bytes=len(device_raw),sha256=hashlib.sha256(device_raw).hexdigest())
            else:pins[name]=write_json(rawdir/name,dict(schema=1,case=name[:-5],binding=binding,evidence=values[name]))
        report['casePins']=pins;write_json(args.output/REPORT_NAME,report)
        if error is None:
            try:verify_gecko_cpu_ip_combo_evidence(args.output,source,identity)
            except Exception as rejected:
                # Preserve the original report bytes and fail the command. A
                # checker rejection must not silently rewrite a device outcome.
                error=rejected
    print(json.dumps(dict(status='passed' if error is None else 'failed',sourceCommit=source,runNonce=nonce,
        stage=(activity or {}).get('stage','unavailable'),
        errorType=type(error).__name__ if error is not None else None,
        actualAndroidExecution=report['actualAndroidExecution'],actualGeckoExecution=report['actualGeckoExecution'],
        syntheticGeoService=True,actualPublicIpGeolocationVerified=False),separators=(',',':')))
    if error is not None:raise SystemExit(1)
if __name__=='__main__':main()
