#!/usr/bin/env python3
"""Verify distinct source/APK/nonce-bound actual resource diagnostic and host controls."""
import argparse
import hashlib
import json
from pathlib import Path
import re
import subprocess
try:
    from .check_template_evidence import selected_bytes, selected_contract
except ImportError:
    import sys
    sys.path.insert(0,str(Path(__file__).resolve().parent))
    from check_template_evidence import selected_bytes, selected_contract

ROOT=Path(__file__).resolve().parents[2]


def verify_resource_evidence(directory,source):
    directory=Path(directory)
    if not re.fullmatch('[0-9a-f]{40}',source):raise ValueError('Exact source required')
    tree=subprocess.check_output(['git','rev-parse',source+'^{tree}'],cwd=ROOT,text=True).strip()
    contract=selected_contract(source,'resource_invocation_contract');invocation=selected_contract(source,'profile_invocation_contract')
    expected=re.findall(r'resourceCheck\("([^"\n]+)"',selected_bytes(source,'tests/gecko/ResourcePressureIntegrationActivity.java').decode())
    raw=(directory/'resource-pressure-results.json').read_bytes();report=json.loads(raw);log=json.loads((directory/'resource-pressure-runner-log.json').read_text());identity=log.get('buildIdentity',{})
    settings=selected_bytes(source,'app/build.gradle').decode();version=re.search(r"versionName '([^']+)'",settings).group(1);code=int(re.search('versionCode ([0-9]+)',settings).group(1))
    if log.get('status')!='passed' or log.get('sourceCommit')!=source or log.get('installedBeforeAndAfterMatched') is not True or log.get('rawReportPreserved') is not True or log.get('diagnosticOnly') is not True or log.get('reportSha256')!=hashlib.sha256(raw).hexdigest() or log.get('reportBytes')!=len(raw):raise ValueError('Raw installed/invocation resource identity is incomplete')
    if identity.get('sourceCommit')!=source or identity.get('sourceTree')!=tree or identity.get('dirtySource') is not False or identity.get('package')!='local.pocketchat.test' or identity.get('version')!=version or identity.get('versionCode')!=code or identity.get('sdkCoordinate')!='org.mozilla.geckoview:geckoview:157.0.20261005135250':raise ValueError('Resource APK is not the selected clean version/source/SDK')
    if type(identity.get('apkBytes')) is not int or identity['apkBytes']<=0 or any(not re.fullmatch('[0-9a-f]{64}',str(identity.get(key,''))) for key in ['apkSha256','buildStampSha256']):raise ValueError('Installed resource APK bytes are missing')
    invocation.verify_invocation(report,identity,log.get('runNonce',''));invocation.verify_diagnostic(report)
    if report.get('androidSdk')!=log.get('androidSdk') or type(report.get('androidSdk')) is not int or report['androidSdk']<26:raise ValueError('Observed Android SDK differs')
    # A source stamp alone cannot establish that the baseline, template and
    # resource phases exercised the same installed integration APK bytes.
    device=json.loads((directory/'device-results.json').read_text())
    if device.get('status')!='passed' or device.get('actualAndroidExecution') is not True or device.get('releaseMode') is not True or device.get('diagnosticOnly') is not False or device.get('sourceCommit')!=source or 'error' in device or device.get('artifactErrors'):
        raise ValueError('Resource diagnostics require the successful full same-source device baseline')
    invocation.verify_installed(device.get('eventTransport',{}).get('buildIdentity',{}),identity)
    template_raw=(directory/'gecko-template-results.json').read_bytes();template=json.loads(template_raw)
    template_log=json.loads((directory/'gecko-template-runner-log.json').read_text())
    if template.get('status')!='passed' or template.get('actualAndroidExecution') is not True or template.get('diagnosticOnly') is not False or template_log.get('status')!='passed' or template_log.get('sourceCommit')!=source or template_log.get('diagnosticOnly') is not False or template_log.get('installedBeforeAndAfterMatched') is not True or template_log.get('rawReportPreserved') is not True or template_log.get('reportSha256')!=hashlib.sha256(template_raw).hexdigest() or template_log.get('reportBytes')!=len(template_raw):
        raise ValueError('Resource diagnostics require raw installed/invocation-bound template evidence')
    invocation.verify_installed(template_log.get('buildIdentity',{}),identity)
    invocation.verify_invocation(template,identity,template_log.get('runNonce',''))
    if any(type(value.get('androidSdk')) is not int or value['androidSdk']!=report['androidSdk'] for value in (device,template,template_log)):
        raise ValueError('Device, template and resource observations must use the same actual Android SDK')
    scope=contract.verify_resource_report(report,expected)
    host=json.loads((directory/'resource-pressure-host-results.json').read_text())
    names=re.findall(r'check\("([^"\n]+)"',selected_bytes(source,'tests/resource-pressure-host/local/pocketchat/ResourcePressureHostTest.java').decode())
    if host.get('status')!='passed' or host.get('sourceCommit')!=source or host.get('sourceTree')!=tree or host.get('sourceDirty') is not False or host.get('sourceUnchangedDuringChecks') is not True or host.get('actualAndroidExecution') is not False or host.get('synthetic') is not True or host.get('capacityAcceptance') is not False or host.get('actualPlatformMemoryObservation') is not False or host.get('error') or host.get('runnerError'):raise ValueError('Resource host source/scope mismatch')
    checks=host.get('checks',[])
    if not names or host.get('expectedCheckNames')!=names or [x.get('name') for x in checks]!=names or any(x.get('pass') is not True for x in checks) or any(host.get(key)!=len(names) for key in ['passed','total','executed']):raise ValueError('Exact production pressure JVM negative controls incomplete')
    required={'app/src/main/java/local/pocketchat/ResourcePressureController.java','tools/gecko/run_resource_host_checks.py','tests/resource-pressure-host/local/pocketchat/ResourcePressureHostTest.java','tests/resource-pressure-host/android/app/ActivityManager.java','tests/resource-pressure-host/android/content/Context.java','tests/resource-pressure-host/android/os/SystemClock.java'}
    if set(host.get('files',{}))!=required:raise ValueError('Compiled resource production/double inputs changed')
    for path,digest in host['files'].items():
        if hashlib.sha256(selected_bytes(source,path)).hexdigest()!=digest:raise ValueError('Resource host source hash differs: '+path)
    observer=json.loads((directory/'resource-observer-host-results.json').read_text())
    observer_names=re.findall(r"test\('([^'\n]+)'",selected_bytes(source,'tests/resource-web-observer.cjs').decode())
    if observer.get('status')!='passed' or observer.get('sourceCommit')!=source or observer.get('sourceTree')!=tree or observer.get('sourceDirty') is not False or observer.get('sourceUnchangedDuringChecks') is not True or observer.get('actualAndroidExecution') is not False or observer.get('actualPerformanceMeasurement') is not False or observer.get('capacityAcceptance') is not False or observer.get('realWebsiteExecution') is not False or observer.get('pageDriverExecuted') is not False:raise ValueError('DOM host scope/source mismatch')
    if observer.get('expectedCheckNames')!=observer_names or observer.get('passed')!=len(observer_names) or observer.get('total')!=len(observer_names) or observer.get('failed')!=0 or observer.get('executed')!=len(observer_names) or [row.get('name') for row in observer.get('checks',[])]!=observer_names or [row.get('index') for row in observer.get('checks',[])]!=list(range(1,len(observer_names)+1)) or any(row.get('pass') is not True for row in observer.get('checks',[])) or observer.get('exitCode')!=0 or observer.get('error'):raise ValueError('Actual observer host suite is incomplete')
    observer_files={'app/src/main/assets/web-reply-observer.js','app/src/main/assets/page-driver.js','tests/resource-web-observer.cjs','tools/gecko/run_resource_observer_host.py'}
    if set(observer.get('files',{}))!=observer_files:raise ValueError('Resource observer host inputs changed')
    for path,digest in observer['files'].items():
        if hashlib.sha256(selected_bytes(source,path)).hexdigest()!=digest:raise ValueError('Observer host source hash differs: '+path)
    return dict(scope,observerHostChecks=len(observer_names),sourceCommit=source,sourceTree=tree,actualAndroidExecution=True,hostChecks=len(names),apkSha256=identity['apkSha256'],sameInstalledApkAcrossRegressions=True,androidSdk=report['androidSdk'],reportSha256=hashlib.sha256(raw).hexdigest())


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('directory',type=Path);parser.add_argument('--source',required=True);args=parser.parse_args()
    print(json.dumps(verify_resource_evidence(args.directory,args.source),indent=2))
