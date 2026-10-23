import importlib.util
from pathlib import Path
import time
import unittest
from unittest.mock import patch

spec=importlib.util.spec_from_file_location('native_setup_draft',Path(__file__).resolve().parents[1] / 'tools/gecko/prepare_native_adb.py')
setup=importlib.util.module_from_spec(spec);spec.loader.exec_module(setup)


class FakeCommands:
    def __init__(self, addresses=''):
        self.calls=[];self.addresses=addresses;self.deadline=time.monotonic()+.5
    def run(self,*parts):
        self.calls.append(parts)
        if parts[:4]==('shell','ip','-4','-o'):return self.addresses
        return ''


class NativeSetupControls(unittest.TestCase):
    def test_targets_are_explicit_and_normal_guard_is_unchanged(self):
        for serial in ('physical-phone','emulator-5554','emulator-5558'):
            with self.assertRaises(ValueError):setup.BootstrapCommands('adb',serial,{},10)
        accepted=setup.BootstrapCommands('adb','emulator-5556',{},10)
        self.assertEqual(accepted.serial,'emulator-5556')
        with self.assertRaises(ValueError):setup.normal.Commands('adb','emulator-5556',{},10)

    def test_actual_backend_and_both_addresses_are_required(self):
        valid='VLAN -1 (mynet):\n TCP[HOST_FORWARD] 115 127.0.0.1 5555 10.0.2.15 5555 0 0\n'
        setup.verify_forward(valid)
        invalid=[valid.replace('mynet','virtio-wifi'),valid.replace('10.0.2.15','10.0.2.16'),valid.replace('127.0.0.1','0.0.0.0'),valid.replace('5555','5557'),valid+valid,'']
        for value in invalid:
            with self.assertRaises(ValueError):setup.verify_forward(value)

    def test_monitor_rejects_unapproved_commands_before_connecting(self):
        with patch.object(setup.socket,'socket') as socket:
            with self.assertRaises(ValueError):setup.monitor(Path('/tmp/example.sock'),'system_reset')
            socket.assert_not_called()

    def test_unconfirmed_emulator_or_package_never_reaches_network_reset(self):
        for record in ({},{'confirmedQemu':True},{'disabledStateConfirmed':True}):
            commands=FakeCommands()
            with patch.object(setup.normal,'preflight'):
                with self.assertRaises(ValueError):setup.persistent_network(commands,record,{})
            self.assertEqual(commands.calls,[])

    def test_incomplete_teardown_does_not_connect_or_promote(self):
        commands=FakeCommands('16: wlan0 inet 10.0.2.16/24');record={'confirmedQemu':True,'disabledStateConfirmed':True}
        with patch.object(setup.normal,'preflight'),patch.object(setup.normal,'provision_sdk_wifi') as provision:
            with self.assertRaises(TimeoutError):setup.persistent_network(commands,record,{})
            provision.assert_not_called()
        self.assertNotIn('nativeReady',record)

    def test_missing_final_connectivity_is_rejected_after_provisioning(self):
        commands=FakeCommands();record={'confirmedQemu':True,'disabledStateConfirmed':True}
        with patch.object(setup.normal,'preflight'),patch.object(setup.normal,'provision_sdk_wifi') as provision,patch.object(setup.normal,'network_observation',return_value=False):
            with self.assertRaises(ValueError):setup.persistent_network(commands,record,{})
            provision.assert_called_once()
        self.assertNotIn('nativeReady',record)


if __name__=='__main__':unittest.main()
