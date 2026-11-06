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
from ip_timezone_fixture_server import (IpFixtureCertificates,IpTimeZoneFleet,ROUTES,
    MAX_TRANSPORT_DIAGNOSTICS,TRANSPORT_STAGES,TRANSPORT_EXCEPTION_TYPES,TRANSPORT_GUARD_CODES,
    TRANSPORT_HOST_ROLES,TRANSPORT_HOST_FORMS)
from check_gecko_cpu_ip_combo_evidence import (SOURCE_INPUTS,REPORT_NAME,RAW_DIRECTORY,RAW_FILES,
    FIXTURE_TYPE,verify_gecko_cpu_ip_combo_evidence)
from check_gecko_ip_timezone_evidence import expected_clock,strict_json,_typed_equal

ACTIVITY='local.pocketchat.test/local.pocketchat.GeckoCpuIpComboIntegrationActivity'
URI='content://local.pocketchat.test.gecko-cpu-ip-combo-evidence'
MAX_ACTIVITY_BYTES=524288
TRANSPORT_DIAGNOSTIC_NAME='gecko-cpu-ip-combo-transport-diagnostic.json'
NATIVE_ADMISSION_NAME='gecko-cpu-ip-combo-native-admission.json'
NATIVE_ADMISSION_HASHES={'remote-settings':'3a89382624c14be6f9b46ba27222e537fa59f5a36c63aacd6cd762965f1aff0d',
    'remote-settings-attachments':'329ef95339e0fd70cc2fa20c8ea4b30288dc5ad57c8c96dc860d4479a61c9b79'}


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


def write_transport_diagnostic(directory,server,binding,route_receipts):
    """Separate typed diagnostics, never rewrite route errors or acceptance JSON."""
    value=server.diagnostic_snapshot()
    fields={'schema','kind','binding','collectorClosed','quiescent','eventLimit','totalFailures','recordedEvents','droppedEvents','counts','events'}
    require(type(value) is dict and set(value)==fields and type(value['schema']) is int and value['schema']==1 and value['kind']=='ip-timezone-transport-diagnostics-v1' and _typed_equal(value['binding'],binding),'typed transport diagnostic identity differs')
    require(all(type(value[key]) is bool for key in ('collectorClosed','quiescent')) and (not value['quiescent'] or value['collectorClosed']),'transport diagnostic cleanup state differs')
    require(type(value['eventLimit']) is int and value['eventLimit']==MAX_TRANSPORT_DIAGNOSTICS and all(type(value[key]) is int and value[key]>=0 for key in ('totalFailures','recordedEvents','droppedEvents')),'transport diagnostic counters differ')
    events=value['events'];require(type(events) is list and len(events)==value['recordedEvents']<=MAX_TRANSPORT_DIAGNOSTICS and value['recordedEvents']==min(value['totalFailures'],MAX_TRANSPORT_DIAGNOSTICS) and value['droppedEvents']==value['totalFailures']-len(events),'bounded transport diagnostic events differ')
    counts=value['counts'];categories=set(TRANSPORT_EXCEPTION_TYPES.values())|{'OtherSSLError','OtherUnicodeError','OtherOSError','OtherValueError'}
    guard_codes=set(TRANSPORT_GUARD_CODES.values())|{'other-guard'}
    require(type(counts) is dict and set(counts)==set(ROUTES),'transport diagnostic routes differ')
    totals={}
    for route,stages in counts.items():
        require(type(stages) is dict and set(stages)==set(TRANSPORT_STAGES),'transport diagnostic phases differ')
        for buckets in stages.values():
            require(type(buckets) is dict and set(buckets)<=categories and all(type(count) is int and count>0 for count in buckets.values()),'transport diagnostic exception counters differ')
        totals[route]=sum(count for buckets in stages.values() for count in buckets.values())
    require(sum(totals.values())==value['totalFailures'],'transport diagnostic failure total differs')
    recorded={route:{stage:{} for stage in TRANSPORT_STAGES} for route in ROUTES}
    for index,event in enumerate(events,1):
        require(type(event) is dict and set(event)=={'sequence','route','protocol','stage','exceptionClass','guardCode','collectorClosed','hostRole','hostForm','hostSha256'} and type(event['sequence']) is int and event['sequence']==index and type(event['route']) is str and event['route'] in ROUTES and event['protocol']==ROUTES[event['route']]['protocol'] and type(event['stage']) is str and event['stage'] in TRANSPORT_STAGES and type(event['exceptionClass']) is str and event['exceptionClass'] in categories and type(event['guardCode']) is str and event['guardCode'] in guard_codes and type(event['collectorClosed']) is bool,'transport diagnostic event escapes fixed enums')
        role,form,host_sha=event['hostRole'],event['hostForm'],event['hostSha256']
        require(type(role) is str and role in TRANSPORT_HOST_ROLES and type(form) is str and form in TRANSPORT_HOST_FORMS,'transport diagnostic host classification escapes fixed enums')
        require((role=='unavailable' and form=='unavailable' and host_sha is None) or (role!='unavailable' and form!='unavailable' and type(host_sha) is str and re.fullmatch('[0-9a-f]{64}',host_sha) is not None),'transport diagnostic host digest or availability differs')
        require(role=='unavailable' or (form in ('other','ipv4','ipv6') if role=='other' else form in ('exact','case-variant','trailing-dot','case-and-trailing-dot')),'transport diagnostic host role and form differ')
        if event['guardCode']=='socks-host':
            require(role!='unavailable' and not (role in ('fixture-a','fixture-b','geo') and form=='exact'),'SOCKS host rejection must retain a rejected target classification')
        buckets=recorded[event['route']][event['stage']];category=event['exceptionClass'];buckets[category]=buckets.get(category,0)+1
        require(not event['collectorClosed'] or value['collectorClosed'],'transport diagnostic close state regressed')
    require(all(count<=counts[route][stage].get(category,0) for route,stages in recorded.items() for stage,buckets in stages.items() for category,count in buckets.items()) and (value['droppedEvents']>0 or _typed_equal(recorded,counts)),'diagnostic event and aggregate buckets differ')
    if value['quiescent']:
        require(type(route_receipts) is dict and route_receipts.get('closed') is True and _typed_equal(route_receipts.get('binding'),binding) and _typed_equal(route_receipts.get('errors'),totals),'diagnostics must preserve the closed original route owner and every error')
    return write_json(Path(directory)/TRANSPORT_DIAGNOSTIC_NAME,dict(schema=1,binding=dict(binding),diagnosticOnly=True,qualificationEvidence=False,snapshot=value))


def validate_native_admission(raw,source,nonce,expected):
    """Validate an independent original native snapshot, never acceptance data."""
    require(type(raw) is bytes and 0<len(raw)<=262144,'bounded native admission snapshot required')
    value=strict_json(raw)
    fields={'schema','kind','sourceCommit','sourceTree','runNonce','buildIdentity','process','scope','automaticLatencyChecks',
        'eventLimit','totalRefusals','droppedEvents','events','snapshotScope','diagnosticOnly','qualificationEvidence'}
    require(type(value) is dict and set(value)==fields and type(value['schema']) is int and value['schema']==1
        and value['kind']=='gecko-cpu-ip-combo-native-admission-v1','typed native admission schema differs')
    require(value['sourceCommit']==source and value['sourceTree']==expected['sourceTree'] and value['runNonce']==nonce,'native admission invocation differs')
    require(type(value['buildIdentity']) is dict and set(value['buildIdentity'])==set(expected)|{'scope'}
        and value['buildIdentity']['scope']=='Installed synthetic integration APK bytes and embedded source stamp only'
        and all(_typed_equal(value['buildIdentity'][key],expected[key]) for key in expected),'native admission installed identity differs')
    verify_installed(value['buildIdentity'],expected)
    require(value['scope']=='integration-only-exact-remote-settings-https-admission'
        and value['snapshotScope']=='persisted-async-snapshot-before-force-stop-later-events-not-covered'
        and value['automaticLatencyChecks'] is False and value['diagnosticOnly'] is True and value['qualificationEvidence'] is False,'native admission scope differs')
    process=value['process'];require(type(process) is dict and set(process)=={'pid','uid','name'} and type(process['pid']) is int and process['pid']>0
        and type(process['uid']) is int and process['uid']>=10000 and process['name']=='local.pocketchat.test:profile6','native admission process differs')
    events=value['events'];require(type(value['eventLimit']) is int and value['eventLimit']==128 and type(value['totalRefusals']) is int and 0<=value['totalRefusals']<=9223372036854775807
        and type(value['droppedEvents']) is int and type(events) is list and len(events)==min(128,value['totalRefusals'])
        and value['droppedEvents']==value['totalRefusals']-len(events),'native admission event bounds differ')
    closed={'type':'socks','host':'127.0.0.1','port':9,'proxyDNS':True,'failoverTimeout':1}
    for index,event in enumerate(events,1):
        require(type(event) is dict and set(event)=={'sequence','role','hostSha256','runtimeInstance','viewInstance','sessionId','admissionPredicateObserved','closedRoute','superRoute'}
            and type(event['sequence']) is int and event['sequence']==index and type(event['role']) is str and event['role'] in NATIVE_ADMISSION_HASHES
            and event['hostSha256']==NATIVE_ADMISSION_HASHES[event['role']],'native admission target differs')
        require(all(type(event[key]) is int and event[key]!=0 for key in ('runtimeInstance','viewInstance'))
            and type(event['sessionId']) is str and (event['sessionId']=='' or re.fullmatch('[A-Za-z0-9_.:-]{1,160}',event['sessionId']) is not None),'native admission owner differs')
        require(type(event['admissionPredicateObserved']) is bool and type(event['closedRoute']) is bool and ((_typed_equal(event['superRoute'],closed) and event['closedRoute'])
            or (event['superRoute'] is None and not event['closedRoute'])),'native admission actual super route differs')
    return value

def capture_native_admission(adb,directory,source,nonce,expected):
    # Read before force-stop/scope clear. Preserve exact original bytes. This
    # snapshot cannot establish that no later native event occurred.
    raw=adb('exec-out','content','read','--uri',URI+'/admission',check=False,timeout=20).stdout
    value=validate_native_admission(raw,source,nonce,expected)
    path=Path(directory)/NATIVE_ADMISSION_NAME
    with os.fdopen(os.open(path,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o644),'wb') as stream:stream.write(raw)
    return value


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
        if scope_prepared:
            try:
                admission=capture_native_admission(adb,args.output,source,nonce,identity)
                if activity is not None:require(_typed_equal(admission['process'],activity.get('process')),'native admission and actual activity process differ')
                require(all(event['closedRoute'] for event in admission['events']),'observed native admission returned an unsafe route')
            except Exception as failure:error=error or failure
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
        if server is not None:
            try:write_transport_diagnostic(args.output,server,binding,route_receipts)
            except Exception as failure:
                # Fail the command without rewriting the device-derived outcome,
                # just as a later acceptance-checker rejection does below.
                error=error or failure
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
