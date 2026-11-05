#!/usr/bin/env python3
"""Reject incomplete, overclaimed or differently bound real-Android fingerprint evidence."""
import argparse
import hashlib
import json
from pathlib import Path,PurePosixPath
import re
import sys

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from gecko.profile_invocation_contract import verify_installed
from gecko.sdk_identity_contract import source_bytes,strict_json,_typed_equal,SDK_FIELDS

ORIGINS={'https://fp-a.pocketchat.test','https://fp-b.pocketchat.test'}
CHROMIUM_REQUIRED={'chromium.production-ui','canvas.same-origin-reload','chromium.generic-address-ui','selftest.real-observation-dispatched','selftest.actual-stale-callback-rejected','selftest.stale-document-rejected','selftest.stale-receipt-rejected','canvas.policy-edit-retains-environment-seed','canvas.independent-saved-environment','canvas.independent-environment-output','selftest.current-document-observed'}
for prefix in ('primary','desktop'):
    CHROMIUM_REQUIRED.update(prefix+'.'+suffix for suffix in ('features','native-metadata','native-tls-certificate','first-inline','native-js-ua','canvas','frames','no-gpt-hotpath','worker-explicitly-unprotected','https-native-hints'))
GECKO_REQUIRED={'gecko.production-surface','gecko.address-dialog','gecko.generic-address-ui','gecko.no-gpt-hotpath','gecko.gpt-driver-rejected'}
SOURCE_INPUTS={'tools/browser/fingerprint_fixture_server.py','tools/browser/run_fingerprint_integration.py','tools/browser/check_fingerprint_evidence.py','tests/gecko/AndroidManifest.xml','tests/gecko/BrowserFingerprintIntegrationActivity.java','tests/gecko/BrowserFingerprintFixture.java','tests/gecko/BrowserFingerprintEvidenceProvider.java','tests/gecko/IntegrationBuildIdentity.java','app/src/main/java/local/pocketchat/NormalCaretSdkReceipt.java','tests/gecko/assets/browser-fingerprint-page.js','tests/gecko/res/xml/network_security.xml','app/build.gradle','app/src/main/AndroidManifest.xml','app/src/main/res/xml/network_security.xml','.github/workflows/browser-2_1-acceptance.yml','app/src/main/java/local/pocketchat/BrowserActivity.java','app/src/main/java/local/pocketchat/ChromiumFingerprintRuntime.java','app/src/main/java/local/pocketchat/ChromiumFingerprintSpec.java','app/src/main/java/local/pocketchat/ChromiumFingerprintStore.java','app/src/main/java/local/pocketchat/GeckoAddressUi.java','app/src/main/java/local/pocketchat/GeckoNavigationPolicy.java','app/src/main/java/local/pocketchat/MainActivity.java','app/src/main/java/local/pocketchat/ChatSession.java','app/src/main/java/local/pocketchat/GeckoWebView.java','app/src/main/assets/chromium-fingerprint.js','app/src/main/assets/gecko/content.js','app/src/main/assets/page-driver.js','app/src/main/assets/attachment-driver.js'}


def require(value,message):
    if not value:raise ValueError('Browser fingerprint acceptance: '+message)


def checks(result,required):
    rows=result.get('checks');require(type(rows) is list and rows,'checks missing')
    require(all(type(row) is dict and row.get('pass') is True and type(row.get('id')) is str for row in rows),'check failed or malformed')
    names=[row['id'] for row in rows];require(len(names)==len(set(names)) and required<=set(names),'required checks missing or duplicated')


def unclaimed(value):
    require(all(value.get(key) is False for key in ('fingerprintProtectionVerified','workerCoverageVerified','serviceWorkerCoverageVerified')),'complete/worker protection must not be claimed')


def proxy_scope(result,https=False):
    fixture=result.get('fixture',{});require(type(fixture) is dict and type(fixture.get('upstreamConnections')) is int and fixture['upstreamConnections']==0 and fixture.get('forwardingImplemented') is False and fixture.get('certificateExceptionUsed') is False,'synthetic no-forwarding/no-TLS-exception boundary differs')
    requests=fixture.get('requests');require(type(requests) is list and 0<len(requests)<=200,'controlled request receipts missing')
    require(all(type(r) is dict and r.get('origin') in ORIGINS|{o.replace('https:','http:') for o in ORIGINS} and r.get('method')=='GET' and r.get('path') in ('/document','/frame','/hints','/worker.js','/favicon.ico') and type(r.get('tls')) is bool and r['tls']==r['origin'].startswith('https:') for r in requests),'request escapes controlled origins')
    if https:
        require(type(fixture.get('tlsConnections')) is int and fixture['tlsConnections']>0,'actual native TLS connections missing')
        for key in ('caPemSha256','leafDerSha256'):require(re.fullmatch('[0-9a-f]{64}',str(fixture.get(key,''))),'trust hash missing')
    return requests


def early(value,guard=True):
    require(type(value) is dict and value.get('firstInline') is True and value.get('complete') is True and value.get('secure') is True and value.get('origin') in ORIGINS and not value.get('error'),'HTTPS first-inline observation missing')
    require(type(value.get('documentId')) is str and 0<len(value['documentId'])<=128,'document incarnation missing')
    require(value.get('documentGuard') is guard and value.get('auditAvailable') is guard,'document-start protection absent')
    require(all(type(value.get(key)) is str and re.fullmatch('[0-9a-f]{8}',value[key]) for key in ('canvas','baseline','repeat')) and value['canvas']==value['repeat'] and value['canvas']!=value['baseline'],'stable perturbed Canvas result missing')


def structured_brands(raw):
    require(type(raw) is str and len(raw)<=2048,'native UA-CH brand header missing')
    entries=re.findall(r'"([^"\\]+)";v="([^"\\]+)"',raw)
    require(entries and len(entries)==len(set(entries)),'native UA-CH brands malformed')
    require(', '.join('"'+a+'";v="'+b+'"' for a,b in entries)==raw,'native UA-CH brands not a structured list')
    return dict(entries)


def validate_host_trust(report,results):
    host=report.get('hostTls');require(type(host) is dict,'current ephemeral host TLS evidence missing')
    require(host.get('ephemeral') is True and host.get('privateMaterialLocation')=='host-tmp-only' and host.get('privateMaterialExported') is False and host.get('privateMaterialRemoved') is True,'private material must remain ephemeral host /tmp only')
    require(host.get('opensslChainVerified') is True and host.get('hostnameVerified')==['fp-a.pocketchat.test','fp-b.pocketchat.test'] and host.get('certificateExceptionUsed') is False,'native-valid public certificate chain required')
    require(host.get('guestPort')==18765 and host.get('reverseRemoved') is True,'bounded guest reverse transport or cleanup missing')
    for key in ('caPemSha256','leafDerSha256'):require(type(host.get(key)) is str and re.fullmatch('[0-9a-f]{64}',host[key]),'current public certificate hash missing')
    identity=report.get('expectedBuildIdentity',{});sdk=identity.get('sdkBuildIdentity',{})
    expected=dict(sourceCommit=report.get('sourceCommit'),sourceTree=report.get('sourceTree'),runNonce=report.get('runNonce'),integrationApkSha256=identity.get('apkSha256'),sdkRunId=sdk.get('runId'),sdkRunAttempt=sdk.get('runAttempt'))
    require(_typed_equal(host.get('binding'),expected),'host source/APK/SDK/invocation binding differs')
    installation=host.get('trustInstallation',{});subject=host.get('subjectHashOld')
    require(type(subject) is str and re.fullmatch('[0-9a-f]{8}',subject),'public CA store subject hash missing')
    require(installation.get('method')=='domain-scoped-user-ca' and type(installation.get('androidUser')) is int and installation['androidUser']==0,'exact test-domain user CA method required')
    require(all(installation.get(key) is True for key in ('adbRoot','selinuxEnforcing','installedPublicCaBytesMatch','appForceStoppedAfterInstall','removedAfterExecution')),'native CA installation/readback/cleanup proof incomplete')
    require(installation.get('ownerAndMode')=='644:1000:1000' and type(installation.get('selinuxContext')) is str and re.fullmatch(r'u:object_r:(?!unlabeled)[a-zA-Z0-9_]+:s0',installation['selinuxContext']),'native CA owner/mode/SELinux proof missing')
    require(installation.get('subjectHashOld')==subject and installation.get('storePath')=='/data/misc/user/0/cacerts-added/'+subject+'.0' and installation.get('publicCaPemSha256')==host['caPemSha256'] and installation.get('expectedLeafDerSha256')==host['leafDerSha256'],'public CA store/hash binding differs')
    for engine,result in results.items():
        fixture=result.get('fixture',{});require(fixture.get('engine')==engine and _typed_equal(fixture.get('binding'),expected),'per-engine host source/APK/invocation epoch differs')
        require(fixture.get('caPemSha256')==host['caPemSha256'] and fixture.get('leafDerSha256')==host['leafDerSha256'] and fixture.get('trustMethod')=='domain-scoped-user-ca','engine host trust differs')
        require(type(fixture.get('accepted')) is int and type(fixture.get('requests')) is list and fixture['accepted']==len(fixture['requests'])>0,'fresh per-engine requests missing')
    return host


def validate_behavior(report,source,reader=source_bytes):
    require(type(report) is dict and report.get('schema')==1 and report.get('status')=='passed' and report.get('sourceCommit')==source,'successful exact-source report required')
    require(type(report.get('sourceTree')) is str and re.fullmatch('[0-9a-f]{40}',report['sourceTree']),'source tree missing')
    nonce=report.get('runNonce');require(type(nonce) is str and re.fullmatch('[0-9a-f]{32}',nonce),'fresh invocation required')
    require(report.get('executionInputsUnchanged') is True,'execution inputs changed')
    require(all(report.get(key) is True for key in ('actualAndroidExecution','actualAndroidWebViewExecution','actualGeckoExecution')),'both actual Android engines required')
    require(all(report.get(key) is False for key in ('actualDesktopChromiumExecution','actualPublicWebsiteExecution','actualDevicePerformanceMeasurement')),'execution scope differs');unclaimed(report)
    results=report.get('results');require(type(results) is dict and set(results)=={'chromium','gecko'},'both engine reports required')
    for engine,required in [('chromium',CHROMIUM_REQUIRED),('gecko',GECKO_REQUIRED)]:
        value=results[engine];require(type(value) is dict and value.get('engine')==engine and value.get('status')=='passed' and value.get('stage')=='complete' and not value.get('failure') and value.get('sourceCommit')==source and value.get('runNonce')==nonce,'engine report stale, incomplete or failed')
        require(value.get('actualAndroidExecution') is True and value.get('actualAndroidWebViewExecution') is (engine=='chromium') and value.get('actualGeckoExecution') is (engine=='gecko'),'engine execution differs')
        require(all(value.get(key) is False for key in ('actualPublicWebsiteExecution','actualDevicePerformanceMeasurement')),'engine scope differs');checks(value,required)
    chromium=results['chromium'];unclaimed(chromium);require(chromium.get('uaChNetworkVerified') is True,'actual HTTPS UA-CH required')
    selftest=chromium.get('currentPageSelfTest',{});require(selftest.get('schema')==1 and selftest.get('scope')=='document-start-frames' and selftest.get('fingerprintProtectionVerified') is False and selftest.get('fields',{}).get('canvas',{}).get('state')=='page-observed','current live-document Canvas self-test missing')
    stale=chromium.get('staleCallbackProof',{});require(stale.get('actualCallback') is True and stale.get('staleBinding') is True and stale.get('receiptUnchanged') is True and type(stale.get('callbacks')) is int and stale['callbacks']==1,'actual stale JavaScript callback rejection missing')
    trust=validate_host_trust(report,results)
    requests=proxy_scope(chromium,True);proxy_scope(results['gecko'])
    setups=chromium.get('nativeSetups');samples=chromium.get('samples')
    require(type(setups) is list and [s.get('case') for s in setups]==['primary','desktop'],'both native policies required')
    require(all(setups[0].get(key)==setups[1].get(key) for key in ('providerPackage','providerVersion','chromiumVersion')),'provider changed between current policy observations')
    require(type(samples) is list and [s.get('case') for s in samples]==['primary','reload','desktop','independent-environment-policy'],'all observed document cases required')
    for index,(label,desktop) in enumerate([('primary',False),('desktop',True)]):
        setup=setups[index];sample=samples[index*2];e=sample.get('early');early(e)
        require(setup.get('engine')=='chromium' and setup.get('features')=={'documentStart':True,'userAgentMetadata':True} and setup.get('documentStartRegistered') is True,'native feature gates missing')
        version=setup.get('chromiumVersion');require(type(version) is str and re.fullmatch(r'\d+\.\d+\.\d+\.\d+',version) and int(version.split('.')[0])>=124,'actual Chromium 124+ required')
        require(type(setup.get('providerPackage')) is str and bool(setup['providerPackage']) and type(setup.get('providerVersion')) is str and bool(setup['providerVersion']),'actual provider identity missing')
        require(setup.get('observedLeafDerSha256')==trust['leafDerSha256'],'actual native certificate differs from current host TLS leaf')
        native=setup.get('nativeReadback');require(type(native) is dict and _typed_equal(native,setup.get('nativeRequested')) and native.get('mobile') is (not desktop),'native metadata readback differs')
        require(setup.get('requested',{}).get('engine')=='chromium' and setup['requested'].get('protection')=='protected' and setup['requested'].get('canvas') is True and setup['requested'].get('display')==('desktop' if desktop else 'mobile'),'native requested policy differs')
        require(e.get('ua')==setup.get('nativeUserAgent') and ('Chrome/'+version in e['ua'] or 'Chromium/'+version in e['ua']),'native request/JS version differs')
        require(type(e.get('low')) is dict and type(e.get('high')) is dict and e['low'].get('mobile') is (not desktop) and e['low'].get('platform')==native.get('platform'),'JS UA metadata differs')
        require(e['high'].get('architecture')==native.get('architecture') and e['high'].get('model')==native.get('model') and e['high'].get('platformVersion')==native.get('platformVersion') and e['high'].get('bitness')==('' if native.get('bitness')==0 else str(native.get('bitness'))),'JS high-entropy metadata differs')
        require(type(native.get('brands')) is list and {b['brand']:b['majorVersion'] for b in native['brands']}=={b['brand']:b['version'] for b in e['low']['brands']} and {b['brand']:b['fullVersion'] for b in native['brands']}=={b['brand']:b['version'] for b in e['high']['fullVersionList']},'native/JS UA-CH brand versions differ')
        if desktop:require(native.get('platform')=='Linux' and native.get('architecture')=='x86' and native.get('bitness')==64 and native.get('model')==native.get('platformVersion')=='' and '(X11; Linux x86_64)' in e['ua'],'desktop native request identity differs')
        frames=sample.get('frames');require(type(frames) is list and len(frames)==2 and {f.get('origin') for f in frames}==ORIGINS,'same/cross-origin frames missing')
        for frame in frames:
            early(frame);require(frame.get('ua')==e['ua'],'frame native UA differs');require((frame['canvas']==e['canvas']) is (frame['origin']==e['origin']),'Canvas origin partition differs')
        require(e.get('gpt')=={'reply':'undefined','performance':'undefined'},'ChatGPT-only hot path present on ordinary Chromium site')
        worker=e.get('worker',{});sw=e.get('serviceWorker',{});require(worker.get('actualExecution') is True and worker.get('protected') is False and worker.get('documentGuard') is False and worker.get('auditAvailable') is False and sw.get('actualExecution') is False and sw.get('protected') is False and sw.get('scope')=='unsupported' and e.get('workerCoverageVerified') is False and e.get('serviceWorkerCoverageVerified') is False,'unsupported Worker/SW scope falsely claimed')
        candidates=[r for r in requests if r.get('origin')==e['origin'] and r.get('path')=='/hints' and r.get('tls') is True and r.get('user-agent')==e['ua'] and r.get('sec-ch-ua-mobile')==('?0' if desktop else '?1')]
        match=False
        for request in candidates:
            if all(request.get(header)==json.dumps(e[section][field],ensure_ascii=False,separators=(',',':')) for header,section,field in [('sec-ch-ua-platform','low','platform'),('sec-ch-ua-platform-version','high','platformVersion'),('sec-ch-ua-model','high','model'),('sec-ch-ua-arch','high','architecture'),('sec-ch-ua-bitness','high','bitness')]):
                low=structured_brands(request.get('sec-ch-ua'));high=structured_brands(request.get('sec-ch-ua-full-version-list'))
                if low=={row['brand']:row['version'] for row in e['low']['brands']} and high=={row['brand']:row['version'] for row in e['high']['fullVersionList']}:match=True
        require(match,'server-observed HTTPS UA-CH/UA differs from first-inline native JS')
        unsupported=setup.get('unsupported',{});require(unsupported.get('worker')=='unsupported' and unsupported.get('serviceWorker')=='unsupported' and setup.get('workerCoverageVerified') is False and setup.get('fingerprintProtectionVerified') is False,'native unsupported coverage missing')
    original=samples[0]['early'];reload=samples[1].get('early');independent=samples[3].get('early');early(reload);early(independent)
    require(reload['documentId']!=original['documentId'] and reload['canvas']==original['canvas']==samples[2]['early']['canvas'],'reload/policy edit changed stable Canvas identity or reused old document')
    require(independent['canvas']!=original['canvas'],'independent saved environment policy not independent')
    hashes=report.get('sourceFiles');require(type(hashes) is dict and SOURCE_INPUTS<=set(hashes),'all source/resource hashes required')
    for path,sha in hashes.items():
        require(type(path) is str and str(PurePosixPath(path))==path and not PurePosixPath(path).is_absolute() and '..' not in PurePosixPath(path).parts and '\\' not in path and '\x00' not in path and type(sha) is str and re.fullmatch('[0-9a-f]{64}',sha),'unsafe source hash record')
        require(hashlib.sha256(reader(source,path)).hexdigest()==sha,'selected-source bytes differ: '+path)
    return results


def verify_fingerprint_evidence(directory,source,expected,reader=source_bytes):
    raw=(Path(directory)/'browser-fingerprint-results.json').read_bytes();require(0<len(raw)<=2*1024*1024,'bounded fingerprint report required')
    report=strict_json(raw);results=validate_behavior(report,source,reader)
    require(expected.get('sourceCommit')==source and report.get('sourceTree')==expected.get('sourceTree'),'reference source/tree differs')
    identities=[report.get('expectedBuildIdentity',{}),*(result.get('buildIdentity',{}) for result in results.values())]
    for installed in identities:
        require(type(installed) is dict,'installed identity missing')
        for key in ('schema','package','sourceCommit','sourceTree','dirtySource','version','versionCode','sdkCoordinate','apkSha256','apkBytes','buildStampSha256','sdkBuildIdentity')+SDK_FIELDS:
            require(_typed_equal(installed.get(key),expected.get(key)),'typed build/source/APK/SDK identity differs: '+key)
    for installed in identities:verify_installed(installed,expected)
    sdk=expected['sdkBuildIdentity']
    return dict(sourceCommit=source,sourceTree=expected['sourceTree'],integrationApkSha256=expected['apkSha256'],runId=sdk['runId'],runAttempt=sdk['runAttempt'],reportSha256=hashlib.sha256(raw).hexdigest(),actualAndroidExecution=True,actualAndroidWebViewExecution=True,actualGeckoExecution=True,uaChNetworkVerified=True,checkCount=sum(len(value['checks']) for value in results.values()),fingerprintProtectionVerified=False,workerCoverageVerified=False,serviceWorkerCoverageVerified=False,scope='Native UA/UA-CH, first-inline document/frame Canvas and origin/environment-policy separation on controlled domain-scoped user-CA HTTPS with ephemeral host-only keys; both generic URL UIs and inactive ChatGPT-only drivers. Dedicated Worker observed unprotected. ServiceWorker unsupported/unexecuted. No whole-fingerprint, public-site or phone-performance claim.')


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--directory',type=Path,required=True);p.add_argument('--source',required=True);p.add_argument('--reference',type=Path,required=True);p.add_argument('--output',type=Path);a=p.parse_args();expected=json.loads(a.reference.read_text())['eventTransport']['buildIdentity'];result=verify_fingerprint_evidence(a.directory,a.source,expected)
    if a.output:a.output.parent.mkdir(parents=True,exist_ok=True);a.output.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps(result,ensure_ascii=False))


if __name__=='__main__':main()
