"""Probe-only controls. Host observations never claim actual Android timezone support."""
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

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'tools/gecko'))
spec=importlib.util.spec_from_file_location('native_timezone_probe_runner',ROOT/'tools/gecko/run_native_timezone_probe.py')
runner=importlib.util.module_from_spec(spec);spec.loader.exec_module(runner)
SOURCE='a'*40;TREE='b'*40;NONCE='c'*32

def packet(role,zone):
    values=runner.ZONES[zone]
    fields=('janOffsetMinutes','julyOffsetMinutes','janHour','janMinute','julyHour','julyMinute')
    row=dict(zip(fields,values[:6]),timeZone=values[6][0],janEpochMillis=runner.JAN,julyEpochMillis=runner.JULY)
    return dict(schema=1,nonce=NONCE,sourceCommit=SOURCE,role=role,status='observed',observation=row,error=None)

def report(zone='America/New_York'):
    base=dict(schema=1,kind='timezoneProbeResult',nativeZoneId=zone,nativeSettingReadback=True,
        contextId='12345',scope='top-browsing-context',workerCoverageVerified=False,serviceWorkerCoverageVerified=False)
    return dict(schema=1,status='observed',stage='complete',failure='',runNonce=NONCE,
        requestedZoneId=zone,sourceCommit=SOURCE,sourceTree=TREE,diagnosticOnly=True,releaseAcceptance=False,
        actualAndroidExecution=True,actualGeckoExecution=True,buildIdentity={'controlledHostInputOnly':True},
        javaTimezoneOverrideUsed=False,processTimezoneEnvironmentChangedByProbe=False,debuggingEndpointUsed=False,
        dateOrIntlOverrideUsed=False,workerCoverageVerified=False,serviceWorkerCoverageVerified=False,
        fingerprintProtectionVerified=False,
        process=dict(pid=1234,uid=10234,javaTimezoneBefore='UTC',javaTimezoneAfter='UTC',
                     icuTimezoneBefore='UTC',icuTimezoneAfter='UTC',tzEnvironmentBefore=None,tzEnvironmentAfter=None),
        nativeApply=dict(base,status='applied',requestToken=NONCE+'-apply',requestedZoneId=zone),
        nativeRead=dict(base,status='read',requestToken=NONCE+'-read',requestedZoneId=zone),
        observations=[packet(role,zone) for role in runner.ROLES])

class ProbeControls(unittest.TestCase):
    def validate(self,value,zone='America/New_York'):
        def installed(actual,expected):self.assertEqual(actual,expected)
        with patch.object(runner,'verify_installed',side_effect=installed):
            return runner.validate_case(value,zone=zone,nonce=NONCE,source=SOURCE,tree=TREE,
                identity={'controlledHostInputOnly':True})

    def test_fixed_january_july_and_quarter_hour_values_are_explicit(self):
        self.assertEqual((runner.JAN,runner.JULY),(1768478400000,1784116800000))
        for zone in runner.ZONES:
            value=report(zone);before=copy.deepcopy(value);result=self.validate(value,zone)
            self.assertTrue(result['pageTimezoneVerified'])
            self.assertEqual(value,before)
            self.assertTrue(all(row['timezoneMatchesRequested'] for row in result['contexts']))
            self.assertFalse(result['workerCoverageVerified']);self.assertFalse(result['serviceWorkerCoverageVerified'])

    def test_native_ack_never_masks_worker_mismatch_or_unavailable(self):
        value=report();value['observations'][1]=packet('dedicated','UTC')
        value['observations'][2].update(status='unsupported',observation=None,error='Unavailable')
        result=self.validate(value)
        self.assertTrue(result['pageTimezoneVerified'])
        self.assertFalse(result['contexts'][1]['timezoneMatchesRequested'])
        self.assertTrue(result['contexts'][1]['actualExecution'])
        self.assertFalse(result['contexts'][2]['actualExecution'])
        self.assertEqual(result['contexts'][2]['status'],'unsupported')

    def test_missing_stale_or_untyped_native_fences_are_rejected(self):
        mutations={
            'wrong source':lambda v:v.update(sourceCommit='f'*40),
            'wrong tree':lambda v:v.update(sourceTree='f'*40),
            'old nonce':lambda v:v.update(runNonce='f'*32),
            'wrong target':lambda v:v.update(requestedZoneId='UTC'),
            'boolean schema':lambda v:v.update(schema=True),
            'claim release':lambda v:v.update(releaseAcceptance=True),
            'no real Gecko':lambda v:v.update(actualGeckoExecution=False),
            'date shim':lambda v:v.update(dateOrIntlOverrideUsed=True),
            'debug endpoint':lambda v:v.update(debuggingEndpointUsed=True),
            'process timezone changed':lambda v:v['process'].update(icuTimezoneAfter='America/New_York'),
            'unknown native readback':lambda v:v['nativeApply'].update(nativeSettingReadback='true'),
            'wrong native token':lambda v:v['nativeApply'].update(requestToken='stale'),
            'wrong native zone':lambda v:v['nativeRead'].update(nativeZoneId='UTC'),
            'different same-origin BC':lambda v:v['nativeRead'].update(contextId='12346'),
            'missing context':lambda v:v['observations'].pop(),
            'duplicate context':lambda v:v['observations'].__setitem__(1,copy.deepcopy(v['observations'][0])),
            'stale worker nonce':lambda v:v['observations'][1].update(nonce='f'*32),
            'Boolean offset':lambda v:v['observations'][0]['observation'].update(janOffsetMinutes=True),
            'different instant':lambda v:v['observations'][0]['observation'].update(janEpochMillis=runner.JAN+1),
            'extra raw page data':lambda v:v['observations'][0].update(pageText='private'),
        }
        for name,mutate in mutations.items():
            with self.subTest(name=name):
                value=report();mutate(value)
                with self.assertRaises((ValueError,AssertionError)):self.validate(value)

    def test_json_duplicate_nonfinite_and_byte_caps_are_rejected(self):
        for raw in (b'{"schema":1,"schema":1}',b'{"offset":NaN}',b'[]',b'x'*131073):
            with self.subTest(raw=raw[:50]),self.assertRaises(ValueError):runner.strict_json(raw)

    def test_actual_measurement_asset_on_native_host_date_apis_without_timezone_shims(self):
        node=shutil.which('node');self.assertIsNotNone(node,'Actual Node required; no skip')
        asset=ROOT/'tests/gecko/assets/native-timezone-probe.js'
        program=r"""
const fs=require('node:fs'),vm=require('node:vm');
let output;
const self={postMessage(value){output=value;}};
vm.runInNewContext(fs.readFileSync(process.argv[1],'utf8'),{self,Date,Intl});
self.onmessage({data:{kind:'native-timezone-sample',nonce:'c'.repeat(32),role:'dedicated'}});
if(!output)throw Error('Actual asset did not emit');
process.stdout.write(JSON.stringify(output));
"""
        for zone in runner.ZONES:
            ran=subprocess.run([node,'-e',program,str(asset)],env=dict(os.environ,TZ=zone),
                capture_output=True,text=True,timeout=10)
            self.assertEqual(ran.returncode,0,ran.stderr)
            value=json.loads(ran.stdout);row=packet('dedicated',zone)
            row['observation']=value['observation']
            self.assertTrue(runner.observation(row,'dedicated',zone,NONCE,SOURCE)['timezoneMatchesRequested'])

    def test_bootstrap_and_experiment_are_distinct_from_measurement_and_production(self):
        server=(ROOT/'tests/gecko/NativeTimezoneProbeServer.java').read_text()
        activity=(ROOT/'tests/gecko/NativeTimezoneProbeActivity.java').read_text()
        self.assertIn('bootstrapCompleted=true;apply();',activity)
        self.assertIn('stage="observing";publish();session.loadUri(server.url("/probe"))',activity)
        self.assertIn('session.open(runtime)',activity)
        self.assertIn('.remoteDebuggingEnabled(false)',activity)
        self.assertNotIn('TimeZone.setDefault',activity);self.assertNotIn('Os.setenv',activity)
        self.assertIn('if(uri.isAbsolute()||!("nonce="+nonce).equals(uri.getRawQuery()))',server)
        self.assertIn('new ServerSocket(0,16,InetAddress.getByName("127.0.0.1"))',server)
        main=(ROOT/'app/src/main/AndroidManifest.xml').read_text()
        self.assertNotIn('NativeTimezoneProbe',main)
        integration=(ROOT/'tests/gecko/AndroidManifest.xml').read_text()
        self.assertEqual(integration.count('android:name="local.pocketchat.NativeTimezoneProbeActivity"'),1)
        self.assertEqual(integration.count('android:name="local.pocketchat.NativeTimezoneProbeProvider"'),1)

    def test_workflow_uses_actual_full_sdk_and_original_capacity_fences(self):
        new=yaml.safe_load((ROOT/'.github/workflows/native-timezone-probe.yml').read_text())
        original=yaml.safe_load((ROOT/'.github/workflows/browser-2_1-acceptance.yml').read_text())
        self.assertEqual(new['permissions'],{'contents':'read'})
        self.assertEqual(new['on']['push']['branches'],['diagnostics/native-timezone-*'])
        self.assertEqual(new['env'],original['env'])
        self.assertEqual(set(new['jobs']),{'build','native_timezone_probe'})
        self.assertEqual(new['jobs']['native_timezone_probe']['needs'],'build')
        build=new['jobs']['build']['steps'];steps=new['jobs']['native_timezone_probe']['steps']
        self.assertEqual(build[:5],original['jobs']['build']['steps'][:5])
        self.assertNotIn('Compile release and native regression package',[s.get('name') for s in steps])
        self.assertNotIn('Boot real API35 for diagnostic native timezone observations',[s.get('name') for s in build])
        uploaded=next(s for s in build if s.get('name')=='Transfer exact same-run diagnostic APKs and SDK classpath')
        downloaded=next(s for s in steps if s.get('name')=='Download only this run and attempt diagnostic build')
        self.assertEqual(uploaded['with']['name'],downloaded['with']['name'])
        self.assertIn('$'+'{{ github.run_id }}',uploaded['with']['name'])
        self.assertIn('$'+'{{ github.run_attempt }}',uploaded['with']['name'])
        restore=next(s for s in steps if s.get('name')=='Verify and restore exact selected-source SDK and APK bytes')['run']
        for check in ("value['sourceCommit']==source==os.environ['GITHUB_SHA']",
                      "value['runAttempt']==os.environ['GITHUB_RUN_ATTEMPT']",
                      "h.hexdigest()==row['sha256']",
                      "assert discovered==set(allowed)|{'work/native-timezone-build/manifest.json'}"):
            self.assertIn(check,restore)
        boot=next(s for s in steps if s.get('name')=='Boot real API35 for diagnostic native timezone observations')['run']
        self.assertIn('ANDROID_CAPACITY_PREFLIGHT',boot);self.assertIn('-accel on',boot);self.assertIn('-cores 4',boot)
        self.assertEqual(boot.count('timeout 180 adb -s emulator-5556 wait-for-device'),1)
        self.assertEqual(boot.count('timeout 300 bash'),1)
        expected=original['jobs']['chrome-diagnostic']['steps'][4]['run'].replace("'"+'$'+"{{ matrix.scenario }}'","'native-timezone'")
        position=0
        for line in expected.splitlines():
            index=boot.find(line,position);self.assertGreaterEqual(index,position);position=index+len(line)
        self.assertIn('native-timezone-boot.exit',boot)
        self.assertIn('native-timezone-emulator.exit',boot)
        health=next(s for s in steps if s.get('name')=='Capture bounded read-only emulator startup health')
        self.assertEqual(health['if'],'always()')
        compile(new['env']['ANDROID_CAPACITY_PREFLIGHT'],'parsed-capacity-preflight','exec')
        for job in new['jobs'].values():
            for step in job['steps']:
                run=step.get('run','')
                for marker in ('PYCODE','TZ_BUILD','TZ_RESTORE','TZ_HEALTH'):
                    start="python3 - <<'"+marker+"'"
                    if start in run:compile(run.split(start,1)[1].split('\n'+marker,1)[0].lstrip('\n'),step['name'],'exec')
        self.assertNotIn('Diagnose original chrome collapse flow only',str(new))

    def test_actual_health_collector_is_bounded_and_reads_only_fixed_emulator_log(self):
        value=yaml.safe_load((ROOT/'.github/workflows/native-timezone-probe.yml').read_text())
        step=next(s for s in value['jobs']['native_timezone_probe']['steps']
                  if s.get('name')=='Capture bounded read-only emulator startup health')
        code=step['run'].split("python3 - <<'TZ_HEALTH'",1)[1].split('\nTZ_HEALTH',1)[0].lstrip('\n')
        for symlink in (False,True):
            with self.subTest(symlink=symlink),tempfile.TemporaryDirectory(prefix='timezone-health-host-') as directory:
                temporary=Path(directory);base=temporary/'work/gecko-integration';base.mkdir(parents=True)
                (base/'native-timezone-boot.exit').write_text('124\n')
                (base/'native-timezone-emulator.exit').write_text('1\n')
                (base/'native-timezone-emulator.pid').write_text('../../private')
                (base/'other-private.log').write_text('NEVER_READ_OTHER_LOG')
                if symlink:(base/'emulator.log').symlink_to(base/'other-private.log')
                else:(base/'emulator.log').write_text('x'*100000+'\nPANIC: controlled emulator failure\n')
                ran=subprocess.run([sys.executable,'-c',code],cwd=temporary,
                    env=dict(os.environ,ANDROID_HOME=str(temporary/'missing-sdk'),BOOT_STEP_OUTCOME='failure'),
                    capture_output=True,text=True,timeout=10)
                self.assertEqual(ran.returncode,0,ran.stderr)
                path=temporary/'work/native-timezone-probe-host/emulator-health.json'
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
        workflow=yaml.safe_load((ROOT/'.github/workflows/native-timezone-probe.yml').read_text())
        step=next(s for s in workflow['jobs']['native_timezone_probe']['steps']
                  if s.get('name')=='Verify and restore exact selected-source SDK and APK bytes')
        code=step['run'].split("python3 - <<'TZ_RESTORE'",1)[1].split('\nTZ_RESTORE',1)[0].lstrip('\n')
        namespace={}
        prefix=code.split("root=pathlib.Path('work/native-timezone-build-download')",1)[0]
        exec(compile(prefix,'restore-allowlist','exec'),namespace)
        allowed=namespace['allowed']
        for fault in (None,'source','tree','run','attempt','unknown-path','duplicate',
                      'extra-file','corrupt-bytes','boolean-size','symlink','existing-target'):
            with self.subTest(fault=fault),tempfile.TemporaryDirectory(prefix='timezone-transfer-host-') as directory:
                temporary=Path(directory);download=temporary/'work/native-timezone-build-download'
                rows=[]
                for index,name in enumerate(allowed):
                    p=download/name;p.parent.mkdir(parents=True,exist_ok=True)
                    raw=('Explicit transport-only synthetic byte fixture '+str(index)).encode();p.write_bytes(raw)
                    rows.append(dict(path=name,bytes=len(raw),sha256=hashlib.sha256(raw).hexdigest()))
                value=dict(schema=1,kind='native-timezone-build',sourceCommit=SOURCE,sourceTree=TREE,
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
                manifest=download/'work/native-timezone-build/manifest.json'
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
                            proof=json.loads((temporary/'work/native-timezone-probe-host/build-restore.json').read_text())
                            self.assertFalse(proof['actualAndroidExecution'])
                        else:
                            with self.assertRaises(AssertionError):exec(compile(code,'actual-restore-protocol','exec'),{})
                            self.assertFalse((temporary/'work/native-timezone-probe-host/build-restore.json').exists())
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
    prefix='Llocal/pocketchat/NativeTimezoneProbe'
    expected={prefix+name+';' for name in ('Activity','Server','Provider')}
    if not expected<=classes or any(name.startswith(prefix) for name in release_classes):raise ValueError('Actual probe class separation failed')
    with ZipFile(args.integration_apk) as archive:
        if 'assets/native-timezone-probe.js' not in archive.namelist() or 'assets/native-timezone-extension/manifest.json' not in archive.namelist():raise ValueError('Integration probe assets absent')
    with ZipFile(args.release_apk) as archive:
        if any(name.startswith('assets/native-timezone') for name in archive.namelist()):raise ValueError('Probe assets leaked to production')
    manifest=subprocess.check_output([str(args.aapt2),'dump','xmltree',str(args.release_apk),'--file','AndroidManifest.xml'],text=True)
    if 'NativeTimezoneProbe' in manifest:raise ValueError('Probe component leaked to production')
    source=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip()
    tree=subprocess.check_output(['git','rev-parse','HEAD^{tree}'],cwd=ROOT,text=True).strip()
    if subprocess.check_output(['git','status','--porcelain'],cwd=ROOT,text=True).strip():raise ValueError('Package audit requires clean source')
    result=dict(schema=1,status='passed',sourceCommit=source,sourceTree=tree,diagnosticOnly=True,
        releaseAcceptance=False,actualAndroidExecution=False,actualCompiledProbeDefinitions=sorted(expected),
        integrationApkSha256=runner.sha(args.integration_apk),releaseApkSha256=runner.sha(args.release_apk),
        productionProbeClassesAbsent=True,productionProbeAssetsAbsent=True,productionProbeComponentsAbsent=True,
        scope='Actual Gradle-built APK DEX/ZIP/manifest separation; no device or timezone functionality claim')
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
