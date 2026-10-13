#!/usr/bin/env python3
"""Require distinct source/APK/invocation-bound controlled-template Android evidence."""
import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import re
import subprocess

ROOT=Path(__file__).resolve().parents[2]


def selected_bytes(source,path):
    return subprocess.check_output(['git','show',source+':'+path],cwd=ROOT)


def selected_contract(source,name):
    path=Path(__file__).with_name(name+'.py')
    if path.read_bytes()!=selected_bytes(source,'tools/gecko/'+name+'.py'):
        raise ValueError('Evidence contract differs from selected source: '+name)
    spec=importlib.util.spec_from_file_location('selected_'+name,path)
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module);return module


def verify_template_host(directory,source,tree):
    mandatory={'app/src/main/java/local/pocketchat/'+name+'.java' for name in ['BrowserIdentitySpec','AuditReport','IdentityTemplateController','FingerprintTemplateUi']}
    mandatory.update('app/src/main/assets/gecko/'+name for name in ['background.js','content.js','main-world-audit.js'])
    counts={}
    host=json.loads((directory/'profile-host-results.json').read_text())
    for receipt in [host,json.loads((directory/'identity-controller-host-results.json').read_text()),json.loads((directory/'identity-bridge-host-results.json').read_text())]:
        if receipt.get('status')!='passed' or receipt.get('actualAndroidExecution') is not False or receipt.get('sourceCommit')!=source or receipt.get('sourceTree')!=tree or receipt.get('sourceDirty') is not False or receipt.get('sourceUnchangedDuringChecks') is not True:
            raise ValueError('Every controlled template host report must use this clean frozen source')
        for path,digest in receipt.get('files',{}).items():
            if not isinstance(path,str) or '..' in Path(path).parts or Path(path).is_absolute() or not re.fullmatch('[0-9a-f]{64}',str(digest)) or hashlib.sha256(selected_bytes(source,path)).hexdigest()!=digest:
                raise ValueError('Controlled template host source hash differs: '+str(path))
        if receipt is host and not mandatory.issubset(receipt.get('files',{})):raise ValueError('Template host report omits production template or bridge sources')
        if 'checks' in receipt:
            if type(receipt.get('passed')) is not int or receipt['passed']<70 or receipt['passed']!=receipt.get('total') or len(receipt['checks'])!=receipt['passed'] or any(row.get('pass') is not True for row in receipt['checks']):raise ValueError('Controller host assertions are incomplete')
            counts['controller']=receipt['passed']
        elif receipt is not host:
            groups={row.get('test'):row for row in receipt.get('results',[])}
            for name,minimum in [('audit-bridge.test.cjs',9),('protection-handshake.test.cjs',3)]:
                group=groups.get(name,{})
                if type(group.get('passed')) is not int or group['passed']<minimum or group['passed']!=group.get('total'):raise ValueError('Actual source bridge host suite is incomplete')
                counts[name]=group['passed']
    matches=[group for group in host.get('results',[]) if group.get('test')=='FingerprintTemplateTest']
    if len(matches)!=1 or matches[0].get('exitCode')!=0:raise ValueError('Actual production template/report host suite required')
    template=json.loads(matches[0].get('output','{}'))
    if template.get('actualAndroidExecution') is not False or template.get('status')!='passed' or type(template.get('passed')) is not int or template['passed']<88 or template['passed']!=template.get('total') or len(template.get('checks',[]))!=template['passed'] or any(row.get('pass') is not True for row in template['checks']):raise ValueError('Template report negative host assertions are incomplete')
    counts['templateReport']=template['passed'];return counts


def verify_template_evidence(directory,source):
    directory=Path(directory)
    if not re.fullmatch('[0-9a-f]{40}',source):raise ValueError('Exact source commit required')
    tree=subprocess.check_output(['git','rev-parse',source+'^{tree}'],cwd=ROOT,text=True).strip()
    settings=selected_bytes(source,'app/build.gradle').decode();version=re.search(r"versionName '([^']+)'",settings).group(1);code=int(re.search('versionCode ([0-9]+)',settings).group(1))
    invocation=selected_contract(source,'profile_invocation_contract');template=selected_contract(source,'template_invocation_contract')
    raw=(directory/'gecko-template-results.json').read_bytes();report=json.loads(raw);log=json.loads((directory/'gecko-template-runner-log.json').read_text());identity=log.get('buildIdentity',{})
    if log.get('status')!='passed' or log.get('sourceCommit')!=source or log.get('installedBeforeAndAfterMatched') is not True or log.get('rawReportPreserved') is not True or log.get('reportSha256')!=hashlib.sha256(raw).hexdigest() or log.get('reportBytes')!=len(raw):raise ValueError('Installed/invocation-bound raw template evidence changed')
    if identity.get('sourceCommit')!=source or identity.get('sourceTree')!=tree or identity.get('dirtySource') is not False or identity.get('package')!='local.pocketchat.test' or identity.get('version')!=version or identity.get('versionCode')!=code or identity.get('sdkCoordinate')!=template.SDK:
        raise ValueError('Template APK identity differs from selected clean source/version/SDK')
    if type(identity.get('apkBytes')) is not int or identity['apkBytes']<=0 or any(not re.fullmatch('[0-9a-f]{64}',str(identity.get(key,''))) for key in ['apkSha256','buildStampSha256']):raise ValueError('Installed APK byte identity missing')
    invocation.verify_invocation(report,identity,log.get('runNonce',''));invocation.verify(report,len(template.expected_check_names()),True)
    if log.get('diagnosticOnly') is not False or report.get('androidSdk')!=log.get('androidSdk') or type(report.get('androidSdk')) is not int or report['androidSdk']<26:raise ValueError('Template execution SDK/scope disagrees with runner')
    scope=template.verify_template_report(report)
    host_counts=verify_template_host(directory,source,tree)
    return dict(scope,status='passed',sourceCommit=source,sourceTree=tree,actualAndroidExecution=True,hostCounts=host_counts,apkSha256=identity['apkSha256'],reportSha256=hashlib.sha256(raw).hexdigest())


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('directory',type=Path);parser.add_argument('--source',required=True);args=parser.parse_args()
    print(json.dumps(verify_template_evidence(args.directory,args.source),indent=2))
