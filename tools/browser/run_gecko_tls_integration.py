#!/usr/bin/env python3
"""Formal >=2.1.4 wrapper, preserving the original eleven TLS workloads and independent twelfth combination bytes."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import stat
import sys
ROOT=Path(__file__).resolve().parents[2]

def require(value,message):
    if not value:raise ValueError('Formal TLS gate: '+message)
def read_regular(path,limit):
    require(not any(p.is_symlink() for p in (path,*path.parents)),'ordinary original summary required')
    with os.fdopen(os.open(path,os.O_RDONLY|os.O_NONBLOCK|os.O_NOFOLLOW),'rb') as stream:
        before=os.fstat(stream.fileno());require(stat.S_ISREG(before.st_mode) and 0<before.st_size<=limit,'bounded original TLS summary required');data=stream.read(limit+1);after=os.fstat(stream.fileno());named=os.stat(path,follow_symlinks=False)
    stamp=lambda v:(v.st_dev,v.st_ino,v.st_size,v.st_mtime_ns,v.st_ctime_ns)
    require(len(data)==before.st_size and stamp(before)==stamp(after)==stamp(named),'original summary changed while reading');return data

def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--adb',default='adb');parser.add_argument('--serial',required=True);parser.add_argument('--apk',required=True,type=Path);parser.add_argument('--source',required=True);parser.add_argument('--output',required=True,type=Path);args=parser.parse_args()
    gradle=(ROOT/'app/build.gradle').read_text();version=re.search(r"versionName '([0-9]+\.[0-9]+\.[0-9]+)'",gradle)
    require(version is not None and tuple(map(int,version[1].split('.'))) >= (2,1,4),'prototype213 is not a formal TLS release qualification')
    for name in ('tools/browser/check_gecko_ip_timezone_evidence.py','tools/browser/check_gecko_cpu_ip_combo_evidence.py','app/src/main/java/local/pocketchat/GeckoIpTimeZonePolicy.java'):
        require((ROOT/name).is_file(),'final IP/CPU/IP-combo source is not merged: '+name)
    out=args.output.absolute();require(not any(path.is_symlink() for path in (out,*out.parents)),'ordinary output required');out.mkdir(parents=True,exist_ok=True)
    summary=out/'gecko-tls-results.json';raw=out/'gecko-tls-evidence';require(not summary.exists() and not summary.is_symlink() and not raw.exists() and not raw.is_symlink(),'fresh formal TLS outputs required')
    command=[sys.executable,str(ROOT/'tools/gecko/run_gecko_tls_acceptance.py'),'--adb',args.adb,'--serial',args.serial,'--apk',str(args.apk),'--source',args.source,'--output',str(raw)]
    result=subprocess.run(command,cwd=ROOT)
    original=raw/'results.json'
    if original.is_file() and not original.is_symlink():
        data=read_regular(original,4194304)
        with os.fdopen(os.open(summary,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o644),'wb') as stream:stream.write(data)
    if result.returncode:return result.returncode
    require(summary.is_file(),'original successful TLS summary absent');value=json.loads(summary.read_bytes());sys.path.insert(0,str(ROOT/'tools'));sys.path.insert(0,str(ROOT/'tools/gecko'))
    from browser.check_gecko_tls_evidence import verify_gecko_tls_evidence
    checked=verify_gecko_tls_evidence(out,args.source,value['expectedBuildIdentity'])
    require(type(checked.get('caseCount')) is int and checked['caseCount']==12 and checked.get('coldCpuIpTlsCombinationMeasured') is True,'all original eleven and actual twelfth same-environment CPU/IP/TLS case required')
    print(json.dumps(dict(status='passed',sourceCommit=args.source,caseCount=checked['caseCount'],formalVersionRequirement='>=2.1.4',actualAndroidExecution=True,actualGeckoExecution=True,connectionScope=checked['connectionScope'])));return 0
if __name__=='__main__':raise SystemExit(main())
