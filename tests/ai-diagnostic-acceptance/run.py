#!/usr/bin/env python3
"""One-command offline + numeric-loopback acceptance; never invokes paid providers."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent
HISTORY_METHODS = ["test_old_commit_gap_and_individual_protections_are_observed",
                   "test_exact_inverse_preserves_original_reading_guard"]


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def manifest():
    # Explicit non-secret source/test scope. Each legacy host also records its
    # own more detailed inputs; this does not claim to hash the entire project.
    inputs = set((ROOT / "prototype/ai-diagnostics").glob("*.py"))
    inputs.update((ROOT / "prototype/ai-diagnostics/fixtures").glob("*.json"))
    inputs.update((ROOT / "app/src/main/java/local/pocketchat").glob("AiDiagnostic*.java"))
    for filename in ("GeckoWebView.java", "GeckoAddressUi.java", "MainActivity.java", "ChatSession.java",
                     "BrowserBridgeRequests.java", "BrowserNetworkGuard.java", "NativeNetwork.java", "AppUpdates.java"):
        inputs.add(ROOT / "app/src/main/java/local/pocketchat" / filename)
    for folder in (HERE, ROOT / "tests/ai-diagnostic-attempt-host", ROOT / "tests/ai-diagnostic-route-host",
                   ROOT / "tests/ai-diagnostic-evidence-host", ROOT / "tests/ai-diagnostic-gateway-host",
                   ROOT / "tests/native-tls-callback-host", ROOT / "tests/gecko-tls-host",
                   ROOT / "tests/tls-fixture-update-cause-host",
                   ROOT / "tests/page-bridge-lifecycle-host", ROOT / "tests/gecko-window-selection-host"):
        inputs.update(path for path in folder.glob("*") if path.is_file() and path.suffix in (".py", ".java", ".in"))
    for filename in ("profile_page_bridge_lifecycle_test.py", "profile_gecko_window_selection_test.py"):
        inputs.add(ROOT / "tests" / filename)
    return {str(path.relative_to(ROOT)): digest(path) for path in sorted(inputs) if path.is_file()}


def stop(process):
    if process.poll() is not None:
        return
    try:
        os.killpg(process.pid, signal.SIGTERM)
        process.wait(timeout=3)
    except (ProcessLookupError, subprocess.TimeoutExpired):
        try:
            os.killpg(process.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
        process.wait(timeout=3)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--java-home", type=Path, required=True)
    parser.add_argument("--json-jar", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True, help="A new directory; existing results are never overwritten")
    parser.add_argument("--history", choices=("current", "full"), default="current",
                        help="current runs current-source checks; full additionally requires two immutable historical proofs")
    parser.add_argument("--history-object-dir", type=Path, help="Existing local Git objects directory; never fetched")
    parser.add_argument("--extended-jvm", action="store_true", help="Also run Gecko addon and UI retirement hosts")
    args = parser.parse_args()
    java_home, jar, output = args.java_home.resolve(), args.json_jar.resolve(), args.output_dir.resolve()
    java, javac = java_home / "bin/java", java_home / "bin/javac"
    for path in (java, javac, jar):
        if not path.is_file():
            parser.error("Missing explicit local dependency: " + str(path))
    if output.exists():
        parser.error("--output-dir must be new; choose a different directory")
    alternate = None
    if args.history_object_dir is not None:
        alternate = args.history_object_dir.resolve()
        if not alternate.is_dir() or any(char in str(alternate) for char in (":", "\r", "\n")):
            parser.error("--history-object-dir must be a single existing local objects directory")
    output.mkdir(parents=True, exist_ok=False)
    # No inherited API credentials, proxy settings, Python hooks or Git fetch auth.
    environment = {"PATH": os.defpath, "LANG": "C.UTF-8", "LC_ALL": "C.UTF-8",
                   "PYTHONDONTWRITEBYTECODE": "1", "JAVA_HOME": str(java_home),
                   "PROFILE_JAVA": str(java), "PROFILE_JSON_JAR": str(jar),
                   "GIT_NO_LAZY_FETCH": "1", "GIT_TERMINAL_PROMPT": "0", "GIT_OPTIONAL_LOCKS": "0",
                   "GIT_CONFIG_NOSYSTEM": "1", "GIT_CONFIG_GLOBAL": os.devnull, "GIT_ALLOW_PROTOCOL": "file",
                   "PAGE_BRIDGE_LIFECYCLE_REPORT": str(output / "page-bridge-current.json"),
                   "PAGE_BRIDGE_LIFECYCLE_NEGATIVE_REPORT": str(output / "page-bridge-history.json"),
                   "GECKO_WINDOW_SELECTION_REPORT": str(output / "window-selection.json")}
    if alternate is not None:
        environment["GIT_ALTERNATE_OBJECT_DIRECTORIES"] = str(alternate)
    source = subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT, env=environment,
                            text=True, capture_output=True, timeout=10)
    before = manifest()
    report = {"schema": 1, "status": "running", "sourceCommit": source.stdout.strip() if source.returncode == 0 else None,
              "historyMode": args.history, "historyObjectDirectory": str(alternate) if alternate else None,
              "historyTestsNotRun": HISTORY_METHODS if args.history == "current" else [],
              "extendedJvmSelected": args.extended_jvm,
              "dependencies": {"java": str(java), "javaSha256": digest(java), "javacSha256": digest(javac),
                               "jsonJar": str(jar), "jsonJarSha256": digest(jar)},
              "sourceFiles": before, "stages": [], "actualProviderRequestsSent": False,
              "actualAndroidExecution": False, "actualGeckoExecution": False,
              "deviceRouteAcceptance": False, "productionDeploymentAcceptance": False,
              "scope": "Synthetic Python/JVM checks; HTTP cross-wire uses provider HTTPS doubles. "
                       "Real local TLS is a separately named stage. No paid provider, APK or phone claim."}
    report_path = output / "report.json"
    def save():
        report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    save()

    def stage(name, command, scope, timeout=180, dependency=None):
        row = {"name": name, "scope": scope, "command": list(map(str, command)), "status": "running",
               "stdout": name + ".stdout.log", "stderr": name + ".stderr.log"}
        report["stages"].append(row)
        if dependency is not None and dependency["status"] != "passed":
            row.update(status="blocked", reason="required stage failed")
            save()
            return row
        print("RUN " + name + " — " + scope, flush=True)
        started = time.monotonic()
        with (output / row["stdout"]).open("wb") as stdout, (output / row["stderr"]).open("wb") as stderr:
            process = subprocess.Popen(list(map(str, command)), cwd=ROOT, env=environment,
                                       stdout=stdout, stderr=stderr, start_new_session=True)
            try:
                process.wait(timeout=timeout)
                row.update(returncode=process.returncode, status="passed" if process.returncode == 0 else "failed")
            except subprocess.TimeoutExpired:
                stop(process)
                row.update(status="failed", reason="stage timeout", returncode=process.returncode)
            except BaseException:
                stop(process)
                row.update(status="interrupted", returncode=process.returncode)
                raise
            finally:
                row["elapsedSeconds"] = round(time.monotonic() - started, 3)
                save()
        print(row["status"].upper() + " " + name + " (" + str(row["elapsedSeconds"]) + "s)", flush=True)
        return row

    python = [sys.executable, "-B"]
    worker = python + [HERE / "offline_stage.py"]
    java_args = ["--java-home", java_home, "--json-jar", jar]
    try:
        stage("python-offline", worker + ["python"], "Five explicit Python modules; provider sockets replaced; no real TLS")
        evidence = stage("java-evidence", python + [ROOT / "tests/ai-diagnostic-evidence-host/run.py", *java_args,
            "--wire-fixture", output / "java-wire.json"], "Production Java Journal with synthetic callbacks")
        stage("java-route", python + [ROOT / "tests/ai-diagnostic-route-host/run.py"],
              "Android Network/connection doubles; no sockets")
        stage("java-http-parser", python + [ROOT / "tests/ai-diagnostic-gateway-host/run.py", *java_args],
              "Production Android HTTP and JSON parser classes with JVM doubles")
        stage("java-fresh-id", python + [ROOT / "tests/ai-diagnostic-attempt-host/run.py", "--java-home", java_home],
              "Production confirmation/request-ID members; JVM only")
        stage("java-native-tls-callback", python + [ROOT / "tests/native-tls-callback-host/run.py", *java_args,
            "--output", output / "native-tls-callback.json"], "Native TLS callback attribution host; no handshake or Gecko", timeout=240)
        stage("java-tls-state", python + [ROOT / "tests/gecko-tls-host/run.py", *java_args,
            "--output", output / "tls-state.json"], "Gecko TLS desired-state store; JVM and temporary files, no TLS handshake")
        stage("java-tls-update-cause", python + [ROOT / "tests/tls-fixture-update-cause-host/run.py",
            "--java-home", java_home, "--output", output / "tls-update-cause.json"],
            "AppUpdates fixture lifecycle cause controls; 14 direct plus 42 nested expected, no observed device cause", timeout=240)
        stage("page-bridge", worker + ["page-bridge", "--history", args.history],
              "Current bridge checks" + (" and required immutable history proofs" if args.history == "full" else "; two history proofs explicitly not selected"),
              timeout=300)
        stage("window-selection", worker + ["window-selection"], "Current production window ownership methods with JVM doubles")
        stage("http-cross-wire", worker + ["cross-wire", "--fixture", output / "java-wire.json",
            "--output-dir", output / "http-cross-wire", *java_args],
            "Two in-memory HTTPS providers → real numeric-loopback HTTP gateway/SQLite → Java parser", dependency=evidence)
        stage("https-loopback", python + [ROOT / "prototype/ai-diagnostics/test_acceptance_https_gateway.py",
            "--report", output / "https-loopback.json"],
            "Actual TLS on numeric loopback with ephemeral test certificates; no provider", timeout=180)
        if args.extended_jvm:
            for name, folder in (("java-addon", "gecko-addon-lifecycle-host"), ("java-ui-retirement", "gecko-ui-host-lifecycle")):
                stage(name, python + [ROOT / "tests" / folder / "run.py", *java_args,
                    "--output", output / (name + ".json")], "Extended current-source JVM host with explicit collaborators", timeout=300)
    except KeyboardInterrupt:
        report["interrupted"] = True
    finally:
        after = manifest()
        report["declaredInputsUnchanged"] = before == after
        report["changedDeclaredInputs"] = sorted(key for key in set(before) | set(after) if before.get(key) != after.get(key))
        report["status"] = "passed" if (not report.get("interrupted") and before == after
                                          and all(row["status"] == "passed" for row in report["stages"])) else "failed"
        save()
    print(json.dumps({"status": report["status"], "stages": len(report["stages"]),
                      "historyMode": args.history, "report": str(report_path),
                      "actualProviderRequestsSent": False, "actualAndroidExecution": False}), flush=True)
    return 0 if report["status"] == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
