#!/usr/bin/env python3
"""Execute new persistence fixtures only in local.pocketchat.test, with real adb reports."""
import argparse
import json
from pathlib import Path
import subprocess
import time

ROOT = Path(__file__).resolve().parents[2]
PACKAGE = "local.pocketchat.test"

def verify(report, minimum, require_total=False):
    if report.get("status") != "passed" or report.get("actualAndroidExecution") is not True or report.get("synthetic") is not True:
        raise ValueError("Fixture did not report successful actual synthetic Android execution")
    if type(report.get("passed")) is not int or report["passed"] < minimum or report.get("error") or report.get("failureType"):
        raise ValueError("Fixture assertions failed or were incomplete")
    if require_total:
        checks = report.get("checks")
        if not isinstance(checks, list) or len(checks) != report.get("total") or report["passed"] != len(checks) or any(item.get("pass") is not True for item in checks):
            raise ValueError("Catalog check list is incomplete")

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--adb", required=True)
    parser.add_argument("--serial", default="emulator-5554")
    parser.add_argument("--timeout", type=int, default=120)
    args = parser.parse_args()
    if args.timeout < 1 or args.timeout > 600:
        parser.error("Timeout must be 1..600 seconds")
    output = ROOT / "work/gecko-integration"
    output.mkdir(parents=True, exist_ok=True)
    source = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
    def adb(*parts, check=True):
        result = subprocess.run([args.adb, "-s", args.serial, *parts], check=check, text=True, capture_output=True, timeout=30)
        return result.stdout
    for activity, endpoint, minimum, complete in [
        ("EnvironmentSpecIntegrationActivity", "environment-spec", 20, False),
        ("ExitSubscriptionCatalogTestActivity", "exit-subscriptions", 20, True),
    ]:
        path = output / (endpoint + "-results.json")
        path.unlink(missing_ok=True)
        adb("shell", "am", "force-stop", PACKAGE)
        # Only the fixed synthetic package is cleared; no parameter accepts a user app.
        adb("shell", "pm", "clear", PACKAGE)
        adb("logcat", "-c")
        adb("shell", "am", "start", "-W", "-n", PACKAGE + "/local.pocketchat." + activity)
        deadline = time.monotonic() + args.timeout
        try:
            while time.monotonic() < deadline:
                raw = adb("exec-out", "content", "read", "--uri", "content://" + PACKAGE + ".evidence/" + endpoint, check=False)
                if raw.lstrip().startswith("{"):
                    report = json.loads(raw)
                    verify(report, minimum, complete)
                    report["sourceCommit"] = source
                    report["androidSdk"] = int(adb("shell", "getprop", "ro.build.version.sdk").strip())
                    report["executionScope"] = "Actual synthetic Android SQLite/Keystore/catalog execution; no real account or webpage identity claim"
                    path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
                    print(json.dumps({"fixture": activity, "passed": report["passed"], "sourceCommit": source}))
                    break
                time.sleep(1)
            else:
                raise TimeoutError("No complete Android report: " + activity)
        except Exception:
            (output / (endpoint + "-failure-log.txt")).write_text(adb("logcat", "-d", check=False))
            raise
        finally:
            adb("shell", "am", "force-stop", PACKAGE, check=False)

if __name__ == "__main__":
    main()
