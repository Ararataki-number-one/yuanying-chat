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
BASE='/pocketchat-identity/v1/'
CASES=['standard-source-control','manual-api-checks','credential-and-redirect-controls',
       'top-level-request-identity','controlled-diagnostic-page-recovery','nonempty-draft-refusal','late-registration-cancellation',
       'synthetic-epoch-preflight-invalidation','browser-policy-preflight-invalidation',
       'strict-native-receipt-loss-control']

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
            if not ready or json.loads(process.stdout.readline())!=dict(ready=True,ports=[9889,9890],runNonce=nonce):raise ValueError('Actual independent HTTPS servers did not start')
            adb('shell','am','force-stop',PACKAGE);adb('shell','pm','clear',PACKAGE)
            before=adb('exec-out','content','read','--uri','content://'+PACKAGE+'.evidence/build-identity');verify_installed(json.loads(before),expected);wrapper['installedBeforeSha256']=hashlib.sha256(before.encode()).hexdigest()
            uid=adb('shell','cmd','package','list','packages','-U',PACKAGE);matches=re.findall(r'^package:'+re.escape(PACKAGE)+r' uid:(\d+)\s*$',uid,re.M)
            if len(matches)!=1:raise ValueError('Exact owned integration UID missing')
            wrapper['packageUid']=int(matches[0]);adb('logcat','-c');wrapper['actualAndroidFixtureAttempted']=True;wrapper['fixtureInvocationCount']=1
            adb('shell','am','start','-W','-n',PACKAGE+'/local.pocketchat.FingerprintFollowupIntegrationActivity','--es','sourceCommit',source,'--es','runNonce',nonce,'--es','origin',ORIGIN,'--es','redirectOrigin',REDIRECT_ORIGIN)
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
            trace=json.loads((out/'server-trace.json').read_text());service=json.loads((out/'identity-server.json').read_text())
            for stem,document in [('server-trace',trace),('identity-server',service)]:
                lines=[json.loads(line) for line in (out/(stem+'.jsonl')).read_text().splitlines()]
                if lines!=document['events']:raise ValueError('Original JSON/JSONL observer records differ: '+stem)
                wrapper[stem+'Sha256']=sha(out/(stem+'.json'));wrapper[stem+'JsonlSha256']=sha(out/(stem+'.jsonl'))
            if wrapper['status']=='completed':wrapper['controlReconciliation']=reconcile(native,trace,service)
        except Exception as failure:wrapper.update(status='failed',reconciliationError=type(failure).__name__+': '+str(failure))
        (out/'runner.json').write_text(json.dumps(wrapper,indent=2)+'\n')
    if wrapper['status']!='completed':raise RuntimeError('Fingerprint followup diagnostic incomplete; retain current original runner.json') from error
    print(json.dumps(dict(status='completed',sourceCommit=source,nativeChecks=wrapper['actualNativeChecks'],nativeReportSha256=wrapper['nativeReportSha256'],fullFingerprintProtectionAcceptance=False,releaseAcceptance=False)))

if __name__=='__main__':main()
