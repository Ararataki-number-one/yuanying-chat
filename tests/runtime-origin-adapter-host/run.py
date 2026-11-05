#!/usr/bin/env python3
"""Run committed original/current Java origin adapters and their captured JS in JSDOM."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import tempfile

ROOT=Path(__file__).resolve().parents[2]
HERE=Path(__file__).resolve().parent
NAMES=['GeckoPerformanceIntegrationActivity.java','GeckoIntegrationTestActivity.java','CompactChromeIntegrationActivity.java','FingerprintFollowupIntegrationActivity.java']
BEFORE_COMMIT='72e3bcac55285fea483e612ba4481f7e073a5422'
BEFORE_SHA256={
    'GeckoPerformanceIntegrationActivity.java':'40d0b67983fdbd38c3fce7c8b6e97103682d63669e301a939082106772168fc9',
    'GeckoIntegrationTestActivity.java':'30b1e100831e37edca2c4a0bfd91b804a1a20691d4262bcc431c2cef1207fa7c',
    'CompactChromeIntegrationActivity.java':'0b057b3c982631466e4495d0afe6801c292b2b3a598a3f2e25b536df5b21c8c4',
    'FingerprintFollowupIntegrationActivity.java':'1b30b92708339fc8b9cabfd6f40f5c6995653c622ff488a112c3c1f4fa5f5e67',
}


def sha(raw):return hashlib.sha256(raw).hexdigest()


def member(text,needle):
    start=text.index(needle);opened=text.index('{',start);depth=0;quote=None;escape=line=block=False;i=opened
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
    raise ValueError('Unclosed actual member '+needle)


def command(args,env=None):
    executed=subprocess.run([str(x) for x in args],cwd=ROOT,text=True,capture_output=True,env=env,timeout=60)
    if executed.returncode:raise RuntimeError(executed.stderr or executed.stdout)
    return executed.stdout


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--java-home',type=Path,required=True)
    parser.add_argument('--json-jar',type=Path,required=True)
    parser.add_argument('--android-jar',type=Path,default=ROOT/'work/cloud-setup/platform/android-35/android.jar')
    parser.add_argument('--jsdom-module',type=Path,default=ROOT/'work/chat-smoothness-deps/node_modules/jsdom')
    parser.add_argument('--output',type=Path,default=ROOT/'work/runtime-origin-adapter-current/report-desktop.json',help='JSON report file')
    args=parser.parse_args()
    inputs=[ROOT/'tests/gecko'/name for name in NAMES]+[
        ROOT/'app/src/main/assets/page-driver.js',ROOT/'app/src/main/assets/web-performance.js',ROOT/'tests/gecko/assets/performance-baseline/page-driver.js',
        ROOT/'tests/gecko/assets/performance-baseline/web-performance.js',ROOT/'tests/gecko/assets/performance-baseline/source.json',
        ROOT/'app/src/main/java/local/pocketchat/MainActivity.java',ROOT/'app/src/main/java/local/pocketchat/J.java',
        HERE/'OriginAdapterCaptureHost.java.in',HERE/'check-dom.cjs',HERE/'README.md',Path(__file__).resolve()]
    hashes={str(path.relative_to(ROOT)):sha(path.read_bytes()) for path in inputs}
    source_commit=command(['git','rev-parse','HEAD']).strip()
    # Read old fixtures only as immutable historical inputs. Current execution
    # always comes from actual tracked tests/gecko files, never a preview tree.
    before_sources={name:command(['git','show',BEFORE_COMMIT+':tests/gecko/'+name]) for name in NAMES}
    for name,text in before_sources.items():
        if sha(text.encode())!=BEFORE_SHA256[name]:raise ValueError('Historical fixture bytes differ: '+name)
    baseline_root=ROOT/'tests/gecko/assets/performance-baseline'
    baseline_meta=json.loads((baseline_root/'source.json').read_text())
    for name,row in baseline_meta['files'].items():
        raw=(baseline_root/name).read_bytes()
        if len(raw)!=row['bytes'] or sha(raw)!=row['sha256']:raise ValueError('Historical baseline original bytes changed')
    current_driver=(ROOT/'app/src/main/assets/page-driver.js').read_text();old_driver=(baseline_root/'page-driver.js').read_text()
    old_guard="location.protocol !== 'https:' || location.hostname !== 'chatgpt.com'";new_guard="window !== window.top || location.origin !== 'https://chatgpt.com'"
    if old_driver.count(old_guard)!=1 or current_driver.count(new_guard)!=1:raise ValueError('Actual baseline/current asset must contain one own exact guard')
    fixture=(HERE/'OriginAdapterCaptureHost.java.in').read_text()
    main_origin=re.search(r'^  static final String ORIGIN=.*;$',(ROOT/'app/src/main/java/local/pocketchat/MainActivity.java').read_text(),re.M).group().strip()
    args.output.parent.mkdir(parents=True,exist_ok=True)
    captures=args.output.parent/('captured-'+sha(args.json_jar.read_bytes())[:12]);captures.mkdir(exist_ok=True)
    java_results={};selected_hashes={};generated_hashes={}
    with tempfile.TemporaryDirectory(prefix='runtime-origin-adapter-') as temporary:
        work=Path(temporary)
        for label,before in [('before',True),('after',False)]:
            selected=before_sources if before else {name:(ROOT/'tests/gecko'/name).read_text() for name in NAMES}
            follow=selected['FingerprintFollowupIntegrationActivity.java']
            methods={
                'PERFORMANCE_LOAD':member(selected[NAMES[0]],'void load(String mode)'),
                'COMPLETION':member(selected[NAMES[1]],'void completion(long serial)'),
                'COMPACT_EVALUATE':member(selected[NAMES[2]],'@Override public void evaluateJavascript(String code,android.webkit.ValueCallback<String> callback)'),
                'SOURCE_DRIVER_CONSTANT':re.search(r'^  static final String SOURCE_DRIVER_GUARD=.*;$',follow,re.M).group().strip(),
                'SOURCE_DRIVER_GUARD':member(follow,'static String sourceDriverGuard(String sourceUrl)'),
                'ADAPT_SOURCE_DRIVER':member(follow,'static String adaptSourceDriver(String code,String sourceUrl)'),
                'SHA256':member(follow,'static String sha256(String value)'),
                'FOLLOWUP_EVALUATE':member(follow,'@Override public void evaluateJavascript(String code,ValueCallback<String> callback)'),
                'MAIN_ORIGIN_CONSTANT':main_origin,
            }
            selected_hashes[label]={name:sha(text.encode()) for name,text in methods.items()}
            generated=fixture
            for name,text in methods.items():generated=generated.replace('/* '+name+' */',text)
            generated_hashes[label]=sha(generated.encode())
            generated_file=work/'OriginAdapterCaptureHost.java';generated_file.write_text(generated)
            classes=work/label
            command([args.java_home/'bin/javac','-encoding','UTF-8','-source','8','-target','8','-cp',str(args.json_jar.resolve())+os.pathsep+str(args.android_jar.resolve()),'-d',classes,generated_file,ROOT/'app/src/main/java/local/pocketchat/J.java'])
            output=captures/label;output.mkdir(exist_ok=True)
            raw=command([args.java_home/'bin/java','-cp',str(classes)+os.pathsep+str(args.json_jar.resolve())+os.pathsep+str(args.android_jar.resolve()),'local.pocketchat.OriginAdapterCaptureHost',label,ROOT,output])
            java_results[label]=json.loads(raw)
    env=dict(os.environ,JSDOM_MODULE=str(args.jsdom_module.resolve()))
    dom=json.loads(command(['node',HERE/'check-dom.cjs',captures],env))
    stable=all(sha(path.read_bytes())==hashes[str(path.relative_to(ROOT))] for path in inputs) and command(['git','rev-parse','HEAD']).strip()==source_commit
    passed=sum(value['passed'] for value in java_results.values())+dom['passed']
    report=dict(status='passed' if stable else 'source-changed',passed=passed,total=passed,sourceCommit=source_commit,
        sourceFiles=hashes,historicalBeforeCommit=BEFORE_COMMIT,historicalBeforeFiles=BEFORE_SHA256,
        extractedFragments=selected_hashes,generatedHostSha256=generated_hashes,executionInputsUnchanged=stable,
        currentSource='actual tracked tests/gecko files',trackedFilesWritten=False,
        originalHistoricalBaselineBytesVerified=True,baselineGuardCount=old_driver.count(old_guard),currentGuardCount=current_driver.count(new_guard),
        jsonJarSha256=sha(args.json_jar.read_bytes()),androidApiJarSha256=sha(args.android_jar.read_bytes()),actualAndroidValueCallbackInterface=True,
        actualAndroidExecution=False,actualGeckoExecution=False,actualNetworkExecution=False,javaCapture=java_results,dom=dom,
        scope='Verbatim complete immutable72e3 original/current tracked Java load/completion/evaluate methods and exact followup guard/adapter/hash constants/helpers, compiled with actual Android ValueCallback interface and explicit app/Gecko/callback capture facades. Synthetic callback JSON only drives native script generation; actual captured original/current driver JavaScript is independently executed in JSDOM documents/subframes. The old fixtures are negative controls, never an old runtime substituted for current sources. No tracked source mutation, Android/Gecko/HTTP/live account/release acceptance.')
    args.output.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps(dict(status=report['status'],passed=passed,total=passed,currentSource=report['currentSource'],actualAndroidExecution=False,actualGeckoExecution=False,output=str(args.output)),ensure_ascii=False))
    if not stable:raise SystemExit(1)


if __name__=='__main__':main()
