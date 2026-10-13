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


class FakeCommands:
    """A unit double; never a real command receipt."""
    def __init__(self, qemu='1', scan='00:11:22:33:44:55 2412 -45 0 AndroidWifi [ESS]'):
        self.calls=[];self.qemu=qemu;self.scan=scan;self.deadline=time.monotonic()+30
    def run(self,*parts,**unused):
        self.calls.append(parts)
        if parts==('shell','getprop','ro.kernel.qemu'):return self.qemu
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
        commands.deadline=time.monotonic()+9
        with patch.object(bootstrap,'network_observation',side_effect=[True,False]):
            with self.assertRaises(ValueError):bootstrap.preflight(commands,record(),identity())
    def test_similar_ssid_never_connects_or_disables_setup(self):
        for ssid in ['AndroidWifi-other','Other-AndroidWifi','OtherAndroidWifi']:
            with self.subTest(ssid=ssid):
                commands=FakeCommands(scan='00:11:22:33:44:55 2412 -45 0 '+ssid+' [ESS]')
                commands.deadline=time.monotonic()+9
                with patch.object(bootstrap,'network_observation',return_value=False):
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


if __name__=='__main__':unittest.main()
