#!/usr/bin/env python3
"""Run the additional actual Android default-IP timezone production gate once.

Three controlled native proxy/TLS transports terminate synthetic geo responses.
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
from check_gecko_ip_timezone_evidence import (SOURCE_INPUTS,REPORT_NAME,RAW_DIRECTORY,RAW_FILES,
    CASES,FIXTURE_TYPE,verify_gecko_ip_timezone_evidence,expected_clock,strict_json,_typed_equal)

ACTIVITY='local.pocketchat.test/local.pocketchat.GeckoIpTimeZoneIntegrationActivity'
URI='content://local.pocketchat.test.gecko-ip-timezone-evidence'
MAX_ACTIVITY_BYTES=4*1024*1024


def require(value,message):
    if not value:raise ValueError('IP timezone runner: '+message)
def write_json(path,value):
    raw=(json.dumps(value,ensure_ascii=False,separators=(',',':'))+'\n').encode()
    limit=4*1024*1024 if path.name==REPORT_NAME else 262144
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
    # Startup content-provider errors are not JSON evidence. Once an invocation
    # matches, duplicate keys/NaN/identity mismatches are fatal, not normalized.
    try:value=json.loads(raw)
    except (ValueError,UnicodeError):return None
    if type(value) is not dict or value.get('runNonce')!=nonce:return None
    value=strict_json(raw)
    require(value.get('fixtureType')==FIXTURE_TYPE and value.get('sourceCommit')==source and value.get('sourceTree')==expected['sourceTree'],'device source/fixture differs')
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

EXTENSION_STAGES={'bootstrap-loaded','create-enter','create-rejected','create-ready','lookup-received','lookup-rejected','lookup-start','fetch-start','fetch-response','fetch-rejected','deadline','finish-null','finish-observed','before-request','before-redirect','authorization','native-lookup-received','bootstrap-bound','proxy-event','proxy-authorization','header-event','header-authorization','header-listener','hello-result','hello-send-start','hello-failed','snapshot-send-result','native-prepare-received','native-prepare-result','native-protection-received','native-protection-result','port-message-entry','port-connected','port-disconnected','watchdog-scheduled','watchdog-fired','watchdog-hello-start','watchdog-hello-result','watchdog-hello-failed','watchdog-snapshot-result'}
EXTENSION_RESULTS={'none','ready','rejected','missing-port','runtime-url','features','registration','exception','shape-or-busy','pending','accepted','absent','invalid','closed','cancelled','observed'}
EXTENSION_ERRORS={'none','AbortError','NetworkError','TypeError','SecurityError','TimeoutError','NotAllowedError','InvalidStateError','other'}
EXTENSION_SCRIPTS={'ip-timezone-bootstrap.js','request-headers.js','request-identity-background.js','native-timezone-bridge.js','background.js','other'}
def extension_debug(value,nonce):
    require(type(value) is dict and {'registered','accepted','rejected','latest'}<=set(value)<={'registered','accepted','rejected','latest','hello','poll','port','processes','legacyRead','windows'},'extension diagnostic keys differ')
    require(type(value['registered']) is bool and all(type(value[k]) is int and 0<=value[k]<=10000 for k in ('accepted','rejected')),'extension diagnostic counters differ')
    if 'hello' in value:require(type(value['hello']) is int and 0<=value['hello']<=10000,'hello counter differs')
    if 'poll' in value:
        poll=value['poll'];require(type(poll) is dict and set(poll)=={'count','ineligible','eligible','portPresent','extensionSame','runtimeSame','attempted','returned','threw','consoleEnabled','processPid','processUid'},'poll keys differ')
        for k,v in poll.items():require(type(v) is int and 0<=v<2**31 if k in ('processPid','processUid') else type(v) is int and 0<=v<=10000 if k in ('count','ineligible','attempted','returned','threw') else type(v) is bool,'poll value differs')
    if 'port' in value:
        port=value['port'];require(type(port) is dict and set(port)=={'present','id','disconnected','listenersRegistered','dispatcherPresent','dispatcherAttached','pendingMessages'},'port keys differ')
        for k,v in port.items():
            if k in ('present','dispatcherPresent'):require(type(v) is bool,'port present flag differs')
            elif k in ('id','pendingMessages'):require(v is None or type(v) is int and -1<=v<=2**63-1 and (k!='pendingMessages' or v<=10000),'port number differs')
            else:require(v is None or type(v) is bool,'port field differs')
    if 'processes' in value:
        require(type(value['processes']) is list and len(value['processes'])<=64,'native process bound differs')
        for process in value['processes']:require(type(process) is dict and set(process)=={'pid','uid','role'} and type(process['pid']) is int and 1<process['pid']<2**31 and type(process['uid']) is int and 0<=process['uid']<2**31 and process['role'] in ('profile6','gecko-env6'),'native process identity differs')
    if 'windows' in value:
        require(type(value['windows']) is list and len(value['windows'])<=8,'window diagnostic bound differs')
        for row in value['windows']:
            require(type(row) is dict and set(row)=={'sequence','revalidate','completed','reason','received','ready','consumer'} and type(row['sequence']) is int and 1<=row['sequence']<=10000 and all(type(row[k]) is bool for k in ('revalidate','completed')) and row['reason'] in ('none','success','error','timeout','throw','revalidate-error') and all(row[k] is None or type(row[k]) is bool for k in ('received','ready','consumer')),'window diagnostic row differs')
    if 'legacyRead' in value:
        control=value['legacyRead'];require(type(control) is dict and set(control)=={'attempted','returned','threw','id','pendingDelta','portCurrent','responseVerified'} and all(type(control[k]) is bool for k in ('attempted','returned','threw','portCurrent','responseVerified')) and control['responseVerified'] is False and type(control['id']) is int and 0<=control['id']<=2147483647 and type(control['pendingDelta']) is int and control['pendingDelta']==0,'legacy readonly control differs')
    latest=value['latest'];require(type(latest) is dict,'extension diagnostic payload object required')
    if not latest:return value
    require(set(latest)=={'schema','diagnosticOnly','releaseAcceptance','requestNonce','runtimeManifest','helperPresence','events','omitted','invalid','bootstrapObject','bootstrapCreate','headersObject'},'extension payload keys differ')
    require(type(latest['schema']) is int and latest['schema']==1 and latest['diagnosticOnly'] is True and latest['releaseAcceptance'] is False and latest['requestNonce']==nonce,'extension diagnostic scope/nonce differs')
    require(all(type(latest[k]) is int and 0<=latest[k]<=10000 for k in ('omitted','invalid')) and all(type(latest[k]) is bool for k in ('bootstrapObject','bootstrapCreate','headersObject')),'extension payload counter/flag differs')
    manifest=latest['runtimeManifest'];require(type(manifest) is dict and set(manifest)=={'available','version','id','scriptCount','scripts'},'runtime manifest keys differ')
    require(type(manifest['available']) is bool and manifest['version'] in ('2.1.2.104','other','unavailable') and manifest['id'] in ('browser@pocketchat.local','other','unavailable') and type(manifest['scriptCount']) is int and -1<=manifest['scriptCount']<=10000,'runtime manifest values differ')
    require(type(manifest['scripts']) is list and len(manifest['scripts'])<=8 and all(type(v) is str and v in EXTENSION_SCRIPTS for v in manifest['scripts']),'runtime manifest scripts differ')
    helpers=latest['helperPresence'];require(type(helpers) is dict and set(helpers)=={'bootstrap','headers','identity','timezone'} and all(type(v) is str and v in ('undefined','object','function','boolean','number','string','symbol','bigint') for v in helpers.values()),'runtime helper presence differs')
    rows=latest['events'];require(type(rows) is list and len(rows)<=32,'extension event bound differs')
    for i,row in enumerate(rows):
        require(type(row) is dict and {'sequence','stage','urlClass','exactGeo','get','origin','document','requestIdPresent','result','errorName'}<=set(row)<={'sequence','stage','urlClass','exactGeo','get','origin','document','requestIdPresent','result','errorName','generation','portCurrent','messageType','kindClass','nestedKindClass','hasKind','hasMessage','hasData'},'extension event keys differ')
        require(type(row['sequence']) is int and row['sequence']==i+1 and row['stage'] in EXTENSION_STAGES and row['urlClass'] in ('geo-exact','geo-host-variant','other') and row['origin'] in ('own','foreign','absent','invalid','unseen') and row['document'] in ('own','foreign','absent','invalid','unseen') and row['result'] in EXTENSION_RESULTS and row['errorName'] in EXTENSION_ERRORS,'extension event enum differs')
        require(all(type(row[k]) is bool for k in ('exactGeo','get','requestIdPresent')),'extension event flag differs')
        extra={'generation','portCurrent','messageType','kindClass','nestedKindClass','hasKind','hasMessage','hasData'}
        if set(row)&extra:
            require(extra<=set(row) and type(row['generation']) is int and 0<=row['generation']<=10000 and row['messageType'] in ('undefined','object','string','boolean','number','function','symbol','bigint','null') and row['kindClass'] in ('prepare','protection','lookup','snapshot','cancel','header-policy','timezone-read','other') and row['nestedKindClass'] in ('prepare','protection','lookup','snapshot','cancel','header-policy','timezone-read','other','none') and all(type(row[k]) is bool for k in ('portCurrent','hasKind','hasMessage','hasData')),'port entry fields differ')
    return value


def native_debug(value,binding):
    """Independent whitelist; a diagnostic cannot export arbitrary app text."""
    required={'schema','diagnosticOnly','releaseAcceptance','sourceCommit','sourceTree','runNonce',
        'integrationApkSha256','sdkRunId','sdkRunAttempt','snapshots','actualPublicIpGeolocationVerified','scope'}
    require(type(value) is dict and required<=set(value)<=required|{'extensionDiagnostic'} and type(value['schema']) is int and value['schema']==1
        and value['diagnosticOnly'] is True and value['releaseAcceptance'] is False
        and value['actualPublicIpGeolocationVerified'] is False,'diagnostic envelope differs')
    for key,expected in binding.items():require(_typed_equal(value.get(key),expected),'native diagnostic binding differs')
    if 'extensionDiagnostic' in value:extension_debug(value['extensionDiagnostic'],binding['runNonce'])
    fields={
        'timeZonePolicy':{'schema','desiredMode','desiredRevision','state','effectiveMode','rfpPriority','ipMatched','nativeSettingReadback','issue'},
        'defaultNetwork':{'known','internet','vpn','revision','identityPresent'},
        'view':{'ready','failed','destroyed','privacyReady','addonDisabled','requestHeadersInstalled','routePortPresent','nativeProtectionConfirmed','protectionLevel','currentSessionPresent','currentSessionOpen','currentSessionId','currentPagePortPresent','hasVisibleDocument','ipRouteNeedsReload','routeStamp','guardBlocked','generalRouteReady'},
        'linkWatch':{'networkPresent','linksPresent','serial'},
        'routeLeases':{'surfaces','downloads','changes','revision'},
        'gate':{'present','epoch','documentSerial','preparing','ready','revalidating','waiting','proofWaiting','networkWaiting','routeLeasePresent'},
        'lookup':{'present','sent','id','currentSession','currentGate','currentPort','currentRuntime','requestToken','routeStamp','remainingMs','leasePresent','leaseClosed','documentSerial','connectionEpoch','desiredRevision'},
        'operation':{'present','started','retired','finished','ready','verified','unsupported','rfpManaged'},
        'routingCounters':{'bootstrapGeoAllowed','bootstrapGeoDenied','bootstrapOtherAllowed','bootstrapOtherDenied','protectedGeoBlocked','protectedGeoFixedSocks','protectedGeoFixedHttp','protectedGeoFixedHttps','protectedGeoOther','ordinaryGeoBlocked','ordinaryGeoOther','bootstrapGeoVariantAllowed','bootstrapGeoVariantDenied','protectedGeoVariant','ordinaryGeoVariant','capped'},
    }
    base={'elapsedRealtime','stage','terminal','sessionPresent','viewPresent'}
    optional={'networkReady','connecting','navigating','navigationFailed','navigationEpoch','connectionEpoch','ownerDeleted'}|set(fields)
    def scalar(v):
        require(v is None or type(v) in (str,int,bool),'diagnostic primitive differs')
        if type(v) is str:require(len(v)<=512 and '\n' not in v and '\r' not in v and '\x00' not in v and '://' not in v and 'PRIVATE KEY' not in v and not v.startswith('/'),'unsafe diagnostic text')
        if type(v) is int:require(-120000<=v<=2**63-1,'diagnostic number exceeds bound')
    strings={'stage','schemaMode','desiredMode','state','effectiveMode','issue','currentSessionId','routeStamp','epoch','requestToken'}
    numbers={'schema','elapsedRealtime','desiredRevision','navigationEpoch','connectionEpoch','revision','protectionLevel','serial','surfaces','downloads','changes','documentSerial','waiting','proofWaiting','networkWaiting','id','remainingMs',*fields['routingCounters']-{'capped'}}
    def leaf(key,item):
        scalar(item)
        if key in strings:require(type(item) is str or key=='desiredMode' and item is None,'typed diagnostic string required')
        elif key in numbers:require(type(item) is int,'typed diagnostic integer required')
        else:require(type(item) is bool,'typed diagnostic flag required')
    scalar(value['scope']);require(type(value['scope']) is str,'bounded diagnostic scope required')
    require(type(value['snapshots']) is list and len(value['snapshots'])<=16,'bounded diagnostic snapshots required')
    for row in value['snapshots']:
        require(type(row) is dict and base<=set(row)<=base|optional,'diagnostic snapshot keys differ')
        for key,v in row.items():
            if key in fields:
                require(type(v) is dict and set(v)<=fields[key],'diagnostic native state keys differ')
                for field,item in v.items():leaf(field,item)
            else:leaf(key,v)
    return value


CONSOLE_PREFIX='POCKET_IP_TZ_DIAG4 '
def console_debug(raw,process_raw,binding,native_process,native_children=()):
    require(type(raw) is bytes and len(raw)<=4*1024*1024 and type(process_raw) is bytes and len(process_raw)<=262144,'bounded console/process data required')
    processes=[]
    for line in process_raw.decode('utf-8','strict').splitlines():
        fields=line.split()
        if len(fields)!=3 or not fields[0].isdigit() or not fields[1].isdigit():continue
        pid,uid=int(fields[0]),int(fields[1]);name=fields[2]
        role='profile6' if name=='local.pocketchat.test:profile6' else 'gecko-env6' if re.fullmatch(r'local\.pocketchat\.test:gecko_env6_[A-Za-z0-9_]+',name) else None
        if role and 1<pid<2**31 and 10000<=uid<200000:processes.append(dict(pid=pid,uid=uid,role=role))
    require(len(processes)<=64 and len({p['pid'] for p in processes})==len(processes),'process binding bound differs')
    owners=[p for p in processes if p['role']=='profile6'];require(len(owners)==1,'one actual canonical process required')
    owner=owners[0];require(type(native_process) is dict and owner['pid']==native_process.get('processPid') and owner['uid']==native_process.get('processUid'),'console PID differs from installed native report');unverified=sum(1 for p in processes if p['uid']!=owner['uid'] and p not in native_children);processes=[p for p in processes if p['uid']==owner['uid'] or 99000<=p['uid']<=99999 and p in native_children];pids={p['pid'] for p in processes}
    accepted=[];dropped=0
    pattern=re.compile(r'^\d\d-\d\d\s+\d\d:\d\d:\d\d\.\d+\s+(\d+)\s+(\d+)\s+[VDIWEF]\s+[^:]+:\s*(.*)$')
    for line in raw.decode('utf-8','strict').splitlines():
        if CONSOLE_PREFIX not in line:continue
        try:
            match=pattern.fullmatch(line);require(match is not None and int(match[1]) in pids,'console owner differs')
            message=match[3];index=message.index(CONSOLE_PREFIX);value=strict_json(message[index+len(CONSOLE_PREFIX):])
            require({'schema','diagnosticOnly','releaseAcceptance','event'}<=set(value)<={'schema','diagnosticOnly','releaseAcceptance','event','runtimeManifest','helperPresence'} and type(value['schema']) is int and value['schema']==1 and value['diagnosticOnly'] is True and value['releaseAcceptance'] is False,'console diagnostic scope differs')
            event=value['event'];require(type(event) is dict and type(event.get('sequence')) is int and 1<=event['sequence']<=32,'console event sequence differs')
            row=dict(event,sequence=1)
            latest=dict(schema=1,diagnosticOnly=True,releaseAcceptance=False,requestNonce=binding['runNonce'],runtimeManifest=dict(available=False,version='unavailable',id='unavailable',scriptCount=-1,scripts=[]),helperPresence=dict(bootstrap='undefined',headers='undefined',identity='undefined',timezone='undefined'),events=[row],omitted=0,invalid=0,bootstrapObject=False,bootstrapCreate=False,headersObject=False)
            if 'runtimeManifest' in value:latest['runtimeManifest']=value['runtimeManifest']
            if 'helperPresence' in value:latest['helperPresence']=value['helperPresence']
            extension_debug(dict(registered=False,accepted=0,rejected=0,latest=latest),binding['runNonce'])
            record=dict(pid=int(match[1]),tid=int(match[2]),event=event,runtimeManifest=latest['runtimeManifest'],helperPresence=latest['helperPresence'])
            if record in accepted:continue
            require(len(accepted)<32,'console row bound differs');accepted.append(record)
        except (ValueError,TypeError,KeyError,UnicodeError):dropped=min(10000,dropped+1)
    return dict(schema=1,binding=binding,diagnosticOnly=True,releaseAcceptance=False,actualPublicIpGeolocationVerified=False,processes=processes,unverifiedProcessCount=unverified,isolatedChildRequiresNativeActivityManagerPackageProof=True,events=accepted,rejectedOrOmitted=dropped,wholeLogcatExported=False,scope='Only fixed-prefix typed enum JSON from actual canonical profile6 or its named SDK env6 process PIDs. All other logcat content is omitted; diagnostic timing and console output do not establish a production fix.')


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
    certificates=server=ca=activity=None;error=None;mappings=[];scope_prepared=False;host_tls={};system={};device_raw_sha=None
    cleanup=dict(appStopped=False,scopeCleared=False,reverseRemoved=False,caRemoved=False,privateMaterialRemoved=False,serverQuiesced=False)
    report=dict(schema=1,fixtureType=FIXTURE_TYPE,status='running',sourceCommit=source,sourceTree=tree,runNonce=nonce,expectedBuildIdentity=identity,
        actualAndroidExecution=False,actualGeckoExecution=False,syntheticGeoService=True,actualPublicIpGeolocationVerified=False,
        workerCoverageVerified=False,serviceWorkerCoverageVerified=False,fingerprintProtectionVerified=False)
    try:
        require(adb('shell','getprop','ro.kernel.qemu').stdout.decode().strip()=='1','actual controlled Android emulator required')
        require(adb('shell','id','-u').stdout.decode().strip()=='2000','source-bound evidence requires shell UID2000')
        system['before']=adb('shell','getprop','persist.sys.timezone').stdout.decode('ascii').strip();expected_clock(system['before'])
        certificates=IpFixtureCertificates()
        gecko=(ROOT/'tests/gecko/assets/gecko-environment-policy-page.js').read_text()+'\n'+(ROOT/'tests/gecko/assets/gecko-ip-timezone-page.js').read_text()
        server=IpTimeZoneFleet(certificates,(ROOT/'tests/gecko/assets/worker-policy-page.js').read_text(),gecko,binding).start()
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
        setup=strict_json(adb('exec-out','content','read','--uri',URI+'/setup').stdout)
        require(setup.get('status')=='armed' and setup.get('sourceCommit')==source and setup.get('sourceTree')==tree and setup.get('runNonce')==nonce and setup.get('integrationApkSha256')==identity['apkSha256'] and setup.get('timezoneSealedRecordMissing') is True and setup.get('actualDefaultStoreLoadYet') is False and setup.get('manualSeedAppliedToIpScope') is False,'actual unused-scope provider proof differs')
        adb(*activity_args(source,nonce,certificates.leaf_sha))
        deadline=time.monotonic()+960
        while time.monotonic()<deadline:
            raw=adb('exec-out','content','read','--uri',URI+'/report',check=False,timeout=20).stdout
            current=read_activity(raw,source,nonce,identity)
            if current is not None:
                activity=current;device_raw_sha=hashlib.sha256(raw).hexdigest()
                if current.get('status') in ('passed','failed'):break
            time.sleep(.25)
        require(activity is not None and activity.get('status')=='passed','actual IP fixture failed or timed out')
        system['after']=adb('shell','getprop','persist.sys.timezone').stdout.decode('ascii').strip()
        require(system['before']==system['after'],'Android system timezone changed')
        report.update(status='passed',actualAndroidExecution=True,actualGeckoExecution=True)
    except Exception as failure:
        error=failure;report.update(status='failed',errorType=type(failure).__name__)
    finally:
        # Additive debug only. A missing/rejected diagnostic does not grant or
        # revoke acceptance; the original report/checker remains authoritative.
        debug=dict(schema=1,binding=binding,diagnosticOnly=True,releaseAcceptance=False,
                   actualPublicIpGeolocationVerified=False,deviceDebugAvailable=False)
        try:
            raw_debug=adb('exec-out','content','read','--uri',URI+'/transport-debug',check=False,timeout=15).stdout
            require(0<len(raw_debug)<=65536,'bounded native debug unavailable')
            device_debug=native_debug(strict_json(raw_debug),binding)
            require(device_debug.get('sourceCommit')==source and device_debug.get('sourceTree')==tree
                and device_debug.get('runNonce')==nonce and device_debug.get('integrationApkSha256')==identity['apkSha256']
                and device_debug.get('sdkRunId')==sdk['runId'] and device_debug.get('sdkRunAttempt')==sdk['runAttempt'],
                'native diagnostic source/APK/run differs')
            debug.update(deviceDebugAvailable=True,device=device_debug)
        except Exception as diagnostic_error:debug['deviceCollectionErrorType']=type(diagnostic_error).__name__
        try:
            process_rows=adb('shell','ps -A -o PID,UID,NAME',check=False,timeout=10).stdout
            console_rows=adb('shell',"logcat -d -t 2048 -v threadtime GeckoConsole:V Gecko:V '*:S' | grep -F 'POCKET_IP_TZ_DIAG4 '",check=False,timeout=10).stdout
            debug['console']=console_debug(console_rows,process_rows,binding,device_debug['extensionDiagnostic']['poll'],device_debug['extensionDiagnostic'].get('processes',[]))
        except Exception as diagnostic_error:debug['consoleCollectionErrorType']=type(diagnostic_error).__name__
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
        try:debug['transport']=server.diagnostics_snapshot() if server is not None else {}
        except Exception as diagnostic_error:debug['transportCollectionErrorType']=type(diagnostic_error).__name__
        try:write_json(args.output/'ip-timezone-transport-debug.json',debug)
        except Exception:pass  # Never replace the original failed device result.
        if not unchanged:error=error or ValueError('Source changed');report.update(status='failed',errorType='SourceChanged')
        report.update(activity=activity or {},hostTls=host_tls,routeReceipts=route_receipts,systemTimeZone=system,sourceFiles=hashes,
            executionInputsUnchanged=unchanged,cleanup=cleanup,deviceReportReceivedSha256=device_raw_sha,
            rawExtractionScope='Each case is a typed JSON extraction from one original device report; route-receipts is the quiescent host snapshot. File SHA pins bind these exact exported bytes, not the whole device report byte layout.',
            scope='Real canonical MainActivity profile6/default native store and proxy-bound HTTPS IP timezone; synthetic geolocation data only, no actual public IP accuracy or whole Worker coverage claim.')
        values=(activity or {}).get('cases',{});pins={}
        for name in RAW_FILES:
            case=name[:-5];evidence=route_receipts if case=='route-receipts' else (activity or {}).get('setup',{}) if case=='setup-scope' else values.get(case,{})
            pins[name]=write_json(rawdir/name,dict(schema=1,case=case,binding=binding,evidence=evidence))
        report['casePins']=pins;write_json(args.output/REPORT_NAME,report)
        if error is None:
            try:verify_gecko_ip_timezone_evidence(args.output,source,identity)
            except Exception as rejected:
                # Preserve the original report bytes and fail the command. A
                # checker rejection must not silently rewrite a device outcome.
                error=rejected
    print(json.dumps(dict(status='passed' if error is None else 'failed',sourceCommit=source,runNonce=nonce,
        stage=(activity or {}).get('failedAtStage') or (activity or {}).get('stage','unavailable'),
        errorType=type(error).__name__ if error is not None else None,
        actualAndroidExecution=report['actualAndroidExecution'],actualGeckoExecution=report['actualGeckoExecution'],
        syntheticGeoService=True,actualPublicIpGeolocationVerified=False),separators=(',',':')))
    if error is not None:raise SystemExit(1)
if __name__=='__main__':main()
