#!/usr/bin/env python3
"""Controlled resource observations; never physical capacity or native fingerprint acceptance."""
import re
import importlib.util
from pathlib import Path

_guard_spec=importlib.util.spec_from_file_location("resource_shared_guard_contract",Path(__file__).with_name("profile_invocation_contract.py"))
_guard=importlib.util.module_from_spec(_guard_spec);_guard_spec.loader.exec_module(_guard)
from urllib.parse import urlsplit, parse_qsl

CUSTOM=['INDEPENDENT_TIMEZONE','CANVAS_READBACK','WEBGL_IDENTITY','AUDIO_IDENTITY','FONT_IDENTITY']


def prototype_names():
    result=[]
    for index in range(4):
        result += [f'Case {index} uses the open production Gecko bridge',f'Case {index} retains the Java locale request']
        for name in ['primary']+(['secondary'] if index==3 else []):
            prefix=f'Case {index} {name} '
            result += [prefix+'observes the requested official UA mode',prefix+'has all main/frame/worker fields']
            for context in ['parent','frame','worker','blobWorker']:
                result += [prefix+context+' '+suffix for suffix in ['actual UA matches native session','observes SDK normalized language','agrees on observed language list','agrees on observed timezone']]
            result += [prefix+role+' has real server request headers' for role in ['page','frame','worker-script','page-fetch','worker-fetch','blob-worker-fetch']]
        if index==3:result += ['Two sessions share this runtime locale, not separate environment evidence']
    return result+list(_guard.GUARD_CHECK_NAMES)


def verify_resource_port_controls(report):
    """Check actual observer bytes and native ownership, not assertion booleans."""
    controls=report.get('resourcePortControls')
    if not isinstance(controls,dict) or controls.get('sourceCommit')!=report.get('sourceCommit') or controls.get('runNonce')!=report.get('runNonce') or controls.get('phaseScope')!='controlled-production-delegate-sdk-open-load' or controls.get('syntheticPopupActivation') is not True or any(controls.get(key) is not False for key in ('trustedPopupGesture','trustedUserGesture','realWebsiteExecution')) or controls.get('observerDelivery')!='Actual SDK document observer bytes read through native evaluate; unchanged bytes passed to production resource admission':
        raise ValueError('Retained resource popup scope is missing or claims a trusted gesture')
    def integer(value,minimum=1):
        return type(value) is int and minimum<=value<=2**63-1
    for key in ['parentSession','parentPort','popupSession','popupPort','returnedSession','returnedPort','parentEpochBefore','popupEpoch','returnEpoch']:
        if not integer(controls.get(key)):
            raise ValueError('Retained resource native ownership is missing: '+key)
    if controls['parentSession']==controls['popupSession'] or controls['parentPort']==controls['popupPort'] or controls['returnedSession']!=controls['parentSession'] or controls['returnedPort']!=controls['parentPort'] or not controls['parentEpochBefore']<controls['popupEpoch']<controls['returnEpoch']:
        raise ValueError('Retained resource parent restoration or navigation epochs differ')
    primary=report['cases'][0]['sessions'][0]['native']
    if controls['parentSession']!=primary['session'] or report['allocation']['actualRuntimeObject']!=primary['runtime']:
        raise ValueError('Retained resource parent/runtime differs from inherited actual SDK observations')
    parent_url=report['allocation']['recoveredTarget']+'&spa=1'
    popup_url=report['origin']+'/frame?run='+report['runNonce']+'&session=resource-popup'
    events=[]
    for key,url,busy,uploading in [('parentBefore',parent_url,True,True),('popup',popup_url,True,True),('parentReturned',parent_url,True,True),('parentIdle',parent_url,False,False)]:
        event=controls.get(key)
        if not isinstance(event,dict) or event.get('type')!='resource-work' or event.get('url')!=url or event.get('busy') is not busy or event.get('uploading') is not uploading or not integer(event.get('resourceSequence')) or not integer(event.get('capturedAt')) or not isinstance(event.get('documentId'),str) or not re.fullmatch('[a-zA-Z0-9-]{16,80}',event['documentId']) or not isinstance(event.get('resourceBinding'),str) or not re.fullmatch('[0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12}',event['resourceBinding']):
            raise ValueError('Actual retained resource observer event is incomplete: '+key)
        events.append(event)
    before,popup,returned,idle=events
    if any(controls.get(key)!=event['resourceBinding'] for key,event in [('parentBeforeBinding',before),('popupBinding',popup),('parentReturnedBinding',returned)]):
        raise ValueError('Native activation binding differs from actual document observer bytes')
    if returned['documentId']!=before['documentId'] or idle['documentId']!=before['documentId'] or popup['documentId']==before['documentId'] or len({before['resourceBinding'],popup['resourceBinding'],returned['resourceBinding']})!=3 or idle['resourceBinding']!=returned['resourceBinding'] or not before['resourceSequence']<returned['resourceSequence']<idle['resourceSequence']:
        raise ValueError('Retained observer document, activation binding or sequence differs')
    clocks=[event['capturedAt'] for event in events]
    if clocks!=sorted(clocks) or before['capturedAt']>=returned['capturedAt']:
        raise ValueError('Retained resource observations have inconsistent capture times')
    for key in ['stalePopupAfter','staleParentAfter']:
        state=controls.get(key)
        if not isinstance(state,dict) or type(state.get('websiteEpoch')) is not int or state['websiteEpoch']!=-1 or type(state.get('sequence')) is not int or state['sequence']!=0 or state.get('observerBinding')!=returned['resourceBinding'] or type(state.get('observerPort')) is not int or state['observerPort']!=controls['parentPort'] or type(state.get('navigationEpoch')) is not int or state['navigationEpoch']!=controls['returnEpoch']:
            raise ValueError('Stale resource observation changed retained native ownership: '+key)
    first,last=controls.get('before'),controls.get('after')
    if not isinstance(first,dict) or not isinstance(last,dict) or first.get('url')!=parent_url or last.get('url')!=parent_url or not isinstance(first.get('draft'),str) or not first['draft'] or first['draft']!=last.get('draft') or not isinstance(first.get('cookie'),str) or first['cookie']!=last.get('cookie') or [part.strip() for part in first['cookie'].split(';') if part.strip().startswith('resourceRetained=')]!=['resourceRetained=preserved'] or any(type(value.get('sent')) is not int or value['sent']!=0 for value in (first,last)):
        raise ValueError('Retained rebind changed controlled draft, cookie marker, URL or sends')


def verify_resource_report(report, expected):
    if report.get('schema')!=1 or report.get('sdkCoordinate')!='org.mozilla.geckoview:geckoview:157.0.20261005135250' or report.get('sdkAarSha256')!='15f1edf3c58abcdaf2783f299b8c19c3a36272d348969106a9009671fef8d268' or report.get('engineVersion')!='GeckoView 157.0.1':
        raise ValueError('Pinned actual official SDK report identity differs')
    if report.get('fixtureType')!='production-resource-pressure-controlled-v1' or report.get('resourceChecksCompleted') is not True:
        raise ValueError('Production resource fixture is incomplete')
    if any(report.get(key) is not False for key in ['releaseAcceptance','capacityAcceptance','physicalDeviceAcceptance','publicNetworkTraffic','fullDesktopUaConsistency','fingerprintTemplateAcceptance','fullTemplateAcceptance']):
        raise ValueError('Controlled resource observations cannot claim physical/native/release acceptance')
    if report.get('diagnosticOnly') is not True or report.get('actualAndroidExecution') is not True or report.get('actualGeckoExecution') is not True or report.get('synthetic') is not True or report.get('status')!='passed' or report.get('error') or report.get('failureType'):
        raise ValueError('Actual controlled Gecko resource execution failed')
    rows=report.get('resourceChecks')
    if not expected or len(set(expected))!=len(expected) or not isinstance(rows,list) or [x.get('name') for x in rows]!=expected or any(x.get('pass') is not True for x in rows):
        raise ValueError('Exact source resource assertions are missing or duplicated')
    all_rows=report.get('checks',[]);wanted=expected+prototype_names()
    if [x.get('name') for x in all_rows]!=wanted or any(x.get('pass') is not True for x in all_rows) or report.get('passed')!=len(wanted) or report.get('total')!=len(wanted):
        raise ValueError('The independent controlled SDK context checks must remain complete')
    _guard.verify_guard_evidence(report)
    _guard.verify_user_agent_evidence(report)
    allocation=report.get('allocation',{})
    if type(allocation.get('coldRuntimeCreates')) is not int or type(allocation.get('recoveryRuntimeCreates')) is not int or allocation.get('coldRuntimeCreates')!=0 or allocation.get('recoveryRuntimeCreates')!=1 or allocation.get('physicalCapacityAcceptance') is not False or allocation.get('pressureSource')!='synthetic-pressure-control':
        raise ValueError('Runtime creation proof/pressure scope differs')
    if type(allocation.get('actualRuntimeObject')) is not int or allocation['actualRuntimeObject']==0 or type(allocation.get('oldEpoch')) is not int or type(allocation.get('newEpoch')) is not int or allocation['newEpoch']<=allocation['oldEpoch']:
        raise ValueError('Actual runtime/navigation deadline observations are missing')
    origin=report.get('origin','');nonce=report.get('runNonce','')
    if not re.fullmatch(r'http://127\.0\.0\.1:[1-9][0-9]{0,4}',origin) or not re.fullmatch('[0-9a-f]{32}',nonce) or allocation.get('recoveredTarget')!=origin+'/frame?run='+nonce+'&case=4&session=secondary':
        raise ValueError('Captured resource candidate is not bound to this local invocation')
    verify_resource_port_controls(report)
    platform=report.get('platformMemory',{})
    if platform.get('known') is not True or platform.get('source')!='android-ActivityManager.MemoryInfo' or type(platform.get('lowMemory')) is not bool:
        raise ValueError('Actual Android platform snapshot is missing')
    for key in ['availableBytes','totalBytes','thresholdBytes','sampledAt','observedAt']:
        if type(platform.get(key)) is not int or platform[key]<0:raise ValueError('Invalid actual Android memory field: '+key)
    if platform['totalBytes']<=0 or platform['availableBytes']>platform['totalBytes'] or not 0<=platform['observedAt']-platform['sampledAt']<=5000:
        raise ValueError('Actual platform observation is inconsistent or stale')
    process=platform.get('process',{})
    if process.get('source')!='android-Debug.MemoryInfo' or process.get('pid')!=report.get('pid') or 'Gecko child processes excluded' not in process.get('scope',''):
        raise ValueError('App PID memory observation scope is missing')
    for key in ['totalPssKb','javaUsedBytes','javaMaxBytes']:
        if type(process.get(key)) is not int or process[key]<=0:raise ValueError('Process memory observation is invalid')
    if report.get('nativeCustomCapabilities')!={key:'UNSUPPORTED' for key in CUSTOM}:
        raise ValueError('Stock SDK cannot claim new custom native controls')
    if not set(['physical ARM capacity','Gecko child process PSS','real ChatGPT tasks','native file chooser gesture','real upload/download throughput','independent process restoration','desktop Worker fetch UA consistency']).issubset(report.get('resourceUncovered',[])):
        raise ValueError('Resource acceptance limitations were removed')
    wire=[]
    cases=report.get('cases',[])
    if [case.get('index') for case in cases]!=list(range(4)) or [case.get('serial') for case in cases]!=list(range(1,5)):raise ValueError('Independent controlled cases missing')
    roles=['page','frame','worker-script','page-fetch','worker-fetch','blob-worker-fetch']
    for index,case in enumerate(cases):
        sessions=case.get('sessions',[])
        if case.get('status')!='passed' or [item.get('name') for item in sessions]!=['primary']+(['secondary'] if index==3 else []):raise ValueError('Controlled session shape changed')
        language=['en-US','ja-JP','zh-TW','en-US'][index]
        for session in sessions:
            actual=session.get('observed',{});native=session.get('native',{});ua=native.get('userAgent','')
            if actual.get('run')!=nonce or actual.get('case')!=index+1 or actual.get('session')!=session.get('name') or actual.get('provenance')!='controlled-page-main-world' or not isinstance(ua,str) or 'Firefox/157.' not in ua:raise ValueError('Actual controlled document/native ownership differs')
            if ('Android' not in ua) is not (index==1 or session.get('name')=='secondary'):raise ValueError('Controlled SDK UA mode differs')
            parent=actual.get('parent',{})
            for context in ['parent','frame','worker','blobWorker']:
                signal=actual.get(context,{})
                if signal.get('ua')!=ua or signal.get('language')!=language or signal.get('languages')!=parent.get('languages') or not isinstance(signal.get('languages'),list) or not signal['languages'] or signal['languages'][0]!=language or signal.get('zone')!=parent.get('zone') or not isinstance(signal.get('zone'),str) or not signal['zone'] or signal.get('offset')!=parent.get('offset') or type(signal.get('offset')) is not int or not -1440<=signal['offset']<=1440 or type(signal.get('cpu')) is not int or signal['cpu']<=0 or 'memory' not in signal or not isinstance(signal.get('intlLocale'),str) or not signal['intlLocale'] or signal.get('origin')!=origin:raise ValueError('Actual controlled context readback is incomplete or inconsistent')
            records=session.get('requestHeaders',[])
            if len(records)!=6 or set(row.get('role') for row in records)!=set(roles):raise ValueError('Six unique controlled request roles required')
            for row in session.get('requestHeaders',[]):
                path=urlsplit(row.get('path',''));query=parse_qsl(path.query,keep_blank_values=True)
                expected_query=[('run',nonce),('case',str(case.get('serial'))),('session',session.get('name'))]
                extra=[] if row.get('role') in ['page','frame','worker-script'] else [('kind',row.get('role'))]
                wanted_path={'page':'/page','frame':'/frame','worker-script':'/worker'}.get(row.get('role'),'/echo')
                if path.scheme or path.netloc or path.fragment or row.get('method')!='GET' or row.get('userAgent')!=(report['sdkUserAgentBaseline']['userAgent'] if row.get('role') in _guard.WORKER_FETCH_HEADER_ROLES else ua) or row.get('acceptLanguage','').split(',',1)[0].split(';',1)[0].strip()!=language or path.path!=wanted_path or query!=expected_query+extra or row.get('case')!=case.get('serial') or row.get('session')!=session.get('name'):
                    raise ValueError('Controlled SDK request ownership differs')
                wire.append(row)
    if report.get('allRequestHeaders')!=wire or [row.get('sequence') for row in wire]!=list(range(1,len(wire)+1)):
        # Request order across Workers is nondeterministic: sequence and raw
        # list agree, while session lists group their own requests.
        ordered=sorted(wire,key=lambda row:row.get('sequence',-1))
        if report.get('allRequestHeaders')!=ordered or [row.get('sequence') for row in ordered]!=list(range(1,len(wire)+1)):
            raise ValueError('Raw controlled request records changed')
    if len(wire)!=30:raise ValueError('All five actual session header contexts are required')
    return dict(status='passed',diagnosticOnly=True,capacityAcceptance=False,physicalDeviceAcceptance=False,fullDesktopUaConsistency=False,fingerprintTemplateAcceptance=False,fullTemplateAcceptance=False,workerFetchMismatchSessions=[dict(case=case['index'],sessions=case['workerFetchMismatchSessions']) for case in cases],nativeCustomControls='unsupported',resourceChecks=len(expected),controlledSdkChecks=len(prototype_names()),scope='Controlled actual Android/Gecko admission and retained tasks; synthetic pressure, actual platform/PID observations; no physical capacity, performance or uniform desktop Worker UA verdict')
