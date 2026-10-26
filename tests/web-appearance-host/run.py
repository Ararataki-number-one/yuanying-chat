#!/usr/bin/env python3
"""Compile and execute production WebAppearanceSync; no Android/Gecko execution."""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import subprocess

ROOT=Path(__file__).resolve().parents[2]
parser=argparse.ArgumentParser()
parser.add_argument('--json-jar',required=True,type=Path)
parser.add_argument('--java-home',type=Path)
parser.add_argument('--output',type=Path,default=ROOT/'work/web-appearance-host')
args=parser.parse_args()
javac=str(args.java_home/'bin/javac') if args.java_home else shutil.which('javac')
java=str(args.java_home/'bin/java') if args.java_home else shutil.which('java')
if not javac or not java:raise SystemExit('Java compiler/runtime required')
out=args.output.resolve();out.mkdir(parents=True,exist_ok=True)
classes=out/'classes';classes.mkdir(exist_ok=True)
sources=[ROOT/'app/src/main/java/local/pocketchat/WebAppearanceSync.java',ROOT/'app/src/main/java/local/pocketchat/BrowserBridgeRequests.java',ROOT/'tests/web-appearance-host/WebAppearanceSyncHost.java']
compile_command=[javac,'-encoding','UTF-8','-cp',str(args.json_jar.resolve()),'-d',str(classes),*map(str,sources)]
compile_run=subprocess.run(compile_command,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True)
(out/'javac-stdout.txt').write_text(compile_run.stdout)
(out/'javac-stderr.txt').write_text(compile_run.stderr)
if compile_run.returncode:raise SystemExit(compile_run.stderr)
command=[java,'-cp',str(classes)+':'+str(args.json_jar.resolve()),'local.pocketchat.WebAppearanceSyncHost']
run=subprocess.run(command,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True)
(out/'stdout.txt').write_text(run.stdout);(out/'stderr.txt').write_text(run.stderr)
if run.returncode:raise SystemExit(run.stderr)
result=json.loads(run.stdout);assert result['status']=='passed' and all(row['passed'] is True for row in result['results'])
result.update(sourceFiles={str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest()for p in sources},jsonJarSha256=hashlib.sha256(args.json_jar.read_bytes()).hexdigest(),compileCommand=compile_command,executionCommand=command)
(out/'results.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
print(json.dumps({'status':result['status'],'checks':result['checks'],'actualAndroidExecution':False,'actualGeckoExecution':False,'results':str(out/'results.json')}))
