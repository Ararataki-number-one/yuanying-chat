"""Counterfeit parser controls only; no Android, Gecko, input or restart executes."""
import copy
import hashlib
import json
from pathlib import Path
import sys
import shutil
import subprocess
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'tools/gecko'))
from local_draft_contract import verify_local_draft_policy


def counterfeit():
    nonce='e'*32
    def capture(prefix,checkpoint,payload,revision):
        return dict(sourceSdkFormdataContainsUniqueDraft=True,sourceSdkHistoryPresent=True,
            sourceSdkScrollDataPresent=True,sourceSessionCookiePresent=True,checkpointSha256=checkpoint*64,payloadSha256=payload*64,
            draftSha256=hashlib.sha256((prefix+nonce).encode()).hexdigest(),storedRevision=revision,
            sourceHistory=8,sourceScroll=720,sends=0)
    original=capture('f04-enabled-','1','2',0);fresh=capture('f04-fresh-','3','4',2)
    phases=[]
    for index,name in enumerate(['seed','off','stale-on','fresh-on']):
        value=dict(schema=1,status='passed',phase=name,actualAndroidExecution=True,
            actualGeckoExecution=True,fixtureOwnedStore=True,explicitSdkRestore=True,
            automaticStartupSelectionAcceptance=False,physicalPhoneAcceptance=False,
            actualGeckoSessionState=True,fixtureNonce=nonce,profileSlot=1,pid=1000+index)
        value.update(cookieJournalCheckpointed=True,nativeSessionCookiePresent=True,
            environmentIdentity=dict(slot=1,generation=0,environmentId='12345678-1234-1234-1234-123456789012'),
            environmentIdentityAfter=dict(slot=1,generation=0,environmentId='12345678-1234-1234-1234-123456789012'))
        if name in ('seed','stale-on'):
            value.update(capture=copy.deepcopy(original if name=='seed' else fresh),enabledPageMemoryKeepsActualDraft=True)
        if name=='seed':value.update(disabledPageMemoryRedactsActualDraft=True,
            liveDraftPreservedAfterDisable=True,disabledBeforeProcessDeath=True,currentRevision=1)
        else:
            forms=name=='fresh-on';source=fresh if forms else original
            value['read']=dict(checkpointSha256=source['checkpointSha256'],sourceSdkFormdataContainsUniqueDraft=True,
                storedRevision=source['storedRevision'],currentRevision=1 if name=='off' else 2,
                saveDraftEnabled=name!='off',formsPresent=forms,allOtherSdkFieldsUnchanged=True,
                historyUnchanged=True,scrollDataUnchanged=True,freshStoreInstance=True,processId=value['pid'])
            value['restored']=dict(draft='f04-fresh-'+nonce if forms else '',history=8,scroll=720,sends=0,
                cookiePreserved=True,sessionCookiePreserved=True,document=1720000000000+index,
                stableMillis=1000,stableSamples=11,sdkHistoryAndScrollRestored=True)
        if name=='off':value.update(disabledArchiveRejectsNewCopy=True,
            existingArchiveHistoryPreserved=True,enabledForStaleRead=True,nextRevision=2)
        if name=='fresh-on':value.update(ownFixtureCleaned=True,originalPolicyRestored=True)
        phases.append(value)
    return dict(schema=1,phases=phases,forceStopBetweenPhases=True,
        automaticStartupSelectionAcceptance=False,forceStops=[dict(afterPhase=p['phase'],
            beforePid=p['pid'],command=['shell','am','force-stop','local.pocketchat.test'],
            stdout='',returnCode=0) for p in phases[:-1]])


def device(report):
    source='a'*40
    identity=dict(schema=1,package='local.pocketchat.test',sourceCommit=source,sourceTree='b'*40,
        dirtySource=False,version='1.7.0',versionCode=52,
        sdkCoordinate='org.mozilla.geckoview:geckoview:157.0.20261005135250',
        apkSha256='c'*64,apkBytes=100,buildStampSha256='d'*64)
    steps=[];invocations=[]
    for index,phase in enumerate(report['phases'],1):
        nonce=report['phases'][0]['fixtureNonce'] if index==1 else str(index)*32
        event=dict(kind='localDraftPolicy',result=copy.deepcopy(phase),nativeContext='environment-2',processSlot=1)
        envelope=dict(schema=1,sourceCommit=source,buildIdentity=identity,runNonce=nonce,
            fixtureAction='localDraftPolicy',command=index,sequence=1,nativeContext='environment-2',
            processSlot=1,observedAtElapsedRealtime=1000+index,event=event)
        raw=json.dumps(envelope,separators=(',',':'))+'\n'
        receipt=dict(kind='eventReceipt',schema=1,runNonce=nonce,fixtureAction='localDraftPolicy',
            command=index,sequence=1,nativeContext='environment-2',processSlot=1,
            eventKind='localDraftPolicy',payloadBytes=len(raw.encode()),payloadSha256=hashlib.sha256(raw.encode()).hexdigest())
        steps.append(event);invocations.append(dict(runNonce=nonce,fixtureAction='localDraftPolicy',
            processSlot=1,events=[dict(receipt=receipt,rawUtf8=raw)]))
    return dict(sourceCommit=source,steps=steps,eventTransport=dict(buildIdentity=identity,invocations=invocations))


class DraftControls(unittest.TestCase):
    def reject(self,edit):
        value=counterfeit();edit(value)
        with self.assertRaises((ValueError,KeyError,TypeError)):verify_local_draft_policy(value)
    def test_semantic_control_retains_explicit_scope(self):
        value=verify_local_draft_policy(counterfeit())
        self.assertFalse(value['rawDeviceBindingVerified']);self.assertFalse(value['automaticStartupSelectionAcceptance'])
    def test_raw_control_does_not_claim_real_device_execution(self):
        value=counterfeit();result=verify_local_draft_policy(value,device=device(value),source='a'*40)
        self.assertTrue(result['rawDeviceBindingVerified']);self.assertFalse(result['physicalPhoneAcceptance'])
    def test_missing_phase(self):self.reject(lambda v:v['phases'].pop())
    def test_phase_reordered(self):self.reject(lambda v:v['phases'].reverse())
    def test_same_process(self):self.reject(lambda v:v['phases'][2].update(pid=1001))
    def test_missing_force_stop(self):self.reject(lambda v:v['forceStops'].pop())
    def test_wrong_force_stop(self):self.reject(lambda v:v['forceStops'][0].update(command=['shell','am','force-stop','unrelated']))
    def test_empty_source_formdata_cannot_pass(self):self.reject(lambda v:v['phases'][0]['capture'].update(sourceSdkFormdataContainsUniqueDraft=False))
    def test_nonunique_input_cannot_pass(self):self.reject(lambda v:v['phases'][0]['capture'].update(draftSha256='f'*64))
    def test_off_forms_preserved(self):self.reject(lambda v:v['phases'][1]['read'].update(formsPresent=True))
    def test_stale_on_forms_revived(self):self.reject(lambda v:v['phases'][2]['read'].update(formsPresent=True))
    def test_fresh_on_forms_lost(self):self.reject(lambda v:v['phases'][3]['read'].update(formsPresent=False))
    def test_history_changed(self):self.reject(lambda v:v['phases'][2]['read'].update(historyUnchanged=False))
    def test_scroll_changed(self):self.reject(lambda v:v['phases'][1]['restored'].update(scroll=0))
    def test_cookie_lost(self):self.reject(lambda v:v['phases'][3]['restored'].update(cookiePreserved=False))
    def test_accidental_send(self):self.reject(lambda v:v['phases'][3]['restored'].update(sends=1))
    def test_boolean_send(self):self.reject(lambda v:v['phases'][1]['restored'].update(sends=False))
    def test_original_checkpoint_replaced(self):self.reject(lambda v:v['phases'][2]['read'].update(checkpointSha256='f'*64))
    def test_archive_history_deleted(self):self.reject(lambda v:v['phases'][1].update(existingArchiveHistoryPreserved=False))
    def test_new_disabled_copy_accepted(self):self.reject(lambda v:v['phases'][1].update(disabledArchiveRejectsNewCopy=False))
    def test_policy_revision_invented(self):self.reject(lambda v:v['phases'][1].update(nextRevision=3))
    def test_dom_not_stable(self):self.reject(lambda v:v['phases'][2]['restored'].update(stableMillis=999))
    def test_scope_widened(self):self.reject(lambda v:v.update(automaticStartupSelectionAcceptance=True))
    def test_uncleaned_fixture(self):self.reject(lambda v:v['phases'][3].update(ownFixtureCleaned=False))
    def test_raw_mutation(self):
        value=counterfeit();raw=device(value);raw['eventTransport']['invocations'][2]['events'][0]['rawUtf8']+=' '
        with self.assertRaises(ValueError):verify_local_draft_policy(value,device=raw,source='a'*40)
    def test_raw_summary_only(self):
        value=counterfeit();raw=device(value);raw['eventTransport']['invocations'].pop()
        with self.assertRaises(ValueError):verify_local_draft_policy(value,device=raw,source='a'*40)
    def test_raw_foreign_source(self):
        value=counterfeit();raw=device(value)
        with self.assertRaises(ValueError):verify_local_draft_policy(value,device=raw,source='f'*40)
    def test_raw_foreign_invocation(self):
        value=counterfeit();raw=device(value);raw['eventTransport']['invocations'][2]['runNonce']='f'*32
        with self.assertRaises(ValueError):verify_local_draft_policy(value,device=raw,source='a'*40)
    def test_seed_nonce_relabelled(self):
        value=counterfeit();raw=device(value)
        invocation=raw['eventTransport']['invocations'][0];invocation['runNonce']='f'*32
        record=invocation['events'][0];envelope=json.loads(record['rawUtf8']);envelope['runNonce']='f'*32
        encoded=json.dumps(envelope,separators=(',',':'))+'\n';record['rawUtf8']=encoded
        record['receipt'].update(runNonce='f'*32,payloadBytes=len(encoded.encode()),payloadSha256=hashlib.sha256(encoded.encode()).hexdigest())
        with self.assertRaisesRegex(ValueError,'fixture nonce differs'):verify_local_draft_policy(value,device=raw,source='a'*40)
    def test_environment_generation_changed(self):self.reject(lambda v:v['phases'][2]['environmentIdentity'].update(generation=1))
    def test_cookie_checkpoint_missing(self):self.reject(lambda v:v['phases'][0].update(cookieJournalCheckpointed=False))
    def test_boolean_disk_revision(self):self.reject(lambda v:v['phases'][1]['read'].update(storedRevision=False))
    def test_boolean_policy_revision(self):self.reject(lambda v:v['phases'][0].update(currentRevision=True))
    def test_boolean_capture_send(self):self.reject(lambda v:v['phases'][0]['capture'].update(sends=False))
    def test_boolean_phase_schema(self):self.reject(lambda v:v['phases'][0].update(schema=True))


class PublicStageControls(unittest.TestCase):
    def test_declared_public_stage_imports_without_application_checkout(self):
        # This helper reads only copy declarations from publisher AST. No
        # publisher setup, APK handling, Git mutation or network executes.
        from profile_lifecycle_gate_test import release_stage_python_files
        files=release_stage_python_files()
        self.assertIn('tools/gecko/local_draft_contract.py',files)
        with tempfile.TemporaryDirectory(prefix='f04-public-stage-') as temporary:
            stage=Path(temporary)
            for name in files:
                path=stage/name;path.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(ROOT/name,path)
            self.assertFalse((stage/'app').exists())
            for selected,module in [(stage/'tools/gecko','check_interaction_transfer_evidence'),
                                    (stage/'tools','gecko.check_interaction_transfer_evidence')]:
                code='import sys;sys.path.insert(0,'+repr(str(selected))+');import '+module
                result=subprocess.run([sys.executable,'-I','-c',code],cwd=stage,capture_output=True,text=True)
                self.assertEqual(result.returncode,0,result.stderr)
            (stage/'tools/gecko/local_draft_contract.py').unlink()
            code='import sys;sys.path.insert(0,'+repr(str(stage/'tools/gecko'))+');import check_interaction_transfer_evidence'
            rejected=subprocess.run([sys.executable,'-I','-c',code],cwd=stage,capture_output=True,text=True)
            self.assertNotEqual(rejected.returncode,0)
            self.assertIn('local_draft_contract',rejected.stderr)


if __name__=='__main__':unittest.main()
