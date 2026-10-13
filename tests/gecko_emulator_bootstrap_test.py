"""Counterfeit host controls only. No adb, Android or app acceptance is executed."""
import importlib.util
from pathlib import Path
import subprocess
import sys
import time
import unittest
from unittest.mock import patch

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
        with patch.object(bootstrap,'network_observation',side_effect=[True,False]):
            with self.assertRaises(ValueError):bootstrap.preflight(FakeCommands(),record(),identity())
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


if __name__=='__main__':unittest.main()
