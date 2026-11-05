#!/usr/bin/env python3
"""Execute actual environment CPU cleanup branch with real files and semantic mutants."""
import argparse,hashlib,json,shutil,subprocess,tempfile
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];HERE=Path(__file__).resolve().parent
def sha(value):return hashlib.sha256(value).hexdigest()
def balanced(source,brace):
    depth=0;state='code';index=brace
    while index<len(source):
        char=source[index];pair=source[index:index+2]
        if state in ('string','char'):
            if char=='\\':index+=2;continue
            if char==('"' if state=='string' else "'"):state='code'
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
    raise ValueError('Actual Java block is incomplete')
def extracted(source):
    marker='if(slot>0){File files=new File(data,"files/profiles/env"+slot);'
    if source.count(marker)!=1:raise ValueError('Unique actual slot cleanup branch required')
    start=source.index(marker);first_end=balanced(source,source.index('{',start));tail=first_end
    while source[tail].isspace():tail+=1
    if not source.startswith('else{',tail):raise ValueError('Actual slot-zero else branch required')
    end=balanced(source,source.index('{',tail));branch=source[start:end]
    marker='static void erase(File f)throws IOException{'
    if source.count(marker)!=1:raise ValueError('Unique actual recursive erase method required')
    start=source.index(marker);erase=source[start:balanced(source,source.index('{',start))]
    return branch,erase
def change(source,before,after):
    if source.count(before)!=1:raise ValueError('Exact one-site semantic mutation required: '+before)
    return source.replace(before,after,1)
def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--java-home',type=Path);parser.add_argument('--output',type=Path,required=True);args=parser.parse_args()
    def tool(name):return str(args.java_home/'bin'/name) if args.java_home else shutil.which(name)
    delete=ROOT/'app/src/main/java/local/pocketchat/EnvironmentDeleteActivity.java';browser=ROOT/'app/src/main/java/local/pocketchat/EnvironmentBrowserData.java';template=HERE/'CpuCleanupHost.java.in';inputs=[delete,browser,template,Path(__file__).resolve()];hashes={str(path.relative_to(ROOT)):sha(path.read_bytes()) for path in inputs};source=delete.read_text();host=template.read_text();branch,erase=extracted(source)
    if host.count('/*ACTUAL_CLEANUP_BRANCH*/')!=1 or host.count('/*ACTUAL_ERASE_METHOD*/')!=1:raise ValueError('Unique host insertions required')
    variants={'current':branch,'omitted-cpu':change(branch,',"gecko-cpu"',''),'omitted-cpu-lock':change(branch,'erase(new File(profile.getNoBackupFilesDir(),"gecko-cpu.lock"));','/* Mutant omits CPU store lock cleanup. */'),'skipped-private-cleanup':change(branch,'privateStore.remove(name);','if(false)privateStore.remove(name);'),'wrong-slot-branch':change(branch,'if(slot>0)','if(slot>=0)'),'other-environment-erased':change(branch,'erase(new File(profile.getNoBackupFilesDir(),"environment-spec.lock"));','erase(new File(profile.getNoBackupFilesDir(),"environment-spec.lock"));erase(new File(data,"no_backup/profiles/env3"));')}
    results=[];positive=None;compiled_hashes={}
    with tempfile.TemporaryDirectory(prefix='cpu-cleanup-host-') as temp:
        work=Path(temp)
        for name,actual in variants.items():
            folder=work/name;folder.mkdir();java=folder/'CpuCleanupHost.java';compiled=host.replace('/*ACTUAL_CLEANUP_BRANCH*/',actual).replace('/*ACTUAL_ERASE_METHOD*/',erase);java.write_text(compiled);compiled_hashes[name]=sha(compiled.encode())
            compile_run=subprocess.run([tool('javac'),'-encoding','UTF-8','-source','8','-target','8','-d',str(folder/'classes'),str(browser),str(java)],capture_output=True,text=True)
            if compile_run.returncode:raise RuntimeError(name+' compilation failed rather than exercising filesystem semantics:\n'+compile_run.stderr)
            run=subprocess.run([tool('java'),'-cp',str(folder/'classes'),'local.pocketchat.CpuCleanupHost',str(folder/'files')],capture_output=True,text=True,timeout=30)
            if name=='current':
                if run.returncode:raise RuntimeError('Actual current cleanup failed:\n'+run.stderr)
                positive=json.loads(run.stdout);results.append(dict(name=name,status='passed',passed=positive['passed']))
            else:
                if run.returncode==0 or 'java.lang.AssertionError:' not in run.stderr:raise RuntimeError('Semantic mutant was not rejected by actual filesystem assertion: '+name+'\n'+run.stderr)
                results.append(dict(name=name,status='rejected',compiled=True,filesystemAssertion=run.stderr.split('java.lang.AssertionError: ',1)[1].split('\n',1)[0]))
    stable=all(sha(path.read_bytes())==hashes[str(path.relative_to(ROOT))] for path in inputs)
    if not stable:raise RuntimeError('Cleanup input source changed during execution')
    report=dict(schema=1,status='passed',passed=positive['passed']+len(variants)-1,total=positive['total']+len(variants)-1,checks=positive['checks']+['Actual source semantic mutant rejected: '+value['name'] for value in results[1:]],semanticMutants=results[1:],sourceCommit=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),sourceFiles=hashes,methodSha256={'slotCleanupBranch':sha(branch.encode()),'erase':sha(erase.encode())},compiledAdapterSha256=compiled_hashes,executionInputsUnchanged=stable,actualAndroidExecution=False,actualGeckoNativeSettingExecution=False,actualAesKeystoreExecution=False,scope='Verbatim actual EnvironmentDeleteActivity slot>0/else cleanup branch and erase method, complete actual EnvironmentBrowserData, real temp filesystem. FixtureProfile directory and opaque SecretStore.remove boundaries only; Activity lifecycle, process stop, catalog identity, shared preference/database/final catalog deletion are outside this harness. All five mutants compile and fail real filesystem assertions; CPU empty-lock removal and other-environment/default lock preservation are observed.')
    args.output.parent.mkdir(parents=True,exist_ok=True);args.output.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n');print(json.dumps({key:report[key] for key in ['schema','status','passed','total','executionInputsUnchanged','actualAndroidExecution']}))
if __name__=='__main__':main()
