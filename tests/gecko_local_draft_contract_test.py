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
            automaticStartupSelectionAcceptance=False,physicalPhoneAcceptance=False,realChatGptPageMemoryCapture=False,
            actualGeckoSessionState=True,fixtureNonce=nonce,profileSlot=1,pid=1000+index)
        value.update(cookieJournalCheckpointed=True,nativeSessionCookiePresent=True,
            environmentIdentity=dict(slot=1,generation=0,environmentId='12345678-1234-1234-1234-123456789012'),
            environmentIdentityAfter=dict(slot=1,generation=0,environmentId='12345678-1234-1234-1234-123456789012'))
        if name in ('seed','stale-on'):
            value.update(capture=copy.deepcopy(original if name=='seed' else fresh),enabledPageMemoryKeepsActualDraft=True)
            source_url='http://127.0.0.1:8765/browser-session?context=2&localDraft='+nonce+'#f04-saved'
            logical='https://chatgpt.com/c/f04-'+nonce;draft=('f04-enabled-' if name=='seed' else 'f04-fresh-')+nonce
            dom=dict(ok=True,url=source_url,draft=draft,draftLength=len(draft),draftComplete=True,hasDraft=True,
                     selectionStart=len(draft),selectionEnd=len(draft),cookie='f04Draft=kept',token='synthetic-session-2',
                     history=8,scroll=720,sends=0,document=1720000000000+index)
            rows=[]
            for serial,enabled in enumerate((True,False) if name=='seed' else (True,)):
                revision=(serial if name=='seed' else 2);adapted=dict(dom,url=logical)
                stored=dict(adapted,localDraftPolicyRevision=revision)
                if not enabled:
                    stored.update(draft=None,draftComplete=False,draftOmittedReason='local-saving-disabled')
                    stored.pop('selectionStart');stored.pop('selectionEnd')
                rows.append(dict(enabled=enabled,policyRevision=revision,sourceDomRaw=json.dumps(dom),sourceDomAfterRaw=json.dumps(dom),
                    memoryInputRaw=json.dumps(adapted),storedSnapshotRaw=json.dumps(stored),loopbackSerialBefore=serial,
                    loopbackSerialAfter=serial,storedSerial=serial+1,loopbackEntryPresent=False,storedEntryPresent=True))
            value['adapter']=dict(schema=1,kind='page-memory-remember-url-only',sourceDomUrl=source_url,
                logicalMemoryUrl=logical,onlyUrlAdapted=True,realChatGPT=False,checks=rows)
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
    def test_memory_adapter_missing(self):self.reject(lambda v:v['phases'][0].pop('adapter'))
    def test_memory_scope_cannot_claim_website_capture(self):
        self.reject(lambda v:v['phases'][0].update(realChatGptPageMemoryCapture=True))
        self.reject(lambda v:v['phases'][0]['adapter'].update(realChatGPT=True))
    def test_memory_adapter_foreign_urls(self):
        for field in ('sourceDomUrl','logicalMemoryUrl'):
            self.reject(lambda v,field=field:v['phases'][0]['adapter'].update({field:'https://chatgpt.com/c/foreign'}))
    def test_memory_adapter_flags_do_not_replace_actual_rows(self):
        self.reject(lambda v:v['phases'][0]['adapter'].update(checks=[]))
        self.reject(lambda v:v['phases'][0]['adapter']['checks'][0].update(storedSnapshotRaw='null'))
        self.reject(lambda v:v['phases'][0]['adapter']['checks'][0].update(storedSnapshotRaw='{}'))
    def test_memory_adapter_only_url_is_allowed(self):
        for field,replacement in [('draft','other'),('selectionStart',0),('cookie',''),('history',9),('scroll',0),('document',1),('hasDraft',1)]:
            def change(value):
                row=value['phases'][0]['adapter']['checks'][0];data=json.loads(row['memoryInputRaw']);data[field]=replacement;row['memoryInputRaw']=json.dumps(data)
            with self.subTest(field=field):self.reject(change)
    def test_memory_original_dom_is_not_mutated(self):
        self.reject(lambda v:v['phases'][0]['adapter']['checks'][0].update(sourceDomAfterRaw='{}'))
    def test_memory_loopback_call_must_reject(self):
        self.reject(lambda v:v['phases'][0]['adapter']['checks'][0].update(loopbackEntryPresent=True))
        self.reject(lambda v:v['phases'][0]['adapter']['checks'][0].update(loopbackSerialAfter=1))
    def test_memory_adapted_call_must_store(self):
        self.reject(lambda v:v['phases'][0]['adapter']['checks'][0].update(storedEntryPresent=False))
        self.reject(lambda v:v['phases'][0]['adapter']['checks'][0].update(storedSerial=0))
    def test_memory_disabled_snapshot_must_redact(self):
        def change(value):
            row=value['phases'][0]['adapter']['checks'][1];row['storedSnapshotRaw']=row['memoryInputRaw']
        self.reject(change)
    def test_memory_flags_have_strict_types(self):
        self.reject(lambda v:v['phases'][0]['adapter'].update(onlyUrlAdapted=1))
        self.reject(lambda v:v['phases'][0]['adapter'].update(realChatGPT=0))
        self.reject(lambda v:v['phases'][0]['adapter']['checks'][0].update(policyRevision=False))
    def test_memory_raw_duplicate_fields_are_rejected(self):
        for field in ('sourceDomRaw','memoryInputRaw','storedSnapshotRaw'):
            def change(value):
                row=value['phases'][0]['adapter']['checks'][0]
                row[field]='{"draft":"counterfeit",'+row[field][1:]
                if field=='sourceDomRaw':row['sourceDomAfterRaw']=row[field]
            with self.subTest(field=field):self.reject(change)
    def test_memory_raw_nonfinite_fields_are_rejected(self):
        for invalid in ('NaN','Infinity','1e400'):
            def change(value):
                row=value['phases'][0]['adapter']['checks'][0]
                for field in ('sourceDomRaw','sourceDomAfterRaw','memoryInputRaw','storedSnapshotRaw'):
                    row[field]='{"extra":'+invalid+','+row[field][1:]
            with self.subTest(value=invalid):self.reject(change)
    def test_partial_failure_evidence_cannot_establish_acceptance(self):
        value=counterfeit();raw=device(value);record=raw['eventTransport']['invocations'][0]['events'][0]
        envelope=json.loads(record['rawUtf8']);event=envelope['event'];event['kind']='error'
        event['result']=dict(error='F04 actual SDK regression: retained failure',diagnosticOnly=True,
            acceptance=False,partial=dict(domSource=dict(rawUtf8=value['phases'][0]['adapter']['checks'][0]['sourceDomRaw'])))
        encoded=json.dumps(envelope,separators=(',',':'))+'\n';record['rawUtf8']=encoded
        record['receipt'].update(eventKind='error',payloadBytes=len(encoded.encode()),payloadSha256=hashlib.sha256(encoded.encode()).hexdigest())
        with self.assertRaisesRegex(ValueError,'raw device error'):
            verify_local_draft_policy(value,device=raw,source='a'*40)


def restore_observers_preserve_original(text):
    """Remove only the approved passive observations; all old code stays exact."""
    additions=(
        ('    observeStage("start");\n',''),
        ('retainPartial("probeRaw",raw);done.accept(J.parse(raw));','done.accept(J.parse(raw));'),
        ('void waitSeed(boolean fresh){observeStage("capture-wait-document");probe(value->{','void waitSeed(boolean fresh){probe(value->{'),
        ('    observeStage("capture-wait-sdk");\n',''),
        ('void readAndRestore(boolean fresh){observeStage("read-scheduled");worker.execute','void readAndRestore(boolean fresh){worker.execute'),
        ('observeRestoreRead(filtered);observeStage("restore-load-blank");s.web.loadUrl("about:blank");','s.web.loadUrl("about:blank");'),
        ('    observeStage("restore-wait-blank");\n',''),
        ('    observeStage("restore-dispatch");\n',''),
        ('    observeRestored(fresh,dom,ready,now);\n',''),
        ('"memoryStored","probeRaw","stage","restoreRead","sdkRestore","restoreBlank","restoreDispatch","restoreDom","restoreReadiness"','"memoryStored"'),
    )
    for new,old in additions:
        if text.count(new)!=1:return False
        text=text.replace(new,old,1)
    start=text.find('  // Bounded latest observations are emitted only with the existing failure.\n')
    end=text.find('  void retainPartial(',start)
    if start<0 or end<0:return False
    text=text[:start]+text[end:]
    return hashlib.sha256(text.encode()).hexdigest()=='4808b1459b39b47995b54ff5709bdf48019fa883758fccc2958e35efcbe05a81'


class RestoreObservationPreservationControls(unittest.TestCase):
    def setUp(self):self.source=(ROOT/'tests/gecko/GeckoLocalDraftIntegration.java').read_text()
    def test_all_original_fixture_logic_including_readiness_stays_byte_exact(self):
        self.assertTrue(restore_observers_preserve_original(self.source))
    def test_deadline_poll_stability_and_each_original_readiness_guard_cannot_change(self):
        for old,new in [('elapsedRealtime()+40000','elapsedRealtime()+41000'),('}},100);','}},101);'),
                        ('stableSamples<5','stableSamples<4'),('now-stableAt<1000','now-stableAt<999'),
                        ('dom.optBoolean("ok")&&','true&&'),('==prefs.getInt(name+"History",-2)','>=0'),
                        ('&&sameCookies(dom.optString("cookie"),prefs.getString(name+"Cookie",""))',''),
                        ('&&s.web.painted.contains(s.web.current)',''),('&&!s.web.failed','')]:
            with self.subTest(old=old):
                self.assertIn(old,self.source)
                self.assertFalse(restore_observers_preserve_original(self.source.replace(old,new,1)))
    def test_new_readiness_shortcuts_and_extra_page_operations_are_rejected(self):
        for inserted in ('ready=true;','s.web.loadUrl(target);','s.web.checkpointState();'):
            changed=self.source.replace('    observeRestored(fresh,dom,ready,now);','    observeRestored(fresh,dom,ready,now);'+inserted,1)
            self.assertFalse(restore_observers_preserve_original(changed))
    def test_passive_observer_helpers_have_no_page_policy_or_scheduling_mutation(self):
        helpers=self.source.split('  // Bounded latest observations are emitted only with the existing failure.\n',1)[1].split('  void retainPartial(',1)[0]
        for forbidden in ('evaluateJavascript(','.loadUrl(','.restoreCheckpoint(','.checkpointState(','.post(','.postDelayed(','.edit(','.apply(','.commit(','.setActive(','.close(','.add(','.remove('):
            self.assertNotIn(forbidden,helpers)


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
