#!/usr/bin/env python3
"""Run production model/parser policies on the JVM; never labels them Android evidence."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[2]

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--json-jar", type=Path, default=os.environ.get("PROFILE_JSON_JAR"))
    args = parser.parse_args()
    if args.json_jar is None or not Path(args.json_jar).is_file():
        parser.error("--json-jar must name a JSON-java jar for JVM model tests (not a production dependency)")
    json_jar = Path(args.json_jar).resolve()
    java = os.environ.get("PROFILE_JAVA") or shutil.which("java")
    if not java:
        parser.error("JDK 17+ with jdk.compiler is required")
    output = ROOT / "work/profile-host"
    classes = output / "classes"
    classes.mkdir(parents=True, exist_ok=True)
    source = ROOT / "app/src/main/java/local/pocketchat"
    tests = ROOT / "tests/browser-runtime"
    groups = [
        ("NetworkHealthPolicyTest", ["NetworkHealthPolicy"]),
        ("NetworkStatusPolicyTest", ["NetworkStatusPolicy"]),
        ("NetworkPoolIdentityTest", ["NetworkPoolIdentity"]),
        ("LatencyProbePolicyTest", ["LatencyProbePolicy"]),
        ("EnvironmentSpecTest", ["J", "EnvironmentSpec", "EnvironmentSpecMigration"]),
    ]
    extras = [("BrowserIdentitySpecTest", ["J", "BrowserIdentitySpec"])]
    groups += [(name, names) for name, names in extras if (tests / (name + ".java")).is_file()]
    files = {source / (name + ".java") for _, names in groups for name in names}
    files.update(tests / (name + ".java") for name, _ in groups)
    files.update([source / "ExitSubscriptionParser.java", source / "ExitSubscriptionIdentity.java",
                  ROOT / "tests/exit-subscriptions/ExitSubscriptionParserTest.java"])
    compiler = [java, "-m", "jdk.compiler/com.sun.tools.javac.Main", "-encoding", "UTF-8",
                "-source", "8", "-target", "8", "-classpath", str(json_jar), "-d", str(classes)]
    subprocess.run(compiler + [str(path) for path in sorted(files)], cwd=ROOT, check=True)
    results = []
    for name, _ in groups + [("ExitSubscriptionParserTest", [])]:
        command = [java, "-cp", str(classes) + os.pathsep + str(json_jar), "local.pocketchat." + name]
        run = subprocess.run(command, cwd=ROOT, text=True, capture_output=True)
        results.append({"test": name, "exitCode": run.returncode, "output": run.stdout.strip()})
        print(run.stdout.strip())
        if run.returncode:
            print(run.stderr, file=sys.stderr)
            raise subprocess.CalledProcessError(run.returncode, command)
    subprocess.run(["node", "tests/browser-runtime/session-cookies.test.cjs"], cwd=ROOT, check=True)
    bridge = ROOT / "tests/review-host/audit-bridge.test.cjs"
    if bridge.is_file():
        subprocess.run(["node", "--test", str(bridge)], cwd=ROOT, check=True)
    report = {"schema": 1, "status": "passed", "actualAndroidExecution": False,
              "scope": "JVM production model/parser/decision tests and Node protocol fixtures only",
              "jsonJarSha256": hashlib.sha256(json_jar.read_bytes()).hexdigest(),
              "results": results,
              "files": {str(path.relative_to(ROOT)): hashlib.sha256(path.read_bytes()).hexdigest() for path in sorted(files)}}
    (output / "results.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
    print("Host report: work/profile-host/results.json; Android, SDK build, ARM and real login remain separate.")

if __name__ == "__main__":
    main()
