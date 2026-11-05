#!/usr/bin/env python3
"""Host-only real OpenSSL wire controls and offline false-proof rejection. No Android claim."""
import argparse
import copy
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import socket
import ssl
import struct
import subprocess
import sys
import time
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools/browser"))
sys.path.insert(0, str(ROOT / "tools/gecko"))
from fingerprint_fixture_server import EphemeralCertificates
from native_tls_probe_server import NativeTlsServer, TRIALS, parse_client_hello, handshake_bytes, NeedMore, HOSTS
from native_tls_probe_contract import validate_native_tls, validate_wire, strict_json, MIN, MAX, PROTECTED


def context(strict=False, ca=None):
    value = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
    value.minimum_version = ssl.TLSVersion.TLSv1_3 if strict else ssl.TLSVersion.TLSv1_2
    value.maximum_version = ssl.TLSVersion.TLSv1_3
    value.options |= ssl.OP_NO_TICKET
    value.set_alpn_protocols(["h2", "http/1.1"])
    if ca:
        value.load_verify_locations(cafile=ca)
    else:
        value.check_hostname = False
        value.verify_mode = ssl.CERT_NONE
    return value


def client_hello(strict=False):
    incoming, outgoing = ssl.MemoryBIO(), ssl.MemoryBIO()
    native = context(strict).wrap_bio(incoming, outgoing, server_hostname=HOSTS[0])
    try:
        native.do_handshake()
    except ssl.SSLWantReadError:
        pass
    return outgoing.read()


def synthetic_device(host, nonce, source, tree, leaf):
    def prefs(strict=False):
        values = {MIN: dict(default=4 if strict else 3, user=None, effective=4 if strict else 3, hasUserValue=False),
                  MAX: dict(default=4, user=None, effective=4, hasUserValue=False)}
        values.update({key: dict(default=key != PROTECTED[0], user=None, effective=key != PROTECTED[0], hasUserValue=False) for key in PROTECTED})
        return values
    rows = []
    for name, port, version, success in TRIALS:
        row = dict(trial=name, target="https://" + HOSTS[0] + ":" + str(port) + "/tls-probe?run=" + nonce + "&source=" + source + "&trial=" + name,
                   started=True, located=success, targetError=not success, leafVerified=success, securityExceptionUsed=False, titleMatched=success, nativeTargetTlsReady=success, nativeStopOwnershipVerified=False, stopCallbacks=0, successfulStopCallbacks=0)
        if success:
            row.update(secure=True, leafSha256=leaf)
        else:
            row.update(errorCategory=2, errorCode=34, nativeErrorUrlMatched=True)
        rows.append(row)
    return dict(schema=1, status="observed", stage="complete", failureCode="", runNonce=nonce, sourceCommit=source, sourceTree=tree,
                actualAndroidExecution=True, actualGeckoExecution=True, standaloneSessionCapabilityOnly=True, diagnosticOnly=True,
                nativeRestoreSucceeded=True, enterpriseRootsRestored=True, enterpriseRootsInitiallyEnabled=False, pid=1234, elapsedMs=1000,
                releaseQualification=False, nativeSettingReadbackIsWireProof=False, fullTlsFingerprintEmulation=False,
                quicWireVerified=False, debuggingEndpointUsed=False, javascriptTlsOverrideUsed=False, rfpModified=False, h2OrH3PrefsModified=False,
                nativeOriginal=prefs(), nativeStrict=prefs(True), nativeRestored=prefs(), observations=rows)


class ParserControls(unittest.TestCase):
    def test_diagnostic_workflow_and_fixed_native_write_scope(self):
        import yaml
        workflow=yaml.safe_load((ROOT/'.github/workflows/native-tls-probe.yml').read_text())
        self.assertEqual(workflow['permissions'],{'contents':'read'})
        self.assertEqual(workflow['on']['push']['branches'],['diagnostics/native-tls-*'])
        self.assertEqual(set(workflow['jobs']),{'build','native_tls_probe'})
        runtime=workflow['jobs']['native_tls_probe']
        self.assertEqual(runtime['needs'],'build')
        commands='\n'.join(str(step.get('run',''))for step in runtime['steps'])
        self.assertIn('run_native_tls_probe.py',commands)
        self.assertIn('check_native_tls_evidence.py',commands)
        self.assertIn('-cores 4',commands.replace('\n',' '))
        self.assertNotIn('continue-on-error',str(workflow))
        self.assertNotIn('workflow_dispatch',workflow['on'])
        java=(ROOT/'tests/gecko/NativeTlsProbeActivity.java').read_text()
        self.assertIn('GeckoPreferenceController.setGeckoPref(key,Integer.valueOf(value),branch)',java)
        self.assertIn('Arrays.asList(MIN,MAX).contains(key)',java)
        self.assertIn('runtime.getSettings().setEnterpriseRootsEnabled(initialEnterpriseRoots)',java)
        for forbidden in ('setGeckoPref(RFP','setGeckoPref(H2','setGeckoPref(H3','evaluateJS','evaluateJavascript','remoteDebuggingEnabled(true)','CDP','setDefaultSSL'):
            self.assertNotIn(forbidden,java)
    def test_actual_openssl_clienthello_default_and_strict(self):
        for strict in (False, True):
            row = parse_client_hello(client_hello(strict))
            self.assertEqual(row["serverNames"], [HOSTS[0]])
            self.assertIn(772, row["supportedVersions"])
            self.assertEqual(771 in row["supportedVersions"], not strict)
            self.assertEqual(row["offeredAlpn"], ["h2", "http/1.1"])
            self.assertFalse(row["preSharedKeyOffered"])

    def test_fragmented_real_clienthello_records(self):
        raw = client_hello()
        hello = handshake_bytes(raw)
        split = 37
        parts = [b"\x16\x03\x01" + len(piece).to_bytes(2, "big") + piece for piece in (hello[:split], hello[split:])]
        self.assertEqual(parse_client_hello(raw), parse_client_hello(b"".join(parts)))
        with self.assertRaises(NeedMore):
            parse_client_hello(b"".join(parts)[:-1])

    def test_malformed_wire_cannot_be_a_clienthello(self):
        raw = client_hello()
        for bad in (b"", b"\x17" + raw[1:], raw[:2] + b"\x09" + raw[3:], raw[:3] + b"\xff\xff" + raw[5:], b"x" * 65537):
            with self.assertRaises((ValueError, NeedMore)):
                parse_client_hello(bad)

    def test_duplicate_and_nonfinite_json_rejected(self):
        for raw in (b'{"x":1,"x":2}', b'{"x":NaN}', b'{"x":Infinity}', b'\xff', b' ' * 262145):
            with self.assertRaises((ValueError, UnicodeError)):
                strict_json(raw)


class RealHostWireControls(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.certificates = EphemeralCertificates()
        cls.nonce, cls.source, cls.tree = "b" * 32, "a" * 40, "c" * 40
        cls.server = None
        try:
            cls.server = NativeTlsServer(cls.certificates, cls.nonce, cls.source).start()
            for name, port, version, success in TRIALS:
                peer = socket.create_connection(("127.0.0.1", cls.server.port), timeout=5)
                peer.settimeout(5)
                peer.sendall(("CONNECT " + HOSTS[0] + ":" + str(port) + " HTTP/1.1\r\nHost: " + HOSTS[0] + ":" + str(port) + "\r\n\r\n").encode())
                header = bytearray()
                while not header.endswith(b"\r\n\r\n"):
                    header += peer.recv(1)
                if success:
                    with context(name.startswith("strict-"), cls.certificates.ca).wrap_socket(peer, server_hostname=HOSTS[0]) as native:
                        target = "/tls-probe?run=" + cls.nonce + "&source=" + cls.source + "&trial=" + name
                        native.sendall(("GET " + target + " HTTP/1.1\r\nHost: " + HOSTS[0] + ":" + str(port) + "\r\n\r\n").encode())
                        response = bytearray()
                        while True:
                            block = native.recv(4096)
                            if not block:
                                break
                            response.extend(block)
                        if not response.startswith(b"HTTP/1.1 200 OK"):
                            raise AssertionError("actual host TLS response unavailable")
                else:
                    try:
                        context(True, cls.certificates.ca).wrap_socket(peer, server_hostname=HOSTS[0])
                    except ssl.SSLError as error:
                        if error.reason != "TLSV1_ALERT_PROTOCOL_VERSION":
                            raise
                    else:
                        raise AssertionError("actual strict TLS1.2 peer succeeded")
                    finally:
                        peer.close()
            if cls.server is not None:
                cls.server.close()
            cls.host = cls.server.snapshot()
            cls.device = synthetic_device(cls.host, cls.nonce, cls.source, cls.tree, cls.certificates.leaf_sha)
        except BaseException:
            try:
                if cls.server is not None:
                    cls.server.close()
            finally:
                cls.certificates.close()
            raise

    @classmethod
    def tearDownClass(cls):
        cls.certificates.close()
        if cls.certificates.directory.exists():
            raise AssertionError("host private TLS material cleanup failed")

    def checked(self, device=None, host=None):
        return validate_native_tls(self.device if device is None else device, self.host if host is None else host,
                                   run=self.nonce, source=self.source, tree=self.tree, leaf=self.certificates.leaf_sha)

    def test_four_real_openssl_tls_peers(self):
        result = self.checked()
        self.assertEqual(result["uniqueClientRandoms"], 4)
        self.assertTrue(result["trials"]["strict-tls12"]["protocolRejected"])
        self.assertFalse(result["fullTlsFingerprintEmulation"])

    def test_native_ack_does_not_replace_wire(self):
        host = copy.deepcopy(self.host)
        host["records"][1]["clientHello"]["supportedVersions"] = [772, 771]
        with self.assertRaises(ValueError):
            self.checked(host=host)

    def test_timeout_cannot_be_protocol_rejection(self):
        host = copy.deepcopy(self.host)
        row = next(row for row in host["records"] if row["trial"] == "strict-tls12")
        row.update(errorType="TimeoutError", tlsErrorReason="UNSUPPORTED_PROTOCOL")
        with self.assertRaises(ValueError):
            self.checked(host=host)

    def test_resumption_stale_random_and_alpn_mutation_rejected(self):
        for mutate in (lambda h: h["records"][1]["clientHello"].update(preSharedKeyOffered=True),
                       lambda h: h["records"][1]["clientHello"].update(clientRandomHex=h["records"][0]["clientHello"]["clientRandomHex"]),
                       lambda h: h["records"][1]["clientHello"].update(offeredAlpn=["http/1.1"])):
            host = copy.deepcopy(self.host)
            mutate(host)
            with self.assertRaises(ValueError):
                self.checked(host=host)

    def test_restore_user_branch_and_rfp_are_exact(self):
        for mutate in (lambda d: d["nativeRestored"][MIN].update(user=3, hasUserValue=True),
                       lambda d: d["nativeStrict"][PROTECTED[0]].update(default=True, effective=True),
                       lambda d: d["nativeStrict"][MIN].update(default=True, effective=True),
                       lambda d: d.update(nativeRestoreSucceeded=False)):
            device = copy.deepcopy(self.device)
            mutate(device)
            with self.assertRaises(ValueError):
                self.checked(device=device)

    def test_native_timeout_wrong_nonce_and_certificate_exception_rejected(self):
        for mutate in (lambda d: d["observations"][1].update(errorCategory=3, errorCode=51),
                       lambda d: d.update(runNonce="d" * 32),
                       lambda d: d["observations"][0].update(securityExceptionUsed=True)):
            device = copy.deepcopy(self.device)
            mutate(device)
            with self.assertRaises(ValueError):
                self.checked(device=device)

    def test_stop_cannot_replace_nonce_document_title_or_claim_url_ownership(self):
        for mutate in (lambda d:d['observations'][0].update(titleMatched=False,stopCallbacks=1,successfulStopCallbacks=1),
                       lambda d:d['observations'][0].update(nativeStopOwnershipVerified=True),
                       lambda d:d['observations'][1].update(nativeErrorUrlMatched=False)):
            device=copy.deepcopy(self.device);mutate(device)
            with self.assertRaises(ValueError):self.checked(device=device)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path)
    args, remaining = parser.parse_known_args()
    files = [Path(__file__), ROOT / "tools/browser/native_tls_probe_server.py", ROOT / "tools/gecko/native_tls_probe_contract.py", ROOT / "tests/gecko/NativeTlsProbeActivity.java", ROOT / "tests/gecko/NativeTlsProbeProvider.java",ROOT/'.github/workflows/native-tls-probe.yml',ROOT/'tools/browser/check_native_tls_evidence.py',ROOT/'tools/gecko/run_native_tls_probe.py',ROOT/'tools/gecko/check_native_tls_package.py']
    sha = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()
    before = {str(path.relative_to(ROOT)): sha(path) for path in files}
    suite = unittest.defaultTestLoader.loadTestsFromModule(sys.modules[__name__])
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    stable = all(sha(ROOT / name) == digest for name, digest in before.items())
    report = dict(schema=1, status="passed" if result.wasSuccessful() and stable else "failed", total=result.testsRun, passed=result.testsRun - len(result.failures) - len(result.errors),
                  sourceCommit=subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip(), sourceFiles=before, executionInputsUnchanged=stable,
                  actualHostOpenSslWireExecution=True, actualAndroidExecution=False, actualGeckoExecution=False, actualNativePreferenceExecution=False,
                  scope="Host-only bounded actual OpenSSL ClientHello/TLS peer and parser/contract false-proof checks; native callback/preference packets are explicitly synthetic, not Android or Gecko proof.")
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(report, indent=2) + "\n")
    raise SystemExit(0 if report["status"] == "passed" else 1)
