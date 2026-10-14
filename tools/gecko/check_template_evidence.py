#!/usr/bin/env python3
"""Require distinct source/APK/invocation-bound controlled-template Android evidence."""
import argparse
import ast
import hashlib
import importlib.util
import json
import math
from pathlib import Path
import re
import subprocess
from urllib.parse import parse_qs, urlsplit

ROOT=Path(__file__).resolve().parents[2]

# Shared SDK expectations come from selected source, never report-provided pins.
import importlib.util as _sdk_importlib
_sdk_spec=_sdk_importlib.spec_from_file_location('selected_sdk_identity_contract',Path(__file__).with_name('sdk_identity_contract.py'))
_sdk=_sdk_importlib.module_from_spec(_sdk_spec);_sdk_spec.loader.exec_module(_sdk)
LIFECYCLE_SOURCE_FILES=tuple('app/src/main/java/local/pocketchat/'+name+'.java' for name in (
    'EnvironmentSpec','EnvironmentResetPlan','EnvironmentBrowserData','EnvironmentProcessPolicy',
    'EnvironmentSpecRepository','ProfileCatalog','Profiles','ProfileContext','EnvironmentResetActivity',
    'WindowHomeActivity','MainActivity','ChatSession','ChatService','NetworkUiProvider','AppUpdateRoute',
    'EnvironmentDeleteActivity','EnvironmentSpecRuntime'))+(
    'app/src/main/AndroidManifest.xml','tests/browser-runtime/EnvironmentLifecyclePolicyTest.java',
    'tests/gecko/EnvironmentManagementIntegrationActivity.java','tests/gecko/run_device.py')
READING_FIXTURE_CLEANUP_ACTION='readingFixtureCookieCleanup'
READING_FIXTURE_CLEANUP_SOURCE_FILES=(
    'tests/gecko/GeckoIntegrationTestActivity.java','tools/gecko/check_template_evidence.py',
    'tools/gecko/integration_event_contract.py','tools/gecko/profile_invocation_contract.py')


def requires_reading_fixture_cleanup(source):
    """Read capability from the selected producers, never from an evidence claim."""
    action=READING_FIXTURE_CLEANUP_ACTION
    runner=ast.parse(selected_bytes(source,'tests/gecko/run_device.py').decode())
    calls=[node for node in ast.walk(runner) if isinstance(node,ast.Call)
           and isinstance(node.func,ast.Name) and node.func.id=='run'
           and len(node.args)>=2 and isinstance(node.args[1],ast.Constant)
           and node.args[1].value==action]
    java=selected_bytes(source,'tests/gecko/GeckoIntegrationTestActivity.java').decode()
    producers=re.findall(r'\bif\s*\(\s*"'+action+r'"\s*\.equals\(\s*action\s*\)\s*\)',java)
    if not calls and not producers:return False
    if len(calls)!=1 or len(producers)!=1 or len(calls[0].args)!=3 or calls[0].keywords:
        raise ValueError('Selected reading-cookie cleanup producers disagree')
    if not all(isinstance(node,ast.Constant) for node in calls[0].args) or [node.value for node in calls[0].args]!=[2,action,action] or type(calls[0].args[0].value) is not int:
        raise ValueError('Selected reading-cookie cleanup invocation differs')
    return True


def lifecycle_required_source_files(source):
    return LIFECYCLE_SOURCE_FILES+(READING_FIXTURE_CLEANUP_SOURCE_FILES if requires_reading_fixture_cleanup(source) else ())


def expected_lifecycle_host_names(source):
    raw=selected_bytes(source,'tests/browser-runtime/EnvironmentLifecyclePolicyTest.java').decode()
    names=re.findall(r'\b(?:check|rejects)\(\s*("(?:[^"\\]|\\.)*")',raw)
    names=[json.loads(name) for name in names]
    if len(names)!=39 or len(set(names))!=39:raise ValueError('Selected lifecycle source must retain 39 unique literal controls')
    return names


def verify_lifecycle_sources(files,source):
    required=lifecycle_required_source_files(source)
    if not isinstance(files,dict) or not set(required).issubset(files):raise ValueError('Lifecycle host receipt omits production/fixture/admission sources')
    for path in required:
        digest=files[path]
        if not isinstance(digest,str) or not re.fullmatch('[0-9a-f]{64}',digest) or hashlib.sha256(selected_bytes(source,path)).hexdigest()!=digest:
            raise ValueError('Lifecycle source hash differs: '+path)


def verify_lifecycle_host(host,source):
    groups=[group for group in host.get('results',[]) if group.get('test')=='EnvironmentLifecyclePolicyTest']
    if len(groups)!=1 or type(groups[0].get('exitCode')) is not int or groups[0]['exitCode']!=0:raise ValueError('Production lifecycle host controls are missing')
    control=json.loads(groups[0].get('output','{}'));names=expected_lifecycle_host_names(source);checks=control.get('checks',[])
    if control.get('status')!='passed' or control.get('actualAndroidExecution') is not False or type(control.get('passed')) is not int or control['passed']!=39 or type(control.get('total')) is not int or control['total']!=39 or not isinstance(checks,list) or [row.get('name') for row in checks]!=names or any(row.get('pass') is not True for row in checks):raise ValueError('All 39 ordered source lifecycle controls must actually pass')
    return 39


def _java_arguments(text,start):
    """Read only a literal producer's top-level arguments, not its result expressions."""
    parts=[];begin=start;depth=0;quoted=False;escaped=False
    for index in range(start,len(text)):
        char=text[index]
        if quoted:
            if escaped:escaped=False
            elif char=='\\':escaped=True
            elif char=='"':quoted=False
        elif char=='"':quoted=True
        elif char in '([{':depth+=1
        elif char in ')]}':
            if char==')' and depth==0:return parts+[text[begin:index].strip()]
            depth-=1
        elif char==',' and depth==0:parts.append(text[begin:index].strip());begin=index+1
    raise ValueError('Lifecycle result producer has incomplete arguments')


def lifecycle_flag_names(source,action):
    raw=selected_bytes(source,'tests/gecko/EnvironmentManagementIntegrationActivity.java').decode()
    branches=list(re.finditer(r'(?:if|else if)\("([A-Za-z]+)"\.equals\(action\)\)\{',raw))
    matches=[i for i,match in enumerate(branches) if match.group(1)==action]
    if len(matches)!=1:raise ValueError('Actual lifecycle producer action missing: '+action)
    index=matches[0];body=raw[branches[index].end():branches[index+1].start() if index+1<len(branches) else len(raw)]
    initial=re.search(r'\bresult\s*=\s*J\.obj\(',body)
    if initial is None:raise ValueError('Actual lifecycle initial result missing: '+action)
    arguments=_java_arguments(body,initial.end())
    if len(arguments)%2:raise ValueError('Lifecycle result keys/values are incomplete')
    try:names=[json.loads(value) for value in arguments[::2]]
    except ValueError as error:raise ValueError('Lifecycle result keys must remain literal') from error
    names=[name for name in names if name!='action']
    names+=re.findall(r'NetworkCatalog\.put\(result,\s*"([A-Za-z][A-Za-z0-9]*)"',body)
    if not names or len(set(names))!=len(names):raise ValueError('Lifecycle expected flags are missing or duplicated')
    return names


def _cookie_case(step,context,action,populated):
    if not isinstance(step,dict) or step.get('kind')!='fixture' or step.get('nativeContext')!='environment-'+str(context) or type(step.get('processSlot')) is not int or step['processSlot']!=context-1:raise ValueError('Lifecycle browser step belongs to another environment')
    result=step.get('result',{})
    if result.get('context')!=str(context) or result.get('action')!=action or 'error' in result:raise ValueError('Lifecycle browser step action differs')
    expected='synthetic-environment-'+str(context) if populated else None
    if any(result.get(key)!=expected or key not in result for key in ('localStorage','indexedDB','cache','workerToken')) or result.get('cookie')!=('probe='+expected if populated else '') or type(result.get('serviceWorkers')) is not int or result['serviceWorkers']!=int(populated):raise ValueError('Actual lifecycle site storage/cookie isolation failed')
    raw=result.get('nativeCookies')
    if not isinstance(raw,str):raise ValueError('Actual native lifecycle Cookie observation missing')
    parts=[part.split('=',1) for part in raw.split('; ') if part]
    if any(len(part)!=2 for part in parts) or len({part[0] for part in parts})!=len(parts) or dict(parts)!=({'probe':expected,'nativeOnly':expected} if populated else {}):raise ValueError('Actual native lifecycle Cookie isolation failed')


def _reading_cookie_tokens(raw):
    if not isinstance(raw,str):raise ValueError('Reading-cookie cleanup observation missing')
    tokens=[token.strip() for token in raw.split(';') if token.strip()]
    if any('=' not in token or not token.split('=',1)[0] for token in tokens):
        raise ValueError('Reading-cookie cleanup observation is malformed')
    return tokens


def _verify_reading_cookie_removal(before,after):
    marker='readingBounds=controlled-fixture'
    first=_reading_cookie_tokens(before);last=_reading_cookie_tokens(after)
    named=[token for token in first if token.split('=',1)[0]=='readingBounds']
    if named!=[marker] or any(token.split('=',1)[0]=='readingBounds' for token in last):
        raise ValueError('Reading-cookie cleanup must retire exactly its known marker')
    if sorted(token for token in first if token!=marker)!=sorted(last):
        raise ValueError('Reading-cookie cleanup changed another cookie')


def _verify_reading_cleanup_invocation(report,source,value):
    transport=report.get('eventTransport')
    if not isinstance(transport,dict) or type(transport.get('schema')) is not int or transport['schema']!=1:
        raise ValueError('Reading-cookie cleanup event transport missing')
    identity=transport.get('buildIdentity')
    if not isinstance(identity,dict) or identity.get('sourceCommit')!=source:
        raise ValueError('Reading-cookie cleanup installed source differs')
    invocations=transport.get('invocations')
    if not isinstance(invocations,list) or any(not isinstance(item,dict) for item in invocations):
        raise ValueError('Reading-cookie cleanup invocation missing')
    matches=[item for item in invocations if item.get('fixtureAction')==READING_FIXTURE_CLEANUP_ACTION]
    nonce=value['runNonce'];owned=[item for item in invocations if item.get('runNonce')==nonce]
    if len(matches)!=1 or len(owned)!=1 or owned[0]!=matches[0] or type(matches[0].get('processSlot')) is not int or matches[0]['processSlot']!=1:
        raise ValueError('Reading-cookie cleanup nonce/action/environment differs')
    records=matches[0].get('events')
    if not isinstance(records,list) or not records:
        raise ValueError('Reading-cookie cleanup complete event bytes missing')
    decode_event=selected_contract(source,'integration_event_contract').decode_event
    completed=[]
    for sequence,record in enumerate(records,1):
        if not isinstance(record,dict) or not isinstance(record.get('receipt'),dict) or not isinstance(record.get('rawUtf8'),str):
            raise ValueError('Reading-cookie cleanup complete event record missing')
        receipt=record['receipt']
        if type(receipt.get('sequence')) is not int or receipt['sequence']!=sequence:
            raise ValueError('Reading-cookie cleanup event sequence differs')
        event=decode_event(receipt,record['rawUtf8'].encode('utf-8'),identity=identity,
                           nonce=nonce,slot=1,action=READING_FIXTURE_CLEANUP_ACTION,command=value['invocation'])
        if event.get('kind')=='error' or 'error' in event['result']:
            raise ValueError('Reading-cookie cleanup invocation contains a failure')
        if event.get('kind')==READING_FIXTURE_CLEANUP_ACTION:completed.append(event['result'])
    if completed!=[value] or event.get('kind')!=READING_FIXTURE_CLEANUP_ACTION:
        raise ValueError('Reading-cookie cleanup differs from its final complete owned event')


def verify_reading_fixture_cleanup(report,source,steps,copy_index):
    action=READING_FIXTURE_CLEANUP_ACTION
    found=[index for index,step in enumerate(steps) if isinstance(step,dict) and step.get('kind')==action]
    if copy_index<3 or found!=[copy_index-3]:
        raise ValueError('Reading-cookie cleanup must immediately precede lifecycle seeds')
    step=steps[found[0]];value=report.get(action)
    if not isinstance(value,dict) or step.get('result')!=value or 'error' in value:
        raise ValueError('Reading-cookie cleanup summary differs from its unique actual step')
    if step.get('nativeContext')!='environment-2' or type(step.get('processSlot')) is not int or step['processSlot']!=1 or type(value.get('processSlot')) is not int or value['processSlot']!=1:
        raise ValueError('Reading-cookie cleanup belongs to another environment')
    if type(value.get('schema')) is not int or value['schema']!=1 or value.get('cookie')!='readingBounds=controlled-fixture' or value.get('cookiePath')!='/' or value.get('origin')!='http://127.0.0.1:8765':
        raise ValueError('Reading-cookie cleanup target differs')
    nonce=value.get('runNonce');invocation=value.get('invocation')
    if not isinstance(nonce,str) or not re.fullmatch('[0-9a-f]{32}',nonce) or type(invocation) is not int or invocation<=0:
        raise ValueError('Reading-cookie cleanup invocation identity missing')
    target=value.get('url')
    if not isinstance(target,str):raise ValueError('Reading-cookie cleanup document URL missing')
    parsed=urlsplit(target)
    if parsed.scheme!='http' or parsed.netloc!='127.0.0.1:8765' or parsed.path!='/reading-cookie-retirement' or parsed.fragment or parse_qs(parsed.query,keep_blank_values=True)!={'runNonce':[nonce]}:
        raise ValueError('Reading-cookie cleanup document is outside its owned invocation')
    flags=('sameSession','sameDocument','sameUrl','readingFixtureCookieRemovedFromDom',
           'readingFixtureCookieRemovedFromNative','otherDomCookiesPreserved','otherNativeCookiesPreserved')
    if any(value.get(flag) is not True for flag in flags):
        raise ValueError('Reading-cookie cleanup document/cookie receipt failed')
    before=value.get('sessionBefore');after=value.get('sessionAfter')
    if type(before) is not int or before<=0 or type(after) is not int or after!=before:
        raise ValueError('Reading-cookie cleanup SDK session changed')
    before=value.get('documentBefore');after=value.get('documentAfter')
    try:document_matches=type(before) in (int,float) and math.isfinite(before) and before>0 and type(after) in (int,float) and math.isfinite(after) and after==before
    except OverflowError:document_matches=False
    if not document_matches:
        raise ValueError('Reading-cookie cleanup document changed')
    _verify_reading_cookie_removal(value.get('beforeDomCookies'),value.get('afterDomCookies'))
    _verify_reading_cookie_removal(value.get('nativeBefore'),value.get('nativeAfter'))
    _verify_reading_cleanup_invocation(report,source,value)


def verify_lifecycle_device(report,source,identity=None):
    if report.get('status')!='passed' or report.get('actualAndroidExecution') is not True or report.get('releaseMode') is not True or report.get('diagnosticOnly') is not False or report.get('sourceCommit')!=source or 'error' in report or report.get('artifactErrors'):
        raise ValueError('Lifecycle requires successful actual same-source full device acceptance')
    if identity is not None:
        if __package__:
            from .profile_invocation_contract import verify_installed
        else:
            from profile_invocation_contract import verify_installed
        verify_installed(report.get('eventTransport',{}).get('buildIdentity',{}),identity)
    management=report.get('environmentManagement',{});steps=report.get('steps')
    if not isinstance(management,dict) or not isinstance(steps,list):raise ValueError('Actual lifecycle management/browser steps missing')
    indices=[]
    for action in ('copyAndReset','resetZero','deleteOne'):
        value=management.get(action)
        if not isinstance(value,dict) or value.get('action')!=action or 'error' in value or any(value.get(key) is not True for key in lifecycle_flag_names(source,action)) or any(item is not True for key,item in value.items() if key!='action'):raise ValueError('Actual lifecycle result is missing/failed: '+action)
        found=[i for i,step in enumerate(steps) if isinstance(step,dict) and step.get('kind')=='environmentManagement' and step.get('result',{}).get('action')==action]
        if len(found)!=1 or steps[found[0]]['result']!=value:raise ValueError('Lifecycle summary differs from its unique actual step: '+action)
        indices.append(found[0])
    copy_index,reset_index,delete_index=indices
    if not 2<=copy_index<reset_index<delete_index:raise ValueError('Lifecycle action order is incomplete')
    _cookie_case(steps[copy_index-2],1,'seed',True);_cookie_case(steps[copy_index-1],2,'seed',True)
    for begin,cases in ((copy_index,((2,'read',False),(1,'read',True))), (reset_index,((1,'read',False),(2,'read',True)))):
        for offset,(context,action,populated) in enumerate(cases,1):
            if begin+offset>=len(steps):raise ValueError('Lifecycle actual browser reads missing')
            _cookie_case(steps[begin+offset],context,action,populated)
    _cookie_case(steps[reset_index-1],2,'seed',True)
    following=[step for step in steps[delete_index+1:] if isinstance(step,dict) and step.get('kind')=='fixture']
    if not following:raise ValueError('Reused slot has no actual browser read')
    _cookie_case(following[0],2,'read',False)
    if requires_reading_fixture_cleanup(source):verify_reading_fixture_cleanup(report,source,steps,copy_index)
    return {'actualLifecycleDeviceAcceptance':True,'physicalPhoneAcceptance':False,'actions':['copyAndReset','resetZero','deleteOne']}


def selected_bytes(source,path):
    return subprocess.check_output(['git','show',source+':'+path],cwd=ROOT)


def selected_contract(source,name):
    path=Path(__file__).with_name(name+'.py')
    if path.read_bytes()!=selected_bytes(source,'tools/gecko/'+name+'.py'):
        raise ValueError('Evidence contract differs from selected source: '+name)
    helper=Path(__file__).with_name('sdk_identity_contract.py')
    if helper.read_bytes()!=selected_bytes(source,'tools/gecko/sdk_identity_contract.py'):
        raise ValueError('Shared SDK identity contract differs from selected source')
    module_name=(__package__+'.' if __package__ else '')+'selected_'+name
    spec=importlib.util.spec_from_file_location(module_name,path)
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module);return module


def verify_template_host(directory,source,tree):
    mandatory={'app/src/main/java/local/pocketchat/'+name+'.java' for name in ['BrowserIdentitySpec','AuditReport','IdentityTemplateController','FingerprintTemplateUi','BrowserEditIntent','DeferredBrowserSettings','EnvironmentResetPlan','EnvironmentBrowserData','EnvironmentProcessPolicy','EnvironmentResetActivity','EnvironmentSpecRepository','ProfileCatalog','Profiles']}
    mandatory.update('app/src/main/assets/gecko/'+name for name in ['background.js','content.js','main-world-audit.js'])
    counts={}
    host=json.loads((directory/'profile-host-results.json').read_text())
    verify_lifecycle_sources(host.get('files'),source)
    for receipt in [host,json.loads((directory/'identity-controller-host-results.json').read_text()),json.loads((directory/'identity-bridge-host-results.json').read_text())]:
        if receipt.get('status')!='passed' or receipt.get('actualAndroidExecution') is not False or receipt.get('sourceCommit')!=source or receipt.get('sourceTree')!=tree or receipt.get('sourceDirty') is not False or receipt.get('sourceUnchangedDuringChecks') is not True:
            raise ValueError('Every controlled template host report must use this clean frozen source')
        for path,digest in receipt.get('files',{}).items():
            if not isinstance(path,str) or '..' in Path(path).parts or Path(path).is_absolute() or not re.fullmatch('[0-9a-f]{64}',str(digest)) or hashlib.sha256(selected_bytes(source,path)).hexdigest()!=digest:
                raise ValueError('Controlled template host source hash differs: '+str(path))
        if receipt is host and not mandatory.issubset(receipt.get('files',{})):raise ValueError('Template host report omits production template or bridge sources')
        if 'checks' in receipt:
            if type(receipt.get('passed')) is not int or receipt['passed']<74 or receipt['passed']!=receipt.get('total') or len(receipt['checks'])!=receipt['passed'] or any(row.get('pass') is not True for row in receipt['checks']):raise ValueError('Controller host assertions are incomplete')
            counts['controller']=receipt['passed']
        elif receipt is not host:
            groups={row.get('test'):row for row in receipt.get('results',[])}
            for name,minimum in [('audit-bridge.test.cjs',9),('protection-handshake.test.cjs',3)]:
                group=groups.get(name,{})
                if type(group.get('passed')) is not int or group['passed']<minimum or group['passed']!=group.get('total'):raise ValueError('Actual source bridge host suite is incomplete')
                counts[name]=group['passed']
    deferred=json.loads((directory/'deferred-browser-host-results.json').read_text())
    if deferred.get('status')!='passed' or deferred.get('actualAndroidExecution') is not False or deferred.get('sourceCommit')!=source or deferred.get('sourceTree')!=tree or deferred.get('sourceDirty') is not False or deferred.get('sourceUnchangedDuringChecks') is not True or type(deferred.get('passed')) is not int or deferred['passed']<24 or deferred['passed']!=deferred.get('total') or len(deferred.get('checks',[]))!=deferred['passed'] or any(row.get('pass') is not True for row in deferred['checks']):raise ValueError('Production deferred browser failure/normal host controls are incomplete')
    if 'app/src/main/java/local/pocketchat/DeferredBrowserSettings.java' not in deferred.get('files',{}):raise ValueError('Deferred host fixture omitted the production coordinator')
    for path,digest in deferred['files'].items():
        if '..' in Path(path).parts or Path(path).is_absolute() or hashlib.sha256(selected_bytes(source,path)).hexdigest()!=digest:raise ValueError('Deferred browser host source hash changed')
    counts['deferredBrowser']=deferred['passed']
    intents=[group for group in host.get('results',[]) if group.get('test')=='BrowserEditIntentTest']
    if len(intents)!=1 or intents[0].get('exitCode')!=0:raise ValueError('Production editor intent host controls are missing')
    intent=json.loads(intents[0].get('output','{}'))
    if intent.get('status')!='passed' or intent.get('actualAndroidExecution') is not False or type(intent.get('passed')) is not int or intent['passed']<14 or intent['passed']!=intent.get('total') or len(intent.get('checks',[]))!=intent['passed'] or any(row.get('pass') is not True for row in intent['checks']):raise ValueError('Editor intent failure preservation host controls are incomplete')
    counts['editorIntent']=intent['passed']
    matches=[group for group in host.get('results',[]) if group.get('test')=='FingerprintTemplateTest']
    if len(matches)!=1 or matches[0].get('exitCode')!=0:raise ValueError('Actual production template/report host suite required')
    template=json.loads(matches[0].get('output','{}'))
    if template.get('actualAndroidExecution') is not False or template.get('status')!='passed' or type(template.get('passed')) is not int or template['passed']<95 or template['passed']!=template.get('total') or len(template.get('checks',[]))!=template['passed'] or any(row.get('pass') is not True for row in template['checks']):raise ValueError('Template report negative host assertions are incomplete')
    counts['lifecycle']=verify_lifecycle_host(host,source);counts['templateReport']=template['passed'];return counts


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
    _sdk.verify_gate_sdk(identity, directory, source, tree)
    if type(identity.get('apkBytes')) is not int or identity['apkBytes']<=0 or any(not re.fullmatch('[0-9a-f]{64}',str(identity.get(key,''))) for key in ['apkSha256','buildStampSha256']):raise ValueError('Installed APK byte identity missing')
    invocation.verify_invocation(report,identity,log.get('runNonce',''));invocation.verify(report,len(template.expected_check_names()),True)
    if log.get('diagnosticOnly') is not False or report.get('androidSdk')!=log.get('androidSdk') or type(report.get('androidSdk')) is not int or report['androidSdk']<26:raise ValueError('Template execution SDK/scope disagrees with runner')
    scope=template.verify_template_report(report)
    host_counts=verify_template_host(directory,source,tree)
    lifecycle=verify_lifecycle_device(json.loads((directory/'device-results.json').read_text()),source,identity)
    return dict(scope,status='passed',sourceCommit=source,sourceTree=tree,actualAndroidExecution=True,hostCounts=host_counts,lifecycle=lifecycle,apkSha256=identity['apkSha256'],reportSha256=hashlib.sha256(raw).hexdigest())


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('directory',type=Path);parser.add_argument('--source',required=True);args=parser.parse_args()
    print(json.dumps(verify_template_evidence(args.directory,args.source),indent=2))
