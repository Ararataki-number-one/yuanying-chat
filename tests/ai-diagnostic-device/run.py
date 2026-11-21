#!/usr/bin/env python3
"""Boot a network-isolated Android emulator and accept the fixed CI APK."""
import argparse
import hashlib
import json
from pathlib import Path
import re
import subprocess
import time

PACKAGE = "local.pocketchat.aidiagnostics"
ACTIVITY = PACKAGE + "/local.pocketchat.BrandLaunchActivity"
APK_SHA = "75ff5f3f880770aa9b4bc3fe8badd0658701460d0bf6c5f6b9335e23837e2feb"
APK_COMMIT = "cca221ab11c7d05a21e998be7c27197937fbb23a"
SERIAL = "emulator-5554"


def checksum(path):
    digest = hashlib.sha256()
    with path.open("rb") as reader:
        for block in iter(lambda: reader.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def loopback_only():
    details = subprocess.check_output(["ip", "-j", "link", "show"], text=True, timeout=5)
    return {entry["ifname"] for entry in json.loads(details)} == {"lo"}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apk", type=Path, required=True)
    parser.add_argument("--sdk", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    adb_path = args.sdk / "platform-tools" / "adb"
    emulator = args.sdk / "emulator" / "emulator"
    report = {
        "sourceApk": {"run": 44910281335, "artifact": 14709646838, "commit": APK_COMMIT,
                      "expectedSha256": APK_SHA, "package": PACKAGE, "deviceAbi": "x86_64"},
        "scope": {"emulator": True, "physicalDevice": False, "thirdPartyAccess": False,
                  "paidProviderCalls": False, "deviceTrustChanged": False, "productionEgressVerified": False},
        "checks": {},
    }

    def record(name, status, detail=None):
        if status not in ("passed", "failed", "unverified"):
            raise ValueError("invalid status")
        report["checks"][name] = {"status": status}
        if detail is not None:
            report["checks"][name]["detail"] = detail
        suffix = f" ({json.dumps(detail, ensure_ascii=True)})" if status == "failed" and detail is not None else ""
        print(f"{name}: {status}{suffix}", flush=True)
        (args.output / "device-results.json").write_text(
            json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    def host_adb(*parts, timeout=30):
        run = subprocess.run([str(adb_path), *parts], capture_output=True, text=True, timeout=timeout)
        if run.returncode:
            raise RuntimeError("adb command failed")
        return run.stdout.replace("\r", "")

    def adb(*parts, timeout=30):
        return host_adb("-s", SERIAL, *parts, timeout=timeout)

    process = None
    adb_started = False
    scope = "original_apk"
    try:
        sha = checksum(args.apk)
        if sha != APK_SHA:
            raise RuntimeError("APK bytes differ from the fixed CI artifact")
        record(scope, "passed", {"sha256": sha, "bytes": args.apk.stat().st_size})

        scope = "namespace"
        if not loopback_only():
            raise RuntimeError("a loopback-only network namespace is required")
        record(scope, "passed", {"interfaces": ["lo"]})

        scope = "emulator_boot"
        with (args.output / "emulator.private.log").open("w", encoding="utf-8") as log:
            host_adb("start-server")
            adb_started = True
            process = subprocess.Popen(
                [str(emulator), "-avd", "pocketchat-ai", "-port", "5554", "-no-window",
                 "-no-audio", "-no-snapshot", "-no-boot-anim", "-no-metrics", "-accel", "on",
                 "-gpu", "swangle", "-feature", "-Vulkan", "-memory", "3072", "-cores", "2"],
                stdout=log, stderr=subprocess.STDOUT)
            deadline = time.monotonic() + 300
            while time.monotonic() < deadline:
                if process.poll() is not None:
                    raise RuntimeError("emulator process exited before boot")
                try:
                    if adb("shell", "getprop", "sys.boot_completed", timeout=5).strip() == "1":
                        break
                except (RuntimeError, subprocess.TimeoutExpired):
                    pass
                time.sleep(2)
            else:
                raise RuntimeError("emulator boot exceeded 300 seconds")
            guest_abi = adb("shell", "getprop", "ro.product.cpu.abi").strip()
            guest_api = adb("shell", "getprop", "ro.build.version.sdk").strip()
            qemu = adb("shell", "getprop", "ro.kernel.qemu").strip() or adb("shell", "getprop", "ro.boot.qemu").strip()
            if (guest_abi, guest_api, qemu) != ("x86_64", "35", "1"):
                raise RuntimeError("unexpected emulator identity")
            adb("shell", "input", "keyevent", "82")
            record(scope, "passed", {"abi": guest_abi, "api": int(guest_api), "qemu": True})

            scope = "install"
            if "Success" not in adb("install", str(args.apk), timeout=120).splitlines():
                raise RuntimeError("Android did not report installation success")
            package_paths = adb("shell", "pm", "path", PACKAGE).strip().splitlines()
            if len(package_paths) != 1 or not re.fullmatch(r"package:/data/app/[-A-Za-z0-9_+=~./]+/base\.apk", package_paths[0]):
                raise RuntimeError("expected one installed diagnostic base APK")
            record(scope, "passed", {"package": PACKAGE})
            installed_path = package_paths[0][len("package:"):]
            try:
                installed_sha = adb("shell", "sha256sum", installed_path, timeout=40).split()[0]
            except (RuntimeError, IndexError, subprocess.TimeoutExpired):
                record("installed_bytes", "unverified", "ADB shell could not read the installed APK")
            else:
                if installed_sha != APK_SHA:
                    scope = "installed_bytes"
                    raise RuntimeError("installed APK hash differs")
                record("installed_bytes", "passed", {"sha256": installed_sha})

            scope = "launcher"
            output = adb("shell", "am", "start", "-W", "-n", ACTIVITY, timeout=90)
            if "Status: ok" not in output or ACTIVITY not in output:
                raise RuntimeError("Android did not start the expected launcher")
            record(scope, "passed", {"component": ACTIVITY})

            scope = "fixtures"
            from fixture import serve
            from ui import exercise
            with serve() as fixture:
                try:
                    report["observed"] = exercise(adb, record, fixture)
                    print("UI observations:", json.dumps(report["observed"], sort_keys=True), flush=True)
                except Exception as error:
                    record("ui_driver", "unverified", type(error).__name__)
            report["fixture"] = fixture.summary()
            counts = report["fixture"]["counts"]
            print("Synthetic proxy counts:", json.dumps(counts, sort_keys=True), flush=True)
            if counts["geckoConnectAccepted"]:
                rejected = counts["tlsHandshakeFailed"] > 0 and counts["tlsHandshakeCompleted"] == 0
                record("fixture_tls_rejection", "passed" if rejected else "failed")
            if report["checks"].get("confirmation_cancel", {}).get("status") == "passed":
                record("cancel_no_gateway_connection", "passed" if counts["gatewayConnectAccepted"] == 0 else "failed")

    except RuntimeError as problem:
        record(scope, "failed", str(problem))
    except Exception as problem:
        record(scope, "failed", type(problem).__name__)
    finally:
        if process is not None:
            try:
                adb("emu", "kill", timeout=12)
            except (RuntimeError, subprocess.TimeoutExpired):
                pass
            if process.poll() is None:
                process.terminate()
                try:
                    process.wait(timeout=12)
                except subprocess.TimeoutExpired:
                    process.kill()
        if adb_started:
            try:
                host_adb("kill-server", timeout=10)
            except (RuntimeError, subprocess.TimeoutExpired):
                pass

    checks = report["checks"]
    required_ui = ("android_ui", "gecko_certificate_error", "redacted_preview", "confirmation_cancel",
                   "fixture_tls_rejection", "cancel_no_gateway_connection")
    for key in (*required_ui, "trusted_gateway", "production_network_path", "physical_arm64"):
        checks.setdefault(key, {"status": "unverified"})
    core_passed = all(
        checks.get(k, {}).get("status") == "passed"
        for k in ("original_apk", "namespace", "emulator_boot", "install", "launcher")
    ) and checks.get("installed_bytes", {}).get("status") != "failed"
    ui_passed = all(checks[key]["status"] == "passed" for key in required_ui)
    report["result"] = "passed" if core_passed and ui_passed else "partial" if core_passed else "core_failed"
    (args.output / "device-results.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print("Device acceptance result:", report["result"], flush=True)
    return 0 if report["result"] == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
