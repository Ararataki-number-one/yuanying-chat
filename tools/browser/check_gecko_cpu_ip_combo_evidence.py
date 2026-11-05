#!/usr/bin/env python3
"""Verify one source-bound native cold CPU/default-IP first-inline combination.

Synthetic loopback geo/TLS fixtures do not establish public geolocation or
complete Worker coverage. Pref readback and actual page getters stay separate.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path,PurePosixPath
import re
import sys
os.environ['GIT_NO_LAZY_FETCH']='1'
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'tools'));sys.path.insert(0,str(Path(__file__).resolve().parent))
from gecko.sdk_identity_contract import source_bytes,strict_json,_typed_equal
import check_gecko_ip_timezone_evidence as ip

REPORT_NAME='gecko-cpu-ip-combo-results.json'
RAW_DIRECTORY='gecko-cpu-ip-combo-evidence'
RAW_FILES=('combo.json','route-receipts.json','setup-scope.json','process-sample.json')
FIXTURE_TYPE='gecko-production-cpu-ip-combo-v1'
ACTIVITY='local.pocketchat.GeckoCpuIpComboIntegrationActivity'
SCOPE_ACTIVITY='local.pocketchat.GeckoIpTimeZoneIntegrationActivity'
PROCESS='local.pocketchat.test:profile6'
CPU_FIELDS={'schema','engine','desiredRevision','desiredMode','activeBootRevision','activeBootMode','state','issue','failureCode','pendingColdStart','configuredCap','defaultCap','hasUserValue','rfpPriority','nativeSettingReadback','startupReconciled','scope','processNonce','pid','runtimeNonce','environmentId','environmentGeneration','slot','pageObservationVerified','workerCoverageVerified','serviceWorkerCoverageVerified','persistentWorkerColdStartVerified'}
CHECKS=('same-document.first-inline','same-document.native-cpu-one','same-document.native-new-york','same-document.network-marker','production.native-preferences','production.default-ip-durable','production.cpu-desired-durable','production.generic-no-gpt')
SOURCE_INPUTS=set(ip.SOURCE_INPUTS)|{
 *('app/src/main/java/local/pocketchat/'+name+'.java' for name in ('GeckoCpuController','GeckoCpuNative','GeckoCpuProfile','GeckoCpuStore','GeckoCpuSpec','ProfileContext','NormalCaretSdkReceipt')),
 'tools/browser/check_gecko_cpu_ip_combo_evidence.py','tools/browser/run_gecko_cpu_ip_combo_integration.py',
 'tests/gecko/GeckoCpuIpComboIntegrationActivity.java','tests/gecko/GeckoCpuIpComboEvidenceProvider.java',
 'tests/gecko/assets/gecko-cpu-ip-combo-page.js'}


def require(value,message):
    if not value:raise ValueError('CPU/IP combo evidence: '+message)
def equal(actual,wanted,message):require(_typed_equal(actual,wanted),message)
def read_json(path,limit):
    path=Path(path);require(not any(p.is_symlink() for p in (path,*path.parents)),'ordinary nonsymlink evidence required')
    return ip.read_json(path,limit)
def no_overclaims(value):
    for field in ('actualPublicIpGeolocationVerified','workerCoverageVerified','serviceWorkerCoverageVerified','fingerprintProtectionVerified'):require(value.get(field) is False,'unsupported coverage claim: '+field)
def source_hashes(hashes,source,reader):
    require(type(hashes) is dict and SOURCE_INPUTS<=set(hashes) and len(hashes)<=10000,'selected producer dependencies absent')
    for path,digest in hashes.items():
        name=PurePosixPath(path);require(type(path) is str and len(path)<=256 and not name.is_absolute() and str(name)==path and '..' not in name.parts and '\\' not in path and '\0' not in path and ip.token(digest),'unsafe source pin')
        require(hashlib.sha256(reader(source,path)).hexdigest()==digest,'selected source bytes differ: '+path)
def process_sample(value,process,source,tree,nonce):
    equal(value,dict(schema=1,sourceCommit=source,sourceTree=tree,runNonce=nonce,slot=6,processName=PROCESS,expectedPid=process['pid'],observedPid=str(process['pid']),shellUid=2000),'independent shell process ownership differs')
def cpu_proof(activity,identity):
    process=activity['process'];ip.keys(process,('pid','uid','name'))
    require(ip.integer(process['pid'],1) and ip.integer(process['uid'],10000,99999) and process['name']==PROCESS,'actual profile6 process required')
    value=activity['cpuPolicy'];equal(value,activity['runtimeCpuPolicy'],'controller/runtime CPU snapshots differ');ip.keys(value,CPU_FIELDS)
    for field,wanted in dict(schema=1,engine='gecko',desiredMode='1',desiredRevision=2,activeBootMode='1',activeBootRevision=2,state='ready',issue='',failureCode='',pendingColdStart=False,configuredCap=1,defaultCap=1,hasUserValue=False,rfpPriority=False,nativeSettingReadback=True,startupReconciled=True,scope='runtime-wide',slot=6,pid=process['pid'],environmentId=identity['environmentId'],environmentGeneration=identity['generation'],pageObservationVerified=False,workerCoverageVerified=False,serviceWorkerCoverageVerified=False,persistentWorkerColdStartVerified=False).items():equal(value.get(field),wanted,'cold native CPU field differs: '+field)
    require(ip.token(value['processNonce'],32) and ip.token(value['runtimeNonce'],32),'CPU runtime/process incarnation missing')
    equal(activity['freshCpuReadback'],dict(configuredCap=1,defaultCap=1,hasUserValue=False,rfpPriority=False),'fresh SDK CPU preference read differs')
    stored=activity['cpuStoredState'];ip.keys(stored,('identity','revision','spec'));equal(stored['identity'],identity,'durable CPU owner differs');equal(stored['revision'],2,'durable CPU revision differs');equal(stored['spec'],dict(schema=1,engine='gecko',mode='1'),'durable CPU choice differs')
def trust(tls,host,binding):
    ip.keys(tls,('caPemSha256','leafDerSha256','subjectHashOld','opensslChainVerified','hostnameVerified','proxyIpSanVerified','ephemeral','privateMaterialLocation','privateMaterialExported','certificateExceptionUsed','binding','privateMaterialRemoved','trustInstallation'))
    equal(tls['binding'],binding,'host TLS invocation differs')
    require(tls['ephemeral'] is True and tls['privateMaterialLocation']=='host-tmp-only' and tls['privateMaterialExported'] is False and tls['privateMaterialRemoved'] is True and tls['opensslChainVerified'] is True and tls['certificateExceptionUsed'] is False and tls['proxyIpSanVerified']=='127.0.0.1' and tls['hostnameVerified']==['fp-a.pocketchat.test','fp-b.pocketchat.test','ipwho.is'],'ephemeral native TLS scope differs')
    require(ip.token(tls['caPemSha256']) and ip.token(tls['leafDerSha256']) and re.fullmatch('[0-9a-f]{8}',tls['subjectHashOld']) and tls['caPemSha256']==host['caPemSha256'] and tls['leafDerSha256']==host['leafDerSha256'],'controlled CA/leaf differs')
    value=tls['trustInstallation'];ip.keys(value,('method','androidUser','adbRoot','selinuxEnforcing','installedPublicCaBytesMatch','ownerAndMode','selinuxContext','subjectHashOld','appForceStoppedAfterInstall','publicCaPemSha256','expectedLeafDerSha256','evidenceShellUid','shellRestoredAfterInstall','removedAfterExecution','cleanupRootUid','cleanupShellUid','shellRestoredAfterCleanup'))
    for key,wanted in dict(method='domain-scoped-user-ca',androidUser=0,adbRoot=True,selinuxEnforcing=True,installedPublicCaBytesMatch=True,ownerAndMode='644:1000:1000',subjectHashOld=tls['subjectHashOld'],appForceStoppedAfterInstall=True,publicCaPemSha256=tls['caPemSha256'],expectedLeafDerSha256=tls['leafDerSha256'],evidenceShellUid=2000,shellRestoredAfterInstall=True,removedAfterExecution=True,cleanupRootUid=0,cleanupShellUid=2000,shellRestoredAfterCleanup=True).items():equal(value.get(key),wanted,'actual CA lifecycle differs: '+key)
    require(type(value['selinuxContext']) is str and re.fullmatch(r'u:object_r:(?!unlabeled)[A-Za-z0-9_]+:s0',value['selinuxContext']),'CA SELinux label differs')
def validate_behavior(report,source,expected,raw_values,reader):
    require(ip.token(source,40) and expected.get('sourceCommit')==source and expected.get('dirtySource') is False,'exact clean source reference required')
    ip.keys(report,('schema','fixtureType','status','sourceCommit','sourceTree','runNonce','expectedBuildIdentity','actualAndroidExecution','actualGeckoExecution','syntheticGeoService','actualPublicIpGeolocationVerified','workerCoverageVerified','serviceWorkerCoverageVerified','fingerprintProtectionVerified','executionInputsUnchanged','sourceFiles','activity','hostTls','routeReceipts','systemTimeZone','cleanup','prelaunchSetup','processSample'),('casePins','deviceReportReceivedSha256','rawExtractionScope','scope'))
    require(type(report) is dict and report.get('schema')==1 and type(report['schema']) is int and report.get('fixtureType')==FIXTURE_TYPE and report.get('status')=='passed' and report.get('sourceCommit')==source and report.get('sourceTree')==expected['sourceTree'] and ip.token(report.get('runNonce'),32),'successful source-bound combo summary required')
    require(report.get('actualAndroidExecution') is True and report.get('actualGeckoExecution') is True and report.get('syntheticGeoService') is True and report.get('executionInputsUnchanged') is True,'actual native combination execution absent');no_overclaims(report)
    ip.installed(report.get('expectedBuildIdentity'),expected,reader);source_hashes(report.get('sourceFiles'),source,reader)
    versions=re.findall(r'^\s*static final String VERSION=("(?:[^"\\]|\\.)*");',reader(source,'app/src/main/java/local/pocketchat/GeckoWebView.java').decode('utf-8'),re.M);require(len(versions)==1,'unique selected engine version required');engine=json.loads(versions[0])
    activity=report['activity'];ip.keys(activity,('schema','fixtureType','status','stage','failure','sourceCommit','sourceTree','runNonce','buildIdentity','activityClass','scopeAllocationActivity','setup','cpuSetup','cpuStoredState','process','page','native','cpuPolicy','runtimeCpuPolicy','freshCpuReadback','tls','checks','nativeEvents','actualAndroidExecution','actualGeckoExecution','productionChatSession','syntheticGeoService','actualPublicIpGeolocationVerified','workerCoverageVerified','serviceWorkerCoverageVerified','fingerprintProtectionVerified'));ip.installed(activity.get('buildIdentity'),expected,reader)
    require(activity.get('schema')==1 and type(activity['schema']) is int and activity.get('fixtureType')==FIXTURE_TYPE and activity.get('status')=='passed' and activity.get('stage')=='complete' and activity.get('failure')=='' and activity.get('sourceCommit')==source and activity.get('sourceTree')==expected['sourceTree'] and activity.get('runNonce')==report['runNonce'] and activity.get('activityClass')==ACTIVITY and activity.get('scopeAllocationActivity')==SCOPE_ACTIVITY,'actual combination activity/invocation differs')
    require(activity.get('actualAndroidExecution') is True and activity.get('actualGeckoExecution') is True and activity.get('productionChatSession') is True and activity.get('syntheticGeoService') is True,'production main session absent');no_overclaims(activity)
    before=report['prelaunchSetup'];after=activity['setup'];ip.keys(before,('schema','status','sourceCommit','sourceTree','runNonce','integrationApkSha256','slot','identity','unusedSlotBeforeSetup','scopeBeforeAnyProfileAccess','timezoneSealedRecordMissing','actualProfilesPrepare','actualDefaultStoreLoadYet','manualSeedAppliedToIpScope'));ip.keys(after,(*before,'defaultSpec','defaultRevision','loadedIdentity'));require(type(before['schema']) is int and before['schema']==1 and type(before['slot']) is int and before['slot']==6 and before['actualProfilesPrepare'] is True,'actual profile preparation missing');ip.environment(after['loadedIdentity']);identity=after['loadedIdentity']
    require(identity['slot']==6 and before.get('status')=='armed' and before.get('sourceCommit')==source and before.get('sourceTree')==expected['sourceTree'] and before.get('runNonce')==report['runNonce'] and before.get('integrationApkSha256')==expected['apkSha256'] and before.get('unusedSlotBeforeSetup') is True and before.get('scopeBeforeAnyProfileAccess') is True and before.get('timezoneSealedRecordMissing') is True and before.get('actualDefaultStoreLoadYet') is False and before.get('manualSeedAppliedToIpScope') is False,'fresh unused default-IP scope absent')
    for key in before:equal(after.get(key),True if key=='actualDefaultStoreLoadYet' else before[key],'scope changed during actual default load: '+key)
    equal(after['loadedIdentity'],before['identity'],'missing-store environment owner differs');equal(after['defaultSpec'],dict(schema=2,engine='gecko',mode='ip',zoneId=''),'actual missing store is not IP');equal(after['defaultRevision'],1,'default timezone revision differs')
    setup=activity['cpuSetup'];ip.keys(setup,('cpuSealedRecordMissingBefore','actualColdStoreSave','loadedMode','loadedRevision','savedMode','savedRevision','identity','sessionAbsentBeforeSetup'))
    equal(setup,dict(cpuSealedRecordMissingBefore=True,actualColdStoreSave=True,loadedMode='automatic',loadedRevision=1,savedMode='1',savedRevision=2,identity=identity,sessionAbsentBeforeSetup=True),'CPU choice was not durably saved before the real session')
    page=activity['page'];ip.keys(page,('schema','firstInline','secure','sourceCommit','runNonce','documentId','origin','phase','hardwareConcurrency','nativeGetter','nativeTimeZone','markerComplete','networkAllowed'))
    require(type(page['schema']) is int and page['schema']==1 and all(page[k] is True for k in ('firstInline','secure','nativeGetter','markerComplete','networkAllowed')) and type(page['hardwareConcurrency']) is int and page['hardwareConcurrency']==1 and page['sourceCommit']==source and page['runNonce']==report['runNonce'] and page['origin']=='https://fp-a.pocketchat.test' and page['phase']=='gecko-new-york' and type(page['documentId']) is str and re.fullmatch('[0-9a-f]{8}-(?:[0-9a-f]{4}-){3}[0-9a-f]{12}',page['documentId']),'same first-inline native CPU getter absent')
    ip.clock(page['nativeTimeZone'],'America/New_York');native=activity['native'];ip.native(native,'ip','America/New_York',engine);equal(native['identity'],identity,'CPU/timezone environment differs');equal(native['desiredRevision'],1,'default IP was replaced by a manual revision');require(native['privacyLevel']==1 and type(native['privacyLevel']) is int and native['nativeRfpConfirmed'] is False,'standard protection/native RFP scope differs')
    require(native['receipt']['ipObservation']['ip']=='8.8.8.8' and native['receipt']['ipObservation']['source']==ip.GEO_SOURCE,'controlled geo observation differs');cpu_proof(activity,identity)
    sdk=expected['sdkBuildIdentity'];binding=dict(sourceCommit=source,sourceTree=expected['sourceTree'],runNonce=report['runNonce'],integrationApkSha256=expected['apkSha256'],sdkRunId=sdk['runId'],sdkRunAttempt=sdk['runAttempt'])
    host=report['routeReceipts'];ip.route_snapshot(host,binding)
    require(host['closed'] is True and all(value==0 and type(value) is int for value in host['errors'].values()),'fixture route errors or unquiesced collector')
    events=host['events'];require(all(row['route']=='socks' and row['case']=='default-socks' for row in events),'combination crossed a different proxy/case')
    geos=[row for row in events if row['kind']=='geo'];require(len(geos)==1 and geos[0]['behavior']=='normal' and geos[0]['responseWritten'] is True and geos[0]['status']==200 and geos[0]['syntheticIp']=='8.8.8.8' and geos[0]['syntheticZoneId']=='America/New_York','exact single private synthetic geo response absent')
    targets=[row for row in events if row['kind']=='content' and row['path']=='/env-policy'];markers=[row for row in events if row['kind']=='content' and row['path']=='/worker-probe']
    require(len(targets)==1 and len(markers)==1 and all(row['host']=='fp-a.pocketchat.test' and row['phase']=='gecko-new-york' and row['responseWritten'] is True for row in (*targets,*markers)) and markers[0]['realm']=='document' and markers[0]['documentId']==page['documentId'] and geos[0]['sequence']<targets[0]['sequence'] and geos[0]['sequence']<markers[0]['sequence'],'same first-inline document lacks independent same-document wire marker after geo admission')
    security=activity['tls'];equal(security,dict(host='fp-a.pocketchat.test',isSecure=True,isException=False,leafDerSha256=host['leafDerSha256'],enterpriseRootsReadback=True),'actual native document TLS proof differs')
    trust(report['hostTls'],host,binding);system=report['systemTimeZone'];ip.keys(system,('before','after'));equal(system['before'],system['after'],'Android system timezone changed');ip.expected_clock(system['before'])
    process_sample(report['processSample'],activity['process'],source,expected['sourceTree'],report['runNonce'])
    checks=activity['checks'];equal(checks,[dict(id=name,**{'pass':True}) for name in CHECKS],'ordered actual combination assertions differ')
    native_events=activity['nativeEvents'];require(type(native_events) is list and 1<=len(native_events)<=80,'bounded native events absent')
    for index,event in enumerate(native_events,1):
        ip.keys(event,('sequence','kind','targetOwned','sessionId','navigation'));require(type(event['sequence']) is int and event['sequence']==index and event['kind'] in ('page-start','page-stop-true','page-stop-false') and type(event['targetOwned']) is bool and event['sessionId']==native['sessionId'] and ip.integer(event['navigation']),'native session/event order differs')
    require(any(e['kind']=='page-start' and e['targetOwned'] is True for e in native_events) and any(e['kind']=='page-stop-true' and e['targetOwned'] is True for e in native_events),'actual target navigation did not finish')
    equal(report['cleanup'],dict(appStopped=True,scopeCleared=True,reverseRemoved=True,caRemoved=True,privateMaterialRemoved=True,serverQuiesced=True),'all independent cleanups must succeed')
    require(set(raw_values)==set(RAW_FILES),'exact four raw JSONs required')
    payloads={'route-receipts.json':host,'setup-scope.json':dict(beforeLaunch=before,afterLoad=after,cpuSetup=setup,cpuStoredState=activity['cpuStoredState']),'process-sample.json':report['processSample']}
    equal(raw_values['combo.json'],activity,'original device JSON differs from summary snapshot')
    for name,raw in raw_values.items():
        if name!='combo.json':equal(raw,dict(schema=1,case=name[:-5],binding=binding,evidence=payloads[name]),'raw extraction differs from original combination fields: '+name)
    return dict(sourceCommit=source,sourceTree=expected['sourceTree'],runId=sdk['runId'],runAttempt=sdk['runAttempt'],runNonce=report['runNonce'],integrationApkSha256=expected['apkSha256'],caseCount=1,checkCount=len(checks),actualAndroidExecution=True,actualGeckoExecution=True,productionColdCpuDefaultIpCombinationPassed=True,pageHardwareConcurrency=page['hardwareConcurrency'],pageTimeZone=page['nativeTimeZone']['timeZone'],syntheticGeoService=True,actualPublicIpGeolocationVerified=False,workerCoverageVerified=False,serviceWorkerCoverageVerified=False,fingerprintProtectionVerified=False,scope='One canonical profile6 cold CPUcap1 + missing-store default-IP first-inline native page on the same SDK/native context/process and controlled SOCKS/TLS synthetic geo; no public location or whole Worker claim.')
def verify_gecko_cpu_ip_combo_evidence(directory,source,expected,reader=source_bytes):
    directory=Path(directory);rawdir=directory/RAW_DIRECTORY;require(directory.is_dir() and not directory.is_symlink() and rawdir.is_dir() and not rawdir.is_symlink() and {p.name for p in rawdir.iterdir()}==set(RAW_FILES),'exact real raw directory required')
    raw,report=read_json(directory/REPORT_NAME,2*1024*1024);values={};pins={}
    for name in RAW_FILES:
        data,value=read_json(rawdir/name,524288 if name=='combo.json' else 262144);values[name]=value;pins[name]=dict(bytes=len(data),sha256=hashlib.sha256(data).hexdigest())
    equal(report.get('casePins'),pins,'original raw file bytes/SHA differ');equal(report.get('deviceReportReceivedSha256'),pins['combo.json']['sha256'],'original device byte hash differs');value=validate_behavior(report,source,expected,values,reader);value.update(reportSha256=hashlib.sha256(raw).hexdigest(),caseSha256={k:v['sha256'] for k,v in pins.items()});return value

def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--directory',required=True,type=Path);parser.add_argument('--source',required=True);parser.add_argument('--device-reference',required=True,type=Path);args=parser.parse_args();_,device=read_json(args.device_reference,8*1024*1024)
    require(device.get('status')=='passed' and device.get('sourceCommit')==args.source and device.get('actualAndroidExecution') is True,'original actual installed reference absent');print(json.dumps(verify_gecko_cpu_ip_combo_evidence(args.directory,args.source,device['eventTransport']['buildIdentity'])))
if __name__=='__main__':main()
