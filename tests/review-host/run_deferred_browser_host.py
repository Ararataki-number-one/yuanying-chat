#!/usr/bin/env python3
"""Run the production deferred browser coordinator with host doubles; preserve exact source-bound receipts."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess

ROOT=Path(__file__).resolve().parents[2]

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--json-jar',type=Path,required=True);parser.add_argument('--output',type=Path);args=parser.parse_args()
    if not args.json_jar.is_file():parser.error('JSON-java jar not found')
    java=os.environ.get('PROFILE_JAVA') or shutil.which('java')
    if not java:parser.error('JDK with jdk.compiler required')
    output=ROOT/'work/deferred-browser-host/classes';output.mkdir(parents=True,exist_ok=True)
    source=ROOT/'app/src/main/java/local/pocketchat'
    sources=[source/(name+'.java') for name in ['J','DeferredBrowserSettings']]+sorted((ROOT/'tests/review-host/deferred-browser').rglob('*.java'))
    inputs=sources+[Path(__file__).resolve()];before={str(path.relative_to(ROOT)):hashlib.sha256(path.read_bytes()).hexdigest() for path in inputs}
    commit=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip();tree=subprocess.check_output(['git','rev-parse','HEAD^{tree}'],cwd=ROOT,text=True).strip();status=subprocess.check_output(['git','status','--porcelain'],cwd=ROOT,text=True)
    subprocess.run([java,'-m','jdk.compiler/com.sun.tools.javac.Main','-source','8','-target','8','-encoding','UTF-8','-cp',str(args.json_jar.resolve()),'-d',str(output),*map(str,sources)],cwd=ROOT,check=True)
    run=subprocess.run([java,'-cp',str(output)+os.pathsep+str(args.json_jar.resolve()),'local.pocketchat.DeferredBrowserHostTest'],cwd=ROOT,text=True,capture_output=True)
    if run.returncode:print(run.stdout);print(run.stderr);raise subprocess.CalledProcessError(run.returncode,run.args)
    report=json.loads(run.stdout.strip())
    if report.get('status')!='passed' or report.get('actualAndroidExecution') is not False or report.get('passed')!=report.get('total') or len(report.get('checks',[]))!=report.get('passed') or any(check.get('pass') is not True for check in report['checks']):raise ValueError('Incomplete deferred browser host result')
    if subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip()!=commit or subprocess.check_output(['git','status','--porcelain'],cwd=ROOT,text=True)!=status or any(hashlib.sha256((ROOT/path).read_bytes()).hexdigest()!=digest for path,digest in before.items()):raise ValueError('Deferred browser host sources changed during execution')
    report.update(sourceCommit=commit,sourceTree=tree,sourceDirty=bool(status.strip()),sourceUnchangedDuringChecks=True,files=before)
    if args.output:args.output.parent.mkdir(parents=True,exist_ok=True);args.output.write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps({key:report[key] for key in ['status','passed','total','actualAndroidExecution','sourceCommit','scope']},ensure_ascii=False))

if __name__=='__main__':main()
