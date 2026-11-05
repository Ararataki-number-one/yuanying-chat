#!/usr/bin/env python3
"""Require real Android browser evidence for the same source and APK as Gecko acceptance."""
import argparse
import hashlib
import json
from pathlib import Path
import re
import sys

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from gecko.profile_invocation_contract import verify_installed
from gecko.sdk_identity_contract import source_bytes

REQUIRED=(
    'The actual Android WebView rendered the proxy response',
    'The proxy override has acknowledged the actual route',
    'Native file chooser 1 returns its callback after user cancellation',
    'Native file chooser 2 returns its callback after user cancellation',
    'The actual native download publishes one complete file',
    'The browser file is discoverable in the global download index',
    'The old route token is rejected',
    'Blocked navigation opens no surface or proxy request',
    'Engine UI roundtrip preserves the exact live browser document and draft',
    'Browser controls are created at Android font scale two',
    'Large-font landscape keeps address and navigation targets visible',
    'Large-font portrait keeps address and navigation targets visible',
    'Large-font orientation changes preserve the live website draft and document',
    'A live browser surface retains the actual native route',
    'Both live tab surfaces own separate route leases',
    'In-flight native download owns its route lease',
    'Completed native downloads release their own route lease',
    'Retired surfaces and completed downloads release every route hold',
    'Restored live surface reacquires native route protection',
    'Engine task roundtrip retains the live Chromium route lease',
)
SOURCE_INPUTS={
    'tools/browser/run_integration.py',
    'tests/gecko/BrowserIntegrationActivity.java',
    'tests/gecko/BrowserEvidenceProvider.java',
    '.github/workflows/browser-2_1-acceptance.yml',
    'app/src/main/java/local/pocketchat/BrowserActivity.java',
    'app/src/main/java/local/pocketchat/ChromiumRuntime.java',
    'app/src/main/java/local/pocketchat/ChromiumRouteLease.java',
    'app/src/main/java/local/pocketchat/BrowserFiles.java',
    'app/src/main/java/local/pocketchat/BrowserDownloadStore.java',
}


def require(value,message):
    if not value:raise ValueError('Browser acceptance: '+message)


def validate_behavior(report,source,reader=source_bytes):
    require(report.get('status')=='passed' and report.get('sourceCommit')==source,'successful exact-source report required')
    require(report.get('executionInputsUnchanged') is True,'source inputs changed')
    require(report.get('actualAndroidExecution') is True and report.get('actualAndroidWebViewExecution') is True,'actual Android WebView execution required')
    require(all(report.get(k) is False for k in ['actualDesktopChromiumExecution','actualPublicWebsiteExecution','actualDevicePerformanceMeasurement']),'execution scopes differ')
    nonce=report.get('runNonce');require(isinstance(nonce,str) and re.fullmatch('[0-9a-f]{32}',nonce),'fresh invocation identity required')
    result=report.get('result',{});require(result.get('status')=='passed' and result.get('runNonce')==nonce and result.get('sourceCommit')==source,'fixture source/invocation differs')
    require(result.get('actualAndroidExecution') is True and result.get('actualAndroidWebViewExecution') is True,'fixture did not execute WebView')
    require(all(result.get(k) is False for k in ['actualGeckoExecution','actualPublicWebsiteExecution','actualDevicePerformanceMeasurement']),'fixture execution scopes differ')
    provider=result.get('provider',{});require(isinstance(provider,dict) and provider.get('package') and provider.get('version'),'actual provider identity required')
    checks=result.get('checks');require(isinstance(checks,list) and checks and result.get('passed')==result.get('total')==len(checks) and all(c.get('pass') is True for c in checks),'complete passing checks required')
    names=[c.get('name') for c in checks];require(len(names)==len(set(names)) and all(name in names for name in REQUIRED),'required browser scenarios missing or duplicated')
    actions=report.get('trustedAndroidActions',[]);taps=[a for a in actions if a.get('kind')=='tap'];backs=[a for a in actions if a.get('kind')=='back'];switches=[a for a in actions if a.get('kind')=='engine-roundtrip']
    require(report.get('actualAndroidTaps')==len(taps)==3 and {a.get('stage') for a in taps}=={'file-picker-1','file-picker-2','download-click'},'all three real browser taps required')
    require(len(backs)==2 and all(a.get('actualDocumentsUiObserved') is True for a in backs) and {a.get('stage') for a in backs}=={'file-picker-1','file-picker-2'},'both actual DocumentsUI cancellations required')
    require(len(switches)==1 and switches[0].get('actualEnhancedActivityResumed') is True,'actual engine activity roundtrip required')
    switch=switches[0];require(type(switch.get('browserTaskId')) is int and type(switch.get('enhancedTaskId')) is int and switch['browserTaskId']!=switch['enhancedTaskId'] and result.get('taskId')==switch['browserTaskId'],'independent task identity and browser return required')
    rotations=[a for a in actions if a.get('kind')=='rotation'];require([(a.get('stage'),a.get('value')) for a in rotations]==[('rotate-landscape',1),('rotate-portrait',0)],'both actual Android orientation changes required')
    layouts=result.get('layoutObservations',[]);require(len(layouts)==2 and [v.get('orientation') for v in layouts]==[2,1],'both measured native orientations required')
    for layout in layouts:
        require(isinstance(layout.get('fontScale'),(int,float)) and layout['fontScale']>=1.9,'large-font measurement required')
        controls=layout.get('controls',[]);require(len(controls)==5 and {c.get('name') for c in controls}=={'address','back','forward','tabs','reload'},'all native control bounds required')
        require(all(c.get('shown') is True and type(c.get('minimum')) is int and c['minimum']>0 and c.get('visibleWidth',0)>=c['minimum'] and c.get('visibleHeight',0)>=c['minimum'] for c in controls),'native control targets are clipped')
    leases=result.get('leaseObservations',[])
    expected_leases=[('first-surface',1,0),('two-surfaces',2,0),('download-in-flight',2,1),('download-complete',2,0),('route-blocked',0,0),('route-restored',1,0),('engine-roundtrip',1,0)]
    require(len(leases)==len(expected_leases),'complete actual route-lease observations required')
    for observed,(stage,surfaces,downloads) in zip(leases,expected_leases):
        require(observed.get('stage')==stage and observed.get('surfaces')==surfaces and observed.get('downloads')==downloads and observed.get('held') is bool(surfaces or downloads),'surface/download route retention differs')
        if surfaces or downloads:require(observed.get('nativeRouteBusy') is True,'native background route selector did not retain active Chromium work')
    proxy=result.get('proxy',{});require(proxy.get('upstreamConnections')==0 and proxy.get('forwardingImplemented') is False and proxy.get('downloadRequests',0)>0,'controlled proxy/download scope differs')
    hashes=report.get('sourceFiles',{});require(isinstance(hashes,dict) and SOURCE_INPUTS<=set(hashes),'source and harness hashes required')
    for path,sha in hashes.items():
        require(isinstance(path,str) and not Path(path).is_absolute() and '..' not in Path(path).parts and isinstance(sha,str) and re.fullmatch('[0-9a-f]{64}',sha),'invalid source hash entry')
        require(hashlib.sha256(reader(source,path)).hexdigest()==sha,'selected-source hash differs: '+path)
    return result


def verify_browser_evidence(directory,source,reader=source_bytes):
    directory=Path(directory);raw=(directory/'browser-results.json').read_bytes();require(0<len(raw)<=2*1024*1024,'bounded browser result required')
    report=json.loads(raw);result=validate_behavior(report,source,reader)
    device=json.loads((directory/'device-results.json').read_text());require(device.get('status')=='passed' and device.get('actualAndroidExecution') is True and device.get('sourceCommit')==source,'successful original Gecko acceptance required')
    expected=device['eventTransport']['buildIdentity'];require(expected.get('sourceCommit')==source,'reference build source differs')
    verify_installed(report['expectedBuildIdentity'],expected);verify_installed(result['buildIdentity'],expected)
    sdk=expected.get('sdkBuildIdentity',{})
    checked=dict(sourceCommit=source,sourceTree=expected['sourceTree'],integrationApkSha256=expected['apkSha256'],runId=sdk['runId'],runAttempt=sdk['runAttempt'],reportSha256=hashlib.sha256(raw).hexdigest(),checkCount=len(result['checks']),actualAndroidExecution=True,actualAndroidWebViewExecution=True,provider=result['provider'],physicalPhoneAcceptance=False,scope='Same source, run-bound SDK and exact integration APK as original Gecko acceptance; controlled Android WebView browser workload, no public website or device-speed claim')
    version=expected.get('version','')
    require(isinstance(version,str) and re.fullmatch(r'[0-9]+\.[0-9]+\.[0-9]+',version),'reference build version required')
    if tuple(map(int,version.split('.'))) >= (2,1,1):
        from browser.check_fingerprint_evidence import verify_fingerprint_evidence
        checked['fingerprintRegression']=verify_fingerprint_evidence(directory,source,expected,reader=reader)
    return checked


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--directory',required=True,type=Path);p.add_argument('--source',required=True);p.add_argument('--output',type=Path);a=p.parse_args()
    require(re.fullmatch('[0-9a-f]{40}',a.source),'complete source commit required');result=verify_browser_evidence(a.directory,a.source)
    if a.output:a.output.parent.mkdir(parents=True,exist_ok=True);a.output.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps(result,ensure_ascii=False))


if __name__=='__main__':main()
