#!/usr/bin/env python3
"""Execute current Gecko context adaptation against the exact AOSP API 32 callback contract."""
import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import re
import subprocess
import tempfile

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]
PROD=ROOT/'app/src/main/java/local/pocketchat'
PARSER=ROOT/'tests/page-recovery-host/run.py'
spec=importlib.util.spec_from_file_location('context_host_member_parser',PARSER)
parser=importlib.util.module_from_spec(spec);spec.loader.exec_module(parser)
member=parser.member

def digest(path):return hashlib.sha256(path.read_bytes()).hexdigest()

def boundary(source):
    source=re.sub(r'^package [^;]+;\s*','',source,flags=re.M)
    source=re.sub(r'^import [^;]+;\s*','',source,flags=re.M)
    source=source.replace('android.content.SharedPreferences','PrefsBoundary').replace('android.app.Application','ApplicationBoundary')
    source=re.sub(r'@(?:NonNull|GuardedBy\("mLock"\))\s*','',source)
    for original,replacement in {'Context':'ContextBoundary','ContextWrapper':'ContextWrapperBoundary','ComponentCallbacks':'CallbacksBoundary','ComponentCallbacks2':'Callbacks2Boundary','ComponentCallbacksController':'ComponentCallbacksControllerBoundary','Configuration':'ConfigurationBoundary','Intent':'IntentBoundary','ComponentName':'ComponentNameBoundary','ServiceConnection':'ServiceConnectionBoundary','Application':'ApplicationBoundary','Build':'BuildBoundary'}.items():
        source=re.sub(r'\b'+original+r'\b',replacement,source)
    return source

def main():
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--java-home',type=Path,required=True);ap.add_argument('--output',type=Path,required=True);args=ap.parse_args()
    framework_path=HERE/'android32-callbacks.json';framework=json.loads(framework_path.read_text())
    controller_path=HERE/'ComponentCallbacksController.java.source'
    if digest(controller_path)!=framework['files']['ComponentCallbacksController.java']['sha256']:raise AssertionError('Pinned AOSP controller changed')
    selected={
      'PROFILES':('Profiles.java',('static int processSlot()','static int slot(Context c)','static Context global(Context c)')),
      'PROFILE_CONTEXT':('ProfileContext.java',('String name(String value)','public Context getApplicationContext()','public android.content.SharedPreferences getSharedPreferences(','File directory(File base)','public File getFilesDir()','public File getCacheDir()','public File getNoBackupFilesDir()')),
      'APPLICATION_CONTEXT':('PocketApplication.java',('synchronized Context profile(int id)','public Context getApplicationContext()')),
    }
    source=PROD/'GeckoEnvironmentContext.java';template=HERE/'ContextHost.java.in'
    files={source,template,framework_path,controller_path,Path(__file__).resolve(),PARSER}|{PROD/filename for filename,_ in selected.values()}
    hashes={str(path.relative_to(ROOT)):digest(path) for path in sorted(files)}
    actual=source.read_text();text=template.read_text()
    for marker,(filename,needles) in selected.items():
        raw=(PROD/filename).read_text();text=text.replace('@'+marker+'@',boundary('\n'.join(member(raw,needle) for needle in needles)))
    for marker,key in [('API32_CONTEXT_CALLBACKS','Context.java'),('API32_APPLICATION_CALLBACKS','Application.java')]:
        text=text.replace('@'+marker+'@',boundary('\n'.join(framework['files'][key]['members'])))
    controller='package local.pocketchat;\nimport java.util.*;\nimport java.util.function.Consumer;\n'+boundary(controller_path.read_text())
    args.output.parent.mkdir(parents=True,exist_ok=True);artifacts=args.output.with_name(args.output.stem+'-artifacts');artifacts.mkdir(exist_ok=True)
    controls=[]
    with tempfile.TemporaryDirectory(prefix='gecko-context-host-') as temporary:
        def execute(adapter,label):
            folder=artifacts/label;folder.mkdir(exist_ok=True);work=Path(temporary)/label;work.mkdir()
            rendered=text.replace('@GECKO_CONTEXT@',boundary(adapter));host=folder/'ContextHost.java';host.write_text(rendered)
            controller_file=folder/'ComponentCallbacksControllerBoundary.java';controller_file.write_text(controller)
            command=[str(args.java_home/'bin/javac'),'-encoding','UTF-8','-d',str(work),str(host),str(controller_file)]
            compiled=subprocess.run(command,capture_output=True,text=True,timeout=30);(folder/'compile.command.json').write_text(json.dumps(command)+'\n');(folder/'compile.stderr.log').write_text(compiled.stderr)
            if compiled.returncode:raise RuntimeError(compiled.stderr)
            command=[str(args.java_home/'bin/java'),'-Xss256k','-cp',str(work),'local.pocketchat.ContextHost',str(work/'data')]
            ran=subprocess.run(command,capture_output=True,text=True,timeout=15);(folder/'run.command.json').write_text(json.dumps(command)+'\n');(folder/'run.stdout.log').write_text(ran.stdout);(folder/'run.stderr.log').write_text(ran.stderr)
            return ran
        ran=execute(actual,'current')
        if ran.returncode:raise AssertionError(ran.stdout+ran.stderr)
        checks=[line[5:] for line in ran.stdout.splitlines() if line.startswith('PASS ')]
        register=member(actual,'@Override public void registerComponentCallbacks(')
        unregister=member(actual,'@Override public void unregisterComponentCallbacks(')
        mutations=[
          ('old-api32-recursion',actual.replace(register,'').replace(unregister,''),'Callback registration must reach the actual Application without recursion'),
          ('base-profile-recursion',actual.replace('Profiles.global(getBaseContext())','getBaseContext()'),'Callback registration must reach the actual Application without recursion'),
          ('unregister-lost',actual.replace('Profiles.global(getBaseContext()).unregisterComponentCallbacks(callback);',''),'Unregister removes exactly the registered callback 0'),
          ('application-isolation-lost',actual.replace('@Override public Context getApplicationContext(){return this;}','@Override public Context getApplicationContext(){return Profiles.global(getBaseContext());}'),'Gecko keeps its isolated application context 0'),
        ]
        for label,mutant,expected in mutations:
            if mutant==actual:raise AssertionError('Mutation did not change source: '+label)
            result=execute(mutant,label)
            if result.returncode==0 or 'AssertionError: '+expected not in result.stderr:raise AssertionError('Expected behavioral rejection missing: '+label+'\n'+result.stderr)
            controls.append(dict(name=label,compiled=True,mutantRejected=True,expectedAssertion=expected))
    unchanged=all(digest(ROOT/path)==value for path,value in hashes.items())
    report=dict(status='passed' if unchanged else 'source-changed',passed=len(checks),checks=checks,negativeControls=controls,executionInputsUnchanged=unchanged,sourceFiles=hashes,sourceCommit=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),frameworkSource=framework,actualJavaAdapterExecution=True,actualAndroidExecution=False,actualGeckoExecution=False,boundaries=['Complete current GeckoEnvironmentContext, selected current Profiles slot/global and ProfileContext application/preferences/directories, and PocketApplication profile cache methods execute with type tokens renamed to explicit host boundary names.','Exact AOSP android-12.1.0_r1 Context callback methods, Application callback methods, and complete callback controller execute; ContextWrapper inherits Context callback dispatch as on API 32.','Context storage and native service binding are recording boundaries; profile constructor ownsProcess is fixed true, process name is the default process, configuration objects and service callbacks are opaque boundary identities.','No Android framework runtime, GeckoRuntime, real service binding, emulator, or physical-device acceptance is claimed.'])
    args.output.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n');print(json.dumps({k:report[k] for k in ('status','passed','executionInputsUnchanged')}|{'negativeControls':len(controls),'output':str(args.output)}))
    if not unchanged:raise SystemExit(1)

if __name__=='__main__':main()
