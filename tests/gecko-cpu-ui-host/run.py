#!/usr/bin/env python3
"""Compile the full current CPU editor with explicit UI and vault boundaries."""
import argparse,hashlib,json,shutil,subprocess,tempfile
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];HERE=Path(__file__).resolve().parent
def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()
WIDGETS={
'LinearLayout.java':'package android.widget;public final class LinearLayout {public final java.util.List<Object> children=new java.util.ArrayList<>();public final java.util.List<String> notes=new java.util.ArrayList<>();public void addView(Object view){children.add(view);}}',
'TextView.java':'package android.widget;public class TextView {public String text="";public void setText(String value){text=value;}}',
'Button.java':'package android.widget;public final class Button extends TextView {public boolean enabled=true;Runnable click;public void setEnabled(boolean value){enabled=value;}public void setOnClickListener(Runnable value){click=value;}public void click(){if(enabled&&click!=null)click.run();}}',
'Spinner.java':'package android.widget;public final class Spinner {public static final java.util.List<Spinner> all=new java.util.ArrayList<>();public String[] labels;public String description;public int position,minimumHeight;public Spinner(Object activity){all.add(this);}public void setContentDescription(String value){description=value;}public void setMinimumHeight(int value){minimumHeight=value;}public void setAdapter(Object value){labels=(String[])value;}public void setSelection(int value){position=value;}public int getSelectedItemPosition(){return position;}}'
}
def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--java-home',type=Path);p.add_argument('--json-jar',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
    def tool(name):
        value=str(a.java_home/'bin'/name) if a.java_home else shutil.which(name)
        if not value:p.error('Provide JDK17 --java-home')
        return value
    prod=ROOT/'app/src/main/java/local/pocketchat'
    sources=[prod/name for name in ['GeckoCpuUi.java','GeckoCpuSpec.java','EnvironmentSpec.java','J.java']]+[HERE/'CpuUiHost.java']
    inputs=sources+[Path(__file__).resolve()];hashes={str(v.relative_to(ROOT)):sha(v) for v in inputs};jarhash=sha(a.json_jar)
    with tempfile.TemporaryDirectory(prefix='gecko-cpu-ui-') as temporary:
        folder=Path(temporary);classes=folder/'classes';boundaries=[]
        for name,content in WIDGETS.items():
            path=folder/'android/widget'/name;path.parent.mkdir(parents=True,exist_ok=True);path.write_text(content+'\n');boundaries.append(path)
        compiled=subprocess.run([tool('javac'),'-encoding','UTF-8','-source','8','-target','8','-cp',str(a.json_jar.resolve()),'-d',str(classes),*map(str,sources+boundaries)],capture_output=True,text=True)
        if compiled.returncode:raise RuntimeError(compiled.stderr)
        run=subprocess.run([tool('java'),'-cp',str(classes)+':'+str(a.json_jar.resolve()),'local.pocketchat.CpuUiHost'],capture_output=True,text=True,timeout=30)
        if run.returncode:raise RuntimeError(run.stdout+'\n'+run.stderr)
        report=json.loads(run.stdout)
    stable=all(sha(path)==hashes[str(path.relative_to(ROOT))] for path in inputs) and sha(a.json_jar)==jarhash
    report.update(sourceCommit=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),sourceFiles=hashes,jsonJarSha256=jarhash,executionInputsUnchanged=stable,boundarySourcesSha256={name:hashlib.sha256((content+'\n').encode()).hexdigest() for name,content in WIDGETS.items()},actualAndroidExecution=False,actualGeckoNativeSettingExecution=False,actualAesKeystoreExecution=False,actualSqliteExecution=False,scope='Complete current GeckoCpuUi and GeckoCpuSpec plus actual EnvironmentSpec and J. Android widget/modal/activity, queued handler/executor, desired-state vault/CAS and native-controller status are explicit synthetic boundaries. Save-only UI control flow, not actual runtime CPU behavior; no native, Worker, SW, Android, SQLite or Keystore capability is inferred.')
    if not stable:raise RuntimeError('Execution input changed')
    a.output.parent.mkdir(parents=True,exist_ok=True);a.output.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n');print(json.dumps({k:report[k] for k in ['schema','status','passed','total','executionInputsUnchanged','actualAndroidExecution','actualGeckoNativeSettingExecution']}))
if __name__=='__main__':main()
