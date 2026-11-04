#!/usr/bin/env python3
"""Compare verbatim loading presentation methods using counted native adapters."""
import argparse
import hashlib
import json
from pathlib import Path
import re
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


def digest(data):return hashlib.sha256(data).hexdigest()


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--java-home',type=Path)
    parser.add_argument('--before-ref',default='1e3086a')
    parser.add_argument('--output',type=Path,default=ROOT/'work/ux-loading-performance/results.json',help='JSON report file')
    args=parser.parse_args()
    def tool(name):
        selected=str(args.java_home/'bin'/name) if args.java_home else shutil.which(name)
        if not selected:parser.error('Provide --java-home containing '+name)
        return selected
    names=['LoadingUi.java','PageLoadingWait.java','DesignUi.java','ResourcePressureController.java','MainActivity.java']
    inputs=[PRODUCTION/name for name in names]+[HERE/'LoadingPerformanceHost.java',Path(__file__).resolve()]
    hashes={str(path.relative_to(ROOT)):digest(path.read_bytes()) for path in inputs}
    commit=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip()
    baseline_commit=subprocess.check_output(['git','rev-parse',args.before_ref+'^{commit}'],cwd=ROOT,text=True).strip()
    fixture=(HERE/'LoadingPerformanceHost.java').read_text()
    results={}
    for label,before in [('before',True),('after',False)]:
        selected={name:(subprocess.check_output(['git','show',baseline_commit+':app/src/main/java/local/pocketchat/'+name],cwd=ROOT).decode() if before else (PRODUCTION/name).read_text()) for name in names}
        needles=['void fitActions(','void update(']
        if 'void showCover(' in selected['LoadingUi.java']:
            needles+=['static void text(','void hint(','void showCover(','void hideCover(']
        methods={name:member(selected['LoadingUi.java'],name) for name in needles}
        readable=member(selected['DesignUi.java'],'static void readable(')
        visibility=member(selected['MainActivity.java'],'static void chromeVisibility(')
        constant=re.search(r'^  static final String DEFERRED_MESSAGE=.*;$',selected['ResourcePressureController.java'],re.M)
        if constant is None:raise ValueError('Missing actual deferred-message constant')
        generated=fixture.replace('/* PRODUCTION_METHODS */','\n'.join(methods.values())).replace('/* READABLE_METHOD */',readable).replace('/* CHROME_VISIBILITY */',visibility).replace('/* DEFERRED_CONSTANT */',constant.group())
        with tempfile.TemporaryDirectory(prefix='loading-performance-'+label+'-') as temporary:
            work=Path(temporary);java=work/'LoadingPerformanceHost.java';java.write_text(generated)
            wait=work/'PageLoadingWait.java';wait.write_text(selected['PageLoadingWait.java'])
            adapters={
                'android/os/SystemClock.java':'package android.os;public final class SystemClock {public static long now;public static long elapsedRealtime(){return now;}}\n',
                'android/animation/ValueAnimator.java':'package android.animation;public final class ValueAnimator {public static boolean enabled=true;public static boolean areAnimatorsEnabled(){return enabled;}}\n',
                'android/content/res/Configuration.java':'package android.content.res;public final class Configuration {public static final int ORIENTATION_PORTRAIT=1,ORIENTATION_LANDSCAPE=2;public int orientation=ORIENTATION_PORTRAIT;}\n',
                'android/text/TextUtils.java':'package android.text;public final class TextUtils {public static boolean equals(CharSequence a,CharSequence b){return a==b||a!=null&&b!=null&&a.toString().contentEquals(b);}public static boolean isEmpty(CharSequence a){return a==null||a.length()==0;}}\n',
            }
            files=[java,wait]
            for name,text in adapters.items():
                adapter=work/name;adapter.parent.mkdir(parents=True,exist_ok=True);adapter.write_text(text);files.append(adapter)
            classes=work/'classes'
            compiled=subprocess.run([tool('javac'),'-encoding','UTF-8','-source','8','-target','8','-d',str(classes),*[str(path) for path in files]],text=True,capture_output=True)
            if compiled.returncode:raise RuntimeError(label+' compile failed:\n'+compiled.stderr)
            ran=subprocess.run([tool('java'),'-Dbaseline='+str(before).lower(),'-cp',str(classes),'local.pocketchat.LoadingPerformanceHost'],text=True,capture_output=True)
            if ran.returncode:raise RuntimeError(label+' workload failed:\n'+ran.stderr)
            result=json.loads(ran.stdout)
        result.update(selectedSourceSha256={name:digest(text.encode()) for name,text in selected.items()},
            extractedMethods={name:digest(text.encode()) for name,text in methods.items()},
            readableMethodSha256=digest(readable.encode()),chromeVisibilityMethodSha256=digest(visibility.encode()),
            deferredMessageSha256=digest(constant.group().encode()),generatedHarnessSha256=digest(generated.encode()))
        results[label]=result
    unchanged=all(path.is_file() and digest(path.read_bytes())==hashes[str(path.relative_to(ROOT))] for path in inputs)
    total=sum(value['passed'] for value in results.values())
    report=dict(status='passed' if unchanged else 'source-changed',passed=total,total=total,sourceCommit=commit,baselineCommit=baseline_commit,
        sourceFiles=hashes,executionInputsUnchanged=unchanged,before=results['before'],after=results['after'],
        actualAndroidExecution=False,actualGeckoExecution=False,actualDevicePerformanceMeasurement=False,
        scope='Verbatim baseline/current LoadingUi update and fitActions, current text/hint/showCover/hideCover helpers when present, full production PageLoadingWait, and extracted DesignUi.readable/MainActivity.chromeVisibility/deferred message. Explicit counted native View/TextView/Animator/orientation, session and clock adapters. Same100-update live/empty/deferred workloads,20second thresholds, orientation, error details, readable copy and fade callback races. No Android layout, system animator, IME, Gecko, network or device frame-time execution.')
    args.output.parent.mkdir(parents=True,exist_ok=True);args.output.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps(dict(status=report['status'],passed=total,total=total,
        textAssignments={name:{label:results[label]['workloads'][name]['textAssignments'] for label in ['before','after']} for name in ['live100','empty100','deferred100']},
        actualAndroidExecution=False,output=str(args.output)),ensure_ascii=False))
    if report['status']!='passed':raise SystemExit(1)


if __name__=='__main__':main()
