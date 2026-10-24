"""Counterfeit trace/transport/order controls only; no Android samples are made."""
import ast
import copy
import hashlib
import importlib.util
import json
from pathlib import Path
import struct
import subprocess
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools/gecko'))
import experience_save_trace as T
import experience_scenarios as S
import run_experience_comparison as C
from gecko_event_transfer_test import identity, event, packet


METHODS = [
    '0\tlocal.pocketchat.ExperienceScenarios\tsaveStep\t(I)V\tExperienceScenarios.java',
    '0x4\tlocal.pocketchat.DownloadTasks\tsave\t()V\tDownloadTasks.java',
    '0x8\tlocal.pocketchat.DownloadTasks\tsave\t(Z)V\tDownloadTasks.java',
    '0xc\tlocal.pocketchat.DownloadLibrary\tprune\t(Lorg/json/JSONArray;)Lorg/json/JSONArray;\tDownloadLibrary.java',
    '0x10\torg.json.JSONObject\ttoString\t()Ljava/lang/String;\tJSONObject.java',
    '0x14\tandroid.app.SharedPreferencesImpl$EditorImpl\tcommit\t()Z\tSharedPreferencesImpl.java',
    '0x18\tlocal.pocketchat.DownloadLibrary\tsync\t(Landroid/content/Context;Lorg/json/JSONArray;)V\tDownloadLibrary.java',
]


def trace(*, version=3, clock=None, pid=1234, threads=None, methods=None, records=None, metadata=None):
    """Synthetic ART-format bytes for parser controls, never device evidence."""
    clock = clock or ('dual' if version == 3 else 'wall')
    records = records or [
        (7, 0, 0, 0), (7, 4, 10, 100), (7, 8, 10, 100),
        (7, 12, 20, 200), (7, 16, 25, 250), (7, 17, 30, 300), (7, 13, 40, 400),
        (7, 20, 50, 500), (7, 21, 60, 1000),
        (7, 16, 65, 1100), (7, 17, 70, 1200),
        (7, 9, 80, 1300), (7, 5, 90, 1400), (7, 1, 100, 1500)]
    values = dict(pid=str(pid), vm='art', clock=clock, **{'data-file-overflow':'false', 'elapsed-time-usec':'2000', 'num-method-calls':str(len(records))})
    values.update(metadata or {})
    text = '*version\n'+str(version)+'\n'+'\n'.join(key+'='+value for key,value in values.items())
    text += '\n*threads\n'+'\n'.join(threads or ['7\tAndroidUI'])+'\n*methods\n'+'\n'.join(methods or METHODS)+'\n*end\n'
    binary = bytearray(32);binary[:4]=b'SLOW';struct.pack_into('<HHQ',binary,4,version,32,1000000)
    if version == 3: struct.pack_into('<H', binary, 16, 14)
    for tid, method, cpu, wall in records:
        binary += struct.pack('<HIII',tid,method,cpu,wall) if version == 3 else struct.pack('<HII',tid,method,wall if clock=='wall' else cpu)
    return text.encode()+binary


def parse(raw):
    return T.parse_trace(raw, expected_pid=1234, main_tid=1234, main_thread_name='AndroidUI')


def inventory(root):
    return [dict(path=str(path.relative_to(root)), bytes=path.stat().st_size, sha256=hashlib.sha256(path.read_bytes()).hexdigest())
            for path in sorted(root.rglob('*')) if path.is_file() and path.name != T.RESULT_FILE]


def fixture(root):
    """A counterfeit complete report used solely to prove rejection paths."""
    expected = identity(); protocol = {name:'f'*64 for name in T.OBSERVERS}; scenario = S.manifest('download-history-1000')
    build = dict(sourceCommit=expected['sourceCommit'],sourceTree=expected['sourceTree'],runId='123',runAttempt='1',apkSha256=expected['apkSha256'],apkBytes=100)
    snapshot = dict(surface=1,session=2,attachedSession=2,visibleDocument=True,networkReady=True,
                    page=dict(document='fixed',draft='unsent',cookie='session=fixed',replyFingerprint={'length':10},sendCount=0,path='/c/reload-collapse'))
    ready_snapshot = dict(snapshot,name='ready'); final_snapshot = dict(snapshot,name='diagnostic-final')
    saves=[]
    for number in range(1,9):
        start=1000+number*2000+(number-1)*100
        saves.append(dict(name='history-save-'+str(number),step=number,startUptimeMs=start,endUptimeMs=start+100,
                          startElapsedRealtimeNs=start*1000000,endElapsedRealtimeNs=(start+100)*1000000,
                          durationMs=100,received=number*65536,method='DownloadTasks.save',thread='Android main',httpTransferMeasured=False))
    verified=dict(savedRows=1000,taskRows=1001,verifiedProgressBytes=524288,actualAndroidSQLite=True,actualAndroidSharedPreferences=True)
    window=dict(name='diagnostic-history-save-sampling',start=dict(elapsedRealtimeMs=1000,uptimeMs=1000),end=dict(elapsedRealtimeMs=22000,uptimeMs=22000),elapsedDurationMs=21000,lifecycleChanges=0,frameLimitReached=False,verification=verified)
    original=trace();(root/T.TRACE_FILE).write_bytes(original)
    receipt=dict(schema=1,diagnosticOnly=True,performanceComparisonAllowed=False,runNonce='e'*32,pid=1234,mainTid=1234,mainThreadName='AndroidUI',
                 bufferBytes=T.BUFFER_BYTES,intervalUs=T.INTERVAL_US,traceUri='content://local.pocketchat.test.evidence/experience-sampling/'+'e'*32,
                 traceBytes=len(original),traceSha256=hashlib.sha256(original).hexdigest(),completedEightSaves=True,verification=verified,
                 startRequested={'elapsedRealtimeNs':1000*1000000},stopRequested={'elapsedRealtimeNs':22000*1000000},stopped={'elapsedRealtimeNs':22001*1000000})
    seed=dict(timed=False,scenario={'manifest':scenario});ready={'fixture':'ready'}
    events=[event('snapshot',ready_snapshot),event('ready',ready),event('scenarioStarted',{'name':window['name'],'start':window['start']})]
    events += [event('scenarioSave',save) for save in saves]
    events += [event('scenarioFinished',window),event('samplingFinished',receipt),event('snapshot',final_snapshot)]
    def write(action,nonce,items):
        rows=[]
        for sequence,value in enumerate(items,1):
            pointer,raw=packet(value,fixtureAction=action,runNonce=nonce,command=1,sequence=sequence)
            rows.append(dict(receipt=pointer,rawUtf8=raw.decode()))
        (root/(action+'-transport.json')).write_text(json.dumps(rows))
        (root/(action+'-events.json')).write_text(json.dumps(items))
        (root/(action+'-log.txt')).write_text('\n'.join(json.dumps(row['receipt']) for row in rows))
    write('experienceSeed','d'*32,[event('seeded',seed)]);write(T.ACTION,'e'*32,events)
    report=dict(schema=1,status='passed',diagnosticOnly=True,performanceComparisonAllowed=False,sourceCommit=expected['sourceCommit'],actualAndroidExecution=True,
                buildIdentity=expected,installedAfter=expected,selectedRole='A',selectedBuild=build,scenarioManifest=scenario,
                formalIterationsAdded=0,formalActionsAdded=0,timedSaveSamplesAdded=0,additionalRealSaveCalls=8,additionalSaveCountComplete=True,observerFiles=protocol,executionInputsUnchanged=True,
                physicalDeviceAcceptance=False,realChatGptAcceptance=False,releaseAcceptance=False,
                runNonce='e'*32,seedNonce='d'*32,seed=seed,ready=ready,scenarioWindow=window,saves=saves,traceReceipt=receipt,
                readySnapshot=ready_snapshot,finalSnapshot=final_snapshot,traceAnalysis=parse(original))
    report['rawEvidence']=inventory(root)
    (root/T.RESULT_FILE).write_text(json.dumps(report))
    return report,expected,protocol,scenario,build


class TraceParserControls(unittest.TestCase):
    def test_zero_method_identity_and_encoded_thread_are_supported(self):
        value=parse(trace())
        self.assertEqual(value['mainTid'],1234);self.assertEqual(value['mainThreadTraceEncoding'],7)
        self.assertFalse(value['exactMethodDurations']);self.assertFalse(value['sampledEntriesAreExactCalls'])
        self.assertEqual(value['sampledOuterSaveEntries'],1)

    def test_single_clock_wall_and_cpu_are_not_confused(self):
        for clock in ('wall','thread-cpu'):
            value=parse(trace(version=2,clock=clock))
            self.assertEqual(set(value['clockWeightedResidence']),{clock})
        value=parse(trace());wall=value['clockWeightedResidence']['wall'];cpu=value['clockWeightedResidence']['thread-cpu']
        self.assertNotEqual(wall['saveStackResidenceEstimateUs'],cpu['saveStackResidenceEstimateUs'])

    def test_categories_are_disjoint_and_nested_json_stays_in_library(self):
        value=parse(trace())['clockWeightedResidence']['wall']
        self.assertEqual(value['categories']['library-prune'],200)
        self.assertEqual(value['categories']['preferences-commit'],500)
        self.assertEqual(value['categories']['json-outside-library'],100)
        self.assertEqual(sum(value['categories'].values()),value['saveStackResidenceEstimateUs'])
        self.assertEqual(value['observedBetweenStackChanges'],value['outsideSave']+value['saveStackResidenceEstimateUs'])

    def test_outer_library_stage_wins_and_unowned_saves_are_not_classified(self):
        methods={0:{'class':'local/pocketchat/ExperienceScenarios','name':'saveStep','signature':'(I)V'},4:{'class':'local/pocketchat/DownloadTasks','name':'save','signature':'()V'},8:{'class':'local/pocketchat/DownloadLibrary','name':'sync','signature':'()V'},12:{'class':'local/pocketchat/DownloadLibrary','name':'add','signature':'()V'}}
        self.assertEqual(T.category([0,4,8,12],methods),'library-sync')
        self.assertIsNone(T.category([4,8,12],methods))

    def test_missing_or_ambiguous_exact_thread_mapping_is_rejected(self):
        for threads in (['7\tother'],['7\tAndroidUI','8\tAndroidUI'],['7\tAndroidUI-other']):
            with self.subTest(threads=threads),self.assertRaises(ValueError):parse(trace(threads=threads))
        with self.assertRaises(ValueError):T.parse_trace(trace(),expected_pid=1234,main_tid=8,main_thread_name='AndroidUI')

    def test_main_only_callback_on_another_encoded_thread_is_rejected(self):
        with self.assertRaisesRegex(ValueError,'another trace thread'):
            parse(trace(threads=['7\tAndroidUI','8\tworker'],records=[(8,0,0,0),(8,4,10,100),(8,5,20,200),(8,1,30,300)]))

    def test_overflow_missing_pid_and_wrong_process_are_rejected(self):
        for metadata in ({'data-file-overflow':'true'},{'data-file-overflow':'unknown'},{'pid':'1235'},{'vm':'dalvik'}):
            with self.subTest(metadata=metadata),self.assertRaises(ValueError):parse(trace(metadata=metadata))

    def test_truncation_magic_clock_record_count_and_new_format_are_rejected(self):
        raw=trace()
        for bad in (b'',raw[:-1],raw.replace(b'SLOW',b'FAIL'),raw.replace(b'clock=dual',b'clock=wall'),trace(metadata={'num-method-calls':'1'}),trace(version=4)):
            with self.subTest(size=len(bad)),self.assertRaises(ValueError):parse(bad)
        at=raw.index(b'SLOW');bad=bytearray(raw);struct.pack_into('<H',bad,at+16,10)
        with self.assertRaises(ValueError):parse(bytes(bad))

    def test_clock_decrease_unknown_id_duplicate_methods_and_bad_stack_are_rejected(self):
        cases=[trace(records=[(7,0,10,100),(7,4,9,200)]),trace(records=[(7,0,0,0),(7,4,1,10),(7,8,2,9)]),
               trace(records=[(7,0,0,0),(7,400,1,10)]),trace(methods=METHODS+[METHODS[0]]),
               trace(records=[(7,0,0,0),(7,4,1,10),(7,1,2,20)])]
        for bad in cases:
            with self.subTest(size=len(bad)),self.assertRaises(ValueError):parse(bad)

    def test_open_final_stacks_are_disclosed_without_inventing_exit_or_tail(self):
        value=parse(trace(records=[(7,0,0,0),(7,4,1,10),(7,8,2,20)]))
        self.assertEqual(value['openStacksAtLastObservation'],{'7':3})
        self.assertFalse(value['initialAndFinalTailsEstimated'])
        self.assertEqual(value['clockWeightedResidence']['wall']['observedBetweenStackChanges'],20)


class CaptureReplayControls(unittest.TestCase):
    def setUp(self):
        self.folder=tempfile.TemporaryDirectory();self.addCleanup(self.folder.cleanup);self.root=Path(self.folder.name)
        self.report,self.expected,self.protocol,self.scenario,self.build=fixture(self.root)
    def verify(self,report=None):
        return T.verify_diagnostic(report or self.report,self.expected,self.protocol,self.scenario,self.root,self.build)
    def test_complete_counterfeit_fixture_exercises_replay_without_android_claim(self):
        self.assertEqual(self.verify()['sampledOuterSaveEntries'],1)
        self.assertEqual(len(self.report['saves']),8)
    def test_missing_raw_and_same_length_trace_corruption_are_rejected(self):
        path=self.root/T.TRACE_FILE;raw=path.read_bytes();path.write_bytes(raw[:-1]+bytes([raw[-1]^1]))
        with self.assertRaises(ValueError):self.verify()
    def test_counterfeit_host_receipt_summary_cannot_replace_owned_device_payload(self):
        for mutate in (lambda r:r['traceReceipt'].update(intervalUs=500),lambda r:r['saves'][0].update(durationMs=1),
                       lambda r:r['scenarioWindow']['verification'].update(actualAndroidSQLite=False),
                       lambda r:r.update(traceAnalysis={}),lambda r:r.update(performanceComparisonAllowed=True),
                       lambda r:r.update(timedSaveSamplesAdded=8),lambda r:r['selectedBuild'].update(runId='124'),
                       lambda r:r.update(selectedRole='B'),lambda r:r['observerFiles'].update({T.OBSERVERS[0]:'0'*64})):
            changed=copy.deepcopy(self.report);mutate(changed)
            with self.subTest(report=changed.get('selectedRole')),self.assertRaises(ValueError):self.verify(changed)
    def test_original_transport_bytes_sequences_and_log_pointers_are_required(self):
        path=self.root/(T.ACTION+'-transport.json');original=path.read_text();rows=json.loads(original);rows[0]['rawUtf8']+=' '
        path.write_text(json.dumps(rows));self.report['rawEvidence']=inventory(self.root)
        with self.assertRaises(ValueError):self.verify()
        path.write_text(original);(self.root/(T.ACTION+'-log.txt')).write_text('')
        self.report['rawEvidence']=inventory(self.root)
        with self.assertRaises(ValueError):self.verify()
    def test_unindexed_original_and_website_change_are_rejected(self):
        (self.root/'unindexed.bin').write_bytes(b'original')
        with self.assertRaises(ValueError):self.verify()
        (self.root/'unindexed.bin').unlink();self.report['finalSnapshot']['page']['draft']='changed'
        with self.assertRaises(ValueError):self.verify()


class PostBaselineControls(unittest.TestCase):
    def setUp(self):
        self.plan=dict(mode='baseline',order=['A','B','B','A'],scenarioManifest=S.manifest('download-history-1000'),repetitionsPerPhase=3,
                       protocol=C.source_hashes(ROOT,C.HARNESS+C.SETUP))
        row=dict(status='passed',startup={'activityCreateToReadyMs':100},actions=[dict(name=name,responseToDrawMs=20)for name in C.ACTIONS],cpu={'available':False},memoryReady={'available':False},memoryFinal={'available':False},frames={'allNativeHwuiFrames':[],'allChoreographerGapsMs':[]},scenarioWindows=[])
        self.reports={key:[dict(status='passed',iterations=[copy.deepcopy(row)for unused in range(3)])for unused in range(2)]for key in ('A','B')}
        self.record=dict(phases=[dict(condition=key,status='passed',iterations=3)for key in self.plan['order']],baselineRepeatability=C.summarize(self.reports['A']+self.reports['B']))
    def test_exact_12_complete_and_original_summary_are_prerequisites(self):
        self.assertTrue(C.diagnostic_preconditions(self.plan,self.record,self.reports))
        for mutate in (lambda r:r['phases'].pop(),lambda r:r['phases'][0].update(status='in_progress'),lambda r:r.update(baselineRepeatability={}),lambda r:r.update(diagnostics={'historySaveSampling':{'status':'failed'}})):
            value=copy.deepcopy(self.record);mutate(value)
            with self.assertRaises(ValueError):C.diagnostic_preconditions(self.plan,value,self.reports)
        reports=copy.deepcopy(self.reports);reports['A'][0]['iterations'][0]['actions'].pop()
        with self.assertRaises(ValueError):C.diagnostic_preconditions(self.plan,self.record,reports)
    def test_compare_core_and_changed_actual_helper_cannot_start_extra_trace(self):
        for mode,scenario in [('compare','download-history-1000'),('baseline','core')]:
            plan=dict(self.plan,mode=mode,scenarioManifest=S.manifest(scenario))
            self.assertFalse(C.diagnostic_preconditions(plan,self.record,self.reports))
        plan=copy.deepcopy(self.plan);plan['protocol'][T.OBSERVERS[0]]='0'*64
        with self.assertRaisesRegex(ValueError,'Actual workflow'):C.diagnostic_preconditions(plan,self.record,self.reports)
    def test_timeout_with_partial_report_preserves_original_cause_bytes_and_after_proof(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);args=SimpleNamespace(out=root,plan=root/'plan.json',adb='unused-adb')
            args.plan.write_text('{}');build=dict(root=str(ROOT),sourceCommit='a'*40,sourceTree='b'*40,runId='123',runAttempt='1',apkSha256='c'*64)
            plan=dict(self.plan,inputs={'A':build})
            def timed_out(*args,**kwargs):
                capture=root/'diagnostics/history-save-sampling/capture';capture.mkdir()
                (capture/T.RESULT_FILE).write_bytes(b'{"status":')
                (capture/T.TRACE_FILE).write_bytes(b'partial-original')
                raise subprocess.TimeoutExpired('diagnostic',420)
            with mock.patch.object(C,'git',return_value='a'*40),mock.patch.object(C,'prepare_target_proof',return_value={'sha256':'d'*64})as proof,mock.patch.object(C.subprocess,'run',side_effect=timed_out):
                with self.assertRaises(subprocess.TimeoutExpired):C.run_post_baseline_diagnostic(args,plan,self.record,self.reports)
            entry=self.record['diagnostics']['historySaveSampling']
            self.assertEqual(entry['status'],'failed');self.assertEqual(entry['errorType'],'TimeoutExpired')
            self.assertIn('JSONDecodeError',entry['captureReportParseError']);self.assertEqual(proof.call_count,2)
            self.assertEqual((root/'diagnostics/history-save-sampling/capture'/T.TRACE_FILE).read_bytes(),b'partial-original')
    def test_real_execute_places_extra_diagnostic_outside_all_phases_after_summary(self):
        tree=ast.parse((ROOT/'tools/gecko/run_experience_comparison.py').read_text())
        execute=next(node for node in tree.body if isinstance(node,ast.FunctionDef)and node.name=='execute')
        invoke=[node for node in ast.walk(execute)if isinstance(node,ast.Call)and isinstance(node.func,ast.Name)and node.func.id=='run_post_baseline_diagnostic']
        self.assertEqual(len(invoke),1)
        loops=[node for node in ast.walk(execute)if isinstance(node,ast.For)]
        self.assertFalse(any(invoke[0] in list(ast.walk(loop))for loop in loops))
        summaries=[node for node in ast.walk(execute)if isinstance(node,ast.Call)and isinstance(node.func,ast.Name)and node.func.id=='summarize']
        self.assertTrue(all(node.lineno<invoke[0].lineno for node in summaries))
    def test_diagnostic_document_copies_original_inputs_without_refactoring_timed_runner(self):
        original=ast.parse((ROOT/'tests/gecko/run_experience_benchmark.py').read_text())
        extra=ast.parse((ROOT/'tools/gecko/run_experience_save_diagnostic.py').read_text())
        a=next(node for node in ast.walk(original)if isinstance(node,ast.ClassDef)and node.name=='Document')
        b=next(node for node in ast.walk(extra)if isinstance(node,ast.ClassDef)and node.name=='Document')
        self.assertEqual(ast.dump(a,include_attributes=False),ast.dump(b,include_attributes=False))
    def test_java_formal_clocks_single_call_cadence_and_abort_fences_remain(self):
        source=(ROOT/'tests/gecko/ExperienceScenarios.java').read_text()
        self.assertIn('long started=SystemClock.elapsedRealtimeNanos(),up=SystemClock.uptimeMillis();\n    tasks.save();\n    long ended=SystemClock.elapsedRealtimeNanos(),endedUp=SystemClock.uptimeMillis();',source)
        self.assertEqual(source.count('    tasks.save();'),1)
        self.assertIn('if(number<8)a.handler.postDelayed(()->saveStep(number+1),2000);',source)
        guard=source.index('if(sampling!=null&&(diagnosticFinished||a.benchmarkClosed))return;')
        self.assertLess(guard,source.index('    tasks.save();'))
        activity=(ROOT/'tests/gecko/ExperienceBenchmarkActivity.java').read_text()
        self.assertIn('Formal commands are unavailable in a diagnostic invocation',activity)
        self.assertIn('if(scenario!=null)scenario.abortSampling();',activity)
        sampling=(ROOT/'tests/gecko/ExperienceSaveSampling.java').read_text()
        self.assertIn('if(active){try{Debug.stopMethodTracing();}finally{active=false;}}',sampling)
        self.assertLess(sampling.index('Debug.stopMethodTracing();'),sampling.index('Main thread name changed during sampling; profiler stopped'))
        self.assertNotIn('if(!sameName)',sampling.split('if(receipt!=null)',1)[1].split('return receipt;}')[1].split('Debug.stopMethodTracing();')[0])


if __name__=='__main__':unittest.main()
