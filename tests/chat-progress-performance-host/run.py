#!/usr/bin/env python3
"""Compare actual candidate2 and current progress-card setter counts on the JVM."""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import tempfile

ROOT=Path(__file__).resolve().parents[2]
HERE=Path(__file__).resolve().parent
PRODUCTION=ROOT/'app/src/main/java/local/pocketchat'


def member(text,needle):
    start=text.index(needle);opened=text.index('{',start)
    depth=0;quote=None;escape=line=block=False;i=opened
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
    raise ValueError('Unclosed member: '+needle)


def digest(value):return hashlib.sha256(value).hexdigest()


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--java-home',type=Path)
    parser.add_argument('--json-jar',required=True,type=Path)
    parser.add_argument('--before-ref',default='5900426')
    parser.add_argument('--output',type=Path,default=ROOT/'work/ux-chat-progress-performance/results.json',help='JSON report file')
    args=parser.parse_args()
    def tool(name):
        selected=str(args.java_home/'bin'/name) if args.java_home else shutil.which(name)
        if not selected:parser.error('Provide --java-home containing '+name)
        return selected
    names=['ChatDownloadProgressUi.java','ChatDownloadProgress.java','DownloadTasks.java','Attachments.java','J.java']
    paths=[PRODUCTION/name for name in names]+[HERE/'ChatProgressPerformanceHost.java',Path(__file__).resolve()]
    hashes={str(path.relative_to(ROOT)):digest(path.read_bytes()) for path in paths}
    commit=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip()
    baseline_commit=subprocess.check_output(['git','rev-parse',args.before_ref+'^{commit}'],cwd=ROOT,text=True).strip()
    fixture=(HERE/'ChatProgressPerformanceHost.java').read_text()
    results={}
    for label,before in [('before',True),('after',False)]:
        selected={name:(subprocess.check_output(['git','show',baseline_commit+':app/src/main/java/local/pocketchat/'+name],cwd=ROOT).decode() if before else (PRODUCTION/name).read_text()) for name in names}
        needles=['ChatDownloadProgress current(','void visible(','void update(']
        methods={needle:member(selected['ChatDownloadProgressUi.java'],needle) for needle in needles}
        observer=[line.strip() for line in selected['ChatDownloadProgressUi.java'].splitlines() if line.strip().startswith('observer=new ContentObserver(')]
        if len(observer)!=1:raise ValueError('Expected actual observer initialization')
        helpers={'/* LABEL_METHOD */':member(selected['DownloadTasks.java'],'static String label('),'/* AMOUNT_METHOD */':member(selected['DownloadTasks.java'],'static String amount('),'/* SIZE_METHOD */':member(selected['Attachments.java'],'static String sizeLabel(')}
        generated=fixture.replace('/* PRODUCTION_METHODS */','\n'.join(methods.values())).replace('/* OBSERVER_INITIALIZATION */',observer[0])
        for marker,text in helpers.items():generated=generated.replace(marker,text)
        with tempfile.TemporaryDirectory(prefix='chat-progress-'+label+'-') as temporary:
            work=Path(temporary);java=work/'ChatProgressPerformanceHost.java';java.write_text(generated)
            projection=work/'ChatDownloadProgress.java';projection.write_text(selected['ChatDownloadProgress.java'])
            utility=work/'J.java';utility.write_text(selected['J.java'])
            looper=work/'android/os/Looper.java';looper.parent.mkdir(parents=True)
            looper.write_text('package android.os;public final class Looper {private static final Looper MAIN=new Looper(),WORKER=new Looper();public static boolean main=true;public static Looper myLooper(){return main?MAIN:WORKER;}public static Looper getMainLooper(){return MAIN;}}\n')
            classes=work/'classes'
            compiled=subprocess.run([tool('javac'),'-encoding','UTF-8','-source','8','-target','8','-cp',str(args.json_jar.resolve()),'-d',str(classes),str(java),str(projection),str(utility),str(looper)],text=True,capture_output=True)
            if compiled.returncode:raise RuntimeError(label+' compile failed:\n'+compiled.stderr)
            ran=subprocess.run([tool('java'),'-Dbaseline='+str(before).lower(),'-cp',str(classes)+':'+str(args.json_jar.resolve()),'local.pocketchat.ChatProgressPerformanceHost'],text=True,capture_output=True)
            if ran.returncode:raise RuntimeError(label+' workload failed:\n'+ran.stderr)
            result=json.loads(ran.stdout)
        result.update(selectedSourceSha256={name:digest(text.encode()) for name,text in selected.items()},
            extractedMethods={name:digest(text.encode()) for name,text in methods.items()},
            observerInitializationSha256=digest(observer[0].encode()),generatedHarnessSha256=digest(generated.encode()))
        results[label]=result
    unchanged=all(path.is_file() and digest(path.read_bytes())==hashes[str(path.relative_to(ROOT))] for path in paths)
    total=sum(result['passed'] for result in results.values())
    report=dict(status='passed' if unchanged else 'source-changed',passed=total,total=total,sourceCommit=commit,baselineCommit=baseline_commit,
        sourceFiles=hashes,executionInputsUnchanged=unchanged,jsonJarSha256=digest(args.json_jar.read_bytes()),before=results['before'],after=results['after'],
        actualAndroidExecution=False,actualGeckoExecution=False,actualDevicePerformanceMeasurement=False,
        scope='Verbatim candidate2/current ChatDownloadProgressUi current/visible/update methods and actual observer initialization, compiled with each revision complete ChatDownloadProgress/J plus extracted label/amount/sizeLabel helpers. Deterministic View/TextView/ProgressBar/Looper/handler/session/observer adapters count setter calls for identical workloads. The requestSessionUi bridge executes immediately in this card-only harness; actual frame merging is checked separately by frame_binding_run.py. No Android layout, frame timing, Gecko, device, SQLite or network measurement.')
    args.output.parent.mkdir(parents=True,exist_ok=True);args.output.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps(dict(status=report['status'],passed=total,unchangedNotifications=100,
        beforeTextWrites=results['before']['unchangedTextWrites'],afterTextWrites=results['after']['unchangedTextWrites'],
        beforeProgressWrites=results['before']['unchangedProgressWrites'],afterProgressWrites=results['after']['unchangedProgressWrites'],actualAndroidExecution=False,output=str(args.output)),ensure_ascii=False))
    if report['status']!='passed':raise SystemExit(1)


if __name__=='__main__':main()
