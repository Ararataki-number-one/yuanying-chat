#!/usr/bin/env python3
"""Offline host validation of the production anonymous evidence journal."""
import argparse, pathlib, subprocess, tempfile
p=argparse.ArgumentParser()
p.add_argument('--java-home',type=pathlib.Path,required=True)
p.add_argument('--json-jar',type=pathlib.Path,required=True)
p.add_argument('--wire-fixture',type=pathlib.Path)
a=p.parse_args()
root=pathlib.Path(__file__).resolve().parents[2]
with tempfile.TemporaryDirectory(prefix='ai-evidence-host-') as work:
    source=root/'app/src/main/java/local/pocketchat'
    subprocess.run([str(a.java_home/'bin/javac'),'-encoding','UTF-8','-cp',str(a.json_jar),'-d',work,
                    str(source/'J.java'),str(source/'AiDiagnosticEvidence.java'),str(pathlib.Path(__file__).with_name('AiDiagnosticEvidenceHostTest.java'))],check=True,timeout=60)
    subprocess.run([str(a.java_home/'bin/java'),'-cp',work+':'+str(a.json_jar),'local.pocketchat.AiDiagnosticEvidenceHostTest',*([str(a.wire_fixture)] if a.wire_fixture else [])],check=True,timeout=60)
