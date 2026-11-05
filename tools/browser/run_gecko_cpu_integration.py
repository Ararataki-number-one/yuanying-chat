#!/usr/bin/env python3
"""Run the production CPU workload and preserve its original bounded report bytes."""
import argparse
import json
from pathlib import Path
import subprocess
import sys

ROOT=Path(__file__).resolve().parents[2]

def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--adb',default='adb');parser.add_argument('--serial',default='emulator-5554')
    parser.add_argument('--apk',type=Path,required=True);parser.add_argument('--source',required=True);parser.add_argument('--output',type=Path,required=True);args=parser.parse_args()
    output=args.output.absolute()
    if any(path.is_symlink() for path in (output,*output.parents)):raise ValueError('Ordinary evidence output required')
    output.mkdir(parents=True,exist_ok=True);destination=output/'gecko-cpu-results.json'
    if destination.exists():raise ValueError('Fresh CPU summary destination required')
    raw_directory=output/'gecko-cpu-evidence'
    command=[sys.executable,str(ROOT/'tools/gecko/run_gecko_cpu_acceptance.py'),'--adb',args.adb,'--serial',args.serial,
        '--apk',str(args.apk),'--source',args.source,'--output',str(raw_directory)]
    result=subprocess.run(command,cwd=ROOT)
    original=raw_directory/'results.json'
    if original.is_file() and not original.is_symlink() and original.stat().st_size<=4*1024*1024:destination.write_bytes(original.read_bytes())
    if result.returncode:return result.returncode
    if not destination.is_file():raise ValueError('Actual CPU workload summary absent')
    sys.path.insert(0,str(ROOT/'tools/gecko'))
    from cpu_acceptance_server import strict_json
    from check_gecko_cpu_evidence import verify_gecko_cpu_evidence
    value=strict_json(destination.read_bytes(),4*1024*1024)
    checked=verify_gecko_cpu_evidence(output,args.source,value['expectedBuildIdentity'])
    print(json.dumps(dict(status='passed',sourceCommit=args.source,caseCount=checked['caseCount'],actualAndroidExecution=True,actualGeckoExecution=True)))
    return 0

if __name__=='__main__':raise SystemExit(main())
