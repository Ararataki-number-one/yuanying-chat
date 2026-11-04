#!/usr/bin/env python3
"""Replay the ten-workflow host checks. Does not claim Android/device acceptance."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys

ROOT=Path(__file__).resolve().parents[1]

def main():
    p=argparse.ArgumentParser()
    p.add_argument('--java-home',required=True,type=Path)
    p.add_argument('--json-jar',required=True,type=Path)
    p.add_argument('--android-json-jar',type=Path)
    p.add_argument('--android-jar',type=Path)
    p.add_argument('--output',type=Path,default=ROOT/'work/ux-ten-rounds-validation')
    a=p.parse_args()
    a.java_home=a.java_home.resolve();a.json_jar=a.json_jar.resolve();a.output=a.output.resolve()
    a.output.mkdir(parents=True,exist_ok=True)
    env=dict(os.environ);env['PATH']=str(a.java_home/'bin')+os.pathsep+env.get('PATH','')
    java=['--java-home',str(a.java_home)]
    jobs=[('shell-policy',['tests/ux-shell-host/run.py',*java,'--output',str(a.output/'shell-classes')]),
          ('focus-integration',['tests/ux-shell-host/focus_run.py',*java,'--output',str(a.output/'focus.json')]),
          ('session-frame-performance',['tests/ux-shell-host/frame_binding_run.py',*java,'--output',str(a.output/'session-frame-performance.json')]),
          ('environment-refresh-performance',['tests/environment-performance-host/run.py',*java,'--output',str(a.output/'environment-refresh-performance.json')])]
    jars=[('jvm',a.json_jar)]
    if a.android_json_jar:jars.append(('android-json',a.android_json_jar.resolve()))
    for label,jar in jars:
        arg=['--json-jar',str(jar)]
        jobs.extend([
            ('environment-'+label,['tests/environment-workspace-host/run.py',*java,*arg,'--output',str(a.output/('environment-'+label)/'results.json')]),
            ('environment-presentation-'+label,['tests/environment-presentation-host/run.py',*java,*arg,'--output',str(a.output/('environment-presentation-'+label+'.json'))]),
            ('discovery-'+label,['tests/download-discovery-host/run.py',*java,*arg,'--output',str(a.output/('discovery-'+label))]),
            ('collection-share-'+label,['tests/download-discovery-host/share.py',*java,*arg,'--output',str(a.output/('collection-share-'+label))]),
            ('continuity-'+label,['tests/local-continuity-host/run.py',*java,*arg,'--output',str(a.output/('continuity-'+label+'.json'))]),
            ('chat-progress-performance-'+label,['tests/chat-progress-performance-host/run.py',*java,*arg,'--output',str(a.output/('chat-progress-performance-'+label+'.json'))]),
            ('download-ui-before-'+label,['tests/download-performance-host/ui.py',*java,*arg,'--before','--output',str(a.output/('download-ui-before-'+label))]),
            ('download-ui-after-'+label,['tests/download-performance-host/ui.py',*java,*arg,'--output',str(a.output/('download-ui-after-'+label))]),
            ('download-worker-before-'+label,['tests/download-performance-host/worker.py',*java,*arg,'--before','--output',str(a.output/('download-worker-before-'+label))]),
            ('download-worker-after-'+label,['tests/download-performance-host/worker.py',*java,*arg,'--output',str(a.output/('download-worker-after-'+label))])])
    jobs.extend([
        ('download-recovery',['tests/download46-host/run.py',*java,'--json-jar',str(a.json_jar),'--output',str(a.output/'download-recovery')]),
        ('chat-download-progress',['tests/chat-download-progress-host/run.py',*java,'--json-jar',str(a.json_jar),'--output',str(a.output/'chat-download-progress')]),
        ('page-recovery',['tests/page-recovery-host/run.py','--json-jar',str(a.json_jar)])])
    if a.android_jar:jobs.append(('android-api-compile',['tests/ux-native-compile/run.py',*java,'--android-jar',str(a.android_jar.resolve()),'--output',str(a.output/'native-compile')]))
    results=[]
    for name,command in jobs:
        run=subprocess.run([sys.executable,*command],cwd=ROOT,env=env,text=True,capture_output=True,timeout=180)
        (a.output/(name+'.stdout.txt')).write_text(run.stdout)
        (a.output/(name+'.stderr.txt')).write_text(run.stderr)
        result={'name':name,'status':'passed' if run.returncode==0 else 'failed','returncode':run.returncode,'command':[sys.executable,*command]}
        results.append(result);print(name+': '+result['status'],flush=True)
    sources=sorted((ROOT/'app/src/main/java/local/pocketchat').glob('*.java'))
    report={'status':'passed' if all(r['returncode']==0 for r in results) else 'failed','actualAndroidExecution':False,'fullApkBuild':False,'scope':'Production host behaviors and optional native API compile with declared app boundaries; no phone, real account, server or Android storage execution.','results':results,'productionSha256':{str(f.relative_to(ROOT)):hashlib.sha256(f.read_bytes()).hexdigest() for f in sources}}
    (a.output/'summary.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
    return 0 if report['status']=='passed' else 1

if __name__=='__main__':raise SystemExit(main())
