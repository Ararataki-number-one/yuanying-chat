#!/usr/bin/env python3
"""Four actual Gecko public-native-pref/TLS wire capability trials on a clean API35 emulator."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import shlex
import subprocess
import sys
import time
import uuid

from profile_invocation_contract import expected_build, verify_installed
from native_tls_probe_contract import strict_json, validate_native_tls, require

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools/browser"))
from fingerprint_fixture_server import EphemeralCertificates, AndroidUserCa
from native_tls_probe_server import NativeTlsServer, GUEST_PORT
PACKAGE = "local.pocketchat.test"


def sha(path):
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(65536), b""):
            h.update(block)
    return h.hexdigest()


def snapshot():
    names = subprocess.check_output(["git", "ls-files", "app", "tests", "tools", ".github"], cwd=ROOT, text=True).splitlines()
    return {name: sha(ROOT / name) for name in sorted(set(names)) if (ROOT / name).is_file()}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--adb", default="adb")
    parser.add_argument("--serial", default="emulator-5554")
    parser.add_argument("--apk", required=True, type=Path)
    parser.add_argument("--source", required=True)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    source = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
    tree = subprocess.check_output(["git", "rev-parse", "HEAD^{tree}"], cwd=ROOT, text=True).strip()
    require(args.source == source and re.fullmatch("[0-9a-f]{40}", source) and args.serial == "emulator-5554", "exact source/emulator required")
    require(not subprocess.check_output(["git", "status", "--porcelain"], cwd=ROOT, text=True).strip(), "clean selected source required")
    output = args.output.absolute()
    require(not output.exists() and all(not p.is_symlink() for p in (output, *output.parents)), "fresh bounded output directory")
    gradle = (ROOT / "app/build.gradle").read_text()
    identity = expected_build(args.apk, source, tree, re.search(r"versionName '([^']+)'", gradle)[1], int(re.search(r"versionCode ([0-9]+)", gradle)[1]))
    before = snapshot()
    output.mkdir(parents=True)
    run = uuid.uuid4().hex
    device = None
    checked = None
    errors = []
    server = certificates = ca = None
    reversed_port = False
    host_tls = {}
    cleanup = dict(appStopped=False, appDataCleared=False, reverseRemoved=False, caRemoved=False, privateMaterialRemoved=False, shellUidRestored=False)
    def adb(*parts, check=True, timeout=25):
        return subprocess.run([args.adb, "-s", args.serial, *parts], capture_output=True, check=check, timeout=timeout)
    try:
        require(adb("shell", "getprop", "ro.kernel.qemu").stdout.strip() == b"1" and adb("shell", "getprop", "ro.build.version.sdk").stdout.strip() == b"35", "actual controlled API35 emulator")
        require(adb("shell", "getconf", "_NPROCESSORS_ONLN").stdout.strip() == b"4" and adb("shell", "id", "-u").stdout.strip() == b"2000", "actual four native guest CPUs and shell UID2000")
        verify_installed(strict_json(adb("exec-out", "content", "read", "--uri", "content://" + PACKAGE + ".evidence/build-identity").stdout), identity)
        require(not any("tcp:" + str(GUEST_PORT) in line.split() for line in adb("reverse", "--list").stdout.decode().splitlines()), "existing guest reverse must not be replaced")
        certificates = EphemeralCertificates()
        ca = AndroidUserCa(adb, certificates)
        ca.install()
        host_tls = dict(certificates.public, trustInstallation=ca.receipt, guestPort=GUEST_PORT,
                        binding=dict(sourceCommit=source, sourceTree=tree, runNonce=run, integrationApkSha256=identity["apkSha256"]))
        server = NativeTlsServer(certificates, run, source).start()
        adb("reverse", "tcp:" + str(GUEST_PORT), "tcp:" + str(server.port))
        reversed_port = True
        require(adb("shell", "pm", "clear", PACKAGE).stdout.strip() == b"Success", "fresh integration-only native profile")
        command = ["am", "start", "-W", "-n", PACKAGE + "/local.pocketchat.NativeTlsProbeActivity",
                   "--es", "sourceCommit", source, "--es", "runNonce", run,
                   "--es", "expectedLeafSha256", certificates.leaf_sha, "--ei", "fixturePort", str(GUEST_PORT)]
        adb("shell", shlex.join(command))
        deadline = time.monotonic() + 165
        while time.monotonic() < deadline:
            raw = adb("exec-out", "content", "read", "--uri", "content://" + PACKAGE + ".native-tls-probe/report/" + run, check=False).stdout
            try:
                value = strict_json(raw)
            except (ValueError, UnicodeError):
                time.sleep(.25)
                continue
            require(value.get("runNonce") == run and value.get("sourceCommit") == source, "stale native report")
            if value.get("status") in ("observed", "failed"):
                (output / "native-report.json").write_bytes(raw)
                device = value
                break
            time.sleep(.25)
        require(device is not None, "native diagnostic did not terminate; timeout is not protocol rejection")
        verify_installed(device.get("buildIdentity", {}), identity)
        require(adb("shell", "pidof", PACKAGE + ":native_tls_probe").stdout.strip() == str(device["pid"]).encode(), "observed native process owner differs")
        # The server records are produced after each actual socket closes. No manufactured peer packets.
        for _ in range(20):
            host = server.snapshot()
            if len({row.get("trial") for row in host["records"]}) == 4:
                break
            time.sleep(.05)
        checked = validate_native_tls(device, host, run=run, source=source, tree=tree, leaf=certificates.leaf_sha)
    except Exception as error:
        errors.append(dict(stage="actual-native-and-wire", errorType=type(error).__name__, reason=str(error) if isinstance(error,ValueError) and str(error).startswith("Native TLS evidence: ") else "actual-native-or-wire-failed"))
    finally:
        try:
            adb("shell", "am", "force-stop", PACKAGE)
            require(not adb("shell", "pidof", PACKAGE + ":native_tls_probe", check=False).stdout.strip(), "native diagnostic process remained alive")
            cleanup["appStopped"] = True
            require(adb("shell", "pm", "clear", PACKAGE).stdout.strip() == b"Success", "integration test profile/proxy cleanup")
            cleanup["appDataCleared"] = True
        except Exception as error:
            errors.append(dict(stage="integration-app-cleanup", errorType=type(error).__name__))
        if reversed_port:
            try:
                adb("reverse", "--remove", "tcp:" + str(GUEST_PORT))
                cleanup["reverseRemoved"] = True
            except Exception as error:
                errors.append(dict(stage="reverse-cleanup", errorType=type(error).__name__))
        if server is not None:
            try:
                server.close()
            except Exception as error:
                errors.append(dict(stage="server-cleanup", errorType=type(error).__name__))
        if ca is not None:
            try:
                ca.remove()
                cleanup["caRemoved"] = True
            except Exception as error:
                errors.append(dict(stage="public-ca-cleanup", errorType=type(error).__name__))
        if certificates is not None:
            try:
                certificates.close()
                cleanup["privateMaterialRemoved"] = not certificates.directory.exists()
                host_tls["privateMaterialRemoved"] = cleanup["privateMaterialRemoved"]
            except Exception as error:
                errors.append(dict(stage="private-tls-cleanup", errorType=type(error).__name__))
        try:
            cleanup["shellUidRestored"] = adb("shell", "id", "-u").stdout.strip() == b"2000"
        except Exception as error:
            errors.append(dict(stage="shell-cleanup", errorType=type(error).__name__))
    stable = snapshot() == before
    passed = checked is not None and not errors and all(cleanup.values()) and stable
    result = dict(schema=1, kind="native-tls-probe-v1", status="passed" if passed else "failed", sourceCommit=source, sourceTree=tree,
                  runId=os.environ.get("GITHUB_RUN_ID"), runAttempt=os.environ.get("GITHUB_RUN_ATTEMPT"), runNonce=run,
                  expectedBuildIdentity=identity, nativeReport="native-report.json" if device else None,
                  nativeReportSha256=sha(output / "native-report.json") if device else None,
                  host=server.snapshot() if server else None, hostTls=host_tls, cleanup=cleanup, checked=checked, errors=errors,
                  sourceFiles=before, executionInputsUnchanged=stable, actualAndroidExecution=device is not None,
                  actualGeckoExecution=device is not None and device.get("actualGeckoExecution") is True,
                  diagnosticOnly=True, releaseQualification=False, beforePhase1Qualified=False,
                  standaloneSessionCapabilityOnly=True, fullTlsFingerprintEmulation=False, quicWireVerified=False,
                  scope="Standalone existing GeckoSession public native TLS min/max DEFAULT setting and exact DEFAULT/USER restoration, four fresh controlled TLS peers, actual ClientHello plus negotiated TLS/ALPN and protocol failure. Not production admission, per-environment UI, arbitrary TLS fingerprint imitation or QUIC proof.")
    (output / "results.json").write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps({key: result[key] for key in ("status", "sourceCommit", "actualAndroidExecution", "executionInputsUnchanged")}))
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
