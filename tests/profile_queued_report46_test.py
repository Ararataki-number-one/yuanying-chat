"""Counterfeit controls for raw owned evidence; samples are synthetic unit data."""
import ast,copy,hashlib,json,os
from pathlib import Path
import unittest
from gecko.queued_changes46 import verify_queued_changes46

ROOT=Path(__file__).resolve().parents[1]
SOURCE='b'*40
NONCE='a'*32
NATIVE_FILE_PRODUCER = b'\n'.join((
    b'void beginSyntheticFileWork(){session.resourceFileWork(false,true);}',
    b'void finishSyntheticFileWork(){session.resourceFileWork(false,false);}',
    b'beginSyntheticFileWork();session.navigating=false;session.connecting=false;session.state=J.obj("busy",false);',
    b'DeferredBrowserSettings.cancel(session);finishSyntheticFileWork();session.changed();',
    b'"savedWhileFileBusy",ok,"oldRouteKept",kept',
    b'"fileWorkCleared",session.resourceFilePreparations==0&&session.pending==null',
))
FILE_ASSERTIONS = ('savedWhileFileBusy','oldRouteKept','browserSavedWithoutApplying',
                   'fileWorkCleared','appliedWhenIdle','vpnGuardBlocksWithoutVpn')


def sample():
    network=dict(vpn=True,internet=True,network='vpn-101',observerNetwork='vpn-101',offline=False,connecting=False,recoveryScheduled=False,guardCoverageIssue='',guardVpnActive=True,guardRequiresVpn=True,guardRouteProtected=True,guardAllowed=True,networkReady=True)
    state=dict(runNonce=NONCE,sourceCommit=SOURCE,generation=3,running=True,tunEstablished=True,forwardsTraffic=False,mode='full',configuredRoutes=['0.0.0.0/0','::/0'],error='',fdCloseSucceeded=False,startedAt=1000,stoppedAt=0)
    def ipc(value):return dict(schema=1,sameProcessServiceState=True,providerPid=1234,installedSource=SOURCE,state=value)
    covered=dict(ipc=ipc(copy.deepcopy(state)),network=copy.deepcopy(network))
    stopped=copy.deepcopy(state);stopped.update(running=False,tunEstablished=False,fdCloseSucceeded=True,stoppedAt=2000,events=[dict(kind='tun-closed',detail='requested-stop',generation=3)])
    absent=copy.deepcopy(network);absent.update(vpn=False,guardVpnActive=False,guardAllowed=False,networkReady=False)
    closed=dict(ipc=ipc(stopped),network=absent)
    applied=dict(observedAt=1200,pendingCount=0,desiredRevision=4,appliedRevision=4,network=copy.deepcopy(network))
    identity=dict(sourceCommit=SOURCE,runNonce=NONCE,processSlot=1,environmentGeneration=2,environmentId='environment-2',command=46)
    dispatched=ipc(copy.deepcopy(state));dispatched.update(stopDispatched=True,stopGeneration=3)
    candidate=dict(environmentId='environment-2',generation=2,candidateId='saved-candidate-46',savedRevision=4,appliedRevision=0,saveState='saved',applicationState='pending',scope='session')
    vpn=dict(identity,serviceGeneration=3,beganAt=800,stopBudgetStarted=1150,originalCheckBudgetMillis=3500,actualAndroidExecution=True,physicalPhoneAcceptance=False,failure='',appliedObserved=True,closedObserved=True,expectedCandidate=candidate,events=[dict(kind=kind,value=value,at=at) for kind,value,at in [('full-vpn-settled',covered,1100),('actual-deferred-application',applied,1200),('owned-stop-dispatch',dispatched,1300),('owned-vpn-closed-and-guard-blocked',closed,2100)]],originalRouteAdmission=dict(accepted=True,lease=8,network=copy.deepcopy(network)))
    observer=dict(identity,actualSdkSampling=True,retiredAfterApplied=True,productionAdmissionChanged=False,initiallyKnown=False,resourceBinding='actual-binding-123456',url='http://127.0.0.1:8765/fixture?context=2&action=read&command=4',navigationEpoch=7,observations=[dict(known=True,busy=busy,fileBusy=False,documentId='actual-document-123456',navigationEpoch=7,sequence=seq) for seq,busy in [(1,True),(2,False)]])
    return dict(queuedVpnLifecycle=vpn,queuedDocumentObservation=observer)


def native_file_sample():
    """Synthetic current producer shape; never actual device evidence."""
    value=sample();value.update({key:True for key in FILE_ASSERTIONS})
    original=value['queuedDocumentObservation']['observations'][0]
    value['queuedDocumentObservation']['observations']=[
        dict(original,sequence=index+1,busy=busy,fileBusy=file_busy)
        for index,(busy,file_busy) in enumerate(((True,False),(True,True),(True,False),(False,False),(False,False)))]
    return value


class QueuedReport46(unittest.TestCase):
    def test_accepts_complete_raw_owned_evidence(self):
        value=sample();self.assertIs(verify_queued_changes46(value,SOURCE,NONCE),value)

    def test_rejects_owner_type_application_close_and_document_counterfeits(self):
        mutations=[]
        def changed(path,value):
            target=sample();cursor=target
            for key in path[:-1]:cursor=cursor[key]
            cursor[path[-1]]=value;mutations.append(target)
        vpn='queuedVpnLifecycle';observer='queuedDocumentObservation'
        for path,value in [
            ([vpn,'sourceCommit'],'c'*40),([vpn,'runNonce'],'d'*32),([observer,'runNonce'],'d'*32),
            ([vpn,'processSlot'],True),([vpn,'environmentGeneration'],True),([observer,'environmentId'],'other'),
            ([vpn,'serviceGeneration'],True),([vpn,'originalCheckBudgetMillis'],3500.0),([vpn,'failure'],'unconfirmed'),
            ([vpn,'actualAndroidExecution'],1),([vpn,'physicalPhoneAcceptance'],True),([vpn,'appliedObserved'],False),([vpn,'closedObserved'],False),
            ([vpn,'events',0,'value','ipc','schema'],True),([vpn,'events',0,'value','ipc','sameProcessServiceState'],False),
            ([vpn,'events',0,'value','ipc','providerPid'],True),([vpn,'events',0,'value','ipc','installedSource'],'c'*40),
            ([vpn,'events',0,'value','ipc','state','runNonce'],'d'*32),([vpn,'events',0,'value','ipc','state','generation'],4),
            ([vpn,'events',0,'value','ipc','state','forwardsTraffic'],True),([vpn,'events',0,'value','ipc','state','configuredRoutes'],['0.0.0.0/0']),
            ([vpn,'events',0,'value','network','vpn'],False),([vpn,'events',0,'value','network','observerNetwork'],'stale'),
            ([vpn,'events',0,'value','network','guardCoverageIssue'],'split'),([vpn,'events',1,'value','pendingCount'],False),
            ([vpn,'events',1,'value','appliedRevision'],3),([vpn,'events',1,'value','network','guardAllowed'],False),
            ([vpn,'events',1,'value','network','networkReady'],False),([vpn,'events',1,'value','network','network'],'other-vpn'),
            ([vpn,'events',3,'value','ipc','providerPid'],1235),([vpn,'events',3,'value','ipc','state','running'],True),
            ([vpn,'events',3,'value','ipc','state','fdCloseSucceeded'],False),([vpn,'events',3,'value','ipc','state','stoppedAt'],999),
            ([vpn,'events',3,'value','network','vpn'],True),([vpn,'events',3,'value','network','guardRequiresVpn'],False),
            ([vpn,'events',3,'value','network','guardAllowed'],True),([vpn,'originalRouteAdmission','accepted'],False),
            ([observer,'actualSdkSampling'],False),([observer,'retiredAfterApplied'],False),([observer,'productionAdmissionChanged'],True),
            ([observer,'resourceBinding'],'short'),([observer,'url'],'https://foreign.invalid'),([observer,'initiallyKnown'],0),
            ([observer,'observations',0,'known'],False),([observer,'observations',0,'busy'],False),([observer,'observations',1,'busy'],True),
            ([observer,'observations',1,'documentId'],'different-document-123'),([observer,'observations',1,'sequence'],1),
            ([observer,'observations',1,'navigationEpoch'],8),([observer,'observations',1,'fileBusy'],True),
            ([vpn,'expectedCandidate','environmentId'],'other'),([vpn,'expectedCandidate','generation'],True),
            ([vpn,'expectedCandidate','savedRevision'],5),([vpn,'expectedCandidate','applicationState'],'applied'),
            ([vpn,'expectedCandidate','appliedRevision'],4),([vpn,'expectedCandidate','candidateId'],'invalid/credential'),
            ([vpn,'events',3,'value','ipc','state','events',0,'detail'],'system-revoke'),
            ([vpn,'events',3,'value','ipc','state','events',0,'generation'],4),
            ([vpn,'events',2,'value','stopDispatched'],False),([vpn,'events',2,'value','stopGeneration'],4),
            ([vpn,'expectedCandidate','scope'],'core'),([vpn,'stopBudgetStarted'],True),
            ([vpn,'events',3,'at'],5000),([vpn,'events',1,'value','observedAt'],True),
            ([vpn,'events',2,'at'],2200),([vpn,'events',3,'value','ipc','state','stoppedAt'],1100),
        ]:changed(path,value)
        duplicate=sample();duplicate[vpn]['events'].append(copy.deepcopy(duplicate[vpn]['events'][0]));mutations.append(duplicate)
        missing=sample();missing[vpn]['events'].pop();mutations.append(missing)
        for index,value in enumerate(mutations):
            with self.subTest(mutation=index),self.assertRaises(ValueError):verify_queued_changes46(value,SOURCE,NONCE)
        self.assertEqual(len(mutations),68)
        output=os.environ.get('QUEUED_REPORT46_CONTROLS')
        if output:Path(output).write_text(json.dumps(dict(scope='Synthetic report verifier controls only; no Android/Gecko execution.',rejectedCounterfeits=len(mutations),verifierSha256=hashlib.sha256((ROOT/'tests/gecko/queued_changes46.py').read_bytes()).hexdigest(),actualAndroidExecution=False,actualGeckoExecution=False),indent=2)+'\n')

    def test_committed_native_file_producer_accepts_observed_preparation_then_idle(self):
        for producer in (NATIVE_FILE_PRODUCER,(ROOT/'tests/gecko/GeckoIntegrationTestActivity.java').read_bytes()):
            value=native_file_sample()
            self.assertIs(verify_queued_changes46(value,SOURCE,NONCE,producer_source=producer),value)
        value=native_file_sample()
        value['queuedDocumentObservation']['observations'][2]['fileBusy']=True
        self.assertIs(verify_queued_changes46(value,SOURCE,NONCE,producer_source=NATIVE_FILE_PRODUCER),value)

    def test_report_claim_cannot_select_native_file_contract(self):
        for producer in (None,b'// historical reply-only producer'):
            with self.assertRaisesRegex(ValueError,'legacy observation has no native file work'):
                verify_queued_changes46(native_file_sample(),SOURCE,NONCE,producer_source=producer)
        value=sample()
        self.assertIs(verify_queued_changes46(value,SOURCE,NONCE,producer_source=b'// historical reply-only producer'),value)

    def test_current_producer_cannot_use_historical_report_without_file_samples(self):
        value=sample();value.update({key:True for key in FILE_ASSERTIONS})
        with self.assertRaisesRegex(ValueError,'document idle follows actual native file preparation'):
            verify_queued_changes46(value,SOURCE,NONCE,producer_source=NATIVE_FILE_PRODUCER)

    def test_partial_duplicate_or_invalid_source_is_rejected(self):
        for marker in NATIVE_FILE_PRODUCER.splitlines():
            for producer in (NATIVE_FILE_PRODUCER.replace(marker,b'',1),NATIVE_FILE_PRODUCER+b'\n'+marker):
                with self.subTest(marker=marker),self.assertRaisesRegex(ValueError,'complete committed file-preparation producer'):
                    verify_queued_changes46(native_file_sample(),SOURCE,NONCE,producer_source=producer)
        for producer in ('text',b'',bytearray(NATIVE_FILE_PRODUCER),b'x'*(4*1024*1024+1)):
            with self.assertRaisesRegex(ValueError,'committed producer source'):
                verify_queued_changes46(native_file_sample(),SOURCE,NONCE,producer_source=producer)

    def test_native_contract_keeps_all_original_deferral_assertions_strict(self):
        for key in FILE_ASSERTIONS:
            for wrong in (False,1,None):
                value=native_file_sample();value[key]=wrong
                with self.subTest(key=key,value=wrong),self.assertRaises(ValueError):
                    verify_queued_changes46(value,SOURCE,NONCE,producer_source=NATIVE_FILE_PRODUCER)

    def test_native_work_cannot_escape_document_phase_or_reappear_after_idle(self):
        changes=((0,'fileBusy',True),(4,'fileBusy',True),(1,'busy',False),(1,'fileBusy',False),
                 (1,'fileBusy',1),(1,'known',False),(1,'sequence',1),(1,'documentId','foreign-document-123'),
                 (1,'navigationEpoch',8),(3,'fileBusy',True),(3,'busy',True),(4,'busy',True))
        for index,key,wrong in changes:
            value=native_file_sample();value['queuedDocumentObservation']['observations'][index][key]=wrong
            # A still-busy row before final idle is legal; make this mutation a
            # return to busy after the document already became idle instead.
            if index==3 and key=='busy':value['queuedDocumentObservation']['observations'][2]['busy']=False
            with self.subTest(index=index,key=key,wrong=wrong),self.assertRaises(ValueError):
                verify_queued_changes46(value,SOURCE,NONCE,producer_source=NATIVE_FILE_PRODUCER)

    def test_native_contract_retains_same_candidate_and_owned_close(self):
        mutations=(lambda v:v['queuedVpnLifecycle']['expectedCandidate'].update(savedRevision=5),
                   lambda v:v['queuedVpnLifecycle']['events'][2]['value'].update(stopGeneration=4),
                   lambda v:v['queuedVpnLifecycle']['events'][3]['value']['network'].update(guardAllowed=True),
                   lambda v:v['queuedDocumentObservation'].update(retiredAfterApplied=False))
        for mutate in mutations:
            value=native_file_sample();mutate(value)
            with self.assertRaises(ValueError):verify_queued_changes46(value,SOURCE,NONCE,producer_source=NATIVE_FILE_PRODUCER)

    def test_runtime_selects_producer_from_installed_source_commit(self):
        tree=ast.parse((ROOT/'tests/gecko/run_device.py').read_text())
        assignment=next(node for node in ast.walk(tree) if isinstance(node,ast.Assign)
                        and any(isinstance(target,ast.Name) and target.id=='queued_producer' for target in node.targets))
        expected=ast.parse("queued_producer=subprocess.check_output(['git','show',identity['sourceCommit']+':tests/gecko/GeckoIntegrationTestActivity.java'],cwd=ROOT)").body[0]
        self.assertEqual(ast.dump(assignment),ast.dump(expected))
        calls=[node for node in ast.walk(tree) if isinstance(node,ast.Call) and isinstance(node.func,ast.Name) and node.func.id=='verify_queued_changes46']
        self.assertEqual(len(calls),1)
        self.assertEqual([(key.arg,ast.dump(key.value)) for key in calls[0].keywords],[('producer_source',ast.dump(ast.Name(id='queued_producer',ctx=ast.Load())))])


if __name__=='__main__':unittest.main(verbosity=2)
