#!/usr/bin/env python3
"""Controlled-template observations only. No device execution or full fingerprint attestation."""
import importlib.util
from pathlib import Path
import re
from urllib.parse import parse_qsl, urlsplit

# Shared SDK expectations come from selected source, never report-provided pins.
import importlib.util as _sdk_importlib
_sdk_spec=_sdk_importlib.spec_from_file_location('selected_sdk_identity_contract',Path(__file__).with_name('sdk_identity_contract.py'))
_sdk=_sdk_importlib.module_from_spec(_sdk_spec);_sdk_spec.loader.exec_module(_sdk)

# The runner/public gate bind this shared pure contract to the selected source.
_guard_spec=importlib.util.spec_from_file_location('template_shared_guard_contract',Path(__file__).with_name('profile_invocation_contract.py'))
_guard=importlib.util.module_from_spec(_guard_spec);_guard_spec.loader.exec_module(_guard)

SDK='org.mozilla.geckoview:geckoview:157.0.20261005135250'
AAR='15f1edf3c58abcdaf2783f299b8c19c3a36272d348969106a9009671fef8d268'
TEMPLATES=['standard-mobile','standard-desktop','compatibility-mobile','compatibility-desktop']
REQUESTS=[['en-US'],['ja-JP'],['zh-Hant-TW'],['en-US']]
NORMALIZED=['en-US','ja-JP','zh-TW','en-US']
FIELDS=['ua','cpu','memory','language','languages','offset','zone']
ROLES=['page','frame','worker-script','page-fetch','worker-fetch','blob-worker-fetch']
UNCOVERED=['cross-origin frame','Shared Worker','Service Worker','RFP compatibility','real account login','native IME','separate environment isolation','restart persistence','safe-idle application during real tasks','desktop Worker fetch UA consistency']


def expected_check_names():
    names=[]
    for index in range(4):
        names.append(f'Case {index} uses the open production Gecko bridge')
        for suffix in ['desired configuration retains requested locales','SDK getter only acknowledges the request','SDK-normalized prediction is separate','applies production UA and phone-fit viewport','applies actual tracking-list policy']:
            names.append(f'Template {index} '+suffix)
        for session in ['primary']+(['secondary'] if index==3 else []):
            prefix=f'Case {index} {session} '
            names.extend([prefix+'observes the requested official UA mode',prefix+'has all main/frame/worker fields'])
            for context in ['parent','frame','worker','blobWorker']:
                names.extend(prefix+context+' '+suffix for suffix in ['actual UA matches native session','observes SDK normalized language','agrees on observed language list','agrees on observed timezone'])
            names.extend(prefix+role+' has real server request headers' for role in ROLES)
        if index==3:names.append('Two sessions share this runtime locale, not separate environment evidence')
        names.extend(f'Template {index} '+suffix for suffix in ['receives the current native privacy acknowledgement','accepted identity remains requested configuration','actual production acknowledgement binds desired revision'])
        names.extend(f'Template {index} actual observation report covers '+key for key in ['ua','language','frame','worker','zone'])
        names.append(f'Template {index} production controller records the observed revision')
    return names+list(_guard.GUARD_CHECK_NAMES)


def complete_signal(signal):
    if not isinstance(signal,dict):return False
    for key in ['ua','language','zone','intlLocale']:
        if not isinstance(signal.get(key),str) or not signal[key]:return False
    langs=signal.get('languages')
    if not isinstance(langs,list) or not langs or len(langs)>8 or any(not isinstance(value,str) or not value for value in langs):return False
    if type(signal.get('cpu')) is not int or not 0<signal['cpu']<1024:return False
    for key in ['memory']:
        if key not in signal:return False
        value=signal[key]
        if value is not None and (type(value) not in (int,float) or not 0<value<1024):return False
    return type(signal.get('offset')) is int and -1440<=signal['offset']<=1440


def verify_template_report(report):
    if report.get('schema')!=1:raise ValueError('Template report schema is unsupported')
    if report.get('fixtureType')!='production-template-controlled-contexts-v1' or report.get('diagnosticOnly') is not False or report.get('controlledTemplateAcceptance') is not True:
        raise ValueError('A distinct production template fixture is required, not the SDK prototype')
    if report.get('status')!='passed' or report.get('actualAndroidExecution') is not True or report.get('actualGeckoExecution') is not True or report.get('synthetic') is not True or report.get('publicNetworkTraffic') is not False:
        raise ValueError('Actual controlled Android/Gecko execution is incomplete')
    if any(report.get(key) is not False for key in ['releaseAcceptance','fingerprintTemplateAcceptance','realAccountLogin','safeIdleApplicationAcceptance','fullDesktopUaConsistency']):
        raise ValueError('Controlled observations cannot certify untested ChatGPT or lifecycle flows')
    _sdk.verify_report_sdk(report)
    if report.get('templateIds')!=TEMPLATES or set(report.get('uncovered',[]))!=set(UNCOVERED) or 'unsupported' not in report.get('independentTimezone',''):
        raise ValueError('Template or unsupported capability scope changed')
    names=expected_check_names();checks=report.get('checks',[])
    if report.get('passed')!=len(names) or report.get('total')!=len(names) or [item.get('name') for item in checks]!=names or any(item.get('pass') is not True for item in checks):
        raise ValueError('Every exact ordered template/context/header/controller assertion must pass')
    _guard.verify_guard_evidence(report)
    _guard.verify_user_agent_evidence(report)
    if report.get('error') or report.get('failureType'):raise ValueError('Template fixture recorded a failure')
    cases=report.get('cases');applied=report.get('appliedCases')
    if not isinstance(cases,list) or not isinstance(applied,list) or [item.get('index') for item in cases]!=list(range(4)) or [item.get('index') for item in applied]!=list(range(4)):
        raise ValueError('All four independent template cases are required')
    origin=report.get('origin','');nonce=report.get('runNonce','')
    if not re.fullmatch(r'http://127\.0\.0\.1:[1-9][0-9]{0,4}',origin) or not re.fullmatch('[0-9a-f]{32}',nonce):raise ValueError('Controlled origin or invocation nonce is invalid')
    all_wire=[];identity=None;previous_revision=0
    for index,(case,model) in enumerate(zip(cases,applied)):
        if case.get('status')!='passed' or case.get('serial')!=index+1:raise ValueError('Actual template case ownership is invalid')
        wanted_names=['primary']+(['secondary'] if index==3 else [])
        sessions=case.get('sessions',[])
        if [item.get('name') for item in sessions]!=wanted_names:raise ValueError('Actual session observations are missing or duplicated')
        privacy='standard' if index<2 else 'compatibility';desktop=index in [1,3]
        requested=dict(schema=1,templateId=TEMPLATES[index],display='desktop' if desktop else 'mobile',privacy=privacy,locales=REQUESTS[index],timezoneStrategy='system')
        native=model.get('nativePolicy',{})
        if model.get('templateId')!=TEMPLATES[index] or model.get('privacy')!=privacy or native.get('requested')!=requested or native.get('accepted')!=requested:
            raise ValueError('Requested/applied browser configuration does not match the tested template')
        if native.get('requestedLocales')!=REQUESTS[index] or native.get('expectedSdkLocales')!=[NORMALIZED[index]] or native.get('getterScope')!='requested-descriptor-only':
            raise ValueError('SDK request readback was mistaken for content locale adoption')
        if native.get('rfpAcknowledged') is not True or native.get('fingerprintingProtected') is not False or native.get('trackingProtection') is not (index<2):
            raise ValueError('Actual standard/compatibility privacy acknowledgement is missing')
        revision=model.get('desiredRevision')
        if type(revision) is not int or revision<=previous_revision or model.get('appliedRevision')!=revision or model.get('observedRevision')!=revision:
            raise ValueError('Production desired/applied/observed revisions were not acknowledged')
        previous_revision=revision
        current_identity=model.get('identity',{})
        if type(current_identity.get('slot')) is not int or type(current_identity.get('generation')) is not int or not re.fullmatch('[0-9a-f-]{36}',current_identity.get('environmentId','')):
            raise ValueError('Stable synthetic environment identity is incomplete')
        if identity is None:identity=current_identity
        if identity!=current_identity:raise ValueError('Controlled fixture changed environment identity')
        observation=model.get('report',{})
        rows={row.get('key'):row for row in observation.get('rows',[])}
        if observation.get('fresh') is not True or observation.get('identityAppliedRevision')!=revision or any(rows.get(key,{}).get('state')!='verified' for key in ['ua','language','frame','worker','zone']) or rows.get('worker-header',{}).get('state')!='uncovered' or observation.get('fullDesktopUaConsistency') is not False or observation.get('fingerprintTemplateAcceptance') is not False:
            raise ValueError('Actual page observation did not verify its promised fields')
        coverage=observation.get('contextCoverage',{})
        if coverage.get('requiredFields')!=FIELDS or any(coverage.get(context,{}).get('missingOrInvalid')!=[] or coverage.get(context,{}).get('different')!=[] or coverage.get(context,{}).get('compared')!=FIELDS for context in ['frame','worker']):
            raise ValueError('Incomplete contexts cannot certify template observations')
        for session in sessions:
            native_session=session.get('native',{});raw=session.get('observed',{});name=session['name'];ua=native_session.get('userAgent','')
            if not isinstance(ua,str) or not ua or 'Firefox/157.' not in ua or ('Android' in ua)==desktop:
                raise ValueError('Official Gecko session UA mode differs from template')
            if native_session.get('requestedLocales')!=REQUESTS[index] or native_session.get('getterLocales')!=REQUESTS[index] or native_session.get('expectedSdkNormalizedLanguage')!=NORMALIZED[index]:
                raise ValueError('Native request descriptor changed')
            if raw.get('run')!=nonce or raw.get('case')!=index+1 or raw.get('session')!=name or raw.get('provenance')!='controlled-page-main-world':
                raise ValueError('Raw browser signals belong to another controlled invocation')
            parent=raw.get('parent',{})
            for context in ['parent','frame','worker','blobWorker']:
                signal=raw.get(context,{})
                if not complete_signal(signal) or signal['ua']!=ua or signal['language'].lower()!=NORMALIZED[index].lower() or signal['languages']!=parent.get('languages') or signal['offset']!=parent.get('offset') or signal['zone']!=parent.get('zone'):
                    raise ValueError('Actual '+context+' identity fields are missing or inconsistent')
            wire=session.get('requestHeaders',[])
            if len(wire)!=len(ROLES) or set(item.get('role') for item in wire)!=set(ROLES):raise ValueError('All document and actual worker/page request headers are required')
            for header in wire:
                sequence=header.get('sequence')
                if type(sequence) is not int or sequence<1 or sequence>30 or header.get('method')!='GET':raise ValueError('Actual controlled server sequence or HTTP method is invalid')
                path=header.get('path')
                if not isinstance(path,str):raise ValueError('Actual controlled request path is missing')
                parsed=urlsplit(path)
                if parsed.scheme or parsed.netloc or parsed.fragment:raise ValueError('Controlled request path is not a relative first-party target')
                try:pairs=parse_qsl(parsed.query,strict_parsing=True,keep_blank_values=True)
                except ValueError as error:raise ValueError('Controlled query is invalid') from error
                query=dict(pairs)
                if len(query)!=len(pairs):raise ValueError('Controlled query keys are duplicated')
                role=header.get('role')
                wanted_path={'page':'/page','frame':'/frame','worker-script':'/worker'}.get(role,'/echo')
                wanted_query={'run':nonce,'case':str(index+1),'session':name}
                if role in ['page-fetch','worker-fetch','blob-worker-fetch']:wanted_query['kind']=role
                if parsed.path!=wanted_path or query!=wanted_query:raise ValueError('Actual HTTP headers belong to another endpoint or invocation')
                expected_header_ua=report['sdkUserAgentBaseline']['userAgent'] if role in ['worker-fetch','blob-worker-fetch'] else ua
                if header.get('case')!=index+1 or header.get('session')!=name or header.get('userAgent')!=expected_header_ua or header.get('acceptLanguage','').split(',')[0].split(';')[0].strip().lower()!=NORMALIZED[index].lower():
                    raise ValueError('Actual server-observed request headers disagree with the page')
            all_wire.extend(wire)
        if observation.get('controlledRequestHeaders')!=sessions[0].get('requestHeaders'):raise ValueError('Persisted observation omits real controlled HTTP evidence')
    if sorted(row.get('sequence') for row in all_wire)!=list(range(1,31)):raise ValueError('Every actual server sequence must occur once')
    if report.get('allRequestHeaders')!=sorted(all_wire,key=lambda row:row.get('sequence',-1)):raise ValueError('Complete actual first-party wire records are required')
    return {'controlledTemplateAcceptance':True,'fingerprintTemplateAcceptance':False,'fullDesktopUaConsistency':False,'realAccountLogin':False,'safeIdleApplicationAcceptance':False,'templateIds':TEMPLATES,'assertions':len(names),'sessions':5,'workerFetchHeaderScope':'sdk-build-mobile-default','workerFetchMismatchSessions':[{ 'case':case['index'],'sessions':case['workerFetchMismatchSessions']} for case in cases],'uncovered':UNCOVERED,'scope':'Production adapter/controller acknowledgements and actual controlled JS/document headers; Worker fetch headers match the independent SDK mobile build default, with desktop mismatch preserved. This is not uniform desktop HTTP UA acceptance. Process isolation, restart, real ChatGPT and experimental RFP remain separate acceptance.'}
