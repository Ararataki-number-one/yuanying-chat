#!/usr/bin/env python3
"""Controlled resource observations; never physical capacity or native fingerprint acceptance."""
import re
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
    return result


def verify_resource_report(report, expected):
    if report.get('schema')!=1 or report.get('sdkCoordinate')!='org.mozilla.geckoview:geckoview:157.0.20261005135250' or report.get('sdkAarSha256')!='15f1edf3c58abcdaf2783f299b8c19c3a36272d348969106a9009671fef8d268' or report.get('engineVersion')!='GeckoView 157.0.1':
        raise ValueError('Pinned actual official SDK report identity differs')
    if report.get('fixtureType')!='production-resource-pressure-controlled-v1' or report.get('resourceChecksCompleted') is not True:
        raise ValueError('Production resource fixture is incomplete')
    if any(report.get(key) is not False for key in ['releaseAcceptance','capacityAcceptance','physicalDeviceAcceptance','publicNetworkTraffic']):
        raise ValueError('Controlled resource observations cannot claim physical/native/release acceptance')
    if report.get('diagnosticOnly') is not True or report.get('actualAndroidExecution') is not True or report.get('actualGeckoExecution') is not True or report.get('synthetic') is not True or report.get('status')!='passed' or report.get('error'):
        raise ValueError('Actual controlled Gecko resource execution failed')
    rows=report.get('resourceChecks')
    if not expected or len(set(expected))!=len(expected) or not isinstance(rows,list) or [x.get('name') for x in rows]!=expected or any(x.get('pass') is not True for x in rows):
        raise ValueError('Exact source resource assertions are missing or duplicated')
    all_rows=report.get('checks',[]);wanted=expected+prototype_names()
    if [x.get('name') for x in all_rows]!=wanted or any(x.get('pass') is not True for x in all_rows) or report.get('passed')!=len(wanted) or report.get('total')!=len(wanted):
        raise ValueError('The independent controlled SDK context checks must remain complete')
    allocation=report.get('allocation',{})
    if allocation.get('coldRuntimeCreates')!=0 or allocation.get('recoveryRuntimeCreates')!=1 or allocation.get('physicalCapacityAcceptance') is not False or allocation.get('pressureSource')!='synthetic-pressure-control':
        raise ValueError('Runtime creation proof/pressure scope differs')
    if type(allocation.get('actualRuntimeObject')) is not int or allocation['actualRuntimeObject']==0 or type(allocation.get('oldEpoch')) is not int or type(allocation.get('newEpoch')) is not int or allocation['newEpoch']<=allocation['oldEpoch']:
        raise ValueError('Actual runtime/navigation deadline observations are missing')
    origin=report.get('origin','');nonce=report.get('runNonce','')
    if not re.fullmatch(r'http://127\.0\.0\.1:[1-9][0-9]{0,4}',origin) or not re.fullmatch('[0-9a-f]{32}',nonce) or allocation.get('recoveredTarget')!=origin+'/frame?run='+nonce+'&case=4&session=secondary':
        raise ValueError('Captured resource candidate is not bound to this local invocation')
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
    if not set(['physical ARM capacity','Gecko child process PSS','real ChatGPT tasks','native file chooser gesture','real upload/download throughput','independent process restoration']).issubset(report.get('resourceUncovered',[])):
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
                if path.scheme or path.netloc or path.fragment or row.get('method')!='GET' or row.get('userAgent')!=ua or row.get('acceptLanguage','').split(',',1)[0].split(';',1)[0].strip()!=language or path.path!=wanted_path or query!=expected_query+extra or row.get('case')!=case.get('serial') or row.get('session')!=session.get('name'):
                    raise ValueError('Controlled SDK request ownership differs')
                wire.append(row)
    if report.get('allRequestHeaders')!=wire or [row.get('sequence') for row in wire]!=list(range(1,len(wire)+1)):
        # Request order across Workers is nondeterministic: sequence and raw
        # list agree, while session lists group their own requests.
        ordered=sorted(wire,key=lambda row:row.get('sequence',-1))
        if report.get('allRequestHeaders')!=ordered or [row.get('sequence') for row in ordered]!=list(range(1,len(wire)+1)):
            raise ValueError('Raw controlled request records changed')
    if len(wire)!=30:raise ValueError('All five actual session header contexts are required')
    return dict(status='passed',diagnosticOnly=True,capacityAcceptance=False,physicalDeviceAcceptance=False,nativeCustomControls='unsupported',resourceChecks=len(expected),controlledSdkChecks=len(prototype_names()),scope='Controlled actual Android/Gecko admission and retained tasks; synthetic pressure, actual platform/PID observations; no physical capacity or performance verdict')
