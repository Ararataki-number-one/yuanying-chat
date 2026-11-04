#!/usr/bin/env python3
"""Run full browser library/address policy/JSON utility with environment preference adapters."""
import argparse,hashlib,json,pathlib,subprocess,tempfile
ROOT=pathlib.Path(__file__).resolve().parents[2];HERE=pathlib.Path(__file__).resolve().parent
PROD=ROOT/'app/src/main/java/local/pocketchat'

def main():
    p=argparse.ArgumentParser();p.add_argument('--java-home',required=True,type=pathlib.Path);p.add_argument('--json-jar',required=True,type=pathlib.Path);p.add_argument('--output',required=True,type=pathlib.Path);args=p.parse_args()
    names=['BrowserLibrary.java','BrowserAddressPolicy.java','J.java'];paths=[PROD/name for name in names]+[HERE/'BrowserLibraryHost.java',pathlib.Path(__file__).resolve()]
    hashes={str(path.relative_to(ROOT)):hashlib.sha256(path.read_bytes()).hexdigest() for path in paths}
    with tempfile.TemporaryDirectory(prefix='browser-library-host-') as raw:
        base=pathlib.Path(raw);src=base/'src';src.mkdir();(src/'BrowserLibraryHost.java').write_bytes((HERE/'BrowserLibraryHost.java').read_bytes())
        for name in names:(src/name).write_bytes((PROD/name).read_bytes())
        stubs={'android/content/Context.java':'package android.content;public abstract class Context{public abstract SharedPreferences getSharedPreferences(String name,int mode);}', 'android/content/SharedPreferences.java':'package android.content;public interface SharedPreferences{String getString(String key,String fallback);Editor edit();interface Editor{Editor putString(String key,String value);Editor remove(String key);void apply();}}'}
        for name,text in stubs.items():path=src/name;path.parent.mkdir(parents=True,exist_ok=True);path.write_text(text)
        classes=base/'classes';compile=subprocess.run([str(args.java_home/'bin/javac'),'-encoding','UTF-8','-cp',str(args.json_jar.resolve()),'-d',str(classes),*map(str,src.rglob('*.java'))],capture_output=True,text=True)
        if compile.returncode:raise RuntimeError(compile.stderr)
        run=subprocess.run([str(args.java_home/'bin/java'),'-cp',str(classes)+':'+str(args.json_jar.resolve()),'local.pocketchat.BrowserLibraryHost'],capture_output=True,text=True)
        if not run.stdout:raise RuntimeError(run.stderr)
        report=json.loads(run.stdout)
    report.update(sourceCommit=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),sourceFiles=hashes,jsonJarSha256=hashlib.sha256(args.json_jar.read_bytes()).hexdigest(),executionInputsUnchanged=all(path.is_file() and hashlib.sha256(path.read_bytes()).hexdigest()==hashes[str(path.relative_to(ROOT))] for path in paths),actualAndroidExecution=False,actualBrowserExecution=False,scope='Complete production BrowserLibrary, BrowserAddressPolicy and J. Explicit in-memory Context/SharedPreferences/Editor adapters supply separate environment stores; actual ProfileContext, Android persistence scheduling, Chromium/Gecko, page content, DNS and network are not executed. Workloads cover 250 history visits, 130 bookmarks, hard/caller caps, recency/dedup/removal, malicious or malformed old records, two-MiB input rejection, title/surrogate bounds and serialized-storage independence.')
    if not report['executionInputsUnchanged']:report['status']='source-changed'
    args.output.parent.mkdir(parents=True,exist_ok=True);args.output.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps({k:report[k] for k in ['status','passed','total']},ensure_ascii=False))
    if run.returncode or report['status']!='passed':raise SystemExit(1)
if __name__=='__main__':main()
