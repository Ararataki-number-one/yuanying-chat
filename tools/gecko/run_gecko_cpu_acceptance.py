#!/usr/bin/env python3
"""Actual production CPU cold bootstrap/first-inline/persistent SW acceptance."""
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
from cpu_acceptance_server import CpuAcceptanceServer,GUEST_PORT,ROLES,strict_json,require

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'tools/browser'))
from fingerprint_fixture_server import EphemeralCertificates,AndroidUserCa
PACKAGE='local.pocketchat.test'
CASES=(('cap1','1',False,False,False),('cap2','2',False,False,False),
       ('automatic-stale-user','automatic',False,False,True),('rfp','1',True,False,False),
       ('persistent-before','2',False,False,False),('persistent-after','2',False,True,False))


def sha(path):
    digest=hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda:stream.read(65536),b''):digest.update(block)
    return digest.hexdigest()


def typed_equal(actual,expected):
    if type(actual) is not type(expected):return False
    if type(expected) is dict:return set(actual)==set(expected) and all(typed_equal(actual[key],item) for key,item in expected.items())
    if type(expected) is list:return len(actual)==len(expected) and all(typed_equal(a,b) for a,b in zip(actual,expected))
    return actual==expected


def validate_report(value,*,run,case,source,tree,identity,slot,mode,rfp,retain,stale_user,leaf=None,template_apply=False):
    fields={'schema','fixtureType','status','stage','failure','diagnosticOnly','releaseAcceptance','sourceCommit','sourceTree','runNonce','caseNonce','slot','mode','rfpRequested','retainedProfile','staleUserPrefSeeded','identityApplyInvoked','identityApplyCompleted','identityPolicyRevision','identityPolicyBefore','buildIdentity','process','tls','cpuPolicy','runtimeCpuPolicy','storagePathEvidence','navigation','nativeEvents','observations','actualAndroidExecution','actualGeckoExecution','productionChatSession','productionCpuBootstrap','navigatorGetterOverrideUsed','debuggingEndpointUsed','workerCoverageVerified','fingerprintProtectionVerified'}
    require(type(value) is dict and set(value)==fields,'Exact bounded CPU report schema required')
    require(type(value) is dict and type(value.get('schema')) is int and value['schema']==1
        and value.get('fixtureType')=='gecko-production-cpu-v1' and value.get('status')=='passed'
        and value.get('stage')=='complete' and value.get('failure')=='','Completed production CPU workload required')
    for key,expected in dict(runNonce=run,caseNonce=case,sourceCommit=source,sourceTree=tree,slot=slot,mode=mode,
                            rfpRequested=rfp,retainedProfile=retain,staleUserPrefSeeded=stale_user).items():
        require(type(value.get(key)) is type(expected) and value[key]==expected,'Workload binding differs: '+key)
    verify_installed(value.get('buildIdentity',{}),identity)
    require(all(key in value['buildIdentity'] and typed_equal(value['buildIdentity'][key],item) for key,item in identity.items()),'Installed APK identity types differ')
    require(value.get('identityApplyInvoked') is template_apply and value.get('identityApplyCompleted') is template_apply,'Normal template apply execution differs')
    if template_apply:require(type(value.get('identityPolicyBefore')) is int and type(value.get('identityPolicyRevision')) is int
        and value['identityPolicyRevision']>value['identityPolicyBefore'],'Actual ordinary template application revision did not advance')
    for field in ('actualAndroidExecution','actualGeckoExecution','productionChatSession','productionCpuBootstrap','diagnosticOnly'):
        require(value.get(field) is True,'Actual production execution required: '+field)
    for field in ('releaseAcceptance','navigatorGetterOverrideUsed','debuggingEndpointUsed','workerCoverageVerified','fingerprintProtectionVerified'):
        require(value.get(field) is False,'CPU acceptance scope differs: '+field)
    tls=value.get('tls');require(type(tls) is dict and set(tls)=={'isSecure','isException','leafSha256','enterpriseRootsReadback'}
        and tls['isSecure'] is True and tls['isException'] is False and tls['enterpriseRootsReadback'] is True
        and type(tls['leafSha256']) is str and re.fullmatch('[0-9a-f]{64}',tls['leafSha256'])
        and (leaf is None or tls['leafSha256']==leaf),'Actual controlled native TLS leaf without exception required')
    storage=value.get('storagePathEvidence')
    storage_fields={'schema','status','slot','frameworkDataAncestorAlias','globalNoBackupAncestorAlias','environmentRootAncestorAlias','noBackupWithinDataAnchor','rootMatchesSlot','privateComponentsNoSymlinks','validatedPrivateComponents','runtimePathsCanonical'}
    require(type(storage) is dict and set(storage)==storage_fields and type(storage.get('schema')) is int and storage['schema']==1
        and storage.get('status')=='verified' and type(storage.get('slot')) is int and storage['slot']==slot,
        'Actual bounded framework storage relationship required')
    for flag in ('frameworkDataAncestorAlias','globalNoBackupAncestorAlias','environmentRootAncestorAlias'):
        require(type(storage.get(flag)) is bool,'Actual storage alias observation must be Boolean')
    for flag in ('noBackupWithinDataAnchor','rootMatchesSlot','privateComponentsNoSymlinks','runtimePathsCanonical'):
        require(storage.get(flag) is True,'Owned canonical app storage requirement failed: '+flag)
    require(type(storage.get('validatedPrivateComponents')) is int and storage['validatedPrivateComponents']==(1 if slot==0 else 3),
        'Actual private storage component checks required')
    process=value.get('process');require(type(process) is dict and set(process)=={'pid','uid','name'}
        and type(process['pid']) is int and process['pid']>0 and type(process['uid']) is int and 10000<=process['uid']<100000
        and process['name']==PACKAGE+':profile'+str(slot),'Actual production environment process required')
    cpu=value.get('cpuPolicy');runtime=value.get('runtimeCpuPolicy')
    require(type(cpu) is dict and type(runtime) is dict and typed_equal(cpu,runtime),'Actual controller/runtime CPU status differs')
    cpu_fields={'schema','engine','desiredRevision','desiredMode','activeBootRevision','activeBootMode','state','issue','failureCode','pendingColdStart','configuredCap','defaultCap','hasUserValue','rfpPriority','nativeSettingReadback','startupReconciled','scope','processNonce','pid','runtimeNonce','environmentId','environmentGeneration','slot','pageObservationVerified','workerCoverageVerified','serviceWorkerCoverageVerified','persistentWorkerColdStartVerified'}
    require(set(cpu)==cpu_fields and cpu['issue']=='' and cpu['failureCode']=='','Exact native CPU status schema required')
    require(type(cpu.get('schema')) is int and cpu['schema']==1 and cpu.get('engine')=='gecko'
        and cpu.get('state')=='ready' and cpu.get('scope')=='runtime-wide' and cpu.get('slot')==slot
        and type(cpu.get('slot')) is int and cpu.get('pid')==process['pid'] and type(cpu.get('pid')) is int,
        'Ready production CPU runtime required')
    for field in ('nativeSettingReadback','startupReconciled'):require(cpu.get(field) is True,'Actual native CPU readback missing')
    for field in ('pendingColdStart','hasUserValue','workerCoverageVerified','serviceWorkerCoverageVerified','persistentWorkerColdStartVerified','pageObservationVerified'):
        require(cpu.get(field) is False,'Production CPU status must preserve independent scope: '+field)
    require(cpu.get('desiredMode')==mode and cpu.get('activeBootMode')==mode and type(cpu.get('desiredRevision')) is int
        and cpu['desiredRevision']>0 and type(cpu.get('activeBootRevision')) is int
        and cpu['activeBootRevision']==cpu['desiredRevision'],'Immutable desired/boot CPU revision differs')
    require(type(cpu.get('configuredCap')) is int and 1<=cpu['configuredCap']<=65536
        and type(cpu.get('defaultCap')) is int and cpu['configuredCap']==cpu['defaultCap']
        and (mode=='automatic' or cpu['configuredCap']==int(mode)),'Actual startup default CPU value differs')
    require(cpu.get('rfpPriority') is rfp,'RFP policy was weakened or not freshly read')
    require(type(cpu.get('environmentId')) is str and re.fullmatch('[0-9a-f-]{36}',cpu['environmentId'])
        and type(cpu.get('environmentGeneration')) is int and cpu['environmentGeneration']>=0,'Actual environment identity required')
    for field in ('processNonce','runtimeNonce'):
        require(type(cpu.get(field)) is str and re.fullmatch('[0-9a-f]{32}',cpu[field]),'Actual process/runtime invocation binding required')
    nav=value.get('navigation');require(type(nav) is dict and set(nav)=={'targetStarted','targetLocation','targetStopSuccessful','loadError','targetPath'}
        and all(nav.get(k) is True for k in ('targetStarted','targetLocation','targetStopSuccessful'))
        and nav['loadError'] is False and nav['targetPath']=='/cpu/slot'+str(slot)+'/page','Owned production target completion required')
    events=value.get('nativeEvents');require(type(events) is list and 1<=len(events)<=128,'Bounded native navigation events required')
    observed=set()
    for event in events:
        require(type(event) is dict and set(event)=={'event','targetOwned','success','errorCategory','errorCode','nativeUrlAvailable'}
            and event['event'] in ('start','stop','location','load-error') and type(event['targetOwned']) is bool,
            'Bounded native event shape differs')
        stop=event['event']=='stop';error=event['event']=='load-error'
        require(event['nativeUrlAvailable'] is (not stop) and (type(event['success']) is bool if stop else event['success'] is None)
            and all(type(event[k]) is int if error else event[k] is None for k in ('errorCategory','errorCode')),'Native URL ownership/types differ')
        if event['targetOwned'] and (not stop or event['success'] is True):observed.add(event['event'])
    require({'start','location','stop'}<=observed and 'load-error' not in observed,'Actual owned native event proof missing')
    packets=value.get('observations');require(type(packets) is list and len(packets)==len(ROLES),'All five actual contexts required')
    roles={};counts={};service=None
    for packet in packets:
        require(type(packet) is dict and set(packet)=={'schema','runNonce','caseNonce','sourceCommit','slot','role','status','observation','error','service'},'Exact first-inline role packet required')
        role=packet['role'];require(role in ROLES and role not in roles,'Duplicate/unknown context');roles[role]=packet
        require(type(packet['schema']) is int and packet['schema']==1 and packet['runNonce']==run and packet['caseNonce']==case
            and packet['sourceCommit']==source and type(packet['slot']) is int and packet['slot']==slot
            and packet['status']=='observed' and packet['error'] is None,'Actual context execution/binding differs')
        row=packet['observation'];require(type(row) is dict and set(row)=={'hardwareConcurrency','nativeGetter','firstInline','bootNonce'}
            and type(row['hardwareConcurrency']) is int and 1<=row['hardwareConcurrency']<=65536
            and row['nativeGetter'] is True and row['firstInline'] is True and type(row['bootNonce']) is str
            and re.fullmatch('[0-9a-f]{32}',row['bootNonce']),'Actual first-inline native getter required')
        counts[role]=row['hardwareConcurrency']
        if role=='service':
            service=packet['service'];prefix='/cpu/slot'+str(slot)+'/'
            require(type(service) is dict and set(service)=={'existingRegistration','controlledBeforeRegistration','scriptPath','scopePath'}
                and type(service['existingRegistration']) is bool and type(service['controlledBeforeRegistration']) is bool
                and service['scriptPath']==prefix+'service.js' and service['scopePath']==prefix,'Persistent SW origin binding differs')
        else:require(packet['service'] is None,'Unexpected SW metadata')
    require(set(roles)==set(ROLES),'Role set differs')
    expected=4 if mode=='automatic' else int(mode)
    cap_obeyed={role:count<=expected for role,count in counts.items()}
    if not rfp:require(all(count==expected for count in counts.values()),'A production first-inline CPU cap/default mismatch remains')
    if retain:require(service['existingRegistration'] is True and service['controlledBeforeRegistration'] is True,'Actual persisted SW registration/control did not recover')
    return dict(slot=slot,mode=mode,rfpPriority=rfp,counts=counts,capObeyed=cap_obeyed,process=process,
        processNonce=cpu['processNonce'],runtimeNonce=cpu['runtimeNonce'],environmentId=cpu['environmentId'],
        environmentGeneration=cpu['environmentGeneration'],activeBootRevision=cpu['activeBootRevision'],
        serviceBootNonce=roles['service']['observation']['bootNonce'],serviceProof=service,
        workerCoverageVerified=False,fingerprintProtectionVerified=False)


def snapshot():
    names=subprocess.check_output(['git','ls-files','--cached','--others','--exclude-standard','app','tests','tools',
        '.github/workflows/gecko-cpu-acceptance.yml','.github/workflows/browser-2_1-acceptance.yml','.github/workflows/publish-gecko-release.yml'],cwd=ROOT,text=True).splitlines()
    return {name:sha(ROOT/name) for name in sorted(set(names)) if (ROOT/name).is_file()}


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--adb',default='adb');parser.add_argument('--serial',default='emulator-5554')
    parser.add_argument('--apk',type=Path,required=True);parser.add_argument('--source',required=True);parser.add_argument('--output',type=Path,required=True);args=parser.parse_args()
    require(args.serial=='emulator-5554' and re.fullmatch('[0-9a-f]{40}',args.source),'Exact selected source and controlled emulator required')
    source=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip();tree=subprocess.check_output(['git','rev-parse','HEAD^{tree}'],cwd=ROOT,text=True).strip()
    require(source==args.source and not subprocess.check_output(['git','status','--porcelain'],cwd=ROOT,text=True).strip(),'Clean selected product source required')
    output=args.output.absolute();require(not output.exists() and all(not p.is_symlink() for p in (output,*output.parents)),'Fresh ordinary evidence directory required')
    settings=(ROOT/'app/build.gradle').read_text();identity=expected_build(args.apk,source,tree,re.search(r"versionName '([^']+)'",settings)[1],int(re.search(r'versionCode ([0-9]+)',settings)[1]))
    before=snapshot();output.mkdir(parents=True);run=uuid.uuid4().hex;records=[];process_checks=[];errors=[];server=None;reversed_port=False;certificates=None;ca=None;host_tls={};cleanup=dict(appStopped=False,reverseRemoved=False,caRemoved=False,privateMaterialRemoved=False)
    def adb(*parts,check=True,timeout=20):return subprocess.run([args.adb,'-s',args.serial,*parts],capture_output=True,check=check,timeout=timeout)
    def launch(label,mode,rfp,retain,stale_user,slot=1,resample=False,template_apply=False):
        case=uuid.uuid4().hex;server.begin(slot,case)
        tokens=['am','start','-W','-n',PACKAGE+'/local.pocketchat.GeckoCpuAcceptanceActivity$Profile'+str(slot),
            '--es','runNonce',run,'--es','caseNonce',case,'--es','sourceCommit',source,'--es','cpuMode',mode,
            '--es','expectedLeafSha256',certificates.leaf_sha,'--ez','rfp',str(rfp).lower(),'--ez','retain',str(retain).lower(),'--ez','staleUser',str(stale_user).lower(),'--ez','resample',str(resample).lower(),'--ez','templateApply',str(template_apply).lower()]
        adb('shell',shlex.join(tokens));return dict(label=label,caseNonce=case,slot=slot,mode=mode,rfp=rfp,retain=retain,staleUser=stale_user,templateApply=template_apply,status='failed')
    def collect(entry):
        deadline=time.monotonic()+150;current=None
        while time.monotonic()<deadline:
            raw=adb('exec-out','content','read','--uri','content://'+PACKAGE+'.cpu-acceptance/report/'+entry['caseNonce']+'/'+str(entry['slot']),check=False).stdout
            try:value=strict_json(raw)
            except (ValueError,UnicodeError):time.sleep(.25);continue
            if value.get('status') in ('passed','failed'):
                path=output/('case-'+entry['label']+'.json');path.write_bytes(raw);entry.update(report=path.name,reportSha256=hashlib.sha256(raw).hexdigest());current=value;break
            require(value.get('caseNonce')==entry['caseNonce'] and value.get('runNonce')==run,'Stale running report');time.sleep(.25)
        require(current is not None,'Production CPU workload did not terminate')
        finding=validate_report(current,run=run,case=entry['caseNonce'],source=source,tree=tree,identity=identity,
            slot=entry['slot'],mode=entry['mode'],rfp=entry['rfp'],retain=entry['retain'],stale_user=entry['staleUser'],leaf=certificates.leaf_sha,template_apply=entry['templateApply'])
        require(current['observations']==server.evidence(entry['caseNonce'])['observations'],'Device role packets differ from independent host receipt')
        require(adb('shell','pidof',PACKAGE+':profile'+str(entry['slot'])).stdout.decode().strip()==str(finding['process']['pid']),'Actual observed process owner differs')
        entry.update(status='passed',finding=finding)
    def cold_stop():
        adb('shell','am','force-stop',PACKAGE)
        for slot in (1,2):require(not adb('shell','pidof',PACKAGE+':profile'+str(slot),check=False).stdout.strip(),'Prior environment process remained alive')
    def resident(stage,entries):
        require(adb('shell','id','-u').stdout.strip()==b'2000','PID observation requires shell UID2000')
        for entry in entries:
            name=PACKAGE+':profile'+str(entry['slot']);pid=entry['finding']['process']['pid']
            observed=adb('shell','pidof',name).stdout.decode('ascii').strip()
            process_checks.append(dict(stage=stage,slot=entry['slot'],caseNonce=entry['caseNonce'],processName=name,expectedPid=pid,observedPid=observed,shellUid=2000))
            require(observed==str(pid),'Concurrent environment did not remain alive')
    try:
        require(adb('shell','getprop','ro.kernel.qemu').stdout.strip()==b'1' and adb('shell','getprop','ro.build.version.sdk').stdout.strip()==b'35','Actual selected API35 emulator required')
        require(adb('shell','id','-u').stdout.strip()==b'2000','Read-only evidence requires shell UID2000')
        require(adb('shell','getconf','_NPROCESSORS_ONLN').stdout.strip()==b'4','Actual guest CPU count must be four')
        verify_installed(strict_json(adb('exec-out','content','read','--uri','content://'+PACKAGE+'.evidence/build-identity').stdout),identity)
        require(not any('tcp:'+str(GUEST_PORT) in line.split() for line in adb('reverse','--list').stdout.decode('ascii').splitlines()),'Refusing to replace existing guest mapping')
        certificates=EphemeralCertificates();ca=AndroidUserCa(adb,certificates);ca.install()
        host_tls=dict(certificates.public,trustInstallation=ca.receipt,guestPort=GUEST_PORT,binding=dict(sourceCommit=source,sourceTree=tree,runNonce=run,integrationApkSha256=identity.get('apkSha256'),sdkRunId=identity.get('sdkBuildIdentity',{}).get('runId'),sdkRunAttempt=identity.get('sdkBuildIdentity',{}).get('runAttempt')))
        server=CpuAcceptanceServer((ROOT/'tests/gecko/assets/cpu-acceptance-page.js').read_text(),(ROOT/'tests/gecko/assets/cpu-acceptance-worker.js').read_text(),run,source,certificates).start()
        adb('reverse','tcp:'+str(GUEST_PORT),'tcp:'+str(server.port));reversed_port=True
        require(adb('shell','pm','clear',PACKAGE).stdout.strip()==b'Success','Fresh integration-only profile data required')
        for label,mode,rfp,retain,stale_user in CASES:
            cold_stop();entry=launch(label,mode,rfp,retain,stale_user);records.append(entry)
            try:collect(entry)
            except Exception as error:entry['errorType']=type(error).__name__;errors.append(dict(label=label,errorType=type(error).__name__))
        prior={entry['label']:entry for entry in records}
        a=prior['persistent-before'].get('finding');b=prior['persistent-after'].get('finding')
        require(a is not None and b is not None and a['environmentId']==b['environmentId'] and a['environmentGeneration']==b['environmentGeneration']
            and a['activeBootRevision']==b['activeBootRevision'] and a['processNonce']!=b['processNonce'] and a['runtimeNonce']!=b['runtimeNonce']
            and a['serviceBootNonce']!=b['serviceBootNonce'],'Same saved profile/SW failed actual cold recovery')
        cold_stop();concurrent=[]
        for label,mode,slot in (('concurrent-cap1','1',1),('concurrent-cap2','2',2)):
            entry=launch(label,mode,False,False,False,slot);concurrent.append(entry);records.append(entry);collect(entry)
        one,two=(entry['finding'] for entry in concurrent)
        require(one['process']['pid']!=two['process']['pid'] and one['environmentId']!=two['environmentId'] and one['processNonce']!=two['processNonce'] and one['runtimeNonce']!=two['runtimeNonce'],'Concurrent environments must own distinct actual processes/runtimes')
        resident('both-resident',concurrent)
        resample=launch('concurrent-cap1-resample','1',False,False,False,1,resample=True);records.append(resample);collect(resample)
        actual=resample['finding']
        for field in ('processNonce','runtimeNonce','environmentId','environmentGeneration','activeBootRevision'):
            require(actual[field]==one[field],'Concurrent profile1 resample changed original runtime/boot binding')
        require(actual['process']['pid']==one['process']['pid'],'Concurrent profile1 resample recreated process')
        resident('after-resample',concurrent)
        template=launch('normal-template-rfp','1',True,False,False,1,template_apply=True);records.append(template);collect(template)
        actual=template['finding']
        for field in ('processNonce','runtimeNonce','environmentId','environmentGeneration','activeBootRevision'):
            require(actual[field]==one[field],'Ordinary template application changed immutable CPU boot binding')

    except Exception as error:errors.append(dict(stage='device-or-cross-case-proof',errorType=type(error).__name__))
    finally:
        try:cold_stop();cleanup['appStopped']=True
        except Exception as error:errors.append(dict(stage='stop-cleanup',errorType=type(error).__name__))
        if reversed_port:
            try:adb('reverse','--remove','tcp:'+str(GUEST_PORT));cleanup['reverseRemoved']=True;host_tls['reverseRemoved']=True
            except Exception as error:errors.append(dict(stage='reverse-cleanup',errorType=type(error).__name__))
        if server is not None:
            try:server.close()
            except Exception as error:errors.append(dict(stage='server-close-cleanup',errorType=type(error).__name__))
        if ca is not None:
            try:ca.remove();cleanup['caRemoved']=True
            except Exception as error:errors.append(dict(stage='public-ca-cleanup',errorType=type(error).__name__))
        if certificates is not None:
            try:certificates.close();host_tls['privateMaterialRemoved']=not certificates.directory.exists();cleanup['privateMaterialRemoved']=host_tls['privateMaterialRemoved']
            except Exception as error:errors.append(dict(stage='ephemeral-tls-cleanup',errorType=type(error).__name__))
    stable=snapshot()==before;passed=len(records)==10 and all(row['status']=='passed' for row in records) and not errors and stable
    result=dict(schema=1,status='passed' if passed else 'failed',diagnosticOnly=True,releaseAcceptance=False,sourceCommit=source,sourceTree=tree,
        runNonce=run,runId=os.environ.get('GITHUB_RUN_ID'),runAttempt=os.environ.get('GITHUB_RUN_ATTEMPT'),expectedBuildIdentity=identity,
        caseRecords=records,processChecks=process_checks,errors=errors,hostTls=host_tls,cleanup=cleanup,host=server.snapshot() if server else None,sourceFiles=before,executionInputsUnchanged=stable,
        actualAndroidExecution=any(row['status']=='passed' for row in records),actualGeckoExecution=any(row['status']=='passed' for row in records),
        productionColdCpuWorkloadPassed=passed,debuggingEndpointUsed=False,navigatorGetterOverrideUsed=False,workerCoverageVerified=False,fingerprintProtectionVerified=False,
        scope='Production ChatSession/GeckoWebView cold native public preference bootstrap; first-inline page/dedicated/blob/shared/service native getter samples; same-origin domain-scoped trusted HTTPS persistent SW across actual package force-stop; concurrent profile1/profile2 cap1/cap2 with profile1 resampled after both are resident, plus ordinary production RFP template application retaining its original CPU boot. RFP raw counts are observational and never weakened to pass a cap. No general worker/fingerprint protection claim.')
    (output/'results.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps({k:result[k] for k in ('status','sourceCommit','productionColdCpuWorkloadPassed','executionInputsUnchanged')}));return 0 if passed else 1

if __name__=='__main__':raise SystemExit(main())
