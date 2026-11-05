#!/usr/bin/env python3
"""Replay selected-source product TLS device originals and actual ClientHello wire."""
import argparse
import ast
import hashlib
import json
import os
from pathlib import Path,PurePosixPath
import re
import sys
os.environ['GIT_NO_LAZY_FETCH']='1'
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'tools'));sys.path.insert(0,str(ROOT/'tools/gecko'));sys.path.insert(0,str(ROOT/'tools/browser'))
from gecko.sdk_identity_contract import source_bytes,_typed_equal,SDK_FIELDS
from gecko.profile_invocation_contract import verify_installed,expected_build
from tls_acceptance_server import CASE_SPECS,HOST,GUEST_PORT,strict_json
from native_tls_probe_server import parse_client_hello
REPORT_NAME='gecko-tls-results.json'
RAW_DIRECTORY='gecko-tls-evidence'
CASE_FILES=tuple('case-'+row[0]+'.json' for row in CASE_SPECS)
SOURCE_INPUTS={
 'tools/browser/check_gecko_tls_evidence.py','tools/gecko/run_gecko_tls_acceptance.py','tools/gecko/tls_acceptance_contract.py','tools/gecko/tls_acceptance_server.py',
 'tools/browser/fingerprint_fixture_server.py','tools/browser/native_tls_probe_server.py','tools/gecko/profile_invocation_contract.py','tools/gecko/sdk_identity_contract.py',
 'tests/gecko/GeckoTlsAcceptanceActivity.java','tests/gecko/GeckoTlsAcceptanceProvider.java','tests/gecko/IntegrationBuildIdentity.java','tests/gecko/BrowserFingerprintFixture.java','tests/gecko/BrowserFingerprintIntegrationActivity.java','tests/gecko/AndroidManifest.xml',
 'tests/gecko/assets/tls-acceptance-page.js','tests/gecko/assets/tls-acceptance-worker.js','tests/gecko/res/xml/network_security.xml','app/src/main/res/xml/network_security.xml','app/src/main/AndroidManifest.xml','app/build.gradle',
 'app/src/main/java/local/pocketchat/GeckoTlsSpec.java','app/src/main/java/local/pocketchat/GeckoTlsStore.java','app/src/main/java/local/pocketchat/GeckoTlsUi.java','app/src/main/java/local/pocketchat/GeckoTlsController.java','app/src/main/java/local/pocketchat/GeckoTlsNative.java','app/src/main/java/local/pocketchat/GeckoTlsProfile.java',
 'app/src/main/java/local/pocketchat/GeckoWebView.java','app/src/main/java/local/pocketchat/ChatSession.java','app/src/main/java/local/pocketchat/Profiles.java','app/src/main/java/local/pocketchat/ProfileContext.java','app/src/main/java/local/pocketchat/GeckoCpuProfile.java','app/src/main/java/local/pocketchat/GeckoCpuController.java','app/src/main/java/local/pocketchat/GeckoCpuStore.java','app/src/main/java/local/pocketchat/NativeProtectionState.java','app/src/main/java/local/pocketchat/NormalCaretSdkReceipt.java',
 '.github/workflows/gecko-tls-acceptance.yml','tools/gecko/check_gecko_tls_package.py','tools/gecko/check_native_tls_package.py','tools/gecko/caret_build_identity.py'}

def require(value,message):
    if not value:raise ValueError('Selected product TLS gate: '+message)

def sha(raw):return hashlib.sha256(raw).hexdigest()

def digest(value,size=64):return type(value) is str and re.fullmatch('[0-9a-f]{'+str(size)+'}',value) is not None

def ordinary(path,maximum):
    path=Path(path).absolute();require(path.is_file() and not any(q.is_symlink() for q in (path,*path.parents)),'ordinary nonsymlink original file')
    require(0<path.stat().st_size<=maximum,'bounded original file');raw=path.read_bytes();require(0<len(raw)<=maximum,'file grew beyond bound');return raw

def source_hashes(report,source,reader):
    hashes=report.get('sourceFiles');require(type(hashes) is dict and SOURCE_INPUTS<=set(hashes) and len(hashes)<=10000,'all actual selected-source inputs')
    for path,value in hashes.items():
        require(type(path) is str and 0<len(path)<=500 and str(PurePosixPath(path))==path and not PurePosixPath(path).is_absolute() and '..' not in PurePosixPath(path).parts and '\\' not in path and '\0' not in path and digest(value),'safe immutable source hash')
        require(sha(reader(source,path))==value,'selected source differs: '+path)

def selected_contract(source,reader):
    raw=reader(source,'tools/gecko/tls_acceptance_contract.py');require(type(raw) is bytes and 0<len(raw)<=131072,'bounded actual validator source')
    parsed=ast.parse(raw);functions=[n for n in parsed.body if isinstance(n,ast.FunctionDef)]
    names={'require','equal','integer','token','native_policy','preparation','validate_device','validate_wire','validate_cross'}
    require({n.name for n in functions}==names and len(functions)==len(names),'exact actual selected validator functions')
    constants=[n for n in parsed.body if isinstance(n,ast.Assign) and len(n.targets)==1 and isinstance(n.targets[0],ast.Name) and n.targets[0].id in ('PACKAGE','DEVICE_FIELDS','POLICY_FIELDS')]
    require(len(constants)==3,'selected strict native schema constants')
    server=ast.parse(reader(source,'tools/gecko/tls_acceptance_server.py'));cases=[ast.literal_eval(n.value) for n in server.body if isinstance(n,ast.Assign) and any(isinstance(t,ast.Name) and t.id=='CASE_SPECS' for t in n.targets)]
    require(cases==[CASE_SPECS],'exact selected eleven-workload contract')
    namespace=dict(re=re,hashlib=hashlib,parse_qs=None,urlsplit=None,verify_installed=verify_installed,parse_client_hello=parse_client_hello,CASE_SPECS=CASE_SPECS,HOST=HOST)
    exec(compile(ast.Module(body=constants+functions,type_ignores=[]),'selected-product-tls-validator','exec'),namespace)
    return namespace

def trust(report,expected):
    host=report.get('hostTls');require(type(host) is dict,'native-valid controlled trust receipt')
    for flag in ('ephemeral','opensslChainVerified','privateMaterialRemoved','reverseRemoved'):require(host.get(flag) is True,'trust lifecycle '+flag)
    require(host.get('privateMaterialLocation')=='host-tmp-only' and host.get('privateMaterialExported') is False and host.get('certificateExceptionUsed') is False and host.get('hostnameVerified')==['fp-a.pocketchat.test','fp-b.pocketchat.test'] and type(host.get('guestPort')) is int and host['guestPort']==GUEST_PORT,'exact-origin host-only ephemeral trust')
    require(digest(host.get('caPemSha256')) and digest(host.get('leafDerSha256')),'public CA/leaf hashes')
    sdk=expected['sdkBuildIdentity'];binding=dict(sourceCommit=report['sourceCommit'],sourceTree=report['sourceTree'],runNonce=report['runNonce'],integrationApkSha256=expected['apkSha256'],sdkRunId=sdk['runId'],sdkRunAttempt=sdk['runAttempt'])
    require(_typed_equal(host.get('binding'),binding),'host source/APK/SDK/nonce binding')
    installation=host.get('trustInstallation');subject=host.get('subjectHashOld');require(type(installation) is dict and type(subject) is str and re.fullmatch('[0-9a-f]{8}',subject),'actual installed CA identity')
    require(installation.get('method')=='domain-scoped-user-ca' and type(installation.get('androidUser')) is int and installation['androidUser']==0,'domain-scoped user CA')
    for flag in ('adbRoot','selinuxEnforcing','installedPublicCaBytesMatch','appForceStoppedAfterInstall','removedAfterExecution','shellRestoredAfterInstall','shellRestoredAfterCleanup'):require(installation.get(flag) is True,'actual CA setup/cleanup '+flag)
    for key,value in (('evidenceShellUid',2000),('cleanupRootUid',0),('cleanupShellUid',2000)):require(type(installation.get(key)) is int and installation[key]==value,'CA UID '+key)
    require(installation.get('ownerAndMode')=='644:1000:1000' and type(installation.get('selinuxContext')) is str and re.fullmatch('u:object_r:(?!unlabeled)[a-zA-Z0-9_]+:s0',installation['selinuxContext']),'actual CA ownership and SELinux')
    require(installation.get('subjectHashOld')==subject and installation.get('storePath')=='/data/misc/user/0/cacerts-added/'+subject+'.0' and installation.get('publicCaPemSha256')==host['caPemSha256'] and installation.get('expectedLeafDerSha256')==host['leafDerSha256'],'actual public CA installation bytes/leaf')
    return host

def originals(directory):
    root=Path(directory).absolute();rawdir=root/RAW_DIRECTORY if (root/RAW_DIRECTORY).exists() else root
    require(rawdir.is_dir() and not any(p.is_symlink() for p in (rawdir,*rawdir.parents)),'ordinary raw evidence directory')
    summary=root/REPORT_NAME if (root/REPORT_NAME).exists() else rawdir/'results.json';raw=ordinary(summary,4*1024*1024);value=strict_json(raw,4*1024*1024)
    allowed=set(CASE_FILES)|{'results.json'}
    if rawdir==root:allowed.add(REPORT_NAME)
    names={p.name for p in rawdir.iterdir()};require(set(CASE_FILES)<=names and names<=allowed,'exact originals; no logs, private files, unknown JSON or directories')
    if (rawdir/'results.json').exists():require(ordinary(rawdir/'results.json',4*1024*1024)==raw,'duplicate summary alias must be identical')
    packets={name:ordinary(rawdir/name,262144) for name in CASE_FILES};return value,raw,packets,rawdir,summary

def verify_gecko_tls_evidence(directory,source,expected,reader=source_bytes):
    require(digest(source,40),'exact selected source');report,raw,packets,rawdir,summary=originals(directory)
    require(report.get('status')=='passed' and report.get('kind')=='gecko-production-tls-v1' and type(report.get('schema')) is int and report['schema']==1 and report.get('sourceCommit')==source,'completed original product gate')
    require(type(expected) is dict and type(expected.get('sdkBuildIdentity')) is dict,'original same-installed reference');actual=report.get('expectedBuildIdentity');require(type(actual) is dict,'actual installed reference')
    for key in ('schema','package','sourceCommit','sourceTree','dirtySource','version','versionCode','sdkCoordinate','apkSha256','apkBytes','buildStampSha256','sdkBuildIdentity')+SDK_FIELDS:require(_typed_equal(actual.get(key),expected.get(key)),'same source/build/APK/SDK tuple '+key)
    verify_installed(actual,expected);require(actual.get('sourceCommit')==source and actual.get('dirtySource') is False and actual.get('package')=='local.pocketchat.test' and digest(actual.get('apkSha256')) and digest(report.get('sourceTree'),40) and report['sourceTree']==actual['sourceTree'],'clean exact integration identity')
    sdk=actual['sdkBuildIdentity'];require(type(report.get('runId')) is str and report['runId']==sdk['runId'] and type(report.get('runAttempt')) is str and report['runAttempt']==sdk['runAttempt'] and digest(report.get('runNonce'),32),'same actual run and attempt')
    source_hashes(report,source,reader);contract=selected_contract(source,reader);host_tls=trust(report,expected)
    require(report.get('guest')==dict(actualEmulator=True,api=35,onlineCpus=4,evidenceShellUid=2000) and all(type(report['guest'][k]) is type(v) for k,v in dict(actualEmulator=True,api=35,onlineCpus=4,evidenceShellUid=2000).items()),'actual four-CPU API35 guest')
    require(report.get('diagnosticOnly') is True and report.get('releaseAcceptance') is False and report.get('executionInputsUnchanged') is True,'diagnostic gate scope and unchanged inputs')
    for flag in ('actualAndroidExecution','actualGeckoExecution','productionGeckoWebTlsWorkloadPassed','persistentServiceWorkerTlsMeasured'):require(report.get(flag) is True,'actual measured product gate '+flag)
    for flag in ('workerCoverageVerified','serviceWorkerCoverageVerified','fullTlsFingerprintEmulation','quicWireVerified','rawFatalAlertPacketDecoded','appIndependentTlsStacksCovered'):require(report.get(flag) is False,'unverified scope '+flag)
    cleanup=report.get('cleanup');keys={'appStopped','appDataCleared','reverseRemoved','serverClosed','serverThreadsJoined','caRemoved','privateMaterialRemoved','shellUidRestored'}
    require(type(cleanup) is dict and set(cleanup)==keys and all(v is True for v in cleanup.values()) and report.get('errors')==[],'all finally cleanup completed')
    rows=report.get('caseRecords');require(type(rows) is list and [r.get('label') for r in rows]==[s[0] for s in CASE_SPECS],'all eleven ordered originals')
    entries=[];hashes={};seen=set();ports={}
    for index,(spec,row,name) in enumerate(zip(CASE_SPECS,rows,CASE_FILES),1):
        require(type(row) is dict and set(row)=={'label','binding','status','report','reportSha256','finding'} and row['status']=='passed' and row['report']==name and row['reportSha256']==sha(packets[name]),'original packet bytes and outcome '+name)
        binding=row['binding'];require(type(binding) is dict and set(binding)=={'label','caseNonce','slot','port','epoch','service','serverOnlyVersion'} and binding['label']==spec[0] and digest(binding['caseNonce'],32) and binding['caseNonce'] not in seen and type(binding['epoch']) is int and binding['epoch']==index and type(binding['slot']) is int and binding['slot']==spec[1] and type(binding['service']) is bool and binding['service']==spec[9] and binding['serverOnlyVersion']==spec[7] and type(binding['port']) is int and 42000<=binding['port']<62000,'bound original fresh peer registration')
        seen.add(binding['caseNonce'])
        if spec[0]=='persistent-after':require(binding['port']==ports['persistent-before'],'retained worker exact origin')
        else:require(binding['port'] not in ports.values(),'fresh independent peer authority')
        ports[spec[0]]=binding['port'];device=strict_json(packets[name]);finding=contract['validate_device'](device,spec=spec,binding=binding,run=report['runNonce'],source=source,tree=report['sourceTree'],identity=expected,leaf=host_tls['leafDerSha256'])
        require(_typed_equal(row['finding'],finding),'current selected validator finding differs')
        entries.append(dict(row,device=device));hashes[spec[0]]=sha(packets[name])
    contract['validate_cross'](entries,report.get('processChecks'));wire=contract['validate_wire'](report.get('host'),entries,run=report['runNonce'],source=source)
    require(_typed_equal(report.get('checked'),wire),'independent original wire replay differs')
    require(ordinary(summary,4*1024*1024)==raw and all(ordinary(rawdir/name,262144)==value for name,value in packets.items()),'original bytes changed during verification')
    return dict(sourceCommit=source,sourceTree=report['sourceTree'],runId=report['runId'],runAttempt=report['runAttempt'],runNonce=report['runNonce'],integrationApkSha256=expected['apkSha256'],reportSha256=sha(raw),caseCount=11,caseSha256=hashes,actualAndroidExecution=True,actualGeckoExecution=True,productionGeckoWebTlsWorkloadPassed=True,desiredOnlyUiPendingMeasured=True,nonemptyUserColdReconciled=True,persistentServiceWorkerTlsMeasured=True,concurrentEnvironmentsMeasured=True,connectionScope='gecko-web-connections',independentDownloaderTlsCovered=False,connectionCheckTlsCovered=False,proxyEntranceTlsCovered=False,workerCoverageVerified=False,serviceWorkerCoverageVerified=False,fullTlsFingerprintEmulation=False,quicWireVerified=False,http2TransportVerified=False,rawFatalAlertPacketDecoded=False)

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('directory',type=Path);p.add_argument('--source',required=True);p.add_argument('--apk',type=Path);p.add_argument('--output',type=Path);a=p.parse_args();report,_,_,_,_=originals(a.directory)
    expected=report['expectedBuildIdentity']
    if a.apk:
        import subprocess
        tree=subprocess.check_output(['git','rev-parse',a.source+'^{tree}'],cwd=ROOT,text=True).strip();gradle=source_bytes(a.source,'app/build.gradle').decode();expected=expected_build(a.apk,a.source,tree,re.search(r"versionName '([^']+)'",gradle)[1],int(re.search(r'versionCode ([0-9]+)',gradle)[1]))
    result=verify_gecko_tls_evidence(a.directory,a.source,expected)
    if a.output:
        require(not a.output.exists(),'fresh replay output');a.output.parent.mkdir(parents=True,exist_ok=True);a.output.write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps(result,sort_keys=True))
if __name__=='__main__':main()
