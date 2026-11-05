#!/usr/bin/env python3
"""Replay all original production CPU packets using the selected-source validator."""
import argparse
import ast
import hashlib
from pathlib import Path,PurePosixPath
import re
import sys

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'tools'));sys.path.insert(0,str(ROOT/'tools/gecko'))
from gecko.profile_invocation_contract import verify_installed
from gecko.sdk_identity_contract import source_bytes,_typed_equal,SDK_FIELDS
from cpu_acceptance_server import strict_json,ROLES

REPORT_NAME='gecko-cpu-results.json'
CASE_SPECS=(('cap1',1,'1',False,False,False,False),('cap2',1,'2',False,False,False,False),
    ('automatic-stale-user',1,'automatic',False,False,True,False),('rfp',1,'1',True,False,False,False),
    ('persistent-before',1,'2',False,False,False,False),('persistent-after',1,'2',False,True,False,False),
    ('concurrent-cap1',1,'1',False,False,False,False),('concurrent-cap2',2,'2',False,False,False,False),
    ('concurrent-cap1-resample',1,'1',False,False,False,False),('normal-template-rfp',1,'1',True,False,False,True))
SOURCE_INPUTS={'tools/browser/check_gecko_cpu_evidence.py','tools/browser/run_gecko_cpu_integration.py',
    'tools/gecko/run_gecko_cpu_acceptance.py','tools/gecko/cpu_acceptance_server.py','tools/gecko/profile_invocation_contract.py',
    'tools/gecko/sdk_identity_contract.py','tools/browser/fingerprint_fixture_server.py','tests/gecko/GeckoCpuAcceptanceActivity.java',
    'tests/gecko/GeckoCpuAcceptanceProvider.java','tests/gecko/BrowserFingerprintIntegrationActivity.java','tests/gecko/BrowserFingerprintFixture.java',
    'tests/gecko/IntegrationBuildIdentity.java','tests/gecko/AndroidManifest.xml','tests/gecko/assets/cpu-acceptance-page.js',
    'tests/gecko/assets/cpu-acceptance-worker.js','app/build.gradle','app/src/main/AndroidManifest.xml','app/src/main/res/xml/network_security.xml',
    'tests/gecko/res/xml/network_security.xml','app/src/main/java/local/pocketchat/ChatSession.java','app/src/main/java/local/pocketchat/GeckoWebView.java',
    'app/src/main/java/local/pocketchat/GeckoCpuController.java','app/src/main/java/local/pocketchat/GeckoCpuNative.java',
    'app/src/main/java/local/pocketchat/GeckoCpuProfile.java','app/src/main/java/local/pocketchat/GeckoCpuStore.java',
    'app/src/main/java/local/pocketchat/Profiles.java','app/src/main/java/local/pocketchat/ProfileContext.java','app/src/main/java/local/pocketchat/GeckoCpuSpec.java','app/src/main/java/local/pocketchat/IdentityTemplateController.java',
    'app/src/main/java/local/pocketchat/NormalCaretSdkReceipt.java','.github/workflows/gecko-cpu-acceptance.yml',
    '.github/workflows/browser-2_1-acceptance.yml','.github/workflows/publish-gecko-release.yml'}


def require(value,message):
    if not value:raise ValueError('Gecko CPU acceptance: '+message)


def sha(value):return type(value) is str and re.fullmatch('[0-9a-f]{64}',value) is not None


def source_hashes(report,source,reader):
    hashes=report.get('sourceFiles');require(type(hashes) is dict and SOURCE_INPUTS<=set(hashes) and len(hashes)<=10000,'Required source inputs missing')
    for path,digest in hashes.items():
        require(type(path) is str and path and str(PurePosixPath(path))==path and not PurePosixPath(path).is_absolute()
            and '..' not in PurePosixPath(path).parts and '\\' not in path and '\0' not in path and sha(digest),'Unsafe source pin')
        require(hashlib.sha256(reader(source,path)).hexdigest()==digest,'Selected source differs: '+path)


def selected_validator(source,reader):
    path='tools/gecko/run_gecko_cpu_acceptance.py';raw=reader(source,path)
    require(type(raw) is bytes and 0<len(raw)<=131072,'Bounded selected CPU validator source required')
    parsed=ast.parse(raw,filename=path);names=('typed_equal','validate_report')
    functions=[node for node in parsed.body if isinstance(node,ast.FunctionDef) and node.name in names]
    require(len(functions)==2 and {node.name for node in functions}==set(names),'Unique selected CPU validator functions required')
    packages=[node.value.value for node in parsed.body if isinstance(node,ast.Assign)
        and any(isinstance(target,ast.Name) and target.id=='PACKAGE' for target in node.targets)
        and isinstance(node.value,ast.Constant)]
    require(packages==['local.pocketchat.test'],'Exact selected integration package required')
    namespace=dict(re=re,require=require,verify_installed=verify_installed,ROLES=ROLES,PACKAGE=packages[0])
    exec(compile(ast.Module(body=functions,type_ignores=[]),path,'exec'),namespace)
    return namespace['validate_report']


def identity(actual,expected):
    require(type(actual) is dict and type(expected) is dict,'Actual installed identity required')
    for key in ('schema','package','sourceCommit','sourceTree','dirtySource','version','versionCode','sdkCoordinate','apkSha256','apkBytes','buildStampSha256','sdkBuildIdentity')+SDK_FIELDS:
        require(_typed_equal(actual.get(key),expected.get(key)),'Typed installed SDK/APK identity differs: '+key)
    verify_installed(actual,expected)


def trust(report,expected):
    host=report.get('hostTls');require(type(host) is dict,'Actual host TLS trust required')
    require(all(host.get(k) is True for k in ('ephemeral','opensslChainVerified','privateMaterialRemoved','reverseRemoved'))
        and host.get('privateMaterialLocation')=='host-tmp-only' and host.get('privateMaterialExported') is False
        and host.get('certificateExceptionUsed') is False and host.get('hostnameVerified')==['fp-a.pocketchat.test','fp-b.pocketchat.test']
        and type(host.get('guestPort')) is int and host['guestPort']==18766,'Ephemeral native-valid exact-origin trust/cleanup required')
    require(sha(host.get('caPemSha256')) and sha(host.get('leafDerSha256')),'Public trust hashes required')
    sdk=expected['sdkBuildIdentity'];binding=dict(sourceCommit=report['sourceCommit'],sourceTree=report['sourceTree'],runNonce=report['runNonce'],
        integrationApkSha256=expected['apkSha256'],sdkRunId=sdk['runId'],sdkRunAttempt=sdk['runAttempt'])
    require(_typed_equal(host.get('binding'),binding),'Host source/APK/SDK/run/nonce differs')
    installation=host.get('trustInstallation');subject=host.get('subjectHashOld')
    require(type(installation) is dict and type(subject) is str and re.fullmatch('[0-9a-f]{8}',subject),'Actual public CA installation required')
    require(installation.get('method')=='domain-scoped-user-ca' and type(installation.get('androidUser')) is int and installation['androidUser']==0,'Domain-scoped Android user CA required')
    for field in ('adbRoot','selinuxEnforcing','installedPublicCaBytesMatch','appForceStoppedAfterInstall','removedAfterExecution','shellRestoredAfterInstall','shellRestoredAfterCleanup'):
        require(installation.get(field) is True,'Actual CA lifecycle missing: '+field)
    for field,value in (('evidenceShellUid',2000),('cleanupRootUid',0),('cleanupShellUid',2000)):
        require(type(installation.get(field)) is int and installation[field]==value,'CA root/shell evidence UID differs')
    require(installation.get('ownerAndMode')=='644:1000:1000' and type(installation.get('selinuxContext')) is str
        and re.fullmatch('u:object_r:(?!unlabeled)[a-zA-Z0-9_]+:s0',installation['selinuxContext']),'CA ownership/SELinux differs')
    require(installation.get('subjectHashOld')==subject and installation.get('storePath')=='/data/misc/user/0/cacerts-added/'+subject+'.0'
        and installation.get('publicCaPemSha256')==host['caPemSha256'] and installation.get('expectedLeafDerSha256')==host['leafDerSha256'],'Actual public CA/leaf binding differs')
    require(type(report.get('cleanup')) is dict and all(report['cleanup'].get(k) is True for k in ('appStopped','reverseRemoved','caRemoved','privateMaterialRemoved')),'Controlled app/transport/trust cleanup missing')
    return host


def verify_gecko_cpu_evidence(directory,source,expected,reader=source_bytes):
    directory=Path(directory);normalized=directory/REPORT_NAME
    path=normalized if normalized.exists() else directory/'results.json';raw_directory=directory/'gecko-cpu-evidence' if normalized.exists() else directory
    require(path.is_file() and not path.is_symlink() and path.stat().st_size<=4*1024*1024,'Original bounded CPU summary required')
    raw=path.read_bytes();report=strict_json(raw,4*1024*1024)
    require(type(report.get('schema')) is int and report['schema']==1 and report.get('status')=='passed' and report.get('sourceCommit')==source
        and expected.get('sourceCommit')==source and report.get('sourceTree')==expected.get('sourceTree')
        and type(report.get('runNonce')) is str and re.fullmatch('[0-9a-f]{32}',report['runNonce']),'Completed selected-source CPU summary required')
    require(report.get('executionInputsUnchanged') is True and report.get('errors')==[],'CPU input changes or execution errors remain')
    for field in ('diagnosticOnly','actualAndroidExecution','actualGeckoExecution','productionColdCpuWorkloadPassed'):require(report.get(field) is True,'Actual CPU execution scope missing')
    for field in ('releaseAcceptance','debuggingEndpointUsed','navigatorGetterOverrideUsed','workerCoverageVerified','fingerprintProtectionVerified'):require(report.get(field) is False,'CPU summary overclaims scope')
    identity(report.get('expectedBuildIdentity'),expected);sdk=expected['sdkBuildIdentity']
    require(str(report.get('runId'))==str(sdk['runId']) and str(report.get('runAttempt'))==str(sdk['runAttempt']),'Same SDK/APK/run/attempt required')
    source_hashes(report,source,reader);validate=selected_validator(source,reader);host=trust(report,expected)
    fixture=report.get('host');require(type(fixture) is dict and type(fixture.get('schema')) is int and fixture['schema']==1
        and type(fixture.get('upstreamConnections')) is int and fixture['upstreamConnections']==0 and fixture.get('forwardingImplemented') is False
        and fixture.get('certificateExceptionUsed') is False and fixture.get('trustMethod')=='domain-scoped-user-ca'
        and type(fixture.get('tlsConnections')) is int and fixture['tlsConnections']>0 and fixture.get('eventsTruncated') is False,'Actual bounded HTTPS no-forward host required')
    cases=fixture.get('cases');records=report.get('caseRecords');require(type(cases) is dict and len(cases)==10 and type(records) is list and len(records)==10,'All ten actual cases required')
    findings={};nonces=set();hashes={}
    for record,spec in zip(records,CASE_SPECS):
        label,slot,mode,rfp,retain,stale,template=spec
        require(type(record) is dict and record.get('label')==label and record.get('status')=='passed','Ordered successful case missing')
        nonce=record.get('caseNonce');require(type(nonce) is str and re.fullmatch('[0-9a-f]{32}',nonce) and nonce not in nonces,'Fresh unique case nonce required');nonces.add(nonce)
        name='case-'+label+'.json';require(record.get('report')==name and sha(record.get('reportSha256')),'Exact original case file/hash required')
        target=raw_directory/name;require(target.is_file() and not target.is_symlink() and target.stat().st_size<=262144,'Original bounded case bytes required')
        original=target.read_bytes();digest=hashlib.sha256(original).hexdigest();require(digest==record['reportSha256'],'Original case bytes changed');hashes[label]=digest
        value=strict_json(original);identity(value.get('buildIdentity'),expected)
        finding=validate(value,run=report['runNonce'],case=nonce,source=source,tree=report['sourceTree'],identity=expected,
            slot=slot,mode=mode,rfp=rfp,retain=retain,stale_user=stale,leaf=host['leafDerSha256'],template_apply=template)
        receipt=cases.get(nonce);require(type(receipt) is dict and _typed_equal(receipt.get('binding'),dict(runNonce=report['runNonce'],caseNonce=nonce,sourceCommit=source,slot=slot))
            and _typed_equal(receipt.get('observations'),value['observations']),'Original device observations differ from independent host POST receipts')
        findings[label]=finding
    a,b=findings['persistent-before'],findings['persistent-after']
    for key in ('environmentId','environmentGeneration','activeBootRevision'):require(_typed_equal(a[key],b[key]),'Cold recovery changed saved profile/boot revision')
    for key in ('processNonce','runtimeNonce','serviceBootNonce'):require(a[key]!=b[key],'Persistent SW cold restart was replaced by a retained live global')
    one,two=findings['concurrent-cap1'],findings['concurrent-cap2']
    for key in ('environmentId','processNonce','runtimeNonce'):require(one[key]!=two[key],'Concurrent environments share process/runtime/identity')
    require(one['process']['pid']!=two['process']['pid'],'Concurrent environments share actual PID')
    for label in ('concurrent-cap1-resample','normal-template-rfp'):
        actual=findings[label]
        for key in ('processNonce','runtimeNonce','environmentId','environmentGeneration','activeBootRevision','process'):
            require(_typed_equal(actual[key],one[key]),'Concurrent resample/template changed immutable CPU boot/process')
    checks=report.get('processChecks');require(type(checks) is list and len(checks)==4,'Independent concurrent PID samples required')
    for check,(stage,slot) in zip(checks,(('both-resident',1),('both-resident',2),('after-resample',1),('after-resample',2))):
        owner=findings['concurrent-cap'+str(slot)];record=records[6 if slot==1 else 7]
        require(type(check) is dict and set(check)=={'stage','slot','caseNonce','processName','expectedPid','observedPid','shellUid'}
            and _typed_equal(check,dict(stage=stage,slot=slot,caseNonce=record['caseNonce'],processName='local.pocketchat.test:profile'+str(slot),
                expectedPid=owner['process']['pid'],observedPid=str(owner['process']['pid']),shellUid=2000)),
            'Actual both-resident/resample process evidence differs')
    # Every independent cold start must own a distinct process/runtime nonce.
    require(len({findings[label]['processNonce'] for label,*_ in CASE_SPECS[:8]})==8,'A cold/concurrent case reused an earlier process')
    return dict(sourceCommit=source,sourceTree=report['sourceTree'],runNonce=report['runNonce'],integrationApkSha256=expected['apkSha256'],
        runId=sdk['runId'],runAttempt=sdk['runAttempt'],reportSha256=hashlib.sha256(raw).hexdigest(),caseCount=10,caseSha256=hashes,
        pageAndWorkerCounts={label:row['counts'] for label,row in findings.items()},rfpCapObeyed={label:row['capObeyed'] for label,row in findings.items() if row['rfpPriority']},
        actualAndroidExecution=True,actualGeckoExecution=True,productionColdCpuWorkloadPassed=True,workerCoverageVerified=False,
        serviceWorkerCoverageVerified=False,fingerprintProtectionVerified=False,scope='Replayed original source-bound production CPU cold/default/RFP first-inline five-context packets, same-profile persistent SW cold restart, concurrent environment resample and ordinary identity template reapplication.')


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--directory',type=Path,required=True);parser.add_argument('--source',required=True);parser.add_argument('--reference',type=Path,required=True);args=parser.parse_args()
    expected=strict_json(args.reference.read_bytes(),4*1024*1024)['eventTransport']['buildIdentity']
    import json
    print(json.dumps(verify_gecko_cpu_evidence(args.directory,args.source,expected)))

if __name__=='__main__':main()
