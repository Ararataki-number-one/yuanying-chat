#!/usr/bin/env python3
"""Run actual identity controller against deterministic host dependency doubles."""
import argparse
import os
from pathlib import Path
import shutil
import subprocess

ROOT = Path(__file__).resolve().parents[2]

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--json-jar", type=Path, required=True)
    args = parser.parse_args()
    if not args.json_jar.is_file():
        parser.error("JSON-java jar not found")
    java = os.environ.get("PROFILE_JAVA") or shutil.which("java")
    if not java:
        parser.error("JDK with jdk.compiler required")
    output = ROOT / "work/identity-controller-host/classes"
    output.mkdir(parents=True, exist_ok=True)
    source = ROOT / "app/src/main/java/local/pocketchat"
    sources = [source / (name + ".java") for name in
               ("J", "EnvironmentSpec", "BrowserIdentitySpec", "NetworkHealthPolicy", "IdentityTemplateController")]
    sources += sorted((ROOT / "tests/review-host/identity-controller").rglob("*.java"))
    subprocess.run([java, "-m", "jdk.compiler/com.sun.tools.javac.Main", "-source", "8", "-target", "8",
                    "-encoding", "UTF-8", "-cp", str(args.json_jar.resolve()), "-d", str(output),
                    *map(str, sources)], cwd=ROOT, check=True)
    subprocess.run([java, "-cp", str(output) + os.pathsep + str(args.json_jar.resolve()),
                    "local.pocketchat.IdentityControllerHostTest"], cwd=ROOT, check=True)

if __name__ == "__main__":
    main()
