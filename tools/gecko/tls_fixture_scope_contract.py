"""Typed integration scope only: never native admission or evidence of coldness."""
from tls_acceptance_contract import require,equal,integer,token
from tls_acceptance_server import CASE_SPECS
SCOPE_FIELDS=set('schema kind phase sourceCommit sourceTree apkSha256 sdkRunId sdkRunAttempt runNonce claimNonce slot purpose createdAtElapsed identity timezoneDesired timezoneRevision timezoneMissingBefore systemSeeded retainedBytesPreserved scopeOnly nativeAdmissionGranted coldRuntimeProvenByScope caseNonce activityClass processName recordReadOnly'.split())

def validate_manual_scope(value,*,spec,binding,run,source,tree,identity):
    slot=spec[1];scope=value.get('manualScope');sdk=identity['sdkBuildIdentity'];purpose='local.pocketchat.GeckoTlsAcceptanceActivity$Profile'+str(slot)
    require(type(scope) is dict and set(scope)==SCOPE_FIELDS,'exact explicit TLS manual setup scope')
    expected=dict(schema=1,kind='explicit-manual-tls-fixture',phase='armed',sourceCommit=source,sourceTree=tree,apkSha256=identity['apkSha256'],sdkRunId=sdk['runId'],sdkRunAttempt=sdk['runAttempt'],runNonce=run,slot=slot,purpose=purpose,caseNonce=binding['caseNonce'],activityClass=purpose,processName='local.pocketchat.test:profile'+str(slot),scopeOnly=True,nativeAdmissionGranted=False,coldRuntimeProvenByScope=False,recordReadOnly=True)
    for k,v in expected.items():require(equal(scope.get(k),v),'manual scope installed/purpose binding '+k)
    require(token(scope.get('claimNonce')) and integer(scope.get('createdAtElapsed')) and integer(scope.get('timezoneRevision'),1),'bounded manual scope identity')
    require(equal(scope.get('timezoneDesired'),dict(schema=2,engine='gecko',mode='system',zoneId='')),'explicit current schema manual system only')
    policy=value['tlsPolicy'];owner=dict(slot=slot,generation=policy['environmentGeneration'],environmentId=policy['environmentId'])
    require(equal(scope.get('identity'),owner),'same production environment scope owner')
    missing=scope.get('timezoneMissingBefore');require(type(missing) is bool and scope.get('systemSeeded') is missing and scope.get('retainedBytesPreserved') is (not missing),'missing-only manual seed and retained exact bytes')
    return scope['claimNonce']

def validate_manual_cross(entries,checks,*,run,source):
    wanted=[s for s in CASE_SPECS if not s[6]]
    require(type(checks) is list and len(checks)==len(wanted),'independent process absence per cold scope')
    by_label={e['label']:e for e in entries}
    for row,spec in zip(checks,wanted):
        reused=spec[0]=='concurrent-default-tls12'
        expected=dict(label=spec[0],slot=spec[1],sourceCommit=source,runNonce=run,shellUid=2000,processAbsent=True,ownedClearObserved=True,prepared=True,claimNonce=by_label[spec[0]]['device']['manualScope']['claimNonce'],preparationBeforeLabel='concurrent-strict-tls13' if reused else spec[0],allListedFixtureProcessesAbsentAtPreparation=True,scopeProcessesChecked=['local.pocketchat.test']+['local.pocketchat.test:profile'+str(slot) for slot in range(1,8)],scopeReusedBeforeStart=reused,scopeInspectionVerified=reused,reuseAtLabel=spec[0] if reused else '')
        require(equal(row,expected),'actual shell cold preparation/order and separate readonly concurrent inspection')
    claims={};latest={}
    for entry,spec in zip(entries,CASE_SPECS):
        scope=entry['device']['manualScope'];claim=scope['claimNonce'];slot=spec[1]
        if spec[6]:require(latest.get(slot)==claim,'warm resample must retain exact explicit scope claim')
        else:
            require(claim not in claims,'cold scope cannot reuse another boot claim');claims[claim]=spec[0];latest[slot]=claim
    return dict(coldScopeCount=len(wanted),warmScopeCount=len(CASE_SPECS)-len(wanted),scopeOnly=True,nativeAdmissionGranted=False,coldRuntimeProvenByScope=False)
