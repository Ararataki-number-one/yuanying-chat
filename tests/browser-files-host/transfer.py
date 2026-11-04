#!/usr/bin/env python3
"""Execute the complete browser GET transfer with deterministic route/HTTP adapters."""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import tempfile

ROOT=Path(__file__).resolve().parents[2]
HERE=Path(__file__).resolve().parent


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--java-home',type=Path)
    parser.add_argument('--output',type=Path,default=ROOT/'work/browser-files-host/transfer.json')
    args=parser.parse_args()
    java=str(args.java_home/'bin/java') if args.java_home else shutil.which('java')
    javac=str(args.java_home/'bin/javac') if args.java_home else shutil.which('javac')
    files=[ROOT/'app/src/main/java/local/pocketchat/BrowserDownloadTransfer.java',HERE/'TransferCases.java',ROOT/'app/src/main/java/local/pocketchat/BrowserAddressPolicy.java',Path(__file__).resolve()]
    hashes={str(path.relative_to(ROOT)):hashlib.sha256(path.read_bytes()).hexdigest() for path in files}
    with tempfile.TemporaryDirectory(prefix='browser-transfer-host-') as directory:
        subprocess.run([javac,'-encoding','UTF-8','-d',directory,*map(str,files[:3])],check=True,cwd=ROOT)
        result=subprocess.run([java,'-cp',directory,'local.pocketchat.TransferCases'],check=True,capture_output=True,text=True,cwd=ROOT,timeout=30)
        payload=json.loads(result.stdout)
    if not all(hashlib.sha256(path.read_bytes()).hexdigest()==hashes[str(path.relative_to(ROOT))] for path in files):
        raise RuntimeError('Transfer inputs changed during checks')
    payload.update(sourceSha256=hashes,actualAndroidExecution=False,actualProxyExecution=False)
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(json.dumps(payload,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps(payload,ensure_ascii=False))


if __name__=='__main__':
    main()
