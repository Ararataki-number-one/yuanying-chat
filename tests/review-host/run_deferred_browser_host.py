#!/usr/bin/env python3
"""Run the production deferred browser coordinator with host doubles; preserve exact source-bound receipts."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile

ROOT=Path(__file__).resolve().parents[2]

def production_member(text,needle):
    """Copy a complete Java member verbatim, including strings and comments."""
    if text.count(needle)!=1:raise ValueError('Expected one production member: '+needle)
    start=text.index(needle);opened=text.index('{',start);depth=0;quote=None;escape=False;line=False;block=False;i=opened
    while i<len(text):
        c=text[i];pair=text[i:i+2]
        if line:
            if c=='\n':line=False
        elif block:
            if pair=='*/':block=False;i+=1
        elif quote:
            if escape:escape=False
            elif c=='\\':escape=True
            elif c==quote:quote=None
        elif pair=='//':line=True;i+=1
        elif pair=='/*':block=True;i+=1
        elif c in ('"',"'"):quote=c
        elif c=='{':depth+=1
        elif c=='}':
            depth-=1
            if depth==0:return text[start:i+1]
        i+=1
    raise ValueError('Unclosed production member: '+needle)

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--json-jar',type=Path,required=True);parser.add_argument('--output',type=Path);args=parser.parse_args()
    if not args.json_jar.is_file():parser.error('JSON-java jar not found')
    java=os.environ.get('PROFILE_JAVA') or shutil.which('java')
    if not java:parser.error('JDK with jdk.compiler required')
    output=ROOT/'work/deferred-browser-host/classes'
    if output.exists():shutil.rmtree(output)
    output.mkdir(parents=True,exist_ok=True)
    if args.output:args.output.unlink(missing_ok=True)
    source=ROOT/'app/src/main/java/local/pocketchat'
    sources=[source/(name+'.java') for name in ['J','DeferredBrowserSettings']]+sorted((ROOT/'tests/review-host/deferred-browser').rglob('*.java'))
    page_memory=source/'PageMemory.java'
    inputs=sources+[page_memory,Path(__file__).resolve()];before={str(path.relative_to(ROOT)):hashlib.sha256(path.read_bytes()).hexdigest() for path in inputs}
    commit=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip();tree=subprocess.check_output(['git','rev-parse','HEAD^{tree}'],cwd=ROOT,text=True).strip();status=subprocess.check_output(['git','status','--porcelain'],cwd=ROOT,text=True)
    with tempfile.TemporaryDirectory(prefix='deferred-page-memory-') as generated:
        adapter=Path(generated)/'PageMemory.java'
        adapter.write_text('package local.pocketchat;\nimport org.json.JSONObject;\nfinal class PageMemory {\n'+production_member(page_memory.read_text(),'static boolean completeDraft(')+'\n'+production_member(page_memory.read_text(),'static boolean hasDraft(')+'\n}\n')
        subprocess.run([java,'-m','jdk.compiler/com.sun.tools.javac.Main','-source','8','-target','8','-encoding','UTF-8','-cp',str(args.json_jar.resolve()),'-d',str(output),*map(str,sources),str(adapter)],cwd=ROOT,check=True)
    run=subprocess.run([java,'-cp',str(output)+os.pathsep+str(args.json_jar.resolve()),'local.pocketchat.DeferredBrowserHostTest'],cwd=ROOT,text=True,capture_output=True)
    if run.returncode:print(run.stdout);print(run.stderr);raise subprocess.CalledProcessError(run.returncode,run.args)
    report=json.loads(run.stdout.strip())
    if report.get('status')!='passed' or report.get('actualAndroidExecution') is not False or report.get('passed')!=report.get('total') or len(report.get('checks',[]))!=report.get('passed') or any(check.get('pass') is not True for check in report['checks']):raise ValueError('Incomplete deferred browser host result')
    if subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip()!=commit or subprocess.check_output(['git','status','--porcelain'],cwd=ROOT,text=True)!=status or any(hashlib.sha256((ROOT/path).read_bytes()).hexdigest()!=digest for path,digest in before.items()):raise ValueError('Deferred browser host sources changed during execution')
    report.update(sourceCommit=commit,sourceTree=tree,sourceDirty=bool(status.strip()),sourceUnchangedDuringChecks=True,files=before,
        productionMembers=['PageMemory.java:static boolean completeDraft(','PageMemory.java:static boolean hasDraft('],jsonJarSha256=hashlib.sha256(args.json_jar.read_bytes()).hexdigest())
    if args.output:args.output.parent.mkdir(parents=True,exist_ok=True);args.output.write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps({key:report[key] for key in ['status','passed','total','actualAndroidExecution','sourceCommit','scope']},ensure_ascii=False))

if __name__=='__main__':main()
