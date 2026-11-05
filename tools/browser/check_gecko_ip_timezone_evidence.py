#!/usr/bin/env python3
"""Reject inconsistent source-bound Android IP timezone evidence.

The HTTPS geolocation responses are synthetic. This validator cannot establish
public location accuracy, complete Worker coverage or device execution by itself.
"""
import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import stat
import sys
from zoneinfo import ZoneInfo

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from gecko.profile_invocation_contract import verify_installed
from gecko.sdk_identity_contract import source_bytes, strict_json, _typed_equal, SDK_FIELDS, verify_sdk_identity

REPORT_NAME='gecko-ip-timezone-results.json'
RAW_DIRECTORY='gecko-ip-timezone-evidence'
FIXTURE_TYPE='gecko-production-ip-timezone-v1'
GEO_SOURCE='https://ipwho.is/?fields=success,ip,timezone.id'
CASES=('default-socks','route-switch-http','https-proxy','cancel-late','manual-system',
       'manual-iana','rfp-priority','manual-rfp-denied','bootstrap-isolation',
       'redirect-rejected','invalid-geo-rejected')
RAW_FILES=tuple(name+'.json' for name in (*CASES,'route-receipts','setup-scope'))
ROUTES={'socks':('socks5',18766,'America/New_York','8.8.8.8'),
        'http':('http-connect',18767,'Asia/Kathmandu','1.1.1.1'),
        'https':('https-connect',18768,'UTC','9.9.9.9')}
ORIGINS={'https://fp-a.pocketchat.test','https://fp-b.pocketchat.test'}
SAMPLES={'default-socks','route-switch-http','https-proxy','manual-system','manual-iana','rfp-priority'}
STATUS_KEYS=('schema','engine','loaded','desiredMode','desiredZone','desiredRevision','state','effectiveMode','rfpPriority','effectiveZone','observedIp','ipMatched','ipRouteStamp','ipObservedAt','ipSource','nativeSettingReadback','scope','appliedScope','pageObservationVerified','workerCoverageVerified','serviceWorkerCoverageVerified','issue')
REQUIRED={name+'.'+suffix for name in SAMPLES for suffix in ('first-inline-native-clock','exact-native-context')}|{
 'default.actual-main-profile6','default.missing-store-ip','route-switch.visible-document-preserved',
 'route-switch.new-route-proof','route-switch.old-receipt-rejected','cancel.actual-owner-retired',
 'cancel.late-not-admitted','manual-system.no-geo','manual-iana.no-geo','rfp.auto-priority-browses',
 'rfp.manual-conflict-preserves','bootstrap.page-cannot-borrow','bootstrap.dedicated-cannot-borrow',
 'bootstrap.shared-cannot-borrow','bootstrap.service-cannot-borrow','bootstrap.exact-single-private-request',
 'bootstrap.lease-through-native-store-ack',
 'redirect-rejected.no-new-page','invalid-geo-rejected.blank-error-stops-spinner',
 'invalid-geo-rejected.explicit-manual-recovers','scope.worker-and-sw-unclaimed','scope.generic-not-gpt'}
SOURCE_INPUTS={
 'tools/browser/check_gecko_ip_timezone_evidence.py','tools/browser/run_gecko_ip_timezone_integration.py',
 'tools/browser/ip_timezone_fixture_server.py','tools/browser/fingerprint_fixture_server.py',
 'tools/browser/newworker_fixture_server.py','tools/gecko/profile_invocation_contract.py','tools/gecko/sdk_identity_contract.py',
 'tests/gecko/GeckoIpTimeZoneIntegrationActivity.java','tests/gecko/GeckoIpTimeZoneEvidenceProvider.java',
 'tests/gecko/IpTimeZoneFixtureApplication.java','tests/gecko/IpTimeZoneFixtureScopes.java',
 'tests/gecko/IntegrationBuildIdentity.java','tests/gecko/BrowserFingerprintIntegrationActivity.java',
 'tests/gecko/GeckoEnvironmentPolicyIntegrationActivity.java','tests/gecko/AndroidManifest.xml',
 'tests/gecko/res/xml/network_security.xml','tests/gecko/assets/gecko-ip-timezone-page.js',
 'tests/gecko/assets/gecko-environment-policy-page.js','tests/gecko/assets/worker-policy-page.js',
 'app/build.gradle','app/src/main/AndroidManifest.xml','app/src/main/res/xml/network_security.xml',
 '.github/workflows/browser-2_1-acceptance.yml',
}
# Keep the contract readable while binding every app-owned transport dependency.
SOURCE_INPUTS.update('app/src/main/java/local/pocketchat/'+name+'.java' for name in (
 'MainActivity','PocketApplication','ChatSession','Profiles','ProfileCatalog','SecretStore','GeckoWebView',
 'GeckoTimeZoneController','GeckoTimeZoneStore','GeckoTimeZonePolicy','GeckoTimeZoneSpec','GeckoTimeZoneUi',
 'GeckoIpTimeZonePolicy','GeckoIpRouteWatch','GeckoPopupNavigationUi','ChromiumRouteLease','BrowserBridgeRequests'))
SOURCE_INPUTS.add('app/src/main/java/org/mozilla/geckoview/AppSessionIdentity.java')
SOURCE_INPUTS.update('app/src/main/assets/gecko/'+name for name in (
 'manifest.json','background.js','ip-timezone-bootstrap.js','request-headers.js','request-identity-background.js',
 'native-timezone-bridge.js','native-timezone-api.js','native-timezone-schema.json'))


def require(value,message):
    if not value: raise ValueError('IP timezone evidence: '+message)
def integer(value,low=0,high=2**63-1): return type(value) is int and low<=value<=high
def token(value,size=64): return type(value) is str and re.fullmatch('[0-9a-f]{'+str(size)+'}',value) is not None
def text(value,maximum=160): return type(value) is str and 0<len(value)<=maximum and all(ord(c)>=32 for c in value)
def keys(value,required,optional=()):
    require(type(value) is dict and set(required)<=set(value)<=set(required)|set(optional),'unexpected/missing JSON keys')
def unclaimed(value):
    require(value.get('workerCoverageVerified') is False and value.get('serviceWorkerCoverageVerified') is False,'Worker coverage overclaimed')
def environment(value):
    keys(value,('slot','generation','environmentId'));require(integer(value['slot'],0,7) and integer(value['generation']) and text(value['environmentId'],36) and re.fullmatch('[0-9a-f]{8}-(?:[0-9a-f]{4}-){3}[0-9a-f]{12}',value['environmentId']),'environment identity invalid')
def expected_clock(zone_id):
    zone=ZoneInfo(zone_id);result={'timeZone':zone_id}
    for key,month in (('january',1),('july',7)):
        value=datetime(2026,month,15,12,tzinfo=timezone.utc).astimezone(zone)
        result[key]=dict(offsetMinutes=-int(value.utcoffset().total_seconds()//60),year=value.year,month=value.month,day=value.day,hour=value.hour,minute=value.minute)
    return result
def clock(value,wanted=None):
    keys(value,('timeZone','january','july'));require(text(value['timeZone'],80),'bounded IANA clock required')
    try: actual=expected_clock(value['timeZone'])
    except (ValueError,KeyError) as error: raise ValueError('IP timezone evidence: unknown clock zone') from error
    for season in ('january','july'):
        keys(value[season],('offsetMinutes','year','month','day','hour','minute'))
        require(all(type(v) is int for v in value[season].values()) and _typed_equal(value[season],actual[season]),'Date and Intl fixed-epoch observation differs')
    if wanted is not None:
        expected=expected_clock(wanted)
        require(all(_typed_equal(value[k],expected[k]) for k in ('january','july')),'required native IANA/DST effect absent')
        require(ZoneInfo(value['timeZone']).key==ZoneInfo(wanted).key or {value['timeZone'],wanted}<={'Asia/Kathmandu','Asia/Katmandu'} or {value['timeZone'],wanted}<={'UTC','Etc/UTC','Etc/GMT','GMT'},'Intl native zone differs')
def plain(value,depth=0):
    require(depth<=24,'JSON nesting exceeded')
    if type(value) is dict:
        require(len(value)<=10000 and all(type(k) is str and 0<len(k)<=256 for k in value),'JSON key bound exceeded')
        for v in value.values(): plain(v,depth+1)
    elif type(value) is list:
        require(len(value)<=10000,'JSON array bound exceeded')
        for v in value: plain(v,depth+1)
    elif type(value) is str:
        require(len(value)<=2048 and '\x00' not in value and '\r' not in value and '\n' not in value and 'PRIVATE KEY' not in value and 'BEGIN CERTIFICATE' not in value and not value.startswith(('/data/','/tmp/','file:')),'unsafe text in exported JSON')
    else: require(value is None or type(value) in (bool,int),'unexpected JSON primitive')

def read_json(path,limit):
    with os.fdopen(os.open(path,os.O_RDONLY|os.O_NOFOLLOW|os.O_NONBLOCK),'rb') as stream:
        info=os.fstat(stream.fileno());require(stat.S_ISREG(info.st_mode) and 0<info.st_size<=limit,'bounded regular JSON required')
        raw=stream.read(limit+1);require(len(raw)==info.st_size,'JSON changed during read')
    value=strict_json(raw);require(type(value) is dict,'JSON object required');plain(value);return raw,value

def installed(value,expected,reader):
    # Same original installed-APK fields, with typed comparisons and the
    # selected immutable-source reader forwarded through SDK validation too.
    # A historical official-only identity cannot qualify this new workload.
    require(type(value) is dict and type(expected) is dict,'installed identity object required')
    require(set(value)<=set(expected)|{'scope'},'unexpected installed identity field')
    require({'schema','package','sourceCommit','sourceTree','dirtySource','version','versionCode','sdkCoordinate','apkSha256','apkBytes','buildStampSha256','sdkBuildIdentity'}<=set(value) and {'schema','package','sourceCommit','sourceTree','dirtySource','version','versionCode','sdkCoordinate','apkSha256','apkBytes','buildStampSha256','sdkBuildIdentity'}<=set(expected),'mandatory installed fields missing')
    for key in ('schema','package','sourceCommit','sourceTree','dirtySource','version','versionCode',
                'sdkCoordinate','apkSha256','apkBytes','buildStampSha256','sdkBuildIdentity',*SDK_FIELDS):
        if key in expected or key in value:
            require(key in expected and key in value and _typed_equal(value[key],expected[key]),'installed APK/SDK differs: '+key)
    actual=verify_sdk_identity(value,reader=reader);verify_sdk_identity(expected,reader=reader)
    require(actual.get('sdkBuildKind')=='source-derived-java' and actual.get('sourceCommit')==expected['sourceCommit'] and actual.get('sourceTree')==expected['sourceTree'] and type(actual.get('runId')) is str and re.fullmatch('[1-9][0-9]*',actual['runId']) and type(actual.get('runAttempt')) is str and re.fullmatch('[1-9][0-9]*',actual['runAttempt']),'actual same-source/run/attempt derived SDK required')

def route_snapshot(value,binding):
    keys(value,('schema','binding','syntheticGeoService','actualPublicIpGeolocationVerified','productionEndpointOverride','geoSource','routes','events','errors','controlRequests','upstreamConnections','forwardingImplemented','certificateExceptionUsed','caPemSha256','leafDerSha256','closed'))
    require(type(value['schema']) is int and value['schema']==1 and _typed_equal(value['binding'],binding),'host source/APK/run binding differs')
    require(value['syntheticGeoService'] is True and value['actualPublicIpGeolocationVerified'] is False and value['productionEndpointOverride'] is False and value['geoSource']==GEO_SOURCE and value['upstreamConnections']==0 and type(value['upstreamConnections']) is int and value['forwardingImplemented'] is False and value['certificateExceptionUsed'] is False,'host scope or upstream claim differs')
    require(token(value['caPemSha256']) and token(value['leafDerSha256']) and type(value['closed']) is bool and integer(value['controlRequests'],1,20000),'host TLS/poll bounds invalid')
    require(value['routes']=={name:dict(protocol=row[0],guestPort=row[1]) for name,row in ROUTES.items()} and set(value['errors'])==set(ROUTES) and all(integer(v,0,1000) for v in value['errors'].values()),'host routes/errors differ')
    require(type(value['events']) is list and 1<=len(value['events'])<=240,'bounded actual proxy requests required')
    for sequence,row in enumerate(value['events'],1):
        common=('sequence','route','protocol','case','kind','host','path','tls','proxyTls','targetSni','responseWritten')
        if row.get('kind')=='geo':
            keys(row,(*common,'method','credentialsPresent','behavior','responseNonce'),('responseAttempted','responseWriteFailed','status','responseSha256','syntheticIp','syntheticZoneId'))
            require(row['host']=='ipwho.is' and row['path']=='/?fields=success,ip,timezone.id' and row['method']=='GET' and row['credentialsPresent'] is False and row['behavior'] in ('normal','hold','redirect','invalid') and row['responseNonce']==binding['runNonce']+'-'+row['route']+'-'+str(sequence),'fixed private geo transport differs')
            if row['responseWritten']:
                require(row.get('responseAttempted') is True and row.get('status')==(302 if row['behavior']=='redirect' else 200) and token(row.get('responseSha256')) and row.get('syntheticIp')==ROUTES[row['route']][3] and row.get('syntheticZoneId')==('Invalid/ControlledFixtureZone' if row['behavior']=='invalid' else ROUTES[row['route']][2]),'original synthetic geo response receipt differs')
                body=dict(success=True,ip=row['syntheticIp'],timezone={'id':row['syntheticZoneId']})
                require(row['responseSha256']==hashlib.sha256(json.dumps(body,separators=(',',':')).encode()).hexdigest(),'geo response bytes differ from observed IP/IANA')
        elif row.get('kind')=='content':
            keys(row,(*common,'phase','realm','documentId','responseSha256'))
            require(row['host'] in ('fp-a.pocketchat.test','fp-b.pocketchat.test') and row['path'] in ('/env-policy','/env-frame','/worker-probe','/dedicated.js','/module.js','/shared.js','/service.js','/sw-cached','/favicon.ico') and token(row['responseSha256']),'controlled content receipt differs')
        else: raise ValueError('IP timezone evidence: unknown proxy event kind')
        require(type(row['sequence']) is int and row['sequence']==sequence and row['route'] in ROUTES and row['protocol']==ROUTES[row['route']][0] and row['case'] in CASES and row['tls'] is True and row['proxyTls']==(row['route']=='https') and type(row['proxyTls']) is bool and row['targetSni']==row['host'] and type(row['responseWritten']) is bool,'proxy event order/TLS/route differs')

def page(value,source,nonce,wanted=None):
    keys(value,('schema','firstInline','secure','runNonce','sourceCommit','phase','origin','documentId','nativeUserAgent','nativeTimeZone','markerComplete','networkAllowed'))
    require(type(value['schema']) is int and value['schema']==1 and all(value[k] is True for k in ('firstInline','secure','markerComplete','networkAllowed')) and value['sourceCommit']==source and value['runNonce']==nonce and value['origin'] in ORIGINS and text(value['nativeUserAgent'],1024) and re.fullmatch('[0-9a-f]{8}-(?:[0-9a-f]{4}-){3}[0-9a-f]{12}',value['documentId']),'actual first-inline controlled document proof absent')
    clock(value['nativeTimeZone'],wanted)

def native(value,mode,wanted,engine):
    keys(value,('sessionId','sessionEpoch','contextId','freshReadback','receipt','desiredSpec','desiredRevision','identity','status','routeStamp','nativeRfpConfirmed','privacyLevel'))
    environment(value['identity']);require(value['identity']['slot']==6 and integer(value['desiredRevision'],1) and text(value['sessionId']) and text(value['sessionEpoch']) and text(value['contextId'],24) and value['contextId'].isdigit(),'canonical native session binding invalid')
    require(value['desiredSpec']==dict(schema=2,engine='gecko',mode=mode,zoneId='' if mode in ('ip','system') else wanted),'exact desired mode differs')
    receipt=value['receipt'];keys(receipt,('schema','identity','desiredRevision','processNonce','requestToken','binding','nativeSettingReadback','pageObservationVerified','workerCoverageVerified','serviceWorkerCoverageVerified','nativeReceipt','recordedAt'),('effectiveZoneId','ipObservation','rfpManaged'))
    require(type(receipt['schema']) is int and receipt['schema']==(2 if mode=='ip' else 1) and _typed_equal(receipt['identity'],value['identity']) and receipt['desiredRevision']==value['desiredRevision'] and type(receipt['desiredRevision']) is int and token(receipt['processNonce']) and token(receipt['requestToken']) and integer(receipt['recordedAt'],1) and receipt['nativeSettingReadback'] is True and receipt['pageObservationVerified'] is False,'current actual persisted native receipt required');unclaimed(receipt)
    binding=receipt['binding'];keys(binding,('engineVersion','sessionId','sessionEpoch','contextId'));require(binding['engineVersion']==engine and all(binding[k]==value[k] for k in ('sessionId','sessionEpoch','contextId')),'native source engine/session/open/context binding differs')
    effective='' if mode=='system' or value['privacyLevel']==2 else wanted
    ack_keys=('schema','status','requestToken','sessionId','requestedZoneId','nativeZoneId','contextId','nativeSettingReadback','scope','workerCoverageVerified','serviceWorkerCoverageVerified')
    for name,kind in (('nativeReceipt','applied'),('freshReadback','read')):
        ack=receipt[name] if name=='nativeReceipt' else value[name];keys(ack,ack_keys)
        require(type(ack['schema']) is int and ack['schema']==1 and ack['status']==kind and token(ack['requestToken']) and ack['sessionId']==value['sessionId'] and ack['contextId']==value['contextId'] and ack['requestedZoneId']==ack['nativeZoneId']==effective and ack['nativeSettingReadback'] is True and ack['scope']=='top-browsing-context','native apply/read ACK differs');unclaimed(ack)
    require(receipt['nativeReceipt']['requestToken']==receipt['requestToken'] and value['freshReadback']['requestToken']!=receipt['requestToken'],'fresh read must be independently requested')
    status=value['status'];keys(status,STATUS_KEYS,('currentSessionPrepared','popupScope'));require(type(status.get('schema')) is int and status['schema']==1 and status.get('engine')=='gecko' and status.get('loaded') is True and status.get('desiredMode')==mode and type(status.get('desiredRevision')) is int and status.get('desiredRevision')==value['desiredRevision'] and status.get('nativeSettingReadback') is True and status.get('currentSessionPrepared') is True and status.get('pageObservationVerified') is False and not status.get('issue'),'controller current native gate is not ready');unclaimed(status)
    if mode=='ip':
        require(set(receipt)=={'schema','identity','desiredRevision','processNonce','requestToken','binding','nativeSettingReadback','pageObservationVerified','workerCoverageVerified','serviceWorkerCoverageVerified','nativeReceipt','recordedAt','effectiveZoneId','ipObservation','rfpManaged'},'IP sidecar fields missing')
        require(type(receipt['rfpManaged']) is bool,'typed RFP management required')
        if value['privacyLevel']==2:
            require(receipt['rfpManaged'] is True and receipt['ipObservation'] is None and receipt['effectiveZoneId']=='' and status.get('rfpPriority') is True and status.get('effectiveMode')=='rfp-priority' and status.get('ipMatched') is False and value['nativeRfpConfirmed'] is True,'RFP must reset override without claiming IP matching')
        else:
            observation=receipt['ipObservation'];keys(observation,('schema','source','ip','zoneId','routeStamp','observedAt'))
            require(receipt['rfpManaged'] is False and receipt['effectiveZoneId']==wanted and type(observation['schema']) is int and observation['schema']==1 and observation['source']==GEO_SOURCE and observation['zoneId']==wanted and token(observation['routeStamp']) and observation['routeStamp']==value['routeStamp']==status.get('ipRouteStamp') and observation['ip']==status.get('observedIp') and observation['observedAt']==status.get('ipObservedAt') and integer(observation['observedAt'],1) and status.get('ipMatched') is True and status.get('ipSource')==GEO_SOURCE and status.get('effectiveZone')==wanted,'route-bound current observed IP receipt differs')
    else: require(status.get('ipMatched') is False,'manual mode must not claim IP matching')

def validate_behavior(report,source,expected,raw_values,reader):
    keys(report,('schema','fixtureType','status','sourceCommit','sourceTree','runNonce','expectedBuildIdentity','actualAndroidExecution','actualGeckoExecution','syntheticGeoService','actualPublicIpGeolocationVerified','workerCoverageVerified','serviceWorkerCoverageVerified','executionInputsUnchanged','sourceFiles','activity','hostTls','routeReceipts','systemTimeZone','cleanup'),('fingerprintProtectionVerified','casePins','deviceReportReceivedSha256','rawExtractionScope','scope'))
    require(token(source,40) and expected.get('sourceCommit')==source and expected.get('dirtySource') is False and report.get('sourceCommit')==source and report.get('sourceTree')==expected.get('sourceTree') and token(report.get('runNonce'),32),'exact source/tree/invocation required')
    require(report.get('schema')==1 and type(report.get('schema')) is int and report.get('fixtureType')==FIXTURE_TYPE and report.get('status')=='passed' and report.get('actualAndroidExecution') is True and report.get('actualGeckoExecution') is True and report.get('syntheticGeoService') is True and report.get('actualPublicIpGeolocationVerified') is False and report.get('fingerprintProtectionVerified',False) is False and report.get('executionInputsUnchanged') is True,'successful actual Android synthetic-geo workload required');unclaimed(report)
    identity=report.get('expectedBuildIdentity',{});installed(identity,expected,reader)
    for k,v in expected.items():
        if k in identity: require(_typed_equal(identity[k],v),'typed expected APK identity differs: '+k)
    activity=report.get('activity',{});installed(activity.get('buildIdentity',{}),expected,reader)
    keys(activity,('schema','fixtureType','engine','status','stage','failedAtStage','failure','sourceCommit','sourceTree','runNonce','buildIdentity','checks','cases','setup','nativeEvents','lastPage','currentTimeZonePolicy','actualAndroidExecution','actualGeckoExecution','syntheticGeoService','actualPublicIpGeolocationVerified','workerCoverageVerified','serviceWorkerCoverageVerified','fingerprintProtectionVerified','scope'))
    require(activity.get('fixtureType')==FIXTURE_TYPE and activity.get('sourceCommit')==source and activity.get('sourceTree')==expected['sourceTree'] and activity.get('runNonce')==report['runNonce'] and activity.get('status')=='passed' and activity.get('stage')=='complete' and not activity.get('failure') and not activity.get('failedAtStage') and activity.get('actualAndroidExecution') is True and activity.get('actualGeckoExecution') is True and activity.get('actualPublicIpGeolocationVerified') is False and activity.get('syntheticGeoService') is True,'device actual source-bound terminal report missing');unclaimed(activity)
    require(activity.get('fingerprintProtectionVerified') is False,'whole fingerprint claim forbidden')
    require(type(activity['nativeEvents']) is list and len(activity['nativeEvents'])<=160,'bounded native event list required')
    for sequence,event in enumerate(activity['nativeEvents'],1):
        keys(event,('sequence','kind','path','sessionId','navigation','stage'));require(type(event['sequence']) is int and event['sequence']==sequence and event['kind'] in ('page-start','page-stop-true','page-stop-false') and event['path'] in ('/env-policy','/env-frame','other') and text(event['sessionId']) and integer(event['navigation']) and event['stage'] in (*CASES,'startup','complete'),'unknown/unsafe native event')
    hashes=report.get('sourceFiles');require(type(hashes) is dict and SOURCE_INPUTS<=set(hashes) and len(hashes)<=10000,'required actual source dependencies missing')
    for path,digest in hashes.items():
        require(text(path,256) and str(PurePosixPath(path))==path and not PurePosixPath(path).is_absolute() and '..' not in PurePosixPath(path).parts and '\\' not in path and '\0' not in path and token(digest),'unsafe source file pin')
        require(hashlib.sha256(reader(source,path)).hexdigest()==digest,'tested immutable source differs: '+path)
    production=reader(source,'app/src/main/java/local/pocketchat/GeckoWebView.java').decode()
    versions=re.findall(r'^\s*static final String VERSION=("(?:[^"\\]|\\.)*");',production,re.M);require(len(versions)==1,'unique selected Gecko engine version required');engine=json.loads(versions[0])
    sdk=expected['sdkBuildIdentity'];binding=dict(sourceCommit=source,sourceTree=expected['sourceTree'],runNonce=report['runNonce'],integrationApkSha256=expected['apkSha256'],sdkRunId=sdk['runId'],sdkRunAttempt=sdk['runAttempt'])
    require(set(raw_values)==set(RAW_FILES),'exact original raw JSON set required')
    for name,value in raw_values.items():
        keys(value,('schema','case','binding','evidence'));require(type(value['schema']) is int and value['schema']==1 and value['case']==name[:-5] and _typed_equal(value['binding'],binding),'raw case invocation differs')
    case_values=activity.get('cases',{});require(set(case_values)==set(CASES),'all eleven actual cases required')
    for name in CASES: require(_typed_equal(raw_values[name+'.json']['evidence'],case_values[name]),'raw case differs from original device evidence: '+name)
    setup=raw_values['setup-scope.json']['evidence'];keys(setup,('schema','status','sourceCommit','sourceTree','runNonce','integrationApkSha256','slot','identity','unusedSlotBeforeSetup','scopeBeforeAnyProfileAccess','timezoneSealedRecordMissing','actualProfilesPrepare','actualDefaultStoreLoadYet','manualSeedAppliedToIpScope','defaultSpec','defaultRevision','loadedIdentity'));require(_typed_equal(activity.get('setup'),setup),'setup extraction differs')
    require(setup.get('status')=='armed' and setup.get('sourceCommit')==source and setup.get('sourceTree')==expected['sourceTree'] and setup.get('runNonce')==report['runNonce'] and setup.get('integrationApkSha256')==expected['apkSha256'] and setup.get('slot')==6 and all(setup.get(k) is True for k in ('unusedSlotBeforeSetup','scopeBeforeAnyProfileAccess','timezoneSealedRecordMissing','actualProfilesPrepare','actualDefaultStoreLoadYet')) and setup.get('manualSeedAppliedToIpScope') is False and setup.get('defaultSpec')==dict(schema=2,engine='gecko',mode='ip',zoneId='') and type(setup.get('defaultRevision')) is int and setup['defaultRevision']==1 and _typed_equal(setup.get('loadedIdentity'),setup.get('identity')),'actual missing sealed record/default MainActivity scope proof required');environment(setup['identity'])
    checks=activity.get('checks');require(type(checks) is list and 0<len(checks)<=128,'bounded actual checks required');ids=[]
    for row in checks: keys(row,('id','pass'));require(text(row['id']) and row['pass'] is True,'failed actual assertion');ids.append(row['id'])
    require(len(ids)==len(set(ids)) and REQUIRED<=set(ids),'missing/duplicate original IP assertions')
    system=report.get('systemTimeZone',{});require(type(system) is dict and system.get('before')==system.get('after') and text(system.get('before'),80),'Android system timezone changed')
    desired={'default-socks':('ip','America/New_York'),'route-switch-http':('ip','Asia/Kathmandu'),'https-proxy':('ip','UTC'),'manual-system':('system',system['before']),'manual-iana':('iana','Asia/Kathmandu'),'rfp-priority':('ip','UTC')}
    for name,(mode,wanted) in desired.items():
        sample=case_values[name];keys(sample,('page','frames','workers','native','security','case'),('oldTicketReadAttempted','oldTicketRejected','geoCountBefore','geoCountAfter'));require(sample['case']==name,'sample case differs');page(sample['page'],source,report['runNonce'],wanted)
        require(type(sample['frames']) is list and len(sample['frames'])==2 and {v.get('origin') for v in sample['frames']}==ORIGINS,'both real controlled frames required')
        for frame in sample['frames']: page(frame,source,report['runNonce'])
        native(sample['native'],mode,wanted,engine);require(_typed_equal(sample['native']['identity'],setup['identity']) and sample['native']['privacyLevel']==(2 if name=='rfp-priority' else 1) and type(sample['native']['privacyLevel']) is int,'sample environment/protection owner differs')
        security=sample['security'];keys(security,('host','isSecure','isException','leafDerSha256','enterpriseRootsReadback'));require(security['host']=='fp-a.pocketchat.test' and security['isSecure'] is True and security['isException'] is False and security['enterpriseRootsReadback'] is True and security['leafDerSha256']==report['hostTls']['leafDerSha256'],'real target TLS certificate differs')
        if name in ('manual-system','manual-iana','rfp-priority'):require(integer(sample.get('geoCountBefore')) and sample['geoCountBefore']==sample.get('geoCountAfter'),'manual/RFP mode made geo lookup')
    first,second=case_values['default-socks'],case_values['route-switch-http'];require(first['native']['routeStamp']!=second['native']['routeStamp'] and first['native']['receipt']['requestToken']!=second['native']['receipt']['requestToken'] and second.get('oldTicketReadAttempted') is True and second.get('oldTicketRejected') is True,'old-route native ticket not rejected')
    workers=first['workers'];keys(workers,('started','complete','cases'));require(workers['started'] is True and workers['complete'] is True and set(workers['cases'])=={'classic','module','blob','shared','service'},'raw all Worker scope observations required')
    for row in workers['cases'].values():
        keys(row,('available','created','executed','networkAllowed','nativeUserAgent','nativeTimeZone'),('sourceRole','documentGuard','auditAvailable'))
        require(row.get('available') is True and row.get('created') is True and row.get('executed') is True and row.get('networkAllowed') is True and text(row.get('nativeUserAgent'),1024),'real Worker observer incomplete');clock(row.get('nativeTimeZone'))
    host=raw_values['route-receipts.json']['evidence'];require(_typed_equal(report.get('routeReceipts'),host),'final route receipt extraction differs');route_snapshot(host,binding);require(host['closed'] is True,'final native server still has writers')
    for route,case in (('socks','default-socks'),('http','route-switch-http'),('https','https-proxy')):
        rows=[r for r in host['events'] if r['case']==case and r['route']==route];geo=[r for r in rows if r['kind']=='geo' and r['responseWritten']];docs=[r for r in rows if r['kind']=='content' and r['path']=='/env-policy'];require(geo and docs and geo[0]['sequence']<docs[0]['sequence'],'native first document escaped required same-route HTTPS geo bootstrap')
        observation=case_values[case]['native']['receipt']['ipObservation'];require(observation['ip']==ROUTES[route][3] and observation['zoneId']==ROUTES[route][2],'native receipt does not match actual proxy response')
    cancel=case_values['cancel-late'];keys(cancel,('explicitProductionMethodBoundary','actualUserGesture','oldDocumentId','pending','after','lateResultAdmitted'));keys(cancel['after'],STATUS_KEYS,('currentSessionPrepared','popupScope'));require(cancel.get('explicitProductionMethodBoundary') is True and cancel.get('actualUserGesture') is False and cancel.get('lateResultAdmitted') is False and cancel.get('after',{}).get('nativeSettingReadback') is False and cancel.get('after',{}).get('ipMatched') is False,'late/cancel owner result was admitted');route_snapshot(cancel['pending'],binding)
    isolation=case_values['bootstrap-isolation'];keys(isolation,('schema','runNonce','sourceCommit','documentId','source','started','complete','roles','pending','afterAttempts','explicitProductionMethodBoundary','actualUserGesture','nativeApplyLease','nativeAfter','livePrivateCapabilityDuringAttempts'));require(isolation.get('explicitProductionMethodBoundary') is True and isolation.get('actualUserGesture') is False and isolation.get('complete') is True and isolation.get('source')==GEO_SOURCE and isolation.get('runNonce')==report['runNonce'] and isolation.get('sourceCommit')==source and set(isolation.get('roles',{}))=={'page','dedicated','shared','service'},'actual bootstrap isolation observation absent')
    for row in isolation['roles'].values(): keys(row,('available','created','executed','networkAllowed'));require(all(row[k] is True for k in ('available','created','executed')) and row['networkAllowed'] is False,'ordinary page/Worker borrowed the private bootstrap capability')
    lease=isolation.get('nativeApplyLease',{});keys(lease,('actualNativeAck','leaseHeldBeforeNativeAckPublication','controllerPreparedBeforePublication','ack','leaseReleasedAfterNativeAndStoreAck'))
    require(isolation.get('livePrivateCapabilityDuringAttempts') is True and lease['actualNativeAck'] is True and lease['leaseHeldBeforeNativeAckPublication'] is True and lease['controllerPreparedBeforePublication'] is False and lease['leaseReleasedAfterNativeAndStoreAck'] is True,'route lease must span actual native apply and persisted store ACK')
    native(isolation.get('nativeAfter'),'ip','UTC',engine);require(isolation['nativeAfter']['privacyLevel']==1 and _typed_equal(lease['ack'],isolation['nativeAfter']['receipt']['nativeReceipt']),'observed original native apply ACK differs from actual stored receipt')
    for key in ('pending','afterAttempts'):route_snapshot(isolation[key],binding)
    pending=[r for r in isolation['pending']['events'] if r['case']=='bootstrap-isolation' and r['kind']=='geo'];after=[r for r in isolation['afterAttempts']['events'] if r['kind']=='geo'];before=[r for r in isolation['pending']['events'] if r['kind']=='geo'];require(len(pending)==1 and pending[0]['responseWritten'] is False and pending[0]['behavior']=='hold' and _typed_equal(before,after),'server observed an unauthorized extra geo request')
    conflict=case_values['manual-rfp-denied'];keys(conflict,('actualUiAttempt','revisionBefore','revisionAfter','manualSaveRejected','status','privacyLevel'));keys(conflict['status'],STATUS_KEYS,('currentSessionPrepared','popupScope'));require(conflict.get('actualUiAttempt') is True and conflict.get('manualSaveRejected') is True and conflict.get('privacyLevel')==2 and type(conflict.get('revisionBefore')) is int and conflict['revisionBefore']==conflict.get('revisionAfter') and conflict.get('status',{}).get('rfpPriority') is True,'manual IANA weakened RFP or saved through conflict')
    for name,behavior in (('redirect-rejected','redirect'),('invalid-geo-rejected','invalid')):
        value=case_values[name];require(value.get('fallbackApplied') is False and text(value.get('oldDocumentId'),36) and value.get('status',{}).get('state')=='failed' and value['status'].get('nativeSettingReadback') is False and value['status'].get('ipMatched') is False,'geo failure did not keep the new target closed')
        keys(value['status'],STATUS_KEYS,('currentSessionPrepared','popupScope'))
        if name=='redirect-rejected':
            keys(value,('oldDocumentId','remainingDocumentId','status','host','actualAddressUiAttempt','fallbackApplied'));require(value.get('actualAddressUiAttempt') is True and value['oldDocumentId']==value.get('remainingDocumentId'),'redirect must not navigate the controlled existing page')
        else:
            keys(value,('oldDocumentId','newNativeSession','oldSessionId','failedSessionId','oldNativeRequestToken','actualSpontaneousLateCallbackObserved','blankBeforeRecovery','navigationStopped','navigationFailed','errorDisplayed','spinnerStopped','status','host','actualTimeZoneRetryUi','fallbackApplied','queuedTargetRetained','manualRecovery','actualManualUiRecovery','geoCountBeforeRecovery','geoCountAfterRecovery'))
            require(all(value.get(k) is True for k in ('newNativeSession','blankBeforeRecovery','navigationStopped','navigationFailed','errorDisplayed','spinnerStopped','actualTimeZoneRetryUi','queuedTargetRetained','actualManualUiRecovery')) and integer(value.get('geoCountBeforeRecovery'),1) and value['geoCountBeforeRecovery']==value.get('geoCountAfterRecovery'),'real blank-IP failure/progress/manual-recovery proof missing')
            recovery=value.get('manualRecovery',{});require(recovery.get('case')=='invalid-geo-recovery','manual recovery case differs');page(recovery.get('page'),source,report['runNonce'],system['before']);native(recovery.get('native'),'system',system['before'],engine)
            require(text(value['oldSessionId']) and text(value['failedSessionId']) and value['oldSessionId']!=value['failedSessionId'] and token(value['oldNativeRequestToken']) and recovery['native']['receipt']['requestToken']!=value['oldNativeRequestToken'] and value['actualSpontaneousLateCallbackObserved'] is False,'fresh actual SDK owner/native ticket or honest callback scope absent')
        route_snapshot(value['host'],binding);rows=[r for r in value['host']['events'] if r['case']==name];require(any(r['kind']=='geo' and r['behavior']==behavior and r['responseWritten'] for r in rows) and not any(r['kind']=='content' for r in rows),'redirect/invalid scenario missing or forwarded to a page')
    cleanup=report.get('cleanup',{});require(set(cleanup)=={'appStopped','scopeCleared','reverseRemoved','caRemoved','privateMaterialRemoved','serverQuiesced'} and all(v is True for v in cleanup.values()),'all real fixture cleanup must succeed')
    tls=report['hostTls'];keys(tls,('caPemSha256','leafDerSha256','subjectHashOld','opensslChainVerified','hostnameVerified','proxyIpSanVerified','ephemeral','privateMaterialLocation','privateMaterialExported','certificateExceptionUsed','binding','privateMaterialRemoved','trustInstallation'));require(tls.get('ephemeral') is True and tls.get('privateMaterialLocation')=='host-tmp-only' and tls.get('caPemSha256')==host['caPemSha256'] and tls.get('leafDerSha256')==host['leafDerSha256'] and tls.get('opensslChainVerified') is True and set(tls.get('hostnameVerified',[]))=={'ipwho.is','fp-a.pocketchat.test','fp-b.pocketchat.test'} and tls.get('proxyIpSanVerified')=='127.0.0.1' and tls.get('certificateExceptionUsed') is False and tls.get('privateMaterialExported') is False and tls.get('privateMaterialRemoved') is True and _typed_equal(tls.get('binding'),binding),'controlled real host trust/cleanup binding differs')
    trust=tls.get('trustInstallation',{});keys(trust,('method','androidUser','adbRoot','selinuxEnforcing','installedPublicCaBytesMatch','ownerAndMode','selinuxContext','subjectHashOld','appForceStoppedAfterInstall','publicCaPemSha256','expectedLeafDerSha256','evidenceShellUid','shellRestoredAfterInstall','removedAfterExecution','cleanupRootUid','cleanupShellUid','shellRestoredAfterCleanup'));require(trust.get('method')=='domain-scoped-user-ca' and type(trust.get('androidUser')) is int and trust['androidUser']==0 and trust.get('adbRoot') is True and trust.get('installedPublicCaBytesMatch') is True and trust.get('ownerAndMode')=='644:1000:1000' and re.fullmatch(r'u:object_r:(?!unlabeled)[A-Za-z0-9_]+:s0',trust.get('selinuxContext','')) and trust.get('subjectHashOld')==tls['subjectHashOld'] and trust.get('appForceStoppedAfterInstall') is True and trust.get('publicCaPemSha256')==tls['caPemSha256'] and trust.get('expectedLeafDerSha256')==tls['leafDerSha256'] and type(trust.get('evidenceShellUid')) is int and trust['evidenceShellUid']==2000 and trust.get('shellRestoredAfterInstall') is True and trust.get('removedAfterExecution') is True and type(trust.get('cleanupRootUid')) is int and trust['cleanupRootUid']==0 and type(trust.get('cleanupShellUid')) is int and trust['cleanupShellUid']==2000 and trust.get('selinuxEnforcing') is True and trust.get('shellRestoredAfterCleanup') is True,'actual ephemeral CA installation/removal proof absent')
    observed={name:row['nativeTimeZone']['timeZone'] for name,row in workers['cases'].items()}
    return dict(sourceCommit=source,sourceTree=expected['sourceTree'],integrationApkSha256=expected['apkSha256'],runId=sdk['runId'],runAttempt=sdk['runAttempt'],runNonce=report['runNonce'],caseCount=13,checkCount=len(checks),actualAndroidExecution=True,actualGeckoExecution=True,syntheticGeoService=True,actualPublicIpGeolocationVerified=False,workerCoverageVerified=False,serviceWorkerCoverageVerified=False,observedWorkerTimeZones=observed,routeProtocols=[ROUTES[k][0] for k in ROUTES],scope='Source-bound canonical MainActivity native IP timezone and same configured proxy transport on controlled synthetic HTTPS geo responses; no public geolocation or whole-Worker timezone claim.')

def verify_gecko_ip_timezone_evidence(directory,source,expected,reader=source_bytes):
    directory=Path(directory);require(directory.is_dir() and not directory.is_symlink(),'real evidence root required');rawdir=directory/RAW_DIRECTORY;require(rawdir.is_dir() and not rawdir.is_symlink() and {p.name for p in rawdir.iterdir()}==set(RAW_FILES),'exact real raw directory required')
    raw,report=read_json(directory/REPORT_NAME,4*1024*1024);values={};pins={}
    for name in RAW_FILES:
        data,value=read_json(rawdir/name,262144);values[name]=value;pins[name]=dict(bytes=len(data),sha256=hashlib.sha256(data).hexdigest())
    require(_typed_equal(report.get('casePins'),pins),'original raw file bytes/SHA differ from summary')
    result=validate_behavior(report,source,expected,values,reader);result.update(reportSha256=hashlib.sha256(raw).hexdigest(),caseSha256={k:v['sha256'] for k,v in pins.items()});return result

def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--directory',required=True,type=Path);parser.add_argument('--source',required=True);parser.add_argument('--device-reference',required=True,type=Path);args=parser.parse_args()
    _,reference=read_json(args.device_reference,4*1024*1024);require(reference.get('status')=='passed' and reference.get('actualAndroidExecution') is True and reference.get('sourceCommit')==args.source,'successful original Android reference required');result=verify_gecko_ip_timezone_evidence(args.directory,args.source,reference['eventTransport']['buildIdentity']);import json;print(json.dumps(result,ensure_ascii=False))
if __name__=='__main__':main()
