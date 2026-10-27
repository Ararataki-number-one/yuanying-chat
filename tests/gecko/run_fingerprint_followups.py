#!/usr/bin/env python3
"""Single source-bound AVD/HTTPS observation of fingerprint followups, never full attestation."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import select
import subprocess
import sys
import tempfile
import time
import uuid
from urllib.parse import parse_qs, urlsplit

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'tools/gecko'))
from profile_invocation_contract import expected_build,verify_installed

PACKAGE='local.pocketchat.test'
ORIGIN='https://10.0.2.2:9889'
REDIRECT_ORIGIN='https://10.0.2.2:9890'
FRAME_ORIGIN='https://10.0.2.2:9891'
FAULT_ORIGIN='https://10.0.2.2:9892'
BASE='/pocketchat-identity/v1/'
CASES=['standard-source-control','manual-api-checks','credential-and-redirect-controls',
       'top-level-request-identity','controlled-diagnostic-page-recovery','nonempty-draft-refusal','late-registration-cancellation',
       'synthetic-epoch-preflight-invalidation','browser-policy-preflight-invalidation',
       'strict-native-receipt-loss-control','bounded-context-api-checks','pinned-deep-reference-lifecycle',
       'manual-service-capability-controls','controlled-cross-origin-frame']

def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()

def reconcile(native,trace,service):
    """Independent receiver records are kept distinct from browser self-report."""
    if trace.get('runNonce')!=native['runNonce'] or trace.get('dropped')!=0 or service.get('dropped')!=0:
        raise ValueError('Observer nonce mismatch or dropped independent events')
    arrivals=trace['events']
    if [row.get('index') for row in arrivals]!=list(range(1,len(arrivals)+1)):
        raise ValueError('Original observer sequence incomplete')
    if any(row.get('kind')!='http' or row.get('connection',0)<=0 for row in arrivals):
        raise ValueError('Original HTTPS arrival lacks a real TLS connection')
    records=service['events']
    if [row.get('sequence') for row in records]!=list(range(1,len(records)+1)):
        raise ValueError('Original identity service sequence incomplete')
    for row in records:
        if not any(arrival['server']=='detector' and arrival['nonce']==row['nonce']
                   and arrival['path']==row['path'] and arrival['method']==row['method']
                   and arrival['headers']=={key:row['headers'][key] for key in ['userAgent','acceptLanguage','secFetchDest']}
                   for arrival in arrivals):
            raise ValueError('Service request record has no matching independent wire arrival')
    cases={row['case']:row for row in native['cases']}
    control=cases['credential-and-redirect-controls']
    def events(token,path,server='detector'):
        return [row for row in arrivals if row['nonce']==token and row['path']==path and row['server']==server]
    positive=events(control['baselineNonce'],'/credential-probe')
    if len(positive)!=1 or not all(positive[0]['sensitive'][key] for key in ['cookie','authorization','referer']):
        raise ValueError('Cookie/Authorization/Referer browser positive control unavailable; no filter verdict')
    if not positive[0].get('syntheticCookiePresent') or not positive[0].get('syntheticAuthorizationPresent'):
        raise ValueError('Positive control did not contain the exact synthetic sentinels')
    filtered=events(control['filteredNonce'],BASE+'document')
    if len(filtered)!=1 or any(filtered[0]['sensitive'].values()):
        raise ValueError('Registered request filter failed or cancellation allowed a later arrival')
    redirect_positive=events(control['redirectBaselineNonce'],'/redirect-control','redirect')
    followed=events(control['redirectBaselineNonce'],'/redirected')
    if len(redirect_positive)!=1 or len(followed)!=1:
        raise ValueError('Actual browser redirect positive control missing')
    blocked_redirect=events(control['redirectNonce'],BASE+'document','redirect')
    blocked_target=events(control['redirectNonce'],'/redirected')
    if len(blocked_redirect)!=1 or blocked_target or any(blocked_redirect[0]['sensitive'].values()):
        raise ValueError('Registered redirect was not independently observed as closed and credential-free')
    identity=cases['top-level-request-identity']
    token=parse_qs(urlsplit(identity['actualDetectorUrl']).query).get('nonce',[])
    if len(token)!=1 or not re.fullmatch('[a-f0-9]{32}',token[0]):
        raise ValueError('Actual controlled top-level document nonce missing')
    token=token[0]
    doc=events(token,BASE+'document');script=events(token,BASE+'worker.js');worker=events(token,BASE+'observe')
    if len(doc)!=1 or len(script)!=1 or len(worker)!=1:
        raise ValueError('Exactly one real detector document, Worker script and Worker request required')
    if doc[0]['headers']['secFetchDest']!='document' or script[0]['headers']['secFetchDest']!='worker':
        raise ValueError('Independent server cannot establish real top-level/Worker request destinations')
    if any(any(row['sensitive'].values()) for row in doc+script+worker):
        raise ValueError('Actual document or Worker probe carried a sensitive header')
    request=identity['report']['requestIdentity']
    if request.get('status') not in ['observed','issue'] or 'server' not in request or 'browser' not in request:
        raise ValueError('Production audit did not retain complete separately sourced browser/server evidence: '+request.get('status',''))
    saved={row['source']:row for row in request['server']['events']}
    for source,arrival in [('document',doc[0]),('worker-script',script[0]),('worker-fetch',worker[0])]:
        if saved[source]['headers']!=arrival['headers']:
            raise ValueError('Production result changed actual server request headers')
    browser=request['browser']
    if browser['document']['ua']!=identity['configuredSessionUserAgent']:
        raise ValueError('Controlled document did not use requested session UA')
    headers_same=doc[0]['headers']['userAgent']==worker[0]['headers']['userAgent']
    rows={row['key']:row for row in request['rows']}
    expected_worker='verified' if browser['worker']['ua']==worker[0]['headers']['userAgent'] else 'issue'
    if rows['request-worker-ua']['state']!=expected_worker:
        raise ValueError('Worker header mismatch was hidden or invented')
    strict=cases['strict-native-receipt-loss-control']
    for name in ['late-registration-cancellation','synthetic-epoch-preflight-invalidation','browser-policy-preflight-invalidation']:
        token=cases[name]['nonce']
        if any(row['nonce']==token for row in arrivals):
            raise ValueError('Cancelled or invalidated preflight unexpectedly reached a detector endpoint: '+name)
    positive_strict=events(strict['positiveNonce'],'/strict-probe')
    denied_strict=events(strict['attemptNonce'],'/strict-probe')
    if len(positive_strict)!=1 or denied_strict:
        raise ValueError('Strict pending request lacks a valid positive/closed receiver control')
    route=[row for row in native['routes'] if parse_qs(urlsplit(row.get('url','')).query).get('nonce')==[strict['attemptNonce']]]
    if not route or any(row['route'].get('port')!=9 or row['route'].get('host')!='127.0.0.1' for row in route):
        raise ValueError('Actual strict-pending proxy callback was not observed closed')
    terminal=strict['actualRetryTerminal']
    if terminal['state']=='confirmed':
        accepted=events(strict['confirmedProbeNonce'],'/strict-probe')
        if len(accepted)!=1 or not terminal.get('settingsReadbackConfirmed') or not terminal.get('observedFingerprinting'):
            raise ValueError('Actual strict confirmation has no matching allowed-request control')
    elif not terminal.get('newRequestsBlocked'):
        raise ValueError('Failed real strict settings admitted requests')
    return dict(status='passed-controlled-reconciliation',
        mainDocumentAndWorkerActuallyReceived=True,actualRequestHeadersRetained=True,
        documentWorkerHttpUaSame=headers_same,
        workerHttpMatchesIndependentSdkDefault=worker[0]['headers']['userAgent']==identity['sdkDefaultUserAgent'],
        desktopWorkerUaMismatchPreserved=not headers_same,
        syntheticSensitiveHeaderPositiveControl=True,registeredSensitiveHeadersAbsent=True,
        cancelledScopeNoLaterArrival=True,redirectPositiveControl=True,registeredRedirectNoTargetArrival=True,
        lateRegistrationClosed=True,syntheticEpochPreflightInvalidation=True,productionPolicyPreflightInvalidation=True,
        strictPendingActualRequestBlocked=True,actualStrictRetryState=terminal['state'],
        actualStrictPositiveControlAvailable=terminal['state']=='confirmed',
        fullDesktopUaConsistency=False,fullFingerprintProtectionAcceptance=False,
        physicalPhoneAcceptance=False,officialChatGptSiteTested=False,releaseAcceptance=False,
        scope='One actual controlled AVD/Gecko/HTTPS invocation with independent receiver records; aliases and callback-loss fault injection are fixture-only.')

def reconcile_coverage(native,trace,service,frame_service):
    """New context observations remain separate from independent network evidence."""
    if frame_service.get('dropped')!=0:
        raise ValueError('Controlled frame receiver events were dropped')
    cases={row['case']:row for row in native['cases']};arrivals=trace['events']
    contexts_case=cases['bounded-context-api-checks'];light=contexts_case['light']['signals'];deep=contexts_case['deep']['signals']
    if 'apiContexts' in light or 'apiChecks' in light:
        raise ValueError('Ordinary observations performed unrequested deep operations')
    contexts=deep.get('apiContexts',{})
    if contexts.get('schema')!=1 or contexts.get('requested') is not True:
        raise ValueError('Explicit context API observation envelope missing')
    for name,source in [('frame','same-origin-srcdoc'),('worker','dedicated-worker')]:
        context=contexts.get(name,{})
        if context.get('source')!=source and (context.get('source')!='unavailable' or context.get('expectedSource')!=source):
            raise ValueError('Context operation source missing: '+name)
        if context.get('protectionVerified') is not False or context.get('probeVersion')!=1:
            raise ValueError('Context observation changed into a protection verdict')
        for operation in ['canvas','audio','fonts','webgl']:
            probe=context.get('probes',{}).get(operation,{})
            if probe.get('state') not in ['available','restricted','failed','uncovered'] or not probe.get('reason'):
                raise ValueError('Context API state or reason missing: '+name+'/'+operation)
            if context.get('source')=='unavailable' and probe['state']!='uncovered':
                raise ValueError('Unavailable execution context has fabricated API success')
    pinned=cases['pinned-deep-reference-lifecycle'];history=pinned['ordinaryHistoryAfterEight']
    if len(history)!=8 or pinned['comparison'].get('state')!='comparable' or not pinned['pinned']:
        raise ValueError('Fixed deep reference did not survive ordinary history eviction')
    if any(row.get('apis',{}).get('probeVersion',0)>0 for row in history):
        raise ValueError('History eviction control was not eight ordinary checks')
    control=cases['manual-service-capability-controls']
    def capability_arrival(result,server):
        nonce=result.get('nonce','')
        if not re.fullmatch('[a-f0-9]{32}',nonce):raise ValueError('Native service result nonce missing')
        found=[row for row in arrivals if row['nonce']==nonce and row['path']==BASE+'capabilities' and row['server']==server]
        if len(found)!=1 or any(found[0]['sensitive'].values()):
            raise ValueError('Service check lacks one credential-free independent receiver arrival')
        if any(row['nonce']==nonce for row in service['events']):
            raise ValueError('Capabilities request polluted document/Worker identity records')
        return found[0]
    capability_arrival(control['positive'],'detector');capability_arrival(control['faultPositive'],'fault')
    if control['positive'].get('status')!='ready' or control['faultPositive'].get('status')!='ready':
        raise ValueError('Actual protocol/TLS positive service controls absent')
    reasons={'protocol':'protocol-mismatch','capacity':'service-capacity','redirect':'service-connection-or-certificate-unavailable','oversize':'service-response-too-large','timeout':'service-timeout'}
    if [row['mode'] for row in control['faults']]!=list(reasons):raise ValueError('Expected actual service fault controls incomplete')
    for row in control['faults']:
        mode=row['mode'];result=row['result'];received=capability_arrival(result,'fault')
        if received.get('controlledResponseMode')!=mode or result.get('status')!='failed' or result.get('reason')!=reasons[mode]:
            raise ValueError('Actual service failure was hidden or misclassified: '+mode)
        if mode=='redirect' and any(item['server']=='detector' and item['nonce']==result['nonce'] for item in arrivals):
            raise ValueError('Capability redirect reached a second endpoint')
    cancelled=control['cancelledNonce']
    if any(row['nonce']==cancelled for row in arrivals):raise ValueError('Cancelled service preflight or replay reached a detector')
    if control['before']['timeOrigin']!=control['after']['timeOrigin'] or control['before']['draft']!=control['after']['draft']:
        raise ValueError('Service checks navigated or changed the source draft')
    frame_case=cases['controlled-cross-origin-frame'];nonce=frame_case['nonce'];denied=frame_case['unconsentedNonce']
    primary=[row for row in arrivals if row['server']=='detector' and row['nonce']==nonce and row['path']==BASE+'document']
    frame=[row for row in arrivals if row['server']=='frame' and row['nonce']==nonce and row['path']==BASE+'frame']
    if len(primary)!=1 or primary[0].get('diagnosticFrameOptIn') is not True or len(frame)!=1:
        raise ValueError('Explicit detector/frame receiver pair missing or frame replay admitted')
    if frame[0]['headers'].get('secFetchDest')!='iframe' or any(frame[0]['sensitive'].values()):
        raise ValueError('Independent receiver did not observe a credential-free iframe request')
    if any(row['nonce']==denied for row in arrivals):raise ValueError('Unconsented cross-origin frame reached a receiver')
    default_identity=cases['top-level-request-identity'];default_nonce=parse_qs(urlsplit(default_identity['actualDetectorUrl']).query)['nonce'][0]
    if any(row['server']=='frame' and row['nonce']==default_nonce for row in arrivals):
        raise ValueError('Ordinary identity check unexpectedly requested a cross-origin frame')
    records=frame_service['events'];matching=[row for row in records if row['nonce']==nonce and row.get('source')=='cross-origin-frame']
    if len(matching)!=1 or any(matching[0]['sensitiveHeaders'].values()):
        raise ValueError('Frame service did not retain independent source-labelled receiver evidence')
    if matching[0]['headers']['secFetchDest']!='iframe' or {key:matching[0]['headers'][key] for key in ['userAgent','acceptLanguage','secFetchDest']}!=frame[0]['headers']:
        raise ValueError('Frame server record differs from its independent wire observation')
    observed=frame_case['report']['requestIdentity']['browser']['crossOriginFrame']
    if observed.get('status')!='complete' or observed.get('nonce')!=nonce or observed.get('origin')!=FRAME_ORIGIN or observed.get('source')!='controlled-cross-origin-iframe':
        raise ValueError('Native cross-origin API report lost its distinct source binding')
    return dict(status='passed-controlled-coverage-reconciliation',contextOperationsObserved=True,
        missingContextCannotClaimSuccess=True,pinnedDeepReferenceSurvivedEightOrdinaryChecks=True,
        historyAndPinClearingAreIndependent=True,manualServiceKeptDocumentAndDraft=True,
        serviceCredentialsAbsent=True,actualServiceFailureCategoriesPreserved=True,
        serviceRedirectClosed=True,cancelledServiceScopeClosed=True,
        actualCrossOriginIframeReceived=True,ordinaryIdentityDidNotRequestIframe=True,
        unconsentedAndRetiredFrameRequestsClosed=True,fullFingerprintProtectionAcceptance=False,
        physicalPhoneAcceptance=False,officialChatGptSiteTested=False,releaseAcceptance=False,
        scope='Actual controlled AVD observations plus separately retained HTTPS receiver records. No equal-hash rule across contexts, CSP override, physical-phone acceptance or full protection attestation.')

def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--adb',required=True);parser.add_argument('--serial',choices=['emulator-5554'],default='emulator-5554');parser.add_argument('--apk',type=Path,default=ROOT/'app/build/outputs/apk/integration/app-x86_64-integration.apk');args=parser.parse_args()
    out=ROOT/'work/fingerprint-followup-audit/device';out.mkdir(parents=True,exist_ok=True)
    if (out/'runner.json').exists():raise ValueError('Preserve previous invocation; no automatic rerun')
    source=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip();tree=subprocess.check_output(['git','rev-parse','HEAD^{tree}'],cwd=ROOT,text=True).strip()
    if subprocess.check_output(['git','status','--porcelain'],cwd=ROOT,text=True).strip():raise ValueError('Exact clean committed source required')
    gradle=(ROOT/'app/build.gradle').read_text();expected=expected_build(args.apk.resolve(),source,tree,re.search(r"versionName '([^']+)'",gradle).group(1),int(re.search(r'versionCode (\d+)',gradle).group(1)))
    nonce=uuid.uuid4().hex;observations=[];deadline=time.monotonic()+300
    wrapper=dict(schema=1,status='failed',sourceCommit=source,sourceTree=tree,runId=os.environ.get('GITHUB_RUN_ID',''),runAttempt=os.environ.get('GITHUB_RUN_ATTEMPT',''),runNonce=nonce,buildIdentity=expected,fixtureInvocationCount=0,automaticRetryPerformed=False,actualAndroidFixtureAttempted=False,physicalPhoneAcceptance=False,officialChatGptSiteTested=False,fullFingerprintProtectionAcceptance=False,fullDesktopUaConsistency=False,releaseAcceptance=False,publicNetworkTraffic=False,observations=observations)
    def adb(*parts,check=True,cleanup=False):
        remaining=deadline-time.monotonic()
        if remaining<=0 and not cleanup:raise TimeoutError('Single300s diagnostic deadline expired')
        command=[args.adb,'-s',args.serial,*parts];index=len(observations)+1
        try:
            result=subprocess.run(command,capture_output=True,timeout=10 if cleanup else min(25,remaining));stdout,stderr,code=result.stdout,result.stderr,result.returncode
        except subprocess.TimeoutExpired as error:stdout,stderr,code=error.stdout or b'',error.stderr or b'',None
        row=dict(index=index,command=command,returnCode=code,cleanupOnly=cleanup,atUnixMs=int(time.time()*1000),atMonotonicNs=time.monotonic_ns(),streams={})
        for name,raw in [('stdout',stdout),('stderr',stderr)]:
            path=out/('adb-%04d-%s.raw'%(index,name));path.write_bytes(raw);row['streams'][name]=dict(path=path.name,bytes=len(raw),sha256=sha(path))
        observations.append(row)
        if check and code!=0:raise RuntimeError('Actual ADB command failed at observation '+str(index))
        return stdout.decode('utf-8',errors='strict')
    process=None;native=None;error=None
    try:
        with tempfile.TemporaryDirectory(prefix='fingerprint-followup-tls-') as temporary:
            temp=Path(temporary);subprocess.run(['openssl','req','-x509','-newkey','rsa:2048','-nodes','-sha256','-days','1','-subj','/CN=10.0.2.2','-addext','subjectAltName=IP:10.0.2.2','-keyout',str(temp/'key.pem'),'-out',str(temp/'cert.pem')],check=True,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
            der=subprocess.check_output(['openssl','x509','-in',str(temp/'cert.pem'),'-outform','DER']);wrapper['temporaryCertificateSha256']=hashlib.sha256(der).hexdigest();wrapper['temporaryCertificateScope']='Test-only exact10.0.2.2 origins; no production TLS change, key/cert files never uploaded'
            process=subprocess.Popen(['node',str(ROOT/'tests/gecko/assets/fingerprint-followups.cjs'),str(temp/'key.pem'),str(temp/'cert.pem'),str(out),nonce],stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True)
            ready,_,_=select.select([process.stdout],[],[],10)
            if not ready or json.loads(process.stdout.readline())!=dict(ready=True,ports=[9889,9890,9891,9892],runNonce=nonce):raise ValueError('Actual independent HTTPS servers did not start')
            adb('shell','am','force-stop',PACKAGE);adb('shell','pm','clear',PACKAGE)
            before=adb('exec-out','content','read','--uri','content://'+PACKAGE+'.evidence/build-identity');verify_installed(json.loads(before),expected);wrapper['installedBeforeSha256']=hashlib.sha256(before.encode()).hexdigest()
            uid=adb('shell','cmd','package','list','packages','-U',PACKAGE);matches=re.findall(r'^package:'+re.escape(PACKAGE)+r' uid:(\d+)\s*$',uid,re.M)
            if len(matches)!=1:raise ValueError('Exact owned integration UID missing')
            wrapper['packageUid']=int(matches[0]);adb('logcat','-c');wrapper['actualAndroidFixtureAttempted']=True;wrapper['fixtureInvocationCount']=1
            adb('shell','am','start','-W','-n',PACKAGE+'/local.pocketchat.FingerprintFollowupIntegrationActivity','--es','sourceCommit',source,'--es','runNonce',nonce,'--es','origin',ORIGIN,'--es','redirectOrigin',REDIRECT_ORIGIN,'--es','frameOrigin',FRAME_ORIGIN,'--es','faultOrigin',FAULT_ORIGIN)
            while time.monotonic()<deadline:
                raw=adb('exec-out','content','read','--uri','content://'+PACKAGE+'.evidence/fingerprint-followups',check=False)
                if raw.lstrip().startswith('{'):
                    value=json.loads(raw)
                    if value.get('runNonce')==nonce and value.get('status') in ['completed','failed']:
                        native=value;(out/'native-report.json').write_bytes(raw.encode());break
                time.sleep(.4)
            if native is None:raise TimeoutError('No terminal current-invocation native report')
            if native['sourceCommit']!=source or native['sourceTree']!=tree:raise ValueError('Native source/tree mismatch')
            verify_installed(native['buildIdentity'],expected)
            if native.get('actualAndroidExecution') is not True or native.get('actualGeckoExecution') is not True:raise ValueError('Actual Android/Gecko observations missing')
            if native['status']!='completed':raise ValueError('Native checks did not complete: '+str(native.get('error','unknown')))
            if [row['case'] for row in native['cases']]!=CASES or not native['checks'] or not all(row['pass'] is True for row in native['checks']):raise ValueError('Expected actual native case/check set incomplete')
            if any(native.get(key)!=0 for key in ['eventDrops','routeDrops','normalizationDrops']):raise ValueError('Native original evidence truncated')
            if native.get('preflightDriverDrops')!=0:raise ValueError('Native preflight driver evidence truncated')
            after=adb('exec-out','content','read','--uri','content://'+PACKAGE+'.evidence/build-identity');verify_installed(json.loads(after),expected);wrapper['installedAfterSha256']=hashlib.sha256(after.encode()).hexdigest()
            wrapper.update(status='completed',actualAndroidExecution=True,actualGeckoExecution=True,nativeReportSha256=sha(out/'native-report.json'),actualNativeChecks=len(native['checks']))
    except BaseException as failure:
        error=failure;wrapper.update(status='failed',errorType=type(failure).__name__,error=str(failure))
    finally:
        try:wrapper['finalLogcat']=adb('logcat','-d','-s','PocketFingerprintFollowup:I','AndroidRuntime:E','*:S',check=False,cleanup=True)
        except Exception as failure:wrapper['logcatError']=type(failure).__name__
        try:
            if 'packageUid' in wrapper:
                current=adb('shell','cmd','package','list','packages','-U',PACKAGE,cleanup=True);found=re.findall(r'^package:'+re.escape(PACKAGE)+r' uid:(\d+)\s*$',current,re.M)
                if found!=[str(wrapper['packageUid'])]:raise ValueError('Refuse cleanup of foreign/replaced package UID')
                adb('shell','am','force-stop',PACKAGE,cleanup=True);wrapper['ownedPackageCleanup']=True
        except Exception as failure:wrapper.update(status='failed',cleanupError=type(failure).__name__+': '+str(failure))
        if process is not None:
            process.terminate()
            try:stdout,stderr=process.communicate(timeout=8)
            except subprocess.TimeoutExpired:process.kill();stdout,stderr=process.communicate(timeout=5)
            (out/'server.stdout.log').write_text(stdout);(out/'server.stderr.log').write_text(stderr);wrapper['serverExitCode']=process.returncode
            if process.returncode!=0:wrapper.update(status='failed',serverError='Independent server shutdown was abnormal')
        try:
            trace=json.loads((out/'server-trace.json').read_text());service=json.loads((out/'identity-server.json').read_text());frame_service=json.loads((out/'frame-server.json').read_text())
            for stem,document in [('server-trace',trace),('identity-server',service),('frame-server',frame_service)]:
                lines=[json.loads(line) for line in (out/(stem+'.jsonl')).read_text().splitlines()]
                if lines!=document['events']:raise ValueError('Original JSON/JSONL observer records differ: '+stem)
                wrapper[stem+'Sha256']=sha(out/(stem+'.json'));wrapper[stem+'JsonlSha256']=sha(out/(stem+'.jsonl'))
            if wrapper['status']=='completed':
                wrapper['controlReconciliation']=reconcile(native,trace,service)
                wrapper['coverageReconciliation']=reconcile_coverage(native,trace,service,frame_service)
        except Exception as failure:wrapper.update(status='failed',reconciliationError=type(failure).__name__+': '+str(failure))
        (out/'runner.json').write_text(json.dumps(wrapper,indent=2)+'\n')
    if wrapper['status']!='completed':raise RuntimeError('Fingerprint followup diagnostic incomplete; retain current original runner.json') from error
    print(json.dumps(dict(status='completed',sourceCommit=source,nativeChecks=wrapper['actualNativeChecks'],nativeReportSha256=wrapper['nativeReportSha256'],fullFingerprintProtectionAcceptance=False,releaseAcceptance=False)))

if __name__=='__main__':main()
