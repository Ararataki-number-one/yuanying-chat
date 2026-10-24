"""Strict replay of controlled Android framework binding evidence; no device code."""
import hashlib
import json
import math
import re

try:
    from .integration_event_contract import decode_event
    from .profile_invocation_contract import verify_installed
except ImportError:
    from integration_event_contract import decode_event
    from profile_invocation_contract import verify_installed

PACKAGE='local.pocketchat.test'
ACTION='networkClientBinding'
ACTIVITY_PROCESS=PACKAGE+':transport_binding_fixture'
SERVICE_PROCESS=PACKAGE+':transport_binding_services'
CLASS='local.pocketchat.NetworkClientBindingIntegrationActivity'
MISSING='local.pocketchat.AbsentNetworkClientBindingFixture'
CHECKS=(
 'Fixture runs in its separate integration process',
 'Fixture process owns the installed package UID',
 'Actual null binding releases original caller before its ten second deadline',
 'First real bind was accepted for the private null Service',
 'Null callback releases the captured production gate',
 'Null owner is actually unbound once through Android',
 'Private Service records a real null onBind in another process',
 'Actual production callback journal contains exactly one owned null binding',
 'Next ordinary production call receives the real Messenger reply',
 'Next demand binds a distinct owner and gate without automatic retry',
 'Explicit detach unbinds only the Messenger owner once',
 'Service received original snapshot and detach command envelopes',
 'Real Messenger command sender UID matches the owned package',
 'Both actual bind attempts have one successful framework unbind',
 'Missing-component fault names an absent component in this test package',
 'Real missing-component bind returns false and wakes its caller',
 'False-return framework dispatcher is released exactly once',
 'Actual missing bind rejection is distinct from a null callback',
)

def require(ok,message):
    if not ok:raise ValueError('Android client binding: '+message)

def integer(value,minimum=0):return type(value) is int and minimum<=value<=2**63-1

def unique(pairs):
    value={}
    for key,item in pairs:
        require(key not in value,'duplicate raw JSON field');value[key]=item
    return value

def constant(value):raise ValueError('Nonfinite JSON: '+value)

def finite(value):
    number=float(value);require(math.isfinite(number),'nonfinite JSON number');return number

def parse(raw):return json.loads(raw,object_pairs_hook=unique,parse_constant=constant,parse_float=finite)

def same(left,right):
    if type(left) is not type(right):return False
    if isinstance(left,dict):return left.keys()==right.keys() and all(same(left[key],right[key]) for key in left)
    if isinstance(left,list):return len(left)==len(right) and all(same(a,b) for a,b in zip(left,right))
    return left==right

def raw_value(proof):
    require(isinstance(proof,dict) and set(proof)=={'rawUtf8','utf8Bytes','sha256'},'raw observation structure')
    require(isinstance(proof['rawUtf8'],str),'raw UTF8 missing');data=proof['rawUtf8'].encode('utf-8')
    require(integer(proof['utf8Bytes'],1) and len(data)==proof['utf8Bytes']<=2*1024*1024,'raw observation size')
    require(hashlib.sha256(data).hexdigest()==proof['sha256'],'raw observation digest')
    return parse(proof['rawUtf8'])

def environment(value):
    require(isinstance(value,dict) and value.get('slot')==0 and type(value.get('slot')) is int,'fixture environment slot')
    require(integer(value.get('generation')) and isinstance(value.get('environmentId'),str)
            and re.fullmatch('[0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12}',value['environmentId']),'actual environment identity')

def journal(value,env):
    require(isinstance(value,dict),'actual journal missing');environment(value.get('environmentIdentity'))
    require(value['environmentIdentity']==env,'journal environment changed')
    owner=value.get('owner');require(isinstance(owner,str) and re.fullmatch('[0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12}',owner),'actual diagnostic owner')
    require(value.get('diagnosticWaitLimitMs')==3000 and type(value.get('diagnosticWaitLimitMs')) is int
            and integer(value.get('diagnosticWaitBegan')) and integer(value.get('diagnosticWaitEnded'))
            and value['diagnosticWaitEnded']>=value['diagnosticWaitBegan'],'separately bounded diagnostic wait')
    require(value.get('journalMonotonicClock')=='System.nanoTime()/1000000; distinct from elapsedRealtime call/wait clocks','diagnostic clock scope')
    raw=value.get('rawSummary');require(isinstance(raw,str) and len(raw.encode())<=131072,'actual bounded journal summary')
    rows=[line for line in raw.splitlines() if len(line.split('\t'))==12 and line.split('\t')[4]==owner]
    require(rows and value.get('ownedRows')==rows,'owned journal rows differ from original summary')
    events={}
    for line in rows:
        row=line.split('\t');require(row[2:7]==['0','CONTROL',owner,env['environmentId'],str(env['generation'])],'owned journal scope')
        require(all(re.fullmatch('[0-9]+',row[i]) for i in (0,1)) and re.fullmatch('-?[0-9]+',row[11]),'journal numeric fields')
        events[row[8]]=events.get(row[8],0)+1
    return owner,events

def failed_waiter(value):
    require(isinstance(value,dict) and value.get('failed') is True and value.get('failureClass')=='java.io.IOException','actual failed binding caller')
    require(all(integer(value.get(key)) for key in ('began','ended','elapsedMs'))
            and value['ended']>=value['began'] and value['elapsedMs']==value['ended']-value['began']<10000,'caller must finish before original ten second deadline')

def verify_binding_result(report,identity,nonce,uid,sdk):
    require(isinstance(report,dict) and report.get('schema')==1 and type(report.get('schema')) is int and report.get('status')=='passed' and not report.get('error'),'successful complete fixture')
    require(report.get('sourceCommit')==identity['sourceCommit'] and report.get('runNonce')==nonce,'fixture source/nonce');verify_installed(report.get('buildIdentity',{}),identity)
    for key in ('actualAndroidExecution','actualFrameworkBinding','actualMessengerIpc','actualProductionClient'):require(report.get(key) is True,key)
    for key in ('actualProductionNetworkService','actualMihomoExecution','actualGeckoExecution','automaticBindRetryAdded','securityExceptionAndroidAcceptance','bindingDiedAndroidAcceptance','physicalPhoneAcceptance','realUserProxyAcceptance'):require(report.get(key) is False,key)
    require(report.get('manualServiceConnectionCallbacks')==0 and type(report.get('manualServiceConnectionCallbacks')) is int,'manual callback scope')
    require(report.get('clientUid')==uid and integer(uid,1) and integer(report.get('clientPid'),2) and report.get('clientProcess')==ACTIVITY_PROCESS,'actual client UID/process')
    require(report.get('androidSdk')==sdk and integer(sdk,28),'actual Android SDK')
    require([(key,report.get(key)) for key in ('bindingTimeoutSeconds','replyTimeoutSeconds','detachTimeoutSeconds')]==[('bindingTimeoutSeconds',10),('replyTimeoutSeconds',15),('detachTimeoutSeconds',5)],'original deadlines')
    checks=report.get('checks');require(isinstance(checks,list) and report.get('checkCount')==len(CHECKS) and type(report.get('checkCount')) is int
        and [row.get('name') for row in checks]==list(CHECKS) and all(row.get('pass') is True for row in checks),'complete ordered18 checks')
    env=report.get('environmentIdentity');environment(env)
    failed_waiter(report.get('nullWaiter'));failed_waiter(report.get('missingWaiter'))
    for role,key in (('null','nullService'),('messenger','messengerService')):
        value=report.get(key);require(isinstance(value,dict) and same(raw_value(report.get(key+'Raw')),value),'actual private Service raw receipt')
        require(value.get('schema')==1 and type(value.get('schema')) is int and value.get('runNonce')==nonce and value.get('sourceCommit')==identity['sourceCommit'],'Service source and nonce')
        verify_installed(value.get('buildIdentity',{}),identity)
        require(value.get('role')==role and value.get('serviceClass')==CLASS+('$NullService' if role=='null' else '$MessengerService')
                and value.get('serviceUid')==uid and integer(value.get('servicePid'),2) and value['servicePid']!=report['clientPid']
                and value.get('serviceProcess')==SERVICE_PROCESS and value.get('onBindMainLooper') is True and integer(value.get('onBindAt')),'actual private Service process/onBind')
        require(value.get('returnedNull') is (role=='null'),'Service null versus Messenger binder')
    first=report['nullService'];normal=report['messengerService'];state=report.get('recoveredState',{})
    require(state.get('slot')==0 and type(state.get('slot')) is int and state.get('alive') is False and state.get('state')=='fixture' and state.get('generation')=='fixture-'+nonce
            and state.get('fixtureNonce')==nonce and state.get('fixtureRole')=='messenger' and state.get('serviceUid')==uid
            and state.get('servicePid')==normal['servicePid'],'actual Client return binds to Messenger Service')
    rows=normal.get('messages');require(isinstance(rows,list) and len(rows)==2 and [row.get('action') for row in rows]==['snapshot','detach'],'original two Messenger commands')
    ids=[]
    for index,row in enumerate(rows):
        require(isinstance(row.get('id'),str) and re.fullmatch('[0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12}',row['id']),'actual correlated request ID');ids.append(row['id'])
        require(row.get('slot')==0 and type(row.get('slot')) is int and row.get('configuration')==''
                and row.get('generation')==('' if index==0 else 'fixture-'+nonce) and row.get('stopReason')=='UNKNOWN'
                and row.get('expectedGeneration')=='' and row.get('sendingUid')==uid and row.get('replySent') is True
                and integer(row.get('receivedAt')) and row['receivedAt']>=normal['onBindAt'],'original command fields/sender/reply')
    require(ids[0]!=ids[1],'request IDs must remain distinct')
    bindings=report.get('bindings');require(isinstance(bindings,list) and len(bindings)==2,'two explicit fault contexts')
    require(bindings[0].get('missingComponent') is False and bindings[1].get('missingComponent') is True,'fault context order')
    for context,targets in zip(bindings,((CLASS+'$NullService',CLASS+'$MessengerService'),(MISSING,))):
        attempts=context.get('attempts');require(isinstance(attempts,list) and len(attempts)==len(targets) and context.get('outstanding')==0 and type(context.get('outstanding')) is int,'all observed owners unbound')
        for i,(attempt,target) in enumerate(zip(attempts,targets),1):
            require(attempt.get('number')==i and type(attempt.get('number')) is int and attempt.get('target')==target
                    and attempt.get('connectionClass')=='local.pocketchat.NetworkTransportClient$Binding'
                    and integer(attempt.get('connectionIdentity'),1) and integer(attempt.get('gateIdentity'),1)
                    and attempt.get('gateCount')==0 and type(attempt.get('gateCount')) is int
                    and attempt.get('accepted') is (not context['missingComponent'])
                    and attempt.get('error')==attempt.get('unbindError')==''
                    and attempt.get('unbindAttempts')==attempt.get('unbindSuccesses')==1
                    and type(attempt.get('unbindAttempts')) is int and type(attempt.get('unbindSuccesses')) is int,'real attempt/one successful unbind')
            require(integer(attempt.get('began')) and integer(attempt.get('ended')) and attempt['ended']>=attempt['began'],'actual bind call interval')
        if len(attempts)==2:require(attempts[0]['connectionIdentity']!=attempts[1]['connectionIdentity'] and attempts[0]['gateIdentity']!=attempts[1]['gateIdentity'],'fresh owner/gate after actual null callback')
    for wait,attempt in ((report['nullWaiter'],bindings[0]['attempts'][0]),(report['missingWaiter'],bindings[1]['attempts'][0])):
        require(wait['began']<=attempt['began']<=attempt['ended']<=wait['ended'],'call contains actual framework bind')
    owner,events=journal(report.get('nullCallbackJournal'),env);require(events.get('IPC_NULL_BINDING')==1 and not events.get('IPC_CONNECTED'),'owned actual null callback before any endpoint')
    complete,events=journal(report.get('completedCallbackJournal'),env);require(complete==owner and events.get('IPC_NULL_BINDING')==events.get('IPC_CONNECTED')==events.get('IPC_DETACH')==1,'owned production callback/round-trip/detach chain')
    missing,events=journal(report.get('missingCallbackJournal'),env);require(missing!=owner and events.get('IPC_BIND_REJECTED')==1 and not events.get('IPC_NULL_BINDING') and not events.get('IPC_CONNECTED'),'real false return has its own diagnostic owner')
    return {'actualAndroidExecution':True,'actualFrameworkBinding':True,'actualMessengerIpc':True,'checks':len(CHECKS),'nullCallbacks':1,'frameworkBindCalls':3,'successfulFrameworkUnbindCalls':3,'productionNetworkServiceFaulted':False,'securityExceptionAndroidAcceptance':False,'bindingDiedAndroidAcceptance':False,'physicalPhoneAcceptance':False}

def verify_runner_report(wrapper,source,reference_identity=None):
    require(isinstance(wrapper,dict) and wrapper.get('schema')==1 and type(wrapper.get('schema')) is int and wrapper.get('status')=='passed' and wrapper.get('sourceCommit')==source,'current-source runner result')
    require(wrapper.get('actualAndroidFixtureAttempted') is True and wrapper.get('fixtureInvocationCount')==1
            and type(wrapper.get('fixtureInvocationCount')) is int and wrapper.get('automaticRetryPerformed') is False,'one actual fixture invocation, no retry')
    identity=wrapper.get('buildIdentity');require(isinstance(identity,dict) and identity.get('sourceCommit')==source,'expected compiled build identity')
    if reference_identity is not None:verify_installed(identity,reference_identity)
    nonce=wrapper.get('runNonce');require(isinstance(nonce,str) and re.fullmatch('[0-9a-f]{32}',nonce),'fresh runner nonce')
    for key in ('installedBefore','installedAfter'):
        value=raw_value(wrapper.get(key));verify_installed(value,identity)
    uid=wrapper.get('packageUid');require(integer(uid,1),'actual installed package UID')
    for key in ('packageUidBeforeRaw','packageUidAfterRaw'):
        raw=wrapper.get(key);require(isinstance(raw,str) and re.findall(r'^package:'+re.escape(PACKAGE)+r' uid:(\d+)\s*$',raw,re.M)==[str(uid)],'actual package UID before/after')
    records=wrapper.get('eventTransport');require(isinstance(records,list) and len(records)==1,'one complete source-bound event')
    record=records[0];require(isinstance(record,dict) and isinstance(record.get('rawUtf8'),str),'original event bytes')
    event=decode_event(record.get('receipt'),record['rawUtf8'].encode(),identity=identity,nonce=nonce,slot=0,action=ACTION,command=1)
    require(event.get('kind')==ACTION and same(event.get('result'),wrapper.get('result')),'raw event differs from actual result')
    return verify_binding_result(wrapper['result'],identity,nonce,uid,wrapper.get('androidSdk'))
