#!/usr/bin/env python3
"""Diagnostic-only real Gecko native timezone/worker observations; no input replay."""
import argparse
import datetime
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import time
import uuid

from profile_invocation_contract import expected_build,verify_installed

ROOT=Path(__file__).resolve().parents[2]
PACKAGE='local.pocketchat.test'
PROCESS=PACKAGE+':native_timezone_probe'
COMPONENT=PACKAGE+'/local.pocketchat.NativeTimezoneProbeActivity'
ROLES=('page','dedicated','blob','shared','service')
ZONES={
    'UTC':(0,0,12,0,12,0,('UTC','Etc/UTC','Etc/GMT','GMT')),
    'America/New_York':(300,240,7,0,8,0,('America/New_York',)),
    'Asia/Kathmandu':(-345,-345,17,45,17,45,('Asia/Kathmandu','Asia/Katmandu')),
}
JAN=int(datetime.datetime(2026,1,15,12,tzinfo=datetime.timezone.utc).timestamp()*1000)
JULY=int(datetime.datetime(2026,7,15,12,tzinfo=datetime.timezone.utc).timestamp()*1000)

def require(value,message):
    if not value:raise ValueError(message)

def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

def strict_json(raw):
    require(type(raw) is bytes and len(raw)<=131072,'Bounded native report required')
    def pairs(rows):
        value={}
        for key,item in rows:
            require(key not in value,'Duplicate native field');value[key]=item
        return value
    value=json.loads(raw.decode('utf-8'),object_pairs_hook=pairs,
        parse_constant=lambda _:(_ for _ in ()).throw(ValueError('Nonfinite native value')))
    require(type(value) is dict,'Native report object required')
    return value

def observation(value,role,zone,nonce,source):
    require(type(value) is dict and set(value)=={'schema','nonce','sourceCommit','role','status','observation','error'},'Observation schema differs')
    require(type(value['schema']) is int and value['schema']==1 and value['nonce']==nonce
            and value['sourceCommit']==source and value['role']==role,'Observation binding differs')
    status=value['status']
    require(status in ('observed','unsupported','failed'),'Unknown observation status')
    if status!='observed':
        require(value['observation'] is None and type(value['error']) is str
                and re.fullmatch('[A-Za-z][A-Za-z0-9_-]{0,79}',value['error']) is not None,'Invalid failure metadata')
        return dict(role=role,status=status,actualExecution=False,timezoneMatchesRequested=False,error=value['error'])
    row=value['observation']
    fields=('janOffsetMinutes','julyOffsetMinutes','janHour','janMinute','julyHour','julyMinute','janEpochMillis','julyEpochMillis')
    require(type(row) is dict and set(row)=={'timeZone',*fields} and value['error'] is None,'Native Date observation shape differs')
    require(type(row['timeZone']) is str and re.fullmatch('[A-Za-z0-9_+./-]{1,80}',row['timeZone']) is not None
            and all(type(row[name]) is int for name in fields),'Native Date observation types differ')
    require(row['janEpochMillis']==JAN and row['julyEpochMillis']==JULY,'Controlled fixed UTC instants differ')
    require(all(-1440<=row[name]<=1440 for name in ('janOffsetMinutes','julyOffsetMinutes'))
            and all(0<=row[name]<24 for name in ('janHour','julyHour'))
            and all(0<=row[name]<60 for name in ('janMinute','julyMinute')),'Invalid observed offsets or local fields')
    expected=ZONES[zone]
    matches=(tuple(row[name] for name in fields[:6])==expected[:6] and row['timeZone'] in expected[6])
    return dict(role=role,status=status,actualExecution=True,timezoneMatchesRequested=matches,
                nativeDateObservation=dict(row))

def validate_case(report,*,zone,nonce,source,tree,identity):
    require(report.get('schema')==1 and type(report.get('schema')) is int
            and report.get('status')=='observed' and report.get('stage')=='complete' and report.get('failure')=='','Actual completed native observation required')
    require(report.get('runNonce')==nonce and report.get('requestedZoneId')==zone
            and report.get('sourceCommit')==source and report.get('sourceTree')==tree,'Native case source/nonce/zone differs')
    require(report.get('diagnosticOnly') is True and report.get('releaseAcceptance') is False
            and report.get('actualAndroidExecution') is True and report.get('actualGeckoExecution') is True,'Actual diagnostic Gecko execution required')
    verify_installed(report.get('buildIdentity'),identity)
    for name in ('javaTimezoneOverrideUsed','processTimezoneEnvironmentChangedByProbe','debuggingEndpointUsed',
                 'dateOrIntlOverrideUsed','workerCoverageVerified','serviceWorkerCoverageVerified','fingerprintProtectionVerified'):
        require(report.get(name) is False,'Probe must preserve unsupported/global scope: '+name)
    process=report.get('process')
    require(type(process) is dict and type(process.get('pid')) is int and process['pid']>0
            and type(process.get('uid')) is int and 10000<=process['uid']<100000,'Actual process identity required')
    for before,after in (('javaTimezoneBefore','javaTimezoneAfter'),('icuTimezoneBefore','icuTimezoneAfter'),
                         ('tzEnvironmentBefore','tzEnvironmentAfter')):
        require(process.get(before)==process.get(after),'Process timezone baseline changed')
    applied=report.get('nativeApply');read=report.get('nativeRead')
    require(type(applied) is dict and type(read) is dict,'Native setting/readback missing')
    for packet,status,suffix in ((applied,'applied','-apply'),(read,'read','-read')):
        require(type(packet.get('schema')) is int and packet['schema']==1 and packet.get('kind')=='timezoneProbeResult'
                and packet.get('requestToken')==nonce+suffix and packet.get('status')==status
                and packet.get('nativeZoneId')==zone and packet.get('nativeSettingReadback') is True
                and packet.get('scope')=='top-browsing-context' and packet.get('workerCoverageVerified') is False
                and packet.get('serviceWorkerCoverageVerified') is False
                and type(packet.get('contextId')) is str and re.fullmatch('[1-9][0-9]{0,23}',packet['contextId']) is not None,'Native receipt binding differs')
    require(applied.get('requestedZoneId')==zone and applied['contextId']==read['contextId'],'Same-origin context binding differs')
    rows=report.get('observations')
    require(type(rows) is list and len(rows)==len(ROLES),'Every context must report an actual outcome')
    by_role={}
    for row in rows:
        require(type(row) is dict and row.get('role') in ROLES and row['role'] not in by_role,'Duplicate/unknown context')
        by_role[row['role']]=row
    require(set(by_role)==set(ROLES),'Context set differs')
    findings=[observation(by_role[role],role,zone,nonce,source) for role in ROLES]
    require(findings[0]['actualExecution'],'Actual main-document Date/Intl observation missing')
    return dict(zone=zone,nativeContextId=applied['contextId'],pageTimezoneVerified=findings[0]['timezoneMatchesRequested'],
                contexts=findings,workerCoverageVerified=False,serviceWorkerCoverageVerified=False,
                fingerprintProtectionVerified=False)

def snapshot():
    names=subprocess.check_output(['git','ls-files','--cached','--others','--exclude-standard',
        'app','tests','tools','.github/workflows/native-timezone-probe.yml'],cwd=ROOT,text=True).splitlines()
    return {name:sha(ROOT/name) for name in sorted(set(names)) if (ROOT/name).is_file()}

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--adb',default='adb');parser.add_argument('--serial',default='emulator-5554')
    parser.add_argument('--apk',type=Path,default=ROOT/'app/build/outputs/apk/integration/app-x86_64-integration.apk')
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    require(args.serial=='emulator-5554','Controlled emulator target required')
    output=args.output.absolute();require(not output.exists() and all(not p.is_symlink() for p in (output,*output.parents)),'Fresh ordinary report directory required')
    output.mkdir(parents=True);before=snapshot()
    source=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip()
    tree=subprocess.check_output(['git','rev-parse','HEAD^{tree}'],cwd=ROOT,text=True).strip()
    require(not subprocess.check_output(['git','status','--porcelain'],cwd=ROOT,text=True).strip(),'Clean selected diagnostic source required')
    settings=(ROOT/'app/build.gradle').read_text()
    identity=expected_build(args.apk,source,tree,re.search(r"versionName '([^']+)'",settings)[1],int(re.search(r'versionCode ([0-9]+)',settings)[1]))
    def adb(*parts,check=True,timeout=20):
        return subprocess.run([args.adb,'-s',args.serial,*parts],capture_output=True,check=check,timeout=timeout)
    def system_state():
        zone=adb('shell','getprop','persist.sys.timezone').stdout.decode('utf-8').strip()
        auto=adb('shell','settings','get','global','auto_time_zone').stdout.decode('ascii').strip()
        require(len(zone)<=100 and auto in ('0','1','null'),'Invalid system timezone metadata')
        return dict(timezoneProperty=zone,automaticTimezone=auto)
    records=[];findings=[];errors=[];system_before=None;system_after=None
    try:
        require(adb('shell','getprop','ro.kernel.qemu').stdout.strip()==b'1','Actual emulator required')
        require(adb('shell','getprop','ro.build.version.sdk').stdout.strip()==b'35','Selected actual API35 runtime required')
        require(adb('shell','id','-u').stdout.strip()==b'2000','Evidence must be read as shell UID2000')
        verify_installed(strict_json(adb('exec-out','content','read','--uri','content://'+PACKAGE+'.evidence/build-identity').stdout),identity)
        system_before=system_state()
        for zone in ZONES:
            nonce=uuid.uuid4().hex;stage='fresh-process';entry=dict(zone=zone,runNonce=nonce,status='failed')
            try:
                adb('shell','am','force-stop',PACKAGE)
                require(not adb('shell','pidof',PROCESS,check=False).stdout.strip(),'Prior probe process remained alive')
                stage='launch'
                adb('shell','am','start','-W','-n',COMPONENT,'--es','runNonce',nonce,
                    '--es','sourceCommit',source,'--es','zoneId',zone)
                stage='observe';deadline=time.monotonic()+150;report=None
                while time.monotonic()<deadline:
                    response=adb('exec-out','content','read','--uri','content://'+PACKAGE+'.native-timezone-evidence/report/'+nonce,check=False)
                    try:value=strict_json(response.stdout)
                    except (ValueError,UnicodeError):time.sleep(.25);continue
                    if value.get('runNonce')!=nonce:time.sleep(.25);continue
                    require(value.get('sourceCommit')==source and value.get('sourceTree')==tree,'Stale source report')
                    if value.get('status') in ('observed','failed'):report=value;break
                    time.sleep(.25)
                require(report is not None,'Diagnostic did not terminate')
                raw=(json.dumps(report,ensure_ascii=True,indent=2)+'\n').encode()
                path=output/('case-'+str(len(records))+'.json');path.write_bytes(raw)
                entry.update(report=path.name,reportSha256=hashlib.sha256(raw).hexdigest())
                current=validate_case(report,zone=zone,nonce=nonce,source=source,tree=tree,identity=identity)
                pid=adb('shell','pidof',PROCESS).stdout.decode('ascii').strip()
                require(pid==str(report['process']['pid']),'Observed process owner differs')
                current['systemTimezoneUnchanged']=system_state()==system_before
                require(current['systemTimezoneUnchanged'],'Android system timezone changed')
                entry.update(status='observed',finding=current);findings.append(current)
            except Exception as error:
                entry.update(errorType=type(error).__name__,failureStage=stage);errors.append(dict(zone=zone,errorType=type(error).__name__,stage=stage))
            finally:
                try:adb('shell','am','force-stop',PACKAGE)
                except Exception:pass
                records.append(entry)
        system_after=system_state()
    except Exception as error:errors.append(dict(stage='device-preflight-or-final-state',errorType=type(error).__name__))
    stable=snapshot()==before
    completed=len(records)==3 and all(row['status']=='observed' for row in records)
    page_verified=completed and all(row['pageTimezoneVerified'] for row in findings)
    passed=completed and page_verified and system_before is not None and system_before==system_after and stable and not errors
    result=dict(schema=1,status='observed' if passed else 'failed',diagnosticOnly=True,releaseAcceptance=False,
        sourceCommit=source,sourceTree=tree,runId=os.environ.get('GITHUB_RUN_ID'),runAttempt=os.environ.get('GITHUB_RUN_ATTEMPT'),
        expectedBuildIdentity=identity,actualAndroidExecution=bool(records),actualGeckoExecution=bool(findings),
        nativePageTimezoneVerified=bool(page_verified),workerCoverageVerified=False,serviceWorkerCoverageVerified=False,
        fingerprintProtectionVerified=False,caseRecords=records,errors=errors,systemBefore=system_before,systemAfter=system_after,
        systemTimezoneUnchanged=system_before is not None and system_before==system_after,
        sourceFiles=before,executionInputsUnchanged=stable,debuggingEndpointUsed=False,systemTimezoneModifiedByProbe=False,
        scope='Diagnostic-only actual Gecko BrowsingContext timezone setter/readback plus unchanged native Date/Intl at fixed January/July UTC instants. All worker outcomes, including unsupported, failures and mismatches, remain explicit. Native setter acknowledgement is not worker or production protection acceptance.')
    (output/'results.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps({name:result[name] for name in ('status','diagnosticOnly','releaseAcceptance','sourceCommit','nativePageTimezoneVerified','systemTimezoneUnchanged','executionInputsUnchanged')}))
    return 0 if passed else 1

if __name__=='__main__':
    raise SystemExit(main())
