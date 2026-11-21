"""Run the self-target instrumentation fixture in a new loopback-only AVD."""
import argparse
import hashlib
import json
from pathlib import Path
import re
import subprocess
import time

PACKAGE = "local.pocketchat.aidiagnostics"
INSTRUMENTATION = "local.pocketchat.AiDiagnosticInstrumentation"
SERIAL = "emulator-5554"
REQUIRED = {
    "cancel_calls": "0",
    "valid_calls": "1",
    "valid_preview_match": "true",
    "valid_evidence_bound": "true",
    "invalid_calls": "1",
    "invalid_reply_rejected": "true",
    "denial_calls": "1",
    "http_denial_shown": "true",
    "internet_permission_denied": "true",
}
OPTIONAL = {
    "stale_calls": "0",
    "stale_confirmation_rejected": "true",
    "stop_waiting_cancelled": "true",
}


class Failed(RuntimeError):
    """Fixed diagnostic only, without raw process data."""


def receipt(output):
    values = {}
    codes = []
    for line in output.replace("\r", "").splitlines():
        match = re.fullmatch(r"INSTRUMENTATION_RESULT: ([a-z_]+)=(.*)", line)
        if match:
            key, value = match.groups()
            if key in values:
                raise Failed("duplicate-instrumentation-result")
            values[key] = value
        code = re.fullmatch(r"INSTRUMENTATION_CODE: (-?\d+)", line)
        if code:
            codes.append(code.group(1))
    if codes != ["-1"]:
        failure = values.get("failure", "")
        if re.fullmatch(r"[a-z0-9_]{1,40}", failure):
            raise Failed("instrumentation-" + failure)
        raise Failed("instrumentation-did-not-report-success")
    if any(values.get(key) != value for key, value in REQUIRED.items()):
        raise Failed("instrumentation-required-check-missing")
    if any(key in values and values[key] != value for key, value in OPTIONAL.items()):
        raise Failed("instrumentation-optional-check-failed")
    return {key: values[key] for key in REQUIRED | OPTIONAL if key in values}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--sdk", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    report = {
        "schema": 1,
        "kind": "ai-diagnostic-instrumentation-device",
        "status": "failed",
        "scope": {
            "originalApk": False,
            "realAndroidInstrumentation": False,
            "geckoRuntime": False,
            "productionNetworkRoute": False,
            "syntheticHttpsConnection": True,
            "deviceTrustChanged": False,
            "paidProviderCalls": 0,
        },
    }
    output = args.output / "instrumentation-results.json"
    adb_bin = args.sdk / "platform-tools" / "adb"

    def adb(*parts, timeout=30, host=False, check=True):
        command = [str(adb_bin)] + ([] if host else ["-s", SERIAL]) + list(parts)
        result = subprocess.run(command, capture_output=True, text=True, timeout=timeout)
        if check and result.returncode:
            raise Failed("adb-command-failed")
        return result.stdout.replace("\r", "")

    process = None
    started_adb = False
    stage = "namespace"
    try:
        links = subprocess.check_output(["ip", "-j", "link", "show"], text=True, timeout=5)
        if {row["ifname"] for row in json.loads(links)} != {"lo"}:
            raise Failed("loopback-only-namespace-required")
        report["scope"]["runnerNetworkInterfaces"] = ["lo"]

        stage = "fixture-identity"
        private = args.output / "private-build"
        apk = private / "instrumentation-test.apk"
        build = json.loads((private / "build-report.json").read_text(encoding="utf-8"))
        apk_sha = hashlib.sha256(apk.read_bytes()).hexdigest()
        if (build.get("package") != PACKAGE or build.get("instrumentation") != INSTRUMENTATION
                or build.get("targetPackage") != PACKAGE or build.get("internetPermission") is not False
                or build.get("testOnly") is not True or build.get("originalApk") is not False
                or build.get("apkSha256") != apk_sha):
            raise Failed("unexpected-fixture-identity")
        report["apkSha256"] = apk_sha

        stage = "boot"
        with (args.output / "emulator.private.log").open("wb") as log:
            adb("start-server", host=True)
            started_adb = True
            process = subprocess.Popen(
                [str(args.sdk / "emulator" / "emulator"), "-avd", "pocketchat-ai-instrumentation",
                 "-port", "5554", "-no-window", "-no-audio", "-no-snapshot", "-no-boot-anim",
                 "-no-metrics", "-accel", "on", "-gpu", "swangle", "-feature", "-Vulkan",
                 "-memory", "3072", "-cores", "2"],
                stdout=log, stderr=subprocess.STDOUT)
            deadline = time.monotonic() + 300
            while time.monotonic() < deadline:
                if process.poll() is not None:
                    raise Failed("emulator-exited-before-boot")
                try:
                    if adb("shell", "getprop", "sys.boot_completed", timeout=5, check=False).strip() == "1":
                        break
                except subprocess.TimeoutExpired:
                    pass
                time.sleep(2)
            else:
                raise Failed("emulator-boot-timeout")

            platform = {
                "abi": adb("shell", "getprop", "ro.product.cpu.abi").strip(),
                "api": adb("shell", "getprop", "ro.build.version.sdk").strip(),
                "qemu": (adb("shell", "getprop", "ro.kernel.qemu").strip()
                         or adb("shell", "getprop", "ro.boot.qemu").strip()),
            }
            if platform != {"abi": "x86_64", "api": "35", "qemu": "1"}:
                raise Failed("unexpected-emulator-platform")
            report["platform"] = platform
            adb("shell", "input", "keyevent", "82")

            stage = "install"
            if adb("shell", "pm", "path", PACKAGE, check=False).strip():
                raise Failed("diagnostics-package-already-installed")
            if "Success" not in adb("install", "-t", str(apk), timeout=90).splitlines():
                raise Failed("test-apk-installation-failed")
            paths = adb("shell", "pm", "path", PACKAGE).strip().splitlines()
            if len(paths) != 1 or not re.fullmatch(r"package:/data/app/[-A-Za-z0-9_+=~./]+/base\.apk", paths[0]):
                raise Failed("unexpected-installed-package-path")
            installed = adb("shell", "sha256sum", paths[0][len("package:"):], timeout=25).split()
            if not installed or installed[0] != apk_sha:
                raise Failed("installed-fixture-hash-mismatch")
            report["installedFixtureHashMatches"] = True

            stage = "instrumentation"
            native_output = adb("shell", "am", "instrument", "-w", "-r",
                                PACKAGE + "/" + INSTRUMENTATION, timeout=110, check=False)
            report["checks"] = receipt(native_output)
            report["scope"]["realAndroidInstrumentation"] = True
            report["status"] = "passed"
    except Failed as problem:
        report["failure"] = {"stage": stage, "code": str(problem)}
    except Exception as problem:
        report["failure"] = {"stage": stage, "code": type(problem).__name__}
    finally:
        if process is not None and process.poll() is None:
            try:
                adb("emu", "kill", timeout=10, check=False)
            except (OSError, subprocess.SubprocessError):
                pass
            if process.poll() is None:
                process.terminate()
                try:
                    process.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    process.kill()
        if started_adb:
            try:
                adb("kill-server", host=True, timeout=10, check=False)
            except (OSError, subprocess.SubprocessError):
                pass

    output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(report, sort_keys=True), flush=True)
    return 0 if report["status"] == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
