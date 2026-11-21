#!/usr/bin/env python3
"""Compile the production request-confirmation member with JVM-only collaborators."""
import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import subprocess
import tempfile


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--java-home", required=True, type=Path)
    args = parser.parse_args()

    here = Path(__file__).resolve().parent
    root = here.parents[1]
    source = root / "app/src/main/java/local/pocketchat/AiDiagnosticUi.java"
    template = here / "AttemptHost.java.in"
    extractor = root / "tests/gecko-navigation-host/run.py"
    inputs = (source, template, extractor, Path(__file__).resolve())
    before = {str(path.relative_to(root)): hashlib.sha256(path.read_bytes()).hexdigest() for path in inputs}

    spec = importlib.util.spec_from_file_location("attempt_member_extractor", extractor)
    java_members = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(java_members)
    raw = source.read_text(encoding="utf-8")
    attempt = java_members.member_at(raw, raw.index("private static final class Attempt {"))
    preview = java_members.member_at(raw, raw.index("private void preview() {"))
    if "attempt.confirmationText()" not in preview or "attempt.confirmationButton()" not in preview:
        raise AssertionError("The confirmation preview must use both production Attempt methods")

    with tempfile.TemporaryDirectory(prefix="pocketchat-ai-attempt-") as temporary:
        folder = Path(temporary)
        generated = folder / "AttemptHost.java"
        generated.write_text(template.read_text(encoding="utf-8").replace("/* ACTUAL_ATTEMPT */", attempt),
                             encoding="utf-8")
        subprocess.run([str(args.java_home / "bin/javac"), "--release", "17", "-encoding", "UTF-8",
                        "-d", temporary, str(generated)], check=True, timeout=30)
        report = subprocess.run([str(args.java_home / "bin/java"), "-cp", temporary,
                                 "local.pocketchat.AttemptHost"], check=True, stdout=subprocess.PIPE,
                                text=True, timeout=30)
    if any(hashlib.sha256((root / name).read_bytes()).hexdigest() != digest
           for name, digest in before.items()):
        raise RuntimeError("Host inputs changed during execution")
    print(json.dumps({
        "status": "passed",
        "checks": int(report.stdout),
        "sourceFiles": before,
        "previewBindingsChecked": True,
        "actualAndroidExecution": False,
        "actualNetworkExecution": False,
    }))


if __name__ == "__main__":
    main()
