#!/usr/bin/env python3
"""Execute the complete pure-Java universal-browser address policy."""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import tempfile

ROOT=Path(__file__).resolve().parents[2]
HERE=Path(__file__).resolve().parent


def digest(path):return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--java-home',type=Path)
    parser.add_argument('--output',type=Path,default=ROOT/'work/ux-browser-address/results.json',help='JSON report file')
    args=parser.parse_args()
    def tool(name):
        selected=str(args.java_home/'bin'/name) if args.java_home else shutil.which(name)
        if not selected:parser.error('Provide --java-home containing '+name)
        return selected
    source=ROOT/'app/src/main/java/local/pocketchat/BrowserAddressPolicy.java'
    inputs=[source,HERE/'BrowserAddressHost.java',Path(__file__).resolve()]
    hashes={str(path.relative_to(ROOT)):digest(path) for path in inputs}
    with tempfile.TemporaryDirectory(prefix='browser-address-host-') as temporary:
        classes=Path(temporary)/'classes'
        compiled=subprocess.run([tool('javac'),'-encoding','UTF-8','-source','8','-target','8','-d',str(classes),str(source),str(HERE/'BrowserAddressHost.java')],text=True,capture_output=True)
        if compiled.returncode:raise RuntimeError(compiled.stderr)
        ran=subprocess.run([tool('java'),'-cp',str(classes),'local.pocketchat.BrowserAddressHost'],text=True,capture_output=True)
        if ran.returncode:raise RuntimeError(ran.stderr)
        report=json.loads(ran.stdout)
    unchanged=all(digest(path)==hashes[str(path.relative_to(ROOT))] for path in inputs)
    report.update(status='passed' if unchanged else 'source-changed',sourceCommit=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),sourceFiles=hashes,executionInputsUnchanged=unchanged,scope='Complete production BrowserAddressPolicy with JVM URI/IDN/literal-IP and URL encoding APIs. No Android WebView/redirect/network/DNS/browser-provider execution; input policy does not establish DNS rebinding protection.')
    args.output.parent.mkdir(parents=True,exist_ok=True);args.output.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps(dict(status=report['status'],passed=report['passed'],total=report['total'],actualAndroidExecution=False,output=str(args.output)),ensure_ascii=False))
    if report['status']!='passed':raise SystemExit(1)


if __name__=='__main__':main()
