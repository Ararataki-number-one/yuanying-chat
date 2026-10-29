#!/usr/bin/env python3
"""Reproduce the bounded source-handoff checks. Never reports an APK or phone pass."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time
import urllib.request

ROOT = Path(__file__).resolve().parents[2]
BASE = "0445d5fba512a17186434e953950864bae1663e6"
DEPENDENCIES = {
    "json.jar": (
        "https://repo.maven.apache.org/maven2/org/json/json/20250517/json-20250517.jar",
        "3ea61b2a06e31edf1c91134fe9106b0ebb16628be169f3db75bc7a2b06b45796"),
    "android-json.jar": (
        "https://repo.maven.apache.org/maven2/com/vaadin/external/google/android-json/0.0.20131108.vaadin1/android-json-0.0.20131108.vaadin1.jar",
        "dfb7bae2f404cfe0b72b4d23944698cb716b7665171812a0a4d0f5926c0fac79"),
}


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def git(*args):
    try:
        return subprocess.check_output(["git", *args], cwd=ROOT, text=True, stderr=subprocess.DEVNULL).strip()
    except (OSError, subprocess.CalledProcessError):
        return None


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--java", default=os.environ.get("PROFILE_JAVA") or shutil.which("java"))
    parser.add_argument("--android-jar", type=Path, default=os.environ.get("PROFILE_ANDROID_JAR"))
    parser.add_argument("--prepare-dependencies", action="store_true", help="Download only the two SHA-pinned Maven JSON jars")
    parser.add_argument("--require-ui-compile", action="store_true")
    parser.add_argument("--output", type=Path, default=ROOT / "work/first-five-handoff/verification.json")
    args = parser.parse_args()
    if not args.java:
        parser.error("JDK 17 is required; pass --java /path/to/jdk-17/bin/java")
    directory = ROOT / "work/profile-host"
    directory.mkdir(parents=True, exist_ok=True)
    for name, (url, expected) in DEPENDENCIES.items():
        target = directory / name
        if target.is_file() and sha(target) == expected:
            continue
        if not args.prepare_dependencies:
            parser.error("Missing or mismatched pinned dependency " + str(target) + "; use --prepare-dependencies")
        with urllib.request.urlopen(url, timeout=30) as response:
            data = response.read(2 * 1024 * 1024 + 1)
        if len(data) > 2 * 1024 * 1024 or hashlib.sha256(data).hexdigest() != expected:
            raise RuntimeError("Dependency exceeded its limit or failed SHA-256: " + name)
        temporary = target.with_suffix(".download")
        temporary.write_bytes(data)
        temporary.replace(target)
    env = os.environ.copy()
    env["PROFILE_JAVA"] = str(args.java)
    env["PROFILE_JSON_JAR"] = str(directory / "json.jar")
    env["PROFILE_ANDROID_JSON_JAR"] = str(directory / "android-json.jar")
    stages = []
    tests = [
        "profile_environment_identity_status_test.py",
        "profile_mobile_identity_consistency_test.py",
        "profile_fingerprint_report_comparison_test.py",
        "profile_fingerprint_context_baseline_test.py",
        "profile_fingerprint_followup_progress_test.py",
        "profile_protection_template_assessment_test.py",
    ]
    for test in tests:
        stages.append((test, [sys.executable, str(ROOT / "tests" / test)], {}))
    stages.append(("mobile-identity-android-json", [sys.executable, str(ROOT / "tests/profile_mobile_identity_consistency_test.py")],
                   {"PROFILE_JSON_JAR": str(directory / "android-json.jar")}))
    stages.append(("existing-identity-controller", [sys.executable, str(ROOT / "tests/review-host/run_identity_controller_host.py"),
                   "--json-jar", str(directory / "json.jar"), "--output", str(ROOT / "work/first-five-handoff/controller.json")], {}))
    node = shutil.which("node")
    if not node:
        parser.error("Node.js is required for the existing protection handshake regression")
    stages.append(("existing-native-protection-handshake", [node, "tests/browser-runtime/native-protection-handshake.test.cjs"], {}))
    if args.android_jar:
        framework = args.android_jar.resolve()
        if not framework.is_file():
            parser.error("Android platform JAR not found: " + str(framework))
        stages.append(("real-android-api-ui-compile", [sys.executable, "tests/profile_first_five_ui_compile_test.py"],
                       {"PROFILE_ANDROID_JAR": str(framework), "FIRST_FIVE_UI_IDENTITY_ONLY": "0"}))
    elif args.require_ui_compile:
        parser.error("--require-ui-compile requires --android-jar")
    before = {str(path.relative_to(ROOT)): sha(path) for path in (ROOT / "app/src/main/java/local/pocketchat").glob("*.java")}
    records = []
    for name, command, overrides in stages:
        started = time.monotonic()
        try:
            run = subprocess.run(command, cwd=ROOT, env={**env, **overrides}, text=True, capture_output=True, timeout=180)
            record = {"name": name, "status": "passed" if run.returncode == 0 else "failed", "exitCode": run.returncode,
                      "stdout": run.stdout, "stderr": run.stderr, "elapsedSeconds": round(time.monotonic() - started, 3)}
        except subprocess.TimeoutExpired:
            record = {"name": name, "status": "failed", "reason": "timeout", "elapsedSeconds": round(time.monotonic() - started, 3)}
        records.append(record)
        print(name + ": " + record["status"], flush=True)
        if record["status"] != "passed":
            break
    unchanged = before == {str(path.relative_to(ROOT)): sha(path) for path in (ROOT / "app/src/main/java/local/pocketchat").glob("*.java")}
    passed = len(records) == len(stages) and all(item["status"] == "passed" for item in records) and unchanged
    report = {"schema": 1, "baseCommit": BASE, "sourceCommit": git("rev-parse", "HEAD"),
              "sourceTree": git("rev-parse", "HEAD^{tree}"), "sourceStatus": git("status", "--porcelain"),
              "status": "passed" if passed else "failed", "executedStages": len(records), "plannedStages": len(stages),
              "productionSourcesUnchangedDuringChecks": unchanged, "productionJavaSha256": before,
              "dependencySha256": {name: sha(directory / name) for name in DEPENDENCIES}, "stages": records,
              "androidApiUiCompilation": "executed" if args.android_jar else "not-run",
              "fullApplicationCompilation": False, "apkBuilt": False, "actualAndroidExecution": False,
              "actualGeckoExecution": False, "physicalPhoneAcceptance": False,
              "scope": "Source handoff checks only. Android framework compile uses declared app/Gecko doubles; no full APK, device, website or privacy-effectiveness acceptance."}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
