#!/usr/bin/env python3
"""Cold controller/file behavior; explicit callback/Android boundaries, no native proof."""
import argparse,hashlib,json,subprocess,tempfile
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];HERE=Path(__file__).resolve().parent
def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--java-home',required=True,type=Path);p.add_argument('--json-jar',required=True,type=Path);p.add_argument('--output',required=True,type=Path);a=p.parse_args()
    names=['GeckoCpuController.java','GeckoCpuProfile.java','GeckoCpuSpec.java','GeckoCpuStore.java','EnvironmentSpec.java','NetworkShareJson.java','J.java'];sources=[ROOT/'app/src/main/java/local/pocketchat'/n for n in names]+[HERE/'ControllerHost.java'];inputs=sources+[Path(__file__).resolve()];before={str(f.relative_to(ROOT)):sha(f) for f in inputs}
    with tempfile.TemporaryDirectory(prefix='cpu-controller-host-') as tmp:
        work=Path(tmp);context=work/'android/content/Context.java';context.parent.mkdir(parents=True);context.write_text('package android.content;public abstract class Context {public abstract Context getApplicationContext();public abstract java.io.File getNoBackupFilesDir();public abstract android.content.pm.ApplicationInfo getApplicationInfo();}\n');process=work/'android/os/Process.java';process.parent.mkdir(parents=True);process.write_text('package android.os;public final class Process {public static int myPid(){return 111;}}\n');info=work/'android/content/pm/ApplicationInfo.java';info.parent.mkdir(parents=True);info.write_text('package android.content.pm;public final class ApplicationInfo{public String dataDir;}\n');classes=work/'classes'
        cmd=[str(a.java_home/'bin/javac'),'-source','8','-target','8','-encoding','UTF-8','-cp',str(a.json_jar),'-d',str(classes),*map(str,sources),str(context),str(process),str(info)];compiled=subprocess.run(cmd,text=True,capture_output=True)
        if compiled.returncode:raise RuntimeError(compiled.stderr)
        result=subprocess.run([str(a.java_home/'bin/java'),'-cp',str(classes)+':'+str(a.json_jar),'local.pocketchat.ControllerHost',str(work/'files')],text=True,capture_output=True)
        if result.returncode:raise RuntimeError(result.stderr)
        report=json.loads(result.stdout)
    stable=all(sha(ROOT/f)==digest for f,digest in before.items());report.update(schema=1,sourceCommit=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),sourceFiles=before,executionInputsUnchanged=stable,jsonJarSha256=sha(a.json_jar),scope='Verbatim CPU production controller, profile filter, spec/store. Real filesystem/AtomicMove, explicit Context/catalog/plain-vault/process/mainQueue/native-callback models. No Gecko SDK, SQLite, Keystore, actual native setting, page orWorker/runtime Android proof.')
    if not stable:report['status']='source-changed'
    a.output.parent.mkdir(parents=True,exist_ok=True);a.output.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n');print(json.dumps({k:report[k] for k in ['status','passed','total','executionInputsUnchanged','actualAndroidExecution','actualGeckoExecution']}))
    if not stable:raise SystemExit(1)
if __name__=='__main__':main()
