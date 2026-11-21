#!/usr/bin/env python3
"""Compile and exercise the production diagnostics HTTP client against JVM doubles."""
import argparse
import pathlib
import subprocess
import tempfile

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("--json-jar", required=True, type=pathlib.Path)
parser.add_argument("--java-home", type=pathlib.Path)
parser.add_argument("--wire-case", nargs=2, metavar=("CONFIRMED_REQUEST", "GATEWAY_REPLY"))
args = parser.parse_args()
here = pathlib.Path(__file__).resolve().parent
sources = here.parents[1] / "app/src/main/java/local/pocketchat"
jar = args.json_jar.resolve()
java = str(args.java_home / "bin/java") if args.java_home else "java"
javac = str(args.java_home / "bin/javac") if args.java_home else "javac"
with tempfile.TemporaryDirectory(prefix="pocketchat-ai-http-") as classes:
    subprocess.run(
        [javac, "-encoding", "UTF-8", "-cp", str(jar), "-d", classes,
         str(sources / "AiDiagnosticGateway.java"), str(sources / "AiDiagnosticReply.java"),
         str(sources / "AiDiagnosticJson.java"), str(sources / "J.java"),
         str(here / "GatewayHost.java")],
        check=True, timeout=30,
    )
    subprocess.run(
        [java, "-cp", classes + ":" + str(jar), "local.pocketchat.GatewayHost", *(args.wire_case or ())],
        check=True, timeout=30,
    )
