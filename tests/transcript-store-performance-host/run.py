#!/usr/bin/env python3
"""Compare complete baseline/current transcript stores on their real JVM workers."""
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
    parser.add_argument('--before-ref',default='f43adac')
    parser.add_argument('--output',type=Path,default=ROOT/'work/ux-transcript-store-performance/results.json',help='JSON report file')
    args=parser.parse_args()
    def tool(name):
        selected=str(args.java_home/'bin'/name) if args.java_home else shutil.which(name)
        if not selected:parser.error('Provide --java-home containing '+name)
        return selected
    names=['WebTranscriptStore.java','MainActivity.java','J.java']
    paths=[PRODUCTION/name for name in names]+[HERE/'TranscriptStorePerformanceHost.java',Path(__file__).resolve()]
    hashes={str(path.relative_to(ROOT)):digest(path.read_bytes()) for path in paths}
    commit=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip()
    baseline_commit=subprocess.check_output(['git','rev-parse',args.before_ref+'^{commit}'],cwd=ROOT,text=True).strip()
    fixture=(HERE/'TranscriptStorePerformanceHost.java').read_text()
    results={}
    for label,before in [('before',True),('after',False)]:
        selected={name:(subprocess.check_output(['git','show',baseline_commit+':app/src/main/java/local/pocketchat/'+name],cwd=ROOT).decode() if before else (PRODUCTION/name).read_text()) for name in names}
        chat_url=member(selected['MainActivity.java'],'static boolean chatUrl(')
        generated=fixture.replace('/* CHAT_URL_METHOD */',chat_url)
        with tempfile.TemporaryDirectory(prefix='transcript-store-'+label+'-') as temporary:
            work=Path(temporary);java=work/'TranscriptStorePerformanceHost.java';java.write_text(generated)
            store=work/'WebTranscriptStore.java';store.write_text(selected['WebTranscriptStore.java'])
            utility=work/'J.java';utility.write_text(selected['J.java'])
            uri=work/'android/net/Uri.java';uri.parent.mkdir(parents=True)
            uri.write_text('package android.net;public final class Uri {private java.net.URI value;public static Uri parse(String text){Uri result=new Uri();result.value=java.net.URI.create(text);return result;}public String getScheme(){return value.getScheme();}public String getHost(){return value.getHost();}public String getUserInfo(){return value.getUserInfo();}public int getPort(){return value.getPort();}public String getPath(){return value.getPath();}}\n')
            classes=work/'classes'
            compiled=subprocess.run([tool('javac'),'-encoding','UTF-8','-source','8','-target','8','-cp',str(args.json_jar.resolve()),'-d',str(classes),str(java),str(store),str(utility),str(uri)],text=True,capture_output=True)
            if compiled.returncode:raise RuntimeError(label+' compile failed:\n'+compiled.stderr)
            ran=subprocess.run([tool('java'),'-Dbaseline='+str(before).lower(),'-cp',str(classes)+':'+str(args.json_jar.resolve()),'local.pocketchat.TranscriptStorePerformanceHost'],text=True,capture_output=True,timeout=60)
            if ran.returncode:raise RuntimeError(label+' workload failed:\n'+ran.stderr)
            result=json.loads(ran.stdout)
        result.update(selectedSourceSha256={name:digest(text.encode()) for name,text in selected.items()},chatUrlMethodSha256=digest(chat_url.encode()),generatedHarnessSha256=digest(generated.encode()))
        results[label]=result
    unchanged=all(path.is_file() and digest(path.read_bytes())==hashes[str(path.relative_to(ROOT))] for path in paths)
    total=sum(result['passed'] for result in results.values())
    report=dict(status='passed' if unchanged else 'source-changed',passed=total,total=total,sourceCommit=commit,baselineCommit=baseline_commit,
        sourceFiles=hashes,executionInputsUnchanged=unchanged,jsonJarSha256=digest(args.json_jar.read_bytes()),before=results['before'],after=results['after'],
        actualAndroidExecution=False,actualGeckoExecution=False,actualSqliteExecution=False,actualSharedPreferencesExecution=False,actualDevicePerformanceMeasurement=False,
        scope='Complete verbatim f43adac/current WebTranscriptStore and J, actual MainActivity.chatUrl, real production single-worker ExecutorService, and controlled manually advanced Handler/cache/preferences/URI adapters. Counted JSONArray subclass records production toString calls; oracle fixture serialization uses uncounted superclass calls.100changed64-message histories,40offer burst, stale queued worker/native invalidation,2URLs/current-only cursor, legacy sentinel preservation, offline load/stale-load guards and serialization/cache failures. Counts preference setter calls and exact characters passed to transcript setter, not actual XML/disk bytes, heap allocation or device frame time.')
    args.output.parent.mkdir(parents=True,exist_ok=True);args.output.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps(dict(status=report['status'],passed=total,total=total,
        cacheWrites={label:results[label]['streamingCacheWrites'] for label in results},
        transcriptPreferenceWrites={label:results[label]['transcriptPreferenceWrites'] for label in results},
        transcriptPreferenceCharacters={label:results[label]['transcriptPreferenceCharacters'] for label in results},
        conversationCursorWrites={label:results[label]['conversationCursorWrites'] for label in results},
        staleQueuedSerializations={label:results[label]['staleQueuedSerializations'] for label in results},
        actualAndroidExecution=False,output=str(args.output)),ensure_ascii=False))
    if report['status']!='passed':raise SystemExit(1)


if __name__=='__main__':main()
