"""Read-only startup diagnostic guards. No Android or release-acceptance claim."""
import ast
import copy
import hashlib
import importlib.util
import json
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import types
import unittest

ROOT=Path(__file__).resolve().parents[1]
def load(name,path):
    spec=importlib.util.spec_from_file_location(name,path);module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module);return module
member=load('readiness_member',ROOT/'tests/page-recovery-host/run.py').member
transport=load('readiness_transport_controls',ROOT/'tests/gecko_event_transfer_test.py')
SOURCE=ROOT/'tests/gecko/GeckoIntegrationTestActivity.java'
# Original complete bodies at 62a0ff6; remove only named observation calls and
# the exact reviewed additions below, then require these unchanged goldens.
# This is not a replacement device oracle.
ORIGINAL_METHODS={'synchronized void command(': '28954f98e5807eda05494f3716e3f3d2866217eccdac755185c906769162f6a4', 'void waitReady(long serial)': 'cac08fc6d5c0bb7092bb87905c6547efd5187b7ddb168277fba0690230fa3772', 'boolean processForeground()': 'df65dff28876bad373c0b20b9b820dd60946bb12140ccc97280ff450902c2c04', 'protected void onResume()': 'f5c8d29f9cff599577d6416482f715bbd42097d924529b6e3b9b5308901f6dc0', 'protected void onPause()': 'b6a3f4656b0ecc47fe225fd8710646f00ef9dcbdb18e59b494cac26bbe33ce6e', 'protected void onDestroy()': 'abdf66b2085cda5d994492a77ba22a4b6e7f80b311af7a3e28b10bdcbeb95829', 'void loadFixture(long serial)': 'caf9bf560d4e157f975b27added5f0210b2c81ffda7280d47ba998b1eefa0c65', 'void poll(long serial)': 'a36032d9a1d1b333a9ecd3ef82a96bcb19e2088f121920d5b415291bd47adc4b', 'protected void onNewIntent(Intent intent)': '1825fe08cb019f8ded253ac6fe6ba92b29245581401d656688c2597823ceb93d'}
ORIGINAL_RUN_AST='6408387c50d14aa180be171f999763cff35d618698937f5601c2f3b0c55be5ed'

def unobserve(text):
    text=re.sub(r'observeReadiness\((?:serial|run),"[A-Za-z-]+",(?:true|false)\);','',text)
    text=text.replace('observeReadinessNetwork(serial,identity,available,now);','')
    text=text.replace('    readinessObservation="read".equals(action)?new DeviceReadinessObservation(SystemClock.elapsedRealtime()):null;\n','')
    text=text.replace('    readinessForeground=null;readinessForegroundAt=0;readinessNetwork=null;\n','')
    text=text.replace('return observeProcessForeground("RESUMED".equals(lifecycle.getClass().getMethod("getCurrentState").invoke(lifecycle).toString()));','return "RESUMED".equals(lifecycle.getClass().getMethod("getCurrentState").invoke(lifecycle).toString());')
    text=text.replace('return observeProcessForeground(false);','return false;')
    return re.sub(r'\s+','',text)

def run_node(source):
    # Parse the actual UTF-8 source bytes so a conflicting coding declaration
    # cannot make the guard accept different Python runtime string literals.
    main=next(x for x in ast.parse(source.encode('utf-8')).body if isinstance(x,ast.FunctionDef) and x.name=='main')
    return next(x for x in main.body if isinstance(x,ast.FunctionDef) and x.name=='run')

def require(value,message):
    if not value:raise ValueError('Readiness preservation: '+message)

def verify_startup_member(source,needle):
    if needle in ('synchronized void command(','protected void onDestroy()'):
        from experience46_source_compatibility import experience46_source_bytes
        source=experience46_source_bytes(source.encode('utf-8'),'tests/gecko/GeckoIntegrationTestActivity.java').decode('utf-8')
    raw=member(source,needle)
    body=unobserve(raw)
    if needle=='void waitReady(long serial)':
        # F04 adds one dispatch only after the same original ready/route gates.
        # Its exact location and complete body are required; it is not a general
        # permission to remove arbitrary action branches before comparing goldens.
        prior='if("uploadLifecycle".equals(action)){GeckoUploadLifecycleIntegration.run(this,serial);return;}'
        added='if("localDraftPolicy".equals(action)){GeckoLocalDraftIntegration.run(this,serial);return;}'
        following='if("pageContinuity".equals(action)){ChatPageContinuityIntegration.run(this,serial);return;}'
        # The legacy golden removes whitespace even inside literals. Before that
        # comparison, require the new dispatch's actual literals and identifiers;
        # only whitespace between tokens may vary in this reviewed addition.
        tokens=lambda text:re.findall(r'"(?:\\.|[^"\\])*"|\'(?:\\.|[^\'\\])*\'|[A-Za-z_$][A-Za-z0-9_$]*|[^\s]',text)
        actual=tokens(raw);expected=tokens(prior+added+following)
        require(sum(actual[i:i+len(expected)]==expected for i in range(len(actual)))==1,'exact F04 dispatch tokens and position')
        require(body.count(added)==1 and body.count(prior+added+following)==1,'exact F04 dispatch and position')
        body=body.replace(prior+added+following,prior+following,1)
        # The appearance fixture adds one exact dispatch after the same ready
        # gates and page-continuity branch. Keep its full token/position check
        # separate from F04, then recover the unchanged original startup body.
        appearance_prior=following
        appearance_added='if("appearanceSync".equals(action)){GeckoAppearanceIntegration.run(this,serial);return;}'
        appearance_following='if("usability".equals(action)){usability(serial);return;}'
        expected=tokens(appearance_prior+appearance_added+appearance_following)
        require(sum(actual[i:i+len(expected)]==expected for i in range(len(actual)))==1,'exact appearance dispatch tokens and position')
        require(body.count(appearance_added)==1 and body.count(appearance_prior+appearance_added+appearance_following)==1,'exact appearance dispatch and position')
        body=body.replace(appearance_prior+appearance_added+appearance_following,appearance_prior+appearance_following,1)
    require(hashlib.sha256(body.encode()).hexdigest()==ORIGINAL_METHODS[needle],'original startup body changed: '+needle)
    return True

def verify_runner_consumer(source):
    from reading_zoom_trace_contract import strip_reviewed_reading_trace_additions
    source=strip_reviewed_reading_trace_additions(source.encode('utf-8'),'tests/gecko/run_device.py').decode('utf-8')
    run=copy.deepcopy(run_node(source))
    dump=lambda node:ast.dump(node,include_attributes=False)
    statement=lambda text:ast.parse(text.encode('utf-8')).body[0]
    # Only this exact diagnostic wrapper may replace the old read at its
    # original site. Stripping arbitrary try/except or callbacks would permit
    # swallowing the sequence failure or changing the consumer's deadline.
    wrapped=statement('event=read_with_sequence_failure_diagnostics(transfer,receipt,filtered_log=output,out=OUT,adb=args.adb,serial=args.serial)')
    original_read=statement('event=transfer.read(receipt)')
    reads=[node for node in ast.walk(run) if isinstance(node,ast.Assign) and dump(node)==dump(wrapped)]
    require(len(reads)==1,'exact unique sequence-diagnostic read wrapper')
    reads[0].value=original_read.value
    # F06 owns slot 8 and a copy of its result. Remove only these exact statements
    # at the two reviewed insertion points, then require the original whole AST.
    activity=statement("activity='GeckoIntegrationTestActivity' if context==1 else 'ProfileGeckoIntegrationActivity1'")
    select=statement("if action=='downloadResume':\n assert context==8\n activity='DownloadResumeIntegrationActivity'")
    result=statement("result=event['result']")
    retain=statement("if action=='downloadResume':\n report.setdefault('savedFileDeletion',{})['downloadResume']=result")
    found=[i for i,node in enumerate(run.body) if dump(node)==dump(activity)]
    require(len(found)==1,'unique original Activity selection')
    index=found[0]+1
    require(index<len(run.body) and dump(run.body[index])==dump(select),'exact F06 Activity branch and position')
    run.body.pop(index)
    condition=statement("if event.get('kind')==kind:\n pass").test
    matches=[node for node in ast.walk(run) if isinstance(node,ast.If) and dump(node.test)==dump(condition)]
    require(len(matches)==1,'unique original result consumer')
    body=matches[0].body
    require(len(body)>2 and dump(body[0])==dump(result) and dump(body[1])==dump(retain),'exact F06 result retention and position')
    body.pop(1)
    require(hashlib.sha256(dump(run).encode()).hexdigest()==ORIGINAL_RUN_AST,'original runner consumer changed')
    return True

class ReadinessObservationControls(unittest.TestCase):
    def test_original_startup_methods_and_callbacks_preserved(self):
        original=SOURCE.read_text()
        for needle,sha in ORIGINAL_METHODS.items():
            with self.subTest(member=needle):self.assertTrue(verify_startup_member(original,needle))

    def test_preservation_guard_detects_timeout_and_admission_mutants(self):
        original=SOURCE.read_text();needle='void waitReady(long serial)'
        for candidate in [original.replace('initialRouteSamples<3','initialRouteSamples<1'),original.replace('!web.ready','false'),original.replace('waitReady(serial),200','waitReady(serial),1000')]:
            self.assertNotEqual(hashlib.sha256(unobserve(member(candidate,needle)).encode()).hexdigest(),ORIGINAL_METHODS[needle])

    def test_original_runner_consumer_preserved(self):
        self.assertTrue(verify_runner_consumer((ROOT/'tests/gecko/run_device.py').read_text()))

    def test_exact_new_cases_preserve_original_goldens_and_allow_python_formatting(self):
        original=(ROOT/'tests/gecko/run_device.py').read_text()
        self.assertTrue(verify_runner_consumer('# harmless comment\n'+original.replace("action=='downloadResume'", 'action == "downloadResume"')))
        self.assertTrue(verify_startup_member(SOURCE.read_text().replace('GeckoLocalDraftIntegration.run(this,serial);','GeckoLocalDraftIntegration.run(this, serial);'),'void waitReady(long serial)'))
        self.assertTrue(verify_startup_member(SOURCE.read_text().replace('if("localDraftPolicy".equals(action)){GeckoLocalDraftIntegration.run(this,serial);return;}',
            'if ( "localDraftPolicy" . equals ( action ) ) {\n GeckoLocalDraftIntegration . run ( this , serial ) ;\n return ; }'),'void waitReady(long serial)'))
        self.assertEqual(ORIGINAL_RUN_AST,'6408387c50d14aa180be171f999763cff35d618698937f5601c2f3b0c55be5ed')
        self.assertEqual(ORIGINAL_METHODS['void waitReady(long serial)'],'cac08fc6d5c0bb7092bb87905c6547efd5187b7ddb168277fba0690230fa3772')

    def test_f04_cannot_bypass_change_duplicate_or_reorder_original_readiness(self):
        original=SOURCE.read_text();needle='void waitReady(long serial)'
        line='    if("localDraftPolicy".equals(action)){GeckoLocalDraftIntegration.run(this,serial);return;}\n'
        mutants=[original.replace(line,''),original.replace(line,line+line),
                 original.replace('"localDraftPolicy"','"local DraftPolicy"'),
                 original.replace('GeckoLocalDraftIntegration.run','Gecko LocalDraftIntegration.run'),
                 original.replace('GeckoLocalDraftIntegration.run(this,serial);','GeckoLocalDraftIntegration.run(this,serial);session.networkReady=true;'),
                 original.replace(line,'').replace('    if(!web.ready)',line+'    if(!web.ready)'),
                 original.replace('initialRouteSamples<3','initialRouteSamples<1'),
                 original.replace('now-initialRouteStableSince<500','now-initialRouteStableSince<0'),
                 original.replace('!web.ready','false'),original.replace('!activityResumed||!processForeground()','false'),
                 original.replace('waitReady(serial),50','waitReady(serial),5'),
                 original.replace('waitReady(serial),100','waitReady(serial),1000'),
                 original.replace('waitReady(serial),200','waitReady(serial),2000')]
        for i,candidate in enumerate(mutants):
            self.assertNotEqual(candidate,original)
            with self.subTest(mutant=i),self.assertRaises(ValueError):verify_startup_member(candidate,needle)

    def test_appearance_dispatch_cannot_bypass_change_duplicate_or_reorder_original_readiness(self):
        original=SOURCE.read_text();needle='void waitReady(long serial)'
        line='    if("appearanceSync".equals(action)){GeckoAppearanceIntegration.run(this,serial);return;}\n'
        self.assertEqual(original.count(line),1)
        formatted='    if ( "appearanceSync" . equals ( action ) ) {\n GeckoAppearanceIntegration . run ( this , serial ) ;\n return ; }\n'
        self.assertTrue(verify_startup_member(original.replace(line,formatted,1),needle))
        mutants=[original.replace(line,''),original.replace(line,line+line),
                 original.replace('"appearanceSync"','"appearance Sync"'),
                 original.replace('GeckoAppearanceIntegration.run','Gecko AppearanceIntegration.run'),
                 original.replace('GeckoAppearanceIntegration.run','GeckoAppearanceIntegration.changed'),
                 original.replace('GeckoAppearanceIntegration.run(this,serial);','GeckoAppearanceIntegration.run(this,run);'),
                 original.replace(line,'').replace('    if(!web.ready)',line+'    if(!web.ready)'),
                 original.replace('GeckoAppearanceIntegration.run(this,serial);','GeckoAppearanceIntegration.run(this,serial);session.networkReady=true;')]
        for i,candidate in enumerate(mutants):
            self.assertNotEqual(candidate,original)
            with self.subTest(mutant=i),self.assertRaises(ValueError):verify_startup_member(candidate,needle)

    def test_f06_cannot_change_original_consumer_or_new_case_ownership(self):
        original=(ROOT/'tests/gecko/run_device.py').read_text()
        select="        if action=='downloadResume':\n            assert context==8\n            activity='DownloadResumeIntegrationActivity'\n"
        retained="                    if action=='downloadResume':\n                        report.setdefault('savedFileDeletion',{})['downloadResume']=result\n"
        mutants=[original.replace(select,''),original.replace(select,select+select),
                 original.replace('assert context==8','assert context==1'),
                 original.replace("activity='DownloadResumeIntegrationActivity'","activity='GeckoIntegrationTestActivity'"),
                 original.replace(retained,''),original.replace(retained,retained+retained),
                 original.replace("report.setdefault('savedFileDeletion',{})['downloadResume']=result","steps.append(event)"),
                 original.replace('deadline=time.monotonic()+120','deadline=time.monotonic()+121'),
                 original.replace('slot=context-1','slot=context'),
                 original.replace('event_transfers.append(transfer_record)','event_transfers.clear()'),
                 original.replace("logs.append(output);steps.append(event);print(json.dumps(event),flush=True)","logs.append(output);print(json.dumps(event),flush=True)")]
        for i,candidate in enumerate(mutants):
            self.assertNotEqual(candidate,original)
            with self.subTest(mutant=i),self.assertRaises(ValueError):verify_runner_consumer(candidate)

    def test_sequence_diagnostics_cannot_change_consumer_calls_actions_or_deadline(self):
        original=(ROOT/'tests/gecko/run_device.py').read_text()
        wrapper='event=read_with_sequence_failure_diagnostics(transfer,receipt,filtered_log=output,out=OUT,adb=args.adb,serial=args.serial)'
        mutants=[original.replace(wrapper,'event=transfer.read(receipt)'),
                 original.replace(wrapper,wrapper+';event=transfer.read(receipt)'),
                 original.replace('filtered_log=output','filtered_log="replacement"'),
                 original.replace('out=OUT,adb=args.adb','out=OUT,adb="alternate-adb"'),
                 original.replace('serial=args.serial)','serial="alternate-device")'),
                 original.replace(wrapper,wrapper+';deadline=time.monotonic()+120'),
                 original.replace(wrapper,wrapper+';steps.append(event)'),
                 original.replace(wrapper,wrapper+';adb("shell","am","force-stop",package)'),
                 original.replace('deadline=time.monotonic()+120','deadline=time.monotonic()+121'),
                 original.replace("if receipt.get('runNonce')!=nonce or receipt.get('processSlot')!=context-1:continue",'if False:continue')]
        for i,candidate in enumerate(mutants):
            self.assertNotEqual(candidate,original)
            with self.subTest(mutant=i),self.assertRaises(ValueError):verify_runner_consumer(candidate)

    def test_command_entry_precedes_wait_and_only_read_is_observed(self):
        command=member(SOURCE.read_text(),'synchronized void command(')
        self.assertLess(command.index('new IntegrationEventStore('),command.index('"command-entered"'))
        self.assertLess(command.index('"command-entered"'),command.index('waitReady(serial)'))
        self.assertIn('readinessObservation="read".equals(action)?',command)
        observation=member(SOURCE.read_text(),'void observeReadiness(long serial,')
        self.assertIn('eventStore.command!=serial',observation)
        self.assertIn('serial!=run',observation)
        self.assertIn('"diagnosticOnly",true,"acceptance",false',observation)

    def test_snapshot_is_cached_and_has_all_requested_gates(self):
        body=member(SOURCE.read_text(),'void observeReadiness(long serial,')
        for forbidden in ['evaluateJavascript','loadUrl','reconnect(','getActiveNetwork','getNetworkCapabilities','getSharedPreferences','ProfileCatalog','setBlocked','guard.allowed()','postDelayed','isOpen()']:
            self.assertNotIn(forbidden,body)
        for field in ['extensionPresent','checkpointReady','identityPrepared','routePrepared','privacyReady','routePortPresent','policyAcknowledged','rfpAcknowledged','surface','activityResumed','processForeground','networkObservation','ownerSlot','environmentId','environmentGeneration']:
            self.assertIn('"'+field+'"',body)
        self.assertIn('"guardBlocked",session.guard.blocked',body)
        self.assertIn('"primaryPresent",web.primary!=null',body)
        self.assertIn('"processForeground",readinessForeground==null?JSONObject.NULL',body)

    def test_actual_budget_is_bounded_and_does_not_schedule(self):
        source=ROOT/'tests/gecko/DeviceReadinessObservation.java'
        program='''package local.pocketchat;
public class BudgetChecks {
 static class Observer {DeviceReadinessObservation readinessObservation;Boolean readinessForeground;long readinessForegroundAt;
  static class SystemClock {static long elapsedRealtime(){return 17;}}
  /* ACTUAL_OBSERVER */
 }
 static int checks;static void check(boolean x){if(!x)throw new AssertionError("budget check "+checks);checks++;}
 public static void main(String[] args){
  DeviceReadinessObservation b=new DeviceReadinessObservation(100);
  check(b.sample(100,true)&&b.emit(100,"command",true)&&b.emitted==1);
  check(!b.sample(101,false));
  check(b.sample(350,false)&&!b.emit(350,"command",false));
  check(b.sample(600,false)&&b.emit(600,"browser",false));
  check(b.sample(1100,false)&&b.emit(1100,"browser",false));
  check(b.sample(1400,false)&&!b.emit(1400,"browser",false));
  for(long t:new long[]{5100,30100,60100,110100})check(b.sample(t,false)&&b.emit(t,"browser",false));
  for(int i=0;i<100;i++)if(b.sample(120000+i,true))b.emit(120000+i,"lifecycle"+i,true);
  check(b.emitted==24);check(!b.sample(999999,true)&&!b.emit(999999,"late",true));
  DeviceReadinessObservation c=new DeviceReadinessObservation(20);check(c.emitted==0&&c.sample(20,true)&&c.emit(20,"new-command",true));
  check(!c.sample(19,false));
  Observer o=new Observer();check(o.observeProcessForeground(true)&&o.readinessForeground==null);
  check(!o.observeProcessForeground(false)&&o.readinessForeground==null);
  o.readinessObservation=new DeviceReadinessObservation(0);
  check(o.observeProcessForeground(true)&&o.readinessForeground&&o.readinessForegroundAt==17);
  check(!o.observeProcessForeground(false)&&!o.readinessForeground&&o.readinessForegroundAt==17);
  System.out.println("budgetChecks="+checks);
 }
}'''
        program=program.replace('/* ACTUAL_OBSERVER */',member(SOURCE.read_text(),'boolean observeProcessForeground('))
        with tempfile.TemporaryDirectory(prefix='device-readiness-budget-') as name:
            directory=Path(name);java=directory/'BudgetChecks.java';java.write_text(program)
            subprocess.run(['javac','-d',str(directory),str(source),str(java)],check=True,capture_output=True,text=True)
            result=subprocess.run(['java','-cp',str(directory),'local.pocketchat.BudgetChecks'],check=True,capture_output=True,text=True)
            self.assertEqual(result.stdout.strip(),'budgetChecks=18')
        self.assertNotIn('Thread',source.read_text());self.assertNotIn('post',source.read_text())

    def test_independent_diagnostic_tag_cannot_complete_or_shift_business(self):
        receipt,raw=transport.packet()
        bindings,calls=transport.GeckoEventTransportControls().device_runner_control(receipt,raw)
        clock=types.SimpleNamespace(now=0)
        line='10-25 00:00 I PocketReadiness: '+json.dumps(dict(kind='readinessObservation',diagnosticOnly=True,acceptance=False))
        def adb(*parts):return line if parts==('logcat','-d','-s','PocketGeckoIntegration:I','*:S') else ''
        bindings.update(adb=adb,time=types.SimpleNamespace(monotonic=lambda:clock.now,sleep=lambda n:setattr(clock,'now',clock.now+121)))
        with tempfile.TemporaryDirectory() as directory:
            bindings['OUT']=Path(directory)
            with self.assertRaisesRegex(TimeoutError,'No integration result: 1, read, fixture'):bindings['run'](1,'read')
        self.assertEqual(bindings['steps'],[]);self.assertEqual(bindings['event_transfers'][0]['events'],[])
        self.assertIsNone(transport.transfer.parse_receipt_line(line))
        fresh,unused=transport.GeckoEventTransportControls().device_runner_control(receipt,raw)
        with contextlib_redirect():value=fresh['run'](1,'read')
        self.assertEqual(value,{'context':'1','action':'read'})
        self.assertEqual(fresh['event_transfers'][0]['events'][0]['receipt']['sequence'],1)

    def diagnostic(self):
        node=next(n for n in ast.parse((ROOT/'tests/gecko/run_device.py').read_text()).body if isinstance(n,ast.FunctionDef) and n.name=='collect_readiness')
        bindings={'json':json};exec(compile(ast.Module(body=[node],type_ignores=[]),'<actual-diagnostic-collector>','exec'),bindings)
        identity=transport.identity();nonce='e'*32
        value=dict(schema=1,kind='readinessObservation',diagnosticOnly=True,acceptance=False,
                   **{k:identity[k] for k in ('sourceCommit','sourceTree','apkSha256','buildStampSha256')},
                   runNonce=nonce,fixtureAction='read',processSlot=0,command=1,businessSequence=0,
                   observation=dict(diagnosticOnly=True,acceptance=False,maxObservations=24,observation=1))
        def collect(candidate):return bindings['collect_readiness']('10-25 00:00 I PocketReadiness: '+json.dumps(candidate),identity,[dict(runNonce=nonce,fixtureAction='read',processSlot=0)])
        return value,collect

    def test_diagnostic_sidecar_keeps_valid_source_owned_raw_without_acceptance(self):
        value,collect=self.diagnostic();result=collect(value)
        self.assertFalse(result['acceptance']);self.assertTrue(result['observations'][0]['valid'])
        self.assertEqual(json.loads(result['observations'][0]['raw']),value)
        publisher=member(SOURCE.read_text(),'void publishReadiness(')
        self.assertNotIn('eventStore.emit',publisher);self.assertNotIn('event(serial',publisher)
        self.assertIn('Log.i("PocketReadiness",raw)',publisher)
        self.assertIn('length>3500',publisher)

    def test_diagnostic_rejects_wrong_identity_owner_missing_sequence_and_oversize(self):
        value,collect=self.diagnostic()
        for key,replacement in [('sourceCommit','f'*40),('apkSha256','f'*64),('runNonce','f'*32),('processSlot',1),('command',0),('acceptance',True)]:
            bad=copy.deepcopy(value);bad[key]=replacement
            with self.subTest(field=key):self.assertFalse(collect(bad)['observations'][0]['valid'])
        for change in [dict(observation=2),dict(observation=25),dict(maxObservations=25)]:
            bad=copy.deepcopy(value);bad['observation'].update(change);self.assertFalse(collect(bad)['observations'][0]['valid'])
        bad=copy.deepcopy(value);bad['large']='x'*3501;self.assertFalse(collect(bad)['observations'][0]['valid'])

    def test_failure_capture_preserves_error_and_writes_valid_bounded_json(self):
        node=next(n for n in ast.walk(ast.parse((ROOT/'tests/gecko/run_device.py').read_text())) if isinstance(n,ast.FunctionDef) and n.name=='failure_runtime')
        calls=[]
        def run(command,**kwargs):
            calls.append((command,kwargs));self.assertEqual(kwargs['timeout'],5)
            if len(calls)==2:raise subprocess.TimeoutExpired(command,5)
            return types.SimpleNamespace(returncode=0,stdout='x'*140000,stderr='')
        with tempfile.TemporaryDirectory() as directory:
            report=dict(status='failed',error='original-read-timeout')
            bindings=dict(args=types.SimpleNamespace(adb='adb',serial='owned-native'),subprocess=types.SimpleNamespace(run=run),OUT=Path(directory),prefix='',identity=transport.identity(),report=report,json=json)
            exec(compile(ast.Module(body=[node],type_ignores=[]),'<actual-failure-capture>','exec'),bindings)
            bindings['failure_runtime']();result=json.loads((Path(directory)/'device-failure-runtime.json').read_text())
            self.assertEqual(report,dict(status='failed',error='original-read-timeout'))
            self.assertEqual(result['originalError'],'original-read-timeout');self.assertFalse(result['acceptance'])
            self.assertEqual(len(result['observations']),4);self.assertTrue(result['observations'][0]['truncated'])
            self.assertEqual(len(result['observations'][0]['stdout']),131072)
            self.assertIn('TimeoutExpired',result['observations'][1]['error'])

    def test_failure_capture_is_read_only_and_outside_original_deadline(self):
        source=(ROOT/'tests/gecko/run_device.py').read_text();tree=ast.parse(source)
        main=next(x for x in tree.body if isinstance(x,ast.FunctionDef) and x.name=='main')
        nested=[x for x in ast.walk(main) if isinstance(x,ast.FunctionDef) and x.name=='failure_runtime']
        self.assertEqual(len(nested),1);capture=ast.unparse(nested[0])
        for command in ["('dumpsys', 'activity', 'activities')","('dumpsys', 'window', 'windows')","('ps', '-A')","('cat', '/proc/meminfo')"]:self.assertIn(command,capture)
        for denied in ['force-stop','kill','input','start','connect','logcat']:self.assertNotIn(denied,capture)
        self.assertNotIn('failure_runtime',ast.unparse(run_node(source)))
        self.assertIn('timeout=5',capture);self.assertIn('131072',capture)
        self.assertLess(source.index('write_reports()\n        if report.get'),source.index('def failure_runtime'))


def contextlib_redirect():
    import contextlib,io
    return contextlib.redirect_stdout(io.StringIO())
if __name__=='__main__':unittest.main()
