"""Host models of adbd setup boundaries; never Android or TLS acceptance."""
import importlib.util
from pathlib import Path
import subprocess
from types import SimpleNamespace
import unittest
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "ca_transport_under_test", ROOT / "tools/browser/fingerprint_fixture_server.py")
HOST = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(HOST)


class Clock:
    def __init__(self):
        self.now = 100.0

    def __call__(self):
        return self.now


class AdbModel:
    def __init__(self, clock, *, offline=False, delays=None, fault=None, uid=None):
        self.clock, self.offline = clock, offline
        self.delays, self.fault, self.uid_override = delays or {}, fault, uid
        self.uid = 2000
        self.calls = []

    def __call__(self, *args, check=True, timeout=30):
        self.calls.append((args, check, timeout))
        index = len(self.calls)
        delay = self.delays.get(index, 0)
        if delay > timeout:
            self.clock.now += timeout
            raise subprocess.TimeoutExpired(args, timeout, output=b"waiting", stderr=b"offline")
        self.clock.now += delay
        if args == ("wait-for-device",):
            self.offline = False
        elif self.offline or args == self.fault:
            raise subprocess.CalledProcessError(1, args, output=b"original output", stderr=b"device offline")
        elif args == ("root",):
            self.uid = 0
        elif args == ("unroot",):
            self.uid = 2000
        elif args != ("shell", "id", "-u"):
            raise AssertionError("Unexpected setup command: " + repr(args))
        raw = str(self.uid if self.uid_override is None else self.uid_override).encode() + b"\n"
        return SimpleNamespace(returncode=0, stdout=raw, stderr=b"")


def legacy_set_root(instance, root):
    # Exact behavior of public06 before this fix. This is a host-only baseline.
    instance.adb("root" if root else "unroot")
    instance.adb("wait-for-device", timeout=60)
    uid = instance.adb("shell", "id", "-u").stdout.decode().strip()
    HOST.require(uid == ("0" if root else "2000"), "legacy UID mismatch")
    return int(uid)


class AndroidUserCaTransportTests(unittest.TestCase):
    def invoke(self, root=True, **kwargs):
        clock = Clock()
        adb = AdbModel(clock, **kwargs)
        owner = HOST.AndroidUserCa(adb, SimpleNamespace())
        with patch.object(HOST.time, "monotonic", clock):
            result = owner.set_root(root)
        return result, adb

    def test_actual_old_order_rejects_offline_transport_before_it_can_wait(self):
        adb = AdbModel(Clock(), offline=True)
        with self.assertRaises(subprocess.CalledProcessError):
            legacy_set_root(SimpleNamespace(adb=adb), True)
        self.assertEqual([c[0] for c in adb.calls], [("root",)])

    def test_current_waits_before_the_single_request_and_checks_exact_uid(self):
        for root, expected in ((True, 0), (False, 2000)):
            with self.subTest(root=root):
                result, adb = self.invoke(root, offline=True)
                self.assertEqual(result, expected)
                self.assertEqual([c[0] for c in adb.calls], [
                    ("wait-for-device",), ("root" if root else "unroot",),
                    ("wait-for-device",), ("shell", "id", "-u")])
                self.assertTrue(all(c[1] is True for c in adb.calls))

    def test_privilege_failure_propagates_with_original_outputs_and_no_replay(self):
        for action in ("root", "unroot"):
            with self.subTest(action=action):
                clock = Clock()
                adb = AdbModel(clock, fault=(action,))
                owner = HOST.AndroidUserCa(adb, SimpleNamespace())
                with patch.object(HOST.time, "monotonic", clock), self.assertRaises(subprocess.CalledProcessError) as caught:
                    owner.set_root(action == "root")
                self.assertEqual(caught.exception.stdout, b"original output")
                self.assertEqual(caught.exception.stderr, b"device offline")
                self.assertEqual([c[0] for c in adb.calls], [("wait-for-device",), (action,)])
                if hasattr(caught.exception, "__notes__"):
                    self.assertIn("privilege-change", caught.exception.__notes__[0])

    def test_disconnected_device_exhausts_original_sixty_second_budget_without_action(self):
        clock = Clock()
        adb = AdbModel(clock, delays={1: 61})
        with patch.object(HOST.time, "monotonic", clock), self.assertRaises(subprocess.TimeoutExpired):
            HOST.AndroidUserCa(adb, SimpleNamespace()).set_root(True)
        self.assertEqual([c[0] for c in adb.calls], [("wait-for-device",)])
        self.assertEqual(clock.now, 160)

    def test_setup_uses_one_shared_budget_and_retains_command_caps(self):
        _, adb = self.invoke(delays={1: 20, 2: 10, 3: 15})
        self.assertEqual([c[2] for c in adb.calls], [60, 30, 30, 15])

    def test_post_change_timeout_is_not_restarted_or_converted_to_uid_success(self):
        clock = Clock()
        adb = AdbModel(clock, delays={1: 25, 2: 20, 3: 16})
        with patch.object(HOST.time, "monotonic", clock), self.assertRaises(subprocess.TimeoutExpired):
            HOST.AndroidUserCa(adb, SimpleNamespace()).set_root(True)
        self.assertEqual([c[0] for c in adb.calls], [("wait-for-device",), ("root",), ("wait-for-device",)])
        self.assertEqual(adb.calls[-1][2], 15)

    def test_wrong_or_malformed_uid_cannot_qualify(self):
        for root, uid in ((True, 2000), (False, 0), (True, ""), (False, "uid=2000")):
            with self.subTest(root=root, uid=uid), self.assertRaises(ValueError):
                self.invoke(root, uid=uid)

    def test_no_ca_writes_or_evidence_reads_occur_in_transport_setup(self):
        _, adb = self.invoke()
        self.assertFalse(any(c[0][0] in ("push", "exec-out") for c in adb.calls))

    def test_cleanup_transport_failure_cannot_delete_or_claim_certificate_removal(self):
        clock = Clock()
        adb = AdbModel(clock, fault=("root",))
        owner = HOST.AndroidUserCa(adb, SimpleNamespace())
        owner.path = "/data/misc/user/0/cacerts-added/1234abcd.0"
        owner.root_requested = True
        owner.receipt = {"removedAfterExecution": False}
        with patch.object(HOST.time, "monotonic", clock), self.assertRaises(subprocess.CalledProcessError):
            owner.remove()
        self.assertEqual(owner.path, "/data/misc/user/0/cacerts-added/1234abcd.0")
        self.assertFalse(owner.receipt["removedAfterExecution"])
        self.assertEqual(adb.uid, 2000)
        self.assertEqual(owner.receipt["cleanupShellUid"], 2000)
        self.assertFalse(any(c[0][0] in ("push", "exec-out") or c[0][:2] == ("shell", "rm") for c in adb.calls))
        self.assertEqual([c[0] for c in adb.calls if c[0] in (("root",), ("unroot",))], [("root",), ("unroot",)])


if __name__ == "__main__":
    unittest.main()
