#!/usr/bin/env python3
"""Run dependency-free parser tests; output stays in a temporary directory."""
from pathlib import Path
import subprocess
import tempfile
ROOT = Path(__file__).resolve().parents[2]
with tempfile.TemporaryDirectory(prefix="pocketchat-exit-parser-") as output:
    subprocess.run(["javac", "-d", output, str(ROOT / "app/src/main/java/local/pocketchat/ExitSubscriptionParser.java"), str(ROOT / "app/src/main/java/local/pocketchat/ExitSubscriptionIdentity.java"), str(Path(__file__).with_name("ExitSubscriptionParserTest.java"))], check=True)
    subprocess.run(["java", "-cp", output, "local.pocketchat.ExitSubscriptionParserTest"], check=True)
