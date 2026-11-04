from pathlib import Path
import argparse,subprocess,json,hashlib,os
root=Path(__file__).resolve().parents[2]
parser=argparse.ArgumentParser()
parser.add_argument('--java-home',type=Path,default=Path(os.environ.get('JAVA_HOME',root/'work/cloud-setup/jdk/usr/lib/jvm/java-17-openjdk-amd64')))
parser.add_argument('--output',type=Path,default=root/'work/chromium-runtime-native-check/report.json')
parser.add_argument('--android-jar',type=Path,default=root/'work/ux-build-toolchain/platform-37.1_r01/android-37.1/android.jar')
parser.add_argument('--webkit-jar',type=Path,default=root/'work/chromium-runtime-deps/webkit-1.14.0.jar')
parser.add_argument('--json-jar',type=Path,default=root/'work/ux-build-deps/json-20240303.jar')
args=parser.parse_args()
output=args.output.resolve();output.parent.mkdir(parents=True,exist_ok=True)
work=output.parent/(output.stem+'-work');work.mkdir(parents=True,exist_ok=True)
java=args.java_home.resolve()/'bin/javac'
android=args.android_jar.resolve();webkit=args.webkit_jar.resolve();jsonjar=args.json_jar.resolve()
def display(path):
 try:return str(path.relative_to(root))
 except ValueError:return str(path)
boundary=work/'AppBoundaries.java'
def exact_block(source, marker):
 start=source.index(marker); depth=0
 for at in range(start,len(source)):
  if source[at]=='{':depth+=1
  if source[at]=='}':
   depth-=1
   if depth==0:return source[start:at+1]
 raise ValueError(marker)
native_source=(root/'app/src/main/java/local/pocketchat/NativeNetwork.java').read_text()
receipt=exact_block(native_source,'  static final class ExitRouteReceipt {')
boundary.write_text('''package local.pocketchat;
import android.app.*;import android.content.*;import android.os.*;import android.webkit.*;import org.json.*;
class Profiles {static final int MAX=8;static int slot(Context context){return 0;}static int processSlot(){return 0;}static Context context(Context context,int slot){return context;}static Context global(Context context){return context;}}
class EnvironmentSpec {static class Identity{}}
class EnvironmentSpecRuntime {static void requireIdentity(Context context,EnvironmentSpec.Identity identity)throws Exception{}}
class ProfileCatalog {static ProfileCatalog get(Context context){return new ProfileCatalog();}EnvironmentSpec.Identity identity(int slot)throws java.io.IOException{return new EnvironmentSpec.Identity();}}
class NetworkTransportClient {JSONObject state;}
class NativeNetwork {boolean ready,starting,recoveryBlocked;String fingerprint="",token="",currentEntry="";long routeSerial;int controllerPort,proxyPort;java.lang.Process process;JSONObject settings;NetworkHealthPolicy.Admission admission=NetworkHealthPolicy.Admission.BLOCKED;NetworkTransportClient transport;ExitRouteReceipt verifiedRoute;static NativeNetwork get(Context context){return new NativeNetwork();}void addRouteListener(Runnable listener){}void removeRouteListener(Runnable listener){}interface Callback{void done(boolean ok,String text);}void start(Callback callback){}static String transportFingerprint(JSONObject settings){return "config";}NetworkHealthPolicy.Admission connectionAdmission(){ExitRouteReceipt receipt=verifiedRoute;return ready&&!recoveryBlocked&&receipt!=null&&receipt.matches(this,transport==null?null:transport.state)?admission:NetworkHealthPolicy.Admission.BLOCKED;}
__EXIT_ROUTE_RECEIPT__
}
class ChatSession {Context context;SharedPreferences prefs;WebView web;boolean deleted;Handler handler;ResourcesBoundary resources;static ChatSession peek(){return null;}boolean internalNetwork(){return false;}void updateBrowserActivity(){}}
class ResourcesBoundary {void sample(){}}
class AppAppearance {static void install(Application application){}static void refresh(Application application){}}
class AppVisibility {static void install(Application application){}}
class BackgroundReplyPolicy {static void bootstrap(Application application){}static void install(Application application){}}
'''.replace('__EXIT_ROUTE_RECEIPT__',receipt))
names=['ChromiumRuntime.java','ChromiumRoutePolicy.java','BrowserNetworkGuard.java','BrowserAddressPolicy.java','NetworkHealthPolicy.java','VpnDefaultRouteCoverage.java','PocketApplication.java','ProfileContext.java','EnvironmentProcessPolicy.java','EnvironmentBrowserData.java','DownloadLibraryChanges.java']
sources=[root/'app/src/main/java/local/pocketchat'/name for name in names]
result=subprocess.run([str(java),'-encoding','UTF-8','-cp',str(android)+':'+str(webkit),'-d',str(work/'classes'),str(boundary),*map(str,sources)],capture_output=True,text=True,timeout=60)
(work/'javac.log').write_text(result.stdout+result.stderr)
report={'status':'passed' if result.returncode==0 else 'failed','sources':{str(p.relative_to(root)):hashlib.sha256(p.read_bytes()).hexdigest() for p in sources},'androidJar':display(android),'androidJarSha256':hashlib.sha256(android.read_bytes()).hexdigest(),'webkitJar':display(webkit),'webkitJarSha256':hashlib.sha256(webkit.read_bytes()).hexdigest(),'scope':'Exact production Chromium runtime/policy, VPN guard, profile/context/application initialization, and cleanup compiled against actual Android37.1 and official AndroidXWebKit1.14.0 classes. Explicit app-network boundary doubles; no fake Android/Gecko/WebKit SDK. Does not establish WebView device behavior.','runtimeReceiptHost':'Exact production ChromiumRuntime.internalCurrent with verbatim production NativeNetwork.ExitRouteReceipt, explicit network/configuration fixture, and fixture-only Unsafe allocation bypassing Android constructors. 11 checks; not Android UI execution.','jsonJar':display(jsonjar),'jsonJarSha256':hashlib.sha256(jsonjar.read_bytes()).hexdigest(),'receiptProductionSha256':hashlib.sha256(receipt.encode()).hexdigest(),'runnerSha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),'hostSha256':hashlib.sha256((root/'tests/chromium-route-host/local/pocketchat/RuntimeReceiptCases.java').read_bytes()).hexdigest(),'fullApplicationCompile':False,'actualAndroidExecution':False}
print(result.stdout+result.stderr)
if result.returncode==0:
 host=root/'tests/chromium-route-host/local/pocketchat/RuntimeReceiptCases.java'
 cp=str(work/'classes')+':'+str(webkit)+':'+str(jsonjar)+':'+str(android)
 host_compile=subprocess.run([str(java),'-encoding','UTF-8','-cp',cp,'-d',str(work/'classes'),str(host)],capture_output=True,text=True)
 (work/'receipt-javac.log').write_text(host_compile.stdout+host_compile.stderr)
 if host_compile.returncode:
  report['status']='failed';report['failure']='receipt host compilation';output.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n');raise SystemExit(host_compile.returncode)
 fixture=subprocess.run([str(java.parent/'java'),'-cp',cp,'local.pocketchat.RuntimeReceiptCases'],capture_output=True,text=True)
 if fixture.returncode:report['status']='failed';report['failure']='receipt host assertion'
 report['runtimeReceiptOutput']=fixture.stdout.strip();report['runtimeReceiptPassed']=fixture.returncode==0
 print(fixture.stdout,end='')
 (work/'receipt-host.log').write_text(fixture.stdout)
report['javaVersion']=subprocess.check_output([str(java.parent/'java'),'-version'],stderr=subprocess.STDOUT,text=True).strip()
output.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
print(json.dumps({'status':report['status'],'sourceCount':len(sources),'output':str(output)}))
raise SystemExit(0 if report['status']=='passed' else 1)
