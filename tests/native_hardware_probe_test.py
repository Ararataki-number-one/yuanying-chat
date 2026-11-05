"""Hardware probe controls. Host fixtures never establish Android/Gecko execution."""
import argparse
import contextlib
import copy
import hashlib
import importlib.util
import io
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
from zipfile import ZipFile
import yaml

ROOT = Path(__file__).resolve().parents[1]
# The isolated review mirror contains no replacement SDK or build validators.
# After selective export ROOT itself supplies these normal repository modules.
REPO_ROOT = next(path for path in (ROOT, *ROOT.parents)
    if (path / 'tools/gecko/profile_invocation_contract.py').is_file())
sys.path.insert(0, str(REPO_ROOT / 'tools/gecko'))
spec = importlib.util.spec_from_file_location('native_hardware_probe_runner', ROOT / 'tools/gecko/run_native_hardware_probe.py')
runner = importlib.util.module_from_spec(spec); spec.loader.exec_module(runner)
SOURCE = 'a' * 40; TREE = 'b' * 40; NONCE = 'c' * 32
IDENTITY = {'controlledHostInputOnly': True}


def packet(role, phase, count):
    return dict(schema=1, nonce=NONCE, sourceCommit=SOURCE, role=role, phase=phase,
        status='observed', observation=dict(hardwareConcurrency=count, nativeGetter=True), error=None)


def ack(phase, mode='standard', readback=False):
    operation = 'read' if readback or phase == 'baseline' else ('reset' if phase == 'reset' else 'set')
    cap = {'cap2': 2, 'cap1': 1}.get(phase)
    return dict(kind='hardwareProbeResult', schema=1, status={'read': 'read', 'set': 'applied', 'reset': 'reset'}[operation],
        operation=operation, requestToken=NONCE + '-' + phase + ('-read' if readback else '-apply'),
        requestedCap=cap if operation == 'set' else None, configuredCap=cap if cap is not None else 128,
        hasUserValue=phase in ('cap2', 'cap1'), rfpEnabled=mode == 'rfp', nativePreferenceReadback=True,
        scope='runtime-native-pref', workerCoverageVerified=False, fingerprintProtectionVerified=False)


def report(mode='standard'):
    phases = []
    for index, phase in enumerate(runner.PHASES):
        count = (4, 2, 1, 4)[index]
        phases.append(dict(phase=phase, nativeApply=ack(phase, mode), nativeRead=ack(phase, mode, True),
            navigation=dict(schema=1, targetPath=phase + '/probe', activePath=phase + '/probe', locationPath=phase + '/probe',
                generation=3 + index, failedStopsWithoutNativeUrl=1, targetLoadError=False, bootstrapStarted=True,
                bootstrapDocumentReady=True, bootstrapStoppedSuccessfully=True, probeRequested=True, probeStarted=True,
                probeDocumentReady=True, probeStoppedSuccessfully=True, targetOwnedCompletion=True),
            observations=[packet(role, phase, count) for role in runner.ROLES]))
    return dict(schema=1, status='observed', stage='complete', failure='', diagnosticOnly=True, releaseAcceptance=False,
        actualAndroidExecution=True, actualGeckoExecution=True, sourceCommit=SOURCE, sourceTree=TREE,
        buildIdentity=copy.deepcopy(IDENTITY), runNonce=NONCE, mode=mode, nativePreferenceOnly=True,
        navigatorGetterOverrideUsed=False, debuggingEndpointUsed=False, javaTimezoneOverrideUsed=False,
        processTimezoneEnvironmentChangedByProbe=False, workerCoverageVerified=False, fingerprintProtectionVerified=False,
        process=dict(pid=1234, uid=10234, javaTimezoneBefore='UTC', javaTimezoneAfter='UTC',
            icuTimezoneBefore='UTC', icuTimezoneAfter='UTC', tzEnvironmentBefore=None, tzEnvironmentAfter=None), phases=phases,
        server=dict(schema=1, requests=40, responses=40, rejectedRequests=0, transportErrors=0, eventsTruncated=False,
            events=[dict(event='response', method='GET', path=phase + '/probe', status=200, error=None) for phase in runner.PHASES]),
        nativeEvents=[dict(event=name, stage='observing', phase=phase, path=phase + '/probe', generation=3 + index,
            success=True if name == 'page-stop' else None, errorCategory=None, errorCode=None,
            nativeUrlAvailable=name != 'page-stop', elapsedMs=1000 + index)
            for index, phase in enumerate(runner.PHASES)
            for name in ('page-start','location','private-document-ready','page-stop')])


class ProbeControls(unittest.TestCase):
    def validate(self, value, mode='standard'):
        def installed(actual, expected):
            self.assertEqual(actual, expected)
        with patch.object(runner, 'verify_installed', side_effect=installed):
            return runner.validate_case(value, mode=mode, nonce=NONCE, source=SOURCE, tree=TREE, identity=IDENTITY)

    def test_native_default_and_fixed_guest_page_sequence_are_independent(self):
        value = report(); before = copy.deepcopy(value); result = self.validate(value)
        self.assertEqual(value, before)
        self.assertEqual(result['nativeDefaultCap'], 128)
        self.assertEqual(result['pageHardwareCounts'], [4, 2, 1, 4])
        self.assertTrue(result['standardPageSequenceVerified'])
        self.assertFalse(result['workerCoverageVerified']); self.assertFalse(result['fingerprintProtectionVerified'])
        for phase in ('baseline', 'reset'):
            index = runner.PHASES.index(phase)
            self.assertEqual(result['phases'][index]['configuredCap'], 128)
            self.assertEqual(result['phases'][index]['contexts'][0]['hardwareConcurrency'], 4)

    def test_native_ack_never_masks_worker_mismatch_unsupported_or_native_getter_false(self):
        value = report()
        value['phases'][1]['observations'][1]['observation']['hardwareConcurrency'] = 4
        value['phases'][1]['observations'][2].update(status='unsupported', observation=None, error='Unavailable')
        value['phases'][1]['observations'][3]['observation']['nativeGetter'] = False
        result = self.validate(value); contexts = result['phases'][1]['contexts']
        self.assertTrue(result['standardPageSequenceVerified'])
        self.assertFalse(contexts[1]['capObeyed']); self.assertTrue(contexts[1]['actualExecution'])
        self.assertFalse(contexts[2]['actualExecution']); self.assertIsNone(contexts[2]['capObeyed'])
        self.assertFalse(contexts[3]['nativeGetter'])
        self.assertFalse(result['workerCoverageVerified'])

    def test_standard_page_mismatch_is_recorded_and_cannot_pass_sequence_gate(self):
        value = report(); value['phases'][1]['observations'][0]['observation']['hardwareConcurrency'] = 4
        result = self.validate(value)
        self.assertFalse(result['standardPageSequenceVerified'])
        self.assertEqual(result['pageHardwareCounts'], [4, 4, 1, 4])

    def test_rfp_is_observational_and_never_lowered_to_make_caps_pass(self):
        value = report('rfp')
        for phase in value['phases']:
            for row in phase['observations']:
                row['observation']['hardwareConcurrency'] = 2
        result = self.validate(value, 'rfp')
        self.assertIsNone(result['standardPageSequenceVerified'])
        self.assertTrue(result['rfpRemainedEnabled'])
        self.assertFalse(result['phases'][2]['contexts'][0]['capObeyed'])
        value['phases'][2]['nativeRead']['rfpEnabled'] = False
        with self.assertRaises(ValueError): self.validate(value, 'rfp')

    def test_stale_boolean_omitted_replayed_and_scope_fields_are_rejected(self):
        mutations = {
            'wrong source': lambda v: v.update(sourceCommit='f'*40),
            'wrong tree': lambda v: v.update(sourceTree='f'*40),
            'old nonce': lambda v: v.update(runNonce='f'*32),
            'wrong mode': lambda v: v.update(mode='rfp'),
            'Boolean schema': lambda v: v.update(schema=True),
            'claim release': lambda v: v.update(releaseAcceptance=True),
            'no actual Gecko': lambda v: v.update(actualGeckoExecution=False),
            'getter override': lambda v: v.update(navigatorGetterOverrideUsed=True),
            'debug endpoint': lambda v: v.update(debuggingEndpointUsed=True),
            'process timezone changed': lambda v: v['process'].update(icuTimezoneAfter='Asia/Tokyo'),
            'Boolean PID': lambda v: v['process'].update(pid=True),
            'missing phase': lambda v: v['phases'].pop(),
            'replayed phase': lambda v: v['phases'].__setitem__(1, copy.deepcopy(v['phases'][0])),
            'unknown report data': lambda v: v.update(pageText='private'),
            'native readback missing': lambda v: v['phases'][1].pop('nativeRead'),
            'Boolean ACK schema': lambda v: v['phases'][1]['nativeApply'].update(schema=True),
            'wrong read token': lambda v: v['phases'][1]['nativeRead'].update(requestToken=NONCE+'-cap1-read'),
            'replayed apply ACK': lambda v: v['phases'][1].update(nativeApply=copy.deepcopy(v['phases'][0]['nativeApply'])),
            'read requested cap': lambda v: v['phases'][1]['nativeRead'].update(requestedCap=2),
            'Boolean requested cap': lambda v: v['phases'][2]['nativeApply'].update(requestedCap=True),
            'Boolean configured cap': lambda v: v['phases'][2]['nativeRead'].update(configuredCap=True),
            'native baseline is user override': lambda v: v['phases'][0]['nativeApply'].update(hasUserValue=True),
            'reset mismatch default': lambda v: v['phases'][3]['nativeRead'].update(configuredCap=4),
            'reset user pref retained': lambda v: v['phases'][3]['nativeRead'].update(hasUserValue=True),
            'standard RFP weakened': lambda v: v['phases'][1]['nativeRead'].update(rfpEnabled=1),
            'claim worker coverage': lambda v: v['phases'][1]['nativeApply'].update(workerCoverageVerified=True),
            'unknown ACK': lambda v: v['phases'][1]['nativeRead'].update(secret='never'),
            'missing context': lambda v: v['phases'][1]['observations'].pop(),
            'duplicate context': lambda v: v['phases'][1]['observations'].__setitem__(1, copy.deepcopy(v['phases'][1]['observations'][0])),
            'stale worker nonce': lambda v: v['phases'][1]['observations'][1].update(nonce='f'*32),
            'wrong worker phase': lambda v: v['phases'][1]['observations'][1].update(phase='cap1'),
            'Boolean count': lambda v: v['phases'][1]['observations'][1]['observation'].update(hardwareConcurrency=True),
            'zero count': lambda v: v['phases'][1]['observations'][1]['observation'].update(hardwareConcurrency=0),
            'unbounded count': lambda v: v['phases'][1]['observations'][1]['observation'].update(hardwareConcurrency=65537),
            'untyped native getter': lambda v: v['phases'][1]['observations'][1]['observation'].update(nativeGetter=1),
            'non-native standard page getter': lambda v: v['phases'][1]['observations'][0]['observation'].update(nativeGetter=False),
            'unknown observation error': lambda v: v['phases'][1]['observations'][1].update(status='failed', observation=None, error='private-user-data'),
            'unsupported page': lambda v: v['phases'][1]['observations'][0].update(status='unsupported', observation=None, error='Unavailable'),
            'extra observation data': lambda v: v['phases'][1]['observations'][1]['observation'].update(userAgent='private'),
        }
        for name, mutate in mutations.items():
            with self.subTest(name=name):
                value=report(); mutate(value)
                with self.assertRaises((ValueError, AssertionError)): self.validate(value)

    def test_target_requires_real_owned_start_location_ready_stop_and_http200_every_phase(self):
        mutations = {
            'stale active document': lambda v: v['phases'][1]['navigation'].update(activePath='baseline/probe'),
            'stale native location': lambda v: v['phases'][1]['navigation'].update(locationPath='bootstrap'),
            'missing page start': lambda v: v['phases'][1]['navigation'].update(probeStarted=False),
            'missing document ready': lambda v: v['phases'][1]['navigation'].update(probeDocumentReady=False),
            'missing target stop': lambda v: v['phases'][1]['navigation'].update(probeStoppedSuccessfully=False),
            'target load error': lambda v: v['phases'][1]['navigation'].update(targetLoadError=True),
            'old ACK only': lambda v: v['phases'][1]['navigation'].update(targetOwnedCompletion=False),
            'same document replay': lambda v: v['phases'][1]['navigation'].update(generation=3),
            'Boolean generation': lambda v: v['phases'][1]['navigation'].update(generation=True),
            'false stop URL ownership': lambda v: v['nativeEvents'][3].update(nativeUrlAvailable=True),
            'raw native URL': lambda v: v['nativeEvents'][1].update(url='http://private/secret'),
            'untyped native error': lambda v: v['nativeEvents'][1].update(event='load-error', success=None, nativeUrlAvailable=True, errorCode=True, errorCategory=1),
            'missing native event': lambda v: v['nativeEvents'].pop(),
            'stale native generation': lambda v: v['nativeEvents'][7].update(generation=3),
            'wrong native phase': lambda v: v['nativeEvents'][7].update(phase='baseline'),
            'missing target HTTP': lambda v: v['server']['events'].pop(),
            'HTTP500 target': lambda v: v['server']['events'][1].update(status=500),
            'truncated server events': lambda v: v['server'].update(eventsTruncated=True),
            'raw headers': lambda v: v['server']['events'][1].update(headers='secret'),
            'arbitrary error': lambda v: v['server']['events'][1].update(error='secret-user-data'),
            'unbounded events': lambda v: v['server'].update(events=v['server']['events']*65),
        }
        for name, mutate in mutations.items():
            with self.subTest(name=name):
                value=report(); mutate(value)
                with self.assertRaises(ValueError): self.validate(value)

    def test_json_duplicates_nonfinite_and_byte_caps_are_rejected(self):
        for raw in (b'{"schema":1,"schema":1}', b'{"count":NaN}', b'[]', b'x'*(runner.MAX_REPORT_BYTES+1)):
            with self.subTest(raw=raw[:50]), self.assertRaises(ValueError): runner.strict_json(raw)

    def test_installed_identity_rejects_boolean_type_substitution(self):
        with patch.object(runner, 'verify_installed'):
            with self.assertRaises(ValueError): runner.installed_identity({'versionCode': True}, {'versionCode': 1})

    def test_actual_measurement_asset_reads_host_getter_without_replacing_it(self):
        # Real JavaScript execution of this asset against controlled host objects.
        # These values and descriptors are not Android or Gecko observations.
        node=shutil.which('node');self.assertIsNotNone(node,'Actual Node required; no skip')
        asset=ROOT/'tests/gecko/assets/native-hardware-probe.js'
        program=r"""
const fs=require('node:fs'),vm=require('node:vm');
const source=fs.readFileSync(process.argv[1],'utf8');
(async()=>{
 const phases=['baseline','cap2','cap1','reset'];
 for(let index=0;index<phases.length;index++){
  const phase=phases[index],count=[4,2,1,4][index],rows=[];
  const navigator={};const getter=()=>count;
  Object.defineProperty(navigator,'hardwareConcurrency',{get:getter,configurable:false});
  const context={window:{},navigator,isSecureContext:false,setTimeout,clearTimeout,
    __nativeHardwareProbe:{schema:1,nonce:'c'.repeat(32),source:'a'.repeat(40),phase},
    async fetch(path,options){
      if(path!=='/'+phase+'/report?nonce='+'c'.repeat(32))throw Error('cross-phase path');
      rows.push(JSON.parse(options.body));return{ok:true};
    }};
  vm.runInNewContext(source,context);
  await new Promise(resolve=>setImmediate(resolve));
  if(rows.length!==5||new Set(rows.map(row=>row.role)).size!==5)throw Error('missing independent role');
  const page=rows.find(row=>row.role==='page');
  if(page.observation.hardwareConcurrency!==count||page.observation.nativeGetter!==false)throw Error('getter sample changed');
  if(Object.getOwnPropertyDescriptor(navigator,'hardwareConcurrency').get!==getter)throw Error('getter replaced');
  for(const row of rows){
   if(row.nonce!=='c'.repeat(32)||row.sourceCommit!=='a'.repeat(40)||row.phase!==phase)throw Error('wrong packet binding');
   if(row.role!=='page'&&(row.status!=='unsupported'||row.observation!==null))throw Error('unsupported context fabricated');
  }
 }
 // A genuine host built-in getter checks native-function detection without any
 // Function.toString shim. This synthetic ArrayBuffer is never an engine navigator.
 const navigator=new ArrayBuffer(7),get=Object.getOwnPropertyDescriptor(ArrayBuffer.prototype,'byteLength').get;
 Object.defineProperty(navigator,'hardwareConcurrency',{get});
 let output;const self={postMessage(value){output=value;}};
 vm.runInNewContext(source,{self,navigator});
 self.onmessage({data:{kind:'native-hardware-sample',nonce:'c'.repeat(32),phase:'cap2',role:'dedicated'}});
 if(output.observation.hardwareConcurrency!==7||output.observation.nativeGetter!==true)throw Error('native getter detector failed');
 const old=output;self.onmessage({data:{kind:'native-hardware-sample',nonce:'stale',phase:'cap2',role:'dedicated'}});
 if(output!==old)throw Error('stale request answered');
 process.stdout.write(JSON.stringify({hostAssetChecks:4,actualAndroidExecution:false,actualGeckoExecution:false}));
})().catch(error=>{console.error(error);process.exitCode=1});
"""
        ran=subprocess.run([node,'-e',program,str(asset)],capture_output=True,text=True,timeout=10)
        self.assertEqual(ran.returncode,0,ran.stderr)
        result=json.loads(ran.stdout)
        self.assertEqual(result['hostAssetChecks'],4)
        self.assertFalse(result['actualAndroidExecution']);self.assertFalse(result['actualGeckoExecution'])

    def invoke_host_transport(self, fault=None):
        # Only command dispatch/report validation is exercised. This never calls ADB,
        # reads an actual APK or represents these fixture packets as Android evidence.
        directory = tempfile.TemporaryDirectory(prefix='hardware-runner-host-')
        self.addCleanup(directory.cleanup)
        root = Path(directory.name); (root/'app').mkdir(); (root/'app/build.gradle').write_text("versionName 'test'\nversionCode 1\n")
        apk = root/'transport-only.apk'; apk.write_bytes(b'Explicit host-only transport placeholder, never opened as APK')
        output = root/'results'; launches=[]; raw_reports={}; alive=False; current=None
        def git(command, **kwargs):
            if command == ['git','rev-parse','HEAD']: return SOURCE+'\n'
            if command == ['git','rev-parse','HEAD^{tree}']: return TREE+'\n'
            if command == ['git','status','--porcelain']: return ' M app/build.gradle\n' if fault=='dirty' else ''
            raise AssertionError(command)
        def dispatch(command, **kwargs):
            nonlocal alive, current
            self.assertEqual(command[:3], ['controlled-adb', '-s', 'emulator-5554'])
            parts = command[3:]; data=b''
            if parts == ['shell','getprop','ro.kernel.qemu']: data=b'1\n'
            elif parts == ['shell','getprop','ro.build.version.sdk']: data=b'35\n'
            elif parts == ['shell','id','-u']: data=b'2000\n'
            elif parts == ['shell','getconf','_NPROCESSORS_ONLN']: data=b'3\n' if fault=='cpu' else b'4\n'
            elif parts == ['shell','getprop','persist.sys.timezone']: data=b'UTC\n'
            elif parts == ['shell','settings','get','global','auto_time_zone']: data=b'1\n'
            elif parts == ['exec-out','content','read','--uri','content://'+runner.PACKAGE+'.evidence/build-identity']:
                data=json.dumps(IDENTITY).encode()
            elif parts == ['shell','am','force-stop',runner.PACKAGE]: alive=False
            elif parts == ['shell','pidof',runner.PROCESS]: data=(str(current['process']['pid']).encode() if alive else b'')
            elif parts[:4] == ['shell','am','start','-W']:
                self.assertEqual(parts[4:6], ['-n',runner.COMPONENT])
                extras = {parts[index+1]: parts[index+2] for index in range(6,len(parts),3)}
                self.assertEqual(set(extras), {'runNonce','sourceCommit','mode'})
                self.assertEqual(extras['sourceCommit'],SOURCE)
                launches.append(extras); current=report(extras['mode'])
                raw=json.dumps(current).replace(NONCE,extras['runNonce']); current=json.loads(raw)
                current['process']['pid']=1233+len(launches)
                if fault=='page' and extras['mode']=='standard':
                    current['phases'][1]['observations'][0]['observation']['hardwareConcurrency']=4
                if fault=='stale' and extras['mode']=='standard': current['sourceCommit']='f'*40
                if fault=='failed' and extras['mode']=='standard': current.update(status='failed',stage='observing',failure='TargetLoadError')
                if fault=='worker' and extras['mode']=='standard':
                    current['phases'][1]['observations'][2].update(status='unsupported',observation=None,error='Unavailable')
                raw_reports[extras['mode']]=(json.dumps(current,indent=1)+'\n\n').encode();alive=True
            elif parts[:4] == ['exec-out','content','read','--uri']:
                self.assertEqual(parts[4], 'content://'+runner.AUTHORITY+'/report/'+launches[-1]['runNonce'])
                data=raw_reports[launches[-1]['mode']]
            else: raise AssertionError(command)
            return subprocess.CompletedProcess(command,0,stdout=data,stderr=b'')
        arguments=['run_native_hardware_probe.py','--adb','controlled-adb','--apk',str(apk),'--source',SOURCE,'--output',str(output)]
        with patch.object(runner,'ROOT',root), patch.object(runner.subprocess,'check_output',side_effect=git), \
                patch.object(runner.subprocess,'run',side_effect=dispatch), patch.object(runner,'snapshot',return_value={}), \
                patch.object(runner,'expected_build',return_value=IDENTITY), patch.object(runner,'verify_installed'), \
                patch.object(sys,'argv',arguments), contextlib.redirect_stdout(io.StringIO()):
            if fault=='dirty':
                with self.assertRaises(ValueError): runner.main()
                self.assertFalse(output.exists()); self.assertEqual(launches,[])
                return
            code=runner.main()
        return code, json.loads((output/'results.json').read_text()), launches, raw_reports, output

    def test_runner_uses_exactly_two_fresh_mode_launches_and_keeps_raw_failure_bytes(self):
        for fault in (None,'worker','page','stale','failed'):
            with self.subTest(fault=fault):
                code,result,launches,raw_reports,output=self.invoke_host_transport(fault)
                self.assertEqual(code,0 if fault in (None,'worker') else 1)
                self.assertEqual([row['mode'] for row in launches],['standard','rfp'])
                self.assertEqual(len({row['runNonce'] for row in launches}),2)
                self.assertFalse(result['releaseAcceptance']);self.assertFalse(result['workerCoverageVerified'])
                for mode,raw in raw_reports.items():
                    self.assertEqual((output/('case-'+mode+'.json')).read_bytes(),raw)
                if fault=='stale': self.assertEqual(result['caseRecords'][0]['status'],'failed')
                if fault=='page': self.assertFalse(result['standardPageSequenceVerified'])

    def test_runner_rejects_dirty_source_and_non_four_cpu_guest_without_launch(self):
        self.invoke_host_transport('dirty')
        code,result,launches,_,_=self.invoke_host_transport('cpu')
        self.assertEqual(code,1);self.assertEqual(launches,[])
        self.assertIsNone(result['guestOnlineCpus'])
        self.assertFalse(result['actualAndroidExecution'])

    def test_workflow_preserves_fixed_cpu_independent_build_transport_and_no_write_permission(self):
        new = yaml.safe_load((ROOT/'.github/workflows/native-hardware-probe.yml').read_text())
        stable = yaml.safe_load((REPO_ROOT/'.github/workflows/browser-2_1-acceptance.yml').read_text())
        self.assertEqual(new['permissions'], {'contents': 'read'})
        self.assertEqual(new['on']['push']['branches'], ['diagnostics/native-hardware-*'])
        self.assertEqual(new['env'], stable['env'])
        self.assertEqual(set(new['jobs']), {'build', 'native_hardware_probe'})
        self.assertEqual(new['jobs']['native_hardware_probe']['needs'], 'build')
        build = new['jobs']['build']['steps']; steps = new['jobs']['native_hardware_probe']['steps']
        self.assertEqual(build[:5], stable['jobs']['build']['steps'][:5])
        self.assertNotIn('Compile release and native regression package', [s.get('name') for s in steps])
        upload = next(s for s in build if s.get('name')=='Transfer exact same-run diagnostic APKs and SDK classpath')
        download = next(s for s in steps if s.get('name')=='Download only this run and attempt diagnostic build')
        self.assertEqual(upload['with']['name'], download['with']['name'])
        self.assertIn('${{ github.run_id }}', upload['with']['name'])
        self.assertIn('${{ github.run_attempt }}', upload['with']['name'])
        restore = next(s for s in steps if s.get('name')=='Verify and restore exact selected-source SDK and APK bytes')['run']
        for fence in ("value['sourceCommit']==source==os.environ['GITHUB_SHA']", "value['runAttempt']==os.environ['GITHUB_RUN_ATTEMPT']",
            "h.hexdigest()==row['sha256']", "assert discovered==set(allowed)|{'work/native-hardware-build/manifest.json'}"):
            self.assertIn(fence, restore)
        boot = next(s for s in steps if s.get('id')=='boot')['run']
        for fence in ('ANDROID_CAPACITY_PREFLIGHT', '-accel on', '-cores 4', "guest 'native-hardware'"):
            self.assertIn(fence, boot)
        self.assertEqual(boot.count('timeout 180 adb -s emulator-5556 wait-for-device'), 1)
        self.assertEqual(boot.count('timeout 300 bash'), 1)
        measurement = next(s for s in steps if 'run_native_hardware_probe.py --adb' in s.get('run',''))['run']
        self.assertIn('--source "$GITHUB_SHA"', measurement)
        self.assertIn('--apk app/build/outputs/apk/integration/app-x86_64-integration.apk', measurement)
        compile(new['env']['ANDROID_CAPACITY_PREFLIGHT'], 'capacity-preflight', 'exec')
        for job in new['jobs'].values():
            for step in job['steps']:
                run=step.get('run','')
                syntax=subprocess.run(['bash','-n'],input=run,capture_output=True,text=True,timeout=5)
                self.assertEqual(syntax.returncode,0,syntax.stderr)
                for marker in ('PYCODE','HW_BUILD','HW_RESTORE','HW_HEALTH'):
                    start="python3 - <<'"+marker+"'"
                    if start in run:
                        compile(run.split(start,1)[1].split('\n'+marker,1)[0].lstrip('\n'), step['name'], 'exec')
        text = str(new)
        self.assertNotIn('run_native_timezone_probe', text)
        self.assertNotIn('native_timezone_api_contract', text)

    def test_actual_health_collector_is_bounded_and_reads_only_fixed_emulator_log(self):
        value=yaml.safe_load((ROOT/'.github/workflows/native-hardware-probe.yml').read_text())
        step=next(s for s in value['jobs']['native_hardware_probe']['steps']
                  if s.get('name')=='Capture bounded read-only emulator startup health')
        code=step['run'].split("python3 - <<'HW_HEALTH'",1)[1].split('\nHW_HEALTH',1)[0].lstrip('\n')
        for symlink in (False,True):
            with self.subTest(symlink=symlink),tempfile.TemporaryDirectory(prefix='hardware-health-host-') as directory:
                temporary=Path(directory);base=temporary/'work/gecko-integration';base.mkdir(parents=True)
                (base/'native-hardware-boot.exit').write_text('124\n')
                (base/'native-hardware-emulator.exit').write_text('1\n')
                (base/'native-hardware-emulator.pid').write_text('../../private')
                (base/'other-private.log').write_text('NEVER_READ_OTHER_LOG')
                if symlink:(base/'emulator.log').symlink_to(base/'other-private.log')
                else:(base/'emulator.log').write_text('x'*100000+'\nPANIC: controlled emulator failure\n')
                ran=subprocess.run([sys.executable,'-c',code],cwd=temporary,
                    env=dict(os.environ,ANDROID_HOME=str(temporary/'missing-sdk'),BOOT_STEP_OUTCOME='failure'),
                    capture_output=True,text=True,timeout=10)
                self.assertEqual(ran.returncode,0,ran.stderr)
                path=temporary/'work/native-hardware-probe-host/emulator-health.json'
                raw=path.read_bytes();result=json.loads(raw)
                self.assertLessEqual(len(raw),32768)
                self.assertEqual(result['bootExitCode'],124);self.assertEqual(result['emulatorExitCode'],1)
                self.assertFalse(result['rootCauseEstablished'])
                self.assertNotIn('NEVER_READ_OTHER_LOG',raw.decode())
                if symlink:self.assertEqual(result['emulatorLog']['error'],'missing-or-nonregular')
                else:
                    self.assertLessEqual(result['emulatorLog']['tailBytes'],8192)
                    self.assertIn('controlled emulator failure',result['emulatorLog']['tailUtf8'])
                    self.assertTrue(result['emulatorLog']['tailOnly'])

    def test_actual_restore_rejects_stale_or_corrupt_transport_before_native_execution(self):
        # Transport-only synthetic byte fixtures. No fixture is opened as an APK
        # or SDK, compiled, run on Android, or described as a real engine input.
        workflow=yaml.safe_load((ROOT/'.github/workflows/native-hardware-probe.yml').read_text())
        step=next(s for s in workflow['jobs']['native_hardware_probe']['steps']
                  if s.get('name')=='Verify and restore exact selected-source SDK and APK bytes')
        code=step['run'].split("python3 - <<'HW_RESTORE'",1)[1].split('\nHW_RESTORE',1)[0].lstrip('\n')
        namespace={}
        prefix=code.split("root=pathlib.Path('work/native-hardware-build-download')",1)[0]
        exec(compile(prefix,'restore-allowlist','exec'),namespace)
        allowed=namespace['allowed']
        for fault in (None,'source','tree','run','attempt','unknown-path','duplicate',
                      'extra-file','corrupt-bytes','boolean-size','symlink','existing-target'):
            with self.subTest(fault=fault),tempfile.TemporaryDirectory(prefix='hardware-transfer-host-') as directory:
                temporary=Path(directory);download=temporary/'work/native-hardware-build-download'
                rows=[]
                for index,name in enumerate(allowed):
                    p=download/name;p.parent.mkdir(parents=True,exist_ok=True)
                    raw=('Explicit transport-only synthetic byte fixture '+str(index)).encode();p.write_bytes(raw)
                    rows.append(dict(path=name,bytes=len(raw),sha256=hashlib.sha256(raw).hexdigest()))
                value=dict(schema=1,kind='native-hardware-build',sourceCommit=SOURCE,sourceTree=TREE,
                           runId='7',runAttempt='1',diagnosticOnly=True,releaseAcceptance=False,files=rows)
                if fault=='source':value['sourceCommit']='f'*40
                if fault=='tree':value['sourceTree']='f'*40
                if fault=='run':value['runId']='8'
                if fault=='attempt':value['runAttempt']='2'
                if fault=='unknown-path':rows[0]['path']='../../never-read'
                if fault=='duplicate':rows[1]=copy.deepcopy(rows[0])
                if fault=='extra-file':(download/'unknown-file').write_text('Never copied')
                if fault=='corrupt-bytes':(download/allowed[0]).write_bytes(b'corrupt')
                if fault=='boolean-size':rows[0]['bytes']=True
                if fault=='symlink':
                    (download/allowed[0]).unlink();(download/allowed[0]).symlink_to(download/allowed[1])
                if fault=='existing-target':
                    target=temporary/allowed[0];target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(b'old')
                manifest=download/'work/native-hardware-build/manifest.json'
                manifest.parent.mkdir(parents=True,exist_ok=True);manifest.write_text(json.dumps(value))
                def git(command,**kwargs):
                    if command==['git','rev-parse','HEAD']:return SOURCE+'\n'
                    if command==['git','rev-parse','HEAD^{tree}']:return TREE+'\n'
                    if command==['git','status','--porcelain']:return ''
                    raise AssertionError('Unexpected transport command')
                previous=Path.cwd()
                try:
                    os.chdir(temporary)
                    with patch.dict(os.environ,GITHUB_SHA=SOURCE,GITHUB_REPOSITORY='Ararataki-number-one/yuanying-chat',
                                    GITHUB_REPOSITORY_ID='1401080063',GITHUB_RUN_ID='7',GITHUB_RUN_ATTEMPT='1'),\
                            patch.object(subprocess,'check_output',side_effect=git),\
                            contextlib.redirect_stdout(io.StringIO()):
                        if fault is None:
                            exec(compile(code,'actual-restore-protocol','exec'),{})
                            for row in rows:
                                self.assertEqual(hashlib.sha256((temporary/row['path']).read_bytes()).hexdigest(),row['sha256'])
                            proof=json.loads((temporary/'work/native-hardware-probe-host/build-restore.json').read_text())
                            self.assertFalse(proof['actualAndroidExecution'])
                        else:
                            with self.assertRaises(AssertionError):exec(compile(code,'actual-restore-protocol','exec'),{})
                            self.assertFalse((temporary/'work/native-hardware-probe-host/build-restore.json').exists())
                finally:os.chdir(previous)

def check_packages(args):
    from caret_build_identity import dex_definitions
    paths=[args.integration_apk,args.release_apk,args.aapt2]
    if not all(p is not None and p.is_file() for p in paths):raise ValueError('Actual compiled APKs/aapt2 required')
    classes=set();release_classes=set()
    for path,definitions in ((args.integration_apk,classes),(args.release_apk,release_classes)):
        with ZipFile(path) as archive:
            for name in archive.namelist():
                if name.endswith('.dex'):definitions.update(dex_definitions(archive.read(name)))
    prefix='Llocal/pocketchat/NativeHardwareProbe'
    expected={prefix+name+';' for name in ('Activity','Server','Provider')}
    if not expected<=classes or any(name.startswith(prefix) for name in release_classes):raise ValueError('Actual probe class separation failed')
    with ZipFile(args.integration_apk) as archive:
        required=['assets/native-hardware-probe.js',*(
            'assets/native-hardware-extension/'+name for name in ('manifest.json','schema.json','parent.js','background.js','content.js'))]
        if not all(archive.namelist().count(name)==1 for name in required):raise ValueError('Integration probe assets absent or duplicated')
    integration_manifest=subprocess.check_output([str(args.aapt2),'dump','xmltree',str(args.integration_apk),'--file','AndroidManifest.xml'],text=True)
    if not all(value in integration_manifest for value in ('local.pocketchat.NativeHardwareProbeActivity',
            'local.pocketchat.NativeHardwareProbeProvider','local.pocketchat.test.nativehardware',':native_hardware_probe')):
        raise ValueError('Actual integration probe component or authority absent')
    with ZipFile(args.release_apk) as archive:
        if any(name.startswith('assets/native-hardware') for name in archive.namelist()):raise ValueError('Probe assets leaked to production')
    manifest=subprocess.check_output([str(args.aapt2),'dump','xmltree',str(args.release_apk),'--file','AndroidManifest.xml'],text=True)
    if 'NativeHardwareProbe' in manifest:raise ValueError('Probe component leaked to production')
    source=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip()
    tree=subprocess.check_output(['git','rev-parse','HEAD^{tree}'],cwd=ROOT,text=True).strip()
    if subprocess.check_output(['git','status','--porcelain'],cwd=ROOT,text=True).strip():raise ValueError('Package audit requires clean source')
    result=dict(schema=1,status='passed',sourceCommit=source,sourceTree=tree,diagnosticOnly=True,
        releaseAcceptance=False,actualAndroidExecution=False,actualCompiledProbeDefinitions=sorted(expected),
        integrationApkSha256=runner.sha(args.integration_apk),releaseApkSha256=runner.sha(args.release_apk),
        productionProbeClassesAbsent=True,productionProbeAssetsAbsent=True,productionProbeComponentsAbsent=True,
        scope='Actual Gradle-built APK DEX/ZIP/manifest separation; no device or hardware functionality claim')
    args.output.parent.mkdir(parents=True,exist_ok=True);args.output.write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps(result))

if __name__=='__main__':
    parser=argparse.ArgumentParser(add_help=False);parser.add_argument('--check-packages',action='store_true')
    parser.add_argument('--integration-apk',type=Path);parser.add_argument('--release-apk',type=Path)
    parser.add_argument('--aapt2',type=Path);parser.add_argument('--output',type=Path)
    args,remaining=parser.parse_known_args()
    if args.check_packages:
        if args.output is None:parser.error('--output required')
        check_packages(args)
    else:unittest.main(argv=[sys.argv[0],*remaining],verbosity=2)
