#!/usr/bin/env python3
"""Full current Gecko CPU desired-state spec/store with explicit Android I/O boundaries."""
import argparse,hashlib,json,shutil,subprocess,tempfile
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];HERE=Path(__file__).resolve().parent
PRODUCTION=ROOT/'app/src/main/java/local/pocketchat'
def digest(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--java-home',type=Path);p.add_argument('--json-jar',required=True,type=Path);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
    def tool(name):
        value=str(a.java_home/'bin'/name) if a.java_home else shutil.which(name)
        if not value:p.error('Provide --java-home with '+name)
        return value
    sources=[PRODUCTION/name for name in ['GeckoCpuSpec.java','GeckoCpuStore.java','EnvironmentSpec.java','NetworkShareJson.java','J.java']]
    inputs=sources+[HERE/'GeckoCpuHost.java',Path(__file__).resolve()];hashes={str(path.relative_to(ROOT)):digest(path) for path in inputs};jar_hash=digest(a.json_jar);results=[]
    with tempfile.TemporaryDirectory(prefix='gecko-cpu-host-') as temp:
        work=Path(temp);classes=work/'classes';context=work/'android/content/Context.java';context.parent.mkdir(parents=True)
        context.write_text('package android.content;public abstract class Context {public abstract Context getApplicationContext();public abstract java.io.File getNoBackupFilesDir();}\n')
        compiled=subprocess.run([tool('javac'),'-encoding','UTF-8','-source','8','-target','8','-cp',str(a.json_jar.resolve()),'-d',str(classes),*map(str,sources),str(HERE/'GeckoCpuHost.java'),str(context)],capture_output=True,text=True)
        if compiled.returncode:raise RuntimeError(compiled.stderr)
        base=[tool('java'),'-cp',str(classes)+':'+str(a.json_jar.resolve()),'local.pocketchat.GeckoCpuHost']
        def execute(phase,*extra):
            result=subprocess.run([*base,phase,str(work/'state'),*extra],capture_output=True,text=True,timeout=30)
            if result.returncode:raise RuntimeError(phase+' failed:\n'+result.stderr)
            results.append(json.loads(result.stdout))
        for phase in ['main','restart-seed','restart-check','race-seed']:execute(phase)
        processes=[subprocess.Popen([*base,'race-write',str(work/'state'),label],stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True) for label in ['A','B']]
        for child in processes:
            stdout,stderr=child.communicate(timeout=30)
            if child.returncode:raise RuntimeError('Concurrent process failed:\n'+stderr)
            results.append(json.loads(stdout))
        execute('race-check')
    stable=all(path.is_file() and digest(path)==hashes[str(path.relative_to(ROOT))] for path in inputs) and digest(a.json_jar)==jar_hash;total=sum(value['passed'] for value in results)
    report=dict(schema=1,status='passed' if stable else 'source-changed',passed=total,total=total,sourceCommit=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),sourceFiles=hashes,executionInputsUnchanged=stable,jsonJarSha256=jar_hash,phases=results,separateJvmRestartExecuted=True,concurrentJvmCasExecuted=True,actualAndroidExecution=False,actualGeckoNativeSettingExecution=False,actualSqliteExecution=False,actualAesKeystoreExecution=False,scope='Complete current production GeckoCpuSpec/Store plus actual EnvironmentSpec, strict NetworkShareJson and J. Real temp files, FileLock, concurrent callers and independent JVMs. Explicit Context/catalog identity transaction/plain atomic vault adapters with read/write fault injection. Desired-only state; no native pref, webpage, Worker, Service Worker or per-environment fingerprint-isolation evidence.')
    a.output.parent.mkdir(parents=True,exist_ok=True);a.output.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n');print(json.dumps({key:report[key] for key in ['status','passed','total','executionInputsUnchanged','separateJvmRestartExecuted','concurrentJvmCasExecuted','actualAndroidExecution','actualGeckoNativeSettingExecution']}))
    if not stable:raise SystemExit(1)
if __name__=='__main__':main()
