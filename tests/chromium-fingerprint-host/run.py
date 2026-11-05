#!/usr/bin/env python3
"""Run actual spec/runtime with declared Android facade edges and real UA metadata values."""
import argparse,hashlib,json,pathlib,subprocess,tempfile
ROOT=pathlib.Path(__file__).resolve().parents[2]
HERE=pathlib.Path(__file__).resolve().parent
STUBS={
'android/os/Looper.java':'''package android.os;public class Looper {static final Looper MAIN=new Looper();public static boolean main=true;public static Looper myLooper(){return main?MAIN:null;}public static Looper getMainLooper(){return MAIN;}}''',
'android/content/Context.java':'package android.content;public class Context{}',
'android/content/pm/PackageInfo.java':'package android.content.pm;public class PackageInfo{public String packageName,versionName;}',
'android/webkit/WebSettings.java':'''package android.webkit;public class WebSettings {public boolean block=true,refuse;public int sets;public String ua="Mozilla/5.0 (Linux; Android 14; native device) AppleWebKit/537.36 Version/4.0 Chrome/124.0.6367.219 Mobile Safari/537.36";public boolean getBlockNetworkLoads(){return block;}public String getUserAgentString(){return ua;}public void setUserAgentString(String next){sets++;if(!refuse)ua=next;}}''',
'android/webkit/WebView.java':'''package android.webkit;public class WebView {public final WebSettings settings=new WebSettings();public WebSettings getSettings(){return settings;}public android.content.Context getContext(){return new android.content.Context();}}''',
'androidx/webkit/WebViewFeature.java':'''package androidx.webkit;public class WebViewFeature {public static final String USER_AGENT_METADATA="USER_AGENT_METADATA",DOCUMENT_START_SCRIPT="DOCUMENT_START_SCRIPT";public static boolean metadata=true,document=true;public static boolean isFeatureSupported(String f){return f.equals(USER_AGENT_METADATA)?metadata:document;}}''',
'androidx/webkit/ScriptHandler.java':'package androidx.webkit;public interface ScriptHandler{void remove();}',
'androidx/webkit/WebViewCompat.java':'''package androidx.webkit;public class WebViewCompat {public static int added,removed;public static boolean fail,missingProvider;public static String script;public static java.util.Set<String> origins;public static android.content.pm.PackageInfo getCurrentWebViewPackage(android.content.Context c){if(missingProvider)return null;android.content.pm.PackageInfo p=new android.content.pm.PackageInfo();p.packageName="actual-value-object-host-provider";p.versionName="124.0.6367.219";return p;}public static ScriptHandler addDocumentStartJavaScript(android.webkit.WebView v,String s,java.util.Set<String> o){if(fail)throw new IllegalStateException("explicit native registration fault");added++;script=s;origins=o;return ()->{removed++;};}}''',
'androidx/webkit/WebSettingsCompat.java':'''package androidx.webkit;public class WebSettingsCompat {public static boolean mismatch;static final java.util.Map<android.webkit.WebSettings,UserAgentMetadata> VALUES=new java.util.WeakHashMap<>();public static UserAgentMetadata actual(){return new UserAgentMetadata.Builder().setBrandVersionList(java.util.List.of(new UserAgentMetadata.BrandVersion.Builder().setBrand("Chromium").setMajorVersion("124").setFullVersion("124.0.6367.219").build())).setFullVersion("124.0.6367.219").setPlatform("Android").setPlatformVersion("14.0.0").setArchitecture("arm").setModel("actual-device-host-boundary").setMobile(true).setBitness(64).build();}public static UserAgentMetadata getUserAgentMetadata(android.webkit.WebSettings s){return mismatch?actual():VALUES.getOrDefault(s,actual());}public static void setUserAgentMetadata(android.webkit.WebSettings s,UserAgentMetadata m){VALUES.put(s,m);}}'''
}
def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--java-home',required=True,type=pathlib.Path);p.add_argument('--json-jar',required=True,type=pathlib.Path);p.add_argument('--webkit-jar',required=True,type=pathlib.Path);p.add_argument('--output',required=True,type=pathlib.Path);a=p.parse_args()
 inputs=[ROOT/'app/src/main/java/local/pocketchat'/name for name in ['ChromiumFingerprintSpec.java','ChromiumFingerprintRuntime.java','J.java']]+[ROOT/'app/src/main/assets/chromium-fingerprint.js',HERE/'Cases.java',pathlib.Path(__file__).resolve()]
 hashes={str(f.relative_to(ROOT)):hashlib.sha256(f.read_bytes()).hexdigest() for f in inputs};cp=str(a.json_jar.resolve())+':'+str(a.webkit_jar.resolve())
 with tempfile.TemporaryDirectory(prefix='chromium-fingerprint-host-') as directory:
  temp=pathlib.Path(directory);src=temp/'src';src.mkdir()
  for name,body in STUBS.items():target=src/name;target.parent.mkdir(parents=True,exist_ok=True);target.write_text(body)
  classes=temp/'classes';cmd=[str(a.java_home/'bin/javac'),'-encoding','UTF-8','-cp',cp,'-d',str(classes),*map(str,inputs[:3]),str(HERE/'Cases.java'),*map(str,src.rglob('*.java'))]
  compiled=subprocess.run(cmd,capture_output=True,text=True,timeout=60)
  if compiled.returncode:raise RuntimeError(compiled.stderr)
  run=subprocess.run([str(a.java_home/'bin/java'),'-cp',str(classes)+':'+cp,'local.pocketchat.Cases',str(inputs[3])],capture_output=True,text=True,timeout=30)
  if run.returncode:raise RuntimeError(run.stdout+run.stderr)
  report=json.loads(run.stdout)
 report.update(sourceFiles=hashes,executionInputsUnchanged=all(hashlib.sha256((ROOT/name).read_bytes()).hexdigest()==sha for name,sha in hashes.items()),jsonJarSha256=hashlib.sha256(a.json_jar.read_bytes()).hexdigest(),webkitJarSha256=hashlib.sha256(a.webkit_jar.read_bytes()).hexdigest(),actualAndroidExecution=False,actualWebViewExecution=False,actualUserAgentMetadataClasses=True,scope='Complete production spec/runtime/J classes run with explicit Android/WebView feature, settings, provider and registration facade edges; actual supplied AndroidX UserAgentMetadata/Builder/BrandVersion Java value classes. Native facade behavior is controlled host input, not real provider support or page acceptance.')
 if not report['executionInputsUnchanged']:raise ValueError('Source changed during host execution')
 a.output.parent.mkdir(parents=True,exist_ok=True);a.output.write_text(json.dumps(report,indent=2)+'\n');print(json.dumps({'status':report['status'],'passed':report['passed'],'total':report['total'],'output':str(a.output)}))
if __name__=='__main__':main()
