"""Counterfeit host controls only. No adb, Android or app acceptance is executed."""
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import time
import unittest
from unittest.mock import patch
from urllib.parse import parse_qs, urlsplit

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools/gecko'))
spec = importlib.util.spec_from_file_location('bootstrap_controls', ROOT / 'tools/gecko/prepare_emulator.py')
bootstrap = importlib.util.module_from_spec(spec)
spec.loader.exec_module(bootstrap)


def identity():
    return dict(schema=1, package='local.pocketchat.test', sourceCommit='a'*40,
                sourceTree='b'*40, dirtySource=False, version='1.6.0', versionCode=51,
                sdkCoordinate='org.mozilla.geckoview:geckoview:157.0.20261005135250',
                apkSha256='c'*64, apkBytes=100, buildStampSha256='d'*64)


def observation():
    return dict(schema=1, runNonce='e'*32, sourceCommit='a'*40, buildIdentity=identity(),
                actualAndroidExecution=True, actualConnectivityManagerExecution=True,
                actualGeckoExecution=False, applicationAcceptance=False, physicalPhoneAcceptance=False,
                androidSdk=35, pid=100, observedAtElapsedRealtime=123,
                activeNetwork='101', activeNetworkAfter='101', capabilitiesPresent=True,
                internetCapability=True, stableDuringRead=True, usable=True)


def record():
    return dict(commands=[], networkObservations=[], initialInputSettings={},
                disabledStateConfirmed=False, applicationAcceptance=False)


class Clock:
    def __init__(self):self.value=0
    def now(self):return self.value
    def sleep(self,seconds):self.value+=seconds


class FakeCommands:
    """A unit double; never a real command receipt."""
    def __init__(self, qemu='1', scan='00:11:22:33:44:55 2412 -45 0 AndroidWifi [ESS]'):
        self.calls=[];self.qemu=qemu;self.scan=scan;self.deadline=time.monotonic()+30
    def run(self,*parts,**unused):
        self.calls.append(parts)
        if parts==('shell','getprop','ro.kernel.qemu'):return self.qemu
        if parts==('shell','cmd','wifi','status'):return 'Wifi is enabled'
        if parts==('shell','cmd','wifi','start-scan'):return 'Scan requested'
        if parts==('shell','cmd','wifi','list-scan-results'):return self.scan
        if parts[:4]==('shell','pm','list','packages'):return 'package:'+bootstrap.PACKAGE
        return ''


class SampleCommands(FakeCommands):
    """Counterfeit native samples for ordering/validation, never actual adb."""
    def __init__(self, samples, receipt, edit=None, **kwargs):
        super().__init__(**kwargs)
        self.samples=list(samples);self.receipt=receipt;self.edit=edit
    def run(self,*parts,**kwargs):
        output=super().run(*parts,**kwargs)
        if parts[:4]==('exec-out','content','read','--uri'):
            parsed=urlsplit(parts[4])
            if parsed.netloc!=bootstrap.AUTHORITY or parsed.path!='/default-network':
                raise AssertionError('Unexpected preflight provider authority/path')
            value=observation();value['runNonce']=parse_qs(parsed.query)['runNonce'][0]
            if not self.samples.pop(0):
                value.update(activeNetwork='',activeNetworkAfter='',capabilitiesPresent=False,
                             internetCapability=False,stableDuringRead=False,usable=False)
            if self.edit:self.edit(value)
            output=json.dumps(value)
        self.receipt['commands'].append(dict(command=list(parts),stdout=output,
                                             observedAt=time.monotonic(),counterfeitHostControl=True))
        return output


class BootstrapControls(unittest.TestCase):
    def test_complete_metadata_is_only_a_validator_control(self):
        self.assertTrue(bootstrap.validate_observation(observation(),identity(),'e'*32))
    def test_stale_nonce_foreign_apk_and_runtime_promotion_are_rejected(self):
        edits=[lambda v:v.update(runNonce='f'*32),lambda v:v['buildIdentity'].update(apkSha256='f'*64),
               lambda v:v['buildIdentity'].update(dirtySource=True),lambda v:v.update(applicationAcceptance=True),
               lambda v:v.update(actualGeckoExecution=True),lambda v:v.update(buildIdentity=None)]
        for edit in edits:
            with self.subTest(edit=edit):
                value=observation();edit(value)
                with self.assertRaises(ValueError):bootstrap.validate_observation(value,identity(),'e'*32)
    def test_missing_or_unstable_default_network_cannot_pass(self):
        value=observation();value.update(activeNetwork='',activeNetworkAfter='',capabilitiesPresent=False,
                                       internetCapability=False,stableDuringRead=False,usable=False)
        self.assertFalse(bootstrap.validate_observation(value,identity(),'e'*32))
        value=observation();value.update(activeNetworkAfter='102',stableDuringRead=False,usable=False)
        self.assertFalse(bootstrap.validate_observation(value,identity(),'e'*32))
        value['usable']=True
        with self.assertRaises(ValueError):bootstrap.validate_observation(value,identity(),'e'*32)
    def test_numeric_capability_truth_is_rejected(self):
        value=observation();value['internetCapability']=1
        with self.assertRaises(ValueError):bootstrap.validate_observation(value,identity(),'e'*32)
    def test_internet_without_capabilities_is_invalid_even_if_unusable(self):
        value=observation();value.update(capabilitiesPresent=False,usable=False)
        with self.assertRaises(ValueError):bootstrap.validate_observation(value,identity(),'e'*32)
    def test_actual_healthy_before_snapshot_never_changes_wifi(self):
        commands=FakeCommands();receipt=record()
        with patch.object(bootstrap,'network_observation',side_effect=[True,True]) as snapshots:
            bootstrap.preflight(commands,receipt,identity())
        self.assertEqual(snapshots.call_count,2)
        self.assertFalse(any('wifi' in cmd for cmd in commands.calls))
        self.assertEqual(receipt['status'],'passed')
        self.assertFalse(receipt['applicationAcceptance'])
        self.assertFalse(any('put' in cmd for cmd in commands.calls))
    def test_only_confirmed_qemu_may_reach_package_or_wifi_changes(self):
        commands=FakeCommands(qemu='0')
        with self.assertRaises(ValueError):bootstrap.preflight(commands,record(),identity())
        self.assertEqual(commands.calls,[('shell','getprop','ro.kernel.qemu')])
        with self.assertRaises(ValueError):bootstrap.Commands('adb','physical-phone',record(),time.monotonic()+20)
    def test_disconnected_sdk_wifi_is_checked_before_disabling_setup(self):
        commands=FakeCommands();receipt=record()
        with patch.object(bootstrap,'network_observation',side_effect=[False,True,True]):
            bootstrap.preflight(commands,receipt,identity())
        connect=('shell','cmd','wifi','connect-network','AndroidWifi','open')
        disable=('shell','pm','disable-user','--user','0',bootstrap.PACKAGE)
        self.assertLess(commands.calls.index(connect),commands.calls.index(disable))
    def test_after_disable_cm_failure_cannot_be_promoted(self):
        # No usable default network after disable, and no exact SDK AP to
        # restore: this original negative control must still fail.
        commands=FakeCommands(scan='00:11:22:33:44:55 2412 -45 0 Other [ESS]')
        clock=Clock();commands.deadline=30
        with patch.object(bootstrap.time,'monotonic',clock.now),patch.object(bootstrap.time,'sleep',clock.sleep),patch.object(bootstrap,'network_observation',side_effect=[True,False]):
            with self.assertRaises(ValueError):bootstrap.preflight(commands,record(),identity())
    def test_similar_ssid_never_connects_or_disables_setup(self):
        for ssid in ['AndroidWifi-other','Other-AndroidWifi','OtherAndroidWifi']:
            with self.subTest(ssid=ssid):
                commands=FakeCommands(scan='00:11:22:33:44:55 2412 -45 0 '+ssid+' [ESS]')
                clock=Clock();commands.deadline=30
                with patch.object(bootstrap.time,'monotonic',clock.now),patch.object(bootstrap.time,'sleep',clock.sleep),patch.object(bootstrap,'network_observation',return_value=False):
                    with self.assertRaises(ValueError):bootstrap.preflight(commands,record(),identity())
                self.assertFalse(any('connect-network' in cmd or 'disable-user' in cmd for cmd in commands.calls))
    def test_original_stderr_and_per_command_deadline_are_preserved(self):
        receipt=record();commands=bootstrap.Commands('adb',bootstrap.SERIAL,receipt,time.monotonic()+40)
        result=subprocess.CompletedProcess([],1,stdout='original out',stderr='original failure')
        with patch.object(bootstrap.subprocess,'run',return_value=result) as run:
            with self.assertRaises(subprocess.CalledProcessError):commands.run('shell','getprop','ro.kernel.qemu')
        self.assertEqual(receipt['commands'][0]['stderr'],'original failure')
        self.assertLessEqual(run.call_args.kwargs['timeout'],8)
    def test_timeout_preserves_original_partial_streams(self):
        receipt=record();commands=bootstrap.Commands('adb',bootstrap.SERIAL,receipt,time.monotonic()+40)
        failure=subprocess.TimeoutExpired('adb',8,output=b'partial out',stderr=b'partial failure')
        with patch.object(bootstrap.subprocess,'run',side_effect=failure):
            with self.assertRaises(subprocess.TimeoutExpired):commands.run('shell','dumpsys','wifi')
        self.assertEqual(receipt['commands'][0]['stdout'],'partial out')
        self.assertEqual(receipt['commands'][0]['stderr'],'partial failure')

    def test_initially_healthy_network_is_reprovisioned_after_actual_setup_loss(self):
        receipt=record();commands=SampleCommands([True,False,False,True,True],receipt)
        deadline=commands.deadline
        with patch.object(bootstrap.time,'sleep') as sleep:
            bootstrap.preflight(commands,receipt,identity())
        disable=('shell','pm','disable-user','--user','0',bootstrap.PACKAGE)
        connect=('shell','cmd','wifi','connect-network',bootstrap.SSID,'open')
        self.assertLess(commands.calls.index(disable),commands.calls.index(connect))
        self.assertEqual(commands.deadline,deadline)
        sleep.assert_called_once()
        self.assertTrue(receipt['initialNetworkUsable'])
        self.assertTrue(receipt['postSetupNetworkRecoveryRequired'])
        self.assertEqual(receipt['status'],'passed')
        self.assertFalse(receipt['applicationAcceptance'])
        self.assertEqual([row['phase'] for row in receipt['networkObservations']],
                         ['before-network-configuration','after-setup-package-handling',
                          'after-post-setup-sdk-wifi-configuration',
                          'after-post-setup-sdk-wifi-configuration',
                          'after-post-setup-network-recovery-confirmation'])
        self.assertTrue(all(row['raw'] and row['value']['runNonce']==row['runNonce']
                            for row in receipt['networkObservations']))
        stage=receipt['sdkWifiProvisioningStages'][0]
        self.assertEqual(stage['phase'],'post-setup-network-recovery')
        self.assertEqual(stage['status'],'passed')
        self.assertTrue(stage['wifiScans'][0]['raw'].endswith('AndroidWifi [ESS]'))
        self.assertEqual(stage['afterNetworkObservation']-stage['firstNetworkObservation'],2)
        self.assertGreater(stage['afterCommand'],stage['firstCommand'])
        self.assertFalse(any('put' in call or 'airplane-mode' in call for call in commands.calls))

    def test_post_setup_network_stays_missing_until_deadline_and_never_passes(self):
        receipt=record();commands=SampleCommands([True,False,False],receipt)
        commands.deadline=time.monotonic()+1
        with self.assertRaises(TimeoutError):bootstrap.preflight(commands,receipt,identity())
        self.assertNotEqual(receipt.get('status'),'passed')
        self.assertEqual(receipt['sdkWifiProvisioningStages'][0]['status'],'failed')
        self.assertFalse(receipt['networkObservations'][-1]['value']['usable'])

    def test_post_setup_recovery_requires_a_separate_usable_cm_confirmation(self):
        receipt=record();commands=SampleCommands([True,False,True,False],receipt)
        with self.assertRaisesRegex(ValueError,'disappeared after SDK Wi-Fi recovery'):
            bootstrap.preflight(commands,receipt,identity())
        self.assertNotEqual(receipt.get('status'),'passed')
        self.assertEqual(receipt['networkObservations'][-1]['phase'],
                         'after-post-setup-network-recovery-confirmation')

    def test_each_recovery_sample_must_match_source_installed_apk_and_native_scope(self):
        for key,value in [('sourceCommit','f'*40),('apkSha256','f'*64),
                          ('dirtySource',True),('applicationAcceptance',True)]:
            with self.subTest(key=key):
                receipt=record();commands=SampleCommands([True,False,True],receipt)
                def edit(sample):
                    if len(receipt['networkObservations'])==2:
                        if key in ('apkSha256','dirtySource'):sample['buildIdentity'][key]=value
                        else:sample[key]=value
                commands.edit=edit
                with self.assertRaises(ValueError):bootstrap.preflight(commands,receipt,identity())
                self.assertNotEqual(receipt.get('status'),'passed')
                self.assertEqual(len(receipt['networkObservations']),3)

    def test_initial_source_or_apk_mismatch_cannot_reach_setup_or_wifi_changes(self):
        for key,value in [('sourceCommit','f'*40),('apkSha256','f'*64)]:
            with self.subTest(key=key):
                receipt=record()
                def edit(sample):
                    if key=='apkSha256':sample['buildIdentity'][key]=value
                    else:sample[key]=value
                commands=SampleCommands([True],receipt,edit=edit)
                with self.assertRaises(ValueError):bootstrap.preflight(commands,receipt,identity())
                self.assertFalse(any('wifi' in call or 'force-stop' in call
                                     or 'disable-user' in call for call in commands.calls))

    def test_actual_healthy_samples_stay_unmodified_and_only_disable_exact_setup_package(self):
        receipt=record();commands=SampleCommands([True,True],receipt)
        bootstrap.preflight(commands,receipt,identity())
        self.assertFalse(any('wifi' in call for call in commands.calls))
        self.assertNotIn('sdkWifiProvisioningStages',receipt)
        self.assertEqual([call[-1] for call in commands.calls if 'force-stop' in call
                          or 'disable-user' in call],[bootstrap.PACKAGE,bootstrap.PACKAGE])
        self.assertTrue(all(row['value']['usable'] for row in receipt['networkObservations']))


class WifiScanControls(unittest.TestCase):
    def provision(self,commands,receipt,clock,observations):
        with patch.object(bootstrap.time,'monotonic',clock.now),patch.object(bootstrap.time,'sleep',clock.sleep),patch.object(bootstrap,'network_observation',side_effect=observations):
            bootstrap.provision_sdk_wifi(commands,receipt,identity(),'test-provisioning','test-cm')

    def test_enable_and_scan_progress_are_observed_before_single_connect(self):
        clock=Clock();receipt=record();commands=FakeCommands();commands.deadline=30
        status=['Wifi is disabled','Wifi is disabled','Wifi is enabled\nWifi scanning is always available']
        scans=['No scan results','No scan results',commands.scan]
        original=commands.run
        def run(*parts,**kwargs):
            raw=original(*parts,**kwargs)
            if parts[-1]=='status':return status.pop(0)
            if parts[-1]=='list-scan-results':return scans.pop(0)
            return raw
        commands.run=run
        self.provision(commands,receipt,clock,[False,True])
        stage=receipt['sdkWifiProvisioningStages'][0]
        self.assertEqual(stage['status'],'passed')
        self.assertEqual([row['raw'] for row in stage['wifiStatuses']][:2],['Wifi is disabled']*2)
        self.assertEqual([row['raw'] for row in stage['wifiScans']][:2],['No scan results']*2)
        self.assertEqual(stage['scanRequestResponse'],'Scan requested')
        self.assertEqual(stage['scanDeadlineMonotonic'],8)
        self.assertEqual(commands.deadline,30)
        request=('shell','cmd','wifi','start-scan');connect=('shell','cmd','wifi','connect-network',bootstrap.SSID,'open')
        self.assertEqual(commands.calls.count(request),1)
        self.assertEqual(commands.calls.count(connect),1)
        self.assertLess(max(i for i,call in enumerate(commands.calls) if call[-1]=='status'),commands.calls.index(request))
        self.assertLess(commands.calls.index(request),min(i for i,call in enumerate(commands.calls) if call[-1]=='list-scan-results'))
        self.assertLess(max(i for i,call in enumerate(commands.calls) if call[-1]=='list-scan-results'),commands.calls.index(connect))
        self.assertFalse(receipt['applicationAcceptance'])

    def test_disabled_unknown_and_contradictory_states_never_request_or_connect(self):
        for state in ('Wifi is disabled','Wifi state unavailable','Wifi is enabled\nWifi is disabled'):
            with self.subTest(state=state):
                clock=Clock();receipt=record();commands=FakeCommands();commands.deadline=30
                original=commands.run
                def run(*parts,**kwargs):
                    value=original(*parts,**kwargs)
                    return state if parts[-1]=='status' else value
                commands.run=run
                with self.assertRaises(TimeoutError):self.provision(commands,receipt,clock,[])
                self.assertEqual(clock.value,8)
                self.assertFalse(any('start-scan' in call or 'connect-network' in call for call in commands.calls))
                self.assertEqual(receipt['sdkWifiProvisioningStages'][0]['status'],'failed')

    def test_successful_scan_request_without_observed_ap_remains_failure(self):
        clock=Clock();receipt=record();commands=FakeCommands(scan='No scan results');commands.deadline=30
        with self.assertRaisesRegex(ValueError,'access point was not observed'):
            self.provision(commands,receipt,clock,[])
        stage=receipt['sdkWifiProvisioningStages'][0]
        self.assertEqual(stage['scanRequestResponse'],'Scan requested')
        self.assertEqual(stage['status'],'failed')
        self.assertEqual(len(stage['wifiScans']),8)
        self.assertEqual(commands.calls.count(('shell','cmd','wifi','start-scan')),1)
        self.assertFalse(any('connect-network' in call for call in commands.calls))

    def test_consumed_shared_budget_is_never_reset_for_wifi(self):
        clock=Clock();clock.value=24;receipt=record();commands=FakeCommands();commands.deadline=33
        with self.assertRaises(TimeoutError):self.provision(commands,receipt,clock,[])
        stage=receipt['sdkWifiProvisioningStages'][0]
        self.assertEqual(stage['scanDeadlineMonotonic'],23)
        self.assertEqual(commands.deadline,33)
        self.assertEqual(commands.calls,[('shell','cmd','wifi','set-wifi-enabled','enabled')])

    def test_phase_deadline_shortens_command_timeout_without_extending_total(self):
        clock=Clock();receipt=record()
        with patch.object(bootstrap.time,'monotonic',clock.now):
            commands=bootstrap.Commands('adb',bootstrap.SERIAL,receipt,33)
            with patch.object(bootstrap.subprocess,'run',return_value=subprocess.CompletedProcess([],0,stdout='Wifi is enabled',stderr='')) as run:
                commands.run('shell','cmd','wifi','status',deadline=2)
                self.assertEqual(run.call_args.kwargs['timeout'],2)
                commands.run('shell','cmd','wifi','status',deadline=100)
                self.assertEqual(run.call_args.kwargs['timeout'],8)
        self.assertEqual(commands.deadline,33)
        self.assertEqual([row['deadlineMonotonic'] for row in receipt['commands']],[2,33])

    def test_failed_scan_command_preserves_raw_streams_and_never_connects(self):
        clock=Clock();receipt=record()
        with patch.object(bootstrap.time,'monotonic',clock.now),patch.object(bootstrap.time,'sleep',clock.sleep):
            commands=bootstrap.Commands('adb',bootstrap.SERIAL,receipt,33)
            replies=[subprocess.CompletedProcess([],0,stdout='',stderr=''),
                     subprocess.CompletedProcess([],0,stdout='Wifi is enabled',stderr=''),
                     subprocess.CompletedProcess([],1,stdout='Scan failed',stderr='scan service unavailable')]
            with patch.object(bootstrap.subprocess,'run',side_effect=replies),patch.object(bootstrap,'network_observation') as observed:
                with self.assertRaises(subprocess.CalledProcessError):
                    bootstrap.provision_sdk_wifi(commands,receipt,identity(),'test-provisioning','test-cm')
                observed.assert_not_called()
        self.assertEqual(receipt['commands'][-1]['stdout'],'Scan failed')
        self.assertEqual(receipt['commands'][-1]['stderr'],'scan service unavailable')
        self.assertEqual(receipt['commands'][-1]['exitCode'],1)
        self.assertEqual(receipt['sdkWifiProvisioningStages'][0]['failureType'],'CalledProcessError')
        self.assertFalse(any('connect-network' in row['command'] for row in receipt['commands']))

    def test_observed_ap_and_successful_connect_still_require_actual_cm(self):
        clock=Clock();receipt=record();commands=FakeCommands();commands.deadline=12
        with patch.object(bootstrap.time,'monotonic',clock.now),patch.object(bootstrap.time,'sleep',clock.sleep),patch.object(bootstrap,'network_observation',return_value=False) as observed:
            with self.assertRaises(TimeoutError):
                bootstrap.provision_sdk_wifi(commands,receipt,identity(),'test-provisioning','test-cm')
        self.assertGreater(observed.call_count,0)
        self.assertEqual(receipt['sdkWifiProvisioningStages'][0]['status'],'failed')
        self.assertNotEqual(receipt.get('status'),'passed')
        self.assertEqual(commands.calls.count(('shell','cmd','wifi','start-scan')),1)


class SdkApObservationControls(unittest.TestCase):
    """Actual command recorder/CM validator with explicitly synthetic adb replies."""
    real_run=staticmethod(subprocess.run)
    def reset(self):
        self.clock=Clock();self.receipt=record();self.expected=identity()
        self.commands=bootstrap.Commands('adb',bootstrap.SERIAL,self.receipt,33)
        self.scanning='00:13:10:85:fe:01 2447 -50 10.860 AndroidWifi [ESS]'
        self.wifi_status='Wifi is enabled';self.cm_usable=True;self.transports=['wifi']
        self.connect_code=0;self.edit_cm=None

    def setUp(self):
        self.reset()
        self.patches=[patch.object(bootstrap.time,'monotonic',lambda:self.clock.now()),
                      patch.object(bootstrap.time,'sleep',lambda seconds:self.clock.sleep(seconds)),
                      patch.object(bootstrap.subprocess,'run',side_effect=self.reply)]
        for item in self.patches:item.start();self.addCleanup(item.stop)

    def reply(self,command,**options):
        if command[0]!='adb':return self.real_run(command,**options)
        parts=tuple(command[3:]);output='';code=0;self.clock.value+=min(.02,options['timeout'])
        if parts[-1]=='status':output=self.wifi_status
        elif parts[-1]=='list-scan-results':output=self.scanning
        elif 'connect-network' in parts:code=self.connect_code
        elif parts[:4]==('exec-out','content','read','--uri'):
            value=observation();value['runNonce']=parse_qs(urlsplit(parts[4]).query)['runNonce'][0]
            value['transports']=self.transports
            if not self.cm_usable:value.update(activeNetwork='',activeNetworkAfter='',capabilitiesPresent=False,
                                               internetCapability=False,stableDuringRead=False,usable=False)
            if self.edit_cm:self.edit_cm(value)
            output=json.dumps(value)
        return subprocess.CompletedProcess(command,code,stdout=output,stderr='connect failed' if code else '')

    def provision(self,*,reuse=False):
        bootstrap.provision_sdk_wifi(self.commands,self.receipt,self.expected,'unit-stage','unit-cm',reuse_observed_ap=reuse)

    def issue(self):
        self.provision();self.assertIsNotNone(self.commands._sdk_wifi_ap)
        return self.commands._sdk_wifi_ap

    def test_same_invocation_ap_can_select_ssid_without_claiming_a_new_scan(self):
        proof=self.issue();first_cm=len(self.receipt['networkObservations']);before=len(self.receipt['commands'])
        self.scanning='No scan results';self.provision(reuse=True)
        rows=self.receipt['commands'][before:];stage=self.receipt['sdkWifiProvisioningStages'][-1]
        self.assertEqual(stage['apSelection'],'reused-observed-AP');self.assertEqual(stage['wifiScans'],[])
        self.assertNotIn('scanRequestResponse',stage);self.assertFalse(stage['observedAp']['currentConnectivityProven'])
        self.assertFalse(any('start-scan' in row['command'] or 'list-scan-results' in row['command'] for row in rows))
        self.assertEqual(sum('connect-network' in row['command'] for row in rows),1)
        self.assertEqual(len(self.receipt['networkObservations']),first_cm+1)
        self.assertNotEqual(self.receipt['networkObservations'][0]['runNonce'],self.receipt['networkObservations'][-1]['runNonce'])
        self.assertIs(self.commands._sdk_wifi_ap,proof);self.assertEqual(self.commands.deadline,33)

    def test_missing_proof_still_requires_an_observed_ap(self):
        self.scanning='No scan results'
        with self.assertRaisesRegex(ValueError,'access point was not observed'):self.provision(reuse=True)
        self.assertFalse(any('connect-network' in row['command'] for row in self.receipt['commands']))
        self.assertIsNone(self.commands._sdk_wifi_ap)

    def test_foreign_command_record_serial_identity_and_session_reject_proof(self):
        for kind in ('dict','command','record','serial','source','apk','identity-mutation','session','raw-evidence'):
            with self.subTest(kind=kind):
                self.reset();proof=self.issue()
                if kind=='dict':self.commands._sdk_wifi_ap=proof.describe()
                elif kind=='command':
                    other=bootstrap.Commands('adb',bootstrap.SERIAL,self.receipt,33);other._sdk_wifi_ap=proof;self.commands=other
                elif kind=='record':self.receipt=dict(self.receipt)
                elif kind=='serial':self.commands.serial='emulator-5556'
                elif kind=='source':self.expected=dict(self.expected,sourceCommit='f'*40)
                elif kind=='apk':self.expected=dict(self.expected,apkSha256='f'*64)
                elif kind=='identity-mutation':self.expected['apkSha256']='f'*64
                elif kind=='session':self.commands._sdk_wifi_session=object()
                else:self.receipt['commands'][proof.scan]['stdout']='forged AndroidWifi [ESS]'
                before=len(self.receipt['commands'])
                with self.assertRaises(ValueError):self.provision(reuse=True)
                self.assertEqual(len(self.receipt['commands']),before)
                self.assertEqual(self.receipt['sdkWifiProvisioningStages'][-1]['status'],'failed')
                self.assertIsNone(self.commands._sdk_wifi_ap)

    def test_new_preflight_on_same_commands_expires_old_proof_before_any_command(self):
        self.issue();session=self.commands._sdk_wifi_session
        with patch.object(self.commands,'run',return_value='0'):
            with self.assertRaises(ValueError):bootstrap.preflight(self.commands,self.receipt,self.expected)
        self.assertIsNone(self.commands._sdk_wifi_ap);self.assertIsNot(self.commands._sdk_wifi_session,session)

    def test_unconfirmed_wifi_cm_and_failed_connect_cannot_issue_proof(self):
        for transports in (['cellular'],[],None,'wifi'):
            with self.subTest(transports=transports):
                self.reset();self.transports=transports;self.provision()
                self.assertIsNone(self.commands._sdk_wifi_ap)
        self.reset();self.connect_code=1
        with self.assertRaises(subprocess.CalledProcessError):self.provision()
        self.assertIsNone(self.commands._sdk_wifi_ap);self.assertEqual(self.receipt['networkObservations'],[])
        self.assertEqual(self.receipt['sdkWifiProvisioningStages'][-1]['status'],'failed')

    def test_cached_ap_cannot_mask_new_disabled_state_failed_connect_or_cm(self):
        for failure in ('disabled','connect','unusable-cm','foreign-cm'):
            with self.subTest(failure=failure):
                self.reset();self.issue()
                if failure=='disabled':self.wifi_status='Wifi is disabled'
                elif failure=='connect':self.connect_code=1
                elif failure=='unusable-cm':self.cm_usable=False
                else:self.edit_cm=lambda value:value.update(runNonce='f'*32)
                with self.assertRaises((TimeoutError,ValueError,subprocess.SubprocessError)):self.provision(reuse=True)
                self.assertIsNone(self.commands._sdk_wifi_ap)
                self.assertEqual(self.receipt['sdkWifiProvisioningStages'][-1]['status'],'failed')
                self.assertLessEqual(self.clock.value,33)

    def test_expired_shared_budget_never_gets_a_fresh_budget_from_proof(self):
        self.issue();self.clock.value=33
        with self.assertRaises(TimeoutError):self.provision(reuse=True)
        self.assertEqual(self.commands.deadline,33);self.assertIsNone(self.commands._sdk_wifi_ap)

    def test_failed_evidence_binding_preserves_failure_instead_of_passed_stage(self):
        original=bootstrap.network_observation
        def changed(*args,**kwargs):
            result=original(*args,**kwargs)
            self.receipt['commands'][2]['exitCode']=1  # Actual scan request record is unrelated to issuance.
            self.receipt['commands'][3]['timedOut']=True  # Observed-AP result must never issue proof after timeout.
            return result
        with patch.object(bootstrap,'network_observation',side_effect=changed):
            with self.assertRaises(ValueError):self.provision()
        stage=self.receipt['sdkWifiProvisioningStages'][-1]
        self.assertEqual(stage['status'],'failed');self.assertIn('failureType',stage)
        self.assertIsNone(self.commands._sdk_wifi_ap)


if __name__=='__main__':unittest.main()
