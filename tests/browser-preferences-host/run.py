#!/usr/bin/env python3
"""Execute complete browser preferences and verbatim Main dispatch with Android adapters."""
import argparse,hashlib,importlib.util,json,pathlib,subprocess,tempfile
ROOT=pathlib.Path(__file__).resolve().parents[2]
HERE=pathlib.Path(__file__).resolve().parent
PROD=ROOT/'app/src/main/java/local/pocketchat'
spec=importlib.util.spec_from_file_location('extract',ROOT/'tests/chrome-network-state-host/run.py')
extract=importlib.util.module_from_spec(spec);spec.loader.exec_module(extract)

def main():
    p=argparse.ArgumentParser();p.add_argument('--java-home',required=True,type=pathlib.Path);p.add_argument('--json-jar',required=True,type=pathlib.Path);p.add_argument('--output',required=True,type=pathlib.Path);args=p.parse_args()
    paths=[PROD/name for name in ['BrowserPreferences.java','BrowserAddressPolicy.java','MainActivity.java']]+[HERE/'BrowserPreferencesHost.java',pathlib.Path(__file__).resolve(),ROOT/'tests/chrome-network-state-host/run.py']
    hashes={str(path.relative_to(ROOT)):hashlib.sha256(path.read_bytes()).hexdigest() for path in paths}
    dispatch=extract.member((PROD/'MainActivity.java').read_text(),'boolean dispatchBrowser(')
    source=(HERE/'BrowserPreferencesHost.java').read_text().replace('/* DISPATCH_METHOD */',dispatch)
    stubs={
      'android/content/Context.java':'package android.content;public abstract class Context{public static final int MODE_PRIVATE=0;public abstract SharedPreferences getSharedPreferences(String name,int mode);}',
      'android/content/SharedPreferences.java':'package android.content;public interface SharedPreferences{String getString(String key,String fallback);Editor edit();interface Editor{Editor putString(String key,String value);boolean commit();}}',
      'android/app/Activity.java':'package android.app;public abstract class Activity extends android.content.Context{public int finishes;public void finish(){finishes++;}}',
      'android/net/Uri.java':'package android.net;public final class Uri{private final java.net.URI value;private Uri(String s){value=java.net.URI.create(s);}public static Uri parse(String s){return new Uri(s);}public String getScheme(){return value.getScheme();}public String getHost(){return value.getHost();}public String toString(){return value.toString();}}',
      'android/content/Intent.java':'package android.content;public final class Intent{private final java.util.Map<String,Object> extras=new java.util.LinkedHashMap<>();private android.net.Uri data;public Intent putExtra(String k,String v){extras.put(k,v);return this;}public Intent putExtra(String k,boolean v){extras.put(k,v);return this;}public boolean getBooleanExtra(String k,boolean f){Object v=extras.get(k);return v instanceof Boolean?(Boolean)v:f;}public String getStringExtra(String k){Object v=extras.get(k);return v instanceof String?(String)v:null;}public boolean hasExtra(String k){return extras.containsKey(k);}public Intent setData(android.net.Uri v){data=v;return this;}public android.net.Uri getData(){return data;}public String describe(){return extras.toString()+(data==null?"":" "+data);}}'
    }
    with tempfile.TemporaryDirectory(prefix='browser-preferences-host-') as raw:
        base=pathlib.Path(raw);src=base/'src';src.mkdir();(src/'BrowserPreferencesHost.java').write_text(source)
        for name in ['BrowserPreferences.java','BrowserAddressPolicy.java']:(src/name).write_bytes((PROD/name).read_bytes())
        for name,text in stubs.items():path=src/name;path.parent.mkdir(parents=True,exist_ok=True);path.write_text(text)
        classes=base/'classes';compiled=subprocess.run([str(args.java_home/'bin/javac'),'-encoding','UTF-8','-cp',str(args.json_jar.resolve()),'-d',str(classes),*map(str,src.rglob('*.java'))],capture_output=True,text=True)
        if compiled.returncode:raise RuntimeError(compiled.stderr)
        run=subprocess.run([str(args.java_home/'bin/java'),'-cp',str(classes)+':'+str(args.json_jar.resolve()),'local.pocketchat.BrowserPreferencesHost'],capture_output=True,text=True)
        if not run.stdout:raise RuntimeError(run.stderr)
        report=json.loads(run.stdout)
    report.update(sourceCommit=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),sourceFiles=hashes,extractedMainDispatchSha256=hashlib.sha256(dispatch.encode()).hexdigest(),jsonJarSha256=hashlib.sha256(args.json_jar.read_bytes()).hexdigest(),executionInputsUnchanged=all(path.is_file() and hashlib.sha256(path.read_bytes()).hexdigest()==hashes[str(path.relative_to(ROOT))] for path in paths),actualAndroidExecution=False,actualBrowserExecution=False,scope='Complete production BrowserPreferences and BrowserAddressPolicy plus exact MainActivity.dispatchBrowser method. Controlled Android Context/SharedPreferences/Intent/Uri/Activity, catalog availability and BrowserActivity-open adapters. Checks default/migration values, URL-only homepage validation, same-editor preference writes and commit failure propagation, exact routing bypasses and cold/warm session retention. Main onCreate/onNewIntent integration is source-inspected, not executed on Android. No WebView provider, runtime, cookies, network or device performance execution.')
    if not report['executionInputsUnchanged']:report['status']='source-changed'
    args.output.parent.mkdir(parents=True,exist_ok=True);args.output.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps({k:report[k] for k in ['status','passed','total']},ensure_ascii=False))
    if run.returncode or report['status']!='passed':raise SystemExit(1)
if __name__=='__main__':main()
