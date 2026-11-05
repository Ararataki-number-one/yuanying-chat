#!/usr/bin/env python3
"""Current production tls deletion/SealedFileIo filesystem controls."""
import argparse,hashlib,json,subprocess,tempfile
from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]
HERE=Path(__file__).resolve().parent
PROD=ROOT/'app/src/main/java/local/pocketchat'
def sha(raw):return hashlib.sha256(raw).hexdigest()
def balanced(source,brace):
    depth=0;state='code';index=brace
    while index<len(source):
        char=source[index];pair=source[index:index+2]
        if state in ('string','char'):
            if char=='\\':index+=2;continue
            if char==('"'if state=='string'else"'"):state='code'
        elif state=='line':
            if char=='\n':state='code'
        elif state=='comment':
            if pair=='*/':state='code';index+=2;continue
        elif pair=='//':state='line';index+=2;continue
        elif pair=='/*':state='comment';index+=2;continue
        elif char=='"':state='string'
        elif char=="'":state='char'
        elif char=='{':depth+=1
        elif char=='}':
            depth-=1
            if depth==0:return index+1
        index+=1
    raise ValueError('Actual Java member incomplete')
def member(source,signature):
    assert source.count(signature)==1,signature
    start=source.index(signature);return source[start:balanced(source,source.index('{',start))]
def extracted(source):
    start=source.index('if(slot>0){File files=new File(data,"files/profiles/env"+slot);')
    tail=balanced(source,source.index('{',start))
    while source[tail].isspace():tail+=1
    assert source.startswith('else{',tail)
    return source[start:balanced(source,source.index('{',tail))],member(source,'static void erase(File f)throws IOException{')
def change(raw,before,after):
    assert raw.count(before)==1,before
    return raw.replace(before,after,1)

def guard_order(source):
    # These remain source/order checks, separate from the executed filesystem
    # branch below. Framework/process/catalogue actions are not mocked as run.
    body=member(source,'private static void performRemove(Context c,int slot,EnvironmentSpec.Identity expected)throws Exception{')
    guard='EnvironmentResetActivity.verifyRoots(c,slot);'
    assert body[body.index('{')+1:].lstrip().startswith(guard)
    assert body.count(guard)==2 and body.count('requireCurrent(catalog,expected)')==2
    first=body.index(guard);second=body.rindex(guard)
    for sideEffect in ('ProfileCatalog.get(c)','Profiles.context(c,slot)','DownloadLibrary.get(c).migrate()','new NetworkCatalog(c)','"stopForDelete"'):
        assert first<body.index(sideEffect)
    assert body.index('"stopForDelete"')<body.index('android.os.Process.killProcess(p.pid)')<body.index('Thread.sleep(100);}while(true);')<second
    assert body.index('requireCurrent(catalog,expected)')<body.index('"stopForDelete"')
    assert second<body.rindex('requireCurrent(catalog,expected)')<body.index('NotificationManager notices=')
    for destructive in ('files.listFiles()','erase(new File(data,"cache/profiles/env"+slot))','erase(new File(profile.getNoBackupFilesDir(),name))','profile.deleteDatabase(name)','catalog.completeDelete(expected)'):
        assert second<body.index(destructive)
    outer=member(source,'static void remove(Context c,EnvironmentSpec.Identity expected)throws Exception{')
    assert 'EnvironmentMaintenanceLease.with' in outer and 'performRemove(c,expected.slot,expected)'in outer
    assert 'catalog.completeDelete(slot)'not in body

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--java-home',required=True,type=Path);p.add_argument('--json-jar',required=True,type=Path);p.add_argument('--output',required=True,type=Path);a=p.parse_args()
    inputs=[PROD/'EnvironmentDeleteActivity.java',PROD/'EnvironmentResetActivity.java',PROD/'SecretStore.java',PROD/'SealedFileIo.java',PROD/'EnvironmentBrowserData.java',HERE/'TlsCleanupHost.java.in',Path(__file__).resolve(),ROOT/'tests/sealed-file-host/android/util/AtomicFile.java',ROOT/'tests/browser-runtime/EnvironmentLifecyclePolicyTest.java']
    before={str(x.relative_to(ROOT)):sha(x.read_bytes())for x in inputs}
    source=(PROD/'EnvironmentDeleteActivity.java').read_text()
    baselineRef='9f5d8913060f3b97c042120570eb5bfcb71e5dd8'
    baselineBytes=subprocess.check_output(['git','show',baselineRef+':app/src/main/java/local/pocketchat/EnvironmentDeleteActivity.java'],cwd=ROOT)
    baseline=baselineBytes.decode('utf-8')
    guard_order(source)
    branch,erase=extracted(source);oldbranch,_=extracted(baseline)
    secret=(PROD/'SecretStore.java').read_text();members={'/*ACTUAL_SECRET_CONSTRUCTOR*/':member(secret,'SecretStore(Context c)'), '/*ACTUAL_SECRET_FILE*/':member(secret,'File file(String slot)'), '/*ACTUAL_SECRET_REMOVE*/':member(secret,'void remove(String slot)')}
    template=(HERE/'TlsCleanupHost.java.in').read_text()
    for key,value in members.items():assert template.count(key)==1;template=template.replace(key,value)
    template=template.replace('/*ACTUAL_ERASE_METHOD*/',erase)
    variants={
        'current':(branch,template),
        'actual-pre-tls-baseline':(oldbranch,template),
        'omit-tls-sealed':(change(branch,',"gecko-tls"',''),template),
        'omit-tls-lock':(change(branch,'      erase(new File(profile.getNoBackupFilesDir(),"gecko-tls.lock"));\n',''),template),
        'omit-tls-config-scratch':(change(branch,',"pocket-tls-config.tmp"',''),template),
        'erase-other-environment':(change(branch,'erase(new File(profile.getNoBackupFilesDir(),"environment-spec.lock"));','erase(new File(profile.getNoBackupFilesDir(),"environment-spec.lock"));erase(new File(data,"no_backup/profiles/env3"));'),template),
        'primary-only-sealed-delete':(branch,change(template,members['/*ACTUAL_SECRET_REMOVE*/'],'void remove(String slot)throws Exception{file(slot).delete();}')),
    }
    results=[];positive=None;compiledHashes={}
    lifecycleSources=[PROD/(name+'.java')for name in ['J','Sha256','EnvironmentSpec','EnvironmentSpecMigration','EnvironmentResetPlan','EnvironmentBrowserData','EnvironmentProcessPolicy']]+[ROOT/'tests/browser-runtime/EnvironmentLifecyclePolicyTest.java']
    for f in lifecycleSources:before[str(f.relative_to(ROOT))]=sha(f.read_bytes())
    commands=[]
    with tempfile.TemporaryDirectory(prefix='tls-delete-fs-')as temp:
        work=Path(temp)
        for name,(current,base)in variants.items():
            d=work/name;d.mkdir();path=d/'TlsCleanupHost.java';generated=base.replace('/*ACTUAL_CLEANUP_BRANCH*/',current);path.write_text(generated);compiledHashes[name]=sha(generated.encode())
            cmd=[str(a.java_home/'bin/javac'),'-encoding','UTF-8','-source','8','-target','8','-d',str(d/'classes'),str(PROD/'EnvironmentBrowserData.java'),str(PROD/'SealedFileIo.java'),str(ROOT/'tests/sealed-file-host/android/util/AtomicFile.java'),str(path)]
            compile=subprocess.run(cmd,capture_output=True,text=True,timeout=30);commands.append(dict(variant=name,compileExit=compile.returncode))
            if compile.returncode:raise RuntimeError(name+' compile failed, not a semantic rejection:\n'+compile.stderr)
            run=subprocess.run([str(a.java_home/'bin/java'),'-cp',str(d/'classes'),'local.pocketchat.TlsCleanupHost',str(d/'files')],capture_output=True,text=True,timeout=30)
            if name=='current':
                if run.returncode:raise RuntimeError(run.stderr)
                positive=json.loads(run.stdout);results.append(dict(name=name,status='passed',checks=positive['passed']))
            else:
                if run.returncode==0 or 'java.lang.AssertionError:'not in run.stderr:raise RuntimeError(name+' did not fail filesystem assertion:\n'+run.stderr)
                results.append(dict(name=name,status='rejected',compiled=True,assertion=run.stderr.split('java.lang.AssertionError: ',1)[1].split('\n',1)[0]))
        classes=work/'lifecycle-classes';cmd=[str(a.java_home/'bin/javac'),'-encoding','UTF-8','-source','8','-target','8','-cp',str(a.json_jar),'-d',str(classes),*map(str,lifecycleSources)]
        compile=subprocess.run(cmd,capture_output=True,text=True,timeout=30)
        if compile.returncode:raise RuntimeError('Original 39 lifecycle compilation failed:\n'+compile.stderr)
        run=subprocess.run([str(a.java_home/'bin/java'),'-cp',str(classes)+':'+str(a.json_jar),'local.pocketchat.EnvironmentLifecyclePolicyTest'],capture_output=True,text=True,timeout=30)
        if run.returncode:raise RuntimeError(run.stderr)
        original=json.loads(run.stdout);assert original['passed']==original['total']==39 and all(x['pass']is True for x in original['checks'])
    assert all((ROOT/key).is_file()and sha((ROOT/key).read_bytes())==value for key,value in before.items())
    report=dict(schema=1,status='passed',sourceCommit=subprocess.check_output(['git','rev-parse','HEAD'],text=True,cwd=ROOT).strip(),actualAndroidExecution=False,actualAesKeystoreExecution=False,actualGeckoExecution=False,sourceFiles=before,executionInputsUnchanged=True,reportApplied=True,baselineRef=baselineRef,baselineSourceSha256=sha(baselineBytes),filesystemChecks=positive['passed'],filesystemOutcomes=results,originalLifecycleChecks=39,originalLifecycleReport=original,rootIdentityAndWriterExitOrderChecked=True,frameworkProcessLifecycleExecuted=False,compiledCounterfeits=len(variants)-2,actualBaselineRejected=True,memberSha256={'slotCleanupBranch':sha(branch.encode()),'erase':sha(erase.encode()),**{key:sha(value.encode())for key,value in members.items()}},compiledAdapterSha256=compiledHashes,jsonJarSha256=sha(a.json_jar.read_bytes()),scope='Actual verbatim slot>0/else cleanup branch and erase, actual SecretStore constructor/file/remove, complete actual SealedFileIo and EnvironmentBrowserData on a real temporary filesystem. AtomicFile is the existing explicit host adapter. Context directory mapping is explicit. Activity/framework/process stop/catalog identity/shared preferences/databases/final catalogue deletion are outside this branch harness; their retained root/identity/writer-exit order is inspected separately. Original 39 model/filesystem controls run unchanged separately. No Android/Keystore/browser acceptance claim.')
    a.output.parent.mkdir(parents=True,exist_ok=True)
    a.output.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n');print(json.dumps({k:report[k]for k in ['status','filesystemChecks','originalLifecycleChecks','compiledCounterfeits','actualBaselineRejected','executionInputsUnchanged','actualAndroidExecution']}))
if __name__=='__main__':main()
