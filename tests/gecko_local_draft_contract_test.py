"""Counterfeit parser controls only; no Android, Gecko, input or restart executes."""
import copy
import hashlib
import importlib.util
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
from gecko_local_draft_blank_barrier_test import BlankBarrierControls, undo_blank_preparation


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
            owned_nonce=str(index+1)*32
            value['blankBarrier']=dict(schema=1,kind='nonce-owned-local-blank-navigation',nonce=owned_nonce,
                command=index+1,phase=name,uri='http://127.0.0.1:8765/f04-restore-blank?nonce='+owned_nonce+'&command='+str(index+1)+'&phase='+name,
                session=1000+index,requestedAtElapsedRealtime=100,startedAtElapsedRealtime=200,
                committedAtElapsedRealtime=300,stoppedAtElapsedRealtime=400,deadlineElapsedRealtime=40000,
                requestEpoch=0,commitEpoch=1,completed=True,error='',fixturePreparation=True,realChatGPT=False)
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
    def test_system_uptime_cannot_be_a_restored_stability_duration(self):
        self.reject(lambda v:v['phases'][3]['restored'].update(stableMillis=335020,stableSamples=5))
    def test_restored_stability_must_fit_original_40000ms_budget(self):
        self.reject(lambda v:v['phases'][3]['restored'].update(stableMillis=40001))
        value=counterfeit();value['phases'][3]['restored']['stableMillis']=40000
        verify_local_draft_policy(value)
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
    try:text=undo_blank_preparation(text)
    except ValueError:return False
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


class BlankPreparationServerControls(unittest.TestCase):
    def respond(self,path):
        # Execute the actual two HTTP handler methods with an in-memory socket
        # adapter. No real server, Android, browser or network is started.
        import ast, io, re, urllib.parse
        source=(ROOT/'tests/gecko/run_device.py').read_text()
        tree=ast.parse(source);kind=next(x for x in tree.body if isinstance(x,ast.ClassDef) and x.name=='Fixture')
        methods=[copy.deepcopy(x) for x in kind.body if isinstance(x,ast.FunctionDef) and x.name in ('do_GET','end_headers')]
        class Base:
            def send_response(self,value):self.code=value
            def send_header(self,key,value):self.headers_sent.append((key,value))
            def send_error(self,value,message):self.code=value;self.error=message
            def end_headers(self):pass
        node=ast.ClassDef(name='Fixture',bases=[ast.Name(id='Base',ctx=ast.Load())],keywords=[],body=methods,decorator_list=[])
        module=ast.fix_missing_locations(ast.Module(body=[node],type_ignores=[]));scope={'Base':Base,'re':re,'urllib':urllib}
        exec(compile(module,'actual-f04-http-handler','exec'),scope)
        value=scope['Fixture']();value.path=path;value.headers={};value.headers_sent=[];value.wfile=io.BytesIO()
        value.do_GET();return value
    def test_owned_blank_has_no_script_history_form_cookie_or_external_resource(self):
        value=self.respond('/f04-restore-blank?nonce='+'a'*32+'&command=1&phase=off')
        self.assertEqual(value.code,200)
        self.assertEqual(value.wfile.getvalue(),b'<!doctype html><meta charset="utf-8"><title>Owned F04 restore preparation</title>')
        self.assertEqual(dict(value.headers_sent)['Cache-Control'],'no-store')
        self.assertNotIn('Set-Cookie',dict(value.headers_sent))
    def test_foreign_duplicate_or_missing_blank_owner_is_rejected(self):
        base='/f04-restore-blank?nonce='+'a'*32+'&command=1&phase=off'
        for path in (base+'&nonce='+'a'*32,base+'&extra=1',base.replace('&command=1',''),
                     base.replace('command=1','command=0'),base.replace('phase=off','phase=seed'),base.replace('a'*32,'bad')):
            with self.subTest(path=path):
                value=self.respond(path);self.assertEqual(value.code,400);self.assertEqual(value.wfile.getvalue(),b'')


class BlankBarrierEvidenceControls(unittest.TestCase):
    def test_all_callback_receipt_fields_are_required(self):
        from local_draft_contract import verify_blank_barrier
        phase=counterfeit()['phases'][1]
        for key in phase['blankBarrier']:
            with self.subTest(key=key):
                broken=copy.deepcopy(phase);del broken['blankBarrier'][key]
                with self.assertRaises((ValueError,KeyError,TypeError)):verify_blank_barrier(broken)
    def test_callback_order_and_original_deadline_are_strict(self):
        from local_draft_contract import verify_blank_barrier
        phase=counterfeit()['phases'][1]
        changes={'startedAtElapsedRealtime':99,'committedAtElapsedRealtime':199,
                 'stoppedAtElapsedRealtime':299,'deadlineElapsedRealtime':40101}
        for key,value in changes.items():
            with self.subTest(key=key):
                broken=copy.deepcopy(phase);broken['blankBarrier'][key]=value
                with self.assertRaises(ValueError):verify_blank_barrier(broken)
    def test_old_blank_foreign_nonce_command_phase_epoch_and_uncompleted_fail(self):
        from local_draft_contract import verify_blank_barrier
        phase=counterfeit()['phases'][1]
        changes={'uri':'about:blank','nonce':'3'*32,'command':4,'phase':'fresh-on',
                 'commitEpoch':3,'completed':False,'error':'failed','fixturePreparation':False,'realChatGPT':True}
        for key,value in changes.items():
            with self.subTest(key=key):
                broken=copy.deepcopy(phase);broken['blankBarrier'][key]=value
                with self.assertRaises(ValueError):verify_blank_barrier(broken,nonce='2'*32,command=2)
    def test_bool_and_missing_observed_times_are_not_integer_receipts(self):
        from local_draft_contract import verify_blank_barrier
        phase=counterfeit()['phases'][1]
        for key in ('schema','command','session','requestedAtElapsedRealtime','startedAtElapsedRealtime',
                    'committedAtElapsedRealtime','stoppedAtElapsedRealtime','deadlineElapsedRealtime','requestEpoch','commitEpoch'):
            for value in (True,-1,None):
                with self.subTest(key=key,value=value):
                    broken=copy.deepcopy(phase);broken['blankBarrier'][key]=value
                    with self.assertRaises((ValueError,TypeError)):verify_blank_barrier(broken)
    def test_actual_event_owner_cannot_be_rebound_even_when_phase_payload_matches(self):
        value=counterfeit();phase=value['phases'][1];proof=phase['blankBarrier']
        proof['nonce']='f'*32;proof['uri']=proof['uri'].replace('2'*32,'f'*32)
        raw=device(value)
        with self.assertRaisesRegex(ValueError,'blank barrier invocation binding'):
            verify_local_draft_policy(value,device=raw,source='a'*40)


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


class RestorationStabilityHostReceiptControls(unittest.TestCase):
    """Counterfeit host receipts exercise the exact validator used by profile."""
    def setUp(self):
        spec=importlib.util.spec_from_file_location('f04_stability_receipt_contract',ROOT/'tests/local-draft-restoration-stability-host/run.py')
        self.contract=importlib.util.module_from_spec(spec);spec.loader.exec_module(self.contract)
        self.source='a'*40;self.files={'controlled/source.java':'b'*64};self.jar='c'*64
        self.selected=[dict(signature='controlled selected member',sha256='d'*64)]
        self.value=dict(status='passed',sourceCommit=self.source,sourceFiles=self.files,
            jsonJarSha256=self.jar,selectedMembers=self.selected,
            oldAwaitRestoredSha256='6350f73e7922a795a39faf4a5e55e739e253ddff7bb2b6846aa8d5d57379cec8',
            executionInputsUnchanged=True,actualAndroidExecution=False,actualGeckoExecution=False,
            actualFixtureMethodExecuted=True,releaseAcceptance=False)
        for name,count,status,variant in (('candidate',25,'passed','candidate'),('before',2,'reproduced-old-clock-gap','before-exact-inverse')):
            self.value[name]=dict(status=status,variant=variant,checkCount=count,
                checks=[dict(name=name+str(i),**{'pass':True}) for i in range(count)],
                actualFixtureMethodExecuted=True,actualAndroidExecution=False,actualGeckoExecution=False,releaseAcceptance=False)
    def verify(self,value):return self.contract.verify_report(value,self.source,self.files,self.jar,self.selected)
    def test_only_complete_source_bound_host_receipt_is_accepted(self):self.verify(self.value)
    def test_changed_or_boolean_host_counts_are_rejected(self):
        for section in ('candidate','before'):
            for count in (True,0,1,24,26):
                with self.subTest(section=section,count=count):
                    value=copy.deepcopy(self.value);value[section]['checkCount']=count
                    with self.assertRaises(ValueError):self.verify(value)
    def test_missing_failed_duplicate_or_empty_controls_are_rejected(self):
        for section in ('candidate','before'):
            for change in ('missing','failed','duplicate','empty'):
                value=copy.deepcopy(self.value);rows=value[section]['checks']
                if change=='missing':rows.pop()
                elif change=='failed':rows[0]['pass']=False
                elif change=='duplicate':rows[0]['name']=rows[1]['name']
                else:rows[0]['name']=' '
                with self.subTest(section=section,change=change),self.assertRaises(ValueError):self.verify(value)
    def test_android_or_release_scope_claims_are_rejected(self):
        for section in (None,'candidate','before'):
            for field,wrong in (('actualAndroidExecution',True),('actualGeckoExecution',True),('actualFixtureMethodExecuted',False),('releaseAcceptance',True)):
                value=copy.deepcopy(self.value);row=value if section is None else value[section];row[field]=wrong
                with self.subTest(section=section,field=field),self.assertRaises(ValueError):self.verify(value)
    def test_foreign_source_input_or_json_jar_is_rejected(self):
        for key,wrong in (('sourceCommit','f'*40),('sourceFiles',{}),('jsonJarSha256','f'*64),('executionInputsUnchanged',False)):
            value=copy.deepcopy(self.value);value[key]=wrong
            with self.subTest(key=key),self.assertRaises(ValueError):self.verify(value)
    def test_selected_or_old_full_method_identity_cannot_be_changed(self):
        for key,wrong in (('selectedMembers',[]),('oldAwaitRestoredSha256','f'*64)):
            value=copy.deepcopy(self.value);value[key]=wrong
            with self.subTest(key=key),self.assertRaises(ValueError):self.verify(value)
    def test_reproduced_old_false_acceptance_cannot_be_promoted_to_passed(self):
        value=copy.deepcopy(self.value);value['before']['status']='passed'
        with self.assertRaises(ValueError):self.verify(value)


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


if __name__=='__main__':
    program=unittest.main(exit=False)
    print(json.dumps({'blankBarrierControls':BlankBarrierControls.host_report},sort_keys=True))
    raise SystemExit(0 if program.result.wasSuccessful() else 1)
